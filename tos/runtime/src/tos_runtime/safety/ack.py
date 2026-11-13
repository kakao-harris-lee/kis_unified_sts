"""``tos_runtime.safety.ack`` — single-operator STM alert acknowledgement (TOS"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tos_runtime._named_tbd import is_named_tbd_placeholder
from tos_runtime.custody.file_custody import verify_file_mode_and_owner
from tos_runtime.custody.ports import CustodyLoadRefused
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = [
    "AckOutcome",
    "AlertAcknowledgementFileError",
    "acknowledge_alert",
]

_EVIDENCE_KIND_STM_ALERT = "STM_ALERT"

EVIDENCE_KIND_STM_ALERT_ACKNOWLEDGED = "STM_ALERT_ACKNOWLEDGED"


class AlertAcknowledgementFileError(Exception):
    """Raised internally for any refusal reading/validating the on-disk ack file —"""


@dataclass(frozen=True)
class AckOutcome:
    """The outcome of one :func:`acknowledge_alert` call."""

    acknowledged: bool
    evidence_seq: int | None
    reason: str


def _load_raw_ack_file(
    path: Path, *, expected_owner_uid: int, getuid: Callable[[], int]
) -> dict[str, Any]:
    """Custody-gated read + parse of ``approvals/alerts/<alert_seq>.yaml`` — the"""
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
    """Cross-environment isolation — the file's own label must byte-exact match"""
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
    if is_named_tbd_placeholder(principal_id):
        raise AlertAcknowledgementFileError(
            f"{path} 'principal_id' is still the template placeholder 'TBD' — "
            "operator-fill before activation, never a value this loader treats as a "
            "genuine acknowledging identity"
        )
    return principal_id


def _verify_acknowledged_at_label(raw: Mapping[str, Any], path: Path) -> str:
    """An opaque, operator-written string — never parsed as a timestamp, never a"""
    label = raw.get("acknowledged_at_label")
    if not isinstance(label, str) or not label.strip():
        raise AlertAcknowledgementFileError(
            f"{path} 'acknowledged_at_label' is missing or blank"
        )
    return label


def _alert_row_exists(evidence_store: SqliteEvidenceStore, alert_seq: int) -> bool:
    """Whether ``alert_seq`` names a real, already-committed ``STM_ALERT`` evidence"""
    row = evidence_store.connection.execute(
        "SELECT 1 FROM entries WHERE seq = ? AND kind = ?",
        (alert_seq, _EVIDENCE_KIND_STM_ALERT),
    ).fetchone()
    return row is not None


def _already_acknowledged(evidence_store: SqliteEvidenceStore, alert_seq: int) -> bool:
    """Whether a prior ``STM_ALERT_ACKNOWLEDGED`` row already names ``alert_seq`` —"""
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
    """Acknowledge ``alert_seq`` from ``approvals_dir/alerts/<alert_seq>.yaml``"""
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
