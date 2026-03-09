"""FastAPI dashboard application."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from shared.api.cors import get_cors_config, load_api_config
from shared.strategy.registry import register_builtin_components

logger = logging.getLogger(__name__)

# OpenAPI tags for documentation organization
OPENAPI_TAGS = [
    {
        "name": "trading",
        "description": "Trading operations and status management",
    },
    {
        "name": "signals",
        "description": "Trading signals and entry/exit alerts",
    },
    {
        "name": "trades",
        "description": "Trade history and performance statistics",
    },
    {
        "name": "backtest",
        "description": "Backtesting operations and results",
    },
    {
        "name": "experiments",
        "description": "MLflow experiment tracking",
    },
    {
        "name": "strategies",
        "description": "Strategy configuration management",
    },
]


def create_app(
    title: str = "KIS Unified Trading Dashboard",
    debug: bool = False,
    require_auth: Optional[bool] = None,
    api_key: Optional[str] = None,
    rate_limit: int = 0,
    rate_limit_window: int = 60,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        title: Application title.
        debug: Enable debug mode.
        require_auth: If True, require API key authentication. If None (default), enables auth if api_key is available.
        api_key: The API key to use for authentication. Reads from DASHBOARD_API_KEY env var if not provided.
        rate_limit: Maximum requests per window. 0 disables rate limiting.
        rate_limit_window: Rate limit window in seconds.
    """
    # Read API key from environment if not provided
    if api_key is None:
        api_key = os.environ.get("DASHBOARD_API_KEY")

    # Check if dev mode is enabled (disables authentication)
    dev_mode = os.environ.get("DASHBOARD_DEV_MODE", "").lower() == "true"
    if dev_mode:
        logger.warning("Dev mode enabled - authentication disabled")
        require_auth = False
    elif require_auth is None:
        # Honor DASHBOARD_REQUIRE_AUTH env var (documented in .env.example)
        env_require = os.environ.get("DASHBOARD_REQUIRE_AUTH", "").lower()
        if env_require == "true":
            require_auth = True
        elif env_require == "false":
            require_auth = False
        else:
            # Fallback: enable auth if API key is available
            require_auth = bool(api_key)

    # Warn if auth is required but no API key is configured
    if require_auth and not api_key:
        logger.critical(
            "DASHBOARD_REQUIRE_AUTH=true but DASHBOARD_API_KEY is not set. "
            "All dashboard requests will be rejected."
        )

    # Initialize strategy registries
    register_builtin_components()

    app = FastAPI(
        title=title,
        description="Real-time trading dashboard for KIS unified platform",
        version="1.0.0",
        debug=debug,
        openapi_tags=OPENAPI_TAGS,
    )

    # Load CORS configuration (never uses wildcard origins)
    api_config = load_api_config()
    cors_config = get_cors_config(api_config)

    # CORS middleware - secure configuration without wildcard origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config["allow_origins"],
        allow_credentials=cors_config["allow_credentials"],
        allow_methods=cors_config["allow_methods"],
        allow_headers=cors_config["allow_headers"],
    )

    # Rate limiting middleware (add first so it runs before auth)
    if rate_limit > 0:
        from services.dashboard.middleware.rate_limit import RateLimitMiddleware

        app.add_middleware(
            RateLimitMiddleware,
            requests_per_window=rate_limit,
            window_seconds=rate_limit_window,
        )

    # API key authentication middleware
    if require_auth and api_key:
        from services.dashboard.middleware.auth import APIKeyMiddleware

        app.add_middleware(APIKeyMiddleware, api_key=api_key)

    # HTML view middleware (renders HTML for browser requests to API endpoints)
    from services.dashboard.middleware.html_view import HTMLViewMiddleware

    app.add_middleware(HTMLViewMiddleware)

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register API routes."""
    from fastapi import WebSocket

    from services.dashboard.routes import (
        backtest,
        experiments,
        signals,
        strategies,
        trades,
        trading,
    )
    from services.dashboard.websocket import websocket_endpoint

    # Include API routers
    app.include_router(trading.router)
    app.include_router(signals.router)
    app.include_router(trades.router)
    app.include_router(backtest.router)
    app.include_router(experiments.router)
    app.include_router(strategies.router)

    # WebSocket endpoint
    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await websocket_endpoint(websocket)

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Dashboard landing page."""
        return _DASHBOARD_HTML


# =============================================================================
# Dashboard HTML
# =============================================================================

