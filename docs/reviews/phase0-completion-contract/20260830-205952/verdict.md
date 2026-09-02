# 레인 B 계획 «재심» — 54차 판 (재심 #16)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 501f8fe2
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 7ecd7a8ec2729f43e6cda87136d24d4259c63b6203e96238590413a0602be1e4
bound_set_digest: daaba47b1c4b2b31717c098c8d761d9fd2b0cd1eb7e0d55b48d46a4e059f1c3b
job_id: review-mtfrcvnc-vpc9tg
job_class: review
base: 0ed9bf1a
scope: branch
prior_verdict: docs/reviews/phase0-completion-contract/20260830-184827/verdict.md
```

**게이트 판정: 통과 아님.**  findings **2 (medium 2)** — 둘 다 신규 material.
**S-26 ② 카운터 0 유지** (네 회차 연속 needs-attention).

**이 판의 요지: 54차가 «능력 과대서술»을 고치면서 같은 결함을 반대 방향으로 다시 만들었다.**

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 보류. 신규 material (a) 2건이다. 새 문언의 여섯 주장 중 펜스 배제 시 4→1, 펜스 위양성의 (b) 잔여, 펜스 판별 미호출은 확인했지만, HTML 주석 비배제·전 행 스캔·픽스처만 면제라는 핵심 주장은 구현과 반대다. «죽은 검사 2건»은 커밋 기록에서만 확인했고 self-test는 임시 디렉터리 생성 불가로 rc 2여서 독립 재현하지 못했다. 기본 검사와 --report는 rc 0, 67/32/17이었다. 회귀 축은 C2UP·CAP2-FIXTURE·CLOSED-TABLE 각각에서 발견하지 못했다(없음을 증명한 것은 아님).",
  "findings": [
    {
      "severity": "medium",
      "title": "54차 docstring도 실제 CAP-2 배제 범위를 거꾸로 서술한다",
      "body": "문언은 HTML 주석도 배제하지 않고 전 행을 훑으며 면제는 픽스처 행뿐이라고 주장한다. 그러나 `_normalize_scan_text`는 `HTML_COMMENT_RE.sub`로 주석 내용을 제거하고(2358행), `_cap_guard_sites`는 이력 행을 건너뛴다(2457-2459행). 독립 탐침에서도 평문과 fenced guard는 모집단 4→5였지만 같은 guard를 HTML 주석 또는 이력 행에 넣으면 4로 유지됐다. 따라서 #15를 고친 바로 그 문언이 다시 능력을 과대서술한다. 구조 근거로 든 `_fence_spans`/`_enclosing_fence`도 실제 식별자가 아니며, 실제 인터페이스는 `fence_spans`와 `enclosing_fence`다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2438,
      "line_end": 2447,
      "confidence": 1.0
    },
    {
      "severity": "medium",
      "title": "C1의 '기수를 말하는 모든 문장' 주장은 숫자 표기 변경 하나로 우회된다",
      "body": "C1 docstring은 모든 기수 문장을 대조한다고 주장하지만 실제 모집단은 `CARDINALITY_TOKEN_RE = (\\d+)\\s*(개|원소)`뿐이다. 현재 `(4) 대상 ... 아래 9개`를 의미상 틀린 `아래 여덟 항목`으로 바꾼 독립 탐침에서 다른 9원소 문장은 남아 있어 PARSE도 발화하지 않았고 `check_c1` 위반은 0건이었다. 즉 실제 원소는 9개인데 살아 있는 거짓 기수 진술이 green이며, 이는 계약에 등재된 (b) 잔여가 아닌 별도 (a) 능력 과대서술과 우회다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 1084,
      "line_end": 1085,
      "confidence": 0.99
    }
  ],
  "next_steps": [
    "2438-2447행의 CAP-2 범위·면제·실제 식별자 서술을 구현과 일치시킨다.",
    "C1의 전칭 주장을 좁히거나 검출 범위를 넓히고 우회 변이를 회귀 대조군에 추가한다.",
    "쓰기 가능한 환경에서 `--self-test`를 다시 실행해 145종 전건 판별·죽은 검사 0·과잉 차단 0을 독립 확인한다."
  ]
}
```

원문 전체는 `.omc/review/20260830-205952/codex-raw.json`.

---

## 수용검사 (오케스트레이터 = Claude)

**채택 2 · 기각 0 · 팬텀 0.**

### 결속 대조

`plan_scope_digest` 포착 == 재계산 `7ecd7a8e…` · `bound_set_digest` == `daaba47b…`
(결속 문서 무변경 → **O-6 재결속 불요**) · 계약 blob `ecbd478e…` 불변 ·
S-26 ①ⓑ 이력 술어 **공집합** — ⑥ 미발화.

### finding 1 실측 — 세 다리 전부 참이다

