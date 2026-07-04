"""Corporate, disclosure, settlement, and association collectors."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from .collector_base import DataCollector

logger = logging.getLogger("shared.llm.collectors")


class SEIBRODataCollector(DataCollector):
    """SEIBRO 증권정보포털 데이터 수집 (seibro.or.kr)

    수집 데이터:
    - 기업 기본정보
    - 배당 정보
    - 주주 현황
    """

    BASE_URL = "https://seibro.or.kr"

    def collect(self, code: str = None) -> dict:
        """SEIBRO 데이터 수집"""
        isin = None
        if code:
            try:
                from .identifiers import to_isin

                isin = to_isin(code)
            except Exception:
                isin = None

        data = {
            "company_info": self._get_company_info(isin) if isin else {},
            "dividend_info": self._get_dividend_info(isin) if isin else {},
            "shareholder_info": self._get_shareholder_info(isin) if isin else {},
        }
        return data

    def _get_company_info(self, isin: str) -> dict:
        """기업 기본정보"""
        try:
            url = f"{self.BASE_URL}/websquare/engine/pro498.do"
            response = self.session.get(url, params={"isin": isin}, timeout=10)
            if response.status_code == 200:
                return {"status": "available", "raw_html_length": len(response.text)}
        except Exception as e:
            logger.debug(f"SEIBRO company info failed: {e}")
        return {}

    def _get_dividend_info(self, isin: str) -> dict:
        """배당 정보"""
        try:
            url = f"{self.BASE_URL}/websquare/engine/proq11.do"
            response = self.session.get(url, params={"isin": isin}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"SEIBRO dividend info failed: {e}")
        return {}

    def _get_shareholder_info(self, isin: str) -> dict:
        """주주 현황"""
        try:
            url = f"{self.BASE_URL}/websquare/engine/proq21.do"
            response = self.session.get(url, params={"isin": isin}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"SEIBRO shareholder info failed: {e}")
        return {}


class DARTDataCollector(DataCollector):
    """DART 전자공시시스템 데이터 수집 (dart.fss.or.kr)

    수집 데이터:
    - 최근 공시 목록
    - 재무정보
    - 대주주 현황
    """

    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key or os.environ.get("DART_API_KEY", "")

    def collect(self, corp_code: str = None) -> dict:
        """DART 데이터 수집"""
        if not self.api_key:
            logger.debug("DART API key not configured")
            return {"error": "API key not configured"}

        data = {
            "recent_disclosures": self._get_disclosures(corp_code) if corp_code else [],
            "financial_info": self._get_financial_info(corp_code) if corp_code else {},
            "major_shareholders": (
                self._get_major_shareholders(corp_code) if corp_code else {}
            ),
            "executive_major_shareholders": (
                self._get_executive_major_shareholders(corp_code) if corp_code else []
            ),
        }
        return data

    async def fetch_recent_filings(
        self,
        *,
        lookback_days: int = 3,
        page_count: int = 100,
    ) -> list[dict]:
        """Fetch recent filings for the streaming news pipeline."""
        return await asyncio.to_thread(
            self._fetch_recent_filings_sync,
            lookback_days=lookback_days,
            page_count=page_count,
        )

    def _fetch_recent_filings_sync(
        self,
        *,
        lookback_days: int = 3,
        page_count: int = 100,
    ) -> list[dict]:
        """최근 전체 공시 목록."""
        if not self.api_key:
            logger.debug("DART API key not configured")
            return []

        try:
            url = f"{self.BASE_URL}/list.json"
            end_de = datetime.now().strftime("%Y%m%d")
            days = max(0, int(lookback_days))
            bgn_de = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
            params = {
                "crtfc_key": self.api_key,
                "bgn_de": bgn_de,
                "end_de": end_de,
                "sort": "date",
                "sort_mth": "desc",
                "page_count": max(1, min(int(page_count), 100)),
            }
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "000":
                    return data.get("list", [])
                if data.get("status") != "013":
                    logger.debug(
                        "DART recent filings returned status=%s message=%s",
                        data.get("status"),
                        data.get("message"),
                    )
        except Exception as e:
            logger.debug(f"DART recent filings failed: {e}")
        return []

    def _get_disclosures(self, corp_code: str) -> list[dict]:
        """최근 공시 목록"""
        try:
            url = f"{self.BASE_URL}/list.json"
            end_de = datetime.now().strftime("%Y%m%d")
            bgn_de = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
            params = {
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
                "bgn_de": bgn_de,
                "end_de": end_de,
                "page_count": 10,
            }
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "000":
                    return data.get("list", [])
        except Exception as e:
            logger.debug(f"DART disclosures failed: {e}")
        return []

    def _get_financial_info(self, corp_code: str) -> dict:
        """재무정보"""
        try:
            url = f"{self.BASE_URL}/fnlttSinglAcnt.json"
            current_year = datetime.now().year
            params = {
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
                "bsns_year": str(current_year - 1),
                "reprt_code": "11011",  # 사업보고서
            }
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "000":
                    return data.get("list", {})
        except Exception as e:
            logger.debug(f"DART financial info failed: {e}")
        return {}

    def _get_major_shareholders(self, corp_code: str) -> dict:
        """대주주 현황"""
        try:
            url = f"{self.BASE_URL}/majorstock.json"
            params = {
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
            }
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "000":
                    return data.get("list", {})
        except Exception as e:
            logger.debug(f"DART major shareholders failed: {e}")
        return {}

    def _get_executive_major_shareholders(self, corp_code: str) -> dict:
        """임원ㆍ주요주주 특정증권등 소유상황."""
        try:
            url = f"{self.BASE_URL}/elestock.json"
            params = {
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
            }
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "000":
                    return data.get("list", {})
        except Exception as e:
            logger.debug(f"DART executive/major shareholders failed: {e}")
        return {}


class KSDDataCollector(DataCollector):
    """KSD 한국예탁결제원 데이터 수집 (ksd.or.kr)

    수집 데이터:
    - 공매도 현황
    - 대차잔고
    - 대량보유 현황
    """

    BASE_URL = "https://www.ksd.or.kr"

    def collect(self, code: str = None) -> dict:
        """KSD 데이터 수집"""
        isin = None
        if code:
            try:
                from .identifiers import to_isin

                isin = to_isin(code)
            except Exception:
                isin = None

        data = {
            "short_selling": self._get_short_selling(isin) if isin else {},
            "stock_lending": self._get_stock_lending(isin) if isin else {},
            "large_holdings": self._get_large_holdings(isin) if isin else {},
        }
        return data

    def _get_short_selling(self, isin: str) -> dict:
        """공매도 현황"""
        try:
            url = f"{self.BASE_URL}/kor/market/shortsel.do"
            response = self.session.get(url, params={"isin": isin}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KSD short selling failed: {e}")
        return {}

    def _get_stock_lending(self, isin: str) -> dict:
        """대차잔고"""
        try:
            url = f"{self.BASE_URL}/kor/market/sllending.do"
            response = self.session.get(url, params={"isin": isin}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KSD stock lending failed: {e}")
        return {}

    def _get_large_holdings(self, isin: str) -> dict:
        """대량보유 현황"""
        try:
            url = f"{self.BASE_URL}/kor/market/largeholding.do"
            response = self.session.get(url, params={"isin": isin}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KSD large holdings failed: {e}")
        return {}


class KOFIADataCollector(DataCollector):
    """KOFIA 금융투자협회 데이터 수집 (freesis.kofia.or.kr)

    수집 데이터:
    - 펀드 정보
    - 채권 시가평가
    - 투자자 동향
    """

    BASE_URL = "https://freesis.kofia.or.kr"

    def __init__(self):
        super().__init__()
        self.session.headers.update(
            {
                "Referer": "https://freesis.kofia.or.kr/",
            }
        )

    def collect(self) -> dict:
        """KOFIA 데이터 수집"""
        data = {
            "fund_overview": self._get_fund_overview(),
            "bond_evaluation": self._get_bond_evaluation(),
            "investor_trend": self._get_investor_trend(),
        }
        return data

    def _get_fund_overview(self) -> dict:
        """펀드 현황"""
        try:
            url = f"{self.BASE_URL}/stat/FreeSIS/info/fsis/fsis0100/fsis010001.do"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                tables = soup.find_all("table")
                return {"status": "available", "tables_found": len(tables)}
        except Exception as e:
            logger.debug(f"KOFIA fund overview failed: {e}")
        return {}

    def _get_bond_evaluation(self) -> dict:
        """채권 시가평가"""
        try:
            url = f"{self.BASE_URL}/stat/FreeSIS/info/bond/bond0100/bond010001.do"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KOFIA bond evaluation failed: {e}")
        return {}

    def _get_investor_trend(self) -> dict:
        """투자자 동향"""
        try:
            url = f"{self.BASE_URL}/stat/FreeSIS/info/stat/stat0100/stat010001.do"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KOFIA investor trend failed: {e}")
        return {}
