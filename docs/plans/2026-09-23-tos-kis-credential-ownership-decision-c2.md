# C-2 — KIS 자격증명·토큰 소유권 결정 (F-2 처분) · 2026-09-23

- 작성: 2026-09-23 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 측정 시점 main **`c1c9bffa`**
- 상위: `docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` §4 W-C **C-2** · §2 결정 6
  (「F-2 는 코드 전에 결정이 먼저」) · 원 발견 `docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md` §7.2 **F-2**
- 운영자 처분(2026-09-23): **F-3(별도 KIS 앱 등록)은 이 문서의 결정 뒤에 판단한다.**
- 성격: **결정 문서.** 코드는 결정이 난 뒤 별도 PR. C-2 종료조건 = 「선택지 3개 이상과 각각의 노출 표면을
  **줄 수로** 비교 · 결정 후 코드」(상위 §4 W-C).

## 0. 한 줄 요약

KIS 인증 자격증명을 읽는 곳이 지금 **세 모듈**(주문 전송·토큰 수명주기·시세 인테이크)이고, 같은 모의 앱키에
대해 **토큰 수명주기 인스턴스가 둘** 생긴다. 네 번째 소비자인 브로커 증인은 **평문 문자열을 돌려달라는**
다른 모양의 Protocol 을 요구해 배선되지 못하고 있다. 권고는 **(C) 자격증명 하나당 소유자 하나** —
`KisCredentialSession` 이 수명주기와 custody 를 소유하고, 소비자는 **한 호출을 감싸는 `with` 블록 안에서만**
토큰·키·시크릿을 받는다. 이 결정은 **F-3 을 요구하지 않는다**(§5).

## 1. 실측 — 지금 무엇이 어디서 자격증명을 만지는가 (main `c1c9bffa`)

### 1.1 평문이 실체화되는 줄

| # | 위치 | 무엇 | 수명 |
|---|---|---|---|
| L1 | `tos/runtime/src/tos_runtime/transport/kis_mock/token.py:207-208` | 토큰 발급 — custody 에서 키·시크릿 로드 | `with` 블록 = `issue_token` 호출 1회 |
| L2 | `tos/runtime/src/tos_runtime/transport/kis_mock/adapter.py:379-380` | 주문 전송 — 같은 두 scope 로드 | `with` 블록 = `post_order` 1회 |
| L3 | `tos/runtime/src/tos_runtime/transport/kis_quote/adapter.py:383-384` | 시세 조회 — 같은 두 scope 로드 | `with` 블록 = `get_quote` 1회 |
| L4 | `tos/runtime/src/tos_runtime/transport/kis_mock/client.py:202-203` · `:253-254` · `:299-300` | `appkey`·`appsecret` 를 `bytes → str` 디코드해 HTTP 헤더에 넣음(각 두 줄) | 헤더 dict = 요청 1회 |
| L5 | `tos/runtime/src/tos_runtime/recon/witness_kis.py:349-351` | 증인 — `app_key_header()`/`app_secret_header()` 가 **`str` 을 반환**해야 함 | 반환된 `str` 은 **호출자가 버릴 때까지**(불변 객체라 영점화 불가) |

L4 는 어느 선택지에서도 남는다 — KIS 는 **모든** 인증 호출에 `appkey`/`appsecret` 헤더를 요구하고(`client.py:238` 주석),
HTTP 헤더는 `str` 이다. 상위 F-2 가 이미 적은 제약이다: **평문은 어느 선택지에서도 요청마다 실체화된다.** 질문은
「누가 로드하고, 얼마나 오래 들고 있고, 몇 군데서 로드하는가」뿐이다.

### 1.2 같은 앱키에 토큰 수명주기가 둘

- `adapter.py:210` — `KisMockTransport.__init__` 이 자기 `KisTokenLifecycle` 을 만든다.
- `kis_quote/adapter.py:284` — `KisQuoteObservationIntake.__init__` 도 자기 것을 만든다.
- 두 곳 모두 scope `kis_mock.app_key`/`kis_mock.app_secret` — 문자열 정의는 **세 곳**이다
  (`compose/_transport_wiring.py:102-103` · `kis_quote/adapter.py:174-175` · custody 프로비저닝 허용 목록
  `custody/file_custody.py:110-111` `PROVISIONED_SCOPES`). 셋째는 custody 가 어떤 scope 를 허용하는지의 선언이라
  어느 선택지에서도 남는다.

