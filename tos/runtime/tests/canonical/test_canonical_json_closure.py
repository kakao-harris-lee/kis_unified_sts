"""Tree closure for the canonical JSON set-ordering hook (plan §3, "목록 폐쇄")."""

from __future__ import annotations

import dataclasses
import sys
import typing
from pathlib import Path
from types import ModuleType

import tos_runtime.evidence.backup  # noqa: F401  # see _SHADOWED_SUBMODULE_NAMES
from pydantic import BaseModel
from tos.canonical import DigestBoundArtifact
from tos.canonical._base import FrozenModel
from tos.staterestore import _l3_worker as k_staterestore_l3_worker
from tos_runtime import (
    _named_tbd as r_named_tbd,
)
from tos_runtime import (
    authority as r_authority,
)
from tos_runtime import (
    backtest as r_backtest,
)
from tos_runtime import (
    brokercap as r_brokercap,
)
from tos_runtime import (
    calendar as r_calendar,
)
from tos_runtime import (
    compose as r_compose,
)
from tos_runtime import (
    currentness as r_currentness,
)
from tos_runtime import (
    custody as r_custody,
)
from tos_runtime import (
    engine as r_engine,
)
from tos_runtime import (
    evidence as r_evidence,
)
from tos_runtime import (
    marketfeed as r_marketfeed,
)
from tos_runtime import (
    operations as r_operations,
)
from tos_runtime import (
    operator as r_operator,
)
from tos_runtime import (
    posttrade as r_posttrade,
)
from tos_runtime import (
    rcl as r_rcl,
)
from tos_runtime import (
    recon as r_recon,
)
from tos_runtime import (
    recovery as r_recovery,
)
from tos_runtime import (
    release as r_release,
)
from tos_runtime import (
    risk as r_risk,
)
from tos_runtime import (
    riskstate as r_riskstate,
)
from tos_runtime import (
    safety as r_safety,
)
from tos_runtime import (
    strategy as r_strategy,
)
from tos_runtime import (
    time as r_time,
)
from tos_runtime import (
    transport as r_transport,
)
from tos_runtime import (
    venue as r_venue,
)
from tos_runtime import (
    venue_ledger as r_venue_ledger,
)
from tos_runtime.compose import _cli_ops as r_compose_cli_ops
from tos_runtime.compose import _construction_config as r_compose_construction_config
from tos_runtime.compose import _migrate_paths as r_compose_migrate_paths
from tos_runtime.compose import _run_dispatch as r_compose_run_dispatch
from tos_runtime.compose import cli as r_compose_cli
from tos_runtime.recon import (
    witness_synthetic_venue as r_recon_witness_synthetic_venue,
)
from tos_runtime.safety import ack as r_safety_ack

from tos import (
    afg as k_afg,
)
from tos import (
    are as k_are,
)
from tos import (
    authority as k_authority,
)
from tos import (
    backtest as k_backtest,
)
from tos import (
    brokeradapter as k_brokeradapter,
)
from tos import (
    brokercap as k_brokercap,
)
from tos import (
    canonical as k_canonical,
)
from tos import (
    capsule as k_capsule,
)
from tos import (
    cur as k_cur,
)
from tos import (
    dsl as k_dsl,
)
from tos import (
    egress as k_egress,
)
from tos import (
    egressgw as k_egressgw,
)
from tos import (
    engine as k_engine,
)
from tos import (
    evidence as k_evidence,
)
from tos import (
    iap as k_iap,
)
from tos import (
    ioc as k_ioc,
)
from tos import (
    marketfeed as k_marketfeed,
)
from tos import (
    ordering as k_ordering,
)
from tos import (
    orthostate as k_orthostate,
)
from tos import (
    position as k_position,
)
from tos import (
    posttrade as k_posttrade,
)
from tos import (
    rcl as k_rcl,
)
from tos import (
    recon as k_recon,
)
from tos import (
    staterestore as k_staterestore,
)
from tos import (
    time as k_time,
)
from tos import (
    venue as k_venue,
)
from tos import (
    workload as k_workload,
)

