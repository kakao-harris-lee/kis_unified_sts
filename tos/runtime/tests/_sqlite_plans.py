"""Shared sqlite query-plan probe for tests that pin HOW a statement is served, not just"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable

_SQL_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")


def _placeholder_count(sql: str) -> int:
    """How many parameters ``sql`` still needs — bare ``?`` only, never one inside a string"""
    return _SQL_STRING_LITERAL.sub("", sql).count("?")


def query_plans(
    connection: sqlite3.Connection, table: str, run: Callable[[], object]
) -> list[str]:
    """Every query plan sqlite chose for the ``table``-reading statements ``run`` issues on"""
    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    try:
        run()
    finally:
        connection.set_trace_callback(None)

    needle = f"from {table}".lower()
    plans: list[str] = []
    for sql in statements:
        if needle not in sql.lower():
            continue
        rows = connection.execute(
            "EXPLAIN QUERY PLAN " + sql, [None] * _placeholder_count(sql)
        ).fetchall()
        plans.extend(str(row[3]) for row in rows)
    return plans
