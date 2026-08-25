#!/usr/bin/env python3
"""tos 완료-계약 «자기참조 stale» 게이트 — addendum-5 결함 클래스의 구조적 처분.

addendum-5 가 낸 네 건은 전부 같은 클래스다: **계약이 자기 자신에 관한 값을 본문에
적는데, 그 값이 다음 편집에서 조용히 stale 해진다.**  값을 고치는 처분은 다음 회차에
또 stale 해지므로 구조로 막아야 한다 — 이 파일이 그 처분이다.

검사 축 (각 축은 모집단을 **문서 구조에서 파생**한다; 자리 열거를 하드코딩하지 않는다)::

  C1  TOS-CC-C1   「(4) 열거」의 **기수를 말하는 모든 문장** ≡ 실제 열거 원소 수.
      TOS-CC-C1X  실제 원소 집합의 **두 독립 파생**(구분자 분해 · 원형숫자 분해)이 불일치.
  C2  TOS-CC-C2R  자기인용 좌표가 문서 행 범위 «밖».
      TOS-CC-C2A  인용 «목록» + 문장이 병기한 «포섭 술어» ↔ 피인용 행 실측 불일치.
      TOS-CC-C2B  인용에 붙은 «주장절»의 최장 축자 앵커가 피인용 범위에 부재
                  (문서 다른 곳에는 실재 = 좌표가 이동했다는 증거).
      TOS-CC-C2C  ANCHOR-1 규약(아래) 위반 — 규약을 채택한 인용에 한해 발화.
  C3  TOS-CC-C3A  «현행 버전»보다 **큰** 리터럴 버전(= 구성상 미래 지향).
      TOS-CC-C3B  머리말이 스스로 열거한 «미래 지향 필드» 어휘 + 동일 major 리터럴 버전.
  C4  TOS-CC-C4A  currency 층 태그 «현행(N차 이후)» 의 N ≠ 현행 회차.
      TOS-CC-C4B  currency 어휘를 쓰면서 층 태그가 «전무»한 자리.
  --  TOS-CC-PARSE 모집단 파생 자체가 실패 (fail-closed — 파생 못 하면 green 을 내지 않는다).

------------------------------------------------------------------------------
모집단 파생 규약 (왜 하드코딩이 아닌가)
------------------------------------------------------------------------------
9차의 「(4) 열거 7==7」 불변식은 **자리 셋 중 둘만 하드코딩**해 비교했고 세 번째가
stale 인 채 green 이 나왔다(A-F5).  같은 fail-open 을 되풀이하지 않기 위해 이 파일은
**어떤 자리도 상수로 적지 않는다**:

  * 현행 «버전»       — 머리말 `**버전**: vX.Y` 필드에서 파싱(문서가 «유일 소스»라 선언).
  * 현행 «회차»       — 본문 전역 `[vX.Y 에라타 N차 …]` 마커의 최대 N.
  * «미래 지향 필드» 어휘 — 머리말 `**미래 지향 필드**(…)` 괄호를 분해.
  * currency 어휘     — 본문이 성문화한 `「…」 어휘 스윕` 의 「」 안을 분해.
  * (4) 열거 원소     — 「(4) 대상 = …」 정의 자리에서 구분자(`·`)로 분해하고,
                        「(4) 열거 N원소에 … 전수 적용」 블록의 원형숫자 분해와 **교차 검증**.
  * (4) 기수 진술     — 그 열거가 사는 «코드펜스» 안에서 (4) 를 참조하며 수량을 말하는
                        모든 문장을 정규식으로 수집(자리 목록이 아니라 술어).

------------------------------------------------------------------------------
ANCHOR-1 — 자기인용 앵커 규약 (제안 · 아직 채택자 0)
------------------------------------------------------------------------------
자기인용 `:N` / `:N-M` 은 «그 좌표가 무엇을 가리킨다고 주장하는지»를 기계가 알 수 없어
완전 일반해가 없다.  그래서 규약을 제안한다::

    `:N`«앵커»            `:N-M`«앵커»

«앵커»는 피인용 행(범위)의 **축자 부분문자열**이어야 하고, 검사기는 그것을 실측 대조한다
(마크다운 강조·백틱은 양쪽 모두 정규화 후 비교).  규약을 «채택한» 인용만 C2C 로 검사하며,
미채택 인용은 위반이 아니라 **`unanchored` 계수**로 보고한다 — 100여 자리를 소급 개장하는
것은 이 검사기의 소관이 아니기 때문이다.  그 한계는 `--report` 출력과 최종 보고에 남는다.

------------------------------------------------------------------------------
운용
------------------------------------------------------------------------------
fail-closed: 위반 1건 이상이면 rc=1, 내부 예외면 rc=2 (예외를 삼키고 green 을 내지 않는다).
`--self-test` 는 뮤테이션 대조군 배터리를 돌려 **죽은 검사 0** 을 실증한다(양방향 —
«주입하면 red» 와 «수리하면 그 자리만 green»).
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import unicodedata
from collections import namedtuple
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path

logger = logging.getLogger("tos_contract_check")

# ============================================================================
# 조율 상수 (임계값은 전부 여기 선언 — 본문에 매직넘버를 두지 않는다)
# ============================================================================

#: 검사 대상 계약 문서의 저장소 상대 경로.
DEFAULT_CONTRACT_PATH = Path(
    "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md"
)

#: (4) 참조 뒤에서 기수 토큰을 찾는 창(문자 수).  «(4) 의 6개 중 셋» 처럼 한 문장에
#: 여러 수가 오면 **처음 것**이 (4) 에 결속된 기수다.
CARDINALITY_WINDOW = 160

#: C2B 앵커로 인정하는 최소 정규화 길이.  한글 8자는 문서 규모(수십만 자)에서 충분히
#: 희소하다.  낮추면 오검출, 높이면 눈이 먼다 — `--min-anchor` 로 재조정 가능.
MIN_ANCHOR_LEN = 8

#: 주장절 파싱 상한(문자).  이보다 긴 괄호는 인용의 주장절이 아니라 산문으로 본다.
MAX_CLAIM_LEN = 240

#: 자기인용 판별 시 «파일/문서 식별자» 를 되돌아보는 창(문자).
EXTERNAL_LOOKBACK = 40

#: 외부 문서 인용으로 판정하는 접미(파일 확장자)·식별자 형태.
EXTERNAL_SUFFIX_RE = re.compile(r"[\w./\-]$")
EXTERNAL_DOCID_RE = re.compile(
    r"`[^`]*(?:\.py|\.md|\.yml|\.yaml|\.csv|\.toml)[^`]*`\s*$"
)
EXTERNAL_SPECID_RE = re.compile(r"`?[A-Z]{2,}-\d{3}(?:-\d{3})?`?\s*(?:§\S*)?\s*\(?$")
#: `§5 \`:164\`` 처럼 «절» 이 앞서면 절을 가진 다른 문서를 가리킨다(이 계약의 자기인용은
#: 절 번호를 앞세우지 않는다).  정직 경계: `§12.3 :5000` 형태의 자기인용은 오분류된다.
EXTERNAL_SECTION_RE = re.compile(r"§[\d.]+\s*`?$")

# ============================================================================
# 문서 구조 정규식 (자리가 아니라 «형태»를 적는다)
# ============================================================================

VERSION_FIELD_RE = re.compile(r"\*\*버전\*\*\s*:\s*v(\d+)\.(\d+)")
VERSION_LITERAL_RE = re.compile(r"v(\d+)\.(\d+)")
ERRATA_ROUND_RE = re.compile(r"에라타\s*(\d+)\s*차")
FUTURE_FIELD_DECL_RE = re.compile(r"\*\*미래 지향 필드\*\*\s*\(([^)]*)\)")
CURRENCY_VOCAB_DECL_RE = re.compile(r"「([^」]*)」\s*어휘")
LAYER_TAG_RE = re.compile(r"현행\s*\(\s*\*{0,2}\s*(\d+)\s*차\s*이후\s*\*{0,2}\s*\)")
FENCE_RE = re.compile(r"^\s*```")

ENUM_DEF_RE = re.compile(r"\(4\)\s*대사?상\s*=")
ENUM_SWEEP_RE = re.compile(r"\(4\)\s*열거\s*(\d+)\s*원소")
ENUM_BLOCK_STOP_RE = re.compile(r"^\s*(?:\*\*\[|\(\d+\)|```)")
ENUM_REF_RE = re.compile(r"\(4\)\s*(?:의|열거|대상|목록|에)")
CARDINALITY_TOKEN_RE = re.compile(r"(\d+)\s*(개|원소)")
CIRCLED_ITEM_RE = re.compile(r"([①-⑳])\s*\*{0,2}\s*`([^`]+)`")
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
ENUM_SEPARATOR = "·"  # MIDDLE DOT — 문서 전역의 원소 구분자

#: 좌표 자릿수에 **리터럴 상·하한을 두지 않는다.**  `\d{2,4}` 처럼 상한을 두면 5자리
#: 좌표에서 «매칭 실패»가 아니라 **조용한 오탐지**가 난다(`:10234` → `:1023` 을 포착해
#: 엉뚱한 행을 검사한다).  이 문서는 이미 8,761행이고 한 회차에 수백 행이 늘어나므로,
#: 자기참조 stale 을 잡는 게이트가 스스로 자기참조 좌표를 틀리게 읽게 된다.
#: 상한을 다른 리터럴로 바꾸는 것은 처분이 아니다 — 유일한 경계는 `TOS-CC-C2R` 이
#: **문서 실제 행수에서 파생**하는 `1 <= N <= len(lines)` 다.
#: 시각 표기(`08:22:03`)는 앞 문자가 숫자라 `EXTERNAL_SUFFIX_RE` 가 이미 배제한다
#: (실측: 1자리 자기인용 0건 · 2자리 자기인용은 `:95`·`:29` 등 전부 진짜 좌표).
SELF_CITE_RE = re.compile(r":(\d+)(?:\s*[-–—~]\s*(\d+))?")
CITE_LIST_RE = re.compile(r"\[((?::\d+[\s·,]*)+)\]")
GUILLEMET_RE = re.compile(r"«([^»]{1,80})»")
ANCHOR1_RE = re.compile(r":(\d{2,4})(?:\s*[-–—~]\s*(\d{2,4}))?`?\s*«([^»]{1,120})»")

#: `**[v2.9 신설]**` 처럼 «각괄호 안» 의 버전은 편집 출처 표기(= 이력 기록)이므로
#: S-12 상 리터럴이 허용된다.  각괄호 여는 자리를 되돌아보는 창.
PROVENANCE_LOOKBACK = 4
PROVENANCE_OPEN_RE = re.compile(r"\[\**\s*$")

TABLE_ROW_RE = re.compile(r"^\s*>?\s*\|")
HISTORY_FIRST_CELL_RE = re.compile(r"^v\d+\.\d+(?:\s*에라타\s*\d+\s*차)?$")

#: 층 태그로 인정하는 표기.  `현행(N차 이후)` 외에 «vX.Y 동결 내용» / «… 층» 도 태그다.
LAYER_MARK_RES: tuple[re.Pattern[str], ...] = (
    LAYER_TAG_RE,
    re.compile(r"v\d+\.\d+\s*동결\s*내용"),
    re.compile(r"«[^»]{1,40}»\s*층"),
    re.compile(r"층\s*구분"),
    re.compile(r"\[\s*v\d+\.\d+\s*에라타\s*\d+\s*차"),
)

# ============================================================================
# 모델
# ============================================================================

Violation = namedtuple("Violation", ["rule", "path", "line", "message"])


class ContractParseError(RuntimeError):
    """모집단 파생에 필요한 구조를 문서에서 찾지 못했다 (fail-closed 사유)."""


def _normalize(text: str) -> str:
    """마크다운 강조/백틱과 유니코드 폭 차이를 지운 비교용 표현을 만든다.

    Args:
        text: 원문 조각.

    Returns:
        `*`/`` ` `` 제거 + NFKC 정규화 + 연속 공백 1칸 축약을 적용한 문자열.
    """
    stripped = text.replace("*", "").replace("`", "")
    return re.sub(r"[ \t]+", " ", unicodedata.normalize("NFKC", stripped))


