"""Read-only reader for the exported per-bar inspections: one, and the list.

Two routes over the same directory — ``GET /api/tos/sessions/{id}/bars`` reads
one document, ``GET /api/tos/sessions`` names the documents that exist so the
panel can offer a picker instead of asking the operator to type a directory
name. They share :func:`_bars_dir`, :data:`_SESSION_ID_PATTERN` and
:data:`LATEST` on purpose: a second copy of any of the three would drift, and
the list would then offer an id the reader refuses (or hide one it accepts).

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

**The listing opens no document.** Every value it returns is derived from a
*file name* that already passed :data:`_SESSION_ID_PATTERN` — the id itself, the
trading date in its tail, and the tenant shape in its head — plus that file's
mtime. It therefore exposes nothing the bars route does not already echo for the
same session, which matters because ``/tos`` is reachable from the internet
behind Cloudflare Access. Reading all thirteen-odd documents to answer a picker
would also mean a megabyte each, per page load, for one string apiece.

A name the pattern refuses is skipped rather than reported: naming it would echo
a caller-independent but still file-derived string, and the operator cannot act
on it from the browser anyway. The listing is bounded by
``TOS_BARS_SESSION_LIST_MAX`` (:data:`_DEFAULT_SESSION_LIST_MAX`) so a directory
nobody prunes cannot grow the response — or the dropdown — without bound.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from stat import S_ISREG
from typing import Any

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
#: panel still opens on it, so the first paint needs no listing round trip and
#: survives a listing that fails.
LATEST = "latest"

#: A session name split into the tenant label and its trading day —
#: ``<label>-YYYYMMDD``, the shape ``tools/tos_cp3/runners/cp3_tenant_daily.sh``
#: composes and ``tools/tos_cp3/status_board.py::_SESSION_DIR_RE`` parses. It is
#: restated rather than imported for the reason the whole module restates the
#: exporter's constants: this container carries no ``tools/`` at all.
#:
#: The label is non-greedy so the EIGHT trailing digits win: ``stock-000660-r1``
#: keeps its own digits and ``20261125`` is the day, not the other way round.
_SESSION_NAME_RE = re.compile(r"^(?P<label>[A-Za-z0-9][A-Za-z0-9_-]*?)-(?P<day>\d{8})$")

#: The futures labels, which carry the side and no instrument: the tenant tree
#: (``config/tos_runtime/cp3-setup-d-long``) names the contract, the session
#: directory does not, and this route refuses to invent one.
_FUTURES_DIRECTIONS = {"long": "LONG", "short": "SHORT"}

#: The stock labels: ``stock-r<N>`` for the tenant that was there before the
#: others (its symbol is not in the name) and ``stock-<symbol>-r<N>`` for every
#: one since. ``r<N>`` is the run — cron is always ``r1``, an operator restart
#: is ``r2`` — and it is part of the name, so the picker can tell two sessions
#: of one day apart.
_STOCK_LABEL_RE = re.compile(
    r"^stock(?:-(?P<instrument>[0-9A-Za-z]+))?-r(?P<run>\d{1,3})$"
)

#: Session kinds. ``other`` is not a failure: it is a name this route can list
#: and the bars reader can open, whose shape it will not claim to recognise.
KIND_FUTURES = "futures"
KIND_STOCK = "stock"
KIND_OTHER = "other"

#: How many sessions the listing returns, newest first. Overridable as
#: ``TOS_BARS_SESSION_LIST_MAX`` rather than being a literal in a branch.
#:
#: The default is the paper window the clean-day count is already judged over —
#: ``config/tos_status_board.yaml::clean_streak.window_days`` is 40 calendar
#: days — times the five tenant trees that export one document a day. So every
#: session inside the window that decides ``TOS_PAPER_READY`` is reachable from
#: the picker, and a directory nobody prunes still cannot grow the body without
#: bound.
_DEFAULT_SESSION_LIST_MAX = 200


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


def _session_list_max() -> int:
    """How many sessions the listing may return, from the environment.

    A value that is not a positive integer falls back to the default and says
    so once per request at ``WARNING``: a silently ignored cap and a silently
    applied one look identical in the response, and the operator who set it
    would have no way to tell which happened.
    """
    raw = os.environ.get("TOS_BARS_SESSION_LIST_MAX", "").strip()
    if not raw:
        # Unset, or set empty by compose's own `${VAR:-}` pass-through, which is
        # how the knob is REACHABLE without restating its default in the compose
        # file. An empty value is "no opinion", not a bad one, so it is silent.
        return _DEFAULT_SESSION_LIST_MAX
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value <= 0:
        logger.warning(
            "TOS_BARS_SESSION_LIST_MAX is not a positive integer; using %d",
            _DEFAULT_SESSION_LIST_MAX,
        )
        return _DEFAULT_SESSION_LIST_MAX
    return value


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


class BarsExplainRule(BaseModel):
    """What one authored rule means, in the words its author wrote.

    ``rationale`` is the strategy YAML's own sentence; the page shows it instead
    of the bare ``R1-ENTRY-LONG``. ``probe`` says the rule is an order-path
    exercise rather than a strategy signal — and it is NOT parsed out of that
    sentence: it comes from an operator-side map
    (``config/tos_bars_explain.yaml``), because the strategy DSL forbids extra
    keys and the strategy's digest is a replay input.
    """

    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    rule_id: str | None = None
    decision_kind: str | None = None
    rationale: str | None = None
    target_rationale: str | None = None
    probe: bool | None = None
    #: The published field names this rule compares, in the order it reads them.
    fields: list[str] | None = None
    #: The binding keys it compares against; their values are in ``bindings``.
    bindings: list[str] | None = None


class BarsExplainField(BaseModel):
    """One field's definition from the tenant's ``fields.yaml``.

    ``known=false`` means the catalog did not define this name — the exporter
    says so rather than inventing an operation.
    """

    model_config = ConfigDict(extra="ignore")

    #: The catalog's internal name (``z`` for the published ``z_x1000``).
    field: str | None = None
    op: str | None = None
    inputs: list[str] | None = None
    #: Any JSON value, deliberately. The tenant's ``fields.yaml`` is authored
    #: content and a future operation may take a null (``when_missing: null``),
    #: a list, or a nested mapping as a parameter. Typed narrowly, one such
    #: parameter would fail validation of the WHOLE document and the page would
    #: lose its bars — a new parameter shape must only ever be able to degrade
    #: the explanation, never the thing the panel cannot do without.
    params: dict[str, Any] | None = None
    scale: dict[str, Any] | None = None
    published_as: str | None = None
    known: bool | None = None


class BarsExplain(BaseModel):
    """The rule and field explanations, from the tenant content THIS session ran.

    ``schema`` and ``fields`` are aliased rather than the exported document
    renamed around them: ``fields`` would shadow a pydantic v1 ``BaseModel``
    attribute name and ``schema_`` keeps the response body saying ``fields``,
    which is what the page and the exporter both call it. Same reasoning as
    :class:`BarsWindow`'s ``from``.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    schema_: str | None = Field(default=None, alias="schema")
    rules: list[BarsExplainRule] | None = None
    default: BarsExplainRule | None = None
    #: Keyed by the name the rules reference, plus every field those stand on.
    fields_: dict[str, BarsExplainField] | None = Field(default=None, alias="fields")
    probe_basis: str | None = None


