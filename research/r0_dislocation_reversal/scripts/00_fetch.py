"""Stage B: list, pin, download and verify R0 source files.

    uv run python research/r0_dislocation_reversal/scripts/00_fetch.py --list
    uv run python ... 00_fetch.py --list --probe-footers --write-manifest
    uv run python ... 00_fetch.py --download pre-holdout --approve-bytes <N from listing>
    uv run python ... 00_fetch.py --verify

``--list`` downloads no research files. ``--probe-footers`` reads only Parquet
footers through HTTP byte ranges (schema and timestamp statistics; no row
values). Only ``daily_aligned`` files are footer-probed: ``CTF/`` tables have no
timestamp column and are all-date files whose row scope is PENDING the A2 loader
(ADR-0026). ``--download`` requires a written manifest and the exact byte total
of the part, so a bulk download cannot start by accident; the ``ctf`` part is
disabled until the A2 scoped loader is accepted.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime

import _bootstrap  # noqa: F401

from r0.hub import DATASET_REPO, DEFAULT_ENDPOINT, HubClient, RemoteFile
from r0.integrity import IntegrityError, verify_file
from r0.manifest import (
    DISABLED_PARTS,
    LAYER_DAILY,
    MANIFEST_VERSION,
    PARTS,
    FileEntry,
    Listing,
    ManifestError,
    classify,
    gib,
    is_parquet,
    load_authoritative_manifest,
    part_files,
    render,
    render_manifest_md,
    require_authoritative_placement,
)
from r0.paths import RESEARCH_DIR, raw_cache_dir, raw_file
from r0.rawread import read_footer

MANIFEST_JSON = RESEARCH_DIR / "DATA_MANIFEST.json"
MANIFEST_MD = RESEARCH_DIR / "DATA_MANIFEST.md"
TS_CANDIDATES = ("block_timestamp", "timestamp", "block_time")


def _probe(client: HubClient, repo: str, sha: str, f: FileEntry) -> tuple[FileEntry, int, bool]:
    """Footer-probe one file. Returns (entry, bytes fetched, placement verified)."""
    rf = RemoteFile(client, client.file_url(repo, sha, f.path), f.size)
    try:
        info = read_footer(rf, TS_CANDIDATES)
    except Exception as e:  # reported; placement then counts as unverified
        g = replace(f, notes=[*f.notes, f"footer probe failed: {type(e).__name__}"])
        return g, rf.bytes_fetched, False
    g = replace(f, ts_min=info.ts_min, ts_max=info.ts_max, notes=[])
    verified = True
    if info.duplicate_names:
        g.notes.append(f"duplicate field names {list(info.duplicate_names)}")
    if info.ts_column is None:
        g.notes.append("no timestamp column among " + ", ".join(TS_CANDIDATES))
        verified = False
    elif not info.ts_stats_complete:
        # Partial statistics do not bound the file's rows: do not trust them.
        g.notes.append("timestamp statistics missing for some row groups; range not trusted")
        verified = False
    if g.ts_min is not None and not (
        1_500_000_000 <= g.ts_min <= (g.ts_max or g.ts_min) <= 4_000_000_000
    ):
        g.notes.append(f"{info.ts_column} statistics are not epoch seconds; ignored")
        verified = False
    if not verified:
        g.ts_min = g.ts_max = None
    g.placement_verified = verified
    return g, rf.bytes_fetched, verified


def probe_targets(files: list[FileEntry]) -> list[int]:
    """Every daily_aligned Parquet file, whatever its name (file names never
    decide placement). CTF tables are not placement-probed: they have no
    timestamp column and their row scope authority is the A2 loader (ADR-0026)."""
    return [i for i, f in enumerate(files) if is_parquet(f.path) and f.layer == LAYER_DAILY]


def _carry_local_hashes(new: list[FileEntry], old: Listing) -> None:
    """Keep locally computed SHA-256 values for unchanged files of the same revision."""
    prev = {f.path: f for f in old.files}
    for f in new:
        o = prev.get(f.path)
        if o and f.sha256 is None and o.sha256 and (o.size, o.git_oid) == (f.size, f.git_oid):
            f.sha256 = o.sha256
            f.notes.append("sha256 computed locally at download (no upstream LFS hash)")


def cmd_list(a: argparse.Namespace) -> int:
    client = HubClient(a.endpoint)
    sha = client.resolve_revision(a.repo, a.revision)
    if a.write_manifest and MANIFEST_JSON.exists():
        old = Listing.from_json(MANIFEST_JSON.read_text())
        if old.revision_sha != sha and not a.replace_manifest:
            sys.exit(
                f"refusing: DATA_MANIFEST.json pins {old.revision_sha}, upstream now resolves to "
                f"{sha}. Re-pinning changes the data; pass --replace-manifest to do it on purpose."
            )
    tree = client.list_tree(a.repo, sha)

    def fresh(i: int) -> FileEntry:
        r = tree[i]
        return FileEntry(r.path, r.size, r.git_oid, r.sha256)

    files = [classify(fresh(i)) for i in range(len(tree))]
    probed = False
    unverified: list[str] = []
    # A manifest must not rest on file names alone: always verify placement
    # from footer timestamp statistics before writing one.
    if a.probe_footers or a.write_manifest:
        targets = probe_targets(files)
        fetched = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = ex.map(lambda i: _probe(client, a.repo, sha, fresh(i)), targets)
            for i, (g, n, ok) in zip(targets, results, strict=True):
                if not ok:
                    unverified.append(g.path)
                files[i] = classify(g)
                fetched += n
        probed = not unverified
        print(f"[footer probe: {len(targets)} files, {gib(fetched)} fetched]", file=sys.stderr)
    listing = Listing(
        repo_id=a.repo,
        revision_requested=a.revision,
        revision_sha=sha,
        listed_at_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
        endpoint=a.endpoint,
        footers_probed=probed,
        files=sorted(files, key=lambda f: f.path),
        manifest_version=MANIFEST_VERSION,
    )
    print(render(listing), end="")
    if unverified:
        print(
            f"\nFOOTER PROBE FAILED or incomplete for {len(unverified)} files; their "
            "placement is unresolved:"
        )
        print("\n".join(f"  {p}" for p in unverified[:50]))
        if len(unverified) > 50:
            print(f"  ... and {len(unverified) - 50} more")
    if a.write_manifest:
        try:
            if unverified:
                raise ManifestError("footer probe failed or incomplete")
            require_authoritative_placement(listing)  # the same check consumers run
        except ManifestError as e:
            sys.exit(
                "refusing to write the manifest: placement must come from complete footer "
                f"timestamp statistics for every candidate (no override); {e}"
            )
        if MANIFEST_JSON.exists():
            old = Listing.from_json(MANIFEST_JSON.read_text())
            if old.revision_sha == sha:
                _carry_local_hashes(listing.files, old)
        MANIFEST_JSON.write_text(listing.to_json())
        MANIFEST_MD.write_text(render_manifest_md(listing))
        print(f"\nwrote {MANIFEST_JSON.name} and {MANIFEST_MD.name}")
    return 0


def _load_manifest() -> Listing:
    if not MANIFEST_JSON.exists():
        sys.exit("no DATA_MANIFEST.json: run --list --write-manifest first")
    try:
        return load_authoritative_manifest(MANIFEST_JSON)
    except ManifestError as e:
        sys.exit(f"refusing: {e}")


def cmd_download(a: argparse.Namespace) -> int:
    if a.download in DISABLED_PARTS:
        sys.exit(f"refusing: {DISABLED_PARTS[a.download]}")
    listing = _load_manifest()
    sel = part_files(listing.files, a.download)
    total = sum(f.size for f in sel)
    if a.approve_bytes != total:
        print(f"part {a.download!r}: {len(sel)} files, {gib(total)}")
        sys.exit(f"refusing: --approve-bytes must equal {total} (the exact part size)")
    cache = raw_cache_dir(listing.repo_id, listing.revision_sha)
    cache.mkdir(parents=True, exist_ok=True)
    dest = {f.path: raw_file(listing.repo_id, listing.revision_sha, f.path) for f in sel}
    need = sum(f.size for f in sel if not dest[f.path].exists())
    free = shutil.disk_usage(cache).free
    if need * 1.05 > free:
        sys.exit(f"refusing: need {gib(need)} (+5%), free {gib(free)}")
    client = HubClient(listing.endpoint)
    changed = False
    for k, f in enumerate(sel, 1):
        got = client.download(
            client.file_url(listing.repo_id, listing.revision_sha, f.path),
            dest[f.path],
            f.size,
            f.sha256,
            f.git_oid,
            root=cache,
        )
        if f.sha256 is None:
            f.sha256 = got
            f.notes.append("sha256 computed locally at download (no upstream LFS hash)")
            changed = True
        print(f"[{k}/{len(sel)}] ok {f.path}")
    if changed:
        MANIFEST_JSON.write_text(listing.to_json())
        MANIFEST_MD.write_text(render_manifest_md(listing))
    return 0


def cmd_verify(a: argparse.Namespace) -> int:
    """Re-hash cached files; with --part, a missing file of that part is a failure."""
    listing = _load_manifest()
    cache = raw_cache_dir(listing.repo_id, listing.revision_sha)
    required = {f.path for f in part_files(listing.files, a.part)} if a.part else set()
    bad = present = missing = 0
    for f in listing.files:
        p = raw_file(listing.repo_id, listing.revision_sha, f.path)
        if not (p.exists() or p.is_symlink()):
            if f.path in required:
                missing += 1
                print(f"MISSING {f.path}")
            continue
        present += 1
        try:
            verify_file(p, f.size, f.sha256, f.git_oid)
        except IntegrityError as e:
            bad += 1
            print(f"MISMATCH {f.path}: {e}")
    leftovers = list(cache.rglob("*.part")) if cache.exists() else []
    for x in leftovers:
        print(f"LEFTOVER partial download {x.relative_to(cache)}")
    print(
        f"pinned {listing.revision_sha}: verified {present} cached files; {bad} mismatches"
        + (f"; {missing} of {len(required)} files of part {a.part!r} missing" if a.part else "")
    )
    return 1 if bad or missing else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="list and classify; downloads nothing")
    g.add_argument("--download", choices=PARTS, help="download one part into the raw cache")
    g.add_argument(
        "--verify", action="store_true", help="re-hash cached files against the manifest"
    )
    p.add_argument("--repo", default=DATASET_REPO)
    p.add_argument("--revision", default="main", help="branch/tag/sha to pin (resolved to a sha)")
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    p.add_argument(
        "--probe-footers", action="store_true", help="read Parquet footers via byte ranges"
    )
    p.add_argument("--write-manifest", action="store_true", help="implies --probe-footers")
    p.add_argument("--approve-bytes", type=int, default=-1)
    p.add_argument("--replace-manifest", action="store_true", help="allow re-pinning the revision")
    p.add_argument("--part", choices=PARTS, help="with --verify: require every file of this part")
    a = p.parse_args(argv)
    if a.list:
        return cmd_list(a)
    if a.download:
        return cmd_download(a)
    return cmd_verify(a)


if __name__ == "__main__":
    raise SystemExit(main())