_IMPORTED_MODULES: tuple[ModuleType, ...] = (
    k_afg,
    k_are,
    k_authority,
    k_backtest,
    k_brokeradapter,
    k_brokercap,
    k_canonical,
    k_capsule,
    k_cur,
    k_dsl,
    k_egress,
    k_egressgw,
    k_engine,
    k_evidence,
    k_iap,
    k_ioc,
    k_marketfeed,
    k_ordering,
    k_orthostate,
    k_position,
    k_posttrade,
    k_rcl,
    k_recon,
    k_staterestore,
    k_time,
    k_venue,
    k_workload,
    r_named_tbd,
    r_authority,
    r_backtest,
    r_brokercap,
    r_calendar,
    r_compose,
    r_currentness,
    r_custody,
    r_engine,
    r_evidence,
    r_marketfeed,
    r_operations,
    r_operator,
    r_posttrade,
    r_rcl,
    r_recon,
    r_recovery,
    r_release,
    r_risk,
    r_riskstate,
    r_safety,
    r_strategy,
    r_time,
    r_transport,
    r_venue,
    r_venue_ledger,
    k_staterestore_l3_worker,
    r_compose_cli_ops,
    r_compose_construction_config,
    r_compose_migrate_paths,
    r_compose_run_dispatch,
    r_compose_cli,
    r_recon_witness_synthetic_venue,
    r_safety_ack,
)

_SRC_ROOTS: dict[str, Path] = {
    "tos": Path(k_canonical.__file__).resolve().parent.parent,
    "tos_runtime": Path(r_operations.__file__).resolve().parent.parent,
}

_MIN_TREE_SET_MODELS = 15
_MIN_DIRECT_SET_MODELS = 10
_MIN_COVERED_SET_MODELS = 5

_NON_FROZEN_ALLOWLIST: frozenset[str] = frozenset()

_SHADOWED_SUBMODULE_NAMES: tuple[str, ...] = ("tos_runtime.evidence.backup",)


def _module_names_on_disk() -> set[str]:
    """Every importable module name under the two source trees."""
    names: set[str] = set()
    for root_name, root in _SRC_ROOTS.items():
        for path in root.rglob("*.py"):
            parts = list(path.relative_to(root).parts)
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1][: -len(".py")]
            names.add(".".join([root_name, *parts]))
    return names


def _names_reachable_from_the_import_list() -> set[str]:
    """Module names reached by :data:`_IMPORTED_MODULES` **alone**."""
    reached: set[str] = set()
    pending: list[ModuleType] = [
        *_IMPORTED_MODULES,
        *(sys.modules[name] for name in _SHADOWED_SUBMODULE_NAMES),
    ]
    while pending:
        module = pending.pop()
        name = getattr(module, "__name__", "")
        if name in reached or name.split(".")[0] not in _SRC_ROOTS:
            continue
        reached.add(name)
        pending.extend(
            value for value in vars(module).values() if isinstance(value, ModuleType)
        )
    return reached


def _all_models() -> list[type[BaseModel]]:
    """Every loaded pydantic model, deduplicated, in a stable order."""
    seen: dict[int, type[BaseModel]] = {}

    def walk(cls: type[BaseModel]) -> None:
        for sub in cls.__subclasses__():
            if id(sub) not in seen:
                seen[id(sub)] = sub
                walk(sub)

    walk(BaseModel)
    return sorted(seen.values(), key=lambda c: f"{c.__module__}.{c.__qualname__}")


def _tos_models() -> list[type[BaseModel]]:
    """The loaded models that belong to the two distributions."""
    return [m for m in _all_models() if m.__module__.split(".")[0] in _SRC_ROOTS]


def _annotation_has_set(annotation: object, stack: tuple[type, ...]) -> bool:
    """Whether an annotation's tree reaches a set (recursing through models)."""
    origin = typing.get_origin(annotation)
    if origin in (set, frozenset):
        return True
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _tree_has_set(annotation, stack)
    return any(_annotation_has_set(arg, stack) for arg in typing.get_args(annotation))


def _tree_has_set(model_cls: type[BaseModel], stack: tuple[type, ...] = ()) -> bool:
    """Whether the model's whole field tree reaches a set."""
    if model_cls in stack:
        return False
    return any(
        _annotation_has_set(field.annotation, (*stack, model_cls))
        for field in model_cls.model_fields.values()
    )


def _qualified(model_cls: type[BaseModel]) -> str:
    """Dotted name used in assertion messages and the allowlist."""
    return f"{model_cls.__module__}.{model_cls.__qualname__}"


def test_every_module_is_imported() -> None:
    """The written-out import list covers the whole source tree."""
    assert len(_IMPORTED_MODULES) >= 61
    on_disk = _module_names_on_disk()
    unreached = sorted(
        on_disk - _names_reachable_from_the_import_list() - set(_SRC_ROOTS)
    )
    assert unreached == [], (
        "these modules are not reached by the explicit import list at the top "
        f"of this file (add them to it): {unreached}"
    )
    missing = sorted(name for name in on_disk if name not in sys.modules)
    assert (
        missing == []
    ), f"these modules were never imported in this session at all: {missing}"


