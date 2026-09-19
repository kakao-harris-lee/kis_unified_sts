"""Entrypoint logging setup driven by the ``LOG_LEVEL`` environment variable.

``.env.example`` ships ``LOG_LEVEL=INFO``, so operators reasonably expect that
variable to move a service's log level. An entrypoint that hardcodes
``basicConfig(level=logging.INFO)`` silently ignores it, which makes every
DEBUG record in the code it runs unreachable without editing ``main.py`` and
rebuilding the image. Configuration belongs in the environment, not in a
branch, so the level is read here and the fallback is total: an unset or
unparseable value degrades to INFO and never raises, because a typo'd
``LOG_LEVEL`` must not stop a trading daemon from starting.
"""

from __future__ import annotations

import logging
import os

LOG_LEVEL_ENV = "LOG_LEVEL"
DEFAULT_LEVEL = logging.INFO
DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

logger = logging.getLogger(__name__)


def _lookup_level(raw: str | None) -> int | None:
    """Return the level *raw* names, or ``None`` when it names none.

    Names are matched case-insensitively against the standard table
    (``DEBUG``/``INFO``/``WARNING``/``WARN``/``ERROR``/``CRITICAL``/``FATAL``/
    ``NOTSET``). Deliberately not ``getattr(logging, name)``: that resolves any
    module attribute, so ``LOG_LEVEL=basicConfig`` would hand back a function.
    """
    if raw is None:
        return None
    return logging.getLevelNamesMapping().get(raw.strip().upper())


def configure_logging(*, fmt: str = DEFAULT_FORMAT) -> int:
    """Configure root logging from ``LOG_LEVEL``, defaulting to INFO.

    The root level is set explicitly rather than left to ``basicConfig``, which
    is a no-op once the root logger already has a handler.

    Args:
        fmt: Format string for the root handler.

    Returns:
        The effective root logger level. Never raises on a bad value.
    """
    raw = os.environ.get(LOG_LEVEL_ENV)
    named = _lookup_level(raw)
    level = DEFAULT_LEVEL if named is None else named

    logging.basicConfig(level=level, format=fmt)
    logging.getLogger().setLevel(level)

    if raw is not None and named is None:
        # Warned only after logging is configured, or the complaint about the
        # bad value would itself go nowhere.
        logger.warning(
            "%s=%r is not a log level name; falling back to INFO",
            LOG_LEVEL_ENV,
            raw,
        )
    return logging.getLogger().level
