# DRAFT amendment A1 — S_short metadata classifier (not applied, not frozen)

Status: **proposal for owner review** (ADR-0020, BLOCKER-1). The frozen
preregistration (`287afbe`) is unchanged. On approval this text becomes
amendment entry A1 in `AMENDMENTS.md`, followed by an owner re-freeze ADR.
Values marked `<…>` are filled from the exploration-only vocabulary run and
audit (§4 below). Until then, no event detection is implemented or run.

## 1. Gap

§4.3 requires that "its category/tags mark it as crypto, **or** a frozen
regex matches its question or slug". The frozen document specifies neither
the regex nor the crypto tag set.

## 2. Proposed replacement text for §4.3 (metadata condition only)

> m ∈ S_short iff:
> - (scheduled end − τ_first(m)) ≤ 24 h, where τ_first(m) is m's first print
>   in the pinned data and *scheduled end* is the value of `<scheduled_end
>   column>` (`<daily_aligned | pinned Gamma snapshot sha256>`); **and**
> - its metadata marks it as crypto: **(i)** a token of its category or tags
>   field, trimmed and compared with `str.casefold`, is in the frozen set
>   T = `<{…}>`; **or (ii)** `re.search(R_q, question, re.IGNORECASE)` matches,
>   with R_q = `<…>`; **or (iii)** `re.search(R_s, slug, re.IGNORECASE)`
>   matches, with R_s = `<…>` (Python 3.12 `re`).
>
> Tokens: a string field is one token, or, if it is a JSON array or object,
> its elements' strings (an object contributes its `label`, `slug` or
> `name`). Strings are not split on commas.
>
> If category and tags are null, (ii)/(iii) alone decide. If question and slug
> are also null, m is not in S_short and is counted (unchanged).
>
> T, R_q and R_s are stored in `s_short_classifier.toml`, SHA-256 `<…>`,
> committed with this amendment. They were designed and audited on
> exploration-period markets only.

Unchanged: S_short's exclusion from every decision population (§4.3, §6 "not
amendable"), the 24 h duration rule, and descriptive reporting (§8.6).

## 3. Why this classifies conservatively

A short crypto market that is missed enters the decision population. A
non-crypto market that is wrongly flagged only leaves it, and the 24 h
duration condition removes most such false positives. The classifier is
therefore tuned for recall on crypto-price markets.

Known residual risk [INFERENCE]: holdout-period markets may use title
patterns that do not appear in exploration (e.g. new market formats). The
tag condition (i) and full asset-name alternatives in R_q reduce, but cannot
remove, that risk. The owner can accept the risk or add patterns before
freeze, but only from exploration-period vocabulary.

## 4. Audit procedure (exploration-period markets only)

1. Run `01_schema.py vocab` on **all** pre-holdout-side files
   (`--sample-every 1`); it keeps only EXPLORATION-period rows (ADR-0022). Record the classifier SHA-256 and the dataset
   revision.
2. Evaluate the draft (`--classifier`). The run writes three deterministic
   audit samples (SHA-256 ordering, fixed salts), 50 markets each:
   - (a) matched;
   - (b) unmatched but hit by the broad design screen;
   - (c) unmatched at random.
3. The owner labels each market as **crypto-price market: yes or no**. The
   question is whether its question or slug concerns a cryptocurrency's price
   or price direction.
4. Proposed acceptance:
   - (a) ≥ 48/50 "yes";
   - (b) ≤ 1/50 "yes";
   - (c) 0/50 "yes".

   Otherwise revise T, R_q or R_s from exploration vocabulary only, re-run
   with **new salts**, and log each iteration in `AMENDMENTS.md` with the
   specification count.
5. Report counts matched by tag only, by regex only, and by both. Report the
   share of exploration markets flagged by the metadata condition. Do **not**
   report or compute anything involving durations, events or outcomes at
   this stage.

## 5. Related clarifications to cite at the re-freeze (already ruled, ADR-0020)

These are recorded in the decision log. Including them in the same
amendment entry makes the re-frozen specification self-contained:

- C-5: holdout counts and support checks → UNDERPOWERED and STOP without
  computing outcomes, otherwise compute outcomes once.
- C-6: the 2026Q2 K0 stratum ends at the pinned dataset-end block.
- C-3: K0 uses its own validation-only path and flag.
- C-4 and C-7: exploration stops are terminal.
- ADR-0021/ADR-0022: the PRE-HOLDOUT access-control boundary at
  2025-10-08T00:00:00Z, and that research operations use the EXPLORATION
  period (2025-01-01 .. 2025-09-30) only.
