# S_short metadata investigation before A1 design (2026-10-08)

**Status: exploratory classifier-design evidence and a provisional proposal.**
No classifier was evaluated, no S_short membership or duration was computed,
and A1, A2, the code and `PREREGISTRATION.md` are unchanged. Follows
`S_SHORT_VOCAB_FINDINGS.md`.

## Provenance

| Item | Value |
| --- | --- |
| Dataset | `TimeSeventeen/Polymarket-v1` @ `5aa1b9d52316a8b2e789e81c8ae42c7ed532e8aa`, manifest v3 |
| Files | the 282 verified pre-holdout `daily_aligned` files (cache re-verified 2026-10-08: 282 verified, 0 mismatches) |
| Rows | EXPLORATION only: `block_timestamp` in 2025-01-01T00:00:00Z .. 2025-09-30T23:59:59Z, after a `Scope.PRE_HOLDOUT` read through `r0.rawread.read_rows` (trailing 2024 and embargo rows dropped; holdout never returned) |
| Columns read | `condition_id`, `block_timestamp` (filter only), `category`, `category_refined`, `market_slug`. Nothing else |
| Method | a scratch script (not in the repo) that reduces the rows to distinct market-level tuples; examples are ordered by SHA-256(`catref-v1|condition_id`) |
| Code commit | `32f2502fd411715268716785d9e9aa9ab5bec184` (no code changes) |

## A. `category_refined` versus `category` (44,275 exploration markets)

- No nulls or empty strings in `category`, `category_refined` or
  `market_slug`. Exactly one `(category, category_refined, market_slug)` tuple
  per market: **no within-market variation**.
- `category_refined` has **8 values**: Crypto 16,571 · Sports 13,161 ·
  Price Action 6,393 · Politics 4,891 · Other 1,480 · Sci-Tech 652 ·
  Culture 634 · Finance 493.
- It is a coarse topic taxonomy, but it is **not a function of `category`**:
  the same label maps to several refined values (Recurring: Crypto 1,463,
  Politics 29, Other 16, Price Action 5, Sports 3, Finance 1; Mentions:
  Politics 1,105, Other 125, Finance 110, Crypto 97, …). The card calls it
  "Refined/cleaned market category used in analysis" (L143); a search-engine
  summary of the paper (not read directly: arxiv.org is blocked here) mentions
  a mapping table (Table 16) of refined categories. Its construction is
  undocumented here.
- **`Price Action` ≈ crypto price markets.** It holds Up or Down 4,481, 1H
  1,388, Multi Strikes 205, Hit Price 102, Weekly 91, 4H 91, Hide From New 14,
  Today 🚀 11, Recurring 5, 15M 4 and one other. 6,386 of its 6,393 slugs start
  with a crypto asset token (btc, eth, bitcoin, ethereum, solana, xrp, sol,
  dogecoin, ethbtc, hyperliquid, fartcoin). The other 7: MicroStrategy BTC
  purchase markets, `soleth-up-or-down-in-may-267`, and one clear error
  (`will-lily-phillips-break-bonnie-blues-24hr-sex-record-before-april`).
- **Where it resolves an ambiguous `category`** (examples):
  - Recurring → Politics: `will-donald-trump-sign-an-executive-order-on-may-3`
  - Hide From New → Sports: `dota-2-gaimin-gladiators-vs-execration`
  - Up or Down / 1H / 4H / 15M → Price Action (all crypto in the examples)
- **Where it contradicts the observed meaning** (examples):
  - DOGE → **Crypto** (all 14), but these are US-government markets:
    `will-trump-privatize-usps-in-first-100-days`,
    `will-doge-confirm-gold-missing-from-fort-knox`
  - Daily → **Sci-Tech** (all 54), but they are crypto price markets:
    `ethereum-up-or-down-on-july-1`, `bitcoin-above-115pt5k-on-august-24-at-8pm-et`
  - Recurring → **Sports**: `will-jerome-powell-say-inflation-40-or-more-times-during-the-may-meeting`
  - Recurring → Other: `hyperliquid-up-or-down-on-may-20` (a crypto price market)
  - one slug family split across values: `sol-multistrike-4h-*` → Price Action,
    `xrp-/eth-multistrike-4h-*` → Crypto
  - coinbase → Sports (`will-brian-armstrong-say-milady-during-his-x-space`);
    Airdrops → Sci-Tech; Pump.Fun → Politics; pepe → Other
- **Does it materially improve crypto-price detection?** As a recall aid,
  yes: every format label without a crypto name (Up or Down, 1H, 4H, 15M, Hit
  Price, Weekly) lands in Price Action. As a rule, no: it is provider-derived
  and inconsistent (the contradictions above), it mislabels DOGE as Crypto,
  it puts crypto Daily markets in Sci-Tech, and refined `Crypto` also holds
  non-price markets (Mentions, Crypto Summit, MicroStrategy).

