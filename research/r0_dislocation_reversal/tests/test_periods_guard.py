from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from r0 import paths, periods
from r0.paths import (
    HoldoutAccessError,
    HoldoutAuthorization,
    RawCacheAccessError,
    authorize_holdout,
    check_readable,
)


def ts(*a) -> int:
    return int(datetime(*a, tzinfo=UTC).timestamp())


def test_period_constants_match_preregistration():
    assert periods.TRAILING_START == ts(2024, 12, 30, 23, 59, 0)
    assert periods.EXPLORATION_START == ts(2025, 1, 1)
    assert periods.EXPLORATION_END == ts(2025, 9, 30, 23, 59, 59)
    assert periods.EMBARGO_START == periods.EXPLORATION_END + 1
    assert periods.HOLDOUT_START == periods.EMBARGO_END + 1 == ts(2025, 10, 8)
    assert periods.HOLDOUT_END == ts(2026, 4, 27, 23, 59, 59)
    assert (periods.HOLDOUT_END + 1 - periods.HOLDOUT_START) == 202 * 86400
    assert periods.PARTITION_BOUNDARY == periods.HOLDOUT_START


@pytest.mark.parametrize("flag", [False, None, 1, "yes", "True"])
def test_authorize_holdout_needs_literal_true(flag):
    with pytest.raises(HoldoutAccessError):
        authorize_holdout(flag, "test")


def test_authorization_cannot_be_constructed_directly():
    with pytest.raises(HoldoutAccessError):
        HoldoutAuthorization("x")
    assert isinstance(authorize_holdout(True, "t"), HoldoutAuthorization)


def test_holdout_dir_requires_authorization(data_root):
    with pytest.raises(HoldoutAccessError):
        paths.holdout_dir(None)  # type: ignore[arg-type]
    assert paths.holdout_dir(authorize_holdout(True, "t")) == data_root / "holdout"


def test_check_readable_refuses_holdout_and_symlinks(data_root):
    h = data_root / "holdout" / "x.parquet"
    h.parent.mkdir(parents=True)
    h.write_bytes(b"x")
    with pytest.raises(HoldoutAccessError):
        check_readable(h)
    link = data_root / "exploration" / "innocent.parquet"
    link.parent.mkdir(parents=True)
    os.symlink(h, link)
    with pytest.raises(HoldoutAccessError):
        check_readable(link)
    assert check_readable(h, authorize_holdout(True, "t")) == h.resolve()


def test_raw_cache_only_through_rawread(data_root):
    p = paths.raw_cache_dir("o/n", "a" * 40) / "daily_aligned" / "f.parquet"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    with pytest.raises(RawCacheAccessError):
        check_readable(p)
    assert check_readable(p, raw_reader=True) == p.resolve()


def test_raw_cache_dir_requires_pinned_sha(data_root):
    with pytest.raises(ValueError):
        paths.raw_cache_dir("o/n", "main")
    assert paths.raw_cache_dir("o/n", "b" * 40).parent == data_root / "raw"


def test_data_root_env(tmp_path, monkeypatch):
    monkeypatch.setenv("R0_DATA_ROOT", str(tmp_path / "elsewhere"))
    assert paths.data_root() == (tmp_path / "elsewhere").resolve()
    monkeypatch.delenv("R0_DATA_ROOT")
    assert paths.data_root() == (paths.REPO_ROOT / "data").resolve()
