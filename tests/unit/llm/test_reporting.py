from types import SimpleNamespace

from shared.llm import reporting
from shared.llm.data_classes import StockTradingPlan


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


def test_build_llm_quality_snapshot_includes_plan_metadata():
    plan = StockTradingPlan(
        code="080220",
        name="제주반도체",
        strategy="이평크로스(10/30)",
        entry_price=112900.0,
        stop_loss=104997.0,
        take_profit=126448.0,
        position_size=0.2,
        confidence="높음",
        reasons=["백테스트 승률 100.0%"],
        news_sentiment="긍정",
    )
    stock_analysis = {
        "080220": {
            "screening": {
                "score": 100.0,
                "metrics": {},
            }
        }
    }

    payload = reporting.build_llm_quality_snapshot(
        SimpleNamespace(datetime_str="2026-06-26 09:00:00"),
        "snapshot-080220",
        [plan],
        stock_analysis,
    )

    metadata = payload["metadata"]["080220"]
    assert payload["final_codes"] == ["080220"]
    assert payload["quality"] == {"080220": 1.0}
    assert metadata["entry_price"] == 112900.0
    assert metadata["stop_loss"] == 104997.0
    assert metadata["take_profit"] == 126448.0
    assert metadata["llm_plan_strategy"] == "이평크로스(10/30)"
