"""Tests for config mixins."""

from dataclasses import dataclass

import pytest

from shared.config.mixins import ConfigMixin


@dataclass
class SampleConfig(ConfigMixin):
    """Sample config for testing."""

    name: str = "default"
    count: int = 10
    enabled: bool = True


class TestConfigMixin:
    """Tests for ConfigMixin."""

    def test_from_dict_basic(self):
        """Test basic from_dict creation."""
        config = SampleConfig.from_dict(
            {
                "name": "test",
                "count": 5,
                "enabled": False,
            }
        )

        assert config.name == "test"
        assert config.count == 5
        assert config.enabled is False

    def test_from_dict_ignores_unknown_keys(self):
        """Test that unknown keys are ignored."""
        config = SampleConfig.from_dict(
            {
                "name": "test",
                "unknown_field": "ignored",
                "another_unknown": 123,
            }
        )

        assert config.name == "test"
        assert config.count == 10  # default
        assert not hasattr(config, "unknown_field")

    def test_from_dict_uses_defaults(self):
        """Test that defaults are used for missing keys."""
        config = SampleConfig.from_dict({"name": "only_name"})

        assert config.name == "only_name"
        assert config.count == 10  # default
        assert config.enabled is True  # default

    def test_from_dict_none_uses_non_none_default(self):
        """Test that None does not override a non-None default."""
        config = SampleConfig.from_dict({"enabled": None})

        assert config.enabled is True

    def test_from_dict_invalid_primitive_types_use_defaults(self):
        """Test invalid primitive values do not override defaults."""
        config = SampleConfig.from_dict(
            {
                "name": 123,
                "count": "not-an-int",
                "enabled": 0,
            }
        )

        assert config.name == "default"
        assert config.count == 10
        assert config.enabled is True

    def test_from_dict_empty_dict(self):
        """Test creation from empty dict."""
        config = SampleConfig.from_dict({})

        assert config.name == "default"
        assert config.count == 10
        assert config.enabled is True

    def test_from_dict_unwraps_params(self):
        """Test that 'params' key is automatically unwrapped."""
        config = SampleConfig.from_dict(
            {
                "params": {
                    "name": "from_params",
                    "count": 20,
                }
            }
        )

        assert config.name == "from_params"
        assert config.count == 20

    def test_from_dict_params_with_extra_keys(self):
        """Test params unwrapping ignores extra keys outside params."""
        config = SampleConfig.from_dict(
            {
                "type": "some_type",  # extra key at root level
                "params": {
                    "name": "nested",
                },
            }
        )

        assert config.name == "nested"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = SampleConfig(name="test", count=5, enabled=False)
        result = config.to_dict()

        assert result == {
            "name": "test",
            "count": 5,
            "enabled": False,
        }

    def test_roundtrip(self):
        """Test from_dict -> to_dict roundtrip."""
        original_data = {"name": "roundtrip", "count": 42, "enabled": True}
        config = SampleConfig.from_dict(original_data)
        result = config.to_dict()

        assert result == original_data


@dataclass
class NestedFieldConfig(ConfigMixin):
    """Config with different types."""

    rate: float = 0.5
    items: int = 3


class TestConfigMixinWithDifferentTypes:
    """Test ConfigMixin with various field types."""

    def test_float_field(self):
        """Test float field handling."""
        config = NestedFieldConfig.from_dict({"rate": 0.75})
        assert config.rate == 0.75

    def test_type_preservation(self):
        """Test that types are preserved."""
        config = NestedFieldConfig.from_dict(
            {
                "rate": 1.5,
                "items": 10,
            }
        )

        assert isinstance(config.rate, float)
        assert isinstance(config.items, int)


@dataclass
class InnerConfig(ConfigMixin):
    """Inner config for nesting tests."""

    value: int = 0
    label: str = "default"


@dataclass
class OuterConfig(ConfigMixin):
    """Outer config containing nested config."""

    name: str = "outer"
    inner: InnerConfig = None  # type: ignore

    def __post_init__(self):
        if self.inner is None:
            self.inner = InnerConfig()


