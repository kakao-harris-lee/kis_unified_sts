"""Stock news collectors and sentiment helpers."""

from __future__ import annotations

import logging
import time

from bs4 import BeautifulSoup

from .collector_base import DataCollector
from .data_classes import NewsSentiment

logger = logging.getLogger("shared.llm.collectors")


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
        self.session.headers.update(
            {
                "Referer": "https://stock.mk.co.kr/",
            }
        )
        self._market_news_cache: list[dict] = []
        self._market_news_cached_at: float = 0.0
        self._market_news_ttl_seconds: float = 60.0

    def collect(self, code: str = None) -> dict:
        """MK 뉴스 데이터 수집"""
        data = {
            "market_news": self._get_market_news(),
            "stock_news": self._get_stock_news(code) if code else [],
            "analysis": self._get_analysis_news(),
            "theme_news": self._get_theme_news(),
        }
        return data

    def _get_market_news(self) -> list[dict]:
        """시장 뉴스 — ul.news_list > li.news_node > a 구조 (2026-03~)"""
        now_ts = time.time()
        if (
            self._market_news_cache
            and (now_ts - self._market_news_cached_at) < self._market_news_ttl_seconds
        ):
            return [dict(item) for item in self._market_news_cache]

        news_list = []
        try:
            url = f"{self.BASE_URL}/news"
            response = self.session.get(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for li in soup.select("ul.news_list li.news_node")[:10]:
                    a = li.find("a", href=True)
                    if a:
                        title = a.get_text(strip=True)
                        href = a["href"]
                        if title and "/news/view/" in href:
                            news_list.append(
                                {
                                    "title": title,
                                    "link": (
                                        f"{self.BASE_URL}{href}"
                                        if href.startswith("/")
                                        else href
                                    ),
                                    "source": "매일경제",
                                }
                            )
                self._market_news_cache = news_list
                self._market_news_cached_at = now_ts
        except Exception as e:
            logger.debug(f"MK market news failed: {e}")
            if self._market_news_cache:
                return [dict(item) for item in self._market_news_cache]
        return news_list

    def _get_stock_news(self, code: str) -> list[dict]:
        """종목별 뉴스 — MK 종목 페이지 폐기, Naver Finance로 fallback"""
        news_list: list[dict] = []
        try:
            naver = NaverFinanceNewsCollector()
            naver_news = naver._get_stock_news(code)
            for item in naver_news[:5]:
                item["source"] = "네이버금융(MK fallback)"
                news_list.append(item)
        except Exception as e:
            logger.debug(f"MK stock news fallback failed for {code}: {e}")
        return news_list

    def _get_analysis_news(self) -> list[dict]:
        """증권사 분석 — MK 분석 페이지 폐기, 시장 뉴스에서 추출"""
        return []

    def _get_theme_news(self) -> list[dict]:
        """테마 뉴스 — MK 테마 페이지 폐기, 시장 뉴스에서 추출"""
        return []

    def analyze_sentiment(self, news_list: list[dict]) -> NewsSentiment:
        """뉴스 감성 분석 (키워드 기반)"""
        if not news_list:
            return NewsSentiment.NEUTRAL

        positive_keywords = [
            "급등",
            "상승",
            "호재",
            "실적개선",
            "목표가상향",
            "매수",
            "추천",
            "성장",
            "기대",
            "수주",
            "신사업",
            "흑자",
            "반등",
            "돌파",
        ]
        negative_keywords = [
            "급락",
            "하락",
            "악재",
            "실적악화",
            "목표가하향",
            "매도",
            "경고",
            "손실",
            "우려",
            "취소",
            "적자",
            "하회",
            "이탈",
            "감소",
        ]

        pos_count = 0
        neg_count = 0

        for news in news_list:
            title = news.get("title", "")
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

    def collect(self, code: str) -> dict:
        """종목 뉴스 데이터 수집"""
        return {"stock_news": self._get_stock_news(code)}

    def _get_stock_news(self, code: str) -> list[dict]:
        news_list: list[dict] = []
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
                        "link": (
                            f"{self.BASE_URL}{href}" if href.startswith("/") else href
                        ),
                        "code": code,
                        "source": "네이버금융",
                    }
                )

                if len(news_list) >= 10:
                    break
        except Exception as e:
            logger.debug(f"Naver finance stock news failed for {code}: {e}")
        return news_list
