"""Canonical JSON set ordering — the single-process pins (plan §3).

The cross-process pins (five ``PYTHONHASHSEED`` values, real subprocesses) live in
``tests/tools/test_tos_canonical_set_order.py``: ``subprocess`` is firewall-
forbidden under ``tos/`` (``tools/tos_firewall_check.py`` TOS-FW-B), so the seed
sweep has to be driven from outside the kernel. Everything that does **not** need
a second process is pinned here.

Plan: ``docs/plans/2026-09-24-tos-canonical-set-order-plan.md``.
"""

from __future__ import annotations

import timeit
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict
from tos.canonical import EV_L1_PROVISIONAL_VERSION, DigestBoundArtifact, get_scheme
from tos.canonical._base import FrozenModel
from tos.canonical._canonical_json import CanonicalJsonMixin
from tos.liveauth.records import LiveAuthorization, ReArmApprovalRecord

from ._set_order_builders import (
    CONTROL_KEY,
    COVERED_SET_MODELS,
    MIXED_LENGTH_ELEMENTS,
    PREVIOUSLY_SORTED_MODELS,
    build_instance,
    digest_map,
)

#: Digests of the eight models that already sorted their own sets, measured on
#: ``origin/main`` ``153c8fd0`` (before this change) with the builders in
#: ``_set_order_builders.py``. The mixed-length elements matter: with same-length
#: elements a length-first sort key and a lexicographic one agree, and the "wrong
#: key" mutation would pass (review-798 2차 M-3(a)).
#:
#: To re-derive after a deliberate field change on one of these models, run the
#: worker against the model tree and read the printed digest:
#:     PYTHONPATH=tos/src python -m tests.canonical._set_order_worker   # from tos/
_PRE_HOOK_GOLDEN: dict[str, str] = {
    "CurrentnessPolicy": "70219489496fd2226b8c8ee70c98ec8a7708eed2ff7ea533fcf43adbacc3650b",
    "LiveAuthorization": "8f821b530e86c82121402c0fdb2adad36410cdee7931d3eff5a8bf50c61eaf32",
    "ReArmApprovalRecord": "d0b7ac035d8f5fca38ed69b124e836b21eef388c47513f29fe8754fe075df769",
    "RestrictiveFenceRecord": "85c35e3f7a2d0714772bba563c18572b78428867a1c46e7da6bfca504c77a313",
    "SafetyDeviationPolicy": "b3e6c02605e96160f54160f08756f942f37dfde68085b80f5222c1131be4e3ff",
    "SafetyIncidentPolicy": "ea884e0030a0bd73dd02180fffb058905fd1c6ef2afc7dd33ddd9efe89693874",
    "TrialEvidencePackage": "967ce2e0a0904f91453f16009f31203d8670d212a581456b3dd17932532a4ab8",
    "TrialPolicy": "c9f1038ed4dbdee47e8000aa7d3ab06a5cd6d9e500dff81d06e4b6a98f5eec80",
}

#: The two models whose PYTHON-mode dump deliberately CHANGED with this work: a
#: ``field_serializer(..., when_used="always")`` used to sort their scope
#: dimensions in every mode, so python-mode callers saw sorted lists. The shared
#: hook is json-mode only, so python mode now returns the ``frozenset`` itself.
#: Nothing reads it — ``tos/src`` and ``tos/runtime/src`` make zero python-mode
#: ``model_dump()`` calls (review-798 3차 L-1) — and the json bytes are identical.
_PYTHON_MODE_CHANGED: frozenset[str] = frozenset(
    {"LiveAuthorization", "ReArmApprovalRecord"}
)


# --------------------------------------------------------------------------
# Synthetic models — the hook's contract, independent of any kernel artifact
# --------------------------------------------------------------------------


class _Leaf(FrozenModel):
    """A nested frozen model with its own set."""

    leaf_set: frozenset[str] = frozenset()


class _Nested(FrozenModel):
    """Every container shape a covered tree can put a set in."""

    plain: frozenset[str] = frozenset()
    optional: frozenset[str] | None = None
    in_list: list[frozenset[str]] = []
    in_tuple: tuple[frozenset[str], ...] = ()
    in_dict: dict[str, frozenset[str]] = {}
    ordered: tuple[str, ...] = ()
    leaf: _Leaf | None = None


