from types import SimpleNamespace

from shared.llm import reporting


def test_should_not_publish_failed_llm_quality_snapshot():
    stock_analysis = {
        "_analysis_status": {
            "status": "failed",
            "reason": "market_data_unavailable",
        }
    }

    assert reporting.should_publish_llm_quality_snapshot(stock_analysis) is False


def test_publish_llm_quality_snapshot_skips_failed_analysis(monkeypatch):
    stock_analysis = {
        "_analysis_status": {
            "status": "failed",
            "reason": "market_data_unavailable",
        }
    }

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("failed analysis must not build Redis payload")

    monkeypatch.setattr(reporting, "build_llm_quality_snapshot", fail_if_called)

    reporting.publish_llm_quality_snapshot(
        SimpleNamespace(datetime_str="2026-05-27 08:30:00"),
        "snapshot-failed",
        [],
        stock_analysis,
    )
