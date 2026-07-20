# 설계 문서 #1 — `tos/` 경계 & import-firewall 계약 (2026-07-20, v2)

> **비준 기록**: **2026-07-20 운영자 비준 (v2)**. 효력 발생 — IMPLEMENTATION-PLAN-002
> §2 경계의 프로젝트 측 확정 + Phase 1(EV-L1, 비전송) 코드/테스트 작성 착수 승인.
> bounds 승인·독립 리뷰어 지정은 별도 게이트로 유지(§0).
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. **비준 대상** —
> 운영자(단일 운영자, DR-0001 거버넌스)의 본 문서 승인이
> [IMPLEMENTATION-PLAN-002](../../tos-spec/src/part-1-foundation/verification/IMPLEMENTATION-PLAN-002.md)
> §0/§1이 요구하는 "greenfield TOS boundary + mechanism substrate 배치" 비준의
> 구체적 입력물이 된다. 본 문서는 tos-spec에 대해 **non-normative**이며 스펙 텍스트를
> 변경하지 않는다(broker-agnostic 원칙: KIS 언급은 프로젝트 측 문서인 여기에만 존재).
>
> **선행 문서**: [2026-07-20 tos-spec 재사용성 분석](2026-07-20-tos-spec-reuse-analysis.md)
> — 본 계약은 그 분석의 판정(전략 B + 비협상 조건 C1/C2/C3)을 운영 가능한 규칙으로
> 고정한다.
>
> **리뷰 이력**: v1은 독립 비평 리뷰에서 **REJECT** (CRITICAL 2 — 허용목록의
> backtest 모듈이 금지 패키지 `shared.execution`·MLflow/Optuna를 전이 import함을
> 실증; MAJOR 5 — default-deny 미구현·역방향 엣지 불완전·C2 도구 미지정·manifest
> VER 미달·동적 import 사각). v2는 전 항목을 반영했다(§6.1 개정 로그).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

**확정하는 것**
1. tos ↔ kis_unified_sts의 관계 모델(3단계, §1) — 이후 혼선 방지의 기준 서사.
2. 그린필드 경계의 정확한 배치(§2) — 무엇이 `tos/` 안이고 무엇이 밖인가.
3. import의 정의와 firewall 규칙, 기계적 강제 수단(§3) — C1.
4. SAFE-045 논증(§4) — C2. (계층 방어로 정식화; "코드 경로 전무" 과장 제거)
5. 아티팩트 분리·재현성 기록 계약(§5) — C3.
6. 경계 개정 절차와 (C) 추출 트리거(§6).

**하지 않는 것**
- ADR acceptance, restricted-live, production 어느 것도 승인하지 않는다
  (ARCHITECTURE-GATE-STATUS §8의 NO 3종은 그대로).
- tos/ 내부 컴포넌트 아키텍처를 정의하지 않는다 — 그것은 RFC-002가 이미
  정의했고, 구현 배치는 설계 문서 #2(Capsule)·#3(EV-L1 하네스)·#4(Evidence
  Store)가 이어받는다.
- VERIFICATION-PROFILE-002 bounds 승인·독립 리뷰어 지정을 대체하지 않는다
  (Phase 0의 별도 인간 게이트 — evidence *완결*의 선행 조건이며, 본 문서 비준으로
  Phase 1 *코드+property test 작성*은 착수 가능해진다).

---

## 1. 관계 모델 — tos와 kis_unified_sts (혼선 방지 기준 서사)

**요지**: "별개 프로젝트"도 아니고 지금 당장 "tos 위의 kis"도 아니다.
**지금은 의존 엣지가 없는 격리 동거, 최종 상태에서는 kis_unified_sts의 트레이딩
기능이 TOS 위에 올라가는 역전(inversion)** 관계다. `kis_unified_sts`라는 이름은
**repo/호스트**로 남고, 그 안의 트레이딩 기능이 단계적으로 TOS의 첫 번째
입주자(first tenant)가 된다.

### 1.1 1단계 — 현재 (Phase 1, EV-L1, 비전송): 격리 동거

