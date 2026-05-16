"""Tests for RSI/Williams %R/MACD technical consensus."""

from shared.strategy.technical_consensus import (
    TechnicalConsensusConfig,
    build_technical_consensus,
)


def test_entry_consensus_requires_overlapping_votes():
    consensus = build_technical_consensus(
        {
            "prev_williams_r": -86.0,
            "williams_r": -60.0,
            "prev_rsi": 31.0,
            "rsi": 42.0,
            "prev_macd_hist": -0.2,
            "macd_hist": 0.1,
            "close": 103.0,
            "ma20": 100.0,
            "volume_ratio": 1.4,
        },
        config=TechnicalConsensusConfig(min_entry_votes=2),
    )

    assert consensus.entry_signal is True
    assert consensus.exit_signal is False
    assert consensus.entry_vote_count >= 3
    assert consensus.entry_core_vote_count >= 3
    assert consensus.recommendation == "entry_candidate"


def test_exit_consensus_detects_rollover_cluster():
    consensus = build_technical_consensus(
        {
            "prev_williams_r": -8.0,
            "williams_r": -42.0,
            "prev_rsi": 74.0,
            "rsi": 58.0,
            "prev_macd_hist": 0.3,
            "macd_hist": -0.1,
            "close": 96.0,
            "ma20": 100.0,
            "high_since_entry": 103.0,
        },
        config=TechnicalConsensusConfig(min_exit_votes=2),
    )

    assert consensus.exit_signal is True
    assert consensus.entry_signal is False
    assert consensus.exit_vote_count >= 3
    assert consensus.exit_core_vote_count >= 3
    assert consensus.recommendation == "exit_candidate"


def test_short_common_indicator_noise_does_not_vote_without_previous_state():
    consensus = build_technical_consensus(
        {
            "williams_r": -60.0,
            "rsi": 42.0,
            "macd_hist": 0.1,
            "close": 103.0,
            "ma20": 100.0,
        },
        config=TechnicalConsensusConfig(
            min_entry_votes=2,
            include_volume_vote=False,
        ),
    )

    assert consensus.entry_signal is False
    assert [v.name for v in consensus.entry_votes] == ["trend_anchor_reclaim"]
