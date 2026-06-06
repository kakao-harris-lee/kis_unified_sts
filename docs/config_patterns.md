# Configuration Patterns

## Overview

The KIS Unified Trading System uses a standardized configuration pattern based on `ServiceConfigBase` to eliminate boilerplate and ensure consistency across all service configurations.

**Key Benefits:**
- **DRY Principle**: Zero boilerplate - inherit `from_yaml()` and `from_env()` methods
- **Type Safety**: Pydantic BaseModel with automatic validation
- **Consistent Loading**: Single pattern for all services
- **Environment Overrides**: Seamless YAML + environment variable composition
- **SQL Injection Prevention**: Built-in database name validation

---

## ServiceConfigBase Pattern

### Basic Usage

All service configuration classes should extend `ServiceConfigBase`:

```python
from pydantic import Field
from shared.config.base import ServiceConfigBase

class MyServiceConfig(ServiceConfigBase):
    """Configuration for My Service."""

    # Define class-level defaults (optional)
    _default_config_file: ClassVar[str] = "my_service.yaml"
    _default_section: ClassVar[str | None] = None  # Or specify section name
    _env_prefix: ClassVar[str | None] = "MY_SERVICE_"

    # Define fields with Pydantic Field()
    threshold: float = Field(
        default=0.5,
        description="Detection threshold (0.0-1.0)"
    )
    enabled: bool = Field(
        default=True,
        description="Enable service"
    )
    database: str = Field(
        default="market",
        description="Database name (auto-validated for SQL injection)"
    )
    interval_seconds: int = Field(
        default=60,
        ge=1,
        description="Update interval in seconds"
    )
```

### Loading Configuration

#### From YAML File

```python
# Load from default file (uses _default_config_file)
config = MyServiceConfig.from_yaml()

# Load from specific file
config = MyServiceConfig.from_yaml("my_service.yaml")

# Load from specific section in YAML
config = MyServiceConfig.from_yaml("services.yaml", section="my_service")

# Load with environment variable overrides
config = MyServiceConfig.from_yaml(
    "my_service.yaml",
    apply_env_overrides=True,
    env_prefix="MY_SERVICE_"
)
```

#### From Environment Variables

```python
# Load from env vars (uses _env_prefix)
config = MyServiceConfig.from_env()

# Load with custom prefix
config = MyServiceConfig.from_env(env_prefix="MY_SERVICE_")

# Load with overrides (take precedence over env vars)
config = MyServiceConfig.from_env(
    env_prefix="MY_SERVICE_",
    enabled=False  # Override
)
```

### Environment Variable Mapping

Environment variables are automatically mapped to fields:

| Field Name | Env Prefix | Environment Variable | Type Conversion |
|------------|-----------|---------------------|-----------------|
| `threshold` | `MY_SERVICE_` | `MY_SERVICE_THRESHOLD` | `float` |
| `enabled` | `MY_SERVICE_` | `MY_SERVICE_ENABLED` | `bool` (true/false) |
| `database` | `MY_SERVICE_` | `MY_SERVICE_DATABASE` | `str` |
| `interval_seconds` | `MY_SERVICE_` | `MY_SERVICE_INTERVAL_SECONDS` | `int` |

**Type Conversion Rules:**
- **Boolean**: `"true"`, `"1"`, `"yes"`, `"on"` → `True` (case-insensitive)
- **Integer**: Standard int parsing
- **Float**: Standard float parsing
- **String**: No conversion
- **Empty String**: Converted to `None`

---

## Advanced Patterns

### Custom from_yaml() Override

For complex YAML structures (e.g., nested sections), override `from_yaml()`:

```python
class FusionRankerConfig(ServiceConfigBase):
    """Configuration with nested YAML structure."""

    _default_config_file: ClassVar[str] = "fusion_ranker.yaml"

    # Flat fields
    realtime_key: str = Field(...)
    interval_seconds: int = Field(...)
    realtime_weight: float = Field(...)

    @classmethod
    def from_yaml(
        cls,
        path: str | None = None,
        section: str | None = None,
        *,
        apply_env_overrides: bool = False,
        env_prefix: str | None = None,
    ) -> Self:
        """Load from nested YAML structure."""
        # Load raw YAML
        path = path or cls._default_config_file
        raw_data = ConfigLoader.load(path)

        # Flatten nested sections
        config_data = {}
        config_data.update(raw_data.get("redis_keys", {}))
        config_data.update(raw_data.get("ranking", {}))
        config_data.update(raw_data.get("weights", {}))

        # Apply env overrides if requested
        if apply_env_overrides:
            prefix = env_prefix or cls._env_prefix
            if prefix:
                env_overrides = cls._extract_env_vars(prefix)
                config_data.update(env_overrides)

        return cls(**config_data)
```