_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KIS Unified Trading Dashboard</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d28; --border: #2a2d3a;
    --text: #e1e4ed; --muted: #8b8fa3; --accent: #6c8aff;
    --green: #22c55e; --red: #ef4444; --yellow: #eab308;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); }
  .header {
    padding: 20px 24px; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
  }
  .header h1 { font-size: 18px; font-weight: 600; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
  .status-dot.ok { background: var(--green); }
  .status-dot.err { background: var(--red); }
  .header-right { display: flex; align-items: center; gap: 16px; font-size: 13px; color: var(--muted); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; padding: 24px; }
  .card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px;
  }
  .card-label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
  .card-value { font-size: 28px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .card-value.positive { color: var(--green); }
  .card-value.negative { color: var(--red); }
  .card-sub { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .section { padding: 0 24px 24px; }
  .section-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: var(--muted); }
  table { width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 10px; overflow: hidden; border: 1px solid var(--border); }
  th { text-align: left; padding: 10px 14px; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }
  td { padding: 10px 14px; font-size: 13px; border-bottom: 1px solid var(--border); font-variant-numeric: tabular-nums; }
  tr:last-child td { border-bottom: none; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .badge.buy { background: rgba(34,197,94,0.15); color: var(--green); }
  .badge.sell { background: rgba(239,68,68,0.15); color: var(--red); }
  .badge.running { background: rgba(108,138,255,0.15); color: var(--accent); }
  .badge.idle { background: rgba(139,143,163,0.15); color: var(--muted); }
  .links { display: flex; gap: 10px; padding: 24px; flex-wrap: wrap; }
  .links a {
    padding: 8px 16px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; color: var(--accent); text-decoration: none; font-size: 13px;
  }
  .links a:hover { border-color: var(--accent); }
  .empty { color: var(--muted); font-size: 13px; padding: 20px; text-align: center; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 0 24px 24px; }
  @media (max-width: 768px) { .two-col { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<div class="header">
  <h1>KIS Unified Trading</h1>
  <div class="header-right">
    <span><span class="status-dot" id="health-dot"></span><span id="health-text">connecting...</span></span>
    <span id="clock"></span>
  </div>
</div>

<div class="grid" id="stats">
  <div class="card"><div class="card-label">Trading Status</div><div class="card-value" id="s-state">--</div></div>
  <div class="card"><div class="card-label">Open Positions</div><div class="card-value" id="s-positions">--</div></div>
  <div class="card"><div class="card-label">Total P&L</div><div class="card-value" id="s-pnl">--</div><div class="card-sub" id="s-pnl-sub"></div></div>
  <div class="card"><div class="card-label">Total Trades</div><div class="card-value" id="s-trades">--</div></div>
  <div class="card"><div class="card-label">Win Rate</div><div class="card-value" id="s-winrate">--</div></div>
  <div class="card"><div class="card-label">Signals Today</div><div class="card-value" id="s-signals">--</div><div class="card-sub" id="s-signals-sub"></div></div>
</div>

<div class="two-col">
  <div>
    <div class="section-title">Open Positions</div>
    <table>
      <thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Current</th><th>P&L %</th></tr></thead>
      <tbody id="pos-body"><tr><td colspan="6" class="empty">No open positions</td></tr></tbody>
    </table>
  </div>
  <div>
    <div class="section-title">Recent Signals</div>
    <table>
      <thead><tr><th>Time</th><th>Symbol</th><th>Type</th><th>Strategy</th><th>Conf</th></tr></thead>
      <tbody id="sig-body"><tr><td colspan="5" class="empty">No signals</td></tr></tbody>
    </table>
  </div>
</div>

<div class="section">
  <div class="section-title">Recent Trades</div>
  <table>
    <thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Strategy</th></tr></thead>
    <tbody id="trade-body"><tr><td colspan="7" class="empty">No trades yet</td></tr></tbody>
  </table>
</div>

<div class="links">
  <a href="/docs">API Docs</a>
  <a href="/api/trading/status">Trading Status</a>
  <a href="/api/trades">Trade History</a>
  <a href="/api/signals">Signals</a>
  <a href="/api/backtest">Backtests</a>
  <a href="/api/experiments">Experiments</a>
</div>

<script>
const $ = id => document.getElementById(id);
const fmt = n => n == null ? '--' : Number(n).toLocaleString('ko-KR');
const fmtPct = n => n == null ? '--' : Number(n).toFixed(2) + '%';

function updateClock() {
  $('clock').textContent = new Date().toLocaleTimeString('ko-KR', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
setInterval(updateClock, 1000); updateClock();

async function fetchJSON(url) {
  try { const r = await fetch(url); return r.ok ? await r.json() : null; }
  catch { return null; }
}

async function refresh() {
  // Health
  const h = await fetchJSON('/health');
  const dot = $('health-dot');
  const txt = $('health-text');
  if (h) { dot.className = 'status-dot ok'; txt.textContent = 'healthy'; }
  else   { dot.className = 'status-dot err'; txt.textContent = 'error'; }

  // Trading status
  const ts = await fetchJSON('/api/trading/status');
  if (ts) {
    const running = ts.is_running;
    $('s-state').innerHTML = running
      ? '<span class="badge running">RUNNING</span>'
      : '<span class="badge idle">IDLE</span>';
    $('s-positions').textContent = fmt(ts.total_positions || 0);
    const pnl = ts.total_pnl || 0;
    const pnlEl = $('s-pnl');
    pnlEl.textContent = fmt(Math.round(pnl));
    pnlEl.className = 'card-value ' + (pnl >= 0 ? 'positive' : 'negative');
    $('s-pnl-sub').textContent = 'KRW';
  }

  // Positions
  const pos = await fetchJSON('/api/trading/positions');
  const pb = $('pos-body');
  if (pos && pos.length > 0) {
    pb.innerHTML = pos.map(p => `<tr>
      <td>${p.code || p.symbol || '--'}</td>
      <td><span class="badge ${(p.side||'').toLowerCase()}">${p.side||'--'}</span></td>
      <td>${fmt(p.quantity)}</td>
      <td>${fmt(p.entry_price)}</td>
      <td>${fmt(p.current_price)}</td>
      <td style="color:${(p.pnl_pct||0)>=0?'var(--green)':'var(--red)'}">${fmtPct(p.pnl_pct)}</td>
    </tr>`).join('');
  } else {
    pb.innerHTML = '<tr><td colspan="6" class="empty">No open positions</td></tr>';
  }

  // Trades
  const tr = await fetchJSON('/api/trades?limit=10');
  const tb = $('trade-body');
  const trades = tr && tr.trades ? tr.trades : (Array.isArray(tr) ? tr : []);
  if (trades.length > 0) {
    let totalTrades = 0, wins = 0;
    trades.forEach(t => { totalTrades++; if ((t.pnl||0) > 0) wins++; });
    $('s-trades').textContent = fmt(tr.total || totalTrades);
    tb.innerHTML = trades.map(t => {
      const pnl = t.pnl || 0;
      const time = t.exit_time ? new Date(t.exit_time).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'}) : '--';
      return `<tr>
        <td>${time}</td>
        <td>${t.symbol||'--'}</td>
        <td><span class="badge ${(t.side||'').toLowerCase()}">${t.side||'--'}</span></td>
        <td>${fmt(t.entry_price)}</td>
        <td>${fmt(t.exit_price)}</td>
        <td style="color:${pnl>=0?'var(--green)':'var(--red)'}">${fmt(Math.round(pnl))}</td>
        <td>${t.strategy||'--'}</td>
      </tr>`;
    }).join('');
  } else {
    $('s-trades').textContent = '0';
    tb.innerHTML = '<tr><td colspan="7" class="empty">No trades yet</td></tr>';
  }

  // Trade statistics
  const stats = await fetchJSON('/api/trades/statistics');
  if (stats) {
    $('s-winrate').textContent = fmtPct(stats.win_rate);
    if (stats.total_trades) $('s-trades').textContent = fmt(stats.total_trades);
  }

  // Signals
  const sig = await fetchJSON('/api/signals?limit=10');
  const signals = sig && sig.signals ? sig.signals : (Array.isArray(sig) ? sig : []);
  const sb = $('sig-body');
  $('s-signals').textContent = fmt(signals.length);
  const buys = signals.filter(s => (s.side||'').toUpperCase() === 'BUY').length;
  const sells = signals.length - buys;
  $('s-signals-sub').textContent = signals.length > 0 ? `BUY ${buys} / SELL ${sells}` : '';
  if (signals.length > 0) {
    sb.innerHTML = signals.map(s => {
      const time = s.timestamp ? new Date(s.timestamp).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'}) : '--';
      const side = (s.side||'').toUpperCase();
      return `<tr>
        <td>${time}</td>
        <td>${s.symbol||'--'}</td>
        <td><span class="badge ${side.toLowerCase()}">${side||s.signal_type||'--'}</span></td>
        <td>${s.strategy||'--'}</td>
        <td>${s.confidence != null ? Number(s.confidence).toFixed(2) : '--'}</td>
      </tr>`;
    }).join('');
  } else {
    sb.innerHTML = '<tr><td colspan="5" class="empty">No signals</td></tr>';
  }
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""
