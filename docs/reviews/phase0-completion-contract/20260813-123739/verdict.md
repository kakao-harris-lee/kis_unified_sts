# verdict — 레인 A (코드 심판) · v2.7 재심 · **14회 완주**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED            # 16회 연속
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_scope_digest: 4b3fcd41bc1e53b417086d82b4cf1ee2a8ec2ef49f4c1e39c60d21120a84e5a1
reviewed_version: v2.7 (F1·F3 교정분)
findings: 6                        # critical 1 / high 3 / medium 2
prior_verdict: .omc/review/20260813-094300/verdict.md
mode: A (adversarial-review, --scope working-tree), 약 7분, write=false
method: **정적 독해 한정** (렌즈가 동적 재현을 담당 — 상보 설계)
lens_evidence: .omc/review/20260813-123739/evidence/ (security · architecture)
```

리비전 결속: 디스패치 직전 = 심사 종료 후 **동일**. 드리프트 0.
오염 방지: 4회차 verdict·`ld_out`·`d2_out`·`d4_out` 전부와 **해시 상이**, `Turn failed` 0건.

## 방법 설계 — 이번 라운드의 상보 구조

Codex 는 4회차부터 **정적 독해 한정**이다(동적 프로브가 콘텐츠 정책 분류기를 발화시킴).
그 방법 한계를 보완하기 위해 이번 라운드는 **렌즈가 동적 재현을 담당**했다 —
security·architecture 렌즈가 20+ 뮤테이션을 실행하고, Codex 가 그 주장을 코드 독해로 심판했다.
**렌즈는 같은 모델 계열이라 독립 심판이 아니다**; 독립성은 Codex 의 판정에만 있다.

## 처분

**직전 7건**: #1 부분해소 / #2 **부분해소·표면 이동** / #3 부분해소 / #4·#5 **해소** /
#6 **정책 축소로 해소** / #7 부분해소. **회피 0** (두 렌즈 독립 확인).

38 개 대조군 중 **도메인 계약은 23 개로 그대로**이고 신규 6 개는 **전부 메타 검사**다.
검사력은 늘었으나 검사 대상도 커졌고, **가장 심각한 결함들이 새 메타 계층에서 다시 발생했다.**
21 개 한계 노트도 실제 잔여보다 좁다.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

Ship 불가. 직전 7건은 #1 부분해소, #2 부분해소·표면 이동, #3 부분해소, #4·#5 해소, #6 정책 축소로 해소, #7 부분해소다. 렌즈의 exit_status CRITICAL, import 바인딩·probe_window·pre-hook HIGH 지적은 코드상 성립한다. 38개 대조군 중 도메인 계약은 23개로 그대로이고 신규 6개는 모두 메타 검사다. 검사력은 늘었지만 검사 대상도 커졌고, 가장 심각한 결함들이 새 메타 계층에서 다시 발생했다. 21개 한계 노트도 exit 종단 신뢰, probe 기록의 exit 이탈, 미앵커 정책값 등을 빠뜨려 실제 잔여보다 좁다.

Findings:
- [critical] 최종 종료 판정이 같은 프로세스의 단일 교체 가능 함수에 귀결된다 (tools/spikes/phase0_contract/test_contracts.py:748-758)
  `main()`의 유일한 반환은 `exit_status()`이고, SELF-3의 채널 반전 검사도 같은 전역 함수를 호출한다. 따라서 이 이름이 0을 반환하도록 재바인딩되면 red Case, 운영 위반, 앵커 드리프트가 모두 탐지·출력되어도 최종 상태는 0이다. `exit_wiring()`은 소스의 명목상 함수명만 확인하므로 이를 방어하지 못한다. 저장소에는 seeded-red 실행의 비영 종료를 독립 검증하는 외부 소비자도 없다. 이는 직전 #2 결함이 교정 함수로 이동한 것이다. 임의의 same-process 변조를 위협 모델에 포함하는 한 더 많은 내부 자기검사로는 최종 신뢰점을 원리적으로 보호할 수 없다.
  Recommendation: 리비전에 결속된 외부 CI/래퍼가 별도 프로세스에서 알려진 red 조건을 주입하고 비영 종료를 직접 검증하게 하라. 외부 검증이 범위 밖이면 `L-EXIT-ROOT` 구조적 한계로 명시하고, 이 프로토타입이 최종 exit 자체까지 자기증명한다는 주장은 제거하라.
- [high] import로 복사한 설정 함수가 실행코드 앵커 정의역에서 빠진다 (tools/spikes/phase0_contract/test_contracts.py:368-392)
  러너는 `load_config`와 `cfg_pairs` 등을 직접 바인딩하지만, 실행코드 앵커는 객체의 `__module__` 자기신고가 현재 모듈명과 같은 경우만 포함한다. 러너의 바인딩을 `__module__='proto.config'`인 함수로 바꾸면 교체 객체는 러너 앵커에서 제외되고 원본은 `proto.config`에 그대로 남는다. 실제 소비 지점은 교체된 바인딩을 사용하므로 앵커 기대값과 T-79 선언값을 라이브 값으로 위조해 변경된 소스·정책을 green으로 만들 수 있다. 이는 #1의 `digest_drift`가 실제 비교 producer를 거치지 않는 잔여와 #7의 값 앵커를 함께 무력화한다.
  Recommendation: 소비되는 모든 모듈 바인딩을 소속 자기신고와 무관하게 이름·코드 파일·코드 digest로 결속하라. 설정 접근은 모듈 한정 호출로 정규화하고, 앵커 기대값을 읽는 경로 자체를 외부 또는 독립 앵커가 검증하게 하라.
- [high] 전역 probe_window가 실제 위반을 exit 비결속 버킷으로 재분류한다 (tools/spikes/phase0_contract/audit_guard.py:248-252)
  `_record()`는 프로세스 전역 `_PROBE_DEPTH`가 양수이면 모든 스레드의 기록을 `probe_reads/probe_writes`로 보낸다. 종료 게이트는 `blocked_reads/blocked_writes`만 소비한다. 러너 자체도 probe 창 안에서 워커 스레드를 실행하므로 그 시간에 발생한 다른 위반은 차단되더라도 종료 상태에서 사라진다. 공개 `probe_window()`를 호출한 코드가 예외를 삼키는 경우에도 같은 우회가 가능하다. 따라서 보안 N-1과 아키텍처 N-3은 모두 성립하며, 한계 노트의 '분류만 이동한다'는 설명은 v2.7에서 거짓이다.
  Recommendation: probe 상태를 thread-local로 옮기고 고정된 호출 지점에 발급된 capability/token과 일치하는 기록만 프로브로 분류하라. 나머지는 모두 운영 버킷에 유지하고, 허용된 probe 기록의 identity와 개수도 종료 게이트에 결속하라.
- [high] pre-hook 검사가 실행 가능한 대입과 문자열 기반 동적 import를 동시에 놓친다 (tools/spikes/phase0_contract/test_contracts.py:608-682)
  `_INERT_STATEMENTS`는 RHS와 무관하게 모든 Assign/AnnAssign을 비실행문으로 분류하고, 동적 로드 검사는 Name과 Attribute만 본다. 따라서 `_SNEAK = __builtins__['__import__']('proto.register')` 같은 대입은 실행문 계수와 금지 이름 검사 모두에 잡히지 않는다. 이를 `_ARMED_SNAPSHOT` 뒤와 hook 설치 앞에 두면 스냅샷도 이미 지나간다. 남는 검출기는 함께 갱신 가능한 pre-hook digest뿐이므로 '#3의 동적 로드 fail-closed·실행문 0' 주장은 실제 코드보다 넓다.
  Recommendation: 대입 RHS에 Call, Await, comprehension 등 실행 노드가 있으면 실행문으로 분류하고 Constant/Subscript 기반 호출 이름도 검사하라. 더 강한 경계가 필요하면 피검사 모듈보다 먼저 뜨는 최소 외부 bootstrap에서 hook을 설치하라.
- [medium] 정책값 전수 앵커와 잔여 목록이 실제 판정 우주보다 좁다 (tools/spikes/phase0_contract/proto/boundary.py:240-241)
  `_NULLARY_STR_METHODS`는 `_const_call()`이 런타임에 사용하는 AST 폴딩 정책값이지만 `policy_value_targets()`에도 `L-POLICY-ANCHOR`의 예외 목록에도 없다. 런타임에서 이 값을 축소하면 소스 바이트와 실행코드는 그대로이고 T-79도 움직이지 않아 AST 스캔 범위가 조용히 줄어든다. 이는 '#7 전수 결속'과 '표 밖 이름 전부 열거'라는 주장의 직접 반례다.
  Recommendation: 정책값을 수동 양성 목록으로 관리하지 말고 모듈 구조에서 자동 파생한 뒤 의도적 제외만 설정에 선언하라. 최소한 `_NULLARY_STR_METHODS`와 `_INERT_STATEMENTS`를 값 앵커에 추가하고 잔여 목록을 다시 전수 대조하라.
- [medium] 쓰기 음성 대조군이 실패 시 저장소에 실물을 남긴다 (tools/spikes/phase0_contract/test_contracts.py:1613-1617)
  감사 전용 쓰기 프로브는 저장소 내부의 실제 writable 경로를 `w` 모드로 열고 디렉터리를 만든다. `_WATCHED`나 쓰기 이벤트 집합이 깨지는 바로 그 음성 시나리오에서는 파일과 디렉터리가 생성되며, 코드는 잔존물을 보고할 뿐 정리하지 않는다. 이후 실행은 이 잔존물 때문에 지속적으로 red가 되어 다른 미검출 변형을 가릴 수 있다. 자기검사가 검사 대상 작업 트리를 오염시키는 복구·관측성 결함이다.
  Recommendation: 프로브를 격리된 외부 임시 디렉터리나 성공 자체가 불가능한 부재 부모 경로로 옮기고, 실패 여부와 무관하게 저장소 내부에는 어떤 실물도 생성될 수 없게 하라.

Next steps:
- same-process 변조의 신뢰 경계를 확정하고 외부 negative-control 검증자를 먼저 추가한다.
- probe 분류와 pre-hook 분석을 교정한 뒤 직전 7건의 처분을 다시 재심한다.
- 정책값·한계 노트를 자동 census로 대조하고 누락 잔여를 명시한다.
- 쓰기 프로브를 저장소 밖으로 이동한 후에만 전체 뮤테이션 증거를 다시 생성한다.
```

