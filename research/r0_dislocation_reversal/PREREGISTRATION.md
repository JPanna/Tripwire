# R0 preregistration — Ungated anomalous-flow short-horizon reversal (UAFR)

| Field | Value |
| --- | --- |
| Version | **v3 — candidate for freeze** (2026-10-06) |
| Supersedes | v2 (2026-10-05); v1 proposal (2026-10-04) |
| Status | Conditionally approved (ADR-0007, ADR-0014). **Not frozen. Not implemented.** No R0 outcome data has been computed or examined. |
| Purpose | **Alpha scout.** A cheap, credible screen. Not publication-grade infrastructure |
| Next step | Independent review, then owner-approved freeze (§6) |
| Governing decisions | `docs/DECISIONS.md`: ADR-0006 to ADR-0010, ADR-0013, ADR-0014, ADR-0016 (owner); ADR-0011 (agent, Proposed); ADR-0015 (agent, accepted with amendments by ADR-0016) |

**Markers**

| Marker | Meaning |
| --- | --- |
| **[OWNER 2026-10-06]** | Stated by the owner from direct inspection of the current dataset documentation |
| **[OWNER 2026-10-05]** | Stated by the owner in the earlier review |
| **[EXCERPT:x]** | From a search-engine excerpt of source x. The page itself could not be fetched from the agent's environment. **Unverified** |
| **[INFERENCE]** | Agent reasoning, not a sourced fact |
| **[VERIFY@K0]** | Checked during data validation (§7), before any outcome computation |

Unmarked statements are definitions or rules imposed by this document.

---

## 0. Question, scope, and evidence levels

**R0 question.** Is there enough evidence of **UAFR** to justify investing in
better current-market data and infrastructure?

**UAFR ("ungated anomalous-flow short-horizon reversal").** On V1-era
Polymarket trade-tape data, a large abrupt price displacement that comes with
anomalous one-sided aggressive flow is followed, within minutes, by reversal
of later same-side trade prints. "Ungated" means no external-information or
fair-value veto is applied.

**Outcomes:** KILL · INCONCLUSIVE · UNDERPOWERED · CONTINUE (§9). All of them
are screening outcomes.

**Evidence levels** (`docs/RESEARCH_METHOD.md`):
- R0 can at most establish a **statistical effect** in historical trade-tape
  data.
- It cannot establish **tradable edge**: no order book, no fill model, no
  costs beyond an illustration.
- It cannot establish **realized live profitability**.
- **None of the R0 statistics (SSTR, SSTR0, RAW0, DTCP, or any fee-adjusted
  variant) is executable P&L, an executable return, or a backtest result.**
  R0 has no contemporaneous order-book state, no queue position, no fill
  probability, no attainable size, and no model of our own market impact.
  Measuring those is the job of later current-market work (M1).

**In scope:**
- Polymarket-v1 `daily_aligned/` (Standard Binary markets only);
- raw Polygon data for validation only (§7).

**Out of scope:**
- NegRisk / multi-outcome markets (`daily_aligned_multi/`);
- order-book data;
- news or information gating;
- LLM, Jev, ML;
- live or authenticated trading;
- V2-era data;
- other venues;
- the 2022–2024 period.

**Time-box:** about 2–3 weeks of effort after freeze.

---

## 1. Hypotheses

Units: probability units. 0.01 is shown as "1¢" per share [INFERENCE: a
winning share redeems for one unit of collateral; VERIFY@K0].

- **Primary.** H₀: E[SSTR₁₀ | E1] ≤ 0 against H₁: E[SSTR₁₀ | E1] > 0. SSTR₁₀
  is the same-side trade-tape reversal at 10 minutes from the delayed base
  (§5). E1 is the anomalous-flow event set (§4). Tested once on the holdout,
  one-sided, with a market-cluster bootstrap (§8).
- **Premise comparison.** Among comparable displacements, anomalous-flow
  events (E1) reverse more than non-anomalous ones (E0) (§8.3).
- **Magnitude screen.** Mean SSTR₁₀ against the owner-approved research
  screening thresholds, **1¢ kill / 2¢ continue**, applied to the **gross**
  trade-tape statistic (ADR-0008). These are screening thresholds, not
  profitability claims.

Rejecting the primary H₀ alone would mean little. Temporary price impact is
common, so CONTINUE also requires the magnitude, premise, concentration and
liquidity conditions (§9).

---

## 2. Data

