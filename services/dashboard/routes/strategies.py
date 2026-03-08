"""Strategy configuration endpoints."""
from __future__ import annotations

import dataclasses
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from shared.config.loader import ConfigLoader, ConfigError, ConfigNotFoundError
from shared.strategy.registry import (
    EntryRegistry,
    ExitRegistry,
    SizerRegistry,
    ComponentNotFoundError,
    StrategyFactory,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

SUPPORTED_ASSETS = {"stock", "futures"}
SUPPORTED_COMPONENT_TYPES = {"entry", "exit", "position"}


class StrategyInfo(BaseModel):
    """Strategy configuration info."""

    name: str
    asset_class: str
    enabled: bool
    entry_type: str
    exit_type: str
    position_type: str
    description: Optional[str] = None


class StrategyListResponse(BaseModel):
    """Strategy list response."""

    strategies: List[StrategyInfo]
    total: int
    asset_class: Optional[str] = None


class StrategySaveRequest(BaseModel):
    """Strategy save request."""

    asset_class: str = Field(..., description="Asset class (stock, futures)")
    name: str = Field(..., description="Strategy name (alphanumeric, underscores, hyphens)")
    config: Dict[str, Any] = Field(..., description="Full strategy configuration as dict")

    @field_validator("asset_class")
    @classmethod
    def validate_asset_class(cls, v: str) -> str:
        """Validate asset class is supported."""
        if v not in SUPPORTED_ASSETS:
            raise ValueError(
                f"Invalid asset_class '{v}'. Must be one of: {', '.join(SUPPORTED_ASSETS)}"
            )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate strategy name is safe (prevent path traversal)."""
        # Allow alphanumeric, underscore, hyphen only
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Strategy name must contain only alphanumeric characters, underscores, and hyphens"
            )
        # Prevent path traversal
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Strategy name cannot contain path separators or '..'")
        # Prevent empty or too long
        if len(v) == 0 or len(v) > 100:
            raise ValueError("Strategy name must be 1-100 characters")
        return v


class StrategySaveResponse(BaseModel):
    """Strategy save response."""

    success: bool
    message: str
    file_path: str


@router.get("", response_model=StrategyListResponse)
async def list_strategies(
    asset_class: Optional[str] = Query(
        None, description="Filter by asset class (stock, futures)"
    ),
    enabled_only: bool = Query(True, description="Return only enabled strategies"),
):
    """List all available strategies.

    Args:
        asset_class: Optional filter by asset class (stock, futures)
        enabled_only: If True, return only enabled strategies (default: True)

    Returns:
        StrategyListResponse with list of strategies

    Raises:
        HTTPException: 400 if invalid asset_class, 500 if config loading fails
    """
    # Validate asset_class parameter
    if asset_class is not None:
        if asset_class not in SUPPORTED_ASSETS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid asset_class '{asset_class}'. Must be one of: {', '.join(SUPPORTED_ASSETS)}",
            )

    try:
        # Load all strategies using ConfigLoader
        configs = ConfigLoader.load_all_strategies(
            asset_class=asset_class,
            enabled_only=enabled_only,
        )

        # Transform configs to response format
        strategies = []
        for config in configs:
            strategy_config = config.get("strategy", {})
            entry_config = strategy_config.get("entry", {})
            exit_config = strategy_config.get("exit", {})
            position_config = strategy_config.get("position", {})

            strategy_info = StrategyInfo(
                name=strategy_config.get("name", "unknown"),
                asset_class=strategy_config.get("asset_class", asset_class or "unknown"),
                enabled=strategy_config.get("enabled", False),
                entry_type=entry_config.get("type", "unknown"),
                exit_type=exit_config.get("type", "unknown"),
                position_type=position_config.get("type", "unknown"),
                description=strategy_config.get("description"),
            )
            strategies.append(strategy_info)

        logger.info(
            f"Listed {len(strategies)} strategies (asset_class={asset_class}, enabled_only={enabled_only})"
        )

        return StrategyListResponse(
            strategies=strategies,
            total=len(strategies),
            asset_class=asset_class,
        )

    except ConfigNotFoundError as e:
        logger.error(f"Config not found: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Configuration not found: {str(e)}",
        )
    except ConfigError as e:
        logger.error(f"Config error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing strategies: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/{asset}/{name}")
async def get_strategy_detail(
    asset: str,
    name: str,
):
    """Get full strategy configuration.

    Args:
        asset: Asset class (stock, futures)
        name: Strategy name

    Returns:
        Full strategy YAML config as JSON

    Raises:
        HTTPException: 400 if invalid asset_class, 404 if strategy not found, 500 if config loading fails
    """
    # Validate asset parameter
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid asset class '{asset}'. Must be one of: {', '.join(SUPPORTED_ASSETS)}",
        )

    try:
        # Load strategy config using ConfigLoader
        config = ConfigLoader.load_strategy(asset_class=asset, strategy_name=name)

        logger.info(f"Loaded strategy config: {asset}/{name}")

        return config

    except ConfigNotFoundError as e:
        logger.error(f"Strategy not found: {asset}/{name} - {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{name}' not found for asset class '{asset}'",
        )
    except ConfigError as e:
        logger.error(f"Config error loading {asset}/{name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error loading strategy {asset}/{name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.post("", response_model=StrategySaveResponse, status_code=201)
async def save_strategy(
    request: StrategySaveRequest,
):
    """Save strategy configuration to YAML file.

    Creates or updates a strategy YAML file in config/strategies/{asset_class}/{name}.yaml.
    Validates the configuration structure before saving.

    Args:
        request: Strategy save request with asset_class, name, and config

    Returns:
        StrategySaveResponse with success status and file path

    Raises:
        HTTPException: 400 if validation fails, 500 if file write fails
    """
    asset_class = request.asset_class
    name = request.name
    config = request.config

    try:
        # Get config directory from ConfigLoader
        config_dir = ConfigLoader.get_config_dir()
        strategies_dir = config_dir / "strategies" / asset_class

        # Ensure directory exists
        strategies_dir.mkdir(parents=True, exist_ok=True)

        # Build file path
        file_path = strategies_dir / f"{name}.yaml"

        # Validate config structure
        # Required top-level key: "strategy"
        if "strategy" not in config:
            raise HTTPException(
                status_code=400,
                detail="Configuration must contain top-level 'strategy' key",
            )

        strategy_config = config["strategy"]

        # Validate required fields
        required_fields = ["name", "asset_class", "entry", "exit", "position"]
        missing_fields = [f for f in required_fields if f not in strategy_config]
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy config missing required fields: {missing_fields}",
            )

        # Validate entry/exit/position have 'type' field
        for component_type in ["entry", "exit", "position"]:
            component_config = strategy_config.get(component_type, {})
            if "type" not in component_config:
                raise HTTPException(
                    status_code=400,
                    detail=f"'{component_type}' configuration must contain 'type' field",
                )

            # Validate component type is registered
            type_name = component_config["type"]
            if component_type == "entry":
                if not EntryRegistry.is_registered(type_name):
                    available = EntryRegistry.list_all()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unknown entry type '{type_name}'. Available: {available}",
                    )
            elif component_type == "exit":
                if not ExitRegistry.is_registered(type_name):
                    available = ExitRegistry.list_all()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unknown exit type '{type_name}'. Available: {available}",
                    )
            elif component_type == "position":
                if not SizerRegistry.is_registered(type_name):
                    available = SizerRegistry.list_all()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unknown position type '{type_name}'. Available: {available}",
                    )

        # Optional: Try to create strategy instance to validate params
        # This will catch any config errors early
        try:
            params = strategy_config.get("entry", {}).get("params", {})
            entry_type = strategy_config["entry"]["type"]
            _ = EntryRegistry.create(entry_type, params)
        except Exception as e:
            logger.warning(f"Entry validation failed (non-fatal): {e}")
            # Don't fail the save, just log warning

        try:
            params = strategy_config.get("exit", {}).get("params", {})
            exit_type = strategy_config["exit"]["type"]
            _ = ExitRegistry.create(exit_type, params)
        except Exception as e:
            logger.warning(f"Exit validation failed (non-fatal): {e}")

        try:
            params = strategy_config.get("position", {}).get("params", {})
            position_type = strategy_config["position"]["type"]
            _ = SizerRegistry.create(position_type, params)
        except Exception as e:
            logger.warning(f"Position validation failed (non-fatal): {e}")

        # Write YAML file
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                config,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

        logger.info(f"Saved strategy configuration: {file_path}")

        # Clear ConfigLoader cache so new config is loaded on next request
        ConfigLoader.clear_cache()

        return StrategySaveResponse(
            success=True,
            message=f"Strategy '{name}' saved successfully",
            file_path=str(file_path.relative_to(config_dir.parent)),
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.exception(f"Unexpected error saving strategy {asset_class}/{name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save strategy: {str(e)}",
        )


def _generate_schema_from_dataclass(dataclass_type: type) -> Dict[str, Any]:
    """Generate JSON schema from a dataclass.

    Args:
        dataclass_type: Dataclass type to generate schema from

    Returns:
        JSON schema dict compatible with JSON Schema Draft 7
    """
    if not dataclasses.is_dataclass(dataclass_type):
        raise ValueError(f"{dataclass_type} is not a dataclass")

    properties = {}
    required = []

    for field in dataclasses.fields(dataclass_type):
        field_schema = {"title": field.name.replace("_", " ").title()}

        # Extract type information
        field_type = field.type
        type_str = str(field_type)

        # Map Python types to JSON schema types
        if "int" in type_str:
            field_schema["type"] = "integer"
        elif "float" in type_str:
            field_schema["type"] = "number"
        elif "bool" in type_str:
            field_schema["type"] = "boolean"
        elif "str" in type_str:
            field_schema["type"] = "string"
        elif "list" in type_str or "List" in type_str:
            field_schema["type"] = "array"
        elif "dict" in type_str or "Dict" in type_str:
            field_schema["type"] = "object"
        else:
            field_schema["type"] = "string"  # Default fallback

        # Add default value
        if field.default is not dataclasses.MISSING:
            field_schema["default"] = field.default
        elif field.default_factory is not dataclasses.MISSING:
            # For default_factory, we call it to get the default value
            try:
                field_schema["default"] = field.default_factory()
            except Exception:
                pass  # Skip if factory fails
        else:
            # No default means required field
            required.append(field.name)

        properties[field.name] = field_schema

    schema = {
        "type": "object",
        "properties": properties,
        "title": dataclass_type.__name__,
    }

    if required:
        schema["required"] = required

    # Add description from docstring if available
    if dataclass_type.__doc__:
        schema["description"] = dataclass_type.__doc__.strip()

    return schema


@router.get("/schema")
async def get_component_schema(
    entry_type: Optional[str] = Query(
        None, description="Entry strategy type (e.g., mean_reversion)"
    ),
    exit_type: Optional[str] = Query(
        None, description="Exit strategy type (e.g., three_stage)"
    ),
    position_type: Optional[str] = Query(
        None, description="Position sizer type (e.g., fixed, risk_based)"
    ),
):
    """Get JSON schema for a strategy component configuration.

    This endpoint generates a JSON schema for the configuration parameters
    of a specific strategy component (entry, exit, or position sizer).
    The schema can be used for dynamic form generation in the frontend.

    Exactly one of entry_type, exit_type, or position_type must be specified.

    Args:
        entry_type: Entry strategy type name (e.g., mean_reversion)
        exit_type: Exit strategy type name (e.g., three_stage)
        position_type: Position sizer type name (e.g., fixed, risk_based)

    Returns:
        JSON schema dict describing the component's configuration parameters

    Raises:
        HTTPException: 400 if invalid parameters, 404 if component not found, 500 for errors

    Examples:
        GET /api/strategies/schema?entry_type=mean_reversion
        GET /api/strategies/schema?exit_type=three_stage
        GET /api/strategies/schema?position_type=fixed
    """
    # Exactly one parameter must be specified
    params_provided = sum([entry_type is not None, exit_type is not None, position_type is not None])
    if params_provided == 0:
        raise HTTPException(
            status_code=400,
            detail="Must specify exactly one of: entry_type, exit_type, or position_type",
        )
    if params_provided > 1:
        raise HTTPException(
            status_code=400,
            detail="Must specify only one of: entry_type, exit_type, or position_type",
        )

    # Determine component type and name
    if entry_type is not None:
        component_type = "entry"
        type_name = entry_type
        registry = EntryRegistry
    elif exit_type is not None:
        component_type = "exit"
        type_name = exit_type
        registry = ExitRegistry
    else:  # position_type is not None
        component_type = "position"
        type_name = position_type
        registry = SizerRegistry

    try:
        # Get component class from registry
        component_class = registry.get(type_name)

        # Extract CONFIG_CLASS
        if not hasattr(component_class, "CONFIG_CLASS"):
            raise HTTPException(
                status_code=500,
                detail=f"Component '{type_name}' does not have CONFIG_CLASS attribute",
            )

        config_class = component_class.CONFIG_CLASS

        # Generate schema from dataclass
        schema = _generate_schema_from_dataclass(config_class)

        logger.info(f"Generated schema for {component_type}/{type_name}")

        return schema

    except ComponentNotFoundError as e:
        logger.error(f"Component not found: {component_type}/{type_name} - {e}")
        # Get available components from registry
        available = registry.list_all()

        raise HTTPException(
            status_code=404,
            detail=f"Component '{type_name}' not found for type '{component_type}'. Available: {available}",
        )
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.exception(f"Unexpected error generating schema for {component_type}/{type_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )
