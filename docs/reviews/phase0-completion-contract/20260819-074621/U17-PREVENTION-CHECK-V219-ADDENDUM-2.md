# U17-PREVENTION-CHECK-V219-ADDENDUM-2 — v2.19 에라타 2차 `ad5be1a3` S-24 addendum (절 범위 diff 기계 증명 + 영향 변이 재실행: E8 `[PARENTS-UNTRUSTED]` · E9 `P_first`/`P_last` ∀-부모)

> **비규범 부속** — 계약 v2.19 에라타 2차 `ad5be1a3`(7,316행) 후 **S-24** 이행. 선행 증거 `U17-PREVENTION-CHECK-V219.md`·`U16-LEDGER-CHECK-V219.md`(`90a5ce7d`, 동결 `d5a8302a` 결속) 와
> `U17-PREVENTION-CHECK-V219-ADDENDUM.md`(`197f4fe4`, 에라타 `e3ed4e78` 결속)는 U-15-e **(4d) 불변 규율을 준용해 편집하지 않고**, ① `git diff e3ed4e78..ad5be1a3 -- <계약>` 전문과
> **닿는/닿지 않는 절 범위의 기계 증명**(§1)으로 **비영향 변이의 증거가 그대로 결속됨을 선언**하고, ② **영향 변이만 재실행**(§2~§4)한다. **U-17·U-16 두 축을 한 addendum 에 절로 나눠 수록**(파일 하나).
> **결속**: 실행 시점 HEAD == `ad5be1a3` · 계약 워킹트리 blob `22be5f33` == `git show ad5be1a3:<계약>` blob(`git diff --quiet ad5be1a3 -- <계약>` rc=0 · 워킹트리 sha256
> `450ac1851cb6e62f2467f230658d6e9067d40b70319f6d683b412bce5a542f9e`) · `ad5be1a3..HEAD` 계약 커밋 **0** ·
> 하니스 §12.3.4-R 블록 `sed -n '4608,4708p'` sha256 **`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`** — **`e3ed4e78` 의 `:4598-4698` 과 byte-동일**(§1 ④ · §6 재확인).
> **판정 소비자는 이 파일의 응답을 신뢰하지 않고 스스로 live 조회한다**(대조용) · **서버 쓰기·설정 변경 0**(U-17 축은 seam·GET-only, U-16 축은 GitHub 조회 0) ·
> 픽스처는 scratchpad 하위 **독립 git 저장소**(`fx84f/*`·`fx82f/*` — 본 저장소 무접촉·worktree 미사용 · `git replace`/`.git/info/grafts` 조작은 **전부 그 픽스처 안에서만**, 본 저장소는 §6 에서 `replace -l` 공집합·`grafts` 부재·`shallow=false` 로 확인).
- **생성 시각**: 2026-08-19T02:44:54Z (UTC) · 실행 `t84v219e2_utc=2026-08-19T02:40:07Z` · `t82v219e2_utc=2026-08-19T02:42:38Z` · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트(저작자·심판 아님)
- **실행기 결속**:
  - sha256(`s24-proof-2.sh`) = **`866e55b57afa175fe15d1223fa4a852b61af8169d38f9918b1559415881edd2e`** (§1)
  - sha256(`u17-verify-v219e2.sh`) = **`8516adc2684498fb08d5312acab8dc5f25345c9268f0ec84b738d805bfb85968`** (직전 `6a80beed…` 대비 **diff 123행** — E8·E9, §2-1)
  - sha256(`u17-verify-v219e2-CTRL-noobserve.sh`) = **`380eb9b9597d3c4c939da413066ef69995e9e95b82ab7d5704058545d3d54d32`** (**E8 대조군** — ① 관측 limb «만» 제거·② 무력화 유지. diff **9행**. 판정용 아님)
  - sha256(`u16-full-exec-v219e2.py`) = **`cca1d6d7e491a7941f82897ea834655ab6494eff94cae15c70939435ac709482`** (직전 `729867ca…` 대비 **diff 62행** — E8, §2-2)
  - sha256(`u16-full-exec-v219e2-CTRL-noobserve.py`) = **`87c1efa0aaf9ff3b69663904cd093fca1466b03b8b5b911a7c49089fc50862f9`** (**E8 대조군** · diff **13행**)
  - sha256(`t84v219e2.sh`) = `2d4907a455b5154b54fcf0dda8bf6da01903bbf1a6ffd0cf759d250897bfddfc` · sha256(`t82v219e2.sh`) = `25343e47f3d3bc5b8db3c2862a6038b0c62deb565f25409cb058334a1b63596e`
  - **불변 재사용(직전 판 = «①② 둘 다 없음» 기준선)**: `u17-verify-v219e.sh` `6a80beed…` · `u16-full-exec-v219e.py` `729867ca…` · `u16-order-ctrl-g1first.py` `4e9f0bc4…`

## 0. 결속 선언 (S-24 ②·①)

| 변이 (선행 증거 `90a5ce7d`·`197f4fe4`) | 닿는 에라타 2차 절 | 처분 |
| --- | --- | --- |
| **T-84 ①~⑫ 전건**(host·연속성·target·classic terminal·아티팩트 사후 편집 …) · **T-82 ⑮⑯⑰ⓐⓑⓒ⑱⑲⑳ⓐⓑ 전건** | — (§1 ③ 이 §8 **T-84·T-82·T-81 행 전부 ∅**, (a)·(b)·(α) 본체 ∅, U-17-c **전순서 10단** ∅, U-16-d **전순서 12단 표**·**② g-단락** ∅, `c_APP` **수식** ∅, U-16-a2·U-16-h·U-16-b ∅ 로 증명) | **비영향 — `90a5ce7d`·`197f4fe4` 증거 그대로 결속** |
| **[SHALLOW] 4정의**(D·C_R·c_APP·P) · ⑳ⓑ 선-검사 국소화 | **E8** `[SHALLOW]` → `[PARENTS-UNTRUSTED]` 일반화·개명(U-16-c 유일 소스 + 참조 4곳 + 선-검사) | **재실행 + 축 확장**(§3-1·§4-2) — replace/graft·`.git/info/grafts` 축 신설 |
| **T-84 ⑨ 아티팩트 사후 편집** · 직전 addendum **N-2**(P_last 다부모 ∨/∀ 모호) | **E9** `P_first`/`P_last` ∀-부모 동형 구조 «집합» 정의 + U-17-c 상태 조건 재정의 | **재실행**(§3-2·§3-3) — ∨ 폐기·카디널리티 처분 신설 |
| 직전 addendum **N-3~N-5**(관측) | U-16-d 전순서 머리에 «세 층» 주석 추가(비차단) | **문언 정합화 — 실행기 거동 불변**(§1 ③ 이 전순서 «표» 자체는 ∅ 임을 증명) |

- **결과 요약 (재실행분 · stdout·rc 원문 그대로 · 4정의 = `D`·`P`(U-17) + `c_APP`·`C_R`(U-16) 각각 실측)**:

| # | 변이 | 실행기 | 방출값 | rc | 기대 (ad5be1a3 문언) | 대조 |
| --- | --- | --- | --- | --- | --- | --- |
| **1** | **[E8]-1** `git replace --graft` (U-17 `D`·`P` 축) — 진실 | v2.19-2 (①+②) | **`PREVENTION_LATE`**(6) | 1 | graft «전» 진실 | **일치** |
| | 〃 graft 후 | **직전**(①② 없음) | **`PREVENTION_ACTIVE`**(10) | **0** | — | **fail-open 재현**(직전 addendum N-1) |
| | 〃 graft 후 | **CTRL**(②만) | **`PREVENTION_LATE`**(6) | 1 | **② 무력화 = 진짜 부모** | **일치** |
| | 〃 graft 후 | **v2.19-2**(①+②) | **`PREVENTION_UNVERIFIABLE`**(1) | 1 | **① 관측이 전순서 1 로 먼저** | **일치** |
| **1** | **[E8]-2** `.git/info/grafts` (U-17) | 판별 실측 | `%P` 재작성 · **`GIT_NO_REPLACE_OBJECTS=1` 로도 그대로** · `git replace -l` **공집합** | — | 계약 «② 로 꺼지지 않는다 → ① 이 담당» | **일치 (실측)** |
| | 〃 | **CTRL**(②만) | **`PREVENTION_ACTIVE`** | **0** | fail-open 잔존 | **일치 — ② 만으로 불충분 실증** |
| | 〃 | **v2.19-2** | **`PREVENTION_UNVERIFIABLE`**(1) | 1 | ① `.git/info/grafts` 부재 요구 | **일치** |
| **1** | **[E8]-U16-1** `c_APP` 축 (⑳ⓐ 픽스처) | v2.19-2 / 직전 / CTRL / v2.19-2 | 진실 **`APPROVAL_MALFORMED`**(3, `|c_APP|=2`) → graft 후 **`NO_ROWS_CLEAR`**(직전·`|c_APP|=1`) → **`APPROVAL_MALFORMED`**(CTRL, `|c_APP|=2` 복원) → **`PROVENANCE_UNVERIFIABLE`**(2) | 1/0/1/1 | 4정의 중 `c_APP` | **전건 일치** |
| **1** | **[E8]-U16-2** `.git/info/grafts` (U-16) | CTRL / v2.19-2 | **`NO_ROWS_CLEAR`**(fail-open 잔존) / **`PROVENANCE_UNVERIFIABLE`**(2) | 0/1 | 같음 | **일치** |
| **1** | **[E8]-U16-3** `C_R` 축 (⑮ + 증인 위조 graft) | v2.19-2 / 직전 / CTRL / v2.19-2 | 진실 **`APPROVAL_ORDER_INVALID`**(11) → graft 후 **`NO_ROWS_CLEAR`**(직전 — g6 증인이 «생겼다») → **`APPROVAL_ORDER_INVALID`**(CTRL 복원) → **`PROVENANCE_UNVERIFIABLE`**(2) | 1/0/1/1 | 4정의 중 `C_R` | **전건 일치** |
| **1** | **[E8]-3/U16-4** 정상 회귀 | v2.19-2 | U-17 **`PREVENTION_ACTIVE`**/0 · ⑳ⓐ **`APPROVAL_MALFORMED`**/1 · ⑱ **`NO_ROWS_CLEAR`**/0 · ⑳ⓑ 얕은 클론 **`PROVENANCE_UNVERIFIABLE`**/1 (순서 대조군 **3** — 발산 유지) | — | replace 0 · grafts 부재 · shallow=false ⇒ 불변 | **전건 일치** |
| **2** | **[E9]-(i)** 2-부모 머지 · 머지 blob == 한 부모 | v2.19-2 (∀) | **`PREVENTION_ACTIVE`**(10) — `|P_last|=1` (머지는 도입 아님) | **0** | ∀-부모: 그 부모에서 ∀ 깨짐 → 도입 아님 | **일치** |
| | 〃 | **직전**(∨) | **`PREVENTION_ARTIFACT_MUTATED`**(7) — `P_last=M ⋠ d` | 1 | ∨ 읽기의 값 | **극성 차이 실증 — E9 가 폐기한 자리** |
| **2** | **[E9]-(ii)** 머지 blob 이 둘 다와 다름 | v2.19-2 | **`PREVENTION_ACTIVE`** — `|P_first|=2 · |P_last|=1`(머지가 도입) | **0** | «머지가 도입(정상)» | **일치** |
| **2** | **[E9]-(iii)** 형제 «독립 동일 blob» 도입 후 머지 | v2.19-2 | **`PREVENTION_ARTIFACT_MUTATED`**(7) — `|P_last|=2>1` | 1 | 카디널리티 처분 `>1 → MUTATED` | **일치** |
| **2** | **[E9]-(iv)** 직전 addendum §4-1 [E5]-c 2-부모 graft | 직전 / CTRL / v2.19-2 | **`ARTIFACT_MUTATED`**(7·∨ 모호) → **`LATE`**(6·②) → **`UNVERIFIABLE`**(1·①+②) | 1/1/1 | «이제 결정적» | **일치 — 모호성 소거 실증** |
| **2** | **[E9]-(v)** T-84 ⑨ 사후 편집 | v2.19-2 | **`PREVENTION_ARTIFACT_MUTATED`**(7) — `x_last ⋠ d` | 1 | ⑨ 도달 가능성 유지 | **일치** |
| **3** | **[E9] 상보성** 합성 4종 | v2.19-2 | ① 정상 **ACTIVE**(10) · ② 사후 편집 **MUTATED**(7) · ③ 다중 도입 **MUTATED**(7) · ④ 순서 위반 **LATE**(6) | 0/1/1/1 | ¬LATE 하 ACTIVE/MUTATED **상보·결정적** | **전건 일치 — 4종이 정확히 하나씩** |

**이 파일은 본 저장소의 `PREVENTION_ACTIVE` 를 주장하지 않는다** — 본 저장소 live 는 `PREVENTION_ABSENT`(§4-1 말미)이고 `ACTIVE` 는 전부 SIMULATED seam·픽스처다.

---

## 1. S-24 ① — `git diff e3ed4e78..ad5be1a3 -- <계약>` 전문 + 절 범위 diff 기계 증명

에라타 2차가 닿는 절(hunk **14개** — §1-3 ① 이 기계 파싱한 사상 그대로): **H1** 심사 이력 v2.19 행(:118) · **H2** 변경 이력 v2.19 행(:201) · **H3~H4** §12.3.3 (B) 처분표(에라타 2차 서술 + 실행 증거 열) ·
**H5** `U-15-g-1` `D` 정의(**[E8] 참조 1/4**) · **H6~H9** `P_first`/`P_last` + 두 상태의 «기계 조건» + `U-17-c` 상태표 3행(**[E9]** + **[E8] 참조 3·4/4**) · **H10** `C_R` 정의 꼬리(**[E8] 참조 2/4**) ·
**H11~H12** `U-16-c` `[PARENTS-UNTRUSTED]` 정의 본문(**[E8] 유일 소스**) · **H13** `U-16-d` 전순서 머리(**N-3~5 세 층 주석**) · **H14** `U-16-d` ① 선-검사(**[E8]** 개명 반영).
닿지 «않는» 절은 §1-3 ③ 이 리터럴 grep 으로 위치를 파생해 sha256 으로 대조한다 — **§12.3.4-R 하니스 블록 · §8 T-84/T-82/T-81 행 · (a) 술어 블록 전문(E1 classic terminal 포함) · (b) 리비전 특정 전문 ·
(α) 연속성 술어 전문 · C6 host 결속 블록 · U-17-c 전순서 10단 · U-17-d · U-16-c `c_APP` «수식» · U-16-d 전순서 12단 표 · U-16-d ② g-단락 · U-16-a2 · U-16-h · U-16-b 간선 대응·고아 · U-15-g-4 CORR** — **17건 전부 ∅**.

