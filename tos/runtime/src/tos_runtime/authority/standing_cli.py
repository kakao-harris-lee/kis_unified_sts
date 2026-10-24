"""``tos-runtime write-standing-approval`` — writes the standing session approval artifact
(:mod:`tos_runtime.authority.standing`) for one KIS MOCK stock tree and one trading date.

Every bound except the operator's own choices (date, max quantity, which actions, uses per
action) is derived from the RENDERED tree the runtime will boot from, never typed by hand:

* MOCK class — ``broker_scopes.yaml`` active scope + its INSTANCE document through
  :func:`~tos_runtime.brokercap.derive.is_mock_order_class`; any other tree is refused and
  nothing is written;
* ``code_digest`` — ``release.yaml``'s ``expected_code_digest`` (the release the runtime must be
  admitted under);
* ``trading_approval_policy_generation`` — ``authority.yaml``;
* ``strategy_id`` — the tree's one admitted strategy (a content digest);
* ``instrument`` / entry action — ``construction.yaml`` (instrument, action class, side);
* exit side — the Order Construction Policy's ``(CLOSE, direction)`` shape; exit proposal
  direction — the strategy's own ``CLOSE`` targets.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl.serialization import parse_strategy
from tos.engine.admission import strategy_admissible
from tos.venue.vocabulary import ActionClass

from tos_runtime.authority.epoch import load_authority_config
from tos_runtime.authority.standing import (
    STANDING_APPROVAL_RELPATH,
    STANDING_APPROVAL_SCHEMA,
    StandingApprovalError,
    parse_standing_approval,
)
from tos_runtime.brokercap import (
    is_mock_order_class,
    load_active_instance_document,
    load_broker_scopes,
)
from tos_runtime.compose._construction_config import (
    CONSTRUCTION_CONFIG_NAME,
    load_construction_config,
)
from tos_runtime.compose._envelope_wiring import resolve_construction_direction
from tos_runtime.compose._wiring import (
    _AUTHORITY_CONFIG_NAME,
    _BROKER_SCOPES_CONFIG_NAME,
    _RELEASE_CONFIG_NAME,
)
from tos_runtime.release.config import load_release_config
from tos_runtime.strategy.loader import load_strategies
from tos_runtime.strategy.resolve import STRATEGIES_DIRNAME
from tos_runtime.venue import load_order_construction_policy
from tos_runtime.venue._order_construction_policy_loader import (
    ORDER_CONSTRUCTION_POLICY_CONFIG_NAME,
)

__all__ = [
    "COMMAND",
    "StandingApprovalArgs",
    "StandingApprovalRefused",
    "add_standing_approval_subparser",
    "derive_standing_document",
    "dispatch_write_standing_approval",
    "standing_approval_args",
    "write_standing_document",
]

COMMAND = "write-standing-approval"
_ACTION_CHOICES = ("entry", "exit")
_DEFAULT_POLICY_ID = "standing-session-approval"


class StandingApprovalRefused(RuntimeError):
    """The tree is not a MOCK stock tree, or a bound cannot be derived — nothing written."""


@dataclass(frozen=True)
class StandingApprovalArgs:
    config_dir: Path
    custody_root: Path
    environment_label: str
    trading_date: str
    max_quantity: int
    actions: tuple[str, ...]
    max_uses_per_action: int
    replace: bool


def _strategy(config_dir: Path) -> Any:
    loaded = load_strategies(
        config_dir / STRATEGIES_DIRNAME, parse=parse_strategy, admit=strategy_admissible
    )
    if len(loaded.strategies) != 1:
        raise StandingApprovalRefused(
            f"{config_dir}: expected exactly one admitted strategy, found "
            f"{len(loaded.strategies)} — a standing approval names one strategy"
        )
    return loaded.strategies[0].strategy


def _targets(node: Any) -> set[tuple[str, str]]:
    """Every ``(position_effect, direction)`` pair a strategy's targets declare."""
    found: set[tuple[str, str]] = set()
    if isinstance(node, dict):
        effect, direction = node.get("position_effect"), node.get("direction")
        if isinstance(effect, str) and isinstance(direction, str):
            found.add((effect, direction))
        for value in node.values():
            found |= _targets(value)
    elif isinstance(node, list | tuple):
        for value in node:
            found |= _targets(value)
    return found


def _actions(
    config_dir: Path, strategy: Any, wanted: tuple[str, ...], max_uses: int
) -> tuple[str, list[dict[str, Any]]]:
    """``(instrument, actions)`` derived from construction.yaml, the OCP and the strategy."""
    construction = load_construction_config(config_dir / CONSTRUCTION_CONFIG_NAME)
    ocp = load_order_construction_policy(
        config_dir / ORDER_CONSTRUCTION_POLICY_CONFIG_NAME,
        scheme=get_scheme(EV_L1_PROVISIONAL_VERSION),
    )
    rules = ocp.construction_rules
    targets = _targets(strategy.model_dump(mode="json"))
    actions: list[dict[str, Any]] = []
    if "entry" in wanted:
        direction = resolve_construction_direction(
            rules, action_class=construction.action_class
        )
        shape = rules.action_class_shape.get((construction.action_class, direction))
        if shape is None or shape.side != construction.outbound_side:
            raise StandingApprovalRefused(
                f"{config_dir}: construction.yaml side {construction.outbound_side!r} is not "
                f"the OCP shape for ({construction.action_class.value}, {direction})"
            )
        if (shape.position_effect, direction) not in targets:
            raise StandingApprovalRefused(
                f"{config_dir}: the strategy declares no ({shape.position_effect}, "
                f"{direction}) target"
            )
        actions.append(_action(shape.position_effect, direction, shape.side, max_uses))
    if "exit" in wanted:
        held = resolve_construction_direction(rules, action_class=ActionClass.CLOSE)
        shape = rules.action_class_shape.get((ActionClass.CLOSE, held))
        if shape is None:
            raise StandingApprovalRefused(f"{config_dir}: the OCP has no CLOSE shape")
        directions = {d for effect, d in targets if effect == shape.position_effect}
        if len(directions) != 1:
            raise StandingApprovalRefused(
                f"{config_dir}: the strategy's {shape.position_effect} targets name "
                f"{sorted(directions)} — need exactly one direction"
            )
        actions.append(
            _action(shape.position_effect, directions.pop(), shape.side, max_uses)
        )
    return construction.instrument, actions


