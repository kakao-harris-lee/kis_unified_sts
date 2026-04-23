"""Tests for shared.scoring.prompt — versioned prompt template stability."""

from shared.scoring.prompt import PROMPT_V1, render


def test_prompt_v1_has_all_schema_fields():
    for field in (
        "category",
        "sentiment",
        "impact_score",
        "direction_bias",
        "confidence",
        "keywords",
        "reasoning",
    ):
        assert field in PROMPT_V1


def test_render_interpolates_title_and_body():
    text = render(PROMPT_V1, title="FOMC holds rates", body="Powell remarks...")
    assert "FOMC holds rates" in text
    assert "Powell remarks" in text


def test_render_truncates_long_body():
    long_body = "x" * 5000
    text = render(PROMPT_V1, title="t", body=long_body, body_max_chars=2000)
    # The rendered prompt must not contain the full 5000-char body.
    assert "x" * 3000 not in text
