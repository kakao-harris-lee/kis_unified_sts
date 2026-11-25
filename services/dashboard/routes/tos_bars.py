"""Read-only reader for one recorded session's exported per-bar inspection.

Roadmap ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1, second item. This
is a **read model**, not an authority source, and it is the exact sibling of
:mod:`services.dashboard.routes.tos_projection`: it opens a JSON document
written on the host by ``tools/tos_cp3/export_bars.py``, mirrors its fields into
Pydantic v2 DTOs, never writes anything, and **never imports ``tos`` or
``tos_runtime``** — the file is opened purely as a path, which keeps this
outside the reverse-import firewall (TOS-FW-R) and outside this virtualenv's
dependency set (``tos_runtime`` is not installed here).

The producer could not be called in-process even if the firewall allowed it: the
inspection lives in ``tos/runtime/cp3/``, which this container's image does not
carry, over state directories it does not mount. The exporter's module docstring
records all four walls. The boundary is a file, deliberately.

**Unknown is reported as unknown.** A missing document, an unreadable one,
invalid JSON, a schema or version mismatch, and a session id this route will not
put in a path all return ``200`` with ``available=false`` and a ``reason``
rather than a 4xx/5xx — disguising "no data yet" as a server error would violate
ADR-DEV-014 OBS-INV-003, and the reason prefixes are pinned by
``tests/fixtures/tos/bars-reasons.json``, shared with the UI's matcher.

**No ``reason`` ever carries a value read from the document.** The document's
own content IS mirrored under ``document`` — that is what a read model is for —
but it never reaches a diagnostic, and two kinds of value never reach the body
at all. Three consequences, all deliberate:

* reasons carry the failing *location* and the exception or value *type* only;
* the response's top-level ``session`` is the id THIS ROUTE resolved, which has
  passed :data:`_SESSION_ID_PATTERN`, not the document's own ``session`` string.
  The earlier revision echoed ``document.session``, which is file content: a
  document carrying a hostile name would have had it reflected into a field the
  page renders outside the ``document`` block. (The exporter now also refuses to
  write a document whose ``session`` is outside that same pattern, so the two
  agree by construction — but this route does not depend on that.);
* the document's host paths (``data_dir``, ``strategy.path``, ``bindings.path``)
  are **absent from the DTOs**, so ``extra="ignore"`` drops them before the body
  is built. They are deployment details of the host, the page never renders
  them, and this body reaches a browser that holds the dashboard API key in its
  bundle — the same reasoning that keeps the projection's own path out of its
  response.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tos", tags=["tos"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PROJECTION_PATH = "data/tos_runtime/operator_projection.json"

#: Mirrors ``tools/tos_cp3/export_bars.py``'s own constants. The two sides meet
#: through the file, never through an import (the exporter is legacy-side and
#: this container does not hold ``tools/`` at all), so the names are restated
#: here and the version is checked on every read.
_BARS_SUBDIR = "bars"
_SUPPORTED_SCHEMA_VERSION = 1

#: The one path segment a caller controls, so it is validated against a
#: positive pattern rather than scrubbed: session directory names are
#: ``<label>-YYYYMMDD`` (``stock-r1-20261110``). ``.`` and ``..`` cannot match
#: because a dot is not in the class at all, which rules out traversal by
#: construction instead of by a blocklist.
_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

#: The sentinel that means "whichever session was exported most recently". The
#: panel opens on it, so an operator sees today's session without first knowing
#: its name, and it needs no second listing endpoint.
LATEST = "latest"


def _bars_dir() -> Path:
    """The directory holding the exported documents, INSIDE this container.

    Derived from ``TOS_OPERATOR_PROJECTION_PATH`` — the same env var the
    projection reader uses — so the two read models cannot drift onto different
    mounts. Its host counterpart is ``TOS_OPERATOR_PROJECTION_DIR``; the compose
    file calls them a pair that must be set together.
    """
    raw = os.environ.get("TOS_OPERATOR_PROJECTION_PATH", _DEFAULT_PROJECTION_PATH)
    path = Path(raw)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return path.parent / _BARS_SUBDIR


class BarsCompare(BaseModel):
    """One comparison of one rule, on one bar."""

    model_config = ConfigDict(extra="ignore")

    index: int | None = None
    expression: str | None = None
    left_value: str | None = None
    right_value: str | None = None
    passed: bool | None = None


class BarsRule(BaseModel):
    """One authored rule's evaluation on one bar."""

    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    rule_id: str | None = None
    decision_kind: str | None = None
    fired: bool | None = None
    compares: list[BarsCompare] | None = None


