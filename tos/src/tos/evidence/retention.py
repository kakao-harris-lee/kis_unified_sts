"""Retention deletability predicate + Tombstone record (design #40 D3.1, D3-c)."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel

__all__ = ["Tombstone", "retention_deletable"]


def retention_deletable(
    record_class: str | None,
    age_days: int | None,
    minimum_days_by_class: Mapping[str, int] | None,
    holds_active: bool | None,
    open_or_live: bool | None,
) -> bool:
    """Whether a record may be deleted under retention policy (design #40 D3.1)."""
    if record_class is None or age_days is None or minimum_days_by_class is None:
        return False
    if holds_active is not False:
        return False
    if open_or_live is not False:
        return False
    minimum = minimum_days_by_class.get(record_class)
    if minimum is None:
        return False
    if age_days < 0 or minimum < 0:
        return False
    return age_days >= minimum


class Tombstone(FrozenModel):
    """An append-only deletion record over one prior evidence record (design #40 D3.1)."""

    record_id: str | None = None
    record_class: str | None = None
    deleted_at: str | None = None
    dual_control_ref: str | None = None

    @model_validator(mode="after")
    def _dual_control_ref_non_blank(self) -> Tombstone:
        """Reject a Tombstone with a missing or blank dual-control reference."""
        if self.dual_control_ref is None or not self.dual_control_ref.strip():
            raise ArtifactIntegrityError(
                "Tombstone.dual_control_ref must be non-blank — a tombstone with "
                "no dual-control witness is not a valid deletion record "
                "(ADR-002-016 :432-441)"
            )
        return self
