# verdict — 레인 A (코드 심판) · v2.8 재심 · **15회 완주**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED            # 17회 연속
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_scope_digest: d621f54888eeefe1c4d58045c60b58ce5f9b25da793d53b321a22062a8a8dfd6
reviewed_version: v2.8 (F1·F3 교정분 · 운영자 처분 B 반영)
findings: 5                        # high 3 / medium 2
prior_verdict: .omc/review/20260813-123739/verdict.md
mode: A (adversarial-review, --scope working-tree), 약 8분, write=false
method: 정적 독해 한정 (렌즈가 동적 재현 담당 — 상보 설계)
lens_evidence: .omc/review/20260813-141625/evidence/ (security · architecture)
```

리비전 결속: 디스패치 직전 = 심사 종료 후 **동일**. `d6_out.txt` ≠ `d5_out.txt` (재사용 아님 확인).
`Turn failed`·정책 거부 0. 대상 확인: `test_contracts.py` **3637행**(v2.8 확정).

## 처분

**직전 6건**: #1 **정직등재**(운영자 처분 B) / #2 **부분해소·표면 이동** / #3·#4 **부분해소** /
#5 기존 반례 해소 / #6 **해소**. **회피 0.**

**두 렌즈가 갈렸던 #3·#4 를 심판이 해소했다 — security 가 양쪽 다 옳았다.**
probe 사칭과 ClassDef pre-hook 주장이 **코드상 성립**한다. architecture 는 두 형태를 시험하지 않았다.

**최종-exit 자기증명 주장은 철회됐으나 국소 과대주장이 남았다**:
설정의 77 앵커·7 제외 수치는 맞지만 **"잔여 27 전수"는 클래스 누락 때문에 거짓**이다.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

출하 불가. 직전 처분은 #1 정직등재, #2 부분해소·표면이동, #3·#4 부분해소, #5의 기존 반례와 #6 해소다. security의 probe 사칭과 ClassDef pre-hook 주장이 코드상 성립한다. 최종-exit 자기증명 주장은 철회됐지만 국소 과대주장은 남았다. 설정의 77개 앵커·7개 제외 수치는 맞지만 '잔여 27개 전수'는 클래스 누락 때문에 거짓이다. 현행 waiver 3개는 정당한 등재로 보이나 이유 자체는 검사하지 않는다. +517행과 신규 메타 Case 1건에 비해 도메인 계약은 23건 그대로이므로, 실질 보강도 있었지만 변화의 중심은 검사력보다 자기검사 대상 확대다.

Findings:
- [high] T-80의 두 판독기가 동일한 CONFIG_PATH 신뢰점을 공유한다 (tools/spikes/phase0_contract/test_contracts.py:3241-3250)
  주 판독기와 독립 판독기 모두 `config.CONFIG_PATH`를 사용한다. 따라서 이 이름을 외부 위조 파일로 한 번 재바인딩하면 두 판독기가 동시에 같은 위조 앵커를 받아들인다. `CONFIG_PATH`는 정책값 앵커 대상도 아니어서 변경이 관측되지 않는다. 출처 검사도 모듈에 대해서는 `binding_file(module)`과 같은 `module.__file__`의 basename을 비교하므로 사실상 항등식이다. 그 결과 정책값을 변조하면서 위조 설정에 새 기대값을 넣어도 T-80과 모든 앵커가 함께 green이 될 수 있어, '비용을 1지점에서 2지점으로 올렸다'는 설명이 거짓이다.
  Recommendation: 두 번째 판독기는 `config.CONFIG_PATH`를 참조하지 말고 러너 자신의 고정 위치에서 경로를 독립 파생하라. 설정 파일의 경로와 바이트를 그 설정 밖의 신뢰점에 결속하고, 모듈 출처 검사는 자기 `__file__` 비교가 아닌 예상 절대경로·코드 digest로 검증하라.
- [high] probe capability를 사칭하고 기록을 동일 개수로 치환할 수 있다 (tools/spikes/phase0_contract/audit_guard.py:459-489)
  인가 identity는 공개 문자열 토큰과 `basename(co_filename):co_name`뿐이다. `compile`의 filename과 함수명을 맞추면 임의 코드가 허용 호출지점을 사칭할 수 있다. 더구나 창은 호출자에게 mutable `probe_reads`를 반환하고, 종료 게이트는 기록 본문이 아니라 토큰별 개수만 센다. 사칭한 창에서 발생한 차단 기록을 삭제하거나 같은 개수의 다른 내용으로 치환하면 `unsanctioned_windows`와 개수 앵커가 모두 침묵한다. 교차 스레드 결함은 고쳤지만 capability와 기록 결속 주장은 여전히 부분해소다.
  Recommendation: 문자열 토큰 대신 러너만 보유하는 불투명 capability를 사용하고 호출자에게 기록 리스트를 반환하지 마라. 호출지점은 예상 절대경로와 코드 digest에 결속하며, 기록은 호출자가 수정할 수 없는 append-only sequence와 정규화된 내용 digest까지 검증하라.
- [high] pre-hook 실행문 분류가 ClassDef 본문 실행을 누락한다 (tools/spikes/phase0_contract/test_contracts.py:891-904)
  `_statement_executes(ClassDef)`는 decorator·base·keyword만 보고 `node.body`를 순회하지 않는다. 하지만 클래스 본문은 import 시 즉시 실행된다. 따라서 pre-hook 구간에 정적 `_io` import와 `FileIO`를 호출하는 클래스 본문을 두어도 실행문 개수는 증가하지 않고, `FileIO`는 금지 이름 목록에도 없어 dynamic 검사가 비어 있을 수 있다. hook 설치 전 실제 I/O가 가능하며 이를 잡는 층은 함께 갱신 가능한 불투명 구간 digest뿐이다. '실행문 개수를 정직하게 센다'는 선언과 실제가 다르다.
  Recommendation: 가장 안전하게는 피검사 파일보다 먼저 실행되는 외부 bootstrap에서 hook을 설치하라. 현 분석기를 유지한다면 ClassDef 본문과 import 실행, bare decorator 적용을 실행으로 분류하고 `FileIO` 등 누락 I/O 진입점도 검사하라.
- [medium] 자동 정책 census가 클래스 정책값을 어느 분류에도 넣지 않는다 (tools/spikes/phase0_contract/test_contracts.py:693-720)
  census는 `callable(value)`를 이름 등록 전에 건너뛰므로 클래스는 targets뿐 아니라 residual과 phantom 검증에서도 사라진다. 실행코드 앵커도 클래스 멤버 중 `__code__`가 있는 메서드만 묶어 클래스 속성값은 보지 않는다. 따라서 메서드가 참조하는 클래스 정책 상수의 런타임 변경은 앵커와 잔여 목록 모두에서 침묵한다. 현재 77개·잔여 27개는 이 축소된 정의역 안의 수치일 뿐이며, '새 상수는 자동 red'와 '잔여 전수' 주장은 성립하지 않는다.
  Recommendation: 소스에서 파생한 클래스 이름마다 비호출 class attribute와 함수 default/kwdefault를 재귀적으로 census하라. 지원하지 않을 모양은 최소한 residual에 명시하고 전수라는 주장을 그 실제 정의역으로 좁혀라.
- [medium] SELF-3가 필수 L-EXIT-ROOT 이연 대신 미끼 이연도 승인한다 (tools/spikes/phase0_contract/test_contracts.py:3155-3164)
  `deferral_problems`는 설정에 적힌 각 id가 선언된 limit인지와 track이 비었는지만 확인한다. `L-EXIT-ROOT` 자체가 반드시 존재하는지, track이 `Phase 1`인지 또는 유효한 owner-track 문법인지 검사하지 않는다. 다른 선언 id를 미끼로 넣어도 SELF-3는 green이다. 동시에 모듈 docstring·`exit_status`·최종 출력은 설정과 무관하게 Phase 1을 하드코딩해 선언과 평가가 갈릴 수 있다. 현재 설정은 운영자 처분 B와 일치해 정직하지만, 그 처분을 지킨다는 자기검사는 실재하지 않는다.
  Recommendation: 운영자 처분에서 파생한 필수 deferral map을 별도로 고정해 최소한 `L-EXIT-ROOT=Phase 1`을 요구하고 owner-track 문법을 검증하라. docstring과 최종 고지는 검증된 설정값에서 파생해 하드코딩 불일치를 제거하라.

Next steps:
- CONFIG_PATH 단일 신뢰점을 제거한 뒤 T-80의 경로·출처 계약을 다시 심사한다.
- probe capability와 기록 내용 무결성을 함께 교정하고 L-AUDIT-PROBE-THREAD에 현재 사칭 한계를 등재한다.
- hook 이전 ClassDef/import 실행을 차단하거나 외부 bootstrap으로 경계를 이동한다.
- 클래스 정책값 census와 필수 L-EXIT-ROOT 이연 검사를 추가한다.
- 메타 하네스 확장을 동결하고 다음 증분은 실제 도메인 완료 계약 대조군 증가로 제한한다.
```

