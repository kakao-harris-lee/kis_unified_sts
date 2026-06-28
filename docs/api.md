# API Documentation

**Status:** Current. The old `services/api` gateway, `:8000`, and `/api/v1/*`
routes are retired. The single API surface is `services/dashboard` behind Caddy.

## Base URLs

- Operator/Caddy URL: `http://localhost:5081`
- Internal Docker URL: `http://dashboard:8001`
- WebSocket: `ws://localhost:5081/ws`

`DASHBOARD_HOST_PORT` controls the host-published Caddy port. The paper/local
default is `5081`; Caddy still listens on container port `5080` internally.
Internal service ports are not host-published in the supported runtime.

## Core Routes

| Route | Purpose |
|-------|---------|
| `GET /health` | Dashboard service health. |
| `GET /metrics` | Prometheus metrics. |
| `GET /api/health/summary` | Ops cockpit summary. |
| `GET /api/trading/status?asset_class={stock|futures|all}` | Trading status snapshot. |
| `GET /api/trading/positions?asset_class={stock|futures|all}` | Open positions. |
| `GET /api/trading/risk-exposure?asset_class={stock|futures|all}` | Risk/exposure board data. |
| `POST /api/trading/start` | Start supported trading runtime path. |
| `POST /api/trading/stop` | Stop supported trading runtime path. |
| `POST /api/trading/kill-switch` | Trigger kill-switch action. |
| `GET /api/signals` | Signal list/detail data. |
| `GET /api/signals/{signal_id}/trace` | Read-only signal decision trace: LLM context, strategy inputs, risk/orderability, lifecycle lineage, scorecard, and evidence gaps. |
| `GET /api/trades` | Runtime trade history. |
| `GET /api/trades/lifecycle` | Signal -> order -> fill -> position -> trade lineage. |
| `GET /api/strategies` | Strategy registry data. |
| `GET /api/strategy-builder/*` | Visual builder API. |
| `GET /api/strategy-lab/*` | Strategy Lab preview/order-ticket API. |
| `GET /api/kis-builder/experiments/*` | Stock experiment reports and jobs. |
| `GET /api/event-context/diagnostics` | Setup C event-context diagnostics. |
| `GET /api/coverage` | Universe and data coverage snapshot. |

The Next.js frontend proxies `/api/experiments/*` to
`/api/kis-builder/experiments/*` through
`strategy-builder-ui/src/app/api/[...path]/route.ts`.

## Python Example

```python
import requests

api_url = "http://localhost:5081"

status = requests.get(
    f"{api_url}/api/trading/status",
    params={"asset_class": "all"},
    timeout=10,
)
status.raise_for_status()
print(status.json())

risk = requests.get(
    f"{api_url}/api/trading/risk-exposure",
    params={"asset_class": "all"},
    timeout=10,
)
risk.raise_for_status()
print(risk.json())
```

## WebSocket Example

```python
import asyncio
import json

import websockets


async def main() -> None:
    async with websockets.connect("ws://localhost:5081/ws") as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "subscribe",
                    "channels": ["positions", "signals"],
                }
            )
        )
        async for message in ws:
            print(json.loads(message))


asyncio.run(main())
```

## Historical Reference

The retired gateway reference is archived at
[`archive/api-legacy-services-api.md`](archive/api-legacy-services-api.md).
