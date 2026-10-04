"""Take one reading of a drawn service, as sasona-protocol SPEC.md 2.5 orders it.

    python read.py --round <round address> --service <url as drawn> \\
                   --client <path to the sasona client> --keypair <path> \\
                   --out <folder> [--send-to <url>] [--first <reading>]

1. Pick a fresh nonce and build the question from it.
2. Commit the question's hash on chain, and wait until it is final.
3. Send the service the code, and keep its reply exactly as received.
4. Hash the reply and work out the verdict.
5. Reveal the nonce, the reply's hash and the verdict on chain.

--first makes it a second reading of an earlier one (SPEC.md section 3): it is
committed as a re-test of that reading, in a re-read round.

--replay makes it the replay of a chargeback (SPEC.md 7.4): --round is then
not used, and the reading is committed for the purchase named, by the member
drawn for it. The draw's entropy is recorded first if nobody has.

If the service names where it asks to be paid, in an X-Pay-To header, that
address is recorded with the reading (SPEC.md 7.1).

--send-to sends the request somewhere other than the service's own URL. The
devnet test list is made of services that do not exist, so the proof sends
each request to a stand-in instead, and says so.

Everything a checker needs is written to --out: the question's exact bytes,
the reply's exact bytes, and the two transactions. The nonce stays in memory
until it has been revealed.

Standard library only.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

VERDICTS = {1: "delivered", 2: "wrong_answer", 3: "empty"}
MAX_REPLY_BYTES = 10_000


# sasona-protocol SPEC.md 2.1 to 2.4, as in that repository's reference/question.py.
def expected(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("ascii")).hexdigest()[:16]


def code_for(nonce: str) -> str:
    return 'import hashlib\nprint(hashlib.sha256("' + nonce + '".encode()).hexdigest()[:16])'


def canonical(nonce: str) -> bytes:
    code = code_for(nonce)
    q = {"capability": "execute", "nonce": nonce, "expect": expected(nonce), "tier": 1, "code": code,
         "command": ["python", "-c", code], "body": {"code": code, "language": "python"}}
    return json.dumps(q, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def verdict(reply: bytes, nonce: str) -> int:
    if not reply:
        return 3
    return 1 if expected(nonce).encode("ascii") in reply else 2


def client(args, *words) -> str:
    out = subprocess.run([args.client, *words, "--keypair", args.keypair], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"the client failed: {out.stderr.strip()}")
    return out.stdout.strip().splitlines()[-1]


def main():
    p = argparse.ArgumentParser()
    for name in ("--service", "--client", "--keypair", "--out"):
        p.add_argument(name, required=True)
    p.add_argument("--round")
    p.add_argument("--send-to")
    p.add_argument("--first")
    p.add_argument("--replay")
    args = p.parse_args()

    nonce = os.urandom(16).hex()
    question = canonical(nonce)
    question_hash = hashlib.sha256(question).hexdigest()

    if args.replay:
        draw = subprocess.run([args.client, "record-draw", args.replay, "--keypair", args.keypair], capture_output=True, text=True)
        if draw.returncode == 0:
            print(f"recorded   {draw.stdout.strip().splitlines()[-1]}")
        commit_tx = client(args, "commit-replay", args.replay, args.service, question_hash)
    elif args.first:
        commit_tx = client(args, "commit-second", args.round, args.service, question_hash, args.first)
    else:
        commit_tx = client(args, "commit-reading", args.round, args.service, question_hash)
    print(f"committed  {commit_tx}")

    # Only the code goes to the service, never the question (SPEC.md 2.2).
    body = json.dumps({"code": code_for(nonce), "language": "python"}).encode()
    req = urllib.request.Request(args.send_to or args.service, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        # SPEC.md 2.4: the reply is the first 10,000 bytes. That is all a
        # member can put on chain if the reading is challenged.
        reply = r.read(MAX_REPLY_BYTES)
        pay_to = r.headers.get("X-Pay-To", "")
    reply_hash = hashlib.sha256(reply).hexdigest()
    v = verdict(reply, nonce)
    print(f"reply      {len(reply)} bytes, {VERDICTS[v]}")

    paid = ["--pay-to", pay_to] if pay_to else []
    if args.replay:
        reveal_tx = client(args, "reveal-replay", args.replay, nonce, reply_hash, str(v), *paid)
    else:
        reveal_tx = client(args, "reveal-reading", args.round, args.service, nonce, reply_hash, str(v), *paid)
    print(f"revealed   {reveal_tx}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "question.json").write_bytes(question)
    (out / "reply.bin").write_bytes(reply)
    (out / "reading.json").write_text(json.dumps({
        "round": args.round, "service": args.service, "sent_to": args.send_to or args.service,
        "nonce": nonce, "question_hash": question_hash, "reply_hash": reply_hash,
        "verdict": v, "commit_tx": commit_tx, "reveal_tx": reveal_tx, "first": args.first,
        "replay_of": args.replay, "pay_to": pay_to,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
