# 아키텍처 렌즈 감사 — Phase 0 완료 계약 프로토타입 v2.5

```yaml
lens: architecture
role: 증거 생산 (판정 없음 — verdict 는 Codex 심판 레인 소관)
target: tools/spikes/phase0_contract/{test_contracts.py, proto/*}
prior_verdict: .omc/review/20260812-231234/verdict.md (v2.3, needs-attention)
baseline_run: exit 0 · 대조군 30건 중 양방향 성립 30건 · 앵커 4종 전부 일치
findings: 8 (HIGH 3 / MEDIUM 4 / LOW 1)
method: 원본 무수정. in-process 뮤테이션(모듈 객체만 교체) + 구조 분석.
```

**실측 방법 고지.** 프로토타입 파일은 한 바이트도 수정하지 않았다. 러너를 `import` 한 뒤
모듈 **객체**의 속성만 교체하고 `run_all()` 을 재실행해 30개 Case 의 `ok` 와 앵커 4종의
드리프트를 관측했다. 파일 사본을 repo 밖에 두는 방식은 v2.5 가 추가한 `T-77-④` 위치
앵커에 걸리므로 쓰지 않았다 — **그 앵커는 의도대로 작동한다**(부수 확인).

---

## 요약 — 실측된 침묵 4건

v2.5 는 `⒟ 실행코드 앵커`(`loaded_code_text`)로 "러너와 proto 의 **어떤** 편집이든
설정 갱신을 요구한다"는 강한 성질을 주장한다(`proto/config.yaml:49-61`,
`test_contracts.py:335-352`). **그 앵커의 정의역은 함수·메서드의 코드 객체뿐이며
모듈 레벨 데이터 상수는 정의역 밖이다**(`test_contracts.py:291-315`). 정책이 데이터
상수에 들어 있는 지점에서 다음이 **전건 GREEN·앵커 드리프트 0** 으로 통과했다.

| # | 뮤테이션 (in-process) | 결과 | 앵커 드리프트 |
|---|---|---|---|
| M1 | `boundary.FORBIDDEN_ARTIFACTS` 5종 → 1종 | 30/30 GREEN | 없음 |
| M2 | `register.REQUIRED_METRICS` 에서 `imprecise_owner_track` 제거 | 30/30 GREEN | 없음 |
| M2' | 〃 `closable_no_rows` 제거 | 30/30 GREEN | 없음 |
| M3 | `register.FIXTURE_CLAUSES` 에 가짜 절 2개 추가 | 30/30 GREEN | 없음 |
| M7 | `boundary._PATH_BLOCKED` 에서 5개 제거 | 30/30 GREEN | 없음 |

대조군(같은 방식으로 잡힌 것): `LEVEL_KINDS` 변경 → `T-76`·`T-39`·`UNCHK-019`·`SELF-1` red /
`VERIFIABLE_KINDS` 변경 → `FWD-a-0`·`T-39`·`SELF-1` red / `DEFECT_WORDS=()` → `SELF-1` red /
`READ_GUARDED_ENTRY_POINTS` 축소 → `SELF-1` red(⒝ 방출 앵커).
**즉 검출과 침묵을 가르는 것은 중요도가 아니라 "그 상수가 config 앵커를 갖거나 노트
산문에 삽입되는가"라는 우연적 성질이다.**

---

## A-1 (HIGH) — `⒟ 실행코드 앵커`의 정의역이 함수 코드 객체로 한정돼 모듈 레벨 정책 상수가 앵커 밖이다

- **location**: `tools/spikes/phase0_contract/test_contracts.py:291-315` (`_module_code_parts`),
  `:318-332` (`loaded_code_text`), `proto/config.yaml:49-61` (앵커 선언)
