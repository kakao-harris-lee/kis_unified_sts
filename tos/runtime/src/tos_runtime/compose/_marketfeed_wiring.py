"""``tos_runtime.compose._marketfeed_wiring`` — the tick-scheduler compose wiring (TOS tick-source"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import CanonicalizationScheme
from tos.workload import RuntimeIdentity

from tos_runtime._named_tbd import reject_named_tbd
from tos_runtime.brokercap.instance import REAL_ENVIRONMENT, load_instance_documents
from tos_runtime.brokercap.scopes import BrokerScopesConfig
from tos_runtime.calendar.owner import SessionFactsOwner
from tos_runtime.compose._kis_credential_wiring import (
    kis_mock_credential_session,
    kis_quote_pacing,
)
from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.marketfeed.journal import JsonLinesObservationJournal
from tos_runtime.marketfeed.policy import (
    CRITICAL_INPUT_POLICY_CONFIG_NAME,
    load_critical_input_policy,
)
from tos_runtime.marketfeed.ports import ObservationIntake
from tos_runtime.marketfeed.scheduler import PassBudget, TickScheduler
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME, SqliteSnapshotStore
from tos_runtime.marketfeed.time_pacer import TimeEvaluationPacer
from tos_runtime.marketfeed.time_projection import (
    _DELAY_BOUND_FIELDS,
    RuntimeTimeProjection,
)
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
from tos_runtime.transport.kis_quote.adapter import (
    KisQuoteObservationIntake,
    build_quote_client,
)
from tos_runtime.transport.kis_quote.config import load_kis_quote_transport_config

__all__ = [
    "KIS_QUOTE_TRANSPORT_CONFIG_NAME",
    "MARKETFEED_CONFIG_NAME",
    "MarketFeedConfig",
    "MarketFeedConfigError",
    "build_tick_scheduler",
    "load_marketfeed_config",
    "resolve_kis_instance_rest_bases",
]

MARKETFEED_CONFIG_NAME = "marketfeed.yaml"

KIS_QUOTE_TRANSPORT_CONFIG_NAME = "kis_quote.yaml"

_VALID_INTAKE_KINDS = ("journal", "kis_quote")

_REAL_ENVIRONMENT = REAL_ENVIRONMENT

_STR_FIELDS: tuple[str, ...] = (
    "instrument_class",
    "account",
    "direction",
    "quantity_basis",
    "unit",
)
_INT_FIELDS: tuple[str, ...] = (
    "poll_interval_ms",
    "snapshot_age_bound",
    "interval_width",
    "time_evaluate_closed_interval_ms",
)


class MarketFeedConfigError(Exception):
    """Raised when ``marketfeed.yaml`` is missing, malformed, or carries an unfilled"""


@dataclass(frozen=True)
class MarketFeedConfig:
    """A loaded, validated ``marketfeed.yaml`` (module docstring)."""

    instruments: tuple[str, ...]
    instrument_class: str
    account: str
    direction: str
    quantity_basis: str
    unit: str
    intake_kind: str
    journal_path: Path | None
    journal_pass_allowance_ms: int | None
    poll_interval_ms: int
    snapshot_age_bound: int
    interval_width: int
    time_evaluate_closed_interval_ms: int


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MarketFeedConfigError(f"marketfeed config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MarketFeedConfigError(
            f"marketfeed config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise MarketFeedConfigError(
            f"marketfeed config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise MarketFeedConfigError(
            f"{path}: marketfeed config must be a top-level mapping"
        )
    return raw


def _require_str(raw: Any, key: str, path: Path) -> str:
    value = raw.get(key) if isinstance(raw, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise MarketFeedConfigError(
            f"{path}: {key!r} is missing, still null (named-TBD), or not a non-empty string"
        )
    reject_named_tbd(
        value, field=key, context=str(path), error_cls=MarketFeedConfigError
    )
    return value


def _require_int(raw: Any, key: str, path: Path) -> int:
    value = raw.get(key) if isinstance(raw, dict) else None
    if isinstance(value, bool) or not isinstance(value, int):
        raise MarketFeedConfigError(
            f"{path}: {key!r} is missing, still null (named-TBD), or not an int"
        )
    return value


def _require_instruments(raw: Any, path: Path) -> tuple[str, ...]:
    value = raw.get("instruments") if isinstance(raw, dict) else None
    if not isinstance(value, list) or not value:
        raise MarketFeedConfigError(
            f"{path}: 'instruments' is missing, still null (named-TBD), or not a non-empty "
            "list — a bare string is not accepted (the list shape is what lets a "
            "misconfigured multi-symbol deployment be expressed, and therefore refused)"
        )
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise MarketFeedConfigError(
            f"{path}: every 'instruments' entry must be a non-empty string"
        )
    for item in value:
        reject_named_tbd(
            item,
            field="instruments",
            context=str(path),
            error_cls=MarketFeedConfigError,
        )
    return tuple(value)


def _require_intake_kind(raw: Any, path: Path) -> str:
    value = raw.get("intake_kind") if isinstance(raw, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise MarketFeedConfigError(
            f"{path}: 'intake_kind' is missing, still null (named-TBD), or not a non-empty "
            f"string — must be one of {_VALID_INTAKE_KINDS!r} (module docstring: intake "
            "selection never defaults)"
        )
    if value not in _VALID_INTAKE_KINDS:
        raise MarketFeedConfigError(
            f"{path}: intake_kind={value!r} is not one of {_VALID_INTAKE_KINDS!r}"
        )
    return value


def _resolve_journal_path(raw: Any, path: Path, *, intake_kind: str) -> Path | None:
    """Enforce the module docstring's "journal_path is required XOR forbidden" rule."""
    present = isinstance(raw, dict) and raw.get("journal_path") is not None
    if intake_kind == "journal":
        if not present:
            raise MarketFeedConfigError(
                f"{path}: 'journal_path' is missing or still null (named-TBD) — required when "
                "intake_kind: journal"
            )
        return Path(_require_str(raw, "journal_path", path))
    if present:
        raise MarketFeedConfigError(
            f"{path}: 'journal_path' is set but intake_kind={intake_kind!r} — a non-journal "
            "intake_kind must leave journal_path null (module docstring: neither intake kind "
            "is a silent fallback for the other, and a stray journal_path would look "
            "load-bearing while being ignored)"
        )
    return None


