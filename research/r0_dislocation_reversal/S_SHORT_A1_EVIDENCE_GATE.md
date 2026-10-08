# S_short A1 evidence gate: close_at consistency, audit design, provenance (2026-10-08)

**Status: exploratory metadata evidence and a proposed (not executed) audit.**
No classifier evaluation, no S_short membership, no durations, no
first-trade comparisons, no prices or outcomes. A1, A2, the code and
`PREREGISTRATION.md` are unchanged. Follows `S_SHORT_VOCAB_FINDINGS.md` and
`S_SHORT_METADATA_INVESTIGATION.md`.

Owner direction recorded here: `category_refined` is audit-only, never an A1
condition. Explicit crypto labels and asset-specific slug patterns are
provisional candidates. Format labels are not unconditional crypto
indicators. `DOGE` is not Dogecoin. Ambiguous crypto-themed labels are
pending.

## Provenance

| Item | Value |
| --- | --- |
| Dataset | `TimeSeventeen/Polymarket-v1` @ `5aa1b9d52316a8b2e789e81c8ae42c7ed532e8aa`, manifest v3 |
| Files | the 282 verified pre-holdout `daily_aligned` files (re-verified 2026-10-08: 282 verified, 0 mismatches) |
| Rows | EXPLORATION only (`block_timestamp` 2025-01-01T00:00:00Z .. 2025-09-30T23:59:59Z) after a `Scope.PRE_HOLDOUT` read via `r0.rawread.read_rows`; no embargo or holdout rows |
| Columns read | `condition_id`, `block_timestamp` (filter only), `market_slug`, `close_at` |
| Method | scratch scripts outside the repo. Market-level tuples; samples are the first n markets of each slug stratum in SHA-256(`closeat-v1|condition_id`) order, so `close_at` plays no part in selection. Only offsets (`close_at` − slug-derived time) are reported, never absolute `close_at` values |
| Code commit | `27d3f3cf007fcbf11d04855247c8cb9e5d676f9e` (no code changes) |

## Task 1 — close_at consistency

**Presence and within-market consistency (all 44,275 exploration markets).**
44,262 markets have `close_at` and 13 are null. Every market has exactly one
`close_at` value and one slug. `close_at` is `timestamp[us, UTC]`. 99.95% of
the non-null values fall on a whole minute and 92.3% on a quarter hour. The
21 values that are not whole minutes belong to open-ended markets
(`will-btc-hit-100k-or-110k-first`, `btc-above-100k-till-2025-end`, …).

**Slug-encoded schedule versus close_at** (n = 50 per crypto stratum, 25 per
control; ET is America/New_York with DST):

