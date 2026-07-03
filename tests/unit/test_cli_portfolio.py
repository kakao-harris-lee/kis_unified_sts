"""Unit tests for `sts portfolio` (Phase 5A Track A manual-ledger CLI).

Hermetic: tmp_path core-holdings YAML (via --config absolute path, bypassing
ConfigLoader global state) + tmp_path SQLite ledger (via --ledger-path).
Pins that the CLI records and displays ONLY — it never places orders and
never rewrites the operator-authored YAML (valuations go to the sidecar).
"""

from __future__ import annotations

import pytest
import yaml
from click.testing import CliRunner

from cli.main import cli
from shared.storage.runtime_ledger import SQLiteRuntimeLedger


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def core_yaml(tmp_path):
    data = {
        "sectors": {
            "defense": {"label": "방산", "target_weight": 0.35},
            "semiconductor_equipment": {"label": "반도체 장비", "target_weight": 0.35},
            "robotics": {"label": "로보틱스", "target_weight": 0.15},
            "cash": {"label": "현금 버퍼", "target_weight": 0.15},
        },
        "rebalancing": {"drift_threshold_pct": 0.10, "single_holding_max": 0.25},
        "cash_krw": 1_500_000,
        "holdings": [
            {
                "symbol": "012450",
                "name": "한화에어로스페이스",
                "sector": "defense",
                "thesis": "수주잔고 확정형",
                "kill_criteria": ["수주잔고 감소"],
                "shares": 10,
                "avg_price": 900_000,
                "last_valuation": {"date": "2026-07-01", "price": 1_000_000},
            }
        ],
        "candidates": [
            {
                "symbol": "042700",
                "name": "한미반도체",
                "sector": "semiconductor_equipment",
                "thesis": "TC 본더 독점",
                "kill_criteria": ["경쟁사 진입"],
            }
        ],
    }
    path = tmp_path / "core_holdings.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


class TestPortfolioHelp:
    def test_group_help(self, runner):
        result = runner.invoke(cli, ["portfolio", "--help"])
        assert result.exit_code == 0
        assert "주문 없음" in result.output


class TestPortfolioList:
    def test_lists_holdings_candidates_and_weights(self, runner, core_yaml):
        result = runner.invoke(cli, ["portfolio", "list", "--config", str(core_yaml)])
        assert result.exit_code == 0
        assert "012450" in result.output
        assert "한화에어로스페이스" in result.output
        assert "042700" in result.output  # candidate
        assert "10,000,000" in result.output  # holding value
        assert "11,500,000" in result.output  # total incl. cash
        # actual vs target: defense 10.0/11.5 ≈ 87% vs 35% → drift flag
        assert "87.0%" in result.output
        assert "35%" in result.output
        assert "이탈" in result.output

    def test_empty_ledger_lists_cleanly(self, runner, tmp_path):
        result = runner.invoke(
            cli, ["portfolio", "list", "--config", str(tmp_path / "absent.yaml")]
        )
        assert result.exit_code == 0
        assert "없음" in result.output
        assert "총 평가액: -" in result.output


class TestPortfolioValue:
    def test_value_updates_sidecar_not_main_yaml(self, runner, core_yaml):
        before = core_yaml.read_text(encoding="utf-8")
        result = runner.invoke(
            cli,
            [
                "portfolio",
                "value",
                "012450",
                "1100000",
                "--date",
                "2026-07-03",
                "--config",
                str(core_yaml),
            ],
        )
        assert result.exit_code == 0
        assert core_yaml.read_text(encoding="utf-8") == before  # comments safe

        sidecar = core_yaml.parent / "core_holdings_valuations.yaml"
        assert sidecar.exists()
        stored = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
        assert stored["012450"] == {"date": "2026-07-03", "price": 1100000.0}

        listing = runner.invoke(cli, ["portfolio", "list", "--config", str(core_yaml)])
        assert "1,100,000" in listing.output  # merged at load time

    def test_value_rejects_unknown_symbol(self, runner, core_yaml):
        result = runner.invoke(
            cli,
            ["portfolio", "value", "999999", "1000", "--config", str(core_yaml)],
        )
        assert result.exit_code == 1
        assert "보유 종목이 아닙니다" in result.output

    def test_value_rejects_candidate_symbol(self, runner, core_yaml):
        # Candidates are not owned — no valuation bookkeeping for them.
        result = runner.invoke(
            cli,
            ["portfolio", "value", "042700", "90000", "--config", str(core_yaml)],
        )
        assert result.exit_code == 1

    def test_value_rejects_non_positive_price(self, runner, core_yaml):
        result = runner.invoke(
            cli,
            ["portfolio", "value", "012450", "0", "--config", str(core_yaml)],
        )
        assert result.exit_code == 1


