"""Operator-configured ``EngineConfiguration`` bounds (pre-merge fix F5,
2026-09-08).

CLAUDE.md non-negotiable: "thresholds, symbols, risk values, ports, Redis
DBs, schedules, and feature gates belong in YAML/env/config files, not
hardcoded branches." ``tos_runtime.compose._wiring._finalize`` previously
constructed the kernel's :class:`~tos.engine.records.EngineConfiguration`
with ``dsl_evaluation_budget_steps=64``/``max_unresolved_send_per_scope=1``
as bare Python literals — the kernel's own ``EngineConfiguration`` docstring
table names ``dsl_evaluation_budget_steps`` as "key absent from
VERIFICATION-PROFILE-002 — provisional", which makes a code literal the
weaker home (a config file is at least visible, editable, and inspectable
at deploy time without a code change).

This module loads both bounds from ``tos/runtime/config/engine.example.yaml``
-shaped config, fail-closed (a missing file, missing key, or ``null`` value
refuses composition at startup) — the same discipline every other
``tos_runtime.*.config``/``tos_runtime.compose._*`` loader in this codebase
applies. Never a fallback default.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = ["EngineConfig", "EngineConfigError", "load_engine_config"]

_FIELDS: tuple[str, ...] = (
    "dsl_evaluation_budget_steps",
    "max_unresolved_send_per_scope",
)


class EngineConfigError(Exception):
    """Raised when the engine config is missing, malformed, or carries an
    unfilled (named-TBD) field — fail-closed at load, never a silent
    default."""


@dataclass(frozen=True)
class EngineConfig:
    """The two operator-configured ``EngineConfiguration`` bounds (module
    docstring)."""

    dsl_evaluation_budget_steps: int
    max_unresolved_send_per_scope: int


def _require_int(raw: Any, field: str, path: Path) -> int:
    value = raw.get(field) if isinstance(raw, dict) else None
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineConfigError(
            f"{path}: {field!r} is missing, still null (named-TBD), or not "
            "an int — refusing to start until an operator supplies a "
            "concrete value"
        )
    return value


def load_engine_config(path: Path) -> EngineConfig:
    """Load + fail-closed-validate the engine bounds from ``path`` (shaped
    like ``tos/runtime/config/engine.example.yaml``).

    Raises:
        EngineConfigError: The file is missing/unreadable/not valid YAML/
            not a mapping, a key is absent, or its value is still ``null``
            (named-TBD).
    """
    if not path.is_file():
        raise EngineConfigError(f"engine config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EngineConfigError(
            f"engine config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise EngineConfigError(
            f"engine config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise EngineConfigError(
            f"engine config file must be a top-level mapping: {path}"
        )
    values = {field: _require_int(raw, field, path) for field in _FIELDS}
    return EngineConfig(**values)
