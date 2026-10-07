"""The input contract — B1a's five-key journal JSONL and the governed field policy.

Part of the CP-3 B1b runner (``cp3`` package). The runner was one module until the
2026-10-08 review: at 1,820 lines it broke ``config/tos_size_budget.yaml``'s
1,000-line module cap and its 100-line function cap three times over, and
registering four day-one exceptions against a budget whose own header calls
registration "가시성, 면허가 아니라" would have been the wrong answer for NEW code.
So the module was decomposed along the seams it already had, and
``tos/runtime/cp3`` was added to that budget's ``scope`` so the caps are actually
enforced here (the review's fourth gate).

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib + ``pyyaml`` only. No
``shared.*``, no clock, no RNG, no ``subprocess``, no network. Intra-package
imports are RELATIVE — the allowlist does not name ``cp3``, so an absolute
``import cp3.…`` from a file under ``tos/`` is a TOS-FW-A violation while a
relative import carries no absolute name for the gate to classify.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._base import SCHEME, Cp3RunnerRefusal

__all__ = [
    "BAR_FIELD_KEYS",
    "FIELD_POLICY",
    "FIELD_POLICY_GOVERNED_KEYS",
    "INDICATOR_FIELD_KEYS",
    "JOURNAL_REQUIRED_KEYS",
    "REQUIRED_FIELD_KEYS",
    "FieldRecord",
    "read_field_records",
]

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

#: The keys of :data:`FIELD_POLICY` that B1a's ``lineage.json::fields`` also
#: carries, and therefore the keys a drift test can compare the two blocks on.
#: ``max_age_ms`` is deliberately NOT one of them — B1a publishes no freshness
#: bound (it is a producer, not a policy), so an equality over it would compare
#: this block against nothing.
FIELD_POLICY_GOVERNED_KEYS: tuple[str, ...] = (
    "unit",
    "scale",
    "multiplier",
    "sign",
    "quantization",
)

#: **The governed values per field, in the shape a Critical Input Policy
#: declares them** (``config/tos_runtime/paper/critical_input_policy.yaml``
#: 66-86행: ``unit`` / ``scale`` / ``multiplier`` / ``sign`` as STRING tokens
#: plus an int ``max_age_ms``). The string form is load-bearing, not cosmetic:
#: the shipped policy loader ``tos_runtime.marketfeed.policy`` lists
#: ``multiplier`` in ``_FIELD_STR_KEYS`` and refuses an "absent/blank/non-string"
#: value, so emitting ``100`` as an int here would publish a block that a paper
#: deployment could not load — the exact defect the 2026-10-08 review measured.
#:
#: The values mirror B1a's ``lineage.json::fields`` (B1a is the producer and
#: therefore the source of truth for unit/scale/multiplier/sign/quantization).
#: That mirroring is **tested against B1a's own source**, not asserted here:
#: ``tests/test_cp3_field_policy.py`` parses
#: ``tools/tos_cp3/produce_fields.py`` with ``ast`` and compares every shared
#: key — a cited digest cannot detect drift, a parse can.
#:
#: ``max_age_ms`` is ``None`` for every field and that is a **declared
#: difference, not an omission** (lineage ``declared_differences.B1b-D3``): the
#: backtest harness judges freshness from the injected
#: :data:`~cp3.replay.PROVISIONAL_TIME_BOUNDS`, and there is no per-field age
#: consumer on this path at all. A paper deployment of these fields must obtain
#: the value from the operator — it cannot be derived here.
FIELD_POLICY: Mapping[str, Mapping[str, Any]] = {
    "open_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": "100",
        "sign": "unsigned",
        "quantization": "half_up",
        "max_age_ms": None,
    },
    "high_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": "100",
        "sign": "unsigned",
        "quantization": "half_up",
        "max_age_ms": None,
    },
    "low_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": "100",
        "sign": "unsigned",
        "quantization": "half_up",
        "max_age_ms": None,
    },
    "close_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": "100",
        "sign": "unsigned",
        "quantization": "half_up",
        "max_age_ms": None,
    },
    "volume": {
        "unit": "contract",
        "scale": "unit",
        "multiplier": "1",
        "sign": "unsigned",
        "quantization": "exact",
        "max_age_ms": None,
    },
    "session_token": {
        "unit": "opaque_token",
        "scale": "none",
        "multiplier": "1",
        "sign": "unsigned",
        "quantization": "exact",
        "max_age_ms": None,
    },
    "vwap_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": "100",
        "sign": "unsigned",
        "quantization": "half_up",
        "max_age_ms": None,
    },
    "atr14_x100": {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": "100",
        "sign": "unsigned",
        "quantization": "half_up",
        "max_age_ms": None,
    },
    "z_x1000": {
        "unit": "atr",
        "scale": "thousandths",
        "multiplier": "1000",
        "sign": "signed",
        "quantization": "truncate_toward_zero",
        "max_age_ms": None,
    },
    "hi_vol": {
        "unit": "bool",
        "scale": "none",
        "multiplier": "1",
        "sign": "unsigned",
        "quantization": "exact",
        "max_age_ms": None,
    },
    "stall_ok": {
        "unit": "bool",
        "scale": "none",
        "multiplier": "1",
        "sign": "unsigned",
        "quantization": "exact",
        "max_age_ms": None,
    },
    "reversal_ok": {
        "unit": "bool",
        "scale": "none",
        "multiplier": "1",
        "sign": "unsigned",
        "quantization": "exact",
        "max_age_ms": None,
    },
    "entry_window": {
        "unit": "bool",
        "scale": "none",
        "multiplier": "1",
        "sign": "unsigned",
        "quantization": "exact",
        "max_age_ms": None,
    },
    "vwap_reverted": {
        "unit": "bool",
        "scale": "none",
        "multiplier": "1",
        "sign": "unsigned",
        "quantization": "exact",
        "max_age_ms": None,
    },
    "eod": {
        "unit": "bool",
        "scale": "none",
        "multiplier": "1",
        "sign": "unsigned",
        "quantization": "exact",
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
    # Extras are refused for the SAME reason the journal level refuses them, and
    # for one more: every ``fields`` value enters the per-bar snapshot digest
    # (``FieldRecord.snapshot_canonical_digest``), so silently admitting an
    # unknown key would let content nobody governs change the Capsule identity
    # the whole trace is bound to.
    extra = sorted(set(raw) - set(REQUIRED_FIELD_KEYS))
    if extra:
        raise _refuse_line(
            path,
            line_number,
            f"'fields' carries unexpected key(s) {extra} — the admissible set is "
            f"exactly {list(REQUIRED_FIELD_KEYS)}; an ungoverned field would "
            "still enter the snapshot digest this trace is bound to",
        )
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


@dataclass(frozen=True)
class _LineScalars:
    """One line's four validated top-level scalars (``fields`` handled separately)."""

    raw_event_id: str
    source_id: str
    instrument: str
    as_of_ms: int


