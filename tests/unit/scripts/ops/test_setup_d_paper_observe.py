from __future__ import annotations

from pathlib import Path

from scripts.ops.setup_d_paper_observe import build_setup_d_report, main


def test_build_setup_d_report_summarizes_long_short_and_rejections(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text(
        "\n".join(
            [
                '{"strategy":"setup_d_vwap_reversion","side":"BUY","status":"accepted","pnl":12000,"reason":"vwap_revert"}',
                '{"strategy":"setup_d_vwap_reversion","side":"SELL","status":"accepted","pnl":-3000,"reason":"stop_loss"}',
                '{"strategy":"setup_d_vwap_reversion","side":"BUY","status":"rejected","reject_stage":"risk","reject_reason":"spread"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_setup_d_report(ledger)

    assert report["strategy"] == "setup_d_vwap_reversion"
    assert report["accepted"] == 2
    assert report["rejected"] == 1
    assert report["long_signals"] == 2
    assert report["short_signals"] == 1
    assert report["total_pnl"] == 9000
    assert report["top_reject_reasons"] == {"risk:spread": 1}


def test_main_returns_nonzero_when_input_path_is_missing(tmp_path: Path) -> None:
    output = tmp_path / "report.json"

    rc = main(
        [
            "--input",
            str(tmp_path / "missing-signals.jsonl"),
            "--output",
            str(output),
        ]
    )

    assert rc == 1
    assert not output.exists()
