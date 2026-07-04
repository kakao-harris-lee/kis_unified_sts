"""Delegation guards for TradingOrchestrator execution helpers."""

from __future__ import annotations

from services.trading.orchestrator import TradingOrchestrator


def test_orchestrator_updates_entry_slippage_stats_through_runtime(
    monkeypatch,
) -> None:
    orchestrator = TradingOrchestrator.__new__(TradingOrchestrator)
    orchestrator._entry_slippage_stats = {}
    calls: list[tuple[dict[str, float], float]] = []

    def fake_update(stats: dict[str, float], adverse_ticks: float) -> None:
        calls.append((stats, adverse_ticks))
        stats["delegated"] = adverse_ticks

    monkeypatch.setattr(
        "services.trading.orchestrator.update_entry_slippage_stats",
        fake_update,
    )

    orchestrator._update_entry_slippage_stats(2.5)

    assert calls == [(orchestrator._entry_slippage_stats, 2.5)]
    assert orchestrator._entry_slippage_stats == {"delegated": 2.5}


def test_orchestrator_serializes_state_transitions_through_runtime(
    monkeypatch,
) -> None:
    transitions = [object()]
    calls: list[list[object]] = []

    def fake_serialize(items: list[object]) -> list[dict[str, str]]:
        calls.append(items)
        return [{"state": "delegated"}]

    monkeypatch.setattr(
        "services.trading.orchestrator.serialize_state_transitions",
        fake_serialize,
    )

    result = TradingOrchestrator._serialize_state_transitions(transitions)

    assert result == [{"state": "delegated"}]
    assert calls == [transitions]
