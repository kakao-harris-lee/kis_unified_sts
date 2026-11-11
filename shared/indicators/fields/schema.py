"""``fields.yaml`` — schema ``tos-fields/1``, its loader, and its refusals.

Shape (``docs/plans/2026-11-11-tos-p2-declarative-fields.md`` §2.2)::

    schema: tos-fields/1
    catalog: tos-field-catalog/1          # pinned — boot is refused on a mismatch
    fields:                               # order = evaluation order
      - {name: close, op: bar.close}
      - {name: atr,   op: atr, params: {period: 14}}
      - {name: entry_window, op: between, inputs: [mso], params: {lo: 15, hi: 345}}
    publish:                              # what leaves for the journal, and how
      - {field: close, as: close_x100, scale: {mult: 100, round: half_up}}
      - {field: hi_vol}

Everything here fails at LOAD time, before a bar is read. A declaration this
module accepts cannot surprise the evaluator with a missing field, an unknown
op, a mistyped parameter or a reference to a value that does not exist yet.

The refusals, each with its own message, because a producer that refuses without
saying which rule it refused on is not operable:

=========================== =============================================
refusal                     what it catches
=========================== =============================================
``unknown schema``          a ``schema:`` other than ``tos-fields/1``
``catalog version``         a ``catalog:`` other than the loaded catalog
``unknown op``              an op not in ``tos-field-catalog/1``
``duplicate name``          two fields, or two published names, colliding
``cycle``                   a field whose input is itself
``forward reference``       an input naming a field declared later
``unknown reference``       an input naming no field at all
``arity``                   the wrong number of inputs for the op
``value kind``              a bool field where a number is required (or vv.)
``bad params``              unknown / missing / out-of-range parameters
``publish``                 publishing an undeclared field, or the wrong
                            scale for its kind
=========================== =============================================

A cycle longer than a self-reference cannot exist: ``fields`` is an ordered list
and an input may only name an EARLIER field, so any loop needs a forward
reference and is refused as one. The self-reference case is reported as a cycle
because that is what it is.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Any, Final

import yaml

from shared.indicators.fields.catalog import (
    CATALOG,
    CATALOG_VERSION,
    NonePolicy,
    OpSpec,
    ValueKind,
    known_op_names,
)
from shared.indicators.fields.errors import FieldSpecError
from shared.indicators.fields.scaling import ROUNDING_MODES

#: The only ``fields.yaml`` schema this loader understands.
SCHEMA_VERSION: Final[str] = "tos-fields/1"

#: Top-level keys a document may carry. An unknown key is refused rather than
#: ignored: a mistyped ``publish:`` would otherwise produce an empty journal.
_DOCUMENT_KEYS: Final[frozenset[str]] = frozenset(
    {"schema", "catalog", "fields", "publish"}
)
_FIELD_KEYS: Final[frozenset[str]] = frozenset({"name", "op", "inputs", "params"})
_PUBLISH_KEYS: Final[frozenset[str]] = frozenset({"field", "as", "scale"})
_SCALE_KEYS: Final[frozenset[str]] = frozenset({"mult", "round"})

#: Ops whose right-hand side is either a second input or a ``const``.
_BINARY_COMPARISONS: Final[frozenset[str]] = frozenset({"gt", "ge", "lt", "le"})


@dataclass(frozen=True)
class ScaleSpec:
    """How a numeric field becomes the integer the kernel compares.

    Attributes:
        mult: Positive integer multiplier (100 for a price at 0.01 resolution).
        rounding: ``half_up`` or ``toward_zero`` — a key of
            :data:`~shared.indicators.fields.scaling.ROUNDING_MODES`.
    """

    mult: int
    rounding: str


@dataclass(frozen=True)
class PublishSpec:
    """One journal field: which declared field, under which name, scaled how.

    Attributes:
        field: Declared field name to publish.
        name: Published key (the ``as:`` value; defaults to ``field``).
        scale: Required for a numeric field, forbidden for bool/str.
    """

    field: str
    name: str
    scale: ScaleSpec | None


@dataclass(frozen=True)
class FieldSpec:
    """One declared field, with its catalog op resolved.

    Attributes:
        name: Field name, unique within the document.
        inputs: Names of EARLIER fields this op reads, in op-argument order.
        params: Parameters, already coerced and range-checked by the loader
            (``at`` is a :class:`datetime.time`, counts are ``int``, thresholds
            are ``float``).
        op: The resolved catalog entry.
    """

    name: str
    inputs: tuple[str, ...]
    params: Mapping[str, Any]
    op: OpSpec

    @property
    def op_name(self) -> str:
        """The op's catalog name."""
        return self.op.name

    @property
    def returns(self) -> ValueKind:
        """The kind of value this field carries."""
        return self.op.returns


