# 레인 B 계획 심판 — 현행 버전 재심 (v2.22 · 에라타 9차 이후)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 4324b02f795a2edb6ee96d59b4a3b7e65d92246c
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 9416bcc602069f9641b488bf73be79b6d563de85e29d295b484a9dbd145cafc3
job_id: review-mt8v0agd-6b1abv
job_class: review            # adversarial-review = 게이트 적격 유일 경로
elapsed: 3m 33s
bound_set_digest_at_review: a52ee61ae9d0284ebc7aceb57091a6304974a5718420fc87e69c4281f566b09d   # O-6 재결속 7e165b6e
```

**게이트 판정: 통과 아님.** `adjudicator: codex` ✓ · `reviewed_scope_digest` 일치 ✓ ·
그러나 `verdict: approve` 가 아니다 — 세 조건은 AND 이므로 **D0/P-0 착수 불가**가 유지된다.
인용 시점 digest 재계산 결과 `9416bcc6…` 로 심사 시점과 **일치**함을 확인했다(결속 성립).

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "NO-SHIP. 대상 문서의 working-tree diff는 없지만 현행 계약도 착수 불가다. 직전 findings 5는 F#1·F#3·F#4·F#5는 해소, F#2는 조건부 차단으로 대체한 회피/미해소로 판정한다. D0-A는 예방 통제 4종과 재결속·approve가 없어 착수 불가다. ‘규칙 신설=전수 적용’은 산문뿐이며 기계 소비자가 없다. 에라타 7차 이후 새 findings가 9→3→기지 입력 7로 계속 발생해 수렴 구조로 볼 수 없다. S-24 limb ②의 측정된 byte-불변 대체는 10/10 생산 술어와 gen-3→gen-4 9/9 대조군이 비공허성을 입증하므로 그 limb에 한해서는 타당하지만, 계약 전체 종결을 증명하지 않는다. CLAUDE.md 비협상 규칙과의 직접 충돌은 확인되지 않았다.",
  "findings": [
    {
      "severity": "high",
      "title": "D0-A는 필수 예방 통제 부재로 착수할 수 없다",
      "body": "개발계획은 tos-gate 룰셋, workflow, 하니스, u17-verify를 D0-A 이전 필수조건으로 두고 파일 3종 후 룰셋 순서를 강제한다. 기지 사실대로 네 통제가 모두 부재하면 PREVENTION_ACTIVE가 성립할 수 없고, 계약의 3단 가드도 실행 불가능하다. 따라서 이 계획은 현재 Phase 0 구현 착수 가능한 상태가 아니다.",
      "file": "docs/plans/2026-08-11-tos-completion-development-plan.md",
      "line_start": 270,
      "line_end": 286,
      "confidence": 1,
      "recommendation": "D0/P-0를 시작하지 말고 파일 3종을 먼저 실체화·검증한 뒤 룰셋을 마지막에 활성화하며, live 조회로 PREVENTION_ACTIVE를 입증하고 O-6 재결속 및 approve를 취득하라."
    },
    {
      "severity": "high",
      "title": "1,000-suite finding은 해소가 아니라 조건부 이연이다",
      "body": "7차는 심판이 요구한 suite별 check-run 완전 순회를 채택하지 않고 check-suites.total_count가 1,000을 넘으면 차단하는 guard로 대체했다. 그러나 계약 스스로 check-suites가 잘리지 않은 참값을 준다는 근거는 문서 침묵에서의 추론이며, 그 가정이 틀리면 fail-open이라고 인정한다. 즉 원래의 잘린 우주 위 vacuous green을 다른 미증명 상류 계수로 옮겼을 뿐이다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 5540,
      "line_end": 5560,
      "confidence": 0.99,
      "recommendation": "공식 지침대로 suite를 완전 열거한 뒤 suite별 check-run을 소비하고 그 열거 자체의 완전성도 독립 관측하라. 불가능하면 해당 범위에서는 PREVENTION_ACTIVE를 발행하지 않는 명시적 미지원 계약으로 축소하라."
    },
    {
      "severity": "high",
      "title": "‘규칙 신설과 전수 적용은 한 단위’가 기계적으로 강제되지 않는다",
      "body": "계약은 일반 규칙을 선언하지만, 8차 기록은 7차가 새로 만든 상한 규칙을 같은 열거의 actions/runs 소비처에 적용하지 않았다고 자인한다. 이후의 ‘전수 적용 결과’도 문서 내 수동 census일 뿐 신규 규칙과 모든 소비처의 대응을 검증하는 validator/checker 계약이 아니다. 따라서 다음 규칙 추가 때 동일한 형제 미전파가 다시 green으로 남을 수 있다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 5562,
      "line_end": 5571,
      "confidence": 0.98,
      "recommendation": "규칙 ID, 적용 대상 우주, 각 소비처를 독립 manifest에서 파생하고 누락·잉여·중복을 fail-closed로 검사하는 validator를 필수 게이트에 결속하라. 규칙 추가 mutation이 소비처 누락을 반드시 red로 만드는 대조군도 추가하라."
    },
    {
      "severity": "high",
      "title": "완료 계약이 결함 발견 속도를 따라잡지 못해 미종결이다",
      "body": "v2.22 재심의 5건을 7차가 처분한 직후 addendum-3이 9건을, 8차 뒤 addendum-4가 3건을 냈고, 기지 입력의 addendum-5가 다시 7건을 냈다. 현행 문서도 9차 이후 재결속과 v2.23 재심 전이라고 명시한다. 이는 단순 잔여 backlog가 아니라 규칙·열거·자기인용 교정이 새 결함을 지속 생성하는 구조이며, 현재 증거로는 수렴을 주장할 수 없다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 148,
      "line_end": 148,
      "confidence": 0.99,
      "recommendation": "새 에라타 추가를 중지하고 정규화된 단일 소스와 기계 소비자를 먼저 구축하라. 동결된 동일 입력에 대해 독립 재심 두 회 연속 신규 material finding 0, stale 참조 0, 전수 규칙 mutation red를 종결 기준으로 요구하라."
    }
  ],
  "next_steps": [
    "D0/P-0 착수를 계속 차단한다.",
    "F#2를 suite별 완전 순회로 재설계하거나 미지원 범위를 명시적으로 차단한다.",
    "규칙-소비처 전수 대응 validator와 mutation gate를 계약에 결속한다.",
    "기지 addendum-5의 7건과 본 findings를 처분한 뒤 O-6 재결속 및 v2.23 독립 재심을 수행한다."
  ]
}
```

