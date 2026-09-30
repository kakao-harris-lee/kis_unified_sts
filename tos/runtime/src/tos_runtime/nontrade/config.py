"""``required_legs_by_class`` config loader (TOS Phase 5 W5 plan §2 decision 7,
rollover wiring; lane f4).

:mod:`tos_runtime.nontrade.processor`'s own module docstring states the M6
discipline this loader exists to satisfy: "``required_legs_by_class`` is a
constructor-injected mapping, never a module-level literal ... the event-class
-> applicable-leg mapping is caller policy". This is that caller policy's
loader — the compose wiring lane's own config, never a nontrade-package
constant.

Fail-closed, same idiom every ``tos_runtime.*.config`` loader in this codebase
follows (mirrors :mod:`tos_runtime.calendar.config`): a missing file, a
non-mapping top level, or a required key present but still ``null``
(named-TBD) all refuse to load. An event class **absent** from the mapping
entirely is a legitimate, deliberate value — it is exactly the processor's own
"we do not know what legs this class requires" case (module docstring), never
an error. Only a class that IS present with a still-``null`` value, or an
unrecognized class/leg name, refuses.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib +
``pyyaml`` + ``tos.nontrade`` (the two closed vocabularies) only. No
``shared.*``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from tos.nontrade import CredibleTransitionLegKind, NonTradeEventClass

__all__ = [
    "NONTRADE_CONFIG_NAME",
    "NonTradeConfigError",
    "load_required_legs_config",
]

#: The config file name directly under ``config_dir`` (mirrors every other
#: ``tos_runtime.*.config`` loader's own ``_*_CONFIG_NAME`` convention; shaped
#: like ``tos/runtime/config/nontrade.example.yaml``).
NONTRADE_CONFIG_NAME = "nontrade.yaml"


class NonTradeConfigError(RuntimeError):
    """Raised when ``nontrade.yaml`` is missing/malformed, a present class key
    carries a still-``null`` (named-TBD) leg list, or a class/leg name does
    not resolve to a real kernel vocabulary member — fail-closed at load,
    never a silent default or a fabricated leg set."""


def _require_mapping(raw: Any, path: Path, *, ctx: str = "nontrade config") -> dict:
    if not isinstance(raw, dict):
        raise NonTradeConfigError(f"{path}: {ctx} must be a mapping")
    return raw


def _resolve_event_class(name: str, path: Path) -> NonTradeEventClass:
    try:
        return NonTradeEventClass[name]
    except KeyError as exc:
        raise NonTradeConfigError(
            f"{path}: required_legs_by_class key {name!r} is not a real "
            f"NonTradeEventClass member (one of "
            f"{[member.name for member in NonTradeEventClass]!r})"
        ) from exc


def _resolve_leg(name: str, event_class: str, path: Path) -> CredibleTransitionLegKind:
    try:
        return CredibleTransitionLegKind[name]
    except KeyError as exc:
        raise NonTradeConfigError(
            f"{path}: required_legs_by_class[{event_class!r}] entry {name!r} "
            "is not a real CredibleTransitionLegKind member"
        ) from exc


def load_required_legs_config(
    path: Path,
) -> dict[NonTradeEventClass, frozenset[CredibleTransitionLegKind]]:
    """Load + fail-closed-validate ``required_legs_by_class`` from ``path``.

    YAML shape::

        required_legs_by_class:
          CORPORATE_ACTION:
            - PRE_EVENT_POSITION_AND_ORDER
            - POST_EVENT_QUANTITY_INSTRUMENT_MULTIPLIER_CURRENCY_CASH
          LIFECYCLE: null   # still named-TBD -- refuses to load as-is

    A class key entirely ABSENT from the mapping is a legitimate "not
    configured" value (the processor's own unevaluated path) — only a
    PRESENT key whose value is still ``null``, not a list, or names an
    unrecognized member refuses.

    Raises:
        NonTradeConfigError: missing/unreadable file, non-mapping top level
            or ``required_legs_by_class`` value, a present class key with a
            still-``null``/non-list value, or an unrecognized class/leg name.
    """
    if not path.is_file():
        raise NonTradeConfigError(f"nontrade config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise NonTradeConfigError(
            f"nontrade config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise NonTradeConfigError(
            f"nontrade config file is not valid YAML: {path}"
        ) from exc
    raw = _require_mapping(raw, path)

    if "required_legs_by_class" not in raw:
        raise NonTradeConfigError(
            f"{path}: missing required key 'required_legs_by_class'"
        )
    raw_legs_by_class = _require_mapping(
        raw["required_legs_by_class"], path, ctx="'required_legs_by_class'"
    )

    result: dict[NonTradeEventClass, frozenset[CredibleTransitionLegKind]] = {}
    for class_name, raw_legs in raw_legs_by_class.items():
        event_class = _resolve_event_class(class_name, path)
        if not isinstance(raw_legs, list) or not raw_legs:
            raise NonTradeConfigError(
                f"{path}: required_legs_by_class[{class_name!r}] is still "
                "null (named-TBD) or not a non-empty explicit list -- "
                "refusing to start until an operator fills it in (an "
                "entirely ABSENT key, not this one, is how a class stays "
                "unconfigured)"
            )
        result[event_class] = frozenset(
            _resolve_leg(leg_name, class_name, path) for leg_name in raw_legs
        )
    return result
