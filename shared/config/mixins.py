"""Configuration mixins for reducing code duplication.

Provides reusable from_dict() implementations for dataclass configs.

Usage:
    from dataclasses import dataclass
    from shared.config.mixins import ConfigMixin

    @dataclass
    class MyConfig(ConfigMixin):
        field1: str = "default"
        field2: int = 10

    # Now can create from dict:
    config = MyConfig.from_dict({"field1": "value", "unknown": "ignored"})

Validation:
    @dataclass
    class ValidatedConfig(ConfigMixin):
        threshold: float = 0.5

        def validate(self) -> None:
            if not 0 <= self.threshold <= 1:
                raise ValueError("threshold must be between 0 and 1")

    # Raises ValueError if validation fails:
    config = ValidatedConfig.from_dict({"threshold": 1.5})
"""

from __future__ import annotations

import dataclasses
import warnings
from typing import Any, TypeVar, get_args, get_origin, get_type_hints

T = TypeVar("T", bound="ConfigMixin")

# Cache resolved type hints per class. ``get_type_hints`` resolves PEP 563
# stringized annotations (``from __future__ import annotations``) back to real
# ``type`` objects so the type guard behaves identically regardless of whether a
# config module opted into stringized annotations.
_TYPE_HINT_CACHE: dict[type, dict[str, Any]] = {}


def _resolve_type_hints(cls: type) -> dict[str, Any]:
    cached = _TYPE_HINT_CACHE.get(cls)
    if cached is not None:
        return cached
    try:
        hints = get_type_hints(cls)
    except Exception:  # noqa: BLE001 - fall back to raw field.type on any failure
        hints = {}
    _TYPE_HINT_CACHE[cls] = hints
    return hints


def _field_has_default(field: dataclasses.Field[Any]) -> bool:
    return (
        field.default is not dataclasses.MISSING
        or field.default_factory is not dataclasses.MISSING
    )


def _matches_field_type(value: Any, annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is not None:
        if origin is list:
            return isinstance(value, list)
        if origin is dict:
            return isinstance(value, dict)
        if origin is set:
            return isinstance(value, set)
        if origin is tuple:
            return isinstance(value, tuple)
        return any(_matches_field_type(value, arg) for arg in get_args(annotation))

    if annotation is Any or not isinstance(annotation, type):
        return True
    if annotation is bool:
        return isinstance(value, bool)
    if annotation is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if annotation is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if dataclasses.is_dataclass(annotation) and isinstance(value, dict):
        return True
    return isinstance(value, annotation)


class ConfigMixin:
    """Mixin providing from_dict() for dataclasses.

    Supports:
    - Automatic field filtering (ignores unknown keys)
    - Optional "params" key unwrapping for nested YAML configs
    - Type-safe creation
    - Optional validation via validate() hook
    """

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any], *, validate: bool = True) -> T:
        """Create config from dictionary, ignoring unknown keys.

        Args:
            data: Configuration dictionary. May contain a "params" key
                  which will be unwrapped automatically.
            validate: Whether to run validation after creation (default: True)

        Returns:
            New instance with values from dict

        Raises:
            ValueError: If validation fails (or any subclass like ConfigValidationError)

        Example:
            config = MyConfig.from_dict({
                "field1": "value",
                "unknown_field": "ignored"
            })

            # With params unwrapping (common in YAML configs):
            config = MyConfig.from_dict({
                "params": {
                    "field1": "value"
                }
            })

            # Skip validation:
            config = MyConfig.from_dict(data, validate=False)
        """
        # Emit deprecation warning
        warnings.warn(
            f"{cls.__name__}.from_dict() is deprecated. "
            "Use ServiceConfigBase for new service configurations. "
            "See shared/config/base.py for migration guidance.",
            DeprecationWarning,
            stacklevel=2,
        )

        # Unwrap "params" key if present (common in strategy YAML configs)
        if "params" in data and isinstance(data["params"], dict):
            data = data["params"]

        # Get valid fields for this dataclass
        fields = {f.name: f for f in dataclasses.fields(cls)}
        # Resolve stringized (PEP 563) annotations so the type guard below is
        # applied consistently to every config class, not just those that avoid
        # ``from __future__ import annotations``.
        hints = _resolve_type_hints(cls)

        # Filter to only known fields. Treat None as "missing" when the
        # dataclass already has a non-None default; this keeps arbitrary config
        # dicts from erasing bool/int/string defaults while preserving fields
        # that explicitly default to None.
        filtered = {}
        for key, value in data.items():
            field = fields.get(key)
            if field is None:
                continue
            if value is None and (
                field.default_factory is not dataclasses.MISSING
                or field.default is not dataclasses.MISSING
                and field.default is not None
            ):
                continue
            annotation = hints.get(key, field.type)
            if (
                value is not None
                and _field_has_default(field)
                and not _matches_field_type(value, annotation)
            ):
                continue
            filtered[key] = value

        instance = cls(**filtered)

        # Run validation if enabled and validate() is defined
        if validate:
            instance.validate()

        return instance

    def validate(self) -> None:
        """Validate configuration values.

        Override this method in subclasses to add custom validation logic.
        Raise ValueError (or any subclass) for invalid configs.

        Example:
            def validate(self) -> None:
                if self.threshold < 0:
                    raise ValueError("threshold must be non-negative")
                if self.max_items < self.min_items:
                    raise ValueError("max_items must be >= min_items")
        """
        # Default implementation does nothing - override in subclasses
        pass

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Dictionary with all field values
        """
        return dataclasses.asdict(self)