def _resolve_journal_pass_allowance_ms(
    raw: Any, path: Path, *, intake_kind: str
) -> int | None:
    """Enforce the module docstring's "``journal_pass_allowance_ms`` is required XOR"""
    present = isinstance(raw, dict) and raw.get("journal_pass_allowance_ms") is not None
    if intake_kind != "journal":
        if present:
            raise MarketFeedConfigError(
                f"{path}: 'journal_pass_allowance_ms' is set but "
                f"intake_kind={intake_kind!r} — this key budgets the journal poll phase "
                "only and is not read for any other intake kind (module docstring), so a "
                "stray value would look load-bearing while being ignored"
            )
        return None
    if not present:
        raise MarketFeedConfigError(
            f"{path}: 'journal_pass_allowance_ms' is missing or still null (named-TBD) — "
            "required when intake_kind: journal, because the freshness budget cannot be "
            "checked without the runtime's own worst-case pass duration"
        )
    value = _require_int(raw, "journal_pass_allowance_ms", path)
    if value <= 0:
        raise MarketFeedConfigError(
            f"{path}: 'journal_pass_allowance_ms' must be positive (got {value}) — a "
            "zero or negative allowance asserts a pass that costs no time, which would "
            "hand the whole budget to poll_interval_ms and re-open the very gap this key "
            "exists to close"
        )
    return value


def load_marketfeed_config(path: Path) -> MarketFeedConfig:
    """Load and fail-closed-validate ``marketfeed.yaml`` from ``path`` (module docstring)."""
    raw = _load_mapping(path)
    instruments = _require_instruments(raw, path)
    intake_kind = _require_intake_kind(raw, path)
    journal_path = _resolve_journal_path(raw, path, intake_kind=intake_kind)
    journal_pass_allowance_ms = _resolve_journal_pass_allowance_ms(
        raw, path, intake_kind=intake_kind
    )
    str_values = {field: _require_str(raw, field, path) for field in _STR_FIELDS}
    int_values = {field: _require_int(raw, field, path) for field in _INT_FIELDS}
    if int_values["time_evaluate_closed_interval_ms"] <= 0:
        raise MarketFeedConfigError(
            f"{path}: 'time_evaluate_closed_interval_ms' must be positive — a closed session "
            "that is never re-evaluated never sees the session open"
        )
    return MarketFeedConfig(
        instruments=instruments,
        instrument_class=str_values["instrument_class"],
        account=str_values["account"],
        direction=str_values["direction"],
        quantity_basis=str_values["quantity_basis"],
        unit=str_values["unit"],
        intake_kind=intake_kind,
        journal_path=journal_path,
        journal_pass_allowance_ms=journal_pass_allowance_ms,
        poll_interval_ms=int_values["poll_interval_ms"],
        snapshot_age_bound=int_values["snapshot_age_bound"],
        interval_width=int_values["interval_width"],
        time_evaluate_closed_interval_ms=int_values["time_evaluate_closed_interval_ms"],
    )