---

## 수용검사 (오케스트레이터 = Claude)

**채택 4 · 기각 0 · pre-existing 분리 0.**

| finding | `file:line` 실재 | 의도적 silence 여부 | 비협상 규칙 배치 | 처분 |
| --- | --- | --- | --- | --- |
| F1 D0-A 착수 불가 | ✔ 개발계획 :270-286 = 「선행 조건 (D0-A 착수 전)」 블록 실재 · 파일 3종 → 룰셋 순서 강제 문단 실재 | 아님 | 없음 | **채택** |
| F2 1,000-suite = 조건부 이연 | ✔ 계약 :5541 `S.total_count > 1000 → PREVENTION_UNVERIFIABLE` · :5553-5556 「도달 난망이지만 전칭 주장을 하므로 관측면을 둔다」 실재 | 아님 | 없음 | **채택** |
| F3 규칙 전수 적용 기계 강제 부재 | ✔ 계약 :5562-5565 = 8차 ⓓ 「같은 규칙의 두 번째 적용」 실재 | 아님 | 없음 | **채택** |
| F4 수렴하지 않는다 | ✔ 계약 :148 = 심사 이력 v2.22 행 실재 | 아님 | 없음 | **채택** |

**팬텀 finding 0건.** 네 인용 좌표를 전부 원문에서 실측했고 내용이 finding 서술과 일치한다.

**비협상 규칙 대조 (`CLAUDE.md`)**: 네 권고 어느 것도 선물 long/short 대칭 훼손 · 실계좌 증거금 ·
주식 EOD 일괄청산 · ClickHouse 신규 사용 · RL/TFT 부활 · 임계값/포트/Redis DB 하드코딩 ·
Redis DB 1 이탈 · 비-KST 세션 판정을 요구하지 않는다. **배치 0건 — 기각 사유 없음.**
(F1 의 «live 조회로 PREVENTION_ACTIVE 입증»은 GitHub REST GET 이며 KIS 실주문과 무관하다.)

