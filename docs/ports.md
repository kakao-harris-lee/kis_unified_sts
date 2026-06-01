# Port Allocation

This repository owns the KIS Unified STS runtime ports only.

| Port | Owner | Purpose | Notes |
|---:|---|---|---|
| 5080 | `kis-caddy` | Single KIS web entrypoint | User-facing dashboard, Strategy Builder UI, API proxy, and WebSocket entry. |

Do not use host port 3000 in this repository. Port 3000 belongs to the separate `bid-vector` project on this host.

Do not publish `dashboard:8001` or `strategy-builder-ui:3100` on the host. Those are Docker-network internal service ports behind Caddy.

Do not reserve additional KIS host ports without a concrete service that needs them. Containers may listen on internal ports for health checks or reverse proxy routing, but they are not exposed on the host by default.
