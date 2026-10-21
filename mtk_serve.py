"""`mtk serve`: a study site on http://127.0.0.1, plus /api/chat, which answers questions about a video with Claude
using YOUR Anthropic API key, server-side: the page sends the question and the video's transcript, this server adds
the key and streams the answer back. The browser never sees the key.

Key: ANTHROPIC_API_KEY, else a .anthropic_api_key file in the project folder (the working directory, the served
folder or its parent), else ~/.anthropic_api_key. A key that isn't scoped to a workspace also needs the workspace's
id: ANTHROPIC_WORKSPACE_ID, else .anthropic_workspace_id in the same places. With no key the chat endpoint reports
itself off and the page shows no chat box. Dotfiles are never served, so a key file inside a site folder stays put.
"""
import functools
import http.server
import json
import mimetypes
import os
import re
import time
from pathlib import Path

MODEL = "claude-sonnet-5-5"  # the user asked for Sonnet
mimetypes.add_type("text/vtt", ".vtt")
KBPS = 0  # tests: throttle responses to this many KB/s


def _find(name, env, folders):
    if os.environ.get(env, "").strip():
        return os.environ[env].strip(), f"${env}"
    for d in folders:
        f = d / f".{name}"
        if f.is_file() and f.read_text().strip():
            return f.read_text().strip(), str(f)
    return None, None


def credentials(folders=()):
    """(key, workspace id, where the key came from) or (None, None, None). Never print the key."""
    folders = list(dict.fromkeys(Path(f).resolve() for f in [*folders, Path.cwd()])) + [Path.home()]
    key, where = _find("anthropic_api_key", "ANTHROPIC_API_KEY", folders)
    ws, _ = _find("anthropic_workspace_id", "ANTHROPIC_WORKSPACE_ID", folders)
    return key, ws, where


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


def _validate(body):
    """The page's request: {system: str, messages: [{role, content}], alternating, starting and ending with user}."""
    system, messages = body["system"], body["messages"]
    if not isinstance(system, str) or len(system) > 400_000:
        raise ValueError("system must be text under 400k characters")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 41:
        raise ValueError("1 to 41 messages")
    for i, m in enumerate(messages):
        if m.get("role") != ("user" if i % 2 == 0 else "assistant") or not isinstance(m.get("content"), str):
            raise ValueError("messages must alternate user/assistant text, starting with user")
        if len(m["content"]) > 20_000:
            raise ValueError("a message is over 20k characters")
    if messages[-1]["role"] != "user":
        raise ValueError("the last message must be the user's")
    return system, [{"role": m["role"], "content": m["content"]} for m in messages]


class Handler(http.server.SimpleHTTPRequestHandler):
    ranges, no_store, quiet, chat = True, False, False, None  # chat: {key, ws, where} when a key was found

    def log_message(self, *a):
        if not self.quiet:
            super().log_message(*a)

    def end_headers(self):
        if self.no_store:  # tests: a cached copy is range-seekable and would hide the artifact-server behavior
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_head(self):
        self._left = None
        if any(p.startswith(".") for p in self.path.split("?")[0].split("/")):
            self.send_error(404)  # never serve dotfiles: an API key file must not leave this machine
            return None
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", "")) if self.ranges else None
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

    def do_GET(self):
        if self.path.split("?")[0] == "/api/chat":
            return self._json(200, {"enabled": bool(self.chat), "model": MODEL})
        super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/chat":
            return self.send_error(404)
        if not self.chat:
            return self._json(403, {"error": "chat is off: no Anthropic API key found"})
        n = int(self.headers.get("Content-Length") or 0)
        if n > 4_000_000:
            return self._json(413, {"error": "request too large"})
        try:
            system, messages = _validate(json.loads(self.rfile.read(n)))
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            return self._json(400, {"error": f"bad request: {e}"})
        self._answer(system, messages)

    def _answer(self, system, messages):
        import anthropic
        ws = self.chat["ws"]
        client = anthropic.Anthropic(api_key=self.chat["key"], max_retries=2,
                                     default_headers={"anthropic-workspace-id": ws} if ws else None)
        started, err, note = False, None, ""
        try:
            with client.beta.messages.stream(
                model=MODEL,
                max_tokens=4096,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],  # transcript
                messages=messages,
                output_config={"effort": "low"},  # chat
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",  # a declined answer is retried server-side on the recommended model
            ) as stream:
                for text in stream.text_stream:
                    if not started:
                        started = True
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                    self.wfile.write(text.encode())
                    self.wfile.flush()
                final = stream.get_final_message()
            if final.stop_reason == "refusal":
                note = "\n\n(Claude declined to answer this one.)"
            elif final.stop_reason == "max_tokens":
                note = "\n\n(The answer was cut off at its length limit.)"
        except anthropic.AuthenticationError:
            err = "the API key was rejected"
        except anthropic.RateLimitError:
            err = "rate limited by the Anthropic API; try again in a minute"
        except anthropic.APIStatusError as e:
            err = f"Anthropic API error {e.status_code}: {e.message}"
        except anthropic.APIConnectionError:
            err = "couldn't reach the Anthropic API"
        except (BrokenPipeError, ConnectionResetError):
            return  # the viewer navigated away mid-answer
        if err and not started:
            return self._json(502, {"error": err})
        if err:
            note = f"\n\n(The answer stopped: {err}.)"
        if note:
            if not started:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
            self.wfile.write(note.encode())


def serve(folder, port=8000, chat=True, ranges=True, no_store=False, kbps=0, quiet=False):
    global KBPS
    KBPS = kbps
    folder = Path(folder).resolve()
    key, ws, where = credentials([folder, folder.parent]) if chat else (None, None, None)
    H = type("H", (Handler,), {"ranges": ranges, "no_store": no_store, "quiet": quiet,
                               "chat": {"key": key, "ws": ws, "where": where} if key else None})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=str(folder)))
    state = (f"on ({MODEL}; key from {where}; workspace id {'set' if ws else 'not set'})" if key
             else "off (no Anthropic API key found)" if chat else "off")
    print(f"serving {folder} on http://127.0.0.1:{port} ({'with' if ranges else 'without'} Range support); "
          f"chat {state}", flush=True)
    srv.serve_forever()
