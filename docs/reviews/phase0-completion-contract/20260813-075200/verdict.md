# verdict — 레인 A (코드 심판) · v2.5 F1/F3 교정 · **12회 연속 완주**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED            # 14회 연속
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_scope_digest: dfaf7fea6211ec451f4e62db78f1ef35f9255437baeb233bc86ee2f3a51d1ff3
reviewed_scope: tools/spikes/phase0_contract/ (전부 untracked — --scope working-tree)
reviewed_version: v2.5 코드 레인 (F1·F3 교정분)
findings: 4                        # critical 1 / high 3
prior_verdict: .omc/review/20260812-231234/verdict.md
mode: A (adversarial-review, --scope working-tree), job review-msqpqtk1-xepafh, 20m22s, write=false
codex_session: 019ff847-bf98-73f0-8aa9-071679cb3118
lens_evidence: .omc/review/20260813-075200/evidence/ (architecture · security · performance · style)
```

리비전 결속: 디스패치 직전 포착값과 **심사 종료 후 재계산값이 동일**. Codex 뮤테이션은
인메모리/사본에서 수행되어 작업 트리 오염 없음.

> **실행 사고 1건 (기록)**: 최초 디스패치 `review-msqpcot0-7m26yz`는 포워더의 3분 타임아웃이
> 프로세스 그룹을 죽여 중단(상태 레코드만 `running`으로 stale). `cancel`로 정리 후
> `os.setsid()` 이중 fork로 분리해 재디스패치. **회수된 판정은 완주한 두 번째 잡의 것이며
> 부분 결과 혼입 없음.**

## 범위 선언

이번 심사는 v2.3 판정 7건 중 **F1·F3 코드 교정분만** 대상이다.
나머지 5건(F4·F5·IND-1·F7·IND-2)은 문서 소관이며 **미착수**임을 저작자가 사전 명시했고
focus text에 그대로 전달했다 — 이번 판정은 그 5건에 대해 아무것도 말하지 않는다.

## 처분

**F1 부분해소 · F3 부분해소.** 정상 경로의 L1/L2와 v2.3이 제시한 문자열 조립 3종은
실제로 작동한다. 그러나 독립 뮤테이션에서 **실 register 93,904바이트를 읽고도
exit 0 · 30/30 GREEN · 열람 기록 없음 · 앵커 4종 불변**이 재현됐다.

**저작자가 스스로 열거한 "미폐쇄 5건" 목록은 실제 잔여보다 좁다** — SELF-1 소비 배선,
모듈 정책 데이터 앵커, import-before-guard, 경로 동치, 위치 표지 위조를 누락했다.
이것은 v2.3 F1의 결함 클래스("발표 수치를 발표 규칙으로 재계산해 불일치 적발")가
**잔여 목록 자체**에서 재현된 형태다.

## Codex 출력 (verbatim)

```json
{
  "verdict": "needs-attention",
  "summary": "Ship 불가. F1은 부분해소, F3도 부분해소다. 정상 경로의 L1/L2와 제시된 문자열 조립 3종은 작동하지만, 독립 뮤테이션에서 실제 register 93,904바이트를 읽고도 exit 0·30/30 GREEN·열람 기록 없음·앵커 불변이 재현됐다. 저작자의 '미폐쇄 5건' 목록은 SELF-1 소비 배선, 모듈 정책 데이터 앵커, import-before-guard, 경로 동치, 위치 표지 위조를 누락한다. 추가 untracked 파일 중 OQ-11 digest는 현재 일치하고 두 형제 도구와 uv.lock은 F1/F3 교정을 증명하지 않으며, proto/__init__.py는 오히려 'proto 7개' 앵커 누락을 드러낸다.",
  "findings": [
    {
      "severity": "critical",
      "title": "F3 부분해소: 피검사 모듈이 가드 설치 전에 실행된다",
      "body": "proto 모듈 import는 main()의 read_guard 진입보다 먼저 발생한다. 현재 register.py에 bytes로 조립한 경로를 builtins.open으로 읽는 모듈 레벨 문장을 합성한 결과, 리터럴·AST 스캔은 모두 [], 실제 EVIDENCE-REGISTER-002.csv 93,904바이트를 읽은 뒤에도 러너는 exit 0, 30/30 GREEN, 열람 기록 없음, 앵커 4종 불변이었다. 따라서 런타임 가드는 import-time 실행 창을 구조적으로 덮지 못하며 F3의 OD-3-A 강제는 성립하지 않는다.",
      "file": "tools/spikes/phase0_contract/test_contracts.py",
      "line_start": 73,
      "line_end": 74,
      "confidence": 1,
      "recommendation": "피검사 proto를 import하기 전 최소 bootstrap에서 audit hook 또는 동등한 process-wide 가드를 설치하고, import-time 모듈 문장으로 실제 register를 읽는 대조군이 main exit를 red로 만드는지 검증하라."
    },
    {
      "severity": "high",
      "title": "F3 부분해소: 가드 내부에서도 경로 별칭과 위치 위조가 통과한다",
      "body": "가드 활성 중 _io.open으로 동일 register 93,904바이트를 읽어도 attempts=[]였다(builtins.open is io.open is _io.open도 True). 현 APFS에서는 대소문자를 바꾼 TOS-SPEC/.../evidence-register-002.csv가 존재하며 read_violation=None, Path.read_bytes 성공, attempts=[]였다. 또한 repo 내부 tos/의 기존 pyproject.toml을 가짜 루트 표지로 주자 존재하지 않는 예상 러너 경로도 locate_violation=[]였다. 이는 저작자가 열거한 잔여 5건 밖의 독립 F3 우회들이다.",
      "file": "tools/spikes/phase0_contract/proto/boundary.py",
      "line_start": 414,
      "line_end": 566,
      "confidence": 1,
      "recommendation": "열거식 monkeypatch를 audit hook 기반 관측으로 교체하고, 경로 비교는 case normalization 및 실제 대상 identity를 반영하라. 위치 검사는 marker 존재가 아니라 git 최상위 루트와 실재 runner의 동일성을 검증하며 _io·대소문자 별칭·가짜 pyproject 대조군을 추가하라."
    },
    {
      "severity": "high",
      "title": "F1 부분해소: SELF-1의 mutant_red가 실제 실패 소비 배선을 검사하지 않는다",
      "body": "SELF-1의 clean_green에서 undeclared/missing/duplicate/unresolved/parked/digest_drift 소비만 제거하고 합성 probe는 그대로 둔 뒤 미등재·green 주차 노트를 주입했다. 결과는 SELF-1 clean_green=True, mutant_red=True, 실패 Case 0이었다. 방출·Case 앵커는 불일치를 표시했지만 exit에는 반영되지 않았고 실행코드 digest도 f4ea9b8f2d77b472로 불변이었다. 즉 mutant_red는 헬퍼가 저자가 만든 정확한 합성 입력을 반환하는지만 확인하는 자기충족적 검사이며, 그 결과가 exit로 소비되는지는 검증하지 않는다.",
      "file": "tools/spikes/phase0_contract/test_contracts.py",
      "line_start": 1525,
      "line_end": 1573,
      "confidence": 0.99,
      "recommendation": "L1/L2/L3 각 실패 항을 실제 clean_green 소비 경로에서 하나씩 제거하는 뮤턴트를 실행해 main exit 1을 요구하라. 앵커 불일치는 별도 필수 실패 Case로 만들고, 코드 앵커에는 최소한 co_code와 co_names를 포함해 조건식 제거가 침묵하지 않게 하라."
    },
    {
      "severity": "high",
      "title": "신규 결함: '소스 전체' 앵커가 모듈 정책 데이터와 __init__.py를 제외한다",
      "body": "_module_code_parts는 __code__가 있는 함수·메서드만 수집하므로 모듈 레벨 tuple/frozenset/dict, 문장, docstring과 주석은 정의역 밖이다. 독립 인메모리 뮤테이션에서 FORBIDDEN_ARTIFACTS 5→1 및 REQUIRED_METRICS 4→2가 모두 실패 Case 0, 앵커 4종 불변으로 통과했다. 호출 목록도 runner+proto 6개뿐이라 config.yaml이 주장하는 proto 7개 중 __init__.py가 빠진다. 따라서 '어떤 편집이든 갱신 요구'와 현재의 가시화 주장은 사실이 아니다.",
      "file": "tools/spikes/phase0_contract/test_contracts.py",
      "line_start": 291,
      "line_end": 332,
      "confidence": 0.99,
      "recommendation": "스캔 대상 전 파일의 정확한 소스 바이트와 로드된 코드의 의미 직렬화, 모듈 정책 값 전체를 함께 결속하라. FORBIDDEN_ARTIFACTS 전 항목과 REQUIRED_METRICS 전 항목을 각각 제거하는 대조군을 추가하고 __init__.py 포함 여부를 선언과 일치시켜라."
    }
  ],
  "next_steps": [
    "F3를 pre-import 강제로 재설계하고 import-time·_io·대소문자·가짜 루트 뮤테이션이 모두 exit 1인지 확인한다.",
    "F1의 합성 helper probe를 실제 소비 배선 뮤테이션으로 교체하고 코드·모듈 데이터 앵커의 정의역을 닫는다.",
    "작업트리 전체 경로를 다음 재심 범위에 명시하되, F4·F5·IND-1·F7·IND-2 문서 작업과 이번 F1/F3 코드 교정을 구분해 결속한다."
  ]
}
```

---

# 수용검사 (오케스트레이터 = Claude) — **채택 4 / 기각 0**

기각 가능 사유는 3가지뿐이다(팬텀 `file:line` · 의도적 silenced · 비협상 규칙 배치).
**어느 finding도 해당하지 않는다.** 아래는 전건 독립 실측이다.

| # | severity | `file:line` 실재 | 독립 재현 | 처분 |
|---|---|---|---|---|
| 1 | critical | `test_contracts.py:73-74` (import) vs `:1611` (가드 진입) — **실재** | **확증** | 채택 |
| 2 | high | `proto/boundary.py:414-566` — **실재** | **확증** (3축 전부) | 채택 |
| 3 | high | `test_contracts.py:1525-1573` — **실재** | **확증** | 채택 |
| 4 | high | `test_contracts.py:291-332` — **실재** | **확증** | 채택 |

## 오케스트레이터 독립 실측 기록

**#1 import-before-guard (구조적 확증)**
```
:73  from proto import boundary, enforcement, floor, gates, register
:74  from proto.config import cfg_int, cfg_list, load_config
:1611    with boundary.write_guard() as recorder, boundary.read_guard() as read_recorder:
```
import이 가드 진입보다 **1,538행 앞선다**. 저작자가 "실행 전체를 감쌌다"고 한 것은
`run_all()` 전체였지 **프로세스 전체가 아니었다.** 가드를 `main()` 안에서 여는 설계인 한
import-time 창은 구조적으로 덮이지 않는다.

**#2 경로 별칭·위치 위조 (3축 전부 확증)**
```
builtins.open is io.open : True
io.open is _io.open      : True          → 8개 목록 중 2개가 동일 객체, 세 번째 이름 누락
대소문자 변형 존재: True | samefile: True
read_violation(정본): True / read_violation(변형): False    → 우회 성립
tos/pyproject.toml 실재 → locate_violation(가짜루트, 미실재 러너) = []
```
가짜 루트 재료가 **repo 내부에 이미 존재**한다(`tos/pyproject.toml`) — 외부 준비물이 필요 없다.

**#3 mutant_red 자기충족성 (확증)**
```
mutant_red (합성 probe 만 의존): True
실제 위반 존재: True ['L-SMUGGLE']
소비 항 제거 시 Case.ok = True    ← 침묵
```
`mutant_red`는 `probe`에서만, `clean_green`은 `rep`에서만 계산된다 — **두 값이 독립**이므로
소비 배선을 끊어도 방향②는 성립한 채로 남는다. 양방향 대조군의 방향②가
"검사가 작동하는가"가 아니라 "헬퍼가 합성 입력에 기대값을 반환하는가"만 본다.

**#4 앵커 정의역 구멍 (확증)**
```
FORBIDDEN_ARTIFACTS 앵커 blob 에 존재: False
READ_GUARDED        앵커 blob 에 존재: False
EXPECTED_RELPATH    앵커 blob 에 존재: False
proto/*.py 파일수: 7 / 앵커 대상 = runner + proto 6  → __init__.py 누락
```
**경계를 정의하는 정책 상수 전부가 앵커 밖이다.** 5라운드에 걸쳐 앵커가 덮은 것은
함수 **안**의 산문이었고, 강제의 **내용물**은 한 번도 덮이지 않았다.
`config.yaml:52-53`의 "러너의 **어떤 편집이든** 이 값 갱신을 요구한다"와
`:60`의 "proto 7개"는 **둘 다 현재 시제로 거짓**이다.

## 비협상 규칙 대조 — 위반 0

8조항 전건 대조. 4개 finding 모두 **강제를 강화하는 방향**이며 배치되는 권고 없음:
선물 대칭 훼손 · 실계좌 증거금 · EOD 일괄청산 · ClickHouse 신규 · RL/TFT 부활 ·
하드코딩 권고 · Redis DB 이탈 · 비-KST 세션 판정 — **해당 없음.**

다만 finding #4의 권고("모듈 정책 값 전체를 결속")를 이행할 때
**앵커 값은 `config.yaml`에 두어야 한다**(설정 구동). 코드에 박으면 그 자체가 비협상 위반이다.

## 관통 패턴 — 13번째

| 층 | 형태 |
|---|---|
| v1.3.8~v2.1 | 문서 안 선언↔평가 간극 (10회) |
| v2.2 | **증거 도구**로 전이 |
| v2.3 | 증거 도구의 **교정**에도 같은 간극 |
| **v2.5** | **교정의 잔여 목록 자체**로 전이 — 저작자가 열거한 미폐쇄 5건이 실제 잔여보다 좁았다 |

v2.5의 새 형태는 **"닫았다"가 아니라 "이만큼 남았다"는 진술이 틀린 것**이다.
축소 주장(가시화)조차 실제보다 넓었다. 세션 중 stop-hook 5라운드가 매번 저작자가
방금 만진 표면만 짚은 반면, 4렌즈 병렬 + 독립 뮤테이션은 **한 번도 보지 않은 표면**
(모듈 레벨 데이터 · import 창 · 소비 배선)을 짚었다 — 자기검증과 독립심사의 차이가
이 대비로 실증됐다.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립 (14회 연속)
```

**P-0 및 모든 D0 구현 착수 차단 유지.**
