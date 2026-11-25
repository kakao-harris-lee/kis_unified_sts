"""The slim runtime monitor: evidence-chain continuity, tip stall, inbox backlog."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from tos.cur import DimensionKey

from tos_runtime.currentness.vector import DimensionReport
from tos_runtime.safety._policy_loader import (
    load_yaml_document,
    require_int_field,
    require_mapping_field,
)

__all__ = [
    "MonitoringConfigError",
    "EvidenceTipObserver",
    "InboxUnconsumedObserver",
    "MonotonicClock",
    "AlertRecorder",
    "MonitoringService",
]

_IDENTITY = "monitoring-service-v2"

_REASON_EVIDENCE_TIP_UNKNOWN = "evidence_tip_never_observed"
_REASON_EVIDENCE_TIP_STALL = "evidence_tip_stalled"
_REASON_CONTINUITY_UNESTABLISHED = "source_continuity_unestablished"
_REASON_CONTINUITY_BROKEN = "source_continuity_broken"
_REASON_INBOX_BACKLOG = "inbox_unconsumed_over_bound"
_REASON_ALERT_DELIVERY_FAILED = "stm_alert_delivery_failed"

_EVIDENCE_KIND_STM_ALERT = "STM_ALERT"

_NS_PER_MS = 1_000_000


class MonitoringConfigError(Exception):
    """The monitor-coverage policy document is missing, malformed, or still carries an"""


class EvidenceTipObserver(Protocol):
    """Port returning ``(last_seq, last_chain_digest, last_key_generation)``."""

    def __call__(self) -> tuple[int | None, str, int | None]:
        """Return the evidence store's own tip observation."""
        ...


class InboxUnconsumedObserver(Protocol):
    """Port returning the count of currently-unconsumed inbox rows."""

    def __call__(self) -> int:
        """Return the count of currently-unconsumed inbox rows."""
        ...


class MonotonicClock(Protocol):
    """Port returning the stall detector's monotonic nanosecond clock."""

    def __call__(self) -> int:
        """Return the current monotonic nanosecond count."""
        ...


class AlertRecorder(Protocol):
    """Sink for one ``STM_ALERT`` evidence record."""

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        """Durably (from the caller's perspective) record one ``STM_ALERT`` evidence"""
        ...


@dataclass(frozen=True)
class _LoadedCoverage:
    coverage_generation: int
    max_evidence_tip_stall_ms: int
    max_inbox_unconsumed: int
    config_path: Path


@dataclass(frozen=True)
class _Observation:
    """One :meth:`MonitoringService.healthy` call's raw self-observation results."""

    tip_ok: bool | None
    continuity_ok: bool | None
    last_seq: int | None
    unconsumed: int
    inbox_ok: bool


def _load_coverage(config_path: Path) -> _LoadedCoverage:
    """Load the two bounds this monitor needs, fail-closed (module docstring)."""
    raw = load_yaml_document(config_path, MonitoringConfigError)
    coverage = require_mapping_field(
        raw, "coverage", config_path, MonitoringConfigError
    )
    bounds = require_mapping_field(
        coverage, "bounds", config_path, MonitoringConfigError
    )
    return _LoadedCoverage(
        coverage_generation=require_int_field(
            coverage, "coverage_generation", config_path, MonitoringConfigError
        ),
        max_evidence_tip_stall_ms=require_int_field(
            bounds, "max_evidence_tip_stall_ms", config_path, MonitoringConfigError
        ),
        max_inbox_unconsumed=require_int_field(
            bounds, "max_inbox_unconsumed", config_path, MonitoringConfigError
        ),
        config_path=config_path,
    )