# ============================================================================
# 문서 컨텍스트 — 모든 축이 공유하는 «파생된» 사실들
# ============================================================================


class ContractDoc:
    """계약 문서와 그 문서에서 **파생된** 자기기술 사실들.

    자리(행번호)를 상수로 들고 있지 않다.  현행 버전·현행 회차·어휘 목록·열거 원소는
    전부 문서 자신의 선언에서 파싱한다.
    """

    def __init__(self, text: str, display_path: str) -> None:
        """문서를 적재하고 자기기술 사실을 파생한다.

        Args:
            text: 문서 전체 텍스트.
            display_path: 진단 출력에 쓸 경로 표기.

        Raises:
            ContractParseError: 버전 필드 또는 에라타 회차 마커가 없을 때.
        """
        self.display_path = display_path
        self.lines: list[str] = text.splitlines()
        self.norm_lines: list[str] = [_normalize(line) for line in self.lines]
        self.norm_text: str = "\n".join(self.norm_lines)

        self.current_version = self._derive_current_version()
        self.current_round = self._derive_current_round()
        self.future_field_terms = self._derive_future_field_terms()
        self.currency_terms = self._derive_currency_terms()
        self.fence_spans = self._derive_fence_spans()
        self._ngram_index: frozenset[str] | None = None

    # -- 파생 ---------------------------------------------------------------

    def _derive_current_version(self) -> tuple[int, int]:
        """머리말 `**버전**: vX.Y` 를 현행 버전의 유일 소스로 읽는다."""
        matches = [
            (int(m.group(1)), int(m.group(2)))
            for line in self.lines
            for m in [VERSION_FIELD_RE.search(line)]
            if m
        ]
        if not matches:
            raise ContractParseError("머리말 '**버전**: vX.Y' 필드를 찾지 못했다")
        return matches[0]

    def _derive_current_round(self) -> int:
        """본문 전역 `에라타 N차` 마커의 최대 N 을 현행 회차로 삼는다."""
        rounds = [
            int(m.group(1)) for m in ERRATA_ROUND_RE.finditer("\n".join(self.lines))
        ]
        if not rounds:
            raise ContractParseError("'에라타 N차' 회차 마커를 찾지 못했다")
        return max(rounds)

    def _derive_future_field_terms(self) -> list[str]:
        """머리말이 스스로 열거한 «미래 지향 필드» 어휘를 분해한다."""
        terms: list[str] = []
        for line in self.lines:
            m = FUTURE_FIELD_DECL_RE.search(line)
            if not m:
                continue
            for raw in m.group(1).split(ENUM_SEPARATOR):
                raw = raw.strip()
                if not raw:
                    continue
                quoted = re.search(r'["“«]([^"”»]+)["”»]', raw)
                terms.append(quoted.group(1).strip() if quoted else raw)
        if not terms:
            raise ContractParseError(
                "머리말 '**미래 지향 필드**(…)' 선언을 찾지 못했다"
            )
        return terms

    def _derive_currency_terms(self) -> list[str]:
        """본문이 성문화한 `「…」 어휘 스윕` 의 어휘 목록을 분해한다."""
        terms: list[str] = []
        for line in self.lines:
            for m in CURRENCY_VOCAB_DECL_RE.finditer(line):
                terms.extend(t.strip() for t in m.group(1).split("/") if t.strip())
        if not terms:
            raise ContractParseError("'「…」 어휘 스윕' 성문화 자리를 찾지 못했다")
        # 중복 제거, 선언 순서 보존.
        return list(dict.fromkeys(terms))

    def _derive_fence_spans(self) -> list[tuple[int, int]]:
        """코드펜스 쌍을 (열림행, 닫힘행) 1-기반 구간 목록으로 만든다."""
        marks = [
            i for i, line in enumerate(self.lines, start=1) if FENCE_RE.match(line)
        ]
        return [(marks[i], marks[i + 1]) for i in range(0, len(marks) - 1, 2)]

    # -- 조회 ---------------------------------------------------------------

    def enclosing_fence(self, lineno: int) -> tuple[int, int] | None:
        """`lineno` 를 감싸는 코드펜스 구간(있으면)을 돌려준다."""
        for start, end in self.fence_spans:
            if start < lineno < end:
                return start, end
        return None

    def range_text(self, start: int, end: int) -> str:
        """1-기반 [start, end] 행 범위의 정규화 텍스트를 잇는다."""
        lo = max(1, start)
        hi = min(len(self.lines), end)
        return "\n".join(self.norm_lines[lo - 1 : hi])

    def ngram_index(self, size: int) -> frozenset[str]:
        """문서 전역 n-gram 집합(앵커 후보 시드).  최초 호출에서만 만든다."""
        if self._ngram_index is None:
            body = self.norm_text
            self._ngram_index = frozenset(
                body[i : i + size] for i in range(len(body) - size + 1)
            )
        return self._ngram_index

    def is_history_row(self, lineno: int) -> bool:
        """이력 표 행인지 **구조로** 판정한다.

        판정 = 마크다운 표 행이고, **첫 셀이 버전 리터럴 그 자체**인 경우.  「심사 이력」
        「변경 이력」 표는 버전을 키로 삼으므로 이 형태를 갖는다.  반면 currency 표
        (`| 6e⁗ 재결속 (v2.22 동결 내용) | … |`) 는 첫 셀이 절차 단계라 걸리지 않는다.

        Args:
            lineno: 1-기반 행 번호.

        Returns:
            이력 행이면 True.
        """
        line = self.lines[lineno - 1]
        if not TABLE_ROW_RE.match(line):
            return False
        cells = line.lstrip().lstrip(">").strip().strip("|").split("|")
        if not cells:
            return False
        first = _normalize(cells[0]).strip()
        return bool(HISTORY_FIRST_CELL_RE.match(first))