class _NoSets(FrozenModel):
    """A frozen model with no set anywhere — the hook must not attach."""

    a: str = "x"
    b: int = 1
    c: tuple[str, ...] = ("p", "q")


class _PlainNoSets(BaseModel):
    """``_NoSets`` without the mixin — the cost baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    a: str = "x"
    b: int = 1
    c: tuple[str, ...] = ("p", "q")


class _WithSet(FrozenModel):
    """``_NoSets`` plus one set field — the hook attaches here."""

    a: str = "x"
    b: int = 1
    s: frozenset[str] = frozenset(MIXED_LENGTH_ELEMENTS[:6])


class _PlainWithSet(BaseModel):
    """``_WithSet`` without the mixin — the cost baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    a: str = "x"
    b: int = 1
    s: frozenset[str] = frozenset(MIXED_LENGTH_ELEMENTS[:6])


class _Incomparable(FrozenModel):
    """Hashable but not mutually comparable elements — ``sorted()`` must raise."""

    mixed: frozenset[str | None] = frozenset()


# --------------------------------------------------------------------------
# Hook behaviour
# --------------------------------------------------------------------------


def test_json_mode_sorts_sets_in_every_container_shape() -> None:
    """Every originally-set node comes out sorted; sequences keep their order."""
    elements = MIXED_LENGTH_ELEMENTS[:6]
    model = _Nested(
        plain=frozenset(elements),
        optional=frozenset(elements),
        in_list=[frozenset(elements)],
        in_tuple=(frozenset(elements),),
        in_dict={"k": frozenset(elements)},
        ordered=("z", "a", "m"),
        leaf=_Leaf(leaf_set=frozenset(elements)),
    )
    expected = sorted(elements)
    dumped = model.model_dump(mode="json")

    assert dumped["plain"] == expected
    assert dumped["optional"] == expected
    assert dumped["in_list"][0] == expected
    assert dumped["in_tuple"][0] == expected
    assert dumped["in_dict"]["k"] == expected
    assert dumped["leaf"]["leaf_set"] == expected
    # A tuple is order-significant to the canonicalizer and must NOT be sorted.
    assert dumped["ordered"] == ["z", "a", "m"]


def test_model_dump_json_takes_the_same_hook() -> None:
    """``model_dump_json()`` is a json-mode dump and must sort identically."""
    model = _Nested(plain=frozenset(MIXED_LENGTH_ELEMENTS[:6]))
    as_text = model.model_dump_json()
    expected = sorted(MIXED_LENGTH_ELEMENTS[:6])
    assert f'"plain":{expected}'.replace("'", '"').replace(" ", "") in as_text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"include": {"plain"}},
        {"exclude": {"optional"}},
        {"exclude_none": True},
        {"exclude_defaults": True},
        {"round_trip": True},
    ],
)
def test_json_mode_sorting_survives_dump_options(kwargs: dict[str, Any]) -> None:
    """``covered_content()`` dumps with ``include=``; the options must not disarm it."""
    model = _Nested(plain=frozenset(MIXED_LENGTH_ELEMENTS[:6]))
    dumped = model.model_dump(mode="json", **kwargs)
    assert dumped["plain"] == sorted(MIXED_LENGTH_ELEMENTS[:6])


def test_python_mode_keeps_sets_as_sets() -> None:
    """The hook is json-mode only; python-mode output is untouched."""
    elements = frozenset(MIXED_LENGTH_ELEMENTS[:6])
    model = _Nested(plain=elements, leaf=_Leaf(leaf_set=elements))
    dumped = model.model_dump()
    assert dumped["plain"] == elements
    assert dumped["leaf"]["leaf_set"] == elements


@pytest.mark.parametrize("model_cls", COVERED_SET_MODELS, ids=lambda c: c.__name__)
def test_covered_models_keep_frozensets_in_python_mode(
    model_cls: type[DigestBoundArtifact],
) -> None:
    """Python-mode dumps of the 19 covered models still carry ``frozenset`` values.

    ``LiveAuthorization`` / ``ReArmApprovalRecord`` are the deliberate change
    (see ``_PYTHON_MODE_CHANGED``): they used to return sorted lists in python
    mode too, and now return the sets. This test asserts the NEW expectation for
    all 19 uniformly, and the docstring records why two of them moved.
    """
    instance = build_instance(model_cls)
    dumped = instance.model_dump()
    found = _find_container_types(dumped)
    assert frozenset in found or set in found, (
        f"{model_cls.__name__} python-mode dump has no set left; the hook must "
        "not touch python mode"
    )


