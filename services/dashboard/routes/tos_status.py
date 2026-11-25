"""Read-only reader for the exported one-page status board.

Plan ``docs/plans/2026-11-25-tos-operator-page-legibility-plan.md`` §4 ① «상태 띠»:
the strip at the top of ``/tos`` that answers "is this all right now?" — which
tenants ran, how many issues are open and at what level, how many clean trading
days have accumulated against the target, and whether the resident paper session
is alive.

This is a **read model**, not an authority source, and it is the exact sibling of
:mod:`services.dashboard.routes.tos_symbols`: it opens a JSON document written on
the host by ``tools/tos_cp3/export_status.py``, mirrors its fields into Pydantic
v2 DTOs, never writes anything, and **never imports ``tos`` or ``tos_runtime``**
— the file is opened purely as a path, which keeps this outside the reverse
import firewall (TOS-FW-R) and outside this virtualenv's dependency set.

The producer could not be called in-process even if the firewall allowed it, for
the four walls ``export_bars`` already records: this image does not carry
``tools/`` (``Dockerfile.dashboard`` copies ``shared/``, ``services/`` and
``cli/`` only), it does not mount the 0700 state directories the board reads, it
cannot import the kernel, and ``tos_runtime`` is not installed here. The boundary
is a file, deliberately.

**This route judges nothing.** Every level, issue sentence and count is the one
``sts tos status`` already produced on the host; re-deriving any of them here
would let the page and the CLI disagree about the same day.

**Unknown is reported as unknown.** A missing document, an unreadable one,
invalid JSON, and a schema or version mismatch all return ``200`` with
``available=false`` and a ``reason`` rather than a 4xx/5xx — disguising "no data
yet" as a server error would violate ADR-DEV-014 OBS-INV-003. The reason prefixes
are pinned by ``tests/fixtures/tos/status-reasons.json``, shared with the UI's
matcher.

**No ``reason`` ever carries a value read from the document.** Like
``tos_symbols`` and unlike ``tos_bars`` there is no caller-supplied path segment
at all — the document's name is fixed, so this route has no id to validate and
no traversal surface to close.

**What actually keeps host paths out of this body** — the page is open to the
internet behind Cloudflare Access, so this is the part to get right, and it is
*two* mechanisms, not a promise:

1. The DTOs declare no path-bearing key, so ``extra="ignore"`` drops
   ``state_dir``, the clean-streak calendar path, the release digests and the
   boot proof's revision line even if a document carries them.
2. That is **not enough on its own**, because several declared fields are free
   text: issue sentences, ``aborts``, the streak's ``error``. Runner ``die``
   messages interpolate absolute paths (``$TENANT_CUSTODY_ROOT``,
   ``$TENANT_LOG``) and leaf/calendar errors are ``f"{type}: {exc}"``. That is
   exactly how #1179's review found an ``ABORT: … /home/deploy/…`` line reaching
   this route. So every string leaf of the payload is run through
   :func:`services.dashboard.routes._redact.redact_payload` **before**
   validation, and the response says ``redacted=true`` when it had to change
   anything. The exporter redacts too; this tier does not take that on trust.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict

from services.dashboard.routes._redact import redact_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tos", tags=["tos"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PROJECTION_PATH = "data/tos_runtime/operator_projection.json"

#: Mirrors ``tools/tos_cp3/export_status.py``'s own constants. The two sides meet
#: through the file, never through an import (the exporter is host-side and this
#: container does not hold ``tools/`` at all), so the names are restated here and
#: the version is checked on every read.
_STATUS_SUBDIR = "status"
_DOCUMENT_NAME = "board.json"
_SUPPORTED_SCHEMA_VERSION = 1


def _document_path() -> Path:
    """The document's path INSIDE this container.

    Derived from ``TOS_OPERATOR_PROJECTION_PATH`` — the same env var the
    projection, bars and symbols readers use — so the four read models cannot
    drift onto different mounts. Its host counterpart is
    ``TOS_OPERATOR_PROJECTION_DIR``; the compose file calls them a pair that
    must be set together.
    """
    raw = os.environ.get("TOS_OPERATOR_PROJECTION_PATH", _DEFAULT_PROJECTION_PATH)
    path = Path(raw)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return path.parent / _STATUS_SUBDIR / _DOCUMENT_NAME


class StatusIssue(BaseModel):
    """One thing the board wants an operator to look at.

    ``level`` is the board's own word — the document's ``levels`` block names
    both of them, so the page can label and sort without a literal of its own.
    """

    model_config = ConfigDict(extra="ignore")

    level: str | None = None
    #: Which session (or ``paper``, or ``streak/<label>``) raised it.
    where: str | None = None
    text: str | None = None


class StatusTenantIssue(BaseModel):
    """One issue raised by a single tenant session (no ``where`` — it is the row)."""

    model_config = ConfigDict(extra="ignore")

    level: str | None = None
    text: str | None = None


class StatusTenant(BaseModel):
    """One CP-3 tenant session on the board's day."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    label: str | None = None
    tree_id: str | None = None
    market: str | None = None
    direction: str | None = None
    instrument: str | None = None
    #: ``PRE-BOOT``/``RUNNING``/``ENDED``/``FAILED``/``ABORT``/``LOST``…
    status: str | None = None
    #: Only meaningful for today: the exporter does not look at ``/proc`` for a
    #: past date, and both flags are then ``False`` rather than "unknown".
    run_alive: bool | None = None
    producer_alive: bool | None = None
    boot_at: str | None = None
    end_at: str | None = None
    run_rc: int | None = None
    producer_rc: int | None = None
    ticks: int | None = None
    issues: list[StatusTenantIssue] | None = None


