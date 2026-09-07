"""Tests for scripts/trading/recover_positions.py — Phase 5 Task 3."""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

spec = importlib.util.spec_from_file_location(
    "recover_positions",
    _REPO_ROOT / "scripts" / "trading" / "recover_positions.py",
)
_module = importlib.util.module_from_spec(spec)
sys.modules["recover_positions"] = _module
spec.loader.exec_module(_module)

_Position = _module._Position
reconcile = _module.reconcile
write_sentinel = _module.write_sentinel
_resolve_sentinel_path = _module._resolve_sentinel_path


def _redis(symbol: str, side: str, qty: int) -> dict:
    return {"symbol": symbol, "side": side, "quantity": qty}


def _broker(symbol: str, side: str, qty: int) -> dict:
    return {"code": symbol, "side": side, "quantity": qty}


class TestPositionParse:
    def test_parses_redis_long(self):
        p = _Position.from_redis_dict(
            {"symbol": "A05603", "side": "long", "quantity": 1}
        )
        assert p.symbol == "A05603"
        assert p.side == "long"
        assert p.quantity == 1

    def test_parses_redis_buy_to_long(self):
        p = _Position.from_redis_dict(
            {"symbol": "A05603", "side": "BUY", "quantity": 1}
        )
        assert p.side == "long"

    def test_parses_redis_sell_to_short(self):
        p = _Position.from_redis_dict(
            {"symbol": "A05603", "side": "sell", "quantity": 1}
        )
        assert p.side == "short"

    def test_parses_kis_buy_to_long(self):
        p = _Position.from_kis_dict({"code": "A05603", "side": "BUY", "quantity": 1})
        assert p.side == "long"

    def test_parses_kis_sell_to_short(self):
        p = _Position.from_kis_dict({"code": "A05603", "side": "SELL", "quantity": 1})
        assert p.side == "short"

    def test_parses_kis_numeric_codes(self):
        # KIS some TR responses use "1"/"2" for sell/buy
        assert (
            _Position.from_kis_dict({"code": "A05603", "side": "2", "quantity": 1}).side
            == "long"
        )
        assert (
            _Position.from_kis_dict({"code": "A05603", "side": "1", "quantity": 1}).side
            == "short"
        )


class TestReconcile:
    def test_match_no_divergence(self):
        redis = [_redis("A05603", "long", 1)]
        broker = [_broker("A05603", "long", 1)]
        broker_only, redis_only, mismatched = reconcile(redis, broker)
        assert broker_only == []
        assert redis_only == []
        assert mismatched == []

    def test_broker_only(self):
        redis = []
        broker = [_broker("A05603", "long", 1)]
        broker_only, redis_only, mismatched = reconcile(redis, broker)
        assert len(broker_only) == 1
        assert broker_only[0].symbol == "A05603"
        assert redis_only == []
        assert mismatched == []

    def test_redis_only(self):
        redis = [_redis("A05603", "long", 1)]
        broker = []
        broker_only, redis_only, mismatched = reconcile(redis, broker)
        assert broker_only == []
        assert len(redis_only) == 1
        assert redis_only[0].symbol == "A05603"
        assert mismatched == []

    def test_quantity_mismatch(self):
        redis = [_redis("A05603", "long", 1)]
        broker = [_broker("A05603", "long", 2)]
        broker_only, redis_only, mismatched = reconcile(redis, broker)
        assert broker_only == []
        assert redis_only == []
        assert len(mismatched) == 1
        rp, bp = mismatched[0]
        assert rp.quantity == 1
        assert bp.quantity == 2

    def test_side_mismatch(self):
        redis = [_redis("A05603", "long", 1)]
        broker = [_broker("A05603", "short", 1)]
        broker_only, redis_only, mismatched = reconcile(redis, broker)
        assert len(mismatched) == 1
        rp, bp = mismatched[0]
        assert rp.side == "long"
        assert bp.side == "short"

    def test_multiple_symbols_all_match(self):
        redis = [_redis("A05603", "long", 1), _redis("A05604", "short", 2)]
        broker = [_broker("A05603", "long", 1), _broker("A05604", "short", 2)]
        broker_only, redis_only, mismatched = reconcile(redis, broker)
        assert broker_only == []
        assert redis_only == []
        assert mismatched == []

    def test_zero_quantity_broker_position_ignored(self):
        # KIS sometimes returns closed positions with qty=0
        redis = []
        broker = [_broker("A05603", "long", 0)]
        broker_only, redis_only, mismatched = reconcile(redis, broker)
        assert broker_only == []

    def test_zero_quantity_redis_position_ignored(self):
        redis = [_redis("A05603", "long", 0)]
        broker = []
        broker_only, redis_only, mismatched = reconcile(redis, broker)
        assert redis_only == []


