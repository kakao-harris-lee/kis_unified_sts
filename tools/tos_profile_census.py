#!/usr/bin/env python3
"""Shared VERIFICATION-PROFILE-002 null-key census.

Extracted from ``tools/tos_evidence_run.py`` so that both it and
``tools/tos_spec_status.py`` derive the profile's numeric-key population from
one authored implementation instead of two (CLAUDE.md DRY; design
docs/plans/2026-08-12-tos-phase0-completion-contract-design.md §6.3.2). The
behaviour, including the fail-closed shape rejection below, is unchanged from
the original.
"""

from __future__ import annotations


def _is_bound_value(value: object) -> bool:
    """A numeric ceiling. ``bool`` is excluded: ``True`` is not a millisecond."""
    return isinstance(value, int | float) and not isinstance(value, bool)


def _profile_null_key_census(doc: dict) -> tuple[int, list[str]] | None:
    """``(total numeric keys, sorted names of the keys still carrying no value)``.

    A ``bounds`` entry is unapproved-null when its ``value_ms`` is ``null``; a
    ``limits`` entry is a scalar, so the entry itself being ``null`` is the same
    condition.

    Returns ``None`` — which the caller turns into UNKNOWN — for **any** shape the
    census cannot honestly count. Under-counting is the fail-open direction here: a
    key the census fails to recognise as null silently joins the approved population,
    so every unrecognised shape must abort the whole census rather than skip a key.
    Both sections are therefore validated **symmetrically**:

    * neither section may be empty — "0 of 0 unapproved" would read as a fully
      approved profile, which is the strongest claim this function can make and the
      last one an empty file should produce;
    * every ``bounds`` entry is a mapping that *has* a ``value_ms`` which is ``null``
      or numeric (an absent key is a different shape, not a null value);
    * every ``limits`` entry is ``null`` or numeric — a mapping or list here would
      mean the section's shape changed, and plain ``is None`` would then count the
      changed entry as carrying an approved value.
    """
    bounds = doc.get("bounds")
    limits = doc.get("limits")
    if not isinstance(bounds, dict) or not isinstance(limits, dict):
        return None
    if not bounds or not limits:
        return None
    null_names: list[str] = []
    for name, entry in bounds.items():
        if not isinstance(entry, dict) or "value_ms" not in entry:
            return None
        value = entry["value_ms"]
        if value is None:
            null_names.append(str(name))
        elif not _is_bound_value(value):
            return None
    for name, value in limits.items():
        if value is None:
            null_names.append(str(name))
        elif not _is_bound_value(value):
            return None
    return len(bounds) + len(limits), sorted(null_names)