class StatusStreak(BaseModel):
    """One tree's clean-trading-day count against ``TOS_PAPER_READY``'s target.

    Cumulative, not consecutive (relaxation 2026-11-11): a broken day costs that
    day only and never erases what came before, which is why ``broke_on`` and
    ``broke_reason`` stay beside the count instead of resetting it.
    """

    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    days: int | None = None
    target_days: int | None = None
    window_days: int | None = None
    met: bool | None = None
    start: str | None = None
    window_start: str | None = None
    #: Why today cannot be judged yet (a running session), not a failure.
    pending: str | None = None
    broke_on: str | None = None
    broke_reason: str | None = None
    calendar_version: str | None = None
    #: Set when the count could not be taken at all — the page must then show
    #: "unknown", never a zero.
    error: str | None = None


class StatusPaperReport(BaseModel):
    """How the resident paper session ended. The worktree commit is NOT a field."""

    model_config = ConfigDict(extra="ignore")

    verdict: str | None = None
    exit_code: int | None = None
    stop_reason: str | None = None
    started_kst: str | None = None
    ended_kst: str | None = None
    events_consumed: int | None = None
    stale_withheld: int | None = None
    stale_ratio: float | None = None


class StatusPaper(BaseModel):
    """The resident paper session's liveness and outcome."""

    model_config = ConfigDict(extra="ignore")

    session: str | None = None
    #: False for a past date: the exporter did not look at ``/proc``, so the two
    #: ``*_alive`` flags below say nothing and the page must not draw them.
    live_check: bool | None = None
    runtime_alive: bool | None = None
    driver_alive: bool | None = None
    #: The boot proof's verdict alone. ``None`` is "no boot-proof line", which
    #: is not the same as ``False`` ("there was one and it was not OK").
    boot_ok: bool | None = None
    report: StatusPaperReport | None = None
    issues: list[StatusTenantIssue] | None = None


class StatusLevels(BaseModel):
    """The two level words the board uses, so the page needs no literal."""

    model_config = ConfigDict(extra="ignore")

    blocked: str | None = None
    check: str | None = None


