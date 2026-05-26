# Port Allocation

This repository owns the KIS Unified STS runtime ports only.

| Port | Owner | Purpose | Notes |
|---:|---|---|---|
| 8001 | `kis-dashboard` | Primary web dashboard | User-facing KIS dashboard. Use this for dashboard checks and browser access. |

Do not use host port 3000 in this repository. Port 3000 belongs to the separate `bid-vector` project on this host.

Do not reserve additional KIS host ports without a concrete service that needs them. The trading app container may listen on an internal port for container health checks, but it is not exposed on the host by default.
