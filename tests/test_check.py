"""python tests/test_check.py: runs `mtk check` on lint_cases.py (offline voice) and asserts every rule fires."""
import os
import subprocess
from pathlib import Path

here = Path(__file__).parent
out = subprocess.run(["mtk", "check", "lint_cases.py"], cwd=here, capture_output=True, text=True,
                     env={**os.environ, "MTK_TTS": "say"}).stdout
print(out)
for want in ["0 warnings 1 checkpoints", "DRIFT q: SKY in S06; EMBER in S07", "past its narration", "S08_Overrun", "lint_cases S05_Zoom", "'buried label' is hidden under a Square", "'x^2' overlaps 'y^2'", "'off the edge' is cut off",
             "'tiny' renders at font size 12", "picture frozen for", "narration contains =", "budget 20",
             "S04_Clean", "media/board/lint_cases.S04_Clean.png"]:
    assert want in out, want
spot = next(ln for ln in out.splitlines() if ln.startswith("lint_cases S10_Spotlight"))
assert "0 warnings" in spot and "3 beats" in spot, spot
clean = next(ln for ln in out.splitlines() if ln.startswith("lint_cases S04_Clean"))
assert "0 warnings" in clean and "2 beats" not in clean, clean
assert (here / "media/board/lint_cases.S04_Clean.png").exists()
print("check ok")

# script-first brief parsing (mtk voice / mtk brief)
import tempfile
import sys
sys.path.insert(0, str(here.parent))
from mtk_cli import script, groups, vtt, beat_lints
b = Path(tempfile.mkdtemp()) / "BRIEF.md"
b.write_text('# T\n\nshared\n\n## Facts\n- f\n\n## S01_Hook [12]\nPicture: x\n1. "One two."\n   → a\n'
             '2. "Three." (style: slow)\n## S02_Next\n1. "Four."\n')
sc = script(b)
assert sc == {"S01_Hook": (12, [("One two.", None), ("Three.", "slow")]), "S02_Next": (None, [("Four.", None)])}, sc
out = subprocess.run(["mtk", "brief", str(b), "S02"], capture_output=True, text=True).stdout
assert "shared" in out and "- f" in out and "Before you: S01_Hook [12]" in out and "s02_next.py" in out, out
assert '"One two."' not in out.split("YOUR SCENE")[1], out
heard = b.parent / "heard.md"
heard.write_text('# T\n\n**Viewer**: v\n**Knows**: k\nand j\n**Insight**: secret\n\n## Facts\n- f\n\n## S01_Hook [12] Hook\n'
             'Picture: x\n1. "One two."\n   → a\n2. "Three." (style: slow)\n')
out = subprocess.run(["mtk", "script", str(heard)], capture_output=True, text=True).stdout
assert out == '**Viewer**: v\n**Knows**: k\nand j\n\n## S01_Hook Hook\nS01.1 "One two."\n     → a\nS01.2 "Three."\n', out
assert beat_lints("So it turns out the sum is two.") == [
    '"it turns out" asks the viewer to take a step on trust: show the reason, or say plainly it\'s skipped'], beat_lints
assert beat_lints("word " * 51)[0].startswith("51 words") and not beat_lints("Square both sides; both are positive.")
print("brief ok")

# episodes: groups, chapter labels, captions
b2 = b.parent / "B2.md"
b2.write_text('# T  (~3 min)\n\ncolors(\n\n# Episode 1: One | first\n## S01_A [10] Alpha\n1. "x."\n   → y\n'
              '## S02_B\n\n# Problem 2: Two\n## Facts\n- f\n## S021_Read [80]\n')
