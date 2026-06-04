# API Documentation

> **API 통합 (2026-06):** 과거의 별도 REST 게이트웨이 `services/api`(:8000,
> `/api/v1/*`, `/health/live`, `/health/ready`)는 **`services/dashboard` FastAPI
> 로 통합·제거**됐다. 단일 API는 Caddy(:5080) 뒤의 dashboard(:8001)이며 라우트는
> `/api/{trading,signals,trades,strategies,strategy-lab,strategy-builder,metrics,
> health}*`, `/health`, `/metrics`, `/ws` 이다. 아래 일부 `/api/v1/*`·`/health/live`
> 예시는 구 게이트웨이 기준의 historical 문서다.

## Base URL

- Dashboard API: `http://localhost:5080`

## Authentication

모든 API 요청에는 API 키가 필요합니다:

```
X-API-Key: your_api_key_here
```

## Endpoints

### Health

#### GET /health/live

서버 생존 확인 (Liveness Probe)

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-01-22T10:00:00Z"
}
```

#### GET /health/ready

서버 준비 상태 확인 (Readiness Probe)

**Response:**
```json
{
  "status": "ready",
  "components": {
    "redis": "healthy",
    "database": "healthy"
  }
}
```

---

### Trading

#### GET /api/v1/trading/status

현재 거래 상태 조회

**Response:**
```json
{
  "is_running": true,
  "market_status": "open",
  "active_strategies": ["bb_reversion"],
  "total_positions": 3,
  "total_pnl": 150000.0
}
```

#### POST /api/v1/trading/start

거래 시작

**Request Body:**
```json
{
  "strategies": ["bb_reversion"],
  "mode": "paper"
}
```

**Response:**
```json
{
  "status": "started",
  "message": "Trading started successfully"
}
```

#### POST /api/v1/trading/stop

거래 중지

**Response:**
```json
{
  "status": "stopped",
  "message": "Trading stopped"
}
```

---

### Positions

#### GET /api/v1/positions

현재 포지션 목록 조회

**Response:**
```json
{
  "positions": [
    {
      "symbol": "005930",
      "side": "LONG",
      "quantity": 100,
      "entry_price": 58000,
      "current_price": 59500,
      "unrealized_pnl": 150000,
      "pnl_pct": 2.59
    }
  ]
}
```

#### GET /api/v1/positions/{symbol}

특정 심볼 포지션 조회

---

### Strategies

#### GET /api/v1/strategies

등록된 전략 목록 조회

**Response:**
```json
{
  "strategies": [
    {
      "name": "bb_reversion",
      "asset_class": "stock",
      "enabled": true,
      "entry_type": "bb_lower_reentry",
      "exit_type": "three_stage"
    },
    {
      "name": "ofi_momentum",
      "asset_class": "futures",
      "enabled": true,
      "entry_type": "ofi_imbalance",
      "exit_type": "scalping"
    }
  ]
}
```

#### GET /api/v1/strategies/{name}

특정 전략 상세 정보

**Response:**
```json
{
  "name": "bb_reversion",
  "asset_class": "stock",
  "enabled": true,
  "config": {
    "entry": {
      "type": "bb_lower_reentry",
      "params": {
        "bb_period": 20,
        "bb_std": 2.0,
        "rsi_oversold": 30
      }
    },
    "exit": {
      "type": "three_stage",
      "params": {
        "hard_stop_pct": 1.5,
        "breakeven_threshold_pct": 1.5
      }
    }
  }
}
```

---

### Backtest

#### POST /api/v1/backtest/run

백테스트 실행

**Request:**
```json
{
  "strategy": "bb_reversion",
  "asset_class": "stock",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "initial_capital": 100000000
}
```

**Response:**
```json
{
  "run_id": "abc123def456",
  "status": "running",
  "message": "Backtest started"
}
```

#### GET /api/v1/backtest/results/{run_id}

백테스트 결과 조회

**Response:**
```json
{
  "run_id": "abc123def456",
  "status": "completed",
  "metrics": {
    "total_return": 15.5,
    "sharpe_ratio": 1.85,
    "max_drawdown": 8.2,
    "win_rate": 62.5,
    "total_trades": 156
  },
  "mlflow_uri": "http://localhost:5000/#/experiments/1/runs/abc123"
}
```

#### GET /api/v1/backtest/runs

백테스트 실행 목록

---

### Metrics

#### GET /metrics

Prometheus 형식 메트릭

```
# HELP trading_signals_total Total trading signals generated
# TYPE trading_signals_total counter
trading_signals_total{strategy="bb_reversion",signal_type="entry"} 150
trading_signals_total{strategy="bb_reversion",signal_type="exit"} 145