class TosStatusDocument(BaseModel):
    """Mirrors the exporter's document (``tools/tos_cp3/export_status.py``).

    Every leaf is nullable: the board's own sources report "no source == null"
    and this DTO must not paper over that with a default that looks like a fact.
    Unknown extra keys are ignored rather than rejected, so an exporter-side
    field addition does not break this reader until the DTO is deliberately
    updated — and the exporter's stripped keys (host paths, digests, the repo
    commit) are not declared here *by design* (module docstring).
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int
    #: The KST day this board judges. The page compares it against its own
    #: today, so an export that stopped running yesterday is visible as such.
    date: str | None = None
    generated_kst: str | None = None
    tenants: list[StatusTenant] | None = None
    clean_streak: list[StatusStreak] | None = None
    paper: StatusPaper | None = None
    issues: list[StatusIssue] | None = None
    #: Counted by the exporter from the same list, so the strip and the list can
    #: never disagree about how many blocks there are.
    blocked: int | None = None
    checks: int | None = None
    levels: StatusLevels | None = None


class TosStatusResponse(BaseModel):
    """Response DTO for ``GET /api/tos/status``."""

    model_config = ConfigDict(extra="ignore")

    available: bool
    reason: str | None = None
    age_seconds: float | None = None
    #: True when this tier had to strip a path or account-shaped value from the
    #: document. It means the EXPORTER regressed, so the page should say the
    #: document was altered rather than present a scrubbed broken export as
    #: normal. The body is safe either way.
    redacted: bool = False
    document: TosStatusDocument | None = None
    # The document's filesystem path is deliberately NOT a response field, for
    # the same reason the other three read models' are not: it is a
    # host/container deployment detail the page never renders, and operators get
    # it from the server log line in `_unavailable` instead.


def _unavailable(
    reason: str,
    path: Path,
    age_seconds: float | None = None,
    level: int = logging.WARNING,
) -> TosStatusResponse:
    """The one unavailable shape, logged at a level that matches the cause.

    ``status document absent`` is a **normal** state before the first export, so
    it logs at ``INFO``. A real fault — unreadable file, invalid JSON, schema or
    version mismatch — logs at ``WARNING``, which reaches the container's stderr.
    """
    logger.log(level, "tos status document unavailable (%s): %s", reason, path)
    return TosStatusResponse(
        available=False,
        reason=reason,
        age_seconds=age_seconds,
        document=None,
    )


def _read_document(path: Path) -> TosStatusResponse:
    """Read and validate the document, or report why not."""
    age_seconds: float | None = None
    try:
        # The exporter atomically replaces the file; read age and content from
        # the same open inode so a concurrent export cannot mix generations.
        with path.open(encoding="utf-8") as stream:
            mtime = os.fstat(stream.fileno()).st_mtime
            delta = time.time() - mtime
            age_seconds = delta if delta >= 0 else None
            payload = json.load(stream)
    except FileNotFoundError:
        return _unavailable("status document absent", path, level=logging.INFO)
    except (UnicodeError, json.JSONDecodeError) as exc:
        return _unavailable(f"invalid json: {type(exc).__name__}", path, age_seconds)
    except OSError as exc:
        # NOT a data-format problem: a 0700 directory or a uid mismatch on the
        # mount. It gets its own reason so the operator looks at permissions
        # rather than at the exporter's output.
        return _unavailable(
            f"cannot read status document: {type(exc).__name__}", path, age_seconds
        )

    if not isinstance(payload, dict):
        return _unavailable(
            "invalid json: top-level value is not an object", path, age_seconds
        )

    schema_version = payload.get("schema_version")
    # `type(...) is int` excludes `bool`: `True == 1`, so a JSON `true` would
    # otherwise pass this gate and render as a valid v1 document.
    if type(schema_version) is not int or schema_version != _SUPPORTED_SCHEMA_VERSION:
        # The type, never the value — `schema_version` is read from the file.
        return _unavailable(
            f"unsupported schema_version (expected {_SUPPORTED_SCHEMA_VERSION}, "
            f"got {type(schema_version).__name__})",
            path,
            age_seconds,
        )

    # Redact BEFORE validating, so nothing a hostile or regressed document
    # carries can reach the body — not even through a field this DTO ignores
    # but a future one declares. The exporter redacts too; this tier does not
    # take that on trust (module docstring of `_redact`).
    payload, redacted = redact_payload(payload)
    if redacted:
        logger.warning(
            "tos status document carried a path or account-shaped value and was "
            "redacted by the reader; the exporter should have done this: %s",
            path,
        )

    try:
        document = TosStatusDocument.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - report as unknown, never 5xx
        # Exception type only. Pydantic's `str(exc)` embeds `input_value=...`,
        # i.e. the offending slice of a file this body would then echo to a
        # browser; the invalid-JSON branch above makes the same reduction.
        return _unavailable(f"schema mismatch: {type(exc).__name__}", path, age_seconds)

    return TosStatusResponse(
        available=True,
        reason=None,
        age_seconds=age_seconds,
        redacted=redacted,
        document=document,
    )


@router.get("/status", response_model=TosStatusResponse)
async def get_tos_status(response: Response) -> TosStatusResponse:
    """Return the exported one-page status board, if any.

    Read-only: opens the document by path only, never imports
    ``tos``/``tos_runtime``, never calls a broker, and never writes. A missing
    document, an unreadable one, or a schema/version mismatch all report
    ``available=false`` with a ``reason`` rather than raising — this route never
    returns a 5xx for those cases.
    """
    response.headers["Cache-Control"] = "no-store"
    return _read_document(_document_path())