## 1순위 과업의 답 — 직전 5건의 해소 vs 회피

Codex 판정: **F#1 · F#3 · F#4 · F#5 = 해소 · F#2 = 회피/미해소**(조건부 차단으로 대체).
아크 회계로는 **해소 4 · 회피 1**이며, F#2 는 「잘린 우주 위 vacuous green 을 **다른 미증명
상류 계수로 옮겼을 뿐**」이라는 것이 차단 사유다.  이는 이 아크가 v2.19 이래 F#2 계열에
대해 반복해 온 «부분해소» 판정이 이번에 **회피로 굳어졌다**는 뜻이다.

## 이 재심이 낸 가장 무거운 결론 — F4

**「완료」를 판정하는 문서가 결함 발견 속도를 따라잡지 못한다.**  회차별 신규 findings 는
재심 5 → addendum-3 **9** → addendum-4 **3** → addendum-5 **7** 이다.  Codex 의 처방은
«에라타 추가 중지 → 정규화된 단일 소스와 기계 소비자 선행 구축»이고, 종결 기준으로
**「동결된 동일 입력에 대해 독립 재심 2회 연속 신규 material finding 0 · stale 참조 0 ·
전수 규칙 mutation red」**를 요구한다.  이 저장소가 지금까지 쓴 «회차마다 값을 고치는»
방식으로는 이 기준에 도달하지 못한다는 것이 판정의 요지다.

## 심판 레인 운영 기록 (이번 실행의 실패 3회 — 전부 Codex 장애가 아니었다)

| 잡 | 종료 | 실제 원인 |
| --- | --- | --- |
| `task-mt8t5ktx-6z5stv` | cancelled (8m 0s) | 오케스트레이터 취소 — 결속 드리프트 + **`jobClass: task` = 게이트 부적격**(스키마를 프롬프트에 손으로 기입) |
| `review-mt8tgwen-sjha2z` | cancelled (5m 24s) | 호출 래퍼가 도구 타임아웃에 사망 → 잡 취소 |
| `review-mt8trkha-zjrg4g` | 프로세스 사망 · 상태는 `running` 잔존 (34m 46s) | **유일한 진짜 실패.** 30초간 정상 grep 후 32분 무활동, pid 소멸 |
| `review-mt8v0agd-6b1abv` | **completed (3m 33s)** | 범위 축소 재시도(스킬 규정 1회) — 성공 |

**포워더가 이 실패들을 `CODEX_UNAVAILABLE`(네트워크/플러그인 오류)로 보고했으나 근거가
없었다** — 두 건은 «Cancelled by user» 이고 타임라인 주장(「1시간 이상 전」·「PID 83682」)도
실측(8m/5m24s)과 어긋났다.  **근거 없는 폴백 강등은 게이트를 스스로 무의미하게 만든다**
(폴백은 구조적으로 `approve` 를 낼 수 없고, 표시 없는 폴백은 비독립 심판을 독립 심판으로
위장시킨다).  자기신고 대신 `status --json` 과 `ps` 로 구조에서 파생한 관측을 썼다.

**플러그인 결함 관측(비차단·기록만)**: 프로세스가 죽어도 상태 레코드가 `running` 으로 남고,
그 상태에서는 `result` 회수가 거부된다 — **「매달림」과 「사망」이 `status` 만으로 구별되지
않는다.**  `ps -p <pid>` 로 직접 확인해야 한다.

**게이트 규약 관측(비차단·기록만)**: 레인 B `plan_scope_digest` 가 `git rev-parse HEAD` 를
포함하므로 **계약 blob 이 byte-동일해도 무관한 커밋 하나로 결속이 깨진다**
(실측 `08fb6af0…` → `9416bcc6…`, 계약 blob 은 `2408f2929a5d` 로 불변).  `codex-gate` 스킬
본문은 레인 B 를 「무관한 변경이 계획 approve 를 무효화하지 않게」 좁혔다고 적는데 수식이 그
의도와 어긋난다.  실무 영향 = **심사 중 트리 동결 필요**.  스킬 소유자 판단 사항이라
여기서 고치지 않고 등재만 한다.