---

# 수용검사 (오케스트레이터) — **채택 5 / 기각 0**

| # | sev | `file:line` | 실측 | 처분 |
|---|---|---|---|---|
| 1 | high | `test_contracts.py:3241-3250` | `independent = independent_settings(config.CONFIG_PATH)` — **같은 이름에서 경로 취득 = 1 지점** | 채택 |
| 2 | high | `audit_guard.py:459-489` | 토큰이 공개 문자열 + `basename:co_name` · 게이트는 개수만 | 채택 |
| 3 | high | `test_contracts.py:891-904` | `ClassDef` 분기가 `decorator_list`·`bases`·`keywords` 만 — **`node.body` 미순회** | 채택 |
| 4 | medium | `test_contracts.py:693-720` | `callable()` 스킵으로 클래스가 targets·residual·phantom 전부에서 소실 | 채택 |
| 5 | medium | `test_contracts.py:3155-3164` | `not track or lid not in declared_limits` 만 — `L-EXIT-ROOT` 존재·`Phase 1` 값 미요구 | 채택 |

비협상 규칙 대조: 8 조항 전건, **위반 0**. 5 건 모두 강제 강화 방향.

## 이번 라운드의 두 가지 의미

**① 렌즈 불일치의 정답은 security 였다.** architecture 가 `#3`·`#4` 를 해소로 본 것은
**그 형태를 시험하지 않았기 때문**이다. 같은 계열 렌즈 둘이 갈릴 때 낙관 쪽이 틀렸다 —
독립 심판이 없었으면 해소로 기록될 뻔했다.

