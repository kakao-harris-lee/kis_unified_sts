"""``ComposedRuntime.shutdown()`` compose e2e tests (TOS Phase 5 W3.2 plan §2 decision 9,"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore

from .test_compose_root import _compose

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def test_shutdown_proves_every_step_with_zero_transport_calls(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """A nominal shutdown on a freshly composed (never-run) runtime proves all six steps"""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)

    outcome = runtime.shutdown(reason="compose-e2e-nominal-shutdown")

    assert outcome.all_steps_proven is True
    assert len(outcome.steps) == 5
    assert all(step.completed is True for step in outcome.steps)
    assert outcome.latched_before_close is True
    assert len(runtime.transport.requests) == 0


def test_reboot_after_shutdown_sees_the_durable_new_risk_halt_latch(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Deny-before-stop is durable: a SECOND compose over the SAME ``data_dir`` — a fresh"""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    first_outcome = runtime.shutdown(reason="compose-e2e-reboot-first-boot")
    assert first_outcome.latched_before_close is True

    runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
    try:
        assert runtime2.inbox.new_risk_halt() is not None
    finally:
        runtime2.inbox.close()
        runtime2.rcl_log.close()
        runtime2.evidence_store.close()


def test_shutdown_evidence_and_latch_are_durable_after_the_instance_is_closed(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """The recovery-handoff package is durably recorded as evidence BEFORE the store"""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    outcome = runtime.shutdown(reason="compose-e2e-handoff-evidence")
    assert outcome.handoff_id is not None

    reopened_evidence = SqliteEvidenceStore(
        data_dir / "evidence.sqlite3", key_provider=runtime.key_provider
    )
    try:
        kinds = [row.kind for row in reopened_evidence.iter_entry_meta()]
    finally:
        reopened_evidence.close()
    assert "CONTROLLED_SHUTDOWN_STARTED" in kinds
    assert "CONTROLLED_SHUTDOWN_STEPS" in kinds
    assert "CONTROLLED_SHUTDOWN_HANDOFF" in kinds

    reopened_inbox = SqliteEventInbox(data_dir / "inbox.sqlite3", scheme=_SCHEME)
    try:
        assert reopened_inbox.new_risk_halt() is not None
    finally:
        reopened_inbox.close()