def _find_container_types(node: Any, seen: set[type] | None = None) -> set[type]:
    """Collect the container types present anywhere in a dumped value tree."""
    found = set() if seen is None else seen
    if isinstance(node, (set, frozenset)):
        found.add(type(node))
        return found
    if isinstance(node, dict):
        for value in node.values():
            _find_container_types(value, found)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _find_container_types(value, found)
    return found


def test_liveauth_python_mode_change_is_the_expected_one() -> None:
    """The two models whose python-mode output moved, named explicitly."""
    for model_cls in (LiveAuthorization, ReArmApprovalRecord):
        assert model_cls.__name__ in _PYTHON_MODE_CHANGED
        instance = build_instance(model_cls)
        scope_field = (
            "live_authorization_scope"
            if model_cls is LiveAuthorization
            else "requested_scope"
        )
        scope = instance.model_dump()[scope_field]
        assert isinstance(scope["accounts"], frozenset)


def test_incomparable_set_elements_raise_without_a_fallback_key() -> None:
    """``frozenset[str | None]`` is hashable but not sortable — the hook must raise.

    A ``key=str`` fallback would make the digest a function of the key rather
    than of the content, so there deliberately is none. A ``frozenset`` of nested
    models cannot exercise this (it dies earlier, unhashable) — review-798 2차
    M-3(b). pydantic re-raises the hook's ``TypeError`` wrapped in a
    ``PydanticSerializationError`` (a ``ValueError``), naming it in the message.
    """
    model = _Incomparable(mixed=frozenset({"a", None}))
    with pytest.raises(ValueError) as raised:
        model.model_dump(mode="json")
    message = str(raised.value)
    assert "TypeError" in message
    assert "not supported between" in message


# --------------------------------------------------------------------------
# Conditional attachment
# --------------------------------------------------------------------------


def test_hook_attaches_only_to_set_bearing_classes() -> None:
    """A class with no set keeps pydantic-core's native serializer."""
    assert _NoSets.__canonical_set_fields__ == ()
    assert _NoSets.__pydantic_core_schema__.get("serialization") is None
    assert _WithSet.__canonical_set_fields__ == ("s",)
    assert _WithSet.__pydantic_core_schema__["serialization"]["type"] == "function-wrap"


def test_frozen_model_itself_carries_no_hook() -> None:
    """``FrozenModel`` has no fields, so the mixin must leave it alone."""
    assert FrozenModel.__canonical_set_fields__ == ()
    assert DigestBoundArtifact.__canonical_set_fields__ == ()


def test_set_bearing_class_with_its_own_model_serializer_is_refused() -> None:
    """Both serializers cannot coexist; the class definition fails loudly."""
    from pydantic import SerializerFunctionWrapHandler, model_serializer

    with pytest.raises(TypeError, match="model serializer"):

        class _Conflicting(FrozenModel):
            s: frozenset[str] = frozenset()

            @model_serializer(mode="wrap")
            def _ser(
                self, handler: SerializerFunctionWrapHandler
            ) -> dict[str, Any]:  # pragma: no cover - never reached
                return dict(handler(self))


def _dump_cost(model: BaseModel, mode: str) -> float:
    """Best-of-rounds seconds per ``model_dump`` call (minimum absorbs runner noise)."""
    return min(
        timeit.timeit(lambda: model.model_dump(mode=mode), number=2000) / 2000
        for _ in range(5)
    )


@pytest.mark.parametrize("mode", ["python", "json"])
def test_classes_without_sets_pay_nothing_for_the_hook(mode: str) -> None:
    """A set-free ``FrozenModel`` dumps as fast as the same model without the mixin.

    This is the plan §2.1 exit condition, stated as a RATIO so it survives a slow
    or noisy runner. Attaching the hook unconditionally (the shape the plan
    rejects) turns the native serializer into a Python callback for every model
    and takes this ratio well past the bound — measured 2.1x (python) / 3.0x
    (json) on the set-bearing control below.
    """
    ratio = _dump_cost(_NoSets(), mode) / _dump_cost(_PlainNoSets(), mode)
    assert ratio < 1.6, f"set-free FrozenModel dump is {ratio:.2f}x the plain cost"


