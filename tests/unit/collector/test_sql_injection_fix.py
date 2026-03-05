"""Test SQL injection protection in ClickHouse parameterized queries."""
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pytest


class TestDailyAdapterParameterizedQueries:
    """Test parameterized queries in shared/backtest/daily_adapter.py."""

    def test_load_stock_daily_prevents_sql_injection_in_code(self):
        """Test that stock code with SQL injection payload is parameterized."""
        from shared.backtest.daily_adapter import load_stock_daily_from_clickhouse

        # SQL injection payload in code parameter
        malicious_code = "005930' OR '1'='1"
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        mock_client = Mock()
        mock_result = Mock()
        mock_result.result_rows = [
            ("005930", date(2024, 1, 2), 100.0, 105.0, 99.0, 103.0, 1000000),
            ("005930", date(2024, 1, 3), 103.0, 107.0, 102.0, 106.0, 1200000),
        ]
        mock_client.query.return_value = mock_result

        with patch("shared.backtest.daily_adapter.clickhouse_connect.get_client", return_value=mock_client):
            # Should not raise exception and should use parameterized query
            df = load_stock_daily_from_clickhouse(
                code=malicious_code,
                start_date=start_date,
                end_date=end_date
            )

            # Verify query was called with parameters dict
            assert mock_client.query.called
            call_args = mock_client.query.call_args
            query = call_args[0][0]
            params = call_args[1]["parameters"]

            # Verify query uses parameterized placeholders, not f-strings
            assert "{code:String}" in query
            assert "{start:Date}" in query
            assert "{end:Date}" in query

            # Verify parameters are passed separately
            assert params["code"] == malicious_code
            assert params["start"] == start_date
            assert params["end"] == end_date

            # Verify malicious code is NOT in the query string itself
            assert "' OR '1'='1" not in query

    def test_load_stock_daily_prevents_sql_injection_in_dates(self):
        """Test that date parameters with SQL injection are parameterized."""
        from shared.backtest.daily_adapter import load_stock_daily_from_clickhouse

        code = "005930"
        # These would cause SQL injection if not parameterized
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        mock_client = Mock()
        mock_result = Mock()
        mock_result.result_rows = [
            ("005930", date(2024, 1, 2), 100.0, 105.0, 99.0, 103.0, 1000000),
        ]
        mock_client.query.return_value = mock_result

        with patch("shared.backtest.daily_adapter.clickhouse_connect.get_client", return_value=mock_client):
            df = load_stock_daily_from_clickhouse(code, start_date, end_date)

            call_args = mock_client.query.call_args
            query = call_args[0][0]
            params = call_args[1]["parameters"]

            # Verify parameterized query structure
            assert "{start:Date}" in query
            assert "{end:Date}" in query
            assert params["start"] == start_date
            assert params["end"] == end_date

    def test_load_stock_daily_with_only_code_parameter(self):
        """Test load_stock_daily with only code (no start/end dates)."""
        from shared.backtest.daily_adapter import load_stock_daily_from_clickhouse

        code = "005930"

        mock_client = Mock()
        mock_result = Mock()
        mock_result.result_rows = [
            ("005930", date(2024, 1, 2), 100.0, 105.0, 99.0, 103.0, 1000000),
        ]
        mock_client.query.return_value = mock_result

        with patch("shared.backtest.daily_adapter.clickhouse_connect.get_client", return_value=mock_client):
            df = load_stock_daily_from_clickhouse(code=code)

            call_args = mock_client.query.call_args
            query = call_args[0][0]
            params = call_args[1]["parameters"]

            # Should only have code parameter
            assert "{code:String}" in query
            assert params["code"] == code
            assert "start" not in params
            assert "end" not in params


