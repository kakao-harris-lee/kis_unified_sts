"""Measure host↔broker clock skew from KIS's own ``Date`` response header (issue #1138)."""

from __future__ import annotations

from collections.abc import Callable
from email.utils import parsedate_to_datetime

__all__ = ["BrokerClockSkew", "parse_http_date_ms"]


def parse_http_date_ms(value: str | None) -> int | None:
    """One HTTP ``Date`` header as unix ms, or ``None`` when it is not one."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return int(parsed.timestamp() * 1000)


class BrokerClockSkew:
    """The newest measured ``host - broker`` offset of this boot (module docstring)."""

    def __init__(
        self, *, tolerance_s: int, host_unix_ms: Callable[[], int | None]
    ) -> None:
        """Pin the tolerance a judgment may rest on and the host clock to compare against."""
        self._tolerance_ms = tolerance_s * 1000
        self._host_unix_ms = host_unix_ms
        self._measured_ms: int | None = None

    @property
    def measured_ms(self) -> int | None:
        """The newest measured offset in ms, or ``None`` when none has been measured."""
        return self._measured_ms

    def observe(self, date_header: str | None) -> None:
        """Record one broker response's ``Date`` against the host clock. Never raises."""
        broker_ms = parse_http_date_ms(date_header)
        if broker_ms is None:
            return
        try:
            host_ms = self._host_unix_ms()
        except Exception:  # noqa: BLE001 - an unreadable host clock measures nothing
            return
        if not isinstance(host_ms, int) or isinstance(host_ms, bool):
            return
        self._measured_ms = host_ms - broker_ms

    def corroborated(self) -> bool:
        """Is the host clock PROVEN within tolerance of the broker's own?"""
        # SAFETY: 한 번도 재지 못했으면 False 다 — «아직 모른다» 를 «괜찮다» 로 읽으면 #1138 의 130 s 앞선 시계가 우리 주문을 남의 것으로 버린다
        measured = self._measured_ms
        if measured is None:
            return False
        return abs(measured) <= self._tolerance_ms
