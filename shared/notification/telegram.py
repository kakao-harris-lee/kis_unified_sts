"""
Telegram Notifier Module

Sends trading signals, system status, and analysis results via Telegram.
Includes trading hours awareness to avoid notifications outside market hours.
"""
import asyncio
import logging
import os
from datetime import datetime, time
from typing import Optional

logger = logging.getLogger(__name__)


def _parse_time(time_str: str) -> time:
    """HH:MM 형식 문자열을 time 객체로 변환"""
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))


class TelegramNotifier:
    """텔레그램 알림 클래스

    장 운영 시간 기반 알림 제어:
    - 알림 활성 시간: notification_start ~ notification_end
    - 중요 알림 (에러, 시스템 시작/종료)은 시간 제한 무시 가능
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        notification_start: str = "08:30",
        notification_end: str = "15:40",
        critical_always: bool = True,
    ):
        """
        Args:
            bot_token: 텔레그램 봇 토큰 (None이면 환경변수 사용)
            chat_id: 텔레그램 채팅 ID (None이면 환경변수 사용)
            notification_start: 알림 시작 시간 (HH:MM)
            notification_end: 알림 종료 시간 (HH:MM)
            critical_always: 중요 알림은 시간 제한 무시
        """
        self.token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.bot = None
        self.critical_always = critical_always

        # 알림 활성화 시간 파싱
        self._notification_start = _parse_time(notification_start)
        self._notification_end = _parse_time(notification_end)

        if self.token:
            try:
                from telegram import Bot
                self.bot = Bot(token=self.token)
                logger.info("TelegramNotifier initialized")
                logger.info(
                    f"  Notification active hours: {notification_start} ~ {notification_end}"
                )
            except ImportError:
                logger.warning("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            except Exception as e:
                logger.warning(f"Failed to initialize Telegram bot: {e}")
        else:
            logger.warning("Telegram bot not configured (TELEGRAM_BOT_TOKEN missing)")

    def is_notification_active(self) -> bool:
        """현재 시간이 알림 활성화 시간인지 확인

        Returns:
            True: 알림 활성화 시간
            False: 알림 비활성화 시간
        """
        now = datetime.now().time()
        return self._notification_start <= now <= self._notification_end

    async def send_message(
        self,
        message: str,
        disable_notification: bool = False,
        is_critical: bool = False
    ):
        """기본 메시지 전송

        Args:
            message: 전송할 메시지
            disable_notification: 알림음 비활성화 여부
            is_critical: 중요 알림 여부 (True면 시간 제한 무시)
        """
        if not self.bot or not self.chat_id:
            logger.debug("Telegram bot not configured. Skipping notification.")
            return

        # 시간 체크: 장 운영 시간 외에는 알림 차단 (중요 알림 제외)
        if not is_critical and not self.is_notification_active():
            if self.critical_always:
                logger.debug(
                    f"Notification skipped (outside trading hours): {message[:30]}..."
                )
                return

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                disable_notification=disable_notification,
                parse_mode='HTML'
            )
            logger.debug(f"Sent Telegram message: {message[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    async def send_error(self, error_msg: str):
        """에러 알림 (중요 알림 - 시간 제한 무시)"""
        await self.send_message(f"🚨 <b>ERROR</b>\n{error_msg}", is_critical=True)

    async def send_system_start(self, strategies: list = None, auto_trading: bool = False):
        """시스템 시작 알림 (중요 알림 - 시간 제한 무시)"""
        strategies_str = ', '.join(strategies) if strategies else "N/A"
        msg = (
            "🚀 <b>시스템 시작</b>\n"
            f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"전략: {strategies_str}\n"
            f"자동매매: {'✅' if auto_trading else '❌ (알림만)'}"
        )
        await self.send_message(msg, is_critical=True)

    async def send_system_stop(self):
        """시스템 종료 알림 (중요 알림 - 시간 제한 무시)"""
        msg = (
            "🛑 <b>시스템 종료</b>\n"
            f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await self.send_message(msg, is_critical=True)

    async def send_buy_signal(
        self,
        code: str,
        name: str,
        price: float,
        strategy: str,
        confidence: float = None,
        reason: str = None
    ):
        """매수 시그널 알림

        Args:
            code: 종목 코드
            name: 종목명
            price: 현재가
            strategy: 전략명
            confidence: 신뢰도 (0.0 ~ 1.0)
            reason: 추가 사유
        """
        msg = f"🟢 <b>매수 시그널</b>\n"
        msg += f"종목: {name} ({code})\n"
        msg += f"가격: {price:,}원\n"
        msg += f"전략: {strategy}\n"

        if confidence is not None:
            msg += f"신뢰도: {confidence:.1%}\n"

        if reason:
            msg += f"사유: {reason}\n"

        msg += f"시간: {datetime.now().strftime('%H:%M:%S')}"

        await self.send_message(msg)

    async def send_buy_executed(
        self,
        code: str,
        name: str,
        price: float,
        quantity: int,
        amount: int,
        strategy: str
    ):
        """매수 체결 알림

        Args:
            code: 종목 코드
            name: 종목명
            price: 체결가
            quantity: 체결 수량
            amount: 체결 금액
            strategy: 전략명
        """
        msg = f"✅ <b>매수 체결</b>\n"
        msg += f"종목: {name} ({code})\n"
        msg += f"체결가: {price:,}원\n"
        msg += f"수량: {quantity}주\n"
        msg += f"금액: {amount:,}원\n"
        msg += f"전략: {strategy}\n"
        msg += f"시간: {datetime.now().strftime('%H:%M:%S')}"

        await self.send_message(msg)

    async def send_sell_signal(
        self,
        code: str,
        name: str,
        price: float,
        reason: str,
        profit_rate: float = None,
        holding_time: str = None
    ):
        """매도 시그널 알림

        Args:
            code: 종목 코드
            name: 종목명
            price: 현재가
            reason: 매도 사유
            profit_rate: 수익률
            holding_time: 보유 시간
        """
        emoji = "🔴" if profit_rate and profit_rate < 0 else "🟡"
        msg = f"{emoji} <b>매도 시그널</b>\n"
        msg += f"종목: {name} ({code})\n"
        msg += f"가격: {price:,}원\n"
        msg += f"사유: {reason}\n"

        if profit_rate is not None:
            sign = "+" if profit_rate >= 0 else ""
            msg += f"수익률: {sign}{profit_rate:.2%}\n"

        if holding_time:
            msg += f"보유시간: {holding_time}\n"

        msg += f"시간: {datetime.now().strftime('%H:%M:%S')}"

        await self.send_message(msg)

    async def send_sell_executed(
        self,
        code: str,
        name: str,
        price: float,
        quantity: int,
        amount: int,
        profit: int,
        profit_rate: float
    ):
        """매도 체결 알림

        Args:
            code: 종목 코드
            name: 종목명
            price: 체결가
            quantity: 체결 수량
            amount: 체결 금액
            profit: 손익 (원)
            profit_rate: 수익률
        """
        emoji = "✅" if profit >= 0 else "❌"
        sign = "+" if profit >= 0 else ""

        msg = f"{emoji} <b>매도 체결</b>\n"
        msg += f"종목: {name} ({code})\n"
        msg += f"체결가: {price:,}원\n"
        msg += f"수량: {quantity}주\n"
        msg += f"금액: {amount:,}원\n"
        msg += f"손익: {sign}{profit:,}원 ({sign}{profit_rate:.2%})\n"
        msg += f"시간: {datetime.now().strftime('%H:%M:%S')}"

        await self.send_message(msg)

    async def send_daily_summary(
        self,
        total_trades: int,
        win_trades: int,
        total_profit: int,
        win_rate: float
    ):
        """일일 요약 알림 (중요 알림 - 시간 제한 무시)

        Args:
            total_trades: 총 거래 수
            win_trades: 수익 거래 수
            total_profit: 총 손익
            win_rate: 승률
        """
        sign = "+" if total_profit >= 0 else ""
        emoji = "📈" if total_profit >= 0 else "📉"

        msg = f"{emoji} <b>일일 요약</b>\n"
        msg += f"총 거래: {total_trades}건\n"
        msg += f"수익: {win_trades}건\n"
        msg += f"손실: {total_trades - win_trades}건\n"
        msg += f"승률: {win_rate:.1%}\n"
        msg += f"총 손익: {sign}{total_profit:,}원"

        await self.send_message(msg, is_critical=True)

    async def send_balance_summary(
        self,
        cash_balance: int,
        total_eval_amount: int,
        total_purchase_amount: int,
        total_unrealized_pnl: int,
        total_unrealized_pnl_pct: float,
        position_count: int
    ):
        """계좌 잔고 요약 알림 (매시간)

        Args:
            cash_balance: 예수금 (현금 잔고)
            total_eval_amount: 주식 총평가금액
            total_purchase_amount: 주식 매입금액 합계
            total_unrealized_pnl: 평가손익 합계
            total_unrealized_pnl_pct: 평가손익률
            position_count: 보유 종목 수
        """
        total_asset = cash_balance + total_eval_amount
        sign = "+" if total_unrealized_pnl >= 0 else ""
        emoji = "📈" if total_unrealized_pnl >= 0 else "📉"

        msg = f"💰 <b>계좌 잔고</b> ({datetime.now().strftime('%H:%M')})\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"총 자산: {total_asset:,}원\n"
        msg += f"  ├ 예수금: {cash_balance:,}원\n"
        msg += f"  └ 주식: {total_eval_amount:,}원\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"보유종목: {position_count}개\n"
        msg += f"매입금액: {total_purchase_amount:,}원\n"
        msg += f"{emoji} 평가손익: {sign}{total_unrealized_pnl:,}원 ({sign}{total_unrealized_pnl_pct:.2f}%)"

        await self.send_message(msg, disable_notification=True)


# ============================================================
# Singleton and Convenience Functions
# ============================================================


_default_notifier: Optional[TelegramNotifier] = None


def get_telegram_notifier() -> TelegramNotifier:
    """Get or create default TelegramNotifier instance"""
    global _default_notifier
    if _default_notifier is None:
        _default_notifier = TelegramNotifier()
    return _default_notifier


async def send_telegram(message: str, is_critical: bool = False):
    """Convenience function to send telegram message"""
    notifier = get_telegram_notifier()
    await notifier.send_message(message, is_critical=is_critical)
