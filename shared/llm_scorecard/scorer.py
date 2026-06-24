from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import shared.llm_scorecard.facets  # noqa: F401  (populate FACET_REGISTRY)
from shared.llm_scorecard.facets.base import FacetPrediction, enabled_facets

logger = logging.getLogger(__name__)


def _score_to_dict(fs: Any) -> dict:
    """Build the ledger row dict manually (avoids datetime-serialization fragility)."""
    return {
        "date_kst": fs.date_kst,
        "facet": fs.facet,
        "correct": fs.correct,
        "value": fs.value,
        "economic_proxy": fs.economic_proxy,
        "baseline_value": fs.baseline_value,
        "edge": fs.edge,
        "detail": fs.detail,
        "scored_at": (fs.scored_at or datetime.now()).isoformat(),
    }


def score_day(date_kst: str | date, cfg: Any, ledger: Any, outcome: Any) -> int:
    """Score every enabled facet for ``date_kst`` and persist each result.

    Public module-level API consumed by the scorer cron (Task 9) and Phase 3/4.

    - Iterates ``enabled_facets(cfg)`` (a disabled facet is never scored even if a
      prediction was stored for it).
    - Unscorable days (``correct is None``) are STILL persisted so the ledger
      records ``correct=NULL`` — an unscorable call is never counted wrong.
    - Returns the count of facets persisted.
    """
    date_str = date_kst.isoformat() if isinstance(date_kst, date) else str(date_kst)
    preds = {p["facet"]: p for p in ledger.load_predictions(date_str)}
    n = 0
    for facet in enabled_facets(cfg):
        p = preds.get(facet.name)
        if p is None:
            continue
        try:
            pred = FacetPrediction(
                facet=facet.name,
                date_kst=p["date_kst"],
                captured_at=datetime.fromisoformat(p["captured_at"]),
                payload=p["payload"],
                confidence=p.get("confidence"),
            )
            fs = facet.score(pred, outcome)
            if fs is None:
                continue
            ledger.save_score(_score_to_dict(fs))
            n += 1
        except Exception:
            logger.exception("scorecard scoring failed facet=%s", facet.name)
    return n
