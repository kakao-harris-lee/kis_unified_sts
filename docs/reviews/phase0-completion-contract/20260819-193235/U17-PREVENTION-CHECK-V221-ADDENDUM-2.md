# U17-PREVENTION-CHECK-V221-ADDENDUM-2 — S-24 재결속 (v2.21 **에라타 2차 재동결 `7adc1246`** · 정본 «잡» 템플릿)

- **비규범 부속**. 계약·개발계획을 바꾸지 않는다. 선행 증거 `U17-PREVENTION-CHECK-V221.md`(`3e0f2429`)·`…-ADDENDUM.md`(`83f12afd`)는 **(4d) 불변** — 재결속은 이 파일로 한다.
- 생성 UTC `2026-08-19T13:17:33Z` · 서버 쓰기·설정 변경 **0** · GitHub 는 **GET-only**(사후 재조회 1회 · §6) · 픽스처는 scratchpad **독립 git 저장소**.

## 0. 결속 선언 (실측 §6 원문)

| 항목 | 실측 |
| --- | --- |
| HEAD | `7adc1246bee6313021f601abe3ad82ac9e2a1e09` == `7adc1246` |
| 계약 워킹트리 blob | `081b9bc34182beff9cfa01f01031896835dbaf2a` == `git show 7adc1246:<계약>` |
| 개발계획 blob | `4b2f664f835c4f3c68e4dff8560214aaa70f8969` == `0528a919` 동결본 (**에라타 2차에서도 무변경**) |
| `7adc1246..HEAD` | 두 문서 커밋 **0** · 전체 커밋 **0** |
| 하니스 `sed -n '4664,4764p'` | sha256 `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d` — 계약 리터럴 일치 ∧ `65cf2635` 와 **byte-동일** |
| 계약 행수 | 7,551 (인라인 +36/-16 대비 `65cf2635`) |

## 1. S-24 ① — 무엇이 바뀌었고, 무엇이 닿지 않았나

### 1-1. 계약 차분 원문 (`git diff -U0 65cf2635..7adc1246 -- <계약>`)

