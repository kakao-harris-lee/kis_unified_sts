# 성능 렌즈 — 증거 (판정 없음)

**대상**: `tools/spikes/phase0_contract/` (TOS Phase 0 완료 계약 프로토타입 v2.5)
**성격**: 단발 실행 개발/심사 도구. **hot path 없음** — 런타임 트레이딩 루프에 배선되지 않는다.
**이 문서는 verdict 를 내지 않는다.** 심각도는 증거의 크기를 표기한 것이며 차단 판정이 아니다.

## 실측 환경

- Python 3.14.5 (homebrew, arm64) · darwin 25.5.0 · 프로토타입 **무수정**
- 하네스: `/private/tmp/claude-503/.../scratchpad/{prof_driver,complexity,attribute,guard_paired}.py`
- 프로토타입 파일 전건 mtime·크기 불변 확인. 계측 중 생성된 `proto/__pycache__/` 는 제거함
  (세션 시작 시점 스냅샷에 부재했다).

## 기준선

```
$ python3 tools/spikes/phase0_contract/test_contracts.py
대조군 30건 중 양방향 성립 30건 · exit 0
end-to-end wall (10 회): 149.0 / 153.5 / 153.9 / 154.4 / 155.0 / 155.1 / 158.7 / 159.1 / 159.7 / 171.0 ms
  → median 154.7 ms (인터프리터 기동 ~55 ms 포함)
run_all() 자체 (in-process, n=9): median 97.8 ms
```

## 시간 귀속 (계측판, `run_all()` = 101.8 ms)

| 함수 | 호출 | 누적 ms | % of run_all |
| --- | --- | --- | --- |
| `boundary.scan_sources_ast` | **3** | **87.2** | **85.7 %** |
| └ `ast.parse` | 26 | 38.5 | 37.9 % |
| └ `boundary._fold_env` | 25 | 28.6 | 28.1 % |
| `test_contracts.limit_text_anchor` | 1 | 8.6 | 8.5 % |
| `boundary.read_prototype_sources` | 1 | 1.1 | 1.1 % |
| **`boundary.read_violation` (열람 가드)** | **45** | **0.82** | **0.8 %** |
| `test_contracts.loaded_code_text` | 1 | 0.30 | 0.3 % |
| `boundary.scan_sources` (리터럴) | 2 | 0.17 | 0.2 % |

cProfile 교차확인: `run_all` cumtime 0.293 s 중 `t77_boundary` 0.264 s, 그 중 `scan_sources_ast` 0.260 s.
`ast.walk` 128,567 호출 / `iter_child_nodes` 254,971 호출 — 전량 `scan_sources_ast` 소관.

---

# 발견

## P-1 · MEDIUM — `scan_sources_ast` 3 회 전량 재스캔 (2 회는 ~50 B 델타에만 필요)

- **dimension**: performance
- **location**: `tools/spikes/phase0_contract/test_contracts.py:728,735,742` (호출부) ·
  `tools/spikes/phase0_contract/proto/boundary.py:381-411` (구현)
- **경로 구분**: **cold path** (단발 러너). hot path 아님.

`t77_boundary` 는 같은 9 파일 소스맵에 대해 AST 스캔을 3 회 돌린다:

```
728:  clean_ast      = ast_scan(sources)          # 9 파일 원본
735:  mutant_ast     = ast_scan(planted_ast)      # 원본 9 파일 + 52 B 주입 파일 1개
742:  mutant_narrow  = ast_scan(planted_narrow)   # 원본 8 파일 + boundary.py(+26 B)
```

2·3 회차의 입력은 1 회차와 각각 **52 B / 26 B** 만 다른데, `scan_sources_ast` 는 매번
전체를 `ast.parse` 하고 `_fold_env` 로 다시 walk 한다.

**실측 (1 회 스캔 = 28.3 ms, 파일별 내역)**

| 파일 | 크기 | AST 노드 | 1 회 스캔 |
| --- | ---: | ---: | ---: |
| `test_contracts.py` | 57,640 B | 9,028 | 13.34 ms |
| `boundary.py` | 20,681 B | 3,538 | 4.91 ms |
| `enforcement.py` | 11,077 B | 1,981 | 3.02 ms |
| `register.py` | 13,934 B | 2,064 | 2.91 ms |
| `gates.py` | 9,632 B | 1,593 | 2.06 ms |
| `config.py` | 3,273 B | 638 | 0.85 ms |
| `floor.py` | 3,534 B | 553 | 0.74 ms |
| `__init__.py` | 152 B | 3 | 0.01 ms |
| **합** | **119.9 KB** | **19,398** | **28.26 ms** |

