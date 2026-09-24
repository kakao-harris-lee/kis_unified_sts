"""Tree closure for the canonical JSON set-ordering hook (plan §3, "목록 폐쇄").

The hook on :class:`tos.canonical.FrozenModel` orders a model's own sets. A
nested pydantic model that is **not** a ``FrozenModel`` has no hook of its own,
so a set it holds would be dumped in iteration order and silently re-open the
non-determinism this plan closed (review-798 3차 M-2, silent-miss case 2). This
file is the guard: it enumerates every pydantic model in **both** distributions
and refuses any set-bearing model that is not a ``FrozenModel`` subclass.

Why this file lives in the runtime test tree: it has to see ``tos`` *and*
``tos_runtime``, and a kernel-scope file importing ``tos_runtime`` is firewall
rule (g)/TOS-FW-G. Why the imports below are written out one by one: dynamic
import (``importlib.import_module`` / ``__import__``) is firewall rule
(d)/TOS-FW-D, and an enumeration that silently fails to import a module reports
"no offenders" for the wrong reason. :func:`test_every_module_is_imported`
compares the written-out list against the source tree, so a new module is a
RED here rather than a silent gap.
"""

from __future__ import annotations

import sys
import typing
from pathlib import Path
from types import ModuleType

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
    nontrade as r_nontrade,
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
from tos_runtime.compose import _cli_ops as r_compose_cli_ops
from tos_runtime.compose import _construction_config as r_compose_construction_config
from tos_runtime.compose import _migrate_paths as r_compose_migrate_paths
from tos_runtime.compose import (
    _nontrade_eval_dispatch as r_compose_nontrade_eval_dispatch,
)
from tos_runtime.compose import _run_dispatch as r_compose_run_dispatch
from tos_runtime.compose import cli as r_compose_cli
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
    failuredomain as k_failuredomain,
)
from tos import (
    hag as k_hag,
)
from tos import (
    iap as k_iap,
)
from tos import (
    ioc as k_ioc,
)
from tos import (
    liveauth as k_liveauth,
)
from tos import (
    marketfeed as k_marketfeed,
)
from tos import (
    nontrade as k_nontrade,
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
    protective as k_protective,
)
from tos import (
    rcl as k_rcl,
)
from tos import (
    recon as k_recon,
)
from tos import (
    replacement as k_replacement,
)
from tos import (
    rlp as k_rlp,
)
from tos import (
    sbr as k_sbr,
)
from tos import (
    sci as k_sci,
)
from tos import (
    sir as k_sir,
)
from tos import (
    spg as k_spg,
)
from tos import (
    staterestore as k_staterestore,
)
from tos import (
    stm as k_stm,
)
from tos import (
    time as k_time,
)
from tos import (
    venue as k_venue,
)
from tos import (
    wdr as k_wdr,
)
from tos import (
    workload as k_workload,
)

#: Every module under ``tos`` and ``tos_runtime``, imported by name.
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
    k_failuredomain,
    k_hag,
    k_iap,
    k_ioc,
    k_liveauth,
    k_marketfeed,
    k_nontrade,
    k_ordering,
    k_orthostate,
    k_position,
    k_posttrade,
    k_protective,
    k_rcl,
    k_recon,
    k_replacement,
    k_rlp,
    k_sbr,
    k_sci,
    k_sir,
    k_spg,
    k_staterestore,
    k_stm,
    k_time,
    k_venue,
    k_wdr,
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
    r_nontrade,
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
    k_staterestore_l3_worker,
    r_compose_cli_ops,
    r_compose_construction_config,
    r_compose_migrate_paths,
    r_compose_nontrade_eval_dispatch,
    r_compose_run_dispatch,
    r_compose_cli,
    r_safety_ack,
)

#: The two source trees this closure covers, located from an imported module of
#: each so the paths follow the installed distribution rather than a guess.
_SRC_ROOTS: dict[str, Path] = {
    "tos": Path(k_canonical.__file__).resolve().parent.parent,
    "tos_runtime": Path(r_operations.__file__).resolve().parent.parent,
}

#: Lower bounds measured on this branch (2026-09-24). Asserted as bounds, not
#: equalities, so adding a model is not a spurious RED — but an import that
#: silently fails and leaves the enumeration near zero still goes RED.
_MIN_TREE_SET_MODELS = 59
_MIN_DIRECT_SET_MODELS = 41
_MIN_COVERED_SET_MODELS = 19

#: Models allowed to hold a set without being a ``FrozenModel``. Empty today;
#: every entry needs a one-line reason for why its sets never reach a digest.
_NON_FROZEN_ALLOWLIST: frozenset[str] = frozenset()


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
    """The written-out import list covers the whole source tree.

    A new module that nothing imports would leave its models invisible to the
    closure below, which would then report "no offenders" without having looked.
    """
    assert len(_IMPORTED_MODULES) >= 74
    missing = sorted(
        name for name in _module_names_on_disk() if name not in sys.modules
    )
    assert missing == [], (
        "these modules are not reached by the explicit import list at the top "
        f"of this file: {missing}"
    )


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
