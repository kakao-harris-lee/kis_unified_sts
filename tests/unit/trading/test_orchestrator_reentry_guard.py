"""Post-exit re-entry guard tests for stock paper trading."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from services.trading.orchestrator import (
    EntryReentryGuardConfig,
    TradingConfig,
    TradingOrchestrator,
)
from shared.models.signal import ExitReason, ExitSignal, Signal


def _make_orchestrator(
    *,
    guard: EntryReentryGuardConfig | None = None,
    asset_class: str = "stock",
) -> TradingOrchestrator:
    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = TradingConfig(
        asset_class=asset_class, strategy_name="momentum_breakout"
    )
    orch._entry_reentry_guard = guard or EntryReentryGuardConfig(
        enabled=True,
        scope="symbol_strategy",
        default_cooldown_seconds=900,
        reason_cooldown_seconds={"stop_loss": 3600},
    )
    orch._recent_exit_cooldowns = {}
    return orch


def test_reentry_guard_config_normalizes_reason_cooldowns() -> None:
    cfg = EntryReentryGuardConfig.from_dict(
        {
            "enabled": True,
            "scope": "symbol",
            "default_cooldown_seconds": 120,
            "reason_cooldown_seconds": {"STOP_LOSS": 600},
        }
    )

    assert cfg.enabled is True
    assert cfg.scope == "symbol"
    assert cfg.cooldown_for("stop_loss") == 600
    assert cfg.cooldown_for("momentum_decay") == 120


def test_reentry_guard_config_coerces_numeric_strings() -> None:
    """Env-interpolated YAML values (``${VAR:180}``) arrive as strings; from_dict
    must coerce them, not reject them (regression: FUTURES_REENTRY_STOP_LOSS_
    COOLDOWN_SECONDS override disabled the whole guard)."""
    cfg = EntryReentryGuardConfig.from_dict(
        {
            "default_cooldown_seconds": "600",
            "reason_cooldown_seconds": {"stop_loss": "180"},
        }
    )
    assert cfg.default_cooldown_seconds == 600.0
    assert cfg.cooldown_for("stop_loss") == 180.0


def test_records_stop_loss_exit_and_blocks_same_strategy_reentry() -> None:
    orch = _make_orchestrator()
    closed = SimpleNamespace(code="064400", strategy="momentum_breakout")
    exit_signal = ExitSignal(
        code="064400",
        strategy="momentum_breakout",
        reason=ExitReason.STOP_LOSS,
    )

    orch._record_recent_exit_for_reentry_guard(closed, exit_signal, "stop_loss")

    same_strategy = Signal(code="064400", strategy="momentum_breakout")
    block = orch._reentry_guard_block(same_strategy)
    assert block is not None
    assert block["reason"] == "stop_loss"
    assert 0 < block["remaining_seconds"] <= 3600

    other_strategy = Signal(code="064400", strategy="trend_pullback")
    assert orch._reentry_guard_block(other_strategy) is None


def test_reentry_guard_keys_on_position_strategy_not_exit_generator() -> None:
    """The cooldown must key on the ENTRY strategy, not the exit-generator name.

    A real exit signal carries the exit *generator's* name (e.g.
    ``setup_target_exit``), while the re-entry that must be blocked carries the
    ENTRY strategy name (e.g. ``setup_d_vwap_reversion``). Under ``symbol_strategy``
    scope the recorded key must match the entry key, or the guard silently never
    fires. Regression for the 2026-07-07 futures churn: the 30-min stop_loss
    cooldown did not block 1-2 min re-entries because it was keyed on
    ``setup_target_exit`` while entries checked ``setup_d_vwap_reversion``.
    """
    orch = _make_orchestrator(asset_class="futures")
    closed = SimpleNamespace(code="A01609", strategy="setup_d_vwap_reversion")
    exit_signal = ExitSignal(
        code="A01609",
        strategy="setup_target_exit",  # exit generator name — the real value
        reason=ExitReason.STOP_LOSS,
    )

    orch._record_recent_exit_for_reentry_guard(closed, exit_signal, "stop_loss")

    reentry = Signal(code="A01609", strategy="setup_d_vwap_reversion")
    block = orch._reentry_guard_block(reentry)
    assert block is not None, "re-entry within the stop_loss cooldown must be blocked"
    assert block["reason"] == "stop_loss"


def test_symbol_scope_blocks_other_strategy_reentry() -> None:
    orch = _make_orchestrator(
        guard=EntryReentryGuardConfig(
            enabled=True,
            scope="symbol",
            default_cooldown_seconds=900,
            reason_cooldown_seconds={"stop_loss": 3600},
        )
    )
    closed = SimpleNamespace(code="064400", strategy="momentum_breakout")
    exit_signal = ExitSignal(code="064400", strategy="momentum_breakout")

    orch._record_recent_exit_for_reentry_guard(closed, exit_signal, "stop_loss")

    assert (
        orch._reentry_guard_block(Signal(code="064400", strategy="trend_pullback"))
        is not None
    )


def test_expired_reentry_guard_allows_signal_and_prunes_record() -> None:
    orch = _make_orchestrator()
    key = orch._entry_reentry_guard_key("064400", "momentum_breakout")
    orch._recent_exit_cooldowns[key] = {
        "code": "064400",
        "strategy": "momentum_breakout",
        "reason": "stop_loss",
        "exit_time": datetime.now(UTC) - timedelta(seconds=3700),
        "cooldown_seconds": 3600.0,
    }

    signal = Signal(code="064400", strategy="momentum_breakout")
    assert orch._reentry_guard_block(signal) is None
    assert key not in orch._recent_exit_cooldowns


def test_reentry_guard_applies_to_futures() -> None:
    # Futures whipsaw (shake-out stop → immediate re-entry) must be guarded too.
    orch = _make_orchestrator(asset_class="futures")
    closed = SimpleNamespace(code="A05ABC", strategy="setup_a_gap_reversion")
    exit_signal = ExitSignal(
        code="A05ABC",
        strategy="setup_a_gap_reversion",
        reason=ExitReason.STOP_LOSS,
    )

    orch._record_recent_exit_for_reentry_guard(closed, exit_signal, "stop_loss")

    assert orch._recent_exit_cooldowns != {}
    block = orch._reentry_guard_block(
        Signal(code="A05ABC", strategy="setup_a_gap_reversion")
    )
    assert block is not None
    assert block["reason"] == "stop_loss"


def test_load_guard_config_applies_futures_override() -> None:
    # execution.yaml: futures override -> shorter cooldowns than stock.
    stock = _make_orchestrator(asset_class="stock")
    futures = _make_orchestrator(asset_class="futures")

    stock_cfg = stock._load_entry_reentry_guard_config()
    futures_cfg = futures._load_entry_reentry_guard_config()

    assert stock_cfg.cooldown_for("stop_loss") == 3600  # stock: 60 min
    # futures: 3 min — mean-reversion setups, a long post-stop cooldown cuts the
    # reversal wins (2026-07-07). Env-overridable; retuned from 1800.
    assert futures_cfg.cooldown_for("stop_loss") == 180
    assert futures_cfg.cooldown_for("target_reached") == 600  # futures default 10 min
