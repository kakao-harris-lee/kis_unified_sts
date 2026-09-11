"""``MonitoringService`` — the MONITORING runtime owner (stm · item 10 · plan
``docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md`` §2 decision 2, fourth bullet;
lane W3-a2).

Loads one static operator policy document — a Monitor Coverage Manifest (ADR-002-028 §5.4;
``tos.stm``) — into the kernel's own frozen record via the ordinary pydantic constructor,
and builds a fresh ``ContinuousConformanceSnapshot`` on every :meth:`clear` call from three
**self-observations** this runtime can honestly make about itself: how long ago the evidence
store's own tip last advanced, the Trustworthy Time service's own reported health state, and
the engine inbox's own currently-unconsumed row count (plan §2 decision 2: "평가 입력은 런타임
자기 관측"). **This module authors no verdict of its own** — every boolean is either a
concrete config field, an observation compared against a config-declared bound, or a
``tos.stm`` kernel predicate's return value (kernel round #1 §0 "판정은 커널 술어만 한다"; the
M6 lesson from ``tos-phase4-scopes-round-2026-09-09``).

**Honest-source table (docstring per predicate, plan "Report back" requirement).**

* :func:`~tos.stm.critical_coverage_complete_or_gap` — the ``MonitorCoverageManifest`` is
  the loaded static document (three fixed obligations: evidence-tip currency, time-service
  health, inbox backlog — see :data:`_OBLIGATION_REFS`); ``applicable_obligations`` /
  ``applicable_dimensions`` / ``submitted_assumption_ids`` are this service's own derived
  sets (the manifest's own ``coverage_items`` obligation refs; an intentionally EMPTY
  dependency-closure-dimension set — these three infra-only obligations carry no
  cross-Safety-Cell dependency closure, a documented operator claim, not a fabricated one;
  and an empty submitted-assumption set — this service submits no Monitored Assumptions).
  This is a static, config-only gate: given a valid (boot-accepted) document it is always
  ``True`` by construction, the same "config declares its own applicable set" discipline
  :mod:`tos_runtime.safety.incident`'s ``active_set_is_canonical_union`` call uses; kept as
  a real predicate call (never assumed) as defense-in-depth against a ``model_construct``
  bypass.
* :func:`~tos.stm.conformance_requires_complete_current_valid` — the
  ``ContinuousConformanceSnapshot`` built fresh every call from the three self-observations
  below. This predicate does NOT judge whether the system is healthy; it judges whether a
  ``CONFORMING`` claim is honestly backed (module docstring at
  ``tos/src/tos/stm/predicates.py:832``). The health judgement itself is
  ``snapshot.aggregate_result`` compared with ``is``, never truthiness (module docstring
  "Truthy-sentinel discipline").
* ``snapshot.source_continuity_present`` (review disposition, HIGH-2) — **not** a constant.
  Derived from successive ``(seq, chain_digest)`` observations of the evidence tip (the
  ``last_chain_digest`` the evidence-tip observer already returns and this module
  previously discarded): a strictly-advancing ``seq`` paired with a changed ``chain_digest``
  (an ordinary append), or an unchanged ``seq`` paired with an unchanged digest (an idle
  tick — nothing new, nothing torn), both report continuity ``True``; a ``seq`` regression,
  or a digest change with no ``seq`` advance (or vice versa — an append without a matching
  digest movement, or a digest movement with no append), reports ``False``. On the very
  FIRST observation this service ever makes (no prior ``(seq, digest)`` to compare against)
  continuity is honestly ``None`` — **consequence**: a brand-new
  :class:`MonitoringService` instance's first :meth:`clear` call reports ``None`` (UNKNOWN)
  even when every live check looks healthy, because a ``CONFORMING`` claim requires a
  concrete (non-``None``) ``source_continuity_present``
  (``tos/src/tos/stm/records.py:373`` default is ``None``; the coexistence-seal validator at
  ``:413`` refuses to let a ``CONFORMING`` claim coexist with an unestablished continuity
  fact) and this service refuses to assert continuity it has not observed. The second and
  every later call establishes a prior observation and reports a concrete ``True``/``False``.

**The three self-observations (plan §2 decision 2 "MonitoringService" bullet) — each an
injected zero/one-argument callable port, never an imported concrete module (this package
stays decoupled from ``tos_runtime.evidence`` / ``.time`` / ``.engine``; the compose layer
wires the real callables):**

1. ``evidence_tip_observer`` — mirrors
   :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.last_committed`'s own
   ``(last_seq, last_chain_digest, last_key_generation)`` shape. ``last_seq is None`` (an
   empty store) is honestly **UNKNOWN**, not "fresh" — this service tracks internally when
   ``last_seq`` last CHANGED (a stall detector, not a per-entry wall-clock age: no accessor
   in ``SqliteEvidenceStore`` exposes a committed entry's own timestamp without a full-table
   scan, and the ADR concept "how long has this evidence tip gone stale" is naturally a
   stall measurement over successive observations, not a single entry's age) and compares
   the stall duration against ``bounds.max_evidence_tip_stall_ms``. ``last_chain_digest`` is
   ALSO consulted (paired with ``last_seq``) to derive ``source_continuity_present`` (module
   docstring "Honest-source table").
   **Wiring contract (review disposition, HIGH-1) — the observer's counted tip MUST
   EXCLUDE this very service's own ``STM_ALERT`` evidence writes.** If the composed
   observer counts every entry kind, the ``STM_ALERT`` this service itself emits on a
   non-``True`` :meth:`clear` advances the observed ``seq`` on the very next tick, which
   this service would then read as "the tip advanced" and reset the stall clock — a
   continuing stall would flap deny/clear/clear instead of staying denied. The composing
   layer MUST wire a ``kinds_excluded={"STM_ALERT"}``-shaped reader (e.g. ``MAX(seq) FROM
   entries WHERE kind != 'STM_ALERT'``), never the raw unfiltered ``last_committed``, when
   this same evidence store also receives this service's own alert writes.
2. ``time_health_observer`` — returns the Trustworthy Time service's health-state token
   name as a plain ``str`` (never importing ``tos_runtime.time.service.HealthState`` here,
   to keep this module import-decoupled); compared against the config-declared
   ``bounds.healthy_time_states`` list.
3. ``inbox_unconsumed_observer`` — the count of currently-unconsumed
   :class:`~tos_runtime.engine.inbox.SqliteEventInbox` rows. This service only defines
   the port's SHAPE (``Callable[[], int]``); the compose layer supplies the actual
   closure, out of this lane's file ownership (plan §4) — now
   :attr:`~tos_runtime.engine.inbox.SqliteEventInbox.unconsumed_count`, a public reader
   added alongside this composition (W3.1 independent review LOW-1: this module's own
   ``count`` property is "how many events this inbox has ever admitted", not the
   unconsumed subset, so a SEPARATE reader was needed — it now exists and is wired).

``monotonic_ns`` is a fourth injected port (the stall clock — mirrors
``tos_runtime.time.service.TrustworthyTimeService.monotonic``'s shape) and
``evidence_recorder`` a fifth (the ``STM_ALERT`` evidence sink — the ``(kind, fields) ->
None`` shape :class:`~tos_runtime.transport.kis_mock.adapter.EvidenceRecorder` already
uses; this runtime "knows no delivery channel" for the alert itself, plan §2 decision 8).

**Deviation flagged for the operator (plan "report back" requirement) — no
``ApprovedBoundBinding`` / :func:`~tos.stm.bound_integrity_preserved` wiring.** The plan's
MonitoringService bullet parenthetically mentions "``+ ApprovedBoundBinding`` from YAML
bounds"; this module deliberately does not construct one. ``bound_integrity_preserved``
is not part of decision 2's stated ``clear()`` formula
(``critical_coverage_complete_or_gap`` ∧ ``conformance_requires_complete_current_valid``),
and adding a full :class:`~tos.stm.ApprovedBoundBinding` config surface (approved/
implemented ``BoundSemanticKind``, exceedance-window, uncertainty-treatment flags) would
not change this service's tri-state — only add unused structure. Flagged for a follow-up
wave if a future consumer needs ``bound_integrity_preserved`` to gate this service.

**No ``SafetyMonitoringGap`` / :func:`~tos.stm.gap_is_restrictive_not_exemption`
modeling.** This service reports its own live gap state (an ``UNKNOWN`` aggregate result)
directly through ``clear() -> None``; it does not additionally construct a
``SafetyMonitoringGap`` closure record — that lifecycle (a gap opened, later closed under
continuity-reestablishment proof) is a distinct, stateful artifact this minimal 3-check
scope does not need. Flagged for a follow-up wave if gap lifecycle tracking is required.

**Tri-state combination.** ``critical_coverage_complete_or_gap`` is a static, always-``True``
(given a boot-accepted document) gate; the dynamic result comes from
``snapshot.aggregate_result``, itself derived from three buckets — never a fixed
CONFORMING/NON_CONFORMING/UNKNOWN literal:

* ``active_gaps`` — the evidence tip has NEVER been observed (an empty store, ``seq is
  None``): a genuine absence of coverage (STM-INV-002 line 163 "missing ... coverage is a
  gap"), reported once and not also double-counted as an "unknown".
* ``active_unknowns`` — a real observation exists but ``source_continuity_present`` cannot
  yet be judged (this service's own FIRST tick — module docstring "Honest-source table").
* ``active_violations`` / ``delivery_failures`` — a definite, positively-observed problem
  (a stall over bound, a broken continuity chain, an unhealthy time state, an inbox
  backlog over bound, or a remembered prior alert-delivery failure).

Any ``active_gaps`` or ``active_unknowns`` entry ⇒ ``UNKNOWN`` ⇒ :meth:`clear` reports
``None`` — matching the kernel's own ``unknown_is_restrictive`` philosophy
(``tos/src/tos/stm/predicates.py:1029``: "Missing, stale, conflicting ... monitoring state
blocks dependent new risk") without this service fabricating the seven-axis
``MonitoringUnknownState`` record that predicate itself needs (this service has an honest
source for only two of those seven axes — freshness and continuity — so it is not called
directly; flagged for a follow-up wave). Otherwise any ``active_violations`` /
``delivery_failures`` entry ⇒ ``NON_CONFORMING`` ⇒ ``False``. Only when every bucket is
empty ⇒ ``CONFORMING`` ⇒ ``True``. A coverage gap on the STATIC manifest check (should it
somehow fail) dominates to ``False`` regardless of the dynamic result.

**``STM_ALERT`` emission (plan §2 decision 8).** Emitted exactly once per non-``True``
:meth:`clear` call, never on a ``True`` one — this runtime has no delivery channel of its
own for the alert; :meth:`clear`'s caller (or the evidence store's own downstream readers)
owns delivery. **Delivery failure is never swallowed** (review disposition, HIGH-2's sibling
requirement on ``delivery_failures``): the ``evidence_recorder`` call is wrapped, and a
raised exception both (a) propagates out of :meth:`clear` immediately (the caller sees the
failure at the moment it happened) and (b) is remembered on this instance, so the VERY NEXT
:meth:`clear` call's snapshot honestly carries it in ``delivery_failures`` (a real recorded
fact, never a literal ``()``) — denying that next tick too, until a delivery attempt
succeeds again. A delivery failure can only be observed retrospectively (the recorder is
called after this tick's own verdict is already computed), so it cannot deny the SAME tick
it happened on; this is a documented one-tick lag, not a gap in coverage.

Pure module beyond stdlib + third-party: ``pydantic`` (via ``tos.stm`` records) + ``yaml`` +
``tos.stm`` + ``tos_runtime.safety.ports`` + ``tos_runtime.safety._policy_loader`` +
``tos_runtime.currentness.vector`` (``DimensionReport``). No ``shared.*``, no
``os.environ``, no network I/O, no import of ``tos_runtime.evidence`` / ``.time`` /
``.engine`` (module docstring, self-observation ports section).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError
from tos.cur import DimensionKey
from tos.stm import (
    AggregateConformanceResult,
    ContinuousConformanceSnapshot,
    CoverageItem,
    MonitorCoverageManifest,
    MonitorEvaluation,
    NumericInputState,
    TelemetryCriticality,
    conformance_requires_complete_current_valid,
    critical_coverage_complete_or_gap,
)

from tos_runtime.currentness.vector import DimensionReport
from tos_runtime.safety._policy_loader import (
    load_yaml_document,
    require_bool_field,
    require_int_field,
    require_list_field,
    require_mapping_field,
    require_str_field,
)
from tos_runtime.safety.ports import MeshClearance

__all__ = [
    "MonitoringConfigError",
    "EvidenceTipObserver",
    "TimeHealthObserver",
    "InboxUnconsumedObserver",
    "MonotonicClock",
    "AlertRecorder",
    "MonitoringService",
]

#: The code-constant ``owner_identity`` this service stamps (plan §2 decision 1 — an
#: identity is a code constant, never configuration).
_IDENTITY = "monitoring-service-stm-v1"

#: The three fixed obligations this service's self-observations cover (module docstring).
#: A closed catalogue: the config loader refuses a document that does not carry EXACTLY
#: these three ``coverage_items`` keys, so the manifest and the observation code can never
#: silently drift apart.
_OBLIGATION_EVIDENCE_TIP = "evidence-tip-currency"
_OBLIGATION_TIME_HEALTH = "time-service-health"
_OBLIGATION_INBOX_BACKLOG = "inbox-backlog"
_OBLIGATION_REFS: tuple[str, ...] = (
    _OBLIGATION_EVIDENCE_TIP,
    _OBLIGATION_TIME_HEALTH,
    _OBLIGATION_INBOX_BACKLOG,
)

#: Deterministic, fixed-order reason tokens (ports.py "reasons" contract).
_REASON_COVERAGE_GAP = "critical_coverage_complete_or_gap"
_REASON_SNAPSHOT_DISHONEST = "conformance_requires_complete_current_valid"
_REASON_EVIDENCE_TIP_UNKNOWN = "evidence_tip_never_observed"
_REASON_EVIDENCE_TIP_STALL = "evidence_tip_stalled"
_REASON_CONTINUITY_UNESTABLISHED = "source_continuity_unestablished"
_REASON_CONTINUITY_BROKEN = "source_continuity_broken"
_REASON_TIME_UNHEALTHY = "time_health_not_in_healthy_states"
_REASON_INBOX_BACKLOG = "inbox_unconsumed_over_bound"
_REASON_ALERT_DELIVERY_FAILED = "stm_alert_delivery_failed"

#: ``STM_ALERT`` evidence kind (module docstring "STM_ALERT emission").
_EVIDENCE_KIND_STM_ALERT = "STM_ALERT"

_NS_PER_MS = 1_000_000


class MonitoringConfigError(Exception):
    """Raised when the Monitor Coverage Manifest policy document is missing, malformed,
    still carries an unfilled (named-TBD) required field, does not carry exactly the three
    fixed obligations, or fails the kernel record's own schema validation — fail-closed at
    construction, never a lazily-discovered ``None`` inside :meth:`MonitoringService
    .clear`."""


class EvidenceTipObserver(Protocol):
    """The injected evidence-tip port (module docstring, item 1). Any zero-arg callable
    returning ``(last_seq, last_chain_digest, last_key_generation)`` satisfies this —
    ``SqliteEvidenceStore.last_committed`` already does."""

    def __call__(self) -> tuple[int | None, str, int | None]:
        """Return the evidence store's own ``(last_seq, last_chain_digest,
        last_key_generation)`` tip observation."""
        ...


class TimeHealthObserver(Protocol):
    """The injected time-health port (module docstring, item 2). Any zero-arg callable
    returning the health-state token name as a plain ``str`` satisfies this — a caller
    wires ``lambda: time_service.health_state.value`` or an equivalent adapter."""

    def __call__(self) -> str:
        """Return the Trustworthy Time service's current health-state token name."""
        ...


