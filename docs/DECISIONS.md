# Decision log

Lightweight architecture decision records. Append new entries; do not rewrite
history. To reverse a decision, add a new entry that supersedes it. The only
permitted in-place edit is a status transition (e.g. `Proposed` → `Accepted`),
recorded with its date and who made it; the decision text is not changed.

Statuses: `Proposed` · `Accepted` · `Superseded by ADR-NNNN` · `Rejected`.
"Origin" records who made the decision: the project owner's brief, or a coding
agent (agent decisions are provisional until the owner accepts them).

Template:

```
## ADR-NNNN — Title
- Date: YYYY-MM-DD
- Status: …
- Origin: owner | agent (<which>)
- Context: why a decision was needed
- Decision: what was decided
- Consequences: what this enables, forbids, or costs
```

---

## ADR-0001 — Research-first, gated milestones

- Date: 2026-10-04
- Status: Accepted
- Origin: owner (initial project brief)
- Context: Engineering effort does not create trading edge. Building
  infrastructure before an edge is demonstrated risks months of wasted work.
- Decision: Work proceeds M0 → R0 → (only if justified) M1 … M10. Each gate may
  end in "stop". No milestone is implemented before the previous gate passes
  and the owner approves.
- Consequences: Early stages are offline and file-based. Live-capable code does
  not exist before M10 (paper execution not before M8).

## ADR-0002 — Venue-neutral core; Polymarket is research data source #1

- Date: 2026-10-04
- Status: Accepted
- Origin: owner (initial project brief)
- Context: The best venue is unknown, venue access for the owner is not
  established, and several candidate venues exist.
- Decision: Core concepts are venue-neutral where the concept is venue-neutral.
  Polymarket is used first as a research data source; it becomes an adapter
  only if justified. No adapters are built for unused venues.
- Consequences: Venue-specific logic is isolated at boundaries. Research code
  that is inherently venue-specific (e.g., R0) is labelled as such and is not
  promoted into the core model.

## ADR-0003 — Deterministic code holds authority; AI is advisory and deferred

- Date: 2026-10-04
- Status: Accepted
- Origin: owner (initial project brief)
- Context: LLM/Jev outputs are useful for semantic uncertainty but are not
  auditable arithmetic and can fail unpredictably.
- Decision: Deterministic code calculates what can be calculated; AI handles
  only genuinely semantic/fuzzy questions; deterministic policy and risk have
  final authority. No LLM or Jev dependency is added before M6/M7.
- Consequences: See `RISK_INVARIANTS.md` INV-05 to INV-09.

## ADR-0004 — No live-trading implementation until legal and venue access are verified

- Date: 2026-10-04
- Status: Accepted
- Origin: owner (initial project brief)
- Context: The owner is based in Switzerland; live-trading availability is not
  established for any venue.
- Decision: Public-data research is in scope. No live-trading code is written
  until current venue terms, geographic restrictions and applicable Swiss rules
  are verified from authoritative sources and recorded here.
- Consequences: See `RISK_INVARIANTS.md` INV-04.

## ADR-0005 — M0 contains documentation only

- Date: 2026-10-04
- Status: Accepted (owner, 2026-10-05; was Proposed 2026-10-04)
- Origin: agent (Claude Code, M0 implementation)
- Context: The brief asks for the minimal foundation and forbids speculative
  infrastructure.
- Decision: M0 adds only `README.md`, `CLAUDE.md`, `AGENTS.md`, `.gitignore`
  and `docs/`. No Python package, dependency manifest, CI, linters, or
  directory skeleton is created until an approved milestone needs them.
- Consequences: Tooling choices (package manager, lint/format, test runner
  configuration) are deferred to R0 approval.

## ADR-0006 — Public-data research may proceed; execution waits for access questions

- Date: 2026-10-05
- Status: Accepted (open question on keyed read-only access resolved by ADR-0013, owner, 2026-10-06)
- Origin: owner
- Context: Live-trading legality and venue access for a Switzerland-based owner
  are unresolved (see ADR-0004).
- Decision: Public-data research (R0) and public-data measurement (M1) may
  proceed without resolving live-trading legality. Live or authenticated
  execution work may not proceed until the Swiss and venue-access questions
  are resolved.
