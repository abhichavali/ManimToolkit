"""python tests/test_agent.py: the agent renderer's promises, offline. Same frames as a cold classic render; an unchanged
re-render draws nothing; an edit draws only what changed and never shows a stale segment; check --agent reports only
changed beats; check --at works with no video."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCENE = '''from mtk import *

class A01_Mix(VScene):
    def construct(self):
        t = T("alpha", 40)
        tr = ValueTracker(0)
        ring = always_redraw(lambda: Circle(radius=1 + tr.get_value(), color=SKY))
        self.beat("One two three.", Write(t), FadeIn(ring))
        dot = Dot(LEFT * 3, color=EMBER)
        dot.add_updater(lambda m, dt: m.shift(RIGHT * dt))  # stateful: wrong if any frame's dt is skipped
        self.add(dot)
        self.play(tr.animate.set_value(.5), self.camera.frame.animate.scale(.8), run_time=.5)
        self.wait(.4)
        dot.clear_updaters()
        self.wait(.5)  # a frozen frame
        self.beat("Four five six.", t.animate.shift(UP))
        self.wipe()
'''
d = Path(tempfile.mkdtemp())
os.chdir(d)
env = {**os.environ, "MTK_TTS": "say", "PYTHONWARNINGS": "ignore"}
(d / "a.py").write_text(SCENE)
VID = Path("media/videos/a/480p15/A01_Mix.mp4")


def run(*cmd):
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def frames(p):
    return [x.split()[-1] for x in subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(p), "-map", "0:v",
            "-f", "framemd5", "-"], capture_output=True, text=True).stdout.splitlines() if not x.startswith("#")]


def classic(name):
    manim = str(Path(sys.executable).parent / "manim")
    run(manim, "-ql", "--disable_caching", "--media_dir", name, "a.py", "A01_Mix")
    return frames(Path(name) / "videos/a/480p15/A01_Mix.mp4")


def drew(out):
    m = re.search(r"agent: drew (\d+)/(\d+) frames; reused (\d+)/(\d+) plays", out)
    assert m, out
    return tuple(map(int, m.groups()))


render = ("mtk", "render", "a.py", "-s", "A01", "--agent", "-q", "l", "-o", "x")
got = drew(run(*render))
assert got[0] == got[1] > 0 and got[2] == 0, got
want = classic("m1")
assert frames(VID) == want, "cold agent render differs from cold classic"
got = drew(run(*render))
assert got == (0, 0, 0, 0), f"nothing changed, yet the scene ran: {got}"
VID.with_suffix(".key").unlink()
got = drew(run(*render))
assert got[0] == 0 and got[2] == got[3] > 0, f"nothing changed, yet it drew: {got}"
assert frames(VID) == want, "fully reused render differs"
(d / "data.txt").write_text("x")
assert drew(run(*render))[3] > 0, "a new data file beside the scene should make it run again"
print("identical, reused ok")

(d / "a.py").write_text(SCENE.replace('.shift(UP)', '.shift(DOWN)'))
got = drew(run(*render))
assert 0 < got[0] < got[1] and 0 < got[2] < got[3], f"the edit should redraw some plays, not all: {got}"
assert frames(VID) == classic("m2"), "stale segment: edited render differs from cold classic"
print("edit redraws only what changed, no stale segments")

(d / "a.py").write_text(SCENE)
check = ("mtk", "check", "a.py", "-s", "A01", "--agent")
out = run(*check)
assert "A01_Mix" in out and "media/board/a.A01_Mix.diff.png" in out, out
out = run(*check)
assert "0 lint" in out.splitlines()[-1] or "lint" in out, out
assert re.search(r"\b0/(\d+) beats changed", out) and ".diff.png" not in out and "~0 image tokens" in out, out
(d / "a.py").write_text(SCENE.replace('T("alpha", 40)', 'T("beta", 40)'))
out = run(*check)
assert "+'beta'" in out and "-'alpha'" in out and ".diff.png" in out, out
n, of = map(int, re.search(r"(\d+)/(\d+) beats changed", out).groups())
assert 0 < n <= of, out
(d / "a.py").write_text(SCENE.replace('.shift(UP)', '.shift(DOWN)').replace('T("alpha", 40)', 'T("beta", 40)'))
out = run(*check)
assert re.search(r"~'beta' \([-\d.]+,[-\d.]+\)->\([-\d.]+,[-\d.]+\)", out), out
print("check --agent ok")

out = run("mtk", "check", "a.py", "-s", "A01", "--at", "0.5,2.0")
assert "media/board/a.A01_Mix.at.png" in out, out
from PIL import Image
assert Image.open("media/board/a.A01_Mix.at.png").width == 2 * 960 + 4
print("check --at ok")

RACE = """from mtk import *
from manim.mobject.svg.svg_mobject import SVG_HASH_TO_MOB_MAP
for _ in range(60):
    SVG_HASH_TO_MOB_MAP.clear()
    T("shared by every scene", 40), M("x^2")
"""
procs = [subprocess.Popen([sys.executable, "-c", RACE], env=env, stderr=subprocess.PIPE, text=True) for _ in range(8)]
errs = [e for p in procs for e in [p.communicate()[1]] if p.returncode]
assert not errs, f"scenes sharing a text at once broke the cache: {errs[0][-400:]}"
assert all(p.stat().st_size for p in Path("media/texts").glob("*.svg"))
print("shared text cache survives parallel scenes")
