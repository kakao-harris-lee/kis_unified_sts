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


def _resolve_level(env_names: tuple[str, ...]) -> tuple[int, list[tuple[str, str]]]:
    """Return the first level named by *env_names*, plus the values to complain about.

    Sources are consulted in order and the first one that names a level wins.
    A variable that is absent **or blank** is "not configured" and is skipped
    silently: compose renders an unset override as ``""`` (``"${VAR:-}"``), so
    warning on blank would put a spurious line in every container's startup.
    A variable that is set to a non-blank non-level is a typo worth a warning,
    and the search continues to the next source rather than jumping to INFO —
    a misspelled service override must not also swallow a good ``LOG_LEVEL``.
    """
    complaints: list[tuple[str, str]] = []
    for name in env_names:
        raw = os.environ.get(name)
        if raw is None or not raw.strip():
            continue
        named = _lookup_level(raw)
        if named is not None:
            return named, complaints
        complaints.append((name, raw))
    return DEFAULT_LEVEL, complaints


def configure_logging(
    *, fmt: str = DEFAULT_FORMAT, override_env: str | None = None
) -> int:
    """Configure root logging from ``LOG_LEVEL``, defaulting to INFO.

    The root level is set explicitly rather than left to ``basicConfig``, which
    is a no-op once the root logger already has a handler.

    Args:
        fmt: Format string for the root handler.
        override_env: Name of a service-specific level variable that takes
            precedence over ``LOG_LEVEL``. The narrower knob wins by
            convention: an operator who sets one service's level means that
            service, not the whole stack. Used by the stream exporter to keep
            its pre-existing ``STREAM_EXPORTER_LOG_LEVEL`` authoritative.

    Returns:
        The effective root logger level. Never raises on a bad value.
    """
    sources = (override_env, LOG_LEVEL_ENV) if override_env else (LOG_LEVEL_ENV,)
    level, complaints = _resolve_level(sources)

    logging.basicConfig(level=level, format=fmt)
    logging.getLogger().setLevel(level)

    for name, raw in complaints:
        # Warned only after logging is configured, or the complaint about the
        # bad value would itself go nowhere.
        logger.warning(
            "%s=%r is not a log level name; ignoring it (effective level: %s)",
            name,
            raw,
            logging.getLevelName(level),
        )
    return logging.getLogger().level
