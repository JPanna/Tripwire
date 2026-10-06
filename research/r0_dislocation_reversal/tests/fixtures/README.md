# Test fixtures

`legacy_manifest_23a8eda.json` is the exact output of the **old** manifest
writer (`scripts/00_fetch.py --list --write-manifest` at commit `23a8eda`) run
against the tests' synthetic fake Hub (`conftest.FakeHub`, files from
`test_scripts.files()` plus two extra files). Only `endpoint` was replaced by a
placeholder. It contains no real market data.

It preserves the unsafe behaviour fixed after the Codex audit:

- `daily_aligned/2023-01-01.parquet` holds exploration-period rows, but the old
  writer never probed it and serialized it as `not-needed` from its name;
- `daily_aligned/2025-10-07.PARQUET` (mixed-case extension) straddles the
  holdout boundary, but was serialized `required-pre-holdout` from its name;
- no entry has `placement_verified`, yet `footers_probed` is `true`;
- there is no `manifest_version`.

Every current manifest consumer must refuse it.