### 2.1 Polymarket-v1 dataset

The repository is Hugging Face `TimeSeventeen/Polymarket-v1`, with paper
arXiv 2606.04217 [EXCERPT: dataset card / paper]. The implementation records
the exact citation from the dataset card. The licence is CC-BY-4.0
[OWNER 2026-10-05], so every R0 output cites the dataset.

| Fact | Marker |
| --- | --- |
| Coverage 2022-11-21 → 2026-04-28 (V1 exchange era) | [OWNER 2026-10-05] |
| Layers: `OrderFilled/` (raw nominal maker–taker fills); `daily_aligned/` (Standard Binary markets, `neg_risk = false`); `daily_aligned_multi/` (NegRisk multi-outcome, `neg_risk = true`); `CTF/` (lifecycle data including resolutions) | [OWNER 2026-10-06] |
| `OrderFilled/` ≈ 1.2 B rows; `OrderFilled.id` = `chainId_blockNumber_logIndex`; `OrderFilled/` contains `token_amount` | [OWNER 2026-10-06] |
| `block_timestamp` is in seconds; the taker is the aggressor; `p_event` and `D` are the normalized event-axis fields | [OWNER 2026-10-06] |
| No direct transaction hash; no historical CLOB / order-book state in the analysis layer | [OWNER 2026-10-06] |
| V1 external validity to V2 is not guaranteed | [OWNER 2026-10-06] |
| `p_event` = price if `outcome_seq = 1`, else 1 − price; `D` = sign(`taker_direction`) × (±1 by `outcome_seq`). This is the reference-outcome axis | [EXCERPT: paper]; [VERIFY@K0] |

**Rules**
- **Only `daily_aligned/` is analysed.** `daily_aligned_multi/` and NegRisk
  are excluded from R0 entirely: no NegRisk clustering, validation,
  segmentation or fallback logic. If UAFR survives R0, NegRisk can be tested
  later as a separately preregistered hypothesis.
- **Provider-derived fields are not ground truth.** They are validated against
  raw Polygon data on a stratified sample (§7) before any outcome is computed.
- **Version pin.** Record the dataset revision and SHA-256 of every file used.
  The analysis uses only pinned files.
- **Column mapping check (implementation start, metadata only).** Confirm the
  exact `daily_aligned/` column names and types for the roles in §3. If a
  required role is missing or ambiguous: STOP and return to the owner.

### 2.2 Other inputs

- **Raw Polygon logs** (V1 CTF Exchange, ConditionalTokens): validation only
  (§7), never analysis variables. Contract addresses and ABIs are taken from
  verified contract source [VERIFY@K0].
- **Market metadata** (category/tags, originally scheduled end time,
  question/slug): from `daily_aligned/`'s joined metadata, or, if absent, from
  **one** pinned Gamma API snapshot of those fields only, with retrieval time
  and SHA-256 recorded. Metadata is used only for the S_short stratum and for
  descriptive segments. It is never used for event conditions (a)–(f), for
  resolution, or for the settlement value.
- **Access.** Read-only API-key access to RPC and data services is permitted
  (ADR-0013). Credentials live only in environment variables or local secret
  stores and are never committed. No wallet signing, authenticated trading or
  order submission.

---

## 3. Units, arithmetic, rows

**Units and arithmetic**
- Prices are converted to integer micro-units (µ = 10⁻⁶) and shares to
  integer micro-shares. Each is rounded half-even **once** at load.
- Derived quantities (VWAPs, ratios, medians, σ̂ including its factor
  1.4826 = 14826/10000) are exact rationals of those integers.
- **Every threshold comparison is exact**, by integer cross-multiplication or
  exact rationals. No floating-point comparison decides event membership.

**Row fields** (one market m = one `condition_id`):

| Symbol | Meaning |
| --- | --- |
| τ_r | block timestamp, integer seconds |
| p_r | `p_event`, reference-outcome price, in (0, 1) |
| D_r | aggressor direction ∈ {+1, −1} on the same axis |
| q_r | shares. Taken from a share-quantity column if `daily_aligned/` has one; otherwise derived from `usdc_amount` / `price` with the gross-or-net-of-fee formula that K0 validates (§7) |

**Rows used**
- Exclude malformed rows (a required field missing or out of range).
- Exclude rows at or after the market's resolution time `t_res(m)` (§5.3).
- Count both exclusions per month.

