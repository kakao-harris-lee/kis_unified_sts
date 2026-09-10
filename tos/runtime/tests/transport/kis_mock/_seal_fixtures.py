"""A minimal, self-contained ``SendSeal`` builder for the adapter test suite.

Unlike ``tos/tests/egressgw/_egressgw_fixtures.py`` (which drives the full gateway to produce a
seal), this module constructs a :class:`~tos.egressgw.SendSeal` directly via its own constructor
— everything this adapter suite needs is a syntactically valid, self-consistent seal with a
``request_bytes_digest`` the caller can choose (usually: made to match what
``KisMockTransport`` will independently compute for the given body fields, so the "happy path"
digest check passes; deliberately mismatched, for the mismatch test).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal

from tos.egressgw import OUTBOUND_COORDINATE_NAMES, SendSeal
from tos.engine import InstrumentKey
from tos.ordering import OrderingEvent

ACCOUNT = "kis-mock-account-value"
INSTRUMENT = "005930"
ENDPOINT = "https://openapivts.koreainvestment.com:29443"
ENVIRONMENT = "non-live-test"
ROUTE_IDENTITY = "kis-mock-route-1"
ACTION = "NEW_ORDER"
METHOD = "SUBMIT"
ACTIVE_PRINCIPAL = "kis-mock-order-non-live-test"


def expected_body_bytes(
    *,
    field_map: Mapping[str, str],
    account: str,
    instrument: str,
    quantity: Decimal,
    price: Decimal,
) -> bytes:
    """Reproduce ``KisMockTransport``'s own canonical body-bytes serialization (its own private
    ``_canonical_json_bytes``/``_decimal_to_kis_string`` are intentionally NOT imported here —
    this is the test suite's OWN independent reconstruction of the same, small, documented
    algorithm, so a happy-path test does not become tautological with the implementation).
    """
    dynamic_sources = {
        "account": account,
        "instrument": instrument,
        "quantity": format(quantity, "f"),
        "price": format(price, "f"),
    }
    fields = {
        wire_name: dynamic_sources[source] for source, wire_name in field_map.items()
    }
    return json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def build_seal(
    *,
    attempt_id: str = "attempt-1",
    side: str = "BUY",
    quantity: Decimal = Decimal("10"),
    price: Decimal = Decimal("70000"),
    instrument: str = INSTRUMENT,
    account: str = ACCOUNT,
    field_map: Mapping[str, str] | None = None,
    request_bytes_digest: str | None = None,
) -> SendSeal:
    """Build a self-consistent :class:`~tos.egressgw.SendSeal`.

    ``request_bytes_digest`` defaults to the digest of the canonical body
    :func:`expected_body_bytes` computes for the same ``field_map``/values — i.e. the "everything
    matches" happy path. Pass an explicit (wrong) value to exercise the mismatch path.
    """
    if field_map is None:
        field_map = {
            "account": "CANO",
            "instrument": "PDNO",
            "quantity": "ORD_QTY",
            "price": "ORD_UNPR",
        }
    if request_bytes_digest is None:
        body = expected_body_bytes(
            field_map=field_map,
            account=account,
            instrument=instrument,
            quantity=quantity,
            price=price,
        )
        request_bytes_digest = hashlib.sha256(body).hexdigest()

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

    return SendSeal(
        attempt_id=attempt_id,
        instrument_key=InstrumentKey(account=account, instrument=instrument),
        request_bytes_digest=request_bytes_digest,
        canonical_command_digest=f"cmd-digest-{attempt_id}",
        capsule_egress_request_digest=f"capsule-digest-{attempt_id}",
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
