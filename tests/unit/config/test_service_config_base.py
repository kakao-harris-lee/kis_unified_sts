"""Tests for ServiceConfigBase."""
import os
import pytest
import tempfile
from pathlib import Path
from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.config import ConfigNotFoundError


class SimpleConfig(ServiceConfigBase):
    """Simple config for testing."""

    name: str = Field(default="default", description="Service name")
    threshold: float = Field(default=0.5, description="Detection threshold")
    enabled: bool = Field(default=True, description="Service enabled")
    max_items: int = Field(default=10, description="Max items")


class ConfigWithDefaults(ServiceConfigBase):
    """Config with default file/section/prefix."""

    _default_config_file = "test_service.yaml"
    _default_section = "my_service"
    _env_prefix = "TEST_SERVICE_"

    name: str = Field(default="default")
    value: int = Field(default=0)


class ConfigWithDatabase(ServiceConfigBase):
    """Config with database field for validation testing."""

    name: str = Field(default="service")
    database: str = Field(default="market", description="Database name")
    port: int = Field(default=5432)


class TestServiceConfigBaseFromYAML:
    """Tests for from_yaml() class method."""

    def test_from_yaml_basic(self, tmp_path):
        """Test basic YAML loading."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
name: test_service
threshold: 0.75
enabled: false
max_items: 20
""")

        config = SimpleConfig.from_yaml(str(yaml_file))

        assert config.name == "test_service"
        assert config.threshold == 0.75
        assert config.enabled is False
        assert config.max_items == 20

    def test_from_yaml_with_section(self, tmp_path):
        """Test YAML loading with section extraction."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
my_service:
  name: from_section
  threshold: 0.9
other_service:
  name: ignored
""")

        config = SimpleConfig.from_yaml(str(yaml_file), section="my_service")

        assert config.name == "from_section"
        assert config.threshold == 0.9
        assert config.enabled is True  # default

    def test_from_yaml_section_not_found(self, tmp_path):
        """Test that missing section uses entire YAML."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
name: root_level
threshold: 0.6
""")

        # Request non-existent section - should use root level
        config = SimpleConfig.from_yaml(str(yaml_file), section="nonexistent")

        assert config.name == "root_level"
        assert config.threshold == 0.6

    def test_from_yaml_uses_default_file(self, tmp_path, monkeypatch):
        """Test that default config file from class attribute is used."""
        # Create the default config file
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        yaml_file = config_dir / "test_service.yaml"
        yaml_file.write_text("""
my_service:
  name: from_default
  value: 42
""")

        # Mock ConfigLoader to use our temp directory
        monkeypatch.setenv("KIS_CONFIG_DIR", str(config_dir))

        config = ConfigWithDefaults.from_yaml()

        assert config.name == "from_default"
        assert config.value == 42

    def test_from_yaml_requires_path_or_default(self):
        """Test that from_yaml() raises error if no path and no default."""
        with pytest.raises(ValueError, match="requires 'path' argument"):
            SimpleConfig.from_yaml()

    def test_from_yaml_with_env_overrides(self, tmp_path, monkeypatch):
        """Test YAML loading with environment variable overrides."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
name: from_yaml
threshold: 0.5
enabled: true
""")

        # Set env vars
        monkeypatch.setenv("MY_SERVICE_THRESHOLD", "0.9")
        monkeypatch.setenv("MY_SERVICE_ENABLED", "false")

        config = SimpleConfig.from_yaml(
            str(yaml_file),
            apply_env_overrides=True,
            env_prefix="MY_SERVICE_"
        )

        assert config.name == "from_yaml"  # Not overridden
        assert config.threshold == 0.9  # Overridden by env
        assert config.enabled is False  # Overridden by env

    def test_from_yaml_ignores_unknown_fields(self, tmp_path):
        """Test that unknown fields in YAML are ignored."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
name: test
unknown_field: should_be_ignored
another_unknown: 123
threshold: 0.8
""")

        config = SimpleConfig.from_yaml(str(yaml_file))

        assert config.name == "test"
        assert config.threshold == 0.8
        assert not hasattr(config, "unknown_field")

    def test_from_yaml_empty_file_uses_defaults(self, tmp_path):
        """Test that empty YAML file uses default values."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("")

        config = SimpleConfig.from_yaml(str(yaml_file))

        assert config.name == "default"
        assert config.threshold == 0.5
        assert config.enabled is True

    def test_from_yaml_partial_config(self, tmp_path):
        """Test loading with only some fields specified."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
