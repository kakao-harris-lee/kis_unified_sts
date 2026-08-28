"""Fill-status query outcome tests — wave-3b D-1 / D-2 / D-7.

D-1: the fill-status query used to collapse three different situations into one
silent ``found=False`` — "the broker throttled us", "the broker answered and the
row is absent", and "the order really is unfilled". Downstream could not tell
them apart and there was no log line at all.

D-2: on fill-check timeout the auto-cancel fired; when the broker REJECTED the
cancel (because the order had already filled) the executor returned
``filled_qty=0`` without re-querying, while the success path did re-query. That
asymmetry reported a flat book while the broker held a position.

D-7: the query sends empty continuation keys and never read the response's — a
truncated page would have been undetectable.
"""

import logging

import pytest

from shared.execution.config import ExecutionConfig
from shared.execution.executor import (
    FillQueryOutcome,
    OrderExecutor,
    _FuturesFillStatus,
)
from shared.execution.models import OrderRequest, OrderResponse, OrderSide, OrderType

_ORDER_NO = "0000003144"


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


async def _inquire(executor: OrderExecutor) -> _FuturesFillStatus:
    return await executor._inquire_futures_fill_status(
        order=_order(),
        order_no=_ORDER_NO,
        is_mock=False,
        is_night=False,
    )


def _row(filled_qty: int, remaining_qty: int) -> dict:
    return {
        "odno": _ORDER_NO,
        "tot_ccld_qty": str(filled_qty),
        "qty": str(remaining_qty),
        "ord_qty": "1",
        "avg_idx": "330.50",
        "rjct_qty": "0",
        "ingr_trad_rjct_rson_name": "",
    }


# ---------------------------------------------------------------------------
# D-1 — the three outcomes are distinguishable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fill_query_found_is_a_measurement():
    """Happy path: the row is present → FOUND with the broker's quantities."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config())
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    executor._request_json = AsyncMock(
        return_value=({"rt_cd": "0", "output1": [_row(1, 0)]}, 200)
    )

    status = await _inquire(executor)

    assert status.outcome is FillQueryOutcome.FOUND
    assert status.found is True
    assert status.query_failed is False
    assert status.filled_qty == 1


@pytest.mark.asyncio
async def test_fill_query_not_present_is_authoritative_absence():
    """The broker answered and the order row is absent → NOT_PRESENT."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config())
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    executor._request_json = AsyncMock(
        return_value=({"rt_cd": "0", "output1": []}, 200)
    )

    status = await _inquire(executor)

    assert status.outcome is FillQueryOutcome.NOT_PRESENT
    assert status.found is False
    assert status.query_failed is False
    assert status.filled_qty == 0


