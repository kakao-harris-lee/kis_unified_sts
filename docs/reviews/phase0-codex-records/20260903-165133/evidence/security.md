# 보안 렌즈 증거 — codex-gate 레인 A (재기동 2회차)

- 범위: `git diff 28475ca1^ b5d2448a -- . ':!docs/plans' ':!docs/reviews'` (D0 구현 블록)
- HEAD: `b5d2448a`
- 성격: 판정만 내지 않음. 증거 산출 전용. 저장소 read-only.
- 상태: **완료** (A 하니스 · B u17-verify · C CI/룰셋 · D Python 검사기 · E 격리 사본 실험 · F 시크릿 · G 미확인 · H 집계)

---

## A. `tools/tos_entry_harness.sh` (115행 · in-range diff 있음)

### A-1 [HIGH · in-range 아님(구조 · 전 판부터 존재) · 그러나 이 블록의 게이트 핵심]  승인의 «진정성»은 세워지지 않는다 — git 이력만 세운다

- 위치: `tools/tos_entry_harness.sh:82-95` (R-3/R-4)
- 실측: `VD` 는 `git ls-tree -d --name-only HEAD "$STAMPS/"` 의 사전순 마지막 중 `verdict.md` 를 가진 디렉터리.
  `ADJ`/`VER` 는 그 파일에서 `yaml_scalar adjudicator` / `yaml_scalar verdict` 로 읽은 **평문 markdown 값**이다.
- 서명·HMAC·외부 확인이 없다. 피심판자(저작 에이전트)는 `docs/reviews/phase0-completion-contract/<새 스탬프>/verdict.md`
  에 `adjudicator: codex` / `verdict: approve` / `reviewed_at_head: <HEAD>` / `reviewed_plan_paths:` 두 줄을
  써서 커밋하면 R-3~R-7 을 전부 만족시킨다(R-6 은 `$RH` 가 HEAD 의 조상이기만 하면 되고 HEAD 자신도 조상이다;
  R-7 은 그 이후 BP1/BP2 변경이 공집합이면 통과 — 새 verdict 만 커밋하면 공집합).
- 하니스가 실제로 세우는 것: (i) R-2 의 `bound_set_digest` 재계산 = 계약 본문 **결속**(내용 무결성),
  (ii) R-6/R-7 의 **git 조상성·이후 무편집**(승인의 신선도). 세우지 않는 것: **승인의 발화자**.
- 격리 사본 실증은 아래 §E 에 기록.

### A-2 [MEDIUM · in-range 아님]  R-2 digest 는 «워킹트리»를 읽는다 — R-0 freeze 가 유일한 보호막

- 위치: `tools/tos_entry_harness.sh:62-63` — `printf '%s\0' "$BP1" "$BP2" | sort -z -u | xargs -0 shasum -a 256`
  는 파일시스템(워킹트리)에서 읽는다. 나머지 권위 입력(ART·verdict)은 `git show HEAD:` 로 읽어 HEAD 결속인데,
  digest 재계산만 워킹트리다.
- 보호막은 `:49-51` 의 `git status --porcelain -- BP1 BP2 ART STAMPS` 공집합 요구뿐이다.
  `git update-index --assume-unchanged` / `--skip-worktree` 를 세우면 `git status --porcelain` 은 침묵한다.
- 다만 극성은 **fail-closed 쪽**: 워킹트리를 편집하면 `CALC` 만 바뀌고 `HELD`(=HEAD 의 ART)는 그대로라
  `REBINDING_REQUIRED` 로 막힌다. 실증은 §E-2.
- 메모: 아키텍처 메모리의 «`measured_against.kind=worktree` 가 불변 blob 결속을 무효화»(49차 재심 material)
  와 같은 결함 클래스의 셸 판이다.

### A-3 [MEDIUM · in-range 아님]  R-3 스탬프 열거의 인용 누락 — 단어 분리·글로브

- 위치: `tools/tos_entry_harness.sh:83` — `for d in $(git ls-tree -d --name-only HEAD "$STAMPS/" ... )`
- 명령 치환이 인용되지 않아 IFS 단어 분리와 경로명 확장(글로브)이 걸린다. 스탬프 디렉터리 이름은
  **피심판자가 만든다**(저작 산출물). 공백·`*`·`?` 가 든 이름은 «사전순 마지막» 선택자를 흔들 수 있다.
