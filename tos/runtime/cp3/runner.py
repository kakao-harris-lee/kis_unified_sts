"""CP-3 B1b — B1a's field JSONL → ``tos.backtest.Bar`` → ``BacktestDriver`` trace.

`docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md` §3 구축물 B1b, §5 2.
Placement rationale (digest-untouched + firewall scope) is in this package's
``__init__.py`` — read that first.

What this module is
-------------------
A **loader + driver**, nothing else. ``tos.backtest`` ships no loader on
purpose (``bars.py`` 4-7행: parquet/pandas ingestion is out-of-tree because a
harness that reads files is no longer a pure function of its inputs) and the
harness is handed a ``tuple[Bar, ...]``. This module is that out-of-tree loader
for the one input shape CP-3 defines — B1a's five-key journal JSONL — plus the
wiring that drives it through the single shipped event core and writes the
trace artifact the out-of-tree comparator (B3) reads.

It **re-authors nothing**: ``validate_bar_stream``, ``CausalBarConverter``,
``BacktestDriver``, ``EngineCore``, ``trace_document`` / ``trace_digest``, the
strategy loader, the bindings loader and the bindings resolution rules are all
consumed verbatim.

The value-surface seam (how per-bar fields reach the DSL)
---------------------------------------------------------
This is the one non-obvious part, so it is stated precisely.

``tos.backtest`` injects two slots per bar: a ``CapsuleSource``
(``(Bar) -> DecisionContextCapsule``) and a ``DecisionContextResolver``
(``(capsule, *, instrument_key) -> DecisionTickPayload``). The shipped
``ProvisionalContextResolver`` resolves **nothing** — slice #1 binds the
Capsule's ``SnapshotRef`` only, so "the mechanism runs, the decision starves"
(``resolver.py`` class docstring). The **typed seam for values already exists**
one layer down: ``DecisionTickPayload.value_view`` is a
``tos.dsl.ContextValueView``, and ``tos.engine.pipeline`` passes it straight
into ``evaluate_resolved(resolved_context=payload.value_view)``, which merges
it at ``env["capsule"]["resolved_values"][field_key]``
(``tos.dsl.determinism.build_environment``). So a DSL ref
``("capsule", "resolved_values", "z_x1000")`` resolves iff a view carrying that
``field_key`` is published for that tick.

:class:`Cp3CapsuleSource` therefore mints a **per-bar** Capsule whose
``SnapshotRef`` is derived from that bar's own record, and
:class:`Cp3FieldResolver` resolves that reference back to the bar's fields and
publishes the view — the same ``snapshot_id`` + ``canonical_digest`` round trip
``tos.marketfeed.resolver`` performs (``resolver.py`` 170-192행), and the same
refusal: a view is published **only** on an exact binding match, never on a
near miss. Per-bar Capsules are also what makes the bars *distinguishable* at
all (the shipped suite issues one identical Capsule for every bar, which is
honest for a value-free slice but useless here).

**Declared difference — the fields enter as already-admitted values.** The
production path admits a Critical Input through
``tos.marketfeed``'s five-value policy (unit / scale / multiplier / sign /
max_age_ms) and its VALID gate, and ``ContextValueView.values`` is "VALID by
construction" because *that producer* applied the gate
(``tos.dsl.context_value`` class docstring). The backtest harness has **no
policy seam at all**: there is no injection point in ``tos.backtest`` for a
``critical_input_policy``, and ``ContextValue`` deliberately carries no
``field_state``. So B1b publishes B1a's fields as already-admitted values and
records each field's five governed values in the lineage block
(:data:`FIELD_POLICY`) rather than enforcing them here. Two consequences, both
recorded in ``lineage.json::declared_differences``:

* a field whose scale/sign disagrees with B1a's lineage would not be caught
  here — it is caught by B1a's own per-bar equality tests against the legacy
  implementation;
* ``max_age_ms`` has no consumer in this path: freshness is judged from the
  injected :class:`~tos.backtest.BarTimeProjection` bounds, not from the field
  policy.

What the run can and cannot claim
---------------------------------
Exactly what ``tos.backtest`` already declares, carried through unchanged:
``closes_no_ev`` is ``True``, there is no performance surface anywhere, and the
run is a **mechanism / parity demonstration**. Plus the B4 cap: at most **one
order per scope for the whole run**, so every later firing is an exact capacity
denial (``AT_MOST_ONE_EXPOSURE_HELD``) rather than a failure — recorded as
``capacity_denied: true``.

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib + ``pyyaml``(transitively, via
the loaders). No ``shared.*``, no clock, no RNG, no subprocess, no network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from tos.backtest import BacktestDriver as _BacktestDriver
from tos.backtest import (
    Bar,
    BarStream,
    BarTimeProjection,
    CausalBarConverter,
    DeterministicFillModel,
    FillMode,
    FillParameters,
    FillSide,
    NonBrokerTransportNature,
    SyntheticNonLivePreconditions,
    validate_bar_stream,
)
from tos.backtest import trace_digest as _trace_digest
from tos.backtest.results import BacktestRun
from tos.canonical import EV_L1_PROVISIONAL_VERSION, ArtifactIntegrityError, get_scheme
from tos.capsule._base import PolicyRef
from tos.capsule.capsule import (
    CapsuleScope,
    DecisionContextCapsule,
    SafetyCriticalFacts,
    SnapshotRef,
)
from tos.dsl import AuthoredStrategy, ContextValue, ContextValueView, DecisionKind
from tos.dsl.context_value import VALUE_NAMESPACE
from tos.dsl.serialization import parse_strategy
from tos.engine import (
    EngineConfiguration,
    EngineCore,
    EventKind,
    HaltReason,
    InstrumentKey,
    RecordingEvidenceSink,
    StrategyRegistry,
    provisional_stage_map,
)
from tos.engine.admission import (
    derive_instrument_key,
    policy_work_steps,
    strategy_admissible,
)
from tos.engine.records import DecisionTickPayload
from tos.time import HealthState, SessionContext
from tos_runtime.operations.dependency_admission import (
    observe_source_tree_digest,
)
from tos_runtime.strategy.bindings import (
    STRATEGY_BINDINGS_FILE_NAME,
    load_strategy_bindings,
)
from tos_runtime.strategy.loader import load_strategies
from tos_runtime.strategy.resolve import _register_all, _resolve_bindings_or_refuse

# Relative, not absolute: the import firewall's allowlist (kernel §3.2 / runtime
# R1) names stdlib + pydantic/numpy/pandas/pyyaml + ``tos.*`` + ``tos_runtime.*``
# and nothing else, so `import cp3` would be a TOS-FW-A violation. A relative
# import carries no absolute module name for the gate to classify
# (``tools/tos_firewall_check.py`` skips ``node.level > 0``), which is why every
# intra-package import in this directory — the tests' included — is relative.
from . import __version__ as CP3_VERSION

__all__ = [
    "BAR_FIELD_KEYS",
    "FIELD_POLICY",
    "INDICATOR_FIELD_KEYS",
    "JOURNAL_REQUIRED_KEYS",
    "LINEAGE_SCHEMA_VERSION",
    "Cp3CapsuleSource",
    "Cp3FieldResolver",
    "Cp3RunnerRefusal",
    "FieldRecord",
    "LoadedStrategyContent",
    "RunArtifacts",
    "build_bars",
    "load_strategy_content",
    "main",
    "read_field_records",
    "run_replay",
]

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: ADR-002-018 §10 lineage block schema version — the SAME version B1a's
#: ``lineage.json`` carries, because this is the same block shape with a
#: different tool and different parents (B1a ``produce_fields.py``).
LINEAGE_SCHEMA_VERSION = 2


class Cp3RunnerRefusal(ArtifactIntegrityError):
    """A typed refusal — every one exits the CLI with status 2.

    Subclasses :class:`~tos.canonical.ArtifactIntegrityError` (itself a
    ``ValueError``) so a refusal raised here and a refusal raised inside the
    kernel's own validators are the same kind of failure to a caller, as every
    other fail-closed loader in this tree does
    (``tos_runtime.strategy.loader.StrategyLoadError`` precedent).
    """


# ===========================================================================
# The input contract — B1a's five-key journal JSONL
# ===========================================================================

#: The five top-level keys every line carries. Mirrors
#: ``tos_runtime/marketfeed/journal.py::_REQUIRED_KEYS`` (the only shipped
#: reader of this wire shape) and B1a's own
#: ``tools/tos_cp3/produce_fields.py::JOURNAL_REQUIRED_KEYS`` — restated as a
#: literal here for the same reason B1a restates it: the two sides meet through
#: the file, never through an import.
JOURNAL_REQUIRED_KEYS: tuple[str, ...] = (
    "raw_event_id",
    "source_id",
    "instrument",
    "as_of_ms",
    "fields",
)

#: The six ``fields`` keys that become ``Bar`` columns.
BAR_FIELD_KEYS: tuple[str, ...] = (
    "open_x100",
    "high_x100",
    "low_x100",
    "close_x100",
    "volume",
    "session_token",
)

#: The nine ``fields`` keys the Setup D policy and its lineage are about.
INDICATOR_FIELD_KEYS: tuple[str, ...] = (
    "vwap_x100",
    "atr14_x100",
    "z_x1000",
    "hi_vol",
    "stall_ok",
    "reversal_ok",
    "entry_window",
    "vwap_reverted",
    "eod",
)

#: Every required ``fields`` key, in B1a's own emission order.
REQUIRED_FIELD_KEYS: tuple[str, ...] = BAR_FIELD_KEYS + INDICATOR_FIELD_KEYS

#: The ×100 price fields, so the Decimal mapping is declared once.
_PRICE_FIELD_KEYS: frozenset[str] = frozenset(
    {"open_x100", "high_x100", "low_x100", "close_x100", "vwap_x100"}
)

#: **The five governed values per field, as governed Critical Inputs would
#: declare them** (``config/tos_runtime/paper/critical_input_policy.yaml``
#: 66-86행 shape: unit / scale / multiplier / sign / max_age_ms, each with its
#: source). Copied from B1a's ``lineage.json::fields`` — B1a is the producer and
#: therefore the source of truth for unit/scale/multiplier/sign; the runner
#: records them so the artifact is self-describing, and the lineage block cites
#: B1a's digest so a drift between the two is detectable.
#:
#: ``max_age_ms`` is ``None`` for every field and that is a **declared
#: difference, not an omission**: the backtest harness judges freshness from the
#: injected :class:`~tos.backtest.BarTimeProjection` bounds
#: (:data:`PROVISIONAL_TIME_BOUNDS`), and there is no per-field age consumer on
#: this path at all. A paper deployment of these fields must set it.
FIELD_POLICY: Mapping[str, Mapping[str, Any]] = {
    "open_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": 100,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "high_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": 100,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "low_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": 100,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "close_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": 100,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "volume": {
        "unit": "contract",
        "scale": "unit",
        "multiplier": 1,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "session_token": {
        "unit": "opaque_token",
        "scale": "none",
        "multiplier": 1,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "vwap_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": 100,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "atr14_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": 100,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "z_x1000": {
        "unit": "atr",
        "scale": "thousandths",
        "multiplier": 1000,
        "sign": "signed",
        "max_age_ms": None,
    },
    "hi_vol": {
        "unit": "bool",
        "scale": "none",
        "multiplier": 1,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "stall_ok": {
        "unit": "bool",
        "scale": "none",
        "multiplier": 1,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "reversal_ok": {
        "unit": "bool",
        "scale": "none",
        "multiplier": 1,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "entry_window": {
        "unit": "bool",
        "scale": "none",
        "multiplier": 1,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "vwap_reverted": {
        "unit": "bool",
        "scale": "none",
        "multiplier": 1,
        "sign": "unsigned",
        "max_age_ms": None,
    },
    "eod": {
        "unit": "bool",
        "scale": "none",
        "multiplier": 1,
        "sign": "unsigned",
        "max_age_ms": None,
    },
}


@dataclass(frozen=True)
class FieldRecord:
    """One validated JSONL line — the five journal keys, nothing more."""

    raw_event_id: str
    source_id: str
    instrument: str
    as_of_ms: int
    #: The ordered scalar field mapping. Every value is ``int`` / ``bool`` /
    #: ``str``; a float was refused at read time.
    fields: Mapping[str, int | bool | str]

    @property
    def snapshot_id(self) -> str:
        """The per-bar Critical Input Snapshot id this record stands behind.

        Derived from the record's own ``raw_event_id`` so it is a pure function
        of the input and survives replay byte-identically.
        """
        return f"cp3-b1b-snap:{self.raw_event_id}"

    @property
    def snapshot_canonical_digest(self) -> str:
        """The per-bar snapshot digest — the canonical digest of this record.

        Bars with different fields therefore carry different Capsule identities,
        which is what ``tos.backtest`` itself declares it cannot claim without a
        value surface (design #33 §5.2, D-E1 Gap-1). Here the value surface
        exists, so distinctness follows from the content rather than being
        asserted.
        """
        digest = SCHEME.compute_digest(
            {
                "raw_event_id": self.raw_event_id,
                "source_id": self.source_id,
                "instrument": self.instrument,
                "as_of_ms": self.as_of_ms,
                "fields": dict(self.fields),
            }
        )
        # The injected scheme's return type is untyped to its callers; narrow it
        # with a real check rather than a cast (the repo's own `no-any-return`
        # ratchet discipline, .github/workflows/tos-firewall.yml stage 2).
        assert isinstance(digest, str)
        return digest


def _refuse_line(path: Path, line_number: int, detail: str) -> Cp3RunnerRefusal:
    """Build the one refusal shape every per-line check raises."""
    return Cp3RunnerRefusal(f"{path}:{line_number}: {detail}")


def _validated_fields(
    raw: Any, *, path: Path, line_number: int
) -> dict[str, int | bool | str]:
    """Validate one line's ``fields`` mapping (fail-closed, float refused).

    Raises:
        Cp3RunnerRefusal: ``fields`` is not a mapping, a required key is
            missing, or any value is a float / ``None`` / a nested container.
            A float is refused for the kernel's own reason: the Critical Input
            value shape is ``bool``/``int``/``str`` and ``tos.marketfeed.value``
            325-359행 refuses a float outright, so admitting one here would let
            a value through this path that the runtime would reject.
    """
    if not isinstance(raw, dict):
        raise _refuse_line(
            path, line_number, f"'fields' must be a mapping, got {type(raw).__name__}"
        )
    missing = [key for key in REQUIRED_FIELD_KEYS if key not in raw]
    if missing:
        raise _refuse_line(path, line_number, f"'fields' is missing {missing}")
    validated: dict[str, int | bool | str] = {}
    for key, value in raw.items():
        if isinstance(value, bool):
            validated[key] = value
        elif isinstance(value, float):
            raise _refuse_line(
                path,
                line_number,
                f"field {key!r} is a float ({value!r}) — the Critical Input value "
                "shape is bool/int/str and tos.marketfeed.value refuses a float "
                "(no-floats is B1a's own encoding contract too)",
            )
        elif isinstance(value, (int, str)):
            validated[key] = value
        else:
            raise _refuse_line(
                path,
                line_number,
                f"field {key!r} is {type(value).__name__} — only bool/int/str "
                "scalars are admissible",
            )
    return validated


def read_field_records(path: Path) -> tuple[FieldRecord, ...]:
    """Read + fail-closed-validate B1a's field JSONL.

    Args:
        path: The ``fields.jsonl`` produced by ``tools/tos_cp3/produce_fields.py``.

    Returns:
        The records in file order.

    Raises:
        Cp3RunnerRefusal: The file is missing/unreadable, a line is not a JSON
            object, a journal key is missing or extra, ``as_of_ms`` is not a
            non-negative ``int``, a ``fields`` value is a float or a required
            field key is absent, a ``raw_event_id`` repeats, the instrument is
            not constant across the file, ``as_of_ms`` does not strictly
            increase, or the file is empty. An EMPTY file is refused rather
            than treated as a defined empty run: ``tos.backtest`` distinguishes
            a missing stream from an explicitly empty one, and a zero-line file
            on this path is a produced artifact that produced nothing, which is
            a producer failure, not an operator's explicit ``()``.
    """
    if not path.is_file():
        raise Cp3RunnerRefusal(f"{path}: fields JSONL does not exist")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Cp3RunnerRefusal(f"{path}: cannot read fields JSONL: {exc}") from exc

    records: list[FieldRecord] = []
    seen_ids: set[str] = set()
    instrument: str | None = None
    previous_as_of: int | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise _refuse_line(path, line_number, "blank line in a JSONL artifact")
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise _refuse_line(path, line_number, f"not valid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise _refuse_line(
                path, line_number, f"line is {type(raw).__name__}, not a JSON object"
            )
        missing = [key for key in JOURNAL_REQUIRED_KEYS if key not in raw]
        if missing:
            raise _refuse_line(
                path,
                line_number,
                f"missing journal key(s) {missing} — the required set is "
                f"{list(JOURNAL_REQUIRED_KEYS)}",
            )
        extra = sorted(set(raw) - set(JOURNAL_REQUIRED_KEYS))
        if extra:
            raise _refuse_line(
                path,
                line_number,
                f"unexpected journal key(s) {extra} — refusing rather than "
                "silently ignoring content the producer added",
            )
        raw_event_id = raw["raw_event_id"]
        source_id = raw["source_id"]
        line_instrument = raw["instrument"]
        for name, value in (
            ("raw_event_id", raw_event_id),
            ("source_id", source_id),
            ("instrument", line_instrument),
        ):
            if not isinstance(value, str) or not value.strip():
                raise _refuse_line(
                    path, line_number, f"{name!r} must be a non-empty string"
                )
        as_of_ms = raw["as_of_ms"]
        if isinstance(as_of_ms, bool) or not isinstance(as_of_ms, int):
            raise _refuse_line(
                path,
                line_number,
                f"'as_of_ms' must be an int, got {type(as_of_ms).__name__}",
            )
        if as_of_ms < 0:
            raise _refuse_line(path, line_number, "'as_of_ms' must be non-negative")
        if raw_event_id in seen_ids:
            raise _refuse_line(
                path,
                line_number,
                f"duplicate raw_event_id {raw_event_id!r} — one raw event is one "
                "bar; a repeat would make the bar stream and the field lookup "
                "disagree about which record a bar carries",
            )
        if instrument is None:
            instrument = line_instrument
        elif line_instrument != instrument:
            raise _refuse_line(
                path,
                line_number,
                f"instrument {line_instrument!r} differs from the file's first "
                f"instrument {instrument!r} — one replay is one scope",
            )
        if previous_as_of is not None and as_of_ms <= previous_as_of:
            raise _refuse_line(
                path,
                line_number,
                f"'as_of_ms' must strictly increase ({previous_as_of} -> "
                f"{as_of_ms}) — it becomes Bar.timestamp_coordinate, which "
                "tos.backtest.validate_bar_stream requires to be strictly "
                "increasing (a non-advancing coordinate makes freshness "
                "unjudgeable)",
            )
        previous_as_of = as_of_ms
        seen_ids.add(raw_event_id)
        records.append(
            FieldRecord(
                raw_event_id=raw_event_id,
                source_id=source_id,
                instrument=instrument,
                as_of_ms=as_of_ms,
                fields=_validated_fields(
                    raw["fields"], path=path, line_number=line_number
                ),
            )
        )
    if not records:
        raise Cp3RunnerRefusal(
            f"{path}: the fields JSONL carries zero lines — a produced artifact "
            "that produced nothing is a producer failure, not an operator's "
            "explicit empty run"
        )
    return tuple(records)


# ===========================================================================
# Bars
# ===========================================================================


def _price(value: int | bool | str, *, field_key: str, raw_event_id: str) -> Decimal:
    """Map one ×100 integer minor-unit price onto the ``Bar``'s Decimal.

    **The mapping, stated once.** ``Bar``'s price fields are
    :data:`~tos.canonical.CanonicalDecimal` — a ``Decimal`` normalized at
    validation time so numerically-equal magnitudes share one digest. B1a
    publishes prices as *index points × 100* integers (``multiplier: 100``,
    ``scale: hundredths``, ``quantization: half_up``). The inverse is an exact
    decimal scale shift, ``Decimal(x).scaleb(-2)`` — **never** a float divide
    and never ``Decimal(x) / 100``: ``scaleb`` performs no division and so
    cannot round, which keeps the bar a lossless function of the integer and
    keeps the digest a function of the integer too.

    The integers stay the DSL-visible form: the policy compares ``z_x1000`` and
    the other integer fields, never these Decimals (``tos.dsl`` ordering
    comparisons are numeric and B1a exposes minor units precisely so an ordering
    comparison is integral — design #32 §2.5).

    Raises:
        Cp3RunnerRefusal: The value is not a plain ``int``.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise Cp3RunnerRefusal(
            f"{raw_event_id}: field {field_key!r} must be an int price in "
            f"hundredths, got {type(value).__name__}"
        )
    return Decimal(value).scaleb(-2)


def build_bars(
    records: Sequence[FieldRecord],
) -> tuple[BarStream, dict[int, FieldRecord]]:
    """Build the validated bar stream plus the ``bar_index -> record`` side table.

    ``bar_index`` is the record's position in the file (0-based, strictly
    increasing) and ``timestamp_coordinate`` is ``as_of_ms`` verbatim — the
    opaque injected coordinate ``tos.backtest`` asks for, never a clock read.
    ``session_token`` is B1a's KST session date, carried through opaquely (no
    market hours are read from it).

    Args:
        records: The validated field records, in file order.

    Returns:
        ``(bars, by_bar_index)``. The side table keeps the nine indicator
        fields (and the six bar fields) addressable by ``bar_index`` without
        putting them on the ``Bar``, which carries no field surface.

    Raises:
        Cp3RunnerRefusal: A record's prices do not form a well-formed bar
            (inverted range, open/close outside it, a non-positive price, a
            negative volume, a blank session token) — the reason is ``Bar``'s
            own validator's, re-raised with the offending ``raw_event_id``.
    """
    bars: list[Bar] = []
    by_bar_index: dict[int, FieldRecord] = {}
    for bar_index, record in enumerate(records):
        fields = record.fields
        volume = fields["volume"]
        if isinstance(volume, bool) or not isinstance(volume, int):
            raise Cp3RunnerRefusal(
                f"{record.raw_event_id}: field 'volume' must be an int, got "
                f"{type(volume).__name__}"
            )
        session_token = fields["session_token"]
        if not isinstance(session_token, str):
            raise Cp3RunnerRefusal(
                f"{record.raw_event_id}: field 'session_token' must be a str, got "
                f"{type(session_token).__name__}"
            )
        try:
            bar = Bar(
                bar_index=bar_index,
                timestamp_coordinate=record.as_of_ms,
                open_price=_price(
                    fields["open_x100"],
                    field_key="open_x100",
                    raw_event_id=record.raw_event_id,
                ),
                high_price=_price(
                    fields["high_x100"],
                    field_key="high_x100",
                    raw_event_id=record.raw_event_id,
                ),
                low_price=_price(
                    fields["low_x100"],
                    field_key="low_x100",
                    raw_event_id=record.raw_event_id,
                ),
                close_price=_price(
                    fields["close_x100"],
                    field_key="close_x100",
                    raw_event_id=record.raw_event_id,
                ),
                volume=Decimal(volume),
                session_token=session_token,
            )
        except ValueError as exc:  # ArtifactIntegrityError / ValidationError
            raise Cp3RunnerRefusal(
                f"{record.raw_event_id}: not a well-formed Bar: {exc}"
            ) from exc
        bars.append(bar)
        by_bar_index[bar_index] = record
    return validate_bar_stream(bars), by_bar_index


# ===========================================================================
# The per-bar Capsule + value-view seam
# ===========================================================================

#: The Capsule's declared environment. Not ``paper`` and not ``live``: this is
#: an out-of-tree clock-free replay, and labelling it ``paper`` would let a
#: paper-scoped consumer mistake the artifact for a paper session's.
CAPSULE_ENVIRONMENT = "non-live-backtest"

#: The Capsule's decision class. The policy gates on ``resolved_values`` only,
#: so this is scope metadata, never a guard operand here.
CAPSULE_DECISION_CLASS = "entry"

#: The Critical Input policy this replay's Capsules name. A ``PolicyRef`` is
#: required-covered content, and naming B1a's producer identity is the honest
#: answer to "which policy admitted these fields" — see the module docstring's
#: declared difference: B1a is the producer, and there is no policy *seam* in
#: the harness to enforce it through.
CRITICAL_INPUT_POLICY_ID = "cp3-b1b-field-policy"


class Cp3CapsuleSource:
    """The injected ``(Bar) -> DecisionContextCapsule`` slot — one Capsule per bar.

    Capsule issuance belongs to the Critical Input pipeline, never to the
    harness (``tos.backtest.converter`` ``CapsuleSource`` docstring). Here the
    "pipeline" is B1a's artifact, so the Capsule is minted from that artifact's
    own per-bar record and nothing else.
    """

    def __init__(
        self,
        *,
        instrument_key: InstrumentKey,
        direction: str,
        records_by_bar_index: Mapping[int, FieldRecord],
    ) -> None:
        """Wire the source.

        Args:
            instrument_key: The dispatch scope; the Capsule's own scope must
                agree with it or the pipeline refuses the tick
                (``pipeline.py`` 194행 cross-check).
            direction: The deployment's single direction (``LONG`` here —
                direction is a per-deployment fact, kickoff §2).
            records_by_bar_index: :func:`build_bars`' side table.
        """
        self._instrument_key = instrument_key
        self._direction = direction
        self._records = records_by_bar_index

    def __call__(self, bar: Bar) -> DecisionContextCapsule:
        """Issue the Capsule for ``bar``.

        Raises:
            Cp3RunnerRefusal: No record stands behind ``bar`` — a missing
                Decision Context is a fail-closed stop, never an implied empty
                one.
        """
        record = self._records.get(bar.bar_index)
        if record is None:
            raise Cp3RunnerRefusal(
                f"no field record stands behind bar_index={bar.bar_index} — a "
                "missing Decision Context forbids a decision"
            )
        return DecisionContextCapsule.issue(
            scheme=SCHEME,
            issuer_principal_id=CP3_VERSION,
            critical_input_policy=PolicyRef(
                policy_id=CRITICAL_INPUT_POLICY_ID,
                canonical_digest=SCHEME.compute_digest(
                    {"fields": {key: dict(FIELD_POLICY[key]) for key in FIELD_POLICY}}
                ),
            ),
            critical_input_snapshot=SnapshotRef(
                snapshot_id=record.snapshot_id,
                canonical_digest=record.snapshot_canonical_digest,
            ),
            scope=CapsuleScope(
                environment=CAPSULE_ENVIRONMENT,
                account=self._instrument_key.account,
                instrument=self._instrument_key.instrument,
                decision_class=CAPSULE_DECISION_CLASS,
            ),
            safety_critical_facts=SafetyCriticalFacts(
                account=self._instrument_key.account,
                instrument=self._instrument_key.instrument,
                direction=self._direction,
                quantity_basis="RISK",
                unit="contract",
                # session_and_tradability stays EMPTY on purpose: kickoff §2 ①
                # — `entry_window`/`eod` are strategy gates, not evidence of
                # tradability or session phase (RFC-008 §10; ADR-002-019).
            ),
        )


class Cp3FieldResolver:
    """The injected ``DecisionContextResolver`` that publishes the per-bar value view.

    Replaces :class:`~tos.backtest.ProvisionalContextResolver` at the slot the
    converter already has, which is the forward seam the design named
    ("when D-E2's typed resolver lands it is injected in place of the
    provisional one — the converter's call site does not change",
    ``tos.backtest.resolver`` module docstring).

    The binding round trip is the production one: resolve the Capsule's
    ``SnapshotRef`` through a snapshot store and publish a view **only** when
    ``snapshot_id`` *and* ``canonical_digest`` match exactly
    (``tos.marketfeed.resolver`` 170-192행; ADR-002-018 §15:386 — a silent
    substitution of a more-permissive snapshot is refused). Here the store is
    B1a's artifact, keyed by the snapshot id the capsule source derived.
    """

    #: Mirrors the shipped provisional resolver's own honesty label: nothing on
    #: this path is authoritative and nothing here closes an EV.
    authority_label = "NON_AUTHORITATIVE_PROVISIONAL"

    def __init__(self, *, records_by_snapshot_id: Mapping[str, FieldRecord]) -> None:
        """Wire the resolver with its snapshot store."""
        self._records = records_by_snapshot_id

    def __call__(
        self, capsule: DecisionContextCapsule, *, instrument_key: InstrumentKey
    ) -> DecisionTickPayload:
        """Resolve one Capsule into a value-carrying tick payload.

        Raises:
            Cp3RunnerRefusal: The Capsule's ``SnapshotRef`` names an id this
                store does not hold, or names an id whose digest disagrees.
                Both are fail-closed: publishing no view would silently
                degrade every operand to ``UNKNOWN`` (restrictive, but
                *indistinguishable* from "the policy legitimately saw false"),
                which is exactly the silent-inertness defect
                ``tos_runtime.strategy.resolve`` refuses one layer up.
        """
        ref = capsule.critical_input_snapshot
        record = self._records.get(ref.snapshot_id or "")
        if record is None:
            raise Cp3RunnerRefusal(
                f"capsule {capsule.capsule_id!r} binds snapshot_id "
                f"{ref.snapshot_id!r}, which this replay's snapshot store does "
                "not hold"
            )
        if ref.canonical_digest != record.snapshot_canonical_digest:
            raise Cp3RunnerRefusal(
                f"capsule {capsule.capsule_id!r} binds snapshot_id "
                f"{ref.snapshot_id!r} with canonical_digest "
                f"{ref.canonical_digest!r}, but the stored record digests to "
                f"{record.snapshot_canonical_digest!r} — a view is published "
                "only on an exact binding match"
            )
        values = tuple(
            ContextValue(
                field_key=key,
                value=record.fields[key],
                as_of=record.as_of_ms,
                payload_digest=record.snapshot_canonical_digest,
                observation_ref=record.raw_event_id,
            )
            for key in REQUIRED_FIELD_KEYS
        )
        view = ContextValueView(
            snapshot_id=record.snapshot_id,
            snapshot_canonical_digest=record.snapshot_canonical_digest,
            values=values,
            canonical_digest=SCHEME.compute_digest(
                {"values": [value.model_dump(mode="json") for value in values]}
            ),
            canonicalization_version=EV_L1_PROVISIONAL_VERSION,
        )
        return DecisionTickPayload(
            instrument_key=instrument_key, capsule=capsule, value_view=view
        )


# ===========================================================================
# Strategy content — loaded through the production loader
# ===========================================================================


@dataclass(frozen=True)
class LoadedStrategyContent:
    """The admitted strategy plus everything the lineage block needs from it."""

    strategy: AuthoredStrategy
    registry: StrategyRegistry
    instrument_key: InstrumentKey
    direction: str
    strategy_path: Path
    strategy_sha256: str
    bindings_path: Path
    bindings_sha256: str | None
    bindings: Mapping[str, Any]
    work_steps: int
    #: ``decision rationale -> (rule id, decision kind)`` for every rule and the
    #: default, derived from the authored policy itself.
    rule_index: Mapping[str, tuple[str, DecisionKind]]


def _rule_id(rationale: str) -> str:
    """The rule id a Decision's rationale declares — the token before the colon.

    The authored file is the only source of a rule id: the DSL's ``Rule`` has no
    id field (``tos.dsl.vocabulary``), so inventing one in the runner would make
    the trace's "which rule fired" a runner-side label rather than a property of
    the strategy. Reading the id out of the mandatory ``rationale`` keeps the
    strategy file authoritative.
    """
    head, _, _ = rationale.partition(":")
    return head.strip()


def _build_rule_index(
    strategy: AuthoredStrategy, *, strategy_path: Path
) -> dict[str, tuple[str, DecisionKind]]:
    """Map each reachable Decision's rationale onto ``(rule id, kind)``.

    The trace reads the *emitted outcome's* rationale and looks it up here, so
    no re-evaluation of the policy happens anywhere in this module — the engine
    remains the only evaluator.

    For an ``ACTION``/``FLAT`` Decision the emitted Proposal carries the
    **target's** rationale, not the Decision's
    (``tos.dsl.determinism._build_target_proposal``), so both are registered.

    Raises:
        Cp3RunnerRefusal: A rationale is blank, declares an empty rule id, or
            is shared by two different decisions — an ambiguous id would make
            the trace's rule attribution unreadable.
    """
    policy = strategy.policy
    if policy is None:  # pragma: no cover - admission already refused this
        raise Cp3RunnerRefusal(f"{strategy_path}: strategy carries no policy")
    index: dict[str, tuple[str, DecisionKind]] = {}

    def register(rationale: str | None, kind: DecisionKind, where: str) -> None:
        if rationale is None or not rationale.strip():
            raise Cp3RunnerRefusal(
                f"{strategy_path}: {where} has no rationale — the rule id is read "
                "from it"
            )
        rule_id = _rule_id(rationale)
        if not rule_id:
            raise Cp3RunnerRefusal(
                f"{strategy_path}: {where} rationale {rationale!r} declares no "
                "'<rule-id>: <why>' prefix"
            )
        existing = index.get(rationale)
        if existing is not None and existing != (rule_id, kind):
            raise Cp3RunnerRefusal(
                f"{strategy_path}: rationale {rationale!r} is shared by two "
                "decisions with different ids/kinds — rule attribution would be "
                "ambiguous"
            )
        index[rationale] = (rule_id, kind)

    for position, rule in enumerate(policy.rules, start=1):
        where = f"rule #{position}"
        register(rule.decision.rationale, rule.decision.kind, where)
        if rule.decision.target is not None:
            register(
                rule.decision.target.rationale, rule.decision.kind, f"{where} target"
            )
    register(policy.default.rationale, policy.default.kind, "default decision")
    return index


def _single_direction(strategy: AuthoredStrategy, *, strategy_path: Path) -> str:
    """The one direction this deployment's ACTION targets declare.

    Direction is a **per-deployment fact** (kickoff §2 —
    ``order_construction_policy.yaml`` 194-213행), so a file declaring two
    ACTION directions is not one deployment's content and is refused rather
    than silently collapsed.

    Raises:
        Cp3RunnerRefusal: No ``ACTION`` target declares a direction, or two
            declare different ones.
    """
    policy = strategy.policy
    assert policy is not None  # admission guaranteed it
    directions: set[str] = set()
    for rule in policy.rules:
        if rule.decision.kind is not DecisionKind.ACTION:
            continue
        target = rule.decision.target
        if target is None or target.direction is None:
            continue
        directions.add(target.direction)
    if len(directions) != 1:
        raise Cp3RunnerRefusal(
            f"{strategy_path}: expected exactly one ACTION direction, found "
            f"{sorted(directions)} — direction is a per-deployment fact and "
            "SHORT is a separate render (kickoff §4 결정 4)"
        )
    return directions.pop()


def load_strategy_content(
    *, strategy_path: Path, bindings_path: Path
) -> LoadedStrategyContent:
    """Load, admit, and bind the strategy through the **production** path.

    No second implementation of any rule: ``load_strategies`` is the shipped
    loader wired to the shipped ``parse_strategy`` / ``strategy_admissible``
    exactly as ``tos_runtime.strategy.resolve`` wires them,
    ``load_strategy_bindings`` is the shipped bindings loader, and
    ``_resolve_bindings_or_refuse`` / ``_register_all`` are that module's own
    five bindings rules and registration. They are module-private there and are
    reached deliberately: re-authoring the five rules here is precisely the
    "두 번째 구현" the kickoff warns against (§3), and what differs on this path
    is only the evidence sink — ``resolve_strategy_registry`` records a
    ``STRATEGY_REFUSED`` entry into a sqlite evidence store before raising,
    which a clock-free out-of-tree replay has no business opening.

    Args:
        strategy_path: The strategy file. Its **parent directory** is what the
            loader reads, so the directory's own discipline (no stray files,
            no empty directory, every file admissible) applies — the same
            discipline a boot gets.
        bindings_path: The ``strategy_bindings.yaml`` beside that directory.

    Returns:
        The :class:`LoadedStrategyContent`.

    Raises:
        Cp3RunnerRefusal: Any loader/admission/bindings refusal, a bindings
            path not named ``strategy_bindings.yaml``, a strategy directory
            holding more than the one requested file, or an undispatchable
            scope.
    """
    if bindings_path.name != STRATEGY_BINDINGS_FILE_NAME:
        raise Cp3RunnerRefusal(
            f"{bindings_path}: the bindings file must be named "
            f"{STRATEGY_BINDINGS_FILE_NAME!r} — that name is the loader's own "
            "contract (tos_runtime.strategy.bindings), and a differently-named "
            "file would be invisible to a boot"
        )
    strategies_dir = strategy_path.parent
    try:
        loaded = load_strategies(
            strategies_dir, parse=parse_strategy, admit=strategy_admissible
        )
        loaded_bindings = load_strategy_bindings(bindings_path)
        _resolve_bindings_or_refuse(loaded, loaded_bindings)
        registry = _register_all(loaded, loaded_bindings.strategies)
    except ValueError as exc:  # StrategyLoadError / StrategyBindingsLoadError / …
        raise Cp3RunnerRefusal(f"strategy content refused: {exc}") from exc

    selected = [
        entry
        for entry in loaded.strategies
        if entry.path.resolve() == strategy_path.resolve()
    ]
    if not selected:
        raise Cp3RunnerRefusal(
            f"{strategy_path}: not among the strategy files the loader admitted "
            f"in {strategies_dir} ({[str(e.path) for e in loaded.strategies]})"
        )
    if len(loaded.strategies) != 1:
        raise Cp3RunnerRefusal(
            f"{strategies_dir}: holds {len(loaded.strategies)} strategy files — "
            "this replay drives one scope through one core, so the directory "
            "must hold exactly the one requested strategy"
        )
    entry = selected[0]
    key, reasons = derive_instrument_key(entry.strategy)
    if key is None:
        raise Cp3RunnerRefusal(
            f"{strategy_path}: no single dispatch key: {'; '.join(reasons)}"
        )
    policy = entry.strategy.policy
    if policy is None:  # pragma: no cover - admission already refused this
        raise Cp3RunnerRefusal(f"{strategy_path}: strategy carries no policy")
    one = loaded_bindings.strategies.get(entry.path.stem)
    return LoadedStrategyContent(
        strategy=entry.strategy,
        registry=registry,
        instrument_key=key,
        direction=_single_direction(entry.strategy, strategy_path=strategy_path),
        strategy_path=entry.path,
        strategy_sha256=entry.sha256_digest,
        bindings_path=loaded_bindings.path,
        bindings_sha256=loaded_bindings.sha256_digest,
        bindings=dict(one.bindings) if one is not None else {},
        work_steps=policy_work_steps(policy),
        rule_index=_build_rule_index(entry.strategy, strategy_path=entry.path),
    )


# ===========================================================================
# The run
# ===========================================================================

#: Every bound the harness consumes, injected here — ``tos.backtest`` hardcodes
#: none (design #33 §10) and this module is its injection site. The values are
#: the ones the shipped canary suite injects
#: (``tos/tests/backtest/_backtest_fixtures.py::time_projection``), i.e. bounds
#: that positively admit; ``max_age_bound=1000`` is the VERIFICATION-PROFILE-002
#: ``MAX_time_conservative_freshness_age_ms`` value approved 2026-09-04, and the
#: rest remain **provisional** register candidates. A run built on them closes
#: no EV, which is already this harness's own declaration.
PROVISIONAL_TIME_BOUNDS: Mapping[str, Any] = {
    "source_age": 10,
    "delay_bounds": (5,),
    "max_age_bound": 1000,
    "future_tolerance": 50,
    "snapshot_age_bound": 20,
    "maximum_consumer_age_ms": 1000,
    "interval_width": 2,
    "boundary_lag": 10,
}

#: The default DSL work-step budget. Source:
#: ``config/tos_runtime/paper/engine.yaml`` 26행
#: ``dsl_evaluation_budget_steps: 64``. Overridable on the CLI so the value
#: stays injected rather than owned here.
DEFAULT_BUDGET_STEPS = 64

#: The default at-most-one-unresolved-send bound. Source: the same paper
#: ``engine.yaml`` discipline the shipped suite injects (1) — and the B4 cap
#: this run demonstrates (kickoff §3 B4 / design #33 §2.2-§2.3).
DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE = 1

#: The two stand-in bindings the Coordinator's step-12 attempt request consumes.
#: NON-AUTHORITATIVE PROVISIONAL, exactly as ``provisional_stage_map`` declares.
_PROOF_DIGEST = "cp3-b1b-provisional-conformance-proof"
_PERMIT_IDENTITY = "cp3-b1b-provisional-action-flow-permit"


@dataclass(frozen=True)
class RunArtifacts:
    """One replay's outputs — the trace lines, the counts, and the digests."""

    run: BacktestRun
    #: One JSON-native mapping per bar, in bar order.
    trace_lines: tuple[dict[str, Any], ...]
    trace_digest: str
    #: How many JSONL records were read.
    bars_read: int
    #: How many bars actually reached the core as a ``DECISION_TICK`` — counted
    #: from the trace, **not** from ``BacktestRun.bars_consumed``, which is
    #: ``len(stream)`` by construction (``driver.py`` 565행) and would therefore
    #: reconcile against ``bars_read`` vacuously.
    bars_driven: int
    #: ``BacktestRun.bars_consumed``, recorded as the harness reports it.
    bars_consumed_reported: int
    outcome_counts: Mapping[str, int]
    rule_fire_counts: Mapping[str, int]
    capacity_denials: int
    halt_counts: Mapping[str, int]


def _session_template() -> SessionContext:
    """The injected calendar/session determination — never recomputed here.

    ``is_open=True`` with ``phase="CONTINUOUS"`` is an **injected** stance, not
    a derivation from the bars: the kernel reads no market hours and
    ``session_token`` stays opaque. The bars are a replay of a session that did
    trade; asserting the phase here is how the harness states that rather than
    inferring it.
    """
    return SessionContext(
        tz_id="Asia/Seoul",
        tz_db_version="injected-provisional",
        trading_calendar_version="injected-provisional",
        phase="CONTINUOUS",
        is_open=True,
        tz_version_conflict=False,
        boundary_value=0,
    )


def _outcome_rationale(result: Any) -> str | None:
    """The emitted outcome's rationale, or ``None`` when nothing was emitted."""
    pipeline = getattr(result, "pipeline", None)
    if pipeline is None:
        return None
    outcome = pipeline.outcome
    if outcome is None:
        return None
    return getattr(outcome, "rationale", None)


def run_replay(
    *,
    records: Sequence[FieldRecord],
    content: LoadedStrategyContent,
    budget_steps: int = DEFAULT_BUDGET_STEPS,
    max_unresolved_send_per_scope: int = DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE,
) -> RunArtifacts:
    """Drive ``records`` through one engine core and assemble the trace.

    Args:
        records: The validated field records.
        content: The admitted strategy content.
        budget_steps: The injected ``dsl_evaluation_budget_steps``.
        max_unresolved_send_per_scope: The injected at-most-one send bound.

    Returns:
        The :class:`RunArtifacts`.

    Raises:
        Cp3RunnerRefusal: The JSONL's instrument disagrees with the strategy's
            declared dispatch scope, the authored policy does not fit the
            injected budget, or any per-bar refusal from the Capsule source /
            resolver.
    """
    instrument = records[0].instrument
    if instrument != content.instrument_key.instrument:
        raise Cp3RunnerRefusal(
            f"the fields JSONL carries instrument {instrument!r} but "
            f"{content.strategy_path} declares dispatch instrument "
            f"{content.instrument_key.instrument!r} — a replay never retargets a "
            "strategy at another instrument"
        )
    if content.work_steps > budget_steps:
        raise Cp3RunnerRefusal(
            f"{content.strategy_path}: policy_work_steps={content.work_steps} "
            f"exceeds the injected dsl_evaluation_budget_steps={budget_steps}; "
            "the engine would fold every tick to DEGRADED_BOUND_EXHAUSTED"
        )

    bars, by_bar_index = build_bars(records)
    resolver = Cp3FieldResolver(
        records_by_snapshot_id={record.snapshot_id: record for record in records}
    )
    converter = CausalBarConverter(
        instrument_key=content.instrument_key,
        resolver=resolver,
        capsule_source=Cp3CapsuleSource(
            instrument_key=content.instrument_key,
            direction=content.direction,
            records_by_bar_index=by_bar_index,
        ),
        time_projection=BarTimeProjection(
            session_template=_session_template(),
            health_state=HealthState.TRUSTED,
            **PROVISIONAL_TIME_BOUNDS,
        ),
    )
    fill_model = DeterministicFillModel(
        instrument_key=content.instrument_key,
        # ACKNOWLEDGE carries no magnitude and no price (records.py 201-207행):
        # the B4 disposition is "체결 비교 포기", so inventing a settlement
        # price for a comparison that will not use it would be a phantom.
        parameters=FillParameters(mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY),
        scenario_id=None,
    )
    driver = _BacktestDriver(
        converter=converter,
        fill_model=fill_model,
        continuity_id=f"cp3-b1b:{content.instrument_key.instrument}",
        # No mandated ScenarioId: this run is not one of design #33 §5.1's seven
        # rows, and labelling it with one would claim a scenario it does not
        # realize.
        scenario_id=None,
    )
    core = EngineCore(
        registry=content.registry,
        stages=provisional_stage_map(
            conformance_proof_digest=_PROOF_DIGEST,
            action_flow_permit_identity=_PERMIT_IDENTITY,
        ),
        configuration=EngineConfiguration(
            dsl_evaluation_budget_steps=budget_steps,
            max_unresolved_send_per_scope=max_unresolved_send_per_scope,
            canonicalization_version=EV_L1_PROVISIONAL_VERSION,
            enforcement_mechanism_version=CP3_VERSION,
        ),
        preconditions=SyntheticNonLivePreconditions(authority_epoch_current=True),
        transmit=fill_model,
        transport_nature=NonBrokerTransportNature(),
        sink=RecordingEvidenceSink(),
    )
    run = driver.run(core, bars)

    lines: list[dict[str, Any]] = []
    outcome_counts: dict[str, int] = {}
    rule_fire_counts: dict[str, int] = {}
    halt_counts: dict[str, int] = {}
    capacity_denials = 0
    for entry, result in zip(run.trace.entries, run.event_results):
        if entry.event_kind is not EventKind.DECISION_TICK:
            continue
        bar_index = entry.bar_index
        if bar_index is None:  # pragma: no cover - a tick entry always carries one
            raise Cp3RunnerRefusal(
                "a DECISION_TICK trace entry carries no bar_index — the trace "
                "could not be attributed to a bar"
            )
        record = by_bar_index[bar_index]
        rationale = _outcome_rationale(result)
        if rationale is None:
            rule_id, kind_label = "none", "NO_OUTCOME"
        else:
            resolved = content.rule_index.get(rationale)
            if resolved is None:
                raise Cp3RunnerRefusal(
                    f"{record.raw_event_id}: the emitted outcome's rationale "
                    f"{rationale!r} is not one the authored policy declares — "
                    "rule attribution must come from the strategy file, never "
                    "from a runner-side guess"
                )
            rule_id, kind = resolved
            kind_label = kind.value
        flow = getattr(result, "flow", None)
        flow_halt = None if flow is None else flow.halt_reason
        denied = flow_halt is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
        if denied:
            capacity_denials += 1
        pipeline_halt = None if result.pipeline is None else result.pipeline.halt_reason
        outcome_counts[kind_label] = outcome_counts.get(kind_label, 0) + 1
        rule_fire_counts[rule_id] = rule_fire_counts.get(rule_id, 0) + 1
        # Counted ONCE per bar per distinct reason: ``result.halt_reason`` is
        # the core's own restatement of whichever stage halted, so adding all
        # three sources naively double-counts every halt.
        for reason in {
            value
            for value in (pipeline_halt, flow_halt, result.halt_reason)
            if value is not None
        }:
            halt_counts[reason.value] = halt_counts.get(reason.value, 0) + 1
        lines.append(
            {
                "raw_event_id": record.raw_event_id,
                "as_of_ms": record.as_of_ms,
                "bar_index": bar_index,
                "outcome_kind": kind_label,
                "rule_id": rule_id,
                "pipeline_halt_reason": (
                    None if pipeline_halt is None else pipeline_halt.value
                ),
                "flow_halt_reason": None if flow_halt is None else flow_halt.value,
                "flow_halt_step": (
                    None
                    if flow is None or flow.halt_step is None
                    else flow.halt_step.value
                ),
                "capacity_denied": denied,
                "handed_off": entry.handed_off,
                "ordering_admission": entry.ordering_admission.value,
                "yield_sequence": entry.yield_sequence,
                "proposal_digest": entry.proposal_digest,
                "outcome_digest": entry.outcome_digest,
                "trace_entry_digest": SCHEME.compute_digest(
                    entry.model_dump(mode="json")
                ),
            }
        )
    if len(lines) != len(records):
        raise Cp3RunnerRefusal(
            f"the core produced {len(lines)} DECISION_TICK result(s) for "
            f"{len(records)} record(s) — a replay that did not reach every bar "
            "is not a replay of this dataset, and reporting the stream length "
            "as the driven count would hide it"
        )
    return RunArtifacts(
        run=run,
        trace_lines=tuple(lines),
        trace_digest=_trace_digest(run, scheme=SCHEME),
        bars_read=len(records),
        bars_driven=len(lines),
        bars_consumed_reported=run.bars_consumed,
        outcome_counts=dict(sorted(outcome_counts.items())),
        rule_fire_counts=dict(sorted(rule_fire_counts.items())),
        capacity_denials=capacity_denials,
        halt_counts=dict(sorted(halt_counts.items())),
    )


# ===========================================================================
# Artifacts
# ===========================================================================


def _sha256_file(path: Path) -> str:
    """The sha256 of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cp3_code_digest() -> str:
    """This package's own shipped-surface digest — ``__init__.py`` + ``runner.py``.

    Folded through the same canonical scheme
    ``tos_runtime.operations.dependency_admission.observe_source_tree_digest``
    uses, so the two digests in the lineage block are commensurable. Tests are
    deliberately excluded: they are not what produced the artifact.
    """
    here = Path(__file__).resolve().parent
    entries = [
        [name, _sha256_file(here / name)] for name in ("__init__.py", "runner.py")
    ]
    digest = SCHEME.compute_digest({"files": entries})
    assert isinstance(digest, str)
    return digest


def build_lineage(
    *,
    artifacts: RunArtifacts,
    content: LoadedStrategyContent,
    fields_path: Path,
    fields_lineage_path: Path | None,
    budget_steps: int,
    max_unresolved_send_per_scope: int,
) -> dict[str, Any]:
    """The ADR-002-018 §10 lineage block for this run — the same shape B1a emits.

    Parents, versions, counts, reconciliation, determinism, declared
    differences. **No timestamps and no wall-clock reads anywhere**: every value
    is a function of the inputs, so two runs over the same inputs produce a
    byte-identical block (that is the determinism claim, asserted by the
    suite's two-run test).

    Args:
        artifacts: The completed run's artifacts.
        content: The admitted strategy content.
        fields_path: B1a's ``fields.jsonl``.
        fields_lineage_path: B1a's ``lineage.json`` beside it, when present.
        budget_steps: The injected DSL budget.
        max_unresolved_send_per_scope: The injected send bound.

    Returns:
        The JSON-native lineage mapping.
    """
    run = artifacts.run
    return {
        "lineage_schema_version": LINEAGE_SCHEMA_VERSION,
        "tool": {
            "name": "tos/runtime/cp3/runner.py",
            "version": CP3_VERSION,
            "module": "cp3.runner",
            "code_digest": _cp3_code_digest(),
            "canonicalization_version": EV_L1_PROVISIONAL_VERSION,
        },
        "common_mode": (
            "This is NOT independent corroboration of the band math. The "
            "indicator fields this run compares are B1a's, produced by driving "
            "the ONE legacy implementation "
            "(shared/decision/setups/vwap_reversion.py); the TOS side evaluates "
            "a policy over them. What a match therefore corroborates is the "
            "POLICY, never the band arithmetic (ADR-002-018 §10: 'same function "
            "call' is a common mode, not independent confirmation)."
        ),
        "parents": {
            "fields_jsonl": {
                "path": str(fields_path),
                "sha256": _sha256_file(fields_path),
                "lines": artifacts.bars_read,
                "source_id": "see fields.jsonl::source_id (B1a producer identity)",
            },
            "fields_lineage_json": (
                None
                if fields_lineage_path is None
                else {
                    "path": str(fields_lineage_path),
                    "sha256": _sha256_file(fields_lineage_path),
                }
            ),
            "strategy_file": {
                "path": str(content.strategy_path),
                "sha256": content.strategy_sha256,
                "strategy_id": content.strategy.strategy_id,
                "canonical_digest": content.strategy.canonical_digest,
                "dsl_version": content.strategy.dsl_version,
                "config_binding_version": content.strategy.config_binding_version,
            },
            "strategy_bindings_file": {
                "path": str(content.bindings_path),
                "sha256": content.bindings_sha256,
                "bindings": dict(content.bindings),
            },
            "installed_code": {
                "source_tree_digest": observe_source_tree_digest(),
                "roots": ["tos/src/tos", "tos/runtime/src/tos_runtime"],
                "note": (
                    "the SAME digest `tos_runtime.compose.cli print-digests` "
                    "prints as expected_code_digest; cp3 adds zero bytes under "
                    "either root, so this value is unchanged by B1b"
                ),
            },
        },
        "versions": {
            "canonicalization_version": EV_L1_PROVISIONAL_VERSION,
            "dsl_evaluation_budget_steps": budget_steps,
            "dsl_evaluation_budget_steps_source": (
                "config/tos_runtime/paper/engine.yaml::dsl_evaluation_budget_steps"
            ),
            "max_unresolved_send_per_scope": max_unresolved_send_per_scope,
            "policy_work_steps": content.work_steps,
            "value_namespace": VALUE_NAMESPACE,
            "field_policy": {
                key: dict(FIELD_POLICY[key]) for key in REQUIRED_FIELD_KEYS
            },
            "injected_time_bounds": {
                key: list(value) if isinstance(value, tuple) else value
                for key, value in PROVISIONAL_TIME_BOUNDS.items()
            },
        },
        "counts": {
            "bars_read": artifacts.bars_read,
            "bars_driven": artifacts.bars_driven,
            "bars_consumed_reported": artifacts.bars_consumed_reported,
            "events_yielded": run.events_yielded,
            "trace_entries": len(run.trace.entries),
            "trace_lines": len(artifacts.trace_lines),
            "outcome_kinds": dict(artifacts.outcome_counts),
            "rule_fires": dict(artifacts.rule_fire_counts),
            "capacity_denials": artifacts.capacity_denials,
            "halt_reasons": dict(artifacts.halt_counts),
            "handoffs": run.handoff_count,
            "halt_records": len(run.halts),
            "fill_records": len(run.fill_records),
            "unsettled_fill_records": len(run.unsettled_fill_records),
        },
        "reconciliation": {
            # bars_driven is counted from the DECISION_TICK trace entries, so
            # this equality is a real check that every record reached the core.
            # (BacktestRun.bars_consumed is len(stream) by construction, so
            # reconciling against THAT would be vacuous — it is reported
            # separately under counts.bars_consumed_reported.)
            "bars_read_equals_bars_driven": artifacts.bars_read
            == artifacts.bars_driven,
            "bars_read": artifacts.bars_read,
            "bars_driven": artifacts.bars_driven,
            "trace_lines": len(artifacts.trace_lines),
            "trace_lines_equals_bars_driven": len(artifacts.trace_lines)
            == artifacts.bars_driven,
        },
        "determinism": {
            "no_timestamps": True,
            "no_clock_reads": True,
            "no_rng": True,
            "note": (
                "every value in this block is a function of (fields.jsonl, "
                "strategy file, bindings file, injected bounds, installed "
                "code); two runs over the same inputs are byte-identical"
            ),
        },
        "claims": {
            "closes_no_ev": run.closes_no_ev,
            "label": run.label,
            "oracle_scope": "DECISION_AND_INTENT_LEVEL_ONLY",
            "performance_surface": (
                "ABSENT BY CONSTRUCTION — no Sharpe/PnL/return/edge field exists "
                "anywhere in tos.backtest's result types (design #33 §1.2 B1), "
                "so this run makes no performance claim"
            ),
        },
        "declared_differences": [
            {
                "id": "B1b-D1",
                "item": "one order per scope per run (B4)",
                "note": (
                    "tos.backtest holds at most ONE order per scope for the "
                    "whole run — the provisional projection has no release path "
                    "(state.py:22) — so the FIRST firing is realized and every "
                    "later firing is an exact capacity denial "
                    "(AT_MOST_ONE_EXPOSURE_HELD), recorded as "
                    "capacity_denied=true. kickoff §3 B4 disposes this as "
                    "'체결 비교 포기': the comparison is decision/intent level, "
                    "never fill-for-fill. The denials are the seal FIRING, not "
                    "run failures."
                ),
            },
            {
                "id": "B1b-D2",
                "item": "vwap_reverted is the band form (B1a D7)",
                "note": (
                    "the exit gate reads B1a's `vwap_reverted` = abs(z) <= 0.2, "
                    "where 0.2 comes from "
                    "strategy.entry.params.reversal_confirm_atr_mult as a "
                    "FALLBACK: config/strategies/futures/"
                    "setup_d_vwap_reversion.yaml declares no "
                    "vwap_revert_band_atr_mult. The legacy exit is therefore not "
                    "reproduced from a declared band of its own; B1a's lineage "
                    "records the same difference on its side."
                ),
            },
            {
                "id": "B1b-D3",
                "item": "fields enter as already-admitted values",
                "note": (
                    "the backtest harness exposes no critical_input_policy seam: "
                    "ContextValueView.values is 'VALID by construction' because "
                    "the tos.marketfeed producer applied the gate, and "
                    "ContextValue carries no field_state. B1b publishes B1a's "
                    "fields directly and RECORDS each field's five governed "
                    "values (versions.field_policy) instead of enforcing them. "
                    "max_age_ms has no consumer here — freshness is judged from "
                    "versions.injected_time_bounds."
                ),
            },
            {
                "id": "B1b-D4",
                "item": "injected time/session stance",
                "note": (
                    "session phase CONTINUOUS / is_open=true and the trustworthy-"
                    "time bounds are INJECTED, not derived from the bars: the "
                    "kernel reads no market hours and session_token stays "
                    "opaque. The capsule's session_and_tradability slot is left "
                    "EMPTY on purpose (kickoff §2 ①: entry_window/eod are "
                    "strategy gates, not tradability evidence)."
                ),
            },
            {
                "id": "B1b-D5",
                "item": "LONG side only",
                "note": (
                    "the DSL has no abs() (DSL-G1) and direction is a "
                    "per-deployment fact, so the entry rule compares one side "
                    "(z_x1000 <= -1800). The legacy entry fires on abs(z) >= "
                    "1.8, i.e. BOTH sides; the SHORT half is a separate render "
                    "with its own strategy file (kickoff §4 결정 4). Expect this "
                    "run's ACTION/firing count to be a SUBSET of B1a's "
                    "entry-AND bar count for that reason."
                ),
            },
            {
                "id": "B1b-D6",
                "item": "no mandated ScenarioId",
                "note": (
                    "scenario_id is null: this replay is not one of design #33 "
                    "§5.1's seven mandated rows, and borrowing a row's id would "
                    "claim a scenario it does not realize."
                ),
            },
        ],
        "output": {
            "trace_jsonl": "trace.jsonl",
            "trace_digest": artifacts.trace_digest,
            "trace_digest_scope": (
                "tos.backtest.trace_digest over the run's wiring-trace document "
                "— reproducibility, never distinctness (design #33 §5.2)"
            ),
        },
    }


def _write_jsonl(path: Path, lines: Sequence[Mapping[str, Any]]) -> str:
    """Write one JSON object per line and return the file's sha256."""
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return _sha256_file(path)


def write_artifacts(
    *,
    out_dir: Path,
    artifacts: RunArtifacts,
    content: LoadedStrategyContent,
    fields_path: Path,
    budget_steps: int,
    max_unresolved_send_per_scope: int,
) -> tuple[Path, Path]:
    """Write ``trace.jsonl`` + ``lineage.json`` into ``out_dir``.

    Returns:
        ``(trace path, lineage path)``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl"
    lineage_path = out_dir / "lineage.json"
    trace_sha = _write_jsonl(trace_path, artifacts.trace_lines)
    fields_lineage = fields_path.parent / "lineage.json"
    lineage = build_lineage(
        artifacts=artifacts,
        content=content,
        fields_path=fields_path,
        fields_lineage_path=fields_lineage if fields_lineage.is_file() else None,
        budget_steps=budget_steps,
        max_unresolved_send_per_scope=max_unresolved_send_per_scope,
    )
    lineage["output"]["trace_jsonl_sha256"] = trace_sha
    lineage["output"]["trace_jsonl_lines"] = len(artifacts.trace_lines)
    lineage_path.write_text(
        json.dumps(lineage, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return trace_path, lineage_path


# ===========================================================================
# CLI
# ===========================================================================


def _parser() -> argparse.ArgumentParser:
    """The CLI surface."""
    parser = argparse.ArgumentParser(
        prog="cp3.runner",
        description=(
            "CP-3 B1b — drive B1a's field JSONL through tos.backtest and emit a "
            "decision-level trace + lineage. Closes no EV; makes no performance "
            "claim."
        ),
    )
    parser.add_argument("--fields", required=True, type=Path, help="B1a's fields.jsonl")
    parser.add_argument(
        "--strategy",
        required=True,
        type=Path,
        help="the Authored Strategy YAML (its parent directory is loaded)",
    )
    parser.add_argument(
        "--bindings",
        required=True,
        type=Path,
        help=f"the sibling {STRATEGY_BINDINGS_FILE_NAME}",
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="output directory for the artifacts"
    )
    parser.add_argument(
        "--budget-steps",
        type=int,
        default=DEFAULT_BUDGET_STEPS,
        help=(
            "injected dsl_evaluation_budget_steps (default %(default)s, from "
            "config/tos_runtime/paper/engine.yaml)"
        ),
    )
    parser.add_argument(
        "--max-unresolved-send-per-scope",
        type=int,
        default=DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE,
        help="injected max_unresolved_send_per_scope (default %(default)s)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Returns:
        ``0`` on success, ``2`` on any typed refusal.
    """
    args = _parser().parse_args(argv)
    try:
        records = read_field_records(args.fields)
        content = load_strategy_content(
            strategy_path=args.strategy, bindings_path=args.bindings
        )
        artifacts = run_replay(
            records=records,
            content=content,
            budget_steps=args.budget_steps,
            max_unresolved_send_per_scope=args.max_unresolved_send_per_scope,
        )
        trace_path, lineage_path = write_artifacts(
            out_dir=args.out,
            artifacts=artifacts,
            content=content,
            fields_path=args.fields,
            budget_steps=args.budget_steps,
            max_unresolved_send_per_scope=args.max_unresolved_send_per_scope,
        )
    except Cp3RunnerRefusal as exc:
        print(f"cp3.runner: REFUSED — {exc}", file=sys.stderr)
        return 2
    except ArtifactIntegrityError as exc:
        print(f"cp3.runner: REFUSED (kernel) — {exc}", file=sys.stderr)
        return 2
    print(f"bars_read={artifacts.bars_read} bars_driven={artifacts.bars_driven}")
    print(f"outcome_kinds={artifacts.outcome_counts}")
    print(f"rule_fires={artifacts.rule_fire_counts}")
    print(f"capacity_denials={artifacts.capacity_denials}")
    print(f"halt_reasons={artifacts.halt_counts}")
    print(f"handoffs={artifacts.run.handoff_count}")
    print(f"trace_digest={artifacts.trace_digest}")
    print(f"trace={trace_path}")
    print(f"lineage={lineage_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