**YAML Structure:**
```yaml
redis_keys:
  realtime_key: "screener:realtime"

ranking:
  interval_seconds: 300

weights:
  realtime_weight: 0.7
```

### Custom from_env() Override

For non-standard environment variable naming, override `from_env()`:

```python
class TelegramConfig(ServiceConfigBase):
    """Configuration with custom env var mapping."""

    _env_prefix: ClassVar[str] = "TELEGRAM_"

    token: str = Field(default="", repr=False)
    chat_id: str = Field(default="", repr=False)

    @classmethod
    def from_env(cls, env_prefix: str | None = None, **overrides: Any) -> Self:
        """Load with custom env var mapping."""
        # Map non-standard env var names
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")  # Not TELEGRAM_TOKEN
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        # Merge with standard env vars
        prefix = env_prefix or cls._env_prefix
        env_data = cls._extract_env_vars(prefix) if prefix else {}

        # Custom mappings take precedence
        if token:
            env_data["token"] = token
        if chat_id:
            env_data["chat_id"] = chat_id

        # Apply overrides
        env_data.update(overrides)

        return cls(**env_data)
```

### Multi-Prefix Environment Variables

For services with multiple env var prefixes:

```python
class TickStreamPublisherConfig(ServiceConfigBase):
    """Configuration with multiple env prefixes."""

    _env_prefix: ClassVar[str] = "MONITOR_TICK_STREAM_"

    enabled: bool = Field(default=True)
    stock_stream: str = Field(default="ticks:stock")
    futures_stream: str = Field(default="ticks:futures")

    @classmethod
    def from_env(cls, env_prefix: str | None = None, **overrides: Any) -> Self:
        """Load from multiple prefixes."""
        # Load standard prefix
        env_data = cls._extract_env_vars(cls._env_prefix)

        # Load stock-specific vars (different prefix)
        stock_stream = os.getenv("MONITOR_STOCK_TICK_STREAM", env_data.get("stock_stream"))
        if stock_stream:
            env_data["stock_stream"] = stock_stream

        # Load futures-specific vars
        futures_stream = os.getenv("MONITOR_FUTURES_TICK_STREAM", env_data.get("futures_stream"))
        if futures_stream:
            env_data["futures_stream"] = futures_stream

        env_data.update(overrides)
        return cls(**env_data)
```

### Provider-Aware Configuration

For configurations that vary by provider (e.g., OpenAI vs Claude):

```python
class LLMConfig(ServiceConfigBase):
    """Configuration with provider-specific logic."""

    _default_config_file: ClassVar[str] = "llm.yaml"
    _env_prefix: ClassVar[str] = "LLM_"

    llm_provider: str = Field(default="openai")
    api_key: str = Field(default="", repr=False)
    model: str = Field(default="gpt-4")

    @classmethod
    def from_env(cls, env_prefix: str | None = None, **overrides: Any) -> Self:
        """Load with provider-aware API key selection."""
        env_data = cls._extract_env_vars(cls._env_prefix)

        # Detect provider
        provider = overrides.get("llm_provider", env_data.get("llm_provider", "openai"))

        # Select correct API key based on provider
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "")
        elif provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
        else:
            api_key = ""

        if api_key:
            env_data["api_key"] = api_key

        env_data.update(overrides)
        return cls(**env_data)
```

---

## Field Patterns

### Sensitive Fields (Hide in repr)

Use `repr=False` for sensitive data:

```python
api_key: str = Field(
    default="",
    repr=False,  # Hide in __repr__ output
    description="API key for authentication"
)
token: str = Field(default="", repr=False)
password: str = Field(default="", repr=False)
```

### Validated Fields

Pydantic provides built-in validators:

```python
# Range validation
threshold: float = Field(
    default=0.5,
    ge=0.0,  # Greater than or equal to 0
    le=1.0,  # Less than or equal to 1
    description="Threshold between 0 and 1"
)

# Positive integers
pool_size: int = Field(
    default=5,
    gt=0,  # Greater than 0
    description="Connection pool size"
)

# String patterns
code: str = Field(
    default="000000",
    pattern=r"^\d{6}$",  # 6 digits
    description="Stock code"
)
```

### Database Fields (Auto-Validated)

Fields named `database` are automatically validated:

```python
database: str = Field(
    default="market",
    description="Database name (auto-validated)"
)
# Validation: alphanumeric + underscore only (prevents SQL injection)
```

### Frozen/Immutable Configs

For immutable configurations:

```python
class ImmutableConfig(ServiceConfigBase):
    """Immutable configuration."""

    model_config = ConfigDict(
        frozen=True,  # Make all fields immutable
        extra="ignore",
        validate_assignment=True,
    )

    setting: str = Field(default="value")
```

---

