"""Environment-label consistency predicate (design #40 D4-b; ADR-002-013 :498)."""

from __future__ import annotations

__all__ = ["environment_label_consistent"]


def environment_label_consistent(
    runtime_label: str | None, manifest_label: str | None
) -> bool:
    """Whether the boot-arg environment label matches the custody manifest's label."""
    if runtime_label is None or manifest_label is None:
        return False
    if not runtime_label.strip() or not manifest_label.strip():
        return False
    return runtime_label == manifest_label