@pytest.mark.asyncio
async def test_fill_query_throttled_is_query_failed_not_unfilled(caplog):
    """A throttled query must NOT present as "no fill".

    Measured throttle shape (broker-probe P-13): HTTP 500 + rt_cd "1" +
    msg_cd EGW00201.
    """
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config())
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    executor._request_json = AsyncMock(
        return_value=(
            {
                "rt_cd": "1",
                "msg_cd": "EGW00201",
                "msg1": "초당 거래건수를 초과하였습니다.",
            },
            500,
        )
    )

    with caplog.at_level(logging.WARNING, logger="shared.execution.executor"):
        status = await _inquire(executor)

    assert status.outcome is FillQueryOutcome.QUERY_FAILED
    # The whole point: QUERY_FAILED is not NOT_PRESENT.
    assert status.outcome is not FillQueryOutcome.NOT_PRESENT
    assert status.found is False
    assert status.query_failed is True
    # D-1: the function used to contain no logger call at all.
    assert any("query FAILED" in r.message for r in caplog.records)
    assert any("EGW00201" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_fill_query_missing_auth_headers_is_query_failed():
    """No auth headers = no answer from the broker → QUERY_FAILED."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config())
    executor._build_auth_headers = AsyncMock(return_value=None)
    executor._request_json = AsyncMock()

    status = await _inquire(executor)

    assert status.outcome is FillQueryOutcome.QUERY_FAILED
    executor._request_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_fill_query_partial_failure_of_the_date_walk_fails_closed():
    """One unanswered leg poisons the absence: fail closed to QUERY_FAILED.

    Today's query is throttled, yesterday's answers with no row. We did not see
    the whole picture, so the absence is not evidence of "no fill".
    """
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config())
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    executor._request_json = AsyncMock(
        side_effect=[
            ({"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "초당 거래건수"}, 500),
            ({"rt_cd": "0", "output1": []}, 200),
        ]
    )

    status = await _inquire(executor)

    assert status.outcome is FillQueryOutcome.QUERY_FAILED


@pytest.mark.asyncio
async def test_timeout_with_failed_query_flags_unknown_fill_state():
    """The caller must be able to tell 0-because-unknown from 0-because-unfilled."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config(futures_auto_cancel_unfilled=False))
    executor._inquire_futures_fill_status = AsyncMock(
        return_value=_FuturesFillStatus(
            outcome=FillQueryOutcome.QUERY_FAILED,
            order_no=_ORDER_NO,
            order_qty=1,
        )
    )

    resp = await executor._await_futures_fill_or_cancel(
        order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert resp.success is False
    assert resp.filled_qty == 0
    assert resp.fill_state_unknown is True


@pytest.mark.asyncio
async def test_timeout_with_authoritative_absence_is_not_flagged_unknown():
    """Negative control: an answered "no row" is real evidence, not unknown."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config(futures_auto_cancel_unfilled=False))
    executor._inquire_futures_fill_status = AsyncMock(
        return_value=_FuturesFillStatus(
            outcome=FillQueryOutcome.NOT_PRESENT,
            order_no=_ORDER_NO,
            order_qty=1,
        )
    )

    resp = await executor._await_futures_fill_or_cancel(
        order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert resp.success is False
    assert resp.fill_state_unknown is False


# ---------------------------------------------------------------------------
# D-2 — cancel-failure re-query
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejected_cancel_reports_the_true_fill_not_a_flat_book(caplog):
    """Order filled → fill check timed out → cancel rejected → report the fill.

    This is the capital-risk case: the broker rejects the cancel with
    "정정/취소할 수량이 없습니다" precisely BECAUSE the order already filled.
    The old code returned filled_qty=0 here, which downstream turned into
    "missed" — no protective exit armed against a live position.
    """
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config())
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(
            success=False,
            message="[1] 모의투자 정정/취소할 수량이 없습니다.",
        )
    )

    # Every poll before the deadline sees nothing; only the post-cancel
    # re-query reveals the fill.
    async def _poll_then_requery(**_):
        if executor._cancel_futures_order.await_count:
            return _FuturesFillStatus(
                outcome=FillQueryOutcome.FOUND,
                order_no=_ORDER_NO,
                order_qty=1,
                filled_qty=1,
                remaining_qty=0,
                avg_fill_price=330.5,
            )
        return _FuturesFillStatus(
            outcome=FillQueryOutcome.NOT_PRESENT, order_no=_ORDER_NO, order_qty=1
        )

    executor._inquire_futures_fill_status = AsyncMock(side_effect=_poll_then_requery)

    with caplog.at_level(logging.WARNING, logger="shared.execution.executor"):
        resp = await executor._await_futures_fill_or_cancel(
            order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
        )

    executor._cancel_futures_order.assert_awaited_once()
    # The bug: filled_qty=0 while the broker holds a position.
    assert resp.filled_qty == 1
    assert resp.filled_price == 330.5
    assert resp.fill_state_unknown is False
    # Fully filled: report it as a fill so downstream arms a protective exit.
    assert resp.success is True
    assert any(
        "cancel rejected because the order had filled" in r.getMessage()
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_rejected_cancel_re_queries_like_the_success_path():
    """The asymmetry itself: BOTH cancel outcomes must re-query.

    Asserts ORDERING, not a call count. A count assertion is satisfied by the
    poll loop alone (timeout/poll_interval >= 2 calls), so it passes even with
    the re-query removed entirely — it tests the config, not the code.
    """
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config())
    # Record whether the cancel had already been awaited at each inquire.
    inquiries_after_cancel: list[bool] = []

    async def _record(**_):
        inquiries_after_cancel.append(executor._cancel_futures_order.await_count > 0)
        return _FuturesFillStatus(
            outcome=FillQueryOutcome.NOT_PRESENT, order_no=_ORDER_NO, order_qty=1
        )

    executor._inquire_futures_fill_status = AsyncMock(side_effect=_record)
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(success=False, message="[1] cancel rejected")
    )

    await executor._await_futures_fill_or_cancel(
        order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    executor._cancel_futures_order.assert_awaited_once()
    assert any(inquiries_after_cancel), (
        "a rejected cancel must be followed by a fill-status re-query; every "
        f"inquire happened before the cancel ({inquiries_after_cancel})"
    )


@pytest.mark.asyncio
async def test_rejected_cancel_with_unresolved_requery_flags_unknown(caplog):
    """Cancel rejected AND the re-query failed → unknown, never a clean zero."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config())
    executor._inquire_futures_fill_status = AsyncMock(
        return_value=_FuturesFillStatus(
            outcome=FillQueryOutcome.QUERY_FAILED, order_no=_ORDER_NO, order_qty=1
        )
    )
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(
            success=False,
            message="[1] 초당 거래건수를 초과하였습니다.",
            broker_msg_cd="EGW00201",
        )
    )

    with caplog.at_level(logging.WARNING, logger="shared.execution.executor"):
        resp = await executor._await_futures_fill_or_cancel(
            order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
        )

    assert resp.success is False
    assert resp.fill_state_unknown is True
    assert resp.broker_msg_cd == "EGW00201"
    assert any(
        "cancel rejected AND fill state unresolved" in r.getMessage()
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_partial_fill_on_rejected_cancel_reports_the_partial_quantity():
    """Long/short-symmetric partial: report what actually executed."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config())

    async def _poll_then_requery(**_):
        if executor._cancel_futures_order.await_count:
            return _FuturesFillStatus(
                outcome=FillQueryOutcome.FOUND,
                order_no=_ORDER_NO,
                order_qty=3,
                filled_qty=2,
                remaining_qty=1,
                avg_fill_price=330.5,
            )
        return _FuturesFillStatus(
            outcome=FillQueryOutcome.NOT_PRESENT, order_no=_ORDER_NO, order_qty=3
        )

    executor._inquire_futures_fill_status = AsyncMock(side_effect=_poll_then_requery)
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(success=False, message="[1] cancel rejected")
    )

    resp = await executor._await_futures_fill_or_cancel(
        order=_order(quantity=3), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert resp.filled_qty == 2
    # Not fully filled → not a success, but the quantity is truthful and the
    # state is resolved (the re-query answered).
    assert resp.success is False
    assert resp.fill_state_unknown is False


@pytest.mark.asyncio
async def test_successful_cancel_path_still_reports_the_refreshed_fill():
    """Regression guard: the success path behaviour is unchanged."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config())

    async def _poll_then_requery(**_):
        if executor._cancel_futures_order.await_count:
            return _FuturesFillStatus(
                outcome=FillQueryOutcome.FOUND,
                order_no=_ORDER_NO,
                order_qty=1,
                filled_qty=0,
                remaining_qty=0,
            )
        return _FuturesFillStatus(
            outcome=FillQueryOutcome.FOUND,
            order_no=_ORDER_NO,
            order_qty=1,
            filled_qty=0,
            remaining_qty=1,
        )

    executor._inquire_futures_fill_status = AsyncMock(side_effect=_poll_then_requery)
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(success=True, message="cancel_ok")
    )

    resp = await executor._await_futures_fill_or_cancel(
        order=_order(), order_no=_ORDER_NO, is_mock=False, is_night=False
    )

    assert resp.success is False
    assert "cancelled" in resp.message.lower()
    assert resp.fill_state_unknown is False


# ---------------------------------------------------------------------------
# D-7 — truncation detectability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_truncation_warns_when_full_page_carries_a_continuation_key(caplog):
    """A full page + a continuation key means rows may have been cut off."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config(futures_inquire_page_size=3))
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    executor._request_json = AsyncMock(
        return_value=(
            {
                "rt_cd": "0",
                "output1": [
                    {"odno": "0000009999"},
                    {"odno": "0000009998"},
                    {"odno": "0000009997"},
                ],
                "ctx_area_nk200": "NEXTKEY",
            },
            200,
        )
    )

    with caplog.at_level(logging.WARNING, logger="shared.execution.executor"):
        status = await _inquire(executor)

    assert status.outcome is FillQueryOutcome.NOT_PRESENT
    assert any("may be TRUNCATED" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_truncation_silent_on_a_short_page(caplog):
    """Negative: a short page cannot have been truncated — no warning noise."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config(futures_inquire_page_size=15))
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    executor._request_json = AsyncMock(
        return_value=(
            {"rt_cd": "0", "output1": [_row(1, 0)], "ctx_area_nk200": "NEXTKEY"},
            200,
        )
    )

    with caplog.at_level(logging.WARNING, logger="shared.execution.executor"):
        status = await _inquire(executor)

    assert status.outcome is FillQueryOutcome.FOUND
    assert not any("TRUNCATED" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_truncation_silent_without_a_continuation_key(caplog):
    """Negative: a full page with no continuation key is a complete answer."""
    from unittest.mock import AsyncMock

    executor = OrderExecutor(_config(futures_inquire_page_size=1))
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO5201R"})
    executor._request_json = AsyncMock(
        return_value=(
            {"rt_cd": "0", "output1": [_row(1, 0)], "ctx_area_nk200": "   "},
            200,
        )
    )

    with caplog.at_level(logging.WARNING, logger="shared.execution.executor"):
        await _inquire(executor)

    assert not any("TRUNCATED" in r.getMessage() for r in caplog.records)
