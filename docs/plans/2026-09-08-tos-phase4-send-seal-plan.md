# TOS Phase 4 작업 6 — SEND_STARTED 이전 불변 봉인 tuple(`SendSeal`)

- **상위**: 개발계획 §6 Phase 4 작업 6 «exact outbound bytes, credential principal, endpoint, account, environment, request digest 를 SEND_STARTED 이전에 하나의 불변 tuple 로 봉인» · ADR-002-013 §12 «No security-relevant field may be supplied or changed downstream after the proof comparison … if request bytes differ, no send is permitted» · Phase 4 슬라이스 #1 계획 §1 «작업 6 은 #655 머지 후» → 지금.
- **선행**: 커널 라운드 #1(`feat/tos-phase2-kernel-round-1` · approve) — 이 브랜치 `feat/tos-phase4-send-seal` 은 그 위 스택(같은 `egressgw/gateway.py` 를 편집).
- **저작**: 세션 모델 단독 · 권한 부여 없음 · EV 행 상태 변경 0(EGRESS-EV-003 «byte-level reconstruction/route confinement = +Security» 는 이 슬라이스로 닫히지 않는다 — 합성 transport 의 바이트는 합성) · 실 브로커 transport 0.
- **서베이 실측(2026-09-08 · `2ff65bbc`)**:
  - `gateway.py::__call__` 순서: step 15 verify → `outbound_binding_mismatch` → step 16 `_ledger.claim(principal, request_digest, 두 nonce)` → `SEND_STARTED` 증거 → step 17 `POTENTIALLY_LIVE_OBSERVED` → **step 18 에서야 `outbound_coordinates(context)` 파생**(:1706) → `send_once(attempt, instrument_key, coordinates, quantity, price, side, reference)`. 즉 봉인 대상 좌표는 SEND_STARTED «뒤» 에 파생되고, 파생 실패는 `OUTBOUND_COORDINATE_DERIVATION_RAISED` 로 SEND_STARTED 뒤에 halt.
  - 클레임의 `context.principal`/`context.request_digest`(records.py:631-632) 와 `EgressRequestRecord.active_principal`/`request_bytes_digest`(egress/records.py:274-290) 는 **서로 결속 검사 없음**. item 17 `exact_binding_holds` 는 `request_bytes_digest == capsule_egress_request_digest` 와 좌표 10종(`EgressCoordinateSet.COORDINATES`: endpoint·account·environment·action·method·route_identity·credential_generation·broker_session_generation·egress_generation·active_principal) 동일성만 본다.
  - `Transport.send_once` 는 두 Protocol(`egressgw.gateway.SendTransport` · `brokeradapter.protocol.Transport`)로 이중 선언 + 서명 드리프트 canary(`test_seam_engine_brokeradapter.py:384`) + «retry/idempotency/credential/session 파라미터 부재» 핀(`test_brokeradapter_transport.py:79,103`). `SyntheticPaperTransport.send_once` 는 `OutboundSendRequest` 를 `requests` 에 보존.
  - 게이트웨이는 `CanonicalizationScheme` 을 갖지 않는다(grep 0) — 봉인 digest 계산엔 주입 필요(`tos.canonical` 은 커널 허용).
  - 런타임 `_wiring.py:824-833`: authorized 좌표가 리터럴(`action="NEW_ORDER"`·`method="SUBMIT"`·`route_identity="synthetic-route"`·세대 0/0/1·`active_principal=f"egressgw-{env}"`) 이고 `capsule_egress_request_digest` 는 `{account, instrument}` 두 필드 digest — 봉인이 이 값들에 하중을 주는 순간 비협상 규칙(설정 파일) 위반이 드러난다. `_egress_attestations.py`(item 6/12/16 attestation 로더) 가 같은 파일 패턴의 선례.
  - 크기 register: `gateway.py`(1850)·`__call__`(254)·`records.py::send_boundary_context` 등재.

## 0. 공통 규율

커널 라운드 #1 §0 그대로. 추가: **같은 파일은 한 레인에만**(`_wiring.py` 는 레인 R 전용 · `gateway.py`/`records.py`/`protocol.py`/`synthetic.py` 는 레인 K 전용) · 봉인은 «기록» 이 아니라 **transport 호출의 유일한 입력 원천** 이어야 한다(봉인과 별도로 context 를 다시 읽어 인자를 만들면 결함).

## 1. 레인 K — 커널 (`tos/src/tos/egressgw` · `tos/src/tos/brokeradapter` · 선행)

### 1.1 `SendSeal` 레코드 — 신규 모듈 `tos/src/tos/egressgw/seal.py`

