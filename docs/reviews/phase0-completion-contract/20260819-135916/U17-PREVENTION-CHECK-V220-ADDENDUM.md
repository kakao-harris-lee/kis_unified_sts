# U17-PREVENTION-CHECK-V220-ADDENDUM — S-24 재결속 (v2.20 **에라타 재동결 `ae842cce`**)

- **비규범 부속**. 계약·개발계획을 바꾸지 않는다. 선행 증거 `U17-PREVENTION-CHECK-V220.md` · `U16-LEDGER-CHECK-V220.md`(커밋 `d101eb63`)는 **(4d) 불변** — 정정·재결속은 이 파일로 한다.
- 생성 UTC `2026-08-19T08:32:52Z` · 서버 쓰기·설정 변경 **0** · GitHub 는 **GET-only**(사후 재조회 1회 · §6) · 픽스처는 scratchpad **독립 git 저장소**(본 저장소 무접촉·worktree 미사용).

## 0. 결속 선언 (실측 §6 원문)

| 항목 | 실측 |
| --- | --- |
| HEAD | `ae842cceab472c947ec9c01f6b181f5151b92172` == `ae842cce` |
| 계약 워킹트리 blob | `9bfa21aa957b0b001a2f4daf7d26f472619175a5` == `git show ae842cce:<계약>` |
| 개발계획 blob | `d00aa15ef84a9f76058403a0dd91549c9f614533` == `git show 3d17ea66:<개발계획>` (**에라타에서 무변경**) |
| `ae842cce..HEAD` | 두 문서 커밋 **0** · 전체 커밋 **0** |
| 하니스 `sed -n '4654,4754p'` | sha256 `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d` — 계약 리터럴 일치 ∧ `3d17ea66` 과 **byte-동일**(같은 행 범위) |
| 계약 행수 | 7,494 (동결과 동일 · 인라인 +7/-7) |

## 1. S-24 ① — 무엇이 바뀌었고, 무엇이 닿지 않았나

### 1-1. 계약 차분 원문 (`git diff -U0 3d17ea66..ae842cce -- <계약>`)