class HypotheticalTrade(BaseModel):
    """One would-have-been trade. Never a fill, and never a realized figure."""

    model_config = ConfigDict(extra="ignore")

    entry_time_kst: str | None = None
    entry_rule_id: str | None = None
    entry_price_points: str | None = None
    exit_time_kst: str | None = None
    #: ``None`` on a forced close: no rule said to exit, the session just ended.
    exit_rule_id: str | None = None
    exit_price_points: str | None = None
    points: str | None = None
    hypothetical_pnl_krw: str | None = None
    forced_close: bool | None = None
    forced_close_reason: str | None = None


class HypotheticalTotals(BaseModel):
    """The session's would-have-been total. Deliberately not named ``pnl_krw``."""

    model_config = ConfigDict(extra="ignore")

    trades: int | None = None
    wins: int | None = None
    #: ``None`` — not ``"0"`` — on a session with no trade at all. A zero would
    #: render as "±0 today", which is a different claim from "no signal fired".
    points: str | None = None
    hypothetical_pnl_krw: str | None = None
    forced_closes: int | None = None


class HypotheticalDecision(BaseModel):
    """A decision bar whose close could not be read, so it is outside the total."""

    model_config = ConfigDict(extra="ignore")

    time_kst: str | None = None
    decision_kind: str | None = None
    rule_id: str | None = None


