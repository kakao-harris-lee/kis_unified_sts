# TOS KIS MOCK transport 계획 — 주식 모의 주문 어댑터(`tos_runtime`) · Phase 4 후속 슬라이스

- **상위**: 개발계획 `docs/plans/2026-08-11-tos-completion-development-plan.md` §5.2 3행(«MOCK 주식 주문 검증 — profile/evidence 충족 시 허용») · §6 Phase 4 종료 조건 5(운영자 처분 2026-09-10: Phase 5 착지 후 재판정) · Phase 7 최종 시나리오 «synthetic or allowed MOCK transport» · 설계 #34 §5(합성 transport · «실 transport 는 firewall 때문에 `tos/` 밖에 산다») · Phase 4 잔여 계획 §9.5 처분 ①(c).
- **선행**: PR #663(main `1362fa60`) — 스코프 표(`tos_runtime.brokercap.scopes`) · INSTANCE 로더 · item 6/12 파생 · SendSeal · G-4.
- **저작**: 세션 모델 단독 · **권한 부여 0 · 실주문 0 · 라이브 권한 0 · 선물 실계좌 무관(주식 MOCK 만)**.

## 0. 서베이 실측 (2026-09-10 · `1362fa60`)

| 항목 | 실측 |
|---|---|
| transport 포트 | 커널 `tos.brokeradapter.Transport` = `tos.egressgw.gateway.SendTransport`(구조 동형 · 시임 canary): `send_once(attempt, *, instrument_key, coordinates, quantity, price, side, reference, seal_digest) -> EgressResultPayload` — **단발 by construction**(재시도·idempotency key·resend 파라미터 표현 불가 · 금지 파라미터 핀 테스트 존재). 결과 어휘 `EgressResultKind{ACK, FULL_FILL, PARTIAL_FILL, REJECT, UNKNOWN, TIMEOUT}`(+Phase 3 `CANCEL_ACK`·`EXPIRED`) · `broker_execution_id` |
| 합성 transport | `tos/src/tos/brokeradapter/synthetic.py` — 네트워크 0·credential 0·route 0 · 결정론 fill · «실 paper API 호출은 broker-resource-consuming 이라 §10.8:741 전항목 트리거 → 미착지 메시로 §10.8:761 거부, 그것을 게이트웨이가 강제» |
| 게이트웨이 | `resolve_broker_applicability`: `TransportNature.reaches_broker=True` ⇒ `BROKER_RESOURCE_CONSUMING` ⇒ deferred 4·5·7·8·9·10 **UNKNOWN → deny**(Phase 5 owner 부재) · item 6 `capability_admissible(INSTANCE, required, version_current)` — INSTANCE VERIFIED 0·DRAFT ⇒ PROHIBITED |
| Coordinator 게이트 | `tos_runtime/compose/_preconditions.py::live_scope_authorized` = ① 커널 `is_live(None,…)`=False ∧ ② `transport_nature.reaches_broker is False`. 지원 posture 는 `NOT_AUTHORIZED` 뿐. **②가 broker-reaching 을 live 여부와 무관하게 정지**(`LIVE_SCOPE_NOT_AUTHORIZED` · Phase 4 잔여 계획 §9.1 ③ 발견) |
| 스코프 | `MOCK_STOCK_ORDER` = `BROKER_SIMULATION`×{ORDER_SEND, CANCEL_REPLACE}×`BROKER_RESOURCE_ONLY`×STOCK×`MOCK_ORDER` · `profile_evidence_ok: null` ⇒ PROHIBITED(P0-2 증거 0) · `true` ⇒ REDUCED · `instance: MOCK_VTS` · `required_capability_set` 4차원 LEVEL_2 · principal_class ORDER · endpoint_class BROKER_ORDER · `transport_nature(scope)` ⇒ reaches_broker/credential_bearing/route_bearing True · risk_relevant_live False |
| 런타임 규율 | 서드파티 의존 0(`tos/runtime/pyproject.toml` — tos 만) · `os.environ` 0(D1.1 · CLI 경로만) · 헤르메틱 테스트는 `127.0.0.1`/`::1` 소켓만 허용(`localhost` 금지) · credential 은 `tos_runtime.custody.FileCustody`(manifest `scopes.<name>.{file, principal, expected_sha256}` · `CredentialHandle` bytearray 0화 · repr 비노출) |
| firewall | `tos_runtime` → `shared.*` 전면 금지(`.importlinter` v1.2) · `shared.kis`/`shared.execution` 재사용 불가(그 코드는 blind retry 3회·토큰 만료 resend 를 갖는 결함 표면 — 설계 #34 §5.4) |
| KIS MOCK 사실(INSTANCE MOCK_VTS 문서) | rest_base `https://openapivts.koreainvestment.com:29443` · 주식 `order_cash` body 9필드(CANO·ACNT_PRDT_CD·PDNO·ORD_DVSN·ORD_QTY·ORD_UNPR·EXCG_ID_DVSN_CD·SLL_TYPE·CNDT_PRIC) · 응답 broker 부여 `ODNO`·`KRX_FWDG_ORD_ORGNO`·`ORD_TMD` · 주문 TR 은 `V` 접두(모의) · 정정취소 `VTTC0013U` · rate: clean 1.0 rps / 스로틀 2.0 rps(P-13 · `EGW00201`) · 토큰 재발급 쿨다운(N-15 · 4회 전패 기록) · 모의 지정가 미체결 관측(P-11 · 시장가로만 체결) |
| 공식 명세 | `open-trading-api/`(gitignored · 비채택 오라클 · SCI admission 전 의존 금지) — TR ID·경로·필드 대조용 |

**핵심 귀결**: 어댑터를 착지해도 **송신은 3중으로 막힌다** — (a) Coordinator ② · (b) 게이트웨이 deferred 6 UNKNOWN(Phase 5) · (c) item 6 INSTANCE PROHIBITED(P0-2 승인 + required 4차원 VERIFIED 전). 이 계획은 (a) 를 **정직한 별도 admission** 으로 풀고, (b)(c) 는 풀지 않는다. 즉 이 계획의 산출물은 «실 MOCK 주문 1건» 이 아니라 «Phase 5·P0-2 가 닫히는 순간 코드 변경 없이 첫 MOCK 주문이 나가는 어댑터 + 그 전까지의 정직 deny 증거».

## 1. 범위

| 포함 | 제외 (이유) |
|---|---|
| `tos_runtime/transport/kis_mock/` 어댑터(요청 구성·서명·단발 전송·응답 사상) · 설정 `kis_mock_transport.yaml` · custody 스코프(appkey/appsecret/account) · Coordinator **MOCK admission** posture · compose 결선(`--transport kis-mock`) · 헤르메틱 가짜 KIS 서버 e2e · 정직 deny 증거 테스트 · 운영자 레인(모의 운영 서버 dry-run→live) | 선물 MOCK(KIS MOCK 선물 미제공 · §0 결정 3) · REAL 어떤 것도(REAL_READ 어댑터는 별도 · REAL_ORDER 영구 차단) · deferred 4·5·7~10 owner(Phase 5) · INSTANCE VERIFIED 승격(작업 4 운영자) · WebSocket 체결통보(Phase 5 posttrade finality 의 broker witness — 후속) · 정정/취소 어댑터(CANCEL_REPLACE 는 tuple 만 등재 · 후속 슬라이스) |

## 2. 결정

1. **위치·의존**: `tos/runtime/src/tos_runtime/transport/kis_mock/`(신설 · 커널 밖 · firewall 규칙 (g) 준수). HTTP 는 **stdlib `http.client` + `ssl.create_default_context()`** — 서드파티 0 유지(D1.3). 자작 파서 0(JSON 은 `json`). 모듈 ≤1000행 · 함수 ≤100행.
2. **단발성은 포트가 보장, 어댑터는 이를 재확인**: `send_once` 1회 = HTTP POST 1회. 예외·타임아웃·5xx·연결 리셋 ⇒ **`UNKNOWN`**(거부 아님 — 브로커가 받았을 수 있다) · 소켓 타임아웃 ⇒ `TIMEOUT` · `rt_cd != "0"` ⇒ `REJECT`(`msg_cd` 를 evidence 에) · `rt_cd == "0"` ∧ `ODNO` 존재 ⇒ `ACK`(`broker_execution_id=ODNO`). **체결(FULL/PARTIAL)은 어댑터가 주장하지 않는다** — 체결 사실은 Phase 5 finality witness(조회/통보) 소관. 재시도 루프·`sleep` 재전송·`for _ in range` 는 negative-grep(기존 `brokeradapter` 테스트 규율을 런타임 패키지에 확장).
3. **요청 바이트는 SendSeal 이 유일 원천**: 본문 9필드는 `SendSeal.outbound_coordinates`/`quantity`/`price`/`side` 와 설정 매핑(`field_map`: 커널 좌표 → KIS 필드명)에서만 구성 · `seal_digest` 를 요청 헤더 커스텀 필드가 아니라 **evidence 에 echo**(브로커로는 보내지 않음 — 봉인 digest 는 외부 표면이 아니다) · 본문 직렬화 후 `request_bytes_digest` 를 `SendSeal.request_bytes_digest` 와 **전송 직전 대조**, 불일치 ⇒ 전송 0 + `UNKNOWN` 아닌 **`SEND_REFUSED`** 경로(게이트웨이 `outbound_binding_mismatch` 와 같은 결과) — 실 바이트 재구성이 처음 하중을 받는 지점(EGRESS-EV-003 +Security 는 여전히 별개).
4. **credential**: custody manifest 스코프 `kis_mock.app_key`·`kis_mock.app_secret`·`kis_mock.account` — principal 은 스코프 표의 `MOCK_STOCK_ORDER.principal` 과 **동일해야** 로드(불일치 = 부팅 거부 · 하나의 principal 이 credential 과 route 를 동시에 가리키는 구조). 토큰(`/oauth2/tokenP`)은 어댑터가 발급·메모리 보관·만료 시 **재발급하지 않고 UNKNOWN**(다음 attempt 가 새 토큰 — 재시도는 새 attempt 라는 §5.4 원칙 그대로) · 재발급 쿨다운은 설정 `token_reissue_min_interval_s`(N-15 실측값 기입 전 null=부팅 거부).
5. **host 봉인(설정으로도 실전 불가)**: `kis_mock_transport.yaml::endpoint.rest_base` 는 INSTANCE **MOCK_VTS 문서** `_kis.endpoints.rest_base` 와 문자열 동일해야 로드(one source of truth) · REAL_PROD 문서의 rest_base 와 같으면 부팅 거부 · 주문 TR ID 는 설정값이되 로더가 `V` 접두를 강제(런북 §2.3 규칙 2 의 런타임판) · `T`/`STTN`/`CTF` 접두 거부. 어떤 `.py` 에도 호스트·TR 리터럴 0(negative-grep).
6. **페이싱**: 단일 전송 지점 앞에서 `min_send_interval_ms`(설정 · P-13 clean 상한 1.0 rps ⇒ 예시 1100) 를 런타임 `time` 서비스의 단조 클록으로 강제 · 대기는 전송 **직전** 종료(t0 오염 0 · 런북 §5.3.1) · 스로틀 응답(`EGW00201`)은 `REJECT` 로 사상하되 evidence `reason=throttled` — 재시도 없음.
7. **Coordinator MOCK admission(결정 핵심)**: `live_scope_authorized` ②는 **그대로**(live 질문에 대한 구조 보장). 별도 precondition `broker_consuming_nonlive_admitted(transport_nature, active_scope, instance)` 를 **AND 가 아니라 OR 가 아닌 «대체 경로»로 두지 않고**, Coordinator 가 «live-scope 질문» 과 «non-live broker-consuming 질문» 을 **둘 다** 묻게 한다: 후자는 ① 커널 `is_live`=False(불변) ② `active_scope.admissibility ∈ {ADMISSIBLE, REDUCED}`(REDUCED = `profile_evidence_ok: true` 가 P0-2 증거로 뒷받침될 때만 — 설정 `true` 자체가 증거 결속 attestation) ③ tuple 전부 `authorization_class ∈ {MOCK_ORDER, NON_AUTHORIZING_READ}` ∧ `environment is BROKER_SIMULATION` ④ `transport_nature.risk_relevant_live is False` ⑤ INSTANCE 문서 environment 가 스코프 binding 과 일치. 하나라도 비양성 ⇒ 기존 `LIVE_SCOPE_NOT_AUTHORIZED` 정지 유지. posture 값은 `coordinator_preconditions.yaml::nonlive_broker_consuming: {admitted: bool|null}`(null=부팅 거부 · 예시 null). **REAL 은 어떤 값으로도 이 경로를 못 탄다**(③ 구조).
8. **결과 재주입**: 어댑터 결과는 기존 `EgressResultPayload` → 드라이버 `EGRESS_RESULT` 재주입 경로 그대로(Phase 3 슬라이스 A) · `UNKNOWN`/`TIMEOUT` 은 Phase 3 의 «결과 미도착 = 보수 결과» 규칙 그대로 · Phase 5 finality 가 닫을 때까지 예약 점유.
9. **dry-run 모드**: `mode: {dry_run, live}`(설정 · null 거부). dry_run = 토큰 발급 0·소켓 0 · 요청 바이트를 구성하고 digest 대조까지만 하고 evidence 에 `TRANSPORT_DRY_RUN` 기록 · 결과 `UNKNOWN`(전송 안 했으므로 «수락 아님»). 모의 운영 서버 첫 실행은 dry_run.

## 3. 기각 대안

- `shared/kis` 재사용/포팅 → firewall 금지 + 결함 표면(blind retry·토큰 resend) 재생산 금지(설계 #34 §5.4 · tos/CLAUDE.md «레거시는 참조 구현이 아니다»).
- `httpx`/`requests` 추가 → D1.3 «서드파티 0» · stdlib 로 충분(TLS 기본 컨텍스트).
- Coordinator ② 를 `risk_relevant_live` 기준으로 완화 → 구조 보장 약화 · 대신 별도 양성 admission(결정 7).
- 체결 여부를 주문 응답으로 판정 → KIS 주문 응답은 접수(ODNO)일 뿐 · 체결은 witness(Phase 5).
- 토큰 만료 시 어댑터 내부 재발급+재전송 → Q-IDEMP-2 재생산 · 포트가 금지.
- 환경변수 credential → D1.1 · custody 가 이미 있다.

## 4. 슬라이스 · 레인

| 슬라이스 | 내용 | 파일 소유 | 테스트 |
|---|---|---|---|
| **T1 어댑터** | `transport/kis_mock/{config,client,adapter}.py` · 설정 예시 · custody 스코프 3종 · 요청 구성/digest 대조/응답 사상/페이싱 | 신설 패키지만 | 헤르메틱 가짜 KIS 서버(`http.server` · 127.0.0.1 · TLS 없이 `scheme: http` 는 **테스트 전용 설정 플래그** — 예시/운영 설정은 https 강제 · 로더가 `http://` 를 `allow_plaintext_for_tests: true` 없이 거부) · 케이스: rt_cd 0+ODNO ⇒ ACK · rt_cd 비0 ⇒ REJECT · 5xx/리셋 ⇒ UNKNOWN · 소켓 타임아웃 ⇒ TIMEOUT · digest 불일치 ⇒ 전송 0 · 페이싱 t0 비오염 · 토큰 만료 ⇒ UNKNOWN(재발급 0) · negative-grep(재시도·environ·호스트·TR 리터럴·`localhost`) |
| **T2 결선** | Coordinator MOCK admission(`_preconditions.py`) · compose `--transport {synthetic,kis-mock}` · `TransportNature` 를 활성 스코프에서(이미) · `kis_mock_transport.yaml` 로드 · boot-integrity 에 설정 digest | `compose/_preconditions.py`·`_wiring.py`·`cli.py`·`root.py` | admission 5조건 각각 음성 ⇒ 정지 · REAL tuple 은 설정 어떤 값으로도 admitted 불가(전수 sweep) · `nonlive_broker_consuming: null` ⇒ 부팅 거부 |
| **T3 e2e 정직성** | 활성 `MOCK_STOCK_ORDER`(`profile_evidence_ok: true`) + kis-mock(dry_run) 으로 crossing 이벤트 1건: Coordinator **통과** → 게이트웨이 deferred UNKNOWN ⇒ deny · transport 호출 0 · evidence 에 6개 UNKNOWN 사유 · 그리고 `_deferred_item_verdict` 를 monkeypatch 로 SATISFIED 강제한 «Phase 5 가 닫혔다면» 반사실 실행에서 dry_run 요청 바이트가 SendSeal 과 일치하고 가짜 서버 live 모드에서 ACK→EGRESS_RESULT 재주입까지 1회 | 테스트만 | 위 두 경로 + 뮤테이션(어댑터에 재시도 1줄 추가 ⇒ negative-grep red · digest 대조 제거 ⇒ 불일치 테스트 red) |
| **T4 운영자 레인** | 모의 운영 서버: custody 파일 3종(0600 · manifest sha256) · dry_run 부팅 → evidence 확인 → (Phase 5·P0-2 이후) live 전환 | 런북 `docs/runbooks/tos-kis-mock-transport.md` | 실 서버 dry_run 산출 evidence 1건 = 이 계획의 운영자 종료 조건 |

독립 리뷰(Claude 측 `code-reviewer`)는 T1+T2 착지 후 1회, T3 후 재심.

## 5. 종료 조건

- 런타임·커널 스위트 green · ruff/black/mypy 0 · 크기 예산 · firewall · lint-imports · `tos_completion_status --check` GREEN(bound 문서 무접촉).
- 어댑터 negative-grep 전부 0 · 호스트/TR 리터럴 0 · `os.environ` 0 · 서드파티 의존 0.
- T3 정직성: 실 MOCK 송신 **0**(Phase 5·P0-2 전) 이 evidence 로 증명되고, 반사실 경로에서 바이트-봉인 일치·ACK 재주입 1회.
- 운영자 dry_run evidence 1건.
- EV 상태 변경 0 · 권한 부여 0 · 선물 어떤 경로도 0.

## 6. 운영자 확인 지점

1. 결정 7 admission 설계(둘 다 묻는 구조 · `nonlive_broker_consuming` posture 신설) — Phase 2 `_preconditions` 의 «지원 posture 는 NOT_AUTHORIZED 뿐» 문언 개정.
2. 주문 TR ID·경로·필드 매핑 값(공식 명세 대조 후 설정 기입 · P-1/N-17 산출물 인용).
3. `min_send_interval_ms`·`token_reissue_min_interval_s` 값(P-13·N-15 실측 — 작업 4 운영자 레인과 결속).
4. 착수 시점: Phase 5 W3(안전 메시 owner) 전에 T1~T3 를 먼저 착지할지(권고: **먼저** — 송신은 어차피 0 이고 Phase 5 가 닫히는 날 코드 변경 0 으로 첫 주문이 나가야 «구조 완결» 이 실증된다).

## 7. 운영자 처분 (2026-09-10)

| # | 처분 |
|---|---|
| 1 | **별도 non-live admission 신설** 승인 — 기존 게이트 ② 불변 · 5조건 전부 양성일 때만 · REAL 구조 불가 · posture 는 named-TBD null |
| 2·3 | TR ID·경로·필드 매핑 · `min_send_interval_ms` · 토큰 재발급 간격 = **개발 측이 근거(공식 명세+N-17/N-19 · P-13/N-15 실측) 붙여 제안표 작성 → 운영자 승인** · 승인 전 예시 YAML null 유지(부팅 거부) |
| 4 | **T1~T3 먼저 착지, Phase 5 W1 과 병행** — 브랜치 `feat/tos-kis-mock-transport-t1`(워크트리 `../kis_unified_sts-mock-transport`, main `296c0e5f` 기점) |

## 8. 실행 결과 — T1 착지 (2026-09-10 · PR #669 → main `fb16b102`)

- **착지**: `tos_runtime/transport/kis_mock/{config,client,codec,adapter}.py` · 예시 설정 · custody 스코프 2종(`kis_mock.app_key`/`app_secret` — account 는 seal 에서) · 런북 `docs/runbooks/tos-kis-mock-transport.md`(값 제안표 · 운영자 승인 대기 · 토큰 재발급 간격은 서버 실측 대기). 런타임 940 · brokeradapter canary 52 · 커널 diff 0 · 실주문 0.
- **독립 리뷰**: 1차 needs-attention(HIGH 2 · MEDIUM 3 · LOW 3) → 처분 `17c74f9a` → 재심 approve + M8 커버리지 핀 `d1fe6151`. 뮤테이션 M1~M8 전부 red.
- **설계 정정 (리뷰 HIGH 2건)**: ① 세션 seal 의 `request_bytes_digest` 는 오늘 `capsule_egress_request_digest`(캡슐 터미너스 stand-in)와 동일해야 하므로(커널 `exact_binding`) 어댑터의 KIS 본문 digest 와 **결코 일치할 수 없다** → **공유 wire codec `KisOrderWireCodec`**(9필드 정확 · sorted/compact JSON · sha256)을 어댑터의 유일 본문 원천으로 두고, **T2 가 compose context resolver 의 두 digest 를 이 codec digest 로 결속**해야 한다. 그 전까지 `mode: live` 는 로드 단계에서 무조건 거부(dry_run 전용). ② CANO 는 custody 가 아니라 `seal.account`(«seal 은 유일 원천»).
- **T2 must**(리뷰어 목록): codec 결속 · `build_client(config)` 만 사용(주입 client 는 테스트 시임) · `FileCustody.PROVISIONED_SCOPES` 에 `kis_mock.*` 확장 · Coordinator non-live admission(§7-1) · CLI `--transport kis-mock`.
- **T2 이월 사실**: `static_body_fields` 5필드 값·TR ID·간격값은 운영자 승인 제안표(런북 §2) — 승인 전 null=부팅 거부.
