# U17-PREVENTION-CHECK-V219-ADDENDUM-8 — addendum-7 «㉠ 자연 침묵 증명»의 **graft-전 후보 집합** 결함 시인·철회·재실행 (stop-time BLOCK #6 채택)

- 계약 결속: **v2.19 에라타 6차 재동결 `359f5bc5`** (본 addendum 은 계약을 **바꾸지 않는다** — §1)
- 선행 증거: `U17-PREVENTION-CHECK-V219.md`(`d5a8302a` 결속) · ADDENDUM-1~7 (`e3ed4e78`·`ad5be1a3`·`f6493d23`·`db6ce918`·`eddbd241`·`359f5bc5` 결속). **(4d) 불변 규율**에 따라 기존 파일은 편집하지 않고 본 파일로 정정한다.
- 서버 쓰기·설정 변경 **0** · GitHub 는 **GET-only**(본 파일의 실행은 U-17 축이 `file:` seam 응답기, U-16 축이 순수 in-repo — **live 조회 0**) · 픽스처는 scratchpad **독립 git 저장소**(본 저장소 무접촉·worktree 미사용).

## 0. 철회 고지 (stop-time Codex BLOCK #6 — 채택)

지적 원문의 요지: **addendum-7 의 U-16 축 «㉠ 자연 침묵 증명»이 후보 집합을 `grafts` 주입 «전» 에 계산해 `C_R=[]` 로 기록했는데, 주입 «후» 의 실제 뮤턴트 실행은 `C_R={6de2472…}` 를 소비한다. 따라서 «㉠ 대상 전건 raw parent == %P» 증명에서 실제 후보 하나가 누락됐다.**

**전건 채택한다.** 실측으로 확인한 사실은 다음과 같다.

| # | 실측 | 원문 위치 |
| --- | --- | --- |
| 1 | addendum-7 의 U-16 드라이버는 후보 집합을 `grafts` 주입 **이전** 에 방출했다 | 드라이버 원문 `…-ADDENDUM-7.md:256-264` (후보 계산) vs `:275` (grafts 주입) |
| 2 | 그 방출값은 `C_R ㉠-검사 후보(리뷰어 blob 일치) = []` — **빈 집합** | `…-ADDENDUM-7.md:521` |
| 3 | 그러나 실행기는 같은 픽스처에서 `C_R={6de2472}` 를 **실제로 소비**했다 | `…-ADDENDUM-7.md:552`(정직 실행) · `:589-590`(뮤턴트 실행) · `:621-622`(판정기 실행) |
| 4 | U-17 축 드라이버도 **같은 배치 결함**(후보 계산 `:157-163` → grafts 주입 `:175`)을 갖는다 | `…-ADDENDUM-7.md:157-163` vs `:175` |

**철회 대상**: addendum-7 §4-2 의 «㉠ 자연 침묵 증명» 블록(U-16 축) 및 §0/§4-1 의 U-17 축 동종 블록 — 즉 **«㉠ 후보 집합과 각 원소의 부모 대조» 라는 *증명 방식의 그 실행 기록*** 을 철회한다. 근거 데이터가 «실행기가 실제로 소비한 집합» 이 아니라 «드라이버가 주입 전에 독립 재계산한 집합» 이었기 때문이다.

**철회하지 않는 것**: addendum-7 의 상태값·rc 원문(정직/뮤턴트/판정기 실행 결과 자체)과 §2 의 «단일 변수» diff 원문. 이들은 실행기의 실제 stdout 이며 본 파일의 재실행에서 **동일하게 재현**됐다(§2·§6).

**본 파일이 대체하는 방식**: 후보 집합을 드라이버가 재계산하지 않는다. **실행기가 실제로 호출한 `git cat-file commit <x>` 를 shim 으로 추적**해 «실행기가 순회한 x» 를 **기계적으로** 얻고(하한이자 상한), 그 전건에 대해 `--no-replace-objects cat-file` 부모 ↔ 이력 뷰 `%P` 를 대조한다. 대조 대상 저장소는 **addendum-7 이 실제로 소비한 그 픽스처의 사본**(원본 무변경)이므로 `6de2472…` 가 **문자 그대로** 포함된다.

### 결과 요약 (stdout·rc 원문 그대로 — §6 에 전문)

| 축 | 저장소 | 실행기 | 상태값 | rc | 추적된 ㉠ 대상 x | 전건 `cat-file`==`%P` |
| --- | --- | --- | --- | --- | --- | --- |
| **U-16** | addendum-7 픽스처 사본 · **grafts 주입 후** | **단일 변수 뮤턴트** | **`NO_ROWS_CLEAR`**(12) | **0** ← fail-open | `6de2472` `76f2cad` `cc9f2db` `f05cb2b` (4) | **YES** |
| U-16 | 〃 | 판정기(E15) | `PROVENANCE_UNVERIFIABLE`(2) | 1 | 동일 4건 | YES |
| U-16 | 〃 · grafts 치움(정직) | 판정기(E15) | `PROVENANCE_UNVERIFIABLE`(2) | 1 | 동일 4건 | YES |
| **U-17** | addendum-7 픽스처 사본 · **grafts 주입 후** | **단일 변수 뮤턴트** | **`PREVENTION_ACTIVE`**(10) | **0** ← fail-open | `465e8ae` `90d40ff` `a44dbd5` (3) | **YES** |
| U-17 | 〃 | 판정기(E15) | `PREVENTION_UNVERIFIABLE`(1) | 1 | 동일 3건 | YES |
| U-17 | 〃 · grafts 치움(정직) | 판정기(E15) | `PREVENTION_LATE`(6) | 1 | 동일 3건 | YES |
| U-16 | **신규 픽스처**(재구성) · graft **전/후** 양쪽 방출 | 판정기/뮤턴트 | `PROVENANCE_UNVERIFIABLE` / **`NO_ROWS_CLEAR`(rc 0)** / `PROVENANCE_UNVERIFIABLE` | 1/**0**/1 | 전·후 동일 4건 | YES (전·후 모두) |
| U-17 | **신규 픽스처**(재구성) · graft **전/후** 양쪽 방출 | 판정기/뮤턴트 | `PREVENTION_LATE` / **`PREVENTION_ACTIVE`(rc 0)** / `PREVENTION_UNVERIFIABLE` | 1/**0**/1 | 전·후 동일 3건 | YES (전·후 모두) |

→ **결론 등급 = (a)**: graft «후» 후보 집합의 **전건**에서 `cat-file` 부모 == `%P`. ㉠ 는 **자연히 침묵**했고, 따라서 addendum-7 의 «단일 변수 뮤턴트만으로 green 이 나온다 = 옛 `--absolute-git-dir` 결합 분기는 도달 가능한 fail-open» 결론은 **유지**된다(§5).

## 1. S-24 ① — 계약 무변경 선언

본 addendum 은 계약 본문을 편집하지 않는다. 결속 대상은 여전히 `359f5bc5` 이며, 워킹트리 계약과 `359f5bc5` 사이 차분은 **∅** 이다(§7 원문). 하네스 §12.3.4-R 블록 sha256 은 `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d` 로 **불변**(행 오프셋 4631-4731).

## 2. graft «후» ㉠ 대상 집합 — **실행기 추적** 기반 원문

### 2-1. 방법 — 드라이버 재계산 폐기, 실행기 호출 추적

`PATH` 앞단에 아래 shim 을 놓아 실행기가 호출한 `git cat-file commit <x>` 만 기록하고 그대로 실 git 에 위임한다(동작 무변경·`exec`).

```sh
#!/bin/sh
# [추적 shim] 실행기가 호출한 «cat-file commit <x>» 만 기록하고 그대로 실 git 에 위임한다(동작 무변경).
case " $* " in *" cat-file commit "*) printf '%s\n' "$*" >> "$T8TRACE" ;; esac
exec /usr/local/bin/git "$@"
```

- shim sha256 = `e5e5e3cebd7cbe753c79ed3bd4cf02a485f59a0cb282f95547aa21191c682ecc` · 실 git = `/usr/local/bin/git` (`git version 2.38.0`)
- 실행기의 ㉠ 재파생은 **오직** `cat-file commit` 으로 이뤄지므로(`parents_true()` / `parents()`), 추적 집합 = **㉠ 가 검사한 x 전체**. 드라이버의 독립 재계산이 개입할 여지가 없다.

### 2-2. 대상 저장소 = addendum-7 이 «실제로 소비한» 픽스처의 사본 (6de2472 문자 그대로 포함)

```text
-- addendum-7 보존 픽스처 → 사본(원본 무변경) --
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82n/silent
    원본 HEAD=f05cb2b0c9db0a7d7b5e7b6884b9eae781075452 · 사본 HEAD=f05cb2b0c9db0a7d7b5e7b6884b9eae781075452 · 동일? YES
    사본 grafts 원문: 632c2477a95abc9d18fc6a8c94a684d4e738cd31 c3e310d1a7376fbe4170fa810a58a687f5d6361c 6de2472b98c2905a1d70541e6b7869541452082d
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent
    원본 HEAD=90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 · 사본 HEAD=90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 · 동일? YES
    사본 grafts 원문: 97a1860bf6eea145004f1221642b4aa01dfbe9af b0becece68220d2041e568325e47b3a98ca119c3 a44dbd530acc1c1518776701683cd6c4b1fbab10
```

### 2-3. U-16 — graft «후» 추적 집합 전건 대조 (뮤턴트 실행 = 문제의 green 을 낸 그 실행)

```text
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 cc9f2db->76f2cad YES->NO]: COVERED by c_APP=cc9f2db C_R={6de2472}
  · edge#2[r1 6de2472->f05cb2b YES->NO]: COVERED by c_APP=cc9f2db C_R={6de2472}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0
  [U-16 뮤턴트·graft 후] 실행기가 «실제로» cat-file commit 한 x (추적 원문·중복 제거) = [6de2472b98c2905a1d70541e6b7869541452082d 76f2cad92f79e4f70d5c55096a3ef15ce5c89360 cc9f2dbbbcedc3659035b64b2131b8bb04261a41 f05cb2b0c9db0a7d7b5e7b6884b9eae781075452 ]
  [U-16 뮤턴트·graft 후] 호출 횟수 = 29 · 고유 x = 4
  [U-16 뮤턴트·graft 후] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  이력 뷰 %P):
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
    6de2472b98c2  R: reviewer artifact (dige cat-file=[c3e310d1a7376fbe4170fa810a58a687f5d6361c]  %P=[c3e310d1a7376fbe4170fa810a58a687f5d6361c] → 일치
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
    76f2cad92f79  CN: NO transition          cat-file=[cc9f2dbbbcedc3659035b64b2131b8bb04261a41]  %P=[cc9f2dbbbcedc3659035b64b2131b8bb04261a41] → 일치
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
    cc9f2dbbbced  A: approval row (aah=R)    cat-file=[632c2477a95abc9d18fc6a8c94a684d4e738cd31]  %P=[632c2477a95abc9d18fc6a8c94a684d4e738cd31] → 일치
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
    f05cb2b0c9db  M: merge reviewer branch   cat-file=[76f2cad92f79e4f70d5c55096a3ef15ce5c89360 6de2472b98c2905a1d70541e6b7869541452082d]  %P=[76f2cad92f79e4f70d5c55096a3ef15ce5c89360 6de2472b98c2905a1d70541e6b7869541452082d] → 일치
  [U-16 뮤턴트·graft 후] 전건 일치? YES ← ㉠ 자연 침묵 성립(이 실행이 소비한 x 전부)
```

**`6de2472b98c2905a1d70541e6b7869541452082d` 는 대조 대상에 포함되며 `cat-file` 부모 == `%P` 로 일치한다.**

### 2-4. `6de2472…` 는 무엇이고, 왜 `C_R` 에 들어왔나 (실측 기반 설명)

