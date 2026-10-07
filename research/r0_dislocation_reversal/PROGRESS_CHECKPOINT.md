# R0 progress checkpoint — 2026-10-07

A record of where R0 stands at the end of the 2026-10-07 session. It changes
nothing: the governing texts are `docs/RISK_INVARIANTS.md`,
`PREREGISTRATION.md` (frozen), `docs/DECISIONS.md` and `DATA_ACCESS.md`.

## 1. Project state and architecture

- Milestone M0 (documentation) is done. R0, the "ungated anomalous-flow
  short-horizon reversal" (UAFR) alpha scout, is in implementation Stages A–C
  only (ADR-0020): project foundation, dataset listing and pinning, schema and
  exploration-only metadata inspection.
- Code lives in `research/r0_dislocation_reversal/`:
  - `r0/`: `hub.py` (read-only HF client), `manifest.py` (classification,
    placement authority), `rawread.py` (the only Parquet reader; holdout
    guard), `integrity.py`, `paths.py`, `periods.py`, `schema.py`, `roles.py`,
    `vocab.py`;
  - `scripts/00_fetch.py` (list / pin / download / verify) and
    `scripts/01_schema.py` (schema, vocab, domain checks);
  - `tests/` (330 tests; pytest + Ruff clean at `e148077`).
- Tooling: Python 3.12, uv, Polars, PyArrow (ADR-0009, ADR-0019). Data root
  `data/` is Git-ignored; no data is in Git.

## 2. Frozen baseline and decisions

- Preregistration v3 frozen at `287afbe` (ADR-0018, "r0-freeze-v1").
  `PREREGISTRATION.md` is byte-identical to `287afbe`. Note: ADR-0018 says the
  freeze commit is tagged `r0-freeze-v1`, but no such Git tag exists locally or
  on `origin` (checked 2026-10-07); creating it is an owner action.
- Accepted: ADR-0001…0010, 0013, 0014, 0016–0025 (0012 superseded by 0015;
  0015 accepted with amendments by 0016/0017). Proposed: ADR-0011 (agent),
  ADR-0026 (A2, owner-approved in principle).
- Key access rules: PRE-HOLDOUT (rows < 1759881600 = 2025-10-08T00:00:00Z) is
  an access-control notion only; research uses EXPLORATION 2025-01-01 ..
  2025-09-30 (ADR-0022). Holdout rows only via the guard (ADR-0021). Schema
  reports are holdout-blind: no row counts, row-group counts, byte volumes or
  column statistics (ADR-0025).

## 3. Reviews