- Consequences: Strengthens ADR-0004 and `RISK_INVARIANTS.md` INV-04. R0 and
  M1 use public data sources. Whether keyed (API-key) **read-only** access to
  public data, e.g. a Polygon RPC key, is permitted has not been decided by
  the owner. It is an open question (R0 preregistration U5), and
  `CLAUDE.md`/`AGENTS.md` currently forbid "API-authentication code".
- Note: wording drafted by the agent from the owner's 2026-10-05 message and corrected before first commit to separate owner wording from agent additions; owner to confirm the wording when committing.

## ADR-0007 — R0 scope: conditional approval, primary dataset, sample periods

- Date: 2026-10-05
- Status: Accepted
- Origin: owner
- Context: The R0 proposal (2026-10-04) was reviewed by the owner.
- Decision:
  - R0 is conditionally approved and **not yet implemented**. Implementation
    waits for an independent review of the frozen research design.
  - Polymarket-v1 is the primary R0 dataset, **conditional on passing K0**
    independent chain validation. The provider's derived fields are not
    ground truth. (The identifiers "Qin & Yang" and Hugging Face
    `TimeSeventeen/Polymarket-v1` were supplied by the agent from search
    excerpts; S0 verifies them.)
  - The exploration period (2025-01-01 → 2025-09-30), embargo
    (2025-10-01 → 2025-10-07) and Holdout A (2025-10-08 → 2026-04-27) are
    approved.
  - Short-duration crypto markets remain a separate stratum, outside the
    pooled primary test.
- Consequences: The preregistration fixes these choices before any outcome
  data is examined.
- Note: wording drafted by the agent from the owner's 2026-10-05 message and corrected before first commit to separate owner wording from agent additions; owner to confirm the wording when committing.

## ADR-0008 — R0 thresholds are research screening thresholds

- Date: 2026-10-05
- Status: Accepted
- Origin: owner
- Context: R0 uses trade-tape measures, not executable P&L.
- Decision: The 1¢ kill and 2¢ continue thresholds are approved as
  **research screening thresholds**. They are not profitability claims.
- Consequences: R0 results are reported as screening outcomes. They are never
  described as tradable edge or P&L.

## ADR-0009 — R0 tooling

- Date: 2026-10-05
- Status: Accepted
- Origin: owner
- Decision: Python 3.12+, uv, Polars, PyArrow, NumPy, SciPy, matplotlib and
  pytest. No Docker, database server, ML, Jev or LLM dependencies.
- Consequences: Any further dependency needs a new decision entry.

## ADR-0010 — V1→V2 regime gate and narrow interpretation of R0 failure

- Date: 2026-10-05
- Status: Accepted; R0b/narrow-M1 procedure superseded by ADR-0014 (owner, 2026-10-06)
- Origin: owner
- Context: As stated by the owner (2026-10-05; not independently verified by
  the agent), Polymarket's 2026-04-28 exchange upgrade involved new exchange
  contracts, a rewritten order book, new collateral, and changed execution
  and fee infrastructure. It separates the R0 data (V1) from the current
  venue (V2). R0 also deliberately omits external-information confirmation.
- Decision:
  - A V1 result alone never graduates a strategy toward execution.
  - If Holdout A passes, first attempt a bounded recent-V2 replication (R0b)
    using existing public data, if comparable data is cheap to obtain.
  - If comparable V2 historical data cannot be obtained without substantial
    new infrastructure, M1 may proceed **only** as a narrow current-V2
    data-collection and measurement exercise.
  - An R0 failure kills or deprioritizes only the *ungated anomalous-flow
    short-horizon reversal* hypothesis. It does not disprove information-gated
    Tripwire/dislocation strategies.
  - Filters are never retrofitted after the holdout is seen. Any
    information-gated version needs its own separately preregistered
    hypothesis.
- Consequences: Implemented by agent-designed rules in the R0
  preregistration §14–§16 (feasibility criteria, replication rule, routing).
  Those details are agent decisions and are recorded as Proposed in ADR-0012.
- Note: wording drafted by the agent from the owner's 2026-10-05 message and corrected before first commit to separate owner wording from agent additions; owner to confirm the wording when committing.

