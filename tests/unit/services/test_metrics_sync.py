from types import SimpleNamespace
from unittest.mock import Mock

from services.trading.metrics_sync import sync_open_positions_metric


def test_sync_open_positions_metric_no_metrics_no_action():
    tracker = SimpleNamespace(positions=[SimpleNamespace(is_open=True)])

    assert sync_open_positions_metric(None, tracker) is None


def test_sync_open_positions_metric_no_position_tracker_no_action():
    metrics = Mock()

    assert sync_open_positions_metric(metrics, None) is None
    metrics.record_position_change.assert_not_called()


def test_sync_open_positions_metric_prefers_tracker_position_count():
    metrics = Mock()
    tracker = SimpleNamespace(
        position_count=3,
        positions=[
            SimpleNamespace(is_open=True),
            SimpleNamespace(is_open=False),
        ],
    )

    assert sync_open_positions_metric(metrics, tracker) == 3
    metrics.record_position_change.assert_called_once_with(3)


def test_sync_open_positions_metric_counts_open_and_default_open_positions():
    metrics = Mock()
    tracker = SimpleNamespace(
        positions=[
            SimpleNamespace(is_open=True),
            SimpleNamespace(),
            SimpleNamespace(is_open=False),
        ]
    )

    assert sync_open_positions_metric(metrics, tracker) == 2
    metrics.record_position_change.assert_called_once_with(2)


def test_sync_open_positions_metric_ignores_closed_positions():
    metrics = Mock()
    tracker = SimpleNamespace(
        positions=[
            SimpleNamespace(is_open=False),
            SimpleNamespace(is_open=False),
        ]
    )

    assert sync_open_positions_metric(metrics, tracker) == 0
    metrics.record_position_change.assert_called_once_with(0)
