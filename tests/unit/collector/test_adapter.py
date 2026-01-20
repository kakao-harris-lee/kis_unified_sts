"""Test API adapter interface."""
import pytest
from abc import ABC


def test_base_adapter_is_abstract():
    """Test BaseAPIAdapter is abstract class."""
    from shared.collector.adapter import BaseAPIAdapter

    with pytest.raises(TypeError):
        BaseAPIAdapter()


def test_mock_adapter_implements_interface():
    """Test MockAPIAdapter implements interface."""
    from shared.collector.adapter import MockAPIAdapter

    adapter = MockAPIAdapter(tick_interval=0.1)

    assert hasattr(adapter, 'connect')
    assert hasattr(adapter, 'subscribe')
    assert hasattr(adapter, 'disconnect')