```text
        shared/ 순수 커먼즈 (indicators·config·models·resilience·determinism[신설])
              ↑ import                        ↑ import
     ┌────────┴─────────┐          ┌──────────┴──────────────────┐
     │ tos/ (커널 건조 중)  │          │ 운영 시스템 (services/*, 현행 paper/live) │
     └──────────────────┘          └─────────────────────────────┘
             ← 양방향 import 금지 (CI hard gate) →
```

- `tos/` ↔ 운영 시스템 사이에는 **어느 방향으로도 import 엣지가 없다.**
  - tos → 운영 금지: SAFE-045·그린필드 위임(재사용 분석 S1~S5).
  - 운영 → tos 금지: 운영 시스템이 미검증 커널에 의존하면 tos의 아티팩트
    identity·hermetic 테스트·failure-domain 논증이 오염되고, 향후 repo 분리(전략
    C) 옵션이 막힌다. **금지 범위는 shared/services/cli만이 아니라 tos/ 밖의
    모든 파이썬 코드다**(§3.2 R-역방향).
- 둘이 공유하는 것은 **순수 커먼즈(§3.2 허용목록)** 뿐이다.
- **승격 규칙**: 양쪽에 필요한 코드가 생기면 cross-import가 아니라 **커먼즈로
  승격**한다. dual-use 리팩토링(지표 SoT, config artifact identity, 원장
  append-only 하드닝 등 — 재사용 분석 §5.1)은 전부 커먼즈에 떨어진다.
  첫 적용 사례가 §3.4의 `shared/determinism` 추출이다.

### 1.2 2단계 — 중기 (EV-L2~L4): 콘텐츠 이주

- `shared/kis`의 KIS 지식은 tos 쪽 **Broker Capability Profile(KIS 인스턴스) +
  Broker Adapter**로 재저작된다(§7 시퀀스 8단계, ADR-002-004). 전략의 알고리즘
  콘텐츠도 DSL 아티팩트로 추출되기 시작한다.
- 커먼즈는 **별도 빌드 가능한 배포 단위로 분리**한다(§5.2). 목표 의존 그래프:
  `tos → commons ← kis-app`. tos ↔ kis-app 엣지는 여전히 0.

### 1.3 3단계 — 최종 (ADR acceptance → restricted-live → production): 역전

- **kis_unified_sts의 트레이딩 기능이 TOS 위의 콘텐츠/프로파일로 올라간다**:
  KIS Broker Capability Profile + DSL 전략 아티팩트 + evidence-producing 모델 +
  오퍼레이터 UI.
- 이 역전은 선택이 아니라 스펙의 강제다: ARCHITECTURE-GATE-STATUS §7 시퀀스
  7단계가 **"remove every direct live broker-order path"** 를 요구하므로, 동일
  계좌/스코프에서 현행 `OrderExecutor` live 경로와 TOS Egress Gateway는 영구
  공존할 수 없다. **라이브 컷오버 = 레거시 이그레스 폐기**다. (백테스트·스크리너·
  대시보드 등 non-live 도구는 TOS 주변에 남을 수 있다.)
- repo 분리(전략 C) 재검토 시점도 정확히 여기다(§6.2).

### 1.4 기각한 대안 (기록)

- **처음부터 완전 별개 프로젝트**: 커먼즈 dual-use 이점 상실, 단일 운영자에게
  repo 2개 유지비를 즉시 부과. (재사용 분석 §4의 (C) 이연 사유와 동일.)
- **운영 시스템을 지금부터 점진적으로 tos 위로 마이그레이션**: 운영 중인
  paper/live가 미검증(EV-L1 미완) 커널에 의존하게 되고, tos가 운영 요구에
  역제약을 받아 그린필드 위임이 무너진다. 역전은 evidence가 쌓인 뒤(live gate)
  스코프 단위로 일어난다.

---

## 2. 그린필드 경계의 배치

