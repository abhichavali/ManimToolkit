"""mtk command line. Run from the video's project folder.

  mtk check  [files] [-s SCENE..] [-j N]   dry run (no video): LINT/REPORT lines + one storyboard per scene
                                           (a still at the end of every beat, captioned with its narration)
  mtk render [files] [-q l|m|h|k] [-o NAME] [-j N]   render (default h = 1080p30) and join into out/NAME.mp4
  mtk check --agent / --at 12.4,15         report only the beats that changed since the last check (and a sheet of
                                           just those) / full-size stills at chosen moments, with no video
  mtk render --agent                       same pixels, drawn in parallel inside each scene; redraws only changed plays
  mtk voice  BRIEF.md [--voice NAME]       voice the script (numbered "quoted" beats under ## S## headings) in
                                           parallel; print each scene's spoken length against its [budget]
  mtk brief  BRIEF.md S03|p02              what an agent needs: shared part + kit docstrings, its scene (or problem)
  mtk script BRIEF.md                      the script as its viewer meets it: Viewer/Knows, then every beat's words
                                           and picture, with ids (S03.2); no facts or plan (for the cold read)
  mtk episodes BRIEF.md [ep03 p02 ..]      after render: per episode (or problem) out/<stem>.mp4, web/<stem>.mp4
                                           under the artifact's 15 MB cap, poster .jpg, captions .vtt, web/episodes.json
  mtk youtube [ep01=URL ..]                after you upload out/<stem>.mp4 as Unlisted: the site embeds it from YouTube
                                           instead of shipping the file (not on claude.ai artifacts, which refuse embeds)
  mtk site [--title T] [--blurb B] [--out DIR]   after episodes: web/index.html, a study page around the videos
                                           (chapters, captions + transcript built in, resume, Chromium-safe seeking)
                                           plus the artifact publish plan (file maps in batches under 64 MB)
  mtk guide [guide.tex]                    after episodes: compile the study guide with each checkpoint's video time,
                                           crop every checkpoint for the site (web/guide.pdf, web/cp-*.png, guide.json)
  mtk serve [--dir web] [--port 8000]      serve the site locally, seekable, with the chat box answered by Claude
                                           using your key server-side (~/.anthropic_api_key or the project's)
  mtk make "TOPIC" [--minutes N] [--dir D]  the whole video with no coordinator: fresh headless agents per stage, a script
                                           between them; media/make/usage.jsonl has what each cost; re-run to resume
  mtk new SLUG [--walk]                    ~/Movies/Explainers/SLUG with a BRIEF.md skeleton (series or walkthroughs)
  mtk frames VIDEO SEC [SEC..]             one captioned sheet of full-quality frames, for spot checks
  mtk recipe [NAME]                        list the recipe gallery, or print one recipe's source

files default to every *.py here that defines S## scene classes. -s S03,S04 picks scenes by name prefix (any class, e.g. recipes).
All manim runs share global render slots (SLOTS env, default ~ RAM/1.3 GB, capped at the core count),
so parallel agents on one machine queue instead of swapping.
"""
import argparse
import concurrent.futures as cf
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MANIM = str(Path(sys.executable).parent / "manim")
SCENE = re.compile(r"^class (S\d\w*)\(", re.M)
ANY = re.compile(r"^class (\w+)\(", re.M)
QUAL = {"l": (["-ql"], "480p15"), "m": (["-qm"], "720p30"), "h": (["-qh", "--frame_rate", "30"], "1080p30"),
        "k": (["-qk"], "2160p60")}
TILE, COLS, PER_SHEET = (400, 225), 3, 15


def slots():
    if os.environ.get("SLOTS"):
        return int(os.environ["SLOTS"])
    ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30
    return max(1, min(os.cpu_count() or 1, int(ram * 0.75)))


def try_slot():
    """One of the machine-wide render slots if any is free (the fd holding it), else None."""
    d = Path.home() / ".cache/mtk/slots"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(slots()):
        fd = os.open(d / f"{i}.lock", os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            os.close(fd)


def grab_slot():
    """Block until one of the machine-wide render slots is free; returns the fd holding it."""
    while (fd := try_slot()) is None:
        time.sleep(0.5)
    return fd


def find(files, picks):
    picks = [x for p in picks or [] for x in p.split(",") if x]
    if not files:
        files = sorted(str(p) for p in Path(".").glob("*.py") if SCENE.search(p.read_text(errors="ignore")))
    out = []
    for f in files:
        src = Path(f).read_text()
        names = ANY.findall(src) if picks else SCENE.findall(src)
        out += [(f, n) for n in sorted(names) if not picks or any(n.startswith(p) for p in picks)]
    if not out:
        sys.exit(f"no scenes found in {files or 'this folder'}" + (f" matching {picks}" if picks else ""))
    return out


def manim(f, s, flags, env=None, slot=True):
    """Run one scene (one retry: parallel renders can race on the shared LaTeX cache). Returns (ok, log lines).
    A failed scene's log is kept at media/logs/<file>.<scene>.log. slot=False: the scene's workers take the slots."""
    tmp = Path("media/logs") / f"{Path(f).stem}.{s}.{os.getpid()}.log"  # concurrent checks don't share logs
    tmp.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        fd = grab_slot() if slot else None
        try:
            with open(tmp, "w") as out:
                ok = subprocess.run([MANIM, *flags, f, s], stdout=out, stderr=subprocess.STDOUT,
                                    env={**os.environ, "PYTHONWARNINGS": "ignore", "COLUMNS": "200", **(env or {})}
                                    ).returncode == 0
        finally:
            if fd is not None:
                os.close(fd)
        if ok:
            break
    ls = [ln.strip() for ln in re.split(r"[\r\n]", tmp.read_text(errors="ignore"))]
    if ok:
        tmp.unlink()
    else:
        tmp.rename(tmp.with_name(f"{Path(f).stem}.{s}.log"))
    return ok, ls


def marks(ls):
    """REPORT/LINT lines a scene printed."""
    return [m.group(0) for ln in ls for m in [re.search(r"(REPORT|LINT|AGENT) .*", ln)] if m]


def failure(f, s, ls):
    """Where it broke (frames in the user's files) and the exception line, from manim's rich traceback."""
    here = {p.name for p in Path(".").glob("*.py")} | {Path(f).name}
    where = []
    for ln in ls:
        m = re.search(r"([\w./-]+\.py):(\d+) in (\w+)", ln)
        if m and Path(m.group(1)).name in here:
            where.append(f"{Path(m.group(1)).name}:{m.group(2)} in {m.group(3)}")
    exc = [ln.strip("│ ") for ln in ls if re.match(r"^[│ ]*\w*(Error|Exception|Exit)\b", ln)]
    print(f"FAILED {Path(f).stem} {s}  (media/logs/{Path(f).stem}.{s}.log)")
    for ln in where[-3:] + (exc[-1:] or [x for x in ls if x][-1:]):
        print("   ", ln)


def prefetch(pairs):
    """Synthesize every literal narration line of the files in parallel before any scene runs. Scenes fetch
    their lines one by one as they play, so a first check of a new file otherwise waits minutes on TTS."""
    import ast
    import warnings
    warnings.filterwarnings("ignore", category=SyntaxWarning)  # pydub's, on import
    import mtk.core as core
    for f in dict.fromkeys(f for f, _ in pairs):
        tree = ast.parse(Path(f).read_text())
        voice = style = None
        for node in tree.body:  # module-level `core.VOICE = "..."` / `core.STYLE = "..."` overrides
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for t in node.targets:
                    if isinstance(t, ast.Attribute) and t.attr in ("VOICE", "STYLE"):
                        voice, style = (node.value.value, style) if t.attr == "VOICE" else (voice, node.value.value)
        lines = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("say", "beat", "predict"):
                k = 1 if n.func.attr == "predict" else 0
                kw = {x.arg: x.value for x in n.keywords}
                arg = n.args[k] if len(n.args) > k else kw.get("narration" if k else "text")
                st = kw.get("style")
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    lines.append((arg.value, st.value if isinstance(st, ast.Constant) else style))
        core.config.input_file = str(Path(f).resolve())  # tts() caches next to the scene file
        with cf.ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda ls: _quiet(core.tts, ls[0], voice, ls[1]), lines))


