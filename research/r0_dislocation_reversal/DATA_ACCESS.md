# R0 data access: layout, holdout guard, and how to run Stages A–C

Governing decisions: ADR-0019 (tooling), ADR-0020 (owner rulings), ADR-0021
(this design), ADR-0022 (owner clarifications: PRE-HOLDOUT vs EXPLORATION;
domain checks) and ADR-0023 (hardening after the independent audit). The
frozen preregistration is not changed by anything here.

## 1. Two notions of "before the holdout"

| Term | Range (UTC) | Used for |
| --- | --- | --- |
| **PRE-HOLDOUT** | every row with `block_timestamp < 1759881600` (2025-10-08T00:00:00Z): trailing rows from 2024-12-30, the exploration period, the embargo | low-level access control only (`Scope.PRE_HOLDOUT`, manifest side `pre_holdout`, download part `pre-holdout`) |
| **EXPLORATION** | 2025-01-01T00:00:00Z .. 2025-09-30T23:59:59Z only | all research operations: S_short vocabulary, classifier audits, domain checks, all exploration analysis |
| EMBARGO | 2025-10-01 .. 2025-10-07 | only what the frozen specification authorizes (e.g. trailing inputs and cooldown continuity) |
| HOLDOUT | rows `>= 2025-10-08T00:00:00Z` | nothing before the analysis freeze |

The pre-holdout range is never called "exploration": it is wider than the
exploration period.

## 2. Layout

All data lives under the data root (`$R0_DATA_ROOT`, default `<repo>/data`),
which Git ignores.

```
data/
  raw/<owner>__<name>@<revision-sha>/<repo path>   immutable raw-source cache
  exploration/inspection/                          Stage C outputs (exploration period only)
  holdout/                                         holdout partition, built only after the
                                                   analysis freeze, by the frozen loader
```

- **Raw cache.** Whole upstream files at one pinned dataset commit, each
  verified against `DATA_MANIFEST.json` (size and SHA-256, or the git blob
  SHA-1 for non-LFS files) and made read-only. A raw file may hold rows from
  both sides of the boundary.
- **Derived partitions** (Stage E, not built yet) are derived from raw rows by
  timestamp. The pre-holdout partition is built once, hashed, and never
  rebuilt or replaced during the holdout run; the holdout partition is built
  after the freeze by the same frozen loader.

## 3. The access-control rule

A row is **holdout-side** iff `block_timestamp >= 1759881600`. Everything
earlier is **pre-holdout**. The rule is applied to **rows**, not files: a
file that straddles the boundary is split mechanically and its pre-holdout
rows are kept. `CTF/` rows follow the same rule.

## 4. How the guard works

1. **One reader.** `r0/rawread.py` is the only code that parses Parquet. A
   test (`test_only_rawread_parses_parquet`, AST- and text-based) fails if any
   other module or script reads Parquet or Arrow datasets directly.
2. **Scoped row reads.** `read_rows(..., scope=Scope.PRE_HOLDOUT)`:
   - skips every row group whose timestamp statistics start at or after the
     boundary (those bytes are never read);
   - filters the remaining rows to `ts < boundary`;
   - drops rows with a null timestamp;
   - refuses timestamps that are not plausible epoch seconds (e.g.
     milliseconds or days), since the boundary comparison would then be
     meaningless.

   Only rows that pass leave the function. Callers doing research operations
   then keep only EXPLORATION-period rows (`vocab`, `--domain-checks`).
3. **Holdout scope needs authorization.** `Scope.HOLDOUT` requires a
   `HoldoutAuthorization`. Only `authorize_holdout(True, purpose)` creates one,
   from an explicit command-line flag; direct construction raises. No
   Stage A–C script calls it (`test_no_stage_a_c_script_authorizes_holdout`).
4. **Paths.** `check_readable` compares both the literal and the
   symlink-resolved path with both the literal and the resolved guarded
   directories. It refuses `data/holdout/**` without an authorization and
   `data/raw/**` outside `rawread`, including through symlinked files or
   directories.
5. **Footer-only reads.** `read_footer` returns only column names and types,
   row counts, and the timestamp column's min/max statistics. It is allowed
   for every file, because placement and schema checks need it. It exposes no
   other column statistic and no row value.
6. **K0** (Stage D) will get its own validation-only path and flag (ADR-0020).
   It will not reuse the research `--holdout` flag.

This is a code contract enforced by tests, not an operating-system barrier.
Every future research module must read raw data through `r0.rawread`.

## 5. Running Stages A–C (owner's machine)

