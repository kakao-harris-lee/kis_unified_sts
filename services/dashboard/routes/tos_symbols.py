"""Read-only reader for the per-tenant operator row document.

Plan ``docs/plans/2026-11-19-tos-usage-plan.md`` §5 «종목별 운영 화면», widened by
``docs/plans/2026-11-25-tos-operator-page-legibility-plan.md`` §6 P2: one row per
CP-3 tenant on the ``/tos`` page — today's buys, today's sells, the holding TOS
itself knows about, the realized PnL, and the last thing that blocked a bar.

**Five rows, two shapes.** The three stock tenants trade (KIS mock) and carry
fills, a holding and a ``pnl``. The two futures tenants are ``decision_only``:
their entries stop at an independent approval step (operator decision
2026-11-05), so their fill/holding fields are ``None`` — never ``0`` — and they
carry no ``pnl`` at all. A page that drew those as zeros would be claiming the
tenant traded nothing today rather than that it cannot trade here.

This is a **read model**, not an authority source, and it is the exact sibling of
:mod:`services.dashboard.routes.tos_bars`: it opens a JSON document written on
the host by ``tools/tos_cp3/export_symbols.py``, mirrors its fields into Pydantic
v2 DTOs, never writes anything, and **never imports ``tos`` or ``tos_runtime``**
— the file is opened purely as a path, which keeps this outside the reverse
import firewall (TOS-FW-R) and outside this virtualenv's dependency set.

The producer could not be called in-process even if the firewall allowed it, for
the four walls ``export_bars`` already records: this image does not carry
``tools/`` (``Dockerfile.dashboard`` copies ``shared/``, ``services/`` and
``cli/`` only), it does not mount the 0700 tenant state directories the leaves
live in, it cannot import the kernel, and ``tos_runtime`` is not installed here.
The boundary is a file, deliberately.

**No broker call ever happens in this tier.** The holding this route serves is
``holding_basis = TOS_LEDGER_FIFO_OPEN_LOTS`` — what TOS's own evidence says is
still open, computed on the host by ``sts tos perf``'s FIFO. It is not a KIS
balance read, the page labels it «TOS 기준», and nothing here calls KIS.

**Unknown is reported as unknown.** A missing document, an unreadable one,
invalid JSON, and a schema or version mismatch all return ``200`` with
``available=false`` and a ``reason`` rather than a 4xx/5xx — disguising "no data
yet" as a server error would violate ADR-DEV-014 OBS-INV-003. The reason prefixes
are pinned by ``tests/fixtures/tos/symbols-reasons.json``, shared with the UI's
matcher.

**No ``reason`` ever carries a value read from the document.** Unlike
``tos_bars`` there is no caller-supplied path segment at all — the document's
name is fixed, so this route has no id to validate and no traversal surface to
close.

**What keeps host paths and account numbers out of this body**, on a page open
to the internet behind Cloudflare Access — two mechanisms, not a promise:

1. The exporter emits no path key and reduces a leaf-read failure to the
   exception's type name (``export_symbols._reduce_error``).
2. That alone would not be enough: the unresolved-attempt ``reason`` and
   ``observation`` are sentences the RUNTIME wrote, relayed by
   ``perf._attempt_cause``/``_attempt_observation``, and free text is exactly
   how #1179's review found host paths reaching the sibling status route. So
   every string leaf is run through
   :func:`services.dashboard.routes._redact.redact_payload` before validation,
   and the response reports ``redacted=true`` when it had to change anything.
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

#: Mirrors ``tools/tos_cp3/export_symbols.py``'s own constants. The two sides
#: meet through the file, never through an import (the exporter is host-side and
#: this container does not hold ``tools/`` at all), so the names are restated
#: here and the version is checked on every read.
_SYMBOLS_SUBDIR = "symbols"
_DOCUMENT_NAME = "today.json"
_SUPPORTED_SCHEMA_VERSION = 1


def _document_path() -> Path:
    """The document's path INSIDE this container.

    Derived from ``TOS_OPERATOR_PROJECTION_PATH`` — the same env var the
    projection and bars readers use — so the three read models cannot drift onto
    different mounts. Its host counterpart is ``TOS_OPERATOR_PROJECTION_DIR``;
    the compose file calls them a pair that must be set together.
    """
    raw = os.environ.get("TOS_OPERATOR_PROJECTION_PATH", _DEFAULT_PROJECTION_PATH)
    path = Path(raw)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return path.parent / _SYMBOLS_SUBDIR / _DOCUMENT_NAME


class SymbolFill(BaseModel):
    """One observed fill — the most recent one on this side today.

    ``time_kst`` is the KST ``HH:MM`` of the bar whose decision produced the
    order, not a broker fill timestamp: the evidence carries no fill clock, only
    a ``trading_date``. ``time_basis`` names that, and is ``None`` exactly when
    ``time_kst`` is, so "no time" and "a time of unstated origin" never look
    alike.
    """

    model_config = ConfigDict(extra="ignore")

    quantity: str | None = None
    order_price_krw: str | None = None
    execution_price_krw: str | None = None
    price_basis: str | None = None
    broker_execution_id: str | None = None
    time_kst: str | None = None
    time_basis: str | None = None


class SymbolSide(BaseModel):
    """Today's fills on one side."""

    model_config = ConfigDict(extra="ignore")

    fills: int | None = None
    quantity: str | None = None
    last: SymbolFill | None = None