- **위반한 원칙**: 설정 기반 아키텍처(CLAUDE.md 비협상 — 정책값은 설정으로) · 선언층/평가층 일치
- **finding**:
  `_module_code_parts` 는 `getattr(obj, "__code__")` 가 있는 객체와 클래스의 메서드만
  순회한다(`:302-314`). 모듈 레벨 `tuple`/`frozenset`/`dict`/`str` 상수는 두 조건 어디에도
  걸리지 않아 digest 입력에 들어가지 않는다.
  **실측**: `boundary.FORBIDDEN_ARTIFACTS` 를 5→1 로 줄여도 digest 는
  `f4ea9b8f2d77b472` → `f4ea9b8f2d77b472` 로 **불변**. `register.REQUIRED_METRICS` 4→3 도 동일.
  반면 `config.yaml:52-53` 은 이 앵커를 "러너의 **어떤 편집이든** 이 값 갱신을 요구한다"고
  적는다 — **선언이 평가보다 넓다.** 심판이 12판 연속 추적해 온 그 간극의 형태가
  v2.5 의 최신 교정층에서 재현된 것으로 관측된다.
  주의: 문자열 단순 포함 검사는 위양성을 준다 — `'§13.5.2'`·`'write_text'`·`'결함'` 은
  blob 에 **존재**하지만 그것은 각각 `fixture_rows()`·프로브 라벨·`main()` 의 print 라는
  **함수 안**에 같은 리터럴이 별도로 있기 때문이며, 상수 자체가 앵커된 것이 아니다
  (digest 불변 실측이 이를 가른다).
- **recommendation**: 앵커 정의역을 "모듈의 공개 바인딩 중 코드 객체 **또는 해시 가능한
  데이터 상수**"로 넓히거나, 정책을 담은 상수를 `LEVEL_KINDS` 처럼 config 앵커
  (`anchor_level_kinds`)로 개별 승격한다. 어느 쪽도 못 하면 `config.yaml:49-61` 과
  `test_contracts.py:335-352` 의 "어떤 편집이든" 문언을 정의역에 맞게 좁힌다.
- **confidence**: 95 (실측)

## A-2 (HIGH) — OD-3-B "금지 아티팩트 5종" 이 리스트 길이와 무관하게 GREEN 이다

- **location**: `proto/boundary.py:63-69` (`FORBIDDEN_ARTIFACTS`),
  `test_contracts.py:824-839` (Case `T-77-③`), 특히 `:827` `:834` `:836`
- **위반한 원칙**: 단일 소스 정본(문서 §OD-3-B ↔ 코드 목록) · 선언층/평가층 일치
- **finding**:
  대조군은 목록의 **첫 항목만** 표적으로 삼고(`:827` `target = ... FORBIDDEN_ARTIFACTS[0]`),
  방향② 성립 조건이 `len(mutant_artifacts) == 1` 이다(`:836`). 목록이 5개든 1개든 이 식은
  참이다. Case **이름**은 `"금지 D0 아티팩트 5 종 미생성"` 이라는 **리터럴**이며
  `len(FORBIDDEN_ARTIFACTS)` 에서 파생되지 않는다 — 그래서 목록을 줄여도 ⒞ Case 산문
  앵커조차 움직이지 않는다.
  **실측**: 5→1 축소 후 30/30 GREEN, 앵커 드리프트 0. 즉 **OD-3-B 가 강제한다고 적힌 5종 중
  4종을 검사 대상에서 제거해도 이 러너는 아무 말도 하지 않는다.**
  (범위 고지: 실측은 "검사기가 침묵한다"까지다. 실제 D0 아티팩트가 생성되는지는 별개 사실이며
  본 감사는 그것을 주장하지 않는다.)
- **recommendation**: Case 이름·방향② 조건을 `len(FORBIDDEN_ARTIFACTS)` 에서 파생시키고,
  목록 자체를 `config.yaml` 앵커(`anchor_forbidden_artifact_count` 또는 전체 목록)로 올린다.
  최소한 항목 **전수**를 방향② 로 심어 `len(mutant) == len(FORBIDDEN_ARTIFACTS)` 를 요구한다.
- **confidence**: 95 (실측)

## A-3 (HIGH) — U-10 "4 지표" 중 2개는 요구 목록에서 지워도 어느 검사도 발화하지 않는다

- **location**: `proto/register.py:36-41` (`REQUIRED_METRICS`), `:236-252` (`check_u10`),
  `proto/enforcement.py:286-289` (U-10 뮤테이션 컨텍스트), `test_contracts.py:1401-1416` (`T-73`)
