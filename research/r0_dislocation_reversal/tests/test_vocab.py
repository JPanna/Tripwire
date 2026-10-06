from __future__ import annotations

import pyarrow as pa
import pytest
from conftest import write_parquet

from r0.periods import EXPLORATION_END, EXPLORATION_START
from r0.vocab import build_vocab, collect, tokens

COLS = {
    "market_id": "condition_id",
    "timestamp": "block_timestamp",
    "question": "question",
    "category": "category",
    "tags": "tags",
}


def test_exploration_period_bounds_are_exact_seconds(data_root):
    ts = [EXPLORATION_START - 1, EXPLORATION_START, EXPLORATION_END, EXPLORATION_END + 1]
    t = pa.table(
        {
            "block_timestamp": pa.array(ts, pa.int64()),
            "condition_id": ["before", "first", "last", "after"],
            "question": ["q"] * 4,
            "category": ["c"] * 4,
            "tags": [["t"]] * 4,
        }
    )
    p = write_parquet(data_root / "raw" / "edge.parquet", t, row_group_size=1)
    df, stats = collect([p], COLS)
    assert sorted(df["condition_id"].to_list()) == ["first", "last"]
    assert stats["rows_in_exploration_period"] == 2


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, []),
        ("Crypto", ["Crypto"]),
        ('["Crypto", "Bitcoin"]', ["Crypto", "Bitcoin"]),
        ([{"label": "Crypto", "slug": "crypto"}], ["Crypto"]),
        (["a", ["b"]], ["a", "b"]),
        ("a, b", ["a, b"]),  # never split on commas
        ("  ", []),
    ],
)
def test_tokens(value, expected):
    assert tokens(value) == expected


def test_build_vocab_is_deterministic(data_root):
    t = pa.table(
        {
            "block_timestamp": pa.array([EXPLORATION_START + i for i in range(30)], pa.int64()),
            "condition_id": [f"m{i}" for i in range(30)],
            "question": [f"Q{i}" for i in range(30)],
            "category": ["Crypto" if i % 3 == 0 else "Sports" for i in range(30)],
            "tags": [["x"]] * 30,
        }
    )
    p = write_parquet(data_root / "raw" / "d.parquet", t)
    df, _ = collect([p], COLS)
    a, b = build_vocab(df, COLS, 5), build_vocab(df.reverse(), COLS, 5)
    assert a.examples_random == b.examples_random and len(a.examples_random) == 5
    assert dict(a.category_counts) == {"Crypto": 10, "Sports": 20}
