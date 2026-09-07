"""Tests for scripts/trading/flatten_all.py — Phase 5 Task 4."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

spec = importlib.util.spec_from_file_location(
    "flatten_all",
    _REPO_ROOT / "scripts" / "trading" / "flatten_all.py",
)
_module = importlib.util.module_from_spec(spec)
sys.modules["flatten_all"] = _module
spec.loader.exec_module(_module)

_build_open_positions = _module._build_open_positions
render_dry_run = _module.render_dry_run
render_confirmed_summary = _module.render_confirmed_summary
flatten_all_async = _module.flatten_all_async


def _broker(symbol: str, side: str, qty: int, avg_price: float = 100.0) -> dict:
    return {"code": symbol, "side": side, "quantity": qty, "avg_price": avg_price}


@pytest.fixture(autouse=True)
def _hermetic_kis_account_no(monkeypatch):
    """Isolate tests from whatever KIS_ACCOUNT_NO a developer's local .env
    carries (``tests/conftest.py`` loads it once per pytest session, and a
    common placeholder like "your_kis_account_no" fails ExecutionConfig's
    10-digit validator). ``_build_and_run`` resolves ``ExecutionConfig``
    unconditionally now (for the live-mode gate below), so every test here
    needs a deterministic account_no regardless of ambient env.
    """
    monkeypatch.delenv("KIS_ACCOUNT_NO", raising=False)


class TestBuildOpenPositions:
    def test_long_buy_to_long(self):
        positions = _build_open_positions([_broker("A05603", "BUY", 1)])
        assert len(positions) == 1
        assert positions[0].direction == "long"

    def test_short_sell_to_short(self):
        positions = _build_open_positions([_broker("A05603", "SELL", 2)])
        assert len(positions) == 1
        assert positions[0].direction == "short"

    def test_kis_numeric_codes(self):
        positions = _build_open_positions(
            [_broker("A05603", "2", 1), _broker("A05604", "1", 1)]
        )
        sides = [p.direction for p in positions]
        assert "long" in sides
        assert "short" in sides

    def test_zero_qty_skipped(self):
        positions = _build_open_positions([_broker("A05603", "BUY", 0)])
        assert positions == []

    def test_unknown_side_skipped(self):
        positions = _build_open_positions([_broker("A05603", "ambiguous", 1)])
        assert positions == []

    def test_missing_symbol_skipped(self):
        positions = _build_open_positions([{"code": "", "side": "BUY", "quantity": 1}])
        assert positions == []

    def test_unknown_symbol_skipped(self):
        # Symbol with no matching contract spec prefix
        positions = _build_open_positions(
            [{"code": "ZZZ999", "side": "BUY", "quantity": 1}]
        )
        assert positions == []

    def test_avg_price_propagated(self):
        positions = _build_open_positions(
            [_broker("A05603", "BUY", 1, avg_price=331.20)]
        )
        assert positions[0].entry_price == 331.20

    def test_tick_size_resolved_from_spec(self):
        positions = _build_open_positions([_broker("A05603", "BUY", 1)])
        # kospi200_mini tick_size_points = 0.02
        assert positions[0].tick_size_points == 0.02


class TestDryRun:
    def test_no_positions_message(self):
        msg = render_dry_run([])
        assert "no open positions" in msg

    def test_lists_each_position(self):
        positions = _build_open_positions(
            [_broker("A05603", "BUY", 1, avg_price=331.20)]
        )
        msg = render_dry_run(positions)
        assert "A05603" in msg
        assert "long" in msg
        assert "qty=1" in msg
        assert "Re-run with --confirm" in msg


class TestConfirmedSummary:
    def test_empty_results(self):
        msg = render_confirmed_summary([])
        assert "no positions" in msg

    def test_filled_status_shown(self):
        positions = _build_open_positions([_broker("A05603", "BUY", 1)])
        result = SimpleNamespace(state=SimpleNamespace(value="filled"), is_filled=True)
        msg = render_confirmed_summary([(positions[0], result)])
        assert "FILLED" in msg

    def test_failed_status_shown(self):
        positions = _build_open_positions([_broker("A05603", "BUY", 1)])
        msg = render_confirmed_summary([(positions[0], None)])
        assert "FAILED" in msg


class TestFlattenAllAsync:
    @pytest.mark.asyncio
    async def test_calls_close_for_kill_switch_per_position(self):
        broker = [
            _broker("A05603", "BUY", 1, avg_price=331.20),
            _broker("A05604", "SELL", 2, avg_price=329.50),
        ]
        force_close = AsyncMock()
        force_close.close_for_kill_switch = AsyncMock(
            side_effect=[
                SimpleNamespace(state=SimpleNamespace(value="filled"), is_filled=True),
                SimpleNamespace(state=SimpleNamespace(value="filled"), is_filled=True),
            ]
        )

        results = await flatten_all_async(
            broker_positions=broker,
            force_close_executor=force_close,
            reason="test",
            now_ms=1000,
            confirm=True,
        )

        assert len(results) == 2
        assert force_close.close_for_kill_switch.await_count == 2

    @pytest.mark.asyncio
    async def test_per_position_failure_does_not_abort_others(self):
        broker = [
            _broker("A05603", "BUY", 1),
            _broker("A05604", "SELL", 2),
        ]
        force_close = AsyncMock()
        force_close.close_for_kill_switch = AsyncMock(
            side_effect=[
                Exception("KIS down"),
                SimpleNamespace(state=SimpleNamespace(value="filled"), is_filled=True),
            ]
        )

        results = await flatten_all_async(
            broker_positions=broker,
            force_close_executor=force_close,
            reason="test",
            now_ms=1000,
            confirm=True,
        )

        assert len(results) == 2
        assert results[0][1] is None  # failed
        assert results[1][1].is_filled  # succeeded

    @pytest.mark.asyncio
    async def test_empty_broker_positions_yields_no_calls(self):
        force_close = AsyncMock()
        results = await flatten_all_async(
            broker_positions=[],
            force_close_executor=force_close,
            reason="test",
            now_ms=1000,
            confirm=True,
        )
        assert results == []
        force_close.close_for_kill_switch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reason_propagated_to_close_call(self):
        broker = [_broker("A05603", "BUY", 1)]
        force_close = AsyncMock()
        force_close.close_for_kill_switch = AsyncMock(
            return_value=SimpleNamespace(
                state=SimpleNamespace(value="filled"), is_filled=True
            )
        )

        await flatten_all_async(
            broker_positions=broker,
            force_close_executor=force_close,
            reason="custom_reason",
            now_ms=12345,
            confirm=True,
        )

        kwargs = force_close.close_for_kill_switch.call_args.kwargs
        assert kwargs["reason"] == "custom_reason"
        assert kwargs["now_ms"] == 12345

    @pytest.mark.asyncio
    async def test_confirm_required_no_default(self):
        # ``confirm`` is keyword-only with no default — a caller (e.g. a
        # future kill_switch force_close_callback wiring) must decide
        # explicitly rather than silently getting the "send real orders"
        # behavior. LEGACY-006 register gap: this in-process seam previously
        # had no confirm gate at all.
        with pytest.raises(TypeError):
            await flatten_all_async(  # type: ignore[call-arg]
                broker_positions=[],
                force_close_executor=AsyncMock(),
                reason="test",
                now_ms=1000,
            )

    @pytest.mark.asyncio
    async def test_confirm_false_builds_no_client_and_sends_no_orders(self):
        broker = [_broker("A05603", "BUY", 1, avg_price=331.20)]
        force_close = AsyncMock()

        summary = await flatten_all_async(
            broker_positions=broker,
            force_close_executor=force_close,
            reason="test",
            now_ms=1000,
            confirm=False,
        )

        force_close.close_for_kill_switch.assert_not_awaited()
        assert "A05603" in summary
        assert "DRY-RUN" in summary

    @pytest.mark.asyncio
    async def test_confirm_false_with_no_positions(self):
        force_close = AsyncMock()

        summary = await flatten_all_async(
            broker_positions=[],
            force_close_executor=force_close,
            reason="test",
            now_ms=1000,
            confirm=False,
        )

        force_close.close_for_kill_switch.assert_not_awaited()
        assert "no open positions" in summary


class TestBuildAndRunConstruction:
    """Regression: KISClient is constructed config-only (no auth_manager kwarg).

    Guards the crash where the script called
    ``KISClient(config=..., auth_manager=...)`` against a constructor that takes
    ``config`` only — an unconditional ``TypeError`` on every operator run with
    zero test coverage. Exercises the dry-run path (``--confirm`` absent), which
    constructs the REAL ``KISClient(config=...)`` and reads the balance, but
    stops before wiring any executor / issuing any order. Only the network read
    ``get_futures_balance`` is stubbed — no KIS network / live order is touched.
    """

    @pytest.mark.asyncio
    async def test_dry_run_constructs_client_and_reads_balance(
        self, monkeypatch, capsys
    ):
        import shared.kis.client as kis_client_mod

        # KIS_FUTURES_MARKET=real is the normal value on the paper server —
        # it only selects the market-DATA endpoint (KIS's mock server serves
        # no futures data), so it does not imply real order placement here.
        monkeypatch.setenv("KIS_FUTURES_MARKET", "real")
        monkeypatch.setenv("TRADING_MODE", "PAPER")

        raw = [{"code": "A05603", "side": "BUY", "quantity": 1, "avg_price": 331.2}]
        balance_mock = AsyncMock(return_value=raw)
        monkeypatch.setattr(
            kis_client_mod.KISClient, "get_futures_balance", balance_mock
        )

        args = SimpleNamespace(confirm=False, reason="test", live=False)
        rc = await _module._build_and_run(args)

        # Dry-run returns 0 and lists the fetched position; no order issued.
        assert rc == 0
        assert balance_mock.await_count == 1
        out = capsys.readouterr().out
        assert "A05603" in out
        assert "Re-run with --confirm" in out


class TestMarketDataEnvResolution:
    """LEGACY-006: KIS_FUTURES_MARKET must never silently default to real.

    This only selects the market-DATA endpoint for the balance read (see
    TestLiveModeGate below for the actual real-order money gate).
    """

    @pytest.mark.asyncio
    async def test_unset_market_env_aborts_with_configuration_error(self, monkeypatch):
        monkeypatch.delenv("KIS_FUTURES_MARKET", raising=False)
        monkeypatch.setenv("TRADING_MODE", "PAPER")

        args = SimpleNamespace(confirm=False, reason="test", live=False)
        with pytest.raises(_module.ConfigurationError):
            await _module._build_and_run(args)


class TestLiveModeGate:
    """Real order placement is gated by the executor's own trading_mode
    resolution (``config/execution.yaml::execution.trading_mode``, driven
    by ``TRADING_MODE`` / compose's ``FUTURES_EXECUTOR_TRADING_MODE``) —
    NOT by ``KIS_FUTURES_MARKET``, which only selects the market-DATA
    endpoint. ``.env.paper.example`` deliberately sets
    ``KIS_FUTURES_MARKET=real`` on the paper server because KIS's mock
    server serves no futures data at all, so keying the money gate off that
    variable would make ``--confirm`` alone always abort on paper.
    """

    @pytest.mark.asyncio
    async def test_live_trading_mode_without_live_flag_aborts_before_any_client(
        self, monkeypatch, capsys
    ):
        import shared.kis.client as kis_client_mod

        monkeypatch.setenv("KIS_FUTURES_MARKET", "real")
        monkeypatch.setenv("TRADING_MODE", "REAL")

        balance_mock = AsyncMock()
        monkeypatch.setattr(
            kis_client_mod.KISClient, "get_futures_balance", balance_mock
        )
        construction_count = {"n": 0}
        original_init = kis_client_mod.KISClient.__init__

        def _track_init(self, *a, **kw):
            construction_count["n"] += 1
            return original_init(self, *a, **kw)

        monkeypatch.setattr(kis_client_mod.KISClient, "__init__", _track_init)

        args = SimpleNamespace(confirm=True, reason="test", live=False)
        rc = await _module._build_and_run(args)

        assert rc != 0
        # No KIS client was constructed at all — not even for the GET-only
        # balance read — and no balance was fetched.
        assert construction_count["n"] == 0
        balance_mock.assert_not_awaited()
        err = capsys.readouterr().err
        assert "trading_mode" in err.lower()
        assert "--live" in err
        assert "kis_futures_market" not in err.lower()

    @pytest.mark.asyncio
    async def test_live_flag_in_paper_trading_mode_aborts(self, monkeypatch, capsys):
        import shared.kis.client as kis_client_mod

        monkeypatch.setenv("KIS_FUTURES_MARKET", "real")
        monkeypatch.setenv("TRADING_MODE", "PAPER")

        balance_mock = AsyncMock()
        monkeypatch.setattr(
            kis_client_mod.KISClient, "get_futures_balance", balance_mock
        )

        args = SimpleNamespace(confirm=True, reason="test", live=True)
        rc = await _module._build_and_run(args)

        assert rc != 0
        balance_mock.assert_not_awaited()
        err = capsys.readouterr().err
        assert "trading_mode" in err.lower()
        assert "--live" in err
        assert "kis_futures_market" not in err.lower()

    @pytest.mark.asyncio
    async def test_paper_mode_with_confirm_proceeds_with_mock_executor(
        self, monkeypatch, capsys
    ):
        # Full confirmed-path smoke test: PAPER trading_mode + --confirm
        # (no --live) must actually reach flatten_all_async and place
        # (simulated) orders, not merely fail to abort. Every
        # network-touching class is replaced with a fake.
        import redis.asyncio as aioredis_mod

        import shared.execution.executor as executor_mod
        import shared.execution.fill_logger as fill_logger_mod
        import shared.execution.force_close as force_close_mod
        import shared.execution.kis_futures_adapter as adapter_mod
        import shared.kis.client as kis_client_mod
        import shared.kis.futures_feed as feed_mod

        monkeypatch.setenv("KIS_FUTURES_MARKET", "real")
        monkeypatch.setenv("TRADING_MODE", "PAPER")

        raw = [{"code": "A05603", "side": "BUY", "quantity": 1, "avg_price": 331.2}]
        monkeypatch.setattr(
            kis_client_mod.KISClient,
            "get_futures_balance",
            AsyncMock(return_value=raw),
        )

        fake_redis = SimpleNamespace(aclose=AsyncMock())
        monkeypatch.setattr(aioredis_mod, "from_url", lambda *a, **kw: fake_redis)

        monkeypatch.setattr(
            fill_logger_mod,
            "FillLogger",
            lambda **kwargs: SimpleNamespace(flush=AsyncMock()),
        )

        order_executor_fake = SimpleNamespace(initialize=AsyncMock())
        monkeypatch.setattr(
            executor_mod, "OrderExecutor", lambda config: order_executor_fake
        )

        feed_fake = SimpleNamespace(
            update_symbols=lambda symbols: None,
            start=AsyncMock(),
            stop=AsyncMock(),
        )
        monkeypatch.setattr(feed_mod, "KISFuturesPriceFeed", lambda config: feed_fake)

        monkeypatch.setattr(
            adapter_mod, "KISFuturesAdapter", lambda **kwargs: SimpleNamespace()
        )

        filled_result = SimpleNamespace(
            state=SimpleNamespace(value="filled"), is_filled=True
        )
        force_close_fake = SimpleNamespace(
            close_for_kill_switch=AsyncMock(return_value=filled_result)
        )
        monkeypatch.setattr(
            force_close_mod, "ForceCloseExecutor", lambda **kwargs: force_close_fake
        )

        args = SimpleNamespace(confirm=True, reason="test", live=False)
        rc = await _module._build_and_run(args)

        assert rc == 0
        force_close_fake.close_for_kill_switch.assert_awaited_once()
        out = capsys.readouterr().out
        assert "A05603" in out
        assert "FILLED" in out


class TestConfigLoadErrorHandling:
    """_build_and_run's first act is ConfigLoader.load("execution.yaml")
    (for the live-mode gate) — a missing/malformed config file must not
    traceback with a bare exit code 1; it should report the same exit code
    2 as every other configuration failure this script recognizes. The
    catch lives in main() (not _build_and_run), matching how
    ConfigurationError is already handled.
    """

    def test_config_load_error_exits_2_with_no_client_constructed(
        self, monkeypatch, capsys
    ):
        import shared.config.loader as loader_mod
        import shared.kis.client as kis_client_mod

        def _raise_config_error(*args, **kwargs):
            raise loader_mod.ConfigError("execution.yaml malformed")

        monkeypatch.setattr(loader_mod.ConfigLoader, "load", _raise_config_error)

        construction_count = {"n": 0}
        original_init = kis_client_mod.KISClient.__init__

        def _track_init(self, *a, **kw):
            construction_count["n"] += 1
            return original_init(self, *a, **kw)

        monkeypatch.setattr(kis_client_mod.KISClient, "__init__", _track_init)
        monkeypatch.setattr(sys, "argv", ["flatten_all.py"])

        rc = _module.main()

        assert rc == 2
        assert construction_count["n"] == 0
        err = capsys.readouterr().err
        assert "ERROR" in err
        assert "execution.yaml malformed" in err
