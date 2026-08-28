"""폐기 어휘 전수 스윕 — **대조군 내장**.

심판 next_steps 3: "구 U-1a·kind·거짓 L1 참조의 **존재/부재 전수 검색 결과가
서로 일치**해야 한다."

이 도구가 존재하는 이유는 내 스윕이 두 번 연속 실패했기 때문이다:
  1회  `grep -v "UNBOUND"` 가 `BOUND/BLOCKED/UNBOUND` 줄을 통째로 걸러 `BOUND` 잔존을 놓침
  2회  `kind=WORK` 패턴만 찾아 `NORMATIVE` 단독·`WORK`화 형태를 놓침 (DEF-9)

두 번 다 **패턴이 대상보다 좁았고, "0건"을 통과로 읽었다.**
따라서 이 도구는 **0건을 신뢰하지 않는다** — 각 패턴마다 알려진 인스턴스를 심어
검출되는지 먼저 확인하고(대조군), 대조군이 실패하면 그 패턴의 결과를 폐기한다.

## v4 — S-17(다행 주사) 구현

3·4회차 결함(과잉 배제 / 과잉 포함)에 이어 **네 번째 축**이 나왔다: **주사 단위**.

  이 스윕은 **행 단위 정규식**이라 행 경계를 넘는 명제를 놓친다. 실제로 놓쳤다 —
  문서의 거짓 명제가 `L1 이상에`(한 행) / `{PACKAGE, TEST}`(다음 행) 로 갈라져 있어
  **대조군 내장 스윕조차 통과시켰고 심판이 찾았다.**

앞의 셋과 달리 **패턴을 넓혀서는 닫히지 않는다.** 교정:

  ① 각 문서를 **슬라이딩 윈도(연속 2~3행을 공백으로 이어붙인 문자열)** 로도 스캔.
     윈도 히트는 **시작 행 번호**로 보고하고 행 단위 히트와 **중복 제거**하며,
     `[다행]` 표시로 구별한다.
  ② **대조군도 대상의 실제 배치대로 심는다** — 각 probe 의 `control` 을 두 줄로
     쪼개서 심고, 그 다행 대조군이 검출되는지 확인한다. 검출되지 않으면 S-17
     구현이 실패한 것이고 **그 probe 의 결과를 폐기**한다.
     한 줄 대조군도 그대로 유지 — **둘 다 통과해야 OK**.
  ③ 분할점은 **적대적으로** 고른다: "양쪽 반쪽 어느 것도 단독으로는 매치하지 않고
     이어 붙였을 때만 매치하는" 분할을 찾는다. 그런 분할이 없으면 그 probe 의
     패턴은 단일 토큰이라 행 경계에 영향받지 않는다는 뜻이므로 **`S-17 무관`으로
     명시 기록**한다 — 중간 지점 분할로 억지 통과시키지 않는다.

사용: python sweep_deprecated_vocabulary.py <repo_root>
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

WINDOW_WIDTHS = (2, 3)


@dataclass
class Probe:
    name: str
    pattern: re.Pattern[str]
    control: str  # 심을 문자열 — 반드시 검출돼야 한다
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


@dataclass(frozen=True)
class Hit:
    doc: str
    line_no: int  # 다행 히트는 **시작 행 번호**
    text: str
    kind: str  # 활성 / 역사
    multiline: bool


def classify(line: str) -> str:
    """활성/역사 분류. **제외하지 않는다.** 판단 불가는 활성으로 접는다(fail-closed)."""
    if ACTIVE_ROW.match(line):
        return "활성"  # 계약·테스트 행은 내용과 무관하게 활성
    if HISTORY_ROW.match(line):
        return "역사"
    return "활성"


def scan_lines(docs: list[tuple[str, list[str]]], probe: Probe) -> list[Hit]:
    """행 단위 주사."""
    hits: list[Hit] = []
    for doc, lines in docs:
        for i, line in enumerate(lines, start=1):
            if probe.pattern.search(line):
                hits.append(Hit(doc, i, line.strip()[:100], classify(line), False))
    return hits


def scan_windows(
    docs: list[tuple[str, list[str]]],
    probe: Probe,
    covered: set[tuple[str, int]] | None = None,
) -> list[Hit]:
    """다행 주사 (S-17). 연속 2~3행을 공백으로 이어 붙여 스캔한다.

    `covered` 에 든 행을 하나라도 포함하는 윈도는 **중복 제거**로 건너뛴다 —
    행 단위 히트로 이미 보고된 명제를 두 번 세지 않는다. 윈도끼리도 겹치면
    먼저 보고된 쪽만 남긴다.
    """
    hits: list[Hit] = []
    seen: set[tuple[str, int]] = set(covered or ())
    for doc, lines in docs:
        for width in WINDOW_WIDTHS:
            for i in range(len(lines) - width + 1):
                span = [(doc, j) for j in range(i + 1, i + width + 1)]
                if any(key in seen for key in span):
                    continue
                joined = " ".join(x.strip() for x in lines[i : i + width])
                if probe.pattern.search(joined):
                    hits.append(Hit(doc, i + 1, joined[:120], classify(lines[i]), True))
                    seen.update(span)
    return hits


def split_control(probe: Probe) -> tuple[str, str, bool]:
    """대조군을 **대상의 실제 배치대로** 두 줄로 쪼갠다.

    반환 `(앞줄, 뒷줄, adversarial)`.
    `adversarial=True` 는 "양쪽 반쪽 어느 것도 단독 매치하지 않는" 분할을 찾았다는
    뜻이며, 그 경우에만 다행 대조군이 S-17 을 실제로 시험한다.
    찾지 못하면 중간 공백에서 쪼개되 `False` 를 돌려주고 호출부가 `S-17 무관` 으로
    기록한다 — **억지로 통과시키지 않는다.**
    """
    text = probe.control
    spaces = list(re.finditer(r"\s+", text))
    for m in spaces:
        head, tail = text[: m.start()], text[m.end() :]
        if not head or not tail:
            continue
        if not probe.pattern.search(head) and not probe.pattern.search(tail):
            return head, tail, True
    if not spaces:
        return text, "", False
    mid = min(spaces, key=lambda m: abs(m.start() - len(text) // 2))
    return text[: mid.start()], text[mid.end() :], False


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    docs: list[tuple[str, list[str]]] = []
    total = 0
    for doc in DOCS:
        text = (repo / doc).read_text(encoding="utf-8").splitlines()
        docs.append((doc, text))
        total += len(text)
        print(f"대상: {doc}  ({len(text)}행)")
    print(
        f"결속 범위 {len(DOCS)}문서 · 총 {total}행 · 주사 단위 = 행 + 윈도{list(WINDOW_WIDTHS)}\n"
    )

    failed_controls = 0
    for probe in PROBES:
        # --- 대조군 ①: 한 줄로 심는다 -----------------------------------------
        one_line = [("<대조군-한줄>", [probe.control])]
        ctl_line_ok = bool(scan_lines(one_line, probe))

        # --- 대조군 ②: 대상의 실제 배치대로 **두 줄**로 쪼개서 심는다 (S-17) ---
        head, tail, adversarial = split_control(probe)
        planted = [("<대조군-다행>", [head, tail])]
        half_hits = scan_lines(planted, probe)
        ctl_multi_ok = bool(scan_windows(planted, probe))

        print(f"[{probe.name}]")
        print(f"    {probe.note}")
        print(
            f"    한 줄 대조군 : {'OK' if ctl_line_ok else '**실패**'}   "
            f"`{probe.control}`"
        )
        print(
            f"    다행 대조군  : {'OK' if ctl_multi_ok else '**실패**'}"
            f"{'' if adversarial else '  (S-17 무관 — 아래 사유)'}"
        )
        print(f"        앞줄 `{head}`")
        print(f"        뒷줄 `{tail}`")
        if adversarial:
            print(
                "        분할 성질: 양쪽 반쪽 단독 매치 0 — 윈도가 없으면 놓치는 배치다"
            )
        else:
            print(
                f"        분할 성질: 반쪽만으로도 매치 {len(half_hits)}건 → 이 패턴은 "
                f"단일 토큰이라 행 경계에 영향받지 않는다."
            )
            print(
                "                   따라서 이 probe 에서 다행 대조군은 S-17 을 시험하지 "
                "못한다 (통과해도 무의미). 숨기지 않고 기록한다."
            )

        # 한 줄 대조군 실패, 또는 **적대적 분할이 존재하는데** 다행 대조군이 실패하면
        # 그 probe 의 결과를 폐기한다.
        discard = (not ctl_line_ok) or (adversarial and not ctl_multi_ok)
        if discard:
            failed_controls += 1
            print(
                "    → 대조군 실패. 패턴이 자기가 찾겠다는 것조차 못 잡는다. "
                "**이 probe 의 결과를 폐기한다** — 0건을 통과로 읽지 마라.\n"
            )
            continue

        # --- 본 스캔: 행 단위 + 다행 ------------------------------------------
        line_hits = scan_lines(docs, probe)
        covered = {(h.doc, h.line_no) for h in line_hits}
        window_hits = scan_windows(docs, probe, covered=covered)
        hits = sorted(
            line_hits + window_hits, key=lambda h: (h.doc, h.line_no, h.multiline)
        )
        active = [h for h in hits if h.kind == "활성"]

        if hits:
            print(
                f"    히트 {len(hits)}건  (활성 {len(active)} / 역사 {len(hits) - len(active)}"
                f" · 그중 다행 {sum(1 for h in hits if h.multiline)})"
            )
            for h in hits:
                mark = "**" if h.kind == "활성" else "  "
                tag = "[다행]" if h.multiline else "      "
                print(
                    f"    {mark}[{h.kind}]{tag} {Path(h.doc).name}:{h.line_no}  {h.text}"
                )
        else:
            print(
                "    히트 0건 (한 줄·다행 대조군이 모두 통과했으므로 이 0건은 신뢰 가능)"
            )
        print()

    print("=" * 72)
    if failed_controls:
        print(f"대조군 실패 {failed_controls}건 — 해당 probe 결과를 폐기했다")
        return 1
    print("전 패턴 대조군 통과(한 줄 + 다행) — 위 존재/부재 결과는 서로 일치한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