*렌더러가 `confidence` 필드를 출력하지 않아 stdout·stderr 어디에도 없다. 그 외 전 필드 원문.*

---

# 수용검사 (오케스트레이터) — **채택 6 / 기각 0**

기각 사유 3 가지 중 어느 것도 해당하지 않는다. 6 건 전부 직접 실측했다.

| # | sev | `file:line` | 실측 | 처분 |
|---|---|---|---|---|
| 1 | critical | `test_contracts.py:748-758` | `:3116` 단일 반환 · SELF-3 red 도 같은 함수 경유 | 채택 |
| 2 | high | `test_contracts.py:368-392` | `:379 getattr(obj,"__module__",None) != name` — 자기신고 | 채택 |
| 3 | high | `audit_guard.py:248-252` | 게이트가 `blocked_*` 만 소비 · `probe_reads` config 언급 **0** | 채택 |
| 4 | high | `test_contracts.py:608-682` | `_INERT_STATEMENTS = (Import, ImportFrom, **Assign, AnnAssign**, …)` RHS 무관 | 채택 |
| 5 | medium | `boundary.py:240-241` | `_NULLARY_STR_METHODS` 가 `_const_call:289` 에서 소비되는데 config **0회** | 채택 |
| 6 | medium | `test_contracts.py:1613-1617` | `_HERE / "__audit_probe_w.tmp"` — **repo 내부** | 채택 |

