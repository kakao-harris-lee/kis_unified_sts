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

Unknown is reported as unknown. Four causes — a missing file, a file that
cannot be read at all (permissions, a directory in its place), invalid JSON,
and a schema or version mismatch — all return ``200`` with
``available=false`` and a ``reason`` string rather than a 5xx; disguising
"no data yet" as a server error would violate ADR-DEV-014 OBS-INV-003.

No ``reason`` ever carries a value read from the projection file. The file is
operator-supplied content and this body is polled by a browser, so reasons
carry the failing *location* and the exception or value *type* only. The
reason prefixes are pinned by ``tests/fixtures/tos/projection-reasons.json``,
shared with the UI's matcher.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from types import UnionType
from typing import Union, get_args, get_origin

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tos", tags=["tos"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PROJECTION_PATH = "data/tos_runtime/operator_projection.json"
_SUPPORTED_SCHEMA_VERSION = 1


def _projection_path() -> Path:
    raw = os.environ.get("TOS_OPERATOR_PROJECTION_PATH", _DEFAULT_PROJECTION_PATH)
    path = Path(raw)
    return path if path.is_absolute() else _REPO_ROOT / path


class ServiceClearance(BaseModel):
    """Per-service safety-mesh clearance (spg/wdr/sir/stm)."""

    model_config = ConfigDict(extra="ignore")

    clear: bool | None = None
    #: ``None`` means "the runtime had no source for this list", which is NOT the
    #: same fact as an empty list ("evaluated, nothing to report"). The producer
    #: passes its reader's value through verbatim, so both shapes reach here.
    reasons: list[str] | None = None


class _RuntimeIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cell_id: str | None = None
    runtime_generation: int | None = None
    process_nonce: str | None = None
    code_digest: str | None = None


class _RecoveryFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    readiness_verdict: str | None = None
    #: ``None`` == no source (see :class:`ServiceClearance.reasons`).
    reasons: list[str] | None = None


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
    services: dict[str, ServiceClearance] | None = None


class _CurrentnessFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pending_dimensions: list[str] | None = None
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


class _ProtectiveVerdict(BaseModel):
    """One ``ProtectiveActionService`` verdict as the producer renders it.

    Pinned by the producer at ``tos/runtime/src/tos_runtime/compose/
    _operations_wiring.py::_read_protective`` and by its own test
    ``tos/runtime/tests/compose/test_operations_wiring.py`` (the key set is
    asserted there).

    Every leaf is declared nullable, but for two different reasons. Four of
    them (``derestriction_admissible``, ``capacity_exhausted``,
    ``classification``, ``protective_classification_digest``) really are
    ``None`` whenever the runtime has no source for that fact. The other two
    (``unevaluated``, ``reasons``) are always lists today —
    ``ProtectiveVerdict`` declares them ``tuple[str, ...]`` and the producer
    renders them with ``list(...)``, so ``None`` there is tolerated for
    forward compatibility rather than expected.
    """

    model_config = ConfigDict(extra="ignore")

    derestriction_admissible: bool | None = None
    capacity_exhausted: bool | None = None
    #: ``ProtectiveActionOutcome.value`` (a plain string) or ``None``.
    classification: str | None = None
    unevaluated: list[str] | None = None
    reasons: list[str] | None = None
    protective_classification_digest: str | None = None


class _ProtectiveFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    last_verdict: _ProtectiveVerdict | None = None


class _LastBackupFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generation: int | None = None
    age_monotonic_ns: int | None = None
    manifest_digest: str | None = None


class _OperationsFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # ``OperationsFacts.schema_versions`` (compose/_types.py) declares
    # ``dict[str, int | None]`` — a store with no readable ``PRAGMA
    # user_version`` yet reports ``None`` for its own key.
    schema_versions: dict[str, int | None] | None = None
    last_backup: _LastBackupFacts | None = None
    key_continuity: str | None = None
    dependency_admission: bool | None = None


