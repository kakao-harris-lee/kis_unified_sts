"""알림 서비스

텔레그램, 슬랙 등 알림 전송.

Usage:
    from services.monitoring import TelegramNotifier

    notifier = TelegramNotifier(
        token="YOUR_BOT_TOKEN",
        chat_id="YOUR_CHAT_ID",
    )

    await notifier.send("거래 시작!")
    await notifier.send_alert("에러 발생!", level="error")
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """알림 레벨"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Notifier(ABC):
    """알림 서비스 인터페이스"""

    @abstractmethod
    async def send(self, message: str, **kwargs) -> bool:
        """메시지 전송"""
        pass

    @abstractmethod
    async def send_alert(self, message: str, level: AlertLevel, **kwargs) -> bool:
        """알림 전송"""
        pass


class TelegramNotifier(Notifier):
    """텔레그램 알림

    Usage:
        notifier = TelegramNotifier(token, chat_id)

        # 일반 메시지
        await notifier.send("거래 시작!")

        # 알림 (이모지 포함)
        await notifier.send_alert("에러 발생!", AlertLevel.ERROR)

        # 거래 결과
        await notifier.send_trade_result(trade)
    """

    # 레벨별 이모지
    LEVEL_EMOJIS = {
        AlertLevel.INFO: "ℹ️",
        AlertLevel.WARNING: "⚠️",
        AlertLevel.ERROR: "❌",
        AlertLevel.CRITICAL: "🚨",
    }

    def __init__(
        self,
        token: str,
        chat_id: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ):
        """
        Args:
            token: 텔레그램 봇 토큰
            chat_id: 채팅 ID
            parse_mode: 파싱 모드 (HTML, Markdown)
            disable_notification: 알림 소리 비활성화
        """
        self.token = token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.disable_notification = disable_notification
        self.base_url = f"https://api.telegram.org/bot{token}"

        logger.info(f"TelegramNotifier initialized (chat_id: {chat_id[:4]}...)")

    async def send(self, message: str, **kwargs) -> bool:
        """메시지 전송

        Args:
            message: 전송할 메시지

        Returns:
            전송 성공 여부
        """
        try:
            import aiohttp

            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": self.parse_mode,
                "disable_notification": self.disable_notification,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.debug(f"Telegram message sent: {message[:50]}...")
                        return True
                    else:
                        text = await response.text()
                        logger.error(f"Telegram send failed: {text}")
                        return False

        except ImportError:
            logger.warning("aiohttp not installed, skipping telegram send")
            return False
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    async def send_alert(
        self,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        **kwargs,
    ) -> bool:
        """알림 전송 (레벨에 따른 이모지 포함)"""
        emoji = self.LEVEL_EMOJIS.get(level, "")
        formatted = f"{emoji} [{level.value.upper()}]\n{message}"
        return await self.send(formatted)

    async def send_trade_result(
        self,
        code: str,
        name: str,
        pnl: float,
        pnl_pct: float,
        entry_price: float,
        exit_price: float,
        exit_reason: str,
    ) -> bool:
        """거래 결과 전송"""
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"

        message = (
            f"<b>📊 거래 완료</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"종목: {name} ({code})\n"
            f"진입가: {entry_price:,.0f}\n"
            f"청산가: {exit_price:,.0f}\n"
            f"청산사유: {exit_reason}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pnl_emoji} 손익: {pnl:+,.0f}원 ({pnl_pct:+.2f}%)"
        )

        return await self.send(message)

    async def send_daily_summary(
        self,
        date_str: str,
        total_trades: int,
        winning_trades: int,
        total_pnl: float,
        total_return_pct: float,
    ) -> bool:
        """일일 요약 전송"""
        pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

        message = (
            f"<b>📈 일일 요약</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 날짜: {date_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"총 거래: {total_trades}건\n"
            f"승리: {winning_trades}건\n"
            f"승률: {win_rate:.1f}%\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pnl_emoji} 총 손익: {total_pnl:+,.0f}원 ({total_return_pct:+.2f}%)"
        )

        return await self.send(message)

    async def send_error(self, error_message: str, component: str = "System") -> bool:
        """에러 알림 전송"""
        message = (
            f"<b>⚠️ [{component}] 에러 발생</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{error_message}"
        )
        return await self.send(message)


class ConsoleNotifier(Notifier):
    """콘솔 출력 알림 (개발/테스트용)"""

    async def send(self, message: str, **kwargs) -> bool:
        print(f"[NOTIFY] {message}")
        return True

    async def send_alert(
        self,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        **kwargs,
    ) -> bool:
        print(f"[ALERT:{level.value.upper()}] {message}")
        return True


class MultiNotifier(Notifier):
    """복수 알림 서비스 래퍼"""

    def __init__(self, notifiers: list[Notifier]):
        self.notifiers = notifiers

    async def send(self, message: str, **kwargs) -> bool:
        results = await asyncio.gather(
            *[n.send(message, **kwargs) for n in self.notifiers],
            return_exceptions=True,
        )
        return all(r is True for r in results)

    async def send_alert(
        self,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        **kwargs,
    ) -> bool:
        results = await asyncio.gather(
            *[n.send_alert(message, level, **kwargs) for n in self.notifiers],
            return_exceptions=True,
        )
        return all(r is True for r in results)


# 전역 notifier
_notifier: Notifier | None = None


def get_notifier() -> Notifier:
    """전역 notifier 반환"""
    global _notifier
    if _notifier is None:
        _notifier = ConsoleNotifier()
    return _notifier


def set_notifier(notifier: Notifier):
    """전역 notifier 설정"""
    global _notifier
    _notifier = notifier
