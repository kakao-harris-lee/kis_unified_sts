"""Reject the reserved named-TBD placeholder used by runtime config loaders.

Runtime loaders reserve ``None`` for an unfilled value; this module rejects the
separate exact string ``"TBD"`` before it can be sealed into a canonical
configuration digest. The match is intentionally exact and case-sensitive.
``reject_named_tbd`` preserves each caller's error type and names the field and
loader context in its failure.

The helpers are stdlib-only and operate on arbitrary nested mappings and
sequences so raw-dict-to-model loaders can apply the same fail-closed guard.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "NAMED_TBD_PLACEHOLDER",
    "first_named_tbd_leaf",
    "is_named_tbd_placeholder",
    "reject_named_tbd",
]

#: Exact placeholder used by example configs. The match stays case-sensitive and
#: other similar-looking strings remain ordinary values.
NAMED_TBD_PLACEHOLDER = "TBD"


def is_named_tbd_placeholder(value: object) -> bool:
    """Whether ``value`` is exactly the named-TBD placeholder string."""
    return value == NAMED_TBD_PLACEHOLDER


def reject_named_tbd(
    value: object, *, field: str, context: str, error_cls: type[Exception]
) -> None:
    """Raise ``error_cls`` if ``value`` is still the named-TBD placeholder string.

    Callers apply this AFTER their own null/type check has already established ``value`` is
    a concrete string — this function closes only the SECOND gap (a placeholder STRING
    typed in place of a real value), never the first (a bare ``null``), which every caller's
    own existing check already refuses.

    Args:
        value: The already-type-checked value to check (typically a ``str`` a caller's own
            ``isinstance`` check just accepted).
        field: The field name, for the error message.
        context: The loader's own error-message prefix (a file path, a ``scope %r`` label,
            etc. — every caller already builds one of these for its own null/type errors).
        error_cls: The caller's own exception type, so each loader's boot-refusal exception
            type is preserved (mirrors :mod:`tos_runtime.safety._policy_loader`'s own
            ``error_cls`` parameter convention).

    Raises:
        error_cls: ``value`` is exactly ``"TBD"``.
    """
    if is_named_tbd_placeholder(value):
        raise error_cls(
            f"{context}: {field!r} is still the template placeholder "
            f"{NAMED_TBD_PLACEHOLDER!r} — operator-fill before activation, never a value "
            "this loader treats as concrete"
        )


def first_named_tbd_leaf(value: Any, path: str) -> str | None:
    """Return the dotted/indexed path of the first named-TBD placeholder STRING leaf
    found by a depth-first walk of ``value`` (dict values and list elements only —
    scalars ARE the leaves), or ``None`` if there is none.

    For a loader that hands a raw dict straight to ``pydantic.model_validate`` with no
    per-field extraction of its own (e.g. :mod:`tos_runtime.safety.profile`'s three
    policy documents) — :func:`reject_named_tbd` has nothing to wrap in that shape,
    since there is no individual ``value``/``field`` pair to check one at a time. This
    walks the whole raw mapping/list tree in one pass instead, the same discipline
    :mod:`tos_runtime.strategy.loader`'s sibling ``first_null_leaf`` already applies for
    a bare ``null`` anywhere in a free-form strategy file.

    Args:
        value: The (sub)value to inspect.
        path: The dotted/indexed path to ``value`` itself, for the message.

    Returns:
        The path of the first :data:`NAMED_TBD_PLACEHOLDER` string found, else ``None``.
    """
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
