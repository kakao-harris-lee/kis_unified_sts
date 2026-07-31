# 알려진 이연 항목 — 주문 실행 경로 (2026-07-31 기준)

> **문서 성격**: 운영 참조. 2026-07-31 프로브 캠페인 wave-3b 실측에서 나온 결함 중
> **의도적으로 이연한 것들**의 등록부다. 수정된 항목은 `124a96eb`에 있으며 여기 없다.
> 각 항목은 근거 위치와 "무엇을 하면 이 이연이 위험해지는가"를 함께 적는다.

이연 판단의 근거는 커밋 메시지(`124a96eb`)와 4라운드 적대적 리뷰다. 이 파일은
그 판단을 레포에서 조회 가능하게 만드는 것이 목적이며, 새 판단을 하지 않는다.

## ⚠ D-A. `TRADING_MODE` 어휘 충돌 — 라이브 오케스트레이터는 실주문을 낸 적이 없다

**가장 운영에 영향이 큰 항목이다.**

두 노브가 같은 이름을 다르게 쓴다:

| 소비자 | 허용 값 | 근거 |
|---|---|---|
| 오케스트레이터 배포 | `paper` \| `live` | `docker-compose.yml`(`TRADING_MODE: "${TRADING_MODE:-paper}"`) · `scripts/docker/trading_loop_entrypoint.sh`(그 외 값은 exit 64) |
| `ExecutionConfig` | `PAPER` \| `MOCK` \| `REAL` | `shared/execution/config.py` |

`services/trading/orchestrator.py::_init_execution_layer`는 `TRADING_MODE`를 그대로
대문자화해 쓰므로 실운영 경로에서 항상 `PAPER`/`LIVE`로 해석된다. 어느 쪽도
`MOCK`/`REAL`이 아니라서 `ExecutionConfig` 게이트가 거부하고, 그 예외는
degrade 핸들러가 잡아 `_order_executor = None`으로 만든다. 그 결과 청산 경로는
`else: # Mock execution` 분기로 낙하한다.

**따라서: `TRADING_MODE=live`로 띄워도 `OrderExecutor`를 통한 실주문은 나가지 않는다.**
이는 `124a96eb` 이전부터의 동작이며 그 커밋이 바꾸지 않았다(바꾸면 라이브 주문
경로를 켜는 행위이므로 별도 게이트 대상).

- **위험해지는 조건**: 라이브 선물을 무장하면서 이 경로가 동작한다고 가정할 때.
- **고칠 때 필요한 것**: 어휘 통일 + `live→REAL` 매핑은 라이브 주문 활성화이므로
  `config/futures_live.yaml::enabled`·Redis `futures:live:suspended`와 함께
  검토되는 별도 커밋. `124a96eb`는 이 매핑을 **명시적으로 거부**하고 인라인 주석을
  남겼다.

## D-B. 제출 경로 전송 오류 → 메시지 pending → 재전달 → 이중 주문

`124a96eb`는 취소 루프와 체결 조회의 전송 오류를 잡았으나 **주문 제출**은 잡지
않았다. 제출이 예외를 던지면 `services/order_router`의 `except Exception: return False`
경로로 메시지가 pending으로 남아 재전달된다. 전송 오류는 **주문이 이미 브로커에
접수됐는데 응답만 유실된 경우**를 포함하므로, 재전달이 두 번째 주문을 낼 수 있다.

같은 커밋의 unknown-fill 처리는 정반대 판단(재전달 위험 때문에 메시지를 소비)을
하고 있어 **두 경로가 같은 질문에 다르게 답한다**. 이 불일치가 이연의 핵심 근거다.

- **고칠 때**: 제출을 `_TRANSPORT_ERRORS`로 감싸 `OrderResponse(fill_state_unknown=True)`를
  반환하면 기존 소비 분기로 라우팅되어 두 경로가 일치한다(기계는 이미 있다).

## D-C. 자기유발 rate 거부가 `fill_state_unknown`으로 봉인 → 경보 피로

`_request_json`은 자체 rate 거부 시 `{"rt_cd": "RATE_LIMIT"}`를 반환하지만, 체결
조회는 이를 브로커 무응답과 구분하지 않아 `QUERY_FAILED`로 봉인한다. 연속 신호에서
버킷 이월이 생기면 마지막 폴 1건이 거부되어 운영자에게 "포지션 정합 확인" ERROR가
뜬다. **매매 행동은 바뀌지 않으므로 피해는 경보 피로**이지만, 하필 보호 청산
누락을 알리는 그 신호를 무시하게 만든다.

**함께 묶인 관찰**: `LiveExitExecutor`는 같은 어댑터·같은 executor를 재사용하므로
**보호 청산이 진입 체결 폴과 메인 버킷을 경합**한다. 취소에 별도 버킷을 준 논리가
더 안전critical한 청산에는 적용되지 않았다.

## D-D. 잔고 조회 페이지네이션 — 측정 시도됨, 여전히 미확립

`shared/kis/client.py`의 잔고 조회는 1페이지만 읽는다(연속키 미독·`tr_cont` 미검사·
행수 미확인·로그 없음). `services/trading/broker_verification.py`의 파괴적 분기가
이 결과를 소비하므로, 절단되면 보유 포지션이 "브로커 부재"로 추적에서 제거될 수
있다.

