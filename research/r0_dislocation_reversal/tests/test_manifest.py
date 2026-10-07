from __future__ import annotations

from datetime import date

import pytest
from conftest import B

from r0.manifest import (
    FileEntry,
    Listing,
    classify,
    infer_days,
    missing_days,
    part_files,
    render,
    render_manifest_md,
    side_of,
)


@pytest.mark.parametrize(
    "path,expected",
    [
        ("daily_aligned/2025-10-07.parquet", (date(2025, 10, 7), date(2025, 10, 7))),
        ("daily_aligned/date=2025-10-08/part-0.parquet", (date(2025, 10, 8), date(2025, 10, 8))),
        (
            "daily_aligned/year=2025/month=10/day=7/x.parquet",
            (date(2025, 10, 7), date(2025, 10, 7)),
        ),
        ("daily_aligned/20251007.parquet", (date(2025, 10, 7), date(2025, 10, 7))),
        ("daily_aligned/2025_10_07.parquet", (date(2025, 10, 7), date(2025, 10, 7))),
        ("daily_aligned/2025-10.parquet", (date(2025, 10, 1), date(2025, 10, 31))),
        ("daily_aligned/2024-02.parquet", (date(2024, 2, 1), date(2024, 2, 29))),
        ("daily_aligned/2025-09-30_2025-10-08.parquet", (date(2025, 9, 30), date(2025, 10, 8))),
        ("daily_aligned/part-00012345.parquet", None),
        ("daily_aligned/65123456.parquet", None),
        ("daily_aligned/20251399.parquet", None),
    ],
)
def test_infer_days(path, expected):
    assert infer_days(path) == expected


def e(path: str, size: int = 100, **kw) -> FileEntry:
    return classify(FileEntry(path, size, "o" * 40, "s" * 64, **kw))


DAY = 86400
T2412_30 = B - 282 * DAY  # 2024-12-30T00:00:00Z


def probed(path: str, lo: int, hi: int, size: int = 100) -> FileEntry:
    """An entry whose placement came from complete footer statistics."""
    return e(path, size, ts_min=lo, ts_max=hi, placement_verified=True)


def test_pinned_day_constant():
    from datetime import UTC, datetime

    assert datetime.fromtimestamp(T2412_30, UTC).isoformat() == "2024-12-30T00:00:00+00:00"


@pytest.mark.parametrize(
    "lo,hi,side,need",
    [
        (T2412_30 - 10, T2412_30 - 1, "n/a", "not-needed"),
        (T2412_30 - 10, T2412_30, "pre_holdout", "required-pre-holdout"),
        (B - DAY, B - 1, "pre_holdout", "required-pre-holdout"),
        (B, B + DAY - 1, "holdout", "required-holdout"),
        (B - 10, B + 10, "straddle", "required-both"),
    ],
)
def test_daily_placement_from_footer_only(lo, hi, side, need):
    f = probed("daily_aligned/any-name.parquet", lo, hi)
    assert (f.side, f.need, f.date_source) == (side, need, "footer")


@pytest.mark.parametrize(
    "path,hint",
    [
        ("daily_aligned/2024-12-29.parquet", "before-pinned-range"),
        ("daily_aligned/2025-10-07.parquet", "pre_holdout"),
        ("daily_aligned/2025-10-08.parquet", "holdout"),
        ("daily_aligned/2025-10.parquet", "straddle"),
        ("daily_aligned/part-1.parquet", "undated"),
    ],
)
def test_names_alone_are_never_authoritative(path, hint):
    f = e(path)  # not probed
    assert (f.side, f.need, f.name_hint) == ("unprobed", "unresolved", hint)
    g = e(path, placement_verified=False)  # probe failed / incomplete statistics
    assert (g.side, g.need) == ("unverified", "unresolved")
    for part in ("pre-holdout", "holdout"):
        assert f not in part_files([f], part) and g not in part_files([g], part)


def test_misleading_old_filename_with_exploration_rows():
    # Named as a 2023 day (would look "not needed"), but holds exploration rows.
    f = probed("daily_aligned/2023-01-01.parquet", B - 100 * DAY, B - 99 * DAY)
    assert f.name_hint == "before-pinned-range"
    assert (f.side, f.need) == ("pre_holdout", "required-pre-holdout")