class TestSentinel:
    def test_resolves_to_provided_path_when_writable(self, tmp_path):
        target = tmp_path / "tripped"
        result = _resolve_sentinel_path(str(target))
        assert result == target

    def test_resolve_raises_sentinel_write_error_when_not_writable(self):
        # The write path and order_router's read path
        # (kill_switch.recovery_sentinel_path) must always be the same
        # file, so a non-writable resolved path now fails loudly instead
        # of silently falling back to a second, different path (the old
        # FALLBACK_SENTINEL_PATH mechanism was removed for exactly this
        # reason — a silent fallback would let the fail-closed guard never
        # arm without anyone noticing).
        with pytest.raises(_module.SentinelWriteError):
            _resolve_sentinel_path("/this/does/not/exist/tripped")

    def test_build_and_run_reports_write_failure_as_exit_code_5(
        self, monkeypatch, caplog
    ):
        # End-to-end: a divergence is found, but the sentinel cannot be
        # written. This must surface loudly (exit code 5, an ERROR log, a
        # distinct Telegram alert) rather than silently degrading to a
        # different path or swallowing the failure.
        import argparse
        import asyncio

        async def _fake_redis():
            return []

        async def _fake_broker():
            return [{"code": "A05603", "side": "2", "quantity": 1}]

        sent: list[str] = []

        async def _fake_telegram(summary: str) -> None:
            sent.append(summary)

        monkeypatch.setattr(_module, "_fetch_redis_positions", _fake_redis)
        monkeypatch.setattr(_module, "_fetch_broker_positions", _fake_broker)
        monkeypatch.setattr(_module, "_send_telegram", _fake_telegram)

        unwritable_path = "/this/does/not/exist/tripped"
        args = argparse.Namespace(sentinel_path=unwritable_path)

        with caplog.at_level(logging.ERROR):
            code = asyncio.run(_module._build_and_run(args))

        assert code == 5
        assert not Path(unwritable_path).exists()
        assert len(sent) == 1
        assert "could not be written" in sent[0].lower()
        assert any(
            record.levelno >= logging.ERROR
            and "could not be written" in record.getMessage().lower()
            for record in caplog.records
        )

    def test_write_sentinel_serialises_divergence(self, tmp_path):
        sentinel = tmp_path / "tripped"
        broker_only = [_Position("A05603", "long", 1)]
        redis_only = []
        mismatched = []
        write_sentinel(
            sentinel,
            broker_only=broker_only,
            redis_only=redis_only,
            mismatched=mismatched,
        )
        payload = json.loads(sentinel.read_text())
        assert len(payload["broker_only"]) == 1
        assert payload["broker_only"][0]["symbol"] == "A05603"
        assert payload["redis_only"] == []
        assert payload["mismatched"] == []

    def test_mismatched_serialisation_includes_both_sides(self, tmp_path):
        sentinel = tmp_path / "tripped"
        rp = _Position("A05603", "long", 1)
        bp = _Position("A05603", "short", 1)
        write_sentinel(
            sentinel,
            broker_only=[],
            redis_only=[],
            mismatched=[(rp, bp)],
        )
        payload = json.loads(sentinel.read_text())
        assert len(payload["mismatched"]) == 1
        assert payload["mismatched"][0]["redis"]["side"] == "long"
        assert payload["mismatched"][0]["broker"]["side"] == "short"


class TestFetchBrokerPositionsConstruction:
    """Regression: KISClient is constructed config-only (no auth_manager kwarg).

    Guards the crash where the script called
    ``KISClient(config=..., auth_manager=...)`` against a constructor that takes
    ``config`` only — an unconditional ``TypeError`` on every operator run with
    zero test coverage. The REAL ``KISClient`` constructor is exercised here (so
    a re-introduced bad kwarg fails loudly); only the network read
    ``get_futures_balance`` is stubbed. No KIS network / live order is touched.
    """

    @pytest.mark.asyncio
    async def test_construction_and_balance_read_no_typeerror(self, monkeypatch):
        import shared.kis.client as kis_client_mod

        monkeypatch.setenv("KIS_FUTURES_MARKET", "mock")

        raw = [
            {"code": "A05603", "side": "2", "quantity": 1},
            {"code": "A05604", "side": "1", "quantity": 0},  # closed → filtered
        ]
        balance_mock = AsyncMock(return_value=raw)
        monkeypatch.setattr(
            kis_client_mod.KISClient, "get_futures_balance", balance_mock
        )

        # Exercises the real KISClient(config=...) construction inside the script.
        result = await _module._fetch_broker_positions()

        # Zero-quantity (closed) positions are filtered out.
        assert result == [{"code": "A05603", "side": "2", "quantity": 1}]
        assert balance_mock.await_count == 1


