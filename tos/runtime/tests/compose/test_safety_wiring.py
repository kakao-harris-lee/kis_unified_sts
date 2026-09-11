"""Tests for :mod:`tos_runtime.compose._safety_wiring` (Phase 5 W3-b).

Covers W3.1 independent review HIGH-1: the MONITORING evidence-tip observer must be
independent of this service's OWN ``STM_ALERT`` writes to the same store, or a genuine,
continuing evidence-tip stall flaps deny/clear/clear instead of staying denied.
"""

from __future__ import annotations

from pathlib import Path

from tos.cur import DimensionKey
from tos_runtime.compose._safety_wiring import (
    _STM_ALERT_KIND,
    _current_tick_snapshot,
    _evidence_tip_observer_excluding_own_alerts,
    _refresh_tick_snapshot,
    _SafetyMeshTickCell,
    _stm_alert_recorder_for,
)
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.safety.ports import MeshClearance

from ..evidence.conftest import FixedKeyProvider


def _store(tmp_path: Path) -> SqliteEvidenceStore:
    return SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )


def test_observer_ignores_the_store_s_own_stm_alert_writes(tmp_path: Path) -> None:
    """The wiring-level fix: an STM_ALERT write through the SAME sink this observer
    reads from must never be read back as tip advancement."""
    store = _store(tmp_path)
    observer = _evidence_tip_observer_excluding_own_alerts(store)
    recorder = _stm_alert_recorder_for(store)

    store.append({"a": 1}, kind="OTHER", record_class="OTHERCLASS")
    seq_before, digest_before, _ = observer()
    assert seq_before == 0

    # Simulate MonitoringService's own alert emission on a non-True clear() -- the
    # exact self-perturbation HIGH-1 describes.
    recorder(_STM_ALERT_KIND, {"reason": "stall"})

    # The unfiltered store view DOES see the alert (proving the alert really was
    # written, and that a caller reading last_committed() directly WOULD be fooled).
    unfiltered_seq, _, _ = store.last_committed()
    assert unfiltered_seq == 1

    # The wired observer does not.
    seq_after, digest_after, _ = observer()
    assert seq_after == seq_before
    assert digest_after == digest_before

    store.close()


def test_observer_still_reflects_a_genuine_non_alert_append(tmp_path: Path) -> None:
    store = _store(tmp_path)
    observer = _evidence_tip_observer_excluding_own_alerts(store)
    recorder = _stm_alert_recorder_for(store)

    store.append({"a": 1}, kind="OTHER", record_class="OTHERCLASS")
    recorder(_STM_ALERT_KIND, {"reason": "stall"})
    store.append({"a": 2}, kind="OTHER", record_class="OTHERCLASS")

    seq, _, _ = observer()
    assert seq == 2  # the genuine second OTHER append, never the alert row in between

    store.close()


def test_stall_stays_denied_across_three_consecutive_ticks_while_the_tip_is_frozen(
    tmp_path: Path,
) -> None:
    """The end-to-end reproduction of the reviewer's flap (module docstring), driven
    through a real MonitoringService wired with the fixed observer + recorder: three
    consecutive ticks over a frozen (non-alert) tip must ALL deny, never flap back to
    clear because of the service's own alert writes.
    """
    from tos_runtime.safety.monitoring import MonitoringService

    store = _store(tmp_path)
    coverage_path = tmp_path / "monitor_coverage.yaml"
    coverage_path.write_text(
        """
coverage:
  manifest:
    coverage_manifest_id: cov-1
    coverage_generation: 1
    coverage_manifest_digest: digest-1
    policy_digest: digest-2
    is_complete: true
  items:
    evidence-tip-currency:
      restrictive_response_present: true
      alert_path_present: true
      evidence_path_present: true
      currentness_rule_present: true
      closure_1_to_12_complete: true
      criticality: CRITICAL
    time-service-health:
      restrictive_response_present: true
      alert_path_present: true
      evidence_path_present: true
      currentness_rule_present: true
      closure_1_to_12_complete: true
      criticality: CRITICAL
    inbox-backlog:
      restrictive_response_present: true
      alert_path_present: true
      evidence_path_present: true
      currentness_rule_present: true
      closure_1_to_12_complete: true
      criticality: CRITICAL
  bounds:
    max_evidence_tip_stall_ms: 1000
    healthy_time_states: ["TRUSTED"]
    max_inbox_unconsumed: 100
""",
        encoding="utf-8",
    )

    clock_ns = [0]

    def monotonic_ns() -> int:
        return clock_ns[0]

    store.append({"a": 1}, kind="OTHER", record_class="OTHERCLASS")

    service = MonitoringService(
        config_path=coverage_path,
        evidence_tip_observer=_evidence_tip_observer_excluding_own_alerts(store),
        time_health_observer=lambda: "TRUSTED",
        inbox_unconsumed_observer=lambda: 0,
        monotonic_ns=monotonic_ns,
        evidence_recorder=_stm_alert_recorder_for(store),
    )

    # First observation establishes the baseline (never itself a stall).
    service.clear()

    # Advance well past the stall bound, with NO non-alert append in between -- the
    # tip is genuinely frozen. Three consecutive ticks must all deny.
    clock_ns[0] = 2_000 * 1_000_000
    for _ in range(3):
        clearance = service.clear()
        assert clearance.clear is not True

    store.close()


