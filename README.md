# Tripwire

Tripwire is a **research project** asking one question:

> Do repeatable, economically exploitable *structural* trading edges exist —
> and can they be validated rigorously enough to justify building the minimum
> infrastructure needed to trade them safely?

"Structural" means edges that come from how markets are built and behave
(settlement rules, cross-market consistency, liquidity withdrawal, order-flow
pressure, temporary dislocations, information arriving elsewhere first), not
from generic price prediction.

## Current status

| Item | Status |
| --- | --- |
| Stage | **M0** done (governance documents). **R0** research design conditionally approved, under independent review, not implemented |
| Code | None. No data ingestion, no backtester, no strategy code |
| Production trading | **Does not exist.** No order submission, no API keys, no wallets |
| Profitability | **Not demonstrated.** No hypothesis has been tested yet |
| Live-trading legality for the project owner | **Not established.** Must be verified separately before any live work (see `docs/RISK_INVARIANTS.md`) |

Nothing in this repository should be read as evidence that any strategy
works. The expected and acceptable outcome of any research stage is
"this hypothesis does not work".

## Approach

Work proceeds in a deliberately gated order. Each gate can — and often should
— end in "stop":

1. **M0** — minimal repository architecture and governance (this stage).
2. **R0** — a rapid, falsification-first test of one hypothesis (ungated
   anomalous-flow short-horizon reversal, UAFR) on public V1-era Polymarket
   data. A failure deprioritizes only that hypothesis, not every structural
   or Tripwire idea (ADR-0010).
3. Only when a research result justifies it (a V1-era result never graduates
   a strategy toward execution; after a V1 CONTINUE the next step is a
   separately preregistered current-V2 replication, ADR-0014):
   trustworthy data capture and replay (M1),
   realistic backtesting (M2), external feeds (M3), deterministic
   structural-alpha experiments (M4), dislocation engine (M5), bounded-judgment
   experiments (M6), semantic LLM research layer (M7), realistic paper execution
   (M8), adversarial validation (M9), and — only if every legal, operational and
   empirical requirement is met — a deliberately tiny live deployment (M10).

Polymarket is the first **research data source**. It is not the architecture:
core concepts are venue-neutral, and no venue adapter is built before it is
justified.

## Documents

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — intended high-level pipeline (most of it does not exist).
- [`docs/RISK_INVARIANTS.md`](docs/RISK_INVARIANTS.md) — safety rules that no component or agent may weaken.
- [`docs/RESEARCH_METHOD.md`](docs/RESEARCH_METHOD.md) — how a hypothesis graduates (or dies).
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — architecture decision log.
- [`CLAUDE.md`](CLAUDE.md) / [`AGENTS.md`](AGENTS.md) — instructions for coding agents and reviewers.

## Not financial advice

This is a personal research and engineering project. Nothing here is
investment, legal or tax advice.