```diff
diff --git a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
index 2660b800..081b9bc3 100644
--- a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+++ b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
@@ -130 +130 @@
-> | **v2.21** | **재심 미착수.** v2.20 판정 2건(#1 U-17 (b)③ 회피 — «정본 대조» 재설계[1차 (iii) AST 는 독립 검증 C FAIL] · #2 #5/#6 비순환 생산 순서)을 반영한 판이며, **개발계획에 하니스 파일 실체화 한 줄 추가**(운영자 승인 (D) 개정의 연장). **동결(`0528a919`) → 증거(`3e0f2429` — 정본 대조 22픽스처 0 불일치·문언 에라타 ⓐ 적발) → 에라타 재동결(문언·과잉 차단 방향) → 운영자 재결속(현행 사이클)** 대기다. 재결속 전에는 심사를 요청하지 않는다(§12.3.2) |
+> | **v2.21** | **재심 미착수.** v2.20 판정 2건(#1 U-17 (b)③ 회피 — «정본 대조» 재설계[1차 (iii) AST 는 독립 검증 C FAIL] · #2 #5/#6 비순환 생산 순서)을 반영한 판이며, **개발계획에 하니스 파일 실체화 한 줄 추가**(운영자 승인 (D) 개정의 연장). **동결(`0528a919`) → 증거(`3e0f2429` — 정본 대조 22픽스처 0 불일치·문언 에라타 ⓐ 적발) → 에라타 재동결 → **stop-time BLOCK(`65cf2635` — ⓑ 잡 수준 실행 무력화)** → 에라타 2차(정본 «잡 템플릿» 확장) → 운영자 재결속(현행 사이클)** 대기다. 재결속 전에는 심사를 요청하지 않는다(§12.3.2) |
@@ -213 +213 @@
-| **v2.21** | **v2.20 심판 판정 2건(high 1 / medium 1) 전건 반영. 직전 처분은 «#1 회피 · #2·#3·#4 해소(아크 누적 11) · #5/#6 부분» 이다.** ① **#1 U-17 (b)③ (high, 회피) — 정본 대조 재설계**: v2.20 구조 파서+서버 스텝이 «토큰 존재·이름/conclusion»만 인증해 `|| true`·`set +e`·`false && bash tools/…`·`exit 0; bash tools/…`(선행 종결자) 도달 불가 호출이 전부 `PREVENTION_ACTIVE`. **1차 (iii) 셸 AST 요건은 독립 검증 C FAIL**(B10 `set -euo pipefail; exit 0; bash …`·B11 `exec true`·B12 `[ ] && exit 0` — «선행 종결자»를 「`&&` 피연산자」 규칙이 미포섭·런타임 미실행 실증) → 폐기. **운영자 «바퀴 재발명 금지» 지침(CLAUDE.md Development Discipline) 적용해 «정본 대조»로 재설계**: 게이트 두 스텝 `run:` 을 정규화(CRLF→LF·trailing 공백·빈 줄·full-line 주석 제거) 후 계약 «정본»(정본 A `set -euo pipefail` + `bash tools/tos_entry_harness.sh` / 정본 B `set -euo pipefail` + `printf %s…\n <sha> | shasum -a 256 -c -`)과 byte 대조 — 다르면 UNVERIFIED_REVISION. 정본 대조는 «정본과 다르면 전부»라 exit/exec/가드/서브셸/heredoc/eval/무효화/선행 종결자 전 구문 우회를 «열거 없이» 닫는다(열린→닫힌 세계·S-6). YAML 파싱+byte 대조 = 기존 도구·자작 파서/도달성 분석기 불요. 스텝 메타(shell·continue-on-error·if·timeout)는 닫힌 키 집합. 정본 B 는 sha 불일치 시 `shasum -c` 비-0→`set -euo pipefail` 스텝 실패로 실패 전파 보장(실측 정상 OK/0·변조 FAILED/1). **T-84 ⑬ 재편 = «정본 불일치 클래스»**(⑬a echo·⑬b trailing 주석·⑬c `|| true`·⑬d 도달 불가 호출·⑬e continue-on-error/if·⑬f set +e/trap·**⑬g 선행 종결자**·전부 정본 불일치→UNVERIFIED_REVISION·종수 불변) + 양성(정본 일치) + 정규화 대조군(주석/공백만 다르면 일치). **정직 경계**: 정본 일치 ≠ 런타임 실제 실행(선행 스텝 `PATH`/`env` 조작·GitHub 내부·스텝 이름 위조 — 위조 비용↑·닫지 못함). ② **#2 #5/#6 부분 (medium) — 비순환 생산 순서**: 활성 UNCHK-008 owner_track 이 `Phase 1`·U-17 하니스 경로가 «D0-A 산출물»이라 Phase 0 가 PREVENTION_ACTIVE 를 소비하기 전에 그 축·하니스를 누가 산출·폐쇄하는지 단일 비순환 순서 부재((D) verbatim 적용이 활성 형제 소비처 미전파·S-22). **UNCHK-008 owner_track `Phase 1`→`Phase 0`**(D0-A 착수 전 선행조건·운영자/인프라·U-17 live 검증·문법 n∈0..7 유효·imprecise_owner_track 불변[단일 phase])·산문 2곳(:4975·:5102) 전파 · **U-17 하니스 «D0-A 산출물»→«pre-D0-A 실체화»**(§12.3.4-R 결속값 sha 957bf49d… 파일 실체화·D0-A 착수 «전» 운영자/인프라가 둔다) · **개발계획 Phase 0 선행조건 불릿에 하니스 파일 실체화 한 줄 추가**(운영자 승인 (D) 개정의 «연장»·같은 대상·같은 pre-D0-A 주체·(D) ②′ verbatim 재기록). **S-22 전수**: «D0-A 산출물» 표기 중 하니스 파일(:5462)만 정정(U15-ENTRY-CHECK·config·원장·계약텍스트는 유지)·UNCHK-023(브랜치 보호 계열이나 git 이력 신뢰 별개 축이라 `Phase 1` 유지)·형제 UNCHK 행 재독. **종수 전파(S-20)**: T-84 14 불변(⑬c 검출 전환·⑬d/e/f 는 ⑬ 하위 케이스)·T-82 20·T-81 19·U-17-c 10값·U-16-d 12단 불변. **§12.3.3**: (A)=v2.20 판정 5건 리터럴(회피 1·해소 3·부분 1)·(B)=v2.21 2건 주장(«어느 것도 해소 아님»·#1 실행 증거 동결 후·#2 형제 전파+개발계획 연장)·(D) 갱신(②′ 연장). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`·현행 :4664-4764)·`bound_paths` 2건(계약+개발계획) 편집이므로 O-6 재결속 필요.** **[v2.21 에라타 (동결 `0528a919` 후 증거 실행 `3e0f2429` 적발 — 재결속 전이므로 정정 후 재동결·문언·과잉 차단 방향·fail-open 0)]** 증거(`U17-PREVENTION-CHECK-V221.md`)가 정본 대조 22픽스처 기대 불일치 0(⑬a~⑬g·⑬g B10/B11/B12 사멸·정본 B 런타임 OK/FAILED 전파·#2 순서)이되 문언 결함 후보 1건을 적발했다: **ⓐ E1(P-2·문언·과잉 차단)** 정규화 규칙이 YAML 스칼라 «표기»를 미언급 — 스텝 A(2줄)는 folded `>`+빈 줄이면 우연히 일치하나 **스텝 B(단일 파이프라인)를 `>` folded 로 쓰면 두 줄이 접혀 정본 불일치** → 정직한 워크플로도 red. → 정규화 규칙에 «정본 `run:` 은 literal block scalar(`|`) 표기 전제·`>` folded·인라인은 불일치=fail-closed·작성자는 `|` 사용» 명시(극성: 과잉 차단은 «표기 지정»으로 해소·S-15)·T-84 ⑬ 정규화 대조군을 «`|` 표기 + 주석/빈 줄 차이만»으로 정정(folded 는 A 에만 성립·B 불일치 명시). **종수 불변**(문언). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`·:4664-4764)·개발계획 무편집·`bound_paths`(계약만) 재동결.** **증거 결속(S-24)**: 이 에라타 재동결도 addendum 으로 이행(절 범위 `git diff` 공집합 + 영향 변이 재실행 — 스텝 A/B `|` 양성·`>` folded→B 불일치(계약대로 red)·A folded+빈 줄 일치 문언 정합). **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
+| **v2.21** | **v2.20 심판 판정 2건(high 1 / medium 1) 전건 반영. 직전 처분은 «#1 회피 · #2·#3·#4 해소(아크 누적 11) · #5/#6 부분» 이다.** ① **#1 U-17 (b)③ (high, 회피) — 정본 대조 재설계**: v2.20 구조 파서+서버 스텝이 «토큰 존재·이름/conclusion»만 인증해 `|| true`·`set +e`·`false && bash tools/…`·`exit 0; bash tools/…`(선행 종결자) 도달 불가 호출이 전부 `PREVENTION_ACTIVE`. **1차 (iii) 셸 AST 요건은 독립 검증 C FAIL**(B10 `set -euo pipefail; exit 0; bash …`·B11 `exec true`·B12 `[ ] && exit 0` — «선행 종결자»를 「`&&` 피연산자」 규칙이 미포섭·런타임 미실행 실증) → 폐기. **운영자 «바퀴 재발명 금지» 지침(CLAUDE.md Development Discipline) 적용해 «정본 대조»로 재설계**: 게이트 두 스텝 `run:` 을 정규화(CRLF→LF·trailing 공백·빈 줄·full-line 주석 제거) 후 계약 «정본»(정본 A `set -euo pipefail` + `bash tools/tos_entry_harness.sh` / 정본 B `set -euo pipefail` + `printf %s…\n <sha> | shasum -a 256 -c -`)과 byte 대조 — 다르면 UNVERIFIED_REVISION. 정본 대조는 «정본과 다르면 전부»라 exit/exec/가드/서브셸/heredoc/eval/무효화/선행 종결자 전 구문 우회를 «열거 없이» 닫는다(열린→닫힌 세계·S-6). YAML 파싱+byte 대조 = 기존 도구·자작 파서/도달성 분석기 불요. 스텝 메타(shell·continue-on-error·if·timeout)는 닫힌 키 집합. 정본 B 는 sha 불일치 시 `shasum -c` 비-0→`set -euo pipefail` 스텝 실패로 실패 전파 보장(실측 정상 OK/0·변조 FAILED/1). **T-84 ⑬ 재편 = «정본 불일치 클래스»**(⑬a echo·⑬b trailing 주석·⑬c `|| true`·⑬d 도달 불가 호출·⑬e continue-on-error/if·⑬f set +e/trap·**⑬g 선행 종결자**·전부 정본 불일치→UNVERIFIED_REVISION·종수 불변) + 양성(정본 일치) + 정규화 대조군(주석/공백만 다르면 일치). **정직 경계**: 정본 일치 ≠ 런타임 실제 실행(선행 스텝 `PATH`/`env` 조작·GitHub 내부·스텝 이름 위조 — 위조 비용↑·닫지 못함). ② **#2 #5/#6 부분 (medium) — 비순환 생산 순서**: 활성 UNCHK-008 owner_track 이 `Phase 1`·U-17 하니스 경로가 «D0-A 산출물»이라 Phase 0 가 PREVENTION_ACTIVE 를 소비하기 전에 그 축·하니스를 누가 산출·폐쇄하는지 단일 비순환 순서 부재((D) verbatim 적용이 활성 형제 소비처 미전파·S-22). **UNCHK-008 owner_track `Phase 1`→`Phase 0`**(D0-A 착수 전 선행조건·운영자/인프라·U-17 live 검증·문법 n∈0..7 유효·imprecise_owner_track 불변[단일 phase])·산문 2곳(:4975·:5102) 전파 · **U-17 하니스 «D0-A 산출물»→«pre-D0-A 실체화»**(§12.3.4-R 결속값 sha 957bf49d… 파일 실체화·D0-A 착수 «전» 운영자/인프라가 둔다) · **개발계획 Phase 0 선행조건 불릿에 하니스 파일 실체화 한 줄 추가**(운영자 승인 (D) 개정의 «연장»·같은 대상·같은 pre-D0-A 주체·(D) ②′ verbatim 재기록). **S-22 전수**: «D0-A 산출물» 표기 중 하니스 파일(:5462)만 정정(U15-ENTRY-CHECK·config·원장·계약텍스트는 유지)·UNCHK-023(브랜치 보호 계열이나 git 이력 신뢰 별개 축이라 `Phase 1` 유지)·형제 UNCHK 행 재독. **종수 전파(S-20)**: T-84 14 불변(⑬c 검출 전환·⑬d/e/f 는 ⑬ 하위 케이스)·T-82 20·T-81 19·U-17-c 10값·U-16-d 12단 불변. **§12.3.3**: (A)=v2.20 판정 5건 리터럴(회피 1·해소 3·부분 1)·(B)=v2.21 2건 주장(«어느 것도 해소 아님»·#1 실행 증거 동결 후·#2 형제 전파+개발계획 연장)·(D) 갱신(②′ 연장). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`·현행 :4664-4764)·`bound_paths` 2건(계약+개발계획) 편집이므로 O-6 재결속 필요.** **[v2.21 에라타 (동결 `0528a919` 후 증거 실행 `3e0f2429` 적발 — 재결속 전이므로 정정 후 재동결·문언·과잉 차단 방향·fail-open 0)]** 증거(`U17-PREVENTION-CHECK-V221.md`)가 정본 대조 22픽스처 기대 불일치 0(⑬a~⑬g·⑬g B10/B11/B12 사멸·정본 B 런타임 OK/FAILED 전파·#2 순서)이되 문언 결함 후보 1건을 적발했다: **ⓐ E1(P-2·문언·과잉 차단)** 정규화 규칙이 YAML 스칼라 «표기»를 미언급 — 스텝 A(2줄)는 folded `>`+빈 줄이면 우연히 일치하나 **스텝 B(단일 파이프라인)를 `>` folded 로 쓰면 두 줄이 접혀 정본 불일치** → 정직한 워크플로도 red. → 정규화 규칙에 «정본 `run:` 은 literal block scalar(`|`) 표기 전제·`>` folded·인라인은 불일치=fail-closed·작성자는 `|` 사용» 명시(극성: 과잉 차단은 «표기 지정»으로 해소·S-15)·T-84 ⑬ 정규화 대조군을 «`|` 표기 + 주석/빈 줄 차이만»으로 정정(folded 는 A 에만 성립·B 불일치 명시). **종수 불변**(문언). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`·:4664-4764)·개발계획 무편집·`bound_paths`(계약만) 재동결.** **증거 결속(S-24)**: 이 에라타 재동결도 addendum 으로 이행(절 범위 `git diff` 공집합 + 영향 변이 재실행 — 스텝 A/B `|` 양성·`>` folded→B 불일치(계약대로 red)·A folded+빈 줄 일치 문언 정합). **[v2.21 에라타 2차 (ⓐ 재동결 후 stop-time Codex 심판 BLOCK `65cf2635` 적발 — 재결속 전이므로 정정 후 재동결)]** 심판이 ⓐ 재동결본의 실질 우회를 적발했다: **ⓑ (fail-open — 잡 수준 실행 무력화)** 계약이 `defaults.run.shell` 약화 금지를 «요구»하나 검증 실행기는 `jobs.tos-gate.steps` 만 읽고 defaults 를 검사 안 함 — GitHub 은 워크플로/잡 커스텀 셸 템플릿을 지원하므로 **`defaults.run.shell: "true {0}"` 는 정본 스텝 byte·이름을 보존하며 두 스크립트를 실행하지 않고 success 보고**(공식 문서). → **정본 대조 대상을 «두 스텝 run:»에서 «게이트 잡 객체 전체»(정본 잡 템플릿)로 확장**: 워크플로 `defaults`/`env` 부재·`permissions` 최소·`on` 닫힌 집합 / 게이트 잡 허용 키 닫힌 집합 `{runs-on, steps}`(`container`·`services`·`defaults`·`env`·`strategy`·`uses`·`with`·`secrets` 부재·`runs-on` 닫힌 리터럴) / `steps` 정확히 3(체크아웃 `actions/checkout@<40-hex SHA 핀·태그 금지>`·정본 A·정본 B·순서 고정·추가/선행 스텝 부재). **리서치 우선(운영자 지침)**: `run:` 실행을 바꾸는 정적 in-blob 키 전수(워크플로/잡 `defaults`·잡 `container`·`env`·`runs-on`·`strategy`·`uses`·스텝 `shell`/`env`/`with`/`uses`/`continue-on-error`/`if`/`timeout-minutes`)를 열거하는 대신 «허용 키 닫힌 집합 밖=불일치»로 열거 없이 닫음(S-6·열린→닫힌; 문서 `docs.github.com/…/workflow-syntax`·2026-08-19·D0-A 재실측). **기각 대안**: «defaults 만 추가 검사»(열거형·다음 키 통과·S-6)·«스텝 run 만 정본»(이 BLOCK). **정직 경계 이동**: 정적 in-blob 우회(선행 스텝 PATH/env·defaults·container·composite)는 정본 잡 템플릿이 «구조로» 닫고, 잔여=«잡 밖»(다른 잡 아티팩트/캐시·GitHub 내부·런타임·스텝 이름 위조·checkout 신뢰[SHA 핀]). **T-84 ⑬h**(defaults.run.shell 무력화)·**⑬i**(추가/선행 스텝 PATH 조작)·**⑬j**(container/self-hosted/env) 하위 케이스·양성=정본 잡 템플릿 정확·**종수 14 불변**. **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`·:4664-4764)·개발계획 무편집·`bound_paths`(계약만) 재동결.** **증거 결속(S-24)**: addendum 으로 이행(절 범위 `git diff` + 영향 변이 — ⑬h/i/j·양성·⑬a~g 회귀). **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
@@ -2891 +2891 @@ RUNTIME/FAULT/REVIEWER 존재성·REV2·A-1/A-2·D0-5에 테스트가 없었다.
-| **T-84** | **U-17 예방 통제 활성 증거** (§12.3.4) | **v2.15 신설 / v2.16 재작성 / [v2.17 재작성 — stop-time BLOCK B3 / v2.19 확장 / v2.20 확장]** — 파라미터화 **14종**. **v2.16 에라타 E2 가 #5 근거만 고치고 이 행을 보지 않아**(S-22) `rulesets=[]`·«머지 커밋 check-runs 0»·«pulls 공집합»이 **같은 턴 실측과 충돌**한 채 남아 있었다 — 행 전체를 재작성한다. ① **live 서버 음성(실측)** — 아티팩트 선언 == 구조 파생(`main`)인 정상 구성에서 `responder=gh` 실조회: `required_status_checks {strict:false, contexts:["test"]}` 이므로 **`PREVENTION_INSUFFICIENT`** · `/rules/branches/main` → `[]`(적용 규칙 0) · `/rulesets` → `[{name:"protect_main", enforcement:"disabled"}]` ⇒ **룰셋은 실재하나 disabled 라 동등물 없음**. **인증된 진짜 음성이며 모의가 아니다**. **[E1 — v2.17 에라타]** 초안은 여기에 «작업 브랜치 → 404 → `PREVENTION_ABSENT`» 를 함께 적었으나, **v2.17 에서 `target_branch` 는 `default_branch` 로 «파생»되므로 그 구성은 ⑤(`TARGET_MISMATCH`)이지 `ABSENT` 가 아니고 실행기로 재현되지 않는다**(증거 실행 적발 — S-22: B1 의 파생 전환이 이 행에 미전파). **«비-default 브랜치 protection → 404»는 «raw probe 관측»으로만 병기**하며 상태값 기대가 아니다 ② **seam 주입(`SIMULATED`)** — `responder` 주입으로 `PREVENTION_ACTIVE`·`INSUFFICIENT`·`UNVERIFIABLE` 모의. **기본 responder 는 `gh api`**. **양성은 운영자가 보호를 설정하기 전까지 실측 불가**임을 숨기지 않는다. **진정성은 §12.3.4 «진실 원천» 절이 «판정 소비자 자신의 조회»로 닫는다** ③ **리비전 검증(실측)** — `/commits/{d}/pulls` → 착지 PR → PR `head.sha` check-runs. 실측: `origin/main` 착지 `11e382fc` 의 check-runs **15건**(push 트리거 워크플로)·`pulls` = PR #636(merged·base main), PR head `7656259d` check-runs 5건에 **`tos-gate` 없음** ⇒ **`PREVENTION_UNVERIFIED_REVISION`**. 미푸시 커밋 → 422 ⇒ `PREVENTION_UNVERIFIABLE` · 푸시됐으나 PR 없는 `be98f075` → `pulls` `[]` ⇒ UNVERIFIED_REVISION ④ **보호 해제 후(stub)** — «countersign 시 ACTIVE → 이후 해제» 후 완료 판정 재조회가 `ABSENT`/`INSUFFICIENT` ⑤ **[v2.17 신설] target 불일치** — 아티팩트가 **다른 저장소/브랜치**를 선언(예: 보호가 걸린 타 repo, 또는 default 아닌 브랜치) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **`D = ∅` 에서도 red 여야 한다** — v2.16 은 이 구성에서 **임의 대상의 보호만으로 ACTIVE** 를 냈다 ⑥ **[v2.17 신설] `app_id` 위조** — `tos-gate` 라는 이름에 `conclusion: success` 이지만 **`app.id` 가 게이트 앱(기본 `15368`)이 아닌** check-run 을 seam 으로 주입 → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **이름만 보는 구현은 통과시키므로 실패한다** ⑦ **[v2.18] 타 앱 고정 required check** — 보호는 있고 `contexts` 에 `tos-gate` 도 있으나 `required_status_checks.checks[]` 의 그 컨텍스트 `app_id` 가 **Actions 가 아닌 앱**(예 99999) → **`PREVENTION_INSUFFICIENT`** + 비-0. **v2.17 은 이름만 봐서 `prot_ok` 를 냈고 `D=∅` 이면 그대로 진입 승인**됐다(심판이 실행기 술어로 재현) ⑧ **[v2.18] same-app wrong-workflow** — **같은 Actions app id** 로 **다른 워크플로**의 잡을 `tos-gate` 로 이름 지어 success 게시 → workflow run 의 `path` 가 `.github/workflows/tos-gate.yml` 이 아니므로 **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **app id 만 보는 구현은 통과시킨다**(실측: PR #636 head 의 5 run 이 전부 동일 app id) ⑨ **[v2.18] 아티팩트 사후 편집** — `P` → D0-A 착수 → 아티팩트 편집 → **`PREVENTION_ARTIFACT_MUTATED`** + 비-0. **`P_last` 를 쓰지 않고 «최초 도입 P» 만 보는 구현은 통과시킨다**  **[v2.20 — 심판 #3] 부모신뢰 TOCTOU 확장**: `P_last` 조상성 소비도 U-16-c 격리 스냅샷 기층을 쓰므로, ㉡ 관측과 조상성 조회 사이 graft 삽입·제거(SIMULATED seam)로 `ARTIFACT_MUTATED`↔`ACTIVE` 를 뒤집는 구현은 격리 스냅샷 안 소비로 fail-closed 됨을 함께 본다(격리 클론 픽스처·종수 불변) ⑩ **[v2.18] 타 원격·타 호스트** — 아티팩트/원격이 **계약 핀**(`github.com/kakao-harris-lee/kis_unified_sts`)과 다른 host 또는 owner/repo 를 가리킴(비-GitHub 호스트의 동일 경로 포함) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **host 를 버리는 정규화는 통과시킨다** ⑪ **[v2.19 신설 — 심판 F1] 보호 해제 창(off→merge→on) — 연속성** — **live 로 실행하지 않는다**(실측 픽스처가 서버 보호 설정 변경을 요구하므로): v2.16 (a) 방식의 **«캡처된 응답 위 결정적 술어» seam** 으로 SIMULATED 구성한다. 룰셋 응답에 `updated_at` 이 **최초 착지 `merged_at` 보다 늦은** 캡처를 주입 → **`PREVENTION_CONTINUITY_UNVERIFIABLE` + 비-0**(U-17-c). **classic branch protection 만인 캡처**(`updated_at`·`created_at` 부재) → 같은 값(연속성 판정 불가). **`updated_at`·`created_at` ≤ `merged_at` 캡처** → 그 축 통과(다른 축이 성립하면 `PREVENTION_ACTIVE`). **판별력**: 「진입·완료 두 조회가 둘 다 ACTIVE 면 통과」로 접는 구현은 이 SIMULATED 를 통과시켜 실패한다. **live 는 현행 상태 음성만**(오늘 `main` 은 룰셋 `disabled` 라 애초에 `PREVENTION_INSUFFICIENT`). **소비 시각은 «서버 시간»만**(응답의 `updated_at`·`created_at`·PR `merged_at`) — 커밋 author/committer date 는 클라이언트 공급이라 쓰지 않는다. **정직 표기**: 감사 로그 없이 «머지 시점 강제»의 완전 증명은 불가하므로 이 대조군은 **설정 변경의 관측**만 fail-closed 로 승격한다 ⑫ **[v2.19 신설 — 심판 신규 high] `GH_HOST` override — 정본 host 결속** — **live 실행 가능**(GET-only·환경변수만). 소비자는 계약 핀에서 host 를 파생해 **모든 `gh api` 에 `--hostname <핀 host>` 명시 + 자기 환경 `GH_HOST` 를 핀 host 로 설정**한다. 대조군은 `GH_HOST=<타 host>`(+`GH_ENTERPRISE_TOKEN=dummy`) 주입 후 실행 → **상태값이 override 유무와 «불변»**(조회가 핀 host 에 결속)이거나, 핀 host 도달·인증 불가면 **`PREVENTION_UNVERIFIABLE`**(fail-closed). **override 가 상태값을 바꾸면(특히 타 host 응답으로 `PREVENTION_ACTIVE`) 실패** = host 를 `gh` 환경에 위임하는 구현. **심판 실측 프로브**(`GH_HOST=example.invalid … gh api repos/a/b`, exit 1)가 host 없는 명령의 결함을 재현한 그 클래스이며, T-84 ⑩(remote URL 대조만)은 이 축을 잡지 못한다 ⑬ **[v2.20 신설 / v2.21 재편 — 심판 #1] 정본 불일치 클래스** — 동일 path/app/head 성공 워크플로 blob 에서 게이트 두 스텝(`tos-gate: run harness`·`tos-gate: verify harness sha256`)의 `run:` 이 **정규화 후 계약 정본(A/B)과 다르면** → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0.  «토큰 존재»가 아니라 «정본 byte 일치»가 관측량이다(구문 우회 전 클래스를 «열거 없이» 닫음·열린→닫힌 세계). **양성(정본 일치)**: `run:` 이 정본 A/B 와 정규형 일치면 red 가 «아니어야» 한다(허용 정본 집합 안이면 통과) · **정규화 대조군**: **`|` (literal) 표기** 하에서 주석 줄·빈 줄·trailing 공백·CRLF 만 다른 blob → «일치»(정규화가 결정적으로 흡수); `>` folded 는 스텝 A(빈 줄=개행)만 우연 일치·**스텝 B 는 접혀 불일치**(fail-closed)·정본 표기는 `|`([v2.21 에라타 ⓐ/E1]). **불일치 하위 케이스(전부 UNVERIFIED_REVISION·종수 불변)**: ⑬a `echo "…경로…"`(경로가 출력 명령 인자 — 정본 아님) · ⑬b `true  # shasum…|grep 957…`(무실행 + trailing 주석 — 정본 아님) · ⑬c `shasum…|grep 957… || true`(대조 뒤 `|| true` 무효화 — 정본 아님; **v2.20 의 «미검출» 기대가 v2.21 에서 «UNVERIFIED_REVISION» 으로 뒤집힘**·증거 V220 §3 ⑬c ACTIVE 기대 갱신) · **⑬d 도달 불가 호출** — `false && bash tools/tos_entry_harness.sh || true`(하니스가 `&&` 피연산자)·`… && bash tools/…`(선행 가드) — 정본 아님 · ⑬e 스텝 `continue-on-error: true`·`if: always()`/`failure()`·**추가 메타 키**(`working-directory`·`env:`·`with:`·`uses:`) 존재(닫힌 메타 키 집합 위배) · ⑬f `set +e`·`trap … ERR`(정본에 없는 줄) · **⑬g 선행 종결자** — `set -euo pipefail; exit 0; bash tools/…`·`exec true`·`[ -n "${SKIP:-}" ] && exit 0`(하니스 호출 «전»에 제어흐름을 종결해 미실행 — 독립 검증 B10/B11/B12 재현; 정본에 그 «실행 줄»이 없어 불일치로 검출). **⑬a~⑬g 는 전부 «정본과 다른 실행 줄»이라 정본 대조가 열거 없이 닫는다** — 자작 도달성 분석기 불요(운영자 «바퀴 재발명 금지»). **정직 경계(잔여)**: 정본 일치는 «런타임 실제 실행»을 증명 못 함(선행 스텝 `PATH`/env 조작·GitHub 내부·스텝 이름 위조 — 위조 비용↑·닫지 못함) ⑭ **[v2.20 신설 — 심판 #1] 서버 잡 스텝 부재/실패** — blob 구조는 통과하나 서버 `actions/runs/{run_id}/jobs`(또는 `actions/jobs/{job_id}`) 그 잡 `steps[]` 에 계약 리터럴 «스텝 이름»(`tos-gate: run harness`·`tos-gate: verify harness sha256`)이 **부재**하거나 그 스텝 `conclusion != success` → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **판별력**: blob 만 보고 서버 스텝 실행 기록을 대조 안 하는 구현은 통과 → 서버 스텝 대조는 red.  **정직 경계**: 스텝 이름·결론은 «서버 기록»이지 «그 스텝의 run 내용을 그대로 실행했다»의 증명이 아니다(⑬+⑭ 는 위조 비용을 올리되 GitHub 내부 실행 간극은 안 닫는다) |
+| **T-84** | **U-17 예방 통제 활성 증거** (§12.3.4) | **v2.15 신설 / v2.16 재작성 / [v2.17 재작성 — stop-time BLOCK B3 / v2.19 확장 / v2.20 확장]** — 파라미터화 **14종**. **v2.16 에라타 E2 가 #5 근거만 고치고 이 행을 보지 않아**(S-22) `rulesets=[]`·«머지 커밋 check-runs 0»·«pulls 공집합»이 **같은 턴 실측과 충돌**한 채 남아 있었다 — 행 전체를 재작성한다. ① **live 서버 음성(실측)** — 아티팩트 선언 == 구조 파생(`main`)인 정상 구성에서 `responder=gh` 실조회: `required_status_checks {strict:false, contexts:["test"]}` 이므로 **`PREVENTION_INSUFFICIENT`** · `/rules/branches/main` → `[]`(적용 규칙 0) · `/rulesets` → `[{name:"protect_main", enforcement:"disabled"}]` ⇒ **룰셋은 실재하나 disabled 라 동등물 없음**. **인증된 진짜 음성이며 모의가 아니다**. **[E1 — v2.17 에라타]** 초안은 여기에 «작업 브랜치 → 404 → `PREVENTION_ABSENT`» 를 함께 적었으나, **v2.17 에서 `target_branch` 는 `default_branch` 로 «파생»되므로 그 구성은 ⑤(`TARGET_MISMATCH`)이지 `ABSENT` 가 아니고 실행기로 재현되지 않는다**(증거 실행 적발 — S-22: B1 의 파생 전환이 이 행에 미전파). **«비-default 브랜치 protection → 404»는 «raw probe 관측»으로만 병기**하며 상태값 기대가 아니다 ② **seam 주입(`SIMULATED`)** — `responder` 주입으로 `PREVENTION_ACTIVE`·`INSUFFICIENT`·`UNVERIFIABLE` 모의. **기본 responder 는 `gh api`**. **양성은 운영자가 보호를 설정하기 전까지 실측 불가**임을 숨기지 않는다. **진정성은 §12.3.4 «진실 원천» 절이 «판정 소비자 자신의 조회»로 닫는다** ③ **리비전 검증(실측)** — `/commits/{d}/pulls` → 착지 PR → PR `head.sha` check-runs. 실측: `origin/main` 착지 `11e382fc` 의 check-runs **15건**(push 트리거 워크플로)·`pulls` = PR #636(merged·base main), PR head `7656259d` check-runs 5건에 **`tos-gate` 없음** ⇒ **`PREVENTION_UNVERIFIED_REVISION`**. 미푸시 커밋 → 422 ⇒ `PREVENTION_UNVERIFIABLE` · 푸시됐으나 PR 없는 `be98f075` → `pulls` `[]` ⇒ UNVERIFIED_REVISION ④ **보호 해제 후(stub)** — «countersign 시 ACTIVE → 이후 해제» 후 완료 판정 재조회가 `ABSENT`/`INSUFFICIENT` ⑤ **[v2.17 신설] target 불일치** — 아티팩트가 **다른 저장소/브랜치**를 선언(예: 보호가 걸린 타 repo, 또는 default 아닌 브랜치) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **`D = ∅` 에서도 red 여야 한다** — v2.16 은 이 구성에서 **임의 대상의 보호만으로 ACTIVE** 를 냈다 ⑥ **[v2.17 신설] `app_id` 위조** — `tos-gate` 라는 이름에 `conclusion: success` 이지만 **`app.id` 가 게이트 앱(기본 `15368`)이 아닌** check-run 을 seam 으로 주입 → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **이름만 보는 구현은 통과시키므로 실패한다** ⑦ **[v2.18] 타 앱 고정 required check** — 보호는 있고 `contexts` 에 `tos-gate` 도 있으나 `required_status_checks.checks[]` 의 그 컨텍스트 `app_id` 가 **Actions 가 아닌 앱**(예 99999) → **`PREVENTION_INSUFFICIENT`** + 비-0. **v2.17 은 이름만 봐서 `prot_ok` 를 냈고 `D=∅` 이면 그대로 진입 승인**됐다(심판이 실행기 술어로 재현) ⑧ **[v2.18] same-app wrong-workflow** — **같은 Actions app id** 로 **다른 워크플로**의 잡을 `tos-gate` 로 이름 지어 success 게시 → workflow run 의 `path` 가 `.github/workflows/tos-gate.yml` 이 아니므로 **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **app id 만 보는 구현은 통과시킨다**(실측: PR #636 head 의 5 run 이 전부 동일 app id) ⑨ **[v2.18] 아티팩트 사후 편집** — `P` → D0-A 착수 → 아티팩트 편집 → **`PREVENTION_ARTIFACT_MUTATED`** + 비-0. **`P_last` 를 쓰지 않고 «최초 도입 P» 만 보는 구현은 통과시킨다**  **[v2.20 — 심판 #3] 부모신뢰 TOCTOU 확장**: `P_last` 조상성 소비도 U-16-c 격리 스냅샷 기층을 쓰므로, ㉡ 관측과 조상성 조회 사이 graft 삽입·제거(SIMULATED seam)로 `ARTIFACT_MUTATED`↔`ACTIVE` 를 뒤집는 구현은 격리 스냅샷 안 소비로 fail-closed 됨을 함께 본다(격리 클론 픽스처·종수 불변) ⑩ **[v2.18] 타 원격·타 호스트** — 아티팩트/원격이 **계약 핀**(`github.com/kakao-harris-lee/kis_unified_sts`)과 다른 host 또는 owner/repo 를 가리킴(비-GitHub 호스트의 동일 경로 포함) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **host 를 버리는 정규화는 통과시킨다** ⑪ **[v2.19 신설 — 심판 F1] 보호 해제 창(off→merge→on) — 연속성** — **live 로 실행하지 않는다**(실측 픽스처가 서버 보호 설정 변경을 요구하므로): v2.16 (a) 방식의 **«캡처된 응답 위 결정적 술어» seam** 으로 SIMULATED 구성한다. 룰셋 응답에 `updated_at` 이 **최초 착지 `merged_at` 보다 늦은** 캡처를 주입 → **`PREVENTION_CONTINUITY_UNVERIFIABLE` + 비-0**(U-17-c). **classic branch protection 만인 캡처**(`updated_at`·`created_at` 부재) → 같은 값(연속성 판정 불가). **`updated_at`·`created_at` ≤ `merged_at` 캡처** → 그 축 통과(다른 축이 성립하면 `PREVENTION_ACTIVE`). **판별력**: 「진입·완료 두 조회가 둘 다 ACTIVE 면 통과」로 접는 구현은 이 SIMULATED 를 통과시켜 실패한다. **live 는 현행 상태 음성만**(오늘 `main` 은 룰셋 `disabled` 라 애초에 `PREVENTION_INSUFFICIENT`). **소비 시각은 «서버 시간»만**(응답의 `updated_at`·`created_at`·PR `merged_at`) — 커밋 author/committer date 는 클라이언트 공급이라 쓰지 않는다. **정직 표기**: 감사 로그 없이 «머지 시점 강제»의 완전 증명은 불가하므로 이 대조군은 **설정 변경의 관측**만 fail-closed 로 승격한다 ⑫ **[v2.19 신설 — 심판 신규 high] `GH_HOST` override — 정본 host 결속** — **live 실행 가능**(GET-only·환경변수만). 소비자는 계약 핀에서 host 를 파생해 **모든 `gh api` 에 `--hostname <핀 host>` 명시 + 자기 환경 `GH_HOST` 를 핀 host 로 설정**한다. 대조군은 `GH_HOST=<타 host>`(+`GH_ENTERPRISE_TOKEN=dummy`) 주입 후 실행 → **상태값이 override 유무와 «불변»**(조회가 핀 host 에 결속)이거나, 핀 host 도달·인증 불가면 **`PREVENTION_UNVERIFIABLE`**(fail-closed). **override 가 상태값을 바꾸면(특히 타 host 응답으로 `PREVENTION_ACTIVE`) 실패** = host 를 `gh` 환경에 위임하는 구현. **심판 실측 프로브**(`GH_HOST=example.invalid … gh api repos/a/b`, exit 1)가 host 없는 명령의 결함을 재현한 그 클래스이며, T-84 ⑩(remote URL 대조만)은 이 축을 잡지 못한다 ⑬ **[v2.20 신설 / v2.21 재편 — 심판 #1] 정본 불일치 클래스** — 동일 path/app/head 성공 워크플로 blob 에서 게이트 두 스텝(`tos-gate: run harness`·`tos-gate: verify harness sha256`)의 `run:` 이 **정규화 후 계약 정본(A/B)과 다르면** → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0.  «토큰 존재»가 아니라 «정본 byte 일치»가 관측량이다(구문 우회 전 클래스를 «열거 없이» 닫음·열린→닫힌 세계). **양성(정본 일치)**: `run:` 이 정본 A/B 와 정규형 일치면 red 가 «아니어야» 한다(허용 정본 집합 안이면 통과) · **정규화 대조군**: **`|` (literal) 표기** 하에서 주석 줄·빈 줄·trailing 공백·CRLF 만 다른 blob → «일치»(정규화가 결정적으로 흡수); `>` folded 는 스텝 A(빈 줄=개행)만 우연 일치·**스텝 B 는 접혀 불일치**(fail-closed)·정본 표기는 `|`([v2.21 에라타 ⓐ/E1]). **불일치 하위 케이스(전부 UNVERIFIED_REVISION·종수 불변)**: ⑬a `echo "…경로…"`(경로가 출력 명령 인자 — 정본 아님) · ⑬b `true  # shasum…|grep 957…`(무실행 + trailing 주석 — 정본 아님) · ⑬c `shasum…|grep 957… || true`(대조 뒤 `|| true` 무효화 — 정본 아님; **v2.20 의 «미검출» 기대가 v2.21 에서 «UNVERIFIED_REVISION» 으로 뒤집힘**·증거 V220 §3 ⑬c ACTIVE 기대 갱신) · **⑬d 도달 불가 호출** — `false && bash tools/tos_entry_harness.sh || true`(하니스가 `&&` 피연산자)·`… && bash tools/…`(선행 가드) — 정본 아님 · ⑬e 스텝 `continue-on-error: true`·`if: always()`/`failure()`·**추가 메타 키**(`working-directory`·`env:`·`with:`·`uses:`) 존재(닫힌 메타 키 집합 위배) · ⑬f `set +e`·`trap … ERR`(정본에 없는 줄) · **⑬g 선행 종결자** — `set -euo pipefail; exit 0; bash tools/…`·`exec true`·`[ -n "${SKIP:-}" ] && exit 0`(하니스 호출 «전»에 제어흐름을 종결해 미실행 — 독립 검증 B10/B11/B12 재현; 정본에 그 «실행 줄»이 없어 불일치로 검출). **[v2.21 에라타 2차 — 잡 템플릿] ⑬h 실행 무력화 defaults** — 워크플로/잡 `defaults.run.shell: "true {0}"`(정본 스텝 byte·이름 보존하나 실행 무력화·success 보고) → 정본 잡 템플릿의 `defaults` 부재 위배 → UNVERIFIED_REVISION(stop-time BLOCK 재현) · **⑬i 추가/선행 스텝** — 게이트 잡에 선행 `run` 스텝(`echo /x >> $GITHUB_PATH` PATH 조작)·추가 스텝 → `steps` ≠ 정확히 3 → 불일치 · **⑬j 잡 실행환경 키** — 잡 `container:`(가짜 bash 이미지)·self-hosted `runs-on`·잡/워크플로 `env:` → 허용 키/값 닫힌 집합 밖 → 불일치. **⑬a~⑬j 는 전부 «정본 잡 템플릿과 다름»이라 정본 대조가 열거 없이 닫는다** — 자작 도달성 분석기·키 열거 불요(운영자 «바퀴 재발명 금지»). **양성**: 정본 잡 템플릿 정확(체크아웃 `actions/checkout@<SHA 핀>` + 정본 A/B). **정직 경계(잔여)**: 정본 잡 일치는 «런타임 실제 실행»을 증명 못 함(잡 «밖»: 다른 잡 아티팩트/캐시·runner 이미지·GitHub 내부·스텝 이름 위조·checkout 신뢰[SHA 핀] — 위조 비용↑·닫지 못함) ⑭ **[v2.20 신설 — 심판 #1] 서버 잡 스텝 부재/실패** — blob 구조는 통과하나 서버 `actions/runs/{run_id}/jobs`(또는 `actions/jobs/{job_id}`) 그 잡 `steps[]` 에 계약 리터럴 «스텝 이름»(`tos-gate: run harness`·`tos-gate: verify harness sha256`)이 **부재**하거나 그 스텝 `conclusion != success` → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **판별력**: blob 만 보고 서버 스텝 실행 기록을 대조 안 하는 구현은 통과 → 서버 스텝 대조는 red.  **정직 경계**: 스텝 이름·결론은 «서버 기록»이지 «그 스텝의 run 내용을 그대로 실행했다»의 증명이 아니다(⑬+⑭ 는 위조 비용을 올리되 GitHub 내부 실행 간극은 안 닫는다) |
@@ -4398 +4398 @@ closed»로 오분류) → **E15**: 결합을 «`--show-toplevel` 루트 결합
-**v2.20 신규 증거 = `d101eb63`**(`U17`/`U16-…-V220.md` — 기대 전건 일치·문언 에라타 ⓐⓑⓒ 적발·fail-open 0)이며, 그 에라타는 변경 이력 v2.20 에라타 절이 유일 소스다(S-24).  **v2.21 신규 증거 = `3e0f2429`**(`U17-…-V221.md` — 정본 대조 22픽스처 0 불일치·문언 에라타 ⓐ[E1 YAML 스칼라 표기] 적발·fail-open 0)이며 그 에라타는 변경 이력 v2.21 에라타 절이 유일 소스다(S-24).  직전 층(v2.19) 증거는 스탬프
+**v2.20 신규 증거 = `d101eb63`**(`U17`/`U16-…-V220.md` — 기대 전건 일치·문언 에라타 ⓐⓑⓒ 적발·fail-open 0)이며, 그 에라타는 변경 이력 v2.20 에라타 절이 유일 소스다(S-24).  **v2.21 신규 증거 = `3e0f2429`**(`U17-…-V221.md` — 정본 대조 22픽스처 0 불일치·문언 에라타 ⓐ[E1 YAML 스칼라 표기] 적발·fail-open 0)이며 그 에라타는 변경 이력 v2.21 에라타 절이 유일 소스다(S-24).  **v2.21 에라타 2차 = stop-time BLOCK `65cf2635`**(ⓑ 잡 수준 `defaults.run.shell: "true {0}"` 실행 무력화 → 정본 «잡 템플릿» 닫힌-세계 확장; 변경 이력 유일 소스).  직전 층(v2.19) 증거는 스탬프
@@ -5467,5 +5467,24 @@ TOS 게이트 체크 이름  아티팩트가 **파라미터로 선언**하되 **
-                   (1) **blob «정본 대조»** (자작 도달성 분석기 없이 — 운영자 «바퀴 재발명 금지» 지침·CLAUDE.md
-                       Development Discipline: 기존 도구 재사용): YAML 파서(기존 도구)로 `jobs.<게이트 잡>.steps[]` 를
-                       얻어 게이트 두 스텝의 `run:` 을 **정규화 후 계약 «정본»과 byte 대조**한다.  정본과 다르면
-                       (선행 `exit`/`exec`/가드·서브셸·heredoc·eval·`|| true`·`set +e`·«선행 종결자» 등 «전 구문 우회»를
-                       **열거 없이** — 열린-세계→닫힌-세계) → **`PREVENTION_UNVERIFIED_REVISION`**(T-84 ⑬).
+                   (1) **blob «정본 잡 대조»** (자작 도달성 분석기 없이 — 운영자 «바퀴 재발명 금지» 지침·CLAUDE.md
+                       Development Discipline: 기존 도구 재사용): YAML 파서(기존 도구)로 **`jobs.<게이트 잡>` 객체 전체**를
+                       얻어 계약 **«정본 잡 템플릿»과 구조 대조**한다(스텝 `run:` 은 정규화 후 정본 byte 일치).  이탈하면
+                       (선행 `exit`/`exec`/가드·서브셸·heredoc·eval·`|| true`·`set +e`·«선행 종결자» 등 «전 구문 우회»·**실행
+                       방식을 바꾸는 워크플로/잡 키**를 **열거 없이** — 열린-세계→닫힌-세계) → **`PREVENTION_UNVERIFIED_REVISION`**(T-84 ⑬).
+                         **[v2.21 에라타 2차 ⓑ — stop-time BLOCK] 대조 대상을 «두 스텝 run:»에서 «게이트 잡 객체 전체»로 확장.**
+                         근거: `defaults.run.shell: "true {0}"`(워크플로/잡 수준 커스텀 셸 템플릿)은 **정본 스텝 byte·이름을
+                         보존하면서** 두 `run:` 을 실행하지 않고 success 를 보고한다 — 스텝만 정본 대조하면 통과(GitHub
+                         workflow-syntax 공식 문서 확인).  «defaults 만 추가 검사»는 열거형이라 **다음 키가 또 통과**(S-6·이번
+                         BLOCK).  → `jobs.<게이트 잡>` 이 **정본 잡 템플릿**과 (정규화 후) 구조 일치해야 한다:
+                           · **워크플로 수준**: `defaults` 부재 · `env` 부재(PATH 조작 차단) · `permissions` 최소(예 `contents: read`) ·
+                             `on` ∈ 닫힌 집합(`pull_request`/`push`).
+                           · **게이트 잡 허용 키 = 닫힌 집합 `{runs-on, steps}`** — `container`·`services`·`defaults`·`env`·`strategy`·
+                             `uses`·`with`·`secrets`(및 그 외 키) **부재** · `runs-on` ∈ **닫힌 리터럴 집합**(`ubuntu-latest`·`ubuntu-24.04`
+                             등 GitHub-hosted; self-hosted 라벨·배열 금지).
+                           · **`steps` = 정확히 3개·순서 고정**(추가/선행 스텝 부재): [① 체크아웃 `uses: actions/checkout@<40-hex SHA
+                             핀 — 계약 리터럴·태그 금지>`(닫힌 키 `uses`·최소 `with`[`fetch-depth: 0`]) · ② 정본 A 스텝(아래 (i)) ·
+                             ③ 정본 B 스텝(아래 (ii))].
+                         임의 이탈 → **`PREVENTION_UNVERIFIED_REVISION`**(T-84 ⑬h/⑬i/⑬j).  **리서치 근거**(운영자 «리서치 우선»
+                         지침): `run:` 실행 방식을 바꾸는 정적 in-blob 키(워크플로/잡 `defaults.run.shell`·`working-directory`·잡
+                         `container`·`services`·`runs-on`·`env`·`strategy`·`uses`·스텝 `shell`·`working-directory`·`env`·`with`·`uses`·
+                         `continue-on-error`·`if`·`timeout-minutes`)를 «전수 열거»하는 대신 **«허용 키 닫힌 집합 밖 = 불일치»**로
+                         «열거 없이» 닫는다(S-6·열린→닫힌 세계).  문서: `https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax`
+                         (리서치 2026-08-19; 재확인 필요 시 D0-A 가 실측).
@@ -5507,7 +5526,8 @@ printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59
-                       **정직 경계(비차단·상위 «닫지 못한다» 정직 경계와 같은 층)**: **정본 일치는 «그 스텝이 런타임에
-                         실제로 그 스크립트를 실행했다»를 증명하지 않는다** — `run:` 본문 «밖»은 조작 가능하다: 선행 스텝이
-                         `$GITHUB_PATH`/`$GITHUB_ENV` 로 `PATH`·env 를 바꿔 `bash`/`shasum`/`printf` 를 가짜로 앞세우거나
-                         workflow `env:`·composite action 으로 감쌀 수 있고, 스텝 «이름» 자체가 작성자 문자열이다(서버
-                         대조도 «이름·conclusion»만).  **정본 대조는 «in-step 구문 우회» 전 클래스를 닫되(열린→닫힌 세계)
-                         «런타임 환경(선행 스텝 PATH/env)·GitHub 내부 실행»은 못 닫는다** — «위조 비용을 «크게» 올리되
-                         닫지 못한다».
+                       **정직 경계(비차단·상위 «닫지 못한다» 정직 경계와 같은 층)**: **정본 잡 대조는 «그 잡이 런타임에 실제로
+                         그 스크립트를 실행했다»를 증명하지 않는다** — **[v2.21 에라타 2차 ⓑ] 정적 in-blob 우회**(선행 스텝
+                         `$GITHUB_PATH`/`$GITHUB_ENV`·`defaults.run.shell`·`container`·workflow/잡 `env`·composite/reusable)는 **정본 잡
+                         템플릿이 «구조로» 닫는다**(정확히 3 스텝·잡/워크플로 env·defaults 부재).  남는 잔여 = **«잡 «밖»»**: 다른 잡의
+                         아티팩트/캐시 오염·runner 이미지·GitHub 내부 실행·스텝 «이름» 위조(서버 대조도 «이름·conclusion»만)·
+                         `actions/checkout` 자체 신뢰(SHA 핀으로 내용은 고정·런타임 거동은 GitHub 소관).  **정본 잡 대조는 «정적
+                         in-blob 우회» 전 클래스를 닫되(열린→닫힌 세계) «런타임·잡 밖·GitHub 내부»는 못 닫는다** — «위조 비용을
+                         «크게» 올리되 닫지 못한다».
```

### 1-2. s24-proof 3층 (`s24-proof-e2.py` sha256 `823a366dde314951861f1b531b93978503bc7db5f07cea7185a2b503a927ac14` · 111행)

```text
blob(65cf2635:docs/plans/2026-08-12-tos-phase0-completion-contract-design.md) = 2660b800ab04a2536bdeaa3bf86168b65667b78d  행수=7531
blob(7adc1246:docs/plans/2026-08-12-tos-phase0-completion-contract-design.md) = 081b9bc34182beff9cfa01f01031896835dbaf2a  행수=7551

