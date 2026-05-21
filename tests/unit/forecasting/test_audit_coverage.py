import datetime as dt
import importlib.util
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "afc", _REPO / "scripts" / "audit_forecast_coverage.py")
afc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(afc)


class _FakeClient:
    def __init__(self, vol_rows, event_rows):
        self.vol_rows = vol_rows
        self.event_rows = event_rows
    def execute(self, sql, params=None):  # noqa: ARG002
        if "vol_forecasts" in sql:
            return self.vol_rows
        if "event_scores" in sql:
            return self.event_rows
        return []


def test_coverage_full(monkeypatch):
    # 60 minutes × 1 trading minute each → 100% live coverage
    rows = [(60, 60, 0)]  # (total, live_count, recompute_count)
    monkeypatch.setattr(afc, "_get_client", lambda: _FakeClient(rows, [(0,)]))
    r = afc.audit_window(
        start=dt.datetime(2026, 4, 1, 0, 0), end=dt.datetime(2026, 4, 1, 1, 0))
    assert r["vol_total"] == 60
    assert r["vol_live"] == 60
    assert r["vol_recompute"] == 0
    assert r["event_total"] == 0


def test_coverage_recompute_only(monkeypatch):
    rows = [(60, 0, 60)]
    monkeypatch.setattr(afc, "_get_client", lambda: _FakeClient(rows, [(5,)]))
    r = afc.audit_window(
        start=dt.datetime(2025, 9, 1, 0, 0), end=dt.datetime(2025, 9, 1, 1, 0))
    assert r["vol_live"] == 0
    assert r["vol_recompute"] == 60
    assert r["event_total"] == 5


def test_main_ok_when_no_check(capsys, monkeypatch):
    monkeypatch.setattr(
        afc, "_get_client",
        lambda: _FakeClient([(60, 30, 30)], [(2,)]))
    rc = afc.main(["--start", "2026-04-01", "--end", "2026-04-02"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no-check" in out
    assert "vol_forecasts" in out


def test_main_insufficient_returns_1(capsys, monkeypatch):
    # 60 vol rows / 1000 expected = 6% << 90% min → exit 1
    monkeypatch.setattr(
        afc, "_get_client",
        lambda: _FakeClient([(60, 60, 0)], [(0,)]))
    rc = afc.main([
        "--start", "2026-04-01", "--end", "2026-04-02",
        "--expected-trading-minutes", "1000"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "insufficient" in out


def test_main_ok_when_above_threshold(capsys, monkeypatch):
    # 60 / 50 = 120% well above 90% → exit 0 / "ok"
    monkeypatch.setattr(
        afc, "_get_client",
        lambda: _FakeClient([(60, 60, 0)], [(0,)]))
    rc = afc.main([
        "--start", "2026-04-01", "--end", "2026-04-02",
        "--expected-trading-minutes", "50"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "VERDICT: ok" in out
    assert "no-check" not in out
