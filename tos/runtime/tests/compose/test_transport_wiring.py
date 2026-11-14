"""``tos_runtime.compose._transport_wiring`` tests — TOS KIS MOCK transport plan T2 lane C"""

from __future__ import annotations

import ast
import dataclasses
import os
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml
from tos.egressgw.records import GatewayEvidenceRecord
from tos.engine.vocabulary import CommitmentStep
from tos.evidence import EvidenceAppendReceipt
from tos.workload import RuntimeIdentity
from tos_runtime.brokercap.instance import load_instance_documents
from tos_runtime.brokercap.scopes import BrokerScopesConfig, load_broker_scopes
from tos_runtime.compose._request_digest import CapsuleStandInDigest, KisWireCodecDigest
from tos_runtime.compose._transport_wiring import (
    KIS_MOCK_TRANSPORT_CONFIG_NAME,
    SealRegistry,
    TransportKind,
    TransportWiringError,
    build_transport,
    load_transport_config,
    refuse_custody_principal_mismatch,
    refuse_transport_scope_mismatch,
    resolve_transport_boot,
)
from tos_runtime.compose._venue_wiring import VenuePolicyScopeMismatch
from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.ports import CredentialHandle
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.transport.kis_mock.adapter import KisMockTransport
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions

from ..transport.kis_mock import _seal_fixtures as seal_fx
from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DRAFT_PATH = (
    _REPO_ROOT / "docs" / "broker-profiles" / "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
)
_BROKER_SCOPES_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "broker_scopes.example.yaml"
)
_ENVIRONMENT_LABEL = "non-live-test"


