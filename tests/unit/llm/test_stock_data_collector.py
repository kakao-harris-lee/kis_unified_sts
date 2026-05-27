from shared.llm.collectors import StockDataCollector


def test_previous_date_uses_market_calendar_weekend_skip():
    collector = StockDataCollector()

    assert collector._previous_date("20260525") == "20260522"
