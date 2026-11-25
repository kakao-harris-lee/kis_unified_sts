"""Orthostate injected predicate-input models (design #8 §2.1, §5.2)."""

from __future__ import annotations

from tos.orthostate._base import FrozenModel


class CouplingSideConditions(FrozenModel):
    """Injected side-conditions for the cross-dimension coupling predicate (§5.2)."""

    final_quantity_proof: bool | None = None
    consistent_release_proof_rule: bool | None = None
    authority_epoch_current: bool | None = None
    non_reducible_exposure: bool | None = None
