"""
KRX Open API Client

KRX Open API를 통해 시장 데이터를 수집하는 클라이언트.
모든 설정값은 LLMConfig에서 로드 (하드코딩 없음).
"""

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import List, Optional

import requests

from .config import LLMConfig
from .data_classes import (
    BondIndexData,
    ETFData,
    FuturesData,
    IndexData,
    OptionsData,
)


class KRXOpenAPIClient:
    """KRX Open API 클라이언트"""

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        초기화

        Args:
            config: LLMConfig 인스턴스. None이면 환경변수에서 로드
        """
        self.config = config or LLMConfig.from_env()
        self.session = requests.Session()
        self.session.headers.update({
            "AUTH_KEY": self.config.krx_api_key,
            "Content-Type": "application/json",
        })

    def _request(self, endpoint: str, params: Optional[dict] = None) -> list:
        """
        API 요청 수행

        Args:
            endpoint: API 엔드포인트
            params: 쿼리 파라미터

        Returns:
            API 응답 데이터 (리스트)
        """
        url = f"{self.config.krx_base_url}/{endpoint}"

        try:
            response = self.session.get(
                url, params=params, timeout=self.config.krx_timeout
            )
            response.raise_for_status()

            data = response.json()

            if "OutBlock_1" in data:
                return data["OutBlock_1"]
            elif "output" in data:
                return data["output"]
            else:
                return data

        except requests.exceptions.RequestException as e:
            print(f"API 요청 실패 ({endpoint}): {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 실패: {e}")
            return []

    # ============================================================
    # 지수 데이터
    # ============================================================

    def get_kospi_index(self, base_date: Optional[str] = None) -> List[dict]:
        """KOSPI 시리즈 일별시세"""
        if base_date is None:
            base_date = self._get_last_trading_date()

        params = {"basDd": base_date}
        return self._request("idx/kospi_dd_trd", params)

    def get_kosdaq_index(self, base_date: Optional[str] = None) -> List[dict]:
        """KOSDAQ 시리즈 일별시세"""
        if base_date is None:
            base_date = self._get_last_trading_date()

        params = {"basDd": base_date}
        return self._request("idx/kosdaq_dd_trd", params)

    def get_krx_index(self, base_date: Optional[str] = None) -> List[dict]:
        """KRX 시리즈 일별시세"""
        if base_date is None:
            base_date = self._get_last_trading_date()

        params = {"basDd": base_date}
        return self._request("idx/krx_dd_trd", params)

    def get_indices(self, base_date: Optional[str] = None) -> dict[str, IndexData]:
        """주요 지수 조회 (종합)"""
        results = {}

        # KOSPI
        kospi_data = self.get_kospi_index(base_date)
        if kospi_data:
            for item in kospi_data:
                name = item.get("IDX_NM", "")
                if "KOSPI" in name or "코스피" in name:
                    results[name] = IndexData(
                        name=name,
                        price=self._parse_number(item.get("CLSPRC_IDX", 0)),
                        change_rate=self._parse_number(item.get("FLUC_RT", 0)),
                        volume=self._parse_int(item.get("ACC_TRDVOL", 0)),
                        trade_value=self._parse_number(item.get("ACC_TRDVAL", 0)),
                    )

        # KOSDAQ
        kosdaq_data = self.get_kosdaq_index(base_date)
        if kosdaq_data:
            for item in kosdaq_data:
                name = item.get("IDX_NM", "")
                if "KOSDAQ" in name or "코스닥" in name:
                    results[name] = IndexData(
                        name=name,
                        price=self._parse_number(item.get("CLSPRC_IDX", 0)),
                        change_rate=self._parse_number(item.get("FLUC_RT", 0)),
                        volume=self._parse_int(item.get("ACC_TRDVOL", 0)),
                        trade_value=self._parse_number(item.get("ACC_TRDVAL", 0)),
                    )

        return results

    # ============================================================
    # ETF 데이터
    # ============================================================

    def get_etf_daily(self, base_date: Optional[str] = None) -> List[dict]:
        """ETF 일별매매정보"""
        if base_date is None:
            base_date = self._get_last_trading_date()

        params = {"basDd": base_date}
        return self._request("etp/etf_dd_trd", params)

    def get_etf_by_sector(self, base_date: Optional[str] = None) -> List[ETFData]:
        """섹터별 ETF 데이터 조회"""
        etf_data = self.get_etf_daily(base_date)
        results = []

        if not etf_data:
            return results

        # 섹터 ETF 필터링
        sector_codes = set()
        for codes in self.config.sector_etfs.values():
            sector_codes.update(codes)

        for item in etf_data:
            code = item.get("ISU_SRT_CD", "")

            # 섹터 찾기
            sector = ""
            for s, codes in self.config.sector_etfs.items():
                if code in codes:
                    sector = s
                    break

            if sector or len(results) < 30:  # 섹터 ETF 또는 상위 30개
                results.append(
                    ETFData(
                        code=code,
                        name=item.get("ISU_ABBRV", ""),
                        close_price=self._parse_number(item.get("TDD_CLSPRC", 0)),
                        change_rate=self._parse_number(item.get("FLUC_RT", 0)),
                        volume=self._parse_int(item.get("ACC_TRDVOL", 0)),
                        trade_value=self._parse_number(item.get("ACC_TRDVAL", 0)),
                        sector=sector,
                    )
                )

        return results

    # ============================================================
    # 선물 데이터
    # ============================================================

    def get_futures_daily(self, base_date: Optional[str] = None) -> List[dict]:
        """선물 일별매매정보 (주식선물 外)"""
        if base_date is None:
            base_date = self._get_last_trading_date()

        params = {"basDd": base_date}
        return self._request("drv/fut_dd_trd", params)

    def get_kospi200_futures(self, base_date: Optional[str] = None) -> List[FuturesData]:
        """KOSPI200 선물 데이터 조회"""
        futures_data = self.get_futures_daily(base_date)
        results = []

        if not futures_data:
            return results

        for item in futures_data:
            name = item.get("PROD_NM", "")

            # KOSPI200 선물 필터링
            if "KOSPI200" in name or "K200" in name or "코스피200" in name:
                results.append(
                    FuturesData(
                        product_name=name,
                        close_price=self._parse_number(item.get("TDD_CLSPRC", 0)),
                        change=self._parse_number(item.get("PRV_DD_CMPR", 0)),
                        change_rate=self._parse_number(item.get("FLUC_RT", 0)),
                        volume=self._parse_int(item.get("ACC_TRDVOL", 0)),
                        open_interest=self._parse_int(item.get("OPN_INTRST_QTY", 0)),
                        basis=0.0,  # 별도 계산 필요
                    )
                )

        return results

    # ============================================================
    # 옵션 데이터
    # ============================================================

    def get_options_daily(self, base_date: Optional[str] = None) -> List[dict]:
        """옵션 일별매매정보 (주식옵션 外)"""
        if base_date is None:
            base_date = self._get_last_trading_date()

        params = {"basDd": base_date}
        return self._request("drv/opt_dd_trd", params)

    def get_kospi200_options(self, base_date: Optional[str] = None) -> OptionsData:
        """KOSPI200 옵션 데이터 조회 (풋콜비율)"""
        options_data = self.get_options_daily(base_date)

        call_volume = 0
        put_volume = 0
        call_oi = 0
        put_oi = 0

        if options_data:
            for item in options_data:
                name = item.get("PROD_NM", "")

                # KOSPI200 옵션만
                if "KOSPI200" in name or "K200" in name:
                    volume = self._parse_int(item.get("ACC_TRDVOL", 0))
                    oi = self._parse_int(item.get("OPN_INTRST_QTY", 0))

                    if "콜" in name or "C" in name.upper():
                        call_volume += volume
                        call_oi += oi
                    elif "풋" in name or "P" in name.upper():
                        put_volume += volume
                        put_oi += oi

        pcr = put_volume / call_volume if call_volume > 0 else 1.0

        return OptionsData(
            call_volume=call_volume,
            put_volume=put_volume,
            put_call_ratio=round(pcr, 2),
            call_oi=call_oi,
            put_oi=put_oi,
        )

    # ============================================================
    # 채권 데이터
    # ============================================================

    def get_bond_index(self, base_date: Optional[str] = None) -> List[dict]:
        """채권지수 시세정보"""
        if base_date is None:
            base_date = self._get_last_trading_date()

        params = {"basDd": base_date}
        return self._request("idx/bon_dd_trd", params)

    def get_bond_indices(self, base_date: Optional[str] = None) -> List[BondIndexData]:
        """채권지수 데이터 조회"""
        bond_data = self.get_bond_index(base_date)
        results = []

        if not bond_data:
            return results

        for item in bond_data:
            results.append(
                BondIndexData(
                    index_name=item.get("IDX_NM", ""),
                    index_value=self._parse_number(item.get("CLSPRC_IDX", 0)),
                    change=self._parse_number(item.get("PRV_DD_CMPR", 0)),
                    change_rate=self._parse_number(item.get("FLUC_RT", 0)),
                )
            )

        return results

    # ============================================================
    # 유틸리티
    # ============================================================

    def _get_last_trading_date(self) -> str:
        """최근 거래일 (주말 제외)"""
        today = datetime.now()

        # 주말이면 금요일로
        if today.weekday() == 5:  # 토요일
            today = today - timedelta(days=1)
        elif today.weekday() == 6:  # 일요일
            today = today - timedelta(days=2)

        # 장 마감 전이면 전일
        if today.hour < 16:
            today = today - timedelta(days=1)
            if today.weekday() == 5:
                today = today - timedelta(days=1)
            elif today.weekday() == 6:
                today = today - timedelta(days=2)

        return today.strftime("%Y%m%d")

    def get_date_range(self, days: Optional[int] = None) -> List[str]:
        """과거 N 거래일 리스트"""
        if days is None:
            days = self.config.krx_analysis_days

        dates = []
        current = datetime.now()

        while len(dates) < days:
            if current.weekday() < 5:  # 월~금
                dates.append(current.strftime("%Y%m%d"))
            current = current - timedelta(days=1)

        return dates

    @staticmethod
    def _parse_number(value) -> float:
        """숫자 파싱"""
        if value is None:
            return 0.0
        try:
            if isinstance(value, str):
                value = value.replace(",", "").replace(" ", "")
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_int(value) -> int:
        """정수 파싱"""
        return int(KRXOpenAPIClient._parse_number(value))
