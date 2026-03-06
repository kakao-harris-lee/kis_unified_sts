"""Configuration mixins for reducing code duplication.

Provides reusable from_dict() and from_yaml() implementations for dataclass configs.

Usage:
    from dataclasses import dataclass
    from shared.config.mixins import ConfigMixin

    @dataclass
    class MyConfig(ConfigMixin):
        field1: str = "default"
        field2: int = 10

    # Create from dict:
    config = MyConfig.from_dict({"field1": "value", "unknown": "ignored"})

    # Create from YAML (loads via ConfigLoader):
    config = MyConfig.from_yaml("my_service.yaml")

    # Extract a specific section:
    config = MyConfig.from_yaml("ml/rl_mppo.yaml", section="env")

    # Merge multiple sections (fields matched by name):
    config = MyConfig.from_yaml("ml/rl_mppo.yaml", sections=["env", "reward"])

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
from typing import Any, TypeVar

T = TypeVar("T", bound="ConfigMixin")


class ConfigMixin:
    """Mixin providing from_dict() and from_yaml() for dataclasses.

    Supports:
    - Automatic field filtering (ignores unknown keys)
    - Optional "params" key unwrapping for nested YAML configs
    - YAML loading via ConfigLoader with section extraction
    - Type-safe creation
    - Optional validation via validate() hook
    """

    @classmethod
    def from_yaml(
        cls: type[T],
        path: str,
        *,
        section: str | None = None,
        sections: list[str] | None = None,
    ) -> T:
        """Load config from a YAML file via ConfigLoader.

        Args:
            path: YAML file path relative to config/ directory
                (e.g. "daily_scanner.yaml", "ml/rl_mppo.yaml").
            section: Extract a single top-level section key before
                passing to from_dict(). Mutually exclusive with sections.
            sections: Merge multiple top-level section keys into a single
                dict (later sections override earlier ones). Useful when
                dataclass fields span multiple YAML sections.

        Returns:
            New validated config instance.

        Raises:
            ValueError: If both section and sections are provided.
            shared.config.loader.ConfigNotFoundError: If YAML file not found.
        """
        if section and sections:
            raise ValueError("Cannot specify both 'section' and 'sections'")

        from shared.config.loader import ConfigLoader

        raw = ConfigLoader.load(path)

        if section:
            raw = raw.get(section, {})
        elif sections:
            merged: dict[str, Any] = {}
            for key in sections:
                merged.update(raw.get(key, {}))
            raw = merged

        return cls.from_dict(raw)

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