- Stages A–C: accepted by independent (Codex) review; not to be reopened.
- ADR-0025 (holdout-blind schema report), `d8ce40e`: in force.
- A2 preparation (manifest v3, CTF scope authority, Stage C CTF roles),
  `e14807727339c31507223185e83829d42afa2014`: **accepted** by Codex ("ACCEPT A2
  PREPARATION", no BLOCKER/MAJOR findings) and approved for metadata-only
  real-data inspection. The A2 *amendment* itself remains PROPOSED.

## 4. Pinned data and manifest

- Dataset: Hugging Face `TimeSeventeen/Polymarket-v1` (CC-BY-4.0), revision
  `5aa1b9d52316a8b2e789e81c8ae42c7ed532e8aa`. Dataset card `README.md` git
  blob `a1146ecd8d7612b3c327e6a9633feb53e253c7b5` (verified).
- `DATA_MANIFEST.json`/`.md`: manifest v3, written 2026-10-07T22:10:51Z by
  `00_fetch.py --list --revision 5aa1b9d… --write-manifest` (footer byte
  ranges of the 1,248 `daily_aligned` files only; 76,004,429 bytes fetched).
  Accepted by `load_authoritative_manifest`; every entry re-classifies
  identically from its evidence.
- Placement: all 1,248 `daily_aligned` files footer-verified; every file's
  footer day equals its filename date; no straddling files; no unresolved
  files; no missing days 2024-12-30 → 2026-04-28.

| Part | Files | Bytes |
| --- | ---: | ---: |
| Trailing 2024-12-30..31 | 2 | 5,350,807 |
| Exploration 2025-01-01..09-30 | 273 | 514,185,134 |
| Embargo 2025-10-01..07 | 7 | 26,733,569 |
| **Pre-holdout total** (`--download pre-holdout --approve-bytes`) | 282 | **546,269,510** |
| Holdout 2025-10-08..2026-04-28 (raw cache only, after approval) | 203 | 12,457,383,100 |
| `CTF/resolutions.parquet` (all-dates; scope `pending-A2-ctf-loader`; download disabled) | 1 | 92,752,280 |
| Card `README.md` | 1 | 24,460 |
| Minimum acquisition (card + CTF + pre-holdout) | | 639,046,250 |

`CTF/preparations`, `splits`, `merges`, `redemptions`, `OrderFilled/` and
`daily_aligned_multi/` are not needed. Nothing has been downloaded.

## 5. Schema findings (`SCHEMA_REPORT.json`/`.md`, remote footers only)

- `daily_aligned`: one schema in all 485 required files (exploration,
  embargo, holdout): no drift, no type changes. 24 columns: `asset_id`
  large_string, `block_timestamp` int64, `price` double, `maker`, `taker`,
  `taker_direction` large_string, `usdc_amount`, `fee_usdc` double,
  `condition_id` large_string, `outcome_seq` int64, `neg_risk`, `category`,
  `category_refined`, `outcome_label`, `winning_outcome_label`,
  `resolution_status` large_string, `taker_base_fee`, `maker_base_fee`
  double, `opens_at`, `close_at`, `resolved_at` timestamp[us, tz=UTC],
  `market_slug` large_string, `p_event` double, `D` int8.
- FOUND: condition_id, block_timestamp, p_event, D, outcome_seq, usdc_amount,
  price, maker, taker, taker_direction, category.
- `CTF/resolutions`: `id` string, `condition_id` string, `oracle` string,
  `question_id` string, `outcome_slot_count` int64, `payout_numerators`
  list<string>. No timestamp column (card L259); `id` =
  `chainId_blockNumber_logIndex` (card L196, L236, L260).

## 6. Unresolved required roles (schema exit 3)

- **token_id**: candidate `asset_id` (card: "Outcome token id traded in this
  fill"). Owner must confirm or reject; meaning validated at K0.
- **shares**: no share-quantity column in `daily_aligned` (`token_amount` is
  only in `OrderFilled/`). Owner must state `shares=NONE` (§3 `usdc_amount /
  price` fallback) or name a column.

## 7. Other pending decisions and amendments

- `slug`: candidate `market_slug` (owner confirmation).
- `scheduled_end`: candidate `close_at` (named by the owner; the tool's hint
  does not match it). Whether it is the *originally scheduled* end is
  unvalidated (frozen metadata snapshot, card L264/L310).
- `tags` and `question`: absent. S_short (§4.3) then needs either category
  (or `category_refined`) + slug only, or one pinned Gamma snapshot (§2.2).
- `neg_risk`: large_string, not bool/int (optional role).
- Semantic validation pending at K0: p_event and D definitions,
  taker_direction sign, outcome_seq ↔ CTF payout-slot mapping, token → (condition, slot).
- **A1** (S_short classifier, `proposals/S_SHORT_AMENDMENT_DRAFT.md`): draft;
  must be revised for the missing question/tags; not frozen.
- **A2** (`proposals/A2_CTF_RESOLUTION_TIME_DRAFT.md`, ADR-0026): PROPOSED;
  t_res from the Polygon block header of the block in the CTF `id`; scoping by
  block number vs. B\*; fail closed; K0 exact-log verification. Open: cite
  authoritative Polygon/Bor documentation on timestamp ordering before
  relying on B\*.

## 8. Not implemented and not authorized

- Polygon RPC client, A2 scoped CTF loader, header cache, B\* determination.
- Any download (pre-holdout, holdout, CTF); CTF downloads are disabled in code.
- vocab and domain checks; K0; event detection (Stage D, and not before the
  S_short amendment is re-frozen); outcomes, SSTR, statistics; any holdout read.
- Freezing A1/A2; role confirmations; any change to `PREREGISTRATION.md`.
- Any execution, order, wallet or trading code (never in R0).

## 9. Recommended next steps (each needs owner authorization)

1. Owner decisions on token_id and shares; then on slug, scheduled_end,
   S_short metadata source (category/slug vs. Gamma snapshot) and neg_risk.
2. Re-run `01_schema.py schema --confirm …` with those decisions (remote).
3. Approve `--download pre-holdout --approve-bytes 546269510` (and the card).
4. Exploration-only vocab and domain checks; revise and audit A1.
5. Verify Polygon/Bor timestamp ordering; then implement the A2 RPC client and
   scoped CTF loader for independent review; enable the CTF download only after
   acceptance.
6. K0 preparation; re-freeze with A1/A2 before any event detection.

## 10. Provenance

- Code: branch `research/r0-uafr`; reports generated at
  `e14807727339c31507223185e83829d42afa2014`; this checkpoint is committed on
  top of it.
- Data: `TimeSeventeen/Polymarket-v1` @ `5aa1b9d52316a8b2e789e81c8ae42c7ed532e8aa`,
  endpoint `https://huggingface.co`; footers read through the CDN host
  `us.aws.cdn.hf.co` (allowed by the environment's network policy).
- Generated files: `DATA_MANIFEST.json/.md` (2026-10-07T22:10:51Z),
  `SCHEMA_REPORT.json/.md` (2026-10-07T22:11:50Z). They hold no row values, no
  credentials, no outcomes and no row/row-group counts; the only holdout-derived
  values are file placement (per-file footer block-timestamp min/max, sizes,
  hashes), which ADR-0025 authorizes.
