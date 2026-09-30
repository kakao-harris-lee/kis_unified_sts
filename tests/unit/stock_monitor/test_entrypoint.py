"""M5a flag routing: off -> inert; stream mapping; shadow forces key-suffix; config loads."""

from __future__ import annotations

import asyncio
import logging
import os

import pytest

import services.stock_monitor.main as m


def test_resolve_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_MONITOR_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_streams_for_shadow_and_live() -> None:
    assert m._streams_for("shadow") == (
        "order.fill.stock.shadow",
        "signal.final.stock.shadow",
    )
    assert m._streams_for("live") == ("order.fill.stock", "signal.final.stock")


def test_off_mode_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_MONITOR_DAEMON", "off")
    assert asyncio.run(m._build_and_run()) == 0


def test_shadow_forces_key_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    # setenv (not delenv) so monkeypatch TRACKS the key and removes it on
    # teardown — _ensure_shadow_isolation writes os.environ directly, which a
    # delenv-on-absent would NOT undo, leaking the suffix into later tests.
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")
    m._ensure_shadow_isolation("shadow")
    assert os.environ["TRADING_STATE_KEY_SUFFIX"] == "shadow"


def test_live_leaves_empty_suffix_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tracked via setenv so teardown restores cleanly (see note above).
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")
    m._ensure_shadow_isolation("live")
    assert os.environ.get("TRADING_STATE_KEY_SUFFIX", "") == ""


def test_live_clears_shadow_suffix_from_base_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "shadow")
    m._ensure_shadow_isolation("live")
    assert os.environ.get("TRADING_STATE_KEY_SUFFIX", "") == ""


def test_config_loads() -> None:
    from shared.config.loader import ConfigLoader

    tg = (
        ConfigLoader.load("stock_monitor.yaml")
        .get("stock_monitor", {})
        .get("telegram", {})
    )
    assert tg.get("pnl_alert_pct") == 3.0


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
    log_level: str,
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
    restore_root_log_level: logging.Logger,
) -> None:
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
    observed: list[int] = []

    async def _fake_build_and_run() -> int:
        observed.append(logging.getLogger().level)
        return 0

    monkeypatch.setattr(m, "_build_and_run", _fake_build_and_run)

    assert m.main() == 0
    assert observed == [expected]