## B. `close_at` semantics

**Classification: UNRESOLVED — ORIGINAL SCHEDULED END NOT VERIFIED.**

Documented facts:
- Card (pinned blob `a1146ec…`) L150: `close_at` | timestamp | "Market close
  time." L264: market time fields "come from the frozen market metadata
  layer". L310: metadata "is a static snapshot and should be treated as fixed
  analysis metadata rather than a live, continuously updated market database".
- Schema: `timestamp[us, tz=UTC]`, present in every file (no drift).
- A search-engine summary of the paper says metadata comes from a "frozen
  metadata snapshot" joined on `asset_id`. The snapshot date and its source API
  are not stated in anything read here. The paper, docs.polymarket.com and
  RePEc are blocked by this environment's network policy.
- Search-result summaries of Polymarket's Gamma documentation list both
  `endDate` and `closedTime` as market fields (with `closedTime` null for an
  open market). These were not read first-hand.

Inferences (unverified):
- `close_at` could be the scheduled `endDate` or the actual `closedTime`. If
  it is `closedTime`, it is set only when the market closes, so it is
  after-the-fact information, not a scheduled end.
- Even if it is `endDate`, a single later snapshot cannot show whether the
  value was edited after trading began. No source found says whether Polymarket
  changes `endDate` after creation, and the dataset holds no history of it.
- Some crypto slugs embed the scheduled window (`btc-up-or-down-15m-{unix}`,
  `…-multistrike-4h-{unix}-…`, `…-july-7-3pm-et`). Slugs are likely set at
  creation, but that is not verified, and slug-derived times are not part of
  any approved definition.

Not done: no `close_at` values inspected, no durations computed. A present-day
Gamma snapshot is not recommended as historical ground truth.

## C. Provisional A1 design (proposal only; not applied, not evaluated)

1. **Category token set T** (exact match on the whole `category` value after
   trim + casefold; never substring):
   - include: Crypto, Crypto Prices, Bitcoin, Ethereum, Solana, XRP, Ripple,
     Dogecoin, Cardano, eth, sol, fartcoin, hyperliquid, pepe;
   - exclude: `DOGE` (government) and all format/UI labels (Up or Down, 1H, 4H,
     15M, Recurring, Multi Strikes, Hit Price, Daily, Weekly, Hide From New,
     Today 🚀) and the generic `Prices`;
   - undecided (owner review): Memecoins, Airdrops, Crypto Summit,
     MicroStrategy, Crypto Policy, coinbase, Stablecoins, Michael Saylor,
     Pump.Fun, tether, usdc.
2. **Slug patterns R_s** (anchored; asset whitelist; no bare `up-or-down`,
   no `doge` token):
   - `^(bitcoin|btc|ethereum|eth|solana|sol|xrp|dogecoin|hyperliquid|fartcoin|ethbtc|soleth)-up-or-down-`
   - `^(btc|eth|sol|xrp)-multistrike-`
   - `^(bitcoin|ethereum|solana|xrp|dogecoin)-above-`
   - `^will-(bitcoin|btc|ethereum|eth|solana|sol|xrp|dogecoin)-(reach|dip-to|hit)-`
   - `^bitcoin-and-ethereum-up-on-`
3. **`category_refined`**: exclude it from the rule and use it only in the
   audit, as a disagreement signal. It is provider-derived and inconsistent,
   and §2.1 says provider-derived fields are not ground truth.
4. **Finite audit plan** (exploration markets only; samples fixed by SHA-256
   order with a stated salt; manual labels from `category` + `market_slug`
   only):
   - 100 matched by T only; 100 by R_s only; 100 by both;
   - 100 unmatched with `category_refined` ∈ {Crypto, Price Action};
   - 100 unmatched design-screen hits; 100 random unmatched;
   - every market of each undecided label (each ≤ 47 markets).
   Report counts of confirmed false positives and misses per stratum. Owner
   acceptance criteria are set before the audit runs; one logged revision
   round; then freeze with A1. The duration condition stays blocked on
   `close_at`.

## Owner decisions requested

1. Approve T (include / exclude lists) and the fate of each undecided label.
2. Approve R_s.
3. `category_refined`: audit-only (recommended), or part of the rule.
4. Scheduled end: `close_at` is unverified. Choose among: (a) obtain the
   paper's methodology text through an allowed route and re-assess;
   (b) propose a §4.3 amendment with another, documented definition of
   duration; (c) keep S_short's duration condition blocked.
5. Audit acceptance criteria, before the audit is run.
