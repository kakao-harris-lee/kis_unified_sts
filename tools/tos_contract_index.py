#!/usr/bin/env python3
"""tos Phase-0 완료-계약 문서를 읽기 위한 **파생 색인** 생성기.

`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md` 는 10,000행을
넘고 단일 행이 127KB(:264)에 달해 사람도 에이전트도 전문을 한 번에 훑을 수 없다.
이 도구는 그 문서를 **절대 수정하지 않고** 읽기 전용으로 스캔해, 헤딩·식별자·
생존/UNCITED 판정·부피·개정 밀도를 **구조적으로 파생**한 색인을 만든다.

------------------------------------------------------------------------------
설계 규율 (위반하면 이 도구의 존재 이유가 사라진다)
------------------------------------------------------------------------------
* **지목만 한다.**  자연어 요약·재기술 문장을 새로 쓰지 않는다.  헤딩 문언은
  원문에서 그대로 잘라 붙이고(축자), 나머지는 전부 좌표·개수·git 파생 사실이다.
  이 저장소는 요약 저작으로 재심을 7회 연속 실패한 이력이 있다(`dad94fd3`).
* **fail-open 금지.**  파생이 애매하면(정의 행 0개 또는 2개 이상) 하나를 임의로
  골라 조용히 넘기지 않고 `NONE`/`AMBIGUOUS` 로 **드러내서** 출력한다.
* **읽기 전용.**  계약 문서·개발계획 문서를 절대 쓰지 않는다.  이 파일 자신과
  `--out` 산출물만 `tools/` 아래에 쓴다.
* **생존/UNCITED 는 저작 판단이 아니라 파생 술어다.**  "인용이 없다"(UNCITED)와
  "죽었다"(ARCHIVE)는 다른 주장이므로, 이 도구는 후자를 **절대 출력하지 않는다**
  — 증거가 있으면 LIVE, 없으면 UNCITED 둘뿐이다.

재사용: 마크다운 파싱 기반 구조(`ContractDoc`, 헤딩 정규식)는
`tools/tos_contract_check.py` 것을 그대로 import 해서 쓴다 — 계약 문서를 다시
파싱하는 두 번째 파서를 만들지 않는다(CLAUDE.md «바퀴 재발명 금지»).
`tos_contract_check.py` 자체는 이 파일에서 절대 수정하지 않는다.

재생성 명령: ``python tools/tos_contract_index.py --out <경로>``
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# tools/ 는 패키지가 아니다(그리고 만들지 않는다 — tos_contract_check.py 의 기존
# 배치를 존중한다).  스크립트 자신의 디렉터리를 sys.path 맨 앞에 두어, 어느
# 작업 디렉터리에서 호출되든 형제 모듈을 임포트할 수 있게 한다.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tos_contract_check as tcc  # noqa: E402  (재사용 — ContractDoc·헤딩 정규식)

# ============================================================================
# 조율 상수 (매직넘버 금지 — 임계값은 전부 여기 선언)
# ============================================================================

#: 색인 대상 계약 문서 — 검사기와 같은 정본을 기본값으로 공유한다.
DEFAULT_CONTRACT_PATH: Path = tcc.DEFAULT_CONTRACT_PATH

#: 생존 판정에 볼 최근 커밋 수 기본값.
DEFAULT_COMMITS = 30

#: 생존 판정 축 (b) 가 grep 하는 저장소 상대 pathspec.
CITATION_PATHSPECS: tuple[str, ...] = ("tools/*.py", ".github/workflows/*.yml")

#: 부피 상위 보고 개수.
TOP_VOLUME_COUNT = 15

#: 산출물 헤더에 박는 staleness 판정용 키 — `--check` 가 이 키만 대조한다.
BLOB_ID_HEADER_KEY = "contract_blob_id"

#: 헤딩 한 줄에서 `#{1,6}` 레벨과 그 뒤 문언을 함께 캡처한다.  검사기의
#: `MD_HEADING_RE` 는 "헤딩이다/아니다" 판별만 하므로, 레벨·문언 절단은 이
#: 도구가 직접 한다(검사기 공개 계약을 넓히지 않는다).
HEADING_CAPTURE_RE = re.compile(r"^(\s*(?:>\s*)*)(#{1,6})\s?(.*)$")

#: 식별자 우주 — 패밀리별로 형태가 달라(`U-1a` 알파벳 접미·`L-PROTO-STALE` 내부
#: 하이픈 다어절·`R-F4` 무하이픈 접미) 하나의 정규식으로 묶지 않고 패밀리마다
#: 명시한다.  실측 근거: 코퍼스 그렙(§ 조사 단계 — 팀장 지시 4항 "선행 조사").
IDENTIFIER_FAMILY_PATTERNS: dict[str, re.Pattern[str]] = {
    "S": re.compile(r"\bS-\d+[a-z]?\b"),
    "U": re.compile(r"\bU-\d+[a-z]?\b"),
    "T": re.compile(r"\bT-\d+[a-z]?\b"),
    "OQ": re.compile(r"\bOQ-\d+[a-z]?\b"),
    "UNCHK": re.compile(r"\bUNCHK-\d+\b"),
    "L": re.compile(r"\bL-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\b"),
    "D0": re.compile(r"\bD0-[A-Za-z0-9]+\b"),
    "R-F": re.compile(r"\bR-F\d+\b"),
}

#: 정의-행 파생 규칙 ②(산문 행두)에서, 식별자 뒤에 와야 하는 "여기서 토큰이
#: 끝난다"는 경계 문자 집합.  이게 없으면 `S-2` 가 `S-26` 산문 행두에도 거짓
#: 매치된다.
_PROSE_BOUNDARY_CHARS = set(" \t*`([,.:—–«“\n")

#: 정의-행 파생 규칙 ②에서 행두를 벗길 때 제거하는 마크다운 장식 문자.
_PROSE_STRIP_CHARS = "> \t*`-•"

#: 규칙 ②가 허용하는 최대 선두 공백 폭.  이 코퍼스는 빈 줄 없이 문단을 잇는
#: 조밀한 문체를 쓰고, **줄바꿈 후 이어지는 문장(continuation)은 5칸 이상
#: 들여쓴다**(실측: S-26 정의 행 자체는 들여쓰기 0, 그 연속 행들은 5~9칸).
#: 이 문턱이 없으면 "U-17 이 묻는 것은…" 같은 **줄바꿈 중간의 우연한 어두**가
#: 정의로 오검출된다(실측 사례: :7940).
_PROSE_MAX_LEADING_WS = 2

#: 표 행 판별 — 검사기가 쓰는 것과 같은 형상(선두 `|`).
TABLE_ROW_LEADING_RE = re.compile(r"^\s*\|")

#: 버전 리터럴 개정-밀도 축.
VERSION_LITERAL_RE = re.compile(r"\bv\d+\.\d+[a-z]?\b")

#: 섹션 헤딩 문언 선두의 점-구분 숫자(예: "12.3.4", "0.1.1", "1.") — 있으면 그
#: 섹션의 "번호" 로 삼는다(생존 판정 축 (a)(b) 의 검색 토큰).  `\d+`·`(?:\.\d+)*`
#: 는 기본이 탐욕적이라 뒤에 오는 문자를 걱정할 부정 lookahead 가 필요 없다 —
#: 오히려 예전 버전의 `(?![\d.])` 는 "1. 최상위" 처럼 **최상위 절 번호 뒤에 오는
#: 마침표**(다음 숫자 세그먼트가 아니라 문장부호)까지 거부해 이 코퍼스의 모든
#: `## N. 제목` 형 최상위 헤딩에서 번호를 통째로 놓치는 실측 결함이었다.
SECTION_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)")


# ============================================================================
# 모델
# ============================================================================


@dataclass
class Section:
    """헤딩 하나가 여는 문서 구간 — 전부 파생값이다.

    Attributes:
        lineno: 헤딩 자신의 1-기반 행 번호.
        level: `#` 개수(1~6).
        heading_text: 헤딩 마커 이후 문언, **축자**(다듬지 않음).
        raw_line: 헤딩 원문 행 전체.
        end_line: 이 구간의 마지막 행(포함) — 같거나 얕은 레벨의 다음 헤딩
            직전, 없으면 문서 끝.
        number: 헤딩 문언 선두의 점-구분 숫자(없으면 None).
        fence_parity_suspect: 이 구간이 `fence_parity_suspects` 가 찾은 «코드펜스
            짝짓기 이상 구간» 과 겹치는가 — 참이면 `end_line` 경계의 신뢰도가
            낮다(이 구간 안에서 진짜 헤딩이 빠졌거나, 코드 내용이 헤딩으로
            잘못 들어왔을 수 있다).
    """

    lineno: int
    level: int
    heading_text: str
    raw_line: str
    end_line: int
    number: str | None = None
    fence_parity_suspect: bool = False

    def line_count(self) -> int:
        return self.end_line - self.lineno + 1

    def byte_count(self, lines: Sequence[str]) -> int:
        return sum(
            len(lines[i].encode("utf-8")) + 1
            for i in range(self.lineno - 1, self.end_line)
        )

    def contains(self, lineno: int) -> bool:
        return self.lineno <= lineno <= self.end_line


@dataclass
class Definition:
    """식별자 하나의 정의-행 파생 결과.

    Attributes:
        identifier: 식별자 리터럴.
        status: `"DEFINED"` | `"AMBIGUOUS"` | `"NONE"`.
        line: `DEFINED` 일 때만 채워지는 단일 정의 행.
        candidates: `AMBIGUOUS` 일 때 후보 행 전부(오름차순, 중복 제거).
        rule: `DEFINED` 일 때 어느 규칙이 맞았는지 — `"heading"` |
            `"table-row"` | `"prose-line-start"`.
        mention_count: 문서 전역에서 이 식별자 매치의 총 횟수(행이 아니라
            매치 개수).
        mention_lines: 매치가 있는 모든 행(오름차순, 중복 제거).
    """

    identifier: str
    status: str
    line: int | None
    candidates: list[int]
    rule: str | None
    mention_count: int
    mention_lines: list[int]


# ============================================================================
# 섹션 지도 파생
# ============================================================================


def fence_parity_suspects(doc: tcc.ContractDoc) -> list[tuple[int, int, str]]:
    """짝짓기 알고리즘이 «닫힘」으로 소비했지만 실제로는 다음 블록의 「열림」
    처럼 보이는 코드펜스 쌍을 찾는다 — 이 문서 자체의 저작 결함 후보.

    `ContractDoc._derive_fence_spans` 는 문서 전역의 ``` 마커를 **처음부터 끝까지
    번갈아 열림·닫힘으로** 짝짓는다(검사기 :897 과 동일 — 재사용).  이 전제는
    이 계약 문서의 일부 구간에서 실제로 깨져 있다(실측: :5972 가 열고 :5973 한
    줄 뒤 :5974 가 다시 ` ```text` 를 쓴다 — 원래 의도는 :5974 이 «닫힘» `` ` `` `` `
    이어야 다음 블록이 새로 열리는데, 저작 시점에 닫힘 마커 없이 바로 새 열림을
    썼다).  이 함수는 그 자체를 **판정하지 않고**, 「닫힘 자리의 실제 내용이
    맨 backtick-3개 만이 아니다」라는 **관측 가능한** 이상 신호로 후보를 낸다.

    Args:
        doc: 파싱된 계약 문서.

    Returns:
        `(짝짓기상 열림 행, 짝짓기상 닫힘 행, 그 닫힘 행의 실제 내용)` 목록 —
        내용이 순수 ` ``` ` 가 아닌 쌍만.
    """
    marks = [i for i, line in enumerate(doc.lines, start=1) if tcc.FENCE_RE.match(line)]
    suspects: list[tuple[int, int, str]] = []
    for i in range(0, len(marks) - 1, 2):
        open_l, close_l = marks[i], marks[i + 1]
        close_raw = doc.lines[close_l - 1].strip()
        if close_raw != "```":
            suspects.append((open_l, close_l, close_raw))
    return suspects


