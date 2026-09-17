"""Shared named-TBD placeholder rejection (W-A A-0; kernel round #4 ``contract-keeper``
HIGH finding).

Every ``tos_runtime.*`` config loader in this package already refuses a bare ``null`` leaf
as "named-TBD, not filled in yet" — the "null=named-TBD ⇒ refuse to start" discipline nearly
every loader's own module docstring cites. Kernel round #4's ``contract-keeper`` review
found a SECOND, narrower gap in ``tos_runtime.compose._construction_config``'s
``optional_str`` helper: an operator who instead types the literal STRING ``"TBD"`` into a
free-string field (rather than leaving it ``null``) was never caught there — a plain
``isinstance(value, str) and value.strip()`` check happily accepts ``"TBD"`` as if it were a
real value, silently sealing a placeholder into a canonical digest the next commit reads
back as though an operator had actually filled it in.

That was one instance; W-A A-0's own survey (``docs/plans/2026-09-18-tos-config-adoption-
and-carryover-plan.md`` §0.1.3) found the SAME gap-shape open in every other free-string
loader that had no enum/allow-list backing its type check (an enum lookup already refuses
``"TBD"`` on its own, since it is never a valid member name — those loaders needed no
change). This module gives every one of those loaders the same guard from ONE place, so the
check is a single class-closing fact rather than N independently-drifting copies (the two
loaders that already had their own local check —
:mod:`tos_runtime.venue._policy_primitives` / :mod:`tos_runtime.compose._construction_config`
— now source their own ``TBD_STR``/``_TBD_STR`` constant from here too, so there is exactly
one literal, not three).

Pure stdlib module: no ``tos.*``, no ``yaml`` — a bare string-equality helper has no reason
to know a kernel record shape or a YAML shape.
"""

from __future__ import annotations

__all__ = ["NAMED_TBD_PLACEHOLDER", "is_named_tbd_placeholder", "reject_named_tbd"]

#: The one placeholder string this codebase's example configs use for "an operator has not
#: filled this in yet" — an EXACT match only, deliberately never case-folded or fuzzy.
#: ``"tbd"``/``"Tbd"``/``"TODO"``/an empty string etc. are ordinary strings some other field
#: might legitimately need (W-A A-0 survey: this codebase's own convention, set by
#: ``tos_runtime.venue._policy_primitives.TBD_STR`` and the shipped ``*.example.yaml``
#: templates, is the exact uppercase token — widening the match risks refusing a legitimate
#: value that merely happens to look similar, which is a different, unrelated failure mode
#: from the one this module closes).
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
