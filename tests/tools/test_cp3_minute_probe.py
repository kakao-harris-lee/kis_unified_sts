"""Hermetic canaries for the PR-1 quotation capture. No real credentials/network."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from tools.broker_probes.common import SafetyViolation, assert_read_only_call
from tools.tos_cp3 import minute_probe as p

DAY = date(2026, 10, 12)


def row(hour, close="100", volume="20", day="20261012"):
    return {
        "stck_bsop_date": day,
        "stck_cntg_hour": hour,
        "futs_oprc": close,
        "futs_hgpr": close,
        "futs_lwpr": close,
        "futs_prpr": close,
        "cntg_vol": volume,
    }


def test_no_network_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        p.httpx.Client,
        "__init__",
        lambda *a, **k: pytest.fail("network client created"),
    )
    assert (
        p.main(["--config", str(p.ROOT / "config/tos_probes/cp3-pr1-20261012.yaml")])
        == 0
    )
    assert '"mode": "DRY_RUN"' in capsys.readouterr().out


@pytest.mark.parametrize(
    "method,path,tr",
    [
        ("POST", p.QUOTE_PATH, p.TR),
        ("GET", "/uapi/domestic-futureoption/v1/trading/order", p.TR),
        ("GET", p.QUOTE_PATH, "TTTO1101U"),
    ],
)
def test_mutations_rejected_before_transport(method, path, tr):
    with pytest.raises(SafetyViolation):
        assert_read_only_call(method, p.REAL_BASE_URL + path, tr, p.ALLOWLIST)


def test_wrong_day_raw_successor_does_not_count():
    assert p.raw_stamp(row("090000", day="20261008"), DAY) is None
    assert p.raw_stamp(row("090000", volume="0"), DAY).hour == 9
    assert len(p.select_day([row("090000"), row("090100", day="20261008")], DAY)) == 1


def test_parser_comparison_exposes_singleton_phantom():
    rows = [row("090000"), row("090100", "100.1"), row("090200", "900")]
    result = p.parser_comparison(rows, DAY, "A05611")
    assert result["full_rows"] == 2
    assert result["incremental_rows"] == 3
    assert result["different_minutes"] == ["2026-10-12T09:02:00"]


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


def test_history_capped_refuses_incomplete_data():
    quote = p.Quotes.__new__(p.Quotes)
    quote.cfg = {"max_pages": 2}
    pages = iter([[row("090300")], [row("090200")]])
    quote.page = lambda *a: next(pages)
    with pytest.raises(RuntimeError, match="pagination capped"):
        quote.history("A05611", DAY)


def test_history_repeated_cursor_stops_and_filters_other_days():
    quote = p.Quotes.__new__(p.Quotes)
    quote.cfg = {"max_pages": 20}
    pages = iter(
        [[row("090300"), row("090200")], [row("090200"), row("090000", day="20261008")]]
    )
    quote.page = lambda *a: next(pages)
    result = quote.history("A05611", DAY)
    assert len(result) == 3
    assert all(p.raw_stamp(r, DAY) for r in result)


def test_output_never_reuses_previous_capture(tmp_path):
    rec = p.Recorder(tmp_path / "capture")
    rec.event({"orders": 0})
    rec.finish()
    import hashlib
    import json

    digest = json.loads((rec.output / "sha256.json").read_text())
    assert (
        digest["requests.jsonl"]
        == hashlib.sha256((rec.output / "requests.jsonl").read_bytes()).hexdigest()
    )
    with pytest.raises(FileExistsError):
        p.Recorder(tmp_path / "capture")


@pytest.mark.parametrize("seed_failure", [False, True])
def test_confirmed_flow_with_fake_transport(tmp_path, monkeypatch, seed_failure):
    import json

    import yaml

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 12, 8, 45, tzinfo=p.KST)

    class FakeQuotes:
        calls = 0
        http = SimpleNamespace(close=lambda: None)

        def __init__(self, *args):
            pass

        def history(self, symbol, day):
            assert symbol == "A05611"
            return [row("090000")]

    cfg = yaml.safe_load(
        (p.ROOT / "config/tos_probes/cp3-pr1-20261012.yaml").read_text()
    )
    cfg["env_file"] = str(tmp_path / "env")
    cfg["output"] = str(tmp_path / "capture")
    (tmp_path / "env").write_text(
        "KIS_FUTURES_APP_KEY=fake\nKIS_FUTURES_APP_SECRET=fake\n"
    )
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(cfg))
    monkeypatch.setattr(p, "datetime", Clock)
    monkeypatch.setattr(p, "Quotes", FakeQuotes)
    monkeypatch.setattr(
        p,
        "sample",
        lambda *a: (
            [],
            [
                {
                    "boundary_kst": "08:46",
                    "successor_present": True,
                    "delay_upper_s": 1.1,
                }
            ],
        ),
    )
    monkeypatch.setattr(p, "seed_and_compare", lambda *a: (p.frame([]), None, None))
    monkeypatch.setattr(p, "benchmark", lambda *a: {"max_s": 0.1})
    if seed_failure:

        def fail_seed(*args):
            raise RuntimeError("seed density below gate")

        monkeypatch.setattr(p, "seed_and_compare", fail_seed)
        with pytest.raises(RuntimeError, match="probe aborted"):
            p.main(["--config", str(config), "--confirm"])
        assert (tmp_path / "capture/abort.json").exists()
        assert (tmp_path / "capture/m4-today-parser.json").exists()
        assert not (tmp_path / "capture/completion.json").exists()
    else:
        assert p.main(["--config", str(config), "--confirm"]) == 0
        assert (tmp_path / "capture/completion.json").exists()
    summary = json.loads((tmp_path / "capture/summary.json").read_text())
    assert summary["seen_successors"] == 1
    assert summary["orders"] == 0
    assert (tmp_path / "capture/sha256.json").exists()
