"""Integration test configuration.

Provides fixtures to isolate tests from external dependencies and prevent
Prometheus metric registry pollution across tests.
"""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_llm_context_publisher():
    """Prevent LLMContextPublisher from registering Prometheus metrics in every test.

    LLMContextPublisher registers Counter/Gauge metrics in its __init__.
    Prometheus raises ValueError on duplicate timeseries in the same process.
    This fixture patches _init_llm_context_publisher so it does nothing,
    avoiding registry pollution across tests.
    """
    with patch(
        "services.trading.orchestrator.TradingOrchestrator._init_llm_context_publisher",
        return_value=None,
    ):
        yield
