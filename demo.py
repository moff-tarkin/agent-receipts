#!/usr/bin/env python3
"""Demo: build a receipt chain from three REAL, verified on-chain actions.

All three actions are public, already-verified BSC transactions by wallet
0x7430Fb7D8a9d252Aa40f05483247a45B73636143 (agent tarkin.ai) on 2026-11-26:

  1. AURA day 7 claim — checkIn() on 0x48F9373F0b62920CB34B63B18A84bd776A71B23a,
     tx 0x9483e83017acfa5b0104f179cfc7ddea9b82f00b26f26ea05326cb800c27d7a1,
     +170 AURA, balance 980.
  2. Fateborn Mutant #33 mint — brew() on 0xe69de61cc2c7e4d21a83647d3671d8c009515827,
     tx 0x9dfc694e52922b647f9c2b4a916f4dacafc229216fdef98c700d98c09fec56ed,
     token #33.
  3. PEARL day 24 mine — mine() on 0x7E2DA878217EB995F9e5d36eD32c9Cea52442681,
     nonce 72726998148, tx 0xad9fbd20f6973dccc81bbdb1f090584f6dfb98819787921d7cdbdc2e9cd78b81,
     +73.62327807 PEARL, balance 1570.64658704.

Writes demo-chain.jsonl and demo-output.txt next to this script, then prints
the verification result. Standard library only.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from receipts import (GENESIS_PREV, append_receipt, build_receipt,  # noqa: E402
                      canonical_json, load_chain, verify_chain)

HERE = os.path.dirname(os.path.abspath(__file__))
CHAIN_PATH = os.path.join(HERE, "demo-chain.jsonl")
OUTPUT_PATH = os.path.join(HERE, "demo-output.txt")
WALLET = "0x7430Fb7D8a9d252Aa40f05483247a45B73636143"
AGENT = "tarkin.ai"

# Receipts in chronological order. Timestamps are the actions' real times
# (WAT = UTC+1): AURA ~10:26 WAT, Fateborn minted during the 10:43 WAT scan
# run (run started 10:50:37 WAT), PEARL nonce found 12:16:14 WAT.
DEMO_ACTIONS = [
    {
        "timestamp": "2026-11-26T09:26:00Z",
        "action": "claim",
        "inputs": {
            "wallet": WALLET,
            "contract": "0x48F9373F0b62920CB34B63B18A84bd776A71B23a",
            "function": "checkIn()",
            "args": {},
            "chain": 56,
            "chain_name": "BSC",
        },
        "outputs": {
            "tx_hash": "0x9483e83017acfa5b0104f179cfc7ddea9b82f00b26f26ea05326cb800c27d7a1",
            "reward": "+170 AURA",
            "balance_after": "980 AURA",
            "streak": 7,
            "day": 7,
        },
    },
    {
        "timestamp": "2026-11-26T09:50:37Z",
        "action": "mint",
        "inputs": {
            "wallet": WALLET,
            "contract": "0xe69de61cc2c7e4d21a83647d3671d8c009515827",
            "function": "brew()",
            "args": {},
            "chain": 56,
            "chain_name": "BSC",
        },
        "outputs": {
            "tx_hash": "0x9dfc694e52922b647f9c2b4a916f4dacafc229216fdef98c700d98c09fec56ed",
            "token_id": 33,
            "collection": "Fateborn Mutant",
        },
    },
    {
        "timestamp": "2026-11-26T11:16:14Z",
        "action": "mine",
        "inputs": {
            "wallet": WALLET,
            "contract": "0x7E2DA878217EB995F9e5d36eD32c9Cea52442681",
            "function": "mine(uint256,uint256,uint256)",
            "args": {
                "id": "96764417055472979960902442605145561860896804095904113850166865318521985956754",
                "nonce": 72726998148,
            },
            "chain": 56,
            "chain_name": "BSC",
        },
        "outputs": {
            "tx_hash": "0xad9fbd20f6973dccc81bbdb1f090584f6dfb98819787921d7cdbdc2e9cd78b81",
            "reward": "+73.62327807 PEARL",
            "balance_after": "1570.64658704 PEARL",
        },
    },
]


def main():
    # Rebuild the chain from scratch so the demo is reproducible.
    if os.path.exists(CHAIN_PATH):
        os.remove(CHAIN_PATH)

    prev_hash = GENESIS_PREV
    for i, item in enumerate(DEMO_ACTIONS, start=1):
        receipt = build_receipt(
            seq=i,
            prev_hash=prev_hash,
            agent_id=AGENT,
            action=item["action"],
            inputs=item["inputs"],
            outputs=item["outputs"],
            timestamp=item["timestamp"],
        )
        append_receipt(CHAIN_PATH, receipt)
        prev_hash = receipt["hash"]
        print(f"seq {i} {item['action']}: hash {receipt['hash'][:16]}...")

    receipts = load_chain(CHAIN_PATH)
    ok, fail_seq, reason = verify_chain(receipts)
    lines = [
        f"demo chain: {CHAIN_PATH}",
        f"receipts: {len(receipts)}",
        f"verify: {'OK' if ok else f'FAIL at seq {fail_seq}'}",
        f"detail: {reason}",
        f"tip hash: {receipts[-1]['hash'] if receipts else 'n/a'}",
    ]
    output = "\n".join(lines) + "\n"
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(output)
    print()
    print(output, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
