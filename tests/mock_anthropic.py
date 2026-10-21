"""A stand-in for the Anthropic Messages API, so chat tests cost nothing and need no key: it streams a fixed answer
(with a [m:ss] citation) as server-sent events and records each request. Point the SDK at it with
ANTHROPIC_BASE_URL=http://127.0.0.1:PORT. python3 tests/mock_anthropic.py [PORT]"""
import http.server
import json
import sys
import threading
import time

ANSWER = ["The error **squares** each step: ", "e_{n+1} ≈ e_n² / 2√2, ", "which is why the digits double [2:09]."]
requests = []  # (headers, body) of every POST


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests.append((dict(self.headers), body))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()

        def ev(kind, data):
            self.wfile.write(f"event: {kind}\ndata: {json.dumps({'type': kind, **data})}\n\n".encode())
            self.wfile.flush()

        usage = {"input_tokens": 10, "output_tokens": 0}
        ev("message_start", {"message": {"id": "msg_mock", "type": "message", "role": "assistant", "model": body["model"],
                                          "content": [], "stop_reason": None, "stop_sequence": None, "usage": usage}})
        ev("content_block_start", {"index": 0, "content_block": {"type": "text", "text": ""}})
        for part in ANSWER:
            time.sleep(0.15)  # slow enough to see it stream
            ev("content_block_delta", {"index": 0, "delta": {"type": "text_delta", "text": part}})
        ev("content_block_stop", {"index": 0})
        ev("message_delta", {"delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 20}})
        ev("message_stop", {})


def start(port=0):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    srv = start(int(sys.argv[1]) if len(sys.argv) > 1 else 8790)
    print(f"mock Anthropic API on http://127.0.0.1:{srv.server_port}", flush=True)
    threading.Event().wait()
