"""KRXDataCollector 단위 테스트 (실 네트워크 없음).

2026-07-02 실측된 data.krx.co.kr 익명 outerLoader 경로
(MDCSTAT02203_OUT) 응답 구조를 fixture로 사용한다.
"""

import json
import logging
from datetime import datetime

import pytest

from shared.llm.collectors import KRXDataCollector
from shared.llm.config import LLMConfig

TARGET_DATE = "20260701"

# 실측 응답 봉투: 값은 콤마 포함 문자열(원 단위 순매수 거래대금).
# TRDVAL1~7 = 금융투자/보험/투신/사모/은행/기타금융/연기금 (기관 합산)
# TRDVAL8 = 기타법인, TRDVAL9 = 개인, TRDVAL10/11 = 외국인/기타외국인
INVESTOR_ROW_STK = {
    "TRD_DD": "2026/07/01",
    "TRDVAL1": "1,000",
    "TRDVAL2": "2,000",
    "TRDVAL3": "3,000",
    "TRDVAL4": "4,000",
    "TRDVAL5": "5,000",
    "TRDVAL6": "6,000",
    "TRDVAL7": "7,000",
    "TRDVAL8": "-1,500",
    "TRDVAL9": "-30,000",
    "TRDVAL10": "2,000",
    "TRDVAL11": "1,500",
    "TRDVAL_TOT": "0",
}
INVESTOR_FIXTURE_STK = {
    "output": [INVESTOR_ROW_STK],
    "CURRENT_DATETIME": "2026.07.02 PM 07:31:22",
}
# STK 기준: institution=28000, foreign=3500, retail=-30000, etc=-1500

INVESTOR_ROW_KSQ = dict(
    INVESTOR_ROW_STK,
    TRDVAL1="100",
    TRDVAL2="200",
    TRDVAL3="300",
    TRDVAL4="400",
    TRDVAL5="500",
    TRDVAL6="600",
    TRDVAL7="900",
    TRDVAL8="500",
    TRDVAL9="5,000",
    TRDVAL10="-1,000",
    TRDVAL11="-500",
)
INVESTOR_FIXTURE_KSQ = {
    "output": [INVESTOR_ROW_KSQ],
    "CURRENT_DATETIME": "2026.07.02 PM 07:31:22",
}
# KSQ 기준: institution=3000, foreign=-1500, retail=5000, etc=500


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        if text:
            self.text = text
        elif json_data is not None:
            self.text = json.dumps(json_data)
        else:
            self.text = ""

    def json(self):
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class FakeSession:
    """requests.Session 대체 — 큐 기반 응답, 호출 기록."""

    def __init__(self):
        self.headers = {}
        self.get_calls = []
        self.post_calls = []
        self.get_responses = []
        self.post_responses = []

    def get(self, url, **kwargs):
        self.get_calls.append({"url": url, **kwargs})
        assert self.get_responses, f"unexpected GET {url}"
        return self.get_responses.pop(0)

    def post(self, url, data=None, **kwargs):
        self.post_calls.append({"url": url, "data": data, **kwargs})
        assert self.post_responses, f"unexpected POST {url}"
        return self.post_responses.pop(0)


def make_collector(markets, monkeypatch=None):
    config = LLMConfig(
        krx_scrape_request_interval_seconds=0.0,
        krx_scrape_investor_markets=list(markets),
    )
    collector = KRXDataCollector(config)
    collector.session = FakeSession()
    if monkeypatch is not None:
        monkeypatch.setattr(collector, "_get_last_trading_date", lambda: TARGET_DATE)
    return collector


def test_investor_trading_parses_and_aggregates_single_market(monkeypatch):
    collector = make_collector(["STK"], monkeypatch)
    session = collector.session
    session.get_responses = [FakeResponse(200)]
    session.post_responses = [FakeResponse(200, INVESTOR_FIXTURE_STK)]

    result = collector._get_investor_trading()

    assert result["foreign_net"] == pytest.approx(3500.0)
    assert result["institution_net"] == pytest.approx(28000.0)
    assert result["retail_net"] == pytest.approx(-30000.0)
    assert result["etc_corporate_net"] == pytest.approx(-1500.0)
    assert result["date"] == TARGET_DATE
    assert result["unit"] == "KRW"
    assert result["by_market"]["STK"]["foreign_net"] == pytest.approx(3500.0)

    # 부트스트랩 GET: outerLoader + screenId
    assert len(session.get_calls) == 1
    bootstrap_url = session.get_calls[0]["url"]
    assert "outerLoader/index.cmd" in bootstrap_url
    assert "screenId=MDCSTAT022" in bootstrap_url

    # 데이터 POST: MDC_OUT bld + 조회 모드 + Referer 헤더
    assert len(session.post_calls) == 1
    post_call = session.post_calls[0]
    payload = post_call["data"]
    assert payload["bld"] == "dbms/MDC_OUT/STAT/standard/MDCSTAT02203_OUT"
    assert payload["mktId"] == "STK"
    assert payload["strtDd"] == TARGET_DATE
    assert payload["endDd"] == TARGET_DATE
    assert payload["inqTpCd"] == "2"
    assert payload["trdVolVal"] == "2"
    assert payload["askBid"] == "3"
    assert post_call["headers"]["Referer"] == bootstrap_url


