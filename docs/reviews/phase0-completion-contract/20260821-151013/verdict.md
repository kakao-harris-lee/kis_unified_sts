# verdict — 레인 B (계획 심판) · v2.22 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: a0346749934e57b9d48ad5a5980878ecb886c664
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: dcd672f386418d144303a2d5bd3d7fbc673e11377df8d90022afe8623a0d41d8
reviewed_version: v2.22 (계약 8,552행 에라타 6차 재동결 5e96512e · 개발계획 592행 b2985a05 — 이 사이클 무변경) — 동결 8ec22754 · 증거 c477e829 · 에라타 11e138a5(1차~4차)/fd13ca26(5차)/5e96512e(6차) · addendum 4f3cb99d(+에라타 a57c0f4d/79576670)/44aa4aeb(+5f63e740/3b7dad09) · INDEX e25fccb7 · README 93684e72 · 재결속 a0346749
findings: 5                        # high 2 / medium 2 / low 1 — 직전 4건 전건 «해소» · 신규 5
prior_verdict: .omc/review/20260820-082830/verdict.md   # v2.21 재심 (needs-attention · 4건)
mode: B (task --effort high, --background 후 setsid 분리), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: task-mt2ja7m5-zzr8xg / codex thread 01a022e1-d552-7a93-8c7a-046c38758c65
     # status=completed · phase=done · 10m 40s · write=false
     # 모델 식별자는 미확인 (--model 미지정 · companion 로그가 기록하지 않음 — 지어내지 않는다)