- **위반한 원칙**: 설정 기반(지표 우주가 코드 상수) · 대조군 커버리지의 비직교성
- **finding**:
  `check_u10` 의 우주는 `REQUIRED_METRICS` 이고 `metrics()` 가 만드는 값도 같은 모듈의
  같은 4개다. 두 대조군이 이 우주를 건드리는데 **서로 다른 항목 하나씩만** 쓴다:
  `T-73` 은 `METRIC_SUPERSET` 을 pop 하고(`test_contracts.py:1406`),
  `violating_contexts["U-10"]` 은 `METRIC_BLANK_REF` 를 pop 한다(`enforcement.py:288`).
  나머지 두 지표(`imprecise_owner_track`·`closable_no_rows`)는 **어떤 대조군의 표적도 아니다.**
  **실측**: 각각을 `REQUIRED_METRICS` 에서 제거 → 30/30 GREEN, 앵커 드리프트 0.
  (대조 확인: `superset_declared_pairs` 제거 → `T-73`+`SELF-1` red / `blank_normative_ref_rows`
  제거 → `T-39`+`SELF-1` red. 즉 보호는 우연히 표적이 된 2개에만 붙어 있다.)
  이는 심판 F5 의 "5번째 지표에 소비처가 없다"와 같은 결함 클래스가 **기존 4개 쪽에서**
  나타난 것으로 관측된다 — 지표 우주의 크기 자체에 검사기가 없다.
- **recommendation**: `len(REQUIRED_METRICS)` 를 config 앵커로 고정하고,
  `T-67`(`test_contracts.py:1042-1099`)이 이미 4지표 전수를 도는 구조이므로
  `check_u10` 의 방향② 도 `REQUIRED_METRICS` 전수 루프로 일반화한다.
- **confidence**: 95 (실측)

## A-4 (MEDIUM) — 러너가 `proto` 의 private `_check_*` 를 직접 호출해 공개 표면(`run_check`)을 우회한다 · 레지스트리 결속 증거가 T-39 단일 지점에 집중

- **location**: `test_contracts.py:390`, `:414-415`, `:978`, `:1231`, `:1364-1366`,
  `:1404-1407`, `:1422-1424` → `proto/enforcement.py:39-153` (`_check_u11`·`_check_t71`·
  `_check_t76`·`_check_u8a`·`_check_u10`·`_check_u9a`)
- **위반한 원칙**: 레이어 경계 · 캡슐화 · "T-39 의 우주는 이 dict 의 키다"(`enforcement.py:1-5`)
- **finding**:
  러너가 호출하는 `enforcement` 심볼 중 5개가 밑줄 접두 private 이다
  (`_check_t71`·`_check_t76`·`_check_u10`·`_check_u11`·`_check_u8a`·`_check_u9a`).
  결과적으로 `T-71`·`T-73`·`T-74`·`T-76` 등 전용 Case 는 **검사 함수가 동작함**만 증명하고
  **레지스트리가 그 함수를 호출함**은 증명하지 않는다.
  **실측**: `build_registry()` 의 키를 유지한 채 값만 무력화(`lambda ctx: []`)했을 때 —
  ```
  T-71 무력화 → 전용 Case T-71 ok=True
  U-10 무력화 → 전용 Case T-73 ok=True
  U-9a 무력화 → 전용 Case T-74 ok=True
  T-76 무력화 → 전용 Case T-76 ok=True   (`:1211` 이 키 존재는 보지만 결속은 안 본다)
  ```
  전체 실행에서는 `T-39` 하나가 이를 잡는다(`disarm T-71 → failed=['T-39','SELF-1']`).
  즉 **12개 강제 지점의 레지스트리 결속 전부가 T-39 라는 단일 대조군에 걸려 있고**,
  12개 키 중 러너가 등록 여부를 명시 검사하는 것은 `T-76` 하나뿐이다(`:1211`, 그나마 키
  존재만 본다).
- **recommendation**: 전용 Case 들이 `run_check(ctx)` 또는 `run_check(ctx, skip=...)` 의
  공개 표면을 통해 관측하도록 바꾸면 결속 증거가 12개 Case 에 분산된다.
  private 직접 호출이 불가피하면 각 Case 에 `T-76` 식 등록 확인을 더하되 **키 존재가 아니라
  `build_registry()[key] is <함수>` 동일성**을 본다.
- **confidence**: 90 (실측 — 무력화 실험)

## A-5 (MEDIUM) — 피검사 계층(`proto/`)이 뮤테이션 하네스를 자체 보유한다 (검사 대상이 검사 어포던스를 겸함)

