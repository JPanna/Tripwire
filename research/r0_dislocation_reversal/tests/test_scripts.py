"""End-to-end tests of 00_fetch.py and 01_schema.py against a local fake Hub."""

from __future__ import annotations

import io
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import B, load_script

from r0.periods import EXPLORATION_END, EXPLORATION_START, TRAILING_START

REPO, SHA = "Owner/Data-v1", "e" * 40
DAY = 86400
CONFIRM = [
    "--confirm",
    "token_id=asset_id",
    "--confirm",
    "ctf_payouts=payout_numerators",
    "--confirm",
    "shares=token_amount",
]


def pq_bytes(t: pa.Table, rg: int | None = None) -> bytes:
    buf = io.BytesIO()
    pq.write_table(t, buf, row_group_size=rg)
    return buf.getvalue()


def daily(
    rows: list[tuple[int, str, str]],
    drop: tuple[str, ...] = (),
    rename=None,
    extra_cols: dict | None = None,
    duplicate: tuple[str, pa.DataType] | None = None,
) -> bytes:
    """rows: (ts, condition_id, question)."""
    n = len(rows)
    cols = {
        "block_timestamp": pa.array([r[0] for r in rows], pa.int64()),
        "condition_id": [r[1] for r in rows],
        "outcome_seq": pa.array([1 + i % 2 for i in range(n)], pa.int8()),
        "price": [0.4] * n,
        "p_event": [0.4 if i % 2 == 0 else 0.6 for i in range(n)],
        "D": pa.array([1 if i % 3 else -1 for i in range(n)], pa.int8()),
        "taker_direction": pa.array([1] * n, pa.int8()),
        "usdc_amount": [4.0] * n,
        "token_amount": [10.0] * n,
        "maker": ["0xm"] * n,
        "taker": ["0xt"] * n,
        "asset_id": ["123"] * n,
        "neg_risk": [False] * n,
        "category": ["Crypto" if "BTC" in r[2] else "Politics" for r in rows],
        "tags": [["Crypto", "Bitcoin"] if "BTC" in r[2] else ["Elections"] for r in rows],
        "question": [r[2] for r in rows],
        "slug": [r[2].lower().replace(" ", "-") for r in rows],
        "end_date_iso": ["2025-03-01T00:00:00Z"] * n,
    }
    for d in drop:
        cols.pop(d)
    for a, b in (rename or {}).items():
        cols[b] = cols.pop(a)
    for k, v in (extra_cols or {}).items():
        cols[k] = v
    t = pa.table(cols)
    if duplicate is not None:  # a second column with an existing name
        name, dtype = duplicate
        t = t.append_column(pa.field(name, dtype), pa.array([None] * n, dtype))
    return pq_bytes(t, rg=2)


def ctf_res() -> bytes:
    return pq_bytes(
        pa.table(
            {
                "condition_id": ["c1", "c2"],
                "block_timestamp": pa.array([EXPLORATION_START + 5, B + 5], pa.int64()),
                "payout_numerators": [[1, 0], [0, 1]],
                "outcome_slot_count": pa.array([2, 2], pa.int32()),
            }
        )
    )


