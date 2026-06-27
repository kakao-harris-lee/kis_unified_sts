# Signals Decision Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `/signals` into a read-only decision transparency surface that shows LLM context, strategy inputs, risk/orderability, lifecycle, scorecard state, and evidence gaps for the selected signal.

**Architecture:** Add a new FastAPI detail endpoint under `services/dashboard/routes/signals.py`, backed first by Redis signal rows and then enriched from RuntimeLedger and the existing trade lifecycle helpers. Add a typed frontend client and replace the current inline `SignalTraceCard` with a `DecisionTracePanel` that fetches detail on row selection while preserving the existing signal list and filters.

**Tech Stack:** Python 3.12/FastAPI/Pydantic, SQLite RuntimeLedger, Redis DB1 read paths only, Next.js 16/React 19, TanStack Query, lucide-react, pytest, Vitest Testing Library.

---

## Source Inputs

- Design spec: `docs/superpowers/specs/2026-06-27-signals-decision-trace-design.md`
- Existing signal API/page: `services/dashboard/routes/signals.py`, `strategy-builder-ui/src/app/signals/page.tsx`
- Existing lifecycle API/component: `services/dashboard/routes/trades.py`, `strategy-builder-ui/src/components/dashboard/LifecycleTimeline.tsx`
- Existing ledger tables/accessors: `shared/storage/runtime_ledger.py`
- Existing frontend API proxy fallback: `strategy-builder-ui/src/app/api/[...path]/route.ts`

## Global Constraints

- Read-only only. Do not add live order controls, trading mutations, or scorecard feedback into execution.
- New API routes go under `services/dashboard`; do not recreate `services/api`.
- RuntimeLedger is SQLite; do not add ClickHouse usage.
- Redis is read-only here. No new Redis keys are required.
- Operator-facing timestamps render in KST. Stored timestamps stay timezone-aware.
- Missing evidence must render as `missing`, `not_available`, `unknown`, `partial`, or `not_scored_yet`; never imply a pass when the source is absent.
- Scorecard lookup must never use future trading dates relative to the signal timestamp in KST.
- Preserve stock swing behavior and futures long/short symmetry by keeping this work presentation-only.

## File Structure

- Modify `services/dashboard/routes/signals.py`
  - Add `DecisionTraceResponse` and nested response models.
  - Add `GET /api/signals/{signal_id}/trace`.
  - Add read-only helpers for Redis signal lookup, RuntimeLedger enrichment, lifecycle reuse, summary text, and evidence gaps.
- Modify `tests/unit/dashboard/test_signals.py`
  - Keep existing list/history tests.
- Create `tests/unit/dashboard/test_signals_trace.py`
  - Focus endpoint tests for full evidence, missing ledger, missing LLM, prediction-only scorecard, unscorable score, partial lifecycle, and no-look-ahead.
- Create `strategy-builder-ui/src/lib/dashboard/decisionTrace.ts`
  - Define TypeScript response types and `decisionTraceApi.getDecisionTrace`.
- Modify `strategy-builder-ui/src/lib/dashboard/api.ts`
  - Re-export `decisionTraceApi`.
- Modify `strategy-builder-ui/src/app/api/[...path]/route.ts`
  - Add degraded same-origin fallback for `/api/signals/{id}/trace`.
- Modify `strategy-builder-ui/src/app/api/catchall-route.test.ts`
  - Assert degraded trace payload when dashboard API is unavailable.
- Create `strategy-builder-ui/src/app/signals/components/DecisionTracePanel.tsx`
  - Read-only dense detail panel with trace sections.
- Create `strategy-builder-ui/src/app/signals/components/DecisionTracePanel.test.tsx`
  - Component states for full trace, missing LLM, unscorable score, lifecycle gaps, and close button.
- Modify `strategy-builder-ui/src/app/signals/page.tsx`
  - Remove inline `SignalTraceCard`.
  - Fetch `DecisionTraceResponse` after row/card selection.
  - Keep filters, table behavior, and mobile cards.
- Modify `strategy-builder-ui/src/app/quant-ops-workbench.smoke.test.tsx`
  - Add `/signals` smoke coverage for row selection and decision trace rendering.
- Modify `docs/superpowers/plans/INDEX.md`
  - Add this active plan while implementation is underway.

## Response Contract

The backend endpoint is:

```text
GET /api/signals/{signal_id}/trace?asset_class={stock|futures|all}
```

The frontend consumes:

```ts
export interface DecisionTraceResponse {
  signal: DecisionTraceSignal;
  summary: DecisionTraceSummary;
  llm_context: DecisionTraceLlmContext;
  strategy_inputs: DecisionTraceStrategyInputs;
  risk_orderability: DecisionTraceRiskOrderability;
  lineage: DecisionTraceLineage;
  lifecycle: DecisionTraceLifecycle;
  scorecard: DecisionTraceScorecard;
  evidence_gaps: DecisionTraceEvidenceGap[];
}
```

---

### Task 1: Backend Basic Trace Contract From Redis Signal Rows

**Files:**
- Modify: `services/dashboard/routes/signals.py`
- Create: `tests/unit/dashboard/test_signals_trace.py`

- [ ] **Step 1: Write the failing endpoint contract test**

Create `tests/unit/dashboard/test_signals_trace.py`:

```python
"""Tests for signal decision trace endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _reader_with_signals(signals: list[dict]) -> MagicMock:
    return MagicMock(get_signals=MagicMock(return_value=signals))


async def _get(path: str):
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_signal_trace_returns_basic_signal_and_explicit_missing_gaps():
    from services.dashboard.routes import signals as signals_route

    reader = _reader_with_signals(
        [
            {
                "id": "sig-basic-1",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": False,
                "reason": "gap_reversion_candidate",
                "trace": {
                    "orderability": {"state": "paper_orderable"},
                    "reject_stage": "",
                    "reject_reason": "",
                },
            }
        ]
    )

    with patch.object(signals_route, "_get_reader", return_value=reader):
        response = await _get("/api/signals/sig-basic-1/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["signal"]["id"] == "sig-basic-1"
    assert body["signal"]["symbol"] == "101S6000"
    assert body["summary"]["state"] == "orderable"
    assert "setup_a_gap_reversion generated BUY 101S6000" in body["summary"]["text"]
    assert body["llm_context"]["status"] == "not_available"
    assert body["scorecard"]["status"] == "missing"
    assert body["lifecycle"]["status"] == "missing"
    assert {gap["code"] for gap in body["evidence_gaps"]} >= {
        "llm_context_not_available",
        "scorecard_missing",
        "no_lifecycle_evidence",
    }
```

- [ ] **Step 2: Run the test and confirm the expected failure**

Run:

```bash
pytest tests/unit/dashboard/test_signals_trace.py::test_signal_trace_returns_basic_signal_and_explicit_missing_gaps -q
```

Expected:

```text
1 failed
```

The failure should be HTTP `404` or a missing route error for `/api/signals/sig-basic-1/trace`.

- [ ] **Step 3: Add response models in `services/dashboard/routes/signals.py`**

Change the imports:

```python
from pydantic import BaseModel, Field
```

Insert after `SignalHistoryResponse`:

