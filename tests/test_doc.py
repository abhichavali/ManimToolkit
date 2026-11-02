"""python tests/test_doc.py: scene docs, offline. Cues land on their words, stage() can't overlap, narration comes from the
brief, and the new checks catch the defects reviewers found by eye."""
import json
import os
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

d = Path(tempfile.mkdtemp())
os.chdir(d)
env = {**os.environ, "MTK_TTS": "say", "PYTHONWARNINGS": "ignore"}
from mtk.doc import find_phrase, solve, tex_parts, word_times

# --- a 403 with credit left is retried; only a spent key falls back to the draft voice
import io, urllib.error, urllib.request
import mtk.core as core
core.config.input_file = str(d / "x.py")
os.environ["OPENROUTER_API_KEY"] = "test"
real_sleep, core.time.sleep = core.time.sleep, lambda s: None


def fake(left, fails):
    calls = []

    def urlopen(req, timeout=None):
        if req.full_url.endswith("/key"):
            return io.BytesIO(json.dumps({"data": {"limit_remaining": left}}).encode())
        calls.append(1)
        if len(calls) <= fails:
            raise urllib.error.HTTPError(req.full_url, 403, "no", {}, None)
        return io.BytesIO(b"\0\0" * 2400)
    return urlopen, calls


saved, os_tts = urllib.request.urlopen, os.environ.pop("MTK_TTS", None)
urllib.request.urlopen, calls = fake(14.0, 3)
path, _ = core.tts("credit left")
assert len(calls) == 4 and not path.name.endswith(".say.wav"), (calls, path)
urllib.request.urlopen, calls = fake(0.0, 9)
path, _ = core.tts("credit gone")
assert len(calls) == 1 and path.name.endswith(".say.wav"), (calls, path)
urllib.request.urlopen, core.time.sleep, core._QUOTA["out"] = saved, real_sleep, False
print("voice: a 403 with credit left retries, a spent key falls back")

# --- word timing, against joins whose times are known exactly
parts = ["The first thing to notice is how many steps this takes,", "and that number grows with the square of the size.",
         "So we need another idea,", "one that reuses work we already did."]
