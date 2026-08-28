# U17-PREVENTION-CHECK-V219-ADDENDUM-3 — v2.19 에라타 3차 `f6493d23` S-24 addendum (절 범위 diff 기계 증명 + 영향 변이 재실행: E10 `[PARENTS-UNTRUSTED]` 재구조화 · E11 `P_first` 카디널리티)

> **비규범 부속** — 계약 v2.19 에라타 3차 `f6493d23`(7,344행) 후 **S-24** 이행. 선행 증거 `U17-PREVENTION-CHECK-V219.md`·`U16-LEDGER-CHECK-V219.md`(`90a5ce7d`) · `…-ADDENDUM.md`(`197f4fe4`) ·
> `…-ADDENDUM-2.md`(`c83e44db`)는 U-15-e **(4d) 불변 규율을 준용해 편집하지 않고**, ① `git diff ad5be1a3..f6493d23 -- <계약>` 전문과 **닿는/닿지 않는 절 범위의 기계 증명**(§1)으로
> **비영향 변이의 증거가 그대로 결속됨을 선언**하고, ② **영향 변이만 재실행**(§2~§4)한다. **U-17·U-16 두 축을 한 addendum 에 절로 나눠 수록**(파일 하나).
> **결속**: 실행 시점 HEAD == `f6493d23` · 계약 워킹트리 blob `2f9141f8` == `git show f6493d23:<계약>` blob(`git diff --quiet f6493d23 -- <계약>` rc=0 · 워킹트리 sha256
> `cc1661fb09d19ab0aaf2313e89937f6da386d607c8c205a8d81e33fdace3303c`) · `f6493d23..HEAD` 계약 커밋 **0** ·
> 하니스 §12.3.4-R 블록 `sed -n '4614,4714p'` sha256 **`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`** — **`ad5be1a3` 의 `:4608-4708` 과 byte-동일**(§1 ④ · §6 재확인).
> **판정 소비자는 이 파일의 응답을 신뢰하지 않고 스스로 live 조회한다**(대조용) · **서버 쓰기·설정 변경 0**(U-17 축은 SIMULATED seam + 본 저장소 live 1회, U-16 축은 GitHub 조회 0) ·
> 픽스처는 scratchpad 하위 **독립 git 저장소**(`fx84g/*`·`fx82g/*` — 본 저장소 무접촉·worktree 미사용 · `git replace`/`info/grafts`/`--separate-git-dir`/`GIT_REPLACE_REF_BASE` 조작은 **전부 그 픽스처 안에서만**; 본 저장소는 §6 에서 ㉠ 일치·㉡ 공집합/부재·㉢ 얕지 않음으로 확인).
- **생성 시각**: 2026-08-19T03:14:41Z (UTC) · 실행 `t84v219e3_utc=2026-08-19T03:13:05Z` · `t82v219e3_utc=2026-08-19T03:13:45Z` · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트(저작자·심판 아님)
- **실행기 결속**:
  - sha256(`s24-proof-3.sh`) = **`1116fbd9ae20d41f910237bab638d37e51db33831617c273ef6a988685808298`** (§1)
  - sha256(`u17-verify-v219e3.sh`) = **`2554776da60ba9ff1bec99a81891b9d8ac564cc1e5cf2b6dc887e61cc25d78bb`** (직전 `8516adc2…` 대비 **diff 77행** — E10·E11, §2-1)
  - sha256(`u17-ctrl-obs-literal.sh`) = **`65afc9d2dc134a481a26615f4f5fb62e29257715bff30fc92d2d71753649cf1d`** (**E10 대조군** — ㉠ 발화 «제거» + ㉡ 을 **계약 문언 리터럴** `.git/info/grafts` 로. diff **12행**. 판정용 아님)
  - sha256(`u16-full-exec-v219e3.py`) = **`d0c62ee72f8d4858fa7fe363b10c4c0bb4b35b0512e06f4888281dec175970f5`** (직전 `cca1d6d7…` 대비 **diff 73행** — E10, §2-2)
  - sha256(`u16-ctrl-obs-literal.py`) = `6ebdf1cf4772b862c5202c651982947f2f2e368c5d0046cbd49c667e24254449` (diff 16행) · sha256(`u16-order-ctrl-g1first-v219e3.py`) = `8aca665fb9be752d8450787c79d55fb102093fe3cc97d9377243ce94776f4da5` (diff **4행**) · sha256(`u16-ctrl-shallow-global.py`) = `5b4bdda01866ff62e03e6edf5730cd7cc881295c89c472cdaf581fb9635512e9` (diff 8행 — **「얕음=전역」 문자 구현**)
  - sha256(`t84v219e3.sh`) = `1701fb927cb274f98c455d672c4a2c91bf725f52016f3c94b3f25c7deba32211` · sha256(`t82v219e3.sh`) = `519e2af24c911bb832437c2a973106be3b12c3377bb3daf6ce3eac2914fc20f5`
  - **불변 재사용(직전 판 = ㉠ 없음·㉡+무력화만)**: `u17-verify-v219e2.sh` `8516adc2…` · `u16-full-exec-v219e2.py` `cca1d6d7…`

## 0. 결속 선언 (S-24 ②·①)

| 변이 (선행 증거 `90a5ce7d`·`197f4fe4`·`c83e44db`) | 닿는 에라타 3차 절 | 처분 |
| --- | --- | --- |
| **T-84 ①~⑫ 전건** · **T-82 ⑮~⑳ 전건** · (a)·(b)·(α) 술어 · U-17-c 전순서 10단·상태표·기계 조건 · U-16-d 전순서 12단·선-검사·g-단락 · `c_APP` 수식 · **[E8] 참조 자리(D·C_R)** | — (§1 ③ 이 **22건 ∅** 로 증명 — 참조 문구가 «불변»이라 D·C_R 자리도 ∅ 다) | **비영향 — 세 선행 증거 그대로 결속** |
| **[E8] ①②③ 판별**(replace·grafts·얕음) · addendum-2 **M-1**(전역/국소 충돌) · **M-3**(열거는 열린-세계) | **E10** `[PARENTS-UNTRUSTED]` 재구조화 — ㉠ 구조 재파생(주) · ㉡ 전역 관측(보조) · ㉢ 국소 | **재실행 + 축 확장**(§3-1·§4-1·§4-2) |
| addendum-2 **M-5**(`P_first` 카디널리티 공백) | **E11** `P_first` 0/>1/=1 처분 | **재실행**(§3-2) |
| addendum-2 **N-3~5**(세 층) | — (2차에서 이미 반영, 3차 무변경) | **비영향** |

- **결과 요약 (재실행분 · stdout·rc 원문 그대로)**:

| # | 변이 | 실행기 | 방출값 | rc | 기대 (f6493d23 문언) | 대조 |
| --- | --- | --- | --- | --- | --- | --- |
| **0** | **A. ㉠ 원시 프로브 5구성** | (실행기 밖) | (1) 평시 재파생==뷰 · (2) `replace --graft` 재파생≠뷰 · (3) `grafts` 재파생≠뷰 **∧ `replace -l` 공집합** · (4) `GIT_REPLACE_REF_BASE` 재파생≠뷰 · (5) `--separate-git-dir`+grafts 재파생≠뷰 **∧ 리터럴 `.git/info/grafts` ABSENT** | — | ㉠ 이 4표면을 «하나의 술어»로 잡는다 | **일치 — 자기신고 확인 포함**(grafts 는 커밋 «객체»를 안 바꾸므로 `cat-file` 은 진짜 부모) |
| **1** | **[E10]-1** `replace --graft` (U-17 `D`·`P`) | v2.19-3 / 직전(㉡만) | **`PREVENTION_UNVERIFIABLE`** — ㉠ 불일치 1건 / **`PREVENTION_UNVERIFIABLE`**(㉡ `replace -l`) | 1/1 | 둘 다 차단 | **일치** |
| | **[E10]-2** `<git-dir>/info/grafts` | v2.19-3 / 직전 | **`UNVERIFIABLE`** — ㉠ 불일치 1건 · `replace -l` **공집합** / **`UNVERIFIABLE`**(㉡ grafts 항) | 1/1 | 자기신고 확인 | **일치** |
| | **[E10]-3** 제3 표면 `GIT_REPLACE_REF_BASE=refs/evil/` | v2.19-3 / 직전 | **`UNVERIFIABLE`** — ㉠ 불일치 1건 / **`UNVERIFIABLE`** | 1/1 | M-3 이 요구한 «제3 기제» 실증 | **일치** |
| | **[E10]-4** **㉡ 열거가 놓치는 표면** — `--separate-git-dir`+grafts | v2.19-3(㉠) / **㉡ 리터럴 대조군** | **`PREVENTION_UNVERIFIABLE`**(1) / **`PREVENTION_ACTIVE`**(**0**) | 1/**0** | ㉠ 이 «주» 판별임의 실증 | **일치 — 대조군이 «샌다»** |
| | **[E10]-5** 정상 회귀 | v2.19-3 | **`PREVENTION_ACTIVE`** · ㉠ 불일치 **0건** | **0** | replace 0·grafts 부재·shallow=false ⇒ 불변 | **일치** |
| **1** | **[E10]-U16-1** `c_APP` 축 | v2.19-3 | 진실 **`APPROVAL_MALFORMED`**(3, `|c_APP|=2`) → graft 후 **`PROVENANCE_UNVERIFIABLE`**(2, ㉠ 불일치 1건) | 1/1 | 4정의 중 `c_APP` | **일치** |
| | **[E10]-U16-2** `C_R` 축 (grafts) | v2.19-3 | **`PROVENANCE_UNVERIFIABLE`**(2) — ㉠ 불일치 1건 · `replace -l` 공집합 | 1 | 4정의 중 `C_R` | **일치** |
| | **[E10]-U16-3** `--separate-git-dir`+grafts | v2.19-3 / **㉡ 리터럴 대조군** | **`PROVENANCE_UNVERIFIABLE`**(2) / **`NO_ROWS_CLEAR`**(**0**) | 1/**0** | 같음 | **일치 — 대조군이 «샌다»** |
| | **[E10]-U16-4** ⑳ⓑ 얕은 클론 — 후보 우주 «안» | v2.19-3 / **순서 대조군** | **`PROVENANCE_UNVERIFIABLE`**(2) / **`APPROVAL_MALFORMED`**(3) | 1/1 | **2 vs 3 판별력 유지** | **일치** |
| | **[E10]-U16-5** 얕지만 후보 우주 «밖» | v2.19-3 / **「얕음=전역」 대조군** | **`NO_ROWS_CLEAR`**(**0**) / **`PROVENANCE_UNVERIFIABLE`**(2) | **0**/1 | ㉢ 국소 · 「전역」 문자 구현은 **실패** | **일치** |
| | **[E10]-U16-6** 정상 회귀 | v2.19-3 | ⑳ⓐ **`APPROVAL_MALFORMED`**(3) · ⑱ **`NO_ROWS_CLEAR`**(0) | 1/0 | 불변 | **일치** |
| **2** | **[E11]-1** `|P_first|=0` ∧ 아티팩트 **부재** | v2.19-3 (본 저장소 live) | **`PREVENTION_ABSENT`**(2) | 1 | 계약 문언 그대로 | **일치 (인증 실측)** |
| | **[E11]-2** `|P_first|=0` ∧ 아티팩트 **존재**(얕은 클론) | v2.19-3 | **`PREVENTION_UNVERIFIABLE`**(1) — ㉢ 경계 · `|P_first|=0` | 1 | E11 | **일치** |
| | **[E11]-3** `|P_first|=2` · 머지가 X 쪽 blob 으로 해소 | v2.19-3 | **`PREVENTION_ACTIVE`**(10) — `|P_first|=2 · |P_last|=1` | **0** | «∀x 술어 = ∃-증인» 결정적 · ¬LATE | **일치** |
| | **[E11]-3b** `|P_first|=2` 인데 둘 다 `d` 의 **자손** | v2.19-3 | **`PREVENTION_LATE`**(6) | 1 | 반대 방향 고정 | **일치** |
| **3** | **[E11] 상보성 4종** | v2.19-3 | ① 정상 **ACTIVE**(10) · ② 사후 편집 **MUTATED**(7) · ③ 다중 도입(`|P_last|=2`) **MUTATED**(7) · ④ 순서 위반 **LATE**(6) | 0/1/1/1 | ¬LATE 하 상보·결정적 | **전건 일치** |

**이 파일은 본 저장소의 `PREVENTION_ACTIVE` 를 주장하지 않는다** — 본 저장소 live 는 `PREVENTION_ABSENT`(§4-1 [E11]-1)이고 `ACTIVE` 는 전부 SIMULATED seam·픽스처다.

---

## 1. S-24 ① — `git diff ad5be1a3..f6493d23 -- <계약>` 전문 + 절 범위 diff 기계 증명

에라타 3차가 닿는 절(hunk **5개**): **H1** 심사 이력 v2.19 행(:118) · **H2** 변경 이력 v2.19 행(:201) · **H3** §12.3.3 (B) 처분표 머리(에라타 3차 서술 +6행) ·
**H4** `U-17 (c)` `P_first`/`P_last` 카디널리티(**E11** +10행) · **H5** `U-16-c` `[PARENTS-UNTRUSTED]` 판별 블록(**E10** — ①② 이중 판별을 ㉠㉡㉢ 로 재작성).
닿지 «않는» 절은 §1-3 ③ 이 리터럴 grep 으로 위치를 파생해 sha256 으로 대조한다 — **§12.3.4-R 하니스 블록 · §8 T-84/T-82/T-81 행 · (a) 술어 블록 전문 · (b) 리비전 특정 전문 · (α) 연속성 술어 전문 ·
C6 host 결속 · U-17-c 전순서 10단 · U-17-c 상태표 · U-17 (c) 두 상태의 «기계 조건» · U-17-d · [E8] 참조 1/4(`D`) · [E8] 참조 2/4(`C_R`) · U-16-c `c_APP` 수식 · U-16-d 전순서 12단 표 ·
U-16-d ① 선-검사 · ② g-단락 · U-16-a2 · U-16-h · U-16-b · U-15-g-4 CORR** — **22건 전부 ∅**.
**`D`·`C_R` 참조 자리가 ∅ 인 이유**: 3차는 «`[PARENTS-UNTRUSTED]`» 라는 **참조 문구를 바꾸지 않고 유일 소스의 «내용»만** 재작성했다 — 그래서 참조 4곳 중 D·C_R 은 무변경이고 `P` 자리만 E11 로 함께 바뀌었다(H4).

