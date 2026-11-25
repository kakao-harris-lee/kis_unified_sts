#!/usr/bin/env python3
"""Is KRX open on one date? — the KIS 개장일여부, cached once a day, the calendar as fallback.

Issue #1143. The cron gate used to REFUSE to start when the tenant calendar
listed no holiday in the date's year. The calendars carry 2026 only, so from
2027-01-01 every tenant would have stopped until five YAML files were edited —
calendar maintenance was a live risk. Operator 2026-11-20: 「캘린더의 거래일을
미리 확인하고 관리할 이유가 있어? 그냥 정식적인 휴일 알려진 휴일 이외에 장이
열렸는지 매일 아침 체크해도 돼」. So the morning cron asks the broker, and the
calendar is only what answers when the broker cannot.

The order of decision — each step is final:

1. weekend                      -> CLOSED
2. ``--extra-closed``           -> CLOSED (the operator's own "not today")
3. the calendar's ``holidays``  -> CLOSED (the 「알려진 휴일」 the quote names)
4. KIS 국내휴장일조회 ``opnd_yn`` -> ``Y`` open · ``N`` closed
5. KIS unreadable               -> OPEN, because 1-3 did not name this day closed

Steps 1-3 run BEFORE the broker call on purpose: they are exactly the days
``tos_runtime``'s own calendar gate calls closed, so the cron gate and the
session it starts cannot disagree, and a known holiday costs no broker call.
Step 5 is the fallback the old year-coverage refusal replaced: an unlisted
weekday is a trading day.

Exit codes: 0 open · 10 closed by steps 1-3 · 11 closed by step 4 (``opnd_yn=N``) ·
anything else an error. 10 and 11 are both silent SKIPs for the session; the cron
wrapper tells them apart because only 11 — a closure nobody's calendar lists —
is worth one informational message a day.

GET only, REAL key, no order path. KIS asks for 「가급적 1일 1회 호출」, so the
day's answer is cached under ``--cache-dir`` and the five tenants' cron lines
share it under one ``flock``: one broker call per host per day.

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from tools.tos_cp3.session_day import SessionDayError, holidays_of

KST = ZoneInfo("Asia/Seoul")

HOLIDAY_PATH = "/uapi/domestic-stock/v1/quotations/chk-holiday"
HOLIDAY_TR = "CTCA0903R"

# The STOCK real key for every tenant, futures included: chk-holiday is a
# domestic-STOCK quotation TR, and the answer is one market-wide fact. All five
# producer configs name the same `env_file`, so this reads the same pair the stock
# producer does — and the day's cache means only the first cron line of the day
# resolves a credential at all.
APP_KEY_KEY = "KIS_STOCK_APP_KEY"
APP_SECRET_KEY = "KIS_STOCK_APP_SECRET"
CREDENTIAL_KEYS = (APP_KEY_KEY, APP_SECRET_KEY)

OPEN_YES = "Y"
OPEN_NO = "N"
OPND_VALUES = (OPEN_YES, OPEN_NO)

DEFAULT_TIMEOUT_S = 10.0

EXIT_OPEN = 0
EXIT_CLOSED = 10
# The BROKER closed the day, not the calendar: a weekday no tenant calendar lists
# and KRX did not open. Still a silent SKIP for the session, but the cron wrapper
# tells the operator once a day — an unlisted closure is the one they have no
# record of, and the only way the calendar gets the entry is someone noticing.
EXIT_CLOSED_UNLISTED = 11
EXIT_ERROR = 2


class MarketOpenUnreadable(RuntimeError):
    """The broker did not answer with a 개장일여부 this gate may act on."""


def load_holidays(path: Path) -> frozenset[date]:
    """The dates the tenant calendar declares closed. An EMPTY list is allowed."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise SessionDayError(f"{path}: not a YAML mapping")
    raw = data.get("holidays")
    if raw is None:
        return frozenset()
    if not isinstance(raw, list):
        raise SessionDayError(f"{path}: 'holidays' must be a list")
    # SAFETY: an empty or year-less 'holidays' is no longer a refusal (#1143) — it
    # only means the broker, not this file, decides the unlisted weekdays.
    return holidays_of({"holidays": raw}) if raw else frozenset()


def local_verdict(
    day: date, *, holidays: frozenset[date], extra_closed: frozenset[str]
) -> str | None:
    """Why *day* is closed without asking the broker, or ``None`` to go and ask."""
    if day.weekday() >= 5:
        return "weekend"
    if day.isoformat() in extra_closed:
        return "extra closed date (CP3_DAILY_EXTRA_CLOSED)"
    if day in holidays:
        return "the tenant calendar lists this date closed"
    return None


