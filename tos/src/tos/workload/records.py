"""Runtime workload-instance identity record (design #40 D4-a)."""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel

__all__ = ["RuntimeIdentity"]


class RuntimeIdentity(FrozenModel):
    """The identity of one running kernel-hosting process instance (design #40 D4-a)."""

    cell_id: str | None = None
    runtime_generation: int | None = None
    process_nonce: str | None = None
    code_digest: str | None = None

    @model_validator(mode="after")
    def _runtime_identity_invariants(self) -> RuntimeIdentity:
        """Reject a negative generation or a blank (but present) process nonce."""
        if self.runtime_generation is not None and self.runtime_generation < 0:
            raise ArtifactIntegrityError(
                "RuntimeIdentity.runtime_generation must be non-negative "
                f"(got {self.runtime_generation})"
            )
        if self.process_nonce is not None and not self.process_nonce.strip():
            raise ArtifactIntegrityError(
                "RuntimeIdentity.process_nonce must be non-blank when provided — "
                "a blank nonce cannot fence a stale-instance replay"
            )
        return self