두 인스턴스는 서로의 발급 시각을 모른다. 브로커 규칙은 **앱키당 토큰 재발급 1분당 1회**
(`docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:2176-2182`, 공식 문서 인용)이고, 실측으로
5 s 간격 재발급은 **HTTP 403**(`P-15-20260911T002231Z.json`, t3 README 2026-09-11 행)이었다. 따라서 주문
전송과 시세 인테이크가 **함께 구성되는 순간**(모의 스코프 + `intake_kind: kis_quote`) 한쪽의 첫 발급이
다른 쪽 발급 직후에 나가 거부되고, 그쪽은 `token_reissue_min_interval_s` 쿨다운 동안 `TokenStale` 을 낸다.
**지금 드러나지 않는 이유는 둘을 함께 구성한 배포가 아직 없어서다**(A-5 는 SYNTHETIC 스코프 · 로컬 부팅).

### 1.3 증인은 다른 모양을 요구한다

`KisWitnessTokenSession`(`witness_kis.py:138-187`)은 `access_token() -> str` 과
**`app_key_header() -> str` · `app_secret_header() -> str`** 을 요구한다. 증인은 custody 를 쥐지 않기로
설계됐고(모듈 독스트링 「no token/credential lifecycle owned here」), 그 결과 평문 `str` 을 **메서드 반환값으로**
받는다(L5). 프로덕션 구현체는 **0개** — `app_secret_header` 를 정의한 곳은 Protocol 자신과 테스트 더블
`tos/runtime/tests/recon/_witness_kis_fakes.py:30,44` 뿐이다. `KisStockBrokerWitness(` 생성부도 테스트 2 파일뿐
(`test_witness_kis.py:70,328` · `test_witness_kis_reconciliation_pin.py:214`) — **compose 에 배선되지 않았다.**

## 2. 선택지

셈 기준(§3 표의 열):

- **로드 지점** = `custody.load(<KIS scope>)` 를 부르는 모듈 수(L1~L3 형).
- **평문 반환** = 평문 키·시크릿을 **함수 반환값으로** 모듈 경계 밖에 내보내는 메서드 수(L5 형 — `with` 로 수명이
  묶이지 않는 것).
- **수명주기/앱키** = 한 배포에서 같은 앱키에 대해 동시에 존재할 수 있는 `KisTokenLifecycle` 인스턴스 최대 수.
- **scope 상수 사본** = `tos_runtime` 안의 `"kis_mock.app_key"`(또는 앱을 나누면 그 앱의 scope) 문자열 정의 수.
  custody 허용 목록(`file_custody.py:110-111`) 한 벌은 모든 행에 포함한다.

### (A) 얇은 어댑터 — 증인 Protocol 그대로, 어댑터가 수명주기 + custody 를 감싼다

`KisWitnessTokenSession` 구현체를 compose 에 하나 둔다: `access_token()` 은 세 번째 `KisTokenLifecycle` 에 위임,
`app_*_header()` 는 custody 에서 로드해 `.decode()` 한 `str` 을 반환.

- 상위 F-2 가 이미 기각 근거를 적었다: 「감쌀 대상이 없어 adapter 가 **제2의 자격증명 로딩 경로**가 된다」.
- 평문 `str` 이 페이지마다 반환되고, `with` 가 반환값의 수명을 묶지 못한다.

### (B) 증인이 W2/T1 규율을 따른다 — 각 소비자가 custody 를 쥔다

증인 Protocol 을 바꿔 `CredentialCustody` + scope 이름 + 토큰 소스를 주입받고, `kis_quote/adapter.py:371-392`
와 같은 **호출 1회를 감싸는 `with`** 안에서 키·시크릿을 읽게 한다.

- 평문 반환은 0 이 된다. 그러나 로드 지점이 **네 모듈**로 늘고, 수명주기 인스턴스도 소비자마다 하나 — 1.2 의
  재발급 충돌이 **셋 사이**로 커진다.

### (C) 자격증명 하나당 소유자 하나 — `KisCredentialSession` · **권고**

새 클래스 하나. **위치는 방화벽이 정한다**: 증인 모듈은 R1 에서 `tos_runtime.recon` 형제 모듈만 import 할 수
있다(`witness_kis.py:62-68` — `tos_runtime.transport.kis_mock` import 불가). 그래서 둘로 나눈다.

- **구체 클래스** `KisCredentialSession` 은 수명주기 옆(`tos_runtime/transport/kis_mock/token.py` 또는 그 옆 모듈)에 둔다.
- **증인 쪽 Protocol**(`request_credentials()` 하나)은 `tos_runtime/recon/witness_kis.py` 에 남긴다 — 지금
  `KisWitnessTokenSession` 자리. 구체 클래스가 이 Protocol 을 **구조적으로** 만족하고, 둘을 잇는 것은 compose
  루트뿐이다. 증인 → transport import 간선은 생기지 않는다(구현 PR 의 방화벽 검사가 이를 확인한다).

