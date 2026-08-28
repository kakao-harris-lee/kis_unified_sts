# U-17 예방 통제 — 운영자 런북

> **상태**: 운영자·인프라 실행 문서.  **저작자(코딩 에이전트)가 수행할 수 없는 단계만** 모았다.
> **기준 커밋**: `e9bcdc5f`.  본문의 모든 실측은 그 시점 값이다.
> **목적**: `u17-verify` 가 `prevention_control_state=PREVENTION_ACTIVE` 를 내게 하는 것.
> 그것이 `D0-A` 착수 차단의 **실제 해제 조건**이다(계약 §12.3.4 `U-17`).
> **이 문서는 권한을 부여하지 않는다** — ADR acceptance · `restricted_live` · `production`
> 불변이고, **D0/P-0 착수 금지는 이 런북을 다 밟아도 «그 자체로는» 풀리지 않는다**
> (진입은 하니스의 `d0a_entry_state=ENTRY_OK` 와 함께 판정된다).

---

## 0. 왜 저작자가 못 하는가 — 경계를 먼저 적는다

| 단계 | 왜 저작자 밖인가 |
|---|---|
| **아티팩트 `operator_countersign`** | 실행기가 요구하는 **필수 내용이 운영자 서명 하나**다(§2).  대신 쓰면 **운영자 승인 기록의 위조**다.  하지 않는다. |
| **`main` 에 장치 착지** | 머지 결정은 운영자.  **524 커밋 · 1,543 파일** 규모이고, `main` 에는 **TOS Phase-0 장치가 하나도 없다**(§1). |
| **브랜치 보호 필수 체크 등재** | 저장소 관리 권한이 필요하고, **그 설정 자체가 세우려는 통제**다. |

계약도 같은 말을 한다 — 「**여는 것은 푸시가 아니라 «머지 + 필수 체크 등재»이고 저작자
권한 밖**」(§S-26 ①ⓑ 앞 문단).

---

## 1. 현재 상태 — 실측

```bash
bash tools/u17-verify.sh
#   prevention_control_state=PREVENTION_ABSENT
#   reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
#          [수집 3건 중 전순서 최소]
```

**세 건이 «동시에» 걸려 있고 전순서가 가장 작은 것만 보인다**(실행기 `finish()` 규칙).

| 전순서 | 상태 | 원인 | 소관 |
|---|---|---|---|
| **2** | `PREVENTION_ABSENT` | 아티팩트 부재 | **운영자** (§2) |
| **5** | `PREVENTION_INSUFFICIENT` | `main` 필수 체크에 `tos-gate` 없음 (현재 `["test"]` 뿐) | **운영자** (§4) |
| **8** | `PREVENTION_UNVERIFIED_REVISION` | `tos-gate.yml` 이 `main` HEAD 에 부재 (http=404) | **운영자** (§3) |

전순서 전체: `UNVERIFIABLE 1 · ABSENT 2 · UNSIGNED 3 · TARGET_MISMATCH 4 · INSUFFICIENT 5 ·
LATE 6 · ARTIFACT_MUTATED 7 · UNVERIFIED_REVISION 8 · CONTINUITY_UNVERIFIABLE 9` ·
**`ACTIVE` 는 하나도 발화하지 않을 때만** 나온다.

### 1.1 도입 집합 4종의 현황

| # | 항목 | 상태 |
|---|---|---|
| 1 | `.github/workflows/tos-gate.yml` — **default 브랜치에** | **없음** (작업 브랜치엔 있음) |
| 2 | `tools/tos_entry_harness.sh` | 있음 (작업 브랜치) |
| 3 | `tools/u17-verify.sh` | 있음 (작업 브랜치) |
| 4 | 룰셋 required check `tos-gate` | **없음** (`contexts=["test"]` · `strict=false`) |

### 1.2 **`main` 에는 장치가 하나도 없다** — «한 파일만 올리기»는 불가능하다