class TestStockHistoricalParameterizedQueries:
    """Test parameterized queries in shared/collector/historical/stock.py."""

    def test_delete_stock_minute_day_prevents_sql_injection(self):
        """Test delete function uses parameterized query."""
        from shared.collector.historical.stock import delete_stock_minute_day

        malicious_code = "005930'; DROP TABLE minute_candles; --"
        day = date(2024, 1, 15)

        mock_client = Mock()
        mock_client.query.return_value = None

        # Should validate and reject non-alphanumeric code
        with pytest.raises(ValueError, match="Invalid code"):
            delete_stock_minute_day(mock_client, malicious_code, day)

    def test_delete_stock_minute_day_with_valid_code(self):
        """Test delete function with valid code uses parameterized query."""
        from shared.collector.historical.stock import delete_stock_minute_day

        code = "005930"
        day = date(2024, 1, 15)

        mock_client = Mock()
        mock_client.query.return_value = None

        delete_stock_minute_day(mock_client, code, day)

        # Verify query was called with parameterized query
        assert mock_client.query.called
        call_args = mock_client.query.call_args
        query = call_args[0][0]
        params = call_args[1]["parameters"]

        # Verify uses %(code)s and %(day)s placeholders
        assert "%(code)s" in query
        assert "%(day)s" in query
        assert params["code"] == code
        assert params["day"] == day.strftime("%Y-%m-%d")

        # Verify no f-string interpolation
        assert code not in query
        assert "005930" not in query

    def test_load_stock_minute_prevents_sql_injection_in_code(self):
        """Test load_stock_minute_from_clickhouse prevents SQL injection."""
        from shared.collector.historical.stock import load_stock_minute_from_clickhouse

        malicious_code = "005930' UNION SELECT * FROM system.tables --"
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        mock_client = Mock()
        mock_result = Mock()
        mock_result.result_rows = [
            ("005930", datetime(2024, 1, 2, 9, 0), 100.0, 105.0, 99.0, 103.0, 1000),
        ]
        mock_client.query.return_value = mock_result

        with patch("shared.collector.historical.stock.get_stock_db_client", return_value=mock_client):
            df = load_stock_minute_from_clickhouse(
                code=malicious_code,
                start_date=start_date,
                end_date=end_date
            )

            call_args = mock_client.query.call_args
            query = call_args[0][0]
            params = call_args[1]["parameters"]

            # Verify parameterized query
            assert "%(code)s" in query
            assert "%(start)s" in query
            assert "%(end)s" in query

            # Verify parameters passed separately
            assert params["code"] == malicious_code

            # Verify SQL injection payload is NOT in query string
            assert "UNION SELECT" not in query
            assert "system.tables" not in query

    def test_load_stock_minute_prevents_sql_injection_in_dates(self):
        """Test load_stock_minute_from_clickhouse date parameters."""
        from shared.collector.historical.stock import load_stock_minute_from_clickhouse

        code = "005930"
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        mock_client = Mock()
        mock_result = Mock()
        mock_result.result_rows = [
            ("005930", datetime(2024, 1, 2, 9, 0), 100.0, 105.0, 99.0, 103.0, 1000),
        ]
        mock_client.query.return_value = mock_result

        with patch("shared.collector.historical.stock.get_stock_db_client", return_value=mock_client):
            df = load_stock_minute_from_clickhouse(code, start_date, end_date)

            call_args = mock_client.query.call_args
            params = call_args[1]["parameters"]

            # Verify dates are properly passed as parameters
            assert "start" in params
            assert "end" in params
            assert params["start"] == start_date

    def test_get_stock_codes_from_db_prevents_sql_injection(self):
        """Test get_stock_codes_from_db uses parameterized query for date."""
        from shared.collector.historical.stock import get_stock_codes_from_db

        days = 30

        mock_client = Mock()
        mock_result = Mock()
        mock_result.result_rows = [("005930",), ("000660",), ("035420",)]
        mock_client.query.return_value = mock_result
        mock_client.close.return_value = None

        with patch("shared.collector.historical.stock.get_stock_db_client", return_value=mock_client):
            codes = get_stock_codes_from_db(days=days)

            call_args = mock_client.query.call_args
            query = call_args[0][0]

            # Verify parameterized query for date filter
            assert "{start:Date}" in query

            params = call_args[1]["parameters"]
            assert "start" in params
            assert isinstance(params["start"], date)

            # Verify results
            assert codes == ["005930", "000660", "035420"]

    def test_get_stock_codes_from_db_without_days_filter(self):
        """Test get_stock_codes_from_db without date filter."""
        from shared.collector.historical.stock import get_stock_codes_from_db

        mock_client = Mock()
        mock_result = Mock()
        mock_result.result_rows = [("005930",), ("000660",)]
        mock_client.query.return_value = mock_result
        mock_client.close.return_value = None

        with patch("shared.collector.historical.stock.get_stock_db_client", return_value=mock_client):
            codes = get_stock_codes_from_db(days=None)

            call_args = mock_client.query.call_args
            query = call_args[0][0]

            # Should not have WHERE clause when no days filter
            assert "WHERE" not in query
            assert "{start:Date}" not in query

            # Should have no parameters
            assert call_args[1].get("parameters") is None or call_args[1]["parameters"] == {}

    def test_get_stock_collection_status_prevents_sql_injection(self):
        """Test get_stock_collection_status uses parameterized queries."""
        from shared.collector.historical.stock import get_stock_collection_status

        days = 30

        mock_client = Mock()

        # Mock first query result (aggregate stats)
        mock_result1 = Mock()
        mock_result1.result_rows = [(100000, 20, 5, datetime(2024, 1, 1), datetime(2024, 1, 31))]

        # Mock second query result (per-stock stats)
        mock_result2 = Mock()
        mock_result2.result_rows = [
            ("005930", 5000, 20, datetime(2024, 1, 1), datetime(2024, 1, 31)),
            ("000660", 4800, 20, datetime(2024, 1, 1), datetime(2024, 1, 31)),
        ]

        mock_client.query.side_effect = [mock_result1, mock_result2]
        mock_client.close.return_value = None

        with patch("shared.collector.historical.stock.get_stock_db_client", return_value=mock_client):
            status = get_stock_collection_status(days=days)

            # Verify both queries were called
            assert mock_client.query.call_count == 2

            # Check first query (aggregate)
            call_args1 = mock_client.query.call_args_list[0]
            query1 = call_args1[0][0]
            params1 = call_args1[1]["parameters"]

            assert "{start:Date}" in query1
            assert "start" in params1
            assert isinstance(params1["start"], date)

            # Check second query (per-stock)
            call_args2 = mock_client.query.call_args_list[1]
            query2 = call_args2[0][0]
            params2 = call_args2[1]["parameters"]

            assert "{start:Date}" in query2
            assert "start" in params2


