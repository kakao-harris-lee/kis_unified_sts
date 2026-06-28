"""Per-asset strategy evidence summary endpoints."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from pydantic import BaseModel

from services.dashboard.domain.assets import normalize_asset_class

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

KST = ZoneInfo("Asia/Seoul")


class EvidenceGap(BaseModel):
    code: str
    severity: str
    message: str


class StrategyEvidenceSummary(BaseModel):
    strategy: str
    accepted: int
    rejected: int
    paperPnl: float | None = None
    backtestPaperDelta: float | None = None
    status: str


class EvidenceSummaryResponse(BaseModel):
    asset_class: str
    generated_at: str
    strategies: list[StrategyEvidenceSummary]
    evidence_gaps: list[EvidenceGap]


@router.get("/summary", response_model=EvidenceSummaryResponse)
async def get_evidence_summary(
    asset_class: str = Query(default="futures"),
) -> EvidenceSummaryResponse:
    """Return read-only strategy evidence grouped by selected asset class."""
    asset = normalize_asset_class(asset_class)
    now_kst = datetime.now(KST)
    return EvidenceSummaryResponse(
        asset_class=asset,
        generated_at=now_kst.isoformat(),
        strategies=[],
        evidence_gaps=[
            EvidenceGap(
                code="NO_RUNTIME_EVIDENCE",
                severity="warning",
                message="No evidence report has been connected yet.",
            )
        ],
    )