def _load_config_within_freshness_budget(
    path: Path, time_config: TrustworthyTimeConfig
) -> MarketFeedConfig:
    """Load ``marketfeed.yaml`` and, for ``intake_kind: journal``, refuse a pacing that"""
    config = load_marketfeed_config(path)
    if config.intake_kind != "journal":
        return config
    assert config.journal_pass_allowance_ms is not None
    delay_bound_sum: int = sum(
        getattr(time_config, field_name) for field_name in _DELAY_BOUND_FIELDS
    )
    budget_ms = time_config.max_time_conservative_freshness_age_ms - delay_bound_sum
    runtime_share_ms = config.poll_interval_ms + config.journal_pass_allowance_ms
    if runtime_share_ms > budget_ms:
        raise MarketFeedConfigError(
            f"{path}: intake_kind: journal paces outside the conservative freshness "
            f"budget — poll_interval_ms={config.poll_interval_ms} + "
            f"journal_pass_allowance_ms={config.journal_pass_allowance_ms} = "
            f"{runtime_share_ms} ms, but the budget is "
            f"MAX_time_conservative_freshness_age_ms="
            f"{time_config.max_time_conservative_freshness_age_ms} - "
            f"sum(delay_bounds)={delay_bound_sum} = {budget_ms} ms, which leaves the "
            f"upstream collector {budget_ms - runtime_share_ms} ms of headroom. An "
            "observation arriving just after a pass would then be read STALE and dropped "
            "(consumed, never retried) — refusing to boot"
        )
    return config


def _time_pacer_pass(
    config: MarketFeedConfig,
    time_service: TrustworthyTimeService,
    session_owner: SessionFactsOwner,
    monotonic: MonotonicSource,
) -> Callable[[], bool]:
    """The periodic time-health evaluation the ``run`` loop owes the time service (plan"""

    def session_known_closed() -> bool:
        context = session_owner.session_context(config.instrument_class)
        return context is not None and not context.is_open

    return TimeEvaluationPacer(
        evaluate=time_service.evaluate,
        session_known_closed=session_known_closed,
        closed_interval_ms=config.time_evaluate_closed_interval_ms,
        monotonic_ms=monotonic.now_ms,
    ).before_decide


def resolve_kis_instance_rest_bases(
    broker_scopes: BrokerScopesConfig,
) -> tuple[str, str]:
    """Resolve the (MOCK, REAL) INSTANCE ``rest_base`` host-seal facts for the ``kis_quote``"""
    scope = broker_scopes.active_scope
    if scope.instance is None or broker_scopes.instance_path is None:
        raise MarketFeedConfigError(
            "intake_kind: kis_quote requires the active broker scope's own INSTANCE binding "
            f"({scope.name!r}.instance) and broker_scopes.instance_path — the host seal cannot "
            "be proven without both; refusing to boot"
        )
    documents = load_instance_documents(
        broker_scopes.instance_path, expected_sha256=broker_scopes.instance_sha256
    )
    mock_document = next(
        (d for d in documents if d.environment == scope.instance.environment), None
    )
    real_document = next(
        (d for d in documents if d.environment == _REAL_ENVIRONMENT), None
    )
    if mock_document is None or mock_document.rest_base is None:
        raise MarketFeedConfigError(
            f"intake_kind: kis_quote: no unique INSTANCE document for environment "
            f"{scope.instance.environment!r} with a known rest_base at "
            f"{broker_scopes.instance_path} — refusing to boot"
        )
    if real_document is None or real_document.rest_base is None:
        raise MarketFeedConfigError(
            f"intake_kind: kis_quote: no unique INSTANCE document for environment "
            f"{_REAL_ENVIRONMENT!r} with a known rest_base at {broker_scopes.instance_path} — "
            "the REAL host cannot be excluded without it; refusing to boot"
        )
    return mock_document.rest_base, real_document.rest_base


def _evidence_recorder(
    store: SqliteEvidenceStore, runtime_identity: RuntimeIdentity
) -> Any:
    """Adapt the KIS quote intake's injected ``EvidenceRecorder`` Protocol (``record(kind,"""

    def _record(kind: str, fields: Mapping[str, Any]) -> None:
        store.append(
            dict(fields),
            kind=kind,
            record_class=kind,
            runtime_identity=runtime_identity,
        )

    return _record