`SendSeal(FrozenModel)` — covered 전부 필수(None 불허 · 생성 자체가 거부 = 타입 봉인):
- 정체: `attempt_id` · `instrument_key`
- 요청: `request_bytes_digest`(= `egress_request.request_bytes_digest`) · `canonical_command_digest` · `capsule_egress_request_digest`
- 주체·경로(ADR-002-013 §8/§10 좌표): `claim_principal`(= `context.principal`) · `active_principal` · `endpoint` · `account` · `environment` · `route_identity` · `credential_generation` · `broker_session_generation` · `egress_generation` · `action` · `method`
- 단일 사용: `capability_nonce` · `action_flow_permit_nonce`
- 실제 outbound(transport 에 넘길 정확한 값): `outbound_coordinates: tuple[tuple[str, str | None], ...]`(= `outbound_coordinates(context)` 의 결과 그대로) · `outbound_quantity` · `outbound_price` · `outbound_side`(문자열화) · `reference_digest`
- `outbound_request_digest`: 위 outbound 5종 + attempt_id + instrument_key 를 scheme 으로 digest — «exact outbound bytes» 의 커널 측 정의(합성 transport 의 바이트 = `OutboundSendRequest` 의 canonical 형).
- `seal_digest`: covered 전체의 canonical digest(scheme 주입).
- 결합 validator: `outbound_coordinates` 의 각 (name, value) 가 같은 이름의 봉인 필드와 일치(예: `("endpoint", endpoint)`) · `claim_principal == active_principal` 는 **기존 픽스처(`happy_context`·슬라이스 e2e)에서 이미 같을 때만** 강제 — 다르면 강제하지 말고 둘을 기록만 하고 **보고**(두 principal 의 모델상 관계는 운영자 결정 항목).

`build_send_seal(context, attempt, *, scheme) -> SendSeal` — 생성 실패(필수 None·검증 실패)는 예외 `SendSealUnconstructable(reason)`.

술어 `seal_matches_outbound(seal, *, coordinates, quantity, price, side, instrument_key, attempt_id) -> bool` — transport 에 실제로 건네질 인자와 봉인의 동일성(호출 직전 재검·테스트용).

### 1.2 게이트웨이 순서 변경 (`gateway.py::__call__`)

새 순서: step 15 verify → `outbound_binding_mismatch` → **step 15½ 봉인**(`build_send_seal`; 실패 ⇒ `_halt(SEND_SEAL_UNCONSTRUCTABLE)` — 클레임 전이라 아무것도 소비되지 않음 · 기존 `OUTBOUND_COORDINATE_DERIVATION_RAISED` 는 이 자리로 흡수, 멤버는 유지하되 도달 불가임을 도크스트링에 명시) → step 16 claim(인자는 **봉인에서**: `seal.claim_principal`·`seal.request_bytes_digest`·두 nonce) → `SEND_SEALED` 증거(`GatewayEvidenceRecord` 에 `send_seal: SendSeal | None` 필드 · 전체 봉인 탑재) → `SEND_STARTED` 증거(`send_seal_digest` 필드) → step 17 → step 18 `send_once(**seal 에서만 파생한 인자, seal_digest=seal.seal_digest)` → step 19: 결과 기록에 `send_seal_digest` 병기.

`SendHaltReason` 신설: `SEND_SEAL_UNCONSTRUCTABLE`. 게이트웨이 생성자에 `scheme: CanonicalizationScheme | None = None`(None ⇒ `get_scheme(EV_L1_PROVISIONAL_VERSION)` — 이는 커널의 기존 관례(`compose/context.py` 도 동일)이며 폴백이 아니라 버전 핀).

### 1.3 transport 서명 — `seal_digest` 키워드

`SendTransport.send_once`/`Transport.send_once`/`SyntheticPaperTransport.send_once` 에 keyword-only `seal_digest: str | None = None` 추가(기본 None 은 서명 호환용 · 게이트웨이는 항상 전달). `OutboundSendRequest.seal_digest: str | None` 로 보존. 드리프트 canary 는 자동 통과(두 선언 동시 변경) · «credential/session/retry 파라미터 부재» 핀은 유지(seal_digest 는 자격증명이 아니다 — 핀 테스트의 금지 목록에 없음을 확인).

### 1.4 테스트 (TDD · RED 선행)

