# R0 progress checkpoint — PAUSED 2026-10-10

Durable handoff for resuming R0. It changes nothing: the governing texts are
`docs/RISK_INVARIANTS.md`, `PREREGISTRATION.md` (frozen), `docs/DECISIONS.md`
and `DATA_ACCESS.md`. History: first written 2026-10-07, updated 2026-10-08,
rewritten 2026-10-10 as the pause checkpoint.

## 0. Pause status and the next exact action

- **Paused** until Codex review capacity is available again.
- Last completed commit: `1b7273f6861a6020e11814d1a1832a16378126ae` (A1 audit
  protocol v1.1 + labelling rubric).
- **Next exact action:** run ONE final, targeted Codex diff review of
  base `2862cf7fddc25fc9a2d1edf0f0a77578a3f558ea` → head
  `1b7273f6861a6020e11814d1a1832a16378126ae`.
  - Scope: confirm closure of the two original MAJOR findings (conservative
    UNRESOLVED scoring; binding S4/S5 census gates). Assess only
    `provisional/a1_audit/AUDIT_PROTOCOL.md` (v1.1) and
    `provisional/a1_audit/LABELING_RUBRIC.md`.
  - Bound wording to clarify in that review (no file changes were made):
    protocol §7 calls 384 and 580 "exact hypergeometric 95% upper bound[s]".
    They are the upper endpoints of **two-sided** 95% intervals (one-sided
    97.5%). Codex's **312 / 495** are **one-sided** 95% upper bounds. Both pairs
    are correct and were re-checked exactly (2026-10-10, synthetic arithmetic,
    N = 21,152 S7 markets, n = 200 sampled):

    | Observed misses | One-sided 95% upper | Two-sided 95% upper endpoint |
    | --- | ---: | ---: |
    | 0 of 200 | 312 | 384 |
    | 1 of 200 | 495 | 580 |

- **If Codex accepts**, the NEXT, separate owner decision is whether to
  authorize blinded labelling of the 865 worksheet markets. Labelling must not
  start automatically.
- If Codex finds problems: fix only what it names, in the two protocol files,
  and re-review.

## 1. Project state and architecture

- R0, the "ungated anomalous-flow short-horizon reversal" (UAFR) alpha scout,
  is a preregistered, holdout-protected exploratory study. M0 (documentation)
  is done. Implementation is limited to Stages A–C (ADR-0020): foundation,
  dataset pinning, schema and exploration-only metadata inspection.
- Code in `research/r0_dislocation_reversal/`:
  - `r0/`: `hub.py` (read-only HF client), `manifest.py` (classification and
    placement authority), `rawread.py` (the only Parquet reader; holdout guard),
    `integrity.py`, `paths.py`, `periods.py`, `schema.py`, `roles.py`,
    `vocab.py`;
  - `scripts/00_fetch.py` (list/pin/download/verify) and `scripts/01_schema.py`
    (schema, vocab, domain checks);
  - `tests/`: 330 tests; pytest and Ruff clean at `1b7273f`.
- Tooling: Python 3.12, uv, Polars, PyArrow (ADR-0009, ADR-0019). SciPy is not
  installed; exact bounds were computed in plain Python. `data/` is
  Git-ignored; no data is in Git.

## 2. Frozen baseline and decisions

- Preregistration v3 frozen at `287afbe` (ADR-0018, "r0-freeze-v1").
  `PREREGISTRATION.md` is byte-identical to `287afbe` (re-checked 2026-10-10).
  ADR-0018 says the freeze commit is tagged `r0-freeze-v1`, but no such Git tag
  exists locally or on `origin`; creating it is an owner action.
- Accepted ADRs: 0001–0010, 0013, 0014, 0016–0025 (0012 superseded by 0015;
  0015 accepted with amendments by 0016/0017). Proposed: ADR-0011 (agent) and
  ADR-0026 (A2; owner-approved in principle).
