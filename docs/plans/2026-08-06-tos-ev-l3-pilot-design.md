# 작업 메모 — tos-spec EV-L3 (Integrated System Fault Test) 파일럿 설계 (2026-08-06)

> **상태: 비준(RATIFIED) 2026-08-06** — 독립 비평 REVISE(CRITICAL 0·MAJOR 2·MINOR 4·NIT 3) → v1.1 전건
> 반영(반론 0) → 동일 리뷰어 델타 재검증 **RATIFY-READY**(전건 해소·신규 phantom 0·부작용 0·비차단 관찰
> 1건은 §4 CPL 확인 의무로 반영). 비준 주체: 오케스트레이터, ADR-002 시리즈 자동비준 위임(2026-07-25,
> Part-2/3 연장 2026-07-29) — 독립 비평 통과 검증 후 기록. ADR acceptance/live authorization은 별개 게이트.
>
> **v1.1** (독립 비평 REVISE 반영 — CRITICAL 0·MAJOR 2·MINOR 4·NIT 3; 개정 로그 §12). 전 finding을
> **1차 소스 재실측 후 반영**(리뷰어 실측 그대로 신뢰 금지 — 재측정 결과 리뷰어와 불일치 0). 핵심 방향
> 전환: **MAJOR-1** — outside 배치는 subprocess 금지에 의한 **강제가 아니라**, `multiprocessing` spawn
> 우회(inside)가 firewall 허용·기실사용(`tos/tests/test_import_closure.py:6`)이므로 **선택**이다; 채택
> 근거를 "subprocess 금지라서"에서 "**구조적 oracle 독립 우선(구조>convention)**"으로 재서술(§5.2/§5.3).
> **MAJOR-2** — crash 셀의 5차원 커밋 상태 전부 pin + Knowledge 다운그레이드 맵 결정론 파생 + 2층 독립
> 불변식(§4/§5.1). 개정은 문서 직접 편집(오케스트레이터 지시)·커밋 없음.
>
> **문서 성격 (v1.0 저작 초안 상속)**: 이 문서는 `STATE-EV-004`(ADR-002-005 AC-005-4 "Conservative Restart
> Reconstruction", EV-L3, NOT_IMPLEMENTED) 행에 **EV-L3 통합-크래시 층**을 얹는 **설계·실행 계획**이며,
> 그 실행의 부수 효과로 `STATE-EV-001`(EV-L1/2, READY)의 **R-1 durable-axis residual을 닫는** 경로를
> 확정한다. 코드는 작성하지 않는다(설계 계약 단계). **어떤 acceptance/PASS도 선언하지 않는다** — L3 실행이
> 완료돼도 독립 서명·VER §2.7 coverage argument(restart 축)·STATE-EV-004 자체의 network/identity 잔여
> 축·VER §3 complete-baseline가 남는다(§9).
>
> **성격**: EV-L2 파일럿(`docs/plans/2026-07-29-tos-ev-l2-pilot-design.md`)이 STATE-EV-001의 durable 축을
> 정직 이연한 그 residual(R-1)을, 본 파일럿이 **실 durable 저장 + 실 프로세스 경계**로 처음 방전한다. 이는
> 시리즈 최초의 **닫힌-세계 → 열린-세계 전이**(방법론 플레이북 §5:428) — tos/ 최초의 실 I/O·실 크래시.
>
> **브리핑 규율 상속**: 방법론 플레이북 §0(저작자 절, :27)·부록 B(§0.5 체크리스트 13항, :531)·부록 D(극성,
> :600)·**§5 열린-세계 경계(:423)**. anti-phantom: 모든 인용 grep/Read 실측·file:line 부록 A 병기·존재/부재
> 대칭(부재=negative-grep). EV-L2 파일럿 §2(C1 durable 판정)·§9(R-1 residual)을 1차 소스로 상속했다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

**확정한다**: (1) EV-L3 의미 실측 + "Integrated System Fault Test"가 STATE-EV-004에 요구하는 것의 명시 논증
(§1); (2) 열린-세계 전이의 원리 논증 + EV-L3 3축(persistence/identity/network) 분할·정직 이연(§2); (3)
**persistence 기술 결정**(파일럿-범위 vs ADR §4 프로젝트 결정의 지위 명시, falsifiable 근거)(§3); (4)
crash-restart fault 카탈로그(§4, falsifiable Expected만); (5) **durable-reload 컴포넌트 명세 + oracle
독립성**(§5, EV-L2 파일럿의 "L1 하드닝" 위치의 대응물); (6) 하네스 EV-L3 stage 확장 계약(manifest v3·게이트·
prior L1∧L2 결속·self-test)(§6); (7) STATE-EV-001 R-1 closure 경로 + STATE-EV-002/003 처분 + firewall/gap
canary(§7); (8) 테스트 스위트(§8); (9) 수용 주장의 **축소된** 정확한 형태 + 잔여 게이트(§9).

**하지 않는다**:

- **PASS/acceptance 선언.** 하네스는 원리적으로 row status를 이동시키지 않는다(`tools/tos_evidence_run.py:26`).
- **실 broker 주문 전송.** 파일럿은 **실 주문 0바이트**를 방출한다. STATE-EV-004:1045의 "after network
  transmission" 크래시 지점은 **모델된(capability-class VirtualBroker) 전송 마커**로 실현하며, 실 broker
  네트워크는 별도 residual(§2.4 R-N)이다 — 실 선물 계좌 무입금·실주문 경로 영구 차단 정책(CLAUDE.md 비협상
  규칙) 준수. tos-spec broker-agnostic(KIS 사실 금지) 준수.
- **STATE-EV-004의 PASS.** 그 자체 EV-L3의 network·credential-identity 축이 모델/이연이라 STATE-EV-004는
  본 파일럿만으로 PASS-부적격(§9). 파일럿은 STATE-EV-004의 **persistence+process+reconstruction 축**을
  실행하고, 그 산출이 STATE-EV-001의 **R-1(durable) 축**을 방전한다.
- **ADR-002-017 Recovery Barrier / 재-arm 체인.** ADR-002-005 §13:200이 요구하는 "no new risk … until
  Recovery Barrier … re-arm chain"은 **별개 EV-L3 통합**(recovery orchestration)이다. 파일럿은 §13:197-199
  (durable + 보수 재구성)만 방전하고 §13:200은 정직 이연(§7, §10).
- **durable-reload 컴포넌트의 구현.** §5는 코드 명세만 확정 — 구현은 별도 단계(executor)다.

---

## 0.5. 선제-봉합 체크리스트 (플레이북 부록 B:531 상속 + 본 문서 앵커 + 열린-세계 신설)

| # | 규율 | 본 문서 적용 |
|---|------|-------------|
| 1 | **anti-phantom (부재·존재 대칭)** | 전 인용 file:line 부록 A. 부재 5건 negative-grep(§6 STAGE_L3 부재·§3 sqlite3 tos/ 부재·§2 tos/ 실 I/O 부재·§7 STATE-EV-004 evidence dir 부재·§5 network token 부재). |
| 2 | **∅-seal 양방향** | "crash scenario 0건 실행"≠"위반 없음". `all_crash_scenarios_met`에 "빈 스케줄 ⇒ GREEN 불가" 구조 게이트(§6). |
| 3 | **구조 파생 > 자기신고** | reconstruction verdict는 self-report 아닌 **durable store 실독 + 구조 비교**에서 관측. 프로세스 경계는 writer_pid ≠ reader_pid 구조 검사(§6). |
| 4 | **falsifiable Expected만** | Expected가 결정적·반증가능하지 않은 crash 지점은 카탈로그 제외·residual 이연(§4). |
| 5 | **음극성 `is False`만 (부록 D:600)** | 신설 극성 코드 최소화. reconstruct 결과의 극성은 Enum identity(`is UNKNOWN`/`is CONFLICTED`)로 관측 — truthy 금지. |
| 6 | **register CSV 전수 파싱** | STATE-EV-00x 행은 csv 모듈/awk 컬럼 고정 파싱(§부록 A). naive grep head 금지. |
| 7 | **over-scope 금지 (정직 이연)** | network·credential-identity·Recovery Barrier·STATE-EV-002/003 L3·power-loss durability 전부 명시 이연(§7·§10). |
| 8 | **뮤테이션 canary 실효성** | 각 crash fault: both-ways + reload-path mutant(RECONCILED 기본·stale-cache 신뢰·낙관 채움·sync 하향)가 **outside 하드코딩 앵커 테스트를 FAIL**시킴을 실측 의무(§5·§8). |
| **O-1** | **열린-세계 배선 fail-open (플레이북 §5:436)** | fail-open이 술어 내부가 아니라 **배선(store↔process↔reload)**에 산다. §5가 durable-reload seam을 명시·gap canary로 잠금(§7). |
| **O-2** | **결정론 canary 공백 (플레이북 §5:437)** | crash 지점은 **파라미터화된 결정론 os._exit**(racy SIGKILL 아님)·scenario 열거 순서 고정·seed=0(pure projection property). 비결정 크래시는 acceptance 집합 제외(§4·§6). |
| **O-3** | **oracle 독립성 (ASS-CM-04:590 상속)** | "guard가 곧 oracle"을 **firewall R-reverse로 구조 차단**: outside 크래시 테스트는 `import tos` 불가(reverse 규칙 e:192)라 `reconstruct_conservative`를 호출 못 함 ⇒ Expected는 **손으로 유도한 독립 하드코딩 앵커**(§5.3). inside(mp-spawn)도 가능하나(MAJOR-1) **구조적 oracle 독립을 위해 outside 선택 구매**(구조>convention, §5.2 대안 B). |
| **O-4** | **committed canary 전수-grep (누적 교훈)** | 터치 표면(tos.staterestore·outside 테스트·harness L3)의 **모든 committed canary 전수-grep**·closure allowlist만으론 불충분. stale-.pyc 퍼지 필수(§8). |
| **O-5** | **저작-레벨 firewall 잠금** | 신규 `tos.staterestore`는 firewall AST 게이트(`tools/tos_firewall_check.py`:203) 통과 의무 — subprocess/socket 등 금지 stdlib 직접 import 0·os.environ 0(§5·§8). |

---

## 1. EV-L3의 의미 실측 (VER-002-001 verbatim)

### 1.1 강도 레벨 정의 (VER §5:143-161)

```text
EV-L1 (VER:143-145) Model and Property Verification — state-machine exploration, model
                    checking, property-based testing, deterministic simulation.
EV-L2 (VER:147-149) Component Fault Test — "A component is tested with controlled failure
                    injection and authoritative state inspection."
EV-L3 (VER:151-153) Integrated System Fault Test — "Multiple live-path components are tested
                    together with real persistence, identity, and network boundaries."
EV-L4 (VER:155-157) Broker Sandbox or Certified Test Environment.
EV-L5 (VER:159-161) Restricted Production Verification.
```

**세 문장의 델타가 본 설계의 전 경계를 규정**: L1=valid 공간 속성; L2=단일 컴포넌트+통제 실패주입+권위 상태
검사(EV-L2 파일럿이 방전); **L3=다중 live-path 컴포넌트 통합 + 실 persistence·identity·network 경계**.
따라서 L3가 L2에 **추가로 요구하는 것**은 정확히 세 축이다: (a) **실 persistence**(in-memory 직렬화가
아닌 실 durable 저장), (b) **실 identity**(실 프로세스/자격/식별 경계), (c) **실 network**(실 전송 경계).

### 1.2 STATE-EV-004가 EV-L3로 요구하는 것 (VER:1041-1046 verbatim)

**STATE-EV-004 — Conservative Restart Reconstruction** (VER:1041-1046):
- Minimum: `EV-L3`(1043). Supports: **AC-005-4**(1044) — STATE-EV-001의 AC-005-1과 **다른 AC**.
- **Injection**(1045): "Crash at each attempt and broker-order boundary, including after durable
  `SEND_STARTED`, after network transmission, and before evidence persistence; then restart with
  incomplete stores and stale caches."
- **Expected**(1046): "Potentially live attempts and non-terminal orders reconstruct as `POTENTIALLY_LIVE`
  or `UNKNOWN`; Knowledge is re-derived and never defaults to `RECONCILED`."

**규범 근거 (ADR-002-005 §13:195-200)**:
- §13:197 "All five dimensions SHALL be **durable and reconstructable after crash, restart, or failover**."
- §13:198 "On restart, any Attempt that reached `SEND_STARTED` and any Broker Order that is not provably
  terminal SHALL be treated as `POTENTIALLY_LIVE`/`UNKNOWN` until reconciled."
- §13:199 "Knowledge SHALL be re-derived from evidence, defaulting to `UNOBSERVED`/`CONFLICTED`, never to
  `RECONCILED`."
- §13:200 "No new risk SHALL be authorized until the **ADR-002-017 Recovery Barrier** … re-arm chain
  completes." ⇒ **별개 통합**(§7 이연).
- §19:271 "restart reconstructs a conservative composite state **in tests**."

### 1.3 세 축의 파일럿 처분 (요약 — §2에서 논증)

| EV-L3 축 | STATE-EV-004에서의 지시체 | 파일럿 처분 |
|---|---|---|
| **real persistence** | 실 fault(크래시)를 견딘 실 persisted 권위 record(§13:197) | **실행** — 실 on-disk store·프로세스 사후 재적재 |
| **real identity (논리)** | 재구성이 intent/attempt/order **식별자를 store에서 재파생**(reconstruct는 intent_identity 보존, `predicates.py:735`) | **실행** — 논리 식별자 재파생 |
| **real identity (자격/호스트)** | 실 자격·cross-host auth 경계 | **이연** — STATE-EV-005(+Security):1050; residual R-I(§2.4) |
| **real network** | 실 broker 전송(§1045 "after network transmission") | **이연** — 모델 전송; residual R-N; 실주문 정책 영구 차단(§0) |

**핵심 이중-AC 서비스**: 단일 crash-restart run이 (i) STATE-EV-004/AC-005-4의 **재구성**("post-restart
POTENTIALLY_LIVE/UNKNOWN")과 (ii) STATE-EV-001/AC-005-1의 **durable/persisted**("persisted", :237; R-1)
**양쪽 증거를 동시에 산출**한다. R-1은 persistence 축에만 걸리므로 network/identity 축 이연과 무관하게 닫힌다
(§7).

### 1.4 §2.7 coverage argument 의무 (VER:79)

STATE-EV-004 Expected는 **전칭**("**every** … boundary", "**never** defaults to `RECONCILED`")이라 VER:79
coverage argument 의무. 최소 요건 = per-dimension boundary values + "adversarial combinations of the
approved Adverse Scenario Set (ADR-002-021)". ADR-002-021은 여전히 **Proposed**(§9-2). ⇒ EV-L2 파일럿과
동형으로, restart 축 전용 **ADVERSE-SCENARIO-SET-002-EVL3 인스턴스**(운영자 승인)로 adversarial leg를 리뷰
층에서 방전하되 하네스는 `discharged:false`를 기계적으로 유지(§6·§9). VER:3171도 "bounded model still requires
the §2.7 coverage argument"라 못 박음.

---

## 2. 원리 논증 — 열린-세계 전이 + EV-L3 축 분할

### 2.1 닫힌-세계 → 열린-세계 (시리즈 최초 실 I/O)

Part 1(ADR-002)은 **닫힌 세계**였다 — 순수 술어, I/O 없음, 시간조차 `tos.time` 데이터(플레이북 §5:428).
**실측**: tos/src 전체에 sqlite3/fsync/실 파일쓰기 **부재**(negative-grep — `sqlite3`·`fsync`·`open(` 매칭은
sir의 `_member_is_open` 오탐뿐, §부록 A). `orthostate/__init__.py:11` verbatim "**no** persistence / durable
restart"; `:38-39` "STATE-EV-### remains NOT_IMPLEMENTED pending EV-L2/L3 … durable persistence … real
restart." `reconstruct_conservative` docstring(`predicates.py:692`) verbatim "actual durable reload / crash
recovery / Recovery Barrier are **EV-L3**." ⇒ **본 파일럿이 tos/ 최초의 실 durable 저장·실 프로세스 경계를
도입**한다. 이는 firewall 배제가 아니라 **의도된 진화**(플레이북 §5:442 "새 레인 필요 … 정의는 수직 슬라이스
설계 사이클 소관") — firewall은 import 경계만 규정하며 파일 I/O를 금하지 않는다(§3.1).

### 2.2 "durable" 지시체는 열린-세계에서만 존재한다 (EV-L2 파일럿 C1 상속)

EV-L2 파일럿 §2.2가 확정한 축 분할을 1차 소스로 상속한다: STATE-EV-001 durable 축("durable" VER:1025;
crash 복원 ADR §13:197; "persisted" AC-005-1:237)의 **지시체 = 실 fault를 견딘 실 persisted 권위 record —
in-memory에 부재**. EV-L2(순수 모델)로는 **도달 불가**라 R-1 residual로 이연됐다(`STATE-EV-001` 레지스터
notes:91; RESIDUAL-RISK-REGISTER-002 R-1). **본 파일럿이 그 지시체를 처음 실현**한다: 실 store에 commit →
**실 프로세스 크래시(os._exit)** → **fresh 프로세스**가 store 재적재 → 재구성. 두 프로세스 사이 유일 채널이
on-disk store라는 점이 곧 "real persistence … boundaries"(VER:153)의 방전이다.

### 2.3 EV-L3 축 분할 — 대안 명시 검토

| 대안 | 논증 | 판정 |
|---|---|---|
| **A. STATE-EV-004 EV-L3를 3축 모두 실행** | 실 network=실 broker 전송=실 선물 주문 ⇒ 정책 영구 차단(CLAUDE.md); broker-agnostic 위반; 불가 | **기각** |
| **B. 실 network 불가 ⇒ STATE-EV-004 미실행·R-1 영구 미방전** | reconstruction Expected(1046)·durable 축(R-1)은 network 축과 무관하게 실 persistence+process로 완전 검증 가능 ⇒ 미실행은 정보 손실이고 운영자 지시("최종 완료")에 반함 | **기각** |
| **C. 축 분할: persistence+process+reconstruction 실행, network/credential-identity residual**(채택) | reconstruction·durable은 실 persistence+process로 방전; network(모델)·credential-identity(STATE-EV-005)는 정직 residual. R-1은 방전 축에만 걸려 닫힘. STATE-EV-004 자체는 PASS-부적격(잔여 축) | **채택** |

**귀결**: 파일럿은 STATE-EV-004의 **persistence+process+reconstruction 축을 실 EV-L3로 실행**하고, network·
credential-identity 축은 residual로 이연한다. 이 실행이 STATE-EV-001의 **R-1(durable) 축을 방전**한다(그 축은
network/identity와 무관). **STATE-EV-004 자체는 본 파일럿만으로 PASS-부적격**(자체 network/identity 축 미방전
+ 독립 서명 미완). 이 비대칭을 §4 태그·§9 수용주장·§10 경계표가 관철한다.

### 2.4 이연 축의 residual 등재 (비-union·독립 — VER:3308)

파일럿은 §378 레지스터(RESIDUAL-RISK-REGISTER-002.yaml)에 **독립 신규 항** 2건을 등재한다(12필드 SHALL 전수,
owner/approver=D1 operator, 비-union). **R-1과 별개** — R-1은 닫히고 R-N/R-I는 STATE-EV-004 자체를 막는다:

- **R-N — STATE-EV-004 real-network-boundary 축 미방전**: 전송이 모델(VirtualBroker 마커)이라 실 broker
  네트워크 경계 미증거. 지시체 = EV-L4 broker sandbox(VER:155)/+Broker; 실 선물은 정책 영구 차단(무입금). 실
  economic effect 0(전송 0바이트). Critical이라 WAIVED 불가(VER:131).
- **R-I — STATE-EV-004 credential/service-identity 축 미방전**: 논리 식별자 재파생은 실행하나 실 자격·cross-
  host auth 경계 미증거. 지시체 = STATE-EV-005(EV-L2/3+Security):1050. Critical이라 WAIVED 불가.

**추가 이연 (candidate residual, 운영자 결정)**: **R-D — power-loss/torn-sector durability**: os._exit는
애플리케이션 크래시(프로세스 사망)를 충실히 모델하나 커널 page-cache·전원상실·torn-sector는 모델하지 못한다
(FS fault injection 필요). 파일럿은 **프로세스-크래시 durability**(§13 "crash, restart")를 방전하고 전원상실
durability는 이연(§4에서 inter-transaction incomplete-store로 대체 커버되는 범위 명시).

---

## 3. persistence 기술 결정 (파일럿-범위 — ADR §4 프로젝트 결정 아님)

### 3.1 firewall 제약 실측

firewall 허용목록(`2026-07-20-tos-boundary-and-import-firewall-design.md:186-187`): **표준 라이브러리 전체**,
단 직접 import 금지 = `socket, ssl, http, urllib.request, ftplib, smtplib, poplib, imaplib, telnetlib,
subprocess, ctypes`. 서드파티 = `pydantic, numpy, pandas, pytest, hypothesis, pyyaml`(DB 라이브러리 없음).
⇒ **`sqlite3`는 stdlib이며 금지 목록에 없다 ⇒ 허용**(negative-grep: 금지 11개에 sqlite3 부재). `os`(단
`os.environ`/`os.getenv`는 AST 게이트가 검출·금지, :205)·`pathlib`·`hashlib` 허용. **`subprocess` 금지가
본 설계의 핵심 제약**(§5.2·§6).

### 3.2 후보 평가

| 후보 | durable 근거 | incomplete-store 주입 | firewall | 판정 |
|---|---|---|---|---|
| **A. stdlib `sqlite3` WAL, `synchronous=FULL`**(채택) | 트랜잭션 원자 commit·재개 시 WAL recovery가 미commit 롤백; 잘 정의된 크래시 의미 | 두 트랜잭션(SEND_STARTED / ACK) 사이 크래시 = 합법 incomplete store | stdlib·clean | **채택** |
| B. append-only 파일 + `os.fsync` 저널 | 투명하나 원자성·torn-record 수제(오류 위험↑) | torn-record 직접 주입 가능하나 A가 inter-tx로 충분 | clean | 보조(§4 torn 주입 옵션) |
| C. atomic rename 스냅샷(temp+fsync+`os.rename`+dir fsync) | POSIX-atomic rename; whole-composite 스냅샷 durable | 증분 attempt/order 마커에 부자연 | clean | 기각(증분성 부족) |

**결정**: 파일럿 store = **stdlib sqlite3 WAL, synchronous=FULL**. dimension별 마커(intent/attempt/broker/
knowledge/capacity)를 **별도 트랜잭션**으로 commit해 "after SEND_STARTED"·"before evidence persistence"
크래시 지점을 두 트랜잭션 사이에서 실현한다.

### 3.3 지위 — 파일럿-범위 vs ADR §4

ADR-002-005 §4:61 verbatim "This ADR does not decide **the persistence technology**." 이는 **프로덕션
persistence 아키텍처 결정**(RCL·ADR-002-016 evidence·failover 통합)으로 **ADR acceptance 인접 거버넌스 행위**
다. 파일럿은 이를 **하지 않는다**. 파일럿 결정은 **"STATE-EV-004 EV-L3 크래시-테스트할 실 substrate"의
파일럿-범위 선택**이며, 비-live-test scope(PROFILE scope.environment `non-live-test`:59)에 한정된다.

> **⚠ 미해결 쟁점 OQ-1 (§11 최상위)**: R-1의 required_scope_reduction(RESIDUAL-RISK-REGISTER-002 R-1:177)은
> "the persistence technology decision deferred by ADR-002-005 §4 … must be made **first**; an EV-L3 crash/
> restart fault run then discharges the limb"라 적는다. **엄격 독해**로는 §4 프로젝트 결정이 선행이고 파일럿-
> 범위 결정은 그것이 아니다. **파일럿-범위 독해**로는 STATE-EV-004를 돌리는 데 필요한 결정("어떤 실
> substrate를 크래시-테스트하나")은 파일럿 층에서 답 가능하다. 이는 **SPG-EV-002의 coverage-discharge와
> 동형의 운영자/리뷰어 판정**(하네스가 자기-인증 못 하는 leg를 승인 인스턴스가 방전)이다. 본 설계는 (b)를
> 권고하되 — 파일럿-범위 결정 기록 + EV-L3 run 실행 = R-1 방전 — **R-1 closure의 충분성 자체를 운영자 결정
> 항목으로 명시**하고, 축소 수용주장(§9)에 "§4 프로젝트 persistence 결정은 별개 open gate"를 병기한다.

### 3.4 falsifiable 근거

- **durable commit**: "sqlite3 WAL·synchronous=FULL은 commit된 record가 os._exit 크래시 후 fresh 프로세스
  재적재에서 존재함을 보장. **반증**: post-commit 크래시가 commit된 record를 소실." (§8 mutant E)
- **incomplete-store rollback**: "미commit(트랜잭션 중 크래시) 쓰기는 재개 시 롤백되어 reader는 마지막 commit
  상태만 관측(torn 아님). **반증**: 재개된 store가 half-written record 노출."
- **process boundary real**: "writer_pid ≠ reader_pid ∧ 유일 채널 = on-disk store 파일. **반증**: 동일 pid
  또는 in-memory 잔존 채널."

---

## 4. Crash-Restart Fault 카탈로그 (STATE-EV-004; falsifiable Expected만)

**컴포넌트 통합**: `CompositeState`(orthostate) + durable store(staterestore, §5) + durable-reload+
`reconstruct_conservative`(§5) + 실 프로세스 경계 + 모델 전송 마커. **크래시 모델**: 파라미터화된 결정론
`os._exit(137)`(racy SIGKILL 아님 — O-2). **seed**: pure projection property는 `--hypothesis-seed=0`+
`PYTHONHASHSEED=0`; 통합 매트릭스는 파라미터화 결정 열거(seed는 스케줄 append-only에 기록, VER §9.1). **주입-
지점**: 실 crash 호출 라인 + durable-reload seam(구현 시 실측 기록 의무). Expected는 **§5.3 outside 하드코딩
앵커**(reconstruct_conservative 재호출 아님 — oracle 독립).

**MAJOR-2 정정 — 앵커 결정론화**: v1.0은 셀의 커밋 상태를 부분만 지정해 Knowledge 앵커가 셀 서술로부터
파생 불가했다(리뷰어 실측: §13:199는 "defaulting to `UNOBSERVED`/`CONFLICTED`" **둘 다** 허용; `reconstruct_
conservative`는 pre∈`_KNOWLEDGE_DOWNGRADE_ON_RESTART={RECONCILED,CONSISTENT}`(`predicates.py:683-685`)일
때만 CONFLICTED로 강등하고 pre=UNOBSERVED면 UNOBSERVED **보존**(`predicates.py:729-732`) — 재측정 확인).
⇒ v1.1은 **각 셀의 5차원 커밋 상태(I·A·B·K·C)를 전부 pin**해 앵커를 다운그레이드/보존 맵에서 결정론
파생하고, 별도로 **2층 독립 불변식**(reconstruct 재호출 없이 §13:199에서 직파생: `K ∉ {RECONCILED,
CONSISTENT}`)을 병기한다. 부재 차원의 보수-채움 규약은 §5.1 S-2가 논증한다.

카탈로그 = {Attempt 경계} × {Broker 경계} × {evidence 시점} × {store 완전성} × {cache 신선도}의 결정론 부분
집합. `I=Intent·A=Attempt·B=Broker·K=Knowledge·C=Capacity`. 대표 falsifiable 셀(구현 시 enum 경계 전수 열거):

| id | crash 지점 | 커밋 5차원 (I·A·B·K·C) — 전부 pin | Expected 재구성 (결정론 값) | 2층 독립 불변식 | 근거 | 태그 |
|---|---|---|---|---|---|---|
| L3-01 | after durable `SEND_STARTED`, broker 수신 전 | ACTIVE·SEND_STARTED·UNKNOWN·**UNOBSERVED**·POTENTIALLY_LIVE | A=SEND_STARTED; B=UNKNOWN(보존); **K=UNOBSERVED(보존·not-in-downgrade)**; C=POTENTIALLY_LIVE | `K∉{REC,CONS}` ∧ `C⪰PL` ∧ `B=UNKNOWN` | §13:198; `predicates.py:659-668,715-719,731-732` | 핵심 |
| L3-02 | after (모델) network transmission | ACTIVE·SENT_UNCONFIRMED·UNKNOWN·**UNOBSERVED**·POTENTIALLY_LIVE | A=SENT_UNCONFIRMED; B=UNKNOWN; K=UNOBSERVED(보존); C=POTENTIALLY_LIVE | `K∉{REC,CONS}` ∧ `C⪰PL` ∧ `B=UNKNOWN` | §13:198; 1045 "after network transmission" | 핵심·모델전송 |
| L3-03 | **before evidence persistence** (in-mem ACK, durable 전 크래시 — durable=pre-ACK) | ACTIVE·SEND_STARTED·UNKNOWN·**UNOBSERVED**·POTENTIALLY_LIVE (in-mem 낙관 지식 **미persist**) | 소실 ACK가 RECONCILED로 부활 안 함 → K=UNOBSERVED(보존); B=UNKNOWN | **`K∉{REC,CONS}`**(load-bearing, 1046 "never … RECONCILED") | §13:199; 1046 | 핵심 |
| L3-04 | broker-order 경계(비-terminal) 크래시 | ACTIVE·SENT_UNCONFIRMED·**⟨비-terminal member, 구현 enum pin⟩**·UNOBSERVED·POTENTIALLY_LIVE | B→UNKNOWN(비-terminal 재구성); K=UNOBSERVED(보존) | `B=UNKNOWN`(비-terminal) ∧ `C⪰PL` | §13:198; `predicates.py:672-679` | 핵심 |
| L3-05 | **incomplete store**(inter-tx 크래시·차원 부분 commit) | A=SEND_STARTED commit; **B·K 미commit(부재)** | S-2 보수-채움: 부재 K→**UNOBSERVED**·부재 B→UNKNOWN; 낙관 채움 금지 | 부재 차원 ∉ 낙관값 ∧ `K∉{REC,CONS}` | 1045 "incomplete stores"; §5.1 S-2 | L3-신규 |
| L3-06 | **stale cache**(낙관 캐시 파일) + 크래시 | store: K=**UNOBSERVED**(보수); 별도 cache: K=RECONCILED(낙관) | reader가 cache **무시**·store 재파생 → K=UNOBSERVED | **`K∉{REC,CONS}`**(cache의 RECONCILED 미유입) | 1045 "stale caches"; §13:199 re-derive | L3-신규 |
| L3-07 | terminal Broker + 양성 Knowledge 크래시(양성 canary·다운그레이드 발화) | ACTIVE·ACK_OBSERVED·**FILLED**·**RECONCILED**·⟨POSITION_CONSUMED, §14:211⟩ (sub-case: K=CONSISTENT) | B=FILLED(terminal **보존**); **K=RECONCILED→CONFLICTED**(강등·in-downgrade); C=rcl 비교자(⪰PL 보존·아니면 상향, 구현 실측) | `B=FILLED(보존)` ∧ `K=CONFLICTED` ∧ `K∉{REC,CONS}` | §13:199; `predicates.py:729-732,683-685`; §14:211 | L3-신규·both-ways |
| L3-08 | **durability 메커니즘**(정상 완전 commit → 크래시 → 재적재; reconstruct=항등) | ACTIVE·SENT_UNCONFIRMED·UNKNOWN·CONFLICTED·POTENTIALLY_LIVE (§14:208·이미 보수적 ⇒ reconstruct 항등) | 재적재 5차원 **== 커밋 5차원**(무손실 durable round-trip·AC-005-1 "representable and persisted") | `reload(store) == committed` (필드 동일) | §13:197; AC-005-1:237; §14:208 | durability |

**규모**: 대표 8셀(구현은 Attempt·Broker enum 경계 전수로 확장·결정론 열거). `reconstruct_conservative`
코도메인은 **구조적으로 RECONCILED 배제**(`predicates.py:700-702` "codomain **structurally excludes**
RECONCILED") — L3-03/06/07의 `K∉{REC,CONS}` 불변식이 이를 outside에서 독립 재확인(구현 회귀 아닌 §13:199
직파생 앵커).

**④ L3-08 ↔ R-1 방전의 정밀화 (MAJOR-2)**: L3-08은 **durability 메커니즘 셀 1건**이지 R-1 방전 자체가
아니다. R-1(STATE-EV-001 "**every** valid composite remains representable **and durable**", 1025)은 **전칭**
이므로, 그 방전은 **§14 valid composite + 경계조합(1024) 위의 durability 속성**을 요구하고 **VER §2.7 coverage
argument(§9 게이트 2)에 종속**한다. 즉 "L3-08이 R-1을 직접 방전"이 아니라 "L3-08이 durability 메커니즘을
실증하고, R-1 방전 = 열거된 composite 경계집합 위 durability 속성 + coverage argument"다(§7.1 반영).

**뮤테이션 canary 실효성 의무** (§8): 각 reload-path mutant가 outside 앵커 테스트를 **FAIL(KILLED)**시킴을
실측 — (A) 부재 Knowledge를 RECONCILED 기본, (B) 비-terminal Broker 보존(UNKNOWN 미강등), (C) stale cache
신뢰, (D) incomplete store 낙관 채움, (E) sqlite `synchronous=OFF`로 durable 소실. 5종 KILLED가 OQ-2/O-2의
경험적 답.

**카탈로그 제외/이연**: power-loss/torn-sector(R-D, FS fault injection 필요)·Recovery Barrier/재-arm(§13:200,
ADR-002-017 별개 통합)·실 network(R-N)·실 credential(R-I).

**커밋 composite CPL 합법성 (델타 재검증 관찰 반영)**: L3-01~06의 pin된 커밋 composite는 §14 예시에 미열거된
조합을 포함하므로, 구현 시 각 셀의 커밋 composite를 `CompositeState`로 구성하는 시점에
`coupling_violations() == ∅`를 확인한다(CPL-위반 조합은 구성 시 시끄럽게 실패 — silent 결함 불가).
`reconstruct_conservative`는 전(total) 사상이라 앵커 결정론성은 이와 무관하나, 커밋 상태의 합법성 자체를
구현-시 검증 의무로 못 박는다.

---

## 5. durable-reload 컴포넌트 명세 + oracle 독립성 (구현은 별도 단계)

EV-L2 파일럿에서 "§5 L1 하드닝"이 L2 실행의 코드 선행이었듯, 본 파일럿의 코드 선행은 **신규 `tos.staterestore`
패키지(durable store + reload 경로)**와 **outside 크래시 orchestration**이다. 각 항은 ADR §13 SHALL의 실현.

### 5.1 `tos.staterestore` (firewall 내부·subprocess 없음)

| 항 | 명세 | 근거(SHALL) | firewall |
|---|---|---|---|
| **S-1 store** | sqlite3 WAL·synchronous=FULL로 CompositeState 5-dimension 마커를 dimension별 트랜잭션 commit·재적재 | §13:197 durable | stdlib sqlite3(허용)·subprocess 0 |
| **S-2 reload** | 재개 시 store 실독 → 완전이면 CompositeState 복원 → 불완전/torn이면 **부재 dimension을 보수(UNKNOWN/POTENTIALLY_LIVE) 채움** → `reconstruct_conservative` 적용 | §13:198-199; `predicates.py:688` | orthostate import edge |
| **S-3 no-stale** | in-memory/파일 cache는 재개 시 **폐기**·store에서만 재파생 | §13:199 re-derive; 1046 | — |
| **S-4 worker** | `python -m tos.staterestore._l3_worker <mode> <args>` — writer(commit→`os._exit`)·reader(reload→verdict stdout). 파라미터는 **argv**(os.environ 금지·:205) | 결정론 크래시(O-2) | os._exit·subprocess 0·os.environ 0 |

**S-2 per-dimension 보수-채움 규약 (MAJOR-2 명세)**: 부재/torn 차원의 채움값은 §13:199에서 논증한다. §13:199
"Knowledge SHALL be re-derived … **defaulting to `UNOBSERVED`/`CONFLICTED`, never to `RECONCILED`**" — 부재
Knowledge의 자연 독해는 **UNOBSERVED**("durable 증거가 없음"은 관측 부재이지 조작된 conflict가 아님)이며,
CONFLICTED는 존재하지 않는 conflict를 단언한다. ⇒ **부재 K→UNOBSERVED**를 채택하되, **load-bearing 불변식은
음성**(`K∉{RECONCILED,CONSISTENT}`)이다(양성 값은 결정론 앵커, 음성 불변식은 oracle-독립 검증축). 타 차원:
부재 B→UNKNOWN; 부재 A→**SEND_STARTED 미존재 시 send 미개시**(§6:96 "durable **before** the external call"의
순서 보장 — durable SEND_STARTED 부재 = 외부호출 미발생, 구조 안전 독해); 부재 C→CPL-1 최소 보수값
(POTENTIALLY_LIVE); 부재 I→식별 불가 record는 재구성 거부(torn-unidentifiable). 완전 차원은 §4대로
`reconstruct_conservative` 적용(다운그레이드/보존 맵).

**비-transmitting 불변식 보존 (MINOR-3)**: staterestore는 **로컬 durable 저장(disk)만** 추가하고 **egress
0**을 유지한다. tos-wide 불변식 `tos/__init__.py:6` verbatim "This package is **non-transmitting by
construction** (§4): no broker credentials, routes, order-construction, or env-flag capability paths"와,
orthostate-scoped `orthostate/__init__.py:11` "**no** persistence / durable restart / egress"를 함께 보존한다
— persistence(로컬 disk I/O) ≠ transmission(network egress)이며, staterestore는 전자만 도입·후자 0. **canary
열거에 tos-wide non-transmitting 불변식 포함**(§7.4).

**내부 edge**: staterestore → orthostate(CompositeState·reconstruct_conservative) + canonical(직렬화). 정확한
allowlist 배선은 구현 의무이며 게이트 = `tools/tos_firewall_check.py`(§8). staterestore는 orthostate 순수성
(`orthostate/__init__.py:11` "no persistence")을 침해하지 않도록 **별도 패키지**(orthostate 내부 아님).
**`os._exit` gate-clean 실측**: firewall AST 게이트는 `os.environ`/`os.getenv`만 검출(`tos_firewall_check.py:
214-216,237-240`)이라 worker의 `os._exit`(충실한 abrupt 종료)는 gate 통과 — `tos/tests`의 os 회피 관행
(`test_import_closure.py:6`)은 import-closure 격리용이지 게이트 규칙이 아니다(구현 시 명시).

### 5.2 프로세스-경계 spawn 배치 — 대안 명시 검토 (MAJOR-1 정정)

**실측 정정 (v1.0 전제 오류)**: v1.0은 "outside 배치는 `subprocess` 금지(:186)에 의한 **강제**"라 주장했으나
1차 소스 재실측이 이를 반증한다. `multiprocessing`은 stdlib이며 firewall 금지 목록(:186의 11개)에 **없어
허용**(negative-grep: 금지 목록에 multiprocessing 부재)이고, **이미 tos/tests에서 fresh isolated interpreter
목적으로 사용 중**이다 — `tos/tests/test_import_closure.py:6` verbatim "a **fresh, isolated interpreter** (via
`multiprocessing` spawn — `subprocess` and `os` are firewall-forbidden even in tests)"; `:30` `import
multiprocessing as mp`; `tos/tests/test_evidence_import_closure.py:106` `ctx = mp.get_context("spawn")`. 즉
**inside(tos/tests)에서 mp-spawn으로도** writer_pid≠reader_pid·유일채널=on-disk store가 완전 충족된다. 따라서
배치는 **강제가 아니라 선택**이다.

| 대안 | 프로세스 경계 | oracle 독립 | 대가 | 판정 |
|---|---|---|---|---|
| **A. inside `tos/tests/staterestore/`, `mp.get_context("spawn")`** | 충족(spawn=별 pid·별 인터프리터) — 전 orchestration이 firewall AST 게이트 **인증** 범위 안 | **관행적(conventional)** — parent(tos/tests)는 `import tos` 가능(forward 허용)해 `reconstruct_conservative` 직접 호출 가능; 저자가 "호출 안 함"을 **선택**해야만 독립(구조 강제 아님) | orchestration이 firewall 인증 안(장점) | 후보 |
| **B. outside `tests/tos_l3/`, subprocess spawn**(채택) | 충족 — worker=`python -m tos.staterestore._l3_worker`(tos/ 내부, tos import 합법); outside는 arg-string만 넘김(`import tos` 안 함) | **구조적(structural)** — R-reverse(:192)가 outside의 `import tos`를 **강제 금지**(§5.3) ⇒ `reconstruct_conservative` 호출이 구조 불가 | orchestration(spawn·argv·stdout 파싱·앵커 비교)이 firewall 구조 보증 **밖**(§5.2 firewall 정밀) | **채택** |

**채택 근거 (구조 > convention)**: 시리즈 메타 교훈 ②("구조 > 자기신고", 플레이북 §6.1:476)를 oracle 층에
적용한다. A는 oracle 독립이 저자 규율(convention)에 의존하고 B는 firewall R-reverse에 의해 **구조적으로
강제**된다. 본 파일럿은 **outside orchestration 복잡도를 지불하고 구조적 oracle 독립을 구매**한다 — EV-L3의
핵심 위험이 ASS-CM-04(:590 "guards … are also the oracles")이므로 그 방어를 관행이 아닌 구조에 둔다.

**firewall 적용의 정밀 서술 (MINOR-1 정정)**: repo-root `tests/tos_l3/`는 "firewall 밖"이 아니라 **규칙별로
갈린다**. 실측: `tools/tos_firewall_check.py:114-116` `_REVERSE_SCAN_PRUNE = {"tos", ".git", ".venv",
"node_modules", "__pycache__", ".omc", ".history"}` — **`tests` 부재**. ⇒ (i) **forward 규칙(a-d: 허용목록·
금지 stdlib·os.environ)은 tos/(src+tests)에만 적용**(:166-167)이라 repo-root `tests/tos_l3/`는 subprocess
허용; (ii) **reverse 규칙(e: `import tos` 금지)은 repo 전수 스캔**(`check_reverse_imports`:306·prune에 tests
없음)이라 `tests/tos_l3/`에 **적용** — 이것이 O-3 구조 독립의 근거다. worker spawn은 `tos_evidence_run.py`가
`python -m pytest`를 subprocess spawn하는 것과 동형(합법 선례).

### 5.3 oracle 독립성 (O-3 — firewall R-reverse를 구조 자산으로 전용)

outside 크래시 테스트는 reverse 규칙(e)상 `import tos` 불가(§5.2 실측) ⇒ **`reconstruct_conservative`를 호출할
수 없다.** ⇒ Expected 재구성은 **§4 표의 손-유도 하드코딩 앵커**(결정론 값 + 2층 불변식 `never ∈ {RECONCILED,
CONSISTENT}`, §4)로 표현하고 worker가 방출한 **실제** 재구성과 비교한다. 이는 ASS-CM-04(:590)를 **구조적으로
차단** — 구현(reconstruct_conservative)에 버그가 있어도 독립 앵커가 잡는다. 방법론의 "자기참조 순서 단언 →
독립 하드코딩 앵커"(누적 교훈)의 oracle-층 적용. **트레이드오프 명시(MAJOR-1)**: 이 구조 독립은 공짜가 아니라
§5.2-B의 outside orchestration 복잡도(firewall 인증 밖의 spawn·파싱·비교)를 대가로 산 것이다 — 대안 A는 그
복잡도를 firewall 인증 안에 두는 대신 oracle 독립을 관행으로 격하한다. **"firewall 제약을 oracle 독립 보증으로
전용"이 본 파일럿의 방법론적 관찰**이며, 이는 강제가 아닌 **의도적 설계 선택**이다.

---

## 6. 하네스 EV-L3 stage 확장 계약 (`tools/tos_evidence_run.py`)

현 하네스 = EV-L1(manifest v1)·EV-L2(manifest v2 superset) 지원. `STAGE_L3`·`is_l3`·manifest v3 **부재**
(negative-grep: `tools/tos_evidence_run.py`에 STAGE_L3/EV-L3/manifest v3 0건, §부록 A). L3는 **additive
확장**(v2 전 필드 유지).

### 6.1 manifest v2 → v3 (superset·이름 명시)

> **NIT-1 네임스페이스 주의**: 본 문서의 "manifest v3"는 항상 **`tos-evidence/manifest/v3`**(하네스 manifest
> 스키마)를 뜻하며, self-test의 `_VER3_FIELDS`(=VER-002-001 **§3** baseline 22필드, `test_tos_evidence_run.
> py:293`)와 **무관**하다 — 명명 충돌 방지.

```yaml
schema: tos-evidence/manifest/v3
evidence_level_stage: EV-L3
prior_stage_runs:                    # [신규 게이트] L1 AND L2 둘 다 THIS baseline에서 결속
  - {evidence_id: STATE-EV-001, stage: EV-L1, baseline_commit_sha: <B>, baseline_matches_this_run: true, ...}
  - {evidence_id: STATE-EV-001, stage: EV-L2, baseline_commit_sha: <B>, baseline_matches_this_run: true, ...}
integration_boundary:                # [v3 신규 필드그룹]
  persistence:
    technology: "stdlib sqlite3 WAL, synchronous=FULL (pilot-scope; NOT the ADR-002-005 §4 project decision)"
    real_on_disk: true               # 구조 검사: store 파일이 실재·프로세스 사후 존재
  process_boundary:
    writer_pid: <int>; reader_pid: <int>   # writer_pid != reader_pid 구조 검사 (real boundary)
    crash_mechanism: "deterministic os._exit at parametrized crash point"
  modeled_axes:                      # [O-1·over-claim 방지] 모델/이연 축은 residual_ref 필수
    - {axis: network, disposition: MODELED, residual_ref: "RESIDUAL-RISK-REGISTER-002 R-N", note: "VirtualBroker marker; real broker network deferred (EV-L4/+Broker); real-futures policy-blocked"}
    - {axis: credential_identity, disposition: DEFERRED, residual_ref: "R-I", note: "logical identity re-derivation executed; real auth deferred (STATE-EV-005 +Security)"}
crash_injection:                     # [신규 — L2 fault_injection의 L3 대응]
  catalog_ref: docs/plans/2026-08-06-tos-ev-l3-pilot-design.md#4
  schedule_artifact: crash-timeline.jsonl      # append-only (VER §9.1)
  seed: 0
  crash_scenario_count: <per-row>
  all_crash_scenarios_met: true      # [게이트] false·미정의 Expected>0 ⇒ GREEN 불가 (관측 vs 하드코딩 앵커 재파생)
  process_boundary_real: true        # [게이트] writer_pid != reader_pid
  persistence_real: true             # [게이트] on-disk store 실재
coverage_argument:                   # VER §2.7 (restart 축) — L2와 동형
  boundary_values: "per crash-point × composite boundary combinations (deterministic enumeration)"
  adverse_scenario_set: "ADVERSE-SCENARIO-SET-002-EVL3 (operator-approved instance) — restart adversarial leg"
  unexercised_residual_ref: ["R-N network", "R-I credential-identity", "R-D power-loss durability"]
  discharged: false                  # 하네스는 자기-인증 안 함 (리뷰층 방전 — §9)
claim:
  closes_evidence_item: false
  register_status_moved_by_this_run: false
  covered_axis: "STATE-EV-004: persistence + process + reconstruction ONLY (NOT real network, NOT credential
    identity). Serves STATE-EV-001 R-1 durable axis. NOT PASS-eligible for STATE-EV-004 from this pilot."
  independent_review: NOT_SIGNED (VER §9.5)
```

### 6.2 EV-L3 전용 게이트 (각 측정·자기신고 불신 — L2:2130-2149 확장)

1. **`all_crash_scenarios_met`**: 각 (crash × composite) verdict을 **관측(reader stdout) vs §4 하드코딩 앵커**
   재파생. 빈 스케줄·DEVIATION·미정의 Expected ⇒ 미충족(∅ 양방향, O-2·2번).
2. **`process_boundary_real`**: writer_pid ≠ reader_pid 구조 검사(§0.5-3). 동일 pid ⇒ 미충족(in-process
   fallback이 EV-L3를 위조하는 것 차단).
3. **`persistence_real`**: store가 실 on-disk 파일·프로세스 사후 존재. in-memory ⇒ 미충족(EV-L2 파일럿 C1
   "in-memory 재정의" 재발 차단).
4. **`PRIOR_EV_L1_AND_L2_NOT_BOTH_BOUND_AT_THIS_BASELINE`**(NIT-2 개명 — "OR"의 오독 제거·요건은 AND):
   prior_stage_runs가 **`evidence_id == STATE-EV-001`인 L1 AND L2 둘 다**를 `baseline_matches_this_run:true`로
   결속(L2 게이트 M9의 확장·bind_prior_stage_run:903 재사용). **evidence_id 결속 추가(MINOR-2)**: STATE-EV-003도
   `EV-L1/3` READY(register:93)라 엉뚱한 행의 L1/L2로 충족될 수 있으므로 `evidence_id` 구조 검증 필수. **왜
   L1∧L2인가(오독 방지)**: STATE-EV-004 최소레벨은 `EV-L3`-only(1043)라 이 결속은 STATE-EV-004 **자체 staging
   요건이 아니다** — **STATE-EV-001(EV-L1/2)의 durable-limb 연속성 근거**다(L3 durable 증거가 비-stale L1/L2
   모델 기반에 부착돼 R-1을 방전, §7.1). 하나라도 stale/타-evidence_id ⇒ 미충족.
5. **`modeled_axis_residual_declared`**: `integration_boundary.modeled_axes` 각 항에 `residual_ref` 존재
   (over-claim 방지 — 실 network/identity를 residual 없이 주장하면 미충족).
6. **seed 고정** + **DEVIATION run 보존**(supersedes_run_id, VER §2.2 — L2 게이트 상속).

미충족 시 `stages_executed`/`covered_axis`는 **WITHHELD**·`invoked_covered_axis`만 기록(L2:2194-2216 패턴
상속). DISCIPLINE_TAG_L3 신문구: "EV-L3 stage execution record only; not a row PASS; restart coverage argument
+ network/identity residuals + independent review remain as stated in claim/coverage_argument blocks."

### 6.3 §7 applicable 부분집합 (VER:256 "as applicable")

item 1·2·3(crash-timeline)·4·5·30-34 = ✓. **item(network/broker/authority/human/recovery)** = 부분: 전송은
모델·recovery barrier 미포함 ⇒ N/A + residual 명기(§13:200 이연). baseline 노트는 L2 패턴(NOT_APPLICABLE_
PURE_MODEL_L2 → **NOT_APPLICABLE_MODELED_TRANSPORT_L3**) 갱신·§3 미충족 필드 목록 유지(M2 상속).

### 6.4 self-test 갱신 (`tests/tools/test_tos_evidence_run.py`, 현 1744행)

v3 manifest 구조·integration_boundary·crash_injection·6대 게이트(all_crash_scenarios_met withheld-on-empty/
deviation·process_boundary_real pid≠pid·persistence_real·prior L1∧L2 결속·modeled_axis residual 필수·seed)·
DISCIPLINE_TAG_L3·no-PASS(:395) 검증 추가. 게이트 both-ways(충족/미충족 픽스처 각각).

---

## 7. R-1 closure 경로 + 인접 행 처분 + firewall/gap canary

### 7.1 R-1 closure (STATE-EV-001 durable 축)

R-1 register 요건(RESIDUAL-RISK-REGISTER-002 R-1:173-177): "persistence 기술 결정 + EV-L3 crash/restart run이
limb 방전"·"consumer는 STATE-EV-004를 EV-L3·real persistence substrate로 인용". **파일럿 실행이 이를
**조건부**로 충족**한다:
- persistence 결정 = §3(파일럿-범위 sqlite3 WAL) — **:177 문자적 요건("§4 decision first")은 미충족이므로
  OQ-1 운영자 판정 종속**(MINOR-4).
- EV-L3 crash/restart run = §4 카탈로그. **L3-08은 durability 메커니즘 셀**이고 R-1 방전 = **§14 composite +
  경계조합(1024) 위 durability 속성 + VER §2.7 coverage argument(§9 게이트 2)**다(④ 정밀화 — "L3-08 직접
  방전" 아님).
- **R-1 register 항 전이(MINOR-4 — 무조건 아님)**: "open blocking gap" → "**evidence limb discharged by
  STATE-EV-004 run `<L3 run_id>` (substrate-class); §4 project-persistence gate + substrate-class caveat
  OPEN — pending OQ-1**". OQ-1 미해소 시 **이중 기록**("evidence limb 방전 · §4-decision gate 잔존"). evidence_
  references에 L3 run 추가. **비-union**: R-1은 R-N/R-I와 별개(R-1은 조건부 닫히고 R-N/R-I는 STATE-EV-004
  자체를 막음).
- **substrate-class caveat(MINOR-4·OQ-1)**: evidence-limb 방전은 **substrate-class 수준** — ACID durability를
  제공하는 substrate에서 **모델의 durable-restart 속성**을 검증한 것이다. 상이한 §4 production 기술 선택(역시
  ACID)은 별도 production-acceptance EV-L3 소관이지 **R-1 소급 무효화가 아니다**(모델 속성은 substrate-class로
  검증됨). 이 caveat가 파일럿-범위 결정을 방어 가능하게 한다.

**R-1 방전 후 STATE-EV-001 PASS의 축소형(여전히 열림)**: (a) L1∧L2 THIS baseline 재실행(§9 절차); (b) restart
축 coverage argument(ADVERSE-SCENARIO-SET-002-EVL3); (c) P0-1(STATE 축 — reconstruction Expected는 **bound-
independent**라 승인 numeric bound 미소비·negative-grep VER:1046에 ms/duration/retention 토큰 0; 단 null
`MIN_evidence_retention_ms`(:923)를 소비하면 fail-closed·§7.3); (d) 독립 서명(VER §9.5)+운영자 countersign;
(e) VER §3 complete-baseline(구조적 미충족 잔존). **파일럿은 R-1 closure까지만 담당·PASS 미선언**.

### 7.2 인접 행 정직 처분 (over-scope 금지)

| 행 | 최소 레벨 | 파일럿 처분 |
|---|---|---|
| **STATE-EV-002** Conservative Direction(1029) | EV-L2/3 | **미커버**. Injection(1031)은 timeout/ACK loss/query omission/cache miss/**process restart**/authority expiry/operator assertion — restart는 부분 접점이나 나머지 6주입 미실행. process-restart limb만 접하고 **행 미종결**(정직 부분-접점). |
| **STATE-EV-003** Cross-Dimension Coupling(1036) | EV-L1/3 | **L3 limb 미커버**. Expected(1039)=CPL-1..7 under partial-fill/cancel-crossing + RCL capacity transition. **별개 통합**(coupling/RCL 동시성)이라 restart 파일럿 미접촉(negative: 본 카탈로그에 CPL-2..7 fill/cancel·RCL transition 0). 정직 이연. |
| **STATE-EV-005** Dimension Transition Ownership(1050) | EV-L2/3+Security | **미커버**. credential-identity 축(R-I)의 상위 행. 이연. |
| ADR-002-017 Recovery Barrier / 재-arm(§13:200) | 별개 | **미커버**. reconstruction은 보수 상태 산출; "no new risk until Recovery Barrier … re-arm" recovery orchestration은 별개 EV-L3. 이연(§10). |

### 7.3 null-key 노출 분석 (fail-closed)

PROFILE 17 null 키는 key-level 미승인·fail-closed(:6-8). STATE-EV-004 reconstruction Expected(1046)는 **정성적
·bound-independent**(negative-grep: ms/duration/retention/threshold 토큰 0). ⇒ 승인 numeric bound 미소비 —
P0-1 대부분 vacuous 충족. **단** `MIN_evidence_retention_ms`(:923, null)를 소비하는 retention-duration 주장은
파일럿이 **하지 않는다**(재구성은 "얼마나 오래"가 아니라 "무슨 값"이라 retention 무관). 만약 확장이 retention-
duration을 주장하면 null 키에 걸려 **fail-closed·residual**. `B_stale_epoch_reject`=0(승인, :228-232)와 S-3
no-stale re-derive는 **보수 방향만 정합**(NIT-3) — 전자는 **stale ledger/authority epoch fencing**(compare-
and-set), 후자는 **재개 시 cache 폐기·store 재파생**으로 **별개 메커니즘**이다. "0 = no stale window"의 극성이
S-3의 "stale cache 불신"과 같은 보수 방향일 뿐, 동일 메커니즘 주장 아님.

### 7.4 firewall/gap canary 규율 (O-4·O-5)

- **firewall 게이트**: 신규 `tos.staterestore` 전 파일이 `tools/tos_firewall_check.py`(:203) 통과 — subprocess/
  socket 등 금지 stdlib 직접 import 0·os.environ 0·R-reverse(outside `import tos` 0) 실측.
- **gap canary**(`tos/tests/slice/test_slice_gaps.py` 규율 상속): 신규 seam을 실행 가능한 관측으로 잠금 —
  (i) reconstruct_conservative 코도메인이 RECONCILED **구조 배제** 유지(`predicates.py:700-702` 회귀), (ii)
  staterestore가 실 on-disk store(in-memory 아님) 구조 검사, (iii) outside 테스트가 `import tos` **미포함**
  negative-grep(R-reverse 보증 = oracle 독립 O-3), (iv) 금지 stdlib 부재 grep, (v) **tos-wide non-transmitting
  불변식 보존(MINOR-3)** — staterestore가 `tos/__init__.py:6` "non-transmitting by construction"을 유지함을
  잠금: 로컬 durable 저장(disk)만 있고 egress(socket/broker route) 0인지 grep(persistence ≠ transmission).
- **committed canary 전수-grep**(누적 교훈): sanction 전 터치 표면(staterestore·outside·harness L3)의 **모든
  committed canary 전수-grep**·closure allowlist만으론 불충분. stale-.pyc 퍼지 필수(§8).

---

## 8. 테스트 스위트 계획

### 8.1 배치 (firewall 경계 준수)

- **inside tos/** (`tos/tests/staterestore/`, firewall 적용·subprocess 없음): store round-trip·reload
  보수 채움·no-stale re-derive의 **단일-프로세스 단위 테스트** + reconstruct_conservative property(seed=0).
- **outside tos/** (`tests/tos_l3/test_state_ev_004_crash_restart.py`, **forward 규칙(a-d) 미적용 ⇒ subprocess
  허용·reverse 규칙(e) 적용 ⇒ `import tos` 금지**, MINOR-1 정밀): **실 크래시-재개 통합 테스트** — worker
  spawn(§5.2)·§4 하드코딩 앵커 비교(§5.3, R-reverse가 oracle 독립 보증). 이것이 하네스 EV-L3 stage의 target
  노드. (대안 A 채택 시 inside `tos/tests/staterestore/`로 `mp.get_context("spawn")` 이동 — §5.2·OQ-4.)

### 8.2 비중복 매핑 (재-검증 금지)

| L3 fault | 인접 L1/L2 노드 | L3 추가분 |
|---|---|---|
| reconstruct 순수 투영 | orthostate L1 property(reconstruct_conservative) | 재-검증 아님(기존) |
| L3-01..04 재구성 | (없음/EV-L1은 in-memory) | **실 durable + 실 프로세스 경계 신규** |
| L3-05/06 incomplete/stale | (없음) | **실 크래시 산물 신규** |
| L3-08 durability | (없음) | **R-1 직접 방전 신규** |

### 8.3 뮤테이션 canary 실효성 (플레이북 §3.8)

each fault both-ways(가드 발화 ∧ 정당 통과) + §4 mutant A~E가 **outside 앵커 테스트를 FAIL(KILLED)** 실측 +
등가 뮤턴트 열거. mutant는 tos.staterestore reload 경로에 주입, oracle은 outside 하드코딩 앵커(O-3)라 구현 버그
독립 검출. **KILLED 실측이 OQ-2의 경험적 답**.

### 8.4 게이트 실행 환경

pytest = `PYTHONPATH=tos/src .venv/bin/python -m pytest`(pyenv=mypy 전용). worker도 동일 env(PYTHONPATH=
tos/src). **stale-.pyc 퍼지 필수**(pycache 오염이 위양성 유발 — 누적 교훈). firewall check·full suite green
재확인. rc + FAILED grep 판정.

---

## 9. 수용 기준 (축소된 정확한 형태 + 잔여 게이트)

**L3 실행 성립 주장(PASS 아님)**: "STATE-EV-004의 EV-L3 integrated crash-restart stage가 baseline B에서
결정론적으로 실행됐고, §4 카탈로그 전 crash scenario가 §5.3 독립 앵커 대비 재구성 Expected를 MET(또는
DEVIATION 기록·보존)했으며, 실 on-disk sqlite3 WAL store·실 프로세스 경계(writer_pid≠reader_pid)·L1∧L2
prior-stage 결속·modeled-axis residual 등재가 확인됐다. 이 run은 register row를 PASS로 이동시키지 않는다."

**축별 covered 주장**:
- **STATE-EV-001 R-1(durable)**: **조건부 방전(MINOR-4)** — 실 persistence+process가 durable 축 지시체를
  substrate-class로 실현. R-1 register 항 "**evidence limb discharged (substrate-class); §4-decision gate +
  substrate-class caveat OPEN — pending OQ-1**" 전이(무조건 "discharged" 아님). ⇒ durable 잔여는 evidence-limb
  수준 해소·§4 프로젝트 결정 gate 잔존(PASS는 §9 잔여 게이트 후).
- **STATE-EV-004(persistence+process+reconstruction)**: **실행**. network·credential-identity 축 **미방전**
  (R-N/R-I residual) ⇒ STATE-EV-004 자체는 **PASS-부적격**(자체 EV-L3 축 미완).

**PASS 전 잔여 게이트**:
1. **L1∧L2 THIS baseline 재실행**: HEAD 전진으로 기존 d4160fd0 패키지 M9-stale. 최종 baseline B에서 STATE-
   EV-001 **L1 → L2 → (STATE-EV-004) L3 연속 실행·중간 커밋 금지**(§11 절차).
2. **restart 축 coverage argument**(VER:79): boundary leg 충족 가능; adversarial leg = **ADVERSE-SCENARIO-
   SET-002-EVL3 운영자 승인 인스턴스**(EV-L2 파일럿의 EVL2-PILOT 동형·SoD reviewer≠approver:51). ADR-002-021
   PROPOSED이라 하네스는 `discharged:false` 기계 유지·**리뷰층 방전**.
3. **R-N/R-I residual**(§378): STATE-EV-004 자체 PASS는 network·credential 축 방전(EV-L4/+Security) 전까지
   불가. Critical이라 WAIVED 불가(VER:131).
4. **P0-1**: reconstruction bound-independent(§7.3)라 대부분 vacuous; null retention 키 미소비 확인.
5. **독립 서명**(VER §9.5, NOT_SIGNED)+운영자 countersign. **D1 혼합 scheme**(role-scheme §1): reviewer는
   저작 세션과 다른 모델 계열 우선(SPG-EV-002는 "Gemini"). 저작⊥리뷰 — 본 저작자·L3 구현자 서명 불가.
6. **VER §3 complete-baseline**(:110 "as applicable" 없음): ENGINE/live 트랙 아티팩트 실체화 전까지 구조 미충족.
7. **OQ-1(§4 프로젝트 persistence 결정)**: R-1 closure 충분성의 운영자 판정(파일럿-범위 vs §4 프로젝트).
8. **DEVIATION run 보존**(VER §2.2): 실패 run 삭제 금지·supersedes_run_id.

⇒ **acceptance = (L1∧L2∧L3 실행) ∧ R-1 방전 ∧ restart coverage(ADR-002-021 의존) ∧ P0-1 ∧ 독립 서명 ∧
complete-baseline; STATE-EV-004 자체는 추가로 R-N/R-I 해소.** 파일럿은 **L3 실행 1건 + persistence 결정 + R-1
방전 + residual/coverage 정직 등재**를 담당. **STATE-EV-001의 "durable 축 최초 방전"은 성립하나 그 PASS는 본
파일럿 범위 밖**(잔여 6+게이트).

---

## 10. L3 / L4+ / residual 경계 판정 요약 (정직 이연표)

| 축 | **L3 (본 파일럿)** | **이연 (residual/상위)** | 앵커 |
|---|---|---|---|
| real persistence | **포함** — sqlite3 WAL on-disk·크래시 생존 | (power-loss/torn-sector = R-D) | VER:153; §13:197; AC-005-1:237 |
| real process boundary | **포함** — 2 OS 프로세스·os._exit·pid≠pid | — | VER:153 |
| reconstruction(보수) | **포함** — POTENTIALLY_LIVE/UNKNOWN·Knowledge≠RECONCILED | — | VER:1046; §13:198-199 |
| logical identity 재파생 | **포함** — intent/attempt/order 식별자 store 재파생 | — | `predicates.py:735` |
| **real network** | **모델(이연)** — VirtualBroker 마커·실주문 0 | 실 broker 전송 = EV-L4/+Broker; 실선물 정책차단 | VER:153; 1045; CLAUDE.md; R-N |
| **credential/service identity** | **이연** | STATE-EV-005(+Security) | VER:1050; R-I |
| Recovery Barrier / 재-arm | **미포함** | ADR-002-017 별개 EV-L3 | §13:200 |
| STATE-EV-002 전 conservative-direction | restart limb만 접점·미종결 | timeout/ACK/query/cache/authority 주입 | 1031 |
| STATE-EV-003 coupling L3 | **미포함** | CPL/RCL 동시성 통합 | 1039 |

**한 줄**: L3 = 다중 컴포넌트(CompositeState+durable store+reload+reconstruct)를 **실 sqlite 저장·실 프로세스
크래시**로 통합해 보수 재구성 검증. **실 network·credential identity·Recovery Barrier·power-loss durability·
STATE-EV-002/003 L3 전부 이연.** R-1(durable)은 방전, STATE-EV-004 자체 PASS는 R-N/R-I로 미완.

---

## 11. 판단 지점 · Open Questions · 실행 절차

- **OQ-1 (최상위·§3.3)**: R-1의 "§4 persistence 결정 first" 요건 — 파일럿-범위 결정이 R-1 closure에 충분한가,
  아니면 §4 프로젝트 결정(ADR acceptance 인접)이 선행인가. **권고**: (b) 파일럿-범위 sqlite로 EV-L3 evidence
  limb 방전, §4 프로젝트 결정은 별개 open gate로 병기 — 단 **충분성 자체는 운영자/리뷰어 판정**(SPG coverage-
  discharge 동형). **리뷰어 판정 반영(SOUND)**: (b) 권고는 :177 문자적 요건("§4 first")을 만족하지 않으므로
  R-1 기록은 "**evidence limb discharged; §4 project-persistence gate + substrate-class caveat OPEN**" 형태의
  이중 기록이다(무조건 "discharged" 아님). **substrate-class caveat**: evidence-limb 방전은 ACID-durability
  substrate 위에서 **모델의 durable-restart 속성**을 검증한 것(substrate-class)이고, 상이한 §4 production 기술
  선택(역시 ACID)은 별도 production-acceptance EV-L3 소관이지 R-1을 **소급 무효화하지 않는다** — 이 caveat가
  파일럿-범위 결정을 방어 가능하게 하며 §4 gate와 R-1 evidence-limb을 분리한다.
- **OQ-2 (뮤테이션 실증)**: reload-path mutant A~E가 outside 앵커 테스트를 KILLED시키는지 — 구현·실행 시 실측.
  현재 미실증(설계 단계). §8.3이 의무화.
- **OQ-3 (crash 모델 충실도)**: os._exit(결정론·프로세스 크래시) vs 외부 SIGKILL(racy·harder). **권고**:
  결정론 os._exit를 acceptance 집합·외부 SIGKILL fuzz는 optional 하드닝(비-acceptance). power-loss는 R-D.
- **OQ-4 (staterestore 배치 + spawn 메커니즘 — MAJOR-1 병합)**: (i) 신규 `tos.staterestore` 패키지 vs
  orthostate 내부 모듈 — **권고**: 별도 패키지(orthostate `__init__.py:11` "no persistence" 순수성 보존). (ii)
  **프로세스-경계 spawn 메커니즘**(§5.2 대안 A/B): inside `mp.get_context("spawn")`(firewall 인증·oracle 독립
  관행적) vs outside subprocess(orchestration 인증 밖·oracle 독립 **구조적**) — **권고**: B(구조>convention),
  단 최종 채택은 하네스 소유자(OQ-5)와 구현 확정. 최종 명명/edge allowlist는 구현 확정.
- **OQ-5 (하네스 소유자)**: manifest v3 superset·STAGES 확장·outside 노드 target — 하네스 소유자 확인(L2 OQ-5
  상속).
- **OQ-6 (ADVERSE-SCENARIO-SET-002-EVL3 §11 그룹)**: EVL2-PILOT은 9 trading-scenario 그룹 전부 empty(순수
  모델)였다. EV-L3 restart는 execution_path/venue-broker-recovery 그룹에 **모델 전송 접점**이 생긴다 — 그러나
  실 broker 아니므로 여전히 "declared scope limitation"(NOT_APPLICABLE_AT_THIS_SCOPE·모델 전송 명기)로 처분할
  지, 부분 populate할지 = coverage-argument 소유자 판정. **권고**: 모델 축은 empty-with-declared-reason 유지·
  실 network는 R-N 명기(over-claim 금지).

**실행 절차 (최종 baseline B·중간 커밋 금지)**:
1. 구현: `tos.staterestore`(S-1..S-4) + outside 크래시 테스트 + 하네스 v3 확장 + self-test. firewall check green.
2. baseline B(최종 HEAD)에서 **연속 실행**: STATE-EV-001 L1 → STATE-EV-001 L2 → STATE-EV-004 L3 (전부 동일
   `baseline_commit_sha=B` — M9 게이트). full suite + firewall green·stale-.pyc 퍼지.
3. R-1 register 항 "discharged by `<L3 run_id>`" 전이 + R-N/R-I 신규 등재(12필드·비-union) + ADVERSE-
   SCENARIO-SET-002-EVL3 인스턴스(운영자 승인).
4. 독립 리뷰(attempt 1-3 패턴·decorrelated 모델 계열) + 운영자 countersign(SPG-EV-002 review 체인 상속).
5. push는 운영자 수동(`! git push` — 하네스 staleness 게이트는 HEAD `ee5e280d` 기준 살아있음, 메모리 기록).

**잔여 판단(오케스트레이터 보고)**: (a) OQ-1 = R-1 closure 충분성(파일럿-범위 sqlite) 운영자 판정 필요 —
**본 저작자 최대 미해결 쟁점**(substrate-class caveat로 방어). (b) crash 모델 = 결정론 os._exit 권고(§4·
gate-clean 실측). (c) spawn 배치 = **선택**(MAJOR-1 정정) — inside mp-spawn 가능하나 **구조적 oracle 독립**을
위해 outside subprocess 채택(구조>convention, §5.2). (d) 3 residual 신규(R-N/R-I/R-D)·R-1 조건부 전이·비-union.

---

## 12. 개정 로그

- **v1.1 (2026-08-06)** — 독립 비평 **REVISE**(CRITICAL 0·MAJOR 2·MINOR 4·NIT 3; phantom 0·핵심 아키텍처
  건전 판정) 반영. **전 finding 1차 소스 재실측 후 반영 — 재측정 결과 리뷰어 실측과 불일치 0**(반론 없음).
  - **MAJOR-1 (§5.2/§5.3)**: v1.0 전제 오류 정정 — outside 배치는 subprocess 금지 **강제가 아님**. `multiprocessing`
    spawn이 firewall 허용·기실사용(`test_import_closure.py:6`·`test_evidence_import_closure.py:106`
    `mp.get_context("spawn")` 실측)이라 **inside도 가능**. 대안 A(inside mp-spawn·oracle 독립 관행적)/B(outside
    subprocess·oracle 독립 **구조적** R-reverse)의 명시 검토표 신설. 채택 근거를 "subprocess 금지라서" →
    "**구조>convention**(플레이북 §6.1 메타②)·outside 복잡도를 지불하고 구조 독립 구매"로 재서술. §5.3 "방법론적
    발견"을 트레이드오프 명시로 조정.
  - **MAJOR-2 (§4/§5.1)**: crash 셀의 5차원 커밋 상태 전부 pin — v1.0의 CONFLICTED 앵커는 미결정이었음(§13:199
    "UNOBSERVED/CONFLICTED 둘 다 허용"·reconstruct는 pre∈{RECONCILED,CONSISTENT}만 강등, `predicates.py:729-732,
    683-685` 재측정). 앵커 = 다운그레이드/보존 맵 결정론 값 + 2층 독립 불변식 `K∉{RECONCILED,CONSISTENT}`. §5.1
    S-2에 부재 Knowledge→UNOBSERVED 채움 규약을 §13:199에서 논증. ④ "L3-08 직접 R-1 방전" → "durability 메커니즘
    셀; R-1 방전 = composite 경계집합 durability 속성 + coverage argument(§9 게이트 2)"로 정밀화.
  - **MINOR-1 (§5.2/§8.1)**: "firewall 밖 ⇒ 미적용" 정밀화 — `_REVERSE_SCAN_PRUNE`(`tos_firewall_check.py:114-116`)에
    `tests` 부재 실측 ⇒ forward(a-d) 미적용(subprocess 허용)·**reverse(e) 적용**(O-3 구조 독립의 근거).
  - **MINOR-2 (§6.2 게이트 #4)**: `evidence_id==STATE-EV-001` 결속 추가(STATE-EV-003도 EV-L1/3 READY·오충족 차단)
    + "prior L1∧L2는 STATE-EV-004 자체 요건 아니라 STATE-EV-001 durable-limb 연속성" 명시.
  - **MINOR-3 (§5.1/§7.4)**: tos-wide 비-transmitting 불변식(`tos/__init__.py:6`) canary 추가·staterestore가
    로컬 persistence(disk)만·egress 0 보존 못 박음(persistence≠transmission).
  - **MINOR-4 (§7.1/§9/OQ-1)**: 무조건 "discharged" → **OQ-1 조건부 이중 기록** + substrate-class caveat(ACID
    substrate class 검증·§4 production 기술 변경은 R-1 소급 무효화 아님).
  - **NIT-1** manifest v3 네임스페이스 주의(vs `_VER3_FIELDS`=VER §3)·**NIT-2** 게이트 개명 `PRIOR_EV_L1_AND_L2_
    NOT_BOTH_BOUND_AT_THIS_BASELINE`·**NIT-3** B_stale_epoch_reject "보수 방향만 정합"(epoch fencing≠cache 폐기).
  - **OQ-4**에 MAJOR-1 spawn 메커니즘 질문 병합. 리뷰어 OQ 판정(OQ-1 fail-closed 이중기록 SOUND·substrate-class
    caveat) 반영.
- **비준 (2026-08-06)** — 델타 재검증(동일 독립 리뷰어·연속 컨텍스트) **RATIFY-READY**: MAJOR 2건 FULLY
  RESOLVED(대안표 역-비용 명시·8셀 전수 결정론 재파생 확인, L3-07 §14:211/L3-08 §14:208 verbatim 합법·L3-08
  fixpoint 분리검증)·MINOR/NIT 전건 문구 정합·신규 앵커 phantom 0·부작용 0(§2.3 byte-동일·정책 온존). 비차단
  관찰 1건(pin 커밋 composite의 §14 미열거 조합 CPL 합법성) → §4 "커밋 composite CPL 합법성" 절로 반영
  (오케스트레이터 직접·기계적 정정 선례 #20/#23). 자동비준 위임에 따라 비준 기록. 실행 잔여 인간 게이트:
  OQ-1 R-1 closure 충분성·ADVERSE-SCENARIO-SET-002-EVL3 인스턴스 승인·countersign(§9·§11).
- **v1.0 (2026-08-06)** — 저작 초안. EV-L2 파일럿(v1.2)·방법론 플레이북(§0/부록 B/D/§5)·VER §5·STATE-EV-004
  (1041-1046)·ADR-002-005 §13(195-200)·§4(61)·AC-005-4(240)·reconstruct_conservative(688-742)·firewall
  (186-192)·PROFILE(null 17·MIN_evidence_retention_ms:923)·countersign(R-1:39-40)·RESIDUAL-RISK-REGISTER-002
  (R-1)·ADVERSE-SCENARIO-SET-002-EVL2-PILOT·role-scheme §1 전부 1차 소스 실측 후 작성. 핵심 판정: 열린-세계
  전이(시리즈 최초 실 I/O)·EV-L3 축 분할(persistence+process 실행·network/identity 이연)·firewall
  subprocess 금지 → outside spawn + oracle 독립(R-reverse)·pilot-scope persistence(OQ-1)·R-1 방전 vs
  STATE-EV-004 자체 PASS-부적격 비대칭. 독립 비평 리뷰 대기.

---

## 부록 A. 실측 인용 대장 (anti-phantom — file:line)

**VER-002-001**: EV-L1 143-145·EV-L2 147-149·**EV-L3 151-153**·EV-L4 155-157·EV-L5 159-161·composite notation
167-176(staged 172-173)·**§2.7 coverage 79**·complete-baseline 110·WAIVED 금지 **131**(enum 값 128)·bounded-
model 3171·**§378 register 3292-3310**(non-union 3308·broker-limitation 3310)·§379 checklist 3315-3345(restart
limbs 3327-3328)·**STATE-EV-001 1020-1025**(min 1022·sup AC-005-1 1023·inj 1024·exp 1025)·STATE-EV-002 1027-
1032(min EV-L2/3 1029·inj restart 1031)·STATE-EV-003 1034-1039(min EV-L1/3 1036·exp CPL 1039)·**STATE-EV-004
1041-1046**(min EV-L3 1043·sup AC-005-4 1044·inj 1045·exp 1046)·STATE-EV-005 1048-1053(min EV-L2/3+Security
1050)·1 PASS(SPG-EV-002) 6·292/79/1.

**ADR-002-005**: §4 "does not decide the persistence technology" **61**·§6 SEND_STARTED durable before external
call 96·**§13 Persistence and Restart 195-200**(durable+reconstructable **197**·restart POTENTIALLY_LIVE/
UNKNOWN 198·Knowledge never RECONCILED **199**·Recovery Barrier/re-arm **200**)·§14 composite 204-212·AC-005-1
"representable and persisted" **237**·**AC-005-4 restart 240**·§19 "restart reconstructs … in tests" 271.

**reconstruct_conservative** (`tos/src/tos/orthostate/predicates.py`): def **688-742**·docstring "durable
reload / crash recovery … EV-L3" **692**·codomain "structurally excludes RECONCILED" **700-702**·intent_identity
보존 735·_ATTEMPT_POTENTIALLY_LIVE_AFTER_RESTART 659-668·_BROKER_STRUCTURALLY_TERMINAL 672-679·**_KNOWLEDGE_
DOWNGRADE_ON_RESTART={RECONCILED,CONSISTENT} 683-685**·**Knowledge 강등/보존 분기 729-732**(pre∈set→CONFLICTED·
else 보존, MAJOR-2)·capacity 상향 714-719·may_transition send-boundary 594-650. **orthostate __init__**: "no persistence /
durable restart" 11·"pending EV-L2/L3 … durable persistence … real restart" 38-39·reconstruct export 68/114.

**register CSV** (`EVIDENCE-REGISTER-002.csv`): header 1·STATE-EV-001 **91**(EV-L1/2 READY)·STATE-EV-002 92
(EV-L2/3 NOT_IMPL)·STATE-EV-003 93(EV-L1/3 READY)·**STATE-EV-004 94**(EV-L3 NOT_IMPL·broker TBD)·STATE-EV-005
95(EV-L2/3+Security NOT_IMPL).

**firewall** (`2026-07-20-tos-boundary-and-import-firewall-design.md`): 허용목록 **186**(stdlib 전체·금지 11:
socket/ssl/http/urllib.request/ftplib/smtplib/poplib/imaplib/telnetlib/**subprocess**/ctypes·**multiprocessing
부재=허용**)·서드파티 187(pydantic/numpy/pandas/pytest/hypothesis/pyyaml·DB 없음)·**R-reverse 192**·scope
src+tests 166-167·AST 게이트 `tools/tos_firewall_check.py` 203-207. **firewall check 내부(v1.1 신규)**: os
검출 = environ/getenv만(**214-216 from-import·237-240 attr**; os._exit 미검출)·**_REVERSE_SCAN_PRUNE 114-116**
(`{tos,.git,.venv,node_modules,__pycache__,.omc,.history}` — **tests 부재**)·check_reverse_imports 306·reverse
line RE 120. **multiprocessing 기실사용(MAJOR-1)**: `tos/tests/test_import_closure.py:6`("fresh, isolated
interpreter (via `multiprocessing` spawn — `subprocess` and `os` are firewall-forbidden even in tests)")·:30
`import multiprocessing as mp`·`tos/tests/test_evidence_import_closure.py:106` `mp.get_context("spawn")`.
**tos-wide 불변식**: `tos/src/tos/__init__.py:6` "non-transmitting by construction (§4)".

**harness** (`tools/tos_evidence_run.py`): EV-L1/L2 header 2·never PASS 26·STAGE_L1/L2 129-130·STAGES 131·
is_l2 1902·build_baseline stage/schema 1231/1299/1327·**L2 게이트 2130-2149**(NO_PRIOR_EV_L1 2147)·manifest
v2/v1 2164·coverage_argument 2236-2258(discharged false 2248)·DISCIPLINE_TAG_L2 124·bind_prior_stage_run 903
(baseline_matches M9 920)·summarise_fault_schedule 786-889·check_l1_hardening 689·build_parser 1773(--evidence-
level-stage choices=STAGES 1820-1822·--covered-axis 1858·--residual-ref 1876·--prior-stage-run 1838). self-test
`tests/tools/test_tos_evidence_run.py`(1744행·discipline tag 389-391·no-PASS 395-401·ver3 baseline 340·
**`_VER3_FIELDS`=VER §3 22필드 293**[NIT-1 명명 충돌원]).

**PROFILE** (`VERIFICATION-PROFILE-002.yaml`): status APPROVED scope-limited 1-8·17 null fail-closed 6-8/30-31·
scope.environment non-live-test "EV-L1..L3 harness" 35/59·**MIN_evidence_retention_ms null 923**·B_stale_epoch_
reject 0 approved 228-232.

**residual/coverage/role**: RESIDUAL-RISK-REGISTER-002.yaml R-1(required_scope_reduction "§4 first … EV-L3 run
discharges" **177**·"cite STATE-EV-004 … real persistence substrate" 176·VER:131 unwaivable 149·detection
NOT_ESTABLISHED 153·owner/approver operator 161-165). SPG-EV-002 countersign(R-1 blocks STATE-EV-001 PASS 39-40·
SPG PASS first 31-33·coverage via ASS-EVL2-PILOT 25·P0-1 within 146 26). ADVERSE-SCENARIO-SET-002-EVL2-PILOT
(consumer 2 rows·§11 9 groups empty 90-147·ASS-CM-04 guards-are-oracles 590-597·SoD reviewer≠approver 51·
self_referentiality_caveat 158). role-scheme §1(D1 mixed·operator=owner/approver·reviewer diff model family·
Live-Armer unassigned·reviewer≠approver). gate-status(292/79/1 7·EV-L2/L3 ceilings 822).

**부재 (negative-grep)**: (1) `STAGE_L3`/`EV_L3`/`is_l3`/`manifest/v3` in `tos_evidence_run.py` = 0. (2) sqlite3/
fsync/실 파일쓰기 in `tos/src` = 0(sir `_member_is_open` 오탐뿐). (3) `tos-evidence/STATE-EV-004/` 디렉토리 =
0(EV-L3 run 미실행). (4) STATE-EV-004 Expected(1046) ms/duration/retention/threshold 토큰 = 0(bound-
independent). (5) `subprocess` in firewall 허용목록 = 0(금지 11에 포함). (6) **`multiprocessing` in firewall
금지목록 = 0 ⇒ 허용**(MAJOR-1·기실사용 `test_import_closure.py:6`). (7) `_REVERSE_SCAN_PRUNE`에 `tests` = 0
(reverse 규칙이 repo-root `tests/`에 적용 — O-3 근거, MINOR-1).

**플레이북**: 저작자 절 27·부록 B §0.5 13항 531·부록 D 극성 600·**§5 열린-세계 전이 423-447**(닫힌→열린 428·
새 레인 442·배선 fail-open 436·결정론 canary 437)·§3.8 뮤테이션 KILLED 388. **EV-L2 파일럿**: C1 durable 판정
§2.2·R-1 residual §9·축 분할 대안 A/B/C §2.3·L1 하드닝 위치 §5.
