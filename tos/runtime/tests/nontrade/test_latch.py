"""Tests for :mod:`tos_runtime.nontrade.latch` (TOS runtime operations wiring plan, 2026-09-13,
§2 decision 3): first-call-wins latching, evidence-before-state-change ordering, the
``INCIDENT_CANDIDATE`` row appended on every restrictive call (even a losing second one), and the
repo-wide grep pin on ``record_new_risk_halt(`` callers.
"""

from __future__ import annotations

import re
from pathlib import Path

from tos.evidence import EvidenceAppendReceipt
from tos_runtime.nontrade.latch import latch_restrictive

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]  # tos/runtime
_SRC = _RUNTIME_ROOT / "src"

#: The only files under ``tos_runtime/src`` allowed to call ``record_new_risk_halt(`` — the
#: storage-layer definition itself, this package's own shared latch, and the pre-existing
#: callers the entrypoint-wave survey found (``scratchpad/ep-survey-wiring.md`` §3). Never
#: widened silently — a new caller here is a design decision, not a drive-by addition.
#: ``compose/_types.py``'s OLD ``observe_nontrade`` used to call this directly too; that call
#: is retired now that ``observe_nontrade`` routes through the engine + this module's
#: :func:`~tos_runtime.nontrade.latch.latch_restrictive` instead.
_ALLOWED_FILES = {
    _SRC / "tos_runtime" / "engine" / "inbox.py",
    _SRC / "tos_runtime" / "nontrade" / "latch.py",
    _SRC / "tos_runtime" / "engine" / "orthostate_projection.py",
    _SRC / "tos_runtime" / "safety" / "shutdown.py",
}

#: Requires a receiver dot immediately before the call (``x.record_new_risk_halt(``) — mirrors
#: ``test_no_direct_latch_clear.py``'s own ``_DIRECT_CALL`` idiom so a bare mention (a ``def``
#: line, a prose reference) never matches, only a real call shape does.
_CALL = re.compile(r"[\w.]*\.record_new_risk_halt\(")


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def test_record_new_risk_halt_callers_are_the_known_set_only() -> None:
    offenders: list[str] = []
    for path in _python_files(_SRC):
        if path in _ALLOWED_FILES:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if _CALL.search(line):
                offenders.append(
                    f"{path.relative_to(_RUNTIME_ROOT)}:{lineno}: {line.strip()}"
                )
    assert offenders == [], (
        "record_new_risk_halt( called from an un-registered file — the sanctioned callers are "
        f"{sorted(p.relative_to(_RUNTIME_ROOT).as_posix() for p in _ALLOWED_FILES)}; "
        "offenders:\n" + "\n".join(offenders)
    )


def test_the_call_pattern_catches_every_real_receiver_shape() -> None:
    caught = (
        "self.inbox.record_new_risk_halt(",
        "self._inbox.record_new_risk_halt(",
        "inbox.record_new_risk_halt(",
    )
    for scratch in caught:
        assert _CALL.search(scratch), f"expected the pattern to match: {scratch!r}"
    not_caught = (
        "    def record_new_risk_halt(",
        "# never call record_new_risk_halt() directly",
    )
    for scratch in not_caught:
        assert not _CALL.search(
            scratch
        ), f"expected the pattern NOT to match: {scratch!r}"


class _FakeInbox:
    """A minimal duck-typed double for ``SqliteEventInbox``'s new-risk-halt latch — first-call-
    wins, exactly like the real storage layer (``engine/inbox.py::record_new_risk_halt``).
    """

    def __init__(self) -> None:
        self._halt: dict[str, object] | None = None

    def record_new_risk_halt(
        self, *, reason: str, event_id: str | None, evidence_seq: int | None
    ) -> None:
        if self._halt is None:
            self._halt = {
                "reason": reason,
                "event_id": event_id,
                "evidence_seq": evidence_seq,
            }

    def new_risk_halt(self) -> dict[str, object] | None:
        return self._halt


class _FakeEvidenceStore:
    """A minimal duck-typed :class:`~tos_runtime.evidence.ports.EvidenceAppendPort` double."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []
        self._seq = 0

    def append(self, payload, *, kind: str, record_class: str) -> EvidenceAppendReceipt:
        self._seq += 1
        self.calls.append((kind, record_class, dict(payload)))
        return EvidenceAppendReceipt(seq=self._seq)


def test_first_restrictive_call_latches_and_records_incident_candidate() -> None:
    inbox = _FakeInbox()
    store = _FakeEvidenceStore()
    outcome = latch_restrictive(
        inbox=inbox,
        evidence_store=store,
        disposition="NONTRADE_TRAPPED",
        latch_reason="NONTRADE_NONTRADE_TRAPPED",
        event_id="evt-1",
        evidence_seq=7,
        source="engine",
    )
    assert outcome.latched is True
    assert outcome.first_call is True
    assert outcome.incident_candidate_seq == 1
    assert inbox.new_risk_halt() == {
        "reason": "NONTRADE_NONTRADE_TRAPPED",
        "event_id": "evt-1",
        "evidence_seq": 7,
    }
    assert [kind for kind, _rc, _payload in store.calls] == ["INCIDENT_CANDIDATE"]


def test_incident_candidate_is_appended_before_the_latch_call() -> None:
    """Evidence-before-state-change: if the latch call itself failed, the candidate row must
    already exist — proven here by checking the store recorded something even mid-call, i.e.
    the append happens strictly before ``record_new_risk_halt`` in program order."""
    inbox = _FakeInbox()
    store = _FakeEvidenceStore()
    order: list[str] = []

    real_record = inbox.record_new_risk_halt

    def _spy_record(**kwargs):
        order.append("record_new_risk_halt")
        real_record(**kwargs)

    inbox.record_new_risk_halt = _spy_record  # type: ignore[method-assign]
    real_append = store.append

    def _spy_append(payload, *, kind, record_class):
        order.append("append")
        return real_append(payload, kind=kind, record_class=record_class)

    store.append = _spy_append  # type: ignore[method-assign]

    latch_restrictive(
        inbox=inbox,
        evidence_store=store,
        disposition="NONTRADE_TRAPPED",
        latch_reason="NONTRADE_NONTRADE_TRAPPED",
        event_id="evt-1",
        evidence_seq=7,
        source="engine",
    )
    assert order == ["append", "record_new_risk_halt"]


def test_second_restrictive_call_does_not_overwrite_but_still_records_candidate() -> (
    None
):
    inbox = _FakeInbox()
    store = _FakeEvidenceStore()
    first = latch_restrictive(
        inbox=inbox,
        evidence_store=store,
        disposition="NONTRADE_TRAPPED",
        latch_reason="NONTRADE_NONTRADE_TRAPPED",
        event_id="evt-1",
        evidence_seq=7,
        source="engine",
    )
    second = latch_restrictive(
        inbox=inbox,
        evidence_store=store,
        disposition="NONTRADE_BLOCK_NEW_RISK",
        latch_reason="NONTRADE_NONTRADE_BLOCK_NEW_RISK",
        event_id="evt-2",
        evidence_seq=9,
        source="engine",
    )
    assert first.latched is True
    assert first.first_call is True
    assert second.latched is False
    assert second.first_call is False
    assert second.incident_candidate_seq == 2
    # the underlying halt row is still the FIRST event's — first-call-wins, never overwritten
    assert inbox.new_risk_halt()["event_id"] == "evt-1"
    assert len(store.calls) == 2
    assert all(kind == "INCIDENT_CANDIDATE" for kind, _rc, _payload in store.calls)