- `6de2472…` = 픽스처의 **`R`: reviewer artifact (digest)** 커밋. 리뷰어 아티팩트 blob 을 도입한 지점이므로 U-16-c 의 `C_R`(= `blob(리뷰어 아티팩트)` 도입 커밋 집합) 후보다.
- `C_R` 은 실행기에서 **간선별로** 계산된다. 정직 이력에서:
  - `edge#1[r1 cc9f2db->76f2cad]` 의 간선 커밋 `CN=76f2cad` 는 `R` 에 **도달하지 못한다** → `C_R=∅` → `PROVENANCE_UNVERIFIABLE(2)`
  - `edge#2[r1 6de2472->f05cb2b]` 의 간선 커밋 `M=f05cb2b` 는 병합 커밋이라 `R` 에 **도달한다** → `C_R={6de2472}` → `APPROVAL_ORDER_INVALID(11)`
  - 원문: `t8xa7v219e8.out` §U-16(c) — `edge#1 … C_R={}` / `edge#2 … C_R={6de2472}`
- `grafts` 주입 후에는 `CN` 도 `R` 에 도달하므로(`is-ancestor(R,CN)` rc **1 → 0**) **두 간선 모두** `C_R={6de2472}` 가 되고, 승인 행이 진 조상 증인을 얻어 `COVERED` → `NO_ROWS_CLEAR(12)` = **green**.
- 따라서 addendum-7 드라이버의 `C_R=[]` 는 **graft 효과가 아니라 드라이버의 열거 범위 오류**였다: 드라이버는 `C_R` 을 `rev-list CN` 하나로만 열거했고(`…-ADDENDUM-7.md:262`), 실행기는 **간선별**(`CN` 과 `M`)로 열거한다. 그래서 `6de2472` 는 **정직 실행에서도 이미** 소비되고 있었다(`…-ADDENDUM-7.md:552`). 본 파일의 추적 방식은 이 오류 종류를 구조적으로 제거한다.

### 2-5. U-17 — graft «후» 추적 집합 전건 대조 (뮤턴트 실행 · 로그 안의 `…/.git/.git/shallow` 가 바로 철회된 결합 base 의 산물)

```text
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 97a1860bf6eea145004f1221642b4aa01dfbe9af:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=465e8aed14031b68dc1da2006ef3fed85a0f18e3 head=97a1860bf6eea145004f1221642b4aa01dfbe9af merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e7/rs
u17_rc=0
  [U-17 뮤턴트·graft 후] 실행기가 «실제로» cat-file commit 한 x (추적 원문·중복 제거) = [465e8aed14031b68dc1da2006ef3fed85a0f18e3 90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 a44dbd530acc1c1518776701683cd6c4b1fbab10 ]
  [U-17 뮤턴트·graft 후] 호출 횟수 = 18 · 고유 x = 3
  [U-17 뮤턴트·graft 후] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  이력 뷰 %P):
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
    465e8aed1403  d: introduce config/tos_co cat-file=[97a1860bf6eea145004f1221642b4aa01dfbe9af]  %P=[97a1860bf6eea145004f1221642b4aa01dfbe9af] → 일치
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
    90d40ff8bd4b  M: merge artifact branch   cat-file=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10]  %P=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10] → 일치
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
    a44dbd530acc  P: artifact                cat-file=[b0becece68220d2041e568325e47b3a98ca119c3]  %P=[b0becece68220d2041e568325e47b3a98ca119c3] → 일치
  [U-17 뮤턴트·graft 후] 전건 일치? YES ← ㉠ 자연 침묵 성립(이 실행이 소비한 x 전부)

```

### 2-6. 추적 집합은 graft 주입으로 **바뀌지 않았다** (정직 실행과 동일)

`grafts` 는 «어떤 x 가 ㉠ 검사를 받는가» 를 바꾸지 않고 **조상성 판정만** 뒤집었다 — 정직/뮤턴트/판정기 세 실행의 추적 집합이 축별로 **동일**하다(U-16 4건 · U-17 3건, §6 원문 `:81`·`:152`·`:223` / `:304`·`:394`·`:455`). 이는 K-4 정직 경계(«후보 밖 grafts 는 ㉠ 미검사») 의 직접 실측이다.

## 3. 신규 픽스처 재실행 — graft «전» 과 «후» 를 **둘 다** 방출

BLOCK #6 이 요구한 «graft 주입 후 후보 집합 재방출» 을 신규 픽스처에서도 이행했다. 드라이버는 `emit_set()` 을 **주입 전·후 두 번** 호출한다.

### 3-1. U-16 (`t82v219e8.sh`)

```text
  merge-base --is-ancestor R CN → rc=1  (1 = 조상 아님 = 정직)
  [graft 전] c_APP ㉠-검사 후보(원장 행 보유)        = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 c824ea73061c3295106dc251de850ffb739bbe0d 6d75e9115cf13cd2efd42f68a6cbc466387dfa20 ]
  [graft 전] C_R   ㉠-검사 후보(리뷰어 blob 일치·간선 c∈{CN,M} 합집합) = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 ec48e562ae73651e40bf912aabbd4ee14d70ed8a ]
  [graft 전] ㉠ 대상 집합(합집합) = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 6d75e9115cf13cd2efd42f68a6cbc466387dfa20 c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a ]
  [graft 전] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  %P):
    05060ec42596  M: merge reviewer bran cat-file=[c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a]  %P=[c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a] → 일치
    6d75e9115cf1  A: approval row (aah=R cat-file=[908611a678c86d68146f638640e683b2cc0a7a86]  %P=[908611a678c86d68146f638640e683b2cc0a7a86] → 일치
    c824ea73061c  CN: NO transition      cat-file=[6d75e9115cf13cd2efd42f68a6cbc466387dfa20]  %P=[6d75e9115cf13cd2efd42f68a6cbc466387dfa20] → 일치
    ec48e562ae73  R: reviewer artifact ( cat-file=[a1877df7460f2042e3372ad9f33e817e55987135]  %P=[a1877df7460f2042e3372ad9f33e817e55987135] → 일치
  [graft 전] 전건 일치? YES ← ㉠ 자연 침묵 성립
  merge-base --is-ancestor R CN → rc=0  (0 = 뒤집힘)
  --no-replace-objects 하 → rc=0  (여전히 0 = K-4 잔여)
  [graft 후] c_APP ㉠-검사 후보(원장 행 보유)        = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 c824ea73061c3295106dc251de850ffb739bbe0d 6d75e9115cf13cd2efd42f68a6cbc466387dfa20 ]
  [graft 후] C_R   ㉠-검사 후보(리뷰어 blob 일치·간선 c∈{CN,M} 합집합) = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 ec48e562ae73651e40bf912aabbd4ee14d70ed8a ]
  [graft 후] ㉠ 대상 집합(합집합) = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 6d75e9115cf13cd2efd42f68a6cbc466387dfa20 c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a ]
  [graft 후] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  %P):
    05060ec42596  M: merge reviewer bran cat-file=[c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a]  %P=[c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a] → 일치
    6d75e9115cf1  A: approval row (aah=R cat-file=[908611a678c86d68146f638640e683b2cc0a7a86]  %P=[908611a678c86d68146f638640e683b2cc0a7a86] → 일치
    c824ea73061c  CN: NO transition      cat-file=[6d75e9115cf13cd2efd42f68a6cbc466387dfa20]  %P=[6d75e9115cf13cd2efd42f68a6cbc466387dfa20] → 일치
    ec48e562ae73  R: reviewer artifact ( cat-file=[a1877df7460f2042e3372ad9f33e817e55987135]  %P=[a1877df7460f2042e3372ad9f33e817e55987135] → 일치
  [graft 후] 전건 일치? YES ← ㉠ 자연 침묵 성립
```

### 3-2. U-17 (`t84v219e8.sh`)

```text
  merge-base --is-ancestor P d → rc=1  (1 = 조상 아님 = 정직)
  [graft 전] 후보(아티팩트 경로 보유) = [f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 ]
  [graft 전] 후보(config 경로 보유)   = [f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 d1a99fe0599675b2abf2d83d96043bb5935e6246 ]
  [graft 전] ㉠ 대상 집합(합집합) = [8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 d1a99fe0599675b2abf2d83d96043bb5935e6246 f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 ]
  [graft 전] W=7bd0c92807b163095a7af13de3cb746a9c635871 가 집합에 있는가? NO ← ㉠ 대상 아님
  [graft 전] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  %P):
    8c70920d3444  P: artifact              cat-file=[41895b66cfa27c401450aa9cf707791f909a7c0f]  %P=[41895b66cfa27c401450aa9cf707791f909a7c0f] → 일치
    d1a99fe05996  d: introduce config/tos_ cat-file=[7bd0c92807b163095a7af13de3cb746a9c635871]  %P=[7bd0c92807b163095a7af13de3cb746a9c635871] → 일치
    f7c2dfcb71fc  M: merge artifact branch cat-file=[d1a99fe0599675b2abf2d83d96043bb5935e6246 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009]  %P=[d1a99fe0599675b2abf2d83d96043bb5935e6246 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009] → 일치
  [graft 전] 전건 일치? YES ← ㉠ 자연 침묵 성립
  merge-base --is-ancestor P d → rc=0  (0 = 뒤집힘)
  --no-replace-objects 하 → rc=0  (여전히 0 = K-4 잔여)
  [graft 후] 후보(아티팩트 경로 보유) = [f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 ]
  [graft 후] 후보(config 경로 보유)   = [f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 d1a99fe0599675b2abf2d83d96043bb5935e6246 ]
  [graft 후] ㉠ 대상 집합(합집합) = [8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 d1a99fe0599675b2abf2d83d96043bb5935e6246 f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 ]
  [graft 후] W=7bd0c92807b163095a7af13de3cb746a9c635871 가 집합에 있는가? NO ← ㉠ 대상 아님
  [graft 후] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  %P):
    8c70920d3444  P: artifact              cat-file=[41895b66cfa27c401450aa9cf707791f909a7c0f]  %P=[41895b66cfa27c401450aa9cf707791f909a7c0f] → 일치
    d1a99fe05996  d: introduce config/tos_ cat-file=[7bd0c92807b163095a7af13de3cb746a9c635871]  %P=[7bd0c92807b163095a7af13de3cb746a9c635871] → 일치
    f7c2dfcb71fc  M: merge artifact branch cat-file=[d1a99fe0599675b2abf2d83d96043bb5935e6246 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009]  %P=[d1a99fe0599675b2abf2d83d96043bb5935e6246 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009] → 일치
  [graft 후] 전건 일치? YES ← ㉠ 자연 침묵 성립
```

→ 두 축 모두 **graft 전 집합 == graft 후 집합**, 그리고 **양쪽 모두 전건 일치**. (참고: 신규 U-16 드라이버는 `C_R` 을 간선 `{CN, M}` 합집합으로 열거하도록 고쳤으므로 `R` 이 전·후 모두 집합에 나타난다 — addendum-7 의 `C_R=[]` 와 갈리는 지점이 바로 이 열거 범위다.)

## 4. «단일 변수» 뮤턴트 — diff 원문 (재확인)

### 4-1. U-16

```text
-- 단일 변수 확인: 두 실행기의 diff --
  2c2
  < """U-16 «전 규칙» 손 실행기 — v2.19 에라타 6차 (계약 359f5bc5 §13.6.5
  ---
  > """[E15 «단일 변수» 뮤턴트 — 판정용 아님] 결합 base «한 줄»만 --absolute-git-dir 로 교체(㉠ 발화 «유지»).  (계약 359f5bc5 §13.6.5
  113c113
  <     top = g("rev-parse", "--show-toplevel") or R
  ---
```

### 4-2. U-17

```text
-- 단일 변수 확인: 두 실행기의 diff --
  2c2
  < # u17-verify (v2.19 에라타 6차 359f5bc5) — U-17 «예방 통제 활성 증거» 실행기 (계약 359f5bc5 §12.3.4 U-17)
  ---
  > # u17-mut-absgitdir-e7 — [E15 «단일 변수» 뮤턴트] 판정 실행기에서 «결합 base 한 줄»만 --absolute-git-dir 로 바꾼 변형(㉠ 발화 «유지»). 판정용 아님.
  70c70
  < TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || printf '.')
  ---
```

