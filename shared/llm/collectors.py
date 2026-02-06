"""
Korean Financial Data Collectors

Data Sources:
- pykrx: 주식 시세 (기본)
- KRX (data.krx.co.kr): 거래소 공식 데이터, 투자자별 동향
- SEIBRO (seibro.or.kr): 증권정보, 배당, 주주현황
- DART (dart.fss.or.kr): 공시정보, 재무제표
- KSD (ksd.or.kr): 공매도, 대차잔고, 대량보유
- KOFIA (freesis.kofia.or.kr): 펀드, 채권, 투자자동향
- MK Stock (stock.mk.co.kr): 증권뉴스, 테마, 분석
"""
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

from shared.calendar import MarketCalendar
from shared.features.ofi import OFICalculator, OFIConfig
from shared.indicators.orderbook import OrderBookAnalyzer
from shared.streaming.client import RedisClient
from shared.streaming.message import StreamMessage

from .config import LLMConfig
from .errors import DataUnavailableError
from .krx_api_client import KRXOpenAPIClient

from .data_classes import (
    EconomicEvent,
    FlowData,
    GlobalMarketData,
    NewsSentiment,
)

# Optional imports (used for global markets)
try:
    import FinanceDataReader as fdr

    FDR_AVAILABLE = True
except ImportError:
    FDR_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================
# Base Collector
# ============================================================


