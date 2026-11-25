"""Reject the reserved named-TBD placeholder used by runtime config loaders."""

from __future__ import annotations

from typing import Any

__all__ = [
    "NAMED_TBD_PLACEHOLDER",
    "first_named_tbd_leaf",
    "is_named_tbd_placeholder",
    "reject_named_tbd",
]

NAMED_TBD_PLACEHOLDER = "TBD"


def is_named_tbd_placeholder(value: object) -> bool:
    """Whether ``value`` is exactly the named-TBD placeholder string."""
    return value == NAMED_TBD_PLACEHOLDER


def reject_named_tbd(
    value: object, *, field: str, context: str, error_cls: type[Exception]
) -> None:
    """Raise ``error_cls`` if ``value`` is still the named-TBD placeholder string."""
    if is_named_tbd_placeholder(value):
        raise error_cls(
            f"{context}: {field!r} is still the template placeholder "
            f"{NAMED_TBD_PLACEHOLDER!r} — operator-fill before activation, never a value "
            "this loader treats as concrete"
        )


def first_named_tbd_leaf(value: Any, path: str) -> str | None:
    """Return the dotted/indexed path of the first named-TBD placeholder STRING leaf"""
    if isinstance(value, dict):
        for key, sub in value.items():
            found = first_named_tbd_leaf(sub, f"{path}.{key}" if path else str(key))
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for index, sub in enumerate(value):
            found = first_named_tbd_leaf(sub, f"{path}[{index}]")
            if found is not None:
                return found
        return None
    if is_named_tbd_placeholder(value):
        return path or "<root>"
    return None
