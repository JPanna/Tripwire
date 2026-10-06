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


@pytest.mark.parametrize(
    "path,side,need",
    [
        ("daily_aligned/2024-12-29.parquet", "n/a", "not-needed"),
        ("daily_aligned/2024-12-30.parquet", "pre_holdout", "required-pre-holdout"),
        ("daily_aligned/2025-10-07.parquet", "pre_holdout", "required-pre-holdout"),
        ("daily_aligned/2025-10-08.parquet", "holdout", "required-holdout"),
        ("daily_aligned/2026-04-28.parquet", "holdout", "required-holdout"),
        ("daily_aligned/2025-10.parquet", "straddle", "required-both"),
        ("daily_aligned/part-1.parquet", "unknown", "unknown"),
        ("daily_aligned_multi/2025-01-01.parquet", "n/a", "not-needed"),
        ("OrderFilled/2025-01-01.parquet", "n/a", "not-needed"),
        ("CTF/resolutions/2023-01-01.parquet", "pre_holdout", "required-ctf-resolution"),
        ("CTF/resolutions.parquet", "unknown", "required-ctf-resolution"),
        ("CTF/conditionPreparations/2025-01.parquet", "pre_holdout", "optional-ctf-mapping"),
        ("CTF/splits/2025-01-01.parquet", "n/a", "not-needed"),
        ("CTF/weird/2025-01-01.parquet", "pre_holdout", "unknown"),
        ("README.md", "n/a", "required-card"),
        (".gitattributes", "n/a", "not-needed"),
    ],
)
def test_classify(path, side, need):
    f = e(path)
    assert (f.side, f.need) == (side, need)


def test_footer_overrides_file_name():
    f = e("daily_aligned/2025-10-07.parquet", ts_min=B - 3600, ts_max=B + 10)
    assert f.date_source == "footer" and f.side == "straddle" and f.need == "required-both"
    g = e("daily_aligned/part-1.parquet", ts_min=B - 100, ts_max=B - 1)
    assert g.side == "pre_holdout" and g.need == "required-pre-holdout"


def test_parts_totals_and_render():
    files = [
        e("README.md", 10),
        e("CTF/resolutions/2025-01.parquet", 20),
        e("daily_aligned/2024-12-30.parquet", 1000),
        e("daily_aligned/2025-10.parquet", 2000),
        e("daily_aligned/2025-11-01.parquet", 4000),
        e("OrderFilled/2025-01-01.parquet", 99999),
    ]
    assert sum(f.size for f in part_files(files, "pre-holdout")) == 3000
    assert sum(f.size for f in part_files(files, "holdout")) == 4000
    assert sum(f.size for f in part_files(files, "ctf")) == 20
    lst = Listing("o/n", "main", "c" * 40, "2026-10-06T00:00:00", "http://x", False, files)
    text = render(lst)
    assert "pinned commit sha : " + "c" * 40 in text
    assert "Files crossing the pre-holdout/holdout boundary: 1" in text
    assert "minimum now (card + ctf + pre-holdout): 0.00 GiB (3,030 bytes)" in text
    assert Listing.from_json(lst.to_json()) == lst
    assert "| `daily_aligned/2025-10.parquet` | required-both |" in render_manifest_md(lst)


def test_missing_days():
    files = [e(f"daily_aligned/{d}.parquet") for d in ("2024-12-30", "2025-01-01")]
    gaps = missing_days(files)
    assert gaps[0] == "2024-12-31" and "2025-01-01" not in gaps and gaps[-1] == "2026-04-28"


def test_side_of_exact_boundary():
    assert side_of(B - 10, B - 1) == "pre_holdout"
    assert side_of(B - 10, B) == "straddle"
    assert side_of(B, B + 5) == "holdout"


def test_unverified_placement_is_never_wholesale():
    f = e("daily_aligned/2025-12-01.parquet", placement_verified=False)
    assert (f.side, f.need) == ("unverified", "required-both")
    assert f in part_files([f], "pre-holdout") and f not in part_files([f], "holdout")
    g = e("CTF/resolutions/2025-12-01.parquet", placement_verified=False)
    assert g.need == "required-ctf-resolution"


@pytest.mark.parametrize("bad", ["../x.parquet", "/abs.parquet", "a/../../b"])
def test_manifest_rejects_unsafe_paths(bad):
    lst = Listing("o/n", "main", "c" * 40, "t", "http://x", True, [e("README.md")])
    text = lst.to_json().replace('"README.md"', f'"{bad}"')
    with pytest.raises(ValueError, match="unsafe"):
        Listing.from_json(text)
