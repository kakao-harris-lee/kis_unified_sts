"""The slice runs the RFC-008 §10-conformant path — and could not run the other one.

The DSL spike reached market numbers through ``EvaluationConfig.bindings``, which is the
relabelling RFC-008 §10:327-331 and RFC-004 §9:251-252 prohibit: "a market-derived value
carried as an authored constant". Slice #1's whole point is that the value now arrives as an
**admitted, attributed Critical Input** instead.

That claim is asserted three ways, because a claim of *absence* needs more than a claim of
presence (the #27 anti-phantom lesson — a negative must be grepped, not asserted):

1. **structurally** — every operand the shipped policy gates on is a ``"capsule"``-sourced
   ``ref``, and the authored ``bindings`` mapping is empty, so there is no config key a market
   value could hide in;
2. **mechanically** — a negative grep over this suite's own sources shows no
   ``("config", …)`` operand path anywhere;
3. **counterfactually** — the same band logic routed through ``config`` is refused by the
   shipped typed-admission gate, and the value surface is shown to be *load-bearing* by
   removing it and watching every decision collapse to No-Action.

⚠ Authoring evidence; closes no EV.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.backtest import ProvisionalContextResolver, resolved_value_surface_absent
from tos.dsl import (
    VALUE_NAMESPACE,
    AuthoredStrategy,
    Compare,
    CompareOp,
    Decision,
    DecisionKind,
    DecisionPolicy,
    Operand,
    Rule,
    TargetKind,
    TargetSpec,
)
from tos.engine import (
    ADMISSIBLE_EVENT_KINDS,
    CAPSULE_CONTEXT_SOURCE,
    CONFIG_CONTEXT_SOURCE,
    AdmissionVerdict,
    HaltReason,
    RegistrationRefused,
    StrategyRegistry,
    compare_has_capsule_operand,
    iter_outcome_gating_compares,
    operand_source,
    strategy_admissible,
)
from tos.marketfeed import ValueViewDisposition

from ._slice_fixtures import (
    ACCOUNT,
    INSTRUMENT,
    LOWER_BAND,
    SCHEME,
    UPPER_BAND,
    BandBarBook,
    authored_config,
    band_reversion_policy,
    band_reversion_strategy,
    build_resolver,
    instrument_key,
    run_slice,
)

# ---------------------------------------------------------------------------
# 1 — structural: the values arrive under the capsule source, and only there
# ---------------------------------------------------------------------------


def test_every_outcome_gating_operand_reads_the_capsule_value_namespace() -> None:
    """(RFC-008 §10:327-331) Both guards compare two capsule-sourced Critical Input values."""
    policy = band_reversion_policy()
    compares = tuple(iter_outcome_gating_compares(policy))
    assert len(compares) == 2

    for compare in compares:
        assert compare_has_capsule_operand(compare)
        for operand in (compare.left, compare.right):
            # ★ not merely "at least one capsule operand" — *every* operand here is one, so the
            #   band comparison cannot be half-sourced from an authored constant.
            assert operand.const is None
            assert operand_source(operand) == CAPSULE_CONTEXT_SOURCE
            assert operand.ref is not None
            assert operand.ref[1] == VALUE_NAMESPACE
            assert operand.ref[2] in {"close", "lower_band", "upper_band"}


def test_the_authored_configuration_carries_no_bindings_at_all() -> None:
    """(design #31 §3.2 (2)) There is no config key for a market value to hide in."""
    config = authored_config()
    assert config.bindings == {}


def test_the_value_namespace_is_disjoint_from_every_capsule_top_level_key() -> None:
    """(design #32 §3.2 (1)) The merge cannot overwrite covered Capsule content."""
    book = BandBarBook()
    for context in book.contexts:
        assert VALUE_NAMESPACE not in context.capsule.model_dump(mode="json")


# ---------------------------------------------------------------------------
# 2 — mechanical: the negative grep (anti-phantom — an absence is measured)
# ---------------------------------------------------------------------------


def _slice_sources() -> tuple[tuple[str, str], ...]:
    """Every ``.py`` file of this suite, as ``(name, text)``."""
    here = Path(__file__).resolve().parent
    return tuple(
        (path.name, path.read_text(encoding="utf-8")) for path in sorted(here.glob("*.py"))
    )


def test_no_config_sourced_operand_path_appears_anywhere_in_this_suite() -> None:
    """(anti-phantom) The config channel's absence is grepped, not asserted in prose."""
    sources = _slice_sources()
    assert len(sources) >= 4, "the negative grep must actually see this suite's files"
    for name, text in sources:
        for forbidden in (
            f'ref=("{CONFIG_CONTEXT_SOURCE}"',
            f"ref=('{CONFIG_CONTEXT_SOURCE}'",
            f'("{CONFIG_CONTEXT_SOURCE}", "close"',
            f'("{CONFIG_CONTEXT_SOURCE}", "lower_band"',
            f'("{CONFIG_CONTEXT_SOURCE}", "upper_band"',
        ):
            if name == Path(__file__).name:
                continue  # this file names the forbidden shapes in order to forbid them
            assert forbidden not in text, f"{name} routes a value through the config channel"


def test_the_grep_would_actually_fire() -> None:
    """(canary of the canary) A config-sourced ref really is matched by the pattern above."""
    offender = 'Operand(ref=("config", "close"))'
    assert f'ref=("{CONFIG_CONTEXT_SOURCE}"' in offender


# ---------------------------------------------------------------------------
# 3 — counterfactual: the other path is refused, and this one is load-bearing
# ---------------------------------------------------------------------------


def _config_relabelled_policy() -> DecisionPolicy:
    """The same band logic with the market values relabelled as configuration (the escape)."""
    entry = Decision(
        kind=DecisionKind.ACTION,
        rationale="config-relabelled band entry",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            rationale="config-relabelled band entry",
        ),
    )
    hold = Decision(kind=DecisionKind.NO_ACTION, rationale="hold")
    relabelled = Rule(
        all_of=(
            Compare(
                left=Operand(ref=(CONFIG_CONTEXT_SOURCE, "close")),
                op=CompareOp.LT,
                right=Operand(ref=(CONFIG_CONTEXT_SOURCE, "lower_band")),
            ),
        ),
        decision=entry,
    )
    return DecisionPolicy(rules=(relabelled,), default=hold)


