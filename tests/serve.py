"""Static server for testing a site locally (mtk_serve without chat). By default it ignores Range requests (always
200 + the whole file), which is what makes Chromium unable to seek on the claude.ai artifact file server; --ranges
serves 206 partial content like a normal static host. Responses are never cached, so every load is a cold one;
--kbps N throttles every response to N kilobytes per second (a slow connection).
python3 tests/serve.py DIR [PORT] [--ranges] [--kbps N]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mtk_serve import serve  # noqa: E402

if __name__ == "__main__":
    argv = sys.argv[1:]
    kbps = 0
    if "--kbps" in argv:
        i = argv.index("--kbps")
        kbps = float(argv[i + 1])
        del argv[i:i + 2]
    args = [x for x in argv if not x.startswith("--")]
    serve(args[0], int(args[1]) if len(args) > 1 else 8765, chat=False, ranges="--ranges" in argv, no_store=True,
          kbps=kbps)