gs = groups(b2)
assert [g["stem"] for g in gs] == ["ep01", "p02"] and gs[0]["sub"] == "first", gs
assert gs[0]["labels"] == {"S01_A": "Alpha", "S02_B": "B"} and gs[1]["scenes"] == ["S021_Read"], gs
one = groups(b)  # no group headings: one video named after the brief's title
assert len(one) == 1 and one[0]["stem"] == "ep01" and one[0]["title"] == "T" and len(one[0]["scenes"]) == 2, one
out = subprocess.run(["mtk", "brief", str(b2), "p02"], capture_output=True, text=True).stdout
assert "YOURS: S021_Read" in out and "- f" in out and "S01_A" not in out, out
import os
os.chdir(b.parent)
(b.parent / "media/subs").mkdir(parents=True, exist_ok=True)
(b.parent / "media/subs/v1.S01_A.json").write_text('[{"t": 1.0, "dur": 4.0, "text": "One two. Three four five six."}]')
cues = vtt([(10.0, "v1", "S01_A")], b.parent / "x.vtt").read_text()
assert "00:00:11.000 --> 00:00:12.143\nOne two." in cues and "--> 00:00:15.000\nThree four five six." in cues, cues
print("episodes ok")

# site: page data (cues embedded, title split at the colon), copies, publish plan, player script parses
import json, re, shutil
w = b.parent / "proj"
(w / "web").mkdir(parents=True, exist_ok=True)
(w / "web/ep01.mp4").write_bytes(b"\0" * 1000)
(w / "web/ep01.jpg").write_bytes(b"\0" * 10)
(w / "web/ep01.vtt").write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.500\nOne two.\n")
(w / "web/episodes.json").write_text(json.dumps([dict(stem="ep01", kind="episode", n=1, title="A", sub="", file="ep01.mp4",
    poster="ep01.jpg", captions="ep01.vtt", duration=2.5, mb=0.0, chapters=[{"t": 0, "label": "Hook", "scene": "S01"}])]))
pub = b.parent / "pub"
home = b.parent / "home"  # no ~/.anthropic_api_key here: chat stays off
home.mkdir(exist_ok=True)
nokey = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")} | {"HOME": str(home)}
out = subprocess.run(["mtk", "site", "--title", "Series Name: a subtitle", "--out", str(pub)], cwd=w,
                     capture_output=True, text=True, env=nokey).stdout
