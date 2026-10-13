"""Hermetic canaries for the PR-2b expired-contract history probe.

No real credentials and no network: the dry run must fail if a client is built,
and every refusal is exercised against the committed tenant calendar.
"""

import json
import os
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
import yaml

from tools.broker_probes.common import SafetyViolation, assert_read_only_call
from tools.tos_cp3 import expired_history_probe as e
from tools.tos_cp3 import minute_probe as p

CONFIG = p.ROOT / "config/tos_probes/cp3-pr2b-expired-20261014.yaml"
JUNCTION = date(2026, 10, 8)
TODAY = date(2026, 10, 14)


@pytest.fixture(autouse=True)
def preserve_process_umask():
    original = os.umask(0o077)
    os.umask(original)
    try:
        yield
    finally:
        os.umask(original)


def row(hour, close="100", volume="20", day="20261008"):
    return {
        "futs_bsop_date": day,
        "futs_cntg_hour": hour,
        "futs_oprc": close,
        "futs_hgpr": close,
        "futs_lwpr": close,
        "futs_prpr": close,
        "cntg_vol": volume,
    }


def base_config():
    return yaml.safe_load(CONFIG.read_text())


def test_no_network_dry_run(monkeypatch, capsys):
    monkeypatch.setattr(
        p.httpx.Client,
        "__init__",
        lambda *a, **k: pytest.fail("network client created"),
    )

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 14, 10, tzinfo=e.KST)

    monkeypatch.setattr(e, "datetime", Clock)
    assert e.main(["--config", str(CONFIG)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["mode"] == "DRY_RUN"
    assert printed["method"] == "GET"
    assert printed["orders"] == 0
    assert printed["expired_symbol"] == "A05610"
    assert printed["successor_symbol"] == "A05611"
    # five A05610 sessions, newest first, plus the successor leg on the junction
    assert printed["requests"] == [
        "A05610 2026-10-08",
        "A05610 2026-10-07",
        "A05610 2026-10-06",
        "A05610 2026-10-02",
        "A05610 2026-10-01",
        "A05611 2026-10-08",
    ]


def test_committed_plan_walks_the_front_month_resolver():
    plan = e.resolve_plan(base_config(), today=TODAY)
    assert plan["expired_symbol"] == "A05610"
    assert plan["successor_symbol"] == "A05611"
    # the junction is dated by the walk, not recomputed from get_expiry_date
    assert plan["successor_first_session"] == date(2026, 10, 12)
    assert plan["junction_day"] == JUNCTION


def test_symbols_come_from_the_resolver_and_not_from_a_literal(monkeypatch):
    """Red proof for the test above: it passes on hardcoded symbols too.

    §3.2a requires the contract per session to come from the SAME front-month
    resolver the producer uses. Replacing that resolver must move every symbol
    in the plan, and it must be asked for the right (product, date) pairs.
    """
    asked = []

    def fake(*, product, target_date):
        asked.append((product, target_date))
        return "ZZ001" if target_date <= JUNCTION else "ZZ002"

    monkeypatch.setattr(e, "get_front_month_code", fake)
    plan = e.resolve_plan(base_config(), today=TODAY)
    assert plan["expired_symbol"] == "ZZ001"
    assert plan["successor_symbol"] == "ZZ002"
    assert [symbol for symbol, _ in plan["requests"]] == ["ZZ001"] * 5 + ["ZZ002"]
    # mini only, and the successor is asked for the junction's NEXT trading day
    assert {product for product, _ in asked} == {"mini"}
    assert set(asked) == {
        ("mini", JUNCTION),
        ("mini", date(2026, 10, 7)),
        ("mini", date(2026, 10, 6)),
        ("mini", date(2026, 10, 2)),
        ("mini", date(2026, 10, 1)),
        ("mini", date(2026, 10, 12)),
    }


@pytest.mark.parametrize(
    "mutate,reason",
    [
        ({"seed_days": ["2026-10-05"]}, "not a trading day"),  # 대체휴일
        ({"seed_days": ["2026-10-03"]}, "not a trading day"),  # Saturday
        ({"junction_day": "2026-10-09"}, "not a trading day"),  # 한글날
        ({"seed_days": ["2026-10-14"]}, "unfinished session"),  # today
        ({"seed_days": ["2026-10-15"]}, "unfinished session"),  # future
        ({"seed_days": ["2026-10-12"]}, "not before the junction"),
        ({"seed_days": ["2026-09-04"]}, "spans more than one contract junction"),
        (
            {"junction_day": "2026-10-07", "seed_days": ["2026-10-06"]},
            "no contract junction",
        ),
        ({"seed_days": ["2025-10-07"]}, "outside tenant calendar coverage"),
    ],
)
def test_plan_refuses_a_response_that_would_be_empty_for_another_reason(mutate, reason):
    cfg = base_config()
    cfg.update(mutate)
    with pytest.raises(RuntimeError, match=reason):
        e.resolve_plan(cfg, today=TODAY)


def test_mutations_rejected_before_transport():
    """The reused allowlist admits no order path and no non-GET method."""
    for method, path, tr in [
        ("POST", e.QUOTE_PATH, e.TR),
        ("GET", "/uapi/domestic-futureoption/v1/trading/order", e.TR),
        ("GET", e.QUOTE_PATH, "TTTO1101U"),
    ]:
        with pytest.raises(SafetyViolation):
            assert_read_only_call(method, p.REAL_BASE_URL + path, tr, p.ALLOWLIST)


def test_broker_statuses_keep_classes_and_never_msg1(tmp_path):
    rec = p.Recorder(tmp_path / "capture")
    params = {"FID_INPUT_ISCD": "A05610", "FID_INPUT_DATE_1": "20261008"}
    rec.event(
        {"params": params, "rt_cd": "1", "msg_cd": "EGW00123", "http_status": 500}
    )
    rec.event({"params": params, "error": "auth_http_or_json_error"})
    rec.event({"params": params, "rt_cd": "0", "msg_cd": None, "http_status": 200})
    rec.event(
        {
            "params": {"FID_INPUT_ISCD": "A05611", "FID_INPUT_DATE_1": "20261008"},
            "rt_cd": "0",
            "http_status": 200,
        }
    )
    status = e.broker_statuses(rec.output, "A05610", JUNCTION)
    assert status == {
        "pages": 2,
        "rt_cd": ["0", "1"],
        "msg_cd": ["EGW00123"],
        "http_status": [200, 500],
        "transport_errors": ["auth_http_or_json_error"],
    }


def test_transport_records_msg_cd_class_without_msg1(tmp_path, monkeypatch):
    """A refusal has to be nameable from the artifact; its text must not be."""
    from collections import deque

    import httpx

    replies = deque(
        [
            (
                200,
                {
                    "rt_cd": "1",
                    "msg_cd": "EGW00121",
                    "msg1": "조회할 자료가 없습니다",
                    "output2": [],
                },
            )
        ]
    )

    class HTTP:
        def get(self, url, *, headers, params):
            status, body = replies.popleft()
            return httpx.Response(status, json=body, request=httpx.Request("GET", url))

    quote = p.Quotes.__new__(p.Quotes)
    quote.auth = SimpleNamespace(get_token=lambda: "token", invalidate=lambda: None)
    quote.http = HTTP()
    quote.creds = SimpleNamespace(app_key="fake-key", app_secret="fake-secret")
    quote.recorder = p.Recorder(tmp_path / "capture")
    quote.cfg = {"attempts": 1, "pace_s": 0, "retry_pause_s": 0}
    quote.calls, quote.last = 0, 0
    monkeypatch.setattr(p.time, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError, match="broker_response"):
        quote.page("A05610", JUNCTION)
    log = (quote.recorder.output / "requests.jsonl").read_text()
    assert "EGW00121" in log
    assert "자료가 없습니다" not in log
    assert e.broker_statuses(quote.recorder.output, "A05610", JUNCTION)["msg_cd"] == [
        "EGW00121"
    ]


def test_session_report_records_a_refusal_instead_of_failing(tmp_path):
    rec = p.Recorder(tmp_path / "capture")

    class Quotes:
        calls = 0

        def history(self, symbol, day):
            raise RuntimeError("broker_response")

    report, parsed = e.session_report(Quotes(), rec, "A05610", JUNCTION)
    assert parsed == []
    assert report["fetch_error"] == "broker_response"
    assert report["raw_rows"] == 0
    assert report["parsed_bars"] == 0
    assert report["density_pass"] is False
    assert report["raw_last_kst"] is None


def test_session_report_shape_edges_and_density_gate(tmp_path):
    rec = p.Recorder(tmp_path / "capture")
    rows = [row(f"{8 + m // 60:02d}{m % 60:02d}00") for m in range(45, 45 + 400)]
    rows.append(row("090000", volume="1"))  # below the §3.3 floor, same minute
    rows.append(row("090000", day="20261007"))  # another day: never counted

    class Quotes:
        def history(self, symbol, day):
            return rows

    report, parsed = e.session_report(Quotes(), rec, "A05610", JUNCTION)
    assert report["raw_rows"] == 401
    assert report["raw_first_kst"] == "08:45"[:5] + ":00"
    assert report["raw_last_kst"] == "15:24:00"
    assert report["parsed_bars"] == len(parsed) == 400
    assert report["density_gate"] == 330
    assert report["density_pass"] is True
    assert "cntg_vol" in report["raw_row_keys"]
    assert report["parsed_last_kst"] == "15:24"


def bars(symbol, closes, volume=20):
    return [
        (
            symbol,
            datetime(2026, 10, 8, 14, 16) + timedelta(minutes=i),
            close,
            close,
            close,
            close,
            volume,
        )
        for i, close in enumerate(closes)
    ]


def test_c_x100_comes_from_the_last_common_parsed_minute():
    expired = bars("A05610", [340.02, 340.04, 340.06])
    successor = bars("A05611", [340.52, 340.54, 340.56, 340.98, 341.00])
    align = e.junction_alignment(expired, successor)
    assert align["last_common_minute_kst"] == "14:18"
    assert align["expired_close_x100"] == 34006
    assert align["successor_close_x100"] == 34056
    assert align["c_x100"] == 50
    assert align["c_x100_is_even"] is True
    # the expiring leg stopped first; the successor's own last close is not used
    assert align["successor_last_parsed_kst"] == "14:20"
    assert align["last_common_is_expired_last"] is True
    assert align["last_common_is_successor_last"] is False


def test_no_common_minute_is_reported_not_invented():
    align = e.junction_alignment(bars("A05610", [340.0]), [])
    assert align["c_x100"] is None
    assert align["common_parsed_minutes"] == 0
    assert e.spread_window([], [], "14:16", None)["minutes_used"] == 0


def test_spread_window_is_bounded_by_the_common_minute():
    expired = bars("A05610", [340.02, 340.04, 340.06, 340.08])
    successor = bars("A05611", [340.52, 340.58, 340.50, 340.90])
    window = e.spread_window(expired, successor, "14:16", "14:18")
    assert window["minutes_used"] == 3
    assert window["spread_x100_min"] == 44
    assert window["spread_x100_max"] == 54
    assert window["spread_x100_range"] == 10
    assert window["min_volume_observed"] == 20
    assert window["window_end_kst"] == "14:18"


def test_confirmed_flow_writes_derived_artifacts_without_network(tmp_path, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 14, 19, tzinfo=e.KST)

    served = {
        ("A05610", JUNCTION): bars("A05610", [340.02, 340.04]),
        ("A05611", JUNCTION): bars("A05611", [340.52, 340.56]),
    }

    class FakeQuotes:
        calls = 11
        http = SimpleNamespace(close=lambda: None)

        def __init__(self, *args):
            pass

        def history(self, symbol, day):
            if (symbol, day) in served:
                return [
                    row(
                        bar[1].strftime("%H%M%S"),
                        close=str(bar[5]),
                        day=day.strftime("%Y%m%d"),
                    )
                    for bar in served[(symbol, day)]
                ]
            return []

    cfg = base_config()
    cfg["env_file"] = str(tmp_path / "env")
    cfg["output"] = str(tmp_path / "capture")
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(cfg))
    for key, value in {
        "KIS_FUTURES_APP_KEY": "fake",
        "KIS_FUTURES_APP_SECRET": "fake",
        **cfg["parser_env"],
    }.items():
        monkeypatch.setenv(key, str(value))
    monkeypatch.setattr(e, "datetime", Clock)
    monkeypatch.setattr(e, "Quotes", FakeQuotes)
    monkeypatch.setattr(
        e,
        "read_explicit_dotenv",
        lambda *a, **k: {
            "KIS_FUTURES_APP_KEY": "fake",
            "KIS_FUTURES_APP_SECRET": "fake",
        },
    )
    assert e.main(["--config", str(config), "--confirm"]) == 0
    out = tmp_path / "capture"
    summary = json.loads((out / "summary.json").read_text())
    assert summary["orders"] == 0
    assert summary["requests"] == 11
    assert summary["expired_history_served"] is True
    assert summary["expired_sessions_requested"] == 5
    assert summary["expired_sessions_with_bars"] == 1
    assert summary["expired_sessions_passing_density"] == 0
    assert json.loads((out / "junction.json").read_text())["c_x100"] == 52
    assert len(json.loads((out / "sessions.json").read_text())) == 6
    assert json.loads((out / "sha256.json").read_text())["summary.json"]
    assert not (out / "abort.json").exists()


def test_empty_expired_history_is_the_answer_not_an_abort(tmp_path, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 14, 19, tzinfo=e.KST)

    class FakeQuotes:
        calls = 6
        http = SimpleNamespace(close=lambda: None)

        def __init__(self, *args):
            pass

        def history(self, symbol, day):
            if symbol == "A05610":
                return []
            return [row("141600", close="340.52")]

    cfg = base_config()
    cfg["env_file"] = str(tmp_path / "env")
    cfg["output"] = str(tmp_path / "capture")
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(cfg))
    for key, value in {
        "KIS_FUTURES_APP_KEY": "fake",
        "KIS_FUTURES_APP_SECRET": "fake",
        **cfg["parser_env"],
    }.items():
        monkeypatch.setenv(key, str(value))
    monkeypatch.setattr(e, "datetime", Clock)
    monkeypatch.setattr(e, "Quotes", FakeQuotes)
    monkeypatch.setattr(
        e,
        "read_explicit_dotenv",
        lambda *a, **k: {
            "KIS_FUTURES_APP_KEY": "fake",
            "KIS_FUTURES_APP_SECRET": "fake",
        },
    )
    assert e.main(["--config", str(config), "--confirm"]) == 0
    out = tmp_path / "capture"
    summary = json.loads((out / "summary.json").read_text())
    assert summary["expired_history_served"] is False
    assert summary["expired_sessions_with_bars"] == 0
    assert summary["orders"] == 0
    assert json.loads((out / "junction.json").read_text())["c_x100"] is None
    assert not (out / "abort.json").exists()
