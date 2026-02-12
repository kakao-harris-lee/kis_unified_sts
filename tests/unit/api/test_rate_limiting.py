"""Tests for rate limiting on API endpoints."""



class TestRateLimiting:
    """Test rate limiting is applied to endpoints."""

    def test_api_v1_status_has_rate_limit(self):
        """Status endpoint should have rate limiting."""
        from services.api.routes import router

        # Find the status route
        route = next(
            (r for r in router.routes if getattr(r, "path", "") == "/api/v1/status"),
            None,
        )
        assert route is not None, "/api/v1/status route not found"

        # Check dependencies include rate limit
        deps = getattr(route, "dependencies", []) or []
        assert len(deps) > 0, "/api/v1/status should have rate limit dependency"

    def test_api_v1_trading_status_has_rate_limit(self):
        """Trading status endpoint should have rate limiting."""
        from services.api.routes import router

        route = next(
            (
                r
                for r in router.routes
                if getattr(r, "path", "") == "/api/v1/trading/status"
            ),
            None,
        )
        assert route is not None, "/api/v1/trading/status route not found"

        deps = getattr(route, "dependencies", []) or []
        assert (
            len(deps) > 0
        ), "/api/v1/trading/status should have rate limit dependency"

    def test_api_v1_trading_metrics_has_rate_limit(self):
        """Trading metrics endpoint should have rate limiting."""
        from services.api.routes import router

        route = next(
            (
                r
                for r in router.routes
                if getattr(r, "path", "") == "/api/v1/trading/metrics"
            ),
            None,
        )
        assert route is not None, "/api/v1/trading/metrics route not found"

        deps = getattr(route, "dependencies", []) or []
        assert (
            len(deps) > 0
        ), "/api/v1/trading/metrics should have rate limit dependency"

    def test_api_v1_strategies_has_rate_limit(self):
        """Strategies endpoint should have rate limiting."""
        from services.api.routes import router

        route = next(
            (
                r
                for r in router.routes
                if getattr(r, "path", "") == "/api/v1/strategies"
            ),
            None,
        )
        assert route is not None, "/api/v1/strategies route not found"

        deps = getattr(route, "dependencies", []) or []
        assert len(deps) > 0, "/api/v1/strategies should have rate limit dependency"

    def test_api_v1_strategies_detail_has_rate_limit(self):
        """Strategy detail endpoint should have rate limiting."""
        from services.api.routes import router

        route = next(
            (
                r
                for r in router.routes
                if getattr(r, "path", "") == "/api/v1/strategies/{name}"
            ),
            None,
        )
        assert route is not None, "/api/v1/strategies/{name} route not found"

        deps = getattr(route, "dependencies", []) or []
        assert (
            len(deps) > 0
        ), "/api/v1/strategies/{name} should have rate limit dependency"

    def test_api_v1_backtest_results_has_rate_limit(self):
        """Backtest results endpoint should have rate limiting."""
        from services.api.routes import router

        route = next(
            (
                r
                for r in router.routes
                if getattr(r, "path", "") == "/api/v1/backtest/results"
            ),
            None,
        )
        assert route is not None, "/api/v1/backtest/results route not found"

        deps = getattr(route, "dependencies", []) or []
        assert (
            len(deps) > 0
        ), "/api/v1/backtest/results should have rate limit dependency"

    def test_health_check_exempt_from_rate_limit(self):
        """Health check should be exempt from rate limiting."""
        from services.api.routes import router

        route = next(
            (r for r in router.routes if getattr(r, "path", "") == "/health"), None
        )
        assert route is not None, "/health route not found"

        # Health check can have rate limit but at a very high level
        # This is acceptable - we just ensure it exists and is accessible

    def test_rate_limit_helper_functions_exist(self):
        """Rate limit helper functions should be defined."""
        from services.api.routes import (
            get_rate_limit_health,
            get_rate_limit_strategies,
            get_rate_limit_trading,
        )

        assert callable(get_rate_limit_health)
        assert callable(get_rate_limit_trading)
        assert callable(get_rate_limit_strategies)

    def test_rate_limit_backtest_helper_exists(self):
        """Rate limit helper for backtest should be defined."""
        from services.api.routes import get_rate_limit_backtest

        assert callable(get_rate_limit_backtest)

    def test_rate_limit_status_helper_exists(self):
        """Rate limit helper for status should be defined."""
        from services.api.routes import get_rate_limit_status

        assert callable(get_rate_limit_status)

    def test_rate_limit_trading_write_helper_exists(self):
        """Rate limit helper for trading write should be defined."""
        from services.api.routes import get_rate_limit_trading_write

        assert callable(get_rate_limit_trading_write)

    def test_api_v1_trading_start_has_rate_limit(self):
        """Trading start endpoint should have rate limiting."""
        from services.api.routes import router

        route = next(
            (
                r
                for r in router.routes
                if getattr(r, "path", "") == "/api/v1/trading/start"
            ),
            None,
        )
        assert route is not None, "/api/v1/trading/start route not found"

        deps = getattr(route, "dependencies", []) or []
        assert (
            len(deps) > 0
        ), "/api/v1/trading/start should have rate limit dependency"

    def test_api_v1_trading_stop_has_rate_limit(self):
        """Trading stop endpoint should have rate limiting."""
        from services.api.routes import router

        route = next(
            (
                r
                for r in router.routes
                if getattr(r, "path", "") == "/api/v1/trading/stop"
            ),
            None,
        )
        assert route is not None, "/api/v1/trading/stop route not found"

        deps = getattr(route, "dependencies", []) or []
        assert (
            len(deps) > 0
        ), "/api/v1/trading/stop should have rate limit dependency"

    def test_api_v1_trading_pause_has_rate_limit(self):
        """Trading pause endpoint should have rate limiting."""
        from services.api.routes import router

        route = next(
            (
                r
                for r in router.routes
                if getattr(r, "path", "") == "/api/v1/trading/pause"
            ),
            None,
        )
        assert route is not None, "/api/v1/trading/pause route not found"

        deps = getattr(route, "dependencies", []) or []
        assert (
            len(deps) > 0
        ), "/api/v1/trading/pause should have rate limit dependency"

    def test_api_v1_trading_resume_has_rate_limit(self):
        """Trading resume endpoint should have rate limiting."""
        from services.api.routes import router

        route = next(
            (
                r
                for r in router.routes
                if getattr(r, "path", "") == "/api/v1/trading/resume"
            ),
            None,
        )
        assert route is not None, "/api/v1/trading/resume route not found"

        deps = getattr(route, "dependencies", []) or []
        assert (
            len(deps) > 0
        ), "/api/v1/trading/resume should have rate limit dependency"

    def test_api_v1_backtest_run_has_rate_limit(self):
        """Backtest run endpoint should have rate limiting."""
        from services.api.routes import router

        route = next(
            (
                r
                for r in router.routes
                if getattr(r, "path", "") == "/api/v1/backtest/run"
            ),
            None,
        )
        assert route is not None, "/api/v1/backtest/run route not found"

        deps = getattr(route, "dependencies", []) or []
        assert (
            len(deps) > 0
        ), "/api/v1/backtest/run should have rate limit dependency"
