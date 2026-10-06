"""The only reader of raw Parquet files. Applies the holdout partition rule.

Two kinds of read exist:

- ``read_footer``: Parquet footer metadata only (schema, row count, and the
  min/max statistics of the timestamp column). No row values are read and no
  other column statistics are returned. It is permitted for any file, because
  placing files and checking schemas requires it and it reveals no outcomes.
- ``read_rows``: row values, always under a ``Scope``. In the PRE_HOLDOUT
  scope only rows with ``ts < PARTITION_BOUNDARY`` (the holdout start) leave
  this module; row
  groups whose timestamp statistics start at or after the boundary are not
  read at all, and rows with a null timestamp are dropped (they cannot be
  shown to be pre-boundary). The HOLDOUT scope requires a
  ``HoldoutAuthorization`` and returns only rows with ``ts >= boundary``.

A file that straddles the boundary is therefore split mechanically by row
timestamp; it is never assigned wholesale to either side.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import polars as pl
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from r0.paths import HoldoutAuthorization, _require_auth, check_readable
from r0.periods import PARTITION_BOUNDARY

Source = Path | str | BinaryIO


class Scope(enum.Enum):
    # Low-level access control only. PRE_HOLDOUT = every row before the
    # holdout start (trailing 2024 rows, the exploration period and the
    # embargo). It is NOT the exploration period: research operations must
    # further restrict rows to r0.periods.EXPLORATION_START..EXPLORATION_END.
    PRE_HOLDOUT = "pre_holdout"
    HOLDOUT = "holdout"


@dataclass(frozen=True)
class FooterInfo:
    schema: pa.Schema
    num_rows: int
    num_row_groups: int
    ts_column: str | None
    ts_min: int | None
    ts_max: int | None
    ts_stats_complete: bool  # every row group had min/max stats for ts_column


@dataclass(frozen=True)
class ReadStats:
    rows_read: int
    rows_kept: int
    rows_null_ts: int
    row_groups_total: int
    row_groups_skipped: int
    rows_in_skipped_groups: int  # excluded by row-group statistics, never read


def _open(source: Source, auth: HoldoutAuthorization | None = None):
    if isinstance(source, (str, Path)):
        return pq.ParquetFile(check_readable(source, auth, raw_reader=True))
    return pq.ParquetFile(source)


_UNIT_PER_SECOND = {"s": 1, "ms": 1_000, "us": 1_000_000, "ns": 1_000_000_000}


def _ts_stats(pf: pq.ParquetFile, col: str) -> list[tuple[int, int] | None]:
    """Per row group (min, max) of ``col`` in floored epoch seconds, or None.

    Uses the raw physical (integer) statistics and the column's Arrow unit, so
    no time-zone or nanosecond conversion is involved. Non-integer physical
    statistics are treated as absent (the rows are then read and filtered).
    """
    t = pf.schema_arrow.field(col).type
    per_s = _UNIT_PER_SECOND[t.unit] if pa.types.is_timestamp(t) else 1
    md_schema = pf.metadata.schema
    leaf = next(j for j in range(len(md_schema)) if md_schema.column(j).path == col)
    out: list[tuple[int, int] | None] = []
    for i in range(pf.metadata.num_row_groups):
        st = pf.metadata.row_group(i).column(leaf).statistics
        lo = st.min_raw if st is not None and st.has_min_max else None
        hi = st.max_raw if st is not None and st.has_min_max else None
        if isinstance(lo, int) and isinstance(hi, int):
            out.append((lo // per_s, hi // per_s))
        else:
            out.append(None)
    return out


def read_footer(
    source: Source, ts_candidates: tuple[str, ...] = ("block_timestamp",)
) -> FooterInfo:
    pf = _open(source)
    schema = pf.schema_arrow
    ts_col = next((c for c in ts_candidates if c in schema.names), None)
    ts_min = ts_max = None
    complete = False
    if ts_col is not None and _is_ts_type(schema.field(ts_col).type):
        stats = _ts_stats(pf, ts_col)
        known = [s for s in stats if s is not None]
        complete = len(known) == len(stats)
        if known:
            ts_min = min(s[0] for s in known)
            ts_max = max(s[1] for s in known)
    return FooterInfo(
        schema, pf.metadata.num_rows, pf.metadata.num_row_groups, ts_col, ts_min, ts_max, complete
    )


def _is_ts_type(t: pa.DataType) -> bool:
    return pa.types.is_integer(t) or pa.types.is_timestamp(t)


def to_epoch_seconds(arr: pa.ChunkedArray | pa.Array) -> pa.ChunkedArray | pa.Array:
    """Integer seconds stay as they are; Arrow timestamps are floored to seconds."""
    t = arr.type
    if pa.types.is_integer(t):
        return pc.cast(arr, pa.int64())
    if pa.types.is_timestamp(t):
        secs = pc.floor_temporal(arr, unit="second") if t.unit != "s" else arr
        return pc.cast(pc.cast(secs, pa.timestamp("s", tz=t.tz), safe=False), pa.int64())
    raise TypeError(f"timestamp column must be integer seconds or an Arrow timestamp, got {t}")


# Plausible epoch-second range (2017-07-14 .. 2096-10-02). Values outside it mean
# the column is not epoch seconds (e.g. milliseconds or days), and the boundary
# comparison would be meaningless: refuse instead of guessing.
_EPOCH_S_MIN, _EPOCH_S_MAX = 1_500_000_000, 4_000_000_000


def _check_epoch_seconds(ts: pa.ChunkedArray | pa.Array) -> None:
    if len(ts) - ts.null_count == 0:
        return
    mm = pc.min_max(ts)
    lo, hi = mm["min"].as_py(), mm["max"].as_py()
    if lo < _EPOCH_S_MIN or hi > _EPOCH_S_MAX:
        raise ValueError(f"timestamp values [{lo}, {hi}] are not plausible epoch seconds")


def read_rows(
    source: Source,
    columns: list[str],
    *,
    ts_column: str,
    scope: Scope,
    auth: HoldoutAuthorization | None = None,
) -> tuple[pl.DataFrame, ReadStats]:
    """Read ``columns`` (plus ``ts_column``) restricted to ``scope``'s side.

    ``ts_column`` is returned as int64 epoch seconds.
    """
    if scope is Scope.HOLDOUT:
        _require_auth(auth)
    elif scope is not Scope.PRE_HOLDOUT:
        raise ValueError(scope)
    pf = _open(source, auth)
    names = pf.schema_arrow.names
    cols = list(dict.fromkeys([*columns, ts_column]))
    missing = [c for c in cols if c not in names]
    if missing:
        raise KeyError(f"columns not in file: {missing}")
    if not _is_ts_type(pf.schema_arrow.field(ts_column).type):
        raise TypeError(f"{ts_column} is not an integer/timestamp column")

    stats = _ts_stats(pf, ts_column)
    for s in stats:
        if s is not None and (s[0] < _EPOCH_S_MIN or s[1] > _EPOCH_S_MAX):
            raise ValueError(f"{ts_column} statistics {s} are not plausible epoch seconds")
    keep_groups = []
    for i, s in enumerate(stats):
        if s is not None:
            if scope is Scope.PRE_HOLDOUT and s[0] >= PARTITION_BOUNDARY:
                continue
            if scope is Scope.HOLDOUT and s[1] < PARTITION_BOUNDARY:
                continue
        keep_groups.append(i)

    if keep_groups:
        table = pf.read_row_groups(keep_groups, columns=cols)
    else:
        table = pf.schema_arrow.empty_table().select(cols)
    ts = to_epoch_seconds(table.column(ts_column))
    n_null = ts.null_count
    _check_epoch_seconds(ts)
    if scope is Scope.PRE_HOLDOUT:
        mask = pc.less(ts, PARTITION_BOUNDARY)
    else:
        mask = pc.greater_equal(ts, PARTITION_BOUNDARY)
    table = table.set_column(table.schema.get_field_index(ts_column), ts_column, ts)
    kept = table.filter(mask, null_selection_behavior="drop")
    df = pl.from_arrow(kept)
    assert isinstance(df, pl.DataFrame)
    kept_set = set(keep_groups)
    skipped_rows = sum(
        pf.metadata.row_group(i).num_rows for i in range(len(stats)) if i not in kept_set
    )
    return df, ReadStats(
        table.num_rows,
        kept.num_rows,
        n_null,
        len(stats),
        len(stats) - len(keep_groups),
        skipped_rows,
    )
