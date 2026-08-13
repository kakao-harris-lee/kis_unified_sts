"""스파이크 v3.1 — 심판 v1.8 판정의 실행 증거. **입력을 문서에서 파싱한다.**

**성격**: D0 산출물 아님. 게이트 8회 연속 needs-attention, 착수 차단 유지.
코퍼스·설계 문서 모두 읽기 전용.

## v3 의 결함과 v3.1 의 교정

v3 는 `register_v18()` 에 §13.6.3 재분류표를 **손으로 전사**했다. Stop 게이트가
"E2 증거가 실제 입력을 정확히 검증하지 않는다"고 적발했고 맞다:

  - 전사가 **5행**이었는데 문서는 **6행**이다 (`UNCHK-004` 누락)
  - `DEFINED_GATES` 와 `blocks_gate` 허용값도 하드코딩이었다

**이것은 v1 스파이크가 G2 술어를 하드코딩해 거짓 결론을 낸 것과 같은 클래스이며,
그 교훈을 S-15 확장으로 문서에 써넣은 뒤 같은 도구에서 반복한 것이다.**

v3.1 은 세 입력을 전부 문서에서 파싱한다. 파싱 실패는 **중단**이지 기본값이 아니다.

답하는 것:
  E1  v1.8 T-61(=`normative_ref` 뮤테이션)이 "blocks_gate 를 무시하는 구현"을
      구별하지 못함을 보이고, 교정 대조군(=`blocks_gate` 자체 이동)이 잡음을 보인다
  E2  `blocks_gate` 값 중 evaluator 가 실재하지 않는 것 (문서 파싱 기반)
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

DOC = "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md"


@dataclass(frozen=True)
class Unchk:
    ident: str
    normative_ref: str
    closable: str
    blocks_gate: str | None


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


SECTION = re.compile(r"^#{3,4}\s")


def _section_lines(lines: list[str], heading_prefix: str) -> list[str]:
    """지정 섹션의 본문만 잘라낸다.

    §13.2 초기 등재표도 5열이라 열 수로는 구별되지 않는다 — v3.1 초판이 여기서
    fail-closed 로 중단했다(추측하지 않은 것은 옳다). 섹션으로 범위를 좁힌다.
    """
    out: list[str] = []
    inside = False
    for line in lines:
        if line.startswith(heading_prefix):
            inside = True
            continue
        if inside and SECTION.match(line):
            break
        if inside:
            out.append(line)
    if not out:
        raise SystemExit(f"파싱 중단: 섹션 '{heading_prefix}' 를 찾지 못했다")
    return out


SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


def parse_register(lines: list[str]) -> tuple[list[Unchk], list[str]]:
    """§13.6.3 재분류표. 5열: id | normative_ref | closable | blocks_gate | owner_track

    v3.3 — **행 손실 fail-open 폐쇄.**
    v3.2 는 cell 수만 막고 `startswith("| UNCHK-")` 로 **행 인식 실패를 조용히
    건너뛰었다.** 실제로 `| 나머지 | 개별 판정 | …` 행이 사라져 파서가 6행을
    보고했으나 표에는 7행이 있었다(Stop 게이트 적발).

    교정: 표의 **모든 데이터 행**을 세고, 인식하지 못한 행이 있으면 중단한다.
    와일드카드 행(`나머지`)은 버리지 않고 **별도로 반환해 가시화**한다 —
    그것이 문서의 미해소 placeholder 라는 사실 자체가 정보다.
    """
    rows: list[Unchk] = []
    wildcards: list[str] = []
    data_rows = 0

    in_fence = False
    for raw in _section_lines(lines, "#### 13.6.3"):
        # v3.5 — 들여쓰기 처리의 **양 끝을 모두** 막는다.
        #   v3.3  `raw.startswith("|")`      → 들여쓴 표 행을 세지도 못함 (과소)
        #   v3.4  `raw.strip()` 무제한        → 코드 블록 안의 `|` 행을 표로 오인 (과대)
        # 둘 다 Stop 게이트가 적발했다. 스윕에서 겪은 과잉 배제/과잉 포함과 같은 형태다.
        #
        # 경계는 Markdown 규칙으로 잡는다:
        #   - fenced code block(``` …) 안은 표가 아니다
        #   - 선행 공백 4칸 이상은 Markdown 에서 코드 블록이다 (표 행이 아니다)
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent >= 4:
            continue
        line = raw.strip()
        if not line.startswith("|") or SEPARATOR.match(line):
            continue
        cells = _cells(line)
        if cells and cells[0] == "id":      # 헤더
            continue
        data_rows += 1

        if len(cells) != 5:
            raise SystemExit(
                f"파싱 중단: §13.6.3 데이터 행이 5열이 아니다 ({len(cells)}열) — {line[:80]}"
            )

        ident = re.match(r"(UNCHK-\d+)", cells[0])
        if not ident:
            # 인식 불가 행을 **버리지 않는다.** 와일드카드로 알려진 형태만 허용하고
            # 그 외에는 중단한다 — 조용한 skip 이 곧 과소 계수다.
            if cells[0].strip() in {"나머지", "그 외", "기타"}:
                wildcards.append(line.strip())
                continue
            raise SystemExit(f"파싱 중단: 인식 불가 데이터 행 — {line[:80]}")

        ref = "" if cells[1] in {"공란", "—", ""} else cells[1]
        closable = "NO" if "NO" in cells[2] else ("YES" if "YES" in cells[2] else "")
        gate_raw = re.sub(r"[*`]", "", cells[3]).strip()
        gate = None if gate_raw in {"—", "", "-"} else gate_raw
        if not closable:
            raise SystemExit(f"파싱 중단: closable 미해석 — {line[:80]}")
        rows.append(Unchk(ident.group(1), ref, closable, gate))

    if not rows:
        raise SystemExit("파싱 중단: §13.6.3 재분류표를 찾지 못했다")

    # **행 보존 단언** — 인식 결과의 합이 데이터 행 수와 같아야 한다.
    if len(rows) + len(wildcards) != data_rows:
        raise SystemExit(
            f"파싱 중단: 행 손실 — 데이터 {data_rows}행 중 "
            f"인식 {len(rows)}+와일드카드 {len(wildcards)}"
        )
    return rows, wildcards


def parse_defined_gates(lines: list[str]) -> set[str]:
    """§4.2 게이트 표에서 실제로 정의된 게이트 이름을 모은다."""
    gates: set[str] = set()
    for line in lines:
        m = re.match(r"\|\s*(G[1-4])\b", line)
        if m:
            gates.add(m.group(1))
    if not gates:
        raise SystemExit("파싱 중단: §4.2 게이트 정의를 찾지 못했다")
    return gates


def parse_allowed_targets(lines: list[str]) -> set[str]:
    """U-8 이 선언한 blocks_gate 허용값."""
    for line in lines:
        if "허용 값" in line and "blocks_gate" not in line and "Phase 0..7" in line:
            allowed = {f"Phase {n}" for n in range(8)}
            allowed |= set(re.findall(r"\bG[1-4]\b", line))
            return allowed
    raise SystemExit("파싱 중단: U-8 허용값 선언을 찾지 못했다")


# --------------------------------------------------------------- 두 구현 후보

def impl_honest(gate: str, register: list[Unchk]) -> set[str]:
    """`blocks_gate` 를 실제로 읽는 구현."""
    return {e.ident for e in register if e.normative_ref and e.blocks_gate == gate}


def impl_ignores_blocks_gate(gate: str, register: list[Unchk]) -> set[str]:
    """`blocks_gate` 를 무시하고 모든 normative id 를 모든 게이트에 넣는 구현."""
    del gate
    return {e.ident for e in register if e.normative_ref}


IMPLS = {"honest": impl_honest, "ignores_blocks_gate": impl_ignores_blocks_gate}


# --------------------------------------------------------------- 두 대조군 후보

def t61_v18(impl, register: list[Unchk], gate: str) -> bool:
    """v1.8 T-61 — `normative_ref` 공란화. True = 뮤테이션이 검출됨."""
    before = impl(gate, register)
    mutated = [
        Unchk(e.ident, "" if e.blocks_gate == gate else e.normative_ref, e.closable, e.blocks_gate)
        for e in register
    ]
    return before != impl(gate, mutated)


def t61_corrected(impl, register: list[Unchk], gate: str, other: str) -> bool:
    """교정 대조군 — `blocks_gate` 자체를 gate→other 로 옮긴다."""
    target = next((e for e in register if e.blocks_gate == gate), None)
    if target is None:
        raise SystemExit(f"파싱 중단: blocks_gate={gate} 인 행이 없다")
    moved = [
        Unchk(e.ident, e.normative_ref, e.closable, other if e is target else e.blocks_gate)
        for e in register
    ]
    left = target.ident in impl(gate, register) and target.ident not in impl(gate, moved)
    entered = target.ident not in impl(other, register) and target.ident in impl(other, moved)
    return left and entered


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    lines = (repo / DOC).read_text(encoding="utf-8").splitlines()

    register, wildcards = parse_register(lines)
    defined = parse_defined_gates(lines)
    allowed = parse_allowed_targets(lines)

    print(f"문서 파싱: 재분류표 데이터 {len(register) + len(wildcards)}행 "
          f"(UNCHK {len(register)} + 와일드카드 {len(wildcards)}) / 정의 게이트 {sorted(defined)}")
    for raw in wildcards:
        print(f"    ⚠ 와일드카드 행(미해소 placeholder): {raw[:88]}")
    for e in register:
        print(f"    {e.ident:<12} ref={'있음' if e.normative_ref else '공란':<4} "
              f"closable={e.closable:<3} blocks_gate={e.blocks_gate}")
    print()

    print("=== E1: 대조군이 'blocks_gate 무시' 구현을 잡는가 ===")
    print(f"{'대조군':<16} {'honest':<10} {'무시 구현':<12} 판정")
    print("-" * 60)
    r_v18 = {k: t61_v18(f, register, "G2") for k, f in IMPLS.items()}
    r_fix = {k: t61_corrected(f, register, "G2", "G3") for k, f in IMPLS.items()}
    for name, res in (("T-61 (v1.8)", r_v18), ("T-61 (교정)", r_fix)):
        catches = res["honest"] and not res["ignores_blocks_gate"]
        print(f"{name:<16} {str(res['honest']):<10} {str(res['ignores_blocks_gate']):<12} "
              f"{'잡는다' if catches else '**놓친다**'}")

    print("\n=== E2: blocks_gate 고아 target (문서 파싱 기반) ===")
    print(f"  정의된 게이트      {sorted(defined)}")
    print(f"  U-8 허용값 중 미정의 {len(allowed - defined)}종")
    used = {e.blocks_gate for e in register if e.blocks_gate}
    orphan = sorted(g for g in used if g not in defined)
    print(f"  **레지스터가 실제 사용 중인 고아: {orphan}**")
    for e in register:
        if e.blocks_gate in orphan:
            print(f"      {e.ident} → blocks_gate={e.blocks_gate!r} (판정 함수 없음)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