- 극성: 대체로 fail-closed(쪼개진 이름은 `git cat-file -e "HEAD:$d/verdict.md"` 가 실패 → 그 후보 탈락)
  이나, **더 최신 verdict 를 가리고 더 오래된 것을 선택하게 만드는** 경로가 열린다(`VD` 는 마지막 성공 후보를 유지).
- 권고: `git ls-tree -z` + `while IFS= read -r -d ''` 로 바꾸고 `set -f` 를 두라.

### A-4 [LOW · in-range]  `yaml_scalar`/`yaml_list` 는 YAML 파서가 아니라 «열 0 접두 매치» — 프런트매터로 범위가 한정되지 않는다

- 위치: `tools/tos_entry_harness.sh:28-41` (이번 블록에서 `exit` → `done` 플래그로 교체된 바로 그 함수)
- `$0 ~ "^"k":"` 는 문서 어디든 열 0 에서 시작하는 첫 `verdict:` 를 잡는다. 코드펜스 안, 인용문 안,
  산문 중간의 줄도 동일하게 잡힌다. `!done` 이 «첫 매치만» 을 보존하므로 **문서 상단의 서술문이
  하단의 실제 프런트매터를 이긴다.**
- 이 블록의 변경은 EPIPE 회귀(환경이 판정을 가르는 성질) 수리로 **의도된 것이고 «첫 키만» 의미는 보존**된다.
  보안상 새 결함을 들이지는 않았다. 다만 파서 부재라는 기존 성질은 그대로 남는다.
- 대조: `tools/wfcanon-v222.py` 는 같은 문제를 «자작 토크나이저 폐기 → PyYAML compose + 중복 키 검출»
  로 이미 해결했다(v2.21 심판 처분). 하니스 쪽은 그 처분이 적용되지 않았다.

### A-5 [건전함]  fail-closed 골격

- `:5` `set -u -o pipefail` · `:19-20` `trap ... EXIT` 가 «판정 미산출 종료» 를 `HARNESS_ABORTED`(exit 1) 로 접는다.
- 모든 외부 명령이 `|| emit HARNESS_ABORTED` 를 달고 있다(`:44,49,54,57,62,65,69,92,93,98,103,111`).
- `set -e` 는 없지만 명시적 `||` 로 대체돼 있어 «조용한 진행» 자리는 보이지 않았다.
- `shell=True` 상당의 문자열 조립 없음. 외부 입력이 `eval`/`sh -c` 로 흘러가는 자리 없음.

---

## E. 격리 사본 우회 실험 (실측)

사본: `/private/tmp/claude-503/.../scratchpad/sec-clone`, `sec-fresh`, `sec-ci3`
(`git clone --no-local --no-hardlinks` · 본 워킹트리 무변경). 전부 `b5d2448a` detached.

### E-0 기준선 · 대조군 (검사가 «죽은 검사»가 아님을 먼저 세운다)

```
$ bash tools/tos_entry_harness.sh                      # 무편집 사본
R-3 verdict=docs/reviews/phase0-completion-contract/20260902-195656
d0a_entry_state=ENTRY_OK   rc=0

$ printf '\n<!-- audit control edit -->\n' >> <계약 BP1>; git commit -am ...
$ bash tools/tos_entry_harness.sh
d0a_entry_state=REBINDING_REQUIRED  reason=bound_set_digest 불일치   rc=1
```

대조군 통과 — R-2 는 살아 있고 계약 본문 커밋 편집을 실제로 막는다.
(부수 확인: R-3 이 사전순 마지막 `20260903-073904` 를 고르지 않고 `20260902-195656`
을 골랐다. 전자는 `PHASE0-COMPLETION-JUDGMENT-LIVE.md` 만 갖고 `verdict.md` 가 없다 —
41차 ⓒ 의 «verdict.md 를 가진 디렉터리» 정밀화가 실제로 작동한다.)