def test_investor_trading_sums_configured_markets(monkeypatch):
    collector = make_collector(["STK", "KSQ"], monkeypatch)
    session = collector.session
    session.get_responses = [FakeResponse(200)]
    session.post_responses = [
        FakeResponse(200, INVESTOR_FIXTURE_STK),
        FakeResponse(200, INVESTOR_FIXTURE_KSQ),
    ]

    result = collector._get_investor_trading()

    assert result["foreign_net"] == pytest.approx(3500.0 - 1500.0)
    assert result["institution_net"] == pytest.approx(28000.0 + 3000.0)
    assert result["retail_net"] == pytest.approx(-30000.0 + 5000.0)
    assert result["etc_corporate_net"] == pytest.approx(-1500.0 + 500.0)
    assert set(result["by_market"]) == {"STK", "KSQ"}
    # 부트스트랩은 인스턴스당 1회
    assert len(session.get_calls) == 1
    assert [call["data"]["mktId"] for call in session.post_calls] == ["STK", "KSQ"]


def test_investor_trading_keeps_consumer_contract(monkeypatch):
    """컨슈머(_get_briefing_investor_trend)가 읽는 키 계약 유지."""
    collector = make_collector(["STK"], monkeypatch)
    session = collector.session
    session.get_responses = [FakeResponse(200)]
    session.post_responses = [FakeResponse(200, INVESTOR_FIXTURE_STK)]

    inv_data = collector._get_investor_trading()

    for key in ("foreign_net", "institution_net", "retail_net"):
        assert key in inv_data
        assert isinstance(inv_data[key], float)
    # stock_analysis._get_briefing_investor_trend 판정 로직 재현
    assert inv_data.get("foreign_net", 0) > 0
    assert inv_data.get("institution_net", 0) > 0


def test_investor_trading_rebootstraps_once_on_logout(monkeypatch):
    collector = make_collector(["STK"], monkeypatch)
    session = collector.session
    session.get_responses = [FakeResponse(200), FakeResponse(200)]
    session.post_responses = [
        FakeResponse(400, text='"LOGOUT"'),
        FakeResponse(200, INVESTOR_FIXTURE_STK),
    ]

    result = collector._get_investor_trading()

    assert result["foreign_net"] == pytest.approx(3500.0)
    assert len(session.get_calls) == 2  # 최초 + 재부트스트랩
    assert len(session.post_calls) == 2  # LOGOUT + 재시도


def test_investor_trading_fails_after_second_logout(monkeypatch):
    collector = make_collector(["STK"], monkeypatch)
    session = collector.session
    session.get_responses = [FakeResponse(200), FakeResponse(200)]
    session.post_responses = [
        FakeResponse(400, text='"LOGOUT"'),
        FakeResponse(400, text='"LOGOUT"'),
    ]

    result = collector._get_investor_trading()

    assert result == {}
    # 재부트스트랩은 1회만: 무한 재시도 없음
    assert len(session.get_calls) == 2
    assert len(session.post_calls) == 2


def test_investor_trading_caches_per_trading_date(monkeypatch):
    collector = make_collector(["STK"], monkeypatch)
    session = collector.session
    session.get_responses = [FakeResponse(200)]
    session.post_responses = [FakeResponse(200, INVESTOR_FIXTURE_STK)]

    first = collector._get_investor_trading()
    second = collector._get_investor_trading()

    assert second == first
    assert len(session.post_calls) == 1  # 캐시 적중 시 재요청 없음


