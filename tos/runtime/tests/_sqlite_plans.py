"""Shared sqlite query-plan probe for tests that pin HOW a statement is served, not just
what it returns.

A one-row read that happens to be served by a full table scan returns exactly the right
row while keeping the cost the change was made to remove, so some reads are pinned by
their PLAN. Both pins of that kind (``tos/runtime/tests/evidence/test_store.py`` and
``tos/runtime/tests/riskstate/test_flow_observation.py``, evidence growth plan §2 A2-b)
use this one helper rather than each carrying a copy: the ``?``-counting rule below and
the ``row[3]`` column of ``EXPLAIN QUERY PLAN`` are sqlite details that have to change
together everywhere when they change at all.

This lives at the tests ROOT, next to ``conftest.py``, precisely so neither suite imports
from the other's ``conftest`` — the cross-suite import the riskstate/venue conftests
forbid. It is a plain module, not a fixture, because the probe takes a callable and the
store under test differs per suite.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable

#: A single-quoted sqlite string literal, ``''`` escapes included. Stripped before counting
#: placeholders — see :func:`_placeholder_count`.
_SQL_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")


def _placeholder_count(sql: str) -> int:
    """How many parameters ``sql`` still needs — bare ``?`` only, never one inside a string
    literal.

    CPython hands the trace callback the EXPANDED statement, with every parameter already
    substituted, so the usual count is ``0``. A naive ``sql.count("?")`` would then count
    the ``?`` characters INSIDE a substituted value — a ``kind`` or a payload such as
    ``{"q": "why?"}`` — and re-execute the explain with bindings the statement has no slots
    for, failing with ``sqlite3.ProgrammingError: Incorrect number of bindings`` for a
    reason that has nothing to do with the plan under test. Stripping quoted literals first
    counts only real placeholders, and still binds correctly if a future CPython traces the
    unexpanded form instead.
    """
    return _SQL_STRING_LITERAL.sub("", sql).count("?")


def query_plans(
    connection: sqlite3.Connection, table: str, run: Callable[[], object]
) -> list[str]:
    """Every query plan sqlite chose for the ``table``-reading statements ``run`` issues on
    ``connection``.

    The statements are captured with ``sqlite3.Connection.set_trace_callback`` — the real
    statements the code under test executed, never a literal copy restated in the test,
    so the pin cannot pass while the production path does something else — and re-planned
    with ``EXPLAIN QUERY PLAN`` once tracing is off, so the explain itself is not traced.

    Returns the plan detail strings (``EXPLAIN QUERY PLAN``'s 4th column), e.g.
    ``SEARCH entries USING INTEGER PRIMARY KEY (rowid=?)`` or ``SCAN entries``. An empty
    list means ``run`` touched ``table`` not at all — callers assert against that, so a
    mutation that stops reading cannot pass the pin vacuously.
    """
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
