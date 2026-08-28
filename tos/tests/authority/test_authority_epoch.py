"""Authority epoch currentness / fence + coordinate non-collapse (§5.1; §4.3/§4.7).

Any-None coordinate or domain mismatch or stale epoch FENCES (fail-closed); and — the
central §4.7 canary — a value from a *different* generation coordinate (Writer Epoch)
placed in the Safety Authority epoch slot never satisfies the fence, because the two
coordinates carry distinct floors (SA-EV-001/002/014 substrate; SA-INV-002).
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.authority import (
    AuthorityEpochState,
    GenerationVector,
    authority_epoch_current,
    authority_epoch_fenced,
)

from ._authority_strategies import epoch_state


def test_current_epoch_not_fenced() -> None:
    """A claim matching the domain at/above the floor is current (guard not const-False)."""
    state = epoch_state(authority_domain="acct-1", current_epoch_floor=5)
    assert authority_epoch_current(5, "acct-1", state) is True
    assert authority_epoch_current(9, "acct-1", state) is True
    assert authority_epoch_fenced(9, "acct-1", state) is False


@given(
    field=st.sampled_from(
        ["claimed_epoch", "authority_domain", "floor", "state_domain"]
    )
)
def test_any_none_coordinate_is_fenced(field: str) -> None:
    """(canary) Any None coordinate => FENCED (vacuous-admit forbidden, §5.1)."""
    claimed: int | None = 5
    domain: str | None = "acct-1"
    state = epoch_state(authority_domain="acct-1", current_epoch_floor=5)
    if field == "claimed_epoch":
        claimed = None
    elif field == "authority_domain":
        domain = None
    elif field == "floor":
        state = AuthorityEpochState(authority_domain="acct-1", current_epoch_floor=None)
    else:
        state = AuthorityEpochState(authority_domain=None, current_epoch_floor=5)
    assert authority_epoch_current(claimed, domain, state) is False
    assert authority_epoch_fenced(claimed, domain, state) is True


@given(epoch=st.integers(min_value=0, max_value=4))
def test_stale_epoch_below_floor_is_fenced(epoch: int) -> None:
    """A claimed epoch below the monotone floor is always FENCED (§5.2; SA-INV-002)."""
    state = epoch_state(authority_domain="acct-1", current_epoch_floor=5)
    assert authority_epoch_current(epoch, "acct-1", state) is False


def test_domain_mismatch_is_fenced() -> None:
    """A claim for a different authority domain is FENCED (§5.1 domain scoping)."""
    state = epoch_state(authority_domain="acct-1", current_epoch_floor=5)
    assert authority_epoch_current(9, "acct-2", state) is False


def test_guard_fires_both_ways() -> None:
    """The predicate is neither constant-True nor constant-False (guard fires)."""
    state = epoch_state(authority_domain="acct-1", current_epoch_floor=5)
    fenced = authority_epoch_current(4, "acct-1", state)
    passes = authority_epoch_current(5, "acct-1", state)
    assert fenced is False and passes is True


def test_coordinate_non_collapse_writer_epoch_cannot_satisfy_sa_fence() -> None:
    """(canary §4.3/§4.7) A Writer-Epoch value in the SA-epoch slot never satisfies the fence.

    The generation coordinates have DISTINCT floors: the Safety Authority epoch floor is
    10 while the Writer Epoch is 3. Substituting the Writer-Epoch coordinate's value as a
    claimed Safety Authority epoch (coordinate collapse) is fenced (3 < 10), whereas the
    genuine Safety Authority epoch (11) is current — proving the two coordinates are not
    interchangeable (§27 OQ2 "without collapsing authority separation").
    """
    gv = GenerationVector(safety_authority_epoch=11, writer_epoch=3)
    sa_state = epoch_state(authority_domain="acct-1", current_epoch_floor=10)

    # The genuine Safety Authority epoch coordinate is current.
    assert (
        authority_epoch_current(gv.safety_authority_epoch, "acct-1", sa_state) is True
    )
    # Collapsing the Writer Epoch coordinate into the SA-epoch slot is FENCED.
    assert authority_epoch_current(gv.writer_epoch, "acct-1", sa_state) is False


def test_generation_vector_coordinates_are_distinct_fields() -> None:
    """The 9 §4.7 generation coordinates are distinct fields (no single collapsed epoch)."""
    fields = set(GenerationVector.model_fields)
    for coordinate in (
        "safety_authority_epoch",
        "writer_epoch",
        "membership_generation",
        "restore_generation",
        "recovery_generation",
        "time_health_generation",
        "process_generation",
        "hard_safety_envelope_generation",
        "runtime_safety_profile_generation",
    ):
        assert coordinate in fields
