"""Declarative indicator fields — catalog ``tos-field-catalog/1`` and evaluator.

P2-a of ``docs/plans/2026-11-11-tos-p2-declarative-fields.md``. A tenant declares
WHICH fields a producer emits and how they are scaled, in a ``fields.yaml``
(schema ``tos-fields/1``); this package owns the fixed, versioned set of
operations such a declaration may compose, and the evaluator that runs one over
a bar stream.

Example:
    >>> from shared.indicators.fields import FieldBar, FieldEvaluator, parse_fields_document
    >>> document = parse_fields_document(
    ...     {
    ...         "schema": "tos-fields/1",
    ...         "catalog": "tos-field-catalog/1",
    ...         "fields": [
    ...             {"name": "close", "op": "bar.close"},
    ...             {"name": "atr", "op": "atr", "params": {"period": 14}},
    ...         ],
    ...         "publish": [
    ...             {
    ...                 "field": "close",
    ...                 "as": "close_x100",
    ...                 "scale": {"mult": 100, "round": "half_up"},
    ...             }
    ...         ],
    ...     }
    ... )
    >>> evaluator = FieldEvaluator(document)
    >>> bar = FieldBar.create(
    ...     "2026-11-11 09:00", open=1.0, high=2.0, low=0.5, close=1.5, volume=10
    ... )
    >>> evaluator.step(bar).published
    {'close_x100': 150}

Scope (P2-a): the catalog, the schema and loader, the evaluator, and their unit
goldens. The per-tenant ``fields.yaml`` files, the byte-identity harness against
the legacy-driven producer, and the producer switch itself are P2-b and P2-c.

Firewall: this package is inside ``shared.indicators``, one of the six
pure-commons packages ``tos`` may import, so it must stay pure. It imports only
stdlib, numpy, pandas, PyYAML, ``shared.determinism`` and ``shared.indicators``
— never ``shared.backtest``, ``shared.decision``, ``services`` or ``cli``. The
consequence (and the reason the legacy definitions are repeated here under test
rather than imported) is documented in
:mod:`shared.indicators.fields.bar`.
"""

from __future__ import annotations

from shared.indicators.fields.bar import (
    AtrWindow,
    FieldBar,
    SessionVwapTypical,
    minutes_since_open,
)
from shared.indicators.fields.catalog import (
    CATALOG,
    CATALOG_VERSION,
    NonePolicy,
    OpSpec,
    ValueKind,
    known_op_names,
    op_spec,
)
from shared.indicators.fields.errors import (
    FieldError,
    FieldEvalError,
    FieldSpecError,
)
from shared.indicators.fields.evaluator import (
    EvaluatedBar,
    FieldEvaluator,
    FieldValue,
    PublishedValue,
    evaluate_bars,
)
from shared.indicators.fields.scaling import (
    ROUNDING_MODES,
    scaled_int_half_up,
    scaled_int_toward_zero,
)
from shared.indicators.fields.schema import (
    SCHEMA_VERSION,
    FieldsDocument,
    FieldSpec,
    PublishSpec,
    ScaleSpec,
    load_fields_file,
    parse_fields_document,
)
from shared.indicators.fields.stateful import (
    GatedLag,
    GatedMax,
    GatedMin,
    GatedPercentile,
    GatedWindowOp,
)

__all__ = [
    "CATALOG",
    "CATALOG_VERSION",
    "ROUNDING_MODES",
    "SCHEMA_VERSION",
    "AtrWindow",
    "EvaluatedBar",
    "FieldBar",
    "FieldError",
    "FieldEvalError",
    "FieldEvaluator",
    "FieldSpec",
    "FieldSpecError",
    "FieldValue",
    "FieldsDocument",
    "GatedLag",
    "GatedMax",
    "GatedMin",
    "GatedPercentile",
    "GatedWindowOp",
    "NonePolicy",
    "OpSpec",
    "PublishSpec",
    "PublishedValue",
    "ScaleSpec",
    "SessionVwapTypical",
    "ValueKind",
    "evaluate_bars",
    "known_op_names",
    "load_fields_file",
    "minutes_since_open",
    "op_spec",
    "parse_fields_document",
    "scaled_int_half_up",
    "scaled_int_toward_zero",
]
