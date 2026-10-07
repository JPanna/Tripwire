"""Column roles required by the frozen preregistration (commit 287afbe).

Matching policy (no silent substitution):

- A role is FOUND only when a column carries *exactly* the name the frozen
  preregistration itself uses for it (e.g. ``p_event``, ``D``,
  ``block_timestamp``), with a compatible type. For the CTF resolution table,
  whose columns the preregistration does not name, the exact names are those
  documented by the pinned dataset card and cited in the proposed amendment A2
  (ADR-0026): FOUND then means "documented column present", never a confirmed
  semantic mapping (the outcome_seq <-> payout-slot mapping stays a K0 check).
- Any other plausible column is reported as a CANDIDATE. A candidate is used
  only after the owner confirms it (``01_schema.py --confirm role=column``),
  and the confirmation is recorded in the report.
- Otherwise the role is MISSING. ``--confirm role=NONE`` records the owner's
  statement that no column carries the role (CONFIRMED_ABSENT).
"""

from __future__ import annotations

from dataclasses import dataclass

# Requirement levels
REQUIRED = "required"  # analysis cannot run without it -> STOP if not resolved
REQUIRED_K0 = "required-k0"  # K0 (§7) cannot run without it -> STOP
SHARES = "one-of-shares"  # §3 q_r: share column, else usdc_amount / price
OPTIONAL = "optional"
METADATA = "metadata"  # §2.2: dataset metadata, else one pinned Gamma snapshot


@dataclass(frozen=True)
class Role:
    key: str
    level: str
    exact: tuple[str, ...]
    hints: str  # regex (case-insensitive) for candidate suggestions only
    types: tuple[str, ...]  # allowed type families
    spec: str


DAILY_ROLES: tuple[Role, ...] = (
    Role(
        "market_id",
        REQUIRED,
        ("condition_id",),
        r"condition|market",
        ("string", "binary"),
        "§3: one market m = one condition_id; §8.1 cluster",
    ),
    Role(
        "timestamp",
        REQUIRED,
        ("block_timestamp",),
        r"time|ts$",
        ("int", "timestamp"),
        "§3: tau_r block timestamp, integer seconds",
    ),
    Role(
        "p_event",
        REQUIRED,
        ("p_event",),
        r"p_?event|prob",
        ("float", "decimal"),
        "§3: p_r = p_event, reference-outcome price in (0,1)",
    ),
    Role(
        "direction_D",
        REQUIRED,
        ("D",),
        r"^d$|direction|side",
        ("int", "float", "decimal"),
        "§3: D_r aggressor direction in {+1,-1} on the reference axis",
    ),
    Role(
        "outcome_seq",
        REQUIRED,
        ("outcome_seq",),
        r"outcome",
        ("int",),
        "§2.1 p_event definition; §5.3 outcome_seq <-> CTF slot mapping (checked at K0)",
    ),
    Role(
        "shares",
        SHARES,
        # No exact name: the spec names token_amount only for OrderFilled/ (§2.1),
        # so a daily_aligned share column always needs owner confirmation.
        (),
        r"share|token_?amount|size|qty|quantity",
        ("int", "float", "decimal"),
        "§3: q_r from a share-quantity column if present (OrderFilled has token_amount, §2.1)",
    ),
    Role(
        "usdc_amount",
        REQUIRED_K0,
        ("usdc_amount",),
        r"usdc|collateral|notional|amount",
        ("int", "float", "decimal"),
        "§3 q_r fallback usdc_amount/price; §7 matching on (token, maker, taker, USDC amount)",
    ),
    Role(
        "price",
        SHARES,
        ("price",),
        r"price",
        ("float", "decimal"),
        "§3 q_r fallback usdc_amount/price; §2.1 p_event = price or 1 - price",
    ),
    Role(
        "token_id",
        REQUIRED_K0,
        (),
        r"token_?id|asset_?id|position_?id|^asset$|^token$",
        ("string", "int", "decimal", "binary"),
        "§7 matching on token ID; token -> (condition, slot)",
    ),
    Role("maker", REQUIRED_K0, ("maker",), r"maker", ("string", "binary"), "§7 matching on maker"),
    Role(
        "taker",
        REQUIRED_K0,
        ("taker",),
        r"taker(?!_dir)",
        ("string", "binary"),
        "§7 matching on taker",
    ),
    Role(
        "taker_direction",
        OPTIONAL,
        ("taker_direction",),
        r"direction",
        ("int", "string", "float"),
        "§2.1 D = sign(taker_direction) x (+-1 by outcome_seq); compared at K0",
    ),
    Role(
        "block_number",
        OPTIONAL,
        (),
        r"block_?num|^block$",
        ("int",),
        "§7 provider IDs may locate records (never define completeness)",
    ),
    Role("log_index", OPTIONAL, (), r"log_?index", ("int",), "§7 locate records"),
    Role(
        "row_id",
        OPTIONAL,
        (),  # the spec names `id` only for OrderFilled/ (§2.1)
        r"^id$|_id$",
        ("string",),
        "§2.1 OrderFilled.id = chainId_blockNumber_logIndex (locating only)",
    ),
    Role(
        "neg_risk",
        OPTIONAL,
        ("neg_risk",),
        r"neg_?risk",
        ("bool", "int"),
        "§2.1 daily_aligned is neg_risk = false (scope sanity check)",
    ),
    Role(
        "fee", OPTIONAL, (), r"fee", ("int", "float", "decimal"), "§7 gross-or-net quantity formula"
    ),
    Role(
        "category",
        METADATA,
        ("category",),
        r"categor",
        ("string", "list"),
        "§4.3 S_short category/tags; §8.6 category segment",
    ),
    Role("tags", METADATA, ("tags",), r"tag", ("string", "list"), "§4.3 S_short category/tags"),
    Role(
        "question",
        METADATA,
        ("question",),
        r"question|title",
        ("string",),
        "§4.3 S_short regex on question",
    ),
    Role("slug", METADATA, ("slug",), r"slug", ("string",), "§4.3 S_short regex on slug"),
    Role(
        "scheduled_end",
        METADATA,
        (),
        r"end_?date|end_?time|enddate|close_?time|expir|resolution_?(date|time)|game_start",
        ("string", "int", "timestamp", "date"),
        "§4.3 originally scheduled end time; §8.6 time-to-end segment",
    ),
)

