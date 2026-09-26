"""``tos_runtime.compose._marketfeed_wiring`` — the tick-scheduler compose wiring (TOS tick-source
wave, plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §4 lane D).

Loads ``marketfeed.yaml`` (fail-closed, the SAME named-TBD idiom
:mod:`tos_runtime.compose._engine_config` already ships).

**Two distinct absent-file cases — do not conflate them (2026-09-17 correction; an earlier
revision of this paragraph claimed both were the same "returns None" case, which the code never
did).** ``marketfeed.yaml`` ABSENT is the ONLY case that makes :func:`build_tick_scheduler` return
``None`` — the SAME "files exist" idiom :func:`~tos_runtime.compose._session_wiring
.build_nontrade_processor`'s own call site uses for its single optional ``nontrade.yaml``: an
operator who has not yet adopted this wave at all keeps composing exactly as before (module
docstring of ``ComposedRuntime.marketfeed`` — a legitimate state, never a boot refusal). But once
``marketfeed.yaml`` EXISTS, ``critical_input_policy.yaml`` is no longer optional: this module
checks only ``marketfeed.yaml``'s existence before proceeding, then calls
:func:`~tos_runtime.marketfeed.policy.load_critical_input_policy` unconditionally, and THAT
loader raises :class:`~tos_runtime.marketfeed.policy.CriticalInputPolicyConfigError` on a missing
file (its own docstring's ``Raises:`` clause) — never swallowed or downgraded to ``None`` here. An
operator who configured a tick source but did not govern it is refused at boot, not handed a
runtime with a silently absent tick source; :func:`build_tick_scheduler`'s own ``Raises:`` clause
already documented this exception correctly, only this module-level paragraph's blanket "absent
either file" phrasing was wrong.

**Intake selection is explicit, fail-closed, and never defaults (W2 lane,
plan ``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`` §4 W2).**
``marketfeed.yaml``'s ``intake_kind`` names EXACTLY ONE of two
:class:`~tos_runtime.marketfeed.ports.ObservationIntake` implementations —
``"journal"`` (:class:`~tos_runtime.marketfeed.journal.JsonLinesObservationJournal`, this
module's original, file-backed intake) or ``"kis_quote"``
(:class:`~tos_runtime.transport.kis_quote.adapter.KisQuoteObservationIntake`, a real KIS
모의투자 quote HTTP poll). Neither is a fallback for the other: an unrecognized or missing
``intake_kind`` refuses to load, and each kind's own required fields are validated only for
that kind — ``journal_path`` is required (and must be the ONLY intake-shaped field present) when
``intake_kind: journal``; ``kis_quote.yaml`` must exist alongside ``marketfeed.yaml`` (and
``journal_path`` must be ABSENT) when ``intake_kind: kis_quote``. A deployment cannot silently end
up on the file journal because a real transport config was misnamed, nor silently poll a live KIS
endpoint because an operator forgot to set ``intake_kind`` — both are named-TBD refusals.

Building the ``kis_quote`` intake needs the SAME two INSTANCE host-seal facts (MOCK/REAL
``rest_base``) :mod:`tos_runtime.compose._transport_wiring`'s own ``load_transport_config``
resolves for the order transport — resolved independently here (module-local
:func:`_resolve_kis_instance_rest_bases`, duplicated rather than imported from that sibling
wiring module: this module has no dependency on which *order* transport kind is active, and a
deployment may run the KIS quote intake with a purely synthetic order transport, or vice versa —
coupling the two would make one unavailable without the other for no structural reason).

**Why this is called AFTER ``apply_recovery_barrier``, unlike ``venue`` (attached right after
``_finalize``).** :class:`~tos_runtime.marketfeed.scheduler.TickScheduler` captures ``driver`` at
CONSTRUCTION time and holds it for the rest of the process's life — unlike
:meth:`~tos_runtime.compose._types.ComposedRuntime.observe_nontrade`, which re-reads
``self.driver`` fresh on every call. A HOLD verdict detaches ``composed.driver`` (sets it to
``None`` — see that field's own docstring); building the scheduler before the barrier runs would
freeze the PRE-barrier driver reference, so a HOLD would go unnoticed by every subsequent tick.
Calling this module after :func:`~tos_runtime.compose._recovery_wiring.apply_recovery_barrier`
(and after the SAME ``session_facts_owner`` local :func:`~tos_runtime.compose._session_wiring
.apply_session_wiring` itself attaches already exists) guarantees ``composed.driver`` already
reflects the FINAL barrier verdict.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``pyyaml`` + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``, no network, no clock (every clock/session/driver
collaborator is injected by the caller, exactly like every other ``_*_wiring`` module).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import CanonicalizationScheme
from tos.workload import RuntimeIdentity

from tos_runtime._named_tbd import reject_named_tbd
from tos_runtime.brokercap.instance import load_instance_documents
from tos_runtime.brokercap.scopes import BrokerScopesConfig
from tos_runtime.calendar.owner import SessionFactsOwner
from tos_runtime.compose._kis_credential_wiring import kis_mock_credential_session
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
from tos_runtime.marketfeed.scheduler import TickScheduler
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME, SqliteSnapshotStore
from tos_runtime.marketfeed.time_pacer import TimeEvaluationPacer
from tos_runtime.marketfeed.time_projection import RuntimeTimeProjection
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
]

#: The runtime INSTANCE file name (distinct from ``marketfeed.example.yaml``).
MARKETFEED_CONFIG_NAME = "marketfeed.yaml"

#: The KIS quote transport's own runtime INSTANCE file name (distinct from
#: ``kis_quote.example.yaml``) — read ONLY when ``intake_kind: kis_quote`` (module docstring).
KIS_QUOTE_TRANSPORT_CONFIG_NAME = "kis_quote.yaml"

#: The two ``intake_kind`` values this wiring recognizes — anything else is a fail-closed
#: refusal at load (module docstring's "never defaults" note).
_VALID_INTAKE_KINDS = ("journal", "kis_quote")

#: Mirrors ``tos_runtime.compose._transport_wiring``'s own ``_REAL_ENVIRONMENT`` literal
#: (duplicated, not imported — module docstring's "no dependency on the order transport wiring"
#: note; both name the SAME Broker Capability Profile INSTANCE environment label).
_REAL_ENVIRONMENT = "REAL_PROD"

#: The scalar-string fields required regardless of ``intake_kind`` (``journal_path`` is NOT
#: here — module docstring: it is required/forbidden depending on ``intake_kind``, validated
#: separately by :func:`_require_journal_path_matches_intake_kind`).
_STR_FIELDS: tuple[str, ...] = (
    "instrument_class",
    "account",
    "direction",
    "quantity_basis",
    "unit",
)
#: The scalar-int fields.
_INT_FIELDS: tuple[str, ...] = (
    "poll_interval_ms",
    "snapshot_age_bound",
    "interval_width",
    "time_evaluate_closed_interval_ms",
)


class MarketFeedConfigError(Exception):
    """Raised when ``marketfeed.yaml`` is missing, malformed, or carries an unfilled
    (named-TBD, still-``null``) required leaf — fail-closed at load, never a silent default
    (module docstring)."""


@dataclass(frozen=True)
class MarketFeedConfig:
    """A loaded, validated ``marketfeed.yaml`` (module docstring)."""

    instruments: tuple[str, ...]
    instrument_class: str
    account: str
    direction: str
    quantity_basis: str
    unit: str
    #: Which :class:`~tos_runtime.marketfeed.ports.ObservationIntake` this deployment builds —
    #: ``"journal"`` or ``"kis_quote"`` (module docstring; :data:`_VALID_INTAKE_KINDS`).
    intake_kind: str
    #: Required (non-``None``) iff ``intake_kind == "journal"``; MUST be ``None`` otherwise
    #: (module docstring's "never defaults" note — enforced by
    #: :func:`_require_journal_path_matches_intake_kind`).
    journal_path: Path | None
    poll_interval_ms: int
    snapshot_age_bound: int
    interval_width: int
    #: Time-health evaluation spacing while the session is closed (plan 2026-09-26 periodic
    #: time eval, operator option 나 — every pass while open, this interval while closed).
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
    """Enforce the module docstring's "journal_path is required XOR forbidden" rule.

    Args:
        raw: The loaded YAML mapping.
        path: The config file path (for error messages).
        intake_kind: The already-validated ``intake_kind`` value.

    Raises:
        MarketFeedConfigError: ``journal_path`` is missing/null when ``intake_kind == "journal"``,
            or present (non-null) when ``intake_kind != "journal"`` — a stale ``journal_path``
            left in the file when an operator switches to ``kis_quote`` is refused rather than
            silently ignored, so a config never carries a field that looks load-bearing but
            is not.
    """
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


def load_marketfeed_config(path: Path) -> MarketFeedConfig:
    """Load and fail-closed-validate ``marketfeed.yaml`` from ``path`` (module docstring).

    Raises:
        MarketFeedConfigError: The file is missing/unreadable/not valid YAML/not a mapping, or
            any required leaf is absent, ``null``, or the wrong type; ``intake_kind`` is not one
            of :data:`_VALID_INTAKE_KINDS`; or ``journal_path`` disagrees with ``intake_kind``
            (module docstring).
    """
    raw = _load_mapping(path)
    instruments = _require_instruments(raw, path)
    intake_kind = _require_intake_kind(raw, path)
    journal_path = _resolve_journal_path(raw, path, intake_kind=intake_kind)
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
        poll_interval_ms=int_values["poll_interval_ms"],
        snapshot_age_bound=int_values["snapshot_age_bound"],
        interval_width=int_values["interval_width"],
        time_evaluate_closed_interval_ms=int_values["time_evaluate_closed_interval_ms"],
    )


def _time_pacer_pass(
    config: MarketFeedConfig,
    time_service: TrustworthyTimeService,
    session_owner: SessionFactsOwner,
    monotonic: MonotonicSource,
) -> Callable[[], bool]:
    """The periodic time-health evaluation the ``run`` loop owes the time service (plan
    2026-09-26 periodic time eval, W1 — operator option 나). Its closed input is the SAME
    ``session_context`` the scheduler gates on, so the two can never disagree; no context (time
    untrusted) is unknown, not closed (``time_pacer`` module docstring)."""

    def session_known_closed() -> bool:
        context = session_owner.session_context(config.instrument_class)
        return context is not None and not context.is_open

    return TimeEvaluationPacer(
        evaluate=time_service.evaluate,
        session_known_closed=session_known_closed,
        closed_interval_ms=config.time_evaluate_closed_interval_ms,
        monotonic_ms=monotonic.now_ms,
    ).before_pass


def _resolve_kis_instance_rest_bases(
    broker_scopes: BrokerScopesConfig,
) -> tuple[str, str]:
    """Resolve the (MOCK, REAL) INSTANCE ``rest_base`` host-seal facts for the ``kis_quote``
    intake — the SAME two facts
    :func:`tos_runtime.compose._transport_wiring.load_transport_config` resolves for the order
    transport, independently re-derived here (module docstring).

    Args:
        broker_scopes: The already-loaded scope table (unconditionally available at this
            module's call site regardless of which order-transport kind is active).

    Returns:
        ``(instance_mock_rest_base, instance_real_rest_base)``.

    Raises:
        MarketFeedConfigError: The active scope declares no ``instance`` block,
            ``broker_scopes.instance_path`` is unset, or either the MOCK or REAL document
            cannot be uniquely resolved with a known ``rest_base`` — the host seal cannot be
            proven without every one of these facts.
    """
    scope = broker_scopes.active_scope
    if scope.instance is None or broker_scopes.instance_path is None:
        raise MarketFeedConfigError(
            "intake_kind: kis_quote requires the active broker scope's own INSTANCE binding "
            f"({scope.name!r}.instance) and broker_scopes.instance_path — the host seal cannot "
            "be proven without both; refusing to boot"
        )
    documents = load_instance_documents(broker_scopes.instance_path)
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
    """Adapt the KIS quote intake's injected ``EvidenceRecorder`` Protocol (``record(kind,
    fields)``) onto :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.append` — mirrors
    :mod:`tos_runtime.compose._transport_wiring`'s own ``_evidence_recorder`` (duplicated, not
    imported — same "no dependency on the order transport wiring" reasoning as
    :func:`_resolve_kis_instance_rest_bases`)."""

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
    time_service: TrustworthyTimeService,
    broker_scopes: BrokerScopesConfig,
    evidence_store: SqliteEvidenceStore,
    runtime_identity: RuntimeIdentity,
    credential_sessions: KisCredentialSessions | None,
) -> ObservationIntake:
    """Build the ``ObservationIntake`` config.intake_kind selects (module docstring) — the ONE
    branch point between the two intake kinds; every other collaborator below is intake-kind-
    agnostic. ``custody``/``monotonic`` feed the shared KIS token lifecycle (custody: the SAME
    ``kis_mock.*`` scopes the order transport uses; monotonic: its pacing clock, independent of
    ``time_service`` — module docstring's "two clocks, two jobs" note, in
    ``tos_runtime.transport.kis_quote.adapter``); ``broker_scopes`` resolves the host seal
    (:func:`_resolve_kis_instance_rest_bases`); ``runtime_identity`` attributes evidence.
    ``credential_sessions`` is the boot's KIS credential registry (C-2 decision (C)) — the
    intake takes the SAME ``kis_mock.*`` session the order transport holds (required — a
    private registry would silently give it a second token lifecycle for the same app key).
    """
    if config.intake_kind == "journal":
        assert config.journal_path is not None  # load_marketfeed_config's own invariant
        return JsonLinesObservationJournal(config.journal_path)
    assert (
        config.intake_kind == "kis_quote"
    )  # _VALID_INTAKE_KINDS has exactly two members
    instance_mock_rest_base, instance_real_rest_base = _resolve_kis_instance_rest_bases(
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
        ),
        monotonic=monotonic,
        time_service=time_service,
        evidence_sink=_evidence_recorder(evidence_store, runtime_identity),
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
) -> TickScheduler | None:
    """Build the tick scheduler, or ``None`` when this wave is not configured (module docstring).

    Args:
        config_dir: Where ``marketfeed.yaml``/``critical_input_policy.yaml``/(``intake_kind:
            kis_quote`` only) ``kis_quote.yaml`` are read from.
        data_dir: Where the durable snapshot store's own sqlite file lives
            (``data_dir / MARKETFEED_FILE_NAME`` — the SAME path
            :mod:`tos_runtime.compose._migrate_paths` already resolves for ``migrate``).
        scheme: The injected canonicalization scheme.
        time_config: The fully-valued Trustworthy Time config — forwarded to
            :class:`~tos_runtime.marketfeed.time_projection.RuntimeTimeProjection`.
        time_service: This process's shared trustworthy-time service.
        session_owner: This process's shared session-facts owner.
        driver: This process's shared engine driver — the FINAL post-recovery-barrier value
            (module docstring on why this must be called after the barrier runs).
        inbox: This process's shared durable event inbox.
        evidence_store: This process's shared evidence store.
        custody, monotonic, broker_scopes, runtime_identity, credential_sessions: Used ONLY
            when ``intake_kind: kis_quote`` — see :func:`_build_intake` for what each one feeds.

    Returns:
        The built scheduler, or ``None`` when ``marketfeed.yaml`` is absent (an operator who has
        not adopted this wave).

    Raises:
        MarketFeedConfigError: ``marketfeed.yaml`` malformed/incomplete, or ``intake_kind:
            kis_quote``'s host-seal facts could not be resolved.
        tos_runtime.marketfeed.policy.CriticalInputPolicyConfigError: ``critical_input_policy
            .yaml`` missing/malformed/incomplete.
        tos_runtime.transport.kis_quote.config.KisQuoteTransportConfigError: ``intake_kind:
            kis_quote`` but ``kis_quote.yaml`` missing/malformed/incomplete.
        tos_runtime.marketfeed.scheduler.MultiInstrumentRefused: more than one instrument
            (FORWARD-OBLIGATION-MS1 unratified).
        tos_runtime.marketfeed.time_projection.TimeProjectionConfigError: ``time_config`` missing
            ``delay_bounds`` (unreachable in production — defense in depth).
    """
    config_path = config_dir / MARKETFEED_CONFIG_NAME
    if not config_path.is_file():
        return None
    config = load_marketfeed_config(config_path)
    policy = load_critical_input_policy(
        config_dir / CRITICAL_INPUT_POLICY_CONFIG_NAME, scheme=scheme
    )
    store = SqliteSnapshotStore(data_dir / MARKETFEED_FILE_NAME)
    intake = _build_intake(
        config,
        config_dir=config_dir,
        custody=custody,
        monotonic=monotonic,
        time_service=time_service,
        broker_scopes=broker_scopes,
        evidence_store=evidence_store,
        runtime_identity=runtime_identity,
        credential_sessions=credential_sessions,
    )
    time_projection = RuntimeTimeProjection(
        config=time_config,
        time_service=time_service,
        session_owner=session_owner,
        instrument_class=config.instrument_class,
        snapshot_age_bound=config.snapshot_age_bound,
        interval_width=config.interval_width,
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
        store=store,
        time_projection=time_projection,
        time_service=time_service,
        session_owner=session_owner,
        driver=driver,
        inbox=inbox,
        evidence_store=evidence_store,
        poll_interval_ms=config.poll_interval_ms,
        before_pass=_time_pacer_pass(config, time_service, session_owner, monotonic),
    )
