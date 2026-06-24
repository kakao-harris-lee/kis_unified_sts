from __future__ import annotations

import logging
from typing import Any

import shared.llm_scorecard.facets  # noqa: F401  (populate FACET_REGISTRY)
from shared.llm_scorecard.facets.base import CaptureContext, enabled_facets

logger = logging.getLogger(__name__)


def capture_predictions(ctx: CaptureContext, cfg: Any, ledger: Any) -> int:
    """Capture predictions for every enabled facet (best-effort; never raises).

    Public module-level API consumed by the briefing hook (Task 9) and Phase 3/4.
    Returns the count of predictions captured + persisted.
    """
    n = 0
    for facet in enabled_facets(cfg):
        try:
            pred = facet.capture(ctx)
            if pred is None:
                continue
            ledger.save_prediction(
                pred.date_kst,
                pred.facet,
                pred.captured_at.isoformat(),
                pred.payload,
                pred.confidence,
            )
            n += 1
        except Exception:
            logger.exception(
                "scorecard capture failed for facet=%s", getattr(facet, "name", "?")
            )
    return n