```python
class EvidenceGap(BaseModel):
    """One missing or degraded evidence source for the decision trace."""

    code: str
    severity: str
    message: str


class DecisionTraceSignal(BaseModel):
    """Signal identity and basic decision fields."""

    id: str
    asset_class: str
    symbol: str
    strategy: str
    side: str
    signal_type: str | None = None
    status: str | None = None
    reason: str | None = None
    confidence: float | None = None
    strength: float | None = None
    price: float | None = None
    timestamp: datetime | None = None


class DecisionTraceSummary(BaseModel):
    """Deterministic operator summary."""

    state: str
    text: str
    warnings: list[str] = Field(default_factory=list)


class DecisionTraceLlmContext(BaseModel):
    """Market context associated with the signal decision."""

    status: str
    overall_signal: str | None = None
    confidence: float | None = None
    risk_mode: str | None = None
    regime: str | None = None
    risk_score: float | None = None
    captured_at: datetime | None = None
    source: str | None = None


class DecisionTraceStrategyInputs(BaseModel):
    """Strategy-native inputs available for the signal."""

    setup_type: str | None = None
    indicators: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    event_evidence: dict[str, Any] = Field(default_factory=dict)
    raw_reason: str | None = None


class DecisionTraceRiskOrderability(BaseModel):
    """Risk and orderability status for the signal."""

    reject_stage: str | None = None
    reject_reason: str | None = None
    orderability_state: str | None = None
    orderability_details: dict[str, Any] = Field(default_factory=dict)
    risk_state: str | None = None
    risk_details: dict[str, Any] = Field(default_factory=dict)


class DecisionTraceLineage(BaseModel):
    """Known downstream runtime identifiers."""

    signal_id: str | None = None
    order_id: str | None = None
    fill_id: str | None = None
    position_id: str | None = None
    trade_id: str | None = None


class DecisionTraceLifecycle(BaseModel):
    """Compact lifecycle block embedded in the signal trace."""

    status: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DecisionTraceScorecard(BaseModel):
    """LLM prediction scorecard evidence linked to the signal."""

    status: str
    facet: str | None = None
    date_kst: str | None = None
    captured_at: datetime | None = None
    confidence: float | None = None
    correct: bool | None = None
    value: float | None = None
    economic_proxy: float | None = None
    baseline_value: float | None = None
    edge: float | None = None
    scored_at: datetime | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class DecisionTraceResponse(BaseModel):
    """Read-only signal decision trace for the dashboard."""

    signal: DecisionTraceSignal
    summary: DecisionTraceSummary
    llm_context: DecisionTraceLlmContext
    strategy_inputs: DecisionTraceStrategyInputs
    risk_orderability: DecisionTraceRiskOrderability
    lineage: DecisionTraceLineage
    lifecycle: DecisionTraceLifecycle
    scorecard: DecisionTraceScorecard
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
```

- [ ] **Step 4: Add basic trace helpers**

Insert before the existing `@router.get("", response_model=SignalListResponse)` route:

```python
def _gap(code: str, severity: str, message: str) -> EvidenceGap:
    return EvidenceGap(code=code, severity=severity, message=message)


def _trace_state(signal: SignalResponse) -> str:
    status = (signal.status or "").lower()
    orderable = (signal.orderability_state or "").lower()
    if signal.trade_id:
        return "closed"
    if signal.fill_id:
        return "filled"
    if signal.order_id:
        return "submitted"
    if status in {"rejected", "blocked"} or signal.reject_reason:
        return "rejected"
    if orderable in {"paper_orderable", "orderable", "passed"}:
        return "orderable"
    if status:
        return status
    return "generated"


def _trace_summary_text(signal: SignalResponse, state: str) -> str:
    parts = [
        signal.strategy or "unknown_strategy",
        "generated",
        signal.side or "unknown_side",
        signal.symbol or "unknown_symbol",
    ]
    if signal.reason:
        parts.append(f"from {signal.reason}")
    if signal.orderability_state:
        parts.append(f"orderability {signal.orderability_state}")
    if state in {"filled", "closed"}:
        parts.append("fill evidence is available")
    elif state in {"submitted", "orderable"}:
        parts.append("fill evidence is not available")
    return " ".join(parts) + "."


def _empty_lifecycle() -> DecisionTraceLifecycle:
    return DecisionTraceLifecycle(
        status="missing",
        steps=[],
        warnings=["no_lifecycle_evidence"],
    )


def _empty_scorecard() -> DecisionTraceScorecard:
    return DecisionTraceScorecard(status="missing")


def _basic_trace_from_signal(signal: SignalResponse) -> DecisionTraceResponse:
    state = _trace_state(signal)
    gaps = [
        _gap(
            "llm_context_not_available",
            "warning",
            "No LLM market context is linked to this signal.",
        ),
        _gap(
            "scorecard_missing",
            "info",
            "No LLM scorecard prediction or score is linked to this signal.",
        ),
        _gap(
            "no_lifecycle_evidence",
            "info",
            "No order, fill, position, or closed-trade lifecycle evidence is available.",
        ),
    ]
    return DecisionTraceResponse(
        signal=DecisionTraceSignal(
            id=signal.id,
            asset_class=signal.asset_class,
            symbol=signal.symbol,
            strategy=signal.strategy,
            side=signal.side,
            signal_type=signal.signal_type,
            status=signal.status,
            reason=signal.reason,
            confidence=signal.confidence,
            strength=signal.strength,
            price=signal.price,
            timestamp=signal.timestamp,
        ),
        summary=DecisionTraceSummary(
            state=state,
            text=_trace_summary_text(signal, state),
            warnings=[gap.code for gap in gaps if gap.severity != "info"],
        ),
        llm_context=DecisionTraceLlmContext(status="not_available"),
        strategy_inputs=DecisionTraceStrategyInputs(
            setup_type=signal.setup_type,
            raw_reason=signal.reason,
        ),
        risk_orderability=DecisionTraceRiskOrderability(
            reject_stage=signal.reject_stage,
            reject_reason=signal.reject_reason,
            orderability_state=signal.orderability_state,
            orderability_details=signal.orderability_details or {},
        ),
        lineage=DecisionTraceLineage(
            signal_id=signal.id,
            order_id=signal.order_id,
            fill_id=signal.fill_id,
            position_id=signal.position_id,
            trade_id=signal.trade_id,
        ),
        lifecycle=_empty_lifecycle(),
        scorecard=_empty_scorecard(),
        evidence_gaps=gaps,
    )


def _find_signal_for_trace(signal_id: str, asset_class: str) -> SignalResponse | None:
    for target in target_assets(asset_class):
        for raw_signal in _load_signals(target):
            signal = _to_signal_response(raw_signal, target)
            if signal is not None and signal.id == signal_id:
                return signal
    return None
```

- [ ] **Step 5: Add the endpoint**

Insert after `get_signal_history`:

```python
@router.get("/{signal_id}/trace", response_model=DecisionTraceResponse)
async def get_signal_trace(
    signal_id: str,
    asset_class: str = Query(default="futures"),
) -> DecisionTraceResponse:
    """Return a read-only decision trace for a single signal."""
    asset = normalize_asset_class(asset_class)
    signal = _find_signal_for_trace(signal_id, asset)
    if signal is None:
        return DecisionTraceResponse(
            signal=DecisionTraceSignal(
                id=signal_id,
                asset_class=asset,
                symbol="",
                strategy="",
                side="",
            ),
            summary=DecisionTraceSummary(
                state="unknown",
                text=f"Signal {signal_id} was not found in current Redis signal state.",
                warnings=["signal_not_found"],
            ),
            llm_context=DecisionTraceLlmContext(status="unknown"),
            strategy_inputs=DecisionTraceStrategyInputs(),
            risk_orderability=DecisionTraceRiskOrderability(),
            lineage=DecisionTraceLineage(signal_id=signal_id),
            lifecycle=_empty_lifecycle(),
            scorecard=_empty_scorecard(),
            evidence_gaps=[
                _gap(
                    "signal_not_found",
                    "error",
                    "The selected signal is not present in current signal state.",
                )
            ],
        )
    return _basic_trace_from_signal(signal)
```

- [ ] **Step 6: Run the focused test**

Run:

```bash
pytest tests/unit/dashboard/test_signals_trace.py::test_signal_trace_returns_basic_signal_and_explicit_missing_gaps -q
```

Expected:

```text
1 passed
```

- [ ] **Step 7: Run existing signal route tests**

Run:

