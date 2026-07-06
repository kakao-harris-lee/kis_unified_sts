"""Neutral KOSPI futures contract-code helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

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


def get_front_expiry_month(
    product: str = "kospi200",
    target_date: date | None = None,
) -> tuple[int, int]:
    """Return the ``(year, month)`` of the current front contract's expiry.

    KOSPI200 (full) lists quarterly (Mar/Jun/Sep/Dec); mini lists monthly. The
    front contract is the nearest not-yet-expired listing on ``target_date``
    (once ``target_date`` passes an expiry, the front rolls to the next month).
    """
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
        return y, m

    y, m = target_date.year, target_date.month
    expiry = get_expiry_date(y, m)
    if target_date > expiry:
        m += 1
        if m > 12:
            m = 1
            y += 1
    return y, m


def get_next_expiry_month(
    product: str = "kospi200",
    target_date: date | None = None,
) -> tuple[int, int]:
    """Return the ``(year, month)`` of the deferred (next) contract's expiry.

    The deferred contract is the listing immediately after the current front
    (next quarterly for full, next calendar month for mini).
    """
    front_year, front_month = get_front_expiry_month(product, target_date)
    if product == "kospi200":
        quarterly_months = [3, 6, 9, 12]
        idx = quarterly_months.index(front_month) + 1
        if idx >= len(quarterly_months):
            return front_year + 1, quarterly_months[0]
        return front_year, quarterly_months[idx]

    month = front_month + 1
    year = front_year
    if month > 12:
        month = 1
        year += 1
    return year, month


def get_next_month_code(
    product: str = "kospi200",
    target_date: date | None = None,
    legacy: bool = True,
) -> str:
    """Return the deferred (next) contract code for the product."""
    y, m = get_next_expiry_month(product, target_date)
    if product == "kospi200":
        prefix = KOSPI200_LEGACY_PREFIX if legacy else KOSPI200_PREFIX
    else:
        prefix = KOSPI_MINI_LEGACY_PREFIX if legacy else KOSPI_MINI_PREFIX
    return make_code(y, m, prefix=prefix, legacy=legacy)


# ---------------------------------------------------------------------------
# Contract / roll state (read-model — see docs/plans/
# 2026-07-05-futures-market-context-hedge-risk-hardening.md §4.1)
# ---------------------------------------------------------------------------

RollState = Literal["normal", "pre_roll", "roll_required", "expired", "unknown"]


@dataclass(frozen=True)
class FuturesContractState:
    """Front/next/night contract + roll status for one product (I/O-free).

    Deterministic and dependency-injected: callers pass ``target_date`` and the
    roll-window thresholds; the night symbol is optional (resolved elsewhere
    from the KRX night master and passed in). Redis/stream/ledger glue lives in
    :mod:`services.futures_contract.main`.
    """

    schema_version: int
    product: str
    front_symbol: str
    next_symbol: str
    night_front_symbol: str | None
    night_next_symbol: str | None
    expiry_date: date
    next_expiry_date: date
    days_to_expiry: int
    roll_state: RollState
    roll_reason: str
    new_entry_front_allowed: bool
    hedge_front_allowed: bool
    source: str
    asof_ts: datetime


#: Schema version published in the ``futures:contract:latest`` contract.
CONTRACT_STATE_SCHEMA_VERSION = 1

#: Product key → (front-code product arg, legacy flag) for code generation.
_PRODUCT_CODE_ARGS: dict[str, tuple[str, bool]] = {
    "mini": ("mini", True),
    "kospi200": ("kospi200", True),
}


def compute_contract_state(
    *,
    product: str,
    target_date: date,
    asof_ts: datetime,
    pre_roll_days: int,
    block_front_new_entries_days: int,
    require_roll_on_expiry_day: bool,
    night_front_symbol: str | None = None,
    night_next_symbol: str | None = None,
    night_required: bool = False,
    source: str = "calendar",
    legacy_codes: bool = True,
) -> FuturesContractState:
    """Classify roll state and front/next/night codes for ``target_date``.

    Roll policy (docs §4.1):

    * ``days_to_expiry > pre_roll_days`` → ``normal`` (front new-entry + hedge OK).
    * ``block_front_new_entries_days < dte <= pre_roll_days`` → ``pre_roll``
      (front new-entry warned/allowed by mode, hedge still OK).
    * ``0 < dte <= block_front_new_entries_days`` → ``roll_required`` (front
      new-entry blocked; hedge should use next / no-op).
    * ``dte <= 0`` (or expiry day when ``require_roll_on_expiry_day``) →
      ``expired`` (front new-entry + hedge blocked; exit/roll advisory).
    * missing night master when ``night_required`` → ``unknown`` (live
      fail-closed downstream; paper fail-open trace).

    ``days_to_expiry`` is calendar days from ``target_date`` to the front
    expiry (KST trade date basis).
    """
    if product not in _PRODUCT_CODE_ARGS:
        raise ValueError(f"Unsupported product: {product!r}")
    code_product, legacy = _PRODUCT_CODE_ARGS[product]
    legacy = legacy and legacy_codes

    front_year, front_month = get_front_expiry_month(code_product, target_date)
    next_year, next_month = get_next_expiry_month(code_product, target_date)
    expiry = get_expiry_date(front_year, front_month)
    next_expiry = get_expiry_date(next_year, next_month)
    days_to_expiry = (expiry - target_date).days

    front_symbol = get_front_month_code(
        product=code_product, target_date=target_date, legacy=legacy
    )
    next_symbol = get_next_month_code(
        product=code_product, target_date=target_date, legacy=legacy
    )

    night_missing = night_required and not night_front_symbol

    if night_missing:
        roll_state: RollState = "unknown"
        roll_reason = "missing_master"
        new_entry_front_allowed = False
        hedge_front_allowed = False
    elif days_to_expiry < 0 or (require_roll_on_expiry_day and days_to_expiry <= 0):
        roll_state = "expired"
        roll_reason = f"days_to_expiry<={0}"
        new_entry_front_allowed = False
        hedge_front_allowed = False
    elif days_to_expiry <= block_front_new_entries_days:
        roll_state = "roll_required"
        roll_reason = f"days_to_expiry<={block_front_new_entries_days}"
        new_entry_front_allowed = False
        hedge_front_allowed = False
    elif days_to_expiry <= pre_roll_days:
        roll_state = "pre_roll"
        roll_reason = f"days_to_expiry<={pre_roll_days}"
        new_entry_front_allowed = True
        hedge_front_allowed = True
    else:
        roll_state = "normal"
        roll_reason = "days_to_expiry>pre_roll"
        new_entry_front_allowed = True
        hedge_front_allowed = True

    return FuturesContractState(
        schema_version=CONTRACT_STATE_SCHEMA_VERSION,
        product=product,
        front_symbol=front_symbol,
        next_symbol=next_symbol,
        night_front_symbol=night_front_symbol or None,
        night_next_symbol=night_next_symbol or None,
        expiry_date=expiry,
        next_expiry_date=next_expiry,
        days_to_expiry=days_to_expiry,
        roll_state=roll_state,
        roll_reason=roll_reason,
        new_entry_front_allowed=new_entry_front_allowed,
        hedge_front_allowed=hedge_front_allowed,
        source=source,
        asof_ts=asof_ts,
    )


def contract_state_to_fields(state: FuturesContractState) -> dict[str, str]:
    """Flatten a contract state into the ``futures:contract:latest`` hash.

    Absent optional values (night symbols) publish as ``""`` (the repo's null
    marker), mirroring the market-risk/hedge Redis contracts.
    """
    return {
        "schema_version": str(state.schema_version),
        "product": state.product,
        "front_symbol": state.front_symbol,
        "next_symbol": state.next_symbol,
        "night_front_symbol": state.night_front_symbol or "",
        "night_next_symbol": state.night_next_symbol or "",
        "expiry_date": state.expiry_date.isoformat(),
        "next_expiry_date": state.next_expiry_date.isoformat(),
        "days_to_expiry": str(state.days_to_expiry),
        "roll_state": state.roll_state,
        "roll_reason": state.roll_reason,
        "new_entry_front_allowed": "true" if state.new_entry_front_allowed else "false",
        "hedge_front_allowed": "true" if state.hedge_front_allowed else "false",
        "source": state.source,
        "asof_ts": state.asof_ts.isoformat(),
    }


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