① 무변경 구간 증명 — hunk 6개 (기계 추출): -130,1 +130,1 · -213,1 +213,1 · -2891,1 +2891,1 · -4398,1 +4398,1 · -5467,5 +5467,24 · -5507,7 +5526,8
   hunk 여집합 구간별 sha256 대조 (구간을 손으로 적지 않는다 — 누락 불가):
   구간#1: old[1..129] vs new[1..129]  129행/129행  bccbf280af2b737c / bccbf280af2b737c → 동일
   구간#2: old[131..212] vs new[131..212]  82행/82행  3996c5209fb2adec / 3996c5209fb2adec → 동일
   구간#3: old[214..2890] vs new[214..2890]  2677행/2677행  dbb6fbb4f7436614 / dbb6fbb4f7436614 → 동일
   구간#4: old[2892..4397] vs new[2892..4397]  1506행/1506행  81e8d281d7013736 / 81e8d281d7013736 → 동일
   구간#5: old[4399..5466] vs new[4399..5466]  1068행/1068행  26a1718606c95f47 / 26a1718606c95f47 → 동일
   구간#6: old[5472..5506] vs new[5491..5525]  35행/35행  4d115217049a2ca9 / 4d115217049a2ca9 → 동일
   구간#7: old[5514..7532] vs new[5534..7552]  2019행/2019행  6241398637cc92e2 / 6241398637cc92e2 → 동일
   ⇒ 변경이 «닿지 않은» 구간 차이 = 0건 (0 이어야 한다)

