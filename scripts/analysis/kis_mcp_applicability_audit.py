#!/usr/bin/env python3
"""Audit local KIS API usage against official KIS MCP artifacts.

This is an offline audit. It reads the official MCP checkout placed under
``KIS_MCP_REPO_DIR`` and compares its API catalog with local endpoint usage.
It does not call KIS Open API and does not require account credentials.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MCP_REPO_DIR = (
    Path(os.environ.get("KIS_MCP_REPO_DIR", ""))
    if os.environ.get("KIS_MCP_REPO_DIR")
    else Path.home() / ".local/share/kis-mcp/open-trading-api"
)

SCAN_TARGETS = (
    "shared/kis",
    "shared/execution",
    "services/trading",
    "services/order_router",
    "scripts/trading",
    "config/kis",
    "config/execution.yaml",
)

ENDPOINT_RE = re.compile(r"/uapi/[A-Za-z0-9/_-]+")
TR_ID_RE = re.compile(r"\b(?:[A-Z]{1,4}[A-Z0-9]{7,12})\b")

FOCUS_APIS = (
    ("stock quote", "domestic_stock", "inquire_price"),
    ("stock intraday chart", "domestic_stock", "inquire_time_itemchartprice"),
    ("stock balance", "domestic_stock", "inquire_balance"),
    ("stock volume rank", "domestic_stock", "volume_rank"),
    ("stock fluctuation rank", "domestic_stock", "fluctuation"),
    ("stock cash order schema", "domestic_stock", "order_cash"),
    ("futures quote", "domestic_futureoption", "inquire_price"),
    ("futures intraday chart", "domestic_futureoption", "inquire_time_fuopchartprice"),
    ("futures balance", "domestic_futureoption", "inquire_balance"),
    ("futures order schema", "domestic_futureoption", "order"),
    ("futures fill inquiry", "domestic_futureoption", "inquire_ccnl"),
    ("auth token", "auth", "auth_token"),
    ("websocket approval key", "auth", "auth_ws_token"),
)


@dataclass(frozen=True)
class LocalReference:
    path: str
    line: int


@dataclass(frozen=True)
class OfficialApi:
    config: str
    method: str
    name: str
    category: str
    api_path: str
    params: list[str]
    github_url: str


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _iter_scan_files(targets: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        path = REPO_ROOT / target
        if path.is_file():
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for child in path.rglob("*"):
            if child.is_file() and child.suffix in {".py", ".yaml", ".yml", ".json"}:
                files.append(child)
    return sorted(files)


def _load_code_assistant_summary(mcp_repo_dir: Path) -> dict[str, Any]:
    data_csv = mcp_repo_dir / "MCP/KIS Code Assistant MCP/data.csv"
    if not data_csv.exists():
        return {"available": False, "total": 0, "by_category": {}}

    categories: Counter[str] = Counter()
    total = 0
    with data_csv.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            total += 1
            categories[row.get("category", "unknown")] += 1

    return {
        "available": True,
        "total": total,
        "by_category": dict(sorted(categories.items())),
    }


def _load_trade_mcp_catalog(mcp_repo_dir: Path) -> list[OfficialApi]:
    configs_dir = mcp_repo_dir / "MCP/Kis Trading MCP/configs"
    if not configs_dir.exists():
        return []

    catalog: list[OfficialApi] = []
    for path in sorted(configs_dir.glob("*.json")):
        data = _read_json(path)
        apis = data.get("apis", {})
        if not isinstance(apis, dict):
            continue
        for method, raw_api in sorted(apis.items()):
            if not isinstance(raw_api, dict):
                continue
            params = raw_api.get("params", {})
            catalog.append(
                OfficialApi(
                    config=path.stem,
                    method=method,
                    name=str(raw_api.get("name", "")),
                    category=str(raw_api.get("category", "")),
                    api_path=str(raw_api.get("api_path", "")),
                    params=sorted(params) if isinstance(params, dict) else [],
                    github_url=str(raw_api.get("github_url", "")),
                )
            )
    return catalog


def _scan_local_usage() -> dict[str, dict[str, list[LocalReference]]]:
    endpoints: dict[str, list[LocalReference]] = defaultdict(list)
    tr_ids: dict[str, list[LocalReference]] = defaultdict(list)

    for path in _iter_scan_files(SCAN_TARGETS):
        rel = str(path.relative_to(REPO_ROOT))
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for endpoint in ENDPOINT_RE.findall(line):
                if endpoint.endswith("/"):
                    continue
                endpoints[endpoint].append(LocalReference(rel, lineno))
            for tr_id in TR_ID_RE.findall(line):
                if any(char.isdigit() for char in tr_id):
                    tr_ids[tr_id].append(LocalReference(rel, lineno))

    return {"endpoints": endpoints, "tr_ids": tr_ids}


def _limit_refs(refs: list[LocalReference], limit: int = 4) -> list[dict[str, Any]]:
    return [asdict(ref) for ref in refs[:limit]]


def build_report(mcp_repo_dir: Path) -> dict[str, Any]:
    code_summary = _load_code_assistant_summary(mcp_repo_dir)
    trade_catalog = _load_trade_mcp_catalog(mcp_repo_dir)
    local_usage = _scan_local_usage()

    by_path: dict[str, list[OfficialApi]] = defaultdict(list)
    by_config_method: dict[tuple[str, str], OfficialApi] = {}
    for api in trade_catalog:
        if api.api_path:
            by_path[api.api_path].append(api)
        by_config_method[(api.config, api.method)] = api

    matched = []
    missing = []
    for endpoint, refs in sorted(local_usage["endpoints"].items()):
        official = by_path.get(endpoint, [])
        item = {
            "endpoint": endpoint,
            "local_refs": _limit_refs(refs),
            "local_ref_count": len(refs),
            "official": [asdict(api) for api in official],
        }
        if official:
            matched.append(item)
        else:
            missing.append(item)

    focus = []
    for area, config, method in FOCUS_APIS:
        api = by_config_method.get((config, method))
        focus.append(
            {
                "area": area,
                "config": config,
                "method": method,
                "available": api is not None,
                "api": asdict(api) if api else None,
            }
        )

    config_counts = Counter(api.config for api in trade_catalog)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mcp_repo_dir": str(mcp_repo_dir),
        "code_assistant": code_summary,
        "trade_mcp": {
            "available": bool(trade_catalog),
            "total": len(trade_catalog),
            "by_config": dict(sorted(config_counts.items())),
        },
        "local_usage": {
            "endpoint_count": len(local_usage["endpoints"]),
            "tr_id_count": len(local_usage["tr_ids"]),
            "matched_endpoint_count": len(matched),
            "missing_endpoint_count": len(missing),
            "matched_endpoints": matched,
            "missing_endpoints": missing,
            "tr_ids": {
                tr_id: {
                    "local_refs": _limit_refs(refs),
                    "local_ref_count": len(refs),
                }
                for tr_id, refs in sorted(local_usage["tr_ids"].items())
            },
        },
        "focus_apis": focus,
        "recommendations": [
            "Use Code Assistant MCP for endpoint, sample-code, and parameter lookup.",
            "Use Trade MCP only for operator diagnostics and read-only parity checks.",
            "Keep automated trading on the existing KISClient and OrderExecutor path.",
            "Do not route live or paper orders through MCP without a separate explicit guard design.",
        ],
    }


def _format_refs(refs: list[dict[str, Any]]) -> str:
    if not refs:
        return ""
    return "<br>".join(f"{ref['path']}:{ref['line']}" for ref in refs)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# KIS MCP Applicability Audit",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- MCP checkout: `{report['mcp_repo_dir']}`",
        f"- Code Assistant catalog APIs: {report['code_assistant']['total']}",
        f"- Trade MCP tool APIs: {report['trade_mcp']['total']}",
        f"- Local KIS endpoints found: {report['local_usage']['endpoint_count']}",
        f"- Matched endpoints: {report['local_usage']['matched_endpoint_count']}",
        f"- Missing from Trade MCP catalog: {report['local_usage']['missing_endpoint_count']}",
        "",
        "## Project Application Targets",
        "",
        "| Area | MCP config.method | Official path | Params |",
        "| --- | --- | --- | --- |",
    ]

    for item in report["focus_apis"]:
        api = item["api"]
        if api:
            path = api["api_path"] or "(none)"
            params = ", ".join(api["params"][:8])
            if len(api["params"]) > 8:
                params += ", ..."
        else:
            path = "(not found)"
            params = ""
        lines.append(
            f"| {item['area']} | `{item['config']}.{item['method']}` | "
            f"`{path}` | {params} |"
        )

    lines.extend(
        [
            "",
            "## Matched Local Endpoints",
            "",
            "| Endpoint | Local refs | Official MCP APIs |",
            "| --- | --- | --- |",
        ]
    )
    for item in report["local_usage"]["matched_endpoints"]:
        official = ", ".join(
            f"`{api['config']}.{api['method']}`" for api in item["official"]
        )
        lines.append(
            f"| `{item['endpoint']}` | {_format_refs(item['local_refs'])} | "
            f"{official} |"
        )

    lines.extend(
        [
            "",
            "## Local Endpoints Missing From Trade MCP Catalog",
            "",
            "| Endpoint | Local refs |",
            "| --- | --- |",
        ]
    )
    missing = report["local_usage"]["missing_endpoints"]
    if missing:
        for item in missing:
            lines.append(
                f"| `{item['endpoint']}` | {_format_refs(item['local_refs'])} |"
            )
    else:
        lines.append("| None | |")

    lines.extend(["", "## Recommendations", ""])
    for recommendation in report["recommendations"]:
        lines.append(f"- {recommendation}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mcp-repo-dir",
        type=Path,
        default=DEFAULT_MCP_REPO_DIR,
        help="Official open-trading-api checkout containing MCP artifacts.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Output format.",
    )
    args = parser.parse_args()

    report = build_report(args.mcp_repo_dir.expanduser().resolve())
    if args.format == "json":
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
