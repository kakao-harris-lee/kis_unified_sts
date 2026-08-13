# verdict — 레인 A (코드 심판) · 9회차 · **18회 완주** · **코드 레인 종결 기록**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED            # 20회 연속 — 종결 시점 상태
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_scope_digest: 185cc8b6cb57a6762f38d1787439bb4ab189f88932427286134c78b304304aa5
reviewed_version: v2.9 + 투영 정정
findings: 3                        # medium 3
prior_verdict: .omc/review/20260813-174044/verdict.md
mode: A (adversarial-review, --scope working-tree), write=false
method: 정적 독해 한정
lens_scope_reduction: 렌즈 팬아웃 생략 (경량 경로)
closure: **운영자 결정 — 3건 등재 후 문서 트랙 전환. 코드 레인은 여기서 닫는다.**
post_verdict_versions: v2.10 (3건 등재) · v2.11 (⒝·⒞ 접힘 등재)
```

리비전 결속: 사전 = 사후 동일. 산출물 `37f16fa1…` 가 `d8`·`d7` 과 상이.
**스트리밍 트랩 4회차**: 중간 `approve` preview 1회 → 최종 `needs-attention`.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

No-ship: 직전 finding의 핵심 예시는 등재됐지만, 실제 관측 스칼라보다 넓은 투영 주장과 자기신고 기반 바인딩 설명이 남아 있어 처분 B는 아직 완결되지 않았다.

Findings:
- [medium] 투영 설명이 비경계 직렬화의 손실을 누락한다 (tools/spikes/phase0_contract/proto/config.yaml:146-153)
  이 문구는 실행 코드의 필드 투영이 바뀌면 관측된다고 하지만 `_code_prose()` 결과는 `loaded_code_text()`에서 태그나 길이 없이 `\x1f`로 결합된다. 따라서 문자열 상수가 `("a\x1fb",)`에서 `("a","b")`로 바뀌면 열거된 `co_consts` 투영은 달라져도 직렬화 결과와 digest는 같다. 정책값도 `policy_value_text(("a","b"))`와 `policy_value_text(("a\x00b",))`가 동일해, 등재된 tuple↔list·set↔frozenset 외에도 항목 수·내용·중첩 구조가 다른 값이 같은 digest로 접힌다. 즉 투영-프레이밍은 실제 최종 직렬화/digest까지 내려갈 때만 종결적이며, 현재 보장 밖 목록은 불완전하다.
  Recommendation: 검사층을 추가하지 말고, 실행 코드 보장을 `loaded_code_text` 또는 최종 digest가 바뀌는 경우로 축소하라. 정책값 한계에는 NUL 구분자·중첩 평탄화·항목 경계가 만드는 정규화 동치도 명시하고 L-SRC-ANCHOR/L-POLICY-ANCHOR 문구를 함께 맞춰라.
- [medium] module binding은 여전히 자기신고 메타데이터를 실제 출처라고 부른다 (tools/spikes/phase0_contract/test_contracts.py:497-537)
  `module_binding_identities()`가 파생하는 import 이름은 현재 모두 모듈 객체이고, `_binding_origin()`의 모듈 분기는 `binding_file()`로 간다. 그런데 그 분기는 라이브 객체의 가변 `__file__`을 그대로 사용한다. 함수 분기의 `co_filename`도 컴파일 시 제공되는 라벨이지 검증된 파일 provenance가 아니다. 따라서 528-534행의 '코드가 실제로 온 파일', '자기신고가 아닌 결속'은 구현보다 넓다. 같은 코드 투영과 위조한 파일 라벨을 제시하는 모듈/함수 교체는 설명상 거부되는 것처럼 보이지만 실제 identity는 보존될 수 있다.
  Recommendation: `실제 출처`와 `자기신고 제거` 주장을 철회하고 관측값을 `basename(__file__)` 또는 `basename(co_filename)` 메타데이터 라벨과 코드 digest로 정확히 서술하라. 모듈 `__file__` 및 임의 `co_filename`이 보장 밖임을 정본 설명과 L-SRC-ANCHOR에 반영하라.
- [medium] 리터럴 앵커에 대한 기존 전칭이 두 곳에 남아 있다 (tools/spikes/phase0_contract/proto/config.yaml:96-100)
  이 주석은 digest가 `limit()` 호출의 문자열 리터럴 조각만 모은다고 정확히 밝힌 직후, 일반적인 '산문을 고치면' 이 값도 고쳐야 한다고 다시 전칭한다. f-string 삽입 표현이나 삽입값만 바꾸면 방출 산문은 달라져도 `limit_text_anchor()`의 리터럴 조각은 불변이며, 바로 아래 103-105행도 그 우회를 인정한다. 동일한 과대주장이 `limit_text_anchor()` docstring의 365-367행에도 남아 있다. 자체 발견한 3576-3578행 정정만으로 전수 스윕은 끝나지 않았다.
  Recommendation: 100행과 `limit_text_anchor()` docstring을 모두 '문자열 리터럴 조각이 바뀌면 digest가 바뀐다'로 축소하고, 삽입부는 방출 앵커의 투영임을 명시하라.

Next steps:
- 위 문구들을 실제 최종 투영으로 축소한 뒤 정적 재심을 요청하라.
```

## 수용검사 — 채택 3 / 기각 0

