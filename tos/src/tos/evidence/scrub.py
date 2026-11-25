"""Deterministic secret-field scrubbing before evidence serialization (design #40 D3-d)."""

from __future__ import annotations

from collections.abc import Mapping

__all__ = ["scrub_secret_fields"]

_REDACTED = "***REDACTED***"


def _scrub_value(
    value: object, secret_keys: frozenset[str], path: str
) -> tuple[object, list[str]]:
    """Scrub one already-addressed value: mapping and list/tuple recurse, else a leaf."""
    if isinstance(value, Mapping):
        return _scrub_mapping(value, secret_keys, path)
    if isinstance(value, (list, tuple)):
        scrubbed_elements: list[object] = []
        masked: list[str] = []
        for index, element in enumerate(value):
            element_path = f"{path}[{index}]"
            scrubbed_element, nested_masked = _scrub_value(
                element, secret_keys, element_path
            )
            scrubbed_elements.append(scrubbed_element)
            masked.extend(nested_masked)
        preserved: object = (
            tuple(scrubbed_elements) if isinstance(value, tuple) else scrubbed_elements
        )
        return preserved, masked
    return value, []


def _scrub_mapping(
    node: Mapping[str, object], secret_keys: frozenset[str], prefix: str
) -> tuple[dict[str, object], list[str]]:
    """Recursively scrub one mapping level; return the scrubbed copy + masked paths."""
    out: dict[str, object] = {}
    masked: list[str] = []
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if key in secret_keys:
            out[key] = _REDACTED
            masked.append(path)
        else:
            scrubbed_value, nested_masked = _scrub_value(value, secret_keys, path)
            out[key] = scrubbed_value
            masked.extend(nested_masked)
    return out, masked


def scrub_secret_fields(
    payload: Mapping[str, object], secret_keys: frozenset[str]
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Deterministically mask every field whose key is in ``secret_keys`` (design #40 D3-d)."""
    out, masked = _scrub_mapping(payload, secret_keys, "")
    return out, tuple(sorted(masked))
