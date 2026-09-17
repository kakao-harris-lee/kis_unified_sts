# TOS KIS MOCK transport 운영 런북 (레인 T1 → T2 lane C 갱신)

- **상위 계획**: `docs/plans/2026-09-10-tos-kis-mock-transport-plan.md`
- **레인**: T1 어댑터(`tos_runtime.transport.kis_mock`) 착지 + T2 lane C(compose 결선
  `--transport {synthetic,kis-mock}`, `tos_runtime.compose._transport_wiring`, custody
  `PROVISIONED_SCOPES` 확장) 착지. T2 lane A(codec digest 결속)·lane B(Coordinator non-live
  admission)는 각각 `tos_runtime.compose._request_digest`/`_nonlive_admission` — 이 런북은
  그 위에서 lane C 가 실제로 결선한 사실만 갱신한다. T3(e2e 정직성 나머지 절반)는 별도.
- **권한 부여 0 · 실주문 0 · 라이브 권한 0**: 이 문서와 그 산출물은 아무것도 승인하지 않는다.
- **독립 리뷰 처분 반영**(`dc6b47ba` 재심 · F1~F8, 8건 전부 해소): §2.1의 wire codec 분리,
  `mode: live` 부팅 거부, account 소싱 전환(§3), TR ID 형상 검증, `rt_cd` 부재 판정,
  자격증명 보관 정직화, 토큰 정체 evidence 확장 — 아래 각 절에서 상세.

## 1. 착지한 것 / 아직 아닌 것

| 착지 | 착지 아님 |
|---|---|
| `tos_runtime/transport/kis_mock/{config,client,codec,adapter}.py` — 설정 로더·stdlib HTTP 클라이언트·공유 wire codec·`Transport` 어댑터 (T1) | 실 게이트웨이 통합 e2e 전체(T3 나머지 절반 — "정직 deny" crossing 테스트는 착지) |
| 예시 설정 `kis_mock_transport.example.yaml`(전항목 named-TBD null, `static_body_fields` 포함) (T1) | `field_map`/`static_body_fields`/TR ID/`min_send_interval_ms`/`token_reissue_min_interval_s` 값 자체(§4 제안표 — 운영자 승인 대기, 예시 설정은 여전히 null) |
| custody manifest 예시에 `kis_mock.app_key`/`kis_mock.app_secret` 2스코프 행 (T1) | 실전 모의 서버의 실제 credential 값 채움(운영자 레인, §5) |
| 헤르메틱 가짜 KIS 서버 기반 단위 테스트(config/client/codec/adapter) (T1) | INSTANCE VERIFIED 승격 · Phase 5 deferred 항목 4/5/7/8/9/10 owner |
| `FileCustody.PROVISIONED_SCOPES` 에 `kis_mock.app_key`/`kis_mock.app_secret` 추가 + 원칙-일치 부팅 거부(`scope_principal`) (T2 lane C) | |
| `compose --transport {synthetic,kis-mock}` (`cli.py`/`root.py`/`tos_runtime.compose._transport_wiring`) — 스코프/transport 일관성 거부·custody principal 거부·호스트 봉인(INSTANCE MOCK_VTS/REAL_PROD `rest_base`) (T2 lane C) | |
| `SealRegistry`(gateway `SEND_SEALED` evidence → 어댑터 `SealLookup`, 단발성) + `KisWireCodecDigest` 를 `kis-mock` 부팅의 기본 컨텍스트 리졸버에 결속(T2 lane A 의 seam 을 실제로 배선) (T2 lane C) | |

**오늘 이 어댑터를 어딘가에 연결해도 송신은 나가지 않는다** — 두 겹으로 막힌다: (a) 계획 §0
"핵심 귀결"이 지목한 3중 차단(Coordinator ② · 게이트웨이 deferred 6 UNKNOWN · INSTANCE
PROHIBITED), (b) **독립 리뷰가 추가로 확인한 구조적 사실**(§2.1): 오늘의 컴포즈 컨텍스트
리졸버는 `request_bytes_digest`를 실제 KIS wire bytes 의 해시가 아니라
`capsule_egress_request_digest`(STAND-IN)와 **항상 동일하게** 설정하므로, 이 어댑터의 자체
digest 대조는 오늘 어떤 실 seal 에 대해서도 항상 불일치한다 — 그래서 `mode: live` 는 설정
로더에서 **무조건 거부**된다(§2.2). 이 레인의 존재 이유는 "오늘 주문 1건"이 아니라 "Phase
5·P0-2 및 T2 codec 결선이 닫히는 날, 코드 변경 0으로 첫 MOCK 주문이 나갈 준비"다.