배치 원칙(재사용 분석 §4.2): **authority · ordering · integrity · containment을
보유하면 경계 안(그린필드), 순수 · 무권한 · evidence-producing 계산이면 경계
밖(커먼즈, 단방향 import).**

### 2.1 경계 안 — `tos/`에서 신규 저작

- IMPLEMENTATION-PLAN §2의 9개 코어: RCL, Safety Authority, Trustworthy Time,
  Live Authorization, Egress Gateway, Reconciliation, Recovery Coordinator,
  Protective Action Controller, Safety Profile Validator.
- 본 분석이 추가로 경계 안에 넣는 것: **DSL runtime/Enforcement, Evidence Store,
  Currentness Sequencer, Safety Commit Log substrate(조달 가능), Intent Registry,
  Order Construction, Venue Constraint Gate, Action Flow Governor, 전
  governance/release-admission(ADR-002-025..030), 오퍼레이터 safety-critical
  control path.**
- Phase 1 범위는 이 중 EV-L1 대상의 **순수·비전송 모델 + property test**만이다
  (IMPLEMENTATION-PLAN §4 Phase 1).

### 2.2 경계 밖 — 커먼즈로 재사용 (tos가 import)

- `shared/indicators` (순수 계산, multi-backend + shadow)
- `shared/config` (ConfigLoader, Pydantic 기반; 단 `shared.config.secrets` 제외 — §3.2)
- `shared/models` (어휘 수준 dataclass)
- `shared/resilience`, `shared/utils`, `shared/exceptions`
- `shared/determinism` (**신설 예정**, §3.4) — LookaheadGuard·결정론 리플레이
  프리미티브의 무의존 추출본. **추출 완료 전까지 `shared/backtest` 계열은 tos에서
  import 전면 금지**(v1의 모듈 한정 허용은 전이 import 실증 문제로 철회 — §6.1).

### 2.3 경계 밖 — 운영 시스템 전용 (tos가 직접·전이 모두 import하지 않음)

- `shared/execution`, `shared/kis`, `shared/streaming`, `shared/llm`,
  `shared/storage`, `shared/backtest`(§3.4 추출 전까지), `services/*`, `cli/*` —
  사유는 재사용 분석 §2(F1·F2 판정, S1~S5). KIS 지식은 2단계에서 Capability
  Profile로 **재저작**되어 들어오지, import로 들어오지 않는다. LLM 값은 Capsule
  데이터로 pre-capture되어 들어오지(ADR-DEV-003), `shared/llm` import로 들어오지
  않는다.

### 2.4 `tos/` 레이아웃 (초기)

```text
tos/
  pyproject.toml        # 독립 배포 단위 (배포명 "tos", requires-python ">=3.11", §5)
  src/tos/
    __init__.py
    models/             # EV-L1 순수 모델 (capacity·authority epoch·time health·...)
    capsule/            # Decision Context Capsule 계약 (설계 문서 #2)
    evidence/           # Evidence Store 계약 (설계 문서 #4)
    harness/            # property-test·fault-injection 하네스 (설계 문서 #3)
  tests/                # hermetic 전용 (.env 비주입, 외부 I/O 금지)
```

- 내부 세분화는 후속 설계 문서가 정의한다. 원칙: **subpackage는 RFC-002 §10
  컴포넌트 분해를 따른다** (스펙 용어 = 코드 용어).
- **firewall 적용 범위는 `tos/` 전체다** — `src/`뿐 아니라 `tests/`도 §3의 동일
  허용목록을 따른다(테스트가 금지 모듈을 import하면 hermetic 주장이 무너진다).

---

## 3. Import Firewall (C1)

### 3.1 "import"의 정의와 규칙 구조

- **직접 import**: `tos/` 내 소스가 문면에 적는 import 문. → **허용목록(§3.2)
  default-deny**: 목록에 없으면 전부 위반.
- **전이 import**: 허용한 모듈이 끌어오는 의존의 총체(import closure). → 내부
  금지 패키지(§2.3)에 대해서는 **전이 포함 금지**: 허용목록의 어떤 항목도 §2.3
  패키지를 closure에 포함해서는 안 된다. (v1 REJECT의 근원이 이 정의 부재였다.
  stdlib/서드파티의 전이 closure는 §4의 계층 방어와 잔여 리스크로 다룬다.)

