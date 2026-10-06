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

Projection (fail-closed). Every value is projected to authorized content
immediately after it is read, and only projected records are used for
counts, examples and the draft-classifier audit:

- question, slug: a string, else nothing (non-string values are rejected).
- category, tags: string tokens only.
  - a string is one token, or, if it is a JSON array/object, it is parsed and
    projected by the rules below;
  - an object (dict/struct) contributes exactly one token: the value of the
    first of ``label``, ``name``, ``slug`` that is a non-empty string. No other
    key is ever read. An object without such a key contributes nothing and is
    counted as rejected;
  - a list contributes the tokens of its string and object elements; nested
    lists, numbers and booleans are rejected;
  - anything else is rejected.
  Rejected values are only counted, never output.

Determinism: a market's distinct projected variants are kept in canonical
(sorted JSON) order, and every example shows the first variant relevant to
its section (e.g. the variant that matched the classifier), so input order
cannot change any output.
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
LABEL_KEYS = ("label", "name", "slug")  # the only keys ever read from an object

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


def _object_token(d: dict) -> list[str] | None:
    for k in LABEL_KEYS:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return [v.strip()]
    return None


def project_tokens(value: object, *, _in_list: bool = False) -> tuple[list[str], int]:
    """Authorized category/tag tokens of ``value`` and the number of rejected parts."""
    if value is None:
        return [], 0
    if isinstance(value, str):
        s = value.strip()
        if s.startswith(("[", "{")):
            try:
                parsed = json.loads(s)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, (dict, list)):
                return project_tokens(parsed, _in_list=_in_list)
        return ([s], 0) if s else ([], 0)
    if isinstance(value, dict):
        tok = _object_token(value)
        return (tok, 0) if tok else ([], 1)
    if isinstance(value, (list, tuple)) and not _in_list:
        out: list[str] = []
        rejected = 0
        for v in value:
            t, r = project_tokens(v, _in_list=True)
            out += t
            rejected += r
        return out, rejected
    return [], 1


def tokens(value: object) -> list[str]:
    return project_tokens(value)[0]


def _text(value: object) -> tuple[str | None, int]:
    if value is None:
        return None, 0
    return (value, 0) if isinstance(value, str) else (None, 1)


def project(row: dict, cols: dict[str, str]) -> tuple[dict, int]:
    """One raw metadata row -> an authorized record (and its rejected-part count)."""
    rec: dict = {"market_id": str(row[cols["market_id"]])}
    rejected = 0
    for role in ("question", "slug"):
        if role in cols:
            rec[role], r = _text(row.get(cols[role]))
            rejected += r
    for role in ("category", "tags"):
        if role in cols:
            toks, r = project_tokens(row.get(cols[role]))
            rec[role] = sorted(set(toks))
            rejected += r
    return rec, rejected


def _coarse_dtype(dt: pl.DataType) -> str:
    """Type name without nested field names (the full schema is in SCHEMA_REPORT)."""
    if isinstance(dt, pl.Struct):
        return "Struct"
    if isinstance(dt, (pl.List, pl.Array)):
        return f"List({_coarse_dtype(dt.inner)})"
    return str(dt)


def _canon(rec: dict) -> str:
    return json.dumps(rec, sort_keys=True, ensure_ascii=False)


@dataclass
class Collected:
    by_market: dict[str, list[dict]]  # market -> distinct projected variants, canonical order
    column_types: dict[str, str]
    rejected_parts: int
    stats: dict[str, int]


def collect(sources: Iterable[Source], cols: dict[str, str]) -> Collected:
    """Distinct projected metadata variants of exploration-period markets."""
    market, ts = cols["market_id"], cols["timestamp"]
    meta = [cols[r] for r in META_ROLES if r in cols]
    seen: dict[str, dict[str, dict]] = {}
    stats: Counter = Counter()
    rejected = 0
    types: dict[str, str] = {}
    for src in sources:
        df, st = read_rows(src, [market, *meta], ts_column=ts, scope=Scope.PRE_HOLDOUT)
        stats["files"] += 1
        stats["rows_returned_by_reader"] += st.rows_kept
        df = df.filter(pl.col(ts).is_between(EXPLORATION_START, EXPLORATION_END))
        stats["rows_in_exploration_period"] += df.height
        for r in ("market_id", *META_ROLES):
            if r in cols:
                types.setdefault(r, _coarse_dtype(df.schema[cols[r]]))
        for row in df.select([market, *meta]).unique().to_dicts():
            rec, rej = project(row, cols)
            rejected += rej
            seen.setdefault(rec["market_id"], {})[_canon(rec)] = rec
    by_market = {m: [v[k] for k in sorted(v)] for m, v in seen.items()}
    return Collected(by_market, types, rejected, dict(stats))


