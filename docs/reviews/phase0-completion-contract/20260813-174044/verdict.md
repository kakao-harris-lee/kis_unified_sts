# verdict — 레인 A (코드 심판) · 8회차 · **17회 완주**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED            # 19회 연속
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_scope_digest: 5f2e43fbb8555e955d1adf87d4be5395310c9a549183cff33c16d5009020d976
reviewed_version: v2.9 + 산문 정정 (처분 B · 메타 동결)
findings: 1                        # medium 1
prior_verdict: .omc/review/20260813-164133/verdict.md
mode: A (adversarial-review, --scope working-tree), 약 7분, write=false
method: 정적 독해 한정
lens_scope_reduction: **렌즈 팬아웃 생략 (경량 경로)** — 변경이 산문 2곳뿐, 코드 거동 변경 0
```

리비전 결속: 사전 = 사후 동일. `d8_out.txt` 가 `d7`·`d6`·`d5`·`d4` 와 전부 상이(재사용 아님).

## ⚠ 스트리밍 트랩 재현 (3회차)

stderr 에 **`"verdict":"approve"` 로 시작하는 중간 assistant 메시지가 3회** 캡처됐고
**최종은 `needs-attention`** 이었다. v2.3 판정이 성문화한 그 함정이며, 포워더가 잡아 보고했다.
**중간 preview 를 판정으로 읽으면 게이트가 무너진다.**

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

출하 보류. descriptor·클래스 속성 예외는 정정됐지만, 새 문구가 실제 digest 투영보다 넓은 전칭으로 바뀌어 처분 B는 아직 완결되지 않았다.

Findings:
- [medium] 정의역을 붙였지만 앵커가 실제로 관측하는 투영보다 여전히 넓다 (tools/spikes/phase0_contract/test_contracts.py:3614-3616)
  3614-3616행은 직접 `__code__`를 가진 멤버의 모든 교체와 census 정의역 내 값의 모든 대입을 본다고 주장한다. 그러나 `_code_prose`(411-428)는 `co_name`·`co_code`·`co_names`·문자열/중첩 코드 상수만 묶으므로, 같은 `__code__`와 파일명을 쓰되 globals·defaults·closure가 다른 함수 객체로 교체하면 선언된 정의역 안에서도 앵커가 불변일 수 있다. 또한 `policy_value_text`(644-657)는 tuple/list와 set/frozenset을 각각 동일하게 정규화하고 `_is_policy_value`(687-716)는 네 타입을 모두 허용하므로, census 안의 타입 교체가 이름과 digest를 모두 보존할 수 있다. 따라서 직상단 정의역 문장은 `config.yaml:161-163`과 `policy_value_targets`의 790-793행을 참으로 만들지 못하며, 같은 과대주장이 `L-POLICY-ANCHOR` 3515-3517행에도 남는다.
  Recommendation: 새 검사층 없이 모든 정본 문구를 실제 투영으로 한정하라. 실행 코드 앵커는 '수집된 코드 투영이 바뀌는 교체', 정책값 앵커는 'target 이름 집합 또는 `policy_digest`가 바뀌는 대입'만 관측한다고 쓰고, 함수 globals/defaults/closure와 정규화상 동치인 컨테이너 타입 교체는 보장 밖임을 명시하라.

Next steps:
- `test_contracts.py:790-793,3515-3517,3614-3616`과 `proto/config.yaml:146-163`을 동일한 투영 한정 문구로 정정한다. 수집기나 대조군 확장은 필요하지 않다.
```

## 수용검사 — 채택 1 / 기각 0

오케스트레이터 독립 실측:
```
_code_prose: co_name · co_code.hex() · co_names · 문자열/중첩 consts
             → globals · defaults · closure 미포함 (확증)
policy_value_text: (tuple, list) 동일 join · (frozenset, set) 동일 sorted join
POLICY_VALUE_TYPES = (str, bytes, tuple, frozenset, set, list, dict) — 네 타입 전부 (확증)
```
비협상 규칙 8조항 — **위반 0**. 심판이 "수집기나 대조군 확장은 필요하지 않다"고 명시.

**심판이 저작자의 자체 판정을 뒤집었다**: 직전 라운드에 저작자가 "같은 클래스에 들지 않는다"고
판단해 손대지 않은 `config.yaml:161-163`·`test_contracts.py:790-793` 은 **같은 클래스가 맞다.**
직상단 정의역 문장이 그것들을 참으로 만들지 못한다.

## 후속 처분 (같은 스탬프 내)

심판 지목 4곳 + **저작자 전수 스윕이 찾은 4곳**을 정정했다. 원칙을 바꿨다 —
앵커를 "어떤 뮤테이션 부류를 잡는가"가 아니라 **"자기 투영이 무엇인가"로만** 서술한다.
`ast.stmt` Δ0, 대조군 39 유지, 수집기 무변경.

## 게이트

```
현재 = codex AND needs-attention AND 일치      → 불성립 (19회 연속)
```
