# PROVISIONAL A1 classifier audit protocol (prepared, NOT run)

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
| `A1_AUDIT_WORKSHEET_BLINDED.csv` | 865 rows: `review_id, category, market_slug, A_crypto_related, B_crypto_price` (labels blank) | provisional folder, not committed | `30b480ee1e93c4351a01767e7280b525319a2e04ceed8069818a49aadb3fae1a` |
| `data/exploration/inspection/a1_audit_key.csv` | unblinded key: review_id → condition_id, stratum, T, R, F, category_refined | no (Git-ignored, ephemeral; regenerated identically by the script) | `6dd3ff964045dd14498197eeb9ff71b27e44205abc74c12d38f17832485a202b` |

The worksheet does not reveal the stratum, the classifier prediction or
`category_refined`. Rows are interleaved across strata. (`category` itself is
shown by design, so a reviewer can partly infer token matches; this is
unavoidable with the available metadata.)

## 3. Manual labelling (independent human review)

Reviewers see only the worksheet. They may use general public knowledge of
what a name means (e.g. that a token or company is a crypto project), but must
not look up the market itself, its prices or its outcome. Each item gets two
answers: YES / NO / UNRESOLVED. Never guess: insufficient evidence means
UNRESOLVED.

- **A. Crypto-related market:** the market's subject is a cryptocurrency or
  token, a blockchain or crypto protocol, a crypto exchange or crypto-native
  company, crypto regulation or policy, or a crypto-ecosystem event (airdrop,
  hack, listing, launch). A person or company counts only when the market is
  about their crypto activity.
- **B. Crypto-price/direction market:** resolution depends on the price, price
  level, direction, market cap, FDV or dominance of a crypto asset or pair.
  B = YES implies A = YES.

Second review: a second reviewer independently labels every UNRESOLVED item
and a 10% random subset (the first 87 review ids in SHA-256(`a1-audit-v1-qa|review_id`)
order). Disagreements are logged and adjudicated by the owner, never resolved
silently. Labels are recorded before the key is opened.

## 4. Metrics and acceptance thresholds (fixed before any evaluation)

Metric A is primary for §4.3; metric B is descriptive. UNRESOLVED never counts
as a correct identification.

| Stratum | Criterion |
| --- | --- |
| S1, S3 | ≥ 98/100 with A = YES |
| S2 | ≥ 95/100 with A = YES |
| S6 | ≤ 3/150 with A = YES (missed crypto-related markets) |
| S7 | ≤ 1/200 with A = YES (missed crypto-related markets) |
| every sampled stratum | UNRESOLVED ≤ 5% |
| S4, S5 | census; no threshold. The owner decides each undecided label from its A results; `DOGE` stays excluded unless the census contradicts the evidence |

- Any systematic false-positive or false-negative family (≥ 2 items from one
  label or one slug family) is reported, whatever the rates.
- At most **one** logged revision round. A revision changes only the token
  list or patterns, is logged with its reason, and is followed by a re-audit of
  the affected strata with a new salt (`a1-audit-v2`). Then A1 is proposed for
  freezing.
- B results are reported per stratum, without thresholds.

## 5. Not done

No labels assigned, no accuracy computed, no classifier accepted, no
S_short membership, no durations, no events or outcomes.