def _fence_suspect_zone(
    suspects: Sequence[tuple[int, int, str]],
) -> tuple[int, int] | None:
    """의심 쌍 전부를 감싸는 단일 구간(최소 열림 ~ 최대 닫힘) — 없으면 None."""
    if not suspects:
        return None
    return min(s[0] for s in suspects), max(s[1] for s in suspects)


def derive_sections(
    doc: tcc.ContractDoc, suspects: Sequence[tuple[int, int, str]] = ()
) -> list[Section]:
    """모든 헤딩(`#`~`#####`)에서 섹션 구간을 파생한다.

    구간의 끝은 "같거나 얕은 레벨의 다음 헤딩 직전"이다 — 그래서 하위 헤딩은
    상위 섹션 구간 «안»에 포함된다(관용적 마크다운 섹션 경계).

    Args:
        doc: 파싱된 계약 문서.
        suspects: `fence_parity_suspects` 결과 — 주면 그 구간과 겹치는 섹션에
            `fence_parity_suspect=True` 를 찍는다(경계 신뢰도 저하 고지).

    Returns:
        문서 순서의 `Section` 목록.
    """
    raw_headings: list[tuple[int, int, str, str]] = []
    for lineno, line in enumerate(doc.lines, start=1):
        if not _is_heading_line(doc, lineno):
            continue
        m = HEADING_CAPTURE_RE.match(line)
        if not m:
            continue
        level = len(m.group(2))
        text = m.group(3)
        raw_headings.append((lineno, level, text, line))

    zone = _fence_suspect_zone(suspects)
    sections: list[Section] = []
    total_lines = len(doc.lines)
    for idx, (lineno, level, text, raw_line) in enumerate(raw_headings):
        end_line = total_lines
        for later_lineno, later_level, _, _ in raw_headings[idx + 1 :]:
            if later_level <= level:
                end_line = later_lineno - 1
                break
        number_m = SECTION_NUMBER_RE.match(text.strip())
        overlaps_zone = zone is not None and lineno <= zone[1] and end_line >= zone[0]
        sections.append(
            Section(
                lineno=lineno,
                level=level,
                heading_text=text,
                raw_line=raw_line,
                end_line=end_line,
                number=number_m.group(1) if number_m else None,
                fence_parity_suspect=overlaps_zone,
            )
        )
    return sections


