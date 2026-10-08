# CP-3 band 원천 웨이브 — tick 정정(5→2) + band (i) 브로커 조회 계획 (2026-10-08)

- **상위**: `docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md` §2.0 ⚠(tick) · §6(band 원천 선택지) ·
  §8 6단계(「§2.0 tick 정정 + §6 결정 → 별도 계획 문서」) — 이 문서가 그 별도 계획이다.
- **운영자 결정 2026-10-08 (대화)**: ① `max_quantity: 10000` 은 **CP-3 tenant 트리에만**(paper 트리 채택 보류) ·
  ② 배포 `tick_size` 5 → **2** 정정 승인 · ③ band 원천 = **(i) 브로커 조회 먼저**, (ii) 규정 계산은 나중에 대조 확인용.
  ①의 착지는 tenant 트리 PR 의 몫이고 이 문서는 ②·③ 만 다룬다.
- **운영자 승인 2026-10-08 (대화, 이 문서 v1 뒤)**: §6 (A)·(B) **둘 다 권고대로** — (A) 런타임 첫 외부 호출·토큰 수용,
  (B) `_runtime.band_source` 는 증거 digest 로 메우고 커널 covered 승격은 GOV-001 후보 등재만.
- **v2 (2026-10-08, 독립 리뷰 PR #883 처분 — 9건 전건 수용, 기각 0)**: H1 계약 결속(§4.1·§4.4b) · M1 거래일 가드의 날짜
  출처와 레드 증명(§4.2·§4.4a) · M2 가격 척도 비교 대상(§4.1) · M3 커널 필드 스탠드인 표기(§4.3·§6) · L1~L5.
- **v3 (같은 날, 재리뷰 6건 전건 수용)**: H1 의 응답 측 재확인은 가려진 절 → 삭제, GET 종목 출처 단일화 + transport 대조 ·
  M1 입력을 운영 도달 가능 시퀀스로, 수치는 가상 표기 · `price_scale` 요구를 `band_source` 켜진 배포로 한정(상주 paper
  ABORT 방지) · `scope.instruments` 경로 · `timeout_ms` 는 출처 없는 제안값(null 템플릿) · §4.6 「셋」의 켜기 전제 명시.
- **범위 밖**: 커널(`tos/src/tos/`) 변경 · 실전 계좌·실주문(비협상 규칙) · 09-15 계획 §6 ⑤ 의 tradability 반쪽 ·
  CP-3 §5 3 ③ 의 실시간 필드 생산자(이 문서는 그 존재를 **전제 조건**으로만 적는다, §5).

## 0. 한 줄 요약

커널 레코드와 술어는 그대로 두고, 런타임 `VenueConstraintService` 가 스냅샷을 발행할 때 **정책에 선언된 band 원천**
(`FHMIF10000000` 의 `futs_mxpr`/`futs_llam`)을 한 번 읽어 **유효 shape 제약**의 `price_min/price_max` 를 채우고, 그 관측의
digest·연속성·거래일을 스냅샷의 **이미 있는** 세 필드(오늘 `None`)에 결속한다. 원천은 정책 파일의 `_runtime.band_source`
로 **배포마다 켠다** — 상주 paper 는 끈 채로 남는다(가격이 합성값이라 켜면 전부 INADMISSIBLE, §5). tick 은 tenant
트리에서 같은 PR 로 2 로 고치고, 상주 paper 의 tick 은 paper 채택과 함께 미룬다(§3).

fail-open 을 막는 가드는 **셋**이다 — 검증 셋(§4.2) · 거래일 결속(§4.4a) · **계약 결속**(§4.4b). 셋 다 「구체적 실패
입력 + 레드 증명」을 §8 에 갖는다.

✅ **운영자 확인 두 개는 2026-10-08 권고대로 승인됐다**(§6) — 10-08 설계 §6 의 (i) 행은 이 둘을 적지 않았었다:
(A) paper 런타임은 지금 **네트워크 호출 0**이다(transport synthetic · intake journal). band GET 은 그 런타임의 **첫 외부
호출이자 첫 KIS 토큰 소비자**가 된다. (B) 활성화 digest 는 커널 `canonical_digest` 만 덮으므로 `_runtime.band_source`
선언은 **활성화 밖**이다.

## 1. 지금 있는 것 (실측, main `f8869bdd`)

| 사실 | 자리 |
|---|---|
| 서비스는 정책의 shape 제약을 **그대로** 들고 다닌다 | `tos/runtime/src/tos_runtime/venue/service.py:196` (`self.shape_constraints = loaded_policy.policy.shape_constraints`) |
| 그 속성을 읽는 곳은 셋 — step 3 결정 · venue stage · 게이트웨이 item 11 컨텍스트 | `service.py::VenueConstraintService.decide` · `compose/_venue_wiring.py:606,638,676` · `compose/context.py:850` → `tos/src/tos/egressgw/gateway.py::_check_venue` |
| 스냅샷의 출처 세 필드는 항상 `None`, 증거 행에 `absent_fields` 로 기록 | `service.py:88` (`_SNAPSHOT_ABSENT_FIELD_NAMES`) · `service.py:271` 부근 (`_issue_snapshot`) |
| 스냅샷 재발행 계기는 **세션 phase 변화뿐** | `service.py::VenueConstraintService.snapshot` |
| 커널 술어는 band 가 `None` 이면 tick 을 보기 **전에** `UNKNOWN` | `tos/src/tos/venue/predicates.py::order_shape_admissible` (필수 bound 검사 → tick → band 순) |
| 커널 fold 는 `policy` 와 `constraints` 를 **따로** 받는다 — 유효 제약을 정책과 다르게 넘길 seam 이 이미 있다 | `tos/src/tos/egressgw/construction.py::fold_venue_admissibility` |
| `VenueShapeConstraints.price_min/max` 필드는 이미 있다 · 스냅샷의 covered 필드에 `critical_input_snapshot_digest`·`source_continuity_id`·`max_age` 가 이미 있다 | `tos/src/tos/venue/records.py::VenueShapeConstraints` · `records.py::VenueConstraintSnapshot._COVERED_FIELDS` |
| 활성화 대조는 **커널 `canonical_digest`** 로 한다 — `_model_view` 만 덮고 `_runtime` 블록은 밖 | `compose/_venue_wiring.py:265-271` (`require_member_activated(..., digest=p.canonical_digest)`) |
| paper 주문 transport 는 synthetic · 관측 인입은 journal(소켓·시계 없음) | `config/tos_runtime/paper/egress_coordinates.yaml:40` · `config/tos_runtime/paper/marketfeed.yaml:64` |
| 런타임에 MOCK 고정 시세 transport 와 토큰 수명 관리가 이미 있다(`FHMIF10000000` 형상 포함) | `tos/runtime/src/tos_runtime/transport/kis_quote/config.py` (host seal · TR 형상) · `kis_quote/adapter.py::build_quote_client` · `transport/kis_mock/token.py` |
| 런타임 캘린더 소유자가 KST 거래일을 준다 | `tos/runtime/src/tos_runtime/calendar/owner.py::trading_date_now` |
| 상주 paper 의 관측은 **합성값** — close `4_499_000`/`4_510_000` (×100 척도로 44,990 포인트대) | 호스트 드라이버 `~/.config/kis-probes/tos_paper_session.py:43-44` (sha256 `3ce14fb685a0…`, 비커밋) |
| 브로커 band 관측(모의, 10-08): `A05610` 기준가 1073.32 → 1159.18/987.46, 0.02 격자에만 일치 | `docs/broker-profiles/evidence/2026-10-08-cp3-venue-limits/` |

## 2. 단조성 — 왜 「부팅 직후 한 번」이 하루 동안 안전한가

시행세칙 제56조의2 제2항은 정규거래의 가격제한비율을 1단계에서 2·3단계로 **확대**하는 경우만 정하고, 같은 날 축소하는
조항은 없다(증거 `docs/broker-profiles/evidence/2026-10-08-krx-venue-limits/derivatives_enforcement_rule_164th_20260706.txt:2138-2157`).
08:45~09:00 과 개장 후 15분까지는 1단계만 적용된다(같은 조 제2항 본문 · 10-08 설계 §2.1 「단계 확대」 행). 따라서:

- **같은 거래일 안에서** 시각 t 에 읽은 band 는 t 이후의 어느 band 의 **부분집합**이다. 낡은 band 로 생기는 오판은
  「유효 주문을 INADMISSIBLE 로」(보수 방향) 하나뿐이고, 「band 밖 주문을 ADMISSIBLE 로」는 **생기지 않는다**.
- 08:45 부팅 직후의 GET 은 **1단계 band** 를 읽는다 — 그날 가장 좁은 band 다. 시각은 10-08 설계 §4.2 의 ① 샘플 창
  (08:50±3분)과 **다르지만** 같은 「1단계만 적용되는 08:45~09:00」 안이므로, 이 GET 의 증거 행은 ① 샘플의 **역할**(확대
  불가 창의 1단계 대조)을 한다. 창 정의를 바꾸는 것은 상위 설계의 일이고 여기서 하지 않는다.
- **거래일을 넘기면 이 성질이 깨진다** — 기준가격이 바뀌어 band 가 **이동**한다. 그래서 거래일 결속이 이 설계에서
  필요한 가드 셋 중 하나다(§4.4a; 나머지는 §4.2 검증 셋 · §4.4b 계약 결속).
- 단서: 제56조의2 제3항(거래소가 확대 시간을 변경할 수 있음)과 제56조제3항(시장관리상 변경)은 **축소 금지를 말하지
  않는다**. 제55조제5항(장중 기준가격 변경)은 band 를 넓히는 것이 아니라 **옮길** 수 있다(효과는 제56조제3항과 같은
  범주).
- **측정되지 않은 전제**: 08:45 직후의 응답이 **이미 오늘의** 기준가로 계산된 band 라는 것. 응답 본문에는 영업일 필드가
  없고(HTTP `Date` 헤더뿐), 10-08 관측에서 `futs_sdpr == futs_prdy_clpr` 라 기준가로도 날을 판별할 수 없었다. KIS 모의가
  08:45:0x 에 아직 **전일** band(어쩌면 2·3단계로 확대된)를 내준다면 아래 가드 어느 것도 그것을 잡지 못한다 → §4.4a
  잔여 위험. 단조성은 규정 본문의 구조에서 온 것이지 보장된 불변식이 아니다 → 재조회 경로(§4.3)를 열어 두고, 단조성
  위반을 관측하면 증거로 남긴다(§4.5).

## 3. tick 정정 5 → 2 (전제 항목)

| 트리 | 처분 | 이유 |
|---|---|---|
| CP-3 tenant 트리 | **이 웨이브의 첫 PR 에서 `tick_size: 2`** · 헤더에 「운영자 승인 2026-10-08 · 시행세칙 제4조의9 제2호 · 등급 R · 브로커 정황 = P-VL band 격자(PR #881)」 | band 가 들어오면 tick 검사가 살아난다. 5 로 두면 mini 정상 호가(0.02 격자 중 0.05 의 배수가 아닌 가격)가 전부 INADMISSIBLE |
| 상주 `paper` 트리 | **보류 — paper 채택과 함께** | band 를 켜지 않는 한 tick 은 판정에 닿지 않는다(§1 술어 순서: band `None` → tick 전에 `UNKNOWN`). 바꾸면 정책 digest → `safety_activation.yaml::members` 갱신 + 런북 §7.10 6 의 두 번 부팅 의무만 생기고 행동 변화는 0 |
| `config/execution.yaml` 레지스트리 | 변경 없음(이미 0.02) | — |

테스트: tenant 단언에 `tick_size == 2` + 헤더 출처 문자열 핀. 레드 증명 = 값을 5 로 되돌리면 실패 · 출처 문장을 지우면 실패.

## 4. band (i) — 설계

### 4.1 원천 선언 (정책 인스턴스 `_runtime.band_source`)

ADR-002-019 §9 는 「브로커 조회는 브로커 증거일 뿐, 활성 정책이 사실·원천 의미·bound·독립성·실패 응답을 **명시하지
않으면** 혼자서 현재 admissibility 를 증명하지 못한다」고 적는다. 그래서 원천은 코드 상수가 아니라 정책 인스턴스에 둔다:

```yaml
_runtime:
  band_source:            # null = 끔(상주 paper 기본값; 오늘의 거동 그대로)
    kind: "kis_quote_get"
    tr_id: "FHMIF10000000"
    instrument: "A05610"            # 렌더가 채운다 — 최상위 scope.instruments 의 유일 원소와 같아야 함(§4.4b)
    upper_field: "futs_mxpr"
    lower_field: "futs_llam"
    basis_field: "futs_sdpr"        # 증거로만 기록 — 판정에 쓰지 않음
    price_scale: 100                # 아래 _runtime.price_scale 과 같아야 함
    timeout_ms: null                # 운영자 채택 대상 제안값(출처 없음 — 아래 참고); null 이면 band_source 를 켤 수 없음
    bound: "trading_date_kst"       # 거래일이 바뀌면 무효(§4.4a)
    read_on: ["boot", "phase_change"]
    failure: "unknown"              # 읽기·검증 실패 = band None = 커널 UNKNOWN
```

**가격 척도의 비교 대상(리뷰 M2).** 오늘 정책의 ×100 척도는 **헤더 주석에만** 있고 기계가 읽는 키가 없다(`grep
price_scale` 0건). `critical_input_policy.yaml:87-100` 은 가격 필드를 `unit: KRW, scale: "minor"` 로 적어 「지수 포인트
×100」과 어긋나기까지 한다. 그래서 `_runtime.price_scale: 100` 을 **정책 키로 새로 선언**하고(헤더 주석이 아니라), band
원천의 `price_scale` 과 CP-3 §5 3 ③ 생산자 계약의 가격 척도가 **둘 다 이 키와 같아야** 부팅한다. ③ 계약이 생기기 전에는
③ 쪽 대조를 「미결」로 증거에 남기고 band 원천은 켜지 않는다(§5). `critical_input_policy.yaml` 의 `KRW/minor` 표기 불일치는
별도 정정 대상으로 등재만 한다(이 웨이브 범위 밖).

**`timeout_ms` 는 출처 있는 값이 아니다(재리뷰 LOW).** 이 디렉터리는 모든 값에 승인 출처 인용을 요구한다
(`config/tos_runtime/README.md`). P-CA 09-30 의 모의 `ReadTimeout`(`… read timeout=20.0`)은 상한이 **필요하다**는 전례일 뿐
값의 출처가 아니다. 그래서 템플릿은 `null`(named-TBD) 로 두고, 켜는 배포에서 운영자가 값을 채택한다 — 제안 5000 ms 는
「부팅 경로를 막지 않을 만큼 짧고 모의 왕복 실측(수백 ms)보다 충분히 긴 값」이라는 근거뿐인 **제안**이다.

**GET 의 종목은 한 출처에서만 온다(재리뷰 H1 부분).** 요청의 `FID_INPUT_ISCD` 는 **`band_source.instrument` 하나**다.
`kis_quote` transport 설정에도 `instrument` 필드가 있으므로(`transport/kis_quote/config.py`), 그 transport 설정(band 원천이 켜진
배포에 있으면 두 값이 같아야 부팅한다 — 출처가 둘인 채로 어긋나는 것을 로더가 막는다.

로더 규칙 — **전부 `band_source` 가 non-null 일 때만 적용**되고, 위반은 이름을 밝혀 부팅 거부:
`_model_view.shape_constraints.price_min/max` 가 리터럴(원천 둘) · `band_source.instrument` ≠ 최상위 `scope.instruments` 의
유일 원소(로더가 `LoadedVenuePolicy.scope.instrument` 로 노출, `_venue_policy_loader.py:133,168`; §4.4b) · transport 설정의
`instrument` 가 있고 `band_source.instrument` 와 다름(§4.4b) · `_runtime.price_scale` 부재 또는 `band_source.price_scale` 과
불일치 · `failure` 가 `"unknown"` 이 아님 · `read_on` 이 위 두 토큰의 부분집합이 아님 · `timeout_ms` 가 양의 정수가 아님 ·
transport 설정 부재. `_runtime.band_source` 키가 **없으면 null 과 같고**, 그때는 `_runtime.price_scale` 도 요구하지 않는다
(재리뷰 MEDIUM — 무조건 요구하면 상주 paper 트리의 `_runtime`(`instrument_class`·`quantity_unit`·`currency` 뿐)이 PR-2 머지
다음 08:45 에 ABORT 한다).

### 4.2 읽기 (`tos_runtime/venue/band_source.py`, 신규)

- 기존 `kis_quote` transport 의 host seal(MOCK `rest_base` 정확 일치)과 `KisTokenLifecycle` 을 **재사용**한다 — 새 HTTP
  클라이언트·새 토큰 경로를 만들지 않는다.
- 응답 → `BandObservation(instrument, price_min, price_max, trading_date, raw_payload_digest, source_continuity_id, as_of_ms)`.
  `instrument` 는 요청의 `FID_INPUT_ISCD`(= `band_source.instrument`)이고 응답 본문에는 계약 식별자가 없다 — 그래서 계약
  결속은 응답 검사가 아니라 **로더 규칙**이 맡는다(§4.4b). ⚠ `trading_date` 는 **응답에서 온 값이 아니라 로컬 도장**이다 — GET 시점의
  `calendar/owner.py::trading_date_now()`(형식 `YYYYMMDD`, `calendar/phase.py::trading_date_at`). 그래서 이 도장은 「메모리에
  들고 있는 낡은 band」만 잡고 「낡은 응답」은 잡지 못한다(§2 측정되지 않은 전제 · §4.4a).
  변환은 `Decimal` 정확 곱(`× price_scale`)이고 정수가 아니면 거부한다(반올림 금지 — 커널 §12 「silent rounding」 원칙과
  같은 이유).
- 검증 셋(하나라도 실패하면 `None` + 증거): `0 < price_min < price_max` · 두 값 모두 **정책 tick 의 배수**(tick 5 인
  트리에 켜면 여기서 걸린다 — §3 의 정정이 전제인 이유가 코드로도 드러난다) · `rt_cd == "0"`.
- `source_continuity_id` 는 프로세스 부팅마다 새로 만들고(ADR-002-019 §9: 재시작·재접속·자격 교체는 새 연속성), 토큰이
  재발급되면 바꾼다.

### 4.3 서비스 변경 (`VenueConstraintService`)

- 생성자에 선택 인자 `band_reader: Callable[[], BandObservation | None] | None = None` · `trading_date_reader:
  Callable[[], str | None] | None = None`. 둘 다 `None` 이면 **오늘과 바이트 단위로 같은 거동**(회귀 테스트로 고정).
- `shape_constraints` 를 속성(property)으로 바꿔 **유효 제약**을 돌려준다: band 가 있으면
  `policy.shape_constraints.model_copy(update={"price_min": …, "price_max": …})`, 없으면 정책 그대로. 소비자 셋(§1)은
  이 속성을 이미 읽으므로 수정이 필요 없다. step 3 결정과 step 15 재평가는 **그 사이에 재발행이 없을 때** 같은 객체를
  본다. 재발행이 끼면 게이트웨이 item 11 은 `decision.snapshot_digest` 를 결속하지 않고 **현재** 스냅샷·제약으로 다시
  접는다(`gateway.py::_check_venue`) — 현재 band 가 이기고 결정도 ADMISSIBLE 이어야 하므로 보수 방향이다.
- 읽는 시점: 첫 스냅샷 발행 · phase 변화로 인한 재발행. 그 외 시점에는 GET 하지 않는다(모의 시세 rate limit 1.0 rps —
  `config/tos_runtime/paper/marketfeed.yaml:101-103`, 프로브 P-13).
- band 가 바뀌면(값 · 거래일 · 연속성 중 하나) **새 Constraint Generation** 으로 스냅샷을 재발행한다 — ADR-002-019 §18
  이 price-band 변화를 material change 로 열거한다. 지금의 `snapshot()` 은 phase 변화만 보므로 이 조건을 더한다.
- 스냅샷의 세 필드: `critical_input_snapshot_digest` = band 관측 레코드의 정규화 digest · `source_continuity_id` =
  §4.2 · `max_age` = `"trading_date_kst:<YYYYMMDD>"`(런타임 `trading_date_at` 형식 그대로; 커널은 이 필드를 불투명 문자열로
  정의한다). 결정은 스냅샷 digest 를 결속하므로 band 가 결정에 **간접 결속**된다. 커널 레코드 필드 추가 0.
- ⚠ **스탠드인(리뷰 M3).** 커널 docstring 은 `critical_input_snapshot_digest` 를 「CII provenance binding (capsule-owned;
  venue binds the digest, §3.5)」로 정의한다(`tos/src/tos/venue/records.py:489-490`). 여기에 넣는 것은 커널
  `CriticalInputSnapshot`(`tos/src/tos/capsule/snapshot.py`)의 digest 가 **아니라** 런타임 band 관측 레코드의 digest 다.
  기계적으로는 커널 변경 0 이지만(이 필드의 소비자는 레코드 자신뿐) **의미는 런타임이 덧씌운 것**이다. 그래서 정책 헤더와
  증거 행에 `egress_coordinates.yaml::capsule_terminus_fields` 와 같은 관용구로 「스탠드인」이라고 적고, 근거로 상위 설계
  §6(band = Critical Input 사실, ADR-002-019 §9)을 인용하며, 「band 관측을 정식 CriticalInputSnapshot 으로」를 §6 (B) 옆에
  GOV-001 후보로 등재한다.
- 재발행은 **상태 전이에서만** 한다(리뷰 L3): band 있음 → 없음, 없음 → 있음, 값·거래일·연속성 변화. band 가 이미
  `None` 인데 거래일이 `None` 인 상태(장 밖)에서 `snapshot()` 이 불릴 때마다 재발행하면 constraint_generation 이 부풀어
  오른다.

### 4.4a 거래일 결속 가드 — 이것이 실패하는 구체적 입력

**가려진 절 주의(리뷰 M1).** v1 의 입력(「10-08 band 를 들고 10-09 까지 부팅 없이」)은 이 가드를 지워도 막힌다 —
`calendar/phase.py:117-130 trading_date_at` 이 08:45~15:45 창 밖에서 `None` 을 돌려 15:45 에 band 가 떨어지고,
`read_on: phase_change` 가 08:45 에 다시 읽기 때문이다. 두 겹이 가리는 절은 판별에 기여하지 않는다(#838). 그래서 입력을
**그 둘을 걷어낸 상태**로 다시 쓴다.

**입력(운영에서 도달 가능한 형태, 재리뷰 M1 부분)**: D 일 장중에 band 를 읽은 프로세스가 15:45~익일 08:45 의 `None` 창
동안 `snapshot()` 을 **한 번도 부르지 않는다**(장 밖엔 틱이 없거나 호스트가 절전). D+1 에 처음 불릴 때 직전 스냅샷의
phase 와 현재 phase 가 둘 다 정규장이면 phase 변화가 없어 재조회가 일어나지 않는다 — 이때 band 를 떨어뜨리는 것은 **거래일
비교 하나뿐**이다. 값은 **가상**이다: D 상한 1159.18(10-08 `A05610` 실측 상한을 D 의 값으로 빌림, `P-VL-20261008T010644Z.json`)
· D+1 기준가가 1000.00 이라 실제 상한 1080.00 이라고 **가정**하면, 가격 1100.00 의 매수는 낡은 band 로는 ADMISSIBLE,
거래소에서는 거부. 단위 테스트는 이 시퀀스를 그대로 재현한다(D 도장 관측 → `snapshot()` 호출 없이 거래일 진행 → 같은
phase 로 D+1 첫 호출).
**가드**: `snapshot()` 의 **첫 `if`(tick generation 캐시 조기 반환) 앞에서** band 의 `trading_date` 를 현재 거래일과 비교하고,
다르거나 둘 중 하나가 `None` 이면 band 를 버리고(상태 전이일 때만) 재발행한다 → `UNKNOWN`. 캐시 반환 뒤에 두면 tick
generation 이 그대로인 동안 검사가 건너뛰어진다. **레드 증명**: 비교를 지우면 위 입력이 ADMISSIBLE 로 통과 → 테스트 실패.
비교를 캐시 반환 뒤로 옮겨도(같은 tick generation 으로 호출) 실패해야 한다.

**잔여 위험(가드 밖)**: 이 가드는 로컬 도장끼리 비교하므로 §2 의 「08:45 직후 모의가 전일 band 를 내준다」는 잡지 못한다.
v1 은 이를 **측정되지 않은 전제**로 등재하고, 첫 켜기(§9 3) 세션의 `VENUE_BAND_OBSERVED` 행을 그 측정으로 쓴다 —
`stage_hint`(제56조 1단계 산식과의 일치)가 거짓이면 그날 band 를 버리는 응답 측 검사를 **그 측정 뒤에** 넣을지 판단한다
(측정 전에 넣으면 기준가 판별이 무정보인 날 모든 band 를 버릴 수 있다).

### 4.4b 계약 결속 가드 — 이것이 실패하는 구체적 입력 (리뷰 H1)

**입력**(이 문서의 증거 그대로, `docs/broker-profiles/evidence/2026-10-08-cp3-venue-limits/` 의 `P-VL-20261008T010822Z.json`
`measurements.l1_quote_fields.values`): `A05610` band 987.46/1159.18 · `A05611` band 990.48/1162.72. 둘 다 0.02 격자 ·
`0 < min < max` · `rt_cd = 0` 이라 §4.2 검증 셋을 **전부 통과**한다. `A05610` 정책에 `A05611` band 가 붙으면 가격 1160.00
의 매수는 ADMISSIBLE, 거래소에서는 거부. ADR-002-019:357 이 「wrong contract/account mapping」을 공통 원인으로 적는다.
**왜 지금**: 10-12 롤에서 `scope.instrument` 가 새 정책 generation 으로 바뀐다. `kis_quote` transport 설정의 `instrument`
는 poll 시점에만 확인되고 venue 정책 scope 와는 대조되지 않는다(기존 scope 대조는 정책 ↔ construction 뿐,
`compose/_venue_wiring.py:127-153 _cross_check_scope`).
**가드 둘(둘 다 로더)**: `band_source.instrument` ≠ 정책 `scope.instruments` 의 유일 원소 → 부팅 거부 · transport 설정의
`instrument` ≠ `band_source.instrument` → 부팅 거부. v2 의 「런타임 응답 측 재확인」은 **삭제**했다 — GET 의 종목이
`band_source.instrument` 하나에서 오므로 로더가 이미 확인한 값을 다시 비교하는 가려진 절이었다(재리뷰). **레드 증명**:
(1) `A05610` 정책 + `band_source.instrument: A05611` → 첫 검사를 지우면 부팅되어 `A05611` band 로 1160.00 이 ADMISSIBLE ·
(2) `band_source.instrument: A05610` + transport `instrument: A05611` → 둘째 검사를 지우면 부팅된다.

### 4.5 증거

- 새 kind `VENUE_BAND_OBSERVED`(런타임 어휘, 커널 `EvidenceKind` 아님 — `service.py` 의 기존 관용구): GET 마다 한 행 —
  성공이면 `instrument`·`price_min/max`·`basis`·`trading_date`·`raw_payload_digest`·`continuity`·`stage_hint`(§2 의 1단계 산식과의
  일치 여부, 판정 아님), 실패면 `reason`(검증 셋 중 어느 것인지 · transport 오류 · `rt_cd`).
- `VENUE_SNAPSHOT_ISSUED` 행에 `band_digest` 를 더하고 `absent_fields` 는 실제로 빈 필드만 남긴다. 이 키와 아래
  `VENUE_POLICY_BOUND` 의 새 키는 **`band_source` 가 non-null 일 때만** 나온다(리뷰 L2) — 그래야 끈 배포의 행이 오늘과
  바이트 단위로 같다(§8 1).
- 같은 거래일에 band 가 **좁아지는** 관측은 별도 플래그 `narrowed_intraday: true` 로 남긴다(§2 단서의 반증 관측 자리).
- `VENUE_POLICY_BOUND` 행에 `band_source` 블록의 정규화 digest 를 더한다 — §6 (B) 의 공백을 증거로라도 메운다.

### 4.6 실패 응답

모든 실패는 `band None` → 커널 `UNKNOWN` → 송신 0 이다. 즉 이 웨이브의 최악은 **오늘과 같은 상태**이고, 새로 열리는
fail-open 경로는 「틀린 band 를 믿는 것」뿐이다. 그 경로를 막는 것은 **셋** — §4.2 검증 셋(척도·순서·격자·`rt_cd`) ·
§4.4a 거래일 결속 · §4.4b 계약 결속. v1 은 둘이라고 적었고 계약 결속이 빠져 있었다(리뷰 H1). 셋으로 막지 못하는 것은
§4.4a 의 잔여 위험(낡은 **응답**) 하나이고, 측정되지 않은 전제로 등재돼 있다. 단 이 「셋」은 **켜기 전제** 하나와
함께일 때만 참이다 — 가격 척도가 ③ 생산자 계약과 합의되기 전에는 `band_source` 를 켜지 않는다(§4.1 가격 척도 문단 · §5).
척도가 어긋난 채 켜면 band 와 가격이 다른 단위로 비교된다.

## 5. 어느 배포에서 켜나

| 배포 | `band_source` | 이유 |
|---|---|---|
| 상주 `paper` | **null 유지** | 관측이 합성값(§1, close 4,499,000 = 44,990 포인트대)이라 실제 band(~987~1159)를 켜면 **모든** 주문이 INADMISSIBLE — 합성 가격과 실제 band 의 조합은 아무것도 검증하지 않는다 |
| CP-3 tenant (LONG) | **CP-3 §5 3 ③(실시간 필드 생산자)이 실제 가격을 흘린 뒤에** 켠다 | 같은 이유. 그 전에 켜면 위와 똑같이 전부 INADMISSIBLE 이다. 코드와 tenant tick 정정은 먼저 머지해도 된다(null 이면 무동작) |
| 단위·통합 테스트 | 가짜 transport 로 켬 | §8 |

## 6. 운영자 확인 (새로 드러난 사실 둘) — ✅ 2026-10-08 둘 다 권고대로 승인

(A) **런타임 첫 외부 호출.** 오늘 paper 런타임은 소켓을 열지 않는다(§1). (i) 는 그 런타임이 MOCK 도메인에 GET 을 하고,
`.env.mock` 앱키로 토큰을 받는다는 뜻이다. 이 앱키는 상주 세션 래퍼와 프로브가 공유한다(N-15: 토큰 발급 rate limit).
읽기 횟수는 거래일당 1~3회(부팅 + phase 변화)로 작지만 **성질이 바뀐다**. 권고: 그대로 (i) 로 간다 — transport 와 토큰
수명 관리가 이미 런타임에 있고(§1), 런타임이 원 응답의 digest 를 직접 결속할 수 있는 길은 이것뿐이다. 대안은 §7 (i-b).

(B) **`_runtime.band_source` 는 활성화 digest 밖이다.** 활성화는 커널 `canonical_digest`(`_model_view`) 만 대조한다.
`_runtime` 의 다른 블록(`wire_codec` 등)도 같은 처지라 새 공백은 아니지만, band 원천은 판정에 닿는 값이다. 권고: 이번엔
§4.5 처럼 `VENUE_POLICY_BOUND` 증거에 digest 를 남기고, 원천 선언을 커널 covered 필드로 올리는 것은 GOV-001 절차의
후보로 등재만 한다. 같은 후보 목록에 §4.3 의 스탠드인(band 관측을 정식 `CriticalInputSnapshot` 으로)을 함께 올린다.

**처분 (운영자, 2026-10-08)**: (A) 수용 — (i) 그대로 런타임 GET. (B) 수용 — 증거 digest + GOV-001 후보 등재만.

## 7. 기각한 대안

| 대안 | 이유 |
|---|---|
| (ii) 규정 계산만 | 2·3단계 확대를 못 본다. 10-08 운영자 선택이 (i) 먼저. (ii) 는 §4.5 의 `stage_hint` 로 대조 자리만 둔다 |
| (i-b) GET 을 외부 생산자(③)가 하고 band 를 journal 행으로 전달 | 런타임은 소켓 없이 유지되지만, 런타임이 원 응답을 보지 못해 §9 의 raw payload digest·연속성을 **생산자의 주장**으로만 받는다. ③ 이 아직 설계 전이라 그 계약에 band 를 얹는 것은 순서가 뒤집힌다. ③ 설계 때 다시 볼 후보로 남긴다 |
| `VenueConstraintSnapshot` 에 band 필드 추가 | 커널 레코드 변경(GOV-001). 기존 세 필드로 결속이 된다(§4.3) |
| 정책 리터럴 band 를 매일 재렌더 | 일별 값이라 정책 generation 이 매일 바뀌고 활성화 갱신이 매일 필요. 장중 확대도 못 본다 |
| 장중 주기적 재조회 | §2 단조성으로 부팅 1회가 보수 방향으로 안전하다. 확대를 반영하려면 그때 설정 키로 추가(이번엔 `read_on` 두 토큰만) |
| 상주 paper 에 켜기 | §5 |

## 8. 테스트 (레드 증명은 절 단위)

1. `band_reader=None` 회귀(그리고 `_runtime.band_source` 키 부재 = null): 오늘의 스냅샷·결정 증거 행이 바이트 단위로
   같다 — §4.5 의 새 키는 이때 나오지 않는다. **상주 paper 의 실제 `venue_constraint_policy.yaml`**(`_runtime` 에
   `price_scale` 없음)이 그대로 로드되는 것도 여기서 단언한다.
2. band 주입 → 유효 제약의 `price_min/max` 가 채워지고 step 3 결정과 게이트웨이 item 11 이 **같은 값**을 본다
   (`compose` 통합 테스트 — stage 와 context 가 같은 객체를 읽는지).
3. §4.2 검증 셋 각각 한 건씩: 비정수 척도 · `min ≥ max` · tick 격자 밖(tick 5 + 0.02 격자 band) · `rt_cd ≠ 0` → 전부
   `None` + `VENUE_BAND_OBSERVED.reason`.
4. §4.4a 거래일 가드 — §4.4a 의 도달 가능한 시퀀스(장 밖 무호출 → 같은 phase 로 D+1 첫 호출). 비교 삭제 → red · 비교를 캐시 조기
   반환 뒤로 이동 → red.
4b. §4.4b 계약 가드 — 레드 증명 둘(§4.4b): scope ↔ `band_source.instrument` 검사 삭제 → red · transport ↔
   `band_source.instrument` 검사 삭제 → red. band 값은 10-08 P-VL 실측(`A05611` 990.48/1162.72).
4c. 재발행은 전이에서만 — 장 밖에서 `snapshot()` 을 N 번 불러도 constraint_generation 이 1 만 오른다.
4d. **`band_source` 가 켜진 배포에서만** `_runtime.price_scale` 부재·불일치 → 부팅 거부(끈 배포의 부재는 §8 1 이 통과를
   단언) · `timeout_ms: null` 로 켜면 부팅 거부 · 부팅 GET 이 `timeout_ms` 를 넘기면 `None` + `reason`.
5. band 변화 → 새 Constraint Generation (§18) — phase 동일 · band 값만 다른 두 읽기에서 재발행이 일어나야 함. 조건을
   지우면 red.
6. 로더 거부 전부(§4.1 — 원천 둘 · 계약 · 척도 · `failure` · `read_on` · `timeout_ms` · transport 부재).
7. host seal: `band_source` 가 켜진 배포에서 transport `rest_base` 가 REAL 이면 부팅 거부(기존 `kis_quote` seal 재사용
   증명).
8. 같은 거래일 축소 관측 → `narrowed_intraday` 플래그.

## 9. 순서 · 핸드오버

1. **PR-1 (tenant tick)**: tenant 트리 `tick_size: 2` + 헤더 + 단언(§3). tenant 트리 PR 이 머지된 뒤에.
2. **PR-2 (runtime)**: §4 전부 + §8 테스트. `tos/runtime/src/tos_runtime/` 를 바꾸므로 **같은 PR 에서
   `expected_code_digest` 재도출**(`config/tos_runtime/paper/release.yaml` — 재도출하지 않으면 상주 세션이 다음 08:45 에
   ABORT 한다; 주석만 바꾼 PR 도 예외 없음). 상주 paper 의 `band_source` 는 null 이라 행동 변화 0 을 §8 1 이 증명한다.
   커널 무변경이므로 `tos-gate` 의 커널 digest 는 그대로여야 한다.
3. **켜기**: CP-3 §5 3 ③ 이 tenant 에 실제 가격을 흘린 뒤, tenant 정책에 `band_source` 를 채우고 활성화 갱신 → 첫 세션의
   `VENUE_BAND_OBSERVED` 행을 10-08 설계 §5 L2 의 ① 샘플 판정에 쓴다.
4. (ii) 대조: 3 이후 `stage_hint` 가 며칠 모이면 별도 판단.

운영자 확인 §6 (A)·(B) 는 2026-10-08 승인됐다. 남은 운영자 사안은 §9 3 의 켜기 시점(③ 생산자 이후)뿐이다.