def test_the_config_relabelled_twin_is_refused_by_typed_admission() -> None:
    """(design #31 §3.2 (3)) Routing the band through ``config`` is INADMISSIBLE."""
    issued = AuthoredStrategy.issue(
        scheme=SCHEME,
        dsl_version="dsl-slice",
        config_binding_version="cfg-bind-slice",
        policy=_config_relabelled_policy(),
    )
    assert isinstance(issued, AuthoredStrategy)
    admission = strategy_admissible(issued)
    assert admission.verdict is AdmissionVerdict.INADMISSIBLE
    assert any("capsule-sourced operand" in reason for reason in admission.reasons)

    registry = StrategyRegistry()
    with pytest.raises(RegistrationRefused):
        registry.register(issued, authored_config())

    # …while the slice's own strategy registers.
    StrategyRegistry().register(band_reversion_strategy(), authored_config())


def test_without_the_value_surface_every_decision_collapses_to_no_action() -> None:
    """The load-bearing test: remove D-E2 and the band strategy proposes nothing.

    Injecting D-E3's :class:`~tos.backtest.ProvisionalContextResolver` — which resolves *no*
    value, by design (design #33 §3.5 "the mechanism runs, the decision starves") — leaves every
    value operand ``UNKNOWN``, every comparison ``False``, and therefore the mandatory default.
    Nothing is ordered. That is RFC-008 §10:347-350's "the action set can only narrow" observed
    end to end, and it is the proof that the resolved values, not something else, drove the
    positive run.
    """
    provisional = ProvisionalContextResolver()
    starved = run_slice(resolver=provisional)

    assert starved.slot.handoffs == ()
    assert starved.transport.requests == ()
    assert starved.gateway.results == ()
    assert starved.gateway.verifications == ()
    assert starved.run.handoff_count == 0
    for index in range(len(starved.book.contexts)):
        result = starved.result_for(index)
        assert result.halt_reason is HaltReason.NO_ACTION_OUTCOME
        assert result.pipeline is not None
        assert result.pipeline.proposal is None
        assert result.pipeline.signature is not None
        # no value view ⇒ the signature carries the snapshot pointer alone.
        assert len(result.pipeline.signature.captured_external_value_refs) == 1

    # and the provisional resolver's own honesty predicate agrees about why.
    book = BandBarBook()
    payload = provisional(book.context_for(0).capsule, instrument_key=instrument_key())
    assert payload.value_view is None
    assert resolved_value_surface_absent(payload) is True


def test_a_refused_snapshot_binding_starves_the_decision_rather_than_substituting() -> None:
    """(ADR-002-018 §15:386) A store that cannot resolve the reference publishes no view."""

    def empty_store(*, snapshot_id: str | None, canonical_digest: str | None) -> None:
        del snapshot_id, canonical_digest
        return None

    book = BandBarBook()
    resolver = build_resolver(book)
    # rebuild the resolver over a store that resolves nothing — everything else identical.
    from tos.marketfeed import MarketFeedContextResolver

    starving = MarketFeedContextResolver(
        snapshot_store=empty_store,
        candidate_source=book.candidate_source,
        scheme=SCHEME,
    )
    resolved = starving.resolve(book.context_for(0).capsule, instrument_key=instrument_key())
    assert resolved.resolution.disposition is ValueViewDisposition.SNAPSHOT_UNRESOLVED
    assert resolved.payload.value_view is None
    assert resolved.value_surface_published is False

    # the healthy resolver over the same Capsule does publish — so the difference is the store.
    healthy = resolver.resolve(book.context_for(0).capsule, instrument_key=instrument_key())
    assert healthy.value_surface_published is True


def test_the_band_values_the_policy_compared_are_the_ones_the_snapshot_covers() -> None:
    """The end of the chain: the number the DSL saw is the number behind the covered digest."""
    book = BandBarBook()
    resolver = build_resolver(book)
    for context in book.contexts:
        view = resolver.resolve(
            context.capsule, instrument_key=instrument_key()
        ).payload.value_view
        assert view is not None
        by_key = {value.field_key: value for value in view.values}
        assert by_key["close"].value == context.close
        assert by_key["lower_band"].value == LOWER_BAND
        assert by_key["upper_band"].value == UPPER_BAND
        for value in view.values:
            # the provenance pointer is the observation's own covered payload digest.
            assert value.payload_digest == context.snapshot.observations[0].raw.payload_digest
            assert value.observation_ref == context.snapshot.observations[0].raw.raw_event_id
            assert value.as_of == context.snapshot.observations[0].time.source_event_time


def test_the_event_vocabulary_stayed_closed_across_the_slice() -> None:
    """(design #31 §2.2) Only the two admissible kinds ever entered the core."""
    sliced = run_slice()
    kinds = {entry.event_kind for entry in sliced.run.trace.entries}
    assert kinds <= ADMISSIBLE_EVENT_KINDS