def section_for_line(sections: Sequence[Section], lineno: int) -> Section | None:
    """`lineno` 를 담는 가장 깊은(가장 좁은) 섹션을 돌려준다."""
    best: Section | None = None
    for section in sections:
        if section.contains(lineno):
            if best is None or section.level > best.level:
                best = section
    return best


def fence_suppressed_heading_candidates(doc: tcc.ContractDoc) -> list[tuple[int, str]]:
    """코드펜스 «안»으로 분류돼 `derive_sections` 가 제외한 헤딩-형상 행 전부.

    이 문서는 코드펜스 짝짓기(``` 마커를 순서대로 열림·닫힘으로 페어링)가 실제로
    깨진 구간을 갖고 있다(실측: :6136 이후 여러 구간 — `text` 펜스 안에 진짜
    헤딩을 담는 저작 관행과, 페어링 알고리즘이 전제하는 «항상 정확히 교대» 가정이
    충돌한다).  깨졌다는 사실 자체를 **fail-open 으로 삼키지 않는다** — 이 함수가
    낸 목록은 "섹션 지도가 놓쳤을 수 있는 자리"로 그대로 노출되고, 이 도구는 어느
    것이 «진짜» 헤딩인지 판정하지 않는다(그 판정은 사람 몫이다).

    Args:
        doc: 파싱된 계약 문서.

    Returns:
        `(1-기반 행 번호, 헤딩 마커 이후 문언)` 목록, 문서 순서.
    """
    out: list[tuple[int, str]] = []
    for lineno, line in enumerate(doc.lines, start=1):
        if not tcc.MD_HEADING_RE.match(line):
            continue
        if doc.enclosing_fence(lineno) is None:
            continue
        m = HEADING_CAPTURE_RE.match(line)
        out.append((lineno, m.group(3) if m else line))
    return out


# ============================================================================
# 식별자 정의-행 파생
# ============================================================================


def _all_identifier_matches(doc: tcc.ContractDoc) -> dict[str, list[int]]:
    """패밀리 정규식 전체를 돌려 식별자 → 매치 발생 행 목록(중복 포함)을 모은다."""
    hits: dict[str, list[int]] = {}
    for lineno, line in enumerate(doc.lines, start=1):
        for pattern in IDENTIFIER_FAMILY_PATTERNS.values():
            for m in pattern.finditer(line):
                hits.setdefault(m.group(0), []).append(lineno)
    return hits


def _is_heading_line(doc: tcc.ContractDoc, lineno: int) -> bool:
    """마크다운 헤딩이고 **코드펜스 안이 아니다** (검사기 :3340 과 같은 규율).

    `tcc.MD_HEADING_RE` 는 형상(`#{1,6}\\s`)만 보므로, 코드펜스 안의 파이썬 주석
    (`# comment`)이 없으면 헤딩으로 오검출된다.
    """
    line = doc.lines[lineno - 1]
    return bool(tcc.MD_HEADING_RE.match(line)) and doc.enclosing_fence(lineno) is None


def _is_heading_definition(doc: tcc.ContractDoc, lineno: int, identifier: str) -> bool:
    """규칙 ① — 헤딩 «형상» 행이고, 식별자가 백틱으로 감싸여 나타난다.

    **코드펜스 짝짓기에 기대지 않는다.**  이 문서는 코드펜스(주로 `text` 펜스로
    하니스/실행 로그 예시를 담는 블록) 안에 «진짜 헤딩」을 재차 포함하는 자리가
    실측 103건 있고(§ `fence_suppressed_heading_candidates`), 반대로 그 펜스
    페어링 자체가 문서 다른 곳(주석 안 `#`)에서 깨져 있다 — 그래서 펜스 소속
    여부는 «식별자 정의 헤딩」 판별의 신뢰 가능한 신호가 아니다.  대신 이 코퍼스의
    실제 관행(예: `` ##### `U-17` — … ``, `` ### 12.3.4 `U-15` — … ``)이 쓰는
    **백틱으로 감싼 식별자**를 요구해 오검출을 좁힌다 — 헤딩 하나에 다른 식별자가
    "…에 대해 언급"으로만 섞여 들어가는 경우(예: `§S-26` 처럼 백틱 없이 인용만
    하는 자리)를 배제한다.
    """
    line = doc.lines[lineno - 1]
    if not tcc.MD_HEADING_RE.match(line):
        return False
    return f"`{identifier}`" in line


def _is_prose_definition(doc: tcc.ContractDoc, lineno: int, identifier: str) -> bool:
    """규칙 ② — **들여쓰기 없는** 행두(장식 벗긴 뒤)가 식별자로 시작하고 뒤가 경계 문자.

    표 행·헤딩 행은 각자의 규칙이 전담하므로 여기서 제외한다.  선두 공백이
    `_PROSE_MAX_LEADING_WS` 를 넘는 행은 이 코퍼스 관행상 앞 문장의 continuation
    이므로 후보에서 제외한다(그렇지 않으면 줄바꿈 중간의 우연한 어두가 정의로
    오검출된다 — 실측: :7940).
    """
    line = doc.lines[lineno - 1]
    if tcc.MD_HEADING_RE.match(line) or TABLE_ROW_LEADING_RE.match(line):
        return False
    leading_ws = len(line) - len(line.lstrip(" \t"))
    if leading_ws > _PROSE_MAX_LEADING_WS:
        return False
    stripped = line.lstrip(_PROSE_STRIP_CHARS)
    if not stripped.startswith(identifier):
        return False
    tail_index = len(identifier)
    if tail_index == len(stripped):
        return True
    return stripped[tail_index] in _PROSE_BOUNDARY_CHARS


def _is_table_row_definition(
    doc: tcc.ContractDoc, lineno: int, identifier: str
) -> bool:
    """규칙 ③ — 표 행이고 첫 셀(장식 벗긴 뒤)이 식별자와 정확히 같다."""
    line = doc.lines[lineno - 1]
    if not TABLE_ROW_LEADING_RE.match(line):
        return False
    cells = line.strip().strip("|").split("|")
    if not cells:
        return False
    first = cells[0].strip().strip("`*").strip()
    return first == identifier


