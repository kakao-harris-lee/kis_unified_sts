# 작업 메모 — ADR-002 시리즈 품질 방법론·결함-클래스 총화 플레이북 (2026-07-29)

> **문서 성격 (규범성 선언)**: 본 문서는 **비규범 작업 메모**다. **비준(ratification) 대상이 아니며**,
> GOV-001의 세 거버넌스 행위(비준 / ADR acceptance / live authorization) 중 어느 것도 수행하지 않는다.
> ADR·RFC·VER·register의 어떤 상태도 변경하지 않고, 어떤 EV 항목도 이동시키지 않으며, 새 술어·모델·
> 게이트를 정의하지 않는다. 본 문서의 유일한 산출은 **ADR-002 시리즈 30개 설계 사이클(#1~#30)에서
> 확립된 품질 파이프라인·결함 클래스·검증 레인·운영 규칙의 총화**이며, 후속 엔진 층(Part 2/3) 사이클의
> **브리프 입력물**이다. 여기 기록된 어떤 규칙도 규율 개정 자체가 아니라, 각 사이클이 이미 확립한 규율의
> 재정리다. 규율의 정식 개정은 별도 게이트 소관이다(FD §10.2 후속 권고와 동일 취급).

> **본 문서의 자기 규율**: 본 총화가 정리하는 최상위 결함 클래스가 **anti-phantom**(발원 #27 FD)이므로,
> 본 문서의 **모든 발원·재발 주장은 인용 전 grep/Read 실측**을 거쳤다. INDEX는 설계 번호(`#N`)로,
> 설계 문서는 `§`·`INV-###`·template field name 등 **안정 앵커**로 인용한다(문서-내부 line 번호는 드리프트
> 하므로 보조로만; 이는 §3의 인용-드리프트 레인 자체의 적용이다). 코드 seam만 committed `file:line`.
> 아래 "봉인 패턴 (형태)" 블록은 시리즈가 확립한 봉인의 **형태**이지 repo verbatim 코드 인용이 아니다.

---

## 0. 문서 성격·사용법 — 역할별 참조 절 지도

이 플레이북은 **읽는 문서가 아니라 복사하는 문서**다. 후속 엔진 층 사이클을 시작하는 각 역할은
자기 브리프에 아래 지정 절을 그대로 복사해 게이트로 사용한다. 각 절은 표 중심이라 복사 후 즉시
체크리스트로 쓸 수 있다.

| 역할 (에이전트) | 복사할 절 | 사용 목적 | 하지 말 것 |
|---|---|---|---|
| **저작자** (deep-reasoner) | §2 전부 + 부록 B(§0.5 상속) + §4 | 알려진 결함 클래스를 **선제 봉합**하고 발원·재발 앵커를 자기 §0.5에 병기 | 인용 전 미grep·부재 주장 미검증(anti-phantom) |
| **1차 심사** (오케스트레이터) | §1.1 + §3 + §2-Family C | 저작자 고하중 인용을 **재실측**·phantom/드리프트 사전 제거 | 저작자 카운트·앵커 무검증 통과 |
| **독립 비평 리뷰어** (별도 컨텍스트) | §2 전부 + §1.2 + §2 각 family "리뷰어 사냥 순서" | 32개 클래스를 공격 벡터로 **적대적** 사냥 | 발원 앵커 없이 재발 단정·인용 미실측 |
| **구현자** (executor) | §3 전부 + §2 각 family "봉인 패턴" + §4 게이트 환경 | 극성·∅·구조 파생 준수·뮤테이션 KILLED 실측 | 뮤턴트 SURVIVED 방치·export 표면만 잠금 |
| **적대적 코드 리뷰어** (별도 컨텍스트) | §3 뮤테이션 실효성 + §2 전부 + §4 "에라타 vs 코드 약화" | **구현 fail-open** 사냥(배선 결함) | 리뷰어 처방 무검증 강요·구현이 계약보다 안전한데 코드 약화 |
| **게이트** (오케스트레이터) | §1.1 8~10단계 + §3 + §4 게이트 환경 | pytest·firewall·drift-lock **직접 재검증**·에라타·메모리 기록 | 리뷰어 판정 무재검증 신뢰 |

**적용 순서 원칙**: §2는 "이미 발생한 결함의 백로그"다. 새 사이클은 §2를 선제 봉합 목록으로 소비하고,
§2에 **없는** 새 결함만이 그 사이클의 진짜 발견이다. 시리즈 후반 문서일수록 §2 재발 0이 목표다 — #11
protective가 #10 defect class 미재발을 달성한 것이 그 실증(INDEX #11 항목: "#10 defect class 미재발").
반대 방향의 실패도 기록됐다 — #23 CUR·#28 SIR·#30 STM이 "스스로 봉합 선언한 defect class를 자기 문서에
재발"시킨 사례(§6 재발 방지 실적 참조)로, **선제 봉합 목록은 읽는 것으로 부족하고 grep 회귀로 잠가야**
한다는 교훈이다.

---

## 1. 품질 파이프라인 구조

### 1.1 10단계 파이프라인 (저작 → 메모리 기록)

각 사이클은 아래 순서를 통과한다. 단계 사이의 **컨텍스트 분리**가 핵심 안전 장치다(§1.2).

| # | 단계 | 주체 | 산출·게이트 |
|---|---|---|---|
| 1 | **저작** | deep-reasoner (Opus, effort max) | 설계 초안 v1.0 — ADR 조항별 EV-L1 도달성 매핑·모델·술어·§0.5 선제봉합·§3.5 소유권 분할 |
| 2 | **1차 심사** | 오케스트레이터 직접 | 고하중 인용 **재실측**·명백한 phantom/드리프트 사전 제거(독립 리뷰 전 필터) |
| 3 | **독립 비평 리뷰** | 별도 컨텍스트·적대적 리뷰어 | REJECT / REVISE / ACCEPT-WITH-* 판정 + CRITICAL/MAJOR/MINOR/Gap 결함 목록 |
| 4 | **개정** | 원저작자 재개 (세션 사망 시 신규 에이전트가 디스크 실측 재개·§4) | v1.1 — 전 findings 반영, 처방 반론은 1차 소스 재실측 후(§4) |
| 5 | **위임 자동 비준** | 오케스트레이터 (운영자 2026-07-25 위임 지시) | 독립 리뷰 통과·upgrade 조건 충족 검증 후 "운영자 위임 자동 비준"으로 기록·즉시 진행 |
| 6 | **구현** | executor (Opus) | 모델·술어·property·seam·canary·뮤테이션 |
| 7 | **적대적 코드 리뷰** | 별도 컨텍스트 코드 리뷰어 | ACCEPT-WITH-FIXES / -MINOR + **구현 fail-open**(설계에 없던 배선 결함) 사냥 |
| 8 | **처방 적용** | executor / 오케스트레이터 | 뮤턴트 KILLED 전환 실측·생존 뮤턴트 봉인 |
| 9 | **게이트** | 오케스트레이터 직접 | pytest·firewall check·drift-lock 재검증·"구현이 계약보다 안전하면 에라타"(§4) |
| 10 | **에라타 + 메모리 기록** | 오케스트레이터 | 인용 정정 에라타(의미 무변경)·메모리에 사이클 총화 1행 |

**단계 3과 7의 비대칭**이 방법론의 핵심 발견이다: 설계 리뷰(3)는 원리적으로 구현 배선 결함을 볼 수 없고,
코드 리뷰(7)는 계약 소유권 결함을 볼 수 없다. 그래서 **두 레인 모두** 통과해도 잔여가 남을 수 있으며(#14
IOC: 설계 리뷰 통과 후 코드 리뷰 MAJOR-1이 truthy 구조봉인 미채택을 침묵 통과 → 구조 가드로 사후 봉인,
INDEX #14 항목), 그 잔여를 §3 뮤테이션 실효성이 3차로 잡는다.

### 1.2 역할 분리 원칙 (자기승인 금지)

- **저작 레인 ⊥ 리뷰 레인**: 저작(1)과 독립 비평(3)·적대적 코드 리뷰(7)는 **별도 컨텍스트**. 같은 활성
  컨텍스트에서 자기 저작을 승인하지 않는다(글로벌 `<execution_protocols>` 준수).
- **설계 리뷰 ⊥ 코드 리뷰**: 전자는 계약·모델·소유권, 후자는 **구현 fail-open**. FD 코드리뷰 MAJOR가
  그 분리의 실증 — anti-phantom이 export 표면만 잠그고 서브모듈 저작 7/8은 SURVIVED였다(INDEX #27 항목·
  §3 저작-레벨 스윕).
- **오케스트레이터 = 최종 재검증자**: 게이트(9)는 리뷰어 판정을 신뢰하지 않고 **직접 재실측**한다(리뷰어
  라인 주장 재실측으로 확정/반증 — WDR 5건 라인 재실측, INDEX #26 항목).
- **처방 ≠ 명령**: 리뷰어 처방도 1차 소스 재실측 후 반론 가능(§4). SCI에서 리뷰어 단일-헬퍼 처방을
  실측 반증하고 리뷰어가 "저작자가 옳다" UPHOLD한 사례가 이 원칙의 정점(INDEX #29 항목).

### 1.3 수렴 실적 통계 (INDEX 30 항목 실측)

**설계 첫-라운드 독립 비평 판정 분포**(#1~#30 + 병렬 트랙 DSL·Time; #3=EV-L1 모델계층+하네스는 독립
리뷰 기록 부재라 제외):

| 판정 | 건수 | 사이클 (INDEX 항목) |
|---|---|---|
| **REJECT** | 6 | #1(firewall 전이 import C2)·#2(shared.config 전이 C1)·#6(MAJOR 3)·#8(fixture↔INV 모순)·#27 FD(C3)·#29 SCI(C3, 다-라운드) |
| **REVISE** | 20 | #7·#10·#11·#12·#13·#14·#15·#16·#17·#18·#19·#20·#21·#22·#23·#24·#25·#26·#28·#30 |
| **ACCEPT-WITH-MINOR** | 4 | #4 evidence·#5 rcl(시리즈 최초 first-pass 무-REJECT)·#9 recon·DSL |
| **ACCEPT-WITH-RESERVATIONS** | 1 | Time(MAJOR 1 좌표계 혼동) |

**핵심 통계**:
- **무조건 first-pass ACCEPT = 0건.** 31개 리뷰 전부 최소 MINOR 이상 findings. 저작 품질과 무관하게
  적대적 리뷰가 항상 무언가를 발견한다는 실증(RLP·VTG는 MAJOR 0·MINOR만인데도 REVISE 판정 — 판정
  등급은 리뷰어의 blocking 여부 재량; INDEX #25·#19 항목).
- **CRITICAL 보유 설계 리뷰 = 11건**: #1·#2·#8·#16·#18·#21·#24·#27·#28·#29·#30. 시리즈 중반(#13~#17)은
  MAJOR-only로 안정화됐다가 다-leg/거버넌스 문서(#18·#21·#24·#27~#30)에서 CRITICAL 재발 — 표면적 난이도가
  아니라 **동시 상태·소유권 경계·부재 주장**이 결함 밀도를 결정.
- **다-라운드 = #29 SCI 1건**: REJECT → v1.1 REVISE(신규 MAJOR 4) → v1.2 ACCEPT-WITH-MINOR → v1.3
  마이크로. 나머지는 단일 라운드 → v1.1 → 비준(INDEX #29 항목).
- **개정 수렴은 반론 0이 지배적**: 대부분 사이클이 v1.1에서 findings "전량 반영·반론 0". 반론이 정당했던
  경우는 소수지만 결정적(§4 리뷰어 처방 기계적 수용 금지).

**첫-라운드 결함 밀도 상위**(설계 리뷰 CRITICAL+MAJOR 합, INDEX 실측): #16 AFG(C1+M9=10)·#21 NT(C2+M8=10)·
#27 FD(C3+M8=11)·#28 SIR(C2+M8=10)·#29 SCI v1.0(C3+M9=12)·#30 STM(C2+M7=9). 전부 **다-leg 트랜잭션·부재
주장·좌표 소유권**이 얽힌 문서다.

**코드 리뷰 라운드**(단계 7·설계 리뷰와 독립·메모리+INDEX):

| 사이클 | 코드 리뷰 결과 | 대표 구현 fail-open |
|---|---|---|
| #2 capsule | REJECT | fail-open 3건(개정) |
| #4 evidence | REJECT | ReplayCapsule fail-open 3건(개정) |
| #16 AFG | REJECT | assume-grant fall-through(C1) + M3 → 에라타 + 뮤테이션 5종 FAIL 전환 |
| #18 PR | ACCEPT-WITH-FIXES | enum value-swap 뮤턴트 green(검증 공백)·seam 부재 |
| #21 NT | ACCEPT-WITH-MINOR | 뮤테이션 51/57(시리즈 최고 밀도)·이전 발견 재발 0 |
| #22 EGRESS | ACCEPT-WITH-FIXES | lone-signer role 무보수(순서의존 leader 우회)·`expired is not True` 극성 |
| #23 CUR | ACCEPT-WITH-MINOR | 출하 fail-open 0·극성 `is not True` 잔존 0 |
| #24 PTF | ACCEPT-WITH-MINOR | 계약 상속(cross-obligation proof 재사용)·13 등가 뮤턴트 전수 열거 |
| #25 RLP | ACCEPT-WITH-FIXES | wildcard denylist 누수·recovery None⇒live 극성 |
| #26 WDR | ACCEPT-WITH-FIXES | §10 field-group 4개 + prohibited_inferences 통째 누락 |
| #27 FD | ACCEPT-WITH-FIXES | anti-phantom이 export 표면만 잠금(서브모듈 SURVIVED) |

추세: 초기(#2·#4·#16)는 코드 REJECT + fail-open 다수 → 후기는 ACCEPT-WITH-FIXES/-MINOR로 **출하 fail-open
0**에 수렴. 뮤테이션 밀도(#21 51/57)와 등가 뮤턴트 전수 열거(#24)가 코드 리뷰 실효성의 지표.

---

## 2. 결함-클래스 카탈로그 (32종·6 family)

**사용법**: 각 클래스는 `정의 / 발원 / 재발 / 실증 / 봉인 / mandated test`. 발원·재발 앵커는 전부 grep 실측.
`SIR§11`·`STM§11`은 두 문서의 "선제 defect-class 봉합" 표(이미 확립된 시리즈 총화 — 본 카탈로그의 1차
소스). `IDX#N`=INDEX 설계 항목. 각 family 뒤에 **봉인 패턴 (형태)**와 **리뷰어 사냥 순서**를 병기한다.

**family × 포착 단계 매트릭스** (어느 파이프라인 단계가 어느 family를 잡는가 — 각 역할의 책임 지도):

| family | 1차 심사 | 설계 리뷰 | 코드 리뷰 | 뮤테이션 | 실측 근거 |
|---|---|---|---|---|---|
| **2.A 극성·truthy·None** | — | ●(#13·#18·#30 C1) | ●(#22·#23·#25) | ●(극성 반전) | 3 단계 전부 — 최다 재발이라 다중 방어 필요 |
| **2.B ∅·완전성·전수** | — | ●(#8·#15·#26·#29·#30) | ○ | ●(∅ 반전·게이트 제거) | 주로 설계 리뷰 + 뮤테이션 |
| **2.C phantom·anchor·드리프트** | ●(고하중 인용 재실측) | ●(#27·#28) | ●(drift-lock 구현) | ○ | **1차 심사가 1차 방어**·구현 drift-lock이 최후(#27 §10.2) |
| **2.D identity·구조·시그니처** | — | ●(#18·#21·#24) | ●(#16·#24) | ●(value-swap) | 설계+코드+뮤테이션(부분 시그니처는 value-swap green) |
| **2.E 극성 반전·denylist** | — | ●(#16) | ●(#25) | ●(변형 우회) | 설계 검산표 + 코드 정규화 |
| **2.F seam·edge·over-realization** | ○ | ●(§3.5 분할표) | ○ | — | 설계 리뷰 + 게이트 register 전수 계수 |

(●=주 포착 단계·○=보조·—=해당 없음.) phantom/anchor(2.C)만 **1차 심사가 1차 방어선**이고, 나머지는 설계
리뷰가 1차다. 어느 family도 단일 단계로는 완결 안 됨 — §6 역작동 사례가 그 이유.

### 2.A 극성 · truthy · None (fail-open 최다 발생원)

**기전**: 안전 판정은 3-상태(allow / deny / unknown)인데 Python의 truthy·`is not True`가 unknown을 조용히
allow로 접는다. 이 family는 시리즈 fail-open의 최대 발생원이며 #13부터 #30까지 반복 재발했다.

| 클래스 | 정의 | 발원 | 재발 | 실증 (1줄) | 봉인 처방 | mandated test |
|---|---|---|---|---|---|---|
| **truthy-sentinel fail-open** | tri-state StrEnum(UNKNOWN 포함)이 `if x:`에서 truthy로 평가 | #13 ARE (IDX#13) | #14 IOC M1 구조봉인·전 후속 어휘 | UNKNOWN 멤버가 non-empty string이라 truthy → UNKNOWN이 게이트 통과 | `_NonTruthyStrEnum`·`__bool__ ⇒ TypeError`·`if snap.aggregate_result:` 1순위 방어 (STM§11) | `test_bool_raises`·`if x:` 사용처 grep 0 |
| **음극성 bool\|None은 `is False`만** | 음극성 clear 플래그를 `is not True`로 소비 | #18 PR 극성 규율 신설 (IDX#18) | #22·#23 M-3·#25 (SIR§11·STM§11) | `excluded/expired/revoked/consumed is not True`면 None/missing이 "cleared"로 오취급 → fail-open | 음극성=`is False`만·양극성 allow=`is True`·None 양쪽 deny (SCI §0.5-5) | `test_*_polarity`·`is not True` 부재 grep·None 픽스처 |
| **None-축 사각 (표지 None 게이트)** | Enum\|None 표지를 `is not True`/truthy로 접어 None 통과 | #30 STM v1.0 C1 (STM§11) | — | 노른자가 자기 극성표와 모순되게 `excluded is not True`로 필터 → `excluded=None`(unknown) 통과·INV-002 위반 | 필터 `is False` / 게이트 `is not False` 분리·`=None` 각 conjunct mandated | `excluded=None` 두 conjunct 픽스처 |
| **truthy 오독 접기 (`is not DENY`류)** | 다-값 결과에서 non-DENY를 full-permission으로 접음 | #19 VTG (IDX#19) | #30 STM ordering 3치 접기 (STM§11) | `RESTRICTED_PROTECTIVE_ONLY`를 truthy로 오독 → full-permission 위험; send-race 3치(deny/safe/불가) 미접기 | identity 명시 비교·3치 미접기(증명불가≠증명safe) | 4-값 각 멤버 truthy 투영 canary |

**봉인 패턴 (형태)**:
```
# tri-state 어휘: truthy 접근 자체를 타입으로 봉인
class ConformanceResult(_NonTruthyStrEnum):  # __bool__ ⇒ raise TypeError
    CONFORMING = "conforming"; RESTRICTED = "restricted"
    NON_CONFORMING = "non_conforming"; UNKNOWN = "unknown"
# 소비: 양성 identity만
allow = (result is ConformanceResult.CONFORMING)          # 양극성 allow = is <MEMBER>
# 음극성 clear 플래그: is False만 (None/missing은 clear 아님)
is_clear = (excluded is False)          # 필터: 확정 clear만
still_active = (excluded is not False)  # 게이트: unknown은 여전히 active로 보수
```

**리뷰어 사냥 순서**: (1) tri-state enum이 `if x:`/`x or y`/`not x`로 소비되는 곳 grep, (2) 음극성 필드
(`excluded`·`expired`·`revoked`·`consumed`·`suppressed`)의 `is not True` grep, (3) 각 음극성 conjunct에
`=None` 픽스처가 있는지 확인(없으면 None-축 사각 의심), (4) 다-값 결과의 `!= DENY`/`not ... DENY` grep.

### 2.B 공집합 · 완전성 · 전수 (vacuous pass 계열)

**기전**: 빈 집합·미표현 차원·미매핑 멤버는 "검사할 것이 없음"을 "위반 없음"으로 접는다(`all([]) == True`).
방향이 반대인 함정도 있다 — ∅를 무조건 deny하면 ADR이 명시 허용한 explicit-empty를 과잉 봉합(#26 WDR).

| 클래스 | 정의 | 발원 | 재발 | 실증 (1줄) | 봉인 처방 | mandated test |
|---|---|---|---|---|---|---|
| **∅-vacuous 단방향 seal** | 빈 집합이 술어를 공허-True로 통과 | #8·#15 (SIR§11) | 전 집합 술어 | `∅⊆∅` vacuous-True로 subset scope coverage 통과(liveauth §5.3) | ∅ **양방향**·금지 동사 전 커버리지 대조·양측 비어있지-않음 | 양측 ∅ + 한쪽 ∅ 각 픽스처 |
| **∅ 과잉봉합 (fail-closed 과잉)** | ∅ 가드가 ADR 명시 허용 explicit-empty까지 거부 | #26 WDR MAJOR-1 (IDX#26) | — | ∅ 거부 가드가 §13:364 명시 허용 explicit-empty Active Deviation Set을 과잉 거부(**방향 반대의 과잉 봉합**) | ∅ 거부 전 **applicable 측 확인**·explicit-empty 유효 (SIR§11) | explicit-empty 유효 픽스처 |
| **∅ 역방향 오적용** | 타 문서 ∅ 교훈을 극성 반대로 오적용 | #29 SCI v1.0 (SCI §0.5-2) | — | WDR explicit-empty 교훈을 SCI admitted-set에 역적용 → ADR explicit-empty 명시 **부재**인데 공허-True 허용 | ADR "explicit empty" **negative-grep**·명시 부재면 deny (SCI §5.9/§16 grep 0) | explicit-empty 부재 grep 회귀 |
| **두 ∅ 극성 반대 구별** | 같은 문서 내 두 ∅가 극성 반대인데 통일 처리 | #30 STM (STM§11) | — | coverage-∅(applicable 측 확인 deny)와 determinism-∅(관계 단독 valid-True)이 극성 반대 | 각 ∅ 극성 개별 판정 | coverage-∅ / determinism-∅ 분리 픽스처 |
| **미표현 요소 vacuous pass** | 미표현 차원/미매핑 요소가 완전성 검사 공허 통과 | #20·#23 (SIR§11·STM§11) | cur CONTEXT 누락 | 미표현 closure 차원·미매핑 obligation이 완전성 술어를 공허 통과; `DimensionKey`에 CONTEXT 누락(IDX#23) | 미표현⇒incomplete deny·enum에 전 §9 차원 편입 | DimensionKey==§9 3-원천 정합 property |
| **집합 단방향 비교** | 한 방향만 검사(역방향 누락) | #10 brokercap (SIR§11) | — | `applicable ⊆ member`만 검사·`closure ⊇ affected` 누락 | 양방향 부분집합 검사 | 양방향 위반 각 픽스처 |
| **enum 전 멤버 전수 매핑 누락** | closed enum 일부 멤버 미분기 | #21 NT C1 RecordPairKind (IDX#21) | 전 후속 disposition | `RecordPairKind` 5멤버 중 APPLIED_ONCE 도달 불가·DIVERGENT_EMISSION 미매핑 | 전 멤버 전수 분기(3/5/8/9/12-token) (SCI §0.5-6) | enum 멤버 수 == 분기 수 property |

**봉인 패턴 (형태)**:
```
# ∅ 양방향: "검사 대상 없음"과 "위반 없음"을 분리
if required_keys and not corpus:      # 요구는 있는데 코퍼스가 비면 → deny (공허 아님)
    return DENY
# 미표현 차원: enum이 § 차원 전수를 담아 vacuous 원천 봉쇄
assert set(DimensionKey) == set(ADR_SECTION_9_DIMENSIONS)   # property
# explicit-empty 허용은 ADR 명시가 있을 때만 (WDR과 SCI가 정반대)
empty_ok = adr_permits_explicit_empty and applicable_side_confirmed
```

**리뷰어 사냥 순서**: (1) `all(...)`·`⊆`·`issubset` 술어에 양측-∅ 픽스처가 있는지, (2) ∅ deny 가드가
ADR explicit-empty 명시(grep)를 확인하는지 — 명시 있으면 과잉봉합, 없으면 deny가 정답, (3) closed enum
멤버 수 == 분기 수 property 존재 여부, (4) 완전성 술어가 미표현/미매핑 요소를 incomplete로 접는지.

### 2.C phantom · anchor · 드리프트 (본 총화 최상위 클래스)

**기전**: 인용은 검증되지 않으면 **주장**일 뿐이다. 존재 인용은 grep으로 확인하면서 부재 주장("형제
미소유"·"타입 없음")은 확인하지 않는 **검증 비대칭**이 FD v1.0 REJECT의 유일 결함군이었다. 심볼명·필드명·
라인 앵커 모두 드리프트한다.

| 클래스 | 정의 | 발원 | 재발 | 실증 (1줄) | 봉인 처방 | mandated test |
|---|---|---|---|---|---|---|
| **anti-phantom (부재·존재 대칭 grep)** | 존재는 grep, 부재 주장은 미grep한 **검증 비대칭** | #27 FD §0.5 (FD §0.5·§10.2) | #28 SIR "반증된 부재"·#29 SCI "ptf 미착지" 거짓 | FD v1.0 REJECT의 유일 결함군(C1~C3)이 부재 주장 미검증; SIR은 cur INCIDENT 차원 "미소유"가 실은 보유(반증); SCI "ptf 미착지"가 posttrade 패키지명 미검색으로 거짓 | 부재 negative-grep(**디렉토리 토큰 + ADR 번호 문자열 양쪽**)·존재도 grep·유일-소유는 대안 전수 배제·무주인은 전역 grep 0 + Phase-0 등재 | negative-grep 회귀·anchor-resolution property |
| **phantom 존재 주장 (미검증 심볼명)** | 인용 심볼이 실재하지 않음(anti-phantom의 존재 축) | #27 FD §10.2 (FD §10.1·§10.2) | #12 SPG·#22 EGRESS·#15 IAP·#23 CUR·#29 SCI | `rcl.CapabilityClaim`(계약이 docstring 산문을 심볼명화) 실재는 `ClaimRecord`; SPG `EffectiveLimitVector`·EGRESS `proof_binds_command`(실재 `mutation_fence_holds`)·CUR `resolve_restrictive_latch`(실재 `monotonic_denial_no_revival`)·SCI `SafetyChangeInputs`(실재 `SemanticValidationInputs`) | 인용 대상 `git grep -l` 존재 확인·drift-lock 회귀(구현이 자동 봉인) | 형제 token 전수 resolve + phantom 부재 assert |
| **phantom self-report bool 필드** | 존재하지 않는 자기신고 bool을 술어 입력으로 가정 | #29 SCI C3 (SCI §5.4) | — | `source_continuity_proven`·`predecessor_conflict_present` 폐기(실재 필드 아님) | 구조 파생으로 대체(2.D 참조)·self-report bool 금지 | phantom 필드 부재 grep |
| **템플릿/계약 실명 드리프트** | 템플릿 필드명이 구현 실명과 드리프트 | #29 SCI (21건, IDX#29) | #16 WDR field-group | 템플릿 20필드가 구현 실명과 21건 드리프트 | §2.4 field-group 이름 그대로 복원·드리프트 anchor 명시 | field name drift-lock |
| **필드그룹 통째 누락** | 계약 field-group이 구현에서 통째 누락 | #26 WDR 코드리뷰 MAJOR-1 (WDR §10:297 field·에라타 로그) | — | §10 field-group 4개(9/11/12/13) + `prohibited_inferences` 통째 누락 → §2.4 이름 그대로 복원 | 복원 + REQUEST_FIELD_GROUPS 15그룹 드리프트 anchor | field-group 수 == 계약 수 property |
| **dead-row (선언+극성표+미소비 3중)** | 필드가 선언·극성표 등재됐으나 어떤 술어도 소비 안 함 | #29 SCI NEW-4+1b (SCI §5.5) | — | §5.5 `committed`/`current`/`compatibility_complete`/`restriction_state`가 dead-row 7 (선언만·미소비) | 미소비 필드를 술어 배선하거나 삭제·"3중 상태 금지" | 선언 필드 == 소비 필드 property |
| **인용-드리프트 (내부 line vs 안정 앵커)** | 문서-내부 라인으로 앵커 → 드리프트·off-by-one | #14 anchor·cur v1.1 (SCI §0.5-12) | #30 STM M7 (STM-INV 16 off-by-one) | STM-INV 앵커 16건 전수 off-by-one(공백행 인용) | 안정 ADR 조항·INV-###·template field name 앵커·수동전사 명시 | anchor 재실측·drift 테스트 |

**봉인 패턴 (형태)**:
```
# 부재 주장 = negative-grep (디렉토리 토큰 + ADR 번호 양쪽)
#   git grep -l ClosureDecisionResult tos/src/tos   ⇒ 빈 결과여야 "SIR 로컬 저작" 정당
#   ls tos/src/tos/posttrade                          ⇒ 존재해야 "ptf 착지" 주장 정당
# 존재 주장 = 형제 token 전수 resolve + phantom 부재 assert (drift-lock 테스트)
SIBLING_OWNER_TOKENS = ["rcl.ClaimRecord", ...]        # 실재 심볼만
def test_seam_siblings():
    for tok in SIBLING_OWNER_TOKENS: assert resolves(tok)
    assert not resolves("rcl.CapabilityClaim")          # phantom 부재 회귀 (FD §10.2)
```

**리뷰어 사냥 순서**: (1) 부재/무주인/유일-소유 주장마다 negative-grep 근거가 병기됐는지, (2) 인용 심볼명을
`git grep -l`로 실재 확인(계약이 docstring 산문을 심볼명으로 굳힌 경우 최다), (3) 템플릿 필드명 == 구현
실명 drift-lock, (4) 선언 필드 중 어떤 술어도 소비 안 하는 dead-row, (5) 앵커가 문서-내부 line인지 안정
ADR 조항인지.

### 2.D identity · 구조 파생 · 시그니처 도달성

**기전**: 안전 판정을 self-report(그 객체가 스스로 "나는 완전하다"고 신고한 bool/enum)에 의존하면 위조·
치환이 가능하다. 판정은 **구조**(binding 존재·magnitude 산술)에서 파생하고, 판정 입력은 **시그니처**에
전수 편입해야 한다(입력이 없으면 그 판정 항은 도달 불가한 죽은 조건).

| 클래스 | 정의 | 발원 | 재발 | 실증 (1줄) | 봉인 처방 | mandated test |
|---|---|---|---|---|---|---|
| **GRANT/ADMIT 양성 identity** | verdict을 명시 identity 없이 non-deny로 접어 통과 (fall-through) | #16 AFG C1 코드리뷰 (IDX#16) | 전 verdict 소비처 | assume-grant fall-through — `!= DENY`류로 ADMIT 아닌 값도 통과 | `is ADMIT`/`is GRANT` **양성 identity** 명시 비교 (SCI §0.5-4) | 비-ADMIT 멤버 통과 시도 canary |
| **구조 파생 > 자기신고** | 완전성/극성을 self-report enum/bool로 판정 → 위조 가능 | #18 PR·#21 NT (IDX#18·#21) | #29 SCI C3 | no-netting을 주입 flag 대신 `OverlapReservationClaim` outcome magnitude에서 구조 파생; split 극성을 enum 자기신고 대신 pre/post magnitude 파생 | 구조적 binding 존재·pre/post magnitude 파생 (SCI §0.5-7) | 자기신고 우회 뮤턴트·구조 파생 property |
| **주입 인자 identity 결합 게이트** | proof/증언이 대상 식별자 없이 재사용(cross-객체 대체) | #24 PTF 코드리뷰 MAJOR (PTF §11:320·에라타 v1.2) | #29 SCI | proof scope 6성분에 obligation 식별자 부재 → 다른 obligation의 proof 재사용 가능 → ADR §11:320 "exact obligation identity" 근거 봉인 | exact identity kwargs 바인딩·`release_artifact_identity_exact`(SCI) | cross-객체 proof 대체 뮤턴트 |
| **시그니처-판정 도달성 (인자 없는 판정 항 금지)** | 판정에 필요한 입력이 시그니처에 없어 판정 항 도달 불가 | #21 NT C1·#24 PTF C1 (SIR§11·STM§11) | #28 SIR C2·#29 SCI NEW-2·#30 STM | disposition 시그니처가 8/17만 수용(방지 메커니즘 내부 재발); SCI `scope_resolved` 미도달 → §5.4 시그니처에 `target_scope`+`scope_resolved` 추가 | 전 판정 입력을 시그니처에 편입(PTF 8→19입력·§4.8 22행 1:1) | 미수용 입력 스왑 뮤턴트 green이면 결함 |
| **좌표 비붕괴 (mutable lifecycle·주입 채널)** | 정당한 lifecycle 전이가 covered digest에 들어가 오탐; 두 축을 단일 좌표로 붕괴 | #8 orthostate·#7 liveauth·#6 authority (IDX#8·#7·#6) | — | ACTIVE→SUSPENDED 정당 전이가 covered digest 안이면 CRITICAL_CONFLICT 오탐; SA Epoch=Writer Epoch 좌표 붕괴 | lifecycle state를 covered digest **밖**·좌표 분리·관측별 fresh-id·주입 채널 load-bearing 유지 | 정당 전이 non-conflict + 좌표 교환 canary |

**봉인 패턴 (형태)**:
```
# 구조 파생 > 자기신고: outcome magnitude에서 no-netting을 증명 (self-report flag 아님)
netting_absent = (old_mag >= 0 and new_mag >= 0 and simultaneous_mag >= 0)  # 병존 비음수
# 시그니처 도달성: 판정에 필요한 입력을 전수 편입 (없으면 그 조건은 죽은 항)
def post_trade_disposition(rec, prior, proof, scope, cash_kind, ... ):  # 19 입력, §4.8 22행 1:1
    if scope_resolved is not True: return DENY          # scope가 인자라야 이 항이 도달 가능
# identity 결합: proof는 대상 obligation identity에 바인딩
proof_ok = (proof.obligation_identity == rec.obligation_identity)   # cross-객체 재사용 차단
```

**리뷰어 사냥 순서**: (1) 완전성/극성 판정이 self-report bool/enum에 의존하는지 — 있으면 구조 파생으로
대체 가능한지, (2) disposition/관계 술어 시그니처가 ADR 판정 입력을 **전수** 수용하는지(부분 수용이면
value-swap 뮤턴트가 green), (3) proof/증언이 대상 식별자에 바인딩되는지(cross-객체 대체 뮤턴트), (4)
mutable lifecycle이 covered digest에 들어가 정당 전이를 오탐하는지.

### 2.E 극성 반전 · denylist · 정규화

**기전**: ADR은 "smallest"와 "largest", "greatest credible scope"처럼 유사하나 극성 반대인 문구를 담는다.
전사 중 한 글자만 반전되면 fail-open이 박제된다. denylist는 자기 목록의 변형(대소문자·메타문자)에 샌다.

| 클래스 | 정의 | 발원 | 재발 | 실증 (1줄) | 봉인 처방 | mandated test |
|---|---|---|---|---|---|---|
| **유사문구 극성 반전** | ADR의 유사하나 반대 극성 문구를 전사 중 반전 | #16 AFG C1 (IDX#16) | 전 scope 판정 | §1:25 `smallest`(unknown dependency) vs §10:276 `largest`(broker 문서 불완전)를 v1.0이 fail-open 방향으로 반전 전사 | any-broaden-wins·smallest 반전 금지·극성 검산표(#16 이후 작동) (SCI §0.5-13) | greatest-scope drift mandated |
| **denylist 정규화 + 비전수 정직** | 자기 목록 변형(대소문자·메타문자)이 denylist 우회 | #25 RLP MAJOR-1 (STM§11) | #30 STM weak-kind | wildcard denylist가 "All"부터 샘 → `is_wildcard_value` strip+casefold+메타문자 거부; STM은 denylist→whitelist 반전(hard⇒hard 정확 보존·신규 멤버 자동 deny) | strip+casefold+메타문자 거부·denylist→whitelist 반전·비전수는 +Security 정직 명기 (SCI §0.5-8) | 변형 표기 우회 canary·신규 멤버 deny |
| **placeholder/sentinel 정규화 단일소스** | 정규화를 층마다 재선언 → 2층 방어가 1층으로 붕괴 | #29 SCI CRITICAL-1 (SCI §5·placeholder 정규화) | — | placeholder `strip().casefold()=="tbd"` 2층 방어를 층별 재선언이 1층으로 붕괴 | 정규화 단일 소스·층별 재선언 금지 | 층별 우회 뮤턴트 |

**봉인 패턴 (형태)**:
```
# denylist → whitelist 반전 (신규 멤버 자동 deny)
preserved = (bound_kind in ALLOWED_HARD_KINDS)   # 미지/신규 멤버는 자동으로 deny 측
# wildcard/placeholder: 정규화 단일 소스 + 비전수 정직
def is_wildcard_value(s): return _norm(s) in {"*", "all", "any"}  # strip+casefold+메타문자
#   신종 표기는 여기서 못 잡음을 정직 명기 → +Security/런타임 소유
# 극성 검산표: smallest ≠ largest 를 mandated drift 테스트로 고정
```

**리뷰어 사냥 순서**: (1) ADR "smallest/largest/greatest" 유사문구가 코드 극성과 일치하는지 검산표 대조,
(2) denylist가 자기 목록 대소문자/공백/메타문자 변형에 새는지 — whitelist 반전이 가능한지, (3) 정규화가
층마다 재선언돼 2층 방어가 붕괴하는지.

### 2.F seam · edge · scope 정직 (거버넌스 문서 특유)

**기전**: 거버넌스 문서(#19~#30)는 형제 패키지가 이미 소유한 개념을 재저작하기 쉽다. 재저작은 중복 좌표를
낳고, 중복 좌표는 두 곳이 갈라지면 fail-open이다. 또 predicate-only substrate가 어떤 EV도 안 닫는데
"완결"로 과대 표현하는 것도 이 family다.

| 클래스 | 정의 | 발원 | 재발 | 실증 (1줄) | 봉인 처방 | mandated test |
|---|---|---|---|---|---|---|
| **seam 재저작 (거버넌스 중복)** | 형제 소유 개념을 재저작(중복 좌표) | #19·#22·#23·#25·#26 (SIR§11·STM§11) | 전 거버넌스 문서 | 형제가 소유한 currentness/floor/policy를 재저작 | 소유 코드 실측·주입 소비·sibling edge 0·produced-value seam·§3.5 분할표 | seam drift-lock (§3) |
| **rcl edge 과잉 (불필요 import)** | capacity 산술 미수행인데 rcl CapacityVector import | #26 WDR (SIR§11·STM§11) | #28·#30 | §7:217 "deviation budget or accepted risk is never capacity" — L1 capacity 산술 미수행이면 edge 불요 | L1 capacity 산술 여부로 edge 판정·edge 0 | import-closure allowlist (§3) |
| **over-realization (INV 밀도 > L1 행)** | predicate-only substrate가 어떤 EV도 안 닫는데 "완결"로 과대 표현 | #28 SIR·#30 STM 특유 (SIR§11·STM§11) | 거버넌스 6부작 | §6 predicate-only substrate 9종이 어떤 SIR-EV/STM-EV도 닫지 않음·닫는 EV 0 | 닫는 EV 0 명기·predicate-only 규모 정직 경계·+Security 잔여 명기 | register 전수 계수 |
| **과대 주장 (authoring=acceptance)** | 저작을 acceptance로 오표현 | 전 시리즈 (SIR§11·STM§11) | — | "EV-L1-complete" 주장 | 닫는 EV 0·"EV-L1-complete 주장 금지" 명문 | register 실측 계수 |
| **grep head 절단 카운트 오류** | naive grep head 절단으로 register 카운트 오류 | #12 spg (SIR§11·STM§11) | — | register 카운트가 grep head로 절단되어 오계수 | register 전수 파싱(csv line 직접)·naive grep 금지 | 계수 過0·不0 property |
| **malformed-model construct 우회** | `model_construct`로 validator 우회 → incomplete가 positive claim과 공존 | #20 HAG (SIR§11·STM§11) | — | model_construct로 validator 건너뛴 incomplete 모델이 "ADMIT/CONFORMING" claim과 공존 | positive-claim + incomplete-scope validator + 술어 2층 | construct 우회 공존 시도 canary |
| **전칭 부정 반례 미배제** | 거버넌스 판정문이 전칭 부정·완전성 주장을 하면서 실재 반례를 본문에서 배제하지 않음 | GOV-001 G6 materiality 판정 (RFC-002 §32 / ARCHITECTURE-GATE-STATUS §3.25, 2026-08-05) | 같은 판정 사이클 **6문서·9구절**(계수 술어: "반례/제외 대상을 이름으로 지목하고 술어 차이로 배제하는 구절" 1건 = 1구절, 공백 정규화 grep 실측) — RFC-002 §32(pin-test 배제·13-vs-9 배제 2) · ARCHITECTURE-GATE-STATUS §3.25(동 2) · RFC-004 §15(문구 배제 1) · RFC-005 §16(1) · RFC-006 §17(문구 배제 1 + 수치 한정 1 = 2) · RFC-007 §16(retained-phrase 1). **RFC-003은 해당 구절 0**(§16 편집이 문구 대체를 수반하지 않음)이므로 계수에서 빠진다 | 실측 3건 — ① "No other Ratified document's cited-version pins name RFC-002 §26"은 문언상 참이나 Ratified RFC-000 v0.16 §5(`RFC-000-Trading-Constitution.md:144`)가 "(see RFC-002 §26)"으로 그 절을 상호참조한다; ② `83987c7d` 판정이 9건인데 실측 터치는 13파일(README·VER-002-001·VER-DEV-001·RFC-002 자신); ③ RFC-006 "no numeric appears on any changed line"은 `All 13 RFC-class baselines`의 13·기재일·절 번호 3건이 반례 — **이 인용은 시정 전 문자열이며 현행 코퍼스에 존재하지 않는다(grep 0). 본문은 처방 (d)를 적용해 "no bound-bearing numeric appears anywhere in the diff"로 좁히고 비구속 numeral 3건을 열거한 상태**이므로, 이 셀의 문자열로 현행 본문을 찾으려 하면 팬텀 앵커가 된다 | 전칭 부정·완전성 주장마다 (a) 반례 후보를 **구조 파생 grep으로 전수 수집**(자기신고·기억 금지), (b) 각 반례를 판정 본문에서 **명시 배제**, (c) 배제 근거를 **술어 차이**로 진술 — "반례가 무해하다"가 아니라 "술어를 만족하지 않는다"(G6는 *cited-version pin*에 걸리고 RFC-000의 것은 버전 없는 상호참조라 pin이 아님 / VER 명세는 GOV-001 G2로 ratification ladder 밖이라 "Ratified document" 술어 미충족), (d) 과잉 열거 대신 실질 술어로 좁힘("no numeric" → "no bound-bearing numeric") | 전칭 부정 문장별 반례-grep 0·주장 대상 전수 계수 == 판정 건수 |

**봉인 패턴 (형태)**:
```
# seam: 형제 소유 값은 주입 소비 (재저작 금지) — §3.5 소유권 분할표가 근거
def stm_predicate(..., dimension_floor_current: bool | None):   # cur이 소유·주입
    ...   # STM은 값 생산자, 완전성 판정은 cur 소유 (재저작 0·sibling edge 0)
# over-realization: 닫는 EV 0을 명문화
#   "이 predicate substrate는 어떤 STM-EV도 닫지 않는다; EV-L1-complete 주장 금지"
```

**리뷰어 사냥 순서**: (1) 형제가 소유한 개념(currentness·floor·policy·capacity)을 재저작했는지 §3.5
분할표 대조, (2) rcl CapacityVector import가 실제 capacity 산술을 수반하는지(안 하면 edge 과잉), (3)
predicate-only substrate가 "완결"로 과대 표현됐는지 — 닫는 EV 계수, (4) register 카운트가 전수 파싱인지
naive grep head인지, (5) 판정문의 전칭 부정("~하는 다른 것은 없다")·완전성 주장마다 반례 후보를 역방향
grep으로 사냥해 본문 명시 배제가 있는지 — 배제 근거가 술어 차이인지 무해성 판단인지 구별할 것.

### 2.G 사례 연구 — FD anti-phantom 사이클 (플래그십 결함 클래스의 발원·자기재발)

anti-phantom은 시리즈 최상위 결함 클래스이고, 그 발원인 FD #27은 방법론이 자기 자신을 잡은 유일한 기록이라
사례로 남긴다.

| 단계 | 사건 | 앵커 |
|---|---|---|
| 설계 리뷰 | FD v1.0이 **시리즈 첫 설계 REJECT(#8 이후)** — CRITICAL 3·MAJOR 8. 결함은 코드 품질이 아니라 **부재 주장 3건의 검증 비대칭**(존재는 grep·부재는 미grep). 코드 인용 40건 무결점·카운트 15종 전수 일치는 시리즈 최고 평가 | FD §0.5·§10.2, INDEX #27 |
| 규율 신설 | v1.1이 신규 defect class `anti-phantom` 명문화 — 부재 주장도 negative-grep 병기(§0.5) | FD §0.5 (부재도 grep) |
| 리뷰어 반론 | 리뷰어 인용 1건(VER §382)을 오케스트레이터가 실측 반론(추적성 매트릭스)해 확정 | INDEX #27 (리뷰어 인용 실측 반론) |
| 코드 리뷰 | 구현 후 코드 리뷰 MAJOR — anti-phantom이 **export 표면만 잠그고 서브모듈 저작 7/8 SURVIVED** → 저작-레벨 vars()+AST 스윕으로 상향 | INDEX #27 (검증-레인) |
| **자기재발** | 구현 단계 drift-lock이 계약의 **phantom 존재 주장**을 발견 — `rcl.CapabilityClaim`은 실재하지 않고 실명은 `ClaimRecord`(계약이 docstring 산문을 심볼명으로 굳힘). §0.5가 *부재* 주장용이었는데 대칭인 *존재* 주장은 미검증 사각이었음을 §10.2에 기록 | FD §10.1·§10.2 |
| 총화 | 규율을 "**부재 주장과 존재 주장 양방향 grep**"으로 확장 권고 → #28 SIR·#30 STM이 상속 | FD §10.2 후속 권고 |

**교훈**: (1) 완벽한 존재 인용(40건 무결점)도 부재 검증 비대칭이면 REJECT 가능. (2) 규율은 신설만으론
부족하고 **구현 drift-lock으로 잠가야** 자기 사각까지 덮인다("인용은 테스트로 잠근다"의 정당성 사후 입증).
(3) 방법론의 개선은 종종 방법론이 자기 자신에게 실패한 지점에서 나온다.

---

## 3. 검증 레인 표준

**원칙**: 인용은 테스트로 잠근다(FD §10.2 실증 — drift-lock이 저작 phantom을 자동 봉인). 각 레인은
**both-ways**(가드 발화 ∧ 정당 통과) + **뮤테이션 KILLED 실측**을 의무로 한다. 아래 9개 레인을 구현자·게이트
브리프에 그대로 복사한다.

### 3.1 import-closure allowlist (denylist 금지)
- **잠그는 것**: 미래 형제 패키지가 firewall 배제 목록에 새는 것. denylist는 신규 형제를 자동 차단 못 함.
- **표준**: `⊆ {canonical, ordering, rcl, 자기}` allowlist. 발원 #16 AFG M9, 선례 #19 VTG(firewall이
  미래 형제 `tos.pr` 자동 배제·INDEX #19), #17 SBR(배제 목록 afg 누락이 유일 가드 구멍·INDEX #17).
- **안티패턴**: `if pkg not in DENY_LIST` — 신규 형제가 DENY_LIST에 없어 통과.

### 3.2 저작-레벨 잠금 (export 표면 아님)
- **잠그는 것**: 서브모듈이 실제 저작한 심볼. export(`__all__`/`__init__`)만 잠그면 서브모듈은 SURVIVED.
- **표준**: 서브모듈 `vars()` + AST 스윕·멤버 타입 가드. 발원 #27 FD 코드리뷰(export 표면만 잠금 →
  서브모듈 7/8 SURVIVED, INDEX #27·SCI §0.5-10).

### 3.3 anchor-drift (디스크 실독 의무)
- **잠그는 것**: 인용 앵커. 복제본 대조는 vacuous(원본과 복제본이 같이 틀림).
- **표준**: 디스크 원문 Read·경로는 실명/glob·안정 ADR 조항/INV-###/template field name 앵커. 발원 #14·
  cur v1.1(SCI §0.5-12). 재발 #30 STM M7(STM-INV 16 앵커 전수 off-by-one·공백행 인용).

### 3.4 seam drift-lock (test-only import·인과 격리)
- **잠그는 것**: 형제 seam 심볼. 인과 격리(형제 코드 변경이 자기 테스트를 깨야 함).
- **표준**: test-only import로 형제 token 전수 resolve + phantom 부재 assert. 선례 #18 `test_seam_vtg`,
  #24 `test_seam_cur`(drift-lock 19토큰, INDEX #18·#24). 조건부 seam은 "착지 분기" 사전 명문화(§4).

### 3.5 negative-token (부재 주장·anti-phantom 존재 축)
- **잠그는 것**: "형제 미소유"·"타입 없음" 부재 주장.
- **표준**: `git grep -l <name> ⇒ 빈 결과` 회귀·동명이축 seal(같은 이름 다른 축). #28 SIR seal 3건(evidence
  GapStatus·spg 토큰·cur DimensionKey)·#30 STM seal 4건(SIR§11·STM§11).

### 3.6 극성 회귀 (`test_*_polarity`)
- **잠그는 것**: 음극성 fail-open.
- **표준**: `is not True` 부재 grep·음극성 각 None 픽스처. 발원 #18, 재발 봉인 #22·#23·#25(2.A). #23 CUR가
  `is not True → is False` ×2를 극성 회귀로 봉인(INDEX #23).

### 3.7 both-ways canary (가드 발화 ∧ 정당 통과)
- **잠그는 것**: 가드가 정당 흐름까지 막는 과잉봉합 / 은폐 분기.
- **표준**: 가드 발화 픽스처 ∧ 정당 통과 픽스처 쌍. #26 WDR ∅ 과잉봉합(2.B)·#28 "보수 분기 지배(픽스처
  은폐)"(정직-침묵/fail-open-시도 픽스처 각각 명시·STM§11).

### 3.8 뮤테이션 canary 실효성 (KILLED 실측 의무)
- **잠그는 것**: canary 자체가 무효(항상 green).
- **표준**: 극성 반전·enum swap·∅ 반전·게이트 제거·tri-state→bool 투영 뮤턴트 **KILLED 실측** + **등가
  뮤턴트 전수 열거**. 실적: #24 PTF(뮤테이션 124중 99 검출 + 13 등가 뮤턴트 전수 열거로 증명), #21 NT
  (51/57 시리즈 최고 밀도), #27 FD(11종 KILLED), #30 STM(뮤테이션 2건 FAIL 전환). 리뷰어는 실제 뮤턴트
  스펙을 로드해 KILLED 재확인(#24에서 검증). **"value-swap 뮤테이션 green"은 검증 공백의 증거**(#18 PR
  코드리뷰 MAJOR·INDEX #18).

### 3.9 planted-leak / escape canary
- **잠그는 것**: escape-closure/firewall 정적 분석의 실효.
- **표준**: 심어둔 leak/exec/import를 검출하는지 확인. 선례 DSL escape-checker(`ast` 정적분석·no exec/eval/
  import)·#1 firewall AST 게이트(INDEX #1·DSL).

---

## 4. 운영 규칙

| 규칙 | 내용 | 발원·실증 |
|---|---|---|
| **병렬 세션 조율** | 문서 번호 **선배정**(변경 금지)·메모리 **자기 섹션만** 편집·조건부 seam은 "착지 분기" **사전 명문화**(구현 시점 디스크 실측해 착지 시 seam 테스트, 미착지면 명시 이연) | 세션 A/B/C 3트랙(메모리)·SCI sir-seam 조건부(INDEX #29 "구현 시점 committed 여부 실측·조건부") |
| **스톨 / 세션한도 복구** | API 스트림 스톨·저작자 세션 사망 시 **디스크 실측 → 손실 판정 → SendMessage 트랜스크립트 재개**. 신규 에이전트가 디스크에서 재개(무손실) | WDR 스톨 3회 무손실 복구(메모리)·#21 NT 저작자 사망→신규 에이전트 재개(INDEX #21)·#22 EGRESS 세션 사망→오케스트레이터 self-check 대체(INDEX #22)·#27 FD 2회 복구(INDEX #27) |
| **리뷰어 처방 기계적 수용 금지** | 처방은 **1차 소스 재실측 후** 반론 가능. 구현이 리뷰어 bool 처방보다 우수하면 우수안 채택 | SCI ordering 단일-헬퍼 처방을 `_cmp equal⇒AMBIGUOUS` 실측으로 반증→2종 분리·리뷰어 UPHOLD(INDEX #29)·SCI C1 digest-binding "리뷰어 처방보다 우수"·FD 리뷰어 인용 1건(VER §382) 실측 반론(INDEX #27) |
| **에라타 vs 코드 약화** | 구현이 계약보다 **안전**하면 코드를 약화하지 말고 **에라타로 계약을 정직화** | WDR `is_expired/is_revoked` 미실현 → `economic_effect_persists` all-false shape 치환이 INV-012 역전 위험 회피 → 에라타 v1.2(메모리·INDEX #26)·FD 인용 정정 에라타 v1.2(FD §10.1, 의미 무변경) |
| **게이트 실행 환경** | pytest는 `PYTHONPATH=tos/src .venv/bin/python -m pytest`(pyenv=mypy 전용)·요약 억제 시 `rc + FAILED grep`으로 판정 | 메모리 기록(전 사이클 공통) |
| **register CSV-aware 파싱** | register는 **전수 파싱**(csv line 직접)·naive grep head 금지·부재는 디렉토리 토큰+ADR 번호 양쪽 | #12 grep head 절단(2.F)·SCI §0.5-1 M5(posttrade 패키지명 미검색 교훈) |

**세부 — 조건부 seam "착지 분기"**: 병렬 세션에서 형제 패키지가 아직 미착지일 수 있다. 이때 seam 테스트를
"착지 시 실행 / 미착지 시 명시 이연"으로 사전 분기해 두면, 구현 시점의 실제 착지 상태에 관계없이 무결하다
(SCI가 sir-seam을 이렇게 처리·INDEX #29). 미착지 형제의 코드를 인용하는 것은 phantom(§2.C)이므로 금지.

**세부 — 손실 무판정 재개**: 세션 사망 후 재개는 반드시 **디스크 실측이 먼저**다. 이전 컨텍스트의 기억이
아니라 디스크가 진실의 원천이다(WDR 3회·NT 1회·EGRESS 1회·FD 2회 전부 디스크 실측으로 무손실 복구).

---

## 5. 엔진 층 적용 한계 (경계 표시)

경로 평가 메모(`2026-07-29-tos-engine-completion-path-assessment.md`)가 확정한 난이도 구조상, 본 카탈로그의
적용 범위에는 **경계**가 있다. 본 절은 그 경계만 표시하며, 엔진 층 기능 분해·EV 매핑은 다루지 않는다.

**닫힌 세계 → 열린 세계 전이**(경로 평가 §2): Part 1(ADR-002)은 **닫힌 세계**였다 — 순수 술어, I/O 없음,
시간조차 `tos.time`이 데이터로 모델링. 이 세계에서 "문서 우선 → property → 뮤테이션" 파이프라인이 정확성을
**증명**했다. 엔진 층은 **열린 세계**라 정확성의 성격이 바뀐다(경험적 보정·배선 seam·비동기 장애·재도출 비용).

| 층 | 본 카탈로그 유효성 | 근거 |
|---|---|---|
| **술어·모델·계약 충실성** (극성·∅·enum 전수·anti-phantom·구조 파생·시그니처 도달성·좌표 비붕괴) | **그대로 유효** — 순수 판정 로직은 열린 세계에서도 동일 | §2 전 클래스가 순수 술어/계약 층. 경로 평가 §1 안전축 "이미 우위" |
| **경험적 정확성** (백테스트 충실도·체결·슬리피지) | **부분 커버** — property가 원리적으로 못 닿음 | 경로 평가 §2-1: 보정(calibration)은 실 KIS 체결 대조로만 검증·EV-L2+ 실행 증거 요구가 그 지점 |
| **통합 실패 모드** (술어↔이벤트 루프 배선) | **새 레인 필요** — fail-open이 술어 내부가 아니라 배선에 산다 | 경로 평가 §2-2: 28패키지 seam이 실제 이벤트 흐름 미수령. §3 seam drift-lock은 정적 구조만 잠금 |
| **비동기·장애** (단절·토큰 만료·부분체결·크래시 복구) | **새 레인 필요** — 결정론 리플레이·장애 주입 | 경로 평가 §3-4: property 외에 결정론 리플레이 시뮬·장애 주입·보정 게이트(WDR deviation budget 재사용) |

**요약**: §2 결함 클래스(술어·모델·계약)는 엔진 층에서도 **선제 봉합 목록으로 유효**하다. 특히 극성·∅·
anti-phantom·구조 파생은 언어·패러다임 불변이라 async·배선 코드에서도 동일하게 적용된다. 다만 열린 세계
고유 결함(배선 fail-open·비동기·보정 괴리)은 §3 검증 레인에 **리플레이·장애 주입·보정 게이트를 추가**해야
잡힌다(경로 평가 §3-4). **본 카탈로그는 이 새 레인을 정의하지 않는다** — 정의는 수직 슬라이스 설계 사이클
소관이다.

**명시 경계**: 엔진 층 **기능 분해·EV 매핑·수직 슬라이스 스코핑**은 별도 세션(수직 슬라이스 스코핑 survey —
`2026-07-29-tos-engine-vertical-slice-scoping-survey.md` 등)의 소관이며, **본 문서는 다루지 않는다.** 본
문서의 산출은 방법론·결함 클래스·검증 레인·운영 규칙의 총화에 한정된다.

---

## 6. 재발 방지 실적 (방법론 작동·역작동 증거)

선제 봉합 목록이 실제로 재발을 막았는지, 반대로 스스로 봉합 선언한 클래스가 재발했는지를 기록한다.
후자가 §3 "인용은 테스트로 잠근다"·"뮤테이션 KILLED 실측" 의무의 근거다.

| 방향 | 사이클 | 실적 | 앵커 |
|---|---|---|---|
| **막음** | #11 protective | #10 브로커캡 defect class 미재발 | INDEX #11 |
| **막음** | #9 recon | 리뷰어 사전 예측 공격 5개 전부 선제 봉합(전부 빗나감) | INDEX #9 |
| **막음** | #25 RLP | 시리즈 첫-초안 최고 성적(MAJOR 0)·over-realization/duplication 반론 전부 기각 | INDEX #25 |
| **막음** | #21 NT 코드리뷰 | 이전 사이클 발견(enum 바인딩·_ID_FIELD) 재발 0·뮤테이션 51/57 | INDEX #21 |
| **역작동** | #23 CUR | 스스로 봉합 선언한 defect class 3종(phantom·∅·극성)이 재발("인용 충실도 시리즈 최고"에도) | INDEX #23 |
| **역작동** | #28 SIR v1.0 | anti-phantom 규율을 자기 문서에 미적용(narrow-grep로 cur INCIDENT 차원 미소유 오주장) | INDEX #28·SIR §0.5 |
| **역작동** | #30 STM v1.0 C1 | §4.3 극성 규율의 자기위반이 노른자에 재발(`excluded is not True`) | STM§11·INDEX #30 |
| **역작동** | #27 FD §10.2 | anti-phantom 규율이 *부재*엔 적용됐으나 대칭인 *존재* 주장 미검증(자기 사각) | FD §10.2 |

**결론**: 규율은 **읽는 것으로 부족**하다. #23·#28·#30·#27이 전부 "스스로 봉합 선언한 클래스를 재발"시켰고,
전부 **구현 단계 grep 회귀/drift-lock/뮤테이션**이 사후에 잡았다. 그래서 §2 선제 봉합은 §3 검증 레인과
**쌍으로만** 유효하다 — 선제 봉합이 저작을, 검증 레인이 구현을 잠근다.

### 6.1 메타 교훈 3선 (32 클래스가 수렴하는 상위 원리·엔진 층 이월)

| 교훈 | 정의 | 관통 클래스 | 발원 |
|---|---|---|---|
| **① 부재도 grep한다** | 인용의 존재만이 아니라 **부재·무주인·유일-소유 주장도** 검증한다. 완벽한 존재 인용도 부재 비대칭이면 REJECT | 2.C 전부·2.F seam | #27 FD §0.5·§10.2 |
| **② 구조 > 자기신고** | 안전 판정은 self-report bool/enum이 아니라 **구조**(binding 존재·magnitude 산술·양성 identity·전수 시그니처)에서 파생 | 2.D 전부·2.A 양성 identity | #18 PR·#21 NT (SCI §0.5-7) |
| **③ 규율은 테스트로 잠근다** | 선제 봉합(§2)은 읽는 것으로 부족·**검증 레인(§3)과 쌍으로만** 유효(극성 회귀·drift-lock·뮤테이션 KILLED 실측) | 2.A·2.C·2.E 재발 봉인 | §6 역작동 4건·FD §10.2 |

이 3선은 언어·패러다임 불변이므로 엔진 층(열린 세계·§5)에서도 그대로 이월된다. 새로 필요한 것은 결함
클래스가 아니라 **검증 레인**(리플레이·장애 주입·보정 게이트)이다.

---

## 부록 A. 30-사이클 판정 원장 (INDEX 실측)

**용도**: 브리프에 붙여 각 결함 클래스의 발원 사이클을 한눈에 대조. `설계리뷰`=첫-라운드 독립 비평 판정
(C=CRITICAL·M=MAJOR). `#3`은 EV-L1 모델계층+하네스(독립 리뷰 기록 부재). DSL·Time은 병렬 트랙(무번호).

| # | 이름 (pkg) | ADR | 설계리뷰 | 핵심 결함 (발원 클래스) |
|---|---|---|---|---|
| 1 | boundary/firewall | IMPL-002 §2 | REJECT (C2) | backtest 허용 모듈의 전이 import(firewall closure) |
| 2 | capsule/snapshot (capsule) | -018 | REJECT (C1) | `shared.config` 전이 import(#1 동형)·코드 REJECT→fail-open 3 |
| 3 | EV-L1 모델계층+하네스 | — | (기록 부재) | 모델 계층·property 하네스 착수 |
| 4 | evidence-store (evidence) | -016 | ACCEPT-W-MINOR | id=f(digest) 미채택(§12 충돌 탐지 보존)·코드 REJECT→fail-open 3 |
| 5 | risk-capacity-ledger (rcl) | -012·-002 | ACCEPT-W-MINOR | 시리즈 최초 first-pass 무-REJECT·classify core PROMOTE |
| — | strategy-dsl (dsl) | RFC-008·DEV-001 | ACCEPT-W-MINOR | AST 순수 모델·escape-checker 정적분석 |
| — | trustworthy-time (time) | -008 | ACCEPT-W-RESERV (M1) | 좌표계 혼동(interval vs monotonic)·ordering PROMOTE |
| 6 | safety-authority (authority) | -003 | REJECT (M3) | exclusivity ∅ vacuous-True·주입 bool seam·PROMOTE dsl 누락 |
| 7 | live-authorization (liveauth) | -007 | REVISE (M2) | SAFE-053 compose 구현불가·lifecycle covered 제외(좌표 비붕괴) |
| 8 | orthogonal-state (orthostate) | -005 | REJECT | fixture clean↔CPL-5 위반 모순(∅ vacuous·좌표 비붕괴) |
| 9 | reconciliation-confidence (recon) | -006 | ACCEPT-W-MINOR | 리뷰어 사전 예측 5개 전부 빗나감·전 공격 선제 봉합 |
| 10 | broker-capability (brokercap) | -004 | REVISE (M2) | orthostate seam enum-basis 정정·집합 단방향(발원) |
| 11 | degraded/protective (protective) | -001 | REVISE (M1) | `protective_leases_reconciled` 정의 술어 부재(#7 class)·#10 미재발 |
| 12 | safety-profile-gov (spg) | -014 | REVISE (M3) | phantom `EffectiveLimitVector`·grep head 카운트 오류(발원) |
| 13 | aggregate-risk-proj (are) | -021 | REVISE (M1) | 자체 vector 이연 reducer 검증 불가·truthy-sentinel(발원) |
| 14 | intent-order-conf (ioc) | -020 | REVISE (M1) | truthy 구조봉인 미채택→`__bool__⇒TypeError`(구조봉인 승격) |
| 15 | proposal-approval (iap) | -023 | REVISE (M1) | phantom `OrderConformanceProof.approval_identity`·∅ 양방향 |
| 16 | action-flow-budget (afg) | -022 | REVISE (C1·M9) | smallest/largest 극성 반전 전사(발원)·assume-grant fall-through |
| 17 | startup-recovery (sbr) | -017 | REVISE (M2) | firewall 배제 목록 afg 누락(병렬 레이스)·"코드 부재" 거짓 |
| 18 | protective-replacement (replacement) | -011 | REVISE (C2) | old-취소 fail-open·no-netting 구조 파생·음극성 규율 신설(발원) |
| 19 | venue-tradability (venue) | -019 | REVISE (M0·MINOR4) | 인용-충실도만·RESTRICTED_PROTECTIVE_ONLY truthy 오독(발원) |
| 20 | human-authority (hag) | -015 | REVISE (M2) | 미표현 principal fail-open·malformed-model construct(발원) |
| 21 | non-trade (nontrade) | -010 | REVISE (C2) | RecordPairKind 5멤버 전수 매핑(발원)·split 극성 구조 파생 |
| 22 | egress-commit-proof (egress) | -013 | REVISE (M2) | phantom `proof_binds_command`·signer dedup 해석 B·음극성 재발 |
| 23 | currentness-fencing (cur) | -024 | REVISE (M3) | DimensionKey CONTEXT 누락(미표현 vacuous)·`is not True` 재발 |
| 24 | post-trade (posttrade) | -030 | REVISE (C1) | disposition 시그니처 8/17(도달성)·cross-obligation proof 재사용 |
| 25 | restricted-live (rlp) | -025 | REVISE (M0·MINOR3) | 첫-초안 최고 성적·wildcard denylist 누수(발원, 코드리뷰) |
| 26 | safety-waiver (wdr) | -026 | REVISE (M2) | ∅ 과잉봉합(발원)·field-group 누락(코드리뷰)·rcl edge 과잉(발원) |
| 27 | failure-domain (failuredomain) | -009 | REJECT (C3) | anti-phantom 발원(부재 주장 검증 비대칭)·phantom 존재 주장 |
| 28 | safety-incident (sir) | -027 | REVISE (C2) | "반증된 부재 주장"·시그니처 도달성 재발·over-realization |
| 29 | supply-chain (sci) | -029 | REJECT→REVISE→AWM | ∅ 역방향 오적용·placeholder 단일소스·dead-row·실명 드리프트 21 |
| 30 | safety-telemetry (stm) | -028 | REVISE (C2) | None-축 사각(음극성 자기위반)·두 ∅ 극성 반대·denylist→whitelist |

> **원장 주석 (INDEX 내부 표현 정합)**: #8 orthostate 항목은 INDEX에서 "시리즈 첫 CRITICAL"로 기술되나,
> #1(C2)·#2(C1)이 앞서 CRITICAL을 받았다. 두 기록은 #1/#2의 CRITICAL이 **import-firewall closure(구조적)**
> 이고 #8의 것이 **safety-model fail-open(의미론적)**이라는 축 차이로 정합한다("첫"은 후자 축 한정). FD
> 항목의 "#8 이후 첫 설계 REJECT"는 #8~#27 사이 REJECT 부재를 뜻하며 #1/#2/#6 REJECT와 무모순.

---

## 부록 B. §0.5 선제-봉합 체크리스트 (설계 문서 상속용 최신본)

새 설계 문서는 아래를 자기 §0.5로 상속하고, 각 항에 **자기 문서 앵커를 병기**한다(SCI §0.5 13항이 최신·
최다·1차 소스).

1. **anti-phantom** — 부재·존재 주장 모두 grep. 부재는 **디렉토리 토큰 + ADR 번호 양쪽**.
2. **∅-vacuous 양방향 deny** — 부재⇒deny. 단, ADR explicit-empty 명시 허용을 negative-grep 확인(WDR 역방향 교훈).
3. **truthy-sentinel** — tri-state StrEnum `__bool__⇒TypeError` + `is <MEMBER>` 명시 비교.
4. **양성 identity** — ADMIT/GRANT `is` 명시(fall-through 금지).
5. **음극성 `is False`만** — 음극성 clear는 `is False`만·`is not True` 금지·None 양쪽 deny.
6. **enum 전 멤버 전수 매핑** — closed enum 전 멤버 분기.
7. **구조 파생 > 자기신고** — 완전성/극성은 구조적 binding·magnitude에서 파생·self-report bool 금지.
8. **denylist 정규화 + 비전수 정직** — strip+casefold+메타문자 거부·신종은 +Security 정직 명기.
9. **import-closure allowlist** — denylist 금지.
10. **저작-레벨 잠금** — 서브모듈 vars()+AST(export 표면 아님).
11. **뮤테이션 canary 실효성** — both-ways + 극성/enum-swap/∅-반전/tri-state→bool 뮤턴트 KILLED + 등가 뮤턴트 열거.
12. **인용-드리프트 방지** — 안정 ADR 조항·INV-###·template field name 앵커.
13. **greatest-credible-scope 극성 일관성** — any-broaden-wins·smallest 반전 금지.

**본 총화가 SCI 13항에 추가하는 항(#28~#30 이후 확립)**: (14) **시그니처-판정 도달성** — 판정 입력을
시그니처에 전수 편입(#21·#24·#28·#29·#30). (15) **주입 인자 identity 결합** — proof/증언에 대상 식별자
바인딩(#24·#29). (16) **좌표 비붕괴** — mutable lifecycle을 covered digest 밖·두 축 단일 좌표 붕괴 금지
(#6·#7·#8). (17) **dead-row 금지** — 선언+극성표+미소비 3중 상태 금지(#29). (18) **필드그룹 통째 누락
방지** — 계약 field-group 이름 그대로 복원(#26). (19) **placeholder 정규화 단일소스**(#29).

---

## 부록 C. 아키텍처 seam / edge / PROMOTE 원장 (INDEX 실측·소유권 경계 지도)

**용도**: 새 문서가 형제 소유 개념을 재저작(2.F)하지 않도록 기존 edge/seam/PROMOTE 결정을 대조. `sibling
edge`=형제 패키지 import, `PROMOTE`=substrate 승격, `produced-value seam`=import 없이 값만 주입 소비.

| 사이클 | sibling edge | PROMOTE | 비고 (앵커) |
|---|---|---|---|
| #4 evidence | 0 | canonical/digest **PROMOTE**(capsule·evidence 공유) | id=f(digest) 미채택(§12 충돌 탐지) (INDEX #4) |
| #5 rcl | 0 | `classify_record_pair` core **PROMOTE** | RCL=capacity 유일 authority·evidence import 금지 (INDEX #5) |
| Time | 0 | ordering **PROMOTE→`tos.ordering`** | TIME-EV 0건 완결·predicate substrate만 (INDEX Time) |
| #6 authority | 1 (**→time**, 시리즈 첫 sibling→sibling) | IndependentIdArtifact→canonical(rcl+dsl) | SA Epoch≠Writer Epoch 좌표 비붕괴 (INDEX #6) |
| #7 liveauth | 2 (→authority compose·→time) | 0 | lifecycle covered 제외 (INDEX #7) |
| #8 orthostate | 3 (→rcl) | 0 | 관측별 fresh-id·CompositeState no-mixed-enum (INDEX #8) |
| #9 recon | 0 | CanonicalDecimal **PROMOTE rcl→canonical** | orthostate produced-bool seam (INDEX #9) |
| #10 brokercap | 0 | 0 | liveauth/recon/orthostate produced-value 상류 producer·MANDATED test-only cross-check ×3 (INDEX #10) |
| #11 protective | 0 | 0 | produced-bool seam 5슬롯·소유권 분할 7축 (INDEX #11) |
| #12 spg | 0 | 0 | 7-소비자 produced-bool/scalar seam·effective-limit min은 rcl 소유 (INDEX #12) |
| #13 ARE | 1 (→rcl, 4번째) | 0 | AdverseIncrement=CapacityVector REUSE (INDEX #13) |
| #14 IOC | 1 (→rcl, 5번째) | 0 | EconomicEffectEnvelope=CapacityVector REUSE (INDEX #14) |
| #15 IAP | 0 | 0 | control-plane gate·형제 타입 REUSE 불요 (INDEX #15) |
| #16 AFG | 1 (→rcl, 6번째) | 0 | ActionFlowVector=CapacityVector REUSE·import-closure allowlist 전환 (INDEX #16) |
| #17 SBR | 0 | 0 | recovery orchestrator·obligation-graph 로컬 저작(iap PROMOTE 기각) (INDEX #17) |
| #18 PR | 0 | 0 | CapacityVector REUSE 기각(are가 risk 축 소유) (INDEX #18) |
| #19 VTG | 0 | 0 | time.SessionContext REUSE 기각(INV-002 위반) (INDEX #19) |
| #20 HAG | 0 | 0 | 8 digest-bound·effective-principal collapse (INDEX #20) |
| #21 NT | 0 | 0 | canonical+ordering만·idempotency 3-계보 분리 (INDEX #21) |
| #22 EGRESS | 0 | 0 | rcl/ioc/evidence 재저작 금지 경계 코드 실측 (INDEX #22) |
| #23 CUR | 0 | 0 | 집계자/형제=leaf·DimensionKey 소유 (INDEX #23) |
| #24 PTF | 0 | 0 | nontrade 상호 이연 양방향·finality 4-성분 monotone (INDEX #24) |
| #25 RLP | 0 | 0 | content owner이자 피이연자(egress/cur가 이름으로 이연) (INDEX #25) |
| #26 WDR | 0 | 0 | greenfield 생산자·CapacityVector edge 명시 기각 (INDEX #26) |
| #27 FD | 0 | 0 | 통합·소유권-분할 레이어·§3.5 분할표가 노른자 (INDEX #27) |
| #28 SIR | 0 (rcl edge 0) | 0 | greenfield 생산자·committed forward seam 4-clade (INDEX #28) |
| #29 SCI | 0 (rcl edge 0) | 0 | greenfield + 유일 착지 하류 소비자·spg produced-value seam (INDEX #29) |
| #30 STM | 0 (rcl edge 0) | 0 | greenfield 생산자·forward committed 소비 4-clade (INDEX #30) |

**패턴**: sibling edge는 rcl `CapacityVector`(capacity 산술 필요 시)에만 집중(#6·#8·#13·#14·#16 = 6개 edge
중 대부분). 거버넌스 문서(#18~#30)는 **전부 edge 0·PROMOTE 0** — 형제 소유 개념을 **produced-value seam**
(import 없이 값 주입)으로 소비한다. capacity 산술을 안 하면 rcl import는 과잉(2.F).

---

## 부록 D. 극성 규율 한 장 (구현자 복사용)

| 필드 극성 | 예시 필드 | allow 판정 | deny/보수 판정 | 금지 |
|---|---|---|---|---|
| **양극성** (proven·resolved·complete·current) | `scope_resolved`·`manifest_resolved`·`current` | `x is True` | `x is not True ⇒ deny` (None/False/missing 전부 deny) | truthy `if x:` |
| **음극성** (excluded·expired·revoked·consumed·suppressed) | `excluded`·`expired`·`revoked` | (해당 없음 — 음극성은 allow 아님) | clear 확정 = `x is False`만 / 여전히 active = `x is not False` | `x is not True`로 clear 판정(None 새어나감) |
| **tri-state 결과** (ADMIT/DENY/UNKNOWN) | `ConformanceResult`·`AdmissionResult` | `x is <ALLOW_MEMBER>` (양성 identity) | 그 외 전부 deny | `x != DENY`·`if x:`·`not x` |
| **None (미표현)** | 모든 bool\|None | (allow 아님) | None ⇒ deny 수렴(양쪽) | None을 무시·기본 allow |

**불변 규칙 3줄**: (1) 양극성 allow는 `is True`, (2) 음극성 clear는 `is False`만, (3) None은 항상 deny 측.
`is not True`는 **양극성 deny에만** 안전하고 **음극성 clear에는 금지**(#18·#22·#23·#25·#30 재발 지점).
