"""KIS API TR ID loader.

Loads the single source of truth at ``config/kis/tr_ids.yaml`` (operator-facing,
audited per ``docs/runbooks/futures-legal-review.md`` §3) and exposes a flat
``{key: tr_id}`` dict that ``ExecutionConfig`` Field defaults consume via
``default_factory``.

Behaviour:
  - File present + parseable + key present → use YAML value.
  - File missing OR key missing → fall back to ``_DEFAULTS`` baked here.
  - Cached per-process via ``lru_cache(1)`` — call ``get_tr_ids.cache_clear()``
    in tests that need to switch ``KIS_CONFIG_DIR``.

The defaults below intentionally duplicate the values in ``config/kis/tr_ids.yaml``
so that the system is functional even without the YAML (e.g. fresh checkout
without ``KIS_CONFIG_DIR`` configured). The YAML remains the canonical record
the operator audits.
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


_DEFAULTS: dict[str, str] = {
    # Stock (KRX)
    "stock_krx_buy_mock": "VTTC0802U",
    "stock_krx_buy_real": "TTTC0802U",
    "stock_krx_sell_mock": "VTTC0801U",
    "stock_krx_sell_real": "TTTC0801U",
    # Stock (ATS)
    "stock_ats_buy_mock": "VTTC0852U",
    "stock_ats_buy_real": "TTTC0852U",
    "stock_ats_sell_mock": "VTTC0851U",
    "stock_ats_sell_real": "TTTC0851U",
    # Futures order
    "futures_order_day_mock": "VTTO1101U",
    "futures_order_day_real": "TTTO1101U",
    "futures_order_night_real": "STTN1101U",
    # Futures cancel
    "futures_cancel_day_mock": "VTTO1103U",
    "futures_cancel_day_real": "TTTO1103U",
    "futures_cancel_night_real": "STTN1103U",
    # Futures inquire
    "futures_inquire_day_mock": "VTTO5201R",
    "futures_inquire_day_real": "TTTO5201R",
    "futures_inquire_night_real": "STTN5201R",
}


def _flatten_tr_ids(root: dict) -> dict[str, str]:
    """Map nested ``kis_tr_ids`` block to the flat key namespace used by
    ``ExecutionConfig`` Field defaults. Unknown keys are silently dropped."""
    out: dict[str, str] = {}

    stock = root.get("stock", {}) or {}
    for venue_key in ("krx", "ats"):
        venue = stock.get(venue_key, {}) or {}
        for side in ("buy_mock", "buy_real", "sell_mock", "sell_real"):
            value = venue.get(side)
            if isinstance(value, str) and value:
                out[f"stock_{venue_key}_{side}"] = value

    futures = root.get("futures", {}) or {}
    for op_key in ("order", "cancel", "inquire"):
        op = futures.get(op_key, {}) or {}
        for kind in ("day_mock", "day_real", "night_real"):
            value = op.get(kind)
            if isinstance(value, str) and value:
                out[f"futures_{op_key}_{kind}"] = value
    return out


@lru_cache(maxsize=1)
def get_tr_ids() -> dict[str, str]:
    """Return the merged TR ID mapping (YAML overlaid on baked defaults)."""
    try:
        from shared.config.loader import ConfigLoader

        data = ConfigLoader.load("kis/tr_ids.yaml")
    except Exception as exc:  # pragma: no cover — fall through to defaults
        logger.info(
            "kis/tr_ids.yaml unavailable (%s); using built-in TR ID defaults", exc
        )
        return dict(_DEFAULTS)

    if not isinstance(data, dict):
        return dict(_DEFAULTS)
    root = data.get("kis_tr_ids", {})
    if not isinstance(root, dict):
        return dict(_DEFAULTS)

    overrides = _flatten_tr_ids(root)
    merged = dict(_DEFAULTS)
    merged.update(overrides)
    return merged


def tr_id(key: str) -> str:
    """Convenience wrapper used by ``ExecutionConfig`` field default factories.

    Returns the YAML-overridden value if present, otherwise the baked default.
    Raises ``KeyError`` if the key is unknown — callers should use one of the
    keys listed in ``_DEFAULTS``.
    """
    if key not in _DEFAULTS:
        raise KeyError(f"unknown TR ID key: {key}")
    return get_tr_ids().get(key, _DEFAULTS[key])