```python
class KisCredentialSession:
    """한 KIS 앱키(= 한 custody scope 쌍 · 한 토큰 엔드포인트)의 유일한 소유자."""
    def __init__(self, *, lifecycle: KisTokenLifecycle, custody: CredentialCustody,
                 app_key_scope: str, app_secret_scope: str) -> None: ...

    @contextmanager
    def request_credentials(self) -> Iterator[KisRequestCredentials]:
        """토큰(ensure_token_string) + 키·시크릿 핸들을 `with` 안에서만 준다.
        블록을 나가면 핸들이 영점화된다 — L2·L3 이 지금 하는 것과 같은 수명."""
```

- compose 루트가 **앱키당 하나** 만들고, 주문 전송·시세 인테이크·증인이 **같은 인스턴스**를 주입받는다.
- 세 소비자는 custody 를 더 이상 쥐지 않는다 — `custody.load(<KIS scope>)` 는 이 클래스(와 그 안의 수명주기)만.
- 증인 Protocol 은 `KisWitnessTokenSession` 의 세 메서드 대신 `request_credentials()` 하나로 바뀐다. 증인은
  여전히 custody 를 쥐지 않는다(설계 의도 유지) — 다만 **평문을 반환값으로 받는 대신 `with` 안에서 받는다**.
- scope 상수는 compose 한 곳(+ custody 허용 목록 `file_custody.py:110-111`, 이것은 남는다).

### (D) 소비자별로 앱을 나눈다 — F-3 을 선행으로

주문 경로와 읽기 경로(시세·증인)에 **서로 다른 KIS 앱키**를 쓴다. 앱키가 다르면 토큰 재발급 창도 다르므로
1.2 의 충돌은 사라진다.

- 그러나 **증인의 평문 반환(1.3)은 그대로 남는다** — 모양의 문제이지 앱 개수의 문제가 아니다. (B) 또는 (C) 가
  여전히 필요하다.
- 읽기 전용 앱이 **브로커 측에서 실제로 읽기 전용인지는 근거가 없다** — 프로파일의
  `account_permission_semantics` 는 **`UNKNOWN`**(`KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:2555`). 권한 분리가
  아니라 **토큰 분리**만 확실하다.
- 외부 등록(운영자 계정 작업)과 custody scope 추가(`kis_mock_read.*`)가 따라온다.

## 3. 비교 (구현 후 기준 — 증인이 배선됐다고 가정)

| 선택지 | 로드 지점 | 평문 반환 | 수명주기/앱키 | scope 상수 사본 | 새 외부 의존 |
|---|---:|---:|---:|---:|---|
| 지금(main, 증인 미배선) | 3 | 0 | **2** | 3 | — |
| (A) 얇은 어댑터 | 4 | **2**(`app_key_header`·`app_secret_header`) | **3** | 3~4 | — |
| (B) 소비자별 custody | 4 | 0 | **3** | 3~4 | — |
| **(C) 단일 소유자** | **1** | **0** | **1** | **2** | — |
| (D) 앱 분리 + (C) | 1 | 0 | 1(앱키당) | 4(앱당 2) | KIS 앱 등록 · custody scope 2개 |
| (D) 앱 분리 + (A) | 4 | 2 | 2(읽기 앱키) | 5 | KIS 앱 등록 · custody scope 2개 |

도출(행마다):

- **지금**: 로드 = `token.py` · `kis_mock/adapter.py` · `kis_quote/adapter.py`. 수명주기 = 두 어댑터가 각자 생성.
  scope 사본 = `_transport_wiring.py` · `kis_quote/adapter.py` · `file_custody.py`.
- **(A)**: 지금 + 증인 어댑터 1 모듈(로드 +1 · 수명주기 +1 · 평문 반환 2). 어댑터가 compose 상수를 재사용하면 scope 3,
  자기 상수를 두면 4.
- **(B)**: 지금 + 증인 자신이 로드(+1), 증인 수명주기 +1, 평문 반환 0. scope 는 (A) 와 같은 이유로 3~4.
- **(C)**: 로드 = `KisCredentialSession` 1 모듈(그 안의 수명주기 포함). 수명주기 = compose 가 앱키당 1개.
  scope 사본 = compose 1 + `file_custody.py` 1.
