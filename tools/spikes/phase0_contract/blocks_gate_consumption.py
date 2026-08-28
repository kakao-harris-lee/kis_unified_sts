"""스파이크 v4 — 심판 v1.9 판정의 실행 증거. **입력을 문서에서 파싱한다.**

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

## v3.2~v3.5 의 결함 이력 (안전장치의 출처 — 지우지 말 것)

  v3.2  cell 수만 막고 `startswith("| UNCHK-")` 로 **행 인식 실패를 조용히 skip**
        → `| 나머지 | 개별 판정 | …` 행이 사라져 6행 보고 / 실제 7행 (Stop 게이트 적발)
  v3.3  `raw.startswith("|")` → 들여쓴 표 행을 세지도 못함 (**과소**)
  v3.4  `raw.strip()` 무제한 → 코드 블록 안의 `|` 행을 표로 오인 (**과대**)
  v3.5  경계를 Markdown 규칙으로 확정: fenced code block 안 제외 +
        선행 공백 4칸 이상 제외 + **행 보존 단언** + 인식 불가 행은 중단

## v4 (v1.9 대응)

v1.9 는 **§13.6.3 재분류표를 삭제하고 §13.2 초기 등재표로 통합**했다(S-14).
v3.5 를 v1.9 문서에 그대로 돌리면 `파싱 중단: §13.6.3 데이터 행이 5열이 아니다
(2열)` 로 fail-closed 한다 — 올바른 동작이고, 이 판에서 파싱 대상을 옮긴다.

  ① 파싱 대상 = **§13.2 초기 등재표 (8열)**.  id 형태 3종(`UNCHK-001` /
     `~~UNCHK-010~~` 철회 / `**UNCHK-019**` 신규 강조)을 전부 인식한다.
     철회 행은 **분석에서 제외하되 카운트해 보고**한다 — 조용히 버리지 않는다.
  ② E1 은 유지, 대상 표만 교체.
  ③ E2 를 **둘로 분해**한다.  v1.9 가 U-8b 를 신설해 `blocks_gate` 허용 집합을
     리터럴 목록 → **게이트 레지스트리 파생**으로 바꿨기 때문이다:
       E2-a  레지스터가 사용 중인 값이 §4.2 정의 게이트 안에 있는가 (고아 검출)
       E2-b  **리터럴 허용 목록이 되살아났는가** 회귀 검사
     구 `parse_allowed_targets`(리터럴 `Phase 0..7` 을 파싱해 허용 집합으로
     삼던 함수)는 U-8b 하에서 존재 자체가 결함이므로 **삭제**하고 E2-b 로 교체.
  ④ **S-16 검사 신설** — 계약이 지목하는 필드와 대조군이 뮤테이션하는 필드의
     교집합이 비면 결함.  이 검사 자체도 **대조군 필수**다: v1.8 판 T-61 텍스트를
     심어 결함으로 검출되는지 먼저 확인하고, 검출되지 않으면 검사를 무효로 보고한다.

**공통 규율**: 대조군 없는 "0건"은 통과가 아니다.  이 도구가 여섯 번 지적받은
결함은 전부 "검사 패턴이 검사 대상보다 좁다" 형태였다.

답하는 것:
  E1    v1.8 T-61(=`normative_ref` 뮤테이션)이 "blocks_gate 를 무시하는 구현"을
        구별하지 못함을 보이고, 교정 대조군(=`blocks_gate` 자체 이동)이 잡음을 보인다
  E2-a  `blocks_gate` 값 중 판정 함수가 실재하지 않는 것 (문서 파싱 기반)
  E2-b  U-8b 가 폐기한 리터럴 허용 목록의 활성 잔존
  S-16  U-8a 계약문의 필드 ∩ T-61 대조군의 필드
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

DOC = "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md"

# S-16 의 필드 어휘 집합. 이 집합 밖의 이름은 계약/대조군 어느 쪽에서도 세지 않는다.
FIELD_VOCAB = (
    "normative_ref",
    "closable",
    "blocks_gate",
    "owner_track",
    "reason",
    "required_kinds",
    "existence",
)


@dataclass(frozen=True)
class Unchk:
    ident: str
    axis: str
    owner_track: str
    normative_ref: str
    closable: str
    blocks_gate: str | None
    withdrawn: bool


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


MARKUP = re.compile(r"[*`~]")


def _plain(cell: str) -> str:
    """강조·코드·취소선 마크업을 벗긴 값."""
    return MARKUP.sub("", cell).strip()


SECTION = re.compile(r"^#{3,4}\s")
SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


def _section_lines(lines: list[str], heading_prefix: str) -> list[str]:
    """지정 섹션의 본문만 잘라낸다.

    §13.2 초기 등재표도 v1.8 까지는 5열이라 열 수로는 §13.6.3 과 구별되지 않았다 —
    v3.1 초판이 여기서 fail-closed 로 중단했다(추측하지 않은 것은 옳다).
    섹션으로 범위를 좁힌다.
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


