"""Stage C: schema inspection and role mapping (metadata only by default).

Reports carry schema structure (column names/types) and file-placement
timestamps only: no row counts or other data-volume statistics (ADR-0025). The
optional domain checks (ADR-0022) read row values only through
``r0.rawread.read_rows`` (PRE_HOLDOUT scope) and then keep exploration-period
rows only.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

import polars as pl
import pyarrow as pa

from r0.roles import (
    AMENDMENT_HINTS,
    METADATA,
    OPTIONAL,
    REQUIRED,
    REQUIRED_K0,
    SHARES,
    Role,
)

RESOLVED = ("FOUND", "CONFIRMED")
# ``--confirm role=NONE``: the owner states that no column carries the role.
ABSENT = "NONE"
_AMEND_IF_NOT_CONFIRMED = (
    "No, if the owner confirms a candidate with identical meaning; otherwise yes."
)


def type_family(t: pa.DataType) -> str:
    if pa.types.is_boolean(t):
        return "bool"
    if pa.types.is_integer(t):
        return "int"
    if pa.types.is_floating(t):
        return "float"
    if pa.types.is_decimal(t):
        return "decimal"
    if pa.types.is_string(t) or pa.types.is_large_string(t) or pa.types.is_string_view(t):
        return "string"
    if pa.types.is_binary(t) or pa.types.is_large_binary(t) or pa.types.is_fixed_size_binary(t):
        return "binary"
    if pa.types.is_timestamp(t):
        return "timestamp"
    if pa.types.is_date(t):
        return "date"
    if pa.types.is_list(t) or pa.types.is_large_list(t) or pa.types.is_list_view(t):
        return "list"
    if pa.types.is_struct(t):
        return "struct"
    if pa.types.is_dictionary(t):
        return type_family(t.value_type)
    return str(t)


@dataclass
class SchemaVariant:
    columns: list[tuple[str, str, str]]  # (name, arrow type string, type family)
    files: int
    first_day: str | None
    last_day: str | None
    example_path: str


def schema_variants(
    items: list[tuple[str, pa.Schema, str | None, str | None]],
) -> list[SchemaVariant]:
    """Group (path, schema, first_day, last_day) by identical schema."""
    groups: dict[tuple, SchemaVariant] = {}
    for path, schema, first, last in items:
        key = tuple((f.name, str(f.type), type_family(f.type)) for f in schema)
        v = groups.get(key)
        if v is None:
            groups[key] = SchemaVariant([*key], 1, first, last, path)
        else:
            v.files += 1
            if first and (v.first_day is None or first < v.first_day):
                v.first_day = first
            if last and (v.last_day is None or last > v.last_day):
                v.last_day = last
    return sorted(groups.values(), key=lambda v: (v.first_day or "", -v.files))


@dataclass
class RoleResult:
    key: str
    level: str
    status: str  # FOUND | CONFIRMED | CANDIDATES | AMBIGUOUS | MISSING
    column: str | None
    candidates: list[str]
    types: list[str]
    spec: str
    note: str = ""


def _families(col: str, variants: list[SchemaVariant]) -> list[str] | None:
    """Type families of ``col`` across variants, or None if absent from any variant."""
    fams = []
    for v in variants:
        d = {name: fam for name, _, fam in v.columns}
        if col not in d:
            return None
        fams.append(d[col])
    return sorted(set(fams))


def map_roles(
    roles: tuple[Role, ...], variants: list[SchemaVariant], confirmations: dict[str, str]
) -> list[RoleResult]:
    all_cols = sorted({c for v in variants for c, _, _ in v.columns})
    out: list[RoleResult] = []
    for r in roles:
        hint = re.compile(r.hints, re.I)
        candidates = [c for c in all_cols if hint.search(c) and c not in r.exact]
        if r.key in confirmations and confirmations[r.key] == ABSENT:
            out.append(
                RoleResult(
                    r.key,
                    r.level,
                    "CONFIRMED_ABSENT",
                    None,
                    candidates,
                    [],
                    r.spec,
                    "owner confirmed: no column carries this role",
                )
            )
            continue
        if r.key in confirmations:
            col = confirmations[r.key]
            fams = _families(col, variants)
            if fams is None:
                out.append(
                    RoleResult(
                        r.key,
                        r.level,
                        "AMBIGUOUS",
                        col,
                        candidates,
                        [],
                        r.spec,
                        "confirmed column is absent from some schema variants",
                    )
                )
            elif not set(fams) <= set(r.types):
                out.append(
                    RoleResult(
                        r.key,
                        r.level,
                        "AMBIGUOUS",
                        col,
                        candidates,
                        fams,
                        r.spec,
                        f"confirmed column type {fams} not in {list(r.types)}",
                    )
                )
            else:
                out.append(
                    RoleResult(
                        r.key,
                        r.level,
                        "CONFIRMED",
                        col,
                        candidates,
                        fams,
                        r.spec,
                        "owner-confirmed mapping",
                    )
                )
            continue
        present = [c for c in r.exact if c in all_cols]
        if len(present) == 1:
            col = present[0]
            fams = _families(col, variants)
            if fams is None:
                out.append(
                    RoleResult(
                        r.key,
                        r.level,
                        "AMBIGUOUS",
                        col,
                        candidates,
                        [],
                        r.spec,
                        "column missing from some schema variants (drift)",
                    )
                )
            elif not set(fams) <= set(r.types):
                out.append(
                    RoleResult(
                        r.key,
                        r.level,
                        "AMBIGUOUS",
                        col,
                        candidates,
                        fams,
                        r.spec,
                        f"type {fams} not in expected {list(r.types)}",
                    )
                )
            else:
                out.append(RoleResult(r.key, r.level, "FOUND", col, candidates, fams, r.spec))
        elif len(present) > 1:
            out.append(
                RoleResult(
                    r.key,
                    r.level,
                    "AMBIGUOUS",
                    None,
                    present + candidates,
                    [],
                    r.spec,
                    "several exact-name columns",
                )
            )
        elif candidates:
            out.append(
                RoleResult(
                    r.key,
                    r.level,
                    "CANDIDATES",
                    None,
                    candidates,
                    [],
                    r.spec,
                    "no column with the spec's name; owner must confirm or reject",
                )
            )
        else:
            out.append(RoleResult(r.key, r.level, "MISSING", None, [], [], r.spec))
    return out


@dataclass
class Blocker:
    role: str
    frozen_rule: str
    problem: str
    available_fields: list[str]
    smallest_resolution: str
    amendment: str


def resolved(results: list[RoleResult], key: str) -> bool:
    return any(r.key == key and r.status in RESOLVED for r in results)


def daily_blockers(results: list[RoleResult], variants: list[SchemaVariant]) -> list[Blocker]:
    avail = sorted({f"{c}: {t}" for v in variants for c, t, _ in v.columns})
    out: list[Blocker] = []
    if not variants:
        return [
            Blocker(
                "daily_aligned",
                "§2.1 column mapping check",
                "no daily_aligned files read",
                [],
                "Run Stage B listing and Stage C against the pinned files.",
                "n/a",
            )
        ]
    for r in results:
        if r.level in (REQUIRED, REQUIRED_K0) and r.status not in RESOLVED:
            out.append(
                Blocker(
                    r.key,
                    r.spec,
                    f"role is {r.status}"
                    + (f"; candidates: {', '.join(r.candidates)}" if r.candidates else "")
                    + (f" ({r.note})" if r.note else ""),
                    avail,
                    (
                        "Owner confirms a candidate with --confirm "
                        f"{r.key}=<column> if it carries exactly this meaning; otherwise: "
                        if r.candidates
                        else ""
                    )
                    + AMENDMENT_HINTS.get(r.key, "Owner decision."),
                    "No, if the owner confirms a candidate with identical meaning; otherwise yes.",
                )
            )
    # §3 uses usdc_amount / price only if daily_aligned has NO share column. A
    # heuristic finding no candidate is not evidence of absence, so the share
    # role has three states: mapped (CONFIRMED), confirmed absent
    # (CONFIRMED_ABSENT, i.e. --confirm shares=NONE) and unresolved (anything
    # else). Only the first two can clear; the fallback needs the second.
    shares = next((r for r in results if r.key == "shares"), None)
    state = shares.status if shares is not None else "MISSING"
    if state not in RESOLVED and state != "CONFIRMED_ABSENT":
        out.append(
            Blocker(
                "shares",
                "§3 q_r: a share-quantity column if daily_aligned has one; otherwise "
                "usdc_amount / price",
                f"share role unresolved ({state}"
                + (
                    f"; candidates: {', '.join(shares.candidates)}"
                    if shares and shares.candidates
                    else "; no heuristic candidate, which does not show that none exists"
                )
                + ")",
                avail,
                "Owner states which column is the share quantity (--confirm shares=<column>) or "
                "that none exists (--confirm shares=NONE); units and gross/net are checked at K0.",
                "No",
            )
        )
    elif state == "CONFIRMED_ABSENT" and not (
        resolved(results, "usdc_amount") and resolved(results, "price")
    ):
        out.append(
            Blocker(
                "shares",
                "§3 q_r: share-quantity column, else usdc_amount / price",
                "no share column (owner-confirmed) and usdc_amount / price not both resolved",
                avail,
                AMENDMENT_HINTS["shares"],
                "Yes",
            )
        )
    return out


def duplicate_field_blocker(table: str, schemas: list[tuple[str, pa.Schema]]) -> Blocker | None:
    """Duplicate field names in any file of a table block before role mapping.

    Works on the schemas' field lists (never on a name-keyed dict, which would
    collapse duplicates). Identical types do not make duplicates acceptable.
    """
    found: dict[str, list[str]] = {}
    for path, schema in schemas:
        for name, n in Counter(schema.names).items():
            if n > 1:
                types = [str(f.type) for f in schema if f.name == name]
                found.setdefault(name, []).append(f"{path} ({', '.join(types)})")
    if not found:
        return None
    return Blocker(
        f"{table}: duplicate field names",
        "§2.1 column mapping check: each role maps to exactly one column",
        "duplicate field names make every role on them ambiguous: "
        + "; ".join(f"`{n}` in {len(ps)} file(s), e.g. {ps[0]}" for n, ps in sorted(found.items())),
        sorted(found),
        "STOP: role mapping is not attempted for this table. The data must be corrected, or "
        "the owner decides how the duplicated columns are disambiguated.",
        "Yes, unless the data is corrected.",
    )


def drift_blocker(table: str, variants: list[SchemaVariant]) -> Blocker | None:
    """Any schema difference between the required files of a table blocks."""
    if len(variants) <= 1:
        return None
    desc = []
    base = {(c, t) for c, t, _ in variants[0].columns}
    for v in variants:
        cols = {(c, t) for c, t, _ in v.columns}
        desc.append(
            f"{v.files} file(s) {v.first_day}..{v.last_day} (e.g. {v.example_path}): "
            f"+{sorted(cols - base)} -{sorted(base - cols)}"
        )
    return Blocker(
        f"{table}: schema drift",
        "§2.1 column mapping check over every pinned file",
        f"{len(variants)} different schemas among the required files: " + " | ".join(desc),
        [],
        "STOP: the owner decides whether the differing files are usable and how.",
        "Possibly",
    )


def coverage_blocker(table: str, missing: list[str], unreadable: list[str]) -> Blocker | None:
    """Every required file must be present and its footer inspected."""
    if not missing and not unreadable:
        return None
    parts = []
    if missing:
        parts.append(f"{len(missing)} required file(s) not available, e.g. {missing[:3]}")
    if unreadable:
        parts.append(f"{len(unreadable)} footer(s) unreadable, e.g. {unreadable[:3]}")
    return Blocker(
        f"{table}: incomplete schema coverage",
        "§2.1 column mapping check over every pinned file",
        "; ".join(parts),
        [],
        "Download/verify the missing files (or use --source remote) and re-run.",
        "No",
    )


def ctf_blockers(
    resolution_tables: dict[str, list[RoleResult]], all_tables: dict[str, list[SchemaVariant]]
) -> list[Blocker]:
    avail = sorted(
        {f"{t}.{c}: {ty}" for t, vs in all_tables.items() for v in vs for c, ty, _ in v.columns}
    )
    if not resolution_tables:
        return [
            Blocker(
                "ctf_resolution_table",
                "§5.3 t_res(m) from the condition's resolution event in CTF/",
                "no CTF table is identifiable as resolutions from file names",
                avail,
                "If one table holds only resolution events, the owner designates it with "
                "--ctf-resolution-table CTF/<name>. If resolutions are mixed with other events in "
                "one table, selecting them by an event-type value is not supported in Stage C: "
                "it needs an owner decision and a code change. No CTF value is read in Stage C.",
                "No, if a resolution table exists under another name.",
            )
        ]
    if len(resolution_tables) > 1:
        return [
            Blocker(
                "ctf_resolution_table",
                "§5.3",
                "several tables look like resolutions: " + ", ".join(resolution_tables),
                avail,
                "Owner selects one with --ctf-resolution-table CTF/<name>.",
                "No",
            )
        ]
    out: list[Blocker] = []
    for _table, results in resolution_tables.items():
        for r in results:
            if r.level == REQUIRED and r.status not in RESOLVED:
                out.append(
                    Blocker(
                        r.key,
                        r.spec,
                        f"role is {r.status}"
                        + (f"; candidates: {', '.join(r.candidates)}" if r.candidates else ""),
                        avail,
                        AMENDMENT_HINTS.get(r.key, "Owner decision."),
                        _AMEND_IF_NOT_CONFIRMED,
                    )
                )
    return out


def ctf_table_key(path: str) -> str:
    """Group CTF files into tables: directory below CTF/, else the file stem."""
    parts = [p for p in path.split("/")[1:] if not re.match(r"(year|month|day|date)=", p)]
    if len(parts) > 1:
        return "CTF/" + parts[0]
    stem = re.sub(r"\.parquet$", "", parts[0], flags=re.I) if parts else "CTF"
    stem = re.sub(r"[-_]?\d[\d_-]*$", "", stem) or stem
    return "CTF/" + stem


# --- optional domain checks (owner-approved, ADR-0022) -------------------------
#
# Run only after every required role is confirmed (no blockers), on rows of the
# EXPLORATION period only (2025-01-01 .. 2025-09-30; no trailing 2024 rows, no
# embargo rows, never holdout rows). They report aggregate data-quality counts
# only: no rows, no per-market or per-time values, no prices over time, no
# events, returns, price paths or SSTR-type statistics.

CODE_ROLES = ("direction_D", "outcome_seq", "taker_direction", "neg_risk")
MAX_CODES = 20


@dataclass
class DomainSummary:
    files_read: int = 0
    rows_checked: int = 0  # exploration-period rows
    rows_excluded_outside_exploration_period: int = 0  # trailing 2024 and embargo rows
    rows_null_timestamp: int = 0
    nulls: dict[str, int] = field(default_factory=dict)
    violations: dict[str, int] = field(default_factory=dict)
    codes: dict[str, dict[str, int]] = field(default_factory=dict)  # distinct code values
    consistency_mismatches: dict[str, int] = field(default_factory=dict)


def _bump(d: dict[str, int], key: str, n: int) -> None:
    d[key] = d.get(key, 0) + int(n)


def domain_update(s: DomainSummary, df: pl.DataFrame, cols: dict[str, str]) -> None:
    """Accumulate aggregate data-quality counts for one exploration-period frame."""
    s.rows_checked += df.height
    for role, c in cols.items():
        _bump(s.nulls, role, df[c].null_count())

    def num(role: str) -> pl.Series:
        return df[cols[role]].cast(pl.Float64, strict=False)

    # Domain checks (§3: p_r in (0, 1); D_r in {+1, -1}; quantities positive).
    if "p_event" in cols:
        x = num("p_event")
        _bump(s.violations, "p_event_outside_open_unit_interval", ((x <= 0) | (x >= 1)).sum())
    if "price" in cols:
        x = num("price")
        _bump(s.violations, "price_outside_open_unit_interval", ((x <= 0) | (x >= 1)).sum())
    if "direction_D" in cols:
        x = num("direction_D")
        _bump(s.violations, "D_not_plus_or_minus_one", (~x.is_in([1.0, -1.0])).sum())
    for role in ("shares", "usdc_amount"):
        if role in cols:
            _bump(s.violations, f"{role}_non_positive", (num(role) <= 0).sum())
    if "neg_risk" in cols:
        _bump(
            s.violations,
            "neg_risk_true",
            (df[cols["neg_risk"]].cast(pl.Boolean, strict=False).fill_null(False)).sum(),
        )
    for role in CODE_ROLES:
        if role in cols:
            d = s.codes.setdefault(role, {})
            for v, n in df[cols[role]].value_counts().iter_rows():
                if str(v) in d or len(d) < MAX_CODES:
                    _bump(d, str(v), n)
                else:
                    _bump(d, "<other>", n)

    # Consistency checks between provider fields (counts of mismatching rows).
    if {"p_event", "price", "outcome_seq"} <= cols.keys():
        p, pr, k = cols["p_event"], cols["price"], cols["outcome_seq"]
        diff = df.select(
            (
                pl.when(pl.col(k) == 1).then(pl.col(pr)).otherwise(1 - pl.col(pr)).cast(pl.Float64)
                - pl.col(p).cast(pl.Float64)
            ).abs()
        ).to_series()
        _bump(s.consistency_mismatches, "p_event_vs_price_rule_gt_1e-9", (diff > 1e-9).sum())
    if {"shares", "usdc_amount", "price"} <= cols.keys():
        u, q, pr = num("usdc_amount"), num("shares"), num("price")
        rel = (u - q * pr).abs() / u.abs()
        _bump(s.consistency_mismatches, "usdc_vs_shares_x_price_rel_gt_1e-6", (rel > 1e-6).sum())


def as_dict(x) -> dict:
    return asdict(x)


__all__ = [
    "METADATA",
    "OPTIONAL",
    "REQUIRED",
    "REQUIRED_K0",
    "SHARES",
    "Blocker",
    "DomainSummary",
    "RoleResult",
    "SchemaVariant",
    "ctf_blockers",
    "ctf_table_key",
    "daily_blockers",
    "domain_update",
    "map_roles",
    "schema_variants",
    "type_family",
]