def files(**daily_kw) -> dict[str, bytes]:
    return {
        "README.md": b"# card",
        "OrderFilled/2025-01-01.parquet": b"o" * 500,
        "CTF/resolutions/2025.parquet": ctf_res(),
        "CTF/splits/2025.parquet": pq_bytes(pa.table({"condition_id": ["c1"], "amount": [1]})),
        "daily_aligned/2024-12-29.parquet": daily(
            [(TRAILING_START - DAY, "cOLD", "Old")], **daily_kw
        ),
        "daily_aligned/2024-12-30.parquet": daily(
            [(TRAILING_START + 30, "cTRAIL", "Trailing only market")], **daily_kw
        ),
        "daily_aligned/2025-02-01.parquet": daily(
            [
                (EXPLORATION_START + 40 * DAY, "c1", "BTC Up or Down 3PM"),
                (EXPLORATION_START + 40 * DAY + 5, "c2", "Will X win the election"),
                (EXPLORATION_START + 40 * DAY + 9, "c3", "BTC above 100k on Feb 1"),
            ],
            **daily_kw,
        ),
        # straddles the boundary: exploration-period, embargo and holdout rows
        "daily_aligned/2025-09.parquet": daily(
            [
                (EXPLORATION_END - 10, "c2", "Will X win the election"),
                (EXPLORATION_END + 3 * DAY, "cEMB", "Embargo only market"),
                (B + 10, "cHOLD", "HOLDOUT-SECRET market"),
                (B + 20, "c2", "HOLDOUT-SECRET variant"),
            ],
            **daily_kw,
        ),
        "daily_aligned/2025-11-01.parquet": daily(
            [(B + 30 * DAY, "cHOLD2", "HOLDOUT-SECRET 2")], **daily_kw
        ),
    }


@pytest.fixture
def env(data_root, tmp_path, monkeypatch, fake_hub_factory):
    fetch = load_script("00_fetch.py")
    schema = load_script("01_schema.py")
    for mod in (fetch, schema):
        monkeypatch.setattr(mod, "MANIFEST_JSON", tmp_path / "DATA_MANIFEST.json")
    monkeypatch.setattr(fetch, "MANIFEST_MD", tmp_path / "DATA_MANIFEST.md")
    monkeypatch.setattr(schema, "REPORT_JSON", tmp_path / "SCHEMA_REPORT.json")
    monkeypatch.setattr(schema, "REPORT_MD", tmp_path / "SCHEMA_REPORT.md")

    def make(lfs: bool = True, extra: dict[str, bytes] | None = None, **kw):
        hub = fake_hub_factory(REPO, SHA, {**files(**kw), **(extra or {})}, page_size=3, lfs=lfs)
        return hub, fetch, schema

    return make


def test_list_downloads_nothing_and_classifies(env, capsys, data_root):
    hub, fetch, _ = env()
    assert fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint]) == 0
    out = capsys.readouterr().out
    assert f"pinned commit sha : {SHA}" in out
    # Names alone are never authoritative: without footers every daily_aligned
    # Parquet file is unresolved (here "2025-09" really straddles the boundary).
    assert "NO: placement is not authoritative" in out
    assert "PLACEMENT UNRESOLVED: 5 daily_aligned files" in out
    assert "Files crossing the pre-holdout/holdout boundary: 0" in out
    assert not any(p.startswith("/cdn/") for p, _ in hub.log)  # no file bytes fetched
    assert not (data_root / "raw").exists()


def test_probe_footers_reads_only_footers(env, capsys):
    hub, fetch, _ = env()
    fetch.main(
        [
            "--list",
            "--repo",
            REPO,
            "--endpoint",
            hub.endpoint,
            "--probe-footers",
            "--write-manifest",
        ]
    )
    lst = json.loads(fetch.MANIFEST_JSON.read_text())
    by = {f["path"]: f for f in lst["files"]}
    assert by["daily_aligned/2025-09.parquet"]["side"] == "straddle"
    assert by["daily_aligned/2025-09.parquet"]["date_source"] == "footer"
    assert by["daily_aligned/2025-02-01.parquet"]["side"] == "pre_holdout"
    assert by["OrderFilled/2025-01-01.parquet"]["need"] == "not-needed"