# ============================================================================
# C1 — 기수 진술 ≡ 실제 열거 크기
# ============================================================================


def _enumeration_block(doc: ContractDoc, start_line: int, after: int) -> str:
    """정의 행 `start_line` 의 `after` 오프셋부터 블록이 끝날 때까지를 잇는다."""
    chunks = [doc.lines[start_line - 1][after:]]
    for lineno in range(start_line + 1, len(doc.lines) + 1):
        line = doc.lines[lineno - 1]
        if not line.strip() or ENUM_BLOCK_STOP_RE.match(line):
            break
        chunks.append(line)
    return " ".join(chunks)


def derive_enum_elements(doc: ContractDoc) -> tuple[list[str], int, list[Violation]]:
    """「(4) 대상 = … = 아래 N개 — a · b · c …」 정의 자리에서 원소를 분해한다.

    구분자(`·`)로 나눈 각 조각의 **첫 코드 스팬**이 원소다.  N 도 이 자리에서 읽되
    비교 대상이지 신뢰 뿌리가 아니다 — 신뢰 뿌리는 분해된 원소 «개수» 다.

    Args:
        doc: 계약 문서 컨텍스트.

    Returns:
        `(원소 목록, 정의 행번호, 파생 중 발견한 위반)`.

    Raises:
        ContractParseError: 정의 자리가 없거나 하나가 아닐 때.
    """
    hits = [i for i, line in enumerate(doc.lines, start=1) if ENUM_DEF_RE.search(line)]
    if len(hits) != 1:
        raise ContractParseError(
            f"'(4) 대상 =' 정의 자리가 정확히 1개가 아니다 (실측 {len(hits)}: {hits})"
        )
    def_line = hits[0]
    m = ENUM_DEF_RE.search(doc.lines[def_line - 1])
    assert m is not None
    tail = doc.lines[def_line - 1][m.end() :]
    dash = tail.find("—")
    if dash < 0:
        raise ContractParseError(
            f"{def_line}: '(4) 대상 =' 정의 행에 원소 도입 '—' 이 없다"
        )

    block = _enumeration_block(doc, def_line, m.end() + dash + 1)
    parts = [p.strip() for p in block.split(ENUM_SEPARATOR)]
    parts = [p for p in parts if p]

    elements: list[str] = []
    violations: list[Violation] = []
    for part in parts:
        span = CODE_SPAN_RE.search(part)
        if span is None:
            violations.append(
                Violation(
                    "TOS-CC-PARSE",
                    doc.display_path,
                    def_line,
                    f"(4) 열거 분해 조각에 코드 스팬이 없다 — 분해 가정 붕괴: {part[:60]!r}",
                )
            )
            continue
        elements.append(span.group(1))
    if not elements:
        raise ContractParseError(
            f"{def_line}: (4) 열거에서 원소를 하나도 분해하지 못했다"
        )
    return elements, def_line, violations