## 2. 공유 wire codec (독립 리뷰 F1)

### 2.1 왜 어댑터 혼자만의 digest 대조로는 부족한가

`tos_runtime/compose/context.py:368`(`_egress_request_for_command`)는
`EgressRequestRecord.request_bytes_digest` 를 **문자 그대로**
`self.capsule_egress_request_digest` 로 설정한다. `tos/src/tos/egress/predicates.py:386-390`
의 `exact_binding_holds` 는 이 둘의 동일성을 게이트웨이 레벨 불변식으로 강제한다.
`capsule_egress_request_digest` 자체는 `tos_runtime.compose._egress_coordinates` 모듈
docstring 이 명시하는 **STAND-IN**(`account`/`instrument` 두 필드만 다이제스트한 값)이지,
실 KIS wire bytes 의 해시가 아니다. 즉 어댑터가 아무리 정확하게 KIS body 를 구성해도, 오늘의
실 seal 에 대해 `sha256(KIS body)` 는 `seal.request_bytes_digest` 와 **구조적으로 절대
일치할 수 없다**.

### 2.2 해법 — 공유 codec + `mode: live` 무조건 거부

`tos_runtime.transport.kis_mock.codec.KisOrderWireCodec` 하나를 신설해 어댑터가 **오직 이
codec** 을 통해서만 body 를 구성·다이제스트한다. T2(컴포즈 결선 레인)가 **같은 codec** 을
컨텍스트 리졸버의 `capsule_egress_request_digest` 계산에 결속하면, 그 순간부터
`request_bytes_digest == capsule_egress_request_digest == codec 자체 다이제스트`가 성립해
실 seal 로도 대조가 통과한다. 그 결속이 착지하기 전까지는 `tos_runtime.transport.kis_mock.
config.load_kis_mock_transport_config` 가 `mode: live` 를 **다른 모든 필드값과 무관하게**
거부한다 — `dry_run` 만 오늘 유효한 값이다.

### 2.3 codec 직렬화 레시피 (고정 — T2 결속 시 바이트 단위로 동일하게 재현)

1. KIS `order_cash` body 9필드(N-17 메모)를 두 개의 서로소 소스에서 채운다.
   - **동적 4필드**(`field_map`, 커널측 소스명 키): `account`(`SendSeal.account` — **봉인된
     outbound 좌표**, 독립 리뷰 F2 — `instrument_key.account`도 custody 값도 아님),
     `instrument`(`SendSeal.instrument_key.instrument`), `quantity`
     (`SendSeal.outbound_quantity`), `price`(`SendSeal.outbound_price`). 수치 두 개는
     `format(Decimal(value), "f")`로 지수표기 없는 평문 십진 문자열로 변환.
   - **정적 5필드**(`static_body_fields`, 배포별 상수, 그대로 복사): `ACNT_PRDT_CD`,
     `ORD_DVSN`, `EXCG_ID_DVSN_CD`, `SLL_TYPE`, `CNDT_PRIC`.
2. 두 소스의 합집합은 `KIS_ORDER_CASH_WIRE_FIELDS`(9개)와 **정확히** 일치해야 한다 — 부족하거나
   초과하면 바이트를 만들기 전에 `KisOrderWireCodecError`(어댑터에서는 그 이전에 이미 설정
   로더가 부팅 시점에 동일 검사로 거부).
3. `json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")`
   — 키 알파벳 정렬, 불필요한 공백 없음, UTF-8.
4. `digest(body_bytes) = hashlib.sha256(body_bytes).hexdigest()`.

## 3. account 소싱 전환 — custody 아닌 seal (독립 리뷰 F2)

이전 판(T1 1차 착지)은 KIS 계좌번호(CANO)를 custody 스코프 `kis_mock.account` 로 로드했다.
독립 리뷰는 이것이 "seal 이 유일한 입력 원천이어야 한다"는 계획 §2 결정 3 원칙을 깬다고
지적했다 — account 는 이미 `SendSeal.account`(게이트웨이가 승인한 outbound 좌표)로 봉인되어
있으므로, 어댑터가 그 값을 다시 custody 에서 "재확인"하는 것 자체가 두 번째, 독립적인 값
읽기다. **현재 판은 CANO 를 `SendSeal.account` 에서만 읽는다** — `kis_mock.account` custody
스코프는 완전히 제거되었고, custody 는 `kis_mock.app_key`/`kis_mock.app_secret` 2스코프만
쓴다. `custody.manifest.example.yaml` 도 이에 맞춰 2행으로 축소했다.