def test_download_gated_by_exact_bytes(env, capsys, data_root):
    hub, fetch, _ = env()
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    lst = json.loads(fetch.MANIFEST_JSON.read_text())
    need = {"required-pre-holdout", "required-both"}
    total = sum(f["size"] for f in lst["files"] if f["need"] in need)
    # --write-manifest alone must have probed footers (placement never from names alone)
    by = {f["path"]: f for f in lst["files"]}
    assert lst["footers_probed"] is True
    assert by["daily_aligned/2025-09.parquet"]["side"] == "straddle"
    assert by["daily_aligned/2025-09.parquet"]["date_source"] == "footer"
    n_before = len(hub.log)  # the manifest step probed footers via byte ranges
    for wrong in (total - 1, total + 1, -1):
        with pytest.raises(SystemExit, match="refusing"):
            fetch.main(["--download", "pre-holdout", "--approve-bytes", str(wrong)])
    assert len(hub.log) == n_before  # refused before any request
    assert fetch.main(["--verify", "--part", "pre-holdout"]) == 1  # nothing downloaded yet
    assert fetch.main(["--download", "pre-holdout", "--approve-bytes", str(total)]) == 0
    cache = data_root / "raw" / f"Owner__Data-v1@{SHA}" / "daily_aligned"
    assert sorted(p.name for p in cache.iterdir()) == [
        "2024-12-30.parquet",
        "2025-02-01.parquet",
        "2025-09.parquet",
    ]
    assert fetch.main(["--verify", "--part", "pre-holdout"]) == 0
    assert fetch.main(["--verify", "--part", "ctf"]) == 1  # ctf part not downloaded


def test_write_manifest_refuses_silent_repin_and_keeps_local_hashes(env, capsys):
    hub, fetch, _ = env(lfs=False)
    base = ["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"]
    fetch.main(base)
    lst = json.loads(fetch.MANIFEST_JSON.read_text())
    card = next(f for f in lst["files"] if f["path"] == "README.md")
    assert card["sha256"] is None
    fetch.main(["--download", "card", "--approve-bytes", str(card["size"])])
    fetch.main(base)  # same revision: the locally computed hash is kept
    lst = json.loads(fetch.MANIFEST_JSON.read_text())
    assert next(f for f in lst["files"] if f["path"] == "README.md")["sha256"]
    lst["revision_sha"] = "d" * 40  # pretend the manifest pins another revision
    fetch.MANIFEST_JSON.write_text(json.dumps(lst))
    with pytest.raises(SystemExit, match="refusing"):
        fetch.main(base)
    assert fetch.main([*base, "--replace-manifest"]) == 0


def test_unprobeable_required_candidate_blocks_manifest_and_download(env, capsys):
    t = pa.table({"block_timestamp": pa.array([B + 5, B - 5], pa.int64()), "x": [1, 2]})
    buf = io.BytesIO()
    pq.write_table(t, buf, write_statistics=False)
    hub, fetch, _ = env(extra={"daily_aligned/2025-12-01.parquet": buf.getvalue()})
    base = ["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"]
    with pytest.raises(SystemExit, match="refusing to write the manifest"):
        fetch.main(base)
    assert not fetch.MANIFEST_JSON.exists()
    with pytest.raises(SystemExit):  # the old override no longer exists
        fetch.main([*base, "--accept-unverified"])
    assert not fetch.MANIFEST_JSON.exists()
    # A hand-made manifest with an unresolved entry cannot drive a download either.
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint])  # names only
    lst = fetch.Listing(
        REPO,
        "main",
        SHA,
        "t",
        hub.endpoint,
        True,
        [fetch.classify(fetch.FileEntry("daily_aligned/2025-12-01.parquet", 10, "a" * 40, None))],
    )
    fetch.MANIFEST_JSON.write_text(lst.to_json())
    with pytest.raises(SystemExit, match="unverified placements"):
        fetch.main(["--download", "pre-holdout", "--approve-bytes", "0"])


def test_misleading_old_name_and_mixed_case_extension(env, capsys):
    """A file named as a 2023 day holding exploration rows, and a .PARQUET file."""
    rows = [(EXPLORATION_START + 50 * DAY, "cX", "BTC hidden in an old-named file")]
    hub, fetch, _ = env(
        extra={
            "daily_aligned/2023-01-01.parquet": daily(rows),
            "daily_aligned/2025-03-03.PARQUET": daily(rows),
        }
    )
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    lst = json.loads(fetch.MANIFEST_JSON.read_text())
    by = {f["path"]: f for f in lst["files"]}
    for path in ("daily_aligned/2023-01-01.parquet", "daily_aligned/2025-03-03.PARQUET"):
        assert by[path]["need"] == "required-pre-holdout", path
        assert by[path]["date_source"] == "footer" and by[path]["placement_verified"] is True
    assert by["daily_aligned/2023-01-01.parquet"]["name_hint"] == "before-pinned-range"
    # footer-verified as older than the pinned range: authoritatively not needed
    assert by["daily_aligned/2024-12-29.parquet"]["need"] == "not-needed"
    assert by["daily_aligned/2024-12-29.parquet"]["date_source"] == "footer"
    assert lst["footers_probed"] is True


