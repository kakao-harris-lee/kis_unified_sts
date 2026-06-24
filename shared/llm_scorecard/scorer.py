from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from shared.llm_scorecard.config import ScorecardConfig
from shared.llm_scorecard.facets.base import FACET_REGISTRY, FacetPrediction, FacetScore

logger = logging.getLogger(__name__)


class DayScorer:
    def __init__(self, cfg: ScorecardConfig, ledger: Any, outcome: Any) -> None:
        self._cfg = cfg
        self._ledger = ledger
        self._outcome = outcome

    def score_day(self, date_kst: date) -> list[FacetScore]:
        date_str = date_kst.isoformat()
        preds = self._ledger.load_predictions(date_str)
        scores: list[FacetScore] = []
        for pred_row in preds:
            facet_name = pred_row["facet"]
            facet = FACET_REGISTRY.get(facet_name)
            if facet is None:
                logger.warning("Facet %s not in registry, skipping", facet_name)
                continue
            pred = FacetPrediction(
                facet=facet_name,
                date_kst=pred_row["date_kst"],
                captured_at=datetime.fromisoformat(pred_row["captured_at"]),
                payload=pred_row["payload"],
                confidence=pred_row.get("confidence"),
            )
            try:
                score = facet.score(pred, self._outcome)
                if score is None:
                    continue
                score_dict = asdict(score)
                score_dict["scored_at"] = score.scored_at.isoformat() if score.scored_at else None
                self._ledger.save_score(score_dict)
                scores.append(score)
            except Exception as exc:
                logger.warning("Facet %s score failed for %s: %s", facet_name, date_str, exc)
        return scores
