# A1 audit labelling rubric (PROVISIONAL; binding for this audit round)

Use with `A1_AUDIT_WORKSHEET_BLINDED.csv` only. For each row you see
`review_id`, `category` and `market_slug`. You do **not** see, and must not
seek, the classifier's prediction, the stratum, `category_refined`, the
unblinded key, the market page, its prices or its outcome. General public
knowledge of what a name means is allowed (e.g. that "Monad" is a blockchain).

Answer two questions per row: **YES**, **NO** or **UNRESOLVED**. If the
provided metadata does not establish the answer, write UNRESOLVED; never
infer or guess. Add a short note for every UNRESOLVED.

## A. Is the market about cryptocurrencies or the crypto ecosystem? (PRIMARY)

**YES** when the subject of the market is any of:
- a cryptocurrency or token, including memecoins and stablecoins, or a
  blockchain or crypto protocol (e.g. bitcoin, ethereum, solana, XRP, dogecoin,
  USDC/USDT, Hyperliquid, Ethena, Monad);
- a crypto exchange or crypto-native business, about its business (e.g.
  Coinbase listings or launches, Bybit, OpenSea, Pump.fun);
- crypto regulation or policy, a crypto hack, a token listing, an airdrop or a
  token launch;
- a stablecoin's supply, market cap or peg (e.g. `usdt-depeg-in-2025`);
- a person or company **in their crypto activity**, e.g. MicroStrategy buying
  bitcoin, or SBF's crypto-fraud case;
- a "mention" market whose counted word or phrase is itself a crypto term
  (e.g. `will-trump-say-crypto-or-bitcoin-…`).

**NO** when crypto plays no part in the subject:
- a person or company whose market concerns unrelated activity (e.g. a
  politician's election, a company's non-crypto product);
- a "mention" market about a non-crypto word, even if the speaker is linked to
  crypto;
- **`DOGE` as the US "Department of Government Efficiency"** (e.g.
  `will-doge-cut-1b-from-usaid-…`, `will-trump-create-a-doge-dividend-…`).
  Government DOGE is NO.

**UNRESOLVED** when the metadata cannot settle it:
- ambiguous names or symbols whose sense the slug does not fix: `sol` (Solana
  vs. Spanish "sun" or a name), `eth`, `ltc`, `pepe` (memecoin vs. meme),
  `base` (Coinbase's L2 vs. ordinary word), `lighter` (exchange vs. ordinary
  word), `doge` when the slug does not show government vs. Dogecoin;
- a company or person label where the slug does not show whether the market
  concerns their crypto activity;
- any slug too terse to determine the subject.

A clear slug decides even under a misleading category, e.g. category `sol`
with slug `will-solana-hit-270-in-december` is YES. Dogecoin, the coin, is YES.

## B. Is resolution specifically about a crypto price, direction, market cap, FDV or dominance? (DESCRIPTIVE)

**B = YES requires A = YES.** If A = NO, then B = NO. If A = UNRESOLVED, then
B is NO or UNRESOLVED, never YES.

**YES** when the resolution depends on a crypto asset's or pair's price
level, price direction (up/down), market cap, FDV or dominance. Examples:
`bitcoin-up-or-down-…`, `eth-multistrike-4h-…`, `xrp-above-…`,
`will-solana-reach-…`, `usdc-market-cap-up-or-down-this-week`,
`what-will-btc-dominance-hit-first-…`, `…-fdv-one-day-after-launch`, and a
stablecoin depeg defined by a price threshold (e.g. `usdt-depeg-in-2025`).

**NO** for crypto-related markets resolved by something else: an airdrop
happening, a listing, a hack, regulation, a purchase announcement, a mention,
an ETF approval.

**Not automatically YES:** a crypto company's **stock price** (e.g.
MicroStrategy or Coinbase shares, or MicroStrategy's NAV) is not a
cryptocurrency price. Mark B = NO when the slug shows it is about the
stock/NAV, and UNRESOLVED when it is unclear whether a token or a stock is
meant.

## Procedure reminders

- The primary reviewer labels all rows and finishes before the second reviewer
  sees any primary answer.
- The second reviewer labels, independently, every item the primary marked
  UNRESOLVED and the deterministic 10% QA sample, without seeing primary
  answers.
- The owner adjudicates disagreements and UNRESOLVED items with written
  reasons. The key is opened, and acceptance computed, only after adjudication
  (`AUDIT_PROTOCOL.md` §3–§5).
- Label A governs acceptance; B is descriptive. Crypto-related (A) is broader
  than crypto-price (B): non-price crypto markets are A = YES.