def derive_enum_elements_secondary(doc: ContractDoc) -> tuple[list[str], int] | None:
    """「(4) 열거 N원소에 … 전수 적용」 블록의 원형숫자 분해 — 독립 2차 파생."""
    for lineno, line in enumerate(doc.lines, start=1):
        if not ENUM_SWEEP_RE.search(line):
            continue
        block = _enumeration_block(doc, lineno, 0)
        seen: dict[str, str] = {}
        for m in CIRCLED_ITEM_RE.finditer(block):
            seen.setdefault(m.group(1), m.group(2))
        if seen:
            return [seen[k] for k in sorted(seen)], lineno
    return None


def check_c1(doc: ContractDoc) -> list[Violation]:
    """C1 — (4) 를 참조하며 기수를 말하는 모든 문장을 실제 열거 크기와 대조한다."""
    elements, def_line, violations = derive_enum_elements(doc)
    actual = len(elements)

    secondary = derive_enum_elements_secondary(doc)
    if secondary is None:
        violations.append(
            Violation(
                "TOS-CC-PARSE",
                doc.display_path,
                def_line,
                "(4) 열거의 2차 독립 파생(원형숫자 블록)을 찾지 못했다 — 교차 검증 불가",
            )
        )
    else:
        secondary_elements, secondary_line = secondary
        if sorted(secondary_elements) != sorted(elements):
            violations.append(
                Violation(
                    "TOS-CC-C1X",
                    doc.display_path,
                    secondary_line,
                    "(4) 열거의 두 독립 파생이 불일치 — "
                    f"구분자 분해({def_line}) {sorted(elements)} vs "
                    f"원형숫자 분해 {sorted(secondary_elements)}",
                )
            )

    fence = doc.enclosing_fence(def_line)
    if fence is None:
        raise ContractParseError(
            f"{def_line}: (4) 열거 정의가 코드펜스 안에 없다 — 참조 모집단을 범위 한정할 수 없다"
        )
    lo, hi = fence

    statements = 0
    for lineno in range(lo + 1, hi):
        line = doc.lines[lineno - 1]
        for ref in ENUM_REF_RE.finditer(line):
            window = line[ref.end() : ref.end() + CARDINALITY_WINDOW]
            token = CARDINALITY_TOKEN_RE.search(window)
            if token is None:
                continue
            statements += 1
            claimed = int(token.group(1))
            if claimed != actual:
                violations.append(
                    Violation(
                        "TOS-CC-C1",
                        doc.display_path,
                        lineno,
                        f"(4) 열거의 기수 진술 '{token.group(0).strip()}' 이 "
                        f"실제 열거 원소 수 {actual} 와 불일치 "
                        f"(원소: {', '.join(elements)})",
                    )
                )
    logger.info(
        "C1: 열거 원소 %d개 · (4) 기수 진술 %d건 (범위 %d-%d)",
        actual,
        statements,
        lo,
        hi,
    )
    if statements == 0:
        violations.append(
            Violation(
                "TOS-CC-PARSE",
                doc.display_path,
                def_line,
                "(4) 를 참조하는 기수 진술을 하나도 수집하지 못했다 — 술어가 눈이 멀었다",
            )
        )
    return violations


# ============================================================================
# C2 — 자기인용 좌표 실측 일치
# ============================================================================


def _is_external_citation(line: str, start: int) -> bool:
    """인용 토큰 앞 문맥이 «다른 문서»를 가리키는지 판정한다."""
    if start == 0:
        return False
    prefix = line[max(0, start - EXTERNAL_LOOKBACK) : start]
    if EXTERNAL_SUFFIX_RE.search(prefix):
        return True
    return bool(
        EXTERNAL_DOCID_RE.search(prefix)
        or EXTERNAL_SPECID_RE.search(prefix)
        or EXTERNAL_SECTION_RE.search(prefix)
    )


def iter_self_citations(doc: ContractDoc) -> Iterator[tuple[int, re.Match[str]]]:
    """자기인용 좌표 토큰을 훑는다(외부 문서 인용·시각 표기는 배제)."""
    for lineno, line in enumerate(doc.lines, start=1):
        for m in SELF_CITE_RE.finditer(line):
            if _is_external_citation(line, m.start()):
                continue
            yield lineno, m


def _extract_claim(line: str, cite_start: int, cite_end: int) -> str | None:
    """인용 토큰에 붙은 «주장절»을 뽑는다.

    두 형태를 인정한다 — ``(:N-M: 주장)`` (인용을 여는 괄호 안) 과
    ``:N(주장)`` / ``` `:N`(주장) ``` (인용 뒤 괄호).  괄호는 균형 계수로 닫는다.

    Args:
        line: 인용이 있는 원문 행.
        cite_start: 인용 토큰 시작 오프셋.
        cite_end: 인용 토큰 끝 오프셋.

    Returns:
        주장절 텍스트, 없으면 None.
    """
    tail = line[cite_end:].lstrip("`")
    offset = cite_end + (len(line[cite_end:]) - len(tail))

    prefix = line[:cite_start].rstrip("`")
    opened_before = prefix.endswith("(")

    if tail.startswith(":") and opened_before:
        return _balanced_take(line, offset + 1, depth=1)
    if tail.startswith("("):
        return _balanced_take(line, offset + 1, depth=1)
    if tail.startswith(":") and not opened_before:
        return None
    return None


def _balanced_take(line: str, start: int, depth: int) -> str | None:
    """`start` 부터 괄호 깊이가 0 이 될 때까지의 내용을 돌려준다."""
    out: list[str] = []
    for ch in line[start : start + MAX_CLAIM_LEN]:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                text = "".join(out).strip()
                return text or None
        out.append(ch)
    return None


def _longest_present(
    claim: str, haystack: str, seeds: frozenset[str], size: int
) -> str | None:
    """`claim` 의 부분문자열 중 `haystack` 에 실재하는 최장(길이 ≥ size)을 찾는다."""
    best: str | None = None
    for i in range(len(claim) - size + 1):
        seed = claim[i : i + size]
        if seed not in seeds:
            continue
        if seed not in haystack:
            continue
        end = i + size
        while end < len(claim) and claim[i : end + 1] in haystack:
            end += 1
        candidate = claim[i:end]
        if best is None or len(candidate) > len(best):
            best = candidate
    return best


