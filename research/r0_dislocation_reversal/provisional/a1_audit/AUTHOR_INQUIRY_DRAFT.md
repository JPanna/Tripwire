# DRAFT email to the Polymarket-v1 authors (NOT SENT; owner approval required)

**To:** Boka Qin, Rui Yang (authors, "Polymarket-v1 Database", arXiv:2606.04217)
**Subject:** Polymarket-v1: provenance of `daily_aligned.close_at` and multistrike slug timestamps

Dear Dr. Qin and Dr. Yang,

Thank you for releasing the Polymarket-v1 database. We are using the Hugging
Face dataset `TimeSeventeen/Polymarket-v1` at revision
`5aa1b9d52316a8b2e789e81c8ae42c7ed532e8aa` in a preregistered study, and need
the exact meaning of one metadata field before we rely on it. We would be
grateful for answers to the following:

1. Which original source field was transformed into `daily_aligned.close_at`:
   Polymarket Gamma `endDate`, Gamma `closedTime`, or another field? Was any
   transformation applied (e.g. time zone or rounding)?
2. On what date was the frozen metadata snapshot that `daily_aligned` joins
   (§3.1 of the paper) collected?
3. Can `close_at` reflect changes made after a market began trading (for
   example, an end date that was extended or otherwise edited before the
   snapshot)?
4. Does an original, as-created scheduled end timestamp exist anywhere in the
   underlying data or your construction pipeline (for example, an earlier
   snapshot or a change history)?
5. For the recurring 4-hour "multistrike" crypto markets (slugs like
   `eth-multistrike-4h-{unix}-{strike}`), does the Unix time in the slug
   encode the beginning or the end of the contract window?

Short answers would be very helpful. We will cite the dataset and the paper in
any resulting work.

Kind regards,
[Owner name, affiliation]
