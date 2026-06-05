#!/usr/bin/env python3
"""Evaluate post-news stock response quality from LLM screening outputs.

This script builds an event-study style report using existing artifacts:
- ``output/llm/training_rows.jsonl`` (event candidates + selected flag)
- ``output/llm/unified_data_*.json`` (news/theme enrichment per snapshot)
- minute bars from Parquet or local CSV fallback

Outputs (under ``--output-dir``):
- ``event_returns.csv``: per-event forward returns and metadata
- ``summary.json``: aggregate metrics (directional accuracy, A/B selected vs unselected)
- ``summary.md``: human-readable report
- ``top_winners.csv`` / ``top_losers.csv``: quick manual review list
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

POSITIVE_SENTIMENTS = {"긍정", "매우 긍정"}
NEGATIVE_SENTIMENTS = {"부정", "매우 부정"}


def _parse_horizons(raw: str) -> list[int]:
    out: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        h = int(token)
        if h <= 0:
            raise ValueError(f"Invalid horizon: {h}")
        out.append(h)
    if not out:
        raise ValueError("At least one horizon is required")
    return sorted(set(out))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue
    return rows


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return None
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.tz_convert("Asia/Seoul").tz_localize(None)
        return ts.to_pydatetime()
    except Exception:
        return None


def _news_direction(sentiment: str) -> int:
    if sentiment in POSITIVE_SENTIMENTS:
        return 1
    if sentiment in NEGATIVE_SENTIMENTS:
        return -1
    return 0


def _load_training_events(path: Path) -> pd.DataFrame:
    rows = _load_jsonl(path)
    out: list[dict[str, Any]] = []

    for r in rows:
        code = str(r.get("code", "")).strip()
        if not code:
            continue

        generated_at = _parse_dt(r.get("generated_at"))
        if generated_at is None:
            continue

        features = r.get("features", {})
        if not isinstance(features, dict):
            features = {}

        metrics = features.get("screening_metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}

        decision = r.get("decision", {})
        if not isinstance(decision, dict):
            decision = {}

        sentiment = str(features.get("news_sentiment", "")).strip() or "중립"
        news_count = int(_to_float(features.get("news_count"), 0.0) or 0)
        news_headlines = features.get("news_headlines", [])
        if not isinstance(news_headlines, list):
            news_headlines = []

        out.append(
            {
                "snapshot_id": str(r.get("snapshot_id", "")),
                "date": str(r.get("date", "")),
                "generated_at": generated_at,
                "code": code,
                "name": str(r.get("name", "")),
                "selected": bool(r.get("selected", False)),
                "strategy": str(decision.get("strategy", "")),
                "news_sentiment": sentiment,
                "news_direction": _news_direction(sentiment),
                "news_count": news_count,
                "news_headline_1": (
                    str(news_headlines[0]) if len(news_headlines) >= 1 else ""
                ),
                "news_headline_2": (
                    str(news_headlines[1]) if len(news_headlines) >= 2 else ""
                ),
                "screening_score": _to_float(features.get("screening_score")),
                "theme_score": _to_float(metrics.get("theme_score")),
                "theme_matched": str(metrics.get("theme_matched", "")),
                "risk_keywords_count": _len_safe(features.get("risk_keywords", [])),
            }
        )

    if not out:
        return pd.DataFrame()

    df = pd.DataFrame(out)
    df = df.sort_values(["generated_at", "code"]).reset_index(drop=True)
    return df


def _to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def _len_safe(value: Any) -> int:
    return len(value) if isinstance(value, (list, tuple, set)) else 0


def _load_unified_enrichment(
    glob_pattern: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(Path().glob(glob_pattern)):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        analysis = payload.get("analysis", {})
        if not isinstance(analysis, dict):
            continue

        snapshot_id = str(analysis.get("snapshot_id", ""))
        stock = analysis.get("stock", {})
        if not snapshot_id or not isinstance(stock, dict):
            continue

        for code, item in stock.items():
            if not isinstance(code, str) or code.startswith("_"):
                continue
            if not isinstance(item, dict):
                continue

            news = item.get("news", {})
            if not isinstance(news, dict):
                news = {}
            screening = item.get("screening", {})
            if not isinstance(screening, dict):
                screening = {}
            metrics = screening.get("metrics", {})
            if not isinstance(metrics, dict):
                metrics = {}

            key_events = news.get("mk_headlines") or news.get("key_events") or []
            if not isinstance(key_events, list):
                key_events = []

            result[(snapshot_id, code)] = {
                "news_count": int(_to_float(news.get("news_count"), 0.0) or 0),
                "news_sentiment_raw": str(news.get("sentiment", "")),
                "news_headline_1": str(key_events[0]) if len(key_events) >= 1 else "",
                "news_headline_2": str(key_events[1]) if len(key_events) >= 2 else "",
                "industry": str(metrics.get("industry", "")),
                "theme_score_raw": _to_float(metrics.get("theme_score")),
                "theme_matched_raw": str(metrics.get("theme_matched", "")),
            }

    return result


@dataclass
class MinuteSourceConfig:
    source: str
    start_date: date
    end_date: date


class MinuteDataLoader:
    def __init__(self, config: MinuteSourceConfig):
        self.config = config
        self.cache: dict[str, pd.DataFrame] = {}

    def get(self, code: str) -> pd.DataFrame:
        if code in self.cache:
            return self.cache[code]

        df: pd.DataFrame | None = None
        errors: list[str] = []

        if self.config.source in ("auto", "parquet"):
            try:
                from shared.collector.historical.stock import (
                    load_stock_minute_from_parquet,
                )

                df = load_stock_minute_from_parquet(
                    code,
                    start_date=self.config.start_date,
                    end_date=self.config.end_date,
                )
            except Exception as e:
                errors.append(f"parquet:{e}")

        if (df is None or df.empty) and self.config.source in ("auto", "csv"):
            try:
                df = self._load_from_csv(code)
            except Exception as e:
                errors.append(f"csv:{e}")

        if df is None or df.empty:
            raise ValueError(f"No minute data for {code} ({'; '.join(errors)})")

        df = df.copy()
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        if getattr(df["datetime"].dt, "tz", None) is not None:
            df["datetime"] = (
                df["datetime"].dt.tz_convert("Asia/Seoul").dt.tz_localize(None)
            )

        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = (
            df.dropna(subset=["datetime", "close"])
            .sort_values("datetime")
            .reset_index(drop=True)
        )

        start_dt = datetime.combine(self.config.start_date, time(0, 0))
        end_dt = datetime.combine(self.config.end_date + timedelta(days=1), time(0, 0))
        df = df[(df["datetime"] >= start_dt) & (df["datetime"] < end_dt)].reset_index(
            drop=True
        )

        if df.empty:
            raise ValueError(f"Minute data empty after date filter for {code}")

        self.cache[code] = df
        return df

    @staticmethod
    def _load_from_csv(code: str) -> pd.DataFrame:
        path = Path("data") / f"stock_minute_{code}.csv"
        if not path.exists():
            raise FileNotFoundError(str(path))
        return pd.read_csv(path)


def _compute_forward_returns(
    df: pd.DataFrame,
    event_ts: datetime,
    horizons: list[int],
    allow_overnight: bool,
) -> dict[str, Any]:
    if df.empty:
        return {f"ret_{h}m_pct": np.nan for h in horizons}

    dts = df["datetime"].to_numpy(dtype="datetime64[ns]")
    closes = df["close"].to_numpy(dtype="float64")

    idx = int(np.searchsorted(dts, np.datetime64(event_ts), side="left"))
    if idx >= len(df):
        out = {f"ret_{h}m_pct": np.nan for h in horizons}
        out["anchor_time"] = pd.NaT
        out["anchor_price"] = np.nan
        return out

    anchor_time = pd.Timestamp(dts[idx]).to_pydatetime()
    anchor_price = float(closes[idx])

    out: dict[str, Any] = {
        "anchor_time": anchor_time,
        "anchor_price": anchor_price,
    }

    if anchor_price <= 0:
        for h in horizons:
            out[f"ret_{h}m_pct"] = np.nan
        return out

    anchor_day = anchor_time.date()

    for h in horizons:
        target_time = anchor_time + timedelta(minutes=h)
        j = int(np.searchsorted(dts, np.datetime64(target_time), side="left"))
        if j >= len(df):
            out[f"ret_{h}m_pct"] = np.nan
            continue

        target_dt = pd.Timestamp(dts[j]).to_pydatetime()
        if not allow_overnight and target_dt.date() != anchor_day:
            out[f"ret_{h}m_pct"] = np.nan
            continue

        target_price = float(closes[j])
        out[f"ret_{h}m_pct"] = (target_price / anchor_price - 1.0) * 100.0

    return out


def _build_event_returns(
    events: pd.DataFrame,
    horizons: list[int],
    minute_loader: MinuteDataLoader,
    allow_overnight: bool,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    failed_codes: set[str] = set()

    for r in events.to_dict(orient="records"):
        code = str(r["code"])
        event_ts = r["generated_at"]

        out = dict(r)
        try:
            df = minute_loader.get(code)
            ret = _compute_forward_returns(df, event_ts, horizons, allow_overnight)
            out.update(ret)
            out["data_available"] = True
        except Exception:
            failed_codes.add(code)
            for h in horizons:
                out[f"ret_{h}m_pct"] = np.nan
            out["anchor_time"] = pd.NaT
            out["anchor_price"] = np.nan
            out["data_available"] = False

        rows.append(out)

    result = pd.DataFrame(rows)
    if failed_codes:
        print(f"[warn] minute data unavailable for {len(failed_codes)} codes")
    return result


def _directional_accuracy(df: pd.DataFrame, ret_col: str) -> float | None:
    sub = df[(df["news_direction"] != 0) & df[ret_col].notna()]
    if sub.empty:
        return None
    hit = np.sign(sub[ret_col].to_numpy(dtype="float64")) == sub[
        "news_direction"
    ].to_numpy(dtype="int64")
    return float(hit.mean())


def _summarize(
    df: pd.DataFrame,
    horizons: list[int],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "rows": int(len(df)),
        "selected_rows": int(df["selected"].sum()) if "selected" in df.columns else 0,
        "data_available_rows": (
            int(df["data_available"].sum()) if "data_available" in df.columns else 0
        ),
        "sentiment_counts": {
            str(k): int(v)
            for k, v in df["news_sentiment"]
            .value_counts(dropna=False)
            .to_dict()
            .items()
        },
        "horizons": {},
    }

    for h in horizons:
        col = f"ret_{h}m_pct"
        h_info: dict[str, Any] = {}

        sub_all = df[df[col].notna()]
        sub_sel = df[(df[col].notna()) & (df["selected"])]
        sub_unsel = df[(df[col].notna()) & (~df["selected"])]

        h_info["coverage_all"] = int(len(sub_all))
        h_info["coverage_selected"] = int(len(sub_sel))
        h_info["coverage_unselected"] = int(len(sub_unsel))

        h_info["avg_return_all_pct"] = _to_float(sub_all[col].mean())
        h_info["avg_return_selected_pct"] = _to_float(sub_sel[col].mean())
        h_info["avg_return_unselected_pct"] = _to_float(sub_unsel[col].mean())
        h_info["median_return_selected_pct"] = _to_float(sub_sel[col].median())

        h_info["directional_accuracy_all"] = _to_float(
            _directional_accuracy(sub_all, col)
        )
        h_info["directional_accuracy_selected"] = _to_float(
            _directional_accuracy(sub_sel, col)
        )

        snap_diffs: list[float] = []
        for _, g in sub_all.groupby("snapshot_id"):
            sel_mean = g.loc[g["selected"], col].mean()
            unsel_mean = g.loc[~g["selected"], col].mean()
            if pd.notna(sel_mean) and pd.notna(unsel_mean):
                snap_diffs.append(float(sel_mean - unsel_mean))

        if snap_diffs:
            h_info["snapshot_ab_mean_diff_pct"] = _to_float(float(np.mean(snap_diffs)))
            h_info["snapshot_ab_win_rate"] = _to_float(
                float(np.mean(np.array(snap_diffs) > 0.0))
            )
        else:
            h_info["snapshot_ab_mean_diff_pct"] = None
            h_info["snapshot_ab_win_rate"] = None

        by_sentiment: dict[str, Any] = {}
        for sentiment, gs in sub_all.groupby("news_sentiment"):
            by_sentiment[str(sentiment)] = {
                "count": int(len(gs)),
                "avg_return_pct": _to_float(gs[col].mean()),
                "selected_avg_return_pct": _to_float(
                    gs.loc[gs["selected"], col].mean()
                ),
                "selected_count": int(gs["selected"].sum()),
            }
        h_info["by_sentiment"] = by_sentiment

        summary["horizons"][str(h)] = h_info

    return summary


def _render_summary_md(
    summary: dict[str, Any],
    horizons: list[int],
    args: argparse.Namespace,
) -> str:
    lines: list[str] = []
    lines.append("# News Response Evaluation")
    lines.append("")
    lines.append(f"- generated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- rows: {summary.get('rows', 0)}")
    lines.append(f"- selected_rows: {summary.get('selected_rows', 0)}")
    lines.append(f"- data_available_rows: {summary.get('data_available_rows', 0)}")
    lines.append(f"- source: {args.source}")
    lines.append(f"- horizons(min): {','.join(str(h) for h in horizons)}")
    lines.append("")

    lines.append("## Sentiment Distribution")
    for k, v in summary.get("sentiment_counts", {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Horizon Metrics")
    for h in horizons:
        info = summary.get("horizons", {}).get(str(h), {})
        lines.append(f"### {h}m")
        lines.append(f"- coverage_selected: {info.get('coverage_selected')}")
        lines.append(
            f"- avg_return_selected_pct: {info.get('avg_return_selected_pct')}"
        )
        lines.append(
            f"- directional_accuracy_selected: {info.get('directional_accuracy_selected')}"
        )
        lines.append(
            f"- snapshot_ab_mean_diff_pct: {info.get('snapshot_ab_mean_diff_pct')}"
        )
        lines.append(f"- snapshot_ab_win_rate: {info.get('snapshot_ab_win_rate')}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _apply_filters(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    out = df.copy()

    if args.selected_only:
        out = out[out["selected"]]

    if args.codes:
        code_set = {c.strip() for c in args.codes.split(",") if c.strip()}
        out = out[out["code"].isin(code_set)]

    if args.start_date:
        start_dt = datetime.strptime(args.start_date, "%Y-%m-%d")
        out = out[out["generated_at"] >= start_dt]

    if args.end_date:
        end_dt = datetime.strptime(args.end_date, "%Y-%m-%d") + timedelta(days=1)
        out = out[out["generated_at"] < end_dt]

    if args.intraday_only:
        start_t = datetime.strptime(args.intraday_start, "%H:%M").time()
        end_t = datetime.strptime(args.intraday_end, "%H:%M").time()
        out = out[out["generated_at"].dt.time.between(start_t, end_t)]

    if args.sentiments:
        sent_set = {s.strip() for s in args.sentiments.split(",") if s.strip()}
        out = out[out["news_sentiment"].isin(sent_set)]

    if args.max_events and args.max_events > 0:
        out = out.head(args.max_events)

    return out.reset_index(drop=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Evaluate stock response quality after news-driven LLM events"
    )
    p.add_argument("--training-rows", default="output/llm/training_rows.jsonl")
    p.add_argument("--unified-glob", default="output/llm/unified_data_*.json")
    p.add_argument("--output-dir", default="artifacts/news_response_eval")

    p.add_argument(
        "--horizons", default="5,15,30,60", help="Forward return horizons in minutes"
    )
    p.add_argument("--source", choices=["auto", "parquet", "csv"], default="auto")
    p.add_argument("--allow-overnight-horizon", action="store_true")

    p.add_argument("--selected-only", action="store_true")
    p.add_argument(
        "--intraday-only",
        dest="intraday_only",
        action="store_true",
        default=True,
        help="Keep only events inside intraday window",
    )
    p.add_argument(
        "--all-hours",
        dest="intraday_only",
        action="store_false",
        help="Disable intraday window filter",
    )
    p.add_argument("--intraday-start", default="08:30")
    p.add_argument("--intraday-end", default="15:30")
    p.add_argument("--start-date", help="YYYY-MM-DD")
    p.add_argument("--end-date", help="YYYY-MM-DD")
    p.add_argument("--codes", help="Comma-separated stock codes")
    p.add_argument("--sentiments", help="Comma-separated sentiment filters")
    p.add_argument("--max-events", type=int, default=0)
    return p


def main() -> None:
    args = build_parser().parse_args()
    horizons = _parse_horizons(args.horizons)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    events = _load_training_events(Path(args.training_rows))
    if events.empty:
        raise SystemExit("No events found in training_rows")

    enrichment = _load_unified_enrichment(args.unified_glob)
    if enrichment:
        keys = list(zip(events["snapshot_id"], events["code"], strict=False))
        news_count = []
        news_h1 = []
        news_h2 = []
        industry = []
        theme_score_raw = []
        theme_matched_raw = []
        for k in keys:
            info = enrichment.get((str(k[0]), str(k[1])), {})
            news_count.append(int(info.get("news_count", 0)))
            news_h1.append(str(info.get("news_headline_1", "")))
            news_h2.append(str(info.get("news_headline_2", "")))
            industry.append(info.get("industry", ""))
            theme_score_raw.append(info.get("theme_score_raw"))
            theme_matched_raw.append(info.get("theme_matched_raw", ""))

        existing_news_count = (
            pd.to_numeric(events.get("news_count", 0), errors="coerce")
            .fillna(0)
            .astype(int)
        )
        events["news_count"] = np.where(
            np.array(news_count) > 0, np.array(news_count), existing_news_count
        )
        events["news_headline_1"] = np.where(
            np.array([len(x) > 0 for x in news_h1]),
            np.array(news_h1, dtype=object),
            events.get("news_headline_1", ""),
        )
        events["news_headline_2"] = np.where(
            np.array([len(x) > 0 for x in news_h2]),
            np.array(news_h2, dtype=object),
            events.get("news_headline_2", ""),
        )
        events["industry"] = industry
        events["theme_score_raw"] = theme_score_raw
        events["theme_matched_raw"] = theme_matched_raw
    else:
        if "industry" not in events.columns:
            events["industry"] = ""
        if "theme_score_raw" not in events.columns:
            events["theme_score_raw"] = np.nan
        if "theme_matched_raw" not in events.columns:
            events["theme_matched_raw"] = ""

    events = _apply_filters(events, args)
    if events.empty:
        raise SystemExit("No events left after filters")

    start_day = events["generated_at"].min().date()
    end_day = events["generated_at"].max().date() + timedelta(days=1)

    loader = MinuteDataLoader(
        MinuteSourceConfig(
            source=args.source,
            start_date=start_day,
            end_date=end_day,
        )
    )

    event_returns = _build_event_returns(
        events,
        horizons,
        loader,
        allow_overnight=args.allow_overnight_horizon,
    )

    for h in horizons:
        col = f"ret_{h}m_pct"
        hit_col = f"hit_{h}m"
        event_returns[hit_col] = np.where(
            event_returns["news_direction"] == 0,
            np.nan,
            (
                np.sign(event_returns[col].astype(float))
                == event_returns["news_direction"]
            ).astype(float),
        )

    summary = _summarize(event_returns, horizons)

    event_csv = output_dir / "event_returns.csv"
    summary_json = output_dir / "summary.json"
    summary_md = output_dir / "summary.md"

    event_returns.sort_values(
        ["generated_at", "selected", "code"], ascending=[True, False, True]
    ).to_csv(
        event_csv,
        index=False,
        encoding="utf-8-sig",
    )

    summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    summary_md.write_text(_render_summary_md(summary, horizons, args), encoding="utf-8")

    key_h = 30 if 30 in horizons else horizons[-1]
    key_col = f"ret_{key_h}m_pct"
    selected = event_returns[
        event_returns["selected"] & event_returns[key_col].notna()
    ].copy()
    if not selected.empty:
        selected.nlargest(20, key_col).to_csv(
            output_dir / "top_winners.csv", index=False, encoding="utf-8-sig"
        )
        selected.nsmallest(20, key_col).to_csv(
            output_dir / "top_losers.csv", index=False, encoding="utf-8-sig"
        )

    print(
        json.dumps(
            {
                "events": int(len(event_returns)),
                "selected_events": int(event_returns["selected"].sum()),
                "output_dir": str(output_dir),
                "event_returns": str(event_csv),
                "summary_json": str(summary_json),
                "summary_md": str(summary_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
