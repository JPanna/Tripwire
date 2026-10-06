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
        ("CTF/conditionPreparations/2025-01.parquet", "optional-ctf-mapping"),
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
    assert g.need == "required-ctf-resolution" and g.side == "unverified"


@pytest.mark.parametrize("bad", ["../x.parquet", "/abs.parquet", "a/../../b"])
def test_manifest_rejects_unsafe_paths(bad):
    lst = Listing("o/n", "main", "c" * 40, "t", "http://x", True, [e("README.md")])
    text = lst.to_json().replace('"README.md"', f'"{bad}"')
    with pytest.raises(ValueError, match="unsafe"):
        Listing.from_json(text)
