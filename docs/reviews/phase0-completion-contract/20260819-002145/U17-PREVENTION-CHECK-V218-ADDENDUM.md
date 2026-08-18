# U17-PREVENTION-CHECK-V218-ADDENDUM — v2.18 에라타 `feb91d60` S-24 addendum (절 범위 diff 기계 증명 + 영향 변이 재실행: 서버측 워크플로 blob · 선언 키 선택 · 원격 공존)

> **비규범 부속** — 계약 v2.18 에라타 `feb91d60`(6,998행) 후 **S-24** 이행: 본 증거 `U17-PREVENTION-CHECK-V218.md`(`7a146466`, 동결 `5f4b7cfd` 결속)는 (4d) 규율을 준용해 편집하지 않고,
> ① `git diff 5f4b7cfd..feb91d60 -- <계약>` 전문과 **닿는/닿지 않는 절 범위의 diff 기계 증명**(§1)으로 **비영향 변이의 증거가 그대로 결속됨을 선언**하고, ② **영향 변이만 재실행**(§2~§4)한다.
> 실행 시점 HEAD == `feb91d60` · 계약 워킹트리 blob `aa7839b1` == feb91d60 blob(sha256 `2a7926831b8c6ababeb747d370bc8f9d1fff10678507b81a6196f65d6d793db5`) · `feb91d60..HEAD` 계약 커밋 0 ·
> 하니스 §12.3.4-R 블록(`sed -n '4528,4628p'`) sha256 **`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`** — 5f4b7cfd·feb91d60·워킹트리 전부 byte-동일(§1·§6).
> GET-only · 서버 설정 무변경(§6 재조회) · 픽스처 = scratchpad 독립 git repo. **판정 소비자는 이 파일의 응답을 신뢰하지 않고 스스로 live 조회한다**(대조용).
- **생성 시각**: 2026-08-18T19:15:39Z (UTC) · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트
- **실행기 결속**: sha256(u17-verify-v218e.sh) = `6b196756890f580058c38c4b8e1f44e39c95c1b4137a33377af2602ad414a15c`(본 증거 실행기 `cfbab4ae…` 대비 델타 = E1 R2 ③ 서버 조회 · E2 선언 키 선택 · 헤더 —
  `diff` 32행, §3 독해) · sha256(t84v218e.sh) = `aac1b72aade6b64c5bf33305b8cb360aeb7782c5bfb43eaa698c4aa77ce1d27c` · 절 범위 증명 스크립트 `s24-proof.sh`(§1 원문 출력).

## 0. 결속 선언 (S-24 ②·①)

| 변이 (본 증거 `7a146466` §3) | 닿는 에라타 절 | 처분 |
| --- | --- | --- |
| ① live INSUFFICIENT · ② seam(ACTIVE/INSUFFICIENT/UNVERIFIABLE) · ④ stub · ⑥ app.id 위조 · ⑦ checks[].app_id · ⑨ ARTIFACT_MUTATED/LATE · 부속 UNSIGNED · 본 저장소 ABSENT | (a) 술어(5109-5157→5120-5168 ∅) · (c) P_first/P_last·U-17-c(5329-5387→5351-5409 ∅) · (c-0) · §8 T-84 행(2868 ∅) · 하니스(4528-4628 ∅) | **비영향 — `7a146466` 증거 그대로 결속** (§1 기계 증명) |
| ⑤ 선언 불일치 · ⑩ 원격 불일치/공존 | E2(선언 키 «선택» — 있으면 대조) · E3(공존 «의도») | **문언 정합화 — 실행기 거동 불변**(있으면 대조·없으면 미발화·공존 허용). E2 «없음» 경로는 v2.18 본 증거에 없어 **§4 에서 신규 실측** |
| ③-b seam 양성 · R2-a/R2-b · ⑧ (그리고 ③-0 live 병기 중 «로컬 git show») | **E1 (R2 ③ 서버 조회)** — 5237-5239→5248-5261 | **재실행**(§4) — 실행기 R2 ③ 을 `contents/…?ref=` 서버 조회로 교체 · live 병기 재측정 |

- **결과 요약 (재실행분 · stdout·rc 원문 그대로)**:

| 변이 | 구성 · responder | 방출값 | rc | 기대 (feb91d60 §8 T-84 · U-17 E1/E2/E3) | 대조 |
| --- | --- | --- | --- | --- | --- |
| **E1 live 병기** | 실 repo PR#636 head `7656259d`(로컬 미보유): `contents/.github/workflows/tos-gate.yml?ref=7656259d` → **404** · `contents/.github/workflows/test.yml?ref=7656259d` → **200**(base64·`# .github/workflows/test.yml`·두 리터럴 0회) | (원자료) | — | «서버 blob 조회는 로컬 head 미보유와 무관하게 성립 · tos-gate.yml 은 그 head 에 부재 → UNVERIFIED_REVISION» | **일치** |
| ③-b seam (b) 양성 | 픽스처 `seed→P→W→d` · contents?ref=W **200**(base64 · 두 리터럴 grep 2·1) · 나머지 (b) 3중 충족 | `PREVENTION_ACTIVE` | 0 | E1 양성(모의) | **일치 (모의)** |
| R2-a seam | contents?ref=W **404** | `PREVENTION_UNVERIFIED_REVISION` — `contents http=404 (…부재·조회 실패) — 검사 생략 금지` | 1 | E1 «404/HTTP → UNVERIFIED_REVISION» | **일치** |
| R2-b seam | contents 200 이나 두 리터럴 부재(grep 0·0) | `PREVENTION_UNVERIFIED_REVISION` | 1 | E1 | **일치** |
| R2-c seam | contents 주입 응답 없음(네트워크 오류 모의) | `PREVENTION_UNVERIFIABLE`(1) | 1 | E1 «네트워크·인증 → UNVERIFIABLE» | **일치** |
| ⑧ seam | app 15368 · workflow run path=`test.yml` · contents 200 정상 | `PREVENTION_UNVERIFIED_REVISION` — `path≠.github/workflows/tos-gate.yml` | 1 | ⑧ | **일치 (E1 실행기 하 불변)** |
| **R2-d seam** | 판정 저장소에 PR head 커밋이 **없는** 별도 픽스처(squash 착지 모의) · 서버 blob 200 | `PREVENTION_ACTIVE` — `U17-B5x 로컬에 … 커밋 없음 — 서버 조회만으로 판정` | 0 | E1 의 동기(«정직한 착지도 항상 red» 해소) | **일치 (모의)** |
| **① live 선언 키 부재** | 아티팩트에 owner_repo/target_branch 없음 · 원격=핀 · gh | `PREVENTION_INSUFFICIENT` — `U17-T … 일치/선언 없음 (declared owner_repo=∅ … target_branch=∅ …)` | 1 | E2 «없으면 핀·API 파생이 유일 소스» → ① | **일치 (인증 실측)** |
| **⑤/⑩ live 선언 키 부재 + gitlab 원격** | 선언 없음 · 원격 `gitlab.com/kakao-harris-lee/kis_unified_sts` | `PREVENTION_TARGET_MISMATCH` — `핀과 일치하는 원격 부재`(선언 대조 미발화) | 1 | E2/E3 — 선언 없으면 MISMATCH 는 원격 축으로만 | **일치** |
| ⑤ live 선언 있음(비-default) | 선언 target=작업 브랜치 | `PREVENTION_TARGET_MISMATCH`(선언 대조) | 1 | E2 «있으면 대조» | **일치 (불변)** |
| (본 저장소) | HEAD `feb91d60` — 아티팩트 부재 | `PREVENTION_ABSENT`(수집 ABSENT·INSUFFICIENT → 2) | 1 | «현재 평가» | **일치** |

---

## 1. S-24 ① — `git diff 5f4b7cfd..feb91d60 -- <계약>` 전문 + 절 범위 diff 기계 증명

에라타가 닿는 절: **H1** 변경 이력 v2.18 행(:193 — 에라타 서술 추가) · **H2** U-17 핀 블록에 **E2**(선언 키 선택, old 5077 앞 +7행) · **E3**(원격 공존 의도, old 5081 앞 +4행) · **H3** (b) R2 ③
서버 조회 전환 **E1**(old 5237-5239 → new 5248-5261). 닿지 않는 절 범위(diff 공집합)는 아래 스크립트 출력에 행 범위로 명시 — 하니스 블록·§8 T-84 행·(a) 술어·(c) P_first/P_last·U-17-c 상태표/전순서 등.

