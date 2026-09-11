"""``GatewayEvidenceRecord.send_seal`` / ``send_seal_digest`` kind pairing (independent review
finding #9).

Before ``_seal_fields_match_their_kind`` (``tos/src/tos/egressgw/records.py``), ``kind`` was a
free-form ``str`` and nothing enforced which kinds may legitimately carry the whole seal or its
digest — only a field comment asserted it. The reviewer's own probe,
``GatewayEvidenceRecord(kind="SEND_REFUSED", attempt_id="a", send_seal_digest="deadbeef")``,
constructed without error.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.egressgw import (
    GatewayEvidenceRecord,
    SendSeal,
    build_send_seal,
    outbound_coordinates,
)
from tos.engine import CommitmentStep

from ._egressgw_fixtures import SCHEME, happy_context


def _a_seal() -> SendSeal:
    attempt, context = happy_context()
    return build_send_seal(
        context=context,
        attempt=attempt,
        coordinates=outbound_coordinates(context),
        scheme=SCHEME,
    )


def test_send_seal_digest_is_rejected_on_a_kind_that_never_legitimately_carries_it() -> (
    None
):
    """(independent review finding #9) The reviewer's own probe now raises."""
    with pytest.raises(ValidationError, match="send_seal_digest"):
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            attempt_id="a",
            send_seal_digest="deadbeef",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
        )


def test_send_seal_is_rejected_on_a_kind_other_than_send_sealed() -> None:
    """The full seal is legitimate only on the ``SEND_SEALED`` record."""
    seal = _a_seal()
    with pytest.raises(ValidationError, match="send_seal"):
        GatewayEvidenceRecord(
            kind="SEND_STARTED",
            attempt_id="a",
            send_seal=seal,
            step=CommitmentStep.SEND_STARTED_DURABLE,
        )


@pytest.mark.parametrize(
    ("kind", "step"),
    [
        ("SEND_STARTED", CommitmentStep.SEND_STARTED_DURABLE),
        ("EGRESS_RESULT_RECORDED", CommitmentStep.EVIDENCE_RECORD),
    ],
)
def test_send_seal_digest_is_accepted_on_the_kinds_the_gateway_actually_stamps_it_onto(
    kind: str, step: CommitmentStep
) -> None:
    """(independent review finding #9) ``gateway.py``'s own ``send_seal_digest=`` call sites."""
    seal = _a_seal()
    record = GatewayEvidenceRecord(
        kind=kind, attempt_id="a", send_seal_digest=seal.seal_digest, step=step
    )
    assert record.send_seal_digest == seal.seal_digest


def test_send_seal_is_accepted_on_send_sealed() -> None:
    seal = _a_seal()
    record = GatewayEvidenceRecord(
        kind="SEND_SEALED",
        attempt_id="a",
        send_seal=seal,
        step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
    )
    assert record.send_seal is seal


def test_send_seal_digest_is_rejected_on_send_sealed_itself() -> None:
    """(design §1.2) ``SEND_SEALED`` carries the whole seal, not its digest — the digest belongs
    to the later ``SEND_STARTED`` / ``EGRESS_RESULT_RECORDED`` records only."""
    seal = _a_seal()
    with pytest.raises(ValidationError, match="send_seal_digest"):
        GatewayEvidenceRecord(
            kind="SEND_SEALED",
            attempt_id="a",
            send_seal_digest=seal.seal_digest,
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
        )


def test_step_is_a_required_field() -> None:
    """(kernel round #2 §2 decision 3 — mutation M4) A record built without ``step`` is
    unconstructable — the Phase 3 wave 3 KW3-GW auditability gap this field closes cannot be
    silently reopened by a call site that simply omits it."""
    with pytest.raises(ValidationError, match="step"):
        GatewayEvidenceRecord(kind="SEND_REFUSED", attempt_id="a")