def _quiet(fn, *a):
    try:
        return fn(*a)
    except Exception:  # the scene run retries and reports it properly
        return None


def tiled(tiles, out, tile=TILE, cols=COLS):
    """Captioned sheet(s) from [(number, png, {"t", "text"}), ...]. Returns the paths."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.load_default(size=15)
    w, h = tile
    cap = 24
    paths = []
    for k in range(0, len(tiles), PER_SHEET):
        chunk = tiles[k:k + PER_SHEET]
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w + (cols - 1) * 4, rows * (h + cap + 4)), "#05060a")
        d = ImageDraw.Draw(sheet)
        for i, (n, p, b) in enumerate(chunk):
            x, y = (i % cols) * (w + 4), (i // cols) * (h + cap + 4)
            sheet.paste(Image.open(p).convert("RGB").resize(tile), (x, y))
            txt = f"{n}  {b['t']:.1f}s  {b['text'] or '(wipe)'}"
            while d.textlength(txt, font=font) > w - 8 and len(txt) > 4:
                txt = txt[:-2].rstrip() + "…"
            d.text((x + 4, y + h + 4), txt, fill="#c8ccd6", font=font)
        path = out if k == 0 else out.with_name(f"{out.stem}.{k // PER_SHEET + 1}.png")
        sheet.save(path)
        paths.append(path)
    return paths


def beat_tiles(snapdir):
    beats = json.loads((snapdir / "beats.json").read_text()) if (snapdir / "beats.json").exists() else []
    return [(i + 1, p, beats[i] if i < len(beats) else {"t": 0, "text": ""})
            for i, p in enumerate(sorted(snapdir.glob("[0-9][0-9].png")))]


def board(snapdir, out):
    """Tile a scene's beat stills into captioned storyboard sheet(s). Returns (paths, changed?)."""
    tiles = beat_tiles(snapdir)
    if not tiles:
        return [], False
    digest = hashlib.sha1(b"".join(p.read_bytes() for _, p, _ in tiles)
                          + json.dumps([{k: b[k] for k in ("t", "text") if k in b} for _, _, b in tiles]).encode()).hexdigest()
    sha = out.with_suffix(".sha")
    changed = not sha.exists() or sha.read_text() != digest
    paths = tiled(tiles, out)
    sha.write_text(digest)
    return paths, changed


def beat_diff(snapdir, out):
    """`mtk check --agent`: which beats' pictures differ from the last check of this scene, as (lines, sheet paths,
    number changed, number of beats). A beat is matched by its narration, so inserting one doesn't mark everything after it as changed. A sheet holds
    only the changed beats; each line names what moved, so a fix can often be confirmed without opening an image."""
    tiles = beat_tiles(snapdir)
    mem = out.with_suffix(".beats.json")
    old = json.loads(mem.read_text()) if mem.exists() else None
    now = [dict(b, sha=hashlib.sha1(p.read_bytes()).hexdigest()) for _, p, b in tiles]
    mem.write_text(json.dumps(now))
    seen = {(b["text"], b["sha"]) for b in old or []}
    fresh = [t for t, b in zip(tiles, now) if (b["text"], b["sha"]) not in seen]
    lines = []
    for n, _, b in fresh if old is not None else []:
        was = next((x["on"] for x in old if x["text"] == b["text"]), None)
        head = f"beat {n} {b['t']:.1f}s {(b['text'] or '(wipe)')[:48]!r}"
        lines.append(f"{head}: new beat" if was is None else f"{head}: {on_screen_diff(was, b['on'])}")
    sheet = out.with_name(f"{out.stem}.diff.png")
    return lines, tiled(fresh, sheet) if fresh else [], len(fresh), len(tiles)


def on_screen_diff(was, now):
    """What changed in the visible text, or that only the rest of the picture did."""
    out = [f"+{k}" for k in now if k not in was] + [f"-{k}" for k in was if k not in now]
    for k in now:
        if k in was and now[k] != was[k]:
            a, b = was[k], now[k]
            what = ("color " + b[4]) if a[:4] == b[:4] else f"({a[0]},{a[1]})->({b[0]},{b[1]})"
            out.append(f"~{k} {what}")
    return " ".join(out)[:240] or "same text, other shapes changed"


HEAD = re.compile(r"^#+\s*(S\d+\w*)(?:[^\[]*\[(\d+)\])?")
BEAT = re.compile(r'^\s*\d+[.)]\s+"([^"]+)"(?:\s*\(style:\s*([^)]*)\))?')


def script(path):
    """{scene: (budget words, [(narration, style), ...])} from a script-first brief."""
    out, cur = {}, None
    for ln in Path(path).read_text().splitlines():
        h = HEAD.match(ln)
        if h:
            cur = h.group(1)
            out[cur] = (int(h.group(2)) if h.group(2) else None, [])
        elif cur and BEAT.match(ln):
            b = BEAT.match(ln)
            out[cur][1].append((b.group(1).strip(), b.group(2)))
    return out


HANDWAVE = re.compile(r"\b(clearly|obviously|trivially|of course|it'?s (?:easy|not hard) to see|it is (?:easy|not hard) "
                      r"to see|it turns out|it can be shown|one can show|it follows that|needless to say|as you know)\b",
                      re.I)


def beat_lints(t):
    """What a teacher would flag in one narration line."""
    out = [f'"{m}" asks the viewer to take a step on trust: show the reason, or say plainly it\'s skipped'
           for m in dict.fromkeys(x.group(0).lower() for x in HANDWAVE.finditer(t))]
    if len(t.split()) > 50:
        out.append(f"{len(t.split())} words: one idea per beat; split it so the picture can keep up")
    return out


def as_heard(a):
    """`mtk script`: who the viewer is, then each beat's words and picture. No facts, no plan, no insight line."""
    ls = Path(a.brief).read_text().splitlines()
    who, on = [], False
    for ln in ls:  # the **Viewer** and **Knows** paragraphs, wrapped lines included
        on = ln.startswith(("**Viewer**", "**Knows**")) or (on and ln.strip() and not ln.startswith(("**", "#")))
        if on:
            who.append(ln)
    print("\n".join(who) or "(no **Viewer** or **Knows** line: assume only what the narration itself explains)")
    cur = None
    for ln in ls:
        if GROUP.match(ln):
            print(f"\n{ln}")
        elif HEAD.match(ln):
            cur, k = HEAD.match(ln).group(1), 0
            print("\n" + re.sub(r"\s*\[\d+\]", "", ln))
        elif cur and BEAT.match(ln):
            k += 1
            print(f'{cur.split("_")[0]}.{k} "{BEAT.match(ln).group(1)}"')
        elif cur and ln.strip().startswith(("→", "->")):
            print("     " + ln.strip())


