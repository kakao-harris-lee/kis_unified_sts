# verdict — 레인 A (코드 심판) · v2.9 재심 · **16회 완주**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED            # 18회 연속
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_scope_digest: 41cd6f89a42a02731b3881d86bcc7943c14b9071b078cdf5c03c39a938472efb
reviewed_version: v2.9 + 후속 산문 정정 (운영자 처분 B · 메타 하네스 동결)
findings: 1                        # medium 1  (critical 0 / high 0)
prior_verdict: .omc/review/20260813-141625/verdict.md
mode: A (adversarial-review, --scope working-tree), 약 8분, write=false
method: 정적 독해 한정 (렌즈가 동적 재현 담당)
lens_evidence: .omc/review/20260813-164133/evidence/ (security · architecture)
```

리비전 결속: 디스패치 직전 = 심사 종료 후 **동일**. `d7_out.txt` 가 `d6`·`d5`·`d4` 와 전부 상이(재사용 아님).
Codex 가 **`CLAUDE.md` 를 최초 명령으로 열람** — 6회차 포워더가 지적한 우연 의존을 focus 에 명시해 해소.

## 추세

| 라운드 | 대상 | findings |
|---|---|---|
| 4회차 | v2.6 | 4 (critical 1 / high 3) |
| 5회차 | v2.7 | 6 (critical 1 / high 3 / medium 2) |
| 6회차 | v2.8 | 5 (high 3 / medium 2) |
| **7회차** | **v2.9** | **1 (medium 1)** — critical 0 · high 0 |

## 심판이 확인한 것

- 직전 5 건의 **등재·`SELF-3` 교정 정적 확인**
- 렌즈 이후 저작자가 한 **4 개 문구 정정 확인**
- **메타 하네스 동결 확인**
- **R-1 처분이 옳다**: "`Case.ok` 의 특별한 위험까지 명시했으므로 **운영자 처분 B 아래에서는
  수집기 확장보다 등재가 맞다**" — 오케스트레이터의 판단(수집기를 넓히지 않고 등재)이 승인됐다
- **동결 유지**: "`Case.ok` 수집기 확장은 운영자가 동결을 별도로 변경하지 않는 한 이번 처분의
  필수 조건으로 삼지 않는다"

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

출하 보류. 직전 5건의 등재·SELF-3 교정, 렌즈 이후 4개 문구 정정, 메타 하네스 동결은 정적으로 확인된다. R-1도 `Case.ok`의 특별한 위험까지 명시했으므로 운영자 처분 B 아래에서는 수집기 확장보다 등재가 맞다. 다만 같은 노트가 곧바로 런타임 대입 전반이 앵커에 잡힌다고 다시 일반화해, 이번 라운드의 핵심인 정직한 주장 철회가 아직 일관되지 않다.

Findings:
- [medium] R-1을 등재한 직후 런타임 대입 전칭을 다시 주장한다 (tools/spikes/phase0_contract/test_contracts.py:3598-3614)
  3598-3611행은 descriptor 6건이 실행코드 앵커 밖이고, 특히 `Case.ok` 교체가 37/39를 39/39로 바꿔도 그 앵커가 불변임을 정확히 적는다. 그런데 3613-3614행은 디스크를 건드리지 않는 런타임 대입을 실행코드·정책값 앵커가 본다고 다시 일반화한다. `Case.ok` 교체는 바로 그 런타임 대입이지만 직접 `__code__`도 없고 정책 census 대상도 아니므로 두 앵커 모두 침묵한다. `proto/config.yaml:145-152`에도 같은 일반화가 남아 있다. 등재가 유일한 처분인 이번 판에서 정본 설명이 서로 충돌하면 운영자 처분 B의 주장 철회가 완결되지 않는다.
  Recommendation: 두 위치의 일반화를 각각 '직접 `__code__`를 가진 멤버'와 '정책 census 정의역에 든 값'으로 한정하고 descriptor·클래스 속성 예외를 명시하라. 새 검사층이나 수집기 확장은 요구하지 않는다.

Next steps:
- `test_contracts.py`와 `proto/config.yaml`의 런타임 대입 설명만 실제 두 앵커의 정의역으로 축소하고, 영향을 받는 기존 산문·소스 앵커 값을 갱신한다.
- 메타 하네스 동결은 유지한다. `Case.ok` 수집기 확장은 운영자가 동결을 별도로 변경하지 않는 한 이번 처분의 필수 조건으로 삼지 않는다.
```