**Symmetry.** Swapping which outcome is the reference, or recording a print
on the complementary token, must leave events and statistics unchanged up to
sign. Tested (§13).

**Print-second.** A print-second (m, τ) is a second τ with ≥ 1 used row in m.
A **side-s print-second** has ≥ 1 used row with D = s.
- `P^s(m,τ) = Σ_{D=s} p·q / Σ_{D=s} q`, the side-s VWAP.
- `Q(m,I)` and `Q^s(m,I)` are shares in interval I, all sides or side s.

Print-seconds are clock units. **No transaction or order identity is ever
inferred from timestamps** (ADR-0011).

---

## 4. Event construction (causal)

Detection runs continuously from 2025-01-01 00:00:00 to 2026-04-27 23:59:59
UTC. Trailing inputs may use rows from 2024-12-30 23:59:00. No pre-2025 events
or outcomes are analysed.

### 4.1 Quantities at a side-s print-second (m, τ)

| Quantity | Definition |
| --- | --- |
| Formation window | (τ − 60, τ] |
| Baseline window B(τ) | [τ − 60 − 86 400, τ − 60) |
| Anchor a^s | P^s at the latest side-s print-second τ_a ≤ τ − 60. Requires τ − 60 − τ_a ≤ 900 s |
| p_end | P^s(m, τ) |
| Displacement Δ | s · (p_end − a^s), same side to same side |
| σ̂^s(τ) | max(0.01, 1.4826 · MAD{c_k}), with c_k = L^s(k) − L^s(k−1). L^s(k) is P^s at the latest side-s print-second in UTC minute k. Only minutes k where **k and k−1 both contain side-s prints and both lie fully inside B(τ)** count. MAD = median\|c_k − median(c)\|. Requires ≥ 30 such k |
| One-sidedness O | Q^s(m,(τ−60, τ]) / Q(m,(τ−60, τ]) |
| Baseline flow b(τ) | median of Q(m, minute) over non-empty minutes fully inside B(τ) |
| Flow anomaly R | Q(m,(τ−60, τ]) / b(τ) |
| Liquidity L | Q(m, B(τ)), trailing 24-h shares (used in §8.5) |

Measuring Δ and σ̂ same-side reduces first-order bid–ask bounce
[INFERENCE; depends on fill-price semantics, VERIFY@K0].

### 4.2 Displacement events E_Δ, and the anomaly label

A side-s print-second (m, τ) is a **displacement trigger** iff all of the
following hold:
- (a) Δ ≥ 0.05;
- (b) Δ ≥ 4 · σ̂^s(τ);
- (c) O ≥ 3/4;
- (d) a^s ∈ [0.05, 0.95] and p_end ∈ [0.03, 0.97];
- (e) eligible: the anchor exists and is fresh, σ̂^s is defined, and b(τ) > 0;
- (f) not in cooldown: τ > τ₀_prev + 3 600, where τ₀_prev is m's previous
  event time.

**Event time and label**
- τ₀ is the earliest trigger in m. Both sides cannot trigger at the same τ,
  because (c) requires O > 1/2.
- **E1 (anomalous):** R(τ₀) ≥ 5. **E0 (non-anomalous):** R(τ₀) < 5.
- One process with one cooldown produces both groups. Each episode therefore
  yields one event, labelled by its flow at the moment the displacement first
  qualifies. E1 and E0 events are measured at the same stage of an episode.

**Periods**
- Events whose τ₀ falls in the embargo start a cooldown but are not analysed.
- Markets in S_short (§4.3) are detected the same way but kept in a separate
  set.

**Causality.** Every input at τ uses only rows with τ_r ≤ τ, plus τ_first and
whitelisted metadata for S_short. Detection never uses later rows, t_res, or
outcomes. Tested (§13).

**Robustness variants** (exploratory; never decide), one at a time:
- formation window 30 s or 300 s, with b(τ) computed over bins of the same
  length;
- factor in (b) of 3 or 6;
- threshold in (c) of 0.6 or 0.9;
- label threshold 3 or 10.

### 4.3 Short-duration crypto stratum (S_short), excluded from decisions

m ∈ S_short iff:
- (scheduled end − τ_first(m)) ≤ 24 h, where τ_first(m) is m's first print in
  the pinned data; **and**
- its category/tags mark it as crypto, **or** a frozen regex matches its
  question or slug.

If metadata is null, the regex alone decides; if question and slug are also
null, m is not in S_short and is counted.

