"""``tos_runtime.safety.ack`` — single-operator STM alert acknowledgement (TOS
runtime operations wiring plan ``docs/plans/2026-09-13-tos-runtime-operations-
wiring-plan.md`` §2 decision 4; ADR-002-028 :159/:187/:191/:388/:511).

**Acknowledgement is not containment, remediation, incident closure, recovery
readiness, or re-arm** (ADR-002-028 :388: "Recipient acknowledgement means
only that the exact alert was received by an authenticated effective person
or approved automated endpoint. It is not containment, remediation, broker
finality, incident closure, recovery readiness, or re-arm."). This module's
only observable effect is appending one ``STM_ALERT_ACKNOWLEDGED`` evidence
row — a fact a projection reader may later fold into the operator
projection's ``resolved_stm_alert_seqs`` input
(:mod:`tos_runtime.compose._operations_wiring`). It never evaluates, never
touches :meth:`~tos_runtime.safety.monitoring.MonitoringService.clear`'s own
verdict, never latches or clears a new-risk halt, and never re-arms
anything.

**Structural pin (ADR-002-028 :159/:187/:388).** This module imports nothing
from ``tos_runtime.safety.monitoring``, ``tos_runtime.safety.latch``,
``tos_runtime.safety.rearm``, or ``tos_runtime.engine.inbox`` — an AST-level
import scan in ``tests/safety/test_ack.py`` proves it mechanically (mirrors
``tests/engine/test_no_direct_latch_clear.py``'s own "make the invariant
mechanical, not conventional" discipline). An acknowledgement can therefore
never be wired, even by accident, into any of those modules' decisions —
there is no import path from here into them at all.

**The custody idiom is replicated, not shared.** The acknowledging file is
an operator-authored ``approvals/alerts/<alert_seq>.yaml`` document under
the SAME 0600-mode + owner-uid + ``environment_label`` custody convention
:mod:`tos_runtime.authority.iap` (``load_operator_approval_file``) and
:mod:`tos_runtime.safety.rearm` (``_load_raw_rearm_file`` /
``_verify_environment_label``) already use for their own operator-authored
approval files — both of those modules' own loader helpers are private
(module-local, not exported), so this module replicates the same idiom
locally rather than import a leading-underscore name across a package
boundary (the same discipline :mod:`tos_runtime.safety.rearm`'s own module
docstring already applies when it reuses
:func:`~tos_runtime.custody.file_custody.verify_file_mode_and_owner`
directly but re-authors its own read/parse wrapper).

**Fields.** ``principal_id`` (non-empty ``str`` — the acknowledging
operator's identity) and ``acknowledged_at_label`` (an opaque ``str`` the
operator writes — never parsed as a timestamp, never a time-predicate
input; this module reads no clock at all) plus the same
``environment_label`` every operator-authored file here carries.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib
(``json``, ``os``) + ``pyyaml`` + ``tos_runtime.custody`` +
``tos_runtime.evidence.store`` only.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tos_runtime.custody.file_custody import verify_file_mode_and_owner
from tos_runtime.custody.ports import CustodyLoadRefused
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = [
    "AckOutcome",
    "AlertAcknowledgementFileError",
    "acknowledge_alert",
]

#: Duplicated from :mod:`tos_runtime.safety.monitoring` (a private module constant
#: there, ``_EVIDENCE_KIND_STM_ALERT`` — not exported) and from
#: :mod:`tos_runtime.compose._operations_wiring` (its own ``_STM_ALERT_KIND`` — also
#: not exported) — the SAME "duplicate the literal, do not import a leading-
#: underscore name across a package boundary" discipline both of those modules'
#: own docstrings already apply. This module structurally cannot import
#: ``tos_runtime.safety.monitoring`` at all (module docstring), so the duplication
#: here is not optional.
_EVIDENCE_KIND_STM_ALERT = "STM_ALERT"

#: The evidence kind this module is the sole producer of (module docstring; plan
#: §2 decision 4/8). Read back by :mod:`tos_runtime.compose._operations_wiring`'s
#: own resolved-seq reader.
EVIDENCE_KIND_STM_ALERT_ACKNOWLEDGED = "STM_ALERT_ACKNOWLEDGED"


class AlertAcknowledgementFileError(Exception):
    """Raised internally for any refusal reading/validating the on-disk ack file —
    always caught by :func:`acknowledge_alert` and turned into a refused
    :class:`AckOutcome`, never propagated to the caller."""


@dataclass(frozen=True)
class AckOutcome:
    """The outcome of one :func:`acknowledge_alert` call.

    Attributes:
        acknowledged: ``True`` only when a fresh ``STM_ALERT_ACKNOWLEDGED``
            row was durably appended by this call.
        evidence_seq: That row's own ``seq``, or ``None`` on any refusal
            (including "already acknowledged", which appends nothing new).
        reason: A short, non-secret disclosure of the refusal reason, or
            ``"ACKNOWLEDGED"`` on success — never file content, never a
            principal's raw identity beyond what the operator's own file
            already named.
    """

    acknowledged: bool
    evidence_seq: int | None
    reason: str


def _load_raw_ack_file(
    path: Path, *, expected_owner_uid: int, getuid: Callable[[], int]
) -> dict[str, Any]:
    """Custody-gated read + parse of ``approvals/alerts/<alert_seq>.yaml`` — the
    same 0600-mode + owner-uid custody rule
    :func:`~tos_runtime.custody.file_custody.verify_file_mode_and_owner` enforces
    for every other operator-authored file in this runtime (module docstring)."""
    if not path.is_file():
        raise AlertAcknowledgementFileError(f"alert ack file not found: {path}")
    try:
        verify_file_mode_and_owner(
            path, expected_owner_uid=expected_owner_uid, getuid=getuid
        )
    except CustodyLoadRefused as exc:
        raise AlertAcknowledgementFileError(
            f"{path} failed the custody mode/owner gate: {exc}"
        ) from exc
    try:
        raw_text = path.read_text()
    except OSError as exc:
        raise AlertAcknowledgementFileError(f"cannot read {path}: {exc}") from exc
    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise AlertAcknowledgementFileError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise AlertAcknowledgementFileError(
            f"{path} must parse to a mapping (got {type(raw).__name__})"
        )
    return raw


def _verify_environment_label(
    raw: Mapping[str, Any], path: Path, environment_label: str
) -> None:
    """Cross-environment isolation — the file's own label must byte-exact match
    the runtime's (the same rule :mod:`tos_runtime.authority.iap` and
    :mod:`tos_runtime.safety.rearm` each apply to their own operator files)."""
    file_label = raw.get("environment_label")
    if file_label != environment_label or not file_label:
        raise AlertAcknowledgementFileError(
            f"{path} environment_label={file_label!r} does not match runtime "
            f"environment_label={environment_label!r} — refuse (cross-environment "
            "isolation)"
        )


def _verify_principal_id(raw: Mapping[str, Any], path: Path) -> str:
    principal_id = raw.get("principal_id")
    if not isinstance(principal_id, str) or not principal_id.strip():
        raise AlertAcknowledgementFileError(
            f"{path} 'principal_id' is missing or blank"
        )
    return principal_id


def _verify_acknowledged_at_label(raw: Mapping[str, Any], path: Path) -> str:
    """An opaque, operator-written string — never parsed as a timestamp, never a
    time-predicate input (module docstring)."""
    label = raw.get("acknowledged_at_label")
    if not isinstance(label, str) or not label.strip():
        raise AlertAcknowledgementFileError(
            f"{path} 'acknowledged_at_label' is missing or blank"
        )
    return label


def _alert_row_exists(evidence_store: SqliteEvidenceStore, alert_seq: int) -> bool:
    """Whether ``alert_seq`` names a real, already-committed ``STM_ALERT`` evidence
    row — checked so an ack file can never manufacture an acknowledgement of a seq
    that was never actually alerted (plan §2 decision 4's own "target seq must be
    a real STM_ALERT row" requirement; mutation M9)."""
    row = evidence_store.connection.execute(
        "SELECT 1 FROM entries WHERE seq = ? AND kind = ?",
        (alert_seq, _EVIDENCE_KIND_STM_ALERT),
    ).fetchone()
    return row is not None


def _already_acknowledged(evidence_store: SqliteEvidenceStore, alert_seq: int) -> bool:
    """Whether a prior ``STM_ALERT_ACKNOWLEDGED`` row already names ``alert_seq`` —
    read from the store's own durable history (never an in-process cache), so a
    freshly re-opened process over the same store refuses a second acknowledgement
    identically (mirrors :meth:`~tos_runtime.safety.rearm.ReArmWorkflow
    ._prior_consumptions`'s own log-enforced, not memory-enforced, discipline)."""
    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ?",
        (EVIDENCE_KIND_STM_ALERT_ACKNOWLEDGED,),
    ).fetchall()
    for (payload_json,) in rows:
        payload = json.loads(payload_json)["payload"]
        if payload.get("alert_seq") == alert_seq:
            return True
    return False