def _prepare_local(env, **kw):
    hub, fetch, schema = env(**kw)
    fetch.main(
        [
            "--list",
            "--repo",
            REPO,
            "--endpoint",
            hub.endpoint,
            "--probe-footers",
            "--write-manifest",
        ]
    )
    lst = json.loads(fetch.MANIFEST_JSON.read_text())
    for part, needs in (
        ("pre-holdout", {"required-pre-holdout", "required-both"}),
        ("ctf", {"required-ctf-resolution"}),
    ):
        total = sum(f["size"] for f in lst["files"] if f["need"] in needs)
        fetch.main(["--download", part, "--approve-bytes", str(total)])
    return hub, fetch, schema


def test_schema_remote_blocks_on_unconfirmed_token_id(env, capsys):
    hub, fetch, schema = env()
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    assert schema.main(["schema", "--source", "remote"]) == 3
    rep = json.loads(schema.REPORT_JSON.read_text())
    roles = {r["key"]: r for r in rep["daily_aligned"]["roles"]}
    assert roles["p_event"]["status"] == "FOUND"
    assert (
        roles["token_id"]["status"] == "CANDIDATES"
        and "asset_id" in roles["token_id"]["candidates"]
    )
    assert roles["scheduled_end"]["status"] == "CANDIDATES"
    # token_amount is not the spec's daily_aligned name: an undecided share column blocks,
    # even though usdc_amount and price exist (no silent fallback, §3).
    assert roles["shares"]["status"] == "CANDIDATES"
    assert [b["role"] for b in rep["blockers"]] == ["token_id", "shares", "ctf_payouts"]
    ctf = rep["ctf"]["CTF/resolutions"]
    assert ctf["is_resolution_table"] and not rep["ctf"]["CTF/splits"]["is_resolution_table"]


def test_schema_confirmations_clear_blockers(env, capsys):
    hub, fetch, schema = env()
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    assert schema.main(["schema", "--source", "remote", *CONFIRM]) == 0
    rep = json.loads(schema.REPORT_JSON.read_text())
    assert rep["confirmations"] == {
        "token_id": "asset_id",
        "ctf_payouts": "payout_numerators",
        "shares": "token_amount",
    }
    assert "None found by the schema check." in schema.REPORT_MD.read_text()
    # Owner states there is no share column: the usdc_amount / price fallback applies.
    conf = [*CONFIRM[:4], "--confirm", "shares=NONE"]
    assert schema.main(["schema", "--source", "remote", *conf]) == 0
    roles = {
        r["key"]: r for r in json.loads(schema.REPORT_JSON.read_text())["daily_aligned"]["roles"]
    }
    assert roles["shares"]["status"] == "CONFIRMED_ABSENT"


def test_shares_fallback_blocked_without_usdc_or_price(env, capsys):
    hub, fetch, schema = env(drop=("price",))
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    conf = [*CONFIRM[:4], "--confirm", "shares=NONE"]
    assert schema.main(["schema", "--source", "remote", *conf]) == 3
    assert [b["role"] for b in json.loads(schema.REPORT_JSON.read_text())["blockers"]] == ["shares"]


