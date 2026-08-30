# 레인 B 계획 «재심» — 50차 처분 판 (재심 #11)

```yaml
adjudicator: codex
verdict: approve
reviewed_at_head: 2cdf2541
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: e7af79e02d36fd29f1b221cc9f95fd40e03a09216f44e58a37a32bb731f9dfbe
bound_set_digest: daaba47b1c4b2b31717c098c8d761d9fd2b0cd1eb7e0d55b48d46a4e059f1c3b
job_id: review-mtfbo7h2-47vquv
job_class: review
base: 169414b8
scope: branch
cancelled_jobs:
  - review-mtfatdwx-altb5o   # 로그 11분 무성장 — 취소
  - review-mtfb9wve-3z6oxb   # 로그 8분 반 무성장 — 취소 후 범위 축소 재시도
prior_verdict: docs/reviews/phase0-completion-contract/20260830-093036/verdict.md
```

**이 아크 최초의 `approve` 다.  그러나 게이트는 열리지 않는다.**  findings **0** ·
신규 material **0**.  approve 조건은 「**재심 2회 연속 material 0 + 그 사이 편집 0**」이고
이번은 그 **첫 판**이다.  S-26 ② 카운터가 **열두 판 만에 처음으로 1** 이 됐다.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "approve",
  "summary": "출하 차단할 신규 material을 찾지 못했다. #10은 회피가 아니라 해소됐다: `allow_mutable=True`는 측정 CLI 한 곳뿐이고, 인메모리 실측에서 worktree 기준선은 C2UP·CAP2-FIXTURE 각각 1건 red였다. 기본 검사 rc 0, 미앵커 67·닫힌 표 32·픽스처 셀 17, 결속 digest 일치를 확인했다. 신규 대조군 4종과 총 141종의 정의는 확인했으나, 읽기 전용 환경에 사용 가능한 임시 디렉터리가 없어 `--self-test`는 rc 2로 중단되어 141종 전건 판별·죽은 검사 0은 독립 재검증하지 못했다. (b) 핀 이전 세탁과 기존 셀 안 숨기기는 기존 등재 잔여로 유지하며 finding으로 세지 않았다.",
  "findings": [],
  "next_steps": [
    "쓰기 가능한 임시 디렉터리 환경에서 `.venv/bin/python tools/tos_contract_check.py --self-test`를 재실행해 141종 전건 판별·죽은 검사 0을 확인한다."
  ]
}
```

원문 전체(잡 메타 포함)는 `.omc/review/20260830-131640/codex-raw.json`.

---

## 수용검사 (오케스트레이터 = Claude)

**채택 0 · 기각 0 · 팬텀 0** (findings 0).  게이트 조건 대조는 아래.

### 결속 대조 — 전건 일치

| 값 | 포착 | 재계산 | 판정 |
|---|---|---|---|
| `plan_scope_digest` | `e7af79e0…` | `e7af79e0…` | **일치 — 심사 중 편집 0** |
| `bound_set_digest` (OQ-11 `2cdf2541` 기입) | `daaba47b…` | `daaba47b…` | **일치 — 결속 유효** |
| `reviewed_at_head` | `2cdf2541` | HEAD 동일 · 트리 clean | 일치 |

### 게이트 통과 조건 (레인 B)

```
adjudicator: codex ✔  +  verdict: approve ✔  +  digest 일치 ✔
```

세 조건은 **성립**한다.  그러나 이 아크는 그 위에 **자체 조건**을 더 두고 있다 —
「재심 2회 연속 material 0 + 그 사이 편집 0」.  **이번은 1회차다.**  D0/P-0 착수 금지는
불변이며, 다음 재심까지 계약 문서를 편집하면 카운터는 0으로 돌아간다.

### approve 의 «범위» — 이 판이 승인한 것과 승인하지 않은 것

심판이 **스스로 적은 미검증 레그**가 있다: 읽기 전용 샌드박스에 임시 디렉터리가 없어
`--self-test` 가 **rc 2 로 중단**됐다.  그러므로 이 approve 는

- **승인한 것**: `allow_mutable=True` 가 측정 CLI 한 자리뿐이라는 구조 · worktree 기준선이
  C2UP·CAP2-FIXTURE **두 축 모두 red** 라는 실측 · 검사기 rc 0 · 래칫 67/32/17 · 결속 일치 ·
  신규 대조군 4종과 141종의 **정의 실재**.
- **승인하지 «않은» 것**: 그 141종이 **실제로 판별력을 갖는가**(전건 판별 · 죽은 검사 0).
  그 레그는 **오케스트레이터의 실행에만** 근거한다 — 즉 **저작자가 자기 배터리를 돌린 것**이다.

이 구별을 흐리면 approve 가 실제보다 넓어진다.  **심판이 배터리를 완주하지 못한 것은 이번이
세 회차 연속**이다(#9 PyYAML 부재 · #10 임시 디렉터리 부재 · #11 임시 디렉터리 부재).
심판 레인의 실행 표면은 **구조적 제약**이며, 이 아크의 「대조군 없는 심사는 의견이다」 규율이
가장 직접적으로 적용되는 자리다.

### 독립 재현 (오케스트레이터 · 판정 전에 먼저 돌린 것)

| 실측 | 결과 |
|---|---|
| 실저장소 루트 · `kind` 만 worktree 로 바꾼 기준선 | **C2UP 1건 + CAP2-FIXTURE 1건 red** — 계약 문언 「두 축 모두 red」가 참 |
| 재심 #10 반례(문서 +1 셀 AND 기준값 상향 AND worktree) | **red** — 49차 판에선 0건이었다 |
| 기준선 출처를 읽는 다른 경로 | **없음** — `read_commit_blob` 호출부는 `read_baseline_source` 안 1자리뿐 |
| `allow_mutable=True` 누출 | **1자리**(`measure_baseline`)뿐 |
| **세 번째 호출부** `build_baseline_fixtures` | 플래그 없이 호출 → **자동 fail-closed**.  호출자별 가드였다면 빠졌을 자리다 |
| 네 번째 스윕 자리 | **부재** — 「불변 blob」 전역 grep 이 이미 쓴 세 자리로 닫힌다(부재 방향 확인) |
| `--self-test` | **141종 전건 판별 · 죽은 검사 0** — *단, 이것은 저작자 실행이다* |

### 비협상 규칙 대조

**배치 0 — 25판 연속.**  findings 0 이므로 기각 대상 자체가 없다.

### S-26 ② 카운터

**1 — 열두 판 만의 최초 기립.**  궤적: findings 4 → 2 → 3 → 2 → 1 → 2 → 1 → 1 → 1 → 1 → **0**.
층의 하강은 여기서 멈춘다: 면제의 단위 → 판별 순서 → 운반체 → 정체의 종류 → 정체의 «출처» →
출처의 «불변성» → **(신규 없음)**.

---

## 오케스트레이터 관측 (판정 아님)

1. **이 approve 는 «범위 축소된 focus» 위에서 났다.**  3차 디스패치에서 focus 를 절반 이하로
   줄이고 계약 문서 통독 대신 diff 가 닿은 자리만 보게 했다(앞 두 잡이 대용량 문서 읽기 직후
   멈췄기 때문).  `--base`·`--scope`·결속 경로·digest 는 **전부 불변**이므로 결속은 온전하지만,
   **심판이 본 표면은 앞 두 회차보다 좁다.**  findings 0 을 읽을 때 이 사실을 함께 읽어야 한다.
2. **배터리 판별력의 독립 검증이 세 회차째 비어 있다.**  이것은 «이번 판의 결함»이 아니라
   **심판 레인의 구조적 공백**이다.  닫으려면 심판이 쓰기 가능한 작업 디렉터리를 갖거나,
   배터리가 임시 디렉터리 없이 돌 수 있어야 한다.  후자는 검사기의 변경이므로 **다음 판의
   후보**이지 이 판정의 처분이 아니다.
3. **다음 재심이 카운터의 두 번째 판이다.**  그 사이에 계약 문서를 편집하면 「그 사이 편집 0」이
   깨져 카운터가 0 으로 돌아간다 — 위 관측 2 를 처분하려면 **검사기만** 만지고 계약 문서는
   건드리지 않는 경로를 찾아야 한다.

---

## 운영 기록 (정직)

**이 회차는 심판 잡을 세 번 띄웠다.**

| 잡 | 결과 |
|---|---|
| `review-mtfatdwx-altb5o` | 로그 `04:18:13Z` 이후 **11분 무성장** → 취소 |
| `review-mtfb9wve-3z6oxb` | 로그 `04:32:18Z` 이후 **8분 반 무성장** → 취소 |
| `review-mtfbo7h2-47vquv` | **완주 2분 20초** — 이 판정의 출처 |

**절차 이탈(명시)**: 이번 회차는 `codex-plan-reviewer` 포워더를 거치지 않고 오케스트레이터가
companion 을 직접 호출했다.  사유는 포워더 경유가 **세 회차 연속 다른 형태로 깨졌기** 때문이다
(#8 판정문 오독 · #9 매달림 대응 · #10 중복 디스패치 + verbatim 대신 요약 반환).  심판자는
그대로 Codex 이고 verbatim 은 `result --json` 원문을 보존했으므로 **독립성 성질은 유지**된다 —
포워더는 독립성의 원천이 아니라 전달 경로다.  다만 이것은 하네스 계약의 이탈이므로 기록한다.

**내 탐지기가 한 번 틀렸다.**  첫 잡을 「죽었다」고 판정하며 근거 셋(로그 무성장 · `pid` 부재 ·
`status: running` 의 stale)을 댔는데, `sessionRuntime.mode = shared` 에서는 실제 작업이 broker
프로세스에서 돌고 잡 레코드의 `pid` 는 이미 빠져나간 래퍼다.  **「pid 부재 = 사망」은 정상
상태와 구별되지 않는다.**  유효한 근거는 로그 무성장 하나뿐이었고, 결론은 그것만으로 서지만
증거 셋으로 제시한 것은 과했다.  두 번째 감시에서 그 레그를 제거했다.
**대조군 없이 만든 탐지기의 판정도 의견이다** — 이 아크의 규율이 도구에도 적용된다.