```bash
uv sync                                    # Python 3.12 + polars, pyarrow; dev: pytest, ruff
uv run pytest -q && uv run ruff check .

# Stage B: list only (downloads nothing; Parquet footers are read only if asked)
uv run python research/r0_dislocation_reversal/scripts/00_fetch.py --list
# Pin: probe footers (byte ranges, footers only) and write DATA_MANIFEST.{json,md}.
# Every daily_aligned Parquet file (any name, any case of ".parquet") is probed;
# placement comes only from complete footer timestamp statistics, never from
# file names. Refuses (no override) if any candidate's placement is unresolved,
# or if the manifest already pins another revision (--replace-manifest re-pins
# on purpose).
uv run python research/r0_dislocation_reversal/scripts/00_fetch.py --list --write-manifest

# Stage C: schema and role mapping from footers (no download needed). Every
# required daily_aligned file and every file of the CTF resolution table is
# inspected (no sampling); a missing/unreadable file, schema drift between
# files, or a duplicated field name is a blocker.
uv run python research/r0_dislocation_reversal/scripts/01_schema.py schema
#   exit code 3 = SPEC IMPLEMENTATION BLOCKER (see SCHEMA_REPORT.md); confirm a
#   candidate only if it has exactly the spec's meaning:
#   ... 01_schema.py schema --confirm token_id=<column> --confirm shares=<column>
#   ... --confirm shares=NONE      (no share-quantity column: §3 usdc_amount/price fallback;
#                                   the fallback is used ONLY with this explicit statement)
#   ... --ctf-resolution-table CTF/<name>   (if no CTF table is named "resolution...")

# Only after you approve the size printed by --list:
uv run python research/r0_dislocation_reversal/scripts/00_fetch.py \
    --download pre-holdout --approve-bytes <exact bytes from the listing>
uv run python research/r0_dislocation_reversal/scripts/00_fetch.py \
    --download ctf --approve-bytes <exact bytes>
uv run python research/r0_dislocation_reversal/scripts/00_fetch.py --verify --part pre-holdout

# Stage C: S_short vocabulary (EXPLORATION-period markets; category, tags, question, slug only)
uv run python research/r0_dislocation_reversal/scripts/01_schema.py vocab \
    --classifier research/r0_dislocation_reversal/proposals/s_short_classifier_DRAFT.toml

# Optional domain checks (ADR-0022): run only after the schema is cleared
# (complete coverage, no blocker). They always read integrity-verified LOCAL
# pre-holdout files, so schema coverage can come from --source remote. EXPLORATION-period
# rows only; aggregate data-quality counts only (nulls, p_event/price outside
# (0, 1), D outside {-1, +1}, non-positive quantities/amounts, neg_risk = true,
# code values, field-consistency mismatches). No rows, no events, no returns,
# no price paths, no SSTR-type statistics.
uv run python research/r0_dislocation_reversal/scripts/01_schema.py schema \
    --source remote --domain-checks --confirm ...
```

`vocab --source remote --sample-every 7` reads only the needed columns over
byte ranges, without downloading the pre-holdout part. It still transfers
some data, so use it only with your approval.

Environment variables:
- `HF_TOKEN` (optional): only if the dataset becomes gated or rate-limited.
  It is sent only over HTTPS to the configured endpoint host, never to the
  CDN host after a redirect or to another origin, and never printed.
- `R0_DATA_ROOT` (optional): moves the data root.

Upstream paths are validated (no absolute paths, `.` or `..` components)
before any local file is written. Downloads go to a unique temporary file
created exclusively inside the cache directory (`tempfile.mkstemp`; symlinked
directories or destinations are refused) and are renamed into place only after
verification.

**Integrity (one implementation, `r0/integrity.py`).** Every local raw file
is verified before it is consumed by `--verify`, `schema --source local`,
`vocab` or the domain checks: byte size, then the manifest SHA-256 if
recorded, otherwise the Git blob SHA-1 (`git_oid`). A file without usable
integrity metadata is refused. On any failure the script exits with code 4
and writes no output.

**S_short metadata projection.** Category/tag values are reduced to string
tokens immediately after reading; an object contributes only its `label`,
`name` or `slug` string (in that order). Other nested fields are never read
into any output; unsupported shapes are counted as rejected and dropped. A
string starting with `{` or `[` must be valid JSON; otherwise the whole value
is rejected and its text is never published. The selected `label`/`name`/`slug`
value must itself be plain text: if it starts with `{` or `[` the object is
rejected (never parsed, no fallback to a later key).

**Manifest placement authority.** Every consumer (download, `--verify`,
schema, vocab, domain checks) loads the manifest through one function,
`r0.manifest.load_authoritative_manifest`. It refuses the manifest unless it
has `manifest_version` 2 and every `daily_aligned` Parquet entry (including
`not-needed` ones) carries footer placement evidence whose implied side/need
equals the serialized values. Legacy manifests must be re-listed.

## 6. Files written

| Path | Content | In Git? |
| --- | --- | --- |
| `research/.../DATA_MANIFEST.json`, `.md` | pinned revision, paths, sizes, hashes, placement | yes (no data) |
| `research/.../SCHEMA_REPORT.json`, `.md` | column names/types, role mapping, blockers; optional domain-check aggregates | yes (no row data) |
| `data/raw/...` | raw files | no (ignored) |
| `data/exploration/inspection/*` | S_short vocabulary: category/tag counts, question/slug examples | no (ignored) |
