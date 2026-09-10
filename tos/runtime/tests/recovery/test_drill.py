"""Crash-drill tests for the TOS Phase 5 W1 recovery barrier (plan §2 decision 2; §5 rows 1-2).

Boots a full :func:`~tos_runtime.compose.root.compose_paper_runtime` runtime in ``tmp_path``,
injects each Phase 3 crash window directly against the SAME durable inbox/evidence-store files
the runtime already opened (mirroring ``tos/runtime/tests/engine/test_driver.py``'s own
crash-window technique — never a real OS-level crash), then rebuilds the runtime from the same
``data_dir`` (a real reboot: ``compose_paper_runtime`` called again, same
``tos.runtime.tests.compose.test_compose_root.TestRecomposeReplay`` convention of closing
``rcl_log``/``evidence_store`` before the second boot) and asserts the recovery barrier's verdict.
"""

from __future__ import annotations

import pytest
from tos.engine.records import event_identity
from tos.engine.vocabulary import HaltReason
from tos.sbr.vocabulary import ReadinessVerdict
from tos_runtime.compose._types import RecoveryBarrierHeld

from .conftest import SCHEME, _compose, _reach_trusted, fx, write_approval_file

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_EVENT_HANDLING_STARTED_KIND = "EVENT_HANDLING_STARTED"
_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_SEND_STARTED_KIND = "SEND_STARTED"


def _mark_handling_started(runtime, event) -> tuple[str, int]:
    """Durably record the write-ahead marker for ``event`` without ever calling the driver —
    the common first half of every crash-window injection below."""
    receipt = runtime.inbox.enqueue(event)
    event_id = event_identity(event, scheme=SCHEME)
    marker = runtime.evidence_store.append(
        {"event_id": event_id},
        kind=_EVENT_HANDLING_STARTED_KIND,
        record_class=_EVENT_HANDLING_STARTED_KIND,
    )
    runtime.inbox.mark_handling_started(
        receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
    )
    return event_id, receipt.seq


def _reboot(tmp_path, config_dir, data_dir, custody_root, runtime):
    runtime.rcl_log.close()
    runtime.evidence_store.close()
    return _compose(tmp_path, config_dir, data_dir, custody_root)


def _assert_held(
    runtime2, *, expected_event_ids: set[str], reason_fragment: str
) -> None:
    assert runtime2.driver is None
    assert runtime2.recovery is not None
    assert runtime2.recovery.readiness_verdict is ReadinessVerdict.NOT_READY
    assert runtime2.recovery.ready is False
    assert reason_fragment in runtime2.recovery.reason
    assert set(runtime2.recovery.possibly_live_reconciliation) >= expected_event_ids
    # (d) capacity is neither released nor re-armed: with no driver wired, nothing in this
    # runtime can even reach the gateway/RCL reservation lifecycle again.
    with pytest.raises(RecoveryBarrierHeld):
        runtime2.run_once((fx.crossing_event(seq=999),))
    # (c) duplicate send 0: the synthetic transport never received a second call across restart.
    assert len(runtime2.transport.requests) == 0


