"""A stand-in for an `execute` service, for testing readings on devnet.

    python seller.py honest 8401 [pay-to address]
    python seller.py canned 8402 [pay-to address]

It takes a POST with a JSON body {"code": ..., "language": "python"} and
answers like a code-execution service would.

  honest  answers what the challenge code prints. It does not run the code
          it is sent: running code from the network is not something a
          stand-in should do. It recognises the challenge and computes the
          answer itself. sasona-protocol SPEC.md 2.6 says plainly that this
          still counts as delivered: an `execute` reading checks the answer,
          not how it was produced.
  canned  answers the same fixed reply to everything, which is what a
          service that takes payment and does nothing often returns.

With a pay-to address, every reply names it in an X-Pay-To header: where the
service asks to be paid, which a reader records (sasona-protocol SPEC.md 7.1).

Standard library only.
"""

import hashlib
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

CHALLENGE = re.compile(r'hashlib\.sha256\("([0-9a-f]{32})"\.encode\(\)\)\.hexdigest\(\)\[:16\]')
CANNED = b'{"status":"ok","output":"done"}'


def answer(code: str) -> bytes:
    m = CHALLENGE.search(code)
    if not m:
        return json.dumps({"stdout": "", "stderr": "unsupported", "exit": 1}).encode()
    printed = hashlib.sha256(m.group(1).encode()).hexdigest()[:16] + "\n"
    return json.dumps({"stdout": printed, "exit": 0}).encode()


def handler(mode: str, pay_to: str):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            try:
                code = json.loads(self.rfile.read(length))["code"]
            except (ValueError, KeyError, TypeError):
                code = ""
            body = answer(code) if mode == "honest" else CANNED
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            if pay_to:
                self.send_header("X-Pay-To", pay_to)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return Handler


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4) or sys.argv[1] not in ("honest", "canned"):
        sys.exit(__doc__)
    pay_to = sys.argv[3] if len(sys.argv) == 4 else ""
    HTTPServer(("127.0.0.1", int(sys.argv[2])), handler(sys.argv[1], pay_to)).serve_forever()
