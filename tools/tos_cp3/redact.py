#!/usr/bin/env python3
"""내보내는 문서에서 호스트 경로와 계좌를 지운다 — 키를 고르지 않고 **전부** 훑어서.

``/tos`` 는 Cloudflare Access 뒤에서 인터넷에 열려 있고 앱 자체 인증이 없다. 그런데
상태판과 종목 문서가 싣는 문장 중 여럿은 **자유 텍스트**다 — 러너의 ``die`` 메시지
(``$TENANT_CUSTODY_ROOT`` · ``$TENANT_LOG`` · ``$DATA_LEAF`` 를 그대로 끼워 넣는다),
``f"{type(exc).__name__}: {exc}"`` 로 만든 잎/달력 오류, 그리고 그 문장들을 다시
감싼 상태판 이슈. 실제 사고 모양(#1179 리뷰): 세션 로그의
``ABORT: cannot create data leaf /home/deploy/.local/state/tos/...`` 한 줄이
``board.json`` 에 세 번 실려 라우트를 타고 브라우저까지 갔다.

**키를 골라 지우지 않는다.** 「이 필드는 자유 텍스트니까 여기만」 식으로 막으면
다음에 필드가 하나 늘어날 때 조용히 새는 길이 생긴다 — 실제로 그래서 샜다. 그래서
:func:`redact_document` 는 완성된 문서를 통째로 걸어 **모든 문자열 잎**(과 키)을
지운다. 새 필드는 기본적으로 지워진 채 나간다.

**기본은 경로를 통째로 지우는 것이다.** basename 만 남기는 선택지가 있지만, 이
저장소의 basename 은 잎 이름(``A05612``)이나 계좌 지문처럼 **그 자체가 식별자**인
경우가 많다. 가장 안전한 쪽을 고른다 — :data:`PATH_PLACEHOLDER` 하나로 바꾼다.

지우는 것이 **사유를 지우지는 않는다**: 「무엇이 막혔나」 는 문장에 그대로 남고
경로만 자리 표시로 바뀐다. 운영자가 경로를 봐야 하면 호스트의 로그에 있다.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

__all__ = [
    "ACCOUNT_ENV_SUBSTRING",
    "ACCOUNT_PLACEHOLDER",
    "IDENTIFIER_KEYS",
    "PATH_PLACEHOLDER",
    "account_values_from_env",
    "redact_document",
    "redact_mapping",
    "redact_text",
]

#: 경로가 있던 자리. 사람이 읽는 문장 안에 들어가므로 한국어로 적는다.
PATH_PLACEHOLDER = "<경로>"

#: 계좌로 보이는 수가 있던 자리.
ACCOUNT_PLACEHOLDER = "<계좌>"

#: URL — 매치하면 **그대로 둔다**. 경로 규칙이 ``//host/path`` 를 잘라 주소를
#: 반쪽으로 만들지 않게, 같은 훑기에서 먼저 잡아 두고 원문을 돌려준다.
_URL = r"(?P<url>[A-Za-z][A-Za-z0-9+.\-]*://[^\s'\"<>]*)"

#: 윈도 경로. ``C:\...`` · ``C:/...`` 와 ``\\wsl$\...`` 같은 UNC.
_WINDOWS = (
    r"(?P<win>(?<![A-Za-z0-9_])"
    r"(?:[A-Za-z]:[\\/]|\\\\[A-Za-z0-9_.$-]+\\)[^\s'\"<>]*)"
)

#: ``$HOME/...`` · ``${TENANT_CUSTODY_ROOT}/...`` — 러너가 끼워 넣는 모양.
_SHELL = r"(?P<shell>\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/[A-Za-z0-9_./@%+\-]*)"

#: 절대 경로 토큰. ``~/`` 로 시작하거나 ``/`` 구획이 둘 이상인 덩어리.
#:
#: 앞이 ASCII 단어 문자나 ``.`` 이면 매치하지 않는다 — ``0/143`` 같은 비율을
#: 경로로 오인하지 않기 위해서다. 한글은 여기서 **빠진다**: ``잎/home/deploy/x``
#: 처럼 조사 바로 뒤에 붙은 경로가 그대로 새 나갔다(#1179 리뷰 LOW).
#: 구획을 둘 이상 요구하므로 ``확인/막힘`` · ``손익/pnl`` 은 경로가 아니다.
_POSIX = (
    r"(?P<posix>(?<![A-Za-z0-9_.])"
    r"(?:~/[A-Za-z0-9_./@%+\-]*|/[A-Za-z0-9_.@%+\-]+(?:/[A-Za-z0-9_.@%+\-]*)+))"
)

#: ``.local/state/tos/...`` 처럼 숨은 디렉터리로 시작하는 상대 경로.
_RELATIVE = r"(?P<rel>(?<![A-Za-z0-9_./~])\.[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_.@%+\-]+)+)"

_PATH_TOKEN = re.compile("|".join((_URL, _WINDOWS, _SHELL, _POSIX, _RELATIVE)))

#: 따옴표 안이 경로로 시작하면 **닫는 따옴표까지** 지운다 — 공백이 든 경로의
#: 꼬리(``'/home/deploy/my data/x.yaml'`` 의 ``my data/x.yaml``)가 남지 않게.
_QUOTED_PATH = re.compile(
    r"""(['"])((?:~?/|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/|[A-Za-z]:[\\/]|\\\\)[^'"]*)\1"""
)

_ASCII_LETTER = re.compile(r"[A-Za-z]")

#: 계좌 번호 모양. 하이픈 형(``12345678-01``)과 10~12 자리 숫자.
#:
#: 자릿수 하한이 10 인 이유는 이 문서들이 정상적으로 싣는 수가 전부 그 아래이기
#: 때문이다 — 세션 이름의 날짜(``20261125``, 8자리) · 종목(``000660``, 6자리) ·
#: 원화 가격(7자리 이하). 하한을 8 로 내리면 날짜가 전부 가려진다.
_HYPHENATED_ACCOUNT = re.compile(r"(?<!\d)\d{8}-\d{2}(?!\d)")
_BARE_ACCOUNT = re.compile(r"(?<!\d)\d{10,12}(?!\d)")

#: 계좌라고 **이름표가 붙은** 8자리. ``CANO=50205915`` · ``계좌 50205915``.
#:
#: SAFETY: 이름표 없는 8자리는 절대 지우지 않는다 — 거래일(20261125)이 전부 가려진다
_LABELLED_ACCOUNT = re.compile(
    r"((?:CANO|ACNO|ACCT|ACCOUNT|계좌)[A-Za-z0-9_]*\s*[:=]?\s*)(\d{8})(?![\d-])",
    re.IGNORECASE,
)

#: 이 글자를 이름에 담은 환경변수의 값은 계좌로 보고 지운다
#: (``KIS_STOCK_ACCOUNT_NO`` · ``KIS_FUTURES_ACCOUNT_NO`` …).
ACCOUNT_ENV_SUBSTRING = "ACCOUNT"

#: 계좌 **패턴** 규칙에서 빼는 키.
#:
#: SAFETY: broker_execution_id 는 주문번호(odno)이지 계좌가 아니다 — 10자리라 계좌 패턴에 걸리는데, 가리면 운영자가 브로커에서 그 주문을 찾을 길이 사라진다
#:
#: 경로 규칙과 「환경변수에서 읽은 **실제 계좌 값**」 규칙은 이 키에도 그대로
#: 적용된다. 빠지는 것은 「10자리니까 계좌일 것」 이라는 추측뿐이다.
IDENTIFIER_KEYS = frozenset({"broker_execution_id"})


def account_values_from_env(
    environ: Mapping[str, str] | None = None,
) -> frozenset[str]:
    """환경에 설정된 계좌 값들 — 이름에 ``ACCOUNT`` 를 담은 변수의 값.

    값 자체로 지우므로 패턴이 놓치는 모양(짧은 계좌 · 접미사가 붙은 것)도 걸린다.
    너무 짧은 값은 버린다 — 두세 글자를 문서 전체에서 지우면 멀쩡한 문장이 깨진다.
    """
    items = (os.environ if environ is None else environ).items()
    return frozenset(
        value.strip()
        for name, value in items
        if ACCOUNT_ENV_SUBSTRING in name.upper() and len(value.strip()) >= 6
    )


def _replace_path_token(match: re.Match[str]) -> str:
    """한 토큰을 자리 표시로 — URL 과 숫자뿐인 비율은 원문 그대로 돌려준다."""
    token = match.group(0)
    if match.lastgroup == "url":
        return token
    # SAFETY: 「3 /378」 처럼 숫자뿐인 덩어리는 비율이지 경로가 아니다 — 지우면 측정값이 사라진다
    if match.lastgroup == "posix" and not _ASCII_LETTER.search(token):
        return token
    return PATH_PLACEHOLDER


def redact_text(
    text: str,
    *,
    account_values: Iterable[str] = (),
    extra_paths: Iterable[str] = (),
    mask_account_pattern: bool = True,
) -> str:
    """한 문장에서 경로와 계좌를 자리 표시로 바꾼다.

    Args:
        text: 바꿀 문장.
        account_values: 지울 실제 계좌 값(환경에서 읽은 것).
        extra_paths: 지울 경로 문자열(상태 루트 등). 절대 경로 규칙이 이미 잡지만,
            규칙이 바뀌어도 상태 루트만은 반드시 지워지게 따로 받는다.
        mask_account_pattern: ``False`` 면 「계좌처럼 보이는 수」 규칙을 끈다
            (:data:`IDENTIFIER_KEYS` 의 값에만 쓴다).
    """
    out = text
    # 긴 것부터 — 짧은 접두가 긴 값을 반쪽만 지우는 일이 없게.
    for value in sorted((v for v in extra_paths if v), key=len, reverse=True):
        out = out.replace(value, PATH_PLACEHOLDER)
    # 따옴표가 먼저다 — 토큰 규칙이 공백에서 끊고 나면 꼬리만 남은 채 닫힌다.
    out = _QUOTED_PATH.sub(lambda m: f"{m.group(1)}{PATH_PLACEHOLDER}{m.group(1)}", out)
    out = _PATH_TOKEN.sub(_replace_path_token, out)
    for value in sorted((v for v in account_values if v), key=len, reverse=True):
        out = out.replace(value, ACCOUNT_PLACEHOLDER)
    if mask_account_pattern:
        out = _HYPHENATED_ACCOUNT.sub(ACCOUNT_PLACEHOLDER, out)
        out = _LABELLED_ACCOUNT.sub(rf"\1{ACCOUNT_PLACEHOLDER}", out)
        out = _BARE_ACCOUNT.sub(ACCOUNT_PLACEHOLDER, out)
    return out


def redact_document(
    value: Any,
    *,
    account_values: Iterable[str] = (),
    extra_paths: Iterable[str] = (),
    _key: str | None = None,
) -> Any:
    """문서를 통째로 걸으며 **모든** 문자열(키와 값)을 :func:`redact_text` 에 건다.

    이 함수의 일은 「어느 필드가 위험한가」 를 알지 않는 것이다. 내보내기가 필드를
    하나 더해도 기본값이 「지워진 채 나간다」 가 되게 하는 것이 전부다.
    """
    values = tuple(account_values)
    paths = tuple(extra_paths)
    if isinstance(value, str):
        return redact_text(
            value,
            account_values=values,
            extra_paths=paths,
            mask_account_pattern=_key not in IDENTIFIER_KEYS,
        )
    if isinstance(value, Mapping):
        return {
            (
                redact_text(key, account_values=values, extra_paths=paths)
                if isinstance(key, str)
                else key
            ): redact_document(item, account_values=values, extra_paths=paths, _key=key)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            redact_document(item, account_values=values, extra_paths=paths, _key=_key)
            for item in value
        ]
    return value


def redact_mapping(
    document: Mapping[str, Any],
    *,
    account_values: Iterable[str] = (),
    extra_paths: Iterable[str] = (),
) -> dict[str, Any]:
    """문서 하나를 지운 결과 — 최상위가 매핑임을 타입으로 말하는 입구.

    :func:`redact_document` 는 어떤 값이든 받는 walker 라 반환이 ``Any`` 다. 문서를
    닫는 자리에서는 ``dict`` 임이 분명하므로, 내보내기 쪽이 ``Any`` 를 돌려주지
    않도록 여기서 한 번 좁힌다.
    """
    redacted = redact_document(
        dict(document), account_values=account_values, extra_paths=extra_paths
    )
    if not isinstance(redacted, dict):  # pragma: no cover - 위 분기상 닿지 않는다
        raise TypeError("redact_document가 매핑을 돌려주지 않았다")
    return redacted