def test_investor_trading_picks_row_matching_target_date(monkeypatch):
    """일별추이 응답에 여러 날짜가 있어도 대상 거래일 행을 사용."""
    other_row = dict(INVESTOR_ROW_STK, TRD_DD="2026/06/30", TRDVAL10="999,999")
    fixture = {
        "output": [other_row, INVESTOR_ROW_STK],
        "CURRENT_DATETIME": "2026.07.02 PM 07:31:22",
    }
    collector = make_collector(["STK"], monkeypatch)
    session = collector.session
    session.get_responses = [FakeResponse(200)]
    session.post_responses = [FakeResponse(200, fixture)]

    result = collector._get_investor_trading()

    assert result["foreign_net"] == pytest.approx(3500.0)


def test_parse_krx_number_handles_commas_and_missing():
    parse = KRXDataCollector._parse_krx_number
    assert parse("1,234,567") == pytest.approx(1234567.0)
    assert parse("-1,234") == pytest.approx(-1234.0)
    assert parse("-") == 0.0
    assert parse("") == 0.0
    assert parse(None) == 0.0


def test_program_trading_marks_explicit_missing_and_warns_once(caplog):
    collector = make_collector(["STK"])
    session = collector.session  # 응답 큐 비움 → 네트워크 호출 시 실패

    with caplog.at_level(logging.WARNING, logger="shared.llm.collectors"):
        first = collector._get_program_trading()
        second = collector._get_program_trading()

    assert first == {
        "status": "unavailable",
        "reason": "krx_login_required_pending_kis_tr",
    }
    assert second == first
    warnings = [
        rec for rec in caplog.records if "program trading" in rec.getMessage().lower()
    ]
    assert len(warnings) == 1  # 1회성 경고
    assert not session.get_calls and not session.post_calls  # 네트워크 호출 없음


def test_collect_keeps_top_level_keys(monkeypatch):
    """collect() 반환 계약 유지: 4개 최상위 키."""
    collector = make_collector(["STK"])
    monkeypatch.setattr(collector, "_get_market_overview", lambda: {"mo": 1})
    monkeypatch.setattr(collector, "_get_investor_trading", lambda: {"inv": 1})
    monkeypatch.setattr(collector, "_get_index_data", lambda: {"idx": 1})

    data = collector.collect()

    assert set(data) == {
        "market_overview",
        "investor_trading",
        "program_trading",
        "index_data",
    }
    assert data["program_trading"]["status"] == "unavailable"


def test_last_trading_date_uses_krx_publish_cutoff(monkeypatch):
    """T일 데이터는 ~18:00 KST 게시 — 그 전에는 직전 거래일."""

    class FakeDateTime(datetime):
        _now = datetime(2026, 7, 2, 17, 0)  # 목요일 17:00 (< 18:00)

        @classmethod
        def now(cls, tz=None):
            return cls._now

    monkeypatch.setattr("shared.llm.collectors.datetime", FakeDateTime)
    collector = make_collector(["STK"])

    FakeDateTime._now = datetime(2026, 7, 2, 17, 0)
    assert collector._get_last_trading_date() == "20260701"

    FakeDateTime._now = datetime(2026, 7, 2, 18, 30)
    assert collector._get_last_trading_date() == "20260702"


def test_llm_config_loads_krx_scrape_section_from_yaml(tmp_path):
    yaml_path = tmp_path / "llm.yaml"
    yaml_path.write_text(
        """
krx_api:
  scrape:
    base_url: "https://example.invalid"
    timeout_seconds: 5
    request_interval_seconds: 0.5
    investor_trading:
      bld: "dbms/MDC_OUT/STAT/standard/CUSTOM_OUT"
      screen_id: "MDCSTAT099"
      markets: ["STK"]
""",
        encoding="utf-8",
    )

    config = LLMConfig.from_yaml(yaml_path)

    assert config.krx_scrape_base_url == "https://example.invalid"
    assert config.krx_scrape_timeout == 5
    assert config.krx_scrape_request_interval_seconds == 0.5
    assert config.krx_scrape_investor_bld == "dbms/MDC_OUT/STAT/standard/CUSTOM_OUT"
    assert config.krx_scrape_investor_screen_id == "MDCSTAT099"
    assert config.krx_scrape_investor_markets == ["STK"]


def test_llm_config_krx_scrape_defaults():
    config = LLMConfig()

    assert config.krx_scrape_base_url == "https://data.krx.co.kr"
    assert (
        config.krx_scrape_investor_bld == "dbms/MDC_OUT/STAT/standard/MDCSTAT02203_OUT"
    )
    assert config.krx_scrape_investor_screen_id == "MDCSTAT022"
    assert config.krx_scrape_investor_markets == ["STK", "KSQ"]
    assert config.krx_scrape_request_interval_seconds == 2.0
    assert config.krx_scrape_timeout == 10
