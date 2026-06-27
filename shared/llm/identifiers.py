"""Identifier helpers for Korean markets (KRX/DART/KSD/SEIBRO).

This module centralizes mapping logic so data collectors can be called with the
correct identifier types (e.g., stock_code vs ISIN vs DART corp_code).
"""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import requests

logger = logging.getLogger(__name__)


def normalize_krx_stock_code(code: str) -> str | None:
    """Normalize KRX stock code to 6 digits."""
    c = (code or "").strip()
    if not c:
        return None
    if c.isdigit() and len(c) == 6:
        return c
    return None


def _isin_expand_to_digits(isin: str) -> str:
    digits = []
    for ch in isin:
        if ch.isdigit():
            digits.append(ch)
        elif ch.isalpha():
            digits.append(str(ord(ch.upper()) - ord("A") + 10))
        else:
            raise ValueError(f"Invalid ISIN character: {ch!r}")
    return "".join(digits)


def calculate_isin_check_digit(isin_without_check_digit: str) -> str:
    """Calculate ISIN check digit (Luhn) for 11-char ISIN body."""
    digits = _isin_expand_to_digits(isin_without_check_digit)
    total = 0

    # Luhn (ISIN): starting from the right, double every second digit (i=0,2,4...)
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n = n * 2
            total += n // 10 + n % 10
        else:
            total += n

    return str((10 - (total % 10)) % 10)


def krx_stock_code_to_isin(stock_code: str) -> str | None:
    """Convert 6-digit KRX stock code to ISIN (best-effort).

    For most KRX-listed equities/ETFs, ISIN format is:
      KR7 + {stock_code} + 00 + {check_digit}
    """
    code = normalize_krx_stock_code(stock_code)
    if code is None:
        return None

    body = f"KR7{code}00"  # 11 chars
    return body + calculate_isin_check_digit(body)


def to_isin(code_or_isin: str) -> str | None:
    """Accept either ISIN or 6-digit stock code and return ISIN."""
    s = (code_or_isin or "").strip()
    if not s:
        return None
    if len(s) == 12 and s[:2].isalpha() and s[2:].isalnum():
        # Likely already ISIN
        return s.upper()
    return krx_stock_code_to_isin(s)


@dataclass
class DARTCorpCodeMapper:
    """Maps KRX stock codes to DART corp_codes with an optional cached file.

    - Cache path can be set via DART_CORP_CODE_MAP_PATH or provided directly.
    - If cache is missing and API key is available, it can refresh from DART
      corpCode.xml (large file).
    """

    api_key: str = ""
    cache_path: Path = Path("output/llm/dart_corp_codes.json")
    auto_refresh: bool = False

    _map: dict[str, str] = None  # type: ignore[assignment]
    _loaded: bool = False

    def __post_init__(self) -> None:
        env_path = os.environ.get("DART_CORP_CODE_MAP_PATH")
        if env_path:
            self.cache_path = Path(env_path)
        self.auto_refresh = self.auto_refresh or (
            os.environ.get("DART_CORP_CODE_AUTO_REFRESH", "false").lower() == "true"
        )

    def _load_cache(self) -> None:
        if self._loaded:
            return
        self._map = {}
        try:
            if self.cache_path.exists():
                self._map = json.loads(self.cache_path.read_text(encoding="utf-8"))
                logger.info(f"Loaded DART corp_code map: {len(self._map)} entries")
        except Exception as e:
            logger.warning(f"Failed to load DART corp_code cache: {e}")
            self._map = {}
        finally:
            self._loaded = True

    def get_corp_code(self, stock_code: str) -> str | None:
        self._load_cache()
        code = normalize_krx_stock_code(stock_code)
        if code is None:
            return None

        corp = self._map.get(code)
        if corp:
            return corp

        if self.auto_refresh and self.api_key:
            try:
                self.refresh()
                return self._map.get(code)
            except Exception as e:
                logger.warning(f"Failed to refresh DART corp_code map: {e}")

        return None

    def refresh(self) -> None:
        """Download and rebuild corp_code mapping from DART corpCode.xml."""
        if not self.api_key:
            raise ValueError("DART api_key not configured")

        url = "https://opendart.fss.or.kr/api/corpCode.xml"
        resp = requests.get(url, params={"crtfc_key": self.api_key}, timeout=30)
        resp.raise_for_status()

        # Response is a ZIP containing CORPCODE.xml
        mapping: dict[str, str] = {}
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not xml_names:
                raise ValueError("corpCode.xml response missing XML payload")
            xml_bytes = zf.read(xml_names[0])

        root = ElementTree.fromstring(xml_bytes)
        for item in root.findall(".//list"):
            corp_code = (item.findtext("corp_code") or "").strip()
            stock_code = (item.findtext("stock_code") or "").strip()
            if corp_code and stock_code and stock_code.isdigit() and len(stock_code) == 6:
                mapping[stock_code] = corp_code

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._map = mapping
        self._loaded = True
        logger.info(f"Refreshed DART corp_code map: {len(mapping)} entries")