class InboxUnconsumedObserver(Protocol):
    """The injected inbox-backlog port (module docstring, item 3). Any zero-arg callable
    returning the count of currently-unconsumed inbox rows satisfies this. No public
    reader exists on ``SqliteEventInbox`` today (module docstring) — the compose layer
    supplies the closure."""

    def __call__(self) -> int:
        """Return the count of currently-unconsumed inbox rows."""
        ...


class MonotonicClock(Protocol):
    """The injected monotonic-clock port (the stall detector's own clock — module
    docstring). Any zero-arg callable returning a monotonically non-decreasing
    nanosecond count satisfies this."""

    def __call__(self) -> int:
        """Return the current monotonic nanosecond count."""
        ...


class AlertRecorder(Protocol):
    """The injected ``STM_ALERT`` evidence sink (module docstring). Mirrors
    :class:`~tos_runtime.transport.kis_mock.adapter.EvidenceRecorder`'s own
    ``(kind, fields) -> None`` shape exactly, so one adapter can serve both."""

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        """Durably (from the caller's perspective) record one ``STM_ALERT`` evidence
        entry — never a secret / bearer token in ``fields``."""
        ...


@dataclass(frozen=True)
class _Bounds:
    max_evidence_tip_stall_ms: int
    healthy_time_states: tuple[str, ...]
    max_inbox_unconsumed: int


