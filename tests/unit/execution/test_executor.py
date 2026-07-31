"""Test order executor."""
import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_executor_paper_mode():
    """Test paper trading mode simulates orders."""
    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="PAPER")
    executor = OrderExecutor(config)

    order = OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
    )

    response = await executor.execute_order(order)

    assert response.success is True
    assert response.order_no is not None


@pytest.mark.asyncio
async def test_executor_initialize_cleanup():
    """Test session lifecycle."""
    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor

    config = ExecutionConfig(trading_mode="PAPER")
    executor = OrderExecutor(config)

    await executor.initialize()
    assert executor._initialized is True

    await executor.cleanup()
    assert executor.session is None


@pytest.mark.asyncio
async def test_send_order_routes_futures_orders():
    """Futures orders should use futures execution path."""
    from unittest.mock import AsyncMock

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="REAL", rate_limit_key="futures")
    executor = OrderExecutor(config=config)
    executor._send_kis_futures_order = AsyncMock(return_value=type("R", (), {"success": True})())

    order = OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=330.5,
    )
    await executor._send_order(order)

    executor._send_kis_futures_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_futures_fill_timeout_triggers_cancel():
    """On fill timeout, cancel API should be called."""
    from unittest.mock import AsyncMock

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import (
        FillQueryOutcome,
        OrderExecutor,
        _FuturesFillStatus,
    )
    from shared.execution.models import (
        OrderRequest,
        OrderResponse,
        OrderSide,
        OrderType,
    )

    config = ExecutionConfig(
        trading_mode="REAL",
        rate_limit_key="futures",
        futures_fill_check_poll_interval_seconds=0.05,
        futures_fill_check_timeout_seconds=0.1,
        futures_auto_cancel_unfilled=True,
    )
    executor = OrderExecutor(config=config)
    order = OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=330.5,
    )

    pending = _FuturesFillStatus(
        outcome=FillQueryOutcome.FOUND,
        order_no="0000001234",
        order_qty=1,
        filled_qty=0,
        remaining_qty=1,
    )
    after_cancel = _FuturesFillStatus(
        outcome=FillQueryOutcome.FOUND,
        order_no="0000001234",
        order_qty=1,
        filled_qty=0,
        remaining_qty=0,
    )
    executor._inquire_futures_fill_status = AsyncMock(side_effect=[pending, pending, after_cancel])
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(success=True, message="cancel_ok")
    )

    resp = await executor._await_futures_fill_or_cancel(
        order=order,
        order_no="0000001234",
        is_mock=False,
        is_night=False,
    )

    assert resp.success is False
    executor._cancel_futures_order.assert_awaited_once()
    assert "cancelled" in resp.message.lower()


@pytest.mark.asyncio
async def test_execute_order_does_not_retry_when_order_no_exists():
    """Failure with order number should not be retried (duplicate-order guard)."""
    from unittest.mock import AsyncMock

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import (
        OrderRequest,
        OrderResponse,
        OrderSide,
        OrderType,
    )

    config = ExecutionConfig(trading_mode="REAL", max_retries=3, retry_delay=0.01)
    executor = OrderExecutor(config=config)
    executor._send_order = AsyncMock(
        side_effect=[
            OrderResponse(
                success=False,
                order_no="0000001234",
                message="Futures unfilled order cancelled",
            ),
            OrderResponse(success=True, order_no="0000009999", message="should_not_reach"),
        ]
    )

    order = OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=330.5,
    )

    resp = await executor.execute_order(order)

    assert resp.success is False
    assert resp.order_no == "0000001234"
    assert executor._send_order.await_count == 1