def test_ctf_resolution_table_designation(env, capsys):
    hub, fetch, schema = env()
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    rc = schema.main(
        ["schema", "--source", "remote", *CONFIRM, "--ctf-resolution-table", "CTF/splits"]
    )
    rep = json.loads(schema.REPORT_JSON.read_text())
    assert rc == 3 and rep["ctf_resolution_table_designated_by_owner"] == "CTF/splits"
    assert rep["ctf"]["CTF/splits"]["is_resolution_table"]
    assert not rep["ctf"]["CTF/resolutions"]["is_resolution_table"]
    with pytest.raises(SystemExit):
        schema.main(["schema", "--source", "remote", "--ctf-resolution-table", "CTF/nope"])


def test_missing_required_role_is_a_blocker(env, capsys):
    hub, fetch, schema = env(drop=("p_event",))
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    assert schema.main(["schema", "--source", "remote", *CONFIRM]) == 3
    rep = json.loads(schema.REPORT_JSON.read_text())
    b = rep["blockers"][0]
    assert b["role"] == "p_event" and "MISSING" in b["problem"]
    assert any(x.startswith("price:") for x in b["available_fields"])


def test_domain_checks_use_exploration_rows_only(env, capsys):
    _, _, schema = _prepare_local(env)
    # ADR-0022: refused until every required role is confirmed.
    schema.main(["schema", "--source", "remote", "--domain-checks"])
    dc = json.loads(schema.REPORT_JSON.read_text())["domain_checks"]
    assert "skipped" in dc
    # Local schema coverage is incomplete (holdout files not downloaded): no domain checks.
    assert schema.main(["schema", "--source", "local", "--domain-checks", *CONFIRM]) == 3
    rep = json.loads(schema.REPORT_JSON.read_text())
    assert "skipped" in rep["domain_checks"]
    assert any("incomplete schema coverage" in b["role"] for b in rep["blockers"])
    # Complete coverage (footers via remote) and cleared roles: checks run on local files.
    assert schema.main(["schema", "--source", "remote", "--domain-checks", *CONFIRM]) == 0
    dc = json.loads(schema.REPORT_JSON.read_text())["domain_checks"]
    # pre-holdout files: 1 trailing + 3 + 1 exploration + 1 embargo row; 2 holdout rows.
    # Only the 4 exploration-period rows are checked.
    assert dc["rows_checked"] == 4 and dc["rows_excluded_holdout_side"] == 2
    assert dc["rows_excluded_outside_exploration_period"] == 2
    assert dc["violations"]["D_not_plus_or_minus_one"] == 0
    assert dc["violations"]["p_event_outside_open_unit_interval"] == 0
    assert dc["violations"]["shares_non_positive"] == 0
    assert dc["consistency_mismatches"]["usdc_vs_shares_x_price_rel_gt_1e-6"] == 0
    assert dc["consistency_mismatches"]["p_event_vs_price_rule_gt_1e-9"] == 0
    # aggregates only: no ranges, no per-row or per-market values
    assert set(dc) == {
        "files_read",
        "rows_checked",
        "rows_excluded_holdout_side",
        "rows_excluded_outside_exploration_period",
        "rows_null_timestamp",
        "nulls",
        "violations",
        "codes",
        "consistency_mismatches",
        "sample_every",
        "columns",
    }


def test_vocab_never_sees_holdout_or_non_exploration_markets(env, capsys, data_root, tmp_path):
    _, _, schema = _prepare_local(env)
    schema.main(
        ["schema", "--source", "local", *CONFIRM, "--confirm", "scheduled_end=end_date_iso"]
    )
    draft = tmp_path / "draft.toml"
    draft.write_text("tag_values = [\"crypto\"]\nquestion_regex = '\\bBTC\\b'\n")
    assert schema.main(["vocab", "--source", "local", "--classifier", str(draft)]) == 0
    out_dir = data_root / "exploration" / "inspection"
    text = "".join(p.read_text() for p in out_dir.iterdir())
    assert "HOLDOUT-SECRET" not in text and "cHOLD" not in text
    assert "Embargo only" not in text and "Trailing only" not in text and "cOLD" not in text
    assert "2025-03-01" not in text  # scheduled end values are not read (not authorized)
    v = json.loads((out_dir / "s_short_vocab.json").read_text())
    assert v["n_markets"] == 3
    assert dict(v["category_counts"]) == {"Crypto": 2, "Politics": 1}
    assert dict(v["tag_counts"])["Bitcoin"] == 2
    ev = json.loads((out_dir / "s_short_draft_eval.json").read_text())
    assert ev["matched_both"] == 2 and ev["unmatched"] == 1


