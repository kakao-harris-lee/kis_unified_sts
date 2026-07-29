"""The engine-side D-E2 extension: ``DecisionTickPayload.value_view`` + pipeline threading (#32 §3.2).

A *new* file on purpose: every shipped ``tos/tests/engine`` test — the fourteen-package import
closure canary above all — stays byte-for-byte unedited and green, which is the sanction premise
design #32 §15.2 ③ states ("committed 테스트 파괴 0") demonstrated rather than asserted.

Three claims:

1. **the field is additive and dsl-typed** (§2.2 F1). ``value_view`` is a
   :class:`~tos.dsl.ContextValueView`, so it rides the pre-existing ``engine -> dsl`` edge
   (``records.py:28-33``) and the engine's import-closure allowlist is untouched. A
   ``tos.marketfeed`` type here would have created an ``engine -> marketfeed -> engine`` cycle.
2. **``None`` is restrictive** (§6). A tick with no view merges no namespace, so every value operand
   resolves to ``UNKNOWN`` and every comparison against it is ``False`` — the action set narrows.
3. **the pipeline threads it, and the signature moves with it** (§3.2 (3)). Two ticks over the same
   Capsule and the same strategy but different resolved values produce different outcomes *and*
   different recorded signatures. This is the D-E1 §6 Gap-1 residue closing: identical Capsule,
   distinguishable run.

Regime tag: authoring evidence only; closes no EV (design #32 §1.1).
"""

from __future__ import annotations

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION
from tos.dsl import (
    VALUE_NAMESPACE,
    Compare,
    CompareOp,
    ContextValue,
    ContextValueView,
    Decision,
    DecisionKind,
    DecisionPolicy,
    Operand,
    Rule,
    TargetKind,
    TargetSpec,
)
from tos.engine import DecisionTickPayload, RegisteredStrategy
from tos.engine.pipeline import run_decision_pipeline
from tos.engine.sink import RecordingEvidenceSink
from tos.engine.vocabulary import HaltReason

from ._engine_fixtures import (
    ACCOUNT,
    INSTRUMENT,
    SCHEME,
    admitting_time_inputs,
    authored_config,
    engine_configuration,
    instrument_key,
    issue_capsule,
    issue_strategy,
)

_CLOSE = 4_512_500


def _value_view(*, close: int = _CLOSE, digest: str = "view-0") -> ContextValueView:
    """A one-value view, digest supplied explicitly so the signature assertions are readable."""
    return ContextValueView(
        snapshot_id="cis-1",
        snapshot_canonical_digest="sd-1",
        values=(
            ContextValue(
                field_key="close",
                value=close,
                as_of=1_700_000_060_000,
                payload_digest="pay-1",
                observation_ref="raw-1",
            ),
        ),
        canonical_digest=digest,
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
    )


def _value_gated_policy(*, threshold: int) -> DecisionPolicy:
    """A policy whose guard reads a **resolved value** — a capsule-sourced ref, so admission holds."""
    action = Decision(
        kind=DecisionKind.ACTION,
        rationale="the resolved close cleared the authored threshold",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="0.7",
            rationale="the resolved close cleared the authored threshold",
        ),
    )
    return DecisionPolicy(
        rules=(
            Rule(
                all_of=(
                    Compare(
                        left=Operand(ref=("capsule", VALUE_NAMESPACE, "close")),
                        op=CompareOp.GT,
                        right=Operand(const=threshold),
                    ),
                ),
                decision=action,
            ),
        ),
        default=Decision(kind=DecisionKind.NO_ACTION, rationale="the guard did not fire — hold"),
    )


def _run(*, threshold: int, view: ContextValueView | None):
    """Run the decision pipeline for one value-gated strategy over one tick."""
    key = instrument_key()
    entry = RegisteredStrategy(
        strategy=issue_strategy(_value_gated_policy(threshold=threshold)),
        config=authored_config(),
        instrument_key=key,
    )
    payload = DecisionTickPayload(
        instrument_key=key,
        capsule=issue_capsule(),
        time=admitting_time_inputs(),
        value_view=view,
    )
    return run_decision_pipeline(
        entry=entry,
        payload=payload,
        configuration=engine_configuration(),
        scheme=SCHEME,
        sink=RecordingEvidenceSink(),
    )


# ---------------------------------------------------------------------------
# 1. The field (design #32 §2.2 F1 / §15.2 ②)
# ---------------------------------------------------------------------------


def test_the_payload_carries_the_value_surface_as_a_dsl_type() -> None:
    """(§2.2 F1 ★) A dsl type, so the engine's closure allowlist is untouched and no cycle exists."""
    annotation = str(DecisionTickPayload.model_fields["value_view"].annotation)
    assert "ContextValueView" in annotation
    assert "marketfeed" not in annotation.lower()


def test_the_field_is_additive_and_defaults_to_none() -> None:
    """(§15.2 ②) Every pre-D-E2 construction site still constructs — the field is optional."""
    assert set(DecisionTickPayload.model_fields) == {
        "instrument_key",
        "capsule",
        "time",
        "reference",
        "value_view",
    }
    payload = DecisionTickPayload(instrument_key=instrument_key(), capsule=issue_capsule())
    assert payload.value_view is None