@dataclass(frozen=True)
class _LoadedCoverage:
    manifest: MonitorCoverageManifest
    bounds: _Bounds
    config_path: Path


@dataclass(frozen=True)
class _Observation:
    """One :meth:`MonitoringService.clear` tick's raw self-observation results (review
    disposition, HIGH-2) — the single source both :meth:`MonitoringService._build_snapshot`
    and :meth:`MonitoringService.clear`'s own reason derivation read, so the two can never
    disagree about what was actually observed.

    ``freshness_ok`` / ``continuity_ok`` are ``None`` exactly when unestablished (module
    docstring "Honest-source table"): ``freshness_ok is None`` only when the evidence tip
    has NEVER been observed (``seq is None``, a gap); ``continuity_ok is None`` only on
    this service's first-ever REAL observation (a seq exists, but there is no PRIOR
    observation to compare against yet — an unknown, not a gap). ``continuity_ok`` is left
    ``None`` (never computed) when ``freshness_ok`` is itself ``None`` — the gap already
    says everything there is to say; a second, redundant "also unknown" would double-count
    the same absent fact.
    """

    freshness_ok: bool | None
    continuity_ok: bool | None
    evidence_numeric_state: NumericInputState
    last_seq: int | None
    time_state: str
    time_ok: bool
    unconsumed: int
    inbox_ok: bool