def derive_definition(
    doc: tcc.ContractDoc, identifier: str, mention_lines: Sequence[int]
) -> Definition:
    """식별자 하나의 정의-행을 세 규칙(헤딩/표-첫셀/산문-행두)으로 파생한다.

    Args:
        doc: 파싱된 계약 문서.
        identifier: 식별자 리터럴(예: `"S-26"`).
        mention_lines: 이 식별자가 등장하는 모든 행(중복 포함, 파생 전 원본).

    Returns:
        `Definition` — 후보가 정확히 1개면 `DEFINED`, 0개면 `NONE`, 2개
        이상이면 `AMBIGUOUS`(전부 나열, 하나를 임의로 고르지 않는다).
    """
    unique_lines = sorted(set(mention_lines))
    candidates: list[tuple[int, str]] = []
    for lineno in unique_lines:
        if _is_heading_definition(doc, lineno, identifier):
            candidates.append((lineno, "heading"))
        elif _is_table_row_definition(doc, lineno, identifier):
            candidates.append((lineno, "table-row"))
        elif _is_prose_definition(doc, lineno, identifier):
            candidates.append((lineno, "prose-line-start"))

    if len(candidates) == 1:
        line, rule = candidates[0]
        return Definition(
            identifier=identifier,
            status="DEFINED",
            line=line,
            candidates=[line],
            rule=rule,
            mention_count=len(mention_lines),
            mention_lines=unique_lines,
        )
    if not candidates:
        return Definition(
            identifier=identifier,
            status="NONE",
            line=None,
            candidates=[],
            rule=None,
            mention_count=len(mention_lines),
            mention_lines=unique_lines,
        )
    return Definition(
        identifier=identifier,
        status="AMBIGUOUS",
        line=None,
        candidates=[c[0] for c in candidates],
        rule=None,
        mention_count=len(mention_lines),
        mention_lines=unique_lines,
    )


def derive_all_definitions(doc: tcc.ContractDoc) -> dict[str, Definition]:
    """문서 전역의 모든 추적 식별자에 대해 `derive_definition` 을 적용한다."""
    hits = _all_identifier_matches(doc)
    return {
        identifier: derive_definition(doc, identifier, lines)
        for identifier, lines in sorted(hits.items())
    }


def locate_range(
    doc: tcc.ContractDoc, sections: Sequence[Section], definition: Definition
) -> tuple[int, int, str]:
    """`DEFINED` 정의의 «행 범위» 를 정한다.

    헤딩 정의는 그 헤딩이 여는 섹션 구간 전체가 범위다(경계가 구조로 정해진다).
    표-행·산문-행두 정의는 **단일 행만** 돌려준다 — 이 코퍼스는 문단 사이에
    빈 줄을 두지 않는 조밀한 문체를 쓰므로(실측: S-26 정의 행부터 다음 빈 줄까지
    591행, 무관한 다른 절 여럿을 관통), "블록 끝"을 구조적으로 안전하게 파생할
    방법이 없다.  없는 경계를 지어내는 대신 단일 행 + 한계 고지를 낸다.

    Args:
        doc: 파싱된 계약 문서.
        sections: `derive_sections` 결과.
        definition: `status == "DEFINED"` 인 `Definition`.

    Returns:
        `(시작 행, 끝 행, 한계 고지)`.
    """
    assert definition.line is not None
    if definition.rule == "heading":
        section = next((s for s in sections if s.lineno == definition.line), None)
        if section is not None:
            note = (
                "이 구간은 코드펜스 짝짓기 의심 구간과 겹친다 — 끝 경계"
                f"(:{section.end_line})가 실제보다 지나치게 넓거나 좁을 수 있다"
                " (§ `fence_parity_suspects`)."
                if section.fence_parity_suspect
                else ""
            )
            return definition.line, section.end_line, note
        # 이 헤딩은 `derive_sections` 의 코드펜스 게이팅에 걸려 섹션 지도에
        # 없다(§ `fence_suppressed_heading_candidates`) — 펜스 소속에 기대지
        # 않는 헤딩-형상 전용 2차 파생으로 경계를 다시 잰다.
        end = _fence_independent_heading_end(doc, definition.line)
        return (
            definition.line,
            end,
            "이 헤딩은 코드펜스 짝짓기 이상 구간에 있어 정식 섹션 지도에 없다"
            " — 펜스 소속과 무관하게 다음 헤딩-형상 행 직전까지로 범위를 다시"
            " 쟀다(2차 파생 · 사람이 원문 대조 권장).",
        )
    return (
        definition.line,
        definition.line,
        "비-헤딩 정의 — 블록 종료를 구조적으로 파생할 수 없어 단일 행만 지목한다"
        "(빈 줄 없는 조밀 문체 · 이 행부터 직접 읽어라).",
    )


def _fence_independent_heading_end(doc: tcc.ContractDoc, lineno: int) -> int:
    """`lineno` 헤딩의 끝을, 펜스 소속을 보지 «않고» 헤딩 형상만으로 다시 잰다.

    `locate_range` 가 코드펜스 게이팅에 걸려 섹션 지도에 없는 헤딩을 다룰 때만
    쓰는 대체 경로다 — 같거나 얕은 레벨의 «다음 헤딩-형상 행» 직전, 없으면
    문서 끝.
    """
    m = HEADING_CAPTURE_RE.match(doc.lines[lineno - 1])
    level = len(m.group(2)) if m else 6
    for later, line in enumerate(doc.lines[lineno:], start=lineno + 1):
        if not tcc.MD_HEADING_RE.match(line):
            continue
        later_m = HEADING_CAPTURE_RE.match(line)
        later_level = len(later_m.group(2)) if later_m else 6
        if later_level <= level:
            return later - 1
    return len(doc.lines)


# ============================================================================
# git 파생 사실
# ============================================================================


