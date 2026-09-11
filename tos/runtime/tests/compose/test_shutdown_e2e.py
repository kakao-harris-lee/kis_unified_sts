"""``ComposedRuntime.shutdown()`` compose e2e tests (TOS Phase 5 W3.2 plan §2 decision 9,
lane d3). Hermetic — a real composed runtime, real sqlite files under ``tmp_path``, real
custody files (``tests/compose/conftest.py``'s autouse guards enforce this); no transport
call is ever made (this suite never calls :meth:`~tos_runtime.compose._types.ComposedRuntime
.run_once`).
"""

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
    """A nominal shutdown on a freshly composed (never-run) runtime proves all six steps
    and never touches the transport this suite's own docstring promises."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)

    outcome = runtime.shutdown(reason="compose-e2e-nominal-shutdown")

    assert outcome.all_steps_proven is True
    assert len(outcome.procedure.ordered_steps) == 6
    assert all(step.completed is True for step in outcome.procedure.ordered_steps)
    assert outcome.not_broker_finality is True
    assert outcome.obligations_survive_shutdown_called is False
    # honest at shutdown time — no Recovery Session has accepted anything yet.
    assert outcome.handoff_accepted is False
    assert len(runtime.transport.requests) == 0


def test_reboot_after_shutdown_sees_the_durable_new_risk_halt_latch(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Deny-before-stop is durable: a SECOND compose over the SAME ``data_dir`` — a fresh
    process boot, in every way this test can express without literally forking a new
    Python process — still sees the latch the first runtime's shutdown set. Boot itself
    is not refused by a held latch (only per-event send admission is, driver-side) —
    this is exactly the "boots with the latch held" contract lane d3's plan §4 entry
    describes."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    first_outcome = runtime.shutdown(reason="compose-e2e-reboot-first-boot")
    assert first_outcome.procedure.deny_before_stop is True

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
    """The recovery-handoff package is durably recorded as evidence BEFORE the store
    closes — a FRESH reader (never the closed instance under test, and never the same
    process's cached handle) over the SAME evidence/inbox files sees it, exactly what the
    next boot's W1 recovery barrier would read to decide acceptance (plan §4 lane d3:
    "record the package for the barrier to consume, do not fake acceptance")."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    outcome = runtime.shutdown(reason="compose-e2e-handoff-evidence")
    assert outcome.handoff_package.unresolved_obligations == outcome.obligations

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