- **location**: `proto/enforcement.py:236-346` (`violating_contexts`),
  `proto/gates.py:92` (`is_zero = _is_zero`, 주석 "뮤테이션 하네스가 술어를 재조립할 때 쓴다"),
  `:214-221` (`build_reasons_ignoring_blocks_gate`, "red 로 만들어야 하는 뮤턴트"),
  `:239-241` + `:263-264` (`ignore_inputs`/`fold` 분기가 프로덕션 평가기 안에 있음),
  `proto/floor.py:88-97` (`use_floor=False`, "음성 대조군으로만 쓴다"),
  `proto/register.py:380-445` (`all_met_inputs`·`all_checkable_registry`·`_always_true`·
  `all_checkable_inputs`·`rows_replacing`)
- **위반한 원칙**: 레이어 경계(대조군 계층의 책임이 피검사 계층으로 하향) · 단일 책임
- **finding**:
  대조군이 필요로 하는 변형 능력이 **피검사 모듈의 공개 시그니처에 상주**한다.
  가장 뚜렷한 것은 `gates._contribute`(`:224-255`) 로, `ignore_inputs and PARTIAL` 분기는
  오직 뮤턴트가 되기 위해 존재한다 — 프로덕션 결합 규칙의 동작이 테스트의 필요로
  파라미터화돼 있다. `enforcement.violating_contexts` 는 강제 레지스트리와 **같은 파일**에서
  그 레지스트리를 위반시키는 컨텍스트 12종을 생산한다.
  이는 프롬프트가 물은 "검사기가 자기 검사 대상을 겸하는 지점"의 정확한 형태다.
  **추정(미실측)**: 이 어포던스를 제거하는 방향의 뮤테이션은 해당 Case 의 방향②를 구성
  불가로 만들어 red 가 되고(`_contribute` 는 함수이므로 ⒟ 앵커도 발화), **fail-closed 로
  보인다.** 따라서 현재 악용 가능한 통로라기보다 구조적 결합도 문제로 보고한다.
- **recommendation**: 뮤테이션 어포던스를 `proto/` 밖(러너 곁의 `harness` 모듈)으로 옮기고,
  피검사 API 는 정상 경로만 노출한다. `violating_contexts` 는 `build_registry` 와 다른 파일로
  분리해 "키와 뮤테이션이 같은 편집에서 함께 사라지는" 동시-편집 창을 좁힌다.
- **confidence**: 80 (구조 실측 + 영향은 추정)

## A-6 (MEDIUM) — 쓰기 가드의 **고지 목록**과 **실제 차단 목록**이 서로 다른 두 데이터이고 정합 검사가 없다

- **location**: `proto/boundary.py:101-136` (`GUARDED_ENTRY_POINTS`, 고지용 34항)
  vs `:138-172` (`_OS_BLOCKED`·`_SHUTIL_BLOCKED`·`_PATH_BLOCKED`, 실제 패치 대상)
  + `:635-645` (패치 루프), `test_contracts.py:904-910` (노트가 고지 목록을 삽입)
- **위반한 원칙**: DRY · 단일 소스 정본
- **finding**:
  같은 사실이 두 곳에 독립적으로 표현된다. 현재 두 집합은 **정확히 일치한다**(실측:
  advertised 34 / actual 34 / 차집합 양방향 공집합) — 그러나 **둘을 비교하는 검사가
  코드베이스에 없다**(실측). 그리고 비대칭적으로, 고지 목록은
  `L-T77-WRITE-SCOPE` 노트 본문에 삽입되므로 ⒝ 방출 앵커가 덮는 반면
  (실측: `READ_GUARDED_ENTRY_POINTS` 축소 → `SELF-1` red),
  **실제 차단 목록은 어떤 앵커도 덮지 않는다** (실측: `_PATH_BLOCKED` 에서 `touch`·
  `mkdir`·`rmdir`·`symlink_to`·`hardlink_to` 5개 제거 → 30/30 GREEN, 드리프트 0).
  즉 **앵커가 붙은 쪽은 광고문이고, 강제하는 쪽은 무방비다.**
  **추정(미실측)**: 그 5개를 지워도 `Path.touch`→`os.open`, `Path.mkdir`→`os.mkdir` 처럼
  `os.*` 계층 패치가 중복 방어로 남을 수 있어 실제 쓰기 탈출이 항목마다 성립한다고
  단정하지 않는다. 실측 범위는 "축소가 침묵한다"까지다.