def test_resolve_futures_inquire_tr_id_and_path_by_session():
    """체결조회 TR 연동: 모의/주간/야간 경로가 정확히 분기된다."""
    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor

    config = ExecutionConfig(trading_mode="REAL", rate_limit_key="futures")
    executor = OrderExecutor(config=config)

    tr_id, path = executor._resolve_futures_inquire_tr_id_and_path(is_mock=True, is_night=False)
    assert tr_id == config.futures_tr_code_inquire_day_mock
    assert path.endswith("/trading/inquire-ccnl")

    tr_id, path = executor._resolve_futures_inquire_tr_id_and_path(is_mock=False, is_night=False)
    assert tr_id == config.futures_tr_code_inquire_day_real
    assert path.endswith("/trading/inquire-ccnl")

    tr_id, path = executor._resolve_futures_inquire_tr_id_and_path(is_mock=False, is_night=True)
    assert tr_id == config.futures_tr_code_inquire_night_real
    assert path.endswith("/trading/inquire-ngt-ccnl")


@pytest.mark.asyncio
async def test_request_json_reissues_once_on_token_expired():
    """KIS server-side token expiry should invalidate local auth and retry once."""
    from unittest.mock import AsyncMock

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor

    config = ExecutionConfig(trading_mode="MOCK")
    auth_manager = MagicMock()
    auth_manager.get_auth_headers.return_value = {"authorization": "Bearer fresh"}
    executor = OrderExecutor(config=config, auth_manager=auth_manager)

    expired_resp = AsyncMock()
    expired_resp.status = 200
    expired_resp.json.return_value = {
        "rt_cd": "1",
        "msg_cd": "EGW00123",
        "msg1": "기간이 만료된 token 입니다.",
    }
    success_resp = AsyncMock()
    success_resp.status = 200
    success_resp.json.return_value = {"rt_cd": "0", "msg1": "정상처리"}

    expired_cm = MagicMock()
    expired_cm.__aenter__ = AsyncMock(return_value=expired_resp)
    expired_cm.__aexit__ = AsyncMock(return_value=None)
    success_cm = MagicMock()
    success_cm.__aenter__ = AsyncMock(return_value=success_resp)
    success_cm.__aexit__ = AsyncMock(return_value=None)

    executor.session = MagicMock()
    executor.session.request = MagicMock(side_effect=[expired_cm, success_cm])

    data, status = await executor._request_json(
        "POST",
        "https://example.test/order",
        headers={"authorization": "Bearer stale", "tr_id": "VTTC0802U", "custtype": "P"},
        json={"PDNO": "005930"},
    )

    assert status == 200
    assert data["rt_cd"] == "0"
    auth_manager.invalidate.assert_called_once()
    assert executor.session.request.call_count == 2


def test_is_night_session_boundary():
    """야간 세션 경계(18:00~06:00) 판단 검증."""
    from shared.execution.executor import KST, OrderExecutor

    assert OrderExecutor._is_night_session(datetime(2026, 2, 25, 17, 59, tzinfo=KST)) is False
    assert OrderExecutor._is_night_session(datetime(2026, 2, 25, 18, 0, tzinfo=KST)) is True
    assert OrderExecutor._is_night_session(datetime(2026, 2, 26, 5, 59, tzinfo=KST)) is True
    assert OrderExecutor._is_night_session(datetime(2026, 2, 26, 6, 0, tzinfo=KST)) is False


@pytest.mark.asyncio
async def test_futures_night_order_refused_when_disabled(monkeypatch):
    """Phase 5 legal-review §4: 야간세션이 disabled면 fail-closed로 주문 거부."""
    from unittest.mock import patch

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="LIVE", rate_limit_key="futures")
    executor = OrderExecutor(config)
    order = OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=350.0,
    )
    with (
        patch.object(OrderExecutor, "_is_night_session", return_value=True),
        patch(
            "shared.strategy.market_time.is_futures_night_session_enabled",
            return_value=False,
        ),
    ):
        resp = await executor._send_kis_futures_order(order, is_mock=False)

    assert resp.success is False
    assert "Night session disabled" in resp.message


@pytest.mark.asyncio
async def test_futures_day_order_not_blocked_by_night_guard(monkeypatch):
    """주간 세션이면 야간 가드를 건드리지 않고 정상 경로로 진입(이후 단계는 mock 부재로 실패해도 OK).

    핵심 검증은 응답 메시지가 'Night session disabled'가 아님.
    """
    from unittest.mock import patch

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="LIVE", rate_limit_key="futures")
    executor = OrderExecutor(config)
    order = OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=350.0,
    )
    with patch.object(OrderExecutor, "_is_night_session", return_value=False):
        resp = await executor._send_kis_futures_order(order, is_mock=False)

    assert "Night session disabled" not in (resp.message or "")


