"""Broker throttle handling — wave-3b D-4 / D-5 / D-6.

Measured throttle shape (broker-probe artifact P-13): HTTP 500 + ``rt_cd="1"``
+ ``msg_cd="EGW00201"`` + ``초당 거래건수를 초과하였습니다``.

D-4: a throttle was blind-retried at the fixed ``retry_delay`` (1.0s) — tighter
than the 1.1s pacing that had just been refused.
D-5: the timeout cancel made exactly one call; a throttled cancel left the order
resting at the broker (observed: P-8, order 0000003144).
D-6: EGW00201 arrives as HTTP 500 and was counted as a KIS-side infra failure,
feeding the kill switch's ``api_error_rate_5min`` force-flatten signal with our
own pacing.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.execution.config import ExecutionConfig
from shared.execution.executor import KIS_THROTTLE_MSG_CD, OrderExecutor
from shared.execution.models import OrderRequest, OrderSide, OrderType

_THROTTLE_BODY = {
    "rt_cd": "1",
    "msg_cd": "EGW00201",
    "msg1": "초당 거래건수를 초과하였습니다.",
}
_BUSINESS_REJECT_BODY = {
    "rt_cd": "1",
    "msg_cd": "40570000",
    "msg1": "모의투자 주문가능금액이 부족합니다.",
}


def _stock_order() -> OrderRequest:
    return OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=70000.0,
    )


# ---------------------------------------------------------------------------
# D-4 — throttle backs off instead of retrying at the fixed retry_delay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_throttle_uses_backoff_not_the_fixed_retry_delay(caplog):
    config = ExecutionConfig(
        trading_mode="MOCK",
        rate_limit_key="stock",
        max_retries=3,
        retry_delay=1.0,
        throttle_backoff_initial_seconds=2.0,
        throttle_backoff_multiplier=2.0,
        throttle_backoff_max_seconds=30.0,
    )
    executor = OrderExecutor(config)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "VTTC0012U"})
    executor._request_json = AsyncMock(return_value=(_THROTTLE_BODY, 500))

    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)

    with caplog.at_level(logging.WARNING, logger="shared.execution.executor"):
        with patch("shared.execution.executor.asyncio.sleep", _sleep):
            resp = await executor.execute_order(_stock_order())

    assert resp.success is False
    # 2 sleeps for 3 attempts, geometric — and never the 1.0s retry_delay.
    assert slept == [2.0, 4.0]
    assert 1.0 not in slept
    assert any(KIS_THROTTLE_MSG_CD in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_throttle_backoff_is_capped():
    config = ExecutionConfig(
        trading_mode="MOCK",
        max_retries=4,
        throttle_backoff_initial_seconds=2.0,
        throttle_backoff_multiplier=10.0,
        throttle_backoff_max_seconds=5.0,
    )
    executor = OrderExecutor(config)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "VTTC0012U"})
    executor._request_json = AsyncMock(return_value=(_THROTTLE_BODY, 500))

    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)

    with patch("shared.execution.executor.asyncio.sleep", _sleep):
        await executor.execute_order(_stock_order())

    assert slept == [2.0, 5.0, 5.0]


@pytest.mark.asyncio
async def test_non_throttle_rejection_still_uses_retry_delay():
    """Negative control: ordinary rejects keep the configured retry delay."""
    config = ExecutionConfig(
        trading_mode="MOCK",
        max_retries=3,
        retry_delay=1.0,
        throttle_backoff_initial_seconds=2.0,
    )
    executor = OrderExecutor(config)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "VTTC0012U"})
    executor._request_json = AsyncMock(return_value=(_BUSINESS_REJECT_BODY, 200))

    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)

    with patch("shared.execution.executor.asyncio.sleep", _sleep):
        resp = await executor.execute_order(_stock_order())

    assert resp.success is False
    assert slept == [1.0, 1.0]


@pytest.mark.asyncio
async def test_throttle_code_reaches_the_caller_as_a_typed_field():
    """The throttle is a structured value, not a substring of ``message``."""
    config = ExecutionConfig(trading_mode="MOCK")
    executor = OrderExecutor(config)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "VTTC0012U"})
    executor._request_json = AsyncMock(return_value=(_THROTTLE_BODY, 500))

    resp = await executor._send_kis_stock_order(_stock_order(), is_mock=True)

    assert resp.broker_msg_cd == KIS_THROTTLE_MSG_CD


@pytest.mark.asyncio
async def test_throttle_detected_through_the_real_non_json_branch():
    """Drive `_request_json`'s non-JSON branch instead of mocking it away.

    That branch assigns the ENTIRE response body to ``msg1``. Mocking
    ``_request_json`` skips it and only re-asserts the helper's own matcher, so
    this goes through ``session.request`` with a body that fails ``.json()``.
    """
    from shared.execution import executor as executor_mod

    executor = _request_json_executor()
    resp_obj = AsyncMock()
    resp_obj.status = 500
    resp_obj.json.side_effect = ValueError("not json")
    resp_obj.text.return_value = (
        "<html><body>error EGW00201 초당 거래건수를 초과하였습니다.</body></html>"
    )
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp_obj)
    cm.__aexit__ = AsyncMock(return_value=None)
    executor.session.request = MagicMock(return_value=cm)

    with patch.object(executor_mod, "_record_kis_api_outcome") as rec:
        data, status = await executor._request_json(
            "POST", "https://x/order", headers=_HEADERS, json={}
        )

    # The non-JSON branch really ran: the raw body landed in msg1.
    assert "EGW00201" in data["msg1"]
    assert status == 500
    assert executor._reject_msg_cd(data) == KIS_THROTTLE_MSG_CD
    # ...and the throttle exclusion applied off that reconstructed body.
    rec.assert_called_once_with(is_error=False)


@pytest.mark.asyncio
async def test_unanchored_mention_of_the_code_is_not_treated_as_a_throttle():
    """Negative: a body merely CONTAINING the token must not be excluded.

    ``msg1`` can hold an entire gateway error page. A bare substring test would
    silently exclude any page that mentions the code — e.g. inside a longer
    identifier — turning a real outage into an invisible one.
    """
    from shared.execution import executor as executor_mod

    executor = _request_json_executor()
    resp_obj = AsyncMock()
    resp_obj.status = 500
    resp_obj.json.side_effect = ValueError("not json")
    resp_obj.text.return_value = "<html>trace id XEGW002019 gateway failure</html>"
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp_obj)
    cm.__aexit__ = AsyncMock(return_value=None)
    executor.session.request = MagicMock(return_value=cm)

    with patch.object(executor_mod, "_record_kis_api_outcome") as rec:
        data, _ = await executor._request_json(
            "POST", "https://x/order", headers=_HEADERS, json={}
        )

    assert executor._reject_msg_cd(data) != KIS_THROTTLE_MSG_CD
    rec.assert_called_once_with(is_error=True)


@pytest.mark.asyncio
async def test_throttle_detected_when_the_code_is_only_in_msg1():
    """Anchored msg1 fallback still catches a genuinely code-shaped mention."""
    config = ExecutionConfig(trading_mode="MOCK")
    executor = OrderExecutor(config)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "VTTC0012U"})
    executor._request_json = AsyncMock(
        return_value=({"rt_cd": "500", "msg1": "<html>EGW00201 ...</html>"}, 500)
    )

    resp = await executor._send_kis_stock_order(_stock_order(), is_mock=True)

    assert resp.broker_msg_cd == KIS_THROTTLE_MSG_CD


# ---------------------------------------------------------------------------
# D-5 — bounded cancel retry
# ---------------------------------------------------------------------------


async def _cancel(executor: OrderExecutor):
    return await executor._cancel_futures_order(
        order_no="0000003144", cancel_quantity=1, is_mock=False, is_night=False
    )


def _cancel_executor(**overrides) -> OrderExecutor:
    base = {
        "trading_mode": "REAL",
        "rate_limit_key": "futures",
        "account_no": "5011064801",
        "futures_cancel_max_attempts": 3,
        "futures_cancel_retry_delay_seconds": 0.3,
        "throttle_backoff_initial_seconds": 2.0,
        "throttle_backoff_multiplier": 2.0,
    }
    base.update(overrides)
    executor = OrderExecutor(ExecutionConfig(**base))
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO1103U"})
    return executor


@pytest.mark.asyncio
async def test_throttled_cancel_is_retried_with_backoff(caplog):
    executor = _cancel_executor()
    executor._request_json = AsyncMock(return_value=(_THROTTLE_BODY, 500))

    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)

    with caplog.at_level(logging.WARNING, logger="shared.execution.executor"):
        with patch("shared.execution.executor.asyncio.sleep", _sleep):
            resp = await _cancel(executor)

    assert resp.success is False
    assert executor._request_json.await_count == 3
    assert slept == [2.0, 4.0]
    assert resp.broker_msg_cd == KIS_THROTTLE_MSG_CD
    assert any("may still" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_cancel_retry_succeeds_on_the_second_attempt():
    executor = _cancel_executor()
    executor._request_json = AsyncMock(
        side_effect=[
            (_THROTTLE_BODY, 500),
            ({"rt_cd": "0", "msg1": "정상처리", "output": {"ODNO": "0000003145"}}, 200),
        ]
    )

    with patch("shared.execution.executor.asyncio.sleep", AsyncMock()):
        resp = await _cancel(executor)

    assert resp.success is True
    assert executor._request_json.await_count == 2


@pytest.mark.asyncio
async def test_deterministic_cancel_reject_is_not_retried():
    """ "취소할 수량이 없습니다" cannot change on retry — do not burn budget."""
    executor = _cancel_executor()
    executor._request_json = AsyncMock(
        return_value=(
            {
                "rt_cd": "1",
                "msg_cd": "40600000",
                "msg1": "모의투자 정정/취소할 수량이 없습니다.",
            },
            200,
        )
    )

    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)

    with patch("shared.execution.executor.asyncio.sleep", _sleep):
        resp = await _cancel(executor)

    assert resp.success is False
    assert executor._request_json.await_count == 1
    assert slept == []


@pytest.mark.asyncio
async def test_cancel_5xx_retry_uses_the_plain_cancel_delay():
    executor = _cancel_executor(futures_cancel_max_attempts=2)
    executor._request_json = AsyncMock(
        return_value=({"rt_cd": "500", "msg1": "Internal Server Error"}, 503)
    )

    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)

    with patch("shared.execution.executor.asyncio.sleep", _sleep):
        resp = await _cancel(executor)

    assert resp.success is False
    assert executor._request_json.await_count == 2
    assert slept == [0.3]


@pytest.mark.asyncio
async def test_cancel_attempts_are_bounded_by_config():
    executor = _cancel_executor(futures_cancel_max_attempts=1)
    executor._request_json = AsyncMock(return_value=(_THROTTLE_BODY, 500))

    with patch("shared.execution.executor.asyncio.sleep", AsyncMock()):
        await _cancel(executor)

    assert executor._request_json.await_count == 1


# ---------------------------------------------------------------------------
# D-6 — the self-inflicted throttle must not feed the kill switch
# ---------------------------------------------------------------------------


def _response_cm(status: int, body: dict):
    resp = AsyncMock()
    resp.status = status
    resp.json.return_value = body
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _request_json_executor() -> OrderExecutor:
    auth_manager = MagicMock()
    auth_manager.get_auth_headers.return_value = {"authorization": "Bearer x"}
    executor = OrderExecutor(
        config=ExecutionConfig(trading_mode="MOCK"), auth_manager=auth_manager
    )
    executor.session = MagicMock()
    return executor


_HEADERS = {"authorization": "Bearer x", "tr_id": "T", "custtype": "P"}


@pytest.mark.asyncio
async def test_throttle_500_does_not_increment_the_infra_error_signal():
    from shared.execution import executor as executor_mod

    executor = _request_json_executor()
    executor.session.request = MagicMock(return_value=_response_cm(500, _THROTTLE_BODY))

    with patch.object(executor_mod, "_record_kis_api_outcome") as rec:
        _, status = await executor._request_json(
            "POST", "https://x/order", headers=_HEADERS, json={}
        )

    assert status == 500
    rec.assert_called_once_with(is_error=False)


@pytest.mark.asyncio
async def test_genuine_500_still_increments_the_infra_error_signal():
    """Negative control: D-6 must not blind the kill switch to real outages."""
    from shared.execution import executor as executor_mod

    executor = _request_json_executor()
    executor.session.request = MagicMock(
        return_value=_response_cm(500, {"rt_cd": "1", "msg1": "Internal Server Error"})
    )

    with patch.object(executor_mod, "_record_kis_api_outcome") as rec:
        await executor._request_json(
            "POST", "https://x/order", headers=_HEADERS, json={}
        )

    rec.assert_called_once_with(is_error=True)