# ============================================================================
# SafetyMeshSnapshot — one evaluation shared by every per-tick consumer
# (team-lead disposition following HIGH-1/HIGH-2: clear() is now stateful, so calling
# it 3+ times per tick from 3 separate consumers can see 3 different answers).
# ============================================================================


class _CountingMeshService:
    """A minimal :class:`~tos_runtime.safety.ports.SafetyMeshService` double that counts
    how many times each of its two methods is actually called."""

    def __init__(self, *, identity: str = "counting-service") -> None:
        self._identity = identity
        self.clear_calls = 0
        self.dimension_report_calls = 0

    @property
    def identity(self) -> str:
        return self._identity

    @property
    def dimension_key(self) -> DimensionKey:
        return DimensionKey.SAFETY_ENVELOPE_PROFILE

    def dimension_report(self):
        self.dimension_report_calls += 1
        return None

    def clear(self) -> MeshClearance:
        self.clear_calls += 1
        return MeshClearance(identity=self._identity, clear=True, reasons=())

    def describe(self):
        return {}


def test_snapshot_is_computed_once_and_reused_by_every_consumer_within_one_tick() -> (
    None
):
    """The invocation-count pin the team lead asked for: across a SIMULATED single
    tick's three consumers (Coordinator refresh, currentness dimension_report read,
    deferred-fields read), a service's clear()/dimension_report() must each be called
    exactly once — never once per consumer."""
    service = _CountingMeshService()
    services = (service,)
    cell = _SafetyMeshTickCell()

    # Consumer 1: the Coordinator ALWAYS refreshes, unconditionally, at the top of
    # every live_scope_authorized() call -- this is what makes the cell hold THIS
    # tick's snapshot before either later consumer runs.
    _refresh_tick_snapshot(services, cell)
    assert service.clear_calls == 1
    assert service.dimension_report_calls == 1

    # Consumer 2: the currentness dimension_report reader -- reuses the cell, no new
    # evaluation.
    snapshot_for_currentness = _current_tick_snapshot(services, cell)
    assert snapshot_for_currentness.report_for(service.identity) is None
    assert service.clear_calls == 1
    assert service.dimension_report_calls == 1

    # Consumer 3: the deferred-mesh-fields read -- also reuses the cell.
    snapshot_for_deferred = _current_tick_snapshot(services, cell)
    assert snapshot_for_deferred.clear_for(service.identity).clear is True
    assert service.clear_calls == 1
    assert service.dimension_report_calls == 1


def test_snapshot_refreshes_on_the_next_tick() -> None:
    """The cell must NOT silently carry a stale snapshot into the NEXT tick -- the
    Coordinator's own unconditional refresh (every live_scope_authorized() call) is
    what guarantees this."""
    service = _CountingMeshService()
    services = (service,)
    cell = _SafetyMeshTickCell()

    _refresh_tick_snapshot(services, cell)  # tick 1
    assert service.clear_calls == 1

    _refresh_tick_snapshot(services, cell)  # tick 2
    assert service.clear_calls == 2


def test_current_tick_snapshot_takes_one_when_the_cell_starts_empty() -> None:
    """A consumer that happens to run FIRST in a tick (e.g. on the synthetic path,
    where the Coordinator's mesh question is never reached) still gets a real,
    freshly-taken snapshot -- never a crash on an empty cell."""
    service = _CountingMeshService()
    services = (service,)
    cell = _SafetyMeshTickCell()
    assert cell.snapshot is None

    snapshot = _current_tick_snapshot(services, cell)
    assert snapshot.clear_for(service.identity).clear is True
    assert service.clear_calls == 1
    assert cell.snapshot is snapshot