class TestSQLInjectionPayloads:
    """Test various SQL injection attack patterns are prevented."""

    @pytest.mark.parametrize("malicious_code", [
        "'; DROP TABLE minute_candles; --",
        "' OR '1'='1",
        "' UNION SELECT * FROM system.tables --",
        "005930'; DELETE FROM minute_candles WHERE code='005930",
        "' OR code LIKE '%",
        "005930' AND 1=0 UNION SELECT password FROM users --",
    ])
    def test_malicious_code_payloads_in_delete(self, malicious_code):
        """Test various SQL injection payloads are rejected or parameterized."""
        from shared.collector.historical.stock import delete_stock_minute_day

        day = date(2024, 1, 15)
        mock_client = Mock()

        # Non-alphanumeric codes should be rejected
        if not malicious_code.isalnum():
            with pytest.raises(ValueError, match="Invalid code"):
                delete_stock_minute_day(mock_client, malicious_code, day)
        else:
            # If somehow alphanumeric, should still use parameterized query
            delete_stock_minute_day(mock_client, malicious_code, day)
            call_args = mock_client.query.call_args
            params = call_args[1]["parameters"]
            assert params["code"] == malicious_code

    @pytest.mark.parametrize("malicious_code", [
        "'; DROP TABLE minute_candles; --",
        "' OR '1'='1",
        "' UNION SELECT * FROM system.tables --",
    ])
    def test_malicious_code_payloads_in_load_minute(self, malicious_code):
        """Test SQL injection payloads in load_stock_minute_from_clickhouse."""
        from shared.collector.historical.stock import load_stock_minute_from_clickhouse

        mock_client = Mock()
        mock_result = Mock()
        mock_result.result_rows = [
            ("005930", datetime(2024, 1, 2, 9, 0), 100.0, 105.0, 99.0, 103.0, 1000),
        ]
        mock_client.query.return_value = mock_result

        with patch("shared.collector.historical.stock.get_stock_db_client", return_value=mock_client):
            df = load_stock_minute_from_clickhouse(
                code=malicious_code,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )

            # Verify query uses parameters
            call_args = mock_client.query.call_args
            query = call_args[0][0]
            params = call_args[1]["parameters"]

            # Malicious payload should be in parameters, not query string
            assert params["code"] == malicious_code
            assert "DROP TABLE" not in query
            assert "UNION SELECT" not in query
            assert "system.tables" not in query

    @pytest.mark.parametrize("malicious_code", [
        "'; DROP TABLE daily_candles; --",
        "' OR '1'='1",
    ])
    def test_malicious_code_payloads_in_load_daily(self, malicious_code):
        """Test SQL injection payloads in load_stock_daily_from_clickhouse."""
        from shared.backtest.daily_adapter import load_stock_daily_from_clickhouse

        mock_client = Mock()
        mock_result = Mock()
        mock_result.result_rows = [
            ("005930", date(2024, 1, 2), 100.0, 105.0, 99.0, 103.0, 1000000),
        ]
        mock_client.query.return_value = mock_result

        with patch("shared.backtest.daily_adapter.clickhouse_connect.get_client", return_value=mock_client):
            df = load_stock_daily_from_clickhouse(
                code=malicious_code,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )

            call_args = mock_client.query.call_args
            query = call_args[0][0]
            params = call_args[1]["parameters"]

            # Verify parameterization
            assert params["code"] == malicious_code
            assert "DROP TABLE" not in query
            assert "daily_candles" in query  # Table name should be in query
            assert "{code:String}" in query  # But code should be parameterized


