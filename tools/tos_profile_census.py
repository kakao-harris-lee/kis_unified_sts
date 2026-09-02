#!/usr/bin/env python3
"""Shared VERIFICATION-PROFILE-002 null-key census.

Extracted from ``tools/tos_evidence_run.py`` so that both it and
``tools/tos_spec_status.py`` derive the profile's numeric-key population from
one authored implementation instead of two (CLAUDE.md DRY; design
docs/plans/2026-08-12-tos-phase0-completion-contract-design.md §6.3.2). The
behaviour, including the fail-closed shape rejection below, is unchanged from
the original.

``profile_key_universe`` (§6.3.2 follow-up, D0-4b) is the single walk both the
null-key census *and* any caller that needs the full ``{key: is_null}``
mapping (not just the count) build on — so a key-level consumer (D-1's
disposition derivation in ``tools/tos_completion_status.py``) does not need to
re-author the bounds/limits walk to get at the key population.
"""

from __future__ import annotations


def _is_bound_value(value: object) -> bool:
    """A numeric ceiling. ``bool`` is excluded: ``True`` is not a millisecond."""
    return isinstance(value, int | float) and not isinstance(value, bool)


def profile_key_universe(doc: dict) -> dict[str, bool] | None:
    """``{key name: is_null}`` for every numeric key across ``bounds`` and
    ``limits`` combined — the full key population, not just the null subset.

    A ``bounds`` entry is null when its ``value_ms`` is ``null``; a ``limits``
    entry is a scalar, so the entry itself being ``null`` is the same
    condition. This is the one walk :func:`_profile_null_key_census` derives
    its count from below.

    Returns ``None`` for **any** shape this walk cannot honestly count —
    including a name that appears in *both* sections, which would otherwise
    silently collapse two keys into one universe entry and under-count (the
    fail-open direction, per the module docstring's rule: an unrecognised
    shape aborts the whole census rather than skipping a key). Both sections
    are validated **symmetrically**:

    * neither section may be empty — "0 of 0 unapproved" would read as a
      fully approved profile, which is the strongest claim this function can
      make and the last one an empty file should produce;
    * every ``bounds`` entry is a mapping that *has* a ``value_ms`` which is
      ``null`` or numeric (an absent key is a different shape, not a null
      value);
    * every ``limits`` entry is ``null`` or numeric — a mapping or list here
      would mean the section's shape changed, and plain ``is None`` would
      then count the changed entry as carrying an approved value.
    """
    bounds = doc.get("bounds")
    limits = doc.get("limits")
    if not isinstance(bounds, dict) or not isinstance(limits, dict):
        return None
    if not bounds or not limits:
        return None
    universe: dict[str, bool] = {}
    for name, entry in bounds.items():
        if not isinstance(entry, dict) or "value_ms" not in entry:
            return None
        value = entry["value_ms"]
        if value is None:
            universe[str(name)] = True
        elif _is_bound_value(value):
            universe[str(name)] = False
        else:
            return None
    for name, value in limits.items():
        key = str(name)
        if key in universe:
            # bounds/limits 이름 충돌 — 우주가 두 절의 분리합(disjoint union)이
            # 아니게 되어 총계가 조용히 under-count 된다(fail-open 방향이라
            # 스킵하지 않고 전체를 중단한다).
            return None
        if value is None:
            universe[key] = True
        elif _is_bound_value(value):
            universe[key] = False
        else:
            return None
    return universe


def _profile_null_key_census(doc: dict) -> tuple[int, list[str]] | None:
    """``(total numeric keys, sorted names of the keys still carrying no value)``.

    Derived from :func:`profile_key_universe`'s single walk — this function
    only post-processes that result (count + null-name projection) rather
    than re-walking ``bounds``/``limits`` itself, so the fail-closed shape
    rules live in exactly one place.

    Returns ``None`` — which the caller turns into UNKNOWN — whenever
    :func:`profile_key_universe` does (see its docstring for the exact
    fail-closed rules).
    """
    universe = profile_key_universe(doc)
    if universe is None:
        return None
    null_names = sorted(name for name, is_null in universe.items() if is_null)
    return len(universe), null_names