def test_the_engine_import_closure_allowlist_is_unchanged() -> None:
    """(§15.2 ③ ★) The committed canary's own constant is read — fourteen packages, no marketfeed.

    Anti-phantom in its existence form: rather than asserting "we did not have to edit the engine
    canary", the shipped constant is imported and inspected.
    """
    from .test_engine_import_closure import _ALLOWED_TOS_PACKAGES

    assert len(_ALLOWED_TOS_PACKAGES) == 14
    assert "tos.marketfeed" not in _ALLOWED_TOS_PACKAGES


# ---------------------------------------------------------------------------
# 2. None is restrictive (design #32 §6)
# ---------------------------------------------------------------------------


def test_without_a_view_a_value_gated_guard_cannot_fire() -> None:
    """(§6, RFC-008 §10:347-350) Absence narrows: no namespace ⇒ UNKNOWN ⇒ comparison False."""
    result = _run(threshold=_CLOSE - 1, view=None)
    assert result.proposal is None
    assert result.halt_reason is HaltReason.NO_ACTION_OUTCOME


def test_an_explicit_empty_view_is_equally_restrictive_but_still_recorded() -> None:
    """(§6 ∅ 양방향) A published empty view narrows exactly as much, and still signs distinctly."""
    empty = ContextValueView(
        snapshot_id="cis-1",
        snapshot_canonical_digest="sd-1",
        canonical_digest="view-empty",
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
    )
    absent = _run(threshold=_CLOSE - 1, view=None)
    explicit = _run(threshold=_CLOSE - 1, view=empty)
    assert absent.proposal is explicit.proposal is None
    assert absent.signature is not None and explicit.signature is not None
    assert (
        explicit.signature.captured_external_value_refs
        != absent.signature.captured_external_value_refs
    ), "a published empty view is a recorded fact, not the same as no view at all"


# ---------------------------------------------------------------------------
# 3. Threading + the signature (design #32 §3.2 (3); the D-E1 Gap-1 residue)
# ---------------------------------------------------------------------------


def test_a_resolved_value_reaches_the_policy_and_decides_the_outcome() -> None:
    """(§3.2 ★ end to end) A market number, arriving as Critical Input, produces a Proposal."""
    fires = _run(threshold=_CLOSE - 1, view=_value_view())
    holds = _run(threshold=_CLOSE + 1, view=_value_view())
    assert fires.proposal is not None
    assert fires.proposal.account == ACCOUNT
    assert holds.proposal is None
    assert holds.halt_reason is HaltReason.NO_ACTION_OUTCOME


def test_the_view_digest_reaches_the_recorded_signature() -> None:
    """(§3.2 (3b) ★) The pipeline's signature carries the value view's digest."""
    result = _run(threshold=_CLOSE - 1, view=_value_view(digest="view-alpha"))
    assert result.signature is not None
    assert "view-alpha" in result.signature.captured_external_value_refs


def test_the_value_free_signature_is_unchanged() -> None:
    """(§7.2-9) A value-free tick signs exactly as it did before D-E2 — the snapshot digest only."""
    result = _run(threshold=_CLOSE - 1, view=None)
    assert result.signature is not None
    capsule = issue_capsule()
    assert result.signature.captured_external_value_refs == (
        capsule.critical_input_snapshot.canonical_digest,
    )


def test_two_ticks_over_one_capsule_are_distinguishable_by_their_values() -> None:
    """(§3.2 (3b) ★ the D-E1 Gap-1 residue) Same Capsule, different values, different signature.

    D-E1 could reproduce an outcome but could not make two *different* bars distinguishable, because
    the value surface did not exist. With the values in the signature, two runs that differ only in
    what the market did are now separable on replay.
    """
    high = _run(threshold=_CLOSE - 1, view=_value_view(close=_CLOSE, digest="view-high"))
    low = _run(threshold=_CLOSE - 1, view=_value_view(close=_CLOSE - 100, digest="view-low"))
    assert high.signature is not None and low.signature is not None
    assert (
        high.signature.capsule_canonical_digest == low.signature.capsule_canonical_digest
    ), "the Capsule is identical — only the values differ"
    assert (
        high.signature.captured_external_value_refs
        != low.signature.captured_external_value_refs
    )
    assert high.proposal is not None
    assert low.proposal is None


def test_the_same_tick_reproduces_the_same_signature_and_outcome() -> None:
    """(§1.1/§7.1) Determinism holds through the threading: no clock, no RNG, no nonce."""
    first = _run(threshold=_CLOSE - 1, view=_value_view(digest="view-alpha"))
    second = _run(threshold=_CLOSE - 1, view=_value_view(digest="view-alpha"))
    assert first.signature == second.signature
    assert first.outcome_digest == second.outcome_digest


@pytest.mark.parametrize("threshold", [_CLOSE - 1, _CLOSE + 1])
def test_the_capsule_admission_path_is_untouched_by_the_value_surface(threshold: int) -> None:
    """(§0.2) The value surface changes what a policy *reads*, not whether the Capsule admits."""
    from tos.engine.pipeline import capsule_admitted

    payload = DecisionTickPayload(
        instrument_key=instrument_key(),
        capsule=issue_capsule(),
        time=admitting_time_inputs(),
        value_view=_value_view(),
    )
    assert capsule_admitted(payload) == (None, None)
    assert _run(threshold=threshold, view=None).halt_reason is HaltReason.NO_ACTION_OUTCOME
