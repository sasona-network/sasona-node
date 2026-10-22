# Sasona node

The member's software: what a member runs to test the services a round has drawn.

> **This is the first design, built on Solana devnet. It has been superseded and is kept as a record.** Nothing here runs on mainnet, and the network's new contract is not built yet.
>
> The SASONA coin is live on Solana mainnet since 20 October 2026, at `8xH5RFEkSyneYBhCZh5gi2svgdyrDCREW9SxCfKuYgFd` only; see [`sasona-coin`](https://github.com/sasona-network/sasona-coin). The devnet coin in this repository is a different token, used only for testing.

## What it does so far

| Part | What it does |
|---|---|
| [`reader/read.py`](reader/read.py) | Takes one reading of a drawn service, in the order [sasona-protocol](https://github.com/sasona-network/sasona-protocol) section 2.5 sets: commit the question's hash on chain, call the service with the code, reveal the nonce, the reply's hash and the verdict |
| [`standin/seller.py`](standin/seller.py) | A stand-in `execute` service for devnet, honest or canned, because the services on the devnet test list do not exist |

Both are Python, standard library only. The reader drives the command-line client from [`sasona-program`](https://github.com/sasona-network/sasona-program) for the on-chain steps.

## Take a reading on devnet

```bash
python standin/seller.py honest 8401 &
python reader/read.py --round <round> --service <a drawn service> \
    --send-to http://127.0.0.1:8401 --client <path to sasona> --keypair <path> --out reading/
```

Only the member drawn for a service can read it ([sasona-protocol](https://github.com/sasona-network/sasona-protocol) section 4). The client works out the draw, and stops before sending anything if your key was not drawn. To become a member, lock a stake with `sasona member-join`.

`--first <reading>` makes it a second reading, in a re-read round, of the reading named ([sasona-protocol](https://github.com/sasona-network/sasona-protocol) section 3). The reading named has to be the latest one of that service.