def _run_git(args: Sequence[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )


def git_blob_id(path: Path, repo_root: Path) -> str:
    """`git hash-object` 로 파일 blob id 를 잰다 — staleness 판정의 유일한 근거."""
    proc = _run_git(["hash-object", str(path)], repo_root)
    if proc.returncode != 0:
        raise RuntimeError(f"git hash-object 실패: {proc.stderr.strip()}")
    return proc.stdout.strip()


def recent_commit_messages(repo_root: Path, count: int) -> list[tuple[str, str]]:
    """최근 `count` 커밋의 `(짧은 sha, 제목+본문)` 목록."""
    proc = _run_git(
        ["log", "-n", str(count), "--pretty=format:%h%x00%s%x00%b%x01"],
        repo_root,
    )
    if proc.returncode != 0:
        return []
    out: list[tuple[str, str]] = []
    for chunk in proc.stdout.split("\x01"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        parts = chunk.split("\x00")
        sha = parts[0] if parts else ""
        subject = parts[1] if len(parts) > 1 else ""
        body = parts[2] if len(parts) > 2 else ""
        out.append((sha, f"{subject}\n{body}"))
    return out


def grep_citation_paths(
    repo_root: Path, patterns: Sequence[str]
) -> list[tuple[str, int, str]]:
    """`tools/*.py`·`.github/workflows/*.yml` 에서 패턴 중 하나라도 나오는 행.

    Args:
        repo_root: 검색 기준 저장소 루트.
        patterns: **이미 완성된 정규식 조각**(호출자가 리터럴은 `re.escape`
            까지 마친 상태) — 이 함수는 다시 이스케이프하지 않고 `|` 로만
            묶는다.  `git grep -E` 는 **POSIX ERE**(비집합 그룹 `(?:…)`·
            lookaround `(?!…)`/`(?<!…)` 미지원)라, 호출자가 넘기는 패턴은
            그 부분집합(`\\b` 단어경계는 git 이 GNU 확장으로 지원 — 실측
            확인)만 써야 한다.  괄호는 **일반** `(...)` 로 묶는다(POSIX ERE 도
            일반 그룹은 지원 — `?:` 만 못 쓴다).

    Returns:
        `(경로, 행, 내용)` 목록.  `git grep` 이 진짜 매치-없음(rc=1)이 아닌
        다른 이유로 실패하면(rc≥2 — 대개 이 함수가 못 다루는 정규식 문법이
        패턴에 섞여 들어온 것) **stderr 에 경고를 남기고** 빈 목록을 낸다 —
        조용히 «증거 없음»으로만 접지 않는다(팀장 지적 — fail-open 재발 방지).
    """
    if not patterns:
        return []
    pattern = "|".join(f"({p})" for p in patterns)
    proc = _run_git(
        ["grep", "-nE", pattern, "--", *CITATION_PATHSPECS],
        repo_root,
    )
    if proc.returncode not in (0, 1):  # 1 = 매치 없음(성공), 그 외 = 오류
        print(
            f"tos-contract-index: WARNING — git grep 이 패턴 「{pattern}」 에서 "
            f"rc={proc.returncode} 로 실패했다(정규식 미지원 문법 의심) — "
            "이 섹션의 grep 증거를 비운 채 계속한다: "
            f"{proc.stderr.strip()[:200]}",
            file=sys.stderr,
        )
        return []
    hits: list[tuple[str, int, str]] = []
    for line in proc.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        path, lineno_s, content = parts
        try:
            lineno = int(lineno_s)
        except ValueError:
            continue
        hits.append((path, lineno, content.strip()))
    return hits


# ============================================================================
# 생존/UNCITED 판정 — 파생 술어 (a)(b), 저작 판단 아님
# ============================================================================


@dataclass
class Citation:
    """섹션 하나의 생존 판정 결과와 그 근거."""

    status: str  # "LIVE" | "UNCITED"
    tokens: list[str]
    evidence: list[str]


def owned_identifiers(
    section: Section, definitions: dict[str, Definition]
) -> list[str]:
    """이 섹션이 **정의**하는(= `DEFINED` 이고 정의 행이 이 섹션 안인) 식별자들."""
    return sorted(
        ident
        for ident, d in definitions.items()
        if d.status == "DEFINED" and d.line is not None and section.contains(d.line)
    )


def _citation_search_patterns(
    section: Section, definitions: dict[str, Definition]
) -> dict[str, str]:
    """이 섹션이 «자기 것」이라 주장할 수 있는 검색 패턴 — 라벨 → 정규식.

    **운영자 지시로 교정(fail-open 결함 실측 발견 후)**: 식별자(`S-26`·`U-15`
    류)는 고유 토큰이라 단어 경계만으로 충분하다.  섹션 «번호»는 맨 숫자만으로
    찾으면 거의 모든 문서·코드에 우연히 등장한다(실측 오탐: `.github/workflows/
    devcontainer.yml` 의 `devcontainers/ci@v0.3` 가 §0.3 을, `probes_real_order.py`
    의 `default=0.4` 가 §0.4 를, 커밋 메시지의 아무 `0`·`1` 이 §0·§1 을 LIVE 로
    만들었다 — 판별력 0인 축은 없는 축보다 나쁘다).  그래서 섹션 번호는 **`§`
    접두가 실제로 붙은 형태**(`§12.3.4`·`§ 12.3.4`·`§12.3.4-R` 등)만 인용으로
    인정한다.

    패턴은 **Python `re` 와 `git grep -E`(POSIX ERE) 양쪽에서 동일하게** 쓰인다
    (커밋 메시지는 전자, `tools/`·`.github/workflows/` 는 후자로 검색 — §
    `classify_citation`).  그래서 `\\b` 만 쓴다(git 이 GNU 확장으로 지원하는
    것을 실측 확인) — Python 전용 lookaround(`(?<!\\w)`·`(?!\\d)`)는 POSIX ERE
    에 없어 `git grep` 을 rc≥2 로 깨뜨린다(초판에서 실측한 회귀 — 두 엔진에 다른
    패턴을 유지하는 대신 교집합 문법 하나로 통일한다).  대가: 더 깊은 하위 절
    인용(`§12.3.5`)이 얕은 절(`§12.3`)의 증거로도 잡힐 수 있다 — «판별력 없음»
    보다는 안전한 방향의 잔여 부정확이라 받아들인다.

    Args:
        section: 판정 대상 섹션.
        definitions: 문서 전역 식별자 정의 사상.

    Returns:
        `{라벨: 정규식 패턴}` — 라벨은 근거 문구·JSON `citation_tokens` 에 그대로
        쓰인다.
    """
    patterns: dict[str, str] = {
        ident: rf"\b{re.escape(ident)}\b"
        for ident in owned_identifiers(section, definitions)
    }
    if section.number:
        patterns[f"§{section.number}"] = rf"§\s*{re.escape(section.number)}\b"
    return patterns


def classify_citation(
    section: Section,
    definitions: dict[str, Definition],
    commits: Sequence[tuple[str, str]],
    repo_root: Path,
) -> Citation:
    """섹션 하나를 LIVE/UNCITED 로 파생한다 (근거 (a) 커밋 메시지, (b) tools/workflows grep).

    Args:
        section: 판정 대상 섹션.
        definitions: 문서 전역 식별자 정의 사상.
        commits: `recent_commit_messages` 결과.
        repo_root: `tools/`·`.github/` grep 에 쓸 저장소 루트.

    Returns:
        `Citation` — 근거 0건이면 `UNCITED`(«죽었다» 가 아니라 «인용 없음»).
        판별력 있는 검색 패턴이 하나도 없어도(자기 정의 식별자 0 · 번호 없음)
        `UNCITED` — LIVE 를 후하게 주지 않는다.
    """
    patterns = _citation_search_patterns(section, definitions)
    if not patterns:
        return Citation(status="UNCITED", tokens=[], evidence=[])

    evidence: list[str] = []
    compiled = {label: re.compile(p) for label, p in patterns.items()}
    for sha, message in commits:
        for label, regex in compiled.items():
            if regex.search(message):
                subject = message.splitlines()[0] if message.splitlines() else ""
                evidence.append(f"commit {sha} 「{label}」 인용 — {subject[:72]}")
                break  # 커밋 하나당 근거 한 줄이면 충분(전건 나열은 소음)

    for path, lineno, content in grep_citation_paths(
        repo_root, list(patterns.values())
    ):
        evidence.append(f"{path}:{lineno} — {content[:88]}")

    status = "LIVE" if evidence else "UNCITED"
    return Citation(status=status, tokens=list(patterns.keys()), evidence=evidence)


# ============================================================================
# 부피·개정 밀도
# ============================================================================


def top_sections_by_bytes(
    sections: Sequence[Section], lines: Sequence[str], count: int
) -> list[Section]:
    return sorted(sections, key=lambda s: -s.byte_count(lines))[:count]


def top_lines_by_bytes(lines: Sequence[str], count: int) -> list[tuple[int, int, str]]:
    """`(1-기반 행 번호, 바이트 수, 앞부분 미리보기)` 상위 `count` 개."""
    sized = [(i + 1, len(line.encode("utf-8"))) for i, line in enumerate(lines)]
    sized.sort(key=lambda t: -t[1])
    out: list[tuple[int, int, str]] = []
    for lineno, size in sized[:count]:
        preview = lines[lineno - 1][:96]
        out.append((lineno, size, preview))
    return out


@dataclass
class RevisionDensity:
    version_literals: int
    errata_markers: int
    review_markers: int  # "심판"
    rereview_markers: int  # "재심"


def revision_density(section: Section, lines: Sequence[str]) -> RevisionDensity:
    text = "\n".join(lines[section.lineno - 1 : section.end_line])
    return RevisionDensity(
        version_literals=len(VERSION_LITERAL_RE.findall(text)),
        errata_markers=text.count("에라타"),
        review_markers=text.count("심판"),
        rereview_markers=text.count("재심"),
    )


# ============================================================================
# --locate
# ============================================================================


def resolve_locate_target(
    doc: tcc.ContractDoc,
    sections: Sequence[Section],
    definitions: dict[str, Definition],
    target: str,
) -> Definition:
    """`--locate` 인자 하나(식별자 또는 `§`절번호)를 `Definition` 으로 푼다.

    `§` 접두는 헤딩 선두 절번호 조회로 다룬다 — 식별자 패밀리와 별개 우주다.

    Args:
        doc: 파싱된 계약 문서.
        sections: `derive_sections` 결과.
        definitions: `derive_all_definitions` 결과.
        target: CLI 로 받은 원문 인자.

    Returns:
        `Definition` (절번호 조회는 즉석에서 합성한다 — 식별자 사전에 없으므로).

    Raises:
        SystemExit: 식별자가 어느 추적 패밀리에도 속하지 않을 때(오타 방지).
    """
    if target.startswith("§"):
        # 절번호는 식별자 3규칙(헤딩/표/산문)이 아니라 **섹션 지도 자신**이 이미
        # 정확히 아는 사실이다(`Section.number`) — 헤딩 문언이 번호를 백틱으로
        # 감싸지 않으므로(예: "### 12.3.4 `U-15` — …") 일반 식별자 규칙을 그대로
        # 돌리면 항상 NONE 이 난다.  섹션 지도에서 직접 조회한다.
        number = target[1:]
        matches = [s for s in sections if s.number == number]
        mention_count = len(
            re.findall(rf"(?<!\d){re.escape(number)}(?!\d)", "\n".join(doc.lines))
        )
        if len(matches) == 1:
            s = matches[0]
            return Definition(
                identifier=target,
                status="DEFINED",
                line=s.lineno,
                candidates=[s.lineno],
                rule="heading",
                mention_count=mention_count,
                mention_lines=[s.lineno],
            )
        if not matches:
            return Definition(
                identifier=target,
                status="NONE",
                line=None,
                candidates=[],
                rule=None,
                mention_count=mention_count,
                mention_lines=[],
            )
        return Definition(
            identifier=target,
            status="AMBIGUOUS",
            line=None,
            candidates=[s.lineno for s in matches],
            rule=None,
            mention_count=mention_count,
            mention_lines=[s.lineno for s in matches],
        )

    if target in definitions:
        return definitions[target]

    if not any(p.fullmatch(target) for p in IDENTIFIER_FAMILY_PATTERNS.values()):
        raise SystemExit(
            f"tos-contract-index: ERROR — «{target}」 는 추적 식별자 패밀리"
            f" ({', '.join(IDENTIFIER_FAMILY_PATTERNS)}) 어디에도 속하지 않는다"
            " (오타 의심 — §접두는 절번호 조회)"
        )
    return Definition(
        identifier=target,
        status="NONE",
        line=None,
        candidates=[],
        rule=None,
        mention_count=0,
        mention_lines=[],
    )


def format_locate(
    doc: tcc.ContractDoc,
    sections: Sequence[Section],
    contract_path: Path,
    definition: Definition,
) -> tuple[str, int]:
    """`--locate` 출력 문자열과 종료 코드를 만든다.

    Returns:
        `(출력, rc)` — rc 0 = 유일 정의, 3 = AMBIGUOUS, 4 = NONE.
    """
    quoted = str(contract_path)
    if definition.status == "DEFINED":
        start, end, note = locate_range(doc, sections, definition)
        lines_out = [f"sed -n '{start},{end}p' {quoted}"]
        lines_out.append(
            f"# {definition.identifier}: 규칙={definition.rule} · 언급 {definition.mention_count}회"
        )
        if note:
            lines_out.append(f"# 한계: {note}")
        return "\n".join(lines_out), 0
    if definition.status == "AMBIGUOUS":
        lines_out = [
            f"# {definition.identifier}: AMBIGUOUS — 후보 {len(definition.candidates)}개"
            " (하나를 임의로 고르지 않는다)"
        ]
        for c in definition.candidates:
            lines_out.append(f"sed -n '{c},{c}p' {quoted}")
        return "\n".join(lines_out), 3
    lines_out = [f"# {definition.identifier}: NONE — 정의 규칙 3종 무매치"]
    if definition.mention_lines:
        lines_out.append(
            f"# 언급 {definition.mention_count}회, 첫 언급 행 {definition.mention_lines[0]}"
        )
        lines_out.append(
            f"sed -n '{definition.mention_lines[0]},{definition.mention_lines[0]}p' {quoted}"
        )
    else:
        lines_out.append("# 문서에 전혀 등장하지 않는다")
    return "\n".join(lines_out), 4


# ============================================================================
# 색인 조립 (md/json 공용 중간 표현)
# ============================================================================


@dataclass
class IndexReport:
    contract_path: Path
    blob_id: str
    line_count: int
    byte_count: int
    generated_at: str
    generated_command: str
    commits_considered: int
    sections: list[Section]
    citations: dict[int, Citation]  # section.lineno -> Citation
    definitions: dict[str, Definition]
    top_sections: list[Section]
    top_lines: list[tuple[int, int, str]]
    density: dict[int, RevisionDensity]  # section.lineno -> density
    fence_suppressed: list[tuple[int, str]]
    fence_suspects: list[tuple[int, int, str]]


def build_report(
    contract_path: Path, repo_root: Path, commits: int, argv_display: str
) -> IndexReport:
    """파일을 한 번 읽어 전체 색인을 조립한다 (전체 파이프라인의 오케스트레이터)."""
    text = contract_path.read_text(encoding="utf-8")
    doc = tcc.ContractDoc(text, str(contract_path))
    suspects = fence_parity_suspects(doc)
    sections = derive_sections(doc, suspects)
    definitions = derive_all_definitions(doc)
    commit_log = recent_commit_messages(repo_root, commits)
    citations = {
        s.lineno: classify_citation(s, definitions, commit_log, repo_root)
        for s in sections
    }
    density = {s.lineno: revision_density(s, doc.lines) for s in sections}
    byte_count = len(text.encode("utf-8"))
    return IndexReport(
        contract_path=contract_path,
        blob_id=git_blob_id(contract_path, repo_root),
        line_count=len(doc.lines),
        byte_count=byte_count,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds") + "Z",
        generated_command=argv_display,
        commits_considered=commits,
        fence_suppressed=fence_suppressed_heading_candidates(doc),
        fence_suspects=suspects,
        sections=sections,
        citations=citations,
        definitions=definitions,
        top_sections=top_sections_by_bytes(sections, doc.lines, TOP_VOLUME_COUNT),
        top_lines=top_lines_by_bytes(doc.lines, TOP_VOLUME_COUNT),
        density=density,
    )


# ============================================================================
# 렌더링 — markdown
# ============================================================================


def render_markdown(report: IndexReport) -> str:
    """`IndexReport` 를 markdown 색인으로 렌더링한다 (전부 지목 — 재기술 없음)."""
    lines: list[str] = []
    lines.append("<!-- 이 파일은 생성물이다 · 손으로 고치지 마라 -->")
    lines.append(
        "<!-- 재생성: python tools/tos_contract_index.py "
        f"--contract {report.contract_path} --out <이 경로> -->"
    )
    lines.append(f"# tos 완료-계약 파생 색인 — `{report.contract_path}`")
    lines.append("")
    lines.append("## 헤더")
    lines.append(f"- `{BLOB_ID_HEADER_KEY}`: `{report.blob_id}`")
    lines.append(f"- 행수: {report.line_count}")
    lines.append(f"- 바이트: {report.byte_count}")
    lines.append(f"- 생성 시각(UTC): {report.generated_at}")
    lines.append(f"- 생성 명령: `{report.generated_command}`")
    lines.append(f"- 생존 판정 대상 최근 커밋 수: {report.commits_considered}")
    lines.append("")

    lines.append("## 섹션 지도 · 생존 판정 · 개정 밀도")
    lines.append(
        "| 레벨 | 행범위 | 행수 | 바이트 | 헤딩 문언(축자) | 펜스의심 | 생존 | 근거"
        " | v리터럴 | 에라타 | 심판 | 재심 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    doc_lines_for_bytes = report.contract_path.read_text(encoding="utf-8").splitlines()
    for section in report.sections:
        citation = report.citations[section.lineno]
        dens = report.density[section.lineno]
        heading_escaped = section.heading_text.replace("|", "\\|")
        evidence = citation.evidence[0] if citation.evidence else "—"
        evidence = evidence.replace("|", "\\|")
        fence_flag = "⚠" if section.fence_parity_suspect else "—"
        # 행범위 칸 자체에 이상 고지를 박는다 — 별도 열만 두면 스캔하다 놓친다
        # (틀린 끝 경계를 «사실처럼» 내지 않기 위한 조치, 운영자 지시).
        range_cell = f"{section.lineno}-{section.end_line}"
        if section.fence_parity_suspect:
            range_cell += " (⚠ 경계 미확정)"
        lines.append(
            f"| {section.level} | {range_cell} "
            f"| {section.line_count()} | {section.byte_count(doc_lines_for_bytes)} "
            f"| {heading_escaped} | {fence_flag} | {citation.status} | {evidence} "
            f"| {dens.version_literals} | {dens.errata_markers} "
            f"| {dens.review_markers} | {dens.rereview_markers} |"
        )
    lines.append("")

    lines.append("## 식별자 색인")
    lines.append("| 식별자 | 상태 | 정의 행 | 규칙 | 언급 횟수 | 소속 섹션 |")
    lines.append("|---|---|---|---|---|---|")
    for identifier, d in sorted(report.definitions.items()):
        def_section = (
            section_for_line(report.sections, d.line)
            if d.status == "DEFINED" and d.line is not None
            else None
        )
        section_label = (
            f"{def_section.lineno} {def_section.heading_text[:48]}".replace("|", "\\|")
            if def_section is not None
            else "—"
        )
        if d.status == "DEFINED":
            def_col = str(d.line)
        elif d.status == "AMBIGUOUS":
            def_col = "AMBIGUOUS: " + ",".join(str(c) for c in d.candidates)
        else:
            def_col = "NONE"
        lines.append(
            f"| {identifier} | {d.status} | {def_col} | {d.rule or '—'} "
            f"| {d.mention_count} | {section_label} |"
        )
    lines.append("")

    lines.append(f"## 부피 상위 섹션 {TOP_VOLUME_COUNT}")
    lines.append("| 순위 | 행범위 | 바이트 | 헤딩 문언(축자) |")
    lines.append("|---|---|---|---|")
    for rank, section in enumerate(report.top_sections, start=1):
        heading_escaped = section.heading_text.replace("|", "\\|")
        range_cell = f"{section.lineno}-{section.end_line}"
        if section.fence_parity_suspect:
            range_cell += " (⚠ 경계 미확정)"
        lines.append(
            f"| {rank} | {range_cell} "
            f"| {section.byte_count(doc_lines_for_bytes)} | {heading_escaped} |"
        )
    lines.append("")

    lines.append(f"## 부피 상위 단일 행 {TOP_VOLUME_COUNT}")
    lines.append("| 순위 | 행 | 바이트 | 미리보기(축자·잘림) |")
    lines.append("|---|---|---|---|")
    for rank, (lineno, size, preview) in enumerate(report.top_lines, start=1):
        preview_escaped = preview.replace("|", "\\|")
        lines.append(f"| {rank} | {lineno} | {size} | {preview_escaped} |")
    lines.append("")

    lines.append(
        f"## 코드펜스 내부 헤딩-형상 행 — 미해결 ({len(report.fence_suppressed)}건)"
    )
    lines.append(
        "이 문서의 ``` 펜스 짝짓기는 일부 구간에서 깨져 있다(실측 — 상세는 "
        "`fence_suppressed_heading_candidates` docstring). 아래 행은 헤딩 «형상»"
        "(`#{1,6}\\s`)이지만 파생상 코드펜스 «안»으로 분류돼 위 섹션 지도·식별자"
        " 헤딩-정의 판정에서 제외됐다. **이 도구는 어느 것이 진짜 헤딩인지 판정하지"
        " 않는다** — 사람이 원문을 직접 대조하라."
    )
    lines.append("")
    lines.append("| 행 | 헤딩-형상 문언(축자) |")
    lines.append("|---|---|")
    for lineno, text in report.fence_suppressed:
        text_escaped = text.replace("|", "\\|")
        lines.append(f"| {lineno} | {text_escaped} |")
    lines.append("")

    lines.append(f"## 코드펜스 짝짓기 의심 쌍 ({len(report.fence_suspects)}건)")
    lines.append(
        "«짝짓기상 닫힘» 자리의 실제 내용이 순수 ` ``` ` 가 아닌 쌍 — 다음 블록의"
        " «열림» 을 짝짓기 알고리즘이 닫힘으로 잘못 소비했을 가능성의 관측 신호."
        " 위 섹션 지도에서 `fence_parity_suspect=True` 로 찍힌 구간의 근거가 여기다."
    )
    lines.append("")
    lines.append("| 열림 행 | 짝짓기상 닫힘 행 | 그 행의 실제 내용 |")
    lines.append("|---|---|---|")
    for open_l, close_l, content in report.fence_suspects:
        content_escaped = content.replace("|", "\\|")
        lines.append(f"| {open_l} | {close_l} | `{content_escaped}` |")
    lines.append("")

    return "\n".join(lines) + "\n"


# ============================================================================
# 렌더링 — json
# ============================================================================


def render_json(report: IndexReport) -> str:
    """`IndexReport` 를 JSON 색인으로 렌더링한다."""
    payload: dict[str, object] = {
        BLOB_ID_HEADER_KEY: report.blob_id,
        "contract_path": str(report.contract_path),
        "line_count": report.line_count,
        "byte_count": report.byte_count,
        "generated_at": report.generated_at,
        "generated_command": report.generated_command,
        "commits_considered": report.commits_considered,
        "generated_note": "이 파일은 생성물이다 — 손으로 고치지 마라",
        "sections": [
            {
                "level": s.level,
                "line_start": s.lineno,
                "line_end": s.end_line,
                "line_count": s.line_count(),
                "heading_text": s.heading_text,
                "number": s.number,
                "fence_parity_suspect": s.fence_parity_suspect,
                "citation_status": report.citations[s.lineno].status,
                "citation_tokens": report.citations[s.lineno].tokens,
                "citation_evidence": report.citations[s.lineno].evidence,
                "revision_density": {
                    "version_literals": report.density[s.lineno].version_literals,
                    "errata_markers": report.density[s.lineno].errata_markers,
                    "review_markers": report.density[s.lineno].review_markers,
                    "rereview_markers": report.density[s.lineno].rereview_markers,
                },
            }
            for s in report.sections
        ],
        "identifiers": {
            identifier: {
                "status": d.status,
                "line": d.line,
                "candidates": d.candidates,
                "rule": d.rule,
                "mention_count": d.mention_count,
                "mention_lines": d.mention_lines,
            }
            for identifier, d in sorted(report.definitions.items())
        },
        "top_sections_by_bytes": [
            {
                "line_start": s.lineno,
                "line_end": s.end_line,
                "heading_text": s.heading_text,
            }
            for s in report.top_sections
        ],
        "top_lines_by_bytes": [
            {"line": lineno, "bytes": size, "preview": preview}
            for lineno, size, preview in report.top_lines
        ],
        "fence_suppressed_heading_candidates": {
            "note": (
                "코드펜스 짝짓기가 깨진 구간이 있다 — 이 목록은 헤딩 형상이지만"
                " 코드펜스 안으로 분류돼 sections/identifiers 판정에서 제외된 행이다."
                " 진위 판정은 하지 않는다."
            ),
            "lines": [
                {"line": lineno, "heading_text": text}
                for lineno, text in report.fence_suppressed
            ],
        },
        "fence_parity_suspects": [
            {"open_line": open_l, "close_line": close_l, "close_line_content": content}
            for open_l, close_l, content in report.fence_suspects
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


# ============================================================================
# --check
# ============================================================================


def check_staleness(
    out_path: Path, contract_path: Path, repo_root: Path
) -> tuple[bool, str]:
    """`out_path` 산출물이 `contract_path` 의 현재 blob 기준으로 최신인지 검증.

    Returns:
        `(최신인가, 진단 메시지)`.
    """
    if not out_path.exists():
        return False, f"산출물이 없다: {out_path}"
    text = out_path.read_text(encoding="utf-8")
    stored: str | None = None
    if out_path.suffix == ".json":
        try:
            stored = json.loads(text).get(BLOB_ID_HEADER_KEY)
        except json.JSONDecodeError as exc:
            return False, f"산출물 JSON 파싱 실패: {exc}"
    else:
        m = re.search(rf"`{BLOB_ID_HEADER_KEY}`:\s*`([0-9a-f]+)`", text)
        stored = m.group(1) if m else None
    if not stored:
        return False, f"산출물에서 `{BLOB_ID_HEADER_KEY}` 를 찾지 못했다 — 손상 의심"

    current = git_blob_id(contract_path, repo_root)
    if stored == current:
        return True, f"최신 — blob {current}"
    return False, f"STALE — 산출물 blob {stored} != 현재 blob {current} (재생성 필요)"


# ============================================================================
# CLI
# ============================================================================


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점.

    Args:
        argv: 인자 목록(테스트용). `None` 이면 `sys.argv[1:]`.

    Returns:
        종료 코드 — 0 정상, `--locate` 는 0/3/4, `--check` 는 0/1, 그 외 오류 2.
    """
    parser = argparse.ArgumentParser(
        description="tos 완료-계약 문서의 파생 색인 생성기 (읽기 전용 · docs/ 무접촉)"
    )
    parser.add_argument(
        "--contract", type=Path, default=None, help="색인할 계약 문서 경로"
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="색인을 쓸 경로(미지정 = stdout)"
    )
    parser.add_argument(
        "--check", action="store_true", help="--out 산출물이 최신인지만 검증"
    )
    parser.add_argument(
        "--locate",
        metavar="ID",
        default=None,
        help="식별자 또는 §절번호 하나의 정의 행 범위만 출력",
    )
    parser.add_argument(
        "--commits",
        type=int,
        default=DEFAULT_COMMITS,
        help="생존 판정에 볼 최근 커밋 수",
    )
    parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="--out 미지정 시 stdout 형식",
    )
    args = parser.parse_args(argv)

    repo_root = tcc.default_repo_root()
    contract_path = (args.contract or repo_root / DEFAULT_CONTRACT_PATH).resolve()
    if not contract_path.exists():
        print(f"tos-contract-index: ERROR — 계약 문서가 없다: {contract_path}")
        return 2

    if args.check:
        if args.out is None:
            print("tos-contract-index: ERROR — --check 는 --out 산출물 경로가 필요하다")
            return 2
        fresh, message = check_staleness(args.out, contract_path, repo_root)
        print(f"tos-contract-index: {message}")
        return 0 if fresh else 1

    argv_display = "python tools/tos_contract_index.py " + " ".join(
        sys.argv[1:] if argv is None else argv
    )

    if args.locate is not None:
        text = contract_path.read_text(encoding="utf-8")
        doc = tcc.ContractDoc(text, str(contract_path))
        sections = derive_sections(doc, fence_parity_suspects(doc))
        definitions = derive_all_definitions(doc)
        definition = resolve_locate_target(doc, sections, definitions, args.locate)
        output, rc = format_locate(doc, sections, contract_path, definition)
        print(output)
        return rc

    try:
        report = build_report(contract_path, repo_root, args.commits, argv_display)
    except tcc.ContractParseError as exc:
        print(f"tos-contract-index: ERROR — 계약 문서 파생 실패: {exc}")
        return 2

    rendered = render_json(report) if args.format == "json" else render_markdown(report)
    if args.out is not None:
        args.out.write_text(rendered, encoding="utf-8")
        print(
            f"tos-contract-index: 색인을 썼다 — {args.out} ({len(rendered.encode('utf-8'))} bytes)"
        )
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