#: KIS futures ORD_DVSN_CD -> expected (NMPR_TYPE_CD, KRX_NMPR_CNDT_CD).
#: Source: KIS official examples_llm domestic_futureoption/order docstring
#: (accessed 2026-07-29) — NMPR_TYPE_CD 01:지정가 02:시장가 03:조건부 04:최유리,
#: KRX_NMPR_CNDT_CD 0:없음 3:IOC 4:FOK.
_EXPECTED_FUTURES_NMPR = {
    "01": ("01", "0"),
    "02": ("02", "0"),
    "03": ("03", "0"),
    "04": ("04", "0"),
    "10": ("01", "3"),
    "11": ("01", "4"),
    "12": ("02", "3"),
    "13": ("02", "4"),
    "14": ("04", "3"),
    "15": ("04", "4"),
}


def test_stock_order_type_mapping_covers_every_order_type():
    """모든 OrderType 멤버가 주식 ORD_DVSN 명시 매핑에 존재한다."""
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderType

    expected = {
        OrderType.LIMIT: "00",  # 지정가
        OrderType.MARKET: "01",  # 시장가
        OrderType.CONDITIONAL: "02",  # 조건부지정가
    }
    for order_type, ord_dvsn in expected.items():
        assert OrderExecutor._map_stock_order_type(order_type.value) == ord_dvsn


@pytest.mark.parametrize("unknown", ["", "99", "03", "07", "IOC", "market", None])
def test_stock_unknown_order_type_is_refused(unknown):
    """주식: 매핑에 없는 주문유형은 폴백 없이 명시 예외로 거부된다."""
    from shared.execution.exceptions import OrderExecutionError
    from shared.execution.executor import OrderExecutor

    with pytest.raises(OrderExecutionError) as exc:
        OrderExecutor._map_stock_order_type(unknown)

    assert "unknown order type" in str(exc.value)


def test_futures_order_type_mapping_covers_every_order_type():
    """선물: 내부 OrderType 3종 + 선물 네이티브 코드 10종이 전부 매핑된다."""
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderType

    expected = {
        OrderType.LIMIT: "01",  # stock 지정가 -> futures 지정가
        OrderType.MARKET: "02",  # stock 시장가 -> futures 시장가
        OrderType.CONDITIONAL: "03",  # stock 조건부 -> futures 조건부
    }
    for order_type, ord_dvsn_cd in expected.items():
        assert OrderExecutor._map_futures_order_type(order_type.value) == ord_dvsn_cd

    for native in ("04", "10", "11", "12", "13", "14", "15"):
        assert OrderExecutor._map_futures_order_type(native) == native


@pytest.mark.parametrize("unknown", ["", "05", "16", "99", "IOC", "market", None])
def test_futures_unknown_order_type_is_refused_without_01_fallback(unknown):
    """선물: 미지 주문유형이 조용히 "01"로 접히지 않고 예외로 거부된다."""
    from shared.execution.exceptions import OrderExecutionError
    from shared.execution.executor import OrderExecutor

    with pytest.raises(OrderExecutionError) as exc:
        OrderExecutor._map_futures_order_type(unknown)

    assert "unknown order type" in str(exc.value)


def test_futures_quote_type_codes_match_kis_enumeration():
    """ORD_DVSN_CD 10종 전부에 대해 [필수] 2필드가 KIS 값집합으로 파생된다."""
    from shared.execution.executor import OrderExecutor

    for ord_dvsn_cd, expected in _EXPECTED_FUTURES_NMPR.items():
        codes = OrderExecutor._futures_quote_type_codes(ord_dvsn_cd)
        assert codes == expected
        assert codes[0] in {"01", "02", "03", "04"}
        assert codes[1] in {"0", "3", "4"}
        assert "" not in codes


