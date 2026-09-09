"""``Operand.ref`` source validation ([K2-p3-#10] finding #10).

Design §4's ``Operand.ref`` field docstring has long claimed "``ref[0]`` ... SHALL be an
:data:`ADMISSIBLE_CONTEXT_SOURCES` member — there is no way to name an ambient source here
(DCE-INV-003)". Before this lane that was **false**: ``Operand._exactly_one`` validated only
"exactly one of const/ref is set, and ref is non-empty" — it never checked ``ref[0]`` against
``ADMISSIBLE_CONTEXT_SOURCES`` at all, so ``Operand(ref=("ambient", "now"))`` constructed without
complaint. The independent review that found this ran exactly that probe and also constructed
``Operand(ref=("network", "fetch"))`` successfully.

The escape-checker (:func:`tos.dsl.admissibility.analyze`, exercised in
``tos/tests/engine/test_engine_admission_escape_checker.py``) already caught this at the *lowered
program* layer — a genuinely ambient-sourced strategy was never admitted end-to-end. But the two
gates disagreed **in scope**, not just in effect: the constructor admitted a shape the escape-
checker alone had to catch. This module closes that gap at the source: the constructor now
positively validates ``ref[0]`` too, so both gates agree by construction.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.dsl import ADMISSIBLE_CONTEXT_SOURCES, Operand

#: The reviewer's exact probe sources, plus a few more ambient sources already used elsewhere in
#: the DSL test suite (``tos/tests/dsl/_dsl_strategies.py::_AMBIENT_SOURCES``) for consistency.
_NON_ADMISSIBLE_SOURCES = (
    "ambient",
    "network",
    "clock",
    "filesystem",
    "env",
    "global",
    "builtin",
)


@pytest.mark.parametrize("source", _NON_ADMISSIBLE_SOURCES)
def test_a_ref_naming_a_non_admissible_source_is_unconstructable(source: str) -> None:
    """(finding #10) ``Operand(ref=(source, ...))`` refuses any source outside the admissible set.

    Before the fix this constructed successfully for every one of these sources — the field
    docstring's "there is no way to name an ambient source here" claim was aspirational, not
    enforced. Pydantic wraps a ``model_validator``'s raised ``ArtifactIntegrityError`` into its own
    :class:`~pydantic.ValidationError`, so that is what a caller actually observes here (the same
    pattern the shipped ``test_dsl_admissibility.py`` / ``test_dsl_bounds.py`` suites use for other
    ``model_validator``-raised construction refusals).
    """
    assert source not in ADMISSIBLE_CONTEXT_SOURCES
    with pytest.raises(ValidationError, match="ADMISSIBLE_CONTEXT_SOURCES"):
        Operand(ref=(source, "now"))


@pytest.mark.parametrize("source", sorted(ADMISSIBLE_CONTEXT_SOURCES))
def test_a_ref_naming_an_admissible_source_still_constructs(source: str) -> None:
    """(no regression) Every genuinely admissible source still constructs without complaint."""
    operand = Operand(ref=(source, "some_field"))
    assert operand.ref == (source, "some_field")


def test_the_non_empty_path_guard_still_fires_independently_of_the_source_check() -> (
    None
):
    """(no regression) An empty ``ref`` is still refused on its own pre-existing message.

    An empty tuple carries no ``ref[0]`` to check a source against at all — that is the older,
    distinct "non-empty path" defect class, and it must keep firing on its own message rather than
    being shadowed by the new source-membership check.
    """
    with pytest.raises(ValidationError, match="non-empty path"):
        Operand(ref=())
