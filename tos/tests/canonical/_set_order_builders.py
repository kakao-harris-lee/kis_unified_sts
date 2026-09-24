"""Representative instances for the canonical set-ordering pins (plan §3).

Every pin in ``test_canonical_json_set_order.py`` (single process) and in
``tests/tos_l3/test_tos_canonical_set_order.py`` (many processes, many
``PYTHONHASHSEED`` values) measures the *same* instances, built here.

Two properties the builders must have, both of them review findings:

* **Mixed-length set elements.** Sorting by a length-first key and sorting
  lexicographically agree on same-length elements, so a golden built from
  ``{"aa", "bb", "cc"}`` cannot tell the two apart and the "sort key" mutation
  passes (review-798 2차 M-3(a)). :data:`MIXED_LENGTH_ELEMENTS` therefore mixes
  one-, two- and three-character strings, upper and lower case, digits and a
  non-ASCII letter.
* **At least six elements per set.** With ``n`` elements, two processes draw the
  same iteration order with probability ≈ ``1/n!``; at ``n = 3`` a seed-divergence
  pin passes by luck ~3% of the time (review-798 1차 MEDIUM-2(a)). Six is the
  floor, and the enum-valued sets use **every** member of their vocabulary.

Instances are built with ``model_construct`` on purpose: the pins measure the
serialization of the covered content, not artifact admissibility, and hand-
building 19 admissible ``issue()`` calls would make the pins expensive without
measuring anything more (review-798 1차 MEDIUM-2(c)).
"""

from __future__ import annotations

import datetime as dt
import types
import typing
from decimal import Decimal
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel
from tos.brokercap.records import BrokerCapabilityProfile
from tos.canonical import EV_L1_PROVISIONAL_VERSION, DigestBoundArtifact, get_scheme
from tos.cur.records import CurrentnessPolicy, RestrictiveFenceRecord
from tos.engine.records import EngineEvent, event_identity
from tos.hag.records import (
    HumanApprovalRequest,
    HumanAuthorityPolicy,
    HumanDelegationRecord,
    HumanHaltCommand,
)
from tos.liveauth.records import LiveAuthorization, ReArmApprovalRecord
from tos.posttrade.records import StatementCoverageManifest
from tos.rlp.records import TrialEvidencePackage, TrialPolicy
from tos.sbr.records import (
    RecoveryInventoryCut,
    RecoveryObligation,
    RecoveryReadinessDecision,
)
from tos.sir.records import SafetyIncidentPolicy
from tos.venue.records import OrderAdmissibilityDecision, VenueConstraintPolicy
from tos.wdr.records import SafetyDeviationPolicy

#: Deliberately mixed-length, mixed-case, non-ASCII-carrying set elements.
MIXED_LENGTH_ELEMENTS: tuple[str, ...] = (
    "b",
    "aa",
    "c",
    "dd",
    "zzz",
    "B",
    "Aé",
    "10",
    "9",
)

#: The 19 ``DigestBoundArtifact`` subclasses whose covered field tree holds a set
#: (plan §1.2). Eight of them were already deterministic through a per-model
#: sorter; the other eleven were not.
COVERED_SET_MODELS: tuple[type[DigestBoundArtifact], ...] = (
    BrokerCapabilityProfile,
    CurrentnessPolicy,
    RestrictiveFenceRecord,
    HumanApprovalRequest,
    HumanAuthorityPolicy,
    HumanDelegationRecord,
    HumanHaltCommand,
    LiveAuthorization,
    ReArmApprovalRecord,
    StatementCoverageManifest,
    TrialEvidencePackage,
    TrialPolicy,
    RecoveryInventoryCut,
    RecoveryObligation,
    RecoveryReadinessDecision,
    SafetyIncidentPolicy,
    OrderAdmissibilityDecision,
    VenueConstraintPolicy,
    SafetyDeviationPolicy,
)

#: The eight models that carried their own ``sorted()`` before this change; their
#: digests must be bit-identical after it (plan §2.3).
PREVIOUSLY_SORTED_MODELS: tuple[type[DigestBoundArtifact], ...] = (
    CurrentnessPolicy,
    RestrictiveFenceRecord,
    SafetyDeviationPolicy,
    SafetyIncidentPolicy,
    TrialEvidencePackage,
    TrialPolicy,
    LiveAuthorization,
    ReArmApprovalRecord,
)

_MAX_DEPTH = 8

#: Preserves the concrete model type through :func:`build_instance`.
_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _first_arg(annotation: Any) -> Any:
    """Return the first non-``None`` member of a union annotation."""
    for arg in typing.get_args(annotation):
        if arg is not type(None):
            return arg
    return None


def _enum_elements(enum_cls: type[Enum]) -> tuple[Enum, ...]:
    """Every member of an enum vocabulary (never a subset — see the module doc)."""
    return tuple(enum_cls)


