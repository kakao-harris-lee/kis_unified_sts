"""Strategy configuration endpoints."""
from __future__ import annotations

import dataclasses
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from shared.config.loader import ConfigLoader, ConfigError, ConfigNotFoundError
from shared.strategy.registry import (
    EntryRegistry,
    ExitRegistry,
    SizerRegistry,
    ComponentNotFoundError,
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
