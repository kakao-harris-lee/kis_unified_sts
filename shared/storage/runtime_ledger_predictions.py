"""Prediction and score methods for RuntimeLedger."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .runtime_ledger_helpers import (
    _utc_now_iso,
)


class RuntimeLedgerPredictionMixin:
    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        payload = data.get("payload_json")
        if isinstance(payload, str):
            try:
                data["payload"] = json.loads(payload)
            except json.JSONDecodeError:
                data["payload"] = {}
        return data

    def save_prediction(
        self,
        date_kst: str,
        facet: str,
        captured_at: str,
        payload: dict,
        confidence: float | None,
    ) -> None:
        """Idempotent upsert of an LLM prediction (per date_kst+facet)."""
        with self._lock:
            self._require_conn().execute(
                "INSERT INTO llm_predictions(date_kst,facet,captured_at,payload_json,confidence,created_at)"
                " VALUES(?,?,?,?,?,?)"
                " ON CONFLICT(date_kst,facet) DO UPDATE SET"
                " captured_at=excluded.captured_at, payload_json=excluded.payload_json,"
                " confidence=excluded.confidence",
                (
                    date_kst,
                    facet,
                    captured_at,
                    json.dumps(payload),
                    confidence,
                    _utc_now_iso(),
                ),
            )
            self._require_conn().commit()

    def load_predictions(self, date_kst: str) -> list[dict]:
        """Return all LLM predictions recorded for the given trading date (KST)."""
        with self._lock:
            rows = (
                self._require_conn()
                .execute("SELECT * FROM llm_predictions WHERE date_kst=?", (date_kst,))
                .fetchall()
            )
        return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]

    def query_predictions(
        self,
        facet: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        """Query LLM predictions with optional facet and date range filters.

        Mirrors query_scores but reads from llm_predictions. Rows include a
        ``payload`` key with the deserialized JSON payload.
        """
        q = "SELECT * FROM llm_predictions WHERE 1=1"
        p: list = []
        if facet:
            q += " AND facet=?"
            p.append(facet)
        if start:
            q += " AND date_kst>=?"
            p.append(start)
        if end:
            q += " AND date_kst<=?"
            p.append(end)
        q += " ORDER BY date_kst ASC"
        with self._lock:
            rows = self._require_conn().execute(q, p).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]

    def save_score(self, s: dict) -> None:
        """Idempotent upsert of a prediction score (per date_kst+facet)."""
        correct = None if s["correct"] is None else (1 if s["correct"] else 0)
        with self._lock:
            self._require_conn().execute(
                "INSERT INTO prediction_scores(date_kst,facet,correct,value,economic_proxy,"
                "baseline_value,edge,detail_json,scored_at) VALUES(?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(date_kst,facet) DO UPDATE SET correct=excluded.correct,"
                " value=excluded.value, economic_proxy=excluded.economic_proxy,"
                " baseline_value=excluded.baseline_value, edge=excluded.edge,"
                " detail_json=excluded.detail_json, scored_at=excluded.scored_at",
                (
                    s["date_kst"],
                    s["facet"],
                    correct,
                    s["value"],
                    s["economic_proxy"],
                    s["baseline_value"],
                    s["edge"],
                    json.dumps(s["detail"]),
                    s["scored_at"],
                ),
            )
            self._require_conn().commit()

    def query_scores(
        self, facet: str | None = None, start: str | None = None, end: str | None = None
    ) -> list[dict]:
        """Query prediction scores with optional facet and date range filters."""
        q = "SELECT * FROM prediction_scores WHERE 1=1"
        p: list = []
        if facet:
            q += " AND facet=?"
            p.append(facet)
        if start:
            q += " AND date_kst>=?"
            p.append(start)
        if end:
            q += " AND date_kst<=?"
            p.append(end)
        q += " ORDER BY date_kst ASC"
        with self._lock:
            rows = self._require_conn().execute(q, p).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["detail"] = json.loads(d.pop("detail_json"))
            d["correct"] = None if d["correct"] is None else bool(d["correct"])
            out.append(d)
        return out