`ast.parse` 에 투입된 누적 바이트 (1 회 실행):

```
test_contracts.py  172,920 B  (= 57,640 × 3)
boundary.py         62,069 B  (= 20,681 × 2 + 20,707 × 1)
<unknown>           57,640 B  (limit_text_anchor 의 parse, filename 미지정)
register.py         41,802 B  (= 13,934 × 3)   …  이하 동일 패턴
```

- **예상 영향**: 회차 2·3 이 실질적으로 전량 중복 = 약 **56–58 ms** / `run_all()` 96–102 ms 의 **~58 %**,
  end-to-end 155 ms 의 **~37 %**.
- **recommendation**: `(파일명, 텍스트)` 키 메모이즈 또는 델타 파일만 스캔하고 나머지는 재사용.
  다만 **이 러너는 "검사기 입력 seam 으로 뮤테이션을 주입한다"는 계약을 그대로 표현한 코드**이고,
  캐시를 끼우면 그 seam 이 캐시 뒤로 숨어 대조군의 독립성 주장이 약해질 수 있다 —
  **성능 이득(≈58 ms)이 그 위험을 정당화하는지는 성능 렌즈의 판단 범위 밖**이다. 현상만 기록한다.
- **confidence**: 95

## P-2 · LOW — 러너 소스를 1 회 실행에 4 번 파싱

- **dimension**: performance
- **location**: `test_contracts.py:1487-1489` (`Path(__file__).read_text()` → `limit_text_anchor`) ·
  `test_contracts.py:728,735,742` (스캔 3 회)
- `test_contracts.py` (57.6 KB) 는 `scan_sources_ast` 안에서 3 회, `limit_text_anchor` 에서 1 회,
  총 **4 회** `ast.parse` 된다. `limit_text_anchor` 실측 **7.87–8.60 ms** (그 중 `ast.parse` 단독 4.90 ms).
- 세 앵커는 각각 **다른 목적**(스캔 = 금지 토큰 / 앵커 = `limit()` 리터럴 digest)이므로
  트리 재사용은 가능하되 자명하지 않다. P-1 을 고치면 자연히 4 → 2 로 준다.
- **recommendation**: P-1 과 함께 처리할 때만 의미. 단독으로는 비용 대비 이득 없음.
- **confidence**: 92

---

# 기각된 가설 — 측정 결과 "없음"

## H-1 · 열람 가드(`read_guard`) 실행 오버헤드 → **실질 영향 없음**

브리핑 가설: "러너 전체를 감싸므로 모든 읽기가 `Path(...).resolve()`(stat)를 탄다."
**구조는 그렇지만 읽기 횟수가 45 회뿐이라 총액이 1 ms 미만이다.**

- `boundary.py:428` `Path(text).resolve()` 는 실제로 매 열람마다 호출된다 — 확인됨.
- **단위 비용**: `read_violation()` **15.6 µs/call**, 그 중 `Path(x).resolve()` **13.4 µs**
  (존재하는 경로 13.37 µs · 부재 경로 15.04 µs), `os.fsdecode()` 0.06 µs.
  → 비용의 **86 %** 가 `resolve()` 이며, 이는 경로 **값**으로 판정한다는 설계의 본질 비용이다
  (싼 prefilter 를 넣으면 v2.3 이 뚫린 "프록시로 강제" 로 되돌아간다).
- **1 회 실행 실측 호출 수: 45 회 · 누적 0.74–0.82 ms** = `run_all()` 의 **0.8 %**, wall 의 **0.5 %**.
- **가드 유무 A/B (교차 21 쌍, in-process)**:

```
guards OFF  median  95.53 ms  stdev 2.27
guards ON   median  95.46 ms  stdev 1.62
paired delta median +0.250 ms · mean +0.172 ms · stdev 2.062 ms   → 노이즈와 구분되지 않음
```

  차분의 stdev(2.06 ms)가 차분 자체(+0.25 ms)보다 크다. **A/B 로는 검출 불가**이므로
  위의 호출수×단위비용 회계(0.70 ms)를 상한 근거로 삼는다.
