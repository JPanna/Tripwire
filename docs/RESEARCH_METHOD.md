# Research method

The purpose of research in Tripwire is to **try to kill hypotheses cheaply**.
The ones that survive honest attempts at falsification may earn further
investment. "This does not work" is a successful research outcome.

## 1. Three levels of evidence (never conflate them)

| Level | Name | What it means | What it does **not** mean |
| --- | --- | --- | --- |
| L1 | **Statistical effect** | A pattern in prices/flows that is reproducible out of sample and robust to reasonable specification changes | That anyone can make money from it |
| L2 | **Tradable edge** | Positive expected profit *after* pessimistic modelling of fees, spread, slippage, latency, fill probability, partial fills, queue position and adverse selection, at a stated size, using only information available at decision time | That the profit will be realized live |
| L3 | **Realized live profitability** | Actual reconciled P&L from real orders, net of all costs, over a sample large enough to distinguish from luck | That it will persist, or scale |

Rules:

- Reports must state the highest level of evidence actually achieved and must
  not use language implying a higher one ("profitable", "alpha", "edge") for
  a lower one.
- A gross effect smaller than plausible round-trip costs is an L1 curiosity,
  not a candidate strategy.
- Win rate, Sharpe ratio, or mean return computed before costs is never
  evidence of L2.

## 2. Graduation pipeline

```
G0 hypothesis
 → G1 exploratory historical test
 → G2 holdout / out-of-sample test
 → G3 robustness analysis
 → G4 pessimistic execution simulation
 → G5 live paper trading
 → G6 consideration for deliberately small live deployment
```

Every gate has three possible outcomes: **kill**, **revise** (which creates a
*new* hypothesis that restarts at G0/G1 and needs fresh holdout data), or
**continue**. Skipping a gate is not allowed. Passing a gate never
automatically triggers the next investment; the project owner decides.

### G0 — Hypothesis card

Written *before* looking at test data. Must contain:

1. Statement of the effect and the **economic mechanism** (who is on the other
   side and why they would accept a worse price).
2. Why the effect might not already be competed away.
3. Precise null and alternative hypotheses, with the primary estimand and
   primary test fixed.
4. Exact operational definitions (events, windows, prices, outcomes).
5. Data required, data source(s), and known data limitations.
6. Exploratory / holdout split, chosen before any analysis.
7. **Kill criteria** and **continue criteria**, numeric where possible.
8. The cheapest experiment that could falsify it.

### G1 — Exploratory historical test (in-sample)

- Uses only the exploratory split. Free to iterate, but every specification
  tried is logged (the count of attempts matters for multiple testing).
- Output: a frozen specification for G2, its code version (git commit), and
  the result of a power estimate showing the holdout can detect the effect
  size that would matter economically.

### G2 — Holdout / out-of-sample test

- The holdout is touched **once**, with the frozen G1 specification.
- Any change after seeing holdout results makes this a new hypothesis that
  requires *new* unseen data (e.g., forward-collected data).
- Failure here is a kill, not an invitation to tune.

### G3 — Robustness analysis

At minimum: alternative reasonable parameter values (pre-listed), equal
weighting by market vs by event, exclusion of the most influential markets,
sub-periods, regime changes (fee schedule, venue upgrades), and controls for
known confounders (price level, liquidity, time to resolution). An effect that
lives in one market, one week, or one parameter value is not robust.

### G4 — Pessimistic execution simulation

Requires data adequate to model execution (typically order-book data, not
trades alone). Model fees, spread, slippage, latency, fill uncertainty, partial
fills, queue position and adverse selection pessimistically. If the data cannot
support a cost, bound it conservatively and say so. Only a positive result here
can be described as L2 (tradable edge), and only for the stated size.

### G5 — Live paper trading

Forward, real-time, no capital at risk, with the same code paths and logging a
live system would use. Compare paper results to simulation; large divergence is
a finding about the simulator, not noise to ignore.

### G6 — Consideration for deliberately small live deployment

A human decision, never an automatic one. Requires: G1–G5 passed, legal and
venue access verified (`RISK_INVARIANTS.md` INV-04), all on-build invariants
implemented and tested, predefined capital and loss limits, and predefined
live kill criteria. The purpose of a small live deployment is to measure the
gap between simulation and reality (L3), not to make money.

## 3. Mandatory kill criteria

Every hypothesis must define, **before seeing the data they are evaluated on**:

- the empirical outcomes that end it (statistical, economic, robustness,
  capacity, and data-validity criteria);
- the outcomes that justify further investment;
- what result counts as "inconclusive", and what (bounded) action follows.

Kill criteria may not be relaxed after results are seen. If they were badly
chosen, document why, and treat any re-test as a new hypothesis on new data.

## 4. Bias and leakage checklist (every study)

- **Look-ahead:** every feature, threshold and normalization uses only data
  available at decision time (trailing windows, point-in-time metadata).
- **Selection / survivorship:** the sample universe is defined from the raw
  record (e.g., all traded instruments), not from today's listings or from
  "successful" or high-lifetime-volume markets.
- **Overlap and clustering:** overlapping events and correlated instruments are
  de-duplicated or handled by clustered inference; the effective sample size is
  stated.
- **Multiple testing:** the number of specifications and segments tried is
  reported; corrections are applied; segments are few and pre-declared.
- **Mechanical artifacts:** bid–ask bounce, price clipping, stale/forward-filled
  prices, percentage returns on low bases, and dropping instruments that settle
  inside the horizon.
- **Data validity:** third-party data is validated against an authoritative
  source on a sample before results are interpreted. Large is not the same as
  correct.
- **Timestamps:** source time vs receive time vs settlement time are
  distinguished; horizons are not shorter than timestamp precision supports.

## 5. Reporting standard

- Report effect sizes with confidence intervals, not only p-values.
- Report null and negative results with the same prominence as positive ones.
- Record data source, data version/hash, code commit, parameters and random
  seeds for every reported number.
- State limitations explicitly, especially what the data cannot show.
- Distinguish verified fact, inference, and assumption.

## 6. Reasoning examples

Unacceptable:

- "Mean return after dislocations is negative, therefore we have a trading strategy."
- "Win rate is 60%, therefore it is profitable."
- "The backtest is profitable before spread and fill assumptions, therefore build the bot."
- "An LLM/Jev agrees the event looks anomalous, therefore trade it."

Acceptable:

- "The raw effect appears statistically robust out of sample, but available
  historical data is insufficient to establish whether a passive order could
  have obtained fills."
- "The effect disappears after controlling for time-to-resolution."
- "The phenomenon exists only in tiny illiquid contracts and likely lacks capacity."
- "The effect does not survive holdout data, so we stop."

## 7. AI in research

LLM- or Jev-generated hypotheses, labels or curation are inputs to be validated
conventionally, never evidence by themselves. Any AI-produced label used in a
study must be versioned, stored verbatim, and assessed for its own error rate.
No AI dependency is used before M6/M7.