## Migration Guide

### From ConfigMixin (dataclass)

**Before:**
```python
from dataclasses import dataclass, field
from shared.config.mixins import ConfigMixin

@dataclass
class OldConfig(ConfigMixin):
    threshold: float = 0.5
    enabled: bool = True

    @classmethod
    def from_yaml(cls, path: str = "config.yaml"):
        data = ConfigLoader.load(path)
        return cls.from_dict(data)
```

**After:**
```python
from pydantic import Field
from shared.config.base import ServiceConfigBase

class NewConfig(ServiceConfigBase):
    _default_config_file: ClassVar[str] = "config.yaml"

    threshold: float = Field(default=0.5, description="Threshold value")
    enabled: bool = Field(default=True, description="Enable service")

    # from_yaml() inherited - no implementation needed!
```

### From Pydantic BaseModel

**Before:**
```python
from pydantic import BaseModel, Field

class OldConfig(BaseModel):
    threshold: float = Field(default=0.5)
    enabled: bool = Field(default=True)

    @classmethod
    def from_env(cls):
        threshold = float(os.getenv("THRESHOLD", "0.5"))
        enabled = os.getenv("ENABLED", "true").lower() == "true"
        return cls(threshold=threshold, enabled=enabled)
```

**After:**
```python
from shared.config.base import ServiceConfigBase

class NewConfig(ServiceConfigBase):
    _env_prefix: ClassVar[str] = "MY_SERVICE_"

    threshold: float = Field(default=0.5, description="Threshold value")
    enabled: bool = Field(default=True, description="Enable service")

    # from_env() inherited - automatic type conversion!
```

### From Inline os.environ.get()

**Before:**
```python
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class OldConfig:
    threshold: float = float(os.environ.get("THRESHOLD", "0.5"))
    enabled: bool = os.environ.get("ENABLED", "true").lower() == "true"
    interval: int = int(os.environ.get("INTERVAL", "60"))
```

**After:**
```python
from shared.config.base import ServiceConfigBase

class NewConfig(ServiceConfigBase):
    _env_prefix: ClassVar[str] = ""  # No prefix, direct env var names

    threshold: float = Field(default=0.5, description="Threshold value")
    enabled: bool = Field(default=True, description="Enable service")
    interval: int = Field(default=60, description="Interval in seconds")

    # Load with: NewConfig.from_env()
```

---

## Best Practices

### 1. Always Use Field() with Descriptions

```python
# Good
threshold: float = Field(
    default=0.5,
    ge=0.0,
    le=1.0,
    description="Detection threshold (0.0-1.0)"
)

# Bad
threshold: float = 0.5
```

### 2. Set Class-Level Defaults

```python
class MyConfig(ServiceConfigBase):
    _default_config_file: ClassVar[str] = "my_service.yaml"
    _env_prefix: ClassVar[str] = "MY_SERVICE_"
    # ...
```

### 3. Use Descriptive Environment Prefixes

```python
# Good
_env_prefix = "SCREENER_"        # MY_SERVICE_ENABLED
_env_prefix = "FUSION_RANKER_"   # FUSION_RANKER_TOP_N

# Bad
_env_prefix = "SVC_"             # Too generic
_env_prefix = "X_"               # Not descriptive
```

### 4. Document Custom Overrides

When overriding `from_yaml()` or `from_env()`, document the reason:

```python
@classmethod
def from_yaml(cls, path: str | None = None, ...) -> Self:
    """Load from nested YAML structure.

    Custom override needed because YAML has nested sections:
    - redis_keys: {...}
    - ranking: {...}
    - weights: {...}

    These are flattened into a single config object.
    """
    # ...
```

### 5. Maintain Backward Compatibility

When migrating existing configs:
- Keep all field names the same
- Preserve default values
- Support existing env var names (override `from_env()` if needed)
- Test with existing YAML files

### 6. Use Type Hints Consistently

```python
# Good
threshold: float = Field(...)
enabled: bool = Field(...)
items: list[str] = Field(default_factory=list)

# Bad
threshold = Field(...)  # Missing type hint
```

### 7. Validate at the Right Level

```python
# Field-level validation (simple constraints)
age: int = Field(ge=0, le=120)

# Model-level validation (complex cross-field logic)
@model_validator(mode="after")
def validate_config(self) -> Self:
    if self.min_value > self.max_value:
        raise ValueError("min_value must be <= max_value")
    return self
```

---

## Testing Patterns

### Unit Tests for Config Loading