pcm, rate, want = [], 24000, []
for i, p in enumerate(parts):
    f = d / f"p{i}.wav"
    subprocess.run(["say", "-v", "Samantha", "-r", "185", "--file-format=WAVE", "--data-format=LEI16@24000", "-o", str(f), p], check=True)
    with wave.open(str(f)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16)
    # each clause's first voiced sample, not its file start: say pads the head with silence
    head = np.argmax(np.abs(x) > 0.05 * np.abs(x).max())
    want.append((sum(map(len, pcm)) + head) / rate)
    pcm.append(x)
    pcm.append(np.zeros(rate // 4, np.int16))
with wave.open(str(d / "all.wav"), "wb") as w:
    w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate), w.writeframes(np.concatenate(pcm).tobytes())
text = " ".join(parts)
times = word_times(d / "all.wav", text)
starts = [len(" ".join(parts[:i]).split()) for i in range(len(parts))]
err = [abs(times[k] - t) for k, t in zip(starts, want)]
assert max(err) < 0.2, f"clause starts off by {err}"
assert all(a <= b for a, b in zip(times, times[1:])), "word times must increase"
print(f"word timing: clause starts within {max(err):.3f}s")

assert find_phrase("Square of", text) == text.lower().split().index("square")
assert tex_parts(r"X_k = E_k + z^k O_k", ["E_k", "O_k", "X_k", "E"]) == ["X_k", "=", "E_k", "+ z^k", "O_k"]
assert tex_parts(r"\frac{E}{2} + E", ["E"]) == [r"\frac{E}{2} +", "E"], "a piece inside braces can't be split out"
assert tex_parts(r"\left(E\right)", ["E"]) == [r"\left(E\right)"]

# --- the layout can't overlap, whatever it's handed
rng = np.random.default_rng(1)
names = ["top", "bottom", "left", "center", "right"]
for _ in range(500):
    picked = [s for s in names if rng.random() < .6] or ["center"]
    slots = {s: [tuple(rng.uniform(.3, 16, 2)) for _ in range(rng.integers(1, 4))] for s in picked}
    k, box = solve(slots, 14.22, 8)
    rects = []
    for s, v in slots.items():
        x, y, w, h = box[s]
        tw, th = max(a for a, _ in v) * k[s], sum(b for _, b in v) * k[s] + .35 * (len(v) - 1)
        assert tw <= w + 1e-6 and th <= h + .36 * (len(v) - 1) + 1e-6, (s, tw, w, th, h)
        assert abs(x) + w / 2 <= 7.11 and abs(y) + h / 2 <= 4 + 1e-6, (s, x, y, w, h)
        rects.append((x - w / 2, x + w / 2, y - h / 2, y + h / 2))
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert min(a[1], b[1]) - max(a[0], b[0]) <= 1e-6 or min(a[3], b[3]) - max(a[2], b[2]) <= 1e-6, (slots, a, b)
print("layout: no overlaps in 500 random pictures")

# --- a whole scene through mtk check
(d / "BRIEF.md").write_text('''# T (~1 min)

## S01_A [32]
1. "Here is the sum we want to split into two pieces."
   → eq
2. "Now watch the label stay with its dot while the dot moves across."
   → dot
3. "And this last line never plays, which the check reports."
   → x
''')
SCENE = '''from mtk import *
colors(E=SKY)

class S01_A(Doc):
    def construct(self):
        eq, note = EQ(r"X = E + O"), T("the sum", 40)
        huge = VGroup(*[T("very wide text that cannot fit at its size " * 4, 30) for _ in range(3)]).arrange(DOWN)
        self.line(1, {"sum": self.stage(top=eq, center=note), "split": Indicate(part(eq, "E"))})
        self.t_sum = self.time
        dot, lab = Dot(LEFT * 3), T("dot", 30)
        self.follow(lab, dot)
        self.line(2, {"label": self.stage(top=eq, center=dot), "moves": dot.animate.shift(RIGHT * 6)})
        assert note not in self.mobjects, "stage() must clear what it doesn't list"
        assert np.isclose(lab.get_center()[0], dot.get_center()[0], atol=.01), "the label left its dot"
        assert eq.get_center()[1] > 2, "eq stays in the top slot"
        d2, lab2 = Dot(), T("cue", 30)
        self.follow(lab2, d2)
        self.play(FadeIn(d2))
        assert lab2 in self.mobjects, "a label enters with its anchor on a cue too"
        self.play(FadeOut(d2))
        assert lab2 not in self.mobjects, "and leaves with it"
        self.play(self.stage(left=huge, right=T("beside it", 30)))
        boxes = [m for m in self.mobjects]
        l, r = sorted(self.mobjects, key=lambda m: m.get_center()[0])[:2]
        assert l.get_right()[0] <= r.get_left()[0], "columns overlap"
        flash, serif, white = M(r"20 \\times 2^{20} \\approx 2.1 \\times 10^{7} + 1234567890"), M(r"\\text{same speed}"), M("E")
        self.play(self.stage(top=flash, center=serif, bottom=white))
        self.wipe()
'''
(d / "s01_a.py").write_text(SCENE)
r = subprocess.run([sys.executable, "-m", "mtk_cli", "check"], env=env, capture_output=True, text=True)
out = r.stdout + r.stderr
assert "S01_A" in out and "FAILED" not in out, out
assert "beats [3] of the brief never play" in out, out
assert "stage left: no room" in out, out
assert "serif math font" in out, out
assert "'E' is white" in out, out
assert re.search(r"readable for \d\.\ds", out), out
print("whole scene ok; beat, fit, font, color and reading checks fire")

(d / "s01_a.py").write_text(SCENE.replace('"split"', '"nosuchword"'))
r = subprocess.run([sys.executable, "-m", "mtk_cli", "check"], env=env, capture_output=True, text=True)
assert "isn't in the rest of the line" in r.stdout + r.stderr, r.stdout + r.stderr
print("a cue on a word that isn't there names the line")

(d / "s01_a.py").write_text(SCENE)
SOME = {"MTK_AGENT": "1"}
r = subprocess.run([sys.executable, "-m", "mtk_cli", "render", "--agent", "-q", "l", "-o", "x"], env=env, capture_output=True, text=True)
assert r.returncode == 0 and "reused" in r.stdout, r.stdout + r.stderr
assert (d / "out/x.mp4").stat().st_size > 0
print("renders through the agent renderer")
