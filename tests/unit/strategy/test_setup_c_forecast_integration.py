"""Tests for Setup C adapter consuming ForecastClient."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import ScheduledEvent
from shared.strategy.base import EntryContext
from shared.strategy.entry.setup_adapters import (
    SetupCEntryAdapter,
    SetupCEntryConfig,
    SetupCForecastIntegrationConfig,
)

KST = ZoneInfo("Asia/Seoul")


class _FakeForecastClient:
    def __init__(self, event_score: Any | None):
        self._event_score = event_score

    async def get_latest_event_score(self) -> Any | None:
        return self._event_score


def _wired_client() -> _FakeForecastClient:
    """A client that satisfies the wiring guard but publishes no score.

    Tests below that exercise the threshold/filter arithmetic with
    ``forecast_integration.enabled=True`` must pass *some* client: the adapter
    now refuses to construct when the feature is on and nothing is wired (see
    ``SetupCEntryAdapter._validate_config``).
    """
    return _FakeForecastClient(None)


def _vf(forecast_atr_eq=3.0):
    return SimpleNamespace(
        asof=datetime.now(UTC),
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=forecast_atr_eq,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )


def _event_context(ts: datetime, event: ScheduledEvent) -> EntryContext:
    return EntryContext(
        market_data={
            "code": "A05603",
            "close": 350.2,
            "prev_close": 349.0,
            "open": 349.5,
            "atr": 0.8,
            "vwap": 349.8,
            "last_15min_high": 350.0,
            "last_15min_low": 349.0,
            "spread_ticks": 1.0,
        },
        indicators={},
        timestamp=ts,
        metadata={"scheduled_events": [event]},
    )


def test_buffer_scales_with_forecast_when_enabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, buffer_vol_mult=0.5, target_vol_mult=2.5
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=_wired_client())
    # When forecast_atr_eq = 6 (2x normal), buffer = 0.5 * 6 = 3
    buffer, target = adapter._derive_thresholds(
        forecast=_vf(forecast_atr_eq=6.0), atr=3.0
    )
    assert buffer == pytest.approx(3.0)
    assert target == pytest.approx(15.0)


def test_buffer_falls_back_to_atr_when_disabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=False, buffer_vol_mult=0.5, target_vol_mult=2.5
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    buffer, target = adapter._derive_thresholds(forecast=None, atr=3.0)
    # ATR-based with existing params (defaults breakout_buffer_atr_mult=0.5, target=2.5)
    assert buffer == pytest.approx(3.0 * 0.5)
    assert target == pytest.approx(3.0 * 2.5)


def test_buffer_falls_back_to_atr_when_forecast_stale():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, buffer_vol_mult=0.5, target_vol_mult=2.5
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=_wired_client())
    # forecast=None simulates stale (client returned None)
    buffer, target = adapter._derive_thresholds(forecast=None, atr=3.0)
    assert buffer == pytest.approx(3.0 * 0.5)
    assert target == pytest.approx(3.0 * 2.5)


def test_event_filter_uses_impact_score_when_enabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, min_event_impact_score=70
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=_wired_client())
    weak = SimpleNamespace(
        asof=datetime.now(UTC),
        impact_score=50,
        event_type="X",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    strong = SimpleNamespace(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    assert adapter._event_passes_filter(weak) is False
    assert adapter._event_passes_filter(strong) is True


def test_event_filter_uses_tier_fallback_when_forecast_disabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(enabled=False)
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    # When forecast disabled, all events pass the new filter (legacy tier filter
    # remains the gate)
    assert adapter._event_passes_filter(None) is True


def test_construction_raises_when_forecast_enabled_but_no_client_wired():
    """Enabling the feature without wiring a client must fail loudly at startup.

    Regression guard for the 2026-06-25..2026-08-05 silent outage: the shipped
    config had forecast_integration.enabled=true while nothing ever passed a
    forecast_client, so every qualifying event was rejected as
    "forecast_event_score_missing" and Setup C emitted zero signals with no
    error anywhere.
    """
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, min_event_impact_score=70
        )
    )

    with pytest.raises(ValueError) as excinfo:
        SetupCEntryAdapter(cfg, forecast_client=None)

    message = str(excinfo.value)
    # The operator must be able to act on the message without opening the source:
    # it has to name the cause and both remedies.
    assert "forecast_integration.enabled is true" in message
    assert "no forecast client" in message
    assert "forecast_event_score_missing" in message
    assert "get_latest_event_score" in message  # remedy 1: wire a client
    assert (
        "config/strategies/futures/setup_c_event_reaction.yaml" in message
    )  # remedy 2: turn the flag off


def test_construction_succeeds_when_forecast_enabled_and_client_wired():
    """The guard keys on the client, not on whether that client has a score yet."""
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, min_event_impact_score=70
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=_wired_client())
    assert adapter._forecast_client is not None


def test_event_filter_fails_open_on_missing_score_when_client_is_wired():
    """A wired client returning None must NOT veto — it defers to the tier gate.

    This is the genuinely contested case: the feature is on, a client is wired,
    and the forecast service is down / the score is stale / nothing has been
    published yet. Settled 2026-08-05 by operator judgment in favour of the
    ratified plan (docs/superpowers/plans/archive/
    2026-05-13-forecast-aware-paradigm.md:3147-3158), which specifies fail-OPEN
    here — commit 81a10e53 had inverted it to fail-closed without review, and
    Setup C emitted zero signals for the following six weeks.

    Fail-open is not unguarded: the legacy ``min_impact_tier`` gate still runs.
    Paired with :func:`test_event_filter_uses_impact_score_when_enabled`, which
    shows a PUBLISHED score is still enforced in both directions.
    """
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, min_event_impact_score=70
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=_wired_client())
    assert adapter._event_passes_filter(None) is True


# ---------------------------------------------------------------------------
# Shipped production config — pins the 2026-08-05 restoration end-to-end.
#
# NOTE: these go through StrategyFactory (the real runtime path:
# ConfigLoader -> EntryRegistry.create). Do NOT substitute
# SetupCEntryConfig.from_yaml(): its _default_section is the dotted string
# "strategy.entry.params", which is never a literal key in the YAML, so it
# silently falls back to pydantic defaults and would assert nothing about what
# actually ships.
# ---------------------------------------------------------------------------


def _production_setup_c_adapter() -> SetupCEntryAdapter:
    """Build the Setup C adapter exactly as the runtime factory builds it."""
    from shared.strategy.builtin_components import register_builtin_components
    from shared.strategy.factory import StrategyFactory

    register_builtin_components()
    strategy = StrategyFactory.create_from_file("futures", "setup_c_event_reaction")
    entry = strategy.entry
    assert isinstance(entry, SetupCEntryAdapter)
    return entry


def test_shipped_production_config_constructs_and_filter_is_fail_open():
    """The shipped config must build (Change C guard) and not veto (Change B).

    If someone flips forecast_integration.enabled back to true in the YAML
    without wiring a client, construction raises here and this test fails loudly
    instead of the strategy going quietly dead in paper.
    """
    adapter = _production_setup_c_adapter()

    assert adapter.config.forecast_integration.enabled is False
    assert adapter._forecast_client is None
    # Flag off → short-circuit to True; the legacy min_impact_tier gate decides,
    # which is what the ratified plan specified for a missing client.
    assert adapter._event_passes_filter(None) is True


@pytest.mark.asyncio
async def test_production_config_emits_signal_for_qualifying_event(monkeypatch):
    """Counterfactual: the shipped config FIRES, and fail-open keeps it firing.

    Phase 1 asserts the emitted signal under the shipped config
    (forecast_integration disabled → the legacy min_impact_tier gate decides).

    Phase 2 rebuilds the same adapter with forecast_integration.enabled=true and
    a wired client that publishes no score — the exact case the 2026-08-05
    judgment settled — and shows the identical context still firing instead of
    being rejected as forecast_event_score_missing.

    Phase 3 hands that same wired client a below-threshold score and shows the
    filter still rejecting. Without it, Phase 2 could be satisfied by a gate
    that had gone inert; together they say the gate discriminates on PUBLISHED
    scores and only defers when there is nothing to discriminate on.
    """
    import shared.strategy.entry.setup_adapters as facade

    evals: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        facade,
        "_publish_setup_eval",
        lambda name, outcome, reason: evals.append((name, outcome, reason)),
    )

    ts = datetime(2026, 4, 23, 9, 30, tzinfo=KST)
    event = ScheduledEvent(
        event_id="event_prod_001",
        event_type="CPI",
        scheduled_at=datetime(2026, 4, 23, 9, 20, tzinfo=KST),  # 10 min < window 15
        impact_tier=1,  # passes min_impact_tier=2
    )

    # --- Phase 1: shipped config ------------------------------------------
    adapter = _production_setup_c_adapter()
    result = await adapter.generate(_event_context(ts, event))

    assert result is not None, f"expected a signal, got none; evals={evals}"
    assert result.strategy == "setup_c_event_reaction"
    assert result.metadata["direction"] == "long"
    assert result.signal_type.value == "entry"
    assert ("setup_c_event_reaction", "fired", "long") in evals
    assert not any(
        reason == "forecast_event_score_missing" for _, _, reason in evals
    ), f"forecast gate still suppressing under the shipped config: {evals}"

    # --- Phase 2: feature on, wired client, NO score published -------------
    evals.clear()
    forecast_on_cfg = adapter.config.model_copy(
        update={
            "forecast_integration": SetupCForecastIntegrationConfig(
                enabled=True, min_event_impact_score=60
            )
        }
    )
    unscored_adapter = SetupCEntryAdapter(
        forecast_on_cfg, forecast_client=_wired_client()
    )
    unscored_result = await unscored_adapter.generate(_event_context(ts, event))

    assert unscored_result is not None, (
        "fail-open regression: a wired client with no score must defer to the "
        f"legacy min_impact_tier gate, not veto; evals={evals}"
    )
    assert not any(
        reason == "forecast_event_score_missing" for _, _, reason in evals
    ), f"the missing-score veto is back: {evals}"

    # --- Phase 3: same wired client, but a below-threshold score -----------
    evals.clear()
    weak_score = SimpleNamespace(
        asof=datetime.now(UTC),
        impact_score=50,  # < min_event_impact_score=60
        event_type="CPI",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    scored_adapter = SetupCEntryAdapter(
        forecast_on_cfg, forecast_client=_FakeForecastClient(weak_score)
    )
    scored_result = await scored_adapter.generate(_event_context(ts, event))

    assert scored_result is None
    assert any(
        reason.startswith("forecast_event_score_below_min") for _, _, reason in evals
    ), f"a published-but-weak score must still be gated; evals={evals}"


@pytest.mark.asyncio
async def test_generate_rejects_entry_when_event_score_below_configured_minimum():
    ts = datetime(2026, 4, 23, 9, 30, tzinfo=KST)
    event = ScheduledEvent(
        event_id="event_001",
        event_type="CPI",
        scheduled_at=datetime(2026, 4, 23, 9, 20, tzinfo=KST),
        impact_tier=1,
    )
    weak_event_score = SimpleNamespace(
        asof=datetime.now(UTC),
        impact_score=50,
        event_type="CPI",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    cfg = SetupCEntryConfig(
        daily_bias_filter_enabled=False,
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True,
            min_event_impact_score=70,
        ),
    )
    adapter = SetupCEntryAdapter(
        cfg,
        forecast_client=_FakeForecastClient(weak_event_score),
    )

    result = await adapter.generate(_event_context(ts, event))

    assert result is None
    assert not adapter._setup.tracker.already_traded(event.event_id)
