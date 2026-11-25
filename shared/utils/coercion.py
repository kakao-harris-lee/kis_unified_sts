"""None-returning value coercion for Redis-hash / stream field parsing.

Read-model publishers and dashboard health helpers read flattened Redis hash
values (all strings, with ``""`` as the null marker) and must distinguish
"absent/unparseable" (→ ``None``, feeding ``degraded``/``missing_components``)
from a real ``0``. These helpers return ``None`` on failure — deliberately
distinct from :mod:`shared.utils.parsing` (``parse_float``/``parse_int``), which
return ``0.0``/``0`` and would silently corrupt the degraded-tracking logic.

Stdlib-only (``math``) so the advisory-only hedge lane can import these without
pulling any order path (``shared.execution``); the import-ban guard in
``tests/unit/portfolio/test_hedge.py`` pins that.
"""

from __future__ import annotations

import math
from typing import Any

_TRUE_TOKENS = {"true", "1", "yes"}
_FALSE_TOKENS = {"false", "0", "no"}


def to_float(value: Any) -> float | None:
    """Parse a finite float, or ``None`` for absent/empty/NaN/inf/unparseable.

    Empty string (the Redis null marker) and non-finite results (NaN, ±inf)
    both coerce to ``None`` so they flow into ``missing_components`` rather than
    poisoning downstream arithmetic.
    """
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def to_int(value: Any) -> int | None:
    """Parse an int via :func:`to_float` (truncating), or ``None`` on failure."""
    num = to_float(value)
    return None if num is None else int(num)


def to_text(value: Any) -> str | None:
    """Return the stripped string, or ``None`` when absent/empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def to_bool(value: Any) -> bool | None:
    """Parse a tri-state bool: ``True``/``False`` or ``None`` when unrecognized.

    A real ``bool`` passes through unchanged; strings match the ``true/1/yes``
    and ``false/0/no`` token sets (case-insensitive). Anything else → ``None``.
    """
    if isinstance(value, bool):
        return value
    text = to_text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in _TRUE_TOKENS:
        return True
    if lowered in _FALSE_TOKENS:
        return False
    return None
