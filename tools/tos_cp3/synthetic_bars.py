#!/usr/bin/env python3
"""리플레이 정답의 입력이 되는 **합성** 분봉 — 시세 데이터가 아니다.

이 저장소는 공개돼 있고 ``data/`` 는 gitignore 다. 그래서 정답 고정본은 호스트의
실제 분봉이 아니라 여기서 만든 합성 분봉이다(계획 §4.3). 과정은 설정
(``config/tos_replay_golden.yaml::synthetic``)과 표준 라이브러리 ``random.Random``
뿐이므로 같은 씨앗이면 같은 바이트가 나온다.
"""

from __future__ import annotations

import math
import random
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

__all__ = [
    "ProcessParams",
    "SyntheticSpec",
    "SyntheticBarsError",
    "build_frame",
    "generate_rows",
]


class SyntheticBarsError(RuntimeError):
    """합성 분봉을 만들 수 없는 설정 — 조용한 기본값 없이 거부한다."""


@dataclass(frozen=True)
class ProcessParams:
    """모든 종목이 공유하는 과정 모양. 값은 설정에서 온다."""

    dev_persistence: float
    anchor_drift_ticks: float
    overnight_gap_ticks: float
    burst_probability: float
    burst_min_bars: int
    burst_max_bars: int
    burst_vol_mult: float
    session_vol_sigma: float
    wick_mult: float
    volume_burst_mult: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, where: str) -> ProcessParams:
        missing = [name for name in cls.__dataclass_fields__ if name not in raw]
        if missing:
            raise SyntheticBarsError(f"{where}: process 키가 없다 {missing}")
        return cls(
            dev_persistence=float(raw["dev_persistence"]),
            anchor_drift_ticks=float(raw["anchor_drift_ticks"]),
            overnight_gap_ticks=float(raw["overnight_gap_ticks"]),
            burst_probability=float(raw["burst_probability"]),
            burst_min_bars=int(raw["burst_min_bars"]),
            burst_max_bars=int(raw["burst_max_bars"]),
            burst_vol_mult=float(raw["burst_vol_mult"]),
            session_vol_sigma=float(raw["session_vol_sigma"]),
            wick_mult=float(raw["wick_mult"]),
            volume_burst_mult=float(raw["volume_burst_mult"]),
        )


@dataclass(frozen=True)
class SyntheticSpec:
    """한 종목의 합성 분봉 명세 — 전부 설정값이다."""

    symbol: str
    market: str
    seed: int
    sessions: int
    first_session: date
    session_open: time
    session_last: time
    base_price: float
    tick: float
    price_decimals: int
    vol_ticks: float
    volume_base: int
    volume_jitter: int
    process: ProcessParams

    @property
    def bars_per_session(self) -> int:
        """한 세션의 봉 수 — 개장부터 마지막 분까지 빈 분 없이."""
        open_minutes = self.session_open.hour * 60 + self.session_open.minute
        last_minutes = self.session_last.hour * 60 + self.session_last.minute
        if last_minutes <= open_minutes:
            raise SyntheticBarsError(
                f"{self.symbol}: session_last {self.session_last} 가 session_open "
                f"{self.session_open} 보다 뒤가 아니다"
            )
        return last_minutes - open_minutes + 1


def _sessions(spec: SyntheticSpec) -> list[date]:
    """거래일 ``sessions`` 개 — 주말은 건너뛴다."""
    days: list[date] = []
    cursor = spec.first_session
    while len(days) < spec.sessions:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _price(ticks: int, spec: SyntheticSpec) -> float:
    """정수 틱 수를 가격으로 — 호가 격자를 벗어난 값이 나올 수 없다."""
    return round(ticks * spec.tick, spec.price_decimals)