def _load_scopes(
    tmp_path: Path, *, active_scope: str, mock_evidence_ok: bool = False
) -> BrokerScopesConfig:
    raw = yaml.safe_load(_BROKER_SCOPES_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = active_scope
    raw["instance_path"] = os.path.relpath(_DRAFT_PATH, tmp_path)
    if mock_evidence_ok:
        for scope in raw["scopes"]:
            if scope["name"] == "MOCK_STOCK_ORDER":
                scope["profile_evidence_ok"] = True
    path = tmp_path / f"broker_scopes_{active_scope}.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(path, environment_label=_ENVIRONMENT_LABEL)


def _activate_mock_stock_order(config_dir: Path) -> None:
    """Rewrite the standard ``config_dir`` fixture's ``broker_scopes.yaml`` to activate"""
    raw = yaml.safe_load(_BROKER_SCOPES_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = "MOCK_STOCK_ORDER"
    raw["instance_path"] = os.path.relpath(_DRAFT_PATH, config_dir)
    for scope in raw["scopes"]:
        if scope["name"] == "MOCK_STOCK_ORDER":
            scope["profile_evidence_ok"] = True
    (config_dir / "broker_scopes.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )


def _build_custody(
    custody_root: Path, *, principal: str = fx.KIS_MOCK_ORDER_PRINCIPAL
) -> None:
    fx.provision_kis_mock_custody(custody_root, principal=principal)


@pytest.fixture()
def mock_stock_order_scopes(tmp_path: Path) -> BrokerScopesConfig:
    return _load_scopes(
        tmp_path, active_scope="MOCK_STOCK_ORDER", mock_evidence_ok=True
    )


@pytest.fixture()
def synthetic_scopes(tmp_path: Path) -> BrokerScopesConfig:
    return _load_scopes(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")


@pytest.fixture()
def real_read_scopes(tmp_path: Path) -> BrokerScopesConfig:
    return _load_scopes(tmp_path, active_scope="REAL_READ")


def test_load_transport_config_synthetic_returns_none(
    tmp_path: Path, synthetic_scopes: BrokerScopesConfig
) -> None:
    assert (
        load_transport_config(TransportKind.SYNTHETIC, tmp_path, synthetic_scopes)
        is None
    )


def test_load_transport_config_kis_mock_loads_the_real_config(
    tmp_path: Path, mock_stock_order_scopes: BrokerScopesConfig
) -> None:
    fx.write_kis_mock_transport_config(tmp_path)
    config = load_transport_config(
        TransportKind.KIS_MOCK, tmp_path, mock_stock_order_scopes
    )
    assert config is not None
    assert config.endpoint_rest_base == fx.KIS_MOCK_REST_BASE
    assert config.mode == "dry_run"


def test_load_transport_config_kis_mock_refuses_when_active_scope_has_no_instance(
    tmp_path: Path, synthetic_scopes: BrokerScopesConfig
) -> None:
    fx.write_kis_mock_transport_config(tmp_path)
    with pytest.raises(TransportWiringError, match="INSTANCE binding"):
        load_transport_config(TransportKind.KIS_MOCK, tmp_path, synthetic_scopes)


def test_load_transport_config_kis_mock_refuses_when_instance_path_is_none(
    tmp_path: Path, mock_stock_order_scopes: BrokerScopesConfig
) -> None:
    fx.write_kis_mock_transport_config(tmp_path)
    scopes = BrokerScopesConfig(
        scopes=mock_stock_order_scopes.scopes,
        active_scope=mock_stock_order_scopes.active_scope,
        environment_binding=mock_stock_order_scopes.environment_binding,
        asset_binding=mock_stock_order_scopes.asset_binding,
        instance_path=None,
    )
    with pytest.raises(TransportWiringError, match="INSTANCE binding"):
        load_transport_config(TransportKind.KIS_MOCK, tmp_path, scopes)


def test_load_transport_config_kis_mock_attests_codec_bound(
    tmp_path: Path, mock_stock_order_scopes: BrokerScopesConfig
) -> None:
    """The compose wiring's own attestation that it binds KisWireCodecDigest — proven here by"""
    fx.write_kis_mock_transport_config(tmp_path, mode="live")
    config = load_transport_config(
        TransportKind.KIS_MOCK, tmp_path, mock_stock_order_scopes
    )
    assert config is not None
    assert config.mode == "live"


def _documents_with_rest_base_cleared(
    instance_path: Path, *, environment: str
) -> tuple:
    """The real, loaded INSTANCE documents, with ``environment``'s own ``rest_base`` cleared to"""
    return tuple(
        (
            dataclasses.replace(document, rest_base=None)
            if document.environment == environment
            else document
        )
        for document in load_instance_documents(instance_path)
    )


def test_load_transport_config_kis_mock_refuses_when_mock_document_rest_base_is_none(
    tmp_path: Path,
    mock_stock_order_scopes: BrokerScopesConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Independent review MEDIUM-4: the mock-document host-seal guard had never actually gone"""
    fx.write_kis_mock_transport_config(tmp_path)
    assert mock_stock_order_scopes.instance_path is not None
    doctored = _documents_with_rest_base_cleared(
        mock_stock_order_scopes.instance_path, environment="MOCK_VTS"
    )
    monkeypatch.setattr(
        "tos_runtime.compose._transport_wiring.load_instance_documents",
        lambda _path, **_kwargs: doctored,
    )
    with pytest.raises(TransportWiringError, match="rest_base"):
        load_transport_config(TransportKind.KIS_MOCK, tmp_path, mock_stock_order_scopes)


def test_load_transport_config_kis_mock_refuses_when_real_document_rest_base_is_none(
    tmp_path: Path,
    mock_stock_order_scopes: BrokerScopesConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Symmetric to the MOCK-document case above — the REAL_PROD exclusion fact must be"""
    fx.write_kis_mock_transport_config(tmp_path)
    assert mock_stock_order_scopes.instance_path is not None
    doctored = _documents_with_rest_base_cleared(
        mock_stock_order_scopes.instance_path, environment="REAL_PROD"
    )
    monkeypatch.setattr(
        "tos_runtime.compose._transport_wiring.load_instance_documents",
        lambda _path, **_kwargs: doctored,
    )
    with pytest.raises(TransportWiringError, match="rest_base"):
        load_transport_config(TransportKind.KIS_MOCK, tmp_path, mock_stock_order_scopes)


def test_refuse_transport_scope_mismatch_kis_mock_with_mock_stock_order_admits(
    mock_stock_order_scopes: BrokerScopesConfig,
) -> None:
    refuse_transport_scope_mismatch(TransportKind.KIS_MOCK, mock_stock_order_scopes)


def test_refuse_transport_scope_mismatch_synthetic_with_synthetic_scope_admits(
    synthetic_scopes: BrokerScopesConfig,
) -> None:
    refuse_transport_scope_mismatch(TransportKind.SYNTHETIC, synthetic_scopes)


def test_refuse_transport_scope_mismatch_kis_mock_with_synthetic_scope_refuses(
    synthetic_scopes: BrokerScopesConfig,
) -> None:
    with pytest.raises(TransportWiringError, match="broker-reaching"):
        refuse_transport_scope_mismatch(TransportKind.KIS_MOCK, synthetic_scopes)


def test_refuse_transport_scope_mismatch_synthetic_with_mock_stock_order_refuses(
    mock_stock_order_scopes: BrokerScopesConfig,
) -> None:
    with pytest.raises(TransportWiringError, match="non-broker-reaching"):
        refuse_transport_scope_mismatch(
            TransportKind.SYNTHETIC, mock_stock_order_scopes
        )


def test_refuse_transport_scope_mismatch_kis_mock_with_real_scope_refuses(
    real_read_scopes: BrokerScopesConfig,
) -> None:
    with pytest.raises(TransportWiringError, match="broker-reaching"):
        refuse_transport_scope_mismatch(TransportKind.KIS_MOCK, real_read_scopes)


def test_full_sweep_every_scope_x_both_kinds(tmp_path: Path) -> None:
    """The team-lead spec's own full sweep: only (SYNTHETIC_FUTURES_ORDER, synthetic) and"""
    raw = yaml.safe_load(_BROKER_SCOPES_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["instance_path"] = os.path.relpath(_DRAFT_PATH, tmp_path)
    for scope in raw["scopes"]:
        if scope["name"] == "MOCK_STOCK_ORDER":
            scope["profile_evidence_ok"] = True
    path = tmp_path / "broker_scopes_sweep.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    admitted_a_case = False
    for scope_name in (s["name"] for s in raw["scopes"]):
        if scope_name == "REAL_ORDER":
            continue
        raw["active_scope"] = scope_name
        path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        config = load_broker_scopes(path, environment_label=_ENVIRONMENT_LABEL)
        for kind in (TransportKind.SYNTHETIC, TransportKind.KIS_MOCK):
            if (
                scope_name == "SYNTHETIC_FUTURES_ORDER"
                and kind is TransportKind.SYNTHETIC
                or scope_name == "MOCK_STOCK_ORDER"
                and kind is TransportKind.KIS_MOCK
            ):
                refuse_transport_scope_mismatch(kind, config)
                admitted_a_case = True
            else:
                with pytest.raises(TransportWiringError):
                    refuse_transport_scope_mismatch(kind, config)
    assert admitted_a_case


def test_refuse_custody_principal_mismatch_synthetic_is_a_noop(
    custody_root: Path, mock_stock_order_scopes: BrokerScopesConfig
) -> None:
    custody = FileCustody(
        custody_root,
        environment_label=_ENVIRONMENT_LABEL,
        expected_owner_uid=os.getuid(),
        evidence=_NullEvidence(),
    )
    refuse_custody_principal_mismatch(
        TransportKind.SYNTHETIC, custody, mock_stock_order_scopes.active_scope
    )


def test_refuse_custody_principal_mismatch_matching_principal_admits(
    custody_root: Path, mock_stock_order_scopes: BrokerScopesConfig
) -> None:
    _build_custody(custody_root)
    custody = FileCustody(
        custody_root,
        environment_label=_ENVIRONMENT_LABEL,
        expected_owner_uid=os.getuid(),
        evidence=_NullEvidence(),
    )
    refuse_custody_principal_mismatch(
        TransportKind.KIS_MOCK, custody, mock_stock_order_scopes.active_scope
    )


def test_refuse_custody_principal_mismatch_wrong_principal_refuses(
    custody_root: Path, mock_stock_order_scopes: BrokerScopesConfig
) -> None:
    _build_custody(custody_root, principal="some-other-principal")
    custody = FileCustody(
        custody_root,
        environment_label=_ENVIRONMENT_LABEL,
        expected_owner_uid=os.getuid(),
        evidence=_NullEvidence(),
    )
    with pytest.raises(TransportWiringError, match="does not equal"):
        refuse_custody_principal_mismatch(
            TransportKind.KIS_MOCK, custody, mock_stock_order_scopes.active_scope
        )


def test_refuse_custody_principal_mismatch_checks_both_scopes_independently(
    custody_root: Path, mock_stock_order_scopes: BrokerScopesConfig
) -> None:
    """Independent review MEDIUM-2: corrupt ONLY ``kis_mock.app_secret``'s manifest principal —"""
    _build_custody(custody_root)
    manifest_path = custody_root / "custody.manifest.yaml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    raw["scopes"]["kis_mock.app_secret"]["principal"] = "some-other-principal"
    manifest_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    custody = FileCustody(
        custody_root,
        environment_label=_ENVIRONMENT_LABEL,
        expected_owner_uid=os.getuid(),
        evidence=_NullEvidence(),
    )
    with pytest.raises(TransportWiringError, match="kis_mock.app_secret"):
        refuse_custody_principal_mismatch(
            TransportKind.KIS_MOCK, custody, mock_stock_order_scopes.active_scope
        )


class _NullEvidence:
    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:  # noqa: ARG002
        del payload, kind, record_class
        return EvidenceAppendReceipt()


def test_seal_registry_captures_from_send_sealed_and_pops_single_use() -> None:
    registry = SealRegistry()
    seal = seal_fx.build_seal(attempt_id="attempt-x")
    registry.capture(
        GatewayEvidenceRecord(
            kind="SEND_SEALED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="attempt-x",
            send_seal=seal,
        )
    )

    assert registry("attempt-x") is seal
    assert registry("attempt-x") is None


def test_seal_registry_ignores_non_send_sealed_records() -> None:
    """Independent review LOW-2: the kernel's own ``GatewayEvidenceRecord`` construction-time"""
    registry = SealRegistry()
    seal = seal_fx.build_seal(attempt_id="attempt-y")
    registry.capture(
        GatewayEvidenceRecord(
            kind="SEND_STARTED",
            step=CommitmentStep.SEND_STARTED_DURABLE,
            attempt_id="attempt-y",
        )
    )
    assert registry("attempt-y") is None
    registry.capture(
        GatewayEvidenceRecord(
            kind="SEND_SEALED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="attempt-y",
            send_seal=seal,
        )
    )
    assert registry("attempt-y") is seal


def test_seal_registry_evicts_on_a_later_send_refused_for_the_same_attempt() -> None:
    """HIGH-1's bounding half: a ``SEND_REFUSED`` recorded for an attempt this registry already"""
    registry = SealRegistry()
    seal = seal_fx.build_seal(attempt_id="attempt-z")
    registry.capture(
        GatewayEvidenceRecord(
            kind="SEND_SEALED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="attempt-z",
            send_seal=seal,
        )
    )
    registry.capture(
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="attempt-z",
        )
    )
    assert registry("attempt-z") is None


def test_seal_registry_unknown_attempt_returns_none() -> None:
    registry = SealRegistry()
    assert registry("never-seen") is None


def test_synthetic_compose_never_wires_the_seal_registry_observer(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Independent review HIGH-1: under the DEFAULT ``synthetic`` transport,"""
    calls: list[object] = []
    original_capture = SealRegistry.capture

    def _spying_capture(self: SealRegistry, record: object) -> None:
        calls.append(record)
        original_capture(self, record)  # type: ignore[arg-type]

    monkeypatch.setattr(SealRegistry, "capture", _spying_capture)

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
    assert len(runtime.transport.requests) == 1

    assert calls == []

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_build_transport_synthetic_builds_a_synthetic_paper_transport() -> None:
    from tos.brokeradapter import SyntheticPaperTransport

    transport = build_transport(
        TransportKind.SYNTHETIC,
        transport_config=None,
        custody=_NullCustody(),
        monotonic=_NullMonotonic(),
        seal_lookup=SealRegistry(),
        evidence_store=_NullEvidenceStore(),
        runtime_identity=RuntimeIdentity(),
        credential_sessions=_null_credential_sessions(),
    )
    assert isinstance(transport, SyntheticPaperTransport)


def test_build_transport_kis_mock_builds_a_kis_mock_transport(
    tmp_path: Path, mock_stock_order_scopes: BrokerScopesConfig
) -> None:
    fx.write_kis_mock_transport_config(tmp_path)
    config = load_transport_config(
        TransportKind.KIS_MOCK, tmp_path, mock_stock_order_scopes
    )
    assert config is not None
    transport = build_transport(
        TransportKind.KIS_MOCK,
        transport_config=config,
        custody=_NullCustody(),
        monotonic=_NullMonotonic(),
        seal_lookup=SealRegistry(),
        evidence_store=_NullEvidenceStore(),
        runtime_identity=RuntimeIdentity(),
        credential_sessions=_null_credential_sessions(),
    )
    assert isinstance(transport, KisMockTransport)
    session = transport._credential_session  # noqa: SLF001
    assert session._app_key_scope == "kis_mock.app_key"  # noqa: SLF001
    assert session._app_secret_scope == "kis_mock.app_secret"  # noqa: SLF001


def _null_credential_sessions() -> KisCredentialSessions:
    """A registry that never loads anything — ``build_transport`` only asks it for a session."""
    return KisCredentialSessions(
        custody=_NullCustody(),
        monotonic=_NullMonotonic(),
        evidence_sink=lambda _kind, _fields: None,
    )


class _NullCustody:
    def load(self, scope: str) -> CredentialHandle:  # noqa: ARG002 - never invoked
        raise AssertionError("not invoked by build_transport itself")


class _NullMonotonic:
    def now_ms(self) -> int:  # pragma: no cover - never invoked in this test
        return 0


class _NullEvidenceStore(SqliteEvidenceStore):
    """Never invoked in these two tests — ``build_transport`` only ever builds the"""

    def __init__(self) -> None:
        pass


def test_resolve_transport_boot_synthetic(
    tmp_path: Path, custody_root: Path, synthetic_scopes: BrokerScopesConfig
) -> None:
    custody = FileCustody(
        custody_root,
        environment_label=_ENVIRONMENT_LABEL,
        expected_owner_uid=os.getuid(),
        evidence=_NullEvidence(),
    )
    result = resolve_transport_boot(
        TransportKind.SYNTHETIC, tmp_path, synthetic_scopes, custody
    )
    assert result.transport_config is None
    assert result.extra_config_files == ()


def test_resolve_transport_boot_kis_mock(
    tmp_path: Path, custody_root: Path, mock_stock_order_scopes: BrokerScopesConfig
) -> None:
    fx.write_kis_mock_transport_config(tmp_path)
    _build_custody(custody_root)
    custody = FileCustody(
        custody_root,
        environment_label=_ENVIRONMENT_LABEL,
        expected_owner_uid=os.getuid(),
        evidence=_NullEvidence(),
    )
    result = resolve_transport_boot(
        TransportKind.KIS_MOCK, tmp_path, mock_stock_order_scopes, custody
    )
    assert result.transport_config is not None
    assert result.extra_config_files == (tmp_path / KIS_MOCK_TRANSPORT_CONFIG_NAME,)


def test_e2e_boot_wires_a_kis_mock_transport_and_codec_digest_source(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)

    assert isinstance(runtime.transport, KisMockTransport)
    assert isinstance(
        runtime.context_resolver.request_bytes_digest_source, KisWireCodecDigest
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_e2e_boot_synthetic_still_uses_the_stand_in_digest_source(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert isinstance(
        runtime.context_resolver.request_bytes_digest_source, CapsuleStandInDigest
    )
    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_e2e_boot_refuses_when_custody_principal_mismatches(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root, principal="wrong-principal")
    with pytest.raises(TransportWiringError):
        _compose(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            transport_kind=TransportKind.KIS_MOCK,
        )


def test_e2e_boot_refuses_when_kis_mock_selected_against_the_synthetic_scope(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root)
    with pytest.raises(TransportWiringError):
        _compose(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            transport_kind=TransportKind.KIS_MOCK,
        )


def test_e2e_boot_records_kis_mock_transport_config_as_an_attested_input(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    import json

    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    rows = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'OPERATOR_ATTESTED_INPUTS'"
    ).fetchall()
    assert len(rows) == 1
    coordinates = json.loads(rows[0][0])["payload"]["attested_coordinates"]
    names = {row["source_file"] for row in coordinates}
    assert KIS_MOCK_TRANSPORT_CONFIG_NAME in names

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_crossing_event_coordinator_passes_gateway_denies_honestly(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Plan §4 T3's first half, landed here since it falls out of the wiring: with"""
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root)
    (config_dir / "coordinator_preconditions.yaml").write_text(
        yaml.safe_dump(
            {
                "live_authorization_state": "NOT_AUTHORIZED",
                "nonlive_broker_consuming": {"admitted": True},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)

    event = fx.crossing_event()
    results = runtime.run_once((event,))
    assert results[0].pipeline is not None
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label=_ENVIRONMENT_LABEL,
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )

    results2 = runtime.run_once((event,))
    flow = results2[0].flow
    assert flow is not None
    assert flow.handed_off is True
    assert flow.handoff is not None
    assert flow.handoff.accepted_for_transmission is not True

    live_scope_halts = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE payload_json LIKE '%LIVE_SCOPE_NOT_AUTHORIZED%'"
    ).fetchone()[0]
    assert live_scope_halts == 0

    send_refused_rows = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'SEND_REFUSED'"
    ).fetchone()[0]
    assert send_refused_rows == 1
    transport_rows = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind LIKE 'TRANSPORT_%'"
    ).fetchone()[0]
    assert transport_rows == 0

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def _compose_package_files() -> list[Path]:
    import tos_runtime.compose as pkg

    return list(Path(pkg.__file__).parent.glob("*.py"))


def _code_only(source: str) -> str:
    """Blank out every module/class/function docstring — mirrors"""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    for node in ast.walk(tree):
        if (
            isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            doc_node = node.body[0]
            start = doc_node.lineno - 1
            end = (doc_node.end_lineno or doc_node.lineno) - 1
            for i in range(start, end + 1):
                lines[i] = "\n"
    return "".join(lines)


def test_no_forbidden_literals_or_os_environ_in_tos_runtime_compose() -> None:
    forbidden = ("koreainvestment", "VTTC", "localhost", "os.environ", "os.getenv")
    offenders: list[str] = []
    for path in _compose_package_files():
        code_only = _code_only(path.read_text(encoding="utf-8"))
        for token in forbidden:
            if token in code_only:
                offenders.append(f"{path.name}: forbidden token {token!r}")
    assert offenders == [], offenders


def test_the_planted_violation_scan_actually_catches_something() -> None:
    planted = 'REST_BASE = "https://openapivts.koreainvestment.com:29443"\n'
    code_only = _code_only(planted)
    assert "koreainvestment" in code_only


def _set_scales(config_dir: Path, *, transport: int, policy: int | None) -> None:
    transport_path = config_dir / "kis_mock_transport.yaml"
    raw = yaml.safe_load(transport_path.read_text(encoding="utf-8"))
    raw["price_scale"] = transport
    transport_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    vcp_path = config_dir / "venue_constraint_policy.yaml"
    vcp = yaml.safe_load(vcp_path.read_text(encoding="utf-8"))
    if policy is None:
        vcp["_runtime"].pop("price_scale", None)
    else:
        vcp["_runtime"]["price_scale"] = policy
    vcp_path.write_text(
        yaml.safe_dump(vcp, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("transport", "policy"),
    [
        (1000, 100),
        (100, None),
    ],
)
def test_a_kis_mock_boot_refuses_a_price_scale_the_tree_does_not_state(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    transport: int,
    policy: int | None,
) -> None:
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _set_scales(config_dir, transport=transport, policy=policy)
    _build_custody(custody_root)
    with pytest.raises(VenuePolicyScopeMismatch, match="price_scale"):
        _compose(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            transport_kind=TransportKind.KIS_MOCK,
        )


def test_a_kis_mock_boot_with_equal_scales_boots(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _set_scales(config_dir, transport=100, policy=100)
    _build_custody(custody_root)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    assert runtime.context_resolver.request_bytes_digest_source.price_scale == 100
    runtime.rcl_log.close()
    runtime.evidence_store.close()
