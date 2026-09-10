"""Compose-level end-to-end pin (T2 lane A — codec digest binding, plan
``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md`` §8 "설계 정정 ①", "the point of this
lane"): a :class:`~tos_runtime.compose.context.ComposeContextResolver` bound with
:class:`~tos_runtime.compose._request_digest.KisWireCodecDigest` drives a real compose run to
``SEND_SEALED`` and produces a :class:`~tos.egressgw.SendSeal` whose ``request_bytes_digest``
GENUINELY equals ``KisOrderWireCodec.digest(KisOrderWireCodec.encode(seal, ...))`` — closing the
gap :mod:`tos_runtime.transport.kis_mock.codec`'s own module docstring names.

Hermetic — reuses ``test_compose_root.py``'s ``_compose``/``_reach_trusted`` two-pass pattern and
``test_send_seal.py``'s durable-row-readback (real sqlite, never a mock of the gateway's sink).
The ``ComposeContextResolver`` dataclass is mutable (not ``frozen=True``), so this test swaps
``runtime.context_resolver.request_bytes_digest_source`` after composition, before running any
event — a test-only technique (mirrors ``FakeMonotonicSource`` in ``test_compose_root.py``), NOT
a production wiring change: binding ``KisWireCodecDigest`` into the DEFAULT compose wiring is a
later lane's job (compose ``--transport kis-mock``), which this lane's own constraints exclude.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from tos.egress.predicates import exact_binding_holds
from tos_runtime.compose._request_digest import CapsuleStandInDigest, KisWireCodecDigest
from tos_runtime.transport.kis_mock.codec import KisOrderWireCodec

from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted
from .test_send_seal import _durable_rows_in_order

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

FIELD_MAP = {
    "account": "CANO",
    "instrument": "PDNO",
    "quantity": "ORD_QTY",
    "price": "ORD_UNPR",
}
STATIC_FIELDS = {
    "ACNT_PRDT_CD": "01",
    "ORD_DVSN": "00",
    "EXCG_ID_DVSN_CD": "KRX",
    "SLL_TYPE": "",
    "CNDT_PRIC": "",
}


def _run_to_send_boundary(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
):
    """Compose, THEN swap the resolver's digest source, THEN run the same two-pass pattern
    ``test_send_seal.py::_run_to_send_boundary`` uses to reach a real send hand-off."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    runtime.context_resolver.request_bytes_digest_source = KisWireCodecDigest(
        field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS
    )
    _reach_trusted(runtime)
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    runtime.run_once((event,))
    return runtime


def _seal_field(seal: dict, name: str):
    return seal[name]


def test_kis_wire_codec_digest_binds_the_seals_own_request_bytes_digest(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """The positive pin: with ``KisWireCodecDigest`` bound, the sealed
    ``request_bytes_digest`` is GENUINELY the codec's own digest of the sealed outbound — never
    a look-alike stand-in."""
    runtime = _run_to_send_boundary(config_dir, data_dir, custody_root, tmp_path)
    rows = _durable_rows_in_order(runtime)
    seal = next(payload for kind, payload in rows if kind == "SEND_SEALED")["send_seal"]

    body = KisOrderWireCodec.encode_fields(
        account=_seal_field(seal, "account"),
        instrument=seal["instrument_key"]["instrument"],
        quantity=Decimal(str(seal["outbound_quantity"])),
        price=Decimal(str(seal["outbound_price"])),
        field_map=FIELD_MAP,
        static_body_fields=STATIC_FIELDS,
    )
    recomputed_digest = KisOrderWireCodec.digest(body)

    assert recomputed_digest == seal["request_bytes_digest"]
    assert seal["capsule_egress_request_digest"] == seal["request_bytes_digest"]

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_exact_binding_holds_over_the_kis_wire_codec_bound_context(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """The kernel's own item-17 predicate still holds over the last resolved
    ``SendBoundaryContext`` when the digest source is the genuine codec binding."""
    runtime = _run_to_send_boundary(config_dir, data_dir, custody_root, tmp_path)
    context = runtime.context_resolver.contexts[-1]
    construction = context.construction
    assert construction is not None and construction.conformance_result is not None
    verdict_token = str(construction.conformance_result.value)

    assert exact_binding_holds(
        context.egress_request,
        context.quorum_commit_certificate,
        context.authorized_coordinates,
        verdict_token,
        context.capsule_egress_request_digest,
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_capsule_stand_in_digest_does_not_satisfy_the_codec_comparison(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Mutation-style negative (plan §8 "the point of this lane"): with the DEFAULT
    ``CapsuleStandInDigest`` (unchanged from today), the same codec-recomputed digest does NOT
    equal the sealed ``request_bytes_digest`` — proving the positive test above is not
    trivially true for ANY digest source, only for a genuine codec binding."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    assert isinstance(
        runtime.context_resolver.request_bytes_digest_source, CapsuleStandInDigest
    )
    _reach_trusted(runtime)
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    runtime.run_once((event,))

    rows = _durable_rows_in_order(runtime)
    seal = next(payload for kind, payload in rows if kind == "SEND_SEALED")["send_seal"]

    body = KisOrderWireCodec.encode_fields(
        account=_seal_field(seal, "account"),
        instrument=seal["instrument_key"]["instrument"],
        quantity=Decimal(str(seal["outbound_quantity"])),
        price=Decimal(str(seal["outbound_price"])),
        field_map=FIELD_MAP,
        static_body_fields=STATIC_FIELDS,
    )
    recomputed_digest = KisOrderWireCodec.digest(body)

    assert recomputed_digest != seal["request_bytes_digest"]

    runtime.rcl_log.close()
    runtime.evidence_store.close()