class BarsEvidence(BaseModel):
    """What the engine recorded for one bar, as the exporter rendered it.

    ``value_view`` is the engine's own evaluation inputs and is kept: it is the
    whole point of the panel's ``V`` marker. It carries market values the
    producer already published, not host or credential content.
    """

    model_config = ConfigDict(extra="ignore")

    joined: bool | None = None
    unjoined_reason: str | None = None
    event_id: str | None = None
    snapshot_id: str | None = None
    outcome_type: str | None = None
    outcome_halt_reason: str | None = None
    consumed_halt_reason: str | None = None
    consumed_halt_step: str | None = None
    withheld_reason: str | None = None
    halt_step: str | None = None
    halt_reason: str | None = None
    halt_detail: str | None = None
    value_view: dict[str, bool | int | float | str] | None = None
    value_view_refusal: str | None = None


class BarsViewDiff(BaseModel):
    """One field key the engine's view and the journal disagreed on."""

    model_config = ConfigDict(extra="ignore")

    value_view: str | None = None
    journal: str | None = None


class BarsBar(BaseModel):
    """One recorded bar."""

    model_config = ConfigDict(extra="ignore")

    raw_event_id: str | None = None
    as_of_ms: int | None = None
    time_kst: str | None = None
    time_source: str | None = None
    fields: dict[str, bool | int | float | str] | None = None
    env_values: dict[str, bool | int | float | str] | None = None
    evaluation: str | None = None
    counted: bool | None = None
    flags: str | None = None
    view_diff: dict[str, BarsViewDiff] | None = None
    engine_shape: str | None = None
    decision_disagrees: bool | None = None
    decision_rule_id: str | None = None
    decision_kind: str | None = None
    rules: list[BarsRule] | None = None
    evidence: BarsEvidence | None = None


class BarsSummaryCompare(BaseModel):
    """How often one comparison was the thing that was false."""

    model_config = ConfigDict(extra="ignore")

    index: int | None = None
    expression: str | None = None
    failed_bars: int | None = None
    bars: int | None = None
    failed_pct: float | None = None


class BarsSummaryRule(BaseModel):
    """How often one rule fired, and which comparison blocked it."""

    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    rule_id: str | None = None
    fired_bars: int | None = None
    bars: int | None = None
    fired_pct: float | None = None
    compares: list[BarsSummaryCompare] | None = None


class BarsSummary(BaseModel):
    """The populations and the per-comparison shares."""

    model_config = ConfigDict(extra="ignore")

    bars: int | None = None
    counted_bars: int | None = None
    withheld_bars: int | None = None
    substituted_bars: int | None = None
    view_diff_bars: int | None = None
    view_diff_fields: dict[str, int] | None = None
    disagreement_bars: int | None = None
    not_comparable_bars: int | None = None
    rules: list[BarsSummaryRule] | None = None
    decisions: dict[str, int] | None = None
    evidence_outcomes: dict[str, int] | None = None
    evidence_halts: dict[str, int] | None = None
    unjoined: dict[str, int] | None = None
    value_view_refused: dict[str, int] | None = None


class BarsStrategy(BaseModel):
    """The strategy's identity. ``path`` is deliberately NOT declared."""

    model_config = ConfigDict(extra="ignore")

    sha256: str | None = None


class BarsBindings(BaseModel):
    """The resolved thresholds. ``path`` is deliberately NOT declared."""

    model_config = ConfigDict(extra="ignore")

    values: dict[str, bool | int | float | str] | None = None


class BarsWindow(BaseModel):
    """The KST window the export covered, if it was bounded.

    The document's key is ``from``, a Python keyword, so the field is aliased
    rather than the exported document renamed around a language detail. FastAPI
    serializes a response model by alias, so the body keeps saying ``from``.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    from_: str | None = Field(default=None, alias="from")
    to: str | None = None


class BarsDefault(BaseModel):
    """The policy's mandatory default decision."""

    model_config = ConfigDict(extra="ignore")

    rule_id: str | None = None
    decision_kind: str | None = None


