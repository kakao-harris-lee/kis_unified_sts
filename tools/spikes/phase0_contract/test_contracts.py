#!/usr/bin/env python3
"""Phase 0 완료 계약 프로토타입의 **대조군** — pytest 없이 단독 실행한다.

    python3 tools/spikes/phase0_contract/test_contracts.py

목표는 green 이 아니라 반증이다.  각 대조군은 **양방향**으로 관측한다.
한 방향만 확인한 대조군은 무효다.

## 보고 채널 — 발견은 exit status 에 결속된다 (교정 1 / v2.5 재설계)

  **Case**  양방향 관측.  `방향①`(기준) 과 `방향②`(변형) 이 **둘 다 성립**해야 OK 다.
            OK 가 아닌 Case 가 하나라도 있으면 `exit_status()` 가 1 을 돌려준다
            — 그 함수 자체의 same-process 한계는 `L-EXIT-ROOT` 가 등재한다.
            검출형 Case 의 `방향② 성립` = "뮤테이션이 red 로 잡혔다".
            앵커형 Case 의 `방향② 성립` = "고정된 예측대로 관측됐다".
  **발견**  `rep.defect(tid, ...)` — 관측된 계약 위반.  **같은 tid 의 Case 가 반드시
            있어야 하고 그 Case 는 red 여야 한다.**  발견은 집계에서 빠지지 않는다.
  **한계**  `rep.limit(lid, text, case=/unchk=)` — 한계·범위 서술.  **모든 노트는
            `lid` 를 갖고 그 `lid` 는 설정에 등재돼 있어야 한다.**

## v2.5 — 어휘 분류를 폐기하고 **등재**로 옮겼다 (심판 F1)

v2.3 은 `DEFECT_WORDS` 7 개 닫힌 목록으로 "결함 주장 노트"를 분류하려 했고,
심판이 **목록 밖 서술**(`잡지 못한다`)·**green Case 주차**(`[Case:T-75]`)·
동의어 치환 3 종으로 전부 우회해 **미수정 결함 2 건을 exit 0 으로 통과**시켰다.

교훈은 목록이 짧았다는 게 아니다.  **산문이 결함 주장인지 판정하는 것은
결정 불가능**하며, 실제로 이 러너의 정당한 한계 노트도 `잡지 못한다` 를
쓴다(UNCHK-019).  목록을 늘리는 교정은 같은 게임을 다시 지는 것이다.

그래서 v2.5 는 두 층으로 나눈다:

  **L1 등재 강제 (구조적)**  모든 노트는 `lid` 를 갖고, 그 집합은 설정의
      `declared_limit_ids` 와 **정확히 일치**해야 한다.  누락도 잉여도 red 다.
      ⇒ 발견을 노트로 흘리려면 **설정을 고쳐야 하고, 그것은 diff 에 남는다.**
      이것은 **폐쇄가 아니라 가시화**다.  그렇게 적는다.
  **L2 주차 거부 (패턴 한정)**  결함 어휘를 쓴 노트는 **등재된 갭**(`unchk=`)
      이나 **red Case**(`case=`) 에 결속돼야 한다.  green Case 주차를 거부한다
      — v2.3 의 비대칭(발견 경로만 red 를 검사)이 여기서 사라진다.
      **닫힌 목록이므로 L2 는 불완전하다.**  목록 밖 서술은 L2 가 아니라
      L1 이 잡는다.

**남는 것**: 설정을 함께 고치면 노트는 추가된다.  Case `detail` 문자열과
`print()` 는 이 계약 밖이다.  아예 관측하지 않는 결함은 어느 층도 잡지 못한다.

## OD-3 경계에서 T-77 이 실제로 강제하는 것

  A  코퍼스·register 접근 금지 — **프로세스 전역 감사 hook**(정본) +
     monkeypatch 가드(심층 방어) + 리터럴/AST 합성 소스 스캔(심층 방어)
  B  금지 D0 아티팩트 미생성 — **각 항목을 하나씩** 표적으로 관측한다
  C  실행 중 파일 쓰기 0 — 감사 hook + Python 표준 라이브러리 진입점

  **D(CI 미편입)·E(D0 승격 금지)에는 기계 검사가 없다.**  강제한다고 쓰지 않는다.
  이 러너 파일 자체가 `proto/` 밖에 있다는 사실도 출력에 그대로 적는다.

## v2.6 — 강제를 import 이전으로 옮겼다 (심판 F3 critical / F1 high)

v2.5 의 가드는 `main()` 안에서 열렸다.  피검사 모듈의 **import 는 그보다 먼저**
일어나므로 모듈 레벨 문장이 가드 창 밖에서 돌았고, 심판은 그 창으로 실제
register 93,904 바이트를 읽고도 exit 0 · 30/30 GREEN · 앵커 4 종 불변을
재현했다.  교정은 네 갈래다:

  **F3-①** `audit_guard` 가 `proto` 보다 먼저 import 되며 그 순간 프로세스 전역
      감사 hook 을 설치한다.  이 순서 자체를 `T-77-AUDIT` 이 자기 소스의 AST 에서
      파생해 관측한다 — 자기신고가 아니다.
  **F3-②** 경로 동치는 casefold 정규화로, 위치 표지는 `.git` + `samefile` 로
      좁혔다.
  **F1-①** `clean_green` 을 손으로 쓴 불리언식에서 **명명된 검사 dict** 파생으로
      바꾸고, 각 항이 실제로 소비되는지를 `SELF-2` 가 전수 관측한다.
  **F1-②** 앵커에 `co_code`·`co_names` 와 **소스 바이트 digest** 를 더해
      모듈 레벨 데이터·주석·`__init__.py` 를 정의역 안으로 넣었다.

## v2.7 — 관측 채널을 exit 에 결속했다 (심판 7 건 전건 채택)

v2.6 의 관통 패턴은 "관측은 하는데 exit 에 닿지 않는다" 였다.  가드가 실제
경계 위반을 탐지·기록해도 대상이 `AuditViolation` 을 삼키면 exit 0 이었고
(#2), 앵커 드리프트는 `collect_self_checks()` 의 **단일 항** 하나로만 닿았다
(#1).  교정은 일곱 갈래다:

  **#1** `SELF-2` 를 합성 dict 가 아니라 **실제 `Report` 위반을 심은 양성
      대조군**으로 재설계했다 — producer 가 값을 버리면 red 가 된다.  앵커
      드리프트는 `SELF-3` 이 `main()` 배선을 AST 로 관측해 **독립 결속**한다.
  **#2** 종료 코드를 `exit_status()` 한 곳으로 모으고 ⑴ Case ⑵ 대조군 창 밖
      가드 기록·정책 상태 ⑶ 앵커 드리프트 세 채널을 전부 넘긴다.  프로브
      기록과 운영 기록의 분리는 유지하되 `T-77-SEPARATION` 이 그 분리와
      "삼켜진 위반도 red 가 된다" 를 실물로 관측한다.
  **#3** hook 설치를 `audit_guard` 본문 최상단으로 올리고, 설치 시점
      `sys.modules` 스냅샷과 **pre-hook 구간 digest**(동적 로드 이름은
      fail-closed)로 순서를 고정했다.  "bootstrap 부터 armed" 의 실제 범위는
      `L-AUDIT-BOOTSTRAP` 에 다시 썼다.
  **#4** 재진입 상태를 `threading.local` 로 격리하고, hook 안에서 사용자
      콜백(`__fspath__`)을 부를 수 있는 비원시 path 인자를 fail-closed 로 막았다.
  **#5** `.git` 을 존재가 아니라 **형태별 내부 구조**로 검증하고 실제
      repository top-level 일치까지 본다.  `L-LOCATE-FORGE` 의 과대 서술을 정정했다.
  **#6** inode 별칭은 **정책을 경로명 차단으로 명시 축소**해 등재했다
      (`L-INODE-ALIAS`).  canonical identity 집합을 만들려면 코퍼스를 열거해야
      하고 그 열거가 곧 OD-3-A 가 금지하는 행위이기 때문이다.
  **#7** 판정 우주를 정의하는 모듈 정책값을 설정의 `anchor_policy_values`
      에 결속하고(`T-79`) **항목별 삭제·확장 대조군**을 붙였다.  그 표 밖에
      남는 이름은 `L-POLICY-ANCHOR` 가 열거한다 — **모듈 레벨 비호출 이름이라는
      축소된 정의역 안에서** (v2.9 정정: 클래스는 그 정의역 밖이다).

## v2.8 — **주장을 철회하고 한계를 등재했다** (심판 v2.7 6 건 전건 채택)

v2.7 의 관통 패턴은 "교정이 만든 통합 지점에서 같은 결함이 다시 난다" 였고,
심판은 그것이 반복이 아니라 **천장**임을 진단했다: 임의의 same-process 변조를
위협 모델에 포함하는 한, **더 많은 내부 자기검사로는 최종 신뢰점을 원리적으로
보호할 수 없다.**  그래서 v2.8 은 그 항목에 층을 더 쌓지 않는다.

  **critical** 최종 종료 판정(`exit_status`)은 같은 프로세스 안에서 자기 절단을
      검출할 수 없다.  운영자 처분 **B**(한계 등재 + 주장 철회)에 따라
      `L-EXIT-ROOT` 로 등재하고, **이 러너가 최종 exit 자체까지 자기증명한다는
      주장을 본문 전체에서 제거했다.**  해소책(별도 프로세스의 외부 검증자)은
      `deferred_owner_tracks` 에 owner track 과 함께 **명시 이연**했다 —
      미등재 이연은 누락과 구별되지 않기 때문이다.  트랙 값 자체는 이 산문에
      적지 않는다 (v2.9): 리터럴로 적으면 선언과 평가가 갈린다.
  **#2** 실행코드 앵커의 정의역에서 **자기신고(`__module__`)를 없앴다**.  설정
      접근은 모듈 한정 호출로 정규화했고, 소비 바인딩은 이름·**파일 라벨**·코드
      digest 로 값 앵커에 묶었으며(`runner.MODULE_BINDINGS`), 앵커 **기대값을
      읽는 경로**는 파싱 코드가 다른 판독기로 이중화해 `T-80` 이 대조한다.
      **경로 신뢰점은 이중화되지 않았다** (v2.9 정정) — `L-CONFIG-TRUSTPOINT`.
      **v2.10 주장 철회** (심판 9 회차 #2): 없앤 것은 `__module__` **하나뿐**이고
      **파일 라벨은 없애지 못했다**.  두 번째 축은 여전히 `basename(co_filename)`
      또는 `basename(__file__)` 이라는 **메타데이터 라벨**이다 — 전자는 컴파일
      시점에 제공되는 값이고 후자는 라이브 객체의 가변 속성이라, 둘 다 검증된
      provenance 가 아니다.  `L-SRC-ANCHOR` 가 그 보장 밖을 등재한다.
  **#3** 프로브 창을 **스레드 지역**으로 옮기고 **토큰 + 고정 호출 지점**으로
      인가한다.  인가되지 않은 창은 여는 것 자체가 findings 이고, 인가된 기록의
      토큰별 개수도 `anchor_probe_records` 에 결속했다.  **v2.9 정정**: 그 인가
      identity 는 공개 토큰 + `basename:co_name` 이라 사칭 가능하고 게이트는
      개수만 센다 — `L-AUDIT-PROBE-THREAD` 에 등재했다.
  **#4** pre-hook 실행문 분류가 대입의 **우변**을 본다.  "실행문 0" 은 분류
      규약의 산물이었으므로 서술을 정정하고, 그 개수를
      `anchor_prehook_executable` 에 등재했다.  동적 로드 이름 검사는 subscript
      첨자·호출 인자의 **문자열 상수**까지 본다.  **v2.9 정정**: 그 개수는
      최상위 문장의 우변·데코레이터·기본 인자라는 **축소된 정의역** 안의
      값이다 — `ClassDef` 본문은 걷지 않는다 (`L-AUDIT-BOOTSTRAP`).
  **#5** 정책값 정의역을 **자동 census** 로 파생한다.  손으로 쓴 양성 목록은
      신규 항목을 영원히 못 찾으므로, 구조에서 파생하고 **의도적 제외만**
      설정에 선언하며 잔여도 census 가 열거한다.  **v2.9 정정**: census 의
      정의역은 모듈 레벨 **비호출** 이름이다 — 클래스와 그 속성값은 어느
      분류에도 들어가지 않는다 (`L-POLICY-ANCHOR`).
  **#6** 쓰기 프로브의 표적을 **부재 부모** 밑으로 옮겼다 — 가드가 깨지는
      음성 시나리오에서도 저장소 안에 실물이 생기지 않는다.
"""

from __future__ import annotations

import ast
import hashlib
import os
import shutil
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True  # .pyc 쓰기도 파일 쓰기다 (OD-3-C)

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]

# v2.7: `sys.path.insert(...)` 를 **없앴다** (심판 #3).  문서화된 호출 방식
# (스크립트 실행)에서는 `sys.path[0]` 이 이미 이 디렉터리이므로 필요 없고,
# 아닌 경우(`-P`·`PYTHONSAFEPATH`)에는 ImportError 로 **시끄럽게** 실패한다.
#
# **v2.8 정정 (심판 v2.7 #4)**: v2.7 은 여기에 "그 결과 두 파일 모두 pre-hook
# 실행문 0 개가 되고 그것이 구조 요구사항" 이라고 적었다.  거짓이었다 —
# 바로 아래 `_HERE = Path(__file__).resolve().parent` 가 호출을 평가하는
# 실행문이고, `audit_guard.py` 쪽에는 그런 대입이 열한 개 있다.  0 은 러너가
# 대입을 우변과 무관하게 비실행으로 세던 **분류 규약의 산물**이었다.  v2.8 은
# 우변을 보아 세고 그 **개수**를 설정 `anchor_prehook_executable` 에 핀으로
# 고정한다.  이 구간은 고정될 뿐 **차단되지 않는다**.
#
# **v2.9 정정 (심판 v2.8 #3)**: 그 개수는 **최상위 문장의 우변·데코레이터·기본
# 인자** 라는 정의역 안에서만 정직하다.  `ClassDef` 본문은 import 시 즉시
# 실행되는데 분류기가 그 본문을 걷지 않으므로, 여기 클래스를 하나 두고 그
# 본문에서 파일을 열면 개수는 그대로다 (실측: `_io.FileIO(...).readall()` 로
# register 15,736 바이트를 읽고도 계수 1 불변, 금지 이름 findings 0).

# **이 두 줄의 순서가 F3 교정의 전부다** (v2.6, 심판 critical).
# `audit_guard` 는 import 되는 순간 프로세스 전역 감사 hook 을 설치한다.
# 피검사 모듈(`proto/*`)이 그보다 먼저 import 되면 모듈 레벨 문장이 가드 창
# **밖**에서 돌고, 심판은 그 창으로 실제 register 를 읽고도 전건 GREEN 을
# 재현했다.  순서가 뒤집히면 `T-77-AUDIT` 이 자기 소스를 파싱해 red 를 낸다.
import audit_guard  # noqa: E402
from proto import boundary, config, enforcement, floor, gates, register  # noqa: E402

#: monkeypatch 로 **바뀌지 않는** 별칭들.  `builtins.open is io.open is _io.open`
#: 이지만 patch 는 모듈 속성만 바꾸므로 `sys.modules['_io'].open` 은 원본
#: 그대로다(`os.listdir` ↔ `posix.listdir` 도 같다).  심판이 `_io.open` 으로
#: 가드 안에서 실제 register 를 읽었다.  이 별칭들을 거치면 차단은 오직 감사
#: hook 이 낸 것이므로 `T-77-AUDIT` 이 그 층을 단독으로 관측할 수 있다.
_IO = sys.modules["_io"]
_POSIX = sys.modules["posix"]

#: 쓰기 프로브의 표적 — **부모가 존재하지 않는** 경로다 (v2.8, 심판 v2.7 #6).
#:
#: v2.7 의 프로브는 `_HERE` 밑의 실제 writable 경로를 `w` 로 열고 디렉터리를
#: 만들었다.  가드가 깨지는 **바로 그 음성 시나리오**에서 실물이 생성됐고
#: 정리되지 않아 후속 실행이 영구 오염됐다 (실측: 직전 라운드 감사가 그
#: 함정에 빠져 24 건을 위양성으로 만들었다).  감사 이벤트는 파일이 만들어지기
#: **전에** 발화하므로 가드가 살아 있으면 여기서도 똑같이 차단되고, 가드가
#: 죽으면 부모 부재로 `OSError` 가 나 — **어느 경우에도 실물이 생기지 않는다.**
#: 이 디렉터리는 만들지 않는다.  관측 대상은 "hook 이 발화하는가"이지
#: "쓰기가 성공하는가"가 아니다.
_WRITE_PROBE_ROOT = _HERE / "__absent_probe_root"

#: L2 — 이 어휘를 쓴 한계 노트는 등재된 갭이나 red Case 에 결속돼야 한다.
#:
#: **이 목록은 폐쇄가 아니다.**  심판이 v2.3 에서 목록 밖 서술로 우회했고,
#: 그 지적은 옳다.  L2 는 "green Case 에 결함 주장을 주차하는" **특정 패턴**만
#: 거부하며, 목록 밖 서술은 L1(등재 강제)이 잡는다.  목록을 늘려 폐쇄를
#: 주장하지 않는다 — 그것이 v2.3 이 진 게임이다.
DEFECT_WORDS: tuple[str, ...] = (
    "결함",
    "위반",
    "반증",
    "충돌",
    "우회",
    "미검출",
    "통과시킨",
)


@dataclass
class Case:
    """대조군 하나의 양방향 결과.  `ok` 가 exit status 를 결정한다."""

    tid: str
    name: str
    clean_green: bool
    mutant_red: bool
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.clean_green and self.mutant_red


@dataclass
class Defect:
    """관측된 계약 위반.  같은 tid 의 red Case 로 결속돼야 한다."""

    tid: str
    text: str


@dataclass
class Limit:
    """한계·범위 노트.  `lid` 는 설정에 등재된 안정 식별자다."""

    lid: str
    text: str
    case: str | None = None
    unchk: str | None = None


@dataclass
class Report:
    cases: list[Case] = field(default_factory=list)
    defects: list[Defect] = field(default_factory=list)
    limits: list[Limit] = field(default_factory=list)
    #: SELF-1 이 계산한 앵커 대조 결과.  **detail 이 아니라 여기 담는다** —
    #: detail 에 넣으면 Case 산문 앵커가 자기참조가 되어 SELF-1 을 덮지 못한다.
    anchors: dict[str, str] = field(default_factory=dict)

    def add(self, case: Case) -> Case:
        self.cases.append(case)
        return case

    def defect(self, tid: str, text: str) -> None:
        """계약 위반 관측을 등재한다.  Case 결속은 SELF-1 이 강제한다."""
        self.defects.append(Defect(tid, text))

    def limit(
        self,
        lid: str,
        text: str,
        *,
        case: str | None = None,
        unchk: str | None = None,
    ) -> None:
        """한계·범위 서술.  `lid` 등재는 SELF-1 L1 이 강제한다."""
        self.limits.append(Limit(lid, text, case, unchk))

    # --- 발견 결속 (기존) --------------------------------------------------
    def case_index(self) -> dict[str, Case]:
        return {case.tid: case for case in self.cases}

    def unbound_defects(self) -> list[Defect]:
        """발견 목록에 있는데 Case 에 없는 항목."""
        known = self.case_index()
        return [d for d in self.defects if d.tid not in known]

    def green_bound_defects(self) -> list[Defect]:
        """Case 는 있는데 그 Case 가 green 인 항목 — 결함이 통과한 것이다."""
        known = self.case_index()
        return [d for d in self.defects if d.tid in known and known[d.tid].ok]

    # --- L1 등재 강제 (v2.5) ----------------------------------------------
    def undeclared_limits(self, declared: Sequence[str]) -> list[str]:
        """설정에 등재되지 않은 노트 — **주입된 노트가 여기서 잡힌다.**"""
        allowed = set(declared)
        return [limit.lid for limit in self.limits if limit.lid not in allowed]

    def missing_limits(self, declared: Sequence[str]) -> list[str]:
        """등재됐는데 방출되지 않은 노트 — 삭제도 diff 를 요구한다."""
        emitted = {limit.lid for limit in self.limits}
        return [lid for lid in declared if lid not in emitted]

    def duplicate_limits(self) -> list[str]:
        """같은 `lid` 재사용 — 등재 1 건 뒤에 여러 노트를 숨기는 통로."""
        seen: set[str] = set()
        duplicates: list[str] = []
        for limit in self.limits:
            if limit.lid in seen:
                duplicates.append(limit.lid)
            seen.add(limit.lid)
        return duplicates

    def unresolved_limit_refs(self, unchk_ids: Sequence[str]) -> list[str]:
        """`case=` / `unchk=` 가 실재하지 않는 대상을 가리키는 노트."""
        known = self.case_index()
        registered = set(unchk_ids)
        bad: list[str] = []
        for limit in self.limits:
            if limit.case is not None and limit.case not in known:
                bad.append(f"{limit.lid}: case={limit.case} 부재")
            if limit.unchk is not None and limit.unchk not in registered:
                bad.append(f"{limit.lid}: unchk={limit.unchk} 미등재")
        return bad

    # --- L2 주차 거부 (v2.5) ----------------------------------------------
    def parked_limits(
        self, unchk_ids: Sequence[str], waivers: Sequence[str]
    ) -> list[str]:
        """결함 어휘를 쓰면서 **green Case 에 주차**한 노트.

        v2.3 의 비대칭 — 발견 경로만 red 를 검사하고 한계 경로는 존재만 봤다 —
        을 여기서 없앤다.  정당한 경로는 셋뿐이며 **전부 등재 표면**이다:
        등재된 갭(`unchk=`) · red Case(`case=`) · 설정에 적힌 면제(`waivers`).
        """
        known = self.case_index()
        registered = set(unchk_ids)
        waived = set(waivers)
        parked: list[str] = []
        for limit in self.limits:
            if not any(word in limit.text for word in DEFECT_WORDS):
                continue
            if limit.lid in waived:
                continue
            if limit.unchk is not None and limit.unchk in registered:
                continue
            bound = known.get(limit.case) if limit.case is not None else None
            if bound is not None and not bound.ok:
                continue
            parked.append(limit.lid)
        return parked


def limit_text_anchor(source: str) -> tuple[str, dict[str, str]]:
    """한계 노트 **본문**의 앵커 — id 집합만으로는 부족하다 (v2.5 2차 교정).

    1 차 교정은 `lid` 집합만 설정에 묶었다.  그래서 **이미 등재된 노트의 본문을
    고쳐** 발견을 흘리면 설정 변경 0 으로 통과했다 — "설정을 고쳐야 하므로
    diff 에 남는다"는 주장이 거짓이었다(심판 stop-time 지적).

    여기서는 러너 자기 소스를 파싱해 각 `limit()` 호출의 **문자열 리터럴 조각**만
    모아 digest 한다.  런타임 값(f-string 삽입부)은 제외되므로 앵커가 흔들리지
    않고, **문자열 리터럴 조각이 바뀌면 digest 가 바뀐다.**

    **주장 축소 (v2.10, 심판 9 회차 #3).**  직전 판은 여기에 "산문을 고치면
    digest 가 바뀐다" 고 적었는데 **전칭이 거짓**이다.  바로 위 문장이 밝힌 대로
    이 digest 의 정의역은 리터럴 조각뿐이므로, f-string **삽입 표현이나 삽입값만**
    고치면 방출 산문은 달라져도 리터럴 조각은 불변이고 이 값은 움직이지 않는다.
    삽입부는 이 앵커의 정의역이 아니라 **방출 앵커(`emitted_text_anchor`)의
    투영**이 덮는다 — 두 앵커를 합쳐야 노트 산문 전체가 고정된다.
    """
    tree = ast.parse(source)
    per_note: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "limit"):
            continue
        if not node.args:
            continue
        head = node.args[0]
        if not (isinstance(head, ast.Constant) and isinstance(head.value, str)):
            continue
        parts: list[str] = []
        for arg in node.args[1:]:
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    parts.append(sub.value)
        digest = hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()[:12]
        per_note[head.value] = digest
    joined = "|".join(f"{lid}={digest}" for lid, digest in sorted(per_note.items()))
    combined = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
    return combined, per_note


