"""``tos_runtime.compose._marketfeed_wiring`` — the tick-scheduler compose wiring (TOS tick-source
wave, plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §4 lane D).

Loads ``marketfeed.yaml`` (fail-closed, the SAME named-TBD idiom
:mod:`tos_runtime.compose._engine_config` already ships) and, only when it exists under
``config_dir`` ALONGSIDE a ``critical_input_policy.yaml``
(:data:`~tos_runtime.marketfeed.policy.CRITICAL_INPUT_POLICY_CONFIG_NAME`), builds a real
:class:`~tos_runtime.marketfeed.scheduler.TickScheduler` — the SAME "files exist" idiom
:func:`~tos_runtime.compose._session_wiring.build_nontrade_processor` already uses for its own
optional ``nontrade.yaml``. Absent either file, :func:`build_tick_scheduler` returns ``None``: an
operator who has not yet adopted this wave keeps composing exactly as before (module docstring of
``ComposedRuntime.marketfeed`` — a legitimate state, never a boot refusal).

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

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import CanonicalizationScheme

from tos_runtime.calendar.owner import SessionFactsOwner
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.marketfeed.journal import JsonLinesObservationJournal
from tos_runtime.marketfeed.policy import (
    CRITICAL_INPUT_POLICY_CONFIG_NAME,
    load_critical_input_policy,
)
from tos_runtime.marketfeed.scheduler import TickScheduler
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME, SqliteSnapshotStore
from tos_runtime.marketfeed.time_projection import RuntimeTimeProjection
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TrustworthyTimeService

__all__ = [
    "MARKETFEED_CONFIG_NAME",
    "MarketFeedConfig",
    "MarketFeedConfigError",
    "build_tick_scheduler",
    "load_marketfeed_config",
]

#: The runtime INSTANCE file name (distinct from ``marketfeed.example.yaml``).
MARKETFEED_CONFIG_NAME = "marketfeed.yaml"

#: The scalar-string fields, in the shipped example's own declaration order.
_STR_FIELDS: tuple[str, ...] = (
    "instrument_class",
    "account",
    "direction",
    "quantity_basis",
    "unit",
    "journal_path",
)
#: The scalar-int fields.
_INT_FIELDS: tuple[str, ...] = (
    "poll_interval_ms",
    "snapshot_age_bound",
    "interval_width",
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
    journal_path: Path
    poll_interval_ms: int
    snapshot_age_bound: int
    interval_width: int


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
    return tuple(value)


def load_marketfeed_config(path: Path) -> MarketFeedConfig:
    """Load and fail-closed-validate ``marketfeed.yaml`` from ``path`` (module docstring).

    Raises:
        MarketFeedConfigError: The file is missing/unreadable/not valid YAML/not a mapping, or
            any required leaf is absent, ``null``, or the wrong type.
    """
    raw = _load_mapping(path)
    instruments = _require_instruments(raw, path)
    str_values = {field: _require_str(raw, field, path) for field in _STR_FIELDS}
    int_values = {field: _require_int(raw, field, path) for field in _INT_FIELDS}
    return MarketFeedConfig(
        instruments=instruments,
        instrument_class=str_values["instrument_class"],
        account=str_values["account"],
        direction=str_values["direction"],
        quantity_basis=str_values["quantity_basis"],
        unit=str_values["unit"],
        journal_path=Path(str_values["journal_path"]),
        poll_interval_ms=int_values["poll_interval_ms"],
        snapshot_age_bound=int_values["snapshot_age_bound"],
        interval_width=int_values["interval_width"],
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
) -> TickScheduler | None:
    """Build the tick scheduler, or ``None`` when this wave is not configured (module docstring).

    Args:
        config_dir: Where ``marketfeed.yaml``/``critical_input_policy.yaml`` are read from.
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

    Returns:
        The built :class:`~tos_runtime.marketfeed.scheduler.TickScheduler`, or ``None`` when
        ``marketfeed.yaml`` is absent (an operator who has not adopted this wave).

    Raises:
        MarketFeedConfigError: ``marketfeed.yaml`` exists but is malformed/incomplete.
        tos_runtime.marketfeed.policy.CriticalInputPolicyConfigError: ``marketfeed.yaml`` exists
            but ``critical_input_policy.yaml`` is missing/malformed/incomplete.
        tos_runtime.marketfeed.scheduler.MultiInstrumentRefused: ``instruments`` names more than
            one instrument (FORWARD-OBLIGATION-MS1 is unratified).
        tos_runtime.marketfeed.time_projection.TimeProjectionConfigError: ``time_config`` is
            missing a required ``delay_bounds`` term (unreachable in production — that config
            loader already refuses first — kept as this module's own defense in depth).
    """
    config_path = config_dir / MARKETFEED_CONFIG_NAME
    if not config_path.is_file():
        return None
    config = load_marketfeed_config(config_path)
    policy = load_critical_input_policy(
        config_dir / CRITICAL_INPUT_POLICY_CONFIG_NAME, scheme=scheme
    )
    store = SqliteSnapshotStore(data_dir / MARKETFEED_FILE_NAME)
    intake = JsonLinesObservationJournal(config.journal_path)
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
    )