def _build_intake(
    config: MarketFeedConfig,
    *,
    config_dir: Path,
    custody: CredentialCustody,
    monotonic: MonotonicSource,
    broker_scopes: BrokerScopesConfig,
    evidence_store: SqliteEvidenceStore,
    runtime_identity: RuntimeIdentity,
    credential_sessions: KisCredentialSessions | None,
) -> ObservationIntake:
    """Build the ``ObservationIntake`` config.intake_kind selects (module docstring) — the ONE"""
    if config.intake_kind == "journal":
        assert config.journal_path is not None
        return JsonLinesObservationJournal(config.journal_path)
    assert config.intake_kind == "kis_quote"
    instance_mock_rest_base, instance_real_rest_base = resolve_kis_instance_rest_bases(
        broker_scopes
    )
    quote_config = load_kis_quote_transport_config(
        config_dir / KIS_QUOTE_TRANSPORT_CONFIG_NAME,
        instance_mock_rest_base=instance_mock_rest_base,
        instance_real_rest_base=instance_real_rest_base,
    )
    if credential_sessions is None:
        raise MarketFeedConfigError(
            "intake_kind: kis_quote needs the boot's KIS credential registry "
            "(ComposedRuntime.kis_credential_sessions) — refusing to build a private one, which "
            "would give this app key a second token lifecycle (C-2 decision (C))"
        )
    client = build_quote_client(quote_config)
    return KisQuoteObservationIntake(
        config=quote_config,
        client=client,
        credential_session=kis_mock_credential_session(
            credential_sessions,
            client=client,
            token_endpoint_base=quote_config.endpoint_rest_base,
            token_path=quote_config.token_path,
            token_reissue_min_interval_s=quote_config.token_reissue_min_interval_s,
            pacing=kis_quote_pacing(quote_config),
        ),
        monotonic=monotonic,
        evidence_sink=_evidence_recorder(evidence_store, runtime_identity),
    )


def _pass_budget(
    config: MarketFeedConfig, monotonic: MonotonicSource
) -> PassBudget | None:
    """This config's per-pass measurement, or ``None`` when it declares no allowance."""
    if config.journal_pass_allowance_ms is None:
        return None
    return PassBudget(
        monotonic=monotonic, allowance_ms=config.journal_pass_allowance_ms
    )


def _build_time_projection(
    config: MarketFeedConfig,
    time_config: TrustworthyTimeConfig,
    time_service: TrustworthyTimeService,
    session_owner: SessionFactsOwner,
) -> RuntimeTimeProjection:
    """The lane-C time projection the scheduler resolves through — split out of"""
    return RuntimeTimeProjection(
        config=time_config,
        time_service=time_service,
        session_owner=session_owner,
        instrument_class=config.instrument_class,
        snapshot_age_bound=config.snapshot_age_bound,
        interval_width=config.interval_width,
    )


def build_tick_scheduler(
    *,
    config_dir: Path,
    data_dir: Path,
    scheme: CanonicalizationScheme,
    time_config: TrustworthyTimeConfig,
    time_service: TrustworthyTimeService,
    session_owner: SessionFactsOwner,
    driver: EngineDriver | None,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    custody: CredentialCustody,
    monotonic: MonotonicSource,
    broker_scopes: BrokerScopesConfig,
    runtime_identity: RuntimeIdentity,
    credential_sessions: KisCredentialSessions | None,
    after_pass: Callable[[], None] | None = None,
) -> TickScheduler | None:
    """Build the tick scheduler, or ``None`` when this wave is not configured (module docstring)."""
    config_path = config_dir / MARKETFEED_CONFIG_NAME
    if not config_path.is_file():
        return None
    config = _load_config_within_freshness_budget(config_path, time_config)
    policy = load_critical_input_policy(
        config_dir / CRITICAL_INPUT_POLICY_CONFIG_NAME, scheme=scheme
    )
    intake = _build_intake(
        config,
        config_dir=config_dir,
        custody=custody,
        monotonic=monotonic,
        broker_scopes=broker_scopes,
        evidence_store=evidence_store,
        runtime_identity=runtime_identity,
        credential_sessions=credential_sessions,
    )
    time_projection = _build_time_projection(
        config, time_config, time_service, session_owner
    )
    return TickScheduler(
        instruments=config.instruments,
        instrument_class=config.instrument_class,
        account=config.account,
        direction=config.direction,
        quantity_basis=config.quantity_basis,
        unit=config.unit,
        policy=policy,
        scheme=scheme,
        intake=intake,
        store=SqliteSnapshotStore(data_dir / MARKETFEED_FILE_NAME),
        time_projection=time_projection,
        time_service=time_service,
        session_owner=session_owner,
        driver=driver,
        inbox=inbox,
        evidence_store=evidence_store,
        poll_interval_ms=config.poll_interval_ms,
        before_decide=_time_pacer_pass(config, time_service, session_owner, monotonic),
        after_pass=after_pass,
        pass_budget=_pass_budget(config, monotonic),
    )
