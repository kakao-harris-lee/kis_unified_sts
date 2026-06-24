from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from shared.llm_scorecard.aggregator import RollingAggregator
from shared.llm_scorecard.config import ScorecardConfig


class DailyScorecardReporter:
    def __init__(self, cfg: ScorecardConfig, aggregator: RollingAggregator, ledger: Any) -> None:
        self._cfg = cfg
        self._agg = aggregator
        self._ledger = ledger

    def format_daily(self, date_kst: date) -> str:
        date_str = date_kst.isoformat()
        lines = [f"📊 <b>LLM 마켓 콜 스코어카드 — {date_str}</b>", ""]
        preds = self._ledger.load_predictions(date_str)
        scores = self._ledger.query_scores(start=date_str, end=date_str)
        score_by_facet = {s["facet"]: s for s in scores}
        pred_by_facet = {p["facet"]: p for p in preds}
        for facet_name in self._cfg.enabled_facets:
            score = score_by_facet.get(facet_name)
            pred = pred_by_facet.get(facet_name)
            if pred is None:
                lines.append(f"• <b>{facet_name}</b>: 예측 없음")
                continue
            direction = pred["payload"].get("direction", pred["payload"].get("overall_signal", "?"))
            if score is None:
                lines.append(f"• <b>{facet_name}</b>: {direction} → 미채점")
            else:
                result_icon = "✅" if score["correct"] else ("❌" if score["correct"] is False else "➡️")
                actual = score["detail"].get("actual", "?")
                ret = score["detail"].get("return_pct")
                ret_str = f"{ret:+.2f}%" if ret is not None else ""
                lines.append(f"• <b>{facet_name}</b>: {direction} → {actual} {result_icon} {ret_str}".strip())
            # Rolling windows
            for window in self._cfg.rolling_windows:
                m = self._agg.rolling_metrics(facet_name, window)
                if m["n"] > 0:
                    lines.append(f"  {window}일 정확도: {m['accuracy']:.1%} (N={m['n']}, edge={m['edge']:+.3f})")
        return "\n".join(lines)

    def format_weekly(self, end_date: date) -> str:
        start_date = end_date - timedelta(days=7)
        lines = [f"📊 <b>LLM 마켓 콜 주간 리포트 — {start_date} ~ {end_date}</b>", ""]
        for facet_name in self._cfg.enabled_facets:
            lines.append(f"<b>{facet_name}</b>")
            for window in self._cfg.rolling_windows:
                m = self._agg.rolling_metrics(facet_name, window)
                lines.append(f"  {window}일: accuracy={m['accuracy']:.1%}, edge={m['edge']:+.3f}, N={m['n']}")
            # Calibration
            cal = self._agg.calibration_bins(facet_name)
            if cal:
                lines.append("  캘리브레이션:")
                for b in cal:
                    lines.append(f"    [{b['bin_low']:.1f},{b['bin_high']:.1f}]: {b['accuracy']:.1%} (N={b['n']})")
        return "\n".join(lines)