class _AlertsFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    unresolved_stm_alert_seqs: list[int] | None = None
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
    runtime: _RuntimeIdentity | None = None
    recovery: _RecoveryFacts | None = None
    driver: _DriverFacts | None = None
    time: _TimeFacts | None = None
    safety_mesh: _SafetyMeshFacts | None = None
    currentness: _CurrentnessFacts | None = None
    rcl: _RclFacts | None = None
    inbox: _InboxFacts | None = None
    evidence: _EvidenceFacts | None = None
    release: _ReleaseFacts | None = None
    protective: _ProtectiveFacts | None = None
    operations: _OperationsFacts | None = None
    alerts: _AlertsFacts | None = None
    export: _ExportFacts | None = None


class TosProjectionResponse(BaseModel):
    """Response DTO for ``GET /api/tos/projection``."""

    model_config = ConfigDict(extra="ignore")

    available: bool
    reason: str | None = None
    age_seconds: float | None = None
    projection: TosOperatorProjection | None = None
    # The projection's filesystem path is deliberately NOT a response field.
    # It is a deployment detail of the host/container, the page never renders
    # it, and this body is polled every 15 s by a browser that holds the
    # dashboard API key in its bundle. Operators get the path from the server
    # log line in ``_unavailable`` instead.


def _field_target(annotation: object) -> object:
    """What a DTO field's annotation points at, for walking an error location.

    Returns a ``BaseModel`` subclass, or ``("dict", target)`` / ``("list",
    target)`` for a container whose entries are addressed by a key or index,
    or ``None`` when the annotation is a plain scalar.
    """
    args = [arg for arg in get_args(annotation) if arg is not type(None)]
    if get_origin(annotation) in (Union, UnionType) and len(args) == 1:
        annotation = args[0]
    origin = get_origin(annotation)
    if origin is dict:
        return ("dict", _field_target(get_args(annotation)[1]))
    if origin in (list, tuple):
        return ("list", _field_target(get_args(annotation)[0]))
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _safe_error_location(loc: tuple[object, ...]) -> str:
    """Render a pydantic error location without any file-derived text.

    A location is not automatically safe: inside a mapping field such as
    ``operations.schema_versions`` the offending segment is a key *from the
    projection file*, and echoing it would put file content back into the
    response the same way ``str(exc)`` did. Every segment is therefore
    resolved against the DTO: a real field name is kept, a mapping key
    becomes ``<key>``, and a list position keeps its integer index (an index
    is generated by pydantic, not read from the file).
    """
    node: object = TosOperatorProjection
    parts: list[str] = []
    for raw in loc:
        if isinstance(node, type) and issubclass(node, BaseModel):
            name = str(raw)
            field = node.model_fields.get(name)
            if field is not None:
                parts.append(name)
                node = _field_target(field.annotation)
                continue
            parts.append("<key>")
            node = None
            continue
        if isinstance(node, tuple):
            kind, target = node
            parts.append(
                str(raw) if kind == "list" and isinstance(raw, int) else "<key>"
            )
            node = target
            continue
        parts.append("<key>")
        node = None
    return ".".join(parts)


def _unavailable(
    reason: str,
    path: Path,
    age_seconds: float | None = None,
    level: int = logging.WARNING,
) -> TosProjectionResponse:
    """Report "no usable projection" as a 200 with a reason, never a 5xx.

    The filesystem path stays on the server: it is logged here and never put
    in the response body. ``reason`` is built by the callers from locations
    and type names only, so no projection file content reaches this line
    either.

    Levels, measured rather than assumed. Nothing in this app calls
    ``basicConfig``/``dictConfig``, and uvicorn's ``LOGGING_CONFIG`` declares
    only the ``uvicorn``, ``uvicorn.error`` and ``uvicorn.access`` loggers —
    so after startup the root logger still has no handler and keeps level
    ``WARNING``. A ``WARNING`` from this module therefore reaches the
    container's stderr through ``logging.lastResort`` (a stderr handler at
    ``WARNING``), and an ``INFO`` produces no output at all.

    That is exactly the split this route wants, so the level is per cause:

    * ``projection file absent`` is a **normal** state outside a paper
      session, and this body is polled every 15 s while a tab is open (about
      240 lines an hour). It logs at ``INFO`` — recorded in the call, silent
      in this deployment.
    * a real fault (unreadable file, invalid JSON, schema or version
      mismatch) logs at ``WARNING``, which is visible.
    """
    logger.log(level, "tos operator projection unavailable (%s): %s", reason, path)
    return TosProjectionResponse(
        available=False,
        reason=reason,
        age_seconds=age_seconds,
        projection=None,
    )