@pytest.mark.parametrize("mode", ["python", "json"])
def test_the_cost_pin_can_actually_see_the_hook(mode: str) -> None:
    """Positive control: the set-bearing model IS measurably slower.

    Without this, ``test_classes_without_sets_pay_nothing_for_the_hook`` could be
    green because the measurement is blind rather than because the hook is
    absent — the failure shape this repo keeps meeting.
    """
    ratio = _dump_cost(_WithSet(), mode) / _dump_cost(_PlainWithSet(), mode)
    assert ratio > 1.3, f"the hook costs nothing measurable ({ratio:.2f}x)"


# --------------------------------------------------------------------------
# Digest pins
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_cls", PREVIOUSLY_SORTED_MODELS, ids=lambda c: c.__name__
)
def test_previously_sorted_models_are_bit_compatible(
    model_cls: type[DigestBoundArtifact],
) -> None:
    """The eight models that already sorted keep their exact pre-hook digest.

    RED when the hook orders sets by anything other than ``sorted()`` — the eight
    per-model sorters this change deleted used plain ``sorted()``, so any other
    key (a length-first canonical token, say) moves these bytes.
    """
    scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
    instance = build_instance(model_cls)
    digest = scheme.compute_digest(instance.covered_content())
    assert digest == _PRE_HOOK_GOLDEN[model_cls.__name__], (
        f"{model_cls.__name__} digest moved. If a covered field was added or "
        "removed on purpose, re-derive the golden (see _PRE_HOOK_GOLDEN); "
        "otherwise the set ordering key changed and the change is not "
        "bit-compatible."
    )


def test_digest_map_covers_every_pinned_surface() -> None:
    """The cross-process worker measures all 19 models plus both non-covered shapes."""
    digests = digest_map()
    expected = {model.__name__ for model in COVERED_SET_MODELS} | {
        "EngineEvent.event_identity",
        "EngineEvent.payload_digest",
        CONTROL_KEY,
    }
    assert set(digests) == expected
    assert len(COVERED_SET_MODELS) == 19


# --------------------------------------------------------------------------
# Alias ban — the hook's one silent-miss case that new code could introduce
# --------------------------------------------------------------------------


def _aliased_set_fields(model_cls: type[BaseModel]) -> list[str]:
    """Set-bearing fields of ``model_cls`` that carry any alias."""
    names = getattr(model_cls, "__canonical_set_fields__", ())
    aliased = []
    for name in names:
        field = model_cls.model_fields.get(name)
        if field is None:
            continue
        if field.alias or field.serialization_alias or field.validation_alias:
            aliased.append(name)
    return aliased


def _all_frozen_model_subclasses() -> list[type[FrozenModel]]:
    """Every loaded :class:`FrozenModel` subclass, deduplicated."""
    seen: dict[int, type[FrozenModel]] = {}

    def walk(cls: type[FrozenModel]) -> None:
        for sub in cls.__subclasses__():
            if id(sub) not in seen:
                seen[id(sub)] = sub
                walk(sub)

    walk(FrozenModel)
    return list(seen.values())


def test_no_set_field_carries_an_alias() -> None:
    """``by_alias=True`` would dump the alias as the key and skip the sort.

    The walk pairs the dumped key with ``getattr(model, key)``, so an aliased set
    field is simply not found and stays unsorted, with no warning. Forbidding the
    alias is cheaper than teaching the hook about them (there are zero today).
    """
    offenders = {
        f"{cls.__module__}.{cls.__qualname__}": aliased
        for cls in _all_frozen_model_subclasses()
        if (aliased := _aliased_set_fields(cls))
    }
    assert offenders == {}, (
        "a set field with an alias is silently left unsorted by the canonical "
        f"JSON hook: {offenders}"
    )


def test_the_mixin_is_on_frozen_model() -> None:
    """The wiring itself — ``FrozenModel`` must inherit the mixin."""
    assert issubclass(FrozenModel, CanonicalJsonMixin)
