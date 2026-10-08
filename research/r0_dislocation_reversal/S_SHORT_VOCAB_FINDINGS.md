# S_short metadata vocabulary — exploration-only findings (2026-10-08)

**Status: exploratory classifier-design evidence only.** Not a classifier,
not an evaluation, not used by any event logic. A1 is unchanged and unfrozen.
No S_short membership was derived, and the ≤ 24 h duration condition (§4.3)
was not evaluated.

## Provenance

| Item | Value |
| --- | --- |
| Dataset | Hugging Face `TimeSeventeen/Polymarket-v1` @ `5aa1b9d52316a8b2e789e81c8ae42c7ed532e8aa` (manifest v3) |
| Files read | the 282 `pre-holdout` `daily_aligned` files (2024-12-30 .. 2025-10-07), 546,269,510 bytes, all SHA-256-verified (`00_fetch.py --verify --part pre-holdout`: 282 verified, 0 mismatches) |
| Rows used | `block_timestamp` in the EXPLORATION period only: 2025-01-01T00:00:00Z .. 2025-09-30T23:59:59Z. Trailing 2024 rows and the 2025-10-01..07 embargo rows are dropped after the scoped read; holdout rows are never returned by `r0.rawread` |
| Columns read | `condition_id` (market id), `block_timestamp` (filter only), `category`, `market_slug` (owner-confirmed `slug`). `question`, `tags` do not exist; `close_at` / scheduled end and all price, quantity and direction columns were not read |
| Command | `uv run python research/r0_dislocation_reversal/scripts/01_schema.py vocab --source local --sample-every 1` (exit 0), no `--classifier` |
| Code commit | `f2237ff0963975caca14928bebaf8e6a9fa54e40` (no code changes) |
| Outputs (Git-ignored, ephemeral, deterministic) | `data/exploration/inspection/s_short_vocab.json` SHA-256 `b8e960df193ff560ee5e723c55af24a7cfc5e7ecc6f831011f87193ae83fb74a`; `s_short_vocab.md` SHA-256 `78571bb7104ebcce9ecc3fb2dde8ec62c04177c69427d9b320501fc2a88584b9` |

The raw Parquet cache and the outputs above live only in the cloud session's
ephemeral `data/` directory and are not in Git; re-running the download,
verification and command reproduces them.

## Overall

- 44,275 exploration-period markets (`condition_id`s with at least one
  exploration-period row).
- `category`: present for every market (0 markets with null category);
  exactly **one value per market** (the per-market counts sum to 44,275); no
  market has varying metadata; 0 rejected/structured values. 528 distinct
  values, 219 of them used by a single market.
- `market_slug`: present for every market (0 null).
- The over-inclusive design screen (keywords on the slug, `r0.vocab.DESIGN_SCREEN`)
  matches 23,006 markets; it is a search aid, not a classifier.

## What `category` is

`category` is a single tag-like label, not a broad category: alongside
topical labels (`Sports`, `Politics`, `Crypto`) it holds asset labels
(`Bitcoin`, `Solana`), product/format labels (`Up or Down`, `1H`,
`Multi Strikes`, `Recurring`) and UI labels (`Hide From New`, `Today 🚀`).
Spelling and case vary (`Ethereum`/`eth`, `Solana`/`sol`, `Dogecoin`/`DOGE`).

Top labels (markets): Sports 10,749 · Up or Down 4,481 · Crypto 3,273 ·
Bitcoin 2,195 · Crypto Prices 1,946 · Ethereum 1,778 · Solana 1,635 ·
Recurring 1,517 · Mentions 1,500 · Hide From New 1,431 · XRP 1,393 · 1H 1,388 ·
Politics 879 · Multi Strikes 877 · Esports 677 · Games 674 · Trump 597 ·
Tennis 387 · Culture 386 · Trump Presidency 337 · Ripple 300 · World 282 ·
Geopolitics 245 · Today 🚀 205 · U.S. Politics 190 · NFL 169 · Tech 150.

## Crypto-related labels (markets; classified by reading the exported examples)