def _table_rows(lines: list[str]) -> list[str]:
    """Markdown 표 데이터 행만 돌려준다 (헤더·구분선 제외 전 단계).

    경계는 Markdown 규칙으로 잡는다 — 과소/과대 양 끝을 모두 막는다:
      - fenced code block(``` …) 안은 표가 아니다        (v3.4 과대 교정)
      - 선행 공백 4칸 이상은 코드 블록이다               (v3.4 과대 교정)
      - `raw.strip()` 후 판정한다                        (v3.3 과소 교정)
    """
    out: list[str] = []
    in_fence = False
    for raw in lines:
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if len(raw) - len(raw.lstrip(" ")) >= 4:
            continue
        line = raw.strip()
        if not line.startswith("|") or SEPARATOR.match(line):
            continue
        out.append(line)
    return out


IDENT = re.compile(r"UNCHK-\d+")
# `**`G2`** ← v1.9 재배치` 처럼 주석이 붙은 셀에서 값만 뽑되, 예상 밖 형태는 중단한다.
GATE_SHAPE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:[ -]\d+)?$")


def parse_register(lines: list[str]) -> list[Unchk]:
    """§13.2 초기 등재표. **8열**:

        id | axis | reason | blocked_by | owner_track | normative_ref | closable | blocks_gate

    v1.9 데이터 이행으로 세 필드가 이 표에 들어왔고 §13.6.3 표는 삭제됐다.

    안전장치(전부 Stop 게이트 지적으로 추가된 것 — 유지):
      - fenced code block / 4칸 들여쓰기 제외
      - **행 보존 단언**: 데이터 행 수 == 인식 결과 수
      - 인식 불가 데이터 행은 조용한 skip 이 아니라 **중단**
      - 열 수가 기대와 다르면 **중단**
      - 철회 행은 버리지 않고 `withdrawn=True` 로 **가시화**
    """
    rows: list[Unchk] = []
    data_rows = 0

    for line in _table_rows(_section_lines(lines, "### 13.2")):
        cells = _cells(line)
        if cells and _plain(cells[0]) == "id":  # 헤더
            continue
        data_rows += 1

        if len(cells) != 8:
            raise SystemExit(
                f"파싱 중단: §13.2 데이터 행이 8열이 아니다 ({len(cells)}열) — {line[:80]}"
            )

        ident_cell = cells[0].strip()
        withdrawn = ident_cell.startswith("~~")
        ident_plain = _plain(ident_cell)
        if not IDENT.fullmatch(ident_plain):
            # 인식 불가 행을 **버리지 않는다.** 조용한 skip 이 곧 과소 계수다.
            raise SystemExit(f"파싱 중단: 인식 불가 데이터 행 — {line[:80]}")

        ref_plain = _plain(cells[5])
        ref = "" if ref_plain in {"공란", "—", "-", ""} else cells[5].strip()

        closable_plain = _plain(cells[6])
        if withdrawn:
            # 철회 행은 세 필드가 전부 `—` 다. 분석에서 제외하되 카운트는 남긴다.
            closable = ""
        elif closable_plain in {"YES", "NO"}:
            closable = closable_plain
        else:
            raise SystemExit(
                f"파싱 중단: closable 미해석 ({closable_plain!r}) — {line[:80]}"
            )

        gate_plain = _plain(cells[7]).split("←")[0].strip()
        if gate_plain in {"—", "-", ""}:
            gate = None
        elif GATE_SHAPE.match(gate_plain):
            gate = gate_plain
        else:
            raise SystemExit(
                f"파싱 중단: blocks_gate 미해석 ({gate_plain!r}) — {line[:80]}"
            )

        rows.append(
            Unchk(
                ident=ident_plain,
                axis=_plain(cells[1])[:40],
                owner_track=_plain(cells[4]),
                normative_ref=ref,
                closable=closable,
                blocks_gate=gate,
                withdrawn=withdrawn,
            )
        )

    if not rows:
        raise SystemExit("파싱 중단: §13.2 초기 등재표를 찾지 못했다")

    # **행 보존 단언** — 인식 결과의 수가 데이터 행 수와 같아야 한다.
    if len(rows) != data_rows:
        raise SystemExit(
            f"파싱 중단: 행 손실 — 데이터 {data_rows}행 중 인식 {len(rows)}"
        )
    return rows


