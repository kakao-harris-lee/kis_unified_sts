"""P6-c: _send_telegram_alerts staticmethod regression (096d22f2 sibling).

The 096d22f2 refactor ("Refactor LLM analysis modules by responsibility") stacked
SEVEN ``@staticmethod`` decorators onto
``UnifiedTradingAnalyzer._send_telegram_alerts`` even though the method declares a
``self`` parameter and forwards it straight through:

    @staticmethod              # (x7)
    async def _send_telegram_alerts(self, stock_plans, futures_plan, ...):
        await _reporting.send_telegram_alerts(self, stock_plans, ...)

``reporting.send_telegram_alerts`` dereferences the forwarded object as an
analyzer (``analyzer.notifier``, ``analyzer.datetime_str``). Because the method
was static, the live call site inside ``run`` —

    await self._send_telegram_alerts(
        stock_plans, futures_plan, futures_analysis, stock_analysis
    )

never bound the instance: the four positional args slotted into
``(self, stock_plans, futures_plan, futures_analysis)`` so ``self`` became the
``stock_plans`` *list*. ``reporting.send_telegram_alerts`` then evaluated
``analyzer.notifier`` on that list → ``AttributeError`` — a latent crash on the
first real Telegram-alert dispatch (the call site is gated by
``if send_telegram and self.notifier``). The prior suite exercised the reporting
helper directly but never drove the *instance-bound* wrapper, so the regression
stayed uncovered. These tests close that gap by invoking the alert path **through
an instance** (``analyzer._send_telegram_alerts(...)``), the exact shape that
regressed. This mirrors ``test_futures_analysis_staticmethod.py`` (P6-a).
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

from shared.llm.unified_trading_analyzer import UnifiedTradingAnalyzer


class _Plan:
    """Minimal stand-in for Stock/FuturesTradingPlan (only ``to_telegram_message``)."""

    def to_telegram_message(self) -> str:
        return "PLAN-BODY"


def _analyzer(datetime_str: str = "2026-07-10 08:30:00") -> UnifiedTradingAnalyzer:
    """Build a real ``UnifiedTradingAnalyzer`` instance without the heavy __init__.

    ``__init__`` wires up a dozen collectors/clients irrelevant to Telegram
    dispatch; ``object.__new__`` gives us a genuine instance whose method
    resolution is identical to production, and we populate only the two
    attributes the alert path reads.
    """
    analyzer = object.__new__(UnifiedTradingAnalyzer)
    analyzer.notifier = AsyncMock()
    analyzer.datetime_str = datetime_str
    return analyzer


# --------------------------------------------------------------------------- #
# Structural lock — the method must be a plain instance method, never static.
# --------------------------------------------------------------------------- #
def test_send_telegram_alerts_is_not_staticmethod():
    raw = inspect.getattr_static(UnifiedTradingAnalyzer, "_send_telegram_alerts")
    assert not isinstance(raw, staticmethod), (
        "_send_telegram_alerts uses self.notifier/self.datetime_str; it must be an "
        "instance method so self binds at the call site (096d22f2 stacked 7 "
        "@staticmethod here → instance-bound calls crashed)."
    )


# --------------------------------------------------------------------------- #
# Behavioral — instance-bound dispatch must not crash and must bind self.
# --------------------------------------------------------------------------- #
async def test_send_telegram_alerts_instance_bound_binds_self_and_dispatches():
    analyzer = _analyzer(datetime_str="2026-07-10 08:30:00")

    # Before the fix: static → self bound to the [] stock_plans list, and
    # reporting raised AttributeError on ``list.notifier``.
    await analyzer._send_telegram_alerts([], None, {}, None)

    assert analyzer.notifier.send_message.await_count >= 1
    # self bound to the analyzer (not the stock_plans list): reporting stamps
    # ``analyzer.datetime_str`` into the header — proving correct binding.
    header = analyzer.notifier.send_message.await_args_list[0].args[0]
    assert "2026-07-10 08:30:00" in header


async def test_send_telegram_alerts_forwards_plans_and_missing_sources():
    analyzer = _analyzer()

    await analyzer._send_telegram_alerts(
        [_Plan(), _Plan()],  # stock_plans → per-plan dispatch loop
        _Plan(),  # futures_plan → to_telegram_message()
        {"missing_sources": ["futures_flow"]},  # rendered as a warning block
        None,
    )

    sent = [c.args[0] for c in analyzer.notifier.send_message.await_args_list]
    # futures_plan + stock plans forwarded through the (now bound) instance.
    assert any("PLAN-BODY" in m for m in sent)
    # missing_sources block rendered from futures_analysis.
    assert any("선물 데이터 누락" in m for m in sent)