```diff
diff --git a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
index 22be5f33..2f9141f8 100644
--- a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+++ b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
@@ -115,7 +115,7 @@
 > | **v2.14** | **`needs-attention` · `NOT_PASSED`** — findings 5 (**high 3 / medium 2**), **전건 채택, 기각 0**. 직전 3건 처분: **#1 부분해소 / #2 부분해소 / #3 «회피» — 아크 최초의 회피 판정**. 잔여·신규 5건: **F1 정직 경계는 과장 철회일 뿐 해소 아님**(§11 이 `CLEAR` 를 완료 허용값으로 소비하는데 예방은 `Phase 1`) + **처분표 (B) 가 마감 전 초안 문구 그대로**(S-22 «7회차») · **F2 복수 D0A-FIRST**(카디널리티 가정) · **F3 digest 선배치**(토큰 도입만 추적) · **F4 «회피»**(append 복구가 조상성에 걸려 전체 계약에서 green 불가·부분 표면 실행기) · **F5 `row_ref` 의 `c_APP` 비단수**. 동결 `db19a0e8` → 증거 `c5359c74` → 에라타 후 재동결 `af61a40e`. `docs/reviews/phase0-completion-contract/20260819-002145/verdict.md` |
 > | **v2.15** | **재심 미도달 — 동결 후 stop-time BLOCK 3회로 재개정.** v2.14 판정 5건을 반영해 `11a56d3e` 로 동결·`b453b4e5` 로 실행 증거까지 기록했으나, **재결속 전에 stop-time 심판이 세 번 BLOCK** 을 내 v2.16(`eb2805a9`)→v2.17(`a3c95b4f`)→v2.18(`5f4b7cfd`)로 재개정됐다. **v2.15~v2.17 은 재결속 전이라 승인 표면을 가진 적이 없다**(v2.9→v2.10 선례). 재결속·레인 B 재심은 **v2.18 에서** 이뤄졌다 |
 > | **v2.18** | **`needs-attention` · `NOT_PASSED`** — findings 6 (**high 3 / medium 3**), **전건 채택, 기각 0**. 직전 5건 처분: **F1 부분해소 / F2 부분해소 / F3 해소됨(계약 수준) / F4 부분해소 / F5 «회피»** — **아크 누적 해소 5**(F3 = 다섯 번째). 신규 2건: **정본 host 미결속**(host 없는 `gh api` 조회 — `GH_HOST` override 로 타 host 응답이 `PREVENTION_ACTIVE` 가능·high) · **두 결속 계획 Phase 0/1 선행관계 충돌**(운영자 게이트·medium). 잔여 F1 은 «보호 off→머지→재활성» 창을 어느 술어도 소비 안 함 + 처분표 (B) 가 «완료 가능성 자체를 막는다»로 과대주장 · F2 는 D0A-FIRST 절이 `diff-filter=A` 규범 잔존 · F4 는 `T-82 ⑱` 입력이 폐지된 `edge_seq` 기재 · F5 는 `c_APP` 단수 정의 잔존. 동결 `5f4b7cfd` → 증거 `7a146466` → 에라타 재동결 `feb91d60` → S-24 addendum `540ff0e3` → 재결속 `81d532ff`. `docs/reviews/phase0-completion-contract/20260819-074621/verdict.md` |
-> | **v2.19** | **재심 미착수.** v2.18 판정 6건을 반영한 판이며, **동결(`d5a8302a`) → 증거(`90a5ce7d` — E1~E7 적발) → 에라타 재동결(`e3ed4e78`) → addendum(`197f4fe4` — [PARENTS-UNTRUSTED]/P 결함 E8~E9 적발) → 에라타 2차 정정 후 재동결**(재결속 전이므로·v2.15/v2.18 선례) → **운영자 재결속(현행 사이클)** 대기다. 재결속 전에는 심사를 요청하지 않는다(§12.3.2) |
+> | **v2.19** | **재심 미착수.** v2.18 판정 6건을 반영한 판이며, **동결(`d5a8302a`) → 증거(`90a5ce7d` — E1~E7 적발) → 에라타 재동결(`e3ed4e78`) → addendum(`197f4fe4` — E8~E9 적발) → 에라타 2차 재동결(`ad5be1a3`) → addendum 2차(`c83e44db` — E10~E11 문언 + M-3 적발) → 에라타 3차 정정 후 재동결**(재결속 전이므로·v2.15/v2.18 선례) → **운영자 재결속(현행 사이클)** 대기다. 재결속 전에는 심사를 요청하지 않는다(§12.3.2) |
 >
 > **[v2.7 갱신 — 6e 는 "고쳐졌다가 다시 만료되는" 축이다]** 아래 v2.1·v2.4 서술은
 > **당시 상태의 기록**이며 현행 상태가 아니다. **6e 를 "완료/미완료"의 1회성 축으로
@@ -198,7 +198,7 @@
 | v1.1 | §3.0 신설 — 해당 작업이 `acd45c43`에서 수행돼 `15d48f72`에서 팬텀 할당으로 revert된 이력 확인 |
 | v1.2 | 심판 10건 반영. §3.0 인용에 사실 오류(F-1), §6.3이 선행 구현 누락(F-5), §4.2가 없는 열 참조(F-3) |
 | v1.3 | 재심 8건 + **운영자 결정 2건** 반영. **F-2를 "회피"로 판정받아 30/30을 거버넌스 트랙으로 정식 이관**. Phase 0 범위를 기계 검사 가능 축으로 축소하고 **불가 축을 §13 레지스터로 명시 노출**. T-3c 공집합 결함 수정 |
-| **v2.19** | **v2.18 심판 판정 6건(high 3 / medium 3) 전건 반영. 직전 처분은 «F1·F2·F4 부분해소 · F3 해소됨(계약 수준) · F5 회피» 이고 신규 2는 host 미결속·두 결속 계획 충돌이다.** ① **#1 F1 (high) — 보호 해제 창**: 진입·완료 두 live 조회 사이 [보호 off→체크 통과→머지→재활성] 창을 **어느 술어도 소비 안 했고**, (B) 표가 «완료 가능성 자체를 막는다»고 **과대주장**했다. **과대주장 철회** + **연속성 소비자 신설**(완료 판정 시점 — 적용 룰셋 `created_at`/`updated_at` > `t_land`[= D 착지 PR 의 서버 `merged_at` 최소]이면 `PREVENTION_CONTINUITY_UNVERIFIABLE`·운영자 재심사 · classic-only[타임스탬프 부재]도 판정 불가로 차단 · 삭제-재생성은 새 id·created_at 로 검출). **극성**: 관측만 하고 통과시키면 창이 정상 완료로 세탁되고 무조건 영구 차단하면 정당한 강화를 막는다 — **판정 불가를 «판정 불가»로 보고**하는 것이 fail-closed(F2 동형). **서버 시간만 소비**(커밋 시각 불신). **정직 경계**: «룰셋 미변경» 우회(연속 bypass_actors·admin override)는 감사 로그 소관이라 **못 닫는다** — «부분해소»이지 «닫힌다»가 아니다. T-84 ⑪(off→merge→on 은 서버 설정 변경 요구 → SIMULATED seam·live 는 현행 음성만) ② **#2 host 미결속 (high, 신규)**: 모든 `gh api repos/{owner}/{repo}/…` 가 host 없이 나가 `GH_HOST` 를 바꾸면 **타 host `/api/v3` 응답으로 `PREVENTION_ACTIVE` 위조** 가능(심판 실측 프로브). **host 를 계약 핀에서 파생해 «명령에 명시»**(`gh api --hostname <핀 host>`) + **소비자 자기 환경 `GH_HOST` 재핀**(플래그·환경 이중 결속 — 우선순위 의존 안 함) + `gh auth status --hostname <핀 host>` 전제. **극성**: 도달 불가 = `PREVENTION_UNVERIFIABLE`(타 host 폴백 없음). 아티팩트 선언 아님(C3 규율). T-84 ⑫(GET-only·live) ③ **#3 F2 (high) — D0A-FIRST 규범 잔존**: 앞선 D0A-FIRST 절이 «모호 없이 한 커밋»·`git log --diff-filter=A` 를 **판정 규범**으로 유지해(S-22) 구조 `D`(U-15-g-1)와 병존했다. **판정 소비 자리를 구조 `D` 참조로 전환**하고 «다중 후보 문제가 여기서 발생 안 함» 단정을 **철회**(gg/gu/uu 로 `D` 크기>1). **편의 표기(∅ 확인·단일 픽스처)와 판정 소비를 구별해 명시** — §12.3.4-G 의 `diff-filter=A` 는 편의 표기로만. 재기술→참조로 stale 클래스 제거(S-14) ④ **#4 F4 (medium) — T-82 ⑱ 입력 stale + 계약 밖 규칙**: ⑱ 이 **폐지된 `edge_seq` 기재**(«각각 seq=1 부여»)를 지시했고 손 실행기가 «사전순 최소·상태 우선순위»를 **자체 선언**했다(`U16-LEDGER-CHECK.md:34-48`). **⑱ 을 현행 스키마로 재기술**(edge_seq 미기재·소비자 표시용 파생) + **U-16-d 상태 전순서·규칙 평가 순서를 계약 리터럴로 고정**(전순서 12단·«전부 평가 후 최소» 의미 — 자체 선언 흡수) ⑤ **#5 F5 (medium, 회피) — 단수 `c_APP`**: `row_ref` 만 없앴고 같은 비단수 `c_APP` 가 U-16-c·g5·g6 에 단수로 잔존했다(형제 동일 행 독립 도입 시 선택 재량). **`c_APP` 를 구조 집합 정의**(`D`·`C_R` 동형: `{x⊑HEAD : a∈rows(x:LEDGER) ∧ ∀p∈parents(x): a∉rows(p:LEDGER)}`)·`c_APP` 크기 0→`PROVENANCE_UNVERIFIABLE`·크기>1→`APPROVAL_MALFORMED`·크기 1→유일 원소·세 소비처 일관. **극성**: 동일 승인 행 병렬 도입은 «언제 승인»이 유일하지 않아 차단(U-15-g-2 동형)·«사전순 최소»는 판정 불가를 답한 척한다. T-82 ⑳(형제 동일 행→MALFORMED)·⑱(서로 다른 행→green) 상호 배타 ⑥ **#6 두 결속 계획 충돌 (medium, 운영자 게이트)**: 개발계획 Phase 1 작업 7·종료조건(required CI·branch protection 증거) vs 계약 U-17 D0-A 착수 선행조건. **계약이 «함께 착수 불가» 정직 표기** + §12.3.3 (D) 에 **적용 준비된 개정안 문안**(tos-gate 도입을 Phase 0 로 이관·Phase 1 종료조건은 «U-17 연속성 유지»로 — verbatim diff). **개발계획 자체는 무편집** — 정식 개정은 운영자 소관(`bound_paths`·O-6 재결속 시 함께 심사). **종수 전파(S-20)**: T-84 10→**12종**(⑪·⑫) · T-82 19→**20종**(⑳) · T-81 19 불변 · U-17-c 9값→**10값/차단 9/전순서 10단** · U-16-d **전순서 12단 신설**. **§12.3.3 (A)=v2.18 판정 5건 처분·(B)=v2.19 6건 주장(«어느 것도 해소 아님»)·(B) 실행 증거 열 현행화**(직전 `20260819-002145` 증거 명시·신규는 «동결 후 실행»). **S-22 스윕**: 처분표 (A)(B)·§0 요약·심사 이력·변경 이력·§11·D0A-FIRST 절 전파. **[독립 검증 마감(실행 픽스처) 3건]**: (i) **S-22 재발 1건 정정** — U-16-b 의 v2.15 산문 «[F5 소멸] `c_APP` 비단수도 함께 소멸»이 v2.19 구조 정의(단수 잔존→처분)와 모순 → `row_ref`·tombstone 축만 소멸로 정정 (ii) **U-16-d 규칙 평가 순서 동치 주장 정정** — 「전 규칙 상태번호 비감소」는 거짓(구조 상태 2 `c_APP` 크기 0 < 3 MALFORMED)이라 **구조 선-검사 1·2·4 를 g-규칙 앞 필수 단계로 재배치**하고 동치는 g-단락 5~11 로 한정 · **T-82 ⑳ⓑ**(발산 corner·종수 불변) 신설 (iii) **target_branch 파생의 host 없는 `gh api` 잔재 → C6 참조 전환**(S-14). **[v2.19 에라타 (동결 `d5a8302a` 후 증거 실행 `90a5ce7d` 적발 — 재결속 전이므로 정정 후 재동결·v2.15/v2.18 선례)]** 증거가 계약 결함 후보 7건을 적발했다(실행기는 계약대로 발화했으나 계약 «문언»이 死분기·공백·실행기 독해와 갈린 자리): **ⓐ E1 (U-17 실질)** classic disjunct 死분기 — `D≠∅` 이면 classic-only 는 (a) 통과해도 연속성(룰셋 타임스탬프 의존)이 항상 9 발화 → «classic 은 진입 가능·완료 불가, 완료 인정 경로는 룰셋»을 (a) 옆에 정직 명시(disjunct 철회 아님·fail-closed terminal)·양성 대조군 룰셋 기반 · **ⓑ E2 (U-17 공백)** `t_land` 파생 불가 시 (α) 처분 미정의 → `CONTINUITY_UNVERIFIABLE`(fail-closed·(b) 8 이 전순서상 이겨 방출 불변이나 정의는 닫음)·타임스탬프 파싱 불가도 명시 · **ⓒ E3 (U-17 관측/문언)** gh 2.93.0 실측 `--hostname` 이 `GH_HOST` 를 이김 → 「의존하지 않는 이중결속」을 「플래그 우선 실측·재핀은 방어적 중복」으로 정정 · `responder=file:` auth 전제 «기록만» · 아티팩트 `host` 키 «선택»(v2.18 E2 동형) · 타 host ACTIVE 위조는 GET-only 라 직접 실증 불가 = ⑫ 는 「상태 불변+nohost→UNVERIFIABLE」로만 검증(정직 경계) · **ⓓ E4 (U-16 실질)** T-82 ⑱ 리터럴 «별개 `row_id`» 가 g2·간선 대응과 충돌(리터럴 픽스처는 MALFORMED/1 = 정반대) → «같은 `row_id`, 서로 다른 승인 행(transition·근거 다름)»으로 정정(S-22: 정정을 적는 것과 전파는 별개) · **ⓔ E5 (U-16 실질)** `c_APP` 정의가 «진짜 루트»와 «얕은 클론 경계(부모 미상)»를 미구별 → 리터럴 파생에서 경계커밋이 루트로 읽혀 `c_APP` 크기 1(fail-open) → **[PARENTS-UNTRUSTED] 단서 신설**(1차 신설명 [SHALLOW]; 경계 = 부모 미상 → 도입 지점 확정 안 함 → `PROVENANCE_UNVERIFIABLE`)·**동형 정의 전수 적용**(`C_R`·`D`·`P_first`/`P_last` 가 [PARENTS-UNTRUSTED] 참조·플래그 의존 클래스 동형 규율) · **ⓕ E6 (U-16 공백)** 선-검사 2 「얕은 클론」을 전역 단축으로 읽으면 ⑳ⓑ 대조군 구별력 상실 → 「경계 커밋이 해당 행/간선 도입 후보 우주에 있어 크기 0일 때」로 국소화 · **ⓖ E7 (U-16 공백)** 한 간선 다수 후보 상태 귀속(=대응 후보 전순서 최소·D-4)·「고아」 구조 정의(=같은 row_id∧g1 일치 간선 0·규칙 탈락 행은 그 규칙 상태 귀속·D-5, `ORDER_INVALID`→`MALFORMED` 오귀속 방지) 고정. **증거 결속(S-24)**: 이 에라타 재동결에 대해 **addendum 으로 이행**(절 범위 `git diff` 공집합 증명 + 영향 변이 재실행 — §5 산출 목록). **종수 불변**(E1~E7 은 문언 정정·⑳ⓑ 는 기존 하위 케이스). **[v2.19 에라타 2차 (재동결 `e3ed4e78` 후 S-24 addendum `197f4fe4` 적발 — 재결속 전이므로 정정 후 재동결)]** addendum 이 [SHALLOW] 자체의 결함 2건을 적발했다: **ⓗ E8 (U-16 실질·fail-open)** `git replace --graft`(및 `.git/info/grafts`)가 [SHALLOW] 리터럴 3판별(`--is-shallow-repository=false`·`.git/shallow` 부재·부모 객체 present)을 **전부 통과**하면서 `git log --format=%P`·`rev-list`·`merge-base` 등 replace 를 따르는 명령이 «가짜» 부모를 반환 → 같은 seam 에서 `PREVENTION_LATE`(6)→`PREVENTION_ACTIVE`(10) 극성 전환 실측(`GIT_NO_REPLACE_OBJECTS=1` 에서는 진짜 부모). [SHALLOW] 가 닫으려던 클래스는 «부모 집합 신뢰 불가»이고 얕은 클론은 한 사례 → **[SHALLOW]→[PARENTS-UNTRUSTED] 일반화·개명**(부모 «재작성» 축 추가) + **이중 판별**(① 관측: `git replace -l` 공집합 ∧ `.git/info/grafts` 부재 ∧ 얕은 클론 아님 → 위반 시 `PROVENANCE_UNVERIFIABLE`/`PREVENTION_UNVERIFIABLE` · ② 무력화: 조상·부모 파생 `git` 전부 `--no-replace-objects` 고정) · 극성 = «부모 신뢰 불가면 도입 지점 확정 불가 → 판정 불가를 판정 불가로»(E5 동형·fail-closed) · 유일 소스(U-16-c)에서만 고치고 동형 4곳(`D`·`C_R`·`c_APP`·`P_first`/`P_last`)은 참조(재기술 금지). **개명 스윕(S-22)**: 활성 태그 8곳 개명·역사 참조 2곳(정의 헤더 «구 [SHALLOW]»·ⓔ «1차 신설명 [SHALLOW]») 보존 · **ⓘ E9 (U-17 문언 공백·극성)** `P_last`(및 `P_first`) 의 다부모 의미 미규정 — 실행기가 ∨(«어느 한 부모와라도 다름»)로 읽어 2-부모 graft 에서 `ARTIFACT_MUTATED`(7)↔`ACTIVE`(10) 극성 분기. `c_APP`·`C_R`·`D` 는 ∀-부모인데 P 만 비대칭(S-22 계열) → **P_first/P_last 를 D·C_R·c_APP 와 ∀-부모 «동형 구조 정의»로 고정**(도입지점(b) = ∀부모에 blob≠b 인 x · P_last = 현행 blob 도입 집합 · P_last 크기 0→UNVERIFIABLE·>1→ARTIFACT_MUTATED[c_APP 크기>1 동형·보수]·1→유일 원소) · 머지는 «∀부모 다름»일 때만 도입(한 부모와 같으면 도입 아님) · 상태 조건(LATE/MUTATED/ACTIVE)을 집합 위에서 결정적으로 재정의(ACTIVE·MUTATED 는 ¬LATE 하 상보·`T-84 ⑨` 도달 유지). **N-3~5(관측·비차단)**: «전순서 최소»가 규칙 간·후보 간·전역 3층에서 같은 규칙임을 U-16-d 에 한 줄 명시. **증거 결속(S-24)**: 이 2차 에라타 재동결도 **addendum 2차로 이행**(절 범위 `git diff` 공집합 + 영향 변이 재실행). **종수 불변**(E8~E9 은 문언 정정·개명·동형화). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`)·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
+| **v2.19** | **v2.18 심판 판정 6건(high 3 / medium 3) 전건 반영. 직전 처분은 «F1·F2·F4 부분해소 · F3 해소됨(계약 수준) · F5 회피» 이고 신규 2는 host 미결속·두 결속 계획 충돌이다.** ① **#1 F1 (high) — 보호 해제 창**: 진입·완료 두 live 조회 사이 [보호 off→체크 통과→머지→재활성] 창을 **어느 술어도 소비 안 했고**, (B) 표가 «완료 가능성 자체를 막는다»고 **과대주장**했다. **과대주장 철회** + **연속성 소비자 신설**(완료 판정 시점 — 적용 룰셋 `created_at`/`updated_at` > `t_land`[= D 착지 PR 의 서버 `merged_at` 최소]이면 `PREVENTION_CONTINUITY_UNVERIFIABLE`·운영자 재심사 · classic-only[타임스탬프 부재]도 판정 불가로 차단 · 삭제-재생성은 새 id·created_at 로 검출). **극성**: 관측만 하고 통과시키면 창이 정상 완료로 세탁되고 무조건 영구 차단하면 정당한 강화를 막는다 — **판정 불가를 «판정 불가»로 보고**하는 것이 fail-closed(F2 동형). **서버 시간만 소비**(커밋 시각 불신). **정직 경계**: «룰셋 미변경» 우회(연속 bypass_actors·admin override)는 감사 로그 소관이라 **못 닫는다** — «부분해소»이지 «닫힌다»가 아니다. T-84 ⑪(off→merge→on 은 서버 설정 변경 요구 → SIMULATED seam·live 는 현행 음성만) ② **#2 host 미결속 (high, 신규)**: 모든 `gh api repos/{owner}/{repo}/…` 가 host 없이 나가 `GH_HOST` 를 바꾸면 **타 host `/api/v3` 응답으로 `PREVENTION_ACTIVE` 위조** 가능(심판 실측 프로브). **host 를 계약 핀에서 파생해 «명령에 명시»**(`gh api --hostname <핀 host>`) + **소비자 자기 환경 `GH_HOST` 재핀**(플래그·환경 이중 결속 — 우선순위 의존 안 함) + `gh auth status --hostname <핀 host>` 전제. **극성**: 도달 불가 = `PREVENTION_UNVERIFIABLE`(타 host 폴백 없음). 아티팩트 선언 아님(C3 규율). T-84 ⑫(GET-only·live) ③ **#3 F2 (high) — D0A-FIRST 규범 잔존**: 앞선 D0A-FIRST 절이 «모호 없이 한 커밋»·`git log --diff-filter=A` 를 **판정 규범**으로 유지해(S-22) 구조 `D`(U-15-g-1)와 병존했다. **판정 소비 자리를 구조 `D` 참조로 전환**하고 «다중 후보 문제가 여기서 발생 안 함» 단정을 **철회**(gg/gu/uu 로 `D` 크기>1). **편의 표기(∅ 확인·단일 픽스처)와 판정 소비를 구별해 명시** — §12.3.4-G 의 `diff-filter=A` 는 편의 표기로만. 재기술→참조로 stale 클래스 제거(S-14) ④ **#4 F4 (medium) — T-82 ⑱ 입력 stale + 계약 밖 규칙**: ⑱ 이 **폐지된 `edge_seq` 기재**(«각각 seq=1 부여»)를 지시했고 손 실행기가 «사전순 최소·상태 우선순위»를 **자체 선언**했다(`U16-LEDGER-CHECK.md:34-48`). **⑱ 을 현행 스키마로 재기술**(edge_seq 미기재·소비자 표시용 파생) + **U-16-d 상태 전순서·규칙 평가 순서를 계약 리터럴로 고정**(전순서 12단·«전부 평가 후 최소» 의미 — 자체 선언 흡수) ⑤ **#5 F5 (medium, 회피) — 단수 `c_APP`**: `row_ref` 만 없앴고 같은 비단수 `c_APP` 가 U-16-c·g5·g6 에 단수로 잔존했다(형제 동일 행 독립 도입 시 선택 재량). **`c_APP` 를 구조 집합 정의**(`D`·`C_R` 동형: `{x⊑HEAD : a∈rows(x:LEDGER) ∧ ∀p∈parents(x): a∉rows(p:LEDGER)}`)·`c_APP` 크기 0→`PROVENANCE_UNVERIFIABLE`·크기>1→`APPROVAL_MALFORMED`·크기 1→유일 원소·세 소비처 일관. **극성**: 동일 승인 행 병렬 도입은 «언제 승인»이 유일하지 않아 차단(U-15-g-2 동형)·«사전순 최소»는 판정 불가를 답한 척한다. T-82 ⑳(형제 동일 행→MALFORMED)·⑱(서로 다른 행→green) 상호 배타 ⑥ **#6 두 결속 계획 충돌 (medium, 운영자 게이트)**: 개발계획 Phase 1 작업 7·종료조건(required CI·branch protection 증거) vs 계약 U-17 D0-A 착수 선행조건. **계약이 «함께 착수 불가» 정직 표기** + §12.3.3 (D) 에 **적용 준비된 개정안 문안**(tos-gate 도입을 Phase 0 로 이관·Phase 1 종료조건은 «U-17 연속성 유지»로 — verbatim diff). **개발계획 자체는 무편집** — 정식 개정은 운영자 소관(`bound_paths`·O-6 재결속 시 함께 심사). **종수 전파(S-20)**: T-84 10→**12종**(⑪·⑫) · T-82 19→**20종**(⑳) · T-81 19 불변 · U-17-c 9값→**10값/차단 9/전순서 10단** · U-16-d **전순서 12단 신설**. **§12.3.3 (A)=v2.18 판정 5건 처분·(B)=v2.19 6건 주장(«어느 것도 해소 아님»)·(B) 실행 증거 열 현행화**(직전 `20260819-002145` 증거 명시·신규는 «동결 후 실행»). **S-22 스윕**: 처분표 (A)(B)·§0 요약·심사 이력·변경 이력·§11·D0A-FIRST 절 전파. **[독립 검증 마감(실행 픽스처) 3건]**: (i) **S-22 재발 1건 정정** — U-16-b 의 v2.15 산문 «[F5 소멸] `c_APP` 비단수도 함께 소멸»이 v2.19 구조 정의(단수 잔존→처분)와 모순 → `row_ref`·tombstone 축만 소멸로 정정 (ii) **U-16-d 규칙 평가 순서 동치 주장 정정** — 「전 규칙 상태번호 비감소」는 거짓(구조 상태 2 `c_APP` 크기 0 < 3 MALFORMED)이라 **구조 선-검사 1·2·4 를 g-규칙 앞 필수 단계로 재배치**하고 동치는 g-단락 5~11 로 한정 · **T-82 ⑳ⓑ**(발산 corner·종수 불변) 신설 (iii) **target_branch 파생의 host 없는 `gh api` 잔재 → C6 참조 전환**(S-14). **[v2.19 에라타 (동결 `d5a8302a` 후 증거 실행 `90a5ce7d` 적발 — 재결속 전이므로 정정 후 재동결·v2.15/v2.18 선례)]** 증거가 계약 결함 후보 7건을 적발했다(실행기는 계약대로 발화했으나 계약 «문언»이 死분기·공백·실행기 독해와 갈린 자리): **ⓐ E1 (U-17 실질)** classic disjunct 死분기 — `D≠∅` 이면 classic-only 는 (a) 통과해도 연속성(룰셋 타임스탬프 의존)이 항상 9 발화 → «classic 은 진입 가능·완료 불가, 완료 인정 경로는 룰셋»을 (a) 옆에 정직 명시(disjunct 철회 아님·fail-closed terminal)·양성 대조군 룰셋 기반 · **ⓑ E2 (U-17 공백)** `t_land` 파생 불가 시 (α) 처분 미정의 → `CONTINUITY_UNVERIFIABLE`(fail-closed·(b) 8 이 전순서상 이겨 방출 불변이나 정의는 닫음)·타임스탬프 파싱 불가도 명시 · **ⓒ E3 (U-17 관측/문언)** gh 2.93.0 실측 `--hostname` 이 `GH_HOST` 를 이김 → 「의존하지 않는 이중결속」을 「플래그 우선 실측·재핀은 방어적 중복」으로 정정 · `responder=file:` auth 전제 «기록만» · 아티팩트 `host` 키 «선택»(v2.18 E2 동형) · 타 host ACTIVE 위조는 GET-only 라 직접 실증 불가 = ⑫ 는 「상태 불변+nohost→UNVERIFIABLE」로만 검증(정직 경계) · **ⓓ E4 (U-16 실질)** T-82 ⑱ 리터럴 «별개 `row_id`» 가 g2·간선 대응과 충돌(리터럴 픽스처는 MALFORMED/1 = 정반대) → «같은 `row_id`, 서로 다른 승인 행(transition·근거 다름)»으로 정정(S-22: 정정을 적는 것과 전파는 별개) · **ⓔ E5 (U-16 실질)** `c_APP` 정의가 «진짜 루트»와 «얕은 클론 경계(부모 미상)»를 미구별 → 리터럴 파생에서 경계커밋이 루트로 읽혀 `c_APP` 크기 1(fail-open) → **[PARENTS-UNTRUSTED] 단서 신설**(1차 신설명 [SHALLOW]; 경계 = 부모 미상 → 도입 지점 확정 안 함 → `PROVENANCE_UNVERIFIABLE`)·**동형 정의 전수 적용**(`C_R`·`D`·`P_first`/`P_last` 가 [PARENTS-UNTRUSTED] 참조·플래그 의존 클래스 동형 규율) · **ⓕ E6 (U-16 공백)** 선-검사 2 「얕은 클론」을 전역 단축으로 읽으면 ⑳ⓑ 대조군 구별력 상실 → 「경계 커밋이 해당 행/간선 도입 후보 우주에 있어 크기 0일 때」로 국소화 · **ⓖ E7 (U-16 공백)** 한 간선 다수 후보 상태 귀속(=대응 후보 전순서 최소·D-4)·「고아」 구조 정의(=같은 row_id∧g1 일치 간선 0·규칙 탈락 행은 그 규칙 상태 귀속·D-5, `ORDER_INVALID`→`MALFORMED` 오귀속 방지) 고정. **증거 결속(S-24)**: 이 에라타 재동결에 대해 **addendum 으로 이행**(절 범위 `git diff` 공집합 증명 + 영향 변이 재실행 — §5 산출 목록). **종수 불변**(E1~E7 은 문언 정정·⑳ⓑ 는 기존 하위 케이스). **[v2.19 에라타 2차 (재동결 `e3ed4e78` 후 S-24 addendum `197f4fe4` 적발 — 재결속 전이므로 정정 후 재동결)]** addendum 이 [SHALLOW] 자체의 결함 2건을 적발했다: **ⓗ E8 (U-16 실질·fail-open)** `git replace --graft`(및 `.git/info/grafts`)가 [SHALLOW] 리터럴 3판별(`--is-shallow-repository=false`·`.git/shallow` 부재·부모 객체 present)을 **전부 통과**하면서 `git log --format=%P`·`rev-list`·`merge-base` 등 replace 를 따르는 명령이 «가짜» 부모를 반환 → 같은 seam 에서 `PREVENTION_LATE`(6)→`PREVENTION_ACTIVE`(10) 극성 전환 실측(`GIT_NO_REPLACE_OBJECTS=1` 에서는 진짜 부모). [SHALLOW] 가 닫으려던 클래스는 «부모 집합 신뢰 불가»이고 얕은 클론은 한 사례 → **[SHALLOW]→[PARENTS-UNTRUSTED] 일반화·개명**(부모 «재작성» 축 추가) + **이중 판별**(① 관측: `git replace -l` 공집합 ∧ `.git/info/grafts` 부재 ∧ 얕은 클론 아님 → 위반 시 `PROVENANCE_UNVERIFIABLE`/`PREVENTION_UNVERIFIABLE` · ② 무력화: 조상·부모 파생 `git` 전부 `--no-replace-objects` 고정) · 극성 = «부모 신뢰 불가면 도입 지점 확정 불가 → 판정 불가를 판정 불가로»(E5 동형·fail-closed) · 유일 소스(U-16-c)에서만 고치고 동형 4곳(`D`·`C_R`·`c_APP`·`P_first`/`P_last`)은 참조(재기술 금지). **개명 스윕(S-22)**: 활성 태그 8곳 개명·역사 참조 2곳(정의 헤더 «구 [SHALLOW]»·ⓔ «1차 신설명 [SHALLOW]») 보존 · **ⓘ E9 (U-17 문언 공백·극성)** `P_last`(및 `P_first`) 의 다부모 의미 미규정 — 실행기가 ∨(«어느 한 부모와라도 다름»)로 읽어 2-부모 graft 에서 `ARTIFACT_MUTATED`(7)↔`ACTIVE`(10) 극성 분기. `c_APP`·`C_R`·`D` 는 ∀-부모인데 P 만 비대칭(S-22 계열) → **P_first/P_last 를 D·C_R·c_APP 와 ∀-부모 «동형 구조 정의»로 고정**(도입지점(b) = ∀부모에 blob≠b 인 x · P_last = 현행 blob 도입 집합 · P_last 크기 0→UNVERIFIABLE·>1→ARTIFACT_MUTATED[c_APP 크기>1 동형·보수]·1→유일 원소) · 머지는 «∀부모 다름»일 때만 도입(한 부모와 같으면 도입 아님) · 상태 조건(LATE/MUTATED/ACTIVE)을 집합 위에서 결정적으로 재정의(ACTIVE·MUTATED 는 ¬LATE 하 상보·`T-84 ⑨` 도달 유지). **N-3~5(관측·비차단)**: «전순서 최소»가 규칙 간·후보 간·전역 3층에서 같은 규칙임을 U-16-d 에 한 줄 명시. **증거 결속(S-24)**: 이 2차 에라타 재동결도 **addendum 2차로 이행**(절 범위 `git diff` 공집합 + 영향 변이 재실행). **종수 불변**(E8~E9 은 문언 정정·개명·동형화). **[v2.19 에라타 3차 (재동결 `ad5be1a3` 후 S-24 addendum 2차 `c83e44db` 적발 — 재결속 전이므로 정정 후 재동결·국소 문언)]** addendum 2차가 문언 결함 2건 + 강력 권고 1건을 냈다: **ⓙ E10 (M-1 문언 충돌·판별력 직결) + M-3 채택** — E8① 관측의 «얕은 클론 아님»(전역)이 E6 «국소 판정»과 충돌해 문자대로면 `T-82 ⑳ⓑ` 2 vs 3 판별력이 붕괴(얕은 클론이 후보 우주 무관 무조건 차단). **M-3(부모 집합 독립 재파생)을 채택해 함께 처분**: [PARENTS-UNTRUSTED] 판별을 **㉠ 주 판별 = 구조 재파생**(`git --no-replace-objects cat-file commit <x>` 의 `parent` 줄 직접 파싱 ↔ `%P`/rev-list 대조·불일치 → UNVERIFIABLE — 열거의 열린-세계[N-1 클래스]를 구조로 닫음·«구조 파생 > 열거» S-6) · **㉡ 전역 관측**(replace -l 공집합 ∧ grafts 부재 — per-commit 특정 불가라 전역·M-2 무간섭 실측) · **㉢ 국소 축**(cat-file 부모 객체 조회 실패 = 얕은 경계·`.git/shallow` 로 특정 → «그 후보만» 국소 차단)로 재작성. **전역/국소 분할 근거**: per-commit 판별 가능성(얕음은 `.git/shallow` 로 특정 가능=국소, replace/grafts 는 불가=전역)이 «판정 불가를 판정 불가로»와 «과잉 차단 회피»를 동시에 만족 · **ⓚ E11 (M-5 공백)** E9 로 `P_first` 가 집합이 됐는데 카디널리티 처분 부재(P_first 크기 0 → `∀x∈∅` 공허참 → LATE 발화이나 문언 자리 없음·크기 2 실측) → **P_first 카디널리티 명시**(D 동형): P_first 크기 0 → 아티팩트 부재면 `PREVENTION_ABSENT`(전순서 2·live 실측)/현행 존재하나 도입 지점 ∅ 이면 `[PARENTS-UNTRUSTED]`→`UNVERIFIABLE` · `>1` → LATE 술어를 `∀x∈P_first` 로 그대로(∃-증인이라 다중 결정적·신규 상태 불요) · `=1` 정상 · 전순서상 ABSENT(2)/UNVERIFIABLE(1)가 LATE(6)보다 먼저라 상보성 유지. **M-2/M-4 는 관측(결함 아님)** — M-2(두 limb 무간섭)는 ㉡ 에 한 줄 반영, M-4(graft 새 객체 --all 가시)는 약한 표면이라 미채택. **증거 결속(S-24)**: 이 3차 에라타도 addendum 3차로 이행. **종수 불변**(E10~E11 은 국소 문언·M-3 은 판별 재구조화). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`)·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
 | **v2.18** | **stop-time Codex BLOCK #3 5건 반영 — «v2.17 은 여전히 wrong-target·forged-gate 를 ACTIVE 로 승인한다».** ① **C1 (a) 가 required check «정체성»을 안 봤다** — `contexts` 의 **이름만** 검사해 **`tos-gate` 를 제3자 앱에 고정하면 (a) 통과**했고 `D=∅` 이면 (b) 가 생략돼 그대로 진입 승인(심판이 실행기 술어로 `prot_ok=True` 재현). → **`required_status_checks.checks[]` 의 그 컨텍스트 `app_id` == Actions app id**(룰셋은 `integration_id`) ② **C2 `app.id` 는 정본 워크플로를 식별하지 않는다** — **모든 Actions 잡이 같은 app id 를 갖고 한 suite 를 공유**한다(실측 PR #636 head 5 run 전부 동일). → **`gate_app_id` 파라미터 «폐지»**하고 `gh api apps/github-actions .id` 로 **서버 파생**(전역 상수를 아티팩트가 선언하면 그것이 위조 표면) + **워크플로 정체성 3중 결속**(run `path` == 계약 리터럴 `.github/workflows/tos-gate.yml` ∧ run `head_sha` == PR head ∧ **그 시점 워크플로 blob 이 하니스 호출·sha256 검증 스텝 포함**). **한계 정직 표기**: 3중은 **위조 비용을 올리지 «닫지» 않는다** — «서버가 그 파일 내용을 그대로 실행했다»는 공개 REST 로 증명 불가 ③ **C3 대상 결속 자기선택** — `remote_name` 을 **같은 아티팩트가 골랐고** 정규화가 **host 를 버려** 비-GitHub 동일 경로가 같은 값이 됐다. → **정본 host+owner/repo 를 계약 자체에 핀**(`github.com/kakao-harris-lee/kis_unified_sts` — `bound_paths` 안이라 **리뷰·재결속으로 보호**되고 **아티팩트는 선언하지 않는다**) · 정규화 **host 보존** · `git remote` 는 파생이 아니라 **«핀과 일치하는 원격이 존재하는가»의 대조**(원격 «이름»은 묻지 않는다) ⇒ **`remote_name` 폐지** ④ **C4 아티팩트 사후 편집** — 파라미터·countersign 은 HEAD 에서 읽으면서 순서는 **«최초 도입 P»** 만 봐 **P → 착수 → 편집**이 통과했다. → **`P_last`**(마지막 변경 커밋·구조 파생)로 바꾸고 `∀d∈D: P_last ⊰ d` ∧ 소비 blob == `P_last` 시점 blob. 위반 = **`PREVENTION_ARTIFACT_MUTATED`**(신설). **`LATE` 로 접지 않는 근거**: «순서가 늦다»는 순서를 고치면 되고 «착수 후 고쳤다»는 **그 편집이 무엇을 바꿨는지 재심사**해야 한다 ⑤ **C5 증거 결속** — v2.17 증거가 동결 `a3c95b4f` 에 결속됐는데 에라타 `75474351` 이 계약을 바꿔 **증거가 «이전 계약»을 검증한 상태**로 남았다. → **`S-24` 신설**(에라타 후 **재실행** 또는 **`git diff <freeze>..<errata>` 가 해당 절 범위에서 공집합임을 기계 증명**). **이번 판의 증거는 v2.18 «최종 동결 후»에 만든다**. **[v2.18 에라타 (동결 `5f4b7cfd` 후 증거 실행 `7a146466` 적발 — T-84 ①~⑩ 전건 기대 일치·S-24 결속 수록)]** ⓐ **E1 (실질)** — (b) ③ 의 워크플로 blob 검증이 **로컬 `git show <PR head>:…`** 를 전제해, squash·rebase 착지에서 **판정 저장소가 PR head 커밋을 보유하지 않으면**(실측: PR #636 head `7656259d` 로컬 미보유) **정직한 착지도 항상 red** 였다 → **`gh api repos/{pin}/contents/…?ref=<PR head.sha>`(서버 조회·base64 decode 후 두 리터럴 grep)** 로 전환, 404/HTTP → `UNVERIFIED_REVISION` · 네트워크/인증 → `UNVERIFIABLE`. **진실 원천이 서버라는 U-17 원칙과 정합**하며 로컬 `git show` 는 **보조 대조(선택)** ⓑ **E2 (문언 충돌)** — «아티팩트는 `canonical_target` 을 선언하지 않는다»(C3)와 §8 ⑤ 의 «선언 불일치 = MISMATCH» 가 충돌해 보였다 → **아티팩트의 `owner_repo`·`target_branch` 키는 «선택»**(있으면 대조·불일치 = MISMATCH / 없으면 핀·`default_branch` 가 유일 소스)으로 고정. **극성 서술**: 선택으로 둬도 약해지지 않는다 — 두 경우 모두 조회 대상은 핀이고 선언은 **추가 대조**일 뿐 대상을 «고를» 수 없다 ⓒ **E3** — 핀 일치 원격 «존재» 대조가 **비-핀 원격 공존을 허용**함은 **의도**임을 명시(«원격 이름·개수는 묻지 않는다 — 조회 대상은 핀이지 원격이 아니다»·포크/미러를 두는 정상 작업을 막지 않는다). **상태 8값 → 9값 / 차단 8 / 전순서 9단 · T-84 6종 → 10종**(⑦ 타 앱 고정 · ⑧ same-app wrong-workflow · ⑨ 아티팩트 사후 편집 · ⑩ 타 원격·타 호스트). **하니스 byte-identical·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
 | **v2.17** | **stop-time Codex BLOCK 3건 반영 — «U-17 이 잘못된 보호 대상과 비강제 체크를 ACTIVE 로 승인할 수 있다».** v2.16 은 **재결속 전이라 승인 표면을 가진 적이 없다.** ① **B1 — 대상 미결속**: `owner_repo`·`target_branch` 를 **아티팩트 선언값 그대로** 쓰고 실행기가 **형식만** 검사해, 실제 `origin`·정본 착지 브랜치와 결속되지 않았고 **`D = ∅` 이면 «임의 대상의 보호»만으로 진입 승인**됐다. 교정: `owner_repo` 는 **`git remote get-url origin` 파생**(원격 이름은 파라미터·기본 `origin`), `target_branch` 는 **`gh api repos/{o}/{r}` 의 `.default_branch`** 파생 — **선언값은 «대조 대상»으로 강등**하고 불일치 = **`PREVENTION_TARGET_MISMATCH`**(신설). `D ≠ ∅` 이면 **(b) 의 PR `base` == target 과 3중 일치**. **새 상태값인 근거**: `INSUFFICIENT` 로 접으면 «맞는 대상인데 약하다»와 «엉뚱한 대상을 봤다»가 같은 값이 되고 **운영자가 할 일이 완전히 다르다** ② **B2 — 논증 철회**: v2.16 의 «보호 꺼진 창의 커밋에는 흔적이 없다»는 **불성립이며 철회**한다 — **PR 체크는 보호 설정과 독립 실행**되므로 보호를 끄고 체크를 통과시켜 머지한 뒤 재활성하면 **정상 흔적이 남는다**. 그리고 **`app.id` 미검증**이라 제3자 앱이 `tos-gate` success 를 **위조 게시**할 수 있었다. 교정: check-run 검증에 **`app.id`(기본 `15368` = GitHub Actions·오늘 `main` 실측값)·`head_sha`·`check_suite` 귀속** 추가. **(b) 의 정확한 진술로 재저작**: 증명하는 것은 «그 리비전에서 서버가 게이트를 실행해 통과했다»이고, «머지 «시점»에 보호가 강제 중이었다»는 **공개 REST 로 사후 증명 불가**(감사 로그는 org/enterprise 소관)다. 잡는 것(체크 실패·부재 / 직접 push / 위조 success)을 열거하고 **남는 것 = «보호 off 상태에서 체크는 통과한 리비전 착지»** 를 **닫지 못함으로 명시**. **완화 2종**: (α) 룰셋 `created_at ≤ merged_at(min D)` 요구 + `updated_at > merged_at` 은 **차단이 아니라 관측 기록**(정당한 정책 개선까지 막는 과잉 차단 방지) (β) **예방 주체는 서버 자체**·`UNCHK-008` 잔존·**강제 «연속성» 증명은 감사 로그 확보 시 승격**. **«흔적 없음» 류 문장 전수 제거** ③ **B3 — S-22**: §8 `T-84` 행이 **에라타 E2 이후에도** `rulesets=[]`·«머지 커밋 check-runs 0»·«pulls 공집합»을 유지해 **같은 턴 실측과 충돌**했다(E2 가 #5 근거만 고치고 이 행을 안 봤다) → **행 전체 재작성** + **⑤ target 불일치**·**⑥ `app_id` 위조** 신설 ⇒ **T-84 4종 → 6종**. **상태 7값 → 8값 / 차단 7 / 전순서 8단.** **[v2.17 에라타 (동결 `a3c95b4f` 후 증거 실행 `6bad7c23` 적발 — 재결속 전 정정)]** ⓐ **E1 (S-22)** — §8 `T-84` ① 이 «작업 브랜치 → 404 → `PREVENTION_ABSENT`» 를 유지했으나, **v2.17 에서 `target_branch` 가 `default_branch` 로 «파생»되므로 그 구성은 ⑤(`TARGET_MISMATCH`)** 이고 **실행기로 재현되지 않는다**. **B1 의 파생 전환이 이 행에 미전파**된 것이며, ① 은 «선언 == 파생(`main`) → `INSUFFICIENT`» 로만 두고 404 는 **«raw probe 관측»으로 강등**했다 ⓑ **E2 (리터럴 고정 3건)** — 원격 URL **정규화 규칙**(https/ssh/scp 형식 → `<owner>/<repo>`·`.git` 제거·형식 밖 = 차단) · **`check_suite` «귀속 일치»의 구체**(check-run 의 `check_suite.id` 가 가리키는 suite 의 `head_sha` == PR `head.sha` — 산문으로 두면 구현마다 다르게 읽는다) · 아티팩트 키 이름 **`remote_name`**(기본 `origin`)·**`gate_app_id`**(기본 `15368`). **증거 실행 결과**: ⑤ **live `TARGET_MISMATCH`(`D=∅`)** · ⑥ `app.id` 위조 red · ① `main` `INSUFFICIENT` · ③ live — **전건 기대 일치**. **하니스 byte-identical·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
 | **v2.16** | **stop-time Codex 심판 BLOCK 2건 반영. 중심은 «U-17 의 진실 원천을 저장소에서 서버로 옮긴 것».** v2.15 는 **재결속 전이라 승인 표면을 가진 적이 없다**(v2.9→v2.10 선례). ① **BLOCK ① — S-22 미전파**: `U-17` 이 7c/8 결속을 **주장**했으나 **§12.3 실행 착수 절차 텍스트는 여전히 `U-15` 만 요구**하고 `prevention_control_state` 를 언급하지 않았다. 7c·8 텍스트에 **live `PREVENTION_ACTIVE`** 를 명시 소비로 추가하고 진입 조건을 **논리곱 셋**으로 확정 ② **BLOCK ② — 자기신고 검증**: `PREVENTION_ACTIVE` 가 **비인증 저장소 내 자기신고 + 커밋 조상성**만 봐 **실제·현재 브랜치 보호를 보지 않았고**, **양성 테스트가 모의 문자열을 스스로 쓰고 ACTIVE 를 냈다** ⇒ **거짓 주장·countersign 후 보호 해제가 green**. 교정: **진실 원천을 서버로** — 별도 실행기 **`u17-verify`** 가 **인증 API 로 live 조회**(`branches/{t}/protection` + 룰셋)하고 raw 응답을 transcript 에 verbatim 수록, 술어(**TOS 게이트 체크 ∈ contexts ∧ strict ∧ enforce_admins ∧ force-push/deletion 불허 ∧ PR 필수**)를 캡처된 응답 위에서 결정적으로 평가. **상태 4값 → 7값**(`PREVENTION_UNVERIFIABLE`·`PREVENTION_INSUFFICIENT`·`PREVENTION_UNVERIFIED_REVISION` 신설, 차단 6, 전순서 7단). **(b) 리비전 특정** — `∀d∈D` 에 대해 **check-run success + merged PR** 실조회. **«countersign 후 보호 해제»가 닫히는 논증**: (a) 를 **진입 시점과 완료 판정 시점 둘 다 live** 로 평가하고 (b) 가 **리비전마다 서버 실행 흔적**을 요구한다 — **어느 하나만으로는 닫히지 않는다**. 아티팩트·countersign 은 **진실 원천이 아니라 파라미터 선언 + 기록 순서**(owner/repo·대상 브랜치·체크 이름을 **선언**하고 **서버가 검증** — 하드코딩 금지)로 강등. **가드 체인 3단화**(`하니스 && u17-verify && D0A-FIRST`) — **하니스는 오프라인·결정적이어야 하고 byte-identical 회귀 기준선을 가지므로 네트워크를 넣지 않는다**(층 분리). **T-84 재저작**: **음성은 실측·양성은 seam** — 이 저장소 실조회로 `main` → **`PREVENTION_INSUFFICIENT`**(contexts `["test"]`·strict false), 작업 브랜치 → **`PREVENTION_ABSENT`**(404), rulesets `[]`. **인증된 진짜 음성 증거가 지금 존재한다.** 양성은 `responder` 주입 seam(기본 `gh api`·transcript 에 명시)으로 모의하되 **`SIMULATED` 표기**하고 **운영자가 보호를 설정하기 전엔 실측 불가**임을 정직 표기 — **seam 이 정당한 근거는 응답 파서와 판정 함수가 동일 코드 경로**라 주입이 **입력만** 바꾼다는 것이다. **[v2.16 마감 (검증 FAIL 반영 — live 실측은 계약대로였고 차단 3·medium 3)]** ⓐ **#1 (BLOCK ① 클래스 재발)** — §12.3.4-G 의 **G-음성·G-양성 가드가 여전히 2단**이라 **T-81 ⑫ 양성이 폐기된 형태를 탔다**. **3단으로 교정**하고 **`G-음성-2`(하니스 통과 + u17 차단)를 신설** — **현 실측(`INSUFFICIENT`/`ABSENT`)으로 «두 번째 억제 지점»을 live 로 실행할 수 있다** ⓑ **#2** — §8 `T-84` 행이 «4종» 선언 아래 **6항·③ 중복·v2.15 자기신고 기준 잔존**으로 (a) 정의와 **정면 충돌**했다 → 행 전체 재작성 ⓒ **#3 (자기신고 잔여)** — «transcript 에 responder 명시»는 **자기신고**이고 «파서·판정 동일 경로»는 **다른 명제**다. **구조로 닫는다**: 진입자의 `u17-verify` 는 **가드**일 뿐이고 **판정 소비자는 transcript 를 신뢰하지 않고 스스로 live 조회**한다 ⇒ **진실 원천 = 판정 소비자 자신의 조회**. **responder 위조는 진입자 transcript 만 오염**시킨다. 남는 것(**판정 소비자 자신의 환경 위조**·**예방 주체는 서버 자체**)은 **정직 경계 절**로 명시 ⓓ **#4** — 술어에 `required_pull_request_reviews` **부재 = 불충족** · `restrictions`/apps 우회 없음 · 룰셋 **필드 수준**(`enforcement=active`·`bypass_actors=[]`·`required_status_checks`·`pull_request`·`non_fast_forward`·`deletion`) 추가. **TOS 게이트 체크 기본 이름 `tos-gate`** 를 계약이 정하되 **파라미터 기본값**이고 **CI 잡 이름과 일치해야** 하며 **현재 CI 에 부재 → 오늘 `main` 이 `INSUFFICIENT` 인 것이 맞다** ⓔ **#5** — (b) 조회 SHA 를 **PR `head.sha`** 로 못박음(**squash/merge 착지에서 check-run 은 머지 커밋이 아니라 PR head 에 붙는다** — 실측: 머지 커밋 check-runs 0·pulls 공집합·미푸시 422). `d` 직접 조회는 **정직한 착지도 항상 red** 로 만든다 ⓕ **#6** — `T-84 ③` 의 타 축 값(`NOT_STARTED`) 제거하고 **`D = ∅` 처리**를 U-17 에 명시: (a) live 술어는 **`D` 와 무관**(착수 «전»에도 ACTIVE 가능해야 착수한다) · (b)(c) 는 «검증 대상 없음» — **공허참에 기대지 않는다**. **[v2.16 에라타 (동결 `eb2805a9` 후 증거 실행 `434448b2` 적발 — 재결속 전 정정)]** ⓐ **E1 문언 소실** — v2.15 에라타 E3 가 고정한 `operator_countersign: "<식별> <ISO-8601 UTC>"` **리터럴이 U-17 재작성에서 사라져** «형식 위반»이 **재-미정의**됐다 → `(c-0)` 로 복원 ⓑ **E2 사실 정정** — #5 근거의 «머지 커밋 check-runs 0건·pulls 공집합»은 **거짓**이었다(live 재측정: `11e382fc` check-runs **15건**·`pulls` = PR #636 merged 1건). **결론(조회 SHA = PR head.sha)은 유지하고 근거를 교체**한다: 그 15건은 **push 트리거 워크플로**이지 **PR 게이트가 아니며**, 게이트 결과는 **PR head SHA 에 귀속**된다(PR head `7656259d` check-runs 5건에 `tos-gate` 없음). `d` 직접 조회는 **게이트 아닌 실행을 게이트로 오인**하게 만든다 ⓒ **E3 fail-closed 리터럴 고정** — `allow_force_pushes`·`allow_deletions` **키 부재 = 불충족**(없는 것을 «허용 안 함»으로 읽지 않는다) · `restrictions` 실재 시 **`apps == []`**(users/teams 는 push 제한이라 우회 아님) · `rulesets/{id}` 의 **`bypass_actors` 키 부재도 불충족**(조회 못 한 것을 «없음»으로 읽지 않는다) ⓓ **성능 주** — 구조 `D`·`P` 판정은 `git rev-list --full-history` 로 **후보를 축소**해도 되며(2,149 커밋 ~36s → <1s), **완전성 근거**(술어 만족 `x` 는 모든 부모와 tree 가 달라 후보에 포함)와 함께 **«축소는 최적화·판정은 구조 평가»** 임을 명시했다. **증거 실행 결과**: G-음성-2 **live 성립** · T-84 live 음성(`main` INSUFFICIENT·브랜치 ABSENT) · seam 양성 · 3단 가드 ⑫ CLEAR. **하니스 byte-identical·`bound_paths` 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
@@ -4356,6 +4356,12 @@ addendum 으로 이행**한다(S-24: 재동결에 대한 절 범위 `git diff` 
 구조 정의로 고정.  **이 2차 에라타의 결속도 addendum 2차로 이행**(S-24: 절 범위 diff 공집합 +
 영향 변이 재실행 — §5 산출 목록).
 
+**[v2.19 에라타 3차 — addendum 2차 적발]** 2차 재동결(`ad5be1a3`) 후 **addendum 2차**
+(`…/U17-PREVENTION-CHECK-V219-ADDENDUM-2.md` §5)이 문언 결함 2건 + 권고 1건을 냈다:
+**E10**(E8① 전역 관측이 E6 국소 판정과 충돌) + **M-3**(열거는 열린-세계) → 판별을 **구조 재파생
+(㉠) + 전역 관측(㉡) + 국소 축(㉢)**으로 재작성 · **E11**(`P_first` 카디널리티 공백) → D 동형 처분.
+**이 3차 에라타의 결속도 addendum 3차로 이행**.
+
 | v2.18 finding | 심판 지적 | v2.19 의 변경 | 왜 회피가 아닌가 | 실행 증거 |
 |---|---|---|---|---|
 | **#1 F1** 보호 해제 창 (high) | 진입·완료 두 조회 사이 off→머지→재활성 창을 어느 술어도 소비 안 함 + (B) «완료 가능성 자체를 막는다» 과대주장 | **과대주장 철회** + **연속성 소비자 신설**(완료 판정 시점 룰셋 `created_at`/`updated_at` > `t_land` → `PREVENTION_CONTINUITY_UNVERIFIABLE`, 운영자 재심사) · U-17-c **10값** | 과대주장 대신 «위조 비용을 올리지 닫지 않는다» 정직 표기 · **설정 변경을 fail-closed 로 «관측→차단»** 승격(관측만이 아님) · 룰셋 미변경 우회는 감사 로그 경계로 명시 | 직전 U-17 = `20260819-002145/U17-PREVENTION-CHECK-V218.md`(T-84 ①~⑩) · **v2.19 ⑪ = `20260819-074621/U17-PREVENTION-CHECK-V219.md`** — (a)~(f) SIMULATED 6픽스처 전건 일치(off→merge→on·삭제-재생성·classic-only → `CONTINUITY_UNVERIFIABLE`·direct-push → 8 선발화·committer-date 무시)·**단 classic 死분기(E1)·t_land 공백(E2) 적발 → 에라타 정정** |
@@ -5549,6 +5555,16 @@ operator_countersign: "<운영자 식별> <ISO-8601 UTC>"   # 예: "operator 202
      |P_last| > 1  →  PREVENTION_ARTIFACT_MUTATED (현행 내용의 도입 지점이 «유일하지 않다» =
                       «언제 기록»이 유일하지 않아 사후 편집 배제 불가 · c_APP 크기>1 동형·보수)
      |P_last| = 1  →  그 유일 원소 `x_last` 를 아래 조건에 쓴다
+     **[E11 — v2.19 에라타 3차] `P_first` 카디널리티도 처분한다**(E9 로 P_first 가 집합이 됐다):
+     |P_first| = 0  →  아티팩트 경로가 HEAD 조상에 «도입된 적 없음».  아티팩트 부재이면
+                       **PREVENTION_ABSENT**(전순서 2 — 기존 «아티팩트 부재», 본 저장소 live 실측),
+                       현행에 «존재»하는데 도입 지점이 ∅ 이면 [PARENTS-UNTRUSTED] → **PREVENTION_UNVERIFIABLE**
+     |P_first| > 1  →  경로 복수 도입(형제 병렬 도입·도입-제거-재도입).  **LATE 술어를 `∀x∈P_first`
+                       로 그대로 둔다** — «어느 도입이라도 d 의 조상이면 ¬LATE»(∃-증인)라 다중
+                       카디널리티가 결정적으로 처리된다(신규 상태 불요).  |P_first|=2 실측(N-2 계열)
+     |P_first| = 1  →  정상
+     («∅ 취급»: `∀x∈∅` 공허참이라 |P_first|=0 이면 LATE 가 발화하나, 전순서상 ABSENT(2)/
+      UNVERIFIABLE(1)가 LATE(6)보다 먼저라 위 처분이 우선 — 상보성 유지)
 
 두 상태의 «기계 조건» — ∀-부모 도입 집합 위에서 결정적   [R1 — v2.18 마감 / E9 재정의]
   PREVENTION_LATE             ∃ d ∈ D : ∀ x ∈ P_first : **x ⋠ d**   («그 착지 시점에 경로가 없었다»)
@@ -7009,13 +7025,25 @@ c_APP(a) = { x ⊑ HEAD :  a ∈ rows(x:LEDGER)  ∧  ∀ p ∈ parents(x): a 
                  부모 객체 present» 세 판별을 «전부 통과»하면서** `git log --format=%P`·`rev-list`·
                  `merge-base` 등 **replace 를 따르는 모든 명령이 «가짜» 부모를 반환**해 `PREVENTION_LATE`
                  (6)→`PREVENTION_ACTIVE`(10) fail-open 이 났다(`GIT_NO_REPLACE_OBJECTS=1` 에서는 진짜 부모).
-           **판별 — 이중(관측 + 무력화, «둘 다»)**:
-             ① **관측**: `git replace -l` **공집합** ∧ `.git/info/grafts` **부재** ∧ 얕은 클론 아님.
-                하나라도 위반 = 부모 신뢰 불가 → **`PROVENANCE_UNVERIFIABLE`/`PREVENTION_UNVERIFIABLE`**
-                (얕은 클론은 `--no-replace-objects` 로 무력화되지 않으므로 관측이 필수다)
-             ② **무력화**: 모든 «조상·부모 파생» `git` 호출을 **`git --no-replace-objects …`**
-                (또는 `GIT_NO_REPLACE_OBJECTS=1`)로 고정 — replace 뷰를 «따르지 않는다»(grafts 는
-                이 플래그로 꺼지지 않으므로 ① 의 부재 요구가 grafts 축을 담당한다)
+           **판별 — 주(구조 재파생) + 전역 관측 + 국소 축** **[M-3 채택·E10 — v2.19 에라타 3차]**
+             **㉠ 주 판별 — «구조 재파생»(열거가 아니라 재파생·열린-세계를 닫는다)**: 각 후보 `x` 의
+                부모 집합을 **`git --no-replace-objects cat-file commit <x>` 의 `parent` 줄에서 직접
+                파싱**한다 — 커밋 객체의 «원본» 부모이며 replace·grafts·«미지의 재작성 기제»를 «따르지
+                않는다».  판정의 모든 `∀p ∈ parents(x)` 항은 이 재파생 집합을 쓴다.  재파생 집합이
+                `git rev-list`/`%P` 가 준 부모와 **불일치**하면 = 이력 뷰가 재작성됨 →
+                **`PROVENANCE_UNVERIFIABLE`/`PREVENTION_UNVERIFIABLE`**.  **극성**: 부모를 객체에서
+                재파생하면 열거가 다음 표면을 놓치는 열린-세계(N-1 클래스)가 «구조»로 닫힌다 — 이 계약이
+                반복해 세운 «구조 파생 > 자기신고/열거»다(S-6).  **열거(㉡)는 «관측 보조»로 격하**
+             **㉡ 전역 관측(보조)**: `git replace -l` **공집합** ∧ `.git/info/grafts` **부재**.
+                비어 있지 않으면 «어느 커밋이 재작성됐는지 열거 없이는 알 수 없다»(전역) → 차단.
+                ㉠ 의 교차 확인·리뷰 표면이며 `--no-replace-objects` 는 이 관측을 «가리지 않는다»(실측 M-2 무간섭)
+             **㉢ 국소 축(얕음·per-commit 판별 가능)**: `cat-file commit <x>` 가 부모 «객체» 조회에 실패
+                (얕은 클론 경계·`.git/shallow` 로 «특정»)하면 그 `x` 는 부모 미상 → **«그 후보만» 국소 차단**
+                (E6 — 해당 행/간선 도입 후보 우주에 그 경계가 있을 때만).  **[E10] 전역/국소 분할 근거**:
+                얕음은 `.git/shallow` 로 경계 커밋을 «특정»할 수 있어 «국소», replace/grafts 는 per-commit
+                특정 불가라 «전역» — 이 분할이 «판정 불가를 판정 불가로»(fail-closed)와 «얕지만 후보 밖은
+                접지 않음»(과잉 차단 회피)을 «동시에» 만족시키는 유일한 분할이다(E8① 전역 관측과 E6 국소
+                판정의 충돌 해소·`T-82 ⑳ⓑ` 2 vs 3 판별력 보존)
            경계·재작성 커밋은 `x` 를 도입 지점으로 **«확정하지 않는다»**.  **극성**: 부모를 신뢰할 수
            없으면 도입 지점을 확정할 수 없으니 **판정 불가를 판정 불가로**(E5 와 동형·fail-closed).
            «경로 부재(a∉rows, 참)»와 «부모 미상·위조(판정 불가)»를 구별한다.
```

### 1-2. `s24-proof-3.sh` — 원문 (sha256 `1116fbd9ae20d41f910237bab638d37e51db33831617c273ef6a988685808298`)

```bash
#!/usr/bin/env bash
# s24-proof-3.sh — S-24 ① «절 범위 diff 기계 증명» (에라타 2차 재동결 ad5be1a3 → 에라타 3차 재동결 f6493d23).
#   ① 두 blob 의 hunk 를 파싱해 «변경된 행 범위»를 기계 추출하고, 그 사이의 «닿지 않는» 구간을
#      전부 자동 생성해 old/new 양쪽에서 잘라 sha256 을 대조한다(∅ = byte-동일).
#   ② 계약이 지목한 «명명 절»(하니스 블록·U-17-c 상태표/전순서·(b) 술어·(c) 기계 조건·연속성 판정
#      본체·U-16-d 12단 표·c_APP 수식)은 **각 blob 에서 리터럴 grep 으로 위치를 파생**해(하드코딩
#      행번호 아님) 범위를 잘라 대조한다 — 행 이동(shift)이 있어도 «내용 동일»이 직접 증명된다.
#   해시·행번호를 발명하지 않는다. 전 값은 실측이다.
set -u
R=/Users/harris/Development/private/kis_unified_sts
P=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
OLD=ad5be1a3; NEW=f6493d23
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
sec "(a) 술어 블록 전문" '술어 (캡처된 응답 위에서 결정적)' 'TOS 게이트 체크 이름  아티팩트가'
sec "(b) 리비전 특정 전문" '**(b) 리비전 특정 — 사후·완료 판정** (§11)' '**[#5 — v2.16 마감 / E2 근거 교체] 조회 SHA 를'
sec "(α) 연속성 술어 전문" '(α) 연속성 술어 — 룰셋 «서버 타임스탬프»만 소비한다' '    **차단이되 «운영자 재심사 경로»**'
sec "C6 host 결속 블록 (E3)" '핀 host    = canonical_target 의 host 성분' '적용 범위  (a)·(b)·(c)·target'
sec "U-17-c 전순서 10단" '        **전순서** (전제 붕괴 순서):' '         10 PREVENTION_ACTIVE'
sec "U-17-c 상태표 (E9 조건 — 3차는 무변경)" 'U-17-c  상태  prevention_control_state   (1급 노출)' '        **열 값 중 «아홉이 차단»이고'
sec "U-17 (c) 두 상태의 «기계 조건» (E9)" '두 상태의 «기계 조건» — ∀-부모 도입 집합 위에서 결정적' '**초안의 결함**:'
sec "U-17-d 강제 지점·종료조건·대조군" 'U-17-d  강제 지점  §12.3 단계' '        대조군     T-84 (§8) — **12종**'
sec "[E8] 참조 1/4 — U-15-g-1 D 정의" 'D = { x ⊑ HEAD :  path ∈ tree(x)' '+6'
sec "[E8] 참조 2/4 — g6 C_R 정의 꼬리" '         = 전이 커밋 c 의 조상 중 **«도입 지점»**' '+6'
sec "U-16-c c_APP 수식 3행" 'c_APP(a) = { x ⊑ HEAD :  a ∈ rows(x:LEDGER)' '+3'
sec "U-16-d 전순서 12단 표" '  1  CONSUMER_ABSENT           검사기·원장·레지스터가 없으면' ' 12  NO_ROWS_CLEAR'
sec "U-16-d ① 선-검사 (E6/E8 — 3차는 무변경)" '        ① **선-검사(전역·구조 — g-규칙 «앞»에 필수로 온다)**:' '        ② **g-단락'
sec "U-16-d ② g-단락 (5~11)" '        ② **g-단락 — 선-검사를 통과한' '+3'
sec "U-16-a2 전칭 판정 블록" 'U-16-a2 **전칭 판정 — 고르지 않는다.**' '+8'
sec "U-16-h 시점 고정 블록" 'U-16-h  **승인 산출물이 그 내용을 인용해야 한다' '+6'
sec "U-16-b 간선 대응·고아 (E7)" '간선 대응        승인 행 `a` 가 간선 `(p→c)` 를 «덮는다» ⇔' '`edge_seq`       **소비자가 표시용으로 파생**한다'
sec "U-15-g-4 CORR 술어 블록" '            CORR(d) = { (t,k) ∈ RUNS :' '+5'
echo "  --"
# — 닿아야 «하는» 절 (에라타 3차의 실체 — ≠ 가 기대값)
sec "[E10] U-16-c [PARENTS-UNTRUSTED] 정의 블록 (유일 소스)" 'c_APP(a) = { x ⊑ HEAD :  a ∈ rows(x:LEDGER)' '```'
sec "[E11] U-17 (c) P_first/P_last 정의 + 카디널리티" '`P ⊰ d` 를 충족한 채 통과했다(사후 편집 허용).' '두 상태의 «기계 조건» — ∀-부모'
sec "§12.3.3 (B) 처분표 머리 (에라타 3차 서술)" '**[v2.19 에라타 2차 — addendum 적발]**' '| v2.18 finding | 심판 지적'
sec "심사 이력 v2.19 행" '> | **v2.19** | **재심 미착수.**' '+1'
sec "변경 이력 v2.19 행" '| **v2.19** | **v2.18 심판 판정 6건(high 3 / medium 3) 전건 반영.' '+1'

echo
echo "-- ④ 하니스 §12.3.4-R 블록 sha256 (계약이 리터럴로 결속한 값) --"
printf '  %s :4608-4708  %s\n' "$OLD" "$(sed -n '4608,4708p' "$b_old" | shasum -a 256 | cut -d' ' -f1)"
printf '  %s :4614-4714  %s\n' "$NEW" "$(sed -n '4614,4714p' "$b_new" | shasum -a 256 | cut -d' ' -f1)"
printf '  두 값 동일? %s\n' "$([ "$(sed -n '4608,4708p' "$b_old" | shasum -a 256 | cut -d' ' -f1)" = "$(sed -n '4614,4714p' "$b_new" | shasum -a 256 | cut -d' ' -f1)" ] && echo yes || echo no)"
printf '  계약 리터럴(본문 인용) 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d 과 일치? %s\n' \
  "$([ "$(sed -n '4614,4714p' "$b_new" | shasum -a 256 | cut -d' ' -f1)" = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d ] && echo yes || echo no)"

echo
echo "-- ⑤ 워킹트리·HEAD 결속 --"
printf '  HEAD                    = %s\n' "$(git -C "$R" rev-parse HEAD)"
printf '  blob(HEAD:계약)         = %s\n' "$(git -C "$R" rev-parse "HEAD:$P")"
printf '  blob(%s:계약)     = %s\n' "$NEW" "$(git -C "$R" rev-parse "$NEW:$P")"
printf '  워킹트리 hash-object    = %s\n' "$(git -C "$R" hash-object "$WT")"
printf '  git diff --quiet %s -- 계약 → rc=%s\n' "$NEW" "$(git -C "$R" diff --quiet "$NEW" -- "$P"; echo $?)"
printf '  sha256(워킹트리)        = %s\n' "$(shasum -a 256 "$WT" | cut -d' ' -f1)"
printf '  %s..HEAD 계약 커밋 수  = %s\n' "$NEW" "$(git -C "$R" rev-list --count "$NEW"..HEAD -- "$P")"
printf '  sed -n 4614,4714p <워킹트리> sha256 = %s\n' "$(sed -n '4614,4714p' "$WT" | shasum -a 256 | cut -d' ' -f1)"
rm -f "$b_old" "$b_new"
```

### 1-3. `s24-proof-3.sh` 출력 원문 (∅ = byte-동일 · ≠ = 에라타가 건드린 범위)

```text
=== S-24 절 범위 diff 기계 증명 (2026-08-19T03:04:50Z) — 동결 ad5be1a3(7316행) → 에라타 재동결 f6493d23(7344행) ===
$ git diff ad5be1a3..f6493d23 --stat -- <계약>
   ...-08-12-tos-phase0-completion-contract-design.md | 46 +++++++++++++++++-----
   1 file changed, 37 insertions(+), 9 deletions(-)
$ git diff ad5be1a3..f6493d23 -- <계약> | grep '^@@'   (hunk 목록 — 이것이 변경의 전부)
  @@ -115,7 +115,7 @@
  @@ -198,7 +198,7 @@
  @@ -4356,6 +4356,12 @@ addendum 으로 이행**한다(S-24: 재동결에 대한 절 범위 `git diff` 
  @@ -5549,6 +5555,16 @@ operator_countersign: "<운영자 식별> <ISO-8601 UTC>"   # 예: "operator 202
  @@ -7009,13 +7025,25 @@ c_APP(a) = { x ⊑ HEAD :  a ∈ rows(x:LEDGER)  ∧  ∀ p ∈ parents(x): a 

-- ① hunk 사상 (기계 파싱: 각 hunk 안에서 실제로 «바뀐» 행의 old/new 범위) --
   #  old[start,len]  new[start,len]   (len=0 은 순수 삽입/삭제)
  H1  old[118,1]        new[118,1]
  H2  old[201,1]        new[201,1]
  H3  old[4358,0]        new[4359,6]
  H4  old[5551,0]        new[5558,10]
  H5  old[7012,7]        new[7028,19]

-- ② «닿지 않는» 구간 자동 생성 + sha256 대조 (∅ = byte-동일) --
  ∅  old[1,117] == new[1,117]  sha256=8ab22be232d458c9…
  ≠   H1: old[118,118] vs new[118,118]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[119,200] == new[119,200]  sha256=128750c2bdb207c6…
  ≠   H2: old[201,201] vs new[201,201]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[202,4358] == new[202,4358]  sha256=f38454e862b61727…
  ≠   H3: old[4358,4358] vs new[4359,4364]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[4359,5551] == new[4365,5557]  sha256=701d72bfb19052ba…
  ≠   H4: old[5551,5551] vs new[5558,5567]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[5552,7011] == new[5568,7027]  sha256=d2fbb2394dd3af2e…
  ≠   H5: old[7012,7018] vs new[7028,7046]  — 에라타가 건드린 범위(≠ 기대)
  ∅  old[7019,7316] == new[7047,7344]  sha256=8308c3913c183c5d…   (말미~EOF)

-- 자동 구간 전건 결과: 전 구간 ∅ (변경은 hunk 안에만 있다) --

-- ③ 명명 절 대조 (각 blob 에서 «리터럴 grep 으로 위치 파생» — 하드코딩 행번호 아님) --
  ∅   §12.3.4-R 하니스 블록 (101행) : old[4609,4708] == new[4615,4714]  sha256=0d3a33b007033c4b…
  ∅   §8 T-84 행 (12종 — U-17 대조군) : old[2877,2877] == new[2877,2877]  sha256=acf53d204e14eb9b…
  ∅   §8 T-82 행 (20종 — U-16 대조군) : old[2927,2927] == new[2927,2927]  sha256=39641355848eef83…
  ∅   §8 T-81 행 (U-15 대조군) : old[2926,2926] == new[2926,2926]  sha256=4b416b99334a5605…
  ∅   (a) 술어 블록 전문 : old[5254,5291] == new[5260,5297]  sha256=5570120023328a32…
  ∅   (b) 리비전 특정 전문 : old[5354,5419] == new[5360,5425]  sha256=63c63d4e387c6f37…
  ∅   (α) 연속성 술어 전문 : old[5478,5504] == new[5484,5510]  sha256=98e4571de23fbc3f…
  ∅   C6 host 결속 블록 (E3) : old[5227,5242] == new[5233,5248]  sha256=6966d914f5e1cb36…
  ∅   U-17-c 전순서 10단 : old[5589,5599] == new[5605,5615]  sha256=efca55f331d90ca9…
  ∅   U-17-c 상태표 (E9 조건 — 3차는 무변경) : old[5572,5588] == new[5588,5604]  sha256=0060054207110b5a…
  ∅   U-17 (c) 두 상태의 «기계 조건» (E9) : old[5553,5560] == new[5569,5576]  sha256=969719aaa9d8db84…
  ∅   U-17-d 강제 지점·종료조건·대조군 : old[5601,5605] == new[5617,5621]  sha256=d31967d667226129…
  ∅   [E8] 참조 1/4 — U-15-g-1 D 정의 : old[4940,4945] == new[4946,4951]  sha256=463ba244686c9fe7…
  ∅   [E8] 참조 2/4 — g6 C_R 정의 꼬리 : old[6924,6929] == new[6940,6945]  sha256=7d78e31d5e99bca6…
  ∅   U-16-c c_APP 수식 3행 : old[6997,6999] == new[7013,7015]  sha256=34771ac4e3a056c6…
  ∅   U-16-d 전순서 12단 표 : old[7104,7116] == new[7132,7144]  sha256=de24dfc1244e20ba…
  ∅   U-16-d ① 선-검사 (E6/E8 — 3차는 무변경) : old[7121,7131] == new[7149,7159]  sha256=35d6bf7fd4d08008…
  ∅   U-16-d ② g-단락 (5~11) : old[7131,7133] == new[7159,7161]  sha256=6bed132451327946…
  ∅   U-16-a2 전칭 판정 블록 : old[6725,6732] == new[6741,6748]  sha256=fc6bae4bfcbd4cc1…
  ∅   U-16-h 시점 고정 블록 : old[6965,6970] == new[6981,6986]  sha256=394535f673cbb928…
  ∅   U-16-b 간선 대응·고아 (E7) : old[6793,6809] == new[6809,6825]  sha256=8f6b4646b910a32e…
  ∅   U-15-g-4 CORR 술어 블록 : old[4994,4998] == new[5000,5004]  sha256=77e8185e57e2ea05…
  --
  ≠   [E10] U-16-c [PARENTS-UNTRUSTED] 정의 블록 (유일 소스) : old[6997,7025]=a2c47dd49203dbf0… vs new[7013,7053]=6337d70237a3cf1c…  (에라타가 건드림)
  ≠   [E11] U-17 (c) P_first/P_last 정의 + 카디널리티 : old[5532,5553]=73ce2e6c3c999a6c… vs new[5538,5569]=6a0acf54c7909dcc…  (에라타가 건드림)
  ≠   §12.3.3 (B) 처분표 머리 (에라타 3차 서술) : old[4349,4359]=c250f3dbef5e174c… vs new[4349,4365]=1c8c9c1ab3d50f74…  (에라타가 건드림)
  ≠   심사 이력 v2.19 행 : old[118,118]=e5acf51508858c13… vs new[118,118]=b95b62a2f162f7cf…  (에라타가 건드림)
  ≠   변경 이력 v2.19 행 : old[201,201]=ca026f3c5d01ecdf… vs new[201,201]=2b24570a4bb6ef01…  (에라타가 건드림)

-- ④ 하니스 §12.3.4-R 블록 sha256 (계약이 리터럴로 결속한 값) --
  ad5be1a3 :4608-4708  957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  f6493d23 :4614-4714  957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  두 값 동일? yes
  계약 리터럴(본문 인용) 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d 과 일치? yes

-- ⑤ 워킹트리·HEAD 결속 --
  HEAD                    = f6493d23b95f45b62063c30a3ad47fc1c23f3738
  blob(HEAD:계약)         = 2f9141f80d5a86b367026e68588c373568fdc161
  blob(f6493d23:계약)     = 2f9141f80d5a86b367026e68588c373568fdc161
  워킹트리 hash-object    = 2f9141f80d5a86b367026e68588c373568fdc161
  git diff --quiet f6493d23 -- 계약 → rc=0
  sha256(워킹트리)        = cc1661fb09d19ab0aaf2313e89937f6da386d607c8c205a8d81e33fdace3303c
  f6493d23..HEAD 계약 커밋 수  = 0
  sed -n 4614,4714p <워킹트리> sha256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
```

**판독**: ② 의 «자동 구간»은 hunk 사이의 **모든** 무변경 구간을 기계 생성해 old/new 양쪽에서 잘라 sha256 을 대조한 것이고 **전 구간 ∅** 다. ③ 은 행번호를 하드코딩하지 않고 각 blob 에서 리터럴 grep 으로 위치를 파생한다(shift +6 ~ +28행).
**`§8 T-84`(12종)·`T-82`(20종)·`T-81` 행이 ∅ 라는 사실이 «종수 불변»을 기계적으로 확인**하고, **`U-17-c` 전순서 10단·상태표·기계 조건이 ∅** 라는 사실이 «E11 은 `P_first` 카디널리티 «처분»만 추가하고 상태 집합·전순서·기계 조건은 건드리지 않았다»를 확인한다.

---

## 2. 실행기 델타 — 에라타 3차가 요구한 코드 변경만

### 2-1. `u17-verify-v219e3.sh` (sha256 `2554776da60ba9ff1bec99a81891b9d8ac564cc1e5cf2b6dc887e61cc25d78bb`) — 직전 `8516adc2…` 대비 diff

델타 2건: **[E10]** ㉠ `parents_true()`(= `git --no-replace-objects cat-file commit <x>` 의 `parent` 줄 파싱)를 **모든 `∀p` 항의 유일 입력**으로 삼고, `parents_ambient()`(무력화를 «걷어낸» `%P`)와 대조해 불일치를 전역 차단
(**얕은 경계는 ㉢ 소관으로 예외** — §5 K-1) · ㉡ 관측 라인 재작성 · **[E11]** `|P_first|=0` ∧ 아티팩트 존재 → `PREVENTION_UNVERIFIABLE`.
함수가 서브셸에서 도므로 ㉠ 결과는 파일(`$PUF`/`$PUC`)로 누적한다.

```diff
2,17c2,13
< # u17-verify (v2.19 에라타 2차 ad5be1a3) — U-17 «예방 통제 활성 증거» 실행기 (계약 ad5be1a3 §12.3.4 U-17)
< #   v2.19 에라타 실행기(e3ed4e78·sha256 6a80beed…) 에서 파생 — 델타는 **에라타 2차 2건**뿐이다:
< #     [E8] `[SHALLOW]` → **`[PARENTS-UNTRUSTED]`** 일반화 (U-16-c 유일 소스).  «부모 집합을 신뢰할 수 없는 상태»는 둘이다:
< #          (1) 얕은 클론 «경계»(부모 미상) — `.git/shallow` ∪ 부모 커밋 «객체» 조회 실패.  **국소**(E6: 해당 경로의 후보 우주에 있을 때만).
< #          (2) 부모 «재작성» — `git replace --graft`/replace ref · `.git/info/grafts`.  **전역 관측**(어느 커밋이 재작성됐는지
< #              per-commit 으로 판별할 수단이 없다 — replace 를 따르는 모든 명령이 «가짜» 부모를 반환하므로 뷰 전체가 오염된다).
< #          판별 = **이중**: ① 관측 `git replace -l` 공집합 ∧ `.git/info/grafts` 부재 ∧ (얕음은 국소) — 위반 → PREVENTION_UNVERIFIABLE(1)
< #                          ② 무력화 `GIT_NO_REPLACE_OBJECTS=1` 전역 export (모든 조상·부모 파생 git 호출이 replace 뷰를 따르지 않는다).
< #                          **`.git/info/grafts` 는 ② 로 꺼지지 않는다(실측)** — 그래서 ① 의 «부재 요구»가 grafts 축을 담당한다.
< #     [E9] `P_first`·`P_last` 를 `D`·`C_R`·`c_APP` 와 **동형 ∀-부모 구조 «집합»** 정의로 고정(∨ «어느 한 부모와라도 다름» 폐기):
< #          P_first = { x ⊑ HEAD : path ∈ tree(x) ∧ ∀p∈parents(x): path ∉ tree(p) }            (D 동형)
< #          P_last  = { x ⊑ HEAD : blob(x:path) == blob(HEAD:path) ∧ ∀p: blob(p:path) ≠ 그 blob }  (C_R 동형)
< #          |P_last|=0 → PREVENTION_UNVERIFIABLE · >1 → PREVENTION_ARTIFACT_MUTATED(¬LATE 하) · =1 → x_last
< #          LATE = ∃d∈D: ∀x∈P_first: x ⋠ d   ·   MUTATED = ¬LATE ∧ (|P_last|>1 ∨ ∃d: x_last ⋠ d)
< #          ACTIVE 조건 = |P_last|=1 ∧ ∀d: x_last ⊰ d ∧ 소비 blob == blob(x_last:path)   (¬LATE 하 ACTIVE/MUTATED 상보·결정적)
< #   (E1 classic terminal·E2 t_land·E3 host 키·E6 국소화 는 e3ed4e78 실행기 거동 그대로 — 코드 델타 0.)
---
> # u17-verify (v2.19 에라타 3차 f6493d23) — U-17 «예방 통제 활성 증거» 실행기 (계약 f6493d23 §12.3.4 U-17)
> #   v2.19 에라타 2차 실행기(ad5be1a3·sha256 8516adc2…) 에서 파생 — 델타는 **에라타 3차 2건**뿐이다:
> #     [E10] `[PARENTS-UNTRUSTED]` 판별 «재구조화» (U-16-c 유일 소스):
> #       ㉠ **주 판별 = 구조 재파생** — 각 후보 x 의 부모를 `git --no-replace-objects cat-file commit <x>` 의 `parent` 줄에서 «직접 파싱».
> #            판정의 «모든» ∀p∈parents(x) 항이 이 재파생 집합을 쓴다.  이 집합이 «이력 뷰»(`%P`/rev-list, 무력화 «없이» 관측)와
> #            불일치하면 = 이력 뷰가 재작성됨 → PREVENTION_UNVERIFIABLE.  열거가 아니라 «재파생»이라 열린-세계(M-3)를 닫는다.
> #       ㉡ **전역 관측(보조)** — `git replace -l` 공집합 ∧ `<git-dir>/info/grafts` 부재.  ㉠ 의 교차 확인·리뷰 표면.
> #       ㉢ **국소 축** — `cat-file commit <x>` 가 «부모 객체» 조회에 실패(얕은 경계·`.git/shallow` 로 특정)하면 «그 후보만» 국소 차단(E6).
> #       [독해 — 계약 미규정 자리] ㉠ 불일치가 «얕은 경계»에서 비롯되면 ㉢ 이 담당한다(전역 승격 안 함) — 그래야 E6 국소화·T-82 ⑳ⓑ 판별력이 보존된다(§5 K-1).
> #     [E11] `P_first` 카디널리티 처분: |P_first|=0 ∧ 아티팩트 «부재» → PREVENTION_ABSENT(2, 기존 경로) / |P_first|=0 ∧ 아티팩트 «존재» → PREVENTION_UNVERIFIABLE(1)
> #            |P_first|>1 → LATE 술어 `∀x∈P_first: x ⋠ d` 그대로(∃-증인이라 결정적·신규 상태 불요) / =1 정상.
> #   (E1·E2·E3·E6·E8②·E9 는 ad5be1a3 실행기 거동 그대로 — 코드 델타 0.)
81c77,90
< # (1) 국소 — 그 커밋의 부모가 «미상»인가 (E6: 전역 단축 아님)
---
> # ── [E10 ㉠] 주 판별 — 부모 집합 «구조 재파생»(커밋 객체의 parent 줄 직접 파싱).  판정의 모든 ∀p 항이 이것을 쓴다.
> parents_true() { git --no-replace-objects cat-file commit "$1" 2>/dev/null | awk '/^$/{exit} /^parent /{printf "%s ", $2}'; }
> # ── [E10 ㉠ 대조] «이력 뷰»가 주는 부모 — 무력화를 «걷어내고» 관측한다(재작성 여부를 보려면 뷰를 그대로 봐야 한다)
> parents_ambient() { env -u GIT_NO_REPLACE_OBJECTS git log --format=%P -1 "$1" 2>/dev/null; }
> nset() { printf '%s\n' $1 | sort | tr '\n' ' '; }
> # 함수는 «명령 치환 서브셸»에서 도므로 결과를 변수로 되돌릴 수 없다 — 파일로 누적한다.
> PUF=$(mktemp); PUC=$(mktemp); : > "$PUF"; : > "$PUC"
> check_parents() { local x="$1" tp ap b
>   printf '%s\n' "$x" >> "$PUC"
>   tp=$(nset "$(parents_true "$x")"); ap=$(nset "$(parents_ambient "$x")")
>   [ "$tp" = "$ap" ] && return 0
>   for b in $SHALLOW_LIST; do [ "$b" = "$x" ] && return 0; done   # 얕은 경계는 ㉢ 국소 축 소관(전역 승격 안 함)
>   printf '%s[재파생=(%s) vs 뷰=(%s)]\n' "$x" "${tp% }" "${ap% }" >> "$PUF"; return 1; }
> # ── [E10 ㉢] 국소 — 그 커밋의 부모 «객체»가 미상인가 (E6: 전역 단축 아님)
83c92
<   for p in $(git log --format=%P -1 "$x"); do have_commit "$p" || return 0; done; return 1; }
---
>   for p in $(parents_true "$x"); do have_commit "$p" || return 0; done; return 1; }
106,107c115,116
< printf 'U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[%s] · %s=%s · is_shallow=%s · 무력화 GIT_NO_REPLACE_OBJECTS=%s\n' \
<   "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "${GIT_NO_REPLACE_OBJECTS:-∅}"
---
> printf 'U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[%s] · %s=%s · ㉢ is_shallow=%s(.git/shallow=[%s]) · 무력화 GIT_NO_REPLACE_OBJECTS=%s · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄\n' \
>   "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "$(printf '%s ' $SHALLOW_LIST)" "${GIT_NO_REPLACE_OBJECTS:-∅}"
239c248,249
<     intro=1; for p in $(git log --format=%P -1 "$x"); do git cat-file -e "$p:$path" 2>/dev/null && { intro=0; break; }; done; [ "$intro" = 1 ] && out="$out $x"; done; printf '%s' "$out"; }
---
>     check_parents "$x" || true
>     intro=1; for p in $(parents_true "$x"); do git cat-file -e "$p:$path" 2>/dev/null && { intro=0; break; }; done; [ "$intro" = 1 ] && out="$out $x"; done; printf '%s' "$out"; }
245c255,256
<     same=0; for p in $(git log --format=%P -1 "$x"); do
---
>     check_parents "$x" || true
>     same=0; for p in $(parents_true "$x"); do
257a269,272
> # [E10 ㉠] 후보 전수에 대해 «재파생 vs 이력 뷰» 대조 결과를 방출하고 불일치는 전역 차단
> PU_CHECKED=$(sort -u "$PUC" | grep -c .); PU_N=$(grep -c . "$PUF"); PU_MISMATCH=$(tr '\n' ' ' < "$PUF")
> printf 'U17-PU㉠ 재파생 대조: 검사 후보 %s건 · 불일치 %s건=[%s]\n' "$PU_CHECKED" "$PU_N" "$PU_MISMATCH"
> [ "$PU_N" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: $PU_MISMATCH"
265a281,282
>   # [E11] P_first 카디널리티 — 아티팩트가 «존재»하는데 도입 지점이 ∅ 이면 [PARENTS-UNTRUSTED] 로 확정 불가
>   [ "$NPF" -ne 0 ] || fire PREVENTION_UNVERIFIABLE "[E11] 아티팩트는 HEAD 에 «존재»하나 |P_first|=0 — [PARENTS-UNTRUSTED](㉢ 경계/㉠ 재작성)로 경로 도입 지점 확정 불가"
266a284
> # [E11] 아티팩트 «부재» 이면 |P_first|=0 이 정상이며 전순서 2 ABSENT 가 이미 발화했다(위 아티팩트 절) — 여기서 재발화하지 않는다
```

`u17-ctrl-obs-literal.sh` (sha256 `65afc9d2dc134a481a26615f4f5fb62e29257715bff30fc92d2d71753649cf1d`) — **㉠ 발화 «제거» + ㉡ 을 계약 문언 리터럴 `.git/info/grafts` 로**. 판정용 아님:

```diff
2c2
< # u17-verify (v2.19 에라타 3차 f6493d23) — U-17 «예방 통제 활성 증거» 실행기 (계약 f6493d23 §12.3.4 U-17)
---
> # u17-ctrl-obs-literal — [E10 대조군] ㉠ 주 판별 «제거» + ㉡ 을 «계약 문언 리터럴»(`.git/info/grafts`)로 구현한 변형. 판정용 아님.
74c74
< GRAFTS_PATH="$GITDIR/info/grafts"
---
> GRAFTS_PATH=".git/info/grafts"    # [대조군] 계약 문언 리터럴 — git-dir 파생 «아님»
272c272
< [ "$PU_N" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: $PU_MISMATCH"
---
> # [대조군] ㉠ 발화 «제거» — ㉡ 열거만으로 무엇이 잡히고 무엇이 새는지 본다
```

<details><summary>`u17-verify-v219e3.sh` 전문</summary>

```bash
#!/usr/bin/env bash
# u17-verify (v2.19 에라타 3차 f6493d23) — U-17 «예방 통제 활성 증거» 실행기 (계약 f6493d23 §12.3.4 U-17)
#   v2.19 에라타 2차 실행기(ad5be1a3·sha256 8516adc2…) 에서 파생 — 델타는 **에라타 3차 2건**뿐이다:
#     [E10] `[PARENTS-UNTRUSTED]` 판별 «재구조화» (U-16-c 유일 소스):
#       ㉠ **주 판별 = 구조 재파생** — 각 후보 x 의 부모를 `git --no-replace-objects cat-file commit <x>` 의 `parent` 줄에서 «직접 파싱».
#            판정의 «모든» ∀p∈parents(x) 항이 이 재파생 집합을 쓴다.  이 집합이 «이력 뷰»(`%P`/rev-list, 무력화 «없이» 관측)와
#            불일치하면 = 이력 뷰가 재작성됨 → PREVENTION_UNVERIFIABLE.  열거가 아니라 «재파생»이라 열린-세계(M-3)를 닫는다.
#       ㉡ **전역 관측(보조)** — `git replace -l` 공집합 ∧ `<git-dir>/info/grafts` 부재.  ㉠ 의 교차 확인·리뷰 표면.
#       ㉢ **국소 축** — `cat-file commit <x>` 가 «부모 객체» 조회에 실패(얕은 경계·`.git/shallow` 로 특정)하면 «그 후보만» 국소 차단(E6).
#       [독해 — 계약 미규정 자리] ㉠ 불일치가 «얕은 경계»에서 비롯되면 ㉢ 이 담당한다(전역 승격 안 함) — 그래야 E6 국소화·T-82 ⑳ⓑ 판별력이 보존된다(§5 K-1).
#     [E11] `P_first` 카디널리티 처분: |P_first|=0 ∧ 아티팩트 «부재» → PREVENTION_ABSENT(2, 기존 경로) / |P_first|=0 ∧ 아티팩트 «존재» → PREVENTION_UNVERIFIABLE(1)
#            |P_first|>1 → LATE 술어 `∀x∈P_first: x ⋠ d` 그대로(∃-증인이라 결정적·신규 상태 불요) / =1 정상.
#   (E1·E2·E3·E6·E8②·E9 는 ad5be1a3 실행기 거동 그대로 — 코드 델타 0.)
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
# ── [E10 ㉠] 주 판별 — 부모 집합 «구조 재파생»(커밋 객체의 parent 줄 직접 파싱).  판정의 모든 ∀p 항이 이것을 쓴다.
parents_true() { git --no-replace-objects cat-file commit "$1" 2>/dev/null | awk '/^$/{exit} /^parent /{printf "%s ", $2}'; }
# ── [E10 ㉠ 대조] «이력 뷰»가 주는 부모 — 무력화를 «걷어내고» 관측한다(재작성 여부를 보려면 뷰를 그대로 봐야 한다)
parents_ambient() { env -u GIT_NO_REPLACE_OBJECTS git log --format=%P -1 "$1" 2>/dev/null; }
nset() { printf '%s\n' $1 | sort | tr '\n' ' '; }
# 함수는 «명령 치환 서브셸»에서 도므로 결과를 변수로 되돌릴 수 없다 — 파일로 누적한다.
PUF=$(mktemp); PUC=$(mktemp); : > "$PUF"; : > "$PUC"
check_parents() { local x="$1" tp ap b
  printf '%s\n' "$x" >> "$PUC"
  tp=$(nset "$(parents_true "$x")"); ap=$(nset "$(parents_ambient "$x")")
  [ "$tp" = "$ap" ] && return 0
  for b in $SHALLOW_LIST; do [ "$b" = "$x" ] && return 0; done   # 얕은 경계는 ㉢ 국소 축 소관(전역 승격 안 함)
  printf '%s[재파생=(%s) vs 뷰=(%s)]\n' "$x" "${tp% }" "${ap% }" >> "$PUF"; return 1; }
# ── [E10 ㉢] 국소 — 그 커밋의 부모 «객체»가 미상인가 (E6: 전역 단축 아님)
is_boundary() { local x="$1" b p; for b in $SHALLOW_LIST; do [ "$b" = "$x" ] && return 0; done
  for p in $(parents_true "$x"); do have_commit "$p" || return 0; done; return 1; }

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
printf 'U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[%s] · %s=%s · ㉢ is_shallow=%s(.git/shallow=[%s]) · 무력화 GIT_NO_REPLACE_OBJECTS=%s · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄\n' \
  "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "$(printf '%s ' $SHALLOW_LIST)" "${GIT_NO_REPLACE_OBJECTS:-∅}"
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
    check_parents "$x" || true
    intro=1; for p in $(parents_true "$x"); do git cat-file -e "$p:$path" 2>/dev/null && { intro=0; break; }; done; [ "$intro" = 1 ] && out="$out $x"; done; printf '%s' "$out"; }
# [E9] P_last = «현행 blob 의 도입 지점 집합»(C_R 동형 · ∀-부모).  ∨(«어느 한 부모와라도 다름») 폐기.
blob_intro_set() { local path="$1" b="$2" out="" x p same; : > "$BNDF"
  for x in $(git rev-list --full-history HEAD -- "$path"); do
    [ "$(git rev-parse -q --verify "$x:$path" 2>/dev/null || echo ABSENT)" = "$b" ] || continue
    if is_boundary "$x"; then printf '%s\n' "$x" >> "$BNDF"; continue; fi
    check_parents "$x" || true
    same=0; for p in $(parents_true "$x"); do
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
# [E10 ㉠] 후보 전수에 대해 «재파생 vs 이력 뷰» 대조 결과를 방출하고 불일치는 전역 차단
PU_CHECKED=$(sort -u "$PUC" | grep -c .); PU_N=$(grep -c . "$PUF"); PU_MISMATCH=$(tr '\n' ' ' < "$PUF")
printf 'U17-PU㉠ 재파생 대조: 검사 후보 %s건 · 불일치 %s건=[%s]\n' "$PU_CHECKED" "$PU_N" "$PU_MISMATCH"
[ "$PU_N" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: $PU_MISMATCH"
NBD=$(printf '%s\n' $BND_D | grep -c .); NBP=$(printf '%s\n' $BND_P | grep -c .)
printf 'U17-SHALLOW is_shallow=%s .git/shallow=[%s] · 후보 우주 내 경계 커밋: D=[%s](%s건) P=[%s](%s건)  (E6: 전역 단축 아님 — 경로별 국소 판정)\n' "$IS_SHALLOW" "$(printf '%s ' $SHALLOW_LIST)" "$(printf '%s ' $BND_D)" "$NBD" "$(printf '%s ' $BND_P)" "$NBP"
[ "$NBD" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[SHALLOW] D 후보 우주에 얕은 클론 경계 커밋($(printf '%s ' $BND_D)) — 부모 미상이라 도입 지점 확정 불가 (부재를 «참»으로 접지 않는다)"
[ "$NBP" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[SHALLOW] P_first/P_last 후보 우주에 얕은 클론 경계 커밋($(printf '%s ' $BND_P)) — 확정 불가"
sanc() { git merge-base --is-ancestor "$1" "$2" 2>/dev/null && [ "$1" != "$2" ]; }   # 진(strict) 조상
if [ -n "$BODY" ]; then
  # [E9] 카디널리티 처분은 «무조건 항»(c_APP 동형) — |P_last|=0 은 이력 파생 실패다
  [ "$NPL" -ne 0 ] || fire PREVENTION_UNVERIFIABLE "[E9] |P_last|=0 — 현행 blob($HEAD_BLOB)의 도입 지점 없음 = 이력 파생 실패/[PARENTS-UNTRUSTED]"
  # [E11] P_first 카디널리티 — 아티팩트가 «존재»하는데 도입 지점이 ∅ 이면 [PARENTS-UNTRUSTED] 로 확정 불가
  [ "$NPF" -ne 0 ] || fire PREVENTION_UNVERIFIABLE "[E11] 아티팩트는 HEAD 에 «존재»하나 |P_first|=0 — [PARENTS-UNTRUSTED](㉢ 경계/㉠ 재작성)로 경로 도입 지점 확정 불가"
fi
# [E11] 아티팩트 «부재» 이면 |P_first|=0 이 정상이며 전순서 2 ABSENT 가 이미 발화했다(위 아티팩트 절) — 여기서 재발화하지 않는다
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

### 2-2. `u16-full-exec-v219e3.py` (sha256 `d0c62ee72f8d4858fa7fe363b10c4c0bb4b35b0512e06f4888281dec175970f5`) — 직전 `cca1d6d7…` 대비 diff

델타 1건: **[E10]** `parents()` 를 구조 재파생으로 교체(모든 `∀p` 항이 이것을 쓴다) + `parents_ambient()` 대조 → `PU_MISMATCH` 전역 `PROVENANCE_UNVERIFIABLE`(얕은 경계 예외) · ㉡ 관측 라인 재작성.
**E11 은 U-17 소관**이라 이 실행기의 델타가 아니다.

```diff
2c2
< """U-16 «전 규칙» 손 실행기 — v2.19 에라타 2차 (계약 ad5be1a3 §13.6.5 U-16-a/a2/b/c/d/f/g(g1~g6)/h).
---
> """U-16 «전 규칙» 손 실행기 — v2.19 에라타 3차 (계약 f6493d23 §13.6.5
3a4,12
> v2.19 에라타 2차 실행기(ad5be1a3·sha256 cca1d6d7…) 에서 파생 — 델타는 **에라타 3차 [E10] 1건**뿐이다:
>   `[PARENTS-UNTRUSTED]` 판별을 «재구조화» — ㉠ 주 판별 = 부모 집합 «구조 재파생»(`git --no-replace-objects cat-file commit <x>` 의
>   `parent` 줄 직접 파싱).  판정의 «모든» ∀p∈parents(x) 항이 이 재파생 집합을 쓰고, 이 집합이 «이력 뷰»(`git log --format=%P`, 무력화 «없이»)와
>   불일치하면 이력 뷰가 재작성된 것 → 전역 `PROVENANCE_UNVERIFIABLE`.  열거가 아니라 재파생이라 열린-세계(M-3)를 닫는다.
>   ㉡ 전역 관측(`git replace -l` 공집합 ∧ `<git-dir>/info/grafts` 부재)은 «보조»로 격하 · ㉢ 국소 축(얕은 경계)은 그대로.
>   [독해 — 계약 미규정] ㉠ 불일치가 «얕은 경계»에서 비롯되면 ㉢ 이 담당한다(전역 승격 안 함) — E6 국소화·T-82 ⑳ⓑ 판별력 보존(§5 K-1).
>   E11(P_first)은 U-17 소관이라 이 실행기의 델타가 아니다.
>  U-16-a/a2/b/c/d/f/g(g1~g6)/h).
> 
98c107,116
<     return g("log", "--format=%P", "-1", c).split()
---
>     """[E10 ㉠] 부모 집합 «구조 재파생» — 커밋 «객체»의 parent 줄을 직접 파싱한다.
>     replace ref·grafts·«미지의 재작성 기제»를 따르지 않는다(열거가 아니라 재파생)."""
>     out = subprocess.run([*GITBASE, R, "cat-file", "commit", c], capture_output=True, text=True).stdout
>     ps = []
>     for line in out.split("\n"):
>         if line == "":
>             break
>         if line.startswith("parent "):
>             ps.append(line.split()[1])
>     return ps
100a119,140
> def parents_ambient(c):
>     """[E10 ㉠ 대조] «이력 뷰»가 주는 부모 — 무력화를 걷어내고 관측(재작성 여부를 보려면 뷰를 그대로 봐야 한다)."""
>     import os as _os
>     env = dict(_os.environ); env.pop("GIT_NO_REPLACE_OBJECTS", None)
>     return subprocess.run(["git", "-C", R, "log", "--format=%P", "-1", c],
>                           capture_output=True, text=True, env=env).stdout.split()
> 
> 
> PU_MISMATCH = []
> 
> 
> def check_parents(x):
>     """㉠ 불일치 수집.  얕은 경계는 ㉢(국소)이 담당하므로 전역으로 승격하지 않는다."""
>     tp, ap = sorted(parents(x)), sorted(parents_ambient(x))
>     if tp == ap:
>         return True
>     if x in shallow_boundary():
>         return True
>     PU_MISMATCH.append((x, tp, ap))
>     return False
> 
> 
155c195
<         if is_boundary(x):                # [SHALLOW/E5] 부모 집합 «미상» ⇒ 도입 지점으로 확정하지 않는다
---
>         if is_boundary(x):                # ㉢ 국소 — 부모 «객체» 미상 ⇒ 도입 지점으로 확정하지 않는다
157a198
>         check_parents(x)                  # ㉠ 재파생 대조 (전역 수집)
197a239
>         check_parents(x)                  # ㉠ 재파생 대조 (전역 수집)
233,234c275,277
<     print(f"[PARENTS-UNTRUSTED] 관측: git replace -l={[x[:7] for x in REPL]} · .git/info/grafts={'present' if GRAFTS else 'ABSENT'}"
<           f" · is_shallow={SHALLOW} · 무력화 = git --no-replace-objects (전 호출)")
---
>     print(f"[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l={[x[:7] for x in REPL]} · <git-dir>/info/grafts={'present' if GRAFTS else 'ABSENT'}"
>           f" · ㉢ is_shallow={SHALLOW} · 무력화 = git --no-replace-objects (전 호출)"
>           f" · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱")
307a351,352
>     print(f"[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 {len(PU_MISMATCH)}건: "
>           f"{[(x[:7], [q[:7] for q in tp], [q[:7] for q in ap]) for x, tp, ap in PU_MISMATCH]}")
310a356,359
>     if PU_MISMATCH:
>         add("global", "PROVENANCE_UNVERIFIABLE",
>             "[PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: %s"
>             % [(x[:7], [q[:7] for q in tp], [q[:7] for q in ap]) for x, tp, ap in PU_MISMATCH])
```

대조군 3종 (전부 판정용 아님):

```diff
2c2
< """U-16 «전 규칙» 손 실행기 — v2.19 에라타 3차 (계약 f6493d23 §13.6.5
---
> """[E10 대조군 — 판정용 아님] ㉠ 주 판별 «제거» + ㉡ 을 «계약 문언 리터럴»(`.git/info/grafts`)로 구현한 변형.  (계약 f6493d23 §13.6.5
213,214c213
<     base = d if os.path.isabs(d) else os.path.join(R, d)
<     return os.path.exists(os.path.join(base, "info", "grafts"))
---
>     return os.path.exists(os.path.join(R, ".git", "info", "grafts"))   # [대조군] 계약 문언 리터럴 — git-dir 파생 «아님»
356,359c355
<     if PU_MISMATCH:
<         add("global", "PROVENANCE_UNVERIFIABLE",
<             "[PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: %s"
<             % [(x[:7], [q[:7] for q in tp], [q[:7] for q in ap]) for x, tp, ap in PU_MISMATCH])
---
>     # [대조군] ㉠ 발화 «제거»
57c57
< EVAL_ORDER = "precheck-first"          # 대조군 파일: "g1-first"  (계약 U-16-d ① 선-검사 → ② g-단락 · [E6] 국소)
---
> EVAL_ORDER = "g1-first"                 # [대조군] «g1·g4 먼저» 문자 구현 (U-16-d 정정 «전» 초안 순서) — 판정용 아님
2c2
< """U-16 «전 규칙» 손 실행기 — v2.19 에라타 3차 (계약 f6493d23 §13.6.5
---
> """[E10 대조군 — 판정용 아님] 「얕음 = 전역 관측 위반」 문자 구현 (E6 국소화 미적용).  (계약 f6493d23 §13.6.5
355a356,358
>     if SHALLOW:   # [대조군] 「얕음 = 전역」 문자 구현 — E6 국소화를 «따르지 않는다»
>         add("global", "PROVENANCE_UNVERIFIABLE",
>             "[대조군] 얕은 클론 자체를 전역 위반으로 읽음(E6 국소화 미적용)")
```

<details><summary>`u16-full-exec-v219e3.py` 전문</summary>

```python
#!/usr/bin/env python3
"""U-16 «전 규칙» 손 실행기 — v2.19 에라타 3차 (계약 f6493d23 §13.6.5

v2.19 에라타 2차 실행기(ad5be1a3·sha256 cca1d6d7…) 에서 파생 — 델타는 **에라타 3차 [E10] 1건**뿐이다:
  `[PARENTS-UNTRUSTED]` 판별을 «재구조화» — ㉠ 주 판별 = 부모 집합 «구조 재파생»(`git --no-replace-objects cat-file commit <x>` 의
  `parent` 줄 직접 파싱).  판정의 «모든» ∀p∈parents(x) 항이 이 재파생 집합을 쓰고, 이 집합이 «이력 뷰»(`git log --format=%P`, 무력화 «없이»)와
  불일치하면 이력 뷰가 재작성된 것 → 전역 `PROVENANCE_UNVERIFIABLE`.  열거가 아니라 재파생이라 열린-세계(M-3)를 닫는다.
  ㉡ 전역 관측(`git replace -l` 공집합 ∧ `<git-dir>/info/grafts` 부재)은 «보조»로 격하 · ㉢ 국소 축(얕은 경계)은 그대로.
  [독해 — 계약 미규정] ㉠ 불일치가 «얕은 경계»에서 비롯되면 ㉢ 이 담당한다(전역 승격 안 함) — E6 국소화·T-82 ⑳ⓑ 판별력 보존(§5 K-1).
  E11(P_first)은 U-17 소관이라 이 실행기의 델타가 아니다.
 U-16-a/a2/b/c/d/f/g(g1~g6)/h).

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
    """[E10 ㉠] 부모 집합 «구조 재파생» — 커밋 «객체»의 parent 줄을 직접 파싱한다.
    replace ref·grafts·«미지의 재작성 기제»를 따르지 않는다(열거가 아니라 재파생)."""
    out = subprocess.run([*GITBASE, R, "cat-file", "commit", c], capture_output=True, text=True).stdout
    ps = []
    for line in out.split("\n"):
        if line == "":
            break
        if line.startswith("parent "):
            ps.append(line.split()[1])
    return ps


def parents_ambient(c):
    """[E10 ㉠ 대조] «이력 뷰»가 주는 부모 — 무력화를 걷어내고 관측(재작성 여부를 보려면 뷰를 그대로 봐야 한다)."""
    import os as _os
    env = dict(_os.environ); env.pop("GIT_NO_REPLACE_OBJECTS", None)
    return subprocess.run(["git", "-C", R, "log", "--format=%P", "-1", c],
                          capture_output=True, text=True, env=env).stdout.split()


PU_MISMATCH = []


def check_parents(x):
    """㉠ 불일치 수집.  얕은 경계는 ㉢(국소)이 담당하므로 전역으로 승격하지 않는다."""
    tp, ap = sorted(parents(x)), sorted(parents_ambient(x))
    if tp == ap:
        return True
    if x in shallow_boundary():
        return True
    PU_MISMATCH.append((x, tp, ap))
    return False


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
        if is_boundary(x):                # ㉢ 국소 — 부모 «객체» 미상 ⇒ 도입 지점으로 확정하지 않는다
            boundary.append(x)
            continue
        check_parents(x)                  # ㉠ 재파생 대조 (전역 수집)
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
        check_parents(x)                  # ㉠ 재파생 대조 (전역 수집)
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
    print(f"[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l={[x[:7] for x in REPL]} · <git-dir>/info/grafts={'present' if GRAFTS else 'ABSENT'}"
          f" · ㉢ is_shallow={SHALLOW} · 무력화 = git --no-replace-objects (전 호출)"
          f" · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱")
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

    print(f"[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 {len(PU_MISMATCH)}건: "
          f"{[(x[:7], [q[:7] for q in tp], [q[:7] for q in ap]) for x, tp, ap in PU_MISMATCH]}")
    print("\n[상태 귀속] 계약 U-16-d 순서 적용")
    if consumer_absent:
        add("global", "CONSUMER_ABSENT", "레지스터·원장 부재")
    if PU_MISMATCH:
        add("global", "PROVENANCE_UNVERIFIABLE",
            "[PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: %s"
            % [(x[:7], [q[:7] for q in tp], [q[:7] for q in ap]) for x, tp, ap in PU_MISMATCH])
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

### 3-1. `t84v219e3.sh` (U-17 축 · sha256 `1701fb927cb274f98c455d672c4a2c91bf725f52016f3c94b3f25c7deba32211`)

```bash
#!/usr/bin/env bash
# t84v219e3.sh — v2.19 에라타 3차(f6493d23) «영향 변이» 재실행 드라이버 (U-17 축):
#   [E10] [PARENTS-UNTRUSTED] 판별 재구조화 — ㉠ 구조 재파생 · ㉡ 전역 관측(보조) · ㉢ 국소 · [E11] P_first 카디널리티 · 상보성.
# GET-only(seam 위주·본 저장소 live 1회) · 서버 쓰기·설정 변경 0 · 픽스처는 scratchpad 독립 git repo(본 저장소 무접촉·worktree 미사용).
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u17-verify-v219e3.sh"; CTRL_OBS="$SP/u17-ctrl-obs-literal.sh"; EXPREV="$SP/u17-verify-v219e2.sh"
FX="$SP/fx84g"; SEAM="$SP/seam219e3"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md; WF=.github/workflows/tos-gate.yml
OR=kakao-harris-lee/kis_unified_sts; PINURL=https://github.com/kakao-harris-lee/kis_unified_sts.git
REPO=/Users/harris/Development/private/kis_unified_sts
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
TLAND=2026-08-10T00:00:00Z
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
initrepo(){ rm -rf "$1"; git init -q -b main "$1"; git -C "$1" remote add origin "$PINURL"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; git -C "$1" rev-parse HEAD; }
artfile(){ mkdir -p "$1/$(dirname $PC)"; printf 'owner_repo: %s\ntarget_branch: main\ntos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED%s\n' "$OR" "${2:-}" > "$1/$PC"; }
art(){ artfile "$1" "${2:-}"; git -C "$1" add -A; git -C "$1" commit -q -m "P: artifact${2:+ (variant$2)}"; git -C "$1" rev-parse HEAD; }
wfcontent(){ printf 'name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - name: verify harness identity\n        run: shasum -a 256 tools/tos_entry_harness.sh | grep %s\n      - name: run entry harness\n        run: bash tools/tos_entry_harness.sh\n' "$LIT2"; }
wf(){ mkdir -p "$1/.github/workflows"; wfcontent > "$1/$WF"; git -C "$1" add -A; git -C "$1" commit -q -m "W: workflow"; git -C "$1" rev-parse HEAD; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact\n' > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "d: introduce config/tos_completion.yaml"; git -C "$1" rev-parse HEAD; }
run(){ git -C "$1" log --oneline --graph --all 2>/dev/null | sed 's/^/  /'
  echo "\$ ${4:-}bash $(basename "${3:-$EX}") <fixture>"
  env ${4:-} U17_RESPONDER="${2:-gh}" U17_CAPTURE_DIR="$(mktemp -d)" bash "${3:-$EX}" "$1" 2>&1 | grep -avE '^U17-(A00|A0 |A1|A2|A3|A4|B1|B2|B3|B4|B5) |^  \| |^U17-H '; echo "u17_rc=${PIPESTATUS[0]}"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; printf '%s\n' "$4" > "$1/$(k "$2").body"; }
seam_ruleset(){ rm -rf "$1"; mkdir -p "$1"
  inject "$1" "apps/github-actions" 200 '{"id":15368,"slug":"github-actions"}'
  inject "$1" "repos/$OR" 200 '{"full_name":"kakao-harris-lee/kis_unified_sts","default_branch":"main"}'
  inject "$1" "repos/$OR/branches/main/protection" 404 '{"message":"Branch not protected","status":"404"}'
  inject "$1" "repos/$OR/rules/branches/main" 200 '[{"type":"required_status_checks","ruleset_id":42,"parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]'
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
tp(){ git -C "$1" --no-replace-objects cat-file commit "$2" 2>/dev/null | awk '/^$/{exit} /^parent /{printf "%s ", $2}'; }
ap(){ env -u GIT_NO_REPLACE_OBJECTS git -C "$1" log --format=%P -1 "$2" 2>/dev/null; }
probe(){ printf '  ㉠ 재파생 cat-file parent = [%s]\n  ㉠ 이력 뷰 %%P            = [%s]\n  ㉡ git replace -l         = [%s] · <git-dir>/info/grafts = %s · 리터럴 .git/info/grafts = %s\n  ㉢ is_shallow             = %s\n' \
  "$(tp "$1" "$2")" "$(ap "$1" "$2")" "$(git -C "$1" replace -l | tr '\n' ' ')" \
  "$( [ -f "$(git -C "$1" rev-parse --absolute-git-dir)/info/grafts" ] && echo present || echo ABSENT )" \
  "$( [ -f "$1/.git/info/grafts" ] && echo present || echo ABSENT )" "$(git -C "$1" rev-parse --is-shallow-repository)"; }

rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"; SM="$SEAM/rs"; seam_ruleset "$SM"
printf 't84v219e3_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'sha256(u17-verify-v219e3.sh)=%s   (재실행 실행기 — 에라타 3차 델타 E10·E11)\n' "$(shasum -a 256 "$EX" | cut -d" " -f1)"
printf 'sha256(u17-ctrl-obs-literal.sh)=%s  (대조군 — ㉠ 제거 + ㉡ 을 계약 문언 리터럴 `.git/info/grafts` 로)\n' "$(shasum -a 256 "$CTRL_OBS" | cut -d" " -f1)"
printf 'sha256(u17-verify-v219e2.sh)=%s   (직전 실행기 — ㉡+무력화만·㉠ 없음 · c83e44db 증거의 것)\n' "$(shasum -a 256 "$EXPREV" | cut -d" " -f1)"

########################################################################
sec "A. ㉠ 판별 원시 프로브 — 「재파생(커밋 객체 parent 줄)」 vs 「이력 뷰(%P)」 를 5구성에서 실측"
BASE="$FX/probe"; SEED=$(initrepo "$BASE"); PB=$(art "$BASE"); WB=$(wf "$BASE"); DB=$(d0a "$BASE")
echo "-- (1) 평시 --"; probe "$BASE" "$DB"
echo "-- (2) git replace --graft d P --"; git -C "$BASE" replace --graft "$DB" "$PB" >/dev/null 2>&1; probe "$BASE" "$DB"; git -C "$BASE" replace -d "$DB" >/dev/null 2>&1
echo "-- (3) <git-dir>/info/grafts --"; mkdir -p "$BASE/.git/info"; printf '%s %s\n' "$DB" "$PB" > "$BASE/.git/info/grafts"; probe "$BASE" "$DB"; rm -f "$BASE/.git/info/grafts"
echo "  ⇒ 자기신고 확인: grafts 는 «커밋 객체»를 바꾸지 않으므로 cat-file 은 «진짜» 부모, %P 는 «가짜» — ㉠ 이 불일치로 잡는다"
echo "-- (4) 제3 표면: GIT_REPLACE_REF_BASE=refs/evil/ --"
git -C "$BASE" replace --graft "$DB" "$PB" >/dev/null 2>&1; EVIL=$(git -C "$BASE" replace -l)
git -C "$BASE" update-ref "refs/evil/$EVIL" "$(git -C "$BASE" rev-parse "refs/replace/$EVIL")"; git -C "$BASE" replace -d "$DB" >/dev/null 2>&1
printf '  (base 미설정) %%P=[%s] replace -l=[%s]\n' "$(ap "$BASE" "$DB")" "$(git -C "$BASE" replace -l | tr '\n' ' ')"
printf '  (GIT_REPLACE_REF_BASE=refs/evil/) ㉠ 재파생=[%s] · %%P=[%s] · replace -l=[%s]\n' \
  "$(GIT_REPLACE_REF_BASE=refs/evil/ tp "$BASE" "$DB")" "$(GIT_REPLACE_REF_BASE=refs/evil/ ap "$BASE" "$DB")" "$(GIT_REPLACE_REF_BASE=refs/evil/ git -C "$BASE" replace -l | tr '\n' ' ')"
echo "-- (5) --separate-git-dir + grafts (㉡ «리터럴 .git/info/grafts» 가 놓치는 자리) --"
SEP="$FX/sep"; SEPGD="$FX/sepgd"; rm -rf "$SEP" "$SEPGD"; mkdir -p "$SEP"
git init -q -b main --separate-git-dir "$SEPGD" "$SEP" >/dev/null; git -C "$SEP" remote add origin "$PINURL"
printf 'seed\n' > "$SEP/seed.md"; git -C "$SEP" add -A; git -C "$SEP" commit -q -m seed
PS=$(art "$SEP"); WS=$(wf "$SEP"); DS=$(d0a "$SEP")
mkdir -p "$SEPGD/info"; printf '%s %s\n' "$DS" "$PS" > "$SEPGD/info/grafts"
echo "  .git 는 파일(gitdir 포인터) · rev-parse --git-dir = $(git -C "$SEP" rev-parse --git-dir)"; probe "$SEP" "$DS"

########################################################################
sec "[E10]-1 replace --graft — ㉠ 불일치 ⇒ PREVENTION_UNVERIFIABLE (D·P 두 정의 후보 우주에서)"
R1="$FX/e10-replace"; SEED=$(initrepo "$R1"); P1=$(art "$R1"); W1=$(wf "$R1"); D1=$(d0a "$R1")
rev_seam "$SM" "$D1" "$W1"
git -C "$R1" replace --graft "$D1" "$P1" >/dev/null 2>&1; probe "$R1" "$D1"; run "$R1" "file:$SM"
sec "[E10]-1b 대조 — ㉡만 있고 ㉠ 없는 직전 실행기(v219e2)"
run "$R1" "file:$SM" "$EXPREV"

sec "[E10]-2 «.git/info/grafts» — ㉠ 불일치 ⇒ UNVERIFIABLE (자기신고 확인: cat-file 은 grafts 미적용)"
R2="$FX/e10-grafts"; rm -rf "$R2"; cp -R "$R1" "$R2"; git -C "$R2" replace -d "$D1" >/dev/null 2>&1
mkdir -p "$R2/.git/info"; printf '%s %s\n' "$D1" "$P1" > "$R2/.git/info/grafts"; probe "$R2" "$D1"; run "$R2" "file:$SM"
sec "[E10]-2b 대조 — 직전 실행기(㉡ 열거만)"
run "$R2" "file:$SM" "$EXPREV"

sec "[E10]-3 제3 표면 «GIT_REPLACE_REF_BASE=refs/evil/» — ㉠ 불일치 ⇒ UNVERIFIABLE"
R3="$FX/e10-refbase"; rm -rf "$R3"; cp -R "$R1" "$R3"; RB=$(git -C "$R3" replace -l)
git -C "$R3" update-ref "refs/evil/$RB" "$(git -C "$R3" rev-parse "refs/replace/$RB")"; git -C "$R3" replace -d "$D1" >/dev/null 2>&1
echo "  refs/evil/ 준비 · 기본 뷰 replace -l=[$(git -C "$R3" replace -l | tr '\n' ' ')] · %P=[$(ap "$R3" "$D1")]"
run "$R3" "file:$SM" "$EX" "GIT_REPLACE_REF_BASE=refs/evil/ "
sec "[E10]-3b 대조 — 직전 실행기(㉡ 열거만) · 같은 env"
run "$R3" "file:$SM" "$EXPREV" "GIT_REPLACE_REF_BASE=refs/evil/ "

sec "[E10]-4 **㉡ 열거가 «놓치는» 표면** — --separate-git-dir + grafts: ㉠ 는 잡고, 계약 문언 리터럴 ㉡ 구현은 «샌다»"
rev_seam "$SM" "$DS" "$WS"
echo "-- (a) v2.19-3 판정 실행기(㉠ 포함) --"; run "$SEP" "file:$SM"
echo "-- (b) 대조군: ㉠ 제거 + ㉡ 리터럴 `.git/info/grafts` (계약 문언 그대로) --"; run "$SEP" "file:$SM" "$CTRL_OBS"

sec "[E10]-5 정상 회귀 — replace 0 · grafts 부재 · shallow=false ⇒ ACTIVE 불변"
R5="$FX/e10-normal"; SEED=$(initrepo "$R5"); P5=$(art "$R5"); W5=$(wf "$R5"); D5=$(d0a "$R5")
rev_seam "$SM" "$D5" "$W5"; probe "$R5" "$D5"; run "$R5" "file:$SM"

########################################################################
sec "[E11]-1 |P_first|=0 ∧ 아티팩트 «부재» ⇒ PREVENTION_ABSENT(2) — 본 저장소 live (계약 문언 그대로)"
echo "\$ bash u17-verify-v219e3.sh $REPO"; U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO" 2>&1 | grep -avE '^  \| ' ; echo "u17_rc=${PIPESTATUS[0]}"

sec "[E11]-2 |P_first|=0 ∧ 아티팩트 «존재» ⇒ PREVENTION_UNVERIFIABLE(1) — 얕은 클론(㉢ 국소)"
SH="$FX/e11-shallow"; rm -rf "$SH"; git clone -q --depth 1 "file://$R5" "$SH"; git -C "$SH" remote set-url origin "$PINURL"
echo "  is_shallow=$(git -C "$SH" rev-parse --is-shallow-repository) · .git/shallow=$(cat "$SH/.git/shallow" | tr '\n' ' ') · HEAD=$(git -C "$SH" rev-parse HEAD)"
echo "  아티팩트 HEAD 존재? $(git -C "$SH" cat-file -e "HEAD:$PC" 2>/dev/null && echo yes || echo no)"; probe "$SH" "$(git -C "$SH" rev-parse HEAD)"
rev_seam "$SM" "$(git -C "$SH" rev-parse HEAD)" "$W5"; run "$SH" "file:$SM"

sec "[E11]-3 |P_first|=2 — 형제 «병렬 경로 도입»(서로 다른 blob) 후 머지가 X 쪽으로 해소 ⇒ ∀x 술어가 ∃-증인으로 결정적 (¬LATE · |P_last|=1 → ACTIVE)"
R6="$FX/e11-two"; SEED=$(initrepo "$R6")
git -C "$R6" checkout -q -b bX "$SEED"; artfile "$R6" " vX"; printf 'x\n' > "$R6/x.md"; git -C "$R6" add -A; git -C "$R6" commit -q -m "X: artifact 경로 도입 (blob vX) [side x]"; X6=$(git -C "$R6" rev-parse HEAD)
git -C "$R6" checkout -q -b bY "$SEED"; artfile "$R6" " vY"; printf 'y\n' > "$R6/y.md"; git -C "$R6" add -A; git -C "$R6" commit -q -m "Y: artifact 경로 도입 (blob vY) [side y]"; Y6=$(git -C "$R6" rev-parse HEAD)
git -C "$R6" checkout -q bX; git -C "$R6" merge -q --no-ff --no-commit "$Y6" >/dev/null 2>&1 || true
artfile "$R6" " vX"; git -C "$R6" add -A; git -C "$R6" commit -q -m "M: merge — 해소를 X 쪽 blob 으로 (머지는 도입 «아님»)"; M6=$(git -C "$R6" rev-parse HEAD)
git -C "$R6" branch -f main HEAD; git -C "$R6" checkout -q main
W6=$(wf "$R6"); D6=$(d0a "$R6")
echo "X=$X6(blob $(git -C "$R6" rev-parse "$X6:$PC")) Y=$Y6(blob $(git -C "$R6" rev-parse "$Y6:$PC")) M=$M6(blob $(git -C "$R6" rev-parse "$M6:$PC")) W=$W6 d=$D6"
rev_seam "$SM" "$D6" "$W6"; run "$R6" "file:$SM"

sec "[E11]-3b |P_first|=2 인데 «어느 도입도 d 의 조상이 아닌» 구성 ⇒ LATE(6) — ∀x 결정적임을 반대 방향으로 고정"
R7="$FX/e11-two-late"; SEED=$(initrepo "$R7"); W7=$(wf "$R7"); D7=$(d0a "$R7")
git -C "$R7" checkout -q -b lX "$D7"; artfile "$R7"; printf 'x\n' > "$R7/x.md"; git -C "$R7" add -A; git -C "$R7" commit -q -m "X: artifact 도입 (d «이후») [side x]"; LX=$(git -C "$R7" rev-parse HEAD)
git -C "$R7" checkout -q -b lY "$D7"; artfile "$R7"; printf 'y\n' > "$R7/y.md"; git -C "$R7" add -A; git -C "$R7" commit -q -m "Y: artifact 도입 (d «이후») [side y]"; LY=$(git -C "$R7" rev-parse HEAD)
git -C "$R7" checkout -q lX; git -C "$R7" merge -q --no-ff -m "M: merge (두 도입 모두 d 의 자손)" "$LY"; git -C "$R7" branch -f main HEAD; git -C "$R7" checkout -q main
echo "W=$W7 d=$D7 X=$LX Y=$LY"; rev_seam "$SM" "$D7" "$W7"; run "$R7" "file:$SM"

########################################################################
sec "[E11] 상보성 — ¬LATE 하 ACTIVE / ARTIFACT_MUTATED 상보·결정적 (합성 4종 · P_first 카디널리티 포함)"
echo "  ① 정상        = [E10]-5 (P → W → d, |P_first|=1)                 → ACTIVE(10)"
echo "  ② 사후 편집   = 아래 (P → W → d → P_edit)                        → ARTIFACT_MUTATED(7)"
echo "  ③ 다중 도입   = 아래 (X ∥ Y 동일 blob → M → W → d, |P_last|=2)   → ARTIFACT_MUTATED(7)"
echo "  ④ 순서 위반   = [E11]-3b (|P_first|=2 이나 전부 d 의 «자손»)      → LATE(6)"
R8="$FX/comp-edit"; SEED=$(initrepo "$R8"); P8=$(art "$R8"); W8=$(wf "$R8"); D8=$(d0a "$R8")
artfile "$R8" " EDITED-AFTER-d"; git -C "$R8" add -A; git -C "$R8" commit -q -m "P_edit: artifact edited AFTER d"
rev_seam "$SM" "$D8" "$W8"; run "$R8" "file:$SM"
R9="$FX/comp-multi"; SEED=$(initrepo "$R9")
git -C "$R9" checkout -q -b mX "$SEED"; artfile "$R9"; printf 'x\n' > "$R9/x.md"; git -C "$R9" add -A; git -C "$R9" commit -q -m "X: artifact (동일 blob 독립 도입) [x]"
git -C "$R9" checkout -q -b mY "$SEED"; artfile "$R9"; printf 'y\n' > "$R9/y.md"; git -C "$R9" add -A; git -C "$R9" commit -q -m "Y: artifact (동일 blob 독립 도입) [y]"; MY=$(git -C "$R9" rev-parse HEAD)
git -C "$R9" checkout -q mX; git -C "$R9" merge -q --no-ff -m "M: merge" "$MY"; git -C "$R9" branch -f main HEAD; git -C "$R9" checkout -q main
W9=$(wf "$R9"); D9=$(d0a "$R9"); rev_seam "$SM" "$D9" "$W9"; run "$R9" "file:$SM"
```

### 3-2. `t82v219e3.sh` (U-16 축 · sha256 `519e2af24c911bb832437c2a973106be3b12c3377bb3daf6ce3eac2914fc20f5`)

```bash
#!/usr/bin/env bash
# t82v219e3.sh — v2.19 에라타 3차(f6493d23) «영향 변이» 재실행 드라이버 (U-16 축):
#   [E10] ㉠ 구조 재파생(c_APP·C_R) · ㉡ 열거가 놓치는 표면 · ㉢ 국소(⑳ⓑ 2 vs 3 · 후보 우주 «밖» → green) · 정상 회귀.
# 서버 조회 0(순수 in-repo) · 픽스처는 scratchpad 독립 git repo(본 저장소 무접촉·worktree 미사용).
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u16-full-exec-v219e3.py"; CTRL_OBS="$SP/u16-ctrl-obs-literal.py"
CTRL_ORD="$SP/u16-order-ctrl-g1first-v219e3.py"; CTRL_SG="$SP/u16-ctrl-shallow-global.py"; EXPREV="$SP/u16-full-exec-v219e2.py"
FX="$SP/fx82g"; REF=reviews/review.md; RAT=rationale/r1.md
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
dig(){ python3 -c "import hashlib,sys; r=dict(id=sys.argv[1],closable=sys.argv[2],owner_track=sys.argv[3]); print(hashlib.sha256(b'\0'.join(f'{k}={r[k]}'.encode() for k in sorted(r))).hexdigest())" "$@"; }
DNO=$(dig r1 NO tos)
reg(){ printf 'id,closable,owner_track\n'; for kv in "$@"; do printf '%s\n' "$kv"; done; }
c(){ git -C "$1" add -A && git -C "$1" commit -q --allow-empty -m "$2" && git -C "$1" rev-parse HEAD; }
row(){ printf 'r1 | %s | %s | %s | %s | %s\n' "$1" "$DNO" "$2" "$REF" "${3:-$RAT}"; }
setNO(){ reg 'other,YES,x' 'r1,NO,tos' > "$1/register.csv"; }
run(){ git -C "$1" log --graph --oneline --all 2>/dev/null | sed 's/^/  /'; echo "\$ ${3:-}python3 $(basename "${2:-$EX}") <fixture>"; env ${3:-} python3 "${2:-$EX}" "$1"; echo "u16_rc=$?"; }
mergeled(){ git -C "$1" merge -q --no-ff -m "$3" "$2" 2>/dev/null || { { echo "## ledger"; git -C "$1" show HEAD:LEDGER.md | tail -n +2; git -C "$1" show "$2":LEDGER.md | tail -n +2; } | awk '!seen[$0]++' > "$1/LEDGER.md"; git -C "$1" add -A; git -C "$1" commit -q -m "$3"; }; }
tp(){ git -C "$1" --no-replace-objects cat-file commit "$2" 2>/dev/null | awk '/^$/{exit} /^parent /{printf "%s ", $2}'; }
ap(){ git -C "$1" log --format=%P -1 "$2" 2>/dev/null; }
probe(){ printf '  ㉠ 재파생=[%s] · ㉠ 이력 뷰 %%P=[%s] · ㉡ replace -l=[%s] · <git-dir>/info/grafts=%s · 리터럴 .git/info/grafts=%s · ㉢ is_shallow=%s\n' \
  "$(tp "$1" "$2")" "$(ap "$1" "$2")" "$(git -C "$1" replace -l | tr '\n' ' ')" \
  "$( [ -f "$(git -C "$1" rev-parse --absolute-git-dir)/info/grafts" ] && echo present || echo ABSENT )" \
  "$( [ -f "$1/.git/info/grafts" ] && echo present || echo ABSENT )" "$(git -C "$1" rev-parse --is-shallow-repository)"; }

# ⑳ⓐ 픽스처 빌더 (동일 승인 행 형제 독립 도입 · 진실 = APPROVAL_MALFORMED(3))
build20a(){ local R="$1" GDOPT="${2:-}"; rm -rf "$R"; mkdir -p "$R"
  if [ -n "$GDOPT" ]; then rm -rf "$GDOPT"; git init -q -b main --separate-git-dir "$GDOPT" "$R" >/dev/null; else git init -q -b main "$R"; fi
  mkdir -p "$R/reviews" "$R/rationale"
  reg 'other,YES,x' 'r1,YES,tos' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"
  printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; local H0 X CN Y; H0=$(c "$R" "H0: base (r1=YES · reviewer digest)")
  git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$H0" >> "$R/LEDGER.md"; printf 'x\n' > "$R/x.md"; X=$(c "$R" "X: approval row A [side x]")
  setNO "$R"; CN=$(c "$R" "CN: NO transition (child of X)")
  git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$H0" >> "$R/LEDGER.md"; printf 'y\n' > "$R/y.md"; Y=$(c "$R" "Y: approval row A (byte-identical) [side y]")
  git -C "$R" checkout -q --detach "$CN"; mergeled "$R" "$Y" "M: merge sibling identical approval introduction"; git -C "$R" branch -f main HEAD
  printf '%s %s %s %s\n' "$H0" "$X" "$CN" "$Y"; }

rm -rf "$FX"; mkdir -p "$FX"
printf 't82v219e3_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'sha256(u16-full-exec-v219e3.py)=%s   (재실행 실행기 — 에라타 3차 델타 E10)\n' "$(shasum -a 256 "$EX" | cut -d" " -f1)"
printf 'sha256(u16-ctrl-obs-literal.py)=%s  (대조군 — ㉠ 제거 + ㉡ 계약 문언 리터럴)\n' "$(shasum -a 256 "$CTRL_OBS" | cut -d" " -f1)"
printf 'sha256(u16-order-ctrl-g1first-v219e3.py)=%s (⑳ⓑ 순서 대조군)\n' "$(shasum -a 256 "$CTRL_ORD" | cut -d" " -f1)"
printf 'sha256(u16-ctrl-shallow-global.py)=%s (「얕음=전역」 문자 구현 대조군)\n' "$(shasum -a 256 "$CTRL_SG" | cut -d" " -f1)"
printf 'sha256(u16-full-exec-v219e2.py)=%s   (직전 실행기 — ㉡+무력화만 · c83e44db 증거의 것)\n' "$(shasum -a 256 "$EXPREV" | cut -d" " -f1)"
echo "계약 U-16-d 전순서: 1 CONSUMER_ABSENT · 2 PROVENANCE_UNVERIFIABLE · 3 APPROVAL_MALFORMED · 4 APPROVAL_MISSING · 5 SAME_COMMIT · 6 AFTER · 7 CONTENT_DRIFT · 8 HEAD_INVALID · 9 ROW_MUTATED · 10 UNBOUND · 11 ORDER_INVALID · 12 NO_ROWS_CLEAR"

########################################################################
sec "[E10]-U16-1 c_APP 축 — replace --graft ⇒ ㉠ 불일치 → PROVENANCE_UNVERIFIABLE(2)"
R="$FX/capp"; read -r H0 X CN Y <<< "$(build20a "$R")"; M=$(git -C "$R" rev-parse HEAD)
echo "H0=$H0 X=$X CN=$CN Y=$Y M=HEAD=$M"
echo "-- graft «전» (진실 = APPROVAL_MALFORMED(3) · |c_APP|=2) --"; probe "$R" "$M"; run "$R"
echo; echo "\$ git -C <fixture> replace --graft $M $CN     # 형제 도입 Y 를 숨긴다"
git -C "$R" replace --graft "$M" "$CN" 2>&1 | sed 's/^/  /'; probe "$R" "$M"
run "$R"

sec "[E10]-U16-2 C_R 축 — <git-dir>/info/grafts ⇒ ㉠ 불일치 → PROVENANCE_UNVERIFIABLE(2) (자기신고: cat-file 은 grafts 미적용)"
R2="$FX/capp-grafts"; rm -rf "$R2"; cp -R "$R" "$R2"; git -C "$R2" replace -d "$M" >/dev/null 2>&1
mkdir -p "$R2/.git/info"; printf '%s %s\n' "$M" "$CN" > "$R2/.git/info/grafts"; probe "$R2" "$M"; run "$R2"

sec "[E10]-U16-3 **㉡ 열거가 «놓치는» 표면** — --separate-git-dir + grafts: ㉠ 는 잡고 계약 문언 리터럴 ㉡ 구현은 «샌다»"
R3="$FX/sep"; GD3="$FX/sepgd"; read -r H3 X3 CN3 Y3 <<< "$(build20a "$R3" "$GD3")"; M3=$(git -C "$R3" rev-parse HEAD)
mkdir -p "$GD3/info"; printf '%s %s\n' "$M3" "$CN3" > "$GD3/info/grafts"
echo "  rev-parse --git-dir = $(git -C "$R3" rev-parse --git-dir)"; probe "$R3" "$M3"
echo "-- (a) v2.19-3 판정 실행기(㉠ 포함) --"; run "$R3"
echo "-- (b) 대조군: ㉠ 제거 + ㉡ 리터럴 .git/info/grafts (계약 문언 그대로) --"; run "$R3" "$CTRL_OBS"

sec "[E10]-U16-4 ㉢ 국소 — ⑳ⓑ 얕은 클론: 후보 우주 «안» ⇒ PROVENANCE_UNVERIFIABLE(2) · 순서 대조군은 3 (판별력 유지)"
R4="$FX/reg20a"; read -r H4 X4 CN4 Y4 <<< "$(build20a "$R4")"
SH="$FX/sh-in"; rm -rf "$SH"; git clone -q --depth 1 "file://$R4" "$SH"
echo "  is_shallow=$(git -C "$SH" rev-parse --is-shallow-repository) · .git/shallow=$(cat "$SH/.git/shallow" | tr '\n' ' ')"; probe "$SH" "$(git -C "$SH" rev-parse HEAD)"
run "$SH"; echo "-- 순서 대조군(«g1·g4 먼저») --"; run "$SH" "$CTRL_ORD"

sec "[E10]-U16-5 ㉢ 국소 — «얕지만 경계가 후보 우주 «밖»» ⇒ NO_ROWS_CLEAR/0 · 「얕음=전역」 문자 구현 대조군은 «밖»에서도 2 를 내 실패"
R5="$FX/e6"; rm -rf "$R5"; git init -q -b main "$R5"; mkdir -p "$R5/reviews" "$R5/rationale"
printf 'c0\n' > "$R5/c0.md"; c "$R5" "c0: seed0" >/dev/null
printf 'c1\n' > "$R5/c1.md"; c "$R5" "c1: seed1" >/dev/null
reg 'other,YES,x' > "$R5/register.csv"; echo "## ledger" > "$R5/LEDGER.md"; echo "rationale for r1 NO" > "$R5/$RAT"
printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R5/$REF"; RR=$(c "$R5" "R: reviewer artifact (digest)")
reg 'other,YES,x' 'r1,YES,tos' > "$R5/register.csv"; H5=$(c "$R5" "H0: register r1=YES")
row YES-\>NO "$RR" >> "$R5/LEDGER.md"; A5=$(c "$R5" "A: approval row (aah=R)")
setNO "$R5"; E5=$(c "$R5" "e: YES->NO")
SH2="$FX/sh-out"; rm -rf "$SH2"; git clone -q --depth 5 "file://$R5" "$SH2"
echo "  is_shallow=$(git -C "$SH2" rev-parse --is-shallow-repository) · .git/shallow=$(cat "$SH2/.git/shallow" 2>/dev/null | tr '\n' ' ')  (경계 = c1 — 후보 우주 «밖»)"
echo "-- (a) v2.19-3 판정 실행기 (㉢ 국소) --"; run "$SH2"
echo "-- (b) 대조군: 「얕음 = 전역」 문자 구현 --"; run "$SH2" "$CTRL_SG"

sec "[E10]-U16-6 정상 회귀 — replace 0 · grafts 부재 · shallow=false ⇒ 직전 판과 «불변»"
echo "-- ⑳ⓐ 원본 → APPROVAL_MALFORMED(3) --"; probe "$R4" "$(git -C "$R4" rev-parse HEAD)"; run "$R4"
echo "-- ⑱ 정정 문언(같은 row_id·다른 승인 행·형제 도입→merge) → NO_ROWS_CLEAR/0 --"
R6="$FX/reg18"; rm -rf "$R6"; git init -q -b main "$R6"; mkdir -p "$R6/reviews" "$R6/rationale"
reg 'other,YES,x' > "$R6/register.csv"; echo "## ledger" > "$R6/LEDGER.md"; echo "rationale for r1 NO" > "$R6/$RAT"
echo "rationale (approver a)" > "$R6/rationale/r1-a.md"; echo "rationale (approver b)" > "$R6/rationale/r1-b.md"
printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R6/$REF"; H6=$(c "$R6" "H0: r1 absent (reviewer digest)")
git -C "$R6" checkout -q --detach "$H6"; row ABSENT-\>NO "$H6" rationale/r1-a.md >> "$R6/LEDGER.md"; A61=$(c "$R6" "A1: approval (ABSENT->NO, rationale a)")
git -C "$R6" checkout -q --detach "$H6"; row YES-\>NO "$H6" rationale/r1-b.md >> "$R6/LEDGER.md"; A62=$(c "$R6" "A2: approval (YES->NO, rationale b)")
git -C "$R6" checkout -q --detach "$A61"; mergeled "$R6" "$A62" "MA: merge sibling approval introductions"
setNO "$R6"; c "$R6" "e1: ABSENT->NO" >/dev/null; reg 'other,YES,x' 'r1,YES,tos' > "$R6/register.csv"; c "$R6" "back to YES" >/dev/null; setNO "$R6"; c "$R6" "e2: YES->NO" >/dev/null
git -C "$R6" branch -f main HEAD; run "$R6"
```

---

## 4. 실행 기록 (stdout 전문 · rc 포함)

### 4-1. U-17 축 — `bash t84v219e3.sh` (A. ㉠ 원시 프로브 5구성 · [E10] 1~5 · [E11] 1~3b · 상보성 · 본 저장소 live)

각 run 은 `U17-0 target=…` 라인이 열고 run 당 상태 라인은 `prevention_control_state=` **정확히 1개**다. 가독을 위해 캡처 본문(raw JSON)과 `U17-H` 라인은 드라이버가 필터링했다 —
**판정에 쓰이는 라인(`U17-PU`·`U17-PU㉠`·`U17-SHALLOW`·`P_first`/`P_last`·`u17_live_state`·`U17-fire`·`prevention_control_state`·`reason`)은 전부 원문**이다.

```text
t84v219e3_utc=2026-08-19T03:13:05Z
sha256(u17-verify-v219e3.sh)=2554776da60ba9ff1bec99a81891b9d8ac564cc1e5cf2b6dc887e61cc25d78bb   (재실행 실행기 — 에라타 3차 델타 E10·E11)
sha256(u17-ctrl-obs-literal.sh)=65afc9d2dc134a481a26615f4f5fb62e29257715bff30fc92d2d71753649cf1d  (대조군 — ㉠ 제거 + ㉡ 을 계약 문언 리터럴 `.git/info/grafts` 로)
sha256(u17-verify-v219e2.sh)=8516adc2684498fb08d5312acab8dc5f25345c9268f0ec84b738d805bfb85968   (직전 실행기 — ㉡+무력화만·㉠ 없음 · c83e44db 증거의 것)

########## A. ㉠ 판별 원시 프로브 — 「재파생(커밋 객체 parent 줄)」 vs 「이력 뷰(%P)」 를 5구성에서 실측 ##########
-- (1) 평시 --
  ㉠ 재파생 cat-file parent = [b84495711b179f89c8f7e43d69b6067d5fefde5f ]
  ㉠ 이력 뷰 %P            = [b84495711b179f89c8f7e43d69b6067d5fefde5f]
  ㉡ git replace -l         = [] · <git-dir>/info/grafts = ABSENT · 리터럴 .git/info/grafts = ABSENT
  ㉢ is_shallow             = false
-- (2) git replace --graft d P --
  ㉠ 재파생 cat-file parent = [b84495711b179f89c8f7e43d69b6067d5fefde5f ]
  ㉠ 이력 뷰 %P            = [7a4f9ad0d02d73f449efd8d2e7a3d8249ebe80e0]
  ㉡ git replace -l         = [6e37f6515bbd77da0b7cf68cf420f9477626518c ] · <git-dir>/info/grafts = ABSENT · 리터럴 .git/info/grafts = ABSENT
  ㉢ is_shallow             = false
-- (3) <git-dir>/info/grafts --
  ㉠ 재파생 cat-file parent = [b84495711b179f89c8f7e43d69b6067d5fefde5f ]
  ㉠ 이력 뷰 %P            = [7a4f9ad0d02d73f449efd8d2e7a3d8249ebe80e0]
  ㉡ git replace -l         = [] · <git-dir>/info/grafts = present · 리터럴 .git/info/grafts = present
  ㉢ is_shallow             = false
  ⇒ 자기신고 확인: grafts 는 «커밋 객체»를 바꾸지 않으므로 cat-file 은 «진짜» 부모, %P 는 «가짜» — ㉠ 이 불일치로 잡는다
-- (4) 제3 표면: GIT_REPLACE_REF_BASE=refs/evil/ --
  (base 미설정) %P=[b84495711b179f89c8f7e43d69b6067d5fefde5f] replace -l=[]
  (GIT_REPLACE_REF_BASE=refs/evil/) ㉠ 재파생=[b84495711b179f89c8f7e43d69b6067d5fefde5f ] · %P=[7a4f9ad0d02d73f449efd8d2e7a3d8249ebe80e0] · replace -l=[6e37f6515bbd77da0b7cf68cf420f9477626518c ]
-- (5) --separate-git-dir + grafts (㉡ «리터럴 .git/info/grafts» 가 놓치는 자리) --
  .git 는 파일(gitdir 포인터) · rev-parse --git-dir = /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84g/sepgd
  ㉠ 재파생 cat-file parent = [89fdaeea3a0f1ec4329f0acd0eafea6339ffd406 ]
  ㉠ 이력 뷰 %P            = [ff02e8928ead0eaa315931cfbd1988bacd3948ad]
  ㉡ git replace -l         = [] · <git-dir>/info/grafts = present · 리터럴 .git/info/grafts = ABSENT
  ㉢ is_shallow             = false

########## [E10]-1 replace --graft — ㉠ 불일치 ⇒ PREVENTION_UNVERIFIABLE (D·P 두 정의 후보 우주에서) ##########
  ㉠ 재파생 cat-file parent = [4241759615056e06cb93f7e8a42965c63aa49bd3 ]
  ㉠ 이력 뷰 %P            = [34de54bac24228a4932fe3e574ce20ee8ce75804]
  ㉡ git replace -l         = [0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ] · <git-dir>/info/grafts = ABSENT · 리터럴 .git/info/grafts = ABSENT
  ㉢ is_shallow             = false
  * 0feee6a d: introduce config/tos_completion.yaml
  | * 7e0fd78 d: introduce config/tos_completion.yaml
  |/  
  * 34de54b P: artifact
  * 6feb920 seed
$ bash u17-verify-v219e3.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.WT1mFWDzUD
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ] · .git/info/grafts=no · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ) — 부모 집합 재작성 = 신뢰 불가
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:07Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] |D|=1 D=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · 불일치 1건=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb[재파생=(4241759615056e06cb93f7e8a42965c63aa49bd3) vs 뷰=(34de54bac24228a4932fe3e574ce20ee8ce75804)] ]
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb[재파생=(4241759615056e06cb93f7e8a42965c63aa49bd3) vs 뷰=(34de54bac24228a4932fe3e574ce20ee8ce75804)] 
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 4241759615056e06cb93f7e8a42965c63aa49bd3:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=0feee6a71f115f3b8ebdf28f5786e179c9f47ceb head=4241759615056e06cb93f7e8a42965c63aa49bd3 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ) — 부모 집합 재작성 = 신뢰 불가 [수집 2건 중 전순서 최소]
u17_rc=1

########## [E10]-1b 대조 — ㉡만 있고 ㉠ 없는 직전 실행기(v219e2) ##########
  * 0feee6a d: introduce config/tos_completion.yaml
  | * 7e0fd78 d: introduce config/tos_completion.yaml
  |/  
  * 34de54b P: artifact
  * 6feb920 seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qTfJKAYHEF
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ) — 부모 집합 재작성 = 신뢰 불가
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:09Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] |D|=1 D=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 4241759615056e06cb93f7e8a42965c63aa49bd3:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=0feee6a71f115f3b8ebdf28f5786e179c9f47ceb head=4241759615056e06cb93f7e8a42965c63aa49bd3 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ) — 부모 집합 재작성 = 신뢰 불가 [수집 1건 중 전순서 최소]
u17_rc=1