### E-1 [CRITICAL 급 · 게이트 우회 성공]  손으로 쓴 6줄 markdown 이 ENTRY_OK 를 낸다

완전 신선 클론(`sec-ci3` · 워킹트리 청정 = **CI 체크아웃 조건**)에서, Codex 를
한 번도 호출하지 않고 다음 파일만 커밋했다:

```
docs/reviews/phase0-completion-contract/20260904-000000/verdict.md
---------------------------------------------------------------
adjudicator: codex
verdict: approve
reviewed_at_head: b5d2448a6b7de7bc0342ddafa216a46569c25453
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
```

결과:

```
R-0 head=a776df3dccc3a59dfa22cdba20d71acb451af929
R-3 verdict=docs/reviews/phase0-completion-contract/20260904-000000
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치   rc=0
```

- **어느 R 단계도 막지 않았다.** 필요한 필드는 넷뿐이고(`adjudicator`·`verdict`·
  `reviewed_at_head`·`reviewed_plan_paths`) 나머지(`job_id`·`reviewed_scope_digest`·
  `bound_set_digest`·`prior_verdict`)는 하니스가 읽지 않는다.
- 코드펜스도 필요 없었다 — 열 0 접두 매치라 평문 6줄로 충분하다(A-4 확증).
- R-6 은 `reviewed_at_head` 가 HEAD 의 «조상»이기만 요구하므로 위조 시점 HEAD 를 그대로 쓰면 된다.
  R-7 은 그 이후 BP1/BP2 를 건드리지 않으면 공집합이다 — verdict 만 커밋하면 자동 충족.
- 하니스가 세우는 것은 **결속(R-2 digest) + 신선도(R-6/R-7 이력)** 이고,
  **발화자(누가 approve 했는가)는 세우지 않는다.**

### E-2 [MEDIUM]  `--assume-unchanged` 는 R-0 freeze 를 눈멀게 한다 (단독으로는 fail-closed)

```
$ git update-index --assume-unchanged <계약 BP1>
$ printf '\n<!-- audit worktree-only edit -->\n' >> <계약 BP1>
$ git status --porcelain -- <계약 BP1>
[]                                        ← R-0 이 침묵한다
$ bash tools/tos_entry_harness.sh
d0a_entry_state=REBINDING_REQUIRED  reason=bound_set_digest 불일치   rc=1
```

R-0 은 우회되지만 R-2 가 잡는다(CALC=워킹트리 편집본 ≠ HELD=HEAD 의 ART). **단독 극성은 fail-closed.**

### E-3 [HIGH]  E-1 + E-2 결합 — HEAD 의 계약 본문이 결속되지 않은 채 ENTRY_OK

1. 계약 본문에 미승인 바이트를 **커밋** (`066f5a4e`)
2. 워킹트리만 승인 바이트로 되돌리고 `--assume-unchanged` (→ `git status` 공집합)
3. `reviewed_at_head=066f5a4e` 인 위조 verdict 커밋

```
d0a_entry_state=ENTRY_OK   rc=0
$ git show HEAD:<계약 BP1> | tail -2
<!-- AUDIT: 승인되지 않은 계약 본문 삽입 -->
```

**ENTRY_OK 가 가리키는 digest `e0729ff3…` 는 HEAD 의 계약 blob 이 아니라 워킹트리 파일의 것이다.**

- **보상 통제 실측**: 같은 HEAD 를 **신선 클론**에서 재판정하면 막힌다.

```
$ (sec-ci: 같은 커밋 fresh clone) bash tools/tos_entry_harness.sh
d0a_entry_state=REBINDING_REQUIRED  reason=bound_set_digest 불일치   rc=1
```

  즉 E-3 의 «분열» 절반은 **로컬 실행 전용**이고 CI(`tos-gate.yml` 의 `actions/checkout`)가
  잡는다. **그러나 E-1 의 «위조 verdict» 절반은 신선 체크아웃에서도 그대로 통과한다** —
  CI 는 보상 통제가 되지 못한다.

### E-4  보상 통제의 실제 위치

