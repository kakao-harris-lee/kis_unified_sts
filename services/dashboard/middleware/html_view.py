"""Middleware that renders HTML views for browser requests to API endpoints.

When a browser (Accept: text/html) hits an API endpoint, this middleware
wraps the JSON response in a styled HTML page. API clients (Accept: application/json)
receive normal JSON responses unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from html import escape

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

# Page configs: path prefix -> (title, description)
_PAGE_META: dict[str, tuple[str, str]] = {
    "/api/trading/status": ("Trading Status", "Current trading system status"),
    "/api/trading/positions": ("Open Positions", "Currently open positions"),
    "/api/trades/closed/statistics": (
        "Closed Trade Statistics",
        "Closed trade performance statistics",
    ),
    "/api/trades/closed": ("Closed Trades", "Closed trade records"),
    "/api/trades/statistics": (
        "Trade Statistics",
        "Overall trade performance statistics",
    ),
    "/api/trades/by-strategy": (
        "Strategy Performance",
        "Performance grouped by strategy",
    ),
    "/api/trades": ("Trade History", "Completed trade records"),
    "/api/signals/history": ("Signal History", "Signal generation history"),
    "/api/signals": ("Signals", "Trading signals"),
    "/api/backtest": ("Backtests", "Backtest results"),
    "/api/experiments": ("Experiments", "MLflow experiments"),
}


def _wants_html(request: Request) -> bool:
    """Check if the request prefers HTML (browser)."""
    accept = request.headers.get("accept", "")
    # Browsers send text/html first in Accept header
    if "text/html" not in accept:
        return False
    # API clients typically send application/json
    return not accept.startswith("application/json")


def _get_page_meta(path: str) -> tuple[str, str] | None:
    """Match path to page metadata, longest prefix first."""
    for prefix in sorted(_PAGE_META, key=len, reverse=True):
        if (
            path == prefix
            or path.startswith(prefix + "/")
            or path.startswith(prefix + "?")
        ):
            return _PAGE_META[prefix]
    return None


def _render_value(val: object, depth: int = 0) -> str:
    """Render a JSON value as HTML table rows."""
    if isinstance(val, dict):
        rows = []
        for k, v in val.items():
            rendered = _render_value(v, depth + 1)
            rows.append(
                f'<tr><td class="key">{escape(str(k))}</td>'
                f'<td class="val">{rendered}</td></tr>'
            )
        return f'<table class="kv">{"".join(rows)}</table>'
    if isinstance(val, list):
        if not val:
            return '<span class="muted">empty</span>'
        # Check if list of dicts -> render as data table
        if isinstance(val[0], dict):
            return _render_data_table(val)
        return ", ".join(escape(str(v)) for v in val)
    if isinstance(val, bool):
        cls = "badge running" if val else "badge idle"
        return f'<span class="{cls}">{val}</span>'
    if isinstance(val, (int, float)):
        return _render_number(val)
    if val is None:
        return '<span class="muted">--</span>'
    return escape(str(val))


def _render_number(n: int | float) -> str:
    """Render a number with color for P&L values."""
    if isinstance(n, float) and abs(n) > 100:
        cls = "positive" if n > 0 else "negative" if n < 0 else ""
        return f'<span class="{cls}">{n:,.2f}</span>'
    if isinstance(n, float):
        return f"{n:.4f}"
    return f"{n:,}"


def _render_data_table(items: list[dict]) -> str:
    """Render a list of dicts as an HTML table."""
    if not items:
        return '<span class="muted">empty</span>'

    keys = list(items[0].keys())
    header = "".join(f"<th>{escape(k)}</th>" for k in keys)
    rows = []
    for item in items:
        cells = "".join(f"<td>{_render_value(item.get(k), 1)}</td>" for k in keys)
        rows.append(f"<tr>{cells}</tr>")

    return (
        f'<table class="data-table"><thead><tr>{header}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _build_html(title: str, description: str, data: object, path: str) -> str:
    """Build the full HTML page wrapping JSON data."""
    if isinstance(data, dict):
        body = _render_value(data)
    elif isinstance(data, list):
        body = (
            _render_data_table(data)
            if data and isinstance(data[0], dict)
            else _render_value(data)
        )
    else:
        body = f"<pre>{escape(json.dumps(data, indent=2, default=str))}</pre>"

    nav_links = "".join(
        f'<a href="{p}" class="{"active" if p == path else ""}">{t}</a>'
        for p, (t, _) in _PAGE_META.items()
    )

    return f"""\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} - KIS Dashboard</title>