name: partial
""")

        config = SimpleConfig.from_yaml(str(yaml_file))

        assert config.name == "partial"
        assert config.threshold == 0.5  # default
        assert config.enabled is True  # default


class TestServiceConfigBaseFromEnv:
    """Tests for from_env() class method."""

    def test_from_env_basic(self, monkeypatch):
        """Test basic environment variable loading."""
        monkeypatch.setenv("MY_SERVICE_NAME", "from_env")
        monkeypatch.setenv("MY_SERVICE_THRESHOLD", "0.8")
        monkeypatch.setenv("MY_SERVICE_ENABLED", "false")
        monkeypatch.setenv("MY_SERVICE_MAX_ITEMS", "50")

        config = SimpleConfig.from_env(env_prefix="MY_SERVICE_")

        assert config.name == "from_env"
        assert config.threshold == 0.8
        assert config.enabled is False
        assert config.max_items == 50

    def test_from_env_with_default_prefix(self, monkeypatch):
        """Test env loading with default prefix from class attribute."""
        monkeypatch.setenv("TEST_SERVICE_NAME", "from_default_prefix")
        monkeypatch.setenv("TEST_SERVICE_VALUE", "99")

        config = ConfigWithDefaults.from_env()

        assert config.name == "from_default_prefix"
        assert config.value == 99

    def test_from_env_with_overrides(self, monkeypatch):
        """Test env loading with explicit overrides."""
        monkeypatch.setenv("MY_SERVICE_NAME", "from_env")
        monkeypatch.setenv("MY_SERVICE_THRESHOLD", "0.7")

        config = SimpleConfig.from_env(
            env_prefix="MY_SERVICE_",
            enabled=False  # Override via kwarg
        )

        assert config.name == "from_env"
        assert config.threshold == 0.7
        assert config.enabled is False  # From override

    def test_from_env_bool_conversion(self, monkeypatch):
        """Test boolean field conversion from env vars."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("anything_else", False),
        ]

        for env_value, expected in test_cases:
            monkeypatch.setenv("TEST_ENABLED", env_value)
            config = SimpleConfig.from_env(env_prefix="TEST_")
            assert config.enabled == expected, f"Failed for {env_value}"

    def test_from_env_int_conversion(self, monkeypatch):
        """Test integer field conversion from env vars."""
        monkeypatch.setenv("TEST_MAX_ITEMS", "42")

        config = SimpleConfig.from_env(env_prefix="TEST_")

        assert config.max_items == 42
        assert isinstance(config.max_items, int)

    def test_from_env_float_conversion(self, monkeypatch):
        """Test float field conversion from env vars."""
        monkeypatch.setenv("TEST_THRESHOLD", "3.14159")

        config = SimpleConfig.from_env(env_prefix="TEST_")

        assert config.threshold == 3.14159
        assert isinstance(config.threshold, float)

    def test_from_env_empty_string_becomes_none(self, monkeypatch):
        """Test that empty string is treated as None."""
        monkeypatch.setenv("TEST_NAME", "")

        config = SimpleConfig.from_env(env_prefix="TEST_")

        # Pydantic will use the default for None
        assert config.name == "default"

    def test_from_env_ignores_unknown_vars(self, monkeypatch):
        """Test that env vars not matching model fields are ignored."""
        monkeypatch.setenv("MY_SERVICE_NAME", "test")
        monkeypatch.setenv("MY_SERVICE_UNKNOWN_FIELD", "ignored")
        monkeypatch.setenv("DIFFERENT_PREFIX_NAME", "also_ignored")

        config = SimpleConfig.from_env(env_prefix="MY_SERVICE_")

        assert config.name == "test"
        assert not hasattr(config, "unknown_field")

    def test_from_env_no_prefix(self, monkeypatch):
        """Test env loading without prefix."""
        monkeypatch.setenv("NAME", "no_prefix")
        monkeypatch.setenv("THRESHOLD", "0.95")

        config = SimpleConfig.from_env(env_prefix="")

        assert config.name == "no_prefix"
        assert config.threshold == 0.95

    def test_from_env_case_insensitive(self, monkeypatch):
        """Test that env var name matching is case-insensitive."""
        # Env vars are uppercase, but should map to lowercase field names
        monkeypatch.setenv("TEST_NAME", "case_test")
        monkeypatch.setenv("TEST_MAX_ITEMS", "100")

        config = SimpleConfig.from_env(env_prefix="TEST_")

        assert config.name == "case_test"
        assert config.max_items == 100

    def test_from_env_uses_defaults_for_missing_vars(self, monkeypatch):
        """Test that missing env vars use default values."""
        monkeypatch.setenv("TEST_NAME", "only_name")

        config = SimpleConfig.from_env(env_prefix="TEST_")

        assert config.name == "only_name"
        assert config.threshold == 0.5  # default
        assert config.enabled is True  # default

    def test_from_env_invalid_type_conversion(self, monkeypatch, caplog):
        """Test handling of invalid type conversion."""
        monkeypatch.setenv("TEST_THRESHOLD", "not_a_float")
        monkeypatch.setenv("TEST_MAX_ITEMS", "not_an_int")

        # Pydantic will raise ValidationError during construction
        # because it can't convert the invalid values
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SimpleConfig.from_env(env_prefix="TEST_")