```bash
for f in docs/plans/2026-08-12-tos-phase0-completion-contract-design.md \
         docs/plans/2026-08-11-tos-completion-development-plan.md \
         tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md \
         tools/tos_entry_harness.sh \
         .github/workflows/tos-gate.yml \
         .github/workflows/tos-firewall.yml ; do
  git cat-file -e origin/main:"$f" 2>/dev/null && echo "있음  $f" || echo "없음  $f"
done
#   → 여섯 전부 «없음»  (docs/reviews/phase0-completion-contract 도 없음)
```

`tos-gate.yml` 은 `tools/tos_entry_harness.sh` 를 실행하고, 그 하니스는 **계약 문서 ·
상위 계획 · `OQ-11-DISPOSITION.md` · 심사 스탬프 디렉터리**를 읽는다.  ⟹ **워크플로 한 개만
올리면 잡이 `HARNESS_ABORTED: 입력 부재` 로 죽는다.**  착지 단위는 **의존 사슬 전체**다.

---

## 2. 단계 A — 아티팩트 `D0A-PREVENTION-CONTROL.md` (운영자 서명)

**경로**: `tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md`
**작업 브랜치에 커밋**한다(실행기는 `git show HEAD:<경로>` 로 **커밋본만** 읽는다).

### 2.1 실행기가 요구하는 것 — **필수는 하나뿐이다**

```text
operator_countersign: "<서명자> <ISO8601 UTC>"        ← 정확히 1회 · 형식 강제
```

정규식(실행기 `CS_RE`)이 요구하는 형태:

```
^operator_countersign:[ \t]*"<공백·따옴표 아닌 문자로 시작하는 이름> YYYY-MM-DDTHH:MM:SSZ"[ \t]*(#주석)?$
```

예:

```yaml
operator_countersign: "harris.lee 2026-08-28T09:30:00Z"
```

* 키가 **0회 또는 2회 이상**이면 `PREVENTION_UNSIGNED`(전순서 3).
* 값 형식이 어긋나도 `PREVENTION_UNSIGNED`.

### 2.2 선언 파라미터는 **선택**이다 (실행기 `[E2]`)

`owner_repo` · `target_branch` · `host` 는 **써도 되고 안 써도 된다.**
쓰면 **계약 핀과 대조**되고 어긋나면 `PREVENTION_TARGET_MISMATCH`(전순서 4).
안 쓰면 **계약 핀과 API 파생이 유일 소스**다.

```text
계약 핀 (아티팩트가 «선언하지 않는다»):
  CANON      = github.com/kakao-harris-lee/kis_unified_sts     ← u17-verify:71
  WF_PATH    = .github/workflows/tos-gate.yml                  ← u17-verify:73
  게이트 체크 이름 = tos-gate                                    ← 계약 리터럴 (F#2 로 아티팩트에서 «제거»됨)
```