## 비협상 규칙 대조 — 위반 0

8 조항 전건 대조. 6 건 모두 강제 강화 방향. 다만 #5 이행 시 **값 앵커는 `config.yaml`** 에.

## 관통 패턴 — 15 번째, 그리고 **천장의 발견**

| 층 | 형태 |
|---|---|
| v1.3.8~v2.1 | 문서 안 선언↔평가 간극 (10 회) |
| v2.2~v2.3 | 증거 도구, 그리고 그 교정으로 전이 |
| v2.5 | 교정의 **잔여 목록**으로 전이 |
| v2.6 | **가드 기록 채널**로 전이 |
| **v2.7** | **교정이 만든 통합 지점(`exit_status`)으로 전이** |

v2.7 이 이전 판들과 다른 점은, 심판이 **이것이 반복이 아니라 천장임을 진단**했다는 것이다:

> 임의의 same-process 변조를 위협 모델에 포함하는 한 **더 많은 내부 자기검사로는 최종 신뢰점을
> 원리적으로 보호할 수 없다.**

즉 지금까지의 대응(= 새 층을 하나 더 쌓기)은 이 항목에 대해 **원리적으로 종료하지 않는다.**
심판이 제시한 처분은 둘뿐이다:

1. **외부 검증자** — 리비전에 결속된 CI/래퍼가 **별도 프로세스**에서 seeded-red 를 주입하고
   비영 종료를 직접 검증
2. **한계 등재 + 주장 철회** — `L-EXIT-ROOT` 로 구조적 한계를 명시하고,
   **"이 프로토타입이 최종 exit 자체까지 자기증명한다"는 주장을 제거**

이 선택은 저작자 재량이 아니라 **Phase 0 완료 계약의 범위 결정**이다 — 오케스트레이터가
운영자에게 올린다.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립 (16회 연속)
```

**P-0 및 모든 D0 구현 착수 차단 유지.**
