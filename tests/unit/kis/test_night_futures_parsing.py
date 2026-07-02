"""Unit tests for H0MFCNT0 (KRX night futures trade) parsing.

Field layout fixtures follow the official koreainvestment/open-trading-api
column lists (examples_llm krx_ngt_futures_ccnl: 49 columns; legacy
ws_domestic_future stockspurchase_cmefuts: 46 columns — first 46 identical).
"""

from __future__ import annotations

import time

from shared.kis.websocket import (
    NIGHT_TRADE_FIELDS,
    NIGHT_TRADE_MIN_FIELDS,
    KISWebSocketAdapter,
    NightFuturesTrade,
    parse_night_futures_trades,
)

# Baseline values keyed by official column index.
_BASE_VALUES = {
    0: "101W9000",  # futs_shrn_iscd
    1: "055930",  # bsop_hour (HHMMSS KST)
    5: "412.35",  # futs_prpr
    6: "410.00",  # futs_oprc
    7: "413.05",  # futs_hgpr
    8: "409.55",  # futs_lwpr
    9: "3",  # last_cnqn
    10: "5321",  # acml_vol
    13: "0.85",  # mrkt_basis
    14: "0.21",  # dprt
    18: "24810",  # hts_otst_stpl_qty (OI)
}


def _night_record(
    n_fields: int = 46, overrides: dict[int, str] | None = None
) -> list[str]:
    """Build one H0MFCNT0 record as a field list (default legacy 46 columns)."""
    fields = ["0"] * n_fields
    for idx, value in _BASE_VALUES.items():
        fields[idx] = value
    for idx, value in (overrides or {}).items():
        fields[idx] = value
    return fields


def _frame(*records: list[str]) -> str:
    return "^".join(field for record in records for field in record)


class TestParseNightFuturesTrades:
    """Tests for the pure parse_night_futures_trades function."""

    def test_valid_single_record_maps_all_confirmed_fields(self):
        ts = time.time()
        trades = parse_night_futures_trades(_frame(_night_record()), ts)

        assert len(trades) == 1
        trade = trades[0]
        assert trade.symbol == "101W9000"
        assert trade.timestamp == ts
        assert trade.trade_time == "055930"
        assert trade.price == 412.35
        assert trade.open_price == 410.00
        assert trade.high_price == 413.05
        assert trade.low_price == 409.55
        assert trade.tick_volume == 3.0
        assert trade.cumulative_volume == 5321.0
        assert trade.market_basis == 0.85
        assert trade.disparity_rate == 0.21
        assert trade.open_interest == 24810.0

    def test_examples_llm_49_column_layout_parses(self):
        trades = parse_night_futures_trades(
            _frame(_night_record(n_fields=49)), time.time()
        )
        assert len(trades) == 1
        assert trades[0].price == 412.35
        assert trades[0].open_interest == 24810.0

    def test_multi_record_frame_preserves_wire_order(self):
        first = _night_record(overrides={1: "055801", 5: "411.00"})
        second = _night_record(overrides={1: "055959", 5: "412.90"})
        trades = parse_night_futures_trades(
            _frame(first, second), time.time(), record_count=2
        )

        assert [t.price for t in trades] == [411.00, 412.90]
        assert trades[-1].trade_time == "055959"

    def test_record_count_mismatch_falls_back_to_first_record(self):
        # 46 fields but claimed count 3 (46 % 3 != 0) → parse first record only.
        trades = parse_night_futures_trades(
            _frame(_night_record()), time.time(), record_count=3
        )
        assert len(trades) == 1
        assert trades[0].price == 412.35

    def test_short_frame_returns_empty(self):
        short = _night_record()[: NIGHT_TRADE_MIN_FIELDS - 1]
        assert parse_night_futures_trades(_frame(short), time.time()) == []

    def test_record_without_price_is_dropped(self):
        no_price = _night_record(overrides={NIGHT_TRADE_FIELDS["current_price"]: ""})
        assert parse_night_futures_trades(_frame(no_price), time.time()) == []

    def test_record_without_symbol_is_dropped(self):
        no_symbol = _night_record(overrides={0: " "})
        assert parse_night_futures_trades(_frame(no_symbol), time.time()) == []

    def test_non_numeric_optional_field_degrades_to_none(self):
        bad_basis = _night_record(overrides={NIGHT_TRADE_FIELDS["market_basis"]: "N/A"})
        trades = parse_night_futures_trades(_frame(bad_basis), time.time())
        assert len(trades) == 1
        assert trades[0].market_basis is None
        assert trades[0].price == 412.35

    def test_malformed_trade_time_degrades_to_none(self):
        bad_time = _night_record(overrides={1: "5:59"})
        trades = parse_night_futures_trades(_frame(bad_time), time.time())
        assert len(trades) == 1
        assert trades[0].trade_time is None


class TestAdapterNightTradeRouting:
    """H0MFCNT0 envelope routing through KISWebSocketAdapter._process_message."""

    def _adapter(self, mock_config, callback=None) -> KISWebSocketAdapter:
        adapter = KISWebSocketAdapter(mock_config)
        adapter._night_callback = callback
        return adapter

    def test_night_frame_invokes_night_callback(self, mock_config):
        received: list[NightFuturesTrade] = []
        adapter = self._adapter(mock_config, received.append)

        adapter._process_message(f"0|H0MFCNT0|001|{_frame(_night_record())}")

        assert len(received) == 1
        assert received[0].symbol == "101W9000"
        assert received[0].price == 412.35

    def test_multi_record_envelope_count_is_honored(self, mock_config):
        received: list[NightFuturesTrade] = []
        adapter = self._adapter(mock_config, received.append)
        first = _night_record(overrides={5: "411.00"})
        second = _night_record(overrides={5: "412.90"})

        adapter._process_message(f"0|H0MFCNT0|002|{_frame(first, second)}")

        assert [t.price for t in received] == [411.00, 412.90]

    def test_no_callback_registered_does_not_raise(self, mock_config):
        adapter = self._adapter(mock_config, callback=None)
        adapter._process_message(f"0|H0MFCNT0|001|{_frame(_night_record())}")

    def test_night_frame_does_not_hit_day_callback(self, mock_config):
        day_ticks: list = []
        adapter = self._adapter(mock_config)
        adapter._callback = day_ticks.append

        adapter._process_message(f"0|H0MFCNT0|001|{_frame(_night_record())}")

        assert day_ticks == []

    def test_callback_exception_is_contained(self, mock_config):
        def _boom(_trade: NightFuturesTrade) -> None:
            raise RuntimeError("boom")

        adapter = self._adapter(mock_config, _boom)
        # Must not propagate — the WS processing loop stays alive.
        adapter._process_message(f"0|H0MFCNT0|001|{_frame(_night_record())}")
