"""python tests/test_check.py: runs `mtk check` on lint_cases.py (offline voice) and asserts every rule fires."""
import os
import subprocess
from pathlib import Path

here = Path(__file__).parent
out = subprocess.run(["mtk", "check", "lint_cases.py"], cwd=here, capture_output=True, text=True,
                     env={**os.environ, "MTK_TTS": "say"}).stdout
print(out)
for want in ["'buried label' is hidden under a Square", "'x^2' overlaps 'y^2'", "'off the edge' is cut off",
             "'tiny' renders at font size 12", "picture frozen for", "narration contains =", "budget 20",
             "S04_Clean", "media/board/lint_cases.S04_Clean.png"]:
    assert want in out, want
clean = next(ln for ln in out.splitlines() if ln.startswith("lint_cases S04_Clean"))
assert "0 warnings" in clean and "2 beats" not in clean, clean
assert (here / "media/board/lint_cases.S04_Clean.png").exists()
print("check ok")