########## [E10]-2 «.git/info/grafts» — ㉠ 불일치 ⇒ UNVERIFIABLE (자기신고 확인: cat-file 은 grafts 미적용) ##########
  ㉠ 재파생 cat-file parent = [4241759615056e06cb93f7e8a42965c63aa49bd3 ]
  ㉠ 이력 뷰 %P            = [34de54bac24228a4932fe3e574ce20ee8ce75804]
  ㉡ git replace -l         = [] · <git-dir>/info/grafts = present · 리터럴 .git/info/grafts = present
  ㉢ is_shallow             = false
  * 0feee6a d: introduce config/tos_completion.yaml
  * 34de54b P: artifact
  * 6feb920 seed
$ bash u17-verify-v219e3.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.jx4qNglrPa
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · .git/info/grafts=yes · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:12Z  http=200  x-github-request-id=  (.default_branch=main)
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
P_first(집합·|1|)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] |D|=1 D=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · 불일치 1건=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb[재파생=(4241759615056e06cb93f7e8a42965c63aa49bd3) vs 뷰=(34de54bac24228a4932fe3e574ce20ee8ce75804)] ]
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb[재파생=(4241759615056e06cb93f7e8a42965c63aa49bd3) vs 뷰=(34de54bac24228a4932fe3e574ce20ee8ce75804)] 
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 4241759615056e06cb93f7e8a42965c63aa49bd3:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=0feee6a71f115f3b8ebdf28f5786e179c9f47ceb head=4241759615056e06cb93f7e8a42965c63aa49bd3 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) [수집 2건 중 전순서 최소]
u17_rc=1