class SymbolHolding(BaseModel):
    """What TOS's own ledger still holds open. Never a broker balance."""

    model_config = ConfigDict(extra="ignore")

    quantity: str | None = None
    lots: int | None = None
    basis: str | None = None


class SymbolHaltReason(BaseModel):
    """One halt, with the KST time of the bar it happened on."""

    model_config = ConfigDict(extra="ignore")

    reason: str | None = None
    step: str | None = None
    time_kst: str | None = None


class SymbolHalt(BaseModel):
    """Today's blocks. Flow halts and withholdings stay apart, as exported.

    A withholding (``TIME_NOT_ADMITTED`` and friends) can fire on every bar near
    the close, so folding the two together would bury the flow halt — approval,
    release, venue — that the operator actually needs to see.
    """

    model_config = ConfigDict(extra="ignore")

    error: str | None = None
    last_flow: SymbolHaltReason | None = None
    last_withheld: SymbolHaltReason | None = None
    flow_counts: dict[str, int] | None = None


class SymbolSession(BaseModel):
    """Today's tenant session. ``status`` is ``None`` when none ran today."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    status: str | None = None
    boot_at: str | None = None
    end_at: str | None = None
    run_rc: int | None = None


class SymbolPnlPeriod(BaseModel):
    """Realized PnL over one period — today, or everything TOS has closed.

    Realized only, and FIFO: the exporter reads ``sts tos perf``'s own report
    rather than counting a second time, so the page and the CLI can never
    disagree. ``pnl_basis`` names the price the figure is built on; the page
    must say so, because a basis of ``MIXED`` or the sealed order price means
    some leg used the limit it sent, not a broker execution price.
    """

    model_config = ConfigDict(extra="ignore")

    pnl_krw: str | None = None
    pnl_basis: str | None = None
    closed_round_trips: int | None = None
    wins: int | None = None
    buy_fills: int | None = None
    sell_fills: int | None = None
    quantity_bought: str | None = None
    quantity_sold: str | None = None
    #: Cumulative only: what the FIFO still holds open.
    open_quantity: str | None = None
    open_lots: int | None = None


class SymbolUnresolvedAttempt(BaseModel):
    """One order attempt that is outside the PnL — «집계 밖» in ``sts tos perf``.

    ``reason`` and ``observation`` are the exporter's copy of the sentences the
    CLI prints, so an operator reading the page and an operator reading the
    terminal are told the same thing about the same order. The attempt's leaf
    path is NOT a field: the exporter strips it before writing.
    """

    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    status_label: str | None = None
    side: str | None = None
    quantity: str | None = None
    order_price_krw: str | None = None
    broker_execution_id: str | None = None
    trading_date: str | None = None
    reason: str | None = None
    observation: str | None = None


class SymbolUnresolved(BaseModel):
    """Everything the FIFO could not account for, with its count."""

    model_config = ConfigDict(extra="ignore")

    count: int | None = None
    attempts: list[SymbolUnresolvedAttempt] | None = None


class SymbolPnl(BaseModel):
    """One tenant's realized PnL. ``None`` on a decision-only tenant."""

    model_config = ConfigDict(extra="ignore")

    today: SymbolPnlPeriod | None = None
    cumulative: SymbolPnlPeriod | None = None
    unresolved: SymbolUnresolved | None = None


class SymbolRow(BaseModel):
    """One tenant's row — a stock tenant, or a decision-only futures one.

    On a ``decision_only`` row ``buy``/``sell``/``holding`` carry ``None``
    rather than ``0`` and ``pnl`` is absent entirely: futures entries stop at an
    independent approval step (operator decision 2026-11-05), so there is no
    order, no fill and no holding to report, and a zero would read as "bought
    nothing today" instead of "cannot buy here".
    """

    model_config = ConfigDict(extra="ignore")

    symbol: str | None = None
    tree_id: str | None = None
    #: ``stock`` or ``futures``, as the tenant tree's own render manifest
    #: declares it. Present on every row, including the stock ones that
    #: predate this field.
    kind: str | None = None
    #: ``LONG``/``SHORT``. Fixed per tenant in config — there is no step that
    #: picks a direction, so this is a label, not an outcome.
    direction: str | None = None
    decision_only: bool | None = None
    session: SymbolSession | None = None
    buy: SymbolSide | None = None
    sell: SymbolSide | None = None
    holding: SymbolHolding | None = None
    pnl: SymbolPnl | None = None
    halt: SymbolHalt | None = None
    ticks: int | None = None
    error: str | None = None


