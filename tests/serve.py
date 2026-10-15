"""Static server for testing a site locally. By default it ignores Range requests (always 200 + the whole file),
which is what makes Chromium unable to seek outside its buffer on the claude.ai artifact file server; --ranges
serves 206 partial content like a normal static host. Responses are never cached, so every load is a cold one;
--kbps N throttles every response to N kilobytes per second (a slow connection).
python3 tests/serve.py DIR [PORT] [--ranges] [--kbps N]"""
import functools
import http.server
import mimetypes
import os
import re
import sys
import time

KBPS = 0

mimetypes.add_type("text/vtt", ".vtt")


def _pace(src, dst, n=None):
    """Copy src to dst (at most n bytes), at KBPS if set."""
    while n is None or n > 0:
        chunk = src.read(1 << 14 if n is None else min(1 << 14, n))
        if not chunk:
            break
        dst.write(chunk)
        if n is not None:
            n -= len(chunk)
        if KBPS:
            time.sleep(len(chunk) / (KBPS * 1024))


class Plain(http.server.SimpleHTTPRequestHandler):
    def copyfile(self, src, dst):
        _pace(src, dst)

    def end_headers(self):  # no browser caching: a cached copy is range-seekable and hides the bug
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class Ranged(Plain):
    def send_head(self):
        self._left = None
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        path = self.translate_path(self.path)
        if not m or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        a = int(m[1]) if m[1] else max(0, size - int(m[2] or 0))
        b = min(int(m[2]) if m[1] and m[2] else size - 1, size - 1)
        if a > b:
            self.send_error(416)
            return None
        f = open(path, "rb")
        f.seek(a)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        self.send_header("Content-Length", str(b - a + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._left = b - a + 1
        return f

    def copyfile(self, src, dst):
        _pace(src, dst, self._left)


if __name__ == "__main__":
    if "--kbps" in sys.argv:
        KBPS = float(sys.argv[sys.argv.index("--kbps") + 1])
        sys.argv[sys.argv.index("--kbps"):sys.argv.index("--kbps") + 2] = []
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    handler = Ranged if "--ranges" in sys.argv else Plain
    port = int(args[1]) if len(args) > 1 else 8765
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(handler, directory=args[0]))
    print(f"serving {args[0]} on http://127.0.0.1:{port} ({'with' if handler is Ranged else 'without'} Range support)",
          flush=True)
    srv.serve_forever()