def emitted_text_anchor(limits: Sequence[Limit]) -> str:
    """**방출된** 노트 본문의 앵커 (v2.5 3차 교정).

    2 차 교정은 소스의 **리터럴 조각**만 digest 했다.  그래서 산문을 f-string
    **삽입부**로 흘리면 리터럴이 그대로여서 통과했다 — 이 러너의 노트는 이미
    전부 삽입부를 쓰므로 통로가 열려 있었다(심판 stop-time 2 차 지적).

    여기서는 최종 방출 문자열 자체를 묶는다.  삽입값은 고정 픽스처에서
    결정적이므로 앵커는 흔들리지 않는다.

    **주장 축소 (v2.11 — 심판 9 회차 #1 의 구분자 접힘 클래스를 ⒝ 에 귀속).**
    직전 판은 여기에 "값이 실제로 바뀌면 red 가 되어 재검토를 강제한다" 고
    적었는데 **그 전칭은 거짓이다.**  이 앵커가 관측하는 것은 아래 `joined` —
    즉 **이어붙인 문자열(따라서 그 digest)이 바뀌는** 변경뿐이다.  레코드 안의
    네 항은 태그도 길이도 없이 `\\x1f` 로, 레코드 사이는 `\\x00` 으로만 이어지므로
    **항 목록이 달라도 이어붙인 결과가 같으면 digest 는 불변이다.**
    **보장 밖**: 구분자(`\\x1f`/`\\x00`)가 값 안에 들어가 항 경계가 사라져 같은
    직렬화로 접히는 변경.  실측 — 접힘의 최소 사례는 `('a\\x1fb',)` 와
    `('a','b')` 가 둘 다 `a\\x1fb` 로 접히는 것이고, 이 앵커에서는
    `Limit("L1", "x\\x1fy")` 와 `Limit("L1\\x1fx", "y")` 가 둘 다
    `L1\\x1fx\\x1fy\\x1f\\x1f` 로 접혀 digest 가 같다(`8ec383d8d23dde51`).
    `\\x00` 쪽도 같아서 두 노트를 한 노트로 접을 수 있다.  ⒞
    `case_prose_anchor` 와 **같은 클래스**이며 등재는 `L-SRC-ANCHOR` 이다.
    """
    joined = "\x00".join(
        "\x1f".join((limit.lid, limit.text, limit.case or "", limit.unchk or ""))
        for limit in sorted(limits, key=lambda item: (item.lid, item.text))
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _code_prose(code: object, out: list[str]) -> None:
    """코드 객체가 **실제로 들고 있는** 것을 펼친다 — 이름·상수·바이트코드.

    v2.6: `co_code` 와 `co_names` 를 추가한다 (심판 F1 권고).  이름과 문자열
    상수만 묶으면 **조건식 제거가 침묵한다** — `if x and y:` 에서 `and y` 를
    떼도 상수·이름 집합은 그대로일 수 있기 때문이다.  바이트코드는 그 편집을
    직접 관측한다.  대가: 앵커가 CPython 버전에 묶인다 — 동결 계약 아티팩트의
    앵커이므로 의도된 대가이며 `L-SRC-ANCHOR` 로 등재한다.
    """
    consts = getattr(code, "co_consts", ())
    out.append(str(getattr(code, "co_name", "")))
    out.append(getattr(code, "co_code", b"").hex())
    out.extend(getattr(code, "co_names", ()))
    for const in consts:
        if isinstance(const, str):
            out.append(const)
        elif hasattr(const, "co_consts"):
            _code_prose(const, out)


def _module_class_names(module: object) -> frozenset[str]:
    """모듈이 **자기 소스에서 정의한** 최상위 클래스 이름 — 구조 파생이다.

    `type.__module__` 도 객체가 스스로 적는 값이므로 정의역 판정의 근거가 될
    수 없다.  여기서는 그 모듈 **파일의 AST** 에서 이름을 뽑는다 — 목록을
    좁히려면 디스크 편집이 필요하고 그것은 소스 바이트 앵커가 본다.
    """
    path = getattr(module, "__file__", None)
    if path is None:
        return frozenset()
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    return frozenset(node.name for node in tree.body if isinstance(node, ast.ClassDef))


def _module_code_parts(label: str, module: object) -> list[str]:
    """모듈 네임스페이스에서 `__code__` 를 **직접 가진** 멤버를 모은다.

    "전수" 가 아니다 (v2.9 후속 정정).  판정은 `getattr(obj, "__code__")` 하나이므로
    `property`·`staticmethod`·`classmethod` 처럼 **descriptor 로 감싼** 멤버는
    정의역 밖이다 — 그 6 건과 그중 `Case.ok` 가 갖는 무게는 `L-SRC-ANCHOR` 이
    등재한다.

    `label` 은 **고정 이름**이다.  런타임 `__name__` 을 쓰면 스크립트 실행
    (`__main__`)과 import 실행에서 digest 가 갈린다 — 앵커가 호출 방식에
    의존하면 앵커가 아니다.

    **v2.8 — `__module__` 자기신고를 정의역에서 제거했다** (심판 v2.7 #2 high).
    제거한 것은 그 속성 **하나뿐**이고 파일 라벨은 남아 있다 (v2.10 철회).  v2.7 은
    `getattr(obj, "__module__", None) != name` 으로 소속을 판정했다.
    `__module__` 은 **함수 객체가 스스로 적는 속성**이라, 러너가 import 로
    바인딩한 `load_config` 를 `__module__='proto.config'` 인 함수로 갈아끼우면
    교체본이 러너 부분집합에서 빠지고 원본 모듈 쪽 부분집합은 그대로여서
    **어느 앵커도 그 교체를 보지 못했다** — 앵커 기대값 전체를 라이브로 위조할
    수 있는 지렛대였다.  v2.8 은 두 가지를 바꾼다:

      - `__code__` 를 가진 객체는 **소속과 무관하게 전부** 묶고, 그 코드가
        내놓는 **파일 라벨**(`basename(co_filename)`)을 함께 적는다 (stdlib
        헬퍼도 그대로 들어온다).  그 라벨은 컴파일 시 제공되는 값이라 위조
        가능하며 검증된 provenance 가 아니다 (v2.10 철회) — 결속의 무게는
        함께 묶이는 코드 투영이 진다.
      - 클래스의 정의역은 그 모듈 **소스의 최상위 `ClassDef` 이름**으로 정한다.
        이름이 목록에 있는데 객체가 클래스가 아니게 되면 그 사실이 기록된다.
    """
    parts: list[str] = [f"\x00module:{label}"]
    class_names = _module_class_names(module)
    for attr in sorted(dir(module)):
        obj = getattr(module, attr, None)
        code = getattr(obj, "__code__", None)
        if code is not None:
            parts.append(f"\x01{attr}@{os.path.basename(code.co_filename)}")
            _code_prose(code, parts)
            continue
        if attr not in class_names:
            continue
        parts.append(f"\x01{attr}:{type(obj).__name__}")
        for member in sorted(vars(obj)) if isinstance(obj, type) else ():
            sub = getattr(vars(obj)[member], "__code__", None)
            if sub is not None:
                parts.append(f"\x01{attr}.{member}@{os.path.basename(sub.co_filename)}")
                _code_prose(sub, parts)
    return parts


def _code_digest(code: object) -> str:
    """코드 객체 하나의 digest — 바인딩 결속의 재료다."""
    parts: list[str] = []
    _code_prose(code, parts)
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def binding_file(obj: object) -> str:
    """바인딩된 객체가 내놓는 **파일 라벨** — `basename(co_filename)` 또는
    `basename(__file__)` 이다.

    **주장 철회 (v2.10, 심판 9 회차 #2).**  직전 판은 이것을 "코드가 실제로 온
    파일 이름 — 자기신고가 아니다" 라고 적었는데 **구현보다 넓었다**.  참인 것은
    `__module__` 과의 대비뿐이다: 그 속성은 객체가 스스로 적는 값이라 교체본이
    임의로 적을 수 있다.  그러나 여기서 읽는 두 값도 **검증된 provenance 가
    아니다** — 함수 분기의 `co_filename` 은 컴파일 시점에 **제공되는 라벨**이라
    `compile(src, "임의이름.py", ...)` 이 그대로 실어 보내고, 모듈 분기의
    `__file__` 은 라이브 객체의 **가변 속성**이라 대입 한 줄로 바뀐다.  따라서
    관측값은 그 메타데이터 라벨일 뿐이고, 결속의 무게는 함께 묶이는 코드
    digest 가 진다.  보장 밖은 `L-SRC-ANCHOR` 가 등재한다.
    """
    code = getattr(obj, "__code__", None)
    if code is not None:
        return os.path.basename(code.co_filename)
    path = getattr(obj, "__file__", None)
    return os.path.basename(path) if path is not None else ""


def _binding_origin(obj: object) -> str:
    """바인딩을 **파일 라벨 + 코드 digest** 로 적는다 — 라벨은 보장 밖이다."""
    code = getattr(obj, "__code__", None)
    if code is not None:
        return f"함수\x02{binding_file(obj)}\x02{_code_digest(code)}"
    if getattr(obj, "__file__", None) is not None:
        digest = hashlib.sha256(
            "\x1f".join(_module_code_parts("bound", obj)).encode("utf-8")
        ).hexdigest()[:16]
        return f"모듈\x02{binding_file(obj)}\x02{digest}"
    return f"기타\x02{type(obj).__name__}"


#: 러너가 결속해야 하는 import 뿌리.  이름 목록 자체는 소스 AST 에서 파생한다.
ANCHOR_IMPORT_ROOTS: frozenset[str] = frozenset({"proto", "audit_guard"})


def module_binding_identities(source: str) -> tuple[str, ...]:
    """러너가 import 로 바인딩한 이름을 **이름·파일 라벨·코드 digest** 로 묶는다.

    이름 목록은 손으로 쓰지 않는다 — 러너 **소스의 AST** 에서 파생하므로
    목록을 줄이려면 디스크 편집이 필요하다.  이 값은
    값 앵커(`anchor_policy_values`)의 대상이므로, **그 세 축 중 하나라도**
    갈리면 실행코드 앵커와 **독립으로** 한 번 더 red 가 된다 (심판 v2.7 #2).

    **주장 철회 (v2.10, 심판 9 회차 #2).**  직전 판은 두 번째 축을 "자기신고
    (`__module__`)가 아니라 **코드가 실제로 온 파일**" 이라고 적었는데
    **구현보다 넓었다**.  v2.8 이 정의역에서 없앤 것은 `__module__` 이지 **파일
    라벨이 아니다.**  여기서 읽는 값은 `binding_file()` 이 내놓는
    `basename(co_filename)`(함수) 또는 `basename(__file__)`(모듈)이라는
    **메타데이터 라벨**이다 — 전자는 컴파일 시 제공되는 값, 후자는 라이브 모듈
    객체의 가변 속성이라 어느 쪽도 검증된 provenance 가 아니고 둘 다 위조
    가능하다.  실제 `module_binding_identities()` 가 파생하는 이름은 현재 전부
    모듈 객체이므로 **가변 `__file__` 쪽 분기만 탄다.**

    관측되는 것은 세 축의 투영뿐이다 — **보장 밖**: ⑴ 같은 `__code__` 와 같은
    파일 라벨을 쓰되 globals·defaults·closure 만 다른 함수 객체로의 교체는 세
    축이 전부 불변이라 여기서도 침묵하고, ⑵ 같은 코드 투영을 유지한 채 **파일
    라벨만 위조한** 모듈·함수 교체도 세 축이 보존되므로 identity 가 그대로다.
    설명상 거부되는 것처럼 보였던 두 번째 경우가 실제로는 통과한다
    (`L-SRC-ANCHOR` 등재).
    """
    tree = ast.parse(source)
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if str(node.module or "").split(".")[0] in ANCHOR_IMPORT_ROOTS:
                names.extend(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.extend(
                alias.asname or alias.name
                for alias in node.names
                if alias.name.split(".")[0] in ANCHOR_IMPORT_ROOTS
            )
    runner = sys.modules[__name__]
    return tuple(
        f"{name}\x02{_binding_origin(getattr(runner, name, None))}"
        for name in sorted(set(names))
    )


def independent_settings(path: Path) -> dict[str, str]:
    """**파싱 코드가** 독립인 두 번째 설정 판독기 (v2.8, 심판 #2).

    앵커의 기대값은 전부 설정에서 온다.  그 판독 경로가 함수 하나뿐이면 그
    함수를 갈아끼우는 것만으로 기대값 전체를 라이브로 위조할 수 있다 —
    심판이 지목한 정확한 지렛대다.  여기서는 러너가 자기 코드로 같은 파일을
    한 번 더 읽어 **키·값을 그대로** 비교한다.

    **v2.9 정정 (심판 v2.8 #1).**  v2.8 은 여기에 "비용을 1 지점에서 2 지점으로
    올릴 뿐" 이라고 적었다.  실측 **1 지점**이므로 거짓이었다.  독립인 것은
    파싱 코드뿐이고 **경로 신뢰점은 하나다** — 호출자가 넘기는 `path` 는 주
    판독기와 같은 `config.CONFIG_PATH` 에서 오며, 그 이름을 한 번 재바인딩하면
    두 판독기가 동시에 같은 파일을 읽는다.  `CONFIG_PATH` 자체는 값 앵커의
    정의역 밖(잔여)이라 그 재바인딩은 관측되지 않는다.  등재는
    `L-CONFIG-TRUSTPOINT`, 종단 한계는 `L-EXIT-ROOT` 다.
    """
    settings: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped or ":" not in stripped:
            continue
        key, raw = stripped.split(":", 1)
        settings[key.strip()] = raw.strip()
    return settings


def loaded_code_text(modules: Sequence[object]) -> str:
    """앵커 대상 = **실행 중인 코드**.  디스크 파일이 아니다 (v2.5 5 차 교정).

    4 차 교정은 `Path(__file__).read_text()` 로 **디스크 파일**을 해시했다.
    실행되는 것은 `sys.modules` 에 로드된 코드 객체이므로, 런타임에 함수를
    갈아끼우면 디스크는 그대로여서 digest 가 맞고 우회가 성립했다
    (심판 stop-time 4 차 지적).  여기서는 로드된 코드 객체의 이름과 문자열
    상수를 직접 펼쳐 묶는다 — 산문은 `co_consts` 에 들어 있다.

    **투영이 아니라 이 직렬화가 앵커의 정의역이다 (v2.10, 심판 9 회차 #1).**
    `_module_code_parts` 가 모은 항은 여기서 태그도 길이도 없이 `"\\x1f".join`
    으로만 이어진다.  그래서 **수집 항 목록이 달라도 이어붙인 결과가 같으면
    digest 는 불변이다** — 구분자가 값 안에 들어 있으면 항 경계가 사라지기
    때문이다.  실측: `("a\\x1fb",)` 와 `("a","b")` 는 항 목록이 서로 다른데
    직렬화는 둘 다 `a\\x1fb` 로 접힌다.  따라서 실행 코드 앵커의 보장은
    "수집된 투영이 바뀌면" 이 아니라 **"이 함수가 내는 문자열(따라서 그
    digest)이 바뀌면"** 으로만 적어야 종결적이다 (`L-SRC-ANCHOR` 등재).

    `*.yaml` 은 앵커 값 자체를 담고 있어 대상이 아니다(자기참조).
    """
    parts: list[str] = []
    for label, module in modules:
        parts.extend(_module_code_parts(label, module))
    return "\x1f".join(parts)


def anchor_source_paths() -> tuple[Path, ...]:
    """소스 바이트 앵커의 대상 파일 — **스캔 대상 전 파일**.

    러너 + `audit_guard.py` + `proto/*.py` (**`__init__.py` 포함**).
    `config.yaml` 은 앵커 값 자체를 담으므로 제외한다(자기참조).
    """
    return (
        Path(__file__).resolve(),
        Path(audit_guard.__file__).resolve(),
        *sorted((_HERE / "proto").glob("*.py")),
    )


def source_bytes_anchor(paths: Sequence[Path]) -> str:
    """**소스 바이트** 앵커 (v2.6, 심판 F1 신규 결함).

    실행 코드 앵커(⒟)는 `__code__` 를 가진 객체만 순회한다.  그래서 모듈 레벨
    tuple/frozenset/dict·문장·docstring·주석은 정의역 **밖**이었고, 심판이
    `FORBIDDEN_ARTIFACTS` 5→1 과 `REQUIRED_METRICS` 4→2 를 앵커 4 종 불변으로
    통과시켰다.  `proto/__init__.py` 는 코드 객체가 하나도 없어 아예 대상이
    아니었는데 설정 주석은 "proto 7 개"라고 적고 있었다.

    여기서는 대상 파일의 **정확한 바이트**를 묶는다.  파일 이름도 함께 묶으므로
    목록에서 파일을 빼는 것 자체가 값을 바꾼다.
    """
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x1f")
    return digest.hexdigest()[:16]


def tuple_anchor(values: Sequence[str]) -> str:
    """모듈 레벨 **정책 값** 자체의 앵커 (v2.6).

    소스 바이트 앵커는 디스크 편집을 잡지만 **런타임 대입**은 잡지 못한다.
    이 앵커는 로드된 값에서 직접 파생하므로 인메모리 대입도 관측한다 — 다만
    관측되는 것은 NUL 로 이은 **항목 텍스트가 바뀌는** 대입뿐이다.  실제 값에
    대해 항목별 삭제가 전부 그 텍스트를 움직이는지는 `T-77-③` 이 전수
    확인하며, 컨테이너 타입만 tuple↔list 로 바꾸는 교체는 같은 텍스트로
    접히므로 **보장 밖**이다.
    """
    return hashlib.sha256("\x00".join(values).encode("utf-8")).hexdigest()[:16]


# --- ⒡ 런타임 정책값 앵커 (v2.7, 심판 #7 medium) -----------------------------


def policy_value_text(value: object) -> str:
    """정책 값을 **순서 안정적인** 텍스트로 펼친다 — digest 의 입력이다.

    **이 평탄화가 만드는 정규화 동치 (v2.10, 심판 9 회차 #1).**  컨테이너는
    타입 태그도 길이도 없이 NUL(`\\x00`) 하나로만 이어지고 중첩도 같은 구분자로
    평탄해진다.  그래서 등재된 tuple↔list · set↔frozenset 접힘 **밖에서도**
    항목 수·항목 경계·중첩 구조가 다른 값이 같은 문자열로 접힌다 — 실측:
    `policy_value_text(("a","b"))` 와 `policy_value_text(("a\\x00b",))` 가
    둘 다 `a\\x00b` 다.  값 앵커의 보장을 "값이 바뀌면" 으로 적으면 그 전칭이
    거짓이므로, 보장은 **`policy_digest` 가 바뀌는 경우**로만 적는다
    (`L-POLICY-ANCHOR` 등재).
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (tuple, list)):
        return "\x00".join(policy_value_text(item) for item in value)
    if isinstance(value, (frozenset, set)):
        return "\x00".join(sorted(policy_value_text(item) for item in value))
    if isinstance(value, Mapping):
        return "\x00".join(
            f"{key!r}\x02{policy_value_text(sub)}"
            for key, sub in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    return repr(value)


def policy_digest(value: object) -> str:
    return hashlib.sha256(policy_value_text(value).encode("utf-8")).hexdigest()[:16]


def anchor_modules() -> tuple[tuple[str, object], ...]:
    """앵커 대상 모듈과 그 **고정 라벨** — 실행코드 앵커와 값 census 의 공통 정의역.

    두 곳에서 따로 적으면 그 사본이 곧 다음 간극이다.  라벨을 고정하는 이유는
    `_module_code_parts` 의 docstring 에 적었다.
    """
    return (
        ("runner", sys.modules[__name__]),
        ("audit_guard", audit_guard),
        ("boundary", boundary),
        ("config", config),
        ("enforcement", enforcement),
        ("floor", floor),
        ("gates", gates),
        ("register", register),
    )


#: 값 앵커 census 의 **정의역 타입**.  이 타입이면 정책값 후보로 자동 편입된다.
#: bool/int/float 은 값이 아니라 상태·수치 임계이므로 제외하고, 그 제외분은
#: census 가 **잔여로 자동 열거**한다 — 손으로 적는 잔여 목록은 쓰지 않는다.
#: 다만 열거되는 것은 census 가 **이름 등록까지 도달한** 항목뿐이다: 호출
#: 가능 객체와 모듈은 그 앞에서 걸러지므로 잔여에도 나타나지 않는다 (v2.9).
POLICY_VALUE_TYPES: tuple[type, ...] = (str, bytes, tuple, frozenset, set, list, dict)

#: 컨테이너 원소로 허용되는 타입.  이보다 복잡한 원소가 있으면 digest 가
#: 재현되지 않을 수 있으므로 후보에서 빼고 잔여로 보낸다 (fail-closed).
POLICY_ELEMENT_TYPES: tuple[type, ...] = (
    str,
    bytes,
    int,
    float,
    bool,
    type,
    type(None),
    tuple,
    frozenset,
    set,
)


def _is_policy_value(value: object) -> bool:
    """모듈 레벨 **정책값**인가 — 타입 구조로 판정한다 (양성 목록이 아니다)."""
    if isinstance(value, (bool, int, float)):
        return False
    if not isinstance(value, POLICY_VALUE_TYPES):
        return False
    if isinstance(value, (str, bytes)):
        return True
    items = (
        list(value.values()) + list(value) if isinstance(value, dict) else list(value)
    )
    return all(isinstance(item, POLICY_ELEMENT_TYPES) for item in items)


def policy_value_census(excluded: Sequence[str]) -> dict[str, object]:
    """모듈 **구조에서** 정책값을 파생한다 — 수동 양성 목록을 쓰지 않는다 (v2.8).

    v2.7 의 `policy_value_targets()` 는 손으로 쓴 25 개 목록이었다.  손 목록은
    **신규 항목을 영원히 못 찾는다**: `_NULLARY_STR_METHODS` 가 `_const_call()`
    에서 판정에 쓰이는데 표에도, 한계 노트의 "표 밖" 열거에도 없었다 (심판
    v2.7 #5 — 하드코딩 census 의 알려진 결함 클래스).

    v2.8 은 대상 모듈의 모듈 레벨 이름을 훑어 자동으로 3 분류한다:
      - `targets`  : 정의역 타입에 드는 값 — 설정 앵커 등재를 요구한다
      - `excluded` : 설정 `policy_value_exclusions` 에 적힌 **의도적 제외**
      - `residual` : 정의역 타입 **밖** 이름 — 손이 아니라 census 가 열거한다
    선언만 있고 실물이 없는 제외(`phantom`)도 fail-closed 로 보고한다.

    **정의역 (v2.9 정정, 심판 v2.8 #4)**: 아래 `callable(value)`/모듈 스킵은
    **이름 등록보다 앞에** 있다.  그래서 클래스는 `targets` 뿐 아니라
    `residual`·`phantom` 에서도 사라진다 — 실측 52 개 모듈 레벨 클래스 중
    어느 하나도 세 분류에 나타나지 않는다.  그 결과 클래스 **속성**에 놓인
    정책 상수는 이 census 밖이고, 실행코드 앵커도 클래스 멤버 중 `__code__` 가
    있는 것만 묶으므로 속성 **값**은 보지 않는다.  "새 상수가 생기면 자동으로
    red" 는 **모듈 레벨 비호출 이름에 한해** 참이다.  `L-POLICY-ANCHOR` 참조.
    """
    waived = set(excluded)
    seen: set[str] = set()
    targets: dict[str, object] = {}
    skipped: list[str] = []
    residual: list[str] = []
    for label, module in anchor_modules():
        for attr in sorted(vars(module)):
            if attr.startswith("__") and attr.endswith("__"):
                continue
            value = vars(module)[attr]
            # 코드와 모듈은 **실행코드 앵커**의 정의역이다 (이중 결속 불필요).
            # **클래스도 여기서 걸린다** (v2.9 정정, 심판 v2.8 #4): 실행코드
            # 앵커는 클래스 멤버 중 `__code__` 가 있는 것만 묶으므로 클래스
            # **속성값**은 어느 쪽에도 들어가지 않는다.  이 스킵이 이름 등록보다
            # 앞이라 클래스는 잔여 열거에서도 사라진다.
            if callable(value) or isinstance(value, type(sys)):
                continue
            name = f"{label}.{attr}"
            seen.add(name)
            if name in waived:
                skipped.append(name)
            elif _is_policy_value(value):
                targets[name] = value
            else:
                residual.append(f"{name}({type(value).__name__})")
    return {
        "targets": targets,
        "excluded": tuple(skipped),
        "residual": tuple(residual),
        "phantom": tuple(sorted(waived - seen)),
    }


def synthetic_policy_targets() -> dict[str, object]:
    """구조 파생만으로는 결속되지 않아 **정규화해서** 묶는 값.

    - `audit_guard.SAFE_PATH_TYPES` — 타입 객체 집합을 이름으로 정규화한다.
    - `runner.MODULE_BINDINGS` — 러너가 import 로 바인딩한 이름의 identity
      (이름·**파일 라벨**·코드 digest).  `__module__` 자기신고를 쓰지 않는
      결속이다 (심판 #2) — 다만 **파일 라벨 자체는 보장 밖**이고 (v2.10 철회,
      심판 9 회차 #2) 그 한계는 `module_binding_identities()` 가 적는다.
    """
    return {
        "audit_guard.SAFE_PATH_TYPES": audit_guard.safe_path_types(),
        "runner.MODULE_BINDINGS": module_binding_identities(
            Path(__file__).read_text(encoding="utf-8")
        ),
    }


def policy_value_targets(excluded: Sequence[str]) -> dict[str, object]:
    """값 앵커의 정의역 = **자동 census** + 정규화 대상.

    값은 **호출 시점에 라이브 모듈에서** 읽는다 — 그래서 디스크를 건드리지
    않는 런타임 대입도 digest 를 움직일 수 있다.  다만 앵커가 관측하는 것은
    **target 이름 집합 또는 `policy_digest` 가 바뀌는** 대입뿐이다 — 어떤
    뮤테이션 부류를 잡는지가 아니라 **자기 투영이 무엇인지**로만 적는다.
    **보장 밖**: 정규화상 동치인 컨테이너 타입 교체 — `policy_value_text` 가
    tuple 과 list 를, set 과 frozenset 을 각각 같은 문자열로 접고
    `POLICY_VALUE_TYPES` 는 네 타입을 다 받으므로, census 안에서의 그 타입
    교체는 이름과 digest 를 **둘 다 보존한다**.  **그 목록은 닫혀 있지 않다**
    (v2.10, 심판 9 회차 #1): `policy_value_text` 가 타입 태그·길이 없이 NUL
    하나로 이어 붙이고 중첩을 평탄화하므로 **항목 수·항목 경계·중첩 구조가
    다른 값도** 같은 문자열로 접힌다 — 예: `("a","b")` 와 `("a\\x00b",)`.
    그래서 여기의 보장은 값이 아니라 **`policy_digest`** 로만 적는다
    (`L-POLICY-ANCHOR` 등재).
    """
    targets = dict(policy_value_census(excluded)["targets"])
    targets.update(synthetic_policy_targets())
    return targets


def policy_value_variants(value: object) -> list[tuple[str, object]]:
    """**항목별** 삭제·확장 변형.  각 변형의 digest 가 달라져야 결속이 성립한다."""
    sentinel = ""
    if isinstance(value, str):
        variants: list[tuple[str, object]] = [("확장", value + sentinel)]
        if value:
            variants.append(("절단", value[:-1]))
        return variants
    if isinstance(value, tuple):
        return [
            ("확장", value + (sentinel,)),
            *(
                (f"삭제[{index}]", value[:index] + value[index + 1 :])
                for index in range(len(value))
            ),
        ]
    if isinstance(value, (frozenset, set)):
        base = frozenset(value)
        return [
            ("확장", base | {sentinel}),
            *((f"삭제[{item}]", base - {item}) for item in sorted(base, key=str)),
        ]
    if isinstance(value, Mapping):
        return [
            ("확장", {**value, sentinel: sentinel}),
            *(
                (
                    f"삭제[{key}]",
                    {k: v for k, v in value.items() if k != key},
                )
                for key in sorted(value, key=str)
            ),
        ]
    return []


# --- pre-hook 구간 분석 (v2.7, 심판 #3 high) ---------------------------------

#: pre-hook 구간에 나타나면 **그 자체로** findings 다.  정적 import 문만 보던
#: v2.6 의 순서 검사는 `__import__`·`importlib`·`exec` 로 먼저 로드하는 경로를
#: 전혀 보지 못했다.  이름은 `Name.id` 와 `Attribute.attr` 양쪽에서 찾는다.
#: 동적 로드에 더해 **I/O 진입점**도 넣는다 — hook 이 서기 전의 열람·쓰기는
#: 어느 층도 보지 못하기 때문이다.  이 집합 자체는 값 앵커에 결속돼 있다.
#:
#: **이것은 닫힌 목록이다** (v2.9 정정, 심판 v2.8 #3).  여기 적힌 이름만 찾으므로
#: `_io.FileIO`·`readall` 처럼 목록 밖의 진입점은 검사가 비어 있다.  "hook 이
#: 서기 전의 I/O 를 잡는다" 가 아니라 "적어 둔 이름을 잡는다" 가 실제 정의역이다.
PREHOOK_FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        # 동적 로드·실행
        "__import__",
        "importlib",
        "import_module",
        "exec",
        "eval",
        "compile",
        "runpy",
        "run_module",
        "run_path",
        "SourceFileLoader",
        "exec_module",
        "load_module",
        "__loader__",
        "system",
        "popen",
        "subprocess",
        "spawnv",
        "execv",
        # I/O 진입점
        "open",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "listdir",
        "scandir",
        "iterdir",
        "glob",
        "rglob",
        "walk",
        "fdopen",
        "mkdir",
        "makedirs",
        "remove",
        "unlink",
    }
)

#: 문장 **종류**만으로 비실행이라 볼 수 있는 것.  대입은 여기 있지만 그
#: **우변은 따로 본다** — 종류만 보던 v2.7 이 뚫린 지점이다.
_INERT_STATEMENTS = (
    ast.Import,
    ast.ImportFrom,
    ast.Assign,
    ast.AnnAssign,
    ast.FunctionDef,
    ast.ClassDef,
)

#: 평가되면 **코드가 도는** 노드.  대입 우변·데코레이터·기본 인자에 이것이
#: 있으면 그 문장은 실행문이다 (v2.8, 심판 v2.7 #4 high).
#:
#: v2.7 은 `ast.Assign`/`ast.AnnAssign` 을 **우변과 무관하게** 비실행문으로
#: 분류했다.  그래서 `_SNEAK = __builtins__['__import__']('proto.register')` 는
#: 실행문 계수에서 빠졌고, 같은 페이로드가 금지 이름 검사(`Name`/`Attribute`
#: 만 봤다)에서도 빠져 **두 층이 한 번에 침묵**했다.
_EXECUTING_NODES = (
    ast.Call,
    ast.Await,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Yield,
    ast.YieldFrom,
    ast.NamedExpr,
)


def _is_docstring(node: ast.stmt) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)


def _contains_execution(nodes: Sequence[ast.AST | None]) -> bool:
    return any(
        isinstance(sub, _EXECUTING_NODES)
        for root in nodes
        if root is not None
        for sub in ast.walk(root)
    )


def _statement_executes(node: ast.stmt) -> bool:
    """이 최상위 문장이 **코드를 돌리는가** — 우변·데코레이터·기본 인자까지 본다.

    **정의역 (v2.9 정정, 심판 v2.8 #3)**: `ClassDef` 는 데코레이터·base·keyword
    만 본다 — **`node.body` 를 걷지 않는다.**  클래스 본문은 import 시 즉시
    실행되므로 이 판정은 그만큼 좁다.  `FunctionDef` 본문을 걷지 않는 것은
    호출 전까지 실행되지 않으니 옳지만, `ClassDef` 에 같은 규약을 쓴 것은
    옳지 않다.  그 잔여는 `L-AUDIT-BOOTSTRAP` 이 등재한다.
    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = node.args
        return _contains_execution(
            [*node.decorator_list, *args.defaults, *args.kw_defaults]
        )
    if isinstance(node, ast.ClassDef):
        return _contains_execution(
            [*node.decorator_list, *node.bases, *(kw.value for kw in node.keywords)]
        )
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return _contains_execution([node.value])
    return not isinstance(node, _INERT_STATEMENTS) and not _is_docstring(node)


def _forbidden_constant(node: ast.AST | None) -> str:
    """문자열 **상수**로 적힌 금지 이름 — `d['__import__']` · `getattr(m, 'open')`.

    v2.7 의 동적 로드 검사는 `ast.Name` 과 `ast.Attribute` 만 봤다.
    `__builtins__['__import__']` 는 그 둘 중 어느 노드도 만들지 않아 검사가
    통째로 침묵했다 (심판 v2.7 #4).  판정 위치는 **호출 이름이 놓이는 자리**
    (subscript 첨자·호출 인자)로 좁힌다 — 모든 상수를 보면 `READ_EVENTS` 의
    `"open"` 같은 정상 데이터가 위양성이 된다.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value if node.value in PREHOOK_FORBIDDEN_NAMES else ""
    return ""


def is_hook_install(node: ast.stmt) -> bool:
    """`sys.addaudithook(...)` 호출문인가 — **구조**로 판정한다.

    문자열 검색으로 찾으면 모듈 docstring 안의 같은 낱말이 먼저 잡혀 구간이
    빈 채로 통과한다 (실측: 첫 구현이 정확히 그렇게 됐다).
    """
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "addaudithook"
    )


def is_audit_guard_import(node: ast.stmt) -> bool:
    """`import audit_guard` 문인가 — 구조로 판정한다."""
    return isinstance(node, ast.Import) and any(
        alias.name == "audit_guard" for alias in node.names
    )


def prehook_analysis(
    source: str, marker: Callable[[ast.stmt], bool], filename: str
) -> dict[str, object]:
    """hook 설치(또는 `import audit_guard`) **이전** 모듈 본문을 구조로 판정한다.

    v2.6 의 `order_ok` 는 `ast.Import`/`ast.ImportFrom` 의 **행번호만** 비교했다.
    그래서 ⑴ hook 이전에 실행되는 문장 ⑵ `__import__`·`importlib`·`exec` 로 하는
    동적 로드 를 둘 다 보지 못했다 (심판 #3).

    여기서는 marker 문장의 **위치**를 찾아 그 앞 구간을 통째로 본다:
      - `marker_found`  : marker 가 모듈 본문 최상위에 있는가 (없으면 fail-closed)
      - `dynamic`       : 동적 로드·실행 이름의 등장 (있으면 그 자체로 findings)
      - `executable`    : inert 가 아닌 문장의 `ast.unparse` 목록
      - `digest`        : 구간 전체의 `ast.unparse` digest — 설정에 핀으로 고정한다

    digest 를 핀으로 두는 이유: pre-hook 실행문을 **금지**하면 러너의 `sys.path`
    조정이 불가능해지고, **무조건 허용**하면 v2.6 의 구멍이 그대로다.  구간을
    통째로 고정하면 새 문장은 무엇이든 red 가 되고 그 승인은 설정 diff 로 남는다.

    **v2.8 (심판 v2.7 #4)**: `executable` 은 이제 대입의 **우변**까지 본다.
    그 결과 실행문은 0 이 아니며(러너 1 · `audit_guard.py` 11), 개수는 설정
    `anchor_prehook_executable` 에 핀으로 고정된다 — "실행문 0" 을 구조
    요구사항이라 적던 v2.7 의 서술은 분류 규약이 만든 산물이었다.

    **v2.9 (심판 v2.8 #3)**: `executable` 의 정의역은 `_statement_executes` 가
    정하며 **`ClassDef` 본문을 걷지 않는다.**  `dynamic` 의 정의역도
    `PREHOOK_FORBIDDEN_NAMES` 라는 **명명된 목록**이라 `FileIO`·`readall` 같은
    진입점은 들어 있지 않다.  따라서 이 구간에서 실제 I/O 가 일어나도 두 값이
    함께 침묵할 수 있고, 남는 층은 `digest` 와 소스 바이트 앵커 — 즉 차단이
    아니라 **고정** — 뿐이다.  `L-AUDIT-BOOTSTRAP` 참조.
    """
    tree = ast.parse(source, filename=filename)
    index = None
    for position, node in enumerate(tree.body):
        if marker(node):
            index = position
            break
    region = tree.body if index is None else tree.body[:index]
    dynamic: list[str] = []
    for node in ast.walk(ast.Module(body=list(region), type_ignores=[])):
        found = ""
        if isinstance(node, ast.Name) and node.id in PREHOOK_FORBIDDEN_NAMES:
            found = node.id
        elif isinstance(node, ast.Attribute) and node.attr in PREHOOK_FORBIDDEN_NAMES:
            found = node.attr
        elif isinstance(node, ast.Subscript):
            found = _forbidden_constant(node.slice)
        elif isinstance(node, ast.Call):
            found = next(
                (name for name in map(_forbidden_constant, node.args) if name), ""
            )
        if found:
            dynamic.append(f"{filename}:{getattr(node, 'lineno', 0)}: {found}")
    executable = [ast.unparse(node) for node in region if _statement_executes(node)]
    # docstring 은 digest 에서 뺀다 — 산문 편집이 이 앵커를 흔들면 구간 고정의
    # 신호가 잡음에 묻힌다.  산문 쪽은 소스 바이트 앵커가 이미 덮는다.
    unparsed = "\x00".join(
        ast.unparse(node) for node in region if not _is_docstring(node)
    )
    return {
        "marker_found": index is not None,
        "dynamic": sorted(dynamic),
        "executable": executable,
        "digest": hashlib.sha256(unparsed.encode("utf-8")).hexdigest()[:16],
        "statements": len(region),
    }


# --- 발견 채널 → exit 결속 (v2.7, 심판 #2 high) ------------------------------


def anchor_report_failures(anchors: Mapping[str, str]) -> list[str]:
    """앵커 드리프트를 `rep.anchors` **하나만 보고** 판정한다.

    v2.6 은 드리프트가 `collect_self_checks()` 의 `digest_drift` **단일 항**을
    통해서만 exit 에 닿았다 — 그 항을 무력화하면 앵커 불일치가 출력에만 남았다
    (심판 #1).  이 producer 는 그 항과 **독립**이며 `main()` 이 직접 소비한다.

    앵커가 아예 계산되지 않은 상태도 fail-closed 로 실패다.
    """
    if not anchors:
        return ["앵커가 계산되지 않았다"]
    return [
        f"{label}={value}" for label, value in sorted(anchors.items()) if "!=" in value
    ]


def guard_record_violations() -> list[str]:
    """감사 hook 이 **인가된 프로브 창 밖에서** 기록한 위반 + 정책 상태 이상.

    v2.6 은 이 기록을 `print` 만 했다.  대상 코드가 `AuditViolation` 을 삼키면
    가드가 탐지·기록했어도 모든 Case 가 green 이라 exit 0 이었다 (심판 #2).

    프로브 기록 쪽은 실행 도중에는 계속 늘어나므로 여기서 보지 않는다 —
    종료 시점 결속은 `probe_record_violations()` 가 맡는다.
    """
    findings = [f"감사hook·열람:{item}" for item in audit_guard.blocked_reads]
    findings += [f"감사hook·쓰기:{item}" for item in audit_guard.blocked_writes]
    depth = audit_guard.probe_depth()
    if depth != 0:
        findings.append(f"프로브 창이 열린 채 남았다: depth={depth}")
    read_armed, write_armed = audit_guard.armed()
    if not read_armed:
        findings.append("열람 정책이 내려갔다")
    if not write_armed:
        findings.append("쓰기 정책이 내려갔다")
    return findings


def probe_record_violations(cfg) -> list[str]:
    """인가된 프로브 기록의 **토큰별 개수**를 설정 앵커에 결속한다 (v2.8).

    v2.7 은 `blocked_*` 만 exit 에 실었고 `probe_*` 는 어느 채널에도 닿지
    않았다.  그 순간 **분류가 곧 exit 결속 여부**가 됐고, 창을 여는 것만으로
    자기 기록을 게이트에서 감출 수 있었다 (심판 v2.7 #3).  v2.8 은 창을
    토큰·호출 지점으로 인가하고(`audit_guard.PROBE_SITES`), 인가된 창의 기록도
    **토큰별 (열람, 쓰기) 개수**로 설정에 묶는다 — 창 안이든 밖이든 기록 **수**가
    등재와 어긋나면 종료 코드가 뒤집힌다.

    **v2.9 정정 (심판 v2.8 #2)**: v2.8 은 이 함수가 "identity 와 개수" 를
    결속한다고 적었다.  거짓이었다 — 세는 것은 개수뿐이고 기록 **본문**은 어느
    층도 읽지 않는다.  같은 개수의 내용 치환은 여기서 침묵한다.
    등재는 `L-AUDIT-PROBE-THREAD`.
    """
    pinned = config.cfg_pairs(dict(cfg), "anchor_probe_records")
    observed = audit_guard.probe_record_counts()
    findings = [
        f"인가되지 않은 프로브 창: {item}" for item in audit_guard.unsanctioned_windows
    ]
    for token in sorted(set(pinned) | set(observed)):
        counts = observed.get(token)
        actual = "없음" if counts is None else f"{counts[0]}:{counts[1]}"
        expected = pinned.get(token, "미등재")
        if actual != expected:
            findings.append(f"프로브 기록 {token}={actual}!={expected}")
    return findings


def operational_violations(cfg, write_recorder, read_recorder) -> list[str]:
    """**대조군 밖**에서 관측된 경계 위반 전부 — Case 와 무관하게 exit 에 닿는다.

    의도적 프로브 기록과 운영 위반 기록의 분리는 유지한다.  합치면 러너 자신의
    프로브 때문에 상시 red 가 되기 때문이다.  분리가 실제로 성립하는지는 대조군
    `T-77-SEPARATION` 이 관측하고, 분리된 쪽의 **토큰별 개수만**
    `probe_record_violations()` 가 설정 앵커에 결속한다.

    **v2.9 정정 (심판 v2.8 #2)**: v2.8 은 여기에 "개수·identity" 라 적었다.
    거짓이었다 — 결속되는 것은 개수뿐이고 기록 **본문**은 어느 층도 읽지 않는다.
    같은 개수의 내용 치환은 이 경로에서 침묵한다.
    """
    findings = guard_record_violations()
    findings += probe_record_violations(cfg)
    findings += [f"monkeypatch·쓰기:{item}" for item in write_recorder.attempts]
    findings += [f"monkeypatch·열람:{item}" for item in read_recorder.attempts]
    return findings


def exit_status(
    failed: Sequence[Case],
    violations: Sequence[str],
    anchor_failures: Sequence[str],
) -> int:
    """세 발견 채널이 모이는 종료 코드 결정 지점.

    v2.6 은 `Case.ok` 하나만 봤다 — 가드 기록과 앵커 드리프트는 출력 전용이었다.
    배선 **자체가 실재하는지**는 `SELF-3` 이 이 파일의 AST 에서 파생해 관측한다.

    **이 함수는 최종 신뢰점이며 그 자체를 자기검사로 지킬 수 없다** — 같은
    프로세스 안에서 이 이름을 0 만 돌려주게 갈아끼우면 red Case·운영 위반·앵커
    드리프트를 전부 탐지·출력하고도 exit 0 이 된다.  검출층의 판정이 결국 이
    함수를 경유하므로 층을 더 쌓아도 회귀가 끝나지 않는다.  그 구조적 한계는
    `L-EXIT-ROOT` 로 등재했고, 해소는 **별도 프로세스의 외부 검증자**뿐이며
    설정 `deferred_owner_tracks`/`required_deferrals` 에 **기록된** 트랙으로
    이연됐다 (v2.9 — 트랙 값을 여기 리터럴로 적지 않는다.  v2.9 후속 정정:
    러너는 그 두 줄의 **일치**만 보고 트랙 값 자체는 고정하지 않는다).
    자기증명한다고 적지 않는다.
    """
    return 0 if not (failed or violations or anchor_failures) else 1


def exit_wiring(source: str) -> dict[str, bool]:
    """`main()` 이 세 채널을 실제로 `exit_status` 로 넘기는가 — AST 파생.

    자기신고가 아니다.  채널을 하나 빼면 여기서 red 가 된다.
    """
    tree = ast.parse(source)
    main_fn = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        ),
        None,
    )
    if main_fn is None:
        return {"main 존재": False}
    returns = [node for node in ast.walk(main_fn) if isinstance(node, ast.Return)]
    single = len(returns) == 1
    call = returns[0].value if single else None
    via = (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "exit_status"
        and len(call.args) == 3
    )
    assigned: dict[str, str] = {}
    for node in ast.walk(main_fn):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = node.value
        assigned[target.id] = (
            value.func.id
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            else ""
        )
    arg_names = (
        [arg.id for arg in call.args if isinstance(arg, ast.Name)] if via else []
    )
    producers = {assigned.get(name, "") for name in arg_names}
    return {
        "main 존재": True,
        "단일 return": single,
        "exit_status 경유": via,
        "Case 채널": len(arg_names) == 3 and "failed" in arg_names,
        "가드 기록 채널": "operational_violations" in producers,
        "앵커 드리프트 채널": "anchor_report_failures" in producers,
    }


def runner_source_anchor(source: str) -> str:
    """러너 **소스 전체**의 앵커 (v2.5 4 차 교정).

    3 차까지는 산문 통로를 하나씩 닫았고, 매번 **인접 통로**가 남았다:
    노트 리터럴 -> 노트 삽입부 -> `Case.detail` -> **`SELF-1` 자신의 detail**.
    마지막 것은 자기참조를 피하려고 내가 직접 앵커에서 제외해 놓고 **열린 통로로
    등재하지 않은** 것이다.  통로를 열거해 닫는 방식이 3 회 연속 실패했으므로
    여기서 방식을 바꾼다 — **소스 전체를 묶는다.**

    자기참조 없음: 앵커 값은 `config.yaml` 에 있고 소스에는 없다.  대가는
    명시한다 — 러너의 **어떤 편집이든** 설정 갱신을 요구한다.  이 러너는 심사
    중인 동결 계약 아티팩트이므로 그 대가는 의도된 것이며, T-71·T-76 과 같은
    커밋된 앵커 규율이다.

    **여전히 닫히지 않는 것**: 검증 이후 단계의 `print()` 출력과, 앵커를 산문과
    함께 갱신하는 경로(설정 diff 로 드러난다).  폐쇄라고 적지 않는다.
    """
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def case_prose_anchor(cases: Sequence[Case]) -> str:
    """Case 의 `name`·`detail` 앵커 (v2.5 3 차 교정, 선제).

    노트만 묶으면 **인접 통로**가 남는다 — `Case.detail` 도 자유 산문이고
    exit status 에 묶이지 않는다.  green Case 의 detail 에 결함 서술을 실으면
    그것이 곧 §8.2 가 정식화한 "막은 옆에 인접 우회로" 다.

    **`SELF-1` 도 포함한다** (v2.5 5 차 교정).  4 차까지는 digest 값이 SELF-1 의
    detail 에 박혀 있어 자기참조 때문에 제외했고, 그 제외가 곧 주차 지점이었다.
    이제 digest 값을 detail 에서 빼고 `main()` 출력으로 옮겼으므로 자기참조 없이
    포함할 수 있다 — **배제를 없애는 것이 배제를 등재하는 것보다 낫다.**

    `ok` 는 digest 대상이 아니다.  그래서 detail 을 먼저 확정한 뒤 해시하고,
    그 결과로 `ok` 를 정하는 2 단계가 순환 없이 성립한다.

    **주장 축소 (v2.11 — 심판 9 회차 #1 의 구분자 접힘 클래스를 ⒞ 에 귀속).**
    이 앵커가 관측하는 것은 아래 `joined` — 즉 **이어붙인 문자열(따라서 그
    digest)이 바뀌는** 변경뿐이다.  레코드 안의 세 항은 태그도 길이도 없이
    `\\x1f` 로, 레코드 사이는 `\\x00` 으로만 이어지므로 **항 목록이 달라도
    이어붙인 결과가 같으면 digest 는 불변이다.**  **보장 밖**:
    구분자(`\\x1f`/`\\x00`)가 값 안에 들어가 항 경계가 사라져 같은 직렬화로 접히는
    변경.  실측 — 접힘의 최소 사례는 `('a\\x1fb',)` 와 `('a','b')` 가 둘 다
    `a\\x1fb` 로 접히는 것이고, 이 앵커에서는 `Case("T1","n",…,"x\\x1fy")` 와
    `Case("T1","n\\x1fx",…,"y")` 가 둘 다 `T1\\x1fn\\x1fx\\x1fy` 로 접혀 digest 가
    같다(`4880d819e8cb2d12`).  `\\x00` 쪽도 같아서 두 Case 를 한 Case 로 접을 수
    있다.  ⒝ `emitted_text_anchor` 와 **같은 클래스**이며 등재는
    `L-SRC-ANCHOR` 이다.
    """
    joined = "\x00".join(
        "\x1f".join((case.tid, case.name, case.detail))
        for case in sorted(cases, key=lambda item: (item.tid, item.name))
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


# --- 우선순위 1 -------------------------------------------------------------


def t75_all_met_reachability(cfg, rep: Report) -> None:
    """T-75 — 11 항 전부 MET 인 벡터가 계약 위반이 아니고 verdict=MET 인가."""
    registry = register.all_checkable_registry()
    inputs = register.all_checkable_inputs(registry)
    ctx = enforcement.build_context(cfg, registry=registry, inputs=inputs)
    contributions = ctx.evaluation.contributions

    domain_ok = set(contributions) == set(gates.predicate_domain(registry))
    all_met = all(value == gates.MET for value, _ in contributions.values())
    verdict_met = all(v == gates.MET for v in ctx.evaluation.verdict.values())
    u11_problems = enforcement._check_u11(ctx)

    clean_green = domain_ok and all_met and verdict_met and not u11_problems

    # 뮤테이션 = v2.0 의 `전사(surjective)` 문언.  공역의 모든 원소가 상에
    # 포함되어야 하므로 NOT_MET 이 최소 하나 강제되고, 논리곱과 결합하면
    # all-MET 는 계약 위반이 된다.
    surjective_violated = len({v for v, _ in contributions.values()}) < 2
    mutant_red = surjective_violated

    rep.add(
        Case(
            "T-75",
            "all-MET 도달성 (전역 vs 전사)",
            clean_green,
            mutant_red,
            f"11/11 MET={all_met} verdict={ctx.evaluation.verdict} "
            f"U-11위반={u11_problems}",
        )
    )

    # 문서와 실행이 충돌하는 지점을 **앵커형 Case** 로 고정한다 (교정 1).
    # 방향① 기준 레지스트리에서는 분포 앵커가 성립하고,
    # 방향② all-CHECKABLE 승격 레지스트리에서는 성립하지 않는다.
    base_t71 = enforcement._check_t71(enforcement.build_context(cfg))
    promoted_t71 = enforcement._check_t71(ctx)
    rep.add(
        Case(
            "T-75/T-71",
            "all-MET 도달성 ↔ 분포 앵커 (앵커형)",
            not base_t71,
            bool(promoted_t71),
            "all-MET 벡터는 11 술어 전부 CHECKABLE 을 요구하고 그 순간 T-71 "
            f"분포 앵커가 이탈한다 → {promoted_t71}",
        )
    )


def t2_input_missing_basis(cfg, rep: Report) -> None:
    """T-2 — 11 술어 **각각** 입력 삭제 → basis 가 INPUT_MISSING 으로 바뀌는가."""
    registry = gates.build_gate_registry()
    rows = register.fixture_rows()
    base_inputs = register.fixture_inputs()
    baseline = gates.evaluate(registry, base_inputs, rows)

    observable_by_basis: list[str] = []
    observable_by_value: list[str] = []
    unconstructible: list[str] = []
    failures: list[str] = []

    for gid in gates.completion_gates(registry):
        for predicate in registry[gid].predicates:
            pid = predicate.pid
            if predicate.input_key is None:
                unconstructible.append(pid)
                continue
            mutated_inputs = {
                k: v for k, v in base_inputs.items() if k != predicate.input_key
            }
            mutated = gates.evaluate(registry, mutated_inputs, rows)
            before_v, before_b = baseline.contributions[pid]
            after_v, after_b = mutated.contributions[pid]
            if after_b != gates.INPUT_MISSING:
                failures.append(f"{pid}: basis 가 {after_b} 로 남았다")
                continue
            if before_b != after_b:
                observable_by_basis.append(pid)
            if before_v != after_v:
                observable_by_value.append(pid)

    clean_green = not failures

    # 뮤테이션 = 입력을 읽지 않는 구현.  §4.2.2 결합 규칙만 보면 규칙 준수다.
    ignoring_detected: list[str] = []
    for gid in gates.completion_gates(registry):
        for predicate in registry[gid].predicates:
            if predicate.classification != gates.PARTIAL:
                continue
            mutated_inputs = {
                k: v for k, v in base_inputs.items() if k != predicate.input_key
            }
            mutant = gates.evaluate(registry, mutated_inputs, rows, ignore_inputs=True)
            if mutant.contributions[predicate.pid][1] != gates.INPUT_MISSING:
                ignoring_detected.append(predicate.pid)

    mutant_red = len(ignoring_detected) == 3

    rep.add(
        Case(
            "T-2",
            "INV-C3 입력 부재 관측 (basis)",
            clean_green,
            mutant_red,
            f"basis 관측 {len(observable_by_basis)}/11 · "
            f"value 관측 {len(observable_by_value)}/11 · "
            f"구성 불가(NMC) {len(unconstructible)}/11 · 실패 {failures}",
        )
    )
    rep.limit(
        "L-T2-SCOPE",
        f"T-2 관측 범위: basis={sorted(observable_by_basis)} "
        f"value={sorted(observable_by_value)} 구성불가={sorted(unconstructible)}",
    )

    # 잔여를 **앵커형 Case** 로 고정한다 (교정 1).  `부분` 술어의 판정 함수를
    # 상수로 바꿔도 basis 는 동일하게 움직인다 — T-2 는 입력이 '접촉'됐음만
    # 증명하고 '사용'됐음은 증명하지 않는다.  이 예측이 바뀌면 red 가 된다.
    decorative = gates.build_gate_registry()
    for gid in gates.completion_gates(decorative):
        gate = decorative[gid]
        decorative[gid] = gates.Gate(
            gid,
            gate.kind,
            tuple(
                gates.Predicate(
                    p.gate,
                    p.row,
                    p.label,
                    p.classification,
                    p.input_key,
                    (
                        (lambda _value: True)
                        if p.classification == gates.PARTIAL
                        else p.evaluator
                    ),
                )
                for p in gate.predicates
            ),
        )
    decorative_same = True
    for gid in gates.completion_gates(decorative):
        for predicate in decorative[gid].predicates:
            if predicate.classification != gates.PARTIAL:
                continue
            mutated_inputs = {
                k: v for k, v in base_inputs.items() if k != predicate.input_key
            }
            probe = gates.evaluate(decorative, mutated_inputs, rows)
            if probe.contributions[predicate.pid][1] != gates.INPUT_MISSING:
                decorative_same = False
    rep.add(
        Case(
            "T-2-잔여",
            "basis 는 '사용' 을 증명하지 않는다 (앵커형)",
            clean_green,
            decorative_same,
            "`부분` 술어의 판정 함수를 상수 True 로 바꿔도 basis 관측은 동일하다"
            f"({decorative_same}) — basis 는 '입력을 참조했는가'만 운반한다",
        )
    )


def t69_classification_isolation(cfg, rep: Report) -> None:
    """T-69 — 분류 3 종 격리 변형 → 해당 술어의 기여 항만 바뀌는가."""
    registry = gates.build_gate_registry()
    rows = register.fixture_rows()
    inputs = register.fixture_inputs()
    baseline = gates.evaluate(registry, inputs, rows)

    by_class: dict[str, set[str]] = {c: set() for c in gates.CLASSIFICATIONS}
    for gid in gates.completion_gates(registry):
        for predicate in registry[gid].predicates:
            by_class[predicate.classification].add(predicate.pid)

    isolated_ok = True
    detail: list[str] = []
    verdict_moved: list[str] = []
    for classification in gates.CLASSIFICATIONS:
        mutated = gates.evaluate(
            registry, inputs, rows, fold={classification: gates.MET}
        )
        changed = {
            pid
            for pid in baseline.contributions
            if baseline.contributions[pid][0] != mutated.contributions[pid][0]
        }
        if not changed or not changed <= by_class[classification]:
            isolated_ok = False
        detail.append(f"{classification}->{sorted(changed)}")
        if mutated.verdict != baseline.verdict:
            verdict_moved.append(classification)

    # 무뮤테이션 방향: fold 를 주지 않으면 기여 항이 하나도 움직이지 않는다.
    unchanged = gates.evaluate(registry, inputs, rows)
    clean_green = unchanged.contributions == baseline.contributions

    rep.add(
        Case(
            "T-69",
            "결합 규칙 분류별 격리",
            clean_green,
            isolated_ok,
            " · ".join(detail),
        )
    )

    # §4.2.2 의 'verdict 는 세 게이트 모두에서 상수 NOT_MET' 반증을 **앵커형
    # Case** 로 고정한다 (교정 1).  방향① 기준 입력에서 verdict 는 전부 NOT_MET,
    # 방향② 접기 규칙을 변형하면 뒤집히는 분류가 실재한다.
    baseline_all_not_met = all(
        value == gates.NOT_MET for value in baseline.verdict.values()
    )
    rep.add(
        Case(
            "T-69-반증",
            "verdict 상수성은 규칙 변화에 대해 거짓 (앵커형)",
            baseline_all_not_met,
            bool(verdict_moved),
            f"접기 규칙 변형으로 verdict 가 이동하는 분류={verdict_moved} — G3 는 "
            "술어 3 개가 전부 NMC 라 NMC 접기 방향이 곧 G3 의 verdict 다",
        )
    )


def t62_owner_track_grammar(cfg, rep: Report) -> None:
    """T-62 — 문법 밖 값 5 종 전부 거부 + 유효 값은 수용."""
    negatives = ("Phase 5-2", "Phase 8", "Phase 0-7", "GOV-001 / Phase 1", "언젠가")
    positives = (
        "Phase 1",
        "GOV-001",
        "GOV-001+Phase 1",
        "Phase 2-5",
        "Phase 4+Phase 6",
    )

    accepted_positive: list[str] = []
    for value in positives:
        try:
            register.classify_owner_track(value, cfg)
            accepted_positive.append(value)
        except register.OwnerTrackSyntaxError:
            pass
    clean_green = len(accepted_positive) == len(positives)

    rejected: list[str] = []
    for value in negatives:
        try:
            register.classify_owner_track(value, cfg)
        except register.OwnerTrackSyntaxError:
            rejected.append(value)
    mutant_red = len(rejected) == len(negatives)

    rep.add(
        Case(
            "T-62",
            "owner_track 문법 밖 거부",
            clean_green,
            mutant_red,
            f"유효 수용 {len(accepted_positive)}/{len(positives)} · "
            f"음성 거부 {len(rejected)}/{len(negatives)}",
        )
    )

    # 임계값이 정말 설정 구동인지를 **Case** 로 결속한다 (교정 1).  이것이 노트로
    # 남으면 리터럴 하드코딩 회귀(CLAUDE.md 비협상 규칙)가 green 을 유지한다.
    base_rejects = "Phase 0-7" in rejected
    widened = dict(cfg)
    widened["owner_track_range_max_width"] = 7
    try:
        register.classify_owner_track("Phase 0-7", widened)
        config_driven = True
    except register.OwnerTrackSyntaxError:
        config_driven = False
    rep.add(
        Case(
            "T-62-cfg",
            "폭 상한이 설정 구동인가",
            base_rejects,
            config_driven,
            f"기본 상한(3)에서 `Phase 0-7` 거부={base_rejects} · "
            f"상한 7 로 올리면 수용={config_driven}",
        )
    )
    if not config_driven:
        rep.defect(
            "T-62-cfg",
            "폭 상한이 설정에서 읽히지 않는다 — 임계값 하드코딩 금지 규칙 위반이다",
        )


def _probe_builtin_open() -> None:
    """OD-3-C 실물 프로브.  차단되면 `with` 진입 전에 예외가 난다.

    표적은 부모가 없는 경로다 — 가드가 죽어도 실물이 생기지 않는다 (v2.8).
    """
    with open(_WRITE_PROBE_ROOT / "__probe_open.tmp", "w") as handle:
        handle.write("x")


def _probe_os_open() -> None:
    """OD-3-C 실물 프로브.  차단되지 않으면 fd 를 남기지 않고 즉시 닫는다."""
    fd = os.open(
        str(_WRITE_PROBE_ROOT / "__probe_osopen.tmp"), os.O_WRONLY | os.O_CREAT
    )
    os.close(fd)


def t77_boundary(cfg, rep: Report) -> None:
    """T-77 — OD-3 경계 강제 A·B·C.  각각 위반을 심어 검출을 확인한다.

    **D(CI 미편입)·E(D0 승격 금지)는 여기서 검사하지 않는다.**
    """
    proto_dir = _HERE / "proto"
    runner_path = Path(__file__)
    audit_path = Path(audit_guard.__file__)
    # `audit_guard.py` 도 스캔 도메인 안이다 (v2.6) — 강제의 정본이 사는 파일이
    # 스캔 밖이면 그 파일이 곧 다음 창이다.
    sources = boundary.read_prototype_sources(
        proto_dir, extra=(runner_path, audit_path)
    )

    # 금지 토큰을 러너 소스에 리터럴로 두면 러너 자신이 스캔에 걸린다.
    # 조각은 **런타임에** 토큰에서 잘라 쓴다 — 소스에는 남지 않는다.
    token = boundary.FORBIDDEN_SOURCE_TOKENS[0]
    head, tail = token[: len(token) // 2], token[len(token) // 2 :]

    # ①-리터럴 소스 스캔
    clean_scan = boundary.scan_sources(sources)
    planted = dict(sources)
    planted["<주입된 리터럴 위반>"] = "import csv\npath = '" + head + tail + "src/x'\n"
    mutant_scan = boundary.scan_sources(planted)
    rep.add(
        Case(
            "T-77-①",
            "소스에 코퍼스·register 이름 등장 금지 (리터럴)",
            not clean_scan,
            bool(mutant_scan),
            f"clean={clean_scan} mutant={mutant_scan}",
        )
    )

    # ①-AST 스캔 — 리터럴을 **합성**하는 표현식까지 평가한다 (교정 4-A).
    ast_scan = getattr(boundary, "scan_sources_ast", None)
    if ast_scan is None:
        rep.add(
            Case(
                "T-77-①-AST",
                "합성 리터럴 AST 스캔",
                False,
                False,
                "boundary.scan_sources_ast 가 없다 — 합성 위반을 평가하는 검사가 없다",
            )
        )
        rep.defect(
            "T-77-①-AST",
            "리터럴 스캔만 있어 조각을 이어붙인 합성 경로가 검출되지 않는다",
        )
    else:
        clean_ast = ast_scan(sources)
        # 심판이 직접 심은 형태를 그대로 대조군으로 쓴다.
        planted_ast = dict(sources)
        # AST 스캔의 도메인은 `.py` 소스다 — 주입 키도 그 도메인 안에 둔다.
        planted_ast["__주입된_합성_위반__.py"] = (
            "from pathlib import Path\np = Path('" + head + "' + '" + tail + "')\n"
        )
        mutant_ast = ast_scan(planted_ast)
        # 면제가 좁은지도 관측한다 — 면제 파일에 **면제되지 않은 이름**으로 심는다.
        site = boundary.TOKEN_DEFINITION_SITE
        planted_narrow = dict(sources)
        planted_narrow[site] = (
            sources[site] + "\n_LEAK = '" + head + "' + '" + tail + "'\n"
        )
        mutant_narrow = ast_scan(planted_narrow)
        rep.add(
            Case(
                "T-77-①-AST",
                "합성 리터럴 AST 스캔",
                not clean_ast,
                bool(mutant_ast) and bool(mutant_narrow),
                f"clean={clean_ast} · 합성 주입 검출={mutant_ast} · "
                f"면제 파일의 비면제 이름 검출={mutant_narrow}",
            )
        )
        if not (mutant_ast and mutant_narrow):
            rep.defect("T-77-①-AST", "AST 합성 스캔이 심어둔 위반을 검출하지 못한다")
        rep.limit(
            "L-AST-FOLD",
            "T-77-①-AST 폴딩 범위 (v2.5 확장): 상수 `+`·상수 f-string 에 더해 "
            "**단일 대입 이름 전파**·`str.join`·`chr()`·`%`·`.format()`·"
            "`.replace()` 까지 접는다.  그래도 런타임 입력(파일·환경변수·argv)에서 "
            "오는 값과 튜플 언패킹으로 묶인 이름은 접히지 않는다 — 상수 폴딩으로 "
            "열람 금지를 강제하는 것 자체가 프록시이며, 강제는 열람 가드가 한다.",
        )
        rep.limit(
            "L-AST-DOMAIN",
            "T-77-①-AST 의 대상 도메인은 `.py` 소스뿐이다 — `config.yaml` 등 "
            "비-Python 파일에는 리터럴 스캔만 적용된다.  `.py` 인데 파싱되지 "
            "않으면 조용히 넘기지 않고 실패로 보고한다.",
        )
        rep.limit(
            "L-AST-EXEMPT",
            f"AST 스캔은 `{boundary.TOKEN_DEFINITION_SITE}` 의 토큰 정의 대입"
            f"({sorted(boundary.TOKEN_DEFINITION_NAMES)}) 만 면제하고, 같은 파일에서 "
            "그 이름들을 전파 환경에서도 뺀다 — 검사기는 자기가 찾는 토큰을 알아야 "
            "하기 때문이다.  면제가 그 이름들에만 붙는지는 방향② 가 관측한다.",
            case="T-77-①-AST",
        )

    # ② 파일 쓰기 (실제 시도를 심고 차단·탐지되는지 본다)
    with boundary.write_guard() as recorder:
        clean_write_ok = recorder.clean

    # **표적은 전부 부재 부모 밑이다** (v2.8, 심판 v2.7 #6): 가드가 깨지는
    # 음성 시나리오에서도 저장소 안에 실물이 생기지 않는다.
    probes: tuple[tuple[str, object], ...] = (
        ("open(w)", _probe_builtin_open),
        (
            "Path.write_text",
            lambda: (_WRITE_PROBE_ROOT / "__probe_wt.tmp").write_text("x"),
        ),
        (
            "Path.write_bytes",
            lambda: (_WRITE_PROBE_ROOT / "__probe_wb.tmp").write_bytes(b"x"),
        ),
        ("os.open", _probe_os_open),
        (
            "os.replace",
            lambda: os.replace(
                str(_WRITE_PROBE_ROOT / "__probe_a"),
                str(_WRITE_PROBE_ROOT / "__probe_b"),
            ),
        ),
        (
            "shutil.copyfile",
            lambda: shutil.copyfile(
                str(runner_path), str(_WRITE_PROBE_ROOT / "__probe_cp.tmp")
            ),
        ),
        (
            "shutil.rmtree",
            lambda: shutil.rmtree(str(_WRITE_PROBE_ROOT / "__probe_dir")),
        ),
    )
    blocked: list[str] = []
    escaped: list[str] = []
    with boundary.write_guard() as recorder2:
        for label, action in probes:
            try:
                action()  # type: ignore[operator]
                escaped.append(label)
            except boundary.BoundaryViolation:
                blocked.append(label)
            except OSError:
                # 차단되기 **전에** OS 오류가 나면 그 진입점은 감싸지지 않은 것이다.
                escaped.append(f"{label}(OSError)")
    leftovers = sorted(path.name for path in _HERE.glob("__*probe*"))
    rep.add(
        Case(
            "T-77-②",
            "실행 중 파일 쓰기 0 (표준 라이브러리 진입점)",
            clean_write_ok,
            len(blocked) == len(probes) and not leftovers,
            f"차단 {len(blocked)}/{len(probes)} {blocked} · 미차단={escaped or '없음'} "
            f"· 잔존 파일={leftovers or '없음'} · 기록={len(recorder2.attempts)}건",
        )
    )
    if escaped or leftovers:
        rep.defect("T-77-②", f"쓰기 진입점이 감싸지지 않았다: {escaped} {leftovers}")

    # ③ 금지 아티팩트 — **각 항목을 하나씩** 표적으로 삼는다 (v2.6, 심판 F1).
    # v2.5 는 `FORBIDDEN_ARTIFACTS[0]` 하나만 심고 방향② 를 `len(mutant)==1` 로
    # 봤다.  그래서 목록을 5→1 로 줄여도 방향② 가 그대로 성립해 침묵했다.
    clean_artifacts = boundary.forbidden_artifacts_present(
        lambda path: Path(path).exists(), _REPO_ROOT
    )
    per_artifact: list[str] = []
    for rel in boundary.FORBIDDEN_ARTIFACTS:
        target = str(_REPO_ROOT / rel)
        found = boundary.forbidden_artifacts_present(
            lambda path, wanted=target: path == wanted, _REPO_ROOT
        )
        if len(found) == 1 and rel in found[0]:
            per_artifact.append(rel)
    # 항목 **삭제**가 앵커로 관측되는지 — 각 인덱스를 빼 본다.
    artifacts_digest = tuple_anchor(boundary.FORBIDDEN_ARTIFACTS)
    expected_artifacts = str(dict(cfg).get("anchor_forbidden_artifacts_digest", ""))
    shrink_detected = [
        index
        for index in range(len(boundary.FORBIDDEN_ARTIFACTS))
        if tuple_anchor(
            boundary.FORBIDDEN_ARTIFACTS[:index]
            + boundary.FORBIDDEN_ARTIFACTS[index + 1 :]
        )
        != expected_artifacts
    ]
    rep.add(
        Case(
            "T-77-③",
            "금지 D0 아티팩트 전 항목 미생성 + 목록 앵커",
            not clean_artifacts and artifacts_digest == expected_artifacts,
            len(per_artifact) == len(boundary.FORBIDDEN_ARTIFACTS)
            and len(shrink_detected) == len(boundary.FORBIDDEN_ARTIFACTS),
            f"clean={clean_artifacts} · 항목별 검출 {len(per_artifact)}/"
            f"{len(boundary.FORBIDDEN_ARTIFACTS)} · 1 개 삭제 검출 "
            f"{len(shrink_detected)}/{len(boundary.FORBIDDEN_ARTIFACTS)}",
        )
    )
    if artifacts_digest != expected_artifacts:
        rep.defect(
            "T-77-③",
            f"금지 아티팩트 목록이 설정 앵커와 다르다: {artifacts_digest} != "
            f"{expected_artifacts}",
        )

    # ①⒜ 런타임 열람 가드 — 경로 **값** 으로 판정한다 (v2.5, 심판 F3).
    # 정적 스캔이 뚫린 3 종 조립을 그대로 재현해 전부 차단되는지 본다.
    with boundary.read_guard() as read_rec:
        clean_read_ok = read_rec.clean
        try:
            (proto_dir / "config.yaml").read_text(encoding="utf-8")
            self_read_ok = True
        except boundary.BoundaryViolation:
            self_read_ok = False

    corpus = token.rstrip("/")
    assembled = (
        ("리터럴", corpus),
        ("join", "".join((corpus[:3], corpus[3:]))),
        ("chr", corpus[:3] + chr(ord(corpus[3])) + corpus[4:]),
    )
    blocked_reads: list[str] = []
    escaped_reads: list[str] = []
    with boundary.read_guard() as read_rec2:
        for label, name in assembled:
            try:
                (_REPO_ROOT / name / "src").read_text(encoding="utf-8")
                escaped_reads.append(label)
            except boundary.BoundaryViolation:
                blocked_reads.append(label)
            except OSError:
                # 가드가 발화하기 **전에** OS 오류 = 그 경로는 판정되지 않았다.
                escaped_reads.append(f"{label}(OSError)")
    rep.add(
        Case(
            "T-77-①-READ",
            "코퍼스·register 열람 차단 (경로 값)",
            clean_read_ok and self_read_ok,
            len(blocked_reads) == len(assembled),
            f"자기 소스 열람 허용={self_read_ok} · 조립별 차단={blocked_reads} "
            f"· 미차단={escaped_reads or '없음'} · 기록={len(read_rec2.attempts)}건",
        )
    )
    if escaped_reads:
        rep.defect("T-77-①-READ", f"코퍼스 열람이 차단되지 않았다: {escaped_reads}")

    # ④ 러너 위치 앵커 — repo 밖 사본에서도 전건 GREEN 이던 구멍 (심판 F3 부수).
    clean_locate = boundary.locate_violation(runner_path, _REPO_ROOT)
    moved_locate = boundary.locate_violation(
        Path(os.sep) / "elsewhere" / runner_path.name, _REPO_ROOT
    )
    # **가짜 루트 표지** 대조군 (v2.6, 심판 F3 high).  v2.5 는 표지가
    # `('.git','pyproject.toml')` 였고 **하나만 있어도** 통과했다 — repo 안의
    # `tos/pyproject.toml` 이 그대로 가짜 루트 재료였고, 실재하지 않는 러너
    # 경로마저 `[]` 로 통과했다.  **파일을 만들지 않고** 두 층을 다 관측한다:
    #   ⒜ 표지 집합이 좁혀졌는가 (구조 — 상수에서 파생한다)
    #   ⒝ `.git` 없는 루트 + 실물 없는 예상 경로가 실제로 거부되는가 (실물)
    # 절대경로는 detail 에 넣지 않는다 — 같은 상대경로의 사본이 같은 산문 앵커를
    # 갖도록 해야 "사본이면 무조건 red" 라는 잡음이 생기지 않는다.
    marker_narrowed = (
        "pyproject.toml" not in boundary.REPO_MARKERS
        and ".git" in boundary.REPO_MARKERS
    )
    forged_root = _HERE  # `.git` 이 없는 실재 디렉터리
    forged_locate = boundary.locate_violation(
        forged_root / boundary.EXPECTED_RUNNER_RELPATH, forged_root
    )
    forged_layers = {
        "표지": any(
            marker in item for item in forged_locate for marker in boundary.REPO_MARKERS
        ),
        "실물동일성": any(
            boundary.EXPECTED_RUNNER_RELPATH in item for item in forged_locate
        ),
    }
    rep.add(
        Case(
            "T-77-④",
            "러너가 예상 위치의 repo 안에서 돈다",
            not clean_locate,
            bool(moved_locate) and marker_narrowed and all(forged_layers.values()),
            f"현위치 이탈={clean_locate or '없음'} · repo 밖 사본 검출={moved_locate} "
            f"· 표지 {boundary.REPO_MARKERS} 좁힘={marker_narrowed} · "
            f"가짜 루트 거부 {len(forged_locate)}건 층={forged_layers}",
        )
    )

    # ④⒝ **`.git` 의미 검증** (v2.7, 심판 #5 medium).  v2.6 은 `exists()` 만 봐서
    # **빈 `.git` 파일 하나**로 통과했다.  실물을 만들면 그 자체가 OD-3-C 위반
    # 이므로 `FsProbe` seam 으로 음성·양성을 각각 주입한다 (`L-T77-SEAM` 과 같은
    # 패턴).  **실제 파일시스템 양성**은 이 repo 루트 자신이 담당한다.
    def _probe(tree_map: dict[str, str | None]) -> boundary.FsProbe:
        """`{경로문자열: 내용 or None(=디렉터리)}` 로 이루어진 가짜 파일시스템."""
        return boundary.FsProbe(
            exists=lambda path: str(path) in tree_map,
            is_dir=lambda path: tree_map.get(str(path), "") is None,
            is_file=lambda path: isinstance(tree_map.get(str(path)), str),
            read_text=lambda path: str(tree_map[str(path)]),
        )

    fake_root = Path(os.sep) / "fake-root"
    git_cases = {
        # 음성 — 심판이 지목한 위조: 빈 `.git` 파일 하나
        "빈 .git 파일": (_probe({str(fake_root / ".git"): ""}), False),
        # 음성 — 내용은 있으나 gitdir 포인터가 아니다
        "비-gitdir 파일": (
            _probe({str(fake_root / ".git"): "not a pointer\n"}),
            False,
        ),
        # 음성 — gitdir 포인터인데 대상에 HEAD 가 없다
        "죽은 gitdir 포인터": (
            _probe({str(fake_root / ".git"): "gitdir: /nowhere/wt\n"}),
            False,
        ),
        # 음성 — 디렉터리형인데 git 내부 구조가 없다
        "빈 .git 디렉터리": (_probe({str(fake_root / ".git"): None}), False),
        # 양성 — 정상 worktree 의 파일형 `.git`
        "worktree gitdir": (
            _probe(
                {
                    str(fake_root / ".git"): "gitdir: /gitdirs/wt\n",
                    "/gitdirs/wt/HEAD": "ref: refs/heads/main\n",
                }
            ),
            True,
        ),
        # 양성 — 정상 디렉터리형 `.git`
        "디렉터리형 .git": (
            _probe(
                {
                    str(fake_root / ".git"): None,
                    **{
                        str(fake_root / ".git" / name): None
                        for name in boundary.GIT_DIR_REQUIRED
                    },
                }
            ),
            True,
        ),
    }
    git_wrong: list[str] = []
    for label, (probe, expect_ok) in git_cases.items():
        findings = boundary.git_marker_findings(fake_root, probe)
        if bool(findings) == expect_ok:  # ok 를 기대했는데 findings 가 있으면 틀림
            git_wrong.append(label)
    # 실제 파일시스템 양성 — 이 repo 루트.
    real_root_ok = not boundary.git_marker_findings(_REPO_ROOT)
    top_level = boundary.repository_top_level(_HERE)
    top_level_ok = top_level is not None and top_level.resolve() == _REPO_ROOT.resolve()
    rep.add(
        Case(
            "T-77-④-GIT",
            ".git 표지의 의미 검증 (음성·양성)",
            real_root_ok and top_level_ok,
            not git_wrong,
            f"실제 루트 유효={real_root_ok} · top-level 일치={top_level_ok} · "
            f"seam 대조군 {len(git_cases) - len(git_wrong)}/{len(git_cases)} 일치"
            f"{'' if not git_wrong else f' · 불일치={git_wrong}'}",
        )
    )
    if git_wrong or not real_root_ok or not top_level_ok:
        rep.defect(
            "T-77-④-GIT",
            f"`.git` 표지 의미 검증이 어긋난다: 불일치={git_wrong} "
            f"실제루트={real_root_ok} top-level={top_level_ok}",
        )

    # ⑤ **프로세스 전역 감사 hook** — F3 critical 의 교정 지점 (v2.6).
    # 여기서 관측하는 것은 두 가지다:
    #   ⑴ 구조: 러너 자기 소스에서 `import audit_guard` 가 `proto` import 보다
    #      **앞**에 있는가.  자기신고가 아니라 AST 에서 파생한다.
    #   ⑵ 실물: monkeypatch 가 닿지 않는 별칭(`_io.open`)·대소문자 변형 경로·
    #      디렉터리 열람이 전부 차단되는가.  **파일은 존재하지 않아도 된다** —
    #      감사 이벤트는 여는 시점에 발화하므로 실제 열람은 일어나지 않는다.
    own_tree = ast.parse(sources[runner_path.name])
    audit_lines = [
        node.lineno
        for node in ast.walk(own_tree)
        if isinstance(node, ast.Import)
        and any(alias.name == "audit_guard" for alias in node.names)
    ]
    proto_lines = [
        node.lineno
        for node in ast.walk(own_tree)
        if isinstance(node, ast.ImportFrom)
        and str(node.module or "").split(".")[0] == "proto"
    ]
    static_order_ok = (
        bool(audit_lines) and bool(proto_lines) and max(audit_lines) < min(proto_lines)
    )

    # ⑸ **pre-hook 구간** — 정적 import 행번호 비교로는 못 보던 두 표면 (v2.7,
    # 심판 #3 high).  ⒜ hook 이전에 **실행되는 문장** ⒝ `__import__`·`importlib`·
    # `exec` 로 하는 **동적 로드**.  구간 전체를 설정 digest 로 고정하고,
    # 동적 로드 이름은 그 자체로 findings 다 (fail-closed).
    runner_prehook = prehook_analysis(
        sources[runner_path.name], is_audit_guard_import, runner_path.name
    )
    audit_prehook = prehook_analysis(
        sources[audit_path.name], is_hook_install, audit_path.name
    )
    settings = dict(cfg)
    prehook_pins = {
        runner_path.name: (
            runner_prehook,
            str(settings.get("anchor_prehook_runner", "")),
        ),
        audit_path.name: (
            audit_prehook,
            str(settings.get("anchor_prehook_audit_guard", "")),
        ),
    }
    prehook_problems: list[str] = []
    for label, (analysis, pinned) in prehook_pins.items():
        if not analysis["marker_found"]:
            prehook_problems.append(f"{label}: 설치 표지 문장을 찾지 못했다")
        if analysis["dynamic"]:
            prehook_problems.append(f"{label}: 동적 로드 {analysis['dynamic']}")
        if analysis["digest"] != pinned:
            prehook_problems.append(
                f"{label}: pre-hook 구간 digest {analysis['digest']}!={pinned}"
            )
    # **실행문 개수를 설정에 핀으로 고정한다** (v2.8, 심판 v2.7 #4).
    # v2.7 은 "실행문 0" 을 구조 요구사항으로 적었으나, 그 0 은 `ast.Assign` 을
    # 우변과 무관하게 비실행으로 세던 **분류 규약의 산물**이었다.  실제로는
    # `frozenset(...)`·`threading.local()` 같은 호출을 포함한 대입이 있으며,
    # 그 사실을 숨기지 않고 개수를 등재해 **증감을 red 로** 만든다.
    executable_pins = config.cfg_pairs(dict(cfg), "anchor_prehook_executable")
    for label, (analysis, _pin) in prehook_pins.items():
        observed = str(len(analysis["executable"]))
        expected = executable_pins.get(label, "미등재")
        if observed != expected:
            prehook_problems.append(
                f"{label}: pre-hook 실행문 {observed}건!={expected}건 "
                f"{analysis['executable']}"
            )
    # ⑹ **설치 시점 스냅샷** — 피검사 모듈이 hook 보다 먼저 로드됐는지.
    bootstrap_problems = audit_guard.bootstrap_witness(
        ("proto", "boundary", "register", "gates", "floor", "enforcement")
    )
    order_ok = static_order_ok and not prehook_problems and not bootstrap_problems

    corpus_dirname = boundary.FORBIDDEN_SOURCE_TOKENS[0].rstrip("/")
    register_name = boundary.FORBIDDEN_SOURCE_TOKENS[1] + ".csv"
    # **전부 감사 hook 단독 표면**이다 — `_io`·`posix` 는 monkeypatch 대상이
    # 아니므로 여기서 나는 차단은 오직 감사 hook 이 낸 것이다.  monkeypatch 층을
    # 거치는 경로는 `T-77-①-READ` 가 따로 관측하며, 그렇게 나눠야 이 Case 가
    # "두 층 중 어느 쪽이 막았는지 모르는" 관측이 되지 않는다.
    audit_only: tuple[tuple[str, object], ...] = (
        ("_io.open(코퍼스)", lambda: _IO.open(_REPO_ROOT / corpus_dirname / "src")),
        (
            "_io.open(코퍼스 대소문자 변형)",
            lambda: _IO.open(_REPO_ROOT / corpus_dirname.upper() / "src"),
        ),
        ("_io.FileIO(register)", lambda: _IO.FileIO(str(_HERE / register_name))),
        (
            "_io.open(register 대소문자 변형)",
            lambda: _IO.open(str(_HERE / register_name.lower())),
        ),
        (
            "posix.listdir(코퍼스)",
            lambda: _POSIX.listdir(str(_REPO_ROOT / corpus_dirname)),
        ),
        (
            "posix.scandir(코퍼스)",
            lambda: _POSIX.scandir(str(_REPO_ROOT / corpus_dirname)),
        ),
        # 쓰기 정책도 **관측**한다 — 정책 상태를 출력하는 것만으로는 자기신고다.
        # 감사 이벤트는 파일이 만들어지기 **전에** 발화하므로 잔존물이 남지 않고,
        # 표적의 부모가 **아예 없으므로** hook 이 죽어도 실물이 생기지 않는다
        # (v2.8, 심판 v2.7 #6 — v2.7 은 `_HERE` 밑 실제 경로를 열었다).
        (
            "_io.open(쓰기 모드)",
            lambda: _IO.open(str(_WRITE_PROBE_ROOT / "__audit_probe_w.tmp"), "w"),
        ),
        (
            "posix.mkdir",
            lambda: _POSIX.mkdir(str(_WRITE_PROBE_ROOT / "__audit_probe_dir")),
        ),
    )

    audit_blocked: list[str] = []
    audit_escaped: list[str] = []
    with audit_guard.probe_window("t77-audit-battery"):
        try:
            benign = _IO.open(proto_dir / "config.yaml", encoding="utf-8")
            benign.close()
            benign_ok = True
        except audit_guard.AuditViolation:
            benign_ok = False
        for label, action in audit_only:
            try:
                handle = action()  # type: ignore[operator]
                getattr(handle, "close", lambda: None)()
                audit_escaped.append(label)
            except audit_guard.AuditViolation:
                audit_blocked.append(label)
            except OSError:
                # hook 이 발화하기 **전에** OS 오류 = 그 경로는 판정되지 않았다.
                audit_escaped.append(f"{label}(OSError)")
    audit_leftovers = sorted(path.name for path in _HERE.glob("__*probe*"))
    rep.add(
        Case(
            "T-77-AUDIT",
            "프로세스 전역 감사 hook (범위=L-AUDIT-BOOTSTRAP)",
            order_ok and benign_ok,
            len(audit_blocked) == len(audit_only) and not audit_leftovers,
            f"import 순서 audit{audit_lines}<proto{proto_lines}={static_order_ok} · "
            f"pre-hook 구간 문제={prehook_problems or '없음'} · "
            f"pre-hook 실행문 러너 {len(runner_prehook['executable'])}건"
            f"/{audit_path.name} {len(audit_prehook['executable'])}건(등재 대조) · "
            f"설치 스냅샷 위반={bootstrap_problems or '없음'} · "
            f"무해한 열람 허용={benign_ok} · hook 단독 차단 {len(audit_blocked)}/"
            f"{len(audit_only)} {audit_blocked} · 미차단={audit_escaped or '없음'} · "
            f"잔존 파일={audit_leftovers or '없음'}",
        )
    )
    if audit_escaped or not order_ok:
        rep.defect(
            "T-77-AUDIT",
            f"감사 hook 이 덮지 못한 경로가 있다: {audit_escaped} "
            f"순서/구간={order_ok}",
        )

    # ⑹ **재진입 격리 + 비원시 path fail-closed** (v2.7, 심판 #4 high).
    # v2.6 의 `_REENTRANT` 는 모듈 전역 boolean 이라 한 스레드가 `_enforce` 안에
    # 있는 동안 **다른 스레드의 모든 watched event 가 무시**됐다.  또
    # `os.fsdecode` 가 임의 `PathLike.__fspath__` 를 불러 같은 스레드 재진입
    # 창까지 열었다.  두 경로를 각각 실물로 관측한다.

    class _HostilePathLike:
        """`__fspath__` 가 **사용자 코드**임을 드러내는 적대적 인자.

        원시 객체가 hook 까지 **그대로** 도달하는 경로는 실측으로 좁혔다:
        C 구현(`open`·`os.*`)은 감사 이벤트 **이전에** 경로를 문자열로 접어
        보내지만, 순수 파이썬 구현인 `shutil.*` 계열은 `sys.audit(...)` 에
        **원래 인자**를 그대로 싣는다.  v2.6 의 `os.fsdecode` 는 그 객체의
        `__fspath__` — 즉 임의 사용자 코드 — 를 **hook 안에서** 불렀고, 그
        창에서 일어나는 중첩 audit 은 재진입 플래그에 의해 전부 무시됐다.
        여기서는 콜백이 hook 안에서 불렸는지를 직접 관측한다.
        """

        calls = 0
        inside_hook = 0

        def __fspath__(self) -> str:
            _HostilePathLike.calls += 1
            if audit_guard.reentrancy_active():
                _HostilePathLike.inside_hook += 1
            return str(_REPO_ROOT / corpus_dirname / "src")

    thread_result: dict[str, object] = {}

    def _cross_thread_probe() -> None:
        # **워커 스레드는 자기 창을 연다** (v2.8, 심판 v2.7 #3).  창이 프로세스
        # 전역이던 v2.7 에서는 이 스레드의 기록이 부모 스레드의 창 덕분에 프로브로
        # 분류됐고, 같은 통로로 **아무 스레드의 진짜 위반**이든 exit 결속을
        # 벗어났다.  이제 창은 스레드 지역이므로 여기서 직접 인가를 받는다.
        with audit_guard.probe_window("t77-cross-thread"):
            try:
                handle = _IO.open(str(_REPO_ROOT / corpus_dirname / "src"))
                getattr(handle, "close", lambda: None)()
                thread_result["blocked"] = False
            except audit_guard.AuditViolation:
                thread_result["blocked"] = True
            except OSError:
                # hook 이 발화하기 **전에** OS 오류 = 판정되지 않았다.
                thread_result["blocked"] = False

    with audit_guard.probe_window("t77-reentrant"):
        # 이 스레드의 재진입 상태를 켠 채로 **다른 스레드**가 코퍼스를 연다.
        # 전역 boolean 이던 v2.6 에서는 여기서 통과했다.
        with audit_guard.reentrancy_probe():
            worker = threading.Thread(target=_cross_thread_probe, name="audit-probe")
            worker.start()
            worker.join(timeout=30)
        # 순수 파이썬 `shutil.copymode` 는 `sys.audit` 에 **원래 객체**를 실어
        # 보낸다 (실측: C 구현 `open`·`os.*` 는 전부 문자열로 접힌 뒤 발화한다).
        # `write_guard` 의 monkeypatch 대상도 아니어서 실물 경로가 그대로 열린다.
        hostile_mark = len(audit_guard.probe_reads)
        try:
            shutil.copymode(_HostilePathLike(), _HostilePathLike())
            hostile_blocked = False
        except audit_guard.AuditViolation:
            hostile_blocked = True
        except (OSError, TypeError, boundary.BoundaryViolation):
            hostile_blocked = False
        hostile_records = audit_guard.probe_reads[hostile_mark:]
    thread_local = audit_guard.reentrancy_is_thread_local()
    cross_thread_blocked = thread_result.get("blocked") is True
    fspath_outside_hook = _HostilePathLike.inside_hook == 0
    type_fail_closed = any("판정 불가 경로 타입" in item for item in hostile_records)
    rep.add(
        Case(
            "T-77-REENTRANT",
            "재진입 격리 (스레드 지역 + 비원시 path fail-closed)",
            thread_local and not worker.is_alive(),
            cross_thread_blocked
            and hostile_blocked
            and fspath_outside_hook
            and type_fail_closed,
            f"재진입 상태 thread-local={thread_local} · 다른 스레드 차단"
            f"={cross_thread_blocked} · 적대적 PathLike 차단={hostile_blocked}"
            f"(타입 fail-closed={type_fail_closed}) · `__fspath__` 총 "
            f"{_HostilePathLike.calls}회 중 hook 안 {_HostilePathLike.inside_hook}회",
        )
    )
    if not (thread_local and cross_thread_blocked and hostile_blocked):
        rep.defect(
            "T-77-REENTRANT",
            f"재진입 플래그가 hook 을 우회시킨다 (thread-local={thread_local} "
            f"다른 스레드 차단={cross_thread_blocked} PathLike 차단={hostile_blocked})",
        )

    # ⑺ **가드 기록 ↔ exit 결속 + 프로브/운영 기록 분리** (v2.7, 심판 #2 high).
    # 대상이 `AuditViolation` 을 삼켜도 러너가 red 가 되는지를 실물로 관측한다.
    # 창 **밖**에서 위반을 한 번 만들어야 하므로, 만든 개수를 정확히 알고
    # `claim_operational_records()` 로 이관한다 — 개수가 어긋나면 이관이 성립하지
    # 않아 운영 위반이 대조군 뒤에 숨지 못한다.
    probe_records_before = len(audit_guard.probe_reads)
    with audit_guard.probe_window("t77-separation"):
        try:
            inside = _IO.open(str(_REPO_ROOT / corpus_dirname / "src"))
            getattr(inside, "close", lambda: None)()
        except audit_guard.AuditViolation:
            pass
        except OSError:
            pass
    inside_separated = (
        len(audit_guard.probe_reads) == probe_records_before + 1
        and not audit_guard.blocked_reads
    )

    swallowed = False
    outside_before = len(audit_guard.blocked_reads)
    try:
        # **대상이 예외를 삼키는 상황의 재현** — Case 는 전부 green 인데 가드는
        # 위반을 탐지·기록한 상태다.
        outside = _IO.open(str(_REPO_ROOT / corpus_dirname / "src"))
        getattr(outside, "close", lambda: None)()
    except audit_guard.AuditViolation:
        swallowed = True
    except OSError:
        swallowed = False
    outside_recorded = len(audit_guard.blocked_reads) - outside_before
    gate_fired = bool(guard_record_violations())
    claimed = audit_guard.claim_operational_records(1)
    gate_after_claim = guard_record_violations()
    rep.add(
        Case(
            "T-77-SEPARATION",
            "삼켜진 위반도 exit 에 닿는다 (프로브/운영 기록 분리)",
            inside_separated and outside_before == 0,
            swallowed
            and outside_recorded == 1
            and gate_fired
            and len(claimed) == 1
            and not gate_after_claim,
            f"창 안 기록 분리={inside_separated} · 창 밖 기록 {outside_recorded}건 "
            f"· 삼킨 뒤에도 게이트 발화={gate_fired} · 대조군 이관 {len(claimed)}건 "
            f"→ 잔여 게이트={gate_after_claim or '없음'}",
        )
    )
    if not (gate_fired and swallowed):
        rep.defect(
            "T-77-SEPARATION",
            f"가드 기록이 exit 에 결속되지 않는다 (삼킴={swallowed} "
            f"게이트={gate_fired})",
        )

    # ⑻ **정책 정의역 = 경로명** (v2.7, 심판 #6 medium — 선택지 (B)).
    # `st_dev`/`st_ino` 대조는 보호 대상 집합을 만들 때 코퍼스를 열거해야 해서
    # 그 자체가 OD-3-A 위반이다.  정책을 경로명 차단으로 **명시 축소**하고,
    # 그 축소가 사실인지를 구조(순수 함수)와 값(다른 이름은 통과) 양쪽에서 본다.
    guard_src = ast.parse(sources[audit_path.name])
    judge_fn = next(
        (
            node
            for node in ast.walk(guard_src)
            if isinstance(node, ast.FunctionDef) and node.name == "path_violation"
        ),
        None,
    )
    identity_names = {"stat", "lstat", "st_ino", "st_dev", "samefile", "fstat"}
    identity_used = judge_fn is not None and any(
        (isinstance(node, ast.Name) and node.id in identity_names)
        or (isinstance(node, ast.Attribute) and node.attr in identity_names)
        for node in ast.walk(judge_fn)
    )
    protected_name_blocked = (
        audit_guard.path_violation(str(_HERE / register_name)) is not None
    )
    alias_name_passes = (
        audit_guard.path_violation(str(_HERE / "benign-alias.csv")) is None
    )
    rep.add(
        Case(
            "T-77-INODE",
            "보호 판정의 정의역은 경로명뿐이다 (앵커형)",
            judge_fn is not None and not identity_used,
            protected_name_blocked and alias_name_passes,
            f"판정 함수 실재={judge_fn is not None} · inode 동일성 조회 사용"
            f"={identity_used} · 보호 이름 차단={protected_name_blocked} · "
            f"무해한 이름 통과={alias_name_passes}",
        )
    )

    # --- 한계·범위 (결함 주장 아님) ---------------------------------------
    rep.limit(
        "L-T77-SEAM",
        "T-77-①③ 의 뮤테이션은 검사기의 입력 seam 으로 주입했다 — 실물을 만들면 "
        "그 행위 자체가 OD-3-B/C 위반이기 때문이다.  ② ④ 만 실물 시도다.",
        case="T-77-①",
    )
    rep.limit(
        "L-T77-WRITE-SCOPE",
        "T-77-② 의 monkeypatch 가드는 Python 표준 라이브러리 진입점만 감싼다: "
        f"{', '.join(boundary.GUARDED_ENTRY_POINTS)}. "
        "이미 열린 파일 객체·fd, C 확장의 직접 write, subprocess, 가드 진입 전에 "
        "바인딩된 참조는 덮지 못한다.  감사 hook 이 그 위에 한 층 더 있으나 "
        "fd 표면은 그쪽도 못 본다.  전부 막았다고 적지 않는다.",
    )
    rep.limit(
        "L-READ-SCOPE",
        "T-77-①⒜ monkeypatch 열람 가드의 범위는 다음 진입점이 전부다: "
        f"{', '.join(boundary.READ_GUARDED_ENTRY_POINTS)}. "
        "이미 열린 fd 는 경로를 되돌릴 수 없어 판정 대상이 아니고, C 확장의 직접 "
        "read·subprocess·가드 진입 전 바인딩된 참조도 덮지 못한다.  이 층은 "
        "v2.6 에서 **심층 방어로 격하**됐다 — 정본은 감사 hook 이다.",
    )
    rep.limit(
        "L-AUDIT-SCOPE",
        "감사 hook 이 보는 이벤트는 열거다: 열람 "
        f"{', '.join(audit_guard.READ_EVENTS)} / 쓰기 "
        f"{', '.join(audit_guard.WRITE_EVENTS)}. "
        "`open` 하나가 builtins.open·io.open·os.open·_io.open·_io.FileIO·"
        "open_code 에서 전부 발화한다는 점이 이 열거가 짧아도 되는 이유이고, "
        "그 사실은 방향② 가 실물로 관측한다.  **이미 열린 fd 로의 read/write 는 "
        "어느 층도 보지 못한다** — `os.write(fd, ...)` 에는 감사 이벤트 자체가 "
        "없고 fd 는 경로로 되돌릴 수 없다.  mmap·ctypes 직접 syscall·subprocess 도 "
        "같다.  **경로 인자의 타입도 정의역이다** (v2.7): hook 은 `str`·`bytes`·"
        "표준 `PurePath` 계열·`os.DirEntry` 만 해석하고 그 밖의 객체는 해석하지 "
        "않고 차단한다 — `__fspath__` 는 사용자 콜백이라 hook 안에서 부르면 임의 "
        "코드가 감사 창 안에서 돌기 때문이다.  원시 객체가 hook 까지 그대로 "
        "도달하는 경로는 실측으로 좁혔다: C 구현(`open`·`os.*`)은 이벤트 이전에 "
        "문자열로 접히고, 순수 파이썬 `shutil.*` 계열만 원래 인자를 그대로 "
        "싣는다.  그 축소는 과잉 차단 방향이며 fail-closed 다.",
        case="T-77-AUDIT",
    )
    rep.limit(
        "L-AUDIT-PERSIST",
        "감사 hook 은 설계상 해제할 수 없다.  그래서 install/uninstall 이 아니라 "
        "모듈 레벨 정책 상태를 hook 이 참조하며, 열람·쓰기 정책 둘 다 설치 "
        "시점부터 armed 이고 이 러너는 어느 쪽도 내리지 않는다 "
        f"({audit_guard.policy()['read_armed']}/{audit_guard.policy()['write_armed']}). "
        "그 상태와 프로브 창 깊이는 종료 시점에 운영 게이트가 다시 확인한다 — "
        "정책을 내려놓고 통과하는 경로는 그 게이트에 결속돼 있다.  대가는 이 "
        "프로세스가 파일을 쓸 수 없다는 것이다 — 프로토타입이므로 의도된 대가다.  "
        "`probe_window()` 는 기록만 분리하고 차단은 창 안팎이 같다.  **분류는 "
        "진단 편의가 아니라 exit 결속 여부 그 자체이므로**(v2.7 부터) v2.8 은 창을 "
        "토큰·고정 호출 지점으로 인가하고 인가된 기록의 개수까지 설정에 묶는다.  "
        "이 게이트들이 만드는 findings 도 결국 `exit_status()` 를 경유한다 — "
        "그 종단 한계는 `L-EXIT-ROOT` 다.",
        case="T-77-SEPARATION",
    )
    rep.limit(
        "L-AUDIT-BOOTSTRAP",
        "**'bootstrap 부터 armed' 의 정확한 범위** (v2.8 재작성, 심판 v2.7 #4).  "
        f"hook 은 `{audit_path.name}` 모듈 본문에서 상수 대입과 정의 **직후**에 "
        "설치된다.  설치 시점 `sys.modules` 스냅샷에 피검사 모듈이 없었음을 "
        "검증한다 (스냅샷 크기는 환경에 따라 달라지므로 앵커에 넣지 않는다).  "
        "**v2.7 의 ⒜ 서술 — '두 파일 모두 pre-hook 실행문 0 이 구조 요구사항' — 은 "
        "거짓이었다**: 그 0 은 대입을 우변과 무관하게 비실행으로 세던 분류 규약이 "
        "만든 값이고, 실제로는 호출을 평가하는 대입이 러너 "
        f"{len(runner_prehook['executable'])}건·{audit_path.name} "
        f"{len(audit_prehook['executable'])}건 있다.  **armed 가 아닌 구간은 여전히 "
        "존재한다**: ⑴ 인터프리터 기동과 `site` 처리 ⑵ 러너의 "
        f"`import {audit_path.stem}` **이전** 모듈 본문.  ⑵ 는 세 층으로 고정한다 — "
        "⒜ 실행문 **개수**를 설정 `anchor_prehook_executable` 에 등재해 증감을 red 로 "
        f"만들고 ⒝ 동적 로드·I/O 이름({len(PREHOOK_FORBIDDEN_NAMES)}종)은 "
        "`Name`·`Attribute` 에 더해 **subscript 첨자와 호출 인자의 문자열 상수**까지 "
        "보아 그 자체로 findings 이며 ⒞ 구간 전체의 `ast.unparse` digest 를 설정 핀으로 "
        "둔다.  **그래도 armed 는 아니다** — 이 구간은 고정될 뿐 차단되지 않으며 "
        "`Path(__file__).resolve()` 같은 stat 계열 syscall 은 애초에 감사 이벤트를 "
        "내지 않는다.  ⑶ 다른 진입점이 `proto` 를 먼저 import 한 뒤 이 모듈을 "
        "import 하면 스냅샷 검증이 red 를 내는데, 그것은 **차단이 아니라 사후 검출**이다.  "
        "**v2.9 — ⒜⒝ 의 선언을 실제 정의역으로 축소한다** (심판 v2.8 #3).  ⒜ 의 개수는 "
        "`_statement_executes` 가 보는 **최상위 문장의 우변·데코레이터·기본 인자** 안에서만 "
        "정직하다: `ClassDef` 본문은 import 시 즉시 실행되는데 분류기가 `node.body` 를 "
        "걷지 않으므로, 이 구간에 클래스를 하나 두고 그 본문에서 파일을 열면 개수가 "
        "움직이지 않는다.  ⒝ 의 이름 집합도 닫혀 있어 `FileIO`·`readall` 은 들어 있지 "
        "않다.  **실측**: 러너 pre-hook 구간에 `_io.FileIO(...).readall()` 을 부르는 클래스 "
        "본문을 심으니 실행문 개수는 1(핀과 동일)·동적 이름 findings 는 0 인 채로 hook "
        "설치 **전에** 15,736 바이트를 실제로 읽었다.  그 형태를 red 로 만든 것은 ⒞ 구간 "
        "digest 와 소스 바이트·실행코드 앵커뿐이고, 셋 다 **고정**이지 차단이 아니다 — "
        "값을 함께 갱신하면 지난다.  그러므로 이 구간에 대해 러너가 강제하는 것은 "
        "'실행이 없다' 가 아니라 '바뀌면 설정 diff 를 요구한다' 이다.",
        case="T-77-AUDIT",
    )
    rep.limit(
        "L-AUDIT-PROBE-THREAD",
        "**v2.7 의 이 노트는 거짓이었다** (심판 v2.7 #3).  '차단 자체는 영향이 없고 "
        "분류만 이동한다' 고 적었으나, v2.7 부터 종료 게이트가 `blocked_*` 만 "
        "소비했으므로 **분류 이동은 곧 exit 결속 이탈**이었다.  창 깊이가 프로세스 "
        "전역이라 러너 자신이 창 안에서 워커 스레드를 돌리는 시간대에는 어느 "
        "스레드에서 난 진짜 위반이든 게이트에서 사라졌다.  v2.8 은 셋을 바꿨다: "
        "⑴ 창을 **스레드 지역**으로 옮겼고 ⑵ 토큰과 **고정 호출 지점**"
        f"({', '.join(sorted(audit_guard.PROBE_SITES))})이 일치할 때만 프로브로 "
        "분류하며 — 인가되지 않은 창은 여는 것 자체가 findings 다 — ⑶ 인가된 기록의 "
        "토큰별 (열람, 쓰기) 개수를 설정 `anchor_probe_records` 에 결속했다.  "
        "**남는 것 ⓐ**: 인가된 호출 지점의 소스를 고쳐 그 창 안에서 위반하는 경로는 "
        "코드·설정·앵커를 함께 고치면 통과한다 — 가시화이지 폐쇄가 아니다.  "
        "**남는 것 ⓑ — capability 사칭** (v2.9 등재, 심판 v2.8 #2): 인가 identity 는 "
        f"`PROBE_SITES` 에 평문으로 적힌 토큰({', '.join(sorted(audit_guard.PROBE_SITES))})"
        " 과 호출자 프레임의 `basename(co_filename):co_name` **뿐**이다.  둘 다 "
        "호출자가 정한다 — `compile(src, 'test_contracts.py', 'exec')` 로 표에 적힌 "
        "함수명을 만들면 임의 코드가 인가 판정을 받는다.  게다가 창은 호출자에게 "
        "**가변 `probe_reads` 리스트 자체**를 돌려주고 종료 게이트는 **토큰별 개수만** "
        "센다.  **실측**: 사칭한 창에서 `t77-audit-battery` 기록 한 건을 같은 토큰의 "
        "다른 내용으로 치환하니 `unsanctioned_windows` 는 비었고 토큰별 개수는 "
        "(6,2)/(1,0)/(1,0)/(1,0) 로 불변, `probe_record_violations()` 도 빈 목록이었다 "
        "— 실제로 기록돼 있던 코퍼스 차단 한 건이 조용히 사라졌다.  닫으려면 러너만 "
        "쥐는 불투명 capability, 호출자에게 넘기지 않는 append-only 기록, 정규화된 "
        "내용 digest 가 함께 필요하며 v2.9 는 그것을 만들지 않았다 — 등재만 한다.",
    )
    rep.limit(
        "L-INODE-ALIAS",
        "**정책 정의역은 경로명이다** (심판 #6 — 선택지 (B) 를 골랐다).  "
        "`path_violation` 은 해석된 경로명의 순수 함수이며 `st_dev`/`st_ino` 를 "
        "보지 않는다.  따라서 보호 대상의 **기존 hardlink** 가 무해한 이름을 갖고 "
        "있으면 `resolve()` 로 원본 이름이 복원되지 않아 같은 inode 를 다른 "
        "이름으로 열 수 있다 — 실행 중 `os.link` 차단은 **이미 준비된** 별칭을 "
        "막지 못한다.  선택지 (A)(canonical `st_dev`/`st_ino` 집합 대조)를 "
        "고르지 않은 이유는 명확하다: 보호 대상 identity 집합을 만들려면 코퍼스 "
        "디렉터리를 열거해야 하고 **그 열거 자체가 OD-3-A 가 금지하는 행위**다.  "
        "정책을 넓히는 대신 축소해 적는다.  같은 이유로 심볼릭 링크 이외의 별칭 "
        "(bind mount·별도 마운트 지점)도 정의역 밖이다.",
        case="T-77-INODE",
    )
    rep.limit(
        "L-CASEFOLD",
        "경로 동치 판정은 casefold 정규화다.  APFS 같은 case-insensitive "
        "파일시스템에서 대소문자만 다른 코퍼스 경로가 통과하던 것을 막는다.  "
        "case-sensitive 파일시스템에서는 이름만 같고 실제로 다른 디렉터리까지 "
        "차단하는 과잉 차단이 되는데, fail-closed 방향이므로 그대로 둔다.  "
        "유니코드 정규화(NFC/NFD)까지는 접지 않는다.",
    )
    rep.limit(
        "L-LOCATE-FORGE",
        "T-77-④ 는 표지를 `.git` 로 좁히고 예상 상대경로의 실물이 실행 중인 "
        "러너와 같은 파일인지(`os.path.samefile`) 확인한다.  v2.7 은 여기에 "
        "`.git` 의 **의미 검증**을 더한다 — 디렉터리형은 "
        f"{', '.join(boundary.GIT_DIR_REQUIRED)} 를, 파일형은 gitdir 포인터와 그 "
        "대상의 `HEAD` 를 요구하고, 러너에서 위로 올라가 만나는 실제 repository "
        "top-level 이 기대 루트와 같은지도 본다.  **v2.6 의 서술은 위조 비용을 "
        "과대 서술했다**: 당시 검사는 `exists()` 뿐이라 `.git` **디렉터리**가 "
        "아니라 **빈 `.git` 파일 하나**면 통과했다.  지금도 폐쇄는 아니다 — "
        "유효한 `.git` 구조 한 벌(디렉터리형이면 세 항목, 파일형이면 포인터와 "
        "`HEAD`)을 만들고 러너 사본을 예상 상대경로에 두면 통과한다.  비용을 "
        "1 파일에서 구조 1 벌로 올릴 뿐이며, 위치 앵커는 *이동* 을 관측하는 "
        "장치이지 적대적 준비를 이기는 장치가 아니다.",
        case="T-77-④-GIT",
    )
    rep.limit(
        "L-T77-DE",
        "T-77 이 검사하는 것은 OD-3 의 A·B·C 뿐이다.  "
        "D(CI 미편입)·E(D0 승격 금지)에는 기계 검사가 없다 — 사람이 지켜야 한다.",
    )
    rep.limit(
        "L-T77-DOMAIN",
        f"스캔 도메인 = proto/*.py · proto/*.yaml · 이 러너({runner_path.name}) · "
        f"{audit_path.name} 해서 {len(sources)}개: {sorted(sources)}.  "
        f"**이 러너와 {audit_path.name} 은 `proto/` 밖에 있다** "
        f"({runner_path.relative_to(_REPO_ROOT)}).  같은 디렉터리의 다른 스파이크 "
        "도구는 스캔 도메인 밖이다.",
    )


# --- 우선순위 2 -------------------------------------------------------------


def t61_reason_membership_move(cfg, rep: Report) -> None:
    """T-61 — blocks_gate G2→G3 이동 시 id 가 두 사유 집합 사이를 실제로 이동."""
    rows = register.fixture_rows()
    registry = gates.build_gate_registry()
    inputs = register.fixture_inputs()
    target = "PROTO-UNCHK-004"

    before = gates.evaluate(registry, inputs, rows)
    moved_rows = register.rows_replacing(rows, target, blocks_gate="G3")
    after = gates.evaluate(registry, inputs, moved_rows)
    left_g2 = target in before.reasons["G2"] and target not in after.reasons["G2"]
    entered_g3 = target not in before.reasons["G3"] and target in after.reasons["G3"]
    clean_green = left_g2 and entered_g3

    broken_after = gates.evaluate(
        registry,
        inputs,
        moved_rows,
        reasons_builder=gates.build_reasons_ignoring_blocks_gate,
    )
    broken_left = target not in broken_after.reasons["G2"]
    mutant_red = not broken_left

    rep.add(
        Case(
            "T-61",
            "사유 집합 멤버십 이동",
            clean_green,
            mutant_red,
            f"G2 이탈={left_g2} G3 진입={entered_g3} "
            f"blocks_gate 무시 구현 이탈={broken_left}",
        )
    )


def t70_reason_separation(cfg, rep: Report) -> None:
    """T-70 — 서로 다른 게이트의 사유 집합이 동일하면 실패."""
    ctx = enforcement.build_context(cfg)
    clean = enforcement._check_u8a(ctx)
    broken_ctx = enforcement.build_context(
        cfg, reasons_builder=gates.build_reasons_ignoring_blocks_gate
    )
    mutant = enforcement._check_u8a(broken_ctx)
    rep.add(
        Case(
            "T-70",
            "게이트별 사유 집합 분리",
            not clean,
            bool(mutant),
            f"clean={clean} mutant={len(mutant)}건",
        )
    )


def t68_blocks_gate_target(cfg, rep: Report) -> None:
    """T-68 — 정의되지 않은 게이트 거부 + 허용 집합이 **종류(kind)** 로 파생되는가.

    교정 2 의 양방향 대조군: 두 번째 AUTHORITY 게이트(G6)를 넣었을 때
    ① 허용 집합에 포함되지 않아야 하고 ② `blocks_gate=G6` 행이 검출돼야 한다.
    """
    rows = register.rows_replacing(
        register.fixture_rows(), "PROTO-UNCHK-004", blocks_gate="Phase 4"
    )
    base_registry = gates.build_gate_registry()
    rejected = register.check_u8b(rows, base_registry)

    # 완료 게이트를 더하면 허용 집합이 자동 확대되는가
    widened = gates.build_gate_registry()
    widened["G5"] = gates.Gate("G5", gates.COMPLETION, ())
    rows_g5 = register.rows_replacing(
        register.fixture_rows(), "PROTO-UNCHK-004", blocks_gate="G5"
    )
    before_widen = register.check_u8b(rows_g5, base_registry)
    after_widen = register.check_u8b(rows_g5, widened)
    auto_widened = bool(before_widen) and not after_widen

    g4_excluded = "G4" not in gates.allowed_blocks_gate(base_registry)

    # **두 번째 권한 게이트** — id 리터럴 제외라면 여기서 새어나간다.
    authority = gates.build_gate_registry()
    authority["G6"] = gates.Gate("G6", gates.AUTHORITY, ())
    g6_excluded = "G6" not in gates.allowed_blocks_gate(authority)
    rows_g6 = register.rows_replacing(
        register.fixture_rows(), "PROTO-UNCHK-004", blocks_gate="G6"
    )
    g6_detected = bool(register.check_u8b(rows_g6, authority))

    rep.add(
        Case(
            "T-68",
            "blocks_gate target 실재 + 허용집합 종류 파생",
            auto_widened and g4_excluded and g6_excluded,
            bool(rejected) and g6_detected,
            f"`Phase 4` 거부={bool(rejected)} 자동확대={auto_widened} "
            f"G4 제외={g4_excluded} · 두 번째 권한 게이트 G6 제외={g6_excluded} "
            f"G6 행 검출={g6_detected}",
        )
    )
    if not (g6_excluded and g6_detected):
        rep.defect(
            "T-68",
            "두 번째 권한 게이트 G6 가 허용 집합에 새어 들어간다 "
            f"(제외={g6_excluded} 검출={g6_detected}) — 제외 기준이 종류가 아니다",
        )


def t67_metric_movement(cfg, rep: Report) -> None:
    """T-67 — 4 지표 각각이 **고유** 뮤테이션에 반응하는가."""
    rows = register.fixture_rows()
    evidence = register.fixture_evidence()
    base = register.metrics(rows, evidence, cfg)

    mutations: dict[str, tuple[tuple, tuple]] = {
        register.METRIC_SUPERSET: (
            rows,
            (
                floor.EvidenceRow(
                    "PROTO-EV-001",
                    "READY",
                    "EV-L1",
                    frozenset({"PACKAGE", "TEST", "FAULT", "RUNTIME"}),
                ),
                *evidence[1:],
            ),
        ),
        register.METRIC_IMPRECISE: (
            register.rows_replacing(rows, "PROTO-UNCHK-003", owner_track="Phase 3-5"),
            evidence,
        ),
        register.METRIC_BLANK_REF: (
            register.rows_replacing(rows, "PROTO-UNCHK-004", normative_ref=""),
            evidence,
        ),
        register.METRIC_CLOSABLE_NO: (
            register.rows_replacing(rows, "PROTO-UNCHK-003", closable="NO"),
            evidence,
        ),
    }

    moved: list[str] = []
    cross_talk: list[str] = []
    for metric_name, (m_rows, m_evidence) in mutations.items():
        mutated = register.metrics(m_rows, m_evidence, cfg)
        if mutated[metric_name] == base[metric_name] + 1:
            moved.append(metric_name)
        others = [
            name
            for name in register.REQUIRED_METRICS
            if name != metric_name and mutated[name] != base[name]
        ]
        if others:
            cross_talk.append(f"{metric_name}->{others}")

    # 지표 **목록 자체**를 설정에 묶는다 (v2.6, 심판 F1).  v2.5 는 `len(moved)==4`
    # 라는 리터럴만 봤고 `REQUIRED_METRICS` 는 코드에만 있었다 — 목록을 4→2 로
    # 줄이면 U-10 노출 검사(`check_u10`)가 조용히 좁아지는데 대조군이 침묵했다.
    declared_metrics = config.cfg_list(dict(cfg), "declared_required_metrics")
    metrics_declared_ok = sorted(register.REQUIRED_METRICS) == sorted(
        declared_metrics
    ) and sorted(base) == sorted(declared_metrics)
    # 항목 하나를 빼면 반드시 관측되는가 — 각 인덱스를 빼 본다.
    metric_shrink_detected = [
        index
        for index in range(len(register.REQUIRED_METRICS))
        if sorted(
            register.REQUIRED_METRICS[:index] + register.REQUIRED_METRICS[index + 1 :]
        )
        != sorted(declared_metrics)
    ]
    rep.add(
        Case(
            "T-67",
            "U-10 지표 고유 뮤테이션 반응 + 목록 등재",
            all(v >= 0 for v in base.values()) and metrics_declared_ok,
            len(moved) == len(declared_metrics)
            and not cross_talk
            and len(metric_shrink_detected) == len(register.REQUIRED_METRICS),
            f"기준값={base} 이동={moved} 교차반응={cross_talk or '없음'} · "
            f"등재 {len(declared_metrics)}개 일치={metrics_declared_ok} · "
            f"1 개 삭제 검출 {len(metric_shrink_detected)}/"
            f"{len(register.REQUIRED_METRICS)}",
        )
    )
    if cross_talk:
        rep.defect("T-67", f"지표가 직교하지 않는다 — 교차 반응 {cross_talk}")
    if not metrics_declared_ok:
        rep.defect(
            "T-67",
            f"REQUIRED_METRICS {sorted(register.REQUIRED_METRICS)} 가 설정 등재 "
            f"{sorted(declared_metrics)} 와 다르다",
        )


def fwd_a_0_superset_closure(cfg, rep: Report) -> None:
    """FWD-a-0 — floor 밖 kind 를 얹어도 판정이 안 바뀌는가 (superset 우회 폐쇄)."""
    lean = floor.EvidenceRow("PROTO-EV-004", "READY", "EV-L3", frozenset({"RUNTIME"}))
    padded = floor.EvidenceRow(
        "PROTO-EV-004", "READY", "EV-L3", frozenset({"RUNTIME", "PACKAGE", "TEST"})
    )

    v20_lean = floor.fwd_a_0_satisfied(lean)
    v20_padded = floor.fwd_a_0_satisfied(padded)
    closure_holds = (v20_lean is False) and (v20_padded is False)

    v19_lean = floor.fwd_a_0_satisfied(lean, use_floor=False)
    v19_padded = floor.fwd_a_0_satisfied(padded, use_floor=False)
    bypass_existed = (v19_lean is False) and (v19_padded is True)

    rep.add(
        Case(
            "FWD-a-0",
            "floor 한정으로 superset 우회 폐쇄",
            closure_holds,
            bypass_existed,
            f"v2.0(lean={v20_lean}, padded={v20_padded}) "
            f"v1.9(lean={v19_lean}, padded={v19_padded})",
        )
    )


# --- 우선순위 3 -------------------------------------------------------------


def t11_inv_c4(cfg, rep: Report) -> None:
    """T-11 — NMC 술어의 기여값을 MET 으로 변형하면 기여 벡터가 바뀌는가."""
    registry = gates.build_gate_registry()
    rows = register.fixture_rows()
    inputs = register.fixture_inputs()
    base = gates.evaluate(registry, inputs, rows)
    mutated = gates.evaluate(registry, inputs, rows, fold={gates.NMC: gates.MET})
    nmc_pids = [
        p.pid
        for gid in gates.completion_gates(registry)
        for p in registry[gid].predicates
        if p.classification == gates.NMC
    ]
    changed = [
        pid
        for pid in nmc_pids
        if base.contributions[pid][0] != mutated.contributions[pid][0]
    ]
    verdict_changed = mutated.verdict != base.verdict
    rep.add(
        Case(
            "T-11",
            "INV-C4 기여 벡터 관측",
            all(base.contributions[pid][0] == gates.NOT_MET for pid in nmc_pids),
            len(changed) == len(nmc_pids),
            f"NMC {len(nmc_pids)}개 중 {len(changed)}개 이동 · "
            f"게이트 verdict 이동={verdict_changed}",
        )
    )


def t39_enforcement_registry(cfg, rep: Report) -> None:
    """T-39 — 강제 지점 레지스트리 전 키를 하나씩 제거하면 매 키마다 red 인가."""
    reg = enforcement.build_registry()
    cases = enforcement.violating_contexts(cfg)
    missing = sorted(set(reg) - set(cases))
    reds: list[str] = []
    greens_after_skip: list[str] = []
    contaminated: list[str] = []
    for key, ctx in cases.items():
        findings = enforcement.run_check(ctx)
        hit = {f.contract_id for f in findings}
        if key in hit:
            reds.append(key)
        if hit - {key}:
            contaminated.append(f"{key}->{sorted(hit - {key})}")
        if not enforcement.run_check(ctx, skip=frozenset({key})):
            greens_after_skip.append(key)

    baseline_ctx = enforcement.build_context(cfg)
    baseline_findings = enforcement.run_check(baseline_ctx)
    canary = enforcement.key_count_canary(cfg)

    rep.add(
        Case(
            "T-39",
            "강제 지점 전수 (우주 = 레지스트리 키)",
            not baseline_findings and not canary and not missing,
            len(reds) == len(reg) and len(greens_after_skip) == len(reg),
            f"키 {len(reg)}개 {sorted(reg)} · red {len(reds)} · "
            f"제거후 green {len(greens_after_skip)} · 오염 {contaminated or '없음'} "
            f"· 기준선 위반 {baseline_findings} · 컨텍스트 누락 {missing or '없음'}",
        )
    )
    if missing or contaminated:
        rep.defect(
            "T-39",
            f"레지스트리 키와 뮤테이션 컨텍스트가 어긋난다 "
            f"(누락={missing} 오염={contaminated})",
        )


def t76_level_raw_anchor(cfg, rep: Report) -> None:
    """T-76 — floor 입력(레벨 원시값 · 레벨→kind 매핑)이 강제 레지스트리에 있는가.

    교정 3.  이 앵커가 레지스트리 밖이면 floor 입력 조작이 검출되지 않는다.
    """
    reg = enforcement.build_registry()
    check = getattr(enforcement, "_check_t76", None)
    registered = "T-76" in reg

    if check is None or not registered:
        rep.add(
            Case(
                "T-76",
                "floor 입력 원시값 앵커",
                False,
                False,
                f"강제 레지스트리 등록={registered} · 검사 함수 존재={check is not None}"
                f" · 레지스트리 키 {len(reg)}개",
            )
        )
        rep.defect(
            "T-76",
            "레벨 원시값 앵커가 강제 레지스트리 밖이라 floor 입력 조작이 검출되지 않는다",
        )
        return

    ctx = enforcement.build_context(cfg)
    clean = check(ctx)
    canary = enforcement.key_count_canary(cfg)
    clean_green = not clean and not canary

    # 변형 ① — 임의 행의 `minimum_evidence_level` 을 바꾼다
    mutated_evidence = tuple(
        (
            floor.EvidenceRow(row.evidence_id, row.status, "EV-L2", row.required_kinds)
            if row.evidence_id == "PROTO-EV-003"
            else row
        )
        for row in register.fixture_evidence()
    )
    row_red = bool(check(enforcement.build_context(cfg, evidence=mutated_evidence)))

    # 변형 ② — 심판이 실제로 심은 뮤테이션: L3 floor 에 PACKAGE 를 추가한다
    original = floor.LEVEL_KINDS
    padded = floor.EvidenceRow(
        "PROTO-EV-004", "READY", "EV-L3", frozenset({"RUNTIME", "PACKAGE", "TEST"})
    )
    baseline_padded = floor.fwd_a_0_satisfied(padded)
    try:
        floor.LEVEL_KINDS = {**original, 3: frozenset(original[3] | {floor.PACKAGE})}
        mapping_red = bool(check(ctx))
        padded_passes = floor.fwd_a_0_satisfied(padded)
    finally:
        floor.LEVEL_KINDS = original

    mutant_red = row_red and mapping_red
    rep.add(
        Case(
            "T-76",
            "floor 입력 원시값 앵커",
            clean_green,
            mutant_red,
            f"레지스트리 키 {len(reg)}개 · 행 레벨 변경 red={row_red} · "
            f"LEVEL_KINDS 변경 red={mapping_red} (그 뮤테이션에서 padded EV-L3 의 "
            f"FWD-a-0 통과 {baseline_padded}->{padded_passes})",
        )
    )
    if not mutant_red:
        rep.defect(
            "T-76",
            f"floor 입력 조작이 검출되지 않는다 "
            f"(행 레벨={row_red} LEVEL_KINDS={mapping_red})",
        )
    rep.limit(
        "L-T76-ANCHOR",
        "T-76 이 고정하는 것은 floor() 의 **입력** 두 가지다: 픽스처 행의 레벨 "
        "원시값 분포와 레벨→kind 매핑.  floor() 계산 규칙 자체의 재작성이나 "
        "`VERIFIABLE_KINDS` 변경은 이 앵커 밖이다.",
    )


def unchk_019_registry_omission(cfg, rep: Report) -> None:
    """UNCHK-019 — 등록을 빠뜨린 계약은 우주에 없다 (count canary 는 침묵)."""
    reg = enforcement.build_registry()
    canary_before = enforcement.key_count_canary(cfg)

    # 계약을 하나 새로 쓰되 레지스트리에 등록하지 않는다.
    def _unregistered_contract(ctx: enforcement.Context) -> list[str]:
        return ["등록되지 않은 계약이 관측을 냈다"]

    violating_ctx = enforcement.build_context(cfg)
    unregistered_findings = enforcement.run_check(violating_ctx, registry=reg)
    silent = not unregistered_findings and not canary_before
    would_have_fired = bool(_unregistered_contract(violating_ctx))

    shrunk = dict(reg)
    shrunk.pop("U-4")
    deletion_detected = config.cfg_int(
        dict(cfg), "anchor_enforcement_key_count"
    ) != len(shrunk)

    rep.add(
        Case(
            "UNCHK-019",
            "등록 누락은 우주 밖이다 (앵커형)",
            deletion_detected,
            silent and would_have_fired,
            f"삭제는 count canary 가 검출={deletion_detected} · 등록 누락은 침묵"
            f"={silent} (그 계약 자체는 관측을 냈다={would_have_fired}) · "
            f"레지스트리 키 {len(reg)}개",
        )
    )
    rep.limit(
        "L-UNCHK019-CANARY",
        "UNCHK-019 는 구조적 이연 항목이다.  count canary 는 키 **삭제**만 잡고 "
        "새 계약의 **등록 누락**은 잡지 못한다 — 이 앵커형 Case 는 그 사실이 "
        "바뀌면 red 가 되어 재검토를 강제한다.",
        case="UNCHK-019",
    )


def u8b_kind_exclusion(cfg, rep: Report) -> None:
    """U-8b — 허용 집합의 제외 기준이 id 리터럴이 아니라 **종류(kind)** 인가 (교정 2)."""
    base_registry = gates.build_gate_registry()
    base_allowed = gates.allowed_blocks_gate(base_registry)
    base_expected = frozenset(
        gid for gid, gate in base_registry.items() if gate.kind == gates.COMPLETION
    )
    base_ok = base_allowed == base_expected

    registry = gates.build_gate_registry()
    registry["G6"] = gates.Gate("G6", gates.AUTHORITY, ())
    allowed = gates.allowed_blocks_gate(registry)
    expected = frozenset(
        gid for gid, gate in registry.items() if gate.kind == gates.COMPLETION
    )
    kind_derived = allowed == expected

    rep.add(
        Case(
            "U-8b",
            "허용 집합 제외 기준 = 종류(kind)",
            base_ok,
            kind_derived,
            f"기준 허용집합={sorted(base_allowed)} · 권한 게이트 2 개일 때 "
            f"허용집합={sorted(allowed)} 기대={sorted(expected)}",
        )
    )
    if not kind_derived:
        rep.defect(
            "U-8b",
            "허용 집합이 `keys() − {G4}` 라 두 번째 권한 게이트가 자동 포함된다 — "
            "리터럴 목록을 리터럴 단일 제외로 바꾼 것이지 INV-C1 을 종류로 강제한 "
            "것이 아니다",
        )


def t71_distribution_anchor(cfg, rep: Report) -> None:
    """T-71 — §4.2.1 분류 분포 앵커."""
    ctx = enforcement.build_context(cfg)
    clean = enforcement._check_t71(ctx)
    mutated_ctx = enforcement.violating_contexts(cfg)["T-71"]
    mutant = enforcement._check_t71(mutated_ctx)
    rep.add(
        Case(
            "T-71",
            "분류 분포 앵커",
            not clean,
            bool(mutant),
            f"기준 분포={gates.classification_distribution(ctx.registry)} mutant={mutant}",
        )
    )


def t72_range_noblock_but_counted(cfg, rep: Report) -> None:
    """T-72 — 범위형은 차단하지 않되 계수된다 (양방향)."""
    rows = register.rows_replacing(
        register.fixture_rows(), "PROTO-UNCHK-003", owner_track="Phase 3-5"
    )
    blocked = register.check_u1a(rows, cfg)
    counted = register.metrics(rows, register.fixture_evidence(), cfg)[
        register.METRIC_IMPRECISE
    ]
    base_counted = register.metrics(
        register.fixture_rows(), register.fixture_evidence(), cfg
    )[register.METRIC_IMPRECISE]
    rep.add(
        Case(
            "T-72",
            "범위형 비차단 + 계수",
            not blocked,
            counted == base_counted + 1,
            f"차단={blocked} 계수 {base_counted}->{counted}",
        )
    )


def t73_metric_exposure(cfg, rep: Report) -> None:
    """T-73 — 4 지표가 생성물에 전문 노출되는가."""
    ctx = enforcement.build_context(cfg)
    clean = enforcement._check_u10(ctx)
    stale = dict(ctx.report)
    stale.pop(register.METRIC_SUPERSET)
    mutant = enforcement._check_u10(ctx.replaced(report=stale))
    rep.add(
        Case(
            "T-73",
            "U-10 지표 생성물 노출",
            not clean,
            bool(mutant),
            f"노출 키={sorted(ctx.report)} mutant={mutant}",
        )
    )


def t74_closable_transition_anchor(cfg, rep: Report) -> None:
    """T-74 — `closable` YES→NO 전이가 앵커를 red 로 만드는가."""
    ctx = enforcement.build_context(cfg)
    clean = enforcement._check_u9a(ctx)
    mutated = enforcement.violating_contexts(cfg)["U-9a"]
    mutant = enforcement._check_u9a(mutated)
    rep.add(
        Case(
            "T-74",
            "closable YES→NO 전이 앵커",
            not clean,
            bool(mutant),
            f"clean={clean} mutant={mutant}",
        )
    )


def floor_parsing_aborts(cfg, rep: Report) -> None:
    """T-47/T-48 계열 — 파싱 실패는 중단이지 기본값이 아니다."""
    same = floor.floor("EV-L0/1") == floor.floor("EV-L0/L1")
    aborted = 0
    for bad in ("EV-L9", "EV-L", "언젠가", ""):
        try:
            floor.floor(bad)
        except floor.LevelSyntaxError:
            aborted += 1
    profile_blocks = False
    try:
        floor.floor("Profile-dependent")
    except floor.ProfileDependentError:
        profile_blocks = True
    rep.add(
        Case(
            "T-47/48",
            "레벨 파싱 정규화 + fail-closed",
            same and profile_blocks,
            aborted == 4,
            f"L0/1==L0/L1={same} 중단 {aborted}/4 Profile-dependent 차단={profile_blocks}",
        )
    )


# --- 자기 검사 (교정 1) -----------------------------------------------------


def collect_self_checks(
    rep: Report,
    declared_limits: Sequence[str],
    unchk_ids: Sequence[str],
    waivers: Sequence[str],
    digest_drift: Sequence[str],
) -> dict[str, list]:
    """SELF-1 의 **명명된 검사 결과** — 구성 지점은 여기 하나뿐이다 (v2.6).

    v2.5 는 `clean_green` 을 손으로 쓴 불리언식으로 조립했고, `mutant_red` 는
    합성 `probe` 에서만 계산됐다.  **두 값이 독립**이었으므로 소비 항을 하나
    지워도 방향② 는 성립한 채 남았다 — 심판이 그 상태로 실제 미등재 노트를
    exit 0 으로 통과시킨 것을 재현했다(F1).

    이름 있는 dict 로 바꾸면 소비는 `any(...)` 한 곳으로 모이고, **이름 집합
    자체를 설정에 등재**해 항을 통째로 지우는 편집이 red 가 된다.  각 이름이
    실제로 소비되는지는 `SELF-2` 가 전수 관측한다.
    """
    return {
        "unbound": rep.unbound_defects(),
        "green_bound": rep.green_bound_defects(),
        "undeclared": rep.undeclared_limits(declared_limits),
        "missing": rep.missing_limits(declared_limits),
        "duplicated": rep.duplicate_limits(),
        "unresolved": rep.unresolved_limit_refs(unchk_ids),
        "parked": rep.parked_limits(unchk_ids, waivers),
        "digest_drift": list(digest_drift),
    }


def format_checks(checks: dict[str, list]) -> str:
    """SELF-1 detail 용 요약.

    **앵커 상태에 의존하지 않는다.**  detail 이 앵커 값에 의존하면 Case 산문
    앵커가 자기 꼬리를 물어 수렴하지 않는다.  드리프트는 `main()` 의 앵커 대조
    줄이 그대로 보고하며, 소비는 `digest_drift` 항이 `clean_green` 안에서 한다.
    """
    return " ".join(
        f"{name}={len(values)}"
        for name, values in sorted(checks.items())
        if name != "digest_drift"
    )


def self_check_green(checks: dict[str, list], names_match: bool) -> bool:
    """SELF-1 방향① 의 **유일한** 판정 지점.

    `names_match` 는 `checks` 의 키 집합이 설정의 `declared_self_checks` 와
    정확히 일치하는지다 — 항을 지우면 여기서 red 가 된다.
    """
    return names_match and not any(checks.values())


def self_check_probes(
    unchk_ids: Sequence[str],
) -> dict[str, tuple[Report, tuple[str, ...], tuple[str, ...]]]:
    """검사 이름마다 **실제 위반을 심은 Report** 와 그 인자 (v2.7, 심판 #1 critical).

    v2.6 의 SELF-2 는 `collect_self_checks()` 의 **키만** 가져와 각 키에 합성
    값을 주입했다.  그래서 producer 가 실제 값을 `[]` 로 버려도 방향② 가
    성립했다 — 자기충족 결함의 표면 이동이었다.

    여기서는 각 이름마다 그 검사 **하나만** 발화하는 실제 `Report` 를 만들고,
    그것을 `collect_self_checks()` 에 **통과시켜** 관측한다.  producer 를
    무력화하면 해당 이름의 결과가 비어 red 가 된다.

    반환값: 이름 -> (report, declared_limits, drift)
    """

    def _base() -> Report:
        report = Report()
        report.add(Case("P-OK", "정상 Case", True, True))
        report.limit("L-P", "등재된 정상 노트")
        return report

    probes: dict[str, tuple[Report, tuple[str, ...], tuple[str, ...]]] = {}

    # unbound — Case 가 없는 tid 에 붙은 발견
    unbound = _base()
    unbound.defect("<없는 Case>", "심은 발견")
    probes["unbound"] = (unbound, ("L-P",), ())

    # green_bound — green Case 에 붙은 발견
    green_bound = _base()
    green_bound.defect("P-OK", "green Case 에 붙인 발견")
    probes["green_bound"] = (green_bound, ("L-P",), ())

    # undeclared — 설정에 없는 노트
    undeclared = _base()
    undeclared.limit("L-EXTRA", "등재되지 않은 노트")
    probes["undeclared"] = (undeclared, ("L-P",), ())

    # missing — 등재됐는데 방출되지 않은 노트
    probes["missing"] = (_base(), ("L-P", "L-ABSENT"), ())

    # duplicated — 같은 lid 재사용
    duplicated = _base()
    duplicated.limit("L-P", "같은 lid 로 숨긴 두 번째 노트")
    probes["duplicated"] = (duplicated, ("L-P",), ())

    # unresolved — 실재하지 않는 Case 를 가리키는 노트
    unresolved = _base()
    unresolved.limit("L-REF", "실재하지 않는 Case 참조", case="<없는 Case>")
    probes["unresolved"] = (unresolved, ("L-P", "L-REF"), ())

    # parked — 결함 어휘를 green Case 에 주차한 노트
    parked = _base()
    parked.limit("L-PARK", "결함이 생존한다", case="P-OK")
    probes["parked"] = (parked, ("L-P", "L-PARK"), ())

    # digest_drift — producer 가 인자 자체이므로 실제 drift 는 `SELF-3` 이
    # `main()` 배선 쪽에서 **독립**으로 결속한다.  여기서는 소비만 본다.
    probes["digest_drift"] = (_base(), ("L-P",), ("<앵커 드리프트>",))
    return probes


def self_check_consumption(cfg, rep: Report) -> None:
    """SELF-2 — 각 검사 항이 **실제 producer 를 거쳐** 판정에 닿는가 (v2.7).

    심판 v2.6 지적: 방향② 가 합성 dict 만 봤다.  v2.7 은 이름마다 **양성
    대조군**(실제 `Report` 위반)을 `collect_self_checks()` 에 통과시켜 두 가지를
    동시에 관측한다:
      ⒜ **producer 생산**: 그 이름의 결과가 비어 있지 않다 (producer 가 값을
         버리면 여기서 red 가 된다)
      ⒝ **소비**: 그 상태에서 `self_check_green(...)` 이 False 다
    덤으로 ⒞ **직교성**: 심은 이름 외의 항은 전부 비어 있다.

    검사 dict 는 `SELF-1` 과 **같은 구성 지점**(`collect_self_checks`)에서 온다
    — 다른 곳에서 다시 조립하면 그 사본이 곧 다음 간극이다.
    """
    declared = config.cfg_list(dict(cfg), "declared_self_checks")
    unchk_ids = tuple(row.id for row in register.fixture_rows())
    checks = collect_self_checks(
        rep,
        config.cfg_list(dict(cfg), "declared_limit_ids"),
        unchk_ids,
        config.cfg_list(dict(cfg), "limit_vocabulary_waivers"),
        (),
    )
    names_match = sorted(checks) == sorted(declared)
    empty = {name: [] for name in checks}
    baseline_green = self_check_green(empty, True)

    probes = self_check_probes(unchk_ids)
    probes_cover = sorted(probes) == sorted(checks)

    produced: list[str] = []
    consumed: list[str] = []
    silent: list[str] = []
    ignored: list[str] = []
    cross_talk: list[str] = []
    for name in sorted(checks):
        if name not in probes:
            silent.append(name)
            continue
        probe_rep, probe_declared, probe_drift = probes[name]
        observed = collect_self_checks(
            probe_rep, probe_declared, unchk_ids, (), probe_drift
        )
        if observed.get(name):
            produced.append(name)
        else:
            silent.append(name)
        if self_check_green(observed, True):
            ignored.append(name)
        else:
            consumed.append(name)
        noisy = sorted(
            other for other, values in observed.items() if other != name and values
        )
        if noisy:
            cross_talk.append(f"{name}->{noisy}")
    # 이름 집합 불일치 자체도 소비되는가 — 항 삭제를 잡는 층이다.
    name_guard = not self_check_green(empty, False)

    rep.add(
        Case(
            "SELF-2",
            "검사 항의 producer 생산 + 소비 전수 검증",
            names_match and baseline_green and probes_cover,
            len(produced) == len(checks)
            and len(consumed) == len(checks)
            and not silent
            and not ignored
            and not cross_talk
            and name_guard,
            f"등재 {len(declared)}개 ↔ 실제 {sorted(checks)} 일치={names_match} · "
            f"양성 대조군 {len(probes)}개 덮음={probes_cover} · "
            f"producer 생산 {len(produced)}/{len(checks)} (침묵={silent or '없음'}) · "
            f"소비 {len(consumed)}/{len(checks)} (무시={ignored or '없음'}) · "
            f"교차반응={cross_talk or '없음'} · 이름 불일치 소비={name_guard}",
        )
    )
    if silent or ignored or not names_match or not probes_cover:
        rep.defect(
            "SELF-2",
            f"검사 항이 producer 를 거치지 않거나 소비되지 않는다 "
            f"(침묵={silent} 무시={ignored} 등재일치={names_match} "
            f"대조군덮음={probes_cover})",
        )


def self_exit_wiring(cfg, rep: Report) -> None:
    """SELF-3 — 발견 채널 3 종이 **exit 결정에 배선**됐는가 (v2.7, 심판 #1/#2).

    v2.6 에서 앵커 드리프트는 `collect_self_checks()` 의 **단일 항** 하나만
    거쳐 exit 에 닿았고, 가드 기록은 아예 닿지 않았다.  여기서는 종료 코드
    결정을 `exit_status()` 한 곳으로 모으고 ⒜ 세 채널이 실제로 그리로 들어가는지
    를 **이 파일의 AST 에서 파생**해 관측하며 ⒝ 각 채널이 단독으로 판정을
    뒤집는지를 전수 확인한다.

    **이 Case 가 관측하지 못하는 것** (v2.8, 심판 v2.7 critical): 배선의
    *실재* 는 보지만 배선된 함수의 *동작* 은 보지 않는다.  그리고 이 Case 가
    red 를 내더라도 그 red 는 다시 `exit_status()` 를 경유해 종료 코드가 된다.
    같은 프로세스 안에서는 이 회귀가 끝나지 않는다 — `L-EXIT-ROOT` 참조.

    **v2.9 (심판 v2.8 #5)**: 이연 검사가 설정 `required_deferrals` 의 각 항이
    `deferred_owner_tracks` 에 **같은 값으로** 있는지를 본다.  그 map 은 운영자
    처분에서 파생한 값이며 `REQUIRED_KEYS` 에 있어 부재 자체가 중단이다.
    owner-track 문법은 새 검사기를 만들지 않고 `register.classify_owner_track` 을
    재사용한다.  트랙 값은 이 러너의 산문에 리터럴로 적지 않고 검증된 설정에서
    파생한다 — 선언과 평가가 갈리지 않게.

    **이 이연 검사가 강제하는 명제** (v2.9 후속 주장 축소, 독립 검증자 실측):
    ⑴ 두 설정 줄의 **상호 일치** ⑵ owner-track **문법** ⑶ 대상 노트가
    `declared_limit_ids` 에 **등재돼 있음** — 이 셋뿐이다.  **처분 값 자체는
    강제하지 않는다**: 두 줄을 함께 다른 트랙으로 옮기면 이 Case 는 green 이다
    (실측: 둘 다 `Phase 5` 로 옮겨도 `SELF-3` green — 값을 잡은 것은 방출 산문
    앵커 하나이고 그 산문도 함께 재기입하면 통과한다, `L-SELF-VISIBILITY` 범주).
    그리고 `required_deferrals` 는 **하한**이지 정확 집합이 아니다 — 필수 항을
    만족한 채 다른 이연을 **추가로** 등재해도 green 이다 (실측: `L-CASEFOLD` 를
    덧붙여도 green).  처분 값을 고정하는 것은 이 러너가 아니라 판정 기록과
    운영자 결정이다 — `L-EXIT-ROOT` 참조.
    """
    wiring = exit_wiring(Path(__file__).read_text(encoding="utf-8"))
    channels = {
        "Case": ([Case("X", "x", False, False)], [], []),
        "가드 기록": ([], ["<위반>"], []),
        "앵커 드리프트": ([], [], ["<드리프트>"]),
    }
    flipped = [
        label
        for label, (cases, violations, anchors) in channels.items()
        if exit_status(cases, violations, anchors) == 1
    ]
    baseline_zero = exit_status([], [], []) == 0
    # 앵커 producer 자체의 fail-closed — 계산되지 않은 상태도 실패다.
    empty_anchor_fails = bool(anchor_report_failures({}))
    matched_anchor_passes = not anchor_report_failures({"실행코드": "abcd"})
    drifted_anchor_fails = bool(anchor_report_failures({"실행코드": "abcd!=efgh"}))

    # **이연 등재** (v2.8, 운영자 처분 B / v2.9 교정, 심판 v2.8 #5).
    #
    # v2.8 은 `deferred_owner_tracks` 의 각 항이 ⑴ 등재된 노트를 가리키는지
    # ⑵ track 이 비어 있지 않은지만 봤다.  그래서 **미끼 이연** — 운영자 처분과
    # 무관한 다른 선언 id 하나를 아무 문자열 track 으로 적는 것 — 으로 대체해도
    # `SELF-3` 이 green 이었고, 처분이 기록된다는 주장이 성립하지 않았다.
    # v2.9 는 처분에서 파생한 **필수 이연 map** 을 별도 키로 고정하고, 그 각 항이
    # `deferred_owner_tracks` 에 같은 값으로 있는지를 본다 — **대체**는 그래서
    # 잡힌다.  owner-track 문법은 새로 만들지 않고 피검사 계약의
    # `register.classify_owner_track` 을 그대로 재사용한다.
    #
    # **여기서 강제되지 않는 것** (v2.9 후속 주장 축소): ⒜ 처분 **값** — 두 줄을
    # 함께 다른 트랙으로 옮기면 이 검사는 통과한다 ⒝ 이연 집합의 **정확성** —
    # 이 map 은 하한이라 필수 항을 만족한 채 추가로 등재하면 통과한다.  값의
    # 고정은 이 러너 밖(판정 기록·운영자 결정)에 있다.
    deferrals = config.cfg_pairs(dict(cfg), "deferred_owner_tracks")
    required_deferrals = config.cfg_pairs(dict(cfg), "required_deferrals")
    declared_limits = config.cfg_list(dict(cfg), "declared_limit_ids")
    deferral_problems: list[str] = []
    for lid, track in sorted(deferrals.items()):
        if not track:
            deferral_problems.append(f"{lid}=<빈 track>")
            continue
        if lid not in declared_limits:
            deferral_problems.append(f"{lid}: 미등재 노트")
        try:
            kind = register.classify_owner_track(track, cfg)
        except register.OwnerTrackSyntaxError as exc:
            deferral_problems.append(f"{lid}: {exc}")
            continue
        if kind == register.NONE:
            deferral_problems.append(f"{lid}: owner track 미배정({track!r})")
    for lid, track in sorted(required_deferrals.items()):
        if deferrals.get(lid) != track:
            deferral_problems.append(
                f"필수 이연 불일치 {lid}={track!r} "
                f"(실제={deferrals.get(lid, '<부재>')!r})"
            )

    rep.add(
        Case(
            "SELF-3",
            "발견 채널 3 종 ↔ exit 배선 (AST 파생)",
            all(wiring.values())
            and baseline_zero
            and matched_anchor_passes
            and not deferral_problems,
            len(flipped) == len(channels)
            and empty_anchor_fails
            and drifted_anchor_fails,
            f"배선={wiring} · 채널별 판정 반전 {len(flipped)}/{len(channels)} "
            f"{flipped} · 앵커 미계산 실패={empty_anchor_fails} · "
            f"드리프트 실패={drifted_anchor_fails} · 이연 등재 {len(deferrals)}건"
            f"(필수 {len(required_deferrals)}건 상호일치="
            f"{not [p for p in deferral_problems if p.startswith('필수')]}"
            f" — 하한 검사이며 처분 값 자체는 강제하지 않는다)"
            f"{'' if not deferral_problems else f' 문제={deferral_problems}'}",
        )
    )
    if not all(wiring.values()) or deferral_problems:
        rep.defect(
            "SELF-3",
            f"발견 채널이 exit 결정에 배선되지 않았다: {wiring} "
            f"이연 등재 문제={deferral_problems}",
        )
    rep.limit(
        "L-EXIT-ROOT",
        "**최종 종료 판정은 같은 프로세스 안에서 자기 절단을 검출할 수 없다** — "
        "이 프로토타입의 구조적 한계이며, 운영자 처분 B(한계 등재 + 주장 철회)로 "
        "등재한다 (심판 v2.7 critical).  `main()` 의 유일한 반환은 `exit_status()` "
        "이고 세 발견 채널이 전부 그리로 모인다.  따라서 그 이름을 0 만 돌려주게 "
        "재바인딩하면 **red Case·운영 경계 위반·앵커 드리프트를 전부 탐지하고 "
        "출력한 상태에서도 exit 0** 이 된다.  `exit_wiring()` 은 `main()` 의 "
        "소스 텍스트만 보므로 이것을 막지 못한다.  **이유는 구조적이다**: 그 절단을 "
        "관측하는 층(`SELF-3`)의 판정도 결국 판정층인 같은 함수를 경유하므로, "
        "검출층을 하나 더 쌓으면 그 층의 판정도 다시 같은 지점을 지난다 — 임의의 "
        "same-process 변조를 위협 모델에 두는 한 이 회귀는 **종료하지 않는다**.  "
        "그러므로 내부 자기검사를 더 쌓아 닫으려 하지 않는다.  **이 러너가 최종 "
        "exit 자체까지 자기증명한다고 주장하지 않는다.**  해소 경로는 하나뿐이다 — "
        "리비전에 결속된 **외부 CI/래퍼가 별도 프로세스에서** 알려진 red 조건을 "
        "주입하고 비영 종료를 직접 검증하는 것.  그 처분은 아래 이연 항목으로 "
        f"등재됐고 설정 `deferred_owner_tracks` 와 `required_deferrals` 두 줄이 "
        f"서로 일치해야 한다 (owner track = "
        f"{deferrals.get('L-EXIT-ROOT', '<미등재>')}, 필수 = "
        f"{required_deferrals.get('L-EXIT-ROOT', '<미등재>')}).  **다만 이 러너는 "
        "그 트랙 값 자체를 고정하지 않는다** (v2.9 후속 주장 축소) — 두 줄을 함께 "
        "다른 트랙으로 옮기면 `SELF-3` 은 green 이고, `required_deferrals` 는 "
        "하한이라 추가 이연 등재도 통과한다.  처분 값을 고정하는 것은 이 러너가 "
        "아니라 `.omc/review/` 의 판정 기록과 운영자 결정이다.  이연한 이유는 "
        "다음과 같다: 외부 "
        "검증자는 OD-3-D(CI 미편입 — 이 러너는 '기계 강제 없음' 이라 적는다)와 "
        "OD-3-B(D0 아티팩트 생성 금지)의 경계에 직접 닿아, Phase 0 안에서 처리하면 "
        "그 경계 자체를 재정의하게 되기 때문이다.  Phase 0 이 강제하는 범위는 "
        "그대로 두고 처분만 다음 단계로 넘긴다.",
    )


def _settings_mismatch(
    left: Mapping[str, object], right: Mapping[str, object]
) -> list[str]:
    """필수 키에 대해 두 판독 결과가 어긋나는 지점."""
    return [
        f"{key}: A={left.get(key)!r} B={right.get(key)!r}"
        for key in config.REQUIRED_KEYS
        if str(left.get(key, "\x00")) != str(right.get(key, "\x00"))
    ]


def config_read_duality(cfg, rep: Report) -> None:
    """T-80 — 앵커 기대값 **파싱 코드**의 이중화 + 소비 바인딩 구조 결속 (v2.8).

    심판 v2.7 #2: 앵커 5 종의 기대값은 전부 `load_config()` **한 바인딩**에서
    왔고, 그 바인딩은 `__module__` 자기신고 때문에 실행코드 앵커의 정의역
    **밖**이었다.  그래서 러너의 `load_config` 를 `__module__='proto.config'` 인
    함수로 갈아끼우면 디스크가 실제로 편집된 상태에서도 전건 GREEN 이 됐다.

    v2.8 의 교정은 셋이고 이 Case 가 그중 둘을 직접 관측한다:
      ⑴ 설정 접근을 **모듈 한정 호출**(`config.load_config()`)로 정규화했다 —
         러너 네임스페이스에는 갈아끼울 사본이 남아 있지 않다.
      ⑵ 러너가 자기 코드로 설정을 **한 번 더 읽어** 필수 키 전건을 대조한다.
      ⑶ (`T-79` 소관) 소비 바인딩의 이름·**파일 라벨**·코드 digest 를 값 앵커에
         묶는다 — 그 라벨은 검증된 provenance 가 아니다 (v2.10 철회).

    **이 Case 가 무엇을 대조하는지 정확히** (v2.9, 심판 v2.8 #1): 두 판독기의
    **파싱 결과**를 대조한다.  **경로는 대조하지 않는다** — 둘 다
    `config.CONFIG_PATH` 에서 오므로 그 이름 하나를 재바인딩하면 둘이 같은
    파일에서 같은 값을 읽고 이 Case 는 일치를 보고한다.  아래 `foreign` 검사도
    모듈에 대해서는 `binding_file(module)` 과 `basename(module.__file__)` 을
    비교하므로 사실상 항등식이고, 갈리는 것은 **파일 라벨이 서로 다른 함수 항**
    뿐이다 — 그 라벨은 검증된 provenance 가 아니라 `co_filename`·`__file__`
    메타데이터이므로, 라벨을 맞춰 온 교체는 여기서도 갈리지 않는다 (v2.10 철회,
    심판 9 회차 #2).  등재는 `L-CONFIG-TRUSTPOINT`, 종단 한계는 `L-EXIT-ROOT` 다.
    """
    settings = dict(cfg)
    independent = independent_settings(config.CONFIG_PATH)
    mismatched = _settings_mismatch(settings, independent)
    covered = [key for key in config.REQUIRED_KEYS if key in independent]

    # 소비 바인딩의 **파일 라벨**이 그 모듈 자신의 라벨과 같은가.
    # **모듈 항에 대해서는 항등식이다** (v2.9 정정): `binding_file(module)` 이
    # 곧 `basename(module.__file__)` 이므로 이 비교는 모듈을 통째로 갈아끼운
    # 경우를 잡지 못한다.  실질을 갖는 것은 **파일 라벨이 다른 함수** 항이며
    # 방향② 의 양성 대조군도 그 형태다.  라벨은 provenance 가 아니므로 라벨을
    # 맞춰 온 교체는 여기서도 갈리지 않는다 (v2.10 철회).
    foreign = [
        f"{label}: {binding_file(module)}"
        for label, module in anchor_modules()
        if binding_file(module) != os.path.basename(getattr(module, "__file__", ""))
    ]

    # 방향② — 두 축의 양성 대조군.
    forged = {**settings, config.REQUIRED_KEYS[0]: "<위조>"}
    forgery_detected = bool(_settings_mismatch(forged, independent))
    # 다른 파일에서 온 코드는 출처 대조에서 즉시 갈린다.
    foreign_detected = binding_file(ast.parse) != binding_file(config)

    rep.add(
        Case(
            "T-80",
            "설정 **파싱** 이중화 + 바인딩 출처 결속",
            not mismatched
            and len(covered) == len(config.REQUIRED_KEYS)
            and not foreign,
            forgery_detected and foreign_detected,
            f"필수 키 {len(covered)}/{len(config.REQUIRED_KEYS)} 이중 판독 일치"
            f"={not mismatched}{'' if not mismatched else f' 불일치={mismatched}'} · "
            f"바인딩 출처 이탈={foreign or '없음'} · 위조 판독 검출={forgery_detected}"
            f" · 외래 코드 검출={foreign_detected}",
        )
    )
    if mismatched or foreign:
        rep.defect(
            "T-80",
            f"설정 판독 경로가 어긋난다 (불일치={mismatched} 출처이탈={foreign})",
        )
    rep.limit(
        "L-CONFIG-TRUSTPOINT",
        "**설정 판독의 신뢰점은 하나다** (v2.9 등재, 심판 v2.8 #1).  주 판독기 "
        "`config.load_config()` 와 이 Case 의 두 번째 판독기 "
        "`independent_settings()` 는 파싱 코드가 다르지만 **경로는 둘 다 "
        "`config.CONFIG_PATH` 라는 같은 이름에서 온다**.  그 이름을 한 번 "
        "재바인딩하면 두 판독기가 같은 파일을 읽고 이 Case 는 '이중 판독 일치' 를 "
        "보고한다.  `CONFIG_PATH` 는 값 앵커의 정의역 밖(잔여)이라 재바인딩 자체도 "
        "관측되지 않는다.  **실측**: 라이브 모듈에서 `runner.ANCHOR_IMPORT_ROOTS` 를 "
        "좁혀 `runner.MODULE_BINDINGS` 의 정의역에서 `audit_guard` 를 뺀 뒤, 새 "
        "기대값 세 개를 담은 위조 설정으로 `config.CONFIG_PATH` 를 **한 번** "
        "재바인딩하니 디스크 `config.yaml` 이 바이트 그대로인 채 exit 0 · 대조군 "
        "39/39 · 앵커 드리프트 없음이었다.  그래서 v2.8 의 '비용을 1 지점에서 "
        "2 지점으로 올렸다' 는 서술을 정정했다.  같은 이유로 이 Case 의 `foreign` "
        "검사는 **모듈 항에 대해 항등식**이다 — `binding_file(module)` 이 곧 "
        "`basename(module.__file__)` 이므로 모듈 통째 교체는 그 축에서 갈리지 "
        "않는다.  해소 방향은 러너 자신의 고정 위치에서 경로를 파생하고 설정 "
        "바이트를 그 설정 **밖** 신뢰점에 묶는 것인데, 그 신뢰점도 같은 프로세스 "
        "안이면 같은 회귀에 들어간다 — `L-EXIT-ROOT` 참조.  가시화이지 폐쇄가 아니다.",
    )


def policy_value_anchors(cfg, rep: Report) -> None:
    """T-79 — 모듈 정책값을 **자동 census** 로 파생해 설정 앵커에 결속 (v2.8).

    v2.7 은 25 개짜리 **손으로 쓴 양성 목록**이었고, 심판이 그 목록 밖에서
    실제로 판정에 쓰이는 값(`_NULLARY_STR_METHODS`)을 찾아냈다 — 하드코딩
    census 는 신규 항목을 영원히 못 찾는다 (심판 v2.7 #5).  v2.8 은 대상
    모듈의 모듈 레벨 이름을 구조에서 훑고, **의도적 제외만** 설정에 선언한다.
    잔여(정의역 타입 밖)도 손이 아니라 census 가 열거해 노트로 방출한다.
    """
    excluded = config.cfg_list(dict(cfg), "policy_value_exclusions")
    census = policy_value_census(excluded)
    targets = policy_value_targets(excluded)
    declared = config.cfg_pairs(dict(cfg), "anchor_policy_values")
    names_match = sorted(targets) == sorted(declared)
    phantom = census["phantom"]
    drifted = [
        f"{name}={policy_digest(value)}!={declared.get(name)}"
        for name, value in sorted(targets.items())
        if declared.get(name) != policy_digest(value)
    ]

    # **항목별** 삭제·확장이 전부 관측되는가.
    variants = 0
    undetected: list[str] = []
    for name, value in sorted(targets.items()):
        pinned = declared.get(name)
        for label, variant in policy_value_variants(value):
            variants += 1
            if policy_digest(variant) == pinned:
                undetected.append(f"{name}/{label}")

    rep.add(
        Case(
            "T-79",
            "정책값 자동 census ↔ 설정 값 앵커",
            names_match and not drifted and not phantom,
            variants > 0 and not undetected,
            f"census {len(census['targets'])}+정규화 {len(synthetic_policy_targets())}"
            f"={len(targets)}개 ↔ 등재 {len(declared)}개 일치={names_match} · "
            f"의도적 제외 {len(census['excluded'])}개(실물 없는 제외="
            f"{list(phantom) or '없음'}) · 정의역 타입 밖 잔여 "
            f"{len(census['residual'])}개 · 드리프트={drifted or '없음'} · "
            f"항목별 변형 {variants}건 중 미검출 "
            f"{len(undetected)}건{'' if not undetected else f' {undetected}'}",
        )
    )
    if drifted or not names_match or undetected or phantom:
        rep.defect(
            "T-79",
            f"런타임 정책값이 설정 앵커와 어긋난다 (드리프트={len(drifted)} "
            f"이름일치={names_match} 미검출변형={len(undetected)} 팬텀제외={phantom})",
        )
    rep.limit(
        "L-POLICY-ANCHOR",
        f"값 앵커의 정의역은 **자동 census** 가 파생한 {len(targets)}개 이름이다 — "
        "v2.7 의 손으로 쓴 25 개 목록이 아니다.  census 는 앵커 대상 모듈의 모듈 "
        "레벨 **비호출** 이름을 훑어 ⑴ 정의역 타입(str·bytes·tuple·frozenset·set·"
        "list·dict)에 드는 값은 앵커 대상으로 ⑵ 설정 `policy_value_exclusions` "
        f"에 적힌 것은 의도적 제외({', '.join(census['excluded']) or '없음'})로 "
        "⑶ 나머지는 잔여로 3 분류한다.  값은 라이브 모듈에서 읽으므로 런타임 "
        "대입도 관측된다 — 다만 관측되는 것은 **target 이름 집합 또는 "
        "`policy_digest` 가 바뀌는** 대입뿐이다.  앵커는 어떤 뮤테이션 부류를 "
        "잡는지가 아니라 **자기 투영이 무엇인지**로만 서술하며, **v2.10 주장 "
        "축소 (심판 9 회차 #1): 그 서술은 최종 직렬화/digest 까지 내려갈 때만 "
        "종결적이다.**  **보장 밖**: ⑴ "
        "정규화상 동치인 컨테이너 타입 교체 — `policy_value_text` 가 tuple 과 "
        "list 를, set 과 frozenset 을 각각 같은 문자열로 접고 "
        "`POLICY_VALUE_TYPES` 는 네 타입을 다 받으므로, census 안에서의 그 타입 "
        "교체는 이름과 digest 를 **둘 다 보존한다**.  ⑵ **그 타입 목록 밖에서도** "
        "같은 접힘이 일어난다: `policy_value_text` 는 타입 태그도 길이도 없이 "
        "NUL(`\\x00`) 하나로 항목을 잇고 중첩 컨테이너도 같은 구분자로 평탄화하므로 "
        "**항목 수·항목 내용·항목 경계·중첩 구조가 다른 값이 같은 digest 로 "
        "접힌다** — 실측: `policy_value_text(('a','b'))` 와 "
        "`policy_value_text(('a\\x00b',))` 가 둘 다 `a\\x00b` 다.  그래서 이 앵커의 "
        "보장은 '값이 바뀌면' 이 아니라 **`policy_digest` 가 바뀌면**으로만 적고, "
        "위 열거는 닫힌 목록이 아니다.  ⑶ 실행 코드 "
        "앵커도 같은 성질이다 — 그 보장은 '수집된 코드 투영이 바뀌면' 이 아니라 "
        "**`loaded_code_text()` 문자열(따라서 그 digest)이 바뀌면** 이다.  수집 항"
        "(`co_name`·`co_code`·`co_names`·문자열/중첩 코드 상수)은 태그·길이 없이 "
        "`\\x1f` 로만 이어지므로 구분자가 값 안에 들어가면 항 경계가 사라진다: "
        "문자열 상수가 `('a\\x1fb',)` 에서 `('a','b')` 로 바뀌면 항 목록은 갈리는데 "
        "직렬화는 둘 다 `a\\x1fb` 라 digest 가 같다(실측).  같은 `__code__` 와 파일 "
        "라벨을 쓰되 "
        "globals·defaults·closure 만 다른 함수 객체로의 교체도 보장 밖이다.  "
        "**새 상수가 생기면 등재 없이는 red 가 된다** — 다만 그 "
        "'새 상수' 는 **모듈 레벨 비호출 이름**일 때만이다.  **정의역 축소 "
        "(v2.9 등재, 심판 v2.8 #4)**: `callable(value)`/모듈 스킵이 이름 등록보다 "
        "앞에 있어 **클래스는 targets·residual·phantom 어디에도 나타나지 않는다** "
        "(실측 확인).  실행코드 앵커도 클래스 멤버 중 `__code__` 가 있는 것만 "
        "묶으므로 클래스 **속성값**은 보지 않는다.  그래서 클래스 속성에 놓인 "
        "정책 상수의 런타임 대입은 값 앵커와 잔여 목록 양쪽에서 침묵한다 — 실측: "
        "라이브로 클래스 속성 하나를 바꾼 뒤 전건을 돌려도 앵커 5 종이 전부 "
        "불변이었고 exit 0 이었다.  디스크 편집만 소스 바이트 앵커가 본다.  "
        "아래 개수와 목록은 **그 축소된 정의역 안의** 값이다.  "
        "**census 가 이름 등록까지 도달한 잔여** — 이 이름들은 디스크 편집만 소스 "
        f"바이트 앵커가 잡고 런타임 대입은 잡지 못한다: {', '.join(census['residual'])}.  "
        f"제외 {len(census['excluded'])}종은 전부 **실행 중 내용이 변하는 기록 "
        "버킷**이거나 설치 시점 스냅샷이라 digest 로 고정할 수 없다 — 기록 버킷은 "
        "운영 게이트와 `anchor_probe_records` 가, `_ARMED_SNAPSHOT` 은 "
        "`bootstrap_witness()` 가 내용으로 판정한다.  정책 상태"
        "(`_READ_ARMED`·`_WRITE_ARMED`·`_PROBE_DEPTH`)는 값이 아니라 상태라 잔여로 "
        "분류되고 운영 게이트가 종료 시점에 직접 확인한다.  함수 본문의 리터럴은 "
        "실행 코드 앵커 쪽 정의역이다.  census 자체를 좁히는 편집은 코드 diff 로, "
        "제외를 늘리는 편집은 설정 diff 로 드러난다 — 가시화이지 폐쇄가 아니다.",
        case="T-79",
    )


def self_check(cfg, rep: Report) -> None:
    """SELF-1 — 발견이 exit status 에 결속됐는가.  **가장 마지막에 돌린다.**

    v2.5: 어휘 분류(닫힌 목록)에서 **등재 강제**로 옮겼다 (심판 F1).
    v2.6: `clean_green` 을 명명된 검사 dict 에서 파생하고, 소비 배선은
    `SELF-2` 가 전수 관측한다.
    """
    declared = config.cfg_list(dict(cfg), "declared_limit_ids")
    waivers = config.cfg_list(dict(cfg), "limit_vocabulary_waivers")
    declared_checks = config.cfg_list(dict(cfg), "declared_self_checks")
    unchk_ids = tuple(row.id for row in register.fixture_rows())

    # L3 본문 앵커 — 등재된 노트의 **산문**을 고쳐도 red 가 되어야 한다.
    #   ⒜ 소스 리터럴 digest — `limit()` 호출의 **문자열 리터럴 조각**이 바뀌는
    #      편집을 잡는다.  삽입부는 그 투영 밖이고 — 그래서 ⒝ 가 있다.
    #   ⒝ 방출 본문 digest — **최종 방출 문자열**이 바뀌는 편집을 잡는다.
    # ⒜ 만으로는 부족했다: 노트가 전부 f-string 이라 삽입값에 결함 서술을
    # 실으면 리터럴이 불변이어서 통과했다(심판 stop-time 2 차 지적).
    settings = dict(cfg)
    own_source = Path(__file__).read_text(encoding="utf-8")
    expected_digest = str(settings.get("anchor_limit_text_digest", ""))
    actual_digest, per_note = limit_text_anchor(own_source)
    #   ⒟ **실행 중인 코드** digest — 디스크 파일이 아니다 (5 차 교정).
    expected_source = str(settings.get("anchor_runner_source_digest", ""))
    actual_source = runner_source_anchor(loaded_code_text(anchor_modules()))
    #   ⒠ **소스 바이트** digest — 모듈 레벨 데이터·주석·docstring·`__init__.py`
    #   가 ⒟ 의 정의역 밖이라는 심판 F1 지적의 교정이다.
    expected_bytes = str(settings.get("anchor_source_bytes_digest", ""))
    anchor_paths = anchor_source_paths()
    actual_bytes = source_bytes_anchor(anchor_paths)

    # 이 두 노트는 방출 앵커 **계산 전에** 등재한다 — 뒤에 두면 `SELF-1` 이
    # 스스로 방출하는 노트만 ⒝ 의 정의역 밖이 된다(다음 간극이 될 자리다).
    rep.limit(
        "L-SELF-VISIBILITY",
        "SELF-1 의 등재 강제·SELF-2 의 producer/소비 전수 검증·SELF-3 의 배선 "
        "관측·앵커 전 종류는 전부 **가시화**이지 폐쇄가 아니다.  검사 항을 "
        "지우면서 `declared_self_checks` 와 앵커 값을 함께 고치면 러너는 다시 "
        "green 이 된다 — 그 경로는 코드·설정·앵커 3 곳의 diff 로 남을 뿐이다.  "
        "아예 관측하지 않는 조건은 어느 층도 보지 못한다.",
        case="SELF-2",
    )
    rep.limit(
        "L-SRC-ANCHOR",
        "앵커는 8 종이다: ⑴ 노트 리터럴 ⑵ 방출 본문 ⑶ Case 산문 ⑷ 실행 코드 "
        "⑸ 소스 바이트 — 이 다섯은 `rep.anchors` 로 모여 `main()` 이 exit 에 "
        f"직접 결속한다 — 그리고 ⑹ 런타임 정책값(`T-79`) ⑺⑻ 러너·"
        f"{Path(audit_guard.__file__).name} 의 pre-hook 구간(`T-77-AUDIT`).  "
        f"소스 바이트는 {len(anchor_paths)}개 파일"
        f"({', '.join(path.name for path in sorted(anchor_paths, key=lambda p: p.name))})"
        "의 정확한 바이트를 묶고 `config.yaml` 은 자기참조라 제외한다.  실행 코드 "
        "앵커는 `__code__` 를 가진 객체만 순회하므로 모듈 레벨 데이터·주석·"
        "docstring 은 소스 바이트 앵커 쪽이 덮는다.  **v2.8 — 실행 코드 앵커의 "
        "정의역에서 `__module__` 자기신고를 없앴다** (심판 v2.7 #2): v2.7 은 "
        "`obj.__module__` 이 "
        "그 모듈과 같은 것만 묶어서 import 로 바인딩한 이름의 교체를 놓쳤다.  이제 "
        "`__code__` 를 가진 객체는 **소속과 무관하게 전부** 묶고 코드가 내놓는 "
        "**파일 라벨**을 함께 적는다(그래서 stdlib 헬퍼도 정의역에 들어온다).  "
        "**v2.10 주장 철회 (심판 9 회차 #2) — 없앤 것은 `__module__` 이지 파일 "
        "라벨이 아니다.**  직전 판은 이 라벨을 '코드가 실제로 온 파일' 이라 적고 "
        "`module_binding_identities()` 는 그것을 '자기신고가 아닌 결속' 이라 "
        "적었는데 둘 다 구현보다 넓었다.  `binding_file()` 이 읽는 값은 함수면 "
        "`basename(co_filename)`, 모듈이면 `basename(__file__)` 이라는 "
        "**메타데이터 라벨**이다 — 전자는 컴파일 시점에 **제공되는** 값이라 "
        "임의 이름으로 컴파일하면 그대로 실려 오고, 후자는 라이브 객체의 **가변 "
        "속성**이라 대입 한 줄로 바뀐다.  어느 쪽도 검증된 provenance 가 아니며, "
        "현재 `module_binding_identities()` 가 파생하는 이름은 전부 모듈 객체라 "
        "**가변 `__file__` 분기만 탄다**.  따라서 관측값은 그 라벨 + 코드 digest "
        "이고, **같은 코드 투영에 라벨만 위조한 모듈·함수 교체는 세 축이 전부 "
        "보존돼 identity 가 유지된다** — 설명상 거부되는 것처럼 보였을 뿐 실제로는 "
        "통과한다.  클래스는 그 "
        "모듈 소스의 최상위 `ClassDef` 이름으로 정의역을 정한다 — **묶이는 것은 그 "
        "클래스의 `__code__` 를 가진 멤버뿐이고 클래스 속성 값은 정의역 밖이다** "
        "(v2.9 정정).  **v2.9 후속 등재 — descriptor 로 감싼 멤버도 정의역 "
        "밖이다**: 수집기의 판정은 `getattr(obj, '__code__')` 하나뿐이라 "
        "`property`·`staticmethod`·`classmethod` 로 감싼 멤버 6 건(`Case.ok` · "
        "`boundary.ReadRecorder.clean` · `boundary.WriteRecorder.clean` · "
        "`gates.Predicate.pid` · `gates.Evaluation.__new__` · "
        "`gates.Evaluation._make`)의 코드는 묶이지 않는다.  그중 `Case.ok` 는 "
        "**모든 대조군의 판정 술어**(`clean_green and mutant_red`)이므로 무게가 "
        "다르다 — 실측: seeded-red 상태에서 이 property 만 교체하니 37/39 가 "
        "39/39 로 돌고 미성립 목록이 사라지는데 실행 코드 앵커는 **불변**이었다 "
        "(대조군: 같은 클래스의 평문 함수 멤버 교체는 검출된다.  그 실행에서 "
        "종료 코드가 1 로 남은 것은 Case 산문 digest 가 움직였기 때문이지 실행 "
        "코드 앵커가 잡아서가 아니다).  디스크 편집만 "
        "소스 바이트 앵커가 잡는다.  판정 술어의 런타임 교체를 같은 프로세스가 "
        "보지 못한다는 점에서 이것은 `L-EXIT-ROOT` 와 **같은 회귀**다.  "
        "디스크를 건드리지 "
        "않는 런타임 대입은 소스 바이트가 보지 못한다.  그 대신 보는 두 앵커도 "
        "**각자의 최종 직렬화 안에서만** 본다 — 실행 코드 앵커는 "
        "**`loaded_code_text()` 문자열(따라서 그 digest)이 바뀌는** 교체를, "
        "정책값 앵커는 **target 이름 집합 또는 `policy_digest` 가 "
        "바뀌는** 대입을 관측한다.  둘 다 어떤 뮤테이션 부류를 잡는지가 아니라 "
        "**자기 투영이 무엇인지**로 적은 것이며, **v2.10 주장 축소 (심판 9 회차 "
        "#1): 투영-프레이밍은 최종 직렬화/digest 까지 내려갈 때만 종결적이다.**  "
        "직전 판은 실행 코드 앵커의 보장을 '수집된 코드 투영"
        "(`co_name`·`co_code`·`co_names`·문자열/중첩 코드 상수)이 바뀌는 교체' "
        "라고 적었는데 수집 항보다 **한 단계 위**에서 끊긴 서술이었다: 그 항들은 "
        "`loaded_code_text()` 에서 태그도 길이도 없이 `\\x1f` 로만 이어지므로 "
        "**항 목록이 달라도 이어붙인 결과가 같으면 digest 는 불변이다**.  실측 — "
        "문자열 상수가 `('a\\x1fb',)` 에서 `('a','b')` 로 바뀌면 수집 항은 갈리는데 "
        "직렬화는 둘 다 `a\\x1fb` 라 값이 같다.  **보장 밖**: ⑴ 같은 `__code__` "
        "와 파일 라벨을 쓰되 globals·defaults·closure 만 다른 함수 객체로의 "
        "교체(직렬화가 불변이라 정의역 안이어도 앵커가 움직이지 않는다) ⑵ 구분자가 "
        "값 안에 들어 항 경계가 사라져 같은 직렬화로 접히는 교체(바로 위 실측) "
        "⑶ 정규화상 동치인 컨테이너 타입 교체(tuple↔list · set↔frozenset — "
        "`policy_value_text` 가 같은 문자열로 접고 `POLICY_VALUE_TYPES` 가 네 "
        "타입을 다 받으므로 이름과 digest 를 둘 다 보존한다) ⑷ 그 타입 목록 "
        "**밖**에서 NUL 평탄화가 접는 값들 — `policy_value_text` 도 타입 태그·길이 "
        "없이 NUL 하나로 항목을 잇고 중첩을 평탄화하므로 **항목 수·항목 경계·중첩 "
        "구조가 달라도** 같은 digest 가 된다 (예: `('a','b')` 와 `('a\\x00b',)`).  "
        "이 네 갈래의 목록도 **닫힌 열거가 아니다** — 닫는 것은 열거가 아니라 "
        "'최종 직렬화가 바뀌면' 이라는 서술 자체다.  그래서 바로 위에 "
        "적은 descriptor 6 건처럼 `property`·"
        "`staticmethod`·`classmethod` 로 감싼 멤버와 클래스 **속성**은 두 투영 "
        "**어느 쪽에도 들지 않아 양쪽 다 침묵한다** — `Case.ok` 교체가 정확히 그 "
        "경우이고, 그래서 위 실측에서 앵커가 불변이었다.  "
        "정책값 앵커의 정의역과 그 **밖**은 `L-POLICY-ANCHOR` 가 열거한다.  "
        "**v2.11 — 이 구분자 접힘은 ⒟·⒡ 만의 성질이 아니다.**  ⒝ 방출 본문과 "
        "⒞ Case 산문도 레코드 안은 `\\x1f`, 레코드 사이는 `\\x00` 으로만 태그·길이 "
        "없이 이어 붙이므로 **항 목록이 달라도 같은 직렬화로 접히면 digest 가 "
        "불변이다** — 실측: `Limit(L1, x\\x1fy)` 와 `Limit(L1\\x1fx, y)` 가 둘 다 "
        "`8ec383d8d23dde51`, `Case(T1, n, …, x\\x1fy)` 와 `Case(T1, n\\x1fx, …, y)` "
        "가 둘 다 `4880d819e8cb2d12` 다.  나머지 두 종도 코드로 판정했다.  "
        "⒜ 노트 리터럴은 **더 강한 형태**다 — `limit_text_anchor` 는 리터럴 조각을 "
        "**빈 문자열**로 이으므로 항 경계가 애초에 없고 구분자가 값 안에 들어갈 "
        "필요조차 없다(실측: `('a','b')` 와 `('ab',)` 가 둘 다 "
        "`8a887290b7fb0209`).  바깥 `lid=digest` 층도 `|`·`=` 가 lid 에 들어가면 "
        "접힌다(실측: 노트 둘 `L1`·`L2` 와 노트 하나 `L1=e3b0c44298fc|L2` 가 둘 다 "
        "`179bc6a81bc1e683`).  ⒠ 소스 바이트도 같은 성질을 갖는다 — 실측: "
        "`a.py`(`AAA`)+`b.py`(`BBB`) 와 `a.py`(`AAA\\x1fb.py\\x00BBB`) 하나가 둘 다 "
        "`0e2378ef8aad6b9b` 이라 **파일 하나가 목록에서 사라져도 값이 같다**.  다만 "
        "그 접힘은 앵커된 바이트 안의 NUL 을 요구하는데 파일 이름에는 NUL 을 넣을 "
        "수 없고(`ValueError: embedded null byte`) NUL 을 담은 `.py` 는 CPython 이 "
        "컴파일을 거부하므로(`SyntaxError: source code string cannot contain null "
        "bytes`) **임포트 가능한 `.py` 로만 이루어진 이 앵커의 실제 대상 안에서는 "
        "도달 불가**다 (셋 다 실측).  따라서 정확한 서술은 **`rep.anchors` 5 종"
        "(⒜⒝⒞⒟⒠)과 ⒡ 가 전부 같은 구분자 접힘 클래스**이고 ⒜ 가 가장 강하며 ⒠ "
        "만 대상 제약으로 도달 불가라는 것이다.  "
        "`co_code` 를 묶으므로 앵커는 CPython 버전에 묶인다 — 인터프리터를 바꾸면 "
        "값을 다시 기입해야 하고 그 재기입은 diff 에 남는다.  **이 앵커들이 내는 "
        "판정도 결국 `exit_status()` 를 경유한다** — `L-EXIT-ROOT` 참조.",
    )

    expected_emitted = str(settings.get("anchor_limit_emitted_digest", ""))
    actual_emitted = emitted_text_anchor(rep.limits)

    # ⒞ Case 산문 digest — **SELF-1 자신을 포함해서** 계산한다.
    # detail 을 먼저 확정하고 그 다음 해시하므로 순환이 없다.  digest 값은
    # detail 이 아니라 `main()` 출력으로 나간다.
    anchor_pairs = (
        ("리터럴", actual_digest, expected_digest),
        ("방출", actual_emitted, expected_emitted),
        ("실행코드", actual_source, expected_source),
        ("소스바이트", actual_bytes, expected_bytes),
    )
    drift = [label for label, actual, expected in anchor_pairs if actual != expected]

    name = "발견↔exit 결속 자기 검사 (등재 강제)"
    checks_preview = collect_self_checks(rep, declared, unchk_ids, waivers, drift)
    detail = (
        f"발견 {len(rep.defects)}건 · "
        f"검사 {format_checks(checks_preview)} · "
        f"노트 {len(rep.limits)}/{len(declared)} · "
        f"앵커 대상 {len(anchor_paths)}파일 · Case {len(rep.cases) + 1}개"
    )
    expected_prose = str(settings.get("anchor_case_prose_digest", ""))
    actual_prose = case_prose_anchor(
        [*rep.cases, Case("SELF-1", name, True, True, detail)]
    )
    if actual_prose != expected_prose:
        drift.append("Case산문")

    # **소비 항은 여기서 파생된다** — 손으로 쓴 불리언식이 아니다 (v2.6).
    checks = collect_self_checks(rep, declared, unchk_ids, waivers, drift)
    names_match = sorted(checks) == sorted(declared_checks)
    clean_green = self_check_green(checks, names_match)

    rep.anchors = {
        label: f"{actual}{'' if actual == expected else f'!={expected}'}"
        for label, actual, expected in (
            *anchor_pairs,
            ("Case산문", actual_prose, expected_prose),
        )
    }

    # 뮤테이션 — **심판이 v2.3 을 뚫은 우회 3 종을 그대로 심는다.**
    #   ① 어휘 밖 서술  ② 어휘 밖 서술(다른 형태)  ③ green Case 주차
    # ①② 는 L1(등재)이, ③ 은 L2(주차 거부)가 잡아야 한다.
    probe = Report()
    probe.add(Case("PROBE", "프로브", True, True))
    probe.defect("<없는 Case>", "심은 발견")
    probe.defect("PROBE", "green Case 에 붙인 발견")
    probe_declared = ("L-PROBE",)
    probe.limit("L-PROBE", "등재된 정상 노트")
    probe.limit("L-BYPASS-1", "검출기가 이 조건을 잡지 못한다")
    probe.limit("L-BYPASS-2", "조용히 잘못된 값을 산출한다")
    probe.limit("L-BYPASS-3", "결함이 생존한다", case="PROBE")
    probe.limit("L-PROBE", "같은 lid 로 숨긴 두 번째 노트")
    bypass_ids = ["L-BYPASS-1", "L-BYPASS-2", "L-BYPASS-3"]
    # 심어둔 상태를 **실제 소비 경로**에 통과시킨다 (v2.6).  v2.5 는 헬퍼 반환값만
    # 비교했고 그 결과가 exit 로 소비되는지는 보지 않았다 — 심판 F1.
    probe_checks = collect_self_checks(probe, probe_declared, unchk_ids, (), ())
    mutant_red = (
        len(probe.unbound_defects()) == 1
        and len(probe.green_bound_defects()) == 1
        and sorted(set(probe.undeclared_limits(probe_declared))) == bypass_ids
        and probe.parked_limits(unchk_ids, ()) == ["L-BYPASS-3"]
        and probe.duplicate_limits() == ["L-PROBE"]
        and probe.missing_limits(("L-PROBE", "L-ABSENT")) == ["L-ABSENT"]
        and probe.unresolved_limit_refs(unchk_ids) == []
        and not self_check_green(probe_checks, True)
    )

    rep.add(Case("SELF-1", name, clean_green, mutant_red, detail))


# --- 실행 ------------------------------------------------------------------


def run_all() -> tuple[Report, dict]:
    """대조군 전건을 돌리고 **판독한 설정과 함께** 돌려준다.

    설정을 함께 반환하는 이유: 종료 시점 게이트(`operational_violations`)가
    프로브 기록 앵커를 소비해야 하는데, 그 값도 설정에서 온다 (v2.8).
    """
    cfg = config.load_config()
    rep = Report()
    t75_all_met_reachability(cfg, rep)
    t2_input_missing_basis(cfg, rep)
    t69_classification_isolation(cfg, rep)
    t62_owner_track_grammar(cfg, rep)
    t77_boundary(cfg, rep)
    t61_reason_membership_move(cfg, rep)
    t70_reason_separation(cfg, rep)
    t68_blocks_gate_target(cfg, rep)
    t67_metric_movement(cfg, rep)
    fwd_a_0_superset_closure(cfg, rep)
    t11_inv_c4(cfg, rep)
    t39_enforcement_registry(cfg, rep)
    t76_level_raw_anchor(cfg, rep)
    unchk_019_registry_omission(cfg, rep)
    u8b_kind_exclusion(cfg, rep)
    t71_distribution_anchor(cfg, rep)
    t72_range_noblock_but_counted(cfg, rep)
    t73_metric_exposure(cfg, rep)
    t74_closable_transition_anchor(cfg, rep)
    floor_parsing_aborts(cfg, rep)
    config_read_duality(cfg, rep)
    policy_value_anchors(cfg, rep)
    # SELF-2/SELF-3 은 SELF-1 **앞**이다 — SELF-1 의 Case 산문 앵커가 그 detail
    # 까지 덮으려면 그때 이미 `rep.cases` 에 있어야 한다.
    self_exit_wiring(cfg, rep)
    self_check_consumption(cfg, rep)
    self_check(cfg, rep)
    return rep, dict(cfg)


def main() -> int:
    # **가드는 실행 전체를 감싼다.**  v2.5 1 차 교정은 `read_guard` 를 만들고
    # T-77 안 프로브에서만 썼다 — 기제는 있는데 실행에 배선하지 않아 실제
    # 코퍼스 열람이 전건 GREEN 으로 통과했다(심판 stop-time 지적).  선언층과
    # 평가층의 간극이 **이 러너 자신에게서** 재발한 사례다.
    with boundary.write_guard() as recorder, boundary.read_guard() as read_recorder:
        rep, cfg = run_all()

    print("=" * 100)
    print("Phase 0 완료 계약 프로토타입 — 양방향 대조군 결과")
    print("=" * 100)
    print(f"{'ID':<14} {'대조군':<38} {'방향①(기준)':<12} {'방향②(변형)':<12} 판정")
    print("-" * 100)
    for case in rep.cases:
        first = "성립" if case.clean_green else "미성립"
        second = "성립" if case.mutant_red else "미성립"
        verdict = "OK" if case.ok else "결함"
        print(f"{case.tid:<14} {case.name:<38} {first:<12} {second:<12} {verdict}")
    print("-" * 100)
    print()
    print("상세")
    for case in rep.cases:
        print(f"  [{case.tid}] {case.detail}")
    print()
    print(
        f"발견 — 관측된 계약 위반 {len(rep.defects)}건 (전부 Case 로 결속돼 집계된다)"
    )
    if rep.defects:
        index = rep.case_index()
        for found in rep.defects:
            bound = index.get(found.tid)
            state = (
                "Case 없음" if bound is None else ("red" if not bound.ok else "GREEN")
            )
            print(f"  - [{found.tid} / {state}] {found.text}")
    else:
        print("  - 없음")
    print()
    print("한계·범위 (결함 주장 아님 — 전부 설정 `declared_limit_ids` 에 등재됨)")
    for limit in rep.limits:
        bound = ""
        if limit.case is not None:
            bound = f" [case={limit.case}]"
        if limit.unchk is not None:
            bound += f" [unchk={limit.unchk}]"
        print(f"  - [{limit.lid}]{bound} {limit.text}")
    print()
    print("OD-3 강제 범위 고지")
    print(
        "  - 검사됨: A(프로세스 전역 감사 hook[정본] + monkeypatch 열람 가드"
        "[심층 방어] + 소스 스캔: 리터럴 + AST 합성) · B(금지 아티팩트 전 항목) · "
        "C(파일 쓰기) · 러너 위치 앵커"
    )
    print("  - **미검사**: D(CI 미편입) · E(D0 승격 금지) — 기계 강제 없음")
    # 트랙 값은 **검증된 설정에서 파생**한다 (v2.9, 심판 v2.8 #5).  리터럴로
    # 적으면 `SELF-3` 이 평가하는 값과 고지가 갈린다.
    exit_root_track = config.cfg_pairs(cfg, "required_deferrals").get(
        "L-EXIT-ROOT", "<미등재>"
    )
    print(
        "  - **미검사(종단)**: 최종 종료 판정 자체 — 같은 프로세스 안에서 "
        "`exit_status` 재바인딩을 검출할 수 없다 (`L-EXIT-ROOT`).  해소는 별도 "
        f"프로세스의 외부 검증자뿐이며 owner track `{exit_root_track}` 로 이연 "
        "등재했다 (설정 `required_deferrals` 파생 — 러너는 두 설정 줄의 일치만 "
        "보고 그 트랙 값 자체는 고정하지 않는다).  이 러너는 최종 exit 을 "
        "자기증명하지 않는다."
    )
    print(
        f"  - 러너 위치: {Path(__file__).resolve().relative_to(_REPO_ROOT)} (`proto/` 밖)"
    )
    print(
        f"  - 감사 hook 정책: {audit_guard.policy()} — `proto` import 이전부터 "
        "armed 이며 해제 불가.  **그 '이전' 의 정확한 경계와 그 앞 구간에서 "
        "실제 I/O 가 가능하다는 사실은 `L-AUDIT-BOOTSTRAP` 이 등재한다.**"
    )
    print()
    # **세 발견 채널이 전부 exit 에 닿는다** (v2.7, 심판 #1/#2).
    #   ⑴ Case 양방향 성립 여부
    #   ⑵ 대조군 창 **밖**에서 가드가 기록한 위반 + 정책 상태 이상
    #   ⑶ 앵커 드리프트 — `collect_self_checks()` 의 단일 항과 **독립**이다
    # 배선 자체가 실재하는지는 `SELF-3` 이 이 파일의 AST 에서 파생해 관측한다.
    failed = [case for case in rep.cases if not case.ok]
    violations = operational_violations(cfg, recorder, read_recorder)
    anchor_failures = anchor_report_failures(rep.anchors)

    print(f"대조군 {len(rep.cases)}건 중 양방향 성립 {len(rep.cases) - len(failed)}건")
    if failed:
        print(f"미성립: {[case.tid for case in failed]}")
    print(f"OD-3-C 파일 쓰기 시도 기록(monkeypatch 층): {recorder.attempts or '없음'}")
    print(
        f"OD-3-A 코퍼스·register 열람 시도 기록(monkeypatch 층): "
        f"{read_recorder.attempts or '없음'}"
    )
    print(
        f"감사 hook 차단 기록 — 대조군 프로브 밖: 열람 "
        f"{audit_guard.blocked_reads or '없음'} · 쓰기 "
        f"{audit_guard.blocked_writes or '없음'}"
    )
    print(
        f"감사 hook 차단 기록 — 인가된 프로브 창 안(토큰별 열람:쓰기): "
        f"{audit_guard.probe_record_counts() or '없음'} · 인가되지 않은 창 "
        f"{audit_guard.unsanctioned_windows or '없음'} · 대조군 이관(창 밖 의도적) "
        f"{len(audit_guard.sanctioned_reads)}건"
    )
    anchors = " · ".join(f"{key}={value}" for key, value in rep.anchors.items())
    print(f"산문 앵커 대조: {anchors or '계산되지 않음'}")
    print(f"운영 경계 위반(대조군 밖) — exit 결속: {violations or '없음'}")
    print(f"앵커 드리프트 — exit 결속: {anchor_failures or '없음'}")
    return exit_status(failed, violations, anchor_failures)


if __name__ == "__main__":
    raise SystemExit(main())
