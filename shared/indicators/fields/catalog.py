"""``tos-field-catalog/1`` — the fixed, versioned set of field operations.

Why a catalog at all
--------------------
A strategy is tenant YAML, never a Python module
(``docs/plans/2026-11-11-tos-platform-roadmap.md`` §0.1). The platform therefore
owns a *fixed and versioned* list of named operations, and a tenant's
``fields.yaml`` may only compose those (``…-tos-p2-declarative-fields.md`` §2.3).
Adding an op is a reviewed code change; using one is a config change.

Two rules this table exists to keep
-----------------------------------
1. **No strategy name in an op name.** Ops differ by parameters only (roadmap
   §5, risk 2). There is no ``setup_d_hi_vol`` here and there never will be: the
   high-vol gate is ``gated_percentile`` + a comparison with the strategy's own
   numbers in its own YAML.
2. **No free arithmetic.** An op is a fixed shape with named parameters, and its
   inputs are references to *earlier* field names — not expressions. A tenant
   cannot write ``(close - vwap) / atr``; it declares ``ratio_z`` with three
   input names. Which calculations exist is a platform decision, reviewable in
   one place.

Value kinds
-----------
Every op declares the kind of value it produces (:class:`ValueKind`), and the
kinds it accepts. That is what makes ``all(close, vwap)`` a *load-time*
refusal rather than a runtime surprise.

Missing values
--------------
A stateful op returns ``None`` while its window is shorter than its warmup
("no value yet" — never ``0``, never ``False``). :class:`NonePolicy` records,
per op, what happens when a ``None`` reaches it:

* ``PROPAGATE`` — arithmetic and comparison ops: missing in, missing out. A
  comparison **never** turns a missing value into ``False``.
* ``REFUSE`` — boolean combinators, ``sample_when`` gates and ``publish``:
  a ``None`` here is a declaration bug and raises
  :class:`~shared.indicators.fields.errors.FieldEvalError`.
* ``RESOLVE`` — ``permissive`` only: converts ``None`` into its
  ``when_missing`` constant.

So the only way a missing value can become a definite boolean is an explicit
``permissive``, which is how the legacy setup's warmup behaviour ("the gate is
PERMISSIVE during warmup, never silently dead" —
``shared/decision/setups/vwap_reversion.py::_vol_reference``) is written
declaratively.

:class:`NonePolicy` governs the STATELESS ops. A stateful (``gated_*``) op
handles its own missing input, because it must read its window on every bar to
stay causal even on a bar it does not sample — that rule lives in
:class:`~shared.indicators.fields.stateful.GatedWindowOp`, and the evaluator
dispatches those ops before it applies the policy below.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

#: Catalog version. A ``fields.yaml`` pins it and boot is refused on a mismatch
#: (``schema.py``), so a catalog change can never silently alter a shipped
#: tenant's fields.
#:
#: **When this must be bumped.** The version is compared for EQUALITY against a
#: document's ``catalog:`` key, and this module holds exactly ONE op registry —
#: there is no per-version op table, so the version gates compatibility between
#: the loaded catalog and a declaration, not "which ops version N had". That
#: makes the rule:
#:
#: * **Adding** an op does NOT bump it. Every document that loaded against the
#:   previous op set still loads and still evaluates identically: the set only
#:   grew, and a declaration cannot use an op it does not name. ``const`` was
#:   added this way (P2-b).
#: * **Removing** an op, or changing what an existing one COMPUTES or accepts,
#:   DOES bump it — those are the changes that would make an unchanged
#:   declaration mean something else, which is the whole point of the pin.
#:
#: The residual this leaves: a declaration written against the grown ``/1`` and
#: deployed against an older ``/1`` is refused by op name ("unknown op"), not by
#: the version gate. That refusal is correct and specific, so the version does
#: not need to carry it.
CATALOG_VERSION: Final[str] = "tos-field-catalog/1"


class ValueKind(Enum):
    """The kind of value a field carries."""

    NUMBER = "number"
    BOOL = "bool"
    STR = "str"


class NonePolicy(Enum):
    """What an op does with a missing (``None``) input. See the module docstring."""

    PROPAGATE = "propagate"
    REFUSE = "refuse"
    RESOLVE = "resolve"


#: Sentinel for a variadic op's maximum input count.
UNBOUNDED: Final[int] = -1


@dataclass(frozen=True)
class OpSpec:
    """One catalog operation: its shape, not its implementation.

    Attributes:
        name: Op name as a ``fields.yaml`` writes it.
        returns: Kind of value the op produces.
        accepts: Kind every input must carry (``None`` for ops with no inputs).
        min_inputs: Minimum number of input field references.
        max_inputs: Maximum number, or :data:`UNBOUNDED`.
        required_params: Parameter names that MUST be present.
        optional_params: Parameter names that MAY be present. Anything else is
            refused — a misspelled parameter must never be silently ignored.
        stateful: True when the op carries a causal window across bars.
        none_policy: What happens when a ``None`` input reaches this op.
        summary: One line, for error messages and the catalog listing.
    """

    name: str
    returns: ValueKind
    accepts: ValueKind | None
    min_inputs: int
    max_inputs: int
    required_params: frozenset[str]
    optional_params: frozenset[str]
    stateful: bool
    none_policy: NonePolicy
    summary: str

    def accepts_input_count(self, count: int) -> bool:
        """Return whether *count* input references satisfy this op's arity."""
        if count < self.min_inputs:
            return False
        return self.max_inputs == UNBOUNDED or count <= self.max_inputs

    def arity_text(self) -> str:
        """Human-readable arity, for a refusal message."""
        if self.max_inputs == UNBOUNDED:
            return f"{self.min_inputs} or more"
        if self.min_inputs == self.max_inputs:
            return str(self.min_inputs)
        return f"{self.min_inputs}..{self.max_inputs}"