def test_futures_ord_dvsn_cd_tables_share_one_key_set():
    """드리프트 앵커: 수용하는 ORD_DVSN_CD와 [필수] 2필드 파생표의 키집합이 동일.

    한쪽에만 코드를 추가하면 (a) 수용은 되는데 파생이 없어 주문이 거부되거나
    (b) 파생만 있고 수용되지 않는 죽은 행이 생긴다. 둘 다 봉인한다.
    """
    from shared.execution.executor import (
        _FUTURES_NMPR_CODES,
        _FUTURES_ORD_DVSN_CD,
        _FUTURES_ORD_DVSN_CD_NATIVE,
    )

    assert set(_FUTURES_NMPR_CODES) == _FUTURES_ORD_DVSN_CD_NATIVE
    # 내부 OrderType 매핑의 치역도 파생표 안에 있어야 한다.
    assert set(_FUTURES_ORD_DVSN_CD.values()) <= set(_FUTURES_NMPR_CODES)


@pytest.mark.asyncio
async def test_execute_order_does_not_retry_deterministic_refusal():
    """미지 주문유형은 결정론적 거부 — 재시도 없이 즉시 fail-closed 반환."""
    from unittest.mock import AsyncMock

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(
        trading_mode="MOCK", rate_limit_key="stock", max_retries=3, retry_delay=5.0
    )
    executor = OrderExecutor(config)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "VTTC0012U"})
    executor._request_json = AsyncMock()

    order = OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=70000.0,
    ).model_copy(update={"order_type": "99"})

    start = time.monotonic()
    resp = await executor.execute_order(order)
    elapsed = time.monotonic() - start

    assert resp.success is False
    assert "unknown order type" in resp.message
    # retry_delay=5.0 x 2 sleeps would have been taken by the generic handler.
    assert elapsed < 1.0
    executor._request_json.assert_not_awaited()


@pytest.mark.parametrize("unknown", ["", "00", "05", "16", None])
def test_futures_quote_type_codes_refuse_unknown_ord_dvsn_cd(unknown):
    """ORD_DVSN_CD가 KIS 열거 밖이면 빈 문자열 대신 예외."""
    from shared.execution.exceptions import OrderExecutionError
    from shared.execution.executor import OrderExecutor

    with pytest.raises(OrderExecutionError):
        OrderExecutor._futures_quote_type_codes(unknown)


