"""Read-only reader for the tos_runtime operator projection file.

This endpoint is a **read model**, not an authority source (TOS Phase 5 exit
condition 3, decision 9 of
``docs/plans/2026-09-12-tos-phase5-w4-operations-plan.md`` §2). It reads a
JSON file exported by ``tos_runtime`` at the end of every driver turn and
mirrors its fields verbatim into a Pydantic v2 DTO. It never writes anything,
and it never imports ``tos`` or ``tos_runtime`` — the file is opened purely
as a path (``Path.read_text`` / ``json.loads``), which keeps it outside the
reverse-import firewall (TOS-FW-R, ``tools/tos_firewall_check.py`` rule
(e)/(g)) and outside the legacy virtualenv's dependency set (``tos_runtime``
is not installed there).

Unknown is reported as unknown: a missing file, invalid JSON, or a schema
mismatch all return ``200`` with ``available=false`` and a ``reason`` string
rather than a 5xx — disguising "no data yet" as a server error would violate
ADR-DEV-014 OBS-INV-003.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api/tos", tags=["tos"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PROJECTION_PATH = "data/tos_runtime/operator_projection.json"
_SUPPORTED_SCHEMA_VERSION = 1


def _projection_path() -> Path:
    import os

    raw = os.environ.get("TOS_OPERATOR_PROJECTION_PATH", _DEFAULT_PROJECTION_PATH)
    path = Path(raw)
    return path if path.is_absolute() else _REPO_ROOT / path


class ServiceClearance(BaseModel):
    """Per-service safety-mesh clearance (spg/wdr/sir/stm)."""

    model_config = ConfigDict(extra="ignore")

    clear: bool | None = None
    reasons: list[str] = []


class _RuntimeIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cell_id: str | None = None
    runtime_generation: int | None = None
    process_nonce: str | None = None
    code_digest: str | None = None


class _RecoveryFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    readiness_verdict: str | None = None
    reasons: list[str] = []


class _DriverFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    wired: bool | None = None
    halt_latched: bool | None = None
    halt_reason: str | None = None


class _TimeFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    health: str | None = None


class _SafetyMeshFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    snapshot_generation: int | None = None
    services: dict[str, ServiceClearance] = {}


class _CurrentnessFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pending_dimensions: list[str] = []
    last_assemble_complete: bool | None = None


class _RclFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    last_seq: int | None = None
    open_reservations: int | None = None


class _InboxFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    unconsumed_count: int | None = None


class _EvidenceFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tip_seq_excluding_stm_alert: int | None = None
    chain_digest: str | None = None
    key_generation: int | None = None


class _ReleaseFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    admitted: bool | None = None
    software_deployment_ok: bool | None = None


class _ProtectiveFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    last_verdict: str | None = None


class _LastBackupFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generation: int | None = None
    age_monotonic_ns: int | None = None
    manifest_digest: str | None = None


class _OperationsFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_versions: dict[str, int] = {}
    last_backup: _LastBackupFacts = _LastBackupFacts()
    key_continuity: str | None = None
    dependency_admission: bool | None = None


class _AlertsFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    unresolved_stm_alert_seqs: list[int] = []
    delivery_owner: str | None = None


class _ExportFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    failures: int | None = None
    last_error: str | None = None


class TosOperatorProjection(BaseModel):
    """Mirrors the tos_runtime operator projection JSON schema (plan §2.7).

    Every leaf the runtime may not have a source for is ``X | None`` — the
    runtime's own convention is "no source == null" (OBS-INV-003), and this
    DTO must not paper over that with a default value that looks like a
    fact. Unknown extra keys from a newer runtime schema are ignored rather
    than rejected, so a runtime-side field addition does not break the
    reader until this DTO is deliberately updated to match.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int
    projection_generation: int
    exported_at_monotonic_ns: int
    non_authorizing: bool
    runtime: _RuntimeIdentity = _RuntimeIdentity()
    recovery: _RecoveryFacts = _RecoveryFacts()
    driver: _DriverFacts = _DriverFacts()
    time: _TimeFacts = _TimeFacts()
    safety_mesh: _SafetyMeshFacts = _SafetyMeshFacts()
    currentness: _CurrentnessFacts = _CurrentnessFacts()
    rcl: _RclFacts = _RclFacts()
    inbox: _InboxFacts = _InboxFacts()
    evidence: _EvidenceFacts = _EvidenceFacts()
    release: _ReleaseFacts = _ReleaseFacts()
    protective: _ProtectiveFacts = _ProtectiveFacts()
    operations: _OperationsFacts = _OperationsFacts()
    alerts: _AlertsFacts = _AlertsFacts()
    export: _ExportFacts = _ExportFacts()


class TosProjectionResponse(BaseModel):
    """Response DTO for ``GET /api/tos/projection``."""

    model_config = ConfigDict(extra="ignore")

    available: bool
    reason: str | None = None
    path: str
    age_seconds: float | None = None
    projection: TosOperatorProjection | None = None


def _read_projection(path: Path) -> TosProjectionResponse:
    path_str = str(path)

    if not path.exists():
        return TosProjectionResponse(
            available=False,
            reason="projection file absent",
            path=path_str,
            age_seconds=None,
            projection=None,
        )

    try:
        mtime = path.stat().st_mtime
        age_seconds = max(0.0, time.time() - mtime)
    except OSError as exc:  # pragma: no cover - defensive, race with unlink
        return TosProjectionResponse(
            available=False,
            reason=f"invalid json: {type(exc).__name__}: {exc}",
            path=path_str,
            age_seconds=None,
            projection=None,
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as exc:
        return TosProjectionResponse(
            available=False,
            reason=f"invalid json: {type(exc).__name__}: {exc}",
            path=path_str,
            age_seconds=age_seconds,
            projection=None,
        )

    if not isinstance(payload, dict):
        return TosProjectionResponse(
            available=False,
            reason="invalid json: top-level value is not an object",
            path=path_str,
            age_seconds=age_seconds,
            projection=None,
        )

    schema_version = payload.get("schema_version")
    if schema_version != _SUPPORTED_SCHEMA_VERSION:
        return TosProjectionResponse(
            available=False,
            reason=f"unsupported schema_version {schema_version!r}",
            path=path_str,
            age_seconds=age_seconds,
            projection=None,
        )

    try:
        projection = TosOperatorProjection.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - report as unknown, never 5xx
        first_error = ""
        errors = getattr(exc, "errors", None)
        if callable(errors):
            try:
                error_list = errors()
                if error_list:
                    loc = ".".join(str(part) for part in error_list[0].get("loc", ()))
                    first_error = f" at {loc}" if loc else ""
            except Exception:  # noqa: BLE001 - best-effort message only
                first_error = ""
        return TosProjectionResponse(
            available=False,
            reason=f"schema mismatch{first_error}: {type(exc).__name__}: {exc}",
            path=path_str,
            age_seconds=age_seconds,
            projection=None,
        )

    return TosProjectionResponse(
        available=True,
        reason=None,
        path=path_str,
        age_seconds=age_seconds,
        projection=projection,
    )


@router.get("/projection", response_model=TosProjectionResponse)
async def get_tos_projection() -> TosProjectionResponse:
    """Return the last exported tos_runtime operator projection, if any.

    Read-only: opens the projection file by path only, never imports
    ``tos``/``tos_runtime``, and never writes. A missing file, unreadable
    file, or a schema/version mismatch all report ``available=false`` with a
    ``reason`` rather than raising — this route never returns a 5xx for those
    cases.
    """
    return _read_projection(_projection_path())