def _read_projection(path: Path) -> TosProjectionResponse:
    age_seconds = None
    try:
        # The exporter atomically replaces the file. Read age and content from
        # the same open inode so a concurrent export cannot mix generations.
        with path.open(encoding="utf-8") as stream:
            mtime = os.fstat(stream.fileno()).st_mtime
            delta = time.time() - mtime
            age_seconds = delta if delta >= 0 else None
            payload = json.load(stream)
    except FileNotFoundError:
        # Normal outside a session — INFO, not WARNING. See `_unavailable`.
        return _unavailable("projection file absent", path, level=logging.INFO)
    except (UnicodeError, json.JSONDecodeError) as exc:
        return _unavailable(f"invalid json: {type(exc).__name__}", path, age_seconds)
    except OSError as exc:
        # NOT a data-format problem: a 0700 directory, a uid mismatch, or a
        # directory where a file was expected. The runbook names this as the
        # first installation hazard, so it gets its own reason — folding it
        # into "invalid json" would send the operator to look at the exporter's
        # output instead of at the mount's permissions.
        return _unavailable(
            f"cannot read projection: {type(exc).__name__}", path, age_seconds
        )

    if not isinstance(payload, dict):
        return _unavailable(
            "invalid json: top-level value is not an object", path, age_seconds
        )

    schema_version = payload.get("schema_version")
    # `type(...) is int` excludes `bool`: `True != 1` is False, so a JSON
    # `true` passed this gate and pydantic coerced it to 1 — the document
    # rendered as a valid v1 projection (measured). `bool` is an `int`
    # subclass, so `isinstance` would not exclude it.
    if type(schema_version) is not int or schema_version != _SUPPORTED_SCHEMA_VERSION:
        # The type, never the value: `schema_version` is read from the file,
        # so `{schema_version!r}` would echo arbitrary file content (a long
        # string, a nested object) into a body the browser polls. An operator
        # needs to know the document is not v1, not what byte it carried.
        return _unavailable(
            f"unsupported schema_version (expected {_SUPPORTED_SCHEMA_VERSION}, "
            f"got {type(schema_version).__name__})",
            path,
            age_seconds,
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
                    loc = _safe_error_location(tuple(error_list[0].get("loc", ())))
                    first_error = f" at {loc}" if loc else ""
            except Exception:  # noqa: BLE001 - best-effort message only
                first_error = ""
        # DTO-resolved location and exception type only. Pydantic's
        # ``str(exc)`` embeds ``input_value=...`` — the offending slice of the
        # projection file — and the raw location embeds mapping keys read from
        # that same file. This body is polled by the browser, so both are
        # reduced; the invalid-JSON branch above makes the same reduction.
        return _unavailable(
            f"schema mismatch{first_error}: {type(exc).__name__}", path, age_seconds
        )

    return TosProjectionResponse(
        available=True,
        reason=None,
        age_seconds=age_seconds,
        projection=projection,
    )


@router.get("/projection", response_model=TosProjectionResponse)
async def get_tos_projection(response: Response) -> TosProjectionResponse:
    """Return the last exported tos_runtime operator projection, if any.

    Read-only: opens the projection file by path only, never imports
    ``tos``/``tos_runtime``, and never writes. A missing file, unreadable
    file, or a schema/version mismatch all report ``available=false`` with a
    ``reason`` rather than raising — this route never returns a 5xx for those
    cases.
    """
    response.headers["Cache-Control"] = "no-store"
    return _read_projection(_projection_path())
