"""``tos_runtime.compose._construction_config`` — the ``construction.yaml`` loader (TOS ``run``
구동 아크 plan, ``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`` §2 decision
2, §4 W1 lane A).

Loads the operator-authored per-deployment Order Construction facts
(:class:`~tos_runtime.compose._types.ConstructionConfig`) fail-closed — the SAME named-TBD
idiom every other ``tos_runtime.compose._*``/``tos_runtime.*.config`` loader in this codebase
already ships (:mod:`tos_runtime.compose._engine_config`,
:mod:`tos_runtime.compose._marketfeed_wiring`): a missing file, a non-mapping top level, a
missing/``null``/wrong-typed required leaf, an unrecognized top-level key, or the template's
own ``"TBD"`` placeholder string all refuse to load, never a silent default.

**This loader never expresses ``price``** (plan §2 decision 2, binding).
:func:`load_construction_config` always returns a :class:`~tos_runtime.compose._types
.ConstructionConfig` whose ``price`` is ``None`` — a price literal sitting in a config file is
exactly the injected literal the (a′) wave
(``docs/plans/2026-09-16-tos-aprime-envelope-order-shape-plan.md``) removed from
``ConstructionConfig`` itself. The per-tick value view
(:meth:`~tos.egressgw.construction.OrderConstructionStage._price_for`) is the real price source
once a tick source is wired, and ``price_field_key``/``shape_price_field_key`` below are what
actually correlate a construction to that view — never a second, config-authored price.

**Measured consequence, reported rather than silently accepted (plan §4 lane A end condition):**
``_price_for`` (``tos/src/tos/egressgw/construction.py:985-996``) returns the injected
``construction.price`` verbatim whenever EITHER ``price_field_key is None`` OR the current tick
carried no value view. With this loader always supplying ``price=None``, a construction attempt
against a value-free tick (or one whose ``price_field_key`` this file leaves unset) prices at
``None`` — never a stale or fabricated number, but also never a price a caller could size
against. Because ``run`` itself refuses to boot without a wired tick source (plan §2 decision
3), and this loader treats ``price_field_key`` as a required (non-``null``, non-``"TBD"``) leaf
exactly like every other field here, the only way a REAL deployment reaches the value-free
branch is a tick whose critical-input policy does not cover ``price_field_key`` for this
instrument — a governance gap this loader cannot see or refuse from inside ``construction.yaml``
alone. ``ConstructionConfig.price`` is therefore NOT dead / test-only: it remains the real
provisional stand-in :meth:`_price_for` falls back to on that path; this loader just never
supplies a non-``None`` value for it, by design.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``pyyaml`` + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from tos.venue import ActionClass

from tos_runtime.compose._types import ConstructionConfig

__all__ = [
    "CONSTRUCTION_CONFIG_NAME",
    "ConstructionConfigError",
    "load_construction_config",
]

#: The runtime INSTANCE file name (distinct from ``construction.example.yaml``).
CONSTRUCTION_CONFIG_NAME = "construction.yaml"

#: The template's reserved not-yet-filled placeholder — the SAME token every other fail-closed
#: loader in this codebase refuses (``tos_runtime.venue._policy_primitives.TBD_STR``).
#: Duplicated here, rather than importing across the ``tos_runtime.compose``/``tos_runtime.venue``
#: package boundary for one string literal, per the SAME "duplicate the literal, do not reach
#: into another module's private surface" discipline ``compose/cli.py``'s own
#: ``_LIVE_ENVIRONMENT_LABELS`` comment documents.
_TBD_STR = "TBD"

#: Every top-level key this loader recognizes — anything else refuses (an unrecognized key is
#: most often a typo'd or stale field an operator would otherwise never learn silently did
#: nothing).
_KNOWN_KEYS: frozenset[str] = frozenset(
    {
        "account",
        "instrument",
        "action_class",
        "instrument_class",
        "outbound_side",
        "price_field_key",
        "shape_price_field_key",
    }
)

#: The plain-string leaves (``action_class`` is validated separately below, against the kernel
#: enum, rather than accepted as a bare string).
_STR_FIELDS: tuple[str, ...] = (
    "account",
    "instrument",
    "instrument_class",
    "outbound_side",
    "price_field_key",
    "shape_price_field_key",
)


class ConstructionConfigError(Exception):
    """Raised when ``construction.yaml`` is missing, malformed, carries an unrecognized
    top-level key, or a required leaf is absent, ``null``, still the template placeholder
    ``"TBD"``, or the wrong type — fail-closed at load, never a silent default (module
    docstring)."""


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConstructionConfigError(f"construction config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConstructionConfigError(
            f"construction config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConstructionConfigError(
            f"construction config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise ConstructionConfigError(
            f"{path}: construction config must be a top-level mapping"
        )
    unknown = set(raw) - _KNOWN_KEYS
    if unknown:
        raise ConstructionConfigError(
            f"{path}: unrecognized key(s) {sorted(unknown)!r} — known keys are "
            f"{sorted(_KNOWN_KEYS)!r}"
        )
    return raw


def _require_str(raw: dict[str, Any], key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConstructionConfigError(
            f"{path}: {key!r} is missing, still null (named-TBD), or not a non-empty string"
        )
    if value == _TBD_STR:
        raise ConstructionConfigError(
            f"{path}: {key!r} is still the template placeholder {_TBD_STR!r} — "
            "operator-fill before this deployment can boot"
        )
    return value


def _require_action_class(raw: dict[str, Any], path: Path) -> ActionClass:
    value = raw.get("action_class")
    if not isinstance(value, str) or not value.strip():
        raise ConstructionConfigError(
            f"{path}: 'action_class' is missing, still null (named-TBD), or not a "
            "non-empty string"
        )
    if value == _TBD_STR:
        raise ConstructionConfigError(
            f"{path}: 'action_class' is still the template placeholder {_TBD_STR!r} — "
            "operator-fill before this deployment can boot"
        )
    try:
        return ActionClass(value)
    except ValueError as exc:
        valid = [member.value for member in ActionClass]
        raise ConstructionConfigError(
            f"{path}: 'action_class'={value!r} is not a valid tos.venue.ActionClass "
            f"member ({valid}): {exc}"
        ) from exc


def load_construction_config(path: Path) -> ConstructionConfig:
    """Load + fail-closed-validate ``construction.yaml`` from ``path`` (shaped like
    ``tos/runtime/config/construction.example.yaml``).

    ``price`` is never read from ``path`` and always comes back ``None`` on the returned
    :class:`~tos_runtime.compose._types.ConstructionConfig` (module docstring, plan §2 decision
    2) — a per-tick value view is the real price source once a tick source is wired (``run``
    refuses to boot without one, plan §2 decision 3), and the two ``*_field_key`` leaves are what
    correlate a construction to that view.

    Raises:
        ConstructionConfigError: The file is missing/unreadable/not valid YAML/not a mapping,
            carries an unrecognized top-level key, or a required leaf is absent, ``null``,
            still the template placeholder ``"TBD"``, or the wrong type.
    """
    raw = _load_mapping(path)
    action_class = _require_action_class(raw, path)
    str_values = {field: _require_str(raw, field, path) for field in _STR_FIELDS}
    return ConstructionConfig(
        account=str_values["account"],
        instrument=str_values["instrument"],
        price=None,
        action_class=action_class,
        instrument_class=str_values["instrument_class"],
        outbound_side=str_values["outbound_side"],
        price_field_key=str_values["price_field_key"],
        shape_price_field_key=str_values["shape_price_field_key"],
    )