- 봉인 생성: 필수 필드 각각 None ⇒ `SendSealUnconstructable`(파라미터화) · 좌표-필드 불일치 ⇒ 거부 · `seal_digest`/`outbound_request_digest` 결정성(같은 입력 두 번 = 같은 digest · 한 필드 변경 = 다른 digest).
- 순서: 증거 kinds 가 `[VERIFY_ITEM×17, SEND_SEALED, SEND_STARTED, POTENTIALLY_LIVE_OBSERVED, …]` · 봉인 실패 시 `SEND_REFUSED(SEND_SEAL_UNCONSTRUCTABLE)` 이고 **claims 0·SEND_STARTED 0**(기존 순서 테스트 `test_egressgw_gateway.py:141,157` 확장).
- 유일 원천: transport 가 받은 `OutboundSendRequest` 의 각 인자 == 봉인 필드 · `seal_digest` 전달 · `seal_matches_outbound` True. 뮤테이션 M-K1: step 18 에서 봉인 대신 context 를 다시 읽도록 바꾸고 context 에만 다른 값을 심으면 red.
- 뮤테이션 M-K2: 봉인 후 `SEND_STARTED` 전에 context 값을 바꿔도 transport 인자는 봉인값(불변성).
- 기존 전체 `tos/tests` green · 크기 register 재등재(gateway.py 는 새 모듈로 성장 최소화).

## 2. 레인 R — 런타임 (`tos/runtime/` · 레인 K 와 병렬 착수 가능한 부분 먼저)

### 2.1 (K 무관 · 즉시) authorized 좌표·capsule digest 의 설정 이관

`_wiring.py:824-833` 리터럴을 신규 로더 `tos_runtime/compose/_egress_coordinates.py` + `tos/runtime/config/egress_coordinates.example.yaml` 로 이관(`_egress_attestations.py` 와 동일 패턴: 예시는 named-TBD `null` · null 은 부팅 거부 · 테스트 픽스처가 값 공급). 키: `action`·`method`·`route_identity`·`credential_generation`·`broker_session_generation`·`egress_generation`·`active_principal`(환경 라벨 결합은 로더가 `{environment_label}` 치환으로만) . `capsule_egress_request_digest` 는 «capsule 체인 terminus» 의 스탠드인임을 로더 도크스트링에 명시하고 digest 입력 집합(현재 account+instrument)을 설정 키 `capsule_terminus_fields` 로 이관 — 값 자체는 계속 파생(리터럴 아님). `OPERATOR_ATTESTED_INPUTS` 증적에 좌표 7종 추가.

### 2.2 (K 착지 후) e2e

compose e2e 에서: `SEND_SEALED` 가 `SEND_STARTED` 앞에 durable 로 기록 · `SEND_STARTED.send_seal_digest == SEND_SEALED.send_seal.seal_digest == transport.requests[-1].seal_digest` · `EGRESS_RESULT` 증거에 봉인 digest 병기 · 뮤테이션 M-R1: `_wiring.py` 의 좌표 로더를 리터럴로 되돌리면 부팅 거부 테스트 red.

## 3. 기각 대안

- **봉인을 증거로만 기록하고 transport 인자는 종전대로 context 에서 파생**: «기록은 예방이 아니다»(EGRESS-INV-015 류) — 봉인이 유일 입력 원천이어야 substitution 이 구조적으로 불가.
- **transport 서명 불변 + 사후 echo 비교만**: 사후 검출은 send 를 막지 못함. `seal_digest` 키워드는 자격증명·세션·재시도 파라미터가 아니므로 기존 핀과 충돌 없음.
- **바이트 재구성(§10 route confinement 포함)까지 이 슬라이스에서**: EGRESS-EV-003 +Security 소관 · 합성 transport 에서 바이트는 합성 — 과대 주장 금지.
- **좌표 리터럴 유지**: 비협상 규칙 위반이 봉인으로 하중을 받게 됨.

## 4. 종료 조건

- `tos/tests`·`tos/runtime/tests` green(독립 실측 rc + «N passed») · mypy/ruff/black/firewall/lint-imports/budget/completion/spec/contract 통과 · 커널 diff 는 레인 K 커밋에만.
- 뮤테이션 M-K1·M-K2·M-R1 red · 봉인 실패 경로에서 claims 0·SEND_STARTED 0.
- `_wiring.py` 에 egress 좌표 리터럴 0(grep) · EV 상태 변경 0 · 독립 리뷰 approve.

## 5. 가정

- **A1** 합성 transport 의 «exact outbound bytes» = `OutboundSendRequest` canonical 형의 digest. 실 브로커 어댑터(Phase 4 작업 2·Phase 5)는 wire 직전 바이트 digest 를 같은 필드에 넣어야 하며, 그 검증은 EGRESS-EV-003 소관.
- **A2** `claim_principal` 과 `active_principal` 의 동일성은 기존 픽스처 실측에 따른다(레인 K 보고).

