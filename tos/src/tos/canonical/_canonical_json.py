"""Deterministic JSON-mode set ordering for every tos artifact model."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    GetCoreSchemaHandler,
    SerializationInfo,
    SerializerFunctionWrapHandler,
)

__all__ = ["CanonicalJsonMixin"]

_SET_SCHEMA_TYPES: frozenset[str] = frozenset({"set", "frozenset"})

_OPAQUE_SCHEMA_TYPES: frozenset[str] = frozenset(
    {"model", "dataclass", "definition-ref"}
)

_NON_SCHEMA_KEYS: frozenset[str] = frozenset({"default", "metadata"})

_ABSENT: object = object()


def _schema_declares_set(node: Any) -> bool:
    """Whether a core-schema fragment declares a set anywhere outside a nested model."""
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type in _SET_SCHEMA_TYPES:
            return True
        if node_type in _OPAQUE_SCHEMA_TYPES:
            return False
        return any(
            _schema_declares_set(child)
            for key, child in node.items()
            if key not in _NON_SCHEMA_KEYS
        )
    if isinstance(node, (list, tuple)):
        return any(_schema_declares_set(child) for child in node)
    return False


def _set_bearing_field_names(schema: Any) -> tuple[str, ...]:
    """Return the model's own field names whose type tree declares a set."""
    node: Any = schema
    while isinstance(node, dict) and node.get("type") != "model-fields":
        node = node.get("schema")
    if not isinstance(node, dict):
        return ()

    names: list[str] = []
    fields = node.get("fields")
    if isinstance(fields, dict):
        names.extend(
            name
            for name, field_schema in fields.items()
            if _schema_declares_set(field_schema)
        )
    computed = node.get("computed_fields")
    if isinstance(computed, list):
        names.extend(
            entry["property_name"]
            for entry in computed
            if isinstance(entry, dict)
            and isinstance(entry.get("property_name"), str)
            and _schema_declares_set(entry.get("return_schema"))
        )
    return tuple(names)


def _with_sorted_sets(original: Any, dumped: Any) -> Any:
    """Sort the serialized lists whose original value was a set."""
    if isinstance(original, (set, frozenset)):
        return sorted(dumped) if isinstance(dumped, list) else dumped
    if isinstance(original, BaseModel):
        return dumped
    if isinstance(original, Mapping):
        if not isinstance(dumped, dict) or len(dumped) != len(original):
            return dumped
        return {
            key: _with_sorted_sets(original_child, dumped_child)
            for (key, dumped_child), original_child in zip(
                dumped.items(), original.values()
            )
        }
    if isinstance(original, (list, tuple)):
        if not isinstance(dumped, list) or len(dumped) != len(original):
            return dumped
        return [
            _with_sorted_sets(original_child, dumped_child)
            for original_child, dumped_child in zip(original, dumped)
        ]
    return dumped


def _dump_with_sorted_sets(
    model: BaseModel,
    handler: SerializerFunctionWrapHandler,
    info: SerializationInfo,
) -> Any:
    """Wrapping model serializer: order JSON-mode set output deterministically."""
    dumped = handler(model)
    if info.mode != "json" or not isinstance(dumped, dict):
        return dumped
    set_fields: tuple[str, ...] = getattr(type(model), "__canonical_set_fields__", ())
    for name in set_fields:
        if name not in dumped:
            continue
        original = getattr(model, name, _ABSENT)
        if original is _ABSENT:
            continue
        dumped[name] = _with_sorted_sets(original, dumped[name])
    return dumped


_SORTED_SET_SERIALIZATION: dict[str, Any] = {
    "type": "function-wrap",
    "function": _dump_with_sorted_sets,
    "info_arg": True,
    "return_schema": {
        "type": "dict",
        "keys_schema": {"type": "str"},
        "values_schema": {"type": "any"},
    },
}


def _is_this_hook(serialization: Any) -> bool:
    """Whether a core-schema ``serialization`` entry is this module's own hook."""
    return (
        isinstance(serialization, dict)
        and serialization.get("function") is _dump_with_sorted_sets
    )


class CanonicalJsonMixin:
    """Attach deterministic JSON-mode set ordering to set-bearing models only."""

    __canonical_set_fields__: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[Any], handler: GetCoreSchemaHandler
    ) -> Any:
        """Build the model schema, attaching the sort hook only when it is needed."""
        schema = handler(source)
        set_fields = _set_bearing_field_names(schema)
        if not set_fields:
            return schema
        if not isinstance(schema, dict):  # pragma: no cover - defensive
            return schema
        existing = schema.get("serialization")
        if existing is not None and not _is_this_hook(existing):
            raise TypeError(
                f"{source.__qualname__} declares both a set field and its own "
                "model serializer; canonical set ordering would be lost "
                "(tos.canonical._canonical_json)"
            )
        source.__canonical_set_fields__ = set_fields
        schema["serialization"] = dict(_SORTED_SET_SERIALIZATION)
        return schema
