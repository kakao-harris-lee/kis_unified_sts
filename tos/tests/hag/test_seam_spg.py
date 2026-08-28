"""MANDATED test-only seam cross-check: hag break-glass direction <-> spg action-token (design #20 §3.5/§7).

spg (ADR-002-014 §8) owns the **safety-config break-glass action-token** confinement:
``break_glass_confined`` (``predicates.py:746``) restricts an action to
``BREAK_GLASS_ALLOWED_ACTIONS = {HALT, RESTRICTIVE_OVERRIDE}`` (``vocabulary.py:258``, 2 tokens).
hag owns the **human authority-class direction** confinement (§7 8-class taxonomy): only
``HALT`` / ``NARROW`` / ``REQUEST_PROTECTIVE`` are direction-restrictive. **Different axes, different
vocabularies** — and spg's own docstring (``predicates.py:754-756``) explicitly defers the
effective-principal-independence residue to "ADR-002-015 HAG-EV +Security — not-Phase-1", so spg
names hag as the owner. This file imports the real spg symbols as a **test** to lock the boundary;
the import-closure test proves ``tos.spg`` is **absent** from the hag runtime closure.

Regime tag: predicate / model substrate only; HAG-EV-006 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.hag import (
    BREAK_GLASS_RESTRICTIVE_CLASSES,
    AuthorityClass,
    break_glass_direction_restrictive,
)
from tos.spg import BREAK_GLASS_ALLOWED_ACTIONS, BreakGlassAction, break_glass_confined


def test_spg_owns_a_two_token_action_confinement() -> None:
    """(§3.5 (b)) spg confines to a 2-token action set {HALT, RESTRICTIVE_OVERRIDE}."""
    assert (
        frozenset({BreakGlassAction.HALT, BreakGlassAction.RESTRICTIVE_OVERRIDE})
        == BREAK_GLASS_ALLOWED_ACTIONS
    )
    assert break_glass_confined(BreakGlassAction.HALT) is True
    assert break_glass_confined(BreakGlassAction.RESTRICTIVE_OVERRIDE) is True


def test_hag_owns_an_eight_class_direction_confinement() -> None:
    """(§3.5 (b)) hag confines by authority-class direction — 3 restrictive of the 8 classes."""
    assert len(list(AuthorityClass)) == 8
    assert (
        frozenset(
            {
                AuthorityClass.HALT,
                AuthorityClass.NARROW,
                AuthorityClass.REQUEST_PROTECTIVE,
            }
        )
        == BREAK_GLASS_RESTRICTIVE_CLASSES
    )
    assert break_glass_direction_restrictive(AuthorityClass.NARROW) is True
    assert break_glass_direction_restrictive(AuthorityClass.TRANSMIT) is False


def test_the_two_axes_are_distinct_vocabularies() -> None:
    """(§3.5 (b)) The spg action-token axis and the hag authority-class axis are distinct types."""
    # spg's RESTRICTIVE_OVERRIDE is an action token with no HAG authority-class counterpart…
    assert BreakGlassAction.RESTRICTIVE_OVERRIDE.value == "RESTRICTIVE_OVERRIDE"
    hag_class_values = {c.value for c in AuthorityClass}
    assert "RESTRICTIVE_OVERRIDE" not in hag_class_values
    # …and hag's NARROW / REQUEST_PROTECTIVE are authority classes with no spg action-token counterpart.
    spg_action_values = {a.value for a in BreakGlassAction}
    assert "NARROW" not in spg_action_values
    assert "REQUEST_PROTECTIVE" not in spg_action_values


def test_hag_does_not_reauthor_spg_action_token() -> None:
    """(§0.4d/§3.5) hag re-authors neither break_glass_confined nor BreakGlassAction."""
    import tos.hag as hag

    assert not hasattr(hag, "break_glass_confined")
    assert not hasattr(hag, "BreakGlassAction")
    assert not hasattr(hag, "BREAK_GLASS_ALLOWED_ACTIONS")