② 명명 절 증명 — 각 blob 안에서 «리터럴 앵커»로 위치를 찾는다(행 번호 하드코딩 금지)
   절                                              old 행   new 행  판정
  [닿음]
   (b)③ 정본 «잡» 대조 도입 문장                          5467    5467  상이 (기대 상이) ✅   sha256 0f579cfed816 / 96bbd7ae049e
   정직 경계 절 (정본 대조 잔여)                            5507    5526  상이 (기대 상이) ✅   sha256 8c6e659aaf3f / 5387a784dc04
   T-84 ⑬ 행 (⑬h/⑬i/⑬j 신설)                        2891    2891  상이 (기대 상이) ✅   sha256 599d3f3d3dcf / 5c1ac8c9639f
   심사 이력 v2.21 행 (1번째 출현)                         130     130  상이 (기대 상이) ✅   sha256 ef9ce51984ca / 87646c6ee09f
   변경 이력 v2.21 행 (2번째 출현)                         213     213  상이 (기대 상이) ✅   sha256 11175225fb74 / eeb1fb2d87c4
   (B) 주 — v2.21 신규 증거                           4398    4398  상이 (기대 상이) ✅   sha256 ed3cd53d331a / 6e4b093dc1dc
  [닿지 않음]
   정규화 규칙 문장 (E1 표기 전제)                          5497    5516  동일 (기대 동일) ✅   sha256 1c78dbabf639 / 1c78dbabf639
   스텝 메타 닫힌 키 집합 문장                              5499    5518  동일 (기대 동일) ✅   sha256 ba02a1551fb4 / ba02a1551fb4
   서버 잡 스텝 대조 절 (2)                              5514    5534  동일 (기대 동일) ✅   sha256 45631dd8def7 / 45631dd8def7
   하니스 §12.3.4-R 블록 첫 줄                          4664    4664  동일 (기대 동일) ✅   sha256 e2b37d0fbeeb / e2b37d0fbeeb
   하니스 §12.3.4-R 블록 끝 줄                          4764    4764  동일 (기대 동일) ✅   sha256 7c74c97e2e41 / 7c74c97e2e41
   T-82 행 (종수 20)                                2941    2941  동일 (기대 동일) ✅   sha256 a9bd7743aef2 / a9bd7743aef2
   T-81 행 (종수 19)                                2940    2940  동일 (기대 동일) ✅   sha256 6eeb704aa338 / 6eeb704aa338
   U-17-c 상태 10값 정의                              5696    5716  동일 (기대 동일) ✅   sha256 a4770d3b3cef / a4770d3b3cef
   (a) 술어 — required_status_checks               5347    5347  동일 (기대 동일) ✅   sha256 f6e5d2eca7fb / f6e5d2eca7fb
   (α) 연속성 절                                      217     217  동일 (기대 동일) ✅   sha256 d1ecc6575a28 / d1ecc6575a28
   U-16-c c_APP 구조 정의 수식                         7121    7141  동일 (기대 동일) ✅   sha256 dc53f88be2ef / dc53f88be2ef
   U-16 격리 스냅샷 «단일 방법»                           7145    7165  동일 (기대 동일) ✅   sha256 edb7664a2e35 / edb7664a2e35
   UNCHK-008 레지스터 행                              6228    6248  동일 (기대 동일) ✅   sha256 1460d28bd4c8 / 1460d28bd4c8
   U-17 하니스 pre-D0-A 실체화 문장                      5480    5499  동일 (기대 동일) ✅   sha256 0511008c9dfb / 0511008c9dfb

③ 정본 A 코드펜스: old :5476-5477 · new :5495-5496 → byte 동일? True
   내용 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'

③ 정본 B 코드펜스: old :5487-5488 · new :5506-5507 → byte 동일? True
   내용 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"

④ 하니스 §12.3.4-R 블록(:4664-4764) sha256 — old=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
                                              new=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
   계약 리터럴 957bf49d… 와 일치? old=True new=True · 양자 byte-동일? True
```

**판독**: 무변경 구간 차이 **0건** · 닿은 절 6(전건 «상이») · 닿지 않은 절 15(전건 «동일» — 정규화 규칙·스텝 메타·서버 스텝 절·하니스·T-82/T-81·U-17-c·(a)·(α)·U-16·UNCHK-008·pre-D0-A 문장) · **정본 A/B 코드펜스 byte 동일**(행만 이동) · 하니스 블록 byte 동일.
→ **비영향 변이는 `3e0f2429`·`83f12afd` 그대로 결속**. §2 는 **잡 템플릿 축만** 재실행한 기록이다.

## 2. S-24 ② — 영향 변이 재실행 (ⓑ: 대조 대상 = 게이트 잡 객체 전체)

### 2-1. 실행기 갱신 — Codex 가 지적한 «defaults 미검사» 자리

| 파일 | sha256 | 행수 | 역할 |
| --- | --- | --- | --- |
| `u17-verify-v221b.sh` | `23d47e3b8114ba200dbd5be4734f98401eef200652e92a72bd147d5d67ac83ff` | 492 | 판정 실행기 — 술어 파일 교체 1건(v2.21 대비 diff 14행) |
| `wfcanon-v221b.py` | `ff3dc344082828b3e73ead55e9401585d25452d79b6a144cba798768c9730085` | 226 | 정본 «잡» 대조 술어 — v2.21 술어 대비 diff 85행(잡 템플릿 검사 신설) |
| `mkwf-e2.py` | `50a0c9e4427105cbe060b43f65a3c1350e606a87f633b9c817a10feb6d784feb` | 70 | 픽스처 생성기 — 정본 잡 템플릿 + ⑬h/⑬i/⑬j 변형 18종 |
| `t8xe2.sh` | `22b5c5384ec54427cb6c4f275acdd385b7c95b4b7cb067b0d2c01a50e2d4a8f3` | 195 | 드라이버 |

**핵심 델타(신설 함수 `job_template()`)** — v2.21 술어는 `jobs.<게이트 잡>.steps[]` 의 두 스텝 `run:` «만» 읽었고 워크플로/잡 수준 키를 전혀 보지 않았다(그래서 `defaults.run.shell: "true {0}"` 가 통과). 에라타 2차 술어는 다음을 추가로 소비한다:

```python
ALLOWED_JOB_KEYS = {"runs-on", "steps"}                 # 계약 :5479 — 잡 허용 키 «닫힌 집합»
RUNS_ON_OK = {"ubuntu-latest", "ubuntu-24.04"}          # 계약 :5480 — GitHub-hosted 닫힌 리터럴(self-hosted·배열 금지)
ON_OK = {"pull_request", "push"}                        # 계약 :5478 — on 닫힌 집합
PERM_OK = {"contents": "read"}                          # 계약 :5478 — permissions 최소
CHECKOUT_PREFIX = "actions/checkout@"                   # 계약 :5482 — 40-hex SHA 핀(태그 금지)
CHECKOUT_WITH_OK = {"fetch-depth"}                      # 계약 :5483 — 최소 with
STEP1_KEYS = {"uses", "with"}
```

실행기(`u17-verify-v221b.sh`) 자체 델타는 **술어 파일 경로 1줄 + 사유 문자열**뿐이다:

```diff
2c2,8
< # u17-verify (v2.21 동결 0528a919) — U-17 «예방 통제 활성 증거» 실행기 (계약 0528a919 §12.3.4 U-17)
---
> # u17-verify (v2.21 에라타 2차 7adc1246) — U-17 «예방 통제 활성 증거» 실행기 (계약 7adc1246 §12.3.4 U-17)
> #   v2.21 실행기(0528a919·sha256 5410519e...) 에서 파생 — 델타는 **에라타 2차 ⓑ 1건**뿐이다:
> #     [(b)3 :5467-5530] 정본 대조의 «대조 대상» 을 «두 스텝 run:» -> **«게이트 잡 객체 전체 + 워크플로 수준 키»** 로 확장.
> #       술어 파일 교체: wfcanon-v221.py -> wfcanon-v221b.py
> #       (stop-time BLOCK: defaults.run.shell: "true {0}" 가 정본 스텝 byte/이름을 보존한 채 두 run 을 실행하지 않고
> #        success 를 보고한다 — 스텝만 대조하는 구현은 통과.  허용 키 «닫힌 집합 밖 = 불일치»로 열거 없이 닫는다.)
> #     서버 잡 스텝 대조(2)·격리 스냅샷·host 결속·U-17-c 10값은 v2.21 거동 그대로(코드 델타 0).
35c41
< WFSTRUCT="${U17_WFSTRUCT:-$(dirname "$0")/wfcanon-v221.py}"   # [v2.21 #1] «정본 대조» 술어 (YAML 파서 + 정규화 후 byte 비교)
---
> WFSTRUCT="${U17_WFSTRUCT:-$(dirname "$0")/wfcanon-v221b.py}"   # [v2.21 에라타 2차 ⓑ] «정본 «잡» 대조» 술어 (잡 객체 전체 + 워크플로 키)
424c430
<     # ── [v2.21 #1 (1)] 정본 대조 — «토큰 존재»가 아니라 «정본 byte 일치» (열린-세계 → 닫힌-세계)
---
>     # ── [v2.21 에라타 2차 ⓑ] 정본 «잡» 대조 — 대조 대상 = 게이트 잡 객체 전체 + 워크플로 수준 키
432c438
<       *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬)"; continue ;;
---
>       *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 정본 잡 불일치 — 잡 템플릿(워크플로/잡 허용 키·steps 3·checkout SHA 핀) 또는 정본 A/B byte 위배 (T-84 ⑬a~⑬j)"; continue ;;
```

### 2-2. blob 배터리 18종 — 신(잡 템플릿) vs 구(v2.21 스텝만) 술어 동시 실행

```text
########## ① blob 배터리 — 정본 «잡» 템플릿 18 픽스처 · 신(v221b) vs 구(v221 = 스텝만) 술어 동시 실행 ##########
  fixtures=18 → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/wf (checkout pin=11bd71901bbe5b1630ceea73d27597364c9af683)
  id                 기대(계약 ⑬h~⑬j) 실측(v221b·잡)     대조(v221·스텝만) 설명
  pos-job-template   BLOB_OK                BLOB_OK                BLOB_OK                양성 — 정본 잡 템플릿 정확(checkout SHA 핀 + 정본 A/B)  [OK]
  13h-wf-defaults    UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬h — 워크플로 `defaults.run.shell: "true {0}"`(BLOCK 재현)  [OK]
  13h-job-defaults   UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬h — 잡 수준 `defaults.run.shell: "true {0}"`  [OK]
  13h-wf-workdir     UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬h — 워크플로 `defaults.run.working-directory`  [OK]
  13i-pre-step       UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬i — 선행 run 스텝(`echo /x >> $GITHUB_PATH`) → steps 4  [OK]
  13i-post-step      UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬i — 후행 추가 스텝 → steps 4  [OK]
  13i-order-swap     UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬i — 정본 A/B 순서 뒤바꿈  [OK]
  13i-checkout-tag   UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬i — 체크아웃 태그(`@v4`) — SHA 핀 요구 위배  [OK]
  13i-no-checkout    UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬i — 체크아웃 누락 → steps 2  [OK]
  13j-container      UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — 잡 `container:`(가짜 이미지)  [OK]
  13j-self-hosted    UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — `runs-on: self-hosted`  [OK]
  13j-job-env        UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — 잡 `env:`  [OK]
  13j-wf-env         UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — 워크플로 `env:`  [OK]
  13j-strategy       UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — 잡 `strategy.matrix`  [OK]
  13j-job-uses       UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — 잡 `uses:`(reusable workflow)  [OK]
  13j-perm-writeall  UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — `permissions: write-all`(최소 위배)  [OK]
  13j-on-dispatch    UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — `on: [workflow_dispatch]`(닫힌 집합 밖)  [OK]
  13e-step-extra     UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    회귀 ⑬e — 스텝 A 에 `env:` 추가(스텝 메타 닫힌 집합)  [OK]
  ⇒ 기대와 다른 케이스 = 0 건 · 구 술어가 «통과»시킨 red 케이스 = 16 건 (stop-time BLOCK 클래스)