S_short events are reported descriptively and never enter a decision.

---

## 5. Outcome statistics (trade-tape statistics, not P&L)

### 5.1 Primary: SSTR, from a delayed base

**Base.** For each event and horizon h ∈ {30 s, 2 min, **10 min**, 60 min}:
- τ_b = the first side-s print-second in [τ₀ + 10 s, τ₀ + h).
- **B = P^s(m, τ_b).**

**Later reference X_h**
1. If t_res ∈ (τ₀, τ₀+h] and no τ_b exists: flagged
   **settled-before-base**, SSTR_h = 0.
2. Else if no τ_b exists: flagged **no-base**, SSTR_h = 0.
3. Else if t_res ∈ (τ_b, τ₀+h]: X_h = v(m), the settlement value (§5.3).
4. Else X_h = P^s at the latest side-s print-second in (τ_b, τ₀+h]. If there
   is none, X_h = B, flagged **no-update** (SSTR_h = 0).

**`SSTR_h = s · (B − X_h)`.** Positive means later same-side prints moved back
toward the pre-move level. The **primary statistic** is the event-weighted
mean of SSTR at h = 10 min (SSTR₁₀) over holdout E1 events.

**What the delayed base does and does not do** (owner-approved, ADR-0014):
- It reduces regression-to-the-mean bias from selecting an extreme trigger
  print. The base B is never used in event selection.
- It **cannot detect reversal completed within the first 10 seconds** after
  the trigger. Such reversal is not tested by R0.
- Same-side print arrival after the base may itself depend on the price path.
  For example, contrarian buyers may arrive after down-ticks. That can bias
  SSTR in either direction.
- A positive result is therefore a **screening result** that requires
  current-market measurement (M1 or its successor) before any further
  conclusion.

### 5.2 Descriptive statistics (never decide)

- **SSTR0** (trigger-based) = s · (p_end − X0_h). X0_h is v(m) if t_res ∈ (τ₀,
  τ₀+h]; otherwise the latest side-s print-second in [τ₀+1, τ₀+h]; otherwise
  p_end. It includes regression to the mean on the selected print, any
  reversal inside the first 10 s, and differences in the zero rules, and is
  reported under that label.
- **RAW0**: like SSTR0 but using all-side prints. RAW0 − SSTR0 shows the size
  of bid–ask bounce.
- **DTCP** (delayed trade-tape cost proxy), defined only when both references
  exist:
  - e = P^{−s} at the first opposite-side print-second in [τ₀+10, τ₀+h);
  - x = P^s at the first side-s print-second in [τ₀+h, τ₀+h+600], or v(m) if
    resolution comes first;
  - **DTCP = s · (e − x)**.

  It uses other traders' prints as reference prices. It does not show that any
  order could have traded there.
- **Fee illustration:** SSTR₁₀ − 0.07 · x(1−x), and DTCP − 0.07 · [e(1−e) +
  x(1−x)] (x = the later reference price, or 0 for a settlement value; the
  formula and rate are [EXCERPT: Polymarket fees page], unverified). This shows
  the order of magnitude of taker fees only. It is not a cost model and never
  decides.
- **Derived:** f = SSTR/Δ; P(f ≥ ½); P(f < 0); P(f ≤ −½); quantiles 1/5/25/
  75/95/99; and the shares of settled-before-base, no-base, no-update and
  settlement-value cases.

### 5.3 Resolution and settlement value

- **t_res(m)** = block timestamp of the condition's resolution event in the
  pinned `CTF/` layer. If there is none, t_res = +∞ (unresolved).
- **v(m)** = the reference outcome's payout fraction (payout numerator ÷ sum of
  numerators). The `outcome_seq` ↔ CTF outcome-slot mapping is checked at K0.
- Metadata is never used for t_res or v(m).
- A settlement value carries a mechanical half-spread relative to a taker-side
  base [INFERENCE]. Its share is reported, and results excluding
  settlement-value events are a robustness summary.

---

## 6. Periods and protocol

| Period | Dates (UTC, inclusive) |
| --- | --- |
| Exploration | 2025-01-01 → 2025-09-30 |
| Embargo | 2025-10-01 → 2025-10-07 |
| **Holdout** | 2025-10-08 → 2026-04-27 (202 days) |

These are approved (ADR-0007). Event times τ₀ must fall in a period. Outcome
windows may extend beyond it. Horizons that extend past the dataset end are
dropped for that event, and counted.