<style>
:root {{
  --bg:#0f1117; --surface:#1a1d28; --border:#2a2d3a;
  --text:#e1e4ed; --muted:#8b8fa3; --accent:#6c8aff;
  --green:#22c55e; --red:#ef4444;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,'Segoe UI',sans-serif; background:var(--bg); color:var(--text); }}
.header {{
  padding:16px 24px; border-bottom:1px solid var(--border);
  display:flex; justify-content:space-between; align-items:center;
}}
.header h1 {{ font-size:16px; font-weight:600; }}
.header a {{ color:var(--accent); text-decoration:none; font-size:13px; }}
nav {{ display:flex; gap:4px; padding:12px 24px; flex-wrap:wrap; border-bottom:1px solid var(--border); }}
nav a {{
  padding:6px 12px; border-radius:6px; font-size:12px; color:var(--muted);
  text-decoration:none; white-space:nowrap;
}}
nav a:hover {{ background:var(--surface); color:var(--text); }}
nav a.active {{ background:var(--accent); color:#fff; }}
.content {{ padding:24px; }}
.page-title {{ font-size:20px; font-weight:700; margin-bottom:4px; }}
.page-desc {{ font-size:13px; color:var(--muted); margin-bottom:20px; }}
table.kv {{ border-collapse:collapse; }}
table.kv td {{ padding:6px 14px 6px 0; font-size:14px; vertical-align:top; }}
table.kv td.key {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.5px; white-space:nowrap; min-width:140px; }}
table.data-table {{
  width:100%; border-collapse:collapse; background:var(--surface);
  border-radius:10px; overflow:hidden; border:1px solid var(--border);
}}
table.data-table th {{
  text-align:left; padding:10px 14px; font-size:11px; color:var(--muted);
  text-transform:uppercase; letter-spacing:.5px; border-bottom:1px solid var(--border);
}}
table.data-table td {{
  padding:10px 14px; font-size:13px; border-bottom:1px solid var(--border);
  font-variant-numeric:tabular-nums;
}}
table.data-table tr:last-child td {{ border-bottom:none; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }}
.badge.running {{ background:rgba(108,138,255,.15); color:var(--accent); }}
.badge.idle {{ background:rgba(139,143,163,.15); color:var(--muted); }}
.positive {{ color:var(--green); }}
.negative {{ color:var(--red); }}
.muted {{ color:var(--muted); }}
.json-toggle {{
  margin-top:24px; padding:8px 16px; background:var(--surface);
  border:1px solid var(--border); border-radius:8px;
  color:var(--accent); cursor:pointer; font-size:12px;
}}
pre.json {{
  display:none; margin-top:12px; padding:16px; background:var(--surface);
  border:1px solid var(--border); border-radius:8px;
  font-size:12px; overflow-x:auto; white-space:pre-wrap; word-break:break-all;
}}
</style>
</head>
<body>
<div class="header">
  <h1><a href="/" style="color:var(--text);text-decoration:none">KIS Dashboard</a></h1>
  <a href="/docs">API Docs</a>
</div>
<nav>{nav_links}</nav>
<div class="content">
  <div class="page-title">{escape(title)}</div>
  <div class="page-desc">{escape(description)}</div>
  {body}
  <button class="json-toggle" onclick="
    var el=document.getElementById('raw');
    el.style.display=el.style.display==='none'?'block':'none';
  ">Show Raw JSON</button>
  <pre class="json" id="raw">{escape(json.dumps(data, indent=2, default=str, ensure_ascii=False))}</pre>
</div>
</body>
</html>"""


class HTMLViewMiddleware(BaseHTTPMiddleware):
    """Wrap API JSON responses in HTML for browser requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Only intercept /api/* paths for browser requests
        if not path.startswith("/api/") or not _wants_html(request):
            return await call_next(request)

        meta = _get_page_meta(path)
        if meta is None:
            return await call_next(request)

        title, description = meta

        response = await call_next(request)

        # Only wrap successful JSON responses
        if response.status_code != 200:
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Read response body
        body_parts = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                body_parts.append(chunk)
            else:
                body_parts.append(chunk.encode("utf-8"))
        raw = b"".join(body_parts)

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return Response(
                content=raw, status_code=200, headers=dict(response.headers)
            )

        html = _build_html(title, description, data, path)
        return HTMLResponse(content=html, status_code=200)
