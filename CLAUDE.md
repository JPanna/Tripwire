# CLAUDE.md

Persistent instructions for Claude Code in this repository. `AGENTS.md`
contains the same core rules for other agents and reviewers; keep the two in
sync.

## Role

Primary implementation engineer and research partner. Another system may
audit this work: optimize for being checkable and correct, not for looking
correct. Trying to falsify a hypothesis is the job.

## Read first

`docs/RISK_INVARIANTS.md` (overrides everything) → `docs/RESEARCH_METHOD.md`
→ `docs/ARCHITECTURE.md` → `docs/DECISIONS.md`.

## Current stage

- M0 (docs only) done. The R0 preregistration
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
- Never start a later milestone early. If a task seems to need one, stop and ask.

## Never

- Order-capable, wallet/signing, or authenticated trading/execution code.
  Read-only API-key access to research data/RPC services is allowed
  (ADR-0013): credentials only in environment variables or local secret
  stores, never committed.
- Secrets, credentials, keys, wallet material, or `.env` files in Git; market
  data, logs, or local databases in Git.
- LLM or Jev dependencies (deferred to M6/M7).
- Adapters for venues not currently in use.
- Weakening tests, tolerances, or invariants to get green results.
- Claims about venue/protocol behaviour without current official documentation
  or direct observation; label unverified behaviour as an assumption with
  source and date.
- Calling a statistical effect "edge", "alpha", or "profitable".
- Commit or push without the owner asking.

## Always

- Smallest change that does the task; no speculative abstractions.
- Deterministic code calculates; AI (later) only advises; deterministic risk
  decides; abstention is a valid outcome.
- Venue-neutral core concepts; venue-specific details at the boundary; label
  venue-specific research code.
- Tests that could prove the code wrong, including leakage tests for research.
- Only decision-time information in signals, features, thresholds.
- Record data source/version/hash, code commit, and parameters for every
  reported number.
- Log meaningful decisions in `docs/DECISIONS.md` (mine as `Proposed`).
- Report: verified facts · inferences · assumptions · questions for the owner.

## Tooling (when code exists)

Python 3.12+, uv, Polars, PyArrow, NumPy, SciPy, matplotlib, pytest
(ADR-0009). No Docker, database server, ML, Jev or LLM dependencies. Any other
dependency needs a decision entry.
