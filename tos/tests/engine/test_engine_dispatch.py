"""§7.2-4 — the dispatch key is **structurally derived**, and ∅ is handled both ways (§3.3/§6).

The design's target: *"키↔전략 선언 instrument 불일치 등록 거부·event↔strategy instrument 불일치 무평가"*.

``TargetSpec``'s scope fields are literal strings, so one strategy targets one hard-coded
(account, instrument) pair. The key therefore comes **out of the artifact**, never out of a
registrant's assertion — the series' "구조 파생 > 자기신고" discipline. Registration is refused for a
mismatching asserted key, for a ``None`` (wildcard) scope, for a strategy declaring more than one
scope, and for a strategy declaring none.

The ∅ discipline is asserted **both ways** (the #17/#26 vacuity defect class): a *missing* key is
fail-closed and evaluates nothing, while a key declared with *zero* strategies is a defined
no-action. Collapsing either into the other is the defect.

The third leg of the agreement — the Capsule's own declared scope — is asserted too, so
"event says X, strategy says X, capsule says Y" cannot evaluate.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.dsl import Decision, DecisionKind, DecisionPolicy
from tos.engine import (
    AdmissionVerdict,
    DispatchResolution,
    HaltReason,
    InstrumentKey,
    RegistrationRefused,
    StrategyRegistry,
    declared_target_scopes,
    derive_instrument_key,
    strategy_admissible,
)

from ._engine_fixtures import (
    ACCOUNT,
    DECISION_CLASS,
    INSTRUMENT,
    RecordingTransmit,
    authored_config,
    build_core,
    capsule_gated_policy,
    decision_tick,
    instrument_key,
    issue_capsule,
    issue_strategy,
    registry_with,
)


def test_the_key_is_derived_from_the_strategys_own_declared_scope() -> None:
    """(§7.2-4) Registration derives the key from the artifact, not from the caller."""
    strategy = issue_strategy()
    assert declared_target_scopes(strategy) == ((ACCOUNT, INSTRUMENT),)
    key, reasons = derive_instrument_key(strategy)
    assert reasons == ()
    assert key == InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)

    registry = StrategyRegistry()
    entry = registry.register(strategy, authored_config())
    assert entry.instrument_key == key


def test_an_asserted_key_that_disagrees_with_the_declaration_is_refused() -> None:
    """(§7.2-4) "the registry says X but the strategy targets Y" is unconstructable."""
    registry = StrategyRegistry()
    with pytest.raises(RegistrationRefused, match="does not match the scope"):
        registry.register(
            issue_strategy(),
            authored_config(),
            key=InstrumentKey(account=ACCOUNT, instrument="NQ"),
        )
    assert registry.resolve(instrument_key()).resolution is DispatchResolution.MISSING


@pytest.mark.parametrize(
    ("account", "instrument"),
    [(None, INSTRUMENT), (ACCOUNT, None), (None, None)],
)
def test_a_wildcard_none_scope_is_refused_at_registration(account, instrument) -> None:
    """(§3.3 MINOR-1) A ``None`` scope cannot be keyed — the RFC-003 §9:279-283 dispatch mirror."""
    strategy = issue_strategy(capsule_gated_policy(account=account, instrument=instrument))
    result = strategy_admissible(strategy)
    assert result.verdict is AdmissionVerdict.INADMISSIBLE
    assert any("wildcard" in reason for reason in result.reasons)
    with pytest.raises(RegistrationRefused):
        StrategyRegistry().register(strategy, authored_config())


@pytest.mark.parametrize("token", ["*", "ALL", "latest", "ES*"])
def test_a_wildcard_token_scope_is_not_a_usable_key(token) -> None:
    """(§3.3) A "*"/"ALL"/"latest" scope is refused too — the tokens are reused from tos.dsl."""
    with pytest.raises(ValidationError, match="wildcard"):
        InstrumentKey(account=ACCOUNT, instrument=token)


def test_a_strategy_declaring_two_scopes_has_no_single_key() -> None:
    """(§3.3) Slice #1 dispatch is per-instrument; two declared scopes are unkeyable."""
    first = capsule_gated_policy()
    second = capsule_gated_policy(instrument="NQ")
    merged = DecisionPolicy(rules=first.rules + second.rules, default=first.default)
    strategy = issue_strategy(merged)
    key, reasons = derive_instrument_key(strategy)
    assert key is None
    assert any("distinct" in reason for reason in reasons)
    with pytest.raises(RegistrationRefused):
        StrategyRegistry().register(strategy, authored_config())


