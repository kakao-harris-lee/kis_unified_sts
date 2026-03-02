"""Helpers for backtest metadata parity with live orchestrator contexts."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_META_KEYS = (
    "daily_watchlist",
    "dip_candidates",
    "accumulation_candidates",
    "symbol_metadata",
)


def _load_json(path_value: str) -> Any:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise FileNotFoundError(f"Backtest metadata file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(k): v for k, v in value.items()}


def _apply_if_dict(target: dict[str, Any], key: str, value: Any) -> None:
    if isinstance(value, dict):
        target[key] = value


def load_backtest_metadata(strategy_config: dict[str, Any]) -> dict[str, Any]:
    """Load optional backtest metadata from strategy.backtest.metadata.

    Supported fields:
      - file: JSON path containing one or more metadata keys
      - daily_watchlist / dip_candidates / accumulation_candidates / symbol_metadata
      - *_file variants for each key (e.g. dip_candidates_file)
    """
    strategy = strategy_config.get("strategy", {})
    bt = strategy.get("backtest", {})
    raw = bt.get("metadata", {})

    if raw is None:
        raw = {}
    elif isinstance(raw, str):
        raw = {"file": raw}
    elif not isinstance(raw, dict):
        logger.warning("Ignoring invalid backtest.metadata type: %s", type(raw).__name__)
        raw = {}

    result: dict[str, Any] = {
        "daily_watchlist": {},
        "dip_candidates": {},
        "accumulation_candidates": {},
        "symbol_metadata": {},
    }

    # 1) Optional bulk JSON file.
    if isinstance(raw.get("file"), str) and raw["file"].strip():
        try:
            loaded = _load_json(raw["file"])
            if isinstance(loaded, dict):
                for key in _META_KEYS:
                    _apply_if_dict(result, key, loaded.get(key))
        except Exception as exc:
            logger.warning("Failed to load backtest metadata file '%s': %s", raw["file"], exc)

    # 2) Per-key JSON files override bulk file values.
    for key in _META_KEYS:
        file_key = f"{key}_file"
        file_value = raw.get(file_key)
        if isinstance(file_value, str) and file_value.strip():
            try:
                loaded = _load_json(file_value)
                if isinstance(loaded, dict):
                    result[key] = loaded
                else:
                    logger.warning(
                        "Ignoring non-dict backtest metadata in %s (%s)",
                        file_key,
                        type(loaded).__name__,
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to load backtest metadata '%s' file '%s': %s",
                    key,
                    file_value,
                    exc,
                )

    # 3) Inline dict values override file values.
    for key in _META_KEYS:
        _apply_if_dict(result, key, raw.get(key))

    # Normalize symbol-keyed maps for consistent lookup.
    result["dip_candidates"] = _normalize_dict(result["dip_candidates"])
    result["accumulation_candidates"] = _normalize_dict(result["accumulation_candidates"])
    result["symbol_metadata"] = _normalize_dict(result["symbol_metadata"])

    return result


def resolve_symbol_metadata(backtest_metadata: dict[str, Any], code: str) -> dict[str, Any]:
    """Resolve symbol metadata for one code from metadata map."""
    symbol_meta = backtest_metadata.get("symbol_metadata", {})
    if not isinstance(symbol_meta, dict):
        return {}

    candidates = [code]
    if code.isdigit():
        candidates.append(code.lstrip("0"))
        candidates.append(code.zfill(6))

    for key in candidates:
        meta = symbol_meta.get(key)
        if isinstance(meta, dict):
            return dict(meta)

    return {}
