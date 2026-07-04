"""Williams %R 선물 양방향 변형 회귀 테스트.

설계: docs/superpowers/specs/archive/2026-05-15-williams-r-futures-design.md

검증:
  - allow_short=True 에서 과매수 반전 → SHORT 진입 (신규)
  - allow_short=False(주식 default) 에서 SHORT 미생성 (후방호환)
  - allow_short=True 에서 과매도 반전 → LONG 진입 (회귀)
  - trend_filter SHORT 방향 (close < bb_middle 요구)
  - Exit: SHORT 포지션 oversold 청산 (신규)
  - Exit: LONG 포지션 overbought 청산 (회귀)
  - 선물 config(williams_r_15m) 로딩
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason
from shared.strategy.base import EntryContext, ExitContext
from shared.strategy.entry.williams_r import WilliamsRConfig, WilliamsREntry
from shared.strategy.exit.williams_r_exit import WilliamsRExit, WilliamsRExitConfig

KST = timezone(timedelta(hours=9))


def _entry_ctx(
    *,
    close=300.0,
    bb_middle=301.0,
    williams_r=-15.0,
    volume=1000,
    volume_ma=900,
    hour=10,
    minute=30,
    market_state=None,
):
    now = datetime(2026, 5, 15, hour, minute, tzinfo=KST)
    metadata = {}
    if market_state is not None:
        metadata["market_state"] = market_state
    return EntryContext(
        market_data={"code": "101S6000", "name": "KOSPI200 F", "close": close},
        indicators={
            "bb_middle": bb_middle,
            "volume": volume,
            "volume_ma": volume_ma,
            "momentum_5m": {"williams_r": williams_r},
        },
        timestamp=now,
        metadata=metadata,
    )


def _futures_entry_config(**overrides) -> WilliamsRConfig:
    base = {
        "williams_r_period": 14,
        "oversold_threshold": -80.0,
        "reversal_threshold": -80.0,
        "overbought_threshold": -20.0,
        "overbought_reversal_threshold": -20.0,
        "allow_short": True,
        "trend_filter": True,
        "volume_confirm": True,
        "volume_threshold": 1.0,
        "signal_cooldown_seconds": 0,
        "skip_market_open_minutes": 15,
        "skip_market_close_minutes": 30,
        "market_close_hour": 15,
        "market_close_minute": 45,
    }
    base.update(overrides)
    return WilliamsRConfig(**base)


class TestVolumeFilterRvol:
    """volume_confirm은 canonical `rvol`을 우선 사용해야 한다.

    회귀: 인디케이터 파이프라인은 `volume` 키를 노출하지 않고 `rvol`/`volume_ma`만
    노출한다. 과거 `volume < threshold*volume_ma` 로직은 volume→0으로 해석되어
    100% 시그널을 차단했다 (williams_r_15m 백테스트 0거래의 2차 원인).
    """

    def _ctx_no_volume_key(self, *, williams_r, rvol, hour=10, minute=30):
        now = datetime(2026, 5, 15, hour, minute, tzinfo=KST)
        ind = {
            "bb_middle": 301.0,
            "rvol": rvol,  # canonical, present
            "momentum_5m": {"williams_r": williams_r},
        }
        # close > bb_middle so LONG trend_filter passes; isolates the volume
        # filter as the only variable. Deliberately NO "volume" key (matches
        # the real indicator pipeline which emits rvol/volume_ma, not volume).
        return EntryContext(
            market_data={"code": "101S6000", "name": "KF", "close": 305.0},
            indicators=ind,
            timestamp=now,
        )

    @pytest.mark.asyncio
    async def test_rvol_above_threshold_allows_signal(self):
        entry = WilliamsREntry(_futures_entry_config(volume_threshold=1.0))
        await entry.generate(
            self._ctx_no_volume_key(williams_r=-90.0, rvol=1.5, hour=10, minute=0)
        )
        sig = await entry.generate(
            self._ctx_no_volume_key(williams_r=-75.0, rvol=1.5, hour=10, minute=5)
        )
        assert sig is not None
        assert sig.metadata["signal_direction"] == "long"

    @pytest.mark.asyncio
    async def test_rvol_below_threshold_blocks_signal(self):
        entry = WilliamsREntry(_futures_entry_config(volume_threshold=1.0))
        await entry.generate(
            self._ctx_no_volume_key(williams_r=-90.0, rvol=0.4, hour=10, minute=0)
        )
        sig = await entry.generate(
            self._ctx_no_volume_key(williams_r=-75.0, rvol=0.4, hour=10, minute=5)
        )
        assert sig is None


class TestMarketStateFilter:
    def _config(self) -> WilliamsRConfig:
        return _futures_entry_config(
            allow_short=False,
            market_state_filter={
                "enabled": True,
                "allowed_states": ["BULL", "BULL_STRONG", "SIDEWAYS_UP"],
                "blocked_states": ["BEAR", "SIDEWAYS_DOWN", "UNKNOWN"],
            },
        )

    @pytest.mark.asyncio
    async def test_allowed_market_state_allows_long_reversal(self):
        entry = WilliamsREntry(self._config())
        await entry.generate(
            _entry_ctx(
                williams_r=-90.0,
                close=302.0,
                bb_middle=301.0,
                market_state="BULL_STRONG",
                hour=10,
                minute=0,
            )
        )
        sig = await entry.generate(
            _entry_ctx(
                williams_r=-75.0,
                close=302.0,
                bb_middle=301.0,
                market_state="BULL_STRONG",
                hour=10,
                minute=5,
            )
        )
        assert sig is not None
        assert sig.metadata["signal_direction"] == "long"

    @pytest.mark.asyncio
    async def test_blocked_market_state_suppresses_reversal(self):
        entry = WilliamsREntry(self._config())
        await entry.generate(
            _entry_ctx(
                williams_r=-90.0,
                close=302.0,
                bb_middle=301.0,
                market_state="BULL_STRONG",
                hour=10,
                minute=0,
            )
        )
        sig = await entry.generate(
            _entry_ctx(
                williams_r=-75.0,
                close=302.0,
                bb_middle=301.0,
                market_state="SIDEWAYS_DOWN",
                hour=10,
                minute=5,
            )
        )
        assert sig is None

    @pytest.mark.asyncio
    async def test_missing_market_state_suppresses_reversal_when_filter_enabled(self):
        entry = WilliamsREntry(self._config())
        await entry.generate(
            _entry_ctx(
                williams_r=-90.0,
                close=302.0,
                bb_middle=301.0,
                market_state="BULL_STRONG",
                hour=10,
                minute=0,
            )
        )
        sig = await entry.generate(
            _entry_ctx(
                williams_r=-75.0,
                close=302.0,
                bb_middle=301.0,
                hour=10,
                minute=5,
            )
        )
        assert sig is None

    def test_market_state_filter_adds_mfi_requirement(self):
        cfg = self._config()
        assert "mfi" in WilliamsREntry(cfg).required_indicators
        cfg.market_state_filter["enabled"] = False
        assert "mfi" not in WilliamsREntry(cfg).required_indicators


class TestBidirectionalEntry:
    @pytest.mark.asyncio
    async def test_short_on_overbought_reversal(self):
        """과매수 깊이 진입 후 반전하강 → SHORT (close < bb_middle 추세 일치)."""
        entry = WilliamsREntry(_futures_entry_config())
        # prev bar deep overbought (> -20, e.g. -5)
        assert (
            await entry.generate(
                _entry_ctx(
                    williams_r=-5.0, close=300.0, bb_middle=301.0, hour=10, minute=0
                )
            )
            is None
        )
        # current bar crossed down below reversal line (-20)
        sig = await entry.generate(
            _entry_ctx(
                williams_r=-25.0, close=300.0, bb_middle=301.0, hour=10, minute=5
            )
        )
        assert sig is not None
        assert sig.metadata["signal_direction"] == "short"
        assert sig.metadata["williams_r"] == -25.0

    @pytest.mark.asyncio
    async def test_no_short_when_allow_short_false(self):
        """allow_short=False(주식 default)면 과매수 반전이 와도 SHORT 미생성."""
        entry = WilliamsREntry(_futures_entry_config(allow_short=False))
        await entry.generate(_entry_ctx(williams_r=-5.0, hour=10, minute=0))
        sig = await entry.generate(_entry_ctx(williams_r=-25.0, hour=10, minute=5))
        assert sig is None

    @pytest.mark.asyncio
    async def test_long_still_works_with_allow_short(self):
        """allow_short=True 에서도 과매도 반전 LONG은 정상 (회귀)."""
        entry = WilliamsREntry(_futures_entry_config())
        await entry.generate(
            _entry_ctx(
                williams_r=-90.0, close=302.0, bb_middle=301.0, hour=10, minute=0
            )
        )
        sig = await entry.generate(
            _entry_ctx(
                williams_r=-75.0, close=302.0, bb_middle=301.0, hour=10, minute=5
            )
        )
        assert sig is not None
        assert sig.metadata["signal_direction"] == "long"

    @pytest.mark.asyncio
    async def test_short_trend_filter_blocks_when_price_above_bb(self):
        """SHORT인데 close > bb_middle(상승추세)면 trend_filter가 차단."""
        entry = WilliamsREntry(_futures_entry_config())
        await entry.generate(
            _entry_ctx(williams_r=-5.0, close=305.0, bb_middle=301.0, hour=10, minute=0)
        )
        sig = await entry.generate(
            _entry_ctx(
                williams_r=-25.0, close=305.0, bb_middle=301.0, hour=10, minute=5
            )
        )
        assert sig is None


def _make_position(side: PositionSide, entry_price=300.0):
    return Position(
        id="f-pos-1",
        code="101S6000",
        name="KOSPI200 F",
        side=side,
        quantity=1,
        entry_price=entry_price,
        entry_time=datetime(2026, 5, 15, 10, 0, tzinfo=KST),
        current_price=entry_price,
        highest_price=entry_price,
        lowest_price=entry_price,
        state=PositionState.SURVIVAL,
        strategy="williams_r_15m",
    )


def _exit_ctx(position, *, current_price=300.0, williams_r=-50.0, hour=10, minute=45):
    # entry_time is 10:00; keep holding < time_cut_minutes (120) so the
    # indicator-exit branch is reached without TIME_CUT pre-empting it.
    now = datetime(2026, 5, 15, hour, minute, tzinfo=KST)
    return ExitContext(
        position=position,
        market_data={position.code: {"close": current_price, "price": current_price}},
        indicators={"momentum_5m": {"williams_r": williams_r}},
        timestamp=now,
        metadata={"is_backtest": True},  # skip EOD branch for indicator test
    )


class TestDirectionAwareExit:
    @pytest.mark.asyncio
    async def test_short_position_exits_on_oversold(self):
        """SHORT 포지션은 %R <= oversold_exit_threshold 에서 indicator exit."""
        cfg = WilliamsRExitConfig(
            overbought_threshold=-20.0,
            oversold_exit_threshold=-80.0,
            max_stop_loss_pct=-0.03,
            time_cut_minutes=120,
            eod_close_hour=15,
            eod_close_minute=45,
        )
        ex = WilliamsRExit(cfg)
        pos = _make_position(PositionSide.SHORT, entry_price=300.0)
        # price flat (no hard stop), %R deep oversold → SHORT covers
        should, sig = await ex.should_exit(
            _exit_ctx(pos, current_price=300.0, williams_r=-85.0)
        )
        assert should is True
        assert sig.reason == ExitReason.INDICATOR_EXIT
        assert sig.metadata["williams_r"] == -85.0

    @pytest.mark.asyncio
    async def test_short_position_not_exit_on_overbought(self):
        """SHORT 포지션은 과매수(%R 높음)에서는 indicator exit 안 함."""
        cfg = WilliamsRExitConfig(oversold_exit_threshold=-80.0)
        ex = WilliamsRExit(cfg)
        pos = _make_position(PositionSide.SHORT, entry_price=300.0)
        should, _ = await ex.should_exit(
            _exit_ctx(pos, current_price=300.0, williams_r=-10.0)
        )
        assert should is False

    @pytest.mark.asyncio
    async def test_long_position_exits_on_overbought_regression(self):
        """LONG 포지션 과매수 청산은 기존대로 동작 (회귀)."""
        cfg = WilliamsRExitConfig(overbought_threshold=-20.0)
        ex = WilliamsRExit(cfg)
        pos = _make_position(PositionSide.LONG, entry_price=300.0)
        should, sig = await ex.should_exit(
            _exit_ctx(pos, current_price=300.0, williams_r=-10.0)
        )
        assert should is True
        assert sig.reason == ExitReason.INDICATOR_EXIT


class TestFuturesConfigLoads:
    def test_williams_r_15m_loads_with_short_and_futures_eod(self):
        from shared.strategy.registry import (
            StrategyFactory,
            register_builtin_components,
        )

        register_builtin_components()
        s = StrategyFactory.create_from_file("futures", "williams_r_15m")
        assert s.name == "williams_r_15m"
        assert s.entry.config.allow_short is True
        assert (
            s.entry.config.market_close_hour,
            s.entry.config.market_close_minute,
        ) == (15, 45)
        assert s.exit.config.oversold_exit_threshold == -80.0
        assert (s.exit.config.eod_close_hour, s.exit.config.eod_close_minute) == (
            15,
            45,
        )

    def test_stock_williams_r_loads_as_long_only_strategy(self):
        """주식 williams_r은 long-only, EOD 15:15 설정을 유지한다."""
        from shared.strategy.registry import (
            StrategyFactory,
            register_builtin_components,
        )

        register_builtin_components()
        s = StrategyFactory.create_from_file("stock", "williams_r")
        assert s.entry.config.allow_short is False
        assert (
            s.entry.config.market_close_hour,
            s.entry.config.market_close_minute,
        ) == (15, 15)
        assert s.entry.config.market_state_filter["enabled"] is True
        assert s.exit.config.overbought_threshold == 0.0
