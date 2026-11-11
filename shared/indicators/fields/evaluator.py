"""The declarative field evaluator: a ``fields.yaml`` run bar by bar.

One :class:`FieldEvaluator` is one producer state machine. It is handed a
validated :class:`~shared.indicators.fields.schema.FieldsDocument` and then fed
bars in chronological order; on each bar it evaluates the declared fields in
declaration order and returns both every field value (for inspection and for the
P2-b equivalence harness) and the scaled integers/booleans that go to the
journal.

Three properties, each pinned by a test:

* **Causal.** Appending later bars can never change an earlier bar's output —
  every stateful op reads its window before the current bar enters it
  (``shared.indicators.fields.stateful``) and nothing here looks forward.
* **Deterministic.** Same bars in, same records out, bit for bit. No clock, no
  randomness, no dict-ordering dependence (fields are evaluated in declaration
  order; publish keys are emitted in publish order).
* **No silent coercion.** A field that has no value yet is ``None`` and stays
  ``None`` through arithmetic and comparisons; it becomes a definite boolean only
  through an explicit ``permissive``, and it can never be published.

What this evaluator does NOT decide
-----------------------------------
Which bars are *admitted*. A bar that only warms the frame-wide indicators —
the replay warmup and the frame's first session, which the witness computes ATR
and VWAP over but never decides on — goes to :meth:`FieldEvaluator.warm`
instead of :meth:`FieldEvaluator.step`, and the caller decides which is which.

Which bars are *emitted*. The legacy producer drops a bar whose ATR-scaled
fields cannot carry their published meaning
(``tools/tos_cp3/produce_fields.py::_inputs_unusable``: ``atr <= 0``,
``vwap <= 0``, ``close <= 0``) while still evaluating it so the causal windows
advance identically. That omission gate is the producer's, not the catalog's: a
``ratio_z`` with a zero divisor raises here, naming the bar, exactly as the
legacy ``vwap_extension_z`` raises on ``atr == 0``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import time
from typing import Any

from shared.indicators.fields.bar import (
    AtrWindow,
    FieldBar,
    SessionVwapTypical,
    minutes_since_open,
)
from shared.indicators.fields.catalog import NonePolicy
from shared.indicators.fields.errors import FieldEvalError
from shared.indicators.fields.scaling import ROUNDING_MODES
from shared.indicators.fields.schema import FieldsDocument, FieldSpec
from shared.indicators.fields.stateful import (
    GatedLag,
    GatedMax,
    GatedMin,
    GatedPercentile,
    GatedWindowOp,
)

#: Value a declared field can carry. ``None`` means "no value yet".
FieldValue = float | bool | str | None

#: Value a PUBLISHED field can carry — the kernel compares only these
#: (``tos/src/tos/marketfeed/value.py`` drops a float at the border).
PublishedValue = int | bool | str


@dataclass(frozen=True)
class EvaluatedBar:
    """One bar's complete evaluation.

    Attributes:
        bar: The bar that was evaluated.
        values: Every declared field's value, in declaration order. ``None``
            where the field has no value on this bar.
        published: The journal fields, in publish order, already scaled.
    """

    bar: FieldBar
    values: Mapping[str, FieldValue]
    published: Mapping[str, PublishedValue]


class FieldEvaluator:
    """Evaluate a declared field list over a chronological bar stream.

    Args:
        document: A validated declaration. Build it with
            :func:`~shared.indicators.fields.schema.load_fields_file` or
            :func:`~shared.indicators.fields.schema.parse_fields_document` —
            every structural refusal has already happened by then, so this class
            only raises on per-bar problems.
    """

    def __init__(self, document: FieldsDocument) -> None:
        self._document = document
        self._gated: dict[str, GatedWindowOp] = {}
        self._atr: dict[str, AtrWindow] = {}
        self._vwap: dict[str, SessionVwapTypical] = {}
        for spec in document.fields:
            name = spec.op_name
            if name == "atr":
                self._atr[spec.name] = AtrWindow(int(spec.params["period"]))
            elif name == "session.vwap_typical":
                self._vwap[spec.name] = SessionVwapTypical()
            elif name in {"gated_percentile", "gated_max", "gated_min", "gated_lag"}:
                self._gated[spec.name] = _build_gated(spec)

    @property
    def document(self) -> FieldsDocument:
        """The declaration this evaluator runs."""
        return self._document

    def run(self, bars: Iterable[FieldBar]) -> list[EvaluatedBar]:
        """Evaluate every bar of *bars* in order."""
        return list(self.iter_bars(bars))

    def iter_bars(self, bars: Iterable[FieldBar]) -> Iterator[EvaluatedBar]:
        """Lazily evaluate *bars*, yielding one record per bar."""
        for bar in bars:
            yield self.step(bar)

    def step(self, bar: FieldBar) -> EvaluatedBar:
        """Evaluate one bar and advance every causal window.

        Args:
            bar: The next bar in chronological order.

        Returns:
            The bar's field values and its published record.

        Raises:
            FieldEvalError: when a missing value reaches an op that refuses to
                read it as ``False``, when a sampled value is missing, when a
                ``ratio_z`` divisor is zero, or when a published field has no
                value on this bar. The refusal carries the fields that were
                already evaluated in :attr:`FieldEvalError.values`, so a caller
                can ask its own gate about them instead of matching on the
                message.
        """
        values: dict[str, FieldValue] = {}
        try:
            for spec in self._document.fields:
                values[spec.name] = self._evaluate(spec, bar, values)
            published = self._publish(bar, values)
        except FieldEvalError as exc:
            raise FieldEvalError(str(exc), values=values) from exc
        return EvaluatedBar(bar=bar, values=values, published=published)

    def warm(self, bar: FieldBar) -> None:
        """Advance the FRAME-WIDE window indicators and evaluate nothing.

        This is the bar the witness reads but never decides on. ``shared/backtest
        /market_context_replay.py::MarketContextReplay`` precomputes ``atr`` and
        the session VWAP over the *whole* frame, and then
        :meth:`iter_contexts` yields from the 60th bar onward and additionally
        skips every bar whose session has no previous session — so the legacy
        setup's ``check()`` is never called on those bars, and its causal
        ``gated_*`` windows never sample them, while its ATR at the first
        admitted bar is nonetheless the one computed over the warmup.

        Calling :meth:`step` on such a bar instead would differ in two
        measurable ways (review of PR #1067, M2): the ``gated_*`` windows would
        hold samples the legacy never took — 88 ``hi_vol`` cells differed on a
        7-session frame — and a bar whose ATR window is not yet full would
        refuse outright, since ``usable`` combines a ``None``.

        Only the frame-wide ops advance here. The ``gated_*`` ops deliberately
        do not: not sampling them IS the behaviour being reproduced.
        """
        for vwap in self._vwap.values():
            vwap.update(bar)
        for atr in self._atr.values():
            atr.update(bar)

    # -- per-field dispatch -------------------------------------------------

    def _evaluate(
        self, spec: FieldSpec, bar: FieldBar, values: Mapping[str, FieldValue]
    ) -> FieldValue:
        op = spec.op_name
        params = spec.params

        # Bar raw values.
        if op == "bar.open":
            return bar.open
        if op == "bar.high":
            return bar.high
        if op == "bar.low":
            return bar.low
        if op == "bar.close":
            return bar.close
        if op == "bar.volume":
            return bar.volume
        if op == "session.token":
            return bar.session_token
        if op == "const":
            # A declared literal. Definite on every bar by construction, which
            # is what lets `ratio_z` use it as a divisor of 1.0 to express a
            # plain difference bit-identically (x / 1.0 == x in IEEE-754).
            return float(params["value"])
        if op == "session.minutes_since_open":
            return minutes_since_open(
                bar,
                open_hour=int(params["open_hour"]),
                open_minute=int(params["open_minute"]),
            )
        if op == "time_ge":
            cutoff: time = params["at"]  # the loader parsed it into a `time`
            return bar.ts_kst.time() >= cutoff

        # Stateful window values. These must advance on EVERY bar, so they run
        # before the generic missing-value policy below (which would otherwise
        # short-circuit a gated op and silently break its causality).
        if op == "session.vwap_typical":
            return self._vwap[spec.name].update(bar)
        if op == "atr":
            return self._atr[spec.name].update(bar)
        if spec.name in self._gated:
            gate = params["sample_when"]
            sample = _require_bool(values[gate], field=spec.name, what="sample_when")
            return self._gated[spec.name].step(
                _as_number_or_none(values[spec.inputs[0]], spec.inputs[0]),
                sample=sample,
            )

        inputs = [values[ref] for ref in spec.inputs]

        if spec.op.none_policy is NonePolicy.RESOLVE:  # permissive
            resolved = inputs[0]
            if resolved is None:
                return bool(params.get("when_missing", True))
            return _require_bool(resolved, field=spec.name, what="input")
        if spec.op.none_policy is NonePolicy.REFUSE:  # all / any / not
            flags = [
                _require_bool(value, field=spec.name, what=f"input[{index}]")
                for index, value in enumerate(inputs)
            ]
            if op == "all":
                return all(flags)
            if op == "any":
                return any(flags)
            return not flags[0]

        # Arithmetic and comparison: missing in, missing out.
        if any(value is None for value in inputs):
            return None
        numbers = [
            _as_number(value, field=spec.name, what=f"input[{index}]")
            for index, value in enumerate(inputs)
        ]
        if op == "abs":
            return abs(numbers[0])
        if op == "ratio_z":
            divisor = numbers[2]
            if divisor == 0:
                raise FieldEvalError(
                    f"{bar.ts_kst.isoformat()}: field {spec.name!r} (ratio_z) "
                    f"divides by {spec.inputs[2]!r} = 0 — the ratio is undefined"
                )
            return (numbers[0] - numbers[1]) / divisor
        if op == "between":
            return bool(params["lo"] <= numbers[0] <= params["hi"])

        # gt / ge / lt / le: rhs is the second input or the const, times mult.
        rhs = numbers[1] if len(numbers) == 2 else float(params["const"])
        if "mult" in params:
            rhs = rhs * float(params["mult"])
        left = numbers[0]
        if op == "gt":
            return bool(left > rhs)
        if op == "ge":
            return bool(left >= rhs)
        if op == "lt":
            return bool(left < rhs)
        if op == "le":
            return bool(left <= rhs)
        raise FieldEvalError(  # pragma: no cover - the loader rejects unknown ops
            f"field {spec.name!r}: op {op!r} has no evaluator"
        )

    # -- publication --------------------------------------------------------

    def _publish(
        self, bar: FieldBar, values: Mapping[str, FieldValue]
    ) -> dict[str, PublishedValue]:
        published: dict[str, PublishedValue] = {}
        for entry in self._document.publish:
            value = values[entry.field]
            if value is None:
                raise FieldEvalError(
                    f"{bar.ts_kst.isoformat()}: published field "
                    f"{entry.name!r} ({entry.field!r}) has no value on this bar"
                )
            if entry.scale is None:
                if not isinstance(value, (bool, str)):
                    raise FieldEvalError(
                        f"{bar.ts_kst.isoformat()}: published field "
                        f"{entry.name!r} is {type(value).__name__}, which needs "
                        "a scale to become an int"
                    )
                published[entry.name] = value
                continue
            number = _as_number(value, field=entry.field, what="published value")
            published[entry.name] = ROUNDING_MODES[entry.scale.rounding](
                number, entry.scale.mult
            )
        return published


def evaluate_bars(
    document: FieldsDocument, bars: Iterable[FieldBar]
) -> list[EvaluatedBar]:
    """Run *document* over *bars* with a fresh evaluator."""
    return FieldEvaluator(document).run(bars)


# ---------------------------------------------------------------------------
# Value guards
# ---------------------------------------------------------------------------


def _build_gated(spec: FieldSpec) -> GatedWindowOp:
    params = spec.params
    if spec.op_name == "gated_lag":
        return GatedLag(field=spec.name)
    window = int(params["window"])
    warmup = int(params["warmup"])
    if spec.op_name == "gated_percentile":
        return GatedPercentile(
            q=float(params["q"]), window=window, warmup=warmup, field=spec.name
        )
    gated_class = GatedMax if spec.op_name == "gated_max" else GatedMin
    return gated_class(window=window, warmup=warmup, field=spec.name)


def _require_bool(value: FieldValue, *, field: str, what: str) -> bool:
    """Return *value* as a bool, refusing a missing one.

    The one place the "``None`` is not ``False``" rule bites: a boolean
    combinator, or a ``sample_when`` gate, that is handed a value which does not
    exist yet is a declaration bug, not a false condition.
    """
    if value is None:
        raise FieldEvalError(
            f"field {field!r}: {what} has no value on this bar; a missing value "
            "is not False — resolve it with 'permissive' first"
        )
    if not isinstance(value, bool):
        raise FieldEvalError(
            f"field {field!r}: {what} is {type(value).__name__}, not bool"
        )
    return value


def _as_number(value: Any, *, field: str, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FieldEvalError(
            f"field {field!r}: {what} is {type(value).__name__}, not a number"
        )
    return float(value)


def _as_number_or_none(value: FieldValue, field: str) -> float | None:
    if value is None:
        return None
    return _as_number(value, field=field, what="input[0]")


__all__ = [
    "EvaluatedBar",
    "FieldEvaluator",
    "FieldValue",
    "PublishedValue",
    "evaluate_bars",
]
