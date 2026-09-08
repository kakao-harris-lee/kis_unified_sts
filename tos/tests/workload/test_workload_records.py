"""RuntimeIdentity construction + polarity tests (design #40 D4-a)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.workload import RuntimeIdentity


def test_runtime_identity_constructs_with_all_scalars() -> None:
    """A fully-injected RuntimeIdentity constructs and carries every field."""
    identity = RuntimeIdentity(
        cell_id="cell-1",
        runtime_generation=3,
        process_nonce="nonce-abc",
        code_digest="deadbeef",
    )
    assert identity.cell_id == "cell-1"
    assert identity.runtime_generation == 3
    assert identity.process_nonce == "nonce-abc"
    assert identity.code_digest == "deadbeef"


def test_runtime_identity_constructs_with_all_none() -> None:
    """Every field is optional at the type level (∅-both-ways — a bare instance
    is representable; required-ness is enforced at the point of use, matching
    this codebase's convention for injected-scalar records)."""
    identity = RuntimeIdentity()
    assert identity.cell_id is None
    assert identity.runtime_generation is None
    assert identity.process_nonce is None
    assert identity.code_digest is None


def test_runtime_identity_frozen() -> None:
    """RuntimeIdentity is immutable (FrozenModel)."""
    identity = RuntimeIdentity(cell_id="cell-1")
    with pytest.raises((TypeError, ValueError)):
        identity.cell_id = "cell-2"  # type: ignore[misc]


@pytest.mark.parametrize("generation", [-1, -100])
def test_runtime_identity_rejects_negative_generation(generation: int) -> None:
    """A negative runtime_generation is unconstructable."""
    with pytest.raises(ValidationError):
        RuntimeIdentity(runtime_generation=generation)


def test_runtime_identity_accepts_zero_generation() -> None:
    """Zero is a valid (the initial) generation."""
    identity = RuntimeIdentity(runtime_generation=0)
    assert identity.runtime_generation == 0


@pytest.mark.parametrize("nonce", ["", "   ", "\t"])
def test_runtime_identity_rejects_blank_process_nonce(nonce: str) -> None:
    """A present-but-blank process_nonce is unconstructable."""
    with pytest.raises(ValidationError):
        RuntimeIdentity(process_nonce=nonce)


def test_runtime_identity_process_nonce_none_is_representable() -> None:
    """process_nonce=None (not yet injected) is distinct from a blank string and
    does not raise — only a present-but-blank nonce is rejected."""
    identity = RuntimeIdentity(process_nonce=None)
    assert identity.process_nonce is None
