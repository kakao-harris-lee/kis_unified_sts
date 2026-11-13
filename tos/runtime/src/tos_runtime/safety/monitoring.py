"""The slim runtime monitor: evidence-tip stall and inbox backlog.

What this owns, and what it no longer does (plan S2-a). It used to be the
``tos.stm`` safety-mesh service: a coverage manifest, a conformance snapshot,
three self-observations and the egress verify item 10 ``monitoring_clear``
flag. Every one of its 60 alerts in the real evidence was a boot-first-
observation artefact, its coverage manifest was a static YAML constant in all
four shipped tenant trees, and verify item 10 never once denied. The kernel
``tos.stm`` package and verify item 10 are gone; monitoring is carried by the
MONITORING currentness dimension alone.

What it still does: read two injected self-observations once per call — the
evidence tip's own advance (a stall past ``max_evidence_tip_stall_ms`` is not
healthy) and the durable inbox's unconsumed count (a backlog past
``max_inbox_unconsumed`` is not healthy) — report MONITORING's currentness
verdict from them, and append one ``STM_ALERT`` evidence row whenever the
verdict is not positively healthy.

Time health is deliberately NOT observed here: the Trustworthy Time service
owns the TRUSTWORTHY_TIME currentness dimension, and judging the same fact a
second time is what plan S2-a removed.

Recorder failures propagate and are remembered for the next call, so a
delivery failure cannot be silently treated as healthy. The evidence observer
must exclude this service's own alert rows; otherwise its alerts would reset
the stall detector. Ports stay injected so this module does not depend on the
concrete evidence or engine services.

Firewall (R1, runtime scope): stdlib + ``pyyaml`` (via the shared policy
loader) + ``tos.cur`` (``DimensionKey``) + ``tos_runtime.*`` only. No
``shared.*``.
"""

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

#: The code-constant ``owner_identity`` this service stamps — a code constant, never
#: configuration.
_IDENTITY = "monitoring-service-v2"

#: Deterministic, fixed-order reason tokens.
_REASON_EVIDENCE_TIP_UNKNOWN = "evidence_tip_never_observed"
_REASON_EVIDENCE_TIP_STALL = "evidence_tip_stalled"
_REASON_INBOX_BACKLOG = "inbox_unconsumed_over_bound"
_REASON_ALERT_DELIVERY_FAILED = "stm_alert_delivery_failed"

#: ``STM_ALERT`` evidence kind — the one kind this service emits. ``tos_runtime.safety.ack``
#: acknowledges rows of this kind by ``seq``; the payload shape is this module's own.
_EVIDENCE_KIND_STM_ALERT = "STM_ALERT"

_NS_PER_MS = 1_000_000


class MonitoringConfigError(Exception):
    """The monitor-coverage policy document is missing, malformed, or still carries an
    unfilled (named-TBD) required field — fail-closed at construction, never a lazily
    discovered ``None`` inside :meth:`MonitoringService.healthy`."""


class EvidenceTipObserver(Protocol):
    """Port returning ``(last_seq, last_chain_digest, last_key_generation)``.

    The compose layer must exclude this service's own ``STM_ALERT`` rows.
    """

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
        """Durably (from the caller's perspective) record one ``STM_ALERT`` evidence
        entry — never a secret / bearer token in ``fields``."""
        ...


@dataclass(frozen=True)
class _LoadedCoverage:
    coverage_generation: int
    max_evidence_tip_stall_ms: int
    max_inbox_unconsumed: int
    config_path: Path


@dataclass(frozen=True)
class _Observation:
    """One :meth:`MonitoringService.healthy` call's raw self-observation results.

    ``tip_ok`` is ``None`` only when the evidence tip has never been observed
    (``seq is None``) — a genuine gap, never a fabricated pass.
    """

    tip_ok: bool | None
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
        """Load the bounds and bind the injected self-observation ports.

        Raises:
            MonitoringConfigError: the policy document is missing, malformed, or carries
                an unfilled required field.
        """
        self._docs = _load_coverage(config_path)
        self._evidence_tip_observer = evidence_tip_observer
        self._inbox_unconsumed_observer = inbox_unconsumed_observer
        self._monotonic_ns = monotonic_ns
        self._evidence_recorder = evidence_recorder
        self._tip_last_seq: int | None = None
        self._tip_last_advance_ns: int | None = None
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
        seq, _chain_digest, _key_generation = self._evidence_tip_observer()
        if seq is None:
            tip_ok: bool | None = None
        else:
            if seq != self._tip_last_seq:
                self._tip_last_seq = seq
                self._tip_last_advance_ns = now_ns
            assert self._tip_last_advance_ns is not None
            stall_ms = (now_ns - self._tip_last_advance_ns) // _NS_PER_MS
            tip_ok = stall_ms <= self._docs.max_evidence_tip_stall_ms
        unconsumed = self._inbox_unconsumed_observer()
        return _Observation(
            tip_ok=tip_ok,
            last_seq=seq,
            unconsumed=unconsumed,
            inbox_ok=unconsumed <= self._docs.max_inbox_unconsumed,
        )

    def healthy(self) -> bool | None:
        """``True`` when both self-observations are positively within bounds, ``False``
        when one is positively out of bounds, ``None`` when the evidence tip has never
        been observed (unestablished, never a fabricated pass).

        Appends one ``STM_ALERT`` row on every non-``True`` result. A recorder failure
        propagates and is remembered, so the NEXT call can never report ``True`` while a
        prior alert went undelivered.
        """
        reasons: list[str] = []
        if self._last_delivery_failure is not None:
            reasons.append(_REASON_ALERT_DELIVERY_FAILED)
        obs = self._observe(self._monotonic_ns())
        if obs.tip_ok is None:
            reasons.append(_REASON_EVIDENCE_TIP_UNKNOWN)
        elif obs.tip_ok is False:
            reasons.append(_REASON_EVIDENCE_TIP_STALL)
        if obs.inbox_ok is False:
            reasons.append(_REASON_INBOX_BACKLOG)

        if not reasons:
            verdict: bool | None = True
        elif reasons == [_REASON_EVIDENCE_TIP_UNKNOWN]:
            verdict = None
        else:
            verdict = False

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
                    "inbox_unconsumed": obs.unconsumed,
                },
            )
        except Exception as exc:
            # Propagate the failure now and expose it on the next call.
            self._last_delivery_failure = (
                f"{_EVIDENCE_KIND_STM_ALERT}_delivery_failed: {exc!r}"
            )
            raise
        self._last_delivery_failure = None
        return verdict

    def dimension_report(self) -> DimensionReport | None:
        """This owner's currentness verdict for MONITORING.

        ``restrictive_floor`` is ``0`` — a deliberate statement, not an invented default:
        there is no floor-governance runtime (the same "an owner reporting 0 is that
        owner's own choice" discipline :class:`~tos_runtime.currentness.vector
        .DimensionReport`'s own docstring states).
        """
        return DimensionReport(
            bound_generation=self._docs.coverage_generation,
            positively_established=self.healthy() is True,
            restrictive_floor=0,
        )

    def describe(self) -> dict[str, Any]:
        """Evidence-facing description of the loaded policy document — names, generations
        and bounds only; never a secret / bearer token."""
        return {
            "identity": self.identity,
            "config_path": str(self._docs.config_path),
            "coverage_generation": self._docs.coverage_generation,
            "max_evidence_tip_stall_ms": self._docs.max_evidence_tip_stall_ms,
            "max_inbox_unconsumed": self._docs.max_inbox_unconsumed,
        }