- **recommendation**: `GUARDED_ENTRY_POINTS` 를 `_OS_BLOCKED`/`_SHUTIL_BLOCKED`/`_PATH_BLOCKED`
  + 고정 5항에서 **파생**시켜 두 표현을 하나로 만든다(`READ_GUARDED_ENTRY_POINTS` 도 동일).
  파생되면 노트 산문에 실린 ⒝ 앵커가 실제 강제 표면까지 자동으로 덮는다.
- **confidence**: 90 (실측)

## A-7 (MEDIUM) — 앵커 ⒜ 는 ⒟ 대비 독립 검출 표면이 관측되지 않으며, 유일한 차이는 **디스크를 읽는다**는 약한 쪽이다

- **location**: `test_contracts.py:227-259` (`limit_text_anchor`), `:1487-1489` (⒜ 호출,
  `Path(__file__).read_text()`), `:1492-1504` (⒟ 호출, `sys.modules` 코드 객체),
  `proto/config.yaml:28-33` (⒜ 선언) vs `:49-61` (⒟ 선언)
- **위반한 원칙**: DRY · 계층 간 소스 불일치
- **finding**:
  프롬프트가 지목한 불일치는 실재한다: ⒜ 는 `Path(__file__).read_text()` 로 **디스크 파일**을
  파싱하고, ⒟ 는 **로드된 코드 객체**를 본다. `config.yaml:54-56` 은 4차 교정에서
  "디스크를 해시하면 런타임 함수 교체로 우회된다"는 이유로 ⒟ 를 로드 코드로 옮겼다고
  적는데, **⒜ 는 그 교정을 받지 않은 채 남아 있다.**
  **실측**: 러너 소스의 `limit()` 호출에서 ⒜ 가 수집하는 문자열 리터럴 조각은 27개이고,
  그중 ⒟ 의 digest 입력(blob)에 **보이지 않는 조각은 0개**다. 즉 ⒜ 가 단독으로 검출하는
  표면은 관측되지 않았다.
  두 앵커가 갈리는 방향은 두 가지뿐이며 둘 다 ⒜ 에 불리하다:
  ① 런타임 함수 교체 → ⒟ red / ⒜ green(⒜ 는 디스크라 원본을 본다) — **⒟ 가 덮는다.**
  ② import 이후 디스크 편집 → ⒜ red / ⒟ green — 우회가 아니라 위양성 방향.
  ⇒ **실질 결함(= 우회 통로)이라기보다 잉여 레이어**로 관측된다. 다만 "4종 앵커가 각각
  다른 통로를 닫는다"는 서술은 ⒜ 에 대해서는 현재 시제로 뒷받침되지 않는다.
- **recommendation**: ⒜ 를 폐기해 3종으로 줄이거나, 유지한다면 ⒟ 와 **같은 소스**
  (로드된 코드)에서 계산하고 `config.yaml:28-33` 의 역할 서술을 "디스크-로드 불일치 탐지"로
  정직하게 바꾼다. 후자를 택하면 ⒜ 는 잉여가 아니라 무결성 검사가 된다.
- **confidence**: 85 (실측 27/27 + 구조 추론)

## A-8 (MEDIUM) — `self_check` / `Report` 의 책임 과밀 · `Report.anchors` 가 데이터 계층에 SELF-1 전용 슬롯을 만든다

- **location**: `test_contracts.py:1464-1573` (`self_check`, 110행),
  `:126-224` (`Report`, 조회 메서드 8종 + `:133` `anchors` 슬롯)
- **위반한 원칙**: 단일 책임 · 계층 분리
- **finding**:
  `self_check` 한 함수가 ① config 6키 로드 ② L1 등재 4종 검사(`undeclared`/`missing`/
  `duplicated`/`unresolved`) ③ L2 주차 거부 ④ 발견 결속 2종 ⑤ 앵커 4종 계산·대조
  ⑥ 프로브 `Report` 조립과 뮤턴트 판정 ⑦ Case 생성을 모두 수행한다.
  `Report`(수집 자료구조)에 `anchors: dict` 가 붙어 있고(`:131-133`) SELF-1 이 이를 채운다
  (`:1531-1536`) — 수집 계층이 특정 검사의 결과 슬롯을 갖는다.
  **다만 이 슬롯 자체는 F1 교정의 핵심 장치이며 목적을 달성한다**(아래 A-검증 참조).
  지적은 배치이지 존재가 아니다.