class TestParameterValidation:
    """Test parameter validation and edge cases."""

    def test_delete_stock_minute_day_rejects_none_code(self):
        """Test delete rejects None code."""
        from shared.collector.historical.stock import delete_stock_minute_day

        mock_client = Mock()

        # Should return early without calling query
        delete_stock_minute_day(mock_client, None, date(2024, 1, 15))
        assert not mock_client.query.called

    def test_delete_stock_minute_day_rejects_none_day(self):
        """Test delete rejects None day."""
        from shared.collector.historical.stock import delete_stock_minute_day

        mock_client = Mock()

        # Should return early without calling query
        delete_stock_minute_day(mock_client, "005930", None)
        assert not mock_client.query.called

    def test_delete_stock_minute_day_rejects_empty_code(self):
        """Test delete rejects empty string code."""
        from shared.collector.historical.stock import delete_stock_minute_day

        mock_client = Mock()

        # Should return early without calling query
        delete_stock_minute_day(mock_client, "", date(2024, 1, 15))
        assert not mock_client.query.called

    def test_delete_stock_minute_day_rejects_special_characters(self):
        """Test delete rejects code with special characters."""
        from shared.collector.historical.stock import delete_stock_minute_day

        mock_client = Mock()

        # Should raise ValueError for non-alphanumeric
        with pytest.raises(ValueError, match="Invalid code"):
            delete_stock_minute_day(mock_client, "005930-KS", date(2024, 1, 15))

        with pytest.raises(ValueError, match="Invalid code"):
            delete_stock_minute_day(mock_client, "005930.KS", date(2024, 1, 15))

        with pytest.raises(ValueError, match="Invalid code"):
            delete_stock_minute_day(mock_client, "005930;", date(2024, 1, 15))
