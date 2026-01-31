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
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

from .data_classes import (
    EconomicEvent,
    FlowData,
    GlobalMarketData,
    NewsSentiment,
)

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

    def _get_last_trading_date(self) -> str:
        """가장 최근 거래일 반환 (장 시작 전이면 전일)"""
        now = datetime.now()

        # 장 시작 전(09:00 전)이면 전일 데이터 사용
        if now.hour < self.MARKET_OPEN_HOUR:
            target = now - timedelta(days=1)
            logger.info(f"Pre-market hours ({now.strftime('%H:%M')}), using previous day data")
        else:
            target = now

        # 주말 처리: 토요일(5) -> 금요일, 일요일(6) -> 금요일
        while target.weekday() >= 5:
            target -= timedelta(days=1)

        return target.strftime("%Y%m%d")

    def collect(self) -> Optional[pd.DataFrame]:
        """전체 시장 데이터 수집"""
        try:
            from pykrx import stock

            target_date = self._get_last_trading_date()
            logger.info(f"Collecting market data for {target_date}")

            df = stock.get_market_ohlcv(target_date, market="KOSPI")

            # 데이터가 없으면 하루 더 이전 시도
            if len(df) == 0:
                prev_date = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
                logger.info(f"No data for {target_date}, trying {prev_date}")
                df = stock.get_market_ohlcv(prev_date, market="KOSPI")

            if len(df) > 0:
                cap_df = stock.get_market_cap(target_date, market="KOSPI")
                if len(cap_df) == 0:
                    prev_date = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
                    cap_df = stock.get_market_cap(prev_date, market="KOSPI")
                if len(cap_df) > 0:
                    # Drop existing 시가총액 column if present to avoid overlap
                    if '시가총액' in df.columns:
                        df = df.drop(columns=['시가총액'])
                    df = df.join(cap_df[['시가총액']])

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
            today = datetime.now().strftime("%Y%m%d")
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
            today = datetime.now().strftime("%Y%m%d")
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
        data = {
            "company_info": self._get_company_info(code) if code else {},
            "dividend_info": self._get_dividend_info(code) if code else {},
            "shareholder_info": self._get_shareholder_info(code) if code else {},
        }
        return data

    def _get_company_info(self, code: str) -> Dict:
        """기업 기본정보"""
        try:
            url = f"{self.BASE_URL}/websquare/engine/pro498.do"
            response = self.session.get(url, params={"isin": code}, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                return {"status": "available", "raw_html_length": len(response.text)}
        except Exception as e:
            logger.debug(f"SEIBRO company info failed: {e}")
        return {}

    def _get_dividend_info(self, code: str) -> Dict:
        """배당 정보"""
        try:
            url = f"{self.BASE_URL}/websquare/engine/proq11.do"
            response = self.session.get(url, params={"isin": code}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"SEIBRO dividend info failed: {e}")
        return {}

    def _get_shareholder_info(self, code: str) -> Dict:
        """주주 현황"""
        try:
            url = f"{self.BASE_URL}/websquare/engine/proq21.do"
            response = self.session.get(url, params={"isin": code}, timeout=10)
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
        data = {
            "short_selling": self._get_short_selling(code) if code else {},
            "stock_lending": self._get_stock_lending(code) if code else {},
            "large_holdings": self._get_large_holdings(code) if code else {},
        }
        return data

    def _get_short_selling(self, code: str) -> Dict:
        """공매도 현황"""
        try:
            url = f"{self.BASE_URL}/kor/market/shortsel.do"
            response = self.session.get(url, params={"isin": code}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KSD short selling failed: {e}")
        return {}

    def _get_stock_lending(self, code: str) -> Dict:
        """대차잔고"""
        try:
            url = f"{self.BASE_URL}/kor/market/sllending.do"
            response = self.session.get(url, params={"isin": code}, timeout=10)
            if response.status_code == 200:
                return {"status": "available"}
        except Exception as e:
            logger.debug(f"KSD stock lending failed: {e}")
        return {}

    def _get_large_holdings(self, code: str) -> Dict:
        """대량보유 현황"""
        try:
            url = f"{self.BASE_URL}/kor/market/largeholding.do"
            response = self.session.get(url, params={"isin": code}, timeout=10)
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


# ============================================================
# Futures Data Collectors
# ============================================================


class FuturesGlobalCollector(DataCollector):
    """글로벌 시장 데이터 수집"""

    def collect(self) -> GlobalMarketData:
        """글로벌 시장 데이터 수집 (샘플 데이터)"""
        np.random.seed(int(datetime.now().timestamp()) % 1000)

        sp500 = 5800 + np.random.normal(0, 50)
        sp500_change = np.random.normal(0.2, 0.8)
        nasdaq = 18000 + np.random.normal(0, 150)
        nasdaq_change = np.random.normal(0.3, 1.0)
        nikkei = 38000 + np.random.normal(0, 300)
        nikkei_change = np.random.normal(0.1, 0.7)
        shanghai = 3300 + np.random.normal(0, 30)
        shanghai_change = np.random.normal(0, 0.6)
        vix = max(10, 18 + np.random.normal(0, 3))
        wti = 75 + np.random.normal(0, 2)
        gold = 2400 + np.random.normal(0, 20)
        dxy = 105 + np.random.normal(0, 0.5)
        usd_krw = 1380 + np.random.normal(0, 5)

        global_score = (
            sp500_change * 15 +
            nasdaq_change * 10 +
            nikkei_change * 5 -
            (vix - 15) * 2
        )

        return GlobalMarketData(
            sp500=round(sp500, 2),
            sp500_change_pct=round(sp500_change, 2),
            nasdaq=round(nasdaq, 2),
            nasdaq_change_pct=round(nasdaq_change, 2),
            nikkei=round(nikkei, 2),
            nikkei_change_pct=round(nikkei_change, 2),
            shanghai=round(shanghai, 2),
            shanghai_change_pct=round(shanghai_change, 2),
            vix=round(vix, 2),
            wti=round(wti, 2),
            gold=round(gold, 2),
            dxy=round(dxy, 2),
            usd_krw=round(usd_krw, 2),
            global_score=round(global_score, 1)
        )


class FuturesFlowCollector(DataCollector):
    """수급 데이터 수집"""

    def collect(self) -> FlowData:
        """수급 데이터 수집 (샘플 데이터)"""
        np.random.seed(int(datetime.now().timestamp()) % 1000 + 1)

        foreign = np.random.randint(-20000, 20000)
        institution = np.random.randint(-15000, 15000)
        retail = -(foreign + institution)

        foreign_5d = foreign * 5 + np.random.randint(-5000, 5000)
        inst_5d = institution * 5 + np.random.randint(-3000, 3000)

        basis = np.random.normal(0, 0.5)
        put_call = 0.8 + np.random.normal(0, 0.15)

        flow_score = (
            (foreign / 1000) * 2 +
            (institution / 1000) * 1.5 -
            basis * 10
        )

        return FlowData(
            foreign_futures=foreign,
            institution_futures=institution,
            retail_futures=retail,
            foreign_futures_5d=foreign_5d,
            institution_futures_5d=inst_5d,
            basis=round(basis, 2),
            put_call_ratio=round(put_call, 2),
            flow_score=round(flow_score, 1)
        )


class FuturesEventCollector(DataCollector):
    """경제 이벤트 수집"""

    def collect(self, days_ahead: int = 3) -> List[EconomicEvent]:
        """경제 이벤트 수집 (샘플 데이터)"""
        today = datetime.now()

        major_events = [
            {"country": "미국", "event": "FOMC 금리결정", "importance": "높음"},
            {"country": "미국", "event": "비농업 고용지표", "importance": "높음"},
            {"country": "미국", "event": "소비자물가지수(CPI)", "importance": "높음"},
            {"country": "미국", "event": "GDP 성장률", "importance": "높음"},
            {"country": "미국", "event": "ISM 제조업지수", "importance": "중간"},
            {"country": "한국", "event": "한국은행 기준금리", "importance": "높음"},
            {"country": "중국", "event": "제조업 PMI", "importance": "중간"},
        ]

        events = []
        np.random.seed(int(datetime.now().timestamp()) % 1000)

        for i in range(days_ahead):
            date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
            day_events = np.random.choice(
                len(major_events),
                size=min(2, np.random.randint(1, 3)),
                replace=False
            )

            for idx in day_events:
                evt = major_events[idx]
                events.append(EconomicEvent(
                    date=date,
                    time=f"{np.random.randint(8, 23):02d}:{np.random.choice(['00', '30'])}",
                    country=evt["country"],
                    event=evt["event"],
                    importance=evt["importance"]
                ))

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
