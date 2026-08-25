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
      TOS-CC-C2U  «앵커 없는 자기인용 좌표»의 **개수 래칫** (아래 RATCHET-1).
      TOS-CC-C2UP 그 기준선이 «어디서 쟀는가»에 대해 하는 주장의 기계 강제
                  (아래 PROVENANCE-1).
  C3  TOS-CC-C3A  «현행 버전»보다 **큰** 리터럴 버전(= 구성상 미래 지향).
      TOS-CC-C3B  머리말이 스스로 열거한 «미래 지향 필드» 어휘 + 동일 major 리터럴 버전이
                  **같은 마크다운 표 «셀»** 안에 공존 (아래 CELL-1).
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
QUOTE-1 — C1 은 «살아 있는 주장» 과 «에라타가 대체한 옛 표기의 인용» 을 가른다
------------------------------------------------------------------------------
이 계약의 규율은 **대체된 문언을 인용해 남기는 것**이다.  그래서 새 문언은 자기가
치운 옛 표기를 자주 데리고 다닌다::

    [v2.22 에라타 10차 ⓓ] 기수 진술을 «술어»로 교체한다.
    동결~9차는 이 자리를 「(4) 의 «6개» 중 셋」으로 적었고 (4) 가 7원소가 된 뒤에도 …

C1 의 초판은 이 인용문 안의 「6개」를 **살아 있는 기수 진술**로 읽어 red 를 냈다.
고칠 쪽은 문서가 아니라 술어다 — 검사기를 만족시키려고 인용을 지우면 «에라타가 무엇을
대체했는지»를 숨기는 것이고, 그건 규율 자체를 무너뜨린다.

면제 구간은 둘이며, 판정은 **기수 토큰의 위치**로 한다(참조 위치가 아니다)::

  (A) 판을 명시한 각괄호 편집 출처 마커 `[v2.22 에라타 10차 ⓓ]` 의 **안**.
      `]` 에서 닫히며 **닫힌 뒤의 기수는 면제되지 않는다** — 거기는 새 문언이다.
  (B) 인용 부호 「…」 의 **안**.  열고 **닫힌** 것만 구간이 된다.  열어만 두고 닫지
      않은 자리는 면제하지 않는다(면제 남용을 fail-closed 로 막는다).

**«…» 는 면제 구간이 아니다.**  이 문서는 «…» 를 인용에도 «강조»에도 쓰므로, 그것까지
면제하면 살아 있는 진술이 자기 수를 «9개» 로 강조하는 순간 검사가 조용히 눈이 먼다.
위 실물 위양성은 안쪽의 «6개» 가 아니라 바깥의 「…」 가 덮으므로 «…» 없이도 닫힌다 —
두 술어의 결과가 같음을 실측했다(면제 1건 · C1 발화 0).  같은 결과면 좁은 쪽을 고른다.

CELL-1 과 같은 클래스의 «정밀화»다 — 좁힌 모집단은 넓은 모집단의 부분집합이므로
과잉 차단만 사라지고 없던 침묵이 새로 생기지 않는다.  실측: 현행 판에서 살아 있는
진술 2건(둘 다 인용 밖·둘 다 정합) · 인용 면제 1건 · C1 발화 0.

------------------------------------------------------------------------------
CELL-1 — C3B 의 공존 모집단은 «행» 이 아니라 «표 셀» 이다
------------------------------------------------------------------------------
S-11 은 «필드» 단위 규칙이다("미래 지향 «필드»는 리터럴 대신 참조").  그런데 C3B 의
초판은 공존을 **행 단위**로 봤고, 마크다운 표에서는 한 행이 여러 «필드»(셀)를 담으므로
**서로 다른 셀의 두 토큰이 만나** 위양성이 났다.  실측 사례::

    | **6e⁗ 재결속 (v2.22 동결 내용)** | … 현행(8차 이후) … 현재 위치 … |
             ↑ 셀 1 의 리터럴 = 행 «이름» = 완료·이력(S-12 가 명시 허용)
                                            ↑ 셀 2 의 미래 지향 어휘

그래서 표 행에서는 파이프로 셀을 분해하고 **같은 셀 안의 공존만** 발화한다.  이것은
«약화»가 아니라 «정밀화»다 — 좁힌 모집단은 넓은 모집단의 **부분집합**이므로 과잉 차단은
사라지지만 없던 침묵이 새로 생기지는 않는다(같은 셀 공존 ⟹ 같은 행 공존).  경계 둘::

  * 이스케이프된 `\\|` 는 표 안에서 «내용»이므로 분할자가 아니다(이 문서가 실제로 쓴다).
  * 표가 «아닌» 행은 셀이 하나뿐 — 행 전체가 그대로 한 단위다(기존 발화 불변).

C3A(자리 단위 검사)는 셀 분해와 무관하므로 행 단위 그대로 둔다.

------------------------------------------------------------------------------
RATCHET-1 — 앵커 없는 자기인용 좌표의 «개수» 래칫 (닫음이 아니다)
------------------------------------------------------------------------------
C2B/C2C 는 **주장절이나 앵커가 붙은** 자기인용만 검증한다.  나머지 — 앵커도 주장절도
없는 bare 좌표 — 는 «그 좌표가 무엇을 가리킨다고 주장하는지»가 문서에 적혀 있지 않아
기계가 대조할 대상 자체를 갖지 못한다.  결과는 **극성 fail-open** 이다: 본문에 행이
삽입되면 그 좌표들이 조용히 밀어도 **어떤 검사도 발화하지 않는다.**

전수 앵커화(100 자리 규모의 일괄 편집)는 그 자체가 결함원이므로 이번 판에서 하지
않는다.  대신 잔여가 **«늘지 않는 것»만이라도 기계로 보장**한다::

  * 모집단 = 자기인용 중 ANCHOR-1 앵커도 «주장절»도 없는 좌표(= 대조 불가능한 것들).
    술어는 «구조»뿐이라 `--min-anchor` 같은 조율값에 결속되지 않는다.
  * 기준선은 검사기 «밖»의 `tools/.tos_contract_baseline.json` 에 둔다.
  * 개수가 기준선보다 **크면 red**.  줄면 green 이되 «기준선을 낮추라»는 안내를 낸다 —
    **자동 갱신하지 않는다.**  검사기가 자기 기준선을 몰래 낮추면 래칫이 아니라
    래칫의 흉내일 뿐이다(갱신은 사람의 기록 행위로 남아야 한다).
  * 기준선 파일이 없거나 읽히지 않거나 형태가 틀리면 **red**(fail-closed).  부재를
    «0 위반»으로 접는 순간 이 축은 검사가 아니라 장식이 된다.

**이것은 닫음이 아니라 래칫이다.**  잔여 좌표들은 여전히 대조되지 않는다; 보장되는
것은 «잔여가 커지지 않는다» 하나뿐이고, 그 한계는 `--report` 와 최종 보고에 남는다.

------------------------------------------------------------------------------
PROVENANCE-1 — 기준선의 «측정 출처» 주장을 기계로 강제한다
------------------------------------------------------------------------------
기준선 파일은 «이 개수를 커밋 X 의 blob 에서 쟀다»고 적는다.  그 필드는 사람이 적는
산문이므로 **워킹트리를 재고 커밋 이름만 적어 넣는 실수**가 구조적으로 가능하다 — 이
검사기의 초판이 실제로 그렇게 만들어졌고, 그 시점에 다른 레인이 계약을 편집 중이었다.
값이 우연히 맞았을 뿐 **절차가 주장을 지키지 않았다.**

그래서 C2UP 는 `git show <commit>:<path>` 로 **그 blob 을 다시 재어** 기입값과 대조한다::

  * 재측정 ≠ 기입값               → red (주장이 거짓)
  * 출처 필드 부재·형태 위반       → red (검증 불가를 통과로 접지 않는다)
  * 커밋이 16진 sha 가 아님        → red (`HEAD`·브랜치 같은 «움직이는 ref» 는 매 실행마다
                                    다른 대상을 가리켜 주장 자체가 성립하지 않는다)
  * git 실행 실패·커밋/경로 부재   → red

갱신 절차도 기계화한다 — `--measure-baseline <rev>` 는 **커밋 blob** 에서 재어 붙여넣을
JSON 을 출력한다.  **파일은 쓰지 않는다**(RATCHET-1 과 같은 이유: 기입은 사람의 기록
행위여야 한다).  ref 는 그 자리에서 불변 sha 로 해소해 출력한다.

------------------------------------------------------------------------------
운용
------------------------------------------------------------------------------
fail-closed: 위반 1건 이상이면 rc=1, 내부 예외면 rc=2 (예외를 삼키고 green 을 내지 않는다).
`--self-test` 는 뮤테이션 대조군 배터리를 돌려 **죽은 검사 0** 을 실증한다.