오케스트레이터 독립 실측 (전건 확증):
```
#1 ("a\x1fb",) → 'a\x1fb'  ·  ("a","b") → 'a\x1fb'   충돌: True
#2 _binding_origin: basename(co_filename) / basename(__file__) — 둘 다 라벨
#3 config.yaml:100 · test_contracts.py:367 전칭 실재
```
비협상 규칙 8조항 — **위반 0**.

---

# 코드 레인 종결 기록 (운영자 결정)

## 결정

9회차 판정을 받은 시점에 오케스트레이터가 추세를 올렸다 — severity 는 3라운드 연속
critical 0 · high 0 이나 **건수는 단조 감소가 아니고**(1 → 1 → 3), 남은 것은 전부
"산문이 기제보다 아주 조금 넓다"이며 매 라운드 더 미세한 층에서 나온다.

**운영자 결정: "지금 멈추고 3건 등재 후 C(문서 트랙)로."**

## 종결 후 처분 (v2.10 · v2.11)

| 판 | 내용 |
|---|---|
| **v2.10** | 심판 9회차 3건 **등재**. ①투영-프레이밍을 **최종 직렬화/digest** 기준으로 축소 + 보장 밖 5갈래(닫힌 열거 아님 명시) ②**자기신고 주장 철회** — v2.8 이 없앤 것은 `__module__` 이지 **파일 라벨이 아니다**, 라벨은 위조 가능 ③리터럴 앵커 전칭 2곳 축소. 저작자 전수 스윕이 같은 클래스 3곳 추가 적발·수리 |
| **v2.11** | 저작자가 **자체 판정하지 않고 올린** 항목을 오케스트레이터가 실측 확인 후 등재 — `emitted_text_anchor` docstring 의 "값이 실제로 바뀌면 red" 가 **거짓**. ⒝·⒞ 도 같은 구분자 접힘 클래스이며, **⒜ 가 가장 약하고**(빈 문자열 join → `('a','b')` ↔ `('ab',)` 충돌, 오케스트레이터 재현), ⒠ 는 성질은 같으나 NUL 제약으로 **도달 불가** |

**정확한 최종 서술**: `rep.anchors` 5종(⒜⒝⒞⒟⒠)과 ⒡가 **전부 같은 구분자 접힘 클래스**이고,
⒜가 가장 강한 형태이며 ⒠만 대상 제약으로 도달 불가다.

## 종결 시점 상태

```
정상 실행: exit 0 · 대조군 39/39 · 앵커 드리프트 0 · 운영 경계 위반 0
등재 한계: 23건 (L-EXIT-ROOT · L-CONFIG-TRUSTPOINT · L-SRC-ANCHOR · L-POLICY-ANCHOR ·
           L-AUDIT-* · L-INODE-ALIAS · L-CASEFOLD · L-LOCATE-FORGE · L-SELF-VISIBILITY 외)
이연 등재: L-EXIT-ROOT = Phase 1 (외부 CI 검증자 — 운영자 처분 A)
동결: 메타 하네스 확장 중단. 도메인 계약 대조군 23건 불변
게이트: NOT_PASSED (20회 연속)
```

## 미해결로 남기는 것 — 저작자가 자체 판정하지 않고 올린 3건

**오케스트레이터 판정: 셋 다 명백한 in-domain 거짓이 아니므로 등재하지 않고 여기 기록한다.**
다음 라운드가 열리면 첫 후보다.

1. `test_contracts.py:2970` `L-UNCHK019-CANARY` — "그 사실이 바뀌면 red 가 되어 재검토를
   강제한다". 기제가 count canary + 양방향 Case 라 직렬화 접힘과 **다른 클래스**로 보이나
   전칭의 형태는 같다.
2. `test_contracts.py:3682` — "산문을 고쳐도 red 가 **되어야 한다**". 사실 서술이 아니라
   **당위**라 판정이 갈린다.
3. `test_contracts.py:683` · `config.yaml:179` — "목록에서 파일을 빼는 것 자체가 값을 바꾼다".
   저작자 실측이 함수 수준에서 이를 반증하나(`0e2378ef8aad6b9b`), **실제 정의역(임포트 가능한
   `.py`)에서는 NUL 제약으로 도달 불가**하므로 in-domain 으로는 참이다.

## 이 레인이 남긴 것

9회 심사 · 18회 완주 · **게이트 미통과**. 그러나 종결 상태는 "무엇이 검사되고 무엇이 검사되지
않는지가 **기계로 고정되고 산문으로 정확히 적힌**" 프로토타입이다.

핵심 교훈(누적): **막은 옆에 인접 우회로가 남는다**가 증거 도구 → 도구의 교정 → 교정의
잔여 목록 → 가드 기록 채널 → 통합 지점(`exit_status`) → 앵커 직렬화로 **6단계 전이**했다.
심판이 v2.7 에서 그 회귀가 **종료하지 않음**을 진단했고(같은 프로세스 안에서 최종 신뢰점은
자기 절단을 검출할 수 없다), 운영자가 처분 B(등재 + 주장 철회)와 메타 동결로 닫았다.

**자기검증과 독립심사의 차이가 이 세션에서 실증됐다** — stop-hook 5라운드는 매번 저작자가
방금 만진 표면만 짚었고, 렌즈 병렬 + 독립 뮤테이션은 저작자가 한 번도 보지 않은 표면을 짚었다.
그리고 **저작자의 자기보고는 6라운드 연속 실제보다 넓었다.**

**P-0 및 모든 D0 구현 착수 차단 유지.**