def voice(a):
    import warnings
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    import mtk.core as core
    sc = script(a.brief)
    if not any(bs for _, bs in sc.values()):
        print("no scripted beats (fine for walkthroughs: their agents write the narration). A script looks like:\n"
              '  ## S01_Name [words]\n  1. "Narration."\n     → what the screen does')
        return
    core.config.input_file = str(Path(a.brief).resolve())  # audio/ next to the brief = the project folder
    jobs = [(t, st) for _, bs in sc.values() for t, st in bs]
    with cf.ThreadPoolExecutor(8) as ex:
        got = dict(zip(jobs, ex.map(lambda j: _quiet(core.tts, j[0], a.voice, j[1]), jobs)))
    ls = Path(a.brief).read_text().splitlines()
    starts = [i for i, ln in enumerate(ls) if GROUP.match(ln) or HEAD.match(ln)]
    head = "\n".join(ls[:starts[0]] if starts else ls)
    if "colors(" not in head:
        print("BRIEF: the shared part has no colors(...) line; every file should start with the same one")
    for k, why in (("**Knows**", "what the viewer already knows; everything else is explained before it's used"),
                   ("**Crux**", "the step(s) where understanding is won or lost; they get the most time")):
        if k not in head:
            print(f"BRIEF: no {k} line: {why}")
    if not any("spotlight(" in ln for ln in ls if ln.strip().startswith(("→", "->"))):
        print("BRIEF: no key moment: flag the crux out loud, slow it down, and spotlight it (→ self.spotlight(...))")
    cur = None
    for i, ln in enumerate(ls):  # every beat needs its picture line
        cur = HEAD.match(ln).group(1) if HEAD.match(ln) else cur
        if BEAT.match(ln):
            nxt = next((x.strip() for x in ls[i + 1:] if x.strip()), "")
            if not nxt.startswith(("→", "->")):
                print(f"BRIEF {cur} beat {ln.strip().split('.')[0]}: no '→ picture' line under it")
    total = words = 0.0
    for name, (budget, bs) in sc.items():
        if not bs:
            print(f"{name:24s} (no script: its agent writes the narration)" + ("" if budget else "; no [budget]"))
            continue
        if not budget:
            print(f"BRIEF {name}: no [budget] in its heading")
        w = sum(len(t.split()) for t, _ in bs)
        sec = sum(got[b][1] for b in bs if got[b]) + 0.3 * len(bs) + 1.0  # breaths + the closing wipe
        total, words = total + sec, words + w
        flag = f"  <- {w - budget:+d} words vs [{budget}]" if budget and abs(w - budget) > 0.15 * budget else ""
        print(f"{name:24s} {len(bs):2d} beats {w:4d}w  ~{sec:5.1f}s{flag}")
        for i, (t, _) in enumerate(bs, 1):
            bad = sorted(set(core.SYMBOLS.findall(t)))
            if bad:
                print(f"    beat {i}: contains {' '.join(bad)}; spell math out")
            for x in beat_lints(t):
                print(f"    beat {i}: {x}")
            if not got[(t, _)]:
                print(f"    beat {i}: voice failed (the scene's check will retry)")
    print(f"TOTAL ~{int(total // 60)}:{int(total % 60):02d} of narration with breaths ({int(words)} words); "
          "animation overruns add a little")


def kits(folder):
    """Docstrings of the project's shared (non-scene) modules, so scene agents get their API without a Read."""
    import ast
    for f in sorted(Path(folder).glob("*.py")):
        src = f.read_text(errors="ignore")
        if SCENE.search(src) or f.name.startswith("_"):
            continue
        doc = ast.get_docstring(ast.parse(src))
        if doc:
            print(f"\nSHARED KIT {f.name} (from {f.stem} import *):\n{doc}")


def brief(a):
    path = Path(a.brief)
    ls = path.read_text().splitlines()
    starts = [i for i, ln in enumerate(ls) if GROUP.match(ln) or HEAD.match(ln)]
    print("\n".join(ls[:starts[0]] if starts else ls).rstrip())
    kits(path.parent)
    grp = [i for i, ln in enumerate(ls) if GROUP.match(ln) and _gstem(GROUP.match(ln)) == a.scene.lower()]
    if grp:  # a whole episode or problem: every scene in it
        i = grp[0]
        end = next((j for j in range(i + 1, len(ls)) if GROUP.match(ls[j])), len(ls))
        names = [HEAD.match(x).group(1) for x in ls[i:end] if HEAD.match(x)]
        print(f"\nYOURS: {', '.join(names)}, all in {a.scene.lower()}.py (budgets are narration words)\n")
        print("\n".join(ls[i:end]).rstrip())
        return
    heads = [i for i, ln in enumerate(ls) if ln.startswith("#")]
    scenes = [i for i in heads if HEAD.match(ls[i])]
    hit = [i for i in scenes if HEAD.match(ls[i]).group(1).startswith(a.scene)]
    if not hit:
        sys.exit(f"no scene or group {a.scene} in {a.brief}")
    i = hit[0]
    end = next((j for j in heads if j > i), len(ls))
    name = HEAD.match(ls[i]).group(1)
    k = scenes.index(i)
    for label, j in (("Before you", k - 1), ("After you", k + 1)):
        if 0 <= j < len(scenes):
            first = next((BEAT.match(x).group(1) for x in ls[scenes[j]:] if BEAT.match(x)), "")
            print(f"\n{label}: {ls[scenes[j]].lstrip('# ')}" + (f' (opens: "{first[:90]}")' if first else ""))
    budget = HEAD.match(ls[i]).group(2)
    print(f"\nYOUR SCENE: class {name}(Doc) in {name.lower()}.py"
          + (f", budget = {budget} (narration words, not seconds)" if budget else "") + "\n")
    print("\n".join(ls[i:end]).rstrip())


def check(a):
    pairs = find(a.files, a.scene)
    prefetch(pairs)
    Path("media/board").mkdir(parents=True, exist_ok=True)

    def one(fs):
        f, s = fs
        snaps = Path("media/snaps") / f"{Path(f).stem}.{s}.{os.getpid()}"
        out = Path("media/board") / f"{Path(f).stem}.{s}.png"
        if a.at:  # full-size stills at chosen moments, on the final render's clock
            ok, ls = manim(f, s, ["-qh", "--frame_rate", "30", "--dry_run", "--disable_caching"],
                           {"MTK_SNAP": str(snaps.resolve()), "MTK_AT": a.at})
            res = (tiled(beat_tiles(snaps), out.with_name(f"{out.stem}.at.png"), (960, 540), 2), True) if ok else ([], False)
            shutil.rmtree(snaps, ignore_errors=True)
            return ok, ls, res, None, None
        ok, ls = manim(f, s, ["-ql", "--dry_run", "--disable_caching", "--frame_rate", "10"],
                       {"MTK_SNAP": str(snaps.resolve())})
        res = board(snaps, out) if ok else ([], False)
        diff = beat_diff(snaps, out) if ok and a.agent else None
        pal = json.loads((snaps / "palette.json").read_text()) if (snaps / "palette.json").exists() else None
        shutil.rmtree(snaps, ignore_errors=True)
        return ok, ls, res, pal, diff

    with cf.ThreadPoolExecutor(a.jobs or slots()) as ex:
        results = list(ex.map(one, pairs))
    if a.at:
        for (f, s), (ok, ls, (paths, _), _, _) in zip(pairs, results):
            if not ok:
                failure(f, s, ls)
            print(*paths, sep="\n")
        return
    if a.agent:
        return agent_report(pairs, results)
    total = words = nlint = 0
    fresh = []
    for (f, s), (ok, ls, (paths, changed), _, _) in zip(pairs, results):
        if not ok:
            failure(f, s, ls)
            continue
        ms = marks(ls)
        rep = next((m for m in ms if m.startswith("REPORT")), "REPORT ? 0s 0w")
        sec = float(re.search(r" ([\d.]+)s", rep).group(1))
        total += sec
        words += int(re.search(r" (\d+)w", rep).group(1))
        lint = [m for m in ms if m.startswith("LINT")]
        nlint += len(lint)
        tag = "NEW " if changed else "same"
        if changed:
            fresh += paths
        info = rep.split(" ", 2)[2]
        print(f"{Path(f).stem} {s}  {info}  [{tag}] {' '.join(str(p) for p in paths) or '(no stills)'}")
        for m in lint:
            print("   ", m)
    drift(pairs, [r[3] for r in results])
    print(f"TOTAL {int(total // 60)}:{int(total % 60):02d}  {words} words  {nlint} lint  "
          f"{len(fresh)} new/changed storyboard(s) to look at; unchanged ones are marked [same]")


