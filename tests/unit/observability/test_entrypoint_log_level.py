"""Every pipeline daemon entrypoint honours ``LOG_LEVEL`` (#751, #753).

The level-name matrix itself is covered by ``test_logging_setup.py``. What is
worth pinning here is the wiring: each ``main()`` must configure logging, and
must do it *before* it dispatches, or the daemon's own startup records are
emitted against an unconfigured root. Reading the effective level from inside
the daemon seam pins both halves at once — drop the ``configure_logging()``
call from any of these entrypoints and its rows fail.

The roster is the one ``tests/unit/test_compose_runtime_env.py`` derives from
the compose ``command`` of every service carrying ``LOG_LEVEL``: that test
proves the variable reaches the container, this one proves the process reads
it. Neither is sufficient alone.
"""

from __future__ import annotations

import importlib
import logging
import os
from types import ModuleType

import pytest

_ENTRYPOINTS = (
    "services.market_ingest.main",
    "services.stock_strategy.main",
    "services.stock_risk_filter.main",
    "services.stock_order_router.main",
    "services.stock_exit.main",
    "services.stock_monitor.main",
    "services.decision_engine.main",
    "services.risk_filter.main",
    "services.order_router.main",
    "services.futures_monitor.main",
    "services.kill_switch.main",
)

_LEVELS = (
    # The level an operator actually reaches for.
    ("DEBUG", logging.DEBUG),
    # A typo must degrade to INFO, not stop a trading daemon from starting.
    ("bogus", logging.INFO),
    # Unset is the shipped state: INFO, and no crash for want of the variable.
    (None, logging.INFO),
)


@pytest.mark.parametrize("module_name", _ENTRYPOINTS)
@pytest.mark.parametrize(("log_level", "expected"), _LEVELS)
def test_main_configures_logging_before_it_starts_the_daemon(
    module_name: str,
    log_level: str | None,
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
    restore_root_log_level: logging.Logger,
) -> None:
    module: ModuleType = importlib.import_module(module_name)

    if log_level is None:
        monkeypatch.delenv("LOG_LEVEL", raising=False)
    else:
        monkeypatch.setenv("LOG_LEVEL", log_level)
    # A level main() has to move, so an unconfigured root cannot pass by luck.
    restore_root_log_level.setLevel(logging.WARNING)
    observed: list[int] = []

    async def _fake_build_and_run() -> int:
        observed.append(logging.getLogger().level)
        return 0

    monkeypatch.setattr(module, "_build_and_run", _fake_build_and_run)

    assert module.main() == 0
    assert observed == [expected], module_name


def test_stream_exporter_prefers_its_own_knob_over_log_level(
    monkeypatch: pytest.MonkeyPatch, restore_root_log_level: logging.Logger
) -> None:
    """STREAM_EXPORTER_LOG_LEVEL outranks LOG_LEVEL for the exporter (#753).

    What this pins is the precedence and the override's name — the two levels
    disagree, so the one that wins identifies which variable was consulted.
    That ``main()`` calls the setup at all is a separate claim, pinned by
    ``test_stream_exporter_main_configures_logging_before_it_starts``; the
    exporter's distinct log format is pinned by neither, because
    ``basicConfig`` is a no-op against the root handler pytest already
    installed and a format assertion here would pass on the wrong one.
    """
    from services.monitoring.stream_exporter import _setup_logging

    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("STREAM_EXPORTER_LOG_LEVEL", "DEBUG")

    assert _setup_logging() == logging.DEBUG


def test_stream_exporter_falls_back_to_log_level(
    monkeypatch: pytest.MonkeyPatch, restore_root_log_level: logging.Logger
) -> None:
    """With the override blank — how compose renders it unset — LOG_LEVEL wins."""
    from services.monitoring.stream_exporter import _setup_logging

    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("STREAM_EXPORTER_LOG_LEVEL", "")

    assert _setup_logging() == logging.DEBUG


def test_stream_exporter_non_level_attribute_does_not_crash_startup(
    monkeypatch: pytest.MonkeyPatch, restore_root_log_level: logging.Logger
) -> None:
    """The defect #753 names: ``getattr(logging, name)`` resolved any attribute.

    ``STREAM_EXPORTER_LOG_LEVEL=BASIC_FORMAT`` used to hand ``basicConfig`` a
    string and abort the container with ``ValueError: Unknown level``.
    """
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.setenv("STREAM_EXPORTER_LOG_LEVEL", "BASIC_FORMAT")

    from services.monitoring.stream_exporter import _setup_logging

    assert _setup_logging() == logging.INFO


def test_stream_exporter_main_configures_logging_before_it_starts(
    monkeypatch: pytest.MonkeyPatch, restore_root_log_level: logging.Logger
) -> None:
    """The exporter's ``main()`` must configure logging, and before it serves.

    The three tests above call ``_setup_logging()`` directly, which proves
    nothing about the entrypoint — drop the call from ``main()`` and they all
    still pass. The other eleven daemons are pinned through a stubbed
    ``_build_and_run``; the exporter has no such seam (its ``main()`` binds a
    port and loops forever), so the loop itself is stubbed and the effective
    root level read from inside it.
    """
    from services.monitoring import stream_exporter as module

    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.delenv("STREAM_EXPORTER_LOG_LEVEL", raising=False)
    # ``main()`` assigns these directly, which monkeypatch records no undo for;
    # touching them first is what makes them restorable at teardown.
    for key in ("REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_PASSWORD"):
        monkeypatch.setenv(key, os.environ.get(key, ""))
    # A level main() has to move, so an unconfigured root cannot pass by luck.
    restore_root_log_level.setLevel(logging.WARNING)
    observed: list[int] = []

    class _StubConfig:
        redis_host = "localhost"
        redis_port = 6379
        redis_db = 1
        redis_password = ""

    class _StubExporter:
        def __init__(self, config: object) -> None:
            self.config = config

        def run_forever(self) -> None:
            observed.append(logging.getLogger().level)

    monkeypatch.setattr(module, "ExporterConfig", _StubConfig)
    monkeypatch.setattr(module, "StreamExporter", _StubExporter)

    module.main()

    assert observed == [logging.DEBUG]


# The minimal image's COPY coverage is pinned by
# tests/unit/observability/test_stream_exporter_image.py, which imports the
# entrypoint against a rebuilt image tree instead of parsing its import lines.
