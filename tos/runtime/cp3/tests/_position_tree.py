"""A position-enabled tenant tree, written into ``tmp_path`` for the S3 tests."""

from __future__ import annotations

import re
from pathlib import Path

INSTRUMENT = "000660"

ACCOUNT = "9999999999"

PRICE_FIELD = "close_x100"

BAR_INTERVAL_MS = 60_000

STOP_LOSS_BP = -50

TAKE_PROFIT_BP = 80

STOP_RULE_ID = "R1-STOP-LOSS"

TARGET_RULE_ID = "R2-TAKE-PROFIT"

ENTRY_RULE_ID = "R3-ENTRY"

DEFAULT_RULE_ID = "R0-DEFAULT-NO-ACTION"

STRATEGY_FILE_NAME = "position_setup_d.strategy.yaml"

OCP_FILE_NAME = "order_construction_policy.yaml"

#: The admitted field a ``sizing: "field"`` tree reads its risk unit from (P4 S5).
RISK_UNIT_FIELD = "risk_unit_x100"

#: That tree's authored risk budget, in the same integer scale as the field.
RISK_BUDGET = 1000

#: The shipped stock OCP is the only loadable one in the repo, so the fixtures
#: re-author ITS sizing block rather than hand-rolling a second OCP document.
_SHIPPED_OCP = (
    Path(__file__).resolve().parents[4]
    / "config"
    / "tos_runtime"
    / "cp3-setup-d-stock-000660"
    / OCP_FILE_NAME
)

#: The two deployment coordinates the committed tree leaves operator-fill. The
#: loader refuses ``"TBD"``, so an unfilled copy would load as "no policy" and
#: the fixtures would silently fall back to the replay default unit.
_OCP_COORDINATES: tuple[tuple[str, str], ...] = (
    (r'^(\s*accounts:) \["TBD"\]$', rf'\g<1> ["{ACCOUNT}"]'),
    (r'^(\s*instruments:) \["TBD"\]$', rf'\g<1> ["{INSTRUMENT}"]'),
)

_MARKETFEED = """position_context:
  enabled: {enabled}
  bar_interval_ms: {interval}
"""

_CONSTRUCTION = """account: "{account}"
instrument: "{instrument}"
action_class: "{action_class}"
instrument_class: "krx-stock"
outbound_side: "{side}"
price_field_key: "{price_field}"
shape_price_field_key: "{price_field}"
"""

_BINDINGS = """strategies:
  position_setup_d.strategy:
    config_binding_version: cp3-s3-bind-1
    bindings:
      stop_loss_bp: {stop}
      take_profit_bp: {target}
"""

_BINDINGS_EMPTY = "strategies: {}\n"

_HEAD = """dsl_version: cp3-s3-dsl-1
config_binding_version: cp3-s3-bind-1

policy:
  rules:
"""

_EXIT_RULE = """    - all_of:
        - left:
            ref: [capsule, position, side]
          op: NE
          right:
            const: "FLAT"
        - left:
            ref: [capsule, position, unrealized_bp]
          op: {op}
          right:
            ref: [config, {binding}]
      decision:
        kind: FLAT
        rationale: >-
          {rule_id}: the declared bound is reached — go flat.
        target:
          kind: FLAT
          account: {account_ref}
          instrument: {instrument_ref}
          direction: {close_direction}
          position_effect: CLOSE
          rationale: >-
            {rule_id}: close the position at its declared bound.
"""

_ENTRY_RULE = """    - all_of:
{flat_guard}        - left:
            ref: [capsule, resolved_values, entry_window]
          op: EQ
          right:
            const: true
      decision:
        kind: ACTION
        rationale: >-
          {rule_id}: the entry window is open — propose one new position.
        target:
          kind: ACTION
          account: {account_ref}
          instrument: {instrument_ref}
          direction: {direction}
          position_effect: OPEN
          quantity_basis: RISK
          rationale: >-
            {rule_id}: open one new position in the declared direction.
"""

_FLAT_GUARD = """        - left:
            ref: [capsule, position, side]
          op: EQ
          right:
            const: "FLAT"
"""

_TAIL = """  default:
    kind: NO_ACTION
    rationale: >-
      R0-DEFAULT-NO-ACTION: no rule fired — hold exposure unchanged.
"""