def agent_report(pairs, results):
    """`mtk check --agent`: same checks as mtk check, but only what changed since the last one, and what reading it costs."""
    from PIL import Image
    total = nlint = changed = beats = cost = 0
    for (f, s), (ok, ls, _, _, diff) in zip(pairs, results):
        if not ok:
            failure(f, s, ls)
            continue
        ms = marks(ls)
        rep = next((m for m in ms if m.startswith("REPORT")), "REPORT ? 0s 0w")
        total += float(re.search(r" ([\d.]+)s", rep).group(1))
        lint = [m for m in ms if m.startswith("LINT")]
        nlint += len(lint)
        lines, sheets, n, of = diff
        changed, beats = changed + n, beats + of
        cost += sum(w * h // 750 for w, h in (Image.open(p).size for p in sheets))  # Claude's image token estimate
        print(f"{Path(f).stem} {s}  {rep.split(' ', 2)[2]}  {n}/{of} beats changed"
              + "".join(f"  {p}" for p in sheets))
        for m in lint + lines:
            print("   ", m)
    drift(pairs, [r[3] for r in results])
    print(f"TOTAL {int(total // 60)}:{int(total % 60):02d}  {nlint} lint  {changed}/{beats} beats changed  "
          f"~{cost} image tokens to look at them")


def drift(pairs, pals):
    """DRIFT lines: a concept (a colors() key) whose usual color differs between scenes."""
    import mtk.core as core
    names = {getattr(core, n).lower(): n for n in ("SKY", "EMBER", "MINT", "LILAC", "LIME", "ROSE", "GOLD", "INK",
                                                  "INK2", "MUTED", "ACCENT", "GOOD", "BAD")}
    pals = [(s, p) for (_, s), p in zip(pairs, pals) if p]
    concepts = set().union(*[p["concepts"] for _, p in pals]) if pals else set()
    seen = {}
    for s, p in pals:
        for tok, col in p["tokens"].items():
            if tok in concepts:  # only declared concepts: axis labels and the like are muted on purpose
                seen.setdefault(tok, {}).setdefault(col, []).append(s.split("_")[0])
    for tok, cols in sorted(seen.items()):
        if len(cols) > 1:
            print(f"DRIFT {tok}: " + "; ".join(f"{names.get(c, c)} in {','.join(v)}" for c, v in cols.items()))


def join(pairs, vids, out):
    """Concat scene videos into out with gap-free audio, write out.vtt captions from the narration log;
    returns chapters [(start s, file stem, scene)]."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as lst:
        lst.writelines(f"file '{v.resolve()}'\n" for v in vids)
    # each scene's audio ends before its video does, so a plain concat leaves timestamp gaps that drift in
    # editors and some players; aresample fills them with silence and apad pads the tail to the video's end
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst.name,
                    "-c:v", "copy", "-af", "aresample=async=1:first_pts=0,apad", "-shortest", "-c:a", "aac",
                    "-b:a", "192k", str(out)], check=True)
    os.unlink(lst.name)
    chapters, t = [], 0.0
    for (f, s), v in zip(pairs, vids):
        chapters.append((t, Path(f).stem, s))
        t += dur(v)
    vtt(chapters, out.with_suffix(".vtt"))
    return chapters


def checkpoints(chapters):
    """Guide checkpoints logged at render (Narrated.checkpoint), on the joined video's clock."""
    out = []
    for t0, stem, s in chapters:
        f = Path("media/subs") / f"{stem}.{s}.marks.json"
        for m in json.loads(f.read_text()) if f.exists() else []:
            out.append({"id": m["id"], "t": round(t0 + m["t"], 2), "prompt": m["prompt"], "scene": s})
    return out


def vtt(chapters, path):
    """WebVTT from media/subs/<file>.<Scene>.json (say() logs every line during a render), offset per chapter.
    Lines become one cue per sentence, timed in proportion to length. Returns the path, or None without subs."""
    cues = []
    for t0, stem, s in chapters:
        f = Path("media/subs") / f"{stem}.{s}.json"
        for c in json.loads(f.read_text()) if f.exists() else []:
            parts = [x for x in re.split(r"(?<=[.!?])\s+", c["text"].strip()) if x]
            t, n = t0 + c["t"], sum(map(len, parts))
            for x in parts:
                d = c["dur"] * len(x) / n
                cues.append((t, t + d, x))
                t += d
    if not cues:
        return None
    ts = lambda x: f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{x % 60:06.3f}"
    path.write_text("WEBVTT\n\n" + "\n".join(f"{ts(a)} --> {ts(b)}\n{x}\n" for a, b, x in cues))
    return path


def scene_key(f, s, q):
    """A hash of what a rendered scene depends on: its file, the kits and scene files it names, the toolkit, data files
    beside it, and (while draft voices exist, since a real voice can replace one) which voices are cached."""
    src = Path(f).read_bytes()
    pkg = Path(importlib.util.find_spec("mtk").origin).parent
    h = hashlib.sha1(f"{s} {q} {os.environ.get('MTK_TTS')}".encode() + src)
    for p in sorted(pkg.glob("*.py")) + sorted(x for x in Path(".").glob("*.py") if x.name != Path(f).name):
        if p.parent == pkg or not SCENE.search(p.read_text(errors="ignore")) or re.search(rb"\b%s\b" % p.stem.encode(), src):
            h.update(p.read_bytes())
    for p in sorted(x for x in Path(".").glob("*") if x.is_file() and x.suffix not in (".py", ".md")):
        h.update(f"{p.name} {p.stat().st_size} {p.stat().st_mtime_ns}".encode())
    names = sorted(x.name for x in Path(Path(f).parent / "audio").glob("*.wav"))
    if any(n.endswith(".say.wav") for n in names):
        h.update(" ".join(names).encode())
    return h.hexdigest()


def render(a):
    pairs = find(a.files, a.scene)
    prefetch(pairs)
    flags, res = QUAL[a.q]

    def agent(fs):
        f, s = fs
        vid = Path("media/videos") / Path(f).stem / res / f"{s}.mp4"
        stamp, key = vid.with_suffix(".key"), scene_key(f, s, a.q)
        if vid.exists() and stamp.exists() and stamp.read_text() == f"{key} {vid.stat().st_mtime_ns}":
            return True, [f"AGENT {s} 0 plays 0 reused 0/0 frames drawn"]  # nothing it depends on changed: don't even run it
        ok, ls = manim(f, s, [*flags, "--disable_caching", "--progress_bar", "none"], {"MTK_AGENT": "1"}, slot=False)
        if ok:
            stamp.write_text(f"{key} {vid.stat().st_mtime_ns}")
            return ok, ls
        print(f"agent renderer failed on {s}; rendering it the classic way", flush=True)  # same pixels, just slower
        return manim(f, s, flags)

    with cf.ThreadPoolExecutor(a.jobs or slots()) as ex:
        results = list(ex.map(agent if a.agent else lambda fs: manim(*fs, flags), pairs))
    if a.agent:
        got = [re.search(r"(\d+) plays (\d+) reused (\d+)/(\d+)", m).groups() for _, ls in results for m in marks(ls)
               if m.startswith("AGENT")]
        p, r, d, n = (sum(int(x[i]) for x in got) for i in range(4))
        print(f"agent: drew {d}/{n} frames; reused {r}/{p} plays")
    bad = False
    for (f, s), (ok, ls) in zip(pairs, results):
        if not ok:
            bad = True
            failure(f, s, ls)
        else:
            for m in marks(ls):
                if m.startswith("LINT"):
                    print("   ", m)
    if bad:
        sys.exit(1)
    vids = [Path("media/videos") / Path(f).stem / res / f"{s}.mp4" for f, s in pairs]
    name = a.o or (Path(pairs[0][0]).stem if len({f for f, _ in pairs}) == 1 else Path.cwd().name)
    Path("out").mkdir(exist_ok=True)
    out = Path("out") / f"{name}.mp4"
    chapters = join(pairs, vids, out)
    cap = out.with_suffix(".vtt")
    print(f"{out.resolve()}  {dur(out):.1f}s" + (f"  captions: {cap}" if cap.exists() else "") + "\nchapters:")
    for t, stem, s in chapters:
        print(f"  {int(t // 60)}:{int(t % 60):02d}  {stem} {s}")
    for c in checkpoints(chapters):
        print(f"  {int(c['t'] // 60)}:{int(c['t'] % 60):02d}  checkpoint {c['id']}: {c['prompt']}")
    sil = subprocess.run(["ffmpeg", "-nostdin", "-i", str(out), "-vn", "-af", "silencedetect=noise=-45dB:d=3", "-f",
                          "null", "-"], capture_output=True, text=True).stderr
    for m in re.finditer(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", sil):
        print(f"  silence {float(m.group(2)):.1f}s ending at {float(m.group(1)):.1f}s")


GROUP = re.compile(r"^#\s+(Episode|Problem)\s+(\d+)\s*[:.]?\s*(.*)$", re.I)


def _gstem(m):
    return f"{'ep' if m.group(1).lower() == 'episode' else 'p'}{int(m.group(2)):02d}"


def groups(path):
    """Videos in a brief: '# Episode 3: Title | sub' / '# Problem 3: ...' headings group the '## S..' scenes after
    them (stems ep03 / p03); without such headings the whole brief is one video, ep01. Chapter labels: the text
    after [budget] in a scene heading, else the scene name."""
    out, cur, title = [], None, ""
    for ln in Path(path).read_text().splitlines():
        g = GROUP.match(ln)
        if g:
            t, _, sub_ = g.group(3).partition("|")
            cur = dict(stem=_gstem(g), kind=g.group(1).lower(), n=int(g.group(2)), title=t.strip(),
                       sub=sub_.strip(), scenes=[], labels={})
            out.append(cur)
        elif not title and re.match(r"^#\s+\S", ln):
            title = re.sub(r"\s*\(~?[\d.]+\s*min\)\s*$", "", ln[1:].strip())
        elif HEAD.match(ln):
            if cur is None:
                cur = dict(stem="ep01", kind="episode", n=1, title=title, sub="", scenes=[], labels={})
                out.append(cur)
            name = HEAD.match(ln).group(1)
            label = re.sub(r"^#+\s*S\d+\w*\s*(\[\d+\])?\s*", "", ln).strip()
            cur["scenes"].append(name)
            cur["labels"][name] = label or (name.split("_", 1)[1].replace("_", " ") if "_" in name else name)
    return out


def episodes(a):
    gs = [g for g in groups(a.brief) if not a.which or g["stem"] in a.which]
    where = {s: p.stem for p in Path(".").glob("*.py") for s in SCENE.findall(p.read_text(errors="ignore"))}
    res = QUAL[a.q][1]
    Path("out").mkdir(exist_ok=True)
    Path("web").mkdir(exist_ok=True)
    mpath = Path("web/episodes.json")
    man = {e["stem"]: e for e in json.loads(mpath.read_text())} if mpath.exists() else {}
    for g in gs:
        vids = [Path("media/videos") / where.get(s, "?") / res / f"{s}.mp4" for s in g["scenes"]]
        missing = [s for s, v in zip(g["scenes"], vids) if not v.exists()]
        if missing:
            print(f"{g['stem']}: not rendered at {res} yet: {' '.join(missing)} (run mtk render first)")
            continue
        full = Path("out") / f"{g['stem']}.mp4"
        chapters = join([(where[s] + ".py", s) for s in g["scenes"]], vids, full)
        total = dur(full)
        cap = min(a.max_mb, a.mb_per_min * total / 60 if a.mb_per_min else a.max_mb) * 1e6
        web = Path("web") / f"{g['stem']}.mp4"
        for crf in range(a.crf, 52, 2):  # up to x264's max (51): a 17-min 1080p episode needed 42 to fit 14.5 MB
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(full), "-c:v", "libx264",
                            "-preset", "slow", "-tune", "animation", "-crf", str(crf), "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-movflags", "+faststart", str(web)], check=True)
            if web.stat().st_size < cap:
                break
        size = web.stat().st_size
        poster = web.with_suffix(".jpg")
        at = chapters[1][0] + 4 if len(chapters) > 1 else 3.0
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", str(at), "-i", str(full),
                        "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "4", str(poster)], check=True)
        cues = full.with_suffix(".vtt")
        if cues.exists():
            shutil.copy(cues, web.with_suffix(".vtt"))
        was = man.get(g["stem"], {}).get("youtube")
        if was:  # chapters and checkpoints now follow this build, so the old upload may be out of sync with them
            print(f"{g['stem']}: rebuilt, so it plays its local file again. Upload {full} and run mtk youtube "
                  f"{g['stem']}=URL (or {g['stem']}={was} if the picture and timing didn't change)")
        man[g["stem"]] = dict(stem=g["stem"], kind=g["kind"], n=g["n"], title=g["title"], sub=g["sub"],
                              file=web.name, poster=poster.name,
                              captions=web.with_suffix(".vtt").name if cues.exists() else None,
                              duration=round(total, 1), mb=round(size / 1e6, 2), checkpoints=checkpoints(chapters),
                              chapters=[{"t": round(t, 1), "label": g["labels"][s], "scene": s} for t, _, s in chapters])
        over = "  OVER THE CAP" if size >= cap else ""
        print(f"{g['stem']} {g['title']}: {total / 60:.2f} min, {len(chapters)} chapters, web {size / 1e6:.1f} MB "
              f"at crf {crf}{over}")
    mpath.write_text(json.dumps(sorted(man.values(), key=lambda e: (e["kind"], e["n"])), indent=1, ensure_ascii=False))
    print(f"{mpath}: {len(man)} videos, {sum(e['duration'] for e in man.values()) / 60:.1f} min")