## 6. 실행 결과·독립 리뷰 처분

### 6.1 착지 (2026-09-08/09 · 브랜치 `feat/tos-phase4-send-seal` · 7커밋 `e19c6529..564d73da`)

| 레인 | 커밋 | 내용 |
|---|---|---|
| R §2.1 | `e19c6529` | `_egress_coordinates.py` + `egress_coordinates.example.yaml`(7좌표 + `capsule_terminus_fields` · named-TBD null · `{environment_label}` 치환만) · `_wiring.py` 리터럴 0 · `OPERATOR_ATTESTED_INPUTS` +8 · M-R1 catcher(결선된 좌표 == 로더 출력) · `root.py` 2줄 pass-through(보고된 범위 밖 편집) · `capsule_terminus_fields` 검증 대상은 `ConstructionConfig`(계획의 `CandidateConstruction` 표기 정정) |
| K §1.1 | `08008039` | `egressgw/seal.py` `SendSeal`(필수 필드 전부 · 좌표-필드 일치 validator · **`claim_principal == active_principal` 강제** — A2 실측: 픽스처 전부 동일 · 기존 17항목 어디도 이 둘을 비교하지 않았음 → 봉인이 처음 잡음) · `build_send_seal` · `SendSealUnconstructable` · `seal_matches_outbound` · 임포트 폐쇄: `tos.canonical` 은 egressgw allowlist 안(`_base` 경유) · `records↔seal` 순환은 `TYPE_CHECKING` |
| K §1.2 | `a0674dba` `c8b0da7c` | `GatewayEvidenceRecord.send_seal/send_seal_digest` · `SEND_SEAL_UNCONSTRUCTABLE` · `__call__` 재배선(`_seal_and_claim` 헬퍼 · verify → **seal** → claim(봉인 값) → `SEND_SEALED` → `SEND_STARTED` → step 18 봉인 유일 원천) · M-K1 AST 핀(step 18 `send_once` 에 `context.` 읽기 0) · M-K2 리졸버 2회 호출 적발 |
| K §1.3 | `d90f37ec` | `SendTransport`/`Transport`/`SyntheticPaperTransport.send_once(seal_digest=)` · `OutboundSendRequest.seal_digest` · 드리프트 canary 통과 |
| R §2.2 | `48a3919b` | compose e2e 4건: durable `SEND_SEALED` < `SEND_STARTED`(seq) · digest 삼중 일치 · `EGRESS_RESULT_RECORDED` 에 digest · sqlite 재판독으로 `send_seal` 26필드 전부 보존(`model_dump(mode="json")` 재귀 · 어댑터 수정 불요) |
| K 후속 | `564d73da` | 오케스트레이터 결정 2건: 정확 집합 핀에 `seal_digest` 편입(금지 이름 단언 불변) · 봉인에 `reference: OrderingEvent` 탑재 → step 18 `context.reference` 읽기 제거 · M-K1 핀을 «어떤 `context.` 도 금지» 로 일반화 |

**커밋 순서 편차**: K 는 계획 항목 4(transport 서명)를 항목 3(게이트웨이 재배선) 앞에 커밋 — 각 커밋 트리를 green 으로 유지하기 위함(보고·수용).

**보고 갭 G-3(이 슬라이스 밖 · 리뷰 판정 요청)**: `compose/context.py:378-391` QCC 스탠드인(슬라이스 #3 item 3 provisional)이 `egress_generation=1`·`writer_epoch=1`·`committed_revision=1` 등 리터럴을 유지 — 봉인이 config 의 `egress_generation` 을 싣게 되어 QCC 의 값과 드리프트할 수 있다(현재 픽스처는 둘 다 1). 처분 후보: 최소 `egress_generation` 을 좌표 설정에서 읽기 · 나머지 QCC 세대 리터럴은 Phase 5 실 QCC 로 대체.

**독립 실측(최종 트리 `564d73da` · 재설치 venv)**: runtime **492 passed** rc=0 · kernel **9134 passed** rc=0 · mypy 254/54 clean · ruff 0 · black 930 unchanged · firewall PASS · lint-imports 3 KEPT · budget 0 위반(31 등재 · gateway.py 1850→1921 · `_wiring.py` 1045→1073) · completion GREEN · spec PASS · contract PASS · tos-spec/계약 문서 무편집 · `_wiring.py` egress 좌표 리터럴 grep 0(잔여 hit 는 `_egress_coordinates.py` 도크스트링의 이관 전 값 인용 + 위 G-3).

### 6.2 독립 리뷰 처분

(리뷰 후 기입)