- **측정 수단**: `P-BAL` 프로브(`dffa24c0`, GET 전용). 런북 §5.6.
- **wave-4 결과(2026-07-31)**: 3대상 실행 완료 — 실전 주식 0행·실전 선물 0행·
  모의 주식 1행이라 **페이지 크기는 여전히 미확립**(어느 페이지 크기와도 정합).
  절단 인과는 추론으로 남는다. 정본 아티팩트
  `P-BAL-20260731T084147Z`/`-084238Z`/`-114344Z`
  (캠페인 README §wave-4). documentary 참고값(공식 예제 docstring): 주식 실전
  50건/모의 20건, 선물 20건 — 측정값이 아니며, P-5b에서 공식 100건 명세가 실측
  15행과 불일치한 전례가 있어 승격 금지.
- **주의**: 소액 계좌로는 페이지 크기를 확립할 수 없다(하한만 나온다). 실증에는
  페이지 크기를 초과하는 보유 계좌가 필요하다.

## D-F. 실전 선물 잔고 조회 — 런타임 파라미터 셋 자체가 거부됨 (wave-4 실측)

**등재 근거: 운영자 지시(2026-07-31).** D-D가 "절단 가능성"의 추론인 것과 달리
이것은 **실측된 거부**이며, 페이지네이션 이전 단계에서 경로 전체를 무효화한다.

`get_futures_balance`(`shared/kis/client.py:1051-1057`)는 실전 잔고 TR
(CTFO6118R)의 필수 파라미터 `MGNA_DVSN`(증거금구분)·`EXCC_STAT_CD`(정산상태)를
보내지 않는다. 실전 브로커는 이 셋을 `rt_cd=7 APMP0001 "증거금구분코드은(는)
필수입력 항목입니다"`로 거부한다(실측: `P-BAL-20260731T084304Z` — 프로브가
런타임 파라미터의 정확한 미러였고 그 미러가 거부됐다). 모의는 이 TR을 서비스하지
않으므로(`client.py:1026` NOTE + 가드 `:1031-1033`) **이 코드패스는 어느 브로커를
상대로도 성공한 적이 없다.**

결과 처리 방식이 위험을 증폭한다: `client.py`는 `rt_cd != "0"`을 로그 1줄 남기고
`[]`를 반환하므로, 실전에서 선물 잔고는 **항상 빈 목록으로 접힌다** — "거부"가
"보유 없음"과 구분되지 않는다. `broker_verification.py`의 `remove_redis_only`
분기(`:105`, 게이트 `:121-127`)가 이 항상-빈 잔고를 소비하면 추적 중인 **전
포지션이 `broker_absent`로 제거**될 수 있는 구조다.

- **위험해지는 조건**: 라이브 선물 무장 + `remove_redis_only` 활성. 현재는 양쪽
  다 꺼져 있어(`futures_live.enabled=false`) 잠복 상태다.
- **고칠 때 필요한 것**: ① 공식 예제([v1_국내선물-004])대로 두 필수 필드 보충 —
  프로브 하네스는 `af00ad22`에서 동일 수정 완료(야간 자매 TR의 `f00b4647`과 동일
  계열), 런타임 수정은 별도 리뷰 커밋. ② **거부와 빈-셋의 구분**: 실전 선물은
  빈 계좌도 `rt_cd=7`(msg_cd `KIOK0560` 빈-응답)을 반환하므로(실측
  `P-BAL-20260731T114054Z`), "rt_cd≠0 → `[]`" 접기를 유지하면 수정 후에도 정상
  빈-응답과 진짜 오류가 계속 뭉개진다. 파괴적 소비자가 있는 한 오류는 `[]`가
  아니라 명시적 실패로 전파돼야 한다.

## D-E. 소소한 이연 (심각도 낮음)

| # | 항목 | 위치 |
|---|---|---|
| 1 | `_load_execution_section` 도크스트링이 "부재 파일은 관용"이라 주장하나 실제로는 `ConfigNotFoundError`가 except 튜플에 없어 전파된다(HEAD와 동일·회귀 아님) | `services/trading/orchestrator.py` |
| 2 | `REDIS_URL`이 `redis://`/`rediss://` 스킴 없으면 이제 시작 시 실패(fail-closed 방향이라 수용) | `shared/execution/config.py` |
| 3 | 신규 함수 2건 반환 타입 주석 누락 | `orchestrator.py` · `services/order_router/main.py` |
| 4 | `fill_state_unknown` 조회가 happy path에도 await 1건 추가(레포 내 클라이언트는 전부 dict 조회) | `shared/execution/passive_maker.py` |
| 5 | unknown-fill 에스컬레이션의 유일한 영속 산출물이 로그 1줄이다 — 메트릭도 정합 키도 없다 | `services/order_router/main.py` |

## 운영자 확인이 필요한 항목

- **컨테이너 재시작 알림**: `124a96eb`가 수용한 시작 실패 모드들(미지 YAML 키·
  계좌번호 placeholder·스킴 없는 `REDIS_URL`)은 fail-closed가 옳은 방향이지만,
  `restart: unless-stopped` 하에서 **재시작 횟수에 알림이 없으면 조용한 크래시 루프**가
  된다. 알림 존재 여부 확인 필요.
- **`futures_fill_check_timeout_seconds`**: 현재 1.0s, 모의 실측 accept→조회가시
  p50은 2632.9ms. 모의 수치를 실전에 외삽하면 안 되므로 값 변경은 실전 측정
  (`P-R5`, `390800e4`) 후 별도 커밋. D-1/D-2 수정 후에는 타임아웃이 짧아도 위험
  결과가 아니라 정직한 unknown이 나오므로 긴급하지 않다.
