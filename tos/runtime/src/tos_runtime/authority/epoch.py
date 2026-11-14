"""Runtime owner for Safety Authority epoch and currentness state."""

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

from tos_runtime.rcl.log import CommitLogCorruption, SqliteCommitLog, StaleEpochRead
from tos_runtime.time.service import TimeServiceNotStarted, TrustworthyTimeService

__all__ = [
    "AuthorityEpochTransitionRefused",
    "AuthorityRuntimeConfig",
    "SafetyAuthorityEpochService",
    "load_authority_config",
]

_EPOCH_TRANSITION_PREFIX = "authority-epoch-transition"

_EPOCH_TRANSITION_KIND = CommandType.ADVANCE_AUTHORITY_EPOCH

_EVIDENCE_KIND = "AUTHORITY_EPOCH_TRANSITION"
_EVIDENCE_RECORD_CLASS = "AUTHORITY_EPOCH_TRANSITION"


class AuthorityEpochTransitionRefused(RuntimeError):
    """Raised by :meth:`SafetyAuthorityEpochService.transition` on an RCL refusal."""

    def __init__(self, refusal: AppendRefusal) -> None:
        super().__init__(f"authority epoch transition refused: {refusal.reason}")
        self.refusal = refusal


def _epoch_transition_command_id(authority_domain: str, new_epoch: int) -> str:
    """The content-addressed, log-visible id one epoch transition commits under."""
    return f"{_EPOCH_TRANSITION_PREFIX}:{authority_domain}:{new_epoch}"


class AuthorityRuntimeConfig:
    """The fully-valued Safety Authority runtime config (slice plan §1 item 1)."""

    __slots__ = ("containment_bound_ms", "trading_approval_policy_generation")

    def __init__(
        self,
        *,
        containment_bound_ms: int | None,
        trading_approval_policy_generation: int | None = None,
    ) -> None:
        """Args:"""
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
    """Load + fail-closed-validate ``authority.example.yaml``-shaped config."""
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
    """The Safety Authority epoch service (design #40 §5 order 4 item 1)."""

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
        """Compose the service over its injected ports."""
        self._log = log
        self._time = time
        self._evidence = evidence
        self._authority_domain = authority_domain
        self._writer_epoch = writer_epoch
        self._config = config
        self._scheme: CanonicalizationScheme = get_scheme(canonicalization_version)
        self._last_verified_monotonic_ms: int | None = None

    def current_state(self) -> AuthorityEpochState:
        """Derive the current :class:`~tos.authority.AuthorityEpochState`."""
        try:
            view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        except (StaleEpochRead, sqlite3.Error):
            return AuthorityEpochState()
        prefix = f"{_EPOCH_TRANSITION_PREFIX}:{self._authority_domain}:"
        max_epoch: int | None = None
        for entry in view.entries:
            if entry.command_id is None or not entry.command_id.startswith(prefix):
                continue
            if entry.kind is not _EPOCH_TRANSITION_KIND:
                raise CommitLogCorruption(
                    "SafetyAuthorityEpochService.current_state: entry "
                    f"{entry.command_id!r} matches the epoch-transition prefix "
                    f"for domain {self._authority_domain!r} but kind="
                    f"{entry.kind!r} is not {_EPOCH_TRANSITION_KIND!r} — refusing "
                    "to silently skip a legacy/foreign-kind entry under this "
                    "prefix (fail-closed; kernel round #1 §2.1)"
                )
            suffix = entry.command_id[len(prefix) :]
            try:
                candidate = int(suffix)
            except ValueError:
                continue
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

    def witness(self) -> CurrentnessWitness:
        """The online currentness witness (ADR-002-003 §12.1; slice plan §1 item 1)."""
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
            return CurrentnessWitness(present=False, witness_source="log_unreachable")
        now_ms = snapshot.evaluated_monotonic_anchor.monotonic_anchor_value
        if now_ms is None:
            return CurrentnessWitness(
                present=False, witness_source="snapshot_monotonic_value_absent"
            )
        previous = self._last_verified_monotonic_ms
        if previous is None:
            self._last_verified_monotonic_ms = now_ms
            return CurrentnessWitness(
                present=True, within_containment_bound=True, witness_source="rcl_log"
            )
        age_ms = now_ms - previous
        if age_ms < 0 or age_ms > self._config.containment_bound_ms:
            return CurrentnessWitness(
                present=False,
                within_containment_bound=False,
                witness_source="rcl_log",
            )
        self._last_verified_monotonic_ms = now_ms
        return CurrentnessWitness(
            present=True, within_containment_bound=True, witness_source="rcl_log"
        )

    def transition(
        self,
        *,
        leader_identity: str,
        transition_reason: AuthorityTransitionReason,
    ) -> AuthorityEpochTransitionRecord:
        """Issue + durably commit the next Safety Authority epoch transition."""
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
