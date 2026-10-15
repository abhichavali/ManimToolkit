"""python tests/test_check.py: runs `mtk check` on lint_cases.py (offline voice) and asserts every rule fires."""
import os
import subprocess
from pathlib import Path

here = Path(__file__).parent
out = subprocess.run(["mtk", "check", "lint_cases.py"], cwd=here, capture_output=True, text=True,
                     env={**os.environ, "MTK_TTS": "say"}).stdout
print(out)
for want in ["DRIFT q: SKY in S06; EMBER in S07", "past its narration", "S08_Overrun", "lint_cases S05_Zoom", "'buried label' is hidden under a Square", "'x^2' overlaps 'y^2'", "'off the edge' is cut off",
             "'tiny' renders at font size 12", "picture frozen for", "narration contains =", "budget 20",
             "S04_Clean", "media/board/lint_cases.S04_Clean.png"]:
    assert want in out, want
clean = next(ln for ln in out.splitlines() if ln.startswith("lint_cases S04_Clean"))
assert "0 warnings" in clean and "2 beats" not in clean, clean
assert (here / "media/board/lint_cases.S04_Clean.png").exists()
print("check ok")

# script-first brief parsing (mtk voice / mtk brief)
import tempfile
import sys
sys.path.insert(0, str(here.parent))
from mtk_cli import script, groups, vtt
b = Path(tempfile.mkdtemp()) / "BRIEF.md"
b.write_text('# T\n\nshared\n\n## Facts\n- f\n\n## S01_Hook [12]\nPicture: x\n1. "One two."\n   → a\n'
             '2. "Three." (style: slow)\n## S02_Next\n1. "Four."\n')
sc = script(b)
assert sc == {"S01_Hook": (12, [("One two.", None), ("Three.", "slow")]), "S02_Next": (None, [("Four.", None)])}, sc
out = subprocess.run(["mtk", "brief", str(b), "S02"], capture_output=True, text=True).stdout
assert "shared" in out and "- f" in out and "Before you: S01_Hook [12]" in out and "s02_next.py" in out, out
assert '"One two."' not in out.split("YOUR SCENE")[1], out
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
