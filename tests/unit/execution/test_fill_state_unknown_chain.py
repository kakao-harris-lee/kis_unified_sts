"""`fill_state_unknown` must be CONSUMED end to end — review attempt-1 #2.

The three-state redesign (D-1) exists to carry one fact: "we could not
establish what executed". If that fact dies one stack frame above where it is
produced, D-2's stated downstream harm — a live position with no protective
exit — is not closed for the unknown case.

Chain under test:
    OrderResponse.fill_state_unknown
      -> KISFuturesAdapter (ERROR log + distinguishable stash state)
      -> PassiveMaker      (OrderResult.error, NOT .missed)
      -> OrderRouterDaemon (ERROR log, no silent info-level consume —
         pinned in tests/unit/services/test_order_router_main.py)
"""

import pytest

from shared.execution.models import OrderResponse
from shared.execution.order_result import OrderState
from shared.execution.passive_maker import PassiveMaker


class _StubClient:
    """Minimal duck-typed kis_client with a controllable unknown state."""

    def __init__(self, *, unknown: bool) -> None:
        self._unknown = unknown
        self.cancelled: list[str] = []

    async def get_futures_orderbook(self, symbol):
        from types import SimpleNamespace

        return SimpleNamespace(
            bid=[SimpleNamespace(price=331.20)],
            ask=[SimpleNamespace(price=331.22)],
        )

    async def place_futures_order(self, **_):
        return "ORD-X"

    async def await_fill(self, order_id, timeout_seconds):
        return None

    async def cancel_order(self, order_id):
        self.cancelled.append(order_id)
        return True

    def fill_state_unknown(self, order_id):
        return self._unknown


def _signal():
    from types import SimpleNamespace

    return SimpleNamespace(symbol="A05603", direction="long")


def _spec():
    from types import SimpleNamespace

    return SimpleNamespace(tick_size_points=0.02)


async def _run(client) -> object:
    from unittest.mock import AsyncMock

    maker = PassiveMaker(kis_client=client, fill_logger=AsyncMock())
    return await maker.place_passive_limit_futures(
        signal=_signal(),
        signal_id="sig-1",
        quantity=1,
        spec=_spec(),
        timeout_seconds=1,
    )


@pytest.mark.asyncio
async def test_unknown_fill_state_is_not_reported_as_a_miss():
    result = await _run(_StubClient(unknown=True))

    assert result.state is OrderState.ERROR
    assert result.reason == "fill_state_unknown"
    assert result.is_missed is False


@pytest.mark.asyncio
async def test_resolved_absence_is_still_reported_as_a_miss():
    """Negative control: an ordinary unfilled order stays a plain miss."""
    result = await _run(_StubClient(unknown=False))

    assert result.state is OrderState.MISSED
    assert result.reason == "passive_not_filled"


@pytest.mark.asyncio
async def test_client_without_the_probe_keeps_the_old_contract():
    """A client that cannot report the state must not become an error."""

    class _Legacy(_StubClient):
        fill_state_unknown = None  # not callable

    result = await _run(_Legacy(unknown=True))

    assert result.state is OrderState.MISSED


@pytest.mark.asyncio
async def test_a_truthy_mock_attribute_does_not_manufacture_an_error():
    """AsyncMock auto-creates attributes; only a literal True may count.

    Without the ``is True`` discipline every mock-injected client in the repo
    would suddenly report unresolved fills.
    """
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.await_fill = AsyncMock(return_value=None)
    client.get_futures_orderbook = AsyncMock(
        return_value=_StubClient(unknown=False).__class__  # any object with bid/ask
    )
    # Give it a usable orderbook.
    from types import SimpleNamespace

    client.get_futures_orderbook = AsyncMock(
        return_value=SimpleNamespace(
            bid=[SimpleNamespace(price=331.20)], ask=[SimpleNamespace(price=331.22)]
        )
    )
    client.place_futures_order = AsyncMock(return_value="ORD-X")

    result = await _run(client)

    assert result.state is OrderState.MISSED


@pytest.mark.asyncio
async def test_adapter_stash_carries_the_flag_from_the_executor_response():
    """The producing end: the executor's flag reaches the adapter's stash."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from shared.execution.kis_futures_adapter import KISFuturesAdapter

    executor = AsyncMock()
    executor.config = SimpleNamespace(trading_mode="MOCK")
    executor._send_kis_futures_order = AsyncMock(
        return_value=OrderResponse(
            success=False,
            order_no="ORD-U",
            filled_qty=0,
            message="cancel failed, state unresolved",
            fill_state_unknown=True,
        )
    )
    feed = MagicMock()
    adapter = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)

    order_id = await adapter.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=331.2
    )

    assert adapter.fill_state_unknown(order_id) is True
    assert await adapter.await_fill(order_id, timeout_seconds=1) is None


# ---------------------------------------------------------------------------
# Review attempt-2 #3 — the flag must be read on the FILL branch too
# ---------------------------------------------------------------------------


class _FilledButUnresolvedClient(_StubClient):
    """A partial fill whose EXECUTED TOTAL could not be confirmed."""

    def __init__(self, *, quantity: int = 2) -> None:
        super().__init__(unknown=True)
        self._quantity = quantity

    async def await_fill(self, order_id, timeout_seconds):
        from shared.execution.passive_maker import Fill

        return Fill(
            order_id=order_id,
            price=331.20,
            quantity=self._quantity,
            filled_at_ms=2000,
        )


@pytest.mark.asyncio
async def test_a_fill_with_an_unresolved_total_is_flagged_not_discarded():
    """Do not throw the measurement away — surface it alongside the fill.

    The adapter stashes the unknown flag next to a POSITIVE fill (a partial
    whose total is unconfirmed). Consulting it only on the `fill is None`
    branch left exactly the rows where a position EXISTS unflagged.
    """
    result = await _run(_FilledButUnresolvedClient(quantity=2))

    assert result.state is OrderState.FILLED  # measurement kept
    assert result.filled_quantity == 2  # lower bound, still armed
    assert result.unresolved is True  # ...but say so


@pytest.mark.asyncio
async def test_a_resolved_fill_is_not_flagged():
    """Negative control."""

    class _Resolved(_FilledButUnresolvedClient):
        def fill_state_unknown(self, order_id):
            return False

    result = await _run(_Resolved(quantity=2))

    assert result.state is OrderState.FILLED
    assert result.filled_quantity == 2
    assert result.unresolved is False


@pytest.mark.asyncio
async def test_order_result_carries_the_executed_quantity():
    """`OrderResult.filled` must not discard `fill.quantity`.

    Dropping it made the router rebuild the bracket from the REQUESTED size.
    """
    from types import SimpleNamespace

    from shared.execution.order_result import OrderResult

    result = OrderResult.filled(
        SimpleNamespace(order_id="O", price=331.2, quantity=2), slippage_ticks=0.0
    )

    assert result.filled_quantity == 2


@pytest.mark.asyncio
async def test_order_result_tolerates_a_client_without_a_quantity():
    from types import SimpleNamespace

    from shared.execution.order_result import OrderResult

    result = OrderResult.filled(
        SimpleNamespace(order_id="O", price=331.2), slippage_ticks=0.0
    )

    assert result.filled_quantity is None
    assert result.unresolved is False
