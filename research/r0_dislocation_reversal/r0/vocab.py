"""Stage C: exploration-only metadata vocabulary for designing S_short (§4.3).

Owner authorization (2026-10-06): inspect only column/schema information,
unique category/tag values, and question/slug strings of exploration-period
markets, solely to design and audit the S_short metadata classifier.

What this module reads: market id, timestamp and the metadata columns
(category, tags, question, slug), from rows that
``r0.rawread`` returns in the PRE_HOLDOUT scope, further restricted to
timestamps inside the EXPLORATION period (2025-01-01 .. 2025-09-30, §6):
no trailing 2024 rows, no embargo rows (ADR-0022).

What it never reads or computes: prices, directions, quantities, resolution
data, scheduled end times, first-print times, durations, events or outcomes.
The duration part of §4.3 is not evaluated here. Nothing here is used by
event logic.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from r0.periods import EXPLORATION_END, EXPLORATION_START
from r0.rawread import Scope, Source, read_rows

# The only metadata fields read (owner authorization, ADR-0020). The scheduled
# end time is deliberately not read here: it is not part of the authorization.
META_ROLES = ("category", "tags", "question", "slug")

# Design aid only (NOT the classifier): broad keywords used to surface
# examples of crypto-like markets, so that the classifier can be designed from
# observed vocabulary. Deliberately over-inclusive.
DESIGN_SCREEN = re.compile(
    r"crypto|bitcoin|\bbtc\b|ethereum|\beth\b|solana|\bsol\b|\bxrp\b|ripple|doge|"
    r"\bbnb\b|cardano|\bada\b|litecoin|\bltc\b|chainlink|\blink\b|avalanche|\bavax\b|"
    r"polkadot|\bmatic\b|\bpol\b|hyperliquid|\bhype\b|\bsui\b|\bton\b|shib|pepe|"
    r"up or down|updown|up-or-down|\bprice of\b|above|below|\$\d",
    re.I,
)

SAMPLE_SALT = "r0-sshort-vocab-v1"


def market_order_key(market_id: str, salt: str = SAMPLE_SALT) -> str:
    """Deterministic pseudo-random order for samples (SHA-256, no RNG state)."""
    return hashlib.sha256(f"{salt}|{market_id}".encode()).hexdigest()


def tokens(value: object) -> list[str]:
    """Normalise a category/tags value into string tokens (no splitting on commas)."""
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        if s.startswith(("[", "{")):
            try:
                return tokens(json.loads(s))
            except json.JSONDecodeError:
                pass
        return [s] if s else []
    if isinstance(value, dict):
        for k in ("label", "slug", "name"):
            if isinstance(value.get(k), str):
                return [value[k].strip()]
        return [json.dumps(value, sort_keys=True, default=str)]
    if isinstance(value, (list, tuple)):
        return [t for v in value for t in tokens(v)]
    return [str(value)]


def collect(sources: Iterable[Source], cols: dict[str, str]) -> tuple[pl.DataFrame, dict[str, int]]:
    """Distinct (market, metadata...) rows of exploration-period markets."""
    market, ts = cols["market_id"], cols["timestamp"]
    meta = [cols[r] for r in META_ROLES if r in cols]
    frames: list[pl.DataFrame] = []
    stats = Counter()
    for src in sources:
        df, st = read_rows(src, [market, *meta], ts_column=ts, scope=Scope.PRE_HOLDOUT)
        stats["files"] += 1
        stats["rows_returned_by_reader"] += st.rows_kept
        df = df.filter(pl.col(ts).is_between(EXPLORATION_START, EXPLORATION_END))
        stats["rows_in_exploration_period"] += df.height
        frames.append(df.select([market, *meta]).unique())
    if not frames:
        return pl.DataFrame(), dict(stats)
    out = pl.concat(frames, how="diagonal_relaxed").unique()
    return out, dict(stats)


@dataclass
class Vocab:
    n_markets: int
    markets_with_varying_metadata: int
    null_markets: dict[str, int]
    category_counts: list[tuple[str, int]]
    tag_counts: list[tuple[str, int]]
    examples_random: list[dict]
    examples_by_category: dict[str, list[dict]]
    design_screen_hits: int
    design_screen_examples: list[dict]
    column_types: dict[str, str]
    reader_stats: dict[str, int] = field(default_factory=dict)


def _row_example(row: dict, cols: dict[str, str]) -> dict:
    return {
        r: (str(row[cols[r]]) if row.get(cols[r]) is not None else None)
        for r in ("market_id", "question", "slug", "category", "tags")
        if r in cols
    }


def build_vocab(df: pl.DataFrame, cols: dict[str, str], n_examples: int = 200) -> Vocab:
    market = cols["market_id"]
    rows = df.to_dicts()
    by_market: dict[str, list[dict]] = {}
    for r in rows:
        by_market.setdefault(str(r[market]), []).append(r)
    order = sorted(by_market, key=market_order_key)

    nulls: dict[str, int] = {}
    cat_c: Counter = Counter()
    tag_c: Counter = Counter()
    for rs in by_market.values():
        for role in META_ROLES:
            if role in cols and all(r.get(cols[role]) is None for r in rs):
                nulls[role] = nulls.get(role, 0) + 1
        if "category" in cols:
            for t in {t for r in rs for t in tokens(r.get(cols["category"]))}:
                cat_c[t] += 1
        if "tags" in cols:
            for t in {t for r in rs for t in tokens(r.get(cols["tags"]))}:
                tag_c[t] += 1

    examples = [_row_example(by_market[m][0], cols) for m in order[:n_examples]]
    by_cat: dict[str, list[dict]] = {}
    if "category" in cols:
        for m in order:
            for t in tokens(by_market[m][0].get(cols["category"])) or ["<null>"]:
                lst = by_cat.setdefault(t, [])
                if len(lst) < 5:
                    lst.append(_row_example(by_market[m][0], cols))

    def text(r: dict) -> str:
        return " ".join(str(r.get(cols[k]) or "") for k in ("question", "slug") if k in cols)

    hits = [m for m in order if any(DESIGN_SCREEN.search(text(r)) for r in by_market[m])]
    types = {r: str(df.schema[cols[r]]) for r in ("market_id", *META_ROLES) if r in cols}
    return Vocab(
        n_markets=len(by_market),
        markets_with_varying_metadata=sum(1 for rs in by_market.values() if len(rs) > 1),
        null_markets=nulls,
        category_counts=cat_c.most_common(),
        tag_counts=tag_c.most_common(),
        examples_random=examples,
        examples_by_category=by_cat,
        design_screen_hits=len(hits),
        design_screen_examples=[_row_example(by_market[m][0], cols) for m in hits[:150]],
        column_types=types,
    )


# --- draft classifier evaluation (design/audit only; never used by events) ---


@dataclass(frozen=True)
class DraftClassifier:
    tag_values: frozenset[str]  # compared case-insensitively with category/tag tokens
    question_regex: re.Pattern | None
    slug_regex: re.Pattern | None
    source_sha256: str

    @staticmethod
    def load(path: Path) -> DraftClassifier:
        raw = path.read_bytes()
        d = tomllib.loads(raw.decode())
        q, s = d.get("question_regex"), d.get("slug_regex")
        return DraftClassifier(
            frozenset(v.casefold() for v in d.get("tag_values", [])),
            re.compile(q, re.I) if q else None,
            re.compile(s, re.I) if s else None,
            hashlib.sha256(raw).hexdigest(),
        )

    def metadata_match(self, rows: list[dict], cols: dict[str, str]) -> tuple[bool, bool]:
        """(tag/category match, regex match) for one market's metadata rows."""
        tag_hit = any(
            t.casefold() in self.tag_values
            for r in rows
            for role in ("category", "tags")
            if role in cols
            for t in tokens(r.get(cols[role]))
        )
        rx_hit = False
        for r in rows:
            q = r.get(cols["question"]) if "question" in cols else None
            s = r.get(cols["slug"]) if "slug" in cols else None
            if (self.question_regex and isinstance(q, str) and self.question_regex.search(q)) or (
                self.slug_regex and isinstance(s, str) and self.slug_regex.search(s)
            ):
                rx_hit = True
        return tag_hit, rx_hit