**Steps**

1. **Data readiness.** Column-mapping check (§2.1), then K0 validation (§7).
   Failure → STOP.
2. **Exploration.**
   - Uses `data/exploration/` only. The holdout lives in `data/holdout/`, and
     every script refuses to read it unless invoked with an explicit
     `--holdout` flag.
   - All analyses may run on exploration data. **No holdout outcome may be
     computed or inspected.**
   - Every change to the specification is logged in `AMENDMENTS.md` with date,
     reason, what changed, and the number of specifications tried so far.
   - **Not amendable:** the periods, the Standard-Binary-only scope, the
     primary statistic (delayed base, SSTR₁₀, §5.1), the decision rules and
     thresholds (§9), the minimum-sample rule, and S_short's exclusion from
     decisions.
   - Event parameters (§4.2 thresholds, label threshold) may be amended, with
     the log.
   - **Exploration stop:** if exploration E1 has fewer than 200 events or 50
     markets, stop as UNDERPOWERED. If exploration mean SSTR₁₀ ≤ 0, stop as
     KILL (exploration-only evidence). In both cases the holdout stays
     unopened.
3. **Freeze.**
   - Commit the final specification (this document plus amendments), the
     analysis code, and the exploration-derived liquidity cut-point c (§8.5).
   - Record the commit hash in `docs/DECISIONS.md`.
   - The owner approves the holdout run.
4. **Holdout, once.** Run `--holdout` at the frozen commit. It first evaluates
   the minimum-sample rule from counts, then computes outcomes and applies §9.
   All outputs are committed and reported in full, whatever the result.
5. **After the holdout.**
   - A bug or specification problem found later is reported alongside the
     original result. Corrections can only **weaken** the conclusion: the
     less favourable of the original and corrected outcomes stands.
   - If the problem invalidates the result, the outcome is INCONCLUSIVE, and
     any re-test needs a **new holdout** (e.g. forward V2-era data under its
     own preregistration).
   - The holdout is never re-run to improve a result.

---

## 7. K0: independent data validation (sample-based)

**Goal.** Before any outcome is computed, show on a defensible random sample
that `daily_aligned/` matches raw Polygon data. This is not an indexer or a
population reconstruction.

**Preparation** (committed before K0 runs):
- Verify contract addresses, ABIs and fill-event semantics from verified
  contract source (V1 CTF Exchange and ConditionalTokens) [VERIFY@K0]. This
  covers which events a match emits, which field holds the aggressor, how
  complementary (mint/merge) matches appear, and the fill-price semantics.
- Write the independent derivations, using chain data and the verified
  semantics only:
  - token → (condition, outcome slot);
  - shares and price from amounts;
  - reference-outcome price p′;
  - aggressor direction D′;
  - settlement value v′ from resolution payouts;
  - an independent **non-economic-event rule**, e.g. duplicate
    restatements of a match. It uses only the event, its transaction or
    block, and fixed verified addresses.
- If verified semantics do not allow any of these derivations: **K0 FAILS**.

**Sample** (seed 20261005). Strata: calendar quarters 2025Q1 → 2026Q2 (6
strata), Standard Binary markets only.
- **Completeness:** 20 random blocks per stratum containing ≥ 1 fill emitted
  by the V1 CTF Exchange, the Standard Binary venue [INFERENCE; VERIFY@K0].
  All economic fills from that contract in each block are compared with
  `daily_aligned/`. `OrderFilled.id` (block number, log index) may be used to
  locate logs.
- **Precision:** 50 random `daily_aligned/` rows per stratum, drawn before any
  validity filtering, each reconciled against its block.
- **Resolution:** 100 random markets with a `CTF/` resolution, and 100 random
  study-period markets without one (checked as unresolved on chain at the
  dataset end).

**Matching.** Within a block-second, rows are matched as multisets on (token
ID, maker, taker, USDC amount). Price, shares, direction and timestamp are
then compared.

**Checks** (all required)

| Check | Pass condition |
| --- | --- |
| `p_event` mapping (incl. `outcome_seq` ↔ CTF slot) | p within 1 µ of p′; slot correct |
| D / aggressor direction | D = D′ |
| Quantity derivation | Shares within max(1 µshare, 10⁻⁶ relative) under one gross-or-net formula. Both formulas are evaluated and the matching one is selected |
| Timestamp interpretation | τ_r equals the block header time (s) |
| CTF resolution mapping | t_res and v match the chain |
| Relayer filtering | The provider's filtering agrees with the independent rule. Every disagreement is explained |
| Completeness | Economic fills in sampled blocks are present in `daily_aligned/` |
| Precision | Sampled `daily_aligned/` rows correspond to economic fills, each **exactly once** |