### 3.2 허용목록 v2 (직접 import 기준)

| 분류 | 허용 항목 | 비고 |
|---|---|---|
| 표준 라이브러리 | 전체, **단 다음 직접 import 금지**: `socket`, `ssl`, `http`, `urllib.request`, `ftplib`, `smtplib`, `poplib`, `imaplib`, `telnetlib`, `subprocess`, `ctypes` | egress/프로세스/FFI 프리미티브 — C2(§4)와 DSL escape-closure 정신. `importlib`·`__import__`·`exec`/`eval` 동적 import는 §3.3-③에서 별도 금지 |
| 서드파티 | `pydantic`, `numpy`, `pandas`, `pytest`, `hypothesis`, `pyyaml` | EV-L1 최소. **버전은 `tos/pyproject.toml`에 고정(pin)**하고 run manifest에 기록(§5.1). 추가는 §6.1 개정 절차 |
| 커먼즈 | `shared.config`(**`shared.config.secrets` 제외**), `shared.models`, `shared.indicators`, `shared.resilience`, `shared.utils`, `shared.exceptions` | 패키지 단위 허용은 "그 패키지의 closure가 §2.3을 포함하지 않는다"는 검증(§3.3-②) 하에서만 유효. secrets 제외 사유: ambient 자격증명 접근은 C2와 충돌 |
| 커먼즈(신설 후) | `shared.determinism` | §3.4 추출 완료 + §6.1 개정 로그 등재 후에만 |
| 자기 자신 | `tos.*` | — |

**R-역방향 (전면 금지)**: `tos/` **밖의 어떤 파이썬 코드도** `tos`를 import할 수
없다 — `shared/`, `services/`, `cli/`, `core/`, `jobs/`, `scripts/`, `tests/`,
repo 루트 모듈 전부 포함. (v1의 열거식 3개 패키지는 불완전 — §6.1.)

### 3.3 기계적 강제 — CI hard gate

convention은 금지다(재사용 분석 S4: convention 순수성은 이미 실패한 전례).
**import-linter만으로는 §3.1 default-deny를 표현할 수 없으므로**(계약 타입이
전부 denylist 계열), 강제는 3층으로 구성한다:

1. **① 커스텀 AST 게이트 (1차, default-deny의 실제 구현)** —
   `tools/tos_firewall_check.py`: `tos/` 전체(src+tests)의 모든 `.py`를 AST
   파싱하여 (a) 최상위 import가 §3.2 허용목록에 없으면 실패, (b) §3.2 금지
   stdlib 직접 import 검출, (c) `os.environ`/`os.getenv` 사용 검출(C2), (d)
   `importlib.import_module`/`__import__`/`exec`/`eval` 검출(동적 import 우회
   차단), (e) repo 전체 스캔으로 tos/ 밖 파일의 `import tos` 검출(R-역방향).
2. **② import-linter (2차, 내부 금지 패키지의 전이 방어)** — repo 루트
   `.importlinter`에 forbidden contract: source `tos` → forbidden `shared.execution`,
   `shared.kis`, `shared.streaming`, `shared.llm`, `shared.storage`,
   `shared.backtest`, `services`, `cli`. **간접(전이) 검출 활성 상태로 운영한다**
   (`allow_indirect_imports` 사용 금지) — 허용 커먼즈가 금지 패키지를 끌어오면
   여기서 실패한다.
3. **③ CI 잡 `tos-firewall`**: 모든 PR에서 실행(경로 게이팅 없이 — 저비용이고
   우회 여지를 없앤다). ①+② + `pytest tos/tests`(hermetic). **required check**로
   지정 — 실패 시 머지 불가.
4. **우회 기록**: 게이트를 우회(계약·게이트 스크립트 수정 포함)하는 모든 변경은
   §6.1 개정 로그에 사유와 함께 기록한다. 반복 우회는 (C) 추출 트리거다(§6.2).