- **(D)+(C)**: 앱마다 (C) — 로드 모듈은 여전히 1(같은 클래스), scope 는 앱당 compose 1 + custody 1.
- **(D)+(A)**: 주문 앱 = 주문 전송(로드·수명주기 1). 읽기 앱 = 시세 인테이크 + 증인 어댑터(로드 2 · 수명주기 2).
  토큰 발급 로드 `token.py` 포함 로드 모듈 4. scope = 주문 앱(compose 1 + custody 1) + 읽기 앱(시세 어댑터 1 +
  증인 어댑터용 compose 1 + custody 1) = 5.

평문이 HTTP 헤더 `str` 로 실체화되는 L4(`client.py` 세 곳 × 두 줄 + 증인 헤더 두 줄)는 모든 행에서 같다 — 표에서 뺐다.

## 4. 결정 — (C)

1. **(C) 를 채택한다.** 로드 지점 3 → 1, 수명주기/앱키 2 → 1, 평문 반환 0 유지, scope 상수 3 → 2(custody 허용 목록은 남는다). (A) 는 상위
   F-2 가 이미 기각했고 표가 그 근거를 수로 확인한다. (B) 는 평문 반환을 없애지만 1.2 의 충돌을 키운다.
2. **구현 PR 의 모양**(별도 PR, 이 문서 머지 뒤):
   - `KisCredentialSession` 신설 + `KisMockTransport`·`KisQuoteObservationIntake` 가 **자기 수명주기를 만들지 않고
     주입받게** 변경. 동작 보존 — 두 어댑터의 기존 테스트 스위트가 **무변경으로** 통과해야 한다(W2 추출이 쓴 기준).
   - `KisWitnessTokenSession` → `request_credentials()` 모양으로 교체. 테스트 더블 두 벌(`_witness_kis_fakes.py`)
     갱신.
   - compose 루트가 앱키당 하나 생성. 증인 **배선 자체**는 이 PR 범위 밖(모의 서버 핸드오버 아크 — A-5 는 로컬).
3. **핀 — 「이 가드가 실패하는 구체적 입력」:**
   - 주문 전송 + 시세 인테이크를 함께 구성하고, 가짜 클록으로 두 소비자의 첫 호출을 같은 밀리초에 → 가짜
     `issue_token` 호출 **정확히 1회**. 공유를 끊으면(각자 수명주기 생성) 2회 → RED.
   - AST/grep 핀: `tos_runtime` 안에서 `custody.load(` 를 KIS scope 로 부르는 모듈이 `KisCredentialSession`(과
     `KisTokenLifecycle`) 밖에 생기면 RED.
   - 증인: `request_credentials()` 블록 밖에서 핸들 `.value()` 를 부르면 custody 가 거부함을 핀(영점화 확인).

## 5. F-3 판정 — **이 결정은 별도 앱 등록을 요구하지 않는다**

- F-3 이 풀어 줄 수 있는 것은 1.2(같은 앱키의 재발급 충돌)뿐인데, (C) 가 **앱 하나로** 그것을 푼다.
- F-3 이 풀어 준다고 기대할 만한 「읽기 경로가 주문을 못 낸다」는 **근거가 없다**(`account_permission_semantics:
  UNKNOWN`). 근거 없이 등록하면 격리가 있다고 **믿게 되는** 것이 오히려 위험하다.
- 따라서 운영자 결정 ③ 의 「C-2 결정 후 판단」에 대한 이 문서의 답은 **「지금은 필요 없음」**이다. 다시 볼 조건:
  (i) KIS 가 앱 단위 권한 제한을 제공한다는 근거가 생기거나, (ii) 읽기 경로의 호출량이 앱키당 속도 한도
  (`hard_limits: {}` 미확립, 관측 구간 [1.0, 2.0) rps — 프로파일 `:1808-1810` · `:1840-1842`)를 주문 경로와 나눠 써야 할 만큼 커질 때.

## 6. 운영자 확인

| # | 항목 | 추천 | 실제 선택 |
|---|---|---|---|
| ① | (A)/(B)/(C)/(D) 중 선택 | **(C)** | **(C)** — 운영자 확정 2026-09-23 |
| ② | F-3 — 지금 등록하지 않음(§5), 재검토 조건 (i)·(ii) | **등록하지 않음** | **등록하지 않음** — 운영자 확정 2026-09-23 |

## 7. 착지 기록

- 2026-09-23: 결정 문서 PR #792(리뷰 1차 HIGH 1·MEDIUM 3·LOW 1 → 조치 → 2차 0건). 운영자가 ① (C) · ② F-3 미등록을 확정.
- 구현: 미착수 — 별도 PR 에서 §4.2 모양 · §4.3 핀 3종 재현 여부를 덧붙인다.
