"""``SendSeal`` compose e2e assertions (TOS Phase 4 작업 6 §2.2, plan doc"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SEND_SEAL_FIELD_NAMES = (
    "attempt_id",
    "instrument_key",
    "request_bytes_digest",
    "canonical_command_digest",
    "capsule_egress_request_digest",
    "claim_principal",
    "active_principal",
    "endpoint",
    "account",
    "environment",
    "route_identity",
    "credential_generation",
    "broker_session_generation",
    "egress_generation",
    "action",
    "method",
    "capability_nonce",
    "action_flow_permit_nonce",
    "outbound_coordinates",
    "outbound_quantity",
    "outbound_price",
    "outbound_side",
    "reference",
    "reference_digest",
    "outbound_request_digest",
    "seal_digest",
)


def _run_to_send_boundary(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
):
    """Compose + run once + write the matching approval file + re-run — the"""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
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


def _durable_rows_in_order(runtime) -> list[tuple[str, dict]]:
    """Every durable evidence row, in the store's own append (``seq``)"""
    rows = runtime.evidence_store.connection.execute(
        "SELECT kind, payload_json FROM entries ORDER BY seq ASC"
    ).fetchall()
    return [(kind, json.loads(payload_json)["payload"]) for kind, payload_json in rows]


class TestSendSealDurableOrderAndDigestAgreement:
    """§2.2 (i): ``SEND_SEALED`` durably precedes ``SEND_STARTED``, and the"""

    def test_send_sealed_precedes_send_started_durably(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _run_to_send_boundary(config_dir, data_dir, custody_root, tmp_path)
        kinds = [kind for kind, _ in _durable_rows_in_order(runtime)]
        assert "SEND_SEALED" in kinds
        assert "SEND_STARTED" in kinds
        assert kinds.index("SEND_SEALED") < kinds.index("SEND_STARTED")
        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_seal_digest_agrees_across_sealed_started_and_transport(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _run_to_send_boundary(config_dir, data_dir, custody_root, tmp_path)
        rows = _durable_rows_in_order(runtime)

        sealed_payload = next(
            payload for kind, payload in rows if kind == "SEND_SEALED"
        )
        started_payload = next(
            payload for kind, payload in rows if kind == "SEND_STARTED"
        )

        seal_digest = sealed_payload["send_seal"]["seal_digest"]
        assert isinstance(seal_digest, str) and seal_digest

        assert started_payload["send_seal_digest"] == seal_digest
        assert len(runtime.transport.requests) == 1
        assert runtime.transport.requests[-1].seal_digest == seal_digest

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_egress_result_recorded_carries_the_seal_digest(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _run_to_send_boundary(config_dir, data_dir, custody_root, tmp_path)
        rows = _durable_rows_in_order(runtime)

        sealed_payload = next(
            payload for kind, payload in rows if kind == "SEND_SEALED"
        )
        seal_digest = sealed_payload["send_seal"]["seal_digest"]

        result_payload = next(
            payload for kind, payload in rows if kind == "EGRESS_RESULT_RECORDED"
        )
        assert result_payload["send_seal_digest"] == seal_digest

        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestGatewayEvidenceSinkPersistsTheWholeSeal:
    """§2.2 (ii): ``GatewayEvidenceSinkAdapter`` must persist the NESTED"""

    def test_send_sealed_row_carries_every_seal_field_read_back_from_sqlite(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _run_to_send_boundary(config_dir, data_dir, custody_root, tmp_path)
        rows = _durable_rows_in_order(runtime)

        sealed_payload = next(
            payload for kind, payload in rows if kind == "SEND_SEALED"
        )
        seal = sealed_payload.get("send_seal")
        assert isinstance(seal, dict), (
            "SEND_SEALED.send_seal must be a nested mapping, not dropped/"
            f"flattened/null — got {seal!r}"
        )
        missing = [name for name in _SEND_SEAL_FIELD_NAMES if name not in seal]
        assert missing == [], f"send_seal payload dropped field(s): {missing}"
        null_fields = [name for name in _SEND_SEAL_FIELD_NAMES if seal[name] is None]
        assert null_fields == [], f"send_seal payload nulled field(s): {null_fields}"

        runtime.rcl_log.close()
        runtime.evidence_store.close()