- 병합 시점 기계 통제는 룰셋 `tos-gate`(id 21886181, active) 하나이고, 그것이 요구하는 것은
  «`tos-gate` 라는 이름의 Actions 체크가 success» 다. 위조 verdict 를 담은 PR 은 그 체크를 **통과한다**.
- `required_approving_review_count: 0` (실측, 아래 §C) — 병합 시점에 사람이 없다.
- 따라서 E-1 의 유일한 실효 보상 통제는 **운영자의 수동 `git push`**(기계 표면 밖의 운영 관행)다.

---

## B. `tools/u17-verify.sh` (917행 · in-range 델타 = LIT2 sha 1줄)

### B-1 [건전함 · 이례적으로 견고]  gh 응답 소비는 전 지점 fail-closed

- `:105-108` `respond()` 는 `gh api -i` 의 **상태 줄을 파싱**해 `$CAP/<key>.status` 에 보존하고,
  3자리 숫자가 아니면 `ERR` 로 접는다. 헤더(`.hdr`)와 본문(`.bd`)을 분리 보존한다.
- `:144-145` `http_of` / `ok2xx` 로 **ERR(네트워크·인증) 과 비-2xx(서버 응답) 를 구분**하고,
  전자는 `PREVENTION_UNVERIFIABLE`, 후자는 상황에 따라 `UNVERIFIABLE`/`UNVERIFIED_REVISION` 으로
  구분해 발화한다(`:410-411`, `:418-419`, `:514-515`, `:572-573`, `:609-610`, `:638-639`, `:866-867`).
  «조회 실패 → 검사 생략» 자리를 찾지 못했다. `fire`/`emit` 호출 95개.
- `:350` `unverifiable(st)` = `st=="ERR" or (숫자 ∧ 404 아님 ∧ 2xx 아님)` — 404 만 «부재» 로,
  나머지 오류는 «판정 불가» 로 분리한다.
- **열거 상한**: `:586` 은 `head_sha` 질의의 1,000-결과 문서화 상한 도달을 `PREVENTION_UNVERIFIABLE`
  로 접는다. `--paginate --slurp` 로 페이지 수 N 을 본문에서 관측하고 `?page=N+1` 종단 프로브를
  붙여 «silent cap» 을 구별한다(`:130-163` `observe_delta` · `:159` 마지막 페이지가 정확히
  `per_page` 면 «구별 불가» 로 정직하게 미관측 처리).
- **서버 시각 우선**: `:891` 은 `merged_at` 등 «서버 부여 값만» 쓰고 커밋 author/committer date 를
  명시적으로 불신한다. `:906-907` 은 룰셋 `created_at`/`updated_at` 이 `t_land` 보다 뒤면 차단한다.
  이 극성이 옳다 — 커밋 시각은 피심판자가 자유롭게 정한다.

### B-2 [건전함]  토큰 유출 없음

```
$ gh auth status --hostname github.com          # :66 이 그대로 transcript 에 찍는 것
  ✓ Logged in to github.com account kakao-harris-lee (keyring)
  - Token: gho_************************************
  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
```

`--show-token` 을 쓰지 않아 토큰은 마스킹된다. `:135` `reqid()` 는 `X-GitHub-Request-Id` 만
추출하고, `show_capture` 는 `.body` 만 인쇄한다(`.hdr` 전문은 인쇄하지 않는다). 응답 헤더에
`Authorization` 은 없다. 범위 전체 grep(`ghp_|gho_|ghs_|github_pat_|Bearer|GH_TOKEN|--show-token`)
에서 실 토큰 0건.

### B-3 [LOW · in-range 아님]  `$PYBIN` 하드코딩 절대 경로 — 극성은 fail-closed 이나 상태 귀속이 틀린다

- `:77` `PYBIN="${U17_PYBIN:-/Users/harris/Development/private/kis_unified_sts/.venv/bin/python}"`
  — 특정 사용자 홈의 venv 절대 경로가 기본값이다(메모리의 기지 부채 ⑤).
- 실측 극성: 인터프리터가 없으면 `WFOUT` 이 셸 오류 문자열이 되고 `RESULT=` 가 비어
  `case` 의 `*)` 로 떨어진다 → `PREVENTION_UNVERIFIED_REVISION`(`:849`, `:874`).
  **판정은 통과하지 않는다(fail-closed).**