def _require_item_flags(
    raw: dict[str, Any], obligation_ref: str, path: Path
) -> CoverageItem:
    criticality_raw = require_str_field(raw, "criticality", path, MonitoringConfigError)
    try:
        criticality = TelemetryCriticality(criticality_raw)
    except ValueError as exc:
        raise MonitoringConfigError(
            f"{path}: items.{obligation_ref}.criticality {criticality_raw!r} is not a "
            f"valid TelemetryCriticality ({[m.value for m in TelemetryCriticality]!r})"
        ) from exc
    return CoverageItem(
        obligation_ref=obligation_ref,
        scope_dimensions=frozenset(),
        dependency_closure_dimensions=frozenset(),
        restrictive_response_present=require_bool_field(
            raw, "restrictive_response_present", path, MonitoringConfigError
        ),
        alert_path_present=require_bool_field(
            raw, "alert_path_present", path, MonitoringConfigError
        ),
        evidence_path_present=require_bool_field(
            raw, "evidence_path_present", path, MonitoringConfigError
        ),
        currentness_rule_present=require_bool_field(
            raw, "currentness_rule_present", path, MonitoringConfigError
        ),
        closure_1_to_12_complete=require_bool_field(
            raw, "closure_1_to_12_complete", path, MonitoringConfigError
        ),
        excluded=False,
        approved_exclusion_proof_present=None,
        criticality=criticality,
    )