def check_c2(doc: ContractDoc, min_anchor: int) -> list[Violation]:
    """C2 — 자기인용 좌표가 실제로 무엇을 가리키는지 실측 대조한다."""
    violations: list[Violation] = []
    total = 0
    anchored = 0
    claimed = 0

    seeds = doc.ngram_index(min_anchor)
    last_line = len(doc.lines)

    # -- C2R: 범위 밖 좌표 --------------------------------------------------
    for lineno, m in iter_self_citations(doc):
        total += 1
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if not 1 <= start <= last_line or not start <= end <= last_line:
            violations.append(
                Violation(
                    "TOS-CC-C2R",
                    doc.display_path,
                    lineno,
                    f"자기인용 '{m.group(0)}' (파싱 :{start}-{end}) 가 문서 행 범위"
                    f"(1-{last_line}) 밖을 가리킨다",
                )
            )
            continue

        # -- C2C: ANCHOR-1 규약 채택분 ------------------------------------
        anchor_m = ANCHOR1_RE.match(doc.lines[lineno - 1], m.start())
        if anchor_m is not None:
            anchored += 1
            # 이력 행은 «무엇을 바꿨는가»를 적으므로 앵커가 «편집 前» 문자열일 수 있다
            # (예: `:5894 «아래 어느 자리에서든»→«이 문서 어디에서든»`).  설계상 부재가
            # 정상이라 C2C 를 적용하지 않는다 — 이 면제는 정직 경계로 보고한다.
            if doc.is_history_row(lineno):
                continue
            anchor = _normalize(anchor_m.group(3))
            if anchor not in doc.range_text(start, end):
                violations.append(
                    Violation(
                        "TOS-CC-C2C",
                        doc.display_path,
                        lineno,
                        f"ANCHOR-1 위반 — 앵커 «{anchor_m.group(3)}» 가 "
                        f"피인용 범위 :{start}-{end} 에 축자 부재",
                    )
                )
            continue

        # -- C2B: 주장절 최장 앵커 ----------------------------------------
        claim_raw = _extract_claim(doc.lines[lineno - 1], m.start(), m.end())
        if not claim_raw:
            continue
        claim = _normalize(claim_raw)
        if len(claim) < min_anchor:
            continue
        claimed += 1
        in_range = _longest_present(
            claim, doc.range_text(start, end), seeds, min_anchor
        )
        if in_range is not None:
            continue
        # 인용 «행 자신» 은 주장절의 원문이므로 haystack 에서 지운다.  지우지 않으면
        # 모든 주장절이 «자기 자신»과 일치해 검사가 통째로 눈이 먼다.
        haystack = "\n".join(
            "" if i + 1 == lineno else nl for i, nl in enumerate(doc.norm_lines)
        )
        anywhere = _longest_present(claim, haystack, seeds, min_anchor)
        if anywhere is None:
            continue
        elsewhere = [
            i + 1
            for i, nl in enumerate(doc.norm_lines)
            if anywhere in nl and i + 1 != lineno and not start <= i + 1 <= end
        ]
        violations.append(
            Violation(
                "TOS-CC-C2B",
                doc.display_path,
                lineno,
                f"자기인용 ':{start}"
                + (f"-{end}" if end != start else "")
                + "' 의 주장절 "
                f"«{claim_raw[:60]}» 의 최장 축자 앵커 «{anywhere}» 가 피인용 범위에 부재 — "
                f"실재 자리 {elsewhere[:5]} (좌표가 이동했다)",
            )
        )

    # -- C2A: 인용 «목록» + 병기된 포섭 술어 --------------------------------
    for lineno, line in enumerate(doc.lines, start=1):
        for lst in CITE_LIST_RE.finditer(line):
            coords = [int(c) for c in re.findall(r":(\d+)", lst.group(1))]
            if len(coords) < 2:
                continue
            terms = [
                _normalize(g.group(1)) for g in GUILLEMET_RE.finditer(line[lst.end() :])
            ]
            if not terms:
                continue
            for coord in coords:
                if coord > last_line:
                    continue
                target = doc.norm_lines[coord - 1]
                if not any(term in target for term in terms):
                    violations.append(
                        Violation(
                            "TOS-CC-C2A",
                            doc.display_path,
                            lineno,
                            f"인용 목록이 주장한 포섭 술어 {['«' + t + '»' for t in terms]} 가 "
                            f"피인용 행 :{coord} 에 실측 부재",
                        )
                    )

    logger.info(
        "C2: 자기인용 %d건 (ANCHOR-1 채택 %d · 주장절 보유 %d · 미앵커 %d)",
        total,
        anchored,
        claimed,
        total - anchored - claimed,
    )
    return violations


# ============================================================================
# C3 — 미래 지향 필드의 리터럴 버전 금지
# ============================================================================


def check_c3(doc: ContractDoc) -> list[Violation]:
    """C3 — 현행 버전에서 파생한 «미래» 판정으로 리터럴 버전을 잡는다."""
    violations: list[Violation] = []
    major, minor = doc.current_version
    forward_hits = 0

    exempt_history = 0
    for lineno, line in enumerate(doc.lines, start=1):
        history = doc.is_history_row(lineno)
        same_major_literal: str | None = None

        for m in VERSION_LITERAL_RE.finditer(line):
            found = (int(m.group(1)), int(m.group(2)))
            if found[0] != major:
                continue  # 도구 버전(v4.48·v7.0 …) — 계약 버전 네임스페이스가 아니다
            if PROVENANCE_OPEN_RE.search(
                line[max(0, m.start() - PROVENANCE_LOOKBACK) : m.start()]
            ):
                continue  # `**[v2.9 신설]**` — 편집 출처 표기 = 이력 기록(S-12)
            if same_major_literal is None and found >= (major, minor):
                # 과거 판 리터럴(«v2.4·v2.5 의 실패»)은 역사 참조다.  미래 지향 필드에서
                # 문제가 되는 것은 «현행 이상»을 리터럴로 못박는 자리다.
                same_major_literal = m.group(0)
            if found <= (major, minor):
                continue
            if history:
                # 심사 이력·변경 이력 행은 규약상 리터럴 허용(S-12).  다만 «면제했다»는
                # 사실을 계수로 남긴다 — 조용한 면제는 fail-open 과 구별되지 않는다.
                exempt_history += 1
                continue
            violations.append(
                Violation(
                    "TOS-CC-C3A",
                    doc.display_path,
                    lineno,
                    f"현행 버전 v{major}.{minor} 보다 «큰» 리터럴 '{m.group(0)}' "
                    f"(col {m.start()}) — 구성상 미래 지향 필드다 "
                    "(S-11: 판이 올라갈 때마다 stale)",
                )
            )

        if same_major_literal is None or history:
            continue
        matched = [t for t in doc.future_field_terms if t and t in line]
        if matched:
            forward_hits += 1
            violations.append(
                Violation(
                    "TOS-CC-C3B",
                    doc.display_path,
                    lineno,
                    f"머리말이 선언한 미래 지향 필드 어휘 {matched} 자리에 "
                    f"리터럴 버전 '{same_major_literal}' — «현행 버전»으로 참조해야 한다(S-11)",
                )
            )

    logger.info(
        "C3: 현행 v%d.%d · 미래 지향 어휘 %s · 어휘+리터럴 자리 %d건 · 이력 행 면제 %d건",
        major,
        minor,
        doc.future_field_terms,
        forward_hits,
        exempt_history,
    )
    return violations


# ============================================================================
# C4 — currency 층 태그 전수
# ============================================================================