class HypotheticalSkipped(HypotheticalDecision):
    """A decision bar left out of the total on purpose, and why.

    ``NOT_ENGINE_COUNTED``/``ENGINE_DISAGREES`` mean the bar's ``decision_kind``
    was re-derived by the inspection rather than made by the engine;
    ``PROBE_ENTRY`` means the rule is an order-path exercise, not a signal.
    Counting any of them would attribute to the strategy something it did not do.
    """

    model_config = ConfigDict(extra="ignore")

    reason: str | None = None


class BarsHypotheticalPnl(BaseModel):
    """What a decision-only tenant's decisions WOULD have earned, had they filled.

    Present only for the futures tenants, which decide but never order (operator
    decision 2026-11-05). Every field name here carries ``hypothetical``, the
    ``assumptions`` list travels with the numbers, and none of it is ever added
    to a realized PnL: the three assumptions (a guaranteed fill, no fees, no
    slippage) all push the figure the same, flattering way.
    """

    model_config = ConfigDict(extra="ignore")

    hypothetical: bool | None = None
    direction: str | None = None
    instrument: str | None = None
    contract: str | None = None
    multiplier_krw_per_point: int | None = None
    price_field: str | None = None
    price_scale: int | None = None
    assumptions: list[str] | None = None
    trades: list[HypotheticalTrade] | None = None
    totals: HypotheticalTotals | None = None
    unpriced_decisions: list[HypotheticalDecision] | None = None
    #: Decision bars deliberately left out, each with its reason — so the page
    #: can say what the total excluded instead of implying it counted everything.
    skipped_decisions: list[HypotheticalSkipped] | None = None


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
    #: ``stock``/``futures``, from the tenant tree the session actually ran.
    market: str | None = None
    #: True on a tenant that decides but never orders. The page must not draw
    #: an absent order as "ordered nothing".
    decision_only: bool | None = None
    strategy: BarsStrategy | None = None
    bindings: BarsBindings | None = None
    window: BarsWindow | None = None
    default: BarsDefault | None = None
    bars: list[BarsBar] | None = None
    summary: BarsSummary | None = None
    explain: BarsExplain | None = None
    #: Why no explanation, when there is none. A document can lose its rule
    #: sentences and still be a perfectly good bars document.
    explain_error: str | None = None
    hypothetical_pnl: BarsHypotheticalPnl | None = None
    hypothetical_pnl_error: str | None = None


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


class TosSessionEntry(BaseModel):
    """One exported session, as its FILE NAME describes it.

    Every field is derived from the name or the file's mtime; none is read from
    the document. ``kind``-specific fields are ``None`` rather than absent, and
    a field the name does not carry stays ``None`` rather than being guessed —
    ``instrument`` on a futures session, or on the stock tenant whose name
    predates the per-symbol convention, is unknown HERE even though the tenant
    tree knows it.
    """

    model_config = ConfigDict(extra="ignore")

    #: The id to pass back to ``/sessions/{session_id}/bars``, verbatim.
    session: str
    #: The trading day in ``YYYY-MM-DD``, or ``None`` when the tail of the name
    #: is eight digits that are not a date (``20261345``).
    date: str | None = None
    kind: str = KIND_OTHER
    #: ``LONG``/``SHORT`` on a futures session, ``None`` otherwise.
    direction: str | None = None
    #: The symbol when the name carries it (``stock-000660-r1-…``).
    instrument: str | None = None
    #: The run number on a stock session: cron is 1, an operator restart is 2.
    run: int | None = None
    #: Seconds since the export replaced this document, for an "is today's
    #: session already out?" read without opening it.
    age_seconds: float | None = None


class TosSessionsResponse(BaseModel):
    """Response DTO for ``GET /api/tos/sessions``."""

    model_config = ConfigDict(extra="ignore")

    available: bool
    reason: str | None = None
    sessions: list[TosSessionEntry] = Field(default_factory=list)
    #: True when the cap dropped older sessions. The newest are kept, so the
    #: picker is never missing today's — and a UI can say the list is partial
    #: instead of letting an operator conclude a session was never exported.
    truncated: bool = False