```diff
diff --git a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
index 5d6044e9..9bfa21aa 100644
--- a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+++ b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
@@ -125 +125 @@
-> | **v2.20** | **재심 미착수.** v2.19 판정 5건(#1 U-17 (b)③ · #2 U-16-a2 g6 · #3 [PARENTS-UNTRUSTED] TOCTOU · #4 T-82 ⑯ · #5 #6 운영자 게이트)을 반영한 판이며, **운영자 지시(2026-08-19)로 개발계획 개정을 함께 적용**했다(#5/#6 처분 변경 — Phase 0/1 선행관계). **동결 → 증거 → (필요 시 에라타) → 운영자 재결속(현행 사이클)** 대기다. 재결속 전에는 심사를 요청하지 않는다(§12.3.2) |
+> | **v2.20** | **재심 미착수.** v2.19 판정 5건(#1 U-17 (b)③ · #2 U-16-a2 g6 · #3 [PARENTS-UNTRUSTED] TOCTOU · #4 T-82 ⑯ · #5 #6 운영자 게이트)을 반영한 판이며, **운영자 지시(2026-08-19)로 개발계획 개정을 함께 적용**했다(#5/#6 처분 변경 — Phase 0/1 선행관계). **동결(`3d17ea66`) → 증거(`d101eb63` — 문언 에라타 ⓐⓑⓒ 적발·fail-open 0) → 에라타 재동결(문언·과잉 차단 방향) → 운영자 재결속(현행 사이클)** 대기다. 재결속 전에는 심사를 요청하지 않는다(§12.3.2) |
@@ -208 +208 @@
-| **v2.20** | **v2.19 심판 판정 5건(high 3 / medium 2) 전건 반영 + 운영자 지시(2026-08-19)로 개발계획 개정 적용. 직전 처분은 «F1·F4 부분해소 · #2 host·F2·F5 해소(아크 누적 8) · #6 미해소» 이고 신규 3 high 는 전부 «의미 정합 실패»다.** ① **#1 U-17 (b)③ (high) — 워크플로 blob 두 리터럴 grep**: v2.19 는 blob 텍스트에 하니스 경로·sha256 두 리터럴이 «존재»하면 검증 스텝 «존재»로 간주해, 주석·미사용 값에 심고 잡은 `true` 만 돌려도 통과했다(심판 메모리 픽스처). **«문자열 존재» → «실행 스텝 구조»로 교체**: (1) blob 을 YAML 파서로 구조 파싱(주석·비-`run` 필드·셸 주석 배제)해 `run harness` 스텝의 `run:` 이 하니스를 «실행 인자»로 호출하고 `verify sha256` 스텝의 `run:` 이 sha256 을 «대조 대상»으로 비교하는지 · (2) 서버 잡 `steps[]`(`actions/runs/{run_id}/jobs`)에 계약 리터럴 스텝 이름(`tos-gate: run harness`·`tos-gate: verify harness sha256`)이 `conclusion==success` 로 실재하는지 대조 — «그 이름의 스텝이 서버에서 실행됐다»는 서버 기록. **정직 경계**: 스텝 이름·결론은 서버 기록이지 «run 내용을 바이트 그대로 실행했다»의 증명이 아니다(GitHub 내부) — 위조 비용을 «올리되 닫지 못한다». T-84 **12→14종**(⑬ 비활성 리터럴 변이·⑭ 서버 스텝 부재/실패) ② **#2 U-16-a2 g6 (high)** — a2 전칭이 «U-16-g 전 항(g1~g5)» 으로 닫힌 열거라 v2.13 신설 `g6` 을 제외해 인접 S-6 전칭 규율과 자기모순(S-22: g6 신설 시 이 괄호에 미전파)했다. **«(g1~g5)» 제거 → «U-16-g 전 항» 전칭**·6822 에 g6 명시 + «g6 생략 소비자는 `R∥A` 승인으로 `APPROVAL_ORDER_INVALID` 우회 → T-82 ⑮ red» 대조·모든 규범 표면 단일 해석(6877 은 이미 g6 포함). 종수 불변 ③ **#3 [PARENTS-UNTRUSTED] TOCTOU (high)** — ㉡ 의 grafts/replace 부재 관측이 «한 시점»이고 이후 조상성 소비(`%P`·`merge-base`)와 «같은 불변 스냅샷»에 미결속이라, 동시 프로세스가 ㉡ 관측 후·조상성 조회 전에 후보 밖 graft 설치·조회 후 제거하면 `LATE`/`ORDER_INVALID` 를 `ACTIVE`/`NO_ROWS_CLEAR` 로 뒤집었다. **극성 논증 후 (ii) 격리 스냅샷 채택**((i) 2회 관측은 «창 좁힘»이지 «닫음» 아님·K-4 도 못 닫음): 조상성·부모·원장 blob 소비 전부를 진입 시점 HEAD 의 «격리 스냅샷»(`git clone --no-local --no-hardlinks` 단일 방법·`GIT_NO_REPLACE_OBJECTS=1`·bundle 대안 아님[`--all`=refs/replace 유출])에서만 수행 — grafts 는 직렬화 안 돼 전송 미전파·replace 는 기본 refspec 미포함·커밋 객체 내용주소라 스냅샷 조상성=참 그래프 → 「관측 후 삽입」 창 «구조적 부재». **K-4(후보 밖 재작성) 포섭**·**㉡ 은 «원 저장소 관측(리뷰 보조)»으로 격하**·스냅샷 안 ㉡ 은 canary. **정직 경계(«닫힌다» 아님)**: 원본 graft 는 스냅샷을 «실패»시킬 뿐 거짓 통과시키지 못함(연결성 검사)·판정 소비자 자신의 환경 위조는 계약 밖 — 잔여의 «종류»가 후보-우주 사각→전송 충실도로 이동. T-82 ⑳ⓒ(interleaving SIMULATED·격리 클론 픽스처)·T-84 ⑨ 확장·종수 불변 ④ **#4 T-82 ⑯ (medium)** — 같은 셀 ⑱ 만 v2.19 가 현행 스키마로 고치고 형제 항 ⑯ 이 «두 간선 각각 `edge_seq` 1·2» 폐지 필드 잔존(S-22 재발·같은 셀). **⑯ 을 현행 스키마로 재기술**(선형 반복 이력·edge_seq 미기재·소비자 `(author date, commit id)` 표시용 파생·`NO_ROWS_CLEAR`·폐지 필드 소비 구현은 정상 반복 이력 영구 차단으로 red)·같은 셀 ⑮~⑳ 전건 재독·⑱ 상보. 종수 불변 ⑤ **#5 #6 두 결속 계획 충돌 (medium, 운영자 게이트 — 적용됨)** — v2.19 까지 계약 verbatim 제안만 수록(개발계획 무편집)이라 결속 문서 미변경 = 미해소였다. **운영자 지시(2026-08-19)로 개발계획을 이 판에서 함께 편집**: Phase 1 작업 7 tos-gate 분리(D)①·Phase 0 «선행 조건(D0-A 착수 전): 예방 통제 활성» 신설(D)②·Phase 1 종료조건 «연속성 유지»(D)③·헤더 개정 주석. 계약 (D) 를 «적용됨»으로 갱신하고 실제 삽입 위치·문안을 (D) 에 재기록(verbatim 사실 일치). **해소 계수 아님**(주장·재결속·재심 전) — 두 문서 재동결→재결속으로 함께 심사. **종수 전파(S-20)**: T-84 12→**14종**(⑬⑭) · T-82 20 불변(⑮ 절·⑯ 재기술·⑳ⓒ 는 종수 불변) · T-81 19 불변 · U-17-c 10값 불변(⑬⑭ 는 기존 `PREVENTION_UNVERIFIED_REVISION` 로 접힘). **§12.3.3**: (A)=v2.19 판정 6건 리터럴 처분(#6 미해소 포함)·(B)=v2.20 5건 주장(«어느 것도 해소 아님»·#6 은 개발계획 개정 적용 주장)·(D)=운영자 게이트 «적용됨». **S-22 스윕**: §0 심사 상태·수렴 기록(해소 8·12판 연속·→5)·심사 이력 v2.19 실판정+v2.20 미착수·(A)(B)(D)·«개발계획 무편집/운영자 소관» 활성 표현 갱신. **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`)·`bound_paths` 2건(계약+개발계획) 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
+| **v2.20** | **v2.19 심판 판정 5건(high 3 / medium 2) 전건 반영 + 운영자 지시(2026-08-19)로 개발계획 개정 적용. 직전 처분은 «F1·F4 부분해소 · #2 host·F2·F5 해소(아크 누적 8) · #6 미해소» 이고 신규 3 high 는 전부 «의미 정합 실패»다.** ① **#1 U-17 (b)③ (high) — 워크플로 blob 두 리터럴 grep**: v2.19 는 blob 텍스트에 하니스 경로·sha256 두 리터럴이 «존재»하면 검증 스텝 «존재»로 간주해, 주석·미사용 값에 심고 잡은 `true` 만 돌려도 통과했다(심판 메모리 픽스처). **«문자열 존재» → «실행 스텝 구조»로 교체**: (1) blob 을 YAML 파서로 구조 파싱(주석·비-`run` 필드·셸 주석 배제)해 `run harness` 스텝의 `run:` 이 하니스를 «실행 인자»로 호출하고 `verify sha256` 스텝의 `run:` 이 sha256 을 «대조 대상»으로 비교하는지 · (2) 서버 잡 `steps[]`(`actions/runs/{run_id}/jobs`)에 계약 리터럴 스텝 이름(`tos-gate: run harness`·`tos-gate: verify harness sha256`)이 `conclusion==success` 로 실재하는지 대조 — «그 이름의 스텝이 서버에서 실행됐다»는 서버 기록. **정직 경계**: 스텝 이름·결론은 서버 기록이지 «run 내용을 바이트 그대로 실행했다»의 증명이 아니다(GitHub 내부) — 위조 비용을 «올리되 닫지 못한다». T-84 **12→14종**(⑬ 비활성 리터럴 변이·⑭ 서버 스텝 부재/실패) ② **#2 U-16-a2 g6 (high)** — a2 전칭이 «U-16-g 전 항(g1~g5)» 으로 닫힌 열거라 v2.13 신설 `g6` 을 제외해 인접 S-6 전칭 규율과 자기모순(S-22: g6 신설 시 이 괄호에 미전파)했다. **«(g1~g5)» 제거 → «U-16-g 전 항» 전칭**·6822 에 g6 명시 + «g6 생략 소비자는 `R∥A` 승인으로 `APPROVAL_ORDER_INVALID` 우회 → T-82 ⑮ red» 대조·모든 규범 표면 단일 해석(6877 은 이미 g6 포함). 종수 불변 ③ **#3 [PARENTS-UNTRUSTED] TOCTOU (high)** — ㉡ 의 grafts/replace 부재 관측이 «한 시점»이고 이후 조상성 소비(`%P`·`merge-base`)와 «같은 불변 스냅샷»에 미결속이라, 동시 프로세스가 ㉡ 관측 후·조상성 조회 전에 후보 밖 graft 설치·조회 후 제거하면 `LATE`/`ORDER_INVALID` 를 `ACTIVE`/`NO_ROWS_CLEAR` 로 뒤집었다. **극성 논증 후 (ii) 격리 스냅샷 채택**((i) 2회 관측은 «창 좁힘»이지 «닫음» 아님·K-4 도 못 닫음): 조상성·부모·원장 blob 소비 전부를 진입 시점 HEAD 의 «격리 스냅샷»(`git clone --no-local --no-hardlinks` 단일 방법·`GIT_NO_REPLACE_OBJECTS=1`·bundle 대안 아님[`--all`=refs/replace 유출])에서만 수행 — grafts 는 직렬화 안 돼 전송 미전파·replace 는 기본 refspec 미포함·커밋 객체 내용주소라 스냅샷 조상성=참 그래프 → 「관측 후 삽입」 창 «구조적 부재». **K-4(후보 밖 재작성) 포섭**·**㉡ 은 «원 저장소 관측(리뷰 보조)»으로 격하**·스냅샷 안 ㉡ 은 canary. **정직 경계(«닫힌다» 아님)**: 원본 graft 는 스냅샷을 «실패»시킬 뿐 거짓 통과시키지 못함(연결성 검사)·판정 소비자 자신의 환경 위조는 계약 밖 — 잔여의 «종류»가 후보-우주 사각→전송 충실도로 이동. T-82 ⑳ⓒ(interleaving SIMULATED·격리 클론 픽스처)·T-84 ⑨ 확장·종수 불변 ④ **#4 T-82 ⑯ (medium)** — 같은 셀 ⑱ 만 v2.19 가 현행 스키마로 고치고 형제 항 ⑯ 이 «두 간선 각각 `edge_seq` 1·2» 폐지 필드 잔존(S-22 재발·같은 셀). **⑯ 을 현행 스키마로 재기술**(선형 반복 이력·edge_seq 미기재·소비자 `(author date, commit id)` 표시용 파생·`NO_ROWS_CLEAR`·폐지 필드 소비 구현은 정상 반복 이력 영구 차단으로 red)·같은 셀 ⑮~⑳ 전건 재독·⑱ 상보. 종수 불변 ⑤ **#5 #6 두 결속 계획 충돌 (medium, 운영자 게이트 — 적용됨)** — v2.19 까지 계약 verbatim 제안만 수록(개발계획 무편집)이라 결속 문서 미변경 = 미해소였다. **운영자 지시(2026-08-19)로 개발계획을 이 판에서 함께 편집**: Phase 1 작업 7 tos-gate 분리(D)①·Phase 0 «선행 조건(D0-A 착수 전): 예방 통제 활성» 신설(D)②·Phase 1 종료조건 «연속성 유지»(D)③·헤더 개정 주석. 계약 (D) 를 «적용됨»으로 갱신하고 실제 삽입 위치·문안을 (D) 에 재기록(verbatim 사실 일치). **해소 계수 아님**(주장·재결속·재심 전) — 두 문서 재동결→재결속으로 함께 심사. **종수 전파(S-20)**: T-84 12→**14종**(⑬⑭) · T-82 20 불변(⑮ 절·⑯ 재기술·⑳ⓒ 는 종수 불변) · T-81 19 불변 · U-17-c 10값 불변(⑬⑭ 는 기존 `PREVENTION_UNVERIFIED_REVISION` 로 접힘). **§12.3.3**: (A)=v2.19 판정 6건 리터럴 처분(#6 미해소 포함)·(B)=v2.20 5건 주장(«어느 것도 해소 아님»·#6 은 개발계획 개정 적용 주장)·(D)=운영자 게이트 «적용됨». **S-22 스윕**: §0 심사 상태·수렴 기록(해소 8·12판 연속·→5)·심사 이력 v2.19 실판정+v2.20 미착수·(A)(B)(D)·«개발계획 무편집/운영자 소관» 활성 표현 갱신. **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`)·`bound_paths` 2건(계약+개발계획) 편집이므로 O-6 재결속 필요.** **[v2.20 에라타 (동결 `3d17ea66` 후 증거 실행 `d101eb63` 적발 — 재결속 전이므로 정정 후 재동결·전부 문언·과잉 차단/정합 방향·fail-open 0)]** 증거(`U17-PREVENTION-CHECK-V220.md`·`U16-LEDGER-CHECK-V220.md`)가 기대 전건 일치하되 계약 문언 결함 후보 3건을 적발했다: **ⓐ M-3(문언·과잉 차단)** :5461 «명령 위치(첫 단어)»가 관용 표기 `bash tools/tos_entry_harness.sh`(인터프리터+스크립트 인자)를 배제해 정상 워크플로 red(WF-P6x 대조) → «실행 위치 = 명령 위치 ∪ 인터프리터[`bash`·`sh`·`zsh`·`dash`·`ksh`·절대경로·`env`] 첫 비-옵션 인자»로 정정·`echo` 등 출력 명령 인자는 배제 유지(⑬a)·T-84 ⑬ 기준선 양성(`bash tools/…`) 병기·극성=과잉 차단은 fail-closed 결함(S-15) **ⓑ M-1(실행기 계보→계약 문언 보강)** 격리 스냅샷 진입 후 «캐시된 결합 base»가 원 저장소 경로 검사→«거짓 ABSENT»=E15 재발(증거 실행기는 D-γ 로 수정) → 정직 경계 (b)에 «스냅샷 진입 후 파생 경로(`--git-path`·`--show-toplevel`·grafts/replace canary) 전부 스냅샷 안 재파생·진입 전 값 재사용 금지» 명시 **ⓒ N-1(문언 정합)** :7128 «㉠==%P 항상 성립 canary»가 E12(얕은 경계 국소)와 충돌 — 얕은 원본은 스냅샷도 얕음 상속이라 문자 구현이 참 사유(`|c_APP|=0`)를 «기층 오염»으로 덮음 → canary 에 «㉢ 얕은 경계 귀속분 먼저 제외» 명시(양쪽 fail-closed·사유만 상이). **관측(비차단)**: M-2 스냅샷 비용(본 저장소 151초·`.git` 89M)·M-4 ⑬c 미검출 예고대로(정직 경계 확인)·M-5 스텝 «이름» 위조 자인 유지·N-2 ⑳ⓒ fail-open 은 «㉠ 교차검사 회피» 창 한정. **종수 불변**(ⓐ~ⓒ 문언·⑬ 기준선 하위 케이스). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`·:4654-4754)·개발계획 무편집(적용분 유지)·`bound_paths`(계약만) 재동결.** **증거 결속(S-24)**: 이 에라타 재동결도 addendum 으로 이행(절 범위 `git diff` 공집합 + 영향 변이 재실행 — `bash tools/…` 양성·스냅샷 안 재파생·얕음 상속 canary 귀속). **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
@@ -2885 +2885 @@ RUNTIME/FAULT/REVIEWER 존재성·REV2·A-1/A-2·D0-5에 테스트가 없었다.
-| **T-84** | **U-17 예방 통제 활성 증거** (§12.3.4) | **v2.15 신설 / v2.16 재작성 / [v2.17 재작성 — stop-time BLOCK B3 / v2.19 확장 / v2.20 확장]** — 파라미터화 **14종**. **v2.16 에라타 E2 가 #5 근거만 고치고 이 행을 보지 않아**(S-22) `rulesets=[]`·«머지 커밋 check-runs 0»·«pulls 공집합»이 **같은 턴 실측과 충돌**한 채 남아 있었다 — 행 전체를 재작성한다. ① **live 서버 음성(실측)** — 아티팩트 선언 == 구조 파생(`main`)인 정상 구성에서 `responder=gh` 실조회: `required_status_checks {strict:false, contexts:["test"]}` 이므로 **`PREVENTION_INSUFFICIENT`** · `/rules/branches/main` → `[]`(적용 규칙 0) · `/rulesets` → `[{name:"protect_main", enforcement:"disabled"}]` ⇒ **룰셋은 실재하나 disabled 라 동등물 없음**. **인증된 진짜 음성이며 모의가 아니다**. **[E1 — v2.17 에라타]** 초안은 여기에 «작업 브랜치 → 404 → `PREVENTION_ABSENT`» 를 함께 적었으나, **v2.17 에서 `target_branch` 는 `default_branch` 로 «파생»되므로 그 구성은 ⑤(`TARGET_MISMATCH`)이지 `ABSENT` 가 아니고 실행기로 재현되지 않는다**(증거 실행 적발 — S-22: B1 의 파생 전환이 이 행에 미전파). **«비-default 브랜치 protection → 404»는 «raw probe 관측»으로만 병기**하며 상태값 기대가 아니다 ② **seam 주입(`SIMULATED`)** — `responder` 주입으로 `PREVENTION_ACTIVE`·`INSUFFICIENT`·`UNVERIFIABLE` 모의. **기본 responder 는 `gh api`**. **양성은 운영자가 보호를 설정하기 전까지 실측 불가**임을 숨기지 않는다. **진정성은 §12.3.4 «진실 원천» 절이 «판정 소비자 자신의 조회»로 닫는다** ③ **리비전 검증(실측)** — `/commits/{d}/pulls` → 착지 PR → PR `head.sha` check-runs. 실측: `origin/main` 착지 `11e382fc` 의 check-runs **15건**(push 트리거 워크플로)·`pulls` = PR #636(merged·base main), PR head `7656259d` check-runs 5건에 **`tos-gate` 없음** ⇒ **`PREVENTION_UNVERIFIED_REVISION`**. 미푸시 커밋 → 422 ⇒ `PREVENTION_UNVERIFIABLE` · 푸시됐으나 PR 없는 `be98f075` → `pulls` `[]` ⇒ UNVERIFIED_REVISION ④ **보호 해제 후(stub)** — «countersign 시 ACTIVE → 이후 해제» 후 완료 판정 재조회가 `ABSENT`/`INSUFFICIENT` ⑤ **[v2.17 신설] target 불일치** — 아티팩트가 **다른 저장소/브랜치**를 선언(예: 보호가 걸린 타 repo, 또는 default 아닌 브랜치) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **`D = ∅` 에서도 red 여야 한다** — v2.16 은 이 구성에서 **임의 대상의 보호만으로 ACTIVE** 를 냈다 ⑥ **[v2.17 신설] `app_id` 위조** — `tos-gate` 라는 이름에 `conclusion: success` 이지만 **`app.id` 가 게이트 앱(기본 `15368`)이 아닌** check-run 을 seam 으로 주입 → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **이름만 보는 구현은 통과시키므로 실패한다** ⑦ **[v2.18] 타 앱 고정 required check** — 보호는 있고 `contexts` 에 `tos-gate` 도 있으나 `required_status_checks.checks[]` 의 그 컨텍스트 `app_id` 가 **Actions 가 아닌 앱**(예 99999) → **`PREVENTION_INSUFFICIENT`** + 비-0. **v2.17 은 이름만 봐서 `prot_ok` 를 냈고 `D=∅` 이면 그대로 진입 승인**됐다(심판이 실행기 술어로 재현) ⑧ **[v2.18] same-app wrong-workflow** — **같은 Actions app id** 로 **다른 워크플로**의 잡을 `tos-gate` 로 이름 지어 success 게시 → workflow run 의 `path` 가 `.github/workflows/tos-gate.yml` 이 아니므로 **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **app id 만 보는 구현은 통과시킨다**(실측: PR #636 head 의 5 run 이 전부 동일 app id) ⑨ **[v2.18] 아티팩트 사후 편집** — `P` → D0-A 착수 → 아티팩트 편집 → **`PREVENTION_ARTIFACT_MUTATED`** + 비-0. **`P_last` 를 쓰지 않고 «최초 도입 P» 만 보는 구현은 통과시킨다**  **[v2.20 — 심판 #3] 부모신뢰 TOCTOU 확장**: `P_last` 조상성 소비도 U-16-c 격리 스냅샷 기층을 쓰므로, ㉡ 관측과 조상성 조회 사이 graft 삽입·제거(SIMULATED seam)로 `ARTIFACT_MUTATED`↔`ACTIVE` 를 뒤집는 구현은 격리 스냅샷 안 소비로 fail-closed 됨을 함께 본다(격리 클론 픽스처·종수 불변) ⑩ **[v2.18] 타 원격·타 호스트** — 아티팩트/원격이 **계약 핀**(`github.com/kakao-harris-lee/kis_unified_sts`)과 다른 host 또는 owner/repo 를 가리킴(비-GitHub 호스트의 동일 경로 포함) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **host 를 버리는 정규화는 통과시킨다** ⑪ **[v2.19 신설 — 심판 F1] 보호 해제 창(off→merge→on) — 연속성** — **live 로 실행하지 않는다**(실측 픽스처가 서버 보호 설정 변경을 요구하므로): v2.16 (a) 방식의 **«캡처된 응답 위 결정적 술어» seam** 으로 SIMULATED 구성한다. 룰셋 응답에 `updated_at` 이 **최초 착지 `merged_at` 보다 늦은** 캡처를 주입 → **`PREVENTION_CONTINUITY_UNVERIFIABLE` + 비-0**(U-17-c). **classic branch protection 만인 캡처**(`updated_at`·`created_at` 부재) → 같은 값(연속성 판정 불가). **`updated_at`·`created_at` ≤ `merged_at` 캡처** → 그 축 통과(다른 축이 성립하면 `PREVENTION_ACTIVE`). **판별력**: 「진입·완료 두 조회가 둘 다 ACTIVE 면 통과」로 접는 구현은 이 SIMULATED 를 통과시켜 실패한다. **live 는 현행 상태 음성만**(오늘 `main` 은 룰셋 `disabled` 라 애초에 `PREVENTION_INSUFFICIENT`). **소비 시각은 «서버 시간»만**(응답의 `updated_at`·`created_at`·PR `merged_at`) — 커밋 author/committer date 는 클라이언트 공급이라 쓰지 않는다. **정직 표기**: 감사 로그 없이 «머지 시점 강제»의 완전 증명은 불가하므로 이 대조군은 **설정 변경의 관측**만 fail-closed 로 승격한다 ⑫ **[v2.19 신설 — 심판 신규 high] `GH_HOST` override — 정본 host 결속** — **live 실행 가능**(GET-only·환경변수만). 소비자는 계약 핀에서 host 를 파생해 **모든 `gh api` 에 `--hostname <핀 host>` 명시 + 자기 환경 `GH_HOST` 를 핀 host 로 설정**한다. 대조군은 `GH_HOST=<타 host>`(+`GH_ENTERPRISE_TOKEN=dummy`) 주입 후 실행 → **상태값이 override 유무와 «불변»**(조회가 핀 host 에 결속)이거나, 핀 host 도달·인증 불가면 **`PREVENTION_UNVERIFIABLE`**(fail-closed). **override 가 상태값을 바꾸면(특히 타 host 응답으로 `PREVENTION_ACTIVE`) 실패** = host 를 `gh` 환경에 위임하는 구현. **심판 실측 프로브**(`GH_HOST=example.invalid … gh api repos/a/b`, exit 1)가 host 없는 명령의 결함을 재현한 그 클래스이며, T-84 ⑩(remote URL 대조만)은 이 축을 잡지 못한다 ⑬ **[v2.20 신설 — 심판 #1] 비활성 리터럴 변이** — 동일 path/app/head 성공 워크플로 blob 에 두 리터럴(하니스 경로·sha256)을 **비활성 위치**(YAML 주석·`name:`/`env:` 값·`run:` 셸 주석)에만 심고 실제 잡 스텝은 `true` → **구조 YAML 파싱**(주석 제외·`jobs.*.steps[].run` 실행문만·셸 주석 스트립)에서 하니스 경로가 «실행 인자»가 아니고 sha256 이 «대조 대상»이 아니므로 **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **판별력**: v2.19 의 «두 리터럴 grep» 구현은 rc=0 이나 구조 파싱은 red(심판 메모리 픽스처 재현). **하위 케이스(종수 불변)**: ⑬a `echo "…경로…"`(경로가 인자 위치) → 명령-위치 검사로 red · ⑬b `true  # shasum…|grep 957…`(trailing 셸 주석) → 토크나이저가 주석 제거 → red · **⑬c `shasum…|grep 957… || true`(대조는 능동이나 `|| true` 무효화) → «미검출(정직 경계)»** — 정적 파싱·서버 스텝(이름·conclusion)은 런타임 무효화·대조 의미론을 구별 못 함(위조 비용↑·닫지 못함) ⑭ **[v2.20 신설 — 심판 #1] 서버 잡 스텝 부재/실패** — blob 구조는 통과하나 서버 `actions/runs/{run_id}/jobs`(또는 `actions/jobs/{job_id}`) 그 잡 `steps[]` 에 계약 리터럴 «스텝 이름»(`tos-gate: run harness`·`tos-gate: verify harness sha256`)이 **부재**하거나 그 스텝 `conclusion != success` → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **판별력**: blob 만 보고 서버 스텝 실행 기록을 대조 안 하는 구현은 통과 → 서버 스텝 대조는 red.  **정직 경계**: 스텝 이름·결론은 «서버 기록»이지 «그 스텝의 run 내용을 그대로 실행했다»의 증명이 아니다(⑬+⑭ 는 위조 비용을 올리되 GitHub 내부 실행 간극은 안 닫는다) |
+| **T-84** | **U-17 예방 통제 활성 증거** (§12.3.4) | **v2.15 신설 / v2.16 재작성 / [v2.17 재작성 — stop-time BLOCK B3 / v2.19 확장 / v2.20 확장]** — 파라미터화 **14종**. **v2.16 에라타 E2 가 #5 근거만 고치고 이 행을 보지 않아**(S-22) `rulesets=[]`·«머지 커밋 check-runs 0»·«pulls 공집합»이 **같은 턴 실측과 충돌**한 채 남아 있었다 — 행 전체를 재작성한다. ① **live 서버 음성(실측)** — 아티팩트 선언 == 구조 파생(`main`)인 정상 구성에서 `responder=gh` 실조회: `required_status_checks {strict:false, contexts:["test"]}` 이므로 **`PREVENTION_INSUFFICIENT`** · `/rules/branches/main` → `[]`(적용 규칙 0) · `/rulesets` → `[{name:"protect_main", enforcement:"disabled"}]` ⇒ **룰셋은 실재하나 disabled 라 동등물 없음**. **인증된 진짜 음성이며 모의가 아니다**. **[E1 — v2.17 에라타]** 초안은 여기에 «작업 브랜치 → 404 → `PREVENTION_ABSENT`» 를 함께 적었으나, **v2.17 에서 `target_branch` 는 `default_branch` 로 «파생»되므로 그 구성은 ⑤(`TARGET_MISMATCH`)이지 `ABSENT` 가 아니고 실행기로 재현되지 않는다**(증거 실행 적발 — S-22: B1 의 파생 전환이 이 행에 미전파). **«비-default 브랜치 protection → 404»는 «raw probe 관측»으로만 병기**하며 상태값 기대가 아니다 ② **seam 주입(`SIMULATED`)** — `responder` 주입으로 `PREVENTION_ACTIVE`·`INSUFFICIENT`·`UNVERIFIABLE` 모의. **기본 responder 는 `gh api`**. **양성은 운영자가 보호를 설정하기 전까지 실측 불가**임을 숨기지 않는다. **진정성은 §12.3.4 «진실 원천» 절이 «판정 소비자 자신의 조회»로 닫는다** ③ **리비전 검증(실측)** — `/commits/{d}/pulls` → 착지 PR → PR `head.sha` check-runs. 실측: `origin/main` 착지 `11e382fc` 의 check-runs **15건**(push 트리거 워크플로)·`pulls` = PR #636(merged·base main), PR head `7656259d` check-runs 5건에 **`tos-gate` 없음** ⇒ **`PREVENTION_UNVERIFIED_REVISION`**. 미푸시 커밋 → 422 ⇒ `PREVENTION_UNVERIFIABLE` · 푸시됐으나 PR 없는 `be98f075` → `pulls` `[]` ⇒ UNVERIFIED_REVISION ④ **보호 해제 후(stub)** — «countersign 시 ACTIVE → 이후 해제» 후 완료 판정 재조회가 `ABSENT`/`INSUFFICIENT` ⑤ **[v2.17 신설] target 불일치** — 아티팩트가 **다른 저장소/브랜치**를 선언(예: 보호가 걸린 타 repo, 또는 default 아닌 브랜치) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **`D = ∅` 에서도 red 여야 한다** — v2.16 은 이 구성에서 **임의 대상의 보호만으로 ACTIVE** 를 냈다 ⑥ **[v2.17 신설] `app_id` 위조** — `tos-gate` 라는 이름에 `conclusion: success` 이지만 **`app.id` 가 게이트 앱(기본 `15368`)이 아닌** check-run 을 seam 으로 주입 → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **이름만 보는 구현은 통과시키므로 실패한다** ⑦ **[v2.18] 타 앱 고정 required check** — 보호는 있고 `contexts` 에 `tos-gate` 도 있으나 `required_status_checks.checks[]` 의 그 컨텍스트 `app_id` 가 **Actions 가 아닌 앱**(예 99999) → **`PREVENTION_INSUFFICIENT`** + 비-0. **v2.17 은 이름만 봐서 `prot_ok` 를 냈고 `D=∅` 이면 그대로 진입 승인**됐다(심판이 실행기 술어로 재현) ⑧ **[v2.18] same-app wrong-workflow** — **같은 Actions app id** 로 **다른 워크플로**의 잡을 `tos-gate` 로 이름 지어 success 게시 → workflow run 의 `path` 가 `.github/workflows/tos-gate.yml` 이 아니므로 **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **app id 만 보는 구현은 통과시킨다**(실측: PR #636 head 의 5 run 이 전부 동일 app id) ⑨ **[v2.18] 아티팩트 사후 편집** — `P` → D0-A 착수 → 아티팩트 편집 → **`PREVENTION_ARTIFACT_MUTATED`** + 비-0. **`P_last` 를 쓰지 않고 «최초 도입 P» 만 보는 구현은 통과시킨다**  **[v2.20 — 심판 #3] 부모신뢰 TOCTOU 확장**: `P_last` 조상성 소비도 U-16-c 격리 스냅샷 기층을 쓰므로, ㉡ 관측과 조상성 조회 사이 graft 삽입·제거(SIMULATED seam)로 `ARTIFACT_MUTATED`↔`ACTIVE` 를 뒤집는 구현은 격리 스냅샷 안 소비로 fail-closed 됨을 함께 본다(격리 클론 픽스처·종수 불변) ⑩ **[v2.18] 타 원격·타 호스트** — 아티팩트/원격이 **계약 핀**(`github.com/kakao-harris-lee/kis_unified_sts`)과 다른 host 또는 owner/repo 를 가리킴(비-GitHub 호스트의 동일 경로 포함) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **host 를 버리는 정규화는 통과시킨다** ⑪ **[v2.19 신설 — 심판 F1] 보호 해제 창(off→merge→on) — 연속성** — **live 로 실행하지 않는다**(실측 픽스처가 서버 보호 설정 변경을 요구하므로): v2.16 (a) 방식의 **«캡처된 응답 위 결정적 술어» seam** 으로 SIMULATED 구성한다. 룰셋 응답에 `updated_at` 이 **최초 착지 `merged_at` 보다 늦은** 캡처를 주입 → **`PREVENTION_CONTINUITY_UNVERIFIABLE` + 비-0**(U-17-c). **classic branch protection 만인 캡처**(`updated_at`·`created_at` 부재) → 같은 값(연속성 판정 불가). **`updated_at`·`created_at` ≤ `merged_at` 캡처** → 그 축 통과(다른 축이 성립하면 `PREVENTION_ACTIVE`). **판별력**: 「진입·완료 두 조회가 둘 다 ACTIVE 면 통과」로 접는 구현은 이 SIMULATED 를 통과시켜 실패한다. **live 는 현행 상태 음성만**(오늘 `main` 은 룰셋 `disabled` 라 애초에 `PREVENTION_INSUFFICIENT`). **소비 시각은 «서버 시간»만**(응답의 `updated_at`·`created_at`·PR `merged_at`) — 커밋 author/committer date 는 클라이언트 공급이라 쓰지 않는다. **정직 표기**: 감사 로그 없이 «머지 시점 강제»의 완전 증명은 불가하므로 이 대조군은 **설정 변경의 관측**만 fail-closed 로 승격한다 ⑫ **[v2.19 신설 — 심판 신규 high] `GH_HOST` override — 정본 host 결속** — **live 실행 가능**(GET-only·환경변수만). 소비자는 계약 핀에서 host 를 파생해 **모든 `gh api` 에 `--hostname <핀 host>` 명시 + 자기 환경 `GH_HOST` 를 핀 host 로 설정**한다. 대조군은 `GH_HOST=<타 host>`(+`GH_ENTERPRISE_TOKEN=dummy`) 주입 후 실행 → **상태값이 override 유무와 «불변»**(조회가 핀 host 에 결속)이거나, 핀 host 도달·인증 불가면 **`PREVENTION_UNVERIFIABLE`**(fail-closed). **override 가 상태값을 바꾸면(특히 타 host 응답으로 `PREVENTION_ACTIVE`) 실패** = host 를 `gh` 환경에 위임하는 구현. **심판 실측 프로브**(`GH_HOST=example.invalid … gh api repos/a/b`, exit 1)가 host 없는 명령의 결함을 재현한 그 클래스이며, T-84 ⑩(remote URL 대조만)은 이 축을 잡지 못한다 ⑬ **[v2.20 신설 — 심판 #1] 비활성 리터럴 변이** — 동일 path/app/head 성공 워크플로 blob 에 두 리터럴(하니스 경로·sha256)을 **비활성 위치**(YAML 주석·`name:`/`env:` 값·`run:` 셸 주석)에만 심고 실제 잡 스텝은 `true` → **구조 YAML 파싱**(주석 제외·`jobs.*.steps[].run` 실행문만·셸 주석 스트립)에서 하니스 경로가 «실행 인자»가 아니고 sha256 이 «대조 대상»이 아니므로 **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **판별력**: v2.19 의 «두 리터럴 grep» 구현은 rc=0 이나 구조 파싱은 red(심판 메모리 픽스처 재현). **하위 케이스(종수 불변)**: **⑬ 기준선(양성·[v2.20 에라타 ⓐ/M-3 대조])** `bash tools/tos_entry_harness.sh`(인터프리터 실행)는 red 가 «아니어야» 한다 — «첫 단어» 문자 구현의 과잉 차단을 잡는 대조 · ⑬a `echo "…경로…"`(경로가 인자 위치) → 명령-위치 검사로 red · ⑬b `true  # shasum…|grep 957…`(trailing 셸 주석) → 토크나이저가 주석 제거 → red · **⑬c `shasum…|grep 957… || true`(대조는 능동이나 `|| true` 무효화) → «미검출(정직 경계)»** — 정적 파싱·서버 스텝(이름·conclusion)은 런타임 무효화·대조 의미론을 구별 못 함(위조 비용↑·닫지 못함) ⑭ **[v2.20 신설 — 심판 #1] 서버 잡 스텝 부재/실패** — blob 구조는 통과하나 서버 `actions/runs/{run_id}/jobs`(또는 `actions/jobs/{job_id}`) 그 잡 `steps[]` 에 계약 리터럴 «스텝 이름»(`tos-gate: run harness`·`tos-gate: verify harness sha256`)이 **부재**하거나 그 스텝 `conclusion != success` → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **판별력**: blob 만 보고 서버 스텝 실행 기록을 대조 안 하는 구현은 통과 → 서버 스텝 대조는 red.  **정직 경계**: 스텝 이름·결론은 «서버 기록»이지 «그 스텝의 run 내용을 그대로 실행했다»의 증명이 아니다(⑬+⑭ 는 위조 비용을 올리되 GitHub 내부 실행 간극은 안 닫는다) |
@@ -4394 +4394 @@ closed»로 오분류) → **E15**: 결합을 «`--show-toplevel` 루트 결합
-**v2.20 신규 증거는 동결 후에 만든다**(S-24).  직전 층(v2.19) 증거는 스탬프
+**v2.20 신규 증거 = `d101eb63`**(`U17`/`U16-…-V220.md` — 기대 전건 일치·문언 에라타 ⓐⓑⓒ 적발·fail-open 0)이며, 그 에라타는 변경 이력 v2.20 에라타 절이 유일 소스다(S-24).  직전 층(v2.19) 증거는 스탬프
@@ -5461 +5461 @@ TOS 게이트 체크 이름  아티팩트가 **파라미터로 선언**하되 **
-                             그 `run:` 토큰열에서 **`tools/tos_entry_harness.sh` 가 파이프라인 한 명령의 «명령 위치»(첫 단어)에 실재**(`echo "…경로…"` 같은 «인자 위치»는 미충족)
+                             그 `run:` 토큰열에서 **`tools/tos_entry_harness.sh` 가 «실행 위치»에 실재** — 단순 명령의 «명령 위치»(첫 단어)이거나 **인터프리터**(계약 고정 리터럴 집합 `bash`·`sh`·`zsh`·`dash`·`ksh` 및 이들의 절대경로·`env`[→`env bash <스크립트>`])의 **첫 비-옵션 인자(스크립트 경로)** — `bash tools/tos_entry_harness.sh`·`./tools/tos_entry_harness.sh` 는 충족, `echo`/`printf`/`cat` 등 «출력 명령의 인자»는 미충족(⑬a).  **[v2.20 에라타 ⓐ — M-3] «첫 단어» 문자 구현은 관용 표기 `bash tools/…` 를 배제해 정상 워크플로를 red 로 만든다 — 과잉 차단은 «정직한 게이트를 못 쓰게 하는 fail-closed 결함»이다(측정기가 대상보다 좁으면 증거가 아니다·S-15 계열)**
@@ -7125 +7125 @@ c_APP(a) = { x ⊑ HEAD :  a ∈ rows(x:LEDGER)  ∧  ∀ p ∈ parents(x): a 
-               canary — `--local` 폴백·`--all` 번들 오용을 잡는다). (c) 판정 소비자 «자신의 환경 위조»
+               canary — `--local` 폴백·`--all` 번들 오용을 잡는다).  **[v2.20 에라타 ⓑ — M-1] 스냅샷 진입 «후» 모든 파생 경로(`git rev-parse --git-path`·`--show-toplevel`·grafts/replace canary)는 «스냅샷 안에서» 재파생한다 — 진입 «전»(원 저장소) 값·캐시된 결합 base 재사용 금지**(cwd 이동 후 캐시된 base 로 원 저장소 경로를 검사하면 스냅샷이 오염돼도 «거짓 ABSENT»=fail-open·v2.19 E15 극성 재발 표면). (c) 판정 소비자 «자신의 환경 위조»
@@ -7129 +7129 @@ c_APP(a) = { x ⊑ HEAD :  a ∈ rows(x:LEDGER)  ∧  ∀ p ∈ parents(x): a 
-           성립하는 canary»가 된다.  **[극성 규율]** (i) ㉡ 을 «조상성 조회 직전·직후 2회 + grafts 파일 sha
+           성립하는 canary»가 된다 — **단 [v2.20 에라타 ⓒ — N-1] «㉢ 얕은 경계 귀속분은 먼저 제외»**한다: 원본이 얕으면 스냅샷도 얕음을 «상속»하고 얕은 경계는 `cat-file` 부모 有 vs `%P` ∅ 로 ㉠ 불일치를 «정상적으로» 내므로(아래 E12), «㉢ 국소 귀속 후 «남는» ㉠≠`%P`»만 기층 오염이다 — 이 국소화 없이 «문자» 구현하면 참 사유(`|c_APP|=0`·`PROVENANCE_UNVERIFIABLE`)를 «기층 오염»으로 덮는다(양쪽 fail-closed·사유만 상이).  **[극성 규율]** (i) ㉡ 을 «조상성 조회 직전·직후 2회 + grafts 파일 sha
```

### 1-2. s24-proof 2층 (기계 생성 구간 + 리터럴 앵커 절)

실행기: `s24-proof-ae.py` sha256 `c11fb0eb263de6464cd06f42393b992b2c7f4079ddcb2eba05539e5da1b9df36` (102행). ① 층은 hunk 를 **자동 추출**해 그 여집합을 양 blob 에서 sha256 대조하므로 «구간 누락»이 구조적으로 불가능하고, ② 층은 각 절을 **각 blob 안에서 리터럴 앵커로** 찾는다(행 번호 하드코딩 금지).

```text
blob(3d17ea66:docs/plans/2026-08-12-tos-phase0-completion-contract-design.md) = 5d6044e904e9c2e74bf4abb661b3b4b47f044689  행수=7494
blob(ae842cce:docs/plans/2026-08-12-tos-phase0-completion-contract-design.md) = 9bfa21aa957b0b001a2f4daf7d26f472619175a5  행수=7494

① 무변경 구간 증명 — hunk 7개 (기계 추출): -125,1 +125,1 · -208,1 +208,1 · -2885,1 +2885,1 · -4394,1 +4394,1 · -5461,1 +5461,1 · -7125,1 +7125,1 · -7129,1 +7129,1
   hunk 여집합 구간별 sha256 대조 (구간을 손으로 적지 않는다 — 누락 불가):
   구간#1: old[1..124] vs new[1..124]  124행/124행  a38f5ce3f5847c4a / a38f5ce3f5847c4a → 동일
   구간#2: old[126..207] vs new[126..207]  82행/82행  3996c5209fb2adec / 3996c5209fb2adec → 동일
   구간#3: old[209..2884] vs new[209..2884]  2676행/2676행  4559adc8b9442c45 / 4559adc8b9442c45 → 동일
   구간#4: old[2886..4393] vs new[2886..4393]  1508행/1508행  5335b8ddbfd9b2a7 / 5335b8ddbfd9b2a7 → 동일
   구간#5: old[4395..5460] vs new[4395..5460]  1066행/1066행  0e59c5a2cba09cd2 / 0e59c5a2cba09cd2 → 동일
   구간#6: old[5462..7124] vs new[5462..7124]  1663행/1663행  0817cea92b89cfb4 / 0817cea92b89cfb4 → 동일
   구간#7: old[7126..7128] vs new[7126..7128]  3행/3행  f9c556a443f5f98b / f9c556a443f5f98b → 동일
   구간#8: old[7130..7495] vs new[7130..7495]  366행/366행  fddca51b1a0a68b3 / fddca51b1a0a68b3 → 동일
   ⇒ 변경이 «닿지 않은» 구간 차이 = 0건 (0 이어야 한다)

② 명명 절 증명 — 각 blob 안에서 «리터럴 앵커»로 위치를 찾는다(행 번호 하드코딩 금지)
   절                                              old 행   new 행  판정
  [닿음]
   (b)③ 하니스 실행 위치 문장                             5461    5461  상이 (기대 상이) ✅   sha256 8139157b05ce / fc9347dae0b9
   T-84 ⑬ 행(기준선 양성 병기)                           2885    2885  상이 (기대 상이) ✅   sha256 c48b054b9159 / a91601940f7f
   스냅샷 정직 경계 (b) — 재파생 강제                        7125    7125  상이 (기대 상이) ✅   sha256 9268e783a937 / 75137d86434b
   canary ㉢ 선-제외 문장                              7129    7129  상이 (기대 상이) ✅   sha256 5e177fc5c00b / ad79f9d839ea
   심사 이력 v2.20 행 (1번째 출현)                         125     125  상이 (기대 상이) ✅   sha256 f5c159f6f895 / ccc4b34f07af
   변경 이력 v2.20 행 (2번째 출현)                         208     208  상이 (기대 상이) ✅   sha256 4e4b2d261607 / 4ad87e42ff89
   (B) 주 — v2.20 신규 증거                           4394    4394  상이 (기대 상이) ✅   sha256 401b2665a4c3 / c2a9cbb92696
  [닿지 않음]
   하니스 §12.3.4-R 블록 첫 줄                          4654    4654  동일 (기대 동일) ✅   sha256 e2b37d0fbeeb / e2b37d0fbeeb
   하니스 §12.3.4-R 블록 끝 줄                          4754    4754  동일 (기대 동일) ✅   sha256 7c74c97e2e41 / 7c74c97e2e41
   T-82 행 (종수 20)                                2935    2935  동일 (기대 동일) ✅   sha256 a9bd7743aef2 / a9bd7743aef2
   T-81 행 (종수 19)                                2934    2934  동일 (기대 동일) ✅   sha256 6eeb704aa338 / 6eeb704aa338
   U-17-c 상태 10값 정의                              5659    5659  동일 (기대 동일) ✅   sha256 a4770d3b3cef / a4770d3b3cef
   (a) 술어 — required_status_checks               5337    5337  동일 (기대 동일) ✅   sha256 f6e5d2eca7fb / f6e5d2eca7fb
   c_APP 구조 정의 수식                                7084    7084  동일 (기대 동일) ✅   sha256 dc53f88be2ef / dc53f88be2ef
   스냅샷 «단일 방법» 문장                                7108    7108  동일 (기대 동일) ✅   sha256 edb7664a2e35 / edb7664a2e35
   서버 잡 스텝 대조 절 (2)                              5477    5477  동일 (기대 동일) ✅   sha256 45631dd8def7 / 45631dd8def7
   ㉠ 주 판별 문장                                     7133    7133  동일 (기대 동일) ✅   sha256 8b10274d7a71 / 8b10274d7a71
   E12 관할 문장                                     7138    7138  동일 (기대 동일) ✅   sha256 0a6efe99290f / 0a6efe99290f
   심사 이력 v2.18 행                                  123     123  동일 (기대 동일) ✅   sha256 0f4a114ec9a0 / 0f4a114ec9a0
   U-16-d 전순서 12단                                 209     209  동일 (기대 동일) ✅   sha256 22c12092499b / 22c12092499b
   T-84 ⑬c 정직 경계 문장                              5474    5474  동일 (기대 동일) ✅   sha256 fd94dc9f1e38 / fd94dc9f1e38

③ 하니스 §12.3.4-R 블록(:4654-4754) sha256 — old=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
                                              new=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
   계약 리터럴 957bf49d… 와 일치? old=True new=True · 양자 byte-동일? True
```

**판독**: 변경이 닿지 않은 구간 차이 **0건** · 닿은 절 7개(모두 «상이» 기대와 일치) · 닿지 않은 절 13개(모두 «동일») · 하니스 블록 byte-동일.
→ 따라서 **비영향 변이는 `d101eb63` 증거 그대로 결속**된다(재실행 불요). 아래 §2 는 **영향 변이만** 재실행한 기록이다.

## 2. S-24 ② — 영향 변이 재실행

드라이버 2종 · 대조군 3종(판정 실행기 대비 «한 축»만):

| 파일 | sha256 | 행수 | 역할 |
| --- | --- | --- | --- |
| `t8xae84.sh` | `d2e5b7b5bb3c2d015e333f4250f26672a0af653c614f2e447496f6f05ff108b0` | 214 | U-17 축 — ⓐ 실행 위치 · ⓑ 스냅샷 재파생 |
| `t8xae82.sh` | `c2530cd4ca878e3b5b2598c4e367a61bc9d7878036e14160f5a853a6c35f7008` | 130 | U-16 축 — ⓑ 스냅샷 재파생 · ⓒ ㉢ 선-제외 |
| `u17-cachedbase-ae.sh` | `5248310c786c17d4daaf3fed8ecd1a09a4a1afefb53661653241a84f0ad45a57` | 480 | 대조군 ⓑ(U-17) — 결합 base 캐시(계약 :7125 금지 구현) |
| `u16-cachedbase-ae.py` | `1b2fd7991aefb206c6aed14d712299f44a6b67fa00ecc501a3a56a22063f1d76` | 594 | 대조군 ⓑ(U-16) — 결합 base 캐시 |
| `u16-canary-literal-v220.py` | `5b5f7bc9ee949f0393175fa3a73e27da2854562fb62ee4d5912307d3fa6b3f46` | 589 | 대조군 ⓒ — canary ㉠ «문자» 구현(㉢ 국소화 없음) |

### 2-1. ⓐ [`ae842cce:5461`] 실행 위치 = 첫 단어 ∪ 인터프리터 고정 리터럴 집합의 첫 비-옵션 인자

```text
########## ⓐ-1 [계약 ae842cce:5461] 실행 위치 술어 — 인터프리터 고정 리터럴 집합 · 첫 비-옵션 인자 ##########
run: 실행문             계약 기대(ae842cce:5461)                   실측
bash tools/tos_entry_harness.sh BLOB_OK (인터프리터 첫 비-옵션 인자) BLOB_OK
./tools/tos_entry_harness.sh BLOB_OK (명령 위치)                        BLOB_OK
env bash tools/tos_entry_harness.sh BLOB_OK (env → bash → 스크립트)        BLOB_OK
/bin/bash tools/tos_entry_harness.sh BLOB_OK (절대경로 인터프리터)         BLOB_OK
sh -e tools/tos_entry_harness.sh BLOB_OK (첫 «비-옵션» 인자)            BLOB_OK
echo tools/tos_entry_harness.sh UNVERIFIED_REVISION (출력 명령 인자 · ⑬a) UNVERIFIED_REVISION
printf '%s' tools/tos_entry_harness.sh UNVERIFIED_REVISION (출력 명령 인자 · ⑬a) UNVERIFIED_REVISION
cat tools/tos_entry_harness.sh UNVERIFIED_REVISION (출력 명령 인자 · ⑬a) UNVERIFIED_REVISION
python tools/tos_entry_harness.sh UNVERIFIED_REVISION (집합 «밖» 인터프리터) UNVERIFIED_REVISION
-- 실행기 코드의 고정 집합 원문 --
  27:INTERP   = {"bash", "sh", "zsh", "dash", "ksh"}

########## ⓐ-2 픽스처 저장소 (P → W → d) — e2e 3종은 blob 만 바뀐다 ##########
W(PR head)=2812f2858077d50fbdef5c7f718c84e2d60a1fe0  d=9cca068ae0d085a950a20524650acb7cf2292f70
```

| e2e (실행기 전체 · SIMULATED seam) | 계약 기대 | 실측 | rc |
| --- | --- | --- | --- |
| `run: bash tools/tos_entry_harness.sh` (에라타 ⓐ 가 **양성**으로 병기) | `PREVENTION_ACTIVE` | **`PREVENTION_ACTIVE`** | 0 ✅ |
| `run: ./tools/tos_entry_harness.sh` | `PREVENTION_ACTIVE` | **`PREVENTION_ACTIVE`** | 0 ✅ |
| `run: python tools/tos_entry_harness.sh` (집합 **밖** 인터프리터) | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION`** | 1 ✅ |
| 회귀 ⑬a (`echo` 인자) | `UNVERIFIED_REVISION` | 동일 | 1 ✅ 불변 |
| 회귀 ⑭ (서버 스텝 부재) | `UNVERIFIED_REVISION` | 동일 | 1 ✅ 불변 |

→ **`bash tools/…` 가 red 가 아님**을 e2e 로 고정했다(v2.20 증거 M-3 이 지적한 과잉 차단이 문언에서 닫혔다). 술어의 고정 집합은 코드 원문 `INTERP = {"bash", "sh", "zsh", "dash", "ksh"}` + `env`·절대경로(basename) 처리이며 `python` 은 **집합 밖**이라 미충족 — 계약이 말하는 값 그대로다.

### 2-2. ⓑ [`ae842cce:7125`] 스냅샷 진입 «후» 재파생 vs 캐시 base

오염 주입은 **shim** 으로 `git clone` 직후 «스냅샷 안»에 `grafts` 를 심는다(계약 정직 경계 (b) 가 잡아야 하는 «`--local` 폴백·`--all` 번들 오용» 등가물). **원 저장소는 끝까지 깨끗**하다.

| 축 | 오염 종류 | 구현 | canary grafts 관측 | 상태값 | rc | 판독 |
| --- | --- | --- | --- | --- | --- | --- |
| U-17 | — (정직) | 판정 | ABSENT | `PREVENTION_LATE` | 1 | 기준선 |
| U-17 | 유효 graft(㉠ 가시) | **캐시 base** | **`grafts=no`(원 저장소 경로 · 거짓 ABSENT)** | `PREVENTION_UNVERIFIABLE` | 1 | ㉠ 가 대신 잡음 |
| U-17 | 유효 graft | 판정(재파생) | `grafts=yes`(스냅샷 경로) | `PREVENTION_UNVERIFIABLE` | 1 | 두 겹 다 발화 |
| U-17 | **㉠-불가시**(부재 커밋 주어) | **캐시 base** | **`grafts=no`** | `PREVENTION_LATE` | 1 | **오염 신호 상실**(상태는 정직값) |
| U-17 | ㉠-불가시 | 판정(재파생) | `grafts=yes` | `PREVENTION_UNVERIFIABLE` | 1 | **㉡ 단독 발화** — 에라타 ⓑ 가 복구한 그 겹 |
| U-16 | — (정직) | 판정 | ABSENT | `PROVENANCE_UNVERIFIABLE`(g6 C_R=∅) | 1 | 기준선 |
| U-16 | 유효 graft | **캐시 base** | **`grafts=False` ㉠불일치=1** | `PROVENANCE_UNVERIFIABLE`(기층 오염) | 1 | ㉠ 가 대신 잡음 |
| U-16 | 유효 graft | 판정(재파생) | `grafts=True` ㉠불일치=1 | `PROVENANCE_UNVERIFIABLE`(기층 오염) | 1 | 두 겹 다 |
| U-16 | **㉠-불가시** | **캐시 base** | **`grafts=False` ㉠불일치=0** | `PROVENANCE_UNVERIFIABLE`(**정직값** g6 C_R=∅) | 1 | **오염 신호 상실** |
| U-16 | ㉠-불가시 | 판정(재파생) | `grafts=True` ㉠불일치=0 | `PROVENANCE_UNVERIFIABLE`(**기층 오염**) | 1 | **㉡ 단독 발화** |

**정직한 등급 조정 (v2.20 증거 M-1 의 «fail-open» 표현을 이 자리에서 정밀화한다)**: 캐시 base 는 **거짓 ABSENT 를 실제로 만든다**(관측 확정). 다만 «유효한» 오염은 **㉠(구조 재파생)이 독립으로 잡으므로** 이 실행기 구성에서 **종단 상태의 fail-open 은 도달하지 않았다** — ⓑ 가 복구하는 것은 **다층 방어의 한 겹(㉡ 단독 검출 사례)**이다. 그 «한 겹»이 실제로 유일 검출자가 되는 구성(㉠-불가시 오염)을 만들어 **판정 실행기만 발화**함을 실증했다(위 4·5·9·10행).

### 2-3. ⓒ [`ae842cce:7129`] canary — ㉢ 얕은 경계 귀속분 «먼저 제외»

```text
########## ⓒ 얕은 원본 → 얕은 스냅샷: ㉢ 국소 귀속 후 «남는» ㉠ 만 기층 오염 (계약 ae842cce:7129) ##########
  원본 is-shallow=false · 얕은 클론 is-shallow=true · rev-list=1

########## ⓒ-1 판정 실행기 — ㉢ 국소 귀속 후 판정 ⇒ PROVENANCE_UNVERIFIABLE(2) · 사유 = |c_APP|=0 ##########
```

| 구현 | canary 원문 | 상태값 | 사유 | 판독 |
| --- | --- | --- | --- | --- |
| 판정 실행기 (㉢ 선-제외) | `㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 1건 · E12 관할)` | `PROVENANCE_UNVERIFIABLE`(2) | **`\|c_APP\|=0` (도입 지점 파생 불가)** | 계약 기대 사유 ✅ |
| 대조군 (문언 «문자» 구현) | `㉠ 불일치 전역 1건 (국소 귀속 0건)` | `PROVENANCE_UNVERIFIABLE`(2) | `[격리 스냅샷 canary] 기층 오염` | 극성 동일·**사유 오귀속** ✅ 실증 |

### 2-4. 회귀 불변

| 케이스 | 기대 | 실측 | rc |
| --- | --- | --- | --- |
| U-17 ⑬a (`echo` 인자) | `UNVERIFIED_REVISION` | 동일 | 1 ✅ |
| U-17 ⑭ (서버 스텝 부재) | `UNVERIFIED_REVISION` | 동일 | 1 ✅ |
| U-16 ⑮ (R∥A) | `APPROVAL_ORDER_INVALID` | 동일 | 1 ✅ |
| U-16 ⑯ (선형 반복) | `NO_ROWS_CLEAR` | 동일 | 0 ✅ |

## 3. 실행 기록 (stdout 전문 · rc 포함)

### 3-1. `bash t8xae84.sh` (U-17 축) (525행)

```text
t8xae84_utc=2026-08-19T08:28:04Z
sha256(u17-verify-v220.sh)=67d636ce4ac4ff0b4a3da06d24b5551748c7408d3325aebd9f5ac56b264ed101
sha256(wfstruct-v220.py)=792aaa1e73d8ef854c7478577b0732191065b961802f5988687cc03299760dc1
sha256(u17-cachedbase-ae.sh)=5248310c786c17d4daaf3fed8ecd1a09a4a1afefb53661653241a84f0ad45a57
-- 대조군 ⓑ diff (판정 실행기 대비 한 축) --
  82,84c82,83
  < # [v2.20 D-γ] 결합 base 를 «호출 시점»에 파생한다 — 격리 스냅샷으로 cwd 가 바뀐 뒤 캐시된 TOPLEVEL 을 쓰면
  < #   스냅샷의 grafts 를 «원 저장소 경로»로 검사해 «거짓 ABSENT» 가 된다(E15 극성 규율의 재발 표면).
  < gitpath() { local v t; v=$(git rev-parse --git-path "$1" 2>/dev/null); t=$(git rev-parse --show-toplevel 2>/dev/null || printf '%s' "$TOPLEVEL"); case "$v" in /*) printf '%s' "$v";; "") printf '';; *) printf '%s/%s' "$t" "$v";; esac; }
  ---
  > # [대조군 ⓑ — 판정용 아님] 결합 base 를 «진입 전»(원 저장소) 값으로 캐시 — 계약 ae842cce:7125 가 금지한 그 구현
  > gitpath() { local v; v=$(git rev-parse --git-path "$1" 2>/dev/null); case "$v" in /*) printf '%s' "$v";; "") printf '';; *) printf '%s/%s' "$TOPLEVEL" "$v";; esac; }
git=git version 2.38.0 · gh=gh version 2.93.0 (2026-05-27)

########## ⓐ-1 [계약 ae842cce:5461] 실행 위치 술어 — 인터프리터 고정 리터럴 집합 · 첫 비-옵션 인자 ##########
run: 실행문             계약 기대(ae842cce:5461)                   실측
bash tools/tos_entry_harness.sh BLOB_OK (인터프리터 첫 비-옵션 인자) BLOB_OK
./tools/tos_entry_harness.sh BLOB_OK (명령 위치)                        BLOB_OK
env bash tools/tos_entry_harness.sh BLOB_OK (env → bash → 스크립트)        BLOB_OK
/bin/bash tools/tos_entry_harness.sh BLOB_OK (절대경로 인터프리터)         BLOB_OK
sh -e tools/tos_entry_harness.sh BLOB_OK (첫 «비-옵션» 인자)            BLOB_OK
echo tools/tos_entry_harness.sh UNVERIFIED_REVISION (출력 명령 인자 · ⑬a) UNVERIFIED_REVISION
printf '%s' tools/tos_entry_harness.sh UNVERIFIED_REVISION (출력 명령 인자 · ⑬a) UNVERIFIED_REVISION
cat tools/tos_entry_harness.sh UNVERIFIED_REVISION (출력 명령 인자 · ⑬a) UNVERIFIED_REVISION
python tools/tos_entry_harness.sh UNVERIFIED_REVISION (집합 «밖» 인터프리터) UNVERIFIED_REVISION
-- 실행기 코드의 고정 집합 원문 --
  27:INTERP   = {"bash", "sh", "zsh", "dash", "ksh"}

########## ⓐ-2 픽스처 저장소 (P → W → d) — e2e 3종은 blob 만 바뀐다 ##########
W(PR head)=2812f2858077d50fbdef5c7f718c84e2d60a1fe0  d=9cca068ae0d085a950a20524650acb7cf2292f70

########## ⓐ-3 e2e 기준선 «bash tools/tos_entry_harness.sh» ⇒ PREVENTION_ACTIVE (에라타 ⓐ 가 «양성»으로 병기한 그 표기) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 9cca068 2026-08-19T17:28:05+09:00 D0-A: introduce config/tos_completion.yaml
  * 2812f28 2026-08-19T17:28:05+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 4bdcd2d 2026-08-19T17:28:04+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 090059d 2026-08-19T17:28:04+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/bashcall bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=9cca068ae0d085a950a20524650acb7cf2292f70
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.lfnFjNCnnF/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=9cca068ae0d085a950a20524650acb7cf2292f70 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.lfnFjNCnnF/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/bashcall capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.DLAmMUzQAZ
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/bashcall — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.lfnFjNCnnF/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.lfnFjNCnnF/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T08:28:06Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T08:28:06Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T08:28:06Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T08:28:06Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T08:28:06Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T08:28:06Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[4bdcd2df11bcac707d2778663cffab1159387acb ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[4bdcd2df11bcac707d2778663cffab1159387acb ] |D|=1 D=[9cca068ae0d085a950a20524650acb7cf2292f70 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.lfnFjNCnnF/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/9cca068ae0d085a950a20524650acb7cf2292f70/pulls  utc=2026-08-19T08:28:07Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/2812f2858077d50fbdef5c7f718c84e2d60a1fe0/check-runs  utc=2026-08-19T08:28:07Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T08:28:08Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T08:28:08Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=2812f2858077d50fbdef5c7f718c84e2d60a1fe0  utc=2026-08-19T08:28:08Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@2812f2858077d50fbdef5c7f718c84e2d60a1fe0 (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T08:28:08Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 2812f2858077d50fbdef5c7f718c84e2d60a1fe0:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=9cca068ae0d085a950a20524650acb7cf2292f70 head=2812f2858077d50fbdef5c7f718c84e2d60a1fe0 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/bashcall
u17_rc=0

########## ⓐ-4 e2e «./tools/tos_entry_harness.sh» ⇒ PREVENTION_ACTIVE ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 9cca068 2026-08-19T17:28:05+09:00 D0-A: introduce config/tos_completion.yaml
  * 2812f28 2026-08-19T17:28:05+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 4bdcd2d 2026-08-19T17:28:04+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 090059d 2026-08-19T17:28:04+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/dotslash bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=9cca068ae0d085a950a20524650acb7cf2292f70
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.o6lMPqXjke/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=9cca068ae0d085a950a20524650acb7cf2292f70 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.o6lMPqXjke/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/dotslash capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.nvCesgeREg
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/dotslash — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.o6lMPqXjke/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.o6lMPqXjke/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T08:28:10Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T08:28:10Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T08:28:10Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T08:28:10Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T08:28:10Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T08:28:10Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[4bdcd2df11bcac707d2778663cffab1159387acb ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[4bdcd2df11bcac707d2778663cffab1159387acb ] |D|=1 D=[9cca068ae0d085a950a20524650acb7cf2292f70 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.o6lMPqXjke/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/9cca068ae0d085a950a20524650acb7cf2292f70/pulls  utc=2026-08-19T08:28:11Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/2812f2858077d50fbdef5c7f718c84e2d60a1fe0/check-runs  utc=2026-08-19T08:28:11Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T08:28:11Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T08:28:11Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=2812f2858077d50fbdef5c7f718c84e2d60a1fe0  utc=2026-08-19T08:28:11Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0c2ab13a033f4096d304f9a72b441bd4a9f8f9fc", "size": 377, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IC4vdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQ=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@2812f2858077d50fbdef5c7f718c84e2d60a1fe0 (encoding=base64 size=377):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: ./tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = './tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['./tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['./tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (명령 위치 = ./tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = True (명령 위치 = ./tools/tos_entry_harness.sh)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T08:28:12Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 2812f2858077d50fbdef5c7f718c84e2d60a1fe0:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=9cca068ae0d085a950a20524650acb7cf2292f70 head=2812f2858077d50fbdef5c7f718c84e2d60a1fe0 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/dotslash
u17_rc=0

########## ⓐ-5 e2e «python tools/tos_entry_harness.sh» (집합 밖 인터프리터) ⇒ PREVENTION_UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 9cca068 2026-08-19T17:28:05+09:00 D0-A: introduce config/tos_completion.yaml
  * 2812f28 2026-08-19T17:28:05+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 4bdcd2d 2026-08-19T17:28:04+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 090059d 2026-08-19T17:28:04+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/python bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=9cca068ae0d085a950a20524650acb7cf2292f70
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.NaIe3Y9mdl/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=9cca068ae0d085a950a20524650acb7cf2292f70 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.NaIe3Y9mdl/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/python capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.rKAXEpVcOj
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/python — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.NaIe3Y9mdl/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.NaIe3Y9mdl/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T08:28:13Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T08:28:13Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T08:28:13Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T08:28:13Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T08:28:14Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T08:28:14Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[4bdcd2df11bcac707d2778663cffab1159387acb ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[4bdcd2df11bcac707d2778663cffab1159387acb ] |D|=1 D=[9cca068ae0d085a950a20524650acb7cf2292f70 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.NaIe3Y9mdl/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/9cca068ae0d085a950a20524650acb7cf2292f70/pulls  utc=2026-08-19T08:28:15Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/2812f2858077d50fbdef5c7f718c84e2d60a1fe0/check-runs  utc=2026-08-19T08:28:15Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T08:28:15Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T08:28:15Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"2812f2858077d50fbdef5c7f718c84e2d60a1fe0","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=2812f2858077d50fbdef5c7f718c84e2d60a1fe0  utc=2026-08-19T08:28:15Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "bc42cfafdb7511a13ebb891e3dadc4c6c2e780ff", "size": 382, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHB5dGhvbiB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogdmVyaWZ5IGhhcm5lc3Mgc2hhMjU2IgogICAgICAgIHJ1bjogc2hhc3VtIC1hIDI1NiB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaCB8IGdyZXAgOTU3YmY0OWRhOGZjNmFlMzlmOTdhYmU2Nzk0MTFhZmVhYTVhNTlmNzA3ZjM1YmYzYjNhOGM2ZjlkZTE0MWYwZA==\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@2812f2858077d50fbdef5c7f718c84e2d60a1fe0 (encoding=base64 size=382):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: python tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'python tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['python', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['python', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=9cca068ae0d085a950a20524650acb7cf2292f70 head=2812f2858077d50fbdef5c7f718c84e2d60a1fe0 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=9cca068ae0d085a950a20524650acb7cf2292f70 head=2812f2858077d50fbdef5c7f718c84e2d60a1fe0 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1

########## ⓑ [계약 ae842cce:7125] 스냅샷 오염 canary — 픽스처 (P 는 seed 의 형제 · W 는 후보 «밖») ##########
  seed=38838bc W=e7a145c(후보 밖) d=19ee83c P=bcaa3b7 HEAD=78fb9b3
  *   78fb9b3 M: merge artifact branch
  |\  
  | * bcaa3b7 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * | 19ee83c D0-A: introduce config/tos_completion.yaml
  * | e7a145c W: add .github/workflows/tos-gate.yml (SIMULATED)
  |/  
  * 38838bc seed
  정직 조상성: is-ancestor(P,d) rc=1  (1 = P ⋠ d = LATE 진실)
  shim sha256 = ab00a47d9c1f658c3a648dfb93a7299e6bd7916cb7af6ef53016ba42413adc12 · 심는 graft = e7a145cbe6b5b492755458a3c69a0dacac214096 38838bc580abb279ee539add71f58a36f92e261e bcaa3b71f73a8fe7e7115585cdb32cf72377728f
  원 저장소 grafts = ABSENT  (오염은 «스냅샷 안»에만 생긴다)

########## ⓑ-1 정직 기준선 (shim 없음) — 판정 실행기 ⇒ PREVENTION_LATE (P ⋠ d) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  *   78fb9b3 2026-08-19T17:28:16+09:00 M: merge artifact branch
  |\  
  | * bcaa3b7 2026-08-19T17:28:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * | 19ee83c 2026-08-19T17:28:16+09:00 D0-A: introduce config/tos_completion.yaml
  * | e7a145c 2026-08-19T17:28:15+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  |/  
  * 38838bc 2026-08-19T17:28:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/snap bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git/info/grafts=no · is_shallow=false · entry HEAD=78fb9b3aa56205dbd11b9ea0cf608f056dd959a4
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YuMhcAejLq/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=78fb9b3aa56205dbd11b9ea0cf608f056dd959a4 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YuMhcAejLq/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 5개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/snap capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.LAfHagbIbw
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/snap — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YuMhcAejLq/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YuMhcAejLq/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T08:28:18Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T08:28:18Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T08:28:18Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T08:28:18Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T08:28:18Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T08:28:18Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[bcaa3b71f73a8fe7e7115585cdb32cf72377728f ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[bcaa3b71f73a8fe7e7115585cdb32cf72377728f ] |D|=1 D=[19ee83c4c1386fb5e9bb38f160f05224b9b052d2 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YuMhcAejLq/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/19ee83c4c1386fb5e9bb38f160f05224b9b052d2/pulls  utc=2026-08-19T08:28:19Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"e7a145cbe6b5b492755458a3c69a0dacac214096"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/e7a145cbe6b5b492755458a3c69a0dacac214096/check-runs  utc=2026-08-19T08:28:19Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"e7a145cbe6b5b492755458a3c69a0dacac214096","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"e7a145cbe6b5b492755458a3c69a0dacac214096","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T08:28:19Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"e7a145cbe6b5b492755458a3c69a0dacac214096","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T08:28:19Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"e7a145cbe6b5b492755458a3c69a0dacac214096","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=e7a145cbe6b5b492755458a3c69a0dacac214096  utc=2026-08-19T08:28:20Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@e7a145cbe6b5b492755458a3c69a0dacac214096 (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T08:28:20Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"e7a145cbe6b5b492755458a3c69a0dacac214096","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show e7a145cbe6b5b492755458a3c69a0dacac214096:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=19ee83c4c1386fb5e9bb38f160f05224b9b052d2 head=e7a145cbe6b5b492755458a3c69a0dacac214096 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_LATE
reason=[E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다 [수집 1건 중 전순서 최소]
u17_rc=1

########## ⓑ-2 대조군(캐시 base) + 오염 shim ⇒ canary 가 «원 저장소 경로»를 검사해 거짓 ABSENT = fail-open ##########
$ PATH=<shim>:$PATH U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/snap bash u17-cachedbase-ae.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git/info/grafts=no · is_shallow=false · entry HEAD=78fb9b3aa56205dbd11b9ea0cf608f056dd959a4
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qgLGf71fYj/snap
U17-SNAP clone rc=0
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
U17-SNAP canary(스냅샷 «안»): HEAD=78fb9b3aa56205dbd11b9ea0cf608f056dd959a4 · replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 1건 / 커밋 5개
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[격리 스냅샷 canary] 스냅샷 안에서 ㉠ 불일치 1건 — 기층 오염(--local 폴백·번들 오용 표면)
u17_rc=1

########## ⓑ-3 판정 실행기(스냅샷 안 재파생) + 같은 오염 shim ⇒ canary 발화 = fail-closed ##########
$ PATH=<shim>:$PATH U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/snap bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git/info/grafts=no · is_shallow=false · entry HEAD=78fb9b3aa56205dbd11b9ea0cf608f056dd959a4
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zqx46Kv9NC/snap
U17-SNAP clone rc=0
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
U17-SNAP canary(스냅샷 «안»): HEAD=78fb9b3aa56205dbd11b9ea0cf608f056dd959a4 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zqx46Kv9NC/snap/.git/info/grafts=yes · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 1건 / 커밋 5개
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[격리 스냅샷 canary] 스냅샷 안에서 ㉠ 불일치 1건 — 기층 오염(--local 폴백·번들 오용 표면)
u17_rc=1

########## 회귀 불변 — ⑬a(echo 인자) · ⑭(서버 스텝 부재) 를 에라타 하에서 재실행 ##########
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=9cca068ae0d085a950a20524650acb7cf2292f70 head=2812f2858077d50fbdef5c7f718c84e2d60a1fe0 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=9cca068ae0d085a950a20524650acb7cf2292f70 head=2812f2858077d50fbdef5c7f718c84e2d60a1fe0 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=9cca068ae0d085a950a20524650acb7cf2292f70 head=2812f2858077d50fbdef5c7f718c84e2d60a1fe0 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=9cca068ae0d085a950a20524650acb7cf2292f70 head=2812f2858077d50fbdef5c7f718c84e2d60a1fe0 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭) [수집 1건 중 전순서 최소]
u17_rc=1

########## ⓑ-4/5 ㉡ «단독 검출» 사례 — ㉠ 가 볼 수 없는 오염(존재하지 않는 커밋 id 를 주어로 둔 grafts)로 두 구현의 차이를 분리한다 ##########
  shim2 sha256 = acb3e556f7be9992e763e5fc8d5f130d76889b0d5055f0bf41dca9b0f9630fd4  (주어 = 1111…1111 = 부재 커밋)

########## ⓑ-4 대조군(캐시 base) + ㉠-불가시 오염 ⇒ 오염 신호 «상실»(canary grafts=ABSENT · ㉡ 미발화) — 상태는 정직값 PREVENTION_LATE ##########
$ PATH=<shim2>:$PATH bash u17-cachedbase-ae.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git/info/grafts=no · is_shallow=false · entry HEAD=78fb9b3aa56205dbd11b9ea0cf608f056dd959a4
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.HTfKqn0tZS/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=78fb9b3aa56205dbd11b9ea0cf608f056dd959a4 · replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 5개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/snap capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.RRuH2wD9Rb
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T08:28:33Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[bcaa3b71f73a8fe7e7115585cdb32cf72377728f ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[bcaa3b71f73a8fe7e7115585cdb32cf72377728f ] |D|=1 D=[19ee83c4c1386fb5e9bb38f160f05224b9b052d2 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T08:28:35Z  http=200  x-github-request-id=
U17-B5x 보조(선택·판정 미소비): 로컬 git show e7a145cbe6b5b492755458a3c69a0dacac214096:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=19ee83c4c1386fb5e9bb38f160f05224b9b052d2 head=e7a145cbe6b5b492755458a3c69a0dacac214096 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_LATE
reason=[E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다 [수집 1건 중 전순서 최소]
u17_rc=1

########## ⓑ-5 판정 실행기(스냅샷 안 재파생) + 같은 ㉠-불가시 오염 ⇒ ㉡ 이 «단독»으로 발화 = PREVENTION_UNVERIFIABLE ##########
$ PATH=<shim2>:$PATH bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git/info/grafts=no · is_shallow=false · entry HEAD=78fb9b3aa56205dbd11b9ea0cf608f056dd959a4
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.kOIFkeG7rD/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=78fb9b3aa56205dbd11b9ea0cf608f056dd959a4 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.kOIFkeG7rD/snap/.git/info/grafts=yes · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 5개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam8xae84/snap capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1r8z6Hqvtn
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.kOIFkeG7rD/snap/.git/info/grafts(--git-path 파생)=yes · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.kOIFkeG7rD/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae84/snap/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.kOIFkeG7rD/snap/.git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T08:28:37Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[bcaa3b71f73a8fe7e7115585cdb32cf72377728f ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[bcaa3b71f73a8fe7e7115585cdb32cf72377728f ] |D|=1 D=[19ee83c4c1386fb5e9bb38f160f05224b9b052d2 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.kOIFkeG7rD/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T08:28:40Z  http=200  x-github-request-id=
U17-B5x 보조(선택·판정 미소비): 로컬 git show e7a145cbe6b5b492755458a3c69a0dacac214096:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=19ee83c4c1386fb5e9bb38f160f05224b9b052d2 head=e7a145cbe6b5b492755458a3c69a0dacac214096 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.kOIFkeG7rD/snap/.git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) [수집 2건 중 전순서 최소]
u17_rc=1
```

### 3-2. `bash t8xae82.sh` (U-16 축) (193행)

```text
t8xae82_utc=2026-08-19T08:31:09Z
sha256(u16-full-exec-v220.py)=b90920bdc6d2120954e95273c063fbf8c959e943f0c816c2bd82f8df42045e56
sha256(u16-cachedbase-ae.py)=1b2fd7991aefb206c6aed14d712299f44a6b67fa00ecc501a3a56a22063f1d76
sha256(u16-canary-literal-v220.py)=5b5f7bc9ee949f0393175fa3a73e27da2854562fb62ee4d5912307d3fa6b3f46
-- 대조군 ⓑ diff (판정 실행기 대비 한 축) --
  87a88
  > CACHED_TOP = ""                        # [대조군 ⓑ] snapshot() 진입 시 «원 저장소» 루트로 채운다
  126c127,128
  <     top = g("rev-parse", "--show-toplevel") or R
  ---
  >     # [대조군 ⓑ — 판정용 아님] 진입 «전»(원 저장소) 결합 base 를 캐시해 쓴다 — 계약 ae842cce:7125 가 금지한 구현
  >     top = CACHED_TOP or (g("rev-parse", "--show-toplevel") or R)
  324a327,328
  >     global CACHED_TOP
  >     CACHED_TOP = og("rev-parse", "--show-toplevel")      # [대조군 ⓑ] 진입 «전» 값 캐시
  344c348,349
  <         gpc = _os.path.join(sg("rev-parse", "--show-toplevel").stdout.strip() or snap, gpc)
  ---
  >         # [대조군 ⓑ] canary 의 결합 base 도 «진입 전» 값을 재사용한다 (계약 ae842cce:7125 가 금지한 구현)
  >         gpc = _os.path.join(CACHED_TOP or snap, gpc)
-- 대조군 ⓒ diff --
  87c87
  < CANARY_SHALLOW_LOCAL = True            # [E12 관할] 스냅샷 canary 의 ㉠ 불일치 중 얕은 «경계» 귀속분은 국소 (대조군 E: False = 계약 :7124 «항상 성립» 문언의 «문자» 구현)
  ---
  > CANARY_SHALLOW_LOCAL = False            # [E12 관할] 스냅샷 canary 의 ㉠ 불일치 중 얕은 «경계» 귀속분은 국소 (대조군 E: False = 계약 :7124 «항상 성립» 문언의 «문자» 구현)
git=git version 2.38.0
D_NO = 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9

########## ⓑ 픽스처 — R∥A (S0 → H0 → A → CN · R 은 S0 의 형제 · M 병합) · 오염은 «스냅샷 안»에만 심는다 ##########
  *   a11b3ce M: merge reviewer branch
  |\  
  | * 586620c R: reviewer artifact (digest)
  * | 6f88bbc CN: NO transition
  * | 64841e5 A: approval row (aah=R)
  * | d70f937 H0: unrelated only ⇒ 후보 우주 «밖»
  |/  
  * 7acbc9c S0: register/ledger-header/rationale (리뷰어 경로 없음)
  심을 graft(유효·㉠ 가시) = d70f9374de2e786a2a4260ec0f063829835bcb42 7acbc9c820435d07ba2353c38361505aff3673e1 586620c0305c3e75310dbdc51829fcc0789dde04
  원 저장소 grafts = ABSENT
  shimA(유효 graft) sha256 = d1b4f8dc870296e5c4ea20843ad68d7301674313039f3ef92894535e7a906c25
  shimB(㉠-불가시: 주어가 부재 커밋) sha256 = 863216448ee980a402ff7b401d08ae2b4ed3d787edd6568fd05dbee78077d188

########## ⓑ-1 정직 기준선 (shim 없음) — 판정 실행기 ##########
  *   a11b3ce M: merge reviewer branch
  |\  
  | * 586620c R: reviewer artifact (digest)
  * | 6f88bbc CN: NO transition
  * | 64841e5 A: approval row (aah=R)
  * | d70f937 H0: unrelated only ⇒ 후보 우주 «밖»
  |/  
  * 7acbc9c S0: register/ledger-header/rationale (리뷰어 경로 없음)
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpi7xr695b/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=a11b3ce · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpi7xr695b/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpi7xr695b/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpi7xr695b/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=a11b3ce is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('64841e5', '6f88bbc', 'YES->NO'), ('586620c', 'a11b3ce', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['64841e5'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 64841e5->6f88bbc YES->NO]: PROVENANCE_UNVERIFIABLE(2) — g6 C_R=∅ (후보 1 · 대응 1) C_R={}
  · edge#2[r1 586620c->a11b3ce YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={586620c} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={586620c}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ edge#1[r1 64841e5->6f88bbc YES->NO] — g6 C_R=∅ (후보 1 · 대응 1) C_R={} · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_ORDER_INVALID']
u16_rc=1

########## ⓑ-2 대조군(캐시 base) + 유효 graft 오염 ⇒ canary grafts 는 «원 저장소 경로»(거짓 ABSENT) ##########
$ PATH=<shimA>:$PATH python3 u16-cachedbase-ae.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpwqa616k6/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=a11b3ce · replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 1건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
rules_executed=
rules_missing=U-16-a(EDGES);U-16-a2(∀edge∃row);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;g6(C_R blob·∃witness);h;MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=[격리 스냅샷 canary] 기층 오염 — replace=[] grafts=False ㉠불일치=1 (정직 경계 (b): --local 폴백·번들 오용 적발)
u16_rc=1

########## ⓑ-3 판정 실행기(스냅샷 안 재파생) + 같은 오염 ⇒ canary 가 스냅샷 경로를 본다 ##########
$ PATH=<shimA>:$PATH python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmposa8ds_q/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=a11b3ce · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmposa8ds_q/snap/.git/info/grafts=present · is_shallow=false · ㉠ 불일치 전역 1건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
rules_executed=
rules_missing=U-16-a(EDGES);U-16-a2(∀edge∃row);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;g6(C_R blob·∃witness);h;MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=[격리 스냅샷 canary] 기층 오염 — replace=[] grafts=True ㉠불일치=1 (정직 경계 (b): --local 폴백·번들 오용 적발)
u16_rc=1

########## ⓑ-4 대조군(캐시 base) + ㉠-«불가시» 오염 ⇒ 오염 신호 상실(㉡ 미발화) · 상태는 정직값 ##########
$ PATH=<shimB>:$PATH python3 u16-cachedbase-ae.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpvltesqvw/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=a11b3ce · replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=a11b3ce is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('64841e5', '6f88bbc', 'YES->NO'), ('586620c', 'a11b3ce', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['64841e5'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 64841e5->6f88bbc YES->NO]: PROVENANCE_UNVERIFIABLE(2) — g6 C_R=∅ (후보 1 · 대응 1) C_R={}
  · edge#2[r1 586620c->a11b3ce YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={586620c} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={586620c}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ edge#1[r1 64841e5->6f88bbc YES->NO] — g6 C_R=∅ (후보 1 · 대응 1) C_R={} · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_ORDER_INVALID']
u16_rc=1

########## ⓑ-5 판정 실행기 + 같은 ㉠-«불가시» 오염 ⇒ ㉡(grafts 실재)이 «단독»으로 발화 ##########
$ PATH=<shimB>:$PATH python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/snapfix /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpfzl_i_2b/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=a11b3ce · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpfzl_i_2b/snap/.git/info/grafts=present · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
rules_executed=
rules_missing=U-16-a(EDGES);U-16-a2(∀edge∃row);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;g6(C_R blob·∃witness);h;MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=[격리 스냅샷 canary] 기층 오염 — replace=[] grafts=True ㉠불일치=0 (정직 경계 (b): --local 폴백·번들 오용 적발)
u16_rc=1

########## ⓒ 얕은 원본 → 얕은 스냅샷: ㉢ 국소 귀속 후 «남는» ㉠ 만 기층 오염 (계약 ae842cce:7129) ##########
  원본 is-shallow=false · 얕은 클론 is-shallow=true · rev-list=1

########## ⓒ-1 판정 실행기 — ㉢ 국소 귀속 후 판정 ⇒ PROVENANCE_UNVERIFIABLE(2) · 사유 = |c_APP|=0 ##########
  * cfe57ee M: merge sibling identical approval introduction
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/20b-shallow/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/20b-shallow /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpt96idyb_/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=cfe57ee · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpt96idyb_/snap/.git/info/grafts=ABSENT · is_shallow=true · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 1건 · E12 관할) / 커밋 1개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpt96idyb_/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=True · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpt96idyb_/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=cfe57ee is_shallow=True .git/shallow=['cfe57ee'] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('a009b11', 'cfe57ee', 'ABSENT->NO'), ('db38ad4', 'cfe57ee', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=0(+경계 1)', [])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=0 경계커밋=['cfe57ee'] g4_bad=False g2_bad=False 대응간선=0 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 1건: [('cfe57ee', ['a009b11', 'db38ad4'], [])]
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: PROVENANCE_UNVERIFIABLE(2) — |c_APP|=0 (도입 지점 파생 불가)
  · edge#1[r1 a009b11->cfe57ee ABSENT->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
  · edge#2[r1 db38ad4->cfe57ee ABSENT->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ row[r1/YES->NO] — |c_APP|=0 (도입 지점 파생 불가) · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_MISSING']
u16_rc=1

########## ⓒ-2 대조군 — canary ㉠ «문자» 구현(㉢ 국소화 없음) ⇒ 같은 극성이나 사유가 «기층 오염»으로 바뀐다 ##########
  * cfe57ee M: merge sibling identical approval introduction
$ python3 u16-canary-literal-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/20b-shallow/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx8xae82/20b-shallow /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp7g6v59at/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=cfe57ee · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp7g6v59at/snap/.git/info/grafts=ABSENT · is_shallow=true · ㉠ 불일치 전역 1건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 1개
rules_executed=
rules_missing=U-16-a(EDGES);U-16-a2(∀edge∃row);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;g6(C_R blob·∃witness);h;MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=[격리 스냅샷 canary] 기층 오염 — replace=[] grafts=False ㉠불일치=1 (정직 경계 (b): --local 폴백·번들 오용 적발)
u16_rc=1

########## 회귀 불변 — ⑮(R∥A) · ⑯(선형 반복) 를 에라타 하에서 재실행 ##########
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=전순서 최소 = APPROVAL_ORDER_INVALID(11) @ edge#1[r1 5595d74->66f202d YES->NO] — g6 C_R={e5ee022} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={e5ee022} · 발화 전체=['APPROVAL_ORDER_INVALID']
u16_rc=1
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0
```

## 4. 드라이버·대조군 원문

### 4-1. `t8xae84.sh` (sha256 `d2e5b7b5bb3c2d015e333f4250f26672a0af653c614f2e447496f6f05ff108b0` · 214행)

```bash
#!/usr/bin/env bash
# t8xae84.sh — v2.20 «에라타 재동결 ae842cce» S-24 ② 영향 변이 (U-17 축)
#   ⓐ (b)③ 실행 위치 = 첫 단어 ∪ 인터프리터(고정 리터럴 집합)의 첫 비-옵션 인자 — 술어 7종 + e2e 3종
#   ⓑ 스냅샷 진입 후 «재파생» vs «캐시 base» 대조군 (스냅샷 안 grafts 오염을 canary 가 잡는가)
#   회귀 불변 재확인.  GET-only(seam 위주) · 서버 쓰기 0 · 픽스처는 scratchpad 독립 git repo.
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence
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

FX="$SP/fx8xae84"; SEAM="$SP/seam8xae84"
CBASE="$SP/u17-cachedbase-ae.sh"     # 대조군 ⓑ — 결합 base 캐시(계약 :7125 금지 구현)
rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"
printf 't8xae84_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for f in "$EX" "$WFS" "$CBASE"; do printf 'sha256(%s)=%s\n' "$(basename "$f")" "$(shasum -a 256 "$f" | cut -d" " -f1)"; done
printf -- '-- 대조군 ⓑ diff (판정 실행기 대비 한 축) --\n'; diff "$EX" "$CBASE" | sed 's/^/  /'
printf 'git=%s · gh=%s\n' "$(git --version)" "$(gh --version | head -1)"

########################################################################
sec "ⓐ-1 [계약 ae842cce:5461] 실행 위치 술어 — 인터프리터 고정 리터럴 집합 · 첫 비-옵션 인자"
WD="$FX/wf"; mkdir -p "$WD"
mkwf(){ wfcontent ok | sed "s|bash tools/tos_entry_harness.sh|$1|"; }
printf '%-26s %-46s %s\n' "run: 실행문" "계약 기대(ae842cce:5461)" "실측"
while IFS='|' read -r cmd exp; do
  [ -n "$cmd" ] || continue
  mkwf "$cmd" > "$WD/x.yml"
  got=$(python3 "$WFS" blob "$WD/x.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  printf '%-26s %-46s %s\n' "$cmd" "$exp" "$got"
done <<'CASES'
bash tools/tos_entry_harness.sh|BLOB_OK (인터프리터 첫 비-옵션 인자)
./tools/tos_entry_harness.sh|BLOB_OK (명령 위치)
env bash tools/tos_entry_harness.sh|BLOB_OK (env → bash → 스크립트)
/bin/bash tools/tos_entry_harness.sh|BLOB_OK (절대경로 인터프리터)
sh -e tools/tos_entry_harness.sh|BLOB_OK (첫 «비-옵션» 인자)
echo tools/tos_entry_harness.sh|UNVERIFIED_REVISION (출력 명령 인자 · ⑬a)
printf '%s' tools/tos_entry_harness.sh|UNVERIFIED_REVISION (출력 명령 인자 · ⑬a)
cat tools/tos_entry_harness.sh|UNVERIFIED_REVISION (출력 명령 인자 · ⑬a)
python tools/tos_entry_harness.sh|UNVERIFIED_REVISION (집합 «밖» 인터프리터)
CASES
echo "-- 실행기 코드의 고정 집합 원문 --"; grep -n 'INTERP *=' "$WFS" | sed 's/^/  /'

sec "ⓐ-2 픽스처 저장소 (P → W → d) — e2e 3종은 blob 만 바뀐다"
RB="$FX/blob"; mk "$RB"; art "$RB" "$OR" main >/dev/null; WB=$(wf "$RB" ok); DB=$(d0a "$RB")
echo "W(PR head)=$WB  d=$DB"
inj_wf(){ printf '%s' "$2" > "$1/wf.txt"; inject "$1" "repos/$OR/contents/$WF?ref=$WB" 200 "$(contents_json "$1/wf.txt" "$(git hash-object "$1/wf.txt")" "$WF")"; }

sec "ⓐ-3 e2e 기준선 «bash tools/tos_entry_harness.sh» ⇒ PREVENTION_ACTIVE (에라타 ⓐ 가 «양성»으로 병기한 그 표기)"
S1="$SEAM/bashcall"; seam_ruleset "$S1" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S1" "$DB" "$WB" 777001 "$TLAND" ok ok; run "$RB" "file:$S1"

sec "ⓐ-4 e2e «./tools/tos_entry_harness.sh» ⇒ PREVENTION_ACTIVE"
S2="$SEAM/dotslash"; seam_ruleset "$S2" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S2" "$DB" "$WB" 777001 "$TLAND" ok ok
inj_wf "$S2" "$(mkwf './tools/tos_entry_harness.sh')"; run "$RB" "file:$S2"

sec "ⓐ-5 e2e «python tools/tos_entry_harness.sh» (집합 밖 인터프리터) ⇒ PREVENTION_UNVERIFIED_REVISION"
S3="$SEAM/python"; seam_ruleset "$S3" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S3" "$DB" "$WB" 777001 "$TLAND" ok ok
inj_wf "$S3" "$(mkwf 'python tools/tos_entry_harness.sh')"; run "$RB" "file:$S3"

########################################################################
sec "ⓑ [계약 ae842cce:7125] 스냅샷 오염 canary — 픽스처 (P 는 seed 의 형제 · W 는 후보 «밖»)"
RC="$FX/snap"; mk "$RC"; WC=$(wf "$RC" ok); DC=$(d0a "$RC")
git -C "$RC" checkout -q --detach "$(git -C "$RC" rev-list --max-parents=0 HEAD)"; PC=$(art "$RC" "$OR" main)
git -C "$RC" checkout -q --detach "$DC"; git -C "$RC" merge -q --no-ff -m "M: merge artifact branch" "$PC" 2>/dev/null || { git -C "$RC" add -A; git -C "$RC" commit -q -m "M: merge artifact branch"; }
git -C "$RC" branch -f main HEAD
echo "  seed=$(git -C "$RC" rev-list --max-parents=0 HEAD | cut -c1-7) W=$(echo $WC|cut -c1-7)(후보 밖) d=$(echo $DC|cut -c1-7) P=$(echo $PC|cut -c1-7) HEAD=$(git -C "$RC" rev-parse --short HEAD)"
git -C "$RC" log --oneline --graph --all | sed 's/^/  /'
echo "  정직 조상성: is-ancestor(P,d) rc=$(git -C "$RC" merge-base --is-ancestor "$PC" "$DC"; echo $?)  (1 = P ⋠ d = LATE 진실)"
GRAFT_LINE="$(git -C "$RC" rev-parse "$WC") $(git -C "$RC" rev-list --max-parents=0 HEAD) $(git -C "$RC" rev-parse "$PC")"
SHIM="$FX/shim"; rm -rf "$SHIM"; mkdir -p "$SHIM"; REALGIT=$(command -v git)
cat > "$SHIM/git" <<SHIMEOF
#!/bin/sh
# [SIMULATED 기층 오염] clone 직후 «스냅샷 안»에 grafts 를 심는다 (계약 정직 경계 (b) 가 잡아야 하는 «--local 폴백·번들 오용» 등가물).
case " \$* " in
  *" clone "*)
      $REALGIT "\$@"; rc=\$?
      dst=\$(eval echo "\\\${\$#}")
      [ -d "\$dst/.git" ] && { mkdir -p "\$dst/.git/info"; printf '%s\n' "$GRAFT_LINE" > "\$dst/.git/info/grafts"; }
      exit \$rc ;;
esac
exec $REALGIT "\$@"
SHIMEOF
chmod +x "$SHIM/git"
echo "  shim sha256 = $(shasum -a 256 "$SHIM/git" | cut -d' ' -f1) · 심는 graft = $GRAFT_LINE"
echo "  원 저장소 grafts = $( [ -f "$RC/.git/info/grafts" ] && echo present || echo ABSENT )  (오염은 «스냅샷 안»에만 생긴다)"
S4="$SEAM/snap"; seam_ruleset "$S4" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S4" "$DC" "$WC" 777001 "$TLAND" ok ok

sec "ⓑ-1 정직 기준선 (shim 없음) — 판정 실행기 ⇒ PREVENTION_LATE (P ⋠ d)"
run "$RC" "file:$S4"

sec "ⓑ-2 대조군(캐시 base) + 오염 shim ⇒ canary 가 «원 저장소 경로»를 검사해 거짓 ABSENT = fail-open"
echo "\$ PATH=<shim>:\$PATH U17_RESPONDER=file:$S4 bash $(basename "$CBASE") <fixture>"
PATH="$SHIM:$PATH" U17_RESPONDER="file:$S4" U17_CAPTURE_DIR="$(mktemp -d)" bash "$CBASE" "$RC" 2>&1 | grep -avE '^U17-(A00|A0 |A1|A2|A3|A4|B1|B2|B3|B4|B5) |^  \| |^U17-H '; echo "u17_rc=${PIPESTATUS[0]}"

sec "ⓑ-3 판정 실행기(스냅샷 안 재파생) + 같은 오염 shim ⇒ canary 발화 = fail-closed"
echo "\$ PATH=<shim>:\$PATH U17_RESPONDER=file:$S4 bash $(basename "$EX") <fixture>"
PATH="$SHIM:$PATH" U17_RESPONDER="file:$S4" U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$RC" 2>&1 | grep -avE '^U17-(A00|A0 |A1|A2|A3|A4|B1|B2|B3|B4|B5) |^  \| |^U17-H '; echo "u17_rc=${PIPESTATUS[0]}"

sec "회귀 불변 — ⑬a(echo 인자) · ⑭(서버 스텝 부재) 를 에라타 하에서 재실행"
S5="$SEAM/13a"; seam_ruleset "$S5" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S5" "$DB" "$WB" 777001 "$TLAND" echoarg ok; run "$RB" "file:$S5" | tail -6
S6="$SEAM/14"; seam_ruleset "$S6" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S6" "$DB" "$WB" 777001 "$TLAND" ok noverify; run "$RB" "file:$S6" | tail -6

########################################################################
sec "ⓑ-4/5 ㉡ «단독 검출» 사례 — ㉠ 가 볼 수 없는 오염(존재하지 않는 커밋 id 를 주어로 둔 grafts)로 두 구현의 차이를 분리한다"
SHIM2="$FX/shim2"; rm -rf "$SHIM2"; mkdir -p "$SHIM2"
cat > "$SHIM2/git" <<SHIM2EOF
#!/bin/sh
# [SIMULATED 기층 오염 — ㉠ 불가시] 주어가 «저장소에 없는 커밋 id» 라 git 이 무시한다 ⇒ 부모 불변(㉠ 침묵)·파일은 실재(㉡ 만 본다).
case " \$* " in
  *" clone "*)
      $REALGIT "\$@"; rc=\$?
      dst=\$(eval echo "\\\${\$#}")
      [ -d "\$dst/.git" ] && { mkdir -p "\$dst/.git/info"; printf '1111111111111111111111111111111111111111 %s\n' "$(git -C "$RC" rev-parse HEAD)" > "\$dst/.git/info/grafts"; }
      exit \$rc ;;
esac
exec $REALGIT "\$@"
SHIM2EOF
chmod +x "$SHIM2/git"
echo "  shim2 sha256 = $(shasum -a 256 "$SHIM2/git" | cut -d' ' -f1)  (주어 = 1111…1111 = 부재 커밋)"

sec "ⓑ-4 대조군(캐시 base) + ㉠-불가시 오염 ⇒ 오염 신호 «상실»(canary grafts=ABSENT · ㉡ 미발화) — 상태는 정직값 PREVENTION_LATE"
echo "\$ PATH=<shim2>:\$PATH bash $(basename "$CBASE") <fixture>"
PATH="$SHIM2:$PATH" U17_RESPONDER="file:$S4" U17_CAPTURE_DIR="$(mktemp -d)" bash "$CBASE" "$RC" 2>&1 | grep -avE '^U17-(A00|A0 |A1|A2|A3|A4|B1|B2|B3|B4|B5) |^  \| |^U17-H |^힌트|^remote:'; echo "u17_rc=${PIPESTATUS[0]}"

sec "ⓑ-5 판정 실행기(스냅샷 안 재파생) + 같은 ㉠-불가시 오염 ⇒ ㉡ 이 «단독»으로 발화 = PREVENTION_UNVERIFIABLE"
echo "\$ PATH=<shim2>:\$PATH bash $(basename "$EX") <fixture>"
PATH="$SHIM2:$PATH" U17_RESPONDER="file:$S4" U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$RC" 2>&1 | grep -avE '^U17-(A00|A0 |A1|A2|A3|A4|B1|B2|B3|B4|B5) |^  \| |^U17-H |^힌트|^remote:'; echo "u17_rc=${PIPESTATUS[0]}"
```

### 4-2. `t8xae82.sh` (sha256 `c2530cd4ca878e3b5b2598c4e367a61bc9d7878036e14160f5a853a6c35f7008` · 130행)

```bash
#!/usr/bin/env bash
# t8xae82.sh — v2.20 «에라타 재동결 ae842cce» S-24 ② 영향 변이 (U-16 축)
#   ⓑ 스냅샷 진입 후 «재파생» vs «캐시 base» (오염 canary) · ⓒ 얕은 스냅샷에서 ㉢ 국소 귀속 vs «문자» 구현
#   회귀 불변 재확인.  서버 조회 0(순수 in-repo) · 픽스처는 scratchpad 독립 git repo.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence
SP19=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u16-full-exec-v220.py"                 # 판정 실행기 — 격리 스냅샷 기층
CTRL="$SP/u16-order-ctrl-g1first-v220.py"      # 대조군 D — EVAL_ORDER 한 줄 (⑳ⓑ)
EXG6="$SP/u16-g6omit-v220.py"                  # 대조군 B — g6 «생략» (⑮)
EXSEQ="$SP/u16-edgeseq-v220.py"                # 대조군 C — 폐지 edge_seq 기재값 소비 (⑯·⑱)
EXNS="$SP/u16-nosnap-v220.py"                  # 대조군 A — 격리 스냅샷 «없음» (⑳ⓒ)
EX215="$SP19/u16-full-exec-v215.py"            # 직전 판 부속 — «복수면 사전순 최소» (⑳ⓐ)
EXCAN="$SP/u16-canary-literal-v220.py"         # 대조군 E — canary 의 ㉠ 를 계약 :7124 «항상 성립» 문언대로 «문자» 구현 (얕음 국소화 없음)
FX="$SP/fx82v220"; REF=reviews/review.md; RAT=rationale/r1.md
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
dig(){ python3 -c "import hashlib,sys; r=dict(id=sys.argv[1],closable=sys.argv[2],owner_track=sys.argv[3]); print(hashlib.sha256(b'\0'.join(f'{k}={r[k]}'.encode() for k in sorted(r))).hexdigest())" "$@"; }
DNO=$(dig r1 NO tos)     # 승인 대상 = 제안된 NO 행 (id=r1, closable=NO, owner_track=tos)
reg(){ printf 'id,closable,owner_track\n'; for kv in "$@"; do printf '%s\n' "$kv"; done; }
c(){ git -C "$1" add -A && git -C "$1" commit -q --allow-empty -m "$2" && git -C "$1" rev-parse --short HEAD; }
base(){ rm -rf "$1"; git init -q -b main "$1"; mkdir -p "$1/reviews" "$1/rationale"
  reg 'other,YES,x' 'r1,YES,tos' > "$1/register.csv"; echo "## ledger" > "$1/LEDGER.md"; echo "rationale for r1 NO" > "$1/$RAT"
  echo "rationale (approver a)" > "$1/rationale/r1-a.md"; echo "rationale (approver b)" > "$1/rationale/r1-b.md"
  case "${2:-full}" in full) printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$1/$REF";; carrier) printf '%s\n' "$DNO" > "$1/$REF";; unrelated) printf 'unrelated review text\n' > "$1/$REF";; none) ;; esac
  c "$1" "H0: base (r1=YES; reviewer=${2:-full})"; }
row(){ printf 'r1 | %s | %s | %s | %s | %s\n' "$1" "$DNO" "$2" "$REF" "${3:-$RAT}"; }
setNO(){ reg 'other,YES,x' 'r1,NO,tos' > "$1/register.csv"; }
setYES(){ reg 'other,YES,x' 'r1,YES,tos' > "$1/register.csv"; }
run(){ git -C "$1" log --graph --oneline --all | sed 's/^/  /'; echo "\$ python3 $(basename "${2:-$EX}") <fixture>"; python3 "${2:-$EX}" "$1"; echo "u16_rc=$?"; }
mergeled(){ git -C "$1" merge -q --no-ff -m "$3" "$2" 2>/dev/null || { { echo "## ledger"; git -C "$1" show HEAD:LEDGER.md | tail -n +2; git -C "$1" show "$2":LEDGER.md | tail -n +2; } | awk '!seen[$0]++' > "$1/LEDGER.md"; git -C "$1" add -A; git -C "$1" commit -q -m "$3"; }; }

CBASE="$SP/u16-cachedbase-ae.py"      # 대조군 ⓑ — 결합 base 캐시(계약 ae842cce:7125 금지 구현)
EXCAN="$SP/u16-canary-literal-v220.py"  # 대조군 ⓒ — canary ㉠ «문자» 구현(㉢ 국소화 없음)
FX="$SP/fx8xae82"
rm -rf "$FX"; mkdir -p "$FX"
printf 't8xae82_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for f in "$EX" "$CBASE" "$EXCAN"; do printf 'sha256(%s)=%s\n' "$(basename "$f")" "$(shasum -a 256 "$f" | cut -d" " -f1)"; done
printf -- '-- 대조군 ⓑ diff (판정 실행기 대비 한 축) --\n'; diff "$EX" "$CBASE" | sed 's/^/  /'
printf -- '-- 대조군 ⓒ diff --\n'; diff "$EX" "$EXCAN" | sed 's/^/  /'
printf 'git=%s\n' "$(git --version)"
echo "D_NO = $DNO"

########################################################################
sec "ⓑ 픽스처 — R∥A (S0 → H0 → A → CN · R 은 S0 의 형제 · M 병합) · 오염은 «스냅샷 안»에만 심는다"
R="$FX/snapfix"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' 'r1,YES,tos' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"
S0=$(c "$R" "S0: register/ledger-header/rationale (리뷰어 경로 없음)")
printf 'unrelated\n' > "$R/note.md"; H0=$(c "$R" "H0: unrelated only ⇒ 후보 우주 «밖»")
git -C "$R" checkout -q --detach "$S0"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; RR=$(c "$R" "R: reviewer artifact (digest)")
git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$(git -C "$R" rev-parse "$RR")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=R)")
setNO "$R"; CN=$(c "$R" "CN: NO transition")
git -C "$R" merge -q --no-ff -m "M: merge reviewer branch" "$RR" 2>/dev/null || { git -C "$R" add -A; git -C "$R" commit -q -m "M: merge reviewer branch"; }
git -C "$R" branch -f main HEAD
git -C "$R" log --oneline --graph --all | sed 's/^/  /'
GL="$(git -C "$R" rev-parse "$H0") $(git -C "$R" rev-parse "$S0") $(git -C "$R" rev-parse "$RR")"
echo "  심을 graft(유효·㉠ 가시) = $GL"
echo "  원 저장소 grafts = $( [ -f "$R/.git/info/grafts" ] && echo present || echo ABSENT )"
REALGIT=$(command -v git)
mkshim(){ local d="$1" line="$2"; rm -rf "$d"; mkdir -p "$d"
  { echo '#!/bin/sh'
    echo '# [SIMULATED 기층 오염] clone 직후 «스냅샷 안»에 grafts 를 심는다 (계약 정직 경계 (b) 대상).'
    echo 'case " $* " in'
    echo '  *" clone "*)'
    echo "      $REALGIT \"\$@\"; rc=\$?"
    echo '      dst=$(eval echo "\${$#}")'
    echo "      [ -d \"\$dst/.git\" ] && { mkdir -p \"\$dst/.git/info\"; printf '%s\\n' '$line' > \"\$dst/.git/info/grafts\"; }"
    echo '      exit $rc ;;'
    echo 'esac'
    echo "exec $REALGIT \"\$@\""
  } > "$d/git"; chmod +x "$d/git"; }
mkshim "$FX/shimA" "$GL"
mkshim "$FX/shimB" "1111111111111111111111111111111111111111 $(git -C "$R" rev-parse HEAD)"
echo "  shimA(유효 graft) sha256 = $(shasum -a 256 "$FX/shimA/git" | cut -d' ' -f1)"
echo "  shimB(㉠-불가시: 주어가 부재 커밋) sha256 = $(shasum -a 256 "$FX/shimB/git" | cut -d' ' -f1)"

sec "ⓑ-1 정직 기준선 (shim 없음) — 판정 실행기"
run "$R"

sec "ⓑ-2 대조군(캐시 base) + 유효 graft 오염 ⇒ canary grafts 는 «원 저장소 경로»(거짓 ABSENT)"
echo "\$ PATH=<shimA>:\$PATH python3 $(basename "$CBASE") <fixture>"
PATH="$FX/shimA:$PATH" python3 "$CBASE" "$R" 2>&1 | grep -av '^힌트\|^remote:'; echo "u16_rc=${PIPESTATUS[0]}"

sec "ⓑ-3 판정 실행기(스냅샷 안 재파생) + 같은 오염 ⇒ canary 가 스냅샷 경로를 본다"
echo "\$ PATH=<shimA>:\$PATH python3 $(basename "$EX") <fixture>"
PATH="$FX/shimA:$PATH" python3 "$EX" "$R" 2>&1 | grep -av '^힌트\|^remote:'; echo "u16_rc=${PIPESTATUS[0]}"

sec "ⓑ-4 대조군(캐시 base) + ㉠-«불가시» 오염 ⇒ 오염 신호 상실(㉡ 미발화) · 상태는 정직값"
echo "\$ PATH=<shimB>:\$PATH python3 $(basename "$CBASE") <fixture>"
PATH="$FX/shimB:$PATH" python3 "$CBASE" "$R" 2>&1 | grep -av '^힌트\|^remote:'; echo "u16_rc=${PIPESTATUS[0]}"

sec "ⓑ-5 판정 실행기 + 같은 ㉠-«불가시» 오염 ⇒ ㉡(grafts 실재)이 «단독»으로 발화"
echo "\$ PATH=<shimB>:\$PATH python3 $(basename "$EX") <fixture>"
PATH="$FX/shimB:$PATH" python3 "$EX" "$R" 2>&1 | grep -av '^힌트\|^remote:'; echo "u16_rc=${PIPESTATUS[0]}"

########################################################################
sec "ⓒ 얕은 원본 → 얕은 스냅샷: ㉢ 국소 귀속 후 «남는» ㉠ 만 기층 오염 (계약 ae842cce:7129)"
n=0
while :; do
  RA="$FX/20a"; H0=$(base "$RA")
  git -C "$RA" checkout -q --detach; row YES-\>NO "$H0" >> "$RA/LEDGER.md"; X=$(c "$RA" "X: approval row A [branch x nonce=$n]")
  setNO "$RA"; CN2=$(c "$RA" "CN: NO transition (child of X)")
  git -C "$RA" checkout -q --detach main; row YES-\>NO "$H0" >> "$RA/LEDGER.md"; Y=$(c "$RA" "Y: approval row A (byte-identical) [branch y nonce=$n]")
  XF=$(git -C "$RA" rev-parse "$X"); YF=$(git -C "$RA" rev-parse "$Y")
  [ "$XF" \< "$YF" ] && break
  n=$((n+1)); [ "$n" -lt 60 ] || break
done
git -C "$RA" checkout -q --detach "$CN2"; mergeled "$RA" "$Y" "M: merge sibling identical approval introduction"; git -C "$RA" branch -f main HEAD
SH="$FX/20b-shallow"; rm -rf "$SH"; git clone -q --depth 1 "file://$RA" "$SH" 2>/dev/null
echo "  원본 is-shallow=$(git -C "$RA" rev-parse --is-shallow-repository) · 얕은 클론 is-shallow=$(git -C "$SH" rev-parse --is-shallow-repository) · rev-list=$(git -C "$SH" rev-list HEAD | wc -l | tr -d ' ')"

sec "ⓒ-1 판정 실행기 — ㉢ 국소 귀속 후 판정 ⇒ PROVENANCE_UNVERIFIABLE(2) · 사유 = |c_APP|=0"
run "$SH"

sec "ⓒ-2 대조군 — canary ㉠ «문자» 구현(㉢ 국소화 없음) ⇒ 같은 극성이나 사유가 «기층 오염»으로 바뀐다"
run "$SH" "$EXCAN"

########################################################################
sec "회귀 불변 — ⑮(R∥A) · ⑯(선형 반복) 를 에라타 하에서 재실행"
R2="$FX/15"; H0=$(base "$R2" none)
git -C "$R2" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R2/$REF"; RR2=$(c "$R2" "R: new reviewer artifact")
git -C "$R2" checkout -q --detach main; row YES-\>NO "$(git -C "$R2" rev-parse "$RR2")" >> "$R2/LEDGER.md"; A2=$(c "$R2" "A: approval (aah=R) [parallel]")
git -C "$R2" merge -q --no-ff -m "M0: merge R" "$RR2"; setNO "$R2"; c "$R2" "M: NO transition" >/dev/null; git -C "$R2" branch -f main HEAD
run "$R2" | tail -5
R3="$FX/16"; rm -rf "$R3"; git init -q -b main "$R3"; mkdir -p "$R3/reviews" "$R3/rationale"
reg 'other,YES,x' > "$R3/register.csv"; echo "## ledger" > "$R3/LEDGER.md"; echo "rationale for r1 NO" > "$R3/$RAT"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R3/$REF"; c "$R3" "H0: r1 absent" >/dev/null
row ABSENT-\>NO "$(git -C "$R3" rev-parse HEAD)" >> "$R3/LEDGER.md"; c "$R3" "A1: approval (ABSENT->NO)" >/dev/null; setNO "$R3"; c "$R3" "e1: ABSENT->NO" >/dev/null
setYES "$R3"; c "$R3" "back to YES" >/dev/null
row YES-\>NO "$(git -C "$R3" rev-parse HEAD)" >> "$R3/LEDGER.md"; c "$R3" "A2: approval (YES->NO)" >/dev/null; setNO "$R3"; c "$R3" "e2: YES->NO" >/dev/null
run "$R3" | tail -5
```

### 4-3. 대조군 diff (판정 실행기 대비 — 각 «한 축»)

```diff
# u17-verify-v220.sh → u17-cachedbase-ae.sh
82,84c82,83
< # [v2.20 D-γ] 결합 base 를 «호출 시점»에 파생한다 — 격리 스냅샷으로 cwd 가 바뀐 뒤 캐시된 TOPLEVEL 을 쓰면
< #   스냅샷의 grafts 를 «원 저장소 경로»로 검사해 «거짓 ABSENT» 가 된다(E15 극성 규율의 재발 표면).
< gitpath() { local v t; v=$(git rev-parse --git-path "$1" 2>/dev/null); t=$(git rev-parse --show-toplevel 2>/dev/null || printf '%s' "$TOPLEVEL"); case "$v" in /*) printf '%s' "$v";; "") printf '';; *) printf '%s/%s' "$t" "$v";; esac; }
---
> # [대조군 ⓑ — 판정용 아님] 결합 base 를 «진입 전»(원 저장소) 값으로 캐시 — 계약 ae842cce:7125 가 금지한 그 구현
> gitpath() { local v; v=$(git rev-parse --git-path "$1" 2>/dev/null); case "$v" in /*) printf '%s' "$v";; "") printf '';; *) printf '%s/%s' "$TOPLEVEL" "$v";; esac; }
# u16-full-exec-v220.py → u16-cachedbase-ae.py
87a88
> CACHED_TOP = ""                        # [대조군 ⓑ] snapshot() 진입 시 «원 저장소» 루트로 채운다
126c127,128
<     top = g("rev-parse", "--show-toplevel") or R
---
>     # [대조군 ⓑ — 판정용 아님] 진입 «전»(원 저장소) 결합 base 를 캐시해 쓴다 — 계약 ae842cce:7125 가 금지한 구현
>     top = CACHED_TOP or (g("rev-parse", "--show-toplevel") or R)
324a327,328
>     global CACHED_TOP
>     CACHED_TOP = og("rev-parse", "--show-toplevel")      # [대조군 ⓑ] 진입 «전» 값 캐시
344c348,349
<         gpc = _os.path.join(sg("rev-parse", "--show-toplevel").stdout.strip() or snap, gpc)
---
>         # [대조군 ⓑ] canary 의 결합 base 도 «진입 전» 값을 재사용한다 (계약 ae842cce:7125 가 금지한 구현)
>         gpc = _os.path.join(CACHED_TOP or snap, gpc)
# u16-full-exec-v220.py → u16-canary-literal-v220.py
87c87
< CANARY_SHALLOW_LOCAL = True            # [E12 관할] 스냅샷 canary 의 ㉠ 불일치 중 얕은 «경계» 귀속분은 국소 (대조군 E: False = 계약 :7124 «항상 성립» 문언의 «문자» 구현)
---
> CANARY_SHALLOW_LOCAL = False            # [E12 관할] 스냅샷 canary 의 ㉠ 불일치 중 얕은 «경계» 귀속분은 국소 (대조군 E: False = 계약 :7124 «항상 성립» 문언의 «문자» 구현)
```

## 5. 관측 보고 · 신규 결함 후보 (등급)

### A-1 **[관측 — 자기 정정]** v2.20 증거 M-1 의 «fail-open» 은 «다층 방어 한 겹의 오작동»으로 정밀화된다

캐시 base 가 만드는 **거짓 ABSENT 는 실측 확정**이나, 유효 오염은 ㉠ 가 독립 검출하므로 **종단 fail-open 은 이 실행기 구성에서 도달하지 않았다**(§2-2). 에라타 ⓑ 는 여전히 필요하다 — ㉠ 가 보지 못하는 오염(`grafts` 주어가 부재 커밋)에서 **㉡ 이 유일 검출자**이며 그 경우 캐시 base 는 신호를 잃는다(실증). **등급: 관측(선행 증거 표현의 정밀화 — 계약 문언에 영향 없음).**

### A-2 **[관측]** ⓑ 의 노출면은 «`cd` 기반 실행기»에 한정되지 않는다

`git rev-parse --git-path` 는 `git -C <절대경로>` 로 호출해도 **상대 경로**(`.git/info/grafts`)를 반환한다(실측). 따라서 «결합 base» 문제는 `cd` 방식뿐 아니라 `-C` 방식 실행기에도 동일하게 존재하며, 에라타 ⓑ 의 «스냅샷 안에서 재파생» 요구가 두 방식 모두를 덮는다. **등급: 관측(문언 적정성 확인).**

### A-3 **[관측]** ⓒ 는 «사유 라벨»만 바꾸고 극성은 양쪽 fail-closed

판정 실행기와 문자 구현 모두 `PROVENANCE_UNVERIFIABLE`(2)·rc≠0 이며, 차이는 사유(`|c_APP|=0` vs `기층 오염`)다. 계약이 «양쪽 fail-closed·사유만 상이»로 적은 그대로다(:7129). **등급: 관측.**

### A-4 **[fail-open/차단 등급 신규 결함 후보 0]**

이 회차에서 계약 문언을 그대로 구현했을 때 green 을 내는 자리는 발견되지 않았다. 문언 등급 신규 지적도 없다 — ⓐⓑⓒ 는 직전 회차 지적(M-3·M-1·N-1)의 처분이며, 실측이 **셋 다 기대대로** 닫혔음을 보인다.

## 6. 사후 재조회 (서버 무변경 · HEAD 불변)

```text
post_ae_utc=2026-08-19T08:32:52Z
HEAD = ae842cceab472c947ec9c01f6b181f5151b92172  (ae842cce 와 동일? YES)
계약 워킹트리 blob   = 9bfa21aa957b0b001a2f4daf7d26f472619175a5  == ae842cce blob 9bfa21aa957b0b001a2f4daf7d26f472619175a5 → 동일
개발계획 워킹트리 blob = d00aa15ef84a9f76058403a0dd91549c9f614533  == 3d17ea66 blob d00aa15ef84a9f76058403a0dd91549c9f614533 → 동일 (에라타에서 무변경)
ae842cce..HEAD 두 문서 커밋 = 0건 · 전체 커밋 = 0건
계약 행수 = 7494 · 개발계획 행수 = 579
하니스 sed -n 4654,4754p sha256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d (계약 리터럴 957bf49d… 일치? YES · 3d17ea66 과 byte-동일? YES)
워킹트리 두 문서 변경 = 0건
본 저장소 [PARENTS-UNTRUSTED] 관측: replace -l=[] · info/grafts=ABSENT · is_shallow=false
-- 서버 사후 재조회 (GET 1회 · --hostname github.com) --
$ gh api -i --hostname github.com repos/kakao-harris-lee/kis_unified_sts/branches/main/protection    # utc=2026-08-19T08:32:52Z
  | HTTP/2.0 200 OK
  | X-Github-Request-Id: 732B:177308:95A8F2:A4EE47:6A856A34
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks
  ⇒ (a) 술어 입력 불변: contexts=["test"] · tos-gate 부재 ⇒ 본 저장소 live 상태값 극성은 v2.20 증거(d101eb63) 와 동일하다
픽스처 격리: scratchpad 독립 저장소 31개 · 본 저장소 worktree 목록 3줄(이 증거는 worktree 0개 생성)
```