```bash
pytest tests/unit/dashboard/test_signals.py tests/unit/dashboard/test_signals_trace.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 8: Commit**

```bash
git add services/dashboard/routes/signals.py tests/unit/dashboard/test_signals_trace.py
git commit -m "feat: add signal decision trace endpoint"
```

---

### Task 2: RuntimeLedger LLM Context And Scorecard Enrichment

**Files:**
- Modify: `services/dashboard/routes/signals.py`
- Modify: `tests/unit/dashboard/test_signals_trace.py`

- [ ] **Step 1: Add failing tests for RuntimeLedger enrichment and no-look-ahead**

Append to `tests/unit/dashboard/test_signals_trace.py`:

```python
@pytest.mark.asyncio
async def test_signal_trace_enriches_llm_context_and_scorecard_from_ledger(tmp_path):
    from services.dashboard.routes import signals as signals_route
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    ledger = SQLiteRuntimeLedger(db_path)
    ledger.record_signal_decision(
        {
            "signal_id": "sig-ledger-1",
            "asset_class": "futures",
            "symbol": "101S6000",
            "strategy": "setup_a_gap_reversion",
            "decision": "generated",
            "created_at": "2026-06-27T00:19:00+00:00",
            "indicators": {"gap_pct": -0.42, "atr": 1.8},
            "thresholds": {"min_gap_pct": 0.3},
        }
    )
    ledger.record_market_context(
        {
            "asset_class": "futures",
            "context_type": "premarket",
            "created_at": "2026-06-27T00:10:00+00:00",
            "overall_signal": "BULLISH",
            "confidence": 0.71,
            "risk_mode": "risk_on",
            "regime": "trend",
            "risk_score": 0.22,
            "source": "llm_premarket_briefing",
        }
    )
    ledger.save_prediction(
        "2026-06-27",
        "direction",
        "2026-06-27T00:05:00+00:00",
        {"overall_signal": "BULLISH"},
        0.71,
    )
    ledger.save_score(
        {
            "date_kst": "2026-06-27",
            "facet": "direction",
            "correct": True,
            "value": 0.28,
            "economic_proxy": 0.18,
            "baseline_value": 0.10,
            "edge": 0.18,
            "detail": {"outcome": "up"},
            "scored_at": "2026-06-27T07:00:00+00:00",
        }
    )
    ledger.close()

    reader = _reader_with_signals(
        [
            {
                "id": "sig-ledger-1",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": False,
            }
        ]
    )

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(
            signals_route,
            "_get_trace_ledger",
            side_effect=lambda: SQLiteRuntimeLedger(db_path),
        ),
    ):
        response = await _get("/api/signals/sig-ledger-1/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_context"]["status"] == "ok"
    assert body["llm_context"]["overall_signal"] == "BULLISH"
    assert body["strategy_inputs"]["indicators"]["gap_pct"] == -0.42
    assert body["strategy_inputs"]["thresholds"]["min_gap_pct"] == 0.3
    assert body["scorecard"]["status"] == "ok"
    assert body["scorecard"]["facet"] == "direction"
    assert body["scorecard"]["edge"] == 0.18
    assert "llm_context_not_available" not in {gap["code"] for gap in body["evidence_gaps"]}
    assert "scorecard_missing" not in {gap["code"] for gap in body["evidence_gaps"]}


