"""Stage B: classify the pinned dataset listing, estimate sizes, write the manifest.

Nothing here downloads research files. Classification uses the upstream
listing (path, size, hashes) and, optionally, Parquet footer timestamp
statistics (``r0.rawread.read_footer``), which contain no row values.

File naming in ``TimeSeventeen/Polymarket-v1`` could not be observed from the
agent's environment (2026-10-06). Dates inferred from paths are *hints only*:
the placement of every ``daily_aligned`` Parquet file (including whether it is
needed at all) comes only from its footer timestamp statistics. Until a file
has been probed successfully its need is ``unresolved``, and an unresolved
file blocks the manifest and any download. ``.parquet`` is matched
case-insensitively everywhere (``is_parquet``).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta

from r0.paths import safe_repo_path
from r0.periods import (
    DATASET_LAST_DAY,
    PARTITION_BOUNDARY,
    PARTITION_BOUNDARY_DAY,
    PINNED_FIRST_DAY,
)

# Layer directory names as stated by the owner (PREREGISTRATION.md §2.1).
LAYER_DAILY = "daily_aligned"
LAYER_MULTI = "daily_aligned_multi"
LAYER_ORDERFILLED = "OrderFilled"
LAYER_CTF = "CTF"

# CTF sub-table keywords (path, case-insensitive). The CTF layer is described
# as preparations, splits, merges, resolutions and redemptions [EXCERPT].
CTF_NEEDED = ("resolution",)
CTF_MAPPING = ("prepar",)
CTF_NOT_NEEDED = ("split", "merge", "redemption", "redeem", "transfer")

_DATE_PATTERNS = [
    re.compile(r"year=(\d{4})/month=(\d{1,2})/day=(\d{1,2})"),
    re.compile(r"(?<!\d)(\d{4})[-_](\d{2})[-_](\d{2})(?!\d)"),
    re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)"),
]
_MONTH_PATTERNS = [
    re.compile(r"year=(\d{4})/month=(\d{1,2})(?!\d)(?!/day=)"),
    re.compile(r"(?<!\d)(\d{4})[-_](\d{2})(?![-_]?\d)"),
]
_PLAUSIBLE = (date(2020, 1, 1), date(2027, 12, 31))


@dataclass
class FileEntry:
    path: str
    size: int
    git_oid: str
    sha256: str | None
    layer: str = ""
    first_day: str | None = None  # ISO date, inclusive
    last_day: str | None = None
    date_source: str | None = None  # "name" | "footer"
    ts_min: int | None = None
    ts_max: int | None = None
    side: str = ""  # pre_holdout | holdout | straddle | unverified | unknown | n/a
    need: str = ""  # see classify()
    notes: list[str] = field(default_factory=list)
    # True: footer timestamp statistics were read completely (authoritative).
    # False: a probe was attempted but failed or was incomplete. None: not probed.
    placement_verified: bool | None = None
    # Side suggested by the file name only (never authoritative).
    name_hint: str | None = None


def is_parquet(path: str) -> bool:
    return path.lower().endswith(".parquet")


def layer_of(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else ""


def _valid(y: int, m: int, d: int) -> date | None:
    try:
        x = date(y, m, d)
    except ValueError:
        return None
    return x if _PLAUSIBLE[0] <= x <= _PLAUSIBLE[1] else None


def infer_days(path: str) -> tuple[date, date] | None:
    """Inclusive UTC day range a path's name suggests, or None."""
    days: list[date] = []
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(path):
            d = _valid(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if d:
                days.append(d)
        if days:
            return min(days), max(days)
    for pat in _MONTH_PATTERNS:
        for m in pat.finditer(path):
            first = _valid(int(m.group(1)), int(m.group(2)), 1)
            if first:
                nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
                days += [first, nxt - timedelta(days=1)]
        if days:
            return min(days), max(days)
    return None


def _day_start(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def side_of(first_ts: int, last_ts: int) -> str:
    if last_ts < PARTITION_BOUNDARY:
        return "pre_holdout"
    if first_ts >= PARTITION_BOUNDARY:
        return "holdout"
    return "straddle"


def _name_hint(first_day: str | None, last_day: str | None) -> str:
    if not first_day or not last_day:
        return "undated"
    first, last = date.fromisoformat(first_day), date.fromisoformat(last_day)
    if last < PINNED_FIRST_DAY:
        return "before-pinned-range"
    return side_of(_day_start(first), _day_start(last + timedelta(days=1)) - 1)


def classify(e: FileEntry) -> FileEntry:
    """Assign layer, date range, partition side and need for one file.

    need values:
      required-pre-holdout / required-holdout / required-both   (daily_aligned,
                                     from footer evidence only)
      unresolved                     daily_aligned Parquet without verified
                                     footer evidence (blocks manifest/download)
      required-ctf-resolution        all resolution files, whatever their date
      optional-ctf-mapping           CTF preparation files (slot mapping support)
      required-card                  dataset card / top-level docs
      not-needed                     out of scope, or footer-verified to hold
                                     only rows before the pinned range
      unknown                        CTF file of an unrecognised table
    """
    e.layer = layer_of(e.path)
    days = infer_days(e.path)
    name_first = days[0].isoformat() if days else None
    name_last = days[1].isoformat() if days else None
    e.name_hint = _name_hint(name_first, name_last)
    verified = e.placement_verified is True and e.ts_min is not None and e.ts_max is not None
    if verified:
        e.date_source = "footer"
        e.first_day = datetime.fromtimestamp(e.ts_min, UTC).date().isoformat()
        e.last_day = datetime.fromtimestamp(e.ts_max, UTC).date().isoformat()
        e.side = side_of(e.ts_min, e.ts_max)
    else:
        e.date_source = "name" if days else None
        e.first_day, e.last_day = name_first, name_last
        e.side = "unverified" if e.placement_verified is False else "unprobed"

    low = e.path.lower()
    if e.layer == "" or (e.layer not in (LAYER_DAILY, LAYER_MULTI, LAYER_ORDERFILLED, LAYER_CTF)):
        top_doc = e.layer == "" and low.endswith((".md", ".cff", ".txt", ".bib"))
        e.need = "required-card" if top_doc else "not-needed"
        if not top_doc and e.layer:
            e.notes.append("unrecognised top-level directory")
        e.side = "n/a"
        return e
    if e.layer in (LAYER_MULTI, LAYER_ORDERFILLED):
        e.need, e.side = "not-needed", "n/a"
        return e
    if e.layer == LAYER_CTF:
        if not is_parquet(e.path):
            e.need, e.side = "not-needed", "n/a"
        elif any(k in low for k in CTF_NEEDED):
            e.need = "required-ctf-resolution"
        elif any(k in low for k in CTF_MAPPING):
            e.need = "optional-ctf-mapping"
        elif any(k in low for k in CTF_NOT_NEEDED):
            e.need, e.side = "not-needed", "n/a"
        else:
            e.need = "unknown"
            e.notes.append("CTF file with no recognised table name; inspect manually")
        return e
    # daily_aligned
    if not is_parquet(e.path):
        e.need, e.side = "not-needed", "n/a"
        return e
    if not verified:
        # File names are never authoritative: whatever the name suggests, the
        # file may hold study-period rows until its footer shows otherwise.
        e.need = "unresolved"
        e.notes.append(
            "placement unverified (footer probe failed or incomplete)"
            if e.placement_verified is False
            else "placement not yet verified from footer statistics"
        )
        return e
    if e.ts_max < _day_start(PINNED_FIRST_DAY):
        e.need, e.side = "not-needed", "n/a"
        return e
    if date.fromisoformat(e.first_day) > DATASET_LAST_DAY:
        e.notes.append("rows after the stated dataset end 2026-04-28")
    e.need = {
        "pre_holdout": "required-pre-holdout",
        "holdout": "required-holdout",
        "straddle": "required-both",
    }[e.side]
    if e.side == "straddle":
        e.notes.append("crosses the partition boundary: rows split by timestamp")
    return e


def unresolved(files: list[FileEntry]) -> list[FileEntry]:
    """daily_aligned Parquet files whose placement is not footer-verified."""
    return [f for f in files if f.need == "unresolved"]


@dataclass
class Listing:
    repo_id: str
    revision_requested: str
    revision_sha: str
    listed_at_utc: str
    endpoint: str
    footers_probed: bool
    files: list[FileEntry]
    # Writers set MANIFEST_VERSION; a manifest without it (legacy) loads as 0
    # and is refused by require_authoritative_placement.
    manifest_version: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, sort_keys=False) + "\n"

    @staticmethod
    def from_json(text: str) -> Listing:
        d = json.loads(text)
        d["files"] = [FileEntry(**f) for f in d["files"]]
        for f in d["files"]:
            safe_repo_path(f.path)
        return Listing(**d)


# --- placement authority (the one check every manifest consumer runs) ------

MANIFEST_VERSION = 2
LEGACY_MESSAGE = (
    "manifest lacks authoritative per-file placement; re-run --list --write-manifest "
    "with the current tooling"
)
_EPOCH_S_MIN, _EPOCH_S_MAX = 1_500_000_000, 4_000_000_000


class ManifestError(ValueError):
    """A manifest that must not be consumed."""


def placement_state(f: FileEntry) -> str:
    """For a daily_aligned Parquet entry: "verified", "unresolved" or "absent".

    "verified" requires the evidence the current writer records after a
    successful footer probe: placement_verified is True, footer-sourced dates,
    and plausible epoch-second timestamp bounds. "unresolved" means a probe was
    attempted and failed. Anything else (legacy writers, hand edits, names
    only) is "absent".
    """
    if f.placement_verified is False:
        return "unresolved"
    ok_ts = (
        isinstance(f.ts_min, int)
        and isinstance(f.ts_max, int)
        and not isinstance(f.ts_min, bool)
        and not isinstance(f.ts_max, bool)
        and _EPOCH_S_MIN <= f.ts_min <= f.ts_max <= _EPOCH_S_MAX
    )
    if f.placement_verified is True and f.date_source == "footer" and ok_ts:
        return "verified"
    return "absent"


def require_authoritative_placement(listing: Listing) -> None:
    """Refuse a manifest unless every daily_aligned Parquet entry -- including
    entries serialized as "not-needed" -- carries authoritative footer placement
    and its serialized side/need equal what that evidence implies. Serialized
    ``need`` and the manifest-wide ``footers_probed`` flag are never trusted on
    their own; nothing is upgraded or reinterpreted."""
    if listing.manifest_version != MANIFEST_VERSION or listing.footers_probed is not True:
        raise ManifestError(LEGACY_MESSAGE)
    for f in listing.files:
        if layer_of(f.path) != LAYER_DAILY or not is_parquet(f.path):
            continue
        state = placement_state(f)
        if state == "absent":
            raise ManifestError(f"{LEGACY_MESSAGE} (no placement evidence: {f.path})")
        if state == "unresolved":
            raise ManifestError(
                f"placement unresolved for {f.path}; re-run --list --write-manifest"
            )
        expect = classify(
            FileEntry(
                f.path,
                f.size,
                f.git_oid,
                f.sha256,
                ts_min=f.ts_min,
                ts_max=f.ts_max,
                placement_verified=True,
            )
        )
        if (f.side, f.need) != (expect.side, expect.need):
            raise ManifestError(
                f"{LEGACY_MESSAGE} (serialized side/need {f.side}/{f.need} of {f.path} does "
                f"not match its footer evidence: {expect.side}/{expect.need})"
            )


def load_authoritative_manifest(path) -> Listing:
    """Read a manifest and run require_authoritative_placement before any use."""
    listing = Listing.from_json(path.read_text())
    require_authoritative_placement(listing)
    return listing


def totals(files: list[FileEntry]) -> dict[str, int]:
    t: dict[str, int] = {}
    for f in files:
        t[f.need] = t.get(f.need, 0) + f.size
        t[f"layer:{f.layer or '<root>'}"] = t.get(f"layer:{f.layer or '<root>'}", 0) + f.size
    t["repo-total"] = sum(f.size for f in files)
    return t


def part_files(files: list[FileEntry], part: str) -> list[FileEntry]:
    """Files making up a download part."""
    sel = {
        "pre-holdout": {"required-pre-holdout", "required-both"},
        "holdout": {"required-holdout"},
        "ctf": {"required-ctf-resolution"},
        "ctf-mapping": {"optional-ctf-mapping"},
        "card": {"required-card"},
    }[part]
    return [f for f in files if f.need in sel]


PARTS = ("card", "ctf", "pre-holdout", "holdout", "ctf-mapping")


def missing_days(files: list[FileEntry]) -> list[str]:
    """UTC days in [2024-12-30, 2026-04-28] not covered by any daily_aligned file."""
    covered: set[date] = set()
    for f in files:
        if f.layer == LAYER_DAILY and f.first_day and f.last_day and f.need != "not-needed":
            d, last = date.fromisoformat(f.first_day), date.fromisoformat(f.last_day)
            while d <= last:
                covered.add(d)
                d += timedelta(days=1)
    out, d = [], PINNED_FIRST_DAY
    while d <= DATASET_LAST_DAY:
        if d not in covered:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def gib(n: int) -> str:
    return f"{n / 2**30:,.2f} GiB ({n:,} bytes)"


def render(listing: Listing) -> str:
    files = listing.files
    t = totals(files)
    lines = [
        "R0 dataset listing (no research files downloaded)",
        f"  repository        : {listing.repo_id} (Hugging Face dataset)",
        f"  revision requested: {listing.revision_requested}",
        f"  pinned commit sha : {listing.revision_sha}",
        f"  listed at (UTC)   : {listing.listed_at_utc}",
        "  footers probed    : "
        + (
            "yes: every candidate probed successfully (timestamp statistics only)"
            if listing.footers_probed
            else "NO: placement is not authoritative (file names are hints only)"
        ),
        f"  partition boundary: rows with block_timestamp < {PARTITION_BOUNDARY} "
        f"({PARTITION_BOUNDARY_DAY.isoformat()}T00:00:00Z) -> pre-holdout side; >= -> holdout side",
        "",
        "Layer sizes (whole repository, for reference):",
    ]
    for k in sorted(k for k in t if k.startswith("layer:")):
        n = sum(1 for f in files if f"layer:{f.layer or '<root>'}" == k)
        lines.append(f"  {k[6:]:<22} {n:>6} files  {gib(t[k])}")
    lines.append(f"  {'TOTAL':<22} {len(files):>6} files  {gib(t['repo-total'])}")
    lines += ["", "Needed for R0, by purpose:"]
    for need in (
        "required-card",
        "required-ctf-resolution",
        "optional-ctf-mapping",
        "required-pre-holdout",
        "required-both",
        "required-holdout",
        "unresolved",
        "unknown",
    ):
        sel = [f for f in files if f.need == need]
        rng = _range([f for f in sel if f.first_day])
        lines.append(f"  {need:<26} {len(sel):>5} files  {gib(sum(f.size for f in sel))}{rng}")
    expl = sum(f.size for f in part_files(files, "pre-holdout"))
    hold = sum(f.size for f in part_files(files, "holdout"))
    ctf = sum(f.size for f in part_files(files, "ctf"))
    card = sum(f.size for f in part_files(files, "card"))
    unk = sum(f.size for f in files if f.need == "unknown")
    lines += [
        "",
        "Download parts (00_fetch.py --download PART --approve-bytes N):",
        f"  card        : {gib(card)}",
        f"  ctf         : {gib(ctf)}   (CTF resolution support; all dates)",
        f"  pre-holdout : {gib(expl)}   "
        "(daily_aligned 2024-12-30 -> 2025-10-07, incl. straddling files)",
        f"  holdout     : {gib(hold)}   "
        "(daily_aligned 2025-10-08 -> end; raw cache only, not read before the freeze)",
        f"  minimum now (card + ctf + pre-holdout): {gib(card + ctf + expl)}",
        f"  all needed  (+ holdout)               : {gib(card + ctf + expl + hold)}",
    ]
    if unk:
        lines.append(f"  UNCLASSIFIED (not counted above)      : {gib(unk)}")
    unres = unresolved(files)
    if unres:
        lines += [
            "",
            f"PLACEMENT UNRESOLVED: {len(unres)} daily_aligned files, "
            f"{gib(sum(f.size for f in unres))}. No manifest or download until every one is "
            "footer-verified. Provisional split by FILE NAME ONLY (not authoritative):",
        ]
        for hint in ("pre_holdout", "straddle", "holdout", "before-pinned-range", "undated"):
            sel = [f for f in unres if f.name_hint == hint]
            lines.append(
                f"  name suggests {hint:<20} {len(sel):>5} files  {gib(sum(f.size for f in sel))}"
            )
    straddle = [
        f for f in files if f.side == "straddle" and f.need.startswith(("required", "optional"))
    ]
    lines += ["", f"Files crossing the pre-holdout/holdout boundary: {len(straddle)}"]
    lines += [f"  {f.path}  [{f.side}; {f.date_source}]" for f in straddle[:50]]
    if len(straddle) > 50:
        lines.append(f"  ... and {len(straddle) - 50} more (see the manifest)")
    gaps = missing_days(files)
    lines += [
        "",
        f"daily_aligned UTC days with no file in 2024-12-30 -> 2026-04-28: {len(gaps)}"
        + ("" if listing.footers_probed else " (from file-name hints; not authoritative)"),
    ]
    if gaps:
        lines.append("  " + ", ".join(gaps[:40]) + (" ..." if len(gaps) > 40 else ""))
    notes = [f for f in files if f.notes and f.need != "not-needed"]
    if notes:
        lines += ["", "Notes:"]
        lines += [f"  {f.path}: {'; '.join(f.notes)}" for f in notes[:60]]
        if len(notes) > 60:
            lines.append(f"  ... and {len(notes) - 60} more (see the manifest)")
    no_sha = [f for f in files if f.need.startswith("required") and not f.sha256]
    lines += [
        "",
        f"Needed files without an upstream LFS SHA-256 (verified by git blob SHA-1; "
        f"SHA-256 computed at download): {len(no_sha)}",
    ]
    return "\n".join(lines) + "\n"


def _range(sel: list[FileEntry]) -> str:
    if not sel:
        return ""
    return f"  [{min(f.first_day for f in sel)} .. {max(f.last_day for f in sel)}]"  # type: ignore[type-var]


def render_manifest_md(listing: Listing) -> str:
    needed = [f for f in listing.files if f.need.startswith(("required", "optional"))]
    out = [
        "# R0 data manifest",
        "",
        "Generated by `scripts/00_fetch.py --list --write-manifest`. Do not edit by hand.",
        "",
        f"- Dataset: Hugging Face `{listing.repo_id}` (CC-BY-4.0; cite the dataset card)",
        f"- Pinned revision: `{listing.revision_sha}` (requested `{listing.revision_requested}`)",
        f"- Listed at: {listing.listed_at_utc} UTC",
        f"- Manifest version: {listing.manifest_version}",
        f"- Footer timestamps probed: {listing.footers_probed}",
        f"- Partition boundary: rows with timestamp < {PARTITION_BOUNDARY} "
        f"({PARTITION_BOUNDARY_DAY}T00:00:00Z) are pre-holdout",
        "",
        "| Path | Need | Side | Days | Size (bytes) | SHA-256 |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for f in needed:
        days = f"{f.first_day}..{f.last_day} ({f.date_source})" if f.first_day else "-"
        sha = f.sha256 or "computed at download"
        out.append(f"| `{f.path}` | {f.need} | {f.side} | {days} | {f.size} | `{sha}` |")
    return "\n".join(out) + "\n"