**② 저작자 자기보고가 또 거짓이었다.** "비용을 1 지점에서 2 지점으로 올렸다"(`:539-545`)는
실측 1 지점이고, "잔여 27 전수"는 클래스 누락으로 거짓이다. **6 라운드 연속으로 저작자의
자기 서술이 실제보다 넓다.** 다만 v2.8 에서 `#2` 잔여를 저작자가 **스스로 정확히 서술한**
사례가 처음 나왔다(security 실측 확인) — 자기보고 정확도가 개선되는 중이나 아직 신뢰 대상이 아니다.

## ⚠ 심판의 궤적 판단 — `next_steps` 마지막 항

> **메타 하네스 확장을 동결하고 다음 증분은 실제 도메인 완료 계약 대조군 증가로 제한한다.**

수치가 이를 뒷받침한다:

| | v2.6 | v2.7 | v2.8 |
|---|---|---|---|
| 러너 행수 | 2140 | 3120 | **3637** |
| 대조군 | 32 | 38 | 39 |
| **도메인 계약 대조군** | 23 | 23 | **23 (3 라운드 불변)** |
| def/class 본문 중 메타 | — | 32% | **65%** |

**+1497 행 동안 도메인 커버리지는 0 증가**했고, 매 라운드 가장 무거운 신규 결함이
**직전 라운드 교정이 만든 메타 계층에서** 나왔다. 이것은 개별 finding 이 아니라 **궤적에 대한
판정**이며, 처분은 저작자 권한 밖이다 — 운영자 결정 사항으로 올린다.

## 절차 기록 (다음 회차 교정 사항)

`focus5.txt` 에 전역 에이전트 규약이 요구하는 "repo `CLAUDE.md` 비협상 규칙 선독" 문구가 **없었다.**
포워더가 원문 전달 지시를 지켜 주입하지 않았고, 실측상 Codex 가 자력으로 `CLAUDE.md` 를 읽어
범위에는 들어갔으나 **우연 의존이다.** 다음 focus 부터 이 문구를 명시한다.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립 (17회 연속)
```

**P-0 및 모든 D0 구현 착수 차단 유지.**
