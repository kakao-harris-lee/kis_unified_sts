"""Lightweight stock universe definition shared by scanners and collectors.

Backtest universe spanning three market-cap tiers so strategies can be
validated across 대형/중형/소형. Selected 2026-06-09 from KRX daily market-cap
(``KRXOpenAPIClient.get_stock_daily``) over KOSPI+KOSDAQ, filtered to
거래대금 >= ~100억 for backtest-grade liquidity:

  - top    (대형): market cap >= 50조,   ranked by market cap.
  - mid    (중형): 10조 ~ 50조,          ranked by market cap.
  - bottom (소형): 0.3조 ~ 3조,          ranked by turnover (most-traded small caps).

``tier`` is metadata only (no runtime logic keys off it). Re-segment with the
KRX market-cap script when the universe needs refreshing — note 2026 prices are
~4x prior eras (e.g. 삼성전자 종가 ~295k), so cap thresholds are era-relative.
"""

STOCK_UNIVERSE = [
    # 대형주 (시가총액 >=50조)
    {"code": "005930", "name": "삼성전자", "tier": "top"},
    {"code": "000660", "name": "SK하이닉스", "tier": "top"},
    {"code": "402340", "name": "SK스퀘어", "tier": "top"},
    {"code": "005380", "name": "현대차", "tier": "top"},
    {"code": "009150", "name": "삼성전기", "tier": "top"},
    {"code": "373220", "name": "LG에너지솔루션", "tier": "top"},
    {"code": "032830", "name": "삼성생명", "tier": "top"},
    {"code": "028260", "name": "삼성물산", "tier": "top"},
    {"code": "329180", "name": "HD현대중공업", "tier": "top"},
    {"code": "000270", "name": "기아", "tier": "top"},

    # 중형주 (10조 ~ 50조)
    {"code": "055550", "name": "신한지주", "tier": "mid"},
    {"code": "035420", "name": "NAVER", "tier": "mid"},
    {"code": "066570", "name": "LG전자", "tier": "mid"},
    {"code": "034730", "name": "SK", "tier": "mid"},
    {"code": "006400", "name": "삼성SDI", "tier": "mid"},
    {"code": "068270", "name": "셀트리온", "tier": "mid"},
    {"code": "267260", "name": "HD현대일렉트릭", "tier": "mid"},
    {"code": "042660", "name": "한화오션", "tier": "mid"},
    {"code": "010120", "name": "LS ELECTRIC", "tier": "mid"},
    {"code": "086790", "name": "하나금융지주", "tier": "mid"},

    # 소형주 (0.3조 ~ 3조, 유동성 선별; KOSPI+KOSDAQ)
    {"code": "001740", "name": "SK네트웍스", "tier": "bottom"},
    {"code": "090360", "name": "로보스타", "tier": "bottom"},
    {"code": "010170", "name": "대한광통신", "tier": "bottom"},
    {"code": "043260", "name": "성호전자", "tier": "bottom"},
    {"code": "085620", "name": "미래에셋생명", "tier": "bottom"},
    {"code": "001820", "name": "삼화콘덴서", "tier": "bottom"},
    {"code": "100790", "name": "미래에셋벤처투자", "tier": "bottom"},
    {"code": "095610", "name": "테스", "tier": "bottom"},
    {"code": "006220", "name": "제주은행", "tier": "bottom"},
    {"code": "089030", "name": "테크윙", "tier": "bottom"},
]
