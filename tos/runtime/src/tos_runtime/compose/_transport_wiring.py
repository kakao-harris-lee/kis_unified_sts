"""Transport-kind selection + KIS MOCK compose wiring (TOS KIS MOCK transport plan T2 lane C —"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from tos.brokeradapter import SyntheticFillPolicy, SyntheticPaperTransport, Transport
from tos.egressgw import SendSeal
from tos.egressgw.records import GatewayEvidenceRecord
from tos.workload import RuntimeIdentity

from tos_runtime.brokercap.instance import (
    REAL_ENVIRONMENT,
    InstanceDocument,
    load_instance_documents,
)
from tos_runtime.brokercap.scopes import BrokerScope, BrokerScopesConfig
from tos_runtime.brokercap.scopes import transport_nature as scope_transport_nature
from tos_runtime.compose._kis_credential_wiring import (
    KIS_MOCK_APP_KEY_SCOPE,
    KIS_MOCK_APP_SECRET_SCOPE,
    kis_mock_credential_session,
    kis_transport_pacing,
)
from tos_runtime.compose._nonlive_admission import _capability_tuples_mock_simulation
from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.adapter import EvidenceRecorder, KisMockTransport
from tos_runtime.transport.kis_mock.client import build_client
from tos_runtime.transport.kis_mock.config import (
    KisMockTransportConfig,
    load_kis_mock_transport_config,
)
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
from tos_runtime.venue_ledger.synthetic import (
    RecordingSyntheticTransport,
    SyntheticVenueLedger,
)

__all__ = [
    "KIS_MOCK_TRANSPORT_CONFIG_NAME",
    "SealRegistry",
    "TransportBootResult",
    "TransportKind",
    "TransportWiringError",
    "build_transport",
    "evidence_recorder",
    "instance_rest_bases",
    "load_transport_config",
    "refuse_custody_principal_mismatch",
    "refuse_transport_scope_mismatch",
    "resolve_transport_boot",
]

KIS_MOCK_TRANSPORT_CONFIG_NAME = "kis_mock_transport.yaml"

_KIS_MOCK_APP_KEY_SCOPE = KIS_MOCK_APP_KEY_SCOPE
_KIS_MOCK_APP_SECRET_SCOPE = KIS_MOCK_APP_SECRET_SCOPE
_KIS_MOCK_CUSTODY_SCOPES = (_KIS_MOCK_APP_KEY_SCOPE, _KIS_MOCK_APP_SECRET_SCOPE)

_REAL_ENVIRONMENT = REAL_ENVIRONMENT


class TransportKind(StrEnum):
    """The closed vocabulary ``compose --transport`` accepts (T2 lane C)."""

    SYNTHETIC = "synthetic"
    KIS_MOCK = "kis-mock"


class TransportWiringError(Exception):
    """A transport-kind / scope-consistency / custody-principal / host-seal fact could not be"""


def _document_for_environment(
    documents: tuple[InstanceDocument, ...], environment: str
) -> InstanceDocument | None:
    """The single ``documents`` entry whose own ``environment`` equals ``environment``, or"""
    matches = [
        document for document in documents if document.environment == environment
    ]
    return matches[0] if len(matches) == 1 else None


def load_transport_config(
    kind: TransportKind,
    config_dir: Path,
    broker_scopes: BrokerScopesConfig,
) -> KisMockTransportConfig | None:
    """Load ``kis_mock_transport.yaml`` for ``kis-mock`` (``None`` for ``synthetic``)."""
    if kind is TransportKind.SYNTHETIC:
        return None
    mock_rest_base, real_rest_base = instance_rest_bases(broker_scopes)
    return load_kis_mock_transport_config(
        config_dir / KIS_MOCK_TRANSPORT_CONFIG_NAME,
        instance_mock_rest_base=mock_rest_base,
        instance_real_rest_base=real_rest_base,
        codec_bound=True,
    )


def instance_rest_bases(broker_scopes: BrokerScopesConfig) -> tuple[str, str]:
    """The two host-seal facts ``(mock rest_base, REAL rest_base)`` from the INSTANCE documents"""
    scope = broker_scopes.active_scope
    if scope.instance is None or broker_scopes.instance_path is None:
        raise TransportWiringError(
            "kis-mock transport requires the active scope's own INSTANCE binding "
            f"({scope.name!r}.instance) and broker_scopes.instance_path — the host seal "
            "cannot be proven without both; refusing to boot"
        )
    documents = load_instance_documents(
        broker_scopes.instance_path, expected_sha256=broker_scopes.instance_sha256
    )
    mock_document = _document_for_environment(documents, scope.instance.environment)
    real_document = _document_for_environment(documents, _REAL_ENVIRONMENT)
    if mock_document is None or mock_document.rest_base is None:
        raise TransportWiringError(
            f"kis-mock transport: no unique INSTANCE document for environment "
            f"{scope.instance.environment!r} with a known rest_base at "
            f"{broker_scopes.instance_path} — refusing to boot"
        )
    if real_document is None or real_document.rest_base is None:
        raise TransportWiringError(
            f"kis-mock transport: no unique INSTANCE document for environment "
            f"{_REAL_ENVIRONMENT!r} with a known rest_base at {broker_scopes.instance_path} "
            "— the REAL host cannot be excluded without it; refusing to boot"
        )
    return mock_document.rest_base, real_document.rest_base


def refuse_transport_scope_mismatch(
    kind: TransportKind, broker_scopes: BrokerScopesConfig
) -> None:
    """Refuse boot when ``kind`` and the active scope disagree about whether this runtime reaches"""
    scope = broker_scopes.active_scope
    nature = scope_transport_nature(scope)
    if kind is TransportKind.KIS_MOCK:
        if nature.reaches_broker is not True or not _capability_tuples_mock_simulation(
            scope
        ):
            raise TransportWiringError(
                f"kis-mock transport requires active scope {scope.name!r} to be "
                "broker-reaching with every capability tuple MOCK-shaped under "
                "BROKER_SIMULATION — refusing to boot"
            )
    else:
        if nature.reaches_broker is not False:
            raise TransportWiringError(
                f"synthetic transport requires active scope {scope.name!r} to be "
                "non-broker-reaching (reaches_broker is False) — refusing to boot"
            )


def refuse_custody_principal_mismatch(
    kind: TransportKind, custody: FileCustody, active_scope: BrokerScope
) -> None:
    """Refuse boot when a ``kis-mock`` custody scope's own manifest principal does not equal the"""
    if kind is not TransportKind.KIS_MOCK:
        return
    for scope_name in _KIS_MOCK_CUSTODY_SCOPES:
        principal = custody.scope_principal(scope_name)
        if principal != active_scope.principal:
            raise TransportWiringError(
                f"custody scope {scope_name!r} principal {principal!r} does not equal "
                f"active scope {active_scope.name!r}'s own principal "
                f"{active_scope.principal!r} — one principal must name both the "
                "credential and the route (plan §2 decision 4); refusing to boot"
            )


