# Agent Receipts — format specification (v1)

A receipt is one JSON object describing a single action an AI agent performed.
Receipts are stored one per line in a `.jsonl` chain file, in sequence order.
Each receipt links to the previous one by hash, forming a tamper-evident chain:
editing any receipt breaks verification of that receipt and every receipt after it.

## Receipt fields

| Field       | Type            | Description |
|-------------|-----------------|-------------|
| `version`   | integer         | Format version. Currently `1`. |
| `seq`       | integer         | Sequence number in the chain. Starts at `1`, increments by 1. |
| `timestamp` | string          | When the action happened, ISO 8601 UTC, e.g. `2026-11-26T09:26:00Z`. |
| `agent_id`  | string          | Public agent identifier, e.g. `tarkin.ai`. |
| `action`    | string          | One of `mint`, `mine`, `claim`, `inference`. |
| `inputs`    | object          | What the action needed: contract address, function name, arguments, chain id, wallet. |
| `outputs`   | object          | What the action produced: transaction hash, token id, amounts, balances. |
| `model`     | string or null  | Model name for `inference` actions; `null` otherwise. |
| `params`    | object or null  | Model parameters for `inference` actions; `null` otherwise. |
| `prev_hash` | string          | SHA-256 hex of the previous receipt's `hash`. For `seq == 1`, 64 zero characters (`"0" * 64`). |
| `hash`      | string          | SHA-256 hex of this receipt (see below). |

## Hash algorithm

1. Take the receipt object **without** the `hash` field.
2. Serialise it as canonical JSON: keys sorted recursively, separators `,` and
   `:` (no whitespace), UTF-8 encoding, no trailing newline.
3. `hash = SHA-256(canonical_json)` as lowercase hex.

Example (Python):

```python
import hashlib, json
payload = {k: v for k, v in receipt.items() if k != "hash"}
digest = hashlib.sha256(
    json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    .encode("utf-8")
).hexdigest()
```

## Chain rules

- Receipts are appended in order; `seq` is always the previous `seq + 1`.
- `prev_hash` of receipt N is the `hash` of receipt N−1 (or 64 zeros for N = 1).
- A chain verifies when, for every receipt: `seq` matches its position,
  `prev_hash` matches the previous receipt's `hash`, and the recomputed hash
  matches the stored `hash`.
- Verification reports the **first** failing `seq` and the reason.
- Never edit a receipt in place. Corrections are new receipts that reference the
  earlier one (e.g. an `inputs.corrects_seq` field).

## Example receipt (real, from the demo chain)

```json
{"action":"claim","agent_id":"tarkin.ai","hash":"9ea7baa4bb3156581a6b3ca24caeaf6fed34e02691ba629b628e1d9f1e28ba21","inputs":{"args":{},"chain":56,"chain_name":"BSC","contract":"0x48F9373F0b62920CB34B63B18A84bd776A71B23a","function":"checkIn()","wallet":"0x7430Fb7D8a9d252Aa40f05483247a45B73636143"},"model":null,"outputs":{"balance_after":"980 AURA","day":7,"reward":"+170 AURA","streak":7,"tx_hash":"0x9483e83017acfa5b0104f179cfc7ddea9b82f00b26f26ea05326cb800c27d7a1"},"params":null,"prev_hash":"0000000000000000000000000000000000000000000000000000000000000000","seq":1,"timestamp":"2026-11-26T09:26:00Z","version":1}
```

The full demo chain (three real on-chain actions) is in `demo-chain.jsonl`.
