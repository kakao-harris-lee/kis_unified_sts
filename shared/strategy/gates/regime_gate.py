# shared/strategy/gates/regime_gate.py
"""Regime/event gate for futures entries (spec 2026-05-21 P1-③ T3).

Pure filter: given a decision timestamp + signal direction, returns
(allow: bool, reason: str, regime_pct: float). Reads vol_forecasts
(HAR-RV regime), event_scores (per-event impact), MacroSnapshot
(overnight US sp500_change_pct). Missing inputs → PERMISSIVE
pass-through (§9). Look-ahead-safe: vol rows with asof > ts are
treated as MISSING, never used. regime_pct is 0.0 when vol data was
missing (distinguishable from a real low-regime 0.0 via reason field).
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass


@dataclass
class GateConfig:
    regime_percentile_max: float = 80.0      # 0–100; block when > this
    impact_score_max: int = 70               # 0–100; block when any event in window > this
    event_window_minutes: int = 15
    require_overnight_us_direction: bool = False  # if True, long needs sp500_pct > 0
    permissive_on_missing: bool = True


class RegimeGate:
    """Strategy-agnostic gate. `inputs` is a duck-typed source with three
    methods: latest_vol_at(ts) → (asof, regime_percentile) | None;
    events_within(ts, window_min) → list[(asof, impact_score)];
    macro_for(date) → sp500_change_pct (percent) | None.
    """

    def __init__(self, config: GateConfig, inputs):
        self._cfg = config
        self._inputs = inputs

    def allow(
        self, ts: dt.datetime, asset: str, signal_direction: str = "long",  # noqa: ARG002
    ) -> tuple[bool, str, float]:
        """Apply the gate. Returns (allow, reason, regime_pct).

        regime_pct is the regime_percentile value used in the decision
        (0.0 when vol data was missing — distinguishable from a real
        low-regime 0.0 only via the reason field).
        """
        cfg = self._cfg
        regime_pct: float = 0.0

        # 1) regime check (look-ahead-safe: future rows treated as missing)
        vol = self._inputs.latest_vol_at(ts)
        if vol is not None and vol[0] is not None and vol[0] > ts:
            vol = None  # future row → missing
        if vol is None:
            if not cfg.permissive_on_missing:
                return (False, "missing_vol_non_permissive", regime_pct)
            # fall through (do not return yet — still check events/overnight)
            regime_reason = "permissive_missing_vol"
        else:
            _, regime_pct = vol
            if regime_pct > cfg.regime_percentile_max:
                return (False, f"regime_percentile={regime_pct:.1f}>max", regime_pct)
            regime_reason = "regime_ok"

        # 2) event check
        events = self._inputs.events_within(ts, cfg.event_window_minutes)
        for asof, impact in events:
            if asof is not None and asof > ts:
                continue  # future event → look-ahead skip
            if impact > cfg.impact_score_max:
                return (False, f"impact_score={impact}>max", regime_pct)

        # 3) overnight US direction alignment (optional)
        if cfg.require_overnight_us_direction:
            sp500_pct = self._inputs.macro_for(ts.date())
            if sp500_pct is None:
                if not cfg.permissive_on_missing:
                    return (False, "missing_macro_non_permissive", regime_pct)
                # fall through allow
            else:
                us_dir = math.copysign(1.0, sp500_pct)
                want = 1.0 if signal_direction == "long" else -1.0
                if us_dir != want:
                    return (False, f"overnight_us_dir={us_dir} vs {signal_direction}", regime_pct)

        return (True, regime_reason, regime_pct)


def regime_gate_cfg_from_yaml(d: dict | None) -> GateConfig | None:
    """Build a GateConfig from a per-strategy YAML config section.

    Returns None when the strategy has not opted in (missing section
    or `enabled: false`) — adapters then take the gate_cfg=None no-op
    branch in apply_regime_gate(). Defaults match
    config/gates/regime_gate_default.yaml (T12 threshold=60).

    Example YAML section (under strategy.entry.params):
        regime_gate:
          enabled: true
          regime_percentile_max: 60.0
          impact_score_max: 70
          event_window_minutes: 15
          require_overnight_us_direction: false
          permissive_on_missing: true
    """
    if not d or not d.get("enabled", False):
        return None
    return GateConfig(
        regime_percentile_max=float(d.get("regime_percentile_max", 60.0)),
        impact_score_max=int(d.get("impact_score_max", 70)),
        event_window_minutes=int(d.get("event_window_minutes", 15)),
        require_overnight_us_direction=bool(
            d.get("require_overnight_us_direction", False)),
        permissive_on_missing=bool(d.get("permissive_on_missing", True)),
    )
