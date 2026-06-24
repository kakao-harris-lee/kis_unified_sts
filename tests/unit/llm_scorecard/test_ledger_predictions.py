# tests/unit/llm_scorecard/test_ledger_predictions.py
import tempfile, os
from shared.storage.runtime_ledger import SQLiteRuntimeLedger


def _ledger():
    d = tempfile.mkdtemp()
    return SQLiteRuntimeLedger(os.path.join(d, "t.db"))


def test_prediction_upsert_idempotent():
    l = _ledger()
    l.save_prediction("2026-06-25", "direction", "2026-06-25T08:40:00+09:00", {"dir": "BULL"}, 0.7)
    l.save_prediction("2026-06-25", "direction", "2026-06-25T08:41:00+09:00", {"dir": "BEAR"}, 0.6)
    rows = l.load_predictions("2026-06-25")
    assert len(rows) == 1 and rows[0]["payload"]["dir"] == "BEAR"


def test_score_upsert_and_query():
    l = _ledger()
    l.save_score({"date_kst": "2026-06-25", "facet": "direction", "correct": True,
                  "value": 0.8, "economic_proxy": 0.8, "baseline_value": 0.0,
                  "edge": 0.8, "detail": {"realized": 0.8}, "scored_at": "2026-06-25T16:00:00+09:00"})
    rows = l.query_scores(facet="direction")
    assert len(rows) == 1 and rows[0]["correct"] is True and rows[0]["edge"] == 0.8