두 실행기의 차분은 **결합 base 한 줄**뿐이다. ㉠ 발화 코드는 뮤턴트에도 **그대로 살아 있다**(BLOCK #5 가 요구한 단일 변수 조건).

## 5. 결론 등급 — **(a)**

- graft 주입 **후** 의 ㉠ 대상 집합(=실행기가 실제로 순회한 x 전체)에서 **전건** `git --no-replace-objects cat-file commit x` 의 `parent` 줄이 이력 뷰 `%P` 와 **일치**한다. 누락됐던 `6de2472…` 를 포함해 일치.
- 따라서 ㉠ 는 이 픽스처에서 **자연히 침묵**하며, 실행기 자신의 출력도 매 실행 `[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []` 이다.
- 그러므로 **뮤턴트가 낸 green 은 «결합 base 한 줄» 단일 변수의 효과**다 — addendum-7 §5 R-1 의 «옛 `--absolute-git-dir` 결합 분기는 도달 가능한 fail-open» 결론은 **유지**된다.
- 유지 범위의 정직한 한계: 이 결론은 **이 픽스처류(후보 우주 «밖» 커밋에 grafts)** 에 대한 존재 증명이다. «모든 이력에서 fail-open» 이라는 전칭 주장은 하지 않는다. 또한 본 파일도 «arc closed» 를 주장하지 않는다(판정은 심판 소관).

## 6. 실행 기록 (stdout 전문 · rc 포함)

### 6-1. 추적 재실행 — `bash t8xa7v219e8.sh` (addendum-7 픽스처 사본 · 6de2472 포함)

```text
t8xa7v219e8_utc=2026-08-19T04:47:49Z
real git = /usr/local/bin/git (git version 2.38.0)
sha256(u16-full-exec-v219e6.py)=9db1570934466f5fad7c124e21e174e848a13667674e5453d983cbd591469ea9
sha256(u16-mut-absgitdir-e7.py)=e5e1b5609668733be173098c036af3f861d1190ebc082dcf861c24f45b3f8aaa
sha256(u17-verify-v219e6.sh)=174b0c186266f3585b2a592eca8c0a6c0424e57899d9d3d8e40308fae3a920b5
sha256(u17-mut-absgitdir-e7.sh)=050b2eb8f3c3c6bcff61b04ad33e06c2098e29d846d58ad3d32c0fe9d14e3db5
shim sha256=e5e5e3cebd7cbe753c79ed3bd4cf02a485f59a0cb282f95547aa21191c682ecc
드라이버 cwd(= «저장소 밖») = /Users/harris/Development/private/kis_unified_sts
-- addendum-7 보존 픽스처 → 사본(원본 무변경) --
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82n/silent
    원본 HEAD=f05cb2b0c9db0a7d7b5e7b6884b9eae781075452 · 사본 HEAD=f05cb2b0c9db0a7d7b5e7b6884b9eae781075452 · 동일? YES
    사본 grafts 원문: 632c2477a95abc9d18fc6a8c94a684d4e738cd31 c3e310d1a7376fbe4170fa810a58a687f5d6361c 6de2472b98c2905a1d70541e6b7869541452082d
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent
    원본 HEAD=90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 · 사본 HEAD=90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 · 동일? YES
    사본 grafts 원문: 97a1860bf6eea145004f1221642b4aa01dfbe9af b0becece68220d2041e568325e47b3a98ca119c3 a44dbd530acc1c1518776701683cd6c4b1fbab10

########## U-16 축 — addendum-7 이 실제로 소비한 픽스처(6de2472 포함)·graft «후» 상태 ##########
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
  *   f05cb2b M: merge reviewer branch
  |\  
  * | 76f2cad CN: NO transition
  * | cc9f2db A: approval row (aah=R)
  * | 632c247 H0: unrelated only (reviewer 없음·row 없음) ⇒ 후보 우주 밖
  |\| 
  | * 6de2472 R: reviewer artifact (digest)
  |/  
  * c3e310d S0: register/ledger-header/rationale (reviewer 경로 없음)
  R(리뷰어 아티팩트)=6de2472b98c2905a1d70541e6b7869541452082d · 이 커밋이 addendum-7 §4-2 에서 «C_R={6de2472}» 로 소비된 후보다.
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
  6de2472 도달성(graft 후): CN 에서 → rc=0 (0=도달) · HEAD 에서 → rc=0

########## U-16 (a) **단일 변수 뮤턴트** — graft 후 · 추적된 ㉠ 대상 집합 전건 대조 ##########
$ PATH=<shim>:$PATH python3 u16-mut-absgitdir-e7.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82n/silent/.git/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82n/silent/.git/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=f05cb2b is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('cc9f2db', '76f2cad', 'YES->NO'), ('6de2472', 'f05cb2b', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['cc9f2db'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 cc9f2db->76f2cad YES->NO]: COVERED by c_APP=cc9f2db C_R={6de2472}
  · edge#2[r1 6de2472->f05cb2b YES->NO]: COVERED by c_APP=cc9f2db C_R={6de2472}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0
  [U-16 뮤턴트·graft 후] 실행기가 «실제로» cat-file commit 한 x (추적 원문·중복 제거) = [6de2472b98c2905a1d70541e6b7869541452082d 76f2cad92f79e4f70d5c55096a3ef15ce5c89360 cc9f2dbbbcedc3659035b64b2131b8bb04261a41 f05cb2b0c9db0a7d7b5e7b6884b9eae781075452 ]
  [U-16 뮤턴트·graft 후] 호출 횟수 = 29 · 고유 x = 4
  [U-16 뮤턴트·graft 후] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  이력 뷰 %P):
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
    6de2472b98c2  R: reviewer artifact (dige cat-file=[c3e310d1a7376fbe4170fa810a58a687f5d6361c]  %P=[c3e310d1a7376fbe4170fa810a58a687f5d6361c] → 일치
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
    76f2cad92f79  CN: NO transition          cat-file=[cc9f2dbbbcedc3659035b64b2131b8bb04261a41]  %P=[cc9f2dbbbcedc3659035b64b2131b8bb04261a41] → 일치
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
    cc9f2dbbbced  A: approval row (aah=R)    cat-file=[632c2477a95abc9d18fc6a8c94a684d4e738cd31]  %P=[632c2477a95abc9d18fc6a8c94a684d4e738cd31] → 일치
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
    f05cb2b0c9db  M: merge reviewer branch   cat-file=[76f2cad92f79e4f70d5c55096a3ef15ce5c89360 6de2472b98c2905a1d70541e6b7869541452082d]  %P=[76f2cad92f79e4f70d5c55096a3ef15ce5c89360 6de2472b98c2905a1d70541e6b7869541452082d] → 일치
  [U-16 뮤턴트·graft 후] 전건 일치? YES ← ㉠ 자연 침묵 성립(이 실행이 소비한 x 전부)

########## U-16 (b) **판정 실행기**(E15) — graft 후 · 추적된 ㉠ 대상 집합 전건 대조 ##########
$ PATH=<shim>:$PATH python3 u16-full-exec-v219e6.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82n/silent/.git/info/grafts(--git-path 파생)=present · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82n/silent/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=f05cb2b is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('cc9f2db', '76f2cad', 'YES->NO'), ('6de2472', 'f05cb2b', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['cc9f2db'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
  · edge#1[r1 cc9f2db->76f2cad YES->NO]: COVERED by c_APP=cc9f2db C_R={6de2472}
  · edge#2[r1 6de2472->f05cb2b YES->NO]: COVERED by c_APP=cc9f2db C_R={6de2472}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ global — [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) · 발화 전체=['PROVENANCE_UNVERIFIABLE']
u16_rc=1
  [U-16 판정기·graft 후] 실행기가 «실제로» cat-file commit 한 x (추적 원문·중복 제거) = [6de2472b98c2905a1d70541e6b7869541452082d 76f2cad92f79e4f70d5c55096a3ef15ce5c89360 cc9f2dbbbcedc3659035b64b2131b8bb04261a41 f05cb2b0c9db0a7d7b5e7b6884b9eae781075452 ]
  [U-16 판정기·graft 후] 호출 횟수 = 29 · 고유 x = 4
  [U-16 판정기·graft 후] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  이력 뷰 %P):
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
    6de2472b98c2  R: reviewer artifact (dige cat-file=[c3e310d1a7376fbe4170fa810a58a687f5d6361c]  %P=[c3e310d1a7376fbe4170fa810a58a687f5d6361c] → 일치
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
    76f2cad92f79  CN: NO transition          cat-file=[cc9f2dbbbcedc3659035b64b2131b8bb04261a41]  %P=[cc9f2dbbbcedc3659035b64b2131b8bb04261a41] → 일치
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
    cc9f2dbbbced  A: approval row (aah=R)    cat-file=[632c2477a95abc9d18fc6a8c94a684d4e738cd31]  %P=[632c2477a95abc9d18fc6a8c94a684d4e738cd31] → 일치
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
    f05cb2b0c9db  M: merge reviewer branch   cat-file=[76f2cad92f79e4f70d5c55096a3ef15ce5c89360 6de2472b98c2905a1d70541e6b7869541452082d]  %P=[76f2cad92f79e4f70d5c55096a3ef15ce5c89360 6de2472b98c2905a1d70541e6b7869541452082d] → 일치
  [U-16 판정기·graft 후] 전건 일치? YES ← ㉠ 자연 침묵 성립(이 실행이 소비한 x 전부)

########## U-16 (c) 정직 이력 대조군 — 같은 사본에서 grafts 를 «치운» 상태 ##########
  grafts 치움: ABSENT · is-ancestor(R,CN) rc=1 (1=정직)
$ PATH=<shim>:$PATH python3 u16-full-exec-v219e6.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82n/silent/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82n/silent/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=f05cb2b is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('cc9f2db', '76f2cad', 'YES->NO'), ('6de2472', 'f05cb2b', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['cc9f2db'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 cc9f2db->76f2cad YES->NO]: PROVENANCE_UNVERIFIABLE(2) — g6 C_R=∅ (후보 1 · 대응 1) C_R={}
  · edge#2[r1 6de2472->f05cb2b YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={6de2472} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={6de2472}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ edge#1[r1 cc9f2db->76f2cad YES->NO] — g6 C_R=∅ (후보 1 · 대응 1) C_R={} · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_ORDER_INVALID']
u16_rc=1
  [U-16 정직·grafts 없음] 실행기가 «실제로» cat-file commit 한 x (추적 원문·중복 제거) = [6de2472b98c2905a1d70541e6b7869541452082d 76f2cad92f79e4f70d5c55096a3ef15ce5c89360 cc9f2dbbbcedc3659035b64b2131b8bb04261a41 f05cb2b0c9db0a7d7b5e7b6884b9eae781075452 ]
  [U-16 정직·grafts 없음] 호출 횟수 = 23 · 고유 x = 4
  [U-16 정직·grafts 없음] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  이력 뷰 %P):
    6de2472b98c2  R: reviewer artifact (dige cat-file=[c3e310d1a7376fbe4170fa810a58a687f5d6361c]  %P=[c3e310d1a7376fbe4170fa810a58a687f5d6361c] → 일치
    76f2cad92f79  CN: NO transition          cat-file=[cc9f2dbbbcedc3659035b64b2131b8bb04261a41]  %P=[cc9f2dbbbcedc3659035b64b2131b8bb04261a41] → 일치
    cc9f2dbbbced  A: approval row (aah=R)    cat-file=[632c2477a95abc9d18fc6a8c94a684d4e738cd31]  %P=[632c2477a95abc9d18fc6a8c94a684d4e738cd31] → 일치
    f05cb2b0c9db  M: merge reviewer branch   cat-file=[76f2cad92f79e4f70d5c55096a3ef15ce5c89360 6de2472b98c2905a1d70541e6b7869541452082d]  %P=[76f2cad92f79e4f70d5c55096a3ef15ce5c89360 6de2472b98c2905a1d70541e6b7869541452082d] → 일치
  [U-16 정직·grafts 없음] 전건 일치? YES ← ㉠ 자연 침묵 성립(이 실행이 소비한 x 전부)

########## U-17 축 — addendum-7 이 실제로 소비한 픽스처·graft «후» 상태 (BLOCK #6 «U-17 도 확인» 이행) ##########
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
  *   90d40ff M: merge artifact branch
  |\  
  * | 465e8ae d: introduce config/tos_completion.yaml
  * | 97a1860 W: workflow
  |\| 
  | * a44dbd5 P: artifact
  |/  
  * b0becec seed
  grafts 원문: 97a1860bf6eea145004f1221642b4aa01dfbe9af b0becece68220d2041e568325e47b3a98ca119c3 a44dbd530acc1c1518776701683cd6c4b1fbab10

########## U-17 (a) **단일 변수 뮤턴트** — graft 후 · 추적된 ㉠ 대상 집합 전건 대조 ##########
$ PATH=<shim>:$PATH bash u17-mut-absgitdir-e7.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e7/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ou5N7Xy5Zt
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T04:48:04Z  http=200  x-github-request-id=  (.default_branch=main)
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
P_first(집합·|1|)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] |D|=1 D=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 97a1860bf6eea145004f1221642b4aa01dfbe9af:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=465e8aed14031b68dc1da2006ef3fed85a0f18e3 head=97a1860bf6eea145004f1221642b4aa01dfbe9af merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e7/rs
u17_rc=0
  [U-17 뮤턴트·graft 후] 실행기가 «실제로» cat-file commit 한 x (추적 원문·중복 제거) = [465e8aed14031b68dc1da2006ef3fed85a0f18e3 90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 a44dbd530acc1c1518776701683cd6c4b1fbab10 ]
  [U-17 뮤턴트·graft 후] 호출 횟수 = 18 · 고유 x = 3
  [U-17 뮤턴트·graft 후] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  이력 뷰 %P):
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
    465e8aed1403  d: introduce config/tos_co cat-file=[97a1860bf6eea145004f1221642b4aa01dfbe9af]  %P=[97a1860bf6eea145004f1221642b4aa01dfbe9af] → 일치
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
    90d40ff8bd4b  M: merge artifact branch   cat-file=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10]  %P=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10] → 일치
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
    a44dbd530acc  P: artifact                cat-file=[b0becece68220d2041e568325e47b3a98ca119c3]  %P=[b0becece68220d2041e568325e47b3a98ca119c3] → 일치
  [U-17 뮤턴트·graft 후] 전건 일치? YES ← ㉠ 자연 침묵 성립(이 실행이 소비한 x 전부)

########## U-17 (b) **판정 실행기**(E15) — graft 후 · 추적된 ㉠ 대상 집합 전건 대조 ##########
$ PATH=<shim>:$PATH bash u17-verify-v219e6.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e7/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QmD7rYHHTH
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/info/grafts(--git-path 파생)=yes · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T04:48:08Z  http=200  x-github-request-id=  (.default_branch=main)
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
P_first(집합·|1|)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] |D|=1 D=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 97a1860bf6eea145004f1221642b4aa01dfbe9af:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=465e8aed14031b68dc1da2006ef3fed85a0f18e3 head=97a1860bf6eea145004f1221642b4aa01dfbe9af merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) [수집 1건 중 전순서 최소]
u17_rc=1
  [U-17 판정기·graft 후] 실행기가 «실제로» cat-file commit 한 x (추적 원문·중복 제거) = [465e8aed14031b68dc1da2006ef3fed85a0f18e3 90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 a44dbd530acc1c1518776701683cd6c4b1fbab10 ]
  [U-17 판정기·graft 후] 호출 횟수 = 18 · 고유 x = 3
  [U-17 판정기·graft 후] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  이력 뷰 %P):
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
    465e8aed1403  d: introduce config/tos_co cat-file=[97a1860bf6eea145004f1221642b4aa01dfbe9af]  %P=[97a1860bf6eea145004f1221642b4aa01dfbe9af] → 일치
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
    90d40ff8bd4b  M: merge artifact branch   cat-file=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10]  %P=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10] → 일치
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
    a44dbd530acc  P: artifact                cat-file=[b0becece68220d2041e568325e47b3a98ca119c3]  %P=[b0becece68220d2041e568325e47b3a98ca119c3] → 일치
  [U-17 판정기·graft 후] 전건 일치? YES ← ㉠ 자연 침묵 성립(이 실행이 소비한 x 전부)

########## U-17 (c) 정직 이력 대조군 — 같은 사본에서 grafts 를 «치운» 상태 ##########
  grafts 치움: ABSENT
$ PATH=<shim>:$PATH bash u17-verify-v219e6.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e7/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pAwIariZsx
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T04:48:12Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] |D|=1 D=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84n/silent/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 97a1860bf6eea145004f1221642b4aa01dfbe9af:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=465e8aed14031b68dc1da2006ef3fed85a0f18e3 head=97a1860bf6eea145004f1221642b4aa01dfbe9af merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_LATE
reason=[E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다 [수집 1건 중 전순서 최소]
u17_rc=1
  [U-17 정직·grafts 없음] 실행기가 «실제로» cat-file commit 한 x (추적 원문·중복 제거) = [465e8aed14031b68dc1da2006ef3fed85a0f18e3 90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 a44dbd530acc1c1518776701683cd6c4b1fbab10 ]
  [U-17 정직·grafts 없음] 호출 횟수 = 18 · 고유 x = 3
  [U-17 정직·grafts 없음] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  이력 뷰 %P):
    465e8aed1403  d: introduce config/tos_co cat-file=[97a1860bf6eea145004f1221642b4aa01dfbe9af]  %P=[97a1860bf6eea145004f1221642b4aa01dfbe9af] → 일치
    90d40ff8bd4b  M: merge artifact branch   cat-file=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10]  %P=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10] → 일치
    a44dbd530acc  P: artifact                cat-file=[b0becece68220d2041e568325e47b3a98ca119c3]  %P=[b0becece68220d2041e568325e47b3a98ca119c3] → 일치
  [U-17 정직·grafts 없음] 전건 일치? YES ← ㉠ 자연 침묵 성립(이 실행이 소비한 x 전부)

########## 원본 보존 확인 (addendum-7 픽스처 무변경) ##########
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent HEAD=f05cb2b0c9db0a7d7b5e7b6884b9eae781075452 · grafts=632c2477a95abc9d18fc6a8c94a684d4e738cd31 c3e310d1a7376fbe4170fa810a58a687f5d6361c 6de2472b98c2905a1d70541e6b7869541452082d
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent HEAD=90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 · grafts=97a1860bf6eea145004f1221642b4aa01dfbe9af b0becece68220d2041e568325e47b3a98ca119c3 a44dbd530acc1c1518776701683cd6c4b1fbab10
```

### 6-2. 신규 픽스처 U-16 — `bash t82v219e8.sh`

```text
t82v219e8_utc=2026-08-19T04:40:21Z
sha256(u16-full-exec-v219e6.py)=9db1570934466f5fad7c124e21e174e848a13667674e5453d983cbd591469ea9   (판정 실행기 — 결합 base = --show-toplevel)
sha256(u16-mut-absgitdir-e7.py)=e5e1b5609668733be173098c036af3f861d1190ebc082dcf861c24f45b3f8aaa  (**단일 변수 뮤턴트** — 결합 base 한 줄만 · ㉠ 발화 «유지»)
드라이버 cwd(= «저장소 밖») = /Users/harris/Development/private/kis_unified_sts
-- 단일 변수 확인: 두 실행기의 diff --
  2c2
  < """U-16 «전 규칙» 손 실행기 — v2.19 에라타 6차 (계약 359f5bc5 §13.6.5
  ---
  > """[E15 «단일 변수» 뮤턴트 — 판정용 아님] 결합 base «한 줄»만 --absolute-git-dir 로 교체(㉠ 발화 «유지»).  (계약 359f5bc5 §13.6.5
  113c113
  <     top = g("rev-parse", "--show-toplevel") or R
  ---
  >     top = g("rev-parse", "--absolute-git-dir") or R   # [뮤턴트] 결합 base 만 교체 (E15 철회 분기)

########## 픽스처 구성 (addendum-7 과 동일 구조 · 후보 우주 «밖» 커밋 H0 만 재작성 대상) ##########
  S0=a1877df7460f2042e3372ad9f33e817e55987135
  H0=908611a678c86d68146f638640e683b2cc0a7a86  ← graft 재작성 «대상»
  R =ec48e562ae73651e40bf912aabbd4ee14d70ed8a  ← reviewer 아티팩트(= C_R 의 blob 도입 지점 후보)
  A =6d75e9115cf13cd2efd42f68a6cbc466387dfa20
  CN=c824ea73061c3295106dc251de850ffb739bbe0d
  M =05060ec42596f5bf0f309dd8c042b6da4b24dc96 (HEAD)
  *   05060ec M: merge reviewer branch
  |\  
  | * ec48e56 R: reviewer artifact (digest)
  * | c824ea7 CN: NO transition
  * | 6d75e91 A: approval row (aah=R)
  * | 908611a H0: unrelated only (reviewer 없음·row 없음)
  |/  
  * a1877df S0: register/ledger-header/rationale (reviewer 경로 없음)

########## (대조 A) grafts «없는» 정직 이력 — ㉠ 대상 집합 + 판정 ##########
  merge-base --is-ancestor R CN → rc=1  (1 = 조상 아님 = 정직)
  [graft 전] c_APP ㉠-검사 후보(원장 행 보유)        = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 c824ea73061c3295106dc251de850ffb739bbe0d 6d75e9115cf13cd2efd42f68a6cbc466387dfa20 ]
  [graft 전] C_R   ㉠-검사 후보(리뷰어 blob 일치·간선 c∈{CN,M} 합집합) = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 ec48e562ae73651e40bf912aabbd4ee14d70ed8a ]
  [graft 전] ㉠ 대상 집합(합집합) = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 6d75e9115cf13cd2efd42f68a6cbc466387dfa20 c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a ]
  [graft 전] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  %P):
    05060ec42596  M: merge reviewer bran cat-file=[c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a]  %P=[c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a] → 일치
    6d75e9115cf1  A: approval row (aah=R cat-file=[908611a678c86d68146f638640e683b2cc0a7a86]  %P=[908611a678c86d68146f638640e683b2cc0a7a86] → 일치
    c824ea73061c  CN: NO transition      cat-file=[6d75e9115cf13cd2efd42f68a6cbc466387dfa20]  %P=[6d75e9115cf13cd2efd42f68a6cbc466387dfa20] → 일치
    ec48e562ae73  R: reviewer artifact ( cat-file=[a1877df7460f2042e3372ad9f33e817e55987135]  %P=[a1877df7460f2042e3372ad9f33e817e55987135] → 일치
  [graft 전] 전건 일치? YES ← ㉠ 자연 침묵 성립
  *   05060ec M: merge reviewer branch
  |\  
  | * ec48e56 R: reviewer artifact (digest)
  * | c824ea7 CN: NO transition
  * | 6d75e91 A: approval row (aah=R)
  * | 908611a H0: unrelated only (reviewer 없음·row 없음)
  |/  
  * a1877df S0: register/ledger-header/rationale (reviewer 경로 없음)
$ python3 u16-full-exec-v219e6.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82m/silent/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82m/silent/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=05060ec is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('ec48e56', '05060ec', 'YES->NO'), ('6d75e91', 'c824ea7', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['6d75e91'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 ec48e56->05060ec YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={ec48e56} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={ec48e56}
  · edge#2[r1 6d75e91->c824ea7 YES->NO]: PROVENANCE_UNVERIFIABLE(2) — g6 C_R=∅ (후보 1 · 대응 1) C_R={}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ edge#2[r1 6d75e91->c824ea7 YES->NO] — g6 C_R=∅ (후보 1 · 대응 1) C_R={} · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_ORDER_INVALID']
u16_rc=1

########## grafts 주입 — 후보 우주 «밖» 커밋 H0 의 부모만 [S0, R] 로 재작성 ##########
$ cat <fixture>/.git/info/grafts
  908611a678c86d68146f638640e683b2cc0a7a86 a1877df7460f2042e3372ad9f33e817e55987135 ec48e562ae73651e40bf912aabbd4ee14d70ed8a
  merge-base --is-ancestor R CN → rc=0  (0 = 뒤집힘)
  --no-replace-objects 하 → rc=0  (여전히 0 = K-4 잔여)
  [E15] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82m/silent/.git/info/grafts → present · [뮤턴트] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82m/silent/.git/.git/info/grafts → ABSENT ← 거짓 ABSENT

########## **[BLOCK #6 요구] graft «후» ㉠ 대상 집합 재방출 + 전건 부모 대조** (R=ec48e562ae73651e40bf912aabbd4ee14d70ed8a 이 C_R 후보로 «새로» 들어오는지 포함) ##########
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
  [graft 후] c_APP ㉠-검사 후보(원장 행 보유)        = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 c824ea73061c3295106dc251de850ffb739bbe0d 6d75e9115cf13cd2efd42f68a6cbc466387dfa20 ]
  [graft 후] C_R   ㉠-검사 후보(리뷰어 blob 일치·간선 c∈{CN,M} 합집합) = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 ec48e562ae73651e40bf912aabbd4ee14d70ed8a ]
  [graft 후] ㉠ 대상 집합(합집합) = [05060ec42596f5bf0f309dd8c042b6da4b24dc96 6d75e9115cf13cd2efd42f68a6cbc466387dfa20 c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a ]
  [graft 후] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  %P):
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
    05060ec42596  M: merge reviewer bran cat-file=[c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a]  %P=[c824ea73061c3295106dc251de850ffb739bbe0d ec48e562ae73651e40bf912aabbd4ee14d70ed8a] → 일치
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
    6d75e9115cf1  A: approval row (aah=R cat-file=[908611a678c86d68146f638640e683b2cc0a7a86]  %P=[908611a678c86d68146f638640e683b2cc0a7a86] → 일치
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
    c824ea73061c  CN: NO transition      cat-file=[6d75e9115cf13cd2efd42f68a6cbc466387dfa20]  %P=[6d75e9115cf13cd2efd42f68a6cbc466387dfa20] → 일치
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
    ec48e562ae73  R: reviewer artifact ( cat-file=[a1877df7460f2042e3372ad9f33e817e55987135]  %P=[a1877df7460f2042e3372ad9f33e817e55987135] → 일치
  [graft 후] 전건 일치? YES ← ㉠ 자연 침묵 성립
  주: graft 로 CN 에서 R 이 도달 가능해지면서 C_R 후보 집합이 ∅ → {R} 로 «커진다» — addendum-7 이 놓친 원소가 이것이다.
     R 자신은 재작성 «대상이 아니므로»(재작성된 것은 H0) cat-file 부모 == %P 로 남는다.

########## (a) **단일 변수 뮤턴트**(결합 base 만) ⇒ ㉡ 미발화 · ㉠ 침묵 · 조상성 grafts 따라감 ##########
  *   05060ec M: merge reviewer branch
  |\  
  * | c824ea7 CN: NO transition
  * | 6d75e91 A: approval row (aah=R)
  * | 908611a H0: unrelated only (reviewer 없음·row 없음)
  |\| 
  | * ec48e56 R: reviewer artifact (digest)
  |/  
  * a1877df S0: register/ledger-header/rationale (reviewer 경로 없음)
$ python3 u16-mut-absgitdir-e7.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82m/silent/.git/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82m/silent/.git/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=05060ec is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('ec48e56', '05060ec', 'YES->NO'), ('6d75e91', 'c824ea7', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['6d75e91'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 ec48e56->05060ec YES->NO]: COVERED by c_APP=6d75e91 C_R={ec48e56}
  · edge#2[r1 6d75e91->c824ea7 YES->NO]: COVERED by c_APP=6d75e91 C_R={ec48e56}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## (b) **판정 실행기**(E15) ⇒ ㉡ 발화 ⇒ 차단 ##########
  *   05060ec M: merge reviewer branch
  |\  
  * | c824ea7 CN: NO transition
  * | 6d75e91 A: approval row (aah=R)
  * | 908611a H0: unrelated only (reviewer 없음·row 없음)
  |\| 
  | * ec48e56 R: reviewer artifact (digest)
  |/  
  * a1877df S0: register/ledger-header/rationale (reviewer 경로 없음)
$ python3 u16-full-exec-v219e6.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82m/silent/.git/info/grafts(--git-path 파생)=present · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82m/silent/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=05060ec is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('ec48e56', '05060ec', 'YES->NO'), ('6d75e91', 'c824ea7', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['6d75e91'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
  · edge#1[r1 ec48e56->05060ec YES->NO]: COVERED by c_APP=6d75e91 C_R={ec48e56}
  · edge#2[r1 6d75e91->c824ea7 YES->NO]: COVERED by c_APP=6d75e91 C_R={ec48e56}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ global — [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) · 발화 전체=['PROVENANCE_UNVERIFIABLE']
u16_rc=1
```

### 6-3. 신규 픽스처 U-17 — `bash t84v219e8.sh`

```text
t84v219e8_utc=2026-08-19T04:41:16Z
sha256(u17-verify-v219e6.sh)=174b0c186266f3585b2a592eca8c0a6c0424e57899d9d3d8e40308fae3a920b5   (판정 실행기)
sha256(u17-mut-absgitdir-e7.sh)=050b2eb8f3c3c6bcff61b04ad33e06c2098e29d846d58ad3d32c0fe9d14e3db5  (**단일 변수 뮤턴트** — 결합 base 한 줄만 · ㉠ 발화 «유지»)
드라이버 cwd(= «저장소 밖») = /Users/harris/Development/private/kis_unified_sts
-- 단일 변수 확인: 두 실행기의 diff --
  2c2
  < # u17-verify (v2.19 에라타 6차 359f5bc5) — U-17 «예방 통제 활성 증거» 실행기 (계약 359f5bc5 §12.3.4 U-17)
  ---
  > # u17-mut-absgitdir-e7 — [E15 «단일 변수» 뮤턴트] 판정 실행기에서 «결합 base 한 줄»만 --absolute-git-dir 로 바꾼 변형(㉠ 발화 «유지»). 판정용 아님.
  70c70
  < TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || printf '.')
  ---
  > TOPLEVEL=$(git rev-parse --absolute-git-dir 2>/dev/null || printf '.')   # [뮤턴트] 결합 base 만 교체 (E15 가 철회한 옛 허용 분기)

########## 픽스처 구성 (addendum-7 과 동일 구조 · 후보 우주 «밖» 커밋 W 만 재작성 대상) ##########
  seed=41895b66cfa27c401450aa9cf707791f909a7c0f
  W =7bd0c92807b163095a7af13de3cb746a9c635871  ← graft 재작성 «대상»(워크플로만 — 아티팩트·config 경로 없음)
  d =d1a99fe0599675b2abf2d83d96043bb5935e6246
  P =8c70920d3444f5ef70bba4fab5fc0b4e8eac8009
  M =f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 (HEAD)
  *   f7c2dfc M: merge artifact branch
  |\  
  | * 8c70920 P: artifact
  * | d1a99fe d: introduce config/tos_completion.yaml
  * | 7bd0c92 W: workflow
  |/  
  * 41895b6 seed

########## (대조 A) grafts «없는» 정직 이력 — ㉠ 대상 집합 + 판정 ⇒ PREVENTION_LATE(6) ##########
  merge-base --is-ancestor P d → rc=1  (1 = 조상 아님 = 정직)
  [graft 전] 후보(아티팩트 경로 보유) = [f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 ]
  [graft 전] 후보(config 경로 보유)   = [f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 d1a99fe0599675b2abf2d83d96043bb5935e6246 ]
  [graft 전] ㉠ 대상 집합(합집합) = [8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 d1a99fe0599675b2abf2d83d96043bb5935e6246 f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 ]
  [graft 전] W=7bd0c92807b163095a7af13de3cb746a9c635871 가 집합에 있는가? NO ← ㉠ 대상 아님
  [graft 전] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  %P):
    8c70920d3444  P: artifact              cat-file=[41895b66cfa27c401450aa9cf707791f909a7c0f]  %P=[41895b66cfa27c401450aa9cf707791f909a7c0f] → 일치
    d1a99fe05996  d: introduce config/tos_ cat-file=[7bd0c92807b163095a7af13de3cb746a9c635871]  %P=[7bd0c92807b163095a7af13de3cb746a9c635871] → 일치
    f7c2dfcb71fc  M: merge artifact branch cat-file=[d1a99fe0599675b2abf2d83d96043bb5935e6246 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009]  %P=[d1a99fe0599675b2abf2d83d96043bb5935e6246 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009] → 일치
  [graft 전] 전건 일치? YES ← ㉠ 자연 침묵 성립
  *   f7c2dfc M: merge artifact branch
  |\  
  | * 8c70920 P: artifact
  * | d1a99fe d: introduce config/tos_completion.yaml
  * | 7bd0c92 W: workflow
  |/  
  * 41895b6 seed
$ bash u17-verify-v219e6.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e8/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9h9VT468Ca
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T04:41:17Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 ] |D|=1 D=[d1a99fe0599675b2abf2d83d96043bb5935e6246 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 7bd0c92807b163095a7af13de3cb746a9c635871:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=d1a99fe0599675b2abf2d83d96043bb5935e6246 head=7bd0c92807b163095a7af13de3cb746a9c635871 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_LATE
reason=[E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다 [수집 1건 중 전순서 최소]
u17_rc=1

########## grafts 주입 — 후보 우주 «밖» 커밋 W 의 부모만 [seed, P] 로 재작성 ##########
$ cat <fixture>/.git/info/grafts
  7bd0c92807b163095a7af13de3cb746a9c635871 41895b66cfa27c401450aa9cf707791f909a7c0f 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009
  merge-base --is-ancestor P d → rc=0  (0 = 뒤집힘)
  --no-replace-objects 하 → rc=0  (여전히 0 = K-4 잔여)
  [E15] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/info/grafts → present · [뮤턴트] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/.git/info/grafts → ABSENT ← 거짓 ABSENT

########## **[BLOCK #6 요구] graft «후» ㉠ 대상 집합 재방출 + 전건 부모 대조** ##########
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
  [graft 후] 후보(아티팩트 경로 보유) = [f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 ]
  [graft 후] 후보(config 경로 보유)   = [f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 d1a99fe0599675b2abf2d83d96043bb5935e6246 ]
  [graft 후] ㉠ 대상 집합(합집합) = [8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 d1a99fe0599675b2abf2d83d96043bb5935e6246 f7c2dfcb71fcf22cc89c797c706c74d99d1081c8 ]
  [graft 후] W=7bd0c92807b163095a7af13de3cb746a9c635871 가 집합에 있는가? NO ← ㉠ 대상 아님
  [graft 후] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  %P):
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
    8c70920d3444  P: artifact              cat-file=[41895b66cfa27c401450aa9cf707791f909a7c0f]  %P=[41895b66cfa27c401450aa9cf707791f909a7c0f] → 일치
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
    d1a99fe05996  d: introduce config/tos_ cat-file=[7bd0c92807b163095a7af13de3cb746a9c635871]  %P=[7bd0c92807b163095a7af13de3cb746a9c635871] → 일치
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
    f7c2dfcb71fc  M: merge artifact branch cat-file=[d1a99fe0599675b2abf2d83d96043bb5935e6246 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009]  %P=[d1a99fe0599675b2abf2d83d96043bb5935e6246 8c70920d3444f5ef70bba4fab5fc0b4e8eac8009] → 일치
  [graft 후] 전건 일치? YES ← ㉠ 자연 침묵 성립

########## (a) **단일 변수 뮤턴트**(결합 base 만) ⇒ green = fail-open ##########
  *   f7c2dfc M: merge artifact branch
  |\  
  * | d1a99fe d: introduce config/tos_completion.yaml
  * | 7bd0c92 W: workflow
  |\| 
  | * 8c70920 P: artifact
  |/  
  * 41895b6 seed
$ bash u17-mut-absgitdir-e7.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e8/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ZZpSS8vOnH
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T04:41:20Z  http=200  x-github-request-id=  (.default_branch=main)
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
P_first(집합·|1|)=[8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 ] |D|=1 D=[d1a99fe0599675b2abf2d83d96043bb5935e6246 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 7bd0c92807b163095a7af13de3cb746a9c635871:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=d1a99fe0599675b2abf2d83d96043bb5935e6246 head=7bd0c92807b163095a7af13de3cb746a9c635871 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e8/rs
u17_rc=0

########## (b) **판정 실행기**(E15) ⇒ 차단 ##########
  *   f7c2dfc M: merge artifact branch
  |\  
  * | d1a99fe d: introduce config/tos_completion.yaml
  * | 7bd0c92 W: workflow
  |\| 
  | * 8c70920 P: artifact
  |/  
  * 41895b6 seed
$ bash u17-verify-v219e6.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e8/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.jU8wRntR7k
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/info/grafts(--git-path 파생)=yes · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T04:41:23Z  http=200  x-github-request-id=  (.default_branch=main)
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
P_first(집합·|1|)=[8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[8c70920d3444f5ef70bba4fab5fc0b4e8eac8009 ] |D|=1 D=[d1a99fe0599675b2abf2d83d96043bb5935e6246 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 7bd0c92807b163095a7af13de3cb746a9c635871:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=d1a99fe0599675b2abf2d83d96043bb5935e6246 head=7bd0c92807b163095a7af13de3cb746a9c635871 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84m/silent/.git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) [수집 1건 중 전순서 최소]
u17_rc=1
```

## 7. 사후 검증 원문 (계약 무변경 · HEAD · 본 저장소 관측 · 픽스처 격리)

```text
post_utc=2026-08-19T04:41:47Z
$ git -C <repo> rev-parse HEAD
5493c6f067b14e83547a592ffdc3b5c5c0fd1222
$ git -C <repo> status --short
 M uv.lock
?? tools/spikes/
--- 계약 «무변경» (addendum-8 은 계약을 바꾸지 않는다) ---
$ git -C <repo> diff --quiet 359f5bc5 -- <계약> → rc
rc=0
  blob(HEAD:계약)=b5f9b33e8eaa650826c561fb9e3e79254cca7e19 · blob(359f5bc5:계약)=b5f9b33e8eaa650826c561fb9e3e79254cca7e19
$ rev-list --count 359f5bc5..HEAD -- <계약>
0
$ sed -n '4631,4731p' <워킹트리> | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git show 359f5bc5:<계약> | sed -n '4631,4731p' | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git -C <repo> reflog -n 3
5493c6f0 HEAD@{0}: commit: docs(plans): INDEX — phase0 completion contract v2.19 (addendum-7 962cd692 single-variable mutant; addendum-6 claims retracted per stop-time BLOCK #5)
962cd692 HEAD@{1}: commit: docs(tos): addendum 7 — single-variable mutant proves the retracted --absolute-git-dir join is a reachable fail-open (supersedes addendum-6 §4)
27d1aa33 HEAD@{2}: commit: docs(plans): INDEX — phase0 completion contract v2.19 (errata/addendum ×6 → 359f5bc5/301ca2cd after stop-time BLOCK #4)
--- 본 저장소 [PARENTS-UNTRUSTED] 관측 (E15 루트 결합) ---
  [E15] /Users/harris/Development/private/kis_unified_sts/.git/info/grafts → ABSENT · replace -l='' · is-shallow=false
  ㉠ 재파생=962cd692a8c1dac5dac45c9c43d8031196bf4372 · %P=962cd692a8c1dac5dac45c9c43d8031196bf4372
--- 픽스처 격리 ---
       2
```

## 8. 드라이버 원문

### 8-1. `t8xa7v219e8.sh` (sha256 `b336145008409496f59ef786f1d9b562f6f31396b895839a4c4ae4e187874354` · 95 행)

```bash
#!/usr/bin/env bash
# t8xa7v219e8.sh — addendum-8 (계약 무변경·에라타 6차 359f5bc5 결속)
#   [stop-time BLOCK #6 채택] addendum-7 이 **graft 주입 «전»** 에 방출한 ㉠ 후보 집합을,
#   addendum-7 이 «실제로 소비한» 그 픽스처(보존본 fx82k/fx84k 의 사본) 위에서 **graft 주입 «후»** 상태로 재방출한다.
#   후보 집합은 재파생이 아니라 **실행기가 실제로 호출한 `git cat-file commit <x>` 를 shim 으로 «추적»** 해 얻는다
#   (= 계약이 말하는 «실행기가 순회하는 모든 x» 의 기계적 하한이자 상한 — 드라이버의 독립 재계산 오류가 개입할 여지 0).
# GET-only(seam) · 서버 쓰기·설정 변경 0 · 픽스처는 scratchpad 독립 git repo 사본(본 저장소 무접촉·worktree 미사용).
set -uo pipefail
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX16="$SP/u16-full-exec-v219e6.py"; MUT16="$SP/u16-mut-absgitdir-e7.py"
EX17="$SP/u17-verify-v219e6.sh";   MUT17="$SP/u17-mut-absgitdir-e7.sh"
A7FX16="$SP/fx82k/silent"; A7FX17="$SP/fx84k/silent"; SEAM7="$SP/seam219e7/rs"
N16="$SP/fx82n/silent";    N17="$SP/fx84n/silent"
SHIM="$SP/shim-e8"; REALGIT=$(command -v git)
sec(){ printf '\n########## %s ##########\n' "$1"; }

rm -rf "$SP/fx82n" "$SP/fx84n" "$SHIM"; mkdir -p "$SP/fx82n" "$SP/fx84n" "$SHIM"
cp -R "$A7FX16" "$N16"; cp -R "$A7FX17" "$N17"
cat > "$SHIM/git" <<EOF
#!/bin/sh
# [추적 shim] 실행기가 호출한 «cat-file commit <x>» 만 기록하고 그대로 실 git 에 위임한다(동작 무변경).
case " \$* " in *" cat-file commit "*) printf '%s\n' "\$*" >> "\$T8TRACE" ;; esac
exec $REALGIT "\$@"
EOF
chmod +x "$SHIM/git"

printf 't8xa7v219e8_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'real git = %s (%s)\n' "$REALGIT" "$("$REALGIT" --version)"
printf 'sha256(u16-full-exec-v219e6.py)=%s\nsha256(u16-mut-absgitdir-e7.py)=%s\n' "$(shasum -a 256 "$EX16"|cut -d" " -f1)" "$(shasum -a 256 "$MUT16"|cut -d" " -f1)"
printf 'sha256(u17-verify-v219e6.sh)=%s\nsha256(u17-mut-absgitdir-e7.sh)=%s\n' "$(shasum -a 256 "$EX17"|cut -d" " -f1)" "$(shasum -a 256 "$MUT17"|cut -d" " -f1)"
printf 'shim sha256=%s\n드라이버 cwd(= «저장소 밖») = %s\n' "$(shasum -a 256 "$SHIM/git"|cut -d" " -f1)" "$PWD"
echo "-- addendum-7 보존 픽스처 → 사본(원본 무변경) --"
for p in "$A7FX16 $N16" "$A7FX17 $N17"; do set -- $p
  echo "  $1 → $2"
  echo "    원본 HEAD=$("$REALGIT" -C "$1" rev-parse HEAD) · 사본 HEAD=$("$REALGIT" -C "$2" rev-parse HEAD) · 동일? $( [ "$("$REALGIT" -C "$1" rev-parse HEAD)" = "$("$REALGIT" -C "$2" rev-parse HEAD)" ] && echo YES || echo NO )"
  echo "    사본 grafts 원문: $(cat "$2/.git/info/grafts" 2>/dev/null)"
done

# ── 추적된 ㉠ 대상 집합 방출 + 전건 부모 대조 ────────────────────────────────
emit_traced(){ local R="$1" T="$2" tag="$3" bad=0 x TP AP TS AS RES SET
  SET=$(awk '{for(i=1;i<NF;i++) if($i=="commit" && $(i-1)=="cat-file") print $(i+1)}' "$T" | sort -u | tr '\n' ' ')
  echo "  [$tag] 실행기가 «실제로» cat-file commit 한 x (추적 원문·중복 제거) = [$SET]"
  echo "  [$tag] 호출 횟수 = $(wc -l < "$T" | tr -d ' ') · 고유 x = $(printf '%s\n' $SET | grep -c . | tr -d ' ')"
  echo "  [$tag] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  이력 뷰 %P):"
  for x in $SET; do
    TP=$("$REALGIT" -C "$R" --no-replace-objects cat-file commit "$x" | awk '/^$/{exit} /^parent /{printf "%s ", $2}')
    AP=$(env -u GIT_NO_REPLACE_OBJECTS "$REALGIT" -C "$R" log --format=%P -1 "$x")
    TS=$(printf '%s\n' $TP | sort | tr '\n' ' '); AS=$(printf '%s\n' $AP | sort | tr '\n' ' ')
    if [ "$TS" = "$AS" ]; then RES="일치"; else RES="불일치(!!)"; bad=1; fi
    printf '    %s  %-26s cat-file=[%s]  %%P=[%s] → %s\n' "${x:0:12}" "$("$REALGIT" -C "$R" log --format=%s -1 "$x" 2>/dev/null | cut -c1-26)" "${TP% }" "$AP" "$RES"
  done
  echo "  [$tag] 전건 일치? $( [ "$bad" = 0 ] && echo 'YES ← ㉠ 자연 침묵 성립(이 실행이 소비한 x 전부)' || echo 'NO ← ㉠ 침묵 안 함' )"; }

run16(){ local R="$1" E="$2" tag="$3" T; T=$(mktemp)
  echo "\$ PATH=<shim>:\$PATH python3 $(basename "$E") <fixture>"
  PATH="$SHIM:$PATH" T8TRACE="$T" python3 "$E" "$R"; echo "u16_rc=$?"
  emit_traced "$R" "$T" "$tag"; }
run17(){ local R="$1" E="$2" tag="$3" T; T=$(mktemp)
  echo "\$ PATH=<shim>:\$PATH bash $(basename "$E") <fixture>"
  PATH="$SHIM:$PATH" T8TRACE="$T" U17_RESPONDER="file:$SEAM7" U17_CAPTURE_DIR="$(mktemp -d)" bash "$E" "$R" 2>&1 | grep -avE '^U17-(A00|A0 |A1|A2|A3|A4|B1|B2|B3|B4|B5) |^  \| |^U17-H '
  echo "u17_rc=${PIPESTATUS[0]}"
  emit_traced "$R" "$T" "$tag"; }

########################################################################
sec "U-16 축 — addendum-7 이 실제로 소비한 픽스처(6de2472 포함)·graft «후» 상태"
"$REALGIT" -C "$N16" log --oneline --graph --all | sed 's/^/  /'
echo "  R(리뷰어 아티팩트)=6de2472b98c2905a1d70541e6b7869541452082d · 이 커밋이 addendum-7 §4-2 에서 «C_R={6de2472}» 로 소비된 후보다."
echo "  6de2472 도달성(graft 후): CN 에서 → rc=$("$REALGIT" -C "$N16" merge-base --is-ancestor 6de2472b98c2905a1d70541e6b7869541452082d 76f2cad92f79e4f70d5c55096a3ef15ce5c89360; echo $?) (0=도달) · HEAD 에서 → rc=$("$REALGIT" -C "$N16" merge-base --is-ancestor 6de2472b98c2905a1d70541e6b7869541452082d HEAD; echo $?)"

sec "U-16 (a) **단일 변수 뮤턴트** — graft 후 · 추적된 ㉠ 대상 집합 전건 대조"
run16 "$N16" "$MUT16" "U-16 뮤턴트·graft 후"
sec "U-16 (b) **판정 실행기**(E15) — graft 후 · 추적된 ㉠ 대상 집합 전건 대조"
run16 "$N16" "$EX16" "U-16 판정기·graft 후"
sec "U-16 (c) 정직 이력 대조군 — 같은 사본에서 grafts 를 «치운» 상태"
mv "$N16/.git/info/grafts" "$N16/.git/info/grafts.off"
echo "  grafts 치움: $( [ -f "$N16/.git/info/grafts" ] && echo present || echo ABSENT ) · is-ancestor(R,CN) rc=$("$REALGIT" -C "$N16" merge-base --is-ancestor 6de2472b98c2905a1d70541e6b7869541452082d 76f2cad92f79e4f70d5c55096a3ef15ce5c89360; echo $?) (1=정직)"
run16 "$N16" "$EX16" "U-16 정직·grafts 없음"
mv "$N16/.git/info/grafts.off" "$N16/.git/info/grafts"

########################################################################
sec "U-17 축 — addendum-7 이 실제로 소비한 픽스처·graft «후» 상태 (BLOCK #6 «U-17 도 확인» 이행)"
"$REALGIT" -C "$N17" log --oneline --graph --all | sed 's/^/  /'
echo "  grafts 원문: $(cat "$N17/.git/info/grafts")"
sec "U-17 (a) **단일 변수 뮤턴트** — graft 후 · 추적된 ㉠ 대상 집합 전건 대조"
run17 "$N17" "$MUT17" "U-17 뮤턴트·graft 후"
sec "U-17 (b) **판정 실행기**(E15) — graft 후 · 추적된 ㉠ 대상 집합 전건 대조"
run17 "$N17" "$EX17" "U-17 판정기·graft 후"
sec "U-17 (c) 정직 이력 대조군 — 같은 사본에서 grafts 를 «치운» 상태"
mv "$N17/.git/info/grafts" "$N17/.git/info/grafts.off"
echo "  grafts 치움: $( [ -f "$N17/.git/info/grafts" ] && echo present || echo ABSENT )"
run17 "$N17" "$EX17" "U-17 정직·grafts 없음"
mv "$N17/.git/info/grafts.off" "$N17/.git/info/grafts"

sec "원본 보존 확인 (addendum-7 픽스처 무변경)"
for p in "$A7FX16" "$A7FX17"; do echo "  $p HEAD=$("$REALGIT" -C "$p" rev-parse HEAD) · grafts=$(cat "$p/.git/info/grafts")"; done
```

### 8-2. `t82v219e8.sh` (sha256 `3727d3efa4cbc97aedd3f2a94353703ac191bc8a37071283aae64f49b9c16cff` · 105 행)

```bash
#!/usr/bin/env bash
# t82v219e8.sh — addendum-8 (계약 무변경·에라타 6차 359f5bc5 결속) «영향 변이» 재실행 드라이버 (U-16 축):
#   [BLOCK #6 채택] ㉠ 대상 집합을 **graft 주입 «후»** 에 방출하고 전건 부모 대조 — addendum-7 은 graft «전» 집합을 기록해 C_R 후보(R)를 누락했다.
# 서버 조회 0(순수 in-repo) · 픽스처는 scratchpad 독립 git repo(본 저장소 무접촉·worktree 미사용).
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u16-full-exec-v219e6.py"; MUT="$SP/u16-mut-absgitdir-e7.py"

FX="$SP/fx82m"; REF=reviews/review.md; RAT=rationale/r1.md
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
gp(){ local v; v=$(git -C "$1" rev-parse --git-path "$2"); case "$v" in /*) printf '%s' "$v";; *) printf '%s/%s' "$1" "$v";; esac; }
probe(){ printf '  ㉠ 재파생=[%s] · ㉠ 이력 뷰 %%P=[%s] · ㉡ replace -l=[%s]\n  [E13] --git-path info/grafts=%s → %s | «리터럴» .git/info/grafts=%s · --git-path shallow=%s → %s · ㉢ is_shallow=%s\n' \
  "$(tp "$1" "$2")" "$(ap "$1" "$2")" "$(git -C "$1" replace -l | tr '\n' ' ')" \
  "$(git -C "$1" rev-parse --git-path info/grafts)" "$( [ -f "$(gp "$1" info/grafts)" ] && echo present || echo ABSENT )" \
  "$( [ -f "$1/.git/info/grafts" ] && echo present || echo ABSENT )" \
  "$(git -C "$1" rev-parse --git-path shallow)" "$( [ -f "$(gp "$1" shallow)" ] && echo "목록=[$(tr '\n' ' ' < "$(gp "$1" shallow)")]" || echo ABSENT )" \
  "$(git -C "$1" rev-parse --is-shallow-repository)"; }

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
printf 't82v219e8_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'sha256(u16-full-exec-v219e6.py)=%s   (판정 실행기 — 결합 base = --show-toplevel)\n' "$(shasum -a 256 "$EX" | cut -d" " -f1)"
printf 'sha256(u16-mut-absgitdir-e7.py)=%s  (**단일 변수 뮤턴트** — 결합 base 한 줄만 · ㉠ 발화 «유지»)\n' "$(shasum -a 256 "$MUT" | cut -d" " -f1)"
printf '드라이버 cwd(= «저장소 밖») = %s\n' "$PWD"
echo "-- 단일 변수 확인: 두 실행기의 diff --"; diff "$EX" "$MUT" | sed 's/^/  /'

########################################################################
sec "픽스처 구성 (addendum-7 과 동일 구조 · 후보 우주 «밖» 커밋 H0 만 재작성 대상)"
R="$FX/silent"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' 'r1,YES,tos' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"; S0=$(c "$R" "S0: register/ledger-header/rationale (reviewer 경로 없음)")
git -C "$R" checkout -q --detach "$S0"; printf 'unrelated\n' > "$R/note.md"; H0=$(c "$R" "H0: unrelated only (reviewer 없음·row 없음)")
git -C "$R" checkout -q --detach "$S0"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; RR=$(c "$R" "R: reviewer artifact (digest)")
git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$RR" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=R)")
setNO "$R"; CN=$(c "$R" "CN: NO transition")
git -C "$R" merge -q --no-ff -m "M: merge reviewer branch" "$RR" 2>/dev/null || { git -C "$R" add -A; git -C "$R" commit -q -m "M: merge reviewer branch"; }
M=$(git -C "$R" rev-parse HEAD); git -C "$R" branch -f main HEAD
echo "  S0=$S0"; echo "  H0=$H0  ← graft 재작성 «대상»"; echo "  R =$RR  ← reviewer 아티팩트(= C_R 의 blob 도입 지점 후보)"; echo "  A =$A"; echo "  CN=$CN"; echo "  M =$M (HEAD)"
git -C "$R" log --oneline --graph --all | sed 's/^/  /'

# ── ㉠ 대상 집합 재계산기 (실행기 규칙 그대로) : c_APP 측 ∪ C_R 측(간선 커밋별)
ROW=$(git -C "$R" show HEAD:LEDGER.md | grep '^r1 ' | head -1)
TGT=$(git -C "$R" rev-parse "$RR:$REF")
emit_set(){ local tag="$1"; local capp="" cr="" x
  for x in $(git -C "$R" rev-list HEAD); do git -C "$R" show "$x:LEDGER.md" 2>/dev/null | grep -qxF "$ROW" && capp="$capp $x"; done
  for e in "$CN" "$M"; do for x in $(git -C "$R" rev-list "$e"); do [ "$(git -C "$R" rev-parse -q --verify "$x:$REF" 2>/dev/null)" = "$TGT" ] && cr="$cr $x"; done; done
  cr=$(printf '%s\n' $cr | sort -u | tr '\n' ' ')
  echo "  [$tag] c_APP ㉠-검사 후보(원장 행 보유)        = [$(printf '%s ' $capp)]"
  echo "  [$tag] C_R   ㉠-검사 후보(리뷰어 blob 일치·간선 c∈{CN,M} 합집합) = [$cr]"
  ALLSET=$(printf '%s\n' $capp $cr | sort -u | tr '\n' ' ')
  echo "  [$tag] ㉠ 대상 집합(합집합) = [$ALLSET]"
  echo "  [$tag] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  %P):"
  local bad=0
  for x in $ALLSET; do
    TP=$(git -C "$R" --no-replace-objects cat-file commit "$x" | awk '/^$/{exit} /^parent /{printf "%s ", $2}')
    AP=$(git -C "$R" log --format=%P -1 "$x")
    TS=$(printf '%s\n' $TP | sort | tr '\n' ' '); AS=$(printf '%s\n' $AP | sort | tr '\n' ' ')
    if [ "$TS" = "$AS" ]; then RES=일치; else RES="불일치(!!)"; bad=1; fi
    printf '    %s  %-22s cat-file=[%s]  %%P=[%s] → %s\n' "${x:0:12}" "$(git -C "$R" log --format=%s -1 "$x" | cut -c1-22)" "${TP% }" "$AP" "$RES"
  done
  echo "  [$tag] 전건 일치? $( [ "$bad" = 0 ] && echo 'YES ← ㉠ 자연 침묵 성립' || echo 'NO ← ㉠ 침묵 안 함' )"; }

sec "(대조 A) grafts «없는» 정직 이력 — ㉠ 대상 집합 + 판정"
echo "  merge-base --is-ancestor R CN → rc=$(git -C "$R" merge-base --is-ancestor "$RR" "$CN"; echo $?)  (1 = 조상 아님 = 정직)"
emit_set "graft 전"
run "$R"

sec "grafts 주입 — 후보 우주 «밖» 커밋 H0 의 부모만 [S0, R] 로 재작성"
mkdir -p "$R/.git/info"; printf '%s %s %s\n' "$H0" "$S0" "$RR" > "$R/.git/info/grafts"
echo "\$ cat <fixture>/.git/info/grafts"; sed 's/^/  /' "$R/.git/info/grafts"
echo "  merge-base --is-ancestor R CN → rc=$(git -C "$R" merge-base --is-ancestor "$RR" "$CN" 2>/dev/null; echo $?)  (0 = 뒤집힘)"
echo "  --no-replace-objects 하 → rc=$(git -C "$R" --no-replace-objects merge-base --is-ancestor "$RR" "$CN" 2>/dev/null; echo $?)  (여전히 0 = K-4 잔여)"
REL=$(git -C "$R" rev-parse --git-path info/grafts); TOP=$(git -C "$R" rev-parse --show-toplevel); AGD=$(git -C "$R" rev-parse --absolute-git-dir)
echo "  [E15] $TOP/$REL → $( [ -f "$TOP/$REL" ] && echo present || echo ABSENT ) · [뮤턴트] $AGD/$REL → $( [ -f "$AGD/$REL" ] && echo present || echo 'ABSENT ← 거짓 ABSENT' )"

sec "**[BLOCK #6 요구] graft «후» ㉠ 대상 집합 재방출 + 전건 부모 대조** (R=$RR 이 C_R 후보로 «새로» 들어오는지 포함)"
emit_set "graft 후"
echo "  주: graft 로 CN 에서 R 이 도달 가능해지면서 C_R 후보 집합이 ∅ → {R} 로 «커진다» — addendum-7 이 놓친 원소가 이것이다."
echo "     R 자신은 재작성 «대상이 아니므로»(재작성된 것은 H0) cat-file 부모 == %P 로 남는다."

sec "(a) **단일 변수 뮤턴트**(결합 base 만) ⇒ ㉡ 미발화 · ㉠ 침묵 · 조상성 grafts 따라감"
run "$R" "$MUT"
sec "(b) **판정 실행기**(E15) ⇒ ㉡ 발화 ⇒ 차단"
run "$R"
```

### 8-3. `t84v219e8.sh` (sha256 `8b2d43f915194bf5aee25833749fa85c213ec99eafa8b536a110614617995e4b` · 110 행)

```bash
#!/usr/bin/env bash
# t84v219e8.sh — addendum-8 (계약 무변경·에라타 6차 359f5bc5 결속) «영향 변이» 재실행 드라이버 (U-17 축):
#   [BLOCK #6 채택] ㉠ 대상 집합을 **graft 주입 «후»** 에도 방출하고 전건 부모 대조 — addendum-7 은 graft «전» 집합만 기록했다.
# GET-only(seam 위주·본 저장소 live 1회) · 서버 쓰기·설정 변경 0 · 픽스처는 scratchpad 독립 git repo(본 저장소 무접촉·worktree 미사용).
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u17-verify-v219e6.sh"; MUT="$SP/u17-mut-absgitdir-e7.sh"
FX="$SP/fx84m"; SEAM="$SP/seam219e8"
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
gp(){ local v; v=$(git -C "$1" rev-parse --git-path "$2"); case "$v" in /*) printf '%s' "$v";; *) printf '%s/%s' "$1" "$v";; esac; }
probe(){ printf '  ㉠ 재파생 cat-file parent = [%s]\n  ㉠ 이력 뷰 %%P            = [%s]\n  ㉡ git replace -l         = [%s]\n  [E13] --git-path info/grafts = %s → %s   |   «리터럴» .git/info/grafts = %s\n  [E13] --git-path shallow     = %s → %s   |   ㉢ is_shallow = %s\n' \
  "$(tp "$1" "$2")" "$(ap "$1" "$2")" "$(git -C "$1" replace -l | tr '\n' ' ')" \
  "$(git -C "$1" rev-parse --git-path info/grafts)" "$( [ -f "$(gp "$1" info/grafts)" ] && echo present || echo ABSENT )" \
  "$( [ -f "$1/.git/info/grafts" ] && echo present || echo ABSENT )" \
  "$(git -C "$1" rev-parse --git-path shallow)" "$( [ -f "$(gp "$1" shallow)" ] && echo "목록=[$(tr '\n' ' ' < "$(gp "$1" shallow)")]" || echo ABSENT )" "$(git -C "$1" rev-parse --is-shallow-repository)"; }

rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"; SM="$SEAM/rs"; seam_ruleset "$SM"
printf 't84v219e8_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'sha256(u17-verify-v219e6.sh)=%s   (판정 실행기)\n' "$(shasum -a 256 "$EX" | cut -d" " -f1)"
printf 'sha256(u17-mut-absgitdir-e7.sh)=%s  (**단일 변수 뮤턴트** — 결합 base 한 줄만 · ㉠ 발화 «유지»)\n' "$(shasum -a 256 "$MUT" | cut -d" " -f1)"
printf '드라이버 cwd(= «저장소 밖») = %s\n' "$PWD"
echo "-- 단일 변수 확인: 두 실행기의 diff --"; diff "$EX" "$MUT" | sed 's/^/  /'

########################################################################
sec "픽스처 구성 (addendum-7 과 동일 구조 · 후보 우주 «밖» 커밋 W 만 재작성 대상)"
R="$FX/silent"; SEED=$(initrepo "$R")
WC=$(wf "$R"); DC=$(d0a "$R")
git -C "$R" checkout -q --detach "$SEED"; PC2=$(art "$R")
git -C "$R" checkout -q --detach "$DC"; git -C "$R" merge -q --no-ff -m "M: merge artifact branch" "$PC2"; MC=$(git -C "$R" rev-parse HEAD); git -C "$R" branch -f main HEAD
echo "  seed=$SEED"; echo "  W =$WC  ← graft 재작성 «대상»(워크플로만 — 아티팩트·config 경로 없음)"; echo "  d =$DC"; echo "  P =$PC2"; echo "  M =$MC (HEAD)"
git -C "$R" log --oneline --graph --all | sed 's/^/  /'

emit_set(){ local tag="$1" p path x ALLSET bad=0
  local ca="" cc=""
  for x in $(git -C "$R" rev-list --full-history HEAD -- "$PC"); do git -C "$R" cat-file -e "$x:$PC" 2>/dev/null && ca="$ca $x"; done
  for x in $(git -C "$R" rev-list --full-history HEAD -- config/tos_completion.yaml); do git -C "$R" cat-file -e "$x:config/tos_completion.yaml" 2>/dev/null && cc="$cc $x"; done
  echo "  [$tag] 후보(아티팩트 경로 보유) = [$(printf '%s ' $ca)]"
  echo "  [$tag] 후보(config 경로 보유)   = [$(printf '%s ' $cc)]"
  ALLSET=$(printf '%s\n' $ca $cc | sort -u | tr '\n' ' ')
  echo "  [$tag] ㉠ 대상 집합(합집합) = [$ALLSET]"
  echo "  [$tag] W=$WC 가 집합에 있는가? $(printf '%s' "$ALLSET" | grep -q "$WC" && echo 'YES' || echo 'NO ← ㉠ 대상 아님')"
  echo "  [$tag] 전건 부모 대조 (git --no-replace-objects cat-file commit x 의 parent 줄  vs  %P):"
  for x in $ALLSET; do
    TP=$(git -C "$R" --no-replace-objects cat-file commit "$x" | awk '/^$/{exit} /^parent /{printf "%s ", $2}')
    AP=$(git -C "$R" log --format=%P -1 "$x")
    TS=$(printf '%s\n' $TP | sort | tr '\n' ' '); AS=$(printf '%s\n' $AP | sort | tr '\n' ' ')
    if [ "$TS" = "$AS" ]; then RES=일치; else RES="불일치(!!)"; bad=1; fi
    printf '    %s  %-24s cat-file=[%s]  %%P=[%s] → %s\n' "${x:0:12}" "$(git -C "$R" log --format=%s -1 "$x" | cut -c1-24)" "${TP% }" "$AP" "$RES"
  done
  echo "  [$tag] 전건 일치? $( [ "$bad" = 0 ] && echo 'YES ← ㉠ 자연 침묵 성립' || echo 'NO ← ㉠ 침묵 안 함' )"; }

sec "(대조 A) grafts «없는» 정직 이력 — ㉠ 대상 집합 + 판정 ⇒ PREVENTION_LATE(6)"
rev_seam "$SM" "$DC" "$WC"
echo "  merge-base --is-ancestor P d → rc=$(git -C "$R" merge-base --is-ancestor "$PC2" "$DC"; echo $?)  (1 = 조상 아님 = 정직)"
emit_set "graft 전"
run "$R" "file:$SM"

sec "grafts 주입 — 후보 우주 «밖» 커밋 W 의 부모만 [seed, P] 로 재작성"
mkdir -p "$R/.git/info"; printf '%s %s %s\n' "$WC" "$SEED" "$PC2" > "$R/.git/info/grafts"
echo "\$ cat <fixture>/.git/info/grafts"; sed 's/^/  /' "$R/.git/info/grafts"
echo "  merge-base --is-ancestor P d → rc=$(git -C "$R" merge-base --is-ancestor "$PC2" "$DC" 2>/dev/null; echo $?)  (0 = 뒤집힘)"
echo "  --no-replace-objects 하 → rc=$(git -C "$R" --no-replace-objects merge-base --is-ancestor "$PC2" "$DC" 2>/dev/null; echo $?)  (여전히 0 = K-4 잔여)"
REL=$(git -C "$R" rev-parse --git-path info/grafts); TOP=$(git -C "$R" rev-parse --show-toplevel); AGD=$(git -C "$R" rev-parse --absolute-git-dir)
echo "  [E15] $TOP/$REL → $( [ -f "$TOP/$REL" ] && echo present || echo ABSENT ) · [뮤턴트] $AGD/$REL → $( [ -f "$AGD/$REL" ] && echo present || echo 'ABSENT ← 거짓 ABSENT' )"

sec "**[BLOCK #6 요구] graft «후» ㉠ 대상 집합 재방출 + 전건 부모 대조**"
emit_set "graft 후"

sec "(a) **단일 변수 뮤턴트**(결합 base 만) ⇒ green = fail-open"
run "$R" "file:$SM" "$MUT"
sec "(b) **판정 실행기**(E15) ⇒ 차단"
run "$R" "file:$SM"
```

## 9. 관측 보고 · 결함 후보 (등급)

### S-0 **[절차 정정 — 철회]** addendum-7 의 ㉠ 침묵 증명은 «graft 전» 집합이었다

BLOCK #6 지적 그대로다. 근본 원인은 두 겹이다 — ① 후보 계산을 grafts 주입 **전**에 배치 ② `C_R` 열거 범위를 `rev-list CN` 하나로 축소(실행기는 **간선별**). ②는 graft 와 무관한 **드라이버 자체 결함**이며, 정직 실행에서도 `C_R={6de2472}` 가 소비되고 있었다는 사실로 확인된다. 본 파일은 재계산을 폐기하고 **실행기 호출 추적**으로 대체했다. **등급: 절차 결함(증거 방법론) — 결론은 재실증으로 유지.**

### S-1 **[교훈 — 성문화 후보]** «증거가 실행기 밖에서 재계산한 집합» 은 실행기가 소비한 집합과 다를 수 있다

이 아크에서 반복된 결함 클래스(자기신고 → 구조 파생)의 한 변종이다. **구조 파생조차도 «누구의 구조인가» 가 어긋나면 팬텀이 된다**: 드라이버가 계약을 읽고 재구현한 집합은 실행기가 실제로 순회한 집합의 **근사**일 뿐이다. 증거가 «실행기의 판단 대상» 을 주장할 때는 재구현이 아니라 **실행기 호출 자체를 관측**해야 한다(본 파일의 shim). 계약 성문화 후보: *«실행기가 소비한 집합에 관한 주장은 실행기 관측으로 뒷받침한다 — 검증자의 독립 재계산은 대조군이지 근거가 아니다.»* **등급: 문언(계약 반영 여부는 저작자 소관).**

### S-2 **[관측]** grafts 는 ㉠ **검사 대상 집합**을 바꾸지 않는다

세 실행(정직·뮤턴트·판정기)의 추적 집합이 축별로 동일했다. 즉 후보 우주 «밖» grafts 는 ㉠ 의 시야에 아예 들어오지 않으며 조상성 판정만 뒤집는다 — K-4/L-2 가 «㉡ 이 유일 완화 항» 이라고 적은 이유의 직접 실측. **등급: 관측(계약 변경 불요).**

### S-3 **[관측]** `git 2.38.0` 은 `info/grafts` 에 폐기 예고 경고를 낸다

실행 로그에 `힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃 버전에서 제거될 예정입니다` 가 섞인다. 판정에는 영향이 없으나(경고는 stderr), grafts 가 제거된 git 에서는 이 픽스처류의 **재현 경로가 `git replace --convert-graft-file` 로 이동**한다. ㉡ 이 `replace -l` 도 함께 보므로 방어 자체는 유지되지만, **증거 재현 절차의 미래 호환성** 관점의 기록. **등급: 관측.**

### S-4 **[관측 · 신규 결함 후보 없음]**

본 회차에서 **fail-open/차단 등급의 신규 결함 후보는 발견되지 않았다.** 계약 문언 자체를 겨냥한 신규 지적도 없다(S-1 은 증거 방법론 규율 제안이며 판정 규칙 변경이 아니다).
