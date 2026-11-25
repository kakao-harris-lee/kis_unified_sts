"""``tools/tos_cp3/redact.py`` — 내보내는 문서에서 경로와 계좌를 지운다.

사례는 ``tests/fixtures/tos/redaction-cases.json`` 하나를 양쪽(내보내기 · 웹)이
함께 본다. ``services/`` 는 ``tools/`` 를 import 할 수 없으므로 구현이 둘인데,
**사례표는 하나**여야 두 쪽이 갈라지는 것을 테스트가 잡는다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3 import redact as r

_CASES = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "tos"
        / "redaction-cases.json"
    ).read_text(encoding="utf-8")
)


def test_the_placeholders_match_the_shared_fixture() -> None:
    """두 쪽이 다른 자리 표시를 쓰면 화면에 두 가지 «지움» 이 생긴다."""
    assert _CASES["path_placeholder"] == r.PATH_PLACEHOLDER
    assert _CASES["account_placeholder"] == r.ACCOUNT_PLACEHOLDER


@pytest.mark.parametrize("case", _CASES["redacted"], ids=lambda c: c["why"])
def test_every_leaking_shape_is_redacted(case: dict[str, str]) -> None:
    assert r.redact_text(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", _CASES["kept"], ids=lambda c: c["why"])
def test_a_careless_rule_would_break_these_and_must_not(case: dict[str, str]) -> None:
    """사유를 지우면 안 된다 — 경로만 자리 표시로 바뀌고 문장은 남는다."""
    assert r.redact_text(case["input"]) == case["input"]


def test_the_fixture_is_not_empty() -> None:
    """빈 표 위에서 위 두 루프가 공허하게 통과하지 않게."""
    assert len(_CASES["redacted"]) >= 33
    assert len(_CASES["kept"]) >= 16


def test_configured_account_values_are_removed_even_when_the_pattern_misses() -> None:
    """패턴은 모양만 안다 — 실제로 설정된 값은 모양과 상관없이 지운다."""
    env = {"KIS_STOCK_ACCOUNT_NO": "50205915", "HOME": "/home/deploy"}
    values = r.account_values_from_env(env)
    assert values == {"50205915"}
    assert "50205915" not in r.redact_text("acct 50205915", account_values=values)
    # …그리고 계좌와 무관한 변수의 값은 건드리지 않는다.
    assert r.account_values_from_env({"HOME": "/home/deploy"}) == frozenset()


def test_a_too_short_account_value_is_ignored() -> None:
    """두세 글자를 문서 전체에서 지우면 멀쩡한 문장이 깨진다."""
    assert r.account_values_from_env({"ACCOUNT": "12"}) == frozenset()


def test_the_state_root_is_removed_even_if_the_path_rule_changed() -> None:
    """상태 루트만은 규칙과 무관하게 반드시 지워지도록 따로 건넨다."""
    out = r.redact_text(
        "leaf under /srv/state/tos/leaf", extra_paths=["/srv/state/tos"]
    )
    assert "/srv/state/tos" not in out


def test_the_walk_reaches_every_string_including_keys_and_nested_lists() -> None:
    """키를 고르지 않는 것이 요점이다 — 새 필드도 기본적으로 지워진 채 나간다."""
    document: dict[str, Any] = {
        "issues": [
            {"level": "막힘", "text": "ABORT: see /home/deploy/.local/state/tos/x"}
        ],
        "nested": {"deep": [["/home/deploy/secret"]]},
        "a_field_added_tomorrow": "/home/deploy/also-this",
        "/home/deploy/as-a-key": 1,
        "untouched": 42,
        "nothing": None,
    }
    out = r.redact_document(document)
    rendered = json.dumps(out, ensure_ascii=False)
    assert "/home/deploy" not in rendered
    assert out["issues"][0]["level"] == "막힘"
    assert out["issues"][0]["text"] == "ABORT: see <경로>"
    assert out["nested"]["deep"] == [["<경로>"]]
    assert out["a_field_added_tomorrow"] == "<경로>"
    assert r.PATH_PLACEHOLDER in list(out)
    assert out["untouched"] == 42
    assert out["nothing"] is None


def test_a_broker_order_number_survives_but_the_same_digits_in_prose_do_not() -> None:
    """``broker_execution_id`` 는 주문번호다 — 가리면 브로커에서 찾을 길이 없다.

    그 키에서 빠지는 것은 「10자리니까 계좌일 것」 이라는 **추측**뿐이고, 같은
    숫자가 자유 텍스트에 있으면 그대로 지운다.
    """
    out = r.redact_document(
        {"broker_execution_id": "0000027053", "reason": "odno 0000027053 미접수"}
    )
    assert out["broker_execution_id"] == "0000027053"
    assert out["reason"] == "odno <계좌> 미접수"


def test_a_real_account_value_is_removed_even_from_an_identifier_key() -> None:
    """면제는 패턴 추측에만 해당한다 — 실제 계좌 값은 어느 키에서도 지운다."""
    out = r.redact_document(
        {"broker_execution_id": "5020591501"}, account_values={"5020591501"}
    )
    assert out["broker_execution_id"] == "<계좌>"