- 결함은 «상태의 정직성»: 도구를 못 돌린 것은 `UNVERIFIABLE` 이지 «워크플로가 개정됐다»가 아니다.
  같은 `case` 에 이미 `UNVERIFIABLE` 분기가 있으므로 빈 `RESULT` 는 그쪽으로 보내야 한다.

### B-4 [LOW · in-range 아님]  임시 자산 미정리 — 전 저장소 클론이 `$TMPDIR` 에 누적

- `:92` `CAP=$(mktemp -d)` (API 응답 본문·헤더 전량) · `:191` `SNAPBASE=$(mktemp -d)` +
  `git clone --no-local` = **저장소 전체 사본**. `:87` 의 `trap ... EXIT` 는 «판정 방출» 만 하고
  정리하지 않는다. 실행할 때마다 클론 하나가 남는다.
- `mktemp -d` 라 0700 이고 심볼릭 링크 선점은 없다. 심각도는 낮으나 반복 실행 시 디스크·잔류 데이터.

### B-5 [LOW · 정보]  `respond()` 의 awk 조기 `exit` — 하니스가 방금 고친 EPIPE 결함 클래스와 동형

- `:105` `printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"`
- 진입 하니스에서 «환경이 판정을 가른다»며 제거한 바로 그 패턴(`tos_entry_harness.sh:22-27` 주석)이
  여기 남아 있다. **현재는 무해하다** — 이 파이프라인의 종료 상태를 아무도 읽지 않는다.
  `set -e` 가 추가되거나 이 문장이 `||` 절에 들어가는 순간 gawk 환경에서만 발화한다.

---

## C. CI 워크플로 · 룰셋 (in-range: test.yml +43 · tos-firewall.yml +11 · tos-gate.yml sha 1줄)

### C-1 [HIGH · 구조 · in-range 아님]  병합 시점 게이트의 «정의»가 피심판 PR 안에 있다

실측(GET):

| 항목 | 값 |
| --- | --- |
| 활성 룰셋 | `tos-gate` (id 21886181) — `protect_main`(17017682) 은 `enforcement: disabled` |
| required check | context `tos-gate`, integration_id 15368 (Actions 앱) |
| required_approving_review_count | **0** |
| bypass_actors | `[]` · `current_user_can_bypass: never` |
| 기타 | `non_fast_forward`, `deletion`, `strict_required_status_checks_policy: true` |

- 룰셋이 보는 것은 **체크의 «이름»과 «생성 앱»** 뿐이다. `integration_id` 핀 덕분에 외부 상태 API 위조는
  막히지만, `tos-gate` 를 **무엇이 산출하는가**는 `pull_request` 이벤트 규칙상 **PR 자신의
  워크플로 파일**이 정한다.
- `.github/workflows/` 를 보호하는 것이 없다: **CODEOWNERS 부재**(`.github/CODEOWNERS` 없음),
  경로 기반 룰 부재, 필수 승인 0.
- 보상 통제인 «정본 잡 템플릿 대조»(`tools/wfcanon-v222.py` — `permissions`·`runs-on`·체크아웃 `with`·
  steps 순서·`continue-on-error` 키 부재·중복 키까지 byte 단위로 핀)는 **CI 에서 돌지 않는다**:
  `grep -rn "wfcanon|u17-verify" .github/workflows/` 는 test.yml 의 **주석과 yq 핀 스텝**만 잡고,
  실행 스텝은 `tests/tools/test_u17_verify.py`(주입 응답 기반 단위 테스트)뿐이며 그 `Tests` 워크플로는
  required check 도 아니다.
- 즉 정본 대조는 **운영자가 손으로 돌리는 사후 증거 실행기 안에만** 있다.
- **미실행 확인**: 실제로 워크플로를 무력화한 PR 을 올려 검증하지는 않았다(GET-only 제약·푸시 금지).
  근거는 룰셋 실측 + 워크플로 트리거(`on: [pull_request]`) + CI 호출 부재의 조합이다.

