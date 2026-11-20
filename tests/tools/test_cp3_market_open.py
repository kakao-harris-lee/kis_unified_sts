"""The CP-3 cron market-open gate (#1143) — KIS 개장일여부, its cache, and the fallback."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3.ops import market_open as mo

_HOLIDAY = "2026-12-25"
_OPEN_DAY = "2026-11-20"
_SATURDAY = "2026-11-21"
_NEXT_YEAR = "2027-01-04"  # a Monday in a year the calendars do not list

_CALENDAR = f"""calendar_version: "t"
holidays:
  - "{_HOLIDAY}"
sessions:
  krx-stock:
    - {{phase: CONTINUOUS, start: "09:00", end: "15:30", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}}
"""

_PRODUCER = "env_file: /nonexistent/.env.real\nmarket: stock\n"


def _calendar(tmp_path: Path, body: str = _CALENDAR) -> Path:
    path = tmp_path / "calendar.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _producer(tmp_path: Path, body: str = _PRODUCER) -> Path:
    path = tmp_path / "producer.yaml"
    path.write_text(body, encoding="utf-8")
    return path


class _Fetch:
    """Stands in for the one broker call, and counts it."""

    def __init__(self, answer: str | Exception) -> None:
        self.answer = answer
        self.days: list[date] = []

    def __call__(self, day: date, **_kwargs: Any) -> str:
        self.days.append(day)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _argv(tmp_path: Path, day: str, *extra: str) -> list[str]:
    return [
        "--date",
        day,
        "--calendar",
        str(_calendar(tmp_path)),
        "--cache-dir",
        str(tmp_path / "cache"),
        "--producer-config",
        str(_producer(tmp_path)),
        "--repo-root",
        str(tmp_path),
        *extra,
    ]


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    day: str,
    fetch: _Fetch,
    *extra: str,
) -> int:
    monkeypatch.setattr(mo, "fetch_opnd_yn", fetch)
    return mo.main(_argv(tmp_path, day, *extra))


def _no_call() -> _Fetch:
    return _Fetch(AssertionError("the broker was called"))


# ---------------------------------------------------------------- the verdict --


def test_the_tr_and_path_are_the_official_holiday_enquiry() -> None:
    """A typo here would send the real key at another endpoint."""
    assert mo.HOLIDAY_TR == "CTCA0903R"
    assert mo.HOLIDAY_PATH == "/uapi/domestic-stock/v1/quotations/chk-holiday"


def test_a_weekend_skips_without_asking_the_broker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fetch = _no_call()
    assert _run(monkeypatch, tmp_path, _SATURDAY, fetch) == mo.EXIT_CLOSED
    assert fetch.days == []
    assert capsys.readouterr().out.strip() == "weekend"


def test_a_listed_holiday_skips_without_asking_the_broker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The 「알려진 휴일」 of the operator's 11-20 quote: the calendar still answers them,"""
    fetch = _no_call()
    assert _run(monkeypatch, tmp_path, _HOLIDAY, fetch) == mo.EXIT_CLOSED
    assert fetch.days == []
    assert "lists this date closed" in capsys.readouterr().out


def test_an_extra_closed_date_skips_without_asking_the_broker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fetch = _no_call()
    rc = _run(
        monkeypatch, tmp_path, _OPEN_DAY, fetch, "--extra-closed", f"x {_OPEN_DAY}"
    )
    assert rc == mo.EXIT_CLOSED
    assert fetch.days == []
    assert "CP3_DAILY_EXTRA_CLOSED" in capsys.readouterr().out


