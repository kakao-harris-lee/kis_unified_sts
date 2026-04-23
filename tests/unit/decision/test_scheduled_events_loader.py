# tests/unit/decision/test_scheduled_events_loader.py
from shared.decision.context import load_scheduled_events


def test_load_from_yaml_round_trips(tmp_path):
    y = tmp_path / "scheduled_events.yaml"
    y.write_text(
        "events:\n"
        "  - event_id: fomc_2026_may\n"
        "    event_type: FOMC_rate_decision\n"
        "    scheduled_at: '2026-05-01T03:00:00Z'\n"
        "    impact_tier: 1\n"
    )
    events = load_scheduled_events(str(y))
    assert len(events) == 1
    assert events[0].event_type == "FOMC_rate_decision"
    assert events[0].impact_tier == 1