@dataclass(frozen=True)
class TransportBootResult:
    """:func:`resolve_transport_boot`'s return value."""

    transport_config: KisMockTransportConfig | None
    extra_config_files: tuple[Path, ...]


def resolve_transport_boot(
    kind: TransportKind,
    config_dir: Path,
    broker_scopes: BrokerScopesConfig,
    custody: FileCustody,
) -> TransportBootResult:
    """The ONE call site :mod:`tos_runtime.compose._wiring` uses during boot for every"""
    transport_config = load_transport_config(kind, config_dir, broker_scopes)
    refuse_transport_scope_mismatch(kind, broker_scopes)
    refuse_custody_principal_mismatch(kind, custody, broker_scopes.active_scope)
    extra_config_files = (
        (config_dir / KIS_MOCK_TRANSPORT_CONFIG_NAME,)
        if kind is TransportKind.KIS_MOCK
        else ()
    )
    return TransportBootResult(
        transport_config=transport_config, extra_config_files=extra_config_files
    )


@dataclass
class SealRegistry:
    """Captures the kernel gateway's own ``SEND_SEALED`` evidence record's"""

    _seals: dict[str, SendSeal] = field(default_factory=dict)

    def capture(self, record: GatewayEvidenceRecord) -> None:
        """The :class:`~tos_runtime.evidence.sinks.GatewayEvidenceSinkAdapter` ``on_record``"""
        if record.attempt_id is None:
            return
        if record.kind == "SEND_SEALED" and record.send_seal is not None:
            self._seals[record.attempt_id] = record.send_seal
        elif record.kind == "SEND_REFUSED":
            self._seals.pop(record.attempt_id, None)

    def __call__(self, attempt_id: str) -> SendSeal | None:
        """The adapter's own ``SealLookup.__call__`` — single-use (``dict.pop``)."""
        return self._seals.pop(attempt_id, None)