양방향성은 두 형태로 산다.  문서에 그 위반이 **실재할 때**는 `repair`(«수리하면 그 자리만
green»)가 직접 증명하고, 문서가 그 축에서 **이미 green 일 때**는 기준 실행 자신이
«수리된 쪽»이므로 `inject`(«주입하면 red») 하나가 green→red→(원상) 양방향을 전부 진다.
그래서 `before=0` 인 `repair` 대조군은 통과가 아니라 **«대조군 무효»** 로 시끄럽게 뜬다 —
수리할 대상이 없는 수리 대조군은 조용히 참인 채로 아무것도 증명하지 않기 때문이다.

배터리는 «죽은 검사»(검사가 변이를 판별하지 못함 = 검사기 결함)와 «대조군 무효»(변이를
문서에 넣지 못함 = 앵커가 사라짐)를 **분리해** 보고한다.  둘을 섞으면 문서가 움직였을
뿐인데 검사기가 죽은 것처럼 보인다.  그 오귀속을 피하려고 이 파일의 대조군은 자리를
가능한 한 **문서 구조에서 파생**한다(하드코딩 앵커는 계약 편집 한 번에 전부 무효가 된다 —
실측했다).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import tempfile
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

#: RATCHET-1 기준선 파일 — 검사기 «밖»에 두어 개수 갱신이 사람의 기록 행위로 남게 한다.
#: 검사기가 스스로 낮출 수 있는 자리에 두면 래칫이 성립하지 않는다.
DEFAULT_BASELINE_NAME = ".tos_contract_baseline.json"

#: 그 파일 안에서 미앵커 좌표 개수를 담는 키.
BASELINE_UNANCHORED_KEY = "unanchored_self_citations"

#: 그 개수를 «어느 커밋의 어느 blob 에서» 쟀는지를 담는 키 (PROVENANCE-1).
BASELINE_PROVENANCE_KEY = "measured_against"

#: 측정 출처의 «종류».  둘뿐이며, 이름을 강제로 적게 하는 이유는 «어디서 쟀는지»를
#: 산문이 아니라 **판정 가능한 값**으로 남기기 위해서다.
BASELINE_KIND_COMMIT = "commit"  # 불변 커밋 blob — 재현 가능한 정상 상태
BASELINE_KIND_WORKTREE = "worktree"  # 커밋 전 워킹트리 — 과도기의 정직한 기입
BASELINE_KIND_KEY = "kind"

#: 측정 출처 커밋은 **불변 객체 이름**이어야 한다.  `HEAD`·브랜치명 같은 움직이는 ref 를
#: 허용하면 «그 커밋에서 쟀다»는 주장이 매 실행마다 다른 것을 가리켜 검증 자체가 무의미해진다.
BASELINE_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")

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

#: C1 면제 구간 (QUOTE-1) — 이 «안»의 기수 토큰은 «살아 있는 주장»이 아니다.
#:   (A) 판을 명시한 각괄호 편집 출처 마커 — `[v2.22 에라타 10차 ⓓ]`.  `]` 에서 닫히며
#:       **닫힌 뒤의 기수는 면제되지 않는다**(그 자리는 새 문언이지 인용이 아니다).
#:   (B) 인용 부호 「…」 — 열고 **닫힌** 것만.  열어만 두고 닫지 않은 자리는 면제하지
#:       않는다(면제 남용을 fail-closed 로 막는다).
#: **«…» 는 일부러 넣지 않는다.**  이 문서는 «…» 를 인용에도 «강조»에도 쓰므로, 그것까지
#: 면제하면 살아 있는 진술이 자기 수를 «9개» 로 강조하는 순간 조용히 눈이 먼다.  실물
#: 위양성(`「(4) 의 «6개» 중 셋」`)은 바깥의 「」 가 이미 덮으므로 «…» 없이 닫힌다 —
#: 실측으로 확인했다(면제 1건·C1 발화 0, «…» 포함본과 동일).  넓은 술어와 결과가 같다면
#: 좁은 쪽을 고른다.
#: 각 정규식이 여는 문자를 자기 문자 클래스에서 배제하므로 «가장 가까운 닫힘»에 붙는다.
ENUM_EXEMPT_SPAN_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\[[^\[\]]*v\d+\.\d+[^\[\]]*\]"),
    re.compile(r"「[^「」]*」"),
)
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


def _split_cells(line: str) -> list[tuple[int, str]]:
    """행을 «필드» 단위로 분해한다 — 표 행이면 셀, 아니면 행 전체 하나 (CELL-1).

    이스케이프된 ``\\|`` 는 표 안에서 «내용»이므로 분할자가 아니다.  오프셋을 함께
    돌려주는 이유는 셀 안의 자리를 **원문 좌표**로 되돌려야 하기 때문이다(예: 리터럴
    앞 4자를 되돌아보는 `PROVENANCE_OPEN_RE` 는 셀 경계를 넘어 볼 수 있어야 한다).

    Args:
        line: 원문 한 행.

    Returns:
        `(원문 오프셋, 조각 텍스트)` 목록.  표가 아니면 `[(0, line)]`.
    """
    if not TABLE_ROW_RE.match(line):
        return [(0, line)]
    cells: list[tuple[int, str]] = []
    start = 0
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "\\" and i + 1 < n:
            i += 2  # 이스케이프된 문자는 통째로 «내용» — `\|` 가 여기서 살아남는다
            continue
        if line[i] == "|":
            cells.append((start, line[start:i]))
            start = i + 1
        i += 1
    cells.append((start, line[start:]))
    return cells


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


def _exempt_spans(line: str) -> list[tuple[int, int]]:
    """C1 면제 구간(닫힌 인용·판본 각괄호)의 문자 범위를 모은다 (QUOTE-1)."""
    return [
        (m.start(), m.end()) for rx in ENUM_EXEMPT_SPAN_RES for m in rx.finditer(line)
    ]


def _in_exempt_span(spans: Sequence[tuple[int, int]], start: int, end: int) -> bool:
    """`[start, end)` 가 면제 구간 «안»에 **온전히** 들어가는지 본다."""
    return any(lo <= start and end <= hi for lo, hi in spans)


CardinalitySite = namedtuple(
    "CardinalitySite", ["line", "start", "end", "token", "claimed", "exempt"]
)


