#!/usr/bin/env python3
"""Hindsight validation report for the Market Risk Score (roadmap §4.4-2).

Offline, file-backed (validate_har_rv.py pattern): reads score columns that
the Phase 1a hindcast CLI wrote into the ``market_structure_daily`` Parquet
``close`` rows, plus the KOSPI daily close from the same rows, and writes a
markdown report + gate-decision JSON under ``reports/market-risk/``.

Sections:
* Discrimination — forward 5/20-trading-day KOSPI returns after score >=
  threshold days vs all days (mean / median / lower quantiles + one-sided
  permutation test, no new stats dependency).
* Band stability (O7) — dwell-time distribution, transition counts, and
  ELEVATED<->HIGH round trips (flapping).
* Episode replay — was the score already elevated at the prior close /
  same-day premarket for configured crash episodes (default 2026-07-02)?

Usage:
    python scripts/validation/validate_market_risk_score.py
    python scripts/validation/validate_market_risk_score.py \
        --start 2024-07-01 --end 2026-07-01 --tag phase1-gate
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.validation.market_risk_common import (
    KST,
    MarketRiskValidationConfig,
    ValidationSettings,
    build_store,
    first_present_column,
    is_missing,
    load_snapshot_frame,
)

INSUFFICIENT_DATA = "insufficient data"


# ---------------------------------------------------------------------------
# Forward returns + threshold discrimination
# ---------------------------------------------------------------------------


def compute_forward_returns(frame: Any, price_column: str, horizons: list[int]) -> Any:
    """Per trade_date forward returns over trading-day horizons.

    Uses only rows where the price is present; the horizon is counted in
    available close rows (trading days), matching §4.4-2 semantics. Returns a
    DataFrame with ``trade_date`` and ``fwd_{h}d`` fractional-return columns.
    """
    import pandas as pd

    priced = frame[[not is_missing(v) for v in frame[price_column]]]
    priced = priced.sort_values("trade_date").reset_index(drop=True)
    out = pd.DataFrame({"trade_date": priced["trade_date"]})
    price = priced[price_column].astype(float)
    for horizon in horizons:
        out[f"fwd_{horizon}d"] = price.shift(-horizon) / price - 1.0
    return out


def distribution_stats(values: list[float], quantiles: list[float]) -> dict[str, Any]:
    """Mean/median/lower-quantile summary of a return sample."""
    import numpy as np

    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "quantiles": {f"p{int(q * 100)}": None for q in quantiles},
        }
    arr = np.asarray(values, dtype=float)
    return {
        "count": int(arr.size),
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
        "quantiles": {
            f"p{int(q * 100)}": float(np.quantile(arr, q)) for q in quantiles
        },
    }


def permutation_pvalue(
    flagged: list[float],
    rest: list[float],
    iterations: int,
    seed: int,
) -> float | None:
    """One-sided permutation test: P(mean(flagged) - mean(rest) <= observed).

    Small p = flagged days have significantly lower forward returns (the
    score discriminates). Implemented directly on numpy — scipy is not a
    declared project dependency.
    """
    import numpy as np

    if not flagged or not rest:
        return None
    flagged_arr = np.asarray(flagged, dtype=float)
    rest_arr = np.asarray(rest, dtype=float)
    observed = flagged_arr.mean() - rest_arr.mean()
    pooled = np.concatenate([flagged_arr, rest_arr])
    n_flagged = flagged_arr.size
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(iterations):
        rng.shuffle(pooled)
        diff = pooled[:n_flagged].mean() - pooled[n_flagged:].mean()
        if diff <= observed:
            hits += 1
    return float((hits + 1) / (iterations + 1))


def threshold_analysis(
    merged: Any,
    *,
    score_column: str,
    degraded_column: str,
    settings: ValidationSettings,
) -> list[dict[str, Any]]:
    """Flagged-vs-all forward-return comparison per (threshold, horizon).

    ``merged`` must contain the score/degraded columns plus ``fwd_{h}d``
    columns from :func:`compute_forward_returns`.
    """
    results: list[dict[str, Any]] = []
    for threshold in settings.thresholds:
        for horizon in settings.horizons_days:
            column = f"fwd_{horizon}d"
            flagged: list[float] = []
            rest: list[float] = []
            for record in merged.to_dict(orient="records"):
                ret = record.get(column)
                if is_missing(ret):
                    continue
                score = record.get(score_column)
                degraded = record.get(degraded_column)
                degraded_flag = bool(degraded) if not is_missing(degraded) else False
                usable_score = not is_missing(score) and not (
                    settings.exclude_degraded and degraded_flag
                )
                if usable_score and float(score) >= threshold:
                    flagged.append(float(ret))
                else:
                    rest.append(float(ret))
            everyone = flagged + rest
            flagged_stats = distribution_stats(flagged, settings.lower_quantiles)
            all_stats = distribution_stats(everyone, settings.lower_quantiles)
            delta_mean = (
                flagged_stats["mean"] - all_stats["mean"]
                if flagged_stats["mean"] is not None and all_stats["mean"] is not None
                else None
            )
            results.append(
                {
                    "threshold": float(threshold),
                    "horizon_days": int(horizon),
                    "flagged": flagged_stats,
                    "all": all_stats,
                    "delta_mean": delta_mean,
                    "p_value_one_sided": permutation_pvalue(
                        flagged,
                        rest,
                        settings.permutation_iterations,
                        settings.permutation_seed,
                    ),
                }
            )
    return results


# ---------------------------------------------------------------------------
# Band stability / flapping (O7)
# ---------------------------------------------------------------------------


def band_runs(bands: list[Any]) -> list[tuple[str, int]]:
    """Run-length encode the band sequence, dropping missing values."""
    runs: list[tuple[str, int]] = []
    for band in bands:
        if is_missing(band) or str(band).strip() == "":
            continue
        label = str(band)
        if runs and runs[-1][0] == label:
            runs[-1] = (label, runs[-1][1] + 1)
        else:
            runs.append((label, 1))
    return runs


def flapping_metrics(
    bands: list[Any], round_trip_pairs: list[list[str]]
) -> dict[str, Any]:
    """Transition counts, per-band dwell distribution, and X->Y->X round trips."""
    import numpy as np

    runs = band_runs(bands)
    observed_days = sum(length for _, length in runs)
    transitions = max(len(runs) - 1, 0)

    dwell: dict[str, list[int]] = {}
    for label, length in runs:
        dwell.setdefault(label, []).append(length)
    dwell_stats = {
        label: {
            "runs": len(lengths),
            "mean_days": float(np.mean(lengths)),
            "median_days": float(np.median(lengths)),
            "min_days": int(min(lengths)),
            "max_days": int(max(lengths)),
        }
        for label, lengths in sorted(dwell.items())
    }

    round_trips: dict[str, int] = {}
    labels = [label for label, _ in runs]
    for pair in round_trip_pairs:
        if len(pair) != 2:
            continue
        a, b = str(pair[0]), str(pair[1])
        count = sum(
            1
            for i in range(len(labels) - 2)
            if labels[i] == labels[i + 2]
            and {labels[i], labels[i + 1]} == {a, b}
            and labels[i] != labels[i + 1]
        )
        round_trips[f"{a}<->{b}"] = count

    return {
        "observed_days": observed_days,
        "transitions": transitions,
        "transitions_per_20d": (
            float(transitions / observed_days * 20.0) if observed_days else None
        ),
        "dwell": dwell_stats,
        "round_trips": round_trips,
    }


# ---------------------------------------------------------------------------
# Episode replay
# ---------------------------------------------------------------------------


def _row_view(record: dict[str, Any], settings: ValidationSettings) -> dict[str, Any]:
    view: dict[str, Any] = {"trade_date": str(record.get("trade_date"))}
    for key, column in (
        ("score", None),
        ("band", settings.band_column),
        ("regime", settings.regime_column),
        ("degraded", settings.degraded_column),
        ("coverage_ratio", settings.coverage_column),
    ):
        if key == "score":
            score = next(
                (
                    record.get(name)
                    for name in settings.score_columns
                    if not is_missing(record.get(name))
                ),
                None,
            )
            view["score"] = float(score) if score is not None else None
            continue
        value = record.get(column)
        if key == "degraded":
            view[key] = bool(value) if not is_missing(value) else None
        elif key == "coverage_ratio":
            view[key] = float(value) if not is_missing(value) else None
        else:
            view[key] = str(value) if not is_missing(value) else None
    return view


def episode_rows(
    close_frame: Any,
    premarket_frame: Any,
    settings: ValidationSettings,
) -> list[dict[str, Any]]:
    """Score state before/at each configured crash episode date."""
    close_records = (
        close_frame.to_dict(orient="records") if close_frame is not None else []
    )
    premarket_records = (
        premarket_frame.to_dict(orient="records")
        if premarket_frame is not None and not getattr(premarket_frame, "empty", True)
        else []
    )
    rows: list[dict[str, Any]] = []
    for episode in settings.episodes:
        episode_day = date.fromisoformat(str(episode))
        prior = [
            record
            for record in close_records
            if record.get("trade_date") is not None
            and record["trade_date"] < episode_day
        ]
        prior_view = _row_view(prior[-1], settings) if prior else None
        premarket = next(
            (
                record
                for record in premarket_records
                if record.get("trade_date") == episode_day
            ),
            None,
        )
        same_close = next(
            (
                record
                for record in close_records
                if record.get("trade_date") == episode_day
            ),
            None,
        )
        rows.append(
            {
                "episode": str(episode),
                "prior_close": prior_view,
                "premarket": (
                    _row_view(premarket, settings) if premarket is not None else None
                ),
                "close": (
                    _row_view(same_close, settings) if same_close is not None else None
                ),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:+.2f}%"


def _num(value: float | None, fmt: str = "{:.1f}") -> str:
    return "n/a" if value is None else fmt.format(value)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Market Risk Score — hindsight validation (§4.4)",
        "",
        f"- generated_at_kst: {report['generated_at_kst']}",
        f"- data range: {report['data_start']} .. {report['data_end']}"
        f" ({report['close_rows']} close rows, {report['scored_rows']} scored)",
        f"- score column: `{report['score_column']}`"
        f" / price column: `{report['price_column']}`",
        "",
        "## Threshold discrimination (forward KOSPI returns)",
        "",
        "| threshold | horizon | n flagged | mean flagged | mean all |"
        " median flagged | median all | Δmean | perm p (1-sided) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in report["discrimination"]:
        lines.append(
            f"| >= {row['threshold']:.0f} | {row['horizon_days']}d"
            f" | {row['flagged']['count']}"
            f" | {_pct(row['flagged']['mean'])} | {_pct(row['all']['mean'])}"
            f" | {_pct(row['flagged']['median'])} | {_pct(row['all']['median'])}"
            f" | {_pct(row['delta_mean'])}"
            f" | {_num(row['p_value_one_sided'], '{:.4f}')} |"
        )
    lines += ["", "Lower-tail quantiles (flagged / all):", ""]
    for row in report["discrimination"]:
        quantiles = ", ".join(
            f"{name}: {_pct(row['flagged']['quantiles'][name])}"
            f" / {_pct(row['all']['quantiles'][name])}"
            for name in row["flagged"]["quantiles"]
        )
        lines.append(
            f"- >= {row['threshold']:.0f} @ {row['horizon_days']}d — {quantiles}"
        )

    flapping = report["flapping"]
    lines += [
        "",
        "## Band stability / flapping (O7)",
        "",
        f"- observed band days: {flapping['observed_days']}",
        f"- transitions: {flapping['transitions']}"
        f" ({_num(flapping['transitions_per_20d'], '{:.2f}')} per 20 trading days)",
        f"- round trips: {flapping['round_trips'] or 'n/a'}",
        "",
        "| band | runs | mean dwell | median dwell | min | max |",
        "|---|---|---|---|---|---|",
    ]
    for band, stats in flapping["dwell"].items():
        lines.append(
            f"| {band} | {stats['runs']} | {stats['mean_days']:.1f}d"
            f" | {stats['median_days']:.1f}d | {stats['min_days']}d"
            f" | {stats['max_days']}d |"
        )

    lines += [
        "",
        "## Episode replay (score before the drop)",
        "",
        "| episode | prior close score/band | premarket score/band |"
        " close score/band |",
        "|---|---|---|---|",
    ]
    for row in report["episodes"]:

        def cell(view: dict[str, Any] | None) -> str:
            if view is None:
                return "missing"
            return f"{_num(view['score'])} / {view['band'] or 'n/a'}"

        lines.append(
            f"| {row['episode']} | {cell(row['prior_close'])}"
            f" | {cell(row['premarket'])} | {cell(row['close'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_report(
    close_frame: Any,
    premarket_frame: Any,
    settings: ValidationSettings,
) -> dict[str, Any] | None:
    """Assemble the full report dict, or ``None`` when data is insufficient."""
    if close_frame is None or getattr(close_frame, "empty", True):
        return None
    score_column = first_present_column(close_frame, settings.score_columns)
    price_column = first_present_column(close_frame, settings.price_columns)
    if score_column is None or price_column is None:
        return None

    forward = compute_forward_returns(close_frame, price_column, settings.horizons_days)
    keep = [
        column
        for column in {
            "trade_date",
            score_column,
            settings.band_column,
            settings.degraded_column,
        }
        if column in close_frame.columns
    ]
    merged = forward.merge(close_frame[keep], on="trade_date", how="left")
    if settings.degraded_column not in merged.columns:
        merged[settings.degraded_column] = None

    scored_rows = sum(1 for v in close_frame[score_column] if not is_missing(v))
    bands = (
        list(close_frame[settings.band_column])
        if settings.band_column in close_frame.columns
        else []
    )

    return {
        "status": "ok",
        "generated_at_kst": datetime.now(KST).isoformat(),
        "data_start": str(close_frame["trade_date"].iloc[0]),
        "data_end": str(close_frame["trade_date"].iloc[-1]),
        "close_rows": int(len(close_frame)),
        "scored_rows": int(scored_rows),
        "score_column": score_column,
        "price_column": price_column,
        "exclude_degraded": settings.exclude_degraded,
        "discrimination": threshold_analysis(
            merged,
            score_column=score_column,
            degraded_column=settings.degraded_column,
            settings=settings,
        ),
        "flapping": flapping_metrics(bands, settings.flapping_round_trip_pairs),
        "episodes": episode_rows(close_frame, premarket_frame, settings),
    }


def write_reports(
    report: dict[str, Any], out_dir: Path, tag: str | None
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = tag or datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"market_risk_validation_{stamp}.json"
    md_path = out_dir / f"market_risk_validation_{stamp}.md"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return md_path, json_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Hindsight validation report for the Market Risk Score."
    )
    ap.add_argument("--config", default=None, help="market_risk_validation.yaml path")
    ap.add_argument(
        "--parquet-root",
        default=None,
        help="market-data parquet root override (default: config/storage.yaml)",
    )
    ap.add_argument("--start", default=None, help="start trade date (YYYY-MM-DD)")
    ap.add_argument("--end", default=None, help="end trade date (YYYY-MM-DD)")
    ap.add_argument("--out-dir", default=None, help="report dir override")
    ap.add_argument("--tag", default=None, help="report filename tag")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    settings = MarketRiskValidationConfig.load_or_default(args.config).validation

    store = build_store(args.parquet_root)
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    close_frame = load_snapshot_frame(store, "close", start, end)
    premarket_frame = load_snapshot_frame(store, "premarket", start, end)

    report = build_report(close_frame, premarket_frame, settings)
    if report is None:
        print(
            f"{INSUFFICIENT_DATA}: no scored close rows found"
            f" (need columns {settings.score_columns} + {settings.price_columns};"
            " run the backfill and the hindcast --write first)"
        )
        return 0

    out_dir = Path(args.out_dir) if args.out_dir else Path(settings.report_dir)
    md_path, json_path = write_reports(report, out_dir, args.tag)
    print(render_markdown(report))
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
