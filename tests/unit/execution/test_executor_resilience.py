"""Executor resilience gaps found in adversarial review attempt 1.

#3 — the cancel-SUCCESS branch asserted a clean ``filled_qty=0`` even when no
     poll ever answered. A successful cancel establishes "not FULLY filled";
     it does not establish "filled nothing", because `cancel_qty` is the whole
     order quantity whenever nothing was ever measured.
#4 — a transport error escaped the cancel loop and the fill query, unwinding
     the whole path and taking the D-2 re-query, the unknown flag and the
     "may still be resting" ERROR with it.
#5 — a throttle STORM (gateway answering EGW00201 to everything) left no
     signal at all, since throttles are excluded from api_error_rate_5min.
#6 — the cancel shared a rate-limit bucket with the fill polls that decided
     the cancel was needed.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from shared.execution.config import ExecutionConfig
from shared.execution.executor import (
    KIS_THROTTLE_MSG_CD,
    FillQueryOutcome,
    OrderExecutor,
    _FuturesFillStatus,
)
from shared.execution.models import OrderRequest, OrderResponse, OrderSide, OrderType

_ORDER_NO = "0000003144"
_THROTTLE_BODY = {
    "rt_cd": "1",
    "msg_cd": "EGW00201",
    "msg1": "초당 거래건수를 초과하였습니다.",
}


def _config(**overrides) -> ExecutionConfig:
    base = {
        "trading_mode": "REAL",
        "rate_limit_key": "futures",
        "account_no": "5011064801",
        "futures_fill_check_poll_interval_seconds": 0.05,
        "futures_fill_check_timeout_seconds": 0.1,
        "futures_auto_cancel_unfilled": True,
    }
    base.update(overrides)
    return ExecutionConfig(**base)


def _order(quantity: int = 1) -> OrderRequest:
    return OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=330.5,
    )


# ---------------------------------------------------------------------------
# #3 — a successful cancel does not license a measured zero
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_success_after_unanswered_polls_reports_unknown():
    """No poll answered, cancel OK, re-query answers ABSENCE → not a clean zero.

    The re-query must be NOT_PRESENT, not QUERY_FAILED: with QUERY_FAILED the
    weaker ``fill_state_unknown=refreshed.query_failed`` rule also yields True,
    so the test would not discriminate. The gap is exactly the case where the
    re-query succeeds but supplies no row while no poll ever measured anything
    — `cancel_qty` was the FULL quantity, so the cancel may have removed the
    remainder of a partial fill we never saw.
    """
    executor = OrderExecutor(_config())
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(success=True, message="cancel_ok")
    )

    # Keyed on whether the cancel has run, NOT a fixed side_effect list. A list
    # assumes an exact poll count; if the machine is loaded and only one poll
    # runs, the re-query consumes the second QUERY_FAILED element and the test
    # keeps PASSING while silently no longer discriminating.
    async def _polls_fail_then_requery_answers_absence(**_):
        if executor._cancel_futures_order.await_count:
            return _FuturesFillStatus(
                outcome=FillQueryOutcome.NOT_PRESENT, order_no=_ORDER_NO, order_qty=3
            )
        return _FuturesFillStatus(
            outcome=FillQueryOutcome.QUERY_FAILED, order_no=_ORDER_NO, order_qty=3
        )

    executor._inquire_futures_fill_status = AsyncMock(
        side_effect=_polls_fail_then_requery_answers_absence
    )

    resp = await executor._await_futures_fill_or_cancel(
        order=_order(quantity=3), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert resp.filled_qty == 0
    assert resp.fill_state_unknown is True


@pytest.mark.asyncio
async def test_cancel_success_with_a_failed_requery_also_reports_unknown():
    """The other half: the confirming re-query itself going unanswered."""
    executor = OrderExecutor(_config())
    executor._inquire_futures_fill_status = AsyncMock(
        return_value=_FuturesFillStatus(
            outcome=FillQueryOutcome.QUERY_FAILED, order_no=_ORDER_NO, order_qty=3
        )
    )
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(success=True, message="cancel_ok")
    )

    resp = await executor._await_futures_fill_or_cancel(
        order=_order(quantity=3), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert resp.fill_state_unknown is True


@pytest.mark.asyncio
async def test_cancel_success_after_unanswered_polls_but_answered_requery_is_known():
    """The re-query supplying a measurement resolves it — no over-sealing."""
    executor = OrderExecutor(_config())

    async def _fail_then_answer(**_):
        if executor._cancel_futures_order.await_count:
            return _FuturesFillStatus(
                outcome=FillQueryOutcome.FOUND,
                order_no=_ORDER_NO,
                order_qty=3,
                filled_qty=0,
                remaining_qty=0,
            )
        return _FuturesFillStatus(
            outcome=FillQueryOutcome.QUERY_FAILED, order_no=_ORDER_NO, order_qty=3
        )

    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(success=True, message="cancel_ok")
    )
    executor._inquire_futures_fill_status = AsyncMock(side_effect=_fail_then_answer)

    resp = await executor._await_futures_fill_or_cancel(
        order=_order(quantity=3), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert resp.filled_qty == 0
    assert resp.fill_state_unknown is False


@pytest.mark.asyncio
async def test_cancel_success_after_measured_polls_stays_known():
    """Negative control: polls that DID answer keep the result measured."""
    executor = OrderExecutor(_config())
    executor._inquire_futures_fill_status = AsyncMock(
        return_value=_FuturesFillStatus(
            outcome=FillQueryOutcome.FOUND,
            order_no=_ORDER_NO,
            order_qty=1,
            filled_qty=0,
            remaining_qty=1,
        )
    )
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(success=True, message="cancel_ok")
    )

    resp = await executor._await_futures_fill_or_cancel(
        order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert resp.fill_state_unknown is False


# ---------------------------------------------------------------------------
# #4 — transport errors are outcomes, not escapes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transport_error_in_fill_query_is_query_failed_not_an_exception(caplog):
    executor = OrderExecutor(_config())
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    executor._request_json = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("connection reset")
    )

    with caplog.at_level(logging.WARNING, logger="shared.execution.executor"):
        status = await executor._inquire_futures_fill_status(
            order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
        )

    assert status.outcome is FillQueryOutcome.QUERY_FAILED
    assert any("transport" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_transport_timeout_in_fill_query_is_query_failed():
    executor = OrderExecutor(_config())
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    executor._request_json = AsyncMock(side_effect=TimeoutError("read timeout"))

    status = await executor._inquire_futures_fill_status(
        order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert status.outcome is FillQueryOutcome.QUERY_FAILED


@pytest.mark.asyncio
async def test_transport_error_in_cancel_is_retried_and_never_propagates(caplog):
    executor = OrderExecutor(_config(futures_cancel_max_attempts=3))
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO1103U"})
    executor._request_json = AsyncMock(side_effect=OSError("network down"))

    with caplog.at_level(logging.WARNING, logger="shared.execution.executor"):
        with patch("shared.execution.executor.asyncio.sleep", AsyncMock()):
            resp = await executor._cancel_futures_order(
                order_no=_ORDER_NO, cancel_quantity=1, is_mock=False, is_night=False
            )

    assert resp.success is False
    assert executor._request_json.await_count == 3
    assert "TRANSPORT" in resp.message
    # The diagnostics that used to be lost with the exception:
    assert any("may still" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_transport_error_on_cancel_still_reaches_the_d2_requery():
    """The whole point of #4: the recovery path must still run."""
    executor = OrderExecutor(_config())
    executor._cancel_futures_order = AsyncMock(side_effect=None)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO1103U"})

    inquiries_after_cancel: list[bool] = []

    async def _record(**_):
        inquiries_after_cancel.append(executor._cancel_futures_order.await_count > 0)
        return _FuturesFillStatus(
            outcome=FillQueryOutcome.NOT_PRESENT, order_no=_ORDER_NO, order_qty=1
        )

    executor._inquire_futures_fill_status = AsyncMock(side_effect=_record)
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(
            success=False, message="[TRANSPORT] cancel request failed: network down"
        )
    )

    resp = await executor._await_futures_fill_or_cancel(
        order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert any(inquiries_after_cancel), "re-query must survive a transport failure"
    assert resp.fill_state_unknown is True


@pytest.mark.asyncio
async def test_cancel_transport_failure_then_success():
    executor = OrderExecutor(_config(futures_cancel_max_attempts=3))
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO1103U"})
    executor._request_json = AsyncMock(
        side_effect=[
            aiohttp.ClientConnectionError("reset"),
            ({"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "1"}}, 200),
        ]
    )

    with patch("shared.execution.executor.asyncio.sleep", AsyncMock()):
        resp = await executor._cancel_futures_order(
            order_no=_ORDER_NO, cancel_quantity=1, is_mock=False, is_night=False
        )

    assert resp.success is True
    assert executor._request_json.await_count == 2


# ---------------------------------------------------------------------------
# #5 — throttle storm signal
# ---------------------------------------------------------------------------


def _response_cm(status: int, body: dict):
    resp = AsyncMock()
    resp.status = status
    resp.json.return_value = body
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _request_json_executor(**overrides) -> OrderExecutor:
    auth_manager = MagicMock()
    auth_manager.get_auth_headers.return_value = {"authorization": "Bearer x"}
    executor = OrderExecutor(
        config=ExecutionConfig(trading_mode="MOCK", **overrides),
        auth_manager=auth_manager,
    )
    executor.session = MagicMock()
    return executor


_HEADERS = {"authorization": "Bearer x", "tr_id": "T", "custtype": "P"}


@pytest.mark.asyncio
async def test_sustained_throttles_raise_a_storm_alert(caplog):
    """Excluding throttles from api_error_rate must not silence a dead gateway."""
    executor = _request_json_executor(throttle_storm_alert_threshold=3)
    executor.session.request = MagicMock(return_value=_response_cm(500, _THROTTLE_BODY))

    with caplog.at_level(logging.ERROR, logger="shared.execution.executor"):
        for _ in range(3):
            await executor._request_json(
                "POST", "https://x/order", headers=_HEADERS, json={}
            )

    assert executor._throttle_streak == 3
    assert any("THROTTLE STORM" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_throttle_streak_below_threshold_does_not_alert(caplog):
    executor = _request_json_executor(throttle_storm_alert_threshold=5)
    executor.session.request = MagicMock(return_value=_response_cm(500, _THROTTLE_BODY))

    with caplog.at_level(logging.ERROR, logger="shared.execution.executor"):
        for _ in range(4):
            await executor._request_json(
                "POST", "https://x/order", headers=_HEADERS, json={}
            )

    assert not any("THROTTLE STORM" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_a_single_good_response_resets_the_storm_streak():
    executor = _request_json_executor(throttle_storm_alert_threshold=3)
    executor.session.request = MagicMock(return_value=_response_cm(500, _THROTTLE_BODY))
    for _ in range(2):
        await executor._request_json(
            "POST", "https://x/order", headers=_HEADERS, json={}
        )
    assert executor._throttle_streak == 2

    executor.session.request = MagicMock(
        return_value=_response_cm(200, {"rt_cd": "0", "msg1": "ok"})
    )
    await executor._request_json("POST", "https://x/order", headers=_HEADERS, json={})

    assert executor._throttle_streak == 0


# ---------------------------------------------------------------------------
# #6 — the cancel does not share a bucket with its own fill polls
# ---------------------------------------------------------------------------


def test_cancel_uses_a_separate_rate_limit_bucket():
    executor = OrderExecutor(
        _config(redis_url="redis://localhost:6379/1", rate_limit_key="futures")
    )

    assert executor._rate_limiter.key == "kis:ratelimit:futures"
    assert executor._cancel_rate_limiter is not None
    assert executor._cancel_rate_limiter.key == "kis:ratelimit:futures-cancel"
    assert executor._cancel_rate_limiter.key != executor._rate_limiter.key


def test_cancel_bucket_suffix_is_config_driven():
    executor = OrderExecutor(
        _config(
            redis_url="redis://localhost:6379/1",
            rate_limit_key="futures",
            cancel_rate_limit_suffix="-safety",
        )
    )

    assert executor._cancel_rate_limiter.key == "kis:ratelimit:futures-safety"


@pytest.mark.asyncio
async def test_cancel_acquires_from_the_cancel_bucket_not_the_main_one():
    executor = OrderExecutor(_config())
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO1103U"})
    main = AsyncMock()
    cancel_bucket = AsyncMock()
    executor._rate_limiter = main
    executor._cancel_rate_limiter = cancel_bucket
    executor.session = MagicMock()
    executor.session.request = MagicMock(
        return_value=_response_cm(200, {"rt_cd": "0", "msg1": "ok", "output": {}})
    )

    await executor._cancel_futures_order(
        order_no=_ORDER_NO, cancel_quantity=1, is_mock=False, is_night=False
    )

    cancel_bucket.acquire.assert_awaited_once()
    main.acquire.assert_not_awaited()


@pytest.mark.asyncio
async def test_fill_poll_acquires_with_the_short_yield_timeout():
    """Polls yield the bucket instead of blocking a later safety operation."""
    executor = OrderExecutor(
        _config(futures_fill_check_rate_limit_timeout_seconds=0.25)
    )
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    main = AsyncMock()
    executor._rate_limiter = main
    executor.session = MagicMock()
    executor.session.request = MagicMock(
        return_value=_response_cm(200, {"rt_cd": "0", "output1": []})
    )

    await executor._inquire_futures_fill_status(
        order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert main.acquire.await_count >= 1
    for call in main.acquire.await_args_list:
        assert call.kwargs["timeout"] == 0.25
        assert call.kwargs["timeout"] < executor.config.rate_limit_timeout


@pytest.mark.asyncio
async def test_exhausted_poll_budget_surfaces_as_query_failed_not_unfilled():
    """A rate-limited poll is an unanswered query, never 'no fill'."""
    from shared.execution.exceptions import RateLimitExceeded

    executor = OrderExecutor(_config())
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    limiter = AsyncMock()
    limiter.acquire.side_effect = RateLimitExceeded("no tokens")
    executor._rate_limiter = limiter

    status = await executor._inquire_futures_fill_status(
        order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert status.outcome is FillQueryOutcome.QUERY_FAILED
    assert status.outcome is not FillQueryOutcome.NOT_PRESENT


@pytest.mark.asyncio
async def test_throttled_order_response_carries_the_code(caplog):
    """Sanity anchor for the storm counter's input."""
    executor = _request_json_executor()
    executor.session.request = MagicMock(return_value=_response_cm(500, _THROTTLE_BODY))

    data, _ = await executor._request_json(
        "POST", "https://x/order", headers=_HEADERS, json={}
    )

    assert executor._reject_msg_cd(data) == KIS_THROTTLE_MSG_CD
