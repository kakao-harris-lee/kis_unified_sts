"""Setup A RISK_OFF boost telemetry must reach *persisted* position metadata.

``f032080c`` capped the Setup A RISK_OFF confidence product at 1.0, which
erased the only durable fingerprint that the boost had fired (a persisted
``Signal.confidence`` above 1.0).  ``shared/strategy/entry/setup_a_adapter.py``
threads three replacement keys onto ``Signal.metadata`` instead:

- ``llm_risk_off_boost_applied``  (bool; explicit ``False`` when the helper ran
  but the boost did not fire, and *absent* when the helper never ran)
- ``llm_risk_off_base_confidence`` (pre-boost)
- ``llm_risk_off_raw_confidence``  (uncapped product)

These tests pin that the keys survive the orchestrator's
``signal.metadata`` -> ``pos_metadata`` copy in ``_process_filled_entry`` and
land in both durable surfaces that record ``position.metadata`` verbatim:

- the RuntimeLedger ``position_snapshots.payload_json`` column
  (``shared/storage/runtime_ledger_records.py``), and
- ``trade_outcomes.jsonl`` (``_record_entry_telemetry``).

The absence-vs-``False`` pair is asserted in both directions on purpose: a
forwarding rule that collapses "the helper ran and declined" into "the helper
never ran" destroys exactly the evidence an operator needs to judge the live
``1.3`` multiplier.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.models.signal import Signal
from shared.storage.runtime_ledger import SQLiteRuntimeLedger

RISK_OFF_KEYS = (
    "llm_risk_off_boost_applied",
    "llm_risk_off_base_confidence",
    "llm_risk_off_raw_confidence",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tracker(tmp_path) -> tuple[PositionTracker, SQLiteRuntimeLedger]:
    """Real tracker + real SQLite ledger so persistence is exercised, not mocked."""
    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
    tracker = PositionTracker(
        config=PositionTrackerConfig(
            asset_class="futures",
            runtime_ledger_backend="sqlite",
            flush_interval_seconds=0,
        ),
        runtime_ledger=ledger,
    )
    return tracker, ledger


def _make_orchestrator(tmp_path, tracker):
    """Minimal TradingOrchestrator wired for a real ``_process_filled_entry``.

    Only the surfaces that are *not* part of the telemetry reach chain are
    stubbed (notification, metrics, indicator engine, publishers). The position
    tracker, ledger and ``trade_outcomes.jsonl`` writer are real.
    """
    from services.trading.orchestrator import TradingConfig, TradingOrchestrator

    config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
    config.paper_trading = True

    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = config
    orch._position_tracker = tracker
    orch._futures_slippage_controller = None
    orch._indicator_engine = None
    orch._regime_tracker = None
    orch._state_publisher = None
    orch._mock_mirror = None
    orch._metrics = None
    orch._current_regime = "SIDEWAYS_FLAT"
    orch.total_trades = 0
    orch._symbol_names = {}
    orch._entry_slippage_stats = {}
    orch._llm_training_data_dir = str(tmp_path)
    # Logging/notification is not part of the reach chain under test.
    orch._log_entry = MagicMock()
    return orch


def _setup_a_signal(metadata: dict | None = None) -> Signal:
    return Signal(
        code="A05608",
        name="KOSPI200 F",
        strategy="setup_a_gap_reversion",
        price=330.49,
        confidence=1.0,
        metadata=dict(metadata or {}),
    )


async def _enter(orch, signal):
    await orch._process_filled_entry(
        signal,
        330.50,
        1,
        False,
        "long",
        execution_meta={"mode": "slippage_guard"},
    )
    positions = list(orch._position_tracker.positions)
    assert len(positions) == 1
    return positions[0]


def _ledger_payload(ledger: SQLiteRuntimeLedger) -> dict:
    """Read back the single persisted position snapshot payload."""
    rows = ledger.load_open_positions(asset_class="futures")
    assert len(rows) == 1
    payload = rows[0].get("payload")
    assert isinstance(payload, dict)
    return payload


def _trade_outcomes_entry(tmp_path) -> dict:
    path = tmp_path / "trade_outcomes.jsonl"
    assert path.exists(), "trade_outcomes.jsonl was never written"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    return json.loads(lines[0])


# ---------------------------------------------------------------------------
# 1. The regression: telemetry must reach the persisted record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_risk_off_telemetry_reaches_persisted_position_metadata(tmp_path):
    """A boosted Setup A signal leaves a queryable record in both durable stores."""
    tracker, ledger = _make_tracker(tmp_path)
    orch = _make_orchestrator(tmp_path, tracker)

    signal = _setup_a_signal(
        {
            "llm_risk_off_boost_applied": True,
            "llm_risk_off_base_confidence": 0.82,
            "llm_risk_off_raw_confidence": 1.066,
        }
    )

    position = await _enter(orch, signal)

    # In-memory position metadata
    assert position.metadata["llm_risk_off_boost_applied"] is True
    assert position.metadata["llm_risk_off_base_confidence"] == 0.82
    assert position.metadata["llm_risk_off_raw_confidence"] == 1.066

    # Durable surface 1: RuntimeLedger position_snapshots.payload_json
    saved = await tracker.save_to_db()
    assert saved == 1
    ledger_metadata = _ledger_payload(ledger)["metadata"]
    assert ledger_metadata["llm_risk_off_boost_applied"] is True
    assert ledger_metadata["llm_risk_off_base_confidence"] == 0.82
    assert ledger_metadata["llm_risk_off_raw_confidence"] == 1.066

    # Durable surface 2: trade_outcomes.jsonl
    outcome_metadata = _trade_outcomes_entry(tmp_path)["metadata"]
    assert outcome_metadata["llm_risk_off_boost_applied"] is True
    assert outcome_metadata["llm_risk_off_base_confidence"] == 0.82
    assert outcome_metadata["llm_risk_off_raw_confidence"] == 1.066

    # Durable surface 3: RuntimeLedger trades.payload_json, on close. This is
    # the surface an operator actually joins against realised PnL when judging
    # whether the live 1.3 multiplier earns its keep.
    closed = tracker.close_position(position.id, 335.0, "take_profit")
    assert closed is not None
    assert await tracker.save_futures_trade_to_db(closed, "futures") is True
    trades = ledger.query_trades({"asset_class": "futures"})
    assert len(trades) == 1
    trade_metadata = trades[0]["payload"]["metadata"]
    assert trade_metadata["llm_risk_off_boost_applied"] is True
    assert trade_metadata["llm_risk_off_base_confidence"] == 0.82
    assert trade_metadata["llm_risk_off_raw_confidence"] == 1.066


# ---------------------------------------------------------------------------
# 2. Absence vs False -- both directions, never collapsed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_boost_declined_persists_explicit_false(tmp_path):
    """The helper ran and declined: ``False`` is persisted, not dropped."""
    tracker, ledger = _make_tracker(tmp_path)
    orch = _make_orchestrator(tmp_path, tracker)

    signal = _setup_a_signal(
        {
            "llm_risk_off_boost_applied": False,
            "llm_risk_off_base_confidence": 0.61,
            "llm_risk_off_raw_confidence": 0.61,
        }
    )

    position = await _enter(orch, signal)

    assert "llm_risk_off_boost_applied" in position.metadata
    assert position.metadata["llm_risk_off_boost_applied"] is False

    await tracker.save_to_db()
    ledger_metadata = _ledger_payload(ledger)["metadata"]
    assert "llm_risk_off_boost_applied" in ledger_metadata
    assert ledger_metadata["llm_risk_off_boost_applied"] is False
    assert ledger_metadata["llm_risk_off_base_confidence"] == 0.61

    outcome_metadata = _trade_outcomes_entry(tmp_path)["metadata"]
    assert outcome_metadata["llm_risk_off_boost_applied"] is False


@pytest.mark.asyncio
async def test_helper_never_ran_persists_no_key_at_all(tmp_path):
    """The helper never ran: the key stays *absent*, it is not coerced to False."""
    tracker, ledger = _make_tracker(tmp_path)
    orch = _make_orchestrator(tmp_path, tracker)

    position = await _enter(orch, _setup_a_signal({}))

    for key in RISK_OFF_KEYS:
        assert key not in position.metadata

    await tracker.save_to_db()
    ledger_metadata = _ledger_payload(ledger)["metadata"]
    for key in RISK_OFF_KEYS:
        assert key not in ledger_metadata

    outcome_metadata = _trade_outcomes_entry(tmp_path)["metadata"]
    for key in RISK_OFF_KEYS:
        assert key not in outcome_metadata


# ---------------------------------------------------------------------------
# 3. No collateral change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exit_override_forwarding_still_works(tmp_path):
    """The pre-existing exit-parameter allowlist is untouched by the new block."""
    tracker, _ledger = _make_tracker(tmp_path)
    orch = _make_orchestrator(tmp_path, tracker)

    signal = _setup_a_signal(
        {
            "stop_loss": 325.0,
            "take_profit": 340.0,
            "entry_atr": 2.5,
            "exit_stop_atr_multiplier": 1.5,
            "exit_trail_activation_atr": 1.0,
            "exit_trail_atr_multiplier": 2.0,
            "exit_max_hold_days": 3,
            "llm_risk_off_boost_applied": True,
            "llm_risk_off_base_confidence": 0.9,
            "llm_risk_off_raw_confidence": 1.17,
        }
    )

    position = await _enter(orch, signal)

    assert position.metadata["stop_loss"] == 325.0
    assert position.metadata["take_profit"] == 340.0
    assert position.metadata["entry_atr"] == 2.5
    assert position.metadata["exit_stop_atr_multiplier"] == 1.5
    assert position.metadata["exit_trail_activation_atr"] == 1.0
    assert position.metadata["exit_trail_atr_multiplier"] == 2.0
    assert position.metadata["exit_max_hold_days"] == 3
    # ...and the absolute stop is still promoted onto the position itself.
    assert position.stop_price == 325.0
    assert position.metadata["llm_risk_off_boost_applied"] is True


@pytest.mark.asyncio
async def test_signal_without_new_keys_yields_unchanged_pos_metadata(tmp_path):
    """A signal carrying none of the new keys produces the pre-change key set.

    The expected set is hardcoded rather than derived from the implementation so
    an accidental widening of either forwarding block fails loudly here.
    """
    tracker, _ledger = _make_tracker(tmp_path)
    orch = _make_orchestrator(tmp_path, tracker)

    position = await _enter(orch, _setup_a_signal({"stop_loss": 325.0}))

    assert set(position.metadata) == {
        "snapshot_id",
        "llm_quality",
        "realtime_score",
        "risk_flags",
        "entry_signal_confidence",
        "signal_direction",
        "execution",
        "entry_regime",
        "stop_loss",
    }