```

**모드 B 를 쓴 이유**: 결속 문서 2건이 모두 커밋되어 워킹트리 diff 에 없다
(`git status` = `uv.lock` M · `tools/spikes/` untracked). `adversarial-review --scope working-tree`
는 대상을 보지 못한다.

**결속 검증 — 3중 확인, 드리프트 0**

| 항목 | 주장값 | 재파생 | |
|---|---|---|---|
| `bound_set_digest` | `2643201a…f91a179` | 동일 (오케스트레이터 · 레인 B · Codex 3자 독립) | 일치 |
| 계약 blob | `29a08e5e3c83…` | 8,552행 | 일치 |
| 개발계획 blob | `b2985a05215b…` | 592행 · **직전 결속과 동일** = 계약-단독 사이클 | 일치 |
| `decided_at_head` `93684e72` | 결정 행위 시점 HEAD | HEAD~1 (재결속 커밋 `a0346749` 직전) | 규약 부합 |

Codex 도 `git rev-parse HEAD && git hash-object` 로 결속을 자기 힘으로 재검증한 뒤
"대상 고정은 일치합니다"라고 진술했고, 워킹트리의 대상 밖 변경(`uv.lock`·`tools/spikes/`)을
인지하고 건드리지 않겠다고 명시했다. 진본성 신호: `CLAUDE.md` 비협상 규칙 실독,
직전 정본 판정문 `20260820-082830/verdict.md` 실독.

## 처분 — **채택 5 / 기각 0**

전건 채택한다. 판정을 완화·재구성하지 않았고 severity 를 조정하지 않았다.
아래는 **오케스트레이터의 독립 수용검사**이며, 채택 근거는 Codex 진술이 아니라
재실측이다.

**F#1 (high, `계약:5731` — `workflow_run.path` 완전일치 핀) — 채택.**
Codex 의 문헌 전제를 독립 확인했다: GitHub 공식 문서의 workflow-run 예시 응답이
`"path": ".github/workflows/build.yml@main"` 로 **`@<ref>` 를 포함한다**
(`docs.github.com/en/enterprise-server@3.11/rest/actions/workflow-runs` 실측 —
`rest/actions/workflow-runs` 최신판은 예시 값을 렌더하지 않아 WebFetch 1차에서는
미검출됐다. 문헌 부재가 아니라 **렌더 차이**였다).
**한 가지 정밀화**: Codex 문언은 "문서화된 정상 응답에서 `E=∅`" 라 읽히지만,
이 repo 실측 **1,769 run 전수에서 `@` 포함 0**(`gh api --paginate .../actions/runs`)이다.
즉 과잉 차단은 **도달 가능하나 현재 발화하지 않는다**. 그래도 채택하는 이유는
결함의 정체가 «지금 깨진다»가 아니라 **«미확인 거동에 의존하는 핀»** 이라는 것이고,
이는 계약이 v2.21 3차에서 **스스로 성문화한 규율**(`:5278` — «규정되지 않은 파라미터를
핀하면 «명시»가 아니라 **미확인 거동의 승인**이다», check-runs `filter=latest` 핀을
이 근거로 기각했다)의 **정반대 적용**이다. 같은 판이 한 자리에서 규율을 세우고
다른 자리에서 위반했다. 부수 실측: 같은 필드가 `.github/workflows/` **밖** 값도 갖는다
(1,769 중 1건 `dynamic/copilot-pull-request-reviewer/copilot-pull-request-reviewer`) —
`path` 의 값 공간이 계약의 모델보다 넓다는 독립 증거다.
과잉 차단 방향이라 **fail-open 은 아니지만**, 발화하면 정본 run 이 영구히
`PREVENTION_UNVERIFIED_REVISION` 이 되고 **진짜 개변과 구별되는 관측면이 없다**.

**F#2 (high, `계약:5453` — check-runs 무상한 열거 가정) — 채택.**
공식 문서 verbatim 확인: **"If there are more than 1000 check suites on a single git
reference, this endpoint will limit check runs to the 1000 most recent check suites."**
그리고 처방도 문서가 지정한다: **"To iterate over all possible check runs, use the
List check suites for a Git reference endpoint and provide the check_suite_id parameter
to the List check runs in a check suite endpoint."**
(`docs.github.com/en/rest/checks/runs?apiVersion=2022-11-28`)
이것이 fail-open 인 이유는 `--paginate` 가 **이미 잘린 우주를 끝까지 도는** 것이고,
`total_count` 도 같은 잘린 우주의 값이므로 계약의 완전성 술어
(«수집 수 == `total_count`»)가 **잘림을 관측하지 못한 채 성립**한다는 데 있다.
이 아크가 «vacuous green» 이라 기록해 온 형태 그대로다. 5차 ⓧ 가 열거 완전성을
헤더에서 본문 관측면으로 옮겼으나, **옮긴 관측면도 같은 잘린 우주 안**이다 —
완화가 결함을 도입하지는 않았지만 **닫았다고 주장한 축을 닫지 못했다**.
정직 경계: 한 ref 에 suite 1,000개는 실무상 도달 난망하고(이 repo 실측 4),
이 계약의 관심 대상은 «새로 만든 PR head SHA» 다. 그래도 채택한다 —
계약 문언이 «전수 열거»라는 **전칭 주장**을 하고 있고, 이 아크의 규율은
«전칭 부정은 반례를 본문에서 명시 배제한다» 이다.

**F#3 (medium, `개발계획:270` / `계약:3741` — 예방 통제 4종 rollback 부재) — 채택.**
§12.2 revert 표를 실측했다: 행은 **`P-0` · `D0-A` · `D0-4` · `D0-5` 4개뿐**이고
`.github/workflows/tos-gate.yml` · 하니스 파일 · `u17-verify` · **외부 룰셋**은
어느 행에도 없다. 도입 순서만 고정돼 있다(개발계획 `:282` — 파일 3종 먼저·룰셋 마지막).
중요한 비대칭: 나머지 4단계는 전부 «커밋 revert» 로 처분되는데 **룰셋은 커밋이 아니다**
(GitHub 서버측 상태). §12.2 가 "revert 순서는 구현 역순이다" 라고 규정하면서
그 역순에 룰셋이 없다.

**F#4 (medium, `계약:4414`·`:4437` — 에라타 처분 집계 형제 미전파) — 채택.**
이것이 가장 무거운 채택이다. 지배 소스 `:224` 는 **자기 교정을 이미 기록**했다:
«[2차 ⓢ — 비평 MINOR-11] 1차 문언은 «채택 26 · 명시 기각 1» 이라 적어 **채택을 1
과다 계상**했다 — 27행 중 채택 25(1~21), 명시 기각 1(22), 무변경 판단 1(27)».
`:141` 도 «채택 25». 그런데 `:4414`·`:4437` 은 **정정 전 문언 «채택 26 · 명시 기각 1»
을 그대로 들고 있다**. 즉 MINOR-11 정정이 정의 자리에만 적용되고 **형제 두 자리에
전파되지 않았다** — S-22.
**더 무거운 사실**: 6차 에라타 ⓑ 가 바로 이 문제형에 대해 «자기 문서를 세는 숫자는
그 문서에 두지 않는다» 는 규칙을 **성문화**했고, 그 규칙을 **`:5466` 한 자리에만
적용**했다. 그래서 이 finding 은 v2.22 의 결함이면서 동시에 **6차 에라타 자신의
S-22 실패**다. 이 아크가 «한 자리를 고치고 형제를 남기는 것이 최빈 실패형» 이라고
기록해 온 것의 N 번째 실례이고, 이번엔 **그 실패형을 닫으려고 쓴 규칙 자체가
전파되지 않았다.**

**F#5 (low, `V222:2294` — 뮤테이션 종수 25 vs 26) — 채택.**
표 행을 세었다: `M1 M2 M3 M4 M5 M6 M6b M7 M8 M9 M10 M11 M12 M13 M14 M14b M15 M16
M17 M1b M2b M2c M6c M8b M15b M18` = **26행**. 자체 요약 «판정 뒤집힘 19 / 불변 7»
= **26** 으로 행 수와 일치한다. 제목만 «25종» 이고, 계약 `:141` 이 그 «25/19» 를
재인용한다. 지배값은 행 집합이므로 **26 이 참이고 25 가 오기**다. S-20(내역 병기)
위반이며 모집단 재현 불가.

## 관측 (finding 아님)

- **직전 4건 전건 «해소» 판정**이 이 아크 최초의 «회피 0 · 부분해소 0» 재심이다.
  #1 은 4판 연속 회피/부분 끝에 닫혔고(`검증 → 실행` 순서 + 잡 객체 닫힌 세계 +
  `SHELL_OK` + 전 노드 중복 키 + 자기수복 반사실에서 검증 rc 1·실행 미도달 실측),
  #2 도 3연속 부분해소를 벗어났다. 아크 누적 해소 11 → **15**.
- **D 기준(개발계획 stale) 은 심판·오케스트레이터 독립 이중 확인으로 건전**.
  오케스트레이터 실측: 개발계획이 계약을 인용하는 자리는 라벨 5종(`§12.3.4-R` 39 ·
  `U-17-c` 15 · `D0A-FIRST` 31 · `PREVENTION_ACTIVE` 37 · `u17-verify` 33) +
  값 1종(하니스 sha `957bf49d…` 4행) 이고 전부 HEAD 에서 해소된다. 버전 문자열
  (`v2.2x`)·에라타 표기는 개발계획에 **0건** — 판 번호 드리프트가 구조적으로 불가능하다.
- **6차 ⓓ 의 «층» 축에 다른 형제는 없다**(C 기준). Codex: "추가 e2e-only 오판은
  찾지 못했다". 남은 미실행 축 2개는 F#1·F#2 그 자체다.
- 신규 5건의 분포가 의미 있다: **F#1·F#2 는 «외부 API 의 문서화된 형상·상한»**,
  F#3 은 «외부 서버 상태의 rollback», F#4·F#5 는 «집계 전파». 즉 이 판에서 처음으로
  **결함이 계약 «내부» 논리에서 «repo 밖 경계» 로 이동**했다. 내부 술어 설계는
  6판에 걸쳐 수렴했고, 남은 것은 계약이 **자기 힘으로 검증할 수 없는 외부 사실에
  대한 가정**이다 — 그래서 F#1·F#2 의 최소 교정은 둘 다 «공식 문서 문언을 계약에
  결속하고 경계 대조군을 추가» 형태다.

## Codex 출력 (verbatim — 손대지 않음)

`result.txt` 원문이다. 요약·의역·발췌·재구성하지 않았고 severity 를 조정하지 않았다.

````
## 판정

```yaml
verdict: needs-attention
critical: 0
high: 2
medium: 2
low: 1
```

HEAD `a0346749…`, 두 대상 blob·행수를 확인했다. 파일은 수정하지 않았다.

## Findings

### High

1. `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5731` — workflow `path`의 실제 API 형상을 잘못 고정한다.

   - 결함: `workflow_run.path == ".github/workflows/tos-gate.yml"` 완전일치를 요구한다([계약:5731](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5731)). 실행기도 같은 완전일치다([addendum:3837](/Users/harris/Development/private/kis_unified_sts/docs/reviews/phase0-completion-contract/20260820-184748/U17-PREVENTION-CHECK-V222-ADDENDUM.md:3837)). 그러나 GitHub 공식 응답 예시는 `path: ".github/workflows/build.yml@main"`처럼 `@<ref>`를 포함한다. [GitHub workflow-runs API](https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28)
   - 중요성: 문서화된 정상 응답에서 `E=∅`가 되어 정본 run도 `PREVENTION_UNVERIFIED_REVISION`으로 과잉 차단된다. 증거 fixture는 bare path만 넣어 이 분기를 보지 못했다([V222:349](/Users/harris/Development/private/kis_unified_sts/docs/reviews/phase0-completion-contract/20260820-184748/U17-PREVENTION-CHECK-V222.md:349)).
   - 최소 교정: `@<ref>` 포함 API 값을 정규화하는 단일 규칙을 고정하고, `tos-gate.yml@main` 양성 및 타 workflow 음성 대조군을 추가한다.

2. `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5453` — `--paginate`가 check-runs의 1,000-suite 상한까지 완전 열거한다고 가정한다.

   - 결함: 계약은 `commits/{sha}/check-runs`를 `--paginate`, `per_page=100`, 수집 수=`total_count`로 완전성 증명 대상으로 둔다([계약:5453](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5453), [계약:5513](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5513), [계약:5705](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5705)). GitHub는 한 ref에 check suite가 1,000개를 넘으면 이 endpoint를 최근 1,000개 suite로 제한하며, 전체 순회에는 check-suite 열거 후 suite별 check-run 조회를 요구한다. [GitHub check-runs API](https://docs.github.com/en/rest/checks/runs?source=post_page---------------------------)
   - 중요성: `--paginate`는 이미 잘린 우주만 끝까지 돈다. 잘린 canonical/decoy run이 있어도 `수집 수 == total_count`가 성립할 수 있어 “전수 열거”가 fail-open이다. 인용 증거는 check-runs 8개·suite 4개만 실측하여 상한을 다루지 않는다([addendum:2670](/Users/harris/Development/private/kis_unified_sts/docs/reviews/phase0-completion-contract/20260820-184748/U17-PREVENTION-CHECK-V222-ADDENDUM.md:2670)).
   - 최소 교정: 공식 지침대로 ref의 suite를 전수 열거하고 suite별 check-run을 소비하도록 완전성 계약을 결속하며, `>1000 suites` 경계 대조군을 추가한다.

### Medium

3. `docs/plans/2026-08-11-tos-completion-development-plan.md:270` — pre-D0-A 예방 통제 4종의 실패·rollback 경로가 없다.

   - 결함: 파일 3종을 먼저 두고 외부 룰셋을 마지막에 활성화하는 도입 순서는 고정됐다([개발계획:270](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-11-tos-completion-development-plan.md:270)). 그러나 rollback 표는 P-0/D0-A/D0-4/D0-5만 다루며, `tos-gate.yml`, 하니스, `u17-verify`, 외부 룰셋을 포함하지 않는다([계약:3741](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3741)).
   - 중요성: 부분 도입 또는 룰셋 활성화 뒤 검증 실패 시 무엇을 보존·비활성화하고 어떤 순서로 보호 상태를 재검증하는지 판정할 수 없다. 특히 룰셋은 단순 commit revert 대상이 아니다.
   - 최소 교정: 예방 통제 4종에 대한 실패 시점별 처분과 안전한 역순·종료 검증을 rollback 범위에 명시한다.

4. `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4414` — 에라타 처분 집계가 유일 소스와 갈린다.

   - 결함: 변경 이력의 지배값은 `27 = 채택 25 + 기각 1 + 무변경 1`이다([계약:224](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:224)). 그런데 처분 요약 두 곳은 여전히 `채택 26 + 기각 1`이라고 적는다([계약:4414](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4414), [계약:4437](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4437)).
   - 중요성: S-20의 내역 병기·전수 대조([계약:3139](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3139)), S-22의 요약/처분표 형제 전파([계약:3209](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3209)), S-24 유일 소스 규율을 동시에 위반한다.
   - 최소 교정: 요약 위치에서 처분 수치를 재기술하지 말고 변경 이력의 v2.22 에라타 절만 참조한다.

### Low

5. `docs/reviews/phase0-completion-contract/20260820-184748/U17-PREVENTION-CHECK-V222.md:2294` — 기본 증거의 mutation 종수가 산술적으로 맞지 않는다.

   - 결함: 제목은 25종이지만 실제 행은 M1부터 M18까지 26개이고, 자체 요약도 `뒤집힘 19 + 불변 7 = 26`이다([V222:2314](/Users/harris/Development/private/kis_unified_sts/docs/reviews/phase0-completion-contract/20260820-184748/U17-PREVENTION-CHECK-V222.md:2314), [V222:2341](/Users/harris/Development/private/kis_unified_sts/docs/reviews/phase0-completion-contract/20260820-184748/U17-PREVENTION-CHECK-V222.md:2341)). 계약은 이를 `25/19`로 재인용한다([계약:141](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:141)).
   - 중요성: 결과 자체를 뒤집지는 않지만 S-20이 요구하는 증거 모집단을 재현할 수 없다.
   - 최소 교정: 제외 대상 한 건이 있다면 식별·사유를 적고, 없다면 종수와 모든 소비처를 26으로 정합시킨다.

## A–E 판정

- A — 직전 4건: **확인했고 건전**.
  - #1: 해소. 3연속 회피가 아니다. `검증 → 실행`, `if`/`continue-on-error` 키 부재, `SHELL_OK`, 전 노드 중복 키가 결속됐고, 자기수복 반사실에서 v2.22는 검증 rc 1·실행 미도달을 실제 부작용으로 관측했다([V222:1613](/Users/harris/Development/private/kis_unified_sts/docs/reviews/phase0-completion-contract/20260820-184748/U17-PREVENTION-CHECK-V222.md:1613)).
  - #2: 해소. 더 이상 부분해소가 아니다. 개발계획이 `u17-verify` 소유·도입 순서를 고정했고, `D=∅`에서 `(b-blob)@target` 양성/음성이 실제로 갈렸다([개발계획:275](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-11-tos-completion-development-plan.md:275), [V222:776](/Users/harris/Development/private/kis_unified_sts/docs/reviews/phase0-completion-contract/20260820-184748/U17-PREVENTION-CHECK-V222.md:776)).
  - F#2: 해소. job id·표시 이름·계약 리터럴 및 run별 `hit` 유일성이 함께 고정됐다([계약:6194](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:6194), [계약:6352](/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:6352)).
  - F#4: 해소. 권한·runner·checkout `with`·파서·shell 값에 실제 음성 fixture가 있다([V222:2168](/Users/harris/Development/private/kis_unified_sts/docs/reviews/phase0-completion-contract/20260820-184748/U17-PREVENTION-CHECK-V222.md:2168)).
- B — **결함 있음**. 페이지네이션 완화가 1,000-suite 상한을 닫지 못했고, workflow identity 확장이 `path@ref` 형상을 누락했다. 에라타 집계의 형제 자리도 미전파됐다.
- C — **부분 건전, 결함 있음**. 6차 ⓓ는 최종 동결 후 사다리 단위 및 L3j 격리 실행으로 판별력이 관측됐다([addendum-2:82](/Users/harris/Development/private/kis_unified_sts/docs/reviews/phase0-completion-contract/20260821-0150/U17-PREVENTION-CHECK-V222-ADDENDUM-2.md:82)). 다른 zero-flip 4건도 벨트/구조적 잉여로 귀속되고 결합 mutation이 기록됐다([addendum:523](/Users/harris/Development/private/kis_unified_sts/docs/reviews/phase0-completion-contract/20260820-184748/U17-PREVENTION-CHECK-V222-ADDENDUM.md:523)). 추가 e2e-only 오판은 찾지 못했다. 다만 양성 ACTIVE는 주입 응답 위 SIMULATED 층이고, 공식 `path@ref`와 1,000-suite 경계는 어느 층에서도 실행되지 않았다.
- D — **확인했고 건전**. §6은 4개 선행 산출물, 동일 소유자, 파일 3종 선행·룰셋 마지막 순서를 명시한다. 6차 변경은 검증 관측 방식이지 §6 산출물·순서 변경이 아니므로 개발계획이 stale해지지 않았다.
- E — **결함 있음**. S-20은 두 집계 결함, S-22는 에라타 처분 요약 미전파, S-24는 유일 소스와 요약의 충돌이다. 그 밖의 의미 계약에서는 별도 S-14 중복 정의나 형제 자리 미전파를 찾지 못했다.

## 표준 7항

1. 단계 순서·의존성: **확인했고 건전** — 순환·거짓 병렬 없음.
2. 숨은 가정: **결함 있음** — `path` bare 형상과 check-runs 무상한 열거 가정.
3. 검증 가능성: **결함 있음** — `@ref` 및 `>1000 suites` 대조군 부재, mutation 종수 불일치.
4. 실패·rollback: **결함 있음** — pre-D0-A 예방 통제 4종의 rollback 미정의. 되돌릴 수 없는 단계의 조기 배치는 찾지 못했다.
5. 범위 이탈·과잉 설계: **확인했고 건전** — 별도 단일사용 표면을 추가하는 요구는 찾지 못했다.
6. repo 비협상 규칙: **확인했고 건전**. 설정 구동·DRY·실선물 주문/입금 영구 차단 규칙([CLAUDE.md:19](/Users/harris/Development/private/kis_unified_sts/CLAUDE.md:19), [CLAUDE.md:36](/Users/harris/Development/private/kis_unified_sts/CLAUDE.md:36))과 직접 충돌하지 않는다.
7. 누락: **결함 있음** — GitHub API 공식 형상·상한과 외부 룰셋 rollback 영향 누락.

메모리는 과거 판정의 탐색 경로에만 사용했고, 위 판정 근거는 모두 현재 HEAD·현행 증거·공식 API 문서로 재검증했다.


Codex session ID: 01a022e1-d552-7a93-8c7a-046c38758c65
Resume in Codex: codex resume 01a022e1-d552-7a93-8c7a-046c38758c65
````

## 게이트

```yaml
gate_status: NOT_PASSED
D0_start: BARRED      # 재심 needs-attention — 5건 처분 전 D0/P-0 착수 금지 불변
next: 에라타 7차 (F#1~F#5) → addendum → 재결속 → v2.23 재심
```