# HELP trading_positions_active Current active positions
# TYPE trading_positions_active gauge
trading_positions_active{strategy="bb_reversion"} 3

# HELP trading_pnl_total Total realized P&L
# TYPE trading_pnl_total gauge
trading_pnl_total{strategy="bb_reversion"} 1500000
```

---

## WebSocket API

### Dashboard WebSocket

실시간 데이터 스트리밍을 위한 WebSocket 연결

**URL:** `ws://localhost:5080/ws`

#### Authentication

연결 후 첫 메시지로 인증:

```json
{
  "type": "auth",
  "api_key": "your_api_key"
}
```

**Response:**
```json
{
  "type": "auth_result",
  "success": true
}
```

#### Subscribe

채널 구독:

```json
{
  "type": "subscribe",
  "channels": ["positions", "signals", "trades", "metrics"]
}
```

#### Message Types

**Position Update:**
```json
{
  "type": "position_update",
  "data": {
    "symbol": "005930",
    "side": "LONG",
    "quantity": 100,
    "pnl_pct": 2.5
  },
  "timestamp": "2026-01-22T10:00:00Z"
}
```

**Signal:**
```json
{
  "type": "signal",
  "data": {
    "strategy": "bb_reversion",
    "symbol": "005930",
    "signal_type": "entry",
    "direction": "long",
    "confidence": 0.85
  },
  "timestamp": "2026-01-22T10:00:00Z"
}
```

**Trade:**
```json
{
  "type": "trade",
  "data": {
    "trade_id": "T001",
    "symbol": "005930",
    "side": "BUY",
    "quantity": 100,
    "price": 58000,
    "pnl": 150000
  },
  "timestamp": "2026-01-22T10:00:00Z"
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - 잘못된 요청 파라미터 |
| 401 | Unauthorized - 유효하지 않은 API 키 |
| 403 | Forbidden - 권한 부족 |
| 404 | Not Found - 리소스를 찾을 수 없음 |
| 429 | Too Many Requests - 요청 한도 초과 |
| 500 | Internal Server Error - 서버 내부 오류 |

**Error Response Format:**
```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "Invalid strategy name",
    "details": {
      "field": "strategy",
      "value": "unknown_strategy"
    }
  }
}
```

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Default | 100 requests/minute |
| Backtest | 10 requests/minute |
| WebSocket | 50 messages/second |

Rate limit 초과 시 `429 Too Many Requests` 응답과 함께 `Retry-After` 헤더가 반환됩니다.

---

## SDK Examples

### Python

```python
import requests

API_URL = "http://localhost:5080"
API_KEY = "your_api_key"

headers = {"X-API-Key": API_KEY}

# Get trading status
response = requests.get(f"{API_URL}/api/v1/trading/status", headers=headers)
print(response.json())

# Start trading
response = requests.post(
    f"{API_URL}/api/v1/trading/start",
    headers=headers,
    json={"strategies": ["bb_reversion"], "mode": "paper"}
)
print(response.json())
```

### WebSocket (Python)

```python
import asyncio
import websockets
import json

async def connect():
    uri = "ws://localhost:5080/ws"
    async with websockets.connect(uri) as ws:
        # Authenticate
        await ws.send(json.dumps({
            "type": "auth",
            "api_key": "your_api_key"
        }))

        # Subscribe
        await ws.send(json.dumps({
            "type": "subscribe",
            "channels": ["positions", "signals"]
        }))

        # Listen for messages
        async for message in ws:
            data = json.loads(message)
            print(data)

asyncio.run(connect())
```