def test_every_set_bearing_model_is_a_frozen_model() -> None:
    """A set inside a plain ``BaseModel`` would dump unsorted, with no warning."""
    offenders = sorted(
        _qualified(model_cls)
        for model_cls in _tos_models()
        if _tree_has_set(model_cls)
        and not issubclass(model_cls, FrozenModel)
        and _qualified(model_cls) not in _NON_FROZEN_ALLOWLIST
    )
    assert offenders == [], (
        "these models hold a set but do not inherit the canonical JSON hook "
        f"from FrozenModel: {offenders}"
    )


def test_the_closure_actually_found_the_models() -> None:
    """Lower bounds: an enumeration that sees nothing must not read as clean."""
    models = _tos_models()
    tree_set = [m for m in models if _tree_has_set(m)]
    direct_set = [m for m in models if getattr(m, "__canonical_set_fields__", ())]
    covered_set = [
        m
        for m in models
        if issubclass(m, DigestBoundArtifact)
        and getattr(m, "_COVERED_FIELDS", None)
        and any(
            _annotation_has_set(field.annotation, (m,))
            for name, field in m.model_fields.items()
            if name in set(m._COVERED_FIELDS)
        )
    ]
    assert len(tree_set) >= _MIN_TREE_SET_MODELS
    assert len(direct_set) >= _MIN_DIRECT_SET_MODELS
    assert len(covered_set) >= _MIN_COVERED_SET_MODELS


def test_no_set_field_anywhere_carries_an_alias() -> None:
    """``by_alias=True`` on an aliased set field skips the sort silently."""
    offenders: dict[str, list[str]] = {}
    for model_cls in _tos_models():
        aliased = [
            name
            for name in getattr(model_cls, "__canonical_set_fields__", ())
            if (field := model_cls.model_fields.get(name)) is not None
            and (field.alias or field.serialization_alias or field.validation_alias)
        ]
        if aliased:
            offenders[_qualified(model_cls)] = aliased
    assert offenders == {}, (
        "a set field with an alias is left unsorted by the canonical JSON hook: "
        f"{offenders}"
    )


def _reaches_a_set_without_crossing_a_model(annotation: object) -> bool:
    """Whether an annotation reaches a set without entering a nested model."""
    if typing.get_origin(annotation) in (set, frozenset):
        return True
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return False
    return any(
        _reaches_a_set_without_crossing_a_model(arg)
        for arg in typing.get_args(annotation)
    )


def _nested_set_annotations(annotation: object) -> bool:
    """Whether a set in this annotation tree holds another set."""
    args = typing.get_args(annotation)
    if typing.get_origin(annotation) in (set, frozenset):
        return any(_reaches_a_set_without_crossing_a_model(arg) for arg in args)
    return any(_nested_set_annotations(arg) for arg in args)


def test_no_set_is_nested_inside_a_set() -> None:
    """A set inside a set escapes the sort silently, in the seed-dependent direction."""
    offenders: dict[str, list[str]] = {}
    for model_cls in _tos_models():
        nested = sorted(
            name
            for name, field in model_cls.model_fields.items()
            if _nested_set_annotations(field.annotation)
        )
        if nested:
            offenders[_qualified(model_cls)] = nested
    assert offenders == {}, (
        "these fields nest a set inside a set, which the canonical JSON hook "
        f"leaves partly unsorted: {offenders}"
    )


def _opaque_leaf_kind(annotation: object) -> str | None:
    """Name the stdlib aggregate kind of ``annotation``, or ``None``."""
    if typing.is_typeddict(annotation):
        return "TypedDict"
    if not isinstance(annotation, type):
        return None
    if issubclass(annotation, BaseModel):
        return None
    if issubclass(annotation, tuple) and hasattr(annotation, "_fields"):
        return "NamedTuple"
    if dataclasses.is_dataclass(annotation):
        return "dataclass"
    return None


def _opaque_leaves(annotation: object) -> list[str]:
    """Every stdlib dataclass / NamedTuple / TypedDict in an annotation tree."""
    kind = _opaque_leaf_kind(annotation)
    if kind is not None:
        return [f"{kind}:{getattr(annotation, '__name__', annotation)}"]
    found: list[str] = []
    for arg in typing.get_args(annotation):
        found.extend(_opaque_leaves(arg))
    return found


def test_no_model_field_tree_holds_a_stdlib_aggregate() -> None:
    """A stdlib dataclass / NamedTuple / TypedDict field is a double blind spot."""
    offenders: dict[str, dict[str, list[str]]] = {}
    for model_cls in _tos_models():
        found = {
            name: leaves
            for name, field in model_cls.model_fields.items()
            if (leaves := _opaque_leaves(field.annotation))
        }
        if found:
            offenders[_qualified(model_cls)] = found
    assert offenders == {}, (
        "these fields hold a stdlib dataclass/NamedTuple/TypedDict, which both "
        f"the set scan and the model enumeration walk past: {offenders}"
    )
