"""Transformation Lineage element schema (design §2.3 — gap 1)."""

from __future__ import annotations

from tos.capsule._base import FrozenModel
from tos.capsule.field_state import FieldState


class ParentRef(FrozenModel):
    """An exact parent input with its digest (ADR §10 line 280)."""

    parent_id: str | None = None
    digest: str | None = None


class Versions(FrozenModel):
    """Toolchain versions behind the transform (ADR §10 line 282)."""

    code_build: str | None = None
    model: str | None = None
    formula: str | None = None
    library: str | None = None
    schema_: str | None = None
    config: str | None = None


class UnitConversion(FrozenModel):
    """A single explicit unit conversion (ADR §10 line 283)."""

    before_unit: str | None = None
    after_unit: str | None = None
    factor: str | None = None


class NumericBehavior(FrozenModel):
    """Declared numeric behaviour (ADR §10 line 284)."""

    rounding: str | None = None
    clipping: str | None = None
    interpolation: str | None = None
    imputation: str | None = None
    aggregation: str | None = None
    missing_data: str | None = None


class Stochastic(FrozenModel):
    """Stochastic-transform declaration (ADR §10 line 285)."""

    is_stochastic: bool = False
    params: tuple[str, ...] = ()
    random_seed: str | None = None
    nondeterminism_declaration: str | None = None


class OutputSpec(FrozenModel):
    """Output type/range/precision/uncertainty/scope (ADR §10 line 286)."""

    type: str | None = None
    range: str | None = None
    precision: str | None = None
    uncertainty: str | None = None
    intended_scope: str | None = None


class TransformationLineage(FrozenModel):
    """A transformation-graph node with provenance (design §2.3)."""

    output_id: str | None = None
    output_digest: str | None = None
    parents: tuple[ParentRef, ...] = ()
    transform_graph: tuple[str, ...] = ()
    versions: Versions = Versions()
    unit_conversions: tuple[UnitConversion, ...] = ()
    numeric_behavior: NumericBehavior = NumericBehavior()
    stochastic: Stochastic = Stochastic()
    output_spec: OutputSpec = OutputSpec()
    common_mode_tags: tuple[str, ...] = ()
    reproducible: bool = False
    field_state: FieldState = FieldState.UNKNOWN