> **게이트 체크 이름을 아티팩트에 쓰지 마라.**  계약이 그것을 **의도적으로 파라미터에서
> 제거**했다 — 아티팩트가 이름을 «선언»하면 그것이 자기선택 표면이 된다(계약 F#2/N-4).

### 2.3 최소 예시 (내용은 운영자가 확정한다)

```markdown
# D0A-PREVENTION-CONTROL

> 비규범 결정 기록.  진실 원천이 아니다 — 진실은 서버(브랜치 보호·룰셋)에서 파생한다.
> 이 파일의 역할은 ① 운영자 countersign ② (선택) 파라미터 선언 둘뿐이다.

operator_countersign: "<서명자> <YYYY-MM-DDTHH:MM:SSZ>"

# 선택 — 쓰면 계약 핀과 대조된다 (틀리면 PREVENTION_TARGET_MISMATCH)
# owner_repo: github.com/kakao-harris-lee/kis_unified_sts
# target_branch: main
```

**검증**: `bash tools/u17-verify.sh` 가 더 이상 `PREVENTION_ABSENT` 를 내지 않고
**다음 전순서(예상 `PREVENTION_INSUFFICIENT`)** 로 옮겨가면 이 단계는 끝났다.

---

## 3. 단계 B — `main` 에 장치를 착지시킨다 (**룰셋보다 «먼저»**)

### 3.1 순서가 강제된다 — 뒤집으면 자기 차단이다

계약이 못박은 도입 순서:

> **`tos-gate.yml` · 하니스 파일 · `u17-verify` 를 «먼저», 룰셋을 «마지막»으로 둔다.**
> 룰셋(required check)을 먼저 활성화하면 **그 뒤에 `tos-gate.yml` 을 올리는 PR 자신이**
> 영원히 pending 인 필수 체크에 걸려 머지되지 못한다.

**이 순서를 지키지 않으면 저장소가 스스로를 잠근다.**

### 3.2 착지 방법 — 운영자 선택

| 안 | 내용 | 대가 |
|---|---|---|
| **(A) 브랜치 머지** | `mission-critical-trading-operating-system` → `main` (524 커밋 · 1,543 파일) | 크지만 의존 사슬이 자동으로 완비된다.  PR #637 은 **CI 증거용 draft** 이므로 그대로 쓰지 말고 별도 판단 |
| **(B) 큐레이션 PR** | §1.2 의 여섯 경로 + `docs/reviews/phase0-completion-contract/` 만 골라 착지 | 작지만 **계약 문서를 이력 없이 `main` 에 올린다** · 누락 시 잡이 `HARNESS_ABORTED` |

**어느 쪽이든 `.github/workflows/tos-firewall.yml` 도 함께 올리는 것을 권한다** — 그것이
Layer-4 계약 게이트를 담고 있고, 이미 PR 에서 **pass** 가 확인됐다.

### 3.3 검증

```bash
git fetch origin main
git cat-file -e origin/main:.github/workflows/tos-gate.yml && echo "착지됨"
gh api repos/kakao-harris-lee/kis_unified_sts/actions/workflows/tos-gate.yml -q '.state'
```

---

## 4. 단계 C — 룰셋 필수 체크 등재 (**마지막**)

> **⚠ 「`tos-gate` 추가」 하나로는 끝나지 않는다.**  실행기가 낸 실제 사유는 **넷**이다
> (실측 · `e9bcdc5f`):
>
> ```text
> (a) classic:[ contexts∌tos-gate
>              ; strict≠true
>              ; enforce_admins≠true
>              ; required_pull_request_reviews 키 부재 ]
>     ruleset:[ 적용 규칙 0 ]
> ```
>
> **하나만 고치면 `PREVENTION_INSUFFICIENT` 가 그대로 남는다.**  네 항을 함께 설정한다.

`main` 브랜치 보호(현재 `contexts=["test"]` · `strict=false`)를 다음으로 만든다:

| # | 항목 | 현재 | 필요 |
|---|---|---|---|
| 1 | required status checks `contexts` | `["test"]` | **`tos-gate` 포함** |
| 2 | `strict` (머지 전 최신 브랜치 요구) | `false` | **`true`** |
| 3 | `enforce_admins` | 미충족 | **`true`** |
| 4 | `required_pull_request_reviews` | **키 부재** | **키 존재**(리뷰 요구 설정) |

* GitHub UI: Settings → Branches → `main` → 위 넷을 함께 켠다
  (Require status checks + Require branches to be up to date + Do not allow bypassing +
  Require a pull request before merging).
* 실행기는 `checks[].app_id` 가 **GitHub Actions 앱**인지까지 본다 — **제3자 앱에 같은 이름을
  고정하면 거부**된다(계약 C1).
* 실행기는 `branches/<target>/protection` · `rules/branches/<target>` · `rulesets` ·
  `rulesets/{id}`(`bypass_actors`) 넷을 조회한다.  **`bypass_actors` 가 넓으면** 통제가
  «충분»으로 인정되지 않을 수 있다.
* `ruleset:[적용 규칙 0]` — 현재 `main` 에 **적용된 룰셋이 0개**다.  classic 보호로 갈지
  ruleset 으로 갈지는 운영자 선택이고, 실행기는 **둘 다 조회**한다.

> **`enforce_admins=true` 와 `required_pull_request_reviews` 는 운영자 자신에게도 적용된다.**
> 이 저장소의 평소 작업 방식(직접 push)이 막힌다 — **그 대가를 알고 켜야 한다.**
> 이것은 «통제»의 정의상 당연한 귀결이지 부작용이 아니다.

### 4.1 검증

```bash
gh api repos/kakao-harris-lee/kis_unified_sts/branches/main/protection \
  -q '.required_status_checks | {strict, contexts, checks}'
bash tools/u17-verify.sh          # 기대: prevention_control_state=PREVENTION_ACTIVE
```

---

## 5. **부수 효과 — 단계 B 는 계약의 살아 있는 주장을 거짓으로 만든다**

에라타 36차가 limb 단위로 처분하면서 **유일하게 «살아남은» limb** 이 이것이다:

> `tos-firewall.yml`·`tos-gate.yml` 은 **`origin/main` 이력에 한 번도 존재한 적이 없고**
> (`git log origin/main -- <두 경로>` = ∅)

**단계 B 를 수행하면 이 limb 이 거짓이 된다.**  ⟹ **에라타가 하나 필요해진다.**

이것은 이 세션이 관측한 클래스 그대로다 — **원인이 저작자의 편집이 아니라 문서 «밖»의 상태
변화**이고, ⑥ 이 예외 없이 리셋하므로 **그 에라타가 S-26 ② 의 카운터를 다시 0 으로 만든다.**
**미리 적어 둔다** — 놀랄 일이 아니라 **예고된 대가**다.

같은 이유로 **PR #637 을 닫으면** 「이 브랜치발 PR 0건」이 다시 참이 되어 36차가 처분한
자리가 되살아난다.  **PR 을 닫기 전에 그 사실을 인지할 것.**

---

## 6. 이 런북이 «하지 않는» 것

* **`PREVENTION_ACTIVE` 를 보장하지 않는다.**  §1 의 세 건 외에 `LATE`(6) ·
  `ARTIFACT_MUTATED`(7) · `CONTINUITY_UNVERIFIABLE`(9) 같은 항이 착지 «후»에 발화할 수 있다.
  현재는 **`D = ∅`(P-0 미착수) 라 그 항들이 vacuous** 이고, 착지가 `D` 를 비우지 않는지는
  **수행 후에 재야** 안다.
* **D0/P-0 착수를 허가하지 않는다.**  진입은 `u17` 과 **하니스**(`d0a_entry_state`)를
  함께 본다.  하니스는 현재 `REBINDING_REQUIRED`(`bound_set_digest` 불일치)이고 그 해소는
  **O-6 재결속**이며 별개 트랙이다.
* **단계 A 의 서명 내용을 제안하지 않는다.**  서명자와 시각은 운영자의 사실이다.

---

## 7. 요약 — 실행 순서

```text
A. 아티팩트 countersign 커밋      (운영자 서명 · 작업 브랜치)     → ABSENT 해소
B. main 에 장치 착지              (룰셋보다 «먼저»)              → UNVERIFIED_REVISION 해소
C. 룰셋에 tos-gate 필수 체크 등재  («마지막»)                     → INSUFFICIENT 해소
   그 뒤 bash tools/u17-verify.sh  → 기대 PREVENTION_ACTIVE
D. (예고된 대가) 에라타 1회 — §5
```

**A 와 B·C 는 서로 독립이므로 순서를 바꿔도 된다.  B 와 C 의 순서만은 바꾸면 안 된다.**
