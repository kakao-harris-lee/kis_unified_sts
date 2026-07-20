"""Transformation Lineage element schema (design §2.3 — gap 1).

``CRITICAL-INPUT-SNAPSHOT-template.yaml:transformation_lineage: []`` (line 28)
leaves the element schema empty. This module authors it from ADR-002-018 §5.4
(line 122-124) and §10 (line 276-290). Field groups follow the design §2.3
table verbatim.

Reproducibility (design §2.3, CII-EV-004): a derived input with
``reproducible=False`` or a missing parent is ``INVALID`` for new risk (ADR §10
line 288). The derivation predicate lives in :mod:`tos.capsule.predicates`;
this module is data only. Hidden defaults (forward/zero fill, silent coercion,
symbol alias, fallback source) are expressible only as explicit ops — an
imputation absent from ``numeric_behavior`` renders the lineage incomplete
(ADR §10 line 288).

Pure module: ``pydantic`` + stdlib only.
"""

from __future__ import annotations

from tos.capsule._base import FrozenModel
from tos.capsule.field_state import FieldState


class ParentRef(FrozenModel):
    """An exact parent input with its digest (ADR §10 line 280)."""

    parent_id: str | None = None
    digest: str | None = None


class Versions(FrozenModel):
    """Toolchain versions behind the transform (ADR §10 line 282).

    ``schema_`` carries the ADR §10 ``schema`` version identifier; the trailing
    underscore avoids shadowing ``pydantic.BaseModel``'s reserved ``schema``
    attribute (this is an authored element, not template-SoT, so the internal key
    name is free — design §2.3 gap 1).
    """

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
    """Declared numeric behaviour (ADR §10 line 284).

    Any imputation must be recorded here; an imputation not recorded renders the
    lineage incomplete (design §2.3, ADR §10 line 288).
    """

    rounding: str | None = None
    clipping: str | None = None
    interpolation: str | None = None
    imputation: str | None = None
    aggregation: str | None = None
    missing_data: str | None = None


class Stochastic(FrozenModel):
    """Stochastic-transform declaration (ADR §10 line 285).

    If ``is_stochastic`` is true, exactly one of ``random_seed`` or
    ``nondeterminism_declaration`` must be present for the transform to be
    reproducible (evaluated in :mod:`tos.capsule.predicates`).
    """

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
    """A transformation-graph node with provenance (design §2.3).

    Frozen element of ``CriticalInputSnapshot.transformation_lineage``.
    ``common_mode_tags`` (e.g. a shared library id, ADR §10 line 290) feed the
    common-mode collapse in :mod:`tos.capsule.predicates` (§5.2).
    """

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