########## [E10]-2b 대조 — 직전 실행기(㉡ 열거만) ##########
  * 0feee6a d: introduce config/tos_completion.yaml
  * 34de54b P: artifact
  * 6feb920 seed
$ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.04R1ZuZhxj
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[ ] · .git/info/grafts=yes · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:14Z  http=200  x-github-request-id=  (.default_branch=main)
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
P_first(집합·|1|)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] |D|=1 D=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 4241759615056e06cb93f7e8a42965c63aa49bd3:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=0feee6a71f115f3b8ebdf28f5786e179c9f47ceb head=4241759615056e06cb93f7e8a42965c63aa49bd3 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) [수집 1건 중 전순서 최소]
u17_rc=1

########## [E10]-3 제3 표면 «GIT_REPLACE_REF_BASE=refs/evil/» — ㉠ 불일치 ⇒ UNVERIFIABLE ##########
  refs/evil/ 준비 · 기본 뷰 replace -l=[] · %P=[4241759615056e06cb93f7e8a42965c63aa49bd3]
  * 7e0fd78 d: introduce config/tos_completion.yaml
  | * 0feee6a d: introduce config/tos_completion.yaml
  | * 4241759 W: workflow
  |/  
  * 34de54b P: artifact
  * 6feb920 seed
$ GIT_REPLACE_REF_BASE=refs/evil/ bash u17-verify-v219e3.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.WHCmkzoARd
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ] · .git/info/grafts=no · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ) — 부모 집합 재작성 = 신뢰 불가
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:16Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] |D|=1 D=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · 불일치 1건=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb[재파생=(4241759615056e06cb93f7e8a42965c63aa49bd3) vs 뷰=(34de54bac24228a4932fe3e574ce20ee8ce75804)] ]
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb[재파생=(4241759615056e06cb93f7e8a42965c63aa49bd3) vs 뷰=(34de54bac24228a4932fe3e574ce20ee8ce75804)] 
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 4241759615056e06cb93f7e8a42965c63aa49bd3:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=0feee6a71f115f3b8ebdf28f5786e179c9f47ceb head=4241759615056e06cb93f7e8a42965c63aa49bd3 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ) — 부모 집합 재작성 = 신뢰 불가 [수집 2건 중 전순서 최소]
u17_rc=1

