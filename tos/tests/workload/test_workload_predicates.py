"""environment_label_consistent polarity tests (design #40 D4-b; ADR-002-013 :498)."""

from __future__ import annotations

import pytest
from tos.workload import environment_label_consistent


def test_matching_labels_are_consistent() -> None:
    assert environment_label_consistent("paper", "paper") is True


def test_mismatched_labels_are_inconsistent() -> None:
    assert environment_label_consistent("paper", "production") is False


@pytest.mark.parametrize(
    "runtime_label,manifest_label",
    [
        ("restricted-live", "production"),
        ("test", "paper"),
        ("PAPER", "paper"),  # byte-exact only — no case-folding
    ],
)
def test_distinct_labels_never_match(runtime_label: str, manifest_label: str) -> None:
    assert environment_label_consistent(runtime_label, manifest_label) is False


@pytest.mark.parametrize(
    "runtime_label,manifest_label",
    [
        (None, "paper"),
        ("paper", None),
        (None, None),
    ],
)
def test_none_axis_never_admits(runtime_label, manifest_label) -> None:
    """Either label being None (unknown) fails closed — never a vacuous match."""
    assert environment_label_consistent(runtime_label, manifest_label) is False


@pytest.mark.parametrize(
    "runtime_label,manifest_label",
    [
        ("", "paper"),
        ("paper", ""),
        ("   ", "paper"),
    ],
)
def test_blank_axis_never_admits(runtime_label: str, manifest_label: str) -> None:
    """A blank (non-None but empty/whitespace) label also fails closed."""
    assert environment_label_consistent(runtime_label, manifest_label) is False