## ADR-0011 — R0 event unit: print-second (Approach A)

- Date: 2026-10-05
- Status: Proposed
- Origin: agent (Claude Code)
- Context: The R0 analysis layer (`daily_aligned/`) does not appear to expose
  transaction or order identifiers (owner-read), and R0 must not approximate
  orders from timestamps. The schema could not be verified directly from the
  agent's environment.
- Decision: The R0 event unit is the **print-second**: all valid rows of one
  market in one block-timestamp second. Detection, `p_end`, one-sidedness and
  a burst/distributed concentration label are defined on dataset fields only.
  Raw Polygon logs are used for K0 validation only. Chain enrichment of every
  candidate window (B-full), event-scoped chain enrichment (B-lite) and
  log-order reconstruction (A2-lite) are assessed and rejected for R0.
  Order-level questions are deferred. S0, run before freeze, re-checks this
  choice against the verified schema.
- Consequences: R0 cannot test order-level "fat-finger" effects (limitation
  L3). No indexer or keyed RPC at analysis scale.

## ADR-0012 — Agent-designed elements of the R0 preregistration v2

- Date: 2026-10-05
- Status: Superseded by ADR-0015 (2026-10-06; v2 replaced by v3)
- Origin: agent (Claude Code), partly in response to an internal adversarial
  review
- Decision: The following are agent design choices, not owner decisions:
  - **Primary statistic:** SSTR measured from a selection-free base (the
    first same-side print ≥ 10 s after the trigger), to remove regression to
    the mean.
  - **Premise test:** H0₃ is tested on a joint displacement-triggered event
    set with a single cooldown.
  - **K0 design:** block-level, two-sided validation; an independent R0
    exclusion rule; multiplicity exactly 1; resolution-layer check; a STOP
    and owner decision if NegRisk fills are systematically absent.
  - **Gate order:** S0 and F0 before freeze.
  - **Fee deduction:** the current schedule applied to V1 with a zero-rate
    floor; the bias against realized fees is measured.
  - **Decision logic:** intersection–union rule with KILL > CONTINUE >
    INCONCLUSIVE precedence; K7 as futility at 2¢; power gate P0 (power 0.80
    at SSTR_fee = 3¢ and β_anom = 1¢; ≥ 50 clusters).
  - **R0b:** feasibility criteria (≥ 8 weeks, ≤ 3 working days, no paid
    source, K0b and F0b), replication = full §14 rules, window fixed in
    advance. Any case outside the owner's narrow-M1 trigger returns to the
    owner.
  - **Amendments:** only in the features-only exploration stage, with owner
    approval; never after the first outcome computation.
  - **Data:** 2022–2024 is not analysed.
  - **S_short membership rule:** duration from the first tape print, crypto
    via the F0 fee-category table or a frozen regex, rules for null
    metadata, and the audit design. The stratum itself is owner-approved
    (ADR-0007).
  - **Review order:** S0/F0 → independent review → freeze → confirmation
    review of the freeze diff.
  - **G-B route:** recorded by the owner. Route 2 (narrow M1) is defined
    operationally. INCONCLUSIVE has no M1 route and returns to the owner.
  - **Bounded bug-fix rule** (R0 and R0b): outcomes are monotone, a KILL
    stays a KILL, and a single owner-recorded fix run can only downgrade
    the outcome.
  - **Step-8 order:** K6 → minimum clusters → decisiveness → calibration
    (Monte-Carlo-aware, enumerated statistics) → P0. Any failure stops
    before unblinding.
  - **G-B routes** are evaluated in order. Raw chain logs count as an R0b
    source within budget. Route 2 means persistent infrastructure or more
    than 10 working days. Feasibility probes are limited to metadata and
    burn-in-week rows. In R0b a K6 hit means NOT REPLICATED.
  - **"V2-era evidence"** for any step toward execution means a
    confirmatory V2 test of UAFR, not cost or book measurement alone.
- Consequences: These are open to change by the independent review or the
  owner before freeze. After freeze they are protected (§17).

## ADR-0013 — Read-only authenticated research data access

- Date: 2026-10-06
- Status: Accepted
- Origin: owner
- Decision: API-key-authenticated **read-only** RPC and data services are
  approved for research and validation.
