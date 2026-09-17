"""``tos_runtime.compose._nontrade_eval_dispatch`` — the ``nontrade-eval`` subcommand's own YAML
loader + dispatch, split out of ``cli.py`` purely for that module's own size budget
(``tools/tos_size_budget.py`` — module ceiling 1000 lines); no behavioural difference from
having this inline there (the SAME "split purely for size budget" discipline
:mod:`~tos_runtime.compose._types`/:mod:`~tos_runtime.compose._run_dispatch` already document
for themselves). ``cli.py`` imports :func:`dispatch_nontrade_eval` under its private
(``_``-prefixed) name, so this split is invisible to anything outside this package.

``nontrade-eval --observation <path>`` is a pure, stateless dry run (runtime operations wiring
plan, 2026-09-13, §2 decision 7): it loads a
:class:`~tos_runtime.nontrade.observations.NonTradeObservation` from a YAML file (a small,
scalar-fields-only loader local to this module — the nested kernel records
``transition_envelope``/``split_spec``/``correction``/``prior_correction`` are refused rather
than silently dropped if present, a future wave's own loader) and folds it through
:meth:`~tos_runtime.nontrade.processor.NonTradeEventProcessor.evaluate` (that method's own
docstring: "a DRY RUN: records no evidence and touches no durable state"), printing the
disposition + per-predicate result table. Opens no store, no custody, no inbox — genuinely zero
evidence reaches any real durable store.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``pyyaml`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from tos.nontrade import NonTradeEventClass

from tos_runtime.nontrade.observations import NonTradeObservation
from tos_runtime.nontrade.processor import NonTradeEventProcessor

if TYPE_CHECKING:
    # TYPE_CHECKING-only: `cli.py` imports THIS module, so a top-level import here would be
    # circular — the SAME pattern `_run_dispatch.py` already uses for `Args`.
    from tos_runtime.compose.cli import NontradeEvalArgs

__all__ = [
    "NontradeObservationLoadError",
    "dispatch_nontrade_eval",
]

#: ``NonTradeObservation`` fields this CLI's YAML loader accepts directly (scalar/simple types
#: only — module docstring). ``event_class`` is handled separately (enum conversion);
#: ``change_triggers``/``field_confidences`` are handled separately (frozenset conversion);
#: ``injected_worst_intermediate_risk`` is handled separately (Decimal conversion).
_NONTRADE_SCALAR_FIELDS = (
    "observation_id",
    "source_label",
    "event_subtype",
    "workflow_generation",
    "idempotency_key",
    "supersedes_ref",
    "announcement_time",
    "observation_time",
    "record_time",
    "ex_time",
    "effective_time",
    "payable_time",
    "settlement_time",
    "old_instrument_identity",
    "new_instrument_identity",
    "identity_transition_final",
    "original_retained",
    "event_is_material",
    "earliest_credible_boundary",
    "latest_completion_boundary",
    "source_disagreement_bounded",
    "protective_action_may_proceed",
    "injected_credible_space_bounded",
    "injected_union_capacity_known",
)

#: The three nested kernel records :class:`~tos_runtime.nontrade.observations.NonTradeObservation`
#: can carry (``transition_envelope``/``split_spec``/``correction``/``prior_correction``) have no
#: loader here yet — refused rather than silently dropped (module docstring's own "a future wave's
#: own loader" note).
_NONTRADE_UNSUPPORTED_NESTED_FIELDS = (
    "transition_envelope",
    "split_spec",
    "correction",
    "prior_correction",
)


class NontradeObservationLoadError(Exception):
    """Raised by :func:`_load_nontrade_observation` on any refusal."""


def _load_nontrade_observation(path: Path) -> NonTradeObservation:
    """Load a :class:`~tos_runtime.nontrade.observations.NonTradeObservation` from a YAML file
    (module docstring — scalar fields only)."""
    try:
        raw_text = path.read_text()
    except OSError as exc:
        raise NontradeObservationLoadError(f"cannot read {path}: {exc}") from exc
    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise NontradeObservationLoadError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise NontradeObservationLoadError(
            f"{path} must parse to a mapping (got {type(raw).__name__})"
        )
    unsupported = [
        name
        for name in _NONTRADE_UNSUPPORTED_NESTED_FIELDS
        if raw.get(name) is not None
    ]
    if unsupported:
        raise NontradeObservationLoadError(
            f"{path}: field(s) {unsupported} are not supported by this CLI's YAML loader "
            "yet (nested kernel records need a dedicated loader a future wave adds) — "
            "omit them or leave them null"
        )
    kwargs: dict[str, Any] = {
        name: raw[name] for name in _NONTRADE_SCALAR_FIELDS if name in raw
    }
    if raw.get("event_class") is not None:
        try:
            kwargs["event_class"] = NonTradeEventClass(raw["event_class"])
        except ValueError as exc:
            raise NontradeObservationLoadError(
                f"{path}: 'event_class'={raw['event_class']!r} is not a valid "
                f"NonTradeEventClass: {exc}"
            ) from exc
    for name in ("change_triggers", "field_confidences"):
        if raw.get(name) is not None:
            kwargs[name] = frozenset(raw[name])
    if raw.get("injected_worst_intermediate_risk") is not None:
        try:
            kwargs["injected_worst_intermediate_risk"] = Decimal(
                str(raw["injected_worst_intermediate_risk"])
            )
        except InvalidOperation as exc:
            raise NontradeObservationLoadError(
                f"{path}: 'injected_worst_intermediate_risk'="
                f"{raw['injected_worst_intermediate_risk']!r} is not a valid decimal: {exc}"
            ) from exc
    try:
        return NonTradeObservation(**kwargs)
    except TypeError as exc:
        raise NontradeObservationLoadError(
            f"{path}: missing or unexpected field(s): {exc}"
        ) from exc


def dispatch_nontrade_eval(args: NontradeEvalArgs) -> int:
    """The ``nontrade-eval`` subcommand's own dispatch — a pure dry run (module docstring):
    opens no store, no custody, appends zero evidence anywhere real."""
    try:
        observation = _load_nontrade_observation(args.observation)
    except NontradeObservationLoadError as exc:
        print(f"nontrade-eval: refused — {exc}", file=sys.stderr)
        return 1

    processor = NonTradeEventProcessor(required_legs_by_class={})
    outcome = processor.evaluate(observation)

    disposition_str = (
        outcome.disposition.value if outcome.disposition is not None else None
    )
    print(
        f"nontrade-eval: disposition={disposition_str} "
        f"restrictive={outcome.restrictive} latch_reason={outcome.latch_reason}"
    )
    print("nontrade-eval: predicates:")
    for name, value in outcome.predicate_results.items():
        print(f"  {name}: {value}")
    if outcome.unevaluated:
        print(f"nontrade-eval: unevaluated: {list(outcome.unevaluated)}")
    print(
        "nontrade-eval: dry run only — no --data-dir/--custody-root was opened, so zero "
        "evidence was appended to any real store."
    )
    return 0
