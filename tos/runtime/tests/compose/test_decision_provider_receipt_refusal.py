"""``tos_runtime.compose._wiring._decision_provider`` tests (kernel round #1
§2.2 re-review finding #7, LOW).

``_decision_provider`` swallows ``OperatorApprovalFileError`` into ``None``
(fail-closed — the sequencer must never see an exception here, module
docstring's "zero auto-approval"), but that swallow previously left an
operator's own MALFORMED/REFUSED approval file completely invisible: the
same ``None`` as the ordinary "no decision authored yet" case. This module
proves the fix — a refusal now appends one ``IAP_APPROVAL_FILE_REFUSED``
evidence record (naming the path and the refusal text) before returning
``None`` — and that an ordinary MISSING file (never refused, just not
authored yet) records nothing, preserving that distinction.

Hermetic, following this package's own established pattern of unit-testing
one ``_wiring`` private function directly against real collaborators it
does not itself construct (see ``test_time_permits_new_risk.py`` /
``test_rcl_tip_generation_provider.py``) — a real
:func:`tos_runtime.authority.iap.load_operator_approval_with_receipt` call
against a REAL custody-mode violation (never mocked: the failure mode under
test is the real custody gate's real refusal), with only the time service
and evidence port duck-typed doubles.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import Proposal
from tos.dsl.proposal import DecisionContextCapsuleRef, Proposer
from tos.engine.records import InstrumentKey, StageRequest
from tos.engine.vocabulary import CommitmentStep
from tos_runtime.compose._wiring import _decision_provider
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TimeServiceNotStarted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


class _NeverStartedTimeService:
    """Duck-typed double. Never actually reached by either test below — the
    custody mode/owner gate refuses (or the file is simply absent) strictly
    before any receipt work starts (module docstring's own "checks run
    before the file is opened" discipline, shared with ``FileCustody``)."""

    def current_snapshot(self) -> None:
        raise TimeServiceNotStarted("unused by this test")


class _RecordingEvidencePort:
    """A minimal evidence-port double recording every ``append`` call
    verbatim — this test exercises ``_decision_provider``'s OWN refusal-
    visibility behavior, not the real durable evidence chain."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, object], str, str]] = []

    def append(
        self, payload: dict[str, object], *, kind: str, record_class: str
    ) -> None:
        self.calls.append((dict(payload), kind, record_class))


def _time_config() -> TrustworthyTimeConfig:
    return TrustworthyTimeConfig(
        max_time_source_precision_ms=5,
        max_time_transport_and_queue_uncertainty_ms=10,
        max_time_conservative_freshness_age_ms=1000,
        max_future_timestamp_tolerance_ms=200,
        max_process_suspension_ms=0,
        max_time_source_disagreement_ms=50,
        min_time_independent_reference_count=1,
        max_clock_domain_conversion_uncertainty_ms=50,
        max_send_result_wait_ms=5000,
        tz_db_version="2026a",
        trading_calendar_version="cal-1",
        verification_profile_version="vp-0",
        safety_profile_version="sp-0",
    )


def _issued_proposal() -> Proposal:
    """A minimally-valid, digest-verified :class:`Proposal` built directly
    via :meth:`Proposal.issue` — a real, non-DSL-driven digest is sufficient
    for ``_decision_provider``'s own resolution logic (it only ever reads
    ``proposal.canonical_digest``)."""
    scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
    issued = Proposal.issue(
        scheme=scheme,
        proposer=Proposer(strategy_id="s1", strategy_version="v1"),
        account="acct-1",
        instrument="ISU1",
        direction="LONG",
        position_effect="OPEN",
        quantity_basis="qb",
        rationale="r",
        decision_context_capsule=DecisionContextCapsuleRef(
            capsule_id="c1", canonical_digest="capdig"
        ),
        dsl_version="dv1",
        config_version="cv1",
    )
    assert isinstance(issued, Proposal)
    return issued


def _request(proposal: Proposal) -> StageRequest:
    return StageRequest(
        step=CommitmentStep.INDEPENDENT_APPROVAL,
        instrument_key=InstrumentKey(account="acct-1", instrument="ISU1"),
        proposal=proposal,
    )


def test_a_refused_approval_file_is_recorded_before_returning_none(
    tmp_path: Path,
) -> None:
    proposal = _issued_proposal()
    approvals_dir = tmp_path / "approvals"
    approvals_dir.mkdir()
    path = approvals_dir / f"{proposal.canonical_digest}.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "environment_label": "non-live-test",
                "decision_id": "d1",
                "decision_generation": 1,
                "result": "APPROVE",
            }
        )
    )
    os.chmod(path, 0o644)  # wrong mode -- the custody gate refuses this

    evidence = _RecordingEvidencePort()
    provider = _decision_provider(
        tmp_path,
        "non-live-test",
        os.getuid(),
        _NeverStartedTimeService(),
        _time_config(),
        evidence,
    )

    result = provider(_request(proposal))

    assert result is None
    assert len(evidence.calls) == 1
    payload, kind, record_class = evidence.calls[0]
    assert kind == "IAP_APPROVAL_FILE_REFUSED"
    assert record_class == "IAP_APPROVAL_FILE_REFUSED"
    assert payload["path"] == str(path)
    assert "mode" in payload["error"]


def test_a_missing_approval_file_records_nothing(tmp_path: Path) -> None:
    """The ordinary "operator has not authored a decision yet" case (module
    docstring's own zero-auto-approval discipline) must never be confused
    with a refused/malformed file — nothing is durably recorded."""
    proposal = _issued_proposal()
    (tmp_path / "approvals").mkdir()
    evidence = _RecordingEvidencePort()
    provider = _decision_provider(
        tmp_path,
        "non-live-test",
        os.getuid(),
        _NeverStartedTimeService(),
        _time_config(),
        evidence,
    )

    result = provider(_request(proposal))

    assert result is None
    assert evidence.calls == []