class TestMarketResolution:
    """LEGACY-007: KIS_FUTURES_MARKET must never silently default to real.

    This script sends no orders, so there is no confirm/market-flag gate
    like flatten_all.py — but an unset env var must still abort with a
    non-zero exit code rather than building a real client by default.
    """

    @pytest.mark.asyncio
    async def test_unset_market_env_raises_configuration_error(self, monkeypatch):
        monkeypatch.delenv("KIS_FUTURES_MARKET", raising=False)

        with pytest.raises(_module.ConfigurationError):
            await _module._fetch_broker_positions()

    @pytest.mark.asyncio
    async def test_unrecognized_market_env_raises_configuration_error(
        self, monkeypatch
    ):
        monkeypatch.setenv("KIS_FUTURES_MARKET", "sandbox")

        with pytest.raises(_module.ConfigurationError):
            await _module._fetch_broker_positions()

    @pytest.mark.asyncio
    async def test_mock_env_builds_non_real_client(self, monkeypatch):
        import shared.kis.client as kis_client_mod

        monkeypatch.setenv("KIS_FUTURES_MARKET", "mock")

        captured_config = {}
        original_init = kis_client_mod.KISClient.__init__

        def _capture(self, *, config, **kwargs):
            captured_config["is_real"] = config.is_real
            return original_init(self, config=config, **kwargs)

        monkeypatch.setattr(kis_client_mod.KISClient, "__init__", _capture)
        monkeypatch.setattr(
            kis_client_mod.KISClient,
            "get_futures_balance",
            AsyncMock(return_value=[]),
        )

        await _module._fetch_broker_positions()

        assert captured_config["is_real"] is False

    @pytest.mark.asyncio
    async def test_real_env_builds_real_client(self, monkeypatch):
        import shared.kis.client as kis_client_mod

        monkeypatch.setenv("KIS_FUTURES_MARKET", "real")

        captured_config = {}
        original_init = kis_client_mod.KISClient.__init__

        def _capture(self, *, config, **kwargs):
            captured_config["is_real"] = config.is_real
            return original_init(self, config=config, **kwargs)

        monkeypatch.setattr(kis_client_mod.KISClient, "__init__", _capture)
        monkeypatch.setattr(
            kis_client_mod.KISClient,
            "get_futures_balance",
            AsyncMock(return_value=[]),
        )

        await _module._fetch_broker_positions()

        assert captured_config["is_real"] is True

    def test_build_and_run_aborts_on_unset_market_env(self, monkeypatch, tmp_path):
        # Drive _build_and_run end-to-end (not just _fetch_broker_positions)
        # so this guards the actual operator-facing exit code, not just the
        # helper's own contract.
        import argparse
        import asyncio

        monkeypatch.delenv("KIS_FUTURES_MARKET", raising=False)

        async def _fake_redis():
            return []

        sent: list[str] = []

        async def _fake_telegram(summary: str) -> None:
            sent.append(summary)

        monkeypatch.setattr(_module, "_fetch_redis_positions", _fake_redis)
        monkeypatch.setattr(_module, "_send_telegram", _fake_telegram)
        # _fetch_broker_positions is NOT stubbed here — it must reach the
        # real resolve_futures_market_from_env() call and raise.

        args = argparse.Namespace(sentinel_path=str(tmp_path / "tripped"))
        code = asyncio.run(_module._build_and_run(args))

        assert code != 0
        assert code != 4  # distinct from a generic "broker query failed"
        assert sent == []
        assert not (tmp_path / "tripped").exists()