## 4. 값 제안표 (운영자 승인 대기 — 계획 §6 확인 지점 2)

아래 값은 전부 **제안**이다. `kis_mock_transport.example.yaml`은 이 표의 값을 채우지 않은
named-TBD `null` 상태로 유지된다 — 로더가 부팅을 거부하는 것이 의도된 동작이다.

| 필드 | 제안 값 | 근거 |
|---|---|---|
| `order_path` | `/uapi/domestic-stock/v1/trading/order-cash` | 공식 SDK `open-trading-api/examples_llm/domestic_stock/order_cash/order_cash.py:22`(`API_URL`) · N-17 메모 표1행 |
| `token_path` | `/oauth2/tokenP` | 공식 SDK `open-trading-api/examples_llm/auth/auth_token/auth_token.py:28`(`API_URL`) |
| `tr_id_buy` (모의) | `VTTC0012U` | `order_cash.py:103-118`(`env_dv=="demo"` 분기: `ord_dv=="buy"` → `VTTC0012U`) · N-17 메모("주식 주문 TR이 `TTTC0011U`(매도)/`TTTC0012U`(매수)/`TTTC0013U`(정정취소) 및 모의 `VTTC0011U`/`VTTC0012U`/`VTTC0013U`로 확인됨") |
| `tr_id_sell` (모의) | `VTTC0011U` | `order_cash.py:103-118`(`ord_dv=="sell"` → `VTTC0011U`) |
| `field_map.account` → `CANO` | 종합계좌번호(seal 소싱, §3) | `order_cash.py:121`(`"CANO": cano`) |
| `field_map.instrument` → `PDNO` | 상품번호(종목코드) | `order_cash.py:123`(`"PDNO": pdno`) |
| `field_map.quantity` → `ORD_QTY` | 주문수량(문자열) | `order_cash.py:125` · docstring "String으로 전달해야 함" |
| `field_map.price` → `ORD_UNPR` | 주문단가(문자열) | `order_cash.py:126` |
| `static_body_fields.ACNT_PRDT_CD` | 계좌상품코드(2자리, 배포별 상수) | N-17 메모 body 9필드 나열 — 값은 계좌 개설 시 부여, **운영자 승인 대기** |
| `static_body_fields.ORD_DVSN` | 지정가 `"00"` 제안 | `inquire_psbl_order` docstring "`ORD_DVSN`:00(지정가)" — 시장가 `"01"`은 별도 승인 필요 |
| `static_body_fields.EXCG_ID_DVSN_CD` | `"KRX"` 제안 | `order_cash.py` docstring "[필수] 거래소ID구분코드 (ex. KRX)" — NXT/SOR 라우팅은 후속 |
| `static_body_fields.SLL_TYPE` | `""` 제안(매수 시 미사용) | `order_cash.py:34` 기본값 `sll_type: str = ""` |
| `static_body_fields.CNDT_PRIC` | `""` 제안(조건가 미사용) | `order_cash.py:35` 기본값 `cndt_pric: str = ""` |
| `min_send_interval_ms` | **2000**(권고 기본값 · 하한 1100 · 주문 엔드포인트 실측 후 조정) | P-13 실측은 **`endpoint_class=query` 한정**(clean 1.0 rps · 스로틀 2.0 rps · `EGW00201` — `docs/plans/2026-08-06-tos-phase0-p01-residual-17key-disposition-draft.md:141`, `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:1834-1849`). 그 다음 절(`…draft.yaml:1890-1926`)은 **«query 값을 주문 클래스로 외삽하지 말 것»** 경고와 2026-07-31 `--pace-s 1.1`(=1100ms) 페이싱에서도 주문/취소가 스로틀된 관측을 담는다 → 1100 은 하한일 뿐 주문 간격의 근거가 아니다. 보수 방향 = 크게. (2026-09-12 값 제안표 리뷰 HIGH-2 정정 · `docs/plans/2026-09-12-tos-operator-value-proposals.md` §6 와 동일) |
| `token_reissue_min_interval_s` | **서버 캠페인 실측 대기** | N-15 실측 4회가 **전패**(`docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:2119,2162`) — `token_blackout_window_ms: null` 이 그 결과. 이 값은 토큰 **재발급 쿨다운**(N-15 자체 관측 "토큰 1분 재발급 제한")이지 토큰 수명이 아님 — 어댑터는 수명을 각 토큰 응답의 `expires_in` 필드에서 읽는다(값이 없으면 부팅 없이 그 응답 자체를 거부) |