**Material disagreement** is any check below 99% agreement pooled, any
stratum with more than 2 unexplained mismatches on a check, or any systematic
pattern (e.g. all mint/merge fills wrong). Material disagreement → **STOP**.
Fix or replace the data with owner approval, re-run K0 with seed 20261005 + n,
and keep the failing sample as a regression test.

**Output:** `K0_REPORT.md`, containing agreement rates, explained
disagreements, and the selected shares formula. It contains no outcome
variables.

---

## 8. Statistics

### 8.1 Inference

- **Cluster** = market (`condition_id`).
- **Percentile cluster bootstrap:** resample markets with replacement,
  B = 10 000, seed 20261006.
- **LCB** = the 5th percentile of the bootstrap statistic (one-sided 95%).
- No other inferential machinery. If clusters are too few for the bootstrap
  to be credible, the outcome is UNDERPOWERED (§8.2), not a new method.

### 8.2 Minimum sample (UNDERPOWERED)

Evaluated from counts before outcomes, in exploration and again at the start
of the holdout run. The result is UNDERPOWERED if any of these hold:
- fewer than **200** E1 events;
- fewer than **50** markets with E1 events;
- in the premise comparison (§8.3), fewer than **30** markets in either the
  E1 or the E0 group;
- in the premise comparison, fewer than **80%** of E1 events lie in Δ
  buckets that contain at least one E0 event (common support). The premise
  comparison is then not sufficiently identified for this scout.

### 8.3 Premise comparison (E1 vs E0)

- **Events used:** **all** eligible E1 and E0 events. SSTR₁₀ follows exactly
  the primary statistic's zero and settlement rules (§5.1): settled-before-base,
  no-base and no-update events count as 0, and settlement values are
  included. No event is dropped based on post-event activity. Zero rates are
  reported by group.
- **Δ buckets** (fixed): [0.05, 0.075) · [0.075, 0.10) · [0.10, 0.15) ·
  [0.15, 0.20) · [0.20, 0.30) · [0.30, 1].
- **Statistic:** d = Σ_b w_b · (mean SSTR₁₀ of E1 in b − mean SSTR₁₀ of E0 in
  b), with w_b = E1's share of events in bucket b. This reweights E0 to E1's
  displacement mix. Buckets with no E0 events are dropped and w is
  renormalized; this is reported.
- **Inference:** LCB(d) from the §8.1 bootstrap, resampling markets with all
  their E1 and E0 events.
- **Common support:** the 80% rule of §8.2 is checked from counts before
  outcomes. If it fails, the result is UNDERPOWERED, not KILL.
- **Descriptive only:** the same comparison restricted to events with a
  measured SSTR₁₀ (cases 3–4 of §5.1) is reported in §8.6. It never decides
  K3.

### 8.4 Concentration

Let k = max(10, ⌈0.05 · N_m⌉), where N_m is the number of holdout markets
with E1 events. Remove the k markets with the largest market-level ΣSSTR₁₀,
then recompute LCB(mean SSTR₁₀).

### 8.5 Liquid-market frequency

- **Liquidity cut-point c:** the median of L (§4.1) over exploration E1
  events, frozen at freeze.
- An event is **liquid** if L ≥ c.
- **Frequency:** holdout liquid E1 events ÷ (202/7). The threshold is 3 per
  week, i.e. about 87 liquid events over the holdout. It rejects only
  phenomena too rare to justify further data infrastructure; capacity is not
  known at this stage.
- **Effect:** LCB(mean SSTR₁₀) over holdout liquid E1 events.

### 8.6 Exploratory robustness summaries (reported; never decide)

- Other horizons; the §4.2 robustness variants.
- Market-equal weighting.
- Excluding settlement-value events; excluding settled-before-base events.
- Sub-periods before and after the reported fee rollout around 2026-03-06
  [EXCERPT: Polymarket fees page].
- Segments, marginal only: Δ bucket; anchor price (tails vs middle);
  liquidity half; time to scheduled end; category.