def test_vocab_reads_only_permitted_columns(env, capsys, monkeypatch):
    _, _, schema = _prepare_local(env)
    schema.main(
        ["schema", "--source", "local", *CONFIRM, "--confirm", "scheduled_end=end_date_iso"]
    )
    import r0.vocab as vocab

    seen: list[tuple] = []
    real = vocab.read_rows

    def spy(src, columns, **kw):
        seen.append((tuple(columns), kw["ts_column"], kw["scope"].value))
        return real(src, columns, **kw)

    monkeypatch.setattr(vocab, "read_rows", spy)
    schema.main(["vocab", "--source", "local"])
    allowed = {"condition_id", "category", "tags", "question", "slug"}
    assert seen and all(
        set(c) <= allowed and ts == "block_timestamp" and sc == "pre_holdout" for c, ts, sc in seen
    )


# --- Codex finding 1: integrity before any local consumption -----------------

TARGET = "daily_aligned/2025-02-01.parquet"


def _cache(data_root):
    return data_root / "raw" / f"Owner__Data-v1@{SHA}"


def _prepare_all_local(env, **kw):
    hub, fetch, schema = env(**kw)
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    files = fetch.Listing.from_json(fetch.MANIFEST_JSON.read_text()).files
    for part in ("pre-holdout", "holdout", "ctf"):
        total = sum(f.size for f in fetch.part_files(files, part))
        assert fetch.main(["--download", part, "--approve-bytes", str(total)]) == 0
    return hub, fetch, schema


def _set_manifest(fetch, path, **changes):
    lst = json.loads(fetch.MANIFEST_JSON.read_text())
    for f in lst["files"]:
        if f["path"] == path:
            f.update(changes)
    fetch.MANIFEST_JSON.write_text(json.dumps(lst))


