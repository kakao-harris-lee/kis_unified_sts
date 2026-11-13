"""CP-3 bar-frame helpers shared by the live producer and B1a.

**What this module was and what is left.** It was PR-1's real quotation GET
measurement probe (evidence
``docs/broker-profiles/evidence/2026-10-12-cp3-pr1-minute-probe/``). That
measurement is finished, so 2026-11-13 deleted the probe half — the recorder,
the seeding/benchmark/sample campaign drivers, the parser comparison and the
CLI — along with the KIS credential, Parquet-store and legacy-driver imports
only they needed. Its transport was already extracted to
:mod:`tools.tos_cp3.quote_client` (PR-2, #894), which the live producer uses
directly.

What remains are the two pure helpers the **live daily path** imports — the
DataFrame shape (:func:`frame`) and the seed-window count
(:func:`seed_capacity`) — read by
``tools/tos_cp3/live_producer/{frame,stitch_seed,producer}.py`` and
``tools/tos_cp3/fields_equivalence.py``. The module keeps its name so those
imports are untouched; renaming it waits until the P2-c producer switch
(#1067/#1068) has landed, so this removal does not rebase those branches.
"""

from __future__ import annotations

import pandas as pd

from tools.tos_cp3.produce_fields import OpenAnchor, StrategyInputs

#: The bar-frame column order every CP-3 caller builds and reads.
COLUMNS = ["code", "timestamp", "open", "high", "low", "close", "volume"]

__all__ = ["COLUMNS", "frame", "seed_capacity"]


def frame(rows: list[tuple]) -> pd.DataFrame:
    return (
        pd.DataFrame(rows, columns=COLUMNS)
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


def seed_capacity(
    df: pd.DataFrame, strategy: StrategyInputs, anchor: OpenAnchor
) -> int:
    """First session cannot advance check's window without a previous close."""
    if df.empty:
        return 0
    dates = sorted(set(df.timestamp.dt.date))
    minutes = (
        df.timestamp.dt.hour * 60
        + df.timestamp.dt.minute
        - (anchor.hour * 60 + anchor.minute)
    )
    cfg = strategy.entry_config
    return int(
        (
            (df.timestamp.dt.date != dates[0])
            & (minutes >= cfg.valid_minutes_min)
            & (minutes <= cfg.no_entry_after_minutes_since_open)
        ).sum()
    )
