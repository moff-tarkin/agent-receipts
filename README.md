# Agent Receipts

**Verifiable, permanent records of what an AI agent actually did.**

An autonomous agent that mints, mines, claims and runs inference leaves no
auditable trail by default: you either trust its word, or you re-derive
everything from chain explorers by hand. Agent Receipts fixes that. Every
action becomes a signed-by-hash JSON receipt, chained to the previous one, so
anyone can verify the whole history offline — and the chain tip can be
anchored to Arweave, where it lives permanently.

Built for HackerNoon's **Decentralize AI Hackathon, Round 2**
(deadline February 27, 2027). Python, standard library only, no dependencies.

## Why it matters

- **Verifiable AI.** A receipt is not a claim, it is a checkable record: the
  transaction hash, the nonce, the amounts are all in the receipt, and the hash
  chain proves nothing was edited after the fact. If a receipt is tampered
  with, `verify` names the exact sequence number where it breaks.
- **Permanent storage.** The chain tip (hash + receipt count) is bundled into
  an anchor document ready for Arweave. Once anchored, the record is immutable
  and publicly accessible indefinitely — model outputs, provenance records and
  agent history that cannot be taken down or altered.
- **Data sovereignty.** The agent (and its owner) holds the records. No
  platform account, no central database, no permission needed to prove what
  happened. Verification is local and offline.

## The format

One JSON object per action, one per line in a `.jsonl` chain file. Fields:

| Field | Meaning |
|---|---|
| `version` | Format version (`1`). |
| `seq` | Sequence number, starting at 1. |
| `timestamp` | ISO 8601 UTC, e.g. `2026-11-26T09:26:00Z`. |
| `agent_id` | Public agent identifier, e.g. `tarkin.ai`. |
| `action` | `mint`, `mine`, `claim`, or `inference`. |
| `inputs` | Contract address, function, arguments, chain, wallet. |
| `outputs` | Transaction hash, token id, amounts, balances. |
| `model` / `params` | Model name and parameters for `inference`; `null` otherwise. |
| `prev_hash` | Previous receipt's `hash` (64 zeros for `seq` 1). |
| `hash` | SHA-256 of the canonical JSON of all other fields (keys sorted, no whitespace). |

Full spec: [`FORMAT.md`](FORMAT.md).

## CLI usage

```bash
# Record a new action (computes seq, prev_hash and hash for you)
python3 receipts.py record --type mine \
  --input '{"contract": "0x7E2DA878217EB995F9e5d36eD32c9Cea52442681", "function": "mine()", "nonce": 72726998148}' \
  --output '{"tx_hash": "0xad9f...", "reward": "+73.62327807 PEARL"}' \
  --chain receipts.jsonl

# Verify the whole chain
python3 receipts.py verify --chain receipts.jsonl
# OK: chain OK: 3 receipts, tip 9f2c...

# Inference action with model info
python3 receipts.py record --type inference \
  --input '{"prompt": "summarise this contract"}' \
  --output '{"summary": "..."}' \
  --model "llama-3-70b" --params '{"temperature": 0.2}' \
  --chain receipts.jsonl

# Export the chain as a single JSON array (for the article / demo)
python3 receipts.py export --chain receipts.jsonl

# Prepare an Arweave anchor document (dry-run: nothing is uploaded)
python3 receipts.py anchor --chain receipts.jsonl
# Optional read-only gateway reachability check (GET only, never POST):
python3 receipts.py anchor --chain receipts.jsonl --gateway https://arweave.net
```

`verify` exits `0` when the chain is intact and non-zero when it is not,
printing the first failing `seq` and the reason (hash mismatch, broken
`prev_hash` link, or out-of-order `seq`).

## Arweave anchoring

`anchor` bundles the chain tip hash and receipt count into `anchor.json`
with suggested Arweave tags (`App-Name: agent-receipts`, `Tip-Hash`, …) and
prints the steps to upload it. **Anchoring is dry-run by default: nothing is
uploaded and no AR is spent.** A real upload needs an Arweave wallet funded
with AR (cost scales with data size — a small anchor document is a few
hundredths of an AR at most, but check the live price before uploading), then:

1. `POST https://arweave.net/tx` with the signed transaction (or the arweave-js SDK).
2. Confirm with `GET https://arweave.net/tx/<txid>/status`.
3. Record the Arweave txid back into the chain as an anchor receipt.

## Demo

`demo.py` builds a chain from three real, public, already-verified BSC
actions by wallet `0x7430Fb7D8a9d252Aa40f05483247a45B73636143`
(agent `tarkin.ai`) on 2026-11-26 — an AURA check-in claim (+170 AURA), a
Fateborn Mutant #33 mint, and a PEARL day-24 mine (nonce 72726998148,
+73.62327807 PEARL) — then verifies the chain:

```bash
python3 demo.py
python3 receipts.py verify --chain demo-chain.jsonl
cat demo-output.txt
```

## Tests

```bash
python3 test_receipts.py
```

Covers hash recomputation, end-to-end chain verification, tampering with a
receipt's outputs (fails at the right `seq`), tampering with a stored hash,
reordering (breaks the `prev_hash` linkage), and the CLI `record` / `verify` /
`export` round trip.

## Hackathon track mapping

| Hackathon track | How Agent Receipts fits |
|---|---|
| Verifiable / reproducible AI | Hash-chained receipts with on-chain evidence; offline verification. |
| Permanent model storage (Arweave) | Anchor document for the chain tip, ready for Arweave upload. |
| Open inference infrastructure | `inference` receipts record model, params and outputs per call. |
| Data sovereignty | The agent owner holds the records; no central platform required. |
| Decentralized GPU orchestration | Out of scope for v1 (receipts are compute-agnostic by design). |

## Limitations

- A receipt proves the *record* is intact, not that the recorded action
  happened: the evidence is the transaction hash inside the receipt, which
  anyone can check on-chain. A receipt with a fake tx hash verifies as a
  chain but fails as evidence — always check the tx hash.
- Anchoring is dry-run in v1; the Arweave upload step is manual.
- No identity or signature on receipts yet: `agent_id` is a public string,
  not a cryptographic identity. Signed receipts (Ed25519) are the natural v2.
- Timestamps are asserted by the recorder, not independently attested.