def check_c4(doc: ContractDoc) -> list[Violation]:
    """C4 — currency 층 태그가 현행 회차와 정합하는지 전수 검사한다."""
    violations: list[Violation] = []
    current = doc.current_round
    tagged = 0
    swept = 0
    narrowed = 0

    for lineno, line in enumerate(doc.lines, start=1):
        tags = [(int(m.group(1)), m.group(0)) for m in LAYER_TAG_RE.finditer(line)]
        if tags:
            tagged += 1
            # 한 행 안에서 뒤에 오는 태그가 앞을 «대체»한다.  마지막 태그가 그 자리의
            # 서 있는 주장이므로, 그것만 현행 회차와 대조한다.
            standing_round, standing_text = tags[-1]
            if standing_round != current:
                violations.append(
                    Violation(
                        "TOS-CC-C4A",
                        doc.display_path,
                        lineno,
                        f"서 있는 currency 층 태그 '{standing_text}' 가 "
                        f"현행 회차 {current}차와 불일치 (8차 ⓖ 스윕 술어)",
                    )
                )
            for earlier_round, earlier_text in tags[:-1]:
                if earlier_round >= standing_round:
                    violations.append(
                        Violation(
                            "TOS-CC-C4A",
                            doc.display_path,
                            lineno,
                            f"앞선 층 태그 '{earlier_text}' 가 뒤 태그 "
                            f"'{standing_text}' 에 의해 대체되지 않는다(회차 비단조)",
                        )
                    )

        if not any(term in line for term in doc.currency_terms):
            continue
        swept += 1
        # 어휘만으로는 «이 계약의 currency 주장» 과 «미착수라는 낱말의 일반 용법» 이
        # 구별되지 않는다.  주장으로 인정하는 구조적 조건 = 같은 major 의 계약 버전
        # 리터럴을 함께 든 자리(= 판을 지목하는 문장)이고, 이력 행은 제외한다.
        claims_currency = any(
            (int(m.group(1)), int(m.group(2))) >= doc.current_version
            and int(m.group(1)) == doc.current_version[0]
            for m in VERSION_LITERAL_RE.finditer(line)
        )
        if claims_currency:
            narrowed += 1
        if not claims_currency or doc.is_history_row(lineno):
            continue
        if not any(rx.search(line) for rx in LAYER_MARK_RES):
            violations.append(
                Violation(
                    "TOS-CC-C4B",
                    doc.display_path,
                    lineno,
                    f"currency 어휘 {[t for t in doc.currency_terms if t in line]} 를 쓰면서 "
                    "층 태그가 «전무» (8차 ⓖ: 어휘 grep + 층 태그 병기)",
                )
            )

    logger.info(
        "C4: 현행 회차 %d차 · currency 어휘 %s · 태그 보유 행 %d · "
        "어휘 스윕 행 %d (그중 현행-이상 판을 지목 = C4B 모집단 %d)",
        current,
        doc.currency_terms,
        tagged,
        swept,
        narrowed,
    )
    return violations


# ============================================================================
# 오케스트레이션
# ============================================================================

CheckFn = Callable[[ContractDoc], list[Violation]]


def check_document(
    text: str,
    display_path: str,
    min_anchor: int = MIN_ANCHOR_LEN,
    skip_sweep: bool = False,
) -> list[Violation]:
    """계약 문서 텍스트에 네 축을 전부 적용한다.

    Args:
        text: 계약 문서 전체 텍스트.
        display_path: 진단 출력용 경로 표기.
        min_anchor: C2B 앵커 최소 길이.
        skip_sweep: True 면 C4B(무태그 스윕)를 위반에서 제외한다.

    Returns:
        위반 목록.  파생 자체가 실패하면 `TOS-CC-PARSE` 단일 위반을 돌려준다
        (예외를 삼키고 green 을 내지 않는다).
    """
    try:
        doc = ContractDoc(text, display_path)
    except ContractParseError as exc:
        return [Violation("TOS-CC-PARSE", display_path, 0, str(exc))]

    violations: list[Violation] = []
    axes: Sequence[tuple[str, CheckFn]] = (
        ("C1", check_c1),
        ("C2", lambda d: check_c2(d, min_anchor)),
        ("C3", check_c3),
        ("C4", check_c4),
    )
    for name, fn in axes:
        try:
            violations.extend(fn(doc))
        except ContractParseError as exc:
            violations.append(
                Violation(
                    "TOS-CC-PARSE", display_path, 0, f"{name} 모집단 파생 실패: {exc}"
                )
            )
    if skip_sweep:
        violations = [v for v in violations if v.rule != "TOS-CC-C4B"]
    return violations


def _format(violations: Iterable[Violation]) -> str:
    return "\n".join(
        f"  {v.path}:{v.line}: [{v.rule}] {v.message}"
        for v in sorted(violations, key=lambda x: (x.line, x.rule))
    )


# ============================================================================
# 뮤테이션 대조군 배터리 (--self-test)
# ============================================================================

Mutation = namedtuple(
    "Mutation", ["name", "rule", "direction", "transform", "expect"], defaults=(None,)
)


def _sub_once(text: str, old: str, new: str) -> str:
    """정확히 1회 치환한다.  대상이 1개가 아니면 대조군이 무효이므로 예외."""
    count = text.count(old)
    if count != 1:
        raise ContractParseError(
            f"뮤테이션 대상이 유일하지 않다 (count={count}): {old!r}"
        )
    return text.replace(old, new, 1)


def _sub_first(text: str, old: str, new: str) -> str:
    """첫 출현 1회를 치환한다 (0회면 대조군 무효)."""
    if old not in text:
        raise ContractParseError(f"뮤테이션 대상 부재: {old!r}")
    return text.replace(old, new, 1)


def _append(text: str, line: str) -> str:
    """문서 «끝»에 한 행을 덧붙인다.

    행 삽입을 문서 중간에 하면 뒤따르는 모든 위반의 행번호가 밀려 기준선 diff 가
    통째로 «신규»로 보인다 — 대조군의 판별력이 사라진다.  그래서 주입형 대조군은
    항상 말미에 덧붙인다.
    """
    return text.rstrip("\n") + "\n\n" + line + "\n"


