# shared/strategy/gates/conviction_hold_gate.py
"""Conviction-hold conjunction gate (THESIS C).

Strategy-agnostic PURE FILTER. Given a decision timestamp and a set of
already-computed inputs, it answers a once-a-day question: should we ARM a
high-conviction directional HOLD (long/short), or stay FLAT? The thesis: only
arm when MULTIPLE independent high-conviction signals ALIGN —

  1. MFI regime is STRONG in a single direction (BULL_STRONG / BEAR_STRONG),
  2. semiconductor-sector leadership agrees (반도체 basket relative strength),
  3. the session has established a *directional, efficient* morning move,
  4. (optional) the LLM daily bias agrees — PERMISSIVE on missing (§9).

… then HOLD with a wide trailing stop, otherwise stay flat.

VALIDATION STATUS — falsified on the clean window. The counterfactual
(``scripts/analysis/conviction_hold_counterfactual.py``) shows this conjunction
is *anti-predictive* on KOSPI200 futures Dec2025–Apr2026: it arms into reversals
(65% false-start rate, EOD-proxy PnL −12% across the window, OOS true-positive
rate 0%). Root cause: intraday KOSPI200 is mean-reverting, so the strong-
conjunction days (big morning move + aligned regime + sector leadership) are
disproportionately the overextended days that *reverse*. This gate ships
``enabled: false`` as a tested, reproducible building block and a guard against
re-deriving the same negative. See
``docs/superpowers/plans/2026-06-25-futures-conviction-hold-strategy.md``.

Pure filter contract (mirrors RegimeGate):
  * Look-ahead-safe: every input is computed by the caller from bars up to and
    including ``ts``; the gate never reaches forward.
  * PERMISSIVE on missing (§9): a missing *optional* input (LLM bias) does not
    block. A missing *required* structural input (MFI / leadership / morning
    move) yields FLAT, because the conjunction by definition needs all of them.
    ``permissive_on_missing`` only governs the optional LLM arm.
  * Config-driven: build via ``conviction_hold_cfg_from_yaml``.
  * Long/short symmetric: every threshold is mirrored.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# MFI states the MarketClassifier emits that count as "strong" each direction.
_BULL_STRONG_STATES = ("BULL_STRONG",)
_BEAR_STRONG_STATES = ("BEAR_STRONG",)


@dataclass
class ConvictionHoldConfig:
    """Conjunction-gate thresholds. All directionally symmetric."""

    # Morning structural arm (computed from open -> decision-time bars).
    min_morning_disp_pct: float = 0.30  # |displacement from open| as % of price
    min_morning_efficiency: float = 0.10  # Kaufman ER over the morning path
    # MFI regime arm.
    require_mfi_strong: bool = True  # require BULL_STRONG / BEAR_STRONG
    # Semiconductor-leadership arm (prior-session 반도체 basket daily change %).
    min_semi_leadership_pct: float = 0.50
    # Optional LLM daily-bias arm (PERMISSIVE on missing).
    use_llm_bias: bool = False
    permissive_on_missing: bool = True
    # Decision window (KST). The gate is meant to be asked once, mid-morning.
    decision_hour: int = 10
    decision_minute: int = 0
    allow_short: bool = True  # futures long/short symmetry


@dataclass
class ConvictionHoldInputs:
    """All inputs the caller has already computed from bars up to ``ts``.

    Keeping this a plain value object (not a live source) keeps the gate pure
    and trivially unit-testable; the live wiring/backtest replay supplies it.
    """

    morning_disp_pct: float | None  # signed: + = above open, - = below
    morning_efficiency: float | None  # Kaufman ER in [0, 1]
    mfi_state: str | None  # e.g. "BULL_STRONG"
    semi_leadership_pct: float | None  # prior-session semiconductor basket %
    llm_bias: str | None = None  # "long" | "short" | "flat" | None


class ConvictionHoldGate:
    """Strategy-agnostic conjunction gate. Returns
    ``(arm: bool, direction: str, reason: str, score: float)`` where direction
    is "long" | "short" | "flat" and score in [0, 1] is a crude conviction
    proxy (only meaningful when arm is True).
    """

    def __init__(self, config: ConvictionHoldConfig):
        self._cfg = config

    def evaluate(
        self, ts: dt.datetime, inputs: ConvictionHoldInputs  # noqa: ARG002
    ) -> tuple[bool, str, str, float]:
        cfg = self._cfg

        # --- required structural inputs: missing any => cannot form conjunction ---
        if inputs.morning_disp_pct is None or inputs.morning_efficiency is None:
            return (False, "flat", "missing_morning_structure", 0.0)
        if cfg.require_mfi_strong and inputs.mfi_state is None:
            return (False, "flat", "missing_mfi_state", 0.0)
        if inputs.semi_leadership_pct is None:
            return (False, "flat", "missing_semi_leadership", 0.0)

        disp = inputs.morning_disp_pct
        eff = inputs.morning_efficiency
        mfi_state = (inputs.mfi_state or "").upper()
        semi = inputs.semi_leadership_pct

        # candidate direction from the morning move
        if disp > 0:
            cand = "long"
        elif disp < 0:
            cand = "short"
        else:
            return (False, "flat", "no_morning_direction", 0.0)
        if cand == "short" and not cfg.allow_short:
            return (False, "flat", "short_disabled", 0.0)

        # --- morning energy/efficiency arm ---
        if abs(disp) < cfg.min_morning_disp_pct:
            return (False, "flat", f"morning_disp={abs(disp):.2f}%<min", 0.0)
        if eff < cfg.min_morning_efficiency:
            return (False, "flat", f"morning_eff={eff:.2f}<min", 0.0)

        # --- MFI regime arm (must be strong in the candidate direction) ---
        if cfg.require_mfi_strong:
            strong_states = (
                _BULL_STRONG_STATES if cand == "long" else _BEAR_STRONG_STATES
            )
            if mfi_state not in strong_states:
                return (False, "flat", f"mfi_state={mfi_state}_not_strong_{cand}", 0.0)

        # --- semiconductor-leadership arm (must agree with candidate direction) ---
        if cand == "long" and semi < cfg.min_semi_leadership_pct:
            return (False, "flat", f"semi_lead={semi:.2f}%<min_long", 0.0)
        if cand == "short" and semi > -cfg.min_semi_leadership_pct:
            return (False, "flat", f"semi_lead={semi:.2f}%>-min_short", 0.0)

        # --- optional LLM daily-bias arm (PERMISSIVE on missing per §9) ---
        bias = (inputs.llm_bias or "").lower()
        if cfg.use_llm_bias:
            if not bias or bias == "flat":
                if not cfg.permissive_on_missing:
                    return (False, "flat", "missing_llm_bias_non_permissive", 0.0)
                # permissive: missing/flat bias does not block
            elif bias != cand:
                return (False, "flat", f"llm_bias={bias}_vs_{cand}", 0.0)

        # conviction proxy: blend of displacement, efficiency, leadership magnitude
        score = min(
            1.0,
            0.34 * min(1.0, abs(disp) / 1.0)
            + 0.33 * min(1.0, eff / 0.25)
            + 0.33 * min(1.0, abs(semi) / 3.0),
        )
        return (True, cand, "armed", score)


def conviction_hold_cfg_from_yaml(d: dict | None) -> ConvictionHoldConfig | None:
    """Build a ConvictionHoldConfig from a per-strategy YAML section.

    Returns None when the strategy has not opted in (missing section or
    ``enabled: false``) — callers then take the no-op branch. Defaults match the
    counterfactual harness so the YAML and the analysis stay in sync.

    Example YAML (under strategy.entry.params):
        conviction_hold_gate:
          enabled: false
          min_morning_disp_pct: 0.30
          min_morning_efficiency: 0.10
          require_mfi_strong: true
          min_semi_leadership_pct: 0.50
          use_llm_bias: false
          permissive_on_missing: true
          decision_hour: 10
          decision_minute: 0
          allow_short: true
    """
    if not d or not d.get("enabled", False):
        return None
    return ConvictionHoldConfig(
        min_morning_disp_pct=float(d.get("min_morning_disp_pct", 0.30)),
        min_morning_efficiency=float(d.get("min_morning_efficiency", 0.10)),
        require_mfi_strong=bool(d.get("require_mfi_strong", True)),
        min_semi_leadership_pct=float(d.get("min_semi_leadership_pct", 0.50)),
        use_llm_bias=bool(d.get("use_llm_bias", False)),
        permissive_on_missing=bool(d.get("permissive_on_missing", True)),
        decision_hour=int(d.get("decision_hour", 10)),
        decision_minute=int(d.get("decision_minute", 0)),
        allow_short=bool(d.get("allow_short", True)),
    )