YT_ID = re.compile(r"(?:^|v=|youtu\.be/|/embed/|/shorts/|/live/)([\w-]{11})(?:$|[?&#/])")


def youtube(a):
    """`mtk youtube ep01=URL ..`: these videos play from YouTube on the site (`ep01=` puts one back on its local file).
    No arguments: what's where. Uploading is by hand: YouTube locks API uploads from unaudited projects to private."""
    import urllib.error
    import urllib.request
    mpath = Path("web/episodes.json")
    if not mpath.exists():
        sys.exit("no web/episodes.json here: run mtk episodes first")
    vids = json.loads(mpath.read_text())
    by = {e["stem"]: e for e in vids}
    for pair in a.pairs:
        stem, eq, url = pair.partition("=")
        if not eq or stem not in by:
            sys.exit(f"{pair}: expected STEM=URL with STEM one of {' '.join(by)}")
        if not url:
            by[stem].pop("youtube", None)
            continue
        m = YT_ID.search(url.strip())
        if not m:
            sys.exit(f"{pair}: no YouTube video id in that")
        try:
            urllib.request.urlopen(f"https://www.youtube.com/oembed?format=json&url=https://youtu.be/{m[1]}", timeout=15)
        except urllib.error.HTTPError as e:
            sys.exit(f"{stem}: YouTube won't embed {m[1]} (HTTP {e.code}): it must exist, be Unlisted or Public, and "
                     "have Allow embedding on")
        except urllib.error.URLError as e:
            print(f"{stem}: couldn't reach YouTube to check {m[1]} ({e.reason}); saved anyway")
        by[stem]["youtube"] = m[1]
    if a.pairs:
        mpath.write_text(json.dumps(vids, indent=1, ensure_ascii=False))
    for e in vids:
        print(f"{e['stem']}  " + (f"https://youtu.be/{e['youtube']}" if e.get("youtube")
                                  else f"local (upload out/{e['stem']}.mp4 as Unlisted, then mtk youtube {e['stem']}=URL)"))
    if a.pairs:
        print("now run mtk site")