### 3.4 선행 커먼즈 승격 작업 — `shared/determinism` 추출

v1 허용목록의 backtest 모듈 2건은 실증 리뷰에서 철회됐다:
`shared/backtest/__init__.py`가 MLflow/Optuna를 eager import하고(서브모듈
import로도 부모 `__init__` 실행), `market_context_replay.py:34`가
`shared.execution.contract_spec`을 직접 import한다. 따라서:

- **작업**: `LookaheadGuard`(현 71 LOC)와 결정론 리플레이 프리미티브를
  **import 부작용 없고 §2.3 의존이 없는** 신규 커먼즈 `shared/determinism/`으로
  추출한다. replay가 물고 있는 `ContractSpec`은 순수 데이터 스펙이므로
  `shared/instruments`로의 이동을 함께 검토한다(재사용 분석 F6
  REUSE-**AFTER-REFACTOR** 판정의 이행).
- **성격**: §1.1 승격 규칙의 첫 적용 사례이자 dual-use 리팩토링(운영 백테스트도
  동일 프리미티브를 소비 가능).
- **순서**: 설계 문서 #3(EV-L1 하네스)이 이 모듈에 의존하므로 #3 착수 전 완료.

---

## 4. SAFE-045 논증 (C2) — 계층 방어

SAFE-045(RFC-001 §, "live 주문을 전송할 수 있는 인터페이스"의 비-live 환경 보유
금지; 런타임 플래그로 live capability 획득 금지). 현행 시스템은 플래그로 이를
위반한다(재사용 분석 S1). `tos/`는 다음 **계층 방어**로 만족한다 — v1의 "어떤
코드 경로도 없다"는 단일 논증은 과장이라 철회(§6.1)하고, 방어를 명시적으로
분해한다:

1. **자격증명·라우트 부재 (1차 방어)**: tos closure 어디에도 브로커 자격증명,
   토큰, 엔드포인트/라우트 설정, 주문 구성 코드가 없다. `shared.config.secrets`
   제외(§3.2), tos 테스트 `.env` 비주입(§2.4). live-order *인터페이스*는
   자격증명+라우트+주문구성 3요소 없이는 성립하지 않는다.
2. **이그레스 코드 금지 (2차)**: 내부 금지 패키지(execution/kis)는 직접·전이
   모두 차단(§3.3-②), stdlib egress 프리미티브는 직접 import 금지(§3.3-①b).
3. **플래그 금지 (3차)**: `os.environ`/`os.getenv` 사용 금지(§3.3-①c) — 설정은
   버전드 아티팩트로만 진입(config version이 모델 순수함수 서명의 일부).
   capability를 켤 플래그 읽기 자체가 lint 위반이다.
4. **동적 우회 금지 (4차)**: 동적 import/`exec` 금지(§3.3-①d)로 정적 분석
   사각지대를 봉쇄.
5. **역방향 보호 (5차)**: tos/ 밖 코드의 tos import 전면 금지(R-역방향)로, tos를
   경유한 새 live 경로 생성이 불가능.

**잔여 리스크 (정직 기록)**: 허용 커먼즈의 전이 closure에 stdlib 네트워크
프리미티브가 로드될 수 있다(예: `shared.resilience` → `http.client`,
`shared.config` → `socket`/`subprocess` — 리뷰 실측). 이는 자격증명·라우트·주문
구성 코드가 부재한 상태에서 live-order 인터페이스를 구성하지 않으므로 SAFE-045
위반이 아니라고 판단하되, **커먼즈 closure 검토를 설계 문서 #3의 점검 항목**으로
넘기고, §5.2 커먼즈 추출 시 최소화한다.

**미래의 live 경로**: TOS의 live 전송은 오직 ADR-002-013 Egress Gateway 구현 +
ADR-002-007/025 게이트를 통해서만, 별도 비준으로 추가된다. 그 전까지 tos는
정의상 non-transmitting이다.

