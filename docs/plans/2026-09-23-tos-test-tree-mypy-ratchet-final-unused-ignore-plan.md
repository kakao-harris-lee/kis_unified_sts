# tos 테스트 트리 mypy 래칫 마지막 단계 — `unused-ignore` 8건 (2026-09-23)

- 작성: 2026-09-23 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 측정 시점 main **`c2b9761f`**(PR #787 게이트
  활성화 머지) · mypy **2.3.1**(CI 핀) · 모의투자 운용 서버 루트 venv
- 상위: `docs/plans/2026-09-18-tos-test-tree-mypy-ratchet-plan.md` §2 · §3.4 · §6 ① ·
  `docs/plans/2026-09-22-tos-test-tree-mypy-ratchet-stage3-plan.md` §7.1 · §7.5 ·
  핸드오프 `docs/runbooks/2026-09-23-tos-session-handoff-paper-server.md` §4.1
- 성격: **소형 계획 하나 · 운영자 선택 1건 · PR 하나.** 상위 §3.4 가 「마지막에 재면 남은 것이 진짜 죽은 억제」라고
  예고한 그 측정의 결과와 처분이다.

## 0. 한 줄 요약

3단계(`arg-type` 773 → 0) 뒤 새 CI 플래그(`no-untyped-def`·`unused-ignore` 만 유예)에서 `unused-ignore` 는
**커널 5 · 런타임 3 = 8건**이고, zero-disable 에선 **0** 이다. 여덟은 전부 `# type: ignore[no-untyped-def]` 다.
권고는 **(a) 여덟을 지우고 CI 에서 `unused-ignore` 를 켠다** — 유예를 1종(`no-untyped-def`)으로 줄이고
`warn_unused_ignores = true`(`pyproject.toml`) 선언을 게이트가 실제로 집행하게 만든다.

## 1. 실측 (2026-09-23, `rm -rf .mypy_cache` 후, `PYTHONPATH=tos/src:tos/runtime/src`)

| 측정 | 커널 `tos/tests` | 런타임 `tos/runtime/tests` |
|---|---:|---:|
| 새 CI 플래그(`--disable-error-code=no-untyped-def --disable-error-code=unused-ignore`) | 0 / 579 files | 0 / 221 files |
| `unused-ignore` 만 켬(`--disable-error-code=no-untyped-def`) | **5** | **3** |
| zero-disable `unused-ignore` | 0 | 0 |
| zero-disable `no-untyped-def` | 250 | 366 |
| 소스 스텝 `mypy src` / `mypy tos/runtime/src` | 0 / 264 | 0 / 185 |

3단계 착지 기록(§7.1 표)과 수치가 같다. 여덟 자리:

| # | 파일:줄 | 억제된 정의 |
|---|---|---|
| 1 | `tos/tests/sci/test_sci_import_closure.py:231` | `def _run_child(target) -> dict:` |
| 2 | `tos/tests/sci/test_sci_records.py:47` | `def _issue(builder, **overrides):` |
| 3 | `tos/tests/marketfeed/_cycle_children.py:16` | `def dsl_only_child(queue) -> None:` |
| 4 | `tos/tests/marketfeed/_cycle_children.py:25` | `def engine_only_child(queue) -> None:` |
| 5 | `tos/tests/marketfeed/_cycle_children.py:34` | `def capsule_only_child(queue) -> None:` |
| 6 | `tos/runtime/tests/compose/test_riskstate_wiring.py:1262` | 중첩 `def _spy(request):` |
| 7 | `tos/runtime/tests/compose/test_riskstate_wiring.py:1478` | 중첩 `def _seeding_observe(*, root_event_id, attempt_id, root_event_seq=None):` |
| 8 | `tos/runtime/tests/compose/test_riskstate_wiring.py:1561` | 같은 모양, 두 번째 테스트 |

여덟 줄 전부 주석이 `# type: ignore[no-untyped-def]` 하나뿐이다(다른 코드와 겹친 라벨 없음). 즉 주석을 지워도
**코드는 한 글자도 바뀌지 않는다.**

## 2. 왜 여덟이 남았나 — 유예 코드를 억제한 주석

mypy 는 `# type: ignore[X]` 의 `X` 가 **꺼져 있으면** 그 주석을 unused 로 본다(상위 §2.1 대조표 「라벨 코드를 끔 →
`unused-ignore`」). CI 는 `no-untyped-def` 를 **영구 유예**한다(상위 §6 ① — `check_untyped_defs = true` 가 이미
본문을 검사하므로 애노테이션을 채워도 탐지력이 거의 안 는다). 그러므로 `# type: ignore[no-untyped-def]` 는 CI
관점에서 **영원히 unused** 다. 이 여덟은 누군가 로컬에서 zero-disable 로 재다가 `no-untyped-def` 를 조용히 시키려고
붙인 것이고, 게이트가 강제하지 않는 코드를 억제하고 있다.

