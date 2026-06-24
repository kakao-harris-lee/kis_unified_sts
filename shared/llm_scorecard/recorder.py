from __future__ import annotations

import logging
from typing import Any

from shared.llm_scorecard.config import ScorecardConfig
from shared.llm_scorecard.facets.base import CaptureContext, FacetPrediction, enabled_facets

logger = logging.getLogger(__name__)


class PredictionRecorder:
    def __init__(self, cfg: ScorecardConfig, ledger: Any, ctx: CaptureContext) -> None:
        self._cfg = cfg
        self._ledger = ledger
        self._ctx = ctx

    def capture_predictions(self) -> list[FacetPrediction]:
        results: list[FacetPrediction] = []
        for facet in enabled_facets(self._cfg):
            try:
                pred = facet.capture(self._ctx)
                if pred is None:
                    continue
                self._ledger.save_prediction(
                    date_kst=pred.date_kst,
                    facet=pred.facet,
                    captured_at=pred.captured_at.isoformat(),
                    payload=pred.payload,
                    confidence=pred.confidence,
                )
                results.append(pred)
            except Exception as exc:
                logger.warning("Facet %s capture failed: %s", facet.name, exc)
        return results
