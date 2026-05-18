from shared.indicators.contracts import IndicatorContract, IndicatorKind


def test_mtf_base_key_parsed_as_base_with_timeframe():
    c = IndicatorContract.from_required_keys(
        ["bb_lower", "bb_upper", "bb_middle", "rsi", "mtf_base_15m"]
    )
    base_tf = [
        r for r in c.requests
        if r.kind == IndicatorKind.BASE and r.timeframe is not None
    ]
    assert len(base_tf) == 1
    assert base_tf[0].timeframe.minutes == 15
    assert base_tf[0].source_key == "mtf_base_15m"
    assert any(
        r.name == "bb_lower" and r.timeframe is None for r in c.requests
    )


def test_mtf_base_requests_property_exposes_only_tf_base():
    c = IndicatorContract.from_required_keys(["rsi", "mtf_base_60m"])
    reqs = c.mtf_base_requests
    assert len(reqs) == 1 and reqs[0].timeframe.minutes == 60


def test_no_mtf_base_key_means_empty_property():
    c = IndicatorContract.from_required_keys(["bb_lower", "rsi"])
    assert c.mtf_base_requests == ()