class DataCollector(ABC):
    """데이터 수집기 기본 클래스"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    @abstractmethod
    def collect(self, *args, **kwargs) -> Dict:
        """데이터 수집"""
        pass


# ============================================================
# Stock Data Collectors
# ============================================================


class StockDataCollector(DataCollector):
    """주식 시세 데이터 수집 (pykrx 기반)"""

    # 장 시작 시간 (09:00)
    MARKET_OPEN_HOUR = 9
    SUPPORTED_MARKETS = ("KOSPI", "KOSDAQ")

    def __init__(self):
        super().__init__()
        self._calendar = MarketCalendar()

    def _get_last_trading_date(self) -> str:
        """가장 최근 거래일 반환 (휴장일/공휴일 반영)."""
        now = datetime.now()
        today = now.date()

        # 장 시작 전에는 전일(최근 거래일) 데이터 사용
        if now.time() < self._calendar.MARKET_OPEN_TIME:
            target = self._calendar.get_previous_market_day(today)
            logger.info(
                f"Pre-market hours ({now.strftime('%H:%M')}), "
                f"using previous market day {target}"
            )
            return target.strftime("%Y%m%d")

        # 장중/장마감 이후: 오늘이 거래일이면 오늘, 아니면 직전 거래일
        if self._calendar.is_market_day(today):
            return today.strftime("%Y%m%d")

        target = self._calendar.get_previous_market_day(today)
        logger.info(f"Non-trading day {today}, using previous market day {target}")
        return target.strftime("%Y%m%d")

    def collect(self, market: str = "KOSPI") -> Optional[pd.DataFrame]:
        """전체 시장 데이터 수집 (단일 시장)"""
        try:
            from pykrx import stock

            if market not in self.SUPPORTED_MARKETS:
                raise ValueError(f"Unsupported market: {market} (supported={self.SUPPORTED_MARKETS})")

            target_date = self._get_last_trading_date()
            logger.info(f"Collecting market data for {target_date} ({market})")

            df = stock.get_market_ohlcv(target_date, market=market)

            # 데이터가 없으면 하루 더 이전 시도
            if len(df) == 0:
                prev_date = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
                logger.info(f"No data for {target_date}, trying {prev_date}")
                df = stock.get_market_ohlcv(prev_date, market=market)

            if len(df) > 0:
                cap_df = stock.get_market_cap(target_date, market=market)
                if len(cap_df) == 0:
                    prev_date = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
                    cap_df = stock.get_market_cap(prev_date, market=market)
                if len(cap_df) > 0:
                    # Drop existing 시가총액 column if present to avoid overlap
                    if "시가총액" in df.columns:
                        df = df.drop(columns=["시가총액"])
                    df = df.join(cap_df[["시가총액"]], how="left")

            if len(df) > 0:
                # Keep market info for downstream merges.
                df["시장"] = market

            return df
        except Exception as e:
            logger.error(f"Failed to collect market data: {e}")
            return None

    def get_stock_history(self, code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """개별 종목 히스토리 수집"""
        try:
            from pykrx import stock

            end = datetime.now()
            start = end - timedelta(days=days * 2)
            df = stock.get_market_ohlcv(
                start.strftime("%Y%m%d"),
                end.strftime("%Y%m%d"),
                code
            )
            return df.tail(days) if len(df) > days else df
        except Exception as e:
            logger.debug(f"Failed to get history for {code}: {e}")
            return None

    def get_stock_name(self, code: str) -> str:
        """종목명 조회"""
        try:
            from pykrx import stock
            return stock.get_market_ticker_name(code) or code
        except:
            return code


class KRXDataCollector(DataCollector):
    """KRX 한국거래소 데이터 수집 (data.krx.co.kr)

    수집 데이터:
    - 시장 개요
    - 투자자별 매매동향
    - 프로그램매매 현황
    - 업종별 지수
    """

    BASE_URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

    def __init__(self):
        super().__init__()
        self._calendar = MarketCalendar()

    def _get_last_trading_date(self) -> str:
        """KRX 기준 최근 거래일 (휴장일/공휴일 반영)."""
        now = datetime.now()
        today = now.date()

        if now.time() < self._calendar.MARKET_CLOSE_TIME:
            return self._calendar.get_previous_market_day(today).strftime("%Y%m%d")

        if self._calendar.is_market_day(today):
            return today.strftime("%Y%m%d")

        return self._calendar.get_previous_market_day(today).strftime("%Y%m%d")

    def collect(self) -> Dict:
        """KRX 데이터 수집"""
        data = {
            "market_overview": self._get_market_overview(),
            "investor_trading": self._get_investor_trading(),
            "program_trading": self._get_program_trading(),
            "index_data": self._get_index_data(),
        }
        return data

    def get_stock_info(self, code: str) -> Dict:
        """개별 종목 정보 조회"""
        try:
            payload = {
                "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
                "isuCd": code,
                "isuCd2": code,
                "mktId": "STK",
            }
            response = self.session.post(self.BASE_URL, data=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug(f"KRX stock info failed for {code}: {e}")
        return {}

    def _get_market_overview(self) -> Dict:
        """시장 개요"""
        try:
            payload = {
                "bld": "dbms/MDC/STAT/standard/MDCSTAT00101",
                "mktId": "STK",
            }
            response = self.session.post(self.BASE_URL, data=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug(f"KRX market overview failed: {e}")
        return {}

    def _get_investor_trading(self) -> Dict:
        """투자자별 매매동향"""
        try:
            today = self._get_last_trading_date()
            payload = {
                "bld": "dbms/MDC/STAT/standard/MDCSTAT02401",
                "mktId": "STK",
                "strtDd": today,
                "endDd": today,
            }
            response = self.session.post(self.BASE_URL, data=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return self._parse_investor_trading(data)
        except Exception as e:
            logger.debug(f"KRX investor trading failed: {e}")
        return {}

    def _parse_investor_trading(self, data: Dict) -> Dict:
        """투자자별 데이터 파싱"""
        result = {}
        try:
            output = data.get("output", [])
            for row in output:
                inv_type = row.get("INVST_NM", "")
                net_buy = float(row.get("NETT_BUY_QTY", 0))
                if "외국인" in inv_type:
                    result["foreign_net"] = net_buy
                elif "기관" in inv_type:
                    result["institution_net"] = net_buy
                elif "개인" in inv_type:
                    result["retail_net"] = net_buy
        except Exception as e:
            logger.debug(f"Failed to parse investor trading: {e}")
        return result

    def _get_program_trading(self) -> Dict:
        """프로그램 매매"""
        try:
            today = self._get_last_trading_date()
            payload = {
                "bld": "dbms/MDC/STAT/standard/MDCSTAT02701",
                "mktId": "STK",
                "strtDd": today,
                "endDd": today,
            }
            response = self.session.post(self.BASE_URL, data=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug(f"KRX program trading failed: {e}")
        return {}

    def _get_index_data(self) -> Dict:
        """지수 데이터"""
        try:
            payload = {
                "bld": "dbms/MDC/STAT/standard/MDCSTAT00501",
                "idxIndMidclssCd": "01",  # KOSPI
            }
            response = self.session.post(self.BASE_URL, data=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug(f"KRX index data failed: {e}")
        return {}


class SEIBRODataCollector(DataCollector):
    """SEIBRO 증권정보포털 데이터 수집 (seibro.or.kr)

    수집 데이터:
    - 기업 기본정보
    - 배당 정보
    - 주주 현황
    """

    BASE_URL = "https://seibro.or.kr"

    def collect(self, code: str = None) -> Dict:
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

    def _get_company_info(self, isin: str) -> Dict:
        """기업 기본정보"""
        try:
            url = f"{self.BASE_URL}/websquare/engine/pro498.do"
            response = self.session.get(url, params={"isin": isin}, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                return {"status": "available", "raw_html_length": len(response.text)}
        except Exception as e:
            logger.debug(f"SEIBRO company info failed: {e}")
        return {}

    def _get_dividend_info(self, isin: str) -> Dict:
        """배당 정보"""
        try:
            url = f"{self.BASE_URL}/websquare/engine/proq11.do"
            response = self.session.get(url, params={"isin": isin}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"SEIBRO dividend info failed: {e}")
        return {}

    def _get_shareholder_info(self, isin: str) -> Dict:
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

    def collect(self, corp_code: str = None) -> Dict:
        """DART 데이터 수집"""
        if not self.api_key:
            logger.debug("DART API key not configured")
            return {"error": "API key not configured"}

        data = {
            "recent_disclosures": self._get_disclosures(corp_code) if corp_code else [],
            "financial_info": self._get_financial_info(corp_code) if corp_code else {},
            "major_shareholders": self._get_major_shareholders(corp_code) if corp_code else {},
        }
        return data

    def _get_disclosures(self, corp_code: str) -> List[Dict]:
        """최근 공시 목록"""
        try:
            url = f"{self.BASE_URL}/list.json"
            params = {
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
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

    def _get_financial_info(self, corp_code: str) -> Dict:
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

    def _get_major_shareholders(self, corp_code: str) -> Dict:
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


class KSDDataCollector(DataCollector):
    """KSD 한국예탁결제원 데이터 수집 (ksd.or.kr)

    수집 데이터:
    - 공매도 현황
    - 대차잔고
    - 대량보유 현황
    """

    BASE_URL = "https://www.ksd.or.kr"

    def collect(self, code: str = None) -> Dict:
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

    def _get_short_selling(self, isin: str) -> Dict:
        """공매도 현황"""
        try:
            url = f"{self.BASE_URL}/kor/market/shortsel.do"
            response = self.session.get(url, params={"isin": isin}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KSD short selling failed: {e}")
        return {}

    def _get_stock_lending(self, isin: str) -> Dict:
        """대차잔고"""
        try:
            url = f"{self.BASE_URL}/kor/market/sllending.do"
            response = self.session.get(url, params={"isin": isin}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KSD stock lending failed: {e}")
        return {}

    def _get_large_holdings(self, isin: str) -> Dict:
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
        self.session.headers.update({
            'Referer': 'https://freesis.kofia.or.kr/',
        })

    def collect(self) -> Dict:
        """KOFIA 데이터 수집"""
        data = {
            "fund_overview": self._get_fund_overview(),
            "bond_evaluation": self._get_bond_evaluation(),
            "investor_trend": self._get_investor_trend(),
        }
        return data

    def _get_fund_overview(self) -> Dict:
        """펀드 현황"""
        try:
            url = f"{self.BASE_URL}/stat/FreeSIS/info/fsis/fsis0100/fsis010001.do"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                tables = soup.find_all('table')
                return {"status": "available", "tables_found": len(tables)}
        except Exception as e:
            logger.debug(f"KOFIA fund overview failed: {e}")
        return {}

    def _get_bond_evaluation(self) -> Dict:
        """채권 시가평가"""
        try:
            url = f"{self.BASE_URL}/stat/FreeSIS/info/bond/bond0100/bond010001.do"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KOFIA bond evaluation failed: {e}")
        return {}

    def _get_investor_trend(self) -> Dict:
        """투자자 동향"""
        try:
            url = f"{self.BASE_URL}/stat/FreeSIS/info/stat/stat0100/stat010001.do"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KOFIA investor trend failed: {e}")
        return {}


class MKStockNewsCollector(DataCollector):
    """매일경제 증권뉴스 수집 (stock.mk.co.kr)

    수집 데이터:
    - 종목 뉴스
    - 시장 동향
    - 증권가 분석
    - 테마/섹터 뉴스
    """

    BASE_URL = "https://stock.mk.co.kr"

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Referer': 'https://stock.mk.co.kr/',
        })

    def collect(self, code: str = None) -> Dict:
        """MK 뉴스 데이터 수집"""
        data = {
            "market_news": self._get_market_news(),
            "stock_news": self._get_stock_news(code) if code else [],
            "analysis": self._get_analysis_news(),
            "theme_news": self._get_theme_news(),
        }
        return data

    def _get_market_news(self) -> List[Dict]:
        """시장 뉴스"""
        news_list = []
        try:
            url = f"{self.BASE_URL}/news/"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                articles = soup.find_all('div', class_='news_item')[:10]
                for article in articles:
                    title_elem = article.find('a')
                    if title_elem:
                        news_list.append({
                            "title": title_elem.get_text(strip=True),
                            "link": title_elem.get('href', ''),
                            "source": "매일경제"
                        })
        except Exception as e:
            logger.debug(f"MK market news failed: {e}")
        return news_list

    def _get_stock_news(self, code: str) -> List[Dict]:
        """종목별 뉴스"""
        news_list = []
        try:
            url = f"{self.BASE_URL}/quote/{code}/"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                news_section = soup.find('div', class_='news_list')
                if news_section:
                    articles = news_section.find_all('li')[:5]
                    for article in articles:
                        title_elem = article.find('a')
                        if title_elem:
                            news_list.append({
                                "title": title_elem.get_text(strip=True),
                                "link": title_elem.get('href', ''),
                                "code": code,
                                "source": "매일경제"
                            })
        except Exception as e:
            logger.debug(f"MK stock news failed for {code}: {e}")
        return news_list

    def _get_analysis_news(self) -> List[Dict]:
        """증권사 분석"""
        news_list = []
        try:
            url = f"{self.BASE_URL}/news/view_all.php?sc=30600002"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                articles = soup.find_all('div', class_='list_news')[:5]
                for article in articles:
                    title_elem = article.find('a')
                    if title_elem:
                        news_list.append({
                            "title": title_elem.get_text(strip=True),
                            "link": title_elem.get('href', ''),
                            "type": "analysis",
                            "source": "매일경제"
                        })
        except Exception as e:
            logger.debug(f"MK analysis news failed: {e}")
        return news_list

    def _get_theme_news(self) -> List[Dict]:
        """테마 뉴스"""
        news_list = []
        try:
            url = f"{self.BASE_URL}/news/view_all.php?sc=30600004"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                articles = soup.find_all('div', class_='list_news')[:5]
                for article in articles:
                    title_elem = article.find('a')
                    if title_elem:
                        news_list.append({
                            "title": title_elem.get_text(strip=True),
                            "link": title_elem.get('href', ''),
                            "type": "theme",
                            "source": "매일경제"
                        })
        except Exception as e:
            logger.debug(f"MK theme news failed: {e}")
        return news_list

    def analyze_sentiment(self, news_list: List[Dict]) -> NewsSentiment:
        """뉴스 감성 분석 (키워드 기반)"""
        if not news_list:
            return NewsSentiment.NEUTRAL

        positive_keywords = ['급등', '상승', '호재', '실적개선', '목표가상향', '매수', '추천',
                            '성장', '기대', '수주', '신사업', '흑자', '반등', '돌파']
        negative_keywords = ['급락', '하락', '악재', '실적악화', '목표가하향', '매도', '경고',
                            '손실', '우려', '취소', '적자', '하회', '이탈', '감소']

        pos_count = 0
        neg_count = 0

        for news in news_list:
            title = news.get('title', '')
            for kw in positive_keywords:
                if kw in title:
                    pos_count += 1
            for kw in negative_keywords:
                if kw in title:
                    neg_count += 1

        score = pos_count - neg_count

        if score >= 3:
            return NewsSentiment.VERY_POSITIVE
        elif score >= 1:
            return NewsSentiment.POSITIVE
        elif score <= -3:
            return NewsSentiment.VERY_NEGATIVE
        elif score <= -1:
            return NewsSentiment.NEGATIVE
        else:
            return NewsSentiment.NEUTRAL


class NaverFinanceNewsCollector(DataCollector):
    """Naver Finance 종목 뉴스 수집기.

    NOTE:
      - HTML 구조 변경 가능성이 있으므로 실패 시 빈 리스트 반환.
      - 외부 호출 비용이 크므로 상위 후보군에만 사용 권장.
    """

    BASE_URL = "https://finance.naver.com"

    def __init__(self):
        super().__init__()
        self.session.headers.update(
            {
                "Referer": "https://finance.naver.com/",
            }
        )

    def collect(self, code: str) -> Dict:
        """종목 뉴스 데이터 수집"""
        return {"stock_news": self._get_stock_news(code)}

    def _get_stock_news(self, code: str) -> List[Dict]:
        news_list: List[Dict] = []
        try:
            url = f"{self.BASE_URL}/item/news_news.nhn"
            response = self.session.get(url, params={"code": code}, timeout=10)
            if response.status_code != 200:
                return news_list

            soup = BeautifulSoup(response.text, "html.parser")

            # Naver finance: news list is usually in table rows under .type5
            table = soup.find("table", class_="type5")
            if not table:
                return news_list

            for a in table.select("a"):
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if not title or "read" not in href:
                    continue
                news_list.append(
                    {
                        "title": title,
                        "link": f"{self.BASE_URL}{href}" if href.startswith("/") else href,
                        "code": code,
                        "source": "네이버금융",
                    }
                )

                if len(news_list) >= 10:
                    break
        except Exception as e:
            logger.debug(f"Naver finance stock news failed for {code}: {e}")
        return news_list


# ============================================================
# Futures Data Collectors
# ============================================================


class FuturesGlobalCollector(DataCollector):
    """글로벌 시장 데이터 수집"""

    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__()
        self.config = config or LLMConfig.from_env()

    def collect(self) -> GlobalMarketData:
        """글로벌 시장 데이터 수집 (가능하면 실제 데이터 사용)"""
        snapshot = self._load_snapshot()
        if snapshot:
            return snapshot

        if FDR_AVAILABLE:
            try:
                data = self._collect_from_fdr()
                if data:
                    return data
            except Exception as e:
                logger.debug(f"FDR global market collection failed: {e}")
            raise DataUnavailableError("global_market_data", "fdr_empty")

        raise DataUnavailableError("global_market_data", "fdr_not_available")

    def _load_snapshot(self) -> Optional[GlobalMarketData]:
        """외부 스냅샷(JSON)에서 글로벌 데이터 로드 (선택)"""
        snapshot_json = os.environ.get("LLM_GLOBAL_SNAPSHOT_JSON", "").strip()
        snapshot_path = os.environ.get("LLM_GLOBAL_SNAPSHOT_PATH", "").strip()

        payload = None
        if snapshot_json:
            try:
                payload = json.loads(snapshot_json)
            except Exception as e:
                logger.debug(f"Invalid LLM_GLOBAL_SNAPSHOT_JSON: {e}")
                payload = None
        elif snapshot_path:
            try:
                with open(snapshot_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as e:
                logger.debug(f"Failed to load snapshot file: {e}")
                payload = None

        if not isinstance(payload, dict):
            return None

        allowed = set(GlobalMarketData.__dataclass_fields__.keys())
        data = {k: payload.get(k) for k in allowed if k in payload}
        if not data:
            return None

        result = GlobalMarketData(**data)
        if not result.global_score:
            result.global_score = self._compute_global_score(result)
        return result

    def _collect_from_fdr(self) -> Optional[GlobalMarketData]:
        """FinanceDataReader 기반 글로벌 지표 수집 (Investing.com/TradingView 연계)"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        tickers = {
            "sp500": os.environ.get("LLM_TICKER_SP500", "US500"),
            "nasdaq": os.environ.get("LLM_TICKER_NASDAQ", "IXIC"),
            "nikkei": os.environ.get("LLM_TICKER_NIKKEI", "N225"),
            "shanghai": os.environ.get("LLM_TICKER_SHANGHAI", "000001.SS"),
            "vix": os.environ.get("LLM_TICKER_VIX", "VIX"),
            "wti": os.environ.get("LLM_TICKER_WTI", "CL=F"),
            "gold": os.environ.get("LLM_TICKER_GOLD", "GC=F"),
            "dxy": os.environ.get("LLM_TICKER_DXY", "DXY"),
            "usd_krw": os.environ.get("LLM_TICKER_USDKRW", "USDKRW"),
        }

        def _fetch_last(ticker: str) -> Optional[tuple[float, float]]:
            if not ticker:
                return None
            df = fdr.DataReader(ticker, start_date, end_date)
            if df is None or len(df) < 2:
                return None
            col = "Close" if "Close" in df.columns else "close"
            last = float(df[col].iloc[-1])
            prev = float(df[col].iloc[-2])
            change_pct = (last / prev - 1) * 100 if prev else 0.0
            return last, change_pct

        values: dict[str, tuple[float, float]] = {}
        for key, ticker in tickers.items():
            try:
                res = _fetch_last(ticker)
                if res:
                    values[key] = res
            except Exception:
                continue

        if not values:
            return None

        result = GlobalMarketData(
            sp500=round(values.get("sp500", (0.0, 0.0))[0], 2),
            sp500_change_pct=round(values.get("sp500", (0.0, 0.0))[1], 2),
            nasdaq=round(values.get("nasdaq", (0.0, 0.0))[0], 2),
            nasdaq_change_pct=round(values.get("nasdaq", (0.0, 0.0))[1], 2),
            nikkei=round(values.get("nikkei", (0.0, 0.0))[0], 2),
            nikkei_change_pct=round(values.get("nikkei", (0.0, 0.0))[1], 2),
            shanghai=round(values.get("shanghai", (0.0, 0.0))[0], 2),
            shanghai_change_pct=round(values.get("shanghai", (0.0, 0.0))[1], 2),
            vix=round(values.get("vix", (0.0, 0.0))[0], 2),
            wti=round(values.get("wti", (0.0, 0.0))[0], 2),
            gold=round(values.get("gold", (0.0, 0.0))[0], 2),
            dxy=round(values.get("dxy", (0.0, 0.0))[0], 2),
            usd_krw=round(values.get("usd_krw", (0.0, 0.0))[0], 2),
        )
        result.global_score = self._compute_global_score(result)
        return result

    @staticmethod
    def _compute_global_score(data: GlobalMarketData) -> float:
        return round(
            data.sp500_change_pct * 15
            + data.nasdaq_change_pct * 10
            + data.nikkei_change_pct * 5
            - (data.vix - 15) * 2,
            1,
        )



