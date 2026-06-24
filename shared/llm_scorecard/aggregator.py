from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from shared.llm_scorecard.config import ScorecardConfig


class RollingAggregator:
    def __init__(self, cfg: ScorecardConfig, ledger: Any) -> None:
        self._cfg = cfg
        self._ledger = ledger

    def rolling_metrics(self, facet: str, window: int) -> dict:
        end = date.today()
        start = end - timedelta(days=window)
        rows = self._ledger.query_scores(
            facet=facet,
            start=start.isoformat(),
            end=end.isoformat(),
        )
        n = len(rows)
        if n == 0:
            return {"accuracy": 0.0, "edge": 0.0, "n": 0, "correct": 0}
        correct_rows = [r for r in rows if r["correct"] is True]
        correct = len(correct_rows)
        accuracy = correct / n
        baseline = sum(r["baseline_value"] for r in rows) / n
        edge = accuracy - baseline
        return {"accuracy": accuracy, "edge": edge, "n": n, "correct": correct}

    def calibration_bins(self, facet: str, n_bins: int = 5) -> list[dict]:
        rows = self._ledger.query_scores(facet=facet)
        bins_data: list[tuple[float, bool]] = []
        dates = {r["date_kst"] for r in rows}
        score_by_date = {r["date_kst"]: r for r in rows}
        for d in dates:
            preds = self._ledger.load_predictions(d)
            for p in preds:
                if p["facet"] == facet and p.get("confidence") is not None:
                    score_row = score_by_date.get(d)
                    if score_row is not None and score_row["correct"] is not None:
                        bins_data.append((float(p["confidence"]), bool(score_row["correct"])))
        if not bins_data:
            return []
        bin_size = 1.0 / n_bins
        result = []
        for i in range(n_bins):
            low = i * bin_size
            high = (i + 1) * bin_size
            in_bin = [(c, v) for c, v in bins_data if low <= c < high]
            if not in_bin:
                continue
            acc = sum(1 for _, v in in_bin if v) / len(in_bin)
            result.append({"bin_low": low, "bin_high": high, "accuracy": acc, "n": len(in_bin)})
        return result
