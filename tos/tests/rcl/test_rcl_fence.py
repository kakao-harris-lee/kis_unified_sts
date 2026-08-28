"""Writer fencing predicate (RCL design §6.1-§6.3; RCLP-EV-003 substrate).

State-machine fencing (ADR-012 §13 layer 2) as a pure predicate over injected epoch
state: stale / removed / restored / stale-revision, and — the central fail-closed
canary — any missing (``None``) coordinate FENCES.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.rcl import FenceCoordinates, WriterFenceState, writer_fenced

FLOORS = WriterFenceState(
    writer_epoch_floor=5, membership_generation=2, restore_generation=1, revision=3
)


def _coords(**overrides) -> FenceCoordinates:
    base = {
        "expected_writer_epoch": 5,
        "membership_generation": 2,
        "restore_generation": 1,
        "expected_revision": 3,
    }
    base.update(overrides)
    return FenceCoordinates(**base)


def test_current_command_not_fenced() -> None:
    """A command matching every current coordinate is NOT fenced (guard not const-True)."""
    assert writer_fenced(_coords(), FLOORS) is False


@given(
    field=st.sampled_from(
        [
            "expected_writer_epoch",
            "membership_generation",
            "restore_generation",
            "expected_revision",
        ]
    )
)
def test_any_none_coordinate_is_fenced(field: str) -> None:
    """(canary) Any None currentness coordinate => FENCED (fail-closed, §6.1)."""
    assert writer_fenced(_coords(**{field: None}), FLOORS) is True


@given(
    field=st.sampled_from(
        [
            "writer_epoch_floor",
            "membership_generation",
            "restore_generation",
            "revision",
        ]
    )
)
def test_any_none_floor_is_fenced(field: str) -> None:
    """(canary) Any None injected floor => FENCED (currentness unprovable)."""
    floors = FLOORS.model_copy(update={field: None})
    assert writer_fenced(_coords(), floors) is True


@given(epoch=st.integers(min_value=0, max_value=4))
def test_stale_epoch_below_floor_is_fenced(epoch: int) -> None:
    """A writer epoch below the monotone floor is always FENCED (§13 line 355)."""
    assert writer_fenced(_coords(expected_writer_epoch=epoch), FLOORS) is True


def test_epoch_at_or_above_floor_not_stale() -> None:
    """An epoch at/above the floor (other coords current) is not fenced by staleness."""
    assert writer_fenced(_coords(expected_writer_epoch=5), FLOORS) is False
    assert writer_fenced(_coords(expected_writer_epoch=9), FLOORS) is False


def test_membership_mismatch_is_fenced() -> None:
    """A removed / stale voter (membership generation mismatch) is FENCED (§14)."""
    assert writer_fenced(_coords(membership_generation=1), FLOORS) is True


def test_restore_generation_mismatch_is_fenced() -> None:
    """A command crossing a restore generation is FENCED (§5.7 line 139)."""
    assert writer_fenced(_coords(restore_generation=0), FLOORS) is True


def test_stale_expected_revision_is_fenced() -> None:
    """A stale expected revision (CAS mismatch) is FENCED (§9 line 259)."""
    assert writer_fenced(_coords(expected_revision=2), FLOORS) is True


def test_guard_fires_existence() -> None:
    """The predicate is neither constant-True nor constant-False (guard fires)."""
    fenced = writer_fenced(_coords(expected_writer_epoch=0), FLOORS)
    passes = writer_fenced(_coords(), FLOORS)
    assert fenced is True and passes is False
