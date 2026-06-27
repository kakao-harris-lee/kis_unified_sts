"""Theme leader scoring and payload contract tests."""

from __future__ import annotations

import pytest

from shared.theme_universe.models import (
    ThemeCandidate,
    build_theme_targets_payload,
    parse_theme_candidates,
)
from shared.theme_universe.scoring import ThemeScoreInput, classify_theme_candidate


def test_classifies_active_theme_leader():
    result = classify_theme_candidate(
        ThemeScoreInput(
            relative_strength=0.9,
            trading_value_score=0.8,
            volume_surge_score=0.8,
            catalyst_score=0.9,
            theme_breadth_score=0.7,
            intraday_persistence=0.8,
            freshness_score=1.0,
            market_signal_count=2,
            catalyst_signal_count=1,
            risk_flags=[],
        )
    )

    assert result.state == "active"
    assert result.leader_score >= 0.7
    assert result.hard_blocked is False


def test_quarantines_hard_risk_flags():
    result = classify_theme_candidate(
        ThemeScoreInput(
            relative_strength=1.0,
            trading_value_score=1.0,
            volume_surge_score=1.0,
            catalyst_score=1.0,
            theme_breadth_score=1.0,
            intraday_persistence=1.0,
            freshness_score=1.0,
            market_signal_count=3,
            catalyst_signal_count=2,
            risk_flags=["investment_warning"],
        )
    )

    assert result.state == "quarantine"
    assert result.hard_blocked is True


@pytest.mark.parametrize(
    ("market_signal_count", "catalyst_signal_count"),
    [
        (0, 1),
        (3, 0),
    ],
)
def test_requires_market_and_catalyst_evidence_for_active(
    market_signal_count: int,
    catalyst_signal_count: int,
):
    result = classify_theme_candidate(
        ThemeScoreInput(
            relative_strength=0.9,
            trading_value_score=0.9,
            volume_surge_score=0.9,
            catalyst_score=0.9,
            theme_breadth_score=0.9,
            intraday_persistence=0.9,
            freshness_score=1.0,
            market_signal_count=market_signal_count,
            catalyst_signal_count=catalyst_signal_count,
            risk_flags=[],
        )
    )

    assert result.state == "watch"


def test_clamps_score_inputs_to_zero_one_range():
    result = classify_theme_candidate(
        ThemeScoreInput(
            relative_strength=2.0,
            trading_value_score=3.0,
            volume_surge_score=1.5,
            catalyst_score=9.0,
            theme_breadth_score=2.0,
            intraday_persistence=1.1,
            freshness_score=8.0,
            market_signal_count=1,
            catalyst_signal_count=1,
            risk_flags=[],
        )
    )

    assert result.leader_score == 1.0
    assert result.state == "active"


def test_theme_candidate_payload_helpers_round_trip_json_friendly_contract():
    candidate = ThemeCandidate(
        code="005930",
        name="Samsung Electronics",
        theme="HBM",
        state="active",
        leader_score=0.8123456,
        risk_flags=("short_sale_watch",),
        market_signal_count=2,
        catalyst_signal_count=1,
        metadata={"rank": 1, "source": "unit"},
    )

    payload = build_theme_targets_payload([candidate])

    assert payload["codes"] == ["005930"]
    assert payload["themes"] == ["HBM"]
    assert payload["state_counts"] == {"active": 1, "watch": 0, "quarantine": 0}
    assert payload["metadata"]["candidate_count"] == 1
    assert payload["candidates"] == [
        {
            "code": "005930",
            "name": "Samsung Electronics",
            "theme": "HBM",
            "state": "active",
            "leader_score": 0.812346,
            "risk_flags": ["short_sale_watch"],
            "market_signal_count": 2,
            "catalyst_signal_count": 1,
            "metadata": {"rank": 1, "source": "unit"},
        }
    ]

    parsed = parse_theme_candidates(payload)

    assert parsed == [
        ThemeCandidate(
            code="005930",
            name="Samsung Electronics",
            theme="HBM",
            state="active",
            leader_score=0.812346,
            risk_flags=("short_sale_watch",),
            market_signal_count=2,
            catalyst_signal_count=1,
            metadata={"rank": 1, "source": "unit"},
        )
    ]
