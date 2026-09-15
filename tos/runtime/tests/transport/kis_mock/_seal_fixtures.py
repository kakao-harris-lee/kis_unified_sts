"""A minimal, self-contained ``SendSeal`` builder for the adapter test suite.

Unlike ``tos/tests/egressgw/_egressgw_fixtures.py`` (which drives the full gateway to produce a
seal), this module constructs a :class:`~tos.egressgw.SendSeal` directly via its own constructor.

**The digest invariant this builder encodes (review disposition F1, `dc6b47ba`).** By default,
:func:`build_seal` sets BOTH ``request_bytes_digest`` AND ``capsule_egress_request_digest`` to
:class:`~tos_runtime.transport.kis_mock.codec.KisOrderWireCodec`'s own digest of the sealed
outbound. This is **not** a tautology dressed up as a test: it is the literal invariant T2 will
make hold in production once the compose context resolver binds the SAME codec into
``capsule_egress_request_digest`` (today it does not — see ``codec.py``'s own module docstring
for the exact file:line where the compose root currently sets ``request_bytes_digest ==
capsule_egress_request_digest`` to a STAND-IN value, never a real wire-bytes digest). Building
fixtures against the FUTURE invariant, rather than an arbitrary matching pair, is what lets this
suite exercise the adapter's ACK/REJECT/UNKNOWN/TIMEOUT/pacing/token logic realistically today,
while ``mode: live`` stays config-refused until T2's binding actually lands (see
:mod:`tos_runtime.transport.kis_mock.config`'s own docstring).

Pass an explicit ``request_bytes_digest`` (deliberately not matching the codec's own) to exercise
the digest-mismatch path instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from tos.egressgw import OUTBOUND_COORDINATE_NAMES, SendSeal
from tos.engine import InstrumentKey
from tos.ordering import OrderingEvent
from tos_runtime.transport.kis_mock.codec import KisOrderWireCodec

ACCOUNT = "kis-mock-account-value"
INSTRUMENT = "005930"
ENDPOINT = "https://openapivts.koreainvestment.com:29443"
ENVIRONMENT = "non-live-test"
ROUTE_IDENTITY = "kis-mock-route-1"
ACTION = "NEW_ORDER"
METHOD = "SUBMIT"
ACTIVE_PRINCIPAL = "kis-mock-order-non-live-test"

#: The suite's default dynamic field map (the four kernel-sourced KIS wire fields).
DEFAULT_FIELD_MAP: Mapping[str, str] = {
    "account": "CANO",
    "instrument": "PDNO",
    "quantity": "ORD_QTY",
    "price": "ORD_UNPR",
}

#: The suite's default static body fields (the five per-deployment-constant KIS wire fields —
#: review F1's "known T1 gap" fields; arbitrary but fixed test values, never operator-approved
#: ones — see the runbook's proposal table for the real disposition).
DEFAULT_STATIC_BODY_FIELDS: Mapping[str, str] = {
    "ACNT_PRDT_CD": "01",
    "ORD_DVSN": "00",
    "EXCG_ID_DVSN_CD": "KRX",
    "SLL_TYPE": "",
    "CNDT_PRIC": "",
}


def build_seal(
    *,
    attempt_id: str = "attempt-1",
    side: str = "BUY",
    quantity: Decimal = Decimal("10"),
    price: Decimal = Decimal("70000"),
    instrument: str = INSTRUMENT,
    account: str = ACCOUNT,
    instrument_key_account: str | None = None,
    field_map: Mapping[str, str] | None = None,
    static_body_fields: Mapping[str, str] | None = None,
    request_bytes_digest: str | None = None,
    capsule_egress_request_digest: str | None = None,
) -> SendSeal:
    """Build a self-consistent :class:`~tos.egressgw.SendSeal`.

    ``request_bytes_digest``/``capsule_egress_request_digest`` both default to
    :meth:`~tos_runtime.transport.kis_mock.codec.KisOrderWireCodec.digest` of
    :meth:`~tos_runtime.transport.kis_mock.codec.KisOrderWireCodec.encode`'s own output for the
    same ``field_map``/``static_body_fields``/values — the module docstring's "future invariant".
    Pass an explicit (non-matching) ``request_bytes_digest`` to exercise the mismatch path.

    ``instrument_key_account`` defaults to ``account`` (the two coincide in every OTHER test in
    this suite, which is exactly why a mutation swapping ``seal.account`` for
    ``seal.instrument_key.account`` in :mod:`tos_runtime.transport.kis_mock.codec` would
    otherwise go undetected — team-lead re-review, mutation M8). Pass a DIFFERENT value here to
    build a seal where the two coordinates diverge, and assert the codec follows ``seal.account``
    (see ``test_codec.py::test_account_is_the_seal_field_never_instrument_key_account`` and
    ``test_adapter.py``'s companion live-send assertion).
    """
    if instrument_key_account is None:
        instrument_key_account = account
    if field_map is None:
        field_map = DEFAULT_FIELD_MAP
    if static_body_fields is None:
        static_body_fields = DEFAULT_STATIC_BODY_FIELDS

    coordinate_values = {
        "endpoint": ENDPOINT,
        "account": account,
        "environment": ENVIRONMENT,
        "action": ACTION,
        "method": METHOD,
        "route_identity": ROUTE_IDENTITY,
        "credential_generation": "0",
        "broker_session_generation": "0",
        "egress_generation": "1",
        "active_principal": ACTIVE_PRINCIPAL,
    }
    outbound_coordinates = tuple(
        (name, coordinate_values[name]) for name in OUTBOUND_COORDINATE_NAMES
    )

    if request_bytes_digest is None or capsule_egress_request_digest is None:
        # Build a provisional seal first (any digest values will do — the codec reads only
        # the account coordinate / instrument_key / outbound_quantity / outbound_price, all of
        # which are already fixed above) purely so KisOrderWireCodec.encode can be handed a
        # real SendSeal rather than a bespoke stand-in shape.
        provisional = SendSeal(
            attempt_id=attempt_id,
            instrument_key=InstrumentKey(
                account=instrument_key_account, instrument=instrument
            ),
            request_bytes_digest=f"provisional-{attempt_id}",
            canonical_command_digest=f"cmd-digest-{attempt_id}",
            capsule_egress_request_digest=f"provisional-{attempt_id}",
            claim_request_digest=f"claim-digest-{attempt_id}",
            claim_principal=ACTIVE_PRINCIPAL,
            active_principal=ACTIVE_PRINCIPAL,
            endpoint=ENDPOINT,
            account=account,
            environment=ENVIRONMENT,
            route_identity=ROUTE_IDENTITY,
            credential_generation=0,
            broker_session_generation=0,
            egress_generation=1,
            action=ACTION,
            method=METHOD,
            capability_nonce=f"cap-nonce-{attempt_id}",
            action_flow_permit_nonce=f"permit-nonce-{attempt_id}",
            outbound_coordinates=outbound_coordinates,
            outbound_quantity=quantity,
            outbound_price=price,
            outbound_side=side,
            reference=OrderingEvent(event_id=f"ev-{attempt_id}", quorum_commit_index=1),
            reference_digest=f"ref-digest-{attempt_id}",
            outbound_request_digest=f"outbound-req-digest-{attempt_id}",
            seal_digest=f"seal-digest-{attempt_id}",
        )
        codec_digest = KisOrderWireCodec.digest(
            KisOrderWireCodec.encode(
                provisional, field_map=field_map, static_body_fields=static_body_fields
            )
        )
        if request_bytes_digest is None:
            request_bytes_digest = codec_digest
        if capsule_egress_request_digest is None:
            capsule_egress_request_digest = codec_digest

    return SendSeal(
        attempt_id=attempt_id,
        instrument_key=InstrumentKey(
            account=instrument_key_account, instrument=instrument
        ),
        request_bytes_digest=request_bytes_digest,
        canonical_command_digest=f"cmd-digest-{attempt_id}",
        capsule_egress_request_digest=capsule_egress_request_digest,
        claim_request_digest=f"claim-digest-{attempt_id}",
        claim_principal=ACTIVE_PRINCIPAL,
        active_principal=ACTIVE_PRINCIPAL,
        endpoint=ENDPOINT,
        account=account,
        environment=ENVIRONMENT,
        route_identity=ROUTE_IDENTITY,
        credential_generation=0,
        broker_session_generation=0,
        egress_generation=1,
        action=ACTION,
        method=METHOD,
        capability_nonce=f"cap-nonce-{attempt_id}",
        action_flow_permit_nonce=f"permit-nonce-{attempt_id}",
        outbound_coordinates=outbound_coordinates,
        outbound_quantity=quantity,
        outbound_price=price,
        outbound_side=side,
        reference=OrderingEvent(event_id=f"ev-{attempt_id}", quorum_commit_index=1),
        reference_digest=f"ref-digest-{attempt_id}",
        outbound_request_digest=f"outbound-req-digest-{attempt_id}",
        seal_digest=f"seal-digest-{attempt_id}",
    )