### C-2 [MEDIUM · in-range 가 확장]  `tos-firewall.yml` 에 `permissions:` 블록이 없다

- `.github/workflows/tos-firewall.yml:20-27` — 잡·워크플로 어느 층에도 `permissions:` 가 없다.
  같은 블록의 `tos-gate.yml:3-4` 는 `permissions: contents: read` 를 명시한다.
- 이 잡은 `pip install -e "./tos[test]"` 와 `pytest` 로 **PR 의 코드를 실행**한다(`:57-77`).
- 완화 실측: 저장소 기본값이 최소 권한이다.

```
$ gh api repos/kakao-harris-lee/kis_unified_sts/actions/permissions/workflow
{"default_workflow_permissions":"read","can_approve_pull_request_reviews":false}
```

- 따라서 현재는 read 토큰이다. 그러나 그 보호는 **저장소 설정 한 번의 변경으로 사라지고**
  워크플로 파일에는 흔적이 남지 않는다. in-range 변경이 이 잡에 검사기 스텝 둘을 **추가**하면서
  권한 핀은 함께 넣지 않았다.

### C-3 [MEDIUM · in-range 가 접촉]  액션 sha 핀이 게이트 워크플로에만 있다

- 핀됨: `tos-gate.yml:10` `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` +
  `persist-credentials: false` + `fetch-depth: 0` — **이 블록에서 가장 잘 하드닝된 자리**.
- 태그 참조(가변): `tos-firewall.yml:27,43` · `test.yml:34,46,121,134,…` · `devcontainer.yml` ·
  `docker.yml` 전부 `@v4`/`@v5`/`@v3`. 태그는 이동 가능하므로 액션 소유자·계정 탈취 시 공급망 경로가 된다.
- in-range 변경(`test.yml:34-42`)이 바로 그 checkout 스텝에 `with: fetch-depth: 0` 을 **추가하면서**
  sha 핀은 하지 않았다. `persist-credentials: false` 도 없다.

### C-4 [건전함]  `test.yml` 의 yq 설치는 체크섬 검증 후 설치한다

- `.github/workflows/test.yml:87-96` — `curl` 로 받은 바이너리를 `sha256sum -c` 로 대조한 **뒤에만**
  `sudo install` 한다. 릴리스 체크섬 출처를 주석에 남겼다. 다운로드-실행 패턴의 올바른 형태다.
- 파서 버전 핀 자체가 fail-closed(`wfcanon-v222.py:140-148` `yq_version_gate` — 더 «새» 버전도 거부)
  라 임의 PATH 의 파서를 조용히 신뢰하지 않는다.

---

## D. Python 검사기 (`tools/*.py`)

### D-1 [건전함]  역직렬화·명령 주입 표면 없음

- `eval` / `exec` / `pickle` / `os.system` / `shell=True` **0건** (범위 6개 파일 전수 grep).
- YAML: 전부 `yaml.safe_load` (`tos_completion_status.py:242,361` · `tos_spec_status.py:1152,1324,1399`).
  `tos_evidence_run.py:1611` 의 `yaml.load` 는 `Loader=_NoDuplicateKeySafeLoader` 이고
  그 클래스는 `:1527` 에서 **`yaml.SafeLoader` 를 상속**한다 — 중복 키를 last-wins 로 접지 않고
  거부하려는 강화이지 약화가 아니다.
- `wfcanon-v222.py:168` 은 `yaml.compose()` — 노드 트리만 만들고 `construct` 를 부르지 않는다.
  객체 생성이 없으므로 태그 기반 역직렬화 표면이 원천적으로 없다.
- `subprocess` 전 호출이 **리스트 인자**다: `tos_completion_status.py:337,680,1343` ·
  `tos_contract_index.py:538` · `tos_spec_status.py:1712` · `wfcanon-v222.py:143,225`.
  신규 `git ls-files -z --cached --others --exclude-standard` 도 리스트 인자에 `-z` NUL 분리라
  파일명 인젝션이 없다.

### D-2 [건전함]  CSV/데이터 유래 경로에 실제 순회 방어가 있다