def guide(a):
    from PIL import Image
    pkg = Path(importlib.util.find_spec("mtk").origin).parent / "site"
    src = Path(a.tex)
    if not src.exists():
        shutil.copy(pkg / "guide.tex", src)
        sys.exit(f"wrote {src} from the template: fill it in (the skill's guide.md has the rules), then run mtk guide")
    vids = json.loads(Path("web/episodes.json").read_text()) if Path("web/episodes.json").exists() else []
    text = src.read_text()
    ids = re.findall(r"\\checkpoint(?:\[[^\]]*\])?\{([^}]*)\}", text)
    owner = {c["id"]: e for e in vids for c in e.get("checkpoints", [])}
    many = len({owner[i]["stem"] for i in ids if i in owner}) > 1  # "Ep N," only when this guide spans videos
    times = {c["id"]: (f"{'Ep' if e['kind'] == 'episode' else 'Problem'} {e['n']}, " if many else "")
             + f"{int(c['t'] // 60)}:{int(c['t'] % 60):02d}" for e in vids for c in e.get("checkpoints", [])}
    name = src.stem  # guide.tex -> guide.pdf; one guide per video: guide-ep01.tex -> guide-ep01.pdf
    if src.stem == "guide":  # one guide for the whole project: every video checkpoint belongs in it
        for i in sorted(set(times) - set(ids)):
            print(f"GUIDE checkpoint {i} is in the video but not in {src.name}")
    for i in ids:
        if i not in times:
            print(f"GUIDE checkpoint {i} is in {src.name} but not in the rendered video (its time shows ?:??)")
        if not re.search(r"\\solutionfor\{" + re.escape(i) + r"\}", text):
            print(f"GUIDE checkpoint {i} has no \\solutionfor{{{i}}}")
    web = Path("web")
    web.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(src, d / "guide.tex")
        shutil.copy(pkg / "mtkguide.sty", d)
        (d / "guide-times.tex").write_text("".join(f"\\mtk@time{{{i}}}{{{t}}}\n" for i, t in times.items()))
        env = {**os.environ, "TEXINPUTS": f"{src.resolve().parent}{os.pathsep}"}  # figures next to guide.tex
        for _ in range(2):  # twice: page references
            r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "guide.tex"], cwd=d,
                               env=env, capture_output=True, text=True)
            if r.returncode:
                log = (d / "guide.log").read_text(errors="ignore").splitlines()
                for k, ln in enumerate(log):
                    if ln.startswith("!"):
                        print("LATEX", ln, next((x.strip() for x in log[k:k + 8] if x.startswith("l.")), ""))
                sys.exit(1)
        aux = (d / "guide.aux").read_text()
        W, H = (float(x) for x in re.search(r"\\mtkpage\{([\d.]+)pt\}\{([\d.]+)pt\}", aux).groups())
        pos = {(m[0], m[1]): (int(m[2]), int(m[3]) / 65536, int(m[4]) / 65536)
               for m in re.findall(r"\\mtkpos\{([^}]*)\}\{(top|mid|bot)\}\{(\d+)\}\{(\d+)\}\{(\d+)\}", aux)}  # sp
        dpi = 150
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "guide.pdf", "pg"], cwd=d, check=True)
        pages = sorted(d.glob("pg-*.png"), key=lambda q: int(q.stem.split("-")[1]))
        px = lambda pt: pt * dpi / 72.27  # TeX points -> pixels
        info = {"pdf": f"{name}.pdf", "pages": len(pages), "checkpoints": {}}
        for i in ids:
            if (i, "top") not in pos or (i, "bot") not in pos:
                continue
            # the site shows the problem; the answer box (below "mid") is for paper
            (pg, x, top), (pg2, _, bot) = pos[(i, "top")], pos.get((i, "mid"), pos[(i, "bot")])
            im = Image.open(pages[pg - 1])
            lo = H - bot if pg2 == pg else H - 0.9 * 72.27  # the minipage never splits; this is only a guard
            box = (max(0, int(px(x)) - 14), max(0, int(px(H - top)) - 10), min(im.width, int(px(W - x)) + 14),
                   min(im.height, int(px(lo)) + 6))
            im.crop(box).save(web / f"cp-{i}.png")
            info["checkpoints"][i] = {"page": pg, "img": f"cp-{i}.png"}
        shutil.copy(d / "guide.pdf", web / f"{name}.pdf")
    (web / f"{name}.json").write_text(json.dumps(info, indent=1))
    Path("out").mkdir(exist_ok=True)
    shutil.copy(web / f"{name}.pdf", Path("out") / f"{name}.pdf")
    print(f"{(Path('out') / f'{name}.pdf').resolve()}  {info['pages']} pages, {len(info['checkpoints'])} checkpoints "
          f"cropped for the site (web/cp-*.png); mtk site picks them up")


def _cues(text):
    """[[start s, end s, text], ...] from WebVTT."""
    secs = lambda x: sum(float(p) * 60 ** i for i, p in enumerate(reversed(x.strip().split(":"))))
    out = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        ls = block.split("\n")
        i = next((k for k, x in enumerate(ls) if "-->" in x), None)
        if i is not None:
            a, b = ls[i].split("-->")
            out.append([round(secs(a), 3), round(secs(b.split()[0]), 3), " ".join(ls[i + 1:]).strip()])
    return out


