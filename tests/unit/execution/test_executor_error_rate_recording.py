"""OrderExecutor._request_json feeds the KIS error-rate tracker.

2xx = KIS reachable (success); 5xx / 429 / network exception = KIS-side infra
failure. This is the api_error_rate signal for the decoupled futures pipeline,
where OrderExecutor is the only continuous KIS REST caller.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _response_cm(status: int, body: dict):
    resp = AsyncMock()
    resp.status = status
    resp.json.return_value = body
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_executor():
    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor

    auth_manager = MagicMock()
    auth_manager.get_auth_headers.return_value = {"authorization": "Bearer x"}
    executor = OrderExecutor(
        config=ExecutionConfig(trading_mode="MOCK"), auth_manager=auth_manager
    )
    executor.session = MagicMock()
    return executor


_HEADERS = {"authorization": "Bearer x", "tr_id": "T", "custtype": "P"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,expected_error",
    [(200, False), (400, False), (429, True), (500, True), (503, True)],
)
async def test_request_json_records_outcome_by_status(status, expected_error):
    from shared.execution import executor as executor_mod

    executor = _make_executor()
    executor.session.request = MagicMock(
        return_value=_response_cm(status, {"rt_cd": "0"})
    )

    with patch.object(executor_mod, "_record_kis_api_outcome") as rec:
        data, got_status = await executor._request_json(
            "POST", "https://x/order", headers=_HEADERS, json={}
        )

    assert got_status == status
    rec.assert_called_once_with(is_error=expected_error)


@pytest.mark.asyncio
async def test_request_json_records_error_and_reraises_on_network_failure():
    from shared.execution import executor as executor_mod

    executor = _make_executor()
    boom = MagicMock()
    boom.__aenter__ = AsyncMock(side_effect=RuntimeError("network down"))
    boom.__aexit__ = AsyncMock(return_value=None)
    executor.session.request = MagicMock(return_value=boom)

    with patch.object(executor_mod, "_record_kis_api_outcome") as rec:
        with pytest.raises(RuntimeError):
            await executor._request_json(
                "POST", "https://x/order", headers=_HEADERS, json={}
            )

    rec.assert_called_once_with(is_error=True)


@pytest.mark.asyncio
async def test_record_helper_never_raises_when_tracker_unavailable():
    """The guarded helper swallows any tracker error (order path must not break)."""
    from shared.execution.executor import _record_kis_api_outcome

    with patch(
        "shared.kis.error_rate.KISApiErrorRateTracker.get_instance",
        side_effect=RuntimeError("no redis"),
    ):
        _record_kis_api_outcome(is_error=True)  # must not raise
        _record_kis_api_outcome(is_error=False)
