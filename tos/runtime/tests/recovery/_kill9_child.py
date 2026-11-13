"""Child process for the kill -9 recovery drill (TOS rescope plan §2 sentence 3, M3)."""

from __future__ import annotations

import dataclasses
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

from tos.brokeradapter.synthetic import SyntheticPaperTransport
from tos.engine.records import event_identity

from ..compose import _fixtures as fx
from ..compose.conftest import (
    call_wrapped_fixture,
    config_dir,
    custody_root,
    data_dir,
    write_approval_file,
)
from ..compose.test_compose_root import _compose
from ..conftest import _guarded_connect, _guarded_connect_ex, _guarded_sendto
from ..engine.conftest import SCHEME

POINTS = ("BEFORE_SEND", "AFTER_SEND", "AFTER_RESULT")
VENUE_LEDGER_NAME = "venue_ledger.jsonl"
PARK_SNAPSHOT_NAME = "park_snapshot.json"
_RESULT_RECORDED_KIND = "EGRESS_RESULT_RECORDED"
_DRILL_EVENT_SEQ = 1
_FRESH_EVENT_SEQ = 999


def _install_network_guard() -> None:
    """The suite's own loopback-only guard (``tests/conftest.py``), installed for the whole"""
    for name, guard in (
        ("connect", _guarded_connect),
        ("connect_ex", _guarded_connect_ex),
        ("sendto", _guarded_sendto),
    ):
        setattr(socket.socket, name, guard)


def _roots(root: Path) -> tuple[Path, Path, Path]:
    return root / "config", root / "data", root / "custody"


def _build_fixtures(root: Path) -> tuple[Path, Path, Path]:
    return (
        call_wrapped_fixture(config_dir, root),
        call_wrapped_fixture(data_dir, root),
        call_wrapped_fixture(custody_root, root),
    )


def _append_venue_line(ledger: Path, record: dict[str, Any]) -> None:
    fd = os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (json.dumps(record, sort_keys=True) + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def _reservations(runtime: Any) -> dict[str, str]:
    return {
        reservation_id: str(state)
        for reservation_id, state, _seq, _scope in runtime.rcl_log.reservation_rows()
    }


def _wrap_transport(runtime: Any, root: Path, park_at: str | None) -> None:
    """Put the venue ledger (and, in crash mode, the park points) around ``send_once``."""
    ledger = root / VENUE_LEDGER_NAME
    if type(runtime.transport) is not SyntheticPaperTransport:
        raise SystemExit(
            f"drill refuses a non-synthetic transport: {type(runtime.transport)!r}"
        )
    transport: Any = runtime.transport
    real_send_once = transport.send_once

    def send_once(attempt: Any, **kwargs: Any) -> Any:
        if park_at == "BEFORE_SEND":
            _park(runtime, root, "BEFORE_SEND")
        _append_venue_line(
            ledger, {"attempt_id": attempt.attempt_id, "pid": os.getpid()}
        )
        result = real_send_once(attempt, **kwargs)
        if park_at == "AFTER_SEND":
            _park(runtime, root, "AFTER_SEND")
        return result

    transport.send_once = send_once


def _wrap_result_recorded(runtime: Any, root: Path) -> None:
    store = runtime.evidence_store
    real_append = store.append

    def append(payload: Any, *, kind: str, record_class: str, **kwargs: Any) -> Any:
        receipt = real_append(payload, kind=kind, record_class=record_class, **kwargs)
        if kind == _RESULT_RECORDED_KIND:
            _park(runtime, root, "AFTER_RESULT")
        return receipt

    store.append = append


def _park(runtime: Any, root: Path, point: str) -> None:
    """Record what capacity looks like right now, then wait to be killed."""
    snapshot = {"point": point, "reservations": _reservations(runtime)}
    fd = os.open(
        root / PARK_SNAPSHOT_NAME, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
    )
    try:
        os.write(fd, json.dumps(snapshot, sort_keys=True).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    sys.stdout.write(f"AT {point}\n")
    sys.stdout.flush()
    sys.stdin.readline()
    raise SystemExit(f"parked at {point} but was not killed")


def crash(root: Path, point: str) -> int:
    if point not in POINTS:
        raise SystemExit(f"unknown point {point!r}; expected one of {POINTS}")
    _install_network_guard()
    cfg, data, custody = _build_fixtures(root)
    runtime = _compose(root, cfg, data, custody)
    event = fx.crossing_event(seq=_DRILL_EVENT_SEQ)
    first = runtime.run_once((event,))
    proposal_digest = first[0].pipeline.proposal.canonical_digest
    construction = runtime.construction_stage.construction
    write_approval_file(
        custody,
        proposal_digest=proposal_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    _wrap_transport(runtime, root, point)
    if point == "AFTER_RESULT":
        _wrap_result_recorded(runtime, root)
    runtime.run_once((event,))
    sys.stdout.write("NO_PARK\n")
    sys.stdout.flush()
    return 3


def reboot(root: Path, result_path: Path) -> int:
    from tos_runtime.compose._types import RecoveryBarrierHeld

    _install_network_guard()
    cfg, data, custody = _roots(root)
    runtime = _compose(root, cfg, data, custody)
    _wrap_transport(runtime, root, None)
    recovery = runtime.recovery
    reservations_at_boot = _reservations(runtime)
    interrupted = sorted(
        event_identity(event, scheme=SCHEME)
        for seq, event in runtime.inbox.replay()
        if runtime.inbox.handling_started_receipt(seq) is not None
        and not runtime.inbox.is_consumed(seq)
    )
    refused: list[bool] = []
    for seq in (_DRILL_EVENT_SEQ, _FRESH_EVENT_SEQ):
        try:
            runtime.run_once((fx.crossing_event(seq=seq),))
        except RecoveryBarrierHeld:
            refused.append(True)
        else:
            refused.append(False)
    result = {
        "ready": None if recovery is None else recovery.ready,
        "readiness_verdict": (
            None if recovery is None else str(recovery.readiness_verdict)
        ),
        "reason": None if recovery is None else recovery.reason,
        "possibly_live_event_ids": (
            [] if recovery is None else sorted(recovery.possibly_live_reconciliation)
        ),
        "interrupted_event_ids": interrupted,
        "driver_wired": runtime.driver is not None,
        "run_once_refused": refused,
        "reboot_transport_requests": len(runtime.transport.requests),
        "reservations_at_boot": reservations_at_boot,
        "reservations_after_refusals": _reservations(runtime),
        "authority_effect": (
            None if recovery is None else dataclasses.asdict(recovery.authority_effect)
        ),
    }
    runtime.rcl_log.close()
    runtime.evidence_store.close()
    result_path.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "crash":
        return crash(Path(argv[1]), argv[2])
    if len(argv) == 3 and argv[0] == "reboot":
        return reboot(Path(argv[1]), Path(argv[2]))
    raise SystemExit("usage: crash <root> <point> | reboot <root> <result.json>")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