```diff
diff --git a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
index e225bc1a..aa7839b1 100644
--- a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+++ b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
@@ -190,7 +190,7 @@
 | v1.1 | §3.0 신설 — 해당 작업이 `acd45c43`에서 수행돼 `15d48f72`에서 팬텀 할당으로 revert된 이력 확인 |
 | v1.2 | 심판 10건 반영. §3.0 인용에 사실 오류(F-1), §6.3이 선행 구현 누락(F-5), §4.2가 없는 열 참조(F-3) |
 | v1.3 | 재심 8건 + **운영자 결정 2건** 반영. **F-2를 "회피"로 판정받아 30/30을 거버넌스 트랙으로 정식 이관**. Phase 0 범위를 기계 검사 가능 축으로 축소하고 **불가 축을 §13 레지스터로 명시 노출**. T-3c 공집합 결함 수정 |
-| **v2.18** | **stop-time Codex BLOCK #3 5건 반영 — «v2.17 은 여전히 wrong-target·forged-gate 를 ACTIVE 로 승인한다».** ① **C1 (a) 가 required check «정체성»을 안 봤다** — `contexts` 의 **이름만** 검사해 **`tos-gate` 를 제3자 앱에 고정하면 (a) 통과**했고 `D=∅` 이면 (b) 가 생략돼 그대로 진입 승인(심판이 실행기 술어로 `prot_ok=True` 재현). → **`required_status_checks.checks[]` 의 그 컨텍스트 `app_id` == Actions app id**(룰셋은 `integration_id`) ② **C2 `app.id` 는 정본 워크플로를 식별하지 않는다** — **모든 Actions 잡이 같은 app id 를 갖고 한 suite 를 공유**한다(실측 PR #636 head 5 run 전부 동일). → **`gate_app_id` 파라미터 «폐지»**하고 `gh api apps/github-actions .id` 로 **서버 파생**(전역 상수를 아티팩트가 선언하면 그것이 위조 표면) + **워크플로 정체성 3중 결속**(run `path` == 계약 리터럴 `.github/workflows/tos-gate.yml` ∧ run `head_sha` == PR head ∧ **그 시점 워크플로 blob 이 하니스 호출·sha256 검증 스텝 포함**). **한계 정직 표기**: 3중은 **위조 비용을 올리지 «닫지» 않는다** — «서버가 그 파일 내용을 그대로 실행했다»는 공개 REST 로 증명 불가 ③ **C3 대상 결속 자기선택** — `remote_name` 을 **같은 아티팩트가 골랐고** 정규화가 **host 를 버려** 비-GitHub 동일 경로가 같은 값이 됐다. → **정본 host+owner/repo 를 계약 자체에 핀**(`github.com/kakao-harris-lee/kis_unified_sts` — `bound_paths` 안이라 **리뷰·재결속으로 보호**되고 **아티팩트는 선언하지 않는다**) · 정규화 **host 보존** · `git remote` 는 파생이 아니라 **«핀과 일치하는 원격이 존재하는가»의 대조**(원격 «이름»은 묻지 않는다) ⇒ **`remote_name` 폐지** ④ **C4 아티팩트 사후 편집** — 파라미터·countersign 은 HEAD 에서 읽으면서 순서는 **«최초 도입 P»** 만 봐 **P → 착수 → 편집**이 통과했다. → **`P_last`**(마지막 변경 커밋·구조 파생)로 바꾸고 `∀d∈D: P_last ⊰ d` ∧ 소비 blob == `P_last` 시점 blob. 위반 = **`PREVENTION_ARTIFACT_MUTATED`**(신설). **`LATE` 로 접지 않는 근거**: «순서가 늦다»는 순서를 고치면 되고 «착수 후 고쳤다»는 **그 편집이 무엇을 바꿨는지 재심사**해야 한다 ⑤ **C5 증거 결속** — v2.17 증거가 동결 `a3c95b4f` 에 결속됐는데 에라타 `75474351` 이 계약을 바꿔 **증거가 «이전 계약»을 검증한 상태**로 남았다. → **`S-24` 신설**(에라타 후 **재실행** 또는 **`git diff <freeze>..<errata>` 가 해당 절 범위에서 공집합임을 기계 증명**). **이번 판의 증거는 v2.18 «최종 동결 후»에 만든다**. **상태 8값 → 9값 / 차단 8 / 전순서 9단 · T-84 6종 → 10종**(⑦ 타 앱 고정 · ⑧ same-app wrong-workflow · ⑨ 아티팩트 사후 편집 · ⑩ 타 원격·타 호스트). **하니스 byte-identical·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
+| **v2.18** | **stop-time Codex BLOCK #3 5건 반영 — «v2.17 은 여전히 wrong-target·forged-gate 를 ACTIVE 로 승인한다».** ① **C1 (a) 가 required check «정체성»을 안 봤다** — `contexts` 의 **이름만** 검사해 **`tos-gate` 를 제3자 앱에 고정하면 (a) 통과**했고 `D=∅` 이면 (b) 가 생략돼 그대로 진입 승인(심판이 실행기 술어로 `prot_ok=True` 재현). → **`required_status_checks.checks[]` 의 그 컨텍스트 `app_id` == Actions app id**(룰셋은 `integration_id`) ② **C2 `app.id` 는 정본 워크플로를 식별하지 않는다** — **모든 Actions 잡이 같은 app id 를 갖고 한 suite 를 공유**한다(실측 PR #636 head 5 run 전부 동일). → **`gate_app_id` 파라미터 «폐지»**하고 `gh api apps/github-actions .id` 로 **서버 파생**(전역 상수를 아티팩트가 선언하면 그것이 위조 표면) + **워크플로 정체성 3중 결속**(run `path` == 계약 리터럴 `.github/workflows/tos-gate.yml` ∧ run `head_sha` == PR head ∧ **그 시점 워크플로 blob 이 하니스 호출·sha256 검증 스텝 포함**). **한계 정직 표기**: 3중은 **위조 비용을 올리지 «닫지» 않는다** — «서버가 그 파일 내용을 그대로 실행했다»는 공개 REST 로 증명 불가 ③ **C3 대상 결속 자기선택** — `remote_name` 을 **같은 아티팩트가 골랐고** 정규화가 **host 를 버려** 비-GitHub 동일 경로가 같은 값이 됐다. → **정본 host+owner/repo 를 계약 자체에 핀**(`github.com/kakao-harris-lee/kis_unified_sts` — `bound_paths` 안이라 **리뷰·재결속으로 보호**되고 **아티팩트는 선언하지 않는다**) · 정규화 **host 보존** · `git remote` 는 파생이 아니라 **«핀과 일치하는 원격이 존재하는가»의 대조**(원격 «이름»은 묻지 않는다) ⇒ **`remote_name` 폐지** ④ **C4 아티팩트 사후 편집** — 파라미터·countersign 은 HEAD 에서 읽으면서 순서는 **«최초 도입 P»** 만 봐 **P → 착수 → 편집**이 통과했다. → **`P_last`**(마지막 변경 커밋·구조 파생)로 바꾸고 `∀d∈D: P_last ⊰ d` ∧ 소비 blob == `P_last` 시점 blob. 위반 = **`PREVENTION_ARTIFACT_MUTATED`**(신설). **`LATE` 로 접지 않는 근거**: «순서가 늦다»는 순서를 고치면 되고 «착수 후 고쳤다»는 **그 편집이 무엇을 바꿨는지 재심사**해야 한다 ⑤ **C5 증거 결속** — v2.17 증거가 동결 `a3c95b4f` 에 결속됐는데 에라타 `75474351` 이 계약을 바꿔 **증거가 «이전 계약»을 검증한 상태**로 남았다. → **`S-24` 신설**(에라타 후 **재실행** 또는 **`git diff <freeze>..<errata>` 가 해당 절 범위에서 공집합임을 기계 증명**). **이번 판의 증거는 v2.18 «최종 동결 후»에 만든다**. **[v2.18 에라타 (동결 `5f4b7cfd` 후 증거 실행 `7a146466` 적발 — T-84 ①~⑩ 전건 기대 일치·S-24 결속 수록)]** ⓐ **E1 (실질)** — (b) ③ 의 워크플로 blob 검증이 **로컬 `git show <PR head>:…`** 를 전제해, squash·rebase 착지에서 **판정 저장소가 PR head 커밋을 보유하지 않으면**(실측: PR #636 head `7656259d` 로컬 미보유) **정직한 착지도 항상 red** 였다 → **`gh api repos/{pin}/contents/…?ref=<PR head.sha>`(서버 조회·base64 decode 후 두 리터럴 grep)** 로 전환, 404/HTTP → `UNVERIFIED_REVISION` · 네트워크/인증 → `UNVERIFIABLE`. **진실 원천이 서버라는 U-17 원칙과 정합**하며 로컬 `git show` 는 **보조 대조(선택)** ⓑ **E2 (문언 충돌)** — «아티팩트는 `canonical_target` 을 선언하지 않는다»(C3)와 §8 ⑤ 의 «선언 불일치 = MISMATCH» 가 충돌해 보였다 → **아티팩트의 `owner_repo`·`target_branch` 키는 «선택»**(있으면 대조·불일치 = MISMATCH / 없으면 핀·`default_branch` 가 유일 소스)으로 고정. **극성 서술**: 선택으로 둬도 약해지지 않는다 — 두 경우 모두 조회 대상은 핀이고 선언은 **추가 대조**일 뿐 대상을 «고를» 수 없다 ⓒ **E3** — 핀 일치 원격 «존재» 대조가 **비-핀 원격 공존을 허용**함은 **의도**임을 명시(«원격 이름·개수는 묻지 않는다 — 조회 대상은 핀이지 원격이 아니다»·포크/미러를 두는 정상 작업을 막지 않는다). **상태 8값 → 9값 / 차단 8 / 전순서 9단 · T-84 6종 → 10종**(⑦ 타 앱 고정 · ⑧ same-app wrong-workflow · ⑨ 아티팩트 사후 편집 · ⑩ 타 원격·타 호스트). **하니스 byte-identical·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
 | **v2.17** | **stop-time Codex BLOCK 3건 반영 — «U-17 이 잘못된 보호 대상과 비강제 체크를 ACTIVE 로 승인할 수 있다».** v2.16 은 **재결속 전이라 승인 표면을 가진 적이 없다.** ① **B1 — 대상 미결속**: `owner_repo`·`target_branch` 를 **아티팩트 선언값 그대로** 쓰고 실행기가 **형식만** 검사해, 실제 `origin`·정본 착지 브랜치와 결속되지 않았고 **`D = ∅` 이면 «임의 대상의 보호»만으로 진입 승인**됐다. 교정: `owner_repo` 는 **`git remote get-url origin` 파생**(원격 이름은 파라미터·기본 `origin`), `target_branch` 는 **`gh api repos/{o}/{r}` 의 `.default_branch`** 파생 — **선언값은 «대조 대상»으로 강등**하고 불일치 = **`PREVENTION_TARGET_MISMATCH`**(신설). `D ≠ ∅` 이면 **(b) 의 PR `base` == target 과 3중 일치**. **새 상태값인 근거**: `INSUFFICIENT` 로 접으면 «맞는 대상인데 약하다»와 «엉뚱한 대상을 봤다»가 같은 값이 되고 **운영자가 할 일이 완전히 다르다** ② **B2 — 논증 철회**: v2.16 의 «보호 꺼진 창의 커밋에는 흔적이 없다»는 **불성립이며 철회**한다 — **PR 체크는 보호 설정과 독립 실행**되므로 보호를 끄고 체크를 통과시켜 머지한 뒤 재활성하면 **정상 흔적이 남는다**. 그리고 **`app.id` 미검증**이라 제3자 앱이 `tos-gate` success 를 **위조 게시**할 수 있었다. 교정: check-run 검증에 **`app.id`(기본 `15368` = GitHub Actions·오늘 `main` 실측값)·`head_sha`·`check_suite` 귀속** 추가. **(b) 의 정확한 진술로 재저작**: 증명하는 것은 «그 리비전에서 서버가 게이트를 실행해 통과했다»이고, «머지 «시점»에 보호가 강제 중이었다»는 **공개 REST 로 사후 증명 불가**(감사 로그는 org/enterprise 소관)다. 잡는 것(체크 실패·부재 / 직접 push / 위조 success)을 열거하고 **남는 것 = «보호 off 상태에서 체크는 통과한 리비전 착지»** 를 **닫지 못함으로 명시**. **완화 2종**: (α) 룰셋 `created_at ≤ merged_at(min D)` 요구 + `updated_at > merged_at` 은 **차단이 아니라 관측 기록**(정당한 정책 개선까지 막는 과잉 차단 방지) (β) **예방 주체는 서버 자체**·`UNCHK-008` 잔존·**강제 «연속성» 증명은 감사 로그 확보 시 승격**. **«흔적 없음» 류 문장 전수 제거** ③ **B3 — S-22**: §8 `T-84` 행이 **에라타 E2 이후에도** `rulesets=[]`·«머지 커밋 check-runs 0»·«pulls 공집합»을 유지해 **같은 턴 실측과 충돌**했다(E2 가 #5 근거만 고치고 이 행을 안 봤다) → **행 전체 재작성** + **⑤ target 불일치**·**⑥ `app_id` 위조** 신설 ⇒ **T-84 4종 → 6종**. **상태 7값 → 8값 / 차단 7 / 전순서 8단.** **[v2.17 에라타 (동결 `a3c95b4f` 후 증거 실행 `6bad7c23` 적발 — 재결속 전 정정)]** ⓐ **E1 (S-22)** — §8 `T-84` ① 이 «작업 브랜치 → 404 → `PREVENTION_ABSENT`» 를 유지했으나, **v2.17 에서 `target_branch` 가 `default_branch` 로 «파생»되므로 그 구성은 ⑤(`TARGET_MISMATCH`)** 이고 **실행기로 재현되지 않는다**. **B1 의 파생 전환이 이 행에 미전파**된 것이며, ① 은 «선언 == 파생(`main`) → `INSUFFICIENT`» 로만 두고 404 는 **«raw probe 관측»으로 강등**했다 ⓑ **E2 (리터럴 고정 3건)** — 원격 URL **정규화 규칙**(https/ssh/scp 형식 → `<owner>/<repo>`·`.git` 제거·형식 밖 = 차단) · **`check_suite` «귀속 일치»의 구체**(check-run 의 `check_suite.id` 가 가리키는 suite 의 `head_sha` == PR `head.sha` — 산문으로 두면 구현마다 다르게 읽는다) · 아티팩트 키 이름 **`remote_name`**(기본 `origin`)·**`gate_app_id`**(기본 `15368`). **증거 실행 결과**: ⑤ **live `TARGET_MISMATCH`(`D=∅`)** · ⑥ `app.id` 위조 red · ① `main` `INSUFFICIENT` · ③ live — **전건 기대 일치**. **하니스 byte-identical·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
 | **v2.16** | **stop-time Codex 심판 BLOCK 2건 반영. 중심은 «U-17 의 진실 원천을 저장소에서 서버로 옮긴 것».** v2.15 는 **재결속 전이라 승인 표면을 가진 적이 없다**(v2.9→v2.10 선례). ① **BLOCK ① — S-22 미전파**: `U-17` 이 7c/8 결속을 **주장**했으나 **§12.3 실행 착수 절차 텍스트는 여전히 `U-15` 만 요구**하고 `prevention_control_state` 를 언급하지 않았다. 7c·8 텍스트에 **live `PREVENTION_ACTIVE`** 를 명시 소비로 추가하고 진입 조건을 **논리곱 셋**으로 확정 ② **BLOCK ② — 자기신고 검증**: `PREVENTION_ACTIVE` 가 **비인증 저장소 내 자기신고 + 커밋 조상성**만 봐 **실제·현재 브랜치 보호를 보지 않았고**, **양성 테스트가 모의 문자열을 스스로 쓰고 ACTIVE 를 냈다** ⇒ **거짓 주장·countersign 후 보호 해제가 green**. 교정: **진실 원천을 서버로** — 별도 실행기 **`u17-verify`** 가 **인증 API 로 live 조회**(`branches/{t}/protection` + 룰셋)하고 raw 응답을 transcript 에 verbatim 수록, 술어(**TOS 게이트 체크 ∈ contexts ∧ strict ∧ enforce_admins ∧ force-push/deletion 불허 ∧ PR 필수**)를 캡처된 응답 위에서 결정적으로 평가. **상태 4값 → 7값**(`PREVENTION_UNVERIFIABLE`·`PREVENTION_INSUFFICIENT`·`PREVENTION_UNVERIFIED_REVISION` 신설, 차단 6, 전순서 7단). **(b) 리비전 특정** — `∀d∈D` 에 대해 **check-run success + merged PR** 실조회. **«countersign 후 보호 해제»가 닫히는 논증**: (a) 를 **진입 시점과 완료 판정 시점 둘 다 live** 로 평가하고 (b) 가 **리비전마다 서버 실행 흔적**을 요구한다 — **어느 하나만으로는 닫히지 않는다**. 아티팩트·countersign 은 **진실 원천이 아니라 파라미터 선언 + 기록 순서**(owner/repo·대상 브랜치·체크 이름을 **선언**하고 **서버가 검증** — 하드코딩 금지)로 강등. **가드 체인 3단화**(`하니스 && u17-verify && D0A-FIRST`) — **하니스는 오프라인·결정적이어야 하고 byte-identical 회귀 기준선을 가지므로 네트워크를 넣지 않는다**(층 분리). **T-84 재저작**: **음성은 실측·양성은 seam** — 이 저장소 실조회로 `main` → **`PREVENTION_INSUFFICIENT`**(contexts `["test"]`·strict false), 작업 브랜치 → **`PREVENTION_ABSENT`**(404), rulesets `[]`. **인증된 진짜 음성 증거가 지금 존재한다.** 양성은 `responder` 주입 seam(기본 `gh api`·transcript 에 명시)으로 모의하되 **`SIMULATED` 표기**하고 **운영자가 보호를 설정하기 전엔 실측 불가**임을 정직 표기 — **seam 이 정당한 근거는 응답 파서와 판정 함수가 동일 코드 경로**라 주입이 **입력만** 바꾼다는 것이다. **[v2.16 마감 (검증 FAIL 반영 — live 실측은 계약대로였고 차단 3·medium 3)]** ⓐ **#1 (BLOCK ① 클래스 재발)** — §12.3.4-G 의 **G-음성·G-양성 가드가 여전히 2단**이라 **T-81 ⑫ 양성이 폐기된 형태를 탔다**. **3단으로 교정**하고 **`G-음성-2`(하니스 통과 + u17 차단)를 신설** — **현 실측(`INSUFFICIENT`/`ABSENT`)으로 «두 번째 억제 지점»을 live 로 실행할 수 있다** ⓑ **#2** — §8 `T-84` 행이 «4종» 선언 아래 **6항·③ 중복·v2.15 자기신고 기준 잔존**으로 (a) 정의와 **정면 충돌**했다 → 행 전체 재작성 ⓒ **#3 (자기신고 잔여)** — «transcript 에 responder 명시»는 **자기신고**이고 «파서·판정 동일 경로»는 **다른 명제**다. **구조로 닫는다**: 진입자의 `u17-verify` 는 **가드**일 뿐이고 **판정 소비자는 transcript 를 신뢰하지 않고 스스로 live 조회**한다 ⇒ **진실 원천 = 판정 소비자 자신의 조회**. **responder 위조는 진입자 transcript 만 오염**시킨다. 남는 것(**판정 소비자 자신의 환경 위조**·**예방 주체는 서버 자체**)은 **정직 경계 절**로 명시 ⓓ **#4** — 술어에 `required_pull_request_reviews` **부재 = 불충족** · `restrictions`/apps 우회 없음 · 룰셋 **필드 수준**(`enforcement=active`·`bypass_actors=[]`·`required_status_checks`·`pull_request`·`non_fast_forward`·`deletion`) 추가. **TOS 게이트 체크 기본 이름 `tos-gate`** 를 계약이 정하되 **파라미터 기본값**이고 **CI 잡 이름과 일치해야** 하며 **현재 CI 에 부재 → 오늘 `main` 이 `INSUFFICIENT` 인 것이 맞다** ⓔ **#5** — (b) 조회 SHA 를 **PR `head.sha`** 로 못박음(**squash/merge 착지에서 check-run 은 머지 커밋이 아니라 PR head 에 붙는다** — 실측: 머지 커밋 check-runs 0·pulls 공집합·미푸시 422). `d` 직접 조회는 **정직한 착지도 항상 red** 로 만든다 ⓕ **#6** — `T-84 ③` 의 타 축 값(`NOT_STARTED`) 제거하고 **`D = ∅` 처리**를 U-17 에 명시: (a) live 술어는 **`D` 와 무관**(착수 «전»에도 ACTIVE 가능해야 착수한다) · (b)(c) 는 «검증 대상 없음» — **공허참에 기대지 않는다**. **[v2.16 에라타 (동결 `eb2805a9` 후 증거 실행 `434448b2` 적발 — 재결속 전 정정)]** ⓐ **E1 문언 소실** — v2.15 에라타 E3 가 고정한 `operator_countersign: "<식별> <ISO-8601 UTC>"` **리터럴이 U-17 재작성에서 사라져** «형식 위반»이 **재-미정의**됐다 → `(c-0)` 로 복원 ⓑ **E2 사실 정정** — #5 근거의 «머지 커밋 check-runs 0건·pulls 공집합»은 **거짓**이었다(live 재측정: `11e382fc` check-runs **15건**·`pulls` = PR #636 merged 1건). **결론(조회 SHA = PR head.sha)은 유지하고 근거를 교체**한다: 그 15건은 **push 트리거 워크플로**이지 **PR 게이트가 아니며**, 게이트 결과는 **PR head SHA 에 귀속**된다(PR head `7656259d` check-runs 5건에 `tos-gate` 없음). `d` 직접 조회는 **게이트 아닌 실행을 게이트로 오인**하게 만든다 ⓒ **E3 fail-closed 리터럴 고정** — `allow_force_pushes`·`allow_deletions` **키 부재 = 불충족**(없는 것을 «허용 안 함»으로 읽지 않는다) · `restrictions` 실재 시 **`apps == []`**(users/teams 는 push 제한이라 우회 아님) · `rulesets/{id}` 의 **`bypass_actors` 키 부재도 불충족**(조회 못 한 것을 «없음»으로 읽지 않는다) ⓓ **성능 주** — 구조 `D`·`P` 판정은 `git rev-list --full-history` 로 **후보를 축소**해도 되며(2,149 커밋 ~36s → <1s), **완전성 근거**(술어 만족 `x` 는 모든 부모와 tree 가 달라 후보에 포함)와 함께 **«축소는 최적화·판정은 구조 평가»** 임을 명시했다. **증거 실행 결과**: G-음성-2 **live 성립** · T-84 live 음성(`main` INSUFFICIENT·브랜치 ABSENT) · seam 양성 · 3단 가드 ⑫ CLEAR. **하니스 byte-identical·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
 | **v2.15** | **v2.14 심판 판정 5건(high 3 / medium 2) 전건 반영. 직전 처분은 «#1·#2 부분해소 · #3 회피(아크 최초)» 다.** ① **F1 (high) — 정직 경계는 해소가 아니다**: §11 이 `ENTRY_PROVENANCE_CLEAR` 를 **완료 허용값으로 소비**하는데 예방은 `UNCHK-008`(`Phase 1`)이라 **보호 장치보다 먼저 실행되는 Phase 0 진입을 사후 세탁해 정상 완료로 표시**할 수 있었다 — **경계를 적는 것과 그 경계 때문에 완료가 막히게 하는 것은 다르다**. **`U-17` 신설** — `UNCHK-008` 의 «진입 표면 거부»를 **`Phase 1` 종료조건에서 «D0-A 착수 선행 조건»으로 승격**하고, 증거를 **커밋된 보호 아티팩트 + 운영자 countersign**(3상태·중립값 없음)으로 둔다. **구조 선택 근거**: 후보 (a)«하니스 R-단계에 `gh api` 실측»은 **네트워크 의존으로 하니스를 비결정적으로** 만들고(오프라인·토큰 만료·rate limit 이 각각 새 실패 축) **`§12.3.4-R` byte-identical 회귀 기준선을 깨며**, 무엇보다 **질문의 층이 다르다**(하니스 = «이 HEAD 에서 진입 가능한가» / 예방 = «그 이전에 인프라가 서 있는가») → **기각**. 채택 (b) 는 **위조가 커밋 이력에 노출되는 기존 경계와 같은 클래스**이고 `6e` 가 이미 쓰는 권위 형식이다 — **하니스는 byte-identical 로 남는다**. **결속 문서(개발계획)는 편집하지 않고** «Phase 1 종료조건의 그 항목이 D0-A 진입 시점으로 앞당겨진다»만 계약 측에 선언하며 **개발계획 개정은 별도 사이클·운영자 소관**으로 정직 표기. **CORR 은 검출 표면으로 잔존·«닫힌다» 주장 0 유지**. **부수 — 처분표 (B) 가 마감 전 초안 문구 그대로**였다(«두 미검사 축을 한 트레일러 조건으로 동시에 닫고»·«모든 원소가 진 조상(전칭)»·«실행 증거 없음») — 마감(G1 철회·∃ 전환)·증거 `c5359c74`·에라타 **어느 단계도 미전파**. **S-22 «7회차»** 이며 원인은 **sweep 대상에 «개정 처분표»가 없었던 것** → **S-22 에 처분표 (A)(B)·§0 요약·심사 이력·변경 이력을 명시 추가** ② **F2 (high, 신규) — 복수 D0A-FIRST**: `U-15-g-1` 이 «있으면 1건»으로 **카디널리티를 가정**해, 두 브랜치가 각각 파일을 추가하고 머지하면 `D` 크기 2 인데 **양화도 선택 규칙도 없어 guarded `d1` 과 unguarded `d2` 공존 시 임의 선택으로 `CLEAR`** 가 가능했다. **판정 우주를 집합 `D` 로** 바꾸고 **`MULTIPLE_INTRODUCTIONS`** 신설(전순서 **2**) → 상태 **7값 → 8값 / 차단 6**. **극성 논증**: «∀d 최악값»이 아니라 **즉시 차단**인 이유는 — `D0A-FIRST` 는 §12.1 이 «최초 행위»로 **명명**한 것이고 도입 커밋이 둘이면 **명명 자체가 무너진 상태**다. ∀d 최악값은 그 질문을 **답한 척**하고 둘 다 guarded 면 통과시킨다. **판정할 수 없는 상태를 판정하지 않는 것이 fail-closed**. **T-81 ⑲** ③ **F3 (high) — digest 선배치**: `C_R` 이 digest **토큰**의 도입만 추적해, `H0` 에 **digest 만 담은 빈 운반자**를 두고 `B` 에서 **실제 내용을 작성**하되 토큰을 유지하면 `B ∉ C_R`(부모에 토큰 존재)이고 `C_R={H0} ⊰ A` 라 **g6 이 통과**했다. **`U-16-h` 가 이미 `approved_at_head` 시점 blob 을 고정**하므로 **`C_R` 도 «그 blob 의 도입 지점»으로 맞춘다** — h 와 정합하고 선배치 변종에서 `C_R={B}`·`B ⋠ A` → red 이며 **독립 동일 blob 도입은 ∃ 양화자가 green 으로 유지**. **T-82 ⑲** ④ **F4 (medium) — «회피» 판정을 정면으로 인정한다**: 머지 후 도입된 재부여 행 `Z1`·`Z2` 는 **과거 간선 커밋의 조상이 될 수 없어** `U-16-c`·`APPROVAL_AFTER` 에 걸리고 **전체 계약에서 green 이 불가능**했는데, 손 실행 부속이 **tombstone-graph 만 실행하고 조상성을 뺀 채** 양성을 주장했다 — **부분 표면 실행기의 green**. **원인을 기록한다: 실행기가 상태값의 모든 소비 규칙을 실행하지 않았다.** 처분: **`supersedes` 폐기 + `edge_seq` 를 소비자 파생값으로**(원장 기재값은 **대조 대상** — `U-12` 의 `trigger_at_head` 와 같은 규율). **병렬 충돌이 «복구»를 필요로 하지 않게 된다** — 파생값이 애초에 결정적이므로 **append 자체가 불요**하고, `U-16-c` 조상성은 **원 승인 행에만** 걸려 **위반이 발생 자체를 하지 않는다**. **우회가 아니라 소거로 닫는다** ⑤ **F5 (medium, 신규) — `row_ref` 의 `c_APP` 비단수**: **F4 의 `supersedes` 폐기로 `row_ref`·tombstone-graph 가 함께 소멸**해 이 축이 **원인째 사라진다**. **한 결정이 두 건을 닫는다 — v2.14 가 만든 기제 자체가 원인이었다는 뜻이다** ⑥ **`S-23` 신설**: *실행기는 산출 상태값의 «전» 소비 규칙을 실행하거나, 미실행 규칙을 명시하고 green 을 주장하지 않는다.* **`S-15` 의 실행기 판** — 그쪽은 «측정 도구가 대상보다 느슨하면 증거가 아니다», 여기서는 «실행기가 계약보다 좁으면 green 이 증거가 아니다». **`T-82 ⑱` 은 `g1`~`g6`·`h`·`U-16-c` 를 전부 실행하는 실행기로만 양성 주장 가능**. **T-81 19종 · T-82 19종 · T-84 4종 신설.** **하니스 원문 불변**(§12.3.4-R 101행 byte-identical). **[v2.15 에라타 (동결 `11a56d3e` 후 증거 실행 `b453b4e5` 적발 — 재결속 전이므로 정정 후 재동결, v2.14 선례)]** ⓐ **E1 (우회 성립)** — `U-15-g-1` 의 `D` 를 리터럴 `git log --diff-filter=A` 로 둔 것이 **git «이력 단순화»** 때문에 **두 브랜치가 byte-동일 내용으로 추가 후 머지하면 도입 커밋을 1건만 반환**해 `D` 크기 1 → **`ENTRY_PROVENANCE_CLEAR` rc=0** 이 나왔다(`--full-history` 대조는 2건). **`F2` 의 극성 논증이 막으려던 «둘 다 guarded 면 통과»가 카디널리티 단계에서 재현**됐고, **`C_R` 이 이미 닫은 «플래그 의존» 클래스의 `D` 판 재발**이다 → **`D` 를 구조 정의로**(`C_R` 과 같은 형태 — 머지 도입 포함·플래그 무관). `--full-history` 리터럴 고정보다 **일관성** 때문에 이쪽을 택했다. **§8 ⑲ 에 gg 변형 명시**(⑲ 안의 하위 케이스이므로 **종수 불변**) ⓑ **E2 (정밀화)** — `T-82 ⑰ⓑ` 의 기대값을 **`APPROVAL_UNBOUND`** 로 정정: v2.15 blob 정의에서는 `approved_at_head=B` 시점 blob 에 digest 가 없어 **`h` 가 `g6` 보다 먼저 발화**한다(전 규칙 실행기 실측). 초안의 `C_R={M} → ORDER_INVALID` 는 **g6 단독 뷰의 값**이며 **극성은 동일** ⓒ **E3 (정밀화)** — `U-17-b` 의 countersign 을 **`operator_countersign: "<식별> <ISO-8601 UTC>"`** 로 **키·형식 고정**. v2.15 는 «6e 와 같은 권위 형식»이라고만 적어 **실행기가 키를 독해로 채택**했다 — **독해로 채운 키는 계약이 아니다**. 6e 의 `authority:` 를 재사용하지 않는 이유도 명시(의미가 다르다). **하니스 byte-identical·종수 불변(T-81 19·T-82 19·T-84 4).** **`bound_paths` 편집이므로 O-6 대로 재결속 필요.** **심사 미판정 — 동결 후 운영자 재결속(현행 사이클) 대기.** 구현 착수 금지 불변 |
@@ -5074,10 +5074,21 @@ v2.16 은 `owner_repo`·`target_branch` 를 **아티팩트 선언값 그대로**
 계약 핀      canonical_target = github.com/kakao-harris-lee/kis_unified_sts
              **아티팩트 파라미터가 아니다.**  변경하려면 이 문서를 고쳐야 하고
              그러면 O-6 재결속이 돈다 — 그것이 이 핀의 보호다
+             **[E2 — v2.18 에라타] 아티팩트의 `owner_repo`·`target_branch` 키는
+             «선택»이다.**  있으면 **핀·`default_branch` 와 대조**하고 불일치는
+             `PREVENTION_TARGET_MISMATCH`, 없으면 **핀과 API 파생이 유일 소스**다.
+             **극성**: 선택으로 두어도 **약해지지 않는다** — 두 경우 모두 «조회
+             대상»은 핀이고, 선언은 **추가 대조**일 뿐 대상을 «고를» 수 없다.
+             («선언하지 않는다»고만 적은 초안과 머리·§8 ⑤ 의 «선언 불일치 =
+              MISMATCH» 가 충돌해 보였던 것을 이 문장이 해소한다)
 정규화       **host 를 보존**한다: `<host>/<owner>/<repo>`  (v2.17 은 버렸다)
 git remote   **파생이 아니라 «대조»** — `git remote -v` 중 **계약 핀과 일치하는
              원격이 «존재»해야 한다**(원격 «이름»은 묻지 않는다).
              부재 = `PREVENTION_TARGET_MISMATCH`
+             **[E3 — v2.18 에라타] 비-핀 원격의 «공존»은 허용한다** — 원격
+             **이름도 개수도 묻지 않는다.**  **조회 대상은 «핀»이지 «원격»이
+             아니며**, 원격 대조는 «이 작업 트리가 핀 저장소의 클론인가»만
+             확인한다.  포크·미러를 추가로 두는 정상 작업을 막지 않는다
              ⇒ **`remote_name` 파라미터 폐지**
 target       계약 핀 repo 의 `gh api repos/{pin}` `.default_branch`
 ```
