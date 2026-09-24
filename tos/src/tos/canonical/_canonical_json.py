"""Deterministic JSON-mode set ordering for every tos artifact model.

``model_dump(mode="json")`` serializes a ``set`` / ``frozenset`` in **iteration**
order, and iteration order of a set of strings follows ``PYTHONHASHSEED``. The
canonicalizer (``tos.canonical.canonicalization._encode``) sorts mapping keys but
treats a sequence as order-significant, so the same covered content produced two
different digests in two processes — a direct violation of design #2 §3.4
must-pass **(A)-1 "determinism: same covered content => same digest"** (plan
``docs/plans/2026-09-24-tos-canonical-set-order-plan.md`` §0/§1).

The fix is one hook at the root of the model hierarchy instead of one sorter per
model: :class:`CanonicalJsonMixin` is a base of
:class:`tos.canonical._base.FrozenModel`, so **every** JSON-mode dump of a tos
artifact — ``covered_content()``, ``event_identity()``, the runtime's
``compute_digest(x.model_dump(mode="json"))`` call sites, ``model_dump_json()`` —
emits set elements in ``sorted()`` order without any call site knowing.

Two properties this module is responsible for:

* **JSON mode only.** Python-mode ``model_dump()`` keeps returning ``frozenset``
  objects; only ``info.mode == "json"`` output is reordered. Sorting is applied
  to the *serialized* list, and the *original* attribute value is walked beside
  it to decide **which** lists were sets (the wrap handler's output has already
  lost that distinction).
* **Conditional attachment.** A wrapping ``model_serializer`` replaces
  pydantic-core's native serializer with a Python callback for *every* dump of
  the class it is attached to, in python mode too (measured 4-7x on
  ``EngineEvent``). So the hook is attached in
  :meth:`CanonicalJsonMixin.__get_pydantic_core_schema__` **only** to classes
  whose own field schemas contain a set, and the set-bearing field names are
  precomputed there. A class with no set field keeps the native serializer and
  its pre-hook cost exactly.

Known silent-miss cases (all zero in today's kernel, each pinned by a test in
``tos/tests/canonical/test_canonical_json_set_order.py``):

* a set field carrying an ``alias`` / ``serialization_alias`` dumped with
  ``by_alias=True`` — the dumped key is not the field name, so the walk skips it;
* a plain ``BaseModel`` (not a :class:`~tos.canonical._base.FrozenModel`) nested
  inside a covered tree — it has no hook of its own;
* a container filtered by an index-level ``include`` / ``exclude`` — the walk
  refuses to pair a container whose dumped length differs from the original's,
  rather than risk sorting an order-significant sequence;
* **a set nested directly inside a set** — the set branch of
  :func:`_with_sorted_sets` sorts the dumped list and stops, because a set has
  no order to zip the dumped elements back against, so it cannot recurse into
  them. The inner sets stay in iteration order and the outer ``sorted()`` then
  orders seed-dependent values. Measured on this branch, 2026-09-24::

      class SetOfSets(FrozenModel):
          outer: frozenset[frozenset[str]] = frozenset()

      SetOfSets(outer=frozenset({frozenset(("b", "aa", "c", "dd", "zzz", "B")),
                                 frozenset(("q", "rr", "sss", "t", "uu", "v"))})
                ).model_dump(mode="json")
      # PYTHONHASHSEED=0 -> {'outer': [['q','sss','t','uu','v','rr'],
      #                                ['zzz','b','B','c','aa','dd']]}
      # PYTHONHASHSEED=1 -> {'outer': [['aa','zzz','B','b','dd','c'],
      #                                ['sss','t','rr','v','uu','q']]}

  Banned outright rather than handled, by
  ``test_no_set_is_nested_inside_a_set`` in
  ``tos/runtime/tests/canonical/test_canonical_json_closure.py``;
* a set field whose serialized value is **not a list** — the set branch returns
  a non-``list`` ``dumped`` unchanged (``:_with_sorted_sets``), so a field
  serializer rendering a set as a string or a mapping is left unsorted. Zero
  field serializers exist under ``tos/`` today.

Pure module: ``pydantic`` + stdlib only (design §0.3). It imports no ``tos``
module, so ``tos.canonical._base`` can depend on it without a cycle.
"""

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

#: Core-schema node types that ARE a set.
_SET_SCHEMA_TYPES: frozenset[str] = frozenset({"set", "frozenset"})

#: Core-schema node types the scan does not descend into. A nested model (or
#: dataclass) carries its own hook, and a ``definition-ref`` is a recursive model
#: reference; descending would double-count and, for a recursive model, not
#: terminate.
_OPAQUE_SCHEMA_TYPES: frozenset[str] = frozenset(
    {"model", "dataclass", "definition-ref"}
)

#: Core-schema keys that hold values, not sub-schemas. ``default`` holds a real
#: default object (a ``frozenset()`` default is a value, not a schema) and
#: ``metadata`` holds JSON-schema callbacks.
_NON_SCHEMA_KEYS: frozenset[str] = frozenset({"default", "metadata"})

#: Sentinel for "the model has no such attribute" (``None`` is a real value).
_ABSENT: object = object()


