from __future__ import annotations

from datetime import UTC, datetime
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

    generated_at = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)

    report = build_setup_d_report(ledger, generated_at=generated_at)

    assert report["strategy"] == "setup_d_vwap_reversion"
    # KST-native: the UTC instant is emitted in Asia/Seoul (+09:00).
    assert report["generated_at"] == "2026-06-28T21:00:00+09:00"
    assert report["source_path"] == str(ledger)
    assert report["accepted"] == 2
    assert report["rejected"] == 1
    assert report["long_signals"] == 2
    assert report["short_signals"] == 1
    assert report["total_pnl"] == 9000
    assert report["top_reject_reasons"] == {"risk:spread": 1}


def test_build_setup_d_report_handles_repo_vocabulary(tmp_path: Path) -> None:
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text(
        "\n".join(
            [
                '{"strategy":"setup_d_vwap_reversion","direction":"long","status":"paper_filled","pnl":4500}',
                '{"strategy":"setup_d_vwap_reversion","side":"short","status":"paper_rejected","reject_stage":"risk","reject_reason":"spread"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_setup_d_report(ledger)

    assert report["accepted"] == 1
    assert report["rejected"] == 1
    assert report["signals"] == 2
    assert report["long_signals"] == 1
    assert report["short_signals"] == 1
    assert report["total_pnl"] == 4500
    assert report["top_reject_reasons"] == {"risk:spread": 1}


def test_build_setup_d_report_skips_malformed_jsonl_lines(tmp_path: Path) -> None:
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text(
        "\n".join(
            [
                "",  # blank line
                "123",  # non-dict (int)
                '"just-a-string"',  # non-dict (str)
                "[1, 2, 3]",  # non-dict (list)
                "true",  # non-dict (bool)
                "null",  # non-dict (None)
                "{not valid json",  # unparseable
                '{"strategy":"setup_d_vwap_reversion","side":"buy","status":"accepted"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_setup_d_report(ledger)

    assert report["total_rows"] == 1
    assert report["accepted"] == 1
    assert report["long_signals"] == 1
    assert report["signals"] == 1


def test_build_setup_d_report_tolerates_non_numeric_pnl(tmp_path: Path) -> None:
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text(
        "\n".join(
            [
                '{"strategy":"setup_d_vwap_reversion","side":"buy","status":"accepted","pnl":"-"}',
                '{"strategy":"setup_d_vwap_reversion","side":"buy","status":"accepted","pnl":"n/a"}',
                '{"strategy":"setup_d_vwap_reversion","side":"sell","status":"accepted","pnl":2000}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_setup_d_report(ledger)

    assert report["accepted"] == 3
    assert report["total_pnl"] == 2000
    assert report["pnl_rows"] == 1


def test_build_setup_d_report_counts_unresolved_and_keeps_invariant(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text(
        "\n".join(
            [
                '{"strategy":"setup_d_vwap_reversion","side":"long","status":"generated"}',
                '{"strategy":"setup_d_vwap_reversion","side":"long","status":"paper_filled"}',
                '{"strategy":"setup_d_vwap_reversion","side":"short","status":"blocked","reject_stage":"risk","reject_reason":"vol"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_setup_d_report(ledger)

    assert report["total_rows"] == 3
    assert report["accepted"] == 1
    assert report["rejected"] == 1
    assert report["unresolved"] == 1
    assert report["signals"] == report["accepted"] + report["rejected"]


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
