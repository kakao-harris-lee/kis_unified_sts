# Phase 0 완료 계약 — 심판 판정 기록 (추적 보존 정본)

이 디렉터리는 `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`
(및 결속 문서 `2026-08-11-tos-completion-development-plan.md`) 심사 아크의
**판정 기록 보존 정본**이다.

## 출처와 보존 근거

- 판정 기록의 운영 홈은 `.omc/review/<timestamp>/` — codex-gate 가 판정을
  **기록하고 재심 체인(직전 스탬프 탐색·`prior_verdict` 해석)을 잇는** 위치다.
  `.omc/` 가 digest 범위 밖인 것은 의도된 설계다(기록 행위가 심사 대상 digest 를
  바꾸면 기록하는 순간 자기 자신을 무효화한다).
- 그러나 `.omc/` 는 `.gitignore` 대상이라 **clean checkout 과 다른 운영자에게
  전달되지 않는다** — 레인 B v2.5 판정 finding #6 (medium, 채택)이 이것을
  "기록 보존 방식의 결함"으로 등재했고, 운영자가 2026-08-13 추적되는 위치
  보존으로 처분했다.
- 이에 따라 아크 전체 기록(레인 B 계획 심판 + 레인 A 코드 심판)의
  **byte-동일 사본**을 이 위치에 커밋한다. 내용 편집 없음.
- **사본이지 이동이 아니다** — 초판 처분은 이동이었으나, 이동이 `.omc/review/`
  의 재심 체인(codex-gate 의 직전 스탬프 탐색과 기존 판정문의 `prior_verdict`
  경로 해석)을 끊는다는 stop-time 심판 지적으로 **운영 원본 유지 + 추적 사본
  보존**으로 교정했다. 두 사본은 byte-동일하며, 검증은:

  ```bash
  diff -r --exclude=README.md .omc/review docs/reviews/phase0-completion-contract
  ```

## 두 위치의 역할

| 위치 | 역할 | 추적 |
|---|---|---|
| `.omc/review/<ts>/` | 운영 체인 — codex-gate 기록·재심 연속성 | gitignore (의도) |
| `docs/reviews/phase0-completion-contract/<ts>/` | **보존 정본 — 문서가 인용하는 추적 경로** | git |

문서·계획의 **활성 포인터는 추적 경로를 인용**한다. 기록은 불변이므로 두 위치가
갈라질 수 없고, 갈라졌다면 그것 자체가 결함이다(위 diff 로 판별).

## 경로 사상 규칙

기록 본문·계획 문서 이력이 인용하는 `.omc/review/<ts>/…` 는 전부

```
.omc/review/<ts>/…  ↔  docs/reviews/phase0-completion-contract/<ts>/…
```

로 상호 해석한다. 판정 파일 내부의 상호 참조(`prior_verdict` 등)는 **역사적
사실이므로 고치지 않는다** — 운영 위치에서는 그대로 해석되고, clean checkout
에서는 이 사상 규칙이 해석을 담당한다.

## 수록 범위 (23건)

- `20260812-055252` … `20260812-231234` — 레인 B 계획 심판 v1.0~v2.3
  (055252 는 판정 불능 fail-closed 기록 — 게이트를 열지 않는 기록도 보존한다)
- `20260813-075200` … `20260813-180752` — 레인 A 코드 심판 (프로토타입,
  게이트 미통과로 종결 — 정본 `20260813-180752/verdict.md`)
- `20260813-205553` — 레인 B v2.5 판정 (`needs-attention`·`NOT_PASSED`,
  findings 6 전건 채택 — v2.6 개정의 입력)
- `20260813-233530` — 레인 B v2.6 재심 (`needs-attention`·`NOT_PASSED`,
  직전 6건 해소 3·부분해소 3·"문구만" 0, 신규 high 3 전건 채택 — 다음 개정의 입력)

## 향후 관행

판정은 종전대로 `.omc/review/` 에 기록되고(digest 범위 밖 기록 원리·재심 체인
유지), **판정 방출 후** byte-동일 사본을 이 디렉터리에 추가해 커밋한다.
사본 추가는 편집을 동반하지 않는다.