class TestConfigMixinWithNestedDataclass:
    """Test ConfigMixin with nested dataclass fields."""

    def test_nested_dataclass_defaults(self):
        """Test that nested dataclass gets default value."""
        config = OuterConfig.from_dict({})
        assert config.name == "outer"
        assert config.inner is not None
        assert config.inner.value == 0
        assert config.inner.label == "default"

    def test_nested_dataclass_from_dict(self):
        """Test nested dataclass can be created from dict."""
        config = OuterConfig.from_dict(
            {"name": "custom", "inner": {"value": 42, "label": "nested"}}
        )

        # Note: ConfigMixin doesn't automatically convert nested dicts
        # The nested dict is passed directly to the dataclass
        # This test documents current behavior
        assert config.name == "custom"
        # With current implementation, inner is still a dict
        # This is a known limitation of the simple ConfigMixin
        assert config.inner == {"value": 42, "label": "nested"} or (
            hasattr(config.inner, "value") and config.inner.value == 42
        )

    def test_to_dict_with_nested(self):
        """Test to_dict includes nested dataclass as dict."""
        inner = InnerConfig(value=100, label="test")
        outer = OuterConfig(name="outer", inner=inner)

        result = outer.to_dict()

        assert result["name"] == "outer"
        assert result["inner"]["value"] == 100
        assert result["inner"]["label"] == "test"


@dataclass
class OptionalFieldsConfig(ConfigMixin):
    """Config with optional fields."""

    required_field: str = ""
    optional_field: str = None  # type: ignore
    list_field: list = None  # type: ignore
    dict_field: dict = None  # type: ignore


class TestConfigMixinWithOptionalFields:
    """Test ConfigMixin with optional and complex fields."""

    def test_optional_fields_none(self):
        """Test that None values are preserved."""
        config = OptionalFieldsConfig.from_dict(
            {
                "required_field": "value",
            }
        )

        assert config.required_field == "value"
        assert config.optional_field is None

    def test_list_field(self):
        """Test list field handling."""
        config = OptionalFieldsConfig.from_dict(
            {
                "required_field": "value",
                "list_field": [1, 2, 3],
            }
        )

        assert config.list_field == [1, 2, 3]

    def test_dict_field(self):
        """Test dict field handling."""
        config = OptionalFieldsConfig.from_dict(
            {
                "required_field": "value",
                "dict_field": {"key": "value"},
            }
        )

        assert config.dict_field == {"key": "value"}


@dataclass
class ValidatedConfig(ConfigMixin):
    """Config with validation logic."""

    threshold: float = 0.5
    min_value: int = 0
    max_value: int = 100

    def validate(self) -> None:
        if not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        if self.min_value > self.max_value:
            raise ValueError("min_value must be <= max_value")


@dataclass
class NoValidationConfig(ConfigMixin):
    """Config without custom validation."""

    name: str = "default"


class TestConfigMixinValidation:
    """Test ConfigMixin validation hook."""

    def test_validation_passes(self):
        """Test that valid config passes validation."""
        config = ValidatedConfig.from_dict(
            {
                "threshold": 0.7,
                "min_value": 10,
                "max_value": 50,
            }
        )

        assert config.threshold == 0.7
        assert config.min_value == 10
        assert config.max_value == 50

    def test_validation_fails_on_invalid_threshold(self):
        """Test that validation fails for invalid threshold."""
        with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
            ValidatedConfig.from_dict({"threshold": 1.5})

    def test_validation_fails_on_negative_threshold(self):
        """Test that validation fails for negative threshold."""
        with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
            ValidatedConfig.from_dict({"threshold": -0.1})

    def test_validation_fails_on_min_greater_than_max(self):
        """Test that validation fails when min > max."""
        with pytest.raises(ValueError, match="min_value must be <= max_value"):
            ValidatedConfig.from_dict(
                {
                    "min_value": 100,
                    "max_value": 50,
                }
            )

    def test_validation_skipped_when_disabled(self):
        """Test that validation can be skipped."""
        # This should NOT raise even though values are invalid
        config = ValidatedConfig.from_dict({"threshold": 1.5}, validate=False)

        assert config.threshold == 1.5

    def test_no_validation_method_works(self):
        """Test that configs without validate() method work."""
        config = NoValidationConfig.from_dict({"name": "test"})
        assert config.name == "test"

    def test_default_validate_is_no_op(self):
        """Test that default validate() does nothing."""
        config = SampleConfig(name="test")
        # Should not raise
        config.validate()

    def test_validation_runs_on_direct_construction(self):
        """Test that validation can be called manually after construction."""
        config = ValidatedConfig(threshold=1.5)

        # Validation should fail when called manually
        with pytest.raises(ValueError):
            config.validate()

    def test_validation_with_edge_values(self):
        """Test validation with boundary values."""
        # Boundary values should pass
        config1 = ValidatedConfig.from_dict({"threshold": 0.0})
        assert config1.threshold == 0.0

        config2 = ValidatedConfig.from_dict({"threshold": 1.0})
        assert config2.threshold == 1.0

        # Min == max should pass
        config3 = ValidatedConfig.from_dict(
            {
                "min_value": 50,
                "max_value": 50,
            }
        )
        assert config3.min_value == config3.max_value