이제 `field_map`(4) + `static_body_fields`(5) = 9필드 **전항목**을 로더가 구성 시점에
`KIS_ORDER_CASH_WIRE_FIELDS`(codec.py)와 정확 일치 검증한다 — 이전 판의 "known T1 gap"(5필드
미해결)은 스키마 확장으로 해소되었고, 남은 것은 값 자체의 운영자 승인뿐이다.

## 5. custody 파일 준비 절차 (T2 lane C 착지 — `PROVISIONED_SCOPES` 확장 완료)

`kis_mock.app_key`/`kis_mock.app_secret` 두 스코프(계정 스코프는 §3 에 따라 없음)는
`tos_runtime.custody.file_custody.FileCustody.PROVISIONED_SCOPES` 에 이미 등재되어
있다(`frozenset({"read.principal", "evidence.key", "replay.params", "kis_mock.app_key",
"kis_mock.app_secret"})`) — 더 이상 별도 착지가 필요 없다. 남은 것은 파일 준비뿐:

1. **파일 준비**:
   ```bash
   install -m 0600 /dev/null <custody_root>/kis_mock.app_key
   install -m 0600 /dev/null <custody_root>/kis_mock.app_secret
   # 각 파일에 실제 값을 기입(개행 없이) 후:
   sha256sum <custody_root>/kis_mock.app_key      # -> custody.manifest.yaml 의 expected_sha256
   sha256sum <custody_root>/kis_mock.app_secret
   ```
2. **manifest principal 규칙**(계획 §2 결정 4 — `refuse_custody_principal_mismatch`가 부팅
   시점에 강제): `custody.manifest.yaml`(예시 아님, 실 배포판)의 `kis_mock.app_key`/
   `kis_mock.app_secret` 두 행 모두 `principal` 필드가 활성 broker scope(`MOCK_STOCK_ORDER`)
   의 `principal` 과 **문자 그대로 동일**해야 한다. `CustodyManifest` 는
   `{environment_label}` 치환을 하지 않는다(`load_broker_scopes` 와 다름) — 예시 설정의
   `"kis-mock-order-{environment_label}"` 은 치환되지 않은 견본 문자열이므로, 실 배포에서는
   그 자리에 실제 환경 라벨을 채운 구체 값(예: `kis-mock-order-paper`)을 직접 써야
   `refuse_custody_principal_mismatch` 를 통과한다. `file`/`expected_sha256`은 위에서 계산한
   값으로 채운다.
3. **자격증명 보관에 대한 정직한 설명**(독립 리뷰 F5): 어댑터는 app key/secret 을 실제
   네트워크 호출(`issue_token`/`post_order`) 하나를 감싸는 가장 좁은 `with` 블록 안에서만
   로드하고, 그 블록을 벗어나면 `CredentialHandle` 자신의 바이트버퍼는 zero-out 된다. 다만
   `CredentialHandle.value()`가 반환하는 `bytes` 복사본과 그것을 헤더 문자열로 만드는 `str`
   변환은 Python 의 불변 객체라 **이 어댑터가 직접 지울 방법이 없다** — 즉 "보관 범위를
   좁혔다"는 사실과 "메모리상 모든 사본이 지워진다"는 주장은 다르며, 이 코드베이스는 후자를
   주장하지 않는다(`adapter.py` 모듈 docstring이 이를 그대로 기술).

## 6. dry_run 부팅 절차 (T2 lane C 착지 — 실제 호출면)

`tos_runtime/compose/cli.py`는 `argparse` 인자 파싱만 한다 — 데몬 루프도, 전략/이벤트
주입도 하지 않는다(`cli.py` 모듈 docstring). 오늘 실제로 존재하는 호출면은 `python -c`로
`tos_runtime.compose.cli.parse_args` + `tos_runtime.compose.root.compose_paper_runtime` 을
직접 조합해 부르는 것뿐이다 — `sts-runtime` 같은 별도 실행 파일은 **존재하지 않는다**
(전작 초안의 자리표시자 커맨드는 발명이었다 — 정정).

```bash
# argv 만 CLI 로 파싱 (config_dir/data_dir/custody_root/environment_label/transport)
python -c "
from pathlib import Path
from tos_runtime.compose.cli import parse_args
args = parse_args([
    '--config-dir', '<config_dir>',
    '--data-dir', '<data_dir>',
    '--custody-root', '<custody_root>',
    '--environment-label', '<environment_label>',
    '--transport', 'kis-mock',
])
print(args)
"
```