def acknowledge_alert(
    *,
    evidence_store: SqliteEvidenceStore,
    approvals_dir: Path,
    alert_seq: int,
    environment_label: str,
    expected_owner_uid: int,
    getuid: Callable[[], int] = os.getuid,
) -> AckOutcome:
    """Acknowledge ``alert_seq`` from ``approvals_dir/alerts/<alert_seq>.yaml``
    (module docstring).

    Steps (each a fail-closed refusal on its own, never partially applied):

    1. Load the file through the file-custody gate + environment-label check
       (:func:`_load_raw_ack_file` / :func:`_verify_environment_label`) and
       parse its ``principal_id`` / ``acknowledged_at_label`` fields.
    2. Refuse unless ``alert_seq`` is a real, already-committed ``STM_ALERT``
       evidence row (:func:`_alert_row_exists`).
    3. Refuse idempotently (never a second evidence row) if ``alert_seq`` was
       already acknowledged (:func:`_already_acknowledged`).
    4. Append one ``STM_ALERT_ACKNOWLEDGED`` evidence row.

    Args:
        evidence_store: The runtime's own evidence store — both the source of
            truth for step 2/3's reads and the destination of step 4's append.
        approvals_dir: The directory ``alerts/<alert_seq>.yaml`` is resolved
            under (the same root :mod:`tos_runtime.authority.iap` uses for
            ``approvals/<proposal_digest>.yaml`` and
            :mod:`tos_runtime.safety.rearm` uses for ``approvals/rearm/...``).
        alert_seq: The ``STM_ALERT`` evidence row's own ``seq`` being
            acknowledged.
        environment_label: This runtime's own boot-argument environment
            label; the file's own ``environment_label`` must match byte-exact.
        expected_owner_uid: See
            :func:`~tos_runtime.custody.file_custody.verify_file_mode_and_owner`.
        getuid: An ``os.getuid``-shaped callable, injectable for tests.

    Returns:
        The :class:`AckOutcome`.
    """
    path = approvals_dir / "alerts" / f"{alert_seq}.yaml"
    try:
        raw = _load_raw_ack_file(
            path, expected_owner_uid=expected_owner_uid, getuid=getuid
        )
        _verify_environment_label(raw, path, environment_label)
        principal_id = _verify_principal_id(raw, path)
        acknowledged_at_label = _verify_acknowledged_at_label(raw, path)
    except AlertAcknowledgementFileError as exc:
        return AckOutcome(acknowledged=False, evidence_seq=None, reason=str(exc))

    if not _alert_row_exists(evidence_store, alert_seq):
        return AckOutcome(
            acknowledged=False,
            evidence_seq=None,
            reason=f"ALERT_SEQ_NOT_FOUND: {alert_seq} is not a real STM_ALERT row",
        )

    if _already_acknowledged(evidence_store, alert_seq):
        return AckOutcome(
            acknowledged=False,
            evidence_seq=None,
            reason=f"ALREADY_ACKNOWLEDGED: {alert_seq} was already acknowledged",
        )

    receipt = evidence_store.append(
        {
            "alert_seq": alert_seq,
            "principal_id": principal_id,
            "acknowledged_at_label": acknowledged_at_label,
        },
        kind=EVIDENCE_KIND_STM_ALERT_ACKNOWLEDGED,
        record_class=EVIDENCE_KIND_STM_ALERT_ACKNOWLEDGED,
    )
    return AckOutcome(
        acknowledged=True, evidence_seq=receipt.seq, reason="ACKNOWLEDGED"
    )
