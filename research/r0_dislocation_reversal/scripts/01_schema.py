"""Stage C: schema inspection, role mapping and S_short metadata vocabulary.

    uv run python research/r0_dislocation_reversal/scripts/01_schema.py schema [--source remote]
    uv run python ... 01_schema.py schema --confirm token_id=<column> ...
    uv run python ... 01_schema.py schema --domain-checks [--sample-every 7]
    uv run python ... 01_schema.py vocab [--source local] [--classifier draft.toml]

``schema`` reads Parquet footers only (names, types, row counts, timestamp
statistics) and writes SCHEMA_REPORT.md/.json. Exit code 3 means a SPEC
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
from r0.manifest import LAYER_CTF, LAYER_DAILY, FileEntry, Listing
from r0.paths import RESEARCH_DIR, exploration_dir, raw_file
from r0.periods import EXPLORATION_END, EXPLORATION_START
from r0.rawread import Scope, read_footer, read_rows
from r0.roles import CTF_RESOLUTION_ROLES, DAILY_ROLES
from r0.schema import (
    RESOLVED,
    DomainSummary,
    ctf_blockers,
    ctf_table_key,
    daily_blockers,
    domain_update,
    map_roles,
    schema_variants,
)
from r0.vocab import META_ROLES, DraftClassifier, build_vocab, collect, evaluate_draft

MANIFEST_JSON = RESEARCH_DIR / "DATA_MANIFEST.json"
REPORT_JSON = RESEARCH_DIR / "SCHEMA_REPORT.json"
REPORT_MD = RESEARCH_DIR / "SCHEMA_REPORT.md"
TS_CANDIDATES = ("block_timestamp", "timestamp", "block_time")
CTF_FOOTERS_PER_TABLE = 50
# Files that may contain pre-holdout rows (exploration-period rows are a subset).
PRE_HOLDOUT_NEEDS = ("required-pre-holdout", "required-both")
BLOCKER_EXIT = 3


def _listing() -> Listing:
    if not MANIFEST_JSON.exists():
        sys.exit("no DATA_MANIFEST.json: run 00_fetch.py --list --write-manifest first")
    return Listing.from_json(MANIFEST_JSON.read_text())


class Sources:
    def __init__(self, listing: Listing, mode: str) -> None:
        self.listing, self.mode = listing, mode
        self.client = HubClient(listing.endpoint) if mode == "remote" else None
        self.remote: list[RemoteFile] = []

    def available(self, f: FileEntry) -> bool:
        return self.mode == "remote" or self._local(f).exists()

    def _local(self, f: FileEntry) -> Path:
        return raw_file(self.listing.repo_id, self.listing.revision_sha, f.path)

    def open(self, f: FileEntry):
        if self.mode == "local":
            return self._local(f)
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
    def one(f: FileEntry):
        return f, read_footer(src.open(f), TS_CANDIDATES)

    with ThreadPoolExecutor(max_workers=8 if src.mode == "remote" else 2) as ex:
        return list(ex.map(one, files))


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


def cmd_schema(a: argparse.Namespace) -> int:
    listing = _listing()
    src = Sources(listing, a.source)
    confirm = _parse_confirm(a.confirm)

    daily = [f for f in listing.files if f.layer == LAYER_DAILY and f.need.startswith("required")]
    daily_ok = [f for f in daily if src.available(f)]
    ctf_all = [f for f in listing.files if f.layer == LAYER_CTF and f.path.endswith(".parquet")]
    tables: dict[str, list[FileEntry]] = {}
    for f in ctf_all:
        tables.setdefault(ctf_table_key(f.path), []).append(f)
    capped = {
        t: _evenly([f for f in fs if src.available(f)], CTF_FOOTERS_PER_TABLE)
        for t, fs in tables.items()
    }

    d_foot = _footers(src, daily_ok)
    c_foot = {t: _footers(src, fs) for t, fs in capped.items()}

    d_vars = schema_variants([(f.path, i.schema, f.first_day, f.last_day) for f, i in d_foot])
    d_roles = map_roles(
        DAILY_ROLES, d_vars, {k: v for k, v in confirm.items() if not k.startswith("ctf_")}
    )
    c_vars = {
        t: schema_variants([(f.path, i.schema, f.first_day, f.last_day) for f, i in fi])
        for t, fi in c_foot.items()
    }
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
    c_roles = {
        t: map_roles(
            CTF_RESOLUTION_ROLES,
            c_vars[t],
            {k: v for k, v in confirm.items() if k.startswith("ctf_")},
        )
        for t in res_tables
    }
    blockers = daily_blockers(d_roles, d_vars) + ctf_blockers(c_roles, c_vars)

    expl_foot = [(f, i) for f, i in d_foot if f.need in PRE_HOLDOUT_NEEDS]
    ts_all = [(i.ts_min, i.ts_max) for _, i in d_foot if i.ts_min is not None]
    report = {
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": listing.repo_id,
        "revision_sha": listing.revision_sha,
        "source": a.source,
        "confirmations": confirm,
        "ctf_resolution_table_designated_by_owner": a.ctf_resolution_table,
        "daily_aligned": {
            "files_needed": len(daily),
            "footers_read": len(d_foot),
            "footers_missing_locally": len(daily) - len(daily_ok),
            "schema_variants": [asdict(v) for v in d_vars],
            "roles": [asdict(r) for r in d_roles],
            "coverage_utc": [_utc(min(t[0] for t in ts_all)), _utc(max(t[1] for t in ts_all))]
            if ts_all
            else None,
            "rows_total": sum(i.num_rows for _, i in d_foot),
            "rows_pre_holdout_side_files": sum(i.num_rows for _, i in expl_foot),
        },
        "ctf": {
            t: {
                "files": len(tables[t]),
                "footers_read": len(c_foot[t]),
                "capped": len(capped[t]) < len([f for f in tables[t] if src.available(f)]),
                "is_resolution_table": t in res_tables,
                "schema_variants": [asdict(v) for v in c_vars[t]],
                "roles": [asdict(r) for r in c_roles.get(t, [])],
            }
            for t in sorted(tables)
        },
        "blockers": [asdict(b) for b in blockers],
        "remote_bytes_fetched": src.bytes_fetched(),
    }
    if a.domain_checks:
        # ADR-0022: only after every required role is confirmed.
        report["domain_checks"] = (
            {"skipped": "schema roles not confirmed: resolve the blockers first"}
            if blockers
            else _domain(listing, src, d_roles, a.sample_every)
        )
    REPORT_JSON.write_text(json.dumps(report, indent=1, default=str) + "\n")
    REPORT_MD.write_text(render_schema_md(report))
    print(render_schema_md(report))
    return BLOCKER_EXIT if blockers else 0


def _domain(listing: Listing, src: Sources, roles, every: int) -> dict:
    """Aggregate data-quality checks on EXPLORATION-period rows (ADR-0022)."""
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
    files = sorted(
        (
            f
            for f in listing.files
            if f.layer == LAYER_DAILY and f.need in PRE_HOLDOUT_NEEDS and src.available(f)
        ),
        key=lambda f: f.path,
    )[::every]
    s = DomainSummary()
    for f in files:
        df, st = read_rows(
            src.open(f),
            [c for k, c in cols.items() if k != "timestamp"],
            ts_column=cols["timestamp"],
            scope=Scope.PRE_HOLDOUT,
        )
        s.files_read += 1
        s.rows_excluded_holdout_side += (
            st.rows_read - st.rows_kept - st.rows_null_ts + st.rows_in_skipped_groups
        )
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
        "Generated by `scripts/01_schema.py schema`. Footer metadata only (names, types, row",
        "counts, timestamp statistics) unless the domain-check section is present, which",
        "uses exploration-period rows only.",
        "",
        f"- Dataset `{r['dataset']}` at `{r['revision_sha']}`; source: {r['source']}",
        f"- Generated: {r['generated_at_utc']}",
        f"- Owner confirmations: {r['confirmations'] or 'none'}",
        "",
        "## daily_aligned",
        "",
        f"Footers read: {d['footers_read']} of {d['files_needed']} needed files"
        f" (missing locally: {d['footers_missing_locally']}). Total rows: {d['rows_total']:,}"
        f" (pre-holdout-side files: {d['rows_pre_holdout_side_files']:,}).",
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
            f"{', capped' if c['capped'] else ''}; resolution table: {c['is_resolution_table']})",
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
    if r.get("remote_bytes_fetched"):
        L.append(f"Remote bytes fetched: {r['remote_bytes_fetched']:,}")
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
    df, stats = collect((src.open(f) for f in files), cols)
    vocab = build_vocab(df, cols, a.examples)
    vocab.reader_stats = {
        **stats,
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
    if a.classifier:
        ev = evaluate_draft(df, cols, DraftClassifier.load(Path(a.classifier)))
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
    return cmd_schema(a) if a.cmd == "schema" else cmd_vocab(a)


if __name__ == "__main__":
    raise SystemExit(main())
