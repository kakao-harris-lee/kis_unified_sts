"""Unit tests for :mod:`tos_runtime._named_tbd` (W-A A-0, kernel round #4
``contract-keeper`` HIGH finding — closing the named-TBD bypass class rather than
one instance of it).
"""

from __future__ import annotations

import pytest
from tos_runtime._named_tbd import (
    NAMED_TBD_PLACEHOLDER,
    is_named_tbd_placeholder,
    reject_named_tbd,
)


class _SomeConfigError(Exception):
    pass


def test_placeholder_constant_is_the_repo_convention() -> None:
    """Pins the literal to the SAME token every other loader in this codebase
    already uses (``tos_runtime.venue._policy_primitives.TBD_STR`` /
    ``tos_runtime.compose._construction_config._TBD_STR``) — a drift here would
    silently desynchronize every caller of :func:`reject_named_tbd` from those
    two pre-existing, independently-reviewed checks."""
    assert NAMED_TBD_PLACEHOLDER == "TBD"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("TBD", True),
        ("tbd", False),
        ("Tbd", False),
        ("TODO", False),
        ("", False),
        (None, False),
        (0, False),
        (False, False),
        ("TBD ", False),
        (" TBD", False),
        ("some-real-value", False),
    ],
)
def test_is_named_tbd_placeholder_is_an_exact_match_only(
    value: object, expected: bool
) -> None:
    """Deliberately narrow (module docstring): a case-folded or fuzzy match risks
    refusing a legitimate value that merely looks similar — a different, unrelated
    failure mode from the one this module closes."""
    assert is_named_tbd_placeholder(value) is expected


def test_reject_named_tbd_raises_the_callers_own_error_type() -> None:
    with pytest.raises(_SomeConfigError, match="template placeholder"):
        reject_named_tbd(
            "TBD",
            field="some_field",
            context="some context",
            error_cls=_SomeConfigError,
        )


def test_reject_named_tbd_error_names_field_and_context() -> None:
    with pytest.raises(_SomeConfigError) as excinfo:
        reject_named_tbd(
            "TBD",
            field="expected_code_digest",
            context="/tmp/release.yaml",
            error_cls=_SomeConfigError,
        )
    message = str(excinfo.value)
    assert "expected_code_digest" in message
    assert "/tmp/release.yaml" in message


@pytest.mark.parametrize("value", ["real-value", "tbd", "", None, 0, False, 42])
def test_reject_named_tbd_passes_through_every_non_placeholder_value(
    value: object,
) -> None:
    """No raise, no return value mutation — callers keep using their own
    already-validated ``value`` afterward (mirrors every call site's own
    ``reject_named_tbd(value, ...); return value`` shape)."""
    reject_named_tbd(value, field="f", context="c", error_cls=_SomeConfigError)