- `tos_completion_status.py:562-566` (`_resolve_path_line_basis`) — `./` 접두 · 절대경로 ·
  `..` 조각을 전부 거부한 뒤에만 `repo_root / rel` 을 만든다.
- `:600-621` (`_check_package_ref`) — 위에 더해 백슬래시·중복 슬래시를 거부하고,
  **`resolve()` 후 `relative_to(repo_root.resolve())` 로 심볼릭 링크의 저장소 이탈까지 잡는다**.
  대소문자·정규화 불일치도 거부한다. 이 자리는 잘 되어 있다.
- 이 방어가 필요한 이유가 in-range 에 실재한다: `EVIDENCE-SURFACE-MAP.csv`(2,024행 신규)의
  `binding_basis` 열이 곧 파일 경로다.

### D-3 [LOW · in-range]  `_resolve_path_line_basis` 만 심볼릭 링크 이탈을 보지 않는다

- `:562-576` 은 `..`·절대경로는 막지만 `_check_package_ref` 가 하는 `resolve()`+`relative_to` 대조가 없다.
  저장소 안의 심볼릭 링크가 밖을 가리키면 그 파일을 읽는다.
- 영향은 «읽고 그 행에 evidence_id 리터럴이 있는지» 만 판정하는 **존재 오라클**에 그치고,
  입력 CSV 는 커밋된 저장소 데이터다. 그래도 두 해석기가 같은 방어를 갖는 편이 낫다.

### D-4 [MEDIUM · in-range]  워크트리 기준 digest 재계산이 Python 쪽에도 복제돼 있다

- `tools/tos_completion_status.py:418-430` `_compute_bound_set_digest_worktree` —
  «§12.3.4-R 좌변 규율» 을 따라 **의도적으로** 워킹트리 파일을 읽는다(`(repo_root / p).read_bytes()`).
- A-2/E-3 과 같은 성질이 검사기에도 있다. 하니스와의 정합을 위한 의도적 선택이므로 결함이라기보다
  **동일 위험의 두 번째 소재지**로 기록한다. E-3 의 신선-체크아웃 보상 통제가 여기에도 똑같이 적용된다.

### D-5 [건전함 · 실측]  세 검사기 모두 워킹트리를 변조하지 않는다

격리 클론(`sec-st` @ `b5d2448a`)에서 실행 전후 `git status --porcelain` 대조:

```
BEFORE: 0 dirty
$ .venv/bin/python tools/tos_contract_check.py --self-test     rc=0
  self-test: PASS — 뮤테이션 145종 전부 판별 · 죽은 검사 0 · 앵커 불일치 0 ·
             역방향 과잉 차단 0 · 대조군 무효 0 · 분류기 대조군 2종 전건 통과
$ .venv/bin/python tools/tos_spec_status.py --check             rc=0  (TOS spec status PASS)
$ .venv/bin/python tools/tos_completion_status.py --check       rc=0  (RESULT: GREEN, violations=0)
AFTER:  0 dirty
```

- 뮤테이션은 파일이 아니라 **메모리 내 문자열 치환**이다(`tos_contract_check.py:4143`
  `def _mutate(text: str) -> str` · `:4125,4590,4597,4728` 전부 `text.replace(...)`).
  임시 사본조차 필요 없다 — 원상복구 실패 위험이 구조적으로 없다.
- 부수 관측(보안 아님): 메모리에 기록된 «심판 self-test 4회 연속 rc 2» 는 현행 HEAD 에서 해소됐다.

---

## F. 시크릿 위생 (범위 내)

- `.gitignore` 가 `.kis_token_real`/`.kis_token_mock`(`:78-79`) · `.env*`(`:12-21`) ·
  `*.secret`/`.api_key.secret`(`:119-120`) · `scripts/cron/`(`:68`) · `.omc/`(`:5`) 를 덮는다.
- 추적 중인 시크릿 파일 0건 (`git ls-files | grep -iE '\.env$|kis_token|credential|secret'` 의 3건은
  `shared/config/secrets.py`·그 테스트·ADR 문서로, 시크릿이 아니라 시크릿을 다루는 코드다).
