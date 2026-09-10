# TOS KIS MOCK transport 운영 런북 (레인 T1)

- **상위 계획**: `docs/plans/2026-09-10-tos-kis-mock-transport-plan.md`
- **레인**: T1 어댑터(`tos_runtime.transport.kis_mock`) — T2(Coordinator admission·compose 결선)와
  T3(e2e 정직성)는 별도 레인 소관, 이 런북은 T1 산출물만 다룬다.
- **권한 부여 0 · 실주문 0 · 라이브 권한 0**: 이 문서와 그 산출물은 아무것도 승인하지 않는다.

## 1. T1이 착지한 것 / 아닌 것

| 착지 | 착지 아님 |
|---|---|
| `tos_runtime/transport/kis_mock/{config,client,adapter}.py` — 설정 로더·stdlib HTTP 클라이언트·`Transport` 어댑터 | Coordinator `nonlive_broker_consuming` admission (T2) |
| 예시 설정 `kis_mock_transport.example.yaml`(전항목 named-TBD null) | compose 결선(`_wiring.py`/`root.py`/`cli.py`) |
| custody manifest 예시에 `kis_mock.*` 3스코프 행 추가 | `FileCustody.PROVISIONED_SCOPES` 확장(현재 3스코프 고정 — 아래 §4 참조) |
| 헤르메틱 가짜 KIS 서버 기반 단위 테스트(config/client/adapter, 90건) | 실 게이트웨이 통합 e2e(T3) |

**오늘 이 어댑터를 어딘가에 연결해도 송신은 나가지 않는다** — 계획 §0 "핵심 귀결"이 이미 지목한
3중 차단(Coordinator ② · 게이트웨이 deferred 6 UNKNOWN · INSTANCE PROHIBITED) 앞에 이 어댑터는
아예 도달하지 못한다. 이 레인의 존재 이유는 "오늘 주문 1건"이 아니라 "Phase 5·P0-2가 닫히는
날, 코드 변경 0으로 첫 MOCK 주문이 나갈 준비"다.

## 2. 값 제안표 (운영자 승인 대기 — 계획 §6 확인 지점 2)

아래 값은 전부 **제안**이다. `kis_mock_transport.example.yaml`은 이 표의 값을 채우지 않은
named-TBD `null` 상태로 유지된다 — 로더가 부팅을 거부하는 것이 의도된 동작이다.

| 필드 | 제안 값 | 근거 |
|---|---|---|
| `order_path` | `/uapi/domestic-stock/v1/trading/order-cash` | 공식 SDK `open-trading-api/examples_llm/domestic_stock/order_cash/order_cash.py:22`(`API_URL`) · N-17 메모 표1행("주식 `order_cash` `/uapi/domestic-stock/v1/trading/order-cash`") |
| `token_path` | `/oauth2/tokenP` | 공식 SDK `open-trading-api/examples_llm/auth/auth_token/auth_token.py:28`(`API_URL`) |
| `tr_id_buy` (모의) | `VTTC0012U` | `order_cash.py:110-116`(`env_dv=="demo"` 분기: `ord_dv=="buy"` → `VTTC0012U`) · N-17 메모 §69-102("주식 주문 TR이 `TTTC0011U`(매도)/`TTTC0012U`(매수)/`TTTC0013U`(정정취소) 및 모의 `VTTC0011U`/`VTTC0012U`/`VTTC0013U`로 확인됨") |
| `tr_id_sell` (모의) | `VTTC0011U` | `order_cash.py:110-116`(`ord_dv=="sell"` → `VTTC0011U`) · 위와 동일 N-17 인용 |
| `field_map.account` → `CANO` | 종합계좌번호 | `order_cash.py:121`(`"CANO": cano`) · N-17 메모 표1행 body 9필드 나열 |
| `field_map.instrument` → `PDNO` | 상품번호(종목코드) | `order_cash.py:123`(`"PDNO": pdno`) |
| `field_map.quantity` → `ORD_QTY` | 주문수량(문자열) | `order_cash.py:125`(`"ORD_QTY": ord_qty`) · docstring "ORD_QTY(주문수량), ORD_UNPR(주문단가) 등을 String으로 전달해야 함에 유의" |
| `field_map.price` → `ORD_UNPR` | 주문단가(문자열) | `order_cash.py:126`(`"ORD_UNPR": ord_unpr`) |
| `min_send_interval_ms` | **1100**(권고 기본값) | P-13 실측(clean 상한 1.0 rps · 스로틀 2.0 rps · `EGW00201`) — `docs/plans/2026-08-06-tos-phase0-p01-residual-17key-disposition-draft.md:141`, `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:1890-1926`. clean 1.0 rps ⇒ 최소 간격 1000ms; 여유 100ms를 더해 1100ms 제안 |
| `token_reissue_min_interval_s` | **서버 캠페인 실측 대기** | N-15가 이 값을 직접 주지 않는다 — 실측 4회가 **전패**(`docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:2119,2162`: "N-15 4회 전패 기록") 했고 `token_blackout_window_ms: null`이 그 결과로 남아있다(같은 파일 :2128, "⚠ null 유지"). 안전한 임시값(예: 60s)을 쓸지, 작업 4 모의 운영 서버 재실측을 먼저 할지는 운영자 판단 — 이 런북은 값을 대입하지 않는다 |

### 2.1 known T1 gap — `order_cash` 9필드 중 5필드 미해결

