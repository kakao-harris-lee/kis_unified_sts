"""Base configuration class for services.

Provides standard from_yaml() and from_env() class methods that eliminate
boilerplate across service config classes.

Usage:
    from pydantic import Field
    from shared.config.base import ServiceConfigBase

    class MyServiceConfig(ServiceConfigBase):
        threshold: float = Field(default=0.5, description="Detection threshold")
        enabled: bool = Field(default=True, description="Service enabled")
        database: str = Field(default="market", description="Database name")

    # Load from YAML file
    config = MyServiceConfig.from_yaml("my_service.yaml")

    # Load from YAML with specific section
    config = MyServiceConfig.from_yaml("services.yaml", section="my_service")

    # Load from environment variables
    config = MyServiceConfig.from_env(env_prefix="MY_SERVICE_")

    # Load from YAML with env var overrides
    config = MyServiceConfig.from_yaml(
        "my_service.yaml",
        apply_env_overrides=True,
        env_prefix="MY_SERVICE_"
    )

    # Validate database name
    MyServiceConfig.validate_database_name("market")  # OK
    MyServiceConfig.validate_database_name("drop; table")  # Raises ValueError
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, field_validator

from shared.config.loader import ConfigLoader

logger = logging.getLogger(__name__)


class ServiceConfigBase(BaseModel):
    """Base class for service configurations.

    Provides standard configuration loading patterns:
    - from_yaml(): Load from YAML file with optional section extraction
    - from_env(): Load from environment variables with prefix
    - Environment variable precedence over YAML values
    - Database name validation

    All subclasses automatically inherit these methods and can customize
    behavior by overriding class attributes or methods.

    Class Attributes:
        _default_config_file: Default YAML filename (e.g., "my_service.yaml")
        _default_section: Default section name in YAML file
        _env_prefix: Default environment variable prefix
    """

    model_config = ConfigDict(
        frozen=False,  # Allow mutation for now, subclasses can override
        extra="ignore",  # Ignore unknown fields from YAML/env
        validate_assignment=True,  # Validate on field assignment
    )

    # Class-level configuration (override in subclasses)
    _default_config_file: ClassVar[str | None] = None
    _default_section: ClassVar[str | None] = None
    _env_prefix: ClassVar[str | None] = None

    # Database name validation pattern (alphanumeric + underscore only)
    _DATABASE_NAME_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9_]+$")

    @classmethod
    def from_yaml(
        cls,
        path: str | None = None,
        section: str | None = None,
        *,
        apply_env_overrides: bool = False,
        env_prefix: str | None = None,
    ) -> Self:
        """Load configuration from YAML file.

        Args:
            path: YAML file path (relative to config directory).
                  If None, uses cls._default_config_file.
            section: Section name to extract from YAML.
                     If None, uses cls._default_section.
                     If section is specified and exists, extracts that key.
                     Otherwise, uses the entire YAML as config dict.
            apply_env_overrides: If True, apply environment variable overrides
                                 after loading from YAML (default: False)
            env_prefix: Environment variable prefix for overrides
                        (e.g., "MY_SERVICE_"). If None, uses cls._env_prefix.

        Returns:
            Config instance with values from YAML (and optionally env vars)

        Raises:
            ConfigNotFoundError: If config file not found
            ConfigValidationError: If validation fails

        Example:
            # Load from default file
            config = MyConfig.from_yaml()

            # Load from specific file
            config = MyConfig.from_yaml("my_service.yaml")

            # Load specific section
            config = MyConfig.from_yaml("services.yaml", section="my_service")

            # Load with env var overrides
            config = MyConfig.from_yaml(
                "my_service.yaml",
                apply_env_overrides=True,
                env_prefix="MY_SERVICE_"
            )
        """
        # Determine config file path
        if path is None:
            path = cls._default_config_file
            if path is None:
                raise ValueError(
                    f"{cls.__name__} requires 'path' argument or "
                    "_default_config_file class attribute"
                )

        # Load YAML via ConfigLoader
        raw_data = ConfigLoader.load(path)

        # Extract section if specified
        if section is not None:
            section_key = section
        elif cls._default_section is not None:
            section_key = cls._default_section
        else:
            section_key = None

        if section_key is not None:
            if isinstance(raw_data, dict) and section_key in raw_data:
                config_data = raw_data[section_key]
            else:
                # Section not found or data is not a dict - use raw data
                config_data = raw_data
        else:
            config_data = raw_data

        # Ensure we have a dict
        if not isinstance(config_data, dict):
            config_data = {}

        # Apply environment variable overrides if requested
        if apply_env_overrides:
            prefix = env_prefix if env_prefix is not None else cls._env_prefix
            if prefix:
                env_overrides = cls._extract_env_vars(prefix)
                config_data.update(env_overrides)

        # Create and validate config instance
        return cls(**config_data)

    @classmethod
    def from_env(cls, env_prefix: str | None = None, **overrides: Any) -> Self:
        """Load configuration from environment variables.

        Args:
            env_prefix: Environment variable prefix (e.g., "MY_SERVICE_").
                        If None, uses cls._env_prefix.
                        Prefix is stripped before mapping to field names.
            **overrides: Additional field overrides (take precedence over env vars)

        Returns:
            Config instance with values from environment variables

        Example:
            # With default prefix from class
            config = MyConfig.from_env()

            # With custom prefix
            config = MyConfig.from_env(env_prefix="MY_SERVICE_")

            # With overrides
            config = MyConfig.from_env(env_prefix="MY_SERVICE_", enabled=False)

        Environment variable mapping:
            - Field name is converted to uppercase
            - Prefix is prepended
            - Example: field "threshold" with prefix "MY_SERVICE_"
                       maps to "MY_SERVICE_THRESHOLD"
            - Boolean fields: "true"/"false" (case-insensitive)
            - Numeric fields: parsed as int/float
        """
        # Determine prefix
        prefix = env_prefix if env_prefix is not None else cls._env_prefix
        if prefix is None:
            # No prefix - load all model fields from env directly
            prefix = ""

        # Extract env vars matching prefix
        env_data = cls._extract_env_vars(prefix)

        # Apply overrides (take precedence)
        env_data.update(overrides)

        # Create and validate config instance
        return cls(**env_data)

    @classmethod
    def _extract_env_vars(cls, prefix: str) -> dict[str, Any]:
        """Extract environment variables matching prefix and field names.

        Args:
            prefix: Environment variable prefix (e.g., "MY_SERVICE_")

        Returns:
            Dictionary mapping field names to parsed values
        """
        env_data: dict[str, Any] = {}

        # Get field names from model
        field_names = set(cls.model_fields.keys())

        # Scan environment variables
        for env_key, env_value in os.environ.items():
            # Check if env var matches prefix
            if not env_key.startswith(prefix):
                continue

            # Strip prefix and convert to lowercase for field matching
            field_name = env_key[len(prefix) :].lower()

            # Check if this matches a model field
            if field_name not in field_names:
                continue

            # Get field info for type conversion
            field_info = cls.model_fields[field_name]
            field_type = field_info.annotation

            # Parse value based on type
            try:
                parsed_value = cls._parse_env_value(env_value, field_type)
                env_data[field_name] = parsed_value
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Failed to parse {env_key}={env_value} as {field_type}: {e}"
                )
                # Use raw string value as fallback
                env_data[field_name] = env_value

        return env_data

    @classmethod
    def _parse_env_value(cls, value: str, field_type: Any) -> Any:
        """Parse environment variable value based on field type.

        Args:
            value: String value from environment variable
            field_type: Target field type annotation

        Returns:
            Parsed value in appropriate type

        Raises:
            ValueError: If parsing fails
        """
        # Handle None/optional types
        if value == "":
            return None

        # Get the actual type (unwrap Optional, etc.)
        actual_type = field_type
        if hasattr(field_type, "__origin__"):
            # Handle Optional[X] -> X
            if field_type.__origin__ is type(None) or str(field_type).startswith(
                "typing.Union"
            ):
                args = getattr(field_type, "__args__", ())
                # Get first non-None type
                actual_type = next((t for t in args if t is not type(None)), str)

        # Type-specific parsing
        if actual_type is bool or str(actual_type) == "<class 'bool'>":
            return value.lower() in ("true", "1", "yes", "on")
        elif actual_type is int or str(actual_type) == "<class 'int'>":
            return int(value)
        elif actual_type is float or str(actual_type) == "<class 'float'>":
            return float(value)
        else:
            # Default to string
            return value

    @classmethod
    def validate_database_name(cls, name: str) -> str:
        """Validate database name to prevent SQL injection.

        Args:
            name: Database name to validate

        Returns:
            Validated database name (same as input)

        Raises:
            ValueError: If name contains invalid characters

        Example:
            validate_database_name("market")  # OK
            validate_database_name("market_data")  # OK
            validate_database_name("drop; table")  # Raises ValueError
        """
        if not cls._DATABASE_NAME_PATTERN.match(name):
            raise ValueError(
                f"Database name must contain only alphanumeric characters "
                f"and underscores, got: {name!r}"
            )
        return name

    @field_validator("database", mode="before", check_fields=False)
    @classmethod
    def _validate_database_field(cls, v: Any) -> Any:
        """Validate 'database' field if present in the model.

        This validator runs automatically for any subclass that has
        a 'database' field.
        """
        if isinstance(v, str):
            return cls.validate_database_name(v)
        return v

    def model_dump_yaml(self) -> str:
        """Export configuration as YAML string.

        Returns:
            YAML representation of config

        Example:
            config = MyConfig(threshold=0.7, enabled=True)
            print(config.model_dump_yaml())
        """
        import yaml

        return yaml.dump(self.model_dump(), default_flow_style=False, sort_keys=False)