def _schema_declares_set(node: Any) -> bool:
    """Whether a core-schema fragment declares a set anywhere outside a nested model.

    Args:
        node: A core-schema fragment (dict), a list of fragments, or a leaf.

    Returns:
        ``True`` when a ``set`` / ``frozenset`` schema is reachable without
        crossing into a nested model, dataclass, or definition reference.
    """
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
    """Return the model's own field names whose type tree declares a set.

    Nested models are excluded on purpose: each one attaches (or does not attach)
    its own hook, so this class only has to reorder the sets it owns directly —
    including ones wrapped in ``Optional`` / unions / lists / tuples / dicts.

    Args:
        schema: The core schema produced for the model class.

    Returns:
        The field (and computed-field) names to walk, in declaration order.
    """
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
    """Sort the serialized lists whose original value was a set.

    ``original`` and ``dumped`` are the same node of the same value tree, before
    and after serialization. Only a node that *was* a set is reordered; a list or
    tuple keeps its order because the canonicalizer treats a sequence as
    order-significant.

    Args:
        original: The pre-serialization value (from ``getattr`` on the model).
        dumped: The serialized counterpart of ``original``.

    Returns:
        ``dumped`` with every originally-set node replaced by a sorted list. A
        set whose ``dumped`` counterpart is not a ``list`` is returned as-is —
        the module docstring's fourth silent-miss case.

    Raises:
        TypeError: When a set's elements are not mutually comparable. There is
            deliberately no fallback key: a fallback would make the ordering a
            function of the key rather than of the content, which is the defect
            this module exists to remove.
    """
    if isinstance(original, (set, frozenset)):
        # No recursion into the elements: a set has no order to pair them by.
        # A set nested in a set is banned instead (module docstring).
        return sorted(dumped) if isinstance(dumped, list) else dumped
    if isinstance(original, BaseModel):
        # The nested model's own hook (if any) already ordered its sets.
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
    """Wrapping model serializer: order JSON-mode set output deterministically.

    Args:
        model: The model instance being serialized.
        handler: The default serializer for this model.
        info: Serialization context; only ``mode`` is consulted.

    Returns:
        The default serialization, with every JSON-mode set rendered sorted.
    """
    dumped = handler(model)
    if info.mode != "json" or not isinstance(dumped, dict):
        return dumped
    set_fields: tuple[str, ...] = getattr(type(model), "__canonical_set_fields__", ())
    for name in set_fields:
        if name not in dumped:
            # by_alias=True (dumped key is the alias) or an excluded field.
            continue
        original = getattr(model, name, _ABSENT)
        if original is _ABSENT:
            continue
        dumped[name] = _with_sorted_sets(original, dumped[name])
    return dumped


#: The serialization core schema attached to set-bearing classes. Byte-identical
#: in shape to what ``@model_serializer(mode="wrap")`` with a ``dict[str, Any]``
#: return annotation produces; spelled as a literal so this module needs no
#: ``pydantic_core`` import (the tos AST firewall allows ``pydantic`` only).
#: Used as a TEMPLATE, never installed directly — see
#: :meth:`CanonicalJsonMixin.__get_pydantic_core_schema__`.
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
    """Whether a core-schema ``serialization`` entry is this module's own hook.

    pydantic hands back the class's cached core schema when the same model is
    reached a second time (e.g. as a union member), so the hook must recognise
    its own earlier attachment instead of mistaking it for a foreign serializer.

    Args:
        serialization: A core-schema ``serialization`` entry.

    Returns:
        ``True`` when the entry is the sorted-set wrapping serializer.
    """
    return (
        isinstance(serialization, dict)
        and serialization.get("function") is _dump_with_sorted_sets
    )


class CanonicalJsonMixin:
    """Attach deterministic JSON-mode set ordering to set-bearing models only.

    Mixed into :class:`tos.canonical._base.FrozenModel` on its class line, so
    every tos artifact inherits the behaviour. The hook itself is attached per
    class, during core-schema construction, and only when the class declares a
    set somewhere in its own field tree — a class with no set field keeps
    pydantic-core's native serializer and its pre-hook cost.
    """

    #: The class's own field names whose type tree declares a set. Empty unless
    #: the hook was attached (so it doubles as "is the hook active here").
    __canonical_set_fields__: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[Any], handler: GetCoreSchemaHandler
    ) -> Any:
        """Build the model schema, attaching the sort hook only when it is needed.

        Args:
            source: The model class the schema is being built for.
            handler: The next core-schema builder in the chain.

        Returns:
            The class's core schema, with a wrapping model serializer installed
            when the class declares at least one set field.

        Raises:
            TypeError: When a set-bearing class already declares its own
                ``@model_serializer``; installing this hook would silently drop
                it, and leaving it installed would silently drop the ordering.
        """
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
        # A per-class copy, not the module-level template: pydantic is free to
        # annotate a core-schema node in place, and a shared node would spread
        # that annotation to every other set-bearing class at once. Idempotency
        # does not depend on object identity — :func:`_is_this_hook` recognises
        # the attachment by the FUNCTION it carries, which the copy preserves.
        schema["serialization"] = dict(_SORTED_SET_SERIALIZATION)
        return schema