KIS `order_cash` body는 9필드다(N-17 메모): `CANO`·`ACNT_PRDT_CD`·`PDNO`·`ORD_DVSN`·`ORD_QTY`·
`ORD_UNPR`·`EXCG_ID_DVSN_CD`·`SLL_TYPE`·`CNDT_PRIC`. `field_map`의 닫힌 동적 소스 집합
(`account`/`instrument`/`quantity`/`price`)은 이 중 **4개**(`CANO`/`PDNO`/`ORD_QTY`/`ORD_UNPR`)
만 채울 수 있다 — 나머지 5개는 attempt 단위 커널 소스가 아예 없다(계정상품코드 분할·주문구분
코드·거래소구분코드·매도유형·조건가격은 모두 "attempt마다 달라지는 값"이 아니라 "배포마다
고정된 상수"다). 이 5개를 가짜로 채우기보다("증거 없는 값 삽입") 다음 두 경로 중 하나를 후속
슬라이스에 제안한다:

1. `KisMockTransportConfig`에 `static_body_fields: Mapping[str, str]`(KIS wire 필드명 →
   배포별 상수)를 추가해 T1의 `field_map`과 나란히 로드 — 가장 단순하지만 스키마 확장.
2. 이 5필드를 담을 새 커널측 좌표(예: `outbound_coordinates`의 확장)를 Phase 5 캡슐체인
   설계에 포함 — `tos_runtime.compose._egress_coordinates`의 "STAND-IN, not the real thing"
   교훈과 같은 계열의 결정.

운영자 확인 지점 2는 TR ID·경로·필드값뿐 아니라 이 스키마 확장 여부도 포함한다고 제안한다.

## 3. custody 파일 준비 절차

`kis_mock.app_key`/`kis_mock.app_secret`/`kis_mock.account` 세 스코프가
`tos_runtime.custody.file_custody.FileCustody`로 로드되려면 **두 가지가 선행**되어야 한다
(순서 중요):

1. **`FileCustody.PROVISIONED_SCOPES` 확장** (`tos/runtime/src/tos_runtime/custody/
   file_custody.py`) — 현재 `frozenset({"read.principal", "evidence.key", "replay.params"})`
   고정. 이 세 스코프를 추가하는 것은 T1(전송 어댑터 패키지)의 소관이 아니라 T2(compose 결선)
   또는 별도 custody 확장 레인의 소관이다 — T1은 `CredentialCustody` Protocol에만 의존하고
   구체 구현을 건드리지 않는다(운영자 승인 없이 공유 Phase 2 모듈을 수정하지 않기 위함).
2. **파일 준비** (스코프 확장 이후):
   ```bash
   install -m 0600 /dev/null <custody_root>/kis_mock.app_key
   install -m 0600 /dev/null <custody_root>/kis_mock.app_secret
   install -m 0600 /dev/null <custody_root>/kis_mock.account
   # 각 파일에 실제 값을 기입(개행 없이) 후:
   sha256sum <custody_root>/kis_mock.app_key      # -> custody.manifest.yaml 의 expected_sha256
   sha256sum <custody_root>/kis_mock.app_secret
   sha256sum <custody_root>/kis_mock.account
   ```
   `custody.manifest.yaml`(예시 아님, 실 배포판)에 위 3스코프 행을 `tos/runtime/config/
   custody.manifest.example.yaml`과 동일한 `file`/`principal` 값으로, `expected_sha256`은
   방금 계산한 값으로 채운다. `kis_mock.account`의 `principal`은 스코프 표
   `MOCK_STOCK_ORDER.principal`(`broker_scopes.example.yaml`)과 **문자열 동일**해야 한다.

## 4. dry_run 부팅 절차 (자리표시자 — CLI 플래그는 T2 소관)

T1은 CLI 결선을 포함하지 않는다. T2가 `--transport kis-mock` 플래그를 추가하면, 예상 절차는:

```bash
# (T2 완료 후 예상 커맨드 — 아직 존재하지 않음)
sts-runtime compose --transport kis-mock \
  --kis-mock-config <path>/kis_mock_transport.yaml \
  --custody-root <custody_root>
```

`kis_mock_transport.yaml`의 `mode: dry_run`을 유지한 채 부팅 → evidence 저장소에서
`TRANSPORT_DRY_RUN` 레코드 존재를 확인하는 것이 이 계획의 **운영자 종료 조건**이다(계획 §5).
`live` 전환은 Phase 5·P0-2가 닫힌 뒤, 이 런북의 개정판에서 별도로 다룬다.

## 5. 참고

- 공식 SDK 오라클(비채택 · read-only): `open-trading-api/examples_llm/domestic_stock/
  order_cash/order_cash.py`, `open-trading-api/examples_llm/auth/auth_token/auth_token.py`,
  `open-trading-api/examples_llm/kis_auth.py`(헤더 규약: `authorization`/`appkey`/`appsecret`/
  `tr_id`/`custtype`).
- N-17 수집 메모: `docs/plans/2026-07-29-tos-p02-n17-spec-collation.md`.
- P-13/N-15 실측: `docs/plans/2026-08-06-tos-phase0-p01-residual-17key-disposition-draft.md`,
  `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`.
- INSTANCE MOCK_VTS/REAL_PROD rest_base: 같은 파일 각각 `_kis.endpoints.rest_base`
  (MOCK ~line 384, REAL ~line 3579).
