from __future__ import annotations


def rolling_metrics(scores: list[dict], window: int) -> dict:
    """Pure rolling metrics over a window of score rows (most-recent ``window``).

    Public module-level API consumed by the reporter/cron (Task 9) and Phase 3/4.

    - ``n``: total rows in the window.
    - ``n_scored``: rows with a non-None ``correct`` (unscorable rows excluded).
    - ``hit_rate``: hits / ``n_scored`` (None when nothing is scorable).
    - ``mean_edge``: mean ``edge`` over ALL rows in the window.
    - ``econ_proxy_sum``: sum of ``economic_proxy`` over all rows.
    """
    rows = scores[-window:] if window else list(scores)
    scored = [r for r in rows if r.get("correct") is not None]
    hits = sum(1 for r in scored if r["correct"])
    edges = [r.get("edge", 0.0) for r in rows]
    return {
        "n": len(rows),
        "n_scored": len(scored),
        "hit_rate": (hits / len(scored)) if scored else None,
        "mean_edge": (sum(edges) / len(edges)) if edges else 0.0,
        "econ_proxy_sum": sum(r.get("economic_proxy", 0.0) for r in rows),
    }


def calibration_bins(scores: list[dict], pred_conf: dict, n_bins: int = 5) -> list[dict]:
    """Pure confidence-calibration bins.

    ``pred_conf`` maps ``date_kst -> confidence``. Returns one entry per bin with
    ``lo``, ``hi``, ``n`` (scorable members), and ``hit_rate`` (None if empty).
    """
    edges = [(i / n_bins, (i + 1) / n_bins) for i in range(n_bins)]
    out: list[dict] = []
    for lo, hi in edges:
        members = [
            s
            for s in scores
            if s.get("correct") is not None
            and lo <= (pred_conf.get(s["date_kst"], -1)) < (hi if hi < 1 else 1.01)
        ]
        hr = (sum(1 for s in members if s["correct"]) / len(members)) if members else None
        out.append({"lo": lo, "hi": hi, "n": len(members), "hit_rate": hr})
    return out