3단계 이전의 187건 중 179건은 「`arg-type` 이 꺼져 있어서만 unused」였고 `arg-type` 을 켜자 되살아났다(3단계 §7.1).
그 되살아남이 바로 `unused-ignore` 를 마지막에 켜야 하는 이유였고(상위 §2), 이제 남은 여덟은 그 부류가 아니다 —
**앞으로도 켜질 일이 없는 코드**를 가리킨다.

## 3. 선택지

### (a) 여덟을 지우고 `unused-ignore` 를 켠다 — **권고**

- 변경: 여덟 줄에서 주석만 삭제 · `.github/workflows/tos-firewall.yml` 두 테스트 트리 스텝(`:456-457`·`:462-463`)에서
  `--disable-error-code=unused-ignore` 제거 · 스텝 주석 갱신.
- 뒤: CI 유예는 **`no-untyped-def` 1종**. 로컬 zero-disable 의 `no-untyped-def` 는 250 → 255 · 366 → 369 로 **관측**될
  것이다(주석이 억제하던 것이 보이게 됨 — 이것은 회귀가 아니라 ① 이 유예한 코드의 정직한 수치. 불변식으로 승격하지
  말 것, 3단계 §7.0).
- 얻는 것 세 가지.
  1. **죽은 억제가 CI 에서 잡힌다.** 누가 `# type: ignore[arg-type]` 를 붙였다가 코드가 고쳐지면 그 주석은 즉시 red —
     지금까지는 조용히 남았다.
  2. **`# type: ignore[no-untyped-def]` 패턴 자체가 red** 가 된다. 유예 코드를 주석으로 덮는 우회가 재발하지 않는다.
  3. `pyproject.toml` 의 `warn_unused_ignores = true` 선언과 게이트가 **일치**한다. 지금은 `disallow_untyped_defs` 와
     같은 모양의 「선언은 켜고 게이트는 유예」가 하나 더 있는 상태다.

### (b) 켜지 않고 유예 2종으로 종결 선언

- 변경: 계획 문서 착지 기록만. 얻는 것 없음. 잃는 것: (a) 의 1·2·3 전부. 선언-게이트 불일치가 `no-untyped-def`(①, 이유
  있음)에 더해 `unused-ignore`(이유 없음)로 둘이 된다. ① 의 이유(탐지력 미증)는 `unused-ignore` 에 적용되지 않는다 —
  `unused-ignore` 는 탐지력을 **재는 도구**다(상위 §2 「그것은 다른 코드들을 재는 도구」).

### (c) 여덟 함수에 애노테이션을 채우고 (a) 를 한다

- zero-disable 수치가 움직이지 않는다는 것이 유일한 장점. 비용: `queue` 는 `multiprocessing.queues.Queue[...]`,
  `request` 는 커널 요청형, `builder` 는 호출 가능 프로토콜, `_seeding_observe` 는 포트 시그니처 복제 — 여덟 자리 모두
  **애노테이션이 새 `arg-type`/`call-arg` 를 부를 수 있는 형상**이고, ① 「623 은 하지 않는다」의 예외를 여덟 만든다.
  하려면 (a) 착지 **뒤** 별건으로.

## 4. PR 모양 — (a) 기준, 하나

1. 여덟 줄 주석 삭제(`sed` 가 아니라 자리마다 확인 — 같은 파일 다른 줄의 `# type: ignore[...]` 는 건드리지 않는다).
2. `tos-firewall.yml` 두 스텝에서 플래그 제거 + 스텝 주석에 「유예 1종 `no-untyped-def`(상위 §6 ①)」 명기.
3. 상위 계획 §7 · 3단계 계획 §7.5 · 핸드오프 §4.1·§6 에 착지 한 줄씩. `docs/plans/INDEX.md` 행 갱신.
4. 리뷰: sonnet 리뷰 레인(저자와 다른 패스) → 판정 PR 코멘트 → `mergeStateStatus == CLEAN` 확인 후 머지.

## 5. 종료조건 · 뮤테이션 — 「이 가드가 실패하는 구체적 입력」

CI 명령(새 플래그 = `--ignore-missing-imports --disable-error-code=no-untyped-def` 만):

| 검사 | 기대 |
|---|---|
| 커널 테스트 트리 | `Success: no issues found in 579 source files` |
| 런타임 테스트 트리 | `Success: no issues found in 221 source files` |
| 소스 스텝 둘 | 무변화 0 / 264 · 0 / 185 |
| 뮤테이션 ① 죽은 억제 | 스크래치로 테스트 파일 한 줄 `_m: int = 1  # type: ignore[assignment]` 추가 → **RED `[unused-ignore]` 1건** → 삭제 후 0 |
| 뮤테이션 ② 우회 패턴 | 여덟 중 한 줄의 `# type: ignore[no-untyped-def]` 를 되살림 → **RED `[unused-ignore]` 1건** → 삭제 후 0 |
| 대조군 | 뮤테이션 ① 의 주석을 실제 오류 위에 두면(`_m: int = "x"  # type: ignore[assignment]`) **조용** — 「사용 중」 억제는 잡지 않는다는 확인 |
| 해당 4 파일 pytest | `tos/tests/sci/test_sci_import_closure.py` `test_sci_records.py` `tos/tests/marketfeed/`(cycle 테스트) `tos/runtime/tests/compose/test_riskstate_wiring.py` 전건 pass — 코드 무변경이므로 풀스위트는 요구하지 않는다 |
| 거버넌스 | firewall · lint-imports · contract(+self-test) · completion GREEN 749 · spec 164/16 · size — 이 PR 이 건드릴 표면이 아니지만 관례대로 |

