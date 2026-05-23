import datetime as dt
from unittest.mock import MagicMock


def _ctx(ts=None, code="futures"):
    from shared.strategy.base import EntryContext
    return EntryContext(
        market_data={"code": code},
        timestamp=ts or dt.datetime.now(dt.UTC),
    )


def _sig(direction="long"):
    s = MagicMock()
    s.metadata = {"signal_direction": direction}
    return s


def _cfg(threshold=60.0):
    from shared.strategy.gates.regime_gate import GateConfig
    return GateConfig(
        regime_percentile_max=threshold,
        impact_score_max=70,
        event_window_minutes=15,
        require_overnight_us_direction=False,
        permissive_on_missing=True,
    )


def test_gate_cfg_none_returns_not_blocked():
    """When gate_cfg is None (strategy not opted in), helper is a no-op."""
    from shared.strategy.gates.adapter_helper import apply_regime_gate
    blocked = apply_regime_gate(
        gate_cfg=None, decision_signal=_sig(), context=_ctx(),
        strategy_name="setup_a_gap_reversion",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is False


def test_gate_allow_path_not_blocked_and_logs(monkeypatch):
    """When the gate allows, blocked=False and a row is logged."""
    from shared.strategy.gates import adapter_helper
    # Stub LiveVolInputs to return None (PERMISSIVE → allow)
    monkeypatch.setattr(adapter_helper, "LiveVolInputs",
                        lambda **_kw: MagicMock(
                            latest_vol_at=MagicMock(return_value=None),
                            events_within=MagicMock(return_value=[]),
                            macro_for=MagicMock(return_value=None)))
    logged_rows = []
    monkeypatch.setattr(adapter_helper, "_log_decision",
                        lambda **kw: logged_rows.append(kw))
    blocked = adapter_helper.apply_regime_gate(
        gate_cfg=_cfg(), decision_signal=_sig("long"), context=_ctx(code="A01603"),
        strategy_name="setup_a_gap_reversion",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is False
    assert len(logged_rows) == 1
    assert logged_rows[0]["strategy"] == "setup_a_gap_reversion"
    assert logged_rows[0]["signal_direction"] == "long"
    assert logged_rows[0]["asset"] == "A01603"
    assert logged_rows[0]["allow"] is True


def test_gate_block_path_blocked_and_logs(monkeypatch):
    """When the gate blocks (high regime_percentile > max), blocked=True and logged."""
    from shared.strategy.gates import adapter_helper
    # Vol asof is 09:00, ts is 09:30 → asof < ts, so NOT treated as future row
    vol_asof = dt.datetime(2026, 5, 22, 9, 0)   # naive — past relative to ts
    ctx_ts = dt.datetime(2026, 5, 22, 9, 30, tzinfo=dt.UTC)
    # Stub LiveVolInputs to return high regime_pct (75 > threshold 60) → block
    monkeypatch.setattr(adapter_helper, "LiveVolInputs",
                        lambda **_kw: MagicMock(
                            latest_vol_at=MagicMock(
                                return_value=(vol_asof, 75.0)),
                            events_within=MagicMock(return_value=[]),
                            macro_for=MagicMock(return_value=None)))
    logged_rows = []
    monkeypatch.setattr(adapter_helper, "_log_decision",
                        lambda **kw: logged_rows.append(kw))
    blocked = adapter_helper.apply_regime_gate(
        gate_cfg=_cfg(threshold=60.0), decision_signal=_sig("long"),
        context=_ctx(ts=ctx_ts), strategy_name="setup_c_event_reaction",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is True
    assert logged_rows[0]["allow"] is False
    assert "regime_percentile" in logged_rows[0]["reason"]


def test_log_failure_does_not_propagate(monkeypatch):
    """CH insert failure must NOT change the gate verdict or raise."""
    from shared.strategy.gates import adapter_helper
    monkeypatch.setattr(adapter_helper, "LiveVolInputs",
                        lambda **_kw: MagicMock(
                            latest_vol_at=MagicMock(return_value=None),
                            events_within=MagicMock(return_value=[]),
                            macro_for=MagicMock(return_value=None)))
    monkeypatch.setattr(adapter_helper, "_log_decision",
                        MagicMock(side_effect=RuntimeError("ch down")))
    blocked = adapter_helper.apply_regime_gate(
        gate_cfg=_cfg(), decision_signal=_sig(),
        context=_ctx(), strategy_name="bb_reversion_15m",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is False  # verdict preserved


def test_signal_direction_falls_back_to_long_when_missing(monkeypatch):
    """When decision_signal has no metadata['signal_direction'] and no .side,
    apply_regime_gate uses 'long' as the default direction passed to the gate
    AND logged for counterfactual review."""
    from shared.strategy.gates import adapter_helper
    monkeypatch.setattr(adapter_helper, "LiveVolInputs",
                        lambda **_kw: MagicMock(
                            latest_vol_at=MagicMock(return_value=None),
                            events_within=MagicMock(return_value=[]),
                            macro_for=MagicMock(return_value=None)))
    logged_rows = []
    monkeypatch.setattr(adapter_helper, "_log_decision",
                        lambda **kw: logged_rows.append(kw))
    sig = MagicMock()
    sig.metadata = {}      # no signal_direction key
    sig.side = None        # no side
    blocked = adapter_helper.apply_regime_gate(
        gate_cfg=_cfg(), decision_signal=sig, context=_ctx(),
        strategy_name="x", redis=MagicMock(), ch_client=MagicMock())
    # Permissive allow (no vol data); the direction must have been 'long'
    assert blocked is False
    assert logged_rows[0]["signal_direction"] == "long"


def test_log_decision_targets_futures_database(monkeypatch):
    """Regression for cross-DB bug: audit row must land in the futures DB
    (kospi by default via CLICKHOUSE_FUTURES_DATABASE), NOT the stock-DB
    default (`market`). Otherwise the weekly counterfactual SELECT reads
    from kospi.regime_gate_decisions while inserts land in market.* —
    silent feature dud."""
    from shared.strategy.gates import adapter_helper
    captured = {}

    class FakeFuturesClient:
        config = type("C", (), {"database": "kospi"})()

        def insert_regime_gate_decisions(self, rows):
            captured["rows"] = rows
            captured["db"] = self.config.database
            return len(rows)

    monkeypatch.setattr(adapter_helper, "futures_clickhouse_client",
                        lambda: FakeFuturesClient())
    monkeypatch.setattr(adapter_helper, "LiveVolInputs",
                        lambda **_kw: MagicMock(
                            latest_vol_at=MagicMock(return_value=None),
                            events_within=MagicMock(return_value=[]),
                            macro_for=MagicMock(return_value=None)))
    adapter_helper.apply_regime_gate(
        gate_cfg=_cfg(), decision_signal=_sig("long"),
        context=_ctx(code="A01603"),
        strategy_name="setup_a_gap_reversion",
        redis=MagicMock(), ch_client=MagicMock())
    assert captured["db"] == "kospi"  # NOT 'market'
    assert captured["rows"][0]["strategy"] == "setup_a_gap_reversion"


def test_futures_clickhouse_database_resolves_env_var(monkeypatch):
    """Helper uses CLICKHOUSE_FUTURES_DATABASE env var (default kospi)."""
    from shared.strategy.gates.adapter_helper import _futures_clickhouse_database
    monkeypatch.delenv("CLICKHOUSE_FUTURES_DATABASE", raising=False)
    assert _futures_clickhouse_database() == "kospi"
    monkeypatch.setenv("CLICKHOUSE_FUTURES_DATABASE", "custom_futures")
    assert _futures_clickhouse_database() == "custom_futures"


def test_acquire_infra_clients_returns_tuple_when_both_available(monkeypatch):
    """Happy path: both Redis + CH client constructed → returns (redis, ch)."""
    from shared.strategy.gates import adapter_helper
    from shared.streaming.client import RedisClient
    monkeypatch.setattr(RedisClient, "get_client",
                        classmethod(lambda _cls: MagicMock(name="redis")))
    fake_ch = MagicMock(name="ch_client")
    fake_ch.get_sync_client = MagicMock(return_value=MagicMock(name="ch_sync"))
    monkeypatch.setattr(adapter_helper, "futures_clickhouse_client",
                        lambda: fake_ch)
    redis, ch = adapter_helper.acquire_infra_clients()
    assert redis is not None
    assert ch is not None


def test_acquire_infra_clients_returns_none_on_redis_failure(monkeypatch):
    """Redis raise → (None, None) PERMISSIVE degrade."""
    from shared.strategy.gates import adapter_helper
    from shared.streaming.client import RedisClient
    monkeypatch.setattr(RedisClient, "get_client",
                        classmethod(lambda _cls: (_ for _ in ()).throw(
                            RuntimeError("redis down"))))
    redis, ch = adapter_helper.acquire_infra_clients()
    assert redis is None
    assert ch is None


def test_acquire_infra_clients_returns_none_when_futures_cli_none(monkeypatch):
    """futures_clickhouse_client returns None → (None, None)."""
    from shared.strategy.gates import adapter_helper
    from shared.streaming.client import RedisClient
    monkeypatch.setattr(RedisClient, "get_client",
                        classmethod(lambda _cls: MagicMock(name="redis")))
    monkeypatch.setattr(adapter_helper, "futures_clickhouse_client",
                        lambda: None)
    redis, ch = adapter_helper.acquire_infra_clients()
    assert redis is None
    assert ch is None