def env_file_of(producer_config: Path, *, repo_root: Path) -> Path:
    """The ``env_file`` the producer config names — the one real-key source."""
    try:
        data = yaml.safe_load(producer_config.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise MarketOpenUnreadable(f"{producer_config} unreadable: {exc}") from exc
    # One key read with yaml.safe_load, never the producer's own loader: that one
    # validates every producer setting, so a fault in an unrelated field would be
    # reported here as a market-open fault (run_tenant_session.sh step 5b, same rule).
    if not isinstance(data, Mapping) or not isinstance(data.get("env_file"), str):
        raise MarketOpenUnreadable(f"{producer_config} carries no 'env_file' string")
    candidate = Path(str(data["env_file"])).expanduser()
    return candidate if candidate.is_absolute() else repo_root / candidate


def fetch_opnd_yn(
    day: date,
    *,
    env_file: Path,
    token_cache_dir: Path,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> str:
    """ONE GET of 국내휴장일조회 for *day*: ``"Y"`` or ``"N"``, else unreadable."""
    try:
        import requests

        from shared.config.dotenv_guard import read_explicit_dotenv
        from shared.kis.auth import KISAuthManager
        from tools.broker_probes.common import (
            REAL_BASE_URL,
            ProbeCredentials,
            ProbeError,
            ReadOnlyCall,
            assert_read_only_call,
            build_auth_config,
            http_json,
        )
    except ImportError as exc:  # a bare checkout: the calendar answers instead
        raise MarketOpenUnreadable(f"broker transport unavailable: {exc}") from exc

    url = REAL_BASE_URL + HOLIDAY_PATH
    # SAFETY: outside the try — a SafetyViolation here means this gate asked for a
    # call it may not make, which must stop the gate, never degrade to a fallback.
    assert_read_only_call(
        "GET",
        url,
        HOLIDAY_TR,
        (ReadOnlyCall(HOLIDAY_TR, HOLIDAY_PATH, "KIS 국내휴장일조회 (개장일여부)"),),
    )
    try:
        values = read_explicit_dotenv(env_file, keys=CREDENTIAL_KEYS)
        missing = [key for key in CREDENTIAL_KEYS if not values.get(key)]
        if missing:
            raise MarketOpenUnreadable(f"{env_file} carries no {', '.join(missing)}")
        # SAFETY: the pair goes STRAIGHT from the parsed file into the credential
        # object and is never written to `os.environ` (#1151 review). This function
        # is also called in-process by a probe that then sends 모의투자 ORDERS with
        # whatever the environment names (probes_stock_cancel.py::
        # assert_session_window), so a REAL key left in the environment would
        # become an order key. Nothing here starts a child either, so the runner's
        # credential separation (run_tenant_session.sh step 3) stays intact.
        creds = ProbeCredentials(
            app_key=values[APP_KEY_KEY],
            app_secret=values[APP_SECRET_KEY],
            # 개장일여부 is one market-wide fact: the TR carries no account field,
            # and an empty account cannot be mistaken for one that may be traded.
            account_no="",
            is_real=True,
            asset="stock",
        )
        auth = KISAuthManager(
            build_auth_config(creds, token_cache_dir), use_singleton=False
        )
        headers = {
            "authorization": "Bearer " + auth.get_token(),
            "appkey": creds.app_key,
            "appsecret": creds.app_secret,
            "tr_id": HOLIDAY_TR,
            "content-type": "application/json",
        }
        params = {
            "BASS_DT": day.strftime("%Y%m%d"),
            "CTX_AREA_FK": "",
            "CTX_AREA_NK": "",
        }
        with requests.Session() as session:
            status, parsed, _elapsed_ms, _text = http_json(
                session, "GET", url, headers=headers, params=params, timeout=timeout_s
            )
    # SAFETY: ImportError belongs here too — `read_explicit_dotenv` imports
    # `python-dotenv` INSIDE the call, so a checkout without it would otherwise
    # traceback out of this gate instead of falling back to «run» as promised.
    except (
        requests.RequestException,
        ProbeError,
        ValueError,
        OSError,
        ImportError,
    ) as exc:
        raise MarketOpenUnreadable(f"{type(exc).__name__}: {exc}") from exc
    return opnd_yn_of(parsed, day, status=status)


def opnd_yn_of(parsed: Mapping[str, Any], day: date, *, status: int) -> str:
    """*day*'s ``opnd_yn`` in a chk-holiday body. Never a guess — unreadable or Y/N."""
    if status != 200 or str(parsed.get("rt_cd")) != "0":
        raise MarketOpenUnreadable(
            f"http {status} rt_cd={parsed.get('rt_cd')} msg_cd={parsed.get('msg_cd')}"
        )
    rows = parsed.get("output")
    if isinstance(rows, Mapping):
        rows = [rows]
    if not isinstance(rows, list):
        raise MarketOpenUnreadable("chk-holiday body carries no 'output' rows")
    wanted = day.strftime("%Y%m%d")
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("bass_dt") or "").strip() != wanted:
            continue
        answer = str(row.get("opnd_yn") or "").strip().upper()
        if answer in OPND_VALUES:
            return answer
        raise MarketOpenUnreadable(f"opnd_yn={answer!r} is neither Y nor N")
    raise MarketOpenUnreadable(f"chk-holiday returned no row for BASS_DT={wanted}")


def cache_path(cache_dir: Path, day: date) -> Path:
    """The file holding *day*'s broker answer — one per date, shared by the tenants."""
    return cache_dir / f"{day:%Y%m%d}.json"


@contextmanager
def exclusive(cache_dir: Path) -> Iterator[None]:
    """Hold the cache lock: five cron lines make at most one broker call per day."""
    cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(cache_dir / ".lock", "w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_cached(cache_dir: Path, day: date) -> str | None:
    """*day*'s cached ``opnd_yn``, or ``None`` when there is no usable one."""
    try:
        payload = json.loads(cache_path(cache_dir, day).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, Mapping):
        return None
    if str(payload.get("bass_dt") or "") != day.strftime("%Y%m%d"):
        return None
    answer = str(payload.get("opnd_yn") or "").strip().upper()
    return answer if answer in OPND_VALUES else None


def write_cache(cache_dir: Path, day: date, answer: str) -> None:
    """Record *day*'s answer. A failed write costs the next tenant one broker call."""
    body = {
        "bass_dt": day.strftime("%Y%m%d"),
        "opnd_yn": answer,
        "tr_id": HOLIDAY_TR,
        "fetched_at_kst": datetime.now(KST).isoformat(timespec="seconds"),
    }
    target = cache_path(cache_dir, day)
    # SAFETY: os.replace, because `--cache-only` reads this file WITHOUT the lock —
    # a half-written file must never be a readable answer.
    staging = target.with_suffix(".json.partial")
    try:
        staging.write_text(
            json.dumps(body, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(staging, target)
    except OSError as exc:
        print(f"market_open: cache not written: {exc}", file=sys.stderr)


def broker_answer(
    day: date,
    *,
    cache_dir: Path,
    cache_only: bool,
    producer_config: Path | None,
    repo_root: Path,
    timeout_s: float,
) -> tuple[str | None, str]:
    """``("Y"|"N", source)``, or ``(None, why not)`` — then the calendar answers."""
    if cache_only or producer_config is None:
        # SAFETY: no lock and no mkdir on this branch — `--preflight` promises to write
        # nothing, and a lock file under the state dir would be a write.
        cached = read_cached(cache_dir, day)
        if cached is not None:
            return cached, "cached"
        return None, "no cached KIS answer (--cache-only: this call asks nobody)"
    with exclusive(cache_dir):
        cached = read_cached(cache_dir, day)
        if cached is not None:
            return cached, "cached"
        try:
            answer = fetch_opnd_yn(
                day,
                env_file=env_file_of(producer_config, repo_root=repo_root),
                token_cache_dir=cache_dir / "token",
                timeout_s=timeout_s,
            )
        except MarketOpenUnreadable as exc:
            return None, f"KIS unreadable ({exc})"
        write_cache(cache_dir, day, answer)
        return answer, "chk-holiday"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/tos_cp3/ops/market_open.py",
        description=(__doc__ or "").splitlines()[0],
    )
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--extra-closed", default="")
    parser.add_argument("--producer-config", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="read the day's cached answer, never issue a token or call KIS",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """stdout: ONE reason line. Exit 0 open · 10 closed · anything else an error."""
    args = build_parser().parse_args(argv)
    try:
        holidays = load_holidays(args.calendar)
    except (SessionDayError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"market_open: calendar unreadable: {exc}", file=sys.stderr)
        return EXIT_ERROR
    closed = local_verdict(
        args.date,
        holidays=holidays,
        extra_closed=frozenset(str(args.extra_closed).split()),
    )
    if closed is not None:
        print(closed)
        return EXIT_CLOSED
    answer, source = broker_answer(
        args.date,
        cache_dir=args.cache_dir,
        cache_only=args.cache_only,
        producer_config=args.producer_config,
        repo_root=args.repo_root,
        timeout_s=args.timeout_s,
    )
    if answer is None:
        print(f"{source}, calendar fallback: {args.date} is not a listed holiday")
        return EXIT_OPEN
    print(f"KIS 개장일여부 opnd_yn={answer} ({source})")
    return EXIT_OPEN if answer == OPEN_YES else EXIT_CLOSED_UNLISTED


if __name__ == "__main__":  # pragma: no cover - CLI
    sys.exit(main())
