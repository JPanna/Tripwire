"""Frozen R0 period bounds (PREREGISTRATION.md §4 and §6), as UTC epoch seconds.

All bounds are inclusive integer seconds ("Dates (UTC, inclusive)", §6).
"""

from __future__ import annotations

from datetime import UTC, date, datetime


def _epoch(y: int, mo: int, d: int, h: int = 0, mi: int = 0, s: int = 0) -> int:
    return int(datetime(y, mo, d, h, mi, s, tzinfo=UTC).timestamp())


# §4: trailing inputs may use rows from this second on.
TRAILING_START = _epoch(2024, 12, 30, 23, 59, 0)
# First UTC day of pinned data (the day containing TRAILING_START).
PINNED_FIRST_DAY = date(2024, 12, 30)
# Last UTC day of dataset coverage, 2026-04-28 [OWNER 2026-10-05]. Verified
# against the files at listing time (Stage B), not assumed by analysis code.
DATASET_LAST_DAY = date(2026, 4, 28)

EXPLORATION_START = _epoch(2025, 1, 1)
EXPLORATION_END = _epoch(2025, 9, 30, 23, 59, 59)
EMBARGO_START = _epoch(2025, 10, 1)
EMBARGO_END = _epoch(2025, 10, 7, 23, 59, 59)
HOLDOUT_START = _epoch(2025, 10, 8)
HOLDOUT_END = _epoch(2026, 4, 27, 23, 59, 59)

# Access-control boundary for rows (ADR-0021/ADR-0022). Two distinct notions:
# - PRE-HOLDOUT (low-level access control): block_timestamp < HOLDOUT_START,
#   i.e. trailing 2024-12-30 rows, the exploration period and the embargo.
# - EXPLORATION (research operations): EXPLORATION_START..EXPLORATION_END only.
#   S_short vocabulary, classifier audits, domain checks and all exploration
#   analysis use the exploration period only. Embargo rows may be used only
#   for purposes the frozen specification authorizes (e.g. trailing inputs and
#   cooldown continuity).
PARTITION_BOUNDARY = HOLDOUT_START
PARTITION_BOUNDARY_DAY = date(2025, 10, 8)


def in_exploration(ts: int) -> bool:
    return EXPLORATION_START <= ts <= EXPLORATION_END
