"""The env-value carrier shape — ``ContextValue`` / ``ContextValueView`` (design #32 §2.2 F1)."""

from __future__ import annotations

from pydantic import model_validator

from tos.dsl._base import ArtifactIntegrityError, FrozenModel
from tos.dsl.candidate import WILDCARD_TOKENS
from tos.dsl.vocabulary import ScalarValue

__all__ = [
    "VALUE_NAMESPACE",
    "ContextValue",
    "ContextValueView",
    "is_wildcard_field_key",
]

VALUE_NAMESPACE = "resolved_values"


def is_wildcard_field_key(field_key: str) -> bool:
    """Whether a ``field_key`` is a wildcard / "latest" form (design #32 §2.4)."""
    if field_key in WILDCARD_TOKENS:
        return True
    return "*" in field_key or field_key.lower() == "latest"


class ContextValue(FrozenModel):
    """One admitted Critical Input value as the DSL environment sees it (design #32 §2.2)."""

    field_key: str
    value: ScalarValue
    as_of: int
    payload_digest: str
    observation_ref: str

    @model_validator(mode="after")
    def _bindings_concrete_and_governed(self) -> ContextValue:
        """Reject a blank / wildcard key or a blank provenance pointer (fail-closed)."""
        for name in ("field_key", "payload_digest", "observation_ref"):
            token: str = getattr(self, name)
            if not token.strip():
                raise ArtifactIntegrityError(
                    f"ContextValue.{name} must be concrete — a value with no attributed "
                    "provenance is a side channel, not a Critical Input "
                    "(RFC-004 §9:242-244; design #32 §2.3/§4.2)"
                )
        if is_wildcard_field_key(self.field_key):
            raise ArtifactIntegrityError(
                f"ContextValue.field_key={self.field_key!r} must not be a wildcard / 'latest' "
                "form — a wildcard field reference is prohibited on the authoring surface "
                "(RFC-008 §7:239-240; design #32 §2.4)"
            )
        return self


class ContextValueView(FrozenModel):
    """The value set one evaluation may read, bound to its snapshot (design #32 §2.2)."""

    snapshot_id: str
    snapshot_canonical_digest: str
    values: tuple[ContextValue, ...] = ()
    canonical_digest: str
    canonicalization_version: str

    @model_validator(mode="after")
    def _binding_concrete_and_keys_distinct(self) -> ContextValueView:
        """Reject a blank binding/digest or a duplicated ``field_key`` (fail-closed)."""
        for name in (
            "snapshot_id",
            "snapshot_canonical_digest",
            "canonical_digest",
            "canonicalization_version",
        ):
            token: str = getattr(self, name)
            if not token.strip():
                raise ArtifactIntegrityError(
                    f"ContextValueView.{name} must be concrete — an unbound or undigested value "
                    "view cannot evidence which snapshot it came from (ADR-002-018 §15:373-386; "
                    "design #32 §2.2/§3.3)"
                )
        seen: set[str] = set()
        duplicates: list[str] = []
        for value in self.values:
            if value.field_key in seen:
                duplicates.append(value.field_key)
            seen.add(value.field_key)
        if duplicates:
            raise ArtifactIntegrityError(
                f"ContextValueView carries duplicate field_key(s) {sorted(set(duplicates))} — "
                "disagreeing observations of one field are never averaged, majority-voted, or "
                "collapsed onto an arbitrary one (ADR-002-018 §11:311, §14:365; design #32 §6)"
            )
        return self

    def as_environment_mapping(self) -> dict[str, ScalarValue]:
        """Project the view onto the flat ``{field_key: scalar}`` mapping the DSL walks."""
        return {value.field_key: value.value for value in self.values}