def _set_elements(element_annotation: Any) -> tuple[Any, ...]:
    """Six-or-more elements of the right type for a set annotation."""
    if isinstance(element_annotation, type) and issubclass(element_annotation, Enum):
        return _enum_elements(element_annotation)
    return MIXED_LENGTH_ELEMENTS


def value_for(annotation: Any, depth: int = 0) -> Any:
    """Build one representative value for a pydantic field annotation.

    Args:
        annotation: The field annotation.
        depth: Current recursion depth (nested models stop at ``_MAX_DEPTH``).

    Returns:
        A value of the annotated shape, with every set filled per the module doc.
    """
    if depth > _MAX_DEPTH:
        return None
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin in (typing.Union, types.UnionType):
        return value_for(_first_arg(annotation), depth)
    if origin is typing.Annotated:
        return value_for(args[0], depth)
    if origin is typing.Literal:
        return args[0]
    if origin in (set, frozenset):
        return frozenset(_set_elements(args[0]))
    if origin is list:
        return [value_for(args[0], depth + 1)]
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return (value_for(args[0], depth + 1),)
        return tuple(value_for(arg, depth + 1) for arg in args)
    if origin is dict:
        return {"k": value_for(args[1], depth + 1)}
    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel):
            return build_instance(annotation, depth + 1)
        if issubclass(annotation, Enum):
            return _enum_elements(annotation)[0]
        if issubclass(annotation, bool):
            return True
        if issubclass(annotation, int):
            return 7
        if issubclass(annotation, str):
            return "s"
        if issubclass(annotation, float):
            return 1.5
        if issubclass(annotation, Decimal):
            return Decimal("1.5")
        if issubclass(annotation, dt.datetime):
            return dt.datetime(2026, 9, 24, 10, 0, 0, tzinfo=dt.UTC)
        if issubclass(annotation, dt.date):
            return dt.date(2026, 9, 24)
    return None


def build_instance(model_cls: type[_ModelT], depth: int = 0) -> _ModelT:
    """Build one representative instance of ``model_cls`` (no validation).

    Args:
        model_cls: The pydantic model to build.
        depth: Current recursion depth.

    Returns:
        A ``model_construct``-built instance with every field populated.
    """
    values = {
        name: value_for(field.annotation, depth)
        for name, field in model_cls.model_fields.items()
    }
    return model_cls.model_construct(**values)


def corporate_action_event() -> EngineEvent:
    """A ``CORPORATE_ACTION`` engine event — the non-``covered_content()`` path.

    ``event_identity()`` digests ``EngineEvent.model_dump(mode="json")`` directly
    (``tos/src/tos/engine/records.py``), and the runtime's driver recomputes a
    digest of the same dump on the crash-recovery path. Neither goes through
    ``covered_content()``, which is why the fix has to live in the serializer.

    Returns:
        An engine event whose corporate-action payload carries filled sets.
    """
    fields = EngineEvent.model_fields
    kind_annotation = fields["kind"].annotation
    kind_enum = kind_annotation if isinstance(kind_annotation, type) else None
    assert kind_enum is not None and issubclass(kind_enum, Enum)
    values: dict[str, Any] = {
        name: value_for(field.annotation) for name, field in fields.items()
    }
    values["kind"] = kind_enum["CORPORATE_ACTION"]
    return EngineEvent.model_construct(**values)


#: The negative control: a raw ``frozenset`` iteration order, digested without
#: going through any model. It MUST differ between two ``PYTHONHASHSEED`` values.
#: Without it, a seed sweep where the seed never actually took effect would report
#: "every digest is stable" for the wrong reason.
CONTROL_KEY = "CONTROL.raw_frozenset_order"


def digest_map() -> dict[str, str]:
    """Every digest the set-ordering pins compare, keyed by a stable name.

    Returns:
        A mapping of pin key to canonical digest, covering the 19
        ``covered_content()`` models, the two non-covered call shapes, and the
        :data:`CONTROL_KEY` negative control.
    """
    scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
    digests: dict[str, str] = {}
    for model_cls in COVERED_SET_MODELS:
        instance = build_instance(model_cls)
        covered = instance.covered_content()
        digests[model_cls.__name__] = scheme.compute_digest(covered)
    event = corporate_action_event()
    digests["EngineEvent.event_identity"] = event_identity(event, scheme=scheme)
    # The runtime driver's shape: compute_digest(event.model_dump(mode="json")).
    digests["EngineEvent.payload_digest"] = scheme.compute_digest(
        event.model_dump(mode="json")
    )
    digests[CONTROL_KEY] = scheme.compute_digest(
        {"elements": list(frozenset(MIXED_LENGTH_ELEMENTS))}
    )
    return digests
