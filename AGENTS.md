# Instructions for coding agents and reviewers

This file applies to every coding agent and automated reviewer working in this
repository. `CLAUDE.md` contains the same core rules; keep the two in sync.

## What this project is

Tripwire is a **research project** testing whether structural trading edges
exist. It is not a trading bot. No production trading exists, and profitability
has not been demonstrated. See `README.md`.

## Read before changing anything

1. `docs/RISK_INVARIANTS.md` — non-negotiable; overrides everything else.
2. `docs/RESEARCH_METHOD.md` — how hypotheses are tested and killed.
3. `docs/ARCHITECTURE.md` — intended shape; most of it does not exist.
4. `docs/DECISIONS.md` — accepted decisions; append, never rewrite.

## Current stage

- M0 (documentation foundation) is the only completed work.
- R0 (first research sprint): the preregistration
  (`research/r0_dislocation_reversal/PREREGISTRATION.md`, v3 alpha scout) is
  **frozen** (ADR-0018, commit `287afbe`); never edit it.
- R0 implementation: only Stages A–C are authorized (ADR-0020): project
  foundation, dataset listing/pinning, schema and exploration-only metadata
  inspection. No event detection, outcomes, statistics or K0 until the owner
  authorizes them, and no event detection before the S_short amendment is
  re-frozen. Inspect no R0 outcome data; holdout rows only via the guard
  (ADR-0021). Research operations use the exploration period only; the wider
  pre-holdout range is an access-control notion (ADR-0022).
- A V1-era Polymarket result alone never graduates a strategy toward execution
  (ADR-0010).
- Never implement a later milestone early. If a task seems to require it,
  stop and ask.

## Never

- Write order-capable code, wallet/signing code, or authenticated
  trading/execution code. Read-only API-key access to research data/RPC
  services is allowed (ADR-0013): credentials only in environment variables
  or local secret stores, never committed.
- Commit secrets, credentials, keys, wallet material, or `.env` files.
- Commit market data, logs, or local databases (`data/`, `logs/` are ignored).
- Add LLM or Jev dependencies (deferred to M6/M7).
- Build adapters for venues that are not currently in use.
- Weaken, skip, or loosen a test, tolerance, or invariant to get a green result.
- State venue/protocol behaviour that is not supported by current official
  documentation or direct observation. Label anything unverified as an
  assumption, with source and date.
- Describe a statistical effect as "edge", "alpha", or "profitable".
- Commit or push unless the owner asks.

## Always

- Keep changes scoped to the task. No speculative abstractions or
  infrastructure "for later".
- Prefer simple, deterministic, falsifiable code. Deterministic code
  calculates; AI (later) only advises; deterministic risk decides; abstention
  is a valid outcome.
- Keep core concepts venue-neutral where the concept is venue-neutral; keep
  venue-specific details at boundaries and label venue-specific research code.
- Write tests that could prove the implementation wrong (including
  look-ahead/leakage tests for research code).
- Use only information available at decision time in any signal, feature, or
  threshold.
- Record data source, data version/hash, code commit, and parameters for any
  reported number.
- Record meaningful architectural decisions in `docs/DECISIONS.md`
  (agent decisions as `Proposed`).
- In reports, separate: verified facts · inferences · assumptions · open
  questions requiring the owner.

## Tooling (when code exists)

Python 3.12+, uv, Polars, PyArrow, NumPy, SciPy, matplotlib, pytest
(ADR-0009). No Docker, database server, ML, Jev or LLM dependencies. Any other
dependency needs a decision entry in `docs/DECISIONS.md`.

## For reviewers / auditors

Do not assume the implementing agent is correct. Check in particular:

- Any path by which code could submit orders or touch credentials.
- Any change that weakens `RISK_INVARIANTS.md`, tests, or tolerances.
- Look-ahead bias: thresholds, normalizations, metadata, or labels computed
  with future data; holdout data touched more than once.
- Selection/survivorship bias in how the sample universe is defined.
- Gross results presented as tradable; missing fees, spread, latency, fill and
  adverse-selection assumptions.
- Claims about venue APIs, fees, or settlement without an official source.
- Scope creep beyond the approved milestone.
