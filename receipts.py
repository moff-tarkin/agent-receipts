#!/usr/bin/env python3
"""Agent Receipts — verifiable, hash-chained records of an AI agent's work.

A receipt is one JSON object per action. Receipts live in a .jsonl chain file,
each one linked to the previous receipt by hash, so editing any receipt breaks
verification of that receipt and everything after it.

Hash: SHA-256 over the canonical JSON of every field except `hash` itself
(keys sorted, no whitespace, UTF-8).

Standard library only. No network access except the optional read-only
gateway check in `anchor` (GET only, never POST).

Usage:
    python3 receipts.py record --type mine --input '{"contract": "0x..."}' \
        --output '{"tx_hash": "0x..."}' --chain receipts.jsonl
    python3 receipts.py verify --chain receipts.jsonl
    python3 receipts.py anchor --chain receipts.jsonl [--gateway https://arweave.net]
    python3 receipts.py export --chain receipts.jsonl
"""

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone

VERSION = 1
GENESIS_PREV = "0" * 64
ACTIONS = ("mint", "mine", "claim", "inference")
DEFAULT_CHAIN = "receipts.jsonl"


def canonical_json(obj):
    """Canonical JSON: keys sorted, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(receipt):
    """SHA-256 hex of the canonical JSON of all fields except `hash`."""
    payload = {k: v for k, v in receipt.items() if k != "hash"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_receipt(seq, prev_hash, agent_id, action, inputs, outputs,
                  model=None, params=None, timestamp=None):
    """Build a receipt dict (without hash), then attach its hash."""
    receipt = {
        "version": VERSION,
        "seq": seq,
        "timestamp": timestamp or utcnow_iso(),
        "agent_id": agent_id,
        "action": action,
        "inputs": inputs,
        "outputs": outputs,
        "model": model,
        "params": params,
        "prev_hash": prev_hash,
    }
    receipt["hash"] = compute_hash(receipt)
    return receipt


def load_chain(path):
    """Load a .jsonl chain file. Returns a list of receipt dicts."""
    receipts = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    receipts.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}")
    except FileNotFoundError:
        return []
    return receipts


def append_receipt(path, receipt):
    with open(path, "a", encoding="utf-8") as f:
        f.write(canonical_json(receipt) + "\n")


def verify_chain(receipts):
    """Verify a list of receipts.

    Returns (ok, fail_seq, reason). ok is True when the chain is intact.
    fail_seq is the seq of the first receipt that fails (or None).
    """
    if not receipts:
        return True, None, "empty chain: nothing to verify"
    prev_hash = GENESIS_PREV
    for pos, receipt in enumerate(receipts, start=1):
        seq = receipt.get("seq")
        if seq != pos:
            return False, seq, f"seq out of order: expected {pos}, found {seq}"
        if receipt.get("prev_hash") != prev_hash:
            return False, seq, (
                f"prev_hash mismatch: expected {prev_hash[:16]}..., "
                f"found {str(receipt.get('prev_hash'))[:16]}..."
            )
        expected = compute_hash(receipt)
        if receipt.get("hash") != expected:
            return False, seq, (
                f"hash mismatch: stored {str(receipt.get('hash'))[:16]}..., "
                f"recomputed {expected[:16]}..."
            )
        prev_hash = receipt["hash"]
    return True, None, f"chain OK: {len(receipts)} receipts, tip {prev_hash}"


def parse_json_arg(text, name):
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: --{name} is not valid JSON: {exc}")
    if not isinstance(value, dict):
        raise SystemExit(f"error: --{name} must be a JSON object")
    return value


def cmd_record(args):
    receipts = load_chain(args.chain)
    seq = len(receipts) + 1
    prev_hash = receipts[-1]["hash"] if receipts else GENESIS_PREV
    inputs = parse_json_arg(args.input, "input")
    outputs = parse_json_arg(args.output, "output")
    params = None
    if args.params is not None:
        params = parse_json_arg(args.params, "params")
    receipt = build_receipt(
        seq=seq,
        prev_hash=prev_hash,
        agent_id=args.agent,
        action=args.type,
        inputs=inputs,
        outputs=outputs,
        model=args.model,
        params=params,
    )
    append_receipt(args.chain, receipt)
    print(f"recorded seq {seq} -> {args.chain}")
    print(f"  hash: {receipt['hash']}")
    print(f"  prev: {receipt['prev_hash'][:16]}...")
    return 0


def cmd_verify(args):
    try:
        receipts = load_chain(args.chain)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1
    ok, fail_seq, reason = verify_chain(receipts)
    if ok:
        print(f"OK: {reason}")
        return 0
    print(f"FAIL at seq {fail_seq}: {reason}")
    return 1


def cmd_anchor(args):
    try:
        receipts = load_chain(args.chain)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1
    if not receipts:
        print("FAIL: chain is empty, nothing to anchor")
        return 1
    tip = receipts[-1]
    anchor_doc = {
        "version": VERSION,
        "app": "agent-receipts",
        "chain_file": args.chain,
        "receipt_count": len(receipts),
        "tip_seq": tip["seq"],
        "tip_hash": tip["hash"],
        "tip_timestamp": tip["timestamp"],
        "agent_id": tip["agent_id"],
        "created_at": utcnow_iso(),
        "arweave": {
            "network": "arweave.net (mainnet)",
            "note": "DRY-RUN: this document was NOT uploaded. Uploading costs AR.",
            "suggested_tags": [
                {"name": "App-Name", "value": "agent-receipts"},
                {"name": "Tip-Hash", "value": tip["hash"]},
                {"name": "Receipt-Count", "value": str(len(receipts))},
                {"name": "Content-Type", "value": "application/json"},
            ],
        },
    }
    with open(args.anchor_out, "w", encoding="utf-8") as f:
        json.dump(anchor_doc, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"anchor document written to {args.anchor_out} (dry-run, nothing uploaded)")
    print(f"  tip hash: {tip['hash']}")
    print(f"  receipts: {len(receipts)} (seq 1..{tip['seq']})")

    if args.gateway:
        url = args.gateway.rstrip("/") + "/info"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = resp.read(512).decode("utf-8", "replace")
            print(f"gateway check: {args.gateway} reachable (GET {url} -> HTTP {resp.status})")
            print(f"  info preview: {body[:200]}")
        except Exception as exc:  # noqa: BLE001 - report any reachability failure
            print(f"gateway check: {args.gateway} NOT reachable ({exc})")

    print()
    print("To anchor for real (costs AR — do NOT run without explicit instruction):")
    print("  1. Fund an Arweave wallet (arweave.app) with enough AR for the data size.")
    print("  2. Create a transaction with the anchor document as data, e.g.:")
    print("       POST https://arweave.net/tx  (signed, with the tags above)")
    print("     or use the arweave-js SDK: arweave.createTransaction({ data }, wallet)")
    print("  3. Confirm it: GET https://arweave.net/tx/<txid>/status")
    print("  4. Record the Arweave txid back into the chain as an anchor receipt.")
    return 0


def cmd_export(args):
    try:
        receipts = load_chain(args.chain)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    json.dump(receipts, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="receipts.py",
        description="Agent Receipts — verifiable, hash-chained records of agent work.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_record = sub.add_parser("record", help="Append a receipt to a chain file.")
    p_record.add_argument("--type", required=True, choices=ACTIONS,
                          help="Action type: mint, mine, claim, inference.")
    p_record.add_argument("--input", required=True, help="Inputs as a JSON object string.")
    p_record.add_argument("--output", required=True, help="Outputs as a JSON object string.")
    p_record.add_argument("--chain", default=DEFAULT_CHAIN, help="Chain file (default: receipts.jsonl).")
    p_record.add_argument("--agent", default="tarkin.ai", help="Agent ID (default: tarkin.ai).")
    p_record.add_argument("--model", default=None, help="Model name (inference actions).")
    p_record.add_argument("--params", default=None, help="Model params as a JSON object string.")
    p_record.set_defaults(func=cmd_record)

    p_verify = sub.add_parser("verify", help="Verify a chain file.")
    p_verify.add_argument("--chain", default=DEFAULT_CHAIN, help="Chain file (default: receipts.jsonl).")
    p_verify.set_defaults(func=cmd_verify)

    p_anchor = sub.add_parser("anchor", help="Prepare an Arweave anchor document (dry-run by default).")
    p_anchor.add_argument("--chain", default=DEFAULT_CHAIN, help="Chain file (default: receipts.jsonl).")
    p_anchor.add_argument("--anchor-out", default="anchor.json", help="Anchor document path (default: anchor.json).")
    p_anchor.add_argument("--gateway", default=None,
                          help="Optional Arweave gateway base URL for a read-only reachability check (GET only).")
    p_anchor.set_defaults(func=cmd_anchor)

    p_export = sub.add_parser("export", help="Print the chain as a single JSON array.")
    p_export.add_argument("--chain", default=DEFAULT_CHAIN, help="Chain file (default: receipts.jsonl).")
    p_export.set_defaults(func=cmd_export)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