뮤테이션 둘 중 하나라도 RED 가 안 나오면 플래그 제거가 실제로는 게이트를 켜지 않은 것이다 — 그때는 머지하지 않는다.

## 6. 하지 않는 것

- `no-untyped-def` 채우기(상위 §6 ①) · `pyproject.toml` 선언 변경 · 소스 스텝 변경 · `tos-gate.yml`·`tools/tos_entry_harness.sh`
  접촉(재핀 라운드 아님).
- 여덟 함수 시그니처 변경((c) 는 별건).

## 7. 운영자 확인

| # | 항목 | 추천 | 실제 선택 |
|---|---|---|---|
| ① | (a) 지우고 켠다 / (b) 유예 2종 종결 / (c) 애노테이션 후 (a) | **(a)** | **(a)** — 운영자 확정 2026-09-23 |

## 8. 착지 기록

### 8.1 착지 — PR #788 (2026-09-23, base main `cba90764`)

§4 그대로: 여덟 줄 주석 삭제, `tos-firewall.yml` 두 테스트 트리 스텝에서
`--disable-error-code=unused-ignore` 제거 + 스텝 주석 갱신. §5 실측(재검증, `rm -rf
.mypy_cache` 후):

| 검사 | 기대 | 실측 |
|---|---|---|
| 커널 테스트 트리 | `Success … 579 source files` | `Success: no issues found in 579 source files` |
| 런타임 테스트 트리 | `Success … 221 source files` | `Success: no issues found in 221 source files` |
| 소스 스텝 둘 | 0 / 264 · 0 / 185 | 0 / 264 · 0 / 185 |
| zero-disable `no-untyped-def` | 255 · 369(관측, 불변식 아님) | **255 · 369** |
| zero-disable `unused-ignore` | 0 · 0 | **0 · 0** |

뮤테이션(§5) 전부 재현:

| 뮤테이션 | 기대 | 결과 |
|---|---|---|
| ① 죽은 억제(`test_sci_records.py` 끝에 `_m: int = 1  # type: ignore[assignment]`) | RED `[unused-ignore]` 1건 | **RED 1건 재현** → 되돌린 뒤 0 확인 |
| ② 우회 패턴 복원(`_cycle_children.py:16`) | RED `[unused-ignore]` 1건 | **RED 1건 재현** → 되돌린 뒤 0 확인 |
| 대조군(`_m: int = "x"  # type: ignore[assignment]`) | 조용(0) | **조용 — Success, 0건** → 되돌림 |

해당 4 파일 pytest 전건 pass: 커널(`test_sci_import_closure.py` + `test_sci_records.py` +
`tos/tests/marketfeed`) **341 passed**, 런타임(`test_riskstate_wiring.py`) **29
passed**, 실패/에러 0.

거버넌스: firewall PASS · lint-imports 3 kept/0 broken · contract PASS + self-test
PASS(뮤테이션 145종 전부 판별) · completion GREEN(`planned_unassigned_pairs=749`) ·
spec PASS(`profile_keys=164, profile_null_keys=16`) · size budget PASS(0 violations,
39 등록 예외).

한 가지 파생 변경: 주석이 없어지며 `test_riskstate_wiring.py` 의 `_seeding_observe`
정의 두 곳이 한 줄로 줄어들 수 있는 폭이 되어 `black` 이 재포맷을 요구했다(서명
줄바꿈만 제거, 코드 의미 불변) — 적용 후 `black --check`/`ruff check` 모두 통과.

환경 노트(§7.7 ⑤ 재확인): 루트 venv 에 `tos`/`tos-runtime` editable 설치가 없어 소스
스텝이 처음엔 `tos_runtime` 호출이 커널 타입을 `Any` 로 봐 26건 허위 `no-any-return`
을 냈다. CI 와 동일하게 `pip install -e ./tos[test]` · `pip install -e ./tos/runtime
--no-deps` 로 설치해 재현했고, 측정 종료 후 두 패키지를 `pip uninstall` 로 제거해
공유 루트 venv 를 원상 복구했다(`numpy`/`hypothesis` 버전도 설치 중 잠시 바뀌었다가
`==2.4.2`/`==6.151.9` 로 복원 확인).