class TestPortfolioRecord:
    def _record(self, runner, core_yaml, ledger_path, *args):
        return runner.invoke(
            cli,
            [
                "portfolio",
                "record",
                *args,
                "--ledger-path",
                str(ledger_path),
                "--config",
                str(core_yaml),
            ],
        )

    def test_buy_records_track_a_trade(self, runner, core_yaml, tmp_path):
        ledger_path = tmp_path / "runtime.db"
        result = self._record(
            runner, core_yaml, ledger_path, "buy", "012450", "5", "985000"
        )
        assert result.exit_code == 0
        assert "주문은 발행되지 않았습니다" in result.output

        ledger = SQLiteRuntimeLedger(ledger_path)
        try:
            rows = ledger.query_trades({"track_id": "A"})
        finally:
            ledger.close()
        assert len(rows) == 1
        assert rows[0]["symbol"] == "012450"
        assert rows[0]["side"] == "buy"
        assert rows[0]["quantity"] == 5
        assert rows[0]["entry_price"] == pytest.approx(985_000.0)
        assert rows[0]["exit_price"] is None
        assert rows[0]["track_id"] == "A"

    def test_sell_records_exit_side(self, runner, core_yaml, tmp_path):
        ledger_path = tmp_path / "runtime.db"
        result = self._record(
            runner, core_yaml, ledger_path, "sell", "012450", "3", "1010000"
        )
        assert result.exit_code == 0

        ledger = SQLiteRuntimeLedger(ledger_path)
        try:
            rows = ledger.query_trades({"track_id": "A"})
        finally:
            ledger.close()
        assert rows[0]["side"] == "sell"
        assert rows[0]["exit_price"] == pytest.approx(1_010_000.0)
        assert rows[0]["entry_price"] is None

    def test_two_records_stay_distinct(self, runner, core_yaml, tmp_path):
        ledger_path = tmp_path / "runtime.db"
        self._record(runner, core_yaml, ledger_path, "buy", "012450", "5", "985000")
        self._record(runner, core_yaml, ledger_path, "buy", "012450", "5", "985000")
        ledger = SQLiteRuntimeLedger(ledger_path)
        try:
            rows = ledger.query_trades({"track_id": "A"})
        finally:
            ledger.close()
        assert len(rows) == 2  # separate manual fills, never coalesced

    def test_unknown_symbol_warns_but_records(self, runner, core_yaml, tmp_path):
        ledger_path = tmp_path / "runtime.db"
        result = self._record(
            runner, core_yaml, ledger_path, "buy", "999999", "1", "1000"
        )
        assert result.exit_code == 0
        assert "경고" in result.output

        ledger = SQLiteRuntimeLedger(ledger_path)
        try:
            rows = ledger.query_trades({"track_id": "A"})
        finally:
            ledger.close()
        assert len(rows) == 1

    def test_rejects_invalid_side_and_amounts(self, runner, core_yaml, tmp_path):
        ledger_path = tmp_path / "runtime.db"
        assert (
            self._record(
                runner, core_yaml, ledger_path, "hold", "012450", "1", "1000"
            ).exit_code
            != 0
        )
        assert (
            self._record(
                runner, core_yaml, ledger_path, "buy", "012450", "0", "1000"
            ).exit_code
            == 1
        )
        assert (
            self._record(
                runner, core_yaml, ledger_path, "buy", "012450", "1", "0"
            ).exit_code
            == 1
        )