def iter_cardinality_statements(
    doc: ContractDoc, lo: int, hi: int
) -> Iterator[CardinalitySite]:
    """코드펜스 `(lo, hi)` 안에서 (4) 를 참조하며 수량을 말하는 자리를 훑는다.

    검사(C1)와 대조군 주입이 **같은 술어**를 쓰게 하려고 함수로 뽑았다.  둘이 갈라지면
    «검사가 보는 자리»와 «변이가 건드리는 자리»가 달라져 대조군이 판별력을 잃는다.

    Args:
        doc: 계약 문서 컨텍스트.
        lo: 코드펜스 여는 행(배타).
        hi: 코드펜스 닫는 행(배타).

    Yields:
        `CardinalitySite` — 토큰의 **행 내부 절대 오프셋**과 면제 여부를 함께 준다.
    """
    for lineno in range(lo + 1, hi):
        line = doc.lines[lineno - 1]
        spans = _exempt_spans(line)
        for ref in ENUM_REF_RE.finditer(line):
            window = line[ref.end() : ref.end() + CARDINALITY_WINDOW]
            token = CARDINALITY_TOKEN_RE.search(window)
            if token is None:
                continue
            start = ref.end() + token.start()
            end = ref.end() + token.end()
            yield CardinalitySite(
                lineno,
                start,
                end,
                token.group(0),
                int(token.group(1)),
                _in_exempt_span(spans, start, end),
            )


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
    exempt_quoted = 0
    for site in iter_cardinality_statements(doc, lo, hi):
        if site.exempt:
            # 에라타가 «대체한» 옛 표기의 인용이다(QUOTE-1).  대체된 문언을 인용해
            # 남기는 것은 이 아크의 규율이므로, 고칠 쪽은 문서가 아니라 이 술어다.
            # 조용한 면제는 fail-open 과 구별되지 않으므로 계수로 남긴다.
            exempt_quoted += 1
            continue
        statements += 1
        if site.claimed != actual:
            violations.append(
                Violation(
                    "TOS-CC-C1",
                    doc.display_path,
                    site.line,
                    f"(4) 열거의 기수 진술 '{site.token.strip()}' 이 "
                    f"실제 열거 원소 수 {actual} 와 불일치 "
                    f"(원소: {', '.join(elements)})",
                )
            )
    logger.info(
        "C1: 열거 원소 %d개 · 살아 있는 (4) 기수 진술 %d건 · 인용 면제 %d건 (범위 %d-%d)",
        actual,
        statements,
        exempt_quoted,
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
# C2U — 앵커 없는 자기인용 좌표의 개수 래칫 (RATCHET-1)
# ============================================================================


def derive_unanchored_citations(doc: ContractDoc) -> list[tuple[int, str]]:
    """대조 «대상» 자체를 갖지 못하는 자기인용을 모집단으로 파생한다.

    조건은 구조뿐이다 — ANCHOR-1 앵커도, 괄호 주장절도 붙지 않은 좌표.  둘 중 하나라도
    있으면 C2B/C2C 가 실측 대조하므로 래칫의 소관이 아니다.  `--min-anchor` 같은
    조율값에 결속하지 않는 이유는, 조율값을 올리면 기준선이 저절로 깨져 래칫이
    «문서 변경»이 아닌 «설정 변경»에 반응하게 되기 때문이다.

    Args:
        doc: 계약 문서 컨텍스트.

    Returns:
        `(행번호, 좌표 토큰)` 목록 (문서 순서).
    """
    sites: list[tuple[int, str]] = []
    for lineno, m in iter_self_citations(doc):
        line = doc.lines[lineno - 1]
        if ANCHOR1_RE.match(line, m.start()) is not None:
            continue
        if _extract_claim(line, m.start(), m.end()):
            continue
        sites.append((lineno, m.group(0)))
    return sites


BaselineRecord = namedtuple("BaselineRecord", ["count", "kind", "commit", "path"])


def read_unanchored_baseline(path: Path) -> BaselineRecord:
    """래칫 기준선을 읽는다 — 부재·손상·형태 위반은 전부 fail-closed 사유다.

    측정 출처(`measured_against`)는 여기서 «형태»만 본다.  그 주장이 참인지는
    `check_c2up` 이 실제 blob 을 다시 재어 판정한다 (PROVENANCE-1).

    Args:
        path: 기준선 JSON 경로.

    Returns:
        `(개수, 측정 커밋, 측정 경로)`.

    Raises:
        ContractParseError: 읽기·파싱 실패 또는 키/타입 위반.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractParseError(f"기준선 파일을 읽지 못했다 ({path}): {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractParseError(
            f"기준선 파일이 JSON 이 아니다 ({path}): {exc}"
        ) from exc
    if not isinstance(data, dict) or BASELINE_UNANCHORED_KEY not in data:
        raise ContractParseError(
            f"기준선 파일에 '{BASELINE_UNANCHORED_KEY}' 키가 없다 ({path})"
        )
    value = data[BASELINE_UNANCHORED_KEY]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractParseError(
            f"기준선 '{BASELINE_UNANCHORED_KEY}' 가 음이 아닌 정수가 아니다: {value!r}"
        )
    prov = data.get(BASELINE_PROVENANCE_KEY)
    if not isinstance(prov, dict):
        prov = {}

    def _str(key: str) -> str | None:
        raw_value = prov.get(key)
        return raw_value if isinstance(raw_value, str) else None

    return BaselineRecord(value, _str(BASELINE_KIND_KEY), _str("commit"), _str("path"))


def read_baseline_source(repo_root: Path, record: BaselineRecord) -> str:
    """기준선이 «여기서 쟀다»고 주장하는 원본을, **그 주장 그대로** 읽는다.

    이 함수가 출처 종류별 유일한 리더다 — 검증과 픽스처 구성이 같은 경로를 쓰지 않으면
    «blob 을 잰다»는 주장과 실제 읽는 대상이 조용히 갈라질 수 있다.

    Args:
        repo_root: 저장소 루트.
        record: 기준선 레코드.

    Returns:
        원본 텍스트.

    Raises:
        ContractParseError: 출처 종류·형태 위반 또는 읽기 실패.
    """
    if record.path is None:
        raise ContractParseError(
            f"'{BASELINE_PROVENANCE_KEY}.path' 가 없다 — 무엇을 쟀는지 알 수 없다"
        )
    if record.kind == BASELINE_KIND_COMMIT:
        if record.commit is None:
            raise ContractParseError(
                f"'{BASELINE_PROVENANCE_KEY}.commit' 이 없다 (kind=commit)"
            )
        if not BASELINE_COMMIT_RE.match(record.commit):
            raise ContractParseError(
                f"측정 출처 커밋 '{record.commit}' 이 16진 sha 가 아니다 — "
                "움직이는 ref 는 «그 커밋에서 쟀다»는 주장을 검증 불가로 만든다"
            )
        return read_commit_blob(repo_root, record.commit, record.path)
    if record.kind == BASELINE_KIND_WORKTREE:
        try:
            return (repo_root / record.path).read_text(encoding="utf-8")
        except OSError as exc:
            raise ContractParseError(
                f"워킹트리 파일을 읽지 못했다 ({record.path}): {exc}"
            ) from exc
    raise ContractParseError(
        f"'{BASELINE_PROVENANCE_KEY}.{BASELINE_KIND_KEY}' 가 "
        f"'{BASELINE_KIND_COMMIT}'/'{BASELINE_KIND_WORKTREE}' 가 아니다: {record.kind!r}"
    )


def read_commit_blob(repo_root: Path, commit: str, rel_path: str) -> str:
    """`git show <commit>:<path>` 로 **커밋 blob** 을 읽는다 (워킹트리가 아니다).

    Args:
        repo_root: 저장소 루트.
        commit: 불변 커밋 이름(16진 sha).
        rel_path: 저장소 상대 경로.

    Returns:
        blob 텍스트.

    Raises:
        ContractParseError: git 실행 실패 또는 해당 blob 부재.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{commit}:{rel_path}"],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ContractParseError(f"git 을 실행하지 못했다: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()[:200]
        raise ContractParseError(
            f"'git show {commit}:{rel_path}' 실패 (rc={proc.returncode}): {detail}"
        )
    return proc.stdout.decode("utf-8")


def count_unanchored_in_text(text: str) -> int:
    """텍스트 하나에서 미앵커 좌표 개수를 재는 단일 진입점 (측정의 유일 소스)."""
    return len(derive_unanchored_citations(ContractDoc(text, "<blob>")))


def check_c2up(
    doc: ContractDoc,
    baseline_path: Path,
    repo_root: Path,
    notices: list[str] | None = None,
) -> list[Violation]:
    """C2UP — 기준선이 «자기 측정 출처에 대해 하는 주장»을 기계로 강제한다.

    기준선 파일은 «이 개수를 커밋 X 의 blob 에서 쟀다»고 적는다.  그 필드는 사람이
    적는 산문이므로 **워킹트리를 재고 커밋 이름만 적어 넣는 실수**가 구조적으로 가능하다
    (이 검사기의 초판이 실제로 그렇게 만들어졌다).  그래서 `git show <commit>:<path>` 로
    **그 blob 을 다시 재어** 기입값과 대조한다 — 불일치면 red.

    커밋 이름은 16진 sha 만 받는다.  `HEAD`·브랜치명 같은 «움직이는 ref» 를 허용하면
    주장이 매 실행마다 다른 대상을 가리켜 검증이 성립하지 않는다.

    Args:
        doc: 계약 문서 컨텍스트(진단 경로 표기용).
        baseline_path: 기준선 JSON 경로.
        repo_root: 저장소 루트.
        notices: 위반이 아닌 운영 안내를 모으는 목록(있으면).

    Returns:
        위반 목록.
    """

    def fail(message: str) -> list[Violation]:
        return [Violation("TOS-CC-C2UP", doc.display_path, 0, message)]

    try:
        record = read_unanchored_baseline(baseline_path)
    except ContractParseError as exc:
        return fail(f"기준선을 읽지 못해 측정 출처를 검증할 수 없다 — {exc}")

    try:
        source = read_baseline_source(repo_root, record)
        remeasured = count_unanchored_in_text(source)
    except ContractParseError as exc:
        return fail(f"측정 출처를 다시 재지 못했다 — {exc}")

    origin = (
        f"{record.commit}:{record.path}"
        if record.kind == BASELINE_KIND_COMMIT
        else f"워킹트리 {record.path}"
    )
    if remeasured != record.count:
        return fail(
            f"기준선의 자기 주장이 거짓이다 — '{BASELINE_UNANCHORED_KEY}'={record.count} "
            f"이지만 {origin} 을 다시 재면 {remeasured} 다 "
            "(다른 대상을 재고 출처만 적었을 때 나타나는 형태)"
        )

    if record.kind == BASELINE_KIND_WORKTREE and notices is not None:
        # 위반은 아니다 — 운영자가 «커밋 전»이라고 정직하게 적은 과도기 상태다.  다만
        # 워킹트리는 불변 객체가 아니라서 이 주장은 언제든 스스로 거짓이 될 수 있다.
        # 그 사실을 매 실행 표면에 남긴다(조용한 과도기는 영구가 된다).
        notices.append(
            f"[TOS-CC-C2UP] 기준선 측정 출처가 «{BASELINE_KIND_WORKTREE}»(커밋 전)다. "
            "워킹트리는 불변이 아니므로 이 결속은 잠정이다 — 계약 편집을 커밋한 뒤 "
            f"`--measure-baseline <sha>` 로 재측정해 "
            f"'{BASELINE_KIND_KEY}': '{BASELINE_KIND_COMMIT}' 로 승격하라."
        )

    logger.info(
        "C2UP: 기준선 %d == %s 재측정 %d (측정 출처 검증됨 · kind=%s)",
        record.count,
        origin,
        remeasured,
        record.kind,
    )
    return []


def check_c2u(
    doc: ContractDoc, baseline_path: Path, notices: list[str] | None
) -> list[Violation]:
    """C2U — 미앵커 좌표 잔여가 «늘지 않는다»만 보장한다 (닫음이 아니라 래칫).

    Args:
        doc: 계약 문서 컨텍스트.
        baseline_path: 기준선 JSON 경로.
        notices: 위반이 아닌 운영 안내를 모으는 목록(있으면).

    Returns:
        위반 목록.
    """
    sites = derive_unanchored_citations(doc)
    actual = len(sites)

    try:
        baseline = read_unanchored_baseline(baseline_path).count
    except ContractParseError as exc:
        # 기준선 부재를 «0 위반» 으로 접으면 래칫이 장식이 된다 — 부재 자체가 red.
        return [
            Violation(
                "TOS-CC-C2U",
                doc.display_path,
                0,
                f"래칫 기준선을 확립할 수 없다 — {exc} "
                f"(실측 미앵커 좌표 {actual}자리 · 부재를 «0 위반»으로 접지 않는다)",
            )
        ]

    logger.info(
        "C2U: 미앵커 자기인용 %d자리 (기준선 %d · %s)",
        actual,
        baseline,
        baseline_path,
    )

    if actual > baseline:
        # 자리는 «잔여의 말미» 로 잡는다.  래칫은 계수 하나만 내므로 자리를 0 으로 두면
        # 이미 red 인 상태에서 좌표가 또 늘어도 «계수 불변·자리 불변» 이라 대조군이
        # 판별력을 잃는다(실측으로 확인).  말미 자리는 참인 진술이면서 관측면이 된다.
        return [
            Violation(
                "TOS-CC-C2U",
                doc.display_path,
                sites[-1][0] if sites else 0,
                f"앵커 없는 자기인용 좌표가 기준선 {baseline} 에서 {actual} 로 "
                f"{actual - baseline}자리 늘었다 — 이 잔여는 본문 행 삽입에 조용히 밀리는 "
                f"극성 fail-open 이므로 «늘리지 않는다» 가 규율이다 "
                f"(말미 자리 {[ln for ln, _ in sites[-5:]]}, 기준선 {baseline_path})",
            )
        ]

    if actual < baseline and notices is not None:
        notices.append(
            f"[TOS-CC-C2U] 미앵커 자기인용 좌표가 {baseline} → {actual} 로 줄었다. "
            f"{baseline_path} 의 '{BASELINE_UNANCHORED_KEY}' 를 {actual} 로 "
            "**사람이** 갱신하라 — 검사기는 자기 기준선을 낮추지 않는다(RATCHET-1)."
        )
    return []


# ============================================================================
# C3 — 미래 지향 필드의 리터럴 버전 금지
# ============================================================================


def _standing_literal(
    line: str, offset: int, segment: str, current: tuple[int, int]
) -> str | None:
    """`segment` 안에서 «현행 이상»의 동일 major 리터럴 중 **첫 자리**를 돌려준다.

    과거 판 리터럴(«v2.4·v2.5 의 실패»)은 역사 참조다.  미래 지향 필드에서 문제가 되는
    것은 «현행 이상»을 리터럴로 못박는 자리다.  편집 출처 표기(`**[v2.9 신설]**`)는
    S-12 상 이력 기록이므로 제외하며, 그 판정은 **원문 오프셋**으로 되돌아본다 —
    여는 각괄호가 셀 경계 바로 앞에 올 수 있기 때문이다.

    Args:
        line: 조각이 속한 원문 행 전체.
        offset: `segment` 의 원문 시작 오프셋.
        segment: 검사할 조각(표 셀 또는 행 전체).
        current: 현행 버전 `(major, minor)`.

    Returns:
        리터럴 표기(예: `'v2.22'`), 없으면 None.
    """
    major, minor = current
    for m in VERSION_LITERAL_RE.finditer(segment):
        found = (int(m.group(1)), int(m.group(2)))
        if found[0] != major:
            continue  # 도구 버전(v4.48·v7.0 …) — 계약 버전 네임스페이스가 아니다
        abs_start = offset + m.start()
        if PROVENANCE_OPEN_RE.search(
            line[max(0, abs_start - PROVENANCE_LOOKBACK) : abs_start]
        ):
            continue  # `**[v2.9 신설]**` — 편집 출처 표기 = 이력 기록(S-12)
        if found >= (major, minor):
            return m.group(0)
    return None


def check_c3(doc: ContractDoc) -> list[Violation]:
    """C3 — 현행 버전에서 파생한 «미래» 판정으로 리터럴 버전을 잡는다.

    C3A 는 «자리» 단위 검사라 행 전체를 훑는다.  C3B 는 «필드» 단위 규칙이므로
    공존 판정을 표 셀 안으로 좁힌다 (CELL-1).
    """
    violations: list[Violation] = []
    major, minor = doc.current_version
    forward_hits = 0

    exempt_history = 0
    cell_scoped_rows = 0
    for lineno, line in enumerate(doc.lines, start=1):
        history = doc.is_history_row(lineno)

        # -- C3A: 자리 단위 — 셀 분해와 무관하다 ---------------------------
        for m in VERSION_LITERAL_RE.finditer(line):
            found = (int(m.group(1)), int(m.group(2)))
            if found[0] != major:
                continue  # 도구 버전(v4.48·v7.0 …) — 계약 버전 네임스페이스가 아니다
            if PROVENANCE_OPEN_RE.search(
                line[max(0, m.start() - PROVENANCE_LOOKBACK) : m.start()]
            ):
                continue  # `**[v2.9 신설]**` — 편집 출처 표기 = 이력 기록(S-12)
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

        if history:
            continue

        # -- C3B: «필드»(= 표 셀) 단위 공존 --------------------------------
        cells = _split_cells(line)
        if len(cells) > 1:
            cell_scoped_rows += 1
        for index, (offset, cell) in enumerate(cells):
            literal = _standing_literal(line, offset, cell, doc.current_version)
            if literal is None:
                continue
            matched = [t for t in doc.future_field_terms if t and t in cell]
            if not matched:
                continue
            forward_hits += 1
            where = f"셀 {index}" if len(cells) > 1 else "행 전체"
            violations.append(
                Violation(
                    "TOS-CC-C3B",
                    doc.display_path,
                    lineno,
                    f"머리말이 선언한 미래 지향 필드 어휘 {matched} 자리에 "
                    f"리터럴 버전 '{literal}' — «현행 버전»으로 참조해야 한다(S-11) "
                    f"[공존 단위 {where}, col {offset}]",
                )
            )

    logger.info(
        "C3: 현행 v%d.%d · 미래 지향 어휘 %s · 어휘+리터럴 자리 %d건 · "
        "이력 행 면제 %d건 · 셀 분해 적용 행 %d",
        major,
        minor,
        doc.future_field_terms,
        forward_hits,
        exempt_history,
        cell_scoped_rows,
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


def default_baseline_path() -> Path:
    """검사기와 같은 디렉터리의 래칫 기준선 경로 (RATCHET-1)."""
    return Path(__file__).resolve().parent / DEFAULT_BASELINE_NAME


def default_repo_root() -> Path:
    """`tools/` 의 상위 = 저장소 루트."""
    return Path(__file__).resolve().parent.parent


def check_document(
    text: str,
    display_path: str,
    min_anchor: int = MIN_ANCHOR_LEN,
    skip_sweep: bool = False,
    baseline_path: Path | None = None,
    notices: list[str] | None = None,
    repo_root: Path | None = None,
) -> list[Violation]:
    """계약 문서 텍스트에 모든 축을 적용한다.

    Args:
        text: 계약 문서 전체 텍스트.
        display_path: 진단 출력용 경로 표기.
        min_anchor: C2B 앵커 최소 길이.
        skip_sweep: True 면 C4B(무태그 스윕)를 위반에서 제외한다.
        baseline_path: C2U 래칫 기준선 경로.  None 이면 검사기 옆의 기본 파일 —
            «지정 안 함»을 «검사 안 함»으로 접지 않는다.
        notices: 위반이 아닌 운영 안내를 모으는 목록(있으면).
        repo_root: C2UP 가 측정 출처 blob 을 읽을 저장소 루트.

    Returns:
        위반 목록.  파생 자체가 실패하면 `TOS-CC-PARSE` 단일 위반을 돌려준다
        (예외를 삼키고 green 을 내지 않는다).
    """
    baseline = baseline_path if baseline_path is not None else default_baseline_path()
    root = repo_root if repo_root is not None else default_repo_root()
    try:
        doc = ContractDoc(text, display_path)
    except ContractParseError as exc:
        return [Violation("TOS-CC-PARSE", display_path, 0, str(exc))]

    violations: list[Violation] = []
    axes: Sequence[tuple[str, CheckFn]] = (
        ("C1", check_c1),
        ("C2", lambda d: check_c2(d, min_anchor)),
        ("C2U", lambda d: check_c2u(d, baseline, notices)),
        ("C2UP", lambda d: check_c2up(d, baseline, root, notices)),
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
    "Mutation",
    ["name", "rule", "direction", "transform", "expect", "baseline", "ref_baseline"],
    defaults=(None, None, None),
)
"""대조군 한 건.

`expect` 는 `capture`(진단 문구에 포착값이 실재해야 한다)와 `notice`(안내 문구에
이 조각이 실재해야 한다) 방향에서만 쓴다.

`baseline` / `ref_baseline` 은 **기준선 픽스처 키**다(`None` = 실운용 파일,
그 외는 `FIXTURE_*`).  둘을 나눈 이유는 두 종류의 대조군이 있기 때문이다::

  * «기준선 자체» 를 변이시키는 대조군 — 변이본만 픽스처를 바꾸고 기준(ref)은 실운용.
  * «문서» 를 변이시키는 대조군 — 판정이 주변 기준선 상태에 흔들리지 않도록 **양쪽 모두**
    같은 픽스처로 고정한다.

두 번째가 이번 판에서 실제로 문제였다: 앵커화 대조군이 주변 기준선(실운용 파일)에
의존한 탓에, 문서가 이미 기준선을 초과한 상태에서는 «감소»를 만들 수 없어 `1→1` 로
죽었다.  **대조군은 자기 판정에 필요한 픽스처를 스스로 들고 있어야 한다.**
"""

#: 기준선 픽스처 키.
FIXTURE_MEASURED = "measured"  # 검사 «대상 문서» 실측값으로 핀 → C2U green 보장
FIXTURE_MISSING = "missing"  # 존재하지 않는 경로
FIXTURE_NOT_JSON = "not-json"  # 존재하지만 JSON 이 아닌 파일
FIXTURE_PROVENANCE_OK = "prov-ok"  # 출처 blob 실측값으로 핀 → C2UP green 보장
FIXTURE_STALE_COUNT = "stale-count"  # 출처는 참이나 개수가 blob 과 불일치
FIXTURE_BAD_COMMIT = "bad-commit"  # 움직이는 ref
FIXTURE_NO_PROVENANCE = "no-provenance"  # 출처 필드 자체가 없다


def _enum_fence(doc: ContractDoc) -> tuple[int, int]:
    """(4) 열거가 사는 코드펜스 구간을 돌려준다 (대조군 주입 지점 계산용)."""
    _, def_line, _ = derive_enum_elements(doc)
    fence = doc.enclosing_fence(def_line)
    if fence is None:
        raise ContractParseError("(4) 열거 정의가 코드펜스 안에 없다")
    return fence


def _replace_line_once(text: str, old_line: str, new_line: str) -> str:
    """행 «내용»만 바꾼다 (행 수 불변).  대상이 유일하지 않으면 대조군 무효."""
    if text.count(old_line) != 1:
        raise ContractParseError(
            f"주입 대상 행이 유일하지 않다 (count={text.count(old_line)})"
        )
    return text.replace(old_line, new_line, 1)


def _append_in_enum_fence(suffix: str) -> Callable[[str], str]:
    """(4) 열거 펜스 «안»의 안전한 행 끝에 `suffix` 를 덧붙이는 변이를 만든다.

    **행을 삽입하지 않고 기존 행에 덧붙인다.**  펜스 안에 행을 끼워 넣으면 뒤따르는
    모든 위반의 행번호가 밀려 `silent` 대조군이 통째로 «신규 자리»로 보인다 — `_append`
    가 말미에만 덧붙이는 것과 같은 사유이고, C1 대조군은 말미를 쓸 수 없다(모집단이
    펜스 안으로 한정되므로).

    숙주 행은 `(4)`·구분자·원형숫자·인용 부호·각괄호가 **없는** 행으로 고른다.  그래야
    주입한 문자열의 인용/각괄호가 숙주의 기호와 짝지어 엉뚱한 구간을 만들지 않는다.
    """

    def transform(text: str) -> str:
        doc = ContractDoc(text, "<mutation>")
        lo, hi = _enum_fence(doc)
        for lineno in range(lo + 1, hi):
            line = doc.lines[lineno - 1]
            if not line.strip() or "(4)" in line or ENUM_SEPARATOR in line:
                continue
            if CIRCLED_ITEM_RE.search(line) or any(c in line for c in "「」«»[]"):
                continue
            if text.count(line) != 1:
                continue
            return _replace_line_once(text, line, f"{line}  {suffix}")
        raise ContractParseError("(4) 펜스 안에 대조군을 덧붙일 안전한 행이 없다")

    return transform


def _bump_live_cardinality(nth: int) -> Callable[[str], str]:
    """살아 있는 (4) 기수 진술 `nth` 번째의 수를 실제 원소 수와 어긋나게 만든다.

    자리를 상수로 적지 않는다 — 이 배터리의 하드코딩 앵커들이 계약 편집 한 번에
    전부 무효가 된 것을 실측했다(재작성 사유).
    """

    def transform(text: str) -> str:
        doc = ContractDoc(text, "<mutation>")
        lo, hi = _enum_fence(doc)
        live = [s for s in iter_cardinality_statements(doc, lo, hi) if not s.exempt]
        if len(live) <= nth:
            raise ContractParseError(
                f"살아 있는 기수 진술이 {len(live)}건뿐이라 {nth}번째를 변이할 수 없다"
            )
        site = live[nth]
        line = doc.lines[site.line - 1]
        bumped = site.token.replace(str(site.claimed), str(site.claimed + 7), 1)
        return _replace_line_once(
            text, line, line[: site.start] + bumped + line[site.end :]
        )

    return transform


def _phrase_absent_from(doc: ContractDoc, head: str) -> str:
    """문서 «다른 곳»에는 실재하지만 `head` 에는 없는 축자 조각을 고른다.

    C2B 는 «주장절의 앵커가 피인용 범위에 없고 다른 곳에는 있다» 를 잡는다.  그래서
    대조군도 그 두 조건을 만족하는 문구를 **문서에서 파생**해야 한다.
    """
    for lineno in range(len(doc.lines), 2, -1):
        for token in doc.norm_lines[lineno - 1].split():
            if len(token) < MIN_ANCHOR_LEN or token in head:
                continue
            if any(c in token for c in "«»()「」[]`*"):
                continue
            return token
    raise ContractParseError("피인용 범위 밖에서만 실재하는 문구를 찾지 못했다")


def _inject_moved_citation_claim(text: str) -> str:
    """주장절의 앵커가 피인용 범위에 «없는» 자기인용을 만든다 (C2B)."""
    doc = ContractDoc(text, "<mutation>")
    phrase = _phrase_absent_from(doc, doc.range_text(1, 2))
    return _append(text, f"대조군 (:1-2: {phrase} 가 1-2행에 있다고 주장한다)")


def _inject_out_of_range_in_list(text: str) -> str:
    """인용 «목록» 안의 좌표 하나를 문서 행 범위 밖으로 민다 (C2R)."""
    doc = ContractDoc(text, "<mutation>")
    beyond = len(doc.lines) + 1000
    for line in doc.lines:
        m = CITE_LIST_RE.search(line)
        if m is None:
            continue
        coords = re.findall(r":\d+", m.group(1))
        if not coords:
            continue
        listing = m.group(0)
        cut = listing.rfind(coords[-1])
        mutated = listing[:cut] + f":{beyond}" + listing[cut + len(coords[-1]) :]
        return _replace_line_once(
            text, line, line[: m.start()] + mutated + line[m.end() :]
        )
    raise ContractParseError("인용 목록을 하나도 찾지 못했다")


def _inject_layer_tag(offset: int) -> Callable[[str], str]:
    """현행 회차에서 `offset` 만큼 어긋난 층 태그를 말미에 덧붙인다 (C4A).

    회차를 상수로 적지 않는다 — 현행 회차는 문서가 스스로 선언하므로 거기서 읽는다.
    """

    def transform(text: str) -> str:
        doc = ContractDoc(text, "<mutation>")
        round_no = doc.current_round + offset
        return _append(text, f"대조군 — 현행({round_no}차 이후) 층 태그 대조군.")

    return transform


def _inject_nonmonotonic_layer_tags(text: str) -> str:
    """한 행에 «대체되지 않는» 층 태그 둘을 둔다 (C4A 비단조 limb).

    두 태그의 회차를 «현행»으로 같게 두어, 첫 limb(현행 불일치)이 아니라 **비단조
    limb 만** 발화하게 한다 — 대조군은 한 번에 한 가지만 바꾸어야 한다.
    """
    doc = ContractDoc(text, "<mutation>")
    round_no = doc.current_round
    return _append(
        text,
        f"대조군 — 현행({round_no}차 이후) 앞 태그와 현행({round_no}차 이후) 뒤 태그.",
    )


def _anchor_one_unanchored(text: str) -> str:
    """미앵커 좌표 **한 개**를 ANCHOR-1 규약으로 앵커화한다 (문서에서 자리를 파생).

    자리를 상수로 적지 않는 이유는 이 파일의 다른 대조군들이 이미 증명했다 — 하드코딩한
    앵커는 문서가 움직이는 순간 SETUP-FAIL 로 죽는다.  여기서는 «앵커화 가능한 첫 좌표»를
    문서 구조에서 찾고, 앵커 문자열도 피인용 행에서 잘라 쓴다.

    Args:
        text: 원본 문서 텍스트.

    Returns:
        좌표 하나가 앵커화된 텍스트.

    Raises:
        ContractParseError: 앵커화할 수 있는 좌표를 찾지 못했을 때 (대조군 무효).
    """
    doc = ContractDoc(text, "<mutation>")
    for lineno, m in iter_self_citations(doc):
        line = doc.lines[lineno - 1]
        if ANCHOR1_RE.match(line, m.start()) is not None:
            continue
        if _extract_claim(line, m.start(), m.end()):
            continue
        token = m.group(0)
        if not re.fullmatch(r":\d{2,4}(?:\s*[-–—~]\s*\d{2,4})?", token):
            continue  # ANCHOR-1 이 인정하는 자릿수 밖
        if text.count(token) != 1:
            continue  # 유일하지 않으면 어느 자리를 바꿨는지 말할 수 없다
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if start <= lineno <= end:
            continue  # 인용 행 자신을 편집하면 앵커 대상 문자열이 함께 흔들린다
        anchor = _pick_anchor(doc, start)
        if anchor is None:
            continue
        return text.replace(token, f"{token}«{anchor}»", 1)
    raise ContractParseError("앵커화할 수 있는 미앵커 좌표를 찾지 못했다")


def _pick_anchor(doc: ContractDoc, lineno: int) -> str | None:
    """`lineno` 행에서 ANCHOR-1 앵커로 쓸 축자 조각을 고른다(없으면 None)."""
    body = doc.norm_lines[lineno - 1].strip()
    if any(ch in body for ch in "«»"):
        body = re.sub(r"[«»]", " ", body)
    for token in body.split():
        if len(token) >= MIN_ANCHOR_LEN and token in doc.norm_lines[lineno - 1]:
            return token
    return None


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
        # 아래 둘은 «살아 있는» 기수 진술의 자리를 문서에서 파생해 변이시킨다.
        Mutation(
            "C1-inject-first-live-cardinality",
            "TOS-CC-C1",
            "inject",
            _bump_live_cardinality(0),
        ),
        Mutation(
            "C1-inject-second-live-cardinality",
            "TOS-CC-C1",
            "inject",
            _bump_live_cardinality(1),
        ),
        # ---- C1 인용 면제 (QUOTE-1) --------------------------------------
        Mutation(
            "C1-live-cardinality-outside-quote-is-red",
            "TOS-CC-C1",
            "inject",
            # 인용 «밖»의 살아 있는 진술 — 면제를 넣은 뒤에도 반드시 red.
            _append_in_enum_fence("살아 있는 진술: (4) 의 99개 중 셋."),
        ),
        Mutation(
            "C1-quoted-cardinality-is-exempt",
            "TOS-CC-C1",
            "silent",
            # 에라타가 «대체한» 옛 표기의 인용 — 이 자리가 위양성의 실물이었다.
            _append_in_enum_fence(
                "동결~9차는 이 자리를 「(4) 의 «6개» 중 셋」으로 적었다."
            ),
        ),
        Mutation(
            "C1-provenance-bracket-cardinality-is-exempt",
            "TOS-CC-C1",
            "silent",
            # 판본 각괄호 «안»의 기수 — 편집 출처 표기이지 살아 있는 주장이 아니다.
            _append_in_enum_fence(
                "대조군 [v2.22 에라타 10차 — (4) 의 6개 중 셋] 은 인용이다."
            ),
        ),
        Mutation(
            "C1-cardinality-after-provenance-closes-is-red",
            "TOS-CC-C1",
            "inject",
            # 각괄호가 «닫힌 뒤»는 새 문언이다 — 면제가 거기까지 번지면 fail-open.
            _append_in_enum_fence("[v2.22 에라타 10차] 이후 문언: (4) 의 6개 중 셋."),
        ),
        Mutation(
            "C1-unclosed-quote-grants-no-exemption",
            "TOS-CC-C1",
            "inject",
            # 인용을 열고 닫지 않은 자리에 면제를 주면 «면제 남용»이 무료가 된다.
            _append_in_enum_fence("동결~9차는 「(4) 의 6개 중 셋 으로 적었다."),
        ),
        Mutation(
            "C1-guillemet-emphasis-grants-no-exemption",
            "TOS-CC-C1",
            "inject",
            # «…» 는 이 문서에서 강조 기호이기도 하다 — 면제 구간에 넣지 않은 결정을
            # 여기서 고정한다.  넣는 순간 이 자리가 조용해진다.
            _append_in_enum_fence("살아 있는 진술: (4) 의 «99개» 중 셋."),
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
            "C2R-inject-out-of-range-in-list",
            "TOS-CC-C2R",
            "inject",
            _inject_out_of_range_in_list,
        ),
        Mutation(
            "C2A-inject-absent-predicate",
            "TOS-CC-C2A",
            "inject",
            # 인용 목록이 병기한 포섭 술어가 피인용 행에 실측 부재.
            lambda t: _append(
                t, "대조군 [:1·:2] 가 «대조군-술어-부재-XYZ» 를 주장한다."
            ),
        ),
        Mutation(
            "C2B-inject-moved-claim",
            "TOS-CC-C2B",
            "inject",
            _inject_moved_citation_claim,
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
        # ---- C3B 셀 분해 (CELL-1) ---------------------------------------
        Mutation(
            "C3B-same-cell-coexistence",
            "TOS-CC-C3B",
            "inject",
            # 어휘와 리터럴이 **같은 셀** 안 — 좁힌 뒤에도 여전히 red 여야 한다.
            lambda t: _append(t, "| 단계 | 재심 대상은 v2.22 판이 현재 위치다 |"),
        ),
        Mutation(
            "C3B-split-cells-is-silent",
            "TOS-CC-C3B",
            "silent",
            # 리터럴은 셀 1, 어휘는 셀 2 — 갈라져야 할 둘이므로 과잉 차단 0.
            lambda t: _append(t, "| 단계 | v2.22 동결 내용 | 현재 위치 는 여기 |"),
        ),
        Mutation(
            "C3B-non-table-line-still-red",
            "TOS-CC-C3B",
            "inject",
            # 표가 아닌 행은 셀이 하나 = 행 전체 — 기존 발화가 불변임을 고정한다.
            lambda t: _append(t, "대조군 — v2.22 판의 현재 위치 는 여기다."),
        ),
        Mutation(
            "C3B-escaped-pipe-is-not-a-cell-boundary",
            "TOS-CC-C3B",
            "inject",
            # `\|` 를 분할자로 오인하면 리터럴과 어휘가 갈라져 이 자리가 조용해진다.
            # 리터럴 쪽에 다른 어휘를 두지 «않는» 것이 이 대조군의 판별력이다 — 두면
            # 이스케이프를 무시해도 그 어휘로 발화해 변이가 죽지 않는다(실측 확인).
            lambda t: _append(t, "| 단계 | 판 v2.22 \\| 현재 위치 |"),
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
            "C4A-inject-stale-layer-tag",
            "TOS-CC-C4A",
            "inject",
            _inject_layer_tag(-1),
        ),
        Mutation(
            "C4A-inject-nonmonotonic-tags",
            "TOS-CC-C4A",
            "inject",
            _inject_nonmonotonic_layer_tags,
        ),
        Mutation(
            "C4A-current-round-tag-is-silent",
            "TOS-CC-C4A",
            "silent",
            # 현행 회차와 맞는 단일 태그는 조용해야 한다 — 과잉 차단 0.
            _inject_layer_tag(0),
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
        # ---- C2U 래칫 (RATCHET-1) ----------------------------------------
        # 문서를 변이시키는 둘은 기준(ref)과 변이본 «양쪽»을 실측 픽스처로 고정한다 —
        # 주변 기준선 파일이 stale 해도 판정이 흔들리지 않아야 한다.
        Mutation(
            "C2U-inject-extra-bare-coordinate",
            "TOS-CC-C2U",
            "inject",
            # 앵커도 주장절도 없는 좌표 1개 추가 = 잔여 증가 → 래칫이 막아야 한다.
            lambda t: _append(t, "대조군 — 앵커 없는 자기인용 `:512` 를 하나 더 둔다."),
            None,
            FIXTURE_MEASURED,
            FIXTURE_MEASURED,
        ),
        Mutation(
            "C2U-anchoring-one-coordinate-is-notice",
            "TOS-CC-C2U",
            "notice",
            # 좌표 1개를 ANCHOR-1 로 앵커화 = 잔여 감소 → green + «기준선 낮춰라» 안내.
            # 자동 갱신하지 않으므로 다음 실행에서도 같은 안내가 나온다(의도).
            _anchor_one_unanchored,
            "[TOS-CC-C2U] 미앵커 자기인용 좌표가",
            FIXTURE_MEASURED,
            FIXTURE_MEASURED,
        ),
        # 기준선 «자체» 를 변이시키는 둘은 기준(ref)이 실운용 파일이어야 한다.
        Mutation(
            "C2U-baseline-file-missing",
            "TOS-CC-C2U",
            "inject",
            # 문서는 그대로 두고 «기준선만» 지운다.  부재를 «0 위반»으로 접으면 여기서
            # 조용해진다 — fail-closed 의 직접 대조군이다.
            lambda t: t,
            None,
            FIXTURE_MISSING,
            FIXTURE_MEASURED,
        ),
        Mutation(
            "C2U-baseline-file-not-json",
            "TOS-CC-C2U",
            "inject",
            # «있지만 읽어낼 수 없는» 기준선도 부재와 같은 극성이어야 한다.
            lambda t: t,
            None,
            FIXTURE_NOT_JSON,
            FIXTURE_MEASURED,
        ),
        # ---- C2UP 측정 출처 (PROVENANCE-1) --------------------------------
        Mutation(
            "C2UP-count-disagrees-with-blob",
            "TOS-CC-C2UP",
            "inject",
            # 출처 커밋은 참인데 개수만 다르다 = «워킹트리를 재고 커밋 이름만 적은» 형태.
            lambda t: t,
            None,
            FIXTURE_STALE_COUNT,
            FIXTURE_PROVENANCE_OK,
        ),
        Mutation(
            "C2UP-moving-ref-as-provenance",
            "TOS-CC-C2UP",
            "inject",
            # `HEAD` 는 매 실행마다 다른 대상을 가리켜 주장을 검증 불가로 만든다.
            lambda t: t,
            None,
            FIXTURE_BAD_COMMIT,
            FIXTURE_PROVENANCE_OK,
        ),
        Mutation(
            "C2UP-provenance-absent",
            "TOS-CC-C2UP",
            "inject",
            # 출처 없는 기준선을 «검증 통과»로 접으면 필드가 장식이 된다.
            lambda t: t,
            None,
            FIXTURE_NO_PROVENANCE,
            FIXTURE_PROVENANCE_OK,
        ),
        Mutation(
            "C2UP-real-baseline-provenance-verifies",
            "TOS-CC-C2UP",
            "clean",
            # **실운용** 기준선을 그대로 쓰고, «0 건» 이라는 **절대** 기대를 건다.
            # 이 축의 가장 강한 대조군이다.  `silent`(상대 비교)로 두면 기준 실행이
            # 이미 red 일 때 계수가 포화해 무의미해지고, 픽스처로 대체하면 기대값이
            # 같은 리더로 만들어져 순환한다 — 둘 다 실측으로 확인했다.
            # 사람이 커밋에 결속해 적어 둔 값만이 리더와 독립한 oracle 이다.
            lambda t: _append(t, "대조군 — 문서 편집은 C2UP 판정을 바꾸지 않는다."),
            None,
            None,
            None,
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


def _write_fixture(path: Path, payload: dict[str, object]) -> Path:
    """픽스처 기준선 파일 하나를 쓴다."""
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def build_baseline_fixtures(
    text: str, tmpdir: Path, real_baseline: Path, repo_root: Path
) -> dict[str | None, Path]:
    """대조군이 요구하는 기준선 픽스처들을 만든다.

    두 축은 «green 인 기준»의 정의가 다르므로 픽스처도 갈라야 한다.  하나로 합치면 한
    축의 기준이 다른 축에서 이미 red 라서 계수가 포화하고 대조군이 조용히 죽는다
    (이번 판에서 두 번 실측했다 — 그래서 규칙으로 적는다)::

      * C2U  green = 개수가 **검사 대상 문서** 실측과 맞을 때   → `FIXTURE_MEASURED`
      * C2UP green = 개수가 **출처 커밋 blob** 실측과 맞을 때   → `FIXTURE_PROVENANCE_OK`

    결함 픽스처들은 `FIXTURE_PROVENANCE_OK` 에서 **한 가지만** 바꿔 만든다.

    Args:
        text: 검사 대상 문서 텍스트.
        tmpdir: 픽스처를 쓸 임시 디렉터리.
        real_baseline: 실운용 기준선 경로 (출처 필드를 빌려온다).
        repo_root: 출처 blob 을 읽을 저장소 루트.

    Returns:
        픽스처 키 → 경로 사상 (`None` 은 실운용 경로).

    Raises:
        ContractParseError: 실운용 기준선의 출처 blob 을 재지 못했을 때 — 그 경우
            C2UP 대조군의 «green 인 기준» 자체를 만들 수 없으므로 조용히 넘기지 않는다.
    """
    record = read_unanchored_baseline(real_baseline)
    prov = {
        BASELINE_KIND_KEY: record.kind,
        "commit": record.commit,
        "path": record.path,
    }
    # 검증과 같은 리더를 쓴다 — 픽스처의 기대값을 다른 경로로 만들면 «무엇을 재는가»가
    # 조용히 갈라져 C2UP 대조군이 자기 자신을 검증하게 된다.
    blob_count = count_unanchored_in_text(read_baseline_source(repo_root, record))

    return {
        None: real_baseline,
        FIXTURE_MEASURED: _write_fixture(
            tmpdir / "measured.json",
            {
                BASELINE_UNANCHORED_KEY: count_unanchored_in_text(text),
                BASELINE_PROVENANCE_KEY: prov,
            },
        ),
        FIXTURE_MISSING: tmpdir / "there-is-no-such-file.json",
        FIXTURE_NOT_JSON: Path(__file__).resolve(),
        FIXTURE_PROVENANCE_OK: _write_fixture(
            tmpdir / "prov-ok.json",
            {BASELINE_UNANCHORED_KEY: blob_count, BASELINE_PROVENANCE_KEY: prov},
        ),
        FIXTURE_STALE_COUNT: _write_fixture(
            tmpdir / "stale-count.json",
            {BASELINE_UNANCHORED_KEY: blob_count + 1, BASELINE_PROVENANCE_KEY: prov},
        ),
        FIXTURE_BAD_COMMIT: _write_fixture(
            tmpdir / "bad-commit.json",
            {
                BASELINE_UNANCHORED_KEY: blob_count,
                BASELINE_PROVENANCE_KEY: {
                    BASELINE_KIND_KEY: BASELINE_KIND_COMMIT,
                    "commit": "HEAD",
                    "path": record.path,
                },
            },
        ),
        FIXTURE_NO_PROVENANCE: _write_fixture(
            tmpdir / "no-provenance.json", {BASELINE_UNANCHORED_KEY: blob_count}
        ),
    }


def run_self_test(
    text: str,
    display_path: str,
    min_anchor: int,
    baseline_path: Path,
    repo_root: Path,
) -> int:
    """뮤테이션 배터리를 돌려 «죽은 검사 0» 을 실증한다.

    각 대조군은 **자기 픽스처와 짝지은 기준(reference) 실행**과 대조된다.  주변 상태를
    기준으로 쓰면(=실운용 기준선 파일) 그 파일이 stale 해지는 순간 대조군이 조용히
    죽는다 — 이번 판에서 실제로 그렇게 죽었다.

    Args:
        text: 원본 계약 문서 텍스트.
        display_path: 진단 출력용 경로 표기.
        min_anchor: C2B 앵커 최소 길이.
        baseline_path: 실운용 C2U 래칫 기준선 경로.
        repo_root: C2UP 가 측정 출처 blob 을 읽을 저장소 루트.

    Returns:
        프로세스 종료 코드 (죽은 검사가 하나라도 있으면 1).
    """
    with tempfile.TemporaryDirectory(prefix="tos-contract-selftest-") as tmp:
        try:
            fixtures = build_baseline_fixtures(
                text, Path(tmp), baseline_path, repo_root
            )
        except ContractParseError as exc:
            # 픽스처를 못 만들면 배터리 전체가 «green 인 기준»을 잃는다.  조용히
            # 축소 실행하지 않고 여기서 시끄럽게 실패한다.
            print(f"self-test: FAIL — 대조군 픽스처 구성 실패: {exc}")
            return 1
        return _run_battery(
            text, display_path, min_anchor, baseline_path, repo_root, fixtures
        )


def _reference_index(
    text: str,
    display_path: str,
    min_anchor: int,
    repo_root: Path,
    baseline: Path,
    cache: dict[Path, tuple[dict[str, int], dict[str, set[int]]]],
) -> tuple[dict[str, int], dict[str, set[int]]]:
    """어떤 기준선 픽스처에 대한 «원본 문서» 발화 색인을 (캐시해) 돌려준다."""
    if baseline not in cache:
        counts: dict[str, int] = {}
        sites: dict[str, set[int]] = {}
        for v in check_document(
            text, display_path, min_anchor, False, baseline, None, repo_root
        ):
            counts[v.rule] = counts.get(v.rule, 0) + 1
            sites.setdefault(v.rule, set()).add(v.line)
        cache[baseline] = (counts, sites)
    return cache[baseline]


def _run_battery(
    text: str,
    display_path: str,
    min_anchor: int,
    baseline_path: Path,
    repo_root: Path,
    fixtures: dict[str | None, Path],
) -> int:
    """대조군 배터리 본체 (픽스처가 준비된 뒤 실행된다)."""
    cache: dict[Path, tuple[dict[str, int], dict[str, set[int]]]] = {}
    base_count, base_sites = _reference_index(
        text, display_path, min_anchor, repo_root, baseline_path, cache
    )

    print(f"self-test: 기준선 위반 {sum(base_count.values())}건 (실운용 기준선 기준)")
    for rule in sorted(base_count):
        print(
            f"  기준선 {rule}: {base_count[rule]}건 (자리 {sorted(base_sites[rule])})"
        )
    print()

    dead: list[str] = []
    invalid: list[str] = []
    for mut in build_mutations():
        try:
            mutated = mut.transform(text)
        except ContractParseError as exc:
            invalid.append(f"{mut.name} ({mut.rule}): 앵커 부재 — {exc}")
            print(f"  [SETUP-FAIL] {mut.name} ({mut.rule}) — {exc}")
            continue
        # 기준선 «픽스처» 를 바꾸는 대조군은 문서를 건드리지 않는 것이 정상이다.
        mutates_baseline = mut.baseline != mut.ref_baseline
        if mutated == text and not mutates_baseline:
            # 문서를 하나도 바꾸지 못한 변이는 «판별했다»고 말할 수 없다.  이전 판은
            # 이것을 DEAD 로 접어 «검사가 죽었다» 와 «대조군이 무효다» 를 뒤섞었다.
            reason = "변이가 문서를 전혀 바꾸지 못했다 (치환 대상 부재)"
            invalid.append(f"{mut.name} ({mut.rule}): {reason}")
            print(f"  [SETUP-FAIL] {mut.name} ({mut.rule}) — {reason}")
            continue

        ref_counts, ref_sites = _reference_index(
            text,
            display_path,
            min_anchor,
            repo_root,
            fixtures[mut.ref_baseline],
            cache,
        )
        notices: list[str] = []
        got = check_document(
            mutated,
            display_path,
            min_anchor,
            False,
            fixtures[mut.baseline],
            notices,
            repo_root,
        )
        got_count = sum(1 for v in got if v.rule == mut.rule)
        got_sites = {v.line for v in got if v.rule == mut.rule}
        before = ref_counts.get(mut.rule, 0)
        # 메시지 본문은 문서 편집으로 함께 바뀌므로 판정 피연산자로 쓰지 않는다.
        # 하중은 «그 규칙의 계수» 와 «발화 자리 집합» 이 진다.
        delta = got_count - before
        moved = got_sites - ref_sites.get(mut.rule, set())

        if mut.direction == "repair" and before == 0:
            # «수리» 대조군은 기준 실행에 그 위반이 실재한다는 전제 위에 선다.  전제가
            # 깨진 채 돌리면 «수리해도 줄지 않았다» 가 되어 검사기 결함으로 오귀속된다.
            reason = f"수리할 대상이 기준 실행에 없다 ({mut.rule} before=0)"
            invalid.append(f"{mut.name} ({mut.rule}): {reason}")
            print(f"  [SETUP-FAIL] {mut.name} ({mut.rule}) — {reason}")
            continue

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
        elif mut.direction == "clean":
            # 상대 비교(«늘지 않았다»)가 아니라 **절대** 기대(«0 건»).  기준 실행이 이미
            # red 인 상황에서도 판별력을 잃지 않는 유일한 형태다.
            ok = got_count == 0
            detail = f"{mut.rule} 위반 {got_count}건 (0 이어야 한다)"
        elif mut.direction == "notice":
            # 잔여가 «줄었을» 때의 계약 — 위반은 늘지 않고(green), 갱신 안내는 나온다.
            # 안내가 없는 green 은 래칫이 조용히 헐거워진 것과 구별되지 않는다.
            seen = [n for n in notices if mut.expect in n]
            ok = delta <= 0 and not moved and bool(seen)
            detail = (
                f"{mut.rule} {before}→{got_count} · 갱신 안내 "
                f"{'있음' if seen else '없음'}"
            )
        else:  # silent — 잡으면 안 되는 변형
            ok = delta <= 0 and not moved
            detail = f"{mut.rule} {before}→{got_count} (불변이어야 한다)"

        status = "PASS" if ok else "DEAD"
        if not ok:
            dead.append(f"{mut.name} ({mut.rule}/{mut.direction}) — {detail}")
        print(f"  [{status}] {mut.name:36s} {mut.rule:14s} {mut.direction:7s} {detail}")

    print()
    total = len(build_mutations())
    if dead or invalid:
        print(
            f"self-test: FAIL — 뮤테이션 {total}종 중 "
            f"죽은 검사 {len(dead)}건 · 대조군 무효 {len(invalid)}건"
        )
        # 둘은 다른 사실이다.  «죽은 검사» = 검사가 변이를 판별하지 못했다(검사기 결함).
        # «대조군 무효» = 변이를 문서에 넣지 못했다(문서가 움직여 앵커가 사라졌다).
        for d in dead:
            print(f"  - [죽은 검사] {d}")
        for i in invalid:
            print(f"  - [대조군 무효] {i}")
        return 1
    print(f"self-test: PASS — 뮤테이션 {total}종 전부 판별 · 죽은 검사 0")
    return 0


# ============================================================================
# CLI
# ============================================================================


def measure_baseline(repo_root: Path, rev: str, rel_path: str) -> int:
    """`rev` 의 blob 에서 미앵커 좌표를 재어 붙여넣을 JSON 조각을 출력한다.

    **파일을 쓰지 않는다.**  래칫의 기준선 갱신은 사람의 기록 행위여야 하므로, 이
    명령은 «워킹트리가 아니라 커밋 blob 에서 재는» 절차만 기계화하고 기입은 사람에게
    남긴다.  ref 는 여기서 즉시 불변 sha 로 해소해 출력한다.

    Args:
        repo_root: 저장소 루트.
        rev: 측정할 리비전 (ref 도 받아 sha 로 해소한다).
        rel_path: 저장소 상대 계약 문서 경로.

    Returns:
        종료 코드 — 0 성공, 2 측정 실패.
    """
    try:
        if rev == BASELINE_KIND_WORKTREE:
            record = BaselineRecord(0, BASELINE_KIND_WORKTREE, None, rel_path)
            origin = f"워킹트리 {rel_path}"
        else:
            proc = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "rev-parse",
                    "--verify",
                    f"{rev}^{{commit}}",
                ],
                capture_output=True,
                check=False,
            )
            if proc.returncode != 0:
                raise ContractParseError(
                    f"리비전을 해소하지 못했다: {rev} — "
                    f"{proc.stderr.decode('utf-8', 'replace').strip()[:200]}"
                )
            sha = proc.stdout.decode().strip()
            record = BaselineRecord(0, BASELINE_KIND_COMMIT, sha, rel_path)
            origin = f"{sha[:8]}:{rel_path} blob"
        count = count_unanchored_in_text(read_baseline_source(repo_root, record))
    except ContractParseError as exc:
        print(f"tos-contract: ERROR — 기준선 측정 실패: {exc}")
        return 2

    prov: dict[str, object] = {BASELINE_KIND_KEY: record.kind, "path": rel_path}
    if record.kind == BASELINE_KIND_COMMIT:
        prov["commit"] = record.commit
    payload = {
        BASELINE_PROVENANCE_KEY: prov,
        BASELINE_UNANCHORED_KEY: count,
    }
    print(f"tos-contract: {origin} 실측 미앵커 좌표 = {count}자리")
    print("아래를 기준선 파일에 «사람이» 반영하라 (이 명령은 파일을 쓰지 않는다):")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


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
        "--baseline",
        type=Path,
        default=None,
        help=(
            "C2U 래칫 기준선 JSON "
            f"(기본: <검사기 디렉터리>/{DEFAULT_BASELINE_NAME}; 부재하면 red)"
        ),
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
        "--measure-baseline",
        metavar="COMMIT|worktree",
        default=None,
        help=(
            "그 커밋의 blob 에서 미앵커 좌표를 재어 붙여넣을 기준선 JSON 을 **출력만** "
            "한다 (자동 갱신하지 않는다 — RATCHET-1).  커밋 전 과도기에는 'worktree' 를 "
            "주면 워킹트리를 재고 그 사실을 kind 로 기입한다"
        ),
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

    baseline_path = (args.baseline or default_baseline_path()).resolve()
    if args.measure_baseline:
        return measure_baseline(repo_root, args.measure_baseline, rel)

    notices: list[str] = []
    try:
        if args.self_test:
            return run_self_test(text, rel, args.min_anchor, baseline_path, repo_root)
        violations = check_document(
            text,
            rel,
            args.min_anchor,
            args.skip_sweep,
            baseline_path,
            notices,
            repo_root,
        )
    except Exception:  # noqa: BLE001 — 어떤 내부 예외도 green 이 되어선 안 된다
        logger.exception("검사 중 내부 예외")
        print("tos-contract: ERROR — 내부 예외 (rc=2)")
        return 2

    for notice in notices:
        print(f"tos-contract: NOTICE — {notice}")

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