def parse_defined_gates(lines: list[str]) -> set[str]:
    """§4.2 게이트 표에서 실제로 정의된 게이트 이름을 모은다.

    v4: 패턴을 `G[1-4]` → `G\\d+` 로 **넓힌다.** 좁은 리터럴은 게이트가 늘어나는
    순간 조용히 못 찾는다 — 이 도구가 여섯 번 지적받은 결함의 형태다.
    """
    gates: set[str] = set()
    for line in lines:
        m = re.match(r"\|\s*\**\s*(G\d+)\b", line)
        if m:
            gates.add(m.group(1))
    if not gates:
        raise SystemExit("파싱 중단: §4.2 게이트 정의를 찾지 못했다")
    return gates


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
        replace(e, normative_ref="" if e.blocks_gate == gate else e.normative_ref)
        for e in register
    ]
    return before != impl(gate, mutated)


def t61_corrected(impl, register: list[Unchk], gate: str, other: str) -> bool:
    """교정 대조군 — `blocks_gate` 자체를 gate→other 로 옮긴다."""
    target = next((e for e in register if e.blocks_gate == gate), None)
    if target is None:
        raise SystemExit(f"파싱 중단: blocks_gate={gate} 인 행이 없다")
    moved = [replace(e, blocks_gate=other) if e is target else e for e in register]
    left = target.ident in impl(gate, register) and target.ident not in impl(
        gate, moved
    )
    entered = target.ident not in impl(other, register) and target.ident in impl(
        other, moved
    )
    return left and entered


# ------------------------------------------------------- E2-b 리터럴 회귀 검사

# U-8b 는 `blocks_gate` 허용 집합을 **레지스트리 파생**으로 못박았다.
# 리터럴 목록(`Phase 0..7` 류)이 활성 서술로 되살아나면 위반이다.
#
# 패턴은 **대상보다 넓게** 잡는다. 좁은 패턴이 이 도구의 반복 결함이었다.
LITERAL_ALLOWLIST = re.compile(
    r"Phase\s*0\s*(?:\.\.|~|-|–)\s*7"
    r"|허용.{0,40}Phase\s*\d"
    r"|Phase\s*\d.{0,40}허용"
)
# 구조적 역사 표지 — 내용 판단이 아니라 **위치**로만 분류한다 (내용 기반 배제가
# 과잉 배제를 만든 것이 스윕 3회차 결함이었다).
HISTORY_LINE = re.compile(r"^>\s|^\|\s*\*{0,2}~{0,2}v1\.\d")
FIELD_CTX = 3  # 필드 귀속을 판정할 때 보는 앞뒤 행 수


def classify_literal_hit(lines: list[str], idx0: int) -> tuple[str, str]:
    """(활성/역사, 필드 문맥) 을 돌려준다. 판단 불가는 fail-closed 로 접는다."""
    line = lines[idx0]
    kind = "역사" if HISTORY_LINE.match(line.strip()) else "활성"
    lo = max(0, idx0 - FIELD_CTX)
    ctx = " ".join(lines[lo : idx0 + FIELD_CTX + 1])
    has_bg = "blocks_gate" in ctx
    has_ot = "owner_track" in ctx
    if has_bg and not has_ot:
        field = "blocks_gate"
    elif has_ot and not has_bg:
        field = "owner_track"
    elif has_bg and has_ot:
        field = "둘 다"
    else:
        field = "불명"
    return kind, field


