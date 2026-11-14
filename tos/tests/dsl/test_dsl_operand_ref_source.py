"""``Operand.ref`` source validation ([K2-p3-#10] finding #10)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.dsl import ADMISSIBLE_CONTEXT_SOURCES, Operand

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
    """(finding #10) ``Operand(ref=(source, ...))`` refuses any source outside the admissible set."""
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
    """(no regression) An empty ``ref`` is still refused on its own pre-existing message."""
    with pytest.raises(ValidationError, match="non-empty path"):
        Operand(ref=())