page = (pub / "index.html").read_text()
data = json.loads(re.search(r'id="data">(.*?)</script>', page, re.S).group(1).replace("<\\/", "</"))
assert "<title>Series Name</title>" in page and data["heading"] == "Series Name: a subtitle", data["heading"]
assert data["videos"][0]["cues"] == [[1.0, 2.5, "One two."]] and "captions" not in data["videos"][0], data["videos"][0]
assert (pub / "ep01.mp4").exists() and (pub / "ep01.jpg").exists() and not (pub / "ep01.vtt").exists()
assert 'batch 1: {"ep01.mp4"' in out, out
if shutil.which("node"):
    js = page.split('<script>')[-1].split('</script>')[0]
    subprocess.run(["node", "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=js, text=True, check=True)
assert "chat" not in data and "chat: off" in out and "sample" not in out, out
out = subprocess.run(["mtk", "site", "--out", str(pub)], cwd=w, capture_output=True, text=True,
                     env={**nokey, "ANTHROPIC_API_KEY": "sk-test-env"}).stdout
page = (pub / "index.html").read_text()
assert '"chat": {"model": "claude-sonnet-5-5"}' in page and "sk-test" not in page, page[-300:]
assert 'capabilities={"sample": {}}' in out and "key found in $ANTHROPIC_API_KEY" in out, out
print("site ok")

# chat: mtk serve answers through the API with the key from a folder file (mock API), never serves dotfiles,
# and is off without a key
import socket, urllib.request, urllib.error, time, mock_anthropic
api = mock_anthropic.start()


def serve(env):
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    proc = subprocess.Popen(["mtk", "serve", "--dir", str(pub), "--port", str(port)], env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    for _ in range(100):
        try:
            return proc, f"http://127.0.0.1:{port}", json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/chat"))
        except OSError:
            time.sleep(0.1)
    proc.kill()
    raise AssertionError(proc.stdout.read())


def post(base, body):
    req = urllib.request.Request(base + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


(pub / ".anthropic_api_key").write_text("sk-test-file\n")
proc, base, info = serve({**nokey, "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{api.server_port}",
                          "ANTHROPIC_WORKSPACE_ID": "wrkspc_test"})
try:
    assert info == {"enabled": True, "model": "claude-sonnet-5-5"}, info
    try:
        urllib.request.urlopen(base + "/.anthropic_api_key")
        raise AssertionError("served the key file")
    except urllib.error.HTTPError as e:
        assert e.code == 404
    ask = {"system": "TRANSCRIPT\n[0:01] One two.", "messages": [{"role": "user", "content": "Why?"}]}
    assert post(base, ask) == (200, "".join(mock_anthropic.ANSWER))
    headers, body = mock_anthropic.requests[-1]
    headers = {k.lower(): v for k, v in headers.items()}
    key = headers.get("x-api-key") or headers.get("authorization", "").removeprefix("Bearer ")
    assert key == "sk-test-file" and headers["anthropic-workspace-id"] == "wrkspc_test", headers
    assert "server-side-fallback-2026-07-01" in headers["anthropic-beta"], headers
    assert body["model"] == "claude-sonnet-5-5" and body["fallbacks"] == "default" and body["stream"], body
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"} and body["messages"] == ask["messages"], body
    bad = {"system": "x", "messages": [{"role": "assistant", "content": "hi"}]}
    assert post(base, bad)[0] == 400 and len(mock_anthropic.requests) == 1
finally:
    proc.kill()
(pub / ".anthropic_api_key").unlink()
proc, base, info = serve(nokey)
try:
    assert info["enabled"] is False and post(base, ask)[0] == 403, info
finally:
    proc.kill()
api.shutdown()
print("chat ok")


# guide: checkpoint times survive render -> episodes; mtk guide compiles and crops; mtk site embeds both
g = b.parent / "guided"
(g / "web").mkdir(parents=True, exist_ok=True)
(g / "v1.py").write_text('''from mtk import *


class S01_A(VScene):
    def construct(self):
        self.beat("First scene.", FadeIn(Square()))
        self.wipe()


class S02_B(VScene):
    def construct(self):
        self.beat("Your turn.", FadeIn(Circle()))
        self.checkpoint("1.1", "Find the radius")
        self.beat("It is one.", Indicate(Circle()))
        self.wipe()
''')
(g / "BRIEF.md").write_text("# Guided\n\n## S01_A [2]\n## S02_B [5]\n")
(g / "guide.tex").write_text(r"""\documentclass{article}\usepackage{mtkguide}\begin{document}
\checkpoint{1.1}{Radius}{What is the radius of the circle?}
\solutionfor{1.1}{Radius} One.
\end{document}
""")
env = {**os.environ, "MTK_TTS": "say"}
r = subprocess.run(["mtk", "render", "-q", "l"], cwd=g, capture_output=True, text=True, env=env)
assert "checkpoint 1.1: Find the radius" in r.stdout, r.stdout + r.stderr
subprocess.run(["mtk", "episodes", "BRIEF.md", "-q", "l"], cwd=g, capture_output=True, text=True, check=True)
ep = json.loads((g / "web/episodes.json").read_text())[0]
cp = ep["checkpoints"][0]
assert cp["id"] == "1.1" and cp["t"] > ep["chapters"][1]["t"] and cp["scene"] == "S02_B", ep
out = subprocess.run(["mtk", "guide"], cwd=g, capture_output=True, text=True).stdout
assert "GUIDE" not in out and "1 checkpoints cropped" in out, out
gj = json.loads((g / "web/guide.json").read_text())
from PIL import Image
crop = Image.open(g / "web" / gj["checkpoints"]["1.1"]["img"])
assert gj["checkpoints"]["1.1"]["page"] == 1 and 20 < crop.height < 400, (gj, crop.size)
subprocess.run(["mtk", "site"], cwd=g, capture_output=True, text=True, check=True)
page = (g / "web/index.html").read_text()
data = json.loads(re.search(r'id="data">(.*?)</script>', page, re.S).group(1).replace("<\\/", "</"))
v0 = data["videos"][0]  # each video carries its own guide (one guide.tex, or guide-ep01.tex per video)
assert v0["guide"]["checkpoints"]["1.1"]["img"] == "cp-1.1.png" and v0["checkpoints"][0]["id"] == "1.1", v0
print("guide ok")