def scan_literal_allowlist(lines: list[str]) -> list[tuple[int, str, str, str, bool]]:
    """(행번호, 본문, 활성/역사, 필드, 다행여부).

    **fenced code block 을 건너뛰지 않는다.** 계약문 자체가 ```text 블록 안에
    있으므로, 리터럴 목록이 되살아난다면 바로 그 블록 안일 가능성이 가장 높다.
    (표 파서는 fence 를 건너뛴다 — 목적이 다르므로 규칙도 다르다.)
    """
    hits: list[tuple[int, str, str, str, bool]] = []
    covered: set[int] = set()
    for i, line in enumerate(lines):
        if LITERAL_ALLOWLIST.search(line):
            kind, field = classify_literal_hit(lines, i)
            hits.append((i + 1, line.strip()[:110], kind, field, False))
            covered.add(i)
    # 다행 주사 (S-17) — 행 경계를 넘는 명제도 본다. 행 단위 히트와 중복 제거.
    for width in (2, 3):
        for i in range(len(lines) - width + 1):
            span = range(i, i + width)
            if any(j in covered for j in span):
                continue
            joined = " ".join(x.strip() for x in lines[i : i + width])
            if LITERAL_ALLOWLIST.search(joined):
                kind, field = classify_literal_hit(lines, i)
                hits.append((i + 1, joined[:110], kind, field, True))
                covered.update(span)
    return sorted(hits)


# --------------------------------------------------------------- S-16 검사

CONTROL_MARKER = re.compile(r"대조군|\bT-\d+\b")


def fields_in(text: str) -> set[str]:
    return {
        f
        for f in FIELD_VOCAB
        if re.search(rf"(?<![A-Za-z_]){re.escape(f)}(?![A-Za-z_])", text)
    }


def parse_contract_item(lines: list[str], ident: str) -> list[str]:
    """§13.6.2 코드블록 안에서 `<ident>` 로 시작하는 항목의 본문 행을 잘라낸다."""
    body = _section_lines(lines, "#### 13.6.2")
    fenced: list[str] = []
    in_fence = False
    for raw in body:
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            fenced.append(raw)
    if not fenced:
        raise SystemExit("파싱 중단: §13.6.2 코드블록을 찾지 못했다")

    start = None
    for i, raw in enumerate(fenced):
        if re.match(rf"^{re.escape(ident)}\b", raw):
            start = i
            break
    if start is None:
        raise SystemExit(f"파싱 중단: 계약 항목 '{ident}' 를 찾지 못했다")

    item = [fenced[start]]
    for raw in fenced[start + 1 :]:
        if re.match(r"^[A-Za-z]+-?\w*\s{2,}", raw) or re.match(r"^U-\d", raw):
            break  # 다음 항목
        item.append(raw)
    return item


def s16_check(f_contract: set[str], f_control: set[str]) -> tuple[bool, set[str]]:
    """(결함인가, 교집합). 교집합이 비면 결함."""
    inter = f_contract & f_control
    return (not inter), inter


def parse_test_row(lines: list[str], test_id: str) -> str:
    """§8 테스트 표에서 `| <test_id> |` 행을 찾는다. 다중/부재는 **중단**."""
    found = [line for line in _table_rows(lines) if _plain(_cells(line)[0]) == test_id]
    if len(found) != 1:
        raise SystemExit(f"파싱 중단: '{test_id}' 행이 {len(found)}건 (1건이어야 한다)")
    return found[0]


