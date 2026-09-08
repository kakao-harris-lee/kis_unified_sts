"""``SafetyAuthorityEpochService`` — the Safety Authority epoch runtime (design #40
§5 order 4, slice plan §1 item 1).

**This service does not judge.** It collects inputs — the log's own committed
entries, the injected :class:`~tos_runtime.time.service.TrustworthyTimeService`
snapshot, and a configured containment bound — and calls the kernel's own
conservative, fail-closed predicates (``tos.authority.predicates``) to derive
:class:`~tos.authority.state.AuthorityEpochState` and
:class:`~tos.authority.state.CurrentnessWitness`. It never itself decides
whether an epoch or a capability is current; that is
``tos.authority.authority_epoch_current`` / ``currentness_admissible`` /
``permissive_capability_valid``'s job (:mod:`tos_runtime.authority.capability`
calls the last one).

**Writer epoch != Safety Authority epoch (design #40 v1.1 note (2)).** The RCL
``WriterEpoch`` this service's ``append_cas`` calls are fenced under (a single
integer, ``tos_runtime.rcl.log.SqliteCommitLog.acquire_epoch``) and the Safety
Authority epoch this service issues/reads (``AuthorityEpochState
.current_epoch_floor``, a *different*, independently-advancing counter scoped
to ``authority_domain``) are never equated anywhere in this module. The two
values happen to both be committed through the same
:class:`~tos_runtime.rcl.log.SqliteCommitLog` instance, but one fences *who may
write to the log at all* and the other fences *which Safety Authority epoch a
capability was issued under* — ``tos.rcl.commitlog``'s own module docstring
makes exactly this distinction for ``AuthorityEpochTransitionRecord`` (see its
"anti-phantom greps recorded" section).

**Reported ``CommandType`` gap (slice plan §5: "새 CommandType 이 필요하면 커널
편집 대신 보고").** No member of the closed ``tos.rcl.vocabulary.CommandType``
vocabulary names "Safety Authority epoch transition" — the 16 ADR-002-012 §10
persistence commands and the 11 ADR-002-002 §27 conceptual commands are all
RCL capacity/order-lifecycle verbs (``CommitReservation``, ``BindAttempt``,
``RecordFill``, ...). The closest *structural* analog is
:data:`~tos.rcl.vocabulary.CommandType.ADVANCE_RESTORE_GENERATION` — also a
durably-committed, strictly-monotonic generation-like counter advance — even
though its named referent (ADR-002-017 Recovery Generation) is a different
governed axis from the Safety Authority epoch (ADR-002-003 §5). This is a
**reported gap, not resolved by adding a kernel member**: this module never
edits ``tos.rcl.vocabulary``; it reuses ``ADVANCE_RESTORE_GENERATION`` as the
closest available ``kind`` and disambiguates the actual epoch domain/value
entirely through the log-visible ``command_id`` (see
:func:`_epoch_transition_command_id`), never through ``kind`` alone.

**Deriving state from the log without a payload-read API.** The kernel
``CommitLog.append_cas``/``read_linearizable``/``replay`` Protocol exposes only
``CommitEntry(seq, writer_epoch, command_id, command_digest, kind,
payload_digest)`` — the full JSON payload a caller supplies to ``append_cas``
is durably stored by :class:`~tos_runtime.rcl.log.SqliteCommitLog` but is
**not** returned by any Protocol read path (only the reservation-transition
side channel folds ``payload_json`` for its own dedicated
``reservations`` projection). :meth:`SafetyAuthorityEpochService.current_state`
therefore never depends on payload readback: every committed transition's
``command_id`` is itself content-addressed as
``f"authority-epoch-transition:{authority_domain}:{new_epoch}"``
(:func:`_epoch_transition_command_id`) — a value ``read_linearizable`` DOES
return — so the current epoch floor is derivable purely by scanning
``command_id`` strings for the matching ``kind`` and domain prefix and taking
the maximum embedded ``new_epoch``. No cache, no separate projection table.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml
from tos.authority import (
    AuthorityEpochState,
    AuthorityEpochTransitionRecord,
    AuthorityTransitionReason,
    CurrentnessWitness,
    authority_epoch_current,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalizationScheme, get_scheme
from tos.rcl import AppendReceipt, AppendRefusal, CommandType, CommitEntry
from tos.time import HealthState

from tos_runtime.rcl.log import SqliteCommitLog, StaleEpochRead
from tos_runtime.time.service import TimeServiceNotStarted, TrustworthyTimeService

__all__ = [
    "AuthorityEpochTransitionRefused",
    "AuthorityRuntimeConfig",
    "SafetyAuthorityEpochService",
    "load_authority_config",
]

#: Command-id prefix for every authority-epoch-transition entry this service
#: commits — never reused for any other purpose (module docstring, "deriving
#: state from the log" section).
_EPOCH_TRANSITION_PREFIX = "authority-epoch-transition"

#: The reported-gap ``CommandType`` choice (module docstring). Fixed here so
#: both the writer (:meth:`SafetyAuthorityEpochService.transition`) and the
#: reader (:meth:`SafetyAuthorityEpochService.current_state`) agree on exactly
#: one value.
_EPOCH_TRANSITION_KIND = CommandType.ADVANCE_RESTORE_GENERATION

_EVIDENCE_KIND = "AUTHORITY_EPOCH_TRANSITION"
_EVIDENCE_RECORD_CLASS = "AUTHORITY_EPOCH_TRANSITION"


class AuthorityEpochTransitionRefused(RuntimeError):
    """Raised by :meth:`SafetyAuthorityEpochService.transition` on an RCL refusal.

    Carries the log's own :class:`~tos.rcl.AppendRefusal` verbatim — this
    service invents no refusal vocabulary of its own for the CAS-append
    mechanics (stale epoch / seq mismatch / duplicate / store unavailable are
    all the log's closed ``AppendRefusalReason`` already).
    """

    def __init__(self, refusal: AppendRefusal) -> None:
        super().__init__(f"authority epoch transition refused: {refusal.reason}")
        self.refusal = refusal


def _epoch_transition_command_id(authority_domain: str, new_epoch: int) -> str:
    """The content-addressed, log-visible id one epoch transition commits under."""
    return f"{_EPOCH_TRANSITION_PREFIX}:{authority_domain}:{new_epoch}"


class AuthorityRuntimeConfig:
    """The fully-valued Safety Authority runtime config (slice plan §1 item 1).

    ``containment_bound_ms`` is the online-currentness-witness containment
    bound (module docstring; ADR-002-003 §12.1). No VER-002 profile key names
    this specific bound today (grepped 2026-09-08: the VER-002-001 evidence
    spec names ``B_authority_partition_detect`` and the *egress*-currentness
    bounds ``MAX_egress_currentness_proof_age_ms`` /
    ``MAX_currentness_vector_age_ms``, but no ``MAX_*`` bound for the Safety
    Authority epoch's own online witness) — this is therefore a
    ``named-TBD`` key per slice plan §5, and a configured ``null`` value is a
    fail-closed refusal to start (:func:`load_authority_config`), never a
    silent default.

    ``trading_approval_policy_generation`` is the currently-loaded Trading
    Approval Policy's own ``policy_generation`` (:class:`tos.iap.TradingApprovalPolicy`
    field name, "spec terms = code terms") —
    :meth:`~tos_runtime.authority.iap.IntentRegistry.decision_current` (added
    2026-09-08) compares a decision's own
    ``trading_approval_policy_generation`` against this value (equality of
    generation identifiers is the ONLY comparison authored there; no kernel
    predicate judges decision currency — ADR-002-023 §12 item 2 only NAMES
    the fact, ``tos.iap.predicates`` takes it as an injected ``bool | None``).
    Unlike ``containment_bound_ms`` this is not a VER-002 bound at all (no
    threshold to approve) — it is an operational value (which policy
    generation is currently active) — but it is still configuration, not a
    code constant, and a ``null`` value is still a fail-closed refusal to
    start (:func:`load_authority_config`).
    """

    __slots__ = ("containment_bound_ms", "trading_approval_policy_generation")

    def __init__(
        self,
        *,
        containment_bound_ms: int | None,
        trading_approval_policy_generation: int | None = None,
    ) -> None:
        """Args:
        containment_bound_ms: The bound in milliseconds.
            :func:`load_authority_config` never returns an instance with
            this ``None`` (it refuses to load first) — a direct caller
            MAY still construct one with ``None`` to exercise
            :meth:`SafetyAuthorityEpochService.witness`'s own
            ``containment_bound_unconfigured`` fail-closed branch (e.g. in
            tests), which is exactly why this stays ``int | None`` rather
            than a plain ``int``.
        trading_approval_policy_generation: The currently-loaded Trading
            Approval Policy's own generation. :func:`load_authority_config`
            never returns an instance with this ``None`` either — a direct
            caller MAY still omit it (default ``None``) for tests that do
            not exercise :meth:`~tos_runtime.authority.iap.IntentRegistry.decision_current`.
        """
        self.containment_bound_ms = containment_bound_ms
        self.trading_approval_policy_generation = trading_approval_policy_generation


class AuthorityConfigError(RuntimeError):
    """Raised by :func:`load_authority_config` on a missing/invalid/null config."""


def _resolve_positive_int_key(
    raw: dict[str, Any], key: str, path: Path, *, named_tbd_note: str
) -> int:
    """Shared fail-closed positive-int resolution for both config keys."""
    value = raw.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AuthorityConfigError(
            f"load_authority_config: {key!r} {named_tbd_note} and must be a "
            f"positive integer once assigned — got {value!r} at {path}; "
            "refusing to start (fail-closed, never a silent default)"
        )
    return value


def load_authority_config(path: Path) -> AuthorityRuntimeConfig:
    """Load + fail-closed-validate ``authority.example.yaml``-shaped config.

    Args:
        path: The YAML config file.

    Returns:
        The fully-valued :class:`AuthorityRuntimeConfig`.

    Raises:
        AuthorityConfigError: The file is unreadable, not YAML, not a mapping,
            or either ``containment_bound_ms`` / ``trading_approval_policy_generation``
            is absent/``null``/non-positive — an unresolved key is a refusal
            to start, never a silent default (module docstring; slice plan §5).
    """
    try:
        raw_text = path.read_text()
    except OSError as exc:
        raise AuthorityConfigError(
            f"load_authority_config: cannot read {path}: {exc}"
        ) from exc
    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise AuthorityConfigError(
            f"load_authority_config: {path} is not valid YAML: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise AuthorityConfigError(
            f"load_authority_config: {path} must parse to a mapping "
            f"(got {type(raw).__name__})"
        )
    bound = _resolve_positive_int_key(
        raw,
        "containment_bound_ms",
        path,
        named_tbd_note="is a named-TBD key (no VER-002 profile key names this bound yet)",
    )
    policy_generation = _resolve_positive_int_key(
        raw,
        "trading_approval_policy_generation",
        path,
        named_tbd_note="is the currently-loaded Trading Approval Policy generation",
    )
    return AuthorityRuntimeConfig(
        containment_bound_ms=bound,
        trading_approval_policy_generation=policy_generation,
    )


class SafetyAuthorityEpochService:
    """The Safety Authority epoch service (design #40 §5 order 4 item 1).

    Every authority-making transition (epoch issue/advance) is one RCL
    ``append_cas`` entry — never memory, never a separate file (slice plan §0).
    :meth:`current_state` re-derives the epoch floor from
    ``log.read_linearizable`` on every call (no cache, module docstring).
    """

    def __init__(
        self,
        log: SqliteCommitLog,
        time: TrustworthyTimeService,
        evidence: Any,
        *,
        authority_domain: str,
        writer_epoch: int,
        config: AuthorityRuntimeConfig,
        canonicalization_version: str = EV_L1_PROVISIONAL_VERSION,
    ) -> None:
        """Compose the service over its injected ports.

        Args:
            log: The Safety Commit Log this service's transitions are
                committed through (``append_cas`` only — never
                ``apply_reservation_transition``, which is a different,
                concurrently-changing lane's surface, slice plan lane
                contract).
            time: The injected Trustworthy Time health service —
                :meth:`witness` reads its ``current_snapshot()``; this
                service never reads a raw clock itself.
            evidence: The durable append port
                (:class:`~tos_runtime.evidence.ports.EvidenceAppendPort`)
                this service's own domain-labelled records are committed
                through, in addition to whatever the log's own internal
                evidence port already records for the RCL entry itself.
            authority_domain: The Safety Authority domain this instance owns
                (ADR-002-003 §5.1 — a domain is required-concrete for
                ``authority_epoch_current`` to ever hold).
            writer_epoch: The RCL Writer Epoch this instance's ``append_cas``
                calls are fenced under (acquired once, by the composition
                root, via ``log.acquire_epoch`` — never re-acquired here;
                module docstring "writer epoch != Safety Authority epoch").
            config: The fully-valued :class:`AuthorityRuntimeConfig`.
            canonicalization_version: The registered ``tos.canonical`` scheme
                version used to digest every issued
                :class:`~tos.authority.AuthorityEpochTransitionRecord`.
        """
        self._log = log
        self._time = time
        self._evidence = evidence
        self._authority_domain = authority_domain
        self._writer_epoch = writer_epoch
        self._config = config
        self._scheme: CanonicalizationScheme = get_scheme(canonicalization_version)
        #: High-water mark of the last successfully-verified "now" (module
        #: docstring's :meth:`witness` design) — ``None`` until the first
        #: successful online verification.
        self._last_verified_monotonic_ms: int | None = None

    # -- state derivation (no cache) --------------------------------------

    def current_state(self) -> AuthorityEpochState:
        """Derive the current :class:`~tos.authority.AuthorityEpochState`.

        Re-reads ``log.read_linearizable`` every call — never cached. A
        stale-epoch read (this instance's ``writer_epoch`` has been usurped)
        or any other log-read failure (e.g. the underlying sqlite file being
        locked/unreachable — ``sqlite3.Error``, 2026-09-08 independent-review
        MEDIUM fix) yields the fully-``None`` (fenced) state — the kernel's
        own ``authority_epoch_current`` already treats ``None`` coordinates
        as fenced, so this is the honest, fail-closed answer rather than a
        raised exception for a routine currentness check.
        """
        try:
            view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        except (StaleEpochRead, sqlite3.Error):
            return AuthorityEpochState()
        prefix = f"{_EPOCH_TRANSITION_PREFIX}:{self._authority_domain}:"
        max_epoch: int | None = None
        for entry in view.entries:
            if entry.kind is not _EPOCH_TRANSITION_KIND:
                continue
            if entry.command_id is None or not entry.command_id.startswith(prefix):
                continue
            suffix = entry.command_id[len(prefix) :]
            try:
                candidate = int(suffix)
            except ValueError:
                continue  # malformed id from an unrelated caller — never trusted
            if max_epoch is None or candidate > max_epoch:
                max_epoch = candidate
        if max_epoch is None:
            return AuthorityEpochState()
        return AuthorityEpochState(
            authority_domain=self._authority_domain, current_epoch_floor=max_epoch
        )

    def current_epoch(self) -> int | None:
        """Convenience accessor: :meth:`current_state`'s epoch floor, or ``None``."""
        return self.current_state().current_epoch_floor

    # -- online currentness witness ---------------------------------------

    def witness(self) -> CurrentnessWitness:
        """The online currentness witness (ADR-002-003 §12.1; slice plan §1 item 1).

        **The baseline is the monotonic instant of the last call that returned
        ``present=True`` — never anything else.** ``present=True`` only when
        (a) the injected time service's snapshot is currently
        ``HealthState.TRUSTED``, (b) the containment bound is configured,
        (c) a fresh ``read_linearizable`` on this instance's log succeeds, and
        (d) the elapsed monotonic time since that baseline is within
        ``config.containment_bound_ms`` (first-ever successful verification
        establishes the baseline at age 0).

        **Every ``present=False`` path leaves the baseline COMPLETELY
        UNTOUCHED** (2026-09-08 independent-review MEDIUM fix) — it is never
        reset to "now" and never cleared to ``None``. This closes a fail-open
        this module previously had: resetting the baseline to "now" on an
        expired-window return meant a second, immediately-following call (same
        time-service snapshot, no further ``evaluate()``) computed age 0
        against that just-reset baseline and reported ``present=True`` again —
        the containment gate was measuring call *cadence*, not a genuine
        online re-verification (ADR-002-003 :183 "a cached grant SHALL NOT
        authorize after online verification is lost"). With the baseline
        frozen at the last TRUE instant, a caller that lets the window expire
        gets ``present=False`` on every subsequent call, indefinitely, until a
        read that is *itself* within ``containment_bound_ms`` of that frozen
        baseline succeeds — which is exactly why a **transient** failure (the
        log briefly unreachable, or time briefly not ``TRUSTED``, resolved
        before real time has moved past the bound) recovers to ``True`` on
        the next successful read, while a **caller that simply stops polling
        long enough for real time to exceed the bound** does not recover on
        its own — the window is a one-way door once genuinely violated,
        deliberately (a Safety Authority currentness bound is not a self-
        healing cache-refresh timer; a real re-establishment event, e.g. a
        fresh epoch ``transition``, is what the design otherwise consults).
        A ``containment_bound_ms`` of ``0`` (never returned by
        :func:`load_authority_config`, which requires a positive int, but
        directly constructible via :class:`AuthorityRuntimeConfig` — e.g. in
        a test) is therefore ``present=True`` only at the exact read instant
        that establishes/re-confirms the baseline (age exactly ``0``) and
        ``False`` on every subsequent call once monotonic time has moved on
        at all.
        """
        try:
            snapshot = self._time.current_snapshot()
        except TimeServiceNotStarted:
            return CurrentnessWitness(
                present=False, witness_source="time_service_not_started"
            )
        if snapshot.health_state is not HealthState.TRUSTED:
            return CurrentnessWitness(
                present=False, witness_source="time_health_not_trusted"
            )
        if self._config.containment_bound_ms is None:
            return CurrentnessWitness(
                present=False, witness_source="containment_bound_unconfigured"
            )
        try:
            self._log.read_linearizable(writer_epoch=self._writer_epoch)
        except StaleEpochRead:
            return CurrentnessWitness(present=False, witness_source="stale_epoch_read")
        except sqlite3.Error:
            # The underlying log file is locked/unreachable — a genuine read
            # failure (2026-09-08 independent-review MEDIUM fix), never a
            # raised exception for a routine currentness check.
            return CurrentnessWitness(present=False, witness_source="log_unreachable")
        now_ms = snapshot.evaluated_monotonic_anchor.monotonic_anchor_value
        if now_ms is None:
            # The snapshot itself carries no concrete monotonic reading — an
            # unestablished coordinate is never treated as fresh (fail-closed,
            # mirrors the kernel's own None-coordinate discipline).
            return CurrentnessWitness(
                present=False, witness_source="snapshot_monotonic_value_absent"
            )
        previous = self._last_verified_monotonic_ms
        if previous is None:
            # First-ever successful online verification — establish the
            # baseline now, at age 0.
            self._last_verified_monotonic_ms = now_ms
            return CurrentnessWitness(
                present=True, within_containment_bound=True, witness_source="rcl_log"
            )
        age_ms = now_ms - previous
        if age_ms < 0 or age_ms > self._config.containment_bound_ms:
            # A regression, or a genuinely expired window: never treat as
            # fresh, and — critically — never touch the baseline (it stays
            # frozen at `previous`; see the method docstring).
            return CurrentnessWitness(
                present=False,
                within_containment_bound=False,
                witness_source="rcl_log",
            )
        # A successful, still-within-bound re-verification: ratchet the
        # baseline forward to this instant.
        self._last_verified_monotonic_ms = now_ms
        return CurrentnessWitness(
            present=True, within_containment_bound=True, witness_source="rcl_log"
        )

    # -- epoch transitions (authority-making; RCL-committed) --------------

    def transition(
        self,
        *,
        leader_identity: str,
        transition_reason: AuthorityTransitionReason,
    ) -> AuthorityEpochTransitionRecord:
        """Issue + durably commit the next Safety Authority epoch transition.

        Args:
            leader_identity: The identity claiming the new epoch (§10 line
                370).
            transition_reason: One of the 8 §10.2 epoch-advancement triggers.

        Returns:
            The issued, digest-verified :class:`AuthorityEpochTransitionRecord`.

        Raises:
            AuthorityEpochTransitionRefused: The RCL append was refused (stale
                writer epoch, seq mismatch, duplicate, or store unavailable —
                the log's own closed vocabulary, never invented here).
        """
        current = self.current_state()
        old_epoch = current.current_epoch_floor or 0
        new_epoch = old_epoch + 1
        witness = self.witness()
        record = AuthorityEpochTransitionRecord.issue(
            scheme=self._scheme,
            transition_id=_epoch_transition_command_id(
                self._authority_domain, new_epoch
            ),
            authority_domain=self._authority_domain,
            old_epoch=old_epoch,
            new_epoch=new_epoch,
            leader_identity=leader_identity,
            transition_reason=transition_reason,
            currentness_witness=witness,
        )
        assert isinstance(record, AuthorityEpochTransitionRecord)
        payload_json = json.dumps(record.model_dump(mode="json"), sort_keys=True)
        try:
            view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        except StaleEpochRead as exc:
            raise AuthorityEpochTransitionRefused(
                AppendRefusal(reason=exc.reason, detail=str(exc))
            ) from exc
        expected_seq = -1 if view.last_seq is None else view.last_seq
        entry = CommitEntry(
            command_id=record.transition_id,
            command_digest=record.canonical_digest,
            kind=_EPOCH_TRANSITION_KIND,
        )
        result = self._log.append_cas(
            entry,
            expected_seq=expected_seq,
            writer_epoch=self._writer_epoch,
            payload_json=payload_json,
        )
        if isinstance(result, AppendRefusal):
            raise AuthorityEpochTransitionRefused(result)
        assert isinstance(result, AppendReceipt)
        self._evidence.append(
            {
                "authority_domain": self._authority_domain,
                "old_epoch": old_epoch,
                "new_epoch": new_epoch,
                "leader_identity": leader_identity,
                "transition_reason": transition_reason.value,
                "transition_id": record.transition_id,
                "canonical_digest": record.canonical_digest,
            },
            kind=_EVIDENCE_KIND,
            record_class=_EVIDENCE_RECORD_CLASS,
        )
        return record

    def epoch_current(self, claimed_epoch: int | None) -> bool:
        """Whether ``claimed_epoch`` is current for this instance's domain (§5.1)."""
        return authority_epoch_current(
            claimed_epoch, self._authority_domain, self.current_state()
        )