| Stratum (candidates) | Slug time interpretation | Result |
| --- | --- | --- |
| 15 min `{asset}-up-or-down-15m-{unix}` (3,385) | window start = unix; end = unix + 15 min | **50/50: `close_at` = unix + 15 min exactly** (= window end) |
| hourly `{asset}-up-or-down-{mon}-{d}-{h}{am\|pm}-et` (10,522) | ET hour start; end = start + 1 h | **50/50: `close_at` = end of that ET hour exactly**, across EST/EDT dates |
| 4 h `{btc\|eth\|sol\|xrp}-multistrike-4h-{unix}-…` (4,502) | unix = start or end? | **50/50: `close_at` = the slug's unix time exactly**. Whether that time is the window start or end cannot be told from the slug alone |
| daily `{asset}-up-or-down-on-{mon}-{d}` (747) | slug date | **50/50 on one of two round conventions:** 12:00 UTC on the slug date (all sampled March–May markets, 16) or 12:00 ET (all sampled June–September markets, 34). This looks like a change of product convention in May/June |
| control: non-crypto slugs ending in an ISO date (7,338; mostly sports) | event date | 25/25: `close_at` is about 7–8 days after the slug date, at round clock times (00:00, 19:30, …) |
| control: non-crypto `will-…-by-{mon}-{d}` deadlines (353) | deadline date | 21/25 within ±2 days at round times (mostly 00:00 UTC or 12:00 UTC of the deadline date). Discrepancies: `…dnipro-oblast-by-april-30`: `close_at` about 61 days *before* the slug deadline; `…eric-adams-drop-out-by-september-30-183`: about 25 days before; `…openai-…-by-march-31-2026`: about 90 days before (an apparent +365-day case is only the parser's 2025 year assumption) |

**Interpretation (evidence, not proof).**
- `close_at` behaves like a **scheduled end field** (Gamma `endDate`-like),
  not like a recorded actual close (`closedTime`-like). It reproduces
  slug-encoded window ends exactly, its values are almost all round clock
  times, and the sports controls sit at a uniform "event + about one week"
  offset, which looks like a scheduling convention. A recorded close would
  scatter after resolution.
- For recurring crypto price markets (the likely S_short population) it
  agrees exactly with the schedule encoded in the slug, which was probably
  fixed at creation (inference; not documented).
- It is **not** always equal to the deadline stated in the slug. Three of 25
  deadline controls show `close_at` well before the slug deadline. That fits
  a market whose stated deadline changed (extended, re-slugged) while
  `close_at` did not, or the reverse. Either way, slug and `close_at` can
  disagree.

**Still unprovable** without the original metadata source or its history:
that `close_at` is the value at market creation; whether any market's value
was edited before the snapshot; the snapshot date; and for 4 h multistrike
markets, whether the encoded time is the start or the end of the interval.
Classification stands: **UNRESOLVED — ORIGINAL SCHEDULED END NOT VERIFIED.**
The evidence narrows the question but does not close it. A strong match is
not proof of an original value.

## Task 2 — Provisional A1 audit design (prepared, not run)

**Inputs** (exploration markets only; `category`, `market_slug`;
`category_refined` as a challenge signal only):
- T: exact match of the whole trimmed, casefolded `category` against the
  provisional crypto label list (Crypto, Crypto Prices, Bitcoin, Ethereum,
  Solana, XRP, Ripple, Dogecoin, Cardano, eth, sol, fartcoin, hyperliquid,
  pepe).
- R: the bounded asset-specific slug patterns (no bare `up-or-down`, no
  `doge`) from `S_SHORT_METADATA_INVESTIGATION.md` §C.
- U: undecided labels (Memecoins, Airdrops, Crypto Summit, MicroStrategy,
  Crypto Policy, coinbase, Stablecoins, Michael Saylor, Pump.Fun, tether,
  usdc; 172 markets).
- F: `category_refined` ∈ {Crypto, Price Action}.

**Non-overlapping strata** (assigned in this order; samples are the first n
markets in SHA-256(`a1-audit-v1|condition_id`) order):

| Stratum | Definition | n |
| --- | --- | ---: |
| S1 | T ∧ R | 100 |
| S2 | T ∧ ¬R | 100 |
| S3 | ¬T ∧ R | 100 |
| S4 | ¬T ∧ ¬R ∧ category ∈ U | census (≤ 172) |
| S5 | ¬T ∧ ¬R ∧ category = `DOGE` | census (14) |
| S6 | remaining ∧ F (refined says crypto, the rule does not) | 150 |
| S7 | remaining ∧ ¬F | 200 |

**Manual labels** (from `category` + `market_slug` only; the item list is
shuffled and shows no stratum, T/R/F flags or keyword-screen hits; each
answer is YES, NO or UNRESOLVED; never guess):
- **A. Crypto-related**: the subject is a cryptocurrency, token, crypto
  protocol, exchange or crypto company, or crypto policy, or a person acting
  in that role.
- **B. Crypto price/direction**: resolution depends on the price, level,
  direction, market cap or dominance of a crypto asset or pair. B ⊂ A.
- A second reviewer re-labels every UNRESOLVED item and a 10% random subset;
  disagreements are logged, not silently resolved.

The frozen §4.3 metadata condition ("category/tags mark it as crypto, or a
frozen regex matches its question or slug") targets **A**. B is reported to
show what the duration condition must still separate. The ≤ 24 h condition
is not part of this audit.

**Acceptance thresholds** (fixed before any evaluation):
1. Precision on A: S1 ≥ 98/100, S3 ≥ 98/100, S2 ≥ 95/100 confirmed A = YES.
   Any systematic false-positive family (≥ 2 items from one label or slug
   family) must be fixed, whatever the rate.
2. Misses: S6 ≤ 3/150 and S7 ≤ 1/200 items with B = YES. Any missed crypto
   price slug family (≥ 2 items) must be added as a bounded pattern.
3. UNRESOLVED ≤ 5% in every stratum; otherwise the labelling source is
   insufficient and the owner decides.
4. S4 and S5 censuses: the owner decides inclusion per label from the census.
   `DOGE` stays excluded unless the census contradicts the evidence.
5. At most one logged revision round. After a revision, only the affected
   strata are re-audited, with a new salt (`a1-audit-v2`). Then A1 is frozen.

## Task 3 — close_at provenance

- Documented (pinned card, blob `a1146ec…`): L150 "`close_at` | timestamp |
  Market close time."; L264 market time fields "come from the frozen market
  metadata layer"; L310 "static snapshot". No source field and no snapshot
  date are named.
- Owner-supplied, not verified here (arxiv.org is blocked by this
  environment's network policy and was not bypassed): the paper §3.1 joins
  trades to one frozen metadata snapshot; Table 16 documents
  `category_refined` as a harmonisation of metadata keywords/slugs; Price
  Action covers Up/Down and high-frequency interval markets; the paper does
  not establish that `close_at` was scheduled at creation.
- docs.polymarket.com is also blocked. Search summaries list both Gamma
  `endDate` and `closedTime`; neither is mapped to `close_at` in any source.
- Conclusion: the documentation does not determine whether `close_at` is
  Gamma `endDate`, `closedTime` or another field. The data behave like
  `endDate` (Task 1), which is still not proof.

**Proposed question for the dataset authors** (not sent; needs owner
authorization):

> For Polymarket-v1 (revision 5aa1b9d5…), which upstream field populates
> `daily_aligned.close_at` (e.g. Gamma `endDate`, `closedTime`, or another),
> and on what date was the frozen metadata snapshot taken? Could that field
> have been edited after market creation, and do you have, or know of, a
> source of the original end time at market creation?

## Owner decisions requested

1. Accept the Task 1 reading: `close_at` is a scheduled-type field that
   matches slug-encoded windows for recurring crypto price markets, but its
   original value is unverified. Then choose among:
   - (a) ask the authors (question above);
   - (b) amend §4.3 to define scheduled end for slug-encoded recurring markets
     from the slug schedule, with `close_at` as a cross-check;
   - (c) keep the duration condition blocked.
2. 4 h multistrike: decide how to treat the encoded time (start vs end) until
   it is documented.
3. Approve the audit strata, label definitions and thresholds before any
   audit run.
