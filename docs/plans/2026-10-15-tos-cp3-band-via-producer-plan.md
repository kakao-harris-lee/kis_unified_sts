# CP-3 band 원천 경로 변경 — 런타임 GET(i) → ③ 생산자 경유(i-b′) (2026-10-15)

- **상위**: `docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md`(이하 「band 계획」) §4·§7·§9 3 ·
  `docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md`(이하 「③ 계획」) §3.4(자격증명 분리)·§3.5·§5.
- **운영자 결정 2026-10-15 (대화)**: band 켜기 경로 = **(c) ③ 생산자 경유** — 생산자가 실전 키 GET-only 로
  `FHMIF10000000` 을 읽어 저널로 넘기고, 런타임은 키를 들지 않는다. 같은 날 앞선 결정: 「먼저 수정(#904), 그다음 band」.
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
| B2 | 토큰은 custody `kis_mock.app_key/app_secret` 에서 온다. tenant 세션의 custody(`paper-custody`)에는 `read.principal`·`evidence.key`·`replay.params` 셋뿐이고, 러너는 `--env-file` 을 **렌더러에만** 준다 — 런타임은 자격증명을 들지 않는 것이 ③ 계획 §3.4 의 설계다. 덧붙여 `custody.load()` 의 `CustodyError` 는 `KisBandSourceReader.read()` 가 잡는 예외 셋 밖이라 band `None` 으로 접히지 않고 `snapshot()`/`decide()` 로 새어 나간다(band 계획 §4.6 「모든 실패 = band None」과 어긋남 — §6 L1) | `compose/_kis_credential_wiring.py` · `tos_runtime/venue/band_source.py::KisBandSourceReader.read` · `tools/tos_cp3/runners/run_tenant_session.sh` |
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
  `assert_read_only_call` 이 소켓 전에 거부하는 구조는 바뀌지 않는다. ③ 계획 M3 의 도달 모듈 핀(`shared.execution` 의
  주문 모듈 금지)도 그대로.
- 시점: **부팅 시 한 번**(시드 뒤 · 첫 줄 대기 전 — 러너가 런타임을 띄우기 **전에** band 줄이 존재하도록) + 설정 키
  `band_reread_minutes`(정수 또는 null) 주기의 재조회. 기본은 **null**(부팅 1회) — band 계획 §2 단조성(같은 거래일 안에서는
  확대만)으로 부팅 1회가 보수 방향으로 안전하다. 재조회는 2·3단계 확대를 반영하고 싶을 때 운영자가 켠다.
  ⚠ 2026-10-15 은 장중 30분 연속거래 공백(12:39~13:08 원시 행 0, 재개 뒤에도 미충전)과 장중 −10% 하락이 있었다 —
  서킷브레이커 1단계(20분 정지 + 10분 단일가)와 길이가 맞지만 **확인되지 않았다**. 확대가 실제로 있었는지는 첫 켜기
  세션의 재조회 증거가 답한다.
- 변환·검증은 생산자가 하지 **않는다** — 원 응답의 `output` 에서 세 필드(`futs_mxpr`·`futs_llam`·`futs_sdpr`)를 **문자열
  그대로** 옮기고, 원 응답 바이트의 SHA-256 을 함께 적는다. 척도 변환·격자·순서 검증은 런타임의 기존 검증 셋이 한다
  (band 계획 §4.2 — 한 곳에서만).
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
- `as_of_ms` 는 가격 저널과 같은 규칙(PR #898 리뷰 B1 처분 — append 직전 도장).
- append-only · 줄마다 한 번에 쓴다(가격 저널과 같은 원자적 append 경로 재사용). 재조회 줄은 뒤에 붙는다.
- 파일 경로는 정책이 아니라 **배포 값**이다 — 러너 env(`TENANT_PRODUCER_SESSION_DIR`)에서 오고 렌더가 런타임 설정에
  채운다(§3.3).

### 3.3 런타임 쪽 — 새 `band_source.kind: "producer_journal"`

- `BandReader = Callable[[], BandObservation | None]` 은 그대로다. 새 kind 의 reader 는 band 저널의 **마지막 유효 줄**을
  읽어 기존 `BandObservation` 을 만든다 — 서비스(`VenueConstraintService`)·스냅샷 결속·증거 kind(`VENUE_BAND_OBSERVED`)·
  재발행 규칙은 **무변경**.
- `raw_payload_digest` = 줄의 값(생산자가 본 원 바이트의 digest — §2 의 「주장」을 그대로 결속하고 증거 행에
  `raw_payload_digest_source: "producer"` 로 출처를 적는다). `source_continuity_id` = 줄의 `producer_continuity_id`.
- 기존 kind `kis_quote_get` 과 그 팩토리는 남긴다(이 문서는 지우지 않는다 — 주문 scope 와 분리된 MOCK 시세 경로가 생기면
  그때 쓸 수 있다). 로더는 kind 마다 필수 키를 따로 요구한다: `timeout_ms`·`kis_quote.yaml`·host seal 은
  `kis_quote_get` 만, `journal_path` 는 `producer_journal` 만. 2026-10-15 켜기 시도가 실측한 「`kis_quote.yaml` 의 이 경로에서 읽히지 않는
  필수 네 값」(`tr_id`·`field_mapping`·`source_id`·`request_timeout_s`)은 새 kind 에서 요구하지 않는다.
- 읽기 시점: 기존 `read_on`(`boot`·`phase_change`) 그대로. 파일만 읽으므로 rate limit·토큰 문제 없음.

### 3.4 가드 — 각각 실패하는 구체적 입력

band 계획 §4.6 의 셋을 유지하고, (i-b′)가 하나를 **강화**하고 하나를 **더한다**.

| 가드 | 실패 입력 | 처분 |
|---|---|---|
| G1 검증 셋(척도 정수 · `0<min<max` · tick 격자) | 줄의 `upper: "1162.73"`(0.02 격자 밖) | 기존 그대로 — 변환이 런타임에 있으므로 재사용 |
| G2 거래일 결속 | D 일 줄을 들고 D+1 에 같은 phase 로 첫 `snapshot()` | 기존 그대로 + **읽기 측 비교 추가**: 줄의 `trading_date` ≠ 런타임 `trading_date_now()` 이면 그 줄은 무효(이전 세션의 `band.jsonl` 이 남은 경우). 레드: 비교 삭제 → D 줄로 ADMISSIBLE |
| G3 계약 결속 | `A05610` 정책 + `A05611` 줄 | **강화** — 원 (i)에서는 응답에 계약 식별자가 없어 로더 규칙뿐이었지만, 이제 줄이 `instrument` 를 **들고 온다** → 읽기 측 비교가 **진짜 가드**가 된다(줄 `instrument` ≠ 정책 `scope.instruments` 유일 원소 → 무효). 레드: 비교 삭제 → 다른 계약 band 로 ADMISSIBLE (값: 10-08 P-VL 실측 `A05610` 987.46/1159.18 · `A05611` 990.48/1162.72) |
| G4 출처 allowlist (신규) | `source_id` 가 승인 접두가 아닌 줄(손으로 쓴 줄 · 합성 하네스 줄) | `bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES` 와 **같은 목록**(두 번째 목록 금지) — 접두 밖이면 무효. 레드: 검사 삭제 → 합성 줄의 band 로 ADMISSIBLE |

모든 무효 = band `None` + `VENUE_BAND_OBSERVED.reason` → 커널 `UNKNOWN` → 송신 0. 새 fail-open 경로는 여전히 「틀린 band 를
믿는 것」 하나이고, 남는 잔여 위험은 band 계획 §4.4a 의 「낡은 **응답**」(08:45 직후 브로커가 전일 band 를 내주는 경우) —
측정되지 않은 전제로 그대로 등재. REAL 원천이라 그 측정은 첫 켜기 세션의 `symmetric_about_basis` + `basis` 대 전일 종가
(생산자 동결 프레임)로 **오프라인 대조가 가능해진다**(MOCK 은 기준가 판별이 무정보였다 — `futs_sdpr == futs_prdy_clpr`).

### 3.5 런타임 자격증명 분리 — 무변경 확인

- 런타임 프로세스: 소켓 0 · KIS 자격증명 0 · `--env-file` 없음(③ 계획 §3.4 · #901 Codex 승인 경계).
- 생산자 프로세스: 새 GET 하나가 **같은** 실전 시세 키 경로를 쓴다. 키를 읽는 코드·로깅·xtrace 차단은 바뀌지 않는다.
- 세션 뒤 확인 「실전 주문 TR 0」은 「`producer-log.jsonl` 의 TR ⊆ {`FHKIF03020200`, `FHMIF10000000`} · 메서드 전부 GET」
  으로 바뀐다(런북 §7.2-d).

## 4. 켜기와 첫 세션 수용

- 켜는 배포: **LONG tenant 만**(band 계획 §5 — 상주 paper·SHORT 는 null). tick 2(이미 착지) · `_runtime.price_scale: 100`
  (생산자 `PRICE_SCALE = 100`, `tools/tos_cp3/produce_fields.py`).
- 활성화: VCP `canonical_digest` 는 `_runtime` 을 덮지 않으므로 **불변**(2026-10-15 실측: band 선언 유무와 무관하게
  `ef6646e8…`). tenant `safety_activation.yaml::members` 는 null — 갱신 대상 없음. 단 런타임 소스(`tos/runtime/src`)가
  바뀌므로 **같은 PR 에서 `config/tos_runtime/paper/release.yaml::expected_code_digest` 재도출**(band 계획 §9 2 와 같은 의무
  — 재도출하지 않으면 상주 세션이 다음 08:45 에 ABORT).
- 첫 켜기 세션 수용(③ 계획 §5 에 더한다):
  1. `band.jsonl` 에 그날 줄이 있고, 런타임 `VENUE_BAND_OBSERVED` 행의 `raw_payload_digest` 가 그 줄과 같다.
  2. **그날 소비된 모든 가격이 band 안**이다(`price_min ≤ close_x100 ≤ price_max`) — 아니면 band 원천이나 척도가 틀린
     것이고 그 세션의 ADMISSIBLE/INADMISSIBLE 판정을 믿지 않는다.
  3. `VENUE_SNAPSHOT_ISSUED` 행에 `band_digest` 가 있고 `absent_fields` 에서 세 필드가 빠졌다.
  4. 기존 M5·M6·B3·실전 주문 TR 기준(TR 집합은 §3.5 로 확장).
- 첫 세션의 `basis` 와 전일 종가 대조를 band 계획 §4.4a 잔여 위험의 측정으로 기록한다.

## 5. PR 분할 · 순서

1. **PR-A 생산자**: `quote_client.ALLOWLIST` 한 쌍 · band GET(부팅 + 선택 재조회) · `band.jsonl` 쓰기 · 생산자 YAML 키
   (`band_reread_minutes`, 기본 null) · `band_fetch_failed` 로그 · 러너/런북 TR 집합. 레드 증명: allowlist 밖 TR 은 소켓 전
   거부 · 실패 시 줄 없음 · 가격 저널 무영향(같은 입력에서 가격 저널 바이트 동일). 생산자의 자격증명 경로를 건드리지
   않으면 Claude 레인, 건드리면 Codex(③ PR-3 범위 승인).
2. **PR-B 런타임 + 켜기**: `producer_journal` kind · 로더 kind 별 필수 키 · G2 읽기 측 · G3 읽기 측 · G4 · §1 B2 의
   `CustodyError` 누출(kind `kis_quote_get` 경로 — 예외를 band `None` 으로 접고 레드 증명; 켜지 않은 경로지만 band 계획
   §4.6 과 어긋난 채 두지 않는다) · tenant LONG 정책 `band_source` 채움 + 렌더 슬롯(`instrument`·`journal_path`) ·
   `expected_code_digest` 재도출 · 테스트(`TestShippedTreesDeclareNoBandSource` 를 LONG/그 외로 분리). 커널 무변경이므로
   `tos-gate` 커널 digest 는 그대로여야 한다.
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
