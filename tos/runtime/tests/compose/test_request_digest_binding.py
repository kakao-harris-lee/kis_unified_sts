"""Compose-level end-to-end pin (T2 lane A — codec digest binding, plan"""

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
    """Compose, THEN swap the resolver's digest source, THEN run the same two-pass pattern"""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    runtime.context_resolver.request_bytes_digest_source = KisWireCodecDigest(
        field_map=FIELD_MAP, price_scale=1, static_body_fields=STATIC_FIELDS
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
    """The positive pin: with ``KisWireCodecDigest`` bound, the sealed"""
    runtime = _run_to_send_boundary(config_dir, data_dir, custody_root, tmp_path)
    rows = _durable_rows_in_order(runtime)
    seal = next(payload for kind, payload in rows if kind == "SEND_SEALED")["send_seal"]

    body = KisOrderWireCodec.encode_fields(
        account=_seal_field(seal, "account"),
        instrument=seal["instrument_key"]["instrument"],
        quantity=Decimal(str(seal["outbound_quantity"])),
        price=Decimal(str(seal["outbound_price"])),
        field_map=FIELD_MAP,
        price_scale=1,
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
    """The kernel's own item-17 predicate still holds over the last resolved"""
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
    """Mutation-style negative (plan §8 "the point of this lane"): with the DEFAULT"""
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
        price_scale=1,
        static_body_fields=STATIC_FIELDS,
    )
    recomputed_digest = KisOrderWireCodec.digest(body)

    assert recomputed_digest != seal["request_bytes_digest"]

    runtime.rcl_log.close()
    runtime.evidence_store.close()