def test_opnd_yn_y_runs_the_day(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fetch = _Fetch("Y")
    assert _run(monkeypatch, tmp_path, _OPEN_DAY, fetch) == mo.EXIT_OPEN
    assert fetch.days == [date.fromisoformat(_OPEN_DAY)]
    assert "opnd_yn=Y (chk-holiday)" in capsys.readouterr().out


def test_opnd_yn_n_skips_the_day(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unlisted KRX closure — the day the old year-coverage refusal could not see."""
    fetch = _Fetch("N")
    assert _run(monkeypatch, tmp_path, _OPEN_DAY, fetch) == mo.EXIT_CLOSED
    assert "opnd_yn=N" in capsys.readouterr().out


def test_an_unreadable_broker_falls_back_to_the_calendar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fetch = _Fetch(mo.MarketOpenUnreadable("timeout"))
    assert _run(monkeypatch, tmp_path, _OPEN_DAY, fetch) == mo.EXIT_OPEN
    out = capsys.readouterr().out
    assert "KIS unreadable (timeout)" in out and "calendar fallback" in out


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Y", mo.EXIT_OPEN),
        ("N", mo.EXIT_CLOSED),
        (mo.MarketOpenUnreadable("no credentials"), mo.EXIT_OPEN),
    ],
)
def test_1143_a_year_the_calendar_does_not_list_is_no_longer_a_refusal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    answer: str | Exception,
    expected: int,
) -> None:
    """The failing input #1143 names: 2027-01-04 against 2026-only holidays. The old"""
    assert _run(monkeypatch, tmp_path, _NEXT_YEAR, _Fetch(answer)) == expected


def test_an_empty_holiday_list_is_read_not_refused(tmp_path: Path) -> None:
    assert mo.load_holidays(_calendar(tmp_path, "holidays: []\n")) == frozenset()
    assert mo.load_holidays(_calendar(tmp_path, "sessions: {}\n")) == frozenset()


@pytest.mark.parametrize("broken", ["absent.yaml", "", "list.yaml", "bad.yaml"])
def test_an_unreadable_calendar_is_an_error_not_a_skip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, broken: str
) -> None:
    """Only exit 10 may become a silent SKIP — a calendar nobody can read is exit 2."""
    monkeypatch.setattr(mo, "fetch_opnd_yn", _no_call())
    (tmp_path / "list.yaml").write_text("- 2026-12-25\n", encoding="utf-8")
    (tmp_path / "bad.yaml").write_text("holidays: 2026-12-25\n", encoding="utf-8")
    argv = _argv(tmp_path, _OPEN_DAY)
    argv[argv.index("--calendar") + 1] = str(tmp_path / broken)
    assert mo.main(argv) == mo.EXIT_ERROR


# ------------------------------------------------------------------ the cache --


def test_the_days_answer_is_cached_so_the_next_tenant_calls_nobody(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Five tenants' cron lines a day, one KIS call — 「가급적 1일 1회 호출」."""
    first = _Fetch("Y")
    assert _run(monkeypatch, tmp_path, _OPEN_DAY, first) == mo.EXIT_OPEN
    capsys.readouterr()
    cached = json.loads(
        (tmp_path / "cache" / "20261120.json").read_text(encoding="utf-8")
    )
    assert cached["bass_dt"] == "20261120" and cached["opnd_yn"] == "Y"
    assert cached["tr_id"] == mo.HOLIDAY_TR

    second = _no_call()
    assert _run(monkeypatch, tmp_path, _OPEN_DAY, second) == mo.EXIT_OPEN
    assert second.days == []
    assert "(cached)" in capsys.readouterr().out


def test_another_days_cache_file_is_not_read_for_this_day(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "20261120.json").write_text(
        json.dumps({"bass_dt": "20261119", "opnd_yn": "N"}), encoding="utf-8"
    )
    fetch = _Fetch("Y")
    assert _run(monkeypatch, tmp_path, _OPEN_DAY, fetch) == mo.EXIT_OPEN
    assert fetch.days == [date.fromisoformat(_OPEN_DAY)]


def test_a_junk_cache_file_is_ignored_not_trusted(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    day = date.fromisoformat(_OPEN_DAY)
    for body in ("{", "[]", json.dumps({"bass_dt": "20261120", "opnd_yn": "maybe"})):
        (cache / "20261120.json").write_text(body, encoding="utf-8")
        assert mo.read_cached(cache, day) is None


def test_cache_only_never_asks_the_broker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--preflight` is read-only: it may not spend the day's one KIS call."""
    fetch = _no_call()
    assert _run(monkeypatch, tmp_path, _OPEN_DAY, fetch, "--cache-only") == mo.EXIT_OPEN
    assert fetch.days == []
    assert not (tmp_path / "cache" / "20261120.json").exists()
    assert "--cache-only" in capsys.readouterr().out

    monkeypatch.setattr(mo, "fetch_opnd_yn", _Fetch("N"))
    assert mo.main(_argv(tmp_path, _OPEN_DAY)) == mo.EXIT_CLOSED
    capsys.readouterr()
    rc = mo.main(_argv(tmp_path, _OPEN_DAY, "--cache-only"))
    assert rc == mo.EXIT_CLOSED
    assert "(cached)" in capsys.readouterr().out


# ------------------------------------------------------------------- the body --


@pytest.mark.parametrize("answer", ["Y", "N"])
def test_the_row_for_the_asked_date_is_the_one_read(answer: str) -> None:
    body = {
        "rt_cd": "0",
        "output": [
            {"bass_dt": "20261120", "opnd_yn": answer, "bzdy_yn": answer},
            {"bass_dt": "20261121", "opnd_yn": "N", "bzdy_yn": "N"},
        ],
    }
    assert mo.opnd_yn_of(body, date(2026, 11, 20), status=200) == answer
    assert mo.opnd_yn_of(body, date(2026, 11, 21), status=200) == "N"


def test_a_single_output_mapping_is_read_too() -> None:
    body = {"rt_cd": "0", "output": {"bass_dt": "20261120", "opnd_yn": "Y"}}
    assert mo.opnd_yn_of(body, date(2026, 11, 20), status=200) == "Y"


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (500, {"rt_cd": "0", "output": [{"bass_dt": "20261120", "opnd_yn": "Y"}]}),
        (200, {"rt_cd": "1", "msg_cd": "EGW00123", "output": []}),
        (200, {"rt_cd": "0"}),
        (200, {"rt_cd": "0", "output": [{"bass_dt": "20261121", "opnd_yn": "Y"}]}),
        (200, {"rt_cd": "0", "output": [{"bass_dt": "20261120", "opnd_yn": ""}]}),
        (200, {"rt_cd": "0", "output": [{"bass_dt": "20261120", "opnd_yn": "?"}]}),
    ],
)
def test_anything_but_a_y_or_n_for_this_date_is_unreadable(
    status: int, body: dict[str, Any]
) -> None:
    with pytest.raises(mo.MarketOpenUnreadable):
        mo.opnd_yn_of(body, date(2026, 11, 20), status=status)


# ------------------------------------------------------------- the real call --


class _Auth:
    def __init__(self, config: Any, use_singleton: bool = True) -> None:
        self.config = config

    def get_token(self) -> str:
        return "token-placeholder"


def test_fetch_issues_one_get_of_the_holiday_tr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The transport, with only the HTTP boundary faked: GET, the TR, BASS_DT, no body."""
    from shared.config import dotenv_guard
    from shared.kis import auth as kis_auth
    from tools.broker_probes import common

    # SAFETY: setenv (not a bare os.environ write) so the placeholder credentials this
    # test puts where resolve_credentials reads cannot outlive it.
    for key in mo.CREDENTIAL_KEYS:
        monkeypatch.setenv(key, "placeholder")
    monkeypatch.setattr(
        dotenv_guard,
        "read_explicit_dotenv",
        lambda path, *, keys: dict.fromkeys(keys, "placeholder"),
    )
    monkeypatch.setattr(kis_auth, "KISAuthManager", _Auth)
    seen: list[tuple[str, str, dict[str, Any], Any]] = []

    def fake_http_json(
        session: Any,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> tuple[int, dict[str, Any], float, str]:
        seen.append((method, url, dict(params or {}), json_body))
        assert headers["tr_id"] == mo.HOLIDAY_TR
        return (
            200,
            {"rt_cd": "0", "output": [{"bass_dt": "20261120", "opnd_yn": "Y"}]},
            1.0,
            "",
        )

    monkeypatch.setattr(common, "http_json", fake_http_json)
    answer = mo.fetch_opnd_yn(
        date(2026, 11, 20),
        env_file=tmp_path / ".env.real",
        token_cache_dir=tmp_path / "token",
    )
    assert answer == "Y"
    assert len(seen) == 1
    method, url, params, json_body = seen[0]
    assert method == "GET" and json_body is None
    assert url == common.REAL_BASE_URL + mo.HOLIDAY_PATH
    assert params == {"BASS_DT": "20261120", "CTX_AREA_FK": "", "CTX_AREA_NK": ""}


def test_a_credential_file_without_the_keys_is_unreadable_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from shared.config import dotenv_guard

    monkeypatch.setattr(dotenv_guard, "read_explicit_dotenv", lambda path, *, keys: {})
    with pytest.raises(mo.MarketOpenUnreadable, match="KIS_STOCK_APP_KEY"):
        mo.fetch_opnd_yn(
            date(2026, 11, 20),
            env_file=tmp_path / ".env.real",
            token_cache_dir=tmp_path / "token",
        )


def test_env_file_of_reads_the_producers_own_setting(tmp_path: Path) -> None:
    absolute = _producer(tmp_path, "env_file: /srv/keys/.env.real\n")
    assert mo.env_file_of(absolute, repo_root=tmp_path) == Path("/srv/keys/.env.real")
    relative = _producer(tmp_path, "env_file: .env.real\n")
    assert mo.env_file_of(relative, repo_root=tmp_path) == tmp_path / ".env.real"


@pytest.mark.parametrize("body", ["market: stock\n", "[]\n", "env_file: 3\n"])
def test_a_producer_config_without_an_env_file_is_unreadable(
    tmp_path: Path, body: str
) -> None:
    with pytest.raises(mo.MarketOpenUnreadable):
        mo.env_file_of(_producer(tmp_path, body), repo_root=tmp_path)


def test_a_missing_producer_config_is_unreadable(tmp_path: Path) -> None:
    with pytest.raises(mo.MarketOpenUnreadable):
        mo.env_file_of(tmp_path / "absent.yaml", repo_root=tmp_path)
