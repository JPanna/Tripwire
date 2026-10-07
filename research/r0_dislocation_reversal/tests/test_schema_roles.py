"""Unit tests for role mapping and BLOCKER-2 conditions (owner rule: never substitute)."""

from __future__ import annotations

import pyarrow as pa
import pytest

from r0.roles import CTF_RESOLUTION_ROLES, DAILY_ROLES
from r0.schema import (
    coverage_blocker,
    ctf_blockers,
    ctf_table_key,
    daily_blockers,
    drift_blocker,
    duplicate_field_blocker,
    map_roles,
    schema_variants,
)

FULL = {
    "block_timestamp": pa.int64(),
    "condition_id": pa.string(),
    "p_event": pa.float64(),
    "D": pa.int8(),
    "outcome_seq": pa.int8(),
    "usdc_amount": pa.float64(),
    "price": pa.float64(),
    "maker": pa.string(),
    "taker": pa.string(),
    "asset_id": pa.string(),
}
CONF = {"token_id": "asset_id", "shares": "NONE"}


def variants(*schemas: dict):
    return schema_variants(
        [(f"f{i}", pa.schema(list(s.items())), None, None) for i, s in enumerate(schemas)]
    )


def run(*schemas: dict, conf=CONF):
    v = variants(*schemas)
    res = map_roles(DAILY_ROLES, v, conf)
    return {r.key: r for r in res}, [b.role for b in daily_blockers(res, v)]


def test_full_schema_has_no_blockers():
    roles, blockers = run(FULL)
    assert blockers == []
    assert roles["p_event"].status == "FOUND" and roles["token_id"].status == "CONFIRMED"
    assert roles["shares"].status == "CONFIRMED_ABSENT"  # owner said shares=NONE: fallback


def test_exact_name_with_wrong_type_is_ambiguous():
    roles, blockers = run({**FULL, "p_event": pa.string()})
    assert roles["p_event"].status == "AMBIGUOUS" and "p_event" in blockers


def test_schema_drift_is_ambiguous():
    drifted = {k: v for k, v in FULL.items() if k != "D"}
    roles, blockers = run(FULL, drifted)
    assert roles["direction_D"].status == "AMBIGUOUS" and "direction_D" in blockers


def test_case_matters_for_exact_names():
    s = {k: v for k, v in FULL.items() if k != "D"} | {"d": pa.int8()}
    roles, blockers = run(s)
    assert roles["direction_D"].status == "CANDIDATES" and "direction_D" in blockers


def test_confirmation_type_is_checked():
    # A string column confirmed for an integer role is not accepted.
    roles, blockers = run(FULL, conf={**CONF, "outcome_seq": "maker"})
    assert roles["outcome_seq"].status == "AMBIGUOUS" and "outcome_seq" in blockers


def test_confirmation_of_column_missing_in_a_variant():
    other = {k: v for k, v in FULL.items() if k != "asset_id"}
    roles, blockers = run(FULL, other)
    assert roles["token_id"].status == "AMBIGUOUS" and "token_id" in blockers


def test_possible_share_column_blocks_the_fallback():
    conf = {"token_id": "asset_id"}
    roles, blockers = run({**FULL, "token_amount": pa.float64()}, conf=conf)
    assert roles["shares"].status == "CANDIDATES" and blockers == ["shares"]
    roles, blockers = run(
        {**FULL, "token_amount": pa.float64()}, conf={**conf, "shares": "token_amount"}
    )
    assert roles["shares"].status == "CONFIRMED" and blockers == []
    roles, blockers = run({**FULL, "token_amount": pa.float64()}, conf={**conf, "shares": "NONE"})
    assert roles["shares"].status == "CONFIRMED_ABSENT" and blockers == []


def test_unrecognised_share_column_q_keeps_the_fallback_blocked():
    """Codex finding 7: no heuristic match is not evidence that no share column exists."""
    conf = {"token_id": "asset_id"}
    schema = {**FULL, "q": pa.float64()}
    roles, blockers = run(schema, conf=conf)
    assert roles["shares"].status == "MISSING" and "q" not in roles["shares"].candidates
    assert blockers == ["shares"]  # usdc_amount and price exist, yet the fallback is blocked
    roles, blockers = run(schema, conf={**conf, "shares": "q"})
    assert roles["shares"].status == "CONFIRMED" and blockers == []
    roles, blockers = run(schema, conf={**conf, "shares": "NONE"})
    assert roles["shares"].status == "CONFIRMED_ABSENT" and blockers == []


def test_shares_none_still_needs_usdc_and_price():
    no_price = {k: v for k, v in FULL.items() if k != "price"}
    _, blockers = run(no_price)
    assert blockers == ["shares"]


def test_confirmed_absent_does_not_resolve_a_required_role():
    roles, blockers = run(FULL, conf={**CONF, "p_event": "NONE"})
    assert roles["p_event"].status == "CONFIRMED_ABSENT" and "p_event" in blockers