CTF_RESOLUTION_ROLES: tuple[Role, ...] = (
    Role(
        "ctf_condition_id",
        REQUIRED,
        ("condition_id",),
        r"condition",
        ("string", "binary"),
        "§5.3 the condition's resolution event",
    ),
    # CTF/ has no timestamp column (dataset card): t_res is not read from any
    # column. Proposed A2 derives it from the block number in `id` through the
    # scoped loader (not built). There is deliberately no fallback to metadata
    # such as daily_aligned `resolved_at` or `winning_outcome_label` (§5.3).
    Role(
        "ctf_record_id",
        REQUIRED,
        ("id",),
        r"record_?id|event_?id",
        ("string",),
        "A2 (proposed): documented record id chainId_blockNumber_logIndex, the source of "
        "the block number for t_res; not a timestamp column",
    ),
    Role(
        "ctf_payouts",
        REQUIRED,
        ("payout_numerators",),
        r"payout|numerator",
        ("list", "string", "int", "decimal"),
        "§5.3 v(m) = payout numerator / sum of numerators (documented column; the "
        "outcome_seq <-> slot mapping is not confirmed here: K0)",
    ),
    Role(
        "ctf_slot_count",
        REQUIRED,
        ("outcome_slot_count",),
        r"slot",
        ("int",),
        "A2 (proposed): payout-vector length check; outcome-slot mapping support (K0)",
    ),
    Role(
        "ctf_event_type",
        OPTIONAL,
        (),
        r"event|type|kind",
        ("string",),
        "needed only if a table mixes resolutions with other events",
    ),
    Role("ctf_block_number", OPTIONAL, (), r"block_?num|^block$", ("int",), "§7 K0 locate"),
    Role("ctf_log_index", OPTIONAL, (), r"log_?index", ("int",), "§7 K0 locate"),
)


# Smallest amendment or workaround for a required role that is genuinely
# missing. These are proposals for the owner, never applied by code.
AMENDMENT_HINTS: dict[str, str] = {
    "market_id": "None within the frozen spec: markets must be identified by condition_id.",
    "timestamp": "None within the frozen spec: tau_r must be the block timestamp.",
    "p_event": "Derive p_event from price and outcome_seq (p = price if outcome_seq = 1, else "
    "1 - price), validated at K0. This changes §3's data source: amendment required.",
    "direction_D": "Derive D from taker_direction and outcome_seq per §2.1, validated at K0. "
    "Amendment required (§3 names D as the source).",
    "outcome_seq": "Use the token_id -> slot mapping derived from chain data at K0. Amendment "
    "required: chain data would become an analysis input, which §2.2 forbids.",
    "shares": "No share column and no usable usdc_amount + price: q_r cannot be built from the "
    "dataset. Amendment would need another quantity source.",
    "usdc_amount": "K0 matching on (token, maker, taker, USDC amount) is impossible; amend §7 "
    "matching keys (e.g. block-second + token + maker + taker + shares).",
    "token_id": "Amend §7 matching to (condition_id, outcome_seq) after a chain-side "
    "token -> (condition, slot) derivation.",
    "maker": "Amend §7 matching keys.",
    "taker": "Amend §7 matching keys.",
    "ctf_condition_id": "None within the frozen spec: t_res and v(m) need the condition id.",
    "ctf_record_id": "None: without the documented record id the resolution block, and so "
    "t_res under the proposed A2, cannot be determined (SPEC IMPLEMENTATION BLOCKER).",
    "ctf_slot_count": "Owner decision: payout-vector validation under A2 needs the slot count.",
    "ctf_payouts": "v(m) cannot be computed from CTF/: amendment needed (e.g. on-chain "
    "payoutNumerators, which §2.2 forbids as an analysis variable).",
}