@@ -5234,9 +5245,20 @@ TOS 게이트 체크 이름  아티팩트가 **파라미터로 선언**하되 **
                     (**계약 리터럴**이며 아티팩트 파라미터가 아니다)
               ② 그 run 의 **`head_sha` == PR `head.sha`**
               ③ **그 `head_sha` 시점의 워크플로 파일 blob**  [R2 — v2.18 마감]
-                 `git show <head_sha>:.github/workflows/tos-gate.yml`
-                 · **실패(파일 부재·경로 없음) → `PREVENTION_UNVERIFIED_REVISION`**
+                 **[E1 — v2.18 에라타] blob 은 «서버»에서 읽는다.**
+                 ```
+                 gh api repos/{pin}/contents/.github/workflows/tos-gate.yml?ref=<PR head.sha>
+                 → base64 decode 후 아래 두 리터럴 grep
+                 ```
+                 · **404·기타 HTTP 오류 → `PREVENTION_UNVERIFIED_REVISION`**
                    (**검사 생략 금지** — 부재를 «해당 없음»으로 접지 않는다)
+                 · **네트워크·인증 오류 → `PREVENTION_UNVERIFIABLE`**
+                 **초안은 로컬 `git show <head_sha>:…` 를 전제했다.**
+                 squash·rebase 착지에서는 **판정 저장소가 PR head 커밋을 보유하지
+                 않아**(실측: `origin/main` 의 PR #636 head `7656259d` 로컬 미보유)
+                 **정직한 착지도 «항상 red»** 가 됐다.
+                 **진실 원천이 서버라는 U-17 원칙과도 이쪽이 정합**하며,
+                 로컬 `git show` 는 **보조 대조(선택)** 로만 둔다
                  · 성공 시 **파일 텍스트가 «두 리터럴»을 포함**해야 한다(grep 2회):
                    (i) **하니스 실행 리터럴** — 계약이 정하는 경로 리터럴
                        **`tools/tos_entry_harness.sh`**
```

절 범위 diff 기계 증명 (`s24-proof.sh` 출력 원문 · ∅ = 그 범위에서 두 blob 이 byte-동일 · ≠ = 에라타가 건드린 범위):

```text
=== S-24 절 범위 diff 기계 증명 (2026-08-18T19:12:25Z) — 동결 5f4b7cfd(6,976행) → 에라타 feb91d60(6,998행) ===
$ git diff 5f4b7cfd..feb91d60 --stat -- <계약>
   ...-08-12-tos-phase0-completion-contract-design.md | 28 +++++++++++++++++++---
   1 file changed, 25 insertions(+), 3 deletions(-)
$ git diff 5f4b7cfd..feb91d60 -- <계약> | grep '^@@'   (hunk 3개 — 이것이 변경의 전부)
  @@ -190,7 +190,7 @@
  @@ -5074,10 +5074,21 @@ v2.16 은 `owner_repo`·`target_branch` 를 **아티팩트 선언값 그대로**
  @@ -5234,9 +5245,20 @@ TOS 게이트 체크 이름  아티팩트가 **파라미터로 선언**하되 **
-- hunk 사상: H1 old 193 (변경 이력 v2.18 행 — 에라타 서술 추가) · H2 old 5077 앞 삽입 +7 (E2) 및 old 5083 앞 삽입 +4 (E3) · H3 old 5237-5239 → new 5248-5261 (E1: R2 ③ 서버 조회) --
  ∅  머리~변경 이력 직전 (1-192) : old 1,192p == new 1,192p
  ≠  변경 이력 v2.18 행 (193) — 에라타가 건드린 행 (≠ 기대) : old 193p vs new 193p
  ∅  194 ~ U-17 핀 블록 직전 (194-5076)  [S-24·§8 T-84 행 :2868·§12.3.4-R 하니스 블록 4528-4628 포함] : old 194,5076p == new 194,5076p
  ∅  §12.3.4-R 하니스 블록 (4528-4628) : old 4528,4628p == new 4528,4628p
  ∅  §8 T-84 행 (2868) : old 2868p == new 2868p
  ∅  핀 블록 앞부분 (5074-5076) : old 5074,5076p == new 5074,5076p
  ∅  정규화·git remote 대조 4행 (5077-5080 → 5084-5087 shift +7)  [E3 는 old 5081 앞에 +4 삽입] : old 5077,5080p == new 5084,5087p
  ∅  핀 블록 말미(remote_name 폐지·target)~(a) 술어~진실 원천~정직 경계~(b) 머리~R2 ①② (5081-5236 → 5092-5247 shift +11) : old 5081,5236p == new 5092,5247p
  ∅    그중 (a) 술어 블록 (5109-5157 → 5120-5168) : old 5109,5157p == new 5120,5168p
  ≠  R2 ③ 서버 조회 전환부 (5237-5239 → 5248-5261) — 에라타가 건드린 범위 (≠ 기대) : old 5237,5239p vs new 5248,5261p
  ∅  R2 ③ 두 리터럴~#5~D=∅~B2 철회~완화 (α)(β)~(c-0)~(c) P_first/P_last~U-17-c 9값/전순서~U-17-d~(d) 3단 가드~이후 EOF (5240-6976 → 5262-6998 shift +22) : old 5240,6976p == new 5262,6998p
  ∅    그중 (c) P_first/P_last·U-17-c 상태표·전순서 (5329-5387 → 5351-5409) : old 5329,5387p == new 5351,5409p
-- 하니스 블록 sha256: 5f4b7cfd=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d feb91d60=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
-- 워킹트리 == feb91d60: yes · HEAD=feb91d60782a5441e4f00e0123779d0366b89c1a · blob(HEAD)=aa7839b1ca1da440b704ff6bf658b5cf27ce517d blob(feb91d60)=aa7839b1ca1da440b704ff6bf658b5cf27ce517d · sha256(워킹트리)=2a7926831b8c6ababeb747d370bc8f9d1fff10678507b81a6196f65d6d793db5
-- feb91d60..HEAD 계약 커밋: 0건
```

## 2. 실행기 `u17-verify-v218e.sh` — 원문 (sha256 `6b196756890f580058c38c4b8e1f44e39c95c1b4137a33377af2602ad414a15c`)

독해 선언(v2.18 본 실행기 대비 델타만):
- **E1 (R2 ③)**: `repos/{pin}/contents/.github/workflows/tos-gate.yml?ref=<PR head.sha>` 를 responder 경유로 조회(캡처 `U17-B5` verbatim + UTC) → `encoding=="base64"` 이면 `content` 를 decode → 두 리터럴
  `grep -F` 계수. `2xx` 아님(404 등) → `UNVERIFIED_REVISION`(검사 생략 금지) · 캡처 `ERR`(네트워크/인증/주입 없음) → `UNVERIFIABLE`. 로컬 `git show <head>:…` 는 **보조·선택** — `U17-B5x` 로 기록만 하고 판정에
  소비하지 않는다(로컬에 head 커밋이 없어도 판정 성립).
- **E2**: 아티팩트 `owner_repo`/`target_branch` 키는 선택 — 있으면 핀/`default_branch` 와 대조(불일치 = `TARGET_MISMATCH`), 없으면 대조 미발화·`U17-T` 에 «∅(선택 키 부재 → 핀 유일 소스)» 기록.
- **E3**: 원격 «존재» 대조는 그대로(비-핀 원격 공존 허용 — v2.18 본 증거 ⑩-c 그대로).

```bash
#!/usr/bin/env bash
# u17-verify (v2.18 에라타 feb91d60) — U-17 «예방 통제 활성 증거» 실행기 (계약 feb91d60 §12.3.4 U-17: C3 계약 핀·C1 checks[].app_id·C2 app id 서버 파생+워크플로 정체성 3중·**E1 R2 ③ 워크플로 blob 서버 조회**·E2 선언 키 선택·E3 원격 공존·C4/R1 P_first/P_last·U-17-c 9값/전순서 9단)
#   §12.3.4-R 하니스와 «별도». run 은 stdout 의 `U17-0 target=<owner>/<repo>@<branch>` 라인이 연다. CORR 은 이 run 을 보지 않는다.
#
#   [C3] 계약 핀 canonical_target = github.com/kakao-harris-lee/kis_unified_sts (계약 리터럴 · 아티팩트 파라미터 아님).
#        git remote 는 «대조»: `git remote -v` 의 URL 을 host 보존 정규화(<host>/<owner>/<repo>)해 핀과 일치하는 원격이 «존재» 해야 한다(이름 무관). 부재 = TARGET_MISMATCH.
#        target = 핀 repo 의 `gh api repos/{pin}` .default_branch.  아티팩트 선언값(owner_repo·target_branch)은 «대조 대상» — 핀/파생과 불일치 = TARGET_MISMATCH.
#   [C2] Actions app id 는 서버 파생: `gh api apps/github-actions` .id (gate_app_id 파라미터 폐지 — 아티팩트에 있어도 무시·기록).
#   (a) 술어 = v2.17 + [C1] required_status_checks.checks[] 의 <check> 컨텍스트 app_id == Actions app id (룰셋: required_status_checks[].integration_id == app id).
#   (b) ∀d∈D: pulls → merged ∧ base==target 인 PR head.sha → check-runs 에 name==check ∧ conclusion==success ∧ app.id==Actions ∧ head_sha==PR head 인 run;
#       check-suites/{run.check_suite.id}.head_sha == PR head [E2]; 워크플로 정체성 3중 [C2]: actions/runs?check_suite_id=<id> 의 run 중 head_sha==PR head 이고 path==.github/workflows/tos-gate.yml (계약 리터럴);
#       [R2·E1] `repos/{pin}/contents/.github/workflows/tos-gate.yml?ref=<PR head>` (서버 조회 · responder 경유) → base64 decode → 두 리터럴 `tools/tos_entry_harness.sh` · `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d` grep.
#       404·기타 HTTP → UNVERIFIED_REVISION(검사 생략 금지) · 네트워크/인증(ERR) → UNVERIFIABLE. 로컬 `git show <head>:…` 는 보조 대조(선택·판정 미소비·U17-B5x 라인으로 기록만).
#   (c) [C4/R1] P_first(최초 도입)·P_last(마지막 변경) 구조 파생(--full-history 후보 위): LATE = ∃d P_first⋠d · ARTIFACT_MUTATED = ∀d P_first⊰d ∧ ∃d P_last⋠d · ACTIVE 는 ∀d P_last⊰d ∧ HEAD blob == blob(P_last).
#   (c-0) countersign E3 리터럴.  (α) 룰셋 created_at/updated_at 관측(차단 아님).
#   전순서: 1 UNVERIFIABLE > 2 ABSENT > 3 UNSIGNED > 4 TARGET_MISMATCH > 5 INSUFFICIENT > 6 LATE > 7 ARTIFACT_MUTATED > 8 UNVERIFIED_REVISION > 9 ACTIVE.
#   ** 전 단계를 먼저 «수집»하고 마지막에 전순서 최소 순위를 방출한다 ** — (b) 의 조회 실패(1)가 (c) 의 LATE(6) 보다 먼저 성립하도록. exit 0 = ACTIVE 만. trap EXIT 폐쇄.
# 사용: bash u17-verify-v218.sh [<repo-dir>]      (env: U17_RESPONDER=gh|file:<dir>|mixed:<dir> · U17_CAPTURE_DIR)
set -u -o pipefail
CANON=github.com/kakao-harris-lee/kis_unified_sts     # 계약 핀 (C3)
WF_PATH=.github/workflows/tos-gate.yml                # 계약 리터럴 (C2)
LIT1=tools/tos_entry_harness.sh                       # 계약 리터럴 (R2-i)
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d   # 계약 리터럴 (R2-ii) — §12.3.4-R 블록 sha256
EMITTED=0
emit() { EMITTED=1; printf 'prevention_control_state=%s\nreason=%s\n' "$1" "$2"; [ "$1" = PREVENTION_ACTIVE ] && exit 0; exit 1; }
trap '[ "$EMITTED" -eq 1 ] || { printf "prevention_control_state=%s\nreason=%s\n" PREVENTION_UNVERIFIABLE "판정 미산출 상태로 종료(fail-closed)"; exit 1; }' EXIT
cd "${1:-.}" || emit PREVENTION_UNVERIFIABLE "repo 진입 실패"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
CFG=config/tos_completion.yaml
RESP="${U17_RESPONDER:-gh}"
CAP="${U17_CAPTURE_DIR:-$(mktemp -d)}"; mkdir -p "$CAP"
utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }
key() { printf '%s' "$1" | tr '/?=&' '____'; }
# 상태 수집기: RANK[상태]=순위 · 발화한 상태와 사유를 모았다가 최소 순위 방출
rank() { case "$1" in PREVENTION_UNVERIFIABLE) echo 1;; PREVENTION_ABSENT) echo 2;; PREVENTION_UNSIGNED) echo 3;; PREVENTION_TARGET_MISMATCH) echo 4;; PREVENTION_INSUFFICIENT) echo 5;; PREVENTION_LATE) echo 6;; PREVENTION_ARTIFACT_MUTATED) echo 7;; PREVENTION_UNVERIFIED_REVISION) echo 8;; *) echo 99;; esac; }
FIRED=""; NF=0; fire() { NF=$((NF+1)); FIRED="$FIRED$1|$2"$'\n'; printf 'U17-fire %s: %s\n' "$1" "$2"; }
finish() { local best="" bestr=99 f s r; while IFS= read -r f; do [ -n "$f" ] || continue; s=${f%%|*}; r=$(rank "$s"); if [ "$r" -lt "$bestr" ]; then bestr=$r; best="$f"; fi; done <<< "$FIRED"
  if [ -n "$best" ]; then emit "${best%%|*}" "${best#*|} [수집 ${NF}건 중 전순서 최소]"; fi; emit PREVENTION_ACTIVE "$1"; }

