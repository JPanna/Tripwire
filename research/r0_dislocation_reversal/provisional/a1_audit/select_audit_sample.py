"""PROVISIONAL research artifact: deterministic A1 audit sample (not application code).

Builds the blinded A1 audit worksheet from exploration-period metadata only.

    uv run python research/r0_dislocation_reversal/provisional/a1_audit/select_audit_sample.py

Reads ONLY condition_id, category, category_refined (stratification only), market_slug
and block_timestamp (exploration filter) of the integrity-verified pre-holdout
daily_aligned files, through the guarded reader (r0.rawread, Scope.PRE_HOLDOUT), then
keeps 2025-01-01..2025-09-30 UTC rows. Evaluates nothing: no labels, no accuracy.

Outputs:
- A1_AUDIT_WORKSHEET_BLINDED.csv (this folder): review_id, category, market_slug and
  two blank label columns. No stratum, prediction or category_refined.
- data/exploration/inspection/a1_audit_key.csv (Git-ignored): the unblinded key.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # research/r0_dislocation_reversal

import polars as pl  # noqa: E402

from r0.integrity import verify_file  # noqa: E402
from r0.manifest import load_authoritative_manifest, part_files  # noqa: E402
from r0.paths import RESEARCH_DIR, exploration_dir, raw_file  # noqa: E402
from r0.periods import EXPLORATION_END, EXPLORATION_START  # noqa: E402
from r0.rawread import Scope, read_rows  # noqa: E402

SELECT_SALT = "a1-audit-v1"  # stratum sampling order (frozen for this audit round)
ORDER_SALT = "a1-audit-v1-worksheet"  # worksheet row order / review ids
SIZES = {"S1": 100, "S2": 100, "S3": 100, "S4": None, "S5": None, "S6": 150, "S7": 200}
REFINED_CHALLENGE = {"Crypto", "Price Action"}
COLS = ["condition_id", "category", "category_refined", "market_slug"]


def h(salt: str, cid: str) -> str:
    return hashlib.sha256(f"{salt}|{cid}".encode()).hexdigest()


def main() -> int:
    clf = tomllib.loads((HERE / "CANDIDATE_CLASSIFIER_DRAFT.toml").read_text())
    tokens = set(clf["category_tokens"])
    undecided = set(clf["undecided_category_labels"])
    pats = [re.compile(p, re.ASCII) for p in clf["slug_patterns"]]

    listing = load_authoritative_manifest(RESEARCH_DIR / "DATA_MANIFEST.json")
    parts = []
    for f in sorted(part_files(listing.files, "pre-holdout"), key=lambda f: f.path):
        p = raw_file(listing.repo_id, listing.revision_sha, f.path)
        verify_file(p, f.size, f.sha256, f.git_oid)
        df, _ = read_rows(p, COLS, ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)
        df = df.filter(pl.col("block_timestamp").is_between(EXPLORATION_START, EXPLORATION_END))
        parts.append(df.select(COLS).unique())
    markets = pl.concat(parts).unique().sort("condition_id")
    if markets["condition_id"].n_unique() != markets.height:
        raise SystemExit("a market has more than one metadata tuple; refusing")

    strata: dict[str, list[dict]] = {k: [] for k in SIZES}
    for r in markets.iter_rows(named=True):
        cat = (r["category"] or "").strip().casefold()
        slug = r["market_slug"] or ""
        t, s = cat in tokens, any(p.search(slug) for p in pats)
        f = r["category_refined"] in REFINED_CHALLENGE
        r = {**r, "T": t, "R": s, "F": f}
        if t and s:
            k = "S1"
        elif t:
            k = "S2"
        elif s:
            k = "S3"
        elif cat in undecided:
            k = "S4"
        elif cat == "doge":
            k = "S5"
        elif f:
            k = "S6"
        else:
            k = "S7"
        strata[k].append(r)

    chosen = []
    for k, n in SIZES.items():
        pool = sorted(strata[k], key=lambda r: h(SELECT_SALT, r["condition_id"]))
        take = pool if n is None else pool[:n]
        chosen += [{**r, "stratum": k} for r in take]
        print(f"{k}: population {len(pool):>6}  selected {len(take):>4}")

    chosen.sort(key=lambda r: h(ORDER_SALT, r["condition_id"]))
    ws = HERE / "A1_AUDIT_WORKSHEET_BLINDED.csv"
    key_dir = exploration_dir() / "inspection"
    key_dir.mkdir(parents=True, exist_ok=True)
    key = key_dir / "a1_audit_key.csv"
    with ws.open("w", newline="") as fw, key.open("w", newline="") as fk:
        w = csv.writer(fw, lineterminator="\n")
        k = csv.writer(fk, lineterminator="\n")
        w.writerow(["review_id", "category", "market_slug", "A_crypto_related", "B_crypto_price"])
        k.writerow(["review_id", "condition_id", "stratum", "T", "R", "F", "category_refined"])
        for i, r in enumerate(chosen, 1):
            rid = f"A1-{i:04d}"
            w.writerow([rid, r["category"], r["market_slug"], "", ""])
            flags = [r["T"], r["R"], r["F"], r["category_refined"]]
            k.writerow([rid, r["condition_id"], r["stratum"], *flags])
    for p in (ws, key):
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        print(f"{p.name}: {sum(1 for _ in p.open()) - 1} rows, sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
