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
    assert len(reqs) == 1
    assert reqs[0].timeframe.minutes == 60


def test_no_mtf_base_key_means_empty_property():
    c = IndicatorContract.from_required_keys(["bb_lower", "rsi"])
    assert c.mtf_base_requests == ()


def test_malformed_mtf_base_token_falls_back_to_plain_base():
    c = IndicatorContract.from_required_keys(["mtf_base_NOTATOKEN"])
    reqs = [r for r in c.requests if r.source_key == "mtf_base_NOTATOKEN"]
    assert len(reqs) == 1
    assert reqs[0].kind == IndicatorKind.BASE
    assert reqs[0].timeframe is None
    assert reqs[0].name == "mtf_base_NOTATOKEN"
    assert c.mtf_base_requests == ()  # malformed must NOT count as a tf-base req


def test_mtf_timeframes_collects_momentum_and_base_sorted_distinct():
    c = IndicatorContract.from_required_keys(
        ["momentum_5m", "mtf_base_15m", "momentum_15m", "rsi"]
    )
    assert c.mtf_timeframes == (5, 15)


def test_mtf_timeframes_empty_for_1m_only_strategy():
    c = IndicatorContract.from_required_keys(["bb_lower", "bb_upper", "rsi"])
    assert c.mtf_timeframes == ()


def test_warmth_timeframe_is_deepest_intraday():
    c = IndicatorContract.from_required_keys(["momentum_5m", "mtf_base_15m"])
    assert c.warmth_timeframe == 15


def test_warmth_timeframe_none_for_1m_only_strategy():
    c = IndicatorContract.from_required_keys(["bb_lower", "rsi"])
    assert c.warmth_timeframe is None


def test_warmth_timeframe_excludes_daily():
    # 'daily' (mtf_base_1d => 1440 min) is seeded separately from ClickHouse and
    # must not gate is_warm. Warmth follows the deepest *intraday* tf.
    c = IndicatorContract.from_required_keys(["mtf_base_15m", "mtf_base_1d"])
    assert 1440 in c.mtf_timeframes
    assert c.warmth_timeframe == 15


def test_warmth_timeframe_none_when_only_daily():
    c = IndicatorContract.from_required_keys(["mtf_base_1d"])
    assert c.warmth_timeframe is None
