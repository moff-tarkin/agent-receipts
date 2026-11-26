#!/usr/bin/env python3
"""Tests for Agent Receipts (stdlib unittest only).

Run:  python3 test_receipts.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from receipts import (GENESIS_PREV, append_receipt, build_receipt,  # noqa: E402
                      compute_hash, load_chain, verify_chain)

HERE = os.path.dirname(os.path.abspath(__file__))
WALLET = "0x7430Fb7D8a9d252Aa40f05483247a45B73636143"


def make_chain(tmpdir, n=3):
    """Build a valid chain of n receipts in tmpdir, return (path, receipts)."""
    path = os.path.join(tmpdir, "chain.jsonl")
    receipts = []
    prev = GENESIS_PREV
    for i in range(1, n + 1):
        r = build_receipt(
            seq=i,
            prev_hash=prev,
            agent_id="tarkin.ai",
            action="mint",
            inputs={"wallet": WALLET, "contract": "0x" + "ab" * 20, "function": "mint(1)"},
            outputs={"tx_hash": "0x" + f"{i:064x}", "token_id": i},
            timestamp=f"2026-11-26T0{i}:00:00Z",
        )
        append_receipt(path, r)
        receipts.append(r)
        prev = r["hash"]
    return path, receipts


class TestHash(unittest.TestCase):
    def test_hash_recomputation_matches(self):
        r = build_receipt(1, GENESIS_PREV, "tarkin.ai", "claim",
                          {"contract": "0x1234"}, {"tx_hash": "0xabcd"},
                          timestamp="2026-11-26T09:26:00Z")
        self.assertEqual(r["hash"], compute_hash(r))

    def test_hash_changes_when_any_field_changes(self):
        r1 = build_receipt(1, GENESIS_PREV, "tarkin.ai", "claim",
                           {"contract": "0x1234"}, {"amount": 170},
                           timestamp="2026-11-26T09:26:00Z")
        r2 = build_receipt(1, GENESIS_PREV, "tarkin.ai", "claim",
                           {"contract": "0x1234"}, {"amount": 171},
                           timestamp="2026-11-26T09:26:00Z")
        self.assertNotEqual(r1["hash"], r2["hash"])

    def test_genesis_prev_hash_is_64_zeros(self):
        r = build_receipt(1, GENESIS_PREV, "tarkin.ai", "mine",
                          {"nonce": 1}, {"reward": "1 PEARL"},
                          timestamp="2026-11-26T11:16:14Z")
        self.assertEqual(r["prev_hash"], "0" * 64)


class TestChainVerify(unittest.TestCase):
    def test_valid_chain_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = make_chain(tmp, 3)
            ok, fail_seq, reason = verify_chain(load_chain(path))
            self.assertTrue(ok, reason)
            self.assertIsNone(fail_seq)

    def test_tampered_output_breaks_at_the_right_seq(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, receipts = make_chain(tmp, 3)
            tampered = [dict(r) for r in receipts]
            tampered[1]["outputs"] = {"tx_hash": "0x" + "ff" * 32, "token_id": 999}
            ok, fail_seq, _ = verify_chain(tampered)
            self.assertFalse(ok)
            self.assertEqual(fail_seq, 2)

    def test_tampered_hash_field_breaks_at_the_right_seq(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, receipts = make_chain(tmp, 3)
            tampered = [dict(r) for r in receipts]
            tampered[2]["hash"] = "0" * 64
            ok, fail_seq, _ = verify_chain(tampered)
            self.assertFalse(ok)
            self.assertEqual(fail_seq, 3)

    def test_reordered_chain_breaks_linkage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, receipts = make_chain(tmp, 3)
            reordered = [receipts[1], receipts[0], receipts[2]]
            ok, fail_seq, reason = verify_chain(reordered)
            self.assertFalse(ok)
            self.assertEqual(fail_seq, 2)
            self.assertIn("seq", reason)

    def test_tamper_after_the_break_is_not_reached(self):
        # Verification stops at the FIRST failure, so a later tamper is masked.
        with tempfile.TemporaryDirectory() as tmp:
            path, receipts = make_chain(tmp, 3)
            tampered = [dict(r) for r in receipts]
            tampered[0]["outputs"] = {"tx_hash": "0x" + "ee" * 32}
            tampered[2]["outputs"] = {"tx_hash": "0x" + "dd" * 32}
            ok, fail_seq, _ = verify_chain(tampered)
            self.assertFalse(ok)
            self.assertEqual(fail_seq, 1)


class TestCLI(unittest.TestCase):
    def run_cli(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, os.path.join(HERE, "receipts.py"), *args],
            capture_output=True, text=True, cwd=cwd or HERE,
        )

    def test_cli_record_then_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            chain = os.path.join(tmp, "c.jsonl")
            r1 = self.run_cli("record", "--type", "mine",
                              "--input", '{"contract": "0x7E2DA878217EB995F9e5d36eD32c9Cea52442681", "nonce": 72726998148}',
                              "--output", '{"tx_hash": "0xad9fbd20f6973dccc81bbdb1f090584f6dfb98819787921d7cdbdc2e9cd78b81"}',
                              "--chain", chain)
            self.assertEqual(r1.returncode, 0, r1.stderr)
            r2 = self.run_cli("verify", "--chain", chain)
            self.assertEqual(r2.returncode, 0, r2.stdout)
            self.assertIn("OK", r2.stdout)

    def test_cli_verify_fails_on_tampered_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = make_chain(tmp, 2)
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            obj = json.loads(lines[1])
            obj["outputs"] = {"tx_hash": "0x" + "aa" * 32}
            lines[1] = json.dumps(obj, sort_keys=True) + "\n"
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            r = self.run_cli("verify", "--chain", path)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("FAIL at seq 2", r.stdout)

    def test_cli_export_prints_json_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = make_chain(tmp, 2)
            r = self.run_cli("export", "--chain", path)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(r.stdout)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["seq"], 1)
            self.assertEqual(data[1]["seq"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