def _videos(web, slug=""):
    """One project's videos for a page, from its web/: captions inlined (artifacts don't serve .vtt), each video's
    guide attached (the guide*.json holding its checkpoints), and the files it needs as {published path: source}.
    With a slug (a subject on a multi-subject page) stems get "<slug>-" and files "<slug>/", so projects never collide."""
    vids = json.loads((web / "episodes.json").read_text())
    guides = [json.loads(g.read_text()) for g in sorted(web.glob("guide*.json"))]
    pre, files = f"{slug}/" if slug else "", {}
    for e in vids:
        if e.get("youtube"):  # plays from YouTube: the page neither needs nor ships the file
            e.pop("file", None)
        f = web / (e.get("captions") or "")
        e["cues"] = _cues(f.read_text()) if e.get("captions") and f.exists() else []
        e.pop("captions", None)
        ids = {c["id"] for c in e.get("checkpoints", [])}
        g = next((g for g in guides if ids & set(g["checkpoints"])), None)
        if g:
            files[pre + g["pdf"]] = web / g["pdf"]
            files.update({pre + c["img"]: web / c["img"] for c in g["checkpoints"].values()})
            e["guide"] = dict(g, pdf=pre + g["pdf"],
                              checkpoints={i: dict(c, img=pre + c["img"]) for i, c in g["checkpoints"].items()})
        for k in ("file", "poster"):
            if e.get(k):
                files[pre + e[k]] = web / e[k]
                e[k] = pre + e[k]
        if slug:
            e["subject"], e["stem"] = slug, f"{slug}-{e['stem']}"
    return vids, files


def site(a):
    """The study page. One project: run in it (after mtk episodes). Several, as tabs: --subjects hub.json with
    {"title", "kicker", "blurb", "subjects": [{"slug", "name", "dir", "blurb", "links": [{"title", "url"}]}]}."""
    import html as _html
    cfg, subjects = {}, None
    if a.subjects:
        cfg = json.loads(Path(a.subjects).expanduser().read_text())
        vids, files, subjects = [], {}, []
        for s in cfg["subjects"]:
            web = Path(s["dir"]).expanduser() / "web"
            if (web / "episodes.json").exists():
                vs, fs = _videos(web, s["slug"])
                vids += vs
                files.update(fs)
            else:
                print(f"{s['name']}: no {web}/episodes.json yet (its tab says so)")
            entry = {k: s[k] for k in ("slug", "name", "blurb", "links") if k in s}
            for d in s.get("files", []):  # extra downloads for the subject's tab: {"title", "src"} (src relative to dir)
                src = Path(s["dir"]).expanduser() / d["src"]
                if src.exists():
                    files[f"{s['slug']}/{src.name}"] = src
                    entry.setdefault("files", []).append({"title": d["title"], "path": f"{s['slug']}/{src.name}"})
                else:
                    print(f"{s['name']}: {src} not found (skipped)")
            if s.get("quiz"):  # a question bank for the subject's tab: {"title", "questions": [{id, ch, topic, q, choices, answer, why, ep}]}
                qf = Path(s["dir"]).expanduser() / s["quiz"]
                if qf.exists():
                    entry["quiz"] = json.loads(qf.read_text())
                else:
                    print(f"{s['name']}: {qf} not found (no quiz yet)")
            subjects.append(entry)
    else:
        if not Path("web/episodes.json").exists():
            sys.exit("no web/episodes.json here: run mtk episodes first (or pass --subjects)")
        vids, files = _videos(Path("web"))
    heading = a.title or cfg.get("title")
    if not heading and not subjects and Path("BRIEF.md").exists():
        first = next((ln for ln in Path("BRIEF.md").read_text().splitlines() if re.match(r"^#\s+\S", ln)), "# ")
        heading = re.sub(r"\s*\(~?[\d.]+\s*min\)\s*$", "", first[1:].strip())
    heading = heading or Path.cwd().name
    name = heading.partition(":")[0]  # the page's name (its tab and gallery title) stops before an explainer colon
    data = dict(title=name.strip(), heading=heading, kicker=a.kicker or cfg.get("kicker", ""),
                blurb=a.blurb or cfg.get("blurb", ""), videos=vids)
    if subjects:
        data["subjects"] = subjects
    from mtk_serve import MODEL, credentials
    key, _, where = credentials([Path.cwd()] + [Path(s["dir"]).expanduser() for s in cfg.get("subjects", [])])
    if key:  # the chat box exists only where a key does; the key itself never goes into the page
        data["chat"] = {"model": MODEL}
    print(f"chat: {'on (' + MODEL + '; key found in ' + where + ')' if key else 'off (no Anthropic API key found)'}")
    tpl = (Path(importlib.util.find_spec("mtk").origin).parent / "site" / "player.html").read_text()
    page = tpl.replace("{{TITLE}}", _html.escape(name.strip())).replace(
        "/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    out = Path(a.out).expanduser() if a.out else (Path(a.subjects).expanduser().parent / "site" if a.subjects
                                                   else Path("web"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page)
    for f, src in files.items():  # a separate publish folder (e.g. the scratchpad) gets its own copies
        dst = out / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dst.resolve() and (not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime):
            shutil.copy2(src, dst)
    guided = any(e.get("guide") for e in vids)
    print(f"{(out / 'index.html').resolve()}  ({len(vids)} videos, {sum((out / f).stat().st_size for f in files) / 1e6:.1f} MB)")
    tubed = sum(1 for e in vids if e.get("youtube"))
    if tubed:  # no publish plan: claude.ai artifacts refuse embeds, so these videos would only show a link there
        print(f"host: {tubed} of {len(vids)} videos embed from YouTube, which claude.ai artifacts refuse. Run mtk serve, or "
              f"put {out.resolve()} on any static host (over http(s): YouTube rejects file:// pages)")
        return
    batches, cur, size = [], {}, 0
    for f in files:  # one publish carries at most 64 MB: batch the files, all published to the same artifact
        b = (out / f).stat().st_size
        if cur and size + b > 60e6:
            batches.append(cur)
            cur, size = {}, 0
        cur[f] = str((out / f).resolve())
        size += b
    batches.append(cur)
    caps = {**({"downloads": True} if guided else {}), **({"sample": {}} if data.get("chat") else {})}
    print("publish: Artifact file_path=index.html (in that folder) with files=<batch 1>; later batches go to the "
          "same url with the same file_path" + (f"; pass capabilities={json.dumps(caps)}" if caps else "")
          + (" (published, the chat box asks Claude through each viewer's own claude.ai account)"
             if data.get("chat") else ""))
    for i, bt in enumerate(batches, 1):
        print(f"batch {i}: " + json.dumps(bt))


SERIES = """# <Title>  (~N min)

**Viewer**: <who's watching and why>.
**Knows**: <what the narration may use without explaining, listed literally; everything else gets explained>.
**Hook**: <the concrete question or picture of the first 20 s>. **Insight**: <the one sentence the viewer keeps>.
**Payoff**: <how the ending answers the hook>.
**Crux**: <the one or two steps where understanding is won or lost, and the misconception each must defeat>.
**Ladder**: <the ideas in teaching order, each resting only on Knows and earlier rungs>:
1. (support, 0:45) <...>
2. (core, 2:30) <...>
3. (aside, cut) <...>

Every file starts:
```python
from mtk import *
colors(**{"x": SKY})
```
<what each hue means; the shared kit (<topic>.py) if scenes share objects>

## Facts (assert the ones your scene shows)
- <every number, formula, notation choice and source detail the scenes need, and how it's checked>

# Episode 1: <Title> | <subtitle>      <- delete for a single video; add one per episode for a series

## S01_<Name> [<narration words>] <chapter label>
Picture: <layout and what's on screen overall; recipes to borrow (mtk recipe)>
1. "<exact narration: one to three sentences, written for the ear>"
   → <what the screen does during this beat>
2. "<next beat>"
   → <...>
3. "<a key moment: pay close attention here, because ...>" (style: slower and deliberate, stressing the key words)
   → self.spotlight(<the one thing>); hold 2 s
"""

WALK = """# <Course> · <exam> walkthroughs

Viewer: just attempted the problem, maybe got it wrong; wants to see fast how to think about it on the exam.
Tone: a calm tutor at their elbow. American spelling. Every file starts:
```python
from mtk import *
colors(**{"q": SKY})
```
<what each hue means; the shared kit (<topic>.py) for figures that recur>

Shape of every problem (~2 to 2.5 min, 240 to 300 narration words, the problem agent writes the narration):
- Read [70-90]: title_card ("Problem 3: <title>", sub), the problem as a picture (givens labeled, unknown "?"),
  what's asked and which idea it tests, then self.try_it().
- Solve [120-160]: every step on screen, units carried, answer_box; then choices([...]) and mark() the right one.
- Trap [40-70]: mark(row, False) on the most tempting wrong choice, the one-line mistake behind it, key_box takeaway.

# Problem 1: <Title> | <Ch. N · topic · review: Episode K>

## Facts
- Statement: <...>
- Choices: A) <...>  B) <...>  C) <...>  D) <...>;  answer: <letter>
- Solution: <each step with every number, as it should appear>
- Trap: <the tempting wrong choice and the mistake that produces it>

## S011_Read [80]
## S012_Solve [140]
## S013_Trap [55]
"""


def new(a):
    d = Path(a.dir).expanduser() if a.dir else Path.home() / "Movies/Explainers" / a.slug
    d.mkdir(parents=True, exist_ok=True)
    b = d / "BRIEF.md"
    if b.exists():
        sys.exit(f"{b} already exists; not overwriting it")
    b.write_text(WALK if a.walk else SERIES)
    print(b)


def make(a):
    from mtk_make import make as go
    d = Path(a.dir).expanduser() if a.dir else Path.home() / "Movies/Explainers" / re.sub(r"\W+", "-", a.topic.lower()).strip("-")[:40]
    d.mkdir(parents=True, exist_ok=True)
    os.chdir(d)
    go(a)


def serve(a):
    from mtk_serve import serve as run
    run(Path(a.dir) if a.dir else (Path("web") if Path("web/index.html").exists() else Path(".")), a.port)


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(p)], capture_output=True, text=True).stdout)