def _validated_line_scalars(
    raw: Mapping[str, Any], *, path: Path, line_number: int
) -> _LineScalars:
    """Validate one line's four top-level scalars.

    Split out of :func:`read_field_records` so that function fits the 100-line
    function cap ``config/tos_size_budget.yaml`` enforces over this tree; the
    per-line scalar checks and the cross-line invariants (duplicate id, constant
    source_id/instrument, strictly increasing coordinate) are two different
    concerns anyway, and only the second needs the loop's accumulated state.

    Raises:
        Cp3RunnerRefusal: A scalar is blank, the wrong type, or negative.
    """
    raw_event_id = raw["raw_event_id"]
    line_source_id = raw["source_id"]
    line_instrument = raw["instrument"]
    for name, value in (
        ("raw_event_id", raw_event_id),
        ("source_id", line_source_id),
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
    return _LineScalars(
        raw_event_id=raw_event_id,
        source_id=line_source_id,
        instrument=line_instrument,
        as_of_ms=as_of_ms,
    )


def _refuse_cross_line_drift(
    scalars: _LineScalars,
    *,
    path: Path,
    line_number: int,
    seen_ids: set[str],
    source_id: str | None,
    instrument: str | None,
    previous_as_of: int | None,
) -> None:
    """Enforce the invariants that span LINES, not one line.

    A duplicate ``raw_event_id``, a second producer, a second instrument, or a
    non-advancing time coordinate. Split from :func:`read_field_records` for the
    function cap; grouped together because all four need the loop's accumulated
    state and none of them can be judged from a single line.

    Raises:
        Cp3RunnerRefusal: Any of the four.
    """
    raw_event_id = scalars.raw_event_id
    line_source_id = scalars.source_id
    line_instrument = scalars.instrument
    as_of_ms = scalars.as_of_ms
    if raw_event_id in seen_ids:
        raise _refuse_line(
            path,
            line_number,
            f"duplicate raw_event_id {raw_event_id!r} — one raw event is one "
            "bar; a repeat would make the bar stream and the field lookup "
            "disagree about which record a bar carries",
        )
    if source_id is not None and line_source_id != source_id:
        raise _refuse_line(
            path,
            line_number,
            f"source_id {line_source_id!r} differs from the file's first "
            f"source_id {source_id!r} — one artifact is ONE producer's "
            "output; a mixed file has no single producer identity to record "
            "as its lineage parent (ADR-002-018 §10 'exact parents')",
        )
    if instrument is not None and line_instrument != instrument:
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
    source_id: str | None = None
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
        scalars = _validated_line_scalars(raw, path=path, line_number=line_number)
        raw_event_id = scalars.raw_event_id
        line_source_id = scalars.source_id
        line_instrument = scalars.instrument
        as_of_ms = scalars.as_of_ms
        _refuse_cross_line_drift(
            scalars,
            path=path,
            line_number=line_number,
            seen_ids=seen_ids,
            source_id=source_id,
            instrument=instrument,
            previous_as_of=previous_as_of,
        )
        if source_id is None:
            source_id = line_source_id
        if instrument is None:
            instrument = line_instrument
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