- **recommendation**: 앵커 계산을 `anchor_check(cfg, rep) -> dict[str,str]` 로 분리하고
  `self_check` 는 결속 검사만 남긴다. 앵커 결과는 `Report` 필드가 아니라 반환값으로
  `main()` 에 전달한다.
- **confidence**: 75 (구조 판단)

## A-9 (LOW) — `config.yaml:57` 의 앵커 대상 모듈 수 서술이 실제와 1 어긋난다

- **location**: `proto/config.yaml:57` ("대상 모듈 = 러너 + proto 7개")
  vs `test_contracts.py:1494-1502` (실제 튜플: runner + boundary·enforcement·floor·gates·
  register·config = **proto 6개**)
- **finding**: `proto/` 의 `.py` 파일은 7개지만(`__init__.py` 포함) 앵커 튜플은 6개를 싣는다.
  `__init__.py` 는 코드 객체가 없어 검출력 손실은 0 이나, **자기 인용 정확성을 스스로
  규율하는 아티팩트**에서 선언 수치가 평가 수치와 다르다. v2.3 NIT(`CLAUDE.md:20-22` vs
  `:21-23`)와 동종.
- **recommendation**: "proto 6개(`__init__.py` 는 코드 객체 없음)" 로 정정하거나 튜플에
  `proto` 패키지 모듈을 포함시킨다.
- **confidence**: 90 (실측)

---

## 교정이 성립한 것 — 반대 방향 증거

렌즈가 확인해 달라고 요청받은 항목 중 **성립하는** 것들을 명시한다.

### F1 교정 — `SELF-1` 의 구조적 순환은 실제로 제거됐다 (실측)

`case_prose_anchor`(`:355-374`)가 `SELF-1` 을 **포함**하면서도 순환하지 않는다:
`detail` 을 먼저 확정하고(`:1512-1519`) → 임시 Case 로 해시하고(`:1521-1523`) →
digest 값을 `rep.anchors` 에 넣어 `main()` 출력으로 내보내며(`:1531-1536`, `:1669-1670`)
→ 그 다음 실제 Case 를 등재한다(`:1573`). **digest 값이 자기 해시 입력에 들어가지 않는다.**
`config.yaml:44-46` 이 "4차까지의 제외가 곧 주차 지점이었다"고 적은 대로,
배제를 등재하는 대신 배제를 없앤 교정이며 구조적으로 건전하다.

`⒟` 가 러너 모듈 자신을 해시 대상에 포함하는 것도 순환이 아니다 — 앵커 **값**은
`config.yaml` 에만 있고 해시 정의역에서 `*.yaml` 이 제외되기 때문이다(`:328`).

### F1 교정 — 등재 강제(L1)는 주입된 노트를 잡는다 (실측)

`DEFECT_WORDS` 를 빈 튜플로 만들었을 때 `SELF-1` 이 red 가 됐다 — L2 어휘 목록을
무력화해도 방향② 프로브(`:1552-1571`)가 이를 검출한다. 심판이 v2.3 을 뚫은 3종
(어휘 밖 서술 2종 + green Case 주차)이 프로브에 그대로 심겨 있고
(`:1558-1560`) L1/L2 가 각각 이를 잡는 구성이다. **"폐쇄가 아니라 가시화"라는 자기
서술(`:34`, `config.yaml:25`)은 정직하다** — 다만 그 가시화가 덮는 표면은 `limit()` 노트에
한정되며, A-1~A-3 이 보인 대로 **정책 데이터 상수는 그 표면 밖**이다.

### F3 교정 — 런타임 열람 가드와 위치 앵커는 작동한다 (실측)