# ── responder seam
respond() {
  local path="$1" k; k=$(key "$1"); local st="$CAP/$k.status" bd="$CAP/$k.body"
  case "$RESP" in
    gh)  local out; out=$(gh api -i "$path" 2>"$CAP/$k.err"); printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"
         printf '%s\n' "$out" | awk 'f{print} /^\r?$/{f=1}' | tr -d '\r' > "$bd"
         if ! grep -Eq '^[0-9]{3}$' "$st"; then printf 'ERR\n' > "$st"; cat "$CAP/$k.err" > "$bd" 2>/dev/null; return 1; fi; return 0 ;;
    file:*) local dir="${RESP#file:}"
         if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'ERR\n' > "$st"; printf 'SIMULATED responder: no injected response for %s\n' "$path" > "$bd"; return 1; fi ;;
    mixed:*) local dir="${RESP#mixed:}"
         if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; printf 'U17-seam %s ← file(SIMULATED)\n' "$path"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'U17-seam %s ← gh(live)\n' "$path"; local save="$RESP"; RESP=gh; respond "$path"; local r=$?; RESP="$save"; return $r; fi ;;
    *) emit PREVENTION_UNVERIFIABLE "알 수 없는 responder: $RESP" ;;
  esac
}
show_capture() { local k; k=$(key "$2"); printf 'U17-%s %s  utc=%s  http=%s\n' "$1" "$2" "$(utc)" "$(cat "$CAP/$k.status")"; sed 's/^/  | /' "$CAP/$k.body"; }
jget() { python3 -c 'import json,sys
try:
    j=json.load(open(sys.argv[1]))
    for kk in sys.argv[2].split("."):
        j=j[int(kk)] if isinstance(j,list) else j[kk]
    print(j if not isinstance(j,(dict,list)) else json.dumps(j))
except Exception: print("")' "$CAP/$(key "$1").body" "$2" 2>/dev/null; }
http_of() { cat "$CAP/$(key "$1").status" 2>/dev/null; }
ok2xx() { printf '%s' "$1" | grep -Eq '^2'; }

# ── [C3] 핀·원격 대조 (host 보존 정규화)
PIN_OR=${CANON#*/}
norm_url() { printf '%s' "$1" | sed -E 's#^https?://([^/]+)/(.+)$#\1/\2#; s#^ssh://git@([^/]+)/(.+)$#\1/\2#; s#^git@([^:]+):(.+)$#\1/\2#; s#\.git$##; s#/$##'; }
REMOTES=$(git remote -v 2>/dev/null | awk '{print $1" "$2}' | sort -u)
MATCH_REMOTE=""; NORMED=""
while read -r rn ru; do [ -n "${ru:-}" ] || continue; n=$(norm_url "$ru"); NORMED="$NORMED $rn=$n"; [ "$n" = "$CANON" ] && MATCH_REMOTE="$rn"; done <<< "$REMOTES"

# ── [C2] Actions app id 서버 파생 · [C3] target = 핀 repo default_branch  (A00·A0)
respond "apps/github-actions"; ST_APP=$(http_of "apps/github-actions"); APPID=$(jget "apps/github-actions" id)
respond "repos/$PIN_OR";       ST0=$(http_of "repos/$PIN_OR");          TARGET=$(jget "repos/$PIN_OR" default_branch)
printf 'U17-0 target=%s@%s\n' "$PIN_OR" "${TARGET:-UNRESOLVED}"
printf 'U17-0 pin=%s remotes:%s match=%s | actions_app_id=%s (apps/github-actions http=%s) | responder=%s capture_dir=%s\n' "$CANON" "${NORMED:- (none)}" "${MATCH_REMOTE:-∅}" "${APPID:-∅}" "$ST_APP" "$RESP" "$CAP"
show_capture A00 "apps/github-actions"; printf 'U17-A0 repos/%s  utc=%s  http=%s  (.default_branch=%s)\n' "$PIN_OR" "$(utc)" "$ST0" "${TARGET:-∅}"
{ ok2xx "$ST_APP" && [ -n "$APPID" ]; } || fire PREVENTION_UNVERIFIABLE "apps/github-actions 조회 실패(http=$ST_APP) — Actions app id 파생 불가"
{ ok2xx "$ST0" && [ -n "$TARGET" ]; }   || fire PREVENTION_UNVERIFIABLE "repos/$PIN_OR 조회 실패(http=$ST0) — default_branch 파생 불가"
[ -n "$MATCH_REMOTE" ] || fire PREVENTION_TARGET_MISMATCH "계약 핀 $CANON 과 일치하는 원격 부재 (git remote -v 정규화:${NORMED:- none})"

# ── 아티팩트 (전순서 2 ABSENT · 대조값·countersign)  — 커밋-전용 읽기
BODY=$(git show "HEAD:$PC" 2>/dev/null) || { fire PREVENTION_ABSENT "아티팩트 HEAD 부재: $PC"; BODY=""; }
yv() { printf '%s\n' "$BODY" | sed -n "s/^$1:[[:space:]]*//p" | sed 's/[[:space:]]*#.*$//; s/[[:space:]]*$//' | head -1; }
DECL_OR=$(yv owner_repo); DECL_TB=$(yv target_branch); CHECK=$(yv tos_gate_check); [ -n "$CHECK" ] || CHECK=tos-gate
[ -z "$(yv gate_app_id)" ] || printf 'U17-note 아티팩트에 gate_app_id 키가 있으나 v2.18 은 폐지(무시) — 서버 파생값 %s 사용\n' "$APPID"
[ -z "$(yv remote_name)" ]  || printf 'U17-note 아티팩트에 remote_name 키가 있으나 v2.18 은 폐지(무시) — 핀 대조는 원격 이름을 묻지 않는다\n'
if [ -n "$BODY" ]; then
  MM=""   # [E2] 선언 키는 «선택» — 있으면 대조, 없으면 핀·API 파생이 유일 소스
  if [ -n "$DECL_OR" ]; then case "$DECL_OR" in "$CANON"|"$PIN_OR") ;; *) MM="$MM owner_repo(선언=$DECL_OR ≠ 핀=$CANON)";; esac; fi
  if [ -n "$DECL_TB" ] && [ -n "$TARGET" ] && [ "$DECL_TB" != "$TARGET" ]; then MM="$MM target_branch(선언=$DECL_TB ≠ 핀 repo default=$TARGET)"; fi
  printf 'U17-T declared-vs-pin: %s (declared owner_repo=%s target_branch=%s)\n' "${MM:-일치/선언 없음}" "${DECL_OR:-∅(선택 키 부재 → 핀 유일 소스)}" "${DECL_TB:-∅(선택 키 부재 → default_branch 유일 소스)}"
  [ -z "$MM" ] || fire PREVENTION_TARGET_MISMATCH "아티팩트 선언값이 계약 핀/파생값과 불일치:$MM"
  CS_RE='^operator_countersign:[[:space:]]*"[^"[:space:]][^"]* [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"[[:space:]]*(#.*)?$'
  nk=$(printf '%s\n' "$BODY" | grep -c '^operator_countersign:')
  if [ "$nk" != 1 ]; then fire PREVENTION_UNSIGNED "operator_countersign 키 출현 횟수=$nk (정확히 1 요구)"
  elif ! printf '%s\n' "$BODY" | grep -Eq "$CS_RE"; then fire PREVENTION_UNSIGNED "operator_countersign 값 형식 위반: $(printf '%s\n' "$BODY" | grep '^operator_countersign:')"; fi