@dataclass(frozen=True)
class FieldsDocument:
    """A loaded, validated ``fields.yaml``.

    Attributes:
        fields: Declared fields in evaluation order.
        publish: Journal fields in publication order.
        catalog: Catalog version the document pinned.
        schema: Document schema version.
    """

    fields: tuple[FieldSpec, ...]
    publish: tuple[PublishSpec, ...]
    catalog: str = CATALOG_VERSION
    schema: str = SCHEMA_VERSION

    def field_kinds(self) -> dict[str, ValueKind]:
        """Map each declared field name to the kind of value it carries."""
        return {spec.name: spec.returns for spec in self.fields}


# ---------------------------------------------------------------------------
# Primitive coercion
# ---------------------------------------------------------------------------


def _require_mapping(raw: Any, what: str) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise FieldSpecError(f"{what} must be a mapping, got {type(raw).__name__}")
    for key in raw:
        if not isinstance(key, str):
            raise FieldSpecError(f"{what} has a non-string key {key!r}")
    return raw


def _reject_unknown_keys(
    raw: Mapping[str, Any], allowed: frozenset[str], what: str
) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise FieldSpecError(
            f"{what} has unknown key(s) {unknown}; allowed: {sorted(allowed)}"
        )


def _as_int(value: Any, *, what: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FieldSpecError(f"bad params: {what} must be an integer, got {value!r}")
    if minimum is not None and value < minimum:
        raise FieldSpecError(f"bad params: {what} must be >= {minimum}, got {value}")
    return value


def _as_float(value: Any, *, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FieldSpecError(f"bad params: {what} must be a number, got {value!r}")
    return float(value)


def _as_bool(value: Any, *, what: str) -> bool:
    if not isinstance(value, bool):
        raise FieldSpecError(f"bad params: {what} must be true or false, got {value!r}")
    return value


def _as_time(value: Any, *, what: str) -> time:
    if not isinstance(value, str):
        raise FieldSpecError(
            f"bad params: {what} must be a 'HH:MM' or 'HH:MM:SS' string, got {value!r}"
        )
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise FieldSpecError(
            f"bad params: {what}={value!r} is not a 'HH:MM' / 'HH:MM:SS' time ({exc})"
        ) from exc


# ---------------------------------------------------------------------------
# Field parsing
# ---------------------------------------------------------------------------


def _parse_inputs(raw: Any, field_name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str) or not isinstance(raw, Sequence):
        raise FieldSpecError(
            f"field {field_name!r}: inputs must be a list of field names, "
            f"got {raw!r}"
        )
    names: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item:
            raise FieldSpecError(
                f"field {field_name!r}: every input must be a non-empty field "
                f"name, got {item!r}"
            )
        names.append(item)
    return tuple(names)


def _resolve_reference(
    name: str,
    *,
    field_name: str,
    what: str,
    declared: Mapping[str, ValueKind],
    later: frozenset[str],
) -> ValueKind:
    """Resolve a reference to an earlier field, naming the reason it cannot be."""
    if name == field_name:
        raise FieldSpecError(f"cycle: field {field_name!r} names itself as {what}")
    if name in declared:
        return declared[name]
    if name in later:
        raise FieldSpecError(
            f"forward reference: field {field_name!r} names {name!r} as {what}, "
            "but it is declared later — fields may only read EARLIER fields"
        )
    raise FieldSpecError(
        f"unknown reference: field {field_name!r} names {name!r} as {what}, "
        "which no field declares"
    )


def _validate_params(
    *,
    field_name: str,
    op: OpSpec,
    raw_params: Mapping[str, Any],
    inputs: tuple[str, ...],
    declared: Mapping[str, ValueKind],
    later: frozenset[str],
) -> dict[str, Any]:
    """Coerce and range-check one field's parameters, or refuse."""
    allowed = op.required_params | op.optional_params
    unknown = sorted(set(raw_params) - allowed)
    if unknown:
        raise FieldSpecError(
            f"bad params: field {field_name!r} (op {op.name!r}) has unknown "
            f"parameter(s) {unknown}; allowed: {sorted(allowed)}"
        )
    missing = sorted(op.required_params - set(raw_params))
    if missing:
        raise FieldSpecError(
            f"bad params: field {field_name!r} (op {op.name!r}) is missing "
            f"required parameter(s) {missing}"
        )

    out: dict[str, Any] = {}
    where = f"field {field_name!r} (op {op.name!r})"
    for key, value in raw_params.items():
        what = f"{where} parameter {key!r}"
        if key in {"period", "window", "warmup"}:
            out[key] = _as_int(value, what=what, minimum=1)
        elif key == "open_hour":
            hour = _as_int(value, what=what, minimum=0)
            if hour > 23:
                raise FieldSpecError(f"bad params: {what} must be <= 23, got {hour}")
            out[key] = hour
        elif key == "open_minute":
            minute = _as_int(value, what=what, minimum=0)
            if minute > 59:
                raise FieldSpecError(f"bad params: {what} must be <= 59, got {minute}")
            out[key] = minute
        elif key == "q":
            q = _as_float(value, what=what)
            if not 0.0 <= q <= 100.0:
                raise FieldSpecError(f"bad params: {what} must be in [0, 100], got {q}")
            out[key] = q
        elif key in {"const", "mult", "lo", "hi"}:
            out[key] = _as_float(value, what=what)
        elif key == "when_missing":
            out[key] = _as_bool(value, what=what)
        elif key == "at":
            out[key] = _as_time(value, what=what)
        elif key == "sample_when":
            if not isinstance(value, str) or not value:
                raise FieldSpecError(
                    f"bad params: {what} must name a boolean field, got {value!r}"
                )
            kind = _resolve_reference(
                value,
                field_name=field_name,
                what="sample_when",
                declared=declared,
                later=later,
            )
            if kind is not ValueKind.BOOL:
                raise FieldSpecError(
                    f"value kind: {what} names {value!r}, which carries "
                    f"{kind.value}, not bool"
                )
            out[key] = value
        else:  # pragma: no cover - unreachable while the catalog and this agree
            raise FieldSpecError(
                f"bad params: {what} is declared by the catalog but this loader "
                "does not know how to validate it"
            )

    if "warmup" in out and out["warmup"] > out["window"]:
        # The legacy's own footgun note (``trend_warmup_bars``): a warmup above
        # the window cap means the window never reaches warmup, so the field is
        # permanently None and every gate built on it is silently permissive.
        raise FieldSpecError(
            f"bad params: {where} has warmup={out['warmup']} > "
            f"window={out['window']}, so the window can never reach warmup and "
            "the field would be permanently None (a silently dead gate)"
        )
    if op.name == "between" and out["lo"] > out["hi"]:
        raise FieldSpecError(
            f"bad params: {where} has lo={out['lo']} > hi={out['hi']}, so the "
            "window is empty and the field would be permanently false"
        )
    if op.name in _BINARY_COMPARISONS:
        if len(inputs) == 2 and "const" in out:
            raise FieldSpecError(
                f"bad params: {where} has both a second input ({inputs[1]!r}) "
                "and a const — the right-hand side would be ambiguous"
            )
        if len(inputs) == 1 and "const" not in out:
            raise FieldSpecError(
                f"bad params: {where} has one input and no const, so it has no "
                "right-hand side to compare against"
            )
    return out


def _parse_field(
    raw: Any,
    *,
    index: int,
    declared: Mapping[str, ValueKind],
    later: frozenset[str],
) -> FieldSpec:
    mapping = _require_mapping(raw, f"fields[{index}]")
    _reject_unknown_keys(mapping, _FIELD_KEYS, f"fields[{index}]")

    name = mapping.get("name")
    if not isinstance(name, str) or not name:
        raise FieldSpecError(f"fields[{index}]: name must be a non-empty string")
    if name in declared:
        raise FieldSpecError(f"duplicate name: field {name!r} is declared twice")

    op_name = mapping.get("op")
    if not isinstance(op_name, str) or not op_name:
        raise FieldSpecError(f"field {name!r}: op must be a non-empty string")
    op = CATALOG.get(op_name)
    if op is None:
        raise FieldSpecError(
            f"unknown op: field {name!r} uses op {op_name!r}, which "
            f"{CATALOG_VERSION} does not define; known ops: "
            f"{list(known_op_names())}"
        )

    inputs = _parse_inputs(mapping.get("inputs"), name)
    if not op.accepts_input_count(len(inputs)):
        raise FieldSpecError(
            f"arity: field {name!r} (op {op_name!r}) takes {op.arity_text()} "
            f"input(s), got {len(inputs)}"
        )
    for position, ref in enumerate(inputs):
        kind = _resolve_reference(
            ref,
            field_name=name,
            what=f"input[{position}]",
            declared=declared,
            later=later,
        )
        if op.accepts is not None and kind is not op.accepts:
            raise FieldSpecError(
                f"value kind: field {name!r} (op {op_name!r}) requires "
                f"{op.accepts.value} inputs, but input[{position}] {ref!r} "
                f"carries {kind.value}"
            )

    raw_params = mapping.get("params")
    params_mapping = (
        {}
        if raw_params is None
        else _require_mapping(raw_params, f"field {name!r} params")
    )
    params = _validate_params(
        field_name=name,
        op=op,
        raw_params=params_mapping,
        inputs=inputs,
        declared=declared,
        later=later,
    )
    return FieldSpec(name=name, inputs=inputs, params=params, op=op)


# ---------------------------------------------------------------------------
# Publish parsing
# ---------------------------------------------------------------------------


def _parse_scale(raw: Any, *, where: str) -> ScaleSpec:
    mapping = _require_mapping(raw, f"{where} scale")
    _reject_unknown_keys(mapping, _SCALE_KEYS, f"{where} scale")
    missing = sorted(_SCALE_KEYS - set(mapping))
    if missing:
        raise FieldSpecError(f"publish: {where} scale is missing {missing}")
    mult = _as_int(mapping["mult"], what=f"{where} scale mult", minimum=1)
    rounding = mapping["round"]
    if rounding not in ROUNDING_MODES:
        raise FieldSpecError(
            f"publish: {where} scale round={rounding!r} is unknown; "
            f"known modes: {sorted(ROUNDING_MODES)}"
        )
    return ScaleSpec(mult=mult, rounding=rounding)


def _parse_publish(
    raw: Any,
    *,
    index: int,
    kinds: Mapping[str, ValueKind],
    taken: Mapping[str, str],
) -> PublishSpec:
    mapping = _require_mapping(raw, f"publish[{index}]")
    _reject_unknown_keys(mapping, _PUBLISH_KEYS, f"publish[{index}]")

    field = mapping.get("field")
    if not isinstance(field, str) or not field:
        raise FieldSpecError(f"publish[{index}]: field must be a non-empty string")
    if field not in kinds:
        raise FieldSpecError(
            f"publish: entry {index} names field {field!r}, which no field " "declares"
        )
    published_as = mapping.get("as", field)
    if not isinstance(published_as, str) or not published_as:
        raise FieldSpecError(
            f"publish: entry {index} ('{field}') has a non-string 'as' name "
            f"{published_as!r}"
        )
    if published_as in taken:
        raise FieldSpecError(
            f"duplicate name: published name {published_as!r} is used by both "
            f"{taken[published_as]!r} and {field!r}"
        )

    where = f"entry {index} ('{field}')"
    kind = kinds[field]
    raw_scale = mapping.get("scale")
    if kind is ValueKind.NUMBER:
        if raw_scale is None:
            raise FieldSpecError(
                f"publish: {where} carries a number, which the kernel cannot "
                "compare — it needs a scale {mult, round}"
            )
        scale: ScaleSpec | None = _parse_scale(raw_scale, where=where)
    else:
        if raw_scale is not None:
            raise FieldSpecError(
                f"publish: {where} carries {kind.value}, which is published as "
                "is — a scale is meaningless for it"
            )
        scale = None
    return PublishSpec(field=field, name=published_as, scale=scale)


# ---------------------------------------------------------------------------
# Document parsing
# ---------------------------------------------------------------------------


def parse_fields_document(raw: Any) -> FieldsDocument:
    """Validate an already-parsed ``fields.yaml`` mapping.

    Pure: no file system, no YAML. :func:`load_fields_file` is the thin wrapper
    that reads a path.

    Args:
        raw: The document as a mapping (what ``yaml.safe_load`` returns).

    Returns:
        The validated document.

    Raises:
        FieldSpecError: on any refusal listed in the module docstring.
    """
    document = _require_mapping(raw, "fields document")
    _reject_unknown_keys(document, _DOCUMENT_KEYS, "fields document")

    schema = document.get("schema")
    if schema != SCHEMA_VERSION:
        raise FieldSpecError(
            f"unknown schema: {schema!r}; this loader reads {SCHEMA_VERSION!r}"
        )
    catalog = document.get("catalog")
    if catalog != CATALOG_VERSION:
        raise FieldSpecError(
            f"catalog version: document pins {catalog!r} but the loaded catalog "
            f"is {CATALOG_VERSION!r} — the ops may have changed meaning, so the "
            "declaration is refused rather than reinterpreted"
        )

    raw_fields = document.get("fields")
    if not isinstance(raw_fields, Sequence) or isinstance(raw_fields, str):
        raise FieldSpecError("fields must be a non-empty list")
    if not raw_fields:
        raise FieldSpecError("fields must be a non-empty list")

    names_in_order: list[str] = []
    for entry in raw_fields:
        if isinstance(entry, Mapping):
            candidate = entry.get("name")
            if isinstance(candidate, str):
                names_in_order.append(candidate)

    declared: dict[str, ValueKind] = {}
    specs: list[FieldSpec] = []
    for index, entry in enumerate(raw_fields):
        later = frozenset(names_in_order[index + 1 :])
        spec = _parse_field(entry, index=index, declared=declared, later=later)
        specs.append(spec)
        declared[spec.name] = spec.returns

    raw_publish = document.get("publish")
    if not isinstance(raw_publish, Sequence) or isinstance(raw_publish, str):
        raise FieldSpecError("publish must be a non-empty list")
    if not raw_publish:
        raise FieldSpecError("publish must be a non-empty list")

    taken: dict[str, str] = {}
    published: list[PublishSpec] = []
    for index, entry in enumerate(raw_publish):
        publish_spec = _parse_publish(entry, index=index, kinds=declared, taken=taken)
        taken[publish_spec.name] = publish_spec.field
        published.append(publish_spec)

    _assert_published_fields_are_definite(specs, published)
    return FieldsDocument(
        fields=tuple(specs),
        publish=tuple(published),
        catalog=CATALOG_VERSION,
        schema=SCHEMA_VERSION,
    )


def _assert_published_fields_are_definite(
    specs: Sequence[FieldSpec], published: Sequence[PublishSpec]
) -> None:
    """Refuse publishing a field that can carry no value on some bar.

    A published field must have a value on every emitted bar — the kernel's
    journal reader refuses the whole poll on a missing key
    (``tos/runtime/src/tos_runtime/marketfeed/journal.py``). A ``gated_*`` field,
    or any op that PROPAGATEs a missing value, is ``None`` during warmup, so
    publishing it directly is a declaration bug: wrap it in ``permissive`` (or
    publish a comparison that is).
    """
    by_name = {spec.name: spec for spec in specs}
    for entry in published:
        spec = by_name[entry.field]
        if spec.op.stateful or spec.op.none_policy is NonePolicy.PROPAGATE:
            if _may_be_missing(spec, by_name):
                raise FieldSpecError(
                    f"publish: entry names field {entry.field!r} (op "
                    f"{spec.op_name!r}), which has no value during warmup — a "
                    "published field must be definite on every bar; resolve it "
                    "with 'permissive' first"
                )


def _may_be_missing(spec: FieldSpec, by_name: Mapping[str, FieldSpec]) -> bool:
    """Return whether *spec* can evaluate to ``None`` on some bar."""
    if spec.op.none_policy is NonePolicy.RESOLVE:
        return False
    if spec.op.name in {"gated_percentile", "gated_max", "gated_min", "gated_lag"}:
        return True
    if spec.op.none_policy is NonePolicy.REFUSE:
        return False
    return any(_may_be_missing(by_name[ref], by_name) for ref in spec.inputs)


def load_fields_file(path: Path | str) -> FieldsDocument:
    """Read and validate the ``fields.yaml`` at *path*.

    Args:
        path: Path to the declaration file.

    Returns:
        The validated document.

    Raises:
        FieldSpecError: on any refusal listed in the module docstring, and on
            YAML that does not parse.
    """
    file_path = Path(path)
    try:
        raw = yaml.safe_load(file_path.read_bytes().decode("utf-8"))
    except yaml.YAMLError as exc:
        raise FieldSpecError(f"{file_path}: not valid YAML ({exc})") from exc
    try:
        return parse_fields_document(raw)
    except FieldSpecError as exc:
        raise FieldSpecError(f"{file_path}: {exc}") from exc


__all__ = [
    "SCHEMA_VERSION",
    "FieldSpec",
    "FieldsDocument",
    "PublishSpec",
    "ScaleSpec",
    "load_fields_file",
    "parse_fields_document",
]