def _load_manifest(body: dict[str, Any], path: Path) -> MonitorCoverageManifest:
    manifest_body = require_mapping_field(body, "manifest", path, MonitoringConfigError)
    items_body = require_mapping_field(body, "items", path, MonitoringConfigError)
    if frozenset(items_body) != frozenset(_OBLIGATION_REFS):
        raise MonitoringConfigError(
            f"{path}: items must carry EXACTLY the three fixed obligations "
            f"{_OBLIGATION_REFS!r} (got {tuple(sorted(items_body))!r}) — this service's "
            "self-observation code only knows how to evaluate these three (module "
            "docstring)"
        )
    coverage_items = tuple(
        _require_item_flags(
            require_mapping_field(items_body, ref, path, MonitoringConfigError),
            ref,
            path,
        )
        for ref in _OBLIGATION_REFS
    )
    try:
        return MonitorCoverageManifest(
            coverage_manifest_id=require_str_field(
                manifest_body, "coverage_manifest_id", path, MonitoringConfigError
            ),
            coverage_generation=require_int_field(
                manifest_body, "coverage_generation", path, MonitoringConfigError
            ),
            coverage_manifest_digest=require_str_field(
                manifest_body, "coverage_manifest_digest", path, MonitoringConfigError
            ),
            policy_digest=require_str_field(
                manifest_body, "policy_digest", path, MonitoringConfigError
            ),
            coverage_items=coverage_items,
            approved_exclusions=(),
            submitted_monitored_assumptions=(),
            is_complete=require_bool_field(
                manifest_body, "is_complete", path, MonitoringConfigError
            ),
            # A score can never replace item-level closure (§9 line 292) — this service
            # never built a score-based coverage shortcut, a code-constant structural
            # fact, not a fabricated one (module docstring precedent: profile.py's
            # `mixed_versions_present=False` cardinality argument).
            coverage_score_present=False,
        )
    except ValidationError as exc:
        raise MonitoringConfigError(
            f"{path}: manifest does not satisfy MonitorCoverageManifest — {exc}"
        ) from exc


def _load_bounds(body: dict[str, Any], path: Path) -> _Bounds:
    bounds_body = require_mapping_field(body, "bounds", path, MonitoringConfigError)
    healthy_states_raw = require_list_field(
        bounds_body, "healthy_time_states", path, MonitoringConfigError
    )
    if not healthy_states_raw or not all(
        isinstance(v, str) and v.strip() for v in healthy_states_raw
    ):
        raise MonitoringConfigError(
            f"{path}: bounds.healthy_time_states must be a non-empty list of non-blank "
            f"strings (got {healthy_states_raw!r})"
        )
    return _Bounds(
        max_evidence_tip_stall_ms=require_int_field(
            bounds_body, "max_evidence_tip_stall_ms", path, MonitoringConfigError
        ),
        healthy_time_states=tuple(healthy_states_raw),
        max_inbox_unconsumed=require_int_field(
            bounds_body, "max_inbox_unconsumed", path, MonitoringConfigError
        ),
    )


