from __future__ import annotations

import re
from pathlib import Path

import pyarrow as pa
import pytest
from conftest import B, write_parquet

from r0.paths import HoldoutAccessError, authorize_holdout, raw_cache_dir
from r0.rawread import Scope, read_footer, read_rows


def straddle_table() -> pa.Table:
    # row group 1: all pre-holdout; 2: mixed incl. exact boundary; 3: all holdout
    ts = [B - 900, B - 800, B - 2, B - 1, B, B + 1, B + 100, B + 200]
    return pa.table(
        {
            "block_timestamp": pa.array(ts, pa.int64()),
            "condition_id": [f"m{i}" for i in range(8)],
            "p_event": [0.1 * (i + 1) for i in range(8)],
        }
    )


@pytest.fixture
def raw_file(data_root) -> Path:
    p = raw_cache_dir("o/n", "a" * 40) / "daily_aligned" / "2025-10.parquet"
    return write_parquet(p, straddle_table(), row_group_size=3)


def test_pre_holdout_scope_returns_only_pre_boundary_rows(raw_file):
    df, st = read_rows(
        raw_file, ["condition_id"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT
    )
    assert df["block_timestamp"].to_list() == [B - 900, B - 800, B - 2, B - 1]
    assert df.columns == ["condition_id", "block_timestamp"]
    assert st.row_groups_total == 3 and st.row_groups_skipped == 1
    assert st.rows_kept == 4 and st.rows_in_skipped_groups == 2 and st.rows_read == 6


def test_holdout_scope_requires_authorization(raw_file):
    with pytest.raises(HoldoutAccessError):
        read_rows(raw_file, ["condition_id"], ts_column="block_timestamp", scope=Scope.HOLDOUT)
    df, _ = read_rows(
        raw_file,
        ["condition_id"],
        ts_column="block_timestamp",
        scope=Scope.HOLDOUT,
        auth=authorize_holdout(True, "test"),
    )
    assert df["block_timestamp"].min() == B


def test_null_timestamps_are_dropped(data_root):
    t = pa.table({"block_timestamp": pa.array([B - 5, None, B + 5], pa.int64()), "x": [1, 2, 3]})
    p = write_parquet(data_root / "raw" / "f.parquet", t)
    df, st = read_rows(p, ["x"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)
    assert df["x"].to_list() == [1] and st.rows_null_ts == 1


def test_no_statistics_still_filters_rows(data_root):
    p = write_parquet(
        data_root / "raw" / "nostats.parquet",
        straddle_table(),
        row_group_size=3,
        write_statistics=False,
    )
    df, st = read_rows(p, ["p_event"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)
    assert df["block_timestamp"].max() == B - 1 and st.row_groups_skipped == 0


def test_arrow_timestamp_column_is_floored_to_seconds(data_root):
    # B - 0.5 s is before the boundary; flooring keeps it on the pre-holdout side.
    ms = [(B - 1) * 1000 + 500, B * 1000, B * 1000 + 999]
    t = pa.table({"ts": pa.array(ms, pa.timestamp("ms", tz="UTC")), "x": [1, 2, 3]})
    p = write_parquet(data_root / "raw" / "ts.parquet", t)
    df, _ = read_rows(p, ["x"], ts_column="ts", scope=Scope.PRE_HOLDOUT)
    assert df["x"].to_list() == [1] and df["ts"].to_list() == [B - 1]


def test_millisecond_integers_are_refused(data_root):
    t = pa.table({"block_timestamp": pa.array([(B - 10) * 1000], pa.int64()), "x": [1]})
    p = write_parquet(data_root / "raw" / "ms.parquet", t)
    with pytest.raises(ValueError, match="epoch seconds"):
        read_rows(p, ["x"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)


def test_holdout_only_file_yields_nothing_pre_holdout(data_root):
    t = pa.table({"block_timestamp": pa.array([B, B + 1], pa.int64()), "x": [1, 2]})
    p = write_parquet(data_root / "raw" / "h.parquet", t)
    df, st = read_rows(p, ["x"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)
    assert df.height == 0 and st.row_groups_skipped == 1


def test_missing_column_and_non_timestamp(data_root, raw_file):
    with pytest.raises(KeyError):
        read_rows(raw_file, ["nope"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)
    with pytest.raises(TypeError):
        read_rows(raw_file, ["p_event"], ts_column="condition_id", scope=Scope.PRE_HOLDOUT)


def test_footer_exposes_schema_and_timestamp_stats_only(raw_file):
    info = read_footer(raw_file)
    assert info.schema.names == ["block_timestamp", "condition_id", "p_event"]
    assert (info.ts_min, info.ts_max) == (B - 900, B + 200)
    assert info.ts_stats_complete and info.num_rows == 8 and info.num_row_groups == 3
    fields = set(info.__dataclass_fields__)
    assert fields == {
        "schema",
        "num_rows",
        "num_row_groups",
        "ts_column",
        "ts_min",
        "ts_max",
        "ts_stats_complete",
        "duplicate_names",
    }
    assert info.duplicate_names == ()


def test_footer_handles_nested_columns_before_timestamp(data_root):
    t = pa.table(
        {
            "tags": pa.array([["a", "b"], []], pa.list_(pa.string())),
            "block_timestamp": pa.array([B - 10, B + 10], pa.int64()),
        }
    )
    p = write_parquet(data_root / "raw" / "nested.parquet", t)
    info = read_footer(p)
    assert (info.ts_min, info.ts_max) == (B - 10, B + 10)
    df, _ = read_rows(p, ["tags"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)
    assert df["tags"].to_list() == [["a", "b"]]


def test_only_rawread_parses_parquet():
    """Static guard: no other module or script reads Parquet or Arrow datasets directly."""
    import ast

    root = Path(__file__).resolve().parents[1]
    banned_modules = {"pyarrow.parquet", "pyarrow.dataset", "pyarrow.feather", "pyarrow.orc"}
    text_pat = re.compile(
        r"ParquetFile|read_table|read_parquet|scan_parquet|read_pandas|read_metadata|"
        r"pl\.read_|pl\.scan_|polars\.read_|polars\.scan_|ParquetDataset|\.dataset\("
    )
    offenders = []
    for f in [*root.glob("r0/**/*.py"), *root.glob("scripts/*.py")]:
        if f.name == "rawread.py":
            continue
        src = f.read_text()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                names = {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module, *(f"{node.module}.{a.name}" for a in node.names)}
            else:
                continue
            if names & banned_modules:
                offenders.append(f"{f.name}: import")
        if text_pat.search(src):
            offenders.append(f"{f.name}: call")
    assert offenders == []


@pytest.mark.parametrize("stats", [True, False])
@pytest.mark.parametrize("values", [[(B - 10) * 1000], [20368, 20400]], ids=["ms", "days"])
def test_non_second_integers_refused_with_or_without_statistics(data_root, stats, values):
    t = pa.table({"block_timestamp": pa.array(values, pa.int64()), "x": list(range(len(values)))})
    p = write_parquet(data_root / "raw" / "u.parquet", t, write_statistics=stats)
    with pytest.raises(ValueError, match="epoch seconds"):
        read_rows(p, ["x"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)


def test_naive_timestamp_statistics_are_utc_whatever_the_local_zone(data_root, monkeypatch):
    import time

    secs = [B - 3600, B - 1, B, B + 3600]
    t = pa.table({"ts": pa.array([x * 1000 for x in secs], pa.timestamp("ms")), "x": [1, 2, 3, 4]})
    p = write_parquet(data_root / "raw" / "naive.parquet", t, row_group_size=2)
    for tz in ("America/New_York", "Asia/Bangkok"):
        monkeypatch.setenv("TZ", tz)
        time.tzset()
        df, st = read_rows(p, ["x"], ts_column="ts", scope=Scope.PRE_HOLDOUT)
        assert df["x"].to_list() == [1, 2] and st.row_groups_skipped == 1, tz
    monkeypatch.delenv("TZ")
    time.tzset()


def test_nanosecond_statistics_that_are_not_whole_microseconds(data_root):
    ns = [(B - 1) * 10**9 + 5, B * 10**9 + 7]
    t = pa.table({"ts": pa.array(ns, pa.timestamp("ns", tz="UTC")), "x": [1, 2]})
    p = write_parquet(data_root / "raw" / "ns.parquet", t)
    info = read_footer(p, ("ts",))
    assert (info.ts_min, info.ts_max) == (B - 1, B)
    df, _ = read_rows(p, ["x"], ts_column="ts", scope=Scope.PRE_HOLDOUT)
    assert df["x"].to_list() == [1]


def test_authorized_holdout_read_of_holdout_partition(data_root):
    t = pa.table({"block_timestamp": pa.array([B - 1, B], pa.int64()), "x": [1, 2]})
    p = write_parquet(data_root / "holdout" / "part.parquet", t)
    with pytest.raises(HoldoutAccessError):
        read_rows(p, ["x"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)
    with pytest.raises(HoldoutAccessError):
        read_footer(p)
    df, _ = read_rows(
        p,
        ["x"],
        ts_column="block_timestamp",
        scope=Scope.HOLDOUT,
        auth=authorize_holdout(True, "test"),
    )
    assert df["x"].to_list() == [2]


def test_symlinked_guarded_directories(data_root, tmp_path):
    import os

    from r0.paths import RawCacheAccessError, check_readable

    ext = tmp_path / "ext"
    (ext / "holdout").mkdir(parents=True)
    (ext / "raw").mkdir()
    (ext / "holdout" / "h.parquet").write_bytes(b"x")
    (ext / "raw" / "f.parquet").write_bytes(b"x")
    os.symlink(ext / "holdout", data_root / "holdout")
    os.symlink(ext / "raw", data_root / "raw")
    with pytest.raises(HoldoutAccessError):
        check_readable(data_root / "holdout" / "h.parquet")
    with pytest.raises(HoldoutAccessError):
        check_readable(ext / "holdout" / "h.parquet")  # the real location is guarded too
    with pytest.raises(RawCacheAccessError):
        check_readable(data_root / "raw" / "f.parquet")
    with pytest.raises(RawCacheAccessError):
        check_readable(ext / "raw" / "f.parquet")


def test_no_stage_a_c_script_authorizes_holdout():
    root = Path(__file__).resolve().parents[1]
    for f in root.glob("scripts/*.py"):
        text = f.read_text()
        assert "authorize_holdout" not in text and "Scope.HOLDOUT" not in text, f.name


def test_duplicate_field_names_are_never_resolved_silently(data_root):
    t = pa.Table.from_arrays(
        [pa.array([B - 5], pa.int64()), pa.array([B + 5], pa.int64()), pa.array([1])],
        names=["block_timestamp", "block_timestamp", "x"],
    )
    p = write_parquet(data_root / "raw" / "dup.parquet", t)
    info = read_footer(p)
    assert info.duplicate_names == ("block_timestamp",)
    assert info.ts_column is None and info.ts_min is None  # no statistics from an ambiguous column
    with pytest.raises(ValueError, match="duplicate field names"):
        read_rows(p, ["x"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)


# --- ADR-0026: no CTF row access before the A2 scoped loader exists ------------


def test_ctf_resolution_rows_are_not_readable(data_root):
    """CTF/resolutions has no timestamp column, so the only row reader refuses it
    in every scope: no CTF row access exists until the A2 loader is accepted."""
    t = pa.table(
        {
            "id": ["137_1_1", "137_99999999_2"],
            "condition_id": ["c1", "HOLDOUT-SECRET"],
            "outcome_slot_count": pa.array([2, 2], pa.int64()),
            "payout_numerators": pa.array([["1", "0"], ["0", "1"]], pa.list_(pa.string())),
        }
    )
    p = write_parquet(raw_cache_dir("o/n", "a" * 40) / "CTF" / "resolutions.parquet", t)
    cols = ["condition_id", "payout_numerators"]
    with pytest.raises(KeyError):
        read_rows(p, cols, ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)
    with pytest.raises(TypeError):  # the record id is not a timestamp
        read_rows(p, cols, ts_column="id", scope=Scope.PRE_HOLDOUT)
    with pytest.raises(HoldoutAccessError):
        read_rows(p, cols, ts_column="id", scope=Scope.HOLDOUT)
    info = read_footer(p, ("block_timestamp", "timestamp", "block_time"))
    assert info.ts_column is None and info.ts_min is None  # schema only