def _evidence_recorder(
    store: SqliteEvidenceStore, runtime_identity: RuntimeIdentity
) -> EvidenceRecorder:
    """Adapt :class:`~tos_runtime.transport.kis_mock.adapter.KisMockTransport`'s injected"""

    def _record(kind: str, fields: Mapping[str, Any]) -> None:
        store.append(
            dict(fields),
            kind=kind,
            record_class=kind,
            runtime_identity=runtime_identity,
        )

    return _record


evidence_recorder = _evidence_recorder


def _build_synthetic_transport(
    *,
    venue_ledger: SyntheticVenueLedger | None,
    trading_date_now: Callable[[], str | None] | None,
) -> Transport:
    """The ``synthetic`` branch of :func:`build_transport` (split out for the function budget)."""
    synthetic = SyntheticPaperTransport(
        SyntheticFillPolicy(fill_numerator=1, fill_denominator=1, lot_size=Decimal("1"))
    )
    if venue_ledger is None:
        return synthetic
    if trading_date_now is None:
        raise TransportWiringError(
            "build_transport: a venue ledger requires the runtime's trusted trading-date "
            "reader — an undated venue row carries no order_date for the witness's "
            "cross-reference join at all; refusing to boot"
        )
    return RecordingSyntheticTransport(
        synthetic, venue_ledger, trading_date_now=trading_date_now
    )


def build_transport(
    kind: TransportKind,
    *,
    transport_config: KisMockTransportConfig | None,
    custody: CredentialCustody,
    monotonic: MonotonicSource,
    seal_lookup: SealRegistry,
    evidence_store: SqliteEvidenceStore,
    runtime_identity: RuntimeIdentity,
    trading_date_now: Callable[[], str | None] | None = None,
    credential_sessions: KisCredentialSessions,
    venue_ledger: SyntheticVenueLedger | None = None,
) -> Transport:
    """Construct the selected transport (module docstring item 6)."""
    if kind is TransportKind.SYNTHETIC:
        return _build_synthetic_transport(
            venue_ledger=venue_ledger, trading_date_now=trading_date_now
        )
    if venue_ledger is not None:
        raise TransportWiringError(
            f"build_transport: a venue ledger was supplied for a {kind.value!r} transport — "
            "the ledger is the SYNTHETIC venue's own record and must never be written for a "
            "transport that reaches a broker; refusing to boot"
        )
    if transport_config is None:
        raise TransportWiringError(
            "build_transport: kis-mock requires a non-None transport_config — "
            "resolve_transport_boot always supplies one"
        )
    client = build_client(transport_config)
    return KisMockTransport(
        config=transport_config,
        client=client,
        credential_session=kis_mock_credential_session(
            credential_sessions,
            client=client,
            token_endpoint_base=transport_config.endpoint_rest_base,
            token_path=transport_config.token_path,
            token_reissue_min_interval_s=transport_config.token_reissue_min_interval_s,
            pacing=kis_transport_pacing(transport_config),
        ),
        monotonic=monotonic,
        seal_lookup=seal_lookup,
        evidence_sink=_evidence_recorder(evidence_store, runtime_identity),
        trading_date_now=trading_date_now,
    )