- Access rules:
  - PRE-HOLDOUT (rows < 1759881600 = 2025-10-08T00:00:00Z) is access control
    only; research uses EXPLORATION 2025-01-01 .. 2025-09-30 (ADR-0022).
  - Holdout rows only via the guard (ADR-0021).
  - Schema and Stage C reports are holdout-blind: no row counts, row-group
    counts, byte volumes or column statistics (ADR-0025).

## 3. Independent review log

| Item | Commit | Codex result |
| --- | --- | --- |
| Stages A–C | up to `671ced2` | ACCEPTED (not to be reopened) |
| Holdout-blind schema report (ADR-0025) | `d8ce40e` | in force |
| A2 preparation (manifest v3, CTF scope authority, Stage C CTF roles) | `e14807727339c31507223185e83829d42afa2014` | ACCEPT A2 PREPARATION (no BLOCKER/MAJOR); A2 amendment itself still PROPOSED |
| Provisional A1 audit package | `2862cf7fddc25fc9a2d1edf0f0a77578a3f558ea` | ACCEPT AFTER SPECIFIED FIXES: 2 MAJOR, 0 BLOCKER; classifier, sampling and worksheet passed |
| Fixes for the 2 MAJOR findings (protocol v1.1, rubric) | `1b7273f6861a6020e11814d1a1832a16378126ae` | **PENDING**: final targeted diff review (§0) |

Claude's own verification at `1b7273f`: 17 synthetic scoring and acceptance
checks pass, 330 tests pass, lint clean, worksheet hash unchanged. These are
not independent review results. **The classifier audit is NOT yet accepted for
real labelling.**

## 4. Pinned data, manifest and acquisition

- Dataset: Hugging Face `TimeSeventeen/Polymarket-v1` (CC-BY-4.0), revision
  `5aa1b9d52316a8b2e789e81c8ae42c7ed532e8aa`; card `README.md` blob
  `a1146ecd8d7612b3c327e6a9633feb53e253c7b5` (verified).
- `DATA_MANIFEST.json`/`.md`: manifest v3, written 2026-10-07T22:10:51Z. All
  1,248 `daily_aligned` files are footer-placed; footer day = filename date for
  every file; no straddling, unresolved or missing days (2024-12-30 →
  2026-04-28).

| Part | Files | Bytes |
| --- | ---: | ---: |
| Trailing 2024-12-30..31 | 2 | 5,350,807 |
| Exploration 2025-01-01..09-30 | 273 | 514,185,134 |
| Embargo 2025-10-01..07 | 7 | 26,733,569 |
| **Pre-holdout total** | 282 | **546,269,510** |
| Holdout 2025-10-08..2026-04-28 (not acquired) | 203 | 12,457,383,100 |
| `CTF/resolutions.parquet` (all-dates; scope `pending-A2-ctf-loader`; download disabled in code) | 1 | 92,752,280 |

- **Acquisition (2026-10-08, owner-authorized):**
  `00_fetch.py --download pre-holdout --approve-bytes 546269510` and
  `--verify --part pre-holdout` both exited 0: 282 files SHA-256-verified,
  0 mismatches. No holdout, CTF, `OrderFilled/` or `daily_aligned_multi/` file
  was acquired.
- **The raw cache is ephemeral:** it lives only in a cloud container, is not in
  GitHub, and is gone when the container is reclaimed. A new session must
  re-download and re-verify before any row read (owner Option 1).
- Network: `huggingface.co` and `us.aws.cdn.hf.co` are allowed. `arxiv.org`,
  `docs.polymarket.com` and `ideas.repec.org` are blocked by this
  environment's policy and were not bypassed.

## 5. Schema and role mappings

- `daily_aligned`: one schema in all 485 required files, no drift. 24 columns
  (see `SCHEMA_REPORT.md`), including `close_at` timestamp[us, UTC],
  `category`, `category_refined`, `market_slug`. No `question` or `tags`.
