"""Stage C: schema inspection, role mapping and S_short metadata vocabulary.

    uv run python research/r0_dislocation_reversal/scripts/01_schema.py schema [--source remote]
    uv run python ... 01_schema.py schema --confirm token_id=<column> ...
    uv run python ... 01_schema.py schema --domain-checks [--sample-every 7]
    uv run python ... 01_schema.py vocab [--source local] [--classifier draft.toml]

``schema`` reads Parquet footers only and writes SCHEMA_REPORT.md/.json with
schema structure (names, types, variants, roles) and file-placement timestamps.
Holdout blindness (ADR-0025): no row counts, row-group counts, byte volumes or
other column statistics are reported for any file. Exit code 3 means a SPEC
IMPLEMENTATION BLOCKER: stop and return to the owner.

``--domain-checks`` (ADR-0022: runs only once every required role is confirmed)
and ``vocab`` read row values through ``r0.rawread`` (PRE_HOLDOUT scope) and
then keep EXPLORATION-period rows only (2025-01-01 .. 2025-09-30; no trailing
2024 rows, no embargo rows). Domain checks write aggregate data-quality counts
(nulls, domain violations, code values, field-consistency mismatches; no rows)
into SCHEMA_REPORT.json/.md. Vocabulary outputs go to
data/exploration/inspection/ (Git-ignored).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import _bootstrap  # noqa: F401

from r0.hub import HubClient, RemoteFile
from r0.integrity import IntegrityError, verify_file
from r0.manifest import (
    LAYER_CTF,
    LAYER_DAILY,
    FileEntry,
    Listing,
    ManifestError,
    is_parquet,
    load_authoritative_manifest,
)
from r0.paths import RESEARCH_DIR, exploration_dir, raw_file
from r0.periods import EXPLORATION_END, EXPLORATION_START
from r0.rawread import Scope, read_footer, read_rows
from r0.roles import CTF_RESOLUTION_ROLES, DAILY_ROLES
from r0.schema import (
    RESOLVED,
    DomainSummary,
    coverage_blocker,
    ctf_blockers,
    ctf_table_key,
    daily_blockers,
    domain_update,
    drift_blocker,
    duplicate_field_blocker,
    map_roles,
    schema_variants,
)
from r0.vocab import META_ROLES, DraftClassifier, build_vocab, collect, evaluate_draft

MANIFEST_JSON = RESEARCH_DIR / "DATA_MANIFEST.json"
REPORT_JSON = RESEARCH_DIR / "SCHEMA_REPORT.json"
REPORT_MD = RESEARCH_DIR / "SCHEMA_REPORT.md"
TS_CANDIDATES = ("block_timestamp", "timestamp", "block_time")
# Informational CTF tables (not the resolution table) are sampled, and the
# report says so; the resolution table is always inspected completely.
CTF_INFO_FOOTERS_PER_TABLE = 50
REQUIRED_DAILY = ("required-pre-holdout", "required-both", "required-holdout")
# Files that may contain pre-holdout rows (exploration-period rows are a subset).
PRE_HOLDOUT_NEEDS = ("required-pre-holdout", "required-both")
BLOCKER_EXIT = 3
INTEGRITY_EXIT = 4


def _listing() -> Listing:
    """The only manifest loader of Stage C (schema, vocab, domain checks)."""
    if not MANIFEST_JSON.exists():
        sys.exit("no DATA_MANIFEST.json: run 00_fetch.py --list --write-manifest first")
    try:
        return load_authoritative_manifest(MANIFEST_JSON)
    except ManifestError as e:
        sys.exit(f"refusing: {e}")


class Sources:
    """Opens pinned files. Local files are consumed only after r0.integrity
    verification (size, then SHA-256 or Git blob SHA-1); failures raise."""

    def __init__(self, listing: Listing, mode: str) -> None:
        self.listing, self.mode = listing, mode
        self.client = HubClient(listing.endpoint) if mode == "remote" else None
        self.remote: list[RemoteFile] = []
        self._verified: set[str] = set()

    def local_path(self, f: FileEntry) -> Path:
        return raw_file(self.listing.repo_id, self.listing.revision_sha, f.path)

    def present_locally(self, f: FileEntry) -> bool:
        p = self.local_path(f)
        return p.exists() or p.is_symlink()

    def available(self, f: FileEntry) -> bool:
        return self.mode == "remote" or self.present_locally(f)

    def verify_local(self, f: FileEntry) -> Path:
        p = self.local_path(f)
        if f.path not in self._verified:
            verify_file(p, f.size, f.sha256, f.git_oid)  # raises IntegrityError
            self._verified.add(f.path)
        return p

    def open(self, f: FileEntry):
        if self.mode == "local":
            return self.verify_local(f)
        assert self.client is not None
        rf = RemoteFile(
            self.client,
            self.client.file_url(self.listing.repo_id, self.listing.revision_sha, f.path),
            f.size,
        )
        self.remote.append(rf)
        return rf

    def bytes_fetched(self) -> int:
        return sum(r.bytes_fetched for r in self.remote)


def _footers(src: Sources, files: list[FileEntry]):
    """(read, unreadable): footers of ``files``; integrity failures propagate."""
    if src.mode == "local":
        for f in files:  # verify everything before reading anything
            src.verify_local(f)

    def one(f: FileEntry):
        try:
            return f, read_footer(src.open(f), TS_CANDIDATES)
        except IntegrityError:
            raise
        except Exception as e:  # unreadable footer: reported as a coverage gap
            return f, e

    with ThreadPoolExecutor(max_workers=8 if src.mode == "remote" else 2) as ex:
        res = list(ex.map(one, files))
    read = [(f, i) for f, i in res if not isinstance(i, Exception)]
    bad = [f"{f.path}: {type(i).__name__}" for f, i in res if isinstance(i, Exception)]
    return read, bad


def _evenly(files: list[FileEntry], k: int) -> list[FileEntry]:
    if len(files) <= k:
        return files
    step = (len(files) - 1) / (k - 1)
    return [files[round(i * step)] for i in range(k)]


def _parse_confirm(items: list[str]) -> dict[str, str]:
    out = {}
    for it in items:
        role, _, col = it.partition("=")
        if not role or not col:
            sys.exit(f"bad --confirm {it!r}; expected role=column")
        out[role] = col
    return out


def _utc(ts: int | None) -> str | None:
    return None if ts is None else datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _inspect_table(table, roles, src, files, confirm, sample: int | None = None):
    """Footer-inspect one table. Returns (report dict, blockers, role results)."""
    present = [f for f in files if src.available(f)]
    missing = [f.path for f in files if not src.available(f)]
    chosen = _evenly(present, sample) if sample else present
    foot, unreadable = _footers(src, chosen)
    variants = schema_variants([(f.path, i.schema, f.first_day, f.last_day) for f, i in foot])
    blockers = []
    dup = duplicate_field_blocker(table, [(f.path, i.schema) for f, i in foot])
    results = []
    if dup is not None:
        blockers.append(dup)  # no role mapping on ambiguous schemas
    elif roles is not None:
        results = map_roles(roles, variants, confirm)
    if roles is not None:  # a required table: coverage and drift must be complete
        for b in (coverage_blocker(table, missing, unreadable), drift_blocker(table, variants)):
            if b is not None:
                blockers.append(b)
    info = {
        "files": len(files),
        "footers_read": len(foot),
        "missing": len(missing),
        "unreadable": unreadable,
        "sampled": len(chosen) < len(present),
        "schema_variants": [asdict(v) for v in variants],
        "roles": [asdict(r) for r in results],
    }
    return info, blockers, results, foot, variants


def cmd_schema(a: argparse.Namespace) -> int:
    listing = _listing()
    src = Sources(listing, a.source)
    confirm = _parse_confirm(a.confirm)

    daily = [f for f in listing.files if f.layer == LAYER_DAILY and f.need in REQUIRED_DAILY]
    d_info, d_block, d_roles, d_foot, d_vars = _inspect_table(
        "daily_aligned",
        DAILY_ROLES,
        src,
        daily,
        {k: v for k, v in confirm.items() if not k.startswith("ctf_")},
    )
    blockers = list(d_block)
    if not any(b.role.startswith("daily_aligned: duplicate") for b in d_block):
        blockers += daily_blockers(d_roles, d_vars)

    ctf_all = [f for f in listing.files if f.layer == LAYER_CTF and is_parquet(f.path)]
    tables: dict[str, list[FileEntry]] = {}
    for f in ctf_all:
        tables.setdefault(ctf_table_key(f.path), []).append(f)
    if a.ctf_resolution_table:
        if a.ctf_resolution_table not in tables:
            sys.exit(
                f"--ctf-resolution-table {a.ctf_resolution_table!r} is not one of: "
                + ", ".join(sorted(tables))
            )
        res_tables = {a.ctf_resolution_table}  # owner designation, recorded in the report
    else:
        res_tables = {
            t for t, fs in tables.items() if any(f.need == "required-ctf-resolution" for f in fs)
        }
    ctf_confirm = {k: v for k, v in confirm.items() if k.startswith("ctf_")}
    ctf_report, c_roles, c_vars = {}, {}, {}
    for t in sorted(tables):
        is_res = t in res_tables
        if is_res:  # every file of the resolution table, no cap
            info, blk, res, _, variants = _inspect_table(
                t, CTF_RESOLUTION_ROLES, src, tables[t], ctf_confirm
            )
            blockers += blk
            if not any("duplicate" in b.role for b in blk):
                c_roles[t] = res
        else:  # informational only: verified-present files, sampled and labelled
            files = [f for f in tables[t] if src.available(f)]
            info, _, _, _, variants = _inspect_table(
                t, None, src, files, {}, CTF_INFO_FOOTERS_PER_TABLE
            )
        c_vars[t] = variants
        info["is_resolution_table"] = is_res
        ctf_report[t] = info
    blockers += ctf_blockers(c_roles, c_vars) if (c_roles or not res_tables) else []

    ts_all = [(i.ts_min, i.ts_max) for _, i in d_foot if i.ts_min is not None]
    report = {
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": listing.repo_id,
        "revision_sha": listing.revision_sha,
        "source": a.source,
        "confirmations": confirm,
        "ctf_resolution_table_designated_by_owner": a.ctf_resolution_table,
        "daily_aligned": {
            **d_info,
            "coverage_utc": [_utc(min(t[0] for t in ts_all)), _utc(max(t[1] for t in ts_all))]
            if ts_all
            else None,
        },
        "ctf": ctf_report,
        "blockers": [asdict(b) for b in blockers],
    }
    if a.domain_checks:
        # ADR-0022: only once schema coverage is complete and every role is cleared.
        report["domain_checks"] = (
            {"skipped": "schema not cleared: resolve the blockers first"}
            if blockers
            else _domain(listing, d_roles, a.sample_every)
        )
    REPORT_JSON.write_text(json.dumps(report, indent=1, default=str) + "\n")
    REPORT_MD.write_text(render_schema_md(report))
    print(render_schema_md(report))
    return BLOCKER_EXIT if blockers else 0


def _domain(listing: Listing, roles, every: int) -> dict:
    """Aggregate data-quality checks on EXPLORATION-period rows (ADR-0022).

    Always reads integrity-verified local files; every pre-holdout file must be
    present before anything is read."""
    local = Sources(listing, "local")
    cols = {r.key: r.column for r in roles if r.status in RESOLVED and r.column}
    needed = (
        "timestamp",
        "p_event",
        "direction_D",
        "outcome_seq",
        "shares",
        "usdc_amount",
        "price",
        "taker_direction",
        "neg_risk",
    )
    cols = {k: v for k, v in cols.items() if k in needed}
    all_files = sorted(
        (f for f in listing.files if f.layer == LAYER_DAILY and f.need in PRE_HOLDOUT_NEEDS),
        key=lambda f: f.path,
    )
    missing = [f.path for f in all_files if not local.present_locally(f)]
    if missing:
        return {"skipped": f"{len(missing)} pre-holdout files not in the local cache"}
    files = all_files[::every]
    for f in files:  # verify everything before reading anything
        local.verify_local(f)
    s = DomainSummary()
    for f in files:
        df, st = read_rows(
            local.open(f),
            [c for k, c in cols.items() if k != "timestamp"],
            ts_column=cols["timestamp"],
            scope=Scope.PRE_HOLDOUT,
        )
        s.files_read += 1
        s.rows_null_timestamp += st.rows_null_ts
        # Exploration period only: no trailing 2024 rows, no embargo rows.
        in_period = df[cols["timestamp"]].is_between(EXPLORATION_START, EXPLORATION_END)
        s.rows_excluded_outside_exploration_period += int((~in_period).sum())
        domain_update(s, df.filter(in_period), cols)
    out = asdict(s)
    out["sample_every"] = every
    out["columns"] = cols
    return out


def render_schema_md(r: dict) -> str:
    d = r["daily_aligned"]
    L = [
        "# R0 Stage C schema report",
        "",
        "Generated by `scripts/01_schema.py schema`. Footer schema structure and file-placement",
        "timestamps only; no row counts or other data-volume statistics (ADR-0025). The",
        "domain-check section, if present, uses exploration-period rows only.",
        "",
        f"- Dataset `{r['dataset']}` at `{r['revision_sha']}`; source: {r['source']}",
        f"- Generated: {r['generated_at_utc']}",
        f"- Owner confirmations: {r['confirmations'] or 'none'}",
        "",
        "## daily_aligned",
        "",
        f"Footers read: {d['footers_read']} of {d['files']} required files"
        f" (not available: {d['missing']}; unreadable: {len(d['unreadable'])}).",
        f"Timestamp coverage (footer statistics): {d['coverage_utc']}",
        "",
    ]
    for k, v in enumerate(d["schema_variants"], 1):
        L += [
            f"### Schema variant {k}: {v['files']} files, {v['first_day']} .. {v['last_day']}",
            "",
            "| Column | Arrow type | Family |",
            "| --- | --- | --- |",
        ]
        L += [f"| `{c}` | `{t}` | {fam} |" for c, t, fam in v["columns"]]
        L.append("")
    L += [
        "### Role mapping",
        "",
        "| Role | Level | Status | Column | Types | Candidates | Frozen rule | Note |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    L += [
        f"| {x['key']} | {x['level']} | **{x['status']}** | {x['column'] or '-'} | "
        f"{','.join(x['types']) or '-'} | {', '.join(x['candidates']) or '-'} | {x['spec']} | "
        f"{x['note']} |"
        for x in d["roles"]
    ]
    L += ["", "## CTF", ""]
    for t, c in r["ctf"].items():
        L += [
            f"### {t} ({c['files']} files, footers read {c['footers_read']}"
            f"{', SAMPLED (informational table)' if c['sampled'] else ''}"
            f"; resolution table: {c['is_resolution_table']})",
            "",
        ]
        for k, v in enumerate(c["schema_variants"], 1):
            L += [
                f"Variant {k} ({v['files']} files, {v['first_day']} .. {v['last_day']}): "
                + ", ".join(f"`{n}`: {ty}" for n, ty, _ in v["columns"]),
                "",
            ]
        if c["roles"]:
            L += [
                "| Role | Level | Status | Column | Candidates | Frozen rule |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
            L += [
                f"| {x['key']} | {x['level']} | **{x['status']}** | {x['column'] or '-'} | "
                f"{', '.join(x['candidates']) or '-'} | {x['spec']} |"
                for x in c["roles"]
            ]
            L.append("")
    if "domain_checks" in r:
        L += [
            "## Domain checks (exploration-period rows, aggregates only)",
            "",
            "```json",
            json.dumps(r["domain_checks"], indent=1, default=str),
            "```",
            "",
        ]
    L += ["## SPEC IMPLEMENTATION BLOCKERS", ""]
    if not r["blockers"]:
        L.append("None found by the schema check.")
    for b in r["blockers"]:
        L += [
            f"### {b['role']}",
            f"- Frozen rule: {b['frozen_rule']}",
            f"- Problem: {b['problem']}",
            f"- Smallest resolution: {b['smallest_resolution']}",
            f"- Amendment: {b['amendment']}",
            f"- Available fields: {', '.join(b['available_fields']) or '-'}",
            "",
        ]
    return "\n".join(L) + "\n"


def cmd_vocab(a: argparse.Namespace) -> int:
    listing = _listing()
    if not REPORT_JSON.exists():
        sys.exit("run `01_schema.py schema` first")
    rep = json.loads(REPORT_JSON.read_text())
    if rep["revision_sha"] != listing.revision_sha:
        sys.exit("SCHEMA_REPORT.json is for another revision; re-run schema")
    cols = {
        x["key"]: x["column"]
        for x in rep["daily_aligned"]["roles"]
        if x["status"] in RESOLVED and x["key"] in ("market_id", "timestamp", *META_ROLES)
    }
    if not {"market_id", "timestamp"} <= cols.keys():
        sys.exit("market_id/timestamp roles unresolved; resolve them in the schema step first")
    if not any(r in cols for r in ("category", "tags", "question", "slug")):
        print(
            "No category/tags/question/slug column resolved in daily_aligned. Per §2.2 the "
            "metadata must come from one pinned Gamma snapshot; that path is not implemented "
            "in Stages A-C and needs owner approval."
        )
        return BLOCKER_EXIT
    src = Sources(listing, a.source)
    files = sorted(
        (f for f in listing.files if f.layer == LAYER_DAILY and f.need in PRE_HOLDOUT_NEEDS),
        key=lambda f: f.path,
    )
    missing = [f for f in files if not src.available(f)]
    if missing:
        sys.exit(
            f"{len(missing)} pre-holdout-side files are not in the local cache; "
            "download the pre-holdout part or use --source remote"
        )
    files = files[:: a.sample_every]
    clf = DraftClassifier.load(Path(a.classifier)) if a.classifier else None
    if src.mode == "local":
        for f in files:  # verify everything before reading anything
            src.verify_local(f)
    col = collect((src.open(f) for f in files), cols)
    vocab = build_vocab(col, cols, a.examples)
    vocab.reader_stats = {
        **col.stats,
        "sample_every": a.sample_every,
        "remote_bytes_fetched": src.bytes_fetched(),
    }
    out_dir = exploration_dir() / "inspection"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "s_short_vocab.json").write_text(json.dumps(asdict(vocab), indent=1, default=str))
    (out_dir / "s_short_vocab.md").write_text(render_vocab_md(vocab, cols))
    print(
        f"exploration-period markets: {vocab.n_markets:,}; distinct categories: "
        f"{len(vocab.category_counts)}; distinct tags: {len(vocab.tag_counts)}; "
        f"design-screen hits: {vocab.design_screen_hits:,}"
    )
    print(f"wrote {out_dir / 's_short_vocab.md'} (Git-ignored)")
    if clf is not None:
        ev = evaluate_draft(col, clf)
        (out_dir / "s_short_draft_eval.json").write_text(json.dumps(ev, indent=1, default=str))
        print({k: v for k, v in ev.items() if not k.startswith("audit_sample")})
        print(f"wrote {out_dir / 's_short_draft_eval.json'} (Git-ignored)")
    return 0


def render_vocab_md(v, cols: dict[str, str]) -> str:
    L = [
        "# S_short metadata vocabulary (exploration-period markets only)",
        "",
        "Design/audit input for the S_short classifier. Not used by event logic. Git-ignored.",
        "",
        f"- Columns: {cols}",
        f"- Column types: {v.column_types}",
        f"- Markets: {v.n_markets:,}; with varying metadata: {v.markets_with_varying_metadata:,}",
        f"- Markets with null metadata, by field: {v.null_markets}",
        f"- Rejected (unauthorized or unsupported) metadata parts, counted only: "
        f"{v.rejected_metadata_parts:,}",
        f"- Reader stats: {v.reader_stats}",
        "",
        "## Category values (markets)",
        "",
    ]
    L += [f"- `{t}`: {n:,}" for t, n in v.category_counts]
    L += ["", "## Tag values (markets; top 300)", ""]
    L += [f"- `{t}`: {n:,}" for t, n in v.tag_counts[:300]]
    L += ["", f"## Design-screen hits ({v.design_screen_hits:,}; first 150)", ""]
    L += [f"- {e}" for e in v.design_screen_examples]
    L += ["", "## Random examples (deterministic SHA-256 order)", ""]
    L += [f"- {e}" for e in v.examples_random]
    L += ["", "## Examples by category (up to 5 each)", ""]
    for c, es in v.examples_by_category.items():
        L += [f"### {c}", *[f"- {e}" for e in es], ""]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("schema")
    s.add_argument("--source", choices=("remote", "local"), default="remote")
    s.add_argument("--confirm", action="append", default=[], metavar="ROLE=COLUMN")
    s.add_argument("--domain-checks", action="store_true")
    s.add_argument(
        "--ctf-resolution-table",
        metavar="CTF/<name>",
        help="owner designation of the CTF table holding only resolution events",
    )
    s.add_argument("--sample-every", type=int, default=1)
    v = sub.add_parser("vocab")
    v.add_argument("--source", choices=("remote", "local"), default="local")
    v.add_argument("--classifier", help="draft classifier TOML (design/audit only)")
    v.add_argument("--sample-every", type=int, default=1)
    v.add_argument("--examples", type=int, default=200)
    a = p.parse_args(argv)
    if getattr(a, "sample_every", 1) < 1:
        sys.exit("--sample-every must be >= 1")
    try:
        return cmd_schema(a) if a.cmd == "schema" else cmd_vocab(a)
    except IntegrityError as e:
        # Fail closed: nothing has been written by this run.
        print(f"INTEGRITY FAILURE: {e}. No output written.", file=sys.stderr)
        return INTEGRITY_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