def _action(
    position_effect: str, direction: str, side: str, max_uses: int
) -> dict[str, Any]:
    return {
        "position_effect": position_effect,
        "direction": direction,
        "side": side,
        "max_uses": max_uses,
    }


def derive_standing_document(args: StandingApprovalArgs) -> dict[str, Any]:
    """Build the artifact mapping for ``args`` (module docstring).

    Raises:
        StandingApprovalRefused: Not a MOCK tree, or a bound cannot be derived.
    """
    config_dir = args.config_dir
    scopes = load_broker_scopes(
        config_dir / _BROKER_SCOPES_CONFIG_NAME,
        environment_label=args.environment_label,
    )
    instance = load_active_instance_document(scopes)
    if not is_mock_order_class(scopes.active_scope, instance):
        raise StandingApprovalRefused(
            f"{config_dir}: the active broker scope is not the KIS MOCK order class bound to a "
            "BROKER_SIMULATION profile — a standing approval is MOCK-only; nothing written"
        )
    if not args.actions or set(args.actions) - set(_ACTION_CHOICES):
        raise StandingApprovalRefused(f"actions must be a subset of {_ACTION_CHOICES}")
    strategy = _strategy(config_dir)
    instrument, actions = _actions(
        config_dir, strategy, args.actions, args.max_uses_per_action
    )
    release = load_release_config(config_dir / _RELEASE_CONFIG_NAME)
    authority = load_authority_config(config_dir / _AUTHORITY_CONFIG_NAME)
    document = {
        "schema": STANDING_APPROVAL_SCHEMA,
        "environment_label": args.environment_label,
        "code_digest": release.expected_code_digest,
        "trading_date": args.trading_date,
        "strategy_id": strategy.strategy_id,
        "instrument": instrument,
        "max_quantity": args.max_quantity,
        "actions": actions,
        "trading_approval_policy_id": _DEFAULT_POLICY_ID,
        "trading_approval_policy_generation": authority.trading_approval_policy_generation,
        "trading_approval_policy_digest": None,
    }
    try:
        parse_standing_approval(document, config_dir)
    except StandingApprovalError as exc:
        raise StandingApprovalRefused(str(exc)) from exc
    return document


def write_standing_document(
    custody_root: Path, document: dict[str, Any], *, replace: bool
) -> Path:
    """Write ``document`` 0600 under the custody root; refuse to overwrite unless ``replace``."""
    path = custody_root / STANDING_APPROVAL_RELPATH
    if path.exists() and not replace:
        raise StandingApprovalRefused(
            f"{path} already exists — pass --replace to overwrite"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".yaml.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(yaml.safe_dump(document, sort_keys=False, allow_unicode=True))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return path


def _trading_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%Y%m%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--trading-date must be YYYY-MM-DD: {exc}"
        ) from exc


def _actions_arg(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def add_standing_approval_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register ``write-standing-approval``."""
    parser = subparsers.add_parser(
        COMMAND,
        help=(
            "Write the standing session approval for ONE KIS MOCK stock session "
            "(custody_root/approvals/standing-session.yaml). Refuses any non-MOCK tree."
        ),
    )
    parser.add_argument("--config-dir", required=True, type=Path)
    parser.add_argument("--custody-root", required=True, type=Path)
    parser.add_argument("--environment-label", required=True, type=str)
    parser.add_argument("--trading-date", required=True, type=_trading_date)
    parser.add_argument("--max-quantity", type=int, default=1)
    parser.add_argument("--actions", type=_actions_arg, default=("entry", "exit"))
    parser.add_argument("--max-uses-per-action", type=int, default=1)
    parser.add_argument("--replace", action="store_true")


def standing_approval_args(namespace: argparse.Namespace) -> StandingApprovalArgs:
    """The parsed namespace as :class:`StandingApprovalArgs`."""
    return StandingApprovalArgs(
        config_dir=namespace.config_dir,
        custody_root=namespace.custody_root,
        environment_label=namespace.environment_label,
        trading_date=namespace.trading_date,
        max_quantity=namespace.max_quantity,
        actions=tuple(namespace.actions),
        max_uses_per_action=namespace.max_uses_per_action,
        replace=namespace.replace,
    )


def dispatch_write_standing_approval(args: StandingApprovalArgs) -> int:
    """Derive, write, and print the artifact path + digest; ``1`` on refusal."""
    try:
        document = derive_standing_document(args)
        path = write_standing_document(
            args.custody_root, document, replace=args.replace
        )
    except StandingApprovalRefused as exc:
        print(f"{COMMAND}: refused — {exc}", file=sys.stderr)
        return 1
    approval = parse_standing_approval(document, path)
    print(
        f"{COMMAND}: wrote {path} (artifact_digest={approval.digest}, "
        f"trading_date={approval.trading_date}, actions="
        f"{','.join(a.key for a in approval.actions)})"
    )
    return 0
