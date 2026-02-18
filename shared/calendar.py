"""
Market Calendar for KRX (Korea Exchange)

Provides market open/close status checking with holiday awareness.
Used for scheduling pre-market preparation and data collection.

Usage:
    from shared.calendar import MarketCalendar, is_market_open_today

    calendar = MarketCalendar()
    if calendar.is_market_open_today():
        # Run pre-market preparation
        pass
"""
import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketCalendar:
    """KRX Market Calendar with holiday awareness."""

    # KRX Fixed Holidays (month, day) - 매년 고정
    FIXED_HOLIDAYS = [
        (1, 1),   # 신정 New Year's Day
        (3, 1),   # 삼일절 Independence Movement Day
        (5, 5),   # 어린이날 Children's Day
        (6, 6),   # 현충일 Memorial Day
        (8, 15),  # 광복절 Liberation Day
        (10, 3),  # 개천절 National Foundation Day
        (10, 9),  # 한글날 Hangul Day
        (12, 25), # 성탄절 Christmas
    ]

    # KRX 2025 Holidays (lunar calendar-based, varies by year)
    # Source: https://global.krx.co.kr
    HOLIDAYS_2025 = [
        date(2025, 1, 1),   # 신정
        date(2025, 1, 28),  # 설날 연휴
        date(2025, 1, 29),  # 설날
        date(2025, 1, 30),  # 설날 연휴
        date(2025, 3, 1),   # 삼일절
        date(2025, 3, 3),   # 삼일절 대체공휴일
        date(2025, 5, 5),   # 어린이날
        date(2025, 5, 6),   # 부처님오신날
        date(2025, 6, 6),   # 현충일
        date(2025, 8, 15),  # 광복절
        date(2025, 10, 3),  # 개천절
        date(2025, 10, 6),  # 추석 연휴
        date(2025, 10, 7),  # 추석
        date(2025, 10, 8),  # 추석 연휴
        date(2025, 10, 9),  # 한글날
        date(2025, 12, 25), # 성탄절
    ]

    # KRX 2026 Holidays (예상 - 확정 시 업데이트 필요)
    HOLIDAYS_2026 = [
        date(2026, 1, 1),   # 신정
        date(2026, 2, 16),  # 설날 연휴
        date(2026, 2, 17),  # 설날
        date(2026, 2, 18),  # 설날 연휴
        date(2026, 3, 1),   # 삼일절 (일요일 → 3/2 대체)
        date(2026, 3, 2),   # 삼일절 대체공휴일
        date(2026, 5, 5),   # 어린이날
        date(2026, 5, 24),  # 부처님오신날 (일요일 → 5/25 대체)
        date(2026, 5, 25),  # 부처님오신날 대체공휴일
        date(2026, 6, 6),   # 현충일 (토요일)
        date(2026, 8, 15),  # 광복절 (토요일)
        date(2026, 9, 24),  # 추석 연휴
        date(2026, 9, 25),  # 추석
        date(2026, 9, 26),  # 추석 연휴
        date(2026, 10, 3),  # 개천절 (토요일)
        date(2026, 10, 9),  # 한글날
        date(2026, 12, 25), # 성탄절
    ]

    # KRX 2027 Holidays (예상 - 확정 시 업데이트 필요)
    HOLIDAYS_2027 = [
        date(2027, 1, 1),   # 신정
        date(2027, 2, 8),   # 설날 연휴 (2/6 토, 2/7 일 → 평일만)
        date(2027, 2, 9),   # 설날 대체공휴일
        date(2027, 3, 1),   # 삼일절
        date(2027, 5, 5),   # 어린이날
        date(2027, 5, 13),  # 부처님오신날
        date(2027, 6, 7),   # 현충일 대체공휴일 (6/6 일요일)
        date(2027, 8, 16),  # 광복절 대체공휴일 (8/15 일요일)
        date(2027, 9, 14),  # 추석 연휴
        date(2027, 9, 15),  # 추석
        date(2027, 9, 16),  # 추석 연휴
        date(2027, 10, 4),  # 개천절 대체공휴일 (10/3 일요일)
        date(2027, 10, 11), # 한글날 대체공휴일 (10/9 토요일)
        date(2027, 12, 27), # 성탄절 대체공휴일 (12/25 토요일)
    ]

    # Market Hours
    MARKET_OPEN_TIME = time(9, 0)
    MARKET_CLOSE_TIME = time(15, 30)
    PREMARKET_START_TIME = time(8, 0)
    PREMARKET_END_TIME = time(8, 55)

    def __init__(self):
        """Initialize market calendar."""
        self._holidays_by_year: Dict[int, List[date]] = {
            2025: self.HOLIDAYS_2025,
            2026: self.HOLIDAYS_2026,
            2027: self.HOLIDAYS_2027,
        }
        logger.info("MarketCalendar initialized")

    def get_holidays(self, year: int) -> List[date]:
        """Get list of holidays for a specific year.

        Args:
            year: Year to get holidays for

        Returns:
            List of holiday dates
        """
        if year in self._holidays_by_year:
            return self._holidays_by_year[year]

        # Fallback: generate from fixed holidays only
        logger.warning(f"No holiday data for {year}, using fixed holidays only")
        return [date(year, month, day) for month, day in self.FIXED_HOLIDAYS]

    def is_holiday(self, check_date: date) -> bool:
        """Check if a date is a holiday.

        Args:
            check_date: Date to check

        Returns:
            True if holiday, False otherwise
        """
        holidays = self.get_holidays(check_date.year)
        return check_date in holidays

    def is_weekend(self, check_date: date) -> bool:
        """Check if a date is a weekend.

        Args:
            check_date: Date to check

        Returns:
            True if Saturday or Sunday
        """
        return check_date.weekday() >= 5  # 5=Saturday, 6=Sunday

    def is_market_day(self, check_date: date) -> bool:
        """Check if a date is a trading day.

        Args:
            check_date: Date to check

        Returns:
            True if market is open on this date
        """
        if self.is_weekend(check_date):
            return False
        if self.is_holiday(check_date):
            return False
        return True

    def is_market_open_today(self) -> bool:
        """Check if market is open today.

        Returns:
            True if today is a trading day
        """
        return self.is_market_day(date.today())

    def is_market_hours(self, check_time: Optional[datetime] = None) -> bool:
        """Check if current time is within market trading hours.

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            True if within 09:00 - 15:30
        """
        if check_time is None:
            check_time = datetime.now()

        if not self.is_market_day(check_time.date()):
            return False

        current_time = check_time.time()
        return self.MARKET_OPEN_TIME <= current_time <= self.MARKET_CLOSE_TIME

    def is_premarket_hours(self, check_time: Optional[datetime] = None) -> bool:
        """Check if current time is within pre-market hours.

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            True if within 08:00 - 08:55
        """
        if check_time is None:
            check_time = datetime.now()

        if not self.is_market_day(check_time.date()):
            return False

        current_time = check_time.time()
        return self.PREMARKET_START_TIME <= current_time <= self.PREMARKET_END_TIME

    def get_next_market_day(self, from_date: Optional[date] = None) -> date:
        """Get the next trading day.

        Args:
            from_date: Start date (defaults to today)

        Returns:
            Next market open date
        """
        if from_date is None:
            from_date = date.today()

        next_day = from_date + timedelta(days=1)
        while not self.is_market_day(next_day):
            next_day += timedelta(days=1)

        return next_day

    def get_previous_market_day(self, from_date: Optional[date] = None) -> date:
        """Get the previous trading day.

        Args:
            from_date: Start date (defaults to today)

        Returns:
            Previous market open date
        """
        if from_date is None:
            from_date = date.today()

        prev_day = from_date - timedelta(days=1)
        while not self.is_market_day(prev_day):
            prev_day -= timedelta(days=1)

        return prev_day

    def get_market_status(self) -> Dict[str, Any]:
        """Get current market status summary.

        Returns:
            Dictionary with market status info
        """
        now = datetime.now()
        today = date.today()

        return {
            "date": str(today),
            "day_of_week": today.strftime("%A"),
            "is_market_day": self.is_market_day(today),
            "is_weekend": self.is_weekend(today),
            "is_holiday": self.is_holiday(today),
            "is_market_hours": self.is_market_hours(now),
            "is_premarket_hours": self.is_premarket_hours(now),
            "market_open_time": str(self.MARKET_OPEN_TIME),
            "market_close_time": str(self.MARKET_CLOSE_TIME),
            "next_market_day": str(self.get_next_market_day()) if not self.is_market_day(today) else None,
        }

    def get_trading_days_in_range(
        self,
        start_date: date,
        end_date: date
    ) -> List[date]:
        """Get all trading days in a date range.

        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)

        Returns:
            List of trading days
        """
        trading_days = []
        current = start_date
        while current <= end_date:
            if self.is_market_day(current):
                trading_days.append(current)
            current += timedelta(days=1)
        return trading_days


# ============================================================
# Singleton and Convenience Functions
# ============================================================


_calendar_instance: Optional[MarketCalendar] = None


def get_market_calendar() -> MarketCalendar:
    """Get singleton MarketCalendar instance."""
    global _calendar_instance
    if _calendar_instance is None:
        _calendar_instance = MarketCalendar()
    return _calendar_instance


def is_market_open_today() -> bool:
    """Convenience function to check if market is open today."""
    return get_market_calendar().is_market_open_today()


def is_market_hours() -> bool:
    """Convenience function to check if currently market hours."""
    return get_market_calendar().is_market_hours()