class FuturesFlowCollector(DataCollector):
    """수급 데이터 수집"""

    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__()
        self.config = config or LLMConfig.from_env()
        self._calendar = MarketCalendar()
        self._krx_client = KRXOpenAPIClient(self.config)

    def collect(self) -> tuple[FlowData | None, List[str]]:
        """수급 데이터 수집 (투자자별 수급 제외, 실제 데이터만 사용)"""
        missing: List[str] = ["investor_flow_excluded"]
        base_date = self._get_last_trading_date()

        # KOSPI200 선물/옵션 지표 (베이시스, 풋콜)
        basis: float | None = None
        put_call: float | None = None
        if not self.config.krx_api_key:
            missing.append("krx_api_key_missing")
        else:
            try:
                futures_list = self._krx_client.get_kospi200_futures(base_date)
                futures = max(futures_list, key=lambda f: f.volume) if futures_list else None
                options = self._krx_client.get_kospi200_options(base_date)
                spot = self._get_kospi200_index_price(base_date)
                if futures is not None and spot is not None:
                    basis = float(futures.close_price) - float(spot)
                else:
                    missing.append("basis")
                if options:
                    put_call = float(options.put_call_ratio)
                else:
                    missing.append("put_call_ratio")
            except Exception as e:
                logger.debug(f"KRX futures basis/put-call failed: {e}")
                missing.extend(["basis", "put_call_ratio"])

        micro_data, micro_missing = self._collect_microstructure()
        missing.extend(micro_missing)

        if missing:
            missing = list(dict.fromkeys(missing))

        if basis is None and put_call is None and not micro_data:
            return None, missing

        flow_score = 0.0
        if basis is not None:
            flow_score -= basis * 10
        if put_call is not None:
            if put_call > 1.1:
                flow_score += 5
            elif put_call < 0.9:
                flow_score -= 5

        micro_score = micro_data.get("microstructure_score") if micro_data else None
        if micro_score is not None:
            flow_score += micro_score

        return (
            FlowData(
                foreign_futures=None,
                institution_futures=None,
                retail_futures=None,
                foreign_futures_5d=None,
                institution_futures_5d=None,
                basis=round(basis, 2) if basis is not None else None,
                put_call_ratio=round(put_call, 2) if put_call is not None else None,
                orderbook_imbalance=micro_data.get("orderbook_imbalance") if micro_data else None,
                ofi_zscore=micro_data.get("ofi_zscore") if micro_data else None,
                aggressor_ratio=micro_data.get("aggressor_ratio") if micro_data else None,
                aggressor_balance=micro_data.get("aggressor_balance") if micro_data else None,
                oi_change=micro_data.get("oi_change") if micro_data else None,
                price_change=micro_data.get("price_change") if micro_data else None,
                microstructure_score=micro_score,
                flow_score=round(flow_score, 1),
            ),
            missing,
        )

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _load_recent_ticks(self) -> tuple[List[StreamMessage], List[str]]:
        missing: List[str] = []
        stream_name = self.config.futures_tick_stream or "raw_data"
        lookback_seconds = max(60, int(self.config.futures_tick_lookback_seconds))
        max_entries = max(100, int(self.config.futures_tick_max))

        try:
            redis_client = RedisClient.get_client()
            raw_msgs = redis_client.xrevrange(stream_name, max="+", min="-", count=max_entries)
        except Exception as e:
            logger.debug(f"Redis tick fetch failed: {e}")
            missing.append("redis_unavailable")
            return [], missing

        now = time.time()
        parsed: List[StreamMessage] = []
        for msg_id, fields in raw_msgs:
            try:
                msg = StreamMessage.from_raw(stream_name, msg_id, dict(fields))
            except Exception:
                continue
            if now - msg.timestamp > lookback_seconds:
                continue
            parsed.append(msg)

        parsed.reverse()
        if not parsed:
            missing.append("microstructure_ticks")
        return parsed, missing

    @staticmethod
    def _resolve_symbol(ticks: List[StreamMessage], explicit: str | None) -> Optional[str]:
        if explicit:
            for msg in ticks:
                if msg.data.get("symbol") == explicit:
                    return explicit
            return None

        counts: Dict[str, int] = {}
        for msg in ticks:
            symbol = msg.data.get("symbol")
            if symbol:
                counts[symbol] = counts.get(symbol, 0) + 1
        if not counts:
            return None
        return max(counts.items(), key=lambda item: item[1])[0]

    def _extract_orderbook_levels(self, data: Dict[str, Any]) -> tuple[list[float], list[float], list[float], list[float]]:
        bid_prices: list[float] = []
        bid_qtys: list[float] = []
        ask_prices: list[float] = []
        ask_qtys: list[float] = []
        for i in range(1, 6):
            bid_price = self._to_float(data.get(f"bid_price_{i}"))
            bid_qty = self._to_float(data.get(f"bid_qty_{i}"))
            ask_price = self._to_float(data.get(f"ask_price_{i}"))
            ask_qty = self._to_float(data.get(f"ask_qty_{i}"))
            if bid_price is not None and bid_qty is not None and bid_price > 0:
                bid_prices.append(bid_price)
                bid_qtys.append(bid_qty)
            if ask_price is not None and ask_qty is not None and ask_price > 0:
                ask_prices.append(ask_price)
                ask_qtys.append(ask_qty)
        return bid_prices, ask_prices, bid_qtys, ask_qtys

    def _collect_microstructure(self) -> tuple[Dict[str, Any], List[str]]:
        missing: List[str] = []
        ticks, tick_missing = self._load_recent_ticks()
        missing.extend(tick_missing)
        if not ticks:
            return {}, missing

        symbol = self._resolve_symbol(ticks, self.config.futures_tick_symbol or None)
        if not symbol:
            missing.append("microstructure_symbol")
            return {}, missing

        filtered = [msg for msg in ticks if msg.data.get("symbol") == symbol]
        if not filtered:
            missing.append("microstructure_ticks")
            return {}, missing

        orderbook_analyzer = OrderBookAnalyzer()
        ofi_calc = OFICalculator(OFIConfig())

        last_orderbook: Dict[str, Any] | None = None
        last_bid: float | None = None
        last_ask: float | None = None
        last_mid: float | None = None

        buy_volume = 0.0
        sell_volume = 0.0
        trade_count = 0
        first_trade_price: float | None = None
        last_trade_price: float | None = None
        first_oi: float | None = None
        last_oi: float | None = None

        for msg in filtered:
            data = msg.data

            bid = self._to_float(data.get("bid_price_1"))
            ask = self._to_float(data.get("ask_price_1"))
            bid_qty = self._to_float(data.get("bid_qty_1")) or 0.0
            ask_qty = self._to_float(data.get("ask_qty_1")) or 0.0

            if bid is not None and ask is not None and bid > 0 and ask > 0:
                last_bid = bid
                last_ask = ask
                last_mid = (bid + ask) / 2
                last_orderbook = data
                try:
                    ofi_calc.update(bid, bid_qty, ask, ask_qty)
                except Exception:
                    pass

            price = self._to_float(data.get("current_price"))
            if price is not None and price > 0:
                trade_count += 1
                size = self._to_float(data.get("tick_volume")) or 1.0

                if first_trade_price is None:
                    first_trade_price = price
                last_trade_price = price

                oi = self._to_float(data.get("open_interest"))
                if oi is not None:
                    if first_oi is None:
                        first_oi = oi
                    last_oi = oi

                side = None
                if last_bid is not None and last_ask is not None:
                    if price >= last_ask:
                        side = "BUY"
                    elif price <= last_bid:
                        side = "SELL"
                    elif last_mid is not None:
                        if price > last_mid:
                            side = "BUY"
                        elif price < last_mid:
                            side = "SELL"

                if side == "BUY":
                    buy_volume += size
                elif side == "SELL":
                    sell_volume += size

        orderbook_imbalance: float | None = None
        if last_orderbook:
            bid_prices, ask_prices, bid_qtys, ask_qtys = self._extract_orderbook_levels(last_orderbook)
            if bid_prices and ask_prices and bid_qtys and ask_qtys:
                try:
                    imbalance = orderbook_analyzer.calculate(
                        bid_prices=bid_prices,
                        ask_prices=ask_prices,
                        bid_volumes=[int(q) for q in bid_qtys],
                        ask_volumes=[int(q) for q in ask_qtys],
                    )
                    orderbook_imbalance = imbalance.imbalance
                except Exception:
                    orderbook_imbalance = None
            else:
                missing.append("orderbook_imbalance")
        else:
            missing.append("orderbook_imbalance")

        ofi_zscore = ofi_calc.get_ofi_zscore()
        if ofi_zscore is None:
            missing.append("ofi_zscore")

        total_vol = buy_volume + sell_volume
        aggressor_ratio: float | None = None
        aggressor_balance: float | None = None
        if total_vol > 0:
            aggressor_ratio = buy_volume / total_vol
            aggressor_balance = (buy_volume - sell_volume) / total_vol
        else:
            missing.append("aggressor_ratio")

        oi_change: float | None = None
        if first_oi is not None and last_oi is not None and trade_count >= 2:
            oi_change = last_oi - first_oi
        else:
            missing.append("open_interest_change")

        price_change: float | None = None
        if first_trade_price is not None and last_trade_price is not None and trade_count >= 2:
            price_change = last_trade_price - first_trade_price
        else:
            missing.append("price_change")

        micro_score = 0.0
        components = 0
        if orderbook_imbalance is not None:
            micro_score += orderbook_imbalance * 8
            components += 1
        if ofi_zscore is not None:
            capped = max(min(ofi_zscore, 3.0), -3.0)
            micro_score += capped * 1.5
            components += 1
        if aggressor_balance is not None:
            micro_score += aggressor_balance * 6
            components += 1
        if oi_change is not None and price_change is not None:
            components += 1
            if oi_change > 0 and price_change > 0:
                micro_score += 3
            elif oi_change > 0 and price_change < 0:
                micro_score -= 3
            elif oi_change < 0 and price_change > 0:
                micro_score += 1.5
            elif oi_change < 0 and price_change < 0:
                micro_score -= 1.5

        if components == 0:
            missing.append("microstructure_unavailable")
            return {}, missing

        return (
            {
                "orderbook_imbalance": round(orderbook_imbalance, 3) if orderbook_imbalance is not None else None,
                "ofi_zscore": round(ofi_zscore, 2) if ofi_zscore is not None else None,
                "aggressor_ratio": round(aggressor_ratio, 3) if aggressor_ratio is not None else None,
                "aggressor_balance": round(aggressor_balance, 3) if aggressor_balance is not None else None,
                "oi_change": round(oi_change, 2) if oi_change is not None else None,
                "price_change": round(price_change, 2) if price_change is not None else None,
                "microstructure_score": round(micro_score, 1),
            },
            missing,
        )

    def _get_last_trading_date(self) -> str:
        now = datetime.now()
        today = now.date()

        if now.time() < self._calendar.MARKET_OPEN_TIME:
            target = self._calendar.get_previous_market_day(today)
        elif self._calendar.is_market_day(today):
            target = today
        else:
            target = self._calendar.get_previous_market_day(today)

        return target.strftime("%Y%m%d")

    def _get_kospi200_index_price(self, base_date: str) -> Optional[float]:
        data = self._krx_client.get_kospi_index(base_date)
        for item in data or []:
            name = str(item.get("IDX_NM", ""))
            if "KOSPI200" in name or "코스피200" in name:
                return KRXOpenAPIClient._parse_number(item.get("CLSPRC_IDX", 0))
        return None