```python
import pytest
from my_service import MyServiceConfig

def test_from_yaml_basic(tmp_path):
    """Test loading from YAML file."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("""
threshold: 0.7
enabled: false
""")

    config = MyServiceConfig.from_yaml(str(config_file))
    assert config.threshold == 0.7
    assert config.enabled is False

def test_from_env_with_prefix(monkeypatch):
    """Test loading from environment variables."""
    monkeypatch.setenv("MY_SERVICE_THRESHOLD", "0.8")
    monkeypatch.setenv("MY_SERVICE_ENABLED", "true")

    config = MyServiceConfig.from_env(env_prefix="MY_SERVICE_")
    assert config.threshold == 0.8
    assert config.enabled is True

def test_yaml_with_env_overrides(tmp_path, monkeypatch):
    """Test YAML loading with env var overrides."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("threshold: 0.5")

    monkeypatch.setenv("MY_SERVICE_THRESHOLD", "0.9")

    config = MyServiceConfig.from_yaml(
        str(config_file),
        apply_env_overrides=True,
        env_prefix="MY_SERVICE_"
    )
    assert config.threshold == 0.9  # Env var overrides YAML

def test_database_validation():
    """Test database name validation."""
    # Valid names
    config = MyServiceConfig(database="market")
    config = MyServiceConfig(database="market_data")
    config = MyServiceConfig(database="db123")

    # Invalid names (SQL injection prevention)
    with pytest.raises(ValueError, match="alphanumeric"):
        MyServiceConfig(database="market; DROP TABLE")
    with pytest.raises(ValueError, match="alphanumeric"):
        MyServiceConfig(database="market-data")
```

---

## Troubleshooting

### Config File Not Found

**Error:**
```
ConfigNotFoundError: Config file not found: my_service.yaml
```

**Solutions:**
1. Check `KIS_CONFIG_DIR` environment variable
2. Ensure file exists in `config/` directory
3. Use absolute path: `MyConfig.from_yaml("/absolute/path/to/config.yaml")`

### Environment Variable Not Loading

**Problem:** Env var not being picked up

**Checklist:**
1. Verify env var name matches prefix + field name (uppercase)
2. Check `_env_prefix` is set correctly
3. Ensure field name in model matches (case-insensitive matching)
4. Try loading with explicit prefix: `from_env(env_prefix="MY_")`

### Type Conversion Errors

**Error:**
```
Failed to parse MY_SERVICE_THRESHOLD=abc as <class 'float'>
```

**Solution:**
- Check env var value is correct type
- ServiceConfigBase falls back to raw string if conversion fails
- Override `from_env()` for custom type parsing

### Database Validation Failing

**Error:**
```
ValueError: Database name must contain only alphanumeric characters and underscores
```

**Solution:**
- Use only `[a-zA-Z0-9_]` characters in database names
- This prevents SQL injection in DDL statements
- If you need special characters, override the validator (not recommended)

---

## Reference

### ServiceConfigBase API

#### Class Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `_default_config_file` | `str \| None` | Default YAML filename |
| `_default_section` | `str \| None` | Default section in YAML |
| `_env_prefix` | `str \| None` | Default env var prefix |

#### Class Methods

| Method | Description |
|--------|-------------|
| `from_yaml(path, section, apply_env_overrides, env_prefix)` | Load from YAML file |
| `from_env(env_prefix, **overrides)` | Load from environment variables |
| `validate_database_name(name)` | Validate database name (SQL injection prevention) |

#### Instance Methods

| Method | Description |
|--------|-------------|
| `model_dump()` | Export as dict |
| `model_dump_json()` | Export as JSON string |
| `model_dump_yaml()` | Export as YAML string |

### Migrated Configs

All 7 service configs now use ServiceConfigBase:

| Config Class | Location | Fields | Custom Overrides |
|--------------|----------|--------|------------------|
| `DailyScannerConfig` | `services/daily_scanner.py` | 15 | None (uses inherited methods) |
| `FusionRankerConfig` | `services/fusion_ranker.py` | 16 | `from_yaml()` (nested YAML) |
| `TelegramConfig` | `services/monitoring/notifier.py` | 4 | `from_env()` (custom env vars) |
| `TickStreamPublisherConfig` | `services/monitoring/tick_stream_publisher.py` | 12 | `from_env()` (multi-prefix) |
| `LLMConfig` | `shared/llm/config.py` | 100+ | `from_yaml()` + `from_env()` (provider-aware) |
| `ScreenerConfig` | `services/screener.py` | 23 | `from_env()` (non-prefixed vars) |
| `StorageConfig` | `shared/storage/config.py` | runtime + market data | `load_or_default()` + env overrides |

**Boilerplate Eliminated:** ~385 lines of duplicated code removed

---

## See Also

- `shared/config/base.py` - ServiceConfigBase implementation
- `shared/config/loader.py` - ConfigLoader (YAML loading)
- `shared/config/schema.py` - Pydantic schemas for validation
- `tests/unit/config/test_service_config_base.py` - Comprehensive test suite