- Rules:
  - credentials only in environment variables or local secret stores;
  - credentials are never committed;
  - no wallet signing, no authenticated trading, no order submission.
- Consequences: The "no API-authentication code" rule in `CLAUDE.md` and
  `AGENTS.md` is narrowed to authenticated trading/execution and signing.
  Resolves the open question in ADR-0006.

## ADR-0014 — R0 simplified to an alpha scout (v3)

- Date: 2026-10-06
- Status: Accepted
- Origin: owner
- Context: The v2 preregistration had become too complex for R0's purpose:
  a cheap, credible screen for whether better current-market data and
  infrastructure are justified.
- Decision:
  - **Data scope:** R0 analyses `daily_aligned/` Standard Binary markets
    only. `daily_aligned_multi/` / NegRisk is excluded; it may later be a
    separately preregistered hypothesis.
  - **After CONTINUE:** stop. The next task is to design a separately
    preregistered current-V2 replication. No strategy progresses toward
    execution on V1 evidence alone. The v2 R0b/narrow-M1 routing is removed.
  - **Holdout protection:** fixed dates; no holdout outcome inspection during
    exploration; the specification is committed before the holdout analysis;
    the holdout is evaluated once; post-unblinding problems can only weaken
    the conclusion or require a new holdout. Ordinary Git history, separate
    data directories and an explicit `--holdout` flag are sufficient.
  - **Statistics:** one primary 10-minute statistic and test; a market-level
    cluster bootstrap; a minimum sample (otherwise UNDERPOWERED); a premise
    comparison; a gross-magnitude screen (1¢ kill / 2¢ continue, research
    screening only); exploratory robustness summaries.
  - **The delayed base is approved:** reversal remaining after the first
    same-side print ≥ 10 s after the trigger. Reversal completed within 10 s
    is not tested, and a positive result remains a screening result requiring
    M1.
  - The removal of the 2022–2024 descriptive check is confirmed.
- Consequences: Implemented in the R0 preregistration v3.

## ADR-0015 — Agent-designed elements of the R0 preregistration v3

- Date: 2026-10-06
- Status: Accepted with amendments by ADR-0016 and ADR-0017 (owner, 2026-10-06; was Proposed)
- Origin: agent (Claude Code)
- Decision: Within ADR-0014, the agent chose:
  - **Events:** one displacement process with one cooldown; E1/E0 labelled by
    the flow ratio at the trigger second (R ≥ 5).
  - **Premise comparison:** Δ-bucket-reweighted E1 − E0 difference on events
    with a measured SSTR.
  - **Thresholds:** minimum sample of 200 events, 50 markets and 30 markets
    per premise group; concentration rule k = max(10, 5% of markets); liquid =
    above the exploration median of trailing-24 h shares, with ≥ 10 liquid
    events per week; the specific Δ buckets.
  - **K0:** 6 quarterly strata; 20 blocks and 50 rows per stratum; 100 + 100
    resolution checks; material disagreement = < 99% pooled, > 2 unexplained
    mismatches in a stratum, or a systematic pattern.
  - **Exploration:** a stop if mean SSTR₁₀ ≤ 0 or the sample is too small;
    logged amendments of event parameters only.
  - **Fees:** a fixed fee illustration (0.07 · x(1−x)), descriptive only.
- Consequences: Open to change by the independent review or the owner before
  freeze. Open issues O1–O5 are listed in the preregistration §14.

## ADR-0016 — R0 v3: premise comparison, liquid frequency, open issues O1–O5