def _op(
    name: str,
    *,
    returns: ValueKind,
    accepts: ValueKind | None = None,
    inputs: tuple[int, int] = (0, 0),
    required_params: tuple[str, ...] = (),
    optional_params: tuple[str, ...] = (),
    stateful: bool = False,
    none_policy: NonePolicy = NonePolicy.PROPAGATE,
    summary: str = "",
) -> OpSpec:
    return OpSpec(
        name=name,
        returns=returns,
        accepts=accepts,
        min_inputs=inputs[0],
        max_inputs=inputs[1],
        required_params=frozenset(required_params),
        optional_params=frozenset(optional_params),
        stateful=stateful,
        none_policy=none_policy,
        summary=summary,
    )


_NUM = ValueKind.NUMBER
_BOOL = ValueKind.BOOL
_STR = ValueKind.STR

#: Gated (stateful) ops share one base class and therefore one set of window
#: parameters. ``sample_when`` names a previously declared BOOL field: the
#: current bar's value enters the window only on a bar where that field is true,
#: which is what reproduces "the windows only advance on in-window bars with
#: usable inputs" (``vwap_reversion.py::check`` step 3).
_GATED_WINDOW_PARAMS: Final[tuple[str, ...]] = ("window", "warmup", "sample_when")

#: Every op of ``tos-field-catalog/1``, in the order of the plan's table §2.3.
_CATALOG: Final[tuple[OpSpec, ...]] = (
    # --- bar raw values -----------------------------------------------------
    _op("bar.open", returns=_NUM, summary="the bar's open"),
    _op("bar.high", returns=_NUM, summary="the bar's high"),
    _op("bar.low", returns=_NUM, summary="the bar's low"),
    _op("bar.close", returns=_NUM, summary="the bar's close"),
    _op("bar.volume", returns=_NUM, summary="the bar's volume"),
    _op(
        "session.token",
        returns=_STR,
        summary="opaque session identifier (the bar's KST date, ISO-8601)",
    ),
    # --- window values, defined by MarketContextReplay ----------------------
    _op(
        "session.vwap_typical",
        returns=_NUM,
        stateful=True,
        summary="session typical-price VWAP from the session's first bar to this one",
    ),
    _op(
        "atr",
        returns=_NUM,
        required_params=("period",),
        stateful=True,
        summary="partial-window ATR (the replay convention: TR seed high-low at bar 0)",
    ),
    _op(
        "session.minutes_since_open",
        returns=_NUM,
        required_params=("open_hour", "open_minute"),
        summary="elapsed minutes from the configured KST session open to this bar",
    ),
    # --- literal ------------------------------------------------------------
    _op(
        "const",
        returns=_NUM,
        required_params=("value",),
        summary="a declared finite constant, the same on every bar",
    ),
    # --- arithmetic ---------------------------------------------------------
    _op(
        "ratio_z",
        returns=_NUM,
        accepts=_NUM,
        inputs=(3, 3),
        summary="(a - b) / c",
    ),
    _op("abs", returns=_NUM, accepts=_NUM, inputs=(1, 1), summary="abs(a)"),
    # --- comparison ---------------------------------------------------------
    *(
        _op(
            name,
            returns=_BOOL,
            accepts=_NUM,
            inputs=(1, 2),
            optional_params=("const", "mult"),
            summary=f"a {symbol} rhs, where rhs = (b if given else const) * mult",
        )
        for name, symbol in (("gt", ">"), ("ge", ">="), ("lt", "<"), ("le", "<="))
    ),
    _op(
        "between",
        returns=_BOOL,
        accepts=_NUM,
        inputs=(1, 1),
        required_params=("lo", "hi"),
        summary="lo <= a <= hi",
    ),
    _op(
        "time_ge",
        returns=_BOOL,
        required_params=("at",),
        summary="the bar's KST time-of-day >= at (HH:MM or HH:MM:SS)",
    ),
    # --- boolean combination ------------------------------------------------
    _op(
        "all",
        returns=_BOOL,
        accepts=_BOOL,
        inputs=(1, UNBOUNDED),
        none_policy=NonePolicy.REFUSE,
        summary="every input is true",
    ),
    _op(
        "any",
        returns=_BOOL,
        accepts=_BOOL,
        inputs=(1, UNBOUNDED),
        none_policy=NonePolicy.REFUSE,
        summary="at least one input is true",
    ),
    _op(
        "not",
        returns=_BOOL,
        accepts=_BOOL,
        inputs=(1, 1),
        none_policy=NonePolicy.REFUSE,
        summary="the input is false",
    ),
    # --- gated (causal, stateful) -------------------------------------------
    _op(
        "gated_percentile",
        returns=_NUM,
        accepts=_NUM,
        inputs=(1, 1),
        required_params=("q", *_GATED_WINDOW_PARAMS),
        stateful=True,
        summary="q-th percentile of the past samples (None during warmup)",
    ),
    _op(
        "gated_max",
        returns=_NUM,
        accepts=_NUM,
        inputs=(1, 1),
        required_params=_GATED_WINDOW_PARAMS,
        stateful=True,
        summary="maximum of the past samples (None during warmup)",
    ),
    _op(
        "gated_min",
        returns=_NUM,
        accepts=_NUM,
        inputs=(1, 1),
        required_params=_GATED_WINDOW_PARAMS,
        stateful=True,
        summary="minimum of the past samples (None during warmup)",
    ),
    _op(
        "gated_lag",
        returns=_NUM,
        accepts=_NUM,
        inputs=(1, 1),
        required_params=("sample_when",),
        stateful=True,
        summary="the last sample before this bar (None until one exists)",
    ),
    # --- missing-value resolution -------------------------------------------
    _op(
        "permissive",
        returns=_BOOL,
        accepts=_BOOL,
        inputs=(1, 1),
        optional_params=("when_missing",),
        stateful=False,
        none_policy=NonePolicy.RESOLVE,
        summary="the input, or when_missing (default true) while it has no value",
    ),
)

#: Op name -> spec. The one lookup the loader and the evaluator share.
CATALOG: Final[dict[str, OpSpec]] = {spec.name: spec for spec in _CATALOG}

#: Ops whose window parameters the gated base class reads
#: (``shared.indicators.fields.stateful``).
GATED_OPS: Final[frozenset[str]] = frozenset(
    {"gated_percentile", "gated_max", "gated_min", "gated_lag"}
)


def op_spec(name: str) -> OpSpec:
    """Return the :class:`OpSpec` named *name*.

    Raises:
        KeyError: when no such op exists. Callers that must report a tenant's
            typo use :func:`known_op_names` for the "did you mean" list.
    """
    return CATALOG[name]


def known_op_names() -> tuple[str, ...]:
    """Every catalog op name, sorted — for refusal messages."""
    return tuple(sorted(CATALOG))


__all__ = [
    "CATALOG",
    "CATALOG_VERSION",
    "GATED_OPS",
    "UNBOUNDED",
    "NonePolicy",
    "OpSpec",
    "ValueKind",
    "known_op_names",
    "op_spec",
]