- Stage C schema inspection cleared (2026-10-08, exit 0) with these owner
  confirmations:

| Role | Mapping | Status |
| --- | --- | --- |
| token_id | `asset_id` | CONFIRMED |
| shares | `NONE` (no share column; frozen §3 fallback `usdc_amount / price`; quantity, units and fees are K0 questions) | CONFIRMED_ABSENT |
| slug | `market_slug` | CONFIRMED |

- `CTF/resolutions`: `id`, `condition_id`, `oracle`, `question_id`,
  `outcome_slot_count`, `payout_numerators`. No timestamp column; `id` =
  `chainId_blockNumber_logIndex`.

## 6. Exploration-only metadata investigations (complete)

All read only exploration-period metadata through the guarded reader. No
prices, flows, outcomes, durations or holdout data were used.

| Report | Commit | Key findings |
| --- | --- | --- |
| `S_SHORT_VOCAB_FINDINGS.md` | `32f2502` | 44,275 exploration markets. `category` is one tag-like label per market (528 values). `DOGE` = US government, not Dogecoin. Format labels (Up or Down, 1H, …) carry no crypto meaning by name |
| `S_SHORT_METADATA_INVESTIGATION.md` | `27d3f3c` | `category_refined`: 8 coarse, provider-derived values with contradictions (DOGE→Crypto; crypto Daily→Sci-Tech). Owner decision: audit/challenge signal only |
| `S_SHORT_A1_EVIDENCE_GATE.md` | `22c8241` | `close_at` matches slug-encoded schedules exactly in samples (15-min end, ET hour end, multistrike slug time, daily 12:00 UTC→12:00 ET); 99.95% whole-minute values. It looks scheduled-type but is NOT verified as the original scheduled end; some deadline markets disagree with their slugs |

## 7. Provisional A1 audit package (`provisional/a1_audit/`)

Status: PROVISIONAL, NOT FROZEN, NOT run, NOT accepted.

| File | Commit | Notes |
| --- | --- | --- |
| `CANDIDATE_CLASSIFIER_DRAFT.toml` | `2862cf7` | `a1-candidate-v1`: exact category tokens (crypto, crypto prices, bitcoin, ethereum, solana, xrp, ripple, dogecoin, cardano, ltc, eth, sol, fartcoin, hyperliquid, pepe) OR bounded asset-specific slug patterns; `DOGE` and format/UI labels excluded; 28 undecided labels |
| `select_audit_sample.py` | `2862cf7` | deterministic; guarded reader; exploration rows only; salts `a1-audit-v1` and `a1-audit-v1-worksheet` |
| `A1_AUDIT_WORKSHEET_BLINDED.csv` | `2862cf7` | 865 rows; review id, category, slug, two blank labels; SHA-256 `30b480ee1e93c4351a01767e7280b525319a2e04ceed8069818a49aadb3fae1a` |
| `AUDIT_PROTOCOL.md` | `1b7273f` (v1.1) | conservative UNRESOLVED scoring; binding S4/S5 census dispositions (D1/D2/D3); systematic-family gate; single-revision procedure; honest uncertainty reporting |
| `LABELING_RUBRIC.md` | `1b7273f` | A = crypto-related (PRIMARY), B = crypto price/direction (descriptive); YES / NO / UNRESOLVED criteria |
| `AUTHOR_INQUIRY_DRAFT.md` | `2862cf7` | the dataset-author email text; its header still says "NOT SENT" because it predates sending (see §8) |

- Strata (populations / selected): S1 12,070/100 · S2 493/100 ·
  S3 10,171/100 · S4 201/201 (census) · S5 14/14 (census) · S6 174/150 ·
  S7 21,152/200. Total 44,275 / 865.