- **조건부 주의(측정 기반 외삽, 현 코드에는 해당 없음)**: 비용은 열람 횟수에 선형이다 —
  1e3 회 = 15.6 ms, 1e5 회 = 1.6 s. 가드가 열람이 많은 워크로드를 감싸게 되면 그때 재측정 대상.
- **판정**: 현 프로토타입에서 **성능 문제 없음**. 지적을 만들지 않는다.

## H-2 · 앵커 계산 비용 → **1 회 계산, 실질 영향 없음**

브리핑 가설: "`loaded_code_text` 가 모듈 7 개 `dir()` 순회 + 코드 객체 재귀 — 반복 계산되는가."
**전부 `self_check()` 안에서 정확히 1 회씩만 계산된다** (계측 호출수 = 1).

| 앵커 | 위치 | 실측 (median) |
| --- | --- | --- |
| `loaded_code_text(7 modules)` | `test_contracts.py:318,1493-1503` | **0.149 ms** (출력 25,795 chars) |
| `runner_source_anchor` (sha256) | `test_contracts.py:335,1492` | **0.029 ms** |
| `limit_text_anchor` (전체 AST 파싱) | `test_contracts.py:227,1489` | **7.871 ms** ← P-2 |
| `case_prose_anchor` | `test_contracts.py:355,1521` | **0.010 ms** |
| `emitted_text_anchor` | `test_contracts.py:262,1506` | **0.005 ms** |

`loaded_code_text` 의 `dir()` 순회 + `co_consts` 재귀는 **0.15 ms** — 우려된 비용의 실체가 없다.
유일하게 유의미한 것은 `limit_text_anchor` 의 파싱이고 그것은 P-2 로 기록했다.

## H-3 · `scan_sources_ast` / `_const_str` 재귀 폭발 → **지수 아님. Θ(n²)이고, 실제 소스에서는 선형**

브리핑 가설: "`_const_str` 가 중첩 BinOp 에서 **지수적으로** 재계산되는가."
**아니다.** `_const_str` 는 한 호출 안에서 부분트리를 재방문하지 않으므로 호출당 O(subtree).
`ast.walk` 가 모든 expr 노드마다 그것을 다시 부르므로 총합 = Σ(부분트리 크기) = **최악 Θ(n²)**.

**A. 좌측 스파인 상수 연결 `x = 'a' + 'a' + …` (n 항)**

| n | AST 노드 | 스캔 | 배증 시 비율 | ms/n² ×1e3 |
| ---: | ---: | ---: | ---: | ---: |
| 25 | 77 | 0.193 ms | — | 0.308 |
| 50 | 152 | 0.497 ms | ×2.58 | 0.199 |
| 100 | 302 | 1.508 ms | ×3.03 | 0.151 |
| 200 | 602 | 5.492 ms | ×3.64 | 0.137 |
| 400 | 1,202 | 20.19 ms | ×3.68 | 0.126 |
| 800 | 2,402 | 81.00 ms | ×4.01 | 0.127 |
| 1600 | 4,802 | 333.2 ms | ×4.11 | 0.130 |

배증당 **×4 로 수렴**하고 `ms/n²` 이 0.13 에서 **평평해진다** → 지수(×2^n)가 아니라 **정확히 2 차**.
중첩 `%` 포맷(E)도 배증당 ×3.7, 중첩 f-string(B)도 ×3.6 으로 같은 2 차 곡선.

**B. 실제 소스에서는 선형** — 8 개 파일 전부 **0.21–0.27 ms/KB**:

```
floor.py 0.210 · register.py 0.209 · gates.py 0.214 · test_contracts.py 0.231
boundary.py 0.237 · config.py 0.260 · enforcement.py 0.273  ms/KB
```

2 차 항이 나타나려면 **단일 식**이 수백 항이어야 하는데 실제 코드에는 그런 식이 없다.

**C. 왜 싼가 — `_const_str` 는 거의 즉시 None 을 낸다**

```
test_contracts.py 의 non-Constant expr 노드: 4,159 개
그 중 실제로 문자열로 접히는 것:                 8 개  (0.19 %)
_const_str 총 호출: 30,446 회 / 누적 ~20 ms (cProfile tottime 0.011 s)
```