---

## 5. 아티팩트 분리·재현성 기록 계약 (C3)

### 5.1 Phase 1 계약

- `tos/`는 **자체 `pyproject.toml`을 가진 독립 배포 단위**다(배포명 `tos`,
  src-layout, `requires-python ">=3.11"`). 개발 중 monorepo venv에 editable
  설치는 허용한다. 서드파티 의존은 버전 고정(pin)한다(§3.2).
- **evidence를 산출하는 모든 실행**(property-test run 포함)은 run manifest에
  다음을 기록한다 — VER-002-001 **§2.3(재현성)·§3(run baseline: "baseline 없는
  run은 무효")·§9.1(append-only run 기록, seed 포함)·§9.2(보존 아티팩트 전수
  digest)** 의 EV-L1 부분집합:
  1. git commit digest + `tos` 패키지 버전
  2. 인터프리터 버전 + 고정된 의존성 버전 세트(numpy/pandas/pydantic/hypothesis 등)
  3. 실행 환경 식별자(OS/아키텍처)
  4. 하네스(테스트 코드) 버전 — Phase 1은 git digest로 갈음
  5. **property-test seed**(hypothesis seed/derandomize 정책) — append-only 기록
  6. 소비한 설정 아티팩트 digest
  7. 보존하는 산출 아티팩트 전체의 sha256
  (EV-L2 진입 시 §9.1의 fault schedule 기록이 추가된다.)
- 커먼즈 pinning은 Phase 1에서는 **git commit-digest 방식**으로 충분하다
  (tos와 커먼즈가 같은 커밋에 있으므로). 단 위 manifest 항목 2·5가 있어야
  "같은 커밋"이 재현성으로 성립한다.

### 5.2 2단계 전환 (EV-L2 진입 전후)

- hermetic closure가 필요해지는 시점에 §3.2 커먼즈 허용목록을 **별도 빌드
  가능한 commons 배포 단위로 추출**한다(§1.2). 이때부터 tos 빌드는
  content-addressed 자체 아티팩트 + 버전 고정된 commons에만 의존한다.
- ADR-002-029(release admission)의 본격 이행은 그 이후 단계의 설계 문서가
  정의한다. 본 계약은 그 이행이 가능하도록 **배포 단위 분리와 digest 기록을
  지금부터** 강제하는 것까지만 담당한다.

---

## 6. 개정 절차와 트리거

### 6.1 firewall/경계 개정 절차

- §3.2 허용목록 변경, §2 경계 이동, 서드파티 추가는 **본 문서를 수정하는 PR**로만
  가능하며, 아래 개정 로그에 (날짜, 항목, 사유) 1줄을 남긴다.
- 개정 로그:
  - 2026-07-20: v1 최초 작성 (재사용 분석 판정 반영).
  - 2026-07-20: v2 — 독립 비평 리뷰 REJECT 반영. (C-1/C-2) backtest 모듈 2건을
    허용목록에서 철회하고 `shared/determinism` 추출을 선행 작업으로 신설(§3.4);
    (M-1) default-deny를 커스텀 AST 게이트로 실제 구현(§3.3-①); (M-2) 역방향
    금지를 "tos/ 밖 전부"로 확장(R-역방향); (M-3) C2 lint 도구/CI 배선 확정 +
    stdlib egress 직접 import 금지 + §4를 계층 방어로 재프레이밍; (M-4) run
    manifest를 VER §2.3/§3/§9.1/§9.2에 정렬(seed·환경·의존성 버전 추가, 인용
    정정); (M-5) 동적 import 금지(§3.3-①d); (m-1/m-2) 의존성·Python 버전 고정;
    (m-3) firewall 범위를 tos/tests까지 확장; `shared.config.secrets` 허용목록
    제외.
  - 2026-07-20: **v2 운영자 비준.** §6.3 선행 작업 2건(`shared/determinism` 추출,
    firewall 게이트 구축) 착수.
  - 2026-07-20: **선행 작업 2건 완료.** ① `shared/determinism` 신설(§3.4 이행 —
    `LookaheadGuard`·결정론 리플레이 프리미티브 이동, `ContractSpec`은 순수 데이터
    스펙으로 확인되어 `shared/instruments`로 이동, 구경로는 re-export shim; closure
    검증 테스트로 §2.3·MLflow/Optuna 무유입 확인). ② 3층 게이트 구축(§3.3 —
    `tools/tos_firewall_check.py` AST default-deny(a~e), `.importlinter` 전이 검출
    forbidden contract, CI 잡 `tos-firewall`) + 최소 `tos/` 스켈레톤(§2.4,
    pyproject 독립 배포 단위·hermetic tests). 이로써 §3.2 `shared.determinism`
    허용목록 효력 발생. 잔여 수동 조치: GitHub branch-protection에서 `tos-firewall`
    required check 지정 — **단 워크플로우가 `main`에 착지한 뒤에** 등록한다(A안,
    2026-07-20 결정). 워크플로우가 `main`에 없는 상태에서 먼저 required로 지정하면
    해당 잡을 갖지 않은 PR이 "Expected — waiting for status"로 머지 무기한 차단됨.
    현행 `main` 보호의 required check는 `test` 1건.

