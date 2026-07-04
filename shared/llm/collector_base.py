"""Base interfaces for LLM data collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

import requests


class DataCollector(ABC):
    """데이터 수집기 기본 클래스"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    @abstractmethod
    def collect(self, *args, **kwargs) -> dict:
        """데이터 수집"""
        pass
