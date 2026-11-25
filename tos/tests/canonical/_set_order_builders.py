"""Representative instances for the canonical set-ordering pins (plan §3)."""

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
from tos.venue.records import OrderAdmissibilityDecision, VenueConstraintPolicy

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

COVERED_SET_MODELS: tuple[type[DigestBoundArtifact], ...] = (
    BrokerCapabilityProfile,
    CurrentnessPolicy,
    RestrictiveFenceRecord,
    OrderAdmissibilityDecision,
    VenueConstraintPolicy,
)

PREVIOUSLY_SORTED_MODELS: tuple[type[DigestBoundArtifact], ...] = (
    CurrentnessPolicy,
    RestrictiveFenceRecord,
)

_MAX_DEPTH = 8

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
    """Build one representative value for a pydantic field annotation."""
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
    """Build one representative instance of ``model_cls`` (no validation)."""
    values = {
        name: value_for(field.annotation, depth)
        for name, field in model_cls.model_fields.items()
    }
    return model_cls.model_construct(**values)


def decision_tick_event() -> EngineEvent:
    """A ``DECISION_TICK`` engine event — the non-``covered_content()`` path."""
    fields = EngineEvent.model_fields
    kind_annotation = fields["kind"].annotation
    kind_enum = kind_annotation if isinstance(kind_annotation, type) else None
    assert kind_enum is not None and issubclass(kind_enum, Enum)
    values: dict[str, Any] = {
        name: value_for(field.annotation) for name, field in fields.items()
    }
    values["kind"] = kind_enum["DECISION_TICK"]
    return EngineEvent.model_construct(**values)


CONTROL_KEY = "CONTROL.raw_frozenset_order"


def digest_map() -> dict[str, str]:
    """Every digest the set-ordering pins compare, keyed by a stable name."""
    scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
    digests: dict[str, str] = {}
    for model_cls in COVERED_SET_MODELS:
        instance = build_instance(model_cls)
        covered = instance.covered_content()
        digests[model_cls.__name__] = scheme.compute_digest(covered)
    event = decision_tick_event()
    digests["EngineEvent.event_identity"] = event_identity(event, scheme=scheme)
    digests["EngineEvent.payload_digest"] = scheme.compute_digest(
        event.model_dump(mode="json")
    )
    digests[CONTROL_KEY] = scheme.compute_digest(
        {"elements": list(frozenset(MIXED_LENGTH_ELEMENTS))}
    )
    return digests
