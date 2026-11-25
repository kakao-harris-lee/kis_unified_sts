"""A minimal, self-contained ``SendSeal`` builder for the adapter test suite."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from tos.egressgw import OUTBOUND_COORDINATE_NAMES, SendSeal
from tos.engine import InstrumentKey
from tos.ordering import OrderingEvent
from tos_runtime.transport.kis_mock.codec import KisOrderWireCodec

ACCOUNT = "11111111-01"
INSTRUMENT = "005930"
ENDPOINT = "https://openapivts.koreainvestment.com:29443"
ENVIRONMENT = "non-live-test"
ROUTE_IDENTITY = "kis-mock-route-1"
ACTION = "NEW_ORDER"
METHOD = "SUBMIT"
ACTIVE_PRINCIPAL = "kis-mock-order-non-live-test"

DEFAULT_FIELD_MAP: Mapping[str, str] = {
    "account": "CANO",
    "instrument": "PDNO",
    "quantity": "ORD_QTY",
    "price": "ORD_UNPR",
}

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
    """Build a self-consistent :class:`~tos.egressgw.SendSeal`."""
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
                provisional,
                field_map=field_map,
                price_scale=1,
                static_body_fields=static_body_fields,
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