def test_crash_marker_only_holds_the_barrier(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    """Crash window 1 (the SAFER half, per ``EngineDriver``'s own module docstring N1): the
    ``EVENT_HANDLING_STARTED`` marker is durable, but ``core.handle`` never even ran — no send
    evidence exists at all. This barrier does not distinguish it from the wider window (module
    docstring's "any ambiguity is included, never excluded") — it holds all the same."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    event_id, _seq = _mark_handling_started(runtime, fx.crossing_event(seq=1))

    runtime2 = _reboot(tmp_path, config_dir, data_dir, custody_root, runtime)
    _assert_held(
        runtime2, expected_event_ids={event_id}, reason_fragment="possibly-live"
    )


def test_crash_after_send_evidence_holds_the_barrier(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    """Crash window 2 (the WIDEST — independent review finding #3): the marker AND a real
    ``SEND_STARTED`` record both exist, but there is still no ``EVENT_CONSUMED`` receipt — the
    interrupted flow may already have reached the broker."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    event_id, _seq = _mark_handling_started(runtime, fx.crossing_event(seq=1))
    runtime.evidence_store.append(
        {"attempt_id": "attempt-crash-drill"},
        kind=_SEND_STARTED_KIND,
        record_class=_SEND_STARTED_KIND,
    )

    runtime2 = _reboot(tmp_path, config_dir, data_dir, custody_root, runtime)
    _assert_held(
        runtime2, expected_event_ids={event_id}, reason_fragment="possibly-live"
    )


def test_crash_evidence_committed_before_inbox_mark_holds_the_barrier(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    """Crash window 3: the ``EVENT_CONSUMED`` evidence receipt is durably committed, but the
    inbox's own ``mark_consumed`` never happened before the crash — this runtime's
    :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.is_consumed` still reports ``False`` for
    it, so :mod:`tos_runtime.recovery.possibly_live` still (conservatively) counts it.

    The injected receipt uses ``outcome_digest=None`` with a
    :data:`~tos.engine.vocabulary.HaltReason.REGISTRY_MISSING` halt reason -- a genuine "the
    pipeline structurally never ran" shape (``tos_runtime.engine.replay``'s own
    ``_PIPELINE_NEVER_RAN_HALT_REASONS``), so the boot's OWN independent replay check never
    calls ``core.handle`` for it either and cannot diverge; this test's own possibly-live
    assertion depends only on the inbox's ``is_consumed``/``handling_started_receipt`` state,
    never on evidence content.
    """
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    event = fx.crossing_event(seq=1)
    event_id, seq = _mark_handling_started(runtime, event)
    del seq
    runtime.evidence_store.append(
        {
            "event_id": event_id,
            "outcome_digest": None,
            "halt_reason": HaltReason.REGISTRY_MISSING.value,
        },
        kind=_EVENT_CONSUMED_KIND,
        record_class=_EVENT_CONSUMED_KIND,
    )
    # Deliberately never call runtime.inbox.mark_consumed — this IS the crash window.

    runtime2 = _reboot(tmp_path, config_dir, data_dir, custody_root, runtime)
    _assert_held(
        runtime2, expected_event_ids={event_id}, reason_fragment="possibly-live"
    )


def test_legacy_receipt_in_window_holds_with_the_correct_reason(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    """Phase 3 carryover ⓑ: a consumed ``DECISION_TICK`` receipt with no ``flow_fingerprint``
    at all sitting in the replay window holds the barrier — even though replay itself does NOT
    diverge (the digest half still matches: the SAME real digest is reused, so
    ``verify_engine_replay_or_halt`` only flags it non-fatally as
    ``has_unverifiable_receipts``, never raises)."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    event = fx.crossing_event(seq=1)
    results = runtime.run_once((event,))
    # The driver re-stamps every event with its own yield-order coordinate before admitting it
    # (`EngineDriver._stamp`) -- read the ACTUAL admitted (stamped) event back from the inbox
    # rather than re-stamping a fresh copy here, which would derive a DIFFERENT event_id.
    admitted = list(runtime.inbox.replay())
    assert len(admitted) == 1
    event_id = event_identity(admitted[0][1], scheme=SCHEME)
    real_digest = results[0].outcome_digest
    assert real_digest is not None

    # Simulate a pre-CR6 boot's own receipt shape for the SAME event: append a SECOND
    # EVENT_CONSUMED row for the same event_id, same real digest (no divergence risk), but with
    # no flow_fingerprint at all. `_recorded_receipts`/`legacy_receipts_in_window` both key by
    # event_id off the LAST row in seq order, so this becomes "the" recorded receipt.
    runtime.evidence_store.append(
        {"event_id": event_id, "outcome_digest": real_digest},
        kind=_EVENT_CONSUMED_KIND,
        record_class=_EVENT_CONSUMED_KIND,
    )

    runtime2 = _reboot(tmp_path, config_dir, data_dir, custody_root, runtime)
    assert runtime2.driver is None
    assert runtime2.recovery.readiness_verdict is ReadinessVerdict.NOT_READY
    assert "legacy" in runtime2.recovery.reason
    with pytest.raises(RecoveryBarrierHeld):
        runtime2.run_once((fx.crossing_event(seq=999),))
    assert len(runtime2.transport.requests) == 0


def test_clean_shutdown_resumes_and_replay_digest_is_identical(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    """(g) A boot with no unresolved crash window at all resolves READY, wires a real driver,
    and the RCL replay digest is unchanged across the restart — the ordinary
    ``TestRecomposeReplay`` invariant, still held with the recovery barrier now in front of it.
    """
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    results2 = runtime.run_once((event,))
    assert results2[0].flow is not None and results2[0].flow.handed_off is True
    assert len(runtime.transport.requests) == 1

    runtime2 = _reboot(tmp_path, config_dir, data_dir, custody_root, runtime)

    assert runtime2.recovery is not None
    assert runtime2.recovery.readiness_verdict is ReadinessVerdict.READY
    assert runtime2.recovery.ready is True
    assert runtime2.driver is not None
    runtime2.rcl_log.verify_replay()  # does not raise -- identical replay digest
    # (c) still no duplicate send just from booting -- nothing was driven through runtime2 yet.
    assert len(runtime2.transport.requests) == 0
    runtime2.rcl_log.close()
    runtime2.evidence_store.close()


def test_recovery_barrier_evidence_is_recorded_before_any_new_boot_consumption(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    """(e) The ``RECOVERY_BARRIER`` evidence row exists, and — in the HELD case — no
    ``EVENT_CONSUMED`` row for the new boot is ever appended after it (the driver never runs at
    all)."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    _mark_handling_started(runtime, fx.crossing_event(seq=1))

    runtime2 = _reboot(tmp_path, config_dir, data_dir, custody_root, runtime)
    assert runtime2.driver is None

    rows = runtime2.evidence_store.connection.execute(
        "SELECT seq, kind FROM entries ORDER BY seq ASC"
    ).fetchall()
    barrier_rows = [seq for seq, kind in rows if kind == "RECOVERY_BARRIER"]
    # One RECOVERY_BARRIER row per boot (the first boot's own row is already present too) --
    # THIS boot's own row is the last one recorded.
    assert len(barrier_rows) == 2
    this_boots_barrier_seq = barrier_rows[-1]
    later_consumed = [
        seq
        for seq, kind in rows
        if kind == _EVENT_CONSUMED_KIND and seq > this_boots_barrier_seq
    ]
    assert later_consumed == []
    runtime2.rcl_log.close()
    runtime2.evidence_store.close()


def test_mutation_ignore_possibly_live_would_flip_to_ready(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    """(M1) Mutation evidence: if the barrier ignored possibly-live attempts, the exact scenario
    :func:`test_crash_after_send_evidence_holds_the_barrier` exercises would resolve READY
    instead of NOT_READY -- proving that assertion actually depends on the possibly-live
    obligation, not on an unrelated always-failing check."""
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
    from tos.sbr.predicates import obligation_graph_closed
    from tos_runtime.compose._engine_wiring import (
        ENGINE_DRIVER_CONFIG_NAME,
        load_engine_driver_config,
    )
    from tos_runtime.recovery.barrier import _build_obligations
    from tos_runtime.recovery.inputs import assemble_recovery_inputs

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    _mark_handling_started(runtime, fx.crossing_event(seq=1))
    runtime.rcl_log.close()
    runtime.evidence_store.close()

    runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
    assert runtime2.driver is None  # the real (unmutated) barrier holds

    engine_driver_config = load_engine_driver_config(
        config_dir / ENGINE_DRIVER_CONFIG_NAME
    )
    inputs = assemble_recovery_inputs(
        rcl_log=runtime2.rcl_log,
        evidence_store=runtime2.evidence_store,
        inbox=runtime2.inbox,
        scheme=get_scheme(EV_L1_PROVISIONAL_VERSION),
        window_events=engine_driver_config.replay_window_events,
        custody_root=custody_root,
        composite_state_store_path=data_dir / "composite_state.sqlite3",
        time_service=runtime2.time_service,
        account=runtime2.context_resolver.instrument_key.account,
        instrument=runtime2.context_resolver.instrument_key.instrument,
    )
    assert inputs.possibly_live_attempts != ()
    assert inputs.composite_state_incomplete_attempt_ids != ()

    # The mutation: pretend there were never any possibly-live attempts (and, since that is the
    # ONLY thing wrong with this boot's inputs, also clear the composite-state-incomplete field
    # that is a direct CONSEQUENCE of the same possibly-live attempt -- isolating the
    # possibly-live obligation specifically, not the composite-state one tested separately by
    # test_barrier.py::test_incomplete_composite_state_holds_the_barrier).
    mutated = inputs.__class__(
        **{
            **inputs.__dict__,
            "possibly_live_attempts": (),
            "composite_state_incomplete_attempt_ids": (),
        }
    )
    obligations = _build_obligations(mutated)
    assert (
        obligation_graph_closed(obligations) is True
    )  # flips to closed/READY under mutation
    runtime2.rcl_log.close()
    runtime2.evidence_store.close()


def test_mutation_release_capacity_on_hold_would_be_red(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    """(M2) Mutation evidence: if :func:`~tos_runtime.compose._recovery_wiring
    .apply_recovery_barrier` skipped its own ``runtime.driver = None`` line on a HELD verdict
    (i.e. "released capacity"/kept the driver wired anyway), every
    ``pytest.raises(RecoveryBarrierHeld)`` assertion in this file would go red. Demonstrated
    directly by constructing exactly that mutated shape (a real driver left attached to a
    NOT_READY runtime) and showing :meth:`~tos_runtime.compose._types.ComposedRuntime.run_once`
    then processes an event instead of refusing -- proving those assertions are load-bearing.
    """
    from tos_runtime.recovery import (
        LegacyReceiptFacts,
        PossiblyLiveAttempt,
        RecoveryBarrier,
    )
    from tos_runtime.recovery.inputs import RecoveryInputs

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.recovery.readiness_verdict is ReadinessVerdict.READY
    assert runtime.driver is not None

    not_ready_inputs = RecoveryInputs(
        rcl_writer_epoch=runtime.rcl_log.current_epoch(),
        rcl_runtime_generation=runtime.rcl_log.latest_runtime_generation(),
        open_reservations=(),
        evidence_tip_seq=1,
        evidence_tip_key_generation=1,
        legacy_receipts=LegacyReceiptFacts(count=0, event_ids=()),
        inbox_unconsumed_count=0,
        possibly_live_attempts=(
            PossiblyLiveAttempt(
                event_id="mutation-drill",
                inbox_seq=1,
                handling_started_evidence_seq=1,
                handling_started_generation=1,
            ),
        ),
        composite_state_incomplete_attempt_ids=("mutation-drill",),
        custody_environment_label="non-live-test",
        custody_manifest_digest="a" * 64,
    )
    held_verdict = RecoveryBarrier.verdict(not_ready_inputs)
    assert held_verdict.readiness_verdict is ReadinessVerdict.NOT_READY

    # The mutation itself: stamp the HELD verdict but deliberately do NOT clear `driver` (the
    # one line `apply_recovery_barrier` uses to make "never release, never re-arm" structural).
    runtime.recovery = held_verdict
    results = runtime.run_once((fx.crossing_event(seq=777),))
    assert (
        results  # under the real (unmutated) code this object is never reachable at all
    )


def test_mutation_treat_legacy_receipts_as_fingerprinted_would_be_red(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    """(M3) Mutation evidence: if the legacy-receipt gate treated every receipt as fingerprinted
    (i.e. always reported ``LegacyReceiptFacts(count=0, ...)``), the EXACT scenario
    :func:`test_legacy_receipt_in_window_holds_with_the_correct_reason` exercises would resolve
    READY instead of NOT_READY."""
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
    from tos.sbr.predicates import obligation_graph_closed
    from tos_runtime.compose._engine_wiring import (
        ENGINE_DRIVER_CONFIG_NAME,
        load_engine_driver_config,
    )
    from tos_runtime.recovery.barrier import _build_obligations
    from tos_runtime.recovery.inputs import assemble_recovery_inputs
    from tos_runtime.recovery.legacy_receipts import LegacyReceiptFacts

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    event = fx.crossing_event(seq=1)
    results = runtime.run_once((event,))
    admitted = list(runtime.inbox.replay())
    event_id = event_identity(admitted[0][1], scheme=SCHEME)
    real_digest = results[0].outcome_digest
    assert real_digest is not None
    runtime.evidence_store.append(
        {"event_id": event_id, "outcome_digest": real_digest},
        kind=_EVENT_CONSUMED_KIND,
        record_class=_EVENT_CONSUMED_KIND,
    )
    runtime.rcl_log.close()
    runtime.evidence_store.close()

    runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
    assert runtime2.driver is None  # the real (unmutated) gate holds

    engine_driver_config = load_engine_driver_config(
        config_dir / ENGINE_DRIVER_CONFIG_NAME
    )
    inputs = assemble_recovery_inputs(
        rcl_log=runtime2.rcl_log,
        evidence_store=runtime2.evidence_store,
        inbox=runtime2.inbox,
        scheme=get_scheme(EV_L1_PROVISIONAL_VERSION),
        window_events=engine_driver_config.replay_window_events,
        custody_root=custody_root,
        composite_state_store_path=data_dir / "composite_state.sqlite3",
        time_service=runtime2.time_service,
        account=runtime2.context_resolver.instrument_key.account,
        instrument=runtime2.context_resolver.instrument_key.instrument,
    )
    assert inputs.legacy_receipts.count == 1

    # The mutation: pretend the legacy-receipt gate always reports "none found".
    mutated = inputs.__class__(
        **{
            **inputs.__dict__,
            "legacy_receipts": LegacyReceiptFacts(count=0, event_ids=()),
        }
    )
    obligations = _build_obligations(mutated)
    assert (
        obligation_graph_closed(obligations) is True
    )  # flips to closed/READY under mutation
    runtime2.rcl_log.close()
    runtime2.evidence_store.close()


def test_negative_grep_no_operator_override_or_ambient_input_in_recovery_package() -> (
    None
):
    """No ``operator_ok``/``assume``/``force``-named FUNCTION PARAMETER, no ``os.environ``, no
    ``time.time``/``datetime.now`` anywhere in :mod:`tos_runtime.recovery` (plan §2 decision 2:
    "전부 구조 파생, 운영자 «정상» 선언 입력 0") or :mod:`tos_runtime.compose._recovery_wiring`.

    Parses each module's AST and inspects actual function PARAMETER names only -- a call-site
    keyword argument (e.g. ``recovery_authority_separated(effect, forced_ready_requested=False)``,
    a hardcoded ``False`` passed to a KERNEL predicate) is not an operator-override input this
    module accepts, so a naive text grep over ``name=`` would false-positive on it.
    """
    import ast
    from pathlib import Path

    import tos_runtime.compose._recovery_wiring as recovery_wiring_module
    import tos_runtime.recovery as recovery_pkg

    package_dir = Path(recovery_pkg.__file__).parent
    sources = list(package_dir.glob("*.py")) + [Path(recovery_wiring_module.__file__)]
    assert sources, "expected at least the recovery package + _recovery_wiring.py"

    forbidden_names = ("operator_ok", "assume", "force")

    for path in sources:
        text = path.read_text(encoding="utf-8")
        # Actual USAGE forms only -- a docstring disclaiming ambient input (e.g.
        # "no ambient ``os.environ``.") legitimately names these tokens without ever writing the
        # subscript/call forms that would constitute real usage.
        assert "os.environ[" not in text, f"{path} touches os.environ"
        assert "os.environ.get(" not in text, f"{path} touches os.environ"
        assert "os.getenv(" not in text, f"{path} touches os.getenv"
        assert "time.time(" not in text, f"{path} reads the wall clock directly"
        assert "datetime.now(" not in text, f"{path} reads the wall clock directly"

        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            all_params = (
                node.args.posonlyargs
                + node.args.args
                + node.args.kwonlyargs
                + ([node.args.vararg] if node.args.vararg else [])
                + ([node.args.kwarg] if node.args.kwarg else [])
            )
            for param in all_params:
                lowered = param.arg.lower()
                for forbidden in forbidden_names:
                    assert forbidden not in lowered, (
                        f"{path}::{node.name} has parameter {param.arg!r} -- looks like an "
                        "operator-override input"
                    )


def test_reconciliation_runs_the_real_service_but_cannot_clear_an_unmatched_attempt(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    """Once ``tos_runtime.recon`` landed a real ``EvidenceReceiptReader`` adapter
    (``tos_runtime.recon.evidence_reader.SqliteEvidenceReceiptReader``, TOS Phase 5 W1 close-out
    GAP 1), :mod:`tos_runtime.recovery.inputs` runs one real
    :meth:`~tos_runtime.recon.service.ReconciliationService.reconcile` call per boot (module
    docstring: "one scope, one report, applied uniformly") whenever a possibly-live attempt
    exists — not merely a documented ``RECON_UNAVAILABLE`` short-circuit. This test injects an
    ``EGRESS_RESULT_CONSUMED`` receipt for an unrelated attempt into the SAME account/instrument
    scope so the service genuinely has something to read from all three ports, and asserts the
    real call still cannot clear the possibly-live attempt: the injected receipt has no RCL
    reservation, no broker-witness order beyond what the SAME evidence store already gives (the
    disclosed independence caveat), so ``ReconciliationClass.MATCHED`` is never reached and
    ``permits_capacity_release``/``permits_rearm`` stay ``False`` -- the barrier still holds.
    """
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    event_id, _seq = _mark_handling_started(runtime, fx.crossing_event(seq=1))
    instrument_key = runtime.context_resolver.instrument_key
    runtime.evidence_store.append(
        {
            "instrument_key": {
                "account": instrument_key.account,
                "instrument": instrument_key.instrument,
            },
            "attempt_id": "attempt-reconciliation-drill",
            "egress_result_kind": "FULL_FILL",
            "filled_quantity": "1",
            "remaining_quantity": "0",
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )

    runtime2 = _reboot(tmp_path, config_dir, data_dir, custody_root, runtime)

    _assert_held(
        runtime2, expected_event_ids={event_id}, reason_fragment="possibly-live"
    )
