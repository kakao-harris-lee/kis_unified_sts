"""Property-based tests for ConfigMixin using Hypothesis."""

from dataclasses import dataclass
from typing import Optional

from hypothesis import given, settings, strategies as st, assume

import pytest

from shared.config.mixins import ConfigMixin


@dataclass
class SimpleConfig(ConfigMixin):
    """Simple config for property testing."""

    name: str = "default"
    count: int = 0
    rate: float = 0.0
    enabled: bool = True


@dataclass
class ValidatedConfig(ConfigMixin):
    """Config with validation for property testing."""

    threshold: float = 0.5
    max_value: int = 100

    def validate(self) -> None:
        if not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        if self.max_value < 0:
            raise ValueError("max_value must be non-negative")


class TestConfigMixinFromDictProperties:
    """Property-based tests for from_dict()."""

    @given(
        name=st.text(min_size=0, max_size=100),
        count=st.integers(min_value=-1000000, max_value=1000000),
        rate=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False),
        enabled=st.booleans(),
    )
    @settings(max_examples=100)
    def test_from_dict_round_trip(
        self, name: str, count: int, rate: float, enabled: bool
    ):
        """Property: from_dict should preserve all values."""
        data = {
            "name": name,
            "count": count,
            "rate": rate,
            "enabled": enabled,
        }

        config = SimpleConfig.from_dict(data)

        assert config.name == name
        assert config.count == count
        assert config.rate == rate
        assert config.enabled == enabled

    @given(
        known_key=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
        unknown_keys=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet="xyz_123"),
            values=st.one_of(st.integers(), st.text(), st.booleans()),
            min_size=0,
            max_size=10,
        ),
    )
    @settings(max_examples=50)
    def test_ignores_unknown_keys(self, known_key: str, unknown_keys: dict):
        """Property: Unknown keys should be ignored."""
        # Ensure unknown keys don't overlap with config fields
        config_fields = {"name", "count", "rate", "enabled"}
        unknown_keys = {k: v for k, v in unknown_keys.items() if k not in config_fields}

        data = {"name": "test", **unknown_keys}
        config = SimpleConfig.from_dict(data)

        # Should only have known attributes
        for key in unknown_keys:
            assert not hasattr(config, key) or key in config_fields

    @given(
        name=st.text(min_size=0, max_size=50),
        count=st.integers(),
    )
    @settings(max_examples=50)
    def test_params_unwrapping(self, name: str, count: int):
        """Property: 'params' key should be unwrapped."""
        data = {
            "params": {
                "name": name,
                "count": count,
            }
        }

        config = SimpleConfig.from_dict(data)

        assert config.name == name
        assert config.count == count


class TestConfigMixinToDictProperties:
    """Property-based tests for to_dict()."""

    @given(
        name=st.text(min_size=0, max_size=100),
        count=st.integers(min_value=-1000000, max_value=1000000),
        rate=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False),
        enabled=st.booleans(),
    )
    @settings(max_examples=50)
    def test_to_dict_round_trip(
        self, name: str, count: int, rate: float, enabled: bool
    ):
        """Property: to_dict should produce dict with same values."""
        config = SimpleConfig(name=name, count=count, rate=rate, enabled=enabled)
        result = config.to_dict()

        assert result["name"] == name
        assert result["count"] == count
        assert result["rate"] == rate
        assert result["enabled"] == enabled

    @given(
        name=st.text(min_size=0, max_size=50),
        count=st.integers(),
        rate=st.floats(allow_nan=False),
        enabled=st.booleans(),
    )
    @settings(max_examples=50)
    def test_from_dict_to_dict_idempotent(
        self, name: str, count: int, rate: float, enabled: bool
    ):
        """Property: from_dict(to_dict()) should be equivalent."""
        original = SimpleConfig(name=name, count=count, rate=rate, enabled=enabled)
        result_dict = original.to_dict()
        reconstructed = SimpleConfig.from_dict(result_dict)

        assert reconstructed.name == original.name
        assert reconstructed.count == original.count
        assert reconstructed.rate == original.rate
        assert reconstructed.enabled == original.enabled


class TestConfigMixinValidationProperties:
    """Property-based tests for validation."""

    @given(
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        max_value=st.integers(min_value=0, max_value=1000000),
    )
    @settings(max_examples=50)
    def test_valid_values_pass_validation(
        self, threshold: float, max_value: int
    ):
        """Property: Valid values should pass validation."""
        config = ValidatedConfig.from_dict({
            "threshold": threshold,
            "max_value": max_value,
        })

        # Should not raise
        config.validate()

        assert config.threshold == threshold
        assert config.max_value == max_value

    @given(
        threshold=st.floats(min_value=1.01, max_value=1000.0, allow_nan=False),
    )
    @settings(max_examples=30)
    def test_invalid_threshold_above_fails(self, threshold: float):
        """Property: Threshold > 1 should fail validation."""
        with pytest.raises(ValueError, match="threshold"):
            ValidatedConfig.from_dict({"threshold": threshold})

    @given(
        threshold=st.floats(max_value=-0.01, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=30)
    def test_invalid_threshold_below_fails(self, threshold: float):
        """Property: Threshold < 0 should fail validation."""
        with pytest.raises(ValueError, match="threshold"):
            ValidatedConfig.from_dict({"threshold": threshold})

    @given(
        max_value=st.integers(max_value=-1),
    )
    @settings(max_examples=30)
    def test_negative_max_value_fails(self, max_value: int):
        """Property: Negative max_value should fail validation."""
        with pytest.raises(ValueError, match="max_value"):
            ValidatedConfig.from_dict({"threshold": 0.5, "max_value": max_value})

    @given(
        threshold=st.floats(min_value=1.01, max_value=10.0, allow_nan=False),
    )
    @settings(max_examples=20)
    def test_validation_can_be_skipped(self, threshold: float):
        """Property: Validation can be disabled."""
        # Should NOT raise when validation is disabled
        config = ValidatedConfig.from_dict(
            {"threshold": threshold},
            validate=False
        )

        assert config.threshold == threshold


class TestConfigMixinEdgeCases:
    """Property-based tests for edge cases."""

    @given(data=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(st.none(), st.integers(), st.text(), st.booleans()),
        min_size=0,
        max_size=5,
    ))
    @settings(max_examples=50)
    def test_handles_arbitrary_dicts(self, data: dict):
        """Property: Should handle arbitrary dicts without crashing."""
        # Should not raise, even with weird data
        config = SimpleConfig.from_dict(data)

        # Result should always be a valid SimpleConfig
        assert isinstance(config, SimpleConfig)
        assert isinstance(config.name, str)
        assert isinstance(config.count, int)
        assert isinstance(config.enabled, bool)

    def test_empty_dict_uses_defaults(self):
        """Property: Empty dict should use defaults."""
        config = SimpleConfig.from_dict({})

        assert config.name == "default"
        assert config.count == 0
        assert config.rate == 0.0
        assert config.enabled is True