| 주장 | 실측 |
|---|---|
| `_normalize_scan_text` 가 HTML 주석을 지운다 | **참** — `:2358` `unicodedata.normalize("NFKC", HTML_COMMENT_RE.sub(" ", text))` |
| `_cap_guard_sites` 가 이력 행을 건너뛴다 | **참** — `:2458` `if doc.is_history_row(lineno): continue` |
| 「면제는 픽스처 행 하나뿐」 | **거짓** — 배제는 **셋**(이력 행 · 픽스처 행 `_scan_chunks` 빈 목록 · HTML 주석 내용) |
| `_fence_spans`/`_enclosing_fence` 가 팬텀인가 | **팬텀 확정** — 저장소 전체에서 **유일한 출현이 내가 쓴 `:2447` 그 줄**이다.  실제는 `ContractDoc.fence_spans`(속성 · `_derive_fence_spans` 가 채운다)와 `ContractDoc.enclosing_fence`(메서드) |

### finding 2 실측

`check_c1` docstring(`:1085`)은 「**모든** 문장」이라는 전칭인데 모집단은
`CARDINALITY_TOKEN_RE = (\d+)\s*(개|원소)`(`:617`) 하나다 — **아라비아 숫자 + 「개」/「원소」**
형태만 잡는다.  한글 수사·다른 단위는 빠진다.  **전칭이 능력보다 넓다.**

### 기각 사유 대조 (두 건 공통)

`file:line` 실재 **확인** · 의도적 silenced **아니다**(같은 파일이 정반대를 구현한다) ·
비협상 규칙 배치 **없음**(배치 0 — 30판 연속) · 범위 밖 부채 **아니다**(finding 1 은 54차가
이 판에서 쓴 문장 · finding 2 는 이번 focus 가 명시 요청한 «전칭 주장» 축의 결과).

### 이 판의 본질 — 수리가 결함을 만들었다

#15 는 「펜스를 훑지 않는다」는 **과대서술**을 냈다.  54차는 그것을 고치면서
「HTML 주석도 배제하지 않는다 · 면제는 픽스처 행 하나뿐」이라는 **또 다른 과대서술**을 썼다.
방향만 반대이고 결함 클래스는 같다.

**더 나쁜 것은 근거였다.**  #15 판정문에서 오케스트레이터는 이 finding 을 「기제의 부재」라는
**구조 근거로 확정했다**고 적었고, 그 근거로 `_fence_spans`/`_enclosing_fence` 미호출을 들었다.
**그 두 이름은 저장소에 없다.**  결론(그 경로에 펜스 판별이 없다)은 참이지만 **근거로 든
식별자는 내가 지어낸 것**이었다 — 「코드펜스」로 grep 해 그 근처 줄을 본 뒤 이름은 기억으로
적었기 때문이다.  이 아크가 이미 성문화한 규율이 정확히 이 자리를 겨눈다:
**결론이 옳아도 근거는 독립 재실측 대상이다.**

### 심판의 수치 하나는 이번에도 승인하지 않는다

심판은 「평문과 fenced guard 는 모집단 **4→5**」라고 적었다.  #15 때 오케스트레이터가 같은
수치를 재현하지 못했고(전부 4→4) 이번에도 재현을 시도하지 않았다.  **finding 1 은 세 다리
모두 소스 실측으로 확정되므로 그 수치 없이도 선다** — 승인하지 않은 채로 둔다.

### S-26 축별 상태

| 축 | 상태 |
|---|---|
| ① 동결 (이력 술어) | 충족 |
| ② 2회 연속 material 0 | **0** — 네 회차 연속 material |
| ③ validator rc 0 | 충족 (`--report` 도 rc 0) |
| ④ CUR/CIT/VER/CARD/RULE 0 | 충족 |
| ⑤ 배터리 독립 검증 | **미검증 — 일곱 회차 연속** |
| ⑥ 리셋 | 미발화 — 카운터 0 은 ②의 실패 |
| ⑧ 도달 가능성 | 열림 (등재) |

### S-26 ② 카운터

**0.**  궤적: … → 1 → 1 → 1 → **2**.  **이 아크에서 처음으로 findings 가 늘었다**(1 → 2).

---

## 오케스트레이터 관측 (판정 아님)

1. **산문 층 재고는 소진되지 않았고, 수리가 재고를 늘리고 있다.**  #13·#14 는 직전 판이
   만든 것, #15 는 44차 유래, **#16 은 직전 판(54차)이 «수리하면서» 만든 것 + 아크 깊숙이
   묵은 것 하나**다.  세 판 연속 「주석 한 자리 수리」가 매번 새 material 을 낳았다.
   이것이 이 아크의 현재 지배적 패턴이다.
2. **근거 층에 규율이 없다.**  처분 문언의 «주장»은 매 회차 심사받지만, 그 주장을 뒷받침한다고
   적은 «식별자·행번호»는 아무도 검사하지 않는다.  이번에 팬텀 식별자가 판정문까지 올라갔다.
   기계로 지을 수 있는 형태다(코드 주석의 백틱 식별자가 실재하는지) — 다음 판의 후보.
3. **⑤ 는 일곱 회차 연속.**

---

## 운영 기록 (정직)

잡 1건 · 완주 4분 22초 · 중복 0 · 매달림 0.  포워더 우회 6회차 연속 무사고.