# v1.8 판 T-61 — `blocks_gate=G2` 행을 **`normative_ref` 공란화**로 뮤테이션하던 기술.
# S-16 의 대조군이다. 이 텍스트를 넣었을 때 결함으로 검출되지 않으면 S-16 구현은 무효다.
T61_V18_TEXT = (
    "| T-61 | **U-8a 사유 집합 소비** (§13.6.2) | `normative_ref` 가 채워진 행 하나를 "
    "공란으로 바꾸면 → 그 `id` 가 게이트 사유 집합에서 사라져야 한다. 사라지지 않으면 실패 |"
)


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    lines = (repo / DOC).read_text(encoding="utf-8").splitlines()

    register = parse_register(lines)
    active = [e for e in register if not e.withdrawn]
    withdrawn = [e for e in register if e.withdrawn]
    defined = parse_defined_gates(lines)

    print(
        f"문서 파싱: §13.2 초기 등재표 데이터 {len(register)}행 "
        f"(분석 대상 {len(active)} + 철회 {len(withdrawn)}) / 정의 게이트 {sorted(defined)}"
    )
    for e in withdrawn:
        print(f"    ⚠ 철회 행(분석 제외·카운트 보고): {e.ident} — {e.axis}")
    for e in active:
        print(
            f"    {e.ident:<12} ref={'있음' if e.normative_ref else '공란':<4} "
            f"closable={e.closable:<3} blocks_gate={str(e.blocks_gate):<8} "
            f"owner_track={e.owner_track}"
        )
    print()

    print("=== E1: 대조군이 'blocks_gate 무시' 구현을 잡는가 ===")
    print(f"{'대조군':<16} {'honest':<10} {'무시 구현':<12} 판정")
    print("-" * 60)
    r_v18 = {k: t61_v18(f, active, "G2") for k, f in IMPLS.items()}
    r_fix = {k: t61_corrected(f, active, "G2", "G3") for k, f in IMPLS.items()}
    for name, res in (("T-61 (v1.8)", r_v18), ("T-61 (교정)", r_fix)):
        catches = res["honest"] and not res["ignores_blocks_gate"]
        print(
            f"{name:<16} {str(res['honest']):<10} {str(res['ignores_blocks_gate']):<12} "
            f"{'잡는다' if catches else '**놓친다**'}"
        )

    print("\n=== E2-a: blocks_gate 고아 target (문서 파싱 기반) ===")
    used = {e.blocks_gate for e in active if e.blocks_gate}
    orphan = sorted(g for g in used if g not in defined)

    # **대조군 먼저** — 고아를 심었을 때 검출되는가. 대조군 없는 "0건"은 통과가 아니다.
    # 심는 값 `Phase 4` 는 v1.8 이 실제로 갖고 있던 고아이며 v1.9 가 G2 로 재배치했다.
    planted = active + [replace(active[0], ident="<대조군>", blocks_gate="Phase 4")]
    ctl_orphan = sorted({e.blocks_gate for e in planted if e.blocks_gate} - defined)
    ctl_ok = ctl_orphan == ["Phase 4"]
    print(
        f"  대조군(`Phase 4` 주입) → {'검출 OK' if ctl_ok else '**검출 실패**'} "
        f"{ctl_orphan}"
    )
    rc_a = 0 if ctl_ok else 1
    if not ctl_ok:
        print("    → E2-a 는 무효다. 아래 고아 목록을 증거로 쓰지 마라.")

    print(f"  §4.2 정의 게이트                 {sorted(defined)}")
    print(f"  U-8b 파생 허용집합 (정의 − G4)   {sorted(defined - {'G4'})}")
    print(f"  레지스터 사용 중인 값            {sorted(used)}")
    print(f"  **고아(판정 함수 없음): {orphan if orphan else '0건'}**")
    for e in active:
        if e.blocks_gate in orphan:
            print(f"      {e.ident} → blocks_gate={e.blocks_gate!r} (판정 함수 없음)")
    g4_used = sorted(g for g in used if g == "G4")
    print(f"  U-8b 의 G4 제외 위반: {g4_used if g4_used else '0건'} (INV-C1 방향)")

    print("\n=== E2-b: 리터럴 허용 목록 회귀 (U-8b) ===")
    # **대조군 먼저** — v1.8 이 갖고 있던 리터럴 선언을 코퍼스 끝에 심어 검출되는가.
    ctl_line = "U-8b  `blocks_gate` 의 허용 값은 `Phase 0..7` 과 `G1`~`G3` 이다"
    ctl_hits = scan_literal_allowlist(lines + ["", ctl_line])
    ctl_b_ok = any(
        h[0] == len(lines) + 2 and h[2] == "활성" and h[3] == "blocks_gate"
        for h in ctl_hits
    )
    print(
        f"  대조군(v1.8 리터럴 선언 주입) → {'활성·blocks_gate 로 검출 OK' if ctl_b_ok else '**검출 실패**'}"
    )
    if not ctl_b_ok:
        print("    → E2-b 는 무효다. 아래 히트 목록을 '전수'로 읽지 마라.")
        rc_b = 1
    else:
        rc_b = 0

    lit_hits = scan_literal_allowlist(lines)
    suspect = [
        h
        for h in lit_hits
        if h[2] == "활성" and h[3] in {"blocks_gate", "둘 다", "불명"}
    ]
    print(f"  히트 {len(lit_hits)}건 — 전부 표시한다 (분류만 부여, 배제 없음)")
    for line_no, text, kind, field, multi in lit_hits:
        mark = "**" if kind == "활성" else "  "
        tag = "[다행]" if multi else "      "
        print(f"    {mark}[{kind}]{tag}[{field}] :{line_no}  {text}")
    print(
        f"  **U-8b 위반 후보(활성 × blocks_gate|둘 다|불명): {len(suspect)}건**"
        f"  ← 불명은 fail-closed 로 후보에 접는다"
    )

    print("\n=== S-16: 계약이 지목하는 필드 ∩ 대조군이 뮤테이션하는 필드 ===")
    item = parse_contract_item(lines, "U-8a")
    cut = next(
        (i for i, raw in enumerate(item) if CONTROL_MARKER.search(raw)), len(item)
    )
    strict = item[:cut]
    if not strict:
        raise SystemExit("파싱 중단: U-8a 계약문 슬라이스가 비었다")

    print("  [U-8a 항목 전문 — 절단선 표시]")
    for i, raw in enumerate(item):
        print(f"    {'│' if i < cut else '╎'} {raw.rstrip()}")
    print(
        "    ('│' = 계약문 슬라이스 / '╎' = 대조군 지정·이력 슬라이스."
        " 절단 규칙 = 첫 `대조군`/`T-\\d+` 언급 행 직전)"
    )

    f_wide = fields_in("\n".join(item))
    f_strict = fields_in("\n".join(strict))
    row_now = parse_test_row(lines, "T-61")
    f_control_now = fields_in(row_now)
    f_control_v18 = fields_in(T61_V18_TEXT)

    print(f"\n  F_contract (전문 판독, 지시대로 항목 전체) = {sorted(f_wide)}")
    print(f"  F_contract (축소 판독, 계약문 슬라이스만)   = {sorted(f_strict)}")
    print(f"  F_control  (현행 T-61 행)                   = {sorted(f_control_now)}")
    print(f"  F_control  (v1.8 판 T-61 — 대조군)          = {sorted(f_control_v18)}")

    rc = rc_a | rc_b
    for label, f_c in (("전문 판독", f_wide), ("축소 판독", f_strict)):
        # --- 대조군 먼저: v1.8 판 T-61 을 심어 **결함으로 검출되는가** ---
        ctl_defect, ctl_inter = s16_check(f_c, f_control_v18)
        # --- 본 검사: 현행 T-61 ---
        now_defect, now_inter = s16_check(f_c, f_control_now)
        print(f"\n  [{label}]")
        print(
            f"    대조군(v1.8 T-61) → {'결함 검출 OK' if ctl_defect else '**검출 실패**'} "
            f"(교집합 {sorted(ctl_inter) if ctl_inter else '∅'})"
        )
        if not ctl_defect:
            print(
                "    → 이 판독에서 S-16 은 **무효**다. 대조군이 잡히지 않는 검사의 "
                "'결함 0건'은 통과가 아니다."
            )
            rc = 1
        print(
            f"    본 검사(현행 T-61) → {'**결함**' if now_defect else '결함 없음'} "
            f"(교집합 {sorted(now_inter) if now_inter else '∅'})"
        )
        if not ctl_defect:
            print(
                "       ^ 위 대조군이 실패했으므로 이 줄의 '결함 없음'은 증거가 아니다."
            )

    print(
        "\n  진단: 전문 판독이 실패하면 원인은 계약 항목이 **이력 주석**에서 다른 필드를"
    )
    print("        언급하기 때문이다 — 계약문과 대조군 기술이 한 블록에 섞여 있으면")
    print("        S-16 의 기계적 형태(교집합)가 자기 입력에 오염된다. 절단선을 위에")
    print("        전문 인쇄로 함께 내보내는 이유다.")

    print("\n" + "=" * 72)
    print("대조군 종합 (하나라도 실패하면 그 검사의 결과는 증거가 아니다)")
    print(f"  E2-a  고아 주입          : {'OK' if not rc_a else '**실패**'}")
    print(f"  E2-b  리터럴 선언 주입   : {'OK' if not rc_b else '**실패**'}")
    print(
        f"  S-16  v1.8 T-61 (전문)   : "
        f"{'OK' if s16_check(f_wide, f_control_v18)[0] else '**실패**'}"
    )
    print(
        f"  S-16  v1.8 T-61 (축소)   : "
        f"{'OK' if s16_check(f_strict, f_control_v18)[0] else '**실패**'}"
    )
    print(f"종료코드 {rc}" + ("" if rc else " — 전 대조군 통과"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