########## [E10]-3b 대조 — 직전 실행기(㉡ 열거만) · 같은 env ##########
  * 7e0fd78 d: introduce config/tos_completion.yaml
  | * 0feee6a d: introduce config/tos_completion.yaml
  | * 4241759 W: workflow
  |/  
  * 34de54b P: artifact
  * 6feb920 seed
$ GIT_REPLACE_REF_BASE=refs/evil/ bash u17-verify-v219e2.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.F7uaZ0AbOc
U17-PU [PARENTS-UNTRUSTED] 관측: git replace -l=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ] · .git/info/grafts=no · is_shallow=false · 무력화 GIT_NO_REPLACE_OBJECTS=1
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ) — 부모 집합 재작성 = 신뢰 불가
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:18Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[34de54bac24228a4932fe3e574ce20ee8ce75804 ] |D|=1 D=[0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ]  [E9 ∀-부모]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 4241759615056e06cb93f7e8a42965c63aa49bd3:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=0feee6a71f115f3b8ebdf28f5786e179c9f47ceb head=4241759615056e06cb93f7e8a42965c63aa49bd3 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] git replace -l 비공집합(1건: 0feee6a71f115f3b8ebdf28f5786e179c9f47ceb ) — 부모 집합 재작성 = 신뢰 불가 [수집 1건 중 전순서 최소]
u17_rc=1

