"""Unit tests for ``tools/tos_recovery_drill.py``'s pure ``judge`` (TOS rescope M3).

The drill itself runs as its own CI job (``tos-recovery-drill``); these cases pin that the
judge actually fails each property the drill claims, so a green drill cannot come from a judge
that never says no.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_PATH = Path(__file__).resolve().parents[2] / "tools" / "tos_recovery_drill.py"
_spec = importlib.util.spec_from_file_location("tos_recovery_drill", _PATH)
assert _spec is not None and _spec.loader is not None
drill = importlib.util.module_from_spec(_spec)
sys.modules["tos_recovery_drill"] = drill
_spec.loader.exec_module(drill)

_RESERVATIONS = {"resv-1": "COMMITTED_UNBOUND"}
_LINE = {"attempt_id": "attempt-1", "pid": 1}


def _reboot(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ready": False,
        "readiness_verdict": "NOT_READY",
        "reason": "1 possibly-live attempt(s) unreconciled",
        "possibly_live_event_ids": ["event-1"],
        "interrupted_event_ids": ["event-1"],
        "driver_wired": False,
        "run_once_refused": [True, True],
        "reboot_transport_requests": 0,
        "reservations_at_boot": dict(_RESERVATIONS),
        "reservations_after_refusals": dict(_RESERVATIONS),
        "authority_effect": {"creates_capacity": False, "transmits": False},
    }
    report.update(overrides)
    return report


def _judge(point: str = "AFTER_SEND", **kwargs: Any) -> list[str]:
    args: dict[str, Any] = {
        "killed": True,
        "ledger_at_kill": [_LINE],
        "ledger_after": [_LINE],
        "snapshot": {"point": point, "reservations": dict(_RESERVATIONS)},
        "reboots": [_reboot(), _reboot()],
    }
    args.update(kwargs)
    failures: list[str] = drill.judge(point, **args)
    return failures


def test_a_clean_drill_passes() -> None:
    assert _judge() == []
    assert _judge("BEFORE_SEND", ledger_at_kill=[], ledger_after=[]) == []


def test_an_order_sent_after_restart_fails() -> None:
    second = {"attempt_id": "attempt-2", "pid": 2}
    assert any("after restart" in f for f in _judge(ledger_after=[_LINE, second]))


def test_the_same_attempt_sent_twice_fails() -> None:
    failures = _judge(ledger_at_kill=[_LINE, _LINE], ledger_after=[_LINE, _LINE])
    assert any("more than once" in f for f in failures)


def test_a_send_before_the_before_send_point_fails() -> None:
    failures = _judge("BEFORE_SEND", ledger_at_kill=[_LINE], ledger_after=[_LINE])
    assert any("at kill, expected 0" in f for f in failures)


def test_a_child_that_was_not_killed_fails() -> None:
    assert any("SIGKILL" in f for f in _judge(killed=False))


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"ready": True, "readiness_verdict": "READY"}, "barrier did not hold"),
        ({"driver_wired": True}, "driver was wired"),
        ({"run_once_refused": [True, False]}, "not all refused"),
        ({"reboot_transport_requests": 1}, "transport called"),
        ({"possibly_live_event_ids": []}, "not counted as possibly live"),
        ({"interrupted_event_ids": []}, "no interrupted event"),
        ({"authority_effect": {"creates_capacity": True}}, "grants authority"),
        ({"reservations_after_refusals": {"resv-1": "RELEASED"}}, "capacity released"),
        ({"reservations_at_boot": {}}, "reservations_at_boot"),
        ({"error": "reboot 2 exited 1"}, "exited 1"),
    ],
)
def test_each_reboot_property_fails_on_its_own(
    override: dict[str, Any], fragment: str
) -> None:
    failures = _judge(reboots=[_reboot(), _reboot(**override)])
    assert any(fragment in f for f in failures), failures


def test_a_missing_reboot_report_fails() -> None:
    assert any("reboot report" in f for f in _judge(reboots=[_reboot()]))


def test_a_missing_park_snapshot_fails() -> None:
    assert any("park snapshot" in f for f in _judge(snapshot=None))


def test_positive_control_a_resend_after_restart_is_caught(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A real drill (child processes, real SIGKILL) with ``--inject-send``: the first restart
    calls the wrapped ``send_once`` once. The ledger count after restart must move to 1 and the
    drill must judge FAIL — the restart path otherwise never reaches a send (the driver drops a
    consumed seq, and a fresh seq has no approval), so this is the only run that shows the
    ledger check can see a re-send."""
    report = tmp_path / "drill.json"
    exit_code = drill.main(
        [
            "--rounds",
            "1",
            "--points",
            "BEFORE_SEND",
            "--inject-send",
            "--workdir",
            str(tmp_path / "work"),
            "--json",
            str(report),
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "venue received 1 order(s) after restart" in out
    assert "FAIL BEFORE_SEND r1" in out
    result = json.loads(report.read_text("utf-8"))
    assert result["passed"] == 0
    (only,) = result["drills"]
    assert only["passed"] is False
    assert only["killed_by_sigkill"] is True
    assert (only["venue_orders_at_kill"], only["venue_orders_after_restarts"]) == (0, 1)
