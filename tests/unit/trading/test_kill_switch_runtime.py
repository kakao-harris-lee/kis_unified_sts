"""Owner tests for kill-switch runtime parsing helpers."""

from __future__ import annotations

from services.trading.kill_switch_runtime import (
    KillSwitchRequest,
    parse_force_flatten_request,
)


def test_parse_force_flatten_request_defaults_reason() -> None:
    request = parse_force_flatten_request({"event_id": "1-0", "source": "unit"})

    assert request == KillSwitchRequest(
        event_id="1-0",
        source="unit",
        reason="force_flatten",
        dry_run=False,
    )


def test_parse_force_flatten_request_handles_string_dry_run() -> None:
    request = parse_force_flatten_request(
        {"event_id": "2-0", "source": "unit", "dry_run": "true"}
    )

    assert request.dry_run is True


def test_parse_force_flatten_request_decodes_bytes() -> None:
    request = parse_force_flatten_request(
        {
            b"event_id": b"3-0",
            b"source": b"sentinel",
            b"reason": b"operator",
            b"dry_run": b"1",
        }
    )

    assert request == KillSwitchRequest(
        event_id="3-0",
        source="sentinel",
        reason="operator",
        dry_run=True,
    )