########## [E10]-4 **㉡ 열거가 «놓치는» 표면** — --separate-git-dir + grafts: ㉠ 는 잡고, 계약 문언 리터럴 ㉡ 구현은 «샌다» ##########
-- (a) v2.19-3 판정 실행기(㉠ 포함) --
  * 5fa12a7 d: introduce config/tos_completion.yaml
  * ff02e89 P: artifact
  * 6feb920 seed
$ bash u17-verify-v219e3.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.z0UXgM5aS9
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84g/sepgd/info/grafts=yes · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84g/sepgd/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:20Z  http=200  x-github-request-id=  (.default_branch=main)
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
P_first(집합·|1|)=[ff02e8928ead0eaa315931cfbd1988bacd3948ad ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[ff02e8928ead0eaa315931cfbd1988bacd3948ad ] |D|=1 D=[5fa12a77e3dd20c9acec558ab91fac7c8d31ce59 ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · 불일치 1건=[5fa12a77e3dd20c9acec558ab91fac7c8d31ce59[재파생=(89fdaeea3a0f1ec4329f0acd0eafea6339ffd406) vs 뷰=(ff02e8928ead0eaa315931cfbd1988bacd3948ad)] ]
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: 5fa12a77e3dd20c9acec558ab91fac7c8d31ce59[재파생=(89fdaeea3a0f1ec4329f0acd0eafea6339ffd406) vs 뷰=(ff02e8928ead0eaa315931cfbd1988bacd3948ad)] 
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 89fdaeea3a0f1ec4329f0acd0eafea6339ffd406:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=5fa12a77e3dd20c9acec558ab91fac7c8d31ce59 head=89fdaeea3a0f1ec4329f0acd0eafea6339ffd406 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84g/sepgd/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) [수집 2건 중 전순서 최소]
u17_rc=1
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/t84v219e3.sh: line 105: .git/info/grafts: No such file or directory
-- (b) 대조군: ㉠ 제거 + ㉡ 리터럴  (계약 문언 그대로) --
  * 5fa12a7 d: introduce config/tos_completion.yaml
  * ff02e89 P: artifact
  * 6feb920 seed
$ bash u17-ctrl-obs-literal.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9JoY76QtJj
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · .git/info/grafts=no · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:22Z  http=200  x-github-request-id=  (.default_branch=main)
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
P_first(집합·|1|)=[ff02e8928ead0eaa315931cfbd1988bacd3948ad ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[ff02e8928ead0eaa315931cfbd1988bacd3948ad ] |D|=1 D=[5fa12a77e3dd20c9acec558ab91fac7c8d31ce59 ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · 불일치 1건=[5fa12a77e3dd20c9acec558ab91fac7c8d31ce59[재파생=(89fdaeea3a0f1ec4329f0acd0eafea6339ffd406) vs 뷰=(ff02e8928ead0eaa315931cfbd1988bacd3948ad)] ]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 89fdaeea3a0f1ec4329f0acd0eafea6339ffd406:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=5fa12a77e3dd20c9acec558ab91fac7c8d31ce59 head=89fdaeea3a0f1ec4329f0acd0eafea6339ffd406 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs
u17_rc=0

########## [E10]-5 정상 회귀 — replace 0 · grafts 부재 · shallow=false ⇒ ACTIVE 불변 ##########
  ㉠ 재파생 cat-file parent = [1e5899f8e018ca44d80e95f3a05ed56925be8b15 ]
  ㉠ 이력 뷰 %P            = [1e5899f8e018ca44d80e95f3a05ed56925be8b15]
  ㉡ git replace -l         = [] · <git-dir>/info/grafts = ABSENT · 리터럴 .git/info/grafts = ABSENT
  ㉢ is_shallow             = false
  * 332826e d: introduce config/tos_completion.yaml
  * 1e5899f W: workflow
  * cba8183 P: artifact
  * a94fc80 seed
$ bash u17-verify-v219e3.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Z8uU8volOf
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · .git/info/grafts=no · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:24Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[cba81832d53fac93511779855823ca53a4aa5476 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[cba81832d53fac93511779855823ca53a4aa5476 ] |D|=1 D=[332826e76b0d533603d280ac682da6fa34445c23 ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · 불일치 0건=[]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 1e5899f8e018ca44d80e95f3a05ed56925be8b15:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=332826e76b0d533603d280ac682da6fa34445c23 head=1e5899f8e018ca44d80e95f3a05ed56925be8b15 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs
u17_rc=0

########## [E11]-1 |P_first|=0 ∧ 아티팩트 «부재» ⇒ PREVENTION_ABSENT(2) — 본 저장소 live (계약 문언 그대로) ##########
$ bash u17-verify-v219e3.sh /Users/harris/Development/private/kis_unified_sts
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.47Ea2hucLM
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · .git/info/grafts=no · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T03:13:28Z  http=200  x-github-request-id=74F4:94A79:37584D:3DAE18:6A851F57
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:28Z  http=200  x-github-request-id=49CB:94A79:3758CD:3DAEB2:6A851F57  (.default_branch=main)
U17-fire PREVENTION_ABSENT: 아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T03:13:28Z  http=200  x-github-request-id=ADDF:94A79:37598D:3DAF97:6A851F58
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T03:13:29Z  http=200  x-github-request-id=895F:19934D:37CA2E:3E1F46:6A851F59
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T03:13:30Z  http=200  x-github-request-id=237B:177308:37D665:3E2B49:6A851F59
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T03:13:30Z  http=200  x-github-request-id=920C:1D7764:37F1A9:3E479F:6A851F5A
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|0|)=[ ] P_last(집합·|0|·blob=∅)=[ ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 0건 · 불일치 0건=[]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
u17_rc=1

########## [E11]-2 |P_first|=0 ∧ 아티팩트 «존재» ⇒ PREVENTION_UNVERIFIABLE(1) — 얕은 클론(㉢ 국소) ##########
  is_shallow=true · .git/shallow=332826e76b0d533603d280ac682da6fa34445c23  · HEAD=332826e76b0d533603d280ac682da6fa34445c23
  아티팩트 HEAD 존재? yes
  ㉠ 재파생 cat-file parent = [1e5899f8e018ca44d80e95f3a05ed56925be8b15 ]
  ㉠ 이력 뷰 %P            = []
  ㉡ git replace -l         = [] · <git-dir>/info/grafts = ABSENT · 리터럴 .git/info/grafts = ABSENT
  ㉢ is_shallow             = true
  * 332826e d: introduce config/tos_completion.yaml
$ bash u17-verify-v219e3.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.uyLiIxvvII
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · .git/info/grafts=no · ㉢ is_shallow=true(.git/shallow=[332826e76b0d533603d280ac682da6fa34445c23 ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:31Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|0|)=[ ] P_last(집합·|0|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[ ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 0건 · 불일치 0건=[]
U17-SHALLOW is_shallow=true .git/shallow=[332826e76b0d533603d280ac682da6fa34445c23 ] · 후보 우주 내 경계 커밋: D=[332826e76b0d533603d280ac682da6fa34445c23 ](1건) P=[332826e76b0d533603d280ac682da6fa34445c23 ](1건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_UNVERIFIABLE: [SHALLOW] D 후보 우주에 얕은 클론 경계 커밋(332826e76b0d533603d280ac682da6fa34445c23 ) — 부모 미상이라 도입 지점 확정 불가 (부재를 «참»으로 접지 않는다)
U17-fire PREVENTION_UNVERIFIABLE: [SHALLOW] P_first/P_last 후보 우주에 얕은 클론 경계 커밋(332826e76b0d533603d280ac682da6fa34445c23 ) — 확정 불가
U17-fire PREVENTION_UNVERIFIABLE: [E9] |P_last|=0 — 현행 blob(762145cfb2a9a719deb125bef8ecea955d7e656e)의 도입 지점 없음 = 이력 파생 실패/[PARENTS-UNTRUSTED]
U17-fire PREVENTION_UNVERIFIABLE: [E11] 아티팩트는 HEAD 에 «존재»하나 |P_first|=0 — [PARENTS-UNTRUSTED](㉢ 경계/㉠ 재작성)로 경로 도입 지점 확정 불가
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[SHALLOW] D 후보 우주에 얕은 클론 경계 커밋(332826e76b0d533603d280ac682da6fa34445c23 ) — 부모 미상이라 도입 지점 확정 불가 (부재를 «참»으로 접지 않는다) [수집 4건 중 전순서 최소]
u17_rc=1

########## [E11]-3 |P_first|=2 — 형제 «병렬 경로 도입»(서로 다른 blob) 후 머지가 X 쪽으로 해소 ⇒ ∀x 술어가 ∃-증인으로 결정적 (¬LATE · |P_last|=1 → ACTIVE) ##########
X=1768e9e9da4c3150b226efd7f1ef7e2622d91a24(blob e590c3d03b764c6548fefcdf8dee8d3b39658110) Y=7a9c4c0091c244a371e5d9368595d3c748e7ea2f(blob f8f119b1671d82b0808caee0f5eedb47ab08f199) M=f3879da7b92a10ff86bd4261fdb1df543bf1b6fc(blob e590c3d03b764c6548fefcdf8dee8d3b39658110) W=a1052da18ccc009ad410aa6ca74505b8118ee284 d=5af7f5e57e97ac9ab550080064877231b574323f
  * 5af7f5e d: introduce config/tos_completion.yaml
  * a1052da W: workflow
  *   f3879da M: merge — 해소를 X 쪽 blob 으로 (머지는 도입 «아님»)
  |\  
  | * 7a9c4c0 Y: artifact 경로 도입 (blob vY) [side y]
  * | 1768e9e X: artifact 경로 도입 (blob vX) [side x]
  |/  
  * 905106c seed
$ bash u17-verify-v219e3.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ekJMZpyTcx
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · .git/info/grafts=no · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:33Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|2|)=[1768e9e9da4c3150b226efd7f1ef7e2622d91a24 7a9c4c0091c244a371e5d9368595d3c748e7ea2f ] P_last(집합·|1|·blob=e590c3d03b764c6548fefcdf8dee8d3b39658110)=[1768e9e9da4c3150b226efd7f1ef7e2622d91a24 ] |D|=1 D=[5af7f5e57e97ac9ab550080064877231b574323f ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 4건 · 불일치 0건=[]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show a1052da18ccc009ad410aa6ca74505b8118ee284:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=5af7f5e57e97ac9ab550080064877231b574323f head=a1052da18ccc009ad410aa6ca74505b8118ee284 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs
u17_rc=0

########## [E11]-3b |P_first|=2 인데 «어느 도입도 d 의 조상이 아닌» 구성 ⇒ LATE(6) — ∀x 결정적임을 반대 방향으로 고정 ##########
W=113293c6acd6609a6cf60d791c75ae6aee9d86e3 d=01f2ebf72e6d65602ae5dc9e71cb95c2a6e8b578 X=0fbcccd8d5180ae4f6349141be4f042011dd910e Y=a12e774c3309f4d0b9c78c49d29f55f5f536a518
  *   c057fee M: merge (두 도입 모두 d 의 자손)
  |\  
  | * a12e774 Y: artifact 도입 (d «이후») [side y]
  * | 0fbcccd X: artifact 도입 (d «이후») [side x]
  |/  
  * 01f2ebf d: introduce config/tos_completion.yaml
  * 113293c W: workflow
  * b98e6ae seed
$ bash u17-verify-v219e3.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.bhP9i7Zo2M
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · .git/info/grafts=no · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:37Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|2|)=[0fbcccd8d5180ae4f6349141be4f042011dd910e a12e774c3309f4d0b9c78c49d29f55f5f536a518 ] P_last(집합·|2|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[0fbcccd8d5180ae4f6349141be4f042011dd910e a12e774c3309f4d0b9c78c49d29f55f5f536a518 ] |D|=1 D=[01f2ebf72e6d65602ae5dc9e71cb95c2a6e8b578 ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · 불일치 0건=[]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|2|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 113293c6acd6609a6cf60d791c75ae6aee9d86e3:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=01f2ebf72e6d65602ae5dc9e71cb95c2a6e8b578 head=113293c6acd6609a6cf60d791c75ae6aee9d86e3 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_LATE
reason=[E9] ∃d∈D: ∀x∈P_first(|2|) x ⋠ d — 그 착지 시점에 경로가 없었다 [수집 1건 중 전순서 최소]
u17_rc=1

########## [E11] 상보성 — ¬LATE 하 ACTIVE / ARTIFACT_MUTATED 상보·결정적 (합성 4종 · P_first 카디널리티 포함) ##########
  ① 정상        = [E10]-5 (P → W → d, |P_first|=1)                 → ACTIVE(10)
  ② 사후 편집   = 아래 (P → W → d → P_edit)                        → ARTIFACT_MUTATED(7)
  ③ 다중 도입   = 아래 (X ∥ Y 동일 blob → M → W → d, |P_last|=2)   → ARTIFACT_MUTATED(7)
  ④ 순서 위반   = [E11]-3b (|P_first|=2 이나 전부 d 의 «자손»)      → LATE(6)
  * d80101a P_edit: artifact edited AFTER d
  * 421fc36 d: introduce config/tos_completion.yaml
  * 83c687a W: workflow
  * c9fe99c P: artifact
  * f5f6e0d seed
$ bash u17-verify-v219e3.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.WxhLnsAjF1
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · .git/info/grafts=no · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:40Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[c9fe99cdf7e8499721a895e2dde84df485ff18e6 ] P_last(집합·|1|·blob=ae36877de7431236f60ccad09c74af51bbe5b0fe)=[d80101ad0fafabc551a869da6a06dc84d0e7bea4 ] |D|=1 D=[421fc3614891862a56f07dd273ba8547ec925e43 ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · 불일치 0건=[]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_ARTIFACT_MUTATED: [E9] ¬LATE ∧ ∃d∈D: x_last=d80101ad0fafabc551a869da6a06dc84d0e7bea4 ⋠ d — 착수 «후» 아티팩트 변경
U17-B5x 보조(선택·판정 미소비): 로컬 git show 83c687a67b03083a52109c7d1ae5c0040320dec6:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=421fc3614891862a56f07dd273ba8547ec925e43 head=83c687a67b03083a52109c7d1ae5c0040320dec6 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=[E9] ¬LATE ∧ ∃d∈D: x_last=d80101ad0fafabc551a869da6a06dc84d0e7bea4 ⋠ d — 착수 «후» 아티팩트 변경 [수집 1건 중 전순서 최소]
u17_rc=1
  * cf84e65 d: introduce config/tos_completion.yaml
  * af321a2 W: workflow
  *   a2d6678 M: merge
  |\  
  | * e07f284 Y: artifact (동일 blob 독립 도입) [y]
  * | 9c69334 X: artifact (동일 blob 독립 도입) [x]
  |/  
  * 04ca635 seed
$ bash u17-verify-v219e3.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e3/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.14gr1gGodO
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · .git/info/grafts=no · ㉢ is_shallow=false(.git/shallow=[ ]) · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T03:13:43Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|2|)=[9c69334ac88d7384d8d2066020cb7663db164043 e07f2849911272ea931bb0414d5e8e888760e09c ] P_last(집합·|2|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[9c69334ac88d7384d8d2066020cb7663db164043 e07f2849911272ea931bb0414d5e8e888760e09c ] |D|=1 D=[cf84e651bf6bec1040704ae21ecbc1e43c6ec0fb ]  [E9 ∀-부모]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · 불일치 0건=[]
U17-SHALLOW is_shallow=false .git/shallow=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_ARTIFACT_MUTATED: [E9] ¬LATE ∧ |P_last|=2>1 (9c69334ac88d7384d8d2066020cb7663db164043 e07f2849911272ea931bb0414d5e8e888760e09c ) — 현행 내용의 도입 지점이 유일하지 않다
U17-B5x 보조(선택·판정 미소비): 로컬 git show af321a2de961374280c9aa71b26d06b993cf8ba2:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=cf84e651bf6bec1040704ae21ecbc1e43c6ec0fb head=af321a2de961374280c9aa71b26d06b993cf8ba2 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=[E9] ¬LATE ∧ |P_last|=2>1 (9c69334ac88d7384d8d2066020cb7663db164043 e07f2849911272ea931bb0414d5e8e888760e09c ) — 현행 내용의 도입 지점이 유일하지 않다 [수집 1건 중 전순서 최소]
u17_rc=1
```

### 4-2. U-16 축 — `bash t82v219e3.sh` ([E10] `c_APP`·`C_R` 축 · ㉡ 열거가 놓치는 표면 · ㉢ 국소 2 vs 3 · 정상 회귀)

```text
t82v219e3_utc=2026-08-19T03:13:45Z
sha256(u16-full-exec-v219e3.py)=d0c62ee72f8d4858fa7fe363b10c4c0bb4b35b0512e06f4888281dec175970f5   (재실행 실행기 — 에라타 3차 델타 E10)
sha256(u16-ctrl-obs-literal.py)=6ebdf1cf4772b862c5202c651982947f2f2e368c5d0046cbd49c667e24254449  (대조군 — ㉠ 제거 + ㉡ 계약 문언 리터럴)
sha256(u16-order-ctrl-g1first-v219e3.py)=8aca665fb9be752d8450787c79d55fb102093fe3cc97d9377243ce94776f4da5 (⑳ⓑ 순서 대조군)
sha256(u16-ctrl-shallow-global.py)=5b4bdda01866ff62e03e6edf5730cd7cc881295c89c472cdaf581fb9635512e9 (「얕음=전역」 문자 구현 대조군)
sha256(u16-full-exec-v219e2.py)=cca1d6d7e491a7941f82897ea834655ab6494eff94cae15c70939435ac709482   (직전 실행기 — ㉡+무력화만 · c83e44db 증거의 것)
계약 U-16-d 전순서: 1 CONSUMER_ABSENT · 2 PROVENANCE_UNVERIFIABLE · 3 APPROVAL_MALFORMED · 4 APPROVAL_MISSING · 5 SAME_COMMIT · 6 AFTER · 7 CONTENT_DRIFT · 8 HEAD_INVALID · 9 ROW_MUTATED · 10 UNBOUND · 11 ORDER_INVALID · 12 NO_ROWS_CLEAR

########## [E10]-U16-1 c_APP 축 — replace --graft ⇒ ㉠ 불일치 → PROVENANCE_UNVERIFIABLE(2) ##########
H0=62c3c06ffbecdf36ae94e23976b9f889c3a08734 X=2d44f606717e438c84bfb860e2fb2020767fd2ba CN=65f2f13087642c8c57e2ff8d3f8d60250ffcffd1 Y=9fdf684c8833560759a2cc6301a1a43ddc4ba2dd M=HEAD=ced8a77cc3c542847cb6c67f5ffb9f5a1d052083
-- graft «전» (진실 = APPROVAL_MALFORMED(3) · |c_APP|=2) --
  ㉠ 재파생=[65f2f13087642c8c57e2ff8d3f8d60250ffcffd1 9fdf684c8833560759a2cc6301a1a43ddc4ba2dd ] · ㉠ 이력 뷰 %P=[65f2f13087642c8c57e2ff8d3f8d60250ffcffd1 9fdf684c8833560759a2cc6301a1a43ddc4ba2dd] · ㉡ replace -l=[] · <git-dir>/info/grafts=ABSENT · 리터럴 .git/info/grafts=ABSENT · ㉢ is_shallow=false
  *   ced8a77 M: merge sibling identical approval introduction
  |\  
  | * 9fdf684 Y: approval row A (byte-identical) [side y]
  * | 65f2f13 CN: NO transition (child of X)
  * | 2d44f60 X: approval row A [side x]
  |/  
  * 62c3c06 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e3.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · <git-dir>/info/grafts=ABSENT · ㉢ is_shallow=False · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=ced8a77 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('2d44f60', '65f2f13', 'YES->NO'), ('9fdf684', 'ced8a77', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=2', ['9fdf684', '2d44f60'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=2 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['9fdf684', '2d44f60']
  · edge#1[r1 2d44f60->65f2f13 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
  · edge#2[r1 9fdf684->ced8a77 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['9fdf684', '2d44f60'] · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1

$ git -C <fixture> replace --graft ced8a77cc3c542847cb6c67f5ffb9f5a1d052083 65f2f13087642c8c57e2ff8d3f8d60250ffcffd1     # 형제 도입 Y 를 숨긴다
  ㉠ 재파생=[65f2f13087642c8c57e2ff8d3f8d60250ffcffd1 9fdf684c8833560759a2cc6301a1a43ddc4ba2dd ] · ㉠ 이력 뷰 %P=[65f2f13087642c8c57e2ff8d3f8d60250ffcffd1] · ㉡ replace -l=[ced8a77cc3c542847cb6c67f5ffb9f5a1d052083 ] · <git-dir>/info/grafts=ABSENT · 리터럴 .git/info/grafts=ABSENT · ㉢ is_shallow=false
  * ced8a77 M: merge sibling identical approval introduction
  | * b34333c M: merge sibling identical approval introduction
  |/  
  * 65f2f13 CN: NO transition (child of X)
  * 2d44f60 X: approval row A [side x]
  * 62c3c06 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e3.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=['ced8a77'] · <git-dir>/info/grafts=ABSENT · ㉢ is_shallow=False · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=ced8a77 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('2d44f60', '65f2f13', 'YES->NO'), ('9fdf684', 'ced8a77', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=2', ['9fdf684', '2d44f60'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=2 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 1건: [('ced8a77', ['65f2f13', '9fdf684'], ['65f2f13'])]

[상태 귀속] 계약 U-16-d 순서 적용
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: [('ced8a77', ['65f2f13', '9fdf684'], ['65f2f13'])]
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED] git replace -l 비공집합(['ced8a77']) — 부모 집합 재작성 = 신뢰 불가
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['9fdf684', '2d44f60']
  · edge#1[r1 2d44f60->65f2f13 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
  · edge#2[r1 9fdf684->ced8a77 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ global — [PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: [('ced8a77', ['65f2f13', '9fdf684'], ['65f2f13'])] · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_MALFORMED']
u16_rc=1

########## [E10]-U16-2 C_R 축 — <git-dir>/info/grafts ⇒ ㉠ 불일치 → PROVENANCE_UNVERIFIABLE(2) (자기신고: cat-file 은 grafts 미적용) ##########
  ㉠ 재파생=[65f2f13087642c8c57e2ff8d3f8d60250ffcffd1 9fdf684c8833560759a2cc6301a1a43ddc4ba2dd ] · ㉠ 이력 뷰 %P=[65f2f13087642c8c57e2ff8d3f8d60250ffcffd1] · ㉡ replace -l=[] · <git-dir>/info/grafts=present · 리터럴 .git/info/grafts=present · ㉢ is_shallow=false
  * ced8a77 M: merge sibling identical approval introduction
  * 65f2f13 CN: NO transition (child of X)
  * 2d44f60 X: approval row A [side x]
  * 62c3c06 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e3.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · <git-dir>/info/grafts=present · ㉢ is_shallow=False · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=ced8a77 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('2d44f60', '65f2f13', 'YES->NO'), ('9fdf684', 'ced8a77', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['2d44f60'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 1건: [('ced8a77', ['65f2f13', '9fdf684'], ['65f2f13'])]

[상태 귀속] 계약 U-16-d 순서 적용
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: [('ced8a77', ['65f2f13', '9fdf684'], ['65f2f13'])]
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
  · edge#1[r1 2d44f60->65f2f13 YES->NO]: COVERED by c_APP=2d44f60 C_R={62c3c06}
  · edge#2[r1 9fdf684->ced8a77 YES->NO]: COVERED by c_APP=2d44f60 C_R={62c3c06}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ global — [PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: [('ced8a77', ['65f2f13', '9fdf684'], ['65f2f13'])] · 발화 전체=['PROVENANCE_UNVERIFIABLE']
u16_rc=1

########## [E10]-U16-3 **㉡ 열거가 «놓치는» 표면** — --separate-git-dir + grafts: ㉠ 는 잡고 계약 문언 리터럴 ㉡ 구현은 «샌다» ##########
  rev-parse --git-dir = /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82g/sepgd
  ㉠ 재파생=[edab17de962b3ddf147753a095d43e8f6a539978 df4a39fed7988177ec6b99922e16d76f165f6193 ] · ㉠ 이력 뷰 %P=[edab17de962b3ddf147753a095d43e8f6a539978] · ㉡ replace -l=[] · <git-dir>/info/grafts=present · 리터럴 .git/info/grafts=ABSENT · ㉢ is_shallow=false
-- (a) v2.19-3 판정 실행기(㉠ 포함) --
  * a2ff3ae M: merge sibling identical approval introduction
  * edab17d CN: NO transition (child of X)
  * e350487 X: approval row A [side x]
  * 47a7b35 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e3.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · <git-dir>/info/grafts=present · ㉢ is_shallow=False · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=a2ff3ae is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('df4a39f', 'a2ff3ae', 'YES->NO'), ('e350487', 'edab17d', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['e350487'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 1건: [('a2ff3ae', ['df4a39f', 'edab17d'], ['edab17d'])]

[상태 귀속] 계약 U-16-d 순서 적용
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: [('a2ff3ae', ['df4a39f', 'edab17d'], ['edab17d'])]
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
  · edge#1[r1 df4a39f->a2ff3ae YES->NO]: COVERED by c_APP=e350487 C_R={47a7b35}
  · edge#2[r1 e350487->edab17d YES->NO]: COVERED by c_APP=e350487 C_R={47a7b35}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ global — [PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: [('a2ff3ae', ['df4a39f', 'edab17d'], ['edab17d'])] · 발화 전체=['PROVENANCE_UNVERIFIABLE']
u16_rc=1
-- (b) 대조군: ㉠ 제거 + ㉡ 리터럴 .git/info/grafts (계약 문언 그대로) --
  * a2ff3ae M: merge sibling identical approval introduction
  * edab17d CN: NO transition (child of X)
  * e350487 X: approval row A [side x]
  * 47a7b35 H0: base (r1=YES · reviewer digest)
$ python3 u16-ctrl-obs-literal.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · <git-dir>/info/grafts=ABSENT · ㉢ is_shallow=False · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=a2ff3ae is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('df4a39f', 'a2ff3ae', 'YES->NO'), ('e350487', 'edab17d', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['e350487'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 1건: [('a2ff3ae', ['df4a39f', 'edab17d'], ['edab17d'])]

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 df4a39f->a2ff3ae YES->NO]: COVERED by c_APP=e350487 C_R={47a7b35}
  · edge#2[r1 e350487->edab17d YES->NO]: COVERED by c_APP=e350487 C_R={47a7b35}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## [E10]-U16-4 ㉢ 국소 — ⑳ⓑ 얕은 클론: 후보 우주 «안» ⇒ PROVENANCE_UNVERIFIABLE(2) · 순서 대조군은 3 (판별력 유지) ##########
  is_shallow=true · .git/shallow=d830ccb4c670dc4eafb98625d9a1f9608014639c 
  ㉠ 재파생=[afb7171e45ba887e0f867f1738005b549c538262 196776c457ac78004c4ae2a6d041d440932146ca ] · ㉠ 이력 뷰 %P=[] · ㉡ replace -l=[] · <git-dir>/info/grafts=ABSENT · 리터럴 .git/info/grafts=ABSENT · ㉢ is_shallow=true
  * d830ccb M: merge sibling identical approval introduction
$ python3 u16-full-exec-v219e3.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · <git-dir>/info/grafts=ABSENT · ㉢ is_shallow=True · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=d830ccb is_shallow=True .git/shallow=['d830ccb'] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('afb7171', 'd830ccb', 'ABSENT->NO'), ('196776c', 'd830ccb', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=0(+경계 1)', [])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=0 경계커밋=['d830ccb'] g4_bad=False g2_bad=False 대응간선=0 row_id간선=2
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: PROVENANCE_UNVERIFIABLE(2) — |c_APP|=0 (도입 지점 파생 불가)
  · edge#1[r1 afb7171->d830ccb ABSENT->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
  · edge#2[r1 196776c->d830ccb ABSENT->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ row[r1/YES->NO] — |c_APP|=0 (도입 지점 파생 불가) · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_MISSING']
u16_rc=1
-- 순서 대조군(«g1·g4 먼저») --
  * d830ccb M: merge sibling identical approval introduction
$ python3 u16-order-ctrl-g1first-v219e3.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · <git-dir>/info/grafts=ABSENT · ㉢ is_shallow=True · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=d830ccb is_shallow=True .git/shallow=['d830ccb'] EVAL_ORDER=g1-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('afb7171', 'd830ccb', 'ABSENT->NO'), ('196776c', 'd830ccb', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=0(+경계 1)', [])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=0 경계커밋=['d830ccb'] g4_bad=False g2_bad=False 대응간선=0 row_id간선=2
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — 고아 — 대응 간선 0 (row_id 간선 2 · g1 transition 전건 불일치)
  · edge#1[r1 afb7171->d830ccb ABSENT->NO]: APPROVAL_MALFORMED(3) — g1 YES->NO≠ABSENT->NO (후보 1 · 대응 1)
  · edge#2[r1 196776c->d830ccb ABSENT->NO]: APPROVAL_MALFORMED(3) — g1 YES->NO≠ABSENT->NO (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — 고아 — 대응 간선 0 (row_id 간선 2 · g1 transition 전건 불일치) · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1

########## [E10]-U16-5 ㉢ 국소 — «얕지만 경계가 후보 우주 «밖»» ⇒ NO_ROWS_CLEAR/0 · 「얕음=전역」 문자 구현 대조군은 «밖»에서도 2 를 내 실패 ##########
  is_shallow=true · .git/shallow=dcce5da23fb417b2c946059fde56515fa96cc11c   (경계 = c1 — 후보 우주 «밖»)
-- (a) v2.19-3 판정 실행기 (㉢ 국소) --
  * b6bfac1 e: YES->NO
  * 3d587b7 A: approval row (aah=R)
  * 468427c H0: register r1=YES
  * 524d5a4 R: reviewer artifact (digest)
  * dcce5da c1: seed1
$ python3 u16-full-exec-v219e3.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · <git-dir>/info/grafts=ABSENT · ㉢ is_shallow=True · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=b6bfac1 is_shallow=True .git/shallow=['dcce5da'] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('3d587b7', 'b6bfac1', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['3d587b7'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 3d587b7->b6bfac1 YES->NO]: COVERED by c_APP=3d587b7 C_R={524d5a4}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0
-- (b) 대조군: 「얕음 = 전역」 문자 구현 --
  * b6bfac1 e: YES->NO
  * 3d587b7 A: approval row (aah=R)
  * 468427c H0: register r1=YES
  * 524d5a4 R: reviewer artifact (digest)
  * dcce5da c1: seed1
$ python3 u16-ctrl-shallow-global.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · <git-dir>/info/grafts=ABSENT · ㉢ is_shallow=True · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=b6bfac1 is_shallow=True .git/shallow=['dcce5da'] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('3d587b7', 'b6bfac1', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['3d587b7'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · global: PROVENANCE_UNVERIFIABLE(2) — [대조군] 얕은 클론 자체를 전역 위반으로 읽음(E6 국소화 미적용)
  · edge#1[r1 3d587b7->b6bfac1 YES->NO]: COVERED by c_APP=3d587b7 C_R={524d5a4}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ global — [대조군] 얕은 클론 자체를 전역 위반으로 읽음(E6 국소화 미적용) · 발화 전체=['PROVENANCE_UNVERIFIABLE']
u16_rc=1

########## [E10]-U16-6 정상 회귀 — replace 0 · grafts 부재 · shallow=false ⇒ 직전 판과 «불변» ##########
-- ⑳ⓐ 원본 → APPROVAL_MALFORMED(3) --
  ㉠ 재파생=[afb7171e45ba887e0f867f1738005b549c538262 196776c457ac78004c4ae2a6d041d440932146ca ] · ㉠ 이력 뷰 %P=[afb7171e45ba887e0f867f1738005b549c538262 196776c457ac78004c4ae2a6d041d440932146ca] · ㉡ replace -l=[] · <git-dir>/info/grafts=ABSENT · 리터럴 .git/info/grafts=ABSENT · ㉢ is_shallow=false
  *   d830ccb M: merge sibling identical approval introduction
  |\  
  | * 196776c Y: approval row A (byte-identical) [side y]
  * | afb7171 CN: NO transition (child of X)
  * | 8292d21 X: approval row A [side x]
  |/  
  * 8bc87a3 H0: base (r1=YES · reviewer digest)
$ python3 u16-full-exec-v219e3.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · <git-dir>/info/grafts=ABSENT · ㉢ is_shallow=False · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=d830ccb is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('8292d21', 'afb7171', 'YES->NO'), ('196776c', 'd830ccb', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=2', ['196776c', '8292d21'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=2 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['196776c', '8292d21']
  · edge#1[r1 8292d21->afb7171 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
  · edge#2[r1 196776c->d830ccb YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['196776c', '8292d21'] · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1
-- ⑱ 정정 문언(같은 row_id·다른 승인 행·형제 도입→merge) → NO_ROWS_CLEAR/0 --
자동 병합: LEDGER.md
충돌 (내용): LEDGER.md에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
  * 1806aaf e2: YES->NO
  * 4aa3bb7 back to YES
  * dd00f4d e1: ABSENT->NO
  *   89876c3 MA: merge sibling approval introductions
  |\  
  | * e9cc007 A2: approval (YES->NO, rationale b)
  * | dcb16b0 A1: approval (ABSENT->NO, rationale a)
  |/  
  * 563c13f H0: r1 absent (reviewer digest)
$ python3 u16-full-exec-v219e3.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · <git-dir>/info/grafts=ABSENT · ㉢ is_shallow=False · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=1806aaf is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('4aa3bb7', '1806aaf', 'YES->NO'), ('89876c3', 'dd00f4d', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'ABSENT->NO', '|c_APP|=1', ['dcb16b0']), ('r1', 'YES->NO', '|c_APP|=1', ['e9cc007'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/ABSENT->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
  row r1/YES->NO raw#1: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
[PARENTS-UNTRUSTED ㉠] 재파생 대조 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 4aa3bb7->1806aaf YES->NO]: COVERED by c_APP=e9cc007 C_R={563c13f}
  · edge#2[r1 89876c3->dd00f4d ABSENT->NO]: COVERED by c_APP=dcb16b0 C_R={563c13f}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0
```

---
## 5. 관측 보고 · **신규** 계약 결함 후보 (고치지 않는다 — `bound_paths` 동결 · 다음 에라타 대상)

> addendum-2(`c83e44db`)의 **M-1**(전역/국소 충돌)·**M-5**(`P_first` 카디널리티)는 에라타 3차가 **E10**·**E11** 로 처분했고, **M-3**(열거는 열린-세계) 권고는 **㉠ 구조 재파생**으로 채택됐다.
> §3·§4 가 그 처분값을 실측으로 확인했다(전건 일치). 아래는 **이번 addendum 실행에서 «새로» 관측된 것**뿐이다.

### K-1 (문언 공백 — 판별력 직결) — ㉠ 불일치가 «얕은 경계»에서도 성립한다: ㉠(전역)과 ㉢(국소)의 관할이 미규정

- **실측**(§4-1 `[E11]-2` 프로브): `--depth 1` 얕은 클론에서 **㉠ 재파생 = `[e117ec2…]`** 인데 **㉠ 이력 뷰 `%P` = `[]`** 다 — 커밋 «객체»는 진짜 부모를 담고 있으나 shallow graft 가 뷰에서 부모를 지우기 때문이다. 즉 **얕은 클론은 그 자체로 ㉠ 불일치를 만든다**.
- **문언**: 계약 `f6493d23` `U-16-c` ㉠ 은 «재파생 집합이 `git rev-list`/`%P` 가 준 부모와 **불일치**하면 … `PROVENANCE_UNVERIFIABLE`/`PREVENTION_UNVERIFIABLE`»(전역)이고, ㉢ 은 «부모 «객체» 조회 실패 … **«그 후보만» 국소 차단**»이다. **한 상황이 두 항에 동시에 해당할 때 어느 쪽이 관할인지 적혀 있지 않다.**
- **귀결**: ㉠ 을 문자 그대로 «전역»으로 적용하면 **얕은 클론은 후보 우주와 무관하게 항상 전역 `UNVERIFIABLE`** 이 되어 **E6 국소화와 `T-82 ⑳ⓑ` 의 2 vs 3 판별력이 다시 무너진다** — addendum-2 **M-1** 이 지적하고 E10 이 «전역/국소 분할»로 고쳤다고 선언한 바로 그 자리가, ㉠ 신설로 **다른 경로로 재발**한다.
- **본 실행기의 독해(명시)**: **㉠ 불일치가 `.git/shallow` 경계 커밋에서 비롯되면 전역으로 승격하지 않고 ㉢(국소)이 담당**한다(`check_parents()` 의 shallow 예외). 이 독해로 `[E10]-U16-4`(후보 우주 «안» → 2, 순서 대조군 3)와 `[E10]-U16-5`(후보 우주 «밖» → `NO_ROWS_CLEAR`/0)가 **둘 다** 성립했다(실측).
- **처분 제안**: ㉠ 에 «단, 불일치의 원인 커밋이 ㉢ 의 얕은 경계이면 ㉢ 이 관할한다(전역 승격 없음)» 를 명시. **극성 근거**: per-commit 특정 가능성이 전역/국소를 가르는 유일 기준이며(E10 이 세운 논거), 얕은 경계는 `.git/shallow` 로 특정 가능하다.

### K-2 (문언 리터럴 — fail-open 실증) — ㉡ 의 «`.git/info/grafts` 부재» 리터럴이 `--separate-git-dir` 구성에서 **항상 통과**한다

- **실측**(§4-1 `[E10]-4` · §4-2 `[E10]-U16-3`): `git init --separate-git-dir` 로 만든 작업트리에서 `.git` 은 **파일**(gitdir 포인터)이라 **리터럴 `.git/info/grafts` 는 ABSENT**인데 실제 `<git-dir>/info/grafts` 는 **present** 이고 `%P` 는 재작성돼 있다. `git replace -l` 도 **공집합**이다.
- **대조군 결과**: ㉠ 을 제거하고 ㉡ 을 **계약 문언 리터럴대로** 구현한 대조군은 같은 픽스처에서 **`PREVENTION_ACTIVE`/0**(U-17) · **`NO_ROWS_CLEAR`/0**(U-16) 를 냈다 — **완전한 fail-open**. 같은 픽스처에서 v2.19-3(㉠ 포함)은 **`PREVENTION_UNVERIFIABLE`/`PROVENANCE_UNVERIFIABLE`** 로 차단했다.
- **처분 제안**: ㉡ 의 리터럴을 **«`git rev-parse --absolute-git-dir` 파생 `<git-dir>/info/grafts`»** 로 정정(본 실행기는 이미 파생으로 읽는다). **이 건은 «㉠ 이 주 판별»이라는 E10 의 설계가 옳았음을 동시에 실증**한다 — ㉡ 이 새면 ㉠ 이 받는다.

### K-3 (관측 — 계약 설계 지지) — 제3 재작성 표면 `GIT_REPLACE_REF_BASE` 는 실재하고, ㉠ 은 «환경 무관»하게 잡는다

- **실측**(§4-1 A-(4)·`[E10]-3`): `refs/evil/<sha>` 에 replace 객체를 두고 `GIT_REPLACE_REF_BASE=refs/evil/` 를 주면 `%P` 가 재작성된다. 이때 ㉠ 재파생은 **원본 부모**를 반환하고(환경 무관), ㉡ `git replace -l` 은 **그 환경을 물려받았을 때만** 비공집합이 된다.
- ⇒ M-3 이 요구한 «열거 밖 표면»이 실재했고, **㉠ 이 하나의 술어로 네 표면(replace·grafts·REF_BASE·separate-git-dir)을 전부 잡았다**. 계약이 ㉠ 을 «주», ㉡ 을 «보조»로 둔 것이 실측으로 지지된다.

### K-4 (정직 경계) — ㉠ 은 «후보 우주»에 한정 적용된다

- 계약 문언은 «각 후보 `x` 의 부모 집합을 … 재파싱»이고 본 실행기도 후보 우주(경로별 `rev-list --full-history` 축소분)에만 ㉠ 을 적용한다 — 실측 라인 `U17-PU㉠ 재파생 대조: 검사 후보 2~4건`. **후보 우주 «밖» 커밋의 재작성은 검사되지 않는다.**
- 지금 판의 픽스처에서는 재작성 대상이 항상 후보 우주 안이라 문제가 드러나지 않았다. **판정에 쓰이는 조상성(`merge-base --is-ancestor`)은 후보 밖 커밋의 부모도 소비**하므로, 원리상 «후보 밖만 재작성»하는 구성이 남는다. 다만 그 경우 `∀p` 항 자체는 재파생을 쓰므로 도입 지점 판정은 오염되지 않는다 — **잔여는 조상성 축**이며, `--no-replace-objects` 전역 고정(② 무력화)이 그 축을 덮는다(본 실행기는 `export GIT_NO_REPLACE_OBJECTS=1` / `git --no-replace-objects` 전 호출). **grafts 는 그 무력화로 꺼지지 않으므로 이 잔여가 실재**한다 — 비차단 정직 표기.

### K-5 (관측 — 결함 아님) — `[E11]` 세 처분이 «상보·결정적»으로 실측됐다

- `|P_first|=0` ∧ 부재 → `ABSENT`(2) · `|P_first|=0` ∧ 존재 → `UNVERIFIABLE`(1) · `|P_first|=2` → `∀x` 가 **∃-증인**으로 접혀 ¬LATE(→ `ACTIVE`) 또는 LATE 를 **결정적으로** 낸다(§4-1 `[E11]`-1·-2·-3·-3b). 상보성 4종도 정확히 하나씩 나왔다. **신규 상태 없이 처리된다**는 계약 주장이 실측으로 확인됐다.

---
## 6. 사후 검증 원문 (repo 무영향 · HEAD 불변 · S-24 재확인 · 본 저장소 ㉠㉡㉢ 통과 · 픽스처 격리)

```text
post_utc=2026-08-19T03:14:41Z
$ git -C <repo> rev-parse HEAD
f6493d23b95f45b62063c30a3ad47fc1c23f3738
$ git -C <repo> status --short
 M uv.lock
?? tools/spikes/
$ git -C <repo> diff --quiet f6493d23 -- <계약>  → rc
rc=0
$ git -C <repo> rev-list --count f6493d23..HEAD -- <계약>
0
$ sed -n '4614,4714p' <워킹트리 계약> | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git -C <repo> show f6493d23:<계약> | sed -n '4614,4714p' | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git -C <repo> show ad5be1a3:<계약> | sed -n '4608,4708p' | shasum -a 256   (직전 판 — byte-동일 확인)
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git -C <repo> reflog -n 3
f6493d23 HEAD@{0}: commit: docs(tos): phase0 completion contract v2.19 errata #3 — [PARENTS-UNTRUSTED] structural re-derivation (global/local split), P_first cardinality
c83e44db HEAD@{1}: commit: docs(tos): record v2.19 errata #2 addendum evidence (S-24 — [PARENTS-UNTRUSTED] graft/grafts · P ∀-parent · complementarity)
ad5be1a3 HEAD@{2}: commit: docs(tos): phase0 completion contract v2.19 errata #2 — [PARENTS-UNTRUSTED] (replace/graft), P_first/P_last ∀-parent structural definition
--- [E10] 본 저장소 자체의 부모 신뢰 관측 (㉠㉡㉢) ---
$ git -C <repo> replace -l
(빈 출력 = 공집합)
$ ls $(git -C <repo> rev-parse --absolute-git-dir)/info/grafts
ls: /Users/harris/Development/private/kis_unified_sts/.git/info/grafts: No such file or directory
(ABSENT)
$ git -C <repo> rev-parse --is-shallow-repository
false
$ ㉠ 재파생 cat-file parent (HEAD) = c83e44db10abf707dc3a576a8a3c787d9f46f2ee 
$ ㉠ 이력 뷰 %P (HEAD)            = c83e44db10abf707dc3a576a8a3c787d9f46f2ee
  ⇒ ㉠ 일치 · ㉡ 공집합/부재 · ㉢ 얕지 않음 — 본 저장소는 [PARENTS-UNTRUSTED] 를 통과하는 상태
--- 픽스처 격리 ---
$ find <scratchpad addendum-3 fixtures> -maxdepth 3 -name .git | wc -l
      19
```

**판독**: HEAD `f6493d23` 불변 · 계약 워킹트리 = 에라타 3차 blob(`git diff --quiet` rc=0) · `f6493d23..HEAD` 계약 커밋 0 · 하니스 블록 `sed -n '4614,4714p'` sha256 이 워킹트리·`f6493d23` 양쪽에서
**`957bf49d…`** 이고 **`ad5be1a3:4608-4708` 과도 동일**(§1 ④ 와 이중 확인) · 워킹트리 변경은 실행 «전»부터 있던 `uv.lock`·`tools/spikes/` 뿐(본 실행이 만든 것 0 — 선행 증거 4파일은 `90a5ce7d`·`197f4fe4`·`c83e44db` 로 이미 커밋됐다) ·
**본 저장소는 ㉠ 재파생 == 이력 뷰 · ㉡ `git replace -l` 공집합 ∧ `<git-dir>/info/grafts` 부재 · ㉢ `--is-shallow-repository=false`** ⇒ `[PARENTS-UNTRUSTED]` 를 통과하는 상태이고,
`replace`/`grafts`/`--separate-git-dir`/`GIT_REPLACE_REF_BASE` 조작은 **전부 scratchpad 픽스처 안에서만** 이뤄졌다 · addendum-3 픽스처 git 저장소 19개는 전부 scratchpad 하위(`fx84g/*`·`fx82g/*`)다.
**서버 접근**: U-17 축은 SIMULATED seam(`responder=file:`)과 본 저장소 live 1회(GET `gh api --hostname github.com …`)뿐이고 U-16 축은 GitHub 조회 0 이다 ⇒ **서버 쓰기·설정 변경 0**.