async def _capture_futures_order_body(order_type):
    """선물 주문 body를 실제 전송 없이 캡처한다 (HTTP는 전부 mock)."""
    from unittest.mock import AsyncMock, patch

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide

    config = ExecutionConfig(
        trading_mode="REAL",
        rate_limit_key="futures",
        futures_fill_check_enabled=False,
    )
    executor = OrderExecutor(config)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO1101U"})
    executor._request_json = AsyncMock(
        return_value=({"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "1"}}, 200)
    )

    order = OrderRequest(
        code="101W09",
        side=OrderSide.BUY,
        order_type=order_type,
        quantity=1,
        price=350.0,
    )
    with patch.object(OrderExecutor, "_is_night_session", return_value=False):
        resp = await executor._send_kis_futures_order(order, is_mock=False)

    assert resp.success is True
    executor._request_json.assert_awaited_once()
    return executor._request_json.await_args.kwargs["json"]


@pytest.mark.asyncio
async def test_futures_order_body_sends_explicit_required_quote_fields():
    """선물 주문 body의 [필수] 2필드가 빈 문자열이 아니라 명시 코드다."""
    from shared.execution.models import OrderType

    body = await _capture_futures_order_body(OrderType.LIMIT)

    assert body["ORD_DVSN_CD"] == "01"  # 지정가
    assert body["NMPR_TYPE_CD"] == "01"  # 호가유형 지정가
    assert body["KRX_NMPR_CNDT_CD"] == "0"  # 호가조건 없음
    assert body["NMPR_TYPE_CD"] != ""
    assert body["KRX_NMPR_CNDT_CD"] != ""


@pytest.mark.asyncio
async def test_futures_market_order_body_derives_market_quote_type():
    """시장가 주문이면 NMPR_TYPE_CD도 시장가(02)로 파생된다."""
    from shared.execution.models import OrderType

    body = await _capture_futures_order_body(OrderType.MARKET)

    assert body["ORD_DVSN_CD"] == "02"  # 시장가
    assert body["NMPR_TYPE_CD"] == "02"
    assert body["KRX_NMPR_CNDT_CD"] == "0"


@pytest.mark.asyncio
async def test_futures_order_refused_before_any_request_on_unknown_type():
    """미지 주문유형이면 HTTP 요청 자체가 발생하지 않는다 (실주문 0)."""
    from unittest.mock import AsyncMock, patch

    from shared.execution.config import ExecutionConfig
    from shared.execution.exceptions import OrderExecutionError
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="REAL", rate_limit_key="futures")
    executor = OrderExecutor(config)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "TTTO1101U"})
    executor._request_json = AsyncMock()

    order = OrderRequest(
        code="101W09",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=350.0,
    ).model_copy(update={"order_type": "99"})

    with patch.object(OrderExecutor, "_is_night_session", return_value=False):
        with pytest.raises(OrderExecutionError):
            await executor._send_kis_futures_order(order, is_mock=False)

    executor._request_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_stock_order_refused_before_any_request_on_unknown_type():
    """주식도 동일: 미지 주문유형은 HTTP 요청 전에 거부된다."""
    from unittest.mock import AsyncMock

    from shared.execution.config import ExecutionConfig
    from shared.execution.exceptions import OrderExecutionError
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="MOCK", rate_limit_key="stock")
    executor = OrderExecutor(config)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "VTTC0012U"})
    executor._request_json = AsyncMock()

    order = OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=70000.0,
    ).model_copy(update={"order_type": "99"})

    with pytest.raises(OrderExecutionError):
        await executor._send_kis_stock_order(order, is_mock=True)

    executor._request_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_stock_order_body_uses_mapped_ord_dvsn():
    """정상 주식 경로는 무변경 — LIMIT은 ORD_DVSN="00"으로 전송된다."""
    from unittest.mock import AsyncMock

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="MOCK", rate_limit_key="stock")
    executor = OrderExecutor(config)
    executor._build_auth_headers = AsyncMock(return_value={"tr_id": "VTTC0012U"})
    executor._request_json = AsyncMock(
        return_value=({"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "1"}}, 200)
    )

    order = OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=70000.0,
    )
    resp = await executor._send_kis_stock_order(order, is_mock=True)

    assert resp.success is True
    body = executor._request_json.await_args.kwargs["json"]
    assert body["ORD_DVSN"] == "00"  # 지정가


def test_is_futures_night_session_enabled_reads_yaml(tmp_path, monkeypatch):
    """market_schedule.yaml의 enabled 플래그를 읽어 반환."""
    from shared.config.loader import ConfigLoader
    from shared.strategy.market_time import is_futures_night_session_enabled

    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "market_schedule.yaml").write_text(
        "market_schedule:\n"
        "  futures:\n"
        "    night:\n"
        "      enabled: true\n"
        "      open: '18:00'\n"
        "      close: '05:00'\n"
    )
    monkeypatch.setenv("KIS_CONFIG_DIR", str(cfg_dir))
    ConfigLoader.clear_cache()
    try:
        assert is_futures_night_session_enabled() is True
    finally:
        ConfigLoader.clear_cache()


def test_is_futures_night_session_enabled_default_false(tmp_path, monkeypatch):
    """enabled 키 누락 / 파일 없음 → fail-closed로 False."""
    from shared.config.loader import ConfigLoader
    from shared.strategy.market_time import is_futures_night_session_enabled

    cfg_dir = tmp_path / "config_empty"
    cfg_dir.mkdir()
    monkeypatch.setenv("KIS_CONFIG_DIR", str(cfg_dir))
    ConfigLoader.clear_cache()
    try:
        assert is_futures_night_session_enabled() is False
    finally:
        ConfigLoader.clear_cache()
