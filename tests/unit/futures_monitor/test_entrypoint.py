"""F-5 futures monitor entrypoint flag routing."""

from __future__ import annotations

import logging
import os

import pytest

import services.futures_monitor.main as m


@pytest.fixture
def restore_state_suffix():
    """Save/restore TRADING_STATE_KEY_SUFFIX around a test.

    ``_ensure_shadow_isolation`` writes ``os.environ`` directly (the daemon's
    own process env is the contract), and ``monkeypatch.delenv(raising=False)``
    records no undo when the variable was absent — so without this the shadow
    test leaked ``TRADING_STATE_KEY_SUFFIX=shadow`` into every later test on
    the same xdist worker (observed: 4 failures in
    tests/unit/streaming/test_trading_state_publisher.py, which then read
    suffixed keys).
    """
    before = os.environ.get("TRADING_STATE_KEY_SUFFIX")
    try:
        yield
    finally:
        if before is None:
            os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)
        else:
            os.environ["TRADING_STATE_KEY_SUFFIX"] = before


def test_resolve_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("FUTURES_MONITOR_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_streams_for_shadow():
    assert m._streams_for("shadow") == (
        "order.fill.futures.shadow",
        "signal.final.futures.shadow",
    )


def test_streams_for_live():
    assert m._streams_for("live") == ("order.fill.futures", "signal.final.futures")


def test_shadow_forces_suffix(restore_state_suffix):
    os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)
    m._ensure_shadow_isolation("shadow")

    assert os.environ.get("TRADING_STATE_KEY_SUFFIX") == "shadow"


def test_live_clears_suffix(restore_state_suffix):
    os.environ["TRADING_STATE_KEY_SUFFIX"] = "shadow"
    m._ensure_shadow_isolation("live")

    assert os.environ.get("TRADING_STATE_KEY_SUFFIX") == ""


def test_config_loads():
    from shared.config.loader import ConfigLoader

    cfg = ConfigLoader.load("futures_monitor.yaml").get("futures_monitor", {})
    assert "telegram" in cfg


@pytest.mark.parametrize(
    ("log_level", "expected"),
    [
        # The level an operator actually reaches for.
        ("DEBUG", logging.DEBUG),
        # A typo must degrade to INFO, not stop the daemon from starting.
        ("bogus", logging.INFO),
    ],
)
def test_main_configures_logging_before_it_starts_the_daemon(
    log_level, expected, monkeypatch, restore_root_log_level
):
    """``main()`` must configure logging, and must do it before dispatching.

    Calling ``_setup_logging()`` directly proves nothing about the entrypoint:
    it is a pass-through whose whole job is being called from ``main()``, and
    the level-name matrix it delegates to is already covered by
    tests/unit/observability/test_logging_setup.py. Reading the effective root
    level from inside the daemon seam pins both halves at once — delete the
    call from ``main()`` and this fails, which is the regression worth having.
    """
    monkeypatch.setenv("LOG_LEVEL", log_level)
    # A level main() has to move, so an unconfigured root cannot pass by luck.
    restore_root_log_level.setLevel(logging.WARNING)
    observed = []

    async def _fake_build_and_run():
        observed.append(logging.getLogger().level)
        return 0

    monkeypatch.setattr(m, "_build_and_run", _fake_build_and_run)

    assert m.main() == 0
    assert observed == [expected]