def _describe_session(session: str, age_seconds: float | None) -> TosSessionEntry:
    """Derive one entry from a session name. Never opens the document."""
    entry = TosSessionEntry(session=session, age_seconds=age_seconds)
    match = _SESSION_NAME_RE.match(session)
    if match is None:
        return entry

    day = match.group("day")
    try:
        entry.date = datetime.strptime(day, "%Y%m%d").date().isoformat()
    except ValueError:
        # Eight digits that are not a date. The session is still listed — the
        # document opens fine — it just sorts and groups as undated.
        entry.date = None

    label = match.group("label")
    direction = _FUTURES_DIRECTIONS.get(label)
    if direction is not None:
        entry.kind = KIND_FUTURES
        entry.direction = direction
        return entry

    stock = _STOCK_LABEL_RE.match(label)
    if stock is not None:
        entry.kind = KIND_STOCK
        entry.instrument = stock.group("instrument")
        entry.run = int(stock.group("run"))
    return entry


def _sessions_unavailable(
    reason: str, bars_dir: Path, level: int = logging.WARNING
) -> TosSessionsResponse:
    """The one unavailable shape for the listing, logged to match the cause."""
    logger.log(level, "tos bars directory unavailable (%s): %s", reason, bars_dir)
    return TosSessionsResponse(available=False, reason=reason, sessions=[])


def _list_sessions(bars_dir: Path, limit: int) -> TosSessionsResponse:
    """Name every exported session, newest day first, bounded by ``limit``.

    An empty but readable directory is ``available=true`` with no sessions:
    "nothing exported yet" is a fact this route established, not a failure to
    establish one. Only a directory it could not list at all is unavailable.
    """
    now = time.time()
    entries: list[TosSessionEntry] = []
    try:
        for entry in bars_dir.iterdir():
            if entry.suffix != ".json":
                continue
            session = entry.stem
            # The sentinel is not a session. A file literally named
            # `latest.json` would otherwise produce a second option carrying
            # the same value as the picker's "most recent" one, and selecting
            # either would resolve by mtime rather than to that file.
            if session == LATEST or not _SESSION_ID_PATTERN.match(session):
                continue
            try:
                # Inside the loop's own try for the reason `_resolve_latest`
                # gives: an export replacing a document between `iterdir` and
                # `stat` makes this entry vanish, and that is "the exporter ran
                # while the page was loading", not a 500.
                status = entry.stat()
            except OSError:
                continue
            if not S_ISREG(status.st_mode):
                continue
            delta = now - status.st_mtime
            entries.append(_describe_session(session, delta if delta >= 0 else None))
    except FileNotFoundError:
        # Normal before the first export ever ran, and the same words the bars
        # reader uses for one absent document.
        return _sessions_unavailable("bars directory absent", bars_dir, logging.INFO)
    except NotADirectoryError:
        return _sessions_unavailable("bars directory absent", bars_dir)
    except OSError as exc:
        # NOT "nothing exported": a 0700 directory or a uid mismatch on the
        # mount, which sends the operator to permissions rather than to the
        # exporter's output.
        return _sessions_unavailable(
            f"cannot list bars directory: {type(exc).__name__}", bars_dir
        )

    # Two stable passes, so the order is day-descending with a deterministic
    # order inside each day — a single reversed sort would also reverse the
    # names, putting `stock-r1` above `long` for no reason anyone could state.
    # Undated names sort last: `""` is below every ISO date.
    entries.sort(key=lambda item: item.session)
    entries.sort(key=lambda item: item.date or "", reverse=True)
    truncated = len(entries) > limit
    return TosSessionsResponse(
        available=True, reason=None, sessions=entries[:limit], truncated=truncated
    )


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


@router.get("/sessions", response_model=TosSessionsResponse)
async def list_tos_sessions(response: Response) -> TosSessionsResponse:
    """Name the sessions that have an exported bars document, newest day first.

    Two path segments, where the reader below takes four, so the two routes
    cannot shadow each other and ``latest`` stays what it has always been: a
    sentinel the READER resolves, never an id this listing returns.

    Read-only, and it opens no document: every value is derived from a file name
    that passed :data:`_SESSION_ID_PATTERN` and from that file's mtime. An
    unlistable directory reports ``available=false`` with a ``reason`` rather
    than raising; an empty one is ``available=true`` with no sessions.
    """
    response.headers["Cache-Control"] = "no-store"
    return _list_sessions(_bars_dir(), _session_list_max())


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
