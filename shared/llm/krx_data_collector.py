"""KRX market structure and investor-flow collector."""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime

from shared.calendar import MarketCalendar

from .collector_base import DataCollector
from .config import LLMConfig
from .krx_api_client import KRXOpenAPIClient

logger = logging.getLogger("shared.llm.collectors")


class KRXDataCollector(DataCollector):
    """KRX 한국거래소 데이터 수집 (data.krx.co.kr)

    수집 데이터:
    - 시장 개요
    - 투자자별 매매동향 (거래대금 순매수, 원 단위)
    - 프로그램매매 현황 (현재 명시적 결측 — 아래 참조)
    - 업종별 지수

    익명 접근 정책 (2026 KRX 변경, 2026-07-02 실측):
    - 일반 bld(``dbms/MDC/STAT/...``)는 세션 없이 400 + body "LOGOUT" 반환.
    - outerLoader 화이트리스트 화면의 ``dbms/MDC_OUT/STAT/standard/*_OUT``
      bld만 쿠키 부트스트랩(JSESSIONID) 후 익명 조회 가능.
    """

    _DATA_PATH = "/comm/bldAttendant/getJsonData.cmd"
    _BOOTSTRAP_PATH = "/contents/MDC/MDI/outerLoader/index.cmd"

    # KRX 일별 데이터 게시 시간 (~18:00 KST). KRXOpenAPIClient 컷오프와 정합.
    _DATA_AVAILABLE_TIME = KRXOpenAPIClient._KRX_DATA_AVAILABLE_TIME

    # 투자자별 거래실적 조회 모드. 파서(_parse_investor_trading)와 한 몸인
    # 계약이므로 config가 아닌 상수로 유지:
    # inqTpCd=2(일별추이), trdVolVal=2(거래대금), askBid=3(순매수)
    _INVESTOR_QUERY_MODE = {
        "inqTpCd": "2",
        "trdVolVal": "2",
        "askBid": "3",
        "detailView": "1",
        "locale": "ko_KR",
        "csvxls_isNo": "false",
    }

    # MDCSTAT02203_OUT(detailView=1) 응답 컬럼 → 투자자 그룹 매핑 (파서 계약).
    # 값은 콤마 포함 문자열, 원 단위 순매수 거래대금.
    _INSTITUTION_COLUMNS = (
        "TRDVAL1",  # 금융투자
        "TRDVAL2",  # 보험
        "TRDVAL3",  # 투신
        "TRDVAL4",  # 사모
        "TRDVAL5",  # 은행
        "TRDVAL6",  # 기타금융
        "TRDVAL7",  # 연기금
    )
    _ETC_CORPORATE_COLUMN = "TRDVAL8"  # 기타법인
    _RETAIL_COLUMN = "TRDVAL9"  # 개인
    _FOREIGN_COLUMNS = ("TRDVAL10", "TRDVAL11")  # 외국인 + 기타외국인

    def __init__(self, config: LLMConfig | None = None):
        super().__init__()
        self._config = config or LLMConfig.load()
        self._calendar = MarketCalendar()
        self._bootstrapped = False
        self._last_request_monotonic = 0.0
        self._investor_cache: dict[str, dict] = {}
        self._program_trading_warned = False

    # ------------------------------------------------------------
    # 세션 부트스트랩 / 요청 헬퍼
    # ------------------------------------------------------------

    @property
    def _data_url(self) -> str:
        return f"{self._config.krx_scrape_base_url}{self._DATA_PATH}"

    def _bootstrap_url(self, screen_id: str) -> str:
        return (
            f"{self._config.krx_scrape_base_url}{self._BOOTSTRAP_PATH}"
            f"?screenId={screen_id}&locale=ko_KR&kosdaqGlobalYn=1"
        )

    def _throttle(self) -> None:
        """스크레이핑 요청 간 최소 간격 유지 (config 기반)."""
        interval = float(self._config.krx_scrape_request_interval_seconds)
        if interval <= 0:
            return
        wait = self._last_request_monotonic + interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request_monotonic = time.monotonic()

    def _ensure_bootstrap(self, screen_id: str, *, force: bool = False) -> bool:
        """outerLoader 화면 로드로 JSESSIONID 쿠키 획득 (인스턴스당 1회)."""
        if self._bootstrapped and not force:
            return True
        try:
            self._throttle()
            response = self.session.get(
                self._bootstrap_url(screen_id),
                timeout=self._config.krx_scrape_timeout,
            )
        except Exception as e:
            logger.warning(f"KRX session bootstrap failed: {e}")
            self._bootstrapped = False
            return False
        if response.status_code != 200:
            logger.warning(
                f"KRX session bootstrap failed: status={response.status_code}"
            )
            self._bootstrapped = False
            return False
        self._bootstrapped = True
        return True

    def _fetch_outer_json(self, payload: dict, screen_id: str) -> dict | None:
        """MDC_OUT bld 데이터 조회 (400 "LOGOUT" 시 1회 재부트스트랩 후 실패).

        Returns:
            응답 봉투 dict(``{"output": [...], ...}``) 또는 실패 시 None.
        """
        if not self._ensure_bootstrap(screen_id):
            return None
        headers = {"Referer": self._bootstrap_url(screen_id)}
        for attempt in range(2):
            self._throttle()
            response = self.session.post(
                self._data_url,
                data=payload,
                headers=headers,
                timeout=self._config.krx_scrape_timeout,
            )
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    logger.warning("KRX outer data response is not valid JSON")
                    return None
            if (
                response.status_code == 400
                and "LOGOUT" in response.text
                and attempt == 0
            ):
                logger.info("KRX session expired (LOGOUT); re-bootstrapping once")
                if not self._ensure_bootstrap(screen_id, force=True):
                    return None
                continue
            logger.warning(
                f"KRX outer data request failed: status={response.status_code}"
            )
            return None
        return None

    def _get_last_trading_date(self) -> str:
        """KRX 기준 최근 게시 거래일 (휴장일/공휴일 + 게시 시간 반영).

        T일 데이터는 ~18:00 KST 이후 게시되므로 그 전에는 직전 거래일을
        반환한다 (KRXOpenAPIClient._KRX_DATA_AVAILABLE_TIME과 정합).
        """
        compat_module = sys.modules.get("shared.llm.collectors")
        datetime_cls = getattr(compat_module, "datetime", datetime)
        now = datetime_cls.now()
        today = now.date()

        if now.time() < self._DATA_AVAILABLE_TIME:
            return self._calendar.get_previous_market_day(today).strftime("%Y%m%d")

        if self._calendar.is_market_day(today):
            return today.strftime("%Y%m%d")

        return self._calendar.get_previous_market_day(today).strftime("%Y%m%d")

    def collect(self) -> dict:
        """KRX 데이터 수집"""
        data = {
            "market_overview": self._get_market_overview(),
            "investor_trading": self.get_investor_trading(),
            "program_trading": self._get_program_trading(),
            "index_data": self._get_index_data(),
        }
        return data

    def get_stock_info(self, code: str) -> dict:
        """개별 종목 정보 조회"""
        try:
            payload = {
                "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
                "isuCd": code,
                "isuCd2": code,
                "mktId": "STK",
            }
            response = self.session.post(self._data_url, data=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug(f"KRX stock info failed for {code}: {e}")
        return {}

    def _get_market_overview(self) -> dict:
        """시장 개요"""
        try:
            payload = {
                "bld": "dbms/MDC/STAT/standard/MDCSTAT00101",
                "mktId": "STK",
            }
            response = self.session.post(self._data_url, data=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug(f"KRX market overview failed: {e}")
        return {}

    def get_investor_trading(self) -> dict:
        """투자자별 매매동향 (거래대금 순매수, 원 단위).

        익명 outerLoader 경로(MDCSTAT02203_OUT)로 시장별 일별추이를 조회해
        config의 markets(STK/KSQ)를 합산한다. 컨슈머 계약 키
        (foreign_net/institution_net/retail_net)는 유지.
        """
        try:
            target_date = self._get_last_trading_date()
            cached = self._investor_cache.get(target_date)
            if cached is not None:
                return cached

            screen_id = self._config.krx_scrape_investor_screen_id
            by_market: dict[str, dict[str, float]] = {}
            for market in self._config.krx_scrape_investor_markets:
                payload = {
                    "bld": self._config.krx_scrape_investor_bld,
                    "mktId": market,
                    "strtDd": target_date,
                    "endDd": target_date,
                    **self._INVESTOR_QUERY_MODE,
                }
                data = self._fetch_outer_json(payload, screen_id)
                if not data:
                    continue
                parsed = self._parse_investor_trading(data, target_date)
                if parsed:
                    by_market[market] = parsed

            if not by_market:
                return {}

            keys = (
                "foreign_net",
                "institution_net",
                "retail_net",
                "etc_corporate_net",
            )
            result: dict = {
                key: sum(market_data[key] for market_data in by_market.values())
                for key in keys
            }
            result["date"] = target_date
            result["unit"] = "KRW"
            result["measure"] = "trade_value_net"
            result["by_market"] = by_market
            self._investor_cache[target_date] = result
            return result
        except Exception as e:
            logger.debug(f"KRX investor trading failed: {e}")
        return {}

    # Backward-compat alias: market_structure_collector and older callers used
    # the pre-promotion private name.
    _get_investor_trading = get_investor_trading

    def _parse_investor_trading(self, data: dict, target_date: str) -> dict:
        """투자자별 데이터 파싱 (MDCSTAT02203_OUT 일별추이 응답).

        기관 = 금융투자~연기금(TRDVAL1~7) 합산,
        외국인 = 외국인+기타외국인(TRDVAL10+11), 개인 = TRDVAL9.
        """
        try:
            output = data.get("output") or []
            row = None
            for candidate in output:
                trd_dd = str(candidate.get("TRD_DD", ""))
                normalized = trd_dd.replace("/", "").replace("-", "").replace(".", "")
                if normalized == target_date:
                    row = candidate
                    break
            if row is None:
                if not output:
                    return {}
                row = output[0]

            institution = sum(
                self._parse_krx_number(row.get(column))
                for column in self._INSTITUTION_COLUMNS
            )
            foreign = sum(
                self._parse_krx_number(row.get(column))
                for column in self._FOREIGN_COLUMNS
            )
            return {
                "foreign_net": foreign,
                "institution_net": institution,
                "retail_net": self._parse_krx_number(row.get(self._RETAIL_COLUMN)),
                "etc_corporate_net": self._parse_krx_number(
                    row.get(self._ETC_CORPORATE_COLUMN)
                ),
            }
        except Exception as e:
            logger.debug(f"Failed to parse investor trading: {e}")
        return {}

    @staticmethod
    def _parse_krx_number(value) -> float:
        """KRX 콤마 포함 숫자 문자열 파싱 ("1,234" / "-1,234" / "-" / None)."""
        if value is None:
            return 0.0
        text = str(value).strip().replace(",", "")
        if not text or text == "-":
            return 0.0
        return float(text)

    def _get_program_trading(self) -> dict:
        """프로그램 매매 — 현재 자동 수집 불가, 명시적 결측 처리.

        올바른 화면(MDCSTAT02601)은 KRX 로그인이 필요해 익명 접근이 불가하고,
        과거 사용하던 bld(MDCSTAT02701)는 ETN/ELW 시세 화면이라 프로그램매매
        데이터가 아니었다. 가짜/빈 값 대신 사유를 명시해 반환한다.

        TODO(roadmap 2026-07-02 O1/O10): KIS TR 소스 확정 시 교체.
        """
        if not self._program_trading_warned:
            logger.warning(
                "KRX program trading is unavailable via anonymous access "
                "(login required); returning explicit missing marker until "
                "a KIS TR source is confirmed (roadmap O1/O10)"
            )
            self._program_trading_warned = True
        return {
            "status": "unavailable",
            "reason": "krx_login_required_pending_kis_tr",
        }

    def _get_index_data(self) -> dict:
        """지수 데이터"""
        try:
            payload = {
                "bld": "dbms/MDC/STAT/standard/MDCSTAT00501",
                "idxIndMidclssCd": "01",  # KOSPI
            }
            response = self.session.post(self._data_url, data=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug(f"KRX index data failed: {e}")
        return {}