`read_violation`(`boundary.py:414-435`)이 `os.fsdecode` → `Path.resolve()` 후 **경로 값**으로
판정하므로 조립 방식과 무관하다. 러너의 3종 재현(리터럴·`join`·`chr`,
`test_contracts.py:851-856`)이 전부 차단됐다(baseline 출력 `T-77-①-READ` 성립).
`main()`(`:1611`)이 `run_all()` 전체를 두 가드로 감싸는 배선도 확인했다 —
v2.5 1차 교정의 "기제는 있는데 배선하지 않았다"는 문제가 해소돼 있다.
`T-77-④` 위치 앵커도 작동한다: 본 감사가 repo 밖 사본 방식을 포기한 이유가 그것이다.

### 설정 커버리지 — `REQUIRED_KEYS` 누락에 의한 fail-open 없음 (실측)

`config.yaml` 의 키 16개와 `config.py:13-30` 의 `REQUIRED_KEYS` 16개가 **양방향 차집합
공집합**이다. 4종 digest 를 읽는 `settings.get(key, "")`(`:1488` `:1491` `:1505` `:1520`)의
기본값 `""` 는 도달 불가이며, 설령 도달해도 `"" != <hex>` 로 **fail-closed** 방향이다.
`cfg_int`/`cfg_list`/`cfg_pairs`(`config.py:78-112`)는 전부 예외로 중단한다.
**임계값(수치) 하드코딩은 v2.2 이후 재발이 관측되지 않는다.** 본 감사가 지적하는 것은
수치가 아니라 **목록·집합 형태의 정책 상수**다(A-1~A-3, A-6).

### 의존성 방향 — 순환 없음 (실측)

`config ← floor ← register ← enforcement`, `gates ← {register, enforcement}`,
러너 → 전부. `proto/` 가 러너를 import 하는 지점은 없다. 역방향·순환 의존 0.

---

## 부수 관측 (비물질)

- `proto/boundary.py:512-516` 과 `:596-600` 에 동일한 `_patch` 헬퍼가 두 번 정의돼 있다
  (DRY, 사소). 중첩 시 저장/복원 체인은 정상 동작함을 확인했다 —
  `main()` 의 `write_guard` → `read_guard` → `t77_boundary` 내부 가드 3중 중첩에서
  각 가드가 진입 시점 값을 저장하고 역순 복원하므로 위임 사슬이 끊기지 않는다.
- `write_guard` 의 `_blocker`(`:590-594`)는 경로와 무관하게 **무조건** 예외를 던지는 반면
  `read_guard` 는 경로 값으로 선별한다. OD-3-C(쓰기 0)와 OD-3-A(특정 경로 금지)의
  요구가 다르므로 이 비대칭은 의도로 읽힌다 — 지적이 아니라 기록이다.
- `register.py:29` `FIXTURE_CLAUSES` 확장이 침묵하는 것(M3)은 A-1 의 하위 사례다.
  영향은 픽스처 세계 안(U-9 의 "해석되는 인용" 우주)에 갇혀 있어 A-2/A-3 보다 낮게 본다.

---

## 재현 절차

```bash
# 베이스라인 (원본 무수정)
python3 tools/spikes/phase0_contract/test_contracts.py; echo "EXIT=$?"
# → EXIT=0 · 대조군 30건 중 양방향 성립 30건
#   산문 앵커 대조: 리터럴=5efb40f2c1962a30 · 방출=cada1899362b330b
#                   Case산문=a43e14b843e49a4e · 실행코드=f4ea9b8f2d77b472
```

뮤테이션 프로브 3종(파일 무수정, in-process):
`scratchpad/probe.py`(M1~M8 침묵/검출 판정) ·
`scratchpad/probe2.py`(앵커 정의역·⒜⊂⒟·고지/실제 목록·private 호출 전수) ·
`scratchpad/probe3.py`(레지스트리 무력화 실험).

## 렌즈 경계 고지

- **판정 없음.** 위 항목은 증거이며 gate 판정은 Codex 심판 레인 소관이다.
- 스타일·네이밍(style-auditor), 성능(performance-auditor), 시크릿·주입(security-auditor)
  영역은 다루지 않았다. `boundary.py` 의 `setattr` 기반 monkeypatch 는 보안 렌즈의
  관심사일 수 있으나 아키텍처 렌즈에서는 가드 계층의 설계로만 평가했다.
- 설계 문서(`docs/plans/2026-08-12-...`) 본문의 정합성은 이 렌즈의 대상이 아니다 —
  프로토타입 코드와 `proto/config.yaml` 의 자기 서술만 대조했다.