def _load_coverage(path: Path) -> _LoadedCoverage:
    raw = load_yaml_document(path, MonitoringConfigError)
    body = require_mapping_field(raw, "coverage", path, MonitoringConfigError)
    manifest = _load_manifest(body, path)
    bounds = _load_bounds(body, path)
    return _LoadedCoverage(manifest=manifest, bounds=bounds, config_path=path)


def _applicable_obligations(manifest: MonitorCoverageManifest) -> frozenset[str]:
    return frozenset(
        item.obligation_ref
        for item in manifest.coverage_items
        if item.obligation_ref is not None
    )


class MonitoringService:
    """The MONITORING :class:`~tos_runtime.safety.ports.SafetyMeshService` (module
    docstring). Construction loads and validates the Monitor Coverage Manifest policy
    document — a missing / still-null / schema-invalid / wrong-obligation-set document
    refuses construction outright (never a ``None`` service instance)."""

    def __init__(
        self,
        *,
        config_path: Path,
        evidence_tip_observer: EvidenceTipObserver,
        time_health_observer: TimeHealthObserver,
        inbox_unconsumed_observer: InboxUnconsumedObserver,
        monotonic_ns: MonotonicClock,
        evidence_recorder: AlertRecorder,
    ) -> None:
        """Load + validate the Monitor Coverage Manifest policy document, fail-closed.

        Args:
            config_path: Path to a policy YAML document (top-level key ``coverage``,
                carrying ``manifest`` + ``items`` + ``bounds`` — see
                ``tos/runtime/config/monitor_coverage.example.yaml``).
            evidence_tip_observer: Module docstring item 1.
            time_health_observer: Module docstring item 2.
            inbox_unconsumed_observer: Module docstring item 3.
            monotonic_ns: The stall detector's own clock (module docstring).
            evidence_recorder: The ``STM_ALERT`` evidence sink (module docstring).

        Raises:
            MonitoringConfigError: The file is missing, unreadable, not valid YAML, not a
                mapping, missing a required field, still null (named-TBD), does not carry
                exactly the three fixed obligations, or fails the kernel record's own
                schema validation.
        """
        self._docs = _load_coverage(config_path)
        self._applicable_obligations = _applicable_obligations(self._docs.manifest)
        self._evidence_tip_observer = evidence_tip_observer
        self._time_health_observer = time_health_observer
        self._inbox_unconsumed_observer = inbox_unconsumed_observer
        self._monotonic_ns = monotonic_ns
        self._evidence_recorder = evidence_recorder

        # Evidence-tip stall-detector bookkeeping (module docstring item 1) — the last
        # observed seq and the monotonic timestamp at which it last CHANGED. Never
        # consulted by a caller directly; purely this service's own staleness memory.
        self._evidence_tip_last_seq: int | None = None
        self._evidence_tip_last_advance_ns: int | None = None
        # Continuity-detector bookkeeping (review disposition, HIGH-2) — the RAW previous
        # (seq, chain_digest) pair, updated on EVERY real observation (unlike the stall
        # tracker above, which only updates when seq changes) — a continuity break is
        # exactly a mismatch between "did seq change" and "did the digest change".
        self._continuity_last_seq: int | None = None
        self._continuity_last_chain_digest: str | None = None
        # The previous clear() call's own STM_ALERT delivery outcome (review disposition,
        # HIGH-2's sibling requirement) — None until a delivery has been attempted and
        # failed; cleared the next time a delivery is attempted and succeeds.
        self._last_delivery_failure: str | None = None
        self._snapshot_generation = 0

    @property
    def identity(self) -> str:
        return _IDENTITY

    @property
    def dimension_key(self) -> DimensionKey:
        return DimensionKey.MONITORING

    def _observe(self, now_ns: int) -> _Observation:
        """Every self-observation port, called exactly once per :meth:`clear` tick (review
        disposition, HIGH-2 — the single source :meth:`_build_snapshot` and :meth:`clear`'s
        own reason derivation both read, so they can never disagree)."""
        seq, chain_digest, _key_generation = self._evidence_tip_observer()

        if seq is None:
            # Never observed at all — a GAP (module docstring "Tri-state combination"),
            # not an "unknown". Continuity is left unjudged: the gap already says
            # everything there is to say about this obligation this tick.
            freshness_ok: bool | None = None
            continuity_ok: bool | None = None
            evidence_numeric_state = NumericInputState.MISSING_SAMPLE
        else:
            if seq != self._evidence_tip_last_seq:
                self._evidence_tip_last_seq = seq
                self._evidence_tip_last_advance_ns = now_ns
            assert self._evidence_tip_last_advance_ns is not None
            stall_ms = (now_ns - self._evidence_tip_last_advance_ns) // _NS_PER_MS
            freshness_ok = stall_ms <= self._docs.bounds.max_evidence_tip_stall_ms
            evidence_numeric_state = NumericInputState.WELL_FORMED

            if self._continuity_last_seq is None:
                # First-ever REAL observation — no prior (seq, digest) to compare against
                # (module docstring "Honest-source table" — the documented first-tick
                # consequence), not a fabricated True.
                continuity_ok = None
            else:
                seq_advanced = seq > self._continuity_last_seq
                seq_regressed = seq < self._continuity_last_seq
                digest_changed = chain_digest != self._continuity_last_chain_digest
                # A regression is always a break; otherwise "advanced" and "digest
                # changed" must agree (both, an ordinary append; neither, an idle tick) —
                # disagreement (an append with no digest movement, or a digest movement
                # with no append) is exactly a torn/rewritten chain.
                continuity_ok = (
                    False if seq_regressed else (seq_advanced == digest_changed)
                )
            self._continuity_last_seq = seq
            self._continuity_last_chain_digest = chain_digest

        time_state = self._time_health_observer()
        time_ok = time_state in self._docs.bounds.healthy_time_states
        unconsumed = self._inbox_unconsumed_observer()
        inbox_ok = unconsumed <= self._docs.bounds.max_inbox_unconsumed

        return _Observation(
            freshness_ok=freshness_ok,
            continuity_ok=continuity_ok,
            evidence_numeric_state=evidence_numeric_state,
            last_seq=self._evidence_tip_last_seq,
            time_state=time_state,
            time_ok=time_ok,
            unconsumed=unconsumed,
            inbox_ok=inbox_ok,
        )

    def _build_snapshot(self, obs: _Observation) -> ContinuousConformanceSnapshot:
        self._snapshot_generation += 1

        active_violations: list[str] = []
        active_unknowns: list[str] = []
        active_gaps: list[str] = []

        if obs.freshness_ok is None:
            active_gaps.append(_OBLIGATION_EVIDENCE_TIP)
        else:
            if obs.freshness_ok is False:
                active_violations.append(_OBLIGATION_EVIDENCE_TIP)
            if obs.continuity_ok is None:
                active_unknowns.append(_OBLIGATION_EVIDENCE_TIP)
            elif obs.continuity_ok is False:
                active_violations.append(_OBLIGATION_EVIDENCE_TIP)

        if obs.time_ok is False:
            active_violations.append(_OBLIGATION_TIME_HEALTH)
        if obs.inbox_ok is False:
            active_violations.append(_OBLIGATION_INBOX_BACKLOG)

        delivery_failures = (
            (self._last_delivery_failure,) if self._last_delivery_failure else ()
        )

        if active_gaps or active_unknowns:
            aggregate_result = AggregateConformanceResult.UNKNOWN
        elif active_violations or delivery_failures:
            aggregate_result = AggregateConformanceResult.NON_CONFORMING
        else:
            aggregate_result = AggregateConformanceResult.CONFORMING

        def _eval_result(values: tuple[bool | None, ...]) -> AggregateConformanceResult:
            if any(v is None for v in values):
                return AggregateConformanceResult.UNKNOWN
            if any(v is False for v in values):
                return AggregateConformanceResult.NON_CONFORMING
            return AggregateConformanceResult.CONFORMING

        manifest = self._docs.manifest
        evaluations = (
            MonitorEvaluation(
                evaluator_digest="stm-evaluator-evidence-tip-v1",
                canonical_input_digest=f"last_seq={obs.last_seq!r}",
                result=_eval_result((obs.freshness_ok, obs.continuity_ok)),
                numeric_input_state=obs.evidence_numeric_state,
            ),
            MonitorEvaluation(
                evaluator_digest="stm-evaluator-time-health-v1",
                canonical_input_digest=f"health_state={obs.time_state!r}",
                result=_eval_result((obs.time_ok,)),
                numeric_input_state=NumericInputState.WELL_FORMED,
            ),
            MonitorEvaluation(
                evaluator_digest="stm-evaluator-inbox-backlog-v1",
                canonical_input_digest=f"unconsumed={obs.unconsumed!r}",
                result=_eval_result((obs.inbox_ok,)),
                numeric_input_state=NumericInputState.WELL_FORMED,
            ),
        )

        return ContinuousConformanceSnapshot(
            snapshot_id=f"{manifest.coverage_manifest_id}-snapshot",
            snapshot_generation=self._snapshot_generation,
            monitor_generation=manifest.coverage_generation,
            policy_digest=manifest.policy_digest,
            critical_telemetry_manifest_digest=manifest.coverage_manifest_digest,
            coverage_manifest_digest=manifest.coverage_manifest_digest,
            scope=manifest.coverage_manifest_id,
            owner_epoch=self.identity,
            monitor_results=evaluations,
            source_continuity_present=obs.continuity_ok,
            active_violations=tuple(active_violations),
            active_unknowns=tuple(active_unknowns),
            active_gaps=tuple(active_gaps),
            active_suppressions=(),
            delivery_failures=delivery_failures,
            aggregate_result=aggregate_result,
        )

    def _reasons_from_observation(self, obs: _Observation) -> list[str]:
        reasons: list[str] = []
        if obs.freshness_ok is None:
            reasons.append(_REASON_EVIDENCE_TIP_UNKNOWN)
        else:
            if obs.freshness_ok is False:
                reasons.append(_REASON_EVIDENCE_TIP_STALL)
            if obs.continuity_ok is None:
                reasons.append(_REASON_CONTINUITY_UNESTABLISHED)
            elif obs.continuity_ok is False:
                reasons.append(_REASON_CONTINUITY_BROKEN)
        if obs.time_ok is False:
            reasons.append(_REASON_TIME_UNHEALTHY)
        if obs.inbox_ok is False:
            reasons.append(_REASON_INBOX_BACKLOG)
        if self._last_delivery_failure is not None:
            reasons.append(_REASON_ALERT_DELIVERY_FAILED)
        return reasons

    def clear(self) -> MeshClearance:
        """The deferred-item / Coordinator verdict (module docstring)."""
        reasons: list[str] = []

        coverage_ok = critical_coverage_complete_or_gap(
            self._docs.manifest,
            self._applicable_obligations,
            frozenset(),
            frozenset(),
        )
        if coverage_ok is not True:
            reasons.append(_REASON_COVERAGE_GAP)

        obs = self._observe(self._monotonic_ns())
        reasons.extend(self._reasons_from_observation(obs))
        snapshot = self._build_snapshot(obs)

        honest = conformance_requires_complete_current_valid(snapshot)
        if honest is not True:
            reasons.append(_REASON_SNAPSHOT_DISHONEST)

        if coverage_ok is not True or honest is not True:
            overall: bool | None = False
        elif snapshot.aggregate_result is AggregateConformanceResult.CONFORMING:
            overall = True
        elif snapshot.aggregate_result is AggregateConformanceResult.UNKNOWN:
            overall = None
        else:
            overall = False

        if overall is True:
            reasons = []

        clearance = MeshClearance(
            identity=self.identity, clear=overall, reasons=tuple(reasons)
        )
        if overall is not True:
            try:
                self._evidence_recorder(
                    _EVIDENCE_KIND_STM_ALERT,
                    {
                        "identity": self.identity,
                        "clear": overall,
                        "reasons": clearance.reasons,
                        "aggregate_result": (
                            snapshot.aggregate_result.value
                            if snapshot.aggregate_result is not None
                            else None
                        ),
                    },
                )
            except Exception as exc:
                # Never swallow (review disposition, HIGH-2's sibling requirement): the
                # caller sees this failure NOW, and the NEXT tick's snapshot honestly
                # carries it in delivery_failures (module docstring "STM_ALERT emission").
                self._last_delivery_failure = (
                    f"{_EVIDENCE_KIND_STM_ALERT}_delivery_failed: {exc!r}"
                )
                raise
            else:
                self._last_delivery_failure = None
        else:
            self._last_delivery_failure = None
        return clearance

    def dimension_report(self) -> DimensionReport | None:
        """This owner's currentness verdict for MONITORING (module docstring).
        ``restrictive_floor`` is ``0`` — a **deliberate** statement, not an invented
        default: Phase 5 has no floor-governance runtime yet (the same "an owner
        reporting 0 is that owner's own choice" discipline
        :class:`~tos_runtime.currentness.vector.DimensionReport`'s own docstring
        states)."""
        return DimensionReport(
            bound_generation=self._docs.manifest.coverage_generation,
            positively_established=self.clear().clear is True,
            restrictive_floor=0,
        )

    def describe(self) -> dict[str, Any]:
        """Evidence-facing description of the loaded policy document — names,
        generations, and bounds only; never a secret / bearer token
        (:class:`~tos_runtime.safety.ports.SafetyMeshService.describe` contract)."""
        manifest = self._docs.manifest
        bounds = self._docs.bounds
        return {
            "identity": self.identity,
            "config_path": str(self._docs.config_path),
            "coverage_manifest_id": manifest.coverage_manifest_id,
            "coverage_generation": manifest.coverage_generation,
            "obligation_refs": sorted(self._applicable_obligations),
            "max_evidence_tip_stall_ms": bounds.max_evidence_tip_stall_ms,
            "healthy_time_states": list(bounds.healthy_time_states),
            "max_inbox_unconsumed": bounds.max_inbox_unconsumed,
        }