def frames(a):
    from PIL import Image, ImageDraw, ImageFont
    w = 960
    font = ImageFont.load_default(size=20)
    tiles = []
    with tempfile.TemporaryDirectory() as tmp:
        for t in a.sec:
            p = Path(tmp) / f"{t}.png"
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", str(t), "-i", a.video,
                            "-frames:v", "1", "-vf", f"scale={w}:-2", str(p)], check=True)
            tiles.append((t, Image.open(p).convert("RGB")))
    h = tiles[0][1].height
    cols = 1 if len(tiles) == 1 else 2
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols - 1) * 6, rows * (h + 30 + 6)), "#05060a")
    d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(tiles):
        x, y = (i % cols) * (w + 6), (i // cols) * (h + 36)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + h + 5), f"{int(float(t) // 60)}:{float(t) % 60:04.1f}", fill="#c8ccd6", font=font)
    out = Path("media/frames") / f"{Path(a.video).stem}.{'_'.join(a.sec)}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(out)


def recipe(a):
    path = Path(importlib.util.find_spec("mtk").origin).parent / "recipes.py"  # find_spec doesn't import manim
    src = path.read_text()
    blocks = re.split(r"(?m)^(?=class )", src)[1:]
    if not a.name:
        print(path)
        for b in blocks:
            name = ANY.match(b).group(1)
            doc = re.search(r'"""(.*?)(?:\n|""")', b)
            print(f"  {name:22s} {doc.group(1).strip() if doc else ''}")
        return
    hit = [b for b in blocks if ANY.match(b).group(1).startswith(a.name)]
    print("\n".join(hit).rstrip() if hit else f"no recipe {a.name}; run `mtk recipe` for the list")


def main():
    p = argparse.ArgumentParser(prog="mtk", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", check), ("render", render)):
        c = sub.add_parser(name)
        c.add_argument("files", nargs="*")
        c.add_argument("-s", "--scene", action="append", help="scene name prefix(es), comma-separated or repeated")
        c.add_argument("-j", "--jobs", type=int)
        c.add_argument("--agent", action="store_true", help="the agent renderer: only what changed since last time "
                       "is reported (check) or drawn (render)")
        if name == "check":
            c.add_argument("--at", help="full-size stills at these scene times, comma-separated, e.g. 12.4,15 (no video)")
        if name == "render":
            c.add_argument("-q", default="h", choices=QUAL)
            c.add_argument("-o", help="output name (default: the file, or this folder for several)")
        c.set_defaults(fn=fn)
    c = sub.add_parser("script")
    c.add_argument("brief")
    c.set_defaults(fn=as_heard)
    c = sub.add_parser("voice")
    c.add_argument("brief")
    c.add_argument("--voice", help="TTS voice, if the video doesn't use the default")
    c.set_defaults(fn=voice)
    c = sub.add_parser("brief")
    c.add_argument("brief")
    c.add_argument("scene", help="scene name or prefix, e.g. S03")
    c.set_defaults(fn=brief)
    c = sub.add_parser("episodes")
    c.add_argument("brief")
    c.add_argument("which", nargs="*", help="stems to build (ep03 p02 ...); default all")
    c.add_argument("-q", default="h", choices=QUAL, help="the render quality to join (default h = 1080p30)")
    c.add_argument("--max-mb", type=float, default=14.5, help="per-file cap (artifact files max out at 15 MB)")
    c.add_argument("--crf", type=int, default=22, help="first x264 quality to try (higher = smaller; skips passes known to be too big)")
    c.add_argument("--mb-per-min", type=float, help="also cap at this many MB per minute (a site-wide budget)")
    c.set_defaults(fn=episodes)
    c = sub.add_parser("youtube")
    c.add_argument("pairs", nargs="*", metavar="STEM=URL", help="e.g. ep01=https://youtu.be/ID; ep01= goes back to the local file")
    c.set_defaults(fn=youtube)
    c = sub.add_parser("site")
    c.add_argument("--title", help="the page heading (default: the brief's title); its tab name stops at a colon")
    c.add_argument("--kicker", help="small line above the title, e.g. the course")
    c.add_argument("--blurb", help="one or two sentences under the title")
    c.add_argument("--out", help="write index.html and copies of the videos here (default: web/, or site/ next to --subjects)")
    c.add_argument("--subjects", help="hub.json: several projects on one page, one tab each (see site())")
    c.set_defaults(fn=site)
    c = sub.add_parser("guide")
    c.add_argument("tex", nargs="?", default="guide.tex")
    c.set_defaults(fn=guide)
    c = sub.add_parser("serve")
    c.add_argument("--dir", help="the site folder (default: web/ if it has index.html, else here)")
    c.add_argument("--port", type=int, default=8000)
    c.set_defaults(fn=serve)
    c = sub.add_parser("new")
    c.add_argument("slug")
    c.add_argument("--walk", action="store_true", help="exam walkthrough brief instead of a series")
    c.add_argument("--dir", help="folder (default ~/Movies/Explainers/SLUG)")
    c.set_defaults(fn=new)
    c = sub.add_parser("make")
    c.add_argument("topic", help="the topic, or a path to notes or a paper, as you would ask for the video")
    c.add_argument("--minutes", type=int, default=10)
    c.add_argument("--dir", help="project folder (default ~/Movies/Explainers/<topic slug>)")
    c.add_argument("-q", default="h", choices=QUAL)
    c.set_defaults(fn=make)
    c = sub.add_parser("frames")
    c.add_argument("video")
    c.add_argument("sec", nargs="+")
    c.set_defaults(fn=frames)
    c = sub.add_parser("recipe")
    c.add_argument("name", nargs="?")
    c.set_defaults(fn=recipe)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
