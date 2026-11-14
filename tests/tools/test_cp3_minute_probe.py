"""Hermetic canaries for the two surviving CP-3 bar-frame helpers.

PR-1's quotation capture (recorder, seeding/benchmark/sample drivers, parser
comparison, CLI) was deleted 2026-11-13 once its measurement was finished, and
its tests went with it. What is left in ``tools/tos_cp3/minute_probe.py`` is
``frame`` and ``seed_capacity``, which the **live daily path** imports — so
they keep a test.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

from tools.tos_cp3 import minute_probe as p


def test_seed_capacity_excludes_first_session_and_off_window():
    rows = []
    for d in (6, 7, 8, 12):
        for minute in range(420):
            stamp = datetime(2026, 10, d, 8, 45) + timedelta(minutes=minute)
            rows.append(("A05611", stamp, 100, 100, 100, 100, 20))
    strategy = SimpleNamespace(
        entry_config=SimpleNamespace(
            valid_minutes_min=15, no_entry_after_minutes_since_open=345
        )
    )
    assert (
        p.seed_capacity(p.frame(rows), strategy, SimpleNamespace(hour=8, minute=45))
        == 993
    )
    assert (
        p.seed_capacity(
            p.frame(rows[:1260]), strategy, SimpleNamespace(hour=8, minute=45)
        )
        == 662
    )


def test_frame_sorts_by_timestamp_and_keeps_the_column_order():
    """``frame`` is the shape every CP-3 caller builds; order is load-bearing.

    Concrete failing input: the live producer appends a late-arriving bar after
    a later one (``stitch_seed`` shifts a seed day onto the session's), and a
    frame that kept insertion order would hand the producer a backwards series.
    """
    late = datetime(2026, 10, 12, 9, 2)
    early = datetime(2026, 10, 12, 9, 0)
    df = p.frame(
        [
            ("A05611", late, 2, 2, 2, 2, 20),
            ("A05611", early, 1, 1, 1, 1, 10),
        ]
    )
    assert list(df.columns) == p.COLUMNS
    assert list(df.timestamp) == [early, late]
    assert list(df.index) == [0, 1]