class TosSymbolsDocument(BaseModel):
    """Mirrors the exporter's document (``tools/tos_cp3/export_symbols.py``).

    Every leaf is nullable: the exporter's own sources report "no source ==
    null" and this DTO must not paper over that with a default that looks like a
    fact. Unknown extra keys are ignored rather than rejected, so an
    exporter-side field addition does not break this reader until the DTO is
    deliberately updated.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int
    #: The KST day these rows describe. The page compares it against its own
    #: today, so an export that stopped running yesterday is visible as such
    #: rather than reading as today's trading.
    date: str | None = None
    generated_kst: str | None = None
    holding_basis: str | None = None
    symbols: list[SymbolRow] | None = None


class TosSymbolsResponse(BaseModel):
    """Response DTO for ``GET /api/tos/symbols/today``."""

    model_config = ConfigDict(extra="ignore")

    available: bool
    reason: str | None = None
    age_seconds: float | None = None
    #: True when this tier had to strip a path or account-shaped value. It means
    #: the EXPORTER regressed; the body is safe either way.
    redacted: bool = False
    document: TosSymbolsDocument | None = None
    # The document's filesystem path is deliberately NOT a response field, for
    # the same reason the projection's and the bars document's are not: it is a
    # host/container deployment detail the page never renders, and operators get
    # it from the server log line in `_unavailable` instead.


def _unavailable(
    reason: str,
    path: Path,
    age_seconds: float | None = None,
    level: int = logging.WARNING,
) -> TosSymbolsResponse:
    """The one unavailable shape, logged at a level that matches the cause.

    ``symbols document absent`` is a **normal** state before the first export,
    so it logs at ``INFO`` (recorded in the call, silent in this deployment,
    where the root logger keeps level ``WARNING``). A real fault — unreadable
    file, invalid JSON, schema or version mismatch — logs at ``WARNING``, which
    reaches the container's stderr.
    """
    logger.log(level, "tos symbols document unavailable (%s): %s", reason, path)
    return TosSymbolsResponse(
        available=False,
        reason=reason,
        age_seconds=age_seconds,
        document=None,
    )


def _read_document(path: Path) -> TosSymbolsResponse:
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
        return _unavailable("symbols document absent", path, level=logging.INFO)
    except (UnicodeError, json.JSONDecodeError) as exc:
        return _unavailable(f"invalid json: {type(exc).__name__}", path, age_seconds)
    except OSError as exc:
        # NOT a data-format problem: a 0700 directory or a uid mismatch on the
        # mount. It gets its own reason so the operator looks at permissions
        # rather than at the exporter's output.
        return _unavailable(
            f"cannot read symbols document: {type(exc).__name__}", path, age_seconds
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

    # Redact before validating — the unresolved-attempt sentences are free text
    # the runtime wrote, and this tier does not trust the exporter to have
    # cleaned them (see `_redact`'s module docstring).
    payload, redacted = redact_payload(payload)
    if redacted:
        logger.warning(
            "tos symbols document carried a path or account-shaped value and was "
            "redacted by the reader; the exporter should have done this: %s",
            path,
        )

    try:
        document = TosSymbolsDocument.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - report as unknown, never 5xx
        # Exception type only. Pydantic's `str(exc)` embeds `input_value=...`,
        # i.e. the offending slice of a file this body would then echo to a
        # browser; the invalid-JSON branch above makes the same reduction.
        return _unavailable(f"schema mismatch: {type(exc).__name__}", path, age_seconds)

    return TosSymbolsResponse(
        available=True,
        reason=None,
        age_seconds=age_seconds,
        redacted=redacted,
        document=document,
    )


@router.get("/symbols/today", response_model=TosSymbolsResponse)
async def get_tos_symbols_today(response: Response) -> TosSymbolsResponse:
    """Return the exported per-symbol operator rows, if any.

    Read-only: opens the document by path only, never imports
    ``tos``/``tos_runtime``, never calls a broker, and never writes. A missing
    document, an unreadable one, or a schema/version mismatch all report
    ``available=false`` with a ``reason`` rather than raising — this route never
    returns a 5xx for those cases.
    """
    response.headers["Cache-Control"] = "no-store"
    return _read_document(_document_path())
