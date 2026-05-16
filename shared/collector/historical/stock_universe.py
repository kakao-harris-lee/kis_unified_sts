"""Lightweight stock universe definition shared by scanners and collectors."""

STOCK_UNIVERSE = [
    # 대형주 (시가총액 상위)
    {"code": "005930", "name": "삼성전자", "tier": "top"},
    {"code": "000660", "name": "SK하이닉스", "tier": "top"},
    {"code": "207940", "name": "삼성바이오로직스", "tier": "top"},
    {"code": "005380", "name": "현대차", "tier": "top"},
    {"code": "000270", "name": "기아", "tier": "top"},
    {"code": "068270", "name": "셀트리온", "tier": "top"},
    {"code": "035420", "name": "NAVER", "tier": "top"},
    {"code": "005490", "name": "POSCO홀딩스", "tier": "top"},
    {"code": "035720", "name": "카카오", "tier": "top"},
    {"code": "051910", "name": "LG화학", "tier": "top"},

    # 중형주 (시가총액 중간)
    {"code": "006400", "name": "삼성SDI", "tier": "mid"},
    {"code": "028260", "name": "삼성물산", "tier": "mid"},
    {"code": "012330", "name": "현대모비스", "tier": "mid"},
    {"code": "055550", "name": "신한지주", "tier": "mid"},
    {"code": "105560", "name": "KB금융", "tier": "mid"},
    {"code": "034730", "name": "SK", "tier": "mid"},
    {"code": "003550", "name": "LG", "tier": "mid"},
    {"code": "066570", "name": "LG전자", "tier": "mid"},
    {"code": "032830", "name": "삼성생명", "tier": "mid"},
    {"code": "086790", "name": "하나금융지주", "tier": "mid"},

    # 소형주/테마주 (변동성 높음)
    {"code": "247540", "name": "에코프로비엠", "tier": "bottom"},
    {"code": "086520", "name": "에코프로", "tier": "bottom"},
    {"code": "373220", "name": "LG에너지솔루션", "tier": "bottom"},
    {"code": "196170", "name": "알테오젠", "tier": "bottom"},
    {"code": "003670", "name": "포스코퓨처엠", "tier": "bottom"},
    {"code": "009150", "name": "삼성전기", "tier": "bottom"},
    {"code": "000810", "name": "삼성화재", "tier": "bottom"},
    {"code": "018260", "name": "삼성에스디에스", "tier": "bottom"},
    {"code": "033780", "name": "KT&G", "tier": "bottom"},
    {"code": "036570", "name": "엔씨소프트", "tier": "bottom"},
]