@pytest.mark.parametrize("path", ["daily_aligned/2025-01-01.PARQUET", "daily_aligned/x.Parquet"])
def test_mixed_case_extension_is_parquet(path):
    from r0.manifest import is_parquet

    assert is_parquet(path)
    assert e(path).need == "unresolved"  # a candidate, not silently "not-needed"
    assert probed(path, B - 10, B - 1).need == "required-pre-holdout"
    assert e("CTF/resolutions/a.PARQUET").need == "required-ctf-resolution"


@pytest.mark.parametrize(
    "path,need",
    [
        ("daily_aligned/notes.json", "not-needed"),
        ("daily_aligned_multi/2025-01-01.parquet", "not-needed"),
        ("OrderFilled/2025-01-01.parquet", "not-needed"),
        ("CTF/resolutions/2023-01-01.parquet", "required-ctf-resolution"),
        ("CTF/resolutions.parquet", "required-ctf-resolution"),
        ("CTF/conditionPreparations/2025-01.parquet", "not-needed"),
        ("CTF/preparations.parquet", "not-needed"),
        ("CTF/splits/2025-01-01.parquet", "not-needed"),
        ("CTF/weird/2025-01-01.parquet", "unknown"),
        ("README.md", "required-card"),
        (".gitattributes", "not-needed"),
    ],
)
def test_classify_other_layers(path, need):
    assert e(path).need == need


def test_parts_totals_and_render():
    files = [
        e("README.md", 10),
        e("CTF/resolutions/2025-01.parquet", 20),
        probed("daily_aligned/2024-12-30.parquet", T2412_30, T2412_30 + DAY - 1, 1000),
        probed("daily_aligned/2025-10.parquet", B - DAY, B + DAY, 2000),
        probed("daily_aligned/2025-11-01.parquet", B + 24 * DAY, B + 25 * DAY - 1, 4000),
        e("OrderFilled/2025-01-01.parquet", 99999),
    ]
    assert sum(f.size for f in part_files(files, "pre-holdout")) == 3000
    assert sum(f.size for f in part_files(files, "holdout")) == 4000
    assert sum(f.size for f in part_files(files, "ctf")) == 20
    lst = Listing("o/n", "main", "c" * 40, "2026-10-06T00:00:00", "http://x", True, files)
    text = render(lst)
    assert "pinned commit sha : " + "c" * 40 in text
    assert "Files crossing the pre-holdout/holdout boundary: 1" in text
    assert "minimum now (card + ctf + pre-holdout): 0.00 GiB (3,030 bytes)" in text
    assert "PLACEMENT UNRESOLVED" not in text
    assert Listing.from_json(lst.to_json()) == lst
    assert "| `daily_aligned/2025-10.parquet` | required-both |" in render_manifest_md(lst)
    unprobed = Listing(
        "o/n",
        "main",
        "c" * 40,
        "t",
        "http://x",
        False,
        [e("daily_aligned/2025-10-07.parquet", 500)],
    )
    text = render(unprobed)
    assert "PLACEMENT UNRESOLVED: 1 daily_aligned files" in text
    assert (
        "FILE NAME ONLY (not authoritative)" in text and "pre-holdout : 0.00 GiB (0 bytes)" in text
    )


def test_missing_days():
    files = [
        probed(f"daily_aligned/{d}.parquet", lo, lo + DAY - 1)
        for d, lo in (("2024-12-30", T2412_30), ("2025-01-01", T2412_30 + 2 * DAY))
    ]
    gaps = missing_days(files)
    assert gaps[0] == "2024-12-31" and "2025-01-01" not in gaps and gaps[-1] == "2026-04-28"


def test_side_of_exact_boundary():
    assert side_of(B - 10, B - 1) == "pre_holdout"
    assert side_of(B - 10, B) == "straddle"
    assert side_of(B, B + 5) == "holdout"


