"""`mtk make TOPIC`: a video from one command, with no long-lived coordinator.

A script runs the pipeline (voice, checks, renders) and starts each model stage as a fresh headless agent that shares
files, not context: author, cold reader, one writer per scene, reviewer. Scene writers keep their sessions, so a fix
goes back to the agent that wrote the scene. Instructions come from the skill's own files, so there is one copy of them.
Every call's real usage goes to media/make/usage.jsonl; re-running after a failure resumes where it stopped.
"""
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from mtk_cli import script

SKILL = Path(__file__).parent / "plugin/skills/video"
MTK = str(Path(sys.executable).parent / "mtk")
PY = str(Path(sys.executable))
ALLOW = f"Read Write Edit WebSearch WebFetch Bash(mtk *) Bash({PY} *) Bash(cd *) Bash(ls *) Bash(cat *)"
WRITING = "Bash,Read,Write,Edit,WebSearch,WebFetch"
DIR = Path("media/make")
UP_ONE = dict(low="medium", medium="high", high="xhigh")
lock = threading.Lock()


def part(text, start, end):
    """The skill's text from one marker up to another; a missing marker means the skill changed under this driver."""
    i = text.index(start)
    return text[i:text.index(end, i)].strip()


def skill():
    """The stages' instructions, cut from SKILL.md."""
    s = (SKILL / "SKILL.md").read_text()
    how = part(s, "## 1. Understand the topic", "## 2. Set up")
    brief = part(s, "## 3. Write BRIEF.md", "**Read it as the viewer")
    kit = part(s, "Shared objects: if a visual", "## 4. Write the scenes")
    cold = re.sub(r"(?m)^> ?", "", part(s, "> You're about to watch", "\n\nMeanwhile"))
    run = "Run `cd <P> && mtk script BRIEF.md` and read only that\noutput (the narration, with what's on screen under each line); open no other file."
    assert run in cold, "the cold read's prompt changed in SKILL.md"
    return dict(author=f"{how}\n\n{brief}\n\n{kit}", fix=part(s, "Then fix the brief in one pass", "Run `mtk voice` once"),
                cold=cold.replace(run, "The script is below (the narration, with what's on screen under each line)."),
                review=part(s, "- `mtk check` (fast", "- Send fixes"))


def run(*cmd):
    r = subprocess.run([MTK, *cmd], capture_output=True, text=True)
    return r.stdout + r.stderr, r.returncode


def voiced():
    """`mtk voice`, until every line has the real voice: a draft voice mustn't reach a scene's timing or the final cut."""
    for wait in (0, 60, 300):
        time.sleep(wait)
        out = run("voice", "BRIEF.md")[0]
        if "LINT TTS" not in out or os.environ.get("MTK_TTS") == "say":
            return out
    sys.exit("the voice API keeps refusing lines (OpenRouter key limit?): " + out[:300])