def evaluate_draft(
    df: pl.DataFrame, cols: dict[str, str], clf: DraftClassifier, k: int = 50
) -> dict:
    market = cols["market_id"]
    by_market: dict[str, list[dict]] = {}
    for r in df.to_dicts():
        by_market.setdefault(str(r[market]), []).append(r)
    res = {m: clf.metadata_match(rs, cols) for m, rs in by_market.items()}
    tag_only = [m for m, (t, x) in res.items() if t and not x]
    rx_only = [m for m, (t, x) in res.items() if x and not t]
    both = [m for m, (t, x) in res.items() if t and x]
    matched = sorted(tag_only + rx_only + both, key=lambda m: market_order_key(m, "audit-match"))
    unmatched = [m for m in by_market if m not in set(matched)]

    def txt(m: str) -> str:
        return " ".join(
            str(r.get(cols[c]) or "")
            for r in by_market[m]
            for c in ("question", "slug")
            if c in cols
        )

    near = sorted(
        (m for m in unmatched if DESIGN_SCREEN.search(txt(m))),
        key=lambda m: market_order_key(m, "audit-near"),
    )
    rand = sorted(unmatched, key=lambda m: market_order_key(m, "audit-random"))

    def ex(ms: list[str]) -> list[dict]:
        return [_row_example(by_market[m][0], cols) for m in ms[:k]]

    return {
        "classifier_sha256": clf.source_sha256,
        "n_markets": len(by_market),
        "matched_tag_only": len(tag_only),
        "matched_regex_only": len(rx_only),
        "matched_both": len(both),
        "unmatched": len(unmatched),
        "unmatched_design_screen_hits": len(near),
        "audit_sample_matched": ex(matched),
        "audit_sample_unmatched_screen_hits": ex(near),
        "audit_sample_unmatched_random": ex(rand),
        "note": "metadata condition only; the <= 24 h duration condition of §4.3 is not evaluated",
    }
