"""폐기 어휘 전수 스윕 — **대조군 내장**.

심판 next_steps 3: "구 U-1a·kind·거짓 L1 참조의 **존재/부재 전수 검색 결과가
서로 일치**해야 한다."

이 도구가 존재하는 이유는 내 스윕이 두 번 연속 실패했기 때문이다:
  1회  `grep -v "UNBOUND"` 가 `BOUND/BLOCKED/UNBOUND` 줄을 통째로 걸러 `BOUND` 잔존을 놓침
  2회  `kind=WORK` 패턴만 찾아 `NORMATIVE` 단독·`WORK`화 형태를 놓침 (DEF-9)

두 번 다 **패턴이 대상보다 좁았고, "0건"을 통과로 읽었다.**
따라서 이 도구는 **0건을 신뢰하지 않는다** — 각 패턴마다 알려진 인스턴스를 심어
검출되는지 먼저 확인하고(대조군), 대조군이 실패하면 그 패턴의 결과를 폐기한다.

사용: python sweep_deprecated.py <repo_root>
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# **결속 범위 전체**를 스캔한다. v3 초판은 주 문서 한 개만 보면서 "전수 스윕"이라
# 불렀고, Stop 게이트가 "실제 입력을 정확히 검증하지 않는다"고 적발했다.
# plan_scope_digest 가 2문서를 결속하므로 스윕도 2문서를 봐야 범위가 일치한다.
DOCS = [
    "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
    "docs/plans/2026-08-11-tos-completion-development-plan.md",
]

# v3.2: **어떤 히트도 조용히 버리지 않는다.**
#
# 초판은 내용 기반 HISTORY 정규식으로 행을 **제외**했다. 그 결과 활성 테스트 행
# T-58 이 본문에 "자기모순이었다"를 포함한다는 이유만으로 통째로 배제됐고,
# 스윕은 그것을 "잔존 아님"으로 보고했다(Stop 게이트 적발).
#
# 이는 직전 실패의 거울상이다:
#     1·2회  패턴이 **너무 좁아** 히트를 놓쳤다
#     3회    배제가 **너무 넓어** 히트를 떨궜다
# 둘 다 거짓 "깨끗함"을 만든다.
#
# 교정 원칙: **분류는 하되 제외는 하지 않는다.** 활성 후보와 역사 후보를 각각
# 세어 보여주고, 판단은 읽는 사람에게 남긴다.

# 활성 계약·테스트 행은 무슨 내용이 있든 역사로 접지 않는다.
ACTIVE_ROW = re.compile(r"^\|\s*~?~?(T-\d+|K-\d+|U-\d+[a-z]?|INV-C\d+|A-\d+|D-\d+)\b")
# 변경 이력 표의 행과 인용 블록만 '역사 후보'로 분류한다 (제외가 아니라 분류).
HISTORY_ROW = re.compile(r"^\|\s*(~~)?\*{0,2}v1\.\d|^>\s")


@dataclass
class Probe:
    name: str
    pattern: re.Pattern[str]
    control: str          # 심을 문자열 — 반드시 검출돼야 한다
    note: str


PROBES = [
    Probe(
        "구 U-1a 전칭 조건",
        re.compile(r"owner_track['`\s]*이?\s*['`]?미배정['`]?\s*인?\s*행이"),
        "U-1a 단, `owner_track` 이 `미배정` 인 행이 하나라도 있으면",
        "v1.8 이 §11 소비처만 지우고 정의부를 남긴 결함",
    ),
    Probe(
        "폐기 kind 어휘",
        re.compile(r"\bNORMATIVE\b|\bLIMIT\b|(?<![A-Za-z])WORK(?![A-Za-z])"),
        "kind 를 `NORMATIVE` 에서 `WORK` 로",
        "v1.8 이 정의부만 폐기하고 소비처를 남긴 결함 (DEF-9)",
    ),
    Probe(
        "거짓 L1 전칭",
        re.compile(r"L1\s*이상.{0,20}(PACKAGE|\{PACKAGE)"),
        "L1 이상은 {PACKAGE, TEST} 를 포함하므로",
        "합집합 규칙에서 거짓 — 단독 EV-L2·EV-L3 가 반례",
    ),
]


def scan(corpus: list[tuple[str, int, str]], probe: Probe) -> list[tuple[str, int, str, str]]:
    """corpus 는 (파일, 행번호, 원문). 반환에 분류(`활성`/`역사`)를 덧붙인다.

    **제외하지 않는다.** 모든 히트를 돌려주고 분류만 부여한다.
    """
    hits: list[tuple[str, int, str, str]] = []
    for doc, idx, line in corpus:
        if not probe.pattern.search(line):
            continue
        if ACTIVE_ROW.match(line):
            kind = "활성"          # 계약·테스트 행은 내용과 무관하게 활성
        elif HISTORY_ROW.match(line):
            kind = "역사"
        else:
            kind = "활성"          # 판단 불가는 활성으로 접는다 (fail-closed)
        hits.append((doc, idx, line.strip()[:100], kind))
    return hits


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    corpus: list[tuple[str, int, str]] = []
    for doc in DOCS:
        text = (repo / doc).read_text(encoding="utf-8").splitlines()
        corpus += [(doc, i, line) for i, line in enumerate(text, start=1)]
        print(f"대상: {doc}  ({len(text)}행)")
    print(f"결속 범위 {len(DOCS)}문서 · 총 {len(corpus)}행\n")

    failed_controls = 0
    for probe in PROBES:
        # --- 대조군 먼저: 알려진 인스턴스를 심어 검출되는가 -------------------
        planted = corpus + [("<대조군>", 0, probe.control)]
        control_ok = any(d == "<대조군>" for d, _, _, _ in scan(planted, probe))

        # --- 본 스캔 ---------------------------------------------------------
        hits = scan(corpus, probe)
        active = [h for h in hits if h[3] == "활성"]

        status = "OK" if control_ok else "**대조군 실패 — 이 결과는 폐기**"
        if not control_ok:
            failed_controls += 1
        print(f"[{probe.name}]  대조군 {status}")
        print(f"    {probe.note}")
        if not control_ok:
            print("    → 패턴이 자기가 찾겠다는 것조차 못 잡는다. 0건을 통과로 읽지 마라.\n")
            continue
        if hits:
            print(f"    히트 {len(hits)}건  (활성 {len(active)} / 역사 {len(hits) - len(active)})")
            for doc, line_no, text, kind in hits:
                mark = "**" if kind == "활성" else "  "
                print(f"    {mark}[{kind}] {Path(doc).name}:{line_no}  {text}")
        else:
            print("    히트 0건 (대조군이 통과했으므로 이 0건은 신뢰 가능)")
        print()

    print("=" * 72)
    if failed_controls:
        print(f"대조군 실패 {failed_controls}건 — 스윕 결과 일부를 신뢰할 수 없다")
        return 1
    print("전 패턴 대조군 통과 — 위 존재/부재 결과는 서로 일치한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