*인라인 실행이라 job 레코드가 없어 `result --json` 재회수는 불가하다. 위 블록이 stdout 전문이며
`verdict`/`summary`/`findings[]`/`next_steps[]` 전 필드가 렌더에 실려 있다. `confidence` 는 이 표면에 미노출.*

---

# 수용검사 (오케스트레이터) — **채택 1 / 기각 0**

| sev | `file:line` | 실측 | 처분 |
|---|---|---|---|
| medium | `test_contracts.py:3612-3614` · `proto/config.yaml:145-146` | 두 곳 모두 **정의역 없는 전칭** 실재 확인. `L-SRC-ANCHOR` 가 descriptor 6건을 등재한 **3 줄 뒤**에 "런타임 대입은 실행 코드 앵커와 정책값 앵커가 본다"로 되돌린다 | 채택 |

비협상 규칙 대조 8 조항 — **위반 0**. 산문 정정 권고이며 새 층·수집기 확장을 요구하지 않는다.

## 렌즈 결과 (참고 — 독립 심판 아님)

두 렌즈가 **등재 5 종 전부 "정확"**(축소서술 0)으로 판정했고 동결 준수를 수치로 확인했다
(대조군 39 불변 · **도메인 계약 23 불변** · 신규 Case/앵커종류/검사계층/모듈상수 각 0 ·
`ast.stmt` +18 전부 기존 함수 본문 내부). 아키텍처 렌즈 기록:
**"6 라운드 연속 실제보다 넓던 서술이 이번엔 일치하거나 좁은 쪽이었다."**

렌즈가 찾은 잔여 과대주장 4 건(OC-1 HIGH · OC-2 MEDIUM · OC-3 LOW · R-1)은 **렌즈 증거 생성
이후 저작자가 정정**했고, 그 사실을 focus text 에 공개해 심판이 정정 후 상태를 심사했다.

## 이 라운드의 의미

**처음으로 critical·high 가 0 이 됐다.** 그리고 남은 1 건은 새 결함이 아니라 **정직한 등재가
아직 일관되지 않다**는 지적이다 — 3 줄 위에서 정확히 적은 것을 3 줄 뒤에서 되돌렸다.

이것은 v2.4 가 받은 지적("본문 15 곳 stale")과 같은 클래스이며, **부분 정정은 정정이 아니다**를
다시 확인한다. 다만 규모가 2 곳으로 줄었고 방향이 옳다.

## 후속 처분 (같은 스탬프 내)

지적된 2 곳을 **산문만** 정정했다(수집기 무변경 — 심판 지시). `ast.stmt` Δ0, 대조군 39 유지,
앵커 4 종 재기입, 정상 exit 0.

저작자가 **판정 클래스에 들지 않는다고 스스로 판단한 2 곳**(`config.yaml:161`,
`test_contracts.py:793` — 같은 블록/직상단에 정의역 문장이 붙어 있음)을 **다음 후보로 공개**했다.
8 회차 focus 에 그대로 실어 심판이 판단하게 한다.

**절차 사고 1건 (저작자 자진 보고)**: 뮤테이션 복원에 쓴 `cp` 가 interactive alias 라 복원이 조용히
실패해 변형 A 가 B/C 로 샜다. `shutil.copyfile` 로 바꿔 **전건 재실행**했다. 측정 오류가 결과를
오염시킬 뻔한 사례이며, 자진 보고가 없었으면 회귀 3 종이 거짓으로 통과했을 것이다.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립 (18회 연속)
```

**P-0 및 모든 D0 구현 착수 차단 유지.**