- S_short.
- SSTR0, RAW0, DTCP, the fee illustration, and the f-distribution.
- The premise comparison restricted to events with a measured SSTR₁₀.

---

## 9. Decision rules (holdout; evaluated in this order)

| Step | Rule | Outcome if triggered |
| --- | --- | --- |
| 0 | Minimum sample fails (§8.2) | **UNDERPOWERED** |
| K1 | Mean SSTR₁₀ ≤ 0, or LCB(mean SSTR₁₀) ≤ 0 | **KILL** |
| K2 | Mean SSTR₁₀ < 0.01 (1¢) | **KILL** |
| K3 | Premise: LCB(d) ≤ 0 (§8.3) | **KILL** (UAFR premise unsupported) |
| K4 | Concentration: LCB ≤ 0 after removing the top k markets (§8.4) | **KILL** |
| K5 | Liquid frequency < 3 per week, or liquid LCB ≤ 0 (§8.5) | **KILL** |
| I1 | 0.01 ≤ mean SSTR₁₀ < 0.02 (between 1¢ and 2¢) | **INCONCLUSIVE** |
| — | Otherwise, i.e. all of the above pass and mean SSTR₁₀ ≥ 0.02 | **CONTINUE** |

**CONTINUE requires all six owner requirements:**
1. a positive effect;
2. a one-sided 95% cluster-bootstrap LCB > 0;
3. a gross magnitude ≥ 2¢;
4. anomaly events reverse more than comparable non-anomaly displacements;
5. the effect is not concentrated in a handful of markets;
6. the effect is frequent and present in liquid markets.

---

## 10. Interpretation and next steps

**KILL:** *"There is not enough evidence to justify prioritizing ungated
anomalous-flow short-horizon reversal (UAFR), as measured on V1-era
Polymarket Standard Binary trade-tape data, excluding short-duration crypto
markets."*
- Add "(exploration-only evidence)" for an exploration stop.
- Under K3, add: "Any generic reversal observed is reported descriptively and
  may motivate a separate hypothesis."

**UNDERPOWERED:** *"UAFR could not be tested with adequate sample size;
absence is not shown."*

**INCONCLUSIVE:** stop and return to the owner. No re-analysis of the same
holdout under a changed specification.

**CONTINUE:** **stop.** The next task is to design a separately preregistered
current-V2 replication. **No strategy progresses toward execution on V1
evidence alone** (ADR-0010, ADR-0014).

**A stop does not show that** the following fail:
- information-gated (fair-value-veto) Tripwire strategies;
- passive liquidity provision at dislocated prices;
- order-level "fat-finger" effects;
- reversal completed within 10 s;
- NegRisk markets;
- S_short markets;
- the current V2 regime;
- other venues.

**No retrofitting.** After the holdout is run, no filter (news, category,
liquidity, time, wallet, or anything else) is added to rescue UAFR. Any
information-gated version is a separate, separately preregistered hypothesis.

**Holdout use.** If never opened, the holdout stays available to future
preregistrations. Once run, it is spent for UAFR and all its variants.

---

## 11. Leakage checklist

| Risk | Mitigation |
| --- | --- |
| Future rows in thresholds | σ̂, b and the anchor use only rows before τ − 60 or at most τ − 60; tested |
| Selection on the extreme trigger print (regression to the mean) | Delayed base (§5.1); SSTR0 descriptive only |
| Bid–ask bounce | Same-side Δ, σ̂ and SSTR; RAW0 diagnostic |
| Metadata snapshot (end dates edited later, tags added) | Used only for S_short and descriptive segments; never for events (a)–(f), t_res or v(m) |
| Resolution outcome | Used only as a realized value inside the horizon, from on-chain `CTF/` data |
| Dropping markets that settle inside the horizon | Settlement-inclusive; zero-rule cases flagged and counted |
| Percentage returns on low prices | Probability-unit differences only |
| Stale forward-filled prices | Zero rules flagged; no forward-filled prices used as the base |
| Provider cleaning | Independent rule and K0 (§7) |
| Holdout peeking | Separate directory; `--holdout` flag; one run at the frozen commit; Git history |
| Post-outcome respecification | Non-amendable items (§6); amendments logged; corrections only weaken |
| Prior work overlapping the holdout dates, seen at headline level via excerpts (e.g. Ibrahim & Zaki, 2024–2025; OpenMarket, Feb–May 2026) | No amendment may cite or be motivated by their holdout-period results |

---

## 12. Limitations

