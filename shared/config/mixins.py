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
from typing import Any, TypeVar

T = TypeVar("T", bound="ConfigMixin")


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

        # Get valid field names for this dataclass
        field_names = {f.name for f in dataclasses.fields(cls)}

        # Filter to only known fields
        filtered = {k: v for k, v in data.items() if k in field_names}

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
