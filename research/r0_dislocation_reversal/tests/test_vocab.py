from __future__ import annotations

import json

import pyarrow as pa
import pytest
from conftest import write_parquet

from r0.periods import EXPLORATION_END, EXPLORATION_START
from r0.vocab import (
    DraftClassifier,
    build_vocab,
    collect,
    evaluate_draft,
    project_tokens,
    tokens,
)

COLS = {
    "market_id": "condition_id",
    "timestamp": "block_timestamp",
    "question": "question",
    "category": "category",
    "tags": "tags",
}
T0 = EXPLORATION_START + 1000


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
    col = collect([p], COLS)
    assert sorted(col.by_market) == ["first", "last"]
    assert col.stats["rows_in_exploration_period"] == 2


@pytest.mark.parametrize(
    "value,expected,rejected",
    [
        (None, [], 0),
        ("Crypto", ["Crypto"], 0),
        ('["Crypto", "Bitcoin"]', ["Crypto", "Bitcoin"], 0),
        ([{"label": "Crypto", "slug": "crypto"}], ["Crypto"], 0),
        ({"name": "Crypto", "extra": "x"}, ["Crypto"], 0),
        ({"slug": "crypto"}, ["crypto"], 0),
        ("a, b", ["a, b"], 0),  # never split on commas
        ("  ", [], 0),
        ({"id": 7, "secret": "x"}, [], 1),  # no authorized key: rejected, nothing output
        ({"label": 5}, [], 1),  # authorized key but not a string
        (["a", ["nested"]], ["a"], 1),  # nested list rejected
        ([1, True], [], 2),
        (3.5, [], 1),
    ],
)
def test_projection_rules(value, expected, rejected):
    assert project_tokens(value) == (expected, rejected)
    assert tokens(value) == expected


# --- Codex finding 3: nested metadata never leaks ----------------------------

SECRET_END = "2099-12-31T23:59:59Z-SECRET-END"
SECRET_PAYOUT = 777777123


def _nested_table(as_json: bool) -> pa.Table:
    obj = {
        "label": "Crypto",
        "scheduled_end": SECRET_END,
        "payout_numerators": [SECRET_PAYOUT, 0],
    }
    hidden = {"id": "hidden-id-XYZ", "scheduled_end": SECRET_END}
    if as_json:
        cat = [json.dumps(obj), json.dumps(hidden)]
        tags = [json.dumps([obj, hidden]), json.dumps([hidden])]
    else:
        cat = [obj, hidden]
        tags = [[obj, hidden], [hidden]]
    return pa.table(
        {
            "block_timestamp": pa.array([T0, T0 + 1], pa.int64()),
            "condition_id": ["m1", "m2"],
            "question": ["Bitcoin above 100k?", "Who wins?"],
            "category": cat,
            "tags": tags,
        }
    )


@pytest.mark.parametrize("as_json", [False, True], ids=["struct", "json"])
def test_nested_metadata_outputs_only_authorized_tokens(data_root, as_json):
    p = write_parquet(data_root / "raw" / "nested.parquet", _nested_table(as_json))
    col = collect([p], COLS)
    vocab = build_vocab(col, COLS)
    clf = DraftClassifier(frozenset({"crypto"}), None, None, "x")
    ev = evaluate_draft(col, clf)
    assert dict(vocab.category_counts) == {"Crypto": 1}
    assert dict(vocab.tag_counts) == {"Crypto": 1}
    assert vocab.rejected_metadata_parts == 3  # the unlabelled objects, counted only
    artifacts = json.dumps([vars(vocab), ev, col.by_market], default=str)
    for forbidden in (SECRET_END, str(SECRET_PAYOUT), "hidden-id-XYZ", "payout", "scheduled_end"):
        assert forbidden not in artifacts, forbidden
    assert ev["matched_tag_only"] == 1 and ev["audit_sample_matched"][0]["category"] == ["Crypto"]


def test_non_string_question_is_rejected(data_root):
    t = pa.table(
        {
            "block_timestamp": pa.array([T0], pa.int64()),
            "condition_id": ["m1"],
            "question": [{"text": "secret question payload"}],
            "category": ["c"],
            "tags": [["t"]],
        }
    )
    p = write_parquet(data_root / "raw" / "q.parquet", t)
    col = collect([p], COLS)
    assert col.by_market["m1"][0]["question"] is None
    assert "secret question payload" not in json.dumps(vars(build_vocab(col, COLS)), default=str)


# --- MINOR: deterministic variant ordering ------------------------------------


def _variant_table(order: list[int]) -> pa.Table:
    rows = [
        ("m1", "Who wins the election?", "Politics"),
        ("m1", "Bitcoin up or down?", "Crypto"),
        ("m1", "Another title", "Sports"),
        ("m2", "Plain question", "Sports"),
    ]
    rows = [rows[i] for i in order]
    return pa.table(
        {
            "block_timestamp": pa.array([T0 + i for i in range(len(rows))], pa.int64()),
            "condition_id": [r[0] for r in rows],
            "question": [r[1] for r in rows],
            "category": [r[2] for r in rows],
            "tags": [["t"]] * len(rows),
        }
    )


def test_input_order_cannot_change_reported_examples(data_root):
    clf = DraftClassifier(frozenset({"crypto"}), None, None, "x")
    outs = []
    for k, order in enumerate([[0, 1, 2, 3], [3, 2, 1, 0], [1, 3, 0, 2]]):
        p = write_parquet(data_root / "raw" / f"v{k}.parquet", _variant_table(order))
        col = collect([p], COLS)
        outs.append(json.dumps([vars(build_vocab(col, COLS, 5)), evaluate_draft(col, clf)]))
    assert outs[0] == outs[1] == outs[2]
    ev = json.loads(outs[0])[1]
    # the audit example shows the variant that matched, not an arbitrary first one
    assert ev["audit_sample_matched"][0]["category"] == ["Crypto"]
    assert ev["audit_sample_matched"][0]["question"] == "Bitcoin up or down?"
