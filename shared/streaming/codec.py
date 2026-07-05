"""Shared Redis Stream encode/decode helpers."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from pydantic import ValidationError as PydanticValidationError

from shared.models.stream_models import StreamMessage

T = TypeVar("T", bound=StreamMessage)

LegacyAdapter = Callable[[Mapping[str, str]], T]


class StreamCodecError(ValueError):
    """Base error for Redis Stream codec failures."""


class StreamEncodeError(StreamCodecError):
    """Raised when a model cannot be encoded for Redis Stream storage."""


class StreamDecodeError(StreamCodecError):
    """Raised when Redis Stream fields fail contract validation."""


def _to_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return "" if value is None else str(value)


def normalize_stream_fields(fields: Mapping[Any, Any]) -> dict[str, str]:
    """Normalize Redis field maps that may contain bytes or string keys/values."""

    return {_to_text(key): _to_text(value) for key, value in fields.items()}


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _expected_schema_version(model_cls: type[StreamMessage]) -> str:
    default = model_cls.model_fields["schema_version"].default
    return _format_scalar(default)


JsonFieldMap = Mapping[str, str]


def _decode_data_field(model_cls: type[T], fields: dict[str, str]) -> dict[str, Any]:
    raw = fields.get("data")
    if raw is None:
        return dict(fields)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StreamDecodeError(
            f"{model_cls.__name__} data field contains invalid JSON"
        ) from exc
    if not isinstance(data, dict):
        raise StreamDecodeError(
            f"{model_cls.__name__} data field must be a JSON object"
        )
    if "schema_version" not in data and "schema_version" in fields:
        data["schema_version"] = fields["schema_version"]
    return data


def _encode_json_field(model_name: str, field_name: str, value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise StreamEncodeError(
            f"{model_name}.{field_name} is not JSON serializable"
        ) from exc


def _apply_json_field_decoding(
    model_cls: type[T],
    data: dict[str, Any],
    json_fields: JsonFieldMap,
) -> dict[str, Any]:
    for model_field, wire_field in json_fields.items():
        raw = data.pop(wire_field, None)
        if raw is None:
            continue
        try:
            data[model_field] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StreamDecodeError(
                f"{model_cls.__name__}.{wire_field} contains invalid JSON"
            ) from exc
    return data


def encode(
    model: StreamMessage,
    *,
    json_fields: JsonFieldMap | None = None,
) -> dict[str, str]:
    """Encode a stream model into Redis-safe flat string fields.

    Models with only scalar top-level fields are emitted as flat fields. Models
    with any nested container are emitted as ``schema_version`` + ``data`` JSON.
    """

    try:
        data = model.model_dump(exclude_none=True)
    except Exception as exc:
        raise StreamEncodeError(f"failed to dump {type(model).__name__}") from exc

    fields: dict[str, str] = {}
    for model_field, wire_field in (json_fields or {}).items():
        if model_field not in data:
            continue
        fields[wire_field] = _encode_json_field(
            type(model).__name__,
            model_field,
            data.pop(model_field),
        )

    has_nested = any(isinstance(v, (dict, list, tuple, set)) for v in data.values())
    if has_nested:
        if fields:
            nested_fields = [
                key
                for key, value in data.items()
                if isinstance(value, (dict, list, tuple, set))
            ]
            raise StreamEncodeError(
                f"{type(model).__name__} has unmapped nested fields: "
                f"{', '.join(nested_fields)}"
            )
        try:
            return {
                "schema_version": _format_scalar(data.get("schema_version", 1)),
                "data": model.model_dump_json(exclude_none=True),
            }
        except Exception as exc:
            raise StreamEncodeError(
                f"failed to JSON encode {type(model).__name__}"
            ) from exc

    fields.update({key: _format_scalar(value) for key, value in data.items()})
    return fields


def decode(
    model_cls: type[T],
    fields: Mapping[Any, Any],
    *,
    legacy_adapter: LegacyAdapter[T] | None = None,
    json_fields: JsonFieldMap | None = None,
) -> T:
    """Decode Redis Stream fields into a Pydantic stream model.

    Missing ``schema_version`` is treated as legacy data and requires an
    explicit adapter. Version mismatches are rejected.
    """

    normalized = normalize_stream_fields(fields)
    raw_version = normalized.get("schema_version")
    if raw_version is None:
        if legacy_adapter is None:
            raise StreamDecodeError(f"{model_cls.__name__} missing schema_version")
        try:
            return legacy_adapter(normalized)
        except Exception as exc:
            raise StreamDecodeError(
                f"{model_cls.__name__} legacy decode failed: {exc}"
            ) from exc

    expected = _expected_schema_version(model_cls)
    if raw_version != expected:
        raise StreamDecodeError(
            f"{model_cls.__name__} schema_version={raw_version!r} "
            f"does not match expected {expected!r}"
        )

    data = _decode_data_field(model_cls, normalized)
    if json_fields:
        data = _apply_json_field_decoding(model_cls, data, json_fields)
    data["schema_version"] = model_cls.model_fields["schema_version"].default
    try:
        return model_cls.model_validate(data)
    except PydanticValidationError as exc:
        field_names = sorted(
            {
                ".".join(str(part) for part in error.get("loc", ()))
                for error in exc.errors()
            }
        )
        fields_text = ", ".join(field_names) if field_names else "unknown"
        raise StreamDecodeError(
            f"{model_cls.__name__} validation failed for fields: {fields_text}"
        ) from exc