def test_ctf_placement_does_not_change_need():
    g = e("CTF/resolutions/2025-12-01.parquet", placement_verified=False)
    assert g.need == "required-ctf-resolution" and g.side == "all-dates"
    assert g.scope_authority == "pending-A2-ctf-loader" and g.date_source is None


@pytest.mark.parametrize("bad", ["../x.parquet", "/abs.parquet", "a/../../b"])
def test_manifest_rejects_unsafe_paths(bad):
    lst = Listing("o/n", "main", "c" * 40, "t", "http://x", True, [e("README.md")])
    text = lst.to_json().replace('"README.md"', f'"{bad}"')
    with pytest.raises(ValueError, match="unsafe"):
        Listing.from_json(text)


# --- Codex re-check, finding 2: consumers require per-file placement authority ---

from dataclasses import replace as _replace  # noqa: E402
from pathlib import Path  # noqa: E402

from r0.manifest import (  # noqa: E402
    LEGACY_MESSAGE,
    MANIFEST_VERSION,
    ManifestError,
    load_authoritative_manifest,
    placement_state,
    require_authoritative_placement,
)

LEGACY = Path(__file__).parent / "fixtures" / "legacy_manifest_23a8eda.json"


def current_listing(files: list[FileEntry]) -> Listing:
    return Listing("o/n", "main", "c" * 40, "t", "http://x", True, files, MANIFEST_VERSION)


def good_files() -> list[FileEntry]:
    return [
        e("README.md", 10),
        probed("daily_aligned/2024-12-29.parquet", T2412_30 - DAY, T2412_30 - 1),
        probed("daily_aligned/2025-02-01.parquet", B - 200 * DAY, B - 199 * DAY),
        probed("daily_aligned/2025-10-07.PARQUET", B - 100, B + 100),
    ]


def test_legacy_fixture_is_refused():
    with pytest.raises(ManifestError, match=LEGACY_MESSAGE):
        load_authoritative_manifest(LEGACY)
    legacy = Listing.from_json(LEGACY.read_text())
    assert legacy.manifest_version == 0 and legacy.footers_probed is True  # coarse flag lies
    # a version number alone never replaces the per-file evidence
    upgraded = _replace(legacy, manifest_version=MANIFEST_VERSION)
    with pytest.raises(ManifestError, match="no placement evidence"):
        require_authoritative_placement(upgraded)


def test_valid_current_manifest_is_accepted():
    lst = current_listing(good_files())
    require_authoritative_placement(lst)
    assert Listing.from_json(lst.to_json()) == lst


@pytest.mark.parametrize(
    "entry,state",
    [
        (probed("daily_aligned/a.parquet", B - 10, B - 1), "verified"),
        (e("daily_aligned/a.parquet", placement_verified=False), "unresolved"),
        (e("daily_aligned/a.parquet"), "absent"),  # placement_verified=None
        (
            FileEntry(
                "daily_aligned/a.parquet",
                1,
                "o" * 40,
                None,
                placement_verified=True,
                date_source="footer",
            ),
            "absent",
        ),  # no timestamp evidence
        (
            FileEntry(
                "daily_aligned/a.parquet",
                1,
                "o" * 40,
                None,
                placement_verified=True,
                date_source="name",
                ts_min=B - 10,
                ts_max=B - 1,
            ),
            "absent",
        ),
        (
            FileEntry(
                "daily_aligned/a.parquet",
                1,
                "o" * 40,
                None,
                placement_verified=True,
                date_source="footer",
                ts_min=(B - 10) * 1000,
                ts_max=B * 1000,
            ),
            "absent",
        ),
    ],
    ids=["verified", "unresolved", "none", "no-ts", "name-source", "not-seconds"],
)
def test_placement_state(entry, state):
    assert placement_state(entry) == state


def _with(files: list[FileEntry], path: str, **changes) -> Listing:
    return current_listing([_replace(f, **changes) if f.path == path else f for f in files])