def _run(monkeypatch, tmp_path, *, redis_pos, broker_pos, broker_raises=False):
    """Drive ``_build_and_run`` offline, returning (exit_code, telegram_summaries)."""
    import argparse
    import asyncio

    async def _fake_redis():
        return redis_pos

    async def _fake_broker():
        if broker_raises:
            raise RuntimeError("broker unreachable")
        return broker_pos

    sent: list[str] = []

    async def _fake_telegram(summary: str) -> None:
        sent.append(summary)

    monkeypatch.setattr(_module, "_fetch_redis_positions", _fake_redis)
    monkeypatch.setattr(_module, "_fetch_broker_positions", _fake_broker)
    monkeypatch.setattr(_module, "_send_telegram", _fake_telegram)

    args = argparse.Namespace(sentinel_path=str(tmp_path / "tripped"))
    return asyncio.run(_module._build_and_run(args)), sent


class TestAdvisoryOnlyMessaging:
    """The Telegram alert must accurately reflect whether a barrier exists.

    Historical regression guard #1 (superseded): the script used to
    announce "order_router blocked" while no process read the sentinel —
    an operator would believe resume was fenced when it was not.

    Historical regression guard #2 (superseded): once order_router was
    wired up to read this sentinel (LEGACY-007) and refuse to start/
    continue while it exists, the alert kept saying "ADVISORY ONLY —
    nothing is blocked", which became the OPPOSITE false claim — an
    operator would believe resume was NOT fenced when it in fact was.

    The current, correct guard: the alert names order_router and states
    the real (now fail-closed) consequence, matching the module docstring.
    """

    def test_divergence_alert_states_the_order_router_barrier(
        self, monkeypatch, tmp_path
    ):
        code, sent = _run(
            monkeypatch,
            tmp_path,
            redis_pos=[],
            broker_pos=[{"code": "A05603", "side": "2", "quantity": 1}],
        )
        assert code == 3
        assert len(sent) == 1
        summary = sent[0]
        assert "order_router" in summary.lower()
        assert "refuses to" in summary.lower() or "refuse to" in summary.lower()
        assert "operator" in summary.lower()
        # The old, now-false claim must be gone — the sentinel IS a barrier.
        assert "advisory only" not in summary.lower()
        assert "nothing is blocked" not in summary.lower()

    def test_divergence_writes_sentinel_but_returns_advisory_exit_code(
        self, monkeypatch, tmp_path
    ):
        code, _ = _run(
            monkeypatch,
            tmp_path,
            redis_pos=[{"symbol": "A05603", "side": "long", "quantity": 1}],
            broker_pos=[{"code": "A05603", "side": "1", "quantity": 1}],
        )
        assert code == 3
        payload = json.loads((tmp_path / "tripped").read_text())
        assert len(payload["mismatched"]) == 1

    def test_coherent_state_sends_no_alert_and_writes_no_sentinel(
        self, monkeypatch, tmp_path
    ):
        code, sent = _run(
            monkeypatch,
            tmp_path,
            redis_pos=[{"symbol": "A05603", "side": "long", "quantity": 1}],
            broker_pos=[{"code": "A05603", "side": "2", "quantity": 1}],
        )
        assert code == 0
        assert sent == []
        assert not (tmp_path / "tripped").exists()

    def test_broker_failure_reaches_no_verdict(self, monkeypatch, tmp_path):
        code, sent = _run(
            monkeypatch,
            tmp_path,
            redis_pos=[],
            broker_pos=[],
            broker_raises=True,
        )
        assert code == 4
        assert sent == []
        assert not (tmp_path / "tripped").exists()


class TestDocstringHonesty:
    """The module docstring is the operator's first read — keep it truthful."""

    def test_docstring_states_order_router_now_consumes_the_sentinel(self):
        # Regression: this docstring used to say "not a barrier ... nothing
        # reads the sentinel", which became false once order_router wired up
        # a consumer (LEGACY-007). The claim must track reality, not repeat
        # a stale "no consumer" assertion.
        doc = _module.__doc__ or ""
        assert "order_router" in doc.lower()
        assert "refuses to" in doc.lower() or "refuse to" in doc.lower()
        assert "blocks nothing" in doc.lower()  # the exit code, not the file

    def test_docstring_does_not_point_at_a_nonexistent_clear_script(self):
        doc = _module.__doc__ or ""
        clear_script = _REPO_ROOT / "scripts" / "recover_positions_clear.sh"
        assert not clear_script.exists(), (
            "A clear script now exists — the docstring's 'there is no "
            "recover_positions_clear.sh' note must be updated."
        )
        # It may name the script only to say it does not exist.
        assert "Operator clears via" not in doc