def build_mutations() -> list[Mutation]:
    """각 검사 축에 대해 «주입(→red)» 과 «수리(→그 자리 green)» 양방향 대조군을 만든다."""
    return [
        # ---- C1 --------------------------------------------------------
        Mutation(
            "C1-inject-cardinality",
            "TOS-CC-C1",
            "inject",
            lambda t: _sub_once(t, "(4) 열거 7원소", "(4) 열거 9원소"),
        ),
        Mutation(
            "C1-inject-def-size",
            "TOS-CC-C1",
            "inject",
            lambda t: _sub_once(t, "«전수» = 아래 7개", "«전수» = 아래 99개"),
        ),
        Mutation(
            "C1-repair-6",
            "TOS-CC-C1",
            "repair",
            lambda t: _sub_once(t, "(4) 의 6개 중", "(4) 의 7개 중"),
        ),
        Mutation(
            "C1-inject-remove-element",
            "TOS-CC-C1",
            "inject",
            # 실제 열거에서 원소 하나를 지운다.  실제 크기를 하드코딩한 검사기라면
            # 여기서 침묵한다 — A-F5 가 적발한 fail-open 의 직접 대조군이다.
            lambda t: _sub_once(t, "· `rulesets` ·", "·"),
        ),
        Mutation(
            "C1-consistent-rename-is-silent",
            "TOS-CC-C1",
            "silent",
            # 두 파생 «양쪽» 을 함께 고치면 기수는 불변이라 조용해야 한다.
            lambda t: t.replace("`rulesets`", "`rulesets-renamed`"),
        ),
        Mutation(
            "C1X-inject-drop-element",
            "TOS-CC-C1X",
            "inject",
            lambda t: _sub_once(
                t, "**⑦`rules/branches/{target}`**", "**⑦`rules/branches/OTHER`**"
            ),
        ),
        # ---- C2 --------------------------------------------------------
        Mutation(
            "C2R-inject-out-of-range",
            "TOS-CC-C2R",
            "inject",
            lambda t: _sub_once(
                t, "[:231·:2910·:4489·:5827]", "[:231·:2910·:4489·:99999]"
            ),
        ),
        Mutation(
            "C2A-repair-5827",
            "TOS-CC-C2A",
            "repair",
            lambda t: _sub_once(
                t, "[:231·:2910·:4489·:5827]", "[:231·:2910·:4489·:5841]"
            ),
        ),
        Mutation(
            "C2A-inject-extra-coord",
            "TOS-CC-C2A",
            "inject",
            lambda t: _sub_once(
                t, "[:231·:2910·:4489·:5827]", "[:231·:2910·:4489·:5827·:5828]"
            ),
        ),
        Mutation(
            "C2B-repair-range",
            "TOS-CC-C2B",
            "repair",
            lambda t: _sub_once(t, "(:5972-5979:", "(:5986-5990:"),
        ),
        Mutation(
            "C2C-inject-bad-anchor",
            "TOS-CC-C2C",
            "inject",
            lambda t: _append(t, "앵커 대조군 `:103`«이 문자열은 103행에 없다»"),
        ),
        Mutation(
            "C2C-inject-good-anchor-is-silent",
            "TOS-CC-C2C",
            "silent",
            lambda t: _append(t, "앵커 대조군 `:103`«재결속»"),
        ),
        # ---- C3 --------------------------------------------------------
        Mutation(
            "C3A-repair-all-future",
            "TOS-CC-C3A",
            "repair",
            lambda t: t.replace("v2.23", "«현행 버전»의 다음 판"),
        ),
        Mutation(
            "C3A-inject-far-future",
            "TOS-CC-C3A",
            "inject",
            lambda t: _sub_once(
                t, "재심 대상을 리터럴 버전으로", "재심 대상(v2.99)을 리터럴 버전으로"
            ),
        ),
        Mutation(
            "C3B-inject-future-field",
            "TOS-CC-C3B",
            "inject",
            lambda t: _append(t, "대조군 — 재심 대상은 v2.22 다."),
        ),
        Mutation(
            "C3B-history-row-is-exempt",
            "TOS-CC-C3B",
            "silent",
            lambda t: _append(
                t, "| **v2.22** | 재심 대상 현재 위치 v2.22 (이력 행 대조군) |"
            ),
        ),
        Mutation(
            "C3A-history-row-is-exempt",
            "TOS-CC-C3A",
            "silent",
            lambda t: _append(t, "| **v2.22** | 다음은 v2.99 다 (이력 행 대조군) |"),
        ),
        Mutation(
            "C3A-provenance-bracket-is-exempt",
            "TOS-CC-C3A",
            "silent",
            lambda t: _append(
                t, "대조군 — **[v2.99 신설]** 편집 출처 표기는 이력 기록이다."
            ),
        ),
        # ---- C4 --------------------------------------------------------
        Mutation(
            "C4A-repair-4231",
            "TOS-CC-C4A",
            "repair",
            lambda t: _sub_once(
                t,
                "현행(**8차 이후**) 내용의 재결속",
                "현행(**9차 이후**) 내용의 재결속",
            ),
        ),
        Mutation(
            "C4A-inject-supersede-break",
            "TOS-CC-C4A",
            "inject",
            lambda t: _sub_once(
                t,
                "**현행(9차 이후) 내용은 재결속·재심 전**",
                "**현행(7차 이후) 내용은 재결속·재심 전**",
            ),
        ),
        Mutation(
            "C4B-inject-untagged-vocab",
            "TOS-CC-C4B",
            "inject",
            lambda t: _append(t, "대조군 — v2.22 판의 이 항목은 미착수 상태다."),
        ),
        Mutation(
            "C4B-tagged-vocab-is-silent",
            "TOS-CC-C4B",
            "silent",
            lambda t: _append(
                t, "대조군 — 현행(9차 이후) v2.22 판의 이 항목은 미착수 상태다."
            ),
        ),
        Mutation(
            "C4B-past-edition-vocab-is-silent",
            "TOS-CC-C4B",
            "silent",
            lambda t: _append(t, "대조군 — v2.6 당시 이 항목은 미착수였다(역사 기술)."),
        ),
        Mutation(
            "C2R-inject-bare-out-of-range",
            "TOS-CC-C2R",
            "inject",
            lambda t: _append(t, "대조군 — 자기인용 `:99999` 는 범위 밖이다."),
        ),
        # 아래 둘은 «검사기 자신의 잠복 fail-open» 대조군이다.  `\d{2,4}` 상한이 있던
        # 판에서는 `:10234` 가 `:1023` 으로 조용히 절단돼 1023행을 검사했고, 배터리
        # 29종 전부가 이 자리를 놓쳤다.  포착값을 직접 대조해 재발을 고정한다.
        Mutation(
            "C2R-capture-5digit-coordinate",
            "TOS-CC-C2R",
            "capture",
            lambda t: _append(
                t, "대조군 — 자기인용 `:10234` 를 절단 없이 포착해야 한다."
            ),
            ":10234",
        ),
        Mutation(
            "C2R-capture-5digit-range",
            "TOS-CC-C2R",
            "capture",
            lambda t: _append(
                t, "대조군 — 자기인용 `:12000-12010` 을 절단 없이 포착해야 한다."
            ),
            ":12000-12010",
        ),
        # ---- PARSE (fail-closed 방향) ------------------------------------
        Mutation(
            "PARSE-inject-version-field-gone",
            "TOS-CC-PARSE",
            "inject",
            lambda t: _sub_once(t, "> **버전**: v2.22", "> 버전 필드 삭제 대조군"),
        ),
        Mutation(
            "PARSE-inject-future-field-decl-gone",
            "TOS-CC-PARSE",
            "inject",
            lambda t: _sub_once(
                t, "**미래 지향 필드**(", "미래 지향 필드 선언 삭제 대조군("
            ),
        ),
        Mutation(
            "PARSE-inject-currency-vocab-decl-gone",
            "TOS-CC-PARSE",
            "inject",
            lambda t: t.replace("「", "『"),
        ),
        Mutation(
            "PARSE-inject-errata-markers-gone",
            "TOS-CC-PARSE",
            "inject",
            lambda t: t.replace("에라타 ", "에라타삭제대조군 "),
        ),
        Mutation(
            "PARSE-inject-enum-def-gone",
            "TOS-CC-PARSE",
            "inject",
            lambda t: _sub_once(
                t, "(4) 대상 = **배열(목록)", "(4) 삭제 대조군 **배열(목록)"
            ),
        ),
    ]