def _tamper(file, how):
    import os

    file.chmod(0o644)
    data = bytearray(file.read_bytes())
    if how == "size":
        data += b"x"
    else:  # same size, different content
        data[len(data) // 2] ^= 0xFF
    file.write_bytes(bytes(data))
    os.chmod(file, 0o444)


@pytest.mark.parametrize("case", ["wrong-size", "wrong-sha256", "wrong-git-sha1", "no-metadata"])
def test_integrity_failures_prevent_schema_vocab_and_domain_output(env, capsys, data_root, case):
    _, fetch, schema = _prepare_all_local(env, lfs=(case != "wrong-git-sha1"))
    assert schema.main(["schema", "--source", "local", *CONFIRM]) == 0  # clean baseline
    f = _cache(data_root) / TARGET
    if case == "wrong-size":
        _tamper(f, "size")
    elif case == "wrong-sha256":
        _tamper(f, "same-size")
    elif case == "wrong-git-sha1":
        _set_manifest(fetch, TARGET, sha256=None)  # non-LFS: only the git oid remains
        assert fetch.main(["--verify"]) == 0  # git-oid path accepts the good file
        _tamper(f, "same-size")
    else:
        _set_manifest(fetch, TARGET, sha256=None, git_oid="")
    assert fetch.main(["--verify"]) == 1  # the one shared check, via --verify
    out_dir = data_root / "exploration" / "inspection"
    # vocab (needs the earlier schema report for its column mapping)
    assert schema.main(["vocab", "--source", "local"]) == 4
    assert not out_dir.exists()
    for args in (["--source", "local"], ["--source", "remote", "--domain-checks"]):
        schema.REPORT_JSON.unlink()
        schema.REPORT_MD.unlink(missing_ok=True)
        assert schema.main(["schema", *args, *CONFIRM]) == 4, args
        assert not schema.REPORT_JSON.exists() and not schema.REPORT_MD.exists()
        schema.REPORT_JSON.write_text("{}")  # placeholder so unlink works next round
    assert "INTEGRITY FAILURE" in capsys.readouterr().err


# --- Codex finding 5: complete schema coverage --------------------------------


def _blocker_roles(schema):
    return [b["role"] for b in json.loads(schema.REPORT_JSON.read_text())["blockers"]]


def test_full_local_coverage_clears_and_a_missing_daily_file_blocks(env, capsys, data_root):
    _, _, schema = _prepare_all_local(env)
    assert schema.main(["schema", "--source", "local", "--domain-checks", *CONFIRM]) == 0
    (_cache(data_root) / "daily_aligned/2025-11-01.parquet").unlink()
    assert schema.main(["schema", "--source", "local", "--domain-checks", *CONFIRM]) == 3
    rep = json.loads(schema.REPORT_JSON.read_text())
    assert any("daily_aligned: incomplete schema coverage" == r for r in _blocker_roles(schema))
    assert "skipped" in rep["domain_checks"]


def test_missing_required_ctf_file_blocks(env, capsys, data_root):
    _, _, schema = _prepare_all_local(env)
    (_cache(data_root) / "CTF/resolutions/2025.parquet").unlink()
    assert schema.main(["schema", "--source", "local", *CONFIRM]) == 3
    assert "CTF/resolutions: incomplete schema coverage" in _blocker_roles(schema)


def test_drift_in_final_daily_file_blocks(env, capsys):
    last = daily([(B + 30 * DAY, "cH", "q")], extra_cols={"new_col": [1]})
    hub, fetch, schema = env(extra={"daily_aligned/2025-11-01.parquet": last})
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    assert schema.main(["schema", "--source", "remote", *CONFIRM]) == 3
    assert "daily_aligned: schema drift" in _blocker_roles(schema)


def test_ctf_resolution_drift_after_file_50_blocks(env, capsys):
    extra = {f"CTF/resolutions/part-{i:03d}.parquet": ctf_res() for i in range(55)}
    t = pa.table(
        {
            "condition_id": ["c9"],
            "block_timestamp": pa.array([B + 9], pa.int64()),
            "payout_numerators": [[1, 0]],
            "outcome_slot_count": pa.array([2], pa.int32()),
            "late_extra": [1],
        }
    )
    extra["CTF/resolutions/part-055.parquet"] = pq_bytes(t)  # 57th file in path order
    hub, fetch, schema = env(extra=extra)
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    assert schema.main(["schema", "--source", "remote", *CONFIRM]) == 3
    rep = json.loads(schema.REPORT_JSON.read_text())
    assert rep["ctf"]["CTF/resolutions"]["footers_read"] == 57  # no cap
    assert not rep["ctf"]["CTF/resolutions"]["sampled"]
    assert "CTF/resolutions: schema drift" in _blocker_roles(schema)


# --- Codex finding 6: duplicate field names -----------------------------------


@pytest.mark.parametrize(
    "dup,extra_confirm",
    [
        (("p_event", pa.float64()), []),
        (("p_event", pa.string()), []),
        (("asset_id", pa.string()), []),  # token_id=asset_id is confirmed in CONFIRM
    ],
    ids=["same-type", "different-type", "confirmed-candidate"],
)
def test_duplicate_fields_block_before_role_mapping(env, capsys, dup, extra_confirm):
    bad = daily([(EXPLORATION_START + 60 * DAY, "cD", "q")], duplicate=dup)
    hub, fetch, schema = env(extra={"daily_aligned/2025-03-02.parquet": bad})
    fetch.main(["--list", "--repo", REPO, "--endpoint", hub.endpoint, "--write-manifest"])
    assert schema.main(["schema", "--source", "remote", *CONFIRM, *extra_confirm]) == 3
    rep = json.loads(schema.REPORT_JSON.read_text())
    assert "daily_aligned: duplicate field names" in _blocker_roles(schema)
    assert rep["daily_aligned"]["roles"] == []  # role mapping not attempted