- 범위 34파일 전수 grep(`ghp_|gho_|ghs_|ghu_|github_pat_|Bearer |Authorization|GH_TOKEN|api_key|password`)
  에서 실제 자격증명 **0건**. 매치는 전부 `**Production Authorization:**` 헤더 문자열이다.
- `config/tos_completion.yaml`(57행 신규)에 시크릿·내부 URL·계정 없음. 임계값·앵커·`DEADLINE_UNSET` 뿐.
- CLAUDE.md 비협상(«실계좌 선물 영구 차단»·Redis DB 1)에 저촉하는 변경 없음 — 이 블록은
  거버넌스 검사기·CI 게이트·gh 조회 실행기이고 주문 경로·브로커 자격증명을 건드리지 않는다.

---

## G. 미확인 항목 («미발견» 이 아니라 «확인하지 않았다»)

1. **C-1 의 실 PR 재현**: 워크플로를 무력화한 PR 이 실제로 `tos-gate` 를 success 로 만들고 병합
   가능해지는지 **실행하지 않았다**(GET-only·푸시 금지). 룰셋·트리거·CI 호출 부재의 구조 근거만 제시한다.
2. **`tools/ladder-v222e5.py` · `tools/pagelimb-v222e5.py`**: `u17-verify.sh` 가 호출하는 술어이나
   심사 범위(34파일) 밖이라 읽지 않았다. 열거 완전성·4단 사다리 판정의 실제 술어가 그 안에 있다.
3. **`tools/tos_contract_check.py` 본문**: self-test 를 «실행»해 워킹트리 불변과 rc=0 은 실측했으나,
   145종 뮤테이션이 실제로 판별력을 갖는지 **대조군을 직접 만들지는 않았다**(메모리의
   «대조군 없는 심사는 의견이다» 규율상 이 한계를 명시한다).
4. **`u17-verify.sh` 전문 정독**: 917행 중 responder seam(`:100-145`)·스냅샷 기층(`:184-210`)·
   HTTP 처리 전 지점·(b)③ blob/server 층(`:830-880`)·연속성 α(`:885-910`)를 읽었다.
   E₀ 파생(`:340-400`)과 β 축(`:730-770`)은 grep 수준으로만 확인했다.
5. **의존성 취약 버전**: 이 블록은 새 서드파티 의존을 도입하지 않는다(추가된 것은 CI 의 yq 바이너리
   핀 하나이고 체크섬 검증됨). 저장소 전체 의존성 감사는 하지 않았다.
6. **`tos/src/tos/**` 7파일**: docstring 전용 변경임을 diff 로 확인했고 실행 의미 변화 없음.
   `tos/tests/spg/test_spg_replay_substrate.py`(291행 신규)는 테스트 픽스처라 렌즈 대상에서 제외했다.

---

## H. 요약 — severity 별 집계

| severity | 개수 | 항목 |
| --- | --- | --- |
| CRITICAL | 1 | E-1 (위조 verdict.md → ENTRY_OK · 신선 체크아웃에서 재현) |
| HIGH | 3 | A-1 (승인 진정성 미확립 · E-1 의 구조 근거) · E-3 (HEAD 계약 미결속 ENTRY_OK) · C-1 (게이트 정의가 피심판 PR 안) |
| MEDIUM | 5 | A-2 · A-3 · C-2 · C-3 · D-4 |
| LOW | 5 | A-4 · B-3 · B-4 · B-5 · D-3 |

**in-range 신규 취약점: 0.** 위 전부가 이 블록이 «물려받은» 또는 «접촉했으나 고치지 않은» 구조 성질이다.
in-range 변경 자체(awk EPIPE 수리 · sha 재핀 · CI 검사기 편입 · yq 핀 · fetch-depth)는
전부 **fail-closed 방향**이고 새 공격 표면을 열지 않는다.

**렌즈의 한 줄**: 이 블록은 «계약 본문의 무결성»과 «승인의 신선도» 를 매우 견고하게 세운다.
세우지 않는 것은 **승인의 발화자**다 — 그래서 피심판자가 심판의 서명을 대신 쓸 수 있고,
격리 사본에서 6줄로 실증된다. 그 자리를 메우는 것은 현재 기계가 아니라 운영자의 수동 push 다.
