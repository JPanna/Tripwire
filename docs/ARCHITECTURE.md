# Architecture (intended, high level)

Status: **intent, not implementation.** As of M0 none of the stages below
exists in code. This document describes the shape the system is expected to
take *if* research justifies building it. Stages are built only when a
validated research result needs them, and several may never be built.

## 1. Pipeline

```
 venue / external data
          │
          ▼
 normalized observations          (venue-neutral events with provenance + timestamps)
          │
          ▼
 deterministic state / research   (order books, trades, reference data, replay)
          │
          ▼
 structural-alpha models          (deterministic, testable, versioned)
          │
          ▼
 opportunity estimates            (fair value, edge, uncertainty, horizon)
          │
          ▼
 optional semantic AI             (LLM / Jev: advisory, bounded, may only veto or annotate)
          │
          ▼
 deterministic policy             (should we act? sizing intent; abstention is default)
          │
          ▼
 deterministic risk               (hard limits; final authority; fail-closed)
          │
          ▼
 venue adapters / execution       (mode-explicit: simulation | paper | live)
```

Not all stages need to exist in early versions. R0 uses only the first three,
in the form of offline scripts over historical files. Execution does not exist
and will not exist before M8 (paper) and, conditionally, M10 (live).

## 2. Stage responsibilities

| Stage | Responsibility | Must not |
| --- | --- | --- |
| Data sources | Supply raw venue / external records | Be trusted without validation |
| Normalized observations | Convert raw records into venue-neutral events; keep source, receive time, source time, and raw payload reference | Silently drop, reorder or "fix" records |
| Deterministic state / research | Build reproducible state (books, positions, reference data) and replay it | Depend on wall-clock or network state during replay |
| Structural-alpha models | Turn state into signals with explicit assumptions | Use information not available at decision time |
| Opportunity estimates | Quantify expected edge **after** costs, with uncertainty | Present gross effects as tradable edge |
| Semantic AI (optional) | Resolve genuinely semantic questions (rules, matching, evidence) and return bounded outputs | Do arithmetic, accounting, risk, or order submission; increase risk |
| Deterministic policy | Decide act / abstain and intended size | Act on stale, missing or contradictory state |
| Deterministic risk | Enforce hard limits and kill switches; hold final authority | Depend on any AI service; be bypassed by any adapter |
| Venue adapters / execution | Translate approved intents into venue actions; reconcile state | Submit anything not approved by risk; operate in an ambiguous mode |

## 3. Venue neutrality

Core concepts are named and modelled independently of any venue wherever the
concept itself is venue-neutral, for example: `Venue`, `Market`,
`Instrument`, `Outcome`, `OrderBook`, `PriceLevel`, `Trade`, `MarketEvent`,
`FairValueEstimate`, `Signal`, `Opportunity`, `Position`, `OrderIntent`,
`Order`, `Fill`, `RiskState`.

Rules:

- Venue-specific details (contract addresses, token IDs, fee formulas, tick
  rules, settlement mechanics) live in venue-specific modules and are mapped
  into the neutral concepts at the boundary.
- Polymarket is research data source #1 and, only if later justified, venue
  adapter #1. It is not assumed to be the final or best venue.
- Adapters for venues not currently used are **not** built speculatively.
- These concepts are listed to guide naming. They are **not** to be
  implemented as code until a milestone needs them (no speculative class
  hierarchies).

## 4. Authority boundaries

```
 advisory (may annotate, score, or veto)   │   authoritative (decides)
 ──────────────────────────────────────────┼──────────────────────────────
 LLM, Jev, external evidence, research     │   deterministic policy
 outputs, backtest results                 │   deterministic risk (final)
```

- AI outputs are inputs to deterministic policy. They can make the system
  *more* conservative (veto, abstain); they can never make it less
  conservative than the deterministic risk limits allow.
- Research results never authorize live deployment by themselves
  (see `RESEARCH_METHOD.md`, `RISK_INVARIANTS.md`).

## 5. Operating modes

When execution exists, every process runs in exactly one explicit mode:
`simulation`, `paper`, or `live`. The mode is part of every logged decision and
order identifier. `live` is disabled by default and requires explicit,
non-default configuration plus the gates in `RISK_INVARIANTS.md`. Until M10 the
`live` mode does not exist in code at all.

## 6. Reproducibility

Every eventual decision must be reconstructable from: logged inputs (with
source and receive timestamps), code version (git commit), configuration,
model/AI outputs (stored verbatim), and deterministic policy/risk state.
Research results must likewise record data source, data version/hash, code
version, and parameters.

## 7. What exists today

| Component | Exists? |
| --- | --- |
| Governance docs (this folder) | Yes (M0) |
| Data ingestion / capture | No |
| Normalized data model | No |
| Research / backtest code | No |
| Models, policy, risk | No |
| AI integration | No |
| Execution / adapters | No |