class MonitoringService:
    """The slim monitor (module docstring)."""

    def __init__(
        self,
        *,
        config_path: Path,
        evidence_tip_observer: EvidenceTipObserver,
        inbox_unconsumed_observer: InboxUnconsumedObserver,
        monotonic_ns: MonotonicClock,
        evidence_recorder: AlertRecorder,
    ) -> None:
        """Load the bounds and bind the injected self-observation ports."""
        self._docs = _load_coverage(config_path)
        self._evidence_tip_observer = evidence_tip_observer
        self._inbox_unconsumed_observer = inbox_unconsumed_observer
        self._monotonic_ns = monotonic_ns
        self._evidence_recorder = evidence_recorder
        self._tip_last_seq: int | None = None
        self._tip_last_advance_ns: int | None = None
        self._continuity_last_seq: int | None = None
        self._continuity_last_chain_digest: str | None = None
        self._last_delivery_failure: str | None = None

    @property
    def identity(self) -> str:
        """This owner's ``owner_identity`` (module docstring)."""
        return _IDENTITY

    @property
    def dimension_key(self) -> DimensionKey:
        """The one §9 currentness dimension this service owns."""
        return DimensionKey.MONITORING

    def _observe(self, now_ns: int) -> _Observation:
        """Read each self-observation port exactly once for this call."""
        seq, chain_digest, _key_generation = self._evidence_tip_observer()
        if seq is None:
            tip_ok: bool | None = None
            continuity_ok: bool | None = None
        else:
            if seq != self._tip_last_seq:
                self._tip_last_seq = seq
                self._tip_last_advance_ns = now_ns
            assert self._tip_last_advance_ns is not None
            stall_ms = (now_ns - self._tip_last_advance_ns) // _NS_PER_MS
            tip_ok = stall_ms <= self._docs.max_evidence_tip_stall_ms

            if self._continuity_last_seq is None:
                continuity_ok = None
            else:
                seq_advanced = seq > self._continuity_last_seq
                seq_regressed = seq < self._continuity_last_seq
                digest_changed = chain_digest != self._continuity_last_chain_digest
                continuity_ok = (
                    False if seq_regressed else (seq_advanced == digest_changed)
                )
            self._continuity_last_seq = seq
            self._continuity_last_chain_digest = chain_digest

        unconsumed = self._inbox_unconsumed_observer()
        return _Observation(
            tip_ok=tip_ok,
            continuity_ok=continuity_ok,
            last_seq=seq,
            unconsumed=unconsumed,
            inbox_ok=unconsumed <= self._docs.max_inbox_unconsumed,
        )

    def healthy(self) -> bool | None:
        """``True`` when every self-observation is positively within bounds, ``False``"""
        unestablished: list[str] = []
        violated: list[str] = []
        if self._last_delivery_failure is not None:
            violated.append(_REASON_ALERT_DELIVERY_FAILED)
        obs = self._observe(self._monotonic_ns())
        if obs.tip_ok is None:
            unestablished.append(_REASON_EVIDENCE_TIP_UNKNOWN)
        elif obs.tip_ok is False:
            violated.append(_REASON_EVIDENCE_TIP_STALL)
        if obs.continuity_ok is None and obs.tip_ok is not None:
            unestablished.append(_REASON_CONTINUITY_UNESTABLISHED)
        elif obs.continuity_ok is False:
            violated.append(_REASON_CONTINUITY_BROKEN)
        if obs.inbox_ok is False:
            violated.append(_REASON_INBOX_BACKLOG)

        reasons = violated + unestablished
        if violated:
            verdict: bool | None = False
        elif unestablished:
            verdict = None
        else:
            verdict = True

        if verdict is True:
            self._last_delivery_failure = None
            return True
        try:
            self._evidence_recorder(
                _EVIDENCE_KIND_STM_ALERT,
                {
                    "identity": self.identity,
                    "clear": verdict,
                    "reasons": tuple(reasons),
                    "last_evidence_seq": obs.last_seq,
                    "source_continuity_present": obs.continuity_ok,
                    "inbox_unconsumed": obs.unconsumed,
                },
            )
        except Exception as exc:
            self._last_delivery_failure = (
                f"{_EVIDENCE_KIND_STM_ALERT}_delivery_failed: {exc!r}"
            )
            raise
        self._last_delivery_failure = None
        return verdict

    def dimension_report(self) -> DimensionReport | None:
        """This owner's currentness verdict for MONITORING."""
        return DimensionReport(
            bound_generation=self._docs.coverage_generation,
            positively_established=self.healthy() is True,
            restrictive_floor=0,
        )

    def describe(self) -> dict[str, Any]:
        """Evidence-facing description of the loaded policy document — names, generations"""
        return {
            "identity": self.identity,
            "config_path": str(self._docs.config_path),
            "coverage_generation": self._docs.coverage_generation,
            "max_evidence_tip_stall_ms": self._docs.max_evidence_tip_stall_ms,
            "max_inbox_unconsumed": self._docs.max_inbox_unconsumed,
        }
