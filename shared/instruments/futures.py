"""Neutral KOSPI futures contract-code helpers."""

from __future__ import annotations

from datetime import date, timedelta

KOSPI200_PREFIX = "101"
KOSPI_MINI_PREFIX = "105"

KOSPI200_LEGACY_PREFIX = "A01"
KOSPI_MINI_LEGACY_PREFIX = "A05"

# KIS short codes are relative position codes that auto-roll at the broker.
KIS_SHORT_CODES = {
    "mini_front": "A05601",
    "mini_back": "A05602",
    "kospi_front": "101S6000",
    "kospi_back": "101S6001",
}

KOSPI200F_FRONT_CODE = "101S6000"

YEAR_CODES = {
    2020: "Q",
    2021: "R",
    2022: "S",
    2023: "T",
    2024: "V",
    2025: "W",
    2026: "X",
    2027: "Y",
    2028: "Z",
    2029: "A",
    2030: "B",
}
CODE_TO_YEAR = {v: k for k, v in YEAR_CODES.items()}

MINI_KOSPI_LISTING_MONTHS = 6


def get_expiry_date(year: int, month: int) -> date:
    """Return the second Thursday expiry date for a KOSPI futures contract."""
    first_day = date(year, month, 1)
    first_weekday = first_day.weekday()

    if first_weekday <= 3:
        first_thursday = 1 + (3 - first_weekday)
    else:
        first_thursday = 1 + (7 - first_weekday + 3)

    second_thursday = first_thursday + 7
    return date(year, month, second_thursday)


def make_code(
    year: int,
    month: int,
    prefix: str | None = None,
    legacy: bool = True,
) -> str:
    """Generate a Korea Investment futures contract code."""
    if legacy:
        return make_code_legacy(year, month, prefix)

    if prefix is None:
        prefix = KOSPI_MINI_PREFIX

    year_code = YEAR_CODES.get(year)
    if year_code is None:
        raise ValueError(f"Unsupported year: {year}")

    return f"{prefix}{year_code}{month:02d}"


def make_code_legacy(year: int, month: int, prefix: str | None = None) -> str:
    """Generate a futures code using the legacy A-code format."""
    if prefix is None:
        prefix = KOSPI_MINI_LEGACY_PREFIX

    year_digit = str(year)[-1]
    return f"{prefix}{year_digit}{month:02d}"


def parse_code(code: str) -> tuple[int, int]:
    """Parse a futures code into ``(year, month)``."""
    if code.startswith("A"):
        year_digit = int(code[3])
        month = int(code[4:6])
        year = 2020 + year_digit
    else:
        year_code = code[3]
        month = int(code[4:6])
        parsed_year = CODE_TO_YEAR.get(year_code)
        if parsed_year is None:
            raise ValueError(f"Unknown year code: {year_code}")
        year = parsed_year

    return year, month


def get_listing_start(expiry: date) -> date:
    """Estimate the listing start date for a mini KOSPI200 futures contract."""
    month = expiry.month - MINI_KOSPI_LISTING_MONTHS
    year = expiry.year
    if month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def get_active_codes_for_date(target_date: date) -> list[str]:
    """Return mini KOSPI200 futures codes active on ``target_date``."""
    codes = []
    current = date(target_date.year, target_date.month, 1)

    for _ in range(MINI_KOSPI_LISTING_MONTHS):
        expiry = get_expiry_date(current.year, current.month)

        if target_date <= expiry:
            codes.append(make_code(current.year, current.month))

        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return codes


def get_front_month_code(
    product: str = "kospi200",
    target_date: date | None = None,
    legacy: bool = True,
) -> str:
    """Return the nearest active futures contract code for the product."""
    if target_date is None:
        target_date = date.today()

    if product not in {"kospi200", "mini"}:
        raise ValueError(f"Unsupported product: {product}")

    if product == "kospi200":
        quarterly_months = [3, 6, 9, 12]
        y = target_date.year
        m = next((qm for qm in quarterly_months if qm >= target_date.month), None)
        if m is None:
            y += 1
            m = quarterly_months[0]

        expiry = get_expiry_date(y, m)
        if target_date > expiry:
            idx = quarterly_months.index(m) + 1
            if idx >= len(quarterly_months):
                y += 1
                m = quarterly_months[0]
            else:
                m = quarterly_months[idx]

        prefix = KOSPI200_LEGACY_PREFIX if legacy else KOSPI200_PREFIX
        return make_code(y, m, prefix=prefix, legacy=legacy)

    y, m = target_date.year, target_date.month
    expiry = get_expiry_date(y, m)
    if target_date > expiry:
        m += 1
        if m > 12:
            m = 1
            y += 1

    prefix = KOSPI_MINI_LEGACY_PREFIX if legacy else KOSPI_MINI_PREFIX
    return make_code(y, m, prefix=prefix, legacy=legacy)


def get_all_codes_in_range(start: date, end: date) -> list[str]:
    """Return futures codes that were traded during a date range."""
    codes_set = set()

    check_start = date(start.year, start.month, 1)
    if check_start.month == 1:
        check_start = date(check_start.year - 1, 12, 1)
    else:
        check_start = date(check_start.year, check_start.month - 1, 1)

    check_end = date(end.year, end.month, 1)
    for _ in range(12):
        if check_end.month == 12:
            check_end = date(check_end.year + 1, 1, 1)
        else:
            check_end = date(check_end.year, check_end.month + 1, 1)

    current = check_start
    while current <= check_end:
        expiry = get_expiry_date(current.year, current.month)
        listing_start = get_listing_start(expiry)

        if listing_start <= end and expiry >= start:
            codes_set.add(make_code(current.year, current.month))

        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    codes = list(codes_set)
    codes.sort(key=lambda c: (parse_code(c)[0], parse_code(c)[1]))
    return codes


def get_past_year_codes(from_date: date | None = None) -> list[str]:
    """Return all futures codes for the past year ending at ``from_date``."""
    if from_date is None:
        from_date = date.today()

    start = from_date - timedelta(days=365)
    return get_all_codes_in_range(start, from_date)