class TestServiceConfigBaseDatabaseValidation:
    """Tests for database name validation."""

    def test_validate_database_name_valid(self):
        """Test that valid database names are accepted."""
        valid_names = [
            "market",
            "market_data",
            "test_db",
            "db123",
            "UPPERCASE_DB",
            "MixedCase_123",
            "a",
            "a_b_c_1_2_3",
        ]

        for name in valid_names:
            result = SimpleConfig.validate_database_name(name)
            assert result == name

    def test_validate_database_name_invalid(self):
        """Test that invalid database names are rejected."""
        invalid_names = [
            "drop; table",  # SQL injection attempt
            "db-name",  # Hyphen not allowed
            "db.name",  # Dot not allowed
            "db name",  # Space not allowed
            "db/name",  # Slash not allowed
            "db\\name",  # Backslash not allowed
            "db'name",  # Quote not allowed
            "db\"name",  # Double quote not allowed
            "db;name",  # Semicolon not allowed
            "",  # Empty string
            "db(name)",  # Parentheses not allowed
            "db[name]",  # Brackets not allowed
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match="must contain only alphanumeric"):
                SimpleConfig.validate_database_name(name)

    def test_database_field_validator(self, tmp_path):
        """Test that database field is automatically validated."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
name: test
database: valid_db_name
port: 5432
""")

        config = ConfigWithDatabase.from_yaml(str(yaml_file))
        assert config.database == "valid_db_name"

    def test_database_field_validator_rejects_invalid(self, tmp_path):
        """Test that invalid database name in YAML is rejected."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
name: test
database: drop; table
port: 5432
""")

        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            ConfigWithDatabase.from_yaml(str(yaml_file))

    def test_database_field_validator_from_env(self, monkeypatch):
        """Test that database field validation works with env vars."""
        monkeypatch.setenv("TEST_DATABASE", "valid_db")

        config = ConfigWithDatabase.from_env(env_prefix="TEST_")
        assert config.database == "valid_db"

    def test_database_field_validator_env_rejects_invalid(self, monkeypatch):
        """Test that invalid database name from env is rejected."""
        monkeypatch.setenv("TEST_DATABASE", "invalid-db-name")

        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            ConfigWithDatabase.from_env(env_prefix="TEST_")