@pytest.mark.parametrize(
    "path,changes,match",
    [
        # old filename holding exploration rows, serialized from its name as not-needed
        (
            "daily_aligned/2024-12-29.parquet",
            dict(
                placement_verified=None,
                ts_min=None,
                ts_max=None,
                date_source="name",
                need="not-needed",
                side="n/a",
            ),
            "no placement evidence",
        ),
        # mixed-case straddling file serialized from its name
        (
            "daily_aligned/2025-10-07.PARQUET",
            dict(
                placement_verified=None,
                date_source="name",
                need="required-pre-holdout",
                side="pre_holdout",
            ),
            "no placement evidence",
        ),
        (
            "daily_aligned/2025-02-01.parquet",
            dict(placement_verified=None),
            "no placement evidence",
        ),
        ("daily_aligned/2025-02-01.parquet", dict(ts_min=None), "no placement evidence"),
        ("daily_aligned/2025-02-01.parquet", dict(placement_verified=False), "unresolved"),
        # misleading serialized need despite valid evidence
        ("daily_aligned/2025-10-07.PARQUET", dict(need="required-pre-holdout"), "does not match"),
        ("daily_aligned/2025-02-01.parquet", dict(need="not-needed", side="n/a"), "does not match"),
        (
            "daily_aligned/2024-12-29.parquet",
            dict(need="required-pre-holdout", side="pre_holdout"),
            "does not match",
        ),
    ],
    ids=[
        "old-name-not-needed",
        "mixed-case-straddle",
        "verified-none",
        "missing-ts",
        "unresolved",
        "need-straddle-lie",
        "need-not-needed-lie",
        "need-old-lie",
    ],
)
def test_per_file_evidence_is_required(path, changes, match):
    with pytest.raises(ManifestError, match=match):
        require_authoritative_placement(_with(good_files(), path, **changes))


def test_coarse_flags_are_not_enough():
    files = good_files()
    with pytest.raises(ManifestError, match=LEGACY_MESSAGE):
        require_authoritative_placement(_replace(current_listing(files), manifest_version=0))
    with pytest.raises(ManifestError, match=LEGACY_MESSAGE):
        require_authoritative_placement(_replace(current_listing(files), footers_probed=False))
    # footers_probed=True with one entry lacking evidence
    lst = _with(files, "daily_aligned/2025-02-01.parquet", placement_verified=None)
    assert lst.footers_probed is True
    with pytest.raises(ManifestError):
        require_authoritative_placement(lst)


# --- ADR-0026: CTF entries never carry temporal placement ----------------------


def ctf_entry(**kw) -> FileEntry:
    return e("CTF/resolutions.parquet", 20, **kw)


def test_ctf_entry_is_all_dates_with_pending_scope():
    f = ctf_entry()
    assert (f.need, f.side, f.scope_authority) == (
        "required-ctf-resolution",
        "all-dates",
        "pending-A2-ctf-loader",
    )
    assert f.placement_verified is None and f.ts_min is None and f.date_source is None
    assert e("CTF/preparations.parquet").need == "not-needed"
    assert e("daily_aligned/2025-01-01.parquet").scope_authority == "footer-block_timestamp"
    require_authoritative_placement(current_listing([*good_files(), f]))  # accepted


@pytest.mark.parametrize(
    "change",
    [
        {"placement_verified": True},
        {"placement_verified": False},
        {"ts_min": B - 10, "ts_max": B - 5},
        {"date_source": "footer"},
        {"first_day": "2025-01-01", "last_day": "2025-01-02"},
        {"side": "pre_holdout"},
        {"scope_authority": "footer-block_timestamp"},
        {"scope_authority": None},
        {"need": "not-needed"},
    ],
)
def test_ctf_entry_claiming_placement_or_scope_is_refused(change):
    bad = _replace(ctf_entry(), **change)
    with pytest.raises(ManifestError, match="CTF entry"):
        require_authoritative_placement(current_listing([*good_files(), bad]))


def test_previous_manifest_version_is_refused():
    with pytest.raises(ManifestError, match=LEGACY_MESSAGE):
        require_authoritative_placement(
            _replace(current_listing(good_files()), manifest_version=MANIFEST_VERSION - 1)
        )


def test_ctf_part_is_disabled():
    from r0.manifest import DISABLED_PARTS, PARTS

    assert "ctf" in DISABLED_PARTS and "ctf-mapping" not in PARTS
