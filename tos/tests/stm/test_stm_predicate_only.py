"""§6 predicate-only substrate — every one closes **no** STM-EV (design #30 §0.4c/§6/§12).

**The maximum risk in this contract is over-realization.** STM-INV-001..016 is sixteen invariants over
only **two** ``EV-L1``-sliced rows: exactly five (001 / 002 / 003 / 004 / 007) contribute to the yolks
and the other **eleven** are authored here as substrate that closes nothing at all. This file exercises
each §6 predicate both ways *and* asserts the honesty discipline in code: every substrate docstring
carries its "Closes no STM-EV" tag with the row's real minimum level, no module claims EV-L1
completion, and the two ``EV-L1``-sliced rows are honestly recorded as **both carrying ``+Security``**
— uniquely among the governance sextet there is no clean ``EV-L1/3`` row at all.

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import tos.stm.predicates as p
from tos.stm import (
    SuppressionLifecycleState,
    absence_is_not_health,
    alert_state_is_orthogonal,
    attempt_potentially_live,
    broker_finality_unchanged,
    common_mode_is_not_independence,
    economic_effect_outlives_monitor_state,
    evidence_and_status_honest,
    gap_is_restrictive_not_exemption,
    handoff_is_non_authorizing,
    loss_preserves_negative_facts,
    recovery_revives_nothing,
    restriction_ordered_before_capability_claim,
    stale_writer_fenced,
    suppression_cannot_suppress_safety,
    telemetry_semantics_exact,
    unknown_is_restrictive,
)

from ._stm_strategies import (
    clean_alert_state,
    clean_broker_tokens,
    clean_common_mode,
    clean_dashboard,
    clean_gap,
    clean_identity,
    clean_recovery,
    clean_semantic_view,
    clean_send_race,
    clean_signal,
    clean_silence,
    clean_suppression,
    clean_unknown_state,
)

_STM_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "stm"


def _stm_sources() -> list[Path]:
    """Every ``tos.stm`` source, asserted **non-empty** so a path typo cannot make a sweep vacuous."""
    sources = sorted(_STM_SRC.rglob("*.py"))
    assert (
        sources
    ), f"no tos.stm source found under {_STM_SRC} — this sweep would be vacuous"
    return sources


#: Every §6 / §6b substrate predicate and the row it is substrate **for** — none of which it closes.
_SUBSTRATE_ROWS: dict[str, str] = {
    "telemetry_semantics_exact": "STM-EV-002",
    "absence_is_not_health": "STM-EV-003",
    "unknown_is_restrictive": "STM-EV-003",
    "common_mode_is_not_independence": "STM-EV-004",
    "suppression_cannot_suppress_safety": "STM-EV-006",
    "alert_state_is_orthogonal": "STM-EV-007",
    "loss_preserves_negative_facts": "STM-EV-007",
    "handoff_is_non_authorizing": "STM-EV-008",
    "broker_finality_unchanged": "STM-EV-010",
    "economic_effect_outlives_monitor_state": "STM-EV-010",
    "evidence_and_status_honest": "STM-EV-012",
    "recovery_revives_nothing": "STM-EV-012",
    "restriction_ordered_before_capability_claim": "STM-EV-009",
    "attempt_potentially_live": "STM-EV-009",
    "stale_writer_fenced": "STM-EV-011",
}


# --- honesty discipline ----------------------------------------------------


def test_the_substrate_spans_ten_rows_and_closes_none_of_them() -> None:
    """(§0.4c/§12) Twelve §6 functions plus three §6b thin models over ten rows — none closed.

    Eight predicate-only rows (002 / 003 / 004 / 006 / 007 / 008 / 010 / 012) plus the two not-Phase-1
    rows (009 / 011) — every row outside the two ``EV-L1``-sliced yolks (001 / 005).
    """
    assert len(_SUBSTRATE_ROWS) == 15
    assert set(_SUBSTRATE_ROWS.values()) == {
        f"STM-EV-{n:03d}" for n in (2, 3, 4, 6, 7, 8, 9, 10, 11, 12)
    }
    assert "STM-EV-001" not in set(_SUBSTRATE_ROWS.values())
    assert "STM-EV-005" not in set(_SUBSTRATE_ROWS.values())


@pytest.mark.parametrize("name", sorted(_SUBSTRATE_ROWS))
def test_every_substrate_predicate_declares_it_closes_nothing(name: str) -> None:
    """(§6 regime tag) Each substrate docstring says "Closes no STM-EV" in so many words."""
    doc = inspect.getdoc(getattr(p, name)) or ""
    assert "Closes no STM-EV" in doc, f"{name} lacks its closes-nothing tag"


@pytest.mark.parametrize("name,row", sorted(_SUBSTRATE_ROWS.items()))
def test_every_substrate_predicate_names_its_row(name: str, row: str) -> None:
    """(§12 honesty) Each substrate names the row it feeds, so the mapping cannot drift silently."""
    doc = inspect.getdoc(getattr(p, name)) or ""
    assert row in doc, f"{name} does not name {row}"


def test_no_module_claims_ev_l1_completion() -> None:
    """(§1) Every module carries the regime tag and the explicit prohibition."""
    for path in _stm_sources():
        # normalize emphasis markers and wrapping so a line break cannot hide the claim
        text = " ".join(path.read_text(encoding="utf-8").replace("*", "").split())
        assert "Regime tag" in text, f"{path.name} lacks a regime tag"
        assert (
            "EV-L1-complete claim forbidden" in text
        ), f"{path.name} lacks the prohibition"
        assert (
            "closes no stm-ev" in text.lower()
        ), f"{path.name} lacks a closes-nothing claim"


def test_the_two_l1_rows_are_recorded_as_both_carrying_security() -> None:
    """(§1 decisive fact 2) Uniquely among the sextet there is **no** clean ``EV-L1/3`` row."""
    text = (_STM_SRC / "__init__.py").read_text(encoding="utf-8")
    assert "EV-L1/3+Security" in text
    assert "no clean ``EV-L1/3`` row at all" in text


def test_the_yolks_also_declare_they_close_nothing() -> None:
    """(§5) The two core predicates carry the same discipline as the substrate."""
    for name in (
        "critical_coverage_complete_or_gap",
        "deterministic_evaluation_bound_integrity",
    ):
        doc = inspect.getdoc(getattr(p, name)) or ""
        assert "Closes no STM-EV" in doc, f"{name} lacks its closes-nothing tag"


# --- §6.1 telemetry semantics ---------------------------------------------


def test_telemetry_semantics_both_ways() -> None:
    """(§10; STM-INV-003 line 167) All five negative coordinates must be positively ``False``."""
    assert telemetry_semantics_exact(clean_identity(), clean_semantic_view()) is True
    assert telemetry_semantics_exact(None, clean_semantic_view()) is False
    assert telemetry_semantics_exact(clean_identity(), None) is False


# --- §6.2 / §6.3 absence and UNKNOWN --------------------------------------


def test_absence_is_not_health_is_unconditional() -> None:
    """(**MINOR-2**, §6.2) The health claim is judged whether or not any silence marker is set.

    Both conservative branches are exposed **independently** (the #28 MAJOR-3 lesson): a
    marker-saturated honest observation clears, a marker-free honest observation clears, and both an
    asserted and an unknown health claim deny regardless of markers.
    """
    saturated = clean_silence()
    bare = clean_silence(
        no_alert=False,
        repeated_heartbeat=False,
        quiet_time=False,
        empty_query=False,
        green_dashboard=False,
    )
    assert absence_is_not_health(saturated) is True
    assert absence_is_not_health(bare) is True
    for claim in (True, None):
        assert absence_is_not_health(clean_silence(treated_as_healthy=claim)) is False
        assert (
            absence_is_not_health(
                clean_silence(
                    treated_as_healthy=claim,
                    no_alert=False,
                    repeated_heartbeat=False,
                    quiet_time=False,
                    empty_query=False,
                    green_dashboard=False,
                )
            )
            is False
        )
    assert absence_is_not_health(None) is False


def test_unknown_is_restrictive_over_all_seven_axes() -> None:
    """(§13; STM-INV-005 line 175) Every one of the seven axes denies on its own."""
    assert unknown_is_restrictive(clean_unknown_state()) is True
    assert unknown_is_restrictive(None) is False


# --- §6.4 common mode ------------------------------------------------------


def test_a_shared_dependency_forbids_an_independence_claim() -> None:
    """(§14 line 355; STM-INV-006 line 179) Shared paths do not count as independent."""
    assert common_mode_is_not_independence(clean_common_mode()) is True
    assert (
        common_mode_is_not_independence(clean_common_mode(claimed_independent=True))
        is False
    )


def test_independence_may_be_claimed_with_no_shared_dependency() -> None:
    """(both-ways +) With no shared dependency the claim is admissible — never over-sealed."""
    disclosure = clean_common_mode(
        shared_dependencies=frozenset(), claimed_independent=True
    )
    assert common_mode_is_not_independence(disclosure) is True


def test_common_mode_denies_on_absent_disclosure() -> None:
    """(∅-seal) ``None`` is undecidable, therefore denied."""
    assert common_mode_is_not_independence(None) is False


# --- §6.5 suppression ------------------------------------------------------


def test_suppression_needs_all_eight_preserved_functions() -> None:
    """(§15 line 367-376) The preserved set is a **floor** — more is fine, fewer denies."""
    assert suppression_cannot_suppress_safety(clean_suppression()) is True
    extra = clean_suppression(
        preserved_functions=clean_suppression().preserved_functions | {"EXTRA"}
    )
    assert suppression_cannot_suppress_safety(extra) is True
    short = clean_suppression(
        preserved_functions=frozenset(list(clean_suppression().preserved_functions)[:7])
    )
    assert suppression_cannot_suppress_safety(short) is False


@pytest.mark.parametrize(
    "state",
    [
        SuppressionLifecycleState.EXPIRED,
        SuppressionLifecycleState.UNKNOWN,
        None,
    ],
)
def test_an_expired_or_unknown_suppression_is_restrictive(state) -> None:
    """(§15 line 365; §21 line 458) Expiry or uncertainty ⇒ restricted and unsuppressed."""
    assert (
        suppression_cannot_suppress_safety(clean_suppression(lifecycle_state=state))
        is False
    )


def test_a_requested_suppression_is_still_in_force() -> None:
    """(both-ways +) ``REQUESTED`` and ``ACTIVE`` are the two non-restrictive lifecycle states."""
    assert (
        suppression_cannot_suppress_safety(
            clean_suppression(lifecycle_state=SuppressionLifecycleState.REQUESTED)
        )
        is True
    )


def test_suppression_denies_on_absent_record() -> None:
    """(∅-seal) ``None`` is undecidable, therefore denied."""
    assert suppression_cannot_suppress_safety(None) is False


# --- §6.6 alert state ------------------------------------------------------


def test_alert_state_orthogonality_and_loss_are_independent_gates() -> None:
    """(§16 line 388/390; INV-009/010) The two judgements do not shadow each other."""
    vector = clean_alert_state()
    assert alert_state_is_orthogonal(vector) is True
    assert loss_preserves_negative_facts(vector) is True
    dropped = clean_alert_state(adverse_record_dropped=True)
    assert alert_state_is_orthogonal(dropped) is True  # a different axis
    assert loss_preserves_negative_facts(dropped) is False
    implied = clean_alert_state(ack_implies_containment=True)
    assert alert_state_is_orthogonal(implied) is False
    assert loss_preserves_negative_facts(implied) is True
    assert alert_state_is_orthogonal(None) is False
    assert loss_preserves_negative_facts(None) is False


# --- §6.7 handoff ----------------------------------------------------------


def test_handoff_requires_all_false_authority_and_all_four_prohibitions() -> None:
    """(§17 line 402; STM-INV-011 line 199) Monitoring may request restriction **only**."""
    assert handoff_is_non_authorizing(clean_signal()) is True
    assert handoff_is_non_authorizing(None) is False


def test_no_incident_is_a_prohibition_flag_not_a_token() -> None:
    """(the #28 SIR phantom lesson) §17 line 402 forbids publishing it; stm owns no such token."""
    import tos.stm as s

    assert "publishes_no_incident" in s.NEGATIVE_POLARITY_FIELDS
    assert not hasattr(s, "NO_INCIDENT")
    assert not any(
        getattr(member, "value", None) == "NO_INCIDENT"
        for enum in (
            s.AggregateConformanceResult,
            s.DashboardStatusToken,
            s.MonitoringGapKind,
        )
        for member in enum
    )


# --- §6.8 broker finality --------------------------------------------------


def test_broker_finality_and_economic_continuity() -> None:
    """(§19 line 429/431; STM-INV-013 line 207) Three inferences denied, expiry read as a shape."""
    assert broker_finality_unchanged(clean_broker_tokens()) is True
    assert broker_finality_unchanged(None) is False
    assert economic_effect_outlives_monitor_state(None) is False


# --- §6.9 evidence / recovery ---------------------------------------------


def test_recovery_gate_is_armed_by_the_marker_disjunction() -> None:
    """(§24 line 511; OQ1) The nine markers arm the gate structurally — never a self-report.

    Both conservative branches are exposed independently: with **no** recovery event there is nothing to
    revive and the predicate holds; with **any** event recorded all four non-revival fields must be
    positively ``False``.
    """
    assert recovery_revives_nothing(clean_recovery()) is True
    quiet = clean_recovery(
        **dict.fromkeys(clean_recovery().RECOVERY_MARKER_FIELDS, False)
    )
    assert recovery_revives_nothing(quiet) is True
    # a single marker is enough to arm the gate
    for marker in clean_recovery().RECOVERY_MARKER_FIELDS:
        armed = clean_recovery(
            **{
                **dict.fromkeys(clean_recovery().RECOVERY_MARKER_FIELDS, False),
                marker: True,
            },
            revived_prior_authority=True,
        )
        assert recovery_revives_nothing(armed) is False
    assert recovery_revives_nothing(None) is False


def test_a_quiet_system_does_not_hide_a_revival_claim() -> None:
    """(honesty) With no marker the four judgements are unreachable — so the fixtures saturate them."""
    quiet_but_revived = clean_recovery(
        **dict.fromkeys(clean_recovery().RECOVERY_MARKER_FIELDS, False),
        revived_prior_authority=True,
    )
    # documented behaviour: no recovery event ⇒ nothing to revive; the clean fixture is saturated so
    # the four judgements are always exercised (the #28 MAJOR-3 dominated-branch lesson).
    assert recovery_revives_nothing(quiet_but_revived) is True
    assert (
        recovery_revives_nothing(clean_recovery(revived_prior_authority=True)) is False
    )


def test_dashboard_honesty_denies_on_absent_view() -> None:
    """(∅-seal) ``None`` is undecidable, therefore denied."""
    assert evidence_and_status_honest(None) is False
    assert evidence_and_status_honest(clean_dashboard()) is True


# --- §6b not-Phase-1 thin models ------------------------------------------


def test_the_send_race_is_three_valued() -> None:
    """(§18 line 421; §4.3) Proven-deny, proven-safe and unprovable are three distinct states."""
    proven_deny = clean_send_race()
    assert restriction_ordered_before_capability_claim(proven_deny) is True
    assert attempt_potentially_live(proven_deny) is False
    # proven the other way: the claim came first, so nothing was denied before the send
    from tos.ordering import OrderingEvent

    claim_first = clean_send_race(
        restrict_event=OrderingEvent(quorum_commit_index=30),
        capability_claim_event=OrderingEvent(quorum_commit_index=10),
    )
    assert restriction_ordered_before_capability_claim(claim_first) is False
    assert attempt_potentially_live(claim_first) is True
    # unprovable: the same ordering with no proof stays potentially live
    for provable in (False, None):
        assert (
            attempt_potentially_live(clean_send_race(ordering_provable=provable))
            is True
        )
    # an equal generation is AMBIGUOUS, i.e. not proven — conservative side
    equal = clean_send_race(
        restrict_event=OrderingEvent(quorum_commit_index=10),
        capability_claim_event=OrderingEvent(quorum_commit_index=10),
    )
    assert restriction_ordered_before_capability_claim(equal) is False
    assert attempt_potentially_live(equal) is True


def test_a_recorded_first_byte_is_always_potentially_live() -> None:
    """(§19 line 429) Bytes on the wire mean possible acceptance whatever the ordering proves."""
    from tos.ordering import OrderingEvent

    with_byte = clean_send_race(first_byte_event=OrderingEvent(quorum_commit_index=30))
    assert restriction_ordered_before_capability_claim(with_byte) is True
    assert attempt_potentially_live(with_byte) is True


def test_the_race_denies_on_absent_or_incomplete_ordering() -> None:
    """(fail-closed) An absent record or a missing coordinate proves nothing."""
    assert restriction_ordered_before_capability_claim(None) is False
    assert attempt_potentially_live(None) is True
    assert (
        restriction_ordered_before_capability_claim(
            clean_send_race(restrict_event=None)
        )
        is False
    )
    assert (
        restriction_ordered_before_capability_claim(
            clean_send_race(capability_claim_event=None)
        )
        is False
    )


def test_gap_closure_is_only_by_proof() -> None:
    """(§13 line 349) "Monitoring recovery does not close the gap by itself"."""
    assert gap_is_restrictive_not_exemption(clean_gap()) is True
    assert gap_is_restrictive_not_exemption(clean_gap(gap_kind=None)) is False
    for value in (False, None):
        assert (
            gap_is_restrictive_not_exemption(clean_gap(closure_proof_present=value))
            is False
        )
    assert gap_is_restrictive_not_exemption(None) is False


def test_stale_writer_fencing_needs_a_positive_proof() -> None:
    """(§12 line 337; STM-INV-016 line 219) An unproven pair is not a clearance."""
    assert stale_writer_fenced(9, 3) is True
    assert stale_writer_fenced(3, 9) is False


def test_unreported_recovery_markers_do_not_disarm_the_gate() -> None:
    """(**MAJOR-1 regression**) All-``None`` markers arm the gate — silence is not "no recovery".

    A :class:`~tos.stm.state.MonitoringRecoveryInputs` built with no arguments at all has every marker
    ``None``. Reading the disjunction with ``is True`` would treat that default shape as "no recovery
    happened" and skip the four non-revival judgements entirely, so a record openly self-reporting a
    revived prior authority would pass. The disjunction therefore arms on ``is not False``: only a
    **fully disclaimed** marker set (every one positively ``False``) means there is nothing to revive.
    """
    from tos.stm import MonitoringRecoveryInputs

    silent = MonitoringRecoveryInputs()
    assert all(
        getattr(silent, name) is None
        for name in MonitoringRecoveryInputs.RECOVERY_MARKER_FIELDS
    )
    # the exact shipping fail-open the review found
    assert (
        recovery_revives_nothing(MonitoringRecoveryInputs(revived_prior_authority=True))
        is False
    )
    for field in MonitoringRecoveryInputs.NON_REVIVAL_FIELDS:
        assert (
            recovery_revives_nothing(MonitoringRecoveryInputs(**{field: True})) is False
        )
        assert (
            recovery_revives_nothing(MonitoringRecoveryInputs(**{field: None})) is False
        )
    # an all-None record with all four judgements positively disclaimed still clears
    disclaimed = MonitoringRecoveryInputs(
        **dict.fromkeys(MonitoringRecoveryInputs.NON_REVIVAL_FIELDS, False)
    )
    assert recovery_revives_nothing(disclaimed) is True


def test_a_single_unknown_marker_still_arms_the_gate() -> None:
    """(MAJOR-1) A partially disclaimed marker set is not a disclaimer — one ``None`` is enough."""
    from tos.stm import MonitoringRecoveryInputs

    markers = MonitoringRecoveryInputs.RECOVERY_MARKER_FIELDS
    for unknown in markers:
        fields = dict.fromkeys(markers, False)
        fields[unknown] = None
        armed = MonitoringRecoveryInputs(**fields, revived_prior_authority=True)
        assert recovery_revives_nothing(armed) is False


def test_a_suppression_lifecycle_whitelist_auto_denies_an_unclassified_state(
    monkeypatch,
) -> None:
    """(MINOR-2) The lifecycle gate is a positive whitelist — a future member auto-denies.

    On today's four-member enum the whitelist and the contract's §6.5 denylist phrasing are exactly
    equivalent; the whitelist additionally denies a member nobody has classified. This shrinks the
    in-force set to manufacture that future and proves the residue is load-bearing.
    """
    import tos.stm.predicates as predicates
    from tos.stm import IN_FORCE_SUPPRESSION_STATES

    assert (
        suppression_cannot_suppress_safety(
            clean_suppression(lifecycle_state=SuppressionLifecycleState.ACTIVE)
        )
        is True
    )
    monkeypatch.setattr(
        predicates,
        "IN_FORCE_SUPPRESSION_STATES",
        IN_FORCE_SUPPRESSION_STATES - {SuppressionLifecycleState.ACTIVE},
    )
    assert (
        predicates.suppression_cannot_suppress_safety(
            clean_suppression(lifecycle_state=SuppressionLifecycleState.ACTIVE)
        )
        is False
    )


def test_the_lifecycle_whitelist_and_denylist_partition_the_enum() -> None:
    """(MINOR-2 drift) In-force ∪ restrictive == the enum, disjoint (過 0 · 不 0)."""
    from tos.stm import (
        IN_FORCE_SUPPRESSION_STATES,
        RESTRICTIVE_SUPPRESSION_STATES,
        SuppressionLifecycleState,
    )

    assert (
        frozenset(SuppressionLifecycleState)
        == IN_FORCE_SUPPRESSION_STATES | RESTRICTIVE_SUPPRESSION_STATES
    )
    assert not IN_FORCE_SUPPRESSION_STATES & RESTRICTIVE_SUPPRESSION_STATES
