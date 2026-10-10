# PROVISIONAL A1 classifier audit protocol (prepared, NOT run)

Revision: v1.1 (2026-10-10). Closes the two MAJOR findings of the independent
(Codex) review of `2862cf7` (conservative UNRESOLVED scoring; binding S4/S5
census gates) and adds the labelling rubric, the single-revision procedure and
honest sampling-uncertainty reporting. Classifier, selection script, worksheet,
key, hashes, salts and strata are unchanged.

Status: draft for owner approval. Nothing here is labelled, evaluated, accepted
or frozen. A1, A2, the code and `PREREGISTRATION.md` are unchanged. The
`close_at` scheduled-end meaning stays UNCONFIRMED (owner decision), and the
duration condition is not part of this audit.

## 1. What is audited

The metadata condition of §4.3 ("its category/tags mark it as crypto, or a
frozen regex matches its question or slug"), implemented as
`CANDIDATE_CLASSIFIER_DRAFT.toml` (`a1-candidate-v1`):

- **category_tokens** (exact, whole value, trimmed + casefolded): crypto,
  crypto prices, bitcoin, ethereum, solana, xrp, ripple, dogecoin, cardano, ltc,
  eth, sol, fartcoin, hyperliquid, pepe.
- **slug_patterns** (anchored; asset whitelist; no bare `up-or-down`, no
  `doge`): `{asset}-up-or-down-`, `{btc|eth|sol|xrp}-multistrike-`,
  `{asset}-above-`, `will-{asset}-(reach|dip-to|hit)-`,
  `bitcoin-and-ethereum-up-on-`.
- **Never positive by category:** `DOGE` (US government) and product/format/UI
  labels (Up or Down, Recurring, Recurrig, Hide From New, 1H, 4H, 15M, Daily,
  Weekly, Monthly, Multi Strikes, Hit Price, Today 🚀, Prices, Featured,
  Trending Markets, All, NOW, Pre-Market). Such markets can still match by slug.
- **Undecided** (full census, owner decides per label): memecoins, airdrops,
  crypto summit, crypto policy, stablecoins, tether, usdc, coinbase, bybit,
  bybit hack, opensea, pump.fun, ethena, monad, lighter, base, microstrategy,
  mstr, metaplanet, michael saylor, sbf, sam bankman-fried, ansem, $trump,
  $yzy, yzy, $libra, exchange.
- `category_refined` is a stratification and challenge signal only, never an
  input. `question`/`tags` do not exist and are not substituted. `close_at`,
  durations, prices, quantities and outcomes are not used.

Rule: the classifier says crypto-related iff category_token_match OR
slug_match. The classifier targets label **A** (crypto-related), as in §4.3,
not only crypto-price markets.

### Known risks (before any audit)

- **False positives:** short or ambiguous tokens (`sol`, `eth`, `pepe`,
  `ripple`, `ltc`). Labels such as `Crypto` and `Bitcoin` also hold non-price
  markets (A = YES, B = NO), which is correct for §4.3 but should be visible
  in B.
- **False negatives:**
  - crypto markets under format/UI or topical labels whose slug falls outside
    the bounded patterns (e.g. `fartcoin-above-…`, `hyperliquid-above-…`,
    `what-will-btc-dominance-hit-first-…`, `will-btc-hit-100k-or-110k-first`,
    `ethereum-all-time-high-before-2026`, `major-crypto-exchange-hack-in-2025`);
  - assets missing from the whitelist (bnb, sui, ton, link, avax, ada, ltc in
    slugs);
  - crypto "Mentions" markets (`will-trump-say-bitcoin-or-crypto-…`), which
    reviewers decide on;
  - every undecided label (pending the census).

## 2. Data and selection (exploration only)

- `TimeSeventeen/Polymarket-v1` @ `5aa1b9d52316a8b2e789e81c8ae42c7ed532e8aa`,
  manifest v3; the 282 verified pre-holdout `daily_aligned` files
  (re-verified 2026-10-09).
- Rows with `block_timestamp` in 2025-01-01T00:00:00Z .. 2025-09-30T23:59:59Z
  only, after a `Scope.PRE_HOLDOUT` read through `r0.rawread.read_rows`; no
  embargo or holdout rows.
- Columns read: `condition_id`, `block_timestamp` (filter), `category`,
  `market_slug`, and `category_refined` (stratification only).
- One metadata tuple per market (checked; the script refuses otherwise).
  44,275 markets.
- Script: `select_audit_sample.py` (deterministic). Stratum sampling order is
  SHA-256(`a1-audit-v1|condition_id`); worksheet row order and review ids come
  from SHA-256(`a1-audit-v1-worksheet|condition_id`).

### Strata (mutually exclusive, assigned in this priority order)

| Stratum | Definition | Population | Selected |
| --- | --- | ---: | ---: |
| S1 | category token AND slug pattern | 12,070 | 100 |
| S2 | category token only | 493 | 100 |
| S3 | slug pattern only | 10,171 | 100 |
| S4 | neither; category ∈ undecided labels | 201 | 201 (census) |
| S5 | neither; category = `DOGE` | 14 | 14 (census) |
| S6 | neither; `category_refined` ∈ {Crypto, Price Action} | 174 | 150 |
| S7 | all remaining exploration markets | 21,152 | 200 |
| | **total** | **44,275** | **865** |

### Files

| File | Content | In Git? | SHA-256 |
| --- | --- | --- | --- |
| `A1_AUDIT_WORKSHEET_BLINDED.csv` | 865 rows: `review_id, category, market_slug, A_crypto_related, B_crypto_price` (labels blank) | yes: committed in `2862cf7fddc25fc9a2d1edf0f0a77578a3f558ea` (provisional folder) | `30b480ee1e93c4351a01767e7280b525319a2e04ceed8069818a49aadb3fae1a` |
| `data/exploration/inspection/a1_audit_key.csv` | unblinded key: review_id → condition_id, stratum, T, R, F, category_refined | no (Git-ignored, ephemeral; regenerated identically by the script) | `6dd3ff964045dd14498197eeb9ff71b27e44205abc74c12d38f17832485a202b` |

The worksheet does not reveal the stratum, the classifier prediction or
`category_refined`. Rows are interleaved across strata. (`category` itself is
shown by design, so a reviewer can partly infer token matches; this is
unavoidable with the available metadata.)

## 3. Manual labelling (independent human review)

**Rubric.** `LABELING_RUBRIC.md` defines labels A and B and the YES / NO /
UNRESOLVED criteria. It is binding for every reviewer and for adjudication.

**Blinding.** Reviewers receive only `A1_AUDIT_WORKSHEET_BLINDED.csv` and
`LABELING_RUBRIC.md`. They never see the unblinded key, the strata, the
classifier predictions or `category_refined`. They may use general public
knowledge of what a name means, but must not look up the market itself, its
prices or its outcome. Insufficient evidence in the provided metadata means
UNRESOLVED, never an inferred answer.

**Sequence** (each step is completed and its file SHA-256-recorded before the
next step starts):

1. **Primary review.** One reviewer labels A and B for all 865 rows.
2. **Second review.** Only after step 1 is finished, a second reviewer receives
   one combined, shuffled list of review ids, without the primary's answers.
   The list contains (a) every item the primary labelled UNRESOLVED on A or B,
   and (b) the existing deterministic QA sample: the first 87 review ids in
   SHA-256(`a1-audit-v1-qa|review_id`) order (10%). The second reviewer labels
   them independently.
3. **Adjudication.** The owner adjudicates every disagreement and every item
   either reviewer left UNRESOLVED, with a written reason per item. The
   adjudicated label may itself be UNRESOLVED, and is then scored
   conservatively (§4). Nothing is resolved silently.
4. **Unblinding.** Only after adjudication is complete is the key opened and
   are §4 and §5 applied. No scoring happens before adjudication.

## 4. Scoring and acceptance gates (fixed before any evaluation)

All scoring uses **adjudicated** labels. **Label A (crypto-related) governs
every gate.** Label B is descriptive only and can never substitute for A.

For a stratum, let Y, N and U be the counts of adjudicated A = YES, NO and
UNRESOLVED.

**Positive strata** (classifier predicts crypto-related): S1, S2, S3.
Only A = YES counts as a correct positive. A = NO and A = UNRESOLVED do not.

| Stratum | PASS only if |
| --- | --- |
| S1 | Y ≥ 98 of 100 **and** U ≤ 5 |
| S3 | Y ≥ 98 of 100 **and** U ≤ 5 |
| S2 | Y ≥ 95 of 100 **and** U ≤ 5 |

**Negative sampled strata** (classifier predicts not crypto-related): S6,
S7. Missed crypto-related markets are counted **conservatively** as
M = Y + U.

| Stratum | PASS only if |
| --- | --- |
| S6 | M = Y + U ≤ 3 of 150 **and** U ≤ 7 (5%) |
| S7 | M = Y + U ≤ 1 of 200 **and** U ≤ 10 (5%) |

- The ≤ 5% UNRESOLVED limit is an additional condition. It never replaces
  conservative scoring.
- A gate is PASS or FAIL. A FAIL caused only by UNRESOLVED items is recorded
  as "FAIL (inconclusive)"; it still counts as FAIL. Excess uncertainty can
  never produce PASS.
- Passing a single stratum gate is necessary but not sufficient: acceptance
  needs **every** gate in §4, §5 and (if used) §6.

**Synthetic worked examples** (illustrations, not results):

| Case | Labels | Computation | Result |
| --- | --- | --- | --- |
| S7 | 1 YES, 10 UNRESOLVED, 189 NO | M = 1 + 10 = 11 > 1 | **FAIL** (U = 10 ≤ 10 holds, the M criterion does not) |
| S6 | 3 YES, 7 UNRESOLVED, 140 NO | M = 3 + 7 = 10 > 3 | **FAIL** |
| S7 | 0 YES, 0 UNRESOLVED, 200 NO | M = 0 ≤ 1; U = 0 ≤ 10 | **S7 numerical criterion met only.** Overall acceptance still needs every other gate |
| S1 | 97 YES, 3 UNRESOLVED | Y = 97 < 98 | **FAIL** (UNRESOLVED never counts as correct) |
| S2 (boundary) | 95 YES, 5 NO, 0 UNRESOLVED | Y = 95 ≥ 95; U = 0 | S2 gate PASS only |
| S3 (boundary) | 98 YES, 0 NO, 2 UNRESOLVED | Y = 98 ≥ 98; U = 2 ≤ 5 | S3 gate PASS only |

## 5. Binding census gates (S4, S5) and systematic error families

S4 (201 markets) and S5 (14 markets) are complete censuses of markets the
candidate classifier predicts as **not** crypto-related.

**Possible miss.** Every S4/S5 market with adjudicated A = YES or
A = UNRESOLVED is a possible miss. Each one needs exactly one disposition:

- **D1 Corrected:** an owner-approved, bounded, documented category token or
  slug rule, introduced in the single revision (§6). The revised classifier
  must be shown to classify the market as crypto-related, and the full §6
  verification must pass.
- **D2 Resolved as not crypto-related:** only for an adjudicated UNRESOLVED
  market. A further independent review plus owner adjudication, with a written
  reason, concludes A = NO. A market adjudicated A = YES can never be resolved
  by D2.
- **D3 Open:** anything else (unresolved, uncorrected, or a correction that was
  not approved or not verified). **Any D3 means the classifier is NOT
  ACCEPTED.**

Logging or reporting a census miss is not a disposition.

**Undecided labels (S4).** The owner decides each undecided label after
adjudication.
- Including a label as a category token is a D1 correction for its A = YES
  markets.
- Its census markets labelled A = NO or UNRESOLVED then become false
  positives, which fall under the systematic-family rule below.
- Excluding a label leaves each of its A = YES / UNRESOLVED markets needing D1
  (e.g. a bounded slug rule) or D2.

**DOGE (S5).** `DOGE` is never added as a blanket category token. If an
individual DOGE-category market is adjudicated as being about Dogecoin, it
needs a specific disambiguating rule (D1), such as a bounded slug pattern that
names dogecoin. Treating all DOGE markets as crypto is not allowed.

**Systematic error families.** A family is ≥ 2 errors with a common cause (one
category label, one asset token, one slug family or pattern) in any stratum or
census. It covers:
- false positives: A = NO or UNRESOLVED in S1–S3, or in a newly included label;
- false negatives: A = YES or UNRESOLVED in S4–S7.

Every family needs a documented correction and successful verification in
the single revision (§6). Reporting a family is not sufficient. **An
uncorrected or unverified family means NOT ACCEPTED.**

**Overall decision.** The classifier is ACCEPTED (and may only then be
proposed for the A1 freeze) only if all of the following hold:
1. adjudication is complete;
2. every gate in §4 is PASS;
3. every S4/S5 possible miss has disposition D1 or D2;
4. no systematic family is uncorrected;
5. if a revision was made, every step of §6 is complete and passed.

Otherwise it is **NOT ACCEPTED**. Any classifier change needs owner approval
and the single revision of §6; no change is applied by this protocol.

## 6. Single revision procedure (at most one round)

All v1 records stay preserved and unchanged: worksheet, primary and second
labels, adjudication log, key hash, v1 scores and v1 decision. If the owner
approves one revision:

1. Document each changed token or pattern and its justification (which
   errors, families or census dispositions it addresses).
2. Re-assign strata for the **full** exploration population (44,275 markets)
   with the revised classifier, using the selection script with the
   prespecified salts `a1-audit-v2` (sampling), `a1-audit-v2-worksheet` (order
   and ids) and `a1-audit-v2-qa` (QA sample).
3. Check every previously labelled market whose prediction changes: list it
   with its adjudicated v1 label. Adjudicated labels describe the market, not
   the classifier, so they are reused, not relabelled.
4. Re-audit the affected strata with the v2 salts. Newly sampled markets are
   labelled blind with the same rubric and the §3 sequence.
5. Record the overlap between v1 and v2 samples per stratum. Overlapping
   observations are **not** treated as independent replication.
6. Re-apply every gate: §4 thresholds, §5 census dispositions and the
   systematic-family rule.
7. If the revised classifier fails, stop. No A1 freeze is proposed and there
   is no further revision round in this audit. Unlimited revision rounds and
   unlogged post-hoc changes are not allowed.

**Disclosed dependence between rounds.**
- The census strata (S4, S5) repeat across rounds: the same markets, with the
  same adjudicated labels unless re-reviewed.
- S6 samples necessarily overlap substantially: 150 of 174 markets are
  sampled, so two samples of 150 from an unchanged population share at least
  126 markets.
- S1–S3 and S7 overlaps are reported as observed.

## 7. Reporting (honest sampling uncertainty)

The audit report must contain:

- **Per-stratum observed confusion counts:** predicted class (positive for
  S1–S3, negative for S4–S7) × adjudicated A (YES / NO / UNRESOLVED); the same
  table for B, marked descriptive.
- **Population-weighted estimates:** for each stratum h, population N_h,
  sample n_h and sampling fraction f_h = n_h / N_h (S4 and S5 have f = 1).
  The estimated crypto-related count is N_h · y_h / n_h. From these:
  - estimated precision of the predicted-positive set = Σ_{S1–S3} estimated
    count / Σ_{S1–S3} N_h;
  - estimated missed count = Σ_{S4–S7} estimated count;
  - estimated recall = positives / (positives + misses).
  Each is computed twice, with UNRESOLVED as NO and as YES, giving bounds.
- **Finite-population sampling uncertainty:** exact hypergeometric 95%
  intervals for each sampled stratum's crypto-related count (censuses are
  exact). Any combined interval must be labelled as approximate and its method
  stated.
- **Disclosure:** S7 samples only 200 of 21,152 markets (f ≈ 0.95%).
  - Illustration (synthetic; Codex's point): 1 observed miss in 200 is
    compatible with many more unseen misses in S7. The point estimate is about
    106, and the exact hypergeometric 95% upper bound is about 580 markets.
  - Even 0 observed misses leaves an upper bound of about 384.
- **Prohibited claims:** no claim of near-perfect global recall, no
  duration-qualified S_short recall, no event-weighted recall. The stratum
  thresholds are acceptance gates, not global guarantees. The audit concerns
  exploration-period market metadata only.

## 8. Not done

No labels assigned, no adjudication, no accuracy computed, no classifier
accepted, no S_short membership, no durations, no events or outcomes.
