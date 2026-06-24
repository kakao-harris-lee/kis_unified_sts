from __future__ import annotations

from typing import Any


def _mark(correct: Any) -> str:
    """✅/❌/⚪ for True/False/None (unscorable)."""
    return "✅" if correct is True else ("❌" if correct is False else "⚪")


def format_daily(date_kst: Any, day_scores: list[dict], rolling: dict) -> str:
    """Telegram-ready daily scorecard. Pure: receives a day's score rows + rolling.

    Public module-level API consumed by the scorer cron (Task 9) and Phase 3/4.
    """
    lines = [f"📊 <b>LLM 콜 채점 {date_kst}</b>", "━━━━━━━━━━━━━━━━━━━━"]
    for s in day_scores:
        d = s.get("detail", {}) or {}
        lines.append(
            f"{_mark(s.get('correct'))} <b>{s['facet']}</b> "
            f"edge={s.get('edge', 0.0):+.2f} "
            f"({d.get('predicted', '?')}→{d.get('realized', '?')})"
        )
    hr = rolling.get("hit_rate")
    hr_s = f"{hr * 100:.0f}%" if hr is not None else "n/a"
    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"롤링({rolling.get('n_scored', 0)}일) hit-rate={hr_s} "
        f"mean_edge={rolling.get('mean_edge', 0):+.2f}",
    ]
    return "\n".join(lines)


def format_weekly(window: Any, by_facet: dict[str, dict]) -> str:
    """Telegram-ready weekly digest. Pure: receives per-facet rolling metrics."""
    lines = [f"🗓️ <b>LLM 스코어카드 주간 ({window}일 롤링)</b>", "━━━━━━━━━━━━━━━━━━━━"]
    for facet, m in by_facet.items():
        hr = m.get("hit_rate")
        hr_s = f"{hr * 100:.0f}%" if hr is not None else "n/a"
        useful = "유용" if (m.get("mean_edge", 0) > 0 and (hr or 0) > 0.5) else "미입증"
        lines.append(
            f"<b>{facet}</b>: hit={hr_s} edge={m.get('mean_edge', 0):+.2f} "
            f"econ={m.get('econ_proxy_sum', 0):+.1f} n={m.get('n_scored', 0)} → {useful}"
        )
    return "\n".join(lines)
