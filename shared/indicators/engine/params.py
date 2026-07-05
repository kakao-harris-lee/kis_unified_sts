"""Shared parameter-coercion helpers for engine backends.

The fallback defaults each backend passes to these (e.g. ``period=14``) mirror
the builder catalog (``config/strategy_builder/indicators.yaml``); the intended
path always supplies explicit params resolved from that catalog, so these
defaults are last-resort only. Kept in one module so both backends coerce
identically (DRY).
"""

from __future__ import annotations

from collections.abc import Mapping


def int_param(params: Mapping[str, float], name: str, default: int) -> int:
    """Return ``params[name]`` as int, or ``default`` if absent."""
    return int(params.get(name, default))


def float_param(params: Mapping[str, float], name: str, default: float) -> float:
    """Return ``params[name]`` as float, or ``default`` if absent."""
    return float(params.get(name, default))