- No executable P&L: no book, queue, fill probability, attainable size or
  impact.
- Reversal within 10 s of a trigger is not tested. Nothing below about 30 s is
  interpretable: block timestamps are seconds and on-chain time follows the
  off-chain match [INFERENCE].
- No order identity: R0 cannot test single "fat-finger" orders.
- Informed and uninformed moves are mixed (ungated), which plausibly dilutes
  any effect.
- V1 only; V2 validity is not guaranteed [OWNER 2026-10-06].
- Same-side arrival may be path-dependent (§5.1).
- Historical aggressor direction may not be observable in real time with the
  same accuracy.
- Capacity, competition, fees and adverse selection are not modelled.
- Dataset correctness is checked on a sample only (§7).
- Standard Binary markets only; S_short excluded from decisions.

---

## 13. Implementation sketch (not to be built before approval)

**Stack:** Python 3.12+, uv, Polars, PyArrow, NumPy, SciPy, matplotlib,
pytest (ADR-0009). HTTP, JSON-RPC, hashing and exact rationals use the
standard library. No Docker, database server, ML, Jev or LLM.

```
research/r0_dislocation_reversal/
  PREREGISTRATION.md  AMENDMENTS.md  K0_REPORT.md
  r0/  config.py  io.py  chain.py  validate.py  events.py  outcomes.py  stats.py  report.py
  scripts/  01_k0.py  02_explore.py  03_holdout.py      # 03 refuses to run without --holdout
  tests/
  results/
data/exploration/  data/holdout/                         # gitignored
```

**Tests that could prove the code wrong:**
- **causality:** changing rows after τ, t_res or outcomes never changes
  detection at τ;
- **regression-to-the-mean null:** latent martingale plus within-side print
  noise under full E1 selection gives SSTR ≈ 0 while SSTR0 > 0;
- **bounce null:** SSTR ≈ 0 and RAW0 > 0;
- **planted effect:** a known reversal is recovered;
- **symmetry:** swapping the reference outcome changes nothing;
- **exact thresholds:** at every boundary;
- **σ̂ pairs:** an alternating-minute market is ineligible;
- **sign conventions:** for s = ±1 and all zero-rule cases;
- **bootstrap sanity:** coverage on simulated clustered data;
- **holdout guard:** a script without `--holdout` cannot read `data/holdout/`.

**Seeds:** 20261005 (K0), 20261006 (bootstrap).

---

## 14. Owner decisions on the former open issues (ADR-0016, 2026-10-06)

| # | Issue | Decision |
| --- | --- | --- |
| O1 | Failure of the premise comparison | **KILL UAFR.** Any generic reversal observed is a separate future hypothesis |
| O2 | Anomaly label timing | **Frozen at τ₀**, when the displacement first qualifies |
| O3 | Exploration amendments | **Allowed and logged** for amendable event parameters; frozen before the holdout |
| O4 | Numerical choices | **Approved as written**, except: liquid frequency is **3 per week**; the premise comparison adds the **80% E1 common-support** requirement |
| O5 | Where R0 runs | **The owner's local machine.** Read-only API/RPC credentials are allowed under ADR-0013 |

---

## Revision history

**v3 (2026-10-06)** simplifies v2 into an alpha scout (ADR-0014).
- Kept: UAFR, the print-second unit, the delayed base, same-side
  measurement, causal construction, exploration → freeze → holdout once, K0,
  exact thresholds, the not-P&L statement, S_short excluded, and no
  LLM/Jev/ML/book/live trading.
- Removed: the R0b/V2 protocol, NegRisk, cryptographic unblinding and
  restricted-reader machinery, nested bootstrap-t and calibration regimes,
  simulated-power gates, decisiveness gates, and fee-schedule gates.
- Changed:
  - E1 and E0 are labels within one displacement process;
  - the premise comparison is Δ-bucket-reweighted on measured events;
  - the magnitude screen uses gross SSTR₁₀ (v2: fee-adjusted), with fees as a
    descriptive illustration only;
  - the decision table is one screen;
  - K0 is a stratified-sample validation with a single STOP rule;
  - holdout protection relies on Git history, separate directories and a
    `--holdout` flag;
  - read-only authenticated data access is allowed (ADR-0013);
  - Standard Binary markets only.

**v2 (2026-10-05)** and **v1 (2026-10-04)** are preserved in the session
record; see the v2 revision history for v1 → v2.
