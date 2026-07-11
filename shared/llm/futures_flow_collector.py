"""Futures flow and microstructure collector."""

from __future__ import annotations

import contextlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.calendar import MarketCalendar
from shared.features.ofi import OFICalculator, OFIConfig
from shared.indicators.orderbook import OrderBookAnalyzer
from shared.models.stream_models import MarketTickMessage
from shared.streaming.client import RedisClient
from shared.streaming.codec import StreamDecodeError, decode, normalize_stream_fields
from shared.streaming.message import StreamMessage

from .collector_base import DataCollector
from .config import LLMConfig
from .data_classes import FlowData
from .krx_api_client import KRXOpenAPIClient

logger = logging.getLogger("shared.llm.collectors")


class FuturesFlowCollector(DataCollector):
    """수급 데이터 수집"""

    def __init__(self, config: LLMConfig | None = None):
        super().__init__()
        self.config = config or LLMConfig.from_env()
        self._calendar = MarketCalendar()
        self._krx_client = KRXOpenAPIClient(self.config)

    def collect(self) -> tuple[FlowData | None, list[str]]:
        """수급 데이터 수집 (외국인 선물 흐름 + 베이시스/풋콜/미시구조).

        외국인 선물 순매수(``fut_foreign_net_qty``)와 다일 누적(``cum20``)을 시장구조
        read-model(``market:structure:latest``)에서 소싱한다. 소스 부재/stale 시엔
        graceful degrade — 해당 마커를 ``missing``에 기록하고 값은 ``None``으로
        폴백한다(fail-safe; LLM 서사 분석은 외인 흐름 없이도 계속 진행).
        기관 선물(institution)은 read-model 소스가 없어 범위 밖(None 유지).
        """
        missing: list[str] = []
        base_date = self._get_last_trading_date()

        basis, put_call = self._collect_basis_putcall(base_date, missing)
        micro_data, micro_missing = self._collect_microstructure()
        missing.extend(micro_missing)
        foreign_net, foreign_cum20, foreign_missing = self._collect_foreign_flow()
        missing.extend(foreign_missing)

        missing = self._dedupe_missing(missing)
        if (
            basis is None
            and put_call is None
            and not micro_data
            and foreign_net is None
        ):
            return None, missing

        flow_score = self._compute_flow_score(
            basis,
            put_call,
            micro_data,
            foreign_net,
            self.config.futures_flow_foreign_weight,
        )
        flow_data = self._build_flow_data(
            basis, put_call, micro_data, flow_score, foreign_net, foreign_cum20
        )
        return flow_data, missing

    def _collect_basis_putcall(
        self,
        base_date: str,
        missing: list[str],
    ) -> tuple[float | None, float | None]:
        basis: float | None = None
        put_call: float | None = None
        if not self.config.krx_api_key:
            missing.append("krx_api_key_missing")
            return basis, put_call

        try:
            futures_list = self._krx_client.get_kospi200_futures(base_date)
            futures = (
                max(futures_list, key=lambda f: f.volume) if futures_list else None
            )
            options = self._krx_client.get_kospi200_options(base_date)
            spot = self._get_kospi200_index_price(base_date)
            if futures is not None and spot is not None:
                basis = float(futures.close_price) - float(spot)
            else:
                missing.append("basis")
            if options:
                put_call = float(options.put_call_ratio)
            else:
                missing.append("put_call_ratio")
        except Exception as e:
            logger.debug(f"KRX futures basis/put-call failed: {e}")
            missing.extend(["basis", "put_call_ratio"])
        return basis, put_call

    def _collect_foreign_flow(
        self,
    ) -> tuple[float | None, float | None, list[str]]:
        """Read foreign-futures net flow from the market-structure read-model.

        Sources the ``market:structure:latest`` hash published by
        ``services/market_structure_collector`` (KIS FHPTJ04030000 daily
        snapshot). Returns ``(net_qty, cum20, missing)`` where ``net_qty`` is the
        day's foreign net contracts and ``cum20`` is the rolling ~20-trading-day
        cumulative (``fut_foreign_net_qty_cum20`` — NOT a 5-day figure).

        Fail-safe: a missing/empty/stale hash, an unreachable Redis, or an absent
        field degrades to ``(None, None, [marker])`` so the LLM narrative still
        runs without foreign flow — it never raises.
        """
        key = self.config.futures_structure_key
        try:
            client = RedisClient.get_client()
            raw = client.hgetall(key) or {}
        except Exception as e:  # noqa: BLE001 — degraded source must not raise
            logger.debug(f"market-structure hash fetch failed ({key}): {e}")
            return None, None, ["foreign_futures_unavailable"]

        fields = {str(k): v for k, v in dict(raw).items()}
        if not fields:
            return None, None, ["foreign_futures_unavailable"]
        if self._structure_is_stale(fields):
            return None, None, ["foreign_futures_stale"]

        foreign_net = self._to_float(fields.get("fut_foreign_net_qty"))
        foreign_cum20 = self._to_float(fields.get("fut_foreign_net_qty_cum20"))
        missing = [] if foreign_net is not None else ["foreign_futures"]
        return foreign_net, foreign_cum20, missing

    def _structure_is_stale(self, fields: dict[str, Any]) -> bool:
        """Whether the snapshot's asof timestamp is older than the configured
        bound. Missing/unparseable timestamps are treated as fresh so a
        present-but-untimestamped hash is not falsely degraded."""
        stale_after = self.config.futures_structure_stale_seconds
        if stale_after <= 0:
            return False
        asof = self._parse_structure_asof(fields.get("asof_ts") or fields.get("asof"))
        if asof is None:
            return False
        # asof_ts is naive KST (container TZ=Asia/Seoul → naive now() is KST).
        return (datetime.now() - asof).total_seconds() > stale_after

    @staticmethod
    def _parse_structure_asof(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
        return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed

    @staticmethod
    def _dedupe_missing(missing: list[str]) -> list[str]:
        return list(dict.fromkeys(missing)) if missing else missing

    @staticmethod
    def _compute_flow_score(
        basis: float | None,
        put_call: float | None,
        micro_data: dict[str, Any],
        foreign_futures: float | None = None,
        foreign_weight: float = 0.0,
    ) -> float:
        flow_score = 0.0
        if basis is not None:
            flow_score -= basis * 10
        if put_call is not None:
            if put_call > 1.1:
                flow_score += 5
            elif put_call < 0.9:
                flow_score -= 5

        # Foreign futures net-buy is a directional flow signal: net long
        # (positive) is bullish, net short (negative) is bearish. Bounded ±
        # contribution mirrors the put-call term (sign only, no magnitude
        # threshold); the weight is config-driven (futures_flow_foreign_weight).
        if foreign_futures is not None and foreign_weight:
            if foreign_futures > 0:
                flow_score += foreign_weight
            elif foreign_futures < 0:
                flow_score -= foreign_weight

        micro_score = micro_data.get("microstructure_score") if micro_data else None
        if micro_score is not None:
            flow_score += micro_score
        return flow_score

    @staticmethod
    def _build_flow_data(
        basis: float | None,
        put_call: float | None,
        micro_data: dict[str, Any],
        flow_score: float,
        foreign_futures: float | None = None,
        foreign_futures_cum20: float | None = None,
    ) -> FlowData:
        micro_score = micro_data.get("microstructure_score") if micro_data else None
        return FlowData(
            foreign_futures=foreign_futures,
            # institution_futures has no market-structure source today (the
            # read-model publishes only foreign net); left None (out of scope).
            institution_futures=None,
            retail_futures=None,
            # foreign_futures_5d has no 5-day source in market:structure; the
            # available multi-day figure is the 20-day cum (foreign_futures_cum20).
            foreign_futures_5d=None,
            institution_futures_5d=None,
            foreign_futures_cum20=foreign_futures_cum20,
            basis=round(basis, 2) if basis is not None else None,
            put_call_ratio=round(put_call, 2) if put_call is not None else None,
            orderbook_imbalance=(
                micro_data.get("orderbook_imbalance") if micro_data else None
            ),
            ofi_zscore=micro_data.get("ofi_zscore") if micro_data else None,
            aggressor_ratio=micro_data.get("aggressor_ratio") if micro_data else None,
            aggressor_balance=(
                micro_data.get("aggressor_balance") if micro_data else None
            ),
            oi_change=micro_data.get("oi_change") if micro_data else None,
            price_change=micro_data.get("price_change") if micro_data else None,
            microstructure_score=micro_score,
            flow_score=round(flow_score, 1),
        )

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _load_recent_ticks(self) -> tuple[list[StreamMessage], list[str]]:
        missing: list[str] = []
        stream_name = self.config.futures_tick_stream or "raw_data"
        lookback_seconds = max(60, int(self.config.futures_tick_lookback_seconds))
        max_entries = max(100, int(self.config.futures_tick_max))

        try:
            redis_client = RedisClient.get_client()
            raw_msgs = redis_client.xrevrange(
                stream_name, max="+", min="-", count=max_entries
            )
        except Exception as e:
            logger.debug(f"Redis tick fetch failed: {e}")
            missing.append("redis_unavailable")
            return [], missing

        now = time.time()
        parsed: list[StreamMessage] = []
        for msg_id, fields in raw_msgs:
            msg = self._decode_tick_message(stream_name, msg_id, fields)
            if msg is None:
                continue
            if now - msg.timestamp > lookback_seconds:
                continue
            parsed.append(msg)

        parsed.reverse()
        if not parsed:
            missing.append("microstructure_ticks")
        return parsed, missing

    def _decode_tick_message(
        self,
        stream_name: str,
        msg_id: Any,
        fields: dict[Any, Any],
    ) -> StreamMessage | None:
        normalized = normalize_stream_fields(fields)
        try:
            tick = decode(
                MarketTickMessage,
                normalized,
                legacy_adapter=lambda legacy: MarketTickMessage.from_legacy_fields(
                    legacy,
                    price_keys=("current_price", "price", "close"),
                ),
            )
        except StreamDecodeError:
            return None

        data: dict[str, Any] = dict(normalized)
        data["asset"] = tick.asset
        data["symbol"] = tick.symbol
        data["price"] = str(tick.price)
        data["current_price"] = str(tick.price)
        data.setdefault("close", str(tick.price))
        data["timestamp"] = str(tick.timestamp)
        if tick.volume is not None:
            data.setdefault("volume", str(tick.volume))
        if tick.tick_volume is not None:
            data.setdefault("tick_volume", str(tick.tick_volume))
        if tick.cumulative_volume is not None:
            data.setdefault("cumulative_volume", str(tick.cumulative_volume))

        msg_id_text = (
            msg_id.decode("utf-8", errors="replace")
            if isinstance(msg_id, bytes)
            else str(msg_id)
        )
        return StreamMessage(
            id=msg_id_text,
            data=data,
            stream=stream_name,
            timestamp=time.time(),
        )

    @staticmethod
    def _resolve_symbol(ticks: list[StreamMessage], explicit: str | None) -> str | None:
        if explicit:
            for msg in ticks:
                if msg.data.get("symbol") == explicit:
                    return explicit
            return None

        counts: dict[str, int] = {}
        for msg in ticks:
            symbol = msg.data.get("symbol")
            if symbol:
                counts[symbol] = counts.get(symbol, 0) + 1
        if not counts:
            return None
        return max(counts.items(), key=lambda item: item[1])[0]

    def _extract_orderbook_levels(
        self, data: dict[str, Any]
    ) -> tuple[list[float], list[float], list[float], list[float]]:
        bid_prices: list[float] = []
        bid_qtys: list[float] = []
        ask_prices: list[float] = []
        ask_qtys: list[float] = []
        for i in range(1, 6):
            bid_price = self._to_float(data.get(f"bid_price_{i}"))
            bid_qty = self._to_float(data.get(f"bid_qty_{i}"))
            ask_price = self._to_float(data.get(f"ask_price_{i}"))
            ask_qty = self._to_float(data.get(f"ask_qty_{i}"))
            if bid_price is not None and bid_qty is not None and bid_price > 0:
                bid_prices.append(bid_price)
                bid_qtys.append(bid_qty)
            if ask_price is not None and ask_qty is not None and ask_price > 0:
                ask_prices.append(ask_price)
                ask_qtys.append(ask_qty)
        return bid_prices, ask_prices, bid_qtys, ask_qtys

    @dataclass
    class _MicrostructureState:
        last_orderbook: dict[str, Any] | None = None
        last_bid: float | None = None
        last_ask: float | None = None
        last_mid: float | None = None
        buy_volume: float = 0.0
        sell_volume: float = 0.0
        trade_count: int = 0
        first_trade_price: float | None = None
        last_trade_price: float | None = None
        first_oi: float | None = None
        last_oi: float | None = None

    def _init_microstructure_state(self) -> FuturesFlowCollector._MicrostructureState:
        return FuturesFlowCollector._MicrostructureState()

    def _update_state_from_orderbook(
        self,
        data: dict[str, Any],
        state: FuturesFlowCollector._MicrostructureState,
        ofi_calc: OFICalculator,
    ) -> None:
        bid = self._to_float(data.get("bid_price_1"))
        ask = self._to_float(data.get("ask_price_1"))
        bid_qty = self._to_float(data.get("bid_qty_1")) or 0.0
        ask_qty = self._to_float(data.get("ask_qty_1")) or 0.0

        if bid is not None and ask is not None and bid > 0 and ask > 0:
            state.last_bid = bid
            state.last_ask = ask
            state.last_mid = (bid + ask) / 2
            state.last_orderbook = data
            with contextlib.suppress(Exception):
                ofi_calc.update(bid, bid_qty, ask, ask_qty)

    def _update_state_from_trade(
        self,
        data: dict[str, Any],
        state: FuturesFlowCollector._MicrostructureState,
    ) -> None:
        price = self._extract_trade_price(data)
        if price is None:
            return

        size = self._extract_trade_size(data)
        state.trade_count += 1
        self._update_trade_prices(state, price)
        self._update_open_interest(state, data)

        side = self._infer_trade_side(state, price)
        self._apply_trade_side(state, side, size)

    def _extract_trade_price(self, data: dict[str, Any]) -> float | None:
        price = self._to_float(data.get("current_price"))
        if price is None or price <= 0:
            return None
        return price

    def _extract_trade_size(self, data: dict[str, Any]) -> float:
        return self._to_float(data.get("tick_volume")) or 1.0

    @staticmethod
    def _update_trade_prices(
        state: FuturesFlowCollector._MicrostructureState,
        price: float,
    ) -> None:
        if state.first_trade_price is None:
            state.first_trade_price = price
        state.last_trade_price = price

    def _update_open_interest(
        self,
        state: FuturesFlowCollector._MicrostructureState,
        data: dict[str, Any],
    ) -> None:
        oi = self._to_float(data.get("open_interest"))
        if oi is None:
            return
        if state.first_oi is None:
            state.first_oi = oi
        state.last_oi = oi

    @staticmethod
    def _infer_trade_side(
        state: FuturesFlowCollector._MicrostructureState,
        price: float,
    ) -> str | None:
        if state.last_bid is None or state.last_ask is None:
            return None
        if price >= state.last_ask:
            return "BUY"
        if price <= state.last_bid:
            return "SELL"
        if state.last_mid is None:
            return None
        if price > state.last_mid:
            return "BUY"
        if price < state.last_mid:
            return "SELL"
        return None

    @staticmethod
    def _apply_trade_side(
        state: FuturesFlowCollector._MicrostructureState,
        side: str | None,
        size: float,
    ) -> None:
        if side == "BUY":
            state.buy_volume += size
        elif side == "SELL":
            state.sell_volume += size

    def _finalize_microstructure(
        self,
        state: FuturesFlowCollector._MicrostructureState,
        ofi_calc: OFICalculator,
        orderbook_analyzer: OrderBookAnalyzer,
        missing: list[str],
    ) -> tuple[dict[str, Any], list[str]]:
        orderbook_imbalance = self._compute_orderbook_imbalance(
            state,
            orderbook_analyzer,
            missing,
        )
        ofi_zscore = self._compute_ofi_zscore(ofi_calc, missing)
        aggressor_ratio, aggressor_balance = self._compute_aggressor_metrics(
            state, missing
        )
        oi_change, price_change = self._compute_oi_price_change(state, missing)
        micro_score, components = self._compute_micro_score(
            orderbook_imbalance,
            ofi_zscore,
            aggressor_balance,
            oi_change,
            price_change,
        )

        if components == 0:
            missing.append("microstructure_unavailable")
            return {}, missing

        payload = self._format_microstructure_payload(
            orderbook_imbalance,
            ofi_zscore,
            aggressor_ratio,
            aggressor_balance,
            oi_change,
            price_change,
            micro_score,
        )
        return payload, missing

    def _compute_orderbook_imbalance(
        self,
        state: FuturesFlowCollector._MicrostructureState,
        orderbook_analyzer: OrderBookAnalyzer,
        missing: list[str],
    ) -> float | None:
        if not state.last_orderbook:
            missing.append("orderbook_imbalance")
            return None

        bid_prices, ask_prices, bid_qtys, ask_qtys = self._extract_orderbook_levels(
            state.last_orderbook
        )
        if not (bid_prices and ask_prices and bid_qtys and ask_qtys):
            missing.append("orderbook_imbalance")
            return None

        try:
            imbalance = orderbook_analyzer.calculate(
                bid_prices=bid_prices,
                ask_prices=ask_prices,
                bid_volumes=[int(q) for q in bid_qtys],
                ask_volumes=[int(q) for q in ask_qtys],
            )
            return imbalance.imbalance
        except Exception:
            return None

    @staticmethod
    def _compute_ofi_zscore(
        ofi_calc: OFICalculator, missing: list[str]
    ) -> float | None:
        ofi_zscore = ofi_calc.get_ofi_zscore()
        if ofi_zscore is None:
            missing.append("ofi_zscore")
        return ofi_zscore

    @staticmethod
    def _compute_aggressor_metrics(
        state: FuturesFlowCollector._MicrostructureState,
        missing: list[str],
    ) -> tuple[float | None, float | None]:
        total_vol = state.buy_volume + state.sell_volume
        if total_vol <= 0:
            missing.append("aggressor_ratio")
            return None, None
        aggressor_ratio = state.buy_volume / total_vol
        aggressor_balance = (state.buy_volume - state.sell_volume) / total_vol
        return aggressor_ratio, aggressor_balance

    @staticmethod
    def _compute_oi_price_change(
        state: FuturesFlowCollector._MicrostructureState,
        missing: list[str],
    ) -> tuple[float | None, float | None]:
        oi_change: float | None = None
        if (
            state.first_oi is not None
            and state.last_oi is not None
            and state.trade_count >= 2
        ):
            oi_change = state.last_oi - state.first_oi
        else:
            missing.append("open_interest_change")

        price_change: float | None = None
        if (
            state.first_trade_price is not None
            and state.last_trade_price is not None
            and state.trade_count >= 2
        ):
            price_change = state.last_trade_price - state.first_trade_price
        else:
            missing.append("price_change")

        return oi_change, price_change

    @staticmethod
    def _compute_micro_score(
        orderbook_imbalance: float | None,
        ofi_zscore: float | None,
        aggressor_balance: float | None,
        oi_change: float | None,
        price_change: float | None,
    ) -> tuple[float, int]:
        micro_score = 0.0
        components = 0
        if orderbook_imbalance is not None:
            micro_score += orderbook_imbalance * 8
            components += 1
        if ofi_zscore is not None:
            capped = max(min(ofi_zscore, 3.0), -3.0)
            micro_score += capped * 1.5
            components += 1
        if aggressor_balance is not None:
            micro_score += aggressor_balance * 6
            components += 1
        if oi_change is not None and price_change is not None:
            components += 1
            if oi_change > 0 and price_change > 0:
                micro_score += 3
            elif oi_change > 0 and price_change < 0:
                micro_score -= 3
            elif oi_change < 0 and price_change > 0:
                micro_score += 1.5
            elif oi_change < 0 and price_change < 0:
                micro_score -= 1.5
        return micro_score, components

    @staticmethod
    def _format_microstructure_payload(
        orderbook_imbalance: float | None,
        ofi_zscore: float | None,
        aggressor_ratio: float | None,
        aggressor_balance: float | None,
        oi_change: float | None,
        price_change: float | None,
        micro_score: float,
    ) -> dict[str, Any]:
        return {
            "orderbook_imbalance": (
                round(orderbook_imbalance, 3)
                if orderbook_imbalance is not None
                else None
            ),
            "ofi_zscore": round(ofi_zscore, 2) if ofi_zscore is not None else None,
            "aggressor_ratio": (
                round(aggressor_ratio, 3) if aggressor_ratio is not None else None
            ),
            "aggressor_balance": (
                round(aggressor_balance, 3) if aggressor_balance is not None else None
            ),
            "oi_change": round(oi_change, 2) if oi_change is not None else None,
            "price_change": (
                round(price_change, 2) if price_change is not None else None
            ),
            "microstructure_score": round(micro_score, 1),
        }

    def _collect_microstructure(self) -> tuple[dict[str, Any], list[str]]:
        missing: list[str] = []
        ticks, tick_missing = self._load_recent_ticks()
        missing.extend(tick_missing)
        if not ticks:
            return {}, missing

        symbol = self._resolve_symbol(ticks, self.config.futures_tick_symbol or None)
        if not symbol:
            missing.append("microstructure_symbol")
            return {}, missing

        filtered = [msg for msg in ticks if msg.data.get("symbol") == symbol]
        if not filtered:
            missing.append("microstructure_ticks")
            return {}, missing

        orderbook_analyzer = OrderBookAnalyzer()
        ofi_calc = OFICalculator(OFIConfig())
        state = self._init_microstructure_state()

        for msg in filtered:
            data = msg.data
            self._update_state_from_orderbook(data, state, ofi_calc)
            self._update_state_from_trade(data, state)

        return self._finalize_microstructure(
            state, ofi_calc, orderbook_analyzer, missing
        )

    def _get_last_trading_date(self) -> str:
        now = datetime.now()
        today = now.date()

        if now.time() < self._calendar.MARKET_OPEN_TIME:
            target = self._calendar.get_previous_market_day(today)
        elif self._calendar.is_market_day(today):
            target = today
        else:
            target = self._calendar.get_previous_market_day(today)

        return target.strftime("%Y%m%d")

    def _get_kospi200_index_price(self, base_date: str) -> float | None:
        data = self._krx_client.get_kospi_index(base_date)
        for item in data or []:
            name = str(item.get("IDX_NM", ""))
            if "KOSPI200" in name or "코스피200" in name:
                return KRXOpenAPIClient._parse_number(item.get("CLSPRC_IDX", 0))
        return None
