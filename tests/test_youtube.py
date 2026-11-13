"""python tests/test_youtube.py: mtk youtube and the site build around it, offline (YouTube's answer is faked)."""
import contextlib
import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from argparse import Namespace as NS
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mtk_cli as cli  # noqa: E402

ID = "M7lc1UVf-VE"
for url in (ID, f"https://youtu.be/{ID}", f"https://youtu.be/{ID}?si=x", f"https://www.youtube.com/watch?v={ID}&t=3",
            f"https://www.youtube.com/embed/{ID}", f"https://youtube.com/shorts/{ID}"):
    assert cli.YT_ID.search(url)[1] == ID, url
assert not cli.YT_ID.search("https://example.com/short")


def refuse(url, timeout=None):
    raise urllib.error.HTTPError(url, 401, "Unauthorized", None, None)


def run(fn, a):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        fn(a)
    return out.getvalue()


os.chdir(tempfile.mkdtemp())
Path("web").mkdir()
for f in ("ep01.mp4", "ep01.jpg", "ep02.mp4", "ep02.jpg"):
    Path("web", f).write_bytes(b"x")
man = Path("web/episodes.json")
man.write_text(json.dumps([dict(stem=s, kind="episode", n=n, title=s, sub="", file=f"{s}.mp4", poster=f"{s}.jpg", captions=None,
                                duration=60, mb=1, checkpoints=[], chapters=[]) for n, s in ((1, "ep01"), (2, "ep02"))]))
ids = lambda: {e["stem"]: e.get("youtube") for e in json.loads(man.read_text())}

urllib.request.urlopen = refuse  # private, or embedding off: never saved
try:
    run(cli.youtube, NS(pairs=[f"ep01={ID}"]))
    raise AssertionError("a refused video was accepted")
except SystemExit as e:
    assert "Allow embedding" in str(e)
assert ids() == {"ep01": None, "ep02": None}

urllib.request.urlopen = lambda url, timeout=None: None
assert "local (upload out/ep01.mp4" in run(cli.youtube, NS(pairs=[]))
run(cli.youtube, NS(pairs=[f"ep01=https://youtu.be/{ID}"]))
assert ids() == {"ep01": ID, "ep02": None}

vids, files = cli._videos(Path("web"))  # the embedded video ships its poster but not its file
assert "file" not in vids[0] and vids[0]["youtube"] == ID and vids[1]["file"] == "ep02.mp4"
assert "ep01.mp4" not in files and "ep01.jpg" in files and "ep02.mp4" in files

site = NS(subjects=None, title="T", kicker=None, blurb=None, out=None)
out = run(cli.site, site)
assert "artifacts refuse" in out and "batch 1" not in out  # no publish plan for a page an artifact can't play
assert f'"youtube": "{ID}"' in Path("web/index.html").read_text()

run(cli.youtube, NS(pairs=["ep01="]))
assert ids() == {"ep01": None, "ep02": None}
assert "batch 1" in run(cli.site, site)
print("youtube ok")