def test_ctf_blockers():
    # the real CTF/resolutions.parquet schema (pinned dataset card; footer, 2026-10-07)
    real = {
        "id": pa.string(),
        "condition_id": pa.string(),
        "oracle": pa.string(),
        "question_id": pa.string(),
        "outcome_slot_count": pa.int64(),
        "payout_numerators": pa.list_(pa.string()),
    }
    good = variants(real)
    res = map_roles(CTF_RESOLUTION_ROLES, good, {})
    st = {r.key: r.status for r in res}
    assert st["ctf_record_id"] == st["ctf_payouts"] == st["ctf_slot_count"] == "FOUND"
    assert "ctf_resolution_ts" not in st  # no timestamp column is expected in CTF/
    assert ctf_blockers({"CTF/resolutions": res}, {"CTF/resolutions": good}) == []
    no_id = variants({k: v for k, v in real.items() if k != "id"})
    res2 = map_roles(CTF_RESOLUTION_ROLES, no_id, {})
    assert [b.role for b in ctf_blockers({"CTF/r": res2}, {"CTF/r": no_id})] == ["ctf_record_id"]
    renamed = variants(
        {
            **{k: v for k, v in real.items() if k != "payout_numerators"},
            "payouts": pa.list_(pa.string()),
        }
    )
    res3 = map_roles(CTF_RESOLUTION_ROLES, renamed, {})
    assert [b.role for b in ctf_blockers({"CTF/r": res3}, {"CTF/r": renamed})] == ["ctf_payouts"]
    assert [b.role for b in ctf_blockers({}, {"CTF/r": good})] == ["ctf_resolution_table"]
    two = ctf_blockers({"CTF/a": res, "CTF/b": res}, {"CTF/a": good, "CTF/b": good})
    assert [b.role for b in two] == ["ctf_resolution_table"] and "CTF/a" in two[0].problem


def test_no_metadata_fallback_for_resolution_time_or_value():
    """t_res and v(m) never come from frozen metadata (§5.3, A2)."""
    import re

    for r in CTF_RESOLUTION_ROLES:
        for col in ("resolved_at", "winning_outcome_label", "resolution_status", "block_timestamp"):
            assert col not in r.exact and not re.search(r.hints, col, re.I), (r.key, col)
    daily_with_meta = variants(
        {"resolved_at": pa.timestamp("us"), "winning_outcome_label": pa.string()}
    )
    res = map_roles(CTF_RESOLUTION_ROLES, daily_with_meta, {})
    assert all(r.status == "MISSING" for r in res if r.level == "required")


@pytest.mark.parametrize(
    "path,key",
    [
        ("CTF/resolutions/2025-01-01.parquet", "CTF/resolutions"),
        ("CTF/resolutions/year=2025/month=1/x.parquet", "CTF/resolutions"),
        ("CTF/resolutions.parquet", "CTF/resolutions"),
        ("CTF/splits_2025-01.parquet", "CTF/splits"),
        ("CTF/resolutions_2025.PARQUET", "CTF/resolutions"),
    ],
)
def test_ctf_table_key(path, key):
    assert ctf_table_key(path) == key


def test_domain_update_counts_violations():
    import polars as pl

    from r0.schema import DomainSummary, domain_update

    df = pl.DataFrame(
        {
            "p_event": [0.5, 0.0, 1.2, None],
            "price": [0.5, 0.0, 0.3, 0.4],
            "D": [1, 0, -1, 1],
            "outcome_seq": [1, 1, 2, 2],
            "token_amount": [10.0, -1.0, 2.0, 1.0],
            "usdc_amount": [5.0, 0.0, 0.6, 9.0],
            "neg_risk": [False, True, False, None],
        }
    )
    cols = {
        "p_event": "p_event",
        "price": "price",
        "direction_D": "D",
        "outcome_seq": "outcome_seq",
        "shares": "token_amount",
        "usdc_amount": "usdc_amount",
        "neg_risk": "neg_risk",
    }
    s = DomainSummary()
    domain_update(s, df, cols)
    assert s.rows_checked == 4 and s.nulls["p_event"] == 1
    assert s.violations == {
        "p_event_outside_open_unit_interval": 2,
        "price_outside_open_unit_interval": 1,
        "D_not_plus_or_minus_one": 1,
        "shares_non_positive": 1,
        "usdc_amount_non_positive": 1,
        "neg_risk_true": 1,
    }
    assert s.codes["direction_D"] == {"1": 2, "0": 1, "-1": 1}
    # row 3: outcome_seq 2 -> 1 - 0.3 = 0.7 != 1.2; row 4: 0.6 vs null p_event is not counted
    assert s.consistency_mismatches["p_event_vs_price_rule_gt_1e-9"] == 1


# --- Codex findings 5 and 6: duplicate names, drift and coverage --------------


def _schema(fields):
    return pa.schema(fields)  # a list keeps duplicates; a dict would collapse them


BASE = list(FULL.items())


@pytest.mark.parametrize(
    "extra",
    [
        [("p_event", pa.float64())],  # duplicate, same type
        [("p_event", pa.string())],  # duplicate, different type
        [("asset_id", pa.string())],  # duplicate of an owner-confirmed candidate
    ],
    ids=["same-type", "different-type", "confirmed-candidate"],
)
def test_duplicate_field_names_block(extra):
    files = [("f0", _schema(BASE)), ("f1", _schema(BASE + extra))]
    b = duplicate_field_blocker("daily_aligned", files)
    assert b is not None and "duplicate" in b.role
    assert b.available_fields == [extra[0][0]]
    assert duplicate_field_blocker("daily_aligned", [("f0", _schema(BASE))]) is None


def test_drift_in_any_file_blocks():
    v = variants(FULL, FULL, {**FULL, "extra": pa.int8()})
    b = drift_blocker("daily_aligned", v)
    assert b is not None and "drift" in b.role and "extra" in b.problem
    assert drift_blocker("daily_aligned", variants(FULL, FULL)) is None


def test_coverage_blocker():
    assert coverage_blocker("t", [], []) is None
    assert "1 required file" in coverage_blocker("t", ["a.parquet"], []).problem
    assert "footer(s) unreadable" in coverage_blocker("t", [], ["b: OSError"]).problem
