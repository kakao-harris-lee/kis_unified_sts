"""``tos_runtime.compose._transport_wiring`` tests — TOS KIS MOCK transport plan T2 lane C
(compose wiring, ``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md`` §4 row T2, §8 "T2
must").

Hermetic (D1.4): every write stays under ``tmp_path``/the fixture ``custody_root``/``config_dir``
directories; the Broker Capability Profile INSTANCE document is loaded READ-ONLY from
``docs/broker-profiles/`` (never written) — the same pattern
``tos/runtime/tests/brokercap/test_exit_conditions.py`` already uses.
"""

from __future__ import annotations

import ast
import dataclasses
import os
from pathlib import Path

import pytest
import yaml
from tos.egressgw.records import GatewayEvidenceRecord
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
from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.transport.kis_mock.adapter import KisMockTransport

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


# ===========================================================================
# Shared fixture helpers
# ===========================================================================


def _load_scopes(
    tmp_path: Path, *, active_scope: str, mock_evidence_ok: bool = False
) -> BrokerScopesConfig:
    raw = yaml.safe_load(_BROKER_SCOPES_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = active_scope
    raw["instance_path"] = str(_DRAFT_PATH)
    if mock_evidence_ok:
        for scope in raw["scopes"]:
            if scope["name"] == "MOCK_STOCK_ORDER":
                scope["profile_evidence_ok"] = True
    path = tmp_path / f"broker_scopes_{active_scope}.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(path, environment_label=_ENVIRONMENT_LABEL)


def _activate_mock_stock_order(config_dir: Path) -> None:
    """Rewrite the standard ``config_dir`` fixture's ``broker_scopes.yaml`` to activate
    MOCK_STOCK_ORDER (REDUCED, real evidence flag) bound to the real MOCK_VTS INSTANCE document —
    mirrors ``test_exit_conditions.py``'s own ``_ec5_config_dir``."""
    raw = yaml.safe_load(_BROKER_SCOPES_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = "MOCK_STOCK_ORDER"
    raw["instance_path"] = str(_DRAFT_PATH)
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


# ===========================================================================
# load_transport_config — host seal (plan §2 decision 5)
# ===========================================================================


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
    """The compose wiring's own attestation that it binds KisWireCodecDigest — proven here by
    the fact ``mode: live`` (never used in this suite otherwise) loads successfully through this
    call site alone."""
    fx.write_kis_mock_transport_config(tmp_path, mode="live")
    config = load_transport_config(
        TransportKind.KIS_MOCK, tmp_path, mock_stock_order_scopes
    )
    assert config is not None
    assert config.mode == "live"


def _documents_with_rest_base_cleared(
    instance_path: Path, *, environment: str
) -> tuple:
    """The real, loaded INSTANCE documents, with ``environment``'s own ``rest_base`` cleared to
    ``None`` — never a hand-built document (independent review MEDIUM-4's own "never invented"
    concern applies to test fixtures too)."""
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
    """Independent review MEDIUM-4: the mock-document host-seal guard had never actually gone
    red — every fixture's real document always carries ``rest_base``. Clearing it (never
    inventing a replacement) must refuse boot."""
    fx.write_kis_mock_transport_config(tmp_path)
    assert mock_stock_order_scopes.instance_path is not None
    doctored = _documents_with_rest_base_cleared(
        mock_stock_order_scopes.instance_path, environment="MOCK_VTS"
    )
    monkeypatch.setattr(
        "tos_runtime.compose._transport_wiring.load_instance_documents",
        lambda _path: doctored,
    )
    with pytest.raises(TransportWiringError, match="rest_base"):
        load_transport_config(TransportKind.KIS_MOCK, tmp_path, mock_stock_order_scopes)


def test_load_transport_config_kis_mock_refuses_when_real_document_rest_base_is_none(
    tmp_path: Path,
    mock_stock_order_scopes: BrokerScopesConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Symmetric to the MOCK-document case above — the REAL_PROD exclusion fact must be
    provable too, never assumed present."""
    fx.write_kis_mock_transport_config(tmp_path)
    assert mock_stock_order_scopes.instance_path is not None
    doctored = _documents_with_rest_base_cleared(
        mock_stock_order_scopes.instance_path, environment="REAL_PROD"
    )
    monkeypatch.setattr(
        "tos_runtime.compose._transport_wiring.load_instance_documents",
        lambda _path: doctored,
    )
    with pytest.raises(TransportWiringError, match="rest_base"):
        load_transport_config(TransportKind.KIS_MOCK, tmp_path, mock_stock_order_scopes)


# ===========================================================================
# refuse_transport_scope_mismatch — one source of truth (plan §2 decisions 5/7)
# ===========================================================================


def test_refuse_transport_scope_mismatch_kis_mock_with_mock_stock_order_admits(
    mock_stock_order_scopes: BrokerScopesConfig,
) -> None:
    refuse_transport_scope_mismatch(
        TransportKind.KIS_MOCK, mock_stock_order_scopes
    )  # no raise


def test_refuse_transport_scope_mismatch_synthetic_with_synthetic_scope_admits(
    synthetic_scopes: BrokerScopesConfig,
) -> None:
    refuse_transport_scope_mismatch(
        TransportKind.SYNTHETIC, synthetic_scopes
    )  # no raise


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
    # REAL_READ's own tuples are NON_AUTHORIZING_READ but under BROKER_PRODUCTION, not
    # BROKER_SIMULATION — condition 3's MOCK-shape check still fails it.
    with pytest.raises(TransportWiringError, match="broker-reaching"):
        refuse_transport_scope_mismatch(TransportKind.KIS_MOCK, real_read_scopes)


def test_full_sweep_every_scope_x_both_kinds(tmp_path: Path) -> None:
    """The team-lead spec's own full sweep: only (SYNTHETIC_FUTURES_ORDER, synthetic) and
    (MOCK_STOCK_ORDER with profile_evidence_ok, kis-mock) ever admit; every REAL_* scope refuses
    kis-mock, naming the broker-reaching/MOCK-shape reason."""
    raw = yaml.safe_load(_BROKER_SCOPES_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["instance_path"] = str(_DRAFT_PATH)
    for scope in raw["scopes"]:
        if scope["name"] == "MOCK_STOCK_ORDER":
            scope["profile_evidence_ok"] = True
    path = tmp_path / "broker_scopes_sweep.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    admitted_a_case = False
    for scope_name in (s["name"] for s in raw["scopes"]):
        if scope_name == "REAL_ORDER":
            # Always PROHIBITED admissibility — load_broker_scopes itself never sets
            # active_scope to a PROHIBITED scope; skip (module docstring: "listed but always
            # PROHIBITED", never an activatable scope at all).
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
                refuse_transport_scope_mismatch(kind, config)  # admits
                admitted_a_case = True
            else:
                with pytest.raises(TransportWiringError):
                    refuse_transport_scope_mismatch(kind, config)
    assert admitted_a_case


# ===========================================================================
# refuse_custody_principal_mismatch — plan §2 decision 4
# ===========================================================================


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
    )  # never touches custody at all — no raise even though scopes aren't provisioned


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
    )  # no raise


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
    """Independent review MEDIUM-2: corrupt ONLY ``kis_mock.app_secret``'s manifest principal —
    proves both scopes are actually checked (never just whichever happens to appear first in
    ``_KIS_MOCK_CUSTODY_SCOPES``); a mutation dropping either scope from that tuple would make
    this test wrongly pass without raising."""
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
    def append(self, *args: object, **kwargs: object) -> None:  # noqa: ARG002
        return None  # a no-op evidence double — args are intentionally unused


# ===========================================================================
# SealRegistry — single-use SendSeal capture/lookup
# ===========================================================================


def test_seal_registry_captures_from_send_sealed_and_pops_single_use() -> None:
    registry = SealRegistry()
    seal = seal_fx.build_seal(attempt_id="attempt-x")
    registry.capture(
        GatewayEvidenceRecord(
            kind="SEND_SEALED", attempt_id="attempt-x", send_seal=seal
        )
    )

    assert registry("attempt-x") is seal
    assert registry("attempt-x") is None  # single-use — second lookup is None


def test_seal_registry_ignores_non_send_sealed_records() -> None:
    """Independent review LOW-2: the kernel's own ``GatewayEvidenceRecord`` construction-time
    validator (``_seal_fields_match_their_kind``, ``tos/src/tos/egressgw/records.py``) already
    rejects a non-``None`` ``send_seal`` on any kind other than ``SEND_SEALED`` — so a
    ``kind == "SEND_SEALED"`` mutation in :meth:`SealRegistry.capture` is unfalsifiable through
    any record this suite (or production) can actually construct; the ``send_seal is not None``
    guard alone already carries the whole load for every REACHABLE record. This test still pins
    the OBSERVABLE behaviour (a kind-less-seal record captures nothing), not a claim that the
    kind check itself is load-bearing."""
    registry = SealRegistry()
    seal = seal_fx.build_seal(attempt_id="attempt-y")
    registry.capture(GatewayEvidenceRecord(kind="SEND_STARTED", attempt_id="attempt-y"))
    assert registry("attempt-y") is None
    registry.capture(
        GatewayEvidenceRecord(
            kind="SEND_SEALED", attempt_id="attempt-y", send_seal=seal
        )
    )
    assert registry("attempt-y") is seal


def test_seal_registry_evicts_on_a_later_send_refused_for_the_same_attempt() -> None:
    """HIGH-1's bounding half: a ``SEND_REFUSED`` recorded for an attempt this registry already
    holds a captured seal for means that seal will never be consumed — evict it rather than let
    it survive past the attempt's own terminal record."""
    registry = SealRegistry()
    seal = seal_fx.build_seal(attempt_id="attempt-z")
    registry.capture(
        GatewayEvidenceRecord(
            kind="SEND_SEALED", attempt_id="attempt-z", send_seal=seal
        )
    )
    registry.capture(GatewayEvidenceRecord(kind="SEND_REFUSED", attempt_id="attempt-z"))
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
    """Independent review HIGH-1: under the DEFAULT ``synthetic`` transport,
    ``SealRegistry.capture`` must never be wired as the gateway evidence sink's ``on_record``
    observer at all — ``SyntheticPaperTransport`` never calls the lookup, so wiring it
    unconditionally (the pre-fix behaviour) retained every ``SendSeal`` for the whole process
    lifetime. Proven by spying on ``SealRegistry.capture`` itself and driving a REAL synthetic
    hand-off (the same scenario ``test_compose_root.py::test_one_synthetic_transport_handoff``
    drives) through the actual compose root — the spy must never fire."""
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
    assert len(runtime.transport.requests) == 1  # the hand-off genuinely happened

    assert calls == []  # ...but the (unwired) SealRegistry observer never fired

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ===========================================================================
# build_transport
# ===========================================================================


def test_build_transport_synthetic_builds_a_synthetic_paper_transport() -> None:
    from tos.brokeradapter import SyntheticPaperTransport

    transport = build_transport(
        TransportKind.SYNTHETIC,
        transport_config=None,
        custody=_NullCustody(),
        monotonic=_NullMonotonic(),
        seal_lookup=SealRegistry(),
        evidence_store=_NullEvidenceStore(),
        runtime_identity=None,
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
        runtime_identity=None,
    )
    assert isinstance(transport, KisMockTransport)
    # Independent review MEDIUM-2: pin the exact custody scope names build_transport wires the
    # adapter with — a mutation swapping app_key_scope/app_secret_scope (or dropping one from
    # _KIS_MOCK_CUSTODY_SCOPES) previously went undetected, because dry_run never loads a
    # credential.
    assert transport._app_key_scope == "kis_mock.app_key"  # noqa: SLF001
    assert transport._app_secret_scope == "kis_mock.app_secret"  # noqa: SLF001


class _NullCustody:
    def load(self, scope: str) -> object:  # noqa: ARG002 - never invoked in this test
        raise AssertionError("not invoked by build_transport itself")


class _NullMonotonic:
    def now_ms(self) -> int:  # pragma: no cover - never invoked in this test
        return 0


class _NullEvidenceStore:
    def append(self, *args: object, **kwargs: object) -> None:  # noqa: ARG002
        return None  # a no-op evidence-store double — args are intentionally unused


# ===========================================================================
# resolve_transport_boot — the ONE call site _wiring.py uses
# ===========================================================================


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


# ===========================================================================
# compose_paper_runtime(transport_kind=KIS_MOCK) — e2e boot
# ===========================================================================


def test_e2e_boot_wires_a_kis_mock_transport_and_codec_digest_source(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root)
    # Coordinator posture stays False — this test is about WIRING, not admission (that's the
    # crossing-event test below).
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


# ===========================================================================
# The "정직 deny" crossing event — Coordinator PASSES, gateway denies honestly
# ===========================================================================


def test_crossing_event_coordinator_passes_gateway_denies_honestly(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Plan §4 T3's first half, landed here since it falls out of the wiring: with
    MOCK_STOCK_ORDER active (``profile_evidence_ok: true``), kis-mock (dry_run) transport, and
    ``nonlive_broker_consuming.admitted: true``, the Coordinator gate admits (no
    ``LIVE_SCOPE_NOT_AUTHORIZED`` halt) — but the gateway's own deferred safety-governance mesh
    (Phase 5, not yet wired) still denies honestly at the SEND_BOUNDARY_VERIFICATION step, before
    the transport is EVER called."""
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
    assert (
        results[0].pipeline is not None
    )  # Coordinator PASSED — the pipeline actually ran
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
    assert (
        flow.handed_off is True
    )  # steps 1-14 admitted; the attempt reached the gateway
    assert flow.handoff is not None
    assert (
        flow.handoff.accepted_for_transmission is not True
    )  # the gateway itself denied

    # No LIVE_SCOPE_NOT_AUTHORIZED halt was ever recorded for this event.
    live_scope_halts = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE payload_json LIKE '%LIVE_SCOPE_NOT_AUTHORIZED%'"
    ).fetchone()[0]
    assert live_scope_halts == 0

    # The gateway itself refused (SEND_REFUSED), never the transport.
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


# ===========================================================================
# Negative-grep — host/TR literals + os.environ over tos_runtime.compose
# ===========================================================================


def _compose_package_files() -> list[Path]:
    import tos_runtime.compose as pkg

    return list(Path(pkg.__file__).parent.glob("*.py"))


def _code_only(source: str) -> str:
    """Blank out every module/class/function docstring — mirrors
    ``tos/runtime/tests/transport/kis_mock/test_adapter.py``'s own helper of the same name.
    """
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
