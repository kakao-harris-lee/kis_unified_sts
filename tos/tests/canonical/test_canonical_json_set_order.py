"""Canonical JSON set ordering — the single-process pins (plan §3).

The cross-process pins (five ``PYTHONHASHSEED`` values, real subprocesses) live in
``tests/tools/test_tos_canonical_set_order.py``: ``subprocess`` is firewall-
forbidden under ``tos/`` (``tools/tos_firewall_check.py`` TOS-FW-B), so the seed
sweep has to be driven from outside the kernel. Everything that does **not** need
a second process is pinned here.

Plan: ``docs/plans/2026-09-24-tos-canonical-set-order-plan.md``.
"""

from __future__ import annotations

import statistics
import timeit
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict
from tos.canonical import EV_L1_PROVISIONAL_VERSION, DigestBoundArtifact, get_scheme
from tos.canonical._base import FrozenModel
from tos.canonical._canonical_json import CanonicalJsonMixin, _is_this_hook
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


class _PlainNoSetsToo(BaseModel):
    """A second, identical copy of ``_PlainNoSets`` — the noise floor's other side.

    Two classes with no hook on either, so any ratio this pair reads other than
    1.00 is the runner's, not the hook's (``_noise_floor``).
    """

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


def test_each_set_bearing_class_owns_its_serialization_node() -> None:
    """No two classes share the schema node the hook installs — review-802 LOW-5.

    pydantic may annotate a core-schema node in place; a node shared by every
    set-bearing class would spread that annotation to all of them at once. The
    node is a per-class copy, and the copy must still carry the same FUNCTION,
    which is what :func:`_is_this_hook` recognises an earlier attachment by.
    """
    mine = _WithSet.__pydantic_core_schema__["serialization"]
    theirs = _Nested.__pydantic_core_schema__["serialization"]
    assert mine is not theirs
    assert mine == theirs
    assert _is_this_hook(mine) and _is_this_hook(theirs)


def test_a_cached_schema_re_entered_through_a_union_stays_idempotent() -> None:
    """A set-bearing model reached again as a union member must not be refused.

    pydantic hands back the class's CACHED core schema the second time it is
    reached, with this hook's ``serialization`` already on it. If the hook did
    not recognise its own attachment — the copy above changes object identity,
    so recognition has to be by function — it would read it as a foreign
    ``model_serializer`` and raise the conflict ``TypeError`` at class-definition
    time. Defining the holder below is the whole assertion.
    """

    class _UnionHolder(FrozenModel):
        first: _WithSet | _Nested | None = None
        second: _WithSet | None = None

    holder = _UnionHolder(
        first=_WithSet(), second=_WithSet(s=frozenset(MIXED_LENGTH_ELEMENTS[:6]))
    )
    expected = sorted(MIXED_LENGTH_ELEMENTS[:6])
    dumped = holder.model_dump(mode="json")
    assert dumped["first"]["s"] == expected
    assert dumped["second"]["s"] == expected
    assert _is_this_hook(_WithSet.__pydantic_core_schema__["serialization"])


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


#: Paired-measurement shape. 21 rounds so the median has a unique middle; 500
#: calls per round so a round is short enough that a scheduler excursion hits one
#: round, not the whole measurement.
_COST_ROUNDS = 21
_COST_CALLS = 500


def _dump_cost_ratio(model: BaseModel, baseline: BaseModel, mode: str) -> float:
    """Median of per-round cost ratios — ``model`` over ``baseline``.

    review-802 MEDIUM-1: the previous shape measured each side to completion and
    divided the two minima, which made the ratio a function of what the runner
    was doing BETWEEN the two measurements. Measured over 60 repetitions on an
    idle host, a control of ``_PlainNoSets`` against an identical second plain
    class — no hook on either side, so the true ratio is 1.00 — spread 0.42 to
    2.73 and crossed the old 1.6 bound 1-2 times in 60. The bound was therefore
    not measuring the hook.

    Two changes fix it. The two sides are measured in the SAME round, adjacent in
    time, so a frequency or scheduler excursion moves both. And the per-round
    ratios are reduced by MEDIAN, not by taking a minimum of each side
    independently, so a single bad round cannot move the answer. Same 60
    repetitions with this shape: control 0.910-1.073, set-free 0.895-1.097,
    set-bearing 1.683-2.683.
    """
    ratios = []
    for _ in range(_COST_ROUNDS):
        hooked = timeit.timeit(lambda: model.model_dump(mode=mode), number=_COST_CALLS)
        plain = timeit.timeit(
            lambda: baseline.model_dump(mode=mode), number=_COST_CALLS
        )
        ratios.append(hooked / plain)
    return statistics.median(ratios)


def _noise_floor(mode: str) -> float:
    """The same measurement run against two classes that are genuinely identical.

    Whatever this reads above 1.00 is the runner's own asymmetry, not a hook.
    """
    return _dump_cost_ratio(_PlainNoSets(), _PlainNoSetsToo(), mode)


@pytest.mark.parametrize("mode", ["python", "json"])
def test_classes_without_sets_pay_nothing_for_the_hook(mode: str) -> None:
    """A set-free ``FrozenModel`` dumps as fast as the same model without the mixin.

    This is the plan §2.1 exit condition. The GATE is structural and has a
    concrete failing input: attaching the hook unconditionally — the shape the
    plan rejects — leaves a ``serialization`` entry on a set-free class's core
    schema, and that is a fact about the schema, not about a stopwatch.

    The cost bound corroborates it, and is stated relative to a measured noise
    floor (control = plain against an identical plain class) so a loaded runner
    loosens it instead of failing it. Both halves are RED under the unconditional
    attachment mutation: the structural one always, and the cost one because the
    set-free ratio then lands in the set-bearing band (>= 1.68 measured).
    """
    assert _NoSets.__pydantic_core_schema__.get("serialization") is None, (
        "a set-free FrozenModel kept a serialization entry — the hook attached "
        "where it must not, and every dump of every such class now pays for a "
        "Python callback"
    )

    floor = _noise_floor(mode)
    ratio = _dump_cost_ratio(_NoSets(), _PlainNoSets(), mode)
    bound = 1.35 * max(1.0, floor)
    assert ratio <= bound, (
        f"set-free FrozenModel dump is {ratio:.2f}x the plain cost, over the "
        f"{bound:.2f}x bound (noise floor {floor:.2f}x)"
    )


@pytest.mark.parametrize("mode", ["python", "json"])
def test_the_cost_pin_can_actually_see_the_hook(mode: str) -> None:
    """Positive control: the set-bearing model IS measurably slower.

    Without this, ``test_classes_without_sets_pay_nothing_for_the_hook`` could be
    green because the measurement is blind rather than because the hook is
    absent — the failure shape this repo keeps meeting. Lowest of 60 repetitions
    with the paired estimator: 1.68 (python) / 2.40 (json).
    """
    ratio = _dump_cost_ratio(_WithSet(), _PlainWithSet(), mode)
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
