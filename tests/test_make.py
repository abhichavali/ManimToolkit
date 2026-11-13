"""python tests/test_make.py: the mtk make pipeline, offline, with a fake `claude` standing in for every agent. Stages run in
order on real mtk voice/check/render; a crashing scene goes back to its writer; review notes reach only that scene's
session; a re-run does nothing it already did."""
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

FAKE = r'''#!/usr/bin/env python3
import json, os, re, sys, uuid
from pathlib import Path
prompt, argv = sys.stdin.read(), sys.argv[1:]
sid = argv[argv.index("--resume") + 1] if "--resume" in argv else uuid.uuid4().hex
kind = "?"
SCENE = """from mtk import *
class S0{n}_{name}(VScene):
    def construct(self):
        self.beat("{line}", FadeIn(T("x", 40)))
        self.wipe()
"""
BRIEF = """# T  (~1 min)

**Viewer**: v.
**Knows**: k.
**Crux**: c.
colors(x=SKY)

## S01_A [3]
1. "One two three."
   → self.spotlight(x)

## S02_B [3]
1. "Four five six."
   → y
"""
if prompt.startswith("The connection dropped"):
    kind = "continued"
    assert "--resume" in argv
    Path("REVIEW.md").write_text("S02.1: too dark -> brighten\n")
elif prompt.startswith("Request:"):
    kind = "author"
    assert "Target length: 1 minutes" in prompt and "## 3. Write BRIEF.md" in prompt
    Path("BRIEF.md").write_text(BRIEF)
elif "You're about to watch" in prompt:
    kind = "cold"
    assert "S01.1" in prompt and "mtk script" not in prompt and "--system-prompt-file" not in argv
    result = "S01.1 [jump] fine"
elif prompt.startswith("Cold read of"):
    kind = "fix-brief"
    assert "--resume" in argv and "S01.1 [jump]" in prompt and "S01_A" in prompt
elif prompt.startswith("Write scene"):
    m = re.search(r"Write scene S0(\d) .* as (\S+)\.py", prompt)
    n = m.group(1)
    kind = "scene" + n
    assert "YOUR SCENE: class" in prompt and "--system-prompt-file" in argv
    assert ("--effort" in argv and argv[argv.index("--effort") + 1] == ("xhigh" if n == "1" else "high"))
    good = SCENE.format(n=n, name="AB"[int(n) - 1], line=["One two three.", "Four five six."][int(n) - 1])
    Path(m.group(2) + ".py").write_text(good.replace("self.wipe()", "boom()") if n == "2" else good)  # S02 crashes first
elif prompt.startswith("The check of your scene failed"):
    kind = "crash-fix"
    assert "NameError" in prompt, prompt
    f = Path("s02_b.py")
    f.write_text(f.read_text().replace("boom()", "self.wipe()"))
elif "reviewing an explainer" in prompt:
    n = len(list(Path("media/make").glob("review*.md"))) + 1
    kind = f"review{n}"
    assert ".mp4" in prompt and ("Read only the storyboards of S02_B" in prompt if n == 2 else "every storyboard" in prompt)
    Path("REVIEW.md").write_text("S02.1: too dark -> brighten\n" if n == 1 else "")
    if n == 1 and "--resume" not in argv:  # the network dies on the first review
        Path("REVIEW.md").unlink()
        open(os.environ["FAKE_LOG"], "a").write(f"dropped {sid}\n")
        print(json.dumps(dict(result="API Error", session_id=sid, total_cost_usd=1.5, is_error=True)))
        sys.exit(1)
elif prompt.startswith("Review notes"):
    kind = "note-fix"
    assert "S02.1: too dark" in prompt and "S01" not in prompt
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(f"{kind} {sid}\n")
runs = sum(sid in x for x in open(os.environ["FAKE_LOG"]))  # like the real one: a resumed session's total is cumulative
print(json.dumps(dict(result=globals().get("result", "ok"), session_id=sid, total_cost_usd=1.5 * runs, num_turns=3, is_error=False, usage={})))
'''

d = Path(tempfile.mkdtemp())
bin_ = d / "bin"
bin_.mkdir()
(bin_ / "claude").write_text(FAKE)
(bin_ / "claude").chmod(stat.S_IRWXU)
log = d / "log"
env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "FAKE_LOG": str(log), "MTK_TTS": "say",
       "PYTHONWARNINGS": "ignore"}
cmd = [str(Path(sys.executable).parent / "mtk"), "make", "the topic", "--minutes", "1", "--dir", str(d / "p"), "-q", "l"]


def go():
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


out = go()
seen = [x.split() for x in log.read_text().splitlines()]
kinds = [k for k, _ in seen]
assert kinds[:3] == ["author", "cold", "fix-brief"] or kinds[:3] == ["author", "fix-brief", "cold"], kinds
assert sorted(kinds[3:5]) == ["scene1", "scene2"], kinds
assert kinds[5:] == ["crash-fix", "dropped", "continued", "note-fix", "review2"], kinds
sid = dict(seen)
assert sid["scene2"] == sid["crash-fix"] == sid["note-fix"] != sid["scene1"], "fixes must return to the scene's writer"
assert sid["dropped"] == sid["continued"], "a retry must continue the failed session, not pay for its work again"
assert sid["continued"] != sid["review2"], "each review is a fresh agent"
assert "TOTAL" in out and "$  15.00" in out and ".mp4" in out, out
assert (d / "p/out/p.mp4").stat().st_size > 0
print("order, sessions, report ok")

n = len(seen)
go()
assert len(log.read_text().splitlines()) == n, "a finished run re-ran an agent"
print("re-run is a no-op")

rows = [json.loads(x) for x in (d / "p/media/make/usage.jsonl").read_text().splitlines()]
assert len(rows) == n and all(r["t1"] >= r["t0"] for r in rows)
print("usage ledger ok")