-- 대표 3종 술어 원문 (양성 · ⑬h 워크플로 defaults · ⑬i 선행 스텝) --
== pos-job-template ==
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions={'contents': 'read'} · on⊆['pull_request', 'push'] | 잡 키⊆['runs-on', 'steps'] · runs-on∈['ubuntu-24.04', 'ubuntu-latest'] | steps=3[checkout@40-hex, 정본 A, 정본 B]
  WF-C1 워크플로 키 = ['jobs', 'name', 'on', 'permissions'] · 잡 키 = ['runs-on', 'steps'] · steps 이름 = ['actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-CJ 정본 잡 템플릿 위배 0건: 없음
  WF-C3 [A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치 = True
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C3 [B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치 = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = BLOB_OK
  RESULT=BLOB_OK
== 13h-wf-defaults ==
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | defaults:
  |   run:
  |     shell: "true {0}"
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions={'contents': 'read'} · on⊆['pull_request', 'push'] | 잡 키⊆['runs-on', 'steps'] · runs-on∈['ubuntu-24.04', 'ubuntu-latest'] | steps=3[checkout@40-hex, 정본 A, 정본 B]
  WF-C1 워크플로 키 = ['defaults', 'jobs', 'name', 'on', 'permissions'] · 잡 키 = ['runs-on', 'steps'] · steps 이름 = ['actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-CJ 정본 잡 템플릿 위배 1건: ["워크플로 `defaults` 실재 {'run': {'shell': 'true {0}'}} (부재여야 함 — 실행 무력화 표면)"]
  WF-C3 [A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치 = True
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C3 [B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치 = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION
== 13i-pre-step ==
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "prepare"
  |         run: |
  |           echo /x >> $GITHUB_PATH
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions={'contents': 'read'} · on⊆['pull_request', 'push'] | 잡 키⊆['runs-on', 'steps'] · runs-on∈['ubuntu-24.04', 'ubuntu-latest'] | steps=3[checkout@40-hex, 정본 A, 정본 B]
  WF-C1 워크플로 키 = ['jobs', 'name', 'on', 'permissions'] · 잡 키 = ['runs-on', 'steps'] · steps 이름 = ['actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', 'prepare', 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-CJ 정본 잡 템플릿 위배 1건: ['`steps` 길이 = 4 ≠ 3 (추가/선행 스텝 부재여야 함)']
  WF-C3 [A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치 = True
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C3 [B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치 = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION

```

→ **기대 불일치 0건** · **구 술어가 통과시킨 red 케이스 16건** = stop-time BLOCK 이 지목한 클래스가 실행으로 재현됐다.

### 2-3. e2e (실행기 전체 · SIMULATED seam)

| # | 구성 | 실행기 | 계약 기대 | 실측 | rc |
| --- | --- | --- | --- | --- | --- |
| ②-1 | 정본 잡 템플릿 정확(checkout SHA 핀 + 정본 A/B) | v221b | `PREVENTION_ACTIVE` | **`PREVENTION_ACTIVE`** | 0 ✅ |
| ②-2 | **⑬h `defaults.run.shell: "true {0}"`** | v221b | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION`** | 1 ✅ |
| ②-3 | 같은 seam | **V221(스텝만)** | (BLOCK 재현) | **`PREVENTION_ACTIVE`** | **0** | 
| ②-4 | ⑬i 선행 `echo /x >> $GITHUB_PATH` 스텝 | v221b | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION`** | 1 ✅ |
| ②-5 | ⑬j 잡 `container:` | v221b | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION`** | 1 ✅ |

### 2-4. 회귀 불변

```text
########## ③ 회귀 불변 — v2.21 증거·에라타 1차 배터리를 «잡 템플릿» 술어로 재실행 ##########
  주: v2.21/에라타1차 픽스처는 «잡 템플릿» 요건(체크아웃 스텝·permissions·on) 을 갖지 않으므로,
      run: 층 판정만 비교하기 위해 «정본 잡 템플릿에 그 run 을 이식»한 형태로 다시 만든다.
  이식 픽스처 7종 → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/wf3
  id                 기대                 실측(v221b)
  pos-canonical      BLOB_OK                BLOB_OK  [OK]
  ctrl-comments      BLOB_OK                BLOB_OK  [OK]
  ctrl-crlf          BLOB_OK                BLOB_OK  [OK]
  13a-echo           UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  13c-ortrue         UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  13g-exit0          UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  nbsp-trailing      UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]

```

```text
########## ③-2 회귀 — 서버 잡 steps[] mock(⑭) 5종 불변 ##########
  ok          SERVER_OK              SERVER_OK  [OK]
  noverify    UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  verifyfail  UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  norun       UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  jobfail     UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
```

→ v2.21 배터리 대표 7종(양성·정규화 대조군·⑬a·⑬c·⑬g·NBSP)을 **정본 잡 템플릿에 이식**해 재실행 — 전건 불변. 서버 `steps[]` mock(⑭) 5종도 불변.

## 3. 실행 기록 (stdout 전문 · rc 포함)

### 3-1. `bash t8xe2.sh` (682행)

```text
t8xe2_utc=2026-08-19T13:15:06Z
sha256(u17-verify-v221b.sh)=23d47e3b8114ba200dbd5be4734f98401eef200652e92a72bd147d5d67ac83ff
sha256(wfcanon-v221b.py)=ff3dc344082828b3e73ead55e9401585d25452d79b6a144cba798768c9730085
sha256(u17-verify-v221.sh)=5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727
sha256(wfcanon-v221.py)=a5430e1a593d890f19a36713b9577c15c807a12c4131d45bd2937744255b811d
sha256(mkwf-e2.py)=50a0c9e4427105cbe060b43f65a3c1350e606a87f633b9c817a10feb6d784feb
-- 실행기 델타 (v2.21 → 에라타 2차) --
  2c2,8
  < # u17-verify (v2.21 동결 0528a919) — U-17 «예방 통제 활성 증거» 실행기 (계약 0528a919 §12.3.4 U-17)
  ---
  > # u17-verify (v2.21 에라타 2차 7adc1246) — U-17 «예방 통제 활성 증거» 실행기 (계약 7adc1246 §12.3.4 U-17)
  > #   v2.21 실행기(0528a919·sha256 5410519e...) 에서 파생 — 델타는 **에라타 2차 ⓑ 1건**뿐이다:
  > #     [(b)3 :5467-5530] 정본 대조의 «대조 대상» 을 «두 스텝 run:» -> **«게이트 잡 객체 전체 + 워크플로 수준 키»** 로 확장.
  > #       술어 파일 교체: wfcanon-v221.py -> wfcanon-v221b.py
  > #       (stop-time BLOCK: defaults.run.shell: "true {0}" 가 정본 스텝 byte/이름을 보존한 채 두 run 을 실행하지 않고
  > #        success 를 보고한다 — 스텝만 대조하는 구현은 통과.  허용 키 «닫힌 집합 밖 = 불일치»로 열거 없이 닫는다.)
  > #     서버 잡 스텝 대조(2)·격리 스냅샷·host 결속·U-17-c 10값은 v2.21 거동 그대로(코드 델타 0).
  35c41
  < WFSTRUCT="${U17_WFSTRUCT:-$(dirname "$0")/wfcanon-v221.py}"   # [v2.21 #1] «정본 대조» 술어 (YAML 파서 + 정규화 후 byte 비교)
  ---
  > WFSTRUCT="${U17_WFSTRUCT:-$(dirname "$0")/wfcanon-v221b.py}"   # [v2.21 에라타 2차 ⓑ] «정본 «잡» 대조» 술어 (잡 객체 전체 + 워크플로 키)
  424c430
  <     # ── [v2.21 #1 (1)] 정본 대조 — «토큰 존재»가 아니라 «정본 byte 일치» (열린-세계 → 닫힌-세계)
  ---
  >     # ── [v2.21 에라타 2차 ⓑ] 정본 «잡» 대조 — 대조 대상 = 게이트 잡 객체 전체 + 워크플로 수준 키
  432c438
  <       *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬)"; continue ;;
  ---
  >       *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 정본 잡 불일치 — 잡 템플릿(워크플로/잡 허용 키·steps 3·checkout SHA 핀) 또는 정본 A/B byte 위배 (T-84 ⑬a~⑬j)"; continue ;;
git=git version 2.38.0 · yq=yq (https://github.com/mikefarah/yq/) version v4.48.1 · python3=Python 3.14.7

########## ① blob 배터리 — 정본 «잡» 템플릿 18 픽스처 · 신(v221b) vs 구(v221 = 스텝만) 술어 동시 실행 ##########
  fixtures=18 → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/wf (checkout pin=11bd71901bbe5b1630ceea73d27597364c9af683)
  id                 기대(계약 ⑬h~⑬j) 실측(v221b·잡)     대조(v221·스텝만) 설명
  pos-job-template   BLOB_OK                BLOB_OK                BLOB_OK                양성 — 정본 잡 템플릿 정확(checkout SHA 핀 + 정본 A/B)  [OK]
  13h-wf-defaults    UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬h — 워크플로 `defaults.run.shell: "true {0}"`(BLOCK 재현)  [OK]
  13h-job-defaults   UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬h — 잡 수준 `defaults.run.shell: "true {0}"`  [OK]
  13h-wf-workdir     UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬h — 워크플로 `defaults.run.working-directory`  [OK]
  13i-pre-step       UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬i — 선행 run 스텝(`echo /x >> $GITHUB_PATH`) → steps 4  [OK]
  13i-post-step      UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬i — 후행 추가 스텝 → steps 4  [OK]
  13i-order-swap     UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬i — 정본 A/B 순서 뒤바꿈  [OK]
  13i-checkout-tag   UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬i — 체크아웃 태그(`@v4`) — SHA 핀 요구 위배  [OK]
  13i-no-checkout    UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬i — 체크아웃 누락 → steps 2  [OK]
  13j-container      UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — 잡 `container:`(가짜 이미지)  [OK]
  13j-self-hosted    UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — `runs-on: self-hosted`  [OK]
  13j-job-env        UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — 잡 `env:`  [OK]
  13j-wf-env         UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — 워크플로 `env:`  [OK]
  13j-strategy       UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — 잡 `strategy.matrix`  [OK]
  13j-job-uses       UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — 잡 `uses:`(reusable workflow)  [OK]
  13j-perm-writeall  UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — `permissions: write-all`(최소 위배)  [OK]
  13j-on-dispatch    UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                ⑬j — `on: [workflow_dispatch]`(닫힌 집합 밖)  [OK]
  13e-step-extra     UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    회귀 ⑬e — 스텝 A 에 `env:` 추가(스텝 메타 닫힌 집합)  [OK]
  ⇒ 기대와 다른 케이스 = 0 건 · 구 술어가 «통과»시킨 red 케이스 = 16 건 (stop-time BLOCK 클래스)

-- 대표 3종 술어 원문 (양성 · ⑬h 워크플로 defaults · ⑬i 선행 스텝) --
== pos-job-template ==
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions={'contents': 'read'} · on⊆['pull_request', 'push'] | 잡 키⊆['runs-on', 'steps'] · runs-on∈['ubuntu-24.04', 'ubuntu-latest'] | steps=3[checkout@40-hex, 정본 A, 정본 B]
  WF-C1 워크플로 키 = ['jobs', 'name', 'on', 'permissions'] · 잡 키 = ['runs-on', 'steps'] · steps 이름 = ['actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-CJ 정본 잡 템플릿 위배 0건: 없음
  WF-C3 [A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치 = True
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C3 [B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치 = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = BLOB_OK
  RESULT=BLOB_OK
== 13h-wf-defaults ==
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | defaults:
  |   run:
  |     shell: "true {0}"
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions={'contents': 'read'} · on⊆['pull_request', 'push'] | 잡 키⊆['runs-on', 'steps'] · runs-on∈['ubuntu-24.04', 'ubuntu-latest'] | steps=3[checkout@40-hex, 정본 A, 정본 B]
  WF-C1 워크플로 키 = ['defaults', 'jobs', 'name', 'on', 'permissions'] · 잡 키 = ['runs-on', 'steps'] · steps 이름 = ['actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-CJ 정본 잡 템플릿 위배 1건: ["워크플로 `defaults` 실재 {'run': {'shell': 'true {0}'}} (부재여야 함 — 실행 무력화 표면)"]
  WF-C3 [A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치 = True
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C3 [B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치 = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION
== 13i-pre-step ==
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "prepare"
  |         run: |
  |           echo /x >> $GITHUB_PATH
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions={'contents': 'read'} · on⊆['pull_request', 'push'] | 잡 키⊆['runs-on', 'steps'] · runs-on∈['ubuntu-24.04', 'ubuntu-latest'] | steps=3[checkout@40-hex, 정본 A, 정본 B]
  WF-C1 워크플로 키 = ['jobs', 'name', 'on', 'permissions'] · 잡 키 = ['runs-on', 'steps'] · steps 이름 = ['actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', 'prepare', 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-CJ 정본 잡 템플릿 위배 1건: ['`steps` 길이 = 4 ≠ 3 (추가/선행 스텝 부재여야 함)']
  WF-C3 [A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치 = True
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C3 [B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치 = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION

########## ② e2e — 픽스처 저장소(P → W → d) · seam blob 만 바꾼다 ##########
  W(PR head)=6e35439367d852d14ebd5c6d125e8c93370970a0  d=13a6d13ebca60697607c59a6744a6692d7f0c785

########## ②-1 양성 — 정본 잡 템플릿 정확 ⇒ PREVENTION_ACTIVE + rc 0 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 13a6d13 2026-08-19T22:15:09+09:00 D0-A: introduce config/tos_completion.yaml
  * 6e35439 2026-08-19T22:15:08+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 34f44ad 2026-08-19T22:15:08+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * c3142ef 2026-08-19T22:15:08+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/pos bash u17-verify-v221b.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=13a6d13ebca60697607c59a6744a6692d7f0c785
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.6xImKKFqVE/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=13a6d13ebca60697607c59a6744a6692d7f0c785 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.6xImKKFqVE/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/pos capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.kZNrWtxEk5
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/pos — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.6xImKKFqVE/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.6xImKKFqVE/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T13:15:10Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T13:15:10Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T13:15:10Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T13:15:10Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T13:15:10Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T13:15:11Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[34f44ad589798722af97f80b4f2b132367b62bbd ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[34f44ad589798722af97f80b4f2b132367b62bbd ] |D|=1 D=[13a6d13ebca60697607c59a6744a6692d7f0c785 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.6xImKKFqVE/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/13a6d13ebca60697607c59a6744a6692d7f0c785/pulls  utc=2026-08-19T13:15:11Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"6e35439367d852d14ebd5c6d125e8c93370970a0"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/6e35439367d852d14ebd5c6d125e8c93370970a0/check-runs  utc=2026-08-19T13:15:12Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T13:15:12Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T13:15:12Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=6e35439367d852d14ebd5c6d125e8c93370970a0  utc=2026-08-19T13:15:12Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "12a9dab81b054e952a6d1308eb416da41ff0f0d3", "size": 582, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QDExYmQ3MTkwMWJiZTViMTYzMGNlZWE3M2QyNzU5NzM2NGM5YWY2ODMKICAgICAgICB3aXRoOgogICAgICAgICAgZmV0Y2gtZGVwdGg6IDAKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@6e35439367d852d14ebd5c6d125e8c93370970a0 (encoding=base64 size=582):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions={'contents': 'read'} · on⊆['pull_request', 'push'] | 잡 키⊆['runs-on', 'steps'] · runs-on∈['ubuntu-24.04', 'ubuntu-latest'] | steps=3[checkout@40-hex, 정본 A, 정본 B]
  | WF-C1 워크플로 키 = ['jobs', 'name', 'on', 'permissions'] · 잡 키 = ['runs-on', 'steps'] · steps 이름 = ['actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-CJ 정본 잡 템플릿 위배 0건: 없음
  | WF-C3 [A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치 = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C3 [B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치 = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T13:15:12Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 6e35439367d852d14ebd5c6d125e8c93370970a0:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=13a6d13ebca60697607c59a6744a6692d7f0c785 head=6e35439367d852d14ebd5c6d125e8c93370970a0 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/pos
u17_rc=0
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t8xe2.sh: line 140: defaults.run.shell:: command not found

########## ②-2 ⑬h  ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 13a6d13 2026-08-19T22:15:09+09:00 D0-A: introduce config/tos_completion.yaml
  * 6e35439 2026-08-19T22:15:08+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 34f44ad 2026-08-19T22:15:08+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * c3142ef 2026-08-19T22:15:08+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/h bash u17-verify-v221b.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=13a6d13ebca60697607c59a6744a6692d7f0c785
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gDFfTej5iU/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=13a6d13ebca60697607c59a6744a6692d7f0c785 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gDFfTej5iU/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/h capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.VQZOiHHhbm
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/h — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gDFfTej5iU/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gDFfTej5iU/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T13:15:14Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T13:15:14Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T13:15:14Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T13:15:14Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T13:15:14Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T13:15:14Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[34f44ad589798722af97f80b4f2b132367b62bbd ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[34f44ad589798722af97f80b4f2b132367b62bbd ] |D|=1 D=[13a6d13ebca60697607c59a6744a6692d7f0c785 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gDFfTej5iU/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/13a6d13ebca60697607c59a6744a6692d7f0c785/pulls  utc=2026-08-19T13:15:15Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"6e35439367d852d14ebd5c6d125e8c93370970a0"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/6e35439367d852d14ebd5c6d125e8c93370970a0/check-runs  utc=2026-08-19T13:15:15Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T13:15:15Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T13:15:15Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=6e35439367d852d14ebd5c6d125e8c93370970a0  utc=2026-08-19T13:15:15Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "945a9379c2b24c77831af15931c329073f96956a", "size": 621, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmRlZmF1bHRzOgogIHJ1bjoKICAgIHNoZWxsOiAidHJ1ZSB7MH0iCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QDExYmQ3MTkwMWJiZTViMTYzMGNlZWE3M2QyNzU5NzM2NGM5YWY2ODMKICAgICAgICB3aXRoOgogICAgICAgICAgZmV0Y2gtZGVwdGg6IDAKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@6e35439367d852d14ebd5c6d125e8c93370970a0 (encoding=base64 size=621):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | defaults:
  |   run:
  |     shell: "true {0}"
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions={'contents': 'read'} · on⊆['pull_request', 'push'] | 잡 키⊆['runs-on', 'steps'] · runs-on∈['ubuntu-24.04', 'ubuntu-latest'] | steps=3[checkout@40-hex, 정본 A, 정본 B]
  | WF-C1 워크플로 키 = ['defaults', 'jobs', 'name', 'on', 'permissions'] · 잡 키 = ['runs-on', 'steps'] · steps 이름 = ['actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-CJ 정본 잡 템플릿 위배 1건: ["워크플로 `defaults` 실재 {'run': {'shell': 'true {0}'}} (부재여야 함 — 실행 무력화 표면)"]
  | WF-C3 [A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치 = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C3 [B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치 = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=13a6d13ebca60697607c59a6744a6692d7f0c785 head=6e35439367d852d14ebd5c6d125e8c93370970a0 정본 잡 불일치 — 잡 템플릿(워크플로/잡 허용 키·steps 3·checkout SHA 핀) 또는 정본 A/B byte 위배 (T-84 ⑬a~⑬j)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=13a6d13ebca60697607c59a6744a6692d7f0c785 head=6e35439367d852d14ebd5c6d125e8c93370970a0 정본 잡 불일치 — 잡 템플릿(워크플로/잡 허용 키·steps 3·checkout SHA 핀) 또는 정본 A/B byte 위배 (T-84 ⑬a~⑬j) [수집 1건 중 전순서 최소]
u17_rc=1

########## ②-3 stop-time BLOCK 재현 — 같은 seam 을 **V221 실행기**(스텝만 대조)로 → ACTIVE/0 이면 Codex 지적의 실증 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 13a6d13 2026-08-19T22:15:09+09:00 D0-A: introduce config/tos_completion.yaml
  * 6e35439 2026-08-19T22:15:08+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 34f44ad 2026-08-19T22:15:08+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * c3142ef 2026-08-19T22:15:08+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/h221 bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=13a6d13ebca60697607c59a6744a6692d7f0c785
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YkKy0rayc5/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=13a6d13ebca60697607c59a6744a6692d7f0c785 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YkKy0rayc5/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/h221 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.hDzZ5ER7jv
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/h221 — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YkKy0rayc5/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YkKy0rayc5/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T13:15:17Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T13:15:17Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T13:15:17Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T13:15:17Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T13:15:17Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T13:15:18Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[34f44ad589798722af97f80b4f2b132367b62bbd ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[34f44ad589798722af97f80b4f2b132367b62bbd ] |D|=1 D=[13a6d13ebca60697607c59a6744a6692d7f0c785 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YkKy0rayc5/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/13a6d13ebca60697607c59a6744a6692d7f0c785/pulls  utc=2026-08-19T13:15:19Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"6e35439367d852d14ebd5c6d125e8c93370970a0"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/6e35439367d852d14ebd5c6d125e8c93370970a0/check-runs  utc=2026-08-19T13:15:19Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T13:15:19Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T13:15:19Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=6e35439367d852d14ebd5c6d125e8c93370970a0  utc=2026-08-19T13:15:19Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "945a9379c2b24c77831af15931c329073f96956a", "size": 621, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmRlZmF1bHRzOgogIHJ1bjoKICAgIHNoZWxsOiAidHJ1ZSB7MH0iCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QDExYmQ3MTkwMWJiZTViMTYzMGNlZWE3M2QyNzU5NzM2NGM5YWY2ODMKICAgICAgICB3aXRoOgogICAgICAgICAgZmV0Y2gtZGVwdGg6IDAKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@6e35439367d852d14ebd5c6d125e8c93370970a0 (encoding=base64 size=621):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | defaults:
  |   run:
  |     shell: "true {0}"
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T13:15:19Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 6e35439367d852d14ebd5c6d125e8c93370970a0:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=13a6d13ebca60697607c59a6744a6692d7f0c785 head=6e35439367d852d14ebd5c6d125e8c93370970a0 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/h221
u17_rc=0

########## ②-4 ⑬i 선행 PATH 조작 스텝 ⇒ PREVENTION_UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 13a6d13 2026-08-19T22:15:09+09:00 D0-A: introduce config/tos_completion.yaml
  * 6e35439 2026-08-19T22:15:08+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 34f44ad 2026-08-19T22:15:08+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * c3142ef 2026-08-19T22:15:08+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/i bash u17-verify-v221b.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=13a6d13ebca60697607c59a6744a6692d7f0c785
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.uqZHQIuZAZ/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=13a6d13ebca60697607c59a6744a6692d7f0c785 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.uqZHQIuZAZ/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/i capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.RqwnOXKUne
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/i — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.uqZHQIuZAZ/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.uqZHQIuZAZ/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T13:15:21Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T13:15:21Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T13:15:21Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T13:15:21Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T13:15:21Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T13:15:21Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[34f44ad589798722af97f80b4f2b132367b62bbd ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[34f44ad589798722af97f80b4f2b132367b62bbd ] |D|=1 D=[13a6d13ebca60697607c59a6744a6692d7f0c785 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.uqZHQIuZAZ/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/13a6d13ebca60697607c59a6744a6692d7f0c785/pulls  utc=2026-08-19T13:15:22Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"6e35439367d852d14ebd5c6d125e8c93370970a0"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/6e35439367d852d14ebd5c6d125e8c93370970a0/check-runs  utc=2026-08-19T13:15:22Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T13:15:22Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T13:15:22Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=6e35439367d852d14ebd5c6d125e8c93370970a0  utc=2026-08-19T13:15:23Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "52d26257361f4cd0400d11f3a2daff5a3e275049", "size": 655, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QDExYmQ3MTkwMWJiZTViMTYzMGNlZWE3M2QyNzU5NzM2NGM5YWY2ODMKICAgICAgICB3aXRoOgogICAgICAgICAgZmV0Y2gtZGVwdGg6IDAKICAgICAgLSBuYW1lOiAicHJlcGFyZSIKICAgICAgICBydW46IHwKICAgICAgICAgIGVjaG8gL3ggPj4gJEdJVEhVQl9QQVRICiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBiYXNoIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgcHJpbnRmICclcyAgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2hcbicgOTU3YmY0OWRhOGZjNmFlMzlmOTdhYmU2Nzk0MTFhZmVhYTVhNTlmNzA3ZjM1YmYzYjNhOGM2ZjlkZTE0MWYwZCB8IHNoYXN1bSAtYSAyNTYgLWMgLQ==\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@6e35439367d852d14ebd5c6d125e8c93370970a0 (encoding=base64 size=655):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "prepare"
  |         run: |
  |           echo /x >> $GITHUB_PATH
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions={'contents': 'read'} · on⊆['pull_request', 'push'] | 잡 키⊆['runs-on', 'steps'] · runs-on∈['ubuntu-24.04', 'ubuntu-latest'] | steps=3[checkout@40-hex, 정본 A, 정본 B]
  | WF-C1 워크플로 키 = ['jobs', 'name', 'on', 'permissions'] · 잡 키 = ['runs-on', 'steps'] · steps 이름 = ['actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', 'prepare', 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-CJ 정본 잡 템플릿 위배 1건: ['`steps` 길이 = 4 ≠ 3 (추가/선행 스텝 부재여야 함)']
  | WF-C3 [A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치 = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C3 [B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치 = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=13a6d13ebca60697607c59a6744a6692d7f0c785 head=6e35439367d852d14ebd5c6d125e8c93370970a0 정본 잡 불일치 — 잡 템플릿(워크플로/잡 허용 키·steps 3·checkout SHA 핀) 또는 정본 A/B byte 위배 (T-84 ⑬a~⑬j)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=13a6d13ebca60697607c59a6744a6692d7f0c785 head=6e35439367d852d14ebd5c6d125e8c93370970a0 정본 잡 불일치 — 잡 템플릿(워크플로/잡 허용 키·steps 3·checkout SHA 핀) 또는 정본 A/B byte 위배 (T-84 ⑬a~⑬j) [수집 1건 중 전순서 최소]
u17_rc=1
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t8xe2.sh: line 149: container:: command not found

########## ②-5 ⑬j 잡  ⇒ PREVENTION_UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 13a6d13 2026-08-19T22:15:09+09:00 D0-A: introduce config/tos_completion.yaml
  * 6e35439 2026-08-19T22:15:08+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 34f44ad 2026-08-19T22:15:08+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * c3142ef 2026-08-19T22:15:08+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/j bash u17-verify-v221b.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=13a6d13ebca60697607c59a6744a6692d7f0c785
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.i87SrqUOpa/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=13a6d13ebca60697607c59a6744a6692d7f0c785 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.i87SrqUOpa/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/j capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.horzvfOLA4
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe2/j — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.i87SrqUOpa/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.i87SrqUOpa/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T13:15:24Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T13:15:24Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T13:15:25Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T13:15:25Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T13:15:25Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T13:15:25Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[34f44ad589798722af97f80b4f2b132367b62bbd ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[34f44ad589798722af97f80b4f2b132367b62bbd ] |D|=1 D=[13a6d13ebca60697607c59a6744a6692d7f0c785 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.i87SrqUOpa/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/13a6d13ebca60697607c59a6744a6692d7f0c785/pulls  utc=2026-08-19T13:15:26Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"6e35439367d852d14ebd5c6d125e8c93370970a0"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/6e35439367d852d14ebd5c6d125e8c93370970a0/check-runs  utc=2026-08-19T13:15:26Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T13:15:26Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T13:15:26Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"6e35439367d852d14ebd5c6d125e8c93370970a0","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=6e35439367d852d14ebd5c6d125e8c93370970a0  utc=2026-08-19T13:15:26Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "4e5a62099a2f3b139317af7d0dde214a3ebe4b18", "size": 619, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBjb250YWluZXI6CiAgICAgIGltYWdlOiBhbHBpbmU6MwogICAgc3RlcHM6CiAgICAgIC0gdXNlczogYWN0aW9ucy9jaGVja291dEAxMWJkNzE5MDFiYmU1YjE2MzBjZWVhNzNkMjc1OTczNjRjOWFmNjgzCiAgICAgICAgd2l0aDoKICAgICAgICAgIGZldGNoLWRlcHRoOiAwCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBiYXNoIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgcHJpbnRmICclcyAgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2hcbicgOTU3YmY0OWRhOGZjNmFlMzlmOTdhYmU2Nzk0MTFhZmVhYTVhNTlmNzA3ZjM1YmYzYjNhOGM2ZjlkZTE0MWYwZCB8IHNoYXN1bSAtYSAyNTYgLWMgLQ==\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@6e35439367d852d14ebd5c6d125e8c93370970a0 (encoding=base64 size=619):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     container:
  |       image: alpine:3
  |     steps:
  |       - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
  |         with:
  |           fetch-depth: 0
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions={'contents': 'read'} · on⊆['pull_request', 'push'] | 잡 키⊆['runs-on', 'steps'] · runs-on∈['ubuntu-24.04', 'ubuntu-latest'] | steps=3[checkout@40-hex, 정본 A, 정본 B]
  | WF-C1 워크플로 키 = ['jobs', 'name', 'on', 'permissions'] · 잡 키 = ['container', 'runs-on', 'steps'] · steps 이름 = ['actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-CJ 정본 잡 템플릿 위배 1건: ["잡 허용 키 밖 ['container'] (닫힌 집합 ['runs-on', 'steps'])"]
  | WF-C3 [A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치 = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C3 [B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치 = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=13a6d13ebca60697607c59a6744a6692d7f0c785 head=6e35439367d852d14ebd5c6d125e8c93370970a0 정본 잡 불일치 — 잡 템플릿(워크플로/잡 허용 키·steps 3·checkout SHA 핀) 또는 정본 A/B byte 위배 (T-84 ⑬a~⑬j)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=13a6d13ebca60697607c59a6744a6692d7f0c785 head=6e35439367d852d14ebd5c6d125e8c93370970a0 정본 잡 불일치 — 잡 템플릿(워크플로/잡 허용 키·steps 3·checkout SHA 핀) 또는 정본 A/B byte 위배 (T-84 ⑬a~⑬j) [수집 1건 중 전순서 최소]
u17_rc=1

########## ③ 회귀 불변 — v2.21 증거·에라타 1차 배터리를 «잡 템플릿» 술어로 재실행 ##########
  주: v2.21/에라타1차 픽스처는 «잡 템플릿» 요건(체크아웃 스텝·permissions·on) 을 갖지 않으므로,
      run: 층 판정만 비교하기 위해 «정본 잡 템플릿에 그 run 을 이식»한 형태로 다시 만든다.
  이식 픽스처 7종 → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe2/wf3
  id                 기대                 실측(v221b)
  pos-canonical      BLOB_OK                BLOB_OK  [OK]
  ctrl-comments      BLOB_OK                BLOB_OK  [OK]
  ctrl-crlf          BLOB_OK                BLOB_OK  [OK]
  13a-echo           UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  13c-ortrue         UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  13g-exit0          UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  nbsp-trailing      UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]

########## ③-2 회귀 — 서버 잡 steps[] mock(⑭) 5종 불변 ##########
  ok          SERVER_OK              SERVER_OK  [OK]
  noverify    UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  verifyfail  UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  norun       UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  jobfail     UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
```

## 4. 술어·드라이버·생성기 원문

### 4-1. 정본 «잡» 대조 술어 `wfcanon-v221b.py` (sha256 `ff3dc344082828b3e73ead55e9401585d25452d79b6a144cba798768c9730085` · 226행)

```python
#!/usr/bin/env python3
"""U-17 (b)③ «정본 «잡» 대조» 술어 — v2.21 에라타 2차 계약 7adc1246 :5467-5530 의 문자 구현.

  wfcanon-v221.py(정본 «스텝» 대조)에서 파생 — 델타는 **에라타 2차 ⓑ 1건**: 대조 대상을 «두 스텝 run:»에서
  **«게이트 잡 객체 전체 + 워크플로 수준 키»**로 확장한다(stop-time BLOCK: `defaults.run.shell: "true {0}"` 가
  정본 스텝 byte·이름을 보존한 채 두 run 을 실행하지 않고 success 를 보고 — 스텝만 보면 통과).
  «허용 키 닫힌 집합 밖 = 불일치»로 «열거 없이» 닫는다(S-6).

계약 문언(요약 인용):
  (1) blob «정본 대조» — YAML 파서(기존 도구)로 `jobs.<게이트 잡>.steps[]` 를 얻어 게이트 두 스텝의
      `run:` 을 **정규화 후 계약 «정본»과 byte 대조**한다.  정본과 다르면(선행 exit/exec/가드·서브셸·
      heredoc·eval·`|| true`·`set +e`·선행 종결자 등 «전 구문 우회»를 열거 없이) → UNVERIFIED_REVISION.
      정규화(결정적): CRLF→LF · 각 줄 trailing 공백(**ASCII `[ \t]` 만**) 제거 · «빈 줄»과 «full-line
      주석»(첫 비-공백 문자가 `#`) 제거 · 남은 줄을 LF 로 결합.
      스텝 메타(닫힌 키 집합): `shell` 정본값만 · `continue-on-error: true` 부재 · `if` 부재/`success()` ·
      `timeout-minutes` ≠ 0 · run 스텝은 `name`·`run`·(선택 `shell`) «외 키 부재».
  (2) 서버 잡 스텝 대조 — v2.20 과 동일(스텝 이름·conclusion).

운영자 지침(CLAUDE.md Development Discipline: 바퀴 재발명 금지) 이행:
  · YAML 파싱은 **기존 도구 `yq`**(mikefarah) · 대조는 **byte 비교**(표준 문자열 연산)뿐.
  · v2.20 술어의 **자작 셸 토크나이저·명령 위치 판별기는 폐기**(정본 대조가 그 클래스를 열거 없이 닫는다).
출력: `WF-*` 관측 라인 + 마지막 줄 `RESULT=BLOB_OK|UNVERIFIED_REVISION|UNVERIFIABLE` · rc 0/1/2.
"""
import json, os, subprocess, sys

GATE_JOB = os.environ.get("WF_GATE_JOB", "tos-gate")
HARNESS  = os.environ.get("WF_HARNESS", "tools/tos_entry_harness.sh")
SHA      = os.environ.get("WF_SHA", "957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d")
STEP_RUN = os.environ.get("WF_STEP_RUN", "tos-gate: run harness")
STEP_VER = os.environ.get("WF_STEP_VER", "tos-gate: verify harness sha256")

# ── 계약 정본 (계약 :5473-5490 코드펜스 원문에서 그대로 옮긴 리터럴)
CANON_A = "set -euo pipefail\nbash %s" % HARNESS
CANON_B = ("set -euo pipefail\n"
           r"printf '%s  " + HARNESS + r"\n' " + SHA + " | shasum -a 256 -c -")
CANON_B = CANON_B.replace("printf '%s  ", "printf '%s  ")   # (표기 고정 — 두 칸 공백)
SHELL_OK = {"bash", "bash -euo pipefail {0}", "bash -eo pipefail {0}"}
ALLOWED_JOB_KEYS = {"runs-on", "steps"}                 # 계약 :5479 — 잡 허용 키 «닫힌 집합»
RUNS_ON_OK = {"ubuntu-latest", "ubuntu-24.04"}          # 계약 :5480 — GitHub-hosted 닫힌 리터럴(self-hosted·배열 금지)
ON_OK = {"pull_request", "push"}                        # 계약 :5478 — on 닫힌 집합
PERM_OK = {"contents": "read"}                          # 계약 :5478 — permissions 최소
CHECKOUT_PREFIX = "actions/checkout@"                   # 계약 :5482 — 40-hex SHA 핀(태그 금지)
CHECKOUT_WITH_OK = {"fetch-depth"}                      # 계약 :5483 — 최소 with
STEP1_KEYS = {"uses", "with"}
ALLOWED_KEYS = {"name", "run", "shell"}


def normalize(run):
    """계약 정규화 규칙 — CRLF→LF · 줄 trailing ASCII [ \\t] 제거 · 빈 줄/full-line 주석 제거 · LF 결합."""
    s = run.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in s.split("\n"):
        line = line.rstrip(" \t")             # [ASCII 핀] NBSP 등 유니코드 공백은 «제거하지 않는다»
        if line.strip(" \t") == "":
            continue
        if line.lstrip(" \t").startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def parse_yaml(path):
    """기존 도구 재사용 — mikefarah yq (진짜 YAML 파서·주석 폐기·folded/literal 스칼라 처리)."""
    r = subprocess.run(["yq", "-o=json", ".", path], capture_output=True, text=True)
    if r.returncode != 0:
        return None, "yq 파싱 실패: " + r.stderr.strip()[:200]
    try:
        return json.loads(r.stdout), ""
    except Exception as e:
        return None, "JSON 변환 실패: %r" % (e,)


def meta_check(st, kind):
    """닫힌 메타 키 집합 (계약 :5504-5507)."""
    why = []
    if st.get("continue-on-error") in (True, "true"):
        why.append("continue-on-error: true")
    if "if" in st and str(st["if"]).strip() not in ("success()", "${{ success() }}"):
        why.append("if: %r" % (st["if"],))
    if "timeout-minutes" in st:
        try:
            if int(st["timeout-minutes"]) == 0:
                why.append("timeout-minutes: 0")
        except Exception:
            why.append("timeout-minutes: %r(비수치)" % (st["timeout-minutes"],))
    if "shell" in st and str(st["shell"]).strip() not in SHELL_OK:
        why.append("shell: %r (정본값 아님)" % (st["shell"],))
    extra = sorted(set(st) - ALLOWED_KEYS - {"continue-on-error", "if", "timeout-minutes"})
    if extra:
        why.append("추가 메타 키 %s (닫힌 집합 위배)" % extra)
    return (not why), "; ".join(why)


def job_template(doc):
    """[에라타 2차 ⓑ] 워크플로 수준 + 게이트 잡 객체 «정본 잡 템플릿» 대조 (계약 :5472-5484)."""
    why = []
    # ── 워크플로 수준
    if "defaults" in doc:
        why.append("워크플로 `defaults` 실재 %r (부재여야 함 — 실행 무력화 표면)" % (doc["defaults"],))
    if "env" in doc:
        why.append("워크플로 `env` 실재 %r (부재여야 함 — PATH/환경 조작 표면)" % (doc["env"],))
    perm = doc.get("permissions")
    if perm != PERM_OK:
        why.append("`permissions` = %r ≠ 최소 %r" % (perm, PERM_OK))
    on = doc.get("on")
    on_set = set(on) if isinstance(on, (list, dict)) else ({on} if isinstance(on, str) else set())
    if not on_set or not on_set <= ON_OK:
        why.append("`on` = %r ⊄ 닫힌 집합 %s" % (on, sorted(ON_OK)))
    # ── 잡 수준
    job = (doc.get("jobs") or {}).get(GATE_JOB) or {}
    extra = sorted(set(job) - ALLOWED_JOB_KEYS)
    if extra:
        why.append("잡 허용 키 밖 %s (닫힌 집합 %s)" % (extra, sorted(ALLOWED_JOB_KEYS)))
    ro = job.get("runs-on")
    if not isinstance(ro, str) or ro not in RUNS_ON_OK:
        why.append("`runs-on` = %r ∉ 닫힌 리터럴 %s (배열·self-hosted 금지)" % (ro, sorted(RUNS_ON_OK)))
    steps = job.get("steps") or []
    if len(steps) != 3:
        why.append("`steps` 길이 = %d ≠ 3 (추가/선행 스텝 부재여야 함)" % len(steps))
        return why, steps
    # ── 스텝 ① 체크아웃 (SHA 핀)
    s1 = steps[0]
    k1 = sorted(set(s1) - STEP1_KEYS)
    if k1:
        why.append("체크아웃 스텝 허용 키 밖 %s" % k1)
    uses = str(s1.get("uses", ""))
    if not uses.startswith(CHECKOUT_PREFIX):
        why.append("스텝① `uses` = %r (기대 %s<40-hex>)" % (uses, CHECKOUT_PREFIX))
    else:
        ref = uses[len(CHECKOUT_PREFIX):]
        if not (len(ref) == 40 and all(c in "0123456789abcdef" for c in ref.lower())):
            why.append("체크아웃 ref = %r 가 40-hex SHA 핀이 아니다(태그 금지)" % ref)
    w = s1.get("with") or {}
    wextra = sorted(set(w) - CHECKOUT_WITH_OK)
    if wextra:
        why.append("체크아웃 `with` 허용 키 밖 %s" % wextra)
    # ── 스텝 ②③ 순서 고정
    if steps[1].get("name") != STEP_RUN:
        why.append("스텝② name = %r ≠ %r (순서 고정)" % (steps[1].get("name"), STEP_RUN))
    if steps[2].get("name") != STEP_VER:
        why.append("스텝③ name = %r ≠ %r (순서 고정)" % (steps[2].get("name"), STEP_VER))
    return why, steps


def blob_layer(path):
    doc, err = parse_yaml(path)
    print("WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = «정본 잡 템플릿» 구조 + run 정규화 후 byte 비교")
    print("WF-C0 정본 A = %r" % CANON_A)
    print("WF-C0 정본 B = %r" % CANON_B)
    print("WF-C0 잡 템플릿: 워크플로 defaults/env 부재 · permissions=%r · on⊆%s | 잡 키⊆%s · runs-on∈%s | steps=3[checkout@40-hex, 정본 A, 정본 B]"
          % (PERM_OK, sorted(ON_OK), sorted(ALLOWED_JOB_KEYS), sorted(RUNS_ON_OK)))
    if doc is None:
        print("WF-C1 " + err)
        return "UNVERIFIABLE"
    jobs = (doc or {}).get("jobs") or {}
    if GATE_JOB not in jobs:
        print("WF-C1 게이트 잡 «%s» 부재 (jobs=%s)" % (GATE_JOB, list(jobs)))
        return "UNVERIFIED_REVISION"
    print("WF-C1 워크플로 키 = %s · 잡 키 = %s · steps 이름 = %s"
          % (sorted(doc), sorted(jobs[GATE_JOB] or {}),
             [s.get("name") or s.get("uses") for s in ((jobs[GATE_JOB] or {}).get("steps") or [])]))
    verdict = "BLOB_OK"
    tmpl_why, steps = job_template(doc)
    print("WF-CJ 정본 잡 템플릿 위배 %d건: %s" % (len(tmpl_why), tmpl_why if tmpl_why else "없음"))
    if tmpl_why:
        verdict = "UNVERIFIED_REVISION"
    for want, canon, kind in ((STEP_RUN, CANON_A, "A/run harness"), (STEP_VER, CANON_B, "B/verify sha256")):
        hit = [s for s in steps if s.get("name") == want]
        if not hit:
            print("WF-C2 [%s] 스텝 이름 «%s» 부재 → UNVERIFIED_REVISION" % (kind, want))
            verdict = "UNVERIFIED_REVISION"
            continue
        st = hit[0]
        run = st.get("run")
        if not isinstance(run, str):
            print("WF-C2 [%s] run: 실행문 부재(run 이 문자열 아님) → UNVERIFIED_REVISION" % kind)
            verdict = "UNVERIFIED_REVISION"
            continue
        nrm = normalize(run)
        same = (nrm == canon)
        print("WF-C3 [%s] 정규형 = %r" % (kind, nrm))
        print("WF-C4 [%s] byte 일치 = %s" % (kind, same))
        mok, mwhy = meta_check(st, kind)
        print("WF-C5 [%s] 스텝 키 = %s · 메타 닫힌 집합 = %s%s" % (kind, sorted(st), mok, "" if mok else " (%s)" % mwhy))
        if not (same and mok):
            verdict = "UNVERIFIED_REVISION"
    print("WF-C6 blob 층 판정 = %s" % verdict)
    return verdict


def server_layer(path):
    """actions/runs/{run_id}/jobs 응답에서 게이트 잡·두 스텝 이름·conclusion 대조 (v2.20 과 동일)."""
    try:
        j = json.load(open(path))
    except Exception as e:
        print("WF-S0 jobs 응답 파싱 실패 %r → UNVERIFIABLE" % (e,))
        return "UNVERIFIABLE"
    jobs = j.get("jobs") or []
    hit = [x for x in jobs if x.get("name") == GATE_JOB]
    print("WF-S1 서버 jobs[] 이름 = %s" % [x.get("name") for x in jobs])
    if not hit:
        print("WF-S2 게이트 잡 «%s» 서버 기록 부재 → UNVERIFIED_REVISION" % GATE_JOB)
        return "UNVERIFIED_REVISION"
    job = hit[0]
    print("WF-S2 게이트 잡 conclusion = %r" % job.get("conclusion"))
    if job.get("conclusion") != "success":
        return "UNVERIFIED_REVISION"
    steps = job.get("steps") or []
    print("WF-S3 서버 steps[] = %s" % [(s.get("name"), s.get("conclusion")) for s in steps])
    for want in (STEP_RUN, STEP_VER):
        m = [s for s in steps if s.get("name") == want]
        if not m:
            print("WF-S4 스텝 이름 «%s» 서버 부재 → UNVERIFIED_REVISION (T-84 ⑭)" % want)
            return "UNVERIFIED_REVISION"
        if m[0].get("conclusion") != "success":
            print("WF-S4 스텝 «%s» conclusion=%r ≠ success → UNVERIFIED_REVISION (T-84 ⑭)" % (want, m[0].get("conclusion")))
            return "UNVERIFIED_REVISION"
    print("WF-S5 서버 층 판정 = SERVER_OK")
    return "SERVER_OK"


if __name__ == "__main__":
    mode = sys.argv[1]
    res = blob_layer(sys.argv[2]) if mode == "blob" else server_layer(sys.argv[2])
    print("RESULT=" + res)
    sys.exit(0 if res in ("BLOB_OK", "SERVER_OK") else (2 if res == "UNVERIFIABLE" else 1))
```

### 4-2. 픽스처 생성기 `mkwf-e2.py` (sha256 `50a0c9e4427105cbe060b43f65a3c1350e606a87f633b9c817a10feb6d784feb` · 70행)

```python
#!/usr/bin/env python3
"""mkwf-e2.py — v2.21 에라타 2차(잡 템플릿) 픽스처 — 워크플로/잡 «키»와 steps 배치를 변형한다.

mkwf-v221.py 의 정본 run 리터럴(RUNA/RUNB)을 import 재사용한다(같은 바이트 규약·바퀴 재발명 금지).
계약 :5472-5484 «정본 잡 템플릿» 을 기준으로, 각 케이스는 (id, 기대, 설명, bytes).
"""
import importlib.util, os, pathlib, sys

SP = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mk", SP / "mkwf-v221.py")
mk = importlib.util.module_from_spec(spec); spec.loader.exec_module(mk)
RUNA, RUNB = mk.RUNA, mk.RUNB
CHECKOUT_SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"      # actions/checkout v4.2.2 커밋 SHA (40-hex 핀 «형식» 실증용)


def steps_block(pre="", post="", order="AB", checkout="sha", step_extra_a="", job_extra="", wf_extra="", runs_on="ubuntu-latest",
                perms="permissions:\n  contents: read\n", on_line="on: [pull_request]\n"):
    def runstep(name, run, extra=""):
        body = "\n".join("          " + ln if ln else "" for ln in run.split("\n"))
        e = ("\n" + "\n".join("        " + x for x in extra.split("\n"))) if extra else ""
        return f'      - name: "{name}"{e}\n        run: |\n{body}\n'
    co = ""
    if checkout == "sha":
        co = f"      - uses: actions/checkout@{CHECKOUT_SHA}\n        with:\n          fetch-depth: 0\n"
    elif checkout == "tag":
        co = "      - uses: actions/checkout@v4\n        with:\n          fetch-depth: 0\n"
    a = runstep("tos-gate: run harness", RUNA, step_extra_a)
    b = runstep("tos-gate: verify harness sha256", RUNB)
    steps = co + (pre or "") + (a + b if order == "AB" else b + a) + (post or "")
    job = f"  tos-gate:\n    runs-on: {runs_on}\n" + (job_extra or "") + "    steps:\n" + steps
    return "name: tos-gate\n" + on_line + perms + (wf_extra or "") + "jobs:\n" + job


PRE_PATH = '      - name: "prepare"\n        run: |\n          echo /x >> $GITHUB_PATH\n'
POST_EXTRA = '      - name: "after"\n        run: |\n          true\n'

CASES = [
    ("pos-job-template", "BLOB_OK",             "양성 — 정본 잡 템플릿 정확(checkout SHA 핀 + 정본 A/B)", steps_block()),
    # ⑬h 실행 무력화 defaults
    ("13h-wf-defaults",  "UNVERIFIED_REVISION", "⑬h — 워크플로 `defaults.run.shell: \"true {0}\"`(BLOCK 재현)",
     steps_block(wf_extra='defaults:\n  run:\n    shell: "true {0}"\n')),
    ("13h-job-defaults", "UNVERIFIED_REVISION", "⑬h — 잡 수준 `defaults.run.shell: \"true {0}\"`",
     steps_block(job_extra='    defaults:\n      run:\n        shell: "true {0}"\n')),
    ("13h-wf-workdir",   "UNVERIFIED_REVISION", "⑬h — 워크플로 `defaults.run.working-directory`",
     steps_block(wf_extra="defaults:\n  run:\n    working-directory: /tmp\n")),
    # ⑬i 스텝 배치
    ("13i-pre-step",     "UNVERIFIED_REVISION", "⑬i — 선행 run 스텝(`echo /x >> $GITHUB_PATH`) → steps 4", steps_block(pre=PRE_PATH)),
    ("13i-post-step",    "UNVERIFIED_REVISION", "⑬i — 후행 추가 스텝 → steps 4", steps_block(post=POST_EXTRA)),
    ("13i-order-swap",   "UNVERIFIED_REVISION", "⑬i — 정본 A/B 순서 뒤바꿈", steps_block(order="BA")),
    ("13i-checkout-tag", "UNVERIFIED_REVISION", "⑬i — 체크아웃 태그(`@v4`) — SHA 핀 요구 위배", steps_block(checkout="tag")),
    ("13i-no-checkout",  "UNVERIFIED_REVISION", "⑬i — 체크아웃 누락 → steps 2", steps_block(checkout="none")),
    # ⑬j 잡 실행환경 키
    ("13j-container",    "UNVERIFIED_REVISION", "⑬j — 잡 `container:`(가짜 이미지)", steps_block(job_extra="    container:\n      image: alpine:3\n")),
    ("13j-self-hosted",  "UNVERIFIED_REVISION", "⑬j — `runs-on: self-hosted`", steps_block(runs_on="self-hosted")),
    ("13j-job-env",      "UNVERIFIED_REVISION", "⑬j — 잡 `env:`", steps_block(job_extra="    env:\n      PATH: /x\n")),
    ("13j-wf-env",       "UNVERIFIED_REVISION", "⑬j — 워크플로 `env:`", steps_block(wf_extra="env:\n  PATH: /x\n")),
    ("13j-strategy",     "UNVERIFIED_REVISION", "⑬j — 잡 `strategy.matrix`", steps_block(job_extra="    strategy:\n      matrix:\n        n: [1, 2]\n")),
    ("13j-job-uses",     "UNVERIFIED_REVISION", "⑬j — 잡 `uses:`(reusable workflow)", steps_block(job_extra="    uses: ./.github/workflows/other.yml\n")),
    ("13j-perm-writeall","UNVERIFIED_REVISION", "⑬j — `permissions: write-all`(최소 위배)", steps_block(perms="permissions: write-all\n")),
    ("13j-on-dispatch",  "UNVERIFIED_REVISION", "⑬j — `on: [workflow_dispatch]`(닫힌 집합 밖)", steps_block(on_line="on: [workflow_dispatch]\n")),
    ("13e-step-extra",   "UNVERIFIED_REVISION", "회귀 ⑬e — 스텝 A 에 `env:` 추가(스텝 메타 닫힌 집합)", steps_block(step_extra_a="env:\n  FOO: bar")),
]

if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True); idx = []
    for cid, exp, desc, text in CASES:
        open(os.path.join(out, cid + ".yml"), "wb").write(text.encode("utf-8"))
        idx.append("%s|%s|%s" % (cid, exp, desc))
    open(os.path.join(out, "INDEX.txt"), "w", encoding="utf-8").write("\n".join(idx) + "\n")
    print("fixtures=%d → %s (checkout pin=%s)" % (len(idx), out, CHECKOUT_SHA))
```

### 4-3. 드라이버 `t8xe2.sh` (sha256 `22b5c5384ec54427cb6c4f275acdd385b7c95b4b7cb067b0d2c01a50e2d4a8f3` · 195행)

```bash
#!/usr/bin/env bash
# t8xe2.sh — v2.21 «에라타 2차 재동결 7adc1246» S-24 ② 영향 변이 (ⓑ: 대조 대상 = 정본 «잡» 템플릿)
#   ① blob 배터리 18종(양성·⑬h·⑬i·⑬j·⑬e) — 신·구 술어 «동시» 실행(구 술어 통과 = stop-time BLOCK 재현)
#   ② e2e 3건(양성 ACTIVE · ⑬h UNVERIFIED_REVISION · 같은 seam 을 V221 실행기로 = ACTIVE/0 재현)
#   ③ 회귀 불변(v2.21 배터리 대표·folded B·⑭ 서버 mock).  GET-only(seam) · 서버 쓰기 0 · 픽스처 scratchpad.
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence
SP20=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence
SP19=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u17-verify-v220.sh"                      # 판정 실행기 (구조 파싱 + 서버 스텝 + 격리 스냅샷)
WFS="$SP/wfstruct-v220.py"                       # (b)③ 구조 파싱 술어
EX219="$SP19/u17-verify-v219e6.sh"               # 직전 판 실행기 — «두 리터럴 grep» (⑬⑭ 판별력 대조)
CTRL="$SP19/u17-verify-v219-CTRL-nohost.sh"; EX218="$SP19/u17-verify-v218e.sh"
FX="$SP/fx84v220"; SEAM="$SP/seam220"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md; WF=.github/workflows/tos-gate.yml
OR=kakao-harris-lee/kis_unified_sts; PINURL=https://github.com/kakao-harris-lee/kis_unified_sts.git
WB=mission-critical-trading-operating-system; REPO=/Users/harris/Development/private/kis_unified_sts
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
TLAND=2026-08-10T00:00:00Z
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; git -C "$1" remote add origin "${2:-$PINURL}"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; }
art(){ mkdir -p "$1/$(dirname $PC)"; { [ -n "${2:-}" ] && printf 'owner_repo: %s\n' "$2"; [ -n "${3:-}" ] && printf 'target_branch: %s\n' "$3"; printf 'tos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture\n'; } > "$1/$PC"
  git -C "$1" add -A; git -C "$1" commit -q -m "P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys $([ -n "${2:-}" ] && echo present || echo absent))"; git -C "$1" rev-parse HEAD; }
# [v2.20] 워크플로 본문 — 계약 리터럴 «스텝 이름» 2종.  variant: ok | echoarg(⑬a) | trailcomment(⑬b) | ortrue(⑬c) | yamlcomment | env | shcomment | echosha
wfcontent(){ local v="${1:-ok}"
  printf 'name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n'
  case "$v" in
    env) printf '    env:\n      HARNESS: tools/tos_entry_harness.sh\n      EXPECT: "%s"\n' "$LIT2" ;;
    yamlcomment) printf '    # tools/tos_entry_harness.sh %s\n' "$LIT2" ;;
  esac
  printf '    steps:\n      - uses: actions/checkout@v4\n      - name: "tos-gate: run harness"\n'
  case "$v" in
    echoarg)     printf '        run: |\n          echo "note: tools/tos_entry_harness.sh is referenced but not executed"\n' ;;
    yamlcomment|env) printf '        run: true\n' ;;
    shcomment)   printf '        run: |\n          # tools/tos_entry_harness.sh\n          true\n' ;;
    *)           printf '        run: bash tools/tos_entry_harness.sh\n' ;;
  esac
  printf '      - name: "tos-gate: verify harness sha256"\n'
  case "$v" in
    trailcomment) printf '        run: |\n          true  # shasum -a 256 tools/tos_entry_harness.sh | grep %s\n' "$LIT2" ;;
    ortrue)       printf '        run: shasum -a 256 tools/tos_entry_harness.sh | grep %s || true\n' "$LIT2" ;;
    yamlcomment|env) printf '        run: true\n' ;;
    shcomment)    printf '        run: |\n          # shasum -a 256 tools/tos_entry_harness.sh | grep %s\n          true\n' "$LIT2" ;;
    echosha)      printf '        run: |\n          shasum -a 256 tools/tos_entry_harness.sh\n          echo %s\n' "$LIT2" ;;
    *)            printf '        run: shasum -a 256 tools/tos_entry_harness.sh | grep %s\n' "$LIT2" ;;
  esac; }
wf(){ mkdir -p "$1/.github/workflows"; wfcontent "${2:-ok}" > "$1/$WF"; git -C "$1" add -A; git -C "$1" commit -q -m "W: add $WF (SIMULATED)"; git -C "$1" rev-parse HEAD; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact\n' > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "D0-A: introduce config/tos_completion.yaml"; git -C "$1" rev-parse HEAD; }
run(){ # run <repo> [responder] [executor] [env-prefix-label] — env 는 호출자가 앞에 붙인다
  echo "-- remotes --"; git -C "$1" remote -v | sed 's/^/  | /'
  echo "-- artifact @HEAD --"; git -C "$1" show "HEAD:$PC" 2>/dev/null | sed 's/^/  | /'
  git -C "$1" log --oneline --graph --format='%h %ad %s' --date=iso-strict | sed 's/^/  /'
  echo "\$ ${4:-}U17_RESPONDER=${2:-gh} bash $(basename "${3:-$EX}") <fixture>"
  env ${4:-} U17_RESPONDER="${2:-gh}" U17_CAPTURE_DIR="$(mktemp -d)" bash "${3:-$EX}" "$1"; echo "u17_rc=$?"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; if [ -f "$4" ]; then cp "$4" "$1/$(k "$2").body"; else printf '%s\n' "$4" > "$1/$(k "$2").body"; fi; }
ACT='{"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}'
RULES_APPLIED(){ printf '[{"type":"required_status_checks","ruleset_id":%s,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":%s},{"type":"non_fast_forward","ruleset_id":%s},{"type":"deletion","ruleset_id":%s}]' "$1" "$1" "$1" "$1"; }
RSET_ONE(){ printf '{"id":%s,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"%s","updated_at":"%s","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}' "$1" "$2" "$3"; }
RSET_LIST(){ printf '[{"id":%s,"name":"protect_main","target":"branch","enforcement":"active","created_at":"%s","updated_at":"%s"}]' "$1" "$2" "$3"; }
base_common(){ inject "$1" "apps/github-actions" 200 '{"id":15368,"slug":"github-actions","name":"GitHub Actions"}'; inject "$1" "repos/$OR" 200 '{"full_name":"kakao-harris-lee/kis_unified_sts","default_branch":"main"}'; }
seam_ruleset(){ # seam_ruleset <dir> <ruleset id> <created_at> <updated_at>
  rm -rf "$1"; mkdir -p "$1"; base_common "$1"
  inject "$1" "repos/$OR/branches/main/protection" 404 '{"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}'
  inject "$1" "repos/$OR/rules/branches/main" 200 "$(RULES_APPLIED "$2")"
  inject "$1" "repos/$OR/rulesets" 200 "$(RSET_LIST "$2" "$3" "$4")"
  inject "$1" "repos/$OR/rulesets/$2" 200 "$(RSET_ONE "$2" "$3" "$4")"; }
seam_classic(){ # seam_classic <dir> — classic branch protection 만 (적용 룰셋 0)
  rm -rf "$1"; mkdir -p "$1"; base_common "$1"
  inject "$1" "repos/$OR/branches/main/protection" 200 "$ACT"
  inject "$1" "repos/$OR/rules/branches/main" 200 '[]'
  inject "$1" "repos/$OR/rulesets" 200 '[]'; }
contents_json(){ python3 - "$1" "$2" "$3" <<'PY'
import json,sys,base64
t=open(sys.argv[1],'rb').read()
print(json.dumps({"name":sys.argv[3].split("/")[-1],"path":sys.argv[3],"sha":sys.argv[2],"size":len(t),"type":"file","encoding":"base64","content":base64.b64encode(t).decode()+"\n"}))
PY
}
rev_seam(){ # rev_seam <dir> <d> <head> <suite> <merged_at|NOPR> [wf-variant] [jobs-variant]
  local dir="$1" d="$2" h="$3" s="$4" m="$5" wfv="${6:-ok}" jv="${7:-ok}"
  if [ "$m" = NOPR ]; then inject "$dir" "repos/$OR/commits/$d/pulls" 200 '[]'; return; fi
  inject "$dir" "repos/$OR/commits/$d/pulls" 200 "[{\"number\":9999,\"state\":\"closed\",\"merged_at\":\"$m\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$h\"}}]"
  inject "$dir" "repos/$OR/commits/$h/check-runs" 200 "{\"total_count\":2,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}},{\"name\":\"tos-gate\",\"conclusion\":\"success\",\"app\":{\"id\":15368,\"slug\":\"github-actions\"},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}}]}"
  inject "$dir" "repos/$OR/check-suites/$s" 200 "{\"id\":$s,\"head_sha\":\"$h\",\"app\":{\"id\":15368,\"slug\":\"github-actions\"},\"status\":\"completed\",\"conclusion\":\"success\"}"
  inject "$dir" "repos/$OR/actions/runs?check_suite_id=$s" 200 "{\"total_count\":1,\"workflow_runs\":[{\"id\":424242,\"name\":\"tos-gate\",\"path\":\"$WF\",\"head_sha\":\"$h\",\"check_suite_id\":$s,\"conclusion\":\"success\"}]}"
  wfcontent "$wfv" > "$dir/wf.txt"; inject "$dir" "repos/$OR/contents/$WF?ref=$h" 200 "$(contents_json "$dir/wf.txt" "$(git hash-object "$dir/wf.txt")" "$WF")"
  # [v2.20 #1(2)] 서버 잡 스텝 기록 — actions/runs/{run_id}/jobs
  inject "$dir" "repos/$OR/actions/runs/424242/jobs" 200 "$(jobs_json "$jv" "$h")"; }
jobs_json(){ # jobs_json <variant> <head>  — ok | noverify | verifyfail | jobfail | norun
  local v="$1" h="$2" steps
  case "$v" in
    ok)         steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]' ;;
    noverify)   steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2}]' ;;
    verifyfail) steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"failure","number":3}]' ;;
    norun)      steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":2}]' ;;
    jobfail)    steps='[{"name":"tos-gate: run harness","conclusion":"success","number":1},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":2}]' ;;
  esac
  local jc=success; [ "$v" = jobfail ] && jc=failure
  printf '{"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"%s","head_sha":"%s","steps":%s}]}' "$jc" "$h" "$steps"; }
EX="$SP/u17-verify-v221b.sh"; WFS="$SP/wfcanon-v221b.py"
EX221="$SP/u17-verify-v221.sh"; WFS221="$SP/wfcanon-v221.py"
FX="$SP/fx8xe2"; SEAM="$SP/seam8xe2"
rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"
printf 't8xe2_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for f in "$EX" "$WFS" "$EX221" "$WFS221" "$SP/mkwf-e2.py"; do printf 'sha256(%s)=%s\n' "$(basename "$f")" "$(shasum -a 256 "$f" | cut -d" " -f1)"; done
printf -- '-- 실행기 델타 (v2.21 → 에라타 2차) --\n'; diff "$EX221" "$EX" | sed 's/^/  /'
printf 'git=%s · yq=%s · python3=%s\n' "$(git --version)" "$(yq --version)" "$(python3 -V)"
inj_wf(){ printf '%s' "$2" > "$1/wf.txt"; inject "$1" "repos/$OR/contents/$WF?ref=$3" 200 "$(contents_json "$1/wf.txt" "$(git hash-object "$1/wf.txt")" "$WF")"; }

########################################################################
sec "① blob 배터리 — 정본 «잡» 템플릿 18 픽스처 · 신(v221b) vs 구(v221 = 스텝만) 술어 동시 실행"
python3 "$SP/mkwf-e2.py" "$FX/wf" | sed 's/^/  /'
printf '  %-18s %-22s %-22s %-22s %s\n' "id" "기대(계약 ⑬h~⑬j)" "실측(v221b·잡)" "대조(v221·스텝만)" "설명"
FAIL=0; BLOCKN=0
while IFS='|' read -r cid exp desc; do
  got=$(python3 "$WFS" blob "$FX/wf/$cid.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  old=$(python3 "$WFS221" blob "$FX/wf/$cid.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  mark=OK; [ "$got" = "$exp" ] || { mark="MISMATCH"; FAIL=$((FAIL+1)); }
  [ "$exp" = "UNVERIFIED_REVISION" ] && [ "$old" = "BLOB_OK" ] && BLOCKN=$((BLOCKN+1))
  printf '  %-18s %-22s %-22s %-22s %s  [%s]\n' "$cid" "$exp" "$got" "$old" "$desc" "$mark"
done < "$FX/wf/INDEX.txt"
echo "  ⇒ 기대와 다른 케이스 = $FAIL 건 · 구 술어가 «통과»시킨 red 케이스 = $BLOCKN 건 (stop-time BLOCK 클래스)"
echo
echo "-- 대표 3종 술어 원문 (양성 · ⑬h 워크플로 defaults · ⑬i 선행 스텝) --"
for c in pos-job-template 13h-wf-defaults 13i-pre-step; do
  echo "== $c =="; sed 's/^/  | /' "$FX/wf/$c.yml"; python3 "$WFS" blob "$FX/wf/$c.yml" 2>&1 | sed 's/^/  /'
done

########################################################################
sec "② e2e — 픽스처 저장소(P → W → d) · seam blob 만 바꾼다"
RB="$FX/blob"; mk "$RB"; art "$RB" "$OR" main >/dev/null; WHB=$(wf "$RB" ok); DB=$(d0a "$RB")
echo "  W(PR head)=$WHB  d=$DB"
e2e(){ local S1="$SEAM/$2"; seam_ruleset "$S1" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z
  rev_seam "$S1" "$DB" "$WHB" 777001 "$TLAND" ok ok
  inj_wf "$S1" "$(cat "$FX/wf/$1.yml")" "$WHB"; run "$RB" "file:$S1" "${3:-$EX}"; }

sec "②-1 양성 — 정본 잡 템플릿 정확 ⇒ PREVENTION_ACTIVE + rc 0"
e2e pos-job-template pos

sec "②-2 ⑬h `defaults.run.shell: \"true {0}\"` ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0"
e2e 13h-wf-defaults h

sec "②-3 stop-time BLOCK 재현 — 같은 seam 을 **V221 실행기**(스텝만 대조)로 → ACTIVE/0 이면 Codex 지적의 실증"
e2e 13h-wf-defaults h221 "$EX221"

sec "②-4 ⑬i 선행 PATH 조작 스텝 ⇒ PREVENTION_UNVERIFIED_REVISION"
e2e 13i-pre-step i

sec "②-5 ⑬j 잡 `container:` ⇒ PREVENTION_UNVERIFIED_REVISION"
e2e 13j-container j

########################################################################
sec "③ 회귀 불변 — v2.21 증거·에라타 1차 배터리를 «잡 템플릿» 술어로 재실행"
echo "  주: v2.21/에라타1차 픽스처는 «잡 템플릿» 요건(체크아웃 스텝·permissions·on) 을 갖지 않으므로,"
echo "      run: 층 판정만 비교하기 위해 «정본 잡 템플릿에 그 run 을 이식»한 형태로 다시 만든다."
python3 - "$SP" "$FX/wf3" <<'PYEOF'
import importlib.util, json, os, pathlib, subprocess, sys
SP, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("mk2", SP / "mkwf-e2.py"); mk2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(mk2)
OUT.mkdir(parents=True, exist_ok=True)
SRC = [("pos-canonical", "BLOB_OK"), ("ctrl-comments", "BLOB_OK"), ("ctrl-crlf", "BLOB_OK"),
       ("13a-echo", "UNVERIFIED_REVISION"), ("13c-ortrue", "UNVERIFIED_REVISION"),
       ("13g-exit0", "UNVERIFIED_REVISION"), ("nbsp-trailing", "UNVERIFIED_REVISION")]
idx = []
for cid, exp in SRC:
    p = SP / "wf" / (cid + ".yml")
    j = json.loads(subprocess.run(["yq", "-o=json", ".", str(p)], capture_output=True, text=True).stdout)
    st = j["jobs"]["tos-gate"]["steps"]
    a = st[0].get("run", ""); b = st[1].get("run", "")
    txt = mk2.steps_block()
    # 이식: 정본 잡 템플릿의 두 run 본문을 원 픽스처의 run 으로 교체
    def repl(t, old, new):
        oldb = "\n".join("          " + l if l else "" for l in old.rstrip("\n").split("\n"))
        newb = "\n".join("          " + l if l else "" for l in new.rstrip("\n").split("\n"))
        return t.replace(oldb, newb, 1)
    txt = repl(txt, mk2.RUNA, a); txt = repl(txt, mk2.RUNB, b)
    (OUT / (cid + ".yml")).write_bytes(txt.encode("utf-8"))
    idx.append(f"{cid}|{exp}")
(OUT / "INDEX.txt").write_text("\n".join(idx) + "\n", encoding="utf-8")
print(f"  이식 픽스처 {len(idx)}종 → {OUT}")
PYEOF
printf '  %-18s %-22s %s\n' "id" "기대" "실측(v221b)"
while IFS='|' read -r cid exp; do
  got=$(python3 "$WFS" blob "$FX/wf3/$cid.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  printf '  %-18s %-22s %s  [%s]\n' "$cid" "$exp" "$got" "$( [ "$got" = "$exp" ] && echo OK || echo MISMATCH )"
done < "$FX/wf3/INDEX.txt"

sec "③-2 회귀 — 서버 잡 steps[] mock(⑭) 5종 불변"
JD="$FX/jobs"; mkdir -p "$JD"
for v in ok noverify verifyfail norun jobfail; do
  jobs_json "$v" deadbeef > "$JD/$v.json"
  case "$v" in ok) EXP="SERVER_OK" ;; *) EXP="UNVERIFIED_REVISION" ;; esac
  GOT=$(python3 "$WFS" server "$JD/$v.json" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  printf '  %-11s %-22s %s  [%s]\n' "$v" "$EXP" "$GOT" "$( [ "$GOT" = "$EXP" ] && echo OK || echo MISMATCH )"
done
```

### 4-4. `s24-proof-e2.py` (sha256 `823a366dde314951861f1b531b93978503bc7db5f07cea7185a2b503a927ac14` · 111행)

```python
#!/usr/bin/env python3
"""s24-proof-e2.py — S-24 ① 2층 증명 (v2.21 에라타 65cf2635 → 에라타 2차 재동결 7adc1246).

① 무변경 구간 증명(기계 생성): `git diff -U0` 의 hunk 를 «자동» 추출해 그 여집합(=변경이 닿지 않은 구간)을
   양 blob 에서 sha256 비교한다.  구간 목록을 손으로 적지 않으므로 «누락»이 구조적으로 불가능하다.
② 명명 절 증명(리터럴 grep): 각 절을 «각 blob 안에서 리터럴 앵커로» 찾아(행 번호 하드코딩 금지) 그 행을
   sha256 비교한다 — 닿은 절/닿지 않은 절을 각각 명시하고 실측값을 방출한다.
"""
import hashlib, re, subprocess, sys

R = "/Users/harris/Development/private/kis_unified_sts"
C = "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md"
OLD, NEW = "65cf2635", "7adc1246"


def blob(rev):
    return subprocess.run(["git", "-C", R, "show", f"{rev}:{C}"], capture_output=True, text=True).stdout.split("\n")


def sha(t):
    return hashlib.sha256("\n".join(t).encode()).hexdigest()


old, new = blob(OLD), blob(NEW)
print(f"blob({OLD}:{C}) = {subprocess.run(['git','-C',R,'rev-parse',f'{OLD}:{C}'],capture_output=True,text=True).stdout.strip()}  행수={len(old)-1}")
print(f"blob({NEW}:{C}) = {subprocess.run(['git','-C',R,'rev-parse',f'{NEW}:{C}'],capture_output=True,text=True).stdout.strip()}  행수={len(new)-1}")

d = subprocess.run(["git", "-C", R, "diff", "-U0", f"{OLD}..{NEW}", "--", C], capture_output=True, text=True).stdout
hunks = []
for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", d, re.M):
    o1, oc, n1, nc = int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1)
    hunks.append((o1, oc, n1, nc))
print(f"\n① 무변경 구간 증명 — hunk {len(hunks)}개 (기계 추출): " +
      " · ".join(f"-{o1},{oc} +{n1},{nc}" for o1, oc, n1, nc in hunks))
print("   hunk 여집합 구간별 sha256 대조 (구간을 손으로 적지 않는다 — 누락 불가):")
po = pn = 0
bad = 0
for i, (o1, oc, n1, nc) in enumerate(hunks + [(len(old) + 1, 0, len(new) + 1, 0)], 1):
    so, sn = old[po:o1 - 1], new[pn:n1 - 1]
    h1, h2 = sha(so), sha(sn)
    ok = "동일" if h1 == h2 else "상이(!!)"
    if h1 != h2:
        bad += 1
    print(f"   구간#{i}: old[{po+1}..{o1-1}] vs new[{pn+1}..{n1-1}]  {len(so)}행/{len(sn)}행  {h1[:16]} / {h2[:16]} → {ok}")
    po, pn = o1 - 1 + oc, n1 - 1 + nc
print(f"   ⇒ 변경이 «닿지 않은» 구간 차이 = {bad}건 (0 이어야 한다)")

ANCH_TOUCHED = [
    ("(b)③ 정본 «잡» 대조 도입 문장", "blob «정본"),
    ("정직 경계 절 (정본 대조 잔여)", "**정직 경계(비차단·상위 «닫지 못한다» 정직 경계와 같은 층)**"),
    ("T-84 ⑬ 행 (⑬h/⑬i/⑬j 신설)", "**T-84** | **U-17 예방 통제 활성 증거**"),
    ("심사 이력 v2.21 행 (1번째 출현)", "| **v2.21** |", 0),
    ("변경 이력 v2.21 행 (2번째 출현)", "| **v2.21** |", 1),
    ("(B) 주 — v2.21 신규 증거", "**v2.20 신규 증거 = `d101eb63`**"),
]
ANCH_UNTOUCHED = [
    ("정규화 규칙 문장 (E1 표기 전제)", "동일해야 한다."),
    ("스텝 메타 닫힌 키 집합 문장", "**스텝 메타(닫힌 키 집합)**"),
    ("서버 잡 스텝 대조 절 (2)", "**서버 잡 스텝 대조** — ①에서 얻은"),
    ("하니스 §12.3.4-R 블록 첫 줄", "#!/usr/bin/env bash"),
    ("하니스 §12.3.4-R 블록 끝 줄", 'emit ENTRY_OK "R-0~R-7 전부 기대와 일치"'),
    ("T-82 행 (종수 20)", "| **T-82** | **U-16 `closable=NO` 전이 provenance**"),
    ("T-81 행 (종수 19)", "| **T-81** | **U-15 P-0 후 재진입**"),
    ("U-17-c 상태 10값 정의", "U-17-c  상태  prevention_control_state"),
    ("(a) 술어 — required_status_checks", "TOS 게이트 체크 이름  아티팩트가 **파라미터로 선언**"),
    ("(α) 연속성 절", "룰셋 `created_at ≤ merged_at"),
    ("U-16-c c_APP 구조 정의 수식", "c_APP(a) = { x ⊑ HEAD :"),
    ("U-16 격리 스냅샷 «단일 방법»", "**단일 방법으로 고정**"),
    ("UNCHK-008 레지스터 행", "| UNCHK-008 |"),
    ("U-17 하니스 pre-D0-A 실체화 문장", "하니스 «파일»은 «pre-D0-A 실체화»"),
]


def find(lines, anchor, label):
    hit = [i for i, l in enumerate(lines) if anchor in l]
    return hit


print("\n② 명명 절 증명 — 각 blob 안에서 «리터럴 앵커»로 위치를 찾는다(행 번호 하드코딩 금지)")
print(f"   {'절':44s} {'old 행':>7s} {'new 행':>7s}  판정")
for tag, anchors in (("닿음", ANCH_TOUCHED), ("닿지 않음", ANCH_UNTOUCHED)):
    print(f"  [{tag}]")
    for item in anchors:
        label, anchor = item[0], item[1]
        idx = item[2] if len(item) > 2 else 0
        ho, hn = find(old, anchor, label), find(new, anchor, label)
        ho, hn = ho[idx:], hn[idx:]
        if not ho or not hn:
            print(f"   {label:42s} {'∅' if not ho else ho[0]+1:>7} {'∅' if not hn else hn[0]+1:>7}  앵커 미발견(!!)")
            continue
        so, sn = old[ho[0]], new[hn[0]]
        same = "동일" if so == sn else "상이"
        exp = "상이" if tag == "닿음" else "동일"
        mark = "✅" if same == exp else "❌ 기대와 다름"
        print(f"   {label:42s} {ho[0]+1:>7} {hn[0]+1:>7}  {same} (기대 {exp}) {mark}   sha256 {hashlib.sha256(so.encode()).hexdigest()[:12]} / {hashlib.sha256(sn.encode()).hexdigest()[:12]}")

# ③ 정본 A/B 코드펜스 — 각 blob 안에서 «리터럴 앵커»로 펜스를 찾아 내용 자체를 대조한다
def fence(lines, anchor):
    i = next(k for k, l in enumerate(lines) if anchor in l)
    f = [k for k in range(i, i + 14) if lines[k].strip() == "```"]
    return "\n".join(lines[f[0] + 1:f[1]]), f[0] + 2, f[1]
for lab, anc in (("정본 A", "정본 A** 와 일치"), ("정본 B", "정본 B** 와 일치")):
    ao, o1, o2 = fence(old, anc); an, n1, n2 = fence(new, anc)
    print(f"\n③ {lab} 코드펜스: old :{o1}-{o2} · new :{n1}-{n2} → byte 동일? {ao == an}")
    print(f"   내용 = {ao!r}")

hb_old = subprocess.run(["bash", "-c", f"git -C {R} show {OLD}:{C} | sed -n '4664,4764p' | shasum -a 256"], capture_output=True, text=True).stdout.split()[0]
hb_new = subprocess.run(["bash", "-c", f"git -C {R} show {NEW}:{C} | sed -n '4664,4764p' | shasum -a 256"], capture_output=True, text=True).stdout.split()[0]
print(f"\n④ 하니스 §12.3.4-R 블록(:4664-4764) sha256 — old={hb_old}\n"
      f"                                              new={hb_new}\n"
      f"   계약 리터럴 957bf49d… 와 일치? old={hb_old.startswith('957bf49d')} new={hb_new.startswith('957bf49d')} · 양자 byte-동일? {hb_old==hb_new}")
```

판정 실행기 `u17-verify-v221b.sh`(sha256 `23d47e3b8114ba200dbd5be4734f98401eef200652e92a72bd147d5d67ac83ff`)는 §2-1 의 diff 로 v2.21 실행기에서 전량 재구성된다.

## 5. 관측 보고 · 신규 결함 후보 (등급 · file:line)

### R-1 **[문언 — 값 미고정]** 체크아웃 SHA 핀이 «계약 리터럴»이라 적혔으나 계약에 40-hex 값이 없다

- `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5482` 은 `uses: actions/checkout@<40-hex SHA 핀 — 계약 리터럴·태그 금지>` 라고 적지만, 계약 본문 어디에도 **그 40-hex 값 자체가 없다**(전수 grep: `actions/checkout@` 출현은 :3721 의 역사적 `@v4` 서술과 이 자리뿐).
- 따라서 이 증거의 술어는 «값»이 아니라 **«형식»**(접두사 `actions/checkout@` + ref 가 40-hex)만 검사했고, 픽스처는 `actions/checkout` v4.2.2 커밋 SHA `11bd71901bbe5b1630ceea73d27597364c9af683` 를 **형식 실증용**으로 썼다(계약값이 아님을 명시).
- 극성: 값이 고정되지 않으면 **임의의 40-hex(예: 공격자 포크의 커밋)** 도 통과한다 — «태그 금지»는 닫히지만 «어느 SHA 인가»는 열려 있다. **등급: 문언(fail-open 표면 — 값 고정 필요).** 제안: 계약이 `actions/checkout@<40-hex>` 리터럴을 고정하거나, «D0-A 가 고정하고 계약이 그 값을 인용» 임을 명시.

### R-2 **[관측 — BLOCK 재현]** v2.21 술어는 16/17 red 케이스를 통과시킨다

같은 18 픽스처에서 구 술어(스텝만 대조)는 `defaults`(워크플로/잡)·`container`·`self-hosted`·잡/워크플로 `env`·`strategy`·`uses`·`permissions: write-all`·`on: workflow_dispatch`·선행/후행 스텝·순서 뒤바꿈·체크아웃 태그/누락을 **전부 `BLOB_OK`** 로 판정했다(§2-2 대조 열). e2e 에서도 `PREVENTION_ACTIVE`/rc 0(§2-3 ②-3). Codex 지적이 실행으로 재현·처분됐다. **등급: 관측(처분 확인).**

### R-3 **[관측]** 잡 허용 키 닫힌 집합 `{runs-on, steps}` 은 잡 `name:` 도 배제한다

계약 :5479 의 닫힌 집합에 `name` 이 없으므로, 게이트 잡에 `name: TOS Gate` 를 붙이면 불일치가 된다(이 증거의 술어는 문언대로 구현). 실용상 흔한 표기라 D0-A 작성 시 걸릴 수 있다 — **문언 그대로면 fail-closed(과잉 차단 방향)** 이며 위험은 아니다. **등급: 관측(문언 해석 기록).**

### R-4 **[fail-open/차단 등급 신규 결함 후보]** R-1 1건 (checkout SHA 값 미고정)

그 외에 계약 문언대로 구현했을 때 green 을 내는 자리는 없었다 — 18 픽스처 기대 불일치 0건, 회귀 12종 불변.

## 6. 사후 재조회 (서버 무변경 · HEAD 불변)

```text
post_e2_utc=2026-08-19T13:17:33Z
HEAD = 7adc1246bee6313021f601abe3ad82ac9e2a1e09  (7adc1246 와 동일? YES)
계약 워킹트리 blob   = 081b9bc34182beff9cfa01f01031896835dbaf2a  == 7adc1246 blob 081b9bc34182beff9cfa01f01031896835dbaf2a → 동일
개발계획 워킹트리 blob = 4b2f664f835c4f3c68e4dff8560214aaa70f8969  == 0528a919 blob 4b2f664f835c4f3c68e4dff8560214aaa70f8969 → 동일 (에라타 2차에서도 무변경)
7adc1246..HEAD 두 문서 커밋 = 0건 · 전체 커밋 = 0건
계약 행수 = 7551 · 개발계획 행수 = 580
하니스 sed -n 4664,4764p sha256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d (계약 리터럴 957bf49d… 일치? YES · 65cf2635 와 byte-동일? YES)
워킹트리 두 문서 변경 = 0건
본 저장소 [PARENTS-UNTRUSTED] 관측: replace -l=[] · info/grafts=ABSENT · is_shallow=false
-- 서버 사후 재조회 (GET 1회 · --hostname github.com) --
$ gh api -i --hostname github.com repos/kakao-harris-lee/kis_unified_sts/branches/main/protection    # utc=2026-08-19T13:17:34Z
  | HTTP/2.0 200 OK
  | X-Github-Request-Id: D25D:335F3A:D30358:EA7B6F:6A85ACEE
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks
  ⇒ (a) 술어 입력 불변: contexts=["test"] · tos-gate 부재 ⇒ 본 저장소 live 상태값 극성은 v2.20 증거(d101eb63) 와 동일하다
픽스처 격리: scratchpad 독립 저장소 31개 · 본 저장소 worktree 목록 3줄(이 증거는 worktree 0개 생성)
```
