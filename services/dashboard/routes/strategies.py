"""Strategy configuration endpoints."""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from shared.config.loader import ConfigLoader, ConfigError, ConfigNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

SUPPORTED_ASSETS = {"stock", "futures"}


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