def generate_rows(spec: SyntheticSpec) -> list[dict[str, Any]]:
    """``(timestamp, open, high, low, close, volume)`` 행들.

    모양: 느리게 흐르는 anchor 위에 AR(1) 편차를 얹고, 변동성은 세션 배수와
    세션 안의 burst 로 갈린다. 편차가 오래 남으므로 세션 VWAP 에서 멀어진 뒤
    되돌아오고, 그것이 리플레이가 보는 신호다.
    """
    rng = random.Random(spec.seed)
    process = spec.process
    anchor = spec.base_price / spec.tick
    deviation = 0.0
    burst_left = 0
    previous_close_ticks: int | None = None
    rows: list[dict[str, Any]] = []
    bars = spec.bars_per_session

    for day in _sessions(spec):
        anchor += rng.gauss(0.0, process.overnight_gap_ticks)
        session_vol = spec.vol_ticks * math.exp(
            rng.gauss(0.0, process.session_vol_sigma)
        )
        opening = datetime.combine(day, spec.session_open)
        for minute in range(bars):
            if burst_left == 0 and rng.random() < process.burst_probability:
                burst_left = rng.randint(process.burst_min_bars, process.burst_max_bars)
            hot = burst_left > 0
            if hot:
                burst_left -= 1
            sigma = session_vol * (process.burst_vol_mult if hot else 1.0)
            deviation = process.dev_persistence * deviation + rng.gauss(0.0, sigma)
            anchor += rng.gauss(0.0, process.anchor_drift_ticks)

            close_ticks = int(round(anchor + deviation))
            open_ticks = (
                previous_close_ticks
                if previous_close_ticks is not None
                else close_ticks
            )
            upper = int(round(abs(rng.gauss(0.0, sigma)) * process.wick_mult))
            lower = int(round(abs(rng.gauss(0.0, sigma)) * process.wick_mult))
            high_ticks = max(open_ticks, close_ticks) + upper
            low_ticks = min(open_ticks, close_ticks) - lower
            if low_ticks < 1:
                # SAFETY: 0 이하 가격은 생산자의 생략 게이트(close <= 0)에 걸려 봉이
                # 빠진다 — 고정본이 조용히 짧아지는 것을 여기서 막는다
                raise SyntheticBarsError(
                    f"{spec.symbol}: {day} 에 0 이하 가격이 나왔다 — base_price 나 "
                    "vol_ticks 가 과정에 비해 너무 작다"
                )
            volume = spec.volume_base + rng.randint(0, spec.volume_jitter)
            if hot:
                volume = int(volume * process.volume_burst_mult)
            rows.append(
                {
                    "timestamp": opening + timedelta(minutes=minute),
                    "open": _price(open_ticks, spec),
                    "high": _price(high_ticks, spec),
                    "low": _price(low_ticks, spec),
                    "close": _price(close_ticks, spec),
                    "volume": volume,
                }
            )
            previous_close_ticks = close_ticks
    return rows


def build_frame(spec: SyntheticSpec) -> Any:
    """:func:`generate_rows` 를 생산자가 읽는 프레임 모양으로."""
    import pandas as pd

    frame = pd.DataFrame(generate_rows(spec))
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame.sort_values("timestamp").reset_index(drop=True)


def specs_from_config(
    raw: Mapping[str, Any], *, where: str, symbols: Sequence[str] | None = None
) -> tuple[SyntheticSpec, ...]:
    """설정의 ``synthetic`` 블록을 종목별 명세로."""
    block = raw.get("synthetic")
    if not isinstance(block, Mapping):
        raise SyntheticBarsError(
            f"{where}: 'synthetic' 블록이 없다 — 고정본이 합성이라는 사실과 그 씨앗은 "
            "설정에 있어야 재생성이 가능하다"
        )
    process = ProcessParams.from_mapping(
        block.get("process") or {}, where=f"{where}::synthetic"
    )
    markets = block.get("markets")
    instruments = block.get("instruments")
    if not isinstance(markets, Mapping) or not isinstance(instruments, Mapping):
        raise SyntheticBarsError(
            f"{where}::synthetic: 'markets' 와 'instruments' 매핑이 둘 다 필요하다"
        )
    sessions = int(block.get("sessions", 0))
    first_session = block.get("first_session")
    if sessions <= 0 or not isinstance(first_session, date):
        raise SyntheticBarsError(
            f"{where}::synthetic: sessions(양의 정수)와 first_session(날짜)이 필요하다"
        )
    wanted = frozenset(symbols or instruments)
    specs: list[SyntheticSpec] = []
    for symbol in sorted(instruments):
        if symbol not in wanted:
            continue
        entry = instruments[symbol]
        if not isinstance(entry, Mapping):
            raise SyntheticBarsError(f"{where}::synthetic.{symbol}: 매핑이 아니다")
        market = str(entry.get("market") or "")
        window = markets.get(market)
        if not isinstance(window, Mapping):
            raise SyntheticBarsError(
                f"{where}::synthetic.{symbol}: market {market!r} 의 세션 창이 "
                "markets 에 없다"
            )
        specs.append(
            SyntheticSpec(
                symbol=symbol,
                market=market,
                seed=int(entry["seed"]),
                sessions=sessions,
                first_session=first_session,
                session_open=_time_of(window["open"], where=f"{where}::{market}.open"),
                session_last=_time_of(window["last"], where=f"{where}::{market}.last"),
                base_price=float(entry["base_price"]),
                tick=float(entry["tick"]),
                price_decimals=int(entry["price_decimals"]),
                vol_ticks=float(entry["vol_ticks"]),
                volume_base=int(entry["volume_base"]),
                volume_jitter=int(entry["volume_jitter"]),
                process=process,
            )
        )
    if not specs:
        raise SyntheticBarsError(f"{where}::synthetic: 만들 종목이 없다")
    return tuple(specs)


def _time_of(raw: Any, *, where: str) -> time:
    """``HH:MM`` 한 칸."""
    if isinstance(raw, time):
        return raw
    try:
        hour_text, minute_text = str(raw).strip().split(":")[:2]
        return time(int(hour_text), int(minute_text))
    except (TypeError, ValueError) as exc:
        raise SyntheticBarsError(f"{where}: HH:MM 이 아니다 ({raw!r})") from exc
