"""Replay divergence + baseline binding — ERI-EV-007/008 (design #4 §6).

``compute_replay_result`` is never ``MATCH`` if any of {unsupported baseline,
missing/corrupt input, digest mismatch, schema incompatibility, unbounded
nondeterminism} holds (ERI-INV-009). Baseline binding is exact: a changed
baseline yields UNSUPPORTED_BASELINE and can never PASS (ERI-EV-008). Isolation
and result-authority flags are forced false.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from tos.evidence import (
    ReplayResultState,
    compute_replay_result,
    reevaluation_is_distinct_named_result,
    replay_baseline_supported,
)
from tos.evidence.replay import ReplayBaseline, ReplayIsolation, ReplayResult

from ._evidence_strategies import issue_replay

_ALL_GOOD = {
    "baseline_supported": True,
    "input_complete": True,
    "schema_compatible": True,
    "nondeterminism_bounded": True,
    "expected_state_digest": "s",
    "actual_state_digest": "s",
}


def test_all_good_is_match() -> None:
    """When everything holds and digests agree, the result is MATCH."""
    assert compute_replay_result(**_ALL_GOOD) is ReplayResultState.MATCH


def test_unsupported_baseline_never_match() -> None:
    """An unsupported baseline yields UNSUPPORTED_BASELINE, never MATCH (§6.2)."""
    result = compute_replay_result(**{**_ALL_GOOD, "baseline_supported": False})
    assert result is ReplayResultState.UNSUPPORTED_BASELINE


def test_missing_input_never_match() -> None:
    """A missing/corrupt input yields CORRUPT_INPUT, never MATCH (§6.1)."""
    result = compute_replay_result(**{**_ALL_GOOD, "input_complete": False})
    assert result is ReplayResultState.CORRUPT_INPUT


def test_digest_mismatch_diverges() -> None:
    """A safety-relevant digest mismatch yields DIVERGED (§6.1)."""
    result = compute_replay_result(**{**_ALL_GOOD, "actual_state_digest": "other"})
    assert result is ReplayResultState.DIVERGED


def test_unbounded_nondeterminism_never_match() -> None:
    """Unbounded nondeterminism can never be MATCH, even if digests agree (§2.5 D)."""
    result = compute_replay_result(**{**_ALL_GOOD, "nondeterminism_bounded": False})
    assert result is not ReplayResultState.MATCH


def test_schema_incompatibility_never_match() -> None:
    """Schema incompatibility can never be MATCH (§6.1)."""
    result = compute_replay_result(**{**_ALL_GOOD, "schema_compatible": False})
    assert result is not ReplayResultState.MATCH


@given(
    baseline_ok=st.booleans(),
    input_ok=st.booleans(),
    schema_ok=st.booleans(),
    nondet_ok=st.booleans(),
    digests_agree=st.booleans(),
)
def test_match_iff_everything_holds(
    baseline_ok: bool,
    input_ok: bool,
    schema_ok: bool,
    nondet_ok: bool,
    digests_agree: bool,
) -> None:
    """Property: result is MATCH iff every condition holds AND digests agree (§6.1)."""
    result = compute_replay_result(
        baseline_supported=baseline_ok,
        input_complete=input_ok,
        schema_compatible=schema_ok,
        nondeterminism_bounded=nondet_ok,
        expected_state_digest="s",
        actual_state_digest="s" if digests_agree else "t",
    )
    should_match = (
        baseline_ok and input_ok and schema_ok and nondet_ok and digests_agree
    )
    assert (result is ReplayResultState.MATCH) is should_match


def test_not_run_when_no_actual_digest() -> None:
    """No actual state digest (not run to completion) is INCONCLUSIVE, not MATCH."""
    result = compute_replay_result(**{**_ALL_GOOD, "actual_state_digest": None})
    assert result is ReplayResultState.INCONCLUSIVE


# ---- baseline binding ------------------------------------------------------


def test_exact_baseline_supported() -> None:
    """A capsule whose baseline matches an approved baseline is supported (§6.2)."""
    capsule = issue_replay(baseline=ReplayBaseline(repository_commit_sha="sha-1"))
    approved = [ReplayBaseline(repository_commit_sha="sha-1")]
    assert replay_baseline_supported(capsule, approved) is True


def test_changed_baseline_unsupported() -> None:
    """A changed baseline is unsupported => UNSUPPORTED_BASELINE, never PASS (§6.2)."""
    capsule = issue_replay(baseline=ReplayBaseline(repository_commit_sha="sha-9"))
    approved = [ReplayBaseline(repository_commit_sha="sha-1")]
    supported = replay_baseline_supported(capsule, approved)
    assert supported is False
    result = compute_replay_result(
        baseline_supported=supported,
        input_complete=True,
        schema_compatible=True,
        nondeterminism_bounded=True,
        expected_state_digest="s",
        actual_state_digest="s",
    )
    assert result is ReplayResultState.UNSUPPORTED_BASELINE


# ---- isolation + result authority forced false -----------------------------


def test_isolation_live_flag_unconstructable() -> None:
    """A true live-reachability flag makes the isolation block unconstructable (§6.3)."""
    with pytest.raises(ValidationError):
        ReplayIsolation(live_broker_route_reachable=True)


def test_result_authority_flag_unconstructable() -> None:
    """A true result-authority flag is unconstructable (reproducibility != adequacy)."""
    with pytest.raises(ValidationError):
        ReplayResult(creates_authority=True)


def test_issued_replay_isolation_defaults_false() -> None:
    """An issued replay capsule is isolated by default (all live flags false)."""
    capsule = issue_replay()
    iso = capsule.isolation
    assert not iso.live_credentials_present
    assert not iso.live_broker_route_reachable
    assert not iso.production_mutation_endpoint_reachable
    assert not iso.live_approval_or_authorization_consumable


# ---- ERI-EV-008 current-rule re-evaluation = distinct named result ---------


def test_current_rule_reevaluation_is_distinct_named_result() -> None:
    """A current-rule re-evaluation is a distinct record, not a historical overwrite.

    ERI-EV-008 (§6.2, ADR §15 line 409): re-evaluating under current rules yields a
    distinct named result and must not supersede/overwrite the historical result.
    """
    historical = issue_replay(
        replay_capsule_id="rc-historical",
        baseline=ReplayBaseline(repository_commit_sha="commit-OLD"),
        result=ReplayResult(state=ReplayResultState.MATCH),
    )
    reevaluation = issue_replay(
        replay_capsule_id="rc-current",
        baseline=ReplayBaseline(repository_commit_sha="commit-NEW"),
        result=ReplayResult(state=ReplayResultState.DIVERGED),
    )
    assert reevaluation_is_distinct_named_result(historical, reevaluation) is True
    # Append-only: the historical capsule is frozen and its result is unchanged.
    assert historical.result.state is ReplayResultState.MATCH
    assert historical.replay_capsule_id != reevaluation.replay_capsule_id


def test_reevaluation_reusing_historical_identity_is_rejected() -> None:
    """Re-evaluating "in place" (same id / same baseline) is not a distinct result."""
    historical = issue_replay(replay_capsule_id="rc-1")
    assert reevaluation_is_distinct_named_result(historical, historical) is False