- Date: 2026-10-06
- Status: Accepted; premise statistic, support rule and settlement treatment amended by ADR-0017 (owner, 2026-10-06)
- Origin: owner
- Decision:
  - **Premise comparison (amends ADR-0015).** The decision-relevant E1-vs-E0
    comparison (K3) uses **all** eligible E1 and E0 events, with exactly the
    primary statistic's zero and settlement rules. The measured-SSTR-only
    comparison is descriptive only and never decides K3. Δ-bucket
    reweighting is kept. Common support: at least 80% of E1 events must lie
    in Δ buckets containing E0 events; otherwise the result is UNDERPOWERED,
    not KILL. The minimum of 30 markets per group is unchanged. No
    propensity scores, matching models, regressions or ML.
  - **Liquid frequency (amends ADR-0015).** K5's threshold is 3 liquid E1
    events per week (was 10). The positive liquid-market LCB requirement is
    kept.
  - **O1:** premise failure KILLs UAFR. Generic reversal, if observed, is a
    separate future hypothesis.
  - **O2:** the anomaly label is frozen at τ₀, when the displacement first
    qualifies.
  - **O3:** exploration amendments are allowed and logged for amendable event
    parameters, and frozen before the holdout.
  - **O4:** the remaining numerical choices in ADR-0015 are approved.
  - **O5:** R0 will be designed to run on the owner's local machine.
    Read-only API/RPC credentials are allowed under ADR-0013.
- Consequences: Implemented in the R0 preregistration v3 §8.2, §8.3, §8.5,
  §8.6, §9 and §14.

## ADR-0017 — R0 v3 fixes from the independent (Codex) review

- Date: 2026-10-06
- Status: Accepted
- Origin: owner (adopting the required findings of the independent review of
  `review/r0-v3` at 2eec52f)
- Decision:
  - **Settlement treatment.** Settlement-value events keep their place in
    every decision denominator, but their decision SSTR is 0. A spread-free
    payout measured against a taker-side base manufactures positive
    "reversal". The payout-based value (SSTR_pay) is descriptive only.
  - **Premise statistic (amends ADR-0016's no-regression restriction).** K3
    requires both LCB(d) > 0 (bucket-reweighted difference) and LCB(β) > 0,
    where β is the E1 coefficient in an OLS of SSTR₁₀ on bucket indicators,
    one common linear Δ term and the E1 indicator, with the existing
    market-cluster bootstrap. No other covariates, propensity scores,
    matching models or ML.
  - **Premise support (amends ADR-0016).** A bucket is supported iff it has
    ≥ 30 distinct E1 markets and ≥ 30 distinct E0 markets. ≥ 80% of E1
    events must lie in supported buckets. Bootstrap draws resample markets
    jointly with full multiplicities and keep the supported set fixed. Any
    draw with an empty supported cell or a rank-deficient fit, or failure of
    support, makes the result UNDERPOWERED. This replaces the global
    30-markets-per-group rule.
  - **Liquid-market floor.** ≥ 30 distinct markets must contribute liquid E1
    events, checked before outcomes; otherwise UNDERPOWERED. The
    3-per-week frequency rule is separate and unchanged.
  - **K0 completeness frame.** Completeness blocks are sampled from Polygon
    block-number ranges for the pinned quarter bounds, independently of the
    provider. Provider IDs may locate records but never define the
    completeness universe.
- Consequences: Implemented in the R0 preregistration v3 §1, §5.1–§5.3, §7,
  §8.2, §8.3, §8.5, §8.6, §9 and §11. The hypothesis (UAFR) is unchanged.

## ADR-0018 — R0 preregistration freeze (r0-freeze-v1)

- Date: 2026-10-06
- Status: Accepted
- Origin: owner
- Context: The independent Codex review of `review/r0-v3` returned **FREEZE**
  on commit `8f3b31da70aa8fa642b37a1ab6fa4c24584e0fd2` (after the required
  fixes recorded in ADR-0017).
- Decision:
  - The R0 v3 preregistration
    (`research/r0_dislocation_reversal/PREREGISTRATION.md`), as reviewed at
    `8f3b31d`, is **approved and frozen**. Its content is unchanged by this
    entry.
  - **No R0 outcome data was inspected before freeze.** No R0 data was
    downloaded, no R0 code was written, and no R0 statistic was computed.
  - The freeze commit is the commit that adds this entry. It is tagged
    `r0-freeze-v1` and becomes the initial `main` baseline (M0 governance
    plus the R0 preregistration).
  - Implementation has **not** started. It requires an explicit owner
    instruction (`CLAUDE.md`, "Current stage"). From freeze on, any
    specification change follows the preregistration §6 rules (logged
    amendments of event parameters only, before the holdout run).
- Consequences: The holdout (2025-10-08 → 2026-04-27) remains unopened. The
  `--holdout` run happens only once, at a later frozen analysis commit
  approved by the owner (§6 step 3).