def _substituted(text: str, pattern: str, replacement: str) -> str:
    """``text`` with the ONE line ``pattern`` matches replaced, or a named failure."""
    out, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    assert count == 1, f"{_SHIPPED_OCP}: {pattern!r} matched {count} lines, expected 1"
    return out


def ocp_yaml(*, sizing: str, risk_budget: int = RISK_BUDGET) -> str:
    """The shipped stock OCP with its coordinates filled and its sizing re-authored."""
    text = _SHIPPED_OCP.read_text(encoding="utf-8")
    for pattern, replacement in _OCP_COORDINATES:
        text = _substituted(text, pattern, replacement)
    if sizing == "fixed":
        return text
    assert sizing == "field", f"unknown sizing mode {sizing!r}"
    text = _substituted(
        text,
        r"^(\s*)per_unit_risk: 1$",
        rf'\g<1>per_unit_risk_field_key: "{RISK_UNIT_FIELD}"',
    )
    return _substituted(
        text, r"^(\s*)risk_budget: 1$", rf"\g<1>risk_budget: {risk_budget}"
    )


def strategy_yaml(
    *, direction: str = "LONG", flat_guard: bool = True, position_refs: bool = True
) -> str:
    """The S3 scenario's authored policy: stop, target, then a guarded entry."""
    close_direction = "SHORT" if direction == "LONG" else "LONG"
    first = f'&account "{ACCOUNT}"'
    first_instrument = f'&instrument "{INSTRUMENT}"'
    rules = _EXIT_RULE.format(
        op="LE",
        binding="stop_loss_bp",
        rule_id=STOP_RULE_ID,
        account_ref=first,
        instrument_ref=first_instrument,
        close_direction=close_direction,
    )
    rules += _EXIT_RULE.format(
        op="GE",
        binding="take_profit_bp",
        rule_id=TARGET_RULE_ID,
        account_ref="*account",
        instrument_ref="*instrument",
        close_direction=close_direction,
    )
    rules += _ENTRY_RULE.format(
        flat_guard=_FLAT_GUARD if flat_guard else "",
        rule_id=ENTRY_RULE_ID,
        account_ref="*account",
        instrument_ref="*instrument",
        direction=direction,
    )
    if not position_refs:
        rules = _ENTRY_RULE.format(
            flat_guard="",
            rule_id=ENTRY_RULE_ID,
            account_ref=first,
            instrument_ref=first_instrument,
            direction=direction,
        )
    return _HEAD + rules + _TAIL


def write_tree(
    root: Path,
    *,
    direction: str = "LONG",
    enabled: bool = True,
    flat_guard: bool = True,
    position_refs: bool = True,
    marketfeed: bool = True,
    sizing: str | None = None,
    risk_budget: int = RISK_BUDGET,
) -> Path:
    """Write the config dir an inspection reads, and return it."""
    config_dir = root / "render"
    (config_dir / "strategies").mkdir(parents=True, exist_ok=True)
    (config_dir / "strategies" / STRATEGY_FILE_NAME).write_text(
        strategy_yaml(
            direction=direction, flat_guard=flat_guard, position_refs=position_refs
        ),
        encoding="utf-8",
    )
    (config_dir / "strategy_bindings.yaml").write_text(
        (
            _BINDINGS.format(stop=STOP_LOSS_BP, target=TAKE_PROFIT_BP)
            if position_refs
            else _BINDINGS_EMPTY
        ),
        encoding="utf-8",
    )
    if marketfeed:
        (config_dir / "marketfeed.yaml").write_text(
            _MARKETFEED.format(
                enabled="true" if enabled else "false", interval=BAR_INTERVAL_MS
            ),
            encoding="utf-8",
        )
    (config_dir / "construction.yaml").write_text(
        _CONSTRUCTION.format(
            account=ACCOUNT,
            instrument=INSTRUMENT,
            action_class="NEW_LONG" if direction == "LONG" else "NEW_SHORT",
            side="BUY" if direction == "LONG" else "SELL",
            price_field=PRICE_FIELD,
        ),
        encoding="utf-8",
    )
    if sizing is not None:
        (config_dir / OCP_FILE_NAME).write_text(
            ocp_yaml(sizing=sizing, risk_budget=risk_budget), encoding="utf-8"
        )
    return config_dir
