# post-P0-1 currency — 증거 하네스 자기신고 제거 + Part-1 레지스터 열 갱신 (2026-08-06)

**성격**: 비규범 이행 기록. **새 승인 아님** — 2026-07-29 운영자(Bounds-Approver)가 이미 내린
P0-1 판정을, 그 판정을 아직 반영하지 못한 두 좌표에 뒤늦게 전파한다. 이 문서도, 이 편집도
어떤 게이트도 열지 않는다: ADR acceptance·restricted-live·production 권한 전부 불변.

---

## 1. 배경 — P0-1은 닫혔고, 두 좌표만 뒤처졌다

P0-1(Verification Profile profile-level 승인)은 2026-07-29 커밋 `53980b64`
("feat(tos-spec): operator gate decisions — P0-1 profile approval, ASS instance,
residual register", `2026-07-29T23:48:38+09:00`)로 닫혔다. 정본 아티팩트
`tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml` 실측:

| 필드 | 값 |
|---|---|
| `version` | `"2.1"` |
| `status` | `APPROVED` (profile-level, **scope-limited**) |
| `approved_by` | `["operator"]` |
| `effective_from` | `"2026-07-29"` |
| `review_due` | `"2027-01-29"` |
| 수치 키 총계 | 163 (bounds 84 + limits 79) |
| 승인된 키 | 146 |
| null 잔여 키 | **17** (broker bounds 10 = P0-2 대기, instance/architecture limits 6, `MIN_evidence_retention_ms`) — key-level UNAPPROVED·fail-closed 유지 |

즉 "profile은 승인되었으나 17키는 여전히 미승인"이 현재의 정직한 상태다. 그럼에도 다음
두 좌표가 "P0-1 열림"을 계속 주장하고 있었다.

### 1.1 stale 좌표 전수 (수정 전 file:line)

**(A) 증거 하네스 `tools/tos_evidence_run.py`** — 하드코딩 문자열 4곳:

| locus | 수정 전 내용 |
|---|---|
| `:181-182` | 주석 "The Verification Profile is PROPOSED, not approved — P0-1 is open." |
| `:183` | `VERIFICATION_PROFILE_VERSION = "2.1 (PROPOSED — P0-1 open)"` |
| `:1626` | `"approval_state": "PROPOSED — P0-1 (bounds approval) OPEN"` |
| `:1628-1632` | reason `"Recorded, not approved. VER §6 numeric bounds remain unapproved; no bound value is consumed by this run (bounds are hypothesis-injected, not hardcoded)."` |
| `:2805` | `"p0_1_bounds_approval": "OPEN"` |

`:1628-1632`의 "VER §6 numeric bounds remain unapproved"는 146키가 승인된 현재
사실과 다르다 — 미승인은 17키뿐이다.

**(B) Part-1 레지스터 `tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv`**
— `verification_profile_version` 열 **372셀 전부** `2.1-PROPOSED`.
기입 규약 정본은 `docs/plans/2026-07-29-tos-phase0-role-scheme-and-disposition.md:34`:
> `verification_profile_version` 열은 `2.1`(**승인 전이므로** PROPOSED 상태 병기)

괄호 안의 전제("승인 전")가 2026-07-29에 소멸했으므로, 규약 본문이 지정한 값 `2.1`이
현재 정직한 기입값이다. 이는 규약의 개정이 아니라 규약이 이미 조건부로 지정해 둔 값으로의
전이다.

---

## 2. 극성 분석 — stale 주장은 **보수 방향**이었다

이 항이 이 작업 전체의 위험 판정이다.

- stale 주장은 "승인되지 않았다 / 게이트가 열려 있다"였다. 실제는 "146키 승인, 게이트
  scope-limited 폐쇄"다. 즉 하네스는 **자신이 가진 권한을 과소보고**했다.
- 증거 패키지가 만드는 주장은 전부 **부정 방향**이다: `closes_evidence_item: false`,
  `register_status_moved_by_this_run: false`, `discipline_tag`("not a row PASS"),
  `p0_1_bounds_approval: OPEN`. 미승인 주장은 이 부정을 **더 강하게** 만들 뿐 약하게
  만들지 않는다.
- 따라서 **기존 증거의 유효성에는 영향이 없다**: 어떤 런도 stale 주장을 근거로 무언가를
  통과시키지 않았고, 오히려 실제보다 더 많은 잔여 게이트를 스스로 부과한 상태로 기록되었다.
  STATE-EV-001의 PASS(2026-08-06, `209295b2`)를 포함해 재검토·철회 사유는 없다.
- 반대 방향이었다면(승인되지 않은 프로파일을 APPROVED로 기록) 판정은 정반대였을 것이다.
  그래서 §3의 재설계는 fail-closed 극성을 **구조적으로** 강제한다.

**그러나 보수 방향이라고 무해한 것은 아니다.** 결함 클래스는 "정확성"이 아니라 "자기신고":
아티팩트가 바뀌어도 따라오지 않는 문자열이 사실로 읽히는 자리에 있었다. 같은 메커니즘이
반대 극성으로 재발하면 그때는 fail-open이다. 그래서 값을 고치는 것이 아니라 **값의 출처를**
고친다.

---

## 3. 하네스 설계 변경 — 자기신고 → 구조 파생

### 3.1 파생 함수

신설 `read_profile_approval(repo_root) -> dict` (`tools/tos_evidence_run.py:1559`).
하네스는 **이미** 이 파일의 sha256을 `profile_digest`로 기록하고 있었다. 같은 바이트에서
승인 메타데이터를 함께 읽으면 "기록된 주장"과 "봉인된 바이트"가 원리적으로 어긋날 수 없다.

파생 항목: `version` / `status` / `approved_by` / `effective_from` / `review_due` +
null 잔여 키 **동적 계수**(`bounds[*].value_ms is None` + `limits[*] is None`,
`_profile_null_key_census`, `:1534`).

보조:
- `_profile_unknown` (`:1514`) — fail-closed 레코드 생성자.
- `profile_version_reason` (`:1660`) — VER §3 필드의 `reason` 문장을 상태에서 파생.
  문장을 파생부 옆에 둔 것이 요점이다: **문장이 자기가 서술하는 상태보다 오래 살아남는 것**이
  이번 결함의 정확한 메커니즘이었다.

제거: 모듈 상수 `VERIFICATION_PROFILE_VERSION` — 미사용으로 남기지 않고 **삭제**했다
(팬텀 방지). 소스 전수 grep으로 부재를 고정한다(§3.4).

### 3.2 fail-closed 극성 (필수 요건)

`_profile_unknown` 반환 지점 **8곳** — 하나라도 성립하면 전 필드가
`PROFILE_APPROVAL_UNKNOWN = "UNKNOWN (fail-closed)"`:

1. 파일을 읽을 수 없음 (`OSError` — 부재·권한·디렉터리 전부 동일 판정)
2. YAML 파싱 예외 (모든 예외를 동일 판정으로 접음)
3. **중복 매핑 키** — `_NoDuplicateKeySafeLoader`가 거부 (아래 참조)
4. 문서가 매핑이 아님
5. `status`가 닫힌 어휘 `PROFILE_STATUS_VOCABULARY = ("PROPOSED", "APPROVED")` 밖 —
   **필드 부재(`None`)도 포함**
6. `version`이 사용 가능한 문자열이 아님
7. census가 **비었거나** 계수 불가능한 shape (§3.2.1)
8. `status: APPROVED`인데 `approved_by`가 비었거나 `effective_from`이 없음 —
   프로파일 **자신의** ratification 규칙이 둘 다를 요구하므로, 없으면 서명 없는 주장이다.

구조적 보증: 이 함수가 방출할 수 있는 유일한 승인 어휘는 **파일의 `status` 필드에서 온
문자열**이다. 하네스가 스스로 "APPROVED"를 만들어내는 경로는 없다.

**중복 키 거부**: PyYAML 기본은 last-wins라, `status:`가 두 줄이면 파서는 마지막 것을,
위에서 아래로 읽는 사람은 첫 번째를 본다. digest는 이 어긋남을 잡지 못한다(두 줄 다
봉인된 바이트 안에 있다). 그래서 어느 쪽으로도 해석하지 않고 **모호성 자체를 거부**한다.

**결정론**: wall-clock·난수·네트워크·환경변수 미사용. `sorted()` 고정 순서. 같은 바이트 →
같은 레코드.

### 3.2.1 census 비대칭 제거 — 과소 계수 = fail-open

census에서 위험한 방향은 **과소 계수**다. 어떤 키를 null로 인식하지 못하면 그 키는 조용히
승인 인구에 합류한다. 따라서 인식 못 한 shape는 그 키를 건너뛰는 것이 아니라 **census 전체를
중단**시킨다. 두 섹션을 **대칭으로** 검증한다:

- 어느 섹션도 비어 있을 수 없다 — "0 of 0 미승인"은 이 함수가 낼 수 있는 **가장 강한
  승인 주장**이며, 빈 파일이 그것을 만들어내는 것은 정확히 반대 극성이다.
- `bounds` 엔트리는 매핑이고 `value_ms`를 **가지고 있어야** 한다(키 부재 ≠ null 값).
- `limits` 엔트리는 `null` 또는 숫자여야 한다. 매핑/리스트가 오면 shape가 바뀐 것인데
  단순 `is None`은 그것을 "값이 있다=승인됨"으로 센다. (v1의 실제 결함이었다.)
- `bool`은 숫자에서 제외 — `True`는 밀리초가 아니다.

### 3.2.2 바이트를 정확히 한 번 읽는다 (TOCTOU 제거)

v1은 `sha256_file(path)`로 digest를 뜨고 **다시 열어** `read_text()`로 파싱했다. 그
사이에 쓰기가 들어오면 패키지는 **자기가 파싱하지도 않은 바이트의 sha256**을 기록한다 —
digest가 자기 자신의 승인 주장을 덮지 못하는 상태이며, 이 함수의 존재 이유를 정면으로
부정한다. 리뷰어가 동시-writer 시뮬레이션으로 드리프트를 실증했고 v1의 docstring과 출하
산문("parsed from the same bytes the sha256 above covers")은 그로써 반증되었다.

수정: `read_bytes()` **1회** → 같은 버퍼에서 `hashlib.sha256(raw)`와
`yaml.load(raw.decode())`. 선행 `is_file()` 탐침도 제거했다(관측 지점이 하나 더 늘 뿐이다).

**뮤테이션 실증**: 파싱만 재-읽기하도록 되돌린 뮤턴트를 넣자 신규 테스트가
`profile bytes were read 2 times, must be 1`로 **KILL**했다. 테스트는 비어 있지 않다.

**단일 읽기(런 수준)**: `main()`이 `read_profile_approval`을 **한 번** 호출해 baseline과
manifest 양쪽에 같은 레코드를 배선한다. (기존 `build_baseline` 내부 `profile_digest` 계산은
이 레코드의 `digest` 항으로 흡수 — 순서·의미 동일.)

### 3.3 loci별 전/후

| locus | 전 | 후 |
|---|---|---|
| 상수 `:181-183` | `VERIFICATION_PROFILE_VERSION = "2.1 (PROPOSED — P0-1 open)"` | 삭제. `PROFILE_STATUS_VOCABULARY` / `PROFILE_APPROVAL_UNKNOWN` (`:188-189`) 신설 + 결함 경위 주석 |
| baseline `version` | `"2.1 (PROPOSED — P0-1 open)"` | `"2.1 (APPROVED 2026-07-29, profile-level scope-limited; 17 of 163 numeric keys unapproved-null and fail-closed)"` (`:1805`) |
| baseline `approval_state` | `"PROPOSED — P0-1 (bounds approval) OPEN"` | `"APPROVED — profile-level, scope-limited. approved_by=operator; effective_from=2026-07-29; 17 of 163 numeric keys remain null, key-level UNAPPROVED and fail-closed."` |
| baseline `reason` | `"...VER §6 numeric bounds remain unapproved; no bound value is consumed by this run..."` | `profile_version_reason()` 파생 (`:1824`) — §3.5 참조 |
| manifest `p0_1_bounds_approval` | `"OPEN"` | `"CLOSED 2026-07-29 (profile-level, scope-limited; 17 of 163 numeric keys remain key-level unapproved-null and fail-closed)"` (`:2999`) |
| manifest `verification_profile_version` | 상수 | 파생 `version_label` (`:3000`) |

값을 재파생 가능하게 만들기 위해, baseline 필드는 **문장과 함께 파싱된 원자 필드**를
모두 싣는다: `profile_status` / `profile_version` / `approved_by` / `effective_from` /
`review_due` / `numeric_keys_total` / `unapproved_null_keys` /
`unapproved_null_key_names`(17개 실명). 독자가 라벨을 신뢰할 필요 없이 재계산할 수 있다.

`status: PROPOSED`로 되돌아가면 파생은 역사적 문자열을 **바이트 그대로** 재생산한다
(`"{version} (PROPOSED — P0-1 open)"` / `"PROPOSED — P0-1 (bounds approval) OPEN"` /
`"OPEN"`). 과거 15개 PROPOSED-바이트 패키지와의 연속성이 보존되고, 그 분기는 삭제가 아니라 파생된 분기다.

### 3.4 "no bound value is consumed" 주장 — 코드 실측 후 유지(정밀화)

**실측 결과: 참. 단, 이번 변경으로 문장을 정밀화해야 한다 — v1의 문안은 문자적 거짓이었다.**

v1은 "no bound VALUE is read from the profile"이라고 적었으나, census가 null 판정을 위해
`entry["value_ms"]`를 **읽는다**(`:1551`). 리뷰어 MINOR-3 지적이 옳다. HEAD의 원래 어휘가
정확했으므로 그쪽으로 복원한다: **"no bound value is consumed or recorded by this run;
nullity is inspected solely for the census."** 읽기(inspect)와 소비/기록(consume/record)의
구분이 load-bearing이다.

- 이 프로파일 파일을 여는 코드는 리포 전체에서 `tools/tos_evidence_run.py`(digest +
  이번 메타데이터 파싱)와 `tools/broker_probes/*`(P0-2 브로커 프로브 — EV 런 경로에
  미포함, 하네스가 import하지 않음)뿐이다. 하네스는 `bounds`/`limits`의 **값**을 읽지
  않는다 — 어떤 키가 null인지만 센다.
- 커널 패키지는 프로파일 키를 바인딩하지 않으며, 이는 코퍼스에 **집행 테스트로 고정**되어
  있다: `tos/tests/sci/test_sci_import_closure.py:526`
  (`"a VERIFICATION-PROFILE-002 key is bound in code"`),
  `tos/tests/failuredomain/test_failuredomain_anti_phantom.py:208`
  (`value_ms` / `MAX_` / `_MS =` / `THRESHOLD` 금지). 테스트가 소비하는 bound는
  fixture가 주입한다(`tos/tests/engine/_engine_fixtures.py:58` —
  "Every bound the engine consumes is injected here — the package hardcodes none").
- 새 문장은 세 층을 구분한다: 하네스는 **승인 메타데이터와 키의 nullity만 inspect**하고,
  **어떤 bound 값도 consume하거나 record하지 않으며**, 커널 패키지는 프로파일 키를
  **bind하지 않는다**. 전칭 부정을 쓰지 않고 "every bound a test exercises is injected by
  that test"로 반례 표면(테스트 주입)을 본문에서 명시 배제했다.
- 같은 문장에 **`review_due`는 기록하되 집행하지 않음**을 명시했다(NIT-3): 만료 판정은
  wall-clock을 요구하는데 이 하네스는 결정론을 위해 시계를 배제한다. 트레이드오프를
  숨기지 않고, 프로파일 currency는 하네스 게이트가 아니라 운영자/리뷰어 의무로 귀속시킨다.

### 3.5 테스트 — happy + negative

`tests/tools/test_tos_evidence_run.py` (+26 collected / −1 = 순증 25):

- `:402` `test_verification_profile_state_is_derived_from_the_artifact` — **리터럴 핀을
  의도적으로 쓰지 않는다.** 리터럴이야말로 이번에 stale이 된 것이다. 대신 기록된 모든
  필드가 프로파일의 **독립 파싱** 결과와 일치하고, 옆에 기록된 digest가 그 바이트를
  덮는지를 고정한다. null 키 명단·계수·총계도 독립 재계산과 대조한다.
- `:443` `test_verification_profile_version_is_not_the_register_column` — 두 출처가
  하나로 붕괴하지 않음을 고정. 주입 hermetic 레지스터는 `2.1-PROPOSED`를 유지하고
  리포 프로파일은 `2.1`을 파생하므로, 하네스가 레지스터 열을 프로파일 버전으로 echo하기
  시작하면 두 값이 같아지며 실패한다. **hermetic fixture의 `2.1-PROPOSED`는 stale 잔재가
  아니라 이 대조를 위한 의도적 sentinel이다**(레지스터 열 copy-through 검증이 목적).
- `:517` `test_profile_approval_derives_an_approved_profile` — 합성 프로파일
  (`version 9.9` / 4키 중 2 null)에서 계수·라벨·`CLOSED {effective_from}` 파생 확인.
  scope-limitation("2 of 4")이 라벨과 approval_state **양쪽**에 남는지 고정.
- `:533` `test_profile_approval_keeps_the_open_wording_while_status_is_proposed` —
  PROPOSED 분기의 역사적 문구 재생산 고정.
- `test_profile_approval_fails_closed_to_unknown` — **negative, 16 케이스
  parametrize**(실측 = collect된 parametrize id 계수): file-absent / yaml-parse-error /
  not-a-mapping / status-outside-vocabulary / status-absent / version-unusable /
  approved-without-approver / approved-without-effective-from /
  bounds-entry-not-a-mapping / bounds-section-not-a-mapping / **bounds-entry-without-
  value-ms** / **limits-entry-is-a-mapping** / **limits-entry-is-a-bool** /
  **empty-bounds-census** / **empty-limits-census** / **duplicate-status-key**
  (뒤 6개가 델타 재검증에서 추가된 MINOR-1/2·NIT-2 봉인분).
  공통 단언 `_assert_fail_closed`: 5개 주장 필드 전부 UNKNOWN·`approved_by == []`·
  `effective_from == ""`·이유 비어있지 않음·**주장 필드 dump에 "APPROVED"/"CLOSED"
  부재**(진단용 `unreadable_reason`은 발견된 값을 인용할 수 있으므로 명시 제외 —
  극성 검사는 주장 표면에만 건다).
- `:592` `test_unreadable_profile_still_records_the_digest_it_could_compute` —
  UNKNOWN은 **주장**을 억제하지 증거를 억제하지 않는다: 파싱 불가 파일도 digest는
  기록되어 어떤 바이트가 파싱을 무너뜨렸는지 리뷰어가 특정할 수 있다.
- `:606` `test_unreadable_profile_reason_reaches_the_recorded_baseline_reason`
- `:614` `test_harness_hardcodes_no_verification_profile_version` — **양방향 anti-phantom**:
  상수의 **부재**(`not hasattr`) + 소스 전문에 식별자 문자열 부재 + **프로파일이 선언한
  버전 문자열이 하네스 소스 어디에도 없음**(리포 프로파일에서 읽어 대조하므로, 향후
  버전이 바뀌어도 검사가 따라간다).

---

## 4. 07-29 이후 생성되어 stale 주장을 담은 런 패키지 — 사실 기록

> **`tos-evidence/**`는 서명·digest 결속된 불변 증거다. 이 작업은 그 아래를 한 바이트도
> 수정하지 않았고, 앞으로도 수정해서는 안 된다.** 아래는 관측 기록일 뿐이다.
> (검증: `git status --short tos-evidence/` = 빈 출력.)

전체 26개 런 패키지가 `PROPOSED — P0-1 (bounds approval) OPEN`을 담고 있다. 판정 기준은
**시계가 아니라 각 패키지가 스스로 기록한 프로파일 digest**다: 런이 실제로 어떤 바이트를
보았는지는 그 패키지의 `artifact.sha256`가 말해 준다.

방법: git 이력의 프로파일 blob 26종을 전수 파싱해 digest→`status` 사상을 만들고, 각
패키지의 기록 digest를 그 표에 조회한다. 시각 비교가 **전혀 개입하지 않는다**.

- **15개 = 기록 digest가 PROPOSED blob → 당시 주장은 참.** 정정 대상 아님.
- **11개 = 기록 digest가 APPROVED blob(`d837c7e7…5d064`) → 주장이 이미 거짓이었다.**

| 런 패키지 | baseline |
|---|---|
| `tos-evidence/STATE-EV-001/20260729T134948Z-d4160fd0` | `d4160fd0` |
| `tos-evidence/SPG-EV-002/20260729T134949Z-d4160fd0` | `d4160fd0` |
| `tos-evidence/STATE-EV-001/20260729T135130Z-d4160fd0` | `d4160fd0` |
| `tos-evidence/SPG-EV-002/20260729T135131Z-d4160fd0` | `d4160fd0` |
| `tos-evidence/STATE-EV-001/20260729T135150Z-d4160fd0` | `d4160fd0` |
| `tos-evidence/SPG-EV-002/20260729T135209Z-d4160fd0` | `d4160fd0` |
| `tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077` | `12dd4077` |
| `tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077` | `12dd4077` |
| `tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077` | `12dd4077` |
| `tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077` | `12dd4077` |
| `tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077` | `12dd4077` |

### 4.1 함정 성문화 — **author-time vs committer-time** (신규)

이 문서의 v1은 영향 패키지를 **5개**로 셌다. 오류의 원인은 **커밋의 committer-time으로
분류**한 것이다:

| `53980b64` | 시각 |
|---|---|
| **author** | `2026-07-29T21:51:16+09:00` |
| **committer** | `2026-07-29T23:48:38+09:00` |

`d4160fd0`의 6개 런은 **2026-07-29 22:49:48–22:52:09 KST**(run-id UTC
`20260729T134948Z`–`20260729T135209Z`)에 실행되어 **committer-time(23:48:38 KST)보다는
이르지만 author-time(21:51:16 KST)보다는 늦다** — 즉 승인된 프로파일 바이트가 **이미 워킹트리에 있었고**
런이 그것을 읽었다. committer-time으로 자르면 이 6개가 "폐쇄 이전"으로 잘못 분류된다.

**교훈(성문화)**: 커밋 시각으로 아티팩트의 존재 시점을 추론하지 말 것. rebase·amend·
늦은 커밋이 committer-time을 임의로 밀어내며, **워킹트리의 내용은 커밋보다 항상 먼저
존재한다.** 시각 기반 분류가 필요해 보이면 대개 **내용 기반(digest) 분류**가 가능하고,
그쪽이 시계 왜곡에 면역이다. 이번 정정은 시각 축을 **완전히 제거**해서 얻었다.

### 4.2 자기반박 실측 (이 결함의 가장 강한 증거)

11개 패키지가 기록한 `artifact.sha256`는
`d837c7e74b0fbe70d7cf2dfb30e412a29042577a0a38dcba22c649dd457d5064` —
**승인된 프로파일 바이트의 digest와 정확히 일치**한다(현재 HEAD 파일과도 동일).
즉 각 패키지는 *승인된 프로파일을 봉인해 놓고 그 옆에 "미승인"이라고 산문으로 적었다*.
digest는 처음부터 옳았고 산문만 틀렸다 — §3의 "같은 바이트에서 파생" 설계가 원리적으로
차단하는 정확한 형태이며, §4.1의 정정을 가능하게 한 것도 바로 이 digest다.

파생 리뷰 아티팩트 `tos-evidence/STATE-EV-004/review/EVL3-ladder-review-packet-v1.md`에도
`2.1-PROPOSED`가 19회 나타난다(위 런들에서 전사된 값). 동일하게 불변 — 읽기만 한다.

---

## 5. 레지스터 편집 검증 증거 (B)

편집: `EVIDENCE-REGISTER-002.csv`의 `verification_profile_version` 열 372셀
`2.1-PROPOSED` → `2.1`.

**편집 방식(바이트 레이아웃 보존)**: naive sed/grep 계수 금지 규율에 따라, Python으로
① 원본 바이트에서 리터럴 `2.1-PROPOSED` 출현 수 = 372, ② **콤마로 완전히 구분된 필드
형태** `,2.1-PROPOSED,` 출현 수 = **372(동일)** 임을 먼저 확인했다. 두 수가 같다는 것이
"이 리터럴은 언제나 해당 열의 셀 전체이며 다른 열의 부분문자열로 등장하지 않는다"는
구조적 증명이고, 그 위에서만 바이트 치환을 수행했다. CSV 재직렬화를 하지 않으므로
인용·개행·BOM이 재작성될 여지가 없다.

**전후 검증 (Python `csv` 모듈, 대조군 = `git show HEAD:...`)**:

| 항목 | 결과 |
|---|---|
| 행 수 | 372 → 372 |
| 헤더 | 동일 (16열) |
| `evidence_id` 집합·**순서** | 완전 동일, 372개 유일 |
| status 분포 | `NOT_IMPLEMENTED 291 / READY 79 / PASS 2` → **동일** |
| `verification_profile_version` 분포 | `{2.1-PROPOSED: 372}` → `{2.1: 372}` |
| **대상 열 외 전 셀 (15열 × 372행 = 5,580셀)** | **변경 0** |
| 대상 열 변경 셀 | 372 (전부 `2.1-PROPOSED` → `2.1`) |
| BOM (`EF BB BF`) | 보존 |
| 개행 | LF 유지 (CR 0개), 말미 개행 유지 |
| 인용 포함 행 수 | 37 → 37 |
| sha256 | `2148d26a…5b7f52f` → `3f808287…511c791` (97,252 → 93,904 bytes = 372 × 9) |
| `git diff --stat` | `372 insertions(+), 372 deletions(-)` |
| diff 행 중 `2.1(-PROPOSED)?,` 패턴 밖 | **0행** |

**소비자 검증**:
- `PYTHONPATH=tos/src .venv/bin/python tools/tos_spec_status.py` →
  `TOS spec status PASS: documents=13, ADRs=45, Part1=372, DEV=118,
  direct_traceability=29/30, source_gap_adrs=1, p2_carried=28, CONST-003=INCONCLUSIVE,
  migration_rows=54, broker_sites=9, count_transcriptions=11,
  restricted_live=NOT_AUTHORIZED, production=NOT_AUTHORIZED` (지표 불변)
- `tests/tools/` + `tests/tos_l3/` 전체 789 passed.

### 5.1 MD 미러 — 표시되지 않음 (관측만)

`EVIDENCE-REGISTER-002.md:27` "Mirror column mapping" 문단 실측:

> the `Owner` column below mirrors the CSV `implementation_owner` field. The remaining
> administrative fields (`evidence_owner`, **`verification_profile_version`**,
> `broker_capability_profile_version`, `evidence_location`) are carried **only in the
> CSV**, which remains the machine-editable source.

⇒ 이 열은 MD 미러에 **표시되지 않는다**. MD 무변경이 정답이며, 실제로 MD는 한 바이트도
건드리지 않았다. (`2.1-PROPOSED` grep도 이 파일에서 0히트.)

### 5.2 다른 소비자 양방향 grep

`2.1-PROPOSED`를 핀하는 코드/설정 **부재**를 확인했다:

- `tools/tos_spec_status.py` — Part-1 레지스터에 대해 이 열의 **값**을 핀하지 않는다.
  요구는 "비어있지 않을 것"(`:383`)과 "READY 이상이면 TBD/UNKNOWN/빈칸 금지"(`:395`)
  뿐이며 `2.1`은 둘 다 통과한다. `:1318`의 `!= "IOM-0.1-PROPOSED"` 핀은 **Part-3
  DEV/IOM 계열** 전용으로 이 편집과 무관(해당 파일 무변경).
- `--include`를 py/md/csv/yaml/yml/json/ts/tsx로 건 전 리포 grep 결과, `2.1-PROPOSED`
  잔존 위치는 (a) 이 CSV를 제외하면 **역사 기록 문서**
  (`docs/plans/2026-07-26-…-survey.md`, `2026-07-29-…-bounds-draft-package.md`,
  `2026-07-29-…-human-gate-register.md`, `docs/plans/INDEX.md`), (b) 불변 `tos-evidence/`,
  (c) `tos-spec/src/part-1-foundation/ARCHITECTURE-GATE-STATUS.md` 5곳, (d) 테스트
  hermetic fixture 4곳(§3.5 — 의도적 sentinel)뿐이다.
- (c)는 **다른 레인이 이미 처분**했다: HEAD `917fd0d2`
  ("docs(tos-spec): gate-status currency — record P0-1 profile-level approval")가
  `:1058`에 "Currency note (2026-08-06)"를 추가해 그 위 문단들이 "accurate when
  recorded … superseded on 2026-07-29"임을 명시했다. 남은 5곳은 **날짜가 박힌 역사
  기록**이므로 재작성 대상이 아니다(당시 리비전 기준으로 정확). 이 레인은 손대지 않았다.
- `tos-spec/book/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml:17`에
  `version: "2.1-PROPOSED"`가 있으나 `tos-spec/book/`은 **git 미추적 빌드 산출물**
  (`git ls-files tos-spec/book/ | wc -l` = 0)이라 커밋 표면 밖이다. 관측만 기록.

---

## 6. 변경 파일 / 테스트 결과

| 파일 | 변경 |
|---|---|
| `tools/tos_evidence_run.py` | +314 / −33 — 파생 함수 5개 + 중복키 거부 Loader 신설, 상수 1개 삭제, 4 loci 배선, discipline/completeness 문안 4곳 |
| `tests/tools/test_tos_evidence_run.py` | +347 / −5 — 순증 25 tests (negative 16 포함) |
| `tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv` | 372행, 대상 열만 |
| `docs/plans/2026-07-29-tos-ev-l2-pilot-design.md` | **+26 / −0 (순수 가산)** — §12 에라타 v1.3 |
| `docs/plans/2026-08-06-tos-post-p01-currency-harness-register.md` | 신규 (이 문서) |

- `PYTHONPATH=tos/src .venv/bin/python -m pytest tests/tools/test_tos_evidence_run.py`
  → **190 passed** (stale `__pycache__` 퍼지 후 실행)
- `PYTHONPATH=tos/src .venv/bin/python -m pytest tests/tools/ tests/tos_l3/` → **789 passed**
- `PYTHONPATH=tos/src .venv/bin/python -m pytest tests/tos_l3/` → 13 passed
  (하네스를 참조하는 유일한 다른 스위트)
- `ruff check` / `black --check` — 두 파일 모두 통과
- **e2e 실증**: 하네스를 scratchpad 임시 evidence-root로 1회 실행(rc=0). 산출된 baseline이
  `profile_status: APPROVED` / `effective_from: '2026-07-29'` /
  `numeric_keys_total: 163` / `unapproved_null_keys: 17` / 17개 실명,
  manifest가 `p0_1_bounds_approval: CLOSED 2026-07-29 (…)`를 기록함을 확인.
  `register_column_value: '2.1'`로 §5 편집도 함께 반영됨을 관측. **`tos-evidence/`에는
  아무것도 쓰지 않았다.**

---

## 7. 다음 독립 리뷰 레그가 주목할 지점

1. **manifest 자기모순 제거 완료 (MAJOR-1) — 다만 provenance 판정은 분할되었다.**
   v1은 stale 태그 3곳을 "전부 verbatim이라 손댈 수 없다"고 적었다. **이 주장은 틀렸다**
   (MINOR-4). 전수 grep 재실측 결과:

   | 좌표 | verbatim 출처 | 처분 |
   |---|---|---|
   | `DISCIPLINE_TAG` (L1) + 그 주석 | **부재** — `"EV-L1 stage execution record only"`·`"staged rows require higher stages"` 모두 `docs/plans/` 히트 0(**자기참조 = 본 기록 문서 제외**; 본 문서가 이 문자열을 인용한 뒤로는 자기 자신이 유일한 히트) ⇒ **하네스 자작** | **직접 수정** |
   | VER §3 completeness 산문 ×2 ("stands beside P0-1…") | **부재** (자작) | **직접 수정** |
   | `DISCIPLINE_TAG_L2` | **실재** — `2026-07-29-tos-ev-l2-pilot-design.md:268` | **설계 에라타 v1.3 추가 후** 갱신 |
   | `DISCIPLINE_TAG_L3` | 실재 — `2026-08-06-tos-ev-l3-pilot-design.md:470` | **무변경** |

   **`DISCIPLINE_TAG_L3`은 "P0-1"을 포함하지 않는다** — "restart coverage argument +
   network/identity residuals + independent review"만 명명한다. 따라서 stale이 아니고
   EV-L3 설계에 에라타는 **불요**하다. (지시는 L2/L3 양쪽 에라타였으나, 실측상 L3는
   고칠 것이 없다. 필요 없는 에라타를 다는 것 자체가 잡음이므로 달지 않았다.)

   에라타는 **가산적**이다: EV-L2 설계 §12에 v1.3 항을 추가하되 §6.2 N8 본문과 기존
   문자열은 **보존**했다(테스트가 양쪽을 동시에 고정 — §3.5).
   교체 원칙은 §6.2 N8이 원래 세운 것과 동일하다: **태그는 게이트 상태를 재단언하지 않고
   그 상태를 담은 블록을 참조한다.** 고정 문자열 "P0-1"을 파생 필드 참조로 바꾼 것은
   그 원칙의 이탈이 아니라 복원이다.
2. **`p0_1_bounds_approval` 의 `CLOSED` 어휘 (유지 + 역산 가능화)** — YAML은
   `status: APPROVED`만 말하고 "P0-1"이라는 게이트 이름과 `CLOSED`는 프로젝트 용어다.
   `APPROVED ⇒ CLOSED` 매핑은 하네스가 하는 **유일한 한 단계 해석**이다. 어휘는 유지하되,
   manifest claim에 **원자 필드 `verification_profile_status`(파싱 원값)를 동반 기록**해
   독자가 해석을 역산할 수 있게 했다. 해석의 타당성 자체는 여전히 리뷰 대상이다.
3. **hermetic fixture의 `2.1-PROPOSED` 유지**(§3.5) — stale 잔재로 오독될 수 있다.
   의도는 "레지스터 열 copy-through와 프로파일 파생이 서로 다른 출처임을 실증"이며
   `test_verification_profile_version_is_not_the_register_column`이 그 의도를 고정한다.
   이 판단이 옳은지 확인 요망.
4. **fail-closed 분기의 실효성** — negative 16 케이스가 파생 함수를 직접 호출한다.
   `main()` 경로 전체(불량 프로파일을 가진 리포에서 실제 패키지를 굽는 e2e)로는 확장하지
   않았다. 필요하면 다음 사이클 입력물.
5. **§4의 11개 패키지** — 불변이므로 정정하지 않는다. 이후 STATE-EV-004가 재실행되면
   새 런은 자동으로 정직한 값을 기록한다. 재실행 여부는 별개 판정이며, §2의 극성 논증에
   따라 **재실행은 기존 증거의 유효성 때문에 필요한 것이 아니다**.
6. **null 17키 명단의 manifest 미탑재** — 17개 실명은 baseline에만 싣고 manifest claim은
   스칼라 문자열만 유지했다(기존 claim 블록의 형태 보존). manifest에도 필요한지 판단 요망.

---

## 8. 이 편집이 만들지 않는 것

- 새 승인 0. P0-1은 2026-07-29에 이미 닫혔고 이 편집은 그 사실의 전파일 뿐이다.
- 17개 null 키는 여전히 key-level UNAPPROVED·fail-closed. P0-2(브로커 측정)와
  instance/architecture 결정은 그대로 열려 있다.
- 레지스터 status 291/79/2 불변. 어떤 행도 이동하지 않았다.
- ADR acceptance·restricted-live·production 권한 전부 불변
  (`tools/tos_spec_status.py` 출력의 `restricted_live=NOT_AUTHORIZED`,
  `production=NOT_AUTHORIZED` 실측 확인).
- `scope.environment: non-live-test` 불변. 승인된 bound는 harness ceiling이지
  live calibration이 아니다. Live-Armer 미배정(SoD 보존).
- `tos-evidence/**` 무변경.
