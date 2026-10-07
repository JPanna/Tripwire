# DRAFT amendment A2 — CTF resolution timestamp enrichment (PROPOSED, not frozen)

Status: **PROPOSED.** The block-number scoping mechanism and the use of raw
Polygon block headers as an analysis enrichment are **owner-approved in
principle** (2026-10-07), subject to targeted independent review and the future
re-freeze (ADR-0026). The frozen preregistration (`PREREGISTRATION.md`, commit
`287afbe`, ADR-0018) is **not** edited. On acceptance this text becomes entry
A2 in `AMENDMENTS.md`, followed by an owner re-freeze ADR (together with A1 if
that is still pending).

Specifications tried so far: 1 (the frozen v3). Motivated by data structure
only: no outcome, event, resolution value or holdout data was inspected.

## 1. Gap

§5.3 defines **t_res(m)** as the block timestamp of the condition's resolution
event in the pinned `CTF/` layer. The pinned `CTF/resolutions.parquet` has no
timestamp column. Evidence:

- Footer schema (2026-10-07, schema only; no values, counts or statistics):
  `id` string, `condition_id` string, `oracle` string, `question_id` string,
  `outcome_slot_count` int64, `payout_numerators` list<string>.
- Dataset card `README.md` at revision
  `5aa1b9d52316a8b2e789e81c8ae42c7ed532e8aa` (git blob
  `a1146ecd8d7612b3c327e6a9633feb53e253c7b5`, verified against the manifest):
  - L196, L236, L260: CTF `id` is a composite on-chain record ID
    `chainId_blockNumber_logIndex` (example `137_35896903_143`);
  - L232, L269, L272: each `resolutions` row is one `ConditionResolution`
    event log from the Gnosis Conditional Tokens contract on Polygon;
  - L241: `payout_numerators` is the payout distribution array
    (`['1','0']`: first outcome won; the "e.g. YES" is illustrative only);
  - L259: `block_timestamp` is present only in the trade layers, not `CTF/`.

t_res is therefore not computable from the pinned dataset alone.

## 2. Replacement text for §5.3, first bullet

> - **t_res(m)** = the timestamp (UTC epoch seconds) of the Polygon block that
>   contains the condition's `ConditionResolution` record in the pinned
>   `CTF/resolutions.parquet`, obtained as follows.
>   1. **Identity.** `id` must consist of exactly three `_`-separated fields of
>      ASCII decimal digits (`[0-9]+`; no sign, whitespace or other
>      characters), read as integers (chainId, blockNumber, logIndex). Leading
>      zeros are not rejected on their own; the canonical identity of a record
>      is the integer triple. chainId must equal **137** (Polygon PoS) and must
>      agree with the RPC endpoint's `eth_chainId`. blockNumber and logIndex
>      are non-negative integers within the range the chain can produce.
>   2. The resolution event's existence and identity, `condition_id`,
>      `outcome_slot_count` and `payout_numerators` come from the pinned CTF
>      row only, never from RPC or metadata.
>   3. The block header is obtained with read-only JSON-RPC
>      `eth_getBlockByNumber(blockNumber, false)`; **t_res(m)** = the returned
>      header's `timestamp`.
>   4. **Fail closed.** A malformed or non-canonical identity, a wrong chain
>      id, a missing block, a returned block number that differs from the
>      request, a malformed block hash, an invalid timestamp, a timestamp on the
>      wrong side of the record's scope, two records with the same canonical
>      identity, more than one resolution record for one `condition_id`, or
>      invalid required payout data (not non-negative decimal integers, length
>      ≠ `outcome_slot_count`, or sum 0) **aborts the entire load**. A failed
>      record is never dropped and never treated as unresolved.
>   - If a condition has no resolution record, t_res = +∞ (unresolved),
>     unchanged.

## 3. Replacement text for §2.2, first bullet

> - **Raw Polygon logs** (V1 CTF Exchange, ConditionalTokens): validation only
>   (§7), never analysis variables. **Exception (A2):** Polygon **block
>   headers** may be used as an analysis enrichment solely to translate the
>   block number of a lifecycle event already identified in the pinned `CTF/`
>   dataset into its block timestamp (§5.3). No other chain data becomes an
>   analysis variable.

## 4. Holdout scoping of the all-date CTF file (§6, §11)

- **Boundary block B\*** = the first Polygon block whose timestamp is at or
  after 2025-10-08T00:00:00Z (1759881600). It is found from block headers and
  verified on every run by the headers of B\*−1 and B\*:
  ts(B\*−1) < 1759881600 ≤ ts(B\*). Only these two boundary headers (and those
  of the search) may be queried to establish it.
- **Precondition (open):** before B\* is relied on, authoritative Polygon/Bor
  documentation must be cited showing that block timestamps are ordered by
  block number (strictly increasing, or at least non-decreasing) over the
  relevant historical period. Not yet verified.
- A resolution record is **pre-holdout** iff blockNumber < B\*, and
  **holdout-side** iff blockNumber ≥ B\*.
- A dedicated scoped loader (the only CTF row reader, inside `r0.rawread`)
  reads `id` first, scopes by block number, and returns only in-scope records.
  During pre-holdout processing no individual holdout-side resolution block is
  ever queried; every in-scope header must have ts < 1759881600 (checked).
  Out-of-scope values may be decoded transiently in loader memory (Parquet row
  groups cannot be skipped on string `id` statistics) but are never returned,
  logged, counted or written.
- Nothing is lost for exploration: τ₀ ≤ 2025-09-30T23:59:59Z and h ≤ 60 min, so
  every t_res that can affect an exploration outcome is before
  2025-10-01T01:00Z, inside the pre-holdout scope.
- Holdout-side headers are fetched only by the authorized holdout run at the
  frozen commit.

## 5. Header cache and reproducibility

- During development: an operational header cache (Git-ignored), entries
  keyed by block number with chain id, block number, block hash and timestamp
  (plus retrieval time and a provider label; never the credential).
- At the analysis freeze: an **immutable snapshot** of the headers used,
  its SHA-256 and B\* (with both boundary headers) are pinned in the freeze
  commit. No hash of a still-changing cache is pinned.

## 6. §7 K0 additions

- **Exact-log verification:** for each sampled resolution, the log at
  (blockNumber, logIndex) must be a `ConditionResolution` event emitted by the
  verified ConditionalTokens contract, with the same conditionId and
  payoutNumerators as the pinned CTF row; t_res must equal that block's header
  timestamp.
- Verify the semantics of `eth_getBlockByNumber` (`timestamp` in seconds) and
  Polygon chain id 137 from current official documentation.
- The `outcome_seq` ↔ CTF payout-slot mapping remains **UNRESOLVED —
  VALIDATE AT K0** (unchanged).

## 7. §11 leakage checklist, new row

| Risk | Mitigation |
| --- | --- |
| Holdout-period resolutions inside the all-date `CTF/resolutions.parquet` | Scoped loader: scope from block number vs. pinned B\*; only in-scope records returned; no RPC query for holdout-side resolution blocks before the holdout run; fail closed on any inconsistency |

## 8. Unchanged

The R0 hypothesis; event construction and selection (§4); the delayed base;
SSTR (§5.1) except that the already-defined t_res becomes computable; v(m)
(payout numerator ÷ sum of numerators); the periods and holdout protocol (§6);
the statistics (§8); thresholds; the decision rules (§9). Metadata
(`resolved_at`, `winning_outcome_label`, `resolution_status`) is never used for
t_res or v(m). `CTF/preparations.parquet` is not required for R0 unless K0
establishes a concrete need.
