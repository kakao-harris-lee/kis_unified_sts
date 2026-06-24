# tests/unit/llm_scorecard/test_outcome_data.py
import pandas as pd
from datetime import datetime
from shared.llm_scorecard.outcome_data import OutcomeData


class _Store:
    def __init__(self, df): self._df = df
    def get_minute_bars(self, symbol, start=None, end=None): return self._df


def _df():
    idx = pd.to_datetime(["2026-06-25 08:50","2026-06-25 09:00","2026-06-25 15:20"])
    return pd.DataFrame({"open":[100,101,109],"close":[100,101,110]}, index=idx)


def test_session_return_excludes_pre_capture_bars():
    od = OutcomeData(_Store(_df()), now_kst=datetime(2026,6,25,16,0))
    cap = datetime(2026,6,25,8,55)  # after 08:50 pre-market print
    r = od.session_return("X", "2026-06-25", cap)
    assert round(r, 2) == round((110-101)/101*100, 2)  # open=101 (09:00), close=110


def test_missing_data_returns_none():
    class Empty:
        def get_minute_bars(self, *a, **k): return None
    assert OutcomeData(Empty(), now_kst=datetime(2026,6,25,16,0)).session_return("X","2026-06-25",datetime(2026,6,25,8,55)) is None
