"""알림 서비스 테스트"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestTelegramConfig:
    """Telegram 설정 테스트"""

    def test_from_env_with_values(self):
        """환경변수에서 설정 로드"""
        from services.monitoring.notifier import TelegramConfig

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_CHAT_ID": "test-chat-id",
        }):
            config = TelegramConfig.from_env()
            assert config.token == "test-token"
            assert config.chat_id == "test-chat-id"
            assert config.is_configured is True

    def test_from_env_without_values(self):
        """환경변수 미설정 시"""
        from services.monitoring.notifier import TelegramConfig

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(os, "getenv", return_value=""):
                config = TelegramConfig.from_env()
                assert config.is_configured is False

    def test_repr_hides_sensitive_data(self):
        """repr에서 민감 정보 숨김"""
        from services.monitoring.notifier import TelegramConfig

        config = TelegramConfig(token="secret-token", chat_id="secret-chat")
        repr_str = repr(config)

        # token과 chat_id가 repr에 노출되지 않아야 함
        assert "secret-token" not in repr_str
        assert "secret-chat" not in repr_str


class TestTelegramNotifier:
    """Telegram 알림 테스트"""

    def test_mask_sensitive(self):
        """민감 정보 마스킹"""
        from services.monitoring.notifier import TelegramNotifier

        assert TelegramNotifier._mask_sensitive("") == "****"
        assert TelegramNotifier._mask_sensitive("ab") == "****"
        assert TelegramNotifier._mask_sensitive("abcdef") == "ab...ef"
        assert TelegramNotifier._mask_sensitive("1234567890") == "12...90"

    @pytest.mark.asyncio
    async def test_send_when_not_configured(self):
        """미설정 시 전송 스킵"""
        from services.monitoring.notifier import TelegramConfig, TelegramNotifier

        config = TelegramConfig(token="", chat_id="")
        notifier = TelegramNotifier(config)

        result = await notifier.send("test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_session_reuse(self):
        """세션 재사용 확인"""
        from services.monitoring.notifier import TelegramConfig, TelegramNotifier

        config = TelegramConfig(token="test", chat_id="123")
        notifier = TelegramNotifier(config)

        # 첫 번째 세션 생성
        session1 = await notifier._ensure_session()
        # 두 번째 호출 시 같은 세션 반환
        session2 = await notifier._ensure_session()

        if session1 is not None:
            assert session1 is session2

        await notifier.close()

    @pytest.mark.asyncio
    async def test_close_session(self):
        """세션 종료"""
        from services.monitoring.notifier import TelegramConfig, TelegramNotifier

        config = TelegramConfig(token="test", chat_id="123")
        notifier = TelegramNotifier(config)

        await notifier._ensure_session()
        await notifier.close()

        assert notifier._session is None


class TestNotificationTemplates:
    """알림 템플릿 테스트"""

    def test_trade_result_template(self):
        """거래 결과 템플릿"""
        from services.monitoring.notifier import NotificationTemplates

        result = NotificationTemplates.TRADE_RESULT.substitute(
            name="삼성전자",
            code="005930",
            entry_price="70,000",
            exit_price="72,000",
            exit_reason="목표가 도달",
            pnl_emoji="🟢",
            pnl="+200,000",
            pnl_pct="+2.86",
        )

        assert "삼성전자" in result
        assert "005930" in result
        assert "70,000" in result
        assert "72,000" in result
        assert "🟢" in result

    def test_daily_summary_template(self):
        """일일 요약 템플릿"""
        from services.monitoring.notifier import NotificationTemplates

        result = NotificationTemplates.DAILY_SUMMARY.substitute(
            date="2024-01-15",
            total_trades="10",
            winning_trades="7",
            win_rate="70.0",
            pnl_emoji="🟢",
            total_pnl="+1,500,000",
            total_return_pct="+1.50",
        )

        assert "2024-01-15" in result
        assert "10" in result
        assert "70.0" in result


class TestConsoleNotifier:
    """콘솔 알림 테스트"""

    @pytest.mark.asyncio
    async def test_send(self, capsys):
        """메시지 전송"""
        from services.monitoring.notifier import ConsoleNotifier

        notifier = ConsoleNotifier()
        result = await notifier.send("test message")

        assert result is True
        captured = capsys.readouterr()
        assert "[NOTIFY]" in captured.out
        assert "test message" in captured.out

    @pytest.mark.asyncio
    async def test_send_alert(self, capsys):
        """알림 전송"""
        from services.monitoring.notifier import AlertLevel, ConsoleNotifier

        notifier = ConsoleNotifier()
        result = await notifier.send_alert("error occurred", AlertLevel.ERROR)

        assert result is True
        captured = capsys.readouterr()
        assert "[ALERT:ERROR]" in captured.out


class TestMultiNotifier:
    """복수 알림 테스트"""

    @pytest.mark.asyncio
    async def test_send_to_all(self):
        """모든 notifier에 전송"""
        from services.monitoring.notifier import MultiNotifier, Notifier

        mock1 = AsyncMock(spec=Notifier)
        mock1.send.return_value = True
        mock2 = AsyncMock(spec=Notifier)
        mock2.send.return_value = True

        multi = MultiNotifier([mock1, mock2])
        result = await multi.send("test")

        assert result is True
        mock1.send.assert_called_once_with("test")
        mock2.send.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_close_all(self):
        """모든 notifier 종료"""
        from services.monitoring.notifier import MultiNotifier, Notifier

        mock1 = AsyncMock(spec=Notifier)
        mock2 = AsyncMock(spec=Notifier)

        multi = MultiNotifier([mock1, mock2])
        await multi.close()

        mock1.close.assert_called_once()
        mock2.close.assert_called_once()