class TosBarsDocument(BaseModel):
    """Mirrors the exporter's document (``tools/tos_cp3/export_bars.py``).

    Every leaf is nullable: the exporter's own producer reports "no source ==
    null" and this DTO must not paper over that with a default that looks like
    a fact. Unknown extra keys are ignored rather than rejected, so an
    exporter-side field addition does not break this reader until the DTO is
    deliberately updated — and the host-path keys are ignored *by design*
    (module docstring).
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int
    session: str | None = None
    instrument: str | None = None
    strategy: BarsStrategy | None = None
    bindings: BarsBindings | None = None
    window: BarsWindow | None = None
    default: BarsDefault | None = None
    bars: list[BarsBar] | None = None
    summary: BarsSummary | None = None


class TosBarsResponse(BaseModel):
    """Response DTO for ``GET /api/tos/sessions/{session_id}/bars``."""

    model_config = ConfigDict(extra="ignore")

    available: bool
    reason: str | None = None
    age_seconds: float | None = None
    session: str | None = None
    document: TosBarsDocument | None = None
    # The document's filesystem path is deliberately NOT a response field, for
    # the same reason the projection's is not: it is a host/container
    # deployment detail the page never renders, and operators get it from the
    # server log line in `_unavailable` instead.


def _unavailable(
    reason: str,
    path: Path,
    age_seconds: float | None = None,
    session: str | None = None,
    level: int = logging.WARNING,
) -> TosBarsResponse:
    """The one unavailable shape, logged at a level that matches the cause.

    ``bars document absent`` is a **normal** state for a session nobody has
    exported yet, so it logs at ``INFO`` (recorded in the call, silent in this
    deployment, where the root logger keeps level ``WARNING``). A real fault —
    unreadable file, invalid JSON, schema or version mismatch — logs at
    ``WARNING``, which reaches the container's stderr.
    """
    logger.log(level, "tos bars document unavailable (%s): %s", reason, path)
    return TosBarsResponse(
        available=False,
        reason=reason,
        age_seconds=age_seconds,
        session=session,
        document=None,
    )


def _resolve_latest(bars_dir: Path) -> str | None:
    """The most recently exported session's name, or ``None`` when there is none.

    Newest by mtime, which is the moment :func:`os.replace` put the document in
    place — so it orders by *export* time rather than by a name this route would
    otherwise have to parse.

    ``stat`` is INSIDE the try, with the listing: an export replacing a document
    between ``iterdir`` and ``stat`` makes the entry vanish, and that
    ``FileNotFoundError`` raised from inside ``max``'s key function would reach
    FastAPI as a 500 — a server error for "the exporter ran while the page was
    loading", which is exactly the "no data yet as a 5xx" this route refuses
    everywhere else. ``None`` here becomes ``available=false`` instead.
    """
    try:
        newest: tuple[float, str] | None = None
        for entry in bars_dir.iterdir():
            if entry.suffix != ".json" or not entry.is_file():
                continue
            stamp = (entry.stat().st_mtime, entry.stem)
            if newest is None or stamp > newest:
                newest = stamp
    except OSError:
        return None
    return None if newest is None else newest[1]


def _read_document(bars_dir: Path, session_id: str) -> TosBarsResponse:
    """Read and validate one session's document, or report why not."""
    if session_id == LATEST:
        resolved = _resolve_latest(bars_dir)
        if resolved is None:
            return _unavailable("bars document absent", bars_dir, level=logging.INFO)
        session_id = resolved
    if not _SESSION_ID_PATTERN.match(session_id):
        # Never echo the rejected id: it is caller-supplied and this body is
        # read by a browser. The length and the rule are enough to fix a typo.
        return _unavailable(
            f"invalid session id (expected {_SESSION_ID_PATTERN.pattern}, "
            f"got {len(session_id)} chars)",
            bars_dir,
        )

    path = bars_dir / f"{session_id}.json"
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
        return _unavailable(
            "bars document absent", path, session=session_id, level=logging.INFO
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        return _unavailable(
            f"invalid json: {type(exc).__name__}", path, age_seconds, session_id
        )
    except OSError as exc:
        # NOT a data-format problem: a 0700 directory or a uid mismatch on the
        # mount. It gets its own reason so the operator looks at permissions
        # rather than at the exporter's output.
        return _unavailable(
            f"cannot read bars document: {type(exc).__name__}",
            path,
            age_seconds,
            session_id,
        )

    if not isinstance(payload, dict):
        return _unavailable(
            "invalid json: top-level value is not an object",
            path,
            age_seconds,
            session_id,
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
            session_id,
        )

    try:
        document = TosBarsDocument.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - report as unknown, never 5xx
        # Exception type only. Pydantic's `str(exc)` embeds `input_value=...`,
        # i.e. the offending slice of a file this body would then echo to a
        # browser; the invalid-JSON branch above makes the same reduction.
        return _unavailable(
            f"schema mismatch: {type(exc).__name__}", path, age_seconds, session_id
        )

    return TosBarsResponse(
        available=True,
        reason=None,
        age_seconds=age_seconds,
        # The RESOLVED id, which passed `_SESSION_ID_PATTERN` above — never
        # `document.session`, which is file content (module docstring).
        session=session_id,
        document=document,
    )


@router.get("/sessions/{session_id}/bars", response_model=TosBarsResponse)
async def get_tos_session_bars(session_id: str, response: Response) -> TosBarsResponse:
    """Return one recorded session's exported per-bar inspection, if any.

    ``session_id`` is a session directory name (``stock-r1-20261110``) or the
    sentinel ``latest``, which resolves to the most recently exported document.

    Read-only: opens the document by path only, never imports
    ``tos``/``tos_runtime``, and never writes. A missing document, an unreadable
    one, a schema/version mismatch, or a rejected id all report
    ``available=false`` with a ``reason`` rather than raising — this route never
    returns a 5xx for those cases.
    """
    response.headers["Cache-Control"] = "no-store"
    return _read_document(_bars_dir(), session_id)