```diff
diff --git a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
index 4c4f9c85..22be5f33 100644
--- a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+++ b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
@@ -115,7 +115,7 @@
 > | **v2.14** | **`needs-attention` · `NOT_PASSED`** — findings 5 (**high 3 / medium 2**), **전건 채택, 기각 0**. 직전 3건 처분: **#1 부분해소 / #2 부분해소 / #3 «회피» — 아크 최초의 회피 판정**. 잔여·신규 5건: **F1 정직 경계는 과장 철회일 뿐 해소 아님**(§11 이 `CLEAR` 를 완료 허용값으로 소비하는데 예방은 `Phase 1`) + **처분표 (B) 가 마감 전 초안 문구 그대로**(S-22 «7회차») · **F2 복수 D0A-FIRST**(카디널리티 가정) · **F3 digest 선배치**(토큰 도입만 추적) · **F4 «회피»**(append 복구가 조상성에 걸려 전체 계약에서 green 불가·부분 표면 실행기) · **F5 `row_ref` 의 `c_APP` 비단수**. 동결 `db19a0e8` → 증거 `c5359c74` → 에라타 후 재동결 `af61a40e`. `docs/reviews/phase0-completion-contract/20260819-002145/verdict.md` |
 > | **v2.15** | **재심 미도달 — 동결 후 stop-time BLOCK 3회로 재개정.** v2.14 판정 5건을 반영해 `11a56d3e` 로 동결·`b453b4e5` 로 실행 증거까지 기록했으나, **재결속 전에 stop-time 심판이 세 번 BLOCK** 을 내 v2.16(`eb2805a9`)→v2.17(`a3c95b4f`)→v2.18(`5f4b7cfd`)로 재개정됐다. **v2.15~v2.17 은 재결속 전이라 승인 표면을 가진 적이 없다**(v2.9→v2.10 선례). 재결속·레인 B 재심은 **v2.18 에서** 이뤄졌다 |
 > | **v2.18** | **`needs-attention` · `NOT_PASSED`** — findings 6 (**high 3 / medium 3**), **전건 채택, 기각 0**. 직전 5건 처분: **F1 부분해소 / F2 부분해소 / F3 해소됨(계약 수준) / F4 부분해소 / F5 «회피»** — **아크 누적 해소 5**(F3 = 다섯 번째). 신규 2건: **정본 host 미결속**(host 없는 `gh api` 조회 — `GH_HOST` override 로 타 host 응답이 `PREVENTION_ACTIVE` 가능·high) · **두 결속 계획 Phase 0/1 선행관계 충돌**(운영자 게이트·medium). 잔여 F1 은 «보호 off→머지→재활성» 창을 어느 술어도 소비 안 함 + 처분표 (B) 가 «완료 가능성 자체를 막는다»로 과대주장 · F2 는 D0A-FIRST 절이 `diff-filter=A` 규범 잔존 · F4 는 `T-82 ⑱` 입력이 폐지된 `edge_seq` 기재 · F5 는 `c_APP` 단수 정의 잔존. 동결 `5f4b7cfd` → 증거 `7a146466` → 에라타 재동결 `feb91d60` → S-24 addendum `540ff0e3` → 재결속 `81d532ff`. `docs/reviews/phase0-completion-contract/20260819-074621/verdict.md` |
-> | **v2.19** | **재심 미착수.** v2.18 판정 6건을 반영한 판이며, **동결(`d5a8302a`) → 증거 실행(`90a5ce7d` — 계약 결함 후보 E1~E7 적발) → 에라타 정정 후 재동결**(재결속 전이므로·v2.15/v2.18 선례) → **운영자 재결속(현행 사이클)** 대기다. 재결속 전에는 심사를 요청하지 않는다(§12.3.2) |
+> | **v2.19** | **재심 미착수.** v2.18 판정 6건을 반영한 판이며, **동결(`d5a8302a`) → 증거(`90a5ce7d` — E1~E7 적발) → 에라타 재동결(`e3ed4e78`) → addendum(`197f4fe4` — [PARENTS-UNTRUSTED]/P 결함 E8~E9 적발) → 에라타 2차 정정 후 재동결**(재결속 전이므로·v2.15/v2.18 선례) → **운영자 재결속(현행 사이클)** 대기다. 재결속 전에는 심사를 요청하지 않는다(§12.3.2) |
 >
 > **[v2.7 갱신 — 6e 는 "고쳐졌다가 다시 만료되는" 축이다]** 아래 v2.1·v2.4 서술은
 > **당시 상태의 기록**이며 현행 상태가 아니다. **6e 를 "완료/미완료"의 1회성 축으로
@@ -198,7 +198,7 @@
 | v1.1 | §3.0 신설 — 해당 작업이 `acd45c43`에서 수행돼 `15d48f72`에서 팬텀 할당으로 revert된 이력 확인 |
 | v1.2 | 심판 10건 반영. §3.0 인용에 사실 오류(F-1), §6.3이 선행 구현 누락(F-5), §4.2가 없는 열 참조(F-3) |
 | v1.3 | 재심 8건 + **운영자 결정 2건** 반영. **F-2를 "회피"로 판정받아 30/30을 거버넌스 트랙으로 정식 이관**. Phase 0 범위를 기계 검사 가능 축으로 축소하고 **불가 축을 §13 레지스터로 명시 노출**. T-3c 공집합 결함 수정 |
-| **v2.19** | **v2.18 심판 판정 6건(high 3 / medium 3) 전건 반영. 직전 처분은 «F1·F2·F4 부분해소 · F3 해소됨(계약 수준) · F5 회피» 이고 신규 2는 host 미결속·두 결속 계획 충돌이다.** ① **#1 F1 (high) — 보호 해제 창**: 진입·완료 두 live 조회 사이 [보호 off→체크 통과→머지→재활성] 창을 **어느 술어도 소비 안 했고**, (B) 표가 «완료 가능성 자체를 막는다»고 **과대주장**했다. **과대주장 철회** + **연속성 소비자 신설**(완료 판정 시점 — 적용 룰셋 `created_at`/`updated_at` > `t_land`[= D 착지 PR 의 서버 `merged_at` 최소]이면 `PREVENTION_CONTINUITY_UNVERIFIABLE`·운영자 재심사 · classic-only[타임스탬프 부재]도 판정 불가로 차단 · 삭제-재생성은 새 id·created_at 로 검출). **극성**: 관측만 하고 통과시키면 창이 정상 완료로 세탁되고 무조건 영구 차단하면 정당한 강화를 막는다 — **판정 불가를 «판정 불가»로 보고**하는 것이 fail-closed(F2 동형). **서버 시간만 소비**(커밋 시각 불신). **정직 경계**: «룰셋 미변경» 우회(연속 bypass_actors·admin override)는 감사 로그 소관이라 **못 닫는다** — «부분해소»이지 «닫힌다»가 아니다. T-84 ⑪(off→merge→on 은 서버 설정 변경 요구 → SIMULATED seam·live 는 현행 음성만) ② **#2 host 미결속 (high, 신규)**: 모든 `gh api repos/{owner}/{repo}/…` 가 host 없이 나가 `GH_HOST` 를 바꾸면 **타 host `/api/v3` 응답으로 `PREVENTION_ACTIVE` 위조** 가능(심판 실측 프로브). **host 를 계약 핀에서 파생해 «명령에 명시»**(`gh api --hostname <핀 host>`) + **소비자 자기 환경 `GH_HOST` 재핀**(플래그·환경 이중 결속 — 우선순위 의존 안 함) + `gh auth status --hostname <핀 host>` 전제. **극성**: 도달 불가 = `PREVENTION_UNVERIFIABLE`(타 host 폴백 없음). 아티팩트 선언 아님(C3 규율). T-84 ⑫(GET-only·live) ③ **#3 F2 (high) — D0A-FIRST 규범 잔존**: 앞선 D0A-FIRST 절이 «모호 없이 한 커밋»·`git log --diff-filter=A` 를 **판정 규범**으로 유지해(S-22) 구조 `D`(U-15-g-1)와 병존했다. **판정 소비 자리를 구조 `D` 참조로 전환**하고 «다중 후보 문제가 여기서 발생 안 함» 단정을 **철회**(gg/gu/uu 로 `D` 크기>1). **편의 표기(∅ 확인·단일 픽스처)와 판정 소비를 구별해 명시** — §12.3.4-G 의 `diff-filter=A` 는 편의 표기로만. 재기술→참조로 stale 클래스 제거(S-14) ④ **#4 F4 (medium) — T-82 ⑱ 입력 stale + 계약 밖 규칙**: ⑱ 이 **폐지된 `edge_seq` 기재**(«각각 seq=1 부여»)를 지시했고 손 실행기가 «사전순 최소·상태 우선순위»를 **자체 선언**했다(`U16-LEDGER-CHECK.md:34-48`). **⑱ 을 현행 스키마로 재기술**(edge_seq 미기재·소비자 표시용 파생) + **U-16-d 상태 전순서·규칙 평가 순서를 계약 리터럴로 고정**(전순서 12단·«전부 평가 후 최소» 의미 — 자체 선언 흡수) ⑤ **#5 F5 (medium, 회피) — 단수 `c_APP`**: `row_ref` 만 없앴고 같은 비단수 `c_APP` 가 U-16-c·g5·g6 에 단수로 잔존했다(형제 동일 행 독립 도입 시 선택 재량). **`c_APP` 를 구조 집합 정의**(`D`·`C_R` 동형: `{x⊑HEAD : a∈rows(x:LEDGER) ∧ ∀p∈parents(x): a∉rows(p:LEDGER)}`)·`c_APP` 크기 0→`PROVENANCE_UNVERIFIABLE`·크기>1→`APPROVAL_MALFORMED`·크기 1→유일 원소·세 소비처 일관. **극성**: 동일 승인 행 병렬 도입은 «언제 승인»이 유일하지 않아 차단(U-15-g-2 동형)·«사전순 최소»는 판정 불가를 답한 척한다. T-82 ⑳(형제 동일 행→MALFORMED)·⑱(서로 다른 행→green) 상호 배타 ⑥ **#6 두 결속 계획 충돌 (medium, 운영자 게이트)**: 개발계획 Phase 1 작업 7·종료조건(required CI·branch protection 증거) vs 계약 U-17 D0-A 착수 선행조건. **계약이 «함께 착수 불가» 정직 표기** + §12.3.3 (D) 에 **적용 준비된 개정안 문안**(tos-gate 도입을 Phase 0 로 이관·Phase 1 종료조건은 «U-17 연속성 유지»로 — verbatim diff). **개발계획 자체는 무편집** — 정식 개정은 운영자 소관(`bound_paths`·O-6 재결속 시 함께 심사). **종수 전파(S-20)**: T-84 10→**12종**(⑪·⑫) · T-82 19→**20종**(⑳) · T-81 19 불변 · U-17-c 9값→**10값/차단 9/전순서 10단** · U-16-d **전순서 12단 신설**. **§12.3.3 (A)=v2.18 판정 5건 처분·(B)=v2.19 6건 주장(«어느 것도 해소 아님»)·(B) 실행 증거 열 현행화**(직전 `20260819-002145` 증거 명시·신규는 «동결 후 실행»). **S-22 스윕**: 처분표 (A)(B)·§0 요약·심사 이력·변경 이력·§11·D0A-FIRST 절 전파. **[독립 검증 마감(실행 픽스처) 3건]**: (i) **S-22 재발 1건 정정** — U-16-b 의 v2.15 산문 «[F5 소멸] `c_APP` 비단수도 함께 소멸»이 v2.19 구조 정의(단수 잔존→처분)와 모순 → `row_ref`·tombstone 축만 소멸로 정정 (ii) **U-16-d 규칙 평가 순서 동치 주장 정정** — 「전 규칙 상태번호 비감소」는 거짓(구조 상태 2 `c_APP` 크기 0 < 3 MALFORMED)이라 **구조 선-검사 1·2·4 를 g-규칙 앞 필수 단계로 재배치**하고 동치는 g-단락 5~11 로 한정 · **T-82 ⑳ⓑ**(발산 corner·종수 불변) 신설 (iii) **target_branch 파생의 host 없는 `gh api` 잔재 → C6 참조 전환**(S-14). **[v2.19 에라타 (동결 `d5a8302a` 후 증거 실행 `90a5ce7d` 적발 — 재결속 전이므로 정정 후 재동결·v2.15/v2.18 선례)]** 증거가 계약 결함 후보 7건을 적발했다(실행기는 계약대로 발화했으나 계약 «문언»이 死분기·공백·실행기 독해와 갈린 자리): **ⓐ E1 (U-17 실질)** classic disjunct 死분기 — `D≠∅` 이면 classic-only 는 (a) 통과해도 연속성(룰셋 타임스탬프 의존)이 항상 9 발화 → «classic 은 진입 가능·완료 불가, 완료 인정 경로는 룰셋»을 (a) 옆에 정직 명시(disjunct 철회 아님·fail-closed terminal)·양성 대조군 룰셋 기반 · **ⓑ E2 (U-17 공백)** `t_land` 파생 불가 시 (α) 처분 미정의 → `CONTINUITY_UNVERIFIABLE`(fail-closed·(b) 8 이 전순서상 이겨 방출 불변이나 정의는 닫음)·타임스탬프 파싱 불가도 명시 · **ⓒ E3 (U-17 관측/문언)** gh 2.93.0 실측 `--hostname` 이 `GH_HOST` 를 이김 → 「의존하지 않는 이중결속」을 「플래그 우선 실측·재핀은 방어적 중복」으로 정정 · `responder=file:` auth 전제 «기록만» · 아티팩트 `host` 키 «선택»(v2.18 E2 동형) · 타 host ACTIVE 위조는 GET-only 라 직접 실증 불가 = ⑫ 는 「상태 불변+nohost→UNVERIFIABLE」로만 검증(정직 경계) · **ⓓ E4 (U-16 실질)** T-82 ⑱ 리터럴 «별개 `row_id`» 가 g2·간선 대응과 충돌(리터럴 픽스처는 MALFORMED/1 = 정반대) → «같은 `row_id`, 서로 다른 승인 행(transition·근거 다름)»으로 정정(S-22: 정정을 적는 것과 전파는 별개) · **ⓔ E5 (U-16 실질)** `c_APP` 정의가 «진짜 루트»와 «얕은 클론 경계(부모 미상)»를 미구별 → 리터럴 파생에서 경계커밋이 루트로 읽혀 `c_APP` 크기 1(fail-open) → **[SHALLOW] 단서 신설**(경계 = 부모 미상 → 도입 지점 확정 안 함 → `PROVENANCE_UNVERIFIABLE`)·**동형 정의 전수 적용**(`C_R`·`D`·`P_first`/`P_last` 가 [SHALLOW] 참조·플래그 의존 클래스 동형 규율) · **ⓕ E6 (U-16 공백)** 선-검사 2 「얕은 클론」을 전역 단축으로 읽으면 ⑳ⓑ 대조군 구별력 상실 → 「경계 커밋이 해당 행/간선 도입 후보 우주에 있어 크기 0일 때」로 국소화 · **ⓖ E7 (U-16 공백)** 한 간선 다수 후보 상태 귀속(=대응 후보 전순서 최소·D-4)·「고아」 구조 정의(=같은 row_id∧g1 일치 간선 0·규칙 탈락 행은 그 규칙 상태 귀속·D-5, `ORDER_INVALID`→`MALFORMED` 오귀속 방지) 고정. **증거 결속(S-24)**: 이 에라타 재동결에 대해 **addendum 으로 이행**(절 범위 `git diff` 공집합 증명 + 영향 변이 재실행 — §5 산출 목록). **종수 불변**(E1~E7 은 문언 정정·⑳ⓑ 는 기존 하위 케이스). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`)·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
+| **v2.19** | **v2.18 심판 판정 6건(high 3 / medium 3) 전건 반영. 직전 처분은 «F1·F2·F4 부분해소 · F3 해소됨(계약 수준) · F5 회피» 이고 신규 2는 host 미결속·두 결속 계획 충돌이다.** ① **#1 F1 (high) — 보호 해제 창**: 진입·완료 두 live 조회 사이 [보호 off→체크 통과→머지→재활성] 창을 **어느 술어도 소비 안 했고**, (B) 표가 «완료 가능성 자체를 막는다»고 **과대주장**했다. **과대주장 철회** + **연속성 소비자 신설**(완료 판정 시점 — 적용 룰셋 `created_at`/`updated_at` > `t_land`[= D 착지 PR 의 서버 `merged_at` 최소]이면 `PREVENTION_CONTINUITY_UNVERIFIABLE`·운영자 재심사 · classic-only[타임스탬프 부재]도 판정 불가로 차단 · 삭제-재생성은 새 id·created_at 로 검출). **극성**: 관측만 하고 통과시키면 창이 정상 완료로 세탁되고 무조건 영구 차단하면 정당한 강화를 막는다 — **판정 불가를 «판정 불가»로 보고**하는 것이 fail-closed(F2 동형). **서버 시간만 소비**(커밋 시각 불신). **정직 경계**: «룰셋 미변경» 우회(연속 bypass_actors·admin override)는 감사 로그 소관이라 **못 닫는다** — «부분해소»이지 «닫힌다»가 아니다. T-84 ⑪(off→merge→on 은 서버 설정 변경 요구 → SIMULATED seam·live 는 현행 음성만) ② **#2 host 미결속 (high, 신규)**: 모든 `gh api repos/{owner}/{repo}/…` 가 host 없이 나가 `GH_HOST` 를 바꾸면 **타 host `/api/v3` 응답으로 `PREVENTION_ACTIVE` 위조** 가능(심판 실측 프로브). **host 를 계약 핀에서 파생해 «명령에 명시»**(`gh api --hostname <핀 host>`) + **소비자 자기 환경 `GH_HOST` 재핀**(플래그·환경 이중 결속 — 우선순위 의존 안 함) + `gh auth status --hostname <핀 host>` 전제. **극성**: 도달 불가 = `PREVENTION_UNVERIFIABLE`(타 host 폴백 없음). 아티팩트 선언 아님(C3 규율). T-84 ⑫(GET-only·live) ③ **#3 F2 (high) — D0A-FIRST 규범 잔존**: 앞선 D0A-FIRST 절이 «모호 없이 한 커밋»·`git log --diff-filter=A` 를 **판정 규범**으로 유지해(S-22) 구조 `D`(U-15-g-1)와 병존했다. **판정 소비 자리를 구조 `D` 참조로 전환**하고 «다중 후보 문제가 여기서 발생 안 함» 단정을 **철회**(gg/gu/uu 로 `D` 크기>1). **편의 표기(∅ 확인·단일 픽스처)와 판정 소비를 구별해 명시** — §12.3.4-G 의 `diff-filter=A` 는 편의 표기로만. 재기술→참조로 stale 클래스 제거(S-14) ④ **#4 F4 (medium) — T-82 ⑱ 입력 stale + 계약 밖 규칙**: ⑱ 이 **폐지된 `edge_seq` 기재**(«각각 seq=1 부여»)를 지시했고 손 실행기가 «사전순 최소·상태 우선순위»를 **자체 선언**했다(`U16-LEDGER-CHECK.md:34-48`). **⑱ 을 현행 스키마로 재기술**(edge_seq 미기재·소비자 표시용 파생) + **U-16-d 상태 전순서·규칙 평가 순서를 계약 리터럴로 고정**(전순서 12단·«전부 평가 후 최소» 의미 — 자체 선언 흡수) ⑤ **#5 F5 (medium, 회피) — 단수 `c_APP`**: `row_ref` 만 없앴고 같은 비단수 `c_APP` 가 U-16-c·g5·g6 에 단수로 잔존했다(형제 동일 행 독립 도입 시 선택 재량). **`c_APP` 를 구조 집합 정의**(`D`·`C_R` 동형: `{x⊑HEAD : a∈rows(x:LEDGER) ∧ ∀p∈parents(x): a∉rows(p:LEDGER)}`)·`c_APP` 크기 0→`PROVENANCE_UNVERIFIABLE`·크기>1→`APPROVAL_MALFORMED`·크기 1→유일 원소·세 소비처 일관. **극성**: 동일 승인 행 병렬 도입은 «언제 승인»이 유일하지 않아 차단(U-15-g-2 동형)·«사전순 최소»는 판정 불가를 답한 척한다. T-82 ⑳(형제 동일 행→MALFORMED)·⑱(서로 다른 행→green) 상호 배타 ⑥ **#6 두 결속 계획 충돌 (medium, 운영자 게이트)**: 개발계획 Phase 1 작업 7·종료조건(required CI·branch protection 증거) vs 계약 U-17 D0-A 착수 선행조건. **계약이 «함께 착수 불가» 정직 표기** + §12.3.3 (D) 에 **적용 준비된 개정안 문안**(tos-gate 도입을 Phase 0 로 이관·Phase 1 종료조건은 «U-17 연속성 유지»로 — verbatim diff). **개발계획 자체는 무편집** — 정식 개정은 운영자 소관(`bound_paths`·O-6 재결속 시 함께 심사). **종수 전파(S-20)**: T-84 10→**12종**(⑪·⑫) · T-82 19→**20종**(⑳) · T-81 19 불변 · U-17-c 9값→**10값/차단 9/전순서 10단** · U-16-d **전순서 12단 신설**. **§12.3.3 (A)=v2.18 판정 5건 처분·(B)=v2.19 6건 주장(«어느 것도 해소 아님»)·(B) 실행 증거 열 현행화**(직전 `20260819-002145` 증거 명시·신규는 «동결 후 실행»). **S-22 스윕**: 처분표 (A)(B)·§0 요약·심사 이력·변경 이력·§11·D0A-FIRST 절 전파. **[독립 검증 마감(실행 픽스처) 3건]**: (i) **S-22 재발 1건 정정** — U-16-b 의 v2.15 산문 «[F5 소멸] `c_APP` 비단수도 함께 소멸»이 v2.19 구조 정의(단수 잔존→처분)와 모순 → `row_ref`·tombstone 축만 소멸로 정정 (ii) **U-16-d 규칙 평가 순서 동치 주장 정정** — 「전 규칙 상태번호 비감소」는 거짓(구조 상태 2 `c_APP` 크기 0 < 3 MALFORMED)이라 **구조 선-검사 1·2·4 를 g-규칙 앞 필수 단계로 재배치**하고 동치는 g-단락 5~11 로 한정 · **T-82 ⑳ⓑ**(발산 corner·종수 불변) 신설 (iii) **target_branch 파생의 host 없는 `gh api` 잔재 → C6 참조 전환**(S-14). **[v2.19 에라타 (동결 `d5a8302a` 후 증거 실행 `90a5ce7d` 적발 — 재결속 전이므로 정정 후 재동결·v2.15/v2.18 선례)]** 증거가 계약 결함 후보 7건을 적발했다(실행기는 계약대로 발화했으나 계약 «문언»이 死분기·공백·실행기 독해와 갈린 자리): **ⓐ E1 (U-17 실질)** classic disjunct 死분기 — `D≠∅` 이면 classic-only 는 (a) 통과해도 연속성(룰셋 타임스탬프 의존)이 항상 9 발화 → «classic 은 진입 가능·완료 불가, 완료 인정 경로는 룰셋»을 (a) 옆에 정직 명시(disjunct 철회 아님·fail-closed terminal)·양성 대조군 룰셋 기반 · **ⓑ E2 (U-17 공백)** `t_land` 파생 불가 시 (α) 처분 미정의 → `CONTINUITY_UNVERIFIABLE`(fail-closed·(b) 8 이 전순서상 이겨 방출 불변이나 정의는 닫음)·타임스탬프 파싱 불가도 명시 · **ⓒ E3 (U-17 관측/문언)** gh 2.93.0 실측 `--hostname` 이 `GH_HOST` 를 이김 → 「의존하지 않는 이중결속」을 「플래그 우선 실측·재핀은 방어적 중복」으로 정정 · `responder=file:` auth 전제 «기록만» · 아티팩트 `host` 키 «선택»(v2.18 E2 동형) · 타 host ACTIVE 위조는 GET-only 라 직접 실증 불가 = ⑫ 는 「상태 불변+nohost→UNVERIFIABLE」로만 검증(정직 경계) · **ⓓ E4 (U-16 실질)** T-82 ⑱ 리터럴 «별개 `row_id`» 가 g2·간선 대응과 충돌(리터럴 픽스처는 MALFORMED/1 = 정반대) → «같은 `row_id`, 서로 다른 승인 행(transition·근거 다름)»으로 정정(S-22: 정정을 적는 것과 전파는 별개) · **ⓔ E5 (U-16 실질)** `c_APP` 정의가 «진짜 루트»와 «얕은 클론 경계(부모 미상)»를 미구별 → 리터럴 파생에서 경계커밋이 루트로 읽혀 `c_APP` 크기 1(fail-open) → **[PARENTS-UNTRUSTED] 단서 신설**(1차 신설명 [SHALLOW]; 경계 = 부모 미상 → 도입 지점 확정 안 함 → `PROVENANCE_UNVERIFIABLE`)·**동형 정의 전수 적용**(`C_R`·`D`·`P_first`/`P_last` 가 [PARENTS-UNTRUSTED] 참조·플래그 의존 클래스 동형 규율) · **ⓕ E6 (U-16 공백)** 선-검사 2 「얕은 클론」을 전역 단축으로 읽으면 ⑳ⓑ 대조군 구별력 상실 → 「경계 커밋이 해당 행/간선 도입 후보 우주에 있어 크기 0일 때」로 국소화 · **ⓖ E7 (U-16 공백)** 한 간선 다수 후보 상태 귀속(=대응 후보 전순서 최소·D-4)·「고아」 구조 정의(=같은 row_id∧g1 일치 간선 0·규칙 탈락 행은 그 규칙 상태 귀속·D-5, `ORDER_INVALID`→`MALFORMED` 오귀속 방지) 고정. **증거 결속(S-24)**: 이 에라타 재동결에 대해 **addendum 으로 이행**(절 범위 `git diff` 공집합 증명 + 영향 변이 재실행 — §5 산출 목록). **종수 불변**(E1~E7 은 문언 정정·⑳ⓑ 는 기존 하위 케이스). **[v2.19 에라타 2차 (재동결 `e3ed4e78` 후 S-24 addendum `197f4fe4` 적발 — 재결속 전이므로 정정 후 재동결)]** addendum 이 [SHALLOW] 자체의 결함 2건을 적발했다: **ⓗ E8 (U-16 실질·fail-open)** `git replace --graft`(및 `.git/info/grafts`)가 [SHALLOW] 리터럴 3판별(`--is-shallow-repository=false`·`.git/shallow` 부재·부모 객체 present)을 **전부 통과**하면서 `git log --format=%P`·`rev-list`·`merge-base` 등 replace 를 따르는 명령이 «가짜» 부모를 반환 → 같은 seam 에서 `PREVENTION_LATE`(6)→`PREVENTION_ACTIVE`(10) 극성 전환 실측(`GIT_NO_REPLACE_OBJECTS=1` 에서는 진짜 부모). [SHALLOW] 가 닫으려던 클래스는 «부모 집합 신뢰 불가»이고 얕은 클론은 한 사례 → **[SHALLOW]→[PARENTS-UNTRUSTED] 일반화·개명**(부모 «재작성» 축 추가) + **이중 판별**(① 관측: `git replace -l` 공집합 ∧ `.git/info/grafts` 부재 ∧ 얕은 클론 아님 → 위반 시 `PROVENANCE_UNVERIFIABLE`/`PREVENTION_UNVERIFIABLE` · ② 무력화: 조상·부모 파생 `git` 전부 `--no-replace-objects` 고정) · 극성 = «부모 신뢰 불가면 도입 지점 확정 불가 → 판정 불가를 판정 불가로»(E5 동형·fail-closed) · 유일 소스(U-16-c)에서만 고치고 동형 4곳(`D`·`C_R`·`c_APP`·`P_first`/`P_last`)은 참조(재기술 금지). **개명 스윕(S-22)**: 활성 태그 8곳 개명·역사 참조 2곳(정의 헤더 «구 [SHALLOW]»·ⓔ «1차 신설명 [SHALLOW]») 보존 · **ⓘ E9 (U-17 문언 공백·극성)** `P_last`(및 `P_first`) 의 다부모 의미 미규정 — 실행기가 ∨(«어느 한 부모와라도 다름»)로 읽어 2-부모 graft 에서 `ARTIFACT_MUTATED`(7)↔`ACTIVE`(10) 극성 분기. `c_APP`·`C_R`·`D` 는 ∀-부모인데 P 만 비대칭(S-22 계열) → **P_first/P_last 를 D·C_R·c_APP 와 ∀-부모 «동형 구조 정의»로 고정**(도입지점(b) = ∀부모에 blob≠b 인 x · P_last = 현행 blob 도입 집합 · P_last 크기 0→UNVERIFIABLE·>1→ARTIFACT_MUTATED[c_APP 크기>1 동형·보수]·1→유일 원소) · 머지는 «∀부모 다름»일 때만 도입(한 부모와 같으면 도입 아님) · 상태 조건(LATE/MUTATED/ACTIVE)을 집합 위에서 결정적으로 재정의(ACTIVE·MUTATED 는 ¬LATE 하 상보·`T-84 ⑨` 도달 유지). **N-3~5(관측·비차단)**: «전순서 최소»가 규칙 간·후보 간·전역 3층에서 같은 규칙임을 U-16-d 에 한 줄 명시. **증거 결속(S-24)**: 이 2차 에라타 재동결도 **addendum 2차로 이행**(절 범위 `git diff` 공집합 + 영향 변이 재실행). **종수 불변**(E8~E9 은 문언 정정·개명·동형화). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`)·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
 | **v2.18** | **stop-time Codex BLOCK #3 5건 반영 — «v2.17 은 여전히 wrong-target·forged-gate 를 ACTIVE 로 승인한다».** ① **C1 (a) 가 required check «정체성»을 안 봤다** — `contexts` 의 **이름만** 검사해 **`tos-gate` 를 제3자 앱에 고정하면 (a) 통과**했고 `D=∅` 이면 (b) 가 생략돼 그대로 진입 승인(심판이 실행기 술어로 `prot_ok=True` 재현). → **`required_status_checks.checks[]` 의 그 컨텍스트 `app_id` == Actions app id**(룰셋은 `integration_id`) ② **C2 `app.id` 는 정본 워크플로를 식별하지 않는다** — **모든 Actions 잡이 같은 app id 를 갖고 한 suite 를 공유**한다(실측 PR #636 head 5 run 전부 동일). → **`gate_app_id` 파라미터 «폐지»**하고 `gh api apps/github-actions .id` 로 **서버 파생**(전역 상수를 아티팩트가 선언하면 그것이 위조 표면) + **워크플로 정체성 3중 결속**(run `path` == 계약 리터럴 `.github/workflows/tos-gate.yml` ∧ run `head_sha` == PR head ∧ **그 시점 워크플로 blob 이 하니스 호출·sha256 검증 스텝 포함**). **한계 정직 표기**: 3중은 **위조 비용을 올리지 «닫지» 않는다** — «서버가 그 파일 내용을 그대로 실행했다»는 공개 REST 로 증명 불가 ③ **C3 대상 결속 자기선택** — `remote_name` 을 **같은 아티팩트가 골랐고** 정규화가 **host 를 버려** 비-GitHub 동일 경로가 같은 값이 됐다. → **정본 host+owner/repo 를 계약 자체에 핀**(`github.com/kakao-harris-lee/kis_unified_sts` — `bound_paths` 안이라 **리뷰·재결속으로 보호**되고 **아티팩트는 선언하지 않는다**) · 정규화 **host 보존** · `git remote` 는 파생이 아니라 **«핀과 일치하는 원격이 존재하는가»의 대조**(원격 «이름»은 묻지 않는다) ⇒ **`remote_name` 폐지** ④ **C4 아티팩트 사후 편집** — 파라미터·countersign 은 HEAD 에서 읽으면서 순서는 **«최초 도입 P»** 만 봐 **P → 착수 → 편집**이 통과했다. → **`P_last`**(마지막 변경 커밋·구조 파생)로 바꾸고 `∀d∈D: P_last ⊰ d` ∧ 소비 blob == `P_last` 시점 blob. 위반 = **`PREVENTION_ARTIFACT_MUTATED`**(신설). **`LATE` 로 접지 않는 근거**: «순서가 늦다»는 순서를 고치면 되고 «착수 후 고쳤다»는 **그 편집이 무엇을 바꿨는지 재심사**해야 한다 ⑤ **C5 증거 결속** — v2.17 증거가 동결 `a3c95b4f` 에 결속됐는데 에라타 `75474351` 이 계약을 바꿔 **증거가 «이전 계약»을 검증한 상태**로 남았다. → **`S-24` 신설**(에라타 후 **재실행** 또는 **`git diff <freeze>..<errata>` 가 해당 절 범위에서 공집합임을 기계 증명**). **이번 판의 증거는 v2.18 «최종 동결 후»에 만든다**. **[v2.18 에라타 (동결 `5f4b7cfd` 후 증거 실행 `7a146466` 적발 — T-84 ①~⑩ 전건 기대 일치·S-24 결속 수록)]** ⓐ **E1 (실질)** — (b) ③ 의 워크플로 blob 검증이 **로컬 `git show <PR head>:…`** 를 전제해, squash·rebase 착지에서 **판정 저장소가 PR head 커밋을 보유하지 않으면**(실측: PR #636 head `7656259d` 로컬 미보유) **정직한 착지도 항상 red** 였다 → **`gh api repos/{pin}/contents/…?ref=<PR head.sha>`(서버 조회·base64 decode 후 두 리터럴 grep)** 로 전환, 404/HTTP → `UNVERIFIED_REVISION` · 네트워크/인증 → `UNVERIFIABLE`. **진실 원천이 서버라는 U-17 원칙과 정합**하며 로컬 `git show` 는 **보조 대조(선택)** ⓑ **E2 (문언 충돌)** — «아티팩트는 `canonical_target` 을 선언하지 않는다»(C3)와 §8 ⑤ 의 «선언 불일치 = MISMATCH» 가 충돌해 보였다 → **아티팩트의 `owner_repo`·`target_branch` 키는 «선택»**(있으면 대조·불일치 = MISMATCH / 없으면 핀·`default_branch` 가 유일 소스)으로 고정. **극성 서술**: 선택으로 둬도 약해지지 않는다 — 두 경우 모두 조회 대상은 핀이고 선언은 **추가 대조**일 뿐 대상을 «고를» 수 없다 ⓒ **E3** — 핀 일치 원격 «존재» 대조가 **비-핀 원격 공존을 허용**함은 **의도**임을 명시(«원격 이름·개수는 묻지 않는다 — 조회 대상은 핀이지 원격이 아니다»·포크/미러를 두는 정상 작업을 막지 않는다). **상태 8값 → 9값 / 차단 8 / 전순서 9단 · T-84 6종 → 10종**(⑦ 타 앱 고정 · ⑧ same-app wrong-workflow · ⑨ 아티팩트 사후 편집 · ⑩ 타 원격·타 호스트). **하니스 byte-identical·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
 | **v2.17** | **stop-time Codex BLOCK 3건 반영 — «U-17 이 잘못된 보호 대상과 비강제 체크를 ACTIVE 로 승인할 수 있다».** v2.16 은 **재결속 전이라 승인 표면을 가진 적이 없다.** ① **B1 — 대상 미결속**: `owner_repo`·`target_branch` 를 **아티팩트 선언값 그대로** 쓰고 실행기가 **형식만** 검사해, 실제 `origin`·정본 착지 브랜치와 결속되지 않았고 **`D = ∅` 이면 «임의 대상의 보호»만으로 진입 승인**됐다. 교정: `owner_repo` 는 **`git remote get-url origin` 파생**(원격 이름은 파라미터·기본 `origin`), `target_branch` 는 **`gh api repos/{o}/{r}` 의 `.default_branch`** 파생 — **선언값은 «대조 대상»으로 강등**하고 불일치 = **`PREVENTION_TARGET_MISMATCH`**(신설). `D ≠ ∅` 이면 **(b) 의 PR `base` == target 과 3중 일치**. **새 상태값인 근거**: `INSUFFICIENT` 로 접으면 «맞는 대상인데 약하다»와 «엉뚱한 대상을 봤다»가 같은 값이 되고 **운영자가 할 일이 완전히 다르다** ② **B2 — 논증 철회**: v2.16 의 «보호 꺼진 창의 커밋에는 흔적이 없다»는 **불성립이며 철회**한다 — **PR 체크는 보호 설정과 독립 실행**되므로 보호를 끄고 체크를 통과시켜 머지한 뒤 재활성하면 **정상 흔적이 남는다**. 그리고 **`app.id` 미검증**이라 제3자 앱이 `tos-gate` success 를 **위조 게시**할 수 있었다. 교정: check-run 검증에 **`app.id`(기본 `15368` = GitHub Actions·오늘 `main` 실측값)·`head_sha`·`check_suite` 귀속** 추가. **(b) 의 정확한 진술로 재저작**: 증명하는 것은 «그 리비전에서 서버가 게이트를 실행해 통과했다»이고, «머지 «시점»에 보호가 강제 중이었다»는 **공개 REST 로 사후 증명 불가**(감사 로그는 org/enterprise 소관)다. 잡는 것(체크 실패·부재 / 직접 push / 위조 success)을 열거하고 **남는 것 = «보호 off 상태에서 체크는 통과한 리비전 착지»** 를 **닫지 못함으로 명시**. **완화 2종**: (α) 룰셋 `created_at ≤ merged_at(min D)` 요구 + `updated_at > merged_at` 은 **차단이 아니라 관측 기록**(정당한 정책 개선까지 막는 과잉 차단 방지) (β) **예방 주체는 서버 자체**·`UNCHK-008` 잔존·**강제 «연속성» 증명은 감사 로그 확보 시 승격**. **«흔적 없음» 류 문장 전수 제거** ③ **B3 — S-22**: §8 `T-84` 행이 **에라타 E2 이후에도** `rulesets=[]`·«머지 커밋 check-runs 0»·«pulls 공집합»을 유지해 **같은 턴 실측과 충돌**했다(E2 가 #5 근거만 고치고 이 행을 안 봤다) → **행 전체 재작성** + **⑤ target 불일치**·**⑥ `app_id` 위조** 신설 ⇒ **T-84 4종 → 6종**. **상태 7값 → 8값 / 차단 7 / 전순서 8단.** **[v2.17 에라타 (동결 `a3c95b4f` 후 증거 실행 `6bad7c23` 적발 — 재결속 전 정정)]** ⓐ **E1 (S-22)** — §8 `T-84` ① 이 «작업 브랜치 → 404 → `PREVENTION_ABSENT`» 를 유지했으나, **v2.17 에서 `target_branch` 가 `default_branch` 로 «파생»되므로 그 구성은 ⑤(`TARGET_MISMATCH`)** 이고 **실행기로 재현되지 않는다**. **B1 의 파생 전환이 이 행에 미전파**된 것이며, ① 은 «선언 == 파생(`main`) → `INSUFFICIENT`» 로만 두고 404 는 **«raw probe 관측»으로 강등**했다 ⓑ **E2 (리터럴 고정 3건)** — 원격 URL **정규화 규칙**(https/ssh/scp 형식 → `<owner>/<repo>`·`.git` 제거·형식 밖 = 차단) · **`check_suite` «귀속 일치»의 구체**(check-run 의 `check_suite.id` 가 가리키는 suite 의 `head_sha` == PR `head.sha` — 산문으로 두면 구현마다 다르게 읽는다) · 아티팩트 키 이름 **`remote_name`**(기본 `origin`)·**`gate_app_id`**(기본 `15368`). **증거 실행 결과**: ⑤ **live `TARGET_MISMATCH`(`D=∅`)** · ⑥ `app.id` 위조 red · ① `main` `INSUFFICIENT` · ③ live — **전건 기대 일치**. **하니스 byte-identical·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
 | **v2.16** | **stop-time Codex 심판 BLOCK 2건 반영. 중심은 «U-17 의 진실 원천을 저장소에서 서버로 옮긴 것».** v2.15 는 **재결속 전이라 승인 표면을 가진 적이 없다**(v2.9→v2.10 선례). ① **BLOCK ① — S-22 미전파**: `U-17` 이 7c/8 결속을 **주장**했으나 **§12.3 실행 착수 절차 텍스트는 여전히 `U-15` 만 요구**하고 `prevention_control_state` 를 언급하지 않았다. 7c·8 텍스트에 **live `PREVENTION_ACTIVE`** 를 명시 소비로 추가하고 진입 조건을 **논리곱 셋**으로 확정 ② **BLOCK ② — 자기신고 검증**: `PREVENTION_ACTIVE` 가 **비인증 저장소 내 자기신고 + 커밋 조상성**만 봐 **실제·현재 브랜치 보호를 보지 않았고**, **양성 테스트가 모의 문자열을 스스로 쓰고 ACTIVE 를 냈다** ⇒ **거짓 주장·countersign 후 보호 해제가 green**. 교정: **진실 원천을 서버로** — 별도 실행기 **`u17-verify`** 가 **인증 API 로 live 조회**(`branches/{t}/protection` + 룰셋)하고 raw 응답을 transcript 에 verbatim 수록, 술어(**TOS 게이트 체크 ∈ contexts ∧ strict ∧ enforce_admins ∧ force-push/deletion 불허 ∧ PR 필수**)를 캡처된 응답 위에서 결정적으로 평가. **상태 4값 → 7값**(`PREVENTION_UNVERIFIABLE`·`PREVENTION_INSUFFICIENT`·`PREVENTION_UNVERIFIED_REVISION` 신설, 차단 6, 전순서 7단). **(b) 리비전 특정** — `∀d∈D` 에 대해 **check-run success + merged PR** 실조회. **«countersign 후 보호 해제»가 닫히는 논증**: (a) 를 **진입 시점과 완료 판정 시점 둘 다 live** 로 평가하고 (b) 가 **리비전마다 서버 실행 흔적**을 요구한다 — **어느 하나만으로는 닫히지 않는다**. 아티팩트·countersign 은 **진실 원천이 아니라 파라미터 선언 + 기록 순서**(owner/repo·대상 브랜치·체크 이름을 **선언**하고 **서버가 검증** — 하드코딩 금지)로 강등. **가드 체인 3단화**(`하니스 && u17-verify && D0A-FIRST`) — **하니스는 오프라인·결정적이어야 하고 byte-identical 회귀 기준선을 가지므로 네트워크를 넣지 않는다**(층 분리). **T-84 재저작**: **음성은 실측·양성은 seam** — 이 저장소 실조회로 `main` → **`PREVENTION_INSUFFICIENT`**(contexts `["test"]`·strict false), 작업 브랜치 → **`PREVENTION_ABSENT`**(404), rulesets `[]`. **인증된 진짜 음성 증거가 지금 존재한다.** 양성은 `responder` 주입 seam(기본 `gh api`·transcript 에 명시)으로 모의하되 **`SIMULATED` 표기**하고 **운영자가 보호를 설정하기 전엔 실측 불가**임을 정직 표기 — **seam 이 정당한 근거는 응답 파서와 판정 함수가 동일 코드 경로**라 주입이 **입력만** 바꾼다는 것이다. **[v2.16 마감 (검증 FAIL 반영 — live 실측은 계약대로였고 차단 3·medium 3)]** ⓐ **#1 (BLOCK ① 클래스 재발)** — §12.3.4-G 의 **G-음성·G-양성 가드가 여전히 2단**이라 **T-81 ⑫ 양성이 폐기된 형태를 탔다**. **3단으로 교정**하고 **`G-음성-2`(하니스 통과 + u17 차단)를 신설** — **현 실측(`INSUFFICIENT`/`ABSENT`)으로 «두 번째 억제 지점»을 live 로 실행할 수 있다** ⓑ **#2** — §8 `T-84` 행이 «4종» 선언 아래 **6항·③ 중복·v2.15 자기신고 기준 잔존**으로 (a) 정의와 **정면 충돌**했다 → 행 전체 재작성 ⓒ **#3 (자기신고 잔여)** — «transcript 에 responder 명시»는 **자기신고**이고 «파서·판정 동일 경로»는 **다른 명제**다. **구조로 닫는다**: 진입자의 `u17-verify` 는 **가드**일 뿐이고 **판정 소비자는 transcript 를 신뢰하지 않고 스스로 live 조회**한다 ⇒ **진실 원천 = 판정 소비자 자신의 조회**. **responder 위조는 진입자 transcript 만 오염**시킨다. 남는 것(**판정 소비자 자신의 환경 위조**·**예방 주체는 서버 자체**)은 **정직 경계 절**로 명시 ⓓ **#4** — 술어에 `required_pull_request_reviews` **부재 = 불충족** · `restrictions`/apps 우회 없음 · 룰셋 **필드 수준**(`enforcement=active`·`bypass_actors=[]`·`required_status_checks`·`pull_request`·`non_fast_forward`·`deletion`) 추가. **TOS 게이트 체크 기본 이름 `tos-gate`** 를 계약이 정하되 **파라미터 기본값**이고 **CI 잡 이름과 일치해야** 하며 **현재 CI 에 부재 → 오늘 `main` 이 `INSUFFICIENT` 인 것이 맞다** ⓔ **#5** — (b) 조회 SHA 를 **PR `head.sha`** 로 못박음(**squash/merge 착지에서 check-run 은 머지 커밋이 아니라 PR head 에 붙는다** — 실측: 머지 커밋 check-runs 0·pulls 공집합·미푸시 422). `d` 직접 조회는 **정직한 착지도 항상 red** 로 만든다 ⓕ **#6** — `T-84 ③` 의 타 축 값(`NOT_STARTED`) 제거하고 **`D = ∅` 처리**를 U-17 에 명시: (a) live 술어는 **`D` 와 무관**(착수 «전»에도 ACTIVE 가능해야 착수한다) · (b)(c) 는 «검증 대상 없음» — **공허참에 기대지 않는다**. **[v2.16 에라타 (동결 `eb2805a9` 후 증거 실행 `434448b2` 적발 — 재결속 전 정정)]** ⓐ **E1 문언 소실** — v2.15 에라타 E3 가 고정한 `operator_countersign: "<식별> <ISO-8601 UTC>"` **리터럴이 U-17 재작성에서 사라져** «형식 위반»이 **재-미정의**됐다 → `(c-0)` 로 복원 ⓑ **E2 사실 정정** — #5 근거의 «머지 커밋 check-runs 0건·pulls 공집합»은 **거짓**이었다(live 재측정: `11e382fc` check-runs **15건**·`pulls` = PR #636 merged 1건). **결론(조회 SHA = PR head.sha)은 유지하고 근거를 교체**한다: 그 15건은 **push 트리거 워크플로**이지 **PR 게이트가 아니며**, 게이트 결과는 **PR head SHA 에 귀속**된다(PR head `7656259d` check-runs 5건에 `tos-gate` 없음). `d` 직접 조회는 **게이트 아닌 실행을 게이트로 오인**하게 만든다 ⓒ **E3 fail-closed 리터럴 고정** — `allow_force_pushes`·`allow_deletions` **키 부재 = 불충족**(없는 것을 «허용 안 함»으로 읽지 않는다) · `restrictions` 실재 시 **`apps == []`**(users/teams 는 push 제한이라 우회 아님) · `rulesets/{id}` 의 **`bypass_actors` 키 부재도 불충족**(조회 못 한 것을 «없음»으로 읽지 않는다) ⓓ **성능 주** — 구조 `D`·`P` 판정은 `git rev-list --full-history` 로 **후보를 축소**해도 되며(2,149 커밋 ~36s → <1s), **완전성 근거**(술어 만족 `x` 는 모든 부모와 tree 가 달라 후보에 포함)와 함께 **«축소는 최적화·판정은 구조 평가»** 임을 명시했다. **증거 실행 결과**: G-음성-2 **live 성립** · T-84 live 음성(`main` INSUFFICIENT·브랜치 ABSENT) · seam 양성 · 3단 가드 ⑫ CLEAR. **하니스 byte-identical·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
@@ -4346,13 +4346,23 @@ v2.4·v2.5 를 무효화한 행위다. **상태 표기의 currency 와 결속의
 addendum 으로 이행**한다(S-24: 재동결에 대한 절 범위 `git diff` 공집합 증명 + 영향 변이 재실행 —
 영향 변이 목록은 §12.3.3 (B) 하단·변경 이력 v2.19 에라타 절).
 
+**[v2.19 에라타 2차 — addendum 적발]** 에라타 재동결(`e3ed4e78`) 후 **S-24 addendum**
+(`docs/reviews/phase0-completion-contract/20260819-074621/U17-PREVENTION-CHECK-V219-ADDENDUM.md` §5)이
+**[PARENTS-UNTRUSTED] 자체의 결함 2건**을 적발했다: **E8** `git replace --graft` 가 [SHALLOW]
+세 판별을 전부 통과하며 부모 집합을 재작성해 `LATE→ACTIVE` fail-open(실측 `197f4fe4`) · **E9**
+`P_first`/`P_last` 다부모 의미 미규정(실행기 ∨ 읽기 → `ARTIFACT_MUTATED`↔`ACTIVE` 극성 분기).
+→ [SHALLOW]를 **[PARENTS-UNTRUSTED]로 일반화·개명**(부모 재작성 축·`git replace -l` 공집합·
+`.git/info/grafts` 부재·`--no-replace-objects` 이중 판별) · `P` 를 D·C_R·c_APP 와 ∀-부모 동형
+구조 정의로 고정.  **이 2차 에라타의 결속도 addendum 2차로 이행**(S-24: 절 범위 diff 공집합 +
+영향 변이 재실행 — §5 산출 목록).
+
 | v2.18 finding | 심판 지적 | v2.19 의 변경 | 왜 회피가 아닌가 | 실행 증거 |
 |---|---|---|---|---|
 | **#1 F1** 보호 해제 창 (high) | 진입·완료 두 조회 사이 off→머지→재활성 창을 어느 술어도 소비 안 함 + (B) «완료 가능성 자체를 막는다» 과대주장 | **과대주장 철회** + **연속성 소비자 신설**(완료 판정 시점 룰셋 `created_at`/`updated_at` > `t_land` → `PREVENTION_CONTINUITY_UNVERIFIABLE`, 운영자 재심사) · U-17-c **10값** | 과대주장 대신 «위조 비용을 올리지 닫지 않는다» 정직 표기 · **설정 변경을 fail-closed 로 «관측→차단»** 승격(관측만이 아님) · 룰셋 미변경 우회는 감사 로그 경계로 명시 | 직전 U-17 = `20260819-002145/U17-PREVENTION-CHECK-V218.md`(T-84 ①~⑩) · **v2.19 ⑪ = `20260819-074621/U17-PREVENTION-CHECK-V219.md`** — (a)~(f) SIMULATED 6픽스처 전건 일치(off→merge→on·삭제-재생성·classic-only → `CONTINUITY_UNVERIFIABLE`·direct-push → 8 선발화·committer-date 무시)·**단 classic 死분기(E1)·t_land 공백(E2) 적발 → 에라타 정정** |
 | **#2 host 미결속** (high) | 모든 `gh api` 가 host 없이 나가 `GH_HOST` override 로 타 host 응답이 ACTIVE 가능 | host 를 계약 핀에서 파생해 **`--hostname` 명시 + 소비자 `GH_HOST` 재핀 + `gh auth status` 전제**(C6) | 조회 대상 host 가 핀에 이중 결속 · 도달 불가 = `UNVERIFIABLE`(타 host 폴백 없음) · 자기환경 위조는 정직 경계 | **v2.19 ⑫ = `.../U17-PREVENTION-CHECK-V219.md`** — live: `--hostname` 이 `GH_HOST` 를 이김(PROBE)·override 유무 상태 불변·nohost 대조군 → `UNVERIFIABLE`·활성 조회 12곳 전부 `--hostname`.  **단 이중결속 문언·responder=file 전제·host 키·GET-only 경계(E3) 적발 → 에라타 정정** |
 | **#3 F2** D0A-FIRST 규범 잔존 (high) | 앞선 D0A-FIRST 절이 «모호 없이 한 커밋»·`diff-filter=A` 규범 유지 | 판정 소비 자리를 **`U-15-g-1` 구조 `D` 참조로 전환** · 편의 표기(∅ 확인)와 판정 소비 구별 명시 | 재기술을 참조로 바꿔 stale 클래스 제거(S-22·S-14) · 구조 `D` 는 이미 gg/gu/uu 를 차단(T-81 ⑲) | 구조 `D` = `20260819-002145/U15-ENTRY-CHECK-ADDENDUM.md`(T-81 ⑲ gg/gu/uu) · **v2.19 규범 참조 전환 = 문서 정합(코드 무관)** |
 | **#4 F4** T-82 ⑱ 입력 stale (medium) | ⑱ 이 폐지된 `edge_seq` 기재 지시 + 손 실행기 계약 밖 규칙 자체 선언 | **⑱ 을 현행 스키마로 재기술**(edge_seq 미기재·소비자 표시용 파생) + **U-16-d 전순서·규칙 평가 순서를 계약 리터럴로 고정**(자체 선언 흡수) | 입력 의미가 현행 스키마에 결속 · «사전순 최소·상태 우선순위» 자체 선언이 **계약 리터럴**이 됨 | 직전 ⑱ = `20260819-002145/U16-LEDGER-CHECK.md`(폐지 스키마 실행) · **v2.19 ⑱ = `20260819-074621/U16-LEDGER-CHECK-V219.md`** — ⑱-1(같은 `row_id`·다른 내용) `NO_ROWS_CLEAR`/0.  **단 문언 «별개 `row_id`» 가 g2·간선 대응과 충돌(E4) 적발 → ⑱ 을 «같은 row_id»로 에라타 정정** |
-| **#5 F5** 단수 `c_APP` (medium) | `row_ref` 만 없앴고 같은 비단수 `c_APP` 가 U-16-c/g5/g6 에 단수 잔존 | **`c_APP` 를 구조 집합 정의**(D·C_R 동형) · `c_APP` 크기>1 → `APPROVAL_MALFORMED` · 세 소비처 일관 | 표면 이동이 아니라 **동형 정의로 원인 축(단수 선택 재량) 소거** · 극성 = 판정 불가 차단 | **v2.19 ⑳ = `.../U16-LEDGER-CHECK-V219.md`** — ⑳ⓐ(형제 동일 행 → `c_APP` 크기 2 → `MALFORMED`)·⑳ⓑ(얕은 클론 → `PROVENANCE_UNVERIFIABLE`(2), 「g1 먼저」 구현은 3 = 발산 실증) 일치.  **단 루트/얕은 경계 구별([SHALLOW]·E5)·선-검사 국소화(E6)·고아 구조 정의(E7) 적발 → 에라타 정정** |
+| **#5 F5** 단수 `c_APP` (medium) | `row_ref` 만 없앴고 같은 비단수 `c_APP` 가 U-16-c/g5/g6 에 단수 잔존 | **`c_APP` 를 구조 집합 정의**(D·C_R 동형) · `c_APP` 크기>1 → `APPROVAL_MALFORMED` · 세 소비처 일관 | 표면 이동이 아니라 **동형 정의로 원인 축(단수 선택 재량) 소거** · 극성 = 판정 불가 차단 | **v2.19 ⑳ = `.../U16-LEDGER-CHECK-V219.md`** — ⑳ⓐ(형제 동일 행 → `c_APP` 크기 2 → `MALFORMED`)·⑳ⓑ(얕은 클론 → `PROVENANCE_UNVERIFIABLE`(2), 「g1 먼저」 구현은 3 = 발산 실증) 일치.  **단 루트/부모 신뢰 불가 구별([PARENTS-UNTRUSTED]·E5)·선-검사 국소화(E6)·고아 구조 정의(E7) 적발 → 에라타 정정** |
 | **#6 두 결속 계획 충돌** (medium) | 개발계획 Phase 1 작업 7·종료조건 vs 계약 D0-A 착수 선행조건 | **운영자 게이트** — 계약이 «함께 착수 불가»를 정직 표기 + (D) 절에 **적용 준비된 개정안 문안** 수록(개발계획 무편집) | 저작자는 계약 측 선언만 가능 · 정식 개정은 운영자 소관(`bound_paths`·O-6) | **해당 없음** — 실행 증거 아님(운영자 결정) |
 
 **어느 것도 «해소»로 세지 않는다.** **v2.19 가 주장할 수 있는 것은 «6건 전건에 대해 요구된
@@ -4931,7 +4941,7 @@ D = { x ⊑ HEAD :  path ∈ tree(x)  ∧  ∀ p ∈ parents(x): path ∉ tree(p
     path = config/tos_completion.yaml.  머지에서 처음 나타나면 **머지 자체가 원소**.
     **진짜 루트**(부모 없음)는 두 번째 항이 공허참이므로 자동 포함.
     `tree(p)` 가 정의되지 않는 경우(부모 없음)는 `path ∉ tree(p)` 를 **참**으로 읽는다.
-    **[SHALLOW]** 얕은 클론 «경계»(부모 미상)는 «진짜 루트»가 아니다 — U-16-c 의 [SHALLOW]
+    **[PARENTS-UNTRUSTED]** 부모 신뢰 불가(얕은 클론 «경계»·replace/graft 재작성)는 «진짜 루트»가 아니다 — U-16-c 의 [PARENTS-UNTRUSTED]
     단서 동형 적용: 경계 커밋은 도입 지점 확정 안 함 → **`PROVENANCE_UNVERIFIABLE`**
     **[성능 주 — v2.16 에라타]** 전 커밋 순회는 이 저장소(2,149 커밋)에서 ~36s/run
     이므로, 실행기는 `git rev-list --full-history HEAD -- <path>` 로 **후보를 축소**한
@@ -5522,19 +5532,30 @@ operator_countersign: "<운영자 식별> <ISO-8601 UTC>"   # 예: "operator 202
 `P ⊰ d` 를 충족한 채 통과했다(사후 편집 허용).
 
 ```text
-P_first  = HEAD 조상 중 아티팩트 경로를 **«최초 도입»** 한 커밋
-P_last   = HEAD 조상 중 아티팩트 경로를 **«마지막으로 변경»** 한 커밋
-           (둘 다 구조 파생 — `git rev-list --full-history HEAD -- <artifact>`
-            후보 위, §U-15-g-1 성능 주와 같은 규율.
-            **[SHALLOW]** 얕은 클론 경계(부모 미상)는 U-16-c [SHALLOW] 동형 —
-            `P_first`/`P_last` 확정 불가 → `PREVENTION_UNVERIFIABLE`)
-
-두 상태의 «기계 조건»을 분리한다   [R1 — v2.18 마감]
-  PREVENTION_LATE             ∃ d ∈ D : **P_first ⋠ d**
-                              («기록이 아예 착수보다 늦다»)
-  PREVENTION_ARTIFACT_MUTATED **∀ d ∈ D : P_first ⊰ d**  ∧  ∃ d ∈ D : **P_last ⋠ d**
-                              («기록은 먼저 있었는데 착수 «후»에 고쳤다»)
-  PREVENTION_ACTIVE 조건      ∀ d ∈ D : **P_last ⊰ d**   ∧ 소비 blob == P_last 시점 blob
+**[E9 — v2.19 에라타 2차] P_first·P_last 를 D·C_R·c_APP 와 «동형 구조 정의»로 고정한다 (∀-부모).**
+  도입지점(b) = { x ⊑ HEAD :  blob(x:artifact) == b  ∧  ∀ p ∈ parents(x): blob(p:artifact) ≠ b }
+               (경로 부재 blob(p) 미정의는 `≠` 로 읽음 — [H4] 동형 · [PARENTS-UNTRUSTED] 동형)
+  P_first  = **경로 도입 집합** { x ⊑ HEAD : path ∈ tree(x) ∧ ∀p∈parents(x): path ∉ tree(p) }  (D 동형)
+  P_last   = **도입지점(blob(HEAD:artifact))** — 현행 blob 의 도입 지점 «집합»  (C_R 동형)
+           (구조 파생 — `git --no-replace-objects rev-list --full-history HEAD -- <artifact>` 후보 위)
+  **[N-2 정정] «마지막 변경»의 다부모 ∨ 읽기를 폐기한다.**  머지 x(부모 p1·p2)에서 **∀-부모 다름**
+  (blob(p1)≠b ∧ blob(p2)≠b)이라야 x 가 b 의 도입 지점이다:
+     · 두 부모가 서로 다른 blob·머지가 «새» blob → ∀ 성립 → 머지가 도입(정상)
+     · 머지 blob 이 한 부모와 «같음» → 그 부모에서 ∀ 깨짐 → 도입 아님(그 방향에서 이미 존재)
+  실행기의 ∨(«어느 한 부모와라도 다름»)는 2-부모 graft 에서 `ARTIFACT_MUTATED`↔`ACTIVE` 극성이
+  갈렸다(실측 N-2) — ∀ 로 고정해 «동형 정의 중 P 만 비대칭»을 없앤다(S-22 계열).
+  카디널리티 (c_APP 동형·fail-closed):
+     |P_last| = 0  →  PREVENTION_UNVERIFIABLE (현행 blob 도입 지점 없음 = 이력 파생 실패/[PARENTS-UNTRUSTED])
+     |P_last| > 1  →  PREVENTION_ARTIFACT_MUTATED (현행 내용의 도입 지점이 «유일하지 않다» =
+                      «언제 기록»이 유일하지 않아 사후 편집 배제 불가 · c_APP 크기>1 동형·보수)
+     |P_last| = 1  →  그 유일 원소 `x_last` 를 아래 조건에 쓴다
+
+두 상태의 «기계 조건» — ∀-부모 도입 집합 위에서 결정적   [R1 — v2.18 마감 / E9 재정의]
+  PREVENTION_LATE             ∃ d ∈ D : ∀ x ∈ P_first : **x ⋠ d**   («그 착지 시점에 경로가 없었다»)
+  PREVENTION_ARTIFACT_MUTATED ¬LATE ∧ ( **|P_last| > 1**  ∨  ∃ d ∈ D : **x_last ⋠ d** )
+                              («기록은 먼저 있었는데 착수 «후»에 고쳤다» — 다중 도입도 여기)
+  PREVENTION_ACTIVE 조건      **|P_last| = 1** ∧ ∀ d ∈ D : **x_last ⊰ d** ∧ 소비 blob == blob(x_last:artifact)
+  (ACTIVE 와 MUTATED 는 ¬LATE 하에 상보 — 결정적 · `T-84 ⑨`(사후 편집) 도달 가능성 유지)
 
 **초안의 결함**: `P` 를 «최초 도입 → 마지막 변경»으로 **전역 재정의**해 두 상태의
 조건이 **동일**해졌고, 전순서 6 < 7 이라 **`ARTIFACT_MUTATED` 가 도달 불가**였다
@@ -5550,16 +5571,16 @@ P_last   = HEAD 조상 중 아티팩트 경로를 **«마지막으로 변경»**
 ```text
 U-17-c  상태  prevention_control_state   (1급 노출)
           PREVENTION_ACTIVE            (a) 술어 충족 ∧ (b) 전 리비전 검증 ∧ **연속성 성립**
-                                       ∧ countersign 유효 ∧ **∀d∈D: P_last ⊰ d**  (통과)
+                                       ∧ countersign 유효 ∧ **P_last 조건**(위 «기계 조건» 블록·E9 — 재기술 안 함, S-14)  (통과)
           PREVENTION_UNVERIFIABLE      조회 실패(HTTP·네트워크·인증)     → 차단  [v2.16]
           PREVENTION_ABSENT            아티팩트 부재 · 404 미보호        → 차단
           PREVENTION_UNSIGNED          operator_countersign 부재·형식 위반 → 차단
           PREVENTION_TARGET_MISMATCH   계약 핀과 일치하는 원격 부재 ·
                                        target ≠ 핀 repo 의 default_branch → 차단  [v2.17]
           PREVENTION_ARTIFACT_MUTATED  기록은 먼저 있었으나 착수 «후»에 변경됨
-                                       (`∀d: P_first ⊰ d` ∧ `∃d: P_last ⋠ d`) → 차단  [v2.18]
+                                       (위 «기계 조건»·E9: `|P_last|>1 ∨ ∃d: x_last ⋠ d`, ¬LATE) → 차단  [v2.18·E9]
           PREVENTION_INSUFFICIENT      보호는 있으나 술어 불충족          → 차단  [v2.16]
-          PREVENTION_LATE              `∃d: P_first ⋠ d` — 기록이 착수보다 늦다 → 차단
+          PREVENTION_LATE              `∃d: ∀x∈P_first: x ⋠ d`(위 «기계 조건»·E9) — 기록이 착수보다 늦다 → 차단
           PREVENTION_UNVERIFIED_REVISION  (b) 불충족                      → 차단  [v2.16]
           PREVENTION_CONTINUITY_UNVERIFIABLE  착지 후 룰셋 설정 변경 관측 · classic-only
                                        (타임스탬프 부재) — 연속성 판정 불가 → 차단  [v2.19]
@@ -6903,7 +6924,7 @@ C_R(c) = { x ⊑ c :  blob(x:<reviewer_ref>) == blob(approved_at_head:<reviewer_
          = 전이 커밋 c 의 조상 중 **«도입 지점»** — 그 커밋의 blob 이 승인 대상
            blob 과 같고 **어떤 부모의 blob 도 그것과 같지 않다**.  머지에서 해소로 도입되면 **머지 자체가 원소**다.
            **진짜 루트**(부모 없음)는 두 번째 항이 공허참이므로 자동 포함.
-           **[SHALLOW]** 얕은 클론 경계(부모 미상)는 U-16-c [SHALLOW] 단서 동형 적용 —
+           **[PARENTS-UNTRUSTED]** 부모 신뢰 불가(경계·재작성)는 U-16-c [PARENTS-UNTRUSTED] 단서 동형 적용 —
            도입 지점 확정 안 함 → `PROVENANCE_UNVERIFIABLE`(부재를 «참»으로 접지 않는다).
            **[H4 / v2.15 마감]** `blob(p:<ref>)` 가 정의되지 않는 경우(부모에 그 경로가
            **부재**)는 **`blob(p:ref) ≠ 그 blob` 을 참**으로 읽는다 — 경로 신설도 «도입»이며,
@@ -6978,14 +6999,29 @@ c_APP(a) = { x ⊑ HEAD :  a ∈ rows(x:LEDGER)  ∧  ∀ p ∈ parents(x): a 
                             (자기신고 순번·표시용 파생 필드 제외 — U-16-b).  `a` 는 그 정규형 행.
            머지 해소에서 처음 나타나면 **머지 자체가 원소**.  **진짜 루트(부모 없음)**는 둘째 항이
            공허참이라 자동 포함.  부모에 원장 경로 부재는 `a ∉ rows(p)` 로 읽는다([H4] 동형).
-           **[SHALLOW — v2.19 에라타·동형 정의 유일 소스] 얕은 클론 경계 커밋은 «진짜 루트»가
-           아니라 «부모 미상»이다.**  `.git/shallow`(또는 `git rev-parse --is-shallow-repository`
-           ∧ 부모 커밋 «객체» 조회 실패)로 판별한 경계 커밋은 `∀p ∈ parents(x)` 항을 «평가할 수
-           없으므로» 그 `x` 를 도입 지점으로 **«확정하지 않는다» → `PROVENANCE_UNVERIFIABLE`**.
-           **부재를 «참»으로 접으면 얕은 클론이 임의 커밋을 도입 지점으로 만들어낸다(fail-open)** —
-           그래서 «경로 부재(a∉rows, 참)»와 «커밋 객체 부재(부모 미상, 판정 불가)»를 구별한다.
+           **[PARENTS-UNTRUSTED — v2.19 에라타 2차·동형 정의 «유일 소스» (구 [SHALLOW] — 일반화·개명)]
+           «부모 집합을 신뢰할 수 없는 상태»에서는 도입 지점을 확정하지 않는다.**  `∀p ∈ parents(x)`
+           를 평가하려면 그 커밋의 «부모 집합»이 «참»이어야 한다.  참이 아닌 «두 사례»:
+             (1) **얕은 클론 «경계»(부모 미상)** — `.git/shallow` 또는 `git rev-parse
+                 --is-shallow-repository` ∧ 부모 커밋 «객체» 조회 실패로 판별.
+             (2) **부모 «재작성»(위조)** — `git replace --graft`/replace ref, 또는 `.git/info/grafts`
+                 (deprecated 이나 동작).  **[N-1 실측] 이 재작성은 «얕지 않음·`.git/shallow` 부재·
+                 부모 객체 present» 세 판별을 «전부 통과»하면서** `git log --format=%P`·`rev-list`·
+                 `merge-base` 등 **replace 를 따르는 모든 명령이 «가짜» 부모를 반환**해 `PREVENTION_LATE`
+                 (6)→`PREVENTION_ACTIVE`(10) fail-open 이 났다(`GIT_NO_REPLACE_OBJECTS=1` 에서는 진짜 부모).
+           **판별 — 이중(관측 + 무력화, «둘 다»)**:
+             ① **관측**: `git replace -l` **공집합** ∧ `.git/info/grafts` **부재** ∧ 얕은 클론 아님.
+                하나라도 위반 = 부모 신뢰 불가 → **`PROVENANCE_UNVERIFIABLE`/`PREVENTION_UNVERIFIABLE`**
+                (얕은 클론은 `--no-replace-objects` 로 무력화되지 않으므로 관측이 필수다)
+             ② **무력화**: 모든 «조상·부모 파생» `git` 호출을 **`git --no-replace-objects …`**
+                (또는 `GIT_NO_REPLACE_OBJECTS=1`)로 고정 — replace 뷰를 «따르지 않는다»(grafts 는
+                이 플래그로 꺼지지 않으므로 ① 의 부재 요구가 grafts 축을 담당한다)
+           경계·재작성 커밋은 `x` 를 도입 지점으로 **«확정하지 않는다»**.  **극성**: 부모를 신뢰할 수
+           없으면 도입 지점을 확정할 수 없으니 **판정 불가를 판정 불가로**(E5 와 동형·fail-closed).
+           «경로 부재(a∉rows, 참)»와 «부모 미상·위조(판정 불가)»를 구별한다.
            **이 단서는 동형 정의 전부에 적용된다** — `D`(U-15-g-1)·`C_R`(g6)·`P_first`/`P_last`
-           (U-17 c) 가 각각 «[SHALLOW]» 로 이 절을 참조한다(S-14·플래그 의존 클래스 동형 규율).
+           (U-17 c) 가 각각 «[PARENTS-UNTRUSTED]» 로 이 «유일 소스» 절을 참조한다(S-14·재기술 금지·
+           플래그/이력-뷰 의존 클래스 동형 규율).
 ```
           **[v2.19 — 심판 F5] v2.11~v2.18 은 `c_APP(a)` 를 단수 «도입한 커밋»으로 두어**,
           동일 raw 승인 행이 형제 브랜치에서 독립 도입되면 도입 지점이 둘인데 `U-16-c`·g5·g6 세
@@ -7060,7 +7096,10 @@ U-16-d  상태  closable_no_provenance_state  (TOS-COMPLETION-STATUS 에 1급 
         — 계약 밖 규칙).  한 행/간선이 여러 규칙에 걸릴 때 «어느 상태를 보고하는가»가
         규범이 아니면 소비자마다 갈린다.  아래로 고정한다 — **한 행/간선이 여러 상태를
         위반하면 전순서 «번호가 작은(전제가 더 먼저 붕괴한)» 값을 그 행/간선 상태로 하고,
-        전역 상태는 모든 행·모든 간선 상태의 전순서 최소**다(∅ 위반이면 NO_ROWS_CLEAR):
+        전역 상태는 모든 행·모든 간선 상태의 전순서 최소**다(∅ 위반이면 NO_ROWS_CLEAR).
+        **[N-3~5 — v2.19 에라타 2차 관측] «전순서 최소»는 세 층에서 같은 규칙으로 쓰인다**
+        (비차단 명시): ① **규칙 간**(한 행/간선의 g-단락 첫 미충족) ② **후보 간**(한 간선의
+        여러 대응 후보 — E7 D-4) ③ **전역**(모든 행·간선).  세 층 모두 «번호 작은 값 우선»:
 ```text
   1  CONSUMER_ABSENT           검사기·원장·레지스터가 없으면 아무것도 못 묻는다
                                (상위 완료 평가 소관 — T-82 ⑦ 주)
@@ -7081,7 +7120,7 @@ U-16-d  상태  closable_no_provenance_state  (TOS-COMPLETION-STATUS 에 1급 
          구현하는 정합 절차다):
         ① **선-검사(전역·구조 — g-규칙 «앞»에 필수로 온다)**:
              1 `CONSUMER_ABSENT` · 2 `PROVENANCE_UNVERIFIABLE`(`c_APP`/`C_R`/`D` 중 하나의
-               «크기 0» — 얕은 클론 [SHALLOW] 경계가 도입 후보 우주에 있어 크기 0이 되는 경우 포함)
+               «크기 0» — [PARENTS-UNTRUSTED] 경계·재작성 커밋이 도입 후보 우주에 있어 크기 0이 되는 경우 포함)
                **[E6 — v2.19 에라타] «얕은 클론»을 «전역 단축»(실행 초입 즉시 방출)으로 읽지
                않는다** — 그러면 «g1·g4 먼저» 대조군(⑳ⓑ)도 그 단축에 먼저 걸려 둘 다 2 를 내
                «구별력을 잃는다».  얕음 자체가 아니라 **판정에 필요한 부모가 미상인 경계 커밋이
```

### 1-2. `s24-proof-2.sh` — 원문 (sha256 `866e55b57afa175fe15d1223fa4a852b61af8169d38f9918b1559415881edd2e`)

```bash
#!/usr/bin/env bash
# s24-proof-2.sh — S-24 ① «절 범위 diff 기계 증명» (에라타 재동결 e3ed4e78 → 에라타 2차 재동결 ad5be1a3).
#   ① 두 blob 의 hunk 를 파싱해 «변경된 행 범위»를 기계 추출하고, 그 사이의 «닿지 않는» 구간을
#      전부 자동 생성해 old/new 양쪽에서 잘라 sha256 을 대조한다(∅ = byte-동일).
#   ② 계약이 지목한 «명명 절»(하니스 블록·U-17-c 상태표/전순서·(b) 술어·(c) 기계 조건·연속성 판정
#      본체·U-16-d 12단 표·c_APP 수식)은 **각 blob 에서 리터럴 grep 으로 위치를 파생**해(하드코딩
#      행번호 아님) 범위를 잘라 대조한다 — 행 이동(shift)이 있어도 «내용 동일»이 직접 증명된다.
#   해시·행번호를 발명하지 않는다. 전 값은 실측이다.
set -u
R=/Users/harris/Development/private/kis_unified_sts
P=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
OLD=e3ed4e78; NEW=ad5be1a3
WT="$R/$P"
b_old=$(mktemp); b_new=$(mktemp)
git -C "$R" show "$OLD:$P" > "$b_old"; git -C "$R" show "$NEW:$P" > "$b_new"
printf '=== S-24 절 범위 diff 기계 증명 (%s) — 동결 %s(%s행) → 에라타 재동결 %s(%s행) ===\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$OLD" "$(wc -l < "$b_old" | tr -d ' ')" "$NEW" "$(wc -l < "$b_new" | tr -d ' ')"
echo "\$ git diff $OLD..$NEW --stat -- <계약>"; git -C "$R" diff "$OLD".."$NEW" --stat -- "$P" | sed 's/^/  /'
echo "\$ git diff $OLD..$NEW -- <계약> | grep '^@@'   (hunk 목록 — 이것이 변경의 전부)"
git -C "$R" diff "$OLD".."$NEW" -- "$P" | grep '^@@' | sed 's/^/  /'

echo
echo "-- ① hunk 사상 (기계 파싱: 각 hunk 안에서 실제로 «바뀐» 행의 old/new 범위) --"
git -C "$R" diff -U0 "$OLD".."$NEW" -- "$P" > "$(dirname "$b_old")/u0.diff"
python3 - "$(dirname "$b_old")/u0.diff" "$b_old" "$b_new" <<'PY'
import re,sys,subprocess,hashlib
u0,bo,bn=sys.argv[1:4]
hunks=[]
for line in open(u0,encoding='utf-8'):
    m=re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',line)
    if m:
        os_,ol,ns,nl=int(m.group(1)),int(m.group(2) or 1),int(m.group(3)),int(m.group(4) or 1)
        hunks.append((os_,ol,ns,nl))
old_lines=open(bo,encoding='utf-8').read().split('\n')
new_lines=open(bn,encoding='utf-8').read().split('\n')
def sha(lines,a,b):   # 1-기반 포함 범위
    if a>b: return "(빈 범위)"
    return hashlib.sha256(("\n".join(lines[a-1:b])+"\n").encode()).hexdigest()
print("   #  old[start,len]  new[start,len]   (len=0 은 순수 삽입/삭제)")
for i,(os_,ol,ns,nl) in enumerate(hunks,1):
    print(f"  H{i:<2} old[{os_},{ol}]        new[{ns},{nl}]")
print()
print("-- ② «닿지 않는» 구간 자동 생성 + sha256 대조 (∅ = byte-동일) --")
prev_o, prev_n = 0, 0
ok=True
for i,(os_,ol,ns,nl) in enumerate(hunks,1):
    a_o, b_o = prev_o+1, os_-1 if ol>0 else os_
    a_n, b_n = prev_n+1, ns-1 if nl>0 else ns
    if ol==0: b_o = os_          # 순수 삽입: old 쪽은 os_ 까지가 무변경
    if nl==0: b_n = ns
    if b_o>=a_o or b_n>=a_n:
        so,sn=sha(old_lines,a_o,b_o),sha(new_lines,a_n,b_n)
        tag="∅" if so==sn else "≠(!!)"
        if so!=sn: ok=False
        print(f"  {tag}  old[{a_o},{b_o}] == new[{a_n},{b_n}]  sha256={so[:16]}…")
    prev_o = os_+ol-1 if ol>0 else os_
    prev_n = ns+nl-1 if nl>0 else ns
    print(f"  ≠   H{i}: old[{os_},{os_+ol-1 if ol>0 else os_}] vs new[{ns},{ns+nl-1 if nl>0 else ns}]  — 에라타가 건드린 범위(≠ 기대)")
a_o,b_o=prev_o+1,len(old_lines)-1
a_n,b_n=prev_n+1,len(new_lines)-1
so,sn=sha(old_lines,a_o,b_o),sha(new_lines,a_n,b_n)
tag="∅" if so==sn else "≠(!!)"
if so!=sn: ok=False
print(f"  {tag}  old[{a_o},{b_o}] == new[{a_n},{b_n}]  sha256={so[:16]}…   (말미~EOF)")
print()
print(f"-- 자동 구간 전건 결과: {'전 구간 ∅ (변경은 hunk 안에만 있다)' if ok else '불일치 발생 — 증명 실패'} --")
PY

echo
echo "-- ③ 명명 절 대조 (각 blob 에서 «리터럴 grep 으로 위치 파생» — 하드코딩 행번호 아님) --"
sec() { # sec <라벨> <시작 리터럴> <끝 리터럴|+N행>
  local label="$1" s="$2" e="$3" so eo sn en ho hn
  so=$(grep -n -F -- "$s" "$b_old" | head -1 | cut -d: -f1)
  sn=$(grep -n -F -- "$s" "$b_new" | head -1 | cut -d: -f1)
  if [ -z "${so:-}" ] || [ -z "${sn:-}" ]; then printf '  ??  %s — 시작 리터럴 미발견 (old=%s new=%s)\n' "$label" "${so:-∅}" "${sn:-∅}"; return; fi
  case "$e" in
    +*) eo=$((so + ${e#+} - 1)); en=$((sn + ${e#+} - 1)) ;;
    *)  eo=$(awk -v s="$so" 'NR>=s' "$b_old" | grep -n -F -- "$e" | head -1 | cut -d: -f1); eo=$((so + eo - 1))
        en=$(awk -v s="$sn" 'NR>=s' "$b_new" | grep -n -F -- "$e" | head -1 | cut -d: -f1); en=$((sn + en - 1)) ;;
  esac
  ho=$(sed -n "${so},${eo}p" "$b_old" | shasum -a 256 | cut -d' ' -f1)
  hn=$(sed -n "${sn},${en}p" "$b_new" | shasum -a 256 | cut -d' ' -f1)
  if [ "$ho" = "$hn" ]; then printf '  ∅   %s : old[%s,%s] == new[%s,%s]  sha256=%s…\n' "$label" "$so" "$eo" "$sn" "$en" "${ho:0:16}"
  else printf '  ≠   %s : old[%s,%s]=%s… vs new[%s,%s]=%s…  (에라타가 건드림)\n' "$label" "$so" "$eo" "${ho:0:16}" "$sn" "$en" "${hn:0:16}"; fi
}
# — 닿지 «않아야» 하는 절
sec "§12.3.4-R 하니스 블록 (101행)" '# §12.3.4-R  U-15 pre-D0-A 진입 판정 하니스 (v2.10)' '+100'
sec "§8 T-84 행 (12종 — U-17 대조군)" '| **T-84** | **U-17 예방 통제 활성 증거**' '+1'
sec "§8 T-82 행 (20종 — U-16 대조군)" '| **T-82** | **U-16 `closable=NO` 전이 provenance**' '+1'
sec "§8 T-81 행 (U-15 대조군)" '| **T-81** | **U-15 P-0 후 재진입**' '+1'
sec "(a) 술어 블록 전문 (E1 classic terminal 포함)" '술어 (캡처된 응답 위에서 결정적)' 'TOS 게이트 체크 이름  아티팩트가'
sec "(b) 리비전 특정 전문" '**(b) 리비전 특정 — 사후·완료 판정** (§11)' '**[#5 — v2.16 마감 / E2 근거 교체] 조회 SHA 를'
sec "(α) 연속성 술어 전문" '(α) 연속성 술어 — 룰셋 «서버 타임스탬프»만 소비한다' '    **차단이되 «운영자 재심사 경로»**'
sec "C6 host 결속 블록 (E3)" '핀 host    = canonical_target 의 host 성분' '적용 범위  (a)·(b)·(c)·target'
sec "U-17-c 전순서 10단" '        **전순서** (전제 붕괴 순서):' '         10 PREVENTION_ACTIVE'
sec "U-17-d 강제 지점·종료조건·대조군" 'U-17-d  강제 지점  §12.3 단계' '        대조군     T-84 (§8) — **12종**'
sec "U-16-c c_APP 수식 3행" 'c_APP(a) = { x ⊑ HEAD :  a ∈ rows(x:LEDGER)' '+3'
sec "U-16-d 전순서 12단 표" '  1  CONSUMER_ABSENT           검사기·원장·레지스터가 없으면' ' 12  NO_ROWS_CLEAR'
sec "U-16-d ② g-단락 (5~11)" '        ② **g-단락 — 선-검사를 통과한' '+3'
sec "U-16-a2 전칭 판정 블록" 'U-16-a2 **전칭 판정 — 고르지 않는다.**' '+8'
sec "U-16-h 시점 고정 블록" 'U-16-h  **승인 산출물이 그 내용을 인용해야 한다' '+6'
sec "U-16-b 간선 대응·고아 (E7)" '간선 대응        승인 행 `a` 가 간선 `(p→c)` 를 «덮는다» ⇔' '`edge_seq`       **소비자가 표시용으로 파생**한다'
sec "U-15-g-4 CORR 술어 블록" '            CORR(d) = { (t,k) ∈ RUNS :' '+5'
echo "  --"
# — 닿아야 «하는» 절 (에라타 2차의 실체 — ≠ 가 기대값)
sec "[E8] U-16-c [PARENTS-UNTRUSTED] 정의 블록 (유일 소스)" 'c_APP(a) = { x ⊑ HEAD :  a ∈ rows(x:LEDGER)' '```'
sec "[E8] 참조 1/4 — U-15-g-1 D 정의" 'D = { x ⊑ HEAD :  path ∈ tree(x)' '+6'
sec "[E8] 참조 2/4 — g6 C_R 정의 꼬리" '         = 전이 커밋 c 의 조상 중 **«도입 지점»**' '+6'
sec "[E9]+[E8] 참조 3·4/4 — P_first/P_last 정의 + 두 상태의 기계 조건" '`P ⊰ d` 를 충족한 채 통과했다(사후 편집 허용).' '**초안의 결함**:'
sec "[E9] U-17-c 상태표 (ACTIVE·MUTATED·LATE 조건)" 'U-17-c  상태  prevention_control_state   (1급 노출)' '        **열 값 중 «아홉이 차단»이고'
sec "[E8] U-16-d ① 선-검사" '        ① **선-검사(전역·구조 — g-규칙 «앞»에 필수로 온다)**:' '        ② **g-단락'
sec "[N-3~5] U-16-d 전순서 머리 (세 층 주석)" '        **전순서 (전제 붕괴 순서 — 계약이 리터럴로 고정, U-16-d 가 «유일 소스»)**' '```text'
sec "§12.3.3 (B) 처분표" '| v2.18 finding | 심판 지적 | v2.19 의 변경 | 왜 회피가 아닌가 | 실행 증거 |' '+8'
sec "심사 이력 v2.19 행" '> | **v2.19** | **재심 미착수.**' '+1'
sec "변경 이력 v2.19 행" '| **v2.19** | **v2.18 심판 판정 6건(high 3 / medium 3) 전건 반영.' '+1'

echo
echo "-- ④ 하니스 §12.3.4-R 블록 sha256 (계약이 리터럴로 결속한 값) --"
printf '  %s :4598-4698  %s\n' "$OLD" "$(sed -n '4598,4698p' "$b_old" | shasum -a 256 | cut -d' ' -f1)"
printf '  %s :4608-4708  %s\n' "$NEW" "$(sed -n '4608,4708p' "$b_new" | shasum -a 256 | cut -d' ' -f1)"
printf '  두 값 동일? %s\n' "$([ "$(sed -n '4598,4698p' "$b_old" | shasum -a 256 | cut -d' ' -f1)" = "$(sed -n '4608,4708p' "$b_new" | shasum -a 256 | cut -d' ' -f1)" ] && echo yes || echo no)"
printf '  계약 리터럴(본문 인용) 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d 과 일치? %s\n' \
  "$([ "$(sed -n '4608,4708p' "$b_new" | shasum -a 256 | cut -d' ' -f1)" = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d ] && echo yes || echo no)"

echo
echo "-- ⑤ 워킹트리·HEAD 결속 --"
printf '  HEAD                    = %s\n' "$(git -C "$R" rev-parse HEAD)"
printf '  blob(HEAD:계약)         = %s\n' "$(git -C "$R" rev-parse "HEAD:$P")"
printf '  blob(%s:계약)     = %s\n' "$NEW" "$(git -C "$R" rev-parse "$NEW:$P")"
printf '  워킹트리 hash-object    = %s\n' "$(git -C "$R" hash-object "$WT")"
printf '  git diff --quiet %s -- 계약 → rc=%s\n' "$NEW" "$(git -C "$R" diff --quiet "$NEW" -- "$P"; echo $?)"
printf '  sha256(워킹트리)        = %s\n' "$(shasum -a 256 "$WT" | cut -d' ' -f1)"
printf '  %s..HEAD 계약 커밋 수  = %s\n' "$NEW" "$(git -C "$R" rev-list --count "$NEW"..HEAD -- "$P")"
printf '  sed -n 4608,4708p <워킹트리> sha256 = %s\n' "$(sed -n '4608,4708p' "$WT" | shasum -a 256 | cut -d' ' -f1)"
rm -f "$b_old" "$b_new"
```

### 1-3. `s24-proof-2.sh` 출력 원문 (∅ = 그 범위에서 두 blob 이 byte-동일 · ≠ = 에라타가 건드린 범위)

```text
=== S-24 절 범위 diff 기계 증명 (2026-08-19T02:33:29Z) — 동결 e3ed4e78(7277행) → 에라타 재동결 ad5be1a3(7316행) ===
$ git diff e3ed4e78..ad5be1a3 --stat -- <계약>
   ...-08-12-tos-phase0-completion-contract-design.md | 99 +++++++++++++++-------
   1 file changed, 69 insertions(+), 30 deletions(-)
$ git diff e3ed4e78..ad5be1a3 -- <계약> | grep '^@@'   (hunk 목록 — 이것이 변경의 전부)
  @@ -115,7 +115,7 @@
  @@ -198,7 +198,7 @@
  @@ -4346,13 +4346,23 @@ v2.4·v2.5 를 무효화한 행위다. **상태 표기의 currency 와 결속의
  @@ -4931,7 +4941,7 @@ D = { x ⊑ HEAD :  path ∈ tree(x)  ∧  ∀ p ∈ parents(x): path ∉ tree(p
  @@ -5522,19 +5532,30 @@ operator_countersign: "<운영자 식별> <ISO-8601 UTC>"   # 예: "operator 202
  @@ -5550,16 +5571,16 @@ P_last   = HEAD 조상 중 아티팩트 경로를 **«마지막으로 변경»**
  @@ -6903,7 +6924,7 @@ C_R(c) = { x ⊑ c :  blob(x:<reviewer_ref>) == blob(approved_at_head:<reviewer_
  @@ -6978,14 +6999,29 @@ c_APP(a) = { x ⊑ HEAD :  a ∈ rows(x:LEDGER)  ∧  ∀ p ∈ parents(x): a 
  @@ -7060,7 +7096,10 @@ U-16-d  상태  closable_no_provenance_state  (TOS-COMPLETION-STATUS 에 1급 
  @@ -7081,7 +7120,7 @@ U-16-d  상태  closable_no_provenance_state  (TOS-COMPLETION-STATUS 에 1급 

-- ① hunk 사상 (기계 파싱: 각 hunk 안에서 실제로 «바뀐» 행의 old/new 범위) --
   #  old[start,len]  new[start,len]   (len=0 은 순수 삽입/삭제)
  H1  old[118,1]        new[118,1]
  H2  old[201,1]        new[201,1]
  H3  old[4348,0]        new[4349,10]
  H4  old[4355,1]        new[4365,1]
  H5  old[4934,1]        new[4944,1]
  H6  old[5525,13]        new[5535,24]
  H7  old[5553,1]        new[5574,1]
  H8  old[5560,1]        new[5581,1]
  H9  old[5562,1]        new[5583,1]
  H10 old[6906,1]        new[6927,1]
  H11 old[6981,6]        new[7002,20]
  H12 old[6988,1]        new[7023,2]
  H13 old[7063,1]        new[7099,4]
  H14 old[7084,1]        new[7123,1]

-- ② «닿지 않는» 구간 자동 생성 + sha256 대조 (∅ = byte-동일) --
  ∅  old[1,117] == new[1,117]  sha256=8ab22be232d458c9…
  ≠   H1: old[118,118] vs new[118,118]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[119,200] == new[119,200]  sha256=128750c2bdb207c6…
  ≠   H2: old[201,201] vs new[201,201]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[202,4348] == new[202,4348]  sha256=c4d3a2f1348f6cd8…
  ≠   H3: old[4348,4348] vs new[4349,4358]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[4349,4354] == new[4359,4364]  sha256=169e627087933d1c…
  ≠   H4: old[4355,4355] vs new[4365,4365]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[4356,4933] == new[4366,4943]  sha256=209bc532726b5d14…
  ≠   H5: old[4934,4934] vs new[4944,4944]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[4935,5524] == new[4945,5534]  sha256=e3dbcdc2cff0dfc6…
  ≠   H6: old[5525,5537] vs new[5535,5558]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[5538,5552] == new[5559,5573]  sha256=812065d00ed47b6b…
  ≠   H7: old[5553,5553] vs new[5574,5574]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[5554,5559] == new[5575,5580]  sha256=b05369208a2f3ff0…
  ≠   H8: old[5560,5560] vs new[5581,5581]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[5561,5561] == new[5582,5582]  sha256=ec862dced6d16344…
  ≠   H9: old[5562,5562] vs new[5583,5583]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[5563,6905] == new[5584,6926]  sha256=9eb0904f9a8394af…
  ≠   H10: old[6906,6906] vs new[6927,6927]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[6907,6980] == new[6928,7001]  sha256=88a9b41d524533c5…
  ≠   H11: old[6981,6986] vs new[7002,7021]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[6987,6987] == new[7022,7022]  sha256=ebca58850c6623d3…
  ≠   H12: old[6988,6988] vs new[7023,7024]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[6989,7062] == new[7025,7098]  sha256=935d0729df4364db…
  ≠   H13: old[7063,7063] vs new[7099,7102]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[7064,7083] == new[7103,7122]  sha256=89ecf90fa39e50f9…
  ≠   H14: old[7084,7084] vs new[7123,7123]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[7085,7277] == new[7124,7316]  sha256=3ef0693175074403…   (말미~EOF)

-- 자동 구간 전건 결과: 전 구간 ∅ (변경은 hunk 안에만 있다) --

-- ③ 명명 절 대조 (각 blob 에서 «리터럴 grep 으로 위치 파생» — 하드코딩 행번호 아님) --
  ∅   §12.3.4-R 하니스 블록 (101행) : old[4599,4698] == new[4609,4708]  sha256=0d3a33b007033c4b…
  ∅   §8 T-84 행 (12종 — U-17 대조군) : old[2877,2877] == new[2877,2877]  sha256=acf53d204e14eb9b…
  ∅   §8 T-82 행 (20종 — U-16 대조군) : old[2927,2927] == new[2927,2927]  sha256=39641355848eef83…
  ∅   §8 T-81 행 (U-15 대조군) : old[2926,2926] == new[2926,2926]  sha256=4b416b99334a5605…
  ∅   (a) 술어 블록 전문 (E1 classic terminal 포함) : old[5244,5281] == new[5254,5291]  sha256=5570120023328a32…
  ∅   (b) 리비전 특정 전문 : old[5344,5409] == new[5354,5419]  sha256=63c63d4e387c6f37…
  ∅   (α) 연속성 술어 전문 : old[5468,5494] == new[5478,5504]  sha256=98e4571de23fbc3f…
  ∅   C6 host 결속 블록 (E3) : old[5217,5232] == new[5227,5242]  sha256=6966d914f5e1cb36…
  ∅   U-17-c 전순서 10단 : old[5568,5578] == new[5589,5599]  sha256=efca55f331d90ca9…
  ∅   U-17-d 강제 지점·종료조건·대조군 : old[5580,5584] == new[5601,5605]  sha256=d31967d667226129…
  ∅   U-16-c c_APP 수식 3행 : old[6976,6978] == new[6997,6999]  sha256=34771ac4e3a056c6…
  ∅   U-16-d 전순서 12단 표 : old[7065,7077] == new[7104,7116]  sha256=de24dfc1244e20ba…
  ∅   U-16-d ② g-단락 (5~11) : old[7092,7094] == new[7131,7133]  sha256=6bed132451327946…
  ∅   U-16-a2 전칭 판정 블록 : old[6704,6711] == new[6725,6732]  sha256=fc6bae4bfcbd4cc1…
  ∅   U-16-h 시점 고정 블록 : old[6944,6949] == new[6965,6970]  sha256=394535f673cbb928…
  ∅   U-16-b 간선 대응·고아 (E7) : old[6772,6788] == new[6793,6809]  sha256=8f6b4646b910a32e…
  ∅   U-15-g-4 CORR 술어 블록 : old[4984,4988] == new[4994,4998]  sha256=77e8185e57e2ea05…
  --
  ≠   [E8] U-16-c [PARENTS-UNTRUSTED] 정의 블록 (유일 소스) : old[6976,6989]=a575f7f0a18d178d… vs new[6997,7025]=a2c47dd49203dbf0…  (에라타가 건드림)
  ≠   [E8] 참조 1/4 — U-15-g-1 D 정의 : old[4930,4935]=94f5b6ca1f2eb77c… vs new[4940,4945]=463ba244686c9fe7…  (에라타가 건드림)
  ≠   [E8] 참조 2/4 — g6 C_R 정의 꼬리 : old[6903,6908]=0b02cbbe1308d757… vs new[6924,6929]=7d78e31d5e99bca6…  (에라타가 건드림)
  ≠   [E9]+[E8] 참조 3·4/4 — P_first/P_last 정의 + 두 상태의 기계 조건 : old[5522,5539]=43192297f02149e4… vs new[5532,5560]=f590860cb32639d1…  (에라타가 건드림)
  ≠   [E9] U-17-c 상태표 (ACTIVE·MUTATED·LATE 조건) : old[5551,5567]=a3790aa6cbf0c2c8… vs new[5572,5588]=0060054207110b5a…  (에라타가 건드림)
  ≠   [E8] U-16-d ① 선-검사 : old[7082,7092]=a604dc93f7463b16… vs new[7121,7131]=35d6bf7fd4d08008…  (에라타가 건드림)
  ≠   [N-3~5] U-16-d 전순서 머리 (세 층 주석) : old[7057,7064]=8067697a2a15022c… vs new[7093,7103]=6bba4988a23ba96b…  (에라타가 건드림)
  ≠   §12.3.3 (B) 처분표 : old[4349,4356]=f4d44e1ba6be5312… vs new[4359,4366]=c05697650d208326…  (에라타가 건드림)
  ≠   심사 이력 v2.19 행 : old[118,118]=dff472a1e21d57ce… vs new[118,118]=e5acf51508858c13…  (에라타가 건드림)
  ≠   변경 이력 v2.19 행 : old[201,201]=a84914aec86c75ea… vs new[201,201]=ca026f3c5d01ecdf…  (에라타가 건드림)

-- ④ 하니스 §12.3.4-R 블록 sha256 (계약이 리터럴로 결속한 값) --
  e3ed4e78 :4598-4698  957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  ad5be1a3 :4608-4708  957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  두 값 동일? yes
  계약 리터럴(본문 인용) 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d 과 일치? yes

-- ⑤ 워킹트리·HEAD 결속 --
  HEAD                    = ad5be1a36dc489234f71a0d8343a5d83cda13ac1
  blob(HEAD:계약)         = 22be5f331f349afd187d4b1d52d7cce17bf2860a
  blob(ad5be1a3:계약)     = 22be5f331f349afd187d4b1d52d7cce17bf2860a
  워킹트리 hash-object    = 22be5f331f349afd187d4b1d52d7cce17bf2860a
  git diff --quiet ad5be1a3 -- 계약 → rc=0
  sha256(워킹트리)        = 450ac1851cb6e62f2467f230658d6e9067d40b70319f6d683b412bce5a542f9e
  ad5be1a3..HEAD 계약 커밋 수  = 0
  sed -n 4608,4708p <워킹트리> sha256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
```

**판독**: ② 의 «자동 구간»은 hunk 사이의 **모든** 무변경 구간을 기계 생성해 old/new 양쪽에서 잘라 sha256 을 대조한 것이고 **전 구간 ∅** 다 — 변경은 hunk 안에만 있다.
③ 은 **행번호를 하드코딩하지 않고** 각 blob 에서 리터럴 grep 으로 위치를 파생하므로 shift(+10 ~ +39행)가 있어도 «같은 절끼리» 비교된다.
**`U-16-c` 는 «수식 3행 ∅» 이고 «정의 블록 ≠»** — 정의 자체는 그대로 두고 `[PARENTS-UNTRUSTED]` 단서만 아래에 붙었다는 뜻이다(직전 판과 같은 형태).
**`U-17-c` 는 «전순서 10단 ∅» 이고 «상태표 ≠»** — 전순서(값의 개수·순서)는 불변이고 세 상태의 «조건»만 E9 로 재정의됐다는 뜻이며, **T-84 12종·T-82 20종 행이 ∅ 라는 사실이 «종수 불변»을 기계적으로 확인**한다.

---

## 2. 실행기 델타 — 에라타 2차가 요구한 코드 변경만

### 2-1. `u17-verify-v219e2.sh` (sha256 `8516adc2684498fb08d5312acab8dc5f25345c9268f0ec84b738d805bfb85968`) — 직전 `6a80beed…` 대비 diff

델타 2건: **[E8]** `[SHALLOW]`→`[PARENTS-UNTRUSTED]` — ① 관측(`git replace -l` 공집합 ∧ `.git/info/grafts` 부재; **얕음은 국소로 유지** — §5 M-1) · ② 무력화(`export GIT_NO_REPLACE_OBJECTS=1` 전역) ·
**[E9]** `P_first`/`P_last` 를 ∀-부모 구조 «집합»으로(`blob_intro_set()` 신설 · ∨ 기반 `last_change()` **삭제** — 사코드 잔존 금지) + 카디널리티 처분 + `LATE`/`MUTATED`/`ACTIVE` 조건 재작성.

```diff
2,31c2,18
< # u17-verify (v2.19 에라타 e3ed4e78) — U-17 «예방 통제 활성 증거» 실행기 (계약 e3ed4e78 §12.3.4 U-17)
< #   v2.19 실행기(d5a8302a·sha256 52dd0319…) 에서 파생 — 델타는 **에라타 3건**뿐이다:
< #     [E3] 아티팩트 `host` 키 = «선택 대조»(있으면 핀 host 와 대조·불일치 = TARGET_MISMATCH / 없으면 핀 유일 소스).
< #     [SHALLOW/E5] `D`(U-15-g-1)·`P_first`/`P_last`(U-17 c) 의 «∀-부모» 항에 얕은 클론 경계 단서 — 경계 커밋(부모 미상)은
< #          «진짜 루트»가 아니므로 도입 지점으로 «확정하지 않는다» → 후보 우주에 있어 크기 0이 되면 PREVENTION_UNVERIFIABLE(전순서 1).
< #          판별: `.git/shallow` 목록 ∪ (부모 커밋 «객체» 조회 실패).  **[E6] 전역 단축이 아니라 «해당 경로의 후보 우주» 국소 판정**이다.
< #     (E1 classic terminal·E2 t_land fail-closed 는 v2.19 실행기가 이미 그 거동이었다 — 계약 문언이 따라온 것이라 코드 델타 0.)
< #   §12.3.4-R 하니스와 «별도». run 은 stdout 의 `U17-0 target=<owner>/<repo>@<branch>` 라인이 연다. CORR 은 이 run 을 보지 않는다.
< #
< #   [C3] 계약 핀 canonical_target = github.com/kakao-harris-lee/kis_unified_sts (계약 리터럴 · 아티팩트 파라미터 아님).
< #        git remote 는 «대조»: `git remote -v` 의 URL 을 host 보존 정규화(<host>/<owner>/<repo>)해 핀과 일치하는 원격이 «존재» 해야 한다(이름 무관·E3 공존 허용). 부재 = TARGET_MISMATCH.
< #        target = 핀 repo 의 `gh api --hostname <핀 host> repos/{pin}` .default_branch.  아티팩트 선언값(owner_repo·target_branch)은 «선택»[E2] — 있으면 대조·불일치 = TARGET_MISMATCH.
< #   [C6 — v2.19 신설] **host 결속**: 핀 host = canonical_target 의 host 성분(github.com).  ① 전제 `gh auth status --hostname <핀 host>` 실패 → PREVENTION_UNVERIFIABLE
< #        ② **모든** `gh api` 에 `--hostname <핀 host>` 명시  ③ 소비자 «자기 환경» `GH_HOST=<핀 host>` 재핀(플래그·환경 이중 결속 — `--hostname` 이 `GH_HOST` 를 이기는지에 의존하지 않는다)
< #        ④ 도달·인증 불가는 **타 host 로 폴백하지 않는다**(fail-closed).  ⑤ 응답 헤더 `X-GitHub-Request-Id` 를 transcript 에 병기(보조 대조).
< #   [C2] Actions app id 는 서버 파생: `gh api --hostname <핀 host> apps/github-actions` .id (gate_app_id 파라미터 폐지 — 아티팩트에 있어도 무시·기록).
< #   (a) 술어 = v2.17 + [C1] required_status_checks.checks[] 의 <check> 컨텍스트 app_id == Actions app id (룰셋: required_status_checks[].integration_id == app id).
< #   (b) ∀d∈D: pulls → merged ∧ base==target 인 PR head.sha → check-runs 에 name==check ∧ conclusion==success ∧ app.id==Actions ∧ head_sha==PR head 인 run;
< #       check-suites/{run.check_suite.id}.head_sha == PR head [E2]; 워크플로 정체성 3중 [C2]: actions/runs?check_suite_id=<id> 의 run 중 head_sha==PR head 이고 path==.github/workflows/tos-gate.yml (계약 리터럴);
< #       [R2·E1] `repos/{pin}/contents/.github/workflows/tos-gate.yml?ref=<PR head>` (서버 조회 · responder 경유) → base64 decode → 두 리터럴 `tools/tos_entry_harness.sh` · `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d` grep.
< #       404·기타 HTTP → UNVERIFIED_REVISION(검사 생략 금지) · 네트워크/인증(ERR) → UNVERIFIABLE. 로컬 `git show <head>:…` 는 보조 대조(선택·판정 미소비·U17-B5x 라인으로 기록만).
< #   (α) [v2.19 신설 — 심판 F1] **연속성 소비자**(완료 판정 시점).  **서버 시간만 소비**한다 — 커밋 author/committer date 는 쓰지 않는다.
< #       입력우주 = target 에 «적용된» 룰셋 s (`rules/branches/{target}` 의 ruleset_id → `rulesets/{id}`) · t_land = min{ merged_at(착지 PR) : d ∈ D }(서버 부여 값).
< #       ∀ 적용 룰셋 s:  created_at ≤ t_land ∧ updated_at ≤ t_land → 그 축 통과 / created_at > t_land(삭제-재생성 포함) → CONTINUITY_UNVERIFIABLE / updated_at > t_land(off→on 토글 단조) → CONTINUITY_UNVERIFIABLE.
< #       classic branch protection 만(적용 룰셋 부재) = 타임스탬프 부재 → CONTINUITY_UNVERIFIABLE.  타임스탬프 파싱 불가 → CONTINUITY_UNVERIFIABLE(fail-closed).
< #       D = ∅ → 착지 대상 없음 = vacuous.  t_land 파생 불가(D≠∅ 인데 착지 PR 미해석) → CONTINUITY_UNVERIFIABLE(이 경우 (b) 가 이미 8 로 발화하므로 전순서상 8 이 이긴다).
< #   (c) [C4/R1] P_first(최초 도입)·P_last(마지막 변경) 구조 파생(--full-history 후보 위): LATE = ∃d P_first⋠d · ARTIFACT_MUTATED = ∀d P_first⊰d ∧ ∃d P_last⋠d · ACTIVE 는 ∀d P_last⊰d ∧ HEAD blob == blob(P_last).
< #   (c-0) countersign E3 리터럴.
< #   전순서(U-17-c · 10값 · 차단 9): 1 UNVERIFIABLE > 2 ABSENT > 3 UNSIGNED > 4 TARGET_MISMATCH > 5 INSUFFICIENT > 6 LATE > 7 ARTIFACT_MUTATED > 8 UNVERIFIED_REVISION > 9 CONTINUITY_UNVERIFIABLE > 10 ACTIVE.
< #   ** 전 단계를 먼저 «수집»하고 마지막에 전순서 최소 순위를 방출한다 ** — (b) 의 조회 실패(1)가 (c) 의 LATE(6) 보다 먼저 성립하도록. exit 0 = ACTIVE 만. trap EXIT 폐쇄.
---
> # u17-verify (v2.19 에라타 2차 ad5be1a3) — U-17 «예방 통제 활성 증거» 실행기 (계약 ad5be1a3 §12.3.4 U-17)
> #   v2.19 에라타 실행기(e3ed4e78·sha256 6a80beed…) 에서 파생 — 델타는 **에라타 2차 2건**뿐이다:
> #     [E8] `[SHALLOW]` → **`[PARENTS-UNTRUSTED]`** 일반화 (U-16-c 유일 소스).  «부모 집합을 신뢰할 수 없는 상태»는 둘이다:
> #          (1) 얕은 클론 «경계»(부모 미상) — `.git/shallow` ∪ 부모 커밋 «객체» 조회 실패.  **국소**(E6: 해당 경로의 후보 우주에 있을 때만).
> #          (2) 부모 «재작성» — `git replace --graft`/replace ref · `.git/info/grafts`.  **전역 관측**(어느 커밋이 재작성됐는지
> #              per-commit 으로 판별할 수단이 없다 — replace 를 따르는 모든 명령이 «가짜» 부모를 반환하므로 뷰 전체가 오염된다).
> #          판별 = **이중**: ① 관측 `git replace -l` 공집합 ∧ `.git/info/grafts` 부재 ∧ (얕음은 국소) — 위반 → PREVENTION_UNVERIFIABLE(1)
> #                          ② 무력화 `GIT_NO_REPLACE_OBJECTS=1` 전역 export (모든 조상·부모 파생 git 호출이 replace 뷰를 따르지 않는다).
> #                          **`.git/info/grafts` 는 ② 로 꺼지지 않는다(실측)** — 그래서 ① 의 «부재 요구»가 grafts 축을 담당한다.
> #     [E9] `P_first`·`P_last` 를 `D`·`C_R`·`c_APP` 와 **동형 ∀-부모 구조 «집합»** 정의로 고정(∨ «어느 한 부모와라도 다름» 폐기):
> #          P_first = { x ⊑ HEAD : path ∈ tree(x) ∧ ∀p∈parents(x): path ∉ tree(p) }            (D 동형)
> #          P_last  = { x ⊑ HEAD : blob(x:path) == blob(HEAD:path) ∧ ∀p: blob(p:path) ≠ 그 blob }  (C_R 동형)
> #          |P_last|=0 → PREVENTION_UNVERIFIABLE · >1 → PREVENTION_ARTIFACT_MUTATED(¬LATE 하) · =1 → x_last
> #          LATE = ∃d∈D: ∀x∈P_first: x ⋠ d   ·   MUTATED = ¬LATE ∧ (|P_last|>1 ∨ ∃d: x_last ⋠ d)
> #          ACTIVE 조건 = |P_last|=1 ∧ ∀d: x_last ⊰ d ∧ 소비 blob == blob(x_last:path)   (¬LATE 하 ACTIVE/MUTATED 상보·결정적)
> #   (E1 classic terminal·E2 t_land·E3 host 키·E6 국소화 는 e3ed4e78 실행기 거동 그대로 — 코드 델타 0.)
> #   §12.3.4-R 하니스와 «별도». run 은 stdout 의 `U17-0 target=…` 라인이 연다.  전순서 10단 · exit 0 = ACTIVE 만 · trap EXIT 폐쇄.
40a28
> export GIT_NO_REPLACE_OBJECTS=1     # [E8] ② 무력화 — 모든 조상·부모 파생 git 호출이 replace 뷰를 따르지 않는다
85c73
< # ── [SHALLOW/E5] 얕은 클론 «경계» 판별 — 부모 집합이 «미상»인 커밋 (진짜 루트와 구별)
---
> # ── [PARENTS-UNTRUSTED / E8] 부모 집합 신뢰 판별 — (1) 얕은 경계(국소) · (2) 재작성(전역 관측)
88a77,79
> REPLACE_LIST=$(git replace -l 2>/dev/null | tr '\n' ' ')
> GRAFTS_PATH="$GITDIR/info/grafts"
> GRAFTS_PRESENT=$( [ -f "$GRAFTS_PATH" ] && echo yes || echo no )
89a81
> # (1) 국소 — 그 커밋의 부모가 «미상»인가 (E6: 전역 단축 아님)
112a105,110
> # [E8 ①] 전역 관측 — 부모 «재작성» 축 (replace ref · .git/info/grafts).  얕음은 국소(E6)라 여기서 발화하지 않는다.
> printf 'U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[%s] · %s=%s · is_shallow=%s · 무력화 GIT_NO_REPLACE_OBJECTS=%s\n' \
>   "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "${GIT_NO_REPLACE_OBJECTS:-∅}"
> NREP=$(printf '%s\n' $REPLACE_LIST | grep -c .)
> [ "$NREP" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED] git replace -l 비공집합(${NREP}건: $(printf '%s ' $REPLACE_LIST)) — 부모 집합 재작성 = 신뢰 불가"
> [ "$GRAFTS_PRESENT" = no ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED] $GRAFTS_PATH 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)"
242c240,243
< last_change() { local path="$1" x p b bp changed; : > "$BNDF"; for x in $(git rev-list --full-history HEAD -- "$path"); do git cat-file -e "$x:$path" 2>/dev/null || continue
---
> # [E9] P_last = «현행 blob 의 도입 지점 집합»(C_R 동형 · ∀-부모).  ∨(«어느 한 부모와라도 다름») 폐기.
> blob_intro_set() { local path="$1" b="$2" out="" x p same; : > "$BNDF"
>   for x in $(git rev-list --full-history HEAD -- "$path"); do
>     [ "$(git rev-parse -q --verify "$x:$path" 2>/dev/null || echo ABSENT)" = "$b" ] || continue
244,246c245,253
<     b=$(git rev-parse "$x:$path"); changed=0; ps=$(git log --format=%P -1 "$x"); [ -n "$ps" ] || changed=1; for p in $ps; do bp=$(git rev-parse -q --verify "$p:$path" 2>/dev/null || echo ABSENT); [ "$bp" != "$b" ] && changed=1; done; [ "$changed" = 1 ] && { printf '%s' "$x"; return; }; done; }
< if [ -n "$BODY" ]; then P_FIRST=$(intro_set "$PC" | awk '{print $NF}'); BND_P="$BND_P $(tr '\n' ' ' < "$BNDF")"
<   P_LAST=$(last_change "$PC"); BND_P="$BND_P $(tr '\n' ' ' < "$BNDF")"; else P_FIRST=""; P_LAST=""; fi
---
>     same=0; for p in $(git log --format=%P -1 "$x"); do
>       [ "$(git rev-parse -q --verify "$p:$path" 2>/dev/null || echo ABSENT)" = "$b" ] && { same=1; break; }; done
>     [ "$same" = 0 ] && out="$out $x"; done; printf '%s' "$out"; }
> if [ -n "$BODY" ]; then
>   P_FIRST_SET=$(intro_set "$PC"); BND_P="$BND_P $(tr '\n' ' ' < "$BNDF")"
>   HEAD_BLOB=$(git rev-parse "HEAD:$PC")
>   P_LAST_SET=$(blob_intro_set "$PC" "$HEAD_BLOB"); BND_P="$BND_P $(tr '\n' ' ' < "$BNDF")"
> else P_FIRST_SET=""; P_LAST_SET=""; HEAD_BLOB=""; fi
> NPF=$(printf '%s\n' $P_FIRST_SET | grep -c .); NPL=$(printf '%s\n' $P_LAST_SET | grep -c .)
248c255,256
< printf 'P_first=%s P_last=%s |D|=%s D=%s\n' "${P_FIRST:-∅}" "${P_LAST:-∅}" "$ND" "$(printf '%s ' $D)"
---
> printf 'P_first(집합·|%s|)=[%s] P_last(집합·|%s|·blob=%s)=[%s] |D|=%s D=[%s]  [E9 ∀-부모]\n' \
>   "$NPF" "$(printf '%s ' $P_FIRST_SET)" "$NPL" "${HEAD_BLOB:-∅}" "$(printf '%s ' $P_LAST_SET)" "$ND" "$(printf '%s ' $D)"
253a262,266
> sanc() { git merge-base --is-ancestor "$1" "$2" 2>/dev/null && [ "$1" != "$2" ]; }   # 진(strict) 조상
> if [ -n "$BODY" ]; then
>   # [E9] 카디널리티 처분은 «무조건 항»(c_APP 동형) — |P_last|=0 은 이력 파생 실패다
>   [ "$NPL" -ne 0 ] || fire PREVENTION_UNVERIFIABLE "[E9] |P_last|=0 — 현행 blob($HEAD_BLOB)의 도입 지점 없음 = 이력 파생 실패/[PARENTS-UNTRUSTED]"
> fi
255,260c268,278
<   LATE=0; MUT=0
<   for d in $D; do { git merge-base --is-ancestor "$P_FIRST" "$d" && [ "$P_FIRST" != "$d" ]; } || LATE=1; done
<   if [ "$LATE" = 1 ]; then fire PREVENTION_LATE "∃d∈D: P_first=$P_FIRST ⋠ d — 기록이 착수보다 늦다"
<   else for d in $D; do { git merge-base --is-ancestor "$P_LAST" "$d" && [ "$P_LAST" != "$d" ]; } || MUT=1; done
<        [ "$MUT" = 0 ] || fire PREVENTION_ARTIFACT_MUTATED "∀d P_first⊰d 이나 ∃d∈D: P_last=$P_LAST ⋠ d — 착수 «후» 아티팩트 변경"; fi
<   [ "$(git rev-parse HEAD:$PC)" = "$(git rev-parse "$P_LAST:$PC")" ] || fire PREVENTION_ARTIFACT_MUTATED "소비 blob(HEAD) ≠ P_last 시점 blob"
---
>   LATE=0
>   for d in $D; do hit=0; for x in $P_FIRST_SET; do sanc "$x" "$d" && { hit=1; break; }; done; [ "$hit" = 1 ] || LATE=1; done
>   if [ "$LATE" = 1 ]; then fire PREVENTION_LATE "[E9] ∃d∈D: ∀x∈P_first(|$NPF|) x ⋠ d — 그 착지 시점에 경로가 없었다"
>   else
>     if [ "$NPL" -gt 1 ]; then fire PREVENTION_ARTIFACT_MUTATED "[E9] ¬LATE ∧ |P_last|=$NPL>1 ($(printf '%s ' $P_LAST_SET)) — 현행 내용의 도입 지점이 유일하지 않다"
>     elif [ "$NPL" -eq 1 ]; then X_LAST=$(printf '%s' $P_LAST_SET); MUT=0
>       for d in $D; do sanc "$X_LAST" "$d" || MUT=1; done
>       [ "$MUT" = 0 ] || fire PREVENTION_ARTIFACT_MUTATED "[E9] ¬LATE ∧ ∃d∈D: x_last=$X_LAST ⋠ d — 착수 «후» 아티팩트 변경"
>       [ "$(git rev-parse "HEAD:$PC")" = "$(git rev-parse "$X_LAST:$PC")" ] || fire PREVENTION_ARTIFACT_MUTATED "[E9] 소비 blob(HEAD) ≠ blob(x_last)"
>     fi
>   fi
379c397
< finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"
---
> finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"
```

`u17-verify-v219e2-CTRL-noobserve.sh` (sha256 `380eb9b9597d3c4c939da413066ef69995e9e95b82ab7d5704058545d3d54d32`) — **① 관측 limb «만»** 제거(② 무력화 유지). 판정용 아님:

```diff
2c2
< # u17-verify (v2.19 에라타 2차 ad5be1a3) — U-17 «예방 통제 활성 증거» 실행기 (계약 ad5be1a3 §12.3.4 U-17)
---
> # u17-verify-v219e2-CTRL-noobserve — [E8 대조군] v2.19-2 실행기에서 «① 관측» limb «만» 제거한 변형 (② 무력화 GIT_NO_REPLACE_OBJECTS=1 은 유지). 판정용 아님.
109,110c109
< [ "$NREP" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED] git replace -l 비공집합(${NREP}건: $(printf '%s ' $REPLACE_LIST)) — 부모 집합 재작성 = 신뢰 불가"
< [ "$GRAFTS_PRESENT" = no ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED] $GRAFTS_PATH 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)"
---
> # [대조군] ① 관측 발화 «제거» — 무력화(②)만으로 무엇이 잡히고 무엇이 남는지 본다
```

<details><summary>`u17-verify-v219e2.sh` 전문</summary>

```bash
#!/usr/bin/env bash
# u17-verify (v2.19 에라타 2차 ad5be1a3) — U-17 «예방 통제 활성 증거» 실행기 (계약 ad5be1a3 §12.3.4 U-17)
#   v2.19 에라타 실행기(e3ed4e78·sha256 6a80beed…) 에서 파생 — 델타는 **에라타 2차 2건**뿐이다:
#     [E8] `[SHALLOW]` → **`[PARENTS-UNTRUSTED]`** 일반화 (U-16-c 유일 소스).  «부모 집합을 신뢰할 수 없는 상태»는 둘이다:
#          (1) 얕은 클론 «경계»(부모 미상) — `.git/shallow` ∪ 부모 커밋 «객체» 조회 실패.  **국소**(E6: 해당 경로의 후보 우주에 있을 때만).
#          (2) 부모 «재작성» — `git replace --graft`/replace ref · `.git/info/grafts`.  **전역 관측**(어느 커밋이 재작성됐는지
#              per-commit 으로 판별할 수단이 없다 — replace 를 따르는 모든 명령이 «가짜» 부모를 반환하므로 뷰 전체가 오염된다).
#          판별 = **이중**: ① 관측 `git replace -l` 공집합 ∧ `.git/info/grafts` 부재 ∧ (얕음은 국소) — 위반 → PREVENTION_UNVERIFIABLE(1)
#                          ② 무력화 `GIT_NO_REPLACE_OBJECTS=1` 전역 export (모든 조상·부모 파생 git 호출이 replace 뷰를 따르지 않는다).
#                          **`.git/info/grafts` 는 ② 로 꺼지지 않는다(실측)** — 그래서 ① 의 «부재 요구»가 grafts 축을 담당한다.
#     [E9] `P_first`·`P_last` 를 `D`·`C_R`·`c_APP` 와 **동형 ∀-부모 구조 «집합»** 정의로 고정(∨ «어느 한 부모와라도 다름» 폐기):
#          P_first = { x ⊑ HEAD : path ∈ tree(x) ∧ ∀p∈parents(x): path ∉ tree(p) }            (D 동형)
#          P_last  = { x ⊑ HEAD : blob(x:path) == blob(HEAD:path) ∧ ∀p: blob(p:path) ≠ 그 blob }  (C_R 동형)
#          |P_last|=0 → PREVENTION_UNVERIFIABLE · >1 → PREVENTION_ARTIFACT_MUTATED(¬LATE 하) · =1 → x_last
#          LATE = ∃d∈D: ∀x∈P_first: x ⋠ d   ·   MUTATED = ¬LATE ∧ (|P_last|>1 ∨ ∃d: x_last ⋠ d)
#          ACTIVE 조건 = |P_last|=1 ∧ ∀d: x_last ⊰ d ∧ 소비 blob == blob(x_last:path)   (¬LATE 하 ACTIVE/MUTATED 상보·결정적)
#   (E1 classic terminal·E2 t_land·E3 host 키·E6 국소화 는 e3ed4e78 실행기 거동 그대로 — 코드 델타 0.)
#   §12.3.4-R 하니스와 «별도». run 은 stdout 의 `U17-0 target=…` 라인이 연다.  전순서 10단 · exit 0 = ACTIVE 만 · trap EXIT 폐쇄.
# 사용: bash u17-verify-v219.sh [<repo-dir>]      (env: U17_RESPONDER=gh|file:<dir>|mixed:<dir> · U17_CAPTURE_DIR)
set -u -o pipefail
CANON=github.com/kakao-harris-lee/kis_unified_sts     # 계약 핀 (C3)
PIN_HOST=${CANON%%/*}                                 # [C6] 핀 host — 계약 핀에서 «파생»(아티팩트 선언 아님)
WF_PATH=.github/workflows/tos-gate.yml                # 계약 리터럴 (C2)
LIT1=tools/tos_entry_harness.sh                       # 계약 리터럴 (R2-i)
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d   # 계약 리터럴 (R2-ii) — §12.3.4-R 블록 sha256
INHERITED_GH_HOST="${GH_HOST-∅(미설정)}"              # [C6] 재핀 «전» 상속값 기록
export GH_HOST="$PIN_HOST"                            # [C6] ③ 소비자 자기 환경 재핀 (플래그·환경 이중 결속)
export GIT_NO_REPLACE_OBJECTS=1     # [E8] ② 무력화 — 모든 조상·부모 파생 git 호출이 replace 뷰를 따르지 않는다
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
rank() { case "$1" in PREVENTION_UNVERIFIABLE) echo 1;; PREVENTION_ABSENT) echo 2;; PREVENTION_UNSIGNED) echo 3;; PREVENTION_TARGET_MISMATCH) echo 4;; PREVENTION_INSUFFICIENT) echo 5;; PREVENTION_LATE) echo 6;; PREVENTION_ARTIFACT_MUTATED) echo 7;; PREVENTION_UNVERIFIED_REVISION) echo 8;; PREVENTION_CONTINUITY_UNVERIFIABLE) echo 9;; *) echo 99;; esac; }
FIRED=""; NF=0; fire() { NF=$((NF+1)); FIRED="$FIRED$1|$2"$'\n'; printf 'U17-fire %s: %s\n' "$1" "$2"; }
finish() { local best="" bestr=99 f s r; while IFS= read -r f; do [ -n "$f" ] || continue; s=${f%%|*}; r=$(rank "$s"); if [ "$r" -lt "$bestr" ]; then bestr=$r; best="$f"; fi; done <<< "$FIRED"
  if [ -n "$best" ]; then emit "${best%%|*}" "${best#*|} [수집 ${NF}건 중 전순서 최소]"; fi; emit PREVENTION_ACTIVE "$1"; }

# ── responder seam  ([C6] gh 경로의 모든 조회에 --hostname <핀 host> 명시 · 헤더 별도 보존)
respond() {
  local path="$1" k; k=$(key "$1"); local st="$CAP/$k.status" bd="$CAP/$k.body" hd="$CAP/$k.hdr"
  case "$RESP" in
    gh)  local out; out=$(gh api -i --hostname "$PIN_HOST" "$path" 2>"$CAP/$k.err"); printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"
         printf '%s\n' "$out" | awk '/^\r?$/{exit} {print}' | tr -d '\r' > "$hd"
         printf '%s\n' "$out" | awk 'f{print} /^\r?$/{f=1}' | tr -d '\r' > "$bd"
         if ! grep -Eq '^[0-9]{3}$' "$st"; then printf 'ERR\n' > "$st"; cat "$CAP/$k.err" > "$bd" 2>/dev/null; return 1; fi; return 0 ;;
    file:*) local dir="${RESP#file:}"
         if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; : > "$hd"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'ERR\n' > "$st"; printf 'SIMULATED responder: no injected response for %s\n' "$path" > "$bd"; : > "$hd"; return 1; fi ;;
    mixed:*) local dir="${RESP#mixed:}"
         if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; : > "$hd"; printf 'U17-seam %s ← file(SIMULATED)\n' "$path"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'U17-seam %s ← gh(live)\n' "$path"; local save="$RESP"; RESP=gh; respond "$path"; local r=$?; RESP="$save"; return $r; fi ;;
    *) emit PREVENTION_UNVERIFIABLE "알 수 없는 responder: $RESP" ;;
  esac
}
reqid() { grep -i '^X-GitHub-Request-Id:' "$CAP/$(key "$1").hdr" 2>/dev/null | head -1 | tr -d '\r' | sed 's/^[Xx]-[Gg]it[Hh]ub-[Rr]equest-[Ii]d:[[:space:]]*//'; }
show_capture() { local k; k=$(key "$2"); printf 'U17-%s %s  utc=%s  http=%s  x-github-request-id=%s\n' "$1" "$2" "$(utc)" "$(cat "$CAP/$k.status")" "$(reqid "$2")"; sed 's/^/  | /' "$CAP/$k.body"; }
jget() { python3 -c 'import json,sys
try:
    j=json.load(open(sys.argv[1]))
    for kk in sys.argv[2].split("."):
        j=j[int(kk)] if isinstance(j,list) else j[kk]
    print(j if not isinstance(j,(dict,list)) else json.dumps(j))
except Exception: print("")' "$CAP/$(key "$1").body" "$2" 2>/dev/null; }
http_of() { cat "$CAP/$(key "$1").status" 2>/dev/null; }
ok2xx() { printf '%s' "$1" | grep -Eq '^2'; }
# ── [PARENTS-UNTRUSTED / E8] 부모 집합 신뢰 판별 — (1) 얕은 경계(국소) · (2) 재작성(전역 관측)
GITDIR=$(git rev-parse --git-dir 2>/dev/null || echo .git)
IS_SHALLOW=$(git rev-parse --is-shallow-repository 2>/dev/null || echo unknown)
SHALLOW_LIST=$( [ -f "$GITDIR/shallow" ] && tr '\n' ' ' < "$GITDIR/shallow" || printf '' )
REPLACE_LIST=$(git replace -l 2>/dev/null | tr '\n' ' ')
GRAFTS_PATH="$GITDIR/info/grafts"
GRAFTS_PRESENT=$( [ -f "$GRAFTS_PATH" ] && echo yes || echo no )
have_commit() { git cat-file -e "$1^{commit}" 2>/dev/null; }
# (1) 국소 — 그 커밋의 부모가 «미상»인가 (E6: 전역 단축 아님)
is_boundary() { local x="$1" b p; for b in $SHALLOW_LIST; do [ "$b" = "$x" ] && return 0; done
  for p in $(git log --format=%P -1 "$x"); do have_commit "$p" || return 0; done; return 1; }

# ── [C3] 핀·원격 대조 (host 보존 정규화)
PIN_OR=${CANON#*/}
norm_url() { printf '%s' "$1" | sed -E 's#^https?://([^/]+)/(.+)$#\1/\2#; s#^ssh://git@([^/]+)/(.+)$#\1/\2#; s#^git@([^:]+):(.+)$#\1/\2#; s#\.git$##; s#/$##'; }
REMOTES=$(git remote -v 2>/dev/null | awk '{print $1" "$2}' | sort -u)
MATCH_REMOTE=""; NORMED=""
while read -r rn ru; do [ -n "${ru:-}" ] || continue; n=$(norm_url "$ru"); NORMED="$NORMED $rn=$n"; [ "$n" = "$CANON" ] && MATCH_REMOTE="$rn"; done <<< "$REMOTES"

# ── [C6 ①] 전제: 핀 host 인증  (responder=file 은 live 조회가 없으므로 SIMULATED 로 기록만)
AUTHRC=0; AUTHOUT=""; AUTHMODE=live
AUTHCMD="gh auth status --hostname $PIN_HOST"                     # [C6] 표시·사유 문자열 (대조군은 이 줄과 다음 줄이 함께 바뀐다)
case "$RESP" in file:*) AUTHMODE=simulated ;; *) AUTHOUT=$(gh auth status --hostname "$PIN_HOST" 2>&1); AUTHRC=$? ;; esac

# ── [C2] Actions app id 서버 파생 · [C3] target = 핀 repo default_branch  (A00·A0)
respond "apps/github-actions"; ST_APP=$(http_of "apps/github-actions"); APPID=$(jget "apps/github-actions" id)
respond "repos/$PIN_OR";       ST0=$(http_of "repos/$PIN_OR");          TARGET=$(jget "repos/$PIN_OR" default_branch)
printf 'U17-0 target=%s@%s\n' "$PIN_OR" "${TARGET:-UNRESOLVED}"
printf 'U17-0 pin=%s remotes:%s match=%s | actions_app_id=%s (apps/github-actions http=%s) | responder=%s capture_dir=%s\n' "$CANON" "${NORMED:- (none)}" "${MATCH_REMOTE:-∅}" "${APPID:-∅}" "$ST_APP" "$RESP" "$CAP"
printf 'U17-H [C6] pin_host=%s (계약 핀에서 파생) · 상속 GH_HOST=%s → 현행 GH_HOST=%s · auth 전제 `%s` → mode=%s rc=%s\n' "$PIN_HOST" "$INHERITED_GH_HOST" "${GH_HOST-∅(재핀 없음)}" "$AUTHCMD" "$AUTHMODE" "$AUTHRC"
if [ "$AUTHMODE" = live ]; then printf '%s\n' "$AUTHOUT" | sed 's/^/  | /'; else printf '  | (responder=%s — live 조회 없음: 주입 응답 위 결정적 술어)\n' "$RESP"; fi
[ "$AUTHMODE" != live ] || [ "$AUTHRC" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[C6] \`$AUTHCMD\` 실패(rc=$AUTHRC) — 핀 host 인증 부재 (타 host 폴백 없음)"
# [E8 ①] 전역 관측 — 부모 «재작성» 축 (replace ref · .git/info/grafts).  얕음은 국소(E6)라 여기서 발화하지 않는다.
printf 'U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[%s] · %s=%s · is_shallow=%s · 무력화 GIT_NO_REPLACE_OBJECTS=%s\n' \
  "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "${GIT_NO_REPLACE_OBJECTS:-∅}"
NREP=$(printf '%s\n' $REPLACE_LIST | grep -c .)
[ "$NREP" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED] git replace -l 비공집합(${NREP}건: $(printf '%s ' $REPLACE_LIST)) — 부모 집합 재작성 = 신뢰 불가"
[ "$GRAFTS_PRESENT" = no ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED] $GRAFTS_PATH 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)"
show_capture A00 "apps/github-actions"; printf 'U17-A0 repos/%s  utc=%s  http=%s  x-github-request-id=%s  (.default_branch=%s)\n' "$PIN_OR" "$(utc)" "$ST0" "$(reqid "repos/$PIN_OR")" "${TARGET:-∅}"
{ ok2xx "$ST_APP" && [ -n "$APPID" ]; } || fire PREVENTION_UNVERIFIABLE "apps/github-actions 조회 실패(http=$ST_APP) — Actions app id 파생 불가"
{ ok2xx "$ST0" && [ -n "$TARGET" ]; }   || fire PREVENTION_UNVERIFIABLE "repos/$PIN_OR 조회 실패(http=$ST0) — default_branch 파생 불가"
[ -n "$MATCH_REMOTE" ] || fire PREVENTION_TARGET_MISMATCH "계약 핀 $CANON 과 일치하는 원격 부재 (git remote -v 정규화:${NORMED:- none})"

# ── 아티팩트 (전순서 2 ABSENT · 대조값·countersign)  — 커밋-전용 읽기
BODY=$(git show "HEAD:$PC" 2>/dev/null) || { fire PREVENTION_ABSENT "아티팩트 HEAD 부재: $PC"; BODY=""; }
yv() { printf '%s\n' "$BODY" | sed -n "s/^$1:[[:space:]]*//p" | sed 's/[[:space:]]*#.*$//; s/[[:space:]]*$//' | head -1; }
DECL_OR=$(yv owner_repo); DECL_TB=$(yv target_branch); CHECK=$(yv tos_gate_check); [ -n "$CHECK" ] || CHECK=tos-gate
[ -z "$(yv gate_app_id)" ] || printf 'U17-note 아티팩트에 gate_app_id 키가 있으나 v2.18 은 폐지(무시) — 서버 파생값 %s 사용\n' "$APPID"
[ -z "$(yv remote_name)" ]  || printf 'U17-note 아티팩트에 remote_name 키가 있으나 v2.18 은 폐지(무시) — 핀 대조는 원격 이름을 묻지 않는다\n'
DECL_HOST=$(yv host)
if [ -n "$BODY" ]; then
  MM=""   # [E2] 선언 키는 «선택» — 있으면 대조, 없으면 핀·API 파생이 유일 소스
  if [ -n "$DECL_OR" ]; then case "$DECL_OR" in "$CANON"|"$PIN_OR") ;; *) MM="$MM owner_repo(선언=$DECL_OR ≠ 핀=$CANON)";; esac; fi
  if [ -n "$DECL_TB" ] && [ -n "$TARGET" ] && [ "$DECL_TB" != "$TARGET" ]; then MM="$MM target_branch(선언=$DECL_TB ≠ 핀 repo default=$TARGET)"; fi
  # [E3] host 키도 «선택 대조» — 있으면 핀 host 와 대조, 없으면 핀이 유일 소스 (선언으로 host 를 «고를» 수 없다)
  if [ -n "$DECL_HOST" ] && [ "$DECL_HOST" != "$PIN_HOST" ]; then MM="$MM host(선언=$DECL_HOST ≠ 핀 host=$PIN_HOST)"; fi
  printf 'U17-T declared-vs-pin: %s (declared owner_repo=%s target_branch=%s host=%s)\n' "${MM:-일치/선언 없음}" "${DECL_OR:-∅(선택 키 부재 → 핀 유일 소스)}" "${DECL_TB:-∅(선택 키 부재 → default_branch 유일 소스)}" "${DECL_HOST:-∅(선택 키 부재 → 핀 host 유일 소스)}"
  [ -z "$MM" ] || fire PREVENTION_TARGET_MISMATCH "아티팩트 선언값이 계약 핀/파생값과 불일치:$MM"
  CS_RE='^operator_countersign:[[:space:]]*"[^"[:space:]][^"]* [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"[[:space:]]*(#.*)?$'
  nk=$(printf '%s\n' "$BODY" | grep -c '^operator_countersign:')
  if [ "$nk" != 1 ]; then fire PREVENTION_UNSIGNED "operator_countersign 키 출현 횟수=$nk (정확히 1 요구)"
  elif ! printf '%s\n' "$BODY" | grep -Eq "$CS_RE"; then fire PREVENTION_UNSIGNED "operator_countersign 값 형식 위반: $(printf '%s\n' "$BODY" | grep '^operator_countersign:')"; fi
fi

# ── (a) 4 엔드포인트 (핀 repo · 파생 target)
APPLIED_IDS=""
if [ -n "$TARGET" ]; then
P_PROT="repos/$PIN_OR/branches/$TARGET/protection"; P_RULES="repos/$PIN_OR/rules/branches/$TARGET"; P_RSETS="repos/$PIN_OR/rulesets"
respond "$P_PROT";  show_capture A1 "$P_PROT"
respond "$P_RULES"; show_capture A2 "$P_RULES"
respond "$P_RSETS"; show_capture A3 "$P_RSETS"
# [α] 연속성 입력우주 = target 에 «적용된» 룰셋만 (rules/branches/{target} 의 ruleset_id) — rulesets 목록 전체가 아니다
APPLIED_IDS=$(python3 -c 'import json,sys
ids=[]
try:
    a=json.load(open(sys.argv[1]))
    for r in a if isinstance(a,list) else []:
        if isinstance(r,dict) and r.get("ruleset_id") is not None and str(r["ruleset_id"]) not in ids: ids.append(str(r["ruleset_id"]))
except Exception: pass
print(" ".join(ids))' "$CAP/$(key "$P_RULES").body" 2>/dev/null)
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
for id in $RSIDS; do respond "repos/$PIN_OR/rulesets/$id"; show_capture A4 "repos/$PIN_OR/rulesets/$id"; done
[ -n "$RSIDS" ] || printf 'U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)\n'
printf 'U17-α0 적용 룰셋(연속성 입력우주) = [%s]  (rules/branches/%s 의 ruleset_id · rulesets 목록 전체=[%s])\n' "$(printf '%s' "$APPLIED_IDS")" "$TARGET" "$(printf '%s' "$RSIDS")"
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
# [SHALLOW/E5] 후보 우주 안에 «경계 커밋»이 있으면 그 x 를 도입 지점으로 «확정하지 않는다».
# 함수는 «명령 치환 서브셸»에서 돌므로 변수로 되돌릴 수 없다 — 경계 목록은 파일로 넘긴다.
BNDF=$(mktemp); BND_D=""; BND_P=""
intro_set() { local path="$1" out="" x p intro; : > "$BNDF"; for x in $(git rev-list --full-history HEAD -- "$path"); do git cat-file -e "$x:$path" 2>/dev/null || continue
    if is_boundary "$x"; then printf '%s\n' "$x" >> "$BNDF"; continue; fi
    intro=1; for p in $(git log --format=%P -1 "$x"); do git cat-file -e "$p:$path" 2>/dev/null && { intro=0; break; }; done; [ "$intro" = 1 ] && out="$out $x"; done; printf '%s' "$out"; }
# [E9] P_last = «현행 blob 의 도입 지점 집합»(C_R 동형 · ∀-부모).  ∨(«어느 한 부모와라도 다름») 폐기.
blob_intro_set() { local path="$1" b="$2" out="" x p same; : > "$BNDF"
  for x in $(git rev-list --full-history HEAD -- "$path"); do
    [ "$(git rev-parse -q --verify "$x:$path" 2>/dev/null || echo ABSENT)" = "$b" ] || continue
    if is_boundary "$x"; then printf '%s\n' "$x" >> "$BNDF"; continue; fi
    same=0; for p in $(git log --format=%P -1 "$x"); do
      [ "$(git rev-parse -q --verify "$p:$path" 2>/dev/null || echo ABSENT)" = "$b" ] && { same=1; break; }; done
    [ "$same" = 0 ] && out="$out $x"; done; printf '%s' "$out"; }
if [ -n "$BODY" ]; then
  P_FIRST_SET=$(intro_set "$PC"); BND_P="$BND_P $(tr '\n' ' ' < "$BNDF")"
  HEAD_BLOB=$(git rev-parse "HEAD:$PC")
  P_LAST_SET=$(blob_intro_set "$PC" "$HEAD_BLOB"); BND_P="$BND_P $(tr '\n' ' ' < "$BNDF")"
else P_FIRST_SET=""; P_LAST_SET=""; HEAD_BLOB=""; fi
NPF=$(printf '%s\n' $P_FIRST_SET | grep -c .); NPL=$(printf '%s\n' $P_LAST_SET | grep -c .)
D=$(intro_set "$CFG"); BND_D=$(tr '\n' ' ' < "$BNDF"); ND=$(printf '%s\n' $D | grep -c .)
printf 'P_first(집합·|%s|)=[%s] P_last(집합·|%s|·blob=%s)=[%s] |D|=%s D=[%s]  [E9 ∀-부모]\n' \
  "$NPF" "$(printf '%s ' $P_FIRST_SET)" "$NPL" "${HEAD_BLOB:-∅}" "$(printf '%s ' $P_LAST_SET)" "$ND" "$(printf '%s ' $D)"
BND_D=$(printf '%s\n' $BND_D | sort -u | tr '\n' ' '); BND_P=$(printf '%s\n' $BND_P | sort -u | tr '\n' ' ')
NBD=$(printf '%s\n' $BND_D | grep -c .); NBP=$(printf '%s\n' $BND_P | grep -c .)
printf 'U17-SHALLOW is_shallow=%s .git/shallow=[%s] · 후보 우주 내 경계 커밋: D=[%s](%s건) P=[%s](%s건)  (E6: 전역 단축 아님 — 경로별 국소 판정)\n' "$IS_SHALLOW" "$(printf '%s ' $SHALLOW_LIST)" "$(printf '%s ' $BND_D)" "$NBD" "$(printf '%s ' $BND_P)" "$NBP"
[ "$NBD" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[SHALLOW] D 후보 우주에 얕은 클론 경계 커밋($(printf '%s ' $BND_D)) — 부모 미상이라 도입 지점 확정 불가 (부재를 «참»으로 접지 않는다)"
[ "$NBP" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[SHALLOW] P_first/P_last 후보 우주에 얕은 클론 경계 커밋($(printf '%s ' $BND_P)) — 확정 불가"
sanc() { git merge-base --is-ancestor "$1" "$2" 2>/dev/null && [ "$1" != "$2" ]; }   # 진(strict) 조상
if [ -n "$BODY" ]; then
  # [E9] 카디널리티 처분은 «무조건 항»(c_APP 동형) — |P_last|=0 은 이력 파생 실패다
  [ "$NPL" -ne 0 ] || fire PREVENTION_UNVERIFIABLE "[E9] |P_last|=0 — 현행 blob($HEAD_BLOB)의 도입 지점 없음 = 이력 파생 실패/[PARENTS-UNTRUSTED]"
fi
if [ -n "$BODY" ] && [ "$ND" -gt 0 ]; then
  LATE=0
  for d in $D; do hit=0; for x in $P_FIRST_SET; do sanc "$x" "$d" && { hit=1; break; }; done; [ "$hit" = 1 ] || LATE=1; done
  if [ "$LATE" = 1 ]; then fire PREVENTION_LATE "[E9] ∃d∈D: ∀x∈P_first(|$NPF|) x ⋠ d — 그 착지 시점에 경로가 없었다"
  else
    if [ "$NPL" -gt 1 ]; then fire PREVENTION_ARTIFACT_MUTATED "[E9] ¬LATE ∧ |P_last|=$NPL>1 ($(printf '%s ' $P_LAST_SET)) — 현행 내용의 도입 지점이 유일하지 않다"
    elif [ "$NPL" -eq 1 ]; then X_LAST=$(printf '%s' $P_LAST_SET); MUT=0
      for d in $D; do sanc "$X_LAST" "$d" || MUT=1; done
      [ "$MUT" = 0 ] || fire PREVENTION_ARTIFACT_MUTATED "[E9] ¬LATE ∧ ∃d∈D: x_last=$X_LAST ⋠ d — 착수 «후» 아티팩트 변경"
      [ "$(git rev-parse "HEAD:$PC")" = "$(git rev-parse "$X_LAST:$PC")" ] || fire PREVENTION_ARTIFACT_MUTATED "[E9] 소비 blob(HEAD) ≠ blob(x_last)"
    fi
  fi
fi

# ── (b) 리비전 특정 ∀d∈D (전순서 8) — D=∅ 는 «검증 대상 없음»(명시)
MINMERGED=""
if [ "$ND" -eq 0 ]; then
  printf 'U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)\n'
elif [ -n "$TARGET" ]; then
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
fi

# ── (α) [v2.19 — 심판 F1] 연속성 소비자 (전순서 9) — «서버 시간»만 소비한다
if [ "$ND" -eq 0 ]; then
  printf 'U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)\n'
elif [ -z "$TARGET" ]; then
  printf 'U17-α target 미파생 — 연속성 평가 불가 (전순서 1 이 이미 발화)\n'
elif [ -z "$MINMERGED" ]; then
  fire PREVENTION_CONTINUITY_UNVERIFIABLE "t_land 파생 불가(D≠∅ 이나 착지 PR 의 서버 merged_at 미해석) — 연속성 판정 불가"
else
  printf 'U17-α t_land = min{merged_at(착지 PR) : d∈D} = %s  (서버 부여 값만 · 커밋 author/committer date 불신)\n' "$MINMERGED"
  if [ -z "$APPLIED_IDS" ]; then
    fire PREVENTION_CONTINUITY_UNVERIFIABLE "적용 룰셋 0 = classic branch protection 만 → protection 응답에 created_at·updated_at 부재 → 연속성 판정 불가"
  else
    for id in $APPLIED_IDS; do
      CA=$(jget "repos/$PIN_OR/rulesets/$id" created_at); UA=$(jget "repos/$PIN_OR/rulesets/$id" updated_at)
      CONT=$(python3 - "$id" "$CA" "$UA" "$MINMERGED" <<'PY'
import sys,datetime
i,ca,ua,mm=sys.argv[1:5]
def p(s):
    try: return datetime.datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(datetime.timezone.utc)
    except Exception: return None
c,u,m=p(ca),p(ua),p(mm)
if m is None: print("BLOCK|t_land 파싱 불가(merged_at=%s)"%mm); sys.exit(0)
if c is None or u is None: print("BLOCK|ruleset %s 서버 타임스탬프 부재·파싱 불가(created_at=%s updated_at=%s) — 연속성 판정 불가"%(i,ca,ua)); sys.exit(0)
if c>m: print("BLOCK|ruleset %s created_at=%s > t_land=%s — 룰셋이 «착지 후»에 생김(삭제-재생성 포함) = 그 착지는 비보호"%(i,c.isoformat(),m.isoformat())); sys.exit(0)
if u>m: print("BLOCK|ruleset %s updated_at=%s > t_land=%s — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가"%(i,u.isoformat(),m.isoformat())); sys.exit(0)
print("PASS|ruleset %s created_at=%s ≤ t_land ∧ updated_at=%s ≤ t_land"%(i,c.isoformat(),u.isoformat()))
PY
)
      printf 'U17-α ruleset %s: %s\n' "$id" "${CONT#*|}"
      case "$CONT" in BLOCK\|*) fire PREVENTION_CONTINUITY_UNVERIFIABLE "(α) ${CONT#*|} — 운영자 재심사 경로(영구 차단 아님)";; esac
    done
  fi
fi

finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"
```
</details>

### 2-2. `u16-full-exec-v219e2.py` (sha256 `cca1d6d7e491a7941f82897ea834655ab6494eff94cae15c70939435ac709482`) — 직전 `729867ca…` 대비 diff

델타 1건: **[E8]** — `replace_refs()`·`grafts_present()` 신설(① 관측 · 전역 `PROVENANCE_UNVERIFIABLE` 기여) + 모든 git 호출을 `git --no-replace-objects -C <repo> …` 로 고정(② 무력화). `is_boundary()` 는 «얕음 국소» 축으로 남는다.
**E9 는 U-17 소관**이라 이 실행기의 델타가 아니다.

```diff
2c2
< """U-16 «전 규칙» 손 실행기 — v2.19 에라타 (계약 e3ed4e78 §13.6.5 U-16-a/a2/b/c/d/f/g(g1~g6)/h).
---
> """U-16 «전 규칙» 손 실행기 — v2.19 에라타 2차 (계약 ad5be1a3 §13.6.5 U-16-a/a2/b/c/d/f/g(g1~g6)/h).
3a4,12
> v2.19 에라타 실행기(e3ed4e78·sha256 729867ca…) 에서 파생 — 델타는 **에라타 2차 [E8] 1건**뿐이다:
>   `[SHALLOW]` → **`[PARENTS-UNTRUSTED]`** 일반화(U-16-c 유일 소스).  «부모 집합을 신뢰할 수 없는 상태»는 둘이다 —
>   (1) 얕은 클론 «경계»(부모 미상): `.git/shallow` ∪ 부모 커밋 «객체» 조회 실패 → **국소**(E6 — 해당 행/간선의 후보 우주에 있을 때만)
>   (2) 부모 «재작성»: `git replace --graft`/replace ref · `.git/info/grafts` → **전역 관측**(어느 커밋이 재작성됐는지 per-commit 판별 수단이 없다)
>   판별 = 이중: ① 관측 `git replace -l` 공집합 ∧ `.git/info/grafts` 부재 — 위반 → `PROVENANCE_UNVERIFIABLE`(전순서 2)
>               ② 무력화 `GIT_NO_REPLACE_OBJECTS=1` 전역(모든 조상·부모 파생 git 호출).  **grafts 는 ② 로 꺼지지 않는다(실측)** — ① 이 그 축을 담당.
>   E9(P_first/P_last)는 U-17 소관이라 이 실행기의 델타가 아니다.
> 
> 
48a58,61
> # [E8 ②] 무력화 — 모든 git 호출이 replace 뷰를 따르지 않는다 (grafts 는 이 플래그로 꺼지지 않는다: ① 관측이 담당)
> GITBASE = ["git", "--no-replace-objects", "-C"]
> 
> 
50c63
<     return subprocess.run(["git", "-C", R, *a], capture_output=True, text=True).stdout.strip()
---
>     return subprocess.run([*GITBASE, R, *a], capture_output=True, text=True).stdout.strip()
54c67
<     return subprocess.run(["git", "-C", R, *a], capture_output=True).returncode == 0
---
>     return subprocess.run([*GITBASE, R, *a], capture_output=True).returncode == 0
76c89
<     r = subprocess.run(["git", "-C", R, "show", f"{c}:{p}"], capture_output=True, text=True)
---
>     r = subprocess.run([*GITBASE, R, "show", f"{c}:{p}"], capture_output=True, text=True)
147a161,165
> 
> 
> def replace_refs():
>     """[E8 ①] `git replace -l` — 부모 «재작성» 관측 (grafts 는 여기에 «나타나지 않는다» — 실측)."""
>     return [x for x in g("replace", "-l").split() if x]
149a168,175
> def grafts_present():
>     """[E8 ①] `.git/info/grafts` 실재 여부 (deprecated 이나 동작하며 `--no-replace-objects` 로 꺼지지 않는다 — 실측)."""
>     import os
>     d = g("rev-parse", "--git-dir")
>     base = d if os.path.isabs(d) else os.path.join(R, d)
>     return os.path.exists(os.path.join(base, "info", "grafts"))
> 
> 
151c177,178
<     """[SHALLOW/E5] 얕은 클론 «경계» — 부모 집합이 «미상»인 커밋 (진짜 루트와 구별한다)."""
---
>     """[PARENTS-UNTRUSTED (1)] 얕은 클론 «경계» — 그 커밋의 부모 집합이 «미상» (진짜 루트와 구별한다).
>     (2) «재작성» 축은 per-commit 판별 수단이 없어 main() 의 «전역 관측»이 담당한다."""
204a232,234
>     REPL, GRAFTS = replace_refs(), grafts_present()
>     print(f"[PARENTS-UNTRUSTED] 관측: git replace -l={[x[:7] for x in REPL]} · .git/info/grafts={'present' if GRAFTS else 'ABSENT'}"
>           f" · is_shallow={SHALLOW} · 무력화 = git --no-replace-objects (전 호출)")
280a311,316
>     if REPL:
>         add("global", "PROVENANCE_UNVERIFIABLE",
>             "[PARENTS-UNTRUSTED] git replace -l 비공집합(%s) — 부모 집합 재작성 = 신뢰 불가" % [x[:7] for x in REPL])
>     if GRAFTS:
>         add("global", "PROVENANCE_UNVERIFIABLE",
>             "[PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)")
```

`u16-full-exec-v219e2-CTRL-noobserve.py` (sha256 `87c1efa0aaf9ff3b69663904cd093fca1466b03b8b5b911a7c49089fc50862f9`):

```diff
2c2
< """U-16 «전 규칙» 손 실행기 — v2.19 에라타 2차 (계약 ad5be1a3 §13.6.5 U-16-a/a2/b/c/d/f/g(g1~g6)/h).
---
> """[E8 대조군 — 판정용 아님] u16-full-exec-v219e2 에서 «① 관측» limb «만» 제거(② 무력화 --no-replace-objects 유지). (계약 ad5be1a3 §13.6.5 U-16-a/a2/b/c/d/f/g(g1~g6)/h).
311,316c311
<     if REPL:
<         add("global", "PROVENANCE_UNVERIFIABLE",
<             "[PARENTS-UNTRUSTED] git replace -l 비공집합(%s) — 부모 집합 재작성 = 신뢰 불가" % [x[:7] for x in REPL])
<     if GRAFTS:
<         add("global", "PROVENANCE_UNVERIFIABLE",
<             "[PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)")
---
>     # [대조군] ① 관측 발화 «제거» — 무력화(②)만으로 무엇이 잡히고 무엇이 남는지 본다
```

<details><summary>`u16-full-exec-v219e2.py` 전문</summary>

```python
#!/usr/bin/env python3
"""U-16 «전 규칙» 손 실행기 — v2.19 에라타 2차 (계약 ad5be1a3 §13.6.5 U-16-a/a2/b/c/d/f/g(g1~g6)/h).

v2.19 에라타 실행기(e3ed4e78·sha256 729867ca…) 에서 파생 — 델타는 **에라타 2차 [E8] 1건**뿐이다:
  `[SHALLOW]` → **`[PARENTS-UNTRUSTED]`** 일반화(U-16-c 유일 소스).  «부모 집합을 신뢰할 수 없는 상태»는 둘이다 —
  (1) 얕은 클론 «경계»(부모 미상): `.git/shallow` ∪ 부모 커밋 «객체» 조회 실패 → **국소**(E6 — 해당 행/간선의 후보 우주에 있을 때만)
  (2) 부모 «재작성»: `git replace --graft`/replace ref · `.git/info/grafts` → **전역 관측**(어느 커밋이 재작성됐는지 per-commit 판별 수단이 없다)
  판별 = 이중: ① 관측 `git replace -l` 공집합 ∧ `.git/info/grafts` 부재 — 위반 → `PROVENANCE_UNVERIFIABLE`(전순서 2)
              ② 무력화 `GIT_NO_REPLACE_OBJECTS=1` 전역(모든 조상·부모 파생 git 호출).  **grafts 는 ② 로 꺼지지 않는다(실측)** — ① 이 그 축을 담당.
  E9(P_first/P_last)는 U-17 소관이라 이 실행기의 델타가 아니다.


v2.19 실행기(d5a8302a·sha256 5692e75d…) 에서 파생 — 델타는 **에라타 [SHALLOW]/E5 1건**뿐이다:
  `C_R(c)`(g6) 의 «∀-부모» 항에도 얕은 클론 경계 단서를 적용한다(계약 U-16-c [SHALLOW] 동형 — `c_APP` 는 v2.19 에
  이미 적용돼 있었고 에라타가 그 독해를 계약 문언으로 승격했다).  경계 커밋은 «진짜 루트»가 아니므로 도입 지점으로
  «확정하지 않는다» → 그 결과 `C_R` 크기 0 → 선-검사 2 `PROVENANCE_UNVERIFIABLE`.
  **[E6] 전역 단축이 아니라 «해당 행/간선의 후보 우주» 국소 판정**이다(얕아도 후보 우주 밖이면 접지 않는다).
  **[E7]** 고아 구조 정의·«한 간선 다수 후보 → 전순서 최소» 는 v2.19 실행기가 이미 그 거동이었다 — 에라타가
  그 독해를 계약 문언으로 승격했으므로 코드 델타 0(이제 «자체 선언»이 아니라 «계약 인용»이다).


v2.15 부속(`U16-LEDGER-CHECK.md` §1 · sha256 a0201149…) 에서 파생하며 델타는 **심판 F4·F5 처분 두 가지**뿐이다:
  [F5] `c_APP(a)` 를 «구조 집합»으로 파생한다 — v2.15 부속의 «복수면 사전순 최소»(계약 밖 자체 보충)를 폐기하고
       `U-16-c` 카디널리티 처분을 그대로 소비: |c_APP|=0 → PROVENANCE_UNVERIFIABLE · |c_APP|>1 → APPROVAL_MALFORMED ·
       |c_APP|=1 → 그 «유일 원소»를 세 소비처(U-16-c 조상성 · g5 · g6)가 쓴다.
  [F4] 상태 우선순위를 «실행기 자체 선언»에서 **계약 `U-16-d` 전순서 12단**으로 교체하고, 평가 절차를
       **① 선-검사(1~4) → ② g-단락(5~11)** 으로 둔다(계약 U-16-d 정정 블록의 문자 구현).
       `edge_seq` 는 «표시용 파생»으로만 방출하고 판정 입력에 쓰지 않는다(U-16-b #2 마감 스키마).

S-23: 실행한 규칙 목록을 방출하고, 계약 소비 규칙 집합과 차집합이 비지 않으면 green(NO_ROWS_CLEAR) 대신
      PARTIAL_EXECUTION 을 방출한다.

픽스처 형식: register.csv = 'id,closable,owner_track' (헤더 있음) ·
             LEDGER.md 행 = 'row_id | transition | row_content_digest | approved_at_head | reviewer_ref | rationale_ref'
row_content_digest = U-16-f: 레지스터 행 전 열을 LC_ALL=C 열이름 정렬 '<열>=<값>' NUL 결합 sha256.

방출: closable_no_provenance_state=<값> · rules_executed=<목록> · rc 0 = NO_ROWS_CLEAR 만.
"""
import hashlib, subprocess, sys

# ── 계약 U-16-d 전순서 (유일 소스 — 실행기가 순서를 «선언»하지 않는다)
TOTAL_ORDER = ["CONSUMER_ABSENT", "PROVENANCE_UNVERIFIABLE", "APPROVAL_MALFORMED", "APPROVAL_MISSING",
               "APPROVAL_SAME_COMMIT", "APPROVAL_AFTER", "APPROVAL_CONTENT_DRIFT", "APPROVAL_HEAD_INVALID",
               "APPROVAL_ROW_MUTATED", "APPROVAL_UNBOUND", "APPROVAL_ORDER_INVALID", "NO_ROWS_CLEAR"]
TO = {s: i + 1 for i, s in enumerate(TOTAL_ORDER)}

# ── [v2.19 U-16-d 정정] ① 선-검사(1~4) 를 g-규칙 «앞»에 둔다.  대조군(«g1·g4 먼저» 문자 구현)은 이 한 줄만 다르다.
EVAL_ORDER = "precheck-first"          # 대조군 파일: "g1-first"  (계약 U-16-d ① 선-검사 → ② g-단락 · [E6] 국소)

RULES_CONTRACT = ["U-16-a(EDGES)", "U-16-a2(∀edge∃row)", "U-16-b(edge_seq 표시용 파생·판정 미소비)",
                  "U-16-c(c_APP 구조 집합·카디널리티·진 조상)", "g1", "g2", "g3", "g4", "g5",
                  "g6(C_R blob·∃witness)", "h", "MALFORMED(orphan/double-cover)",
                  "U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)"]
REG, LED = "register.csv", "LEDGER.md"
R = None


# [E8 ②] 무력화 — 모든 git 호출이 replace 뷰를 따르지 않는다 (grafts 는 이 플래그로 꺼지지 않는다: ① 관측이 담당)
GITBASE = ["git", "--no-replace-objects", "-C"]


def g(*a):
    return subprocess.run([*GITBASE, R, *a], capture_output=True, text=True).stdout.strip()


def ok(*a):
    return subprocess.run([*GITBASE, R, *a], capture_output=True).returncode == 0


def have(commit):
    """커밋 «객체»가 실재하는가 (얕은 클론 경계 판별 — 경로 부재와 구별한다)."""
    return ok("cat-file", "-e", commit + "^{commit}")


def shallow_boundary():
    """얕은 클론 «경계» 커밋 집합(.git/shallow).  이들의 부모 집합은 «부재»가 아니라 «미상»이다 —
    git 은 경계 커밋을 부모 없는 커밋처럼 보고하므로(`%P` 공백), 구조 정의의 ∀-부모 항이
    «공허참»이 되어 임의 커밋이 도입 지점으로 확정된다(fail-open).  그래서 경계를 분리 관측한다."""
    import os
    d = g("rev-parse", "--git-dir")
    p = d if os.path.isabs(d) else os.path.join(R, d)
    try:
        return set(open(os.path.join(p, "shallow")).read().split())
    except Exception:
        return set()


def show(c, p):
    r = subprocess.run([*GITBASE, R, "show", f"{c}:{p}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def blob(c, p):
    return g("rev-parse", "--quiet", "--verify", f"{c}:{p}") or "ABSENT"


def parents(c):
    return g("log", "--format=%P", "-1", c).split()


def strict_anc(a, b):
    return a != b and ok("merge-base", "--is-ancestor", a, b)


def reg_rows(c):
    t = show(c, REG)
    out = {}
    if t is None:
        return out
    lines = [l for l in t.splitlines() if l.strip()]
    if not lines:
        return out
    hdr = lines[0].split(",")
    for l in lines[1:]:
        f = l.split(",")
        out[f[0]] = dict(zip(hdr, f))
    return out


def canon_digest(row):
    return hashlib.sha256(b"\0".join(f"{k}={row[k]}".encode() for k in sorted(row))).hexdigest()


def led_raw(c):
    """커밋 c 시점 원장 blob 의 «정규형» 행 집합 (U-16-c rows(y:LEDGER)) — 경로 부재 = 공집합([H4] 동형)."""
    t = show(c, LED)
    if t is None:
        return set()
    return set(l.strip() for l in t.splitlines() if l.strip() and not l.startswith("#"))


def led_rows(c):
    t = show(c, LED)
    out = []
    if t is None:
        return out
    for l in t.splitlines():
        if not l.strip() or l.startswith("#"):
            continue
        f = [x.strip() for x in l.split("|")]
        if len(f) >= 6:
            out.append(dict(row_id=f[0], transition=f[1], digest=f[2], aah=f[3],
                            reviewer_ref=f[4], rationale_ref=f[5], raw=l.strip()))
    return out


def c_app_set(raw):
    """U-16-c 구조 집합:  c_APP(a) = { x ⊑ HEAD : a ∈ rows(x:LEDGER) ∧ ∀p∈parents(x): a ∉ rows(p:LEDGER) }
    부모 «커밋 객체»가 없으면(얕은 클론 경계) 둘째 항을 평가할 수 없으므로 그 x 를 도입 지점으로 «확정하지 않는다»
    — 부재를 «참»으로 접으면 얕은 클론이 임의 커밋을 도입 지점으로 만들어낸다(fail-open)."""
    cands, boundary = [], []
    for x in g("rev-list", "HEAD").splitlines():
        if raw not in led_raw(x):
            continue
        if is_boundary(x):                # [SHALLOW/E5] 부모 집합 «미상» ⇒ 도입 지점으로 확정하지 않는다
            boundary.append(x)
            continue
        if all(raw not in led_raw(p) for p in parents(x)):
            cands.append(x)
    return cands, boundary


def replace_refs():
    """[E8 ①] `git replace -l` — 부모 «재작성» 관측 (grafts 는 여기에 «나타나지 않는다» — 실측)."""
    return [x for x in g("replace", "-l").split() if x]


def grafts_present():
    """[E8 ①] `.git/info/grafts` 실재 여부 (deprecated 이나 동작하며 `--no-replace-objects` 로 꺼지지 않는다 — 실측)."""
    import os
    d = g("rev-parse", "--git-dir")
    base = d if os.path.isabs(d) else os.path.join(R, d)
    return os.path.exists(os.path.join(base, "info", "grafts"))


def is_boundary(x):
    """[PARENTS-UNTRUSTED (1)] 얕은 클론 «경계» — 그 커밋의 부모 집합이 «미상» (진짜 루트와 구별한다).
    (2) «재작성» 축은 per-commit 판별 수단이 없어 main() 의 «전역 관측»이 담당한다."""
    if x in shallow_boundary():
        return True
    return any(not have(p) for p in parents(x))


def c_r_set(c, ref, aah):
    """g6 구조 정의:  C_R(c) = { x ⊑ c : blob(x:ref) == blob(aah:ref) ∧ ∀p∈parents(x): blob(p:ref) ≠ 그 blob }
    부모 경로 «부재»는 ≠ 로 읽는다([H4]).  **[SHALLOW/E5] 부모 «커밋 객체» 미상(얕은 경계)은 다르다** —
    ∀-부모 항을 평가할 수 없으므로 그 x 를 도입 지점으로 확정하지 않는다(반환 2번째 값에 경계를 모은다)."""
    tgt = blob(aah, ref)
    if tgt == "ABSENT":
        return [], []
    cands, bnd = [], []
    for x in g("rev-list", c).splitlines():
        if blob(x, ref) != tgt:
            continue
        if is_boundary(x):
            bnd.append(x)
            continue
        if all(blob(p, ref) != tgt for p in parents(x)):
            cands.append(x)
    return cands, bnd


def emit(state, reason, executed, extra=()):
    for line in extra:
        print(line)
    print("rules_executed=" + ";".join(executed))
    missing = [r for r in RULES_CONTRACT if r not in executed]
    print("rules_missing=" + (";".join(missing) if missing else "∅"))
    if missing and state == "NO_ROWS_CLEAR":
        print("closable_no_provenance_state=PARTIAL_EXECUTION")
        print(f"reason=S-23: 미실행 규칙 {missing} — green 방출 금지")
        sys.exit(1)
    print(f"closable_no_provenance_state={state}")
    print(f"reason={reason}")
    sys.exit(0 if state == "NO_ROWS_CLEAR" else 1)


def main():
    global R
    R = sys.argv[1]
    executed = []
    contributions = []          # (scope, state, why)

    def add(scope, state, why):
        contributions.append((scope, state, why))
        print(f"  · {scope}: {state}({TO[state]}) — {why}")

    if not ok("rev-parse", "--is-inside-work-tree"):
        emit("PROVENANCE_UNVERIFIABLE", "git 작업트리 아님", executed)
    HEAD = g("rev-parse", "HEAD")
    SHALLOW = (g("rev-parse", "--is-shallow-repository") == "true")
    REPL, GRAFTS = replace_refs(), grafts_present()
    print(f"[PARENTS-UNTRUSTED] 관측: git replace -l={[x[:7] for x in REPL]} · .git/info/grafts={'present' if GRAFTS else 'ABSENT'}"
          f" · is_shallow={SHALLOW} · 무력화 = git --no-replace-objects (전 호출)")
    print(f"HEAD={HEAD[:7]} is_shallow={SHALLOW} .git/shallow={[x[:7] for x in sorted(shallow_boundary())]} EVAL_ORDER={EVAL_ORDER}"
          f"  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)")

    # ── 소비자 부재 (전순서 1)
    consumer_absent = (show(HEAD, REG) is None) or (show(HEAD, LED) is None)

    cur = reg_rows(HEAD)
    no_rows = [rid for rid, r in cur.items() if r.get("closable") == "NO"]

    # ── U-16-a: EDGES(r)  (→NO 간선 전부 · 루트/부모 부재는 ABSENT->NO)
    executed.append("U-16-a(EDGES)")
    edges = {}
    for rid in no_rows:
        E = []
        for c in g("rev-list", "HEAD").splitlines():
            if reg_rows(c).get(rid, {}).get("closable") != "NO":
                continue
            ps = parents(c) or [None]
            for p in ps:
                pv = "ABSENT" if p is None or rid not in reg_rows(p) else reg_rows(p)[rid]["closable"]
                if pv != "NO":
                    E.append((p, c, "ABSENT->NO" if pv == "ABSENT" else "YES->NO"))
        E.sort(key=lambda e: (g("log", "--format=%ad", "--date=iso-strict", "-1", e[1]), e[1]))
        edges[rid] = E
    # ── U-16-b: edge_seq 는 «표시용 파생»만 — 판정 입력 아님
    executed.append("U-16-b(edge_seq 표시용 파생·판정 미소비)")
    print(f"NO_rows={no_rows}")
    for rid, E in edges.items():
        print(f"EDGES({rid})={[((p or 'ROOT')[:7], c[:7], t) for p, c, t in E]}  "
              f"(edge_seq 표시용 파생={list(range(1, len(E) + 1))} · 판정 미소비)")

    L = led_rows(HEAD)
    executed.append("U-16-c(c_APP 구조 집합·카디널리티·진 조상)")
    for a in L:
        a["capp"], a["capp_boundary"] = c_app_set(a["raw"])
    print("ledger_rows=" + str([(a["row_id"], a["transition"],
                                 "|c_APP|=%d%s" % (len(a["capp"]),
                                                   "" if not a["capp_boundary"] else "(+경계 %d)" % len(a["capp_boundary"])),
                                 [x[:7] for x in a["capp"]]) for a in L]))

    executed += ["g1", "g2", "g3", "g4", "g5", "h", "g6(C_R blob·∃witness)",
                 "U-16-a2(∀edge∃row)", "MALFORMED(orphan/double-cover)",
                 "U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)"]

    # ── 규칙 사실 수집 (short-circuit 없이 전부 측정한 뒤 순서를 적용한다)
    def g4_bad(a):
        return show(HEAD, a["rationale_ref"]) is None

    def g2_bad(a):
        return a["row_id"] not in cur or canon_digest(cur[a["row_id"]]) != a["digest"]

    def g3_bad(a, c):
        return (not have(a["aah"])) or (not ok("merge-base", "--is-ancestor", a["aah"], c)) \
            or show(a["aah"], a["reviewer_ref"]) is None

    def g5_bad(a, capp):
        return a["raw"] not in led_raw(capp)

    def h_bad(a):
        t = show(a["aah"], a["reviewer_ref"])
        return t is None or a["digest"] not in t

    print("\n[사실 수집] 규칙별 측정값 (순서 적용 «전»)")
    for a in L:
        a["_g4"] = g4_bad(a)
        a["_g2"] = g2_bad(a)
        a["_matching_edges"] = [(rid, e) for rid, E in edges.items() for e in E
                                if rid == a["row_id"] and e[2] == a["transition"]]
        a["_rowid_edges"] = [(rid, e) for rid, E in edges.items() for e in E if rid == a["row_id"]]
        print(f"  row {a['row_id']}/{a['transition']} raw#{L.index(a)}: |c_APP|={len(a['capp'])}"
              f"{'' if not a['capp_boundary'] else ' 경계커밋=' + str([x[:7] for x in a['capp_boundary']])}"
              f" g4_bad={a['_g4']} g2_bad={a['_g2']} 대응간선={len(a['_matching_edges'])} row_id간선={len(a['_rowid_edges'])}")

    print("\n[상태 귀속] 계약 U-16-d 순서 적용")
    if consumer_absent:
        add("global", "CONSUMER_ABSENT", "레지스터·원장 부재")
    if REPL:
        add("global", "PROVENANCE_UNVERIFIABLE",
            "[PARENTS-UNTRUSTED] git replace -l 비공집합(%s) — 부모 집합 재작성 = 신뢰 불가" % [x[:7] for x in REPL])
    if GRAFTS:
        add("global", "PROVENANCE_UNVERIFIABLE",
            "[PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)")
    # 얕은 클론은 «전역 단축»으로 처리하지 않는다 — 경계 커밋을 도입 지점으로 «확정하지 않음»으로써
    # `|c_APP|=0` 이라는 구조 사실로 드러나고, 그 값이 선-검사 2 에서 소비된다(계약 U-16-d ①).
    # 그래야 «순서» 대조군(g1-first)이 전역 단축에 가려지지 않고 순서만으로 갈린다.

    # ── 행 단위 구조 상태
    def row_state(a):
        pre = []
        if len(a["capp"]) == 0:
            pre.append(("PROVENANCE_UNVERIFIABLE", "|c_APP|=0 (도입 지점 파생 불가)"))
        if len(a["capp"]) > 1:
            pre.append(("APPROVAL_MALFORMED", "|c_APP|=%d>1 (동일 승인 행 병렬 독립 도입) %s"
                        % (len(a["capp"]), [x[:7] for x in a["capp"]])))
        g14 = []
        if a["_g4"]:
            g14.append(("APPROVAL_MALFORMED", "g4 rationale_ref 미해석"))
        if not a["_matching_edges"]:
            g14.append(("APPROVAL_MALFORMED",
                        "고아 — 대응 간선 0 (row_id 간선 %d · g1 transition 전건 불일치)" % len(a["_rowid_edges"])))
        seq = (pre + g14) if EVAL_ORDER == "precheck-first" else (g14 + pre)
        return seq[0] if seq else None

    for a in L:
        st = row_state(a)
        if st:
            add(f"row[{a['row_id']}/{a['transition']}]", st[0], st[1])

    # ── 간선 단위
    def cand_state(a, p, c, kind):
        """한 후보 행 a 가 간선 (p→c) 에 대해 도달하는 상태 (없으면 None = 덮음)."""
        capp1 = a["capp"][0] if len(a["capp"]) == 1 else None
        CR, CRB = (c_r_set(c, a["reviewer_ref"], a["aah"]) if capp1 else ([], []))
        pre = []
        if len(a["capp"]) == 0:
            pre.append(("PROVENANCE_UNVERIFIABLE", "|c_APP|=0"))
        elif capp1 and not CR:
            pre.append(("PROVENANCE_UNVERIFIABLE",
                        "g6 C_R=∅" + (" [SHALLOW] 경계 커밋 %s 로 확정 불가" % [x[:7] for x in CRB] if CRB else "")))
        if len(a["capp"]) > 1:
            pre.append(("APPROVAL_MALFORMED", "|c_APP|>1"))
        if a["_g4"]:
            pre.append(("APPROVAL_MALFORMED", "g4"))
        g1v = [("APPROVAL_MALFORMED", f"g1 {a['transition']}≠{kind}")] if a["transition"] != kind else []
        head = (pre + g1v) if EVAL_ORDER == "precheck-first" else (g1v + pre)
        if head:
            return head[0]
        if capp1 is None:
            return ("PROVENANCE_UNVERIFIABLE", "|c_APP|≠1 — g-단락 진입 불가")
        # ② g-단락 (5~11) — |c_APP|=1 의 «유일 원소»만 쓴다
        if capp1 == c:
            return ("APPROVAL_SAME_COMMIT", f"U-16-c c_APP={capp1[:7]} == 간선 커밋")
        if not strict_anc(capp1, c):
            return ("APPROVAL_AFTER", f"U-16-c c_APP={capp1[:7]} 가 {c[:7]} 의 진 조상 아님")
        if a["_g2"]:
            return ("APPROVAL_CONTENT_DRIFT", "g2 재계산 digest ≠ 원장 보유값")
        if g3_bad(a, c):
            return ("APPROVAL_HEAD_INVALID", "g3 approved_at_head 비조상·그 시점 blob 소비 불가")
        if g5_bad(a, capp1):
            return ("APPROVAL_ROW_MUTATED", "g5 c_APP 시점 행 ≠ 현행 행")
        if h_bad(a):
            return ("APPROVAL_UNBOUND", "h digest ∉ blob(approved_at_head:reviewer_ref)")
        if not any(strict_anc(x, capp1) for x in CR):
            return ("APPROVAL_ORDER_INVALID",
                    "g6 C_R={%s} 에 c_APP 진 조상 증인 없음" % ",".join(x[:7] for x in CR))
        return None

    for rid, E in edges.items():
        for i, (p, c, kind) in enumerate(E, 1):
            cands = [a for a in L if a["row_id"] == rid]
            corr = [a for a in cands if a["transition"] == kind] if EVAL_ORDER == "precheck-first" else cands
            covers, fails = [], []
            for a in corr:
                st = cand_state(a, p, c, kind)
                (covers if st is None else fails).append((a, st))
            tag = f"edge#{i}[{rid} {(p or 'ROOT')[:7]}->{c[:7]} {kind}]"
            crs = {tuple(c_r_set(c, a["reviewer_ref"], a["aah"])[0]) for a in corr if len(a["capp"]) == 1}
            crtxt = " C_R=" + "|".join("{" + ",".join(x[:7] for x in cr) + "}" for cr in crs) if crs else ""
            if len(covers) == 1:
                print(f"  · {tag}: COVERED by c_APP={covers[0][0]['capp'][0][:7]}{crtxt}")
            elif len(covers) > 1:
                add(tag, "APPROVAL_MALFORMED",
                    "이중 덮음 %s" % [x[0]["capp"][0][:7] for x in covers])
            elif not fails:
                add(tag, "APPROVAL_MISSING", f"덮는 행 부재 (후보 {len(cands)} · 대응 {len(corr)}){crtxt}")
            else:
                st = min((f[1] for f in fails), key=lambda s: TO[s[0]])
                add(tag, st[0], f"{st[1]} (후보 {len(cands)} · 대응 {len(corr)}){crtxt}")

    if not no_rows:
        emit("NO_ROWS_CLEAR", "closable=NO 행 없음(판정 우주 ∅ — 공허 통과가 아니라 대상 없음)", executed)
    if contributions:
        best = min(contributions, key=lambda t: TO[t[1]])
        allst = sorted({c[1] for c in contributions}, key=lambda s: TO[s])
        emit(best[1], f"전순서 최소 = {best[1]}({TO[best[1]]}) @ {best[0]} — {best[2]} · 발화 전체={allst}", executed)
    emit("NO_ROWS_CLEAR", "모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0", executed)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print("rules_executed=\nrules_missing=(예외)\nclosable_no_provenance_state=PROVENANCE_UNVERIFIABLE")
        print(f"reason=판정 미산출: {e!r}")
        sys.exit(1)
```
</details>

---

## 3. 드라이버 원문

### 3-1. `t84v219e2.sh` (U-17 축 · sha256 `2d4907a455b5154b54fcf0dda8bf6da01903bbf1a6ffd0cf759d250897bfddfc`)

```bash
#!/usr/bin/env bash
# t84v219e2.sh — v2.19 에라타 2차(ad5be1a3) «영향 변이» 재실행 드라이버 (U-17 축):
#   [E8] [PARENTS-UNTRUSTED] replace/graft·grafts — 관측 ①·무력화 ②·정상 회귀 · [E9] P_first/P_last ∀-부모 구조 집합 · [E9] 상보성 4종.
# GET-only(gh api 조회만) · 서버 쓰기·설정 변경 0 · 픽스처는 scratchpad 독립 git repo(본 저장소 무접촉·worktree 미사용).
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u17-verify-v219e2.sh"; CTRL="$SP/u17-verify-v219e2-CTRL-noobserve.sh"; EXPREV="$SP/u17-verify-v219e.sh"
FX="$SP/fx84f"; SEAM="$SP/seam219e2"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md; WF=.github/workflows/tos-gate.yml
OR=kakao-harris-lee/kis_unified_sts; PINURL=https://github.com/kakao-harris-lee/kis_unified_sts.git
REPO=/Users/harris/Development/private/kis_unified_sts
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
TLAND=2026-08-10T00:00:00Z
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; git -C "$1" remote add origin "${2:-$PINURL}"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; git -C "$1" rev-parse HEAD; }
artfile(){ mkdir -p "$1/$(dirname $PC)"; printf 'owner_repo: %s\ntarget_branch: main\ntos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED%s\n' "$OR" "${2:-}" > "$1/$PC"; }
art(){ artfile "$1" "${2:-}"; git -C "$1" add -A; git -C "$1" commit -q -m "P: artifact${2:+ (variant$2)}"; git -C "$1" rev-parse HEAD; }
wfcontent(){ printf 'name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - name: verify harness identity\n        run: shasum -a 256 tools/tos_entry_harness.sh | grep %s\n      - name: run entry harness\n        run: bash tools/tos_entry_harness.sh\n' "$LIT2"; }
wf(){ mkdir -p "$1/.github/workflows"; wfcontent > "$1/$WF"; git -C "$1" add -A; git -C "$1" commit -q -m "W: workflow"; git -C "$1" rev-parse HEAD; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact\n' > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "d: introduce config/tos_completion.yaml"; git -C "$1" rev-parse HEAD; }
run(){ git -C "$1" log --oneline --graph --all | sed 's/^/  /'
  echo "\$ ${4:-}bash $(basename "${3:-$EX}") <fixture>"
  env ${4:-} U17_RESPONDER="${2:-gh}" U17_CAPTURE_DIR="$(mktemp -d)" bash "${3:-$EX}" "$1" 2>&1 | grep -vE '^U17-(A00|A1|A2|A3|A4|B1|B2|B3|B4|B5) |^  \| '; echo "u17_rc=${PIPESTATUS[0]}"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; printf '%s\n' "$4" > "$1/$(k "$2").body"; }
RULES_APPLIED(){ printf '[{"type":"required_status_checks","ruleset_id":42,"parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]'; }
seam_ruleset(){ rm -rf "$1"; mkdir -p "$1"
  inject "$1" "apps/github-actions" 200 '{"id":15368,"slug":"github-actions"}'
  inject "$1" "repos/$OR" 200 '{"full_name":"kakao-harris-lee/kis_unified_sts","default_branch":"main"}'
  inject "$1" "repos/$OR/branches/main/protection" 404 '{"message":"Branch not protected","status":"404"}'
  inject "$1" "repos/$OR/rules/branches/main" 200 "$(RULES_APPLIED)"
  inject "$1" "repos/$OR/rulesets" 200 '[{"id":42,"name":"protect_main","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]'
  inject "$1" "repos/$OR/rulesets/42" 200 '{"id":42,"enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}'; }
contents_json(){ python3 - "$1" "$2" <<'PY'
import json,sys,base64
t=open(sys.argv[1],'rb').read()
print(json.dumps({"name":"tos-gate.yml","path":sys.argv[2],"sha":"0"*40,"size":len(t),"type":"file","encoding":"base64","content":base64.b64encode(t).decode()+"\n"}))
PY
}
rev_seam(){ local dir="$1" d="$2" h="$3"
  inject "$dir" "repos/$OR/commits/$d/pulls" 200 "[{\"number\":9999,\"merged_at\":\"$TLAND\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$h\"}}]"
  inject "$dir" "repos/$OR/commits/$h/check-runs" 200 "{\"check_runs\":[{\"name\":\"tos-gate\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$h\",\"check_suite\":{\"id\":777001}}]}"
  inject "$dir" "repos/$OR/check-suites/777001" 200 "{\"id\":777001,\"head_sha\":\"$h\"}"
  inject "$dir" "repos/$OR/actions/runs?check_suite_id=777001" 200 "{\"workflow_runs\":[{\"id\":1,\"path\":\"$WF\",\"head_sha\":\"$h\",\"check_suite_id\":777001}]}"
  wfcontent > "$dir/wf.txt"; inject "$dir" "repos/$OR/contents/$WF?ref=$h" 200 "$(contents_json "$dir/wf.txt" "$WF")"; }
pu(){ printf '  판별 실측: is_shallow=%s · .git/shallow=%s · git replace -l=[%s] · .git/info/grafts=%s\n' \
  "$(git -C "$1" rev-parse --is-shallow-repository)" "$( [ -f "$1/.git/shallow" ] && echo present || echo ABSENT )" \
  "$(git -C "$1" replace -l | tr '\n' ' ')" "$( [ -f "$1/.git/info/grafts" ] && echo present || echo ABSENT )"
  printf '  %%P(d)             = %s\n' "$(git -C "$1" log --format=%P -1 "$2")"
  printf '  %%P(d) 무력화 하    = %s   (GIT_NO_REPLACE_OBJECTS=1)\n' "$(GIT_NO_REPLACE_OBJECTS=1 git -C "$1" log --format=%P -1 "$2")"; }

rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"; SM="$SEAM/rs"
printf 't84v219e2_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'sha256(u17-verify-v219e2.sh)=%s   (재실행 실행기 — 에라타 2차 델타 E8·E9)\n' "$(shasum -a 256 "$EX" | cut -d" " -f1)"
printf 'sha256(u17-verify-v219e2-CTRL-noobserve.sh)=%s  (E8 대조군 — ① 관측만 제거 · ② 무력화 유지)\n' "$(shasum -a 256 "$CTRL" | cut -d" " -f1)"
printf 'sha256(u17-verify-v219e.sh)=%s   (직전 실행기 — 197f4fe4 증거의 것 · ①② 둘 다 없음 · P 는 ∨)\n' "$(shasum -a 256 "$EXPREV" | cut -d" " -f1)"
echo "U-17-c 전순서: 1 UNVERIFIABLE · 2 ABSENT · 3 UNSIGNED · 4 TARGET_MISMATCH · 5 INSUFFICIENT · 6 LATE · 7 ARTIFACT_MUTATED · 8 UNVERIFIED_REVISION · 9 CONTINUITY_UNVERIFIABLE · 10 ACTIVE"

########################################################################
sec "[E8]-1 «git replace --graft« 픽스처 — 직전 addendum §4-1 [E5]-c 구성 재현 (진실 = LATE)"
R="$FX/graft"; SEED=$(mk "$R")
git -C "$R" checkout -q -b sideA "$SEED"; PA=$(art "$R")
git -C "$R" checkout -q main; git -C "$R" reset -q --hard "$SEED"; WG=$(wf "$R")
artfile "$R"; mkdir -p "$R/config"; printf '# D0-A first artifact\n' > "$R/config/tos_completion.yaml"
git -C "$R" add -A; git -C "$R" commit -q -m "d: config + artifact in one commit (artifact blob == P)"; DG=$(git -C "$R" rev-parse HEAD)
echo "SEED=$SEED P(sideA)=$PA W=$WG d=HEAD=$DG · 아티팩트 blob 동일? P=$(git -C "$R" rev-parse "$PA:$PC") d=$(git -C "$R" rev-parse "$DG:$PC")"
seam_ruleset "$SM"; rev_seam "$SM" "$DG" "$WG"
echo "-- graft «전» (진실) · v2.19-2 실행기 --"; pu "$R" "$DG"; run "$R" "file:$SM"
echo
echo "\$ git -C <fixture> replace --graft $DG $PA"; git -C "$R" replace --graft "$DG" "$PA" 2>&1 | sed 's/^/  /'
pu "$R" "$DG"
sec "[E8]-1a 대조 — **직전 실행기**(①② 둘 다 없음) → fail-open 재현"
run "$R" "file:$SM" "$EXPREV"
sec "[E8]-1b **② 무력화만**(CTRL-noobserve) → replace 뷰를 따르지 않아 «진짜 부모» → LATE(6) 유지"
run "$R" "file:$SM" "$CTRL"
sec "[E8]-1c **①+② 둘 다**(v2.19-2 판정 실행기) → 관측이 먼저 잡는다 → PREVENTION_UNVERIFIABLE(1)"
run "$R" "file:$SM"

########################################################################
sec "[E8]-2 «.git/info/grafts« 픽스처 — ② 무력화로는 «꺼지지 않는다» (실측) → ① 관측이 담당"
R2="$FX/grafts"; rm -rf "$R2"; cp -R "$R" "$R2"; git -C "$R2" replace -d "$DG" >/dev/null 2>&1
mkdir -p "$R2/.git/info"; printf '%s %s\n' "$DG" "$PA" > "$R2/.git/info/grafts"
echo "\$ cat <fixture>/.git/info/grafts"; sed 's/^/  /' "$R2/.git/info/grafts"
pu "$R2" "$DG"
echo "  ⇒ «git replace -l« 은 **공집합**인데 »%P« 는 재작성돼 있고, »GIT_NO_REPLACE_OBJECTS=1« 로도 **꺼지지 않는다** — ② 만으로는 못 막는다"
sec "[E8]-2a **② 무력화만**(CTRL-noobserve) → grafts 는 안 꺼지므로 fail-open 잔존"
run "$R2" "file:$SM" "$CTRL"
sec "[E8]-2b **① 관측 포함**(v2.19-2) → «.git/info/grafts« 실재 → PREVENTION_UNVERIFIABLE(1)"
run "$R2" "file:$SM"

########################################################################
sec "[E8]-3 정상 저장소 회귀 — replace 0 · grafts 부재 · shallow=false ⇒ 불변(ACTIVE)"
R3="$FX/normal"; SEED=$(mk "$R3"); PN=$(art "$R3"); WN=$(wf "$R3"); DN=$(d0a "$R3")
S3="$SEAM/normal"; seam_ruleset "$S3"; rev_seam "$S3" "$DN" "$WN"; pu "$R3" "$DN"; run "$R3" "file:$S3"

########################################################################
sec "[E9]-(i) 2-부모 머지 · 머지 blob 이 «한 부모와 같음» → 머지는 도입 «아님» · P_last 불변 ⇒ ACTIVE"
R4="$FX/e9i"; SEED=$(mk "$R4"); P4=$(art "$R4"); W4=$(wf "$R4"); D4=$(d0a "$R4")
git -C "$R4" checkout -q -b sideS "$SEED"; printf 'unrelated\n' > "$R4/side.md"; git -C "$R4" add -A; git -C "$R4" commit -q -m "S: unrelated (artifact ABSENT here)"; S4=$(git -C "$R4" rev-parse HEAD)
git -C "$R4" checkout -q main; git -C "$R4" merge -q --no-ff -m "M: merge S (artifact blob unchanged == parent d)" "$S4"
echo "P=$P4 W=$W4 d=$D4 S=$S4 M=HEAD=$(git -C "$R4" rev-parse HEAD)"
S4S="$SEAM/e9i"; seam_ruleset "$S4S"; rev_seam "$S4S" "$D4" "$W4"
echo "-- ∀-부모(v2.19-2): M 의 부모 d 가 같은 blob → M ∉ P_last · P_last={P} ⊰ d ⇒ ACTIVE --"; run "$R4" "file:$S4S"
echo "-- 대조: ∨-실행기(직전 197f4fe4) — «어느 한 부모와라도 다름»(S 에 부재) → P_last=M ⋠ d ⇒ ARTIFACT_MUTATED --"; run "$R4" "file:$S4S" "$EXPREV"

sec "[E9]-(ii) 2-부모 머지 · 머지 blob 이 «둘 다와 다름» → 머지가 도입 · |P_last|=1 ⇒ ACTIVE"
R5="$FX/e9ii"; SEED=$(mk "$R5")
git -C "$R5" checkout -q -b bA "$SEED"; art "$R5" " vA" >/dev/null; A5=$(git -C "$R5" rev-parse HEAD)
git -C "$R5" checkout -q -b bB "$SEED"; art "$R5" " vB" >/dev/null; B5=$(git -C "$R5" rev-parse HEAD)
git -C "$R5" checkout -q bA; git -C "$R5" merge -q --no-ff --no-commit "$B5" >/dev/null 2>&1 || true
artfile "$R5" " vMERGED"; git -C "$R5" add -A; git -C "$R5" commit -q -m "M: merge resolves to a NEW blob (differs from both parents)"; M5=$(git -C "$R5" rev-parse HEAD)
git -C "$R5" branch -f main HEAD; git -C "$R5" checkout -q main; W5=$(wf "$R5"); D5=$(d0a "$R5")
echo "A=$A5 B=$B5 M=$M5 W=$W5 d=$D5 · blob(A)=$(git -C "$R5" rev-parse "$A5:$PC") blob(B)=$(git -C "$R5" rev-parse "$B5:$PC") blob(M)=$(git -C "$R5" rev-parse "$M5:$PC")"
S5="$SEAM/e9ii"; seam_ruleset "$S5"; rev_seam "$S5" "$D5" "$W5"; run "$R5" "file:$S5"

sec "[E9]-(iii) 형제 «독립 동일 blob» 도입 후 머지 → |P_last|=2 ⇒ ARTIFACT_MUTATED(7)"
# 두 형제 커밋은 «아티팩트 blob 은 동일»하되 «커밋 객체는 달라야» 한다 — 각자 다른 부수 파일을 함께 둔다
R6="$FX/e9iii"; SEED=$(mk "$R6")
git -C "$R6" checkout -q -b bX "$SEED"; artfile "$R6"; printf 'x\n' > "$R6/x.md"; git -C "$R6" add -A; git -C "$R6" commit -q -m "X: artifact (independent introduction, side x)"; X6=$(git -C "$R6" rev-parse HEAD)
git -C "$R6" checkout -q -b bY "$SEED"; artfile "$R6"; printf 'y\n' > "$R6/y.md"; git -C "$R6" add -A; git -C "$R6" commit -q -m "Y: artifact (independent introduction, side y — SAME blob)"; Y6=$(git -C "$R6" rev-parse HEAD)
git -C "$R6" checkout -q bX; git -C "$R6" merge -q --no-ff -m "M: merge sibling identical-blob artifact introductions" "$Y6"
M6=$(git -C "$R6" rev-parse HEAD); git -C "$R6" branch -f main HEAD; git -C "$R6" checkout -q main; W6=$(wf "$R6"); D6=$(d0a "$R6")
echo "X=$X6 Y=$Y6 M=$M6 W=$W6 d=$D6 · 아티팩트 blob: X=$(git -C "$R6" rev-parse "$X6:$PC") Y=$(git -C "$R6" rev-parse "$Y6:$PC") M=$(git -C "$R6" rev-parse "$M6:$PC")  (셋 다 동일 = 독립 동일 blob 도입)"
S6="$SEAM/e9iii"; seam_ruleset "$S6"; rev_seam "$S6" "$D6" "$W6"; run "$R6" "file:$S6"

sec "[E9]-(iv) 직전 addendum §4-1 [E5]-c 의 «2-부모 graft» 구성 — 이제 결정적 (∨ 모호성 소거 + graft 관측)"
R7="$FX/e9iv"; rm -rf "$R7"; cp -R "$FX/graft" "$R7"; git -C "$R7" replace -d "$DG" >/dev/null 2>&1
git -C "$R7" replace --graft "$DG" "$WG" "$PA" 2>&1 | sed 's/^/  /'
pu "$R7" "$DG"
echo "-- 직전 실행기(∨·①② 없음): 2-부모 graft 에서 ARTIFACT_MUTATED(7) 였다 --"; run "$R7" "file:$SM" "$EXPREV"
echo "-- ② 무력화만(CTRL): graft 무효 → 진짜 이력 → LATE(6) --"; run "$R7" "file:$SM" "$CTRL"
echo "-- ①+②(v2.19-2): 관측 → UNVERIFIABLE(1) --"; run "$R7" "file:$SM"

sec "[E9]-(v) T-84 ⑨ 사후 편집 — 여전히 ARTIFACT_MUTATED(7)"
R8="$FX/e9v"; SEED=$(mk "$R8"); P8=$(art "$R8"); W8=$(wf "$R8"); D8=$(d0a "$R8")
artfile "$R8" " EDITED-AFTER-d"; git -C "$R8" add -A; git -C "$R8" commit -q -m "P_edit: artifact edited AFTER d"
S8="$SEAM/e9v"; seam_ruleset "$S8"; rev_seam "$S8" "$D8" "$W8"; run "$R8" "file:$S8"

########################################################################
sec "[E9] 상보성 — ¬LATE 하 ACTIVE / ARTIFACT_MUTATED 상보·결정적 (합성 4종)"
echo "  ① 정상        = [E8]-3 (P → W → d)                       → ACTIVE(10)"
echo "  ② 사후 편집   = [E9]-(v) (P → W → d → P_edit)             → ARTIFACT_MUTATED(7)"
echo "  ③ 다중 도입   = [E9]-(iii) (X ∥ Y 동일 blob → M → W → d)  → ARTIFACT_MUTATED(7)"
echo "  ④ 순서 위반   = 아래 (W → d → P)                          → LATE(6)"
R9="$FX/e9late"; SEED=$(mk "$R9"); W9=$(wf "$R9"); D9=$(d0a "$R9"); P9=$(art "$R9")
S9="$SEAM/e9late"; seam_ruleset "$S9"; rev_seam "$S9" "$D9" "$W9"; run "$R9" "file:$S9"

########################################################################
sec "본 저장소 현행 상태 — live (에라타 2차 실행기 · HEAD ad5be1a3)"
echo "\$ bash u17-verify-v219e2.sh $REPO"; U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO" 2>&1 | grep -vE '^  \| '; echo "u17_rc=${PIPESTATUS[0]}"
```

### 3-2. `t82v219e2.sh` (U-16 축 · sha256 `25343e47f3d3bc5b8db3c2862a6038b0c62deb565f25409cb058334a1b63596e`)

```bash
#!/usr/bin/env bash
# t82v219e2.sh — v2.19 에라타 2차(ad5be1a3) «영향 변이» 재실행 드라이버 (U-16 축):
#   [E8] [PARENTS-UNTRUSTED] — `c_APP`·`C_R` 두 정의를 replace/graft·grafts 아래에서 실측 (관측 ①·무력화 ②·정상 회귀).
# 서버 조회 0(순수 in-repo) · 픽스처는 scratchpad 독립 git repo(본 저장소 무접촉·worktree 미사용).
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u16-full-exec-v219e2.py"; CTRL="$SP/u16-full-exec-v219e2-CTRL-noobserve.py"
EXPREV="$SP/u16-full-exec-v219e.py"; ORDCTRL="$SP/u16-order-ctrl-g1first.py"
FX="$SP/fx82f"; REF=reviews/review.md; RAT=rationale/r1.md
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
dig(){ python3 -c "import hashlib,sys; r=dict(id=sys.argv[1],closable=sys.argv[2],owner_track=sys.argv[3]); print(hashlib.sha256(b'\0'.join(f'{k}={r[k]}'.encode() for k in sorted(r))).hexdigest())" "$@"; }
DNO=$(dig r1 NO tos)
reg(){ printf 'id,closable,owner_track\n'; for kv in "$@"; do printf '%s\n' "$kv"; done; }
c(){ git -C "$1" add -A && git -C "$1" commit -q --allow-empty -m "$2" && git -C "$1" rev-parse HEAD; }
row(){ printf 'r1 | %s | %s | %s | %s | %s\n' "$1" "$DNO" "$2" "$REF" "${3:-$RAT}"; }
setNO(){ reg 'other,YES,x' 'r1,NO,tos' > "$1/register.csv"; }
setYES(){ reg 'other,YES,x' 'r1,YES,tos' > "$1/register.csv"; }
run(){ git -C "$1" log --graph --oneline --all | sed 's/^/  /'; echo "\$ python3 $(basename "${2:-$EX}") <fixture>"; python3 "${2:-$EX}" "$1"; echo "u16_rc=$?"; }
mergeled(){ git -C "$1" merge -q --no-ff -m "$3" "$2" 2>/dev/null || { { echo "## ledger"; git -C "$1" show HEAD:LEDGER.md | tail -n +2; git -C "$1" show "$2":LEDGER.md | tail -n +2; } | awk '!seen[$0]++' > "$1/LEDGER.md"; git -C "$1" add -A; git -C "$1" commit -q -m "$3"; }; }
pu(){ printf '  판별 실측: is_shallow=%s · git replace -l=[%s] · .git/info/grafts=%s\n' \
  "$(git -C "$1" rev-parse --is-shallow-repository)" "$(git -C "$1" replace -l | tr '\n' ' ')" "$( [ -f "$1/.git/info/grafts" ] && echo present || echo ABSENT )"
  printf '  %%P(%s) replace-따름 = %s\n' "${2:0:7}" "$(git -C "$1" log --format=%P -1 "$2")"
  printf '  %%P(%s) 무력화 하    = %s\n' "${2:0:7}" "$(git -C "$1" --no-replace-objects log --format=%P -1 "$2")"; }

rm -rf "$FX"; mkdir -p "$FX"
printf 't82v219e2_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'sha256(u16-full-exec-v219e2.py)=%s   (재실행 실행기 — 에라타 2차 델타 E8)\n' "$(shasum -a 256 "$EX" | cut -d" " -f1)"
printf 'sha256(u16-full-exec-v219e2-CTRL-noobserve.py)=%s  (E8 대조군 — ① 관측만 제거 · ② 무력화 유지)\n' "$(shasum -a 256 "$CTRL" | cut -d" " -f1)"
printf 'sha256(u16-full-exec-v219e.py)=%s   (직전 실행기 — 197f4fe4 증거의 것 · ①② 둘 다 없음)\n' "$(shasum -a 256 "$EXPREV" | cut -d" " -f1)"
printf 'sha256(u16-order-ctrl-g1first.py)=%s (⑳ⓑ 순서 대조군 — 불변 재사용)\n' "$(shasum -a 256 "$ORDCTRL" | cut -d" " -f1)"
echo "D_NO = $DNO"
echo "계약 U-16-d 전순서: 1 CONSUMER_ABSENT · 2 PROVENANCE_UNVERIFIABLE · 3 APPROVAL_MALFORMED · 4 APPROVAL_MISSING · 5 SAME_COMMIT · 6 AFTER · 7 CONTENT_DRIFT · 8 HEAD_INVALID · 9 ROW_MUTATED · 10 UNBOUND · 11 ORDER_INVALID · 12 NO_ROWS_CLEAR"

########################################################################
# ⑳ⓐ 픽스처 — 동일 승인 행 형제 독립 도입 (진실: |c_APP|=2 → APPROVAL_MALFORMED(3))
build20a(){ local R="$1"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
  reg 'other,YES,x' 'r1,YES,tos' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"
  printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; H0=$(c "$R" "H0: base (r1=YES · reviewer digest)")
  git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$H0" >> "$R/LEDGER.md"; printf 'x\n' > "$R/x.md"; X=$(c "$R" "X: approval row A [side x]")
  setNO "$R"; CN=$(c "$R" "CN: NO transition (child of X)")
  git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$H0" >> "$R/LEDGER.md"; printf 'y\n' > "$R/y.md"; Y=$(c "$R" "Y: approval row A (byte-identical) [side y]")
  git -C "$R" checkout -q --detach "$CN"; mergeled "$R" "$Y" "M: merge sibling identical approval introduction"; git -C "$R" branch -f main HEAD
  printf '%s %s %s %s\n' "$H0" "$X" "$CN" "$Y"; }

sec "[E8]-U16-1 «c_APP» 축 — ⑳ⓐ 픽스처 (진실 = APPROVAL_MALFORMED(3) · |c_APP|=2)"
R="$FX/capp"; read -r H0 X CN Y <<< "$(build20a "$R")"; M=$(git -C "$R" rev-parse HEAD)
echo "H0=$H0 X=$X CN=$CN Y=$Y M=HEAD=$M"; pu "$R" "$M"; run "$R"

echo
echo "\$ git -C <fixture> replace --graft $M $CN      # M 의 부모에서 Y 를 «지운다» — 형제 도입을 숨긴다"
git -C "$R" replace --graft "$M" "$CN" 2>&1 | sed 's/^/  /'; pu "$R" "$M"
sec "[E8]-U16-1a 대조 — **직전 실행기**(①② 둘 다 없음) → 형제 도입이 사라져 fail-open"
run "$R" "$EXPREV"
sec "[E8]-U16-1b **② 무력화만**(CTRL-noobserve) → 진짜 부모 → |c_APP|=2 → APPROVAL_MALFORMED(3) 복원"
run "$R" "$CTRL"
sec "[E8]-U16-1c **①+② 둘 다**(v2.19-2 판정 실행기) → 관측이 먼저 → PROVENANCE_UNVERIFIABLE(2)"
run "$R"

########################################################################
sec "[E8]-U16-2 «.git/info/grafts» — ② 무력화로 «꺼지지 않는다» → ① 관측이 담당"
R2="$FX/capp-grafts"; rm -rf "$R2"; cp -R "$R" "$R2"; git -C "$R2" replace -d "$M" >/dev/null 2>&1
mkdir -p "$R2/.git/info"; printf '%s %s\n' "$M" "$CN" > "$R2/.git/info/grafts"
echo "\$ cat <fixture>/.git/info/grafts"; sed 's/^/  /' "$R2/.git/info/grafts"; pu "$R2" "$M"
sec "[E8]-U16-2a **② 무력화만**(CTRL) → grafts 는 안 꺼지므로 fail-open 잔존"
run "$R2" "$CTRL"
sec "[E8]-U16-2b **① 관측 포함**(v2.19-2) → PROVENANCE_UNVERIFIABLE(2)"
run "$R2"

########################################################################
sec "[E8]-U16-3 «C_R» 축 — ⑮(신규 아티팩트 R ∥ A) 에 graft 를 걸어 «리뷰 blob 도입 지점»을 숨긴다 (진실 = APPROVAL_ORDER_INVALID(11))"
R3="$FX/cr"; rm -rf "$R3"; git init -q -b main "$R3"; mkdir -p "$R3/reviews" "$R3/rationale"
reg 'other,YES,x' 'r1,YES,tos' > "$R3/register.csv"; echo "## ledger" > "$R3/LEDGER.md"; echo "rationale for r1 NO" > "$R3/$RAT"
H3=$(c "$R3" "H0: base (reviewer 경로 없음)")
git -C "$R3" checkout -q --detach "$H3"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R3/$REF"; printf 'r\n' > "$R3/r.md"; RR=$(c "$R3" "R: new reviewer artifact [side r]")
git -C "$R3" checkout -q --detach "$H3"; row YES-\>NO "$RR" >> "$R3/LEDGER.md"; printf 'a\n' > "$R3/a.md"; A3=$(c "$R3" "A: approval (aah=R) [side a · R 은 A 의 조상이 아니다]")
git -C "$R3" merge -q --no-ff -m "M0: merge R" "$RR"; M0=$(git -C "$R3" rev-parse HEAD); setNO "$R3"; MN=$(c "$R3" "M: NO transition"); git -C "$R3" branch -f main HEAD
echo "H0=$H3 R=$RR A=$A3 M0=$M0 M=$MN"; pu "$R3" "$M0"; run "$R3"
echo
echo "\$ git -C <fixture> replace --graft $A3 $RR      # A 의 부모를 R 로 «재작성» → R 이 A 의 진 조상이 된다(증인 위조)"
git -C "$R3" replace --graft "$A3" "$RR" 2>&1 | sed 's/^/  /'; pu "$R3" "$A3"
sec "[E8]-U16-3a 대조 — **직전 실행기**(①② 없음) → g6 증인이 «생겨» fail-open"
run "$R3" "$EXPREV"
sec "[E8]-U16-3b **② 무력화만**(CTRL) → 진짜 부모 → APPROVAL_ORDER_INVALID(11) 복원"
run "$R3" "$CTRL"
sec "[E8]-U16-3c **①+②**(v2.19-2) → PROVENANCE_UNVERIFIABLE(2)"
run "$R3"

########################################################################
sec "[E8]-U16-4 정상 회귀 — replace 0 · grafts 부재 · shallow=false ⇒ 직전 판과 «불변»"
echo "-- ⑳ⓐ 원본(graft 없음) → APPROVAL_MALFORMED(3) --"
R4="$FX/reg20a"; read -r H0b Xb CNb Yb <<< "$(build20a "$R4")"; pu "$R4" "$(git -C "$R4" rev-parse HEAD)"; run "$R4"
echo "-- ⑱ 정정 문언(같은 row_id·다른 승인 행·형제 도입→merge) → NO_ROWS_CLEAR/0 --"
R5="$FX/reg18"; rm -rf "$R5"; git init -q -b main "$R5"; mkdir -p "$R5/reviews" "$R5/rationale"
reg 'other,YES,x' > "$R5/register.csv"; echo "## ledger" > "$R5/LEDGER.md"; echo "rationale for r1 NO" > "$R5/$RAT"
echo "rationale (approver a)" > "$R5/rationale/r1-a.md"; echo "rationale (approver b)" > "$R5/rationale/r1-b.md"
printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R5/$REF"; H5=$(c "$R5" "H0: r1 absent (reviewer digest)")
git -C "$R5" checkout -q --detach "$H5"; row ABSENT-\>NO "$H5" rationale/r1-a.md >> "$R5/LEDGER.md"; A51=$(c "$R5" "A1: approval (ABSENT->NO, rationale a)")
git -C "$R5" checkout -q --detach "$H5"; row YES-\>NO "$H5" rationale/r1-b.md >> "$R5/LEDGER.md"; A52=$(c "$R5" "A2: approval (YES->NO, rationale b)")
git -C "$R5" checkout -q --detach "$A51"; mergeled "$R5" "$A52" "MA: merge sibling approval introductions"
setNO "$R5"; c "$R5" "e1: ABSENT->NO" >/dev/null; setYES "$R5"; c "$R5" "back to YES" >/dev/null; setNO "$R5"; c "$R5" "e2: YES->NO" >/dev/null
git -C "$R5" branch -f main HEAD; run "$R5"
echo "-- ⑳ⓑ 얕은 클론(국소 [E6] 유지) → PROVENANCE_UNVERIFIABLE(2) · 순서 대조군은 여전히 3 --"
SH="$FX/reg20b-shallow"; rm -rf "$SH"; git clone -q --depth 1 "file://$R4" "$SH"
echo "  is_shallow=$(git -C "$SH" rev-parse --is-shallow-repository) · .git/shallow=$(cat "$SH/.git/shallow" 2>/dev/null | tr '\n' ' ') · replace -l=[$(git -C "$SH" replace -l | tr '\n' ' ')] · grafts=$( [ -f "$SH/.git/info/grafts" ] && echo present || echo ABSENT )"
run "$SH"; run "$SH" "$ORDCTRL"
```

---

## 4. 실행 기록 (stdout 전문 · rc 포함)

### 4-1. U-17 축 — `bash t84v219e2.sh` ([E8] 1~3 · [E9] (i)~(v) · [E9] 상보성 · 본 저장소 live)

각 run 은 `U17-0 target=…` 라인이 열고 run 당 상태 라인은 `prevention_control_state=` **정확히 1개**다((4c-2) 확장). 기록은 발행 시점에 확정되고 이후 편집하지 않는다((4d)).
가독을 위해 캡처 본문(`U17-A*`/`U17-B*` 의 raw JSON 행)은 드라이버가 필터링했다 — **판정에 쓰이는 라인(`U17-PU`·`U17-SHALLOW`·`P_first`/`P_last`·`u17_live_state`·`U17-fire`·`prevention_control_state`·`reason`)은 전부 원문**이다.

```text
t84v219e2_utc=2026-08-19T02:40:57Z
sha256(u17-verify-v219e2.sh)=8516adc2684498fb08d5312acab8dc5f25345c9268f0ec84b738d805bfb85968   (재실행 실행기 — 에라타 2차 델타 E8·E9)
sha256(u17-verify-v219e2-CTRL-noobserve.sh)=380eb9b9597d3c4c939da413066ef69995e9e95b82ab7d5704058545d3d54d32  (E8 대조군 — ① 관측만 제거 · ② 무력화 유지)
sha256(u17-verify-v219e.sh)=6a80beed1d81d83898aed0c0d930be8b20e48d177d484623f6a1371043cd6b16   (직전 실행기 — 197f4fe4 증거의 것 · ①② 둘 다 없음 · P 는 ∨)
U-17-c 전순서: 1 UNVERIFIABLE · 2 ABSENT · 3 UNSIGNED · 4 TARGET_MISMATCH · 5 INSUFFICIENT · 6 LATE · 7 ARTIFACT_MUTATED · 8 UNVERIFIED_REVISION · 9 CONTINUITY_UNVERIFIABLE · 10 ACTIVE

########## [E8]-1 «git replace --graft« 픽스처 — 직전 addendum §4-1 [E5]-c 구성 재현 (진실 = LATE) ##########
SEED=4f5ae9839b5881205221412c47dcde5a8f916502 P(sideA)=001ad229920097a40c550f91c4445e6da07c79ea W=48c9600be48df860516043fc11a842460fcf1572 d=HEAD=8c07e947a0eda2f2ee77551625fc7d087693248e · 아티팩트 blob 동일? P=762145cfb2a9a719deb125bef8ecea955d7e656e d=762145cfb2a9a719deb125bef8ecea955d7e656e
-- graft «전» (진실) · v2.19-2 실행기 --
  판별 실측: is_shallow=false · .git/shallow=ABSENT · git replace -l=[] · .git/info/grafts=ABSENT
  %P(d)             = 48c9600be48df860516043fc11a842460fcf1572
  %P(d) 무력화 하    = 48c9600be48df860516043fc11a842460fcf1572   (GIT_NO_REPLACE_OBJECTS=1)
  * 8c07e94 d: config + artifact in one commit (artifact blob == P)
  * 48c9600 W: workflow
  | * 001ad22 P: artifact
  |/  
  * 4f5ae98 seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.CwdCZxAJIP
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:40:58Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[8c07e947a0eda2f2ee77551625fc7d087693248e ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[8c07e947a0eda2f2ee77551625fc7d087693248e ] |D|=1 D=[8c07e947a0eda2f2ee77551625fc7d087693248e ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 48c9600be48df860516043fc11a842460fcf1572:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=8c07e947a0eda2f2ee77551625fc7d087693248e head=48c9600be48df860516043fc11a842460fcf1572 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_LATE
reason=[E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다 [수집 1건 중 전순서 최소]
u17_rc=1

$ git -C <fixture> replace --graft 8c07e947a0eda2f2ee77551625fc7d087693248e 001ad229920097a40c550f91c4445e6da07c79ea
  판별 실측: is_shallow=false · .git/shallow=ABSENT · git replace -l=[8c07e947a0eda2f2ee77551625fc7d087693248e ] · .git/info/grafts=ABSENT
  %P(d)             = 001ad229920097a40c550f91c4445e6da07c79ea
  %P(d) 무력화 하    = 48c9600be48df860516043fc11a842460fcf1572   (GIT_NO_REPLACE_OBJECTS=1)

########## [E8]-1a 대조 — **직전 실행기**(①② 둘 다 없음) → fail-open 재현 ##########
  * 8c07e94 d: config + artifact in one commit (artifact blob == P)
  | * d31355c d: config + artifact in one commit (artifact blob == P)
  |/  
  * 001ad22 P: artifact
  * 4f5ae98 seed
$ bash u17-verify-v219e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.l7RMI9BZi0
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:00Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=001ad229920097a40c550f91c4445e6da07c79ea P_last=001ad229920097a40c550f91c4445e6da07c79ea |D|=1 D=8c07e947a0eda2f2ee77551625fc7d087693248e 
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 48c9600be48df860516043fc11a842460fcf1572:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=8c07e947a0eda2f2ee77551625fc7d087693248e head=48c9600be48df860516043fc11a842460fcf1572 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs
u17_rc=0

########## [E8]-1b **② 무력화만**(CTRL-noobserve) → replace 뷰를 따르지 않아 «진짜 부모» → LATE(6) 유지 ##########
  * 8c07e94 d: config + artifact in one commit (artifact blob == P)
  | * d31355c d: config + artifact in one commit (artifact blob == P)
  |/  
  * 001ad22 P: artifact
  * 4f5ae98 seed
$ bash u17-verify-v219e2-CTRL-noobserve.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QSa7kiDBx5
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[8c07e947a0eda2f2ee77551625fc7d087693248e ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:02Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[8c07e947a0eda2f2ee77551625fc7d087693248e ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[8c07e947a0eda2f2ee77551625fc7d087693248e ] |D|=1 D=[8c07e947a0eda2f2ee77551625fc7d087693248e ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 48c9600be48df860516043fc11a842460fcf1572:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=8c07e947a0eda2f2ee77551625fc7d087693248e head=48c9600be48df860516043fc11a842460fcf1572 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_LATE
reason=[E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다 [수집 1건 중 전순서 최소]
u17_rc=1

########## [E8]-1c **①+② 둘 다**(v2.19-2 판정 실행기) → 관측이 먼저 잡는다 → PREVENTION_UNVERIFIABLE(1) ##########
  * 8c07e94 d: config + artifact in one commit (artifact blob == P)
  | * d31355c d: config + artifact in one commit (artifact blob == P)
  |/  
  * 001ad22 P: artifact
  * 4f5ae98 seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.7ZGa1qjpm0
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[8c07e947a0eda2f2ee77551625fc7d087693248e ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 8c07e947a0eda2f2ee77551625fc7d087693248e ) — 부모 집합 재작성 = 신뢰 불가
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:04Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[8c07e947a0eda2f2ee77551625fc7d087693248e ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[8c07e947a0eda2f2ee77551625fc7d087693248e ] |D|=1 D=[8c07e947a0eda2f2ee77551625fc7d087693248e ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 48c9600be48df860516043fc11a842460fcf1572:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=8c07e947a0eda2f2ee77551625fc7d087693248e head=48c9600be48df860516043fc11a842460fcf1572 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 8c07e947a0eda2f2ee77551625fc7d087693248e ) — 부모 집합 재작성 = 신뢰 불가 [수집 2건 중 전순서 최소]
u17_rc=1

########## [E8]-2 «.git/info/grafts« 픽스처 — ② 무력화로는 «꺼지지 않는다» (실측) → ① 관측이 담당 ##########
$ cat <fixture>/.git/info/grafts
  8c07e947a0eda2f2ee77551625fc7d087693248e 001ad229920097a40c550f91c4445e6da07c79ea
  판별 실측: is_shallow=false · .git/shallow=ABSENT · git replace -l=[] · .git/info/grafts=present
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
  %P(d)             = 001ad229920097a40c550f91c4445e6da07c79ea
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
  %P(d) 무력화 하    = 001ad229920097a40c550f91c4445e6da07c79ea   (GIT_NO_REPLACE_OBJECTS=1)
  ⇒ «git replace -l« 은 **공집합**인데 »%P« 는 재작성돼 있고, »GIT_NO_REPLACE_OBJECTS=1« 로도 **꺼지지 않는다** — ② 만으로는 못 막는다

########## [E8]-2a **② 무력화만**(CTRL-noobserve) → grafts 는 안 꺼지므로 fail-open 잔존 ##########
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
  * 8c07e94 d: config + artifact in one commit (artifact blob == P)
  * 001ad22 P: artifact
  * 4f5ae98 seed
$ bash u17-verify-v219e2-CTRL-noobserve.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.n71S0iAEYE
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=yes · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:06Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
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
P_first(집합·|1|)=[001ad229920097a40c550f91c4445e6da07c79ea ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[001ad229920097a40c550f91c4445e6da07c79ea ] |D|=1 D=[8c07e947a0eda2f2ee77551625fc7d087693248e ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 48c9600be48df860516043fc11a842460fcf1572:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=8c07e947a0eda2f2ee77551625fc7d087693248e head=48c9600be48df860516043fc11a842460fcf1572 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs
u17_rc=0

########## [E8]-2b **① 관측 포함**(v2.19-2) → «.git/info/grafts« 실재 → PREVENTION_UNVERIFIABLE(1) ##########
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
  * 8c07e94 d: config + artifact in one commit (artifact blob == P)
  * 001ad22 P: artifact
  * 4f5ae98 seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.AwLbdJh254
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=yes · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:08Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
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
P_first(집합·|1|)=[001ad229920097a40c550f91c4445e6da07c79ea ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[001ad229920097a40c550f91c4445e6da07c79ea ] |D|=1 D=[8c07e947a0eda2f2ee77551625fc7d087693248e ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 48c9600be48df860516043fc11a842460fcf1572:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=8c07e947a0eda2f2ee77551625fc7d087693248e head=48c9600be48df860516043fc11a842460fcf1572 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) [수집 1건 중 전순서 최소]
u17_rc=1

########## [E8]-3 정상 저장소 회귀 — replace 0 · grafts 부재 · shallow=false ⇒ 불변(ACTIVE) ##########
  판별 실측: is_shallow=false · .git/shallow=ABSENT · git replace -l=[] · .git/info/grafts=ABSENT
  %P(d)             = 8e6073da6837419ca60ad403398ae9171572f139
  %P(d) 무력화 하    = 8e6073da6837419ca60ad403398ae9171572f139   (GIT_NO_REPLACE_OBJECTS=1)
  * 8873895 d: introduce config/tos_completion.yaml
  * 8e6073d W: workflow
  * dda0440 P: artifact
  * 148016f seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/normal capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Vapj9bbeJo
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:11Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[dda0440f38ad5452e4880739355b77c857512ad2 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[dda0440f38ad5452e4880739355b77c857512ad2 ] |D|=1 D=[88738958ffb829cc0d537eb96a55957138d5a94a ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 8e6073da6837419ca60ad403398ae9171572f139:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=88738958ffb829cc0d537eb96a55957138d5a94a head=8e6073da6837419ca60ad403398ae9171572f139 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/normal
u17_rc=0

########## [E9]-(i) 2-부모 머지 · 머지 blob 이 «한 부모와 같음» → 머지는 도입 «아님» · P_last 불변 ⇒ ACTIVE ##########
P=91e6c156934eb84ae5e150faef27a33f8abffc96 W=a9ce97b9b4af5691a3a73867c706921c1da15748 d=e773d34ebfa65eafb3e37067986f0753802dde5c S=73ccd4849875835dd3993956b0ebab53d890e175 M=HEAD=933b63fe4d57ed3438d13e20c6164f1a30faceae
-- ∀-부모(v2.19-2): M 의 부모 d 가 같은 blob → M ∉ P_last · P_last={P} ⊰ d ⇒ ACTIVE --
  *   933b63f M: merge S (artifact blob unchanged == parent d)
  |\  
  | * 73ccd48 S: unrelated (artifact ABSENT here)
  * | e773d34 d: introduce config/tos_completion.yaml
  * | a9ce97b W: workflow
  * | 91e6c15 P: artifact
  |/  
  * fbef9ef seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/e9i capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YR6KfcK13k
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:14Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[91e6c156934eb84ae5e150faef27a33f8abffc96 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[91e6c156934eb84ae5e150faef27a33f8abffc96 ] |D|=1 D=[e773d34ebfa65eafb3e37067986f0753802dde5c ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show a9ce97b9b4af5691a3a73867c706921c1da15748:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=e773d34ebfa65eafb3e37067986f0753802dde5c head=a9ce97b9b4af5691a3a73867c706921c1da15748 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/e9i
u17_rc=0
-- 대조: ∨-실행기(직전 197f4fe4) — «어느 한 부모와라도 다름»(S 에 부재) → P_last=M ⋠ d ⇒ ARTIFACT_MUTATED --
  *   933b63f M: merge S (artifact blob unchanged == parent d)
  |\  
  | * 73ccd48 S: unrelated (artifact ABSENT here)
  * | e773d34 d: introduce config/tos_completion.yaml
  * | a9ce97b W: workflow
  * | 91e6c15 P: artifact
  |/  
  * fbef9ef seed
$ bash u17-verify-v219e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/e9i capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.luOlevNTo4
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:16Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=91e6c156934eb84ae5e150faef27a33f8abffc96 P_last=933b63fe4d57ed3438d13e20c6164f1a30faceae |D|=1 D=e773d34ebfa65eafb3e37067986f0753802dde5c 
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_ARTIFACT_MUTATED: ∀d P_first⊰d 이나 ∃d∈D: P_last=933b63fe4d57ed3438d13e20c6164f1a30faceae ⋠ d — 착수 «후» 아티팩트 변경
U17-B5x 보조(선택·판정 미소비): 로컬 git show a9ce97b9b4af5691a3a73867c706921c1da15748:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=e773d34ebfa65eafb3e37067986f0753802dde5c head=a9ce97b9b4af5691a3a73867c706921c1da15748 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=∀d P_first⊰d 이나 ∃d∈D: P_last=933b63fe4d57ed3438d13e20c6164f1a30faceae ⋠ d — 착수 «후» 아티팩트 변경 [수집 1건 중 전순서 최소]
u17_rc=1

########## [E9]-(ii) 2-부모 머지 · 머지 blob 이 «둘 다와 다름» → 머지가 도입 · |P_last|=1 ⇒ ACTIVE ##########
A=ae747e0a1d18b2f05e1e8742e7ac9d1488034341 B=b7ec22b6602019db5e539d7d45ef1735c5e110c8 M=4637e33224876ae35618a7161c433a6f9000b44c W=53df91f5c56846476b1d6e900fd9e958fdad29a0 d=6725ae2837b74333b7b1f1f3bd62242f55a9c394 · blob(A)=73bb7842b6c9e1fae4acc776d36d0ce67d2421c0 blob(B)=0c749d7d0db4c1ee092ac7463bea6a33215407a9 blob(M)=5432b3e09f913500f6512db4d5dc4d5b60b7ff9f
  * 6725ae2 d: introduce config/tos_completion.yaml
  * 53df91f W: workflow
  *   4637e33 M: merge resolves to a NEW blob (differs from both parents)
  |\  
  | * b7ec22b P: artifact (variant vB)
  * | ae747e0 P: artifact (variant vA)
  |/  
  * 0d59b24 seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/e9ii capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.n3w6GNVL1i
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:19Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|2|)=[ae747e0a1d18b2f05e1e8742e7ac9d1488034341 b7ec22b6602019db5e539d7d45ef1735c5e110c8 ] P_last(집합·|1|·blob=5432b3e09f913500f6512db4d5dc4d5b60b7ff9f)=[4637e33224876ae35618a7161c433a6f9000b44c ] |D|=1 D=[6725ae2837b74333b7b1f1f3bd62242f55a9c394 ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 53df91f5c56846476b1d6e900fd9e958fdad29a0:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=6725ae2837b74333b7b1f1f3bd62242f55a9c394 head=53df91f5c56846476b1d6e900fd9e958fdad29a0 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/e9ii
u17_rc=0

########## [E9]-(iii) 형제 «독립 동일 blob» 도입 후 머지 → |P_last|=2 ⇒ ARTIFACT_MUTATED(7) ##########
X=78037c6d1be8a157c7e1426eea081ad77b400677 Y=779bf4d7ffa37fc2c9c4422dfe2b89aa59f25c0b M=4f47704793c30c5d65b0a6bec43242691e32f02e W=6d8c348354952da2f3e3a2417d2c1eafefc0db77 d=f96e143da38494745665c12de8561e015d58d176 · 아티팩트 blob: X=762145cfb2a9a719deb125bef8ecea955d7e656e Y=762145cfb2a9a719deb125bef8ecea955d7e656e M=762145cfb2a9a719deb125bef8ecea955d7e656e  (셋 다 동일 = 독립 동일 blob 도입)
  * f96e143 d: introduce config/tos_completion.yaml
  * 6d8c348 W: workflow
  *   4f47704 M: merge sibling identical-blob artifact introductions
  |\  
  | * 779bf4d Y: artifact (independent introduction, side y — SAME blob)
  * | 78037c6 X: artifact (independent introduction, side x)
  |/  
  * 4aedb6f seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/e9iii capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gCZYk7TXjV
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:22Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|2|)=[78037c6d1be8a157c7e1426eea081ad77b400677 779bf4d7ffa37fc2c9c4422dfe2b89aa59f25c0b ] P_last(집합·|2|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[78037c6d1be8a157c7e1426eea081ad77b400677 779bf4d7ffa37fc2c9c4422dfe2b89aa59f25c0b ] |D|=1 D=[f96e143da38494745665c12de8561e015d58d176 ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_ARTIFACT_MUTATED: [E9] ¬LATE ∧ |P_last|=2>1 (78037c6d1be8a157c7e1426eea081ad77b400677 779bf4d7ffa37fc2c9c4422dfe2b89aa59f25c0b ) — 현행 내용의 도입 지점이 유일하지 않다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 6d8c348354952da2f3e3a2417d2c1eafefc0db77:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=f96e143da38494745665c12de8561e015d58d176 head=6d8c348354952da2f3e3a2417d2c1eafefc0db77 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=[E9] ¬LATE ∧ |P_last|=2>1 (78037c6d1be8a157c7e1426eea081ad77b400677 779bf4d7ffa37fc2c9c4422dfe2b89aa59f25c0b ) — 현행 내용의 도입 지점이 유일하지 않다 [수집 1건 중 전순서 최소]
u17_rc=1

########## [E9]-(iv) 직전 addendum §4-1 [E5]-c 의 «2-부모 graft» 구성 — 이제 결정적 (∨ 모호성 소거 + graft 관측) ##########
  판별 실측: is_shallow=false · .git/shallow=ABSENT · git replace -l=[8c07e947a0eda2f2ee77551625fc7d087693248e ] · .git/info/grafts=ABSENT
  %P(d)             = 48c9600be48df860516043fc11a842460fcf1572 001ad229920097a40c550f91c4445e6da07c79ea
  %P(d) 무력화 하    = 48c9600be48df860516043fc11a842460fcf1572   (GIT_NO_REPLACE_OBJECTS=1)
-- 직전 실행기(∨·①② 없음): 2-부모 graft 에서 ARTIFACT_MUTATED(7) 였다 --
  *   8c07e94 d: config + artifact in one commit (artifact blob == P)
  |\  
  | | * 88e0e9d d: config + artifact in one commit (artifact blob == P)
  | |/| 
  |/|/  
  | * 001ad22 P: artifact
  * | 48c9600 W: workflow
  |/  
  * 4f5ae98 seed
$ bash u17-verify-v219e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gw14cUUkMy
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:25Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=001ad229920097a40c550f91c4445e6da07c79ea P_last=8c07e947a0eda2f2ee77551625fc7d087693248e |D|=1 D=8c07e947a0eda2f2ee77551625fc7d087693248e 
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_ARTIFACT_MUTATED: ∀d P_first⊰d 이나 ∃d∈D: P_last=8c07e947a0eda2f2ee77551625fc7d087693248e ⋠ d — 착수 «후» 아티팩트 변경
U17-B5x 보조(선택·판정 미소비): 로컬 git show 48c9600be48df860516043fc11a842460fcf1572:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=8c07e947a0eda2f2ee77551625fc7d087693248e head=48c9600be48df860516043fc11a842460fcf1572 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=∀d P_first⊰d 이나 ∃d∈D: P_last=8c07e947a0eda2f2ee77551625fc7d087693248e ⋠ d — 착수 «후» 아티팩트 변경 [수집 1건 중 전순서 최소]
u17_rc=1
-- ② 무력화만(CTRL): graft 무효 → 진짜 이력 → LATE(6) --
  *   8c07e94 d: config + artifact in one commit (artifact blob == P)
  |\  
  | | * 88e0e9d d: config + artifact in one commit (artifact blob == P)
  | |/| 
  |/|/  
  | * 001ad22 P: artifact
  * | 48c9600 W: workflow
  |/  
  * 4f5ae98 seed
$ bash u17-verify-v219e2-CTRL-noobserve.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.x5rddSx7Wy
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[8c07e947a0eda2f2ee77551625fc7d087693248e ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:27Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[8c07e947a0eda2f2ee77551625fc7d087693248e ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[8c07e947a0eda2f2ee77551625fc7d087693248e ] |D|=1 D=[8c07e947a0eda2f2ee77551625fc7d087693248e ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 48c9600be48df860516043fc11a842460fcf1572:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=8c07e947a0eda2f2ee77551625fc7d087693248e head=48c9600be48df860516043fc11a842460fcf1572 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_LATE
reason=[E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다 [수집 1건 중 전순서 최소]
u17_rc=1
-- ①+②(v2.19-2): 관측 → UNVERIFIABLE(1) --
  *   8c07e94 d: config + artifact in one commit (artifact blob == P)
  |\  
  | | * 88e0e9d d: config + artifact in one commit (artifact blob == P)
  | |/| 
  |/|/  
  | * 001ad22 P: artifact
  * | 48c9600 W: workflow
  |/  
  * 4f5ae98 seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.LVQyqn33jL
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[8c07e947a0eda2f2ee77551625fc7d087693248e ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 8c07e947a0eda2f2ee77551625fc7d087693248e ) — 부모 집합 재작성 = 신뢰 불가
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:29Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[8c07e947a0eda2f2ee77551625fc7d087693248e ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[8c07e947a0eda2f2ee77551625fc7d087693248e ] |D|=1 D=[8c07e947a0eda2f2ee77551625fc7d087693248e ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 48c9600be48df860516043fc11a842460fcf1572:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=8c07e947a0eda2f2ee77551625fc7d087693248e head=48c9600be48df860516043fc11a842460fcf1572 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 8c07e947a0eda2f2ee77551625fc7d087693248e ) — 부모 집합 재작성 = 신뢰 불가 [수집 2건 중 전순서 최소]
u17_rc=1

########## [E9]-(v) T-84 ⑨ 사후 편집 — 여전히 ARTIFACT_MUTATED(7) ##########
  * 368990d P_edit: artifact edited AFTER d
  * d1f334e d: introduce config/tos_completion.yaml
  * 8791dad W: workflow
  * b8990b3 P: artifact
  * 7367c43 seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/e9v capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.EpgGu9pZ52
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:32Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[b8990b3b3254cb344bee0080d3042058c8c2865c ] P_last(집합·|1|·blob=ae36877de7431236f60ccad09c74af51bbe5b0fe)=[368990de449688251a75fd0484ae30e3babdf95b ] |D|=1 D=[d1f334ec83444c0efdb803298ef997f850096418 ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_ARTIFACT_MUTATED: [E9] ¬LATE ∧ ∃d∈D: x_last=368990de449688251a75fd0484ae30e3babdf95b ⋠ d — 착수 «후» 아티팩트 변경
U17-B5x 보조(선택·판정 미소비): 로컬 git show 8791dad8e75b858b26abdf08a28b0a06503a58f3:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=d1f334ec83444c0efdb803298ef997f850096418 head=8791dad8e75b858b26abdf08a28b0a06503a58f3 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=[E9] ¬LATE ∧ ∃d∈D: x_last=368990de449688251a75fd0484ae30e3babdf95b ⋠ d — 착수 «후» 아티팩트 변경 [수집 1건 중 전순서 최소]
u17_rc=1

########## [E9] 상보성 — ¬LATE 하 ACTIVE / ARTIFACT_MUTATED 상보·결정적 (합성 4종) ##########
  ① 정상        = [E8]-3 (P → W → d)                       → ACTIVE(10)
  ② 사후 편집   = [E9]-(v) (P → W → d → P_edit)             → ARTIFACT_MUTATED(7)
  ③ 다중 도입   = [E9]-(iii) (X ∥ Y 동일 blob → M → W → d)  → ARTIFACT_MUTATED(7)
  ④ 순서 위반   = 아래 (W → d → P)                          → LATE(6)
  * 2c50e85 P: artifact
  * 656ebb4 d: introduce config/tos_completion.yaml
  * 9bf6894 W: workflow
  * 57c4b37 seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e2/e9late capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Ve9w2dmfjd
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:35Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[2c50e8551f15f77a543efa69c330f80c98563527 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[2c50e8551f15f77a543efa69c330f80c98563527 ] |D|=1 D=[656ebb4cec4c4010daf6ee06603f015f6032606c ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 9bf6894b2af9b3270f72d532a877e75289081d1d:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=656ebb4cec4c4010daf6ee06603f015f6032606c head=9bf6894b2af9b3270f72d532a877e75289081d1d merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_LATE
reason=[E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다 [수집 1건 중 전순서 최소]
u17_rc=1

########## 본 저장소 현행 상태 — live (에라타 2차 실행기 · HEAD ad5be1a3) ##########
$ bash u17-verify-v219e2.sh /Users/harris/Development/private/kis_unified_sts
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.xiYkofefri
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-A00 apps/github-actions  utc=2026-08-19T02:41:40Z  http=200  x-github-request-id=7465:328E21:2FA4BA:351164:6A8517E3
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T02:41:40Z  http=200  x-github-request-id=0AD3:346330:2FCA05:3535A5:6A8517E3  (.default_branch=main)
U17-fire PREVENTION_ABSENT: 아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T02:41:41Z  http=200  x-github-request-id=6BD4:389700:2F79E5:34E74E:6A8517E4
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T02:41:41Z  http=200  x-github-request-id=CAB8:1D7764:2FD2E6:3540D6:6A8517E5
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T02:41:42Z  http=200  x-github-request-id=CECE:328E21:2FA7F1:3514FE:6A8517E6
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T02:41:43Z  http=200  x-github-request-id=BB70:177308:2FB773:3524B1:6A8517E6
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|0|)=[ ] P_last(집합·|0|·blob=∅)=[ ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
u17_rc=1
```

### 4-2. U-16 축 — `bash t82v219e2.sh` ([E8] `c_APP`·`C_R` 축 · `.git/info/grafts` · 정상 회귀)

```text
t82v219e2_utc=2026-08-19T02:43:41Z
sha256(u16-full-exec-v219e2.py)=cca1d6d7e491a7941f82897ea834655ab6494eff94cae15c70939435ac709482   (재실행 실행기 — 에라타 2차 델타 E8)
sha256(u16-full-exec-v219e2-CTRL-noobserve.py)=87c1efa0aaf9ff3b69663904cd093fca1466b03b8b5b911a7c49089fc50862f9  (E8 대조군 — ① 관측만 제거 · ② 무력화 유지)
sha256(u16-full-exec-v219e.py)=729867ca66122d692ce56b2046adcfb3a30b36b92005c4ac11b4d9baa5423696   (직전 실행기 — 197f4fe4 증거의 것 · ①② 둘 다 없음)
sha256(u16-order-ctrl-g1first.py)=4e9f0bc42b86d5e9f34d5f216df474c0da5a3b655b6fddeecf6a31f8501a51cd (⑳ⓑ 순서 대조군 — 불변 재사용)
D_NO = 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9
계약 U-16-d 전순서: 1 CONSUMER_ABSENT · 2 PROVENANCE_UNVERIFIABLE · 3 APPROVAL_MALFORMED · 4 APPROVAL_MISSING · 5 SAME_COMMIT · 6 AFTER · 7 CONTENT_DRIFT · 8 HEAD_INVALID · 9 ROW_MUTATED · 10 UNBOUND · 11 ORDER_INVALID · 12 NO_ROWS_CLEAR

########## [E8]-U16-1 «c_APP» 축 — ⑳ⓐ 픽스처 (진실 = APPROVAL_MALFORMED(3) · |c_APP|=2) ##########
H0=c92c956182e703c646eb0d568eb3f86ffaedf33d X=06e6d56e116cfdb98a6193c3f4c659f71938366d CN=4b569a37d15a113177fa1f3e7b609be1703ef7ee Y=be672efb76122e888fd9c71be34d9ab23d410a0c M=HEAD=55a87e9a89710d6707950d642ef459d5d6baf082
  판별 실측: is_shallow=false · git replace -l=[] · .git/info/grafts=ABSENT
  %P(55a87e9) replace-따름 = 4b569a37d15a113177fa1f3e7b609be1703ef7ee be672efb76122e888fd9c71be34d9ab23d410a0c
  %P(55a87e9) 무력화 하    = 4b569a37d15a113177fa1f3e7b609be1703ef7ee be672efb76122e888fd9c71be34d9ab23d410a0c
  *   55a87e9 M: merge sibling identical approval introduction
  |\  
  | * be672ef Y: approval row A (byte-identical) [side y]
  * | 4b569a3 CN: NO transition (child of X)
  * | 06e6d56 X: approval row A [side x]
  |/  
  * c92c956 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e2.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=[] · .git/info/grafts=ABSENT · is_shallow=False · 무력화 = git --no-replace-objects (전 호출)
HEAD=55a87e9 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('06e6d56', '4b569a3', 'YES->NO'), ('be672ef', '55a87e9', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=2', ['be672ef', '06e6d56'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=2 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['be672ef', '06e6d56']
  · edge#1[r1 06e6d56->4b569a3 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
  · edge#2[r1 be672ef->55a87e9 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['be672ef', '06e6d56'] · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1

$ git -C <fixture> replace --graft 55a87e9a89710d6707950d642ef459d5d6baf082 4b569a37d15a113177fa1f3e7b609be1703ef7ee      # M 의 부모에서 Y 를 «지운다» — 형제 도입을 숨긴다
  판별 실측: is_shallow=false · git replace -l=[55a87e9a89710d6707950d642ef459d5d6baf082 ] · .git/info/grafts=ABSENT
  %P(55a87e9) replace-따름 = 4b569a37d15a113177fa1f3e7b609be1703ef7ee
  %P(55a87e9) 무력화 하    = 4b569a37d15a113177fa1f3e7b609be1703ef7ee be672efb76122e888fd9c71be34d9ab23d410a0c

########## [E8]-U16-1a 대조 — **직전 실행기**(①② 둘 다 없음) → 형제 도입이 사라져 fail-open ##########
  * 55a87e9 M: merge sibling identical approval introduction
  | * 8566a0b M: merge sibling identical approval introduction
  |/  
  * 4b569a3 CN: NO transition (child of X)
  * 06e6d56 X: approval row A [side x]
  * c92c956 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e.py <fixture>
HEAD=55a87e9 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('06e6d56', '4b569a3', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['06e6d56'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 06e6d56->4b569a3 YES->NO]: COVERED by c_APP=06e6d56 C_R={c92c956}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## [E8]-U16-1b **② 무력화만**(CTRL-noobserve) → 진짜 부모 → |c_APP|=2 → APPROVAL_MALFORMED(3) 복원 ##########
  * 55a87e9 M: merge sibling identical approval introduction
  | * 8566a0b M: merge sibling identical approval introduction
  |/  
  * 4b569a3 CN: NO transition (child of X)
  * 06e6d56 X: approval row A [side x]
  * c92c956 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e2-CTRL-noobserve.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=['55a87e9'] · .git/info/grafts=ABSENT · is_shallow=False · 무력화 = git --no-replace-objects (전 호출)
HEAD=55a87e9 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('06e6d56', '4b569a3', 'YES->NO'), ('be672ef', '55a87e9', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=2', ['be672ef', '06e6d56'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=2 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['be672ef', '06e6d56']
  · edge#1[r1 06e6d56->4b569a3 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
  · edge#2[r1 be672ef->55a87e9 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['be672ef', '06e6d56'] · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1

########## [E8]-U16-1c **①+② 둘 다**(v2.19-2 판정 실행기) → 관측이 먼저 → PROVENANCE_UNVERIFIABLE(2) ##########
  * 55a87e9 M: merge sibling identical approval introduction
  | * 8566a0b M: merge sibling identical approval introduction
  |/  
  * 4b569a3 CN: NO transition (child of X)
  * 06e6d56 X: approval row A [side x]
  * c92c956 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e2.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=['55a87e9'] · .git/info/grafts=ABSENT · is_shallow=False · 무력화 = git --no-replace-objects (전 호출)
HEAD=55a87e9 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('06e6d56', '4b569a3', 'YES->NO'), ('be672ef', '55a87e9', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=2', ['be672ef', '06e6d56'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=2 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2

[상태 귀속] 계약 U-16-d 순서 적용
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED] git replace -l 비공집합(['55a87e9']) — 부모 집합 재작성 = 신뢰 불가
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['be672ef', '06e6d56']
  · edge#1[r1 06e6d56->4b569a3 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
  · edge#2[r1 be672ef->55a87e9 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ global — [PARENTS-UNTRUSTED] git replace -l 비공집합(['55a87e9']) — 부모 집합 재작성 = 신뢰 불가 · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_MALFORMED']
u16_rc=1

########## [E8]-U16-2 «.git/info/grafts» — ② 무력화로 «꺼지지 않는다» → ① 관측이 담당 ##########
$ cat <fixture>/.git/info/grafts
  55a87e9a89710d6707950d642ef459d5d6baf082 4b569a37d15a113177fa1f3e7b609be1703ef7ee
  판별 실측: is_shallow=false · git replace -l=[] · .git/info/grafts=present
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
  %P(55a87e9) replace-따름 = 4b569a37d15a113177fa1f3e7b609be1703ef7ee
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
  %P(55a87e9) 무력화 하    = 4b569a37d15a113177fa1f3e7b609be1703ef7ee

########## [E8]-U16-2a **② 무력화만**(CTRL) → grafts 는 안 꺼지므로 fail-open 잔존 ##########
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
  * 55a87e9 M: merge sibling identical approval introduction
  * 4b569a3 CN: NO transition (child of X)
  * 06e6d56 X: approval row A [side x]
  * c92c956 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e2-CTRL-noobserve.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=[] · .git/info/grafts=present · is_shallow=False · 무력화 = git --no-replace-objects (전 호출)
HEAD=55a87e9 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('06e6d56', '4b569a3', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['06e6d56'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 06e6d56->4b569a3 YES->NO]: COVERED by c_APP=06e6d56 C_R={c92c956}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## [E8]-U16-2b **① 관측 포함**(v2.19-2) → PROVENANCE_UNVERIFIABLE(2) ##########
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
  * 55a87e9 M: merge sibling identical approval introduction
  * 4b569a3 CN: NO transition (child of X)
  * 06e6d56 X: approval row A [side x]
  * c92c956 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e2.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=[] · .git/info/grafts=present · is_shallow=False · 무력화 = git --no-replace-objects (전 호출)
HEAD=55a87e9 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('06e6d56', '4b569a3', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['06e6d56'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
  · edge#1[r1 06e6d56->4b569a3 YES->NO]: COVERED by c_APP=06e6d56 C_R={c92c956}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ global — [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) · 발화 전체=['PROVENANCE_UNVERIFIABLE']
u16_rc=1

########## [E8]-U16-3 «C_R» 축 — ⑮(신규 아티팩트 R ∥ A) 에 graft 를 걸어 «리뷰 blob 도입 지점»을 숨긴다 (진실 = APPROVAL_ORDER_INVALID(11)) ##########
H0=f768ab508c148e7152b7603335218a16dbca30b8 R=c50c29c7e3e129f44e2eebe60c903af2a89381ae A=ca705744ca4d3a5e0db919867e8ba71a31e05a01 M0=d9364ca657044d02189775e88dc580c0af2a6ab0 M=601e38974a13f85bdb934e7d79529ce524a3a880
  판별 실측: is_shallow=false · git replace -l=[] · .git/info/grafts=ABSENT
  %P(d9364ca) replace-따름 = ca705744ca4d3a5e0db919867e8ba71a31e05a01 c50c29c7e3e129f44e2eebe60c903af2a89381ae
  %P(d9364ca) 무력화 하    = ca705744ca4d3a5e0db919867e8ba71a31e05a01 c50c29c7e3e129f44e2eebe60c903af2a89381ae
  * 601e389 M: NO transition
  *   d9364ca M0: merge R
  |\  
  | * c50c29c R: new reviewer artifact [side r]
  * | ca70574 A: approval (aah=R) [side a · R 은 A 의 조상이 아니다]
  |/  
  * f768ab5 H0: base (reviewer 경로 없음)
$ python3 u16-full-exec-v219e2.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=[] · .git/info/grafts=ABSENT · is_shallow=False · 무력화 = git --no-replace-objects (전 호출)
HEAD=601e389 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('d9364ca', '601e389', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['ca70574'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 d9364ca->601e389 YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={c50c29c} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={c50c29c}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=전순서 최소 = APPROVAL_ORDER_INVALID(11) @ edge#1[r1 d9364ca->601e389 YES->NO] — g6 C_R={c50c29c} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={c50c29c} · 발화 전체=['APPROVAL_ORDER_INVALID']
u16_rc=1

$ git -C <fixture> replace --graft ca705744ca4d3a5e0db919867e8ba71a31e05a01 c50c29c7e3e129f44e2eebe60c903af2a89381ae      # A 의 부모를 R 로 «재작성» → R 이 A 의 진 조상이 된다(증인 위조)
  판별 실측: is_shallow=false · git replace -l=[ca705744ca4d3a5e0db919867e8ba71a31e05a01 ] · .git/info/grafts=ABSENT
  %P(ca70574) replace-따름 = c50c29c7e3e129f44e2eebe60c903af2a89381ae
  %P(ca70574) 무력화 하    = f768ab508c148e7152b7603335218a16dbca30b8

########## [E8]-U16-3a 대조 — **직전 실행기**(①② 없음) → g6 증인이 «생겨» fail-open ##########
  * 601e389 M: NO transition
  *   d9364ca M0: merge R
  |\  
  * | ca70574 A: approval (aah=R) [side a · R 은 A 의 조상이 아니다]
  |/  
  | * de9f02d A: approval (aah=R) [side a · R 은 A 의 조상이 아니다]
  |/  
  * c50c29c R: new reviewer artifact [side r]
  * f768ab5 H0: base (reviewer 경로 없음)
$ python3 u16-full-exec-v219e.py <fixture>
HEAD=601e389 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('d9364ca', '601e389', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['ca70574'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 d9364ca->601e389 YES->NO]: COVERED by c_APP=ca70574 C_R={c50c29c}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## [E8]-U16-3b **② 무력화만**(CTRL) → 진짜 부모 → APPROVAL_ORDER_INVALID(11) 복원 ##########
  * 601e389 M: NO transition
  *   d9364ca M0: merge R
  |\  
  * | ca70574 A: approval (aah=R) [side a · R 은 A 의 조상이 아니다]
  |/  
  | * de9f02d A: approval (aah=R) [side a · R 은 A 의 조상이 아니다]
  |/  
  * c50c29c R: new reviewer artifact [side r]
  * f768ab5 H0: base (reviewer 경로 없음)
$ python3 u16-full-exec-v219e2-CTRL-noobserve.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=['ca70574'] · .git/info/grafts=ABSENT · is_shallow=False · 무력화 = git --no-replace-objects (전 호출)
HEAD=601e389 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('d9364ca', '601e389', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['ca70574'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 d9364ca->601e389 YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={c50c29c} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={c50c29c}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=전순서 최소 = APPROVAL_ORDER_INVALID(11) @ edge#1[r1 d9364ca->601e389 YES->NO] — g6 C_R={c50c29c} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={c50c29c} · 발화 전체=['APPROVAL_ORDER_INVALID']
u16_rc=1

########## [E8]-U16-3c **①+②**(v2.19-2) → PROVENANCE_UNVERIFIABLE(2) ##########
  * 601e389 M: NO transition
  *   d9364ca M0: merge R
  |\  
  * | ca70574 A: approval (aah=R) [side a · R 은 A 의 조상이 아니다]
  |/  
  | * de9f02d A: approval (aah=R) [side a · R 은 A 의 조상이 아니다]
  |/  
  * c50c29c R: new reviewer artifact [side r]
  * f768ab5 H0: base (reviewer 경로 없음)
$ python3 u16-full-exec-v219e2.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=['ca70574'] · .git/info/grafts=ABSENT · is_shallow=False · 무력화 = git --no-replace-objects (전 호출)
HEAD=601e389 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('d9364ca', '601e389', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['ca70574'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED] git replace -l 비공집합(['ca70574']) — 부모 집합 재작성 = 신뢰 불가
  · edge#1[r1 d9364ca->601e389 YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={c50c29c} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={c50c29c}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ global — [PARENTS-UNTRUSTED] git replace -l 비공집합(['ca70574']) — 부모 집합 재작성 = 신뢰 불가 · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_ORDER_INVALID']
u16_rc=1

########## [E8]-U16-4 정상 회귀 — replace 0 · grafts 부재 · shallow=false ⇒ 직전 판과 «불변» ##########
-- ⑳ⓐ 원본(graft 없음) → APPROVAL_MALFORMED(3) --
  판별 실측: is_shallow=false · git replace -l=[] · .git/info/grafts=ABSENT
  %P(1e4b7ab) replace-따름 = 0b61a492b25b63266a059dacedc8ec51149a6d3e a224722c58c2b9165235cd52a87dc31ca2ca6f17
  %P(1e4b7ab) 무력화 하    = 0b61a492b25b63266a059dacedc8ec51149a6d3e a224722c58c2b9165235cd52a87dc31ca2ca6f17
  *   1e4b7ab M: merge sibling identical approval introduction
  |\  
  | * a224722 Y: approval row A (byte-identical) [side y]
  * | 0b61a49 CN: NO transition (child of X)
  * | ab56db0 X: approval row A [side x]
  |/  
  * 9308742 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e2.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=[] · .git/info/grafts=ABSENT · is_shallow=False · 무력화 = git --no-replace-objects (전 호출)
HEAD=1e4b7ab is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('ab56db0', '0b61a49', 'YES->NO'), ('a224722', '1e4b7ab', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=2', ['a224722', 'ab56db0'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=2 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['a224722', 'ab56db0']
  · edge#1[r1 ab56db0->0b61a49 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
  · edge#2[r1 a224722->1e4b7ab YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['a224722', 'ab56db0'] · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1
-- ⑱ 정정 문언(같은 row_id·다른 승인 행·형제 도입→merge) → NO_ROWS_CLEAR/0 --
자동 병합: LEDGER.md
충돌 (내용): LEDGER.md에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
  * a2366af e2: YES->NO
  * 0ccb122 back to YES
  * 1248ab5 e1: ABSENT->NO
  *   d46669a MA: merge sibling approval introductions
  |\  
  | * ebd4a40 A2: approval (YES->NO, rationale b)
  * | 7969385 A1: approval (ABSENT->NO, rationale a)
  |/  
  * 159d119 H0: r1 absent (reviewer digest)
$ python3 u16-full-exec-v219e2.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=[] · .git/info/grafts=ABSENT · is_shallow=False · 무력화 = git --no-replace-objects (전 호출)
HEAD=a2366af is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('d46669a', '1248ab5', 'ABSENT->NO'), ('0ccb122', 'a2366af', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'ABSENT->NO', '|c_APP|=1', ['7969385']), ('r1', 'YES->NO', '|c_APP|=1', ['ebd4a40'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/ABSENT->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
  row r1/YES->NO raw#1: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 d46669a->1248ab5 ABSENT->NO]: COVERED by c_APP=7969385 C_R={159d119}
  · edge#2[r1 0ccb122->a2366af YES->NO]: COVERED by c_APP=ebd4a40 C_R={159d119}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0
-- ⑳ⓑ 얕은 클론(국소 [E6] 유지) → PROVENANCE_UNVERIFIABLE(2) · 순서 대조군은 여전히 3 --
  is_shallow=true · .git/shallow=1e4b7ab5b4f7eac9c97e7792967319aaaa0df1db  · replace -l=[] · grafts=ABSENT
  * 1e4b7ab M: merge sibling identical approval introduction
$ python3 u16-full-exec-v219e2.py <fixture>
[PARENTS-UNTRUSTED] 관측: git replace -l=[] · .git/info/grafts=ABSENT · is_shallow=True · 무력화 = git --no-replace-objects (전 호출)
HEAD=1e4b7ab is_shallow=True .git/shallow=['1e4b7ab'] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('ROOT', '1e4b7ab', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=0(+경계 1)', [])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=0 경계커밋=['1e4b7ab'] g4_bad=False g2_bad=False 대응간선=0 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: PROVENANCE_UNVERIFIABLE(2) — |c_APP|=0 (도입 지점 파생 불가)
  · edge#1[r1 ROOT->1e4b7ab ABSENT->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ row[r1/YES->NO] — |c_APP|=0 (도입 지점 파생 불가) · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_MISSING']
u16_rc=1
  * 1e4b7ab M: merge sibling identical approval introduction
$ python3 u16-order-ctrl-g1first.py <fixture>
HEAD=1e4b7ab shallow=True shallow_boundary=['1e4b7ab'] EVAL_ORDER=g1-first
NO_rows=['r1']
EDGES(r1)=[('ROOT', '1e4b7ab', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=0(+경계 1)', [])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=0 경계커밋=['1e4b7ab'] g4_bad=False g2_bad=False 대응간선=0 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — 고아 — 대응 간선 0 (row_id 간선 1 · g1 transition 전건 불일치)
  · edge#1[r1 ROOT->1e4b7ab ABSENT->NO]: APPROVAL_MALFORMED(3) — g1 YES->NO≠ABSENT->NO (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — 고아 — 대응 간선 0 (row_id 간선 1 · g1 transition 전건 불일치) · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1
```

---
## 5. 관측 보고 · **신규** 계약 결함 후보 (고치지 않는다 — `bound_paths` 동결 · 다음 에라타 대상)

> 직전 addendum(`197f4fe4`)의 N-1(replace/graft fail-open)·N-2(`P_last` 다부모)는 **에라타 2차 `ad5be1a3` 가 E8·E9 로 처분**했고, §3·§4 가 그 처분값을 실측으로 확인했다(전건 일치).
> N-3~N-5(관측)는 U-16-d 전순서 머리에 «세 층» 주석으로 반영됐다. 아래는 **이번 addendum 실행에서 «새로» 관측된 것**뿐이다.

### M-1 (문언 충돌 — 판별력 직결) — `E8 ①` 의 «얕은 클론 아님» 전역 관측이 `E6` 의 «국소 판정» 과 충돌한다

- **문언 ①**: `U-16-c` `[PARENTS-UNTRUSTED]` **판별 ①**(계약 `ad5be1a3:7012-7015`) — «`git replace -l` **공집합** ∧ `.git/info/grafts` **부재** ∧ **얕은 클론 아님**. **하나라도 위반** = 부모 신뢰 불가 → `PROVENANCE_UNVERIFIABLE`/`PREVENTION_UNVERIFIABLE`».
- **문언 ②**: 같은 계약의 `U-16-d` **① 선-검사**(`ad5be1a3:7123` 부근·**E6**) — «**«얕은 클론»을 «전역 단축»으로 읽지 않는다** … 얕음 자체가 아니라 판정에 필요한 부모가 미상인 경계 커밋이 **«해당 행/간선의» 도입 후보 우주에 있어 크기 0이 될 때** 이 선-검사가 발화한다(**국소**)».
- **충돌**: ① 을 문자 그대로 읽으면 **얕은 클론은 후보 우주와 «무관하게» 무조건 차단**이고, 그러면 ② 가 세운 **`T-82 ⑳ⓑ` 의 판별력(2 vs 3)** 과 직전 addendum §4-3 의 «얕지만 후보 우주 밖이면 접지 않는다» 대조가 **둘 다 무너진다**(둘 다 전역 2 가 되어 «g1 먼저» 구현과 구별 불가 — 직전 addendum **D-3** 이 지적하고 **E6** 이 고친 바로 그 자리다).
- **본 실행기의 독해(명시)**: **replace/grafts 축만 «전역 관측»**(어느 커밋이 재작성됐는지 per-commit 판별 «수단이 없다» — `%P`·`rev-list`·`merge-base` 가 전부 오염되므로 뷰 전체가 신뢰 불가) · **얕음 축은 «국소»**(그 커밋의 부모 미상 여부를 per-commit 으로 판별할 수 있다). 이 독해로 §4-2 의 회귀가 **⑳ⓑ 2 vs 3 · 얕지만 후보 우주 밖 → `NO_ROWS_CLEAR`/0** 를 그대로 유지했다(실측).
- **처분 제안(다음 에라타)**: 판별 ① 을 **«전역 축(replace ref · `.git/info/grafts`)»** 과 **«국소 축(얕은 경계)»** 으로 **명시 분리**하고, ② 의 국소 규율을 그 국소 축에만 결속. **극성 근거**: 전역/국소의 구분은 «per-commit 판별 가능성»이 정하며, 그것이 «판정 불가를 판정 불가로»(fail-closed)와 «과잉 차단 회피»를 동시에 만족시키는 유일한 분할이다.

### M-2 (관측 — 결함 아님 · 계약 설계의 실측 확증) — 두 limb 은 «서로를 가리지 않는다»

- 우려: ② 무력화(`GIT_NO_REPLACE_OBJECTS=1` / `--no-replace-objects`)가 ① 관측(`git replace -l`)까지 «가려» 관측이 자기무력화될 수 있다.
- **실측(§6)**: `git replace -l` = `GIT_NO_REPLACE_OBJECTS=1 git replace -l` = `git --no-replace-objects replace -l` = **동일한 비공집합**. ⇒ **무간섭**. 계약이 ①과 ②를 «둘 다» 요구한 것이 실행 가능하다.

### M-3 (관측 — 정직 경계) — `[PARENTS-UNTRUSTED]` 의 «열거»는 열린-세계다

- 계약이 고정한 재작성 표면은 **`refs/replace/*`(= `git replace -l`)와 `.git/info/grafts`** 둘이다. 직전 addendum N-1 이 «`.git/shallow`·`--is-shallow-repository`·부모 객체 조회» 세 수단의 **열거가 새 표면을 못 잡는다**고 보고했고, 이번 에라타가 표면을 둘 더 열거했다 — **같은 구조**다.
- **관측**: 이 축은 «부모 집합이 참인가»라는 **전칭 명제**인데 판별은 **열거**다. 열거는 «작성 시점에 고정돼 이후 추가분을 조용히 놓친다»(계약 S-6 이 다른 자리에서 세운 규율). 지금 판에서 **알려진 미검사 표면을 하나 지목하지는 못했다**(그래서 «결함»이 아니라 «정직 경계» 로 적는다). 다만 **판별을 «열거»가 아니라 «부모 집합의 독립 재파생»**(예: 커밋 객체를 직접 파싱해 `parent` 헤더를 읽고 `%P` 와 대조)으로 두면 열린-세계 문제가 닫힌다 — 구조 파생 > 열거는 이 계약이 반복해 세운 방향이다. **비차단 제안**.

### M-4 (관측) — `git replace --graft` 는 «새 커밋 객체»를 만들어 `--all` 뷰에 두 커밋이 보인다

- §4-1 [E8]-1 의 `git log --oneline --graph --all` 출력에 **같은 메시지의 커밋이 둘** 나타난다(원본 + 대체본). 이는 ① 관측을 보조하는 **부수 관측 표면**이지만 계약이 지목하지 않았고, 대체본이 원본과 메시지가 다르면 눈에 띄지 않으므로 **판별 근거로 쓰기엔 약하다**(기록만).

### M-5 (관측 — E9 파생 효과) — `|P_first|` 도 «집합»이 되면서 `LATE` 술어가 «∃d: ∀x» 로 바뀌었다

- E9 전: `P_first` 는 스칼라라 `∃d: P_first ⋠ d`. E9 후: 집합이라 **`∃d ∈ D: ∀x ∈ P_first: x ⋠ d`**. §4-1 [E9]-(ii) 에서 `|P_first| = 2` 가 실제로 나왔고(두 브랜치가 각각 경로를 도입), 그 경우 «어느 하나라도 조상이면 ¬LATE» 로 접힌다 — **∃ 양화자**다.
- **관측**: 계약은 `P_first` 의 **카디널리티 처분을 두지 않았다**(`P_last` 만 0/1/>1 처분이 있다). `|P_first| = 0` 이면 `∀x ∈ ∅` 가 **공허참**이라 **`LATE` 가 발화**한다(fail-closed 방향이라 극성은 안전하나 **문언에 그 자리가 없다**). 본 저장소 live 실행에서 `|P_first| = 0`(아티팩트 부재)이지만 전순서 2 `ABSENT` 가 먼저라 관측되지 않는다. **비차단 문언 공백**.

---
## 6. 사후 검증 원문 (repo 무영향 · HEAD 불변 · 서버 설정 무변경 · S-24 재확인 · 두 limb 무간섭 · 픽스처 격리)

```text
post_utc=2026-08-19T02:44:54Z
$ git -C <repo> rev-parse HEAD
ad5be1a36dc489234f71a0d8343a5d83cda13ac1
$ git -C <repo> status --short
 M uv.lock
?? tools/spikes/
$ git -C <repo> diff --quiet ad5be1a3 -- <계약>  → rc
rc=0
$ git -C <repo> rev-list --count ad5be1a3..HEAD -- <계약>
0
$ sed -n '4608,4708p' <워킹트리 계약> | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git -C <repo> show ad5be1a3:<계약> | sed -n '4608,4708p' | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git -C <repo> show e3ed4e78:<계약> | sed -n '4598,4698p' | shasum -a 256   (직전 판 — byte-동일 확인)
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git -C <repo> reflog -n 3
ad5be1a3 HEAD@{0}: commit: docs(tos): phase0 completion contract v2.19 errata #2 — [PARENTS-UNTRUSTED] (replace/graft), P_first/P_last ∀-parent structural definition
197f4fe4 HEAD@{1}: commit: docs(tos): record v2.19 errata addendum evidence (S-24 — section-range proof · classic terminal · [SHALLOW] · host key · pre-check/orphan)
e3ed4e78 HEAD@{2}: commit: docs(tos): phase0 completion contract v2.19 errata — classic terminal, t_land fail-closed, [SHALLOW] boundary, T-82 ⑱ literal, pre-check localization
--- [E8] 본 저장소 자체의 부모 신뢰 관측 ---
$ git -C <repo> replace -l
(빈 출력 = 공집합)
$ ls <repo>/.git/info/grafts
ls: /Users/harris/Development/private/kis_unified_sts/.git/info/grafts: No such file or directory
(ABSENT)
$ git -C <repo> rev-parse --is-shallow-repository
false
--- [E8] 두 limb 의 간섭 여부 실측 (① 관측이 ② 무력화 하에서도 동작하는가) ---
$ git replace -l                                  = baf786e4ea2ebd02761666b29afa0e72cc908a34 
$ GIT_NO_REPLACE_OBJECTS=1 git replace -l          = baf786e4ea2ebd02761666b29afa0e72cc908a34 
$ git --no-replace-objects replace -l              = baf786e4ea2ebd02761666b29afa0e72cc908a34 
  ⇒ ② 무력화가 ① 관측을 가리지 않는다(두 limb 무간섭)
--- 픽스처 격리 ---
$ find <scratchpad addendum-2 fixtures> -maxdepth 3 -name .git | wc -l
      15
```

**판독**: HEAD `ad5be1a3` 불변 · 계약 워킹트리 = 에라타 2차 blob(`git diff --quiet` rc=0) · `ad5be1a3..HEAD` 계약 커밋 0 · 하니스 블록 `sed -n '4608,4708p'` sha256 이 워킹트리·`ad5be1a3` 양쪽에서
**`957bf49d…`** 이고 **`e3ed4e78:4598-4698` 과도 동일**(§1 ④ 와 이중 확인) · 워킹트리 변경은 실행 «전»부터 있던 `uv.lock`·`tools/spikes/` 뿐(본 실행이 만든 것 0 — 선행 증거 3파일은 `90a5ce7d`·`197f4fe4` 로 이미 커밋됐다) ·
**본 저장소는 `git replace -l` 공집합 · `.git/info/grafts` 부재 · `--is-shallow-repository=false`** ⇒ `[PARENTS-UNTRUSTED]` 관측 ① 을 통과하는 상태이고, `replace`/`grafts` 조작은 **전부 scratchpad 픽스처 안에서만** 이뤄졌다 ·
**두 limb 무간섭 실측**(§5 M-2) · addendum-2 픽스처 git 저장소 15개는 전부 scratchpad 하위(`fx84f/*`·`fx82f/*`)다.
**서버 접근**: U-17 축은 SIMULATED seam(`responder=file:`)과 본 저장소 live 1회(GET `gh api --hostname github.com …`)뿐이고 U-16 축은 GitHub 조회 0 이다 ⇒ **서버 쓰기·설정 변경 0**.