class FuturesEventCollector(DataCollector):
    """경제 이벤트 수집"""

    def collect(self, days_ahead: int = 3) -> List[EconomicEvent]:
        """경제 이벤트 수집 (외부 스냅샷 사용)"""
        snapshot_json = os.environ.get("LLM_EVENT_SNAPSHOT_JSON", "").strip()
        snapshot_path = os.environ.get("LLM_EVENT_SNAPSHOT_PATH", "").strip()

        payload = None
        if snapshot_json:
            try:
                payload = json.loads(snapshot_json)
            except Exception as e:
                logger.debug(f"Invalid LLM_EVENT_SNAPSHOT_JSON: {e}")
        elif snapshot_path:
            try:
                with open(snapshot_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as e:
                logger.debug(f"Failed to load event snapshot file: {e}")

        if not payload:
            raise DataUnavailableError("macro_events", "snapshot_missing")

        events = []
        for item in payload:
            try:
                events.append(EconomicEvent(
                    date=str(item.get("date", "")),
                    time=str(item.get("time", "")),
                    country=str(item.get("country", "")),
                    event=str(item.get("event", "")),
                    importance=str(item.get("importance", "")),
                    impact_analysis=str(item.get("impact_analysis", "")),
                ))
            except Exception:
                continue

        if not events:
            raise DataUnavailableError("macro_events", "snapshot_empty")

        # limit by days_ahead
        if days_ahead:
            cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            events = [e for e in events if e.date <= cutoff]

        events.sort(key=lambda x: (x.date, x.time))
        return events


# ============================================================
# Convenience Functions
# ============================================================


def collect_krx_data() -> Dict:
    """KRX 데이터 수집 (data.krx.co.kr)"""
    collector = KRXDataCollector()
    return collector.collect()


def collect_seibro_data(code: str = None) -> Dict:
    """SEIBRO 데이터 수집 (seibro.or.kr)"""
    collector = SEIBRODataCollector()
    return collector.collect(code)


def collect_dart_data(corp_code: str = None, api_key: str = None) -> Dict:
    """DART 데이터 수집 (dart.fss.or.kr)"""
    collector = DARTDataCollector(api_key=api_key)
    return collector.collect(corp_code)


def collect_ksd_data(code: str = None) -> Dict:
    """KSD 데이터 수집 (ksd.or.kr)"""
    collector = KSDDataCollector()
    return collector.collect(code)


def collect_kofia_data() -> Dict:
    """KOFIA 데이터 수집 (freesis.kofia.or.kr)"""
    collector = KOFIADataCollector()
    return collector.collect()


def collect_mk_news(code: str = None) -> Dict:
    """매일경제 증권뉴스 수집 (stock.mk.co.kr)"""
    collector = MKStockNewsCollector()
    data = collector.collect(code)
    all_news = data.get("market_news", []) + data.get("stock_news", [])
    data["sentiment"] = collector.analyze_sentiment(all_news).value
    return data
