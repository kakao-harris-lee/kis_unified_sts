"""Prompt templates for news scoring.

Any edit to PROMPT_V1 MUST bump ``scorer_version`` in ``config/news_scoring.yaml``.
Never back-fill old scored rows with a new scorer_version — preserve the audit trail.
"""

from __future__ import annotations

PROMPT_V1 = """당신은 KOSPI200 지수선물 가격 영향을 판단하는 정량 분석 AI 입니다.
뉴스 1건을 읽고 아래 JSON 스키마로만 응답하세요. 설명 금지, JSON only.

뉴스 제목: {title}
뉴스 본문 (최대 2000자): {body}

{{
  "category": "macro_us|macro_kr|geopolitics|samsung|hynix|korea_policy|sector_event|corporate|other",
  "sentiment": <-1.0~1.0>,
  "impact_score": <0.0~1.0>,
  "direction_bias": "long|short|neutral",
  "confidence": <0.0~1.0>,
  "keywords": [<최대 5개 문자열>],
  "reasoning": "<한 줄 요약 60자 이내>"
}}

판단 기준:
- FOMC/CPI/고용지표/FED 인사 발언: impact >= 0.8
- 북한/지정학 군사 리스크: sentiment 음수, impact >= 0.6
- 삼성/SK하이닉스 단일 실적/CAPEX: impact 0.4~0.6
- 일반 기업 실적: impact <= 0.2
- 반복 루머/이미 반영된 이슈: impact <= 0.1
- 한국어/영어 혼재 허용, lang 관계없이 동일 기준.
"""


def render(template: str, *, title: str, body: str, body_max_chars: int = 2000) -> str:
    """Render a prompt template with the given news title and body.

    Args:
        template: A prompt template string containing ``{title}`` and ``{body}``
            placeholders. Literal curly braces in JSON schema examples must be
            escaped as ``{{`` / ``}}``.
        title: News article title.
        body: News article body text. Truncated to *body_max_chars* before
            interpolation to stay within model context limits.
        body_max_chars: Maximum characters of *body* to include (default 2000).

    Returns:
        The fully rendered prompt string ready to send to the LLM.
    """
    body_trim = body[:body_max_chars]
    return template.format(title=title, body=body_trim)