- The unblinded key (`data/exploration/inspection/a1_audit_key.csv`, SHA-256
  `6dd3ff964045dd14498197eeb9ff71b27e44205abc74c12d38f17832485a202b`) is
  Git-ignored and ephemeral. It is regenerated byte-identically by the script
  after re-downloading and re-verifying the pre-holdout part.
- Gates (protocol v1.1), summarised:
  - S1/S3 need adjudicated A = YES ≥ 98/100; S2 ≥ 95/100;
  - S6 needs YES + UNRESOLVED ≤ 3/150; S7 ≤ 1/200;
  - UNRESOLVED ≤ 5% per sampled stratum;
  - every S4/S5 possible miss needs D1 or D2;
  - families of 2 or more related errors need a verified correction;
  - at most one revision round.

## 8. External inquiry

The owner has emailed the dataset authors, Boka Qin and Rui Yang, about:
- the source field of `close_at`;
- the metadata snapshot date;
- whether values could change after trading began;
- original as-created end times;
- whether the 4-hour multistrike slug time is the window's start or end.

**The reply is pending.** Until it arrives, `close_at` stays UNCONFIRMED as the
originally scheduled end, and the multistrike slug time is not interpreted.

## 9. Open decisions and amendments

- **A1** (S_short classifier; `proposals/S_SHORT_AMENDMENT_DRAFT.md`) and
  **A2** (CTF resolution time; `proposals/A2_CTF_RESOLUTION_TIME_DRAFT.md`,
  ADR-0026): both PROPOSED and UNFROZEN. A2 still needs authoritative
  Polygon/Bor documentation on block-timestamp ordering before B\* is relied
  on.
- S_short duration condition: blocked on `close_at` (§8).
- Undecided crypto-themed labels (28): decided per label after the S4 census.
- `neg_risk` is a string (optional role); the fee formula and the semantic
  checks of p_event, D, taker_direction, outcome_seq ↔ CTF slot and
  token → (condition, slot) are K0 questions.
- Missing `r0-freeze-v1` tag (§2).

## 10. Not done and not authorized

- No market labels, adjudication, classifier accuracy or classifier
  acceptance.
- No S_short membership or durations.
- No domain checks, K0, Stage D, event detection, SSTR, outcome or statistical
  analysis.
- No holdout or CTF data acquired or read.
- No Polygon RPC client, A2 loader or B\* determination.
- No change to `PREREGISTRATION.md`; no A1/A2 freeze.
- Never in R0: any execution, order, wallet or trading code.

## 11. Next steps after resumption (each needs owner authorization)

1. **Codex targeted diff review** `2862cf7` → `1b7273f` (§0).
2. If accepted: owner decision on blinded labelling of the 865 markets. If
   authorized, follow protocol v1.1 §3: primary review, second review,
   adjudication, then unblinding and scoring.
3. Apply the §4–§5 gates. At most one owner-approved revision round (§6 of the
   protocol); then, only if ACCEPTED, propose A1 for freezing.
4. Incorporate the authors' reply on `close_at` and the multistrike timestamps;
   decide the S_short duration definition.
5. A2: verify Polygon/Bor timestamp ordering, then implement the RPC client and
   scoped CTF loader for independent review.
6. K0 preparation; re-freeze with A1/A2 before any event detection.

## 12. Provenance

- Branch `research/r0-uafr`. Key commits: `287afbe` (freeze), `671ced2`
  (A–C), `d8ce40e` (ADR-0025), `e148077` (A2 preparation), `5e6455b`
  (manifest + schema), `f2237ff` (cleared mappings), `32f2502` (acquisition +
  vocab), `27d3f3c`, `22c8241` (metadata investigations), `2862cf7` (A1
  package), `1b7273f` (protocol fixes). This checkpoint is committed on top of
  `1b7273f`.
- Generated reports hold no row values, credentials, outcomes or row counts.
  The only holdout-derived values are manifest file placement (per-file footer
  block-timestamp min/max, sizes, hashes), as ADR-0025 authorizes.
