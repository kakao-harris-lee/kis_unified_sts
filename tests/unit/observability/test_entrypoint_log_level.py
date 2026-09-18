"""Every pipeline daemon entrypoint honours ``LOG_LEVEL`` (#751).

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