@pytest.mark.asyncio
async def test_signal_trace_scorecard_uses_no_future_trading_date(tmp_path):
    from services.dashboard.routes import signals as signals_route
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    ledger = SQLiteRuntimeLedger(db_path)
    ledger.save_prediction(
        "2026-06-28",
        "direction",
        "2026-06-28T00:05:00+00:00",
        {"overall_signal": "BULLISH"},
        0.90,
    )
    ledger.save_score(
        {
            "date_kst": "2026-06-28",
            "facet": "direction",
            "correct": True,
            "value": 1.0,
            "economic_proxy": 1.0,
            "baseline_value": 0.0,
            "edge": 1.0,
            "detail": {"outcome": "future"},
            "scored_at": "2026-06-28T07:00:00+00:00",
        }
    )
    ledger.close()

    reader = _reader_with_signals(
        [
            {
                "id": "sig-no-lookahead",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": False,
            }
        ]
    )

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(
            signals_route,
            "_get_trace_ledger",
            side_effect=lambda: SQLiteRuntimeLedger(db_path),
        ),
    ):
        response = await _get("/api/signals/sig-no-lookahead/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["scorecard"]["status"] == "missing"
    assert body["scorecard"]["date_kst"] is None
    assert "scorecard_missing" in {gap["code"] for gap in body["evidence_gaps"]}
```

- [ ] **Step 2: Run tests and confirm the expected failure**

Run:

```bash
pytest tests/unit/dashboard/test_signals_trace.py -q
```

Expected:

```text
2 failed, 1 passed
```

The new failures should show missing `_get_trace_ledger` or unenriched `llm_context`/`scorecard`.

- [ ] **Step 3: Add ledger helpers**

Add imports at the top of `services/dashboard/routes/signals.py`:

```python
import json
from zoneinfo import ZoneInfo
```

Add helpers before `_basic_trace_from_signal`:

```python
KST = ZoneInfo("Asia/Seoul")


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
    return None


def _date_kst(value: datetime | None) -> str | None:
    if value is None:
        return None
    ts = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return ts.astimezone(KST).date().isoformat()


def _json_payload(row: Any, key: str = "payload_json") -> dict[str, Any]:
    if row is None:
        return {}
    data = dict(row)
    raw = data.get(key)
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    payload = data.get("payload")
    return payload if isinstance(payload, dict) else {}


def _get_trace_ledger():
    from services.dashboard.routes.trades import _get_runtime_ledger

    return _get_runtime_ledger()


def _load_signal_decision_payload(ledger: Any, signal: SignalResponse) -> dict[str, Any]:
    try:
        row = (
            ledger._require_conn()  # noqa: SLF001
            .execute(
                "SELECT * FROM signal_decisions "
                "WHERE signal_id = ? AND asset_class = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (signal.id, signal.asset_class),
            )
            .fetchone()
        )
    except Exception:
        return {}
    return _json_payload(row)


def _llm_context_from_payload(payload: dict[str, Any]) -> DecisionTraceLlmContext | None:
    candidate = payload.get("llm_context") or payload.get("market_context")
    if not isinstance(candidate, dict):
        candidate = payload
    if not any(
        key in candidate
        for key in ("overall_signal", "risk_mode", "regime", "risk_score")
    ):
        return None
    return DecisionTraceLlmContext(
        status="ok",
        overall_signal=_as_optional_str(candidate.get("overall_signal")),
        confidence=(
            float(candidate["confidence"])
            if candidate.get("confidence") is not None
            else None
        ),
        risk_mode=_as_optional_str(candidate.get("risk_mode")),
        regime=_as_optional_str(candidate.get("regime")),
        risk_score=(
            float(candidate["risk_score"])
            if candidate.get("risk_score") is not None
            else None
        ),
        captured_at=_parse_dt(
            candidate.get("captured_at") or candidate.get("created_at")
        ),
        source=_as_optional_str(candidate.get("source")),
    )


def _load_market_context(ledger: Any, signal: SignalResponse, payload: dict[str, Any]) -> DecisionTraceLlmContext | None:
    from_payload = _llm_context_from_payload(payload)
    if from_payload is not None:
        return from_payload
    try:
        row = (
            ledger._require_conn()  # noqa: SLF001
            .execute(
                "SELECT * FROM market_context_history "
                "WHERE asset_class = ? AND created_at <= ? "
                "ORDER BY created_at DESC LIMIT 1",
                (signal.asset_class, signal.timestamp.isoformat()),
            )
            .fetchone()
        )
    except Exception:
        return None
    if row is None:
        return None
    context = _json_payload(row)
    context.setdefault("created_at", dict(row).get("created_at"))
    return _llm_context_from_payload(context)


def _scorecard_facet(signal: SignalResponse) -> str | None:
    if signal.asset_class == "futures" and signal.strategy in {
        "setup_a_gap_reversion",
        "setup_c_event_reaction",
        "setup_a",
        "setup_c",
    }:
        return "direction"
    return None


def _load_scorecard(ledger: Any, signal: SignalResponse) -> DecisionTraceScorecard:
    date_kst = _date_kst(signal.timestamp)
    facet = _scorecard_facet(signal)
    if date_kst is None or facet is None:
        return DecisionTraceScorecard(status="missing")
    predictions = ledger.query_predictions(facet=facet, start=date_kst, end=date_kst)
    scores = ledger.query_scores(facet=facet, start=date_kst, end=date_kst)
    prediction = predictions[-1] if predictions else None
    score = scores[-1] if scores else None
    if prediction is None and score is None:
        return DecisionTraceScorecard(status="missing")
    if score is None:
        return DecisionTraceScorecard(
            status="not_scored_yet",
            facet=facet,
            date_kst=date_kst,
            captured_at=_parse_dt(prediction.get("captured_at") if prediction else None),
            confidence=prediction.get("confidence") if prediction else None,
            detail=prediction.get("payload", {}) if prediction else {},
        )
    return DecisionTraceScorecard(
        status="ok",
        facet=facet,
        date_kst=date_kst,
        captured_at=_parse_dt(prediction.get("captured_at") if prediction else None),
        confidence=prediction.get("confidence") if prediction else None,
        correct=score.get("correct"),
        value=score.get("value"),
        economic_proxy=score.get("economic_proxy"),
        baseline_value=score.get("baseline_value"),
        edge=score.get("edge"),
        scored_at=_parse_dt(score.get("scored_at")),
        detail=score.get("detail", {}),
    )
```

- [ ] **Step 4: Replace `_basic_trace_from_signal` with enriched assembly**

Replace `_basic_trace_from_signal` with:

```python
def _trace_from_signal(signal: SignalResponse) -> DecisionTraceResponse:
    state = _trace_state(signal)
    gaps: list[EvidenceGap] = []
    signal_decision_payload: dict[str, Any] = {}
    llm_context = DecisionTraceLlmContext(status="not_available")
    scorecard = _empty_scorecard()
    ledger = _get_trace_ledger()
    if ledger is None:
        gaps.append(
            _gap(
                "runtime_ledger_not_available",
                "warning",
                "RuntimeLedger is unavailable; trace uses Redis signal fields only.",
            )
        )
    else:
        try:
            signal_decision_payload = _load_signal_decision_payload(ledger, signal)
            loaded_context = _load_market_context(ledger, signal, signal_decision_payload)
            if loaded_context is not None:
                llm_context = loaded_context
            scorecard = _load_scorecard(ledger, signal)
        finally:
            ledger.close()

    if llm_context.status != "ok":
        gaps.append(
            _gap(
                "llm_context_not_available",
                "warning",
                "No LLM market context is linked to this signal.",
            )
        )
    if scorecard.status == "missing":
        gaps.append(
            _gap(
                "scorecard_missing",
                "info",
                "No LLM scorecard prediction or score is linked to this signal.",
            )
        )
    elif scorecard.status == "not_scored_yet":
        gaps.append(
            _gap(
                "scorecard_not_scored_yet",
                "info",
                "A prediction exists, but the score has not been recorded yet.",
            )
        )

    lifecycle = _empty_lifecycle()
    gaps.append(
        _gap(
            "no_lifecycle_evidence",
            "info",
            "No order, fill, position, or closed-trade lifecycle evidence is available.",
        )
    )

    return DecisionTraceResponse(
        signal=DecisionTraceSignal(
            id=signal.id,
            asset_class=signal.asset_class,
            symbol=signal.symbol,
            strategy=signal.strategy,
            side=signal.side,
            signal_type=signal.signal_type,
            status=signal.status,
            reason=signal.reason,
            confidence=signal.confidence,
            strength=signal.strength,
            price=signal.price,
            timestamp=signal.timestamp,
        ),
        summary=DecisionTraceSummary(
            state=state,
            text=_trace_summary_text(signal, state),
            warnings=[gap.code for gap in gaps if gap.severity != "info"],
        ),
        llm_context=llm_context,
        strategy_inputs=DecisionTraceStrategyInputs(
            setup_type=signal.setup_type,
            indicators=signal_decision_payload.get("indicators", {})
            if isinstance(signal_decision_payload.get("indicators"), dict)
            else {},
            thresholds=signal_decision_payload.get("thresholds", {})
            if isinstance(signal_decision_payload.get("thresholds"), dict)
            else {},
            event_evidence=signal_decision_payload.get("event_evidence", {})
            if isinstance(signal_decision_payload.get("event_evidence"), dict)
            else {},
            raw_reason=signal.reason,
        ),
        risk_orderability=DecisionTraceRiskOrderability(
            reject_stage=signal.reject_stage,
            reject_reason=signal.reject_reason,
            orderability_state=signal.orderability_state,
            orderability_details=signal.orderability_details or {},
        ),
        lineage=DecisionTraceLineage(
            signal_id=signal.id,
            order_id=signal.order_id,
            fill_id=signal.fill_id,
            position_id=signal.position_id,
            trade_id=signal.trade_id,
        ),
        lifecycle=lifecycle,
        scorecard=scorecard,
        evidence_gaps=gaps,
    )
```

Then change the endpoint return:

```python
return _trace_from_signal(signal)
```

- [ ] **Step 5: Run the trace tests**

Run:

```bash
pytest tests/unit/dashboard/test_signals_trace.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Commit**

```bash
git add services/dashboard/routes/signals.py tests/unit/dashboard/test_signals_trace.py
git commit -m "feat: enrich signal trace with llm scorecard evidence"
```

---

### Task 3: Lifecycle Reuse And Partial Evidence States

**Files:**
- Modify: `services/dashboard/routes/signals.py`
- Modify: `tests/unit/dashboard/test_signals_trace.py`

- [ ] **Step 1: Add a failing lifecycle test**

Append:

```python
@pytest.mark.asyncio
async def test_signal_trace_embeds_lifecycle_and_removes_lifecycle_gap():
    from services.dashboard.routes import signals as signals_route

    reader = _reader_with_signals(
        [
            {
                "id": "sig-life-1",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": True,
                "trace": {"order_id": "ord-1", "fill_id": "fill-1"},
            }
        ]
    )
    lifecycle = signals_route.DecisionTraceLifecycle(
        status="partial",
        steps=[
            {
                "stage": "signal",
                "label": "Signal",
                "status": "generated",
                "id": "sig-life-1",
                "timestamp": "2026-06-27T00:20:00+00:00",
                "source": "runtime_ledger",
                "summary": "BUY 101S6000",
                "details": {"strategy": "setup_a_gap_reversion"},
            }
        ],
        warnings=["partial_legacy_lineage"],
    )

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(signals_route, "_get_trace_ledger", return_value=None),
        patch.object(signals_route, "_build_trace_lifecycle", return_value=lifecycle),
    ):
        response = await _get("/api/signals/sig-life-1/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["lifecycle"]["status"] == "partial"
    assert body["lifecycle"]["steps"][0]["stage"] == "signal"
    assert "partial_legacy_lineage" in body["summary"]["warnings"]
    assert "no_lifecycle_evidence" not in {gap["code"] for gap in body["evidence_gaps"]}
```

- [ ] **Step 2: Run the lifecycle test and confirm failure**

Run:

```bash
pytest tests/unit/dashboard/test_signals_trace.py::test_signal_trace_embeds_lifecycle_and_removes_lifecycle_gap -q
```

Expected:

```text
1 failed
```

The failure should mention missing `_build_trace_lifecycle`.

- [ ] **Step 3: Add lifecycle helper**

Insert before `_trace_from_signal`:

```python
def _lifecycle_status(warnings: list[str], steps: list[dict[str, Any]]) -> str:
    if not steps:
        return "missing"
    if "no_lifecycle_evidence" in warnings:
        return "missing"
    if warnings:
        return "partial"
    return "ok"


def _build_trace_lifecycle(signal: SignalResponse) -> DecisionTraceLifecycle:
    from services.dashboard.routes.trades import (
        _build_lifecycle_response,
        _load_lifecycle_ledger_rows,
        _load_lifecycle_redis_rows,
    )

    ledger_rows, ledger_available = _load_lifecycle_ledger_rows(
        signal.asset_class,
        symbol=signal.symbol or None,
        signal_id=signal.id or None,
        order_id=signal.order_id,
        fill_id=signal.fill_id,
        trade_id=signal.trade_id,
    )
    redis_rows = _load_lifecycle_redis_rows(
        signal.asset_class,
        symbol=signal.symbol or None,
    )
    response = _build_lifecycle_response(
        asset_class=signal.asset_class,
        signal_id=signal.id or None,
        order_id=signal.order_id,
        fill_id=signal.fill_id,
        trade_id=signal.trade_id,
        symbol=signal.symbol or None,
        ledger_rows=ledger_rows,
        redis_rows=redis_rows,
        ledger_available=ledger_available,
    )
    steps = [step.model_dump(mode="json") for step in response.steps]
    return DecisionTraceLifecycle(
        status=_lifecycle_status(response.warnings, steps),
        steps=steps,
        warnings=response.warnings,
    )
```

- [ ] **Step 4: Use lifecycle in trace assembly**

In `_trace_from_signal`, replace:

```python
lifecycle = _empty_lifecycle()
gaps.append(
    _gap(
        "no_lifecycle_evidence",
        "info",
        "No order, fill, position, or closed-trade lifecycle evidence is available.",
    )
)
```

with:

```python
lifecycle = _build_trace_lifecycle(signal)
if lifecycle.status == "missing":
    gaps.append(
        _gap(
            "no_lifecycle_evidence",
            "info",
            "No order, fill, position, or closed-trade lifecycle evidence is available.",
        )
    )
elif lifecycle.status == "partial":
    gaps.append(
        _gap(
            "partial_lifecycle",
            "warning",
            "Lifecycle evidence is present but one or more steps are missing.",
        )
    )
```

- [ ] **Step 5: Run backend trace tests**

Run:

```bash
pytest tests/unit/dashboard/test_signals_trace.py tests/unit/dashboard/test_trades.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 6: Commit**

```bash
git add services/dashboard/routes/signals.py tests/unit/dashboard/test_signals_trace.py
git commit -m "feat: attach lifecycle evidence to signal trace"
```

---

### Task 4: Frontend Types, Client, And Degraded Proxy Fallback

**Files:**
- Create: `strategy-builder-ui/src/lib/dashboard/decisionTrace.ts`
- Modify: `strategy-builder-ui/src/lib/dashboard/api.ts`
- Modify: `strategy-builder-ui/src/app/api/[...path]/route.ts`
- Modify: `strategy-builder-ui/src/app/api/catchall-route.test.ts`

- [ ] **Step 1: Add degraded proxy test**

Append to `strategy-builder-ui/src/app/api/catchall-route.test.ts`:

```ts
  it("returns explicit degraded signal trace payload when the dashboard is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/signals/sig-1/trace?asset_class=futures"),
      contextFor(["signals", "sig-1", "trace"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(response.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
    expect(body.signal.id).toBe("sig-1");
    expect(body.summary.state).toBe("unknown");
    expect(body.llm_context.status).toBe("unknown");
    expect(body.lifecycle.status).toBe("not_available");
    expect(body.evidence_gaps[0].code).toBe("dashboard_api_unavailable");
  });
```

- [ ] **Step 2: Run proxy test and confirm failure**

Run:

```bash
npm --prefix strategy-builder-ui test -- src/app/api/catchall-route.test.ts
```

Expected:

```text
1 failed
```

The new test should fail because the catch-all route does not yet return a degraded trace payload.

- [ ] **Step 3: Create `decisionTrace.ts`**

Create `strategy-builder-ui/src/lib/dashboard/decisionTrace.ts`:

```ts
import { apiClient } from './client';
import type { TradeLifecycleStep } from './trades';

export interface DecisionTraceEvidenceGap {
  code: string;
  severity: 'info' | 'warning' | 'error' | string;
  message: string;
}

export interface DecisionTraceSignal {
  id: string;
  asset_class: string;
  symbol: string;
  strategy: string;
  side: string;
  signal_type?: string | null;
  status?: string | null;
  reason?: string | null;
  confidence?: number | null;
  strength?: number | null;
  price?: number | null;
  timestamp?: string | null;
}

export interface DecisionTraceSummary {
  state: string;
  text: string;
  warnings: string[];
}

export interface DecisionTraceLlmContext {
  status: string;
  overall_signal?: string | null;
  confidence?: number | null;
  risk_mode?: string | null;
  regime?: string | null;
  risk_score?: number | null;
  captured_at?: string | null;
  source?: string | null;
}

export interface DecisionTraceStrategyInputs {
  setup_type?: string | null;
  indicators: Record<string, unknown>;
  thresholds: Record<string, unknown>;
  event_evidence: Record<string, unknown>;
  raw_reason?: string | null;
}

export interface DecisionTraceRiskOrderability {
  reject_stage?: string | null;
  reject_reason?: string | null;
  orderability_state?: string | null;
  orderability_details: Record<string, unknown>;
  risk_state?: string | null;
  risk_details: Record<string, unknown>;
}

export interface DecisionTraceLineage {
  signal_id?: string | null;
  order_id?: string | null;
  fill_id?: string | null;
  position_id?: string | null;
  trade_id?: string | null;
}

export interface DecisionTraceLifecycle {
  status: string;
  steps: TradeLifecycleStep[];
  warnings: string[];
}

export interface DecisionTraceScorecard {
  status: string;
  facet?: string | null;
  date_kst?: string | null;
  captured_at?: string | null;
  confidence?: number | null;
  correct?: boolean | null;
  value?: number | null;
  economic_proxy?: number | null;
  baseline_value?: number | null;
  edge?: number | null;
  scored_at?: string | null;
  detail: Record<string, unknown>;
}

export interface DecisionTraceResponse {
  signal: DecisionTraceSignal;
  summary: DecisionTraceSummary;
  llm_context: DecisionTraceLlmContext;
  strategy_inputs: DecisionTraceStrategyInputs;
  risk_orderability: DecisionTraceRiskOrderability;
  lineage: DecisionTraceLineage;
  lifecycle: DecisionTraceLifecycle;
  scorecard: DecisionTraceScorecard;
  evidence_gaps: DecisionTraceEvidenceGap[];
}

export const decisionTraceApi = {
  getDecisionTrace: (signalId: string, params?: { asset_class?: string }) =>
    apiClient.get<DecisionTraceResponse>(
      `/api/signals/${encodeURIComponent(signalId)}/trace`,
      { params },
    ),
};
```

- [ ] **Step 4: Re-export the client**

Add to `strategy-builder-ui/src/lib/dashboard/api.ts`:

```ts
export { decisionTraceApi } from './decisionTrace';
```

- [ ] **Step 5: Add degraded trace helper**

In `strategy-builder-ui/src/app/api/[...path]/route.ts`, add this function after `degradedLifecycle`:

```ts
function degradedSignalTrace(asset: "stock" | "futures" | "all", targetPath: string, signalId: string) {
  return {
    signal: {
      id: signalId,
      asset_class: asset,
      symbol: "",
      strategy: "",
      side: "",
      signal_type: null,
      status: null,
      reason: null,
      confidence: null,
      strength: null,
      price: null,
      timestamp: null,
    },
    summary: {
      state: "unknown",
      text: unavailableNote(targetPath),
      warnings: ["dashboard_api_unavailable"],
    },
    llm_context: { status: "unknown" },
    strategy_inputs: {
      setup_type: null,
      indicators: {},
      thresholds: {},
      event_evidence: {},
      raw_reason: null,
    },
    risk_orderability: {
      reject_stage: null,
      reject_reason: null,
      orderability_state: null,
      orderability_details: {},
      risk_state: null,
      risk_details: {},
    },
    lineage: {
      signal_id: signalId,
      order_id: null,
      fill_id: null,
      position_id: null,
      trade_id: null,
    },
    lifecycle: {
      status: "not_available",
      steps: [],
      warnings: ["dashboard_api_unavailable"],
    },
    scorecard: {
      status: "unknown",
      facet: null,
      date_kst: null,
      captured_at: null,
      confidence: null,
      correct: null,
      value: null,
      economic_proxy: null,
      baseline_value: null,
      edge: null,
      scored_at: null,
      detail: {},
    },
    evidence_gaps: [
      {
        code: "dashboard_api_unavailable",
        severity: "warning",
        message: unavailableNote(targetPath),
      },
    ],
  };
}
```

In the degraded routing block, insert before the `signals/history` branch:

```ts
  if (root === "signals" && second && third === "trace") {
    return degradedJson(degradedSignalTrace(asset, targetPath, second));
  }
```

- [ ] **Step 6: Run proxy tests**

Run:

```bash
npm --prefix strategy-builder-ui test -- src/app/api/catchall-route.test.ts
```

Expected:

```text
PASS src/app/api/catchall-route.test.ts
```

- [ ] **Step 7: Commit**

```bash
git add strategy-builder-ui/src/lib/dashboard/decisionTrace.ts strategy-builder-ui/src/lib/dashboard/api.ts 'strategy-builder-ui/src/app/api/[...path]/route.ts' strategy-builder-ui/src/app/api/catchall-route.test.ts
git commit -m "feat: add frontend decision trace client"
```

---

### Task 5: DecisionTracePanel Component

**Files:**
- Create: `strategy-builder-ui/src/app/signals/components/DecisionTracePanel.tsx`
- Create: `strategy-builder-ui/src/app/signals/components/DecisionTracePanel.test.tsx`

- [ ] **Step 1: Write component tests**

Create `strategy-builder-ui/src/app/signals/components/DecisionTracePanel.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import DecisionTracePanel from "./DecisionTracePanel";
import type { DecisionTraceResponse } from "@/lib/dashboard/decisionTrace";

const baseTrace: DecisionTraceResponse = {
  signal: {
    id: "sig-1",
    asset_class: "futures",
    symbol: "101S6000",
    strategy: "setup_a_gap_reversion",
    side: "BUY",
    signal_type: "entry",
    status: "generated",
    reason: "gap_reversion_candidate",
    confidence: 0.72,
    strength: 0.72,
    price: 390.25,
    timestamp: "2026-06-27T00:20:00+00:00",
  },
  summary: {
    state: "orderable",
    text: "setup_a_gap_reversion generated BUY 101S6000.",
    warnings: [],
  },
  llm_context: {
    status: "ok",
    overall_signal: "BULLISH",
    confidence: 0.71,
    risk_mode: "risk_on",
    regime: "trend",
    risk_score: 0.22,
    captured_at: "2026-06-27T00:10:00+00:00",
    source: "llm_premarket_briefing",
  },
  strategy_inputs: {
    setup_type: "setup_a",
    indicators: { gap_pct: -0.42, atr: 1.8 },
    thresholds: { min_gap_pct: 0.3 },
    event_evidence: {},
    raw_reason: "gap_reversion_candidate",
  },
  risk_orderability: {
    reject_stage: null,
    reject_reason: null,
    orderability_state: "paper_orderable",
    orderability_details: { state: "paper_orderable" },
    risk_state: null,
    risk_details: {},
  },
  lineage: {
    signal_id: "sig-1",
    order_id: "ord-1",
    fill_id: "fill-1",
    position_id: null,
    trade_id: null,
  },
  lifecycle: {
    status: "partial",
    steps: [
      {
        stage: "signal",
        label: "Signal",
        status: "generated",
        id: "sig-1",
        timestamp: "2026-06-27T00:20:00+00:00",
        source: "runtime_ledger",
        summary: "BUY 101S6000",
        details: { strategy: "setup_a_gap_reversion" },
      },
    ],
    warnings: ["partial_legacy_lineage"],
  },
  scorecard: {
    status: "ok",
    facet: "direction",
    date_kst: "2026-06-27",
    captured_at: "2026-06-27T00:05:00+00:00",
    confidence: 0.71,
    correct: true,
    value: 0.28,
    economic_proxy: 0.18,
    baseline_value: 0.10,
    edge: 0.18,
    scored_at: "2026-06-27T07:00:00+00:00",
    detail: { outcome: "up" },
  },
  evidence_gaps: [],
};

describe("DecisionTracePanel", () => {
  it("renders full decision trace evidence", () => {
    render(<DecisionTracePanel trace={baseTrace} onClose={vi.fn()} onRefresh={vi.fn()} />);

    expect(screen.getByRole("region", { name: "Decision Trace" })).toBeInTheDocument();
    expect(screen.getByText("101S6000")).toBeInTheDocument();
    expect(screen.getByText("BULLISH")).toBeInTheDocument();
    expect(screen.getByText("paper_orderable")).toBeInTheDocument();
    expect(screen.getByText("direction")).toBeInTheDocument();
    expect(screen.getByText("+0.18")).toBeInTheDocument();
    expect(screen.getByText("BUY 101S6000")).toBeInTheDocument();
  });

  it("renders missing LLM context and unscorable score without implying failure", () => {
    render(
      <DecisionTracePanel
        trace={{
          ...baseTrace,
          llm_context: { status: "not_available" },
          scorecard: {
            ...baseTrace.scorecard,
            status: "ok",
            correct: null,
            detail: { reason: "market_data_gap" },
          },
          evidence_gaps: [
            {
              code: "llm_context_not_available",
              severity: "warning",
              message: "No LLM market context is linked to this signal.",
            },
          ],
        }}
        onClose={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText("not_available")).toBeInTheDocument();
    expect(screen.getByText("unscorable")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("No LLM market context");
  });

  it("exposes close and refresh controls", async () => {
    const onClose = vi.fn();
    const onRefresh = vi.fn();

    render(<DecisionTracePanel trace={baseTrace} onClose={onClose} onRefresh={onRefresh} />);

    await userEvent.click(screen.getByRole("button", { name: "Close decision trace" }));
    await userEvent.click(screen.getByRole("button", { name: "Refresh decision trace" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run component tests and confirm failure**

Run:

```bash
npm --prefix strategy-builder-ui test -- src/app/signals/components/DecisionTracePanel.test.tsx
```

Expected:

```text
1 failed
```

The failure should show missing `DecisionTracePanel`.

- [ ] **Step 3: Create `DecisionTracePanel.tsx`**

Create `strategy-builder-ui/src/app/signals/components/DecisionTracePanel.tsx`:

```tsx
"use client";

import type { ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  RefreshCw,
  X,
} from "lucide-react";

import SideBadge from "@/components/dashboard/SideBadge";
import type {
  DecisionTraceEvidenceGap,
  DecisionTraceResponse,
} from "@/lib/dashboard/decisionTrace";

interface DecisionTracePanelProps {
  trace?: DecisionTraceResponse;
  isLoading?: boolean;
  error?: string | null;
  onClose: () => void;
  onRefresh: () => void;
}

function displayValue(value: unknown, fallback = "not available"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : fallback;
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function displaySigned(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "unknown";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

function displayPercent(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "unknown";
  return `${(value * 100).toFixed(0)}%`;
}

function formatTime(value?: string | null): string {
  if (!value) return "not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-3">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Field({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm font-medium text-slate-900">
        {displayValue(value)}
      </div>
    </div>
  );
}

function GapAlert({ gap }: { gap: DecisionTraceEvidenceGap }) {
  const tone =
    gap.severity === "error"
      ? "border-red-200 bg-red-50 text-red-700"
      : gap.severity === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-slate-200 bg-slate-50 text-slate-600";
  return (
    <div role="alert" className={`rounded border px-3 py-2 text-xs ${tone}`}>
      <div className="font-semibold">{gap.code}</div>
      <div className="mt-1 break-words">{gap.message}</div>
    </div>
  );
}

function scoreResult(correct?: boolean | null): string {
  if (correct === null || correct === undefined) {
    return "unscorable";
  }
  return correct ? "correct" : "missed";
}

export default function DecisionTracePanel({
  trace,
  isLoading,
  error,
  onClose,
  onRefresh,
}: DecisionTracePanelProps) {
  return (
    <section
      role="region"
      aria-label="Decision Trace"
      className="rounded-lg border border-slate-200 bg-slate-50 p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">Decision Trace</div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className="break-words text-lg font-bold text-slate-950">
              {trace?.signal.symbol || trace?.signal.id || "No signal selected"}
            </span>
            {trace ? <SideBadge side={trace.signal.side} /> : null}
            {trace ? (
              <span className="rounded bg-white px-2 py-0.5 text-xs font-medium text-slate-600">
                {trace.summary.state}
              </span>
            ) : null}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onRefresh}
            aria-label="Refresh decision trace"
            title="Refresh decision trace"
            className="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 bg-white text-slate-500 hover:bg-slate-100"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close decision trace"
            title="Close decision trace"
            className="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 bg-white text-slate-500 hover:bg-slate-100"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div role="status" className="mt-4 text-sm text-slate-500">
          Loading decision trace
        </div>
      ) : error ? (
        <div role="alert" className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : trace ? (
        <div className="mt-4 space-y-3">
          <div className="rounded border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
            {trace.summary.text}
          </div>

          <Section title="LLM Context">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Status" value={trace.llm_context.status} />
              <Field label="Signal" value={trace.llm_context.overall_signal} />
              <Field label="Confidence" value={displayPercent(trace.llm_context.confidence)} />
              <Field label="Risk Mode" value={trace.llm_context.risk_mode} />
              <Field label="Regime" value={trace.llm_context.regime} />
              <Field label="Captured" value={formatTime(trace.llm_context.captured_at)} />
            </div>
          </Section>

          <Section title="Strategy Inputs">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Setup" value={trace.strategy_inputs.setup_type} />
              <Field label="Reason" value={trace.strategy_inputs.raw_reason} />
              <Field label="Indicators" value={trace.strategy_inputs.indicators} />
              <Field label="Thresholds" value={trace.strategy_inputs.thresholds} />
            </div>
          </Section>

          <Section title="Risk And Orderability">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Orderability" value={trace.risk_orderability.orderability_state} />
              <Field label="Reject Stage" value={trace.risk_orderability.reject_stage} />
              <Field label="Reject Reason" value={trace.risk_orderability.reject_reason} />
              <Field label="Details" value={trace.risk_orderability.orderability_details} />
            </div>
          </Section>

          <Section title="Lifecycle">
            <div className="space-y-2">
              <Field label="Status" value={trace.lifecycle.status} />
              {trace.lifecycle.steps.map((step) => (
                <div key={step.stage} className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                  <div className="flex items-center gap-2 font-medium text-slate-900">
                    {step.status === "unknown" ? (
                      <CircleHelp className="h-4 w-4 text-amber-600" aria-hidden="true" />
                    ) : step.status === "rejected" || step.status === "blocked" ? (
                      <AlertTriangle className="h-4 w-4 text-red-600" aria-hidden="true" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                    )}
                    <span>{step.label}</span>
                    <span className="rounded bg-white px-2 py-0.5 text-[11px] uppercase text-slate-500">
                      {step.status}
                    </span>
                  </div>
                  <div className="mt-1 break-words text-xs text-slate-600">
                    {step.summary || step.id || "not available"}
                  </div>
                </div>
              ))}
            </div>
          </Section>

          <Section title="Scorecard Evidence">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Status" value={trace.scorecard.status} />
              <Field label="Facet" value={trace.scorecard.facet} />
              <Field label="Date KST" value={trace.scorecard.date_kst} />
              <Field label="Result" value={scoreResult(trace.scorecard.correct)} />
              <Field label="Edge" value={displaySigned(trace.scorecard.edge)} />
              <Field label="Scored" value={formatTime(trace.scorecard.scored_at)} />
            </div>
          </Section>

          {trace.evidence_gaps.length > 0 ? (
            <Section title="Evidence Gaps">
              <div className="space-y-2">
                {trace.evidence_gaps.map((gap) => (
                  <GapAlert key={gap.code} gap={gap} />
                ))}
              </div>
            </Section>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 text-sm text-slate-500">Select a signal to inspect decision evidence.</div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Check the component snippet has no React namespace dependency**

Run:

```bash
rg -n "React\\.ReactNode|<ScoreState" strategy-builder-ui/src/app/signals/components/DecisionTracePanel.tsx
```

Expected:

```text
no matches
```

- [ ] **Step 5: Run component test**

Run:

```bash
npm --prefix strategy-builder-ui test -- src/app/signals/components/DecisionTracePanel.test.tsx
```

Expected:

```text
PASS src/app/signals/components/DecisionTracePanel.test.tsx
```

- [ ] **Step 6: Commit**

```bash
git add strategy-builder-ui/src/app/signals/components/DecisionTracePanel.tsx strategy-builder-ui/src/app/signals/components/DecisionTracePanel.test.tsx
git commit -m "feat: add signal decision trace panel"
```

---

### Task 6: Wire `/signals` Page To Fetch Decision Trace

**Files:**
- Modify: `strategy-builder-ui/src/app/signals/page.tsx`
- Modify: `strategy-builder-ui/src/app/quant-ops-workbench.smoke.test.tsx`

- [ ] **Step 1: Add `/signals` smoke test**

Modify `strategy-builder-ui/src/app/quant-ops-workbench.smoke.test.tsx` imports:

```tsx
import SignalsPage from "./signals/page";
import {
  coverageApi,
  decisionTraceApi,
  signalsApi,
  tradesApi,
  tradingApi,
} from "@/lib/dashboard/api";
```

Modify the `vi.mock("@/lib/dashboard/api", ...)` return value:

```tsx
    decisionTraceApi: { getDecisionTrace: vi.fn() },
    signalsApi: { getSignals: vi.fn(), getHistory: vi.fn() },
```

Append this test inside the `describe` block:

```tsx
  it("renders /signals decision trace after selecting a signal", async () => {
    vi.mocked(signalsApi.getSignals).mockResolvedValue(
      axiosResponse({
        total: 1,
        page: 1,
        limit: 50,
        signals: [
          {
            id: "sig-1",
            asset_class: "stock",
            strategy: "setup_a_gap_reversion",
            symbol: "101S6000",
            side: "BUY",
            signal_type: "entry",
            confidence: 0.72,
            strength: 0.72,
            price: 390.25,
            timestamp: "2026-06-27T00:20:00+00:00",
            executed: false,
          },
        ],
      }),
    );
    vi.mocked(decisionTraceApi.getDecisionTrace).mockResolvedValue(
      axiosResponse({
        signal: {
          id: "sig-1",
          asset_class: "stock",
          symbol: "101S6000",
          strategy: "setup_a_gap_reversion",
          side: "BUY",
          signal_type: "entry",
          status: "generated",
          reason: "gap_reversion_candidate",
          confidence: 0.72,
          strength: 0.72,
          price: 390.25,
          timestamp: "2026-06-27T00:20:00+00:00",
        },
        summary: {
          state: "orderable",
          text: "setup_a_gap_reversion generated BUY 101S6000.",
          warnings: [],
        },
        llm_context: {
          status: "ok",
          overall_signal: "BULLISH",
          confidence: 0.71,
          risk_mode: "risk_on",
          regime: "trend",
          risk_score: 0.22,
          captured_at: "2026-06-27T00:10:00+00:00",
          source: "llm_premarket_briefing",
        },
        strategy_inputs: {
          setup_type: "setup_a",
          indicators: { gap_pct: -0.42 },
          thresholds: { min_gap_pct: 0.3 },
          event_evidence: {},
          raw_reason: "gap_reversion_candidate",
        },
        risk_orderability: {
          reject_stage: null,
          reject_reason: null,
          orderability_state: "paper_orderable",
          orderability_details: {},
          risk_state: null,
          risk_details: {},
        },
        lineage: {
          signal_id: "sig-1",
          order_id: null,
          fill_id: null,
          position_id: null,
          trade_id: null,
        },
        lifecycle: {
          status: "missing",
          steps: [],
          warnings: ["no_lifecycle_evidence"],
        },
        scorecard: {
          status: "missing",
          facet: null,
          date_kst: null,
          captured_at: null,
          confidence: null,
          correct: null,
          value: null,
          economic_proxy: null,
          baseline_value: null,
          edge: null,
          scored_at: null,
          detail: {},
        },
        evidence_gaps: [],
      }),
    );

    renderWithQueryClient(<SignalsPage />);

    expect(await screen.findByRole("heading", { name: "Trading Signals" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "View trace for 101S6000" }));

    expect(await screen.findByRole("region", { name: "Decision Trace" })).toBeInTheDocument();
    expect(screen.getByText("BULLISH")).toBeInTheDocument();
    expect(decisionTraceApi.getDecisionTrace).toHaveBeenCalledWith("sig-1", {
      asset_class: "stock",
    });
  });
```

- [ ] **Step 2: Run smoke test and confirm failure**

Run:

```bash
npm --prefix strategy-builder-ui test -- src/app/quant-ops-workbench.smoke.test.tsx
```

Expected:

```text
1 failed
```

The failure should show that `/signals` still uses the old inline trace card or lacks `decisionTraceApi`.

- [ ] **Step 3: Wire API and component in `signals/page.tsx`**

Change imports:

```tsx
import { useQuery } from '@tanstack/react-query';
import { decisionTraceApi, signalsApi } from '@/lib/dashboard/api';
import DecisionTracePanel from './components/DecisionTracePanel';
```

Remove `displayValue`, `formatTraceDetails`, `TraceItem`, and `SignalTraceCard` from `page.tsx`; the panel owns trace rendering.

Add after the existing signal list query:

```tsx
  const {
    data: traceData,
    isLoading: traceLoading,
    error: traceError,
    refetch: refetchTrace,
  } = useQuery({
    queryKey: ['signal-decision-trace', selectedAsset, selectedSignal?.id],
    queryFn: () =>
      decisionTraceApi
        .getDecisionTrace(selectedSignal?.id || '', { asset_class: selectedAsset })
        .then((r) => r.data),
    enabled: Boolean(selectedSignal?.id),
    refetchInterval: false,
  });

  const traceErrorMessage =
    traceError instanceof Error ? traceError.message : traceError ? 'Failed to load decision trace' : null;
```

Replace the selected signal block:

```tsx
          {selectedSignal ? (
            <DecisionTracePanel
              trace={traceData}
              isLoading={traceLoading}
              error={traceErrorMessage}
              onClose={() => setSelectedSignal(null)}
              onRefresh={() => refetchTrace()}
            />
          ) : null}
```

Change mobile trace button:

```tsx
                    <button
                      type="button"
                      onClick={() => setSelectedSignal(signal)}
                      aria-label={`View trace for ${signal.symbol}`}
                      className="mt-4 w-full rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
                    >
                      View trace
                    </button>
```

For desktop rows, keep `role="button"` and add:

```tsx
                          aria-label={`View trace for ${signal.symbol}`}
                          aria-pressed={selectedSignal?.id === signal.id}
```

- [ ] **Step 4: Run focused frontend tests**

Run:

```bash
npm --prefix strategy-builder-ui test -- src/app/signals/components/DecisionTracePanel.test.tsx src/app/quant-ops-workbench.smoke.test.tsx
```

Expected:

```text
PASS src/app/signals/components/DecisionTracePanel.test.tsx
PASS src/app/quant-ops-workbench.smoke.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add strategy-builder-ui/src/app/signals/page.tsx strategy-builder-ui/src/app/quant-ops-workbench.smoke.test.tsx
git commit -m "feat: wire signals page decision trace"
```

---

### Task 7: Full Verification And Visual QA

**Files:**
- Modify: `docs/testing/quant-ops-workbench-2026-06-27.md`
- Create directory when screenshots are captured: `docs/testing/quant-ops-workbench-2026-06-27/`

- [ ] **Step 1: Run backend route tests**

Run:

```bash
pytest tests/unit/dashboard/test_signals.py tests/unit/dashboard/test_signals_trace.py tests/unit/dashboard/test_trades.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 2: Run frontend focused tests**

Run:

```bash
npm --prefix strategy-builder-ui test -- src/app/api/catchall-route.test.ts src/app/signals/components/DecisionTracePanel.test.tsx src/app/quant-ops-workbench.smoke.test.tsx
```

Expected:

```text
all tests passed
```

- [ ] **Step 3: Run lint and build**

Run:

```bash
npm --prefix strategy-builder-ui run lint
npm --prefix strategy-builder-ui run build
```

Expected:

```text
lint exits 0
build exits 0
```

Known repository context: the Next.js build may warn about multiple lockfiles and still succeed. Do not mark warnings as failures unless the command exits nonzero.

- [ ] **Step 4: Start the frontend dev server if no server is running**

Run:

```bash
npm --prefix strategy-builder-ui run dev
```

Expected:

```text
Local: http://localhost:3100
```

If port `3100` is already in use by this app, reuse it. If the port is occupied by another process, start on another available port and record the URL in the QA note.

- [ ] **Step 5: Capture desktop and mobile `/signals` QA evidence**

Use the in-session Browser tool when available. If it is not exposed, use local Playwright. The evidence must verify:

- `/signals` renders without console errors.
- Selecting a signal opens `Decision Trace`.
- LLM context, strategy inputs, lifecycle, scorecard, and evidence gaps are visible when present.
- Missing states render as explicit text.
- Desktop has no horizontal overflow at 1440x900.
- Mobile has no horizontal overflow at 390x844.
- Keyboard `Tab` can reach the selected row/card, close button, and refresh button.

Save screenshots:

```text
docs/testing/quant-ops-workbench-2026-06-27/signals-decision-trace-desktop.png
docs/testing/quant-ops-workbench-2026-06-27/signals-decision-trace-mobile.png
```

- [ ] **Step 6: Write QA evidence note**

Create `docs/testing/quant-ops-workbench-2026-06-27.md`:

```markdown
# Quant Ops Workbench QA - 2026-06-27

## Scope

- `/signals` decision trace panel after selecting a signal.
- Desktop viewport: 1440x900.
- Mobile viewport: 390x844.

## Commands

- `pytest tests/unit/dashboard/test_signals.py tests/unit/dashboard/test_signals_trace.py tests/unit/dashboard/test_trades.py -q`
- `npm --prefix strategy-builder-ui test -- src/app/api/catchall-route.test.ts src/app/signals/components/DecisionTracePanel.test.tsx src/app/quant-ops-workbench.smoke.test.tsx`
- `npm --prefix strategy-builder-ui run lint`
- `npm --prefix strategy-builder-ui run build`

## Render Evidence

- Desktop: `docs/testing/quant-ops-workbench-2026-06-27/signals-decision-trace-desktop.png`
- Mobile: `docs/testing/quant-ops-workbench-2026-06-27/signals-decision-trace-mobile.png`

## Findings

- Decision Trace opens from selected signal rows/cards.
- LLM context, strategy inputs, risk/orderability, lifecycle, scorecard, and evidence gaps render as read-only evidence.
- Missing sources render explicit degraded states.
- No console errors observed during the checked flows.
- No horizontal overflow observed in the checked desktop/mobile viewports.
```

- [ ] **Step 7: Run final diff check**

Run:

```bash
git diff --check
git status --short
```

Expected:

```text
git diff --check exits 0
git status --short shows only intended files before commit
```

- [ ] **Step 8: Commit QA evidence**

```bash
git add docs/testing/quant-ops-workbench-2026-06-27.md docs/testing/quant-ops-workbench-2026-06-27
git commit -m "test: capture signals decision trace qa evidence"
```

---

## Final Verification Bundle

Run before declaring implementation complete:

```bash
pytest tests/unit/dashboard/test_signals.py tests/unit/dashboard/test_signals_trace.py tests/unit/dashboard/test_trades.py -q
npm --prefix strategy-builder-ui test -- src/app/api/catchall-route.test.ts src/app/signals/components/DecisionTracePanel.test.tsx src/app/quant-ops-workbench.smoke.test.tsx
npm --prefix strategy-builder-ui run lint
npm --prefix strategy-builder-ui run build
git diff --check
```

Expected result:

```text
all commands exit 0
```

## Spec Coverage Check

- LLM context visibility: Task 2 backend enrichment and Task 5 panel.
- Strategy inputs and event evidence: Task 2 payload extraction and Task 5 panel.
- Risk/orderability: Task 1 response contract and Task 5 panel.
- Signal -> order -> fill -> position -> trade lifecycle: Task 3 helper reuse and Task 5 lifecycle block.
- Scorecard evidence and no-look-ahead: Task 2 tests and helper logic.
- Evidence gaps: Task 1, Task 2, Task 3, Task 5.
- Responsive `/signals` integration: Task 6 and Task 7.
- Read-only safety: all tasks only add GET/read/render behavior.