def run_self_test(text: str, display_path: str, min_anchor: int) -> int:
    """뮤테이션 배터리를 돌려 «죽은 검사 0» 을 실증한다.

    Args:
        text: 원본 계약 문서 텍스트.
        display_path: 진단 출력용 경로 표기.
        min_anchor: C2B 앵커 최소 길이.

    Returns:
        프로세스 종료 코드 (죽은 검사가 하나라도 있으면 1).
    """
    baseline = check_document(text, display_path, min_anchor)
    base_count: dict[str, int] = {}
    base_sites: dict[str, set[int]] = {}
    for v in baseline:
        base_count[v.rule] = base_count.get(v.rule, 0) + 1
        base_sites.setdefault(v.rule, set()).add(v.line)

    print(f"self-test: 기준선 위반 {len(baseline)}건")
    for rule in sorted(base_count):
        print(
            f"  기준선 {rule}: {base_count[rule]}건 (자리 {sorted(base_sites[rule])})"
        )
    print()

    dead: list[str] = []
    for mut in build_mutations():
        try:
            mutated = mut.transform(text)
        except ContractParseError as exc:
            dead.append(f"{mut.name}: 대조군 주입 실패 — {exc}")
            print(f"  [SETUP-FAIL] {mut.name} ({mut.rule}) — {exc}")
            continue

        got = check_document(mutated, display_path, min_anchor)
        got_count = sum(1 for v in got if v.rule == mut.rule)
        got_sites = {v.line for v in got if v.rule == mut.rule}
        before = base_count.get(mut.rule, 0)
        # 메시지 본문은 문서 편집으로 함께 바뀌므로 판정 피연산자로 쓰지 않는다.
        # 하중은 «그 규칙의 계수» 와 «발화 자리 집합» 이 진다.
        delta = got_count - before
        moved = got_sites - base_sites.get(mut.rule, set())

        if mut.direction == "inject":
            ok = delta > 0 or bool(moved)
            detail = f"{mut.rule} {before}→{got_count} · 신규 자리 {sorted(moved)}"
        elif mut.direction == "repair":
            ok = delta < 0 and not moved
            detail = f"{mut.rule} {before}→{got_count} · 신규 자리 {sorted(moved)}"
        elif mut.direction == "capture":
            # 계수만으로는 «절단된 좌표를 red 로 냈다» 와 «온전한 좌표를 red 로 냈다» 가
            # 구별되지 않는다.  진단 문구에서 포착값 자체를 대조한다.
            hit = [v for v in got if v.rule == mut.rule and mut.expect in v.message]
            ok = bool(hit)
            detail = f"포착값 '{mut.expect}' {'일치' if ok else '불일치'} · {mut.rule} {before}→{got_count}"
        else:  # silent — 잡으면 안 되는 변형
            ok = delta <= 0 and not moved
            detail = f"{mut.rule} {before}→{got_count} (불변이어야 한다)"

        status = "PASS" if ok else "DEAD"
        if not ok:
            dead.append(f"{mut.name} ({mut.rule}/{mut.direction}) — {detail}")
        print(f"  [{status}] {mut.name:36s} {mut.rule:14s} {mut.direction:7s} {detail}")

    print()
    total = len(build_mutations())
    if dead:
        print(f"self-test: FAIL — 뮤테이션 {total}종 중 죽은 검사 {len(dead)}건")
        for d in dead:
            print(f"  - {d}")
        return 1
    print(f"self-test: PASS — 뮤테이션 {total}종 전부 판별 · 죽은 검사 0")
    return 0


# ============================================================================
# CLI
# ============================================================================


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점.

    Args:
        argv: 인자 목록(테스트용).  None 이면 `sys.argv[1:]`.

    Returns:
        종료 코드 — 0 통과, 1 위반, 2 내부 오류.
    """
    parser = argparse.ArgumentParser(
        description="tos 완료-계약 «자기참조 stale» 게이트 (C1~C4)"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=None,
        help=f"검사할 계약 문서 (기본: <repo>/{DEFAULT_CONTRACT_PATH})",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="저장소 루트 (기본: tools/ 의 상위)",
    )
    parser.add_argument(
        "--min-anchor",
        type=int,
        default=MIN_ANCHOR_LEN,
        help=f"C2B 앵커 최소 정규화 길이 (기본 {MIN_ANCHOR_LEN})",
    )
    parser.add_argument(
        "--skip-sweep",
        action="store_true",
        help="C4B(currency 어휘 무태그 스윕)를 위반에서 제외한다",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="뮤테이션 대조군 배터리를 돌려 «죽은 검사 0» 을 실증한다",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="파생된 모집단을 함께 출력한다 (fail-open 가시화)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.report else logging.WARNING,
        format="tos-contract: %(message)s",
        stream=sys.stdout,
    )

    repo_root = (args.repo_root or Path(__file__).resolve().parent.parent).resolve()
    contract = (args.contract or repo_root / DEFAULT_CONTRACT_PATH).resolve()

    try:
        text = contract.read_text(encoding="utf-8")
    except OSError:
        logger.exception("계약 문서를 읽지 못했다: %s", contract)
        print(f"tos-contract: ERROR — 계약 문서를 읽지 못했다: {contract}")
        return 2

    try:
        rel = str(contract.relative_to(repo_root))
    except ValueError:
        rel = str(contract)

    try:
        if args.self_test:
            return run_self_test(text, rel, args.min_anchor)
        violations = check_document(text, rel, args.min_anchor, args.skip_sweep)
    except Exception:  # noqa: BLE001 — 어떤 내부 예외도 green 이 되어선 안 된다
        logger.exception("검사 중 내부 예외")
        print("tos-contract: ERROR — 내부 예외 (rc=2)")
        return 2

    if violations:
        by_rule: dict[str, int] = {}
        for v in violations:
            by_rule[v.rule] = by_rule.get(v.rule, 0) + 1
        print(f"tos-contract: FAIL — {len(violations)} violation(s)")
        print(_format(violations))
        print()
        print("  규칙별: " + " · ".join(f"{k}={by_rule[k]}" for k in sorted(by_rule)))
        print(
            f"\n계약 SoT: {rel}"
            "\n이 게이트는 «값을 고치는» 처분이 아니라 "
            "«값이 stale 해지면 시끄럽게 실패»하는 구조다."
        )
        return 1

    print("tos-contract: PASS — 자기참조 stale 위반 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