def test_a_strategy_declaring_no_target_has_no_key() -> None:
    """(§3.3) A policy of pure no-actions declares no scope and is undispatchable."""
    policy = DecisionPolicy(
        rules=(), default=Decision(kind=DecisionKind.NO_ACTION, rationale="always hold")
    )
    strategy = issue_strategy(policy)
    key, reasons = derive_instrument_key(strategy)
    assert key is None
    assert any("no TargetSpec scope" in reason for reason in reasons)


def test_an_event_for_another_instrument_evaluates_nothing() -> None:
    """(§7.2-4) An event key with no registry entry is fail-closed — nothing is evaluated."""
    transmit = RecordingTransmit()
    core, sink = build_core(transmit=transmit)
    other = InstrumentKey(account=ACCOUNT, instrument="NQ")
    result = core.handle(decision_tick(sequence=1, key=other))

    assert result.halt_reason is HaltReason.REGISTRY_MISSING
    assert result.pipeline is None
    assert transmit.attempts == []


def test_a_missing_key_and_an_explicitly_empty_key_are_distinguished() -> None:
    """(§6 ∅ both ways) MISSING is fail-closed; EXPLICIT_EMPTY is a defined no-action."""
    registry = StrategyRegistry()
    assert registry.resolve(instrument_key()).resolution is DispatchResolution.MISSING

    registry.declare_key(instrument_key())
    dispatch = registry.resolve(instrument_key())
    assert dispatch.resolution is DispatchResolution.EXPLICIT_EMPTY
    assert dispatch.entries == ()

    registry.register(issue_strategy(), authored_config())
    assert registry.resolve(instrument_key()).resolution is DispatchResolution.DISPATCHED


def test_an_explicitly_empty_key_records_its_own_halt_reason() -> None:
    """(§6) The two ∅ shapes reach the evidence sink under **different** reasons."""
    empty_registry = StrategyRegistry()
    empty_registry.declare_key(instrument_key())
    core, _ = build_core(registry=empty_registry, transmit=RecordingTransmit())
    result = core.handle(decision_tick(sequence=1))
    assert result.halt_reason is HaltReason.REGISTRY_EXPLICIT_EMPTY

    missing_core, _ = build_core(registry=StrategyRegistry(), transmit=RecordingTransmit())
    missing_result = missing_core.handle(decision_tick(sequence=1))
    assert missing_result.halt_reason is HaltReason.REGISTRY_MISSING
    assert HaltReason.REGISTRY_EXPLICIT_EMPTY is not HaltReason.REGISTRY_MISSING


def test_a_capsule_scoped_to_another_instrument_evaluates_nothing() -> None:
    """(§3.3 삼자 일치) The Capsule's own declared scope is the third leg of the agreement."""
    from tos.capsule.capsule import CapsuleScope

    mismatched = issue_capsule(
        scope=CapsuleScope(
            environment="non-live-test",
            account=ACCOUNT,
            instrument="NQ",
            decision_class=DECISION_CLASS,
        )
    )
    transmit = RecordingTransmit()
    core, _ = build_core(registry=registry_with(), transmit=transmit)
    result = core.handle(decision_tick(sequence=1, capsule=mismatched))

    assert result.halt_reason is HaltReason.CAPSULE_SCOPE_MISMATCH
    assert transmit.attempts == []


def test_declared_keys_reports_declared_but_empty_scopes() -> None:
    """A declared-empty key is visible in the registry's own key list (∅ is explicit)."""
    registry = StrategyRegistry()
    registry.declare_key(instrument_key())
    assert registry.declared_keys() == (instrument_key(),)