`ast.expr` 로 넓힌 v2.5 변경의 비용은 **`_const_str` 재귀가 아니라 `ast.walk` 순회 자체**다:

```
test_contracts.py 1 파일 분해:  ast.parse 4.85 ms · _fold_env 4.04 ms
                               ast.walk+isinstance 2.67 ms · +_const_str 3.47 ms
                               (_exempt_node_ids 0.000 ms — TOKEN_DEFINITION_SITE 아니면 즉시 반환)
                               full scan_sources_ast 12.86 ms
```

즉 `_fold_env`(boundary.py:314, 전체 walk 1 회)와 `ast.parse` 가 각각 ~31 % / ~38 % 이고,
브리핑이 지목한 `_const_str` 상수 전파는 **27 %** 이며 그 안에서도 walk 오버헤드가 대부분이다.

**D. 부수 관측 (성능 아님, 정직성 기록)** — 중첩 f-string 깊이 150 이상은
CPython 파서가 `SyntaxError: too many nested f-strings` 를 낸다. `scan_sources_ast:394-396` 은
이를 **조용히 통과시키지 않고 finding 으로 보고**한다. 측정표 B 의 depth-160 행이 0.115 ms 로
급락한 것은 성능 개선이 아니라 이 파싱 실패 경로다.

**E. 정직한 한계** — 위 2 차 곡선은 합성 입력으로만 관측했다. 스캔 대상은 커밋된 `proto/*.py` 와
러너 자신이므로 적대적 입력 표면이 아니다. **현 코드에 실질 영향 없음**으로 기록한다.

## H-4 · N+1 · 불필요한 재계산 → **없음**

`proto/` 헬퍼 전량을 계측했다. 호출 빈도가 높은 상위 항목:

```
register.classify_owner_track  867 회  0.574 ms
gates._contribute              759 회  0.200 ms
floor.floor                    305 회  0.313 ms
floor.parse_levels             305 회  0.201 ms
gates.completion_gates         296 회  0.112 ms
register.metrics                81 회  0.900 ms
gates.evaluate                  69 회  0.746 ms
```

호출 횟수는 많지만 **합계가 5 ms 미만**이다 (픽스처가 30 행 규모). 반복 호출을 캐시할 이유가 없고,
오히려 대조군마다 레지스트리를 새로 만드는 것이 테스트 격리에 부합한다. **지적 없음.**

`Report.case_index()` 가 `unbound_defects` / `green_bound_defects` / `unresolved_limit_refs` /
`parked_limits` 에서 각각 재구성되지만 Case 30 건 기준 마이크로초 단위다 — micro-opt 이므로 적지 않는다.

---

# 요약

| # | 심각도 | 위치 | 요지 | 측정 영향 |
| --- | --- | --- | --- | --- |
| P-1 | MEDIUM | `test_contracts.py:728,735,742` | 전량 AST 재스캔 3 회 (델타는 ~50 B) | **≈58 ms / run_all 의 58 %** |
| P-2 | LOW | `test_contracts.py:1489` + 위 | 러너 소스 4 회 파싱 | ≈8 ms (P-1 과 겹침) |
| H-1 | **없음** | `boundary.py:428,492` | 열람 가드 — 45 회 × 15.6 µs | 0.8 % (A/B 로는 검출 불가) |
| H-2 | **없음** | `test_contracts.py:318,335,355,262` | 앵커 — 전부 1 회, 0.005–0.15 ms | 무시 가능 |
| H-3 | **없음** | `boundary.py:265,314,381` | 지수 아님 · Θ(n²) · 실소스는 선형 | 무시 가능 |
| H-4 | **없음** | `proto/*.py` | N+1 없음 | 합계 < 5 ms |

**전체 판단 재료**: 이 도구는 단발 실행 **cold path** 이고 end-to-end **155 ms** 다.
P-1 을 전부 제거해도 약 **97 ms** 가 되며, 사람이 체감할 차이가 아니다.
성능 렌즈가 이 판(v2.5)의 착지를 막을 근거는 제시하지 않는다 — 다만 P-1 은
"같은 파싱을 3 번 한다"는 **관측된 사실**이므로 기록에서 빼지 않는다.