| Group | Labels |
| --- | --- |
| Explicit crypto, generic | Crypto 3,273 · Crypto Prices 1,946 · Prices 1 |
| Explicit crypto, asset | Bitcoin 2,195 · Ethereum 1,778 · Solana 1,635 · XRP 1,393 · Ripple 300 · Dogecoin 23 · eth 5 · fartcoin 5 · hyperliquid 4 · sol 3 · Cardano 1 · pepe 1 · tether 1 · usdc 1 |
| Product/format labels whose examples are all crypto price markets | Up or Down 4,481 · Recurring 1,517 · Hide From New 1,431 · 1H 1,388 · Multi Strikes 877 · Today 🚀 205 · Hit Price 102 · 4H 91 · Weekly 91 · Daily 54 · 15M 4 |
| Crypto-themed, mostly not short price markets | Airdrops 47 · Crypto Summit 37 · Memecoins 29 · MicroStrategy 24 · Crypto Policy 12 · coinbase 8 · Stablecoins 6 · Michael Saylor 5 · Pump.Fun 2 |
| **Not crypto despite the name** | `DOGE` 14 (US "Department of Government Efficiency": e.g. `will-doge-cut-1b-from-usaid-before-march`) |
| Keyword false positives | counter-strike, counter strike 2, Weather, climate & weather, National Anthem/Coin Toss, Nathan's Hot Dog Eating Contest |

Format labels are not crypto-specific by definition: `Up or Down`-style slugs
also occur outside crypto (`trump-approval-up-or-down-this-week-*` under the
label `Approval`; `usdc-market-cap-up-or-down-this-week` under `Stablecoins`).

## Exploration slug patterns (from the ~1,600 exported example markets)

| Pattern | Example | Seen with labels |
| --- | --- | --- |
| `{asset}-up-or-down-{month}-{day}-{h}{am\|pm}-et` (hourly) | `bitcoin-up-or-down-june-21-10pm-et` | Crypto, Recurring, 1H, Up or Down |
| `{asset}-up-or-down-on-{month}-{day}` (daily) | `solana-up-or-down-on-september-20` | Daily, Solana |
| `{asset}-up-or-down-15m-{unix}` (15 min) | `btc-up-or-down-15m-1758989700` | 15M, Up or Down |
| `{asset}-multistrike-4h-{unix}-{strike}` | `eth-multistrike-4h-1757520000-4200` | 4H, Multi Strikes, asset labels |
| `{asset}-above-{price}-on-{date}` | `xrp-above-3pt1-on-september-27` | Weekly, XRP |
| `will-{asset}-reach\|dip-to\|hit-{price}-…` | `will-solana-reach-220-in-august-862` | Hit Price, asset labels |
| pairs / combos | `ethbtc-up-or-down-on-may-17`, `bitcoin-and-ethereum-up-on-july-10` | Today 🚀, Daily |

Asset tokens seen in slugs: `bitcoin`/`btc`, `ethereum`/`eth`,
`solana`/`sol`, `xrp`, `dogecoin`, `hyperliquid`, `fartcoin`, `ethbtc`.
Some slugs carry numeric de-duplication suffixes
(`…-455-941-866-736-589`). The 15M and 4H slugs embed a Unix time; it was
not used, and it must not stand in for the scheduled end without an owner
decision.

## Restrictions and unresolved questions (owner)

1. `tags` and `question` do not exist; §4.3's "category/tags" test reduces to
   one label per market and the regex test to `market_slug`. A1 must be
   revised (frozen token set over `category` plus a slug regex), or one pinned
   Gamma snapshot of question/tags used (§2.2).
2. Include product/format labels (`Up or Down`, `1H`, `4H`, `15M`,
   `Recurring`, `Multi Strikes`, `Hit Price`, `Daily`, `Weekly`,
   `Hide From New`, `Today 🚀`) in the crypto token set, or rely on the slug
   regex for them? They are not crypto by name, and non-crypto up-or-down
   markets exist.
3. `DOGE` must not be treated as Dogecoin; case-insensitive matching of
   `doge` would misclassify it.
4. Crypto-themed non-price labels (Airdrops, Memecoins, Crypto Summit,
   MicroStrategy, Crypto Policy, Stablecoins, coinbase): in or out of
   "marked as crypto"? The 24 h duration condition decides membership
   together with them.
5. `category_refined` exists but was not inspected (not mapped); whether it is
   a better source is an owner decision.
6. The scheduled end (`close_at`) remains unconfirmed; durations were not
   computed.
