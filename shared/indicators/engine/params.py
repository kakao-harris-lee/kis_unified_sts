"""Shared parameter-coercion helpers for engine backends.

The fallback defaults each backend passes to these (e.g. ``period=14``) mirrored
the builder catalog (``config/strategy_builder/indicators.yaml``), which supplied
explicit params on the intended path, so these defaults were last-resort only.
That catalog and its loader went with the legacy removal L7
(docs/plans/2026-11-07-legacy-removal-plan.md §3); callers now always pass
explicit params. Kept in one module so both backends coerce identically (DRY).
"""

from __future__ import annotations

from collections.abc import Mapping


def int_param(params: Mapping[str, float], name: str, default: int) -> int:
    """Return ``params[name]`` as int, or ``default`` if absent."""
    return int(params.get(name, default))


def float_param(params: Mapping[str, float], name: str, default: float) -> float:
    """Return ``params[name]`` as float, or ``default`` if absent."""
    return float(params.get(name, default))
