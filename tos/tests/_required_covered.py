"""Shared harness for the per-package required-covered fail-open suites (design §3.2)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import pytest
from pydantic import BaseModel
from tos.canonical import DigestBoundArtifact

ArtifactTable = Sequence[
    tuple[type[DigestBoundArtifact], Callable[..., dict[str, Any]]]
]


def null_path(kwargs: dict[str, Any], path: str) -> dict[str, Any]:
    """Return ``kwargs`` with the (possibly one-level-nested) dotted ``path`` nulled."""
    out = dict(kwargs)
    if "." in path:
        block, field = path.split(".", 1)
        value = out[block]
        assert isinstance(value, BaseModel), f"expected a model block at {block!r}"
        out[block] = value.model_copy(update={field: None})
    else:
        out[path] = None
    return out


def required_covered_cases(artifacts: ArtifactTable) -> list[Any]:
    """Yield one param per (artifact, required covered path)."""
    cases: list[Any] = []
    for cls, kwargs_fn in artifacts:
        for path in cls._REQUIRED_COVERED:
            cases.append(
                pytest.param(cls, kwargs_fn, path, id=f"{cls.__name__}:{path}")
            )
    return cases


def assert_required_covered_non_vacuous(artifacts: ArtifactTable) -> None:
    """No artifact in the table has an empty ``_REQUIRED_COVERED`` (the fail-open itself)."""
    for cls, _ in artifacts:
        assert cls._REQUIRED_COVERED, f"{cls.__name__} has a vacuous _REQUIRED_COVERED"