def claude(stage, prompt, effort, resume=None, system=SKILL / "API.md", tools="Bash,Read,Write,Edit"):
    """One headless agent, on a minimal prefix (no user settings, MCP servers or skills). Returns (text, session id)."""
    cmd = ["claude", "-p", "--output-format", "json", "--model", "opus", "--effort", effort, "--setting-sources", "",
           "--strict-mcp-config", "--disable-slash-commands", "--tools", tools, "--allowedTools", ALLOW,
           "--permission-mode", "acceptEdits", "--max-budget-usd", "30"]  # a runaway guard: no stage comes near it
    if system:
        cmd += ["--system-prompt-file", str(system)]
    if resume:
        cmd += ["--resume", resume]
    last = ""
    for _ in range(2):  # one retry, in the same session so its work isn't paid for twice: a run can die on the network
        t0 = time.time()
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=3600)
            j = json.loads(r.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            last = str(e)[:500] + (r.stderr[-500:] if "r" in locals() else "")
            continue
        with lock, open(DIR / "usage.jsonl", "a") as f:
            f.write(json.dumps(dict(stage=stage, t0=t0, t1=time.time(), cost=j.get("total_cost_usd", 0),
                                    turns=j.get("num_turns"), usage=j.get("usage"), session=j.get("session_id"))) + "\n")
        if not j.get("is_error"):
            return j.get("result", ""), j["session_id"]
        last = j.get("result") or j.get("subtype") or ""
        if "--resume" not in cmd:
            cmd += ["--resume", j["session_id"]]
        prompt = "The connection dropped. Carry on from where you stopped."
    sys.exit(f"{stage}: the agent failed: {last}\nFix that and run the same command again: it resumes here.")


def load():
    p = DIR / "state.json"
    return json.loads(p.read_text()) if p.exists() else dict(done=[], sessions={})


def save(st):
    with lock:
        (DIR / "state.json").write_text(json.dumps(st, indent=1))


def author(a, st, sk):
    if "author" in st["done"]:
        return
    if "author" not in st:
        _, st["author"] = claude("author", f"Request: {a.topic}\n\nTarget length: {a.minutes} minutes.\n\nThe current "
                                 "directory is the project folder and BRIEF.md its skeleton: fill it in place. Your reference "
                                 f"for what the scenes can draw is in your system prompt. For throwaway numpy and sympy "
                                 f"checks use `{PY}`. Stop when the brief and any shared kit are written: a script runs the "
                                 f"voice pass and a cold read next.\n\n{sk['author']}", a.author_effort, tools=WRITING)
        save(st)
    with cf.ThreadPoolExecutor(2) as ex:  # the cold read and the voice pass overlap
        heard = run("script", "BRIEF.md")[0]
        cold = ex.submit(claude, "cold read", f"{sk['cold']}\n\n{heard}", "medium", None, None, "")
        said = ex.submit(voiced)
        notes, said = cold.result()[0], said.result()
    (DIR / "cold.md").write_text(notes)
    claude("author fix", f"Cold read of your brief:\n\n{notes}\n\n`mtk voice` says:\n\n{said}\n\n{sk['fix']}\n\nThe narration "
           f"must total at most {a.minutes}:00 with breaths; pay for additions by cutting rungs.", a.author_effort, st["author"],
           tools=WRITING)
    said = voiced()
    for _ in range(2):  # every later stage scales with the script, so a long one costs the whole pipeline
        m = re.search(r"TOTAL ~(\d+):(\d+)", said)
        if not m or int(m.group(1)) * 60 + int(m.group(2)) <= a.minutes * 60 * 1.05:
            break
        claude("author cut", f"The narration runs {m.group(1)}:{m.group(2)} against a target of {a.minutes}:00. Cut whole rungs or "
               "asides, not the crux, and keep the budgets true.", a.author_effort, st["author"], tools=WRITING)
        said = voiced()
    (DIR / "voice.txt").write_text(said)
    st["done"].append("author")
    save(st)


def writers(a, st):
    names = list(script("BRIEF.md"))
    if not names:
        sys.exit("BRIEF.md has no scenes")

    def one(i_name):
        i, name = i_name
        if name in st["sessions"]:
            return
        short = name.split("_")[0]
        _, sid = claude(f"scene {short}", f"Write scene {short} of the video in the current directory as "
                        f"{name.lower()}.py. The reference in your system prompt is complete; its loop and token rules "
                        f"are mandatory. Your brief, from `mtk brief BRIEF.md {short}`:\n\n"
                        f"{run('brief', 'BRIEF.md', short)[0]}\n\nRead nothing else. Report in at most 8 lines.",
                        UP_ONE[a.writer_effort] if i == 0 else a.writer_effort)  # the hook makes or breaks the video
        with lock:
            st["sessions"][name] = sid
        save(st)

    with cf.ThreadPoolExecutor(10) as ex:  # ~10 at once stays clear of usage limits
        list(ex.map(one, enumerate(names)))
    return names


def send(st, notes, why):
    """Hand each scene's notes back to the agent that wrote it, all at once."""
    def one(name):
        claude(f"fix {name.split('_')[0]}", f"{why}\n\n{notes[name]}\n\nFix each one and confirm it with `mtk check "
               f"{name.lower()}.py --agent`. Report in at most 4 lines.", "medium", st["sessions"][name])
    with cf.ThreadPoolExecutor(10) as ex:
        list(ex.map(one, notes))


def check(st, names):
    """Every scene runs, or goes back to its writer. Returns the check output."""
    for _ in range(3):
        out = run("check")[0]
        ok = {n for n in names if re.search(rf"^\S+ {n}  ", out, re.M)}
        bad = {}
        for n in set(names) - ok:
            m = re.search(rf"^FAILED \S+ {n}\b.*(?:\n    .*)*", out, re.M)
            bad[n] = m.group(0) if m else "Your scene's class is missing from the check."
        if not bad:
            return out
        send(st, bad, "The check of your scene failed. Open media/logs/ only if this doesn't say enough.")
    sys.exit("these scenes still fail after two rounds with their writers:\n" + "\n".join(bad))


def render(a):
    voiced()
    out, code = run("render", "--agent", "-q", a.q)
    if code or ("LINT TTS" in out and os.environ.get("MTK_TTS") != "say"):
        sys.exit(out)
    (DIR / "render.txt").write_text(out)
    return out


def mp4(rendered):
    return re.search(r"^(\S+\.mp4) ", rendered, re.M).group(1)


def reviews(a, st, names, out):
    """A full review, then a fresh reviewer confirms the fixes. Its notes go back once more, without a third review: each
    new reviewer otherwise finds new taste to raise, and the loop never settles."""
    sk, scope, notes = skill(), names, {}
    rendered = render(a)
    video = mp4(rendered)
    for rnd in range(1, 3):
        if "reviewed" in st["done"]:
            break
        if f"review {rnd}" in st["done"]:
            continue
        was = "\n".join(notes.values())
        path = Path("REVIEW.md")
        path.unlink(missing_ok=True)
        ask = (f"Scene writers answered these notes from the last review:\n{was}\n\nRead only the storyboards of "
               f"{', '.join(scope)}. Report only a note that isn't fixed or something the fix broke; the rest passed review, "
               "so raise nothing new." if was else sk["review"])
        claude(f"review {rnd}", f"You are reviewing an explainer video as its viewer would, in the current directory. "
               f"BRIEF.md is the script. Your reference for what the toolkit can draw is in your system prompt.\n\n{ask}\n\n"
               f"The video is {video}: check motion and full resolution with one image, `mtk frames {video} <4-6 seconds "
               f"mid-animation in the busiest scenes>`, then Read it. Every silence below must be deliberate.\n\n"
               f"`mtk check`:\n{out}\n\n`mtk render`:\n{rendered}\n\nWrite REVIEW.md: one line per real defect, nothing "
               "else, as `S03.2: what's wrong -> what to do` (S03 is the scene, 2 the beat; a problem across scenes gets a "
               "line per scene). Taste you can't tie to a viewer's confusion or a visible flaw isn't a defect. No "
               "defects: an empty file. Don't edit anything else.", "high", tools="Bash,Read,Write")
        text = path.read_text() if path.exists() else ""
        (DIR / f"review{rnd}.md").write_text(text)
        by = lambda ln: next((n for n in names if n.split("_")[0] == ln.split(".")[0].split(":")[0]), None)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        notes = {n: "\n".join(ln for ln in lines if by(ln) == n) for n in {by(ln) for ln in lines} - {None}}
        stray = [ln for ln in lines if not by(ln)]
        st["done"].append(f"review {rnd}")
        save(st)
        if not notes:
            st["done"].append("reviewed")
            save(st)
            return video, stray
        send(st, notes, "Review notes on your scene:")
        scope = list(notes)
        out = check(st, names)
        rendered = render(a)
        video = mp4(rendered)
    return video, []


def report(video, left):
    rows = [json.loads(x) for x in (DIR / "usage.jsonl").read_text().splitlines()]
    phases, seen = {}, {}
    for r in rows:  # a resumed session's total_cost_usd includes its earlier runs
        r["cost"], seen[r["session"]] = (r["cost"] or 0) - seen.get(r["session"], 0), r["cost"] or 0
        p = phases.setdefault(r["stage"].split()[0], dict(cost=0, calls=0, t0=r["t0"], t1=r["t1"]))
        p["cost"] += r["cost"]
        p["calls"] += 1
        p["t0"], p["t1"] = min(p["t0"], r["t0"]), max(p["t1"], r["t1"])
    for k, p in phases.items():
        print(f"{k:8s} {p['calls']:3d} agents  ${p['cost']:7.2f}  {(p['t1'] - p['t0']) / 60:5.1f} min")
    print(f"TOTAL    {len(rows):3d} agents  ${sum(r['cost'] for r in rows):7.2f}  "
          f"{(max(r['t1'] for r in rows) - min(r['t0'] for r in rows)) / 60:5.1f} min end to end")
    print(video)
    for ln in left:
        print("UNRESOLVED", ln)


def make(a):
    DIR.mkdir(parents=True, exist_ok=True)
    st = load()
    if not Path("BRIEF.md").exists():
        out, code = run("new", "x", "--dir", ".")
        if code:
            sys.exit(out)
    author(a, st, skill())
    names = writers(a, st)
    report(*reviews(a, st, names, check(st, names)))
