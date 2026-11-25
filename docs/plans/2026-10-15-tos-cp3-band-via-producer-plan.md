# CP-3 band 원천 경로 변경 — 런타임 GET(i) → ③ 생산자 경유(i-b′) (2026-10-15)

- **상위**: `docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md`(이하 「band 계획」) §4·§7·§9 3 ·
  `docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md`(이하 「③ 계획」) §3.4(자격증명 분리)·§3.5·§5.
- **운영자 결정 2026-10-15 (대화)**: band 켜기 경로 = **(c) ③ 생산자 경유** — 생산자가 실전 키 GET-only 로
  `FHMIF10000000` 을 읽어 저널로 넘기고, 런타임은 키를 들지 않는다. 같은 날 앞선 결정: 「먼저 수정(#904), 그다음 band」.
- **v2 (같은 날, 리뷰 PR #905 처분 — 13건 전건 수용, 기각 0)**: HIGH-1 band GET 을 개장 뒤 첫 경계로 + 러너 band 줄 대기 ·
  HIGH-2 재조회는 측정 전용 · HIGH-3 출처 접두는 렌더된 목록의 설정 일관성 규칙(C1, 가드 아님) · MEDIUM-1 줄 날짜를
  그대로 + 생산자 `refuse_if_journal_exists` + reader 단위 레드 · MEDIUM-2 digest 세 파일 · LOW 1~4.
- **v3 (2026-10-16, 운영자 결정)**: band GET 을 **별도 단명 프로세스**로 분리한다
  (`python -m tools.tos_cp3.live_producer.band_probe`). 생산자의 분봉 루프에는 band 코드가
  없고, 시각·재시도·총 시간 상한은 **러너**가 소유한다. 아래 §3.1 의 「생산자가 band 를
  읽는다」 서술과 §5 1 의 PR-A 범위는 그 범위에서 **대체됐다**(아래 각 절의 ⛔ v3 블록 참조).
  남긴 이유: 그 텍스트가 왜 틀렸는지가 이 결정의 근거다. 지우면 다음 사람이 같은 길을 간다.
- **범위 밖**: 커널(`tos/src/tos/`) 변경 · 실주문(비협상 규칙 — 실전 선물 주문 경로 영구 차단) · 상주 `paper`·SHORT
  트리의 band(둘 다 null 유지, band 계획 §5) · band 계획 (ii) 규정 계산 대조.

## 0. 한 줄 요약

band 계획 §9 3(「tenant 정책에 `band_source` 를 채우고 활성화 갱신」)은 **그대로는 실행 불가**다(§1 실측). 원천을
런타임의 MOCK GET 에서 **③ 생산자의 REAL GET-only 조회**로 옮기고, 생산자가 쓴 **band 저널 한 줄**을 런타임이 새
`band_source.kind` 로 읽는다. 런타임은 계속 **소켓 0 · 자격증명 0**(③ 계획 §3.4) 이고, band 와 가격이 **같은 REAL
도메인**에서 온다. band 계획의 커널 무변경 결속(스냅샷 세 필드 · 유효 제약 · 증거 행)과 가드 셋은 그대로 재사용한다.

## 1. 왜 §9 3 이 막혔나 (2026-10-15 실측, main `7b9a1f00`)

| # | 사실 | 자리 |
|---|---|---|
| B1 | band reader 팩토리는 host seal 의 MOCK/REAL `rest_base` 를 **활성 주문 scope 의 INSTANCE** 에서 읽는다. LONG·SHORT·paper 세 트리의 활성 scope 는 전부 `SYNTHETIC_FUTURES_ORDER`(INSTANCE 없음, 설계상) → `band_source` non-null 이면 **부팅 거부**(`MarketFeedConfigError: intake_kind: kis_quote requires the active broker scope's own INSTANCE binding`) | `tos/runtime/src/tos_runtime/compose/_venue_wiring.py` `build_kis_band_reader_factory._factory` → `compose/_marketfeed_wiring.py::resolve_kis_instance_rest_bases` · `config/tos_runtime/cp3-setup-d-long/broker_scopes.yaml` 의 `active_scope` |
| B2 | 토큰은 custody `kis_mock.app_key/app_secret` 에서 온다. tenant 세션의 custody(`paper-custody`)에는 `read.principal`·`evidence.key`·`replay.params` 셋뿐이고, 러너는 `--env-file` 을 **렌더러에만** 준다 — 런타임은 자격증명을 들지 않는 것이 ③ 계획 §3.4 의 설계다. 덧붙여 `custody.load()` 의 `CustodyError` 는 `KisBandSourceReader.read()` 가 잡는 예외 셋 밖이라 band `None` 으로 접히지 않고 `snapshot()`/`decide()` 로 새어 나간다(band 계획 §4.6 「모든 실패 = band None」과 어긋남 — §L L1) | `compose/_kis_credential_wiring.py` · `tos_runtime/venue/band_source.py::KisBandSourceReader.read` · `tools/tos_cp3/runners/run_tenant_session.sh` |
| B3 | MOCK_VTS INSTANCE 에 묶인 유일한 scope 는 `MOCK_STOCK_ORDER`(`endpoint_class: BROKER_ORDER`, `asset_scope: STOCK`)이고, 그 활성화는 `broker_scopes.yaml` 머리말이 **별도 승인**으로 묶어 두었다(운영자 결정 2026-09-23) | `config/tos_runtime/cp3-setup-d-long/broker_scopes.yaml` 머리말 |

band 계획 §4.2 의 전제(「기존 `kis_quote` host seal 과 토큰 수명 관리를 **재사용**」)가 그 둘이 **활성 주문 scope 에
묶여 있다**는 것을 보지 못했다. 이 문서는 그 전제를 바꾼다.

**부수 실측(같은 날)**: 이 경로 변경과 무관하게, MOCK band 는 REAL 가격과 다른 도메인이다. 10-08 은 MOCK `A05611`
band 990.48/1162.72(`docs/broker-profiles/evidence/2026-10-08-cp3-venue-limits/P-VL-20261008T010822Z.json`) 안에 REAL
분봉 종가 1046~1080(생산자 동결 프레임)이 들어 있었지만, 같은 날 비교는 그 한 번뿐이다. REAL 원천은 이 질문을 없앤다.

## 2. 결정 (§7 (i-b) 재검토)

band 계획 §7 은 (i-b)를 「③ 이 아직 설계 전이라 그 계약에 band 를 얹는 것은 순서가 뒤집힌다 · 런타임이 원 응답을 보지
못해 digest·연속성을 **생산자의 주장**으로만 받는다」로 기각하고 「③ 설계 때 다시 볼 후보」로 남겼다. 지금:

- ③ 은 **있다**(PR-2 #898 · PR-3 #901 · genesis 10-15). 브로커에 닿는 프로세스는 이미 생산자 하나다.
- 「생산자의 주장」은 **새 신뢰가 아니다** — 런타임이 판정하는 가격 15 필드 전부가 이미 생산자의 주장이다. band 를 같은
  주체에게서 받는 것은 신뢰 경계를 넓히지 않고, 런타임에 키를 넣는 (b)와 주문 scope 를 바꾸는 (a)는 넓힌다.
- 이름은 (i-b′)로 둔다 — 원 (i-b)는 「band 를 journal **행**으로」였고, 여기서는 가격 저널과 **분리된 band 저널**이다(§3.2).

## 3. 설계

### 3.1 생산자 쪽 — 읽기

- TR `FHMIF10000000`, 경로 `/uapi/domestic-futureoption/v1/quotations/inquire-price`(P-VL `_PRICE_PATH`,
  `tools/broker_probes/probes_venue_limits.py`), 시장 구분 `F`, 종목 = 생산자 설정의 `instrument`(가격 GET 과 **같은
  하나의 출처**). REAL 호스트 · 실전 **시세** 키(`.env.real`) — 가격 GET 과 같은 자격증명 경로, 새 키 없음.
- `tools/tos_cp3/quote_client.py::ALLOWLIST` 에 이 한 쌍(TR, 경로)을 더한다. 메서드는 GET 그대로 —
  `assert_read_only_call` 이 소켓 전에 거부하는 구조는 바뀌지 않는다. ③ 계획 §5 5번(§3.3)의 도달 모듈 핀
  (`test_item5_*` — `shared.execution` 의 주문 모듈 금지)도 그대로. TR·경로 상수는 `quote_client` 에 **지역 정의**한다 —
  P-VL 모듈은 MOCK 호스트로 봉인돼 있어 import 하지 않는다.
- 이 `ALLOWLIST` 는 「실전 선물 주문 0」 규칙이 **코드로 집행되는 자리**다. 그래서 PR-A 의 그 diff 는 자격증명 코드를
  건드리지 않아도 Codex 범위 리뷰 대상 후보로 올리고, 범위·비용 승인은 PR-A 시점에 운영자에게 묻는다(§5).

⛔ **v3 (2026-10-16, 운영자 결정) — 이 절의 「생산자가 읽는다」는 대체됐다.**
band GET 은 **별도 단명 프로세스**가 한다(`tools/tos_cp3/live_producer/band_probe.py`).
이유: 네 번의 독립 리뷰가 「이 프로세스가 자기 HTTP 호출의 총 시간을 정직하게 묶을 수
없다」를 세 번 다른 방식으로 확인했다 —
① phase 타임아웃은 **청크 하나**의 상한이다(합쳐서 총량이 되지 않는다) ·
② `iter_bytes()` 안의 마감은 **디코드된** 바이트만 보므로 헤더 수신과 압축-무출력
구간을 못 본다(Codex 실측: 1 s 예산에 1.6 s) ·
③ 워커 스레드는 호출자가 `client.close()` 에서 막히고, 해시·파싱이 예산 밖이며,
버려진 워커가 `KISAuthManager.get_token()` 락을 쥐어 다음 `page()` 를 0.8 s 세운다
(Codex 4 라운드 F1·F2·F3). **SIGKILL 은 협상하지 않는다** — 그래서 상한을 프로세스
경계에 둔다.
아래 시점·상한·재시도 서술은 **의도는 그대로**이고 **집행 주체만** 바뀌었다:
「개장 뒤 첫 경계」는 러너가 `open + 한 경계`까지 잠들어 집행하고(STOP_S 로 cap),
재시도 1 회는 러너가 다음 경계에 한 번만 띄우며, 총 시간은
`timeout --kill-after=5s $BAND_PROCESS_TIMEOUT_S` 가 묶는다. 생산자 쪽에 남는 band
설정은 **크기 상한**(`band_max_response_bytes`) 하나다 — 시간이 아니라 크기는 이
계층이 스스로 집행할 수 있고, 48 MiB 본문이 0.2 s 예산 안에서 해시·파싱된 것이 그
필요의 실측이다(F2). ⚠ 그 크기 상한은 **규칙 둘**이다(리뷰 5 라운드 Codex A):
`accept-encoding: identity` 는 **요청**일 뿐이고 `iter_bytes()` 는 yield 전에
**압축을 푼다** — Codex 가 16,328 바이트를 16 MiB 첫 청크로 실측했다. 그래서
비-identity `Content-Encoding` 은 본문을 읽기 **전에** 거부하고, `iter_raw` 로 받으며,
상한은 청크를 **복사하기 전에** 센다. 프로세스 타임아웃은 시간을 묶고, 메모리에는
그런 감독자가 없다.
한 가지는 의도까지 바뀌었다: **요청 로그가 둘로 갈린다.** band 시도는
`band-log.jsonl`(프로브의 세션 dir), 분봉은 `producer-log.jsonl` 이다 — 두 프로세스가
한 파일에 append 하면 줄이 섞여 깨지므로. 따라서 §3.5 의 「TR 부분집합」 확인은
**두 파일을 함께** 읽어야 하고, 아래 로그 서술의 파일 이름은 그만큼 대체됐다
(런북 §7.2-d 가 그 명령을 들고 있다).

- 시점: **개장 뒤 첫 경계에서 한 번** — 생산자가 그날 첫 가격 줄을 append 한 **직후**(이르면 08:46). 부팅 직후(시드 뒤)가
  **아니다**(리뷰 HIGH-1): 생산자는 개장 전에 뜨도록 만들어져 있고(`producer.py` 의 `first_boundary = max(open + 1분, now)`)
  러너의 첫 줄 대기는 600 s 라, 부팅 직후 GET 은 보통 08:3x~08:45 의 **개장 전** 응답이다. 그리고 런타임은 그 band 를
  하루 종일 쓴다(§3.3 — tenant 캘린더는 `CONTINUOUS 08:45–15:45` 한 phase 라 장중 재읽기 계기가 없다). 개장 전 응답은
  band 계획 §4.4a 잔여 위험(「브로커가 전일 band 를 내준다」)이 가장 커지는 시각이다. 개장 뒤 첫 경계면 그날 기준가가
  이미 서 있다 — 여전히 측정되지 않은 전제지만 가장 불리한 시각은 피한다.
- 늦은 기동(09:00 뒤)은 문제가 아니다 — §2 단조성으로 그 시각의 band 는 그때까지 가장 넓은 **현재** band 다.
- 러너: 첫 줄 대기가 **band 줄도** 함께 기다린다(같은 상한 안에서). 상한 안에 band 줄이 없으면 러너는 멈추지 않고
  `BAND ABSENT — 이 세션 전체 band UNKNOWN(송신 0)` 을 크게 적고 진행한다 — 가격 수집·B3 대조는 그래도 가치가 있고,
  band 부재는 보수 방향이다. 이 세션은 §4 수용 1번에서 실패로 기록된다. 「런타임 부팅 전에 band 줄이 있다」는 생산자
  순서가 아니라 **러너 단계가 확인**한다.
- 재조회(설정 키 `band_reread_minutes`, 정수 또는 null, 기본 **null**)는 **측정 전용**이다(리뷰 HIGH-2). 런타임은
  `read_on` 의 `boot`·`phase_change` 에서만 읽고 장중 phase 변화가 없으므로, 장중에 붙은 재조회 줄은 15:45 전에 판정에
  **닿지 않는다**. 재조회의 쓸모는 `band.jsonl` 에 장중 확대의 증거를 남기는 것뿐이다. 장중 확대를 판정에 반영하려면
  런타임 읽기 계기를 더해야 하고(서비스 변경 + 자기 레드 증명), 이 문서 범위 밖이다(§L L4).
  ⚠ 2026-10-15 은 장중 30분 연속거래 공백(12:39~13:08 원시 행 0, 재개 뒤에도 미충전)과 장중 −10% 하락이 있었다 —
  서킷브레이커 1단계(20분 정지 + 10분 단일가)와 길이가 맞지만 **확인되지 않았다**. 확대가 실제로 있었는지는 재조회를 켠
  세션의 증거가 답한다.
- 로그: band GET 은 시도마다 `producer-log.jsonl` 에 메서드·`tr_id`·경로를 남긴다(리뷰 LOW-2 — 지금 `page()` 는 모듈 상수
  `TR` 을 적으므로, 새 메서드가 제 `tr_id` 를 적지 않으면 §3.5 의 TR 부분집합 확인이 이 호출을 **보지 못한 채** 통과한다).
  원 바이트 digest 는 `.json()` 전에 `response.content` 에서 잡는다(`page()` 는 지금 원 바이트를 들고 있지 않다).
- 변환·검증은 생산자가 하지 **않는다** — 원 응답의 `output1` 에서 세 필드(`futs_mxpr`·`futs_llam`·`futs_sdpr`)를 **문자열
  그대로** 옮기고, 원 응답 바이트의 SHA-256 을 함께 적는다. 척도 변환·격자·순서 검증은 런타임의 기존 검증 셋이 한다
  (band 계획 §4.2 — 한 곳에서만).
  ⚠ **정정(PR #906 리뷰 1 라운드)**: 초판은 이 자리를 「`output`」으로 적었다. 실제 멤버는 **`output1`** 이다 —
  공식 래퍼가 이 TR 에 `output1`/`output2`/`output3` 을 돌려주고
  (`examples_llm/domestic_futureoption/inquire_price/inquire_price.py`), P-VL 이 2026-10-08 **MOCK** 실측에서 다섯
  L1 가격 필드를 `output1` 에서 읽었다(`tools/broker_probes/probes_venue_limits.py`). REAL 면은 아직 이 경로로
  읽어 본 적이 없으므로 **같은 래퍼 문서에서 추론**한 것이다(래퍼의 `env_dv` 표가 실전·모의 모두 `FHMIF10000000`
  하나를 주고, 응답 모양을 구분하지 않는다) — 첫 켜기 세션이 그 추론의 실측이다. `output` 을 읽으면 아무것도 맞지
  않아 band 가 **아무 사유도 남기지 않고 영구 부재**가 되므로, 구현은 `output1` 하나만 읽고 부재를 실패로 적는다
  (`band_line.BAND_PAYLOAD_MEMBER`).
- 실패(전송 오류 · `rt_cd ≠ 0` · 필드 부재): band 줄을 **쓰지 않고** `producer-log.jsonl` 에 `band_fetch_failed` 를 남긴다.
  생산자는 계속 돈다 — band 부재는 런타임에서 `UNKNOWN` → 송신 0 으로 접히는 보수 방향이고, 가격 저널을 멈출 이유가
  아니다. 이 실패는 #904 의 `max_consecutive_fetch_error_minutes` 계수에 **넣지 않는다**(그 계수는 분봉 폴링의 것이다).

### 3.2 band 저널 — 계약

생산자 세션 dir 의 **별도 파일** `band.jsonl`(가격 저널과 분리 — 가격 저널은 「분당 한 줄, 15 필드, 줄당 한 번 소비」라는
③ 계약이고 band 는 그 계약 밖의 일별 사실이다). 한 줄:

```json
{"kind": "cp3-band/1", "source_id": "tos-cp3-live/0.x.y", "instrument": "A05611",
 "trading_date": "20261016", "tr_id": "FHMIF10000000",
 "upper": "1012.34", "lower": "862.10", "basis": "937.22",
 "raw_payload_digest": "<sha256 of raw response bytes>",
 "producer_continuity_id": "<생산자 부팅마다 새로>", "as_of_ms": 0}
```

- `trading_date` = 생산자의 KST 캘린더 거래일(생산자가 이미 쓰는 tenant `calendar.yaml`) — band 계획 §4.2 와 같이 **로컬
  도장**이고 응답 필드가 아니다.
- `as_of_ms` 는 가격 저널과 같은 규칙(PR #898 리뷰 B1 처분 — append 직전 도장, 단조 증가).
- 쓰기: `ObservationJournal`(`tools/tos_cp3/live_producer/sinks.py` — 임시 파일 + `os.replace` 통째 교체 · 도장 소유 ·
  비전진 도장 거부)의 의미를 그대로 쓰되, 그 클래스는 가격 `JOURNAL_KEY_ORDER` 를 강제하므로 **키 순서를 인자로
  일반화**한다(리뷰 LOW-1). 재조회 줄은 뒤에 붙는다.
- ⛔ **같은 세션 dir 의 `band.jsonl` 이 이미 있으면 생산자는 부팅을 거부한다**(`refuse_if_journal_exists` — 리뷰
  MEDIUM-1). 지금 생산자는 같은 종목의 세션 dir 재사용을 `refuse_if_partitions_exist` 로 막지만 **다른 종목**(롤 날
  재사용)은 막지 않고, 러너는 세션 dir 에 `mkdir -p` 만 한다. 낡은 band 줄을 구조적으로 막는 것은 이 거부이고, §3.4 G2 의
  읽기 측 비교는 그 뒤의 겹이다.
- 파일 경로는 정책이 아니라 **배포 값**이다 — 러너 env(`TENANT_PRODUCER_SESSION_DIR`)에서 오고 렌더가 런타임 설정에
  채운다. 렌더 슬롯 이름은 **`band_journal_path`**(가격 저널의 기존 `marketfeed.yaml::journal_path` 와 겹치지 않게 —
  리뷰 LOW-4), 렌더러의 닫힌 값 출처 집합(`scripts/tos/render_paper_config.py::_VALUE_SOURCES`)에 새 항목 + 새 러너 인자.

### 3.3 런타임 쪽 — 새 `band_source.kind: "producer_journal"`

- `BandReader = Callable[[], BandObservation | None]` 은 그대로다. 새 kind 의 reader 는 band 저널의 **마지막 줄 하나**를
  읽어 기존 `BandObservation` 을 만든다 — 서비스(`VenueConstraintService`)·스냅샷 결속·증거 kind(`VENUE_BAND_OBSERVED`)·
  재발행 규칙은 **무변경**.
- 마지막 줄이 무효면 **앞 줄로 물러나지 않는다** — band `None` + `reason`(리뷰 LOW-1). 물러나면 「지금 유효한 band」가
  아니라 「한때 유효했던 band」를 믿게 된다. 파일 부재 · 파싱 불가 · I/O 오류도 전부 band `None` + `reason`(band 계획 §4.6).
- `raw_payload_digest` = 줄의 값(생산자가 본 원 바이트의 digest — §2 의 「주장」을 그대로 결속하고 증거 행에
  `raw_payload_digest_source: "producer"` 로 출처를 적는다). `source_continuity_id` = 줄의 `producer_continuity_id`.
- `BandObservation.trading_date` = **줄의 `trading_date`**(생산자 도장)이다 — 런타임의 `trading_date_now()` 로 다시 찍지
  **않는다**(리뷰 MEDIUM-1). 다시 찍으면 서비스의 거래일 결속(`service.py::_enforce_trading_date_bond`)이 낡은 줄에 대해
  영원히 발화하지 못한다. `as_of_ms` = 읽기 직전의 런타임 단조 시계(`kis_quote_get` 과 같은 규칙), 줄의 `as_of_ms` 는 증거에
  `producer_as_of_ms` 로 남긴다.
- 기존 kind `kis_quote_get` 과 그 팩토리는 남긴다(이 문서는 지우지 않는다 — 주문 scope 와 분리된 MOCK 시세 경로가 생기면
  그때 쓸 수 있다). 로더는 kind 마다 필수 키를 따로 요구한다: `timeout_ms`·`kis_quote.yaml`·host seal 은
  `kis_quote_get` 만, `band_journal_path` 와 `approved_source_prefixes`(§3.4 C1) 는 `producer_journal` 만. 2026-10-15 켜기 시도가 실측한 「`kis_quote.yaml` 의 이 경로에서 읽히지 않는
  필수 네 값」(`tr_id`·`field_mapping`·`source_id`·`request_timeout_s`)은 새 kind 에서 요구하지 않는다.
- 읽기 시점: 기존 `read_on`(`boot`·`phase_change`) 그대로. 파일만 읽으므로 rate limit·토큰 문제 없음. ⚠ 즉 판정에 쓰이는
  band 는 **런타임 부팅 시 읽은 한 줄**이다(§3.1 러너 대기가 그 줄의 존재를 보장한다).

### 3.4 가드 — 각각 실패하는 구체적 입력

band 계획 §4.6 의 셋을 유지하고, (i-b′)가 하나(G3)를 **강화**한다. 출처 접두 검사는 가드가 아니라 **설정 일관성 규칙**
(C1)으로 둔다 — 구체적 fail-open 입력을 쓸 수 없기 때문이다(아래).

| 가드 | 실패 입력 | 처분 |
|---|---|---|
| G1 검증 셋(척도 정수 · `0<min<max` · tick 격자) | 줄의 `upper: "1162.73"`(0.02 격자 밖) | 기존 그대로 — 변환이 런타임에 있으므로 재사용 |
| G2 거래일 결속 | ① 구조: 이전 세션의 `band.jsonl` 이 남은 세션 dir 로 생산자 부팅 · ② 읽기: D 일 줄이 D+1 런타임에 읽힘 | ① 생산자 `refuse_if_journal_exists`(§3.2) — 레드: 거부 삭제 → 낡은 줄이 남은 채 부팅. ② 겹: reader 의 읽기 측 비교(줄 `trading_date` ≠ 런타임 `trading_date_now()` → 무효) + 서비스의 기존 결속(§3.3 — 줄 날짜를 그대로 싣기 때문에 발화 가능). ⚠ 가려진 절 주의(리뷰 MEDIUM-1): 서비스 결속은 `snapshot()` 첫머리에서 돌므로, 읽기 측 비교를 지워도 **두 번째** 스냅샷부터는 서비스가 떨어뜨린다 — 그래서 읽기 측 비교의 레드 증명은 **reader 단위 테스트**(reader 가 `None` 을 돌려야 함)와 **읽은 직후 첫 스냅샷**의 판정으로 한다. 두 번 부르는 통합 테스트는 이 절을 판별하지 못한다 |
| G3 계약 결속 | 롤 날 다른 종목 세션 dir 재사용 · 남의 파일 — `A05610` 정책 + `A05611` 줄 | **강화** — 원 (i)에서는 로더 규칙뿐이었지만 이제 줄이 `instrument` 를 들고 와 **읽기 측 비교**가 생긴다(줄 `instrument` ≠ 정책 `scope.instruments` 유일 원소 → 무효). ⚠ 그 `instrument` 는 **브로커 응답의 메아리가 아니라** 생산자의 요청 인자다(응답 본문에는 여전히 계약 식별자가 없다 — 리뷰 LOW-3). 그래서 이 가드는 「생산자의 요청 ↔ 런타임 정책」 결속이지 「브로커가 이 계약의 band 라고 말했다」가 아니다. 레드: 비교 삭제 → 다른 계약 band 로 ADMISSIBLE (값: 10-08 P-VL 실측 `A05610` 987.46/1159.18 · `A05611` 990.48/1162.72) — 테스트는 `instrument` **만** 바꾸고 날짜·출처는 유효하게 둔다 |

**C1 출처 접두 — 설정 일관성 규칙(가드 아님, 리뷰 HIGH-3).** 줄의 `source_id` 가 승인된 실제 생산자 접두가 아니면 무효.
가드 수에 넣지 않는 이유: 오늘 `band.jsonl` 을 쓰는 도구는 생산자 하나뿐이고, 손으로 쓴 줄은 접두를 그대로 베낄 수 있으므로
이 검사가 막는 **구체적 fail-open 입력을 쓸 수 없다**. 남기는 이유는 band 계획 §4.4b 의 transport 종목 규칙과 같다 —
어긋난 줄은 그 자체로 운영 오류의 신호다. 목록의 출처: 런타임(`tos/runtime/**`)은 방화벽 R1(`tools/tos_firewall_check.py`
— stdlib·`tos_runtime.*` 만)이라 `tools.tos_cp3.bootproof_guard` 를 import 할 수 **없다**. 그래서 렌더러(`tos/` 밖, 이미 이
파일을 렌더한다)가 `bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES` 를 렌더된 `band_source.approved_source_prefixes` 에
**값으로 써 넣고**, 「렌더 결과 == 그 상수」를 테스트로 고정한다 — 목록은 여전히 하나다. 레드: 접두 검사 삭제 → 승인 밖
`source_id`(날짜·종목은 유효) 줄이 band 로 쓰임. 이 줄을 실제로 쓰는 도구가 생기면(예: 합성 band 하네스) 그때 가드로 올린다.

모든 무효 = band `None` + `VENUE_BAND_OBSERVED.reason` → 커널 `UNKNOWN` → 송신 0. 새 fail-open 경로는 여전히 「틀린 band 를
믿는 것」 하나이고, 남는 잔여 위험은 band 계획 §4.4a 의 「낡은 **응답**」(08:45 직후 브로커가 전일 band 를 내주는 경우) —
측정되지 않은 전제로 그대로 등재. REAL 원천이라 그 측정은 첫 켜기 세션의 `symmetric_about_basis` + `basis` 대 전일 종가
(생산자 동결 프레임)로 **오프라인 대조가 가능해진다**(MOCK 은 기준가 판별이 무정보였다 — `futs_sdpr == futs_prdy_clpr`).

### 3.5 런타임 자격증명 분리 — 무변경 확인

- 런타임 프로세스: 소켓 0 · KIS 자격증명 0 · `--env-file` 없음(③ 계획 §3.4 · #901 Codex 승인 경계).
- 생산자 프로세스: 새 GET 하나가 **같은** 실전 시세 키 경로를 쓴다. 키를 읽는 코드·로깅·xtrace 차단은 바뀌지 않는다.
- 이 확인은 band GET 이 시도마다 제 `tr_id` 를 로그에 남길 때만 유효하다(§3.1 로그 항목).
- 세션 뒤 확인 「실전 주문 TR 0」은 「`producer-log.jsonl` 의 TR ⊆ {`FHKIF03020200`, `FHMIF10000000`} · 메서드 전부 GET」
  으로 바뀐다(런북 §7.2-d).

## 4. 켜기와 첫 세션 수용

- 켜는 배포: **LONG tenant 만**(band 계획 §5 — 상주 paper·SHORT 는 null). tick 2(이미 착지) · `_runtime.price_scale: 100`
  (생산자 `PRICE_SCALE = 100`, `tools/tos_cp3/produce_fields.py`).
- 활성화: VCP `canonical_digest` 는 `_runtime` 을 덮지 않으므로 **불변**(2026-10-15 실측: band 선언 유무와 무관하게
  `ef6646e8…`). tenant `safety_activation.yaml::members` 는 null — 갱신 대상 없음. 단 런타임 소스(`tos/runtime/src`)가
  바뀌므로 **같은 PR 에서 `expected_code_digest` 를 세 파일 모두 재도출** — `config/tos_runtime/paper/release.yaml` ·
  `config/tos_runtime/cp3-setup-d-long/release.yaml` · `config/tos_runtime/cp3-setup-d-short/release.yaml`(리뷰 MEDIUM-2;
  셋은 바이트 사본이고 `tos/runtime/tests/compose/test_tenant_tree_copies.py` 가 동일성을 강제한다). 빠뜨리면 상주 세션은
  다음 08:45 에, tenant 는 첫 부팅에 ABORT 한다(band 계획 §9 2 와 같은 의무).
- 첫 켜기 세션 수용(③ 계획 §5 에 더한다):
  1. `band.jsonl` 에 그날 첫 줄이 **개장 뒤**(`as_of_ms` ≥ 개장 시각) 있고, 런타임 부팅 전에 러너가 그 줄을 봤고(세션
     로그), 런타임 `VENUE_BAND_OBSERVED` 행의 `raw_payload_digest` 가 그 줄과 같다.
  2. **그날 소비된 모든 가격이 band 안**이다(`price_min ≤ close_x100 ≤ price_max`) — 아니면 band 원천이나 척도가 틀린
     것이고 그 세션의 ADMISSIBLE/INADMISSIBLE 판정을 믿지 않는다.
  3. `VENUE_SNAPSHOT_ISSUED` 행에 `band_digest` 가 있고 `absent_fields` 에서 세 필드가 빠졌다.
  4. 기존 M5·M6·B3·실전 주문 TR 기준(TR 집합은 §3.5 로 확장).
- 첫 세션의 `basis` 와 전일 종가 대조를 band 계획 §4.4a 잔여 위험의 측정으로 기록한다.

## 5. PR 분할 · 순서

1. ⛔ **v3 (2026-10-16) — PR-A 의 범위가 바뀌었다.** 아래 원 항목은 band GET 을 생산자
   안에 두는 전제로 쓰였고, 그 전제가 §3.1 의 v3 블록에서 대체됐다. 실제로 PR-A 가
   내보내는 것: `quote_client.ALLOWLIST` 한 쌍(지역 상수, 변경 없음) · **band 프로브
   프로세스**(`band_probe.py`: 한 번의 GET · `band.jsonl` 한 줄 · `band-log.jsonl` ·
   종료코드 0/2/3/4/1) · 생산자 분봉 루프에서 band 코드 **전부 제거**(남는 변경은
   **둘**이다: `SafetyViolation` 재발생 한 군데와, 리뷰 1 라운드에서 옮긴
   `_real_quotes` → `live_producer/real_quotes.py` — band 프로브가 그것을 import 하고
   실전 자격증명 해석이 한 모듈에 모인다. 그 둘을 빼면 분봉 루프 함수들은
   `origin/main` 과 바이트 동일이고, 그것을 AST 대조로 확인했다) ·
   러너의 `open + 한 경계` 대기와 프로세스 기동·재시도 1 회·rc 1 하드 ABORT ·
   `band.jsonl` 줄 대기와 `BAND ABSENT` · 스트림 크기 상한 · 런북 TR 집합(**두 로그**).
   재조회(`band_reread_minutes`)는 PR-A 에서 **빠졌다**(§L L6).

1. ~~**PR-A 생산자 + 러너**~~ (v3 로 대체 — 위 항목): `quote_client.ALLOWLIST` 한 쌍(지역 상수) · 개장 뒤 첫 경계의 band GET + 측정 전용 재조회
   (`band_reread_minutes`, 기본 null) · 시도마다 `tr_id` 로그 · 원 바이트 digest · `band.jsonl` 쓰기(키 순서를 일반화한
   저널) · `refuse_if_journal_exists(band.jsonl)` · `band_fetch_failed` 로그 · 러너의 band 줄 대기와 `BAND ABSENT` 기록 ·
   런북 TR 집합. 레드 증명: allowlist 밖 TR 은 소켓 전 거부 · 실패 시 줄 없음 · 개장 전에는 GET 하지 않음 · 남은
   `band.jsonl` 로 부팅 거부 · band GET 이 로그에 제 `tr_id` 를 남김 · 가격 저널 무영향(같은 입력에서 가격 저널 바이트
   동일). 리뷰: Claude 레인 + `ALLOWLIST` diff 는 Codex 범위 리뷰 후보(§3.1 — 운영자 승인 시).
2. **PR-B 런타임 + 켜기**: `producer_journal` kind(마지막 줄 하나 · 물러나지 않음 · 줄 날짜를 그대로) · 로더 kind 별 필수
   키 · G2 읽기 측(reader 단위 레드) · G3 읽기 측 · C1(렌더된 접두 목록 + 「렌더 == 상수」 테스트) · §1 B2 의
   `CustodyError` 누출(kind `kis_quote_get` 경로 — 예외를 band `None` 으로 접고 레드 증명; 켜지 않은 경로지만 band 계획
   §4.6 과 어긋난 채 두지 않는다) · tenant LONG 정책 `band_source` 채움 + 렌더 슬롯(`instrument`·`band_journal_path`) ·
   `expected_code_digest` **세 파일** 재도출 · 테스트(`TestShippedTreesDeclareNoBandSource` 를 LONG/그 외로 분리,
   `test_tenant_tree_copies.py` 의 알려진 차이 집합 갱신). 커널 무변경이므로 `tos-gate` 커널 digest 는 그대로여야 한다.
   PR-A 가 함께 지킬 것(v2 재리뷰 LOW 셋):
   - 러너의 band 줄 확인은 **파일이 아니라 줄**을 본다 — 줄 `trading_date` == 오늘 · `instrument` == `$INSTRUMENT` ·
     `as_of_ms` ≥ 개장(수용 1번과 같은 조건). 파일 존재만 보면 생산자 거부가 퇴행했을 때 낡은 파일이 즉시 통과한다.
   - band GET 이 **다음 분 가격 폴링을 밀지 않는다** — band 시도(재시도 포함)는 다음 경계 − `first_poll_delay_s` 전에
     끝나도록 상한을 두고, 다음 폴링 시작 시각이 band 유무와 무관함을 테스트로 고정한다(「가격 저널 바이트 동일」은 내용만
     보고 시각을 보지 않는다).
   - band 줄 대기는 첫 가격 줄 뒤 **별도의 작은 추가 허용**(설정 값)을 갖는다 — 첫 줄이 600 s 상한 끝에 오면 band GET 에
     남는 시간이 거의 없기 때문이다. 넘기면 `BAND ABSENT`(보수 방향).
3. **첫 켜기 세션** → §4 수용 → 증거 PR.

## 6. 기각한 대안

| 대안 | 이유 |
|---|---|
| (a) 배포 자세 변경 — MOCK_VTS scope 활성 + `kis_mock.*` custody | 유일한 MOCK scope 가 **주식 주문** 모양이라 선물 tenant 의 주문 송신 자세를 바꾼다 · 별도 승인 사안(운영자 2026-09-23) · band 는 여전히 MOCK 도메인 |
| (b) 런타임 변경 — host seal 을 주문 scope 에서 떼고 런타임에 MOCK 자격증명 경로 | 런타임에 키를 넣어 ③ 계획 §3.4 분리를 일부 되돌린다 · MOCK band 대 REAL 가격 도메인 불일치가 남는다 |
| band 를 가격 저널의 필드로(원 (i-b) 그대로) | 가격 저널은 15 필드 · 분당 한 줄 · `max_age_ms` 800 의 CII 계약이다. 일별 사실을 그 줄에 얹으면 CII 정책(`critical_input_policy.yaml`)에 신선도 의미가 다른 필드가 섞인다 |
| 생산자가 척도 변환·검증까지 | 검증이 두 곳에 생긴다. 런타임 검증 셋(band 계획 §4.2)이 이미 레드 증명을 갖고 있다 |

## L. 등재만 하는 것

- L1: §1 B2 의 `CustodyError` 누출은 PR-B 에서 고친다(§5 2).
- L2: 원 (i) 경로(`kis_quote_get`)가 쓸모 있으려면 「주문 scope 와 분리된 시세 scope」가 필요하다 — 별도 설계 후보.
- L3: band 계획 §6 (B) 의 GOV-001 후보(원천 선언의 커널 covered 승격 · band 관측을 정식 `CriticalInputSnapshot` 으로)는
  그대로 유효하다.
- L4: 장중 band 재읽기 계기(재조회 줄을 판정에 반영) — 서비스 변경 + 레드 증명이 필요한 별도 결정(§3.1).
- L5: `tools.broker_probes.probes_order`(모의 주문 가능)가 생산자 도달 모듈 핀의 `ORDER_EMITTING_MODULES` 에 없다 — PR-A
  에서 더할지 별도 검토(리뷰 SUGGESTION).
- L6: **band 재조회**(`band_reread_minutes`)는 v3 에서 PR-A 범위에서 빠졌다. 기본값이
  null 이었으므로 거동 변화는 없다. 다시 필요해지면 band 프로브를 **여러 번 띄우는**
  쪽이 자연스럽다(러너의 일정 문제이고, 프로세스 하나는 한 번의 GET 이라는 계약은
  그대로 둔다). ⚠ 재조회가 측정 전용이라는 §3.1 의 판단과, 「가격 줄이 있을 때만 돌아서
  정지 구간의 확대는 못 잡는다」는 한계는 그대로 유효하다 — 프로브를 쓰면 후자는
  해소된다(가격 줄과 무관하게 띄울 수 있으므로).
