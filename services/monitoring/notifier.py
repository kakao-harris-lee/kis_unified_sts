"""알림 서비스

텔레그램, 슬랙 등 알림 전송.

Usage:
    from services.monitoring import TelegramNotifier

    notifier = TelegramNotifier.from_env()  # 환경변수에서 설정 로드

    await notifier.send("거래 시작!")
    await notifier.send_alert("에러 발생!", level="error")

    # 종료 시 세션 정리
    await notifier.close()
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from enum import Enum
from string import Template
from typing import Any

from pydantic import Field

from shared.config.base import ServiceConfigBase

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

    async def close(self) -> None:
        """리소스 정리"""
        pass


# =============================================================================
# 메시지 템플릿
# =============================================================================


class NotificationTemplates:
    """알림 메시지 템플릿"""

    TRADE_RESULT = Template(
        "<b>📊 거래 완료</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "종목: $name ($code)\n"
        "진입가: $entry_price\n"
        "청산가: $exit_price\n"
        "청산사유: $exit_reason\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "$pnl_emoji 손익: $pnl원 ($pnl_pct%)"
    )

    DAILY_SUMMARY = Template(
        "<b>📈 일일 요약</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📅 날짜: $date\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "총 거래: $total_trades건\n"
        "승리: $winning_trades건\n"
        "승률: $win_rate%\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "$pnl_emoji 총 손익: $total_pnl원 ($total_return_pct%)"
    )

    ERROR = Template(
        "<b>⚠️ [$component] 에러 발생</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "$error_message"
    )


# =============================================================================
# Telegram 알림
# =============================================================================


class TelegramConfig(ServiceConfigBase):
    """Telegram 설정

    Attributes:
        token: 봇 토큰 (환경변수에서 로드)
        chat_id: 채팅 ID (환경변수에서 로드)
        parse_mode: HTML or Markdown
        disable_notification: 알림음 비활성화
    """

    token: str = Field(default="", repr=False, description="Telegram bot token")
    chat_id: str = Field(default="", repr=False, description="Telegram chat ID")
    parse_mode: str = Field(default="HTML", description="Message parse mode (HTML or Markdown)")
    disable_notification: bool = Field(default=False, description="Disable notification sound")

    # Default env prefix for ServiceConfigBase
    _env_prefix = "TELEGRAM_"

    @classmethod
    def from_env(cls, env_prefix: str | None = None, **overrides: Any) -> "TelegramConfig":
        """환경변수에서 설정 로드

        Handles non-standard env var names:
        - TELEGRAM_BOT_TOKEN → token
        - TELEGRAM_CHAT_ID → chat_id
        """
        # Custom env var mapping for Telegram (non-standard naming)
        env_data = {}

        # Map TELEGRAM_BOT_TOKEN to token
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if token:
            env_data["token"] = token

        # Map TELEGRAM_CHAT_ID to chat_id
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        if chat_id:
            env_data["chat_id"] = chat_id

        # Standard prefix-based mapping for other fields
        for field_name in ("parse_mode", "disable_notification"):
            env_key = f"TELEGRAM_{field_name.upper()}"
            env_value = os.getenv(env_key)
            if env_value is not None:
                env_data[field_name] = env_value

        # Apply overrides
        env_data.update(overrides)

        # Log warning if not configured
        if not env_data.get("token") or not env_data.get("chat_id"):
            logger.warning(
                "Telegram credentials not configured. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables."
            )

        return cls(**env_data)

    @property
    def is_configured(self) -> bool:
        """설정 완료 여부"""
        return bool(self.token and self.chat_id)


class TelegramNotifier(Notifier):
    """텔레그램 알림

    Usage:
        notifier = TelegramNotifier.from_env()

        # 일반 메시지
        await notifier.send("거래 시작!")

        # 알림 (이모지 포함)
        await notifier.send_alert("에러 발생!", AlertLevel.ERROR)

        # 거래 결과
        await notifier.send_trade_result(...)

        # 종료 시 정리
        await notifier.close()
    """

    # 레벨별 이모지
    LEVEL_EMOJIS = {
        AlertLevel.INFO: "ℹ️",
        AlertLevel.WARNING: "⚠️",
        AlertLevel.ERROR: "❌",
        AlertLevel.CRITICAL: "🚨",
    }

    def __init__(self, config: TelegramConfig):
        """
        Args:
            config: Telegram 설정
        """
        self.config = config
        self._session = None
        self._base_url = "https://api.telegram.org"

        # 마스킹된 정보만 로깅
        masked_id = self._mask_sensitive(config.chat_id)
        logger.info(f"TelegramNotifier initialized (chat_id: {masked_id})")

    @classmethod
    def from_env(cls) -> "TelegramNotifier":
        """환경변수에서 설정 로드하여 인스턴스 생성"""
        return cls(TelegramConfig.from_env())

    @staticmethod
    def _mask_sensitive(value: str) -> str:
        """민감 정보 마스킹"""
        if not value or len(value) <= 4:
            return "****"
        return f"{value[:2]}...{value[-2:]}"

    async def _ensure_session(self):
        """HTTP 세션 초기화 (재사용)"""
        if self._session is None or self._session.closed:
            try:
                import aiohttp

                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30)
                )
            except ImportError:
                logger.warning("aiohttp not installed")
                return None
        return self._session

    async def close(self) -> None:
        """HTTP 세션 종료"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("TelegramNotifier session closed")

    async def send(self, message: str, **_kwargs) -> bool:
        """메시지 전송

        Args:
            message: 전송할 메시지

        Returns:
            전송 성공 여부
        """
        if not self.config.is_configured:
            logger.debug("Telegram not configured, skipping send")
            return False

        try:
            session = await self._ensure_session()
            if session is None:
                return False

            url = f"{self._base_url}/bot{self.config.token}/sendMessage"
            payload = {
                "chat_id": self.config.chat_id,
                "text": message,
                "parse_mode": self.config.parse_mode,
                "disable_notification": self.config.disable_notification,
            }

            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.debug(f"Telegram message sent (length: {len(message)})")
                    return True
                else:
                    logger.error(f"Telegram send failed: status={response.status}")
                    return False

        except (OSError, TimeoutError) as e:
            # Network errors: connection failures, timeouts, DNS errors
            logger.error(f"Telegram network error: {e}")
            return False
        except Exception as e:
            # aiohttp-specific errors (ClientError, etc.) that we can't import without aiohttp
            logger.error(f"Telegram send error: {e}")
            return False

    async def send_alert(
        self,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        **_kwargs,
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

        message = NotificationTemplates.TRADE_RESULT.substitute(
            name=name,
            code=code,
            entry_price=f"{entry_price:,.0f}",
            exit_price=f"{exit_price:,.0f}",
            exit_reason=exit_reason,
            pnl_emoji=pnl_emoji,
            pnl=f"{pnl:+,.0f}",
            pnl_pct=f"{pnl_pct:+.2f}",
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

        message = NotificationTemplates.DAILY_SUMMARY.substitute(
            date=date_str,
            total_trades=total_trades,
            winning_trades=winning_trades,
            win_rate=f"{win_rate:.1f}",
            pnl_emoji=pnl_emoji,
            total_pnl=f"{total_pnl:+,.0f}",
            total_return_pct=f"{total_return_pct:+.2f}",
        )

        return await self.send(message)

    async def send_error(self, error_message: str, component: str = "System") -> bool:
        """에러 알림 전송"""
        message = NotificationTemplates.ERROR.substitute(
            component=component,
            error_message=error_message,
        )
        return await self.send(message)


class ConsoleNotifier(Notifier):
    """콘솔 출력 알림 (개발/테스트용)"""

    async def send(self, message: str, **_kwargs) -> bool:
        print(f"[NOTIFY] {message}")
        return True

    async def send_alert(
        self,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        **_kwargs,
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

    async def close(self) -> None:
        """모든 notifier 정리"""
        await asyncio.gather(
            *[n.close() for n in self.notifiers],
            return_exceptions=True,
        )


# 전역 notifier
_notifier: Notifier | None = None


def get_notifier() -> Notifier:
    """전역 notifier 반환"""
    global _notifier
    if _notifier is None:
        # 환경변수에서 Telegram 설정 시도
        telegram_config = TelegramConfig.from_env()
        if telegram_config.is_configured:
            _notifier = TelegramNotifier(telegram_config)
        else:
            _notifier = ConsoleNotifier()
    return _notifier


def set_notifier(notifier: Notifier):
    """전역 notifier 설정"""
    global _notifier
    _notifier = notifier


async def cleanup_notifier():
    """전역 notifier 정리"""
    global _notifier
    if _notifier:
        await _notifier.close()
        _notifier = None