fi

# ── (a) 4 엔드포인트 (핀 repo · 파생 target)
if [ -n "$TARGET" ]; then
P_PROT="repos/$PIN_OR/branches/$TARGET/protection"; P_RULES="repos/$PIN_OR/rules/branches/$TARGET"; P_RSETS="repos/$PIN_OR/rulesets"
respond "$P_PROT";  show_capture A1 "$P_PROT"
respond "$P_RULES"; show_capture A2 "$P_RULES"
respond "$P_RSETS"; show_capture A3 "$P_RSETS"
RSIDS=$(python3 -c 'import json,sys
ids=set()
for f in sys.argv[1:]:
    try:
        a=json.load(open(f))
        for r in a if isinstance(a,list) else []:
            if isinstance(r,dict):
                if r.get("ruleset_id") is not None: ids.add(str(r["ruleset_id"]))
                elif r.get("id") is not None and "enforcement" in r: ids.add(str(r["id"]))
    except Exception: pass
print(" ".join(sorted(ids)))' "$CAP/$(key "$P_RULES").body" "$CAP/$(key "$P_RSETS").body" 2>/dev/null)
for id in $RSIDS; do respond "repos/$PIN_OR/rulesets/$id"; show_capture A4 "repos/$PIN_OR/rulesets/$id"; printf 'U17-α ruleset %s created_at=%s updated_at=%s enforcement=%s (관측 기록)\n' "$id" "$(jget "repos/$PIN_OR/rulesets/$id" created_at)" "$(jget "repos/$PIN_OR/rulesets/$id" updated_at)" "$(jget "repos/$PIN_OR/rulesets/$id" enforcement)"; done
[ -n "$RSIDS" ] || printf 'U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)\n'
A_STATE=$(python3 - "$CAP" "$PIN_OR" "$TARGET" "$CHECK" "${APPID:-}" <<'PY'
import json,sys,os
cap,orepo,target,check,appid=sys.argv[1:6]
def key(p): return p.replace('/','_').replace('?','_').replace('=','_').replace('&','_')
def load(p):
    try:
        st=open(os.path.join(cap,key(p)+'.status')).read().strip(); body=open(os.path.join(cap,key(p)+'.body')).read()
    except Exception: return "ERR",None
    try: js=json.loads(body) if body.strip() else None
    except Exception: js=None
    return st,js
def unverifiable(st): return st=="ERR" or (st.isdigit() and st!="404" and not st.startswith("2"))
st_p,prot=load(f"repos/{orepo}/branches/{target}/protection"); st_r,rules=load(f"repos/{orepo}/rules/branches/{target}"); st_s,rsets=load(f"repos/{orepo}/rulesets")
if unverifiable(st_p) or unverifiable(st_r) or unverifiable(st_s):
    print("PREVENTION_UNVERIFIABLE|http/network/auth: protection=%s rules=%s rulesets=%s"%(st_p,st_r,st_s)); sys.exit(0)
why=[]; prot_ok=False
if st_p.startswith("2") and isinstance(prot,dict):
    rsc=prot.get("required_status_checks") or {}
    ctx=rsc.get("contexts") or [c.get("context") for c in (rsc.get("checks") or [])]
    if check not in (ctx or []): why.append(f"contexts∌{check}")
    else:
        # [C1] checks[] 의 그 컨텍스트 app_id == Actions app id (이름은 정체성이 아니다)
        cks=[c for c in (rsc.get("checks") or []) if c.get("context")==check]
        if not cks: why.append(f"checks[] 에 {check} 항목 부재(app_id 확인 불가)")
        elif not any(str(c.get("app_id"))==str(appid) for c in cks): why.append(f"checks[{check}].app_id={[c.get('app_id') for c in cks]}≠Actions {appid}")
    if rsc.get("strict") is not True: why.append("strict≠true")
    if (prot.get("enforce_admins") or {}).get("enabled") is not True: why.append("enforce_admins≠true")
    if (prot.get("allow_force_pushes") or {}).get("enabled") is not False: why.append("allow_force_pushes.enabled≠false(부재 포함)")
    if (prot.get("allow_deletions") or {}).get("enabled") is not False: why.append("allow_deletions.enabled≠false(부재 포함)")
    if "required_pull_request_reviews" not in prot: why.append("required_pull_request_reviews 키 부재")
    restr=prot.get("restrictions")
    if isinstance(restr,dict) and (restr.get("apps") or []): why.append("restrictions.apps≠[]")
    prot_ok = not why
elif st_p=="404": why.append("protection 404")
rs_ok=False; rs_why=[]; applied=rules if isinstance(rules,list) else []
if applied:
    types={r.get("type") for r in applied}; ids={r.get("ruleset_id") for r in applied}
    def rsc_ok():
        for r in applied:
            if r.get("type")=="required_status_checks":
                p=r.get("parameters") or {}
                if p.get("strict_required_status_checks_policy") is True and any(c.get("context")==check and str(c.get("integration_id"))==str(appid) for c in p.get("required_status_checks") or []): return True
        return False
    if not rsc_ok(): rs_why.append(f"required_status_checks{{strict,context∋{check},integration_id=={appid}}} 없음")
    for t in ("pull_request","non_fast_forward","deletion"):
        if t not in types: rs_why.append(f"rule {t} 없음")
    for i in ids:
        st_i,rs=load(f"repos/{orepo}/rulesets/{i}")
        if unverifiable(st_i): print("PREVENTION_UNVERIFIABLE|rulesets/%s http=%s"%(i,st_i)); sys.exit(0)
        if not isinstance(rs,dict): rs_why.append(f"rulesets/{i} 본문 없음"); continue
        if rs.get("enforcement")!="active": rs_why.append(f"rulesets/{i}.enforcement={rs.get('enforcement')}")
        if "bypass_actors" not in rs: rs_why.append(f"rulesets/{i}.bypass_actors 키 부재(불충족)")
        elif rs.get("bypass_actors")!=[]: rs_why.append(f"rulesets/{i}.bypass_actors≠[]")
    rs_ok = not rs_why
else: rs_why.append("적용 규칙 0")
if prot_ok or rs_ok: print("PREVENTION_ACTIVE|(a) 술어 충족: classic=%s ruleset=%s"%(prot_ok,rs_ok)); sys.exit(0)
if st_p=="404" and not applied: print("PREVENTION_ABSENT|protection 404 ∧ 적용 규칙 0 (룰셋 목록=%s)"%(len(rsets) if isinstance(rsets,list) else "n/a")); sys.exit(0)
print("PREVENTION_INSUFFICIENT|classic:[%s] ruleset:[%s]"%("; ".join(why),"; ".join(rs_why)))
PY
)
[ -n "$A_STATE" ] || A_STATE="PREVENTION_UNVERIFIABLE|(a) 캡처 평가 함수가 값을 내지 못함(파서 오류)"
A_VAL=${A_STATE%%|*}; A_WHY=${A_STATE#*|}
printf 'u17_live_state=%s\nu17_live_reason=%s\n' "$A_VAL" "$A_WHY"
[ "$A_VAL" = PREVENTION_ACTIVE ] || fire "$A_VAL" "(a) $A_WHY"
fi

# ── (c) P_first / P_last · D  (구조 정의 · 후보 = --full-history)
intro_set() { local path="$1" out="" x p intro; for x in $(git rev-list --full-history HEAD -- "$path"); do git cat-file -e "$x:$path" 2>/dev/null || continue; intro=1; for p in $(git log --format=%P -1 "$x"); do git cat-file -e "$p:$path" 2>/dev/null && { intro=0; break; }; done; [ "$intro" = 1 ] && out="$out $x"; done; printf '%s' "$out"; }
last_change() { local path="$1" x p b bp changed; for x in $(git rev-list --full-history HEAD -- "$path"); do git cat-file -e "$x:$path" 2>/dev/null || continue; b=$(git rev-parse "$x:$path"); changed=0; ps=$(git log --format=%P -1 "$x"); [ -n "$ps" ] || changed=1; for p in $ps; do bp=$(git rev-parse -q --verify "$p:$path" 2>/dev/null || echo ABSENT); [ "$bp" != "$b" ] && changed=1; done; [ "$changed" = 1 ] && { printf '%s' "$x"; return; }; done; }
if [ -n "$BODY" ]; then P_FIRST=$(intro_set "$PC" | awk '{print $NF}'); P_LAST=$(last_change "$PC"); else P_FIRST=""; P_LAST=""; fi
D=$(intro_set "$CFG"); ND=$(printf '%s\n' $D | grep -c .)
printf 'P_first=%s P_last=%s |D|=%s D=%s\n' "${P_FIRST:-∅}" "${P_LAST:-∅}" "$ND" "$(printf '%s ' $D)"
if [ -n "$BODY" ] && [ "$ND" -gt 0 ]; then
  LATE=0; MUT=0
  for d in $D; do { git merge-base --is-ancestor "$P_FIRST" "$d" && [ "$P_FIRST" != "$d" ]; } || LATE=1; done
  if [ "$LATE" = 1 ]; then fire PREVENTION_LATE "∃d∈D: P_first=$P_FIRST ⋠ d — 기록이 착수보다 늦다"
  else for d in $D; do { git merge-base --is-ancestor "$P_LAST" "$d" && [ "$P_LAST" != "$d" ]; } || MUT=1; done
       [ "$MUT" = 0 ] || fire PREVENTION_ARTIFACT_MUTATED "∀d P_first⊰d 이나 ∃d∈D: P_last=$P_LAST ⋠ d — 착수 «후» 아티팩트 변경"; fi
  [ "$(git rev-parse HEAD:$PC)" = "$(git rev-parse "$P_LAST:$PC")" ] || fire PREVENTION_ARTIFACT_MUTATED "소비 blob(HEAD) ≠ P_last 시점 blob"
fi

# ── (b) 리비전 특정 ∀d∈D (전순서 8) — D=∅ 는 «검증 대상 없음»(명시)
if [ "$ND" -eq 0 ]; then
  printf 'U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)\n'
elif [ -n "$TARGET" ]; then
  MINMERGED=""
  for d in $D; do
    respond "repos/$PIN_OR/commits/$d/pulls"; show_capture B1 "repos/$PIN_OR/commits/$d/pulls"
    HS=$(python3 - "$CAP" "$PIN_OR" "$d" "$TARGET" <<'PY'
import json,sys,os
cap,orepo,d,target=sys.argv[1:5]; k=f"repos/{orepo}/commits/{d}/pulls".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: prs=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|pulls 본문 파싱 실패"); sys.exit(0)
ok=[p for p in prs if isinstance(p,dict) and p.get("merged_at") and (p.get("base") or {}).get("ref")==target]
if not ok: print("UNVERIFIED_REVISION|착지 PR 부재·merged 아님·base≠target (pulls=%d)"%len(prs)); sys.exit(0)
print("HEAD|%s|%s"%(ok[0]["head"]["sha"],ok[0]["merged_at"]))
PY
)
    case "$HS" in UNVERIFIABLE\|*) fire PREVENTION_UNVERIFIABLE "(b) d=$d ${HS#*|}"; continue ;; UNVERIFIED_REVISION\|*) fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d ${HS#*|}"; continue ;; esac
    HSHA=$(printf '%s' "$HS" | cut -d'|' -f2); MERGED=$(printf '%s' "$HS" | cut -d'|' -f3); { [ -z "$MINMERGED" ] || [[ "$MERGED" < "$MINMERGED" ]]; } && MINMERGED="$MERGED"
    respond "repos/$PIN_OR/commits/$HSHA/check-runs"; show_capture B2 "repos/$PIN_OR/commits/$HSHA/check-runs"
    CANDS=$(python3 - "$CAP" "$PIN_OR" "$HSHA" "$CHECK" "$APPID" <<'PY'
import json,sys,os
cap,orepo,sha,check,appid=sys.argv[1:6]; k=f"repos/{orepo}/commits/{sha}/check-runs".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: js=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|check-runs 본문 파싱 실패"); sys.exit(0)
runs=js.get("check_runs") or []
named=[r for r in runs if r.get("name")==check and r.get("conclusion")=="success"]
good=[r for r in named if str((r.get("app") or {}).get("id"))==str(appid) and r.get("head_sha")==sha]
why=[]
if not named: why.append("name==%s ∧ conclusion==success 인 run 부재"%check)
else:
    for r in named:
        if str((r.get("app") or {}).get("id"))!=str(appid): why.append("app.id=%s≠Actions %s(위조 표면)"%((r.get("app") or {}).get("id"),appid))
        if r.get("head_sha")!=sha: why.append("head_sha=%s≠PR head"%r.get("head_sha"))
if not good: print("UNVERIFIED_REVISION|%s (check_runs=%d)"%("; ".join(why),len(runs))); sys.exit(0)
print("CAND|"+" ".join(str((r.get("check_suite") or {}).get("id")) for r in good))
PY
)
    case "$CANDS" in UNVERIFIABLE\|*) fire PREVENTION_UNVERIFIABLE "(b) head=$HSHA ${CANDS#*|}"; continue ;; UNVERIFIED_REVISION\|*) fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA ${CANDS#*|}"; continue ;; esac
    IDENT_OK=0; IDENT_WHY=""
    for sid in ${CANDS#CAND|}; do
      [ "$sid" != None ] || { IDENT_WHY="$IDENT_WHY check_suite.id 부재;"; continue; }
      respond "repos/$PIN_OR/check-suites/$sid"; show_capture B3 "repos/$PIN_OR/check-suites/$sid"
      SST=$(http_of "repos/$PIN_OR/check-suites/$sid"); ok2xx "$SST" || { fire PREVENTION_UNVERIFIABLE "(b) check-suites/$sid http=$SST"; continue; }
      [ "$(jget "repos/$PIN_OR/check-suites/$sid" head_sha)" = "$HSHA" ] || { IDENT_WHY="$IDENT_WHY suite $sid head_sha≠PR head;"; continue; }
      # [C2-①②] 워크플로 run: actions/runs?check_suite_id=<sid> → head_sha==PR head ∧ path==WF_PATH
      Q="repos/$PIN_OR/actions/runs?check_suite_id=$sid"; respond "$Q"; show_capture B4 "$Q"
      QST=$(http_of "$Q"); ok2xx "$QST" || { fire PREVENTION_UNVERIFIABLE "(b) $Q http=$QST"; continue; }
      WFOK=$(python3 - "$CAP/$(key "$Q").body" "$HSHA" "$WF_PATH" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); sha,wf=sys.argv[2],sys.argv[3]
runs=j.get("workflow_runs") or []
hit=[r for r in runs if r.get("head_sha")==sha and r.get("path")==wf]
print("OK" if hit else "NO|paths=%s"%[(r.get("path"),r.get("head_sha","")[:7]) for r in runs])
PY
)
      [ "$WFOK" = OK ] || { IDENT_WHY="$IDENT_WHY workflow run path≠$WF_PATH ∨ head_sha≠PR head (${WFOK#NO|});"; continue; }
      IDENT_OK=1; break
    done
    [ "$IDENT_OK" = 1 ] || { fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA 워크플로 정체성 불충족:${IDENT_WHY:- 후보 없음}"; continue; }
    # [R2-③·E1] 그 head_sha 시점의 워크플로 blob — «서버»에서 읽는다: contents/<path>?ref=<head> → base64 decode → 두 리터럴 grep
    CQ="repos/$PIN_OR/contents/$WF_PATH?ref=$HSHA"; respond "$CQ"; show_capture B5 "$CQ"; CST=$(http_of "$CQ")
    if [ "$CST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b) d=$d head=$HSHA contents 조회 네트워크/인증 오류 — $CQ"; continue
    elif ! ok2xx "$CST"; then fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA contents http=$CST ($WF_PATH 부재·조회 실패) — 검사 생략 금지"; continue; fi
    WF=$(python3 -c 'import json,sys,base64
try:
    j=json.load(open(sys.argv[1])); enc=j.get("encoding"); c=j.get("content","")
    sys.stdout.write(base64.b64decode(c).decode("utf-8","replace") if enc=="base64" else str(c))
except Exception as e: sys.stdout.write("")' "$CAP/$(key "$CQ").body")
    printf 'U17-B5 decoded %s@%s (encoding=%s size=%s):\n' "$WF_PATH" "$HSHA" "$(jget "$CQ" encoding)" "$(jget "$CQ" size)"; printf '%s\n' "$WF" | sed 's/^/  | /'
    L1=$(printf '%s\n' "$WF" | grep -cF -- "$LIT1"); L2=$(printf '%s\n' "$WF" | grep -cF -- "$LIT2")
    printf 'U17-B5 grep: %s → %s회 · %s → %s회\n' "$LIT1" "$L1" "$LIT2" "$L2"
    if git cat-file -e "$HSHA^{commit}" 2>/dev/null; then LB=$(git rev-parse -q --verify "$HSHA:$WF_PATH" 2>/dev/null || echo ABSENT); printf 'U17-B5x 보조(선택·판정 미소비): 로컬 git show %s:%s → %s\n' "$HSHA" "$WF_PATH" "$LB"; else printf 'U17-B5x 보조(선택·판정 미소비): 로컬에 %s 커밋 없음 — 서버 조회만으로 판정\n' "$HSHA"; fi
    { [ "$L1" -ge 1 ] && [ "$L2" -ge 1 ]; } || { fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA 서버 워크플로 blob 에 리터럴 부재 (harness path=$L1 sha256=$L2)"; continue; }
    printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
  done
  for id in ${RSIDS:-}; do
    python3 - "$id" "$(jget "repos/$PIN_OR/rulesets/$id" created_at)" "$(jget "repos/$PIN_OR/rulesets/$id" updated_at)" "$MINMERGED" <<'PY'
import sys,datetime
i,ca,ua,mm=sys.argv[1:5]
def p(s):
    try: return datetime.datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(datetime.timezone.utc)
    except Exception: return None
c,u,m=p(ca),p(ua),p(mm)
if None in (c,u,m): print(f"U17-α ruleset {i}: 시각 파싱 불가(created_at={ca} updated_at={ua} merged_at(minD)={mm}) — 관측 기록"); sys.exit(0)
print(f"U17-α ruleset {i}: created_at={c.isoformat()} {'≤' if c<=m else '> (착수 후 생성)'} merged_at(minD)={m.isoformat()} · updated_at={u.isoformat()} {'> merged_at (착수 후 변경됨)' if u>m else '≤ merged_at'} (관측 기록·차단 아님)")
PY
  done
fi

finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=$ND · app/suite/workflow path/blob 2 리터럴) — responder=$RESP"
```

## 3. 드라이버 `t84v218e.sh` — 원문 (sha256 `aac1b72aade6b64c5bf33305b8cb360aeb7782c5bfb43eaa698c4aa77ce1d27c`)

픽스처 = `scratchpad/fx84y/*` · seam `scratchpad/seam218e/*`(contents 응답은 GitHub contents API 형태로 base64 인코딩해 주입 — 실행기의 decode 경로가 그대로 탄다). 정직 표기: 픽스처 커밋 메시지의
`declaration keys presentkakao-…` 는 드라이버 문자열 치환 실수(`${2:+present}${2:-absent}`)로 «present» 뒤에 값이 붙은 것 — 픽스처 메시지일 뿐 판정·캡처와 무관하며 원문 그대로 둔다.

```bash
#!/usr/bin/env bash
# t84v218e.sh — v2.18 에라타(feb91d60) 영향 변이 재실행 드라이버 (u17-verify-v218e.sh): E1 서버 blob(③-b·R2-a·R2-b·⑧) · E2 선언 키 부재(①·⑤·⑩) · live 병기(contents?ref=). GET-only.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
EX="$SP/u17-verify-v218e.sh"; FX="$SP/fx84y"; SEAM="$SP/seam218e"; PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md; WF=.github/workflows/tos-gate.yml
OR=kakao-harris-lee/kis_unified_sts; PINURL=https://github.com/kakao-harris-lee/kis_unified_sts.git; WB=mission-critical-trading-operating-system; REPO=/Users/harris/Development/private/kis_unified_sts
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; git -C "$1" remote add origin "${2:-$PINURL}"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; }
art(){ # art <repo> [owner_repo] [target] — 인자 없으면 선언 키 부재(E2 선택) 아티팩트
  mkdir -p "$1/$(dirname $PC)"; { [ -n "${2:-}" ] && printf 'owner_repo: %s\n' "$2"; [ -n "${3:-}" ] && printf 'target_branch: %s\n' "$3"; printf 'tos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture\n'; } > "$1/$PC"
  git -C "$1" add -A; git -C "$1" commit -q -m "P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys ${2:+present}${2:-absent})"; git -C "$1" rev-parse HEAD; }
wfcontent(){ if [ "${1:-}" = nolit ]; then printf 'name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo no-harness-here\n'; else printf 'name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - name: verify harness identity\n        run: shasum -a 256 tools/tos_entry_harness.sh | grep %s\n      - name: run entry harness\n        run: bash tools/tos_entry_harness.sh\n' "$LIT2"; fi; }
wf(){ mkdir -p "$1/.github/workflows"; wfcontent "${2:-}" > "$1/$WF"; git -C "$1" add -A; git -C "$1" commit -q -m "W: add $WF (SIMULATED)"; git -C "$1" rev-parse HEAD; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact\n' > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "D0-A: introduce config/tos_completion.yaml"; git -C "$1" rev-parse HEAD; }
run(){ echo "-- remotes --"; git -C "$1" remote -v | sed 's/^/  | /'; echo "-- artifact @HEAD --"; git -C "$1" show "HEAD:$PC" 2>/dev/null | sed 's/^/  | /'; git -C "$1" log --oneline --graph | sed 's/^/  /'; echo "\$ U17_RESPONDER=${2:-gh} bash u17-verify-v218e.sh <fixture>"; U17_RESPONDER="${2:-gh}" U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$1"; echo "u17_rc=$?"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; if [ -f "$4" ]; then cp "$4" "$1/$(k "$2").body"; else printf '%s\n' "$4" > "$1/$(k "$2").body"; fi; }
probe(){ echo "\$ gh api -i $1   # utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; gh api -i "$1" 2>&1 | grep -v -E '^[A-Za-z-]+: ' | tr -d '\r' | sed 's/^/  | /'; }
ACT='{"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}'
base_seam(){ inject "$1" "apps/github-actions" 200 '{"id":15368,"slug":"github-actions","name":"GitHub Actions"}'; inject "$1" "repos/$OR" 200 '{"full_name":"kakao-harris-lee/kis_unified_sts","default_branch":"main"}'; inject "$1" "repos/$OR/branches/main/protection" 200 "$2"; inject "$1" "repos/$OR/rules/branches/main" 200 '[]'; inject "$1" "repos/$OR/rulesets" 200 '[]'; }
contents_json(){ # contents_json <text-file> <sha> <path> → GitHub contents API 형태(base64)
  python3 - "$1" "$2" "$3" <<'PY'
import json,sys,base64
t=open(sys.argv[1],'rb').read()
print(json.dumps({"name":sys.argv[3].split("/")[-1],"path":sys.argv[3],"sha":sys.argv[2],"size":len(t),"type":"file","encoding":"base64","content":base64.b64encode(t).decode()+"\n"}))
PY
}
rev_seam(){ # rev_seam <dir> <d> <head> <suite> <contents-mode: ok|nolit|404> [path]
  local dir="$1" d="$2" h="$3" s="$4" cm="$5" path="${6:-.github/workflows/tos-gate.yml}"
  inject "$dir" "repos/$OR/commits/$d/pulls" 200 "[{\"number\":9999,\"state\":\"closed\",\"merged_at\":\"2026-08-19T00:10:00Z\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$h\"}}]"
  inject "$dir" "repos/$OR/commits/$h/check-runs" 200 "{\"total_count\":2,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}},{\"name\":\"tos-gate\",\"conclusion\":\"success\",\"app\":{\"id\":15368,\"slug\":\"github-actions\"},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}}]}"
  inject "$dir" "repos/$OR/check-suites/$s" 200 "{\"id\":$s,\"head_sha\":\"$h\",\"app\":{\"id\":15368,\"slug\":\"github-actions\"},\"status\":\"completed\",\"conclusion\":\"success\"}"
  inject "$dir" "repos/$OR/actions/runs?check_suite_id=$s" 200 "{\"total_count\":1,\"workflow_runs\":[{\"id\":424242,\"name\":\"tos-gate\",\"path\":\"$path\",\"head_sha\":\"$h\",\"check_suite_id\":$s,\"conclusion\":\"success\"}]}"
  case "$cm" in
    ok)    wfcontent > "$dir/wf.txt"; inject "$dir" "repos/$OR/contents/$WF?ref=$h" 200 "$(contents_json "$dir/wf.txt" "$(git hash-object "$dir/wf.txt")" "$WF")" ;;
    nolit) wfcontent nolit > "$dir/wf.txt"; inject "$dir" "repos/$OR/contents/$WF?ref=$h" 200 "$(contents_json "$dir/wf.txt" "$(git hash-object "$dir/wf.txt")" "$WF")" ;;
    404)   inject "$dir" "repos/$OR/contents/$WF?ref=$h" 404 '{"message":"Not Found","documentation_url":"https://docs.github.com/rest/repos/contents#get-repository-content","status":"404"}' ;;
  esac; }
rm -rf "$SEAM"; mkdir -p "$SEAM"; base_seam "$SEAM/active" "$ACT"

sec "E1 live 병기 — 실 repo PR#636 head 7656259d 로 contents?ref= 서버 조회 (로컬 head 미보유와 무관하게 성립하는가)"
HS=7656259d414c4a855824406bab40bdc5438de171
echo "\$ git -C <repo> cat-file -e $HS^{commit}"; git -C "$REPO" cat-file -e "$HS^{commit}" 2>&1 && echo "  present" || echo "  absent locally (v2.18 본 증거 §3 (3)-0 실측 그대로)"
probe "repos/$OR/contents/$WF?ref=$HS" | head -4
echo "\$ gh api -i repos/$OR/contents/.github/workflows/test.yml?ref=$HS   (요약)   # utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; gh api -i "repos/$OR/contents/.github/workflows/test.yml?ref=$HS" 2>&1 | head -1 | tr -d '\r' | sed 's/^/  | /'; gh api "repos/$OR/contents/.github/workflows/test.yml?ref=$HS" 2>/dev/null | python3 -c 'import json,sys,base64; j=json.load(sys.stdin); t=base64.b64decode(j["content"]).decode(); print("  name=%s size=%s encoding=%s sha=%s"%(j["name"],j["size"],j["encoding"],j["sha"])); print("  first line: %r"%t.splitlines()[0]); print("  grep tools/tos_entry_harness.sh: %d · grep 957bf49d…: %d"%(t.count("tools/tos_entry_harness.sh"), t.count("957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d")))'
echo "  ⇒ 서버 blob 조회는 로컬 head 미보유와 무관하게 성립(test.yml 200) · tos-gate.yml 은 그 head 에 부재(404) → 실 repo (b) 는 UNVERIFIED_REVISION (E1 규약)"

sec "T-84 (3)-b seam — (b) 양성: contents?ref=<head> 200 (base64·두 리터럴 포함) → ACTIVE  [E1 재실행]"
R="$FX/rev-seam"; mk "$R"; art "$R" "$OR" main >/dev/null; W=$(wf "$R"); D=$(d0a "$R"); echo "W(PR head)=$W d=$D"
S="$SEAM/rev-ok"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001 ok; run "$R" "file:$S"
sec "T-84 (R2)-a seam — contents?ref=<head> 404 (파일 부재) → UNVERIFIED_REVISION  [E1 재실행]"
S="$SEAM/rev-404"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001 404; run "$R" "file:$S"
sec "T-84 (R2)-b seam — contents 200 이나 두 리터럴 부재 → UNVERIFIED_REVISION  [E1 재실행]"
S="$SEAM/rev-nolit"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001 nolit; run "$R" "file:$S"
sec "T-84 (R2)-c seam — contents 조회 네트워크 오류(주입 응답 없음) → UNVERIFIABLE (E1: 네트워크·인증 → UNVERIFIABLE)"
S="$SEAM/rev-neterr"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001 ok; rm -f "$S/$(k "repos/$OR/contents/$WF?ref=$W")".*; run "$R" "file:$S"
sec "T-84 (8) seam — same-app wrong-workflow (path=test.yml · contents 는 200 정상) → UNVERIFIED_REVISION  [E1 실행기로 재실행]"
S="$SEAM/rev-path"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001 ok .github/workflows/test.yml; run "$R" "file:$S"
sec "T-84 (R2)-d seam — 로컬에 PR head 커밋이 없는 판정 저장소(별도 클론 모의)에서 서버 blob 만으로 ACTIVE  [E1 의 동기 그대로: squash 착지]"
R2="$FX/rev-nolocal"; mk "$R2"; art "$R2" "$OR" main >/dev/null; D2=$(d0a "$R2"); echo "d=$D2 · PR head 는 $W (이 저장소에 없는 커밋)"; S="$SEAM/rev-nolocal"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D2" "$W" 777001 ok; run "$R2" "file:$S"

sec "T-84 (1) live — 선언 키 부재 아티팩트(E2 선택) · 원격 == 핀 → 핀·default_branch 유일 소스 → INSUFFICIENT"
R="$FX/live-nodecl"; mk "$R"; art "$R" >/dev/null; run "$R" gh
sec "T-84 (5)/(10) live — 선언 키 부재 + 원격이 타 host(gitlab.com 동일 경로) → 선언 대조 미발화·원격 대조로 TARGET_MISMATCH (E2/E3)"
R="$FX/nodecl-gitlab"; mk "$R" https://gitlab.com/kakao-harris-lee/kis_unified_sts.git; art "$R" >/dev/null; run "$R" gh
sec "T-84 (5) live — 선언 키 있음(비-default 선언) → 여전히 TARGET_MISMATCH (E2: 있으면 대조)"
R="$FX/decl-wb"; mk "$R"; art "$R" "$OR" "$WB" >/dev/null; run "$R" gh
sec "T-84 부속 — 본 저장소 HEAD 에 실행기 적용 (아티팩트 부재 → ABSENT)"
echo "\$ bash u17-verify-v218e.sh <repo>"; U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO"; echo "u17_rc=$?"
```

## 4. 실행 기록 (t84v218e.sh stdout 전문 · 캡처 verbatim + UTC · live 병기 포함)

```text
t84v218e_utc=2026-08-18T19:14:15Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t84v218e.sh

########## E1 live 병기 — 실 repo PR#636 head 7656259d 로 contents?ref= 서버 조회 (로컬 head 미보유와 무관하게 성립하는가) ##########
$ git -C <repo> cat-file -e 7656259d414c4a855824406bab40bdc5438de171^{commit}
fatal: Not a valid object name 7656259d414c4a855824406bab40bdc5438de171^{commit}
  absent locally (v2.18 본 증거 §3 (3)-0 실측 그대로)
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=7656259d414c4a855824406bab40bdc5438de171   # utc=2026-08-18T19:14:15Z
  | HTTP/2.0 404 Not Found
  | 
  | {"message":"Not Found","documentation_url":"https://docs.github.com/rest/repos/contents#get-repository-content","status":"404"}gh: Not Found (HTTP 404)
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/test.yml?ref=7656259d414c4a855824406bab40bdc5438de171   (요약)   # utc=2026-08-18T19:14:16Z
  | HTTP/2.0 200 OK
  name=test.yml size=7224 encoding=base64 sha=02ce9913d4505f7ebb885f30c0038fc28c8e3ae5
  first line: '# .github/workflows/test.yml'
  grep tools/tos_entry_harness.sh: 0 · grep 957bf49d…: 0
  ⇒ 서버 blob 조회는 로컬 head 미보유와 무관하게 성립(test.yml 200) · tos-gate.yml 은 그 head 에 부재(404) → 실 repo (b) 는 UNVERIFIED_REVISION (E1 규약)

########## T-84 (3)-b seam — (b) 양성: contents?ref=<head> 200 (base64·두 리터럴 포함) → ACTIVE  [E1 재실행] ##########
W(PR head)=271b4a749600a3dd14d99dce8a02a10ac25d199e d=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0461c4b D0-A: introduce config/tos_completion.yaml
  * 271b4a7 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 568a7e1 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys presentkakao-harris-lee/kis_unified_sts)
  * 3aae139 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-ok bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-ok capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.03y75M02sL
U17-A00 apps/github-actions  utc=2026-08-18T19:14:17Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:14:17Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:14:17Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:14:17Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:14:17Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=568a7e172dee48823e59074598916db6493c8b60 P_last=568a7e172dee48823e59074598916db6493c8b60 |D|=1 D=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/0461c4baf9e27654313e4813e9baa5d1d2bfdf6d/pulls  utc=2026-08-18T19:14:18Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/271b4a749600a3dd14d99dce8a02a10ac25d199e/check-runs  utc=2026-08-18T19:14:18Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:14:18Z  http=200
  | {"id":777001,"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:14:18Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=271b4a749600a3dd14d99dce8a02a10ac25d199e  utc=2026-08-18T19:14:18Z  http=200
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@271b4a749600a3dd14d99dce8a02a10ac25d199e (encoding=base64 size=365):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: verify harness identity
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  |       - name: run entry harness
  |         run: bash tools/tos_entry_harness.sh
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B5x 보조(선택·판정 미소비): 로컬 git show 271b4a749600a3dd14d99dce8a02a10ac25d199e:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d head=271b4a749600a3dd14d99dce8a02a10ac25d199e merged_at=2026-08-19T00:10:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=1 · app/suite/workflow path/blob 2 리터럴) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-ok
u17_rc=0

########## T-84 (R2)-a seam — contents?ref=<head> 404 (파일 부재) → UNVERIFIED_REVISION  [E1 재실행] ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0461c4b D0-A: introduce config/tos_completion.yaml
  * 271b4a7 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 568a7e1 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys presentkakao-harris-lee/kis_unified_sts)
  * 3aae139 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-404 bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-404 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.urSXuHH5vI
U17-A00 apps/github-actions  utc=2026-08-18T19:14:19Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:14:19Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:14:19Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:14:19Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:14:19Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=568a7e172dee48823e59074598916db6493c8b60 P_last=568a7e172dee48823e59074598916db6493c8b60 |D|=1 D=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/0461c4baf9e27654313e4813e9baa5d1d2bfdf6d/pulls  utc=2026-08-18T19:14:19Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/271b4a749600a3dd14d99dce8a02a10ac25d199e/check-runs  utc=2026-08-18T19:14:20Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:14:20Z  http=200
  | {"id":777001,"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:14:20Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=271b4a749600a3dd14d99dce8a02a10ac25d199e  utc=2026-08-18T19:14:20Z  http=404
  | {"message":"Not Found","documentation_url":"https://docs.github.com/rest/repos/contents#get-repository-content","status":"404"}
U17-fire PREVENTION_UNVERIFIED_REVISION: (b) d=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d head=271b4a749600a3dd14d99dce8a02a10ac25d199e contents http=404 (.github/workflows/tos-gate.yml 부재·조회 실패) — 검사 생략 금지
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d head=271b4a749600a3dd14d99dce8a02a10ac25d199e contents http=404 (.github/workflows/tos-gate.yml 부재·조회 실패) — 검사 생략 금지 [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (R2)-b seam — contents 200 이나 두 리터럴 부재 → UNVERIFIED_REVISION  [E1 재실행] ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0461c4b D0-A: introduce config/tos_completion.yaml
  * 271b4a7 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 568a7e1 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys presentkakao-harris-lee/kis_unified_sts)
  * 3aae139 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-nolit bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-nolit capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Xc9Kl0YHnY
U17-A00 apps/github-actions  utc=2026-08-18T19:14:20Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:14:20Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:14:20Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:14:21Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:14:21Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=568a7e172dee48823e59074598916db6493c8b60 P_last=568a7e172dee48823e59074598916db6493c8b60 |D|=1 D=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/0461c4baf9e27654313e4813e9baa5d1d2bfdf6d/pulls  utc=2026-08-18T19:14:21Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/271b4a749600a3dd14d99dce8a02a10ac25d199e/check-runs  utc=2026-08-18T19:14:21Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:14:21Z  http=200
  | {"id":777001,"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:14:21Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=271b4a749600a3dd14d99dce8a02a10ac25d199e  utc=2026-08-18T19:14:21Z  http=200
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "bc3683291a33533abe0125fab2687e9620bf756e", "size": 124, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBydW46IGVjaG8gbm8taGFybmVzcy1oZXJlCg==\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@271b4a749600a3dd14d99dce8a02a10ac25d199e (encoding=base64 size=124):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - run: echo no-harness-here
U17-B5 grep: tools/tos_entry_harness.sh → 0회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 0회
U17-B5x 보조(선택·판정 미소비): 로컬 git show 271b4a749600a3dd14d99dce8a02a10ac25d199e:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-fire PREVENTION_UNVERIFIED_REVISION: (b) d=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d head=271b4a749600a3dd14d99dce8a02a10ac25d199e 서버 워크플로 blob 에 리터럴 부재 (harness path=0 sha256=0)
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d head=271b4a749600a3dd14d99dce8a02a10ac25d199e 서버 워크플로 blob 에 리터럴 부재 (harness path=0 sha256=0) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (R2)-c seam — contents 조회 네트워크 오류(주입 응답 없음) → UNVERIFIABLE (E1: 네트워크·인증 → UNVERIFIABLE) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0461c4b D0-A: introduce config/tos_completion.yaml
  * 271b4a7 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 568a7e1 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys presentkakao-harris-lee/kis_unified_sts)
  * 3aae139 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-neterr bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-neterr capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.PHSnYNTXkY
U17-A00 apps/github-actions  utc=2026-08-18T19:14:22Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:14:22Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:14:22Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:14:22Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:14:22Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=568a7e172dee48823e59074598916db6493c8b60 P_last=568a7e172dee48823e59074598916db6493c8b60 |D|=1 D=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/0461c4baf9e27654313e4813e9baa5d1d2bfdf6d/pulls  utc=2026-08-18T19:14:23Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/271b4a749600a3dd14d99dce8a02a10ac25d199e/check-runs  utc=2026-08-18T19:14:23Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:14:23Z  http=200
  | {"id":777001,"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:14:23Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=271b4a749600a3dd14d99dce8a02a10ac25d199e  utc=2026-08-18T19:14:23Z  http=ERR
  | SIMULATED responder: no injected response for repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=271b4a749600a3dd14d99dce8a02a10ac25d199e
U17-fire PREVENTION_UNVERIFIABLE: (b) d=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d head=271b4a749600a3dd14d99dce8a02a10ac25d199e contents 조회 네트워크/인증 오류 — repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=271b4a749600a3dd14d99dce8a02a10ac25d199e
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=(b) d=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d head=271b4a749600a3dd14d99dce8a02a10ac25d199e contents 조회 네트워크/인증 오류 — repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=271b4a749600a3dd14d99dce8a02a10ac25d199e [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (8) seam — same-app wrong-workflow (path=test.yml · contents 는 200 정상) → UNVERIFIED_REVISION  [E1 실행기로 재실행] ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0461c4b D0-A: introduce config/tos_completion.yaml
  * 271b4a7 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 568a7e1 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys presentkakao-harris-lee/kis_unified_sts)
  * 3aae139 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-path bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-path capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OG2SxzX4XD
U17-A00 apps/github-actions  utc=2026-08-18T19:14:23Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:14:23Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:14:24Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:14:24Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:14:24Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=568a7e172dee48823e59074598916db6493c8b60 P_last=568a7e172dee48823e59074598916db6493c8b60 |D|=1 D=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/0461c4baf9e27654313e4813e9baa5d1d2bfdf6d/pulls  utc=2026-08-18T19:14:24Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/271b4a749600a3dd14d99dce8a02a10ac25d199e/check-runs  utc=2026-08-18T19:14:24Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:14:24Z  http=200
  | {"id":777001,"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:14:24Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/test.yml","head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite_id":777001,"conclusion":"success"}]}
U17-fire PREVENTION_UNVERIFIED_REVISION: (b) d=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d head=271b4a749600a3dd14d99dce8a02a10ac25d199e 워크플로 정체성 불충족: workflow run path≠.github/workflows/tos-gate.yml ∨ head_sha≠PR head (paths=[('.github/workflows/test.yml', '271b4a7')]);
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=0461c4baf9e27654313e4813e9baa5d1d2bfdf6d head=271b4a749600a3dd14d99dce8a02a10ac25d199e 워크플로 정체성 불충족: workflow run path≠.github/workflows/tos-gate.yml ∨ head_sha≠PR head (paths=[('.github/workflows/test.yml', '271b4a7')]); [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (R2)-d seam — 로컬에 PR head 커밋이 없는 판정 저장소(별도 클론 모의)에서 서버 blob 만으로 ACTIVE  [E1 의 동기 그대로: squash 착지] ##########
d=c6a97af799d3cf32322b357d1046bd233f1997d9 · PR head 는 271b4a749600a3dd14d99dce8a02a10ac25d199e (이 저장소에 없는 커밋)
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * c6a97af D0-A: introduce config/tos_completion.yaml
  * 771f44a P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys presentkakao-harris-lee/kis_unified_sts)
  * bd18b12 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-nolocal bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-nolocal capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.AAOWbZZVSU
U17-A00 apps/github-actions  utc=2026-08-18T19:14:25Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:14:25Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:14:25Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:14:25Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:14:25Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=771f44af758bfb9eb5198bdf267cec6850a92f3b P_last=771f44af758bfb9eb5198bdf267cec6850a92f3b |D|=1 D=c6a97af799d3cf32322b357d1046bd233f1997d9 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/c6a97af799d3cf32322b357d1046bd233f1997d9/pulls  utc=2026-08-18T19:14:26Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/271b4a749600a3dd14d99dce8a02a10ac25d199e/check-runs  utc=2026-08-18T19:14:26Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:14:26Z  http=200
  | {"id":777001,"head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:14:26Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"271b4a749600a3dd14d99dce8a02a10ac25d199e","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=271b4a749600a3dd14d99dce8a02a10ac25d199e  utc=2026-08-18T19:14:26Z  http=200
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@271b4a749600a3dd14d99dce8a02a10ac25d199e (encoding=base64 size=365):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: verify harness identity
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  |       - name: run entry harness
  |         run: bash tools/tos_entry_harness.sh
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B5x 보조(선택·판정 미소비): 로컬에 271b4a749600a3dd14d99dce8a02a10ac25d199e 커밋 없음 — 서버 조회만으로 판정
U17-B d=c6a97af799d3cf32322b357d1046bd233f1997d9 head=271b4a749600a3dd14d99dce8a02a10ac25d199e merged_at=2026-08-19T00:10:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=1 · app/suite/workflow path/blob 2 리터럴) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218e/rev-nolocal
u17_rc=0

########## T-84 (1) live — 선언 키 부재 아티팩트(E2 선택) · 원격 == 핀 → 핀·default_branch 유일 소스 → INSUFFICIENT ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * af84a86 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys absent)
  * 8cb6029 seed
$ U17_RESPONDER=gh bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GIw0QcqeN1
U17-A00 apps/github-actions  utc=2026-08-18T19:14:28Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:14:28Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=∅(선택 키 부재 → 핀 유일 소스) target_branch=∅(선택 키 부재 → default_branch 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:14:28Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:14:29Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:14:30Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:14:30Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=af84a86a32986335aa6585c779d0738377923aaf P_last=af84a86a32986335aa6585c779d0738377923aaf |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (5)/(10) live — 선언 키 부재 + 원격이 타 host(gitlab.com 동일 경로) → 선언 대조 미발화·원격 대조로 TARGET_MISMATCH (E2/E3) ##########
-- remotes --
  | origin	https://gitlab.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://gitlab.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 6f4d021 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys absent)
  * e8a1edf seed
$ U17_RESPONDER=gh bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=gitlab.com/kakao-harris-lee/kis_unified_sts match=∅ | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MWcbcnWQbo
U17-A00 apps/github-actions  utc=2026-08-18T19:14:32Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:14:32Z  http=200  (.default_branch=main)
U17-fire PREVENTION_TARGET_MISMATCH: 계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=gitlab.com/kakao-harris-lee/kis_unified_sts)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=∅(선택 키 부재 → 핀 유일 소스) target_branch=∅(선택 키 부재 → default_branch 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:14:33Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:14:33Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:14:34Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:14:34Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=6f4d021b5004265ff32df9f7ce11ae4830ba2172 P_last=6f4d021b5004265ff32df9f7ce11ae4830ba2172 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=gitlab.com/kakao-harris-lee/kis_unified_sts) [수집 2건 중 전순서 최소]
u17_rc=1

########## T-84 (5) live — 선언 키 있음(비-default 선언) → 여전히 TARGET_MISMATCH (E2: 있으면 대조) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: mission-critical-trading-operating-system
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 2af4cf6 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys presentkakao-harris-lee/kis_unified_sts)
  * 49ecf9f seed
$ U17_RESPONDER=gh bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1u0J8QtWa8
U17-A00 apps/github-actions  utc=2026-08-18T19:14:36Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:14:36Z  http=200  (.default_branch=main)
U17-T declared-vs-pin:  target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main) (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=mission-critical-trading-operating-system)
U17-fire PREVENTION_TARGET_MISMATCH: 아티팩트 선언값이 계약 핀/파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:14:37Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:14:37Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:14:38Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:14:38Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=2af4cf65e63d5d6deef8b9a2fc8a8e7d83c57375 P_last=2af4cf65e63d5d6deef8b9a2fc8a8e7d83c57375 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 계약 핀/파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main) [수집 2건 중 전순서 최소]
u17_rc=1

########## T-84 부속 — 본 저장소 HEAD 에 실행기 적용 (아티팩트 부재 → ABSENT) ##########
$ bash u17-verify-v218e.sh <repo>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Fhtw4QXfGB
U17-A00 apps/github-actions  utc=2026-08-18T19:14:40Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:14:40Z  http=200  (.default_branch=main)
U17-fire PREVENTION_ABSENT: 아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:14:40Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:14:41Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:14:41Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:14:42Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=∅ P_last=∅ |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
u17_rc=1
(t84v218e.sh exit=0)
```

픽스처 DAG (조립 시점 재확인):

```text
== fx84y/rev-seam  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* 0461c4b D0-A: introduce config/tos_completion.yaml
* 271b4a7 W: add .github/workflows/tos-gate.yml (SIMULATED)
* 568a7e1 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys presentkakao-harris-lee/kis_unified_sts)
* 3aae139 seed
== fx84y/rev-nolocal  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* c6a97af D0-A: introduce config/tos_completion.yaml
* 771f44a P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys presentkakao-harris-lee/kis_unified_sts)
* bd18b12 seed
== fx84y/live-nodecl  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* af84a86 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys absent)
* 8cb6029 seed
== fx84y/nodecl-gitlab  (remotes: origin=https://gitlab.com/kakao-harris-lee/kis_unified_sts.git )
* 6f4d021 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys absent)
* e8a1edf seed
== fx84y/decl-wb  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* 2af4cf6 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys presentkakao-harris-lee/kis_unified_sts)
* 49ecf9f seed
```

## 5. 관측·정직 기록 (고치지 않는다 — bound_paths 동결)

1. **E1 실증**: 같은 head 에 대해 로컬은 커밋 미보유(`cat-file -e` 실패)인데 서버 `contents?ref=` 는 `test.yml` 200 을 돌려줬다 — 서버 조회는 판정 저장소의 fetch 상태와 무관. `tos-gate.yml` 은 그 head 에
   부재(404) → 실 repo (b) 는 여전히 `UNVERIFIED_REVISION`(CI 에 그 워크플로가 없다 — 계약 정직 표기 그대로). R2-d 는 «PR head 를 보유하지 않은 판정 저장소»에서 서버 blob 만으로 ACTIVE(모의)를 냈다 —
   본 증거 §4-3 이 보고한 «정직한 착지도 red» 정밀화 후보가 E1 로 닫혔음을 실측.
2. **E2 실증**: 선언 키 부재 아티팩트로 ①(INSUFFICIENT)·⑩(원격 축 MISMATCH)이 그대로 성립하고 선언 대조는 미발화(`U17-T … 선언 없음`) — «없으면 핀·API 가 유일 소스» 극성 그대로. 선언 있음(비-default)은 불변 MISMATCH.
3. **E3**: 실행기 거동 불변(v2.18 본 증거 ⑩-c) — 이 addendum 은 문언 정합화만 확인.
4. **신규 결함 후보 없음**. 정밀화 여지 1건(비차단): contents API 는 파일 크기 >1MB 에서 `content` 를 비우고 `download_url` 만 준다 — 워크플로 파일이 그 크기를 넘는 경우는 비현실적이나, 계약 E1 은 «base64 decode» 만
   적었으므로 «`encoding≠base64`/`content` 부재 = UNVERIFIED_REVISION(검사 생략 금지)» 로 읽었다(실행기: decode 불가 → 빈 텍스트 → 리터럴 0회 → UNVERIFIED_REVISION).
5. 본 저장소 무접촉·설정 변경 0·worktree 미사용 — §6 사후 재조회로 실행 전후 동일 확인. **S-24**: 이 addendum 은 에라타 재동결 `feb91d60` 에 결속(§6).

## 6. 사후 검증 원문 (repo 무영향 · 서버 설정 무변경 · S-24 결속 feb91d60 · 본 저장소 NOT_STARTED/PREVENTION_ABSENT/REBINDING_REQUIRED)

```text
=== 사후 검증 (2026-08-18T19:14:58Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               feb91d60 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
feb91d60 docs(tos): phase0 completion contract v2.18 errata — server-side workflow blob, declaration keys optional, remote coexistence
-- 실행 전 스냅샷 대조 --
status/HEAD: 실행 전과 byte-동일
-- 이 사이클은 worktree 미사용(픽스처 = scratchpad 독립 repo) — 본 저장소에 모의 커밋 0 --
       3
-- 본 저장소 D0-A 미착수 불변 --
ls: config/tos_completion.yaml: No such file or directory
(도입 커밋 출력 없음 = 미착수)
-- 본 저장소 U-17 아티팩트 부재 (진실 원천은 서버이나 파라미터 선언·기록은 아티팩트) --
absent (HEAD 트리)
$ bash u15g-exec215e.sh <repo>
d0a_entry_provenance_state=NOT_STARTED
reason=|D| = 0
exec_rc=0
$ bash u17-verify-v218e.sh <repo>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.c83ln5gSzE
U17-A00 apps/github-actions  utc=2026-08-18T19:15:35Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:15:35Z  http=200  (.default_branch=main)
U17-fire PREVENTION_ABSENT: 아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:15:36Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:15:36Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:15:37Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:15:37Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=∅ P_last=∅ |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
u17_rc=1
$ bash harness218e.sh (본 저장소 현행)
R-0 head=feb91d60782a5441e4f00e0123779d0366b89c1a
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1
-- 서버 설정 무변경 확인 (GET-only 재조회 · 실행 전 캡처와 동일 필드) --
  main: strict=False contexts=['test'] enforce_admins=False pr_reviews=False
  rulesets: [('protect_main', 'disabled')]
-- 모의 스탬프·ART·기존 transcript 무변경 --
(2999* 없음)
(출력 없음 = 무변경)
-- scratchpad 픽스처(독립 repo)·worktree 잔여 --
decl-wb live-nodecl nodecl-gitlab rev-nolocal rev-seam 
(wt/ 비어 있음)
-- S-24 결속: 계약 워킹트리 == 최종 동결 feb91d60 blob · 하니스 블록 byte-동일 --
  HEAD=feb91d60782a5441e4f00e0123779d0366b89c1a  contract blob(HEAD)=aa7839b1ca1da440b704ff6bf658b5cf27ce517d  contract blob(feb91d60)=aa7839b1ca1da440b704ff6bf658b5cf27ce517d
  git diff --quiet feb91d60 -- <계약>: 무차이 (워킹트리 == feb91d60)
  sha256(워킹트리 계약)=2a7926831b8c6ababeb747d370bc8f9d1fff10678507b81a6196f65d6d793db5
  하니스 블록: git show feb91d60:<계약> | sed -n '4528,4628p' | shasum -a 256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  feb91d60..HEAD 에 계약 문서 커밋 0 (에라타 없음 — 증거가 최종 동결에 결속)
```