@dataclass
class Vocab:
    n_markets: int
    markets_with_varying_metadata: int
    null_markets: dict[str, int]
    rejected_metadata_parts: int
    category_counts: list[tuple[str, int]]
    tag_counts: list[tuple[str, int]]
    examples_random: list[dict]
    examples_by_category: dict[str, list[dict]]
    design_screen_hits: int
    design_screen_examples: list[dict]
    column_types: dict[str, str]
    reader_stats: dict[str, int] = field(default_factory=dict)


def _sorted_counts(c: Counter) -> list[tuple[str, int]]:
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))


def _screen_text(rec: dict) -> str:
    return " ".join(rec.get(k) or "" for k in ("question", "slug"))


def build_vocab(col: Collected, cols: dict[str, str], n_examples: int = 200) -> Vocab:
    by_market = col.by_market
    order = sorted(by_market, key=market_order_key)
    nulls: dict[str, int] = {}
    cat_c: Counter = Counter()
    tag_c: Counter = Counter()
    for recs in by_market.values():
        for role in META_ROLES:
            if role in cols and all(not r.get(role) for r in recs):
                nulls[role] = nulls.get(role, 0) + 1
        for t in {t for r in recs for t in r.get("category", [])}:
            cat_c[t] += 1
        for t in {t for r in recs for t in r.get("tags", [])}:
            tag_c[t] += 1

    by_cat: dict[str, list[dict]] = {}
    if "category" in cols:
        for m in order:
            for t in sorted({t for r in by_market[m] for t in r.get("category", [])}) or ["<null>"]:
                lst = by_cat.setdefault(t, [])
                if len(lst) < 5:
                    rec = next(
                        (r for r in by_market[m] if t in r.get("category", [])), by_market[m][0]
                    )
                    lst.append(rec)
    hits = []
    for m in order:
        rec = next((r for r in by_market[m] if DESIGN_SCREEN.search(_screen_text(r))), None)
        if rec is not None:
            hits.append(rec)
    return Vocab(
        n_markets=len(by_market),
        markets_with_varying_metadata=sum(1 for rs in by_market.values() if len(rs) > 1),
        null_markets=nulls,
        rejected_metadata_parts=col.rejected_parts,
        category_counts=_sorted_counts(cat_c),
        tag_counts=_sorted_counts(tag_c),
        examples_random=[by_market[m][0] for m in order[:n_examples]],
        examples_by_category=dict(sorted(by_cat.items())),
        design_screen_hits=len(hits),
        design_screen_examples=hits[:150],
        column_types=col.column_types,
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

    def record_match(self, rec: dict) -> tuple[bool, bool]:
        """(tag/category match, regex match) for one projected record."""
        tag_hit = any(
            t.casefold() in self.tag_values for k in ("category", "tags") for t in rec.get(k, [])
        )
        q, s = rec.get("question"), rec.get("slug")
        rx_hit = bool(
            (self.question_regex and q and self.question_regex.search(q))
            or (self.slug_regex and s and self.slug_regex.search(s))
        )
        return tag_hit, rx_hit


def evaluate_draft(col: Collected, clf: DraftClassifier, k: int = 50) -> dict:
    by_market = col.by_market
    tag_only, rx_only, both, unmatched = [], [], [], []
    shown: dict[str, dict] = {}  # the variant each audit example shows
    for m, recs in by_market.items():
        res = [clf.record_match(r) for r in recs]
        t = any(a for a, _ in res)
        x = any(b for _, b in res)
        if t or x:
            (both if t and x else tag_only if t else rx_only).append(m)
            shown[m] = next(r for r, (a, b) in zip(recs, res, strict=True) if a or b)
        else:
            unmatched.append(m)
            screen = next((r for r in recs if DESIGN_SCREEN.search(_screen_text(r))), None)
            shown[m] = screen or recs[0]
    matched = sorted(tag_only + rx_only + both, key=lambda m: market_order_key(m, "audit-match"))
    near = sorted(
        (m for m in unmatched if any(DESIGN_SCREEN.search(_screen_text(r)) for r in by_market[m])),
        key=lambda m: market_order_key(m, "audit-near"),
    )
    rand = sorted(unmatched, key=lambda m: market_order_key(m, "audit-random"))

    def ex(ms: list[str]) -> list[dict]:
        return [shown[m] for m in ms[:k]]

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