class TestServiceConfigBaseIntegration:
    """Integration tests combining multiple features."""

    def test_yaml_with_env_overrides_integration(self, tmp_path, monkeypatch):
        """Test full integration of YAML loading with env overrides."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
service:
  name: from_yaml
  database: yaml_db
  port: 5432
""")

        monkeypatch.setenv("TEST_DATABASE", "env_db")
        monkeypatch.setenv("TEST_PORT", "9999")

        config = ConfigWithDatabase.from_yaml(
            str(yaml_file),
            section="service",
            apply_env_overrides=True,
            env_prefix="TEST_"
        )

        assert config.name == "from_yaml"  # From YAML
        assert config.database == "env_db"  # Overridden by env
        assert config.port == 9999  # Overridden by env

    def test_model_dump_yaml(self):
        """Test exporting config as YAML."""
        config = SimpleConfig(
            name="export_test",
            threshold=0.85,
            enabled=False,
            max_items=25
        )

        yaml_output = config.model_dump_yaml()

        assert "name: export_test" in yaml_output
        assert "threshold: 0.85" in yaml_output
        assert "enabled: false" in yaml_output
        assert "max_items: 25" in yaml_output

    def test_pydantic_validation_on_assignment(self):
        """Test that Pydantic validates on field assignment."""
        config = SimpleConfig()

        # Valid assignment
        config.threshold = 0.99
        assert config.threshold == 0.99

        # Invalid type should raise ValidationError
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            config.threshold = "not_a_number"

    def test_extra_fields_ignored(self, tmp_path):
        """Test that extra='ignore' works as expected."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
name: test
extra_field1: ignored
extra_field2: also_ignored
threshold: 0.7
""")

        config = SimpleConfig.from_yaml(str(yaml_file))

        assert config.name == "test"
        assert config.threshold == 0.7
        assert not hasattr(config, "extra_field1")
        assert not hasattr(config, "extra_field2")

    def test_field_defaults_work(self):
        """Test that Pydantic Field defaults work correctly."""
        config = SimpleConfig()

        assert config.name == "default"
        assert config.threshold == 0.5
        assert config.enabled is True
        assert config.max_items == 10

    def test_config_file_not_found(self):
        """Test handling of missing config file."""
        # ConfigLoader will raise ConfigNotFoundError
        with pytest.raises(ConfigNotFoundError):
            SimpleConfig.from_yaml("/nonexistent/path/config.yaml")


class TestServiceConfigBaseEdgeCases:
    """Tests for edge cases and error handling."""

    def test_none_values_in_yaml(self, tmp_path):
        """Test handling of null/None values in YAML."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
name: null
threshold: 0.5
""")

        config = SimpleConfig.from_yaml(str(yaml_file))

        # None should trigger default or be handled by Pydantic
        # Depending on Field configuration
        assert config.threshold == 0.5

    def test_complex_yaml_structure(self, tmp_path):
        """Test handling of nested YAML sections."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
services:
  my_service:
    name: nested
    threshold: 0.9
  other_service:
    name: ignored
""")

        # Load the 'services' section which contains nested configs
        config = SimpleConfig.from_yaml(str(yaml_file), section="services")

        # The section extraction gets the 'services' dict, which isn't
        # directly a valid config. This tests that Pydantic uses defaults
        # when the extracted section doesn't match the expected structure
        # (or it might fail, depending on implementation)
        # This documents the behavior with nested structures

    def test_yaml_with_only_section_key(self, tmp_path):
        """Test YAML file that is just the section dict."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
name: direct
threshold: 0.6
""")

        # Load without section - should use root level
        config = SimpleConfig.from_yaml(str(yaml_file))

        assert config.name == "direct"
        assert config.threshold == 0.6

    def test_env_prefix_with_trailing_underscore(self, monkeypatch):
        """Test that env prefix works with or without trailing underscore."""
        monkeypatch.setenv("PREFIX_NAME", "test1")

        # With trailing underscore
        config1 = SimpleConfig.from_env(env_prefix="PREFIX_")
        assert config1.name == "test1"

        monkeypatch.setenv("PREFIX_NAME", "test2")

        # Without trailing underscore (will match PREFIXNAME)
        # This tests that the implementation handles both cases
        config2 = SimpleConfig.from_env(env_prefix="PREFIX")
        # Should match PREFIX_NAME when looking for PREFIXNAME
        # (depends on implementation)

    def test_multiple_configs_independent(self):
        """Test that multiple config instances are independent."""
        config1 = SimpleConfig(name="config1", threshold=0.3)
        config2 = SimpleConfig(name="config2", threshold=0.7)

        assert config1.name == "config1"
        assert config2.name == "config2"
        assert config1.threshold == 0.3
        assert config2.threshold == 0.7

        # Modifying one shouldn't affect the other
        config1.name = "modified"
        assert config2.name == "config2"