실제 부팅은 `compose_paper_runtime(args.config_dir, args.data_dir, args.custody_root,
args.environment_label, construction=..., aggregate_risk_inputs_provider=...,
action_flow_inputs_provider=..., transport_kind=args.transport)` 를 호출하는 캐릭터 코드가
필요하다 — `construction`/두 risk-inputs provider 는 전략별 고유 값이라 CLI 플래그로
표현되지 않는다(`cli.py` 모듈 docstring). `config_dir` 에는 `kis_mock_transport.yaml`
(파일명 고정 — `tos_runtime.compose._transport_wiring.KIS_MOCK_TRANSPORT_CONFIG_NAME`)이
§4 제안표 승인 후 채워진 채로 있어야 한다; `broker_scopes.yaml` 의 `active_scope` 는
`MOCK_STOCK_ORDER`(`profile_evidence_ok: true`)여야 하고, `coordinator_preconditions.yaml`
의 `nonlive_broker_consuming.admitted` 는 dry_run 부팅만 원한다면 `false`(§2.2 참조 — 부팅
자체는 admission 과 무관), 실제 crossing 이벤트를 admission 통과까지 구동하려면 `true`
여야 한다(5조건 나머지는 스코프/INSTANCE 정합).

`kis_mock_transport.yaml`의 `mode: dry_run`을 유지한 채 부팅 → evidence 저장소에서
`TRANSPORT_DRY_RUN` 레코드 존재를 확인하는 것이 이 계획의 **운영자 종료 조건**이다(계획 §5).
`live` 전환은 §2.2 의 codec 결속이 **기본 compose 경로**(`--transport kis-mock`)에 실제로
배선된 뒤에만 가능하다 — T2 lane C 가 `KisWireCodecDigest` 를 `kis-mock` 부팅의 컨텍스트
리졸버 기본값으로 결속했으므로(`root.py::compose_paper_runtime`), `codec_bound=True` 는
이제 `kis-mock` 부팅마다 자동으로 참이다; 남은 것은 §4 제안표의 값 승인과 호스트/TR ID 가
INSTANCE 문서와 실제로 일치하는지의 운영 확인뿐이다.

## 7. TR ID 형상 검증 (독립 리뷰 F7)

`tr_id_buy`/`tr_id_sell`은 이제 접두사(`V`)뿐 아니라 **전체 형상**을 정규식
`^V[A-Z]{3}\d{4}[A-Z]$`(V + 대문자 3 + 숫자 4 + 대문자 1, 총 9자)으로 검증한다 — 공식 SDK
오라클의 실측(`order_cash.py:103-118`: `VTTC0011U`/`VTTC0012U`/`TTTC0011U`/`TTTC0012U`)과
N-17 메모의 추가 관측(`STTN1101U`, `CTFO6118R`)이 전부 이 형상을 따른다. `VTTTC0012U`(문자
하나 초과) 같은 변형은 접두사만 보는 이전 판에서는 통과했지만 지금은 거부된다.

## 8. 토큰 정체(`TokenStale`) evidence 확장 (독립 리뷰 F8)

토큰이 만료되었고 재발급 쿨다운도 아직 끝나지 않아 이번 attempt 가 거부될 때, evidence
`TRANSPORT_TOKEN_STALE`에 `cooldown_remaining_ms`(쿨다운이 몇 ms 더 남았는지)를 추가로
기록한다 — 운영자가 evidence 만 보고 "왜 이 attempt 가 소진되었는지"를 바로 이해할 수 있게
하기 위함.

## 9. 참고

- 공식 SDK 오라클(비채택 · read-only): `open-trading-api/examples_llm/domestic_stock/
  order_cash/order_cash.py`, `open-trading-api/examples_llm/auth/auth_token/auth_token.py`,
  `open-trading-api/examples_llm/kis_auth.py`(헤더 규약: `authorization`/`appkey`/`appsecret`/
  `tr_id`/`custtype`).
- N-17 수집 메모: `docs/plans/2026-07-29-tos-p02-n17-spec-collation.md`.
- P-13/N-15 실측: `docs/plans/2026-08-06-tos-phase0-p01-residual-17key-disposition-draft.md`,
  `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`.
- INSTANCE MOCK_VTS/REAL_PROD rest_base: 같은 파일 각각 `_kis.endpoints.rest_base`
  (MOCK ~line 384, REAL ~line 3579).
- 컴포즈 컨텍스트의 STAND-IN 다이제스트: `tos_runtime/compose/context.py:368`,
  `tos/src/tos/egress/predicates.py:386-390`, `tos_runtime.compose._egress_coordinates` 모듈
  docstring.