### 6.2 repo 분리(전략 C) 재검토 트리거 — 아래 중 하나라도 발생 시

1. live gate(ADR acceptance) 근접 — 분리된 identity/credential·evidence-backed
   isolation을 monorepo 빌드가 깨끗이 산출하지 못할 때.
2. CI firewall 게이트의 반복적 우회/약화 시도.
3. 커먼즈 추출(§5.2) 후에도 tos 빌드가 kis_unified_sts 배포물에 사실상
   의존하게 될 때(provenance 오염).

### 6.3 후속 작업·설계 문서 (본 계약 위에서)

| # | 항목 | 의존 |
|---|---|---|
| 선행 | `shared/determinism` 커먼즈 추출 (§3.4, dual-use) + `tools/tos_firewall_check.py`·`.importlinter`·CI 잡 구축 (§3.3) | 본 계약 비준 |
| #2 | Decision Context Capsule + Snapshot 계약 (ADR-002-018) | 본 계약 §2.4 |
| #3 | EV-L1 순수 모델 계층 + property-test 하네스 (RFC-004..007, ADR-DEV-010) — 커먼즈 closure 검토 포함(§4 잔여 리스크) | #2, 선행 작업 |
| #4 | Evidence Store 계약 + append-only ledger (ADR-002-016) | 본 계약 §5 |
| 병렬 | DSL 설계 (RFC-008, ADR-DEV-001) — EV-L1 크리티컬 패스 아님 | #2 |

---

## 7. 비준 체크리스트 (운영자 확인 사항)

- [ ] §1 관계 모델(격리 동거 → 콘텐츠 이주 → 역전)에 동의
- [ ] §2 경계 배치(안/커먼즈/운영 전용 3분류, backtest는 §3.4 추출 전 금지)에 동의
- [ ] §3.1 import 정의(직접=default-deny 허용목록, 내부 금지 패키지=전이 포함 금지)에 동의
- [ ] §3.2 허용목록 v2(stdlib egress 금지 목록, secrets 제외, 서드파티 pin) + §3.3 3층 강제(AST 게이트·import-linter 전이 검출·required CI check)에 동의
- [ ] §3.4 `shared/determinism` 추출을 선행 작업으로 승인
- [ ] §4 SAFE-045 계층 방어 논증과 잔여 리스크 기록에 동의
- [ ] §5 C3(독립 배포 단위, requires-python 3.11+, run manifest 7항목, commons 추출은 2단계)에 동의
- [ ] §6.2 (C) 추출 트리거에 동의

비준 시 효력: IMPLEMENTATION-PLAN-002 §2 경계의 프로젝트 측 확정 + Phase 1
(EV-L1, 비전송) 코드/테스트 작성 착수 승인. bounds 승인·독립 리뷰어 지정은 별도
게이트로 남는다(§0).