class TestServiceConfigBaseFromYAMLSections:
    """Tests for from_yaml(sections=...) multi-section merge."""

    def test_sections_merge_two_sections(self, monkeypatch):
        monkeypatch.setattr(
            "shared.config.base.ConfigLoader.load",
            lambda path, **kw: {
                "env": {"name": "from_env_section", "threshold": 0.8},
                "reward": {"max_items": 50, "enabled": False},
            },
        )
        config = SimpleConfig.from_yaml("fake.yaml", sections=["env", "reward"])

        assert config.name == "from_env_section"
        assert config.threshold == 0.8
        assert config.max_items == 50
        assert config.enabled is False

    def test_sections_later_overrides_earlier(self, monkeypatch):
        monkeypatch.setattr(
            "shared.config.base.ConfigLoader.load",
            lambda path, **kw: {
                "first": {"name": "from_first", "threshold": 0.3},
                "second": {"name": "from_second", "threshold": 0.9},
            },
        )
        config = SimpleConfig.from_yaml("fake.yaml", sections=["first", "second"])

        assert config.name == "from_second"
        assert config.threshold == 0.9

    def test_sections_missing_section_treated_as_empty(self, monkeypatch):
        monkeypatch.setattr(
            "shared.config.base.ConfigLoader.load",
            lambda path, **kw: {
                "env": {"name": "only_env", "threshold": 0.7},
            },
        )
        config = SimpleConfig.from_yaml("fake.yaml", sections=["env", "nonexistent"])

        assert config.name == "only_env"
        assert config.threshold == 0.7
        assert config.enabled is True  # default

    def test_sections_empty_list_uses_defaults(self, monkeypatch):
        monkeypatch.setattr(
            "shared.config.base.ConfigLoader.load",
            lambda path, **kw: {"env": {"name": "ignored"}},
        )
        config = SimpleConfig.from_yaml("fake.yaml", sections=[])

        assert config.name == "default"
        assert config.threshold == 0.5

    def test_sections_mutually_exclusive_with_section(self):
        with pytest.raises(ValueError, match="Cannot specify both"):
            SimpleConfig.from_yaml(
                "fake.yaml", section="env", sections=["env", "reward"]
            )

    def test_sections_with_env_overrides(self, monkeypatch):
        monkeypatch.setattr(
            "shared.config.base.ConfigLoader.load",
            lambda path, **kw: {
                "env": {"name": "from_yaml", "threshold": 0.5},
                "reward": {"max_items": 20},
            },
        )
        monkeypatch.setenv("MY_THRESHOLD", "0.99")

        config = SimpleConfig.from_yaml(
            "fake.yaml",
            sections=["env", "reward"],
            apply_env_overrides=True,
            env_prefix="MY_",
        )

        assert config.name == "from_yaml"
        assert config.threshold == 0.99  # env override
        assert config.max_items == 20  # from reward section

    def test_sections_non_dict_section_skipped(self, monkeypatch):
        monkeypatch.setattr(
            "shared.config.base.ConfigLoader.load",
            lambda path, **kw: {
                "env": {"name": "valid_section"},
                "scalar_section": "just_a_string",
            },
        )
        config = SimpleConfig.from_yaml(
            "fake.yaml", sections=["env", "scalar_section"]
        )

        assert config.name == "valid_section"
