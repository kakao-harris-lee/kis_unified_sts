# U-17 «예방 통제 활성 증거» — v2.22 실행 증거 (T-84)

- **계약**: `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md` — **v2.22 동결 `8ec227541d12ca290bbe4906ebe146aed5f06040`**
- **개발계획**: `docs/plans/2026-08-11-tos-completion-development-plan.md` (동결 동일 커밋)
- **실행 시각**: 드라이버 `t84v222_utc=2026-08-20T10:18:02Z` · 착수 스탬프 `20260820-184748`(KST)
- **선행 판**: `docs/reviews/phase0-completion-contract/20260819-193235/U17-PREVENTION-CHECK-V221.md` (3,018행)
- **성격**: 이 문서는 **저작이 아니라 실행 증거**다.  «해소» 를 주장하지 않는다 — 주장할 수 있는 것은
  «v2.22 가 적은 술어를 실행기로 구현해 돌렸고 그 결과가 이것이다» 뿐이고, 판정은 레인 B 재심의 소관이다.
- **서버 쓰기 0**: 모든 GitHub 접근은 `gh api` GET.  live 로 불가능한 구성은 전부 `responder=file:`
  seam 주입이며 그렇게 라벨했다(`SIMULATED`).
- **커밋하지 않았다** — 오케스트레이터의 독립 검증 후 커밋 대상이다.

---

## 1. S-24 결속 (실측)

```text
t84v222_utc=2026-08-20T10:44:14Z
HEAD=6d10fcf99968304d072d27ca491f006b0dc246af  freeze=8ec227541d12ca290bbe4906ebe146aed5f06040
sha256(u17-verify-v222.sh    )=e97ebdfc87e1985306bb15bdff70585095b8c1f42b46c28ed49e00c9f051bf86
sha256(wfcanon-v222.py       )=d5e11bf0fef7f5bb9896caba8bebf93bebe5a4e640543cd963716f9235c95cd0
sha256(mkwf-v222.py          )=2fd62120be6cf0351eb0e59ff7ca0508313e5a8ba5af1cc4319c0259606a8bba
sha256(derive-v222.py        )=896785583699760e326448e78a1cca918bc795138914b3bbcb95a980bec94e95
sha256(u17-verify-v221.sh    )=5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727
sha256(wfcanon-v221.py       )=a5430e1a593d890f19a36713b9577c15c807a12c4131d45bd2937744255b811d
sha256(mkwf-v221.py          )=f0688051749c4ff4ff141a7dd2f148bc7256bd249b8c790762f7230a31e052f5
sha256(t84v221.sh            )=962cc027f88a9ff2adad807c08136132de8168e651c0a3006661fa6022bb9a72
-- 실행기 diff(v2.21 → v2.22) 행수 = 187 (파생기 훅 12개) --
```

- 두 결속 문서의 blob 이 `HEAD`(`6d10fcf9…`) 와 동결 `8ec22754` 에서 **동일**함은 오케스트레이터가
  실측했고 이 실행에서 재확인했다(드라이버 머리 2행).
- **하니스 §12.3.4-R 결속값**: 계약 `4721,4821p`(101행) sha256
  `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`
  == 계약이 선언한 값(`:4517` `:4998` `:5719` `:5726`) — 정본 B 리터럴의 소스다.
- **도구 실측**: `yq (mikefarah) v4.48.1`(계약 핀 `v4.48.x` 일치) · `gh 2.93.0` · `git 2.38.0` ·
  compose 층 `.venv/bin/python` 3.12.2 + PyYAML 6.0.3.
  시스템 `python3` 3.14.7 에는 **PyYAML 이 없다** — 그래서 술어의 compose 층만 `$PYBIN` 으로 돌고
  실행기 자신의 inline JSON 헬퍼는 `python3` 그대로다(코드 델타 0).

---

## 2. 실행기 파생 — v2.21 → v2.22 «델타 전용»

실행기를 손으로 다시 쓰지 않았다.  `derive-v222.py`(§15)가 v2.21 원문
(sha256 `5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727` — **§3-0 추출 충실성 증명 참조**)에
**앵커가 유일한 훅 12개**만 적용한다.  앵커가 1회가 아니면 파생이 즉시 중단되므로,
«v2.21 거동 그대로»는 주장이 아니라 **구조**다.

```text
훅 12개 적용 → u17-verify-v222.sh (591행 · sha256 e97ebdfc87e1985306bb15bdff70585095b8c1f42b46c28ed49e00c9f051bf86)
diff u17-verify-v221.sh u17-verify-v222.sh | grep -c '^[<>]'  →  187
```

### 2-1. 델타 표 (v2.21 실행기·술어 → v2.22)

| 훅 | 계약 근거 | 축 | 델타 |
|---|---|---|---|
| H1 | — | 헤더 | v2.22 델타 이력을 «맨 위»에 얹고 v2.21 원문 헤더를 보존(파생 계보) |
| H2 | :5606-5635 | 술어 파일 | `wfcanon-v221.py` → **`wfcanon-v222.py`** · `$PYBIN`(PyYAML compose 층) · `GATE_JOB` 계약 리터럴 |
| H3 | :5255-5261 · :5425-5437 | 게이트 체크 이름 | 아티팩트 `tos_gate_check` 파생 **폐지** → 계약 리터럴 `tos-gate`(선례 `gate_app_id`·`remote_name`) |
| H4 | :5566-5591 · :5828-5849 | **(b-blob)@target** | `D` 무관 «무조건 항» **신설** — `branches/<target>` → `.commit.sha` verbatim 수록 → `contents?ref=<target HEAD>` 정본 잡 대조.  404·HTTP = `UNVERIFIED_REVISION`(ABSENT 로 접지 않는다) · 네트워크/인증 = `UNVERIFIABLE` |
| H5 | :5557-5565 | (b)② | `conclusion==success` **선-필터 폐기** → **동명 check-run 전수 열거** + 각 check-run 을 그 자신의 워크플로 run 으로 해석(`details_url` 의 run id · 없으면 suite 안 run 이 «정확히 1개»일 때만 결속, 복수 = 모호 = fail-closed) → **정본 `path` 인 것이 «정확히 1개» ∧ `success`**.  `[E2]` suite 귀속 대조 유지 |
| H6 | :5606-5688 | 술어 호출 | `WF_GATE_JOB`/`WF_HARNESS`/`WF_SHA` env **선언 제거**(자기선택 표면) |
| H7 | :5643-5762 · :5789-5802 | 사유 문자열 | «두 스텝 run 대조» → «정본 «잡 템플릿»» · 서버 층에 `hit` 유일성 문구 |
| H8 | :5828-5835 | `D=∅` 안내 | «(b)(c) 검증 대상 없음» → «(b-blob)@target 은 이미 평가됐다» |
| H9 | :6030-6039 | finish 사유 | `(b-blob)@target=<상태>(target HEAD=<sha>)` 를 논리곱에 명시 |

### 2-2. 술어(`wfcanon-v222.py`) 델타 — 신규 축

| # | 계약 | 신규 검사 |
|---|---|---|
| C-1 | :5618-5635 | PyYAML `yaml.compose()` 노드 순회로 **문서 전 매핑 노드**(최상위·중첩·**시퀀스 원소 `steps[i]`**) 중복 키 검출.  키 대조는 **compose 키 노드 `.value`** 위에서만.  **중복 통과 «후에만»** 비교 경로 진행 |
| C-1 벨트 | :5631 | 두 파서 `.value` 키 트리 불일치 → `UNVERIFIED_REVISION` |
| C-1 종료 보장 | **계약 공백(G4)** | 노드 «객체 identity» 방문집합으로 **순환 alias** 검출 → `UNVERIFIED_REVISION`.  계약은 «모든 매핑 노드 재귀» 라고만 적고 종료 보장도 미종료의 상태값도 주지 않는다(§12-d · EC-9) |
| M-4 | :5606-5613 | 파서 핀 `yq (mikefarah) v4.48.x` — `yq --version` 대조 · 불일치 = `PREVENTION_UNVERIFIABLE` · **`<<` merge key 존재 = `UNVERIFIED_REVISION`** |
| M-2 | :5644-5650 | 워크플로 최상위 allowlist `{name, run-name, on, permissions, jobs}` |
| M-1 | :5655-5658 | `on` ⊆ `{pull_request, push}`(list·map 양형) |
| F#4① | :5651-5654 | `permissions` 존재 강제 + 정확히 `{contents: read}` |
| F#4② | :5672-5675 | `runs-on` ∈ 허용 리터럴 «정확히 2개» `{ubuntu-latest, ubuntu-24.04}`(스칼라만) |
| F#4③ | :5680-5688 | 체크아웃 `with` 존재 강제 + 정확히 `{fetch-depth: 0, persist-credentials: false}` (**`fetch-depth` 는 bool 배제한 정수 0** · **`persist-credentials` 는 음극성이라 `is False` 만**) |
| F#2(ii) | :5659-5662 | `jobs` 정확히 1개 ∧ 잡 id == `tos-gate` |
| F#2(i-b) | :5665-5671 | 잡 `name` 존재 강제 + 값 == `tos-gate` |
| F#2(ii) 서버 | :5789-5793 | 이름 필터 `hit` 의 `len(hit) != 1` → `UNVERIFIED_REVISION` (v2.21 은 `hit[0]` 을 말없이 집었다) |
| 잡 키 | :5663-5664 | 게이트 잡 허용 키 닫힌 집합 `{name, runs-on, steps}` |
| F#1 | :5676-5747 | `steps` 정확히 3개·**순서 고정** [① 체크아웃 · ② 정본 B(검증) · ③ 정본 A(실행)] + 체크아웃 `uses` SHA 핀 + 3축 |
| F#1 축2 | :5758 | `continue-on-error` **키 자체 부재**(`false` 명시도 불허 — v2.21 은 `true` 만 거부했다) |

### 2-3. **코드 델타 «0» 인 축** (명시 요구 이행)

실측으로 확인한 것(§3 transcript):

| 축 | 근거 |
|---|---|
| `CANON_A` / `CANON_B` **내용** | v2.21 술어 상수와 **byte 동일 = True** (v2.22 가 바꾼 것은 «순서»뿐) |
| 두 스텝 `name:` 리터럴 | `tos-gate: run harness` · `tos-gate: verify harness sha256` — 계약 본문 각 1회 실재, byte 불변 |
| `normalize()` 정규화 규칙 | v2.21 함수와 **바이트코드 동일 = True** |
| `SHELL_OK` 3값 | v2.21 집합과 **동일 = True** — 계약 문언만 «생략부호 → 3값 명시»로 바뀌었고 술어 코드는 불변 |
| `IF_OK` 허용 집합 | v2.21 과 동일 리터럴 |
| `timeout-minutes != 0` | v2.21 과 동일 |
| 서버 층 잡 `conclusion == "success"` 리터럴 | **v2.21 이 이미 리터럴 대조**였다 — `skipped`/`neutral`/`cancelled`/`null` 은 그때도 배제됐다.  §13 R-1 이 두 술어 나란히 실측(10변형 중 `dupname` 만 갈린다) |
| 서버 층에 «정확히 3개» 미적용 | v2.21 도 적용하지 않았다 |
| 격리 스냅샷 · host 결속 C6 · PARENTS-UNTRUSTED ㉠㉡㉢ · SHALLOW · (a) 술어 · countersign · `P_first`/`P_last` E9/E11 · 연속성 α · 전순서 10단 · trap EXIT · responder seam | 훅 12개 밖 — `diff` 187행 전부가 위 표의 훅에 귀속 |

---

## 3. 정본 리터럴 결속

### 3-0. **추출 충실성 증명** — v2.21 원문이 정말 v2.21 원문인가

이 판의 모든 «v2.21 거동 그대로»·«v2.21 대조군» 주장의 유일한 근거다.
선행 판 §11 의 코드펜스에서 행 범위로 추출한 뒤 sha256 이 그 보고서가 «선언한» 값과 일치함을 보인다.

```text
$ R=docs/reviews/phase0-completion-contract/20260819-193235/U17-PREVENTION-CHECK-V221.md
$ sed -n '1985,2470p' "$R" > u17-verify-v221.sh    # §11-1 펜스 1985..2470
$ sed -n '2476,2634p' "$R" > wfcanon-v221.py       # §11-2 펜스 2476..2634
$ sed -n '2640,2718p' "$R" > mkwf-v221.py          # §11-3 펜스 2640..2718
$ sed -n '2724,2991p' "$R" > t84v221.sh            # §11-4 펜스 2724..2991
$ shasum -a 256 *
f0688051749c4ff4ff141a7dd2f148bc7256bd249b8c790762f7230a31e052f5  mkwf-v221.py
962cc027f88a9ff2adad807c08136132de8168e651c0a3006661fa6022bb9a72  t84v221.sh
5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727  u17-verify-v221.sh
a5430e1a593d890f19a36713b9577c15c807a12c4131d45bd2937744255b811d  wfcanon-v221.py
$ wc -l *
      79 mkwf-v221.py
     268 t84v221.sh
     486 u17-verify-v221.sh
     159 wfcanon-v221.py
```

| 스크립트 | 선행 판이 «선언한» sha256 | 추출 실측 | 행수 선언 / 실측 |
|---|---|---|---|
| `u17-verify-v221.sh` | `5410519e58afc9e2…fd4727` (§11-1) | **동일** | 486 / 486 |
| `wfcanon-v221.py` | `a5430e1a593d890f…5b811d` (§11-2) | **동일** | 159 / 159 |
| `mkwf-v221.py` | `f0688051749c4ff4…e052f5` (§11-3) | **동일** | 79 / 79 |
| `t84v221.sh` | `962cc027f88a9ff2…6022bb9a72` (§11-4 :2721) | **동일** | 268 / 268 |

**4/4 일치 · 첫 시도에서 일치**(펜스 경계·트레일링 개행 조정 0회).

### 3-1. 계약 코드펜스·본문 리터럴 == 술어 상수

```text
########## 3. 정본 리터럴 결속 — 계약 코드펜스·본문 리터럴 == 술어 상수 (byte 일치) ##########
  계약 :5714-5715 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  술어 CANON_A            = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'   → byte 동일? True
  v2.21 술어 CANON_A      = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'   → **v2.22 와 byte 동일? True**  (코드 델타 0 축)
  계약 :5725-5726 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  술어 CANON_B            = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"   → byte 동일? True
  v2.21 술어 CANON_B      = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"   → **v2.22 와 byte 동일? True**  (코드 델타 0 축)

  STEP_VER               술어='tos-gate: verify harness sha256'                          계약 본문 출현=1 :[5721]
  STEP_RUN               술어='tos-gate: run harness'                                    계약 본문 출현=1 :[5710]
  GATE_JOB               술어='tos-gate'                                                 계약 본문 출현=1 :[5279]
  CHECKOUT_USES          술어='actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' 계약 본문 출현=2 :[225, 5677]
  CHECKOUT_WITH          술어={'persist-credentials', 'fetch-depth'}                     계약 본문 출현=3 :[224, 4422, 5681]
  PERMS_EXACT            술어={'contents': 'read'}                                       계약 본문 출현=1 :[5651]
  RUNS_ON_OK             술어=['ubuntu-24.04', 'ubuntu-latest']                          계약 본문 출현=1 :[5672]
  TOP_ALLOW              술어=['jobs', 'name', 'on', 'permissions', 'run-name']          계약 본문 출현=4 :[224, 2903, 4422, 5644]
  JOB_ALLOW              술어=['name', 'runs-on', 'steps']                               계약 본문 출현=1 :[5663]
  SHELL_OK               술어=['bash', 'bash -eo pipefail {0}', 'bash -euo pipefail {0}'] 계약 본문 출현=1 :[5753]
  ON_ALLOW               술어=['pull_request', 'push']                                   계약 본문 출현=1 :[5655]
  IF_OK                  술어=['${{ success() }}', 'success()']                          계약 본문 출현=1 :[5759]
  YQ 파서 핀                술어='mikefarah v4.48.x'                                        계약 본문 출현=3 :[224, 4422, 5607]

  SHELL_OK v2.21 == v2.22 ? True   (계약 문언만 «생략부호 → 3값 명시»로 바뀌었고 술어 코드는 불변)
  normalize() v2.21 == v2.22 ? True   (코드 델타 0)
  ⇒ 모든 리터럴 계약 본문 실재 = True

  **정본 «순서»** — 계약 :5689 / :5708 원문:
    :5689 ② **정본 B 스텝(아래 (ii) — sha256 «검증»)** · ③ **정본 A 스텝(아래 (i) — 하니스 «실행»)**].
    :5708 워크플로 `steps` 의 실행 순서는 **② (ii) 정본 B(sha256 «검증») → ③ (i) 정본 A(하니스 «실행»)** 다.
```


**모든 리터럴이 계약 본문에 실재 = True.**  `GATE_JOB` 은 계약 :5279(«게이트 체크 이름 = `tos-gate`»)에서,
`CHECKOUT_USES` 는 :5677 에서, `SHELL_OK` 3값은 :5753 에서, 최상위 allowlist 는 :5644 에서 왔다.
정본 «순서»는 계약 :5689·:5708 원문을 그대로 인용했다 — **② 정본 B(검증) → ③ 정본 A(실행)**.

---

## 3-2. [G1] 정본 «잡 템플릿» 은 계약에 **코드펜스가 없다** — 비교 피연산자는 «재-파생»이다

**양방향 실측**: 계약 7,912행에서 `^[[:space:]]*jobs:` 는 **0건**이고, 문자열 `jobs` 자체는 **21행**에
실재한다(부재가 팬텀이 아님을 반대 방향으로 고정).  yaml 코드펜스는 `:3865`(무관)·`:5968`
(countersign 형식) **둘뿐**이며, «정본 잡 템플릿» 7회(`:225 :2903 :5605 :5643 :5841 :6033 :6087`)는
**전부 지시적 산문**이다.  **byte 로 핀된 것은 정본 A(`:5713-5716`)·정본 B(`:5724-5727`) =
run «본문» 둘뿐이다.**

⇒ 그러므로 이 판의 `(b)③` 는 **«정본 템플릿과의 byte 대조»가 아니다.**  산문 불릿
(`:5644-5700` · `:5752-5762`)에서 **재-파생(re-derivation)** 한 검사들의 논리곱이다.
그 재-파생 산물을 독립 아티팩트로 실체화하고 각 줄의 계약 근거와 **판단이 개입한 자리**를 병기한다:

- 산물: `canon-job-template.reconstructed.yml` — **sha256 `4a4e1f1f46ad7fde126a29fcfb8820ff65254e1f47fc10049caceff3f59befe3`** · 21행 · 639바이트
- 성격: **re-derivation (산문 → 구조), NOT byte comparison**
- **독립 수렴**: 이 재구성은 픽스처 생성기(`mkwf-v222.py`)를 import 하지 않고 **따로 재타이핑**했는데
  `fx/pos-canonical.yml` 과 **byte 동일**로 수렴했다 — 두 경로가 같은 산문을 같게 읽었다는 관측.
- **양성 앵커**: 재구성본에 대한 술어 판정 = `BLOB_OK`.
- **판단이 개입한 자리 5곳**(전부 §14 에라타 후보로 등재): `on ⊆` 의 좌변(EC-4) · 체크아웃 스텝의
  `name:` 부재(EC-3) · `if:` 의 좁은 쪽 채택(EC-1) · `runs-on` 두 허용값 중 첫째 선택 ·
  최상위 `name`/`run-name` 의 «선택» 해석.

```text
########## 3-2. [G1] 정본 «잡 템플릿» 재-파생 — 계약에 이 펜스는 «존재하지 않는다» ##########
-- 양방향 실측: 계약 7,912행에 «^[[:space:]]*jobs:» 는 몇 건인가 --
  grep -cE '^[[:space:]]*jobs:'  → 0   (부재)
  grep -c  'jobs'               → 21   (대조군 — 문자열 자체는 실재하므로 «부재»가 팬텀이 아니다)
  yaml 코드펜스 위치                    → 3865 5968    (:3865 무관 · :5968 countersign 형식)
  «정본 잡 템플릿» 산문 출현            → 225 2903 5605 5643 5841 6033 6087 
  ⇒ byte 로 핀된 것은 정본 A(:5713-5716)·정본 B(:5724-5727) = run «본문» 둘뿐이다

[G1] 정본 잡 템플릿 **재-파생본** → canon-job-template.reconstructed.yml
     sha256 = 4a4e1f1f46ad7fde126a29fcfb8820ff65254e1f47fc10049caceff3f59befe3 · 21행 · 639바이트
     **성격 = re-derivation(산문→구조), NOT byte comparison.**  계약에 이 펜스는 «존재하지 않는다».

  YAML 요소                                      계약 근거            성격 / 판단이 개입한 자리
  최상위 키 집합                                     :5644            닫힌 allowlist `{name, run-name, on, permissions, jobs}`
                                                                  ↳ 판단: `name`·`run-name` 은 **선택**이다(밖이 아니면 통과) — 재구성본은 `name` 만 둔다
  `on: [pull_request]`                         :5655            `on` ⊆ `{pull_request, push}` · list·map 양형
                                                                  ↳ 판단: **⊆ 의 좌변이 «키 집합»인지 미규정** — 키 집합으로 읽었다(EC-4)
  `permissions: {contents: read}`              :5651-5654       존재 강제 + **정확히** 그 값
  `jobs` 1개 · 잡 id `tos-gate`                  :5659-5662       «정확히 1개» ∧ 키 == 계약 리터럴
  잡 키 = `{name, runs-on, steps}`               :5663-5664       닫힌 집합
  `name: tos-gate`                             :5665-5671       존재 강제 + 값-핀
  `runs-on: ubuntu-latest`                     :5672-5675       허용 «정확히 2개» 중 하나 · 스칼라만
                                                                  ↳ 판단: 재구성본은 첫째 값을 쓴다(`ubuntu-24.04` 도 정본 — `ctrl-runs-on-2404` 가 대조)
  `steps` 3개·순서 고정                             :5676-5689       [① 체크아웃 · ② 정본 B · ③ 정본 A]
                                                                  ↳ 판단: **v2.22 가 반전한 축** — :5689·:5708 이 «② 정본 B → ③ 정본 A» 를 명시
  `uses: actions/checkout@3d3c…`               :5677-5679       허용 SHA = 이 1개 계약 리터럴 핀
  체크아웃 키 = `{uses, with}`                      :5680            닫힌 키
                                                                  ↳ 판단: **체크아웃 스텝의 `name:` 부재가 문언에 명시돼 있지 않다** — 닫힌 키에서 «파생»했다(EC-3)
  `with: {fetch-depth: 0, persist-credentials: false}` :5680-5688       존재 강제 + **정확히** 그 값
                                                                  ↳ 판단: `fetch-depth` 는 bool 배제 정수 0 · `persist-credentials` 는 음극성이라 `is False` 만(파이썬 등가 함정)
  스텝 ② `name` 리터럴                              :5721            계약 리터럴 (byte 불변)
  스텝 ② `run` 본문                                :5724-5727       **계약 코드펜스 = 정본 B (byte 핀)**
                                                                  ↳ 판단: **여기만 byte 대조다** — 나머지는 전부 재-파생
  스텝 ③ `name` 리터럴                              :5710            계약 리터럴 (byte 불변)
  스텝 ③ `run` 본문                                :5713-5716       **계약 코드펜스 = 정본 A (byte 핀)**
                                                                  ↳ 판단: **여기만 byte 대조다**
  run 스텝 메타                                    :5752-5762       `{name, run}` + 선택 `{shell, timeout-minutes}` · `continue-on-error` 키 부재
                                                                  ↳ 판단: **`if:` 는 :5759 가 «허용 값 집합»을 주지만 :5762 닫힌 집합엔 없다 — 좁은 쪽(부재)을 따랐다(EC-1)**
  `|` literal block scalar 표기                  :5750            에라타 ⓐ/E1 — `>` folded 는 접혀 불일치

  독립 재타이핑 vs 픽스처 생성기 `mkwf-v222.py` 의 `pos-canonical.yml` → **byte 동일 = True**
  재-파생본에 대한 술어 판정 = RESULT=BLOB_OK   (양성 앵커 — 재구성이 자기 술어와 정합)
```


---

## 4. [항목 1] per-d 결속 반례 — 두 층이 서로 다른 객체를 집는다

**자리**: blob 층은 «잡 id» 로, 서버 층은 «표시 이름» 으로 게이트 잡을 고른다.
정본 `jobs.tos-gate` 의 표시 이름을 다른 값으로 두고 `name: tos-gate` 인 형제 잡을 더하면
**required check 와 서버 스텝이 우회 잡에서 나온다.**

| 하위 | 구성 | 기대 v2.22 | 실측 v2.22 | **대조군 v2.21** | 실측 v2.21 |
|---|---|---|---|---|---|
| 1-A | `jobs.tos-gate`(name `gate (canonical)`·정본 steps) + `jobs.evil`(name `tos-gate`·무해 steps) · 서버 jobs 도 두 표시 이름 | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION` · rc 1** | `PREVENTION_ACTIVE` | **`PREVENTION_ACTIVE` · rc 0** |
| 1-B | 서버 층 단독 — `name: tos-gate` 인 잡 2개(⑭ㄱ) | `UNVERIFIED_REVISION` | **`UNVERIFIED_REVISION`** | `SERVER_OK` | **`SERVER_OK`** |
| 1-C | **N-11** — `(b-blob)@d` 비정본(v2.21 순서) + `(b-blob)@target` 정본 | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION` · rc 1**  (`@target`=OK · `@d`=red) | — | — |

**기대 ≠ 실측 = 0건.**
1-C 가 «`(b-blob)@target` 이 `(b-blob)@d` 의 «추가»이지 «대체»가 아니다»(N-11)를 실행으로 고정한다 —
대체였다면 이 구성이 `PREVENTION_ACTIVE` 를 냈을 것이다.

```text
########## 4. [항목 1] per-d 결속 반례 — 두 층이 서로 다른 객체를 집는다 (blob=잡 id · 서버=표시 이름) ##########

---------- 1-A  형제 잡: jobs.tos-gate(표시 이름 «gate (canonical)») + jobs.evil(name: tos-gate) ----------
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: gate (canonical)
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |   evil:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: verify harness sha256"
  |         run: true
  |       - name: "tos-gate: run harness"
  |         run: true

>>> 대조군: v2.21 실행기 (기대 = PREVENTION_ACTIVE — 두 층이 다른 객체를 집는다)
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture
  1d8396a D0-A: introduce config/tos_completion.yaml
  2ad8ecc W: add .github/workflows/tos-gate.yml (SIMULATED)
  c1dd1f2 P: D0A-PREVENTION-CONTROL (SIMULATED)
  8c3b686 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/split bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/split/.git/info/grafts=no · is_shallow=false · entry HEAD=1d8396ab9539b46736b740db093794970c3795e8
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/split /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.K5xG4GLdDA/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=1d8396ab9539b46736b740db093794970c3795e8 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.K5xG4GLdDA/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/split capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ppH801I3oZ
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/split — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.K5xG4GLdDA/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.K5xG4GLdDA/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/split/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-20T10:44:24Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-20T10:44:24Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:44:24Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-20T10:44:25Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-20T10:44:25Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-20T10:44:25Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[c1dd1f20f07d6338b3ca1e1e04762f55c4b03131 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[c1dd1f20f07d6338b3ca1e1e04762f55c4b03131 ] |D|=1 D=[1d8396ab9539b46736b740db093794970c3795e8 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.K5xG4GLdDA/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/1d8396ab9539b46736b740db093794970c3795e8/pulls  utc=2026-08-20T10:44:26Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/2ad8ecc35cd99f153359604b2e4381c673c722ab/check-runs  utc=2026-08-20T10:44:26Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab","check_suite":{"id":777001},"details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/111/job/1"},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab","check_suite":{"id":777001},"details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/424242/job/9424242"}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-20T10:44:26Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab","app":{"id":15368},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-20T10:44:26Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=2ad8ecc35cd99f153359604b2e4381c673c722ab  utc=2026-08-20T10:44:26Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "19371563a611cfc28a691480719d338282e1ca92", "size": 834, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1lOiBnYXRlIChjYW5vbmljYWwpCiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QDNkM2M0MmU1YWFjNWJhODA1ODI1ZGE3NjQxMGMxODEyNzNiYTkwYjEKICAgICAgICB3aXRoOgogICAgICAgICAgZmV0Y2gtZGVwdGg6IDAKICAgICAgICAgIHBlcnNpc3QtY3JlZGVudGlhbHM6IGZhbHNlCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgcHJpbnRmICclcyAgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2hcbicgOTU3YmY0OWRhOGZjNmFlMzlmOTdhYmU2Nzk0MTFhZmVhYTVhNTlmNzA3ZjM1YmYzYjNhOGM2ZjlkZTE0MWYwZCB8IHNoYXN1bSAtYSAyNTYgLWMgLQogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogcnVuIGhhcm5lc3MiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAogIGV2aWw6CiAgICBuYW1lOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3RlcHM6CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB0cnVlCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHRydWUK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@2ad8ecc35cd99f153359604b2e4381c673c722ab (encoding=base64 size=834):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: gate (canonical)
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |   evil:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: verify harness sha256"
  |         run: true
  |       - name: "tos-gate: run harness"
  |         run: true
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = [None, 'tos-gate: verify harness sha256', 'tos-gate: run harness']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-20T10:44:26Z  http=200  x-github-request-id=
  | {"total_count":2,"jobs":[{"id":900001,"run_id":424242,"name":"gate (canonical)","status":"completed","conclusion":"success","head_sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab","steps":[{"name":"Set up job","conclusion":"success"}]},{"id":900002,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab","steps":[{"name":"tos-gate: verify harness sha256","conclusion":"success"},{"name":"tos-gate: run harness","conclusion":"success"}]}]}
  | WF-S1 서버 jobs[] 이름 = ['gate (canonical)', 'tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('tos-gate: verify harness sha256', 'success'), ('tos-gate: run harness', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 2ad8ecc35cd99f153359604b2e4381c673c722ab:.github/workflows/tos-gate.yml → 19371563a611cfc28a691480719d338282e1ca92
U17-B d=1d8396ab9539b46736b740db093794970c3795e8 head=2ad8ecc35cd99f153359604b2e4381c673c722ab merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/split
u17_rc=0

>>> v2.22 실행기 (기대 = PREVENTION_UNVERIFIED_REVISION)
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture
  1d8396a D0-A: introduce config/tos_completion.yaml
  2ad8ecc W: add .github/workflows/tos-gate.yml (SIMULATED)
  c1dd1f2 P: D0A-PREVENTION-CONTROL (SIMULATED)
  8c3b686 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/split bash u17-verify-v222.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/split/.git/info/grafts=no · is_shallow=false · entry HEAD=1d8396ab9539b46736b740db093794970c3795e8
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/split /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.nMky066oEd/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=1d8396ab9539b46736b740db093794970c3795e8 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.nMky066oEd/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/split capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.aPibjqiOVs
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/split — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.nMky066oEd/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.nMky066oEd/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/split/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-20T10:44:28Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-20T10:44:28Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:44:28Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-20T10:44:28Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-20T10:44:28Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-20T10:44:28Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
U17-BT0 repos/kakao-harris-lee/kis_unified_sts/branches/main  utc=2026-08-20T10:44:28Z  http=200  x-github-request-id=
  | {"name":"main","commit":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1","url":"SIMULATED"}}
U17-BT [M-7] target HEAD sha = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)
U17-BT1 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1  utc=2026-08-20T10:44:28Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "19371563a611cfc28a691480719d338282e1ca92", "size": 834, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1lOiBnYXRlIChjYW5vbmljYWwpCiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QDNkM2M0MmU1YWFjNWJhODA1ODI1ZGE3NjQxMGMxODEyNzNiYTkwYjEKICAgICAgICB3aXRoOgogICAgICAgICAgZmV0Y2gtZGVwdGg6IDAKICAgICAgICAgIHBlcnNpc3QtY3JlZGVudGlhbHM6IGZhbHNlCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgcHJpbnRmICclcyAgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2hcbicgOTU3YmY0OWRhOGZjNmFlMzlmOTdhYmU2Nzk0MTFhZmVhYTVhNTlmNzA3ZjM1YmYzYjNhOGM2ZjlkZTE0MWYwZCB8IHNoYXN1bSAtYSAyNTYgLWMgLQogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogcnVuIGhhcm5lc3MiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAogIGV2aWw6CiAgICBuYW1lOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3RlcHM6CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB0cnVlCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHRydWUK\n"}
U17-BT1 decoded .github/workflows/tos-gate.yml@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 (target HEAD · encoding=base64 size=834):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: gate (canonical)
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |   evil:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: verify harness sha256"
  |         run: true
  |       - name: "tos-gate: run harness"
  |         run: true
  | WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
  | WF-D0 [G3] C-1 파서 = PyYAML 6.0.3 (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)
  | WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 0건 
  | WF-D2 [M-4] `<<` merge key = 0건 
  | WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
  | WF-D3 [C-1 벨트] 두 파서 `.value` 키 트리 일치 = True
  | WF-C0 판정 파서 = yq -o=json · 대조 = 정규화 후 byte 비교 · 대상 = 정본 «잡 템플릿» 전체
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-T1 [M-2] 최상위 키 = ['jobs', 'name', 'on', 'permissions'] · allowlist = ['jobs', 'name', 'on', 'permissions', 'run-name']
  | WF-T2 [F#4①] permissions = {'contents': 'read'}
  | WF-T3 [M-1] on = ['pull_request'] → 트리거 집합 ['pull_request']
  | WF-J1 [F#2ii] jobs 키 = ['evil', 'tos-gate'] (개수 2 · 요구 1) · 계약 리터럴 잡 id = 'tos-gate'
  | WF-J2 게이트 잡 키 = ['name', 'runs-on', 'steps'] · 닫힌 집합 = ['name', 'runs-on', 'steps']
  | WF-J3 [F#2i-b] 잡 name = 'gate (canonical)' · 계약 리터럴 = 'tos-gate'
  | WF-J4 [F#4②] runs-on = 'ubuntu-latest' · 허용 = ['ubuntu-24.04', 'ubuntu-latest']
  | WF-S1 [F#1] steps 개수 = 3 (요구 3·순서 고정) · 이름 = [None, 'tos-gate: verify harness sha256', 'tos-gate: run harness']
  | WF-S2 [①체크아웃] 키 = ['uses', 'with'] · uses = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' · with = {'fetch-depth': 0, 'persist-credentials': False}
  | WF-C3 [②B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [②B/verify sha256] 정본   = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [②B/verify sha256] byte 일치 = True
  | WF-C5 [②B/verify sha256] 스텝 키 = ['name', 'run'] · 닫힌 집합 = True
  | WF-C3 [③A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [③A/run harness] 정본   = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [③A/run harness] byte 일치 = True
  | WF-C5 [③A/run harness] 스텝 키 = ['name', 'run'] · 닫힌 집합 = True
  | WF-C5 위배: jobs 개수 = 2 ≠ 1 (형제 잡·anchor 복제)
  | WF-C5 위배: 잡 name = 'gate (canonical)' ≠ 계약 리터럴 'tos-gate' (blob 잡 id · 서버 표시 이름 분열)
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 · T-84 ⑬)
U17-BT (b-blob)@target 판정 = UNVERIFIED_REVISION   [무조건 항 · D 와 무관]
P_first(집합·|1|)=[c1dd1f20f07d6338b3ca1e1e04762f55c4b03131 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[c1dd1f20f07d6338b3ca1e1e04762f55c4b03131 ] |D|=1 D=[1d8396ab9539b46736b740db093794970c3795e8 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.nMky066oEd/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/1d8396ab9539b46736b740db093794970c3795e8/pulls  utc=2026-08-20T10:44:29Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/2ad8ecc35cd99f153359604b2e4381c673c722ab/check-runs  utc=2026-08-20T10:44:29Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab","check_suite":{"id":777001},"details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/111/job/1"},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab","check_suite":{"id":777001},"details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/424242/job/9424242"}]}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242  utc=2026-08-20T10:44:29Z  http=200  x-github-request-id=
  | {"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab","check_suite_id":777001,"conclusion":"success"}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-20T10:44:30Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"2ad8ecc35cd99f153359604b2e4381c673c722ab","app":{"id":15368},"status":"completed","conclusion":"success"}
U17-B2e [M-3] 동명(tos-gate) check-run 전수 열거 — 1건 (conclusion 으로 «먼저 거르지 않는다»):
  | check-run #0  conclusion=success  app_id==Actions=1  head_sha==PR head=1  suite=777001  run=424242  path=.github/workflows/tos-gate.yml
U17-B2e 정본 path(.github/workflows/tos-gate.yml) check-run = 1건 (요구 «정확히 1») · 그 conclusion = success · 동명·타 path 공존은 red 가 «아니다»((a) decoy 잔여·열거 기록만)
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=2ad8ecc35cd99f153359604b2e4381c673c722ab  utc=2026-08-20T10:44:30Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "19371563a611cfc28a691480719d338282e1ca92", "size": 834, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1lOiBnYXRlIChjYW5vbmljYWwpCiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QDNkM2M0MmU1YWFjNWJhODA1ODI1ZGE3NjQxMGMxODEyNzNiYTkwYjEKICAgICAgICB3aXRoOgogICAgICAgICAgZmV0Y2gtZGVwdGg6IDAKICAgICAgICAgIHBlcnNpc3QtY3JlZGVudGlhbHM6IGZhbHNlCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgcHJpbnRmICclcyAgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2hcbicgOTU3YmY0OWRhOGZjNmFlMzlmOTdhYmU2Nzk0MTFhZmVhYTVhNTlmNzA3ZjM1YmYzYjNhOGM2ZjlkZTE0MWYwZCB8IHNoYXN1bSAtYSAyNTYgLWMgLQogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogcnVuIGhhcm5lc3MiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAogIGV2aWw6CiAgICBuYW1lOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3RlcHM6CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB0cnVlCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHRydWUK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@2ad8ecc35cd99f153359604b2e4381c673c722ab (encoding=base64 size=834):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: gate (canonical)
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |   evil:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: verify harness sha256"
  |         run: true
  |       - name: "tos-gate: run harness"
  |         run: true
  | WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
  | WF-D0 [G3] C-1 파서 = PyYAML 6.0.3 (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)
  | WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 0건 
  | WF-D2 [M-4] `<<` merge key = 0건 
  | WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
  | WF-D3 [C-1 벨트] 두 파서 `.value` 키 트리 일치 = True
  | WF-C0 판정 파서 = yq -o=json · 대조 = 정규화 후 byte 비교 · 대상 = 정본 «잡 템플릿» 전체
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-T1 [M-2] 최상위 키 = ['jobs', 'name', 'on', 'permissions'] · allowlist = ['jobs', 'name', 'on', 'permissions', 'run-name']
  | WF-T2 [F#4①] permissions = {'contents': 'read'}
  | WF-T3 [M-1] on = ['pull_request'] → 트리거 집합 ['pull_request']
  | WF-J1 [F#2ii] jobs 키 = ['evil', 'tos-gate'] (개수 2 · 요구 1) · 계약 리터럴 잡 id = 'tos-gate'
  | WF-J2 게이트 잡 키 = ['name', 'runs-on', 'steps'] · 닫힌 집합 = ['name', 'runs-on', 'steps']
  | WF-J3 [F#2i-b] 잡 name = 'gate (canonical)' · 계약 리터럴 = 'tos-gate'
  | WF-J4 [F#4②] runs-on = 'ubuntu-latest' · 허용 = ['ubuntu-24.04', 'ubuntu-latest']
  | WF-S1 [F#1] steps 개수 = 3 (요구 3·순서 고정) · 이름 = [None, 'tos-gate: verify harness sha256', 'tos-gate: run harness']
  | WF-S2 [①체크아웃] 키 = ['uses', 'with'] · uses = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' · with = {'fetch-depth': 0, 'persist-credentials': False}
  | WF-C3 [②B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [②B/verify sha256] 정본   = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [②B/verify sha256] byte 일치 = True
  | WF-C5 [②B/verify sha256] 스텝 키 = ['name', 'run'] · 닫힌 집합 = True
  | WF-C3 [③A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [③A/run harness] 정본   = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [③A/run harness] byte 일치 = True
  | WF-C5 [③A/run harness] 스텝 키 = ['name', 'run'] · 닫힌 집합 = True
  | WF-C5 위배: jobs 개수 = 2 ≠ 1 (형제 잡·anchor 복제)
  | WF-C5 위배: 잡 name = 'gate (canonical)' ≠ 계약 리터럴 'tos-gate' (blob 잡 id · 서버 표시 이름 분열)
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b-blob)@d d=1d8396ab9539b46736b740db093794970c3795e8 head=2ad8ecc35cd99f153359604b2e4381c673c722ab 정본 «잡 템플릿» 불일치 — 최상위 allowlist·jobs 개수·잡 키/name/runs-on·steps 순서·체크아웃 with·스텝 메타·중복 키 중 하나 이상 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 · T-84 ⑬) [수집 2건 중 전순서 최소]
u17_rc=1

---------- 1-B  서버 층 단독 — 표시 이름 «tos-gate» 인 잡이 2개 (⑭ㄱ hit 비-유일) ----------
  기대 v2.22 = UNVERIFIED_REVISION · 대조군 v2.21 = SERVER_OK(hit[0] 을 말없이 집는다)
  v2.22: RESULT=UNVERIFIED_REVISION
  v2.21: RESULT=SERVER_OK
    WF-S1 서버 jobs[] 이름 = ['tos-gate', 'tos-gate']
    WF-S1 [F#2ii] 이름 필터 hit = 2건 (요구 정확히 1)
    WF-S2 len(hit)=2 != 1 → UNVERIFIED_REVISION (v2.21 은 hit[0] 을 말없이 집었다)
    RESULT=UNVERIFIED_REVISION

---------- 1-C  per-리비전 결속 (N-11) — PR head 는 «비정본» · target 은 «정본» ⇒ 여전히 차단 ----------
  ⇒ (b-blob)@target 이 (b-blob)@d 를 «대체»하면 이 구성이 통과한다 — «추가»임을 실증한다
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture
  4d1473c D0-A: introduce config/tos_completion.yaml
  172f013 W: add .github/workflows/tos-gate.yml (SIMULATED)
  3021df8 P: D0A-PREVENTION-CONTROL (SIMULATED)
  fd85043 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/perd bash u17-verify-v222.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/perd/.git/info/grafts=no · is_shallow=false · entry HEAD=4d1473c4ace813499bb8e470597f2794ae7183d2
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/perd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.V8epfgsbFC/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=4d1473c4ace813499bb8e470597f2794ae7183d2 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.V8epfgsbFC/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/perd capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Pw9CUUDuvM
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/perd — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.V8epfgsbFC/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.V8epfgsbFC/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/perd/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-20T10:44:32Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-20T10:44:32Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:44:32Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-20T10:44:32Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-20T10:44:32Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-20T10:44:32Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
U17-BT0 repos/kakao-harris-lee/kis_unified_sts/branches/main  utc=2026-08-20T10:44:32Z  http=200  x-github-request-id=
  | {"name":"main","commit":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1","url":"SIMULATED"}}
U17-BT [M-7] target HEAD sha = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)
U17-BT1 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1  utc=2026-08-20T10:44:32Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "ac58ad0b9c03a5756905aac185a28342c79b2f6f", "size": 639, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1lOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3RlcHM6CiAgICAgIC0gdXNlczogYWN0aW9ucy9jaGVja291dEAzZDNjNDJlNWFhYzViYTgwNTgyNWRhNzY0MTBjMTgxMjczYmE5MGIxCiAgICAgICAgd2l0aDoKICAgICAgICAgIGZldGNoLWRlcHRoOiAwCiAgICAgICAgICBwZXJzaXN0LWNyZWRlbnRpYWxzOiBmYWxzZQogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogdmVyaWZ5IGhhcm5lc3Mgc2hhMjU2IgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIHByaW50ZiAnJXMgIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoXG4nIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQgfCBzaGFzdW0gLWEgMjU2IC1jIC0KICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gK\n"}
U17-BT1 decoded .github/workflows/tos-gate.yml@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 (target HEAD · encoding=base64 size=639):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  | WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
  | WF-D0 [G3] C-1 파서 = PyYAML 6.0.3 (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)
  | WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 0건 
  | WF-D2 [M-4] `<<` merge key = 0건 
  | WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
  | WF-D3 [C-1 벨트] 두 파서 `.value` 키 트리 일치 = True
  | WF-C0 판정 파서 = yq -o=json · 대조 = 정규화 후 byte 비교 · 대상 = 정본 «잡 템플릿» 전체
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-T1 [M-2] 최상위 키 = ['jobs', 'name', 'on', 'permissions'] · allowlist = ['jobs', 'name', 'on', 'permissions', 'run-name']
  | WF-T2 [F#4①] permissions = {'contents': 'read'}
  | WF-T3 [M-1] on = ['pull_request'] → 트리거 집합 ['pull_request']
  | WF-J1 [F#2ii] jobs 키 = ['tos-gate'] (개수 1 · 요구 1) · 계약 리터럴 잡 id = 'tos-gate'
  | WF-J2 게이트 잡 키 = ['name', 'runs-on', 'steps'] · 닫힌 집합 = ['name', 'runs-on', 'steps']
  | WF-J3 [F#2i-b] 잡 name = 'tos-gate' · 계약 리터럴 = 'tos-gate'
  | WF-J4 [F#4②] runs-on = 'ubuntu-latest' · 허용 = ['ubuntu-24.04', 'ubuntu-latest']
  | WF-S1 [F#1] steps 개수 = 3 (요구 3·순서 고정) · 이름 = [None, 'tos-gate: verify harness sha256', 'tos-gate: run harness']
  | WF-S2 [①체크아웃] 키 = ['uses', 'with'] · uses = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' · with = {'fetch-depth': 0, 'persist-credentials': False}
  | WF-C3 [②B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [②B/verify sha256] 정본   = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [②B/verify sha256] byte 일치 = True
  | WF-C5 [②B/verify sha256] 스텝 키 = ['name', 'run'] · 닫힌 집합 = True
  | WF-C3 [③A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [③A/run harness] 정본   = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [③A/run harness] byte 일치 = True
  | WF-C5 [③A/run harness] 스텝 키 = ['name', 'run'] · 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-BT (b-blob)@target 판정 = OK   [무조건 항 · D 와 무관]
P_first(집합·|1|)=[3021df8f6e46451be950b4070bf81df59907c7c1 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[3021df8f6e46451be950b4070bf81df59907c7c1 ] |D|=1 D=[4d1473c4ace813499bb8e470597f2794ae7183d2 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.V8epfgsbFC/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/4d1473c4ace813499bb8e470597f2794ae7183d2/pulls  utc=2026-08-20T10:44:33Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"172f0138e9aad08670a7c3a5ddfcc2f28f0c21e6"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/172f0138e9aad08670a7c3a5ddfcc2f28f0c21e6/check-runs  utc=2026-08-20T10:44:34Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"172f0138e9aad08670a7c3a5ddfcc2f28f0c21e6","check_suite":{"id":777001},"details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/111/job/1"},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"172f0138e9aad08670a7c3a5ddfcc2f28f0c21e6","check_suite":{"id":777001},"details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/424242/job/9424242"}]}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242  utc=2026-08-20T10:44:34Z  http=200  x-github-request-id=
  | {"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"172f0138e9aad08670a7c3a5ddfcc2f28f0c21e6","check_suite_id":777001,"conclusion":"success"}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-20T10:44:34Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"172f0138e9aad08670a7c3a5ddfcc2f28f0c21e6","app":{"id":15368},"status":"completed","conclusion":"success"}
U17-B2e [M-3] 동명(tos-gate) check-run 전수 열거 — 1건 (conclusion 으로 «먼저 거르지 않는다»):
  | check-run #0  conclusion=success  app_id==Actions=1  head_sha==PR head=1  suite=777001  run=424242  path=.github/workflows/tos-gate.yml
U17-B2e 정본 path(.github/workflows/tos-gate.yml) check-run = 1건 (요구 «정확히 1») · 그 conclusion = success · 동명·타 path 공존은 red 가 «아니다»((a) decoy 잔여·열거 기록만)
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=172f0138e9aad08670a7c3a5ddfcc2f28f0c21e6  utc=2026-08-20T10:44:34Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "5c9dd00304fd8190aaf87699e73b113e3b961ecc", "size": 639, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1lOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3RlcHM6CiAgICAgIC0gdXNlczogYWN0aW9ucy9jaGVja291dEAzZDNjNDJlNWFhYzViYTgwNTgyNWRhNzY0MTBjMTgxMjczYmE5MGIxCiAgICAgICAgd2l0aDoKICAgICAgICAgIGZldGNoLWRlcHRoOiAwCiAgICAgICAgICBwZXJzaXN0LWNyZWRlbnRpYWxzOiBmYWxzZQogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogcnVuIGhhcm5lc3MiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogdmVyaWZ5IGhhcm5lc3Mgc2hhMjU2IgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIHByaW50ZiAnJXMgIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoXG4nIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQgfCBzaGFzdW0gLWEgMjU2IC1jIC0K\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@172f0138e9aad08670a7c3a5ddfcc2f28f0c21e6 (encoding=base64 size=639):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
  | WF-D0 [G3] C-1 파서 = PyYAML 6.0.3 (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)
  | WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 0건 
  | WF-D2 [M-4] `<<` merge key = 0건 
  | WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
  | WF-D3 [C-1 벨트] 두 파서 `.value` 키 트리 일치 = True
  | WF-C0 판정 파서 = yq -o=json · 대조 = 정규화 후 byte 비교 · 대상 = 정본 «잡 템플릿» 전체
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-T1 [M-2] 최상위 키 = ['jobs', 'name', 'on', 'permissions'] · allowlist = ['jobs', 'name', 'on', 'permissions', 'run-name']
  | WF-T2 [F#4①] permissions = {'contents': 'read'}
  | WF-T3 [M-1] on = ['pull_request'] → 트리거 집합 ['pull_request']
  | WF-J1 [F#2ii] jobs 키 = ['tos-gate'] (개수 1 · 요구 1) · 계약 리터럴 잡 id = 'tos-gate'
  | WF-J2 게이트 잡 키 = ['name', 'runs-on', 'steps'] · 닫힌 집합 = ['name', 'runs-on', 'steps']
  | WF-J3 [F#2i-b] 잡 name = 'tos-gate' · 계약 리터럴 = 'tos-gate'
  | WF-J4 [F#4②] runs-on = 'ubuntu-latest' · 허용 = ['ubuntu-24.04', 'ubuntu-latest']
  | WF-S1 [F#1] steps 개수 = 3 (요구 3·순서 고정) · 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-S2 [①체크아웃] 키 = ['uses', 'with'] · uses = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' · with = {'fetch-depth': 0, 'persist-credentials': False}
  | WF-C5 위배: [②B/verify sha256] 스텝 이름 = 'tos-gate: run harness' ≠ 계약 리터럴 'tos-gate: verify harness sha256'
  | WF-C5 위배: [③A/run harness] 스텝 이름 = 'tos-gate: verify harness sha256' ≠ 계약 리터럴 'tos-gate: run harness'
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b-blob)@d d=4d1473c4ace813499bb8e470597f2794ae7183d2 head=172f0138e9aad08670a7c3a5ddfcc2f28f0c21e6 정본 «잡 템플릿» 불일치 — 최상위 allowlist·jobs 개수·잡 키/name/runs-on·steps 순서·체크아웃 with·스텝 메타·중복 키 중 하나 이상 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b-blob)@d d=4d1473c4ace813499bb8e470597f2794ae7183d2 head=172f0138e9aad08670a7c3a5ddfcc2f28f0c21e6 정본 «잡 템플릿» 불일치 — 최상위 allowlist·jobs 개수·잡 키/name/runs-on·steps 순서·체크아웃 with·스텝 메타·중복 키 중 하나 이상 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1
```


---

## 5. [항목 2] 진입 비-vacuity — `D = ∅` 에서 blob limb 가 «실제로» 평가되는가

픽스처 저장소에 `config/tos_completion.yaml` 이 **없다** → `D = ∅` (진입선).

| 하위 | 구성 | 기대 | 실측 v2.22 | **대조군 v2.21** |
|---|---|---|---|---|
| 2-양성 | target 에 정본 워크플로 | `PREVENTION_ACTIVE` | **`PREVENTION_ACTIVE` · rc 0** · `(b-blob)@target` = OK | — |
| 2-음성-a | target 에 워크플로 **부재**(404) | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION` · rc 1** | **`PREVENTION_ACTIVE` · rc 0** |
| 2-음성-b | target blob 이 **이탈**(v2.21 순서) | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION` · rc 1** | **`PREVENTION_ACTIVE` · rc 0** |

**기대 ≠ 실측 = 0건.**

- 세 run 전부에서 `U17-BT0`(branches/main 조회) → **`U17-BT [M-7] target HEAD sha = …` 가 verbatim 수록**
  → `U17-BT1`(contents?ref=…) 이 transcript 에 실재한다.  «평가됐다»가 자기신고가 아니라
  **네 개의 관측 가능한 라인(HTTP 상태·요청 경로·디코드 본문·술어 판정)** 으로 남는다.
- 대조군 두 건이 심판 #3 의 지적을 그대로 재현한다: v2.21 은 같은 seam 에서
  `U17-B D=∅ — (b)(c) 검증 대상 없음` 을 찍고 **`PREVENTION_ACTIVE`** 를 냈다.
  워크플로 파일이 target 에 아예 없어도 green 이었다.
- **격하(정직 등재)**: 진입선이 얻는 것은 `(b-blob)@target` 뿐이다.  `(b-blob)@d`·`(b-server)` 는
  리비전·런이 물리적으로 없어 평가되지 않는다 — transcript 의 `U17-B D=∅ …` 라인이 그것을 명시한다.

```text
########## 5. [항목 2] 진입 비-vacuity — D = ∅ 에서 blob limb 가 «실제로 평가»되는가 ##########
  D0-A 산출물(config/tos_completion.yaml) 존재? NO ← D0-A 미착수 · D = ∅

---------- 2-양성  target 정본 ⇒ PREVENTION_ACTIVE ----------
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture
  93a7f89 W: add .github/workflows/tos-gate.yml (SIMULATED)
  0ef1447 P: D0A-PREVENTION-CONTROL (SIMULATED)
  5b3e4ac seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-pos bash u17-verify-v222.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry/.git/info/grafts=no · is_shallow=false · entry HEAD=93a7f89b404e781b5170019c5600d63c851833fe
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.w8ahZjDNDp/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=93a7f89b404e781b5170019c5600d63c851833fe · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.w8ahZjDNDp/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 3개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-pos capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.rFIzh3OQPU
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-pos — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.w8ahZjDNDp/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.w8ahZjDNDp/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-20T10:44:36Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-20T10:44:36Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:44:36Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-20T10:44:36Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-20T10:44:36Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-20T10:44:36Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
U17-BT0 repos/kakao-harris-lee/kis_unified_sts/branches/main  utc=2026-08-20T10:44:36Z  http=200  x-github-request-id=
  | {"name":"main","commit":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1","url":"SIMULATED"}}
U17-BT [M-7] target HEAD sha = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)
U17-BT1 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1  utc=2026-08-20T10:44:36Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "ac58ad0b9c03a5756905aac185a28342c79b2f6f", "size": 639, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1lOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3RlcHM6CiAgICAgIC0gdXNlczogYWN0aW9ucy9jaGVja291dEAzZDNjNDJlNWFhYzViYTgwNTgyNWRhNzY0MTBjMTgxMjczYmE5MGIxCiAgICAgICAgd2l0aDoKICAgICAgICAgIGZldGNoLWRlcHRoOiAwCiAgICAgICAgICBwZXJzaXN0LWNyZWRlbnRpYWxzOiBmYWxzZQogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogdmVyaWZ5IGhhcm5lc3Mgc2hhMjU2IgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIHByaW50ZiAnJXMgIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoXG4nIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQgfCBzaGFzdW0gLWEgMjU2IC1jIC0KICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gK\n"}
U17-BT1 decoded .github/workflows/tos-gate.yml@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 (target HEAD · encoding=base64 size=639):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  | WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
  | WF-D0 [G3] C-1 파서 = PyYAML 6.0.3 (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)
  | WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 0건 
  | WF-D2 [M-4] `<<` merge key = 0건 
  | WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
  | WF-D3 [C-1 벨트] 두 파서 `.value` 키 트리 일치 = True
  | WF-C0 판정 파서 = yq -o=json · 대조 = 정규화 후 byte 비교 · 대상 = 정본 «잡 템플릿» 전체
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-T1 [M-2] 최상위 키 = ['jobs', 'name', 'on', 'permissions'] · allowlist = ['jobs', 'name', 'on', 'permissions', 'run-name']
  | WF-T2 [F#4①] permissions = {'contents': 'read'}
  | WF-T3 [M-1] on = ['pull_request'] → 트리거 집합 ['pull_request']
  | WF-J1 [F#2ii] jobs 키 = ['tos-gate'] (개수 1 · 요구 1) · 계약 리터럴 잡 id = 'tos-gate'
  | WF-J2 게이트 잡 키 = ['name', 'runs-on', 'steps'] · 닫힌 집합 = ['name', 'runs-on', 'steps']
  | WF-J3 [F#2i-b] 잡 name = 'tos-gate' · 계약 리터럴 = 'tos-gate'
  | WF-J4 [F#4②] runs-on = 'ubuntu-latest' · 허용 = ['ubuntu-24.04', 'ubuntu-latest']
  | WF-S1 [F#1] steps 개수 = 3 (요구 3·순서 고정) · 이름 = [None, 'tos-gate: verify harness sha256', 'tos-gate: run harness']
  | WF-S2 [①체크아웃] 키 = ['uses', 'with'] · uses = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' · with = {'fetch-depth': 0, 'persist-credentials': False}
  | WF-C3 [②B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [②B/verify sha256] 정본   = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [②B/verify sha256] byte 일치 = True
  | WF-C5 [②B/verify sha256] 스텝 키 = ['name', 'run'] · 닫힌 집합 = True
  | WF-C3 [③A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [③A/run harness] 정본   = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [③A/run harness] byte 일치 = True
  | WF-C5 [③A/run harness] 스텝 키 = ['name', 'run'] · 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-BT (b-blob)@target 판정 = OK   [무조건 항 · D 와 무관]
P_first(집합·|1|)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.w8ahZjDNDp/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b-blob)@d·(b-server)·(c) 는 «D-지표 항»이라 평가 대상 없음.  **(b-blob)@target 은 위에서 «무조건 항»으로 이미 평가됐다**(v2.22·M-7 — v2.21 은 (b)(c) 를 통째로 접었다·심판 #3 vacuity)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ **(b-blob)@target=OK(무조건 항·target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1)** ∧ (b-blob)@d·(b-server) 전 리비전 검증(|D|=0) ∧ (α) 연속성 성립(t_land=∅) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-pos
u17_rc=0

---------- 2-음성-a  target 에 정본 파일 «부재»(404) ⇒ UNVERIFIED_REVISION (ABSENT 로 접지 않는다) ----------
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture
  93a7f89 W: add .github/workflows/tos-gate.yml (SIMULATED)
  0ef1447 P: D0A-PREVENTION-CONTROL (SIMULATED)
  5b3e4ac seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-404 bash u17-verify-v222.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry/.git/info/grafts=no · is_shallow=false · entry HEAD=93a7f89b404e781b5170019c5600d63c851833fe
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GKQ2BKm8eP/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=93a7f89b404e781b5170019c5600d63c851833fe · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GKQ2BKm8eP/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 3개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-404 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.FCCCdJ8VgY
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-404 — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GKQ2BKm8eP/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GKQ2BKm8eP/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-20T10:44:38Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-20T10:44:38Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:44:38Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-20T10:44:38Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-20T10:44:38Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-20T10:44:38Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
U17-BT0 repos/kakao-harris-lee/kis_unified_sts/branches/main  utc=2026-08-20T10:44:39Z  http=200  x-github-request-id=
  | {"name":"main","commit":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1","url":"SIMULATED"}}
U17-BT [M-7] target HEAD sha = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)
U17-BT1 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1  utc=2026-08-20T10:44:39Z  http=404  x-github-request-id=
  | {"message":"Not Found","status":"404"}
U17-fire PREVENTION_UNVERIFIED_REVISION: (b-blob)@target http=404 (.github/workflows/tos-gate.yml 가 target HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 에 부재) — ABSENT 로 접지 않는다(전순서 2 vs 8)
U17-BT (b-blob)@target 판정 = UNVERIFIED_REVISION   [무조건 항 · D 와 무관]
P_first(집합·|1|)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GKQ2BKm8eP/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b-blob)@d·(b-server)·(c) 는 «D-지표 항»이라 평가 대상 없음.  **(b-blob)@target 은 위에서 «무조건 항»으로 이미 평가됐다**(v2.22·M-7 — v2.21 은 (b)(c) 를 통째로 접었다·심판 #3 vacuity)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b-blob)@target http=404 (.github/workflows/tos-gate.yml 가 target HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 에 부재) — ABSENT 로 접지 않는다(전순서 2 vs 8) [수집 1건 중 전순서 최소]
u17_rc=1

---------- 2-음성-b  target blob 이 «이탈»(v2.21 순서) ⇒ UNVERIFIED_REVISION ----------
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture
  93a7f89 W: add .github/workflows/tos-gate.yml (SIMULATED)
  0ef1447 P: D0A-PREVENTION-CONTROL (SIMULATED)
  5b3e4ac seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-dev bash u17-verify-v222.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry/.git/info/grafts=no · is_shallow=false · entry HEAD=93a7f89b404e781b5170019c5600d63c851833fe
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OizKgBZs95/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=93a7f89b404e781b5170019c5600d63c851833fe · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OizKgBZs95/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 3개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-dev capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.k3EORjSXF7
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-dev — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OizKgBZs95/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OizKgBZs95/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-20T10:44:40Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-20T10:44:40Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:44:41Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-20T10:44:41Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-20T10:44:41Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-20T10:44:41Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
U17-BT0 repos/kakao-harris-lee/kis_unified_sts/branches/main  utc=2026-08-20T10:44:41Z  http=200  x-github-request-id=
  | {"name":"main","commit":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1","url":"SIMULATED"}}
U17-BT [M-7] target HEAD sha = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)
U17-BT1 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1  utc=2026-08-20T10:44:41Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "5c9dd00304fd8190aaf87699e73b113e3b961ecc", "size": 639, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1lOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3RlcHM6CiAgICAgIC0gdXNlczogYWN0aW9ucy9jaGVja291dEAzZDNjNDJlNWFhYzViYTgwNTgyNWRhNzY0MTBjMTgxMjczYmE5MGIxCiAgICAgICAgd2l0aDoKICAgICAgICAgIGZldGNoLWRlcHRoOiAwCiAgICAgICAgICBwZXJzaXN0LWNyZWRlbnRpYWxzOiBmYWxzZQogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogcnVuIGhhcm5lc3MiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogdmVyaWZ5IGhhcm5lc3Mgc2hhMjU2IgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIHByaW50ZiAnJXMgIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoXG4nIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQgfCBzaGFzdW0gLWEgMjU2IC1jIC0K\n"}
U17-BT1 decoded .github/workflows/tos-gate.yml@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 (target HEAD · encoding=base64 size=639):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
  | WF-D0 [G3] C-1 파서 = PyYAML 6.0.3 (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)
  | WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 0건 
  | WF-D2 [M-4] `<<` merge key = 0건 
  | WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
  | WF-D3 [C-1 벨트] 두 파서 `.value` 키 트리 일치 = True
  | WF-C0 판정 파서 = yq -o=json · 대조 = 정규화 후 byte 비교 · 대상 = 정본 «잡 템플릿» 전체
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-T1 [M-2] 최상위 키 = ['jobs', 'name', 'on', 'permissions'] · allowlist = ['jobs', 'name', 'on', 'permissions', 'run-name']
  | WF-T2 [F#4①] permissions = {'contents': 'read'}
  | WF-T3 [M-1] on = ['pull_request'] → 트리거 집합 ['pull_request']
  | WF-J1 [F#2ii] jobs 키 = ['tos-gate'] (개수 1 · 요구 1) · 계약 리터럴 잡 id = 'tos-gate'
  | WF-J2 게이트 잡 키 = ['name', 'runs-on', 'steps'] · 닫힌 집합 = ['name', 'runs-on', 'steps']
  | WF-J3 [F#2i-b] 잡 name = 'tos-gate' · 계약 리터럴 = 'tos-gate'
  | WF-J4 [F#4②] runs-on = 'ubuntu-latest' · 허용 = ['ubuntu-24.04', 'ubuntu-latest']
  | WF-S1 [F#1] steps 개수 = 3 (요구 3·순서 고정) · 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-S2 [①체크아웃] 키 = ['uses', 'with'] · uses = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' · with = {'fetch-depth': 0, 'persist-credentials': False}
  | WF-C5 위배: [②B/verify sha256] 스텝 이름 = 'tos-gate: run harness' ≠ 계약 리터럴 'tos-gate: verify harness sha256'
  | WF-C5 위배: [③A/run harness] 스텝 이름 = 'tos-gate: verify harness sha256' ≠ 계약 리터럴 'tos-gate: run harness'
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 · T-84 ⑬)
U17-BT (b-blob)@target 판정 = UNVERIFIED_REVISION   [무조건 항 · D 와 무관]
P_first(집합·|1|)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OizKgBZs95/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b-blob)@d·(b-server)·(c) 는 «D-지표 항»이라 평가 대상 없음.  **(b-blob)@target 은 위에서 «무조건 항»으로 이미 평가됐다**(v2.22·M-7 — v2.21 은 (b)(c) 를 통째로 접었다·심판 #3 vacuity)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 · T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1

---------- 2-대조군  같은 두 음성 seam 을 v2.21 실행기로 — (b)(c) 가 vacuous 인 채 ACTIVE 면 그것이 심판 #3 이 지적한 자리 ----------
>>> v2.21 × entry-404
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture
  93a7f89 W: add .github/workflows/tos-gate.yml (SIMULATED)
  0ef1447 P: D0A-PREVENTION-CONTROL (SIMULATED)
  5b3e4ac seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-404 bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry/.git/info/grafts=no · is_shallow=false · entry HEAD=93a7f89b404e781b5170019c5600d63c851833fe
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9uQOZ3nROA/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=93a7f89b404e781b5170019c5600d63c851833fe · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9uQOZ3nROA/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 3개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-404 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.0kyg70rARV
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-404 — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9uQOZ3nROA/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9uQOZ3nROA/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-20T10:44:43Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-20T10:44:43Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:44:43Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-20T10:44:43Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-20T10:44:43Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-20T10:44:43Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9uQOZ3nROA/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=0) ∧ (α) 연속성 성립(t_land=∅) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-404
u17_rc=0
>>> v2.21 × entry-dev
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture
  93a7f89 W: add .github/workflows/tos-gate.yml (SIMULATED)
  0ef1447 P: D0A-PREVENTION-CONTROL (SIMULATED)
  5b3e4ac seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-dev bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry/.git/info/grafts=no · is_shallow=false · entry HEAD=93a7f89b404e781b5170019c5600d63c851833fe
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2bcseDW60d/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=93a7f89b404e781b5170019c5600d63c851833fe · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2bcseDW60d/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 3개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-dev capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.rdJFZMYPWP
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-dev — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2bcseDW60d/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2bcseDW60d/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/entry/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-20T10:44:45Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-20T10:44:45Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:44:45Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-20T10:44:45Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-20T10:44:45Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-20T10:44:45Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2bcseDW60d/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=0) ∧ (α) 연속성 성립(t_land=∅) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/entry-dev
u17_rc=0
```


---

## 6. [항목 3] C-1 두 순서 — 잡 «안» `steps:` 중복

| 픽스처 | 순서 | 기대 v2.22 | 실측 v2.22 | **대조군 v2.21** |
|---|---|---|---|---|
| `c1-dupsteps-benign-first` | [무해 먼저, 정본 나중] | `UNVERIFIED_REVISION` | **`UNVERIFIED_REVISION`** | **`BLOB_OK`** ← 열린 자리 |
| `c1-dupsteps-canon-first` | [정본 먼저, 무해 나중] | `UNVERIFIED_REVISION` | **`UNVERIFIED_REVISION`** | `UNVERIFIED_REVISION` |

**두 순서 모두 red** — 계약 :5635 의 ««우회-먼저»/«정본-먼저» 두 순서 모두 red 여야 한다» 이행.
검출 지점은 두 순서에서 **같다**: `WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 1건 ['$.jobs.tos-gate.steps']`.

**v2.21 의 비대칭이 중요하다**: v2.21 은 [정본 먼저] 를 «우연히» 잡았다 — `json.loads` last-wins 가
뒤 블록(무해)을 남겨 정본 대조가 깨졌기 때문이지, 중복을 검출해서가 아니다.
[무해 먼저] 에서는 같은 last-wins 가 정본을 남겨 **`BLOB_OK`** 가 됐다.
**«순서에 따라 결과가 갈리는 검출»은 검출이 아니다** — C-1 이 그 자리를 순서 무관하게 닫는다.

e2e 실행기 경로: v2.21 = `PREVENTION_ACTIVE` rc 0 / v2.22 = `PREVENTION_UNVERIFIED_REVISION` rc 1.

```text
########## 6. [항목 3] C-1 두 순서 — 잡 «안» steps: 중복 ##########

---------- c1-dupsteps-benign-first ----------
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: verify harness sha256"
  |         run: true
  |       - name: "tos-gate: run harness"
  |         run: true
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  v2.22 = UNVERIFIED_REVISION
  v2.21 = BLOB_OK
    WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 1건 ['$.jobs.tos-gate.steps']
    WF-D2 [M-4] `<<` merge key = 0건 
    WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
    WF-D1 중복 키 검출 → UNVERIFIED_REVISION (정본 잡 대조·서버 대조로 진행하지 «않는다»)

---------- c1-dupsteps-canon-first ----------
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |     steps:
  |       - name: "tos-gate: verify harness sha256"
  |         run: true
  |       - name: "tos-gate: run harness"
  |         run: true
  v2.22 = UNVERIFIED_REVISION
  v2.21 = UNVERIFIED_REVISION
    WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 1건 ['$.jobs.tos-gate.steps']
    WF-D2 [M-4] `<<` merge key = 0건 
    WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
    WF-D1 중복 키 검출 → UNVERIFIED_REVISION (정본 잡 대조·서버 대조로 진행하지 «않는다»)

---------- 3-e2e  «무해 먼저» 를 실행기로 (v2.21 = ACTIVE / v2.22 = 차단) ----------
>>> v2.21
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture
  5a3dfb8 D0-A: introduce config/tos_completion.yaml
  9dbee19 W: add .github/workflows/tos-gate.yml (SIMULATED)
  91185db P: D0A-PREVENTION-CONTROL (SIMULATED)
  fcc1432 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/dup bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/dupsteps/.git/info/grafts=no · is_shallow=false · entry HEAD=5a3dfb8a593313bfad72556e13ce87c8d1b229df
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/dupsteps /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Fcuz0BenkN/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=5a3dfb8a593313bfad72556e13ce87c8d1b229df · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Fcuz0BenkN/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/dup capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.hCUOTrpnZx
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/dup — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Fcuz0BenkN/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Fcuz0BenkN/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/dupsteps/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-20T10:44:48Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-20T10:44:48Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:44:48Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-20T10:44:48Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-20T10:44:48Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-20T10:44:48Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[91185db8630eef098d7295da05671f99a0a31283 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[91185db8630eef098d7295da05671f99a0a31283 ] |D|=1 D=[5a3dfb8a593313bfad72556e13ce87c8d1b229df ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Fcuz0BenkN/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/5a3dfb8a593313bfad72556e13ce87c8d1b229df/pulls  utc=2026-08-20T10:44:49Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"9dbee1989a1a923c20d958686350da10a8bfb1df"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/9dbee1989a1a923c20d958686350da10a8bfb1df/check-runs  utc=2026-08-20T10:44:49Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"9dbee1989a1a923c20d958686350da10a8bfb1df","check_suite":{"id":777001},"details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/111/job/1"},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"9dbee1989a1a923c20d958686350da10a8bfb1df","check_suite":{"id":777001},"details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/424242/job/9424242"}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-20T10:44:49Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"9dbee1989a1a923c20d958686350da10a8bfb1df","app":{"id":15368},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-20T10:44:49Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"9dbee1989a1a923c20d958686350da10a8bfb1df","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=9dbee1989a1a923c20d958686350da10a8bfb1df  utc=2026-08-20T10:44:50Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "ec0f812f5fc9dec0596df2adcf2e0216494dad1e", "size": 772, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1lOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3RlcHM6CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB0cnVlCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHRydWUKICAgIHN0ZXBzOgogICAgICAtIHVzZXM6IGFjdGlvbnMvY2hlY2tvdXRAM2QzYzQyZTVhYWM1YmE4MDU4MjVkYTc2NDEwYzE4MTI3M2JhOTBiMQogICAgICAgIHdpdGg6CiAgICAgICAgICBmZXRjaC1kZXB0aDogMAogICAgICAgICAgcGVyc2lzdC1jcmVkZW50aWFsczogZmFsc2UKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAtCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBiYXNoIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoCg==\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@9dbee1989a1a923c20d958686350da10a8bfb1df (encoding=base64 size=772):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: verify harness sha256"
  |         run: true
  |       - name: "tos-gate: run harness"
  |         run: true
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = [None, 'tos-gate: verify harness sha256', 'tos-gate: run harness']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-20T10:44:50Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"9dbee1989a1a923c20d958686350da10a8bfb1df","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":2},{"name":"tos-gate: run harness","conclusion":"success","number":3},{"name":"Complete job","conclusion":"success","number":4}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: verify harness sha256', 'success'), ('tos-gate: run harness', 'success'), ('Complete job', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 9dbee1989a1a923c20d958686350da10a8bfb1df:.github/workflows/tos-gate.yml → ec0f812f5fc9dec0596df2adcf2e0216494dad1e
U17-B d=5a3dfb8a593313bfad72556e13ce87c8d1b229df head=9dbee1989a1a923c20d958686350da10a8bfb1df merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/dup
u17_rc=0
>>> v2.22
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture
  5a3dfb8 D0-A: introduce config/tos_completion.yaml
  9dbee19 W: add .github/workflows/tos-gate.yml (SIMULATED)
  91185db P: D0A-PREVENTION-CONTROL (SIMULATED)
  fcc1432 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/dup bash u17-verify-v222.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/dupsteps/.git/info/grafts=no · is_shallow=false · entry HEAD=5a3dfb8a593313bfad72556e13ce87c8d1b229df
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/dupsteps /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.p5swHq4A8j/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=5a3dfb8a593313bfad72556e13ce87c8d1b229df · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.p5swHq4A8j/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/dup capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.oq8dpnzHgz
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/dup — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.p5swHq4A8j/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.p5swHq4A8j/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/dupsteps/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-20T10:44:51Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-20T10:44:51Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:44:51Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-20T10:44:51Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-20T10:44:51Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-20T10:44:52Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
U17-BT0 repos/kakao-harris-lee/kis_unified_sts/branches/main  utc=2026-08-20T10:44:52Z  http=200  x-github-request-id=
  | {"name":"main","commit":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1","url":"SIMULATED"}}
U17-BT [M-7] target HEAD sha = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)
U17-BT1 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1  utc=2026-08-20T10:44:52Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "ec0f812f5fc9dec0596df2adcf2e0216494dad1e", "size": 772, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1lOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3RlcHM6CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB0cnVlCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHRydWUKICAgIHN0ZXBzOgogICAgICAtIHVzZXM6IGFjdGlvbnMvY2hlY2tvdXRAM2QzYzQyZTVhYWM1YmE4MDU4MjVkYTc2NDEwYzE4MTI3M2JhOTBiMQogICAgICAgIHdpdGg6CiAgICAgICAgICBmZXRjaC1kZXB0aDogMAogICAgICAgICAgcGVyc2lzdC1jcmVkZW50aWFsczogZmFsc2UKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAtCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBiYXNoIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoCg==\n"}
U17-BT1 decoded .github/workflows/tos-gate.yml@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 (target HEAD · encoding=base64 size=772):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: verify harness sha256"
  |         run: true
  |       - name: "tos-gate: run harness"
  |         run: true
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  | WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
  | WF-D0 [G3] C-1 파서 = PyYAML 6.0.3 (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)
  | WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 1건 ['$.jobs.tos-gate.steps']
  | WF-D2 [M-4] `<<` merge key = 0건 
  | WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
  | WF-D1 중복 키 검출 → UNVERIFIED_REVISION (정본 잡 대조·서버 대조로 진행하지 «않는다»)
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 · T-84 ⑬)
U17-BT (b-blob)@target 판정 = UNVERIFIED_REVISION   [무조건 항 · D 와 무관]
P_first(집합·|1|)=[91185db8630eef098d7295da05671f99a0a31283 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[91185db8630eef098d7295da05671f99a0a31283 ] |D|=1 D=[5a3dfb8a593313bfad72556e13ce87c8d1b229df ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.p5swHq4A8j/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/5a3dfb8a593313bfad72556e13ce87c8d1b229df/pulls  utc=2026-08-20T10:44:53Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"9dbee1989a1a923c20d958686350da10a8bfb1df"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/9dbee1989a1a923c20d958686350da10a8bfb1df/check-runs  utc=2026-08-20T10:44:53Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"9dbee1989a1a923c20d958686350da10a8bfb1df","check_suite":{"id":777001},"details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/111/job/1"},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"9dbee1989a1a923c20d958686350da10a8bfb1df","check_suite":{"id":777001},"details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/424242/job/9424242"}]}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242  utc=2026-08-20T10:44:53Z  http=200  x-github-request-id=
  | {"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"9dbee1989a1a923c20d958686350da10a8bfb1df","check_suite_id":777001,"conclusion":"success"}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-20T10:44:53Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"9dbee1989a1a923c20d958686350da10a8bfb1df","app":{"id":15368},"status":"completed","conclusion":"success"}
U17-B2e [M-3] 동명(tos-gate) check-run 전수 열거 — 1건 (conclusion 으로 «먼저 거르지 않는다»):
  | check-run #0  conclusion=success  app_id==Actions=1  head_sha==PR head=1  suite=777001  run=424242  path=.github/workflows/tos-gate.yml
U17-B2e 정본 path(.github/workflows/tos-gate.yml) check-run = 1건 (요구 «정확히 1») · 그 conclusion = success · 동명·타 path 공존은 red 가 «아니다»((a) decoy 잔여·열거 기록만)
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=9dbee1989a1a923c20d958686350da10a8bfb1df  utc=2026-08-20T10:44:53Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "ec0f812f5fc9dec0596df2adcf2e0216494dad1e", "size": 772, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25zOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1lOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3RlcHM6CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB0cnVlCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHRydWUKICAgIHN0ZXBzOgogICAgICAtIHVzZXM6IGFjdGlvbnMvY2hlY2tvdXRAM2QzYzQyZTVhYWM1YmE4MDU4MjVkYTc2NDEwYzE4MTI3M2JhOTBiMQogICAgICAgIHdpdGg6CiAgICAgICAgICBmZXRjaC1kZXB0aDogMAogICAgICAgICAgcGVyc2lzdC1jcmVkZW50aWFsczogZmFsc2UKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAtCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBiYXNoIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoCg==\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@9dbee1989a1a923c20d958686350da10a8bfb1df (encoding=base64 size=772):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: verify harness sha256"
  |         run: true
  |       - name: "tos-gate: run harness"
  |         run: true
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  | WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
  | WF-D0 [G3] C-1 파서 = PyYAML 6.0.3 (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)
  | WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 1건 ['$.jobs.tos-gate.steps']
  | WF-D2 [M-4] `<<` merge key = 0건 
  | WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
  | WF-D1 중복 키 검출 → UNVERIFIED_REVISION (정본 잡 대조·서버 대조로 진행하지 «않는다»)
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b-blob)@d d=5a3dfb8a593313bfad72556e13ce87c8d1b229df head=9dbee1989a1a923c20d958686350da10a8bfb1df 정본 «잡 템플릿» 불일치 — 최상위 allowlist·jobs 개수·잡 키/name/runs-on·steps 순서·체크아웃 with·스텝 메타·중복 키 중 하나 이상 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 · T-84 ⑬) [수집 2건 중 전순서 최소]
u17_rc=1
```


---

## 7. [항목 4] C-1 시퀀스 내부 — `steps[i]` 매핑 안의 중복 키

| 픽스처 | 중복 위치 | 기대 | 실측 v2.22 | **대조군 v2.21** |
|---|---|---|---|---|
| `c1-dup-in-step-run` | **시퀀스 원소** `steps[2].run` ×2 | `UNVERIFIED_REVISION` | **`UNVERIFIED_REVISION`** | **`BLOB_OK`** |
| `c1-dup-in-step-name` | **시퀀스 원소** `steps[2].name` ×2 | `UNVERIFIED_REVISION` | **`UNVERIFIED_REVISION`** | **`BLOB_OK`** |
| `c1-dup-jobs` | 최상위 `jobs` ×2 | `UNVERIFIED_REVISION` | **`UNVERIFIED_REVISION`** | `UNVERIFIED_REVISION` |
| `c1-dup-permissions` | 최상위 `permissions` ×2 | `UNVERIFIED_REVISION` | **`UNVERIFIED_REVISION`** | **`BLOB_OK`** |
| `c1-dup-runs-on` | 잡 `runs-on` ×2 | `UNVERIFIED_REVISION` | **`UNVERIFIED_REVISION`** | **`BLOB_OK`** |

검출 경로는 전부 `WF-D1` 이고 귀속 경로가 노드 경로로 찍힌다(예 `['$.jobs.tos-gate.steps[2].run']`).
**시퀀스 원소 매핑까지 재귀한다**는 계약 :5625-5626 의 요구가 관측면으로 남는다.

```text
########## 7. [항목 4] C-1 시퀀스 내부 — steps[i] 매핑 안의 중복 키 ##########
  c1-dup-in-step-run       v2.22=UNVERIFIED_REVISION    v2.21=BLOB_OK               
  c1-dup-in-step-name      v2.22=UNVERIFIED_REVISION    v2.21=BLOB_OK               
  c1-dup-jobs              v2.22=UNVERIFIED_REVISION    v2.21=UNVERIFIED_REVISION   
  c1-dup-permissions       v2.22=UNVERIFIED_REVISION    v2.21=BLOB_OK               
  c1-dup-runs-on           v2.22=UNVERIFIED_REVISION    v2.21=BLOB_OK               

---------- 4-전문  c1-dup-in-step-run (시퀀스 원소 안의 중복 run:) ----------
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
  WF-D0 [G3] C-1 파서 = PyYAML 6.0.3 (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)
  WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 1건 ['$.jobs.tos-gate.steps[2].run']
  WF-D2 [M-4] `<<` merge key = 0건 
  WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
  WF-D1 중복 키 검출 → UNVERIFIED_REVISION (정본 잡 대조·서버 대조로 진행하지 «않는다»)
  RESULT=UNVERIFIED_REVISION
```


---

## 8. [항목 5] C-1 정직 워크플로 발산 0 + `construct`/`safe_load` 대조군

정직한 워크플로 7종(`on:` 리스트·맵·`yes`/`no`/`off`/`on`/`y`/`n` 키·`true`/`false` 키·
`~`/`null`/`Null`/`NULL` 키·숫자/8진수/sexagesimal 형태 키·본 계약 정본 자신)에서:

- **`.value` 키 트리 발산 = 0건 / 7** (기대 0 · 사전 기입) — 과잉 차단 없음.
- **대조군**: 같은 파일들을 `construct`(`safe_load`)로 비교하면 **7/7 전부 발산**한다.
  최상위 키가 `['name', 'on', 'jobs']`(compose `.value`) vs `["'jobs'", "'name'", 'True']`(safe_load) —
  **YAML 1.1 이 `on` 을 `True` 로 접는다.**  계약 :5628-5630 이 «`construct`/`safe_load` 로 키를 비교하는
  것은 금지» 라 적은 이유가 이 한 줄로 관측된다.
- «알려진 `on:` 외» 같은 **열거형 예외 조항 없이** 성립한다(S-6).

```text
########## 8. [항목 5] C-1 정직 워크플로 발산 0 + construct/safe_load 대조군 ##########
  id                     «.value» 트리 판정 설명
  honest-on-list         VALUE_OK       on: 을 리스트로 쓰는 정직한 워크플로
      KT dup=0 merge=0 cycle=0 · `.value` 트리 일치 = True · `construct`(safe_load) 트리 일치 = False
      KT 최상위 키 — compose `.value` = ['name', 'on', 'jobs']
      KT 최상위 키 — safe_load construct = ["'jobs'", "'name'", 'True']
  honest-on-map          VALUE_OK       on: 을 맵으로 쓰고 branches 필터
      KT dup=0 merge=0 cycle=0 · `.value` 트리 일치 = True · `construct`(safe_load) 트리 일치 = False
      KT 최상위 키 — compose `.value` = ['name', 'on', 'jobs']
      KT 최상위 키 — safe_load construct = ["'jobs'", "'name'", 'True']
  honest-yesno           VALUE_OK       YAML 1.1 이 bool 로 접는 키·값 다수 (yes/no/off/on/y/n)
      KT dup=0 merge=0 cycle=0 · `.value` 트리 일치 = True · `construct`(safe_load) 트리 일치 = False
      KT 최상위 키 — compose `.value` = ['name', 'on', 'env', 'jobs']
      KT 최상위 키 — safe_load construct = ["'env'", "'jobs'", "'name'", 'True']
  honest-truefalse       VALUE_OK       true/false 키와 값
      KT dup=0 merge=0 cycle=0 · `.value` 트리 일치 = True · `construct`(safe_load) 트리 일치 = False
      KT 최상위 키 — compose `.value` = ['name', 'on', 'env', 'jobs']
      KT 최상위 키 — safe_load construct = ["'env'", "'jobs'", "'name'", 'True']
  honest-null            VALUE_OK       null 계열 키 (~, null, Null, NULL)
      KT dup=0 merge=0 cycle=0 · `.value` 트리 일치 = True · `construct`(safe_load) 트리 일치 = False
      KT 최상위 키 — compose `.value` = ['name', 'on', 'env', 'jobs']
      KT 최상위 키 — safe_load construct = ["'env'", "'jobs'", "'name'", 'True']
  honest-numeric         VALUE_OK       숫자·8진수·sexagesimal 형태 키
      KT dup=0 merge=0 cycle=0 · `.value` 트리 일치 = True · `construct`(safe_load) 트리 일치 = False
      KT 최상위 키 — compose `.value` = ['name', 'on', 'env', 'jobs']
      KT 최상위 키 — safe_load construct = ["'env'", "'jobs'", "'name'", 'True']
  honest-realgate        VALUE_OK       본 계약 정본 워크플로 자신
      KT dup=0 merge=0 cycle=0 · `.value` 트리 일치 = True · `construct`(safe_load) 트리 일치 = False
      KT 최상위 키 — compose `.value` = ['name', 'on', 'permissions', 'jobs']
      KT 최상위 키 — safe_load construct = ["'jobs'", "'name'", "'permissions'", 'True']
  ⇒ 정직 워크플로 «.value» 키 트리 발산 = 0 건 (기대 0)

---------- 5-대조군 전문 — honest-yesno (yes/no/off/on 키) ----------
  | name: legacy
  | on: [push]
  | env:
  |   yes: a
  |   no: b
  |   off: c
  |   on: d
  |   y: e
  |   n: f
  | jobs:
  |   j:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - run: echo ok
  KT dup=0 merge=0 cycle=0 · `.value` 트리 일치 = True · `construct`(safe_load) 트리 일치 = False
  KT 최상위 키 — compose `.value` = ['name', 'on', 'env', 'jobs']
  KT 최상위 키 — safe_load construct = ["'env'", "'jobs'", "'name'", 'True']
  RESULT=VALUE_OK
```


---

## 9. [항목 6] F#1 3축 + «자기수복 하니스» 반사실 대조

### 9-A. 3축 (술어 단위 · 기대는 사전 기입)

| 픽스처 | 축 | 기대 | 실측 v2.22 | **대조군 v2.21** |
|---|---|---|---|---|
| `f1-if-always` | 축1 `if:` | `UNVERIFIED_REVISION` | **동일** | `UNVERIFIED_REVISION` |
| `f1-if-success` | 축1 — 명시 `if: success()` | `UNVERIFIED_REVISION` | **동일** | **`BLOB_OK`** |
| `f1-coe-true` | 축2 | `UNVERIFIED_REVISION` | **동일** | `UNVERIFIED_REVISION` |
| `f1-coe-false` | 축2 — `false` **명시** | `UNVERIFIED_REVISION` | **동일** | **`BLOB_OK`** ← v2.21 은 `true` 만 거부했다 |
| `f1-shell-sh` / `f1-shell-pwsh` | 축3 | `UNVERIFIED_REVISION` | **동일** | `UNVERIFIED_REVISION` |
| `f1-v221-order` | **순서** | `UNVERIFIED_REVISION` | **동일** | **`BLOB_OK`** ← 이 판의 핵심 |
| `f1-timeout-zero` | 메타 | `UNVERIFIED_REVISION` | **동일** | `UNVERIFIED_REVISION` |

`f1-if-success` 는 **에라타 후보 EC-1** 과 직결된다(§14).

### 9-B. «자기수복 하니스» 런타임 반사실 — **부작용으로 관측한다**

계약 :5690-5697 의 반례를 실제로 돌렸다.  비승인 하니스는 실행되면
① 마커 파일 `EVIL_EXECUTED` 를 남기고 ② **자기 파일을 정본 바이트로 덮고** ③ `exit 0` 한다.
두 스텝 순서만 바꿔 같은 워크스페이스에서 돌린다.

| 순서 | step② | step③ | **`EVIL_EXECUTED` 마커** | 종료 시 하니스 sha256 |
|---|---|---|---|---|
| **v2.21** [② 실행 → ③ 검증] | `run harness` → `EVIL: … self-healing…` **rc 0** | `verify sha256` → `OK` **rc 0** | **실재 — 비승인 바이트가 실행됐다** | `ab1df580…`(= 정본) |
| **v2.22** [② 검증 → ③ 실행] | `verify sha256` → `FAILED … did NOT match` **rc 1** | **미도달** | **부재 — 비승인 바이트가 실행되지 않았다** | `e67d57b4…`(= 비승인 그대로) |

- 정본(승인) 바이트 sha256 `ab1df58089c764501d07dfd000ae9b02ddcb46da1946a3475f5428c42d0ee90f`
- 비승인 하니스 초기 sha256 `e67d57b41108edc3b56a80bc69eb5ebc4ad3c6e62b0586d2bf92edf58f0ab25c`
- **자기신고가 아니다** — 판정은 마커 파일의 존재/부재와 각 스텝의 rc 로 내려간다.
- v2.21 순서에서는 **두 스텝이 모두 success 이고 정적 blob 도 정본**이라 v2.21 술어가 `BLOB_OK` 를 낸다
  (마지막 줄: v2.21 순서 blob → v2.22 술어 `UNVERIFIED_REVISION` / v2.21 술어 `BLOB_OK`).
  **정적 blob 은 같은 스텝 byte·같은 스텝 이름이며 다른 것은 «순서»뿐이다.**

**정직 경계**: 이 실증은 «순서가 도달성을 바꾼다»를 로컬 셸에서 보인 것이고,
GitHub 의 「실패 스텝 이후 skip」신뢰는 여전히 선언 잔여다(계약 :5747).

```text
########## 9. [항목 6] F#1 3축 + «자기수복 하니스» 반사실 대조 ##########

---------- 6-A  3축 — 술어 단위 (기대는 사전 기입) ----------
  f1-if-always         v2.22=UNVERIFIED_REVISION    v2.21=UNVERIFIED_REVISION   
  f1-if-success        v2.22=UNVERIFIED_REVISION    v2.21=BLOB_OK               
  f1-coe-true          v2.22=UNVERIFIED_REVISION    v2.21=UNVERIFIED_REVISION   
  f1-coe-false         v2.22=UNVERIFIED_REVISION    v2.21=BLOB_OK               
  f1-shell-sh          v2.22=UNVERIFIED_REVISION    v2.21=UNVERIFIED_REVISION   
  f1-shell-pwsh        v2.22=UNVERIFIED_REVISION    v2.21=UNVERIFIED_REVISION   
  f1-v221-order        v2.22=UNVERIFIED_REVISION    v2.21=BLOB_OK               
  f1-timeout-zero      v2.22=UNVERIFIED_REVISION    v2.21=UNVERIFIED_REVISION   

---------- 6-B  «자기수복 하니스» 런타임 실증 — 부작용(마커 파일)으로 관측한다 ----------
  정본(승인) 바이트 sha256      = ab1df58089c764501d07dfd000ae9b02ddcb46da1946a3475f5428c42d0ee90f
  비승인 하니스 초기 sha256     = e67d57b41108edc3b56a80bc69eb5ebc4ad3c6e62b0586d2bf92edf58f0ab25c   (≠ 정본 — 검증이 먼저면 여기서 비-0)
  --- v2.21 정본 순서 [② 실행 → ③ 검증]  (반사실) ---
  진입 시 하니스 sha256 = e67d57b41108edc3b56a80bc69eb5ebc4ad3c6e62b0586d2bf92edf58f0ab25c
  step② run harness   : EVIL: unapproved harness executed; self-healing to canonical bytes   [rc=0]
  step③ verify sha256 : tools/tos_entry_harness.sh: OK   [rc=0]
  ⇒ 부작용 관측(자기신고 아님): EVIL_EXECUTED 마커 = **실재 — 비승인 바이트가 실행됐다**
  ⇒ 종료 시 하니스 sha256 = ab1df58089c764501d07dfd000ae9b02ddcb46da1946a3475f5428c42d0ee90f
  --- v2.22 정본 순서 [② 검증 → ③ 실행] ---
  진입 시 하니스 sha256 = e67d57b41108edc3b56a80bc69eb5ebc4ad3c6e62b0586d2bf92edf58f0ab25c
  step② verify sha256 : tools/tos_entry_harness.sh: FAILED shasum: WARNING: 1 computed checksum did NOT match   [rc=1]
  step③ 미도달 (② 가 비-0 · set -euo pipefail 하 암묵 success() 게이트)
  ⇒ 부작용 관측(자기신고 아님): EVIL_EXECUTED 마커 = **부재 — 비승인 바이트가 실행되지 않았다**
  ⇒ 종료 시 하니스 sha256 = e67d57b41108edc3b56a80bc69eb5ebc4ad3c6e62b0586d2bf92edf58f0ab25c
  ⇒ 두 순서의 정적 blob 은 **같은 스텝 byte·같은 이름**이며 다른 것은 «순서»뿐이다:
     v2.21 순서 blob 판정: v2.22 술어=UNVERIFIED_REVISION / v2.21 술어=BLOB_OK
```


---

## 10. [항목 7] anchor · `<<` merge key · 파서 버전

| 픽스처/구성 | 기대 | 실측 v2.22 | **대조군 v2.21** | 검출 지점 |
|---|---|---|---|---|
| `m2-anchor-dup-job` (`&g`/`*g` 로 게이트 잡 복제) | `UNVERIFIED_REVISION` | **동일** | **`BLOB_OK`** | `WF-J1 jobs 키 = ['tos-gate','tos-gate-2'] (개수 2 · 요구 1)` — 계약 :5650 «anchor 는 yq 확장 + `jobs`=1 이 닫는다» 그대로 |
| `m2-anchor-alias-only` | `UNVERIFIED_REVISION` | **동일** | `UNVERIFIED_REVISION` | 최상위 allowlist(`x-base`) |
| `m2-merge-key` (`<<: *b`) | `UNVERIFIED_REVISION` | **동일** | **`BLOB_OK`** | `WF-D2 [M-4] '<<' merge key = 1건 ['$.jobs.tos-gate.<<']` |
| `yq --version` 위조(v3.4.1) | `UNVERIFIABLE` | **`UNVERIFIABLE`** | — | `WF-P0 … → 일치 False` → `WF-P1` |
| 핀 일치 `yq`(v4.48.1) | `BLOB_OK` | **`BLOB_OK`** | — | `WF-P0 … → 일치 True` |
| 파서 위조 **e2e**(실행기) | `PREVENTION_UNVERIFIABLE` | **`PREVENTION_UNVERIFIABLE` · rc 1** | — | 전순서 1 이 이긴다 |

anchor/alias 는 **compose 도 확장**하므로 `.value` 키 트리 벨트가 발산하지 않는다(`WF-D3 … 일치 = True`) —
닫는 것은 `jobs` 개수 1 이다.  계약의 «allowlist 는 anchor 방어가 아니다»(:5649)가 실측으로 확인된다.

```text
########## 10. [항목 7] anchor · «<<» merge key · 파서 버전 ##########

---------- m2-anchor-dup-job ----------
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate: &g
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |   tos-gate-2: *g
  v2.22=UNVERIFIED_REVISION  v2.21=BLOB_OK
    WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 0건 
    WF-D2 [M-4] `<<` merge key = 0건 
    WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
    WF-D3 [C-1 벨트] 두 파서 `.value` 키 트리 일치 = True
    WF-T1 [M-2] 최상위 키 = ['jobs', 'name', 'on', 'permissions'] · allowlist = ['jobs', 'name', 'on', 'permissions', 'run-name']
    WF-J1 [F#2ii] jobs 키 = ['tos-gate', 'tos-gate-2'] (개수 2 · 요구 1) · 계약 리터럴 잡 id = 'tos-gate'

---------- m2-anchor-alias-only ----------
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | x-base: &g
  |   name: tos-gate
  |   runs-on: ubuntu-latest
  |   steps:
  |     - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |       with:
  |         fetch-depth: 0
  |         persist-credentials: false
  | jobs:
  |   tos-gate: *g
  v2.22=UNVERIFIED_REVISION  v2.21=UNVERIFIED_REVISION
    WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 0건 
    WF-D2 [M-4] `<<` merge key = 0건 
    WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
    WF-D3 [C-1 벨트] 두 파서 `.value` 키 트리 일치 = True
    WF-T1 [M-2] 최상위 키 = ['jobs', 'name', 'on', 'permissions', 'x-base'] · allowlist = ['jobs', 'name', 'on', 'permissions', 'run-name']
    WF-J1 [F#2ii] jobs 키 = ['tos-gate'] (개수 1 · 요구 1) · 계약 리터럴 잡 id = 'tos-gate'

---------- m2-merge-key ----------
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | x-base: &b
  |   runs-on: ubuntu-latest
  | jobs:
  |   tos-gate:
  |     <<: *b
  |     name: tos-gate
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  v2.22=UNVERIFIED_REVISION  v2.21=BLOB_OK
    WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 0건 
    WF-D2 [M-4] `<<` merge key = 1건 ['$.jobs.tos-gate.<<']
    WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
    WF-D2 `<<` merge key 존재 자체가 금지 리터럴 → UNVERIFIED_REVISION

---------- 7-파서 버전 위조 — 가짜 yq 를 PATH 에 두고 --version 을 다른 메이저로 만든다 ----------
  실제 yq = /opt/homebrew/bin/yq
  | #!/bin/sh
  | if [ "$1" = "--version" ]; then echo "yq (https://github.com/mikefarah/yq/) version v3.4.1"; exit 0; fi
  | exec /opt/homebrew/bin/yq "$@"
  $ WF_YQ=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/fakeyq/yq wfcanon-v222.py blob pos-canonical.yml   (기대 = UNVERIFIABLE)
    WF-P0 파서 핀 = mikefarah v4.48.* · `/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/fakeyq/yq --version` = 'yq (https://github.com/mikefarah/yq/) version v3.4.1' → 일치 False
    WF-P1 파서 버전 불일치 → PREVENTION_UNVERIFIABLE (임의 PATH 의 다른 yq 를 조용히 쓰지 않는다)
    RESULT=UNVERIFIABLE
  $ (핀 일치 yq) — 기대 = BLOB_OK
    WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
    RESULT=BLOB_OK

---------- 7-e2e  파서 위조를 실행기 경로로 (기대 = PREVENTION_UNVERIFIABLE · 전순서 1) ----------
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  | WF-P0 파서 핀 = mikefarah v4.48.* · `/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx84v222/fakeyq/yq --version` = 'yq (https://github.com/mikefarah/yq/) version v3.4.1' → 일치 False
  | WF-P1 파서 버전 불일치 → PREVENTION_UNVERIFIABLE (임의 PATH 의 다른 yq 를 조용히 쓰지 않는다)
  | RESULT=UNVERIFIABLE
U17-fire PREVENTION_UNVERIFIABLE: (b-blob)@target 정본 잡 대조 불가(파서 핀 불일치·YAML 파서 실패)
U17-BT (b-blob)@target 판정 = UNVERIFIABLE   [무조건 항 · D 와 무관]
P_first(집합·|1|)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] P_last(집합·|1|·blob=f9615429819760c9977c74523d14c5f6cef6620a)=[0ef1447e4fac2c6f235555af7e1a0ba85ed41b23 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.DohXHRVSKL/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b-blob)@d·(b-server)·(c) 는 «D-지표 항»이라 평가 대상 없음.  **(b-blob)@target 은 위에서 «무조건 항»으로 이미 평가됐다**(v2.22·M-7 — v2.21 은 (b)(c) 를 통째로 접었다·심판 #3 vacuity)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=(b-blob)@target 정본 잡 대조 불가(파서 핀 불일치·YAML 파서 실패) [수집 1건 중 전순서 최소]
u17_rc=1
```


---

## 11. [항목 8] 값 핀 3종 — `permissions` · `runs-on` · 체크아웃 `with`

19개 픽스처 전부 **기대 == 실측**이고, **정본 양성 2건**(`pos-canonical` · `ctrl-runs-on-2404`)이
같은 표 안에서 `BLOB_OK` 로 대조된다.  **v2.21 대조군은 19건 중 17건이 `BLOB_OK`** 였다
(양성 2건 제외 전건 — v2.21 은 허용 키 «밖»만 거부하고 **존재·값을 검사하지 않았다**).

음극성/등가 함정 두 건을 전문으로 남긴다:

```text
f4-persistcred-true   with = {'fetch-depth': 0, 'persist-credentials': True}
                      위배: persist-credentials = True — 음극성 bool 은 `is False` 만
f4-fetchdepth-false   with = {'fetch-depth': False, 'persist-credentials': False}
                      위배: fetch-depth = False ≠ 정수 0 (bool 배제)
```

`f4-fetchdepth-false` 가 없으면 파이썬 `False == 0` 등가로 **`fetch-depth: false` 가 통과**한다 —
술어가 자기 언어의 등가에 걸려 fail-open 이 되는 자리를 픽스처로 고정했다.
`f4-persistcred-str`(`"false"` 문자열)도 같은 극성 규율(`is False` 만)로 red 다.

e2e: `f4-perms-absent` 를 실행기로 → v2.21 = `PREVENTION_ACTIVE` rc 0 / v2.22 = `PREVENTION_UNVERIFIED_REVISION` rc 1.

```text
########## 11. [항목 8] 값 핀 3종 — permissions · runs-on · checkout with ##########
  id                       v2.22                  v2.21(대조군)       설명
  pos-canonical            BLOB_OK                BLOB_OK                양성 — 정본 잡 템플릿 정확(체크아웃 SHA 핀 + ② 정본 B → ③ 정본 A)
  ctrl-runs-on-2404        BLOB_OK                BLOB_OK                허용 리터럴 2번째 — runs-on: ubuntu-24.04
  f4-perms-absent          UNVERIFIED_REVISION    BLOB_OK                [F#4①] permissions 생략 (= 리포/조직 기본값·blob 밖)
  f4-perms-write           UNVERIFIED_REVISION    BLOB_OK                [F#4①] permissions: {contents: write}
  f4-perms-extra           UNVERIFIED_REVISION    BLOB_OK                [F#4①] permissions 에 키 추가 — 정확히 {contents: read} 아님
  f4-runson-2204           UNVERIFIED_REVISION    BLOB_OK                [F#4②] runs-on: ubuntu-22.04 (허용 2 밖)
  f4-runson-macos          UNVERIFIED_REVISION    BLOB_OK                [F#4②] runs-on: macos-latest
  f4-runson-selfhosted     UNVERIFIED_REVISION    BLOB_OK                [F#4②] runs-on: [self-hosted, linux] (배열)
  f4-runson-expr           UNVERIFIED_REVISION    BLOB_OK                [F#4②] runs-on: ${{ vars.RUNNER }} (표현식)
  f4-with-absent           UNVERIFIED_REVISION    BLOB_OK                [F#4③] 체크아웃 with 생략 (= 얕은 클론 + 토큰 잔류)
  f4-fetchdepth-absent     UNVERIFIED_REVISION    BLOB_OK                [F#4③] fetch-depth 생략 (기본 1 = 얕은 클론)
  f4-fetchdepth-1          UNVERIFIED_REVISION    BLOB_OK                [F#4③] fetch-depth: 1
  f4-fetchdepth-false      UNVERIFIED_REVISION    BLOB_OK                [F#4③·bool 배제] fetch-depth: false — `False == 0` 파이썬 등가를 배제한다
  f4-persistcred-absent    UNVERIFIED_REVISION    BLOB_OK                [F#4③] persist-credentials 미지정 (기본 true = 토큰 잔류)
  f4-persistcred-true      UNVERIFIED_REVISION    BLOB_OK                [F#4③] persist-credentials: true
  f4-persistcred-str       UNVERIFIED_REVISION    BLOB_OK                [F#4③·음극성 bool] persist-credentials: "false" (문자열) — `is False` 만 통과
  f4-with-extra            UNVERIFIED_REVISION    BLOB_OK                [F#4③] with 에 키 추가 (ref)
  f4-checkout-tag          UNVERIFIED_REVISION    BLOB_OK                [⑬i] 체크아웃 uses 가 태그(@v4) — SHA 핀 아님
  f4-checkout-othersha     UNVERIFIED_REVISION    BLOB_OK                [⑬i] 체크아웃 uses 가 임의 40-hex SHA (포크 커밋)

---------- 8-전문  f4-persistcred-true · f4-fetchdepth-false (음극성 bool·int 등가 배제) ----------
== f4-persistcred-true ==
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
    WF-S2 [①체크아웃] 키 = ['uses', 'with'] · uses = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' · with = {'fetch-depth': 0, 'persist-credentials': True}
    WF-C5 위배: [①체크아웃] persist-credentials = True — 음극성 bool 은 `is False` 만
    RESULT=UNVERIFIED_REVISION
== f4-fetchdepth-false ==
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
    WF-S2 [①체크아웃] 키 = ['uses', 'with'] · uses = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' · with = {'fetch-depth': False, 'persist-credentials': False}
    WF-C5 위배: [①체크아웃] fetch-depth = False ≠ 정수 0 (bool 배제)
    RESULT=UNVERIFIED_REVISION

---------- 8-e2e  f4-perms-absent 를 실행기로 (v2.21 = ACTIVE / v2.22 = 차단) ----------
>>> v2.21
  | WF-C6 blob 층 판정 = BLOB_OK
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/perms
u17_rc=0
>>> v2.22
  | WF-T2 [F#4①] permissions = '∅(부재)'
  | WF-C5 위배: permissions 키 부재(= 리포/조직 기본값 = blob 밖·정적 결정 불가)
U17-fire PREVENTION_UNVERIFIED_REVISION: (b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 · T-84 ⑬)
U17-BT (b-blob)@target 판정 = UNVERIFIED_REVISION   [무조건 항 · D 와 무관]
  | WF-T2 [F#4①] permissions = '∅(부재)'
  | WF-C5 위배: permissions 키 부재(= 리포/조직 기본값 = blob 밖·정적 결정 불가)
U17-fire PREVENTION_UNVERIFIED_REVISION: (b-blob)@d d=73838f07c269c58e62873bf6d6c05ad8c7e932c5 head=1143a2e7e484fd8efd9fea45d310d2c9044d49c4 정본 «잡 템플릿» 불일치 — 최상위 allowlist·jobs 개수·잡 키/name/runs-on·steps 순서·체크아웃 with·스텝 메타·중복 키 중 하나 이상 (T-84 ⑬)
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1 · T-84 ⑬) [수집 2건 중 전순서 최소]
u17_rc=1
```


---

## 12. [항목 9] 동명 decoy 3케이스 — **잔여**로 실증한다

**«닫혔다»고 적지 않는다.**  계약 :5504-5512·:5563-5565 가 «② 는 잔여» 라고 자인한 자리다.

| 케이스 | 구성 | 계약이 말하는 기대 | 실측 v2.22 | 실측 v2.21 |
|---|---|---|---|---|
| ① evil 단독 | `tos-gate` check-run 1건, 그 run 의 path = `evil.yml` | **red** | **`PREVENTION_UNVERIFIED_REVISION` · rc 1**  (정본 path check-run **0건**) | `PREVENTION_UNVERIFIED_REVISION` |
| ② 정본+decoy 둘 다 success | 동명 2건 · 정본 path 1건 success | **red 가 아니다 = 잔여** | **`PREVENTION_ACTIVE` · rc 0** ← **잔여** | `PREVENTION_ACTIVE` |
| ③ 정본 fail + decoy success | 동명 2건 · 정본 path 1건 failure | **red** | **`PREVENTION_UNVERIFIED_REVISION` · rc 1**  (정본 path conclusion=`failure`) | `PREVENTION_UNVERIFIED_REVISION` |

### 12-1. 대조군의 «정직한 결과» — ①③ 에서 v2.21 도 red 다

브리프 규율상 «v2.22 가 차단한다» 에는 «v2.21 은 통과했다» 가 붙어야 한다.
**①③ 에서는 그 대조군이 재현되지 않는다** — v2.21 도 red 다.  숨기지 않고 어디서 갈리는지 적는다:

- **①**: v2.21 은 decoy 의 suite 질의에서 `path≠tos-gate.yml` 을 보고 red 를 낸다
  (사유: `워크플로 정체성 불충족: workflow run path≠… (paths=[('.github/workflows/evil.yml', …)])`).
- **③**: v2.21 은 `conclusion==success` 선-필터 때문에 **decoy 를 정체성 후보로 집고**,
  그 suite 안에서 정본 path 의 run 을 찾아 `RUN_ID` 로 삼은 뒤 **(b-server) 층에서야** red 를 낸다
  (사유: `(b)③ … 서버 잡 스텝 대조 실패 … (T-84 ⑭)`).
  v2.22 는 **(b)② 층에서** red 를 낸다(`정본 path check-run 1건 · conclusion=failure`).
  즉 v2.22 의 이득은 «red 냐 아니냐»가 아니라 **«어느 층에서·어느 객체를 보고» red 를 내느냐**다.
- 계약 :5565 자신이 ③ 을 «**이름-∃ 술어였으면** 통과했을 자리» 라고 적었다 — 즉 계약도 v2.21 실행기가
  통과한다고 주장하지 않는다.  **에라타 아님**(문언과 실측이 정합).

### 12-2. 잔여 (닫지 못한다)

- **케이스 ②** 는 v2.22 에서도 `PREVENTION_ACTIVE` 다.  (a) 예방 층은 이름·`app_id` 만 보고 blob 을
  읽지 않으며, (b) path-aware 열거도 «정본 path 가 success» 면 통과시킨다.
- transcript 는 동명 2건을 **열거 기록**으로 남긴다(`U17-B2e … 전수 열거 — 2건` + 각 행의
  `conclusion/app_id/head_sha/suite/run/path`).  «공존 자체는 red 가 아니다»가 문언대로 구현됐다.

```text
########## 12. [항목 9] 동명 decoy 3케이스 — **잔여**로 실증한다 (닫혔다고 적지 않는다) ##########

---------- 9-1  ① evil 단독 — 정본 path check-run 부재 ⇒ **red** ----------
>>> v2.22
U17-BT (b-blob)@target 판정 = OK   [무조건 항 · D 와 무관]
U17-B2e [M-3] 동명(tos-gate) check-run 전수 열거 — 1건 (conclusion 으로 «먼저 거르지 않는다»):
  | check-run #0  conclusion=success  app_id==Actions=1  head_sha==PR head=1  suite=777001  run=555555  path=.github/workflows/evil.yml
U17-B2e 정본 path(.github/workflows/tos-gate.yml) check-run = 0건 (요구 «정확히 1») · 그 conclusion = ∅ · 동명·타 path 공존은 red 가 «아니다»((a) decoy 잔여·열거 기록만)
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)② d=7ba254509692912ddb363f8f3b46cbaa54d7cf2a head=8ce531ed1bbdb475e87229ae003ae2b919b35d49 path-aware 열거 불충족 — 정본 path check-run 0건(요구 1) · conclusion=∅
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)② d=7ba254509692912ddb363f8f3b46cbaa54d7cf2a head=8ce531ed1bbdb475e87229ae003ae2b919b35d49 path-aware 열거 불충족 — 정본 path check-run 0건(요구 1) · conclusion=∅ [수집 1건 중 전순서 최소]
u17_rc=1
>>> v2.21 (대조군)
U17-fire PREVENTION_UNVERIFIED_REVISION: (b) d=7ba254509692912ddb363f8f3b46cbaa54d7cf2a head=8ce531ed1bbdb475e87229ae003ae2b919b35d49 워크플로 정체성 불충족: workflow run path≠.github/workflows/tos-gate.yml ∨ head_sha≠PR head (paths=[('.github/workflows/evil.yml', '8ce531e')]);
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=7ba254509692912ddb363f8f3b46cbaa54d7cf2a head=8ce531ed1bbdb475e87229ae003ae2b919b35d49 워크플로 정체성 불충족: workflow run path≠.github/workflows/tos-gate.yml ∨ head_sha≠PR head (paths=[('.github/workflows/evil.yml', '8ce531e')]); [수집 1건 중 전순서 최소]
u17_rc=1

---------- 9-2  ② 정본 + decoy 둘 다 success ⇒ **red 가 아니다 = 잔여** ----------
>>> v2.22
U17-BT (b-blob)@target 판정 = OK   [무조건 항 · D 와 무관]
U17-B2e [M-3] 동명(tos-gate) check-run 전수 열거 — 2건 (conclusion 으로 «먼저 거르지 않는다»):
  | check-run #0  conclusion=success  app_id==Actions=1  head_sha==PR head=1  suite=777001  run=424242  path=.github/workflows/tos-gate.yml
  | check-run #1  conclusion=success  app_id==Actions=1  head_sha==PR head=1  suite=777001  run=555555  path=.github/workflows/evil.yml
U17-B2e 정본 path(.github/workflows/tos-gate.yml) check-run = 1건 (요구 «정확히 1») · 그 conclusion = success · 동명·타 path 공존은 red 가 «아니다»((a) decoy 잔여·열거 기록만)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ **(b-blob)@target=OK(무조건 항·target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1)** ∧ (b-blob)@d·(b-server) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/decoy2
u17_rc=0
>>> v2.21 (대조군)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/decoy2
u17_rc=0

---------- 9-3  ③ 정본 fail + decoy success ⇒ **red** ----------
>>> v2.22
U17-BT (b-blob)@target 판정 = OK   [무조건 항 · D 와 무관]
U17-B2e [M-3] 동명(tos-gate) check-run 전수 열거 — 2건 (conclusion 으로 «먼저 거르지 않는다»):
  | check-run #0  conclusion=failure  app_id==Actions=1  head_sha==PR head=1  suite=777001  run=424242  path=.github/workflows/tos-gate.yml
  | check-run #1  conclusion=success  app_id==Actions=1  head_sha==PR head=1  suite=777001  run=555555  path=.github/workflows/evil.yml
U17-B2e 정본 path(.github/workflows/tos-gate.yml) check-run = 1건 (요구 «정확히 1») · 그 conclusion = failure · 동명·타 path 공존은 red 가 «아니다»((a) decoy 잔여·열거 기록만)
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)② d=7ba254509692912ddb363f8f3b46cbaa54d7cf2a head=8ce531ed1bbdb475e87229ae003ae2b919b35d49 path-aware 열거 불충족 — 정본 path check-run 1건(요구 1) · conclusion=failure
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)② d=7ba254509692912ddb363f8f3b46cbaa54d7cf2a head=8ce531ed1bbdb475e87229ae003ae2b919b35d49 path-aware 열거 불충족 — 정본 path check-run 1건(요구 1) · conclusion=failure [수집 1건 중 전순서 최소]
u17_rc=1
>>> v2.21 (대조군)
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=7ba254509692912ddb363f8f3b46cbaa54d7cf2a head=8ce531ed1bbdb475e87229ae003ae2b919b35d49 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭)
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=7ba254509692912ddb363f8f3b46cbaa54d7cf2a head=8ce531ed1bbdb475e87229ae003ae2b919b35d49 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭) [수집 1건 중 전순서 최소]
u17_rc=1

  **잔여 등재(닫지 못한다)**: 케이스 ② 는 v2.22 에서도 통과다 — (a) 예방 층은 이름·app_id 만 보고
  blob 을 읽지 않으며, (b) path-aware 열거도 «정본 path 가 success» 면 통과시킨다.  «닫혔다»가 아니다.
```


---

## 12-c. [G5] **과잉 차단** — 정직한 `on: [pull_request, push]` 이 (b)② «정확히 1» 과 충돌한다

계약 `:5655` 는 `on ⊆ {pull_request, push}` 를 **명시적으로 허용**한다.  그런데 workflow run 의
**`event` 는 계약 어디에도 핀돼 있지 않다** — run 정체성을 묶는 것은 `path`(`:5554`)와
`head_sha`(`:5556`) 뿐이다.  두 트리거를 선언한 정직한 워크플로는 **같은 head SHA 에 같은 `path` 의
run 을 둘**(push 트리거 · pull_request 트리거) 만들고, 각각 `tos-gate` check-run 을 낸다.

| 층 | 대상 | 판정 |
|---|---|---|
| blob 층 | `ctrl-on-push`(정본 + `on: [pull_request, push]`) | **`BLOB_OK`** — 정직한 워크플로다 |
| (b)② 서버 층 | 정본 path check-run **2건**(둘 다 `success`) | **`PREVENTION_UNVERIFIED_REVISION` · rc 1** |
| **대조군 v2.21** | 같은 seam | **`PREVENTION_ACTIVE` · rc 0** |

**같은 blob 을 blob 층은 정본이라 하고 서버 층은 비정본이라 한다.**  방향은 fail-closed(과잉 차단)이라
fail-open 은 아니지만, **F#4 가 닫으려던 «두 소비자·같은 blob·다른 결론» 클래스가 v2.22 «신규»
술어 안에서 재발**한 자리다.  에라타 후보 **EC-7**.

```text
########## 12-c. [G5] **과잉 차단** 실증 — 정직한 «on: [pull_request, push]» 이 (b)② «정확히 1» 과 충돌한다 ##########
  계약은 workflow run 의 «event» 를 어디에도 핀하지 않는다 — run 정체성은 «path»(:5554)·«head_sha»(:5556) 뿐이다.
  그런데 «on: [pull_request, push]»(:5655 가 «허용»)이면 같은 head_sha 에 **같은 path 의 run 이 둘**
  (push 트리거 · pull_request 트리거) 생기고, 각각 «tos-gate» check-run 을 낸다.
  ⇒ (b)② 의 «정본 path check-run 이 정확히 1개» 가 **정직한 구성**을 red 로 만든다.
  blob 층 판정(정직한 워크플로여야 한다): BLOB_OK
>>> v2.22 (실측 — 과잉 차단이면 UNVERIFIED_REVISION)
U17-B2e [M-3] 동명(tos-gate) check-run 전수 열거 — 2건 (conclusion 으로 «먼저 거르지 않는다»):
  | check-run #0  conclusion=success  app_id==Actions=1  head_sha==PR head=1  suite=777001  run=424242  path=.github/workflows/tos-gate.yml
  | check-run #1  conclusion=success  app_id==Actions=1  head_sha==PR head=1  suite=777002  run=424243  path=.github/workflows/tos-gate.yml
U17-B2e 정본 path(.github/workflows/tos-gate.yml) check-run = 2건 (요구 «정확히 1») · 그 conclusion = success · 동명·타 path 공존은 red 가 «아니다»((a) decoy 잔여·열거 기록만)
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)② d=559843382dfecd786d143e4b5ffe1b81ed59ba15 head=d4e13d37df7a8e6f21b81a4501c0805598b171f5 path-aware 열거 불충족 — 정본 path check-run 2건(요구 1) · conclusion=success
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)② d=559843382dfecd786d143e4b5ffe1b81ed59ba15 head=d4e13d37df7a8e6f21b81a4501c0805598b171f5 path-aware 열거 불충족 — 정본 path check-run 2건(요구 1) · conclusion=success [수집 1건 중 전순서 최소]
u17_rc=1
>>> v2.21 (대조군 — 첫 후보에서 break 하므로 통과 기대)
prevention_control_state=PREVENTION_ACTIVE
u17_rc=0
  ⇒ **이것은 fail-open 이 아니라 fail-closed 방향의 과잉 차단**이지만, F#4 가 닫으려던
     «두 소비자가 같은 blob 에 다른 결론» 클래스가 v2.22 «신규» 술어 안에서 재발한 자리다(에라타 후보 EC-7)
```


---

## 12-d. [G4] 순환 alias — 계약이 **«미종료»에 상태값을 배정하지 않았다**

계약 `:5624-5626` 은 «모든 매핑 노드를 재귀 검사» 라고만 적는다.  `<<` 는 금지되나 **문서 수준의
평범한 `&anchor`/`*alias` 는 금지돼 있지 않고**, 계약이 anchor 를 보낸 방어(`:5649-5650` «yq 확장 +
`jobs` 개수 1»)는 **C-1 «이후»** 라 C-1 «자신의 순회»를 보호하지 못한다.

| # | 관측 | 실측 |
|---|---|---|
| 1 | `yaml.compose()` 가 순환 노드 그래프를 만드는가 | **자기 조상을 다시 가리키는 노드**: self 1건 `$.a.b` · branch 2건 · in-job 1건 `$.jobs.tos-gate.steps` |
| 2 | 방문집합 «없는» 순회(깊이 상한 64 만)가 종료하는가 | self 0.000s 종료 · **branch = 12초 미종료** |
| 3 | 방문집합 «있는» 현행 술어 | 3종 전건 종료 · 전건 `UNVERIFIED_REVISION`(사유가 «순환»으로 찍힌다) |
| 4 | 판정 파서 `yq` 자신 | branch = **`fatal error: stack overflow` rc 2** · chain = **조용히 절단된 유한 구조** |
| 5 | **대조군 v2.21 술어** | self → `UNVERIFIED_REVISION` · branch → `UNVERIFIABLE` · **in-job → `RESULT` 라인 «부재» · rc 1 (`AttributeError: 'str' object has no attribute 'get'`)** |

- **미종료는 상태값이 아니다.**  멈춘 프로세스는 `UNVERIFIABLE` 도 아니고 fail-closed 도 아니며
  **판정 자체가 없다** — 실행기의 `trap EXIT` 조차 돌지 않는다.  깊이 상한만으로는 분기 순환에서
  2^depth 로 폭발해 이 상태에 들어간다(실측 2).
- **처분**: 노드 «객체 identity» 방문집합.  순환은 **중복 키로 오귀속하지 않고** 자기 사유를 갖는다
  (한 관측에 두 상태값 금지 · 극성 논증).  깊이 상한은 벨트로 남겼다.
- **v2.21 의 in-job 거동은 «우연한 fail-closed»** 다: yq 가 순환을 조용히 절단해 `steps` 가 시퀀스가
  아닌 매핑이 되고, v2.21 이 그것을 리스트로 순회하다 죽는다.  실행기의 `case *)` 가 빈 `WFRES` 를
  red 로 접으므로 결과는 차단이지만 **설계가 아니다**.  에라타 후보 **EC-9**.

```text
########## 12-d. [G4] 순환 alias — 계약이 «미종료» 에 상태값을 배정하지 않았다 ##########
-- (1) compose 가 순환 «노드 그래프» 를 만드는가 (객체 identity) --
  g4-cycle-self.yml          자기 조상을 다시 가리키는 노드 = 1건 ['$.a.b']
  g4-cycle-branch.yml        자기 조상을 다시 가리키는 노드 = 2건 ['$.a.b', '$.a.c']
  g4-cycle-in-job.yml        자기 조상을 다시 가리키는 노드 = 1건 ['$.jobs.tos-gate.steps']
-- (2) 방문집합 «없는» 순회(깊이 상한 64 만) 가 종료하는가 — 워치독 12초 --
  g4-cycle-self.yml          종료 0.000s · 결과 크기=592
  g4-cycle-branch.yml        **12초 미종료 — 판정 자체가 없다(fail-closed 도 아니다)**
-- (3) 방문집합 «있는» 현행 술어 (기대: 전건 종료 + UNVERIFIED_REVISION) --
  g4-cycle-self              → UNVERIFIED_REVISION
  g4-cycle-branch            → UNVERIFIED_REVISION
  g4-cycle-in-job            → UNVERIFIED_REVISION
      WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 1건 ['$.jobs.tos-gate.steps [순환 alias — 노드가 자기 조상을 다시 가리킨다]']
      WF-D2c 순환 alias 검출 → UNVERIFIED_REVISION (계약은 «미종료»에 상태값을 주지 않는다 — 방문집합 없이는 판정 자체가 없다)
-- (4) 판정 파서 yq 자신은 순환에 무엇을 하는가 (워치독 10초) --
  g4-cycle-self              rc=0   {   "a": {     "b": {       "b": {}     }   } } 
  g4-cycle-branch            rc=2   runtime: goroutine stack exceeds 1000000000-byte limit runtime: sp=0x140202a02f0 stack=[0x1402029e000, 0x1404029e000] fatal error:
  g4-cycle-in-job            rc=0   {   "name": "tos-gate",   "on": [     "pull_request"   ],   "permissions": {     "contents": "read"   },   "jobs": {     "tos-gate
-- (5) v2.21 술어 대조군 (워치독 15초) --
  g4-cycle-self              0.04s → RESULT=UNVERIFIED_REVISION
  g4-cycle-branch            0.23s → RESULT=UNVERIFIABLE
  g4-cycle-in-job            0.04s → **RESULT 라인 부재 · rc=1** (AttributeError: 'str' object has no attribute 'get')
  ⇒ v2.21 은 «g4-cycle-in-job» 에서 **판정을 내지 못하고 죽는다**(yq 가 순환을 «조용히 절단»해
     «steps» 가 시퀀스가 아닌 매핑이 되고 v2.21 이 그것을 리스트로 순회한다).
     실행기의 «case *)» 가 빈 WFRES 를 red 로 접으므로 **결과적으로는 fail-closed 지만 설계가 아니라 우연**이다.
```


---

## 13. 회귀 · 역방향 fail-open 사냥 · 본 저장소 live 실측 · 잔여 등재

### 13-A. 술어 배터리 80종 — 기대(사전 기입) vs 실측

- **기대 ≠ 실측 = 0건 / 83.**  기대값은 `mkwf-v222.py` 가 `INDEX.txt` 에 **실행 «전»** 에 적었다
  (양성 12 · 차단 71).
- **v2.21 이 `BLOB_OK` 를 낸 픽스처 = 55** · **v2.22 가 새로 닫은 자리 = 43**.
- ⑬a~⑬g·NBSP·inline·`env bash` 등 v2.21 이 이미 닫은 자리는 **전건 red 유지**(회귀 0).
- 배터리 3종이 이번 라운드에 늘었다: `g4-cycle-self`·`g4-cycle-branch`·`g4-cycle-in-job`(§12-d).

> **정직 기록(자기 적발 · 앞 라운드에서 수정함)**: 이전 실행(`run2.log`)의 B-1 소제목이 픽스처 수를
> **하드코딩**해 `× 77` 로 굳어 있었다(표와 집계는 실측이었다).  이번 판은 라벨을 `$(grep -c . INDEX.txt)`
> 로 **동적화**해 같은 클래스가 재발하지 않게 했다 — «하드코딩 census 는 신규 항목을 영원히 못 찾는다».

```text
########## 2·13. 실행기 파생 표 + 술어 배터리 (기대는 픽스처 생성기가 «미리» 적었다) · 회귀 ##########
  fixtures=83 (blob 판정) + 7 (정직 워크플로 키트리) → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/fx

---------- B-1  v2.22 술어 × 83 픽스처 — 기대/실측 + v2.21 대조군 ----------
  id                           기대(사전 기입)  실측 v2.22           대조군 v2.21        판정
  pos-canonical                BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-comments                BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-trailing-ws             BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-crlf                    BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-bom                     BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-runs-on-2404            BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-on-map                  BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-on-push                 BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-run-name                BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-shell-euo               BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-shell-eo                BLOB_OK                BLOB_OK                BLOB_OK                OK
  ctrl-timeout-5               BLOB_OK                BLOB_OK                BLOB_OK                OK
  f1-v221-order                UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f1-if-always                 UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  f1-if-success                UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f1-coe-true                  UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  f1-coe-false                 UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f1-shell-sh                  UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  f1-shell-pwsh                UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  f1-timeout-zero              UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  f1-folded                    UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  m1-on-schedule               UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  m1-on-wd                     UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  c1-dupsteps-benign-first     UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  c1-dupsteps-canon-first      UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  c1-dup-in-step-run           UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  c1-dup-in-step-name          UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  c1-dup-jobs                  UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  c1-dup-permissions           UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  c1-dup-runs-on               UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  g4-cycle-self                UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  g4-cycle-branch              UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIABLE           OK
  g4-cycle-in-job              UNVERIFIED_REVISION    UNVERIFIED_REVISION                           OK
  m2-anchor-dup-job            UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  m2-anchor-alias-only         UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  m2-merge-key                 UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  m2-top-concurrency           UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  m2-top-env                   UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  m2-top-defaults              UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  m2-job-defaults              UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-perms-absent              UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-perms-write               UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-perms-extra               UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-runson-2204               UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-runson-macos              UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-runson-selfhosted         UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-runson-expr               UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-with-absent               UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-fetchdepth-absent         UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-fetchdepth-1              UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-fetchdepth-false          UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-persistcred-absent        UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-persistcred-true          UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-persistcred-str           UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-with-extra                UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-checkout-tag              UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f4-checkout-othersha         UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f2-sibling-job               UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f2-sibling-namesok           UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f2-jobid-mismatch            UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  f2-name-free                 UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  f2-name-absent               UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  13a-echo                     UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13b-trailcomment             UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13c-ortrue                   UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13d-unreachable              UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13f-set-plus-e               UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13f-trap                     UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13g-exit0                    UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13g-exec-true                UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13g-guarded-exit             UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  nbsp-trailing                UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  inline-semicolon             UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  env-bash                     UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13i-extra-step               UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  13i-steps-two                UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  13j-job-container            UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  13j-job-env                  UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  13j-job-if                   UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  13j-job-needs                UNVERIFIED_REVISION    UNVERIFIED_REVISION    BLOB_OK                OK ← v2.22 신규 차단
  13e-step-env                 UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13e-step-workdir             UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  13e-step-id                  UNVERIFIED_REVISION    UNVERIFIED_REVISION    UNVERIFIED_REVISION    OK
  ⇒ 기대 ≠ 실측 = 0 건 / 83 · v2.21 이 BLOB_OK 를 낸 픽스처 = 55 · **v2.22 가 새로 닫은 자리 = 43**
```


### 13-B. ⑬/⑭ 회귀 + 연속성 + 아티팩트 변이 + live ⑤⑩⑫

- **⑭ 서버 10변형**: `ok`=SERVER_OK · `noverify`/`verifyfail`/`norun`/`jobfail`/`skipped`/`neutral`/
  `cancelled`/`nullconc` = UNVERIFIED_REVISION — **v2.21 과 전건 동일**(코드 델타 0 실증).
  갈리는 것은 **`dupname` 한 건**(v2.22 = UNVERIFIED_REVISION / v2.21 = SERVER_OK) = F#2(ii).
- **⑪-(a)** 연속성 정상 → `PREVENTION_ACTIVE` rc 0 (`(b-blob)@target=OK` 포함) ·
  **⑪-(b)** `updated_at > t_land` → `PREVENTION_CONTINUITY_UNVERIFIABLE` rc 1.
- **⑨** 착수 «후» 아티팩트 편집 → `PREVENTION_ARTIFACT_MUTATED` rc 1.
- **⑫ live**: `GH_HOST=example.invalid` override 유무로 상태값 **불변**
  (`PREVENTION_INSUFFICIENT` · 사유 문자열까지 동일) — host 결속 유지.
- **⑤-a live**: 선언 `target_branch` = 작업 브랜치 → `PREVENTION_TARGET_MISMATCH`.
- **⑩-a live**: 원격이 `gitlab.com` → `PREVENTION_TARGET_MISMATCH`.

```text
########## 13. 회귀 — v2.21 증거가 이미 세운 축이 v2.22 에서도 그대로인가 ##########

---------- R-1 ⑭ 서버 변형 (부재·실패·잡실패 · skipped/neutral/cancelled/null) ----------
  variant     v2.22                    v2.21                   
  ok          SERVER_OK                SERVER_OK               
  noverify    UNVERIFIED_REVISION      UNVERIFIED_REVISION     
  verifyfail  UNVERIFIED_REVISION      UNVERIFIED_REVISION     
  norun       UNVERIFIED_REVISION      UNVERIFIED_REVISION     
  jobfail     UNVERIFIED_REVISION      UNVERIFIED_REVISION     
  skipped     UNVERIFIED_REVISION      UNVERIFIED_REVISION     
  neutral     UNVERIFIED_REVISION      UNVERIFIED_REVISION     
  cancelled   UNVERIFIED_REVISION      UNVERIFIED_REVISION     
  nullconc    UNVERIFIED_REVISION      UNVERIFIED_REVISION     
  dupname     UNVERIFIED_REVISION      SERVER_OK               

---------- R-2 ⑪-(a) 연속성 정상 ⇒ ACTIVE / ⑪-(b) updated_at > t_land ⇒ CONTINUITY_UNVERIFIABLE ----------
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 94bbe7687c7197e84469f655593469264a426722:.github/workflows/tos-gate.yml → ac58ad0b9c03a5756905aac185a28342c79b2f6f
U17-B d=4245cafbc01e7f81c0bdc2508231cf7825893901 head=94bbe7687c7197e84469f655593469264a426722 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ **(b-blob)@target=OK(무조건 항·target HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1)** ∧ (b-blob)@d·(b-server) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7d02b41f-d331-4fe8-86b9-9b51c78ecde7/scratchpad/v222/v222-evidence/seam222/11a
u17_rc=0
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 updated_at=2026-08-11T09:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가
U17-fire PREVENTION_CONTINUITY_UNVERIFIABLE: (α) ruleset 42 updated_at=2026-08-11T09:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가 — 운영자 재심사 경로(영구 차단 아님)
prevention_control_state=PREVENTION_CONTINUITY_UNVERIFIABLE
reason=(α) ruleset 42 updated_at=2026-08-11T09:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가 — 운영자 재심사 경로(영구 차단 아님) [수집 1건 중 전순서 최소]
u17_rc=1

---------- R-3 ⑨ 착수 «후» 아티팩트 편집 ⇒ ARTIFACT_MUTATED ----------
U17-B d=f1270e36c4b15bbe7640ae6e19e7e274ced73c2e head=03672a380ce9d79290883c879662ebecb6cfca61 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=[E9] ¬LATE ∧ ∃d∈D: x_last=de43379fa041cd8bb7b83044312a2a3e2b2bf647 ⋠ d — 착수 «후» 아티팩트 변경 [수집 1건 중 전순서 최소]
u17_rc=1

---------- R-4 ⑤⑩⑫ live (GET-only) — 선언 target 불일치 · 타 원격 · GH_HOST override 불변 ----------
>>> ⑫-a live 기본
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.eOoMKPvpz9
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
U17-BT [M-7] target HEAD sha = 11e382fc0c9c16d9208a0d59e595d9cf93066be5   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)
U17-BT (b-blob)@target 판정 = UNVERIFIED_REVISION   [무조건 항 · D 와 무관]
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 2건 중 전순서 최소]
>>> ⑫-b live GH_HOST=example.invalid override (상태값 «불변» 기대)
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.VgzsDH0qio
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=example.invalid → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
U17-BT [M-7] target HEAD sha = 11e382fc0c9c16d9208a0d59e595d9cf93066be5   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)
U17-BT (b-blob)@target 판정 = UNVERIFIED_REVISION   [무조건 항 · D 와 무관]
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 2건 중 전순서 최소]
>>> ⑤-a live 선언 target=작업 브랜치
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 계약 핀/파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main) [수집 3건 중 전순서 최소]
>>> ⑩-a live 타 host 원격
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=gitlab.com/kakao-harris-lee/kis_unified_sts) [수집 3건 중 전순서 최소]
```


### 13-C. 역방향 fail-open 사냥 — 뮤테이션 25종

«신규 검사가 실제로 판정을 지고 있는가»를 **자기신고가 아니라 판정 뒤집힘**으로 본다.
각 뮤테이션은 술어의 한 검사(또는 벨트와 함께 둘·셋)를 무력화한 **사본**을 만들고,
그 검사가 잡던 픽스처를 돌려 `BLOB_OK`(= 통과로 뒤집힘)를 기대한다.

- **판정 뒤집힘 19 / 불변 7.**
- **«불변» 7건은 전부 벨트 또는 뮤테이션 산출물이며, 그 귀속을 실행으로 보였다**:
  M1(C-1) ← 키 트리 벨트(M1b 이중 무력화에서 뒤집힘) · M2(`<<`) ← 키 트리 + 최상위 allowlist
  (M2c 삼중 무력화에서 뒤집힘) · M3(키 트리 벨트) ← **구성상 벨트**(알려진 발산 원천이 중복 키와
  `<<` 둘뿐) · M6 ← **뮤테이션 설계 오류**(첫 분기만 끄면 둘째 분기가 `doc["permissions"]` 를 읽어
  KeyError → `<none>`; M6c 이중에서 뒤집힘) · M8(jobs 개수) ← 잡 `name` 값-핀(M8b 단독 픽스처에서
  뒤집힘) · M15(`continue-on-error`) ← run 스텝 허용 키(M15b 이중에서 뒤집힘).
- ⇒ **죽은 검사 0 · 신규 fail-open 0.**
- **정직 기록**: `<<` 금지의 **«단독 부담» 픽스처는 만들지 못했다**.  워크플로에서 `<<` 는 anchor 소스를
  필요로 하고 그 관용 위치(최상위 `x-*` 키)가 allowlist 밖이기 때문이다.  «중복 방어»이지
  «죽은 코드»가 아님은 M2c 로 보였으나, 단독 부담을 보이지 못한 것은 그대로 적는다.

```text
########## 12-b. 역방향 fail-open 사냥 — 신규 술어 뮤테이션 (자기신고 금지 · 판정 뒤집힘으로 본다) ##########
  뮤테이션                   무력화 대상                                   픽스처                        기대             실측
  M1-C1-dup              C-1 전 노드 중복 키 검출                         c1-dupsteps-benign-first   BLOB_OK        UNVERIFIED_REVISION  **불변 — 벨트/죽은코드 판별 필요**
  M2-merge-key           `<<` merge key 금지                        m2-merge-key               BLOB_OK        UNVERIFIED_REVISION  **불변 — 벨트/죽은코드 판별 필요**
  M3-keytree-belt        두 파서 `.value` 키 트리 벨트                    m2-merge-key               BLOB_OK        UNVERIFIED_REVISION  **불변 — 벨트/죽은코드 판별 필요**
  M4-parser-pin          yq 파서 버전 핀                               pos-canonical              BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M5-top-allowlist       최상위 allowlist                            m2-top-concurrency         BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M6-permissions         permissions 존재+값 핀                       f4-perms-absent            BLOB_OK        <none>               **불변 — 벨트/죽은코드 판별 필요**
  M6b-permissions-val    permissions 값 핀(정확히 {contents: read})    f4-perms-write             BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M7-on                  on ⊆ {pull_request, push}                m1-on-schedule             BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M8-jobs-count          jobs 정확히 1개                              f2-sibling-job             BLOB_OK        UNVERIFIED_REVISION  **불변 — 벨트/죽은코드 판별 필요**
  M9-job-keys            게이트 잡 허용 키 닫힌 집합                         13j-job-container          BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M10-name-pin           잡 name 값-핀                               f2-name-free               BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M11-runs-on            runs-on 허용 리터럴 2개                        f4-runson-2204             BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M12-steps-order        steps 정확히 3개·순서 고정                       f1-v221-order              BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M13-checkout-pin       체크아웃 uses SHA 핀                          f4-checkout-tag            BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M14-with-persist       persist-credentials `is False`           f4-persistcred-true        BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M14b-with-fetchdepth   fetch-depth 정수 0 (bool 배제)               f4-fetchdepth-false        BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M15-coe-key            continue-on-error 키 부재                   f1-coe-false               BLOB_OK        UNVERIFIED_REVISION  **불변 — 벨트/죽은코드 판별 필요**
  M16-shell              SHELL_OK 3값                              f1-shell-sh                BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M17-run-step-keys      run 스텝 허용 키 닫힌 집합                        13e-step-env               BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M1b-C1+belt            C-1 중복 검출 **+** 키 트리 벨트 (이중)             c1-dupsteps-benign-first   BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M2b-merge+belt         `<<` 금지 **+** 키 트리 벨트 (이중)               m2-merge-key               BLOB_OK        UNVERIFIED_REVISION  **불변 — 벨트/죽은코드 판별 필요**
  M2c-merge+belt+allow   `<<` 금지 **+** 키 트리 벨트 **+** 최상위 allowlist (삼중) m2-merge-key               BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M6c-permissions-both   permissions 존재 **+** 값 두 분기 (이중)         f4-perms-absent            BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M8b-jobs-count-solo    jobs 정확히 1개 (name 정본인 형제 잡 픽스처)          f2-sibling-namesok         BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M15b-coe+stepkeys      continue-on-error 키 **+** run 스텝 허용 키 (이중) f1-coe-false               BLOB_OK        BLOB_OK              판정 뒤집힘 = 이 검사가 지고 있었다
  M18-server-hit         서버 이름 필터 hit 유일성                         dupname                    SERVER_OK      SERVER_OK            판정 뒤집힘 = 이 검사가 지고 있었다
  ⇒ 판정 뒤집힘 19 / 불변 7  (불변 항은 아래 «벨트 판별» 참조)

---------- 12-b 벨트 판별 — «불변» 항이 죽은 코드인가 벨트인가 (실측으로 귀속한다) ----------
  M1  (C-1 중복)         → 불변.  벨트 = 두 파서 «.value» 키 트리(yq last-wins 붕괴 vs compose 보존).  M1b 이중 무력화에서 BLOB_OK 로 뒤집힘 ⇒ 죽은 코드 아님
  M2  («<<» 금지)        → 불변.  벨트 = 키 트리 + **최상위 allowlist**(anchor 소스 «x-base» 가 allowlist 밖).  실측 발화 지점:
      WF-T1 [M-2] 최상위 키 = ['jobs', 'name', 'on', 'permissions', 'x-base'] · allowlist = ['jobs', 'name', 'on', 'permissions', 'run-name']
      WF-C5 위배: 최상위 allowlist 밖 키 ['x-base']
      RESULT=UNVERIFIED_REVISION
       M2c 삼중 무력화에서 BLOB_OK ⇒ 죽은 코드 아님.  **단독 부담 픽스처는 만들지 못했다** —
       워크플로에서 «<<» 는 anchor 소스를 필요로 하고 그 관용 위치(최상위 x-* 키)가 allowlist 밖이기 때문이다(정직 기록)
  M3  (키 트리 벨트)      → 불변.  **구성상 벨트다** — 알려진 발산 원천이 중복 키와 «<<» 둘뿐이고 그 둘은 이미 차단된다.
                          M1b(벨트 무력화 시 중복이 통과)가 이 검사가 살아 있음을 뒤집힘으로 보인다
  M6  (permissions 존재) → 실측 «<none>» = 뮤테이션 산출물의 KeyError 크래시(첫 분기만 끄면 둘째 분기가 doc["permissions"] 를 읽는다).
                          **술어의 결함이 아니라 뮤테이션 설계 오류**다 — M6c 이중 무력화가 BLOB_OK 로 뒤집혀 검사가 살아 있음을 보인다
  M8  (jobs 개수)        → 불변.  벨트 = 잡 «name» 값-핀(그 픽스처의 게이트 잡 표시 이름이 비정본).  M8b 단독 픽스처에서 뒤집힘
  M15 (continue-on-error) → 불변.  벨트 = run 스텝 허용 키 닫힌 집합.  M15b 이중 무력화에서 뒤집힘
  ⇒ **죽은 검사 0 · 신규 fail-open 0**.  «불변» 7건은 전부 중복 방어(벨트) 또는 뮤테이션 산출물이며 그 귀속을 실행으로 보였다
```


### 13-D. 본 저장소 live 실측 (GET-only · 실행기 1회)

```text
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-BT [M-7] target HEAD sha = 11e382fc0c9c16d9208a0d59e595d9cf93066be5     ← verbatim 수록(계약 :5583 필수)
U17-BT1 …/contents/.github/workflows/tos-gate.yml?ref=11e382fc…  http=404
U17-fire PREVENTION_ABSENT              : 아티팩트 HEAD 부재 (D0A-PREVENTION-CONTROL.md)
U17-fire PREVENTION_INSUFFICIENT        : (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; …] ruleset:[적용 규칙 0]
U17-fire PREVENTION_UNVERIFIED_REVISION : (b-blob)@target http=404 — ABSENT 로 접지 않는다(전순서 2 vs 8)
prevention_control_state=PREVENTION_ABSENT   [수집 3건 중 전순서 최소]
```

- **오늘의 `main` 은 여전히 차단**이며, 그것이 정직한 현재 상태다(§12.3.4-G G-음성-2 의 «지금 live 로
  실행 가능한 진짜 음성»).  아티팩트·워크플로·하니스·`u17-verify` 4종이 전부 «부재»다 —
  개발계획 §6 «선행 조건 4종» 이 아직 이행되지 않았다는 뜻이고, 이 증거가 그것을 대신하지 않는다.
- **`(b-blob)@target` 이 live 에서도 실제로 조회를 돌았다** — 404 를 받고 전순서 8 로 발화했다.
  진입 판정이 blob 을 «한 줄도 읽지 않는» 상태는 이 실행기에서 더는 성립하지 않는다.
- 전순서가 `ABSENT`(2) 를 최소로 골랐으므로 최종 상태값은 `PREVENTION_ABSENT` 다
  (8 을 2 로 접은 것이 아니라 **셋을 다 발화시킨 뒤 전순서로 고른** 것 — 세 `U17-fire` 라인이 증거).

```text
########## 14. 본 저장소 live 실측 (GET · 실행기 1회) — 오늘의 main 은 무엇인가 ##########
  tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md 부재
  .github/workflows/tos-gate.yml                                 부재
  tools/tos_entry_harness.sh                                     부재
  config/tos_completion.yaml                                     부재
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.8TmulDr92G
U17-fire PREVENTION_ABSENT: 아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-20T10:48:54Z  http=200  x-github-request-id=D71C:389513:F3CA52:114BAD8:6A86DB96
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-BT0 repos/kakao-harris-lee/kis_unified_sts/branches/main  utc=2026-08-20T10:48:57Z  http=200  x-github-request-id=D733:38F9C1:F91EA3:11A1476:6A86DB98
U17-BT [M-7] target HEAD sha = 11e382fc0c9c16d9208a0d59e595d9cf93066be5   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)
U17-BT1 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=11e382fc0c9c16d9208a0d59e595d9cf93066be5  utc=2026-08-20T10:48:57Z  http=404  x-github-request-id=D743:164A81:F5BBB9:116A942:6A86DB99
U17-fire PREVENTION_UNVERIFIED_REVISION: (b-blob)@target http=404 (.github/workflows/tos-gate.yml 가 target HEAD 11e382fc0c9c16d9208a0d59e595d9cf93066be5 에 부재) — ABSENT 로 접지 않는다(전순서 2 vs 8)
U17-BT (b-blob)@target 판정 = UNVERIFIED_REVISION   [무조건 항 · D 와 무관]
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 3건 중 전순서 최소]
  (실행기 rc 는 위 상태값이 결정한다 — ACTIVE 만 0)
final rc=0
```


### 13-E. 잔여 등재 — **닫지 못한다** (실증 대상이 아니라 기록 대상)

| 잔여 | 성격 | 이 판에서 한 것 |
|---|---|---|
| **(a) 동명 decoy 케이스 ②** | (a) 예방 층은 이름·`app_id` 만 보고 blob 을 읽지 않는다 | §12 에서 **`PREVENTION_ACTIVE` 로 실증**.  «닫혔다»고 적지 않았다 |
| **`(b-blob)@d`·`(b-server)` 진입선 미평가** | 리비전·런이 물리적으로 부재(pre-D0-A) | §5 transcript 의 `U17-B D=∅ …` 라인이 명시 |
| **blob «밖» 스킵 3벡터** — ① 워크플로 API 비활성화 ② fork PR 승인 게이트 ③ merge queue `merge_group` | 계약의 blob 검사로 **무독**.  세 벡터 모두 저장소/조직 «설정»이거나 GitHub 내부 큐 동작이라 워크플로 blob 에 흔적이 없다 | **실증하지 않았다 · 실증 시도도 하지 않았다.**  «닫지 못한다»로 기록만 한다(계약 :5783-5784·⑥) |
| **파서 go-yaml v3 `UNMAINTAINED` 선언 의존** | M-4 핀이 그 선언에 의존 | 기록 |
| **`fetch-depth` 정확 필요치(0 vs N)** | 보수적 상위집합 | 기록 |
| **`persist-credentials: false` 대칭 잔여** | 하니스가 향후 네트워크 git 을 요구하면 재검토 | 기록 |
| **`u17-verify` 자체 sha 미핀** | 온라인 조회기라 §12.3.4-R 같은 byte 기준선이 없다 | 기록 |
| **GitHub 내부 실행 · 「실패 스텝 skip」 · 「파일대로 실행」 신뢰** | 공개 REST 로 닫히지 않는다 | §9-B 는 «순서가 도달성을 바꾼다»를 로컬로 보였을 뿐이다 |
| **`<<` 금지의 단독 부담 미실증** | 벨트 구조 | §13-C 에 기록 |
| **판정 소비자 자신의 환경 위조** | 소비자가 곧 운영자/리뷰어 | 계약 :5513-5514 그대로 |
| **`on: [pull_request, push]` 과잉 차단** | 계약 공백(EC-7) — run `event` 미핀 | §12-c 에서 **정직한 구성이 red** 임을 실행으로 남겼다.  실행기를 계약보다 관대하게 바꾸지 «않았다» |
| **정본 잡 템플릿이 «재-파생»** | 계약 공백(EC-8) — 코드펜스 부재 | §3-2 에서 재-파생본 + 판단 5자리를 아티팩트로 분리 |
| **순환 alias 의 «미종료»** | 계약 공백(EC-9) — 상태값 미배정 | 방문집합으로 «판정 없음»을 «판정 있음»으로 바꿨을 뿐, **계약에 그 상태값은 여전히 없다** |
| **C-1 파서(PyYAML) 버전 미핀** | 계약 공백(EC-10) | 측정값 6.0.3 을 매 run `WF-D0` 로 기록 — 핀이 아니다 |
| **blob 파싱 실패 상태값 미배정** | 계약 공백(EC-11) | 두 층의 처분을 명시하고 갈리는 창을 실측 |

### 13-F. T-84 종수 — **14종 불변 · 내역 병기**

이 판이 더한 대조군(⑬k 순서·자기수복 / ⑬l 잡-안 중복 `steps:` / ⑬m anchor·allowlist·`<<`·파서 버전 /
⑬n 전 노드 중복 키 / ⑬i·⑬j 값 검사 엄격화 / ⑭ hit 유일·잡 conclusion·path-aware)은 **전부 ⑬·⑭ 의 하위**다.
**종수는 14 이고 내역은 `4+2+4+2+2`** (v2.15/16 ①~④ 4 + v2.17 ⑤⑥ 2 + v2.18 ⑦~⑩ 4 + v2.19 ⑪⑫ 2 +
v2.20 ⑬⑭ 2).  이 실행은 종수를 건드리지 않았다.

---

## 14. 에라타 후보 (계약을 고치지 않았다 — 다음 단계 입력물)

> 규율: 실행 중 발견한 **사실오류·과잉차단·생략부호·도달 불가 분기**를 모은다.
> 계약 두 문서는 동결이며 이 실행에서 **한 글자도 편집하지 않았다**.

### EC-1 (**high 후보**) — `if:` 허용 집합이 «도달 불가 분기»다

- **계약 :5759**: «**`if:` 부재 또는 값 ∈ `{ success() , ${{ success() }} }`**(허용 집합을 계약이
  리터럴로 명시한다 — 실행기가 계약보다 관대해지는 자리를 없앤다·F#1 축 1)»
- **계약 :5762**: «run 스텝은 `name`·`run`·(선택 `shell` 정본값)·(선택 `timeout-minutes`) **외 키 부재**»
- **충돌**: 닫힌 키 집합에 `if` 가 없다.  그러면 `if: success()` 는 **닫힌 집합 위배로 이미 red** 이고
  :5759 의 «허용» 분기는 **영원히 도달하지 않는다**.  이것이 계약 자신이 두 번 기록한
  **«사코드 분기» 클래스**(v2.14 `G4` · :5864-5865)와 같은 형태다.
- **실행기 처분(기록)**: 더 좁은 쪽(닫힌 키 집합)을 따랐다 — **fail-closed 방향**.
  픽스처 `f1-if-success` 가 `UNVERIFIED_REVISION` 인 것이 그 이행이다(v2.21 은 `BLOB_OK`).
- **계약이 골라야 할 것**: (ㄱ) `if` 를 run 스텝 «선택 키»에 넣고 값 집합을 강제하거나,
  (ㄴ) :5759 의 «또는 값 ∈ …» 을 삭제하고 «`if:` 키 부재» 로 단일화한다.
  같은 문제가 **:5738 (축 1) 문언**(«두 스텝 모두 `if:` 부재 또는 `success()` 계열»)과
  **:2903 T-84 ⑬e**(«`if: always()`/`failure()` … 존재»)에도 전파돼 있다.
- `continue-on-error` 는 :5758(«키 자체 부재»)과 :5762 가 **정합**이라 같은 문제가 없다(대조).

### EC-2 (**medium 후보**) — 파서 핀의 «파싱 규격»이 미규정 = F#4 가 닫으려던 R-1 클래스의 재발

- **계약 :5607-5609**: «판정 파서 = **`yq (mikefarah) v4.48.x`** … 소비자는 실행 시
  **`yq --version` 을 파싱해 이 리터럴과 대조**하고 불일치 = `PREVENTION_UNVERIFIABLE`»
- **결함 ①(부분문자열 아님)**: `yq --version` 의 실제 출력은
  `yq (https://github.com/mikefarah/yq/) version v4.48.1` 이다.
  계약이 적은 리터럴 `yq (mikefarah) v4.48.x` 는 **도구 출력의 부분문자열이 아니다** —
  벤더 표기가 `(mikefarah)` 가 아니라 `(https://github.com/mikefarah/yq/)` 이고
  버전 앞에 `version ` 이 붙는다.  «이 리터럴과 대조» 를 문자 그대로 이행하면 **정본 도구가 red** 다.
- **결함 ②(`.x` 는 리터럴이 아니다)**: `v4.48.x` 의 `.x` 는 **patch 와일드카드**로 읽어야 뜻이 통하지만
  계약은 그것을 «리터럴» 이라 부른다.  와일드카드의 의미(patch 만 여는가 · pre-release 는 어떤가)가
  규정돼 있지 않다.
- **귀결**: «파싱해 대조» 의 규격이 없으므로 두 소비자가 다르게 구현할 수 있다
  (부분문자열 `mikefarah` + `v4.48.` 대조 / 정규화 후 완전일치 / 정규식…).
  **이것이 F#4 가 «형식만 검사» 라며 닫으려던 R-1 과 같은 클래스**다.
- **실행기 처분(명시)**: **매치 규칙 = `("mikefarah" in out) and ("v4.48." in out)`** — 벤더 식별자와
  major.minor 를 «둘 다» 요구하고 patch 는 연다(`.x` 를 «patch 와일드카드» 로 읽었다).
  규칙을 술어 상수 `YQ_FLAVOR`/`YQ_MAJMIN` 와 **헤더 주석 [G2]** 에 노출했다 — 다른 소비자가 다른
  규칙을 골랐는지 대조할 수 있게.  §10 에서 v3.4.1 위조가 `UNVERIFIABLE` 로 잡힘을 실증했다.
- **계약이 더할 것**: 정규식 또는 «출력에 `mikefarah` 와 `v4.48.` 이 모두 포함» 같은 **판정 규격 리터럴**.

### EC-3 (**minor 후보**) — 체크아웃 스텝의 `name:` 부재가 문언에 명시돼 있지 않다

- **계약 :5680**: 체크아웃 스텝은 «닫힌 키 `uses`·`with`» 다.  그러면 `name:` 을 붙이면 red 다.
- 그런데 나머지 두 스텝은 **`name:` 리터럴이 강제**되므로, D0-A 작성자가 세 스텝에 일관되게
  `name:` 을 붙이는 것이 자연스러운 오작동이다(과잉 차단의 «표기 지정»으로 해소 가능한 자리 — S-15 선례).
- **제안**: :5676 의 `steps` 절에 «① 체크아웃 스텝은 `name:` 을 두지 않는다» 를 한 줄 명시.

### EC-4 (**minor 후보**) — `on` 의 map 양형에서 «⊆» 의 대상이 모호하다

- **계약 :5655**: «**`on` ⊆ `{pull_request, push}`**(list·map 양형 허용)».
- map 양형에서 `⊆` 의 좌변이 **키 집합**인지 값까지 포함한 구조인지 문언이 정하지 않는다.
  M-1 은 하위 필터(`branches`/`types`/`paths`)를 명시적으로 **허용**하므로 «키 집합» 읽기가 옳지만,
  술어 두 개가 갈릴 수 있다.
- **실행기 처분(기록)**: map 이면 **키 집합**과 비교했다(`ctrl-on-map` 이 `BLOB_OK`).

### EC-5 (**minor 후보**) — §12.3.4-G «G-음성-2» 기대값 줄이 M-7 전 시제다

- **계약 :6198-6200**: 기대 = `PREVENTION_INSUFFICIENT` 또는 `PREVENTION_ABSENT`.
- M-7 이후 `(b-blob)@target` 이 **`D=∅` 에서도 발화**하므로, (a) 가 충족되고 워크플로 파일만 없는
  상태에서는 `PREVENTION_UNVERIFIED_REVISION`(전순서 8)이 최종값이 될 수 있다.
- 오늘의 live 는 `ABSENT`(2)가 이겨 문언이 그대로 성립하지만(§13-D), **기대값 열거가 이제 불완전**하다.
- **제안**: G-음성-2 기대에 «또는 `PREVENTION_UNVERIFIED_REVISION`((b-blob)@target 미충족)» 추가.

### EC-6 (**기록만 · 에라타 아님**) — ⑬k(ㄴ)의 «관측면» 이 실행기 밖이다

- **계약 :2903 ⑬k(ㄴ)**: 자기수복 하니스 픽스처에서 «검증 스텝이 먼저 비-0 이라 하니스가 도달조차
  하지 않음을 **비-0·non-ACTIVE 로 실증**한다».
- 실행기는 **blob 과 서버 기록만** 읽으므로 «하니스가 도달했는가»를 직접 관측할 수 없다.
  실행기가 낼 수 있는 것은 ⑬k(ㄱ)(v2.21 순서 blob = red)이고, (ㄴ)의 도달성은 **런타임 부작용**
  (§9-B 의 마커 파일)으로만 관측된다.
- 문언을 «비-0·non-ACTIVE» 로만 읽으면 실행기가 낼 수 없는 것을 기대하게 된다.
  **제안**: (ㄴ)의 관측면을 «런타임 부작용(스텝 rc + 하니스 실행 흔적)» 으로 명시.

### EC-7 (**high 후보**) — `on: [pull_request, push]` 이 (b)② «정확히 1» 을 **과잉 차단**한다

- **계약 `:5655`** 는 `on ⊆ {pull_request, push}` 를 **명시적으로 허용**한다(M-1 이 «bare-only» 핀을
  일부러 두지 않았다).
- **계약 `:5554`·`:5556`** 은 workflow run 정체성을 `path` 와 `head_sha` 로만 묶는다.
  **run 의 `event` 는 계약 어디에도 핀돼 있지 않다**(`event` 문자열 7회 등장 · run 을 묶는 용례 0).
- **귀결**: 두 트리거를 선언한 정직한 워크플로는 같은 head SHA 에 **같은 `path` 의 run 을 둘** 만들고
  각각 `tos-gate` check-run 을 낸다 → `:5559-5560` 의 «정본 path check-run 이 «정확히 1개»» 가
  **정직한 구성을 `PREVENTION_UNVERIFIED_REVISION` 으로 만든다.**
- **실측(§12-c)**: blob 층 `BLOB_OK` ↔ (b)② 서버 층 `UNVERIFIED_REVISION` · rc 1.
  **대조군 v2.21 = `PREVENTION_ACTIVE` rc 0** — v2.22 «신규» 술어가 만든 회귀다.
- **성격**: 방향은 fail-closed(과잉 차단)이라 fail-open 은 아니다.  그러나 **F#4 가 «두 소비자가 같은
  blob 에 다른 결론» 이라며 닫으려던 클래스**가 이번엔 **한 소비자의 두 층 사이**에서 재발했다.
- **계약이 고를 수 있는 것**: (ㄱ) 정본 run 의 `event` 를 핀한다(예 `pull_request`) ·
  (ㄴ) «정확히 1» 을 «≥1 ∧ 정본 path 인 것이 전부 `success`» 로 완화한다 ·
  (ㄷ) `on` 을 bare `pull_request` 로 좁힌다(단 M-1 이 그 핀을 «근거 소멸» 로 삭제했으므로 되돌림이다).

### EC-8 (**high 후보**) — 정본 «잡 템플릿» 에 **코드펜스가 없다**

- **양방향 실측**: `^[[:space:]]*jobs:` **0건 / 7,912행** · 문자열 `jobs` 는 **21행**에 실재
  (부재가 팬텀이 아님).  yaml 펜스는 `:3865`·`:5968` 둘뿐이고 **어느 쪽도 잡 템플릿이 아니다**.
  «정본 잡 템플릿» 7회는 전부 지시적 산문이다.
- **그런데 계약의 어휘는 byte 핀을 전제한다** — `:5605` «계약 «정본 잡 템플릿»과 **구조 대조**» ·
  `:5643` «`jobs.<게이트 잡>` 이 **정본 잡 템플릿**과 (정규화 후) 구조 일치».
- **귀결**: `(b)③` 의 비교 피연산자는 **산문에서 재-파생한 검사들의 논리곱**이고, 두 소비자가 산문을
  다르게 읽으면 갈린다.  **이것은 계약이 이미 두 번 닫은 클래스**다 — 정본 A/B 는 코드펜스로,
  체크아웃 SHA 는 «계약 본문에 값이 없어 술어가 형식만 검사»(R-1)라며 리터럴 핀으로 닫았다.
- **이 실행의 처분**: 재-파생본을 독립 아티팩트로 실체화했다 —
  `canon-job-template.reconstructed.yml` (sha256 `4a4e1f1f46ad7fde126a29fcfb8820ff65254e1f47fc10049caceff3f59befe3`)
  + 17행 파생표 + **판단이 개입한 5자리 명시**.  §3-2 참조.  **«계약에 이런 펜스가 있다» 가 아니라
  «산문을 이렇게 읽었다» 이다.**
- **제안**: `:5676` 근처에 정본 잡 템플릿 **코드펜스를 추가**하거나, 펜스를 두지 않는다면
  «템플릿은 아래 불릿 열거가 정의를 다한다» 를 명시하고 그 열거를 닫힌 집합으로 못박는다.

### EC-9 (**high 후보**) — C-1 순회에 **종료 보장이 없고 «미종료» 에 상태값이 없다**

- **계약 `:5624-5626`** 은 «모든 매핑 노드를 재귀 검사» 라고만 적는다.  `<<` 는 금지되나
  **문서 수준의 평범한 `&anchor`/`*alias` 는 금지돼 있지 않다.**  계약이 anchor 를 보낸 방어
  (`:5649-5650` «yq 확장 + `jobs` 개수 1»)는 **C-1 «이후»** 에 있어 C-1 자신의 순회를 보호하지 못한다.
- **실측(§12-d)**: ① `yaml.compose()` 는 자기참조 anchor 에서 **같은 노드 객체**를 돌려준다 ·
  ② 깊이 상한만 있는 순회는 분기 순환에서 **12초 미종료**(2^depth 폭발) ·
  ③ 판정 파서 `yq` 자신도 분기 순환에서 **`fatal error: stack overflow`(rc 2)** 로 죽고
  단일 체인에서는 **조용히 절단된 유한 구조**를 낸다.
- **미종료는 상태값이 아니다** — `UNVERIFIABLE` 도 아니고 fail-closed 도 아니며 **판정 자체가 없다**
  (실행기의 `trap EXIT` 도 돌지 않는다).  계약의 열 상태값 어디에도 이 자리가 없다.
- **이 실행의 처분**: 노드 «객체 identity» 방문집합 → 순환은 **자기 사유**로 `UNVERIFIED_REVISION`
  (중복 키로 오귀속하지 않는다).  깊이 상한은 벨트.
- **부수 실측**: **v2.21 술어는 `g4-cycle-in-job` 에서 `AttributeError` 로 죽고 `RESULT` 라인을 내지
  않는다.**  실행기의 `case *)` 가 빈 값을 red 로 접어 결과적으로는 차단이지만 **설계가 아니라 우연**이다.
- **제안**: (ㄱ) 정본 템플릿에서 문서 수준 anchor/alias 를 **명시 금지**하거나
  (ㄴ) «구조 순회 불가·미종료» 에 상태값을 배정한다(전순서 1 이 자연스럽다).

### EC-10 (**medium 후보**) — PyYAML 이 어디에도 **버전 핀** 되어 있지 않다

- **실측**: PyYAML 언급 6회(`:224 :2903 :5614 :5620 :5624 :5632`) · **버전 0회**.
- C-1 은 **동결 차단 CRITICAL** 처분이고 그 전부가 PyYAML `.value` 의미론에 얹혀 있다
  (`compose()` 의 anchor 등록 «순서» · 키 노드 `.value` 타입 · 중복 키 보존).
- **비대칭**: 같은 판이 yq 는 `v4.48.x` 로 핀하고 **런타임 `--version` 대조까지** 요구한다(M-4).
  더 무거운 처분을 진 파서가 핀되지 않은 이유가 문언에 없다.
- **이 실행의 처분**: 측정값을 매 run 의 `WF-D0` 라인으로 방출한다 — **PyYAML 6.0.3**.
  이것은 기록이지 핀이 아니다(핀은 계약 소관).

### EC-11 (**medium 후보**) — blob 의 **YAML 파싱 실패** 에 상태값이 배정돼 있지 않다

- 계약은 **fetch** 실패만 나눈다: `:5587` 404/HTTP → `UNVERIFIED_REVISION` ·
  `:5591` 네트워크/인증 → `UNVERIFIABLE`.  **파싱 실패는 미규정**이다.
- **이 실행의 처분(명시)**: compose 층 실패 → `UNVERIFIED_REVISION`(«그 리비전의 워크플로가 정본이
  아니다») · yq 층 실패 → `UNVERIFIABLE`(**v2.21 거동 그대로 · 코드 델타 0**).
- compose 가 «먼저» 돌므로 실무상 파싱 실패는 8 로 접힌다.  두 층이 갈리는 창은 **실재**한다 —
  `g4-cycle-branch` 는 yq 를 stack overflow 로 죽이면서 compose 는 통과시킨다(순환 검사가 벨트로 잡는다).
- **전순서 1 과 8 은 운영자가 할 일이 다르다**(«조회를 못 했다» vs «리비전이 검증되지 않았다») —
  두 소비자가 반대 끝에 착지할 수 있는 자리다.

### EC-12 (**minor 후보**) — `SHELL_OK` 가 **byte 다른 두 표기**로 렌더돼 있다

- `:5753`(정의 자리): `{ bash , bash -euo pipefail {0} , bash -eo pipefail {0} }` — **내부 공백 있음**
- `:224`(변경 이력 행): `{bash, bash -euo pipefail {0}, bash -eo pipefail {0}}` — **내부 공백 없음**
- 원소는 같고 표기만 다르다.  **이 자리가 바로 변경 이력이 «생략부호 제거» 라 부른 F#4 다섯 번째
  자리**다.  S-14 상 정의 자리 `:5753` 이 지배한다.
- **거동 영향 0**: 술어는 세 «원소» 문자열을 쓰므로 두 표기 어느 쪽으로 읽어도 같다.
  그러나 최근 네 번의 심판이 전부 이 클래스에서 갈렸으므로 등재한다.

---

## 15. 스크립트 원문 (sha256 병기)

이 절의 코드펜스가 §4~§13 을 만든 **유일 소스**다.  추출 규약은 §3-0 과 같다 —
«펜스 여는 줄 다음부터 닫는 줄 직전까지» 를 그대로 뜨면 아래 sha256 이 재현된다.

### u17-verify-v222.sh  (sha256 `e97ebdfc87e1985306bb15bdff70585095b8c1f42b46c28ed49e00c9f051bf86` · 591행)

```bash
#!/usr/bin/env bash
# u17-verify (v2.22 동결 8ec22754) — U-17 «예방 통제 활성 증거» 실행기 (계약 8ec22754 §12.3.4 U-17)
#   v2.21 동결 0528a919 실행기(sha256 5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727)
#   에서 파생 — 델타는 **v2.21 재심 처분 4건 + C-1 + M-4/M-2/M-1/M-3** 뿐이고, 그 밖의 전 축은
#   **코드 델타 0**(격리 스냅샷 · host 결속 C6 · PARENTS-UNTRUSTED ㉠㉡㉢ · SHALLOW · (a) 술어 ·
#    countersign · P_first/P_last E9/E11 · 연속성 α · 전순서 10단 · trap EXIT 폐쇄 · responder seam).
#     [F#1 — #1 «회피» 2연속 :5689-5747]  정본 `steps` 순서 반전 [① 체크아웃 · ② 정본 B(sha256 «검증»)
#           · ③ 정본 A(하니스 «실행»)] + 3축(`if:`·`continue-on-error` 키 부재·`SHELL_OK`).
#           **정본 A/B 코드펜스의 «내용»과 두 스텝 `name:` 리터럴은 byte 불변** — 바뀐 것은 순서뿐이다.
#     [M-7 — #2 부분해소 3연속 :5828-5877]  **(b)③ blob 층에 `D` 무관 «무조건 항» `(b-blob)@target` 추가.**
#           `branches/<target>` → `.commit.sha` 를 해석해 **transcript 에 verbatim 수록(필수)** 한 뒤
#           `contents/<wf>?ref=<target HEAD sha>` 를 정본 잡 템플릿과 대조한다.  **«추가»이지 «대체»가
#           아니다** — 기존 D-지표 항 `(b-blob)@d`(`?ref=<PR head.sha>`)는 그대로 유지한다(N-11).
#           404·HTTP 오류 → `PREVENTION_UNVERIFIED_REVISION`(ABSENT 로 접지 않는다) · 네트워크·인증
#           오류 → `PREVENTION_UNVERIFIABLE`.
#     [F#2 — 신규 high :5659-5671·5787-5793]  게이트 체크/잡 이름을 **아티팩트 파라미터에서 계약
#           리터럴 `tos-gate` 로 이동**(선언 3항→2항).  blob 층 `jobs`=1 ∧ 잡 id·`name` 값-핀 ·
#           서버 층 이름 필터 `hit` 의 `len(hit)!=1` → UNVERIFIED_REVISION (술어 파일 소관).
#     [M-3 :5557-5565]  (b)② **path-aware check-run 전수 열거** — 동명 check-run 을 conclusion 으로
#           «먼저 거르지 않고» 전부 열거해 각각을 워크플로 run 으로 해석하고, **정본 `path` 인 것이
#           «정확히 1개» ∧ 그것이 `success`** 여야 한다.  v2.21 은 `conclusion==success` 로 먼저 걸러
#           첫 후보만 봤다 — 그래서 «정본 fail + decoy success» 가 통과했다.
#           **동명·다른 path 의 공존 자체는 red 가 아니다** — 열거 기록만 남긴다((a) 동명 decoy 잔여).
#     [C-1 / M-4 / M-2 / F#4 / M-1]  술어 파일 교체: wfcanon-v221.py → **wfcanon-v222.py**
#           (전 노드 중복 키 검출 · `yq --version` 파서 핀 · `<<` 금지 · 최상위 allowlist ·
#            `permissions`/`runs-on`/checkout `with` 값 전수 핀 · `on` ⊆ {pull_request, push}).
#           PyYAML compose 층이 필요하므로 그 술어만 `$PYBIN`(.venv) 로 돈다 — 실행기 자신의
#           inline JSON 헬퍼는 **`python3` 그대로**(코드 델타 0).
# ── 이하 v2.21 원문 헤더 ─────────────────────────────────────────────────────────
# u17-verify (v2.21 동결 0528a919) — U-17 «예방 통제 활성 증거» 실행기 (계약 0528a919 §12.3.4 U-17)
#   v2.20/에라타 ae842cce 실행기(sha256 67d636ce...) 에서 파생 — 델타는 **v2.21 심판 #1 처분 1건**뿐이다:
#     [(b)3 :5467-5510] «구조 파싱(자작 토크나이저)» -> **«정본 대조»**(YAML 파서 + 정규화 후 byte 비교).
#       술어 파일 교체: wfstruct-v220.py -> wfcanon-v221.py (자작 셸 토크나이저·명령 위치 판별기 폐기 —
#       운영자 «바퀴 재발명 금지» 지침·CLAUDE.md Development Discipline).  서버 잡 스텝 대조(2)·격리 스냅샷·
#       host 결속·U-17-c 10값은 v2.20 거동 그대로(코드 델타 0).
#   v2.19 에라타 6차 실행기(359f5bc5·sha256 174b0c18...) 에서 파생 — 델타는 **v2.20 심판 처분 2건**뿐이다:
#     [#1 — (b)3 :5452-5486] «두 리터럴 grep» -> **구조 파싱 + 서버 스텝 대조** 2층.
#           (1) 서버 blob 을 YAML 파서로 구조 파싱해 jobs.<게이트 잡>.steps[] 의 run: «실행문만» 소비
#               (셸 토크나이즈·# 주석[full-line·trailing] 제거·bash -n 파스 — wfstruct-v220.py)
#           (2) actions/runs/{run_id}/jobs 의 그 잡 conclusion==success 이고 계약 리터럴 두 «스텝 이름»이
#               각각 conclusion==success 로 실재 — 부재·실패 -> PREVENTION_UNVERIFIED_REVISION (T-84 14)
#     [#3 — [PARENTS-UNTRUSTED] :7098-7124] **격리 스냅샷 기층** — 조상성·부모·blob 소비를 진입 시점 HEAD 의
#           git clone --no-local --no-hardlinks (+GIT_NO_REPLACE_OBJECTS=1) 스냅샷 «안에서만» 수행하고,
#           스냅샷 청정성(제2 공집합·grafts 부재·제1 일치)을 canary 로 방출한다.  clone 실패는 **fail-closed**.
#           원 저장소 관측은 «리뷰 보조»로 격하돼 기록만 남는다.
#   v2.19 에라타 5차 실행기(eddbd241·sha256 cd3e9e1e…) 에서 파생 — 델타는 **에라타 6차 [E15] 1건**뿐이다:
#     [E15 — stop-time BLOCK] 파생 경로 결합 base 를 **«저장소 루트(`git rev-parse --show-toplevel`)»만**으로 고정한다.
#           **`--absolute-git-dir` 결합은 «철회»** — `<root>/.git` + `.git/info/grafts` = **이중 `.git`**(`<root>/.git/.git/info/grafts`)
#           이라 실제 graft 를 «거짓 ABSENT» 로 읽고 ㉡ 이 통과 = **fail-open**(stop-time 실측·addendum-5 가 이를 «fail-closed»로 오분류).
#     [E15 극성 규율] **«거짓 부재(ABSENT)»가 «검사를 통과»시키면 그것은 fail-open 이다** — 부재의 극성은 «검사 방향»이 정한다.
#           `--git-path` 절대 출력(`--separate-git-dir`·linked worktree)은 **그대로** 쓴다(결합 금지).  동등 대안: `git -C <루트> rev-parse --git-path <x>` + 그 cwd 검사.
#   (E1~E14 는 eddbd241 실행기 거동 그대로 — 이 실행기는 이미 `--show-toplevel` 결합만 쓴다·코드 델타 0, 주석·헤더만.)
#   (E1·E2·E3·E6·E8②·E9·E10·E11 은 f6493d23 실행기 거동 그대로 — 코드 델타 0.)
#   (E1·E2·E3·E6·E8②·E9 는 ad5be1a3 실행기 거동 그대로 — 코드 델타 0.)
#   §12.3.4-R 하니스와 «별도». run 은 stdout 의 `U17-0 target=…` 라인이 연다.  전순서 10단 · exit 0 = ACTIVE 만 · trap EXIT 폐쇄.
# 사용: bash u17-verify-v219.sh [<repo-dir>]      (env: U17_RESPONDER=gh|file:<dir>|mixed:<dir> · U17_CAPTURE_DIR)
set -u -o pipefail
CANON=github.com/kakao-harris-lee/kis_unified_sts     # 계약 핀 (C3)
PIN_HOST=${CANON%%/*}                                 # [C6] 핀 host — 계약 핀에서 «파생»(아티팩트 선언 아님)
WF_PATH=.github/workflows/tos-gate.yml                # 계약 리터럴 (C2)
LIT1=tools/tos_entry_harness.sh                       # 계약 리터럴 (R2-i)
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d   # 계약 리터럴 (R2-ii) — §12.3.4-R 블록 sha256
WFCANON="${U17_WFCANON:-$(dirname "$0")/wfcanon-v222.py}"     # [v2.22] «정본 잡 템플릿» 술어 (C-1 전 노드 중복 + 파서 핀 + 값 전수 핀)
PYBIN="${U17_PYBIN:-/Users/harris/Development/private/kis_unified_sts/.venv/bin/python}"  # [v2.22] 술어의 PyYAML compose 층 전용 (시스템 python3 에는 PyYAML 부재)
GATE_JOB=tos-gate                                     # [v2.22·F#2/N-4] 계약 리터럴 — 잡 id == 표시 이름 == required context (아티팩트 파라미터 아님)
INHERITED_GH_HOST="${GH_HOST-∅(미설정)}"              # [C6] 재핀 «전» 상속값 기록
export GH_HOST="$PIN_HOST"                            # [C6] ③ 소비자 자기 환경 재핀 (플래그·환경 이중 결속)
export GIT_NO_REPLACE_OBJECTS=1     # [E8] ② 무력화 — 모든 조상·부모 파생 git 호출이 replace 뷰를 따르지 않는다
EMITTED=0
emit() { EMITTED=1; printf 'prevention_control_state=%s\nreason=%s\n' "$1" "$2"; [ "$1" = PREVENTION_ACTIVE ] && exit 0; exit 1; }
trap '[ "$EMITTED" -eq 1 ] || { printf "prevention_control_state=%s\nreason=%s\n" PREVENTION_UNVERIFIABLE "판정 미산출 상태로 종료(fail-closed)"; exit 1; }' EXIT
cd "${1:-.}" || emit PREVENTION_UNVERIFIABLE "repo 진입 실패"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
CFG=config/tos_completion.yaml
RESP="${U17_RESPONDER:-gh}"
CAP="${U17_CAPTURE_DIR:-$(mktemp -d)}"; mkdir -p "$CAP"
utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }
key() { printf '%s' "$1" | tr '/?=&' '____'; }
# 상태 수집기: RANK[상태]=순위 · 발화한 상태와 사유를 모았다가 최소 순위 방출
rank() { case "$1" in PREVENTION_UNVERIFIABLE) echo 1;; PREVENTION_ABSENT) echo 2;; PREVENTION_UNSIGNED) echo 3;; PREVENTION_TARGET_MISMATCH) echo 4;; PREVENTION_INSUFFICIENT) echo 5;; PREVENTION_LATE) echo 6;; PREVENTION_ARTIFACT_MUTATED) echo 7;; PREVENTION_UNVERIFIED_REVISION) echo 8;; PREVENTION_CONTINUITY_UNVERIFIABLE) echo 9;; *) echo 99;; esac; }
FIRED=""; NF=0; fire() { NF=$((NF+1)); FIRED="$FIRED$1|$2"$'\n'; printf 'U17-fire %s: %s\n' "$1" "$2"; }
finish() { local best="" bestr=99 f s r; while IFS= read -r f; do [ -n "$f" ] || continue; s=${f%%|*}; r=$(rank "$s"); if [ "$r" -lt "$bestr" ]; then bestr=$r; best="$f"; fi; done <<< "$FIRED"
  if [ -n "$best" ]; then emit "${best%%|*}" "${best#*|} [수집 ${NF}건 중 전순서 최소]"; fi; emit PREVENTION_ACTIVE "$1"; }

# ── responder seam  ([C6] gh 경로의 모든 조회에 --hostname <핀 host> 명시 · 헤더 별도 보존)
respond() {
  local path="$1" k; k=$(key "$1"); local st="$CAP/$k.status" bd="$CAP/$k.body" hd="$CAP/$k.hdr"
  case "$RESP" in
    gh)  local out; out=$(gh api -i --hostname "$PIN_HOST" "$path" 2>"$CAP/$k.err"); printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"
         printf '%s\n' "$out" | awk '/^\r?$/{exit} {print}' | tr -d '\r' > "$hd"
         printf '%s\n' "$out" | awk 'f{print} /^\r?$/{f=1}' | tr -d '\r' > "$bd"
         if ! grep -Eq '^[0-9]{3}$' "$st"; then printf 'ERR\n' > "$st"; cat "$CAP/$k.err" > "$bd" 2>/dev/null; return 1; fi; return 0 ;;
    file:*) local dir="${RESP#file:}"
         if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; : > "$hd"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'ERR\n' > "$st"; printf 'SIMULATED responder: no injected response for %s\n' "$path" > "$bd"; : > "$hd"; return 1; fi ;;
    mixed:*) local dir="${RESP#mixed:}"
         if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; : > "$hd"; printf 'U17-seam %s ← file(SIMULATED)\n' "$path"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'U17-seam %s ← gh(live)\n' "$path"; local save="$RESP"; RESP=gh; respond "$path"; local r=$?; RESP="$save"; return $r; fi ;;
    *) emit PREVENTION_UNVERIFIABLE "알 수 없는 responder: $RESP" ;;
  esac
}
reqid() { grep -i '^X-GitHub-Request-Id:' "$CAP/$(key "$1").hdr" 2>/dev/null | head -1 | tr -d '\r' | sed 's/^[Xx]-[Gg]it[Hh]ub-[Rr]equest-[Ii]d:[[:space:]]*//'; }
show_capture() { local k; k=$(key "$2"); printf 'U17-%s %s  utc=%s  http=%s  x-github-request-id=%s\n' "$1" "$2" "$(utc)" "$(cat "$CAP/$k.status")" "$(reqid "$2")"; sed 's/^/  | /' "$CAP/$k.body"; }
jget() { python3 -c 'import json,sys
try:
    j=json.load(open(sys.argv[1]))
    for kk in sys.argv[2].split("."):
        j=j[int(kk)] if isinstance(j,list) else j[kk]
    print(j if not isinstance(j,(dict,list)) else json.dumps(j))
except Exception: print("")' "$CAP/$(key "$1").body" "$2" 2>/dev/null; }
http_of() { cat "$CAP/$(key "$1").status" 2>/dev/null; }
ok2xx() { printf '%s' "$1" | grep -Eq '^2'; }
# ── [PARENTS-UNTRUSTED / E8] 부모 집합 신뢰 판별 — (1) 얕은 경계(국소) · (2) 재작성(전역 관측)
# [E13] 저장소 내부 경로는 «파생»만 — 리터럴 `.git/…` 금지.  (`--git-path` 는 일반 배치에서 상대 경로를 주므로 cwd=repo 전제 · L-1)
# [E14+E15] 파생 + «결합»: 상대면 **저장소 루트(--show-toplevel)** 와 결합, 절대면 그대로.  cwd 상대 검사 금지 · --absolute-git-dir 결합 금지(이중 .git = 거짓 ABSENT = fail-open).
TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || printf '.')
# [v2.20 D-γ] 결합 base 를 «호출 시점»에 파생한다 — 격리 스냅샷으로 cwd 가 바뀐 뒤 캐시된 TOPLEVEL 을 쓰면
#   스냅샷의 grafts 를 «원 저장소 경로»로 검사해 «거짓 ABSENT» 가 된다(E15 극성 규율의 재발 표면).
gitpath() { local v t; v=$(git rev-parse --git-path "$1" 2>/dev/null); t=$(git rev-parse --show-toplevel 2>/dev/null || printf '%s' "$TOPLEVEL"); case "$v" in /*) printf '%s' "$v";; "") printf '';; *) printf '%s/%s' "$t" "$v";; esac; }
GITDIR_ABS=$(git rev-parse --absolute-git-dir 2>/dev/null || printf '')
SHALLOW_PATH=$(gitpath shallow); GRAFTS_PATH=$(gitpath info/grafts)
IS_SHALLOW=$(git rev-parse --is-shallow-repository 2>/dev/null || echo unknown)
SHALLOW_LIST=$( [ -f "$SHALLOW_PATH" ] && tr '\n' ' ' < "$SHALLOW_PATH" || printf '' )
REPLACE_LIST=$(git replace -l 2>/dev/null | tr '\n' ' ')
GRAFTS_PRESENT=$( [ -f "$GRAFTS_PATH" ] && echo yes || echo no )
have_commit() { git cat-file -e "$1^{commit}" 2>/dev/null; }
# ── [E10 ㉠] 주 판별 — 부모 집합 «구조 재파생»(커밋 객체의 parent 줄 직접 파싱).  판정의 모든 ∀p 항이 이것을 쓴다.
parents_true() { git --no-replace-objects cat-file commit "$1" 2>/dev/null | awk '/^$/{exit} /^parent /{printf "%s ", $2}'; }
# ── [E10 ㉠ 대조] «이력 뷰»가 주는 부모 — 무력화를 «걷어내고» 관측한다(재작성 여부를 보려면 뷰를 그대로 봐야 한다)
parents_ambient() { env -u GIT_NO_REPLACE_OBJECTS git log --format=%P -1 "$1" 2>/dev/null; }
nset() { printf '%s\n' $1 | sort | tr '\n' ' '; }
# 함수는 «명령 치환 서브셸»에서 도므로 결과를 변수로 되돌릴 수 없다 — 파일로 누적한다.
PUF=$(mktemp); PUC=$(mktemp); PUL=$(mktemp); : > "$PUF"; : > "$PUC"; : > "$PUL"
# [E12] 절차 순서 = ㉢ 먼저: 얕은 경계로 «특정»되는 불일치는 국소 귀속($PUL)하고, «남는» 것만 전역($PUF)으로 올린다.
check_parents() { local x="$1" tp ap b
  printf '%s\n' "$x" >> "$PUC"
  tp=$(nset "$(parents_true "$x")"); ap=$(nset "$(parents_ambient "$x")")
  [ "$tp" = "$ap" ] && return 0
  for b in $SHALLOW_LIST; do [ "$b" = "$x" ] && { printf '%s[㉢ 얕은 경계 귀속 — 재파생=(%s) vs 뷰=(%s)]\n' "$x" "${tp% }" "${ap% }" >> "$PUL"; return 0; }; done
  printf '%s[재파생=(%s) vs 뷰=(%s)]\n' "$x" "${tp% }" "${ap% }" >> "$PUF"; return 1; }
# ── [E10 ㉢] 국소 — 그 커밋의 부모 «객체»가 미상인가 (E6: 전역 단축 아님)
is_boundary() { local x="$1" b p; for b in $SHALLOW_LIST; do [ "$b" = "$x" ] && return 0; done
  for p in $(parents_true "$x"); do have_commit "$p" || return 0; done; return 1; }

# ── [C3] 핀·원격 대조 (host 보존 정규화)
PIN_OR=${CANON#*/}
norm_url() { printf '%s' "$1" | sed -E 's#^https?://([^/]+)/(.+)$#\1/\2#; s#^ssh://git@([^/]+)/(.+)$#\1/\2#; s#^git@([^:]+):(.+)$#\1/\2#; s#\.git$##; s#/$##'; }
REMOTES=$(git remote -v 2>/dev/null | awk '{print $1" "$2}' | sort -u)
MATCH_REMOTE=""; NORMED=""
while read -r rn ru; do [ -n "${ru:-}" ] || continue; n=$(norm_url "$ru"); NORMED="$NORMED $rn=$n"; [ "$n" = "$CANON" ] && MATCH_REMOTE="$rn"; done <<< "$REMOTES"
# ── [v2.20 — 심판 #3] 격리 스냅샷 기층 (계약 3d17ea66 :7098-7124) ─────────────────────────────
#   조상성·부모·blob 을 소비하는 «모든» 판정을 진입 시점 HEAD 의 격리 스냅샷 «안에서만» 수행한다.
#   원격 관측(위 [C3])은 원 저장소 «설정»이라 스냅샷 «전»에 끝내고, 아래부터는 스냅샷이 기층이다.
ORIGIN=$(pwd -P); ENTRY_HEAD=$(git rev-parse HEAD 2>/dev/null || printf '')
printf 'U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[%s] · %s=%s · is_shallow=%s · entry HEAD=%s\n' \
  "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "${ENTRY_HEAD:-∅}"
[ -n "$ENTRY_HEAD" ] || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 진입 시점 HEAD 파생 불가"
SNAPBASE=$(mktemp -d); SNAP="$SNAPBASE/snap"
printf 'U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks %s %s\n' "$ORIGIN" "$SNAP"
GIT_NO_REPLACE_OBJECTS=1 git clone --quiet --no-local --no-hardlinks "$ORIGIN" "$SNAP" 2>"$CAP/clone.err"; CRC=$?
printf 'U17-SNAP clone rc=%s\n' "$CRC"; [ -s "$CAP/clone.err" ] && sed 's/^/  | /' "$CAP/clone.err"
[ "$CRC" -eq 0 ] || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] clone 실패(rc=$CRC) — 정직 경계 (a): 원본 grafts 가 참 부모를 도달 불가로 만들면 스냅샷 «생성»이 실패한다(거짓 통과 없음·fail-closed)"
git -C "$SNAP" cat-file -e "$ENTRY_HEAD^{commit}" 2>/dev/null || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 진입 HEAD($ENTRY_HEAD) 가 스냅샷에 부재 — 핀 실패 fail-closed"
git -C "$SNAP" checkout --quiet --detach "$ENTRY_HEAD" 2>/dev/null || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 진입 HEAD 체크아웃 실패"
cd "$SNAP" || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 스냅샷 진입 실패"
# ㉠㉡㉢ 는 스냅샷 «안에서» 재파생한다 (계약: 스냅샷 안 ㉡ = 기층이 깨끗함을 고정하는 canary)
SHALLOW_PATH=$(gitpath shallow); GRAFTS_PATH=$(gitpath info/grafts)
IS_SHALLOW=$(git rev-parse --is-shallow-repository 2>/dev/null || echo unknown)
SHALLOW_LIST=$( [ -f "$SHALLOW_PATH" ] && tr '\n' ' ' < "$SHALLOW_PATH" || printf '' )
REPLACE_LIST=$(git replace -l 2>/dev/null | tr '\n' ' ')
GRAFTS_PRESENT=$( [ -f "$GRAFTS_PATH" ] && echo yes || echo no )
CAN_MIS=0; for x in $(git rev-list --all 2>/dev/null); do
  tp=$(nset "$(parents_true "$x")"); ap=$(nset "$(parents_ambient "$x")"); [ "$tp" = "$ap" ] || CAN_MIS=$((CAN_MIS+1)); done
printf 'U17-SNAP canary(스냅샷 «안»): HEAD=%s · replace -l=[%s] · %s=%s · is_shallow=%s · ㉠(cat-file 부모 == %%P) 불일치 %s건 / 커밋 %s개\n' \
  "$(git rev-parse HEAD)" "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "$CAN_MIS" "$(git rev-list --all | grep -c .)"
[ "$CAN_MIS" -eq 0 ] || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷 canary] 스냅샷 안에서 ㉠ 불일치 ${CAN_MIS}건 — 기층 오염(--local 폴백·번들 오용 표면)"


# ── [C6 ①] 전제: 핀 host 인증  (responder=file 은 live 조회가 없으므로 SIMULATED 로 기록만)
AUTHRC=0; AUTHOUT=""; AUTHMODE=live
AUTHCMD="gh auth status --hostname $PIN_HOST"                     # [C6] 표시·사유 문자열 (대조군은 이 줄과 다음 줄이 함께 바뀐다)
case "$RESP" in file:*) AUTHMODE=simulated ;; *) AUTHOUT=$(gh auth status --hostname "$PIN_HOST" 2>&1); AUTHRC=$? ;; esac

# ── [C2] Actions app id 서버 파생 · [C3] target = 핀 repo default_branch  (A00·A0)
respond "apps/github-actions"; ST_APP=$(http_of "apps/github-actions"); APPID=$(jget "apps/github-actions" id)
respond "repos/$PIN_OR";       ST0=$(http_of "repos/$PIN_OR");          TARGET=$(jget "repos/$PIN_OR" default_branch)
printf 'U17-0 target=%s@%s\n' "$PIN_OR" "${TARGET:-UNRESOLVED}"
printf 'U17-0 pin=%s remotes:%s match=%s | actions_app_id=%s (apps/github-actions http=%s) | responder=%s capture_dir=%s\n' "$CANON" "${NORMED:- (none)}" "${MATCH_REMOTE:-∅}" "${APPID:-∅}" "$ST_APP" "$RESP" "$CAP"
printf 'U17-H [C6] pin_host=%s (계약 핀에서 파생) · 상속 GH_HOST=%s → 현행 GH_HOST=%s · auth 전제 `%s` → mode=%s rc=%s\n' "$PIN_HOST" "$INHERITED_GH_HOST" "${GH_HOST-∅(재핀 없음)}" "$AUTHCMD" "$AUTHMODE" "$AUTHRC"
if [ "$AUTHMODE" = live ]; then printf '%s\n' "$AUTHOUT" | sed 's/^/  | /'; else printf '  | (responder=%s — live 조회 없음: 주입 응답 위 결정적 술어)\n' "$RESP"; fi
[ "$AUTHMODE" != live ] || [ "$AUTHRC" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[C6] \`$AUTHCMD\` 실패(rc=$AUTHRC) — 핀 host 인증 부재 (타 host 폴백 없음)"
# [E8 ①] 전역 관측 — 부모 «재작성» 축 (replace ref · info/grafts 파생 경로).  얕음은 국소(E6)라 여기서 발화하지 않는다.
printf 'U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[%s] · %s(--git-path 파생)=%s · ㉢ is_shallow=%s · %s(--git-path 파생) 목록=[%s] · git-dir=%s · 무력화 GIT_NO_REPLACE_OBJECTS=%s · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄\n' \
  "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "$SHALLOW_PATH" "$(printf '%s ' $SHALLOW_LIST)" "$GITDIR_ABS" "${GIT_NO_REPLACE_OBJECTS:-∅}"
NREP=$(printf '%s\n' $REPLACE_LIST | grep -c .)
[ "$NREP" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED] git replace -l 비공집합(${NREP}건: $(printf '%s ' $REPLACE_LIST)) — 부모 집합 재작성 = 신뢰 불가"
[ "$GRAFTS_PRESENT" = no ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED] $GRAFTS_PATH 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)"
show_capture A00 "apps/github-actions"; printf 'U17-A0 repos/%s  utc=%s  http=%s  x-github-request-id=%s  (.default_branch=%s)\n' "$PIN_OR" "$(utc)" "$ST0" "$(reqid "repos/$PIN_OR")" "${TARGET:-∅}"
{ ok2xx "$ST_APP" && [ -n "$APPID" ]; } || fire PREVENTION_UNVERIFIABLE "apps/github-actions 조회 실패(http=$ST_APP) — Actions app id 파생 불가"
{ ok2xx "$ST0" && [ -n "$TARGET" ]; }   || fire PREVENTION_UNVERIFIABLE "repos/$PIN_OR 조회 실패(http=$ST0) — default_branch 파생 불가"
[ -n "$MATCH_REMOTE" ] || fire PREVENTION_TARGET_MISMATCH "계약 핀 $CANON 과 일치하는 원격 부재 (git remote -v 정규화:${NORMED:- none})"

# ── 아티팩트 (전순서 2 ABSENT · 대조값·countersign)  — 커밋-전용 읽기
BODY=$(git show "HEAD:$PC" 2>/dev/null) || { fire PREVENTION_ABSENT "아티팩트 HEAD 부재: $PC"; BODY=""; }
yv() { printf '%s\n' "$BODY" | sed -n "s/^$1:[[:space:]]*//p" | sed 's/[[:space:]]*#.*$//; s/[[:space:]]*$//' | head -1; }
DECL_OR=$(yv owner_repo); DECL_TB=$(yv target_branch)
CHECK="$GATE_JOB"   # [v2.22·F#2/N-4] 계약 리터럴 — «선언하지 않으면 고를 수 없다»(선례 gate_app_id·remote_name)
[ -z "$(yv tos_gate_check)" ] || printf 'U17-note 아티팩트에 tos_gate_check 키가 있으나 v2.22 는 폐지(무시) — 계약 리터럴 %s 사용\n' "$CHECK"
[ -z "$(yv gate_app_id)" ] || printf 'U17-note 아티팩트에 gate_app_id 키가 있으나 v2.18 은 폐지(무시) — 서버 파생값 %s 사용\n' "$APPID"
[ -z "$(yv remote_name)" ]  || printf 'U17-note 아티팩트에 remote_name 키가 있으나 v2.18 은 폐지(무시) — 핀 대조는 원격 이름을 묻지 않는다\n'
DECL_HOST=$(yv host)
if [ -n "$BODY" ]; then
  MM=""   # [E2] 선언 키는 «선택» — 있으면 대조, 없으면 핀·API 파생이 유일 소스
  if [ -n "$DECL_OR" ]; then case "$DECL_OR" in "$CANON"|"$PIN_OR") ;; *) MM="$MM owner_repo(선언=$DECL_OR ≠ 핀=$CANON)";; esac; fi
  if [ -n "$DECL_TB" ] && [ -n "$TARGET" ] && [ "$DECL_TB" != "$TARGET" ]; then MM="$MM target_branch(선언=$DECL_TB ≠ 핀 repo default=$TARGET)"; fi
  # [E3] host 키도 «선택 대조» — 있으면 핀 host 와 대조, 없으면 핀이 유일 소스 (선언으로 host 를 «고를» 수 없다)
  if [ -n "$DECL_HOST" ] && [ "$DECL_HOST" != "$PIN_HOST" ]; then MM="$MM host(선언=$DECL_HOST ≠ 핀 host=$PIN_HOST)"; fi
  printf 'U17-T declared-vs-pin: %s (declared owner_repo=%s target_branch=%s host=%s)\n' "${MM:-일치/선언 없음}" "${DECL_OR:-∅(선택 키 부재 → 핀 유일 소스)}" "${DECL_TB:-∅(선택 키 부재 → default_branch 유일 소스)}" "${DECL_HOST:-∅(선택 키 부재 → 핀 host 유일 소스)}"
  [ -z "$MM" ] || fire PREVENTION_TARGET_MISMATCH "아티팩트 선언값이 계약 핀/파생값과 불일치:$MM"
  CS_RE='^operator_countersign:[[:space:]]*"[^"[:space:]][^"]* [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"[[:space:]]*(#.*)?$'
  nk=$(printf '%s\n' "$BODY" | grep -c '^operator_countersign:')
  if [ "$nk" != 1 ]; then fire PREVENTION_UNSIGNED "operator_countersign 키 출현 횟수=$nk (정확히 1 요구)"
  elif ! printf '%s\n' "$BODY" | grep -Eq "$CS_RE"; then fire PREVENTION_UNSIGNED "operator_countersign 값 형식 위반: $(printf '%s\n' "$BODY" | grep '^operator_countersign:')"; fi
fi

# ── (a) 4 엔드포인트 (핀 repo · 파생 target)
APPLIED_IDS=""
if [ -n "$TARGET" ]; then
P_PROT="repos/$PIN_OR/branches/$TARGET/protection"; P_RULES="repos/$PIN_OR/rules/branches/$TARGET"; P_RSETS="repos/$PIN_OR/rulesets"
respond "$P_PROT";  show_capture A1 "$P_PROT"
respond "$P_RULES"; show_capture A2 "$P_RULES"
respond "$P_RSETS"; show_capture A3 "$P_RSETS"
# [α] 연속성 입력우주 = target 에 «적용된» 룰셋만 (rules/branches/{target} 의 ruleset_id) — rulesets 목록 전체가 아니다
APPLIED_IDS=$(python3 -c 'import json,sys
ids=[]
try:
    a=json.load(open(sys.argv[1]))
    for r in a if isinstance(a,list) else []:
        if isinstance(r,dict) and r.get("ruleset_id") is not None and str(r["ruleset_id"]) not in ids: ids.append(str(r["ruleset_id"]))
except Exception: pass
print(" ".join(ids))' "$CAP/$(key "$P_RULES").body" 2>/dev/null)
RSIDS=$(python3 -c 'import json,sys
ids=set()
for f in sys.argv[1:]:
    try:
        a=json.load(open(f))
        for r in a if isinstance(a,list) else []:
            if isinstance(r,dict):
                if r.get("ruleset_id") is not None: ids.add(str(r["ruleset_id"]))
                elif r.get("id") is not None and "enforcement" in r: ids.add(str(r["id"]))
    except Exception: pass
print(" ".join(sorted(ids)))' "$CAP/$(key "$P_RULES").body" "$CAP/$(key "$P_RSETS").body" 2>/dev/null)
for id in $RSIDS; do respond "repos/$PIN_OR/rulesets/$id"; show_capture A4 "repos/$PIN_OR/rulesets/$id"; done
[ -n "$RSIDS" ] || printf 'U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)\n'
printf 'U17-α0 적용 룰셋(연속성 입력우주) = [%s]  (rules/branches/%s 의 ruleset_id · rulesets 목록 전체=[%s])\n' "$(printf '%s' "$APPLIED_IDS")" "$TARGET" "$(printf '%s' "$RSIDS")"
A_STATE=$(python3 - "$CAP" "$PIN_OR" "$TARGET" "$CHECK" "${APPID:-}" <<'PY'
import json,sys,os
cap,orepo,target,check,appid=sys.argv[1:6]
def key(p): return p.replace('/','_').replace('?','_').replace('=','_').replace('&','_')
def load(p):
    try:
        st=open(os.path.join(cap,key(p)+'.status')).read().strip(); body=open(os.path.join(cap,key(p)+'.body')).read()
    except Exception: return "ERR",None
    try: js=json.loads(body) if body.strip() else None
    except Exception: js=None
    return st,js
def unverifiable(st): return st=="ERR" or (st.isdigit() and st!="404" and not st.startswith("2"))
st_p,prot=load(f"repos/{orepo}/branches/{target}/protection"); st_r,rules=load(f"repos/{orepo}/rules/branches/{target}"); st_s,rsets=load(f"repos/{orepo}/rulesets")
if unverifiable(st_p) or unverifiable(st_r) or unverifiable(st_s):
    print("PREVENTION_UNVERIFIABLE|http/network/auth: protection=%s rules=%s rulesets=%s"%(st_p,st_r,st_s)); sys.exit(0)
why=[]; prot_ok=False
if st_p.startswith("2") and isinstance(prot,dict):
    rsc=prot.get("required_status_checks") or {}
    ctx=rsc.get("contexts") or [c.get("context") for c in (rsc.get("checks") or [])]
    if check not in (ctx or []): why.append(f"contexts∌{check}")
    else:
        # [C1] checks[] 의 그 컨텍스트 app_id == Actions app id (이름은 정체성이 아니다)
        cks=[c for c in (rsc.get("checks") or []) if c.get("context")==check]
        if not cks: why.append(f"checks[] 에 {check} 항목 부재(app_id 확인 불가)")
        elif not any(str(c.get("app_id"))==str(appid) for c in cks): why.append(f"checks[{check}].app_id={[c.get('app_id') for c in cks]}≠Actions {appid}")
    if rsc.get("strict") is not True: why.append("strict≠true")
    if (prot.get("enforce_admins") or {}).get("enabled") is not True: why.append("enforce_admins≠true")
    if (prot.get("allow_force_pushes") or {}).get("enabled") is not False: why.append("allow_force_pushes.enabled≠false(부재 포함)")
    if (prot.get("allow_deletions") or {}).get("enabled") is not False: why.append("allow_deletions.enabled≠false(부재 포함)")
    if "required_pull_request_reviews" not in prot: why.append("required_pull_request_reviews 키 부재")
    restr=prot.get("restrictions")
    if isinstance(restr,dict) and (restr.get("apps") or []): why.append("restrictions.apps≠[]")
    prot_ok = not why
elif st_p=="404": why.append("protection 404")
rs_ok=False; rs_why=[]; applied=rules if isinstance(rules,list) else []
if applied:
    types={r.get("type") for r in applied}; ids={r.get("ruleset_id") for r in applied}
    def rsc_ok():
        for r in applied:
            if r.get("type")=="required_status_checks":
                p=r.get("parameters") or {}
                if p.get("strict_required_status_checks_policy") is True and any(c.get("context")==check and str(c.get("integration_id"))==str(appid) for c in p.get("required_status_checks") or []): return True
        return False
    if not rsc_ok(): rs_why.append(f"required_status_checks{{strict,context∋{check},integration_id=={appid}}} 없음")
    for t in ("pull_request","non_fast_forward","deletion"):
        if t not in types: rs_why.append(f"rule {t} 없음")
    for i in ids:
        st_i,rs=load(f"repos/{orepo}/rulesets/{i}")
        if unverifiable(st_i): print("PREVENTION_UNVERIFIABLE|rulesets/%s http=%s"%(i,st_i)); sys.exit(0)
        if not isinstance(rs,dict): rs_why.append(f"rulesets/{i} 본문 없음"); continue
        if rs.get("enforcement")!="active": rs_why.append(f"rulesets/{i}.enforcement={rs.get('enforcement')}")
        if "bypass_actors" not in rs: rs_why.append(f"rulesets/{i}.bypass_actors 키 부재(불충족)")
        elif rs.get("bypass_actors")!=[]: rs_why.append(f"rulesets/{i}.bypass_actors≠[]")
    rs_ok = not rs_why
else: rs_why.append("적용 규칙 0")
if prot_ok or rs_ok: print("PREVENTION_ACTIVE|(a) 술어 충족: classic=%s ruleset=%s"%(prot_ok,rs_ok)); sys.exit(0)
if st_p=="404" and not applied: print("PREVENTION_ABSENT|protection 404 ∧ 적용 규칙 0 (룰셋 목록=%s)"%(len(rsets) if isinstance(rsets,list) else "n/a")); sys.exit(0)
print("PREVENTION_INSUFFICIENT|classic:[%s] ruleset:[%s]"%("; ".join(why),"; ".join(rs_why)))
PY
)
[ -n "$A_STATE" ] || A_STATE="PREVENTION_UNVERIFIABLE|(a) 캡처 평가 함수가 값을 내지 못함(파서 오류)"
A_VAL=${A_STATE%%|*}; A_WHY=${A_STATE#*|}
printf 'u17_live_state=%s\nu17_live_reason=%s\n' "$A_VAL" "$A_WHY"
[ "$A_VAL" = PREVENTION_ACTIVE ] || fire "$A_VAL" "(a) $A_WHY"
fi

# ── [v2.22·M-7] (b-blob)@target — «D 무관 무조건 항» (계약 :5566-5591 · :5828-5849)
#    진입선(D=∅)에서도 «항상» 평가한다.  이것이 없으면 진입 판정이 blob 을 한 줄도 읽지 않는다(vacuity).
BT_STATE=NOT_EVALUATED
if [ -n "$TARGET" ]; then
  BQ="repos/$PIN_OR/branches/$TARGET"; respond "$BQ"; show_capture BT0 "$BQ"; BST=$(http_of "$BQ")
  if [ "$BST" = ERR ]; then BT_STATE=UNVERIFIABLE; fire PREVENTION_UNVERIFIABLE "(b-blob)@target branches/$TARGET 네트워크/인증 오류"
  elif ! ok2xx "$BST"; then BT_STATE=UNVERIFIED_REVISION; fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target branches/$TARGET http=$BST"
  else
    THSHA=$(jget "$BQ" commit.sha)
    printf 'U17-BT [M-7] target HEAD sha = %s   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)\n' "${THSHA:-∅(파생 불가)}"
    if [ -z "$THSHA" ]; then BT_STATE=UNVERIFIED_REVISION; fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target branches/$TARGET 의 .commit.sha 파생 불가"
    else
      TQ="repos/$PIN_OR/contents/$WF_PATH?ref=$THSHA"; respond "$TQ"; show_capture BT1 "$TQ"; TST=$(http_of "$TQ")
      if [ "$TST" = ERR ]; then BT_STATE=UNVERIFIABLE; fire PREVENTION_UNVERIFIABLE "(b-blob)@target contents 조회 네트워크/인증 오류 — $TQ"
      elif ! ok2xx "$TST"; then BT_STATE=UNVERIFIED_REVISION
        fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target http=$TST ($WF_PATH 가 target HEAD $THSHA 에 부재) — ABSENT 로 접지 않는다(전순서 2 vs 8)"
      else
        TWF=$(python3 -c 'import json,sys,base64
try:
    j=json.load(open(sys.argv[1])); enc=j.get("encoding"); c=j.get("content","")
    sys.stdout.write(base64.b64decode(c).decode("utf-8","replace") if enc=="base64" else str(c))
except Exception: sys.stdout.write("")' "$CAP/$(key "$TQ").body")
        printf 'U17-BT1 decoded %s@%s (target HEAD · encoding=%s size=%s):\n' "$WF_PATH" "$THSHA" "$(jget "$TQ" encoding)" "$(jget "$TQ" size)"
        printf '%s\n' "$TWF" | sed 's/^/  | /'
        TWFF="$CAP/$(key "$TQ").wf.yml"; printf '%s\n' "$TWF" > "$TWFF"
        TOUT=$("$PYBIN" "$WFCANON" blob "$TWFF" 2>&1)
        printf '%s\n' "$TOUT" | sed 's/^/  | /'
        TRES=$(printf '%s\n' "$TOUT" | sed -n 's/^RESULT=//p' | tail -1)
        case "$TRES" in
          BLOB_OK) BT_STATE=OK ;;
          UNVERIFIABLE) BT_STATE=UNVERIFIABLE; fire PREVENTION_UNVERIFIABLE "(b-blob)@target 정본 잡 대조 불가(파서 핀 불일치·YAML 파서 실패)" ;;
          *) BT_STATE=UNVERIFIED_REVISION; fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=$THSHA · T-84 ⑬)" ;;
        esac
      fi
    fi
  fi
else
  printf 'U17-BT [M-7] target 미파생 — (b-blob)@target 평가 불가 (전순서 1 이 이미 발화)\n'
fi
printf 'U17-BT (b-blob)@target 판정 = %s   [무조건 항 · D 와 무관]\n' "$BT_STATE"

# ── (c) P_first / P_last · D  (구조 정의 · 후보 = --full-history)
# [SHALLOW/E5] 후보 우주 안에 «경계 커밋»이 있으면 그 x 를 도입 지점으로 «확정하지 않는다».
# 함수는 «명령 치환 서브셸»에서 돌므로 변수로 되돌릴 수 없다 — 경계 목록은 파일로 넘긴다.
BNDF=$(mktemp); BND_D=""; BND_P=""
intro_set() { local path="$1" out="" x p intro; : > "$BNDF"; for x in $(git rev-list --full-history HEAD -- "$path"); do git cat-file -e "$x:$path" 2>/dev/null || continue
    check_parents "$x" || true
    if is_boundary "$x"; then printf '%s\n' "$x" >> "$BNDF"; continue; fi
    intro=1; for p in $(parents_true "$x"); do git cat-file -e "$p:$path" 2>/dev/null && { intro=0; break; }; done; [ "$intro" = 1 ] && out="$out $x"; done; printf '%s' "$out"; }
# [E9] P_last = «현행 blob 의 도입 지점 집합»(C_R 동형 · ∀-부모).  ∨(«어느 한 부모와라도 다름») 폐기.
blob_intro_set() { local path="$1" b="$2" out="" x p same; : > "$BNDF"
  for x in $(git rev-list --full-history HEAD -- "$path"); do
    [ "$(git rev-parse -q --verify "$x:$path" 2>/dev/null || echo ABSENT)" = "$b" ] || continue
    check_parents "$x" || true
    if is_boundary "$x"; then printf '%s\n' "$x" >> "$BNDF"; continue; fi
    same=0; for p in $(parents_true "$x"); do
      [ "$(git rev-parse -q --verify "$p:$path" 2>/dev/null || echo ABSENT)" = "$b" ] && { same=1; break; }; done
    [ "$same" = 0 ] && out="$out $x"; done; printf '%s' "$out"; }
if [ -n "$BODY" ]; then
  P_FIRST_SET=$(intro_set "$PC"); BND_P="$BND_P $(tr '\n' ' ' < "$BNDF")"
  HEAD_BLOB=$(git rev-parse "HEAD:$PC")
  P_LAST_SET=$(blob_intro_set "$PC" "$HEAD_BLOB"); BND_P="$BND_P $(tr '\n' ' ' < "$BNDF")"
else P_FIRST_SET=""; P_LAST_SET=""; HEAD_BLOB=""; fi
NPF=$(printf '%s\n' $P_FIRST_SET | grep -c .); NPL=$(printf '%s\n' $P_LAST_SET | grep -c .)
D=$(intro_set "$CFG"); BND_D=$(tr '\n' ' ' < "$BNDF"); ND=$(printf '%s\n' $D | grep -c .)
printf 'P_first(집합·|%s|)=[%s] P_last(집합·|%s|·blob=%s)=[%s] |D|=%s D=[%s]  [E9 ∀-부모]\n' \
  "$NPF" "$(printf '%s ' $P_FIRST_SET)" "$NPL" "${HEAD_BLOB:-∅}" "$(printf '%s ' $P_LAST_SET)" "$ND" "$(printf '%s ' $D)"
BND_D=$(printf '%s\n' $BND_D | sort -u | tr '\n' ' '); BND_P=$(printf '%s\n' $BND_P | sort -u | tr '\n' ' ')
# [E10 ㉠] 후보 전수에 대해 «재파생 vs 이력 뷰» 대조 결과를 방출하고 불일치는 전역 차단
PU_CHECKED=$(sort -u "$PUC" | grep -c .); PU_N=$(grep -c . "$PUF"); PU_MISMATCH=$(tr '\n' ' ' < "$PUF")
PU_L=$(grep -c . "$PUL")
printf 'U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 %s건=[%s]\n' "$PU_L" "$(tr '\n' ' ' < "$PUL")"
printf 'U17-PU㉠ 재파생 대조: 검사 후보 %s건 · «남는» 전역 불일치 %s건=[%s]\n' "$PU_CHECKED" "$PU_N" "$PU_MISMATCH"
[ "$PU_N" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: $PU_MISMATCH"
NBD=$(printf '%s\n' $BND_D | grep -c .); NBP=$(printf '%s\n' $BND_P | grep -c .)
printf 'U17-SHALLOW is_shallow=%s shallow 목록(%s)=[%s] · 후보 우주 내 경계 커밋: D=[%s](%s건) P=[%s](%s건)  (E6: 전역 단축 아님 — 경로별 국소 판정)\n' "$IS_SHALLOW" "$SHALLOW_PATH" "$(printf '%s ' $SHALLOW_LIST)" "$(printf '%s ' $BND_D)" "$NBD" "$(printf '%s ' $BND_P)" "$NBP"
[ "$NBD" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[SHALLOW] D 후보 우주에 얕은 클론 경계 커밋($(printf '%s ' $BND_D)) — 부모 미상이라 도입 지점 확정 불가 (부재를 «참»으로 접지 않는다)"
[ "$NBP" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[SHALLOW] P_first/P_last 후보 우주에 얕은 클론 경계 커밋($(printf '%s ' $BND_P)) — 확정 불가"
sanc() { git merge-base --is-ancestor "$1" "$2" 2>/dev/null && [ "$1" != "$2" ]; }   # 진(strict) 조상
if [ -n "$BODY" ]; then
  # [E9] 카디널리티 처분은 «무조건 항»(c_APP 동형) — |P_last|=0 은 이력 파생 실패다
  [ "$NPL" -ne 0 ] || fire PREVENTION_UNVERIFIABLE "[E9] |P_last|=0 — 현행 blob($HEAD_BLOB)의 도입 지점 없음 = 이력 파생 실패/[PARENTS-UNTRUSTED]"
  # [E11] P_first 카디널리티 — 아티팩트가 «존재»하는데 도입 지점이 ∅ 이면 [PARENTS-UNTRUSTED] 로 확정 불가
  [ "$NPF" -ne 0 ] || fire PREVENTION_UNVERIFIABLE "[E11] 아티팩트는 HEAD 에 «존재»하나 |P_first|=0 — [PARENTS-UNTRUSTED](㉢ 경계/㉠ 재작성)로 경로 도입 지점 확정 불가"
fi
# [E11] 아티팩트 «부재» 이면 |P_first|=0 이 정상이며 전순서 2 ABSENT 가 이미 발화했다(위 아티팩트 절) — 여기서 재발화하지 않는다
if [ -n "$BODY" ] && [ "$ND" -gt 0 ]; then
  LATE=0
  for d in $D; do hit=0; for x in $P_FIRST_SET; do sanc "$x" "$d" && { hit=1; break; }; done; [ "$hit" = 1 ] || LATE=1; done
  if [ "$LATE" = 1 ]; then fire PREVENTION_LATE "[E9] ∃d∈D: ∀x∈P_first(|$NPF|) x ⋠ d — 그 착지 시점에 경로가 없었다"
  else
    if [ "$NPL" -gt 1 ]; then fire PREVENTION_ARTIFACT_MUTATED "[E9] ¬LATE ∧ |P_last|=$NPL>1 ($(printf '%s ' $P_LAST_SET)) — 현행 내용의 도입 지점이 유일하지 않다"
    elif [ "$NPL" -eq 1 ]; then X_LAST=$(printf '%s' $P_LAST_SET); MUT=0
      for d in $D; do sanc "$X_LAST" "$d" || MUT=1; done
      [ "$MUT" = 0 ] || fire PREVENTION_ARTIFACT_MUTATED "[E9] ¬LATE ∧ ∃d∈D: x_last=$X_LAST ⋠ d — 착수 «후» 아티팩트 변경"
      [ "$(git rev-parse "HEAD:$PC")" = "$(git rev-parse "$X_LAST:$PC")" ] || fire PREVENTION_ARTIFACT_MUTATED "[E9] 소비 blob(HEAD) ≠ blob(x_last)"
    fi
  fi
fi

# ── (b) 리비전 특정 ∀d∈D (전순서 8) — D=∅ 는 «검증 대상 없음»(명시)
MINMERGED=""
if [ "$ND" -eq 0 ]; then
  printf 'U17-B D=∅ — (b-blob)@d·(b-server)·(c) 는 «D-지표 항»이라 평가 대상 없음.  **(b-blob)@target 은 위에서 «무조건 항»으로 이미 평가됐다**(v2.22·M-7 — v2.21 은 (b)(c) 를 통째로 접었다·심판 #3 vacuity)\n'
elif [ -n "$TARGET" ]; then
  for d in $D; do
    respond "repos/$PIN_OR/commits/$d/pulls"; show_capture B1 "repos/$PIN_OR/commits/$d/pulls"
    HS=$(python3 - "$CAP" "$PIN_OR" "$d" "$TARGET" <<'PY'
import json,sys,os
cap,orepo,d,target=sys.argv[1:5]; k=f"repos/{orepo}/commits/{d}/pulls".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: prs=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|pulls 본문 파싱 실패"); sys.exit(0)
ok=[p for p in prs if isinstance(p,dict) and p.get("merged_at") and (p.get("base") or {}).get("ref")==target]
if not ok: print("UNVERIFIED_REVISION|착지 PR 부재·merged 아님·base≠target (pulls=%d)"%len(prs)); sys.exit(0)
print("HEAD|%s|%s"%(ok[0]["head"]["sha"],ok[0]["merged_at"]))
PY
)
    case "$HS" in UNVERIFIABLE\|*) fire PREVENTION_UNVERIFIABLE "(b) d=$d ${HS#*|}"; continue ;; UNVERIFIED_REVISION\|*) fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d ${HS#*|}"; continue ;; esac
    HSHA=$(printf '%s' "$HS" | cut -d'|' -f2); MERGED=$(printf '%s' "$HS" | cut -d'|' -f3); { [ -z "$MINMERGED" ] || [[ "$MERGED" < "$MINMERGED" ]]; } && MINMERGED="$MERGED"
    respond "repos/$PIN_OR/commits/$HSHA/check-runs"; show_capture B2 "repos/$PIN_OR/commits/$HSHA/check-runs"
    # ── [v2.22·M-3] path-aware check-run «전수 열거» (계약 :5557-5565)
    #    v2.21 은 `conclusion=="success"` 로 «먼저 거른 뒤» 첫 후보에서 break 했다 — 정본 run 이
    #    같은 suite 안에 있으면 decoy 의 suite 질의가 정본 path 를 집어 통과했다(«정본 fail + decoy
    #    success» 가 red 가 아니었던 자리).  v2.22 는 «동명 전부»를 열거하고 **각 check-run 을 그
    #    자신의 워크플로 run 으로** 해석해 정본 path 인 것이 «정확히 1개 ∧ success» 임을 요구한다.
    CRENUM=$(python3 - "$CAP" "$PIN_OR" "$HSHA" "$CHECK" "$APPID" <<'PY'
import json,sys,os,re
cap,orepo,sha,check,appid=sys.argv[1:6]; k=f"repos/{orepo}/commits/{sha}/check-runs".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: js=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|check-runs 본문 파싱 실패"); sys.exit(0)
runs=js.get("check_runs") or []
named=[r for r in runs if r.get("name")==check]     # ← conclusion 으로 «먼저 거르지 않는다»
if not named: print("UNVERIFIED_REVISION|name==%s 인 check-run 부재 (check_runs=%d)"%(check,len(runs))); sys.exit(0)
for i,r in enumerate(named):
    sid=(r.get("check_suite") or {}).get("id")
    rid=""
    for u in (r.get("details_url") or "", r.get("html_url") or ""):
        m=re.search(r"/actions/runs/(\d+)", u)
        if m: rid=m.group(1); break
    print("CR|%d|%s|%d|%d|%s|%s"%(i, r.get("conclusion"),
          1 if str((r.get("app") or {}).get("id"))==str(appid) else 0,
          1 if r.get("head_sha")==sha else 0, sid, rid))
PY
)
    case "$CRENUM" in UNVERIFIABLE\|*) fire PREVENTION_UNVERIFIABLE "(b)② head=$HSHA ${CRENUM#*|}"; continue ;;
                      UNVERIFIED_REVISION\|*) fire PREVENTION_UNVERIFIED_REVISION "(b)② d=$d head=$HSHA ${CRENUM#*|}"; continue ;; esac
    CANON_N=0; CANON_CONC=""; RUN_ID=""; ENUM_WHY=""; ENUM_LOG=""; ENUM_BAD=0
    NCR=$(printf '%s\n' "$CRENUM" | grep -c '^CR|')
    while IFS='|' read -r tag idx conc aidok headok sid rid; do
      [ "$tag" = CR ] || continue
      RPATH="?"; RHEAD=""
      if [ -n "$rid" ]; then
        RQ="repos/$PIN_OR/actions/runs/$rid"; respond "$RQ"; show_capture B4 "$RQ"; RST=$(http_of "$RQ")
        if [ "$RST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)② $RQ 네트워크/인증 오류"; ENUM_BAD=1
        elif ! ok2xx "$RST"; then ENUM_WHY="$ENUM_WHY [check-run #$idx → runs/$rid http=$RST];"; ENUM_BAD=1
        else RPATH=$(jget "$RQ" path); RHEAD=$(jget "$RQ" head_sha); fi
      else
        Q="repos/$PIN_OR/actions/runs?check_suite_id=$sid"; respond "$Q"; show_capture B4 "$Q"; QST=$(http_of "$Q")
        if [ "$QST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)② $Q 네트워크/인증 오류"; ENUM_BAD=1
        elif ! ok2xx "$QST"; then ENUM_WHY="$ENUM_WHY [check-run #$idx → suite $sid http=$QST];"; ENUM_BAD=1
        else
          SR=$(python3 - "$CAP/$(key "$Q").body" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); r=j.get("workflow_runs") or []
print("ONE|%s|%s|%s"%(r[0].get("id"),r[0].get("path"),r[0].get("head_sha")) if len(r)==1 else "AMBIG|%d"%len(r))
PY
)
          case "$SR" in
            ONE\|*) rid=$(printf '%s' "$SR" | cut -d'|' -f2); RPATH=$(printf '%s' "$SR" | cut -d'|' -f3); RHEAD=$(printf '%s' "$SR" | cut -d'|' -f4) ;;
            *) ENUM_WHY="$ENUM_WHY [check-run #$idx: details_url 에 run id 부재 ∧ suite $sid 안 run ${SR#AMBIG|}개 = 모호 → 결속 불가(fail-closed)];"; ENUM_BAD=1 ;;
          esac
        fi
      fi
      ENUM_LOG="$ENUM_LOG
  | check-run #$idx  conclusion=$conc  app_id==Actions=$aidok  head_sha==PR head=$headok  suite=$sid  run=${rid:-∅}  path=$RPATH"
      [ "$RPATH" = "$WF_PATH" ] || continue
      CANON_N=$((CANON_N+1)); CANON_CONC="$conc"; RUN_ID="$rid"
      [ "$aidok" = 1 ] || { ENUM_WHY="$ENUM_WHY [정본 path check-run #$idx app.id≠Actions $APPID(위조 표면)];"; ENUM_BAD=1; }
      [ "$headok" = 1 ] || { ENUM_WHY="$ENUM_WHY [정본 path check-run #$idx head_sha≠PR head];"; ENUM_BAD=1; }
      [ "$RHEAD" = "$HSHA" ] || { ENUM_WHY="$ENUM_WHY [정본 path run $rid head_sha=$RHEAD≠PR head];"; ENUM_BAD=1; }
      # [E2] check_suite 귀속 일치 — 그 check-run 의 suite head_sha == PR head.sha
      respond "repos/$PIN_OR/check-suites/$sid"; show_capture B3 "repos/$PIN_OR/check-suites/$sid"
      SST=$(http_of "repos/$PIN_OR/check-suites/$sid")
      if ! ok2xx "$SST"; then fire PREVENTION_UNVERIFIABLE "(b)② check-suites/$sid http=$SST"; ENUM_BAD=1
      elif [ "$(jget "repos/$PIN_OR/check-suites/$sid" head_sha)" != "$HSHA" ]; then
        ENUM_WHY="$ENUM_WHY [suite $sid head_sha≠PR head];"; ENUM_BAD=1; fi
    done <<< "$CRENUM"
    printf 'U17-B2e [M-3] 동명(%s) check-run 전수 열거 — %s건 (conclusion 으로 «먼저 거르지 않는다»):%s\n' "$CHECK" "$NCR" "$ENUM_LOG"
    printf 'U17-B2e 정본 path(%s) check-run = %s건 (요구 «정확히 1») · 그 conclusion = %s · 동명·타 path 공존은 red 가 «아니다»((a) decoy 잔여·열거 기록만)\n' "$WF_PATH" "$CANON_N" "${CANON_CONC:-∅}"
    if [ "$ENUM_BAD" = 1 ] || [ "$CANON_N" -ne 1 ] || [ "$CANON_CONC" != success ]; then
      fire PREVENTION_UNVERIFIED_REVISION "(b)② d=$d head=$HSHA path-aware 열거 불충족 — 정본 path check-run ${CANON_N}건(요구 1) · conclusion=${CANON_CONC:-∅}${ENUM_WHY:+ · $ENUM_WHY}"
      continue
    fi
    # [R2-③·E1] 그 head_sha 시점의 워크플로 blob — «서버»에서 읽는다: contents/<path>?ref=<head> → base64 decode → 두 리터럴 grep
    CQ="repos/$PIN_OR/contents/$WF_PATH?ref=$HSHA"; respond "$CQ"; show_capture B5 "$CQ"; CST=$(http_of "$CQ")
    if [ "$CST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b) d=$d head=$HSHA contents 조회 네트워크/인증 오류 — $CQ"; continue
    elif ! ok2xx "$CST"; then fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA contents http=$CST ($WF_PATH 부재·조회 실패) — 검사 생략 금지"; continue; fi
    WF=$(python3 -c 'import json,sys,base64
try:
    j=json.load(open(sys.argv[1])); enc=j.get("encoding"); c=j.get("content","")
    sys.stdout.write(base64.b64decode(c).decode("utf-8","replace") if enc=="base64" else str(c))
except Exception as e: sys.stdout.write("")' "$CAP/$(key "$CQ").body")
    printf 'U17-B5 decoded %s@%s (encoding=%s size=%s):\n' "$WF_PATH" "$HSHA" "$(jget "$CQ" encoding)" "$(jget "$CQ" size)"; printf '%s\n' "$WF" | sed 's/^/  | /'
    # ── [v2.21 #1 (1)] 정본 대조 — «토큰 존재»가 아니라 «정본 byte 일치» (열린-세계 → 닫힌-세계)
    WFF="$CAP/$(key "$CQ").wf.yml"; printf '%s\n' "$WF" > "$WFF"
    WFOUT=$("$PYBIN" "$WFCANON" blob "$WFF" 2>&1); WFRC=$?   # [v2.22·F#2] 계약 리터럴은 술어 «안»에 있다 — env 로 선언하지 않는다(자기선택 표면 제거)
    printf '%s\n' "$WFOUT" | sed 's/^/  | /'
    WFRES=$(printf '%s\n' "$WFOUT" | sed -n 's/^RESULT=//p' | tail -1)
    case "$WFRES" in
      UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b-blob)@d d=$d head=$HSHA 정본 잡 대조 불가(파서 핀 `yq (mikefarah) v4.48.x` 불일치 또는 YAML 파서 실패 — M-4)"; continue ;;
      BLOB_OK) : ;;
      *) fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@d d=$d head=$HSHA 정본 «잡 템플릿» 불일치 — 최상위 allowlist·jobs 개수·잡 키/name/runs-on·steps 순서·체크아웃 with·스텝 메타·중복 키 중 하나 이상 (T-84 ⑬)"; continue ;;
    esac
    # ── [v2.20 #1 (2)] 서버 잡 스텝 대조 — actions/runs/{run_id}/jobs (계약 리터럴 스텝 이름 × conclusion)
    [ -n "${RUN_ID:-}" ] || { fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA run_id 미회수 — 서버 스텝 대조 불가"; continue; }
    JQ="repos/$PIN_OR/actions/runs/$RUN_ID/jobs"; respond "$JQ"; show_capture B6 "$JQ"; JST=$(http_of "$JQ")
    if [ "$JST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)③ d=$d jobs 조회 네트워크/인증 오류 — $JQ"; continue
    elif ! ok2xx "$JST"; then fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d jobs http=$JST — 서버 스텝 기록 조회 실패(검사 생략 금지)"; continue; fi
    SVOUT=$("$PYBIN" "$WFCANON" server "$CAP/$(key "$JQ").body" 2>&1); SVRC=$?   # [v2.22·F#2ii] 이름 필터 hit 유일성은 술어 안에서 본다
    printf '%s\n' "$SVOUT" | sed 's/^/  | /'
    SVRES=$(printf '%s\n' "$SVOUT" | sed -n 's/^RESULT=//p' | tail -1)
    case "$SVRES" in
      UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b)③ d=$d jobs 본문 파싱 실패"; continue ;;
      SERVER_OK) : ;;
      *) fire PREVENTION_UNVERIFIED_REVISION "(b-server) d=$d head=$HSHA 서버 대조 실패 — 이름 필터 hit 비-유일(len≠1) · 잡 conclusion≠\"success\" · 계약 리터럴 스텝 이름 부재/비-success (T-84 ⑭)"; continue ;;
    esac
    if git cat-file -e "$HSHA^{commit}" 2>/dev/null; then LB=$(git rev-parse -q --verify "$HSHA:$WF_PATH" 2>/dev/null || echo ABSENT); printf 'U17-B5x 보조(선택·판정 미소비): 로컬 git show %s:%s → %s\n' "$HSHA" "$WF_PATH" "$LB"; else printf 'U17-B5x 보조(선택·판정 미소비): 로컬에 %s 커밋 없음 — 서버 조회만으로 판정\n' "$HSHA"; fi
    printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
  done
fi

# ── (α) [v2.19 — 심판 F1] 연속성 소비자 (전순서 9) — «서버 시간»만 소비한다
if [ "$ND" -eq 0 ]; then
  printf 'U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)\n'
elif [ -z "$TARGET" ]; then
  printf 'U17-α target 미파생 — 연속성 평가 불가 (전순서 1 이 이미 발화)\n'
elif [ -z "$MINMERGED" ]; then
  fire PREVENTION_CONTINUITY_UNVERIFIABLE "t_land 파생 불가(D≠∅ 이나 착지 PR 의 서버 merged_at 미해석) — 연속성 판정 불가"
else
  printf 'U17-α t_land = min{merged_at(착지 PR) : d∈D} = %s  (서버 부여 값만 · 커밋 author/committer date 불신)\n' "$MINMERGED"
  if [ -z "$APPLIED_IDS" ]; then
    fire PREVENTION_CONTINUITY_UNVERIFIABLE "적용 룰셋 0 = classic branch protection 만 → protection 응답에 created_at·updated_at 부재 → 연속성 판정 불가"
  else
    for id in $APPLIED_IDS; do
      CA=$(jget "repos/$PIN_OR/rulesets/$id" created_at); UA=$(jget "repos/$PIN_OR/rulesets/$id" updated_at)
      CONT=$(python3 - "$id" "$CA" "$UA" "$MINMERGED" <<'PY'
import sys,datetime
i,ca,ua,mm=sys.argv[1:5]
def p(s):
    try: return datetime.datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(datetime.timezone.utc)
    except Exception: return None
c,u,m=p(ca),p(ua),p(mm)
if m is None: print("BLOCK|t_land 파싱 불가(merged_at=%s)"%mm); sys.exit(0)
if c is None or u is None: print("BLOCK|ruleset %s 서버 타임스탬프 부재·파싱 불가(created_at=%s updated_at=%s) — 연속성 판정 불가"%(i,ca,ua)); sys.exit(0)
if c>m: print("BLOCK|ruleset %s created_at=%s > t_land=%s — 룰셋이 «착지 후»에 생김(삭제-재생성 포함) = 그 착지는 비보호"%(i,c.isoformat(),m.isoformat())); sys.exit(0)
if u>m: print("BLOCK|ruleset %s updated_at=%s > t_land=%s — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가"%(i,u.isoformat(),m.isoformat())); sys.exit(0)
print("PASS|ruleset %s created_at=%s ≤ t_land ∧ updated_at=%s ≤ t_land"%(i,c.isoformat(),u.isoformat()))
PY
)
      printf 'U17-α ruleset %s: %s\n' "$id" "${CONT#*|}"
      case "$CONT" in BLOCK\|*) fire PREVENTION_CONTINUITY_UNVERIFIABLE "(α) ${CONT#*|} — 운영자 재심사 경로(영구 차단 아님)";; esac
    done
  fi
fi

finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ **(b-blob)@target=$BT_STATE(무조건 항·target HEAD=${THSHA:-∅})** ∧ (b-blob)@d·(b-server) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"
```
### wfcanon-v222.py  (sha256 `d5e11bf0fef7f5bb9896caba8bebf93bebe5a4e640543cd963716f9235c95cd0` · 542행)

```python
#!/usr/bin/env python3
"""U-17 (b)③ «정본 잡 대조» 술어 — v2.22 계약 8ec22754 §12.3.4 U-17 의 문자 구현.

v2.21 술어 `wfcanon-v221.py`(sha256 a5430e1a593d890f19a36713b9577c15c807a12c4131d45bd2937744255b811d)
에서 파생.  **델타는 v2.22 재심 처분 4건(#1/F#1 · #2/M-7 · F#2 · F#4) + C-1 + M-4 + M-1/M-3 뿐이다.**

── 델타 (v2.21 → v2.22) ─────────────────────────────────────────────────────────
[C-1  :5618-5635]  **신규**  PyYAML `yaml.compose()` 노드 순회로 문서 «전 매핑 노드»(최상위·중첩·
                   **시퀀스 원소 `steps[i]`**) 중복 키 검출.  키 대조는 **compose 키 노드의 `.value`
                   (원시 스칼라)** 위에서만 — `construct`/`safe_load` 금지.  **중복 검출 통과 «후에만»**
                   정본 잡 대조로 진행한다(그 순서 덕분에 `yq -o=json` 의 last-wins 붕괴가 무해).
                   두 파서 `.value` 키 트리 불일치도 `UNVERIFIED_REVISION`(벨트).
[M-4  :5606-5617]  **신규**  판정 파서 = `yq (mikefarah) v4.48.x` — `yq --version` 파싱 대조,
                   불일치 = `PREVENTION_UNVERIFIABLE`.  `<<` merge key 존재 자체 = `UNVERIFIED_REVISION`.
[M-2  :5644-5650]  **신규**  워크플로 최상위 allowlist(닫힌 집합) `{name, run-name, on, permissions, jobs}`.
[F#4  :5651-5688]  **신규**  값 전수 핀 — ① `permissions` 존재 + 정확히 `{contents: read}`
                   ② `runs-on` 허용 리터럴 «정확히 2개» ③ 체크아웃 `with` 존재 + 정확히
                   `{fetch-depth: 0, persist-credentials: false}` ④ 파서 핀(M-4) ⑤ `SHELL_OK` 3값.
[F#2  :5659-5671]  **신규**  `jobs` 정확히 1개 ∧ 잡 id == 계약 리터럴 `tos-gate` ∧ 잡 `name` 존재 +
                   값 == `tos-gate`.  서버 층은 이름 필터 `hit` 의 `len(hit) != 1` → `UNVERIFIED_REVISION`
                   (v2.21 은 `hit[0]` 을 말없이 집었다 — 두 층 객체 분열의 서버 쪽 절반).
                   **게이트 잡/체크 이름은 «계약 리터럴»이므로 env 로 «선언»하지 않는다**(v2.21 은
                   `WF_GATE_JOB`/`WF_STEP_*`/`WF_HARNESS`/`WF_SHA` 를 env 로 받았다 — 자기선택 표면 제거).
[F#1  :5689-5747]  **신규**  `steps` = 정확히 3개·**순서 고정** [① 체크아웃 · ② 정본 B(sha256 «검증»)
                   · ③ 정본 A(하니스 «실행»)].  v2.21 순서(실행→검증) blob 은 그 자체로 정본 불일치.
                   3축: (1) `if:` (2) `continue-on-error` **키 자체 부재**(`false` 명시도 불허 — v2.21 은
                   `true` 만 거부했다) (3) 셸 `SHELL_OK`.
[M-1  :5655-5658]  **신규**  `on` ⊆ `{pull_request, push}`(list·map 양형).  «bare-only» 핀은 두지 않는다.
[M-3  ]            (b)② path-aware check-run 전수 열거는 **실행기 소관**(이 파일 밖).

── 코드 델타 «0» 인 축 (v2.21 거동 그대로) ────────────────────────────────────────
· `CANON_A`/`CANON_B` 의 **내용**            — byte 불변(v2.22 가 바꾼 것은 «순서»뿐).
· 두 스텝 `name:` 리터럴                     — byte 불변.
· `normalize()` 정규화 규칙                  — CRLF→LF · trailing ASCII `[ \\t]` · 빈 줄·full-line 주석 제거.
· `SHELL_OK` 3값 집합                        — v2.21 이 이미 정확히 이 3값이었다(계약이 «생략부호»였을 뿐).
· `if:` 허용 집합 `{success(), ${{ success() }}}` — v2.21 과 동일 리터럴.
· `timeout-minutes != 0`                     — v2.21 과 동일.
· 서버 층 잡 `conclusion == "success"`        — v2.21 이 이미 리터럴 대조였다(skipped/neutral/cancelled/
  null 은 이미 배제).  v2.22 는 계약 문언만 명시화했고 **술어 코드는 불변**이다.
· 서버 층에 «정확히 3개» 미적용              — v2.21 도 적용하지 않았다.

── 계약 «공백» 에 대한 방어적 처분 (전부 §14 에라타 후보로 등재 — 계약은 고치지 않았다)
[G1 정본 «잡 템플릿» 은 계약에 코드펜스가 «없다»]
  실측: 계약 7,912행에 `^[[:space:]]*jobs:` 는 **0건**(`jobs` 문자열 자체는 21행 — 부재가 아니라
  «펜스가 없다»는 뜻).  yaml 펜스는 `:3865`(무관)·`:5968`(countersign 형식) 둘뿐이고,
  «정본 잡 템플릿» 7회(`:225 :2903 :5605 :5643 :5841 :6033 :6087`)는 전부 지시적 산문이다.
  byte 로 핀된 것은 **정본 A(:5713-5716)·정본 B(:5724-5727) = 스텝 «본문» 둘뿐**이다.
  ⇒ 이 술어의 비교 피연산자는 산문 불릿(:5644-5700 · :5752-5762)에서 **재-파생(re-derivation)** 한
  검사들의 논리곱이지 **«정본 템플릿과의 byte 대조»가 아니다**.  재-파생 산물을 증거 보고서에
  독립 아티팩트(`canon-job-template.reconstructed.yml` + sha256)로 적어 둔다.
[G2 파서 핀 문자열이 도구 출력과 «불일치»]
  계약 :5607 은 `yq (mikefarah) v4.48.x` 를 핀하고 «`yq --version` 을 파싱해 이 리터럴과 대조» 하라
  적었으나 ① 실제 출력은 `yq (https://github.com/mikefarah/yq/) version v4.48.1` 이라 **핀 문자열이
  부분문자열이 아니고** ② `.x` 는 **와일드카드지 리터럴이 아니다**.  «대조» 규격이 없다.
  **이 술어가 고른 매치 규칙(명시)**: `("mikefarah" in out) and ("v4.48." in out)` — 벤더 식별자와
  major.minor 를 «둘 다» 요구하고 patch 는 열어 둔다(`.x` 를 «patch 와일드카드» 로 읽은 것).
[G3 PyYAML 이 계약 어디에도 «버전 핀» 되어 있지 않다]
  실측: PyYAML 언급 6회(`:224 :2903 :5614 :5620 :5624 :5632`) · 버전 0회.  C-1 은 동결 차단
  CRITICAL 처분인데 그 전부가 PyYAML `.value` 의미론에 얹혀 있다.  **실행 시 측정한 버전을
  `WF-D0` 라인으로 방출**해 증거에 남긴다(핀이 아니라 기록 — 핀은 계약 소관).
[G4 C-1 순회에 «방문집합»도 «종료 보장»도 없다]
  계약 :5624-5626 은 «모든 매핑 노드를 재귀 검사» 라고만 적는다.  `<<` 는 금지되나 문서 수준의
  **평범한 `&anchor`/`*alias` 는 금지돼 있지 않고**, 계약이 anchor 를 보낸 방어(:5649-5650 «yq 확장
  + jobs 개수 1»)는 **C-1 «이후»** 라 C-1 자신의 순회를 보호하지 못한다.
  **실측 3건**: ① `yaml.compose()` 는 자기참조 anchor 에서 **같은 노드 객체**를 돌려준다(순환 그래프).
  ② 분기 순환(`a: &x{b: *x, c: *x}`)에서 **깊이 상한만 있는 순진한 재귀는 2^depth 로 폭발**해
  15초 내 미종료였다(수정 전 이 술어 실측).  ③ 판정 파서 `yq` 자신도 분기 순환에서
  `fatal error: stack overflow`(rc 2)로 죽고, 단일 체인에서는 **조용히 절단된 구조**를 낸다.
  ⇒ **처분**: 노드 «객체 identity» 방문집합으로 순환을 검출해 `UNVERIFIED_REVISION`(fail-closed).
  깊이 상한은 벨트로 남긴다.  **계약은 «미종료»에 상태값을 배정하지 않았다** — 멈춘 프로세스는
  `UNVERIFIABLE` 도 아니고 fail-closed 도 아니며 **판정 자체가 없다**(실행기의 `trap EXIT` 도 못 돈다).
[G7 blob 의 «YAML 파싱 실패» 에 상태값이 배정돼 있지 않다]
  계약은 fetch 실패만 나눈다(:5587 404/HTTP → `UNVERIFIED_REVISION` · :5591 네트워크/인증 →
  `UNVERIFIABLE`).  파싱 실패는 미규정이다.  **이 술어의 처분(명시)**: compose 층 실패 →
  `UNVERIFIED_REVISION`(«그 리비전의 워크플로가 정본이 아니다») · yq 층 실패 → `UNVERIFIABLE`
  (**v2.21 거동 그대로 · 코드 델타 0**).  compose 가 «먼저» 돌므로 실무상 파싱 실패는 8 로 접힌다 —
  두 값이 전순서 1 과 8 로 갈리므로 소비자가 갈릴 수 있는 자리이며 에라타 후보다.

출력: `WF-*` 관측 라인 + 마지막 줄 `RESULT=BLOB_OK|SERVER_OK|UNVERIFIED_REVISION|UNVERIFIABLE` · rc 0/1/2.
모드: `blob <path>` · `server <path>` · `keytree <path>`(C-1 대조군 전용 관측 — 판정 미소비).
"""
import json, os, re, subprocess, sys

try:
    import yaml
except Exception as _e:                                   # pragma: no cover
    yaml = None
    _YAML_ERR = repr(_e)

# ── 계약 리터럴 (§12.3.4 U-17 · «아티팩트 파라미터가 아니다» — env 로 «선언»하지 않는다)
GATE_JOB = "tos-gate"                                     # [F#2/N-4] 잡 id == 표시 이름 == required context
HARNESS  = "tools/tos_entry_harness.sh"
SHA      = "957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d"
STEP_RUN = "tos-gate: run harness"                        # 정본 A 스텝 이름 (byte 불변)
STEP_VER = "tos-gate: verify harness sha256"              # 정본 B 스텝 이름 (byte 불변)
CHECKOUT_USES = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"

# ── 계약 정본 (v2.21 과 «같은 구성식» — byte 불변을 구조로 보장한다)
CANON_A = "set -euo pipefail\nbash %s" % HARNESS
CANON_B = ("set -euo pipefail\n"
           r"printf '%s  " + HARNESS + r"\n' " + SHA + " | shasum -a 256 -c -")

# ── 닫힌 집합 (전부 계약 리터럴)
TOP_ALLOW    = {"name", "run-name", "on", "permissions", "jobs"}          # [M-2]
PERMS_EXACT  = {"contents": "read"}                                      # [F#4 ①]
ON_ALLOW     = {"pull_request", "push"}                                  # [M-1]
RUNS_ON_OK   = {"ubuntu-latest", "ubuntu-24.04"}                         # [F#4 ②]
CHECKOUT_WITH_KEYS = {"fetch-depth", "persist-credentials"}              # [F#4 ③]
JOB_ALLOW    = {"name", "runs-on", "steps"}                              # 게이트 잡 허용 키(닫힌 집합)
SHELL_OK     = {"bash", "bash -euo pipefail {0}", "bash -eo pipefail {0}"}   # [F#4 ⑤] (v2.21 과 동일)
IF_OK        = {"success()", "${{ success() }}"}                         # (v2.21 과 동일)
RUN_STEP_REQ = {"name", "run"}
RUN_STEP_OPT = {"shell", "timeout-minutes"}
YQ_FLAVOR    = "mikefarah"                                               # [M-4]
YQ_MAJMIN    = "v4.48."
YQ_BIN       = os.environ.get("WF_YQ", "yq")   # 대조군(위조 --version) 주입 seam — 판정 리터럴은 위 두 줄

MAXDEPTH = 64


def normalize(run):
    """계약 정규화 규칙 — CRLF→LF · 줄 trailing ASCII [ \\t] 제거 · 빈 줄/full-line 주석 제거 · LF 결합.

    **[코드 델타 0]** v2.21 `wfcanon-v221.normalize` 와 byte 동일하다.
    """
    s = run.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in s.split("\n"):
        line = line.rstrip(" \t")             # [ASCII 핀] NBSP 등 유니코드 공백은 «제거하지 않는다»
        if line.strip(" \t") == "":
            continue
        if line.lstrip(" \t").startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


# ────────────────────────────────────────────────────────────────────────────────
# [M-4] 파서 버전 핀 — 임의 PATH 의 다른 yq/다른 메이저를 «조용히» 쓰지 않는다
# ────────────────────────────────────────────────────────────────────────────────
def yq_version_gate():
    try:
        r = subprocess.run([YQ_BIN, "--version"], capture_output=True, text=True)
    except Exception as e:
        return False, "yq --version 실행 실패: %r" % (e,)
    txt = (r.stdout + r.stderr).strip()
    ok = (YQ_FLAVOR in txt) and (YQ_MAJMIN in txt)
    return ok, txt


# ────────────────────────────────────────────────────────────────────────────────
# [C-1] PyYAML compose 노드 순회 — «전 매핑 노드» 중복 키 · `<<` merge key · `.value` 키 트리
#   키 대조는 compose 키 노드의 `.value`(원시 스칼라) «위에서만» 한다 — 태그·construct 미참조.
# ────────────────────────────────────────────────────────────────────────────────
def compose_scan(path):
    """→ (dups, merges, keytree, err, cycles).  dups/merges/cycles 는 «경로 문자열» 리스트.

    [G4] **방문집합은 노드 «객체 identity» 로 키잉한다.**  `yaml.compose()` 는 자기참조 anchor 에서
    같은 노드 객체를 돌려주므로(실측), 방문집합 없이는 분기 순환에서 2^depth 로 폭발해 «미종료» 가
    된다 — 그리고 계약은 미종료에 상태값을 주지 않는다.  순환은 그 자체로 `UNVERIFIED_REVISION`
    이며 «중복 키» 로 오귀속하지 않는다(한 관측에 두 상태값 금지 · 극성 논증).
    """
    if yaml is None:
        return None, None, None, "PyYAML 부재: " + _YAML_ERR, None
    try:
        with open(path, "rb") as f:
            raw = f.read()
        node = yaml.compose(raw.decode("utf-8-sig"))
    except Exception as e:
        return None, None, None, "compose 실패(단일 문서 아님·구문 오류 포함): %r" % (e,), None
    if node is None:
        return None, None, None, "빈 문서", None
    dups, merges, cycles = [], [], []
    onpath = set()          # ← 현재 재귀 «경로» 위의 노드 id (순환 = 자기 조상 재방문)

    def walk(n, where, depth):
        if id(n) in onpath:
            cycles.append("%s [순환 alias — 노드가 자기 조상을 다시 가리킨다]" % where)
            return "<cycle>"
        if depth > MAXDEPTH:
            dups.append("%s [깊이 %d 초과 — 벨트]" % (where, MAXDEPTH))
            return None
        if isinstance(n, yaml.MappingNode):
            onpath.add(id(n))
            seen, tree = [], []
            for kn, vn in n.value:
                if not isinstance(kn, yaml.ScalarNode):
                    dups.append("%s [비-스칼라 키 노드 %s — 닫힌-세계 위배·fail-closed]"
                                % (where, type(kn).__name__))
                    kv = "<non-scalar>"
                else:
                    kv = kn.value                      # ← «.value» 위에서만 대조 (construct 금지)
                if kv == "<<":
                    merges.append("%s.%s" % (where, kv))
                if kv in seen:
                    dups.append("%s.%s" % (where, kv))
                seen.append(kv)
                tree.append([kv, walk(vn, "%s.%s" % (where, kv), depth + 1)])
            onpath.discard(id(n))
            return tree
        if isinstance(n, yaml.SequenceNode):
            onpath.add(id(n))
            out = [walk(v, "%s[%d]" % (where, i), depth + 1) for i, v in enumerate(n.value)]
            onpath.discard(id(n))
            return out
        return None

    tree = walk(node, "$", 0)
    return dups, merges, tree, "", cycles


def kt_json(o, depth=0):
    """yq `-o=json` 산출물에서 뽑은 «키 트리» — compose `.value` 트리와 같은 모양."""
    if depth > MAXDEPTH:
        return "<depth>"
    if isinstance(o, dict):
        return [[k, kt_json(v, depth + 1)] for k, v in o.items()]
    if isinstance(o, list):
        return [kt_json(v, depth + 1) for v in o]
    return None


def parse_yaml(path):
    """판정 파서 — mikefarah yq (YAML 1.2).  PyYAML 은 `on:`→bool 이라 «판정 파서로 쓰지 않는다»."""
    r = subprocess.run([YQ_BIN, "-o=json", ".", path], capture_output=True, text=True)
    if r.returncode != 0:
        return None, "yq 파싱 실패: " + r.stderr.strip()[:200]
    try:
        return json.loads(r.stdout), ""
    except Exception as e:
        return None, "JSON 변환 실패: %r" % (e,)


# ────────────────────────────────────────────────────────────────────────────────
# 값 술어 헬퍼 — 음극성 bool 은 `is False` «만», int 는 bool 을 배제한다
# ────────────────────────────────────────────────────────────────────────────────
def is_exact_int(v, want):
    return isinstance(v, int) and not isinstance(v, bool) and v == want


def meta_check(st, kind):
    """run 스텝 닫힌 키 집합 + 3축 (계약 :5752-5762).

    v2.21 대비 델타: `continue-on-error` 는 **키 자체 부재**(`false` 명시도 불허) ·
    허용 키를 `{name, run}` + 선택 `{shell, timeout-minutes}` 로 «닫는다»(v2.21 은
    `continue-on-error`/`if` 를 허용 키 밖 예외로 두어 «존재»를 허용했다).
    """
    why = []
    keys = set(st)
    if "continue-on-error" in st:                                   # [F#1 축 2]
        why.append("continue-on-error 키 존재(값=%r · `false` 명시도 불허)" % (st["continue-on-error"],))
    if "if" in st:                                                  # [F#1 축 1] — 닫힌 키 집합 밖
        v = str(st["if"]).strip()
        if v in IF_OK:
            # [에라타 후보 EC-1] 계약은 «`if:` 부재 또는 값 ∈ IF_OK» 를 «허용»으로 적었으나
            #   같은 절의 run 스텝 «닫힌 키 집합»(name·run·shell?·timeout-minutes?)에는 `if` 가 없다.
            #   더 좁은 쪽(닫힌 집합)을 따른다 — fail-closed 방향.  허용-값 분기는 도달 불가다.
            why.append("if 키 존재(값 %r 는 허용 집합 %s 안이나 run 스텝 닫힌 키 집합 밖)"
                       % (st["if"], sorted(IF_OK)))
        else:
            why.append("if: %r (허용 집합 %s 밖)" % (st["if"], sorted(IF_OK)))
    if "timeout-minutes" in st:
        try:
            if int(st["timeout-minutes"]) == 0:
                why.append("timeout-minutes: 0")
        except Exception:
            why.append("timeout-minutes: %r(비수치)" % (st["timeout-minutes"],))
    if "shell" in st and str(st["shell"]).strip() not in SHELL_OK:   # [F#1 축 3 · F#4 ⑤]
        why.append("shell: %r (SHELL_OK 3값 밖)" % (st["shell"],))
    extra = sorted(keys - RUN_STEP_REQ - RUN_STEP_OPT)
    if extra:
        why.append("허용 키 밖 %s (run 스텝 닫힌 집합 = %s + 선택 %s)"
                   % (extra, sorted(RUN_STEP_REQ), sorted(RUN_STEP_OPT)))
    missing = sorted(RUN_STEP_REQ - keys)
    if missing:
        why.append("필수 키 부재 %s" % missing)
    return (not why), "; ".join(why)


def canon_step(st, want_name, canon, kind, why):
    if st.get("name") != want_name:
        why.append("[%s] 스텝 이름 = %r ≠ 계약 리터럴 %r" % (kind, st.get("name"), want_name))
        return
    run = st.get("run")
    if not isinstance(run, str):
        why.append("[%s] run: 이 문자열 아님(%r)" % (kind, run))
        return
    nrm = normalize(run)
    same = (nrm == canon)
    print("WF-C3 [%s] 정규형 = %r" % (kind, nrm))
    print("WF-C3 [%s] 정본   = %r" % (kind, canon))
    off = next((i for i, (x, y) in enumerate(zip(nrm, canon)) if x != y), min(len(nrm), len(canon)))
    print("WF-C4 [%s] byte 일치 = %s%s" % (kind, same, "" if same else "  ← 첫 불일치 오프셋 %d" % off))
    if not same:
        why.append("[%s] 정규화 후 정본 byte 불일치(첫 오프셋 %d)" % (kind, off))
    mok, mwhy = meta_check(st, kind)
    print("WF-C5 [%s] 스텝 키 = %s · 닫힌 집합 = %s%s" % (kind, sorted(st), mok, "" if mok else " (%s)" % mwhy))
    if not mok:
        why.append("[%s] 스텝 메타: %s" % (kind, mwhy))


def blob_layer(path):
    # ── 0. [M-4] 파서 버전 핀 — 판정 «전»에 세운다
    vok, vtxt = yq_version_gate()
    print("WF-P0 파서 핀 = %s %s* · `%s --version` = %r → 일치 %s" % (YQ_FLAVOR, YQ_MAJMIN, YQ_BIN, vtxt, vok))
    if not vok:
        print("WF-P1 파서 버전 불일치 → PREVENTION_UNVERIFIABLE (임의 PATH 의 다른 yq 를 조용히 쓰지 않는다)")
        return "UNVERIFIABLE"

    # ── 1. [C-1] 전 노드 중복 키 검출 — «통과 후에만» 아래 비교 경로로 진행한다
    print("WF-D0 [G3] C-1 파서 = PyYAML %s (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)"
          % (getattr(yaml, "__version__", "?") if yaml else "부재"))
    dups, merges, ctree, cerr, cycles = compose_scan(path)
    if cerr:
        print("WF-D0 compose 실패 → %s  [G7 처분: UNVERIFIED_REVISION]" % cerr)
        return "UNVERIFIED_REVISION"
    print("WF-D1 [C-1] compose 전 매핑 노드 중복 키 = %d건 %s" % (len(dups), dups if dups else ""))
    print("WF-D2 [M-4] `<<` merge key = %d건 %s" % (len(merges), merges if merges else ""))
    print("WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = %d건 %s" % (len(cycles), cycles if cycles else ""))
    if cycles:
        print("WF-D2c 순환 alias 검출 → UNVERIFIED_REVISION (계약은 «미종료»에 상태값을 주지 않는다 — "
              "방문집합 없이는 판정 자체가 없다)")
        return "UNVERIFIED_REVISION"
    if merges:
        print("WF-D2 `<<` merge key 존재 자체가 금지 리터럴 → UNVERIFIED_REVISION")
        return "UNVERIFIED_REVISION"
    if dups:
        print("WF-D1 중복 키 검출 → UNVERIFIED_REVISION (정본 잡 대조·서버 대조로 진행하지 «않는다»)")
        return "UNVERIFIED_REVISION"

    # ── 2. 판정 파서(yq) 로 문서를 얻고 두 파서 `.value` 키 트리를 대조한다(벨트)
    doc, err = parse_yaml(path)
    if doc is None:
        print("WF-C1 " + err + "  [G7 처분: yq 층 실패 = UNVERIFIABLE — v2.21 거동 그대로·코드 델타 0]")
        return "UNVERIFIABLE"
    jtree = kt_json(doc)
    same_tree = (jtree == ctree)
    print("WF-D3 [C-1 벨트] 두 파서 `.value` 키 트리 일치 = %s" % same_tree)
    if not same_tree:
        print("WF-D3 compose 트리 = %s" % json.dumps(ctree, ensure_ascii=False)[:400])
        print("WF-D3 yq    트리 = %s" % json.dumps(jtree, ensure_ascii=False)[:400])
        return "UNVERIFIED_REVISION"

    print("WF-C0 판정 파서 = %s -o=json · 대조 = 정규화 후 byte 비교 · 대상 = 정본 «잡 템플릿» 전체" % YQ_BIN)
    print("WF-C0 정본 A = %r" % CANON_A)
    print("WF-C0 정본 B = %r" % CANON_B)

    why = []
    if not isinstance(doc, dict):
        print("WF-C1 최상위가 매핑 아님(%r)" % type(doc).__name__)
        return "UNVERIFIED_REVISION"

    # ── 3. [M-2] 워크플로 최상위 allowlist (닫힌 집합)
    top = set(doc)
    print("WF-T1 [M-2] 최상위 키 = %s · allowlist = %s" % (sorted(top), sorted(TOP_ALLOW)))
    outside = sorted(top - TOP_ALLOW)
    if outside:
        why.append("최상위 allowlist 밖 키 %s" % outside)

    # ── 4. [F#4 ①] permissions 존재 강제 + 정확히 {contents: read}
    if "permissions" not in doc:
        why.append("permissions 키 부재(= 리포/조직 기본값 = blob 밖·정적 결정 불가)")
    elif doc["permissions"] != PERMS_EXACT:
        why.append("permissions = %r ≠ 정확히 %r" % (doc["permissions"], PERMS_EXACT))
    print("WF-T2 [F#4①] permissions = %r" % (doc.get("permissions", "∅(부재)"),))

    # ── 5. [M-1] on ⊆ {pull_request, push} (list·map 양형)
    onv = doc.get("on", None)
    if isinstance(onv, list):
        onset = set(map(str, onv))
    elif isinstance(onv, dict):
        onset = set(map(str, onv))
    elif isinstance(onv, str):
        onset = {onv}
    else:
        onset = None
    print("WF-T3 [M-1] on = %r → 트리거 집합 %s" % (onv, sorted(onset) if onset else "∅/비해석"))
    if not onset or not (onset <= ON_ALLOW):
        why.append("on = %r 이 허용 집합 %s 안이 아님" % (onv, sorted(ON_ALLOW)))

    # ── 6. [F#2(ii)] jobs 정확히 1개 ∧ 잡 id == 계약 리터럴
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        why.append("jobs 가 매핑 아님(%r)" % (jobs,))
        jobs = {}
    print("WF-J1 [F#2ii] jobs 키 = %s (개수 %d · 요구 1) · 계약 리터럴 잡 id = %r"
          % (sorted(jobs), len(jobs), GATE_JOB))
    if len(jobs) != 1:
        why.append("jobs 개수 = %d ≠ 1 (형제 잡·anchor 복제)" % len(jobs))
    if GATE_JOB not in jobs:
        why.append("게이트 잡 id %r 부재 (jobs=%s)" % (GATE_JOB, sorted(jobs)))
        print("WF-C6 blob 층 판정 = UNVERIFIED_REVISION (%s)" % "; ".join(why))
        return "UNVERIFIED_REVISION"

    job = jobs[GATE_JOB] or {}
    if not isinstance(job, dict):
        why.append("게이트 잡이 매핑 아님")
        print("WF-C6 blob 층 판정 = UNVERIFIED_REVISION (%s)" % "; ".join(why))
        return "UNVERIFIED_REVISION"

    # ── 7. 게이트 잡 허용 키 = 닫힌 집합 {name, runs-on, steps}
    jkeys = set(job)
    print("WF-J2 게이트 잡 키 = %s · 닫힌 집합 = %s" % (sorted(jkeys), sorted(JOB_ALLOW)))
    if jkeys != JOB_ALLOW:
        why.append("게이트 잡 키 %s ≠ 닫힌 집합 %s (밖=%s · 부재=%s)"
                   % (sorted(jkeys), sorted(JOB_ALLOW),
                      sorted(jkeys - JOB_ALLOW), sorted(JOB_ALLOW - jkeys)))

    # ── 8. [F#2(i-b)] name 존재 강제 + 값 = 계약 리터럴
    print("WF-J3 [F#2i-b] 잡 name = %r · 계약 리터럴 = %r" % (job.get("name", "∅(부재)"), GATE_JOB))
    if "name" not in job:
        why.append("잡 name 키 부재 (표시 이름 fallback 은 문서 미규정 — 계약을 얹지 않는다)")
    elif job.get("name") != GATE_JOB:
        why.append("잡 name = %r ≠ 계약 리터럴 %r (blob 잡 id · 서버 표시 이름 분열)"
                   % (job.get("name"), GATE_JOB))

    # ── 9. [F#4 ②] runs-on ∈ 허용 리터럴 정확히 2개 (스칼라 문자열만)
    ro = job.get("runs-on", None)
    print("WF-J4 [F#4②] runs-on = %r · 허용 = %s" % (ro, sorted(RUNS_ON_OK)))
    if not isinstance(ro, str) or ro not in RUNS_ON_OK:
        why.append("runs-on = %r 이 스칼라 허용 리터럴 %s 밖(배열·표현식·self-hosted 금지)"
                   % (ro, sorted(RUNS_ON_OK)))

    # ── 10. [F#1] steps = 정확히 3개 · 순서 고정 [체크아웃 · 정본 B(검증) · 정본 A(실행)]
    steps = job.get("steps")
    if not isinstance(steps, list):
        why.append("steps 가 시퀀스 아님(%r)" % (steps,))
        steps = []
    print("WF-S1 [F#1] steps 개수 = %d (요구 3·순서 고정) · 이름 = %s"
          % (len(steps), [s.get("name") if isinstance(s, dict) else s for s in steps]))
    if len(steps) != 3:
        why.append("steps 개수 = %d ≠ 3 (추가/선행/누락 스텝)" % len(steps))
    else:
        # ① 체크아웃
        s0 = steps[0] if isinstance(steps[0], dict) else {}
        print("WF-S2 [①체크아웃] 키 = %s · uses = %r · with = %r"
              % (sorted(s0), s0.get("uses"), s0.get("with")))
        if set(s0) != {"uses", "with"}:
            why.append("[①체크아웃] 키 %s ≠ 닫힌 집합 ['uses', 'with']" % sorted(s0))
        if s0.get("uses") != CHECKOUT_USES:
            why.append("[①체크아웃] uses = %r ≠ 계약 리터럴 핀 %r" % (s0.get("uses"), CHECKOUT_USES))
        w = s0.get("with")
        if not isinstance(w, dict):
            why.append("[①체크아웃] with 부재·매핑 아님(%r) — 생략 = 얕은 클론 + 토큰 잔류" % (w,))
        else:
            if set(w) != CHECKOUT_WITH_KEYS:
                why.append("[①체크아웃] with 키 %s ≠ 정확히 %s" % (sorted(w), sorted(CHECKOUT_WITH_KEYS)))
            if "fetch-depth" in w and not is_exact_int(w["fetch-depth"], 0):
                why.append("[①체크아웃] fetch-depth = %r ≠ 정수 0 (bool 배제)" % (w["fetch-depth"],))
            if "persist-credentials" in w and w["persist-credentials"] is not False:
                why.append("[①체크아웃] persist-credentials = %r — 음극성 bool 은 `is False` 만"
                           % (w["persist-credentials"],))
        # ② 정본 B (검증) → ③ 정본 A (실행)   ← v2.22 순서 반전
        s1 = steps[1] if isinstance(steps[1], dict) else {}
        s2 = steps[2] if isinstance(steps[2], dict) else {}
        canon_step(s1, STEP_VER, CANON_B, "②B/verify sha256", why)
        canon_step(s2, STEP_RUN, CANON_A, "③A/run harness", why)

    verdict = "BLOB_OK" if not why else "UNVERIFIED_REVISION"
    if why:
        for w_ in why:
            print("WF-C5 위배: %s" % w_)
    print("WF-C6 blob 층 판정 = %s" % verdict)
    return verdict


def server_layer(path):
    """actions/runs/{run_id}/jobs 응답 대조.

    v2.21 대비 델타 = **[F#2(ii)] 이름 필터 `hit` 유일성**(`len(hit) != 1` → UNVERIFIED_REVISION).
    잡 `conclusion == "success"` 리터럴 대조·두 스텝 이름·«정확히 3개» 미적용은 **코드 델타 0**.
    """
    try:
        j = json.load(open(path))
    except Exception as e:
        print("WF-S0 jobs 응답 파싱 실패 %r → UNVERIFIABLE" % (e,))
        return "UNVERIFIABLE"
    jobs = j.get("jobs") or []
    hit = [x for x in jobs if x.get("name") == GATE_JOB]
    print("WF-S1 서버 jobs[] 이름 = %s" % [x.get("name") for x in jobs])
    print("WF-S1 [F#2ii] 이름 필터 hit = %d건 (요구 정확히 1)" % len(hit))
    if len(hit) != 1:
        print("WF-S2 len(hit)=%d != 1 → UNVERIFIED_REVISION (v2.21 은 hit[0] 을 말없이 집었다)" % len(hit))
        return "UNVERIFIED_REVISION"
    job = hit[0]
    print("WF-S2 게이트 잡 conclusion = %r (리터럴 \"success\" 만 통과)" % job.get("conclusion"))
    if job.get("conclusion") != "success":
        return "UNVERIFIED_REVISION"
    steps = job.get("steps") or []
    print("WF-S3 서버 steps[] = %s" % [(s.get("name"), s.get("conclusion")) for s in steps])
    for want in (STEP_VER, STEP_RUN):
        m = [s for s in steps if s.get("name") == want]
        if not m:
            print("WF-S4 스텝 이름 «%s» 서버 부재 → UNVERIFIED_REVISION (T-84 ⑭)" % want)
            return "UNVERIFIED_REVISION"
        if m[0].get("conclusion") != "success":
            print("WF-S4 스텝 «%s» conclusion=%r ≠ success → UNVERIFIED_REVISION (T-84 ⑭)"
                  % (want, m[0].get("conclusion")))
            return "UNVERIFIED_REVISION"
    print("WF-S5 서버 층 판정 = SERVER_OK")
    return "SERVER_OK"


def keytree_mode(path):
    """C-1 대조군 전용 관측(판정 미소비) — `.value` 트리 vs `construct` 트리 발산을 «둘 다» 찍는다."""
    dups, merges, ctree, cerr, cycles = compose_scan(path)
    if cerr:
        print("KT-ERR %s" % cerr)
        print("RESULT=UNVERIFIABLE")
        return "UNVERIFIABLE"
    doc, err = parse_yaml(path)
    if doc is None:
        print("KT-ERR %s" % err)
        print("RESULT=UNVERIFIABLE")
        return "UNVERIFIABLE"
    jtree = kt_json(doc)
    same_value = (jtree == ctree)
    # 대조군 — `construct`/`safe_load` 로 키를 비교하면 YAML 1.1 키-bool화로 오검출된다
    try:
        loaded = yaml.safe_load(open(path, encoding="utf-8-sig").read())
        ltree = kt_json(loaded)
        same_construct = (jtree == ltree)
        lkeys = sorted(map(repr, loaded)) if isinstance(loaded, dict) else "n/a"
    except Exception as e:
        ltree, same_construct, lkeys = None, "ERR:%r" % (e,), "ERR"
    print("KT dup=%d merge=%d cycle=%d · `.value` 트리 일치 = %s · `construct`(safe_load) 트리 일치 = %s"
          % (len(dups), len(merges), len(cycles), same_value, same_construct))
    print("KT 최상위 키 — compose `.value` = %s"
          % ([k for k, _ in ctree] if isinstance(ctree, list) else ctree))
    print("KT 최상위 키 — safe_load construct = %s" % lkeys)
    print("RESULT=%s" % ("VALUE_OK" if same_value else "VALUE_DIVERGE"))
    return "VALUE_OK" if same_value else "VALUE_DIVERGE"


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "keytree":
        res = keytree_mode(sys.argv[2])
        sys.exit(0 if res == "VALUE_OK" else 1)
    res = blob_layer(sys.argv[2]) if mode == "blob" else server_layer(sys.argv[2])
    print("RESULT=" + res)
    sys.exit(0 if res in ("BLOB_OK", "SERVER_OK") else (2 if res == "UNVERIFIABLE" else 1))
```
### derive-v222.py  (sha256 `896785583699760e326448e78a1cca918bc795138914b3bbcb95a980bec94e95` · 297행)

```python
#!/usr/bin/env python3
"""u17-verify-v221.sh → u17-verify-v222.sh «델타 전용» 파생기.

실행기를 손으로 다시 쓰지 않는다 — v2.21 원문(sha256 5410519e…)에 **명시된 훅 N개**만 적용한다.
그래야 «v2.21 거동 그대로»가 주장이 아니라 **구조**가 된다(각 훅은 원문 앵커가 유일해야 하고,
아니면 여기서 즉시 실패한다).
"""
import hashlib, sys

SRC = "u17-verify-v221.sh"
DST = "u17-verify-v222.sh"
V221_SHA = "5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727"

s = open(SRC, encoding="utf-8").read()
got = hashlib.sha256(s.encode()).hexdigest()
assert got == V221_SHA, "v2.21 원문 sha256 불일치: %s" % got

HUNKS = []


def hunk(tag, old, new):
    HUNKS.append((tag, old, new))


# ── H1  헤더 — v2.22 델타를 «맨 위»에 얹는다 (v2.21 이 v2.20/v2.19 이력을 남긴 규약 그대로)
hunk("H1-header",
     "#!/usr/bin/env bash\n"
     "# u17-verify (v2.21 동결 0528a919)",
     r"""#!/usr/bin/env bash
# u17-verify (v2.22 동결 8ec22754) — U-17 «예방 통제 활성 증거» 실행기 (계약 8ec22754 §12.3.4 U-17)
#   v2.21 동결 0528a919 실행기(sha256 5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727)
#   에서 파생 — 델타는 **v2.21 재심 처분 4건 + C-1 + M-4/M-2/M-1/M-3** 뿐이고, 그 밖의 전 축은
#   **코드 델타 0**(격리 스냅샷 · host 결속 C6 · PARENTS-UNTRUSTED ㉠㉡㉢ · SHALLOW · (a) 술어 ·
#    countersign · P_first/P_last E9/E11 · 연속성 α · 전순서 10단 · trap EXIT 폐쇄 · responder seam).
#     [F#1 — #1 «회피» 2연속 :5689-5747]  정본 `steps` 순서 반전 [① 체크아웃 · ② 정본 B(sha256 «검증»)
#           · ③ 정본 A(하니스 «실행»)] + 3축(`if:`·`continue-on-error` 키 부재·`SHELL_OK`).
#           **정본 A/B 코드펜스의 «내용»과 두 스텝 `name:` 리터럴은 byte 불변** — 바뀐 것은 순서뿐이다.
#     [M-7 — #2 부분해소 3연속 :5828-5877]  **(b)③ blob 층에 `D` 무관 «무조건 항» `(b-blob)@target` 추가.**
#           `branches/<target>` → `.commit.sha` 를 해석해 **transcript 에 verbatim 수록(필수)** 한 뒤
#           `contents/<wf>?ref=<target HEAD sha>` 를 정본 잡 템플릿과 대조한다.  **«추가»이지 «대체»가
#           아니다** — 기존 D-지표 항 `(b-blob)@d`(`?ref=<PR head.sha>`)는 그대로 유지한다(N-11).
#           404·HTTP 오류 → `PREVENTION_UNVERIFIED_REVISION`(ABSENT 로 접지 않는다) · 네트워크·인증
#           오류 → `PREVENTION_UNVERIFIABLE`.
#     [F#2 — 신규 high :5659-5671·5787-5793]  게이트 체크/잡 이름을 **아티팩트 파라미터에서 계약
#           리터럴 `tos-gate` 로 이동**(선언 3항→2항).  blob 층 `jobs`=1 ∧ 잡 id·`name` 값-핀 ·
#           서버 층 이름 필터 `hit` 의 `len(hit)!=1` → UNVERIFIED_REVISION (술어 파일 소관).
#     [M-3 :5557-5565]  (b)② **path-aware check-run 전수 열거** — 동명 check-run 을 conclusion 으로
#           «먼저 거르지 않고» 전부 열거해 각각을 워크플로 run 으로 해석하고, **정본 `path` 인 것이
#           «정확히 1개» ∧ 그것이 `success`** 여야 한다.  v2.21 은 `conclusion==success` 로 먼저 걸러
#           첫 후보만 봤다 — 그래서 «정본 fail + decoy success» 가 통과했다.
#           **동명·다른 path 의 공존 자체는 red 가 아니다** — 열거 기록만 남긴다((a) 동명 decoy 잔여).
#     [C-1 / M-4 / M-2 / F#4 / M-1]  술어 파일 교체: wfcanon-v221.py → **wfcanon-v222.py**
#           (전 노드 중복 키 검출 · `yq --version` 파서 핀 · `<<` 금지 · 최상위 allowlist ·
#            `permissions`/`runs-on`/checkout `with` 값 전수 핀 · `on` ⊆ {pull_request, push}).
#           PyYAML compose 층이 필요하므로 그 술어만 `$PYBIN`(.venv) 로 돈다 — 실행기 자신의
#           inline JSON 헬퍼는 **`python3` 그대로**(코드 델타 0).
# ── 이하 v2.21 원문 헤더 ─────────────────────────────────────────────────────────
# u17-verify (v2.21 동결 0528a919)""")

# ── H2  술어 파일·인터프리터·계약 리터럴 잡 이름
hunk("H2-predicate-vars",
     'WFSTRUCT="${U17_WFSTRUCT:-$(dirname "$0")/wfcanon-v221.py}"   '
     '# [v2.21 #1] «정본 대조» 술어 (YAML 파서 + 정규화 후 byte 비교)',
     'WFCANON="${U17_WFCANON:-$(dirname "$0")/wfcanon-v222.py}"     '
     '# [v2.22] «정본 잡 템플릿» 술어 (C-1 전 노드 중복 + 파서 핀 + 값 전수 핀)\n'
     'PYBIN="${U17_PYBIN:-/Users/harris/Development/private/kis_unified_sts/.venv/bin/python}"  '
     '# [v2.22] 술어의 PyYAML compose 층 전용 (시스템 python3 에는 PyYAML 부재)\n'
     'GATE_JOB=tos-gate                                     '
     '# [v2.22·F#2/N-4] 계약 리터럴 — 잡 id == 표시 이름 == required context (아티팩트 파라미터 아님)')

# ── H3  게이트 체크 이름을 아티팩트 선언에서 «파생하지 않는다»
hunk("H3-check-literal",
     'DECL_OR=$(yv owner_repo); DECL_TB=$(yv target_branch); CHECK=$(yv tos_gate_check); '
     '[ -n "$CHECK" ] || CHECK=tos-gate',
     'DECL_OR=$(yv owner_repo); DECL_TB=$(yv target_branch)\n'
     'CHECK="$GATE_JOB"   # [v2.22·F#2/N-4] 계약 리터럴 — «선언하지 않으면 고를 수 없다»(선례 gate_app_id·remote_name)\n'
     '[ -z "$(yv tos_gate_check)" ] || printf \'U17-note 아티팩트에 tos_gate_check 키가 있으나 v2.22 는 폐지(무시) — 계약 리터럴 %s 사용\\n\' "$CHECK"')

# ── H4  (b-blob)@target — D 무관 무조건 항.  (a) 블록 «뒤», (c) 블록 «앞»에 둔다.
hunk("H4-b-blob-target",
     "# ── (c) P_first / P_last · D  (구조 정의 · 후보 = --full-history)",
     r'''# ── [v2.22·M-7] (b-blob)@target — «D 무관 무조건 항» (계약 :5566-5591 · :5828-5849)
#    진입선(D=∅)에서도 «항상» 평가한다.  이것이 없으면 진입 판정이 blob 을 한 줄도 읽지 않는다(vacuity).
BT_STATE=NOT_EVALUATED
if [ -n "$TARGET" ]; then
  BQ="repos/$PIN_OR/branches/$TARGET"; respond "$BQ"; show_capture BT0 "$BQ"; BST=$(http_of "$BQ")
  if [ "$BST" = ERR ]; then BT_STATE=UNVERIFIABLE; fire PREVENTION_UNVERIFIABLE "(b-blob)@target branches/$TARGET 네트워크/인증 오류"
  elif ! ok2xx "$BST"; then BT_STATE=UNVERIFIED_REVISION; fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target branches/$TARGET http=$BST"
  else
    THSHA=$(jget "$BQ" commit.sha)
    printf 'U17-BT [M-7] target HEAD sha = %s   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)\n' "${THSHA:-∅(파생 불가)}"
    if [ -z "$THSHA" ]; then BT_STATE=UNVERIFIED_REVISION; fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target branches/$TARGET 의 .commit.sha 파생 불가"
    else
      TQ="repos/$PIN_OR/contents/$WF_PATH?ref=$THSHA"; respond "$TQ"; show_capture BT1 "$TQ"; TST=$(http_of "$TQ")
      if [ "$TST" = ERR ]; then BT_STATE=UNVERIFIABLE; fire PREVENTION_UNVERIFIABLE "(b-blob)@target contents 조회 네트워크/인증 오류 — $TQ"
      elif ! ok2xx "$TST"; then BT_STATE=UNVERIFIED_REVISION
        fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target http=$TST ($WF_PATH 가 target HEAD $THSHA 에 부재) — ABSENT 로 접지 않는다(전순서 2 vs 8)"
      else
        TWF=$(python3 -c 'import json,sys,base64
try:
    j=json.load(open(sys.argv[1])); enc=j.get("encoding"); c=j.get("content","")
    sys.stdout.write(base64.b64decode(c).decode("utf-8","replace") if enc=="base64" else str(c))
except Exception: sys.stdout.write("")' "$CAP/$(key "$TQ").body")
        printf 'U17-BT1 decoded %s@%s (target HEAD · encoding=%s size=%s):\n' "$WF_PATH" "$THSHA" "$(jget "$TQ" encoding)" "$(jget "$TQ" size)"
        printf '%s\n' "$TWF" | sed 's/^/  | /'
        TWFF="$CAP/$(key "$TQ").wf.yml"; printf '%s\n' "$TWF" > "$TWFF"
        TOUT=$("$PYBIN" "$WFCANON" blob "$TWFF" 2>&1)
        printf '%s\n' "$TOUT" | sed 's/^/  | /'
        TRES=$(printf '%s\n' "$TOUT" | sed -n 's/^RESULT=//p' | tail -1)
        case "$TRES" in
          BLOB_OK) BT_STATE=OK ;;
          UNVERIFIABLE) BT_STATE=UNVERIFIABLE; fire PREVENTION_UNVERIFIABLE "(b-blob)@target 정본 잡 대조 불가(파서 핀 불일치·YAML 파서 실패)" ;;
          *) BT_STATE=UNVERIFIED_REVISION; fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=$THSHA · T-84 ⑬)" ;;
        esac
      fi
    fi
  fi
else
  printf 'U17-BT [M-7] target 미파생 — (b-blob)@target 평가 불가 (전순서 1 이 이미 발화)\n'
fi
printf 'U17-BT (b-blob)@target 판정 = %s   [무조건 항 · D 와 무관]\n' "$BT_STATE"

# ── (c) P_first / P_last · D  (구조 정의 · 후보 = --full-history)''')

# ── H5  (b)② path-aware 전수 열거 — v2.21 의 «성공 필터 후 첫 후보» 를 대체
_OLD_B2 = '''    CANDS=$(python3 - "$CAP" "$PIN_OR" "$HSHA" "$CHECK" "$APPID" <<'PY'
import json,sys,os
cap,orepo,sha,check,appid=sys.argv[1:6]; k=f"repos/{orepo}/commits/{sha}/check-runs".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: js=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|check-runs 본문 파싱 실패"); sys.exit(0)
runs=js.get("check_runs") or []
named=[r for r in runs if r.get("name")==check and r.get("conclusion")=="success"]
good=[r for r in named if str((r.get("app") or {}).get("id"))==str(appid) and r.get("head_sha")==sha]
why=[]
if not named: why.append("name==%s ∧ conclusion==success 인 run 부재"%check)
else:
    for r in named:
        if str((r.get("app") or {}).get("id"))!=str(appid): why.append("app.id=%s≠Actions %s(위조 표면)"%((r.get("app") or {}).get("id"),appid))
        if r.get("head_sha")!=sha: why.append("head_sha=%s≠PR head"%r.get("head_sha"))
if not good: print("UNVERIFIED_REVISION|%s (check_runs=%d)"%("; ".join(why),len(runs))); sys.exit(0)
print("CAND|"+" ".join(str((r.get("check_suite") or {}).get("id")) for r in good))
PY
)
    case "$CANDS" in UNVERIFIABLE\\|*) fire PREVENTION_UNVERIFIABLE "(b) head=$HSHA ${CANDS#*|}"; continue ;; UNVERIFIED_REVISION\\|*) fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA ${CANDS#*|}"; continue ;; esac
    IDENT_OK=0; IDENT_WHY=""
    for sid in ${CANDS#CAND|}; do
      [ "$sid" != None ] || { IDENT_WHY="$IDENT_WHY check_suite.id 부재;"; continue; }
      respond "repos/$PIN_OR/check-suites/$sid"; show_capture B3 "repos/$PIN_OR/check-suites/$sid"
      SST=$(http_of "repos/$PIN_OR/check-suites/$sid"); ok2xx "$SST" || { fire PREVENTION_UNVERIFIABLE "(b) check-suites/$sid http=$SST"; continue; }
      [ "$(jget "repos/$PIN_OR/check-suites/$sid" head_sha)" = "$HSHA" ] || { IDENT_WHY="$IDENT_WHY suite $sid head_sha≠PR head;"; continue; }
      # [C2-①②] 워크플로 run: actions/runs?check_suite_id=<sid> → head_sha==PR head ∧ path==WF_PATH
      Q="repos/$PIN_OR/actions/runs?check_suite_id=$sid"; respond "$Q"; show_capture B4 "$Q"
      QST=$(http_of "$Q"); ok2xx "$QST" || { fire PREVENTION_UNVERIFIABLE "(b) $Q http=$QST"; continue; }
      WFOK=$(python3 - "$CAP/$(key "$Q").body" "$HSHA" "$WF_PATH" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); sha,wf=sys.argv[2],sys.argv[3]
runs=j.get("workflow_runs") or []
hit=[r for r in runs if r.get("head_sha")==sha and r.get("path")==wf]
# [v2.20 #1(2)] 서버 스텝 대조에 쓸 run_id 를 «같은 응답»에서 회수한다 (별도 선언 아님 — 구조 파생)
print(("OK|%s"%hit[0].get("id")) if hit else "NO|paths=%s"%[(r.get("path"),r.get("head_sha","")[:7]) for r in runs])
PY
)
      case "$WFOK" in OK\\|*) RUN_ID="${WFOK#OK|}" ;; *) IDENT_WHY="$IDENT_WHY workflow run path≠$WF_PATH ∨ head_sha≠PR head (${WFOK#NO|});"; continue ;; esac
      IDENT_OK=1; break
    done
    [ "$IDENT_OK" = 1 ] || { fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA 워크플로 정체성 불충족:${IDENT_WHY:- 후보 없음}"; continue; }
'''

_NEW_B2 = r'''    # ── [v2.22·M-3] path-aware check-run «전수 열거» (계약 :5557-5565)
    #    v2.21 은 `conclusion=="success"` 로 «먼저 거른 뒤» 첫 후보에서 break 했다 — 정본 run 이
    #    같은 suite 안에 있으면 decoy 의 suite 질의가 정본 path 를 집어 통과했다(«정본 fail + decoy
    #    success» 가 red 가 아니었던 자리).  v2.22 는 «동명 전부»를 열거하고 **각 check-run 을 그
    #    자신의 워크플로 run 으로** 해석해 정본 path 인 것이 «정확히 1개 ∧ success» 임을 요구한다.
    CRENUM=$(python3 - "$CAP" "$PIN_OR" "$HSHA" "$CHECK" "$APPID" <<'PY'
import json,sys,os,re
cap,orepo,sha,check,appid=sys.argv[1:6]; k=f"repos/{orepo}/commits/{sha}/check-runs".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: js=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|check-runs 본문 파싱 실패"); sys.exit(0)
runs=js.get("check_runs") or []
named=[r for r in runs if r.get("name")==check]     # ← conclusion 으로 «먼저 거르지 않는다»
if not named: print("UNVERIFIED_REVISION|name==%s 인 check-run 부재 (check_runs=%d)"%(check,len(runs))); sys.exit(0)
for i,r in enumerate(named):
    sid=(r.get("check_suite") or {}).get("id")
    rid=""
    for u in (r.get("details_url") or "", r.get("html_url") or ""):
        m=re.search(r"/actions/runs/(\d+)", u)
        if m: rid=m.group(1); break
    print("CR|%d|%s|%d|%d|%s|%s"%(i, r.get("conclusion"),
          1 if str((r.get("app") or {}).get("id"))==str(appid) else 0,
          1 if r.get("head_sha")==sha else 0, sid, rid))
PY
)
    case "$CRENUM" in UNVERIFIABLE\|*) fire PREVENTION_UNVERIFIABLE "(b)② head=$HSHA ${CRENUM#*|}"; continue ;;
                      UNVERIFIED_REVISION\|*) fire PREVENTION_UNVERIFIED_REVISION "(b)② d=$d head=$HSHA ${CRENUM#*|}"; continue ;; esac
    CANON_N=0; CANON_CONC=""; RUN_ID=""; ENUM_WHY=""; ENUM_LOG=""; ENUM_BAD=0
    NCR=$(printf '%s\n' "$CRENUM" | grep -c '^CR|')
    while IFS='|' read -r tag idx conc aidok headok sid rid; do
      [ "$tag" = CR ] || continue
      RPATH="?"; RHEAD=""
      if [ -n "$rid" ]; then
        RQ="repos/$PIN_OR/actions/runs/$rid"; respond "$RQ"; show_capture B4 "$RQ"; RST=$(http_of "$RQ")
        if [ "$RST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)② $RQ 네트워크/인증 오류"; ENUM_BAD=1
        elif ! ok2xx "$RST"; then ENUM_WHY="$ENUM_WHY [check-run #$idx → runs/$rid http=$RST];"; ENUM_BAD=1
        else RPATH=$(jget "$RQ" path); RHEAD=$(jget "$RQ" head_sha); fi
      else
        Q="repos/$PIN_OR/actions/runs?check_suite_id=$sid"; respond "$Q"; show_capture B4 "$Q"; QST=$(http_of "$Q")
        if [ "$QST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)② $Q 네트워크/인증 오류"; ENUM_BAD=1
        elif ! ok2xx "$QST"; then ENUM_WHY="$ENUM_WHY [check-run #$idx → suite $sid http=$QST];"; ENUM_BAD=1
        else
          SR=$(python3 - "$CAP/$(key "$Q").body" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); r=j.get("workflow_runs") or []
print("ONE|%s|%s|%s"%(r[0].get("id"),r[0].get("path"),r[0].get("head_sha")) if len(r)==1 else "AMBIG|%d"%len(r))
PY
)
          case "$SR" in
            ONE\|*) rid=$(printf '%s' "$SR" | cut -d'|' -f2); RPATH=$(printf '%s' "$SR" | cut -d'|' -f3); RHEAD=$(printf '%s' "$SR" | cut -d'|' -f4) ;;
            *) ENUM_WHY="$ENUM_WHY [check-run #$idx: details_url 에 run id 부재 ∧ suite $sid 안 run ${SR#AMBIG|}개 = 모호 → 결속 불가(fail-closed)];"; ENUM_BAD=1 ;;
          esac
        fi
      fi
      ENUM_LOG="$ENUM_LOG
  | check-run #$idx  conclusion=$conc  app_id==Actions=$aidok  head_sha==PR head=$headok  suite=$sid  run=${rid:-∅}  path=$RPATH"
      [ "$RPATH" = "$WF_PATH" ] || continue
      CANON_N=$((CANON_N+1)); CANON_CONC="$conc"; RUN_ID="$rid"
      [ "$aidok" = 1 ] || { ENUM_WHY="$ENUM_WHY [정본 path check-run #$idx app.id≠Actions $APPID(위조 표면)];"; ENUM_BAD=1; }
      [ "$headok" = 1 ] || { ENUM_WHY="$ENUM_WHY [정본 path check-run #$idx head_sha≠PR head];"; ENUM_BAD=1; }
      [ "$RHEAD" = "$HSHA" ] || { ENUM_WHY="$ENUM_WHY [정본 path run $rid head_sha=$RHEAD≠PR head];"; ENUM_BAD=1; }
      # [E2] check_suite 귀속 일치 — 그 check-run 의 suite head_sha == PR head.sha
      respond "repos/$PIN_OR/check-suites/$sid"; show_capture B3 "repos/$PIN_OR/check-suites/$sid"
      SST=$(http_of "repos/$PIN_OR/check-suites/$sid")
      if ! ok2xx "$SST"; then fire PREVENTION_UNVERIFIABLE "(b)② check-suites/$sid http=$SST"; ENUM_BAD=1
      elif [ "$(jget "repos/$PIN_OR/check-suites/$sid" head_sha)" != "$HSHA" ]; then
        ENUM_WHY="$ENUM_WHY [suite $sid head_sha≠PR head];"; ENUM_BAD=1; fi
    done <<< "$CRENUM"
    printf 'U17-B2e [M-3] 동명(%s) check-run 전수 열거 — %s건 (conclusion 으로 «먼저 거르지 않는다»):%s\n' "$CHECK" "$NCR" "$ENUM_LOG"
    printf 'U17-B2e 정본 path(%s) check-run = %s건 (요구 «정확히 1») · 그 conclusion = %s · 동명·타 path 공존은 red 가 «아니다»((a) decoy 잔여·열거 기록만)\n' "$WF_PATH" "$CANON_N" "${CANON_CONC:-∅}"
    if [ "$ENUM_BAD" = 1 ] || [ "$CANON_N" -ne 1 ] || [ "$CANON_CONC" != success ]; then
      fire PREVENTION_UNVERIFIED_REVISION "(b)② d=$d head=$HSHA path-aware 열거 불충족 — 정본 path check-run ${CANON_N}건(요구 1) · conclusion=${CANON_CONC:-∅}${ENUM_WHY:+ · $ENUM_WHY}"
      continue
    fi
'''
hunk("H5-path-aware-enum", _OLD_B2, _NEW_B2)

# ── H6  술어 호출 — env 로 계약 리터럴을 «선언»하지 않는다 + PyYAML compose 층 인터프리터
hunk("H6-blob-call",
     '    WFOUT=$(WF_GATE_JOB="$CHECK" WF_HARNESS="$LIT1" WF_SHA="$LIT2" python3 "$WFSTRUCT" blob "$WFF" 2>&1); WFRC=$?',
     '    WFOUT=$("$PYBIN" "$WFCANON" blob "$WFF" 2>&1); WFRC=$?   '
     '# [v2.22·F#2] 계약 리터럴은 술어 «안»에 있다 — env 로 선언하지 않는다(자기선택 표면 제거)')
hunk("H6-server-call",
     '    SVOUT=$(WF_GATE_JOB="$CHECK" python3 "$WFSTRUCT" server "$CAP/$(key "$JQ").body" 2>&1); SVRC=$?',
     '    SVOUT=$("$PYBIN" "$WFCANON" server "$CAP/$(key "$JQ").body" 2>&1); SVRC=$?   '
     '# [v2.22·F#2ii] 이름 필터 hit 유일성은 술어 안에서 본다')

# ── H7  판정 문구 — (b)③ 는 «정본 잡 템플릿» 이고 서버 층은 hit 유일성을 포함한다
hunk("H7-blob-verdict-text",
     '      *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬)"; continue ;;',
     '      *) fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@d d=$d head=$HSHA 정본 «잡 템플릿» 불일치 — 최상위 allowlist·jobs 개수·잡 키/name/runs-on·steps 순서·체크아웃 with·스텝 메타·중복 키 중 하나 이상 (T-84 ⑬)"; continue ;;')
hunk("H7-blob-unverifiable-text",
     '      UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b)③ d=$d head=$HSHA 워크플로 blob 정본 대조 불가(YAML 파서 실패)"; continue ;;',
     '      UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b-blob)@d d=$d head=$HSHA 정본 잡 대조 불가(파서 핀 `yq (mikefarah) v4.48.x` 불일치 또는 YAML 파서 실패 — M-4)"; continue ;;')
hunk("H7-server-verdict-text",
     '      *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭)"; continue ;;',
     '      *) fire PREVENTION_UNVERIFIED_REVISION "(b-server) d=$d head=$HSHA 서버 대조 실패 — 이름 필터 hit 비-유일(len≠1) · 잡 conclusion≠\\"success\\" · 계약 리터럴 스텝 이름 부재/비-success (T-84 ⑭)"; continue ;;')

# ── H8  D=∅ 안내 문구 — (b-blob)@target 은 «이미 평가됐다»
hunk("H8-D-empty-text",
     "  printf 'U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)\\n'",
     "  printf 'U17-B D=∅ — (b-blob)@d·(b-server)·(c) 는 «D-지표 항»이라 평가 대상 없음.  "
     "**(b-blob)@target 은 위에서 «무조건 항»으로 이미 평가됐다**(v2.22·M-7 — v2.21 은 (b)(c) 를 통째로 접었다·심판 #3 vacuity)\\n'")

# ── H9  최종 사유 문자열
hunk("H9-finish",
     'finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"',
     'finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ **(b-blob)@target=$BT_STATE(무조건 항·target HEAD=${THSHA:-∅})** ∧ (b-blob)@d·(b-server) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"')

for tag, old, new in HUNKS:
    n = s.count(old)
    if n != 1:
        sys.exit("훅 %s 앵커 출현 %d회 (요구 1) — 파생 중단" % (tag, n))
    s = s.replace(old, new)

# 잔존 참조 양방향 확인 (anti-phantom: 존재·부재 «둘 다»)
assert "WFSTRUCT" not in s, "WFSTRUCT 잔존"
_code = [l for l in s.split("\n") if not l.lstrip().startswith("#")]
assert not any("wfcanon-v221" in l for l in _code), "v2.21 술어 파일 참조가 «실행 줄»에 잔존"
assert any("wfcanon-v221" in l for l in s.split("\n")), "v2.21 이력 주석이 소실됨(파생 계보 상실)"
assert s.count("WFCANON") == 5, "WFCANON 참조 수 예상 밖: %d" % s.count("WFCANON")   # 정의 2(U17_WFCANON 포함) + 소비 3
assert "(b-blob)@target" in s and "BT_STATE" in s

open(DST, "w", encoding="utf-8").write(s)
print("훅 %d개 적용 → %s (%d행 · sha256 %s)"
      % (len(HUNKS), DST, s.count("\n"), hashlib.sha256(s.encode()).hexdigest()))
```
### mkwf-v222.py  (sha256 `2fd62120be6cf0351eb0e59ff7ca0508313e5a8ba5af1cc4319c0259606a8bba` · 315행)

```python
#!/usr/bin/env python3
"""t84v222 워크플로 픽스처 생성기 — «바이트 정확» YAML 을 파일로 쓴다.

v2.21 생성기 `mkwf-v221.py`(sha256 f0688051…) 에서 파생.  구조는 그대로다:
각 케이스는 `(id, 기대, 설명, bytes)` 이고 **기대값은 «실행 전»에 이 파일이 적는다** —
`INDEX.txt` 가 실행 «전»에 쓰이고 드라이버가 그것을 읽어 실측과 대조한다.

델타: 정본이 «두 스텝 run:» 에서 «정본 잡 템플릿 전체»로 확장됐으므로 픽스처도
워크플로 «전문»을 만든다(v2.21 의 `wf(run_a, run_b, meta_a, meta_b, scalar)` 헬퍼는
스텝 두 개만 파라미터화해 최상위·잡 층을 만들 수 없다).  정본 문자열은 **재타이핑**
한다 — 술어에서 import 하면 «같은 상수를 자기 자신과 비교»가 되어 증거가 되지 않는다.
"""
import os, sys

SHA = "957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d"
CO_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"

TOP = ("name: tos-gate\n"
       "on: [pull_request]\n"
       "permissions:\n"
       "  contents: read\n")
JOBS = "jobs:\n"
JOBHDR = ("  tos-gate:\n"
          "    name: tos-gate\n"
          "    runs-on: ubuntu-latest\n")
STEPSKW = "    steps:\n"

S_CO = ("      - uses: actions/checkout@" + CO_SHA + "\n"
        "        with:\n"
        "          fetch-depth: 0\n"
        "          persist-credentials: false\n")
# 정본 B — sha256 «검증» (v2.22 순서: 스텝 ②)
S_B = ('      - name: "tos-gate: verify harness sha256"\n'
       "        run: |\n"
       "          set -euo pipefail\n"
       "          printf '%s  tools/tos_entry_harness.sh\\n' " + SHA + " | shasum -a 256 -c -\n")
# 정본 A — 하니스 «실행» (v2.22 순서: 스텝 ③)
S_A = ('      - name: "tos-gate: run harness"\n'
       "        run: |\n"
       "          set -euo pipefail\n"
       "          bash tools/tos_entry_harness.sh\n")


def wf(top=TOP, jobs=JOBS, jobhdr=JOBHDR, stepskw=STEPSKW, steps=None, tail=""):
    if steps is None:
        steps = S_CO + S_B + S_A
    return top + jobs + jobhdr + stepskw + steps + tail


def s_b(run=None, meta="", scalar="|"):
    """정본 B 스텝을 run 본문/메타/스칼라 표기로 파라미터화."""
    if run is None:
        run = ("set -euo pipefail\n"
               "printf '%s  tools/tos_entry_harness.sh\\n' " + SHA + " | shasum -a 256 -c -")
    body = "\n".join(("          " + ln) if ln else "" for ln in run.split("\n"))
    m = ("\n" + "\n".join("        " + x for x in meta.split("\n"))) if meta else ""
    return '      - name: "tos-gate: verify harness sha256"%s\n        run: %s\n%s\n' % (m, scalar, body)


def s_a(run=None, meta="", scalar="|"):
    if run is None:
        run = "set -euo pipefail\nbash tools/tos_entry_harness.sh"
    body = "\n".join(("          " + ln) if ln else "" for ln in run.split("\n"))
    m = ("\n" + "\n".join("        " + x for x in meta.split("\n"))) if meta else ""
    return '      - name: "tos-gate: run harness"%s\n        run: %s\n%s\n' % (m, scalar, body)


def s_co(uses=None, with_block=None):
    uses = uses if uses is not None else "actions/checkout@" + CO_SHA
    if with_block is None:
        with_block = "        with:\n          fetch-depth: 0\n          persist-credentials: false\n"
    return "      - uses: %s\n%s" % (uses, with_block)


OK = "BLOB_OK"
UR = "UNVERIFIED_REVISION"

CASES = []


def add(cid, exp, desc, text):
    CASES.append((cid, exp, desc, text))


# ── 양성 · 정규화 대조군 ──────────────────────────────────────────────────────────
add("pos-canonical", OK, "양성 — 정본 잡 템플릿 정확(체크아웃 SHA 핀 + ② 정본 B → ③ 정본 A)", wf())
add("ctrl-comments", OK, "정규화 대조군 — full-line 주석 + 빈 줄",
    wf(steps=S_CO + s_b(run="# lead\nset -euo pipefail\n\nprintf '%s  tools/tos_entry_harness.sh\\n' "
                            + SHA + " | shasum -a 256 -c -\n# trail") + S_A))
add("ctrl-trailing-ws", OK, "정규화 대조군 — trailing 공백/탭",
    wf(steps=S_CO + S_B + s_a(run="set -euo pipefail   \nbash tools/tos_entry_harness.sh\t")))
add("ctrl-crlf", OK, "정규화 대조군 — CRLF 줄끝(run 본문)",
    wf(steps=S_CO + S_B + s_a(run="set -euo pipefail\r\nbash tools/tos_entry_harness.sh")))
add("ctrl-bom", OK, "정규화 대조군 — UTF-8 BOM 선두", "\ufeff" + wf())
add("ctrl-runs-on-2404", OK, "허용 리터럴 2번째 — runs-on: ubuntu-24.04",
    wf(jobhdr="  tos-gate:\n    name: tos-gate\n    runs-on: ubuntu-24.04\n"))
add("ctrl-on-map", OK, "on 의 map 양형 — on: {pull_request: {}}",
    wf(top="name: tos-gate\non:\n  pull_request:\npermissions:\n  contents: read\n"))
add("ctrl-on-push", OK, "on ⊆ {pull_request, push} — 둘 다",
    wf(top="name: tos-gate\non: [pull_request, push]\npermissions:\n  contents: read\n"))
add("ctrl-run-name", OK, "최상위 allowlist 안 — run-name 존재",
    wf(top="name: tos-gate\nrun-name: gate\non: [pull_request]\npermissions:\n  contents: read\n"))
add("ctrl-shell-euo", OK, "SHELL_OK 2번째 값 — shell: bash -euo pipefail {0}",
    wf(steps=S_CO + s_b(meta="shell: bash -euo pipefail {0}") + s_a(meta="shell: bash -euo pipefail {0}")))
add("ctrl-shell-eo", OK, "SHELL_OK 3번째 값 — shell: bash -eo pipefail {0}",
    wf(steps=S_CO + s_b(meta="shell: bash -eo pipefail {0}") + s_a(meta="shell: bash -eo pipefail {0}")))
add("ctrl-timeout-5", OK, "timeout-minutes 는 존재해도 값 ≠ 0 이면 허용",
    wf(steps=S_CO + s_b(meta="timeout-minutes: 5") + S_A))

# ── [F#1] 순서 반전 + 3축 ────────────────────────────────────────────────────────
add("f1-v221-order", UR, "[F#1] v2.21 순서(③실행 → ②검증) blob 자체가 정본 불일치",
    wf(steps=S_CO + S_A + S_B))
add("f1-if-always", UR, "[F#1 축1] 검증 스텝 if: always()", wf(steps=S_CO + s_b(meta="if: always()") + S_A))
add("f1-if-success", UR, "[F#1 축1·EC-1] 명시 if: success() — 허용 «값»이나 닫힌 키 집합 밖",
    wf(steps=S_CO + s_b(meta="if: success()") + S_A))
add("f1-coe-true", UR, "[F#1 축2] continue-on-error: true", wf(steps=S_CO + s_b(meta="continue-on-error: true") + S_A))
add("f1-coe-false", UR, "[F#1 축2] continue-on-error: false 명시도 «키 부재» 위배 (v2.21 은 통과시켰다)",
    wf(steps=S_CO + s_b(meta="continue-on-error: false") + S_A))
add("f1-shell-sh", UR, "[F#1 축3] shell: sh", wf(steps=S_CO + s_b(meta="shell: sh") + S_A))
add("f1-shell-pwsh", UR, "[F#1 축3] shell: pwsh", wf(steps=S_CO + s_b(meta="shell: pwsh") + S_A))
add("f1-timeout-zero", UR, "timeout-minutes: 0", wf(steps=S_CO + s_b(meta="timeout-minutes: 0") + S_A))
add("f1-folded", UR, "정본 B 를 folded `>` 로 표기 — 개행이 공백으로 접혀 불일치(에라타 ⓐ/E1)",
    wf(steps=S_CO + s_b(scalar=">") + S_A))

add("m1-on-schedule", UR, "[M-1] on: [schedule] — 허용 집합 {pull_request, push} 밖",
    wf(top="name: tos-gate\non: [schedule]\npermissions:\n  contents: read\n"))
add("m1-on-wd", UR, "[M-1] on: [workflow_dispatch] — 수동 트리거는 게이트가 아니다",
    wf(top="name: tos-gate\non: [workflow_dispatch]\npermissions:\n  contents: read\n"))

# ── [C-1] 전 노드 중복 키 ────────────────────────────────────────────────────────
_BENIGN = ('      - name: "tos-gate: verify harness sha256"\n        run: true\n'
           '      - name: "tos-gate: run harness"\n        run: true\n')
add("c1-dupsteps-benign-first", UR, "[C-1·⑬l] 잡 «안» steps: 두 번 — [무해 먼저, 정본 나중]",
    wf() .replace(STEPSKW + S_CO, STEPSKW + _BENIGN + STEPSKW + S_CO))
add("c1-dupsteps-canon-first", UR, "[C-1·⑬l] 잡 «안» steps: 두 번 — [정본 먼저, 무해 나중]",
    wf() + STEPSKW + _BENIGN)
add("c1-dup-in-step-run", UR, "[C-1·⑬n] 시퀀스 원소 steps[i] 안의 중복 run:",
    wf(steps=S_CO + S_B + s_a() .rstrip("\n") + "\n        run: |\n          set -euo pipefail\n          bash tools/tos_entry_harness.sh\n"))
add("c1-dup-in-step-name", UR, "[C-1·⑬n] 시퀀스 원소 steps[i] 안의 중복 name:",
    wf(steps=S_CO + S_B + '      - name: "tos-gate: run harness"\n        name: "tos-gate: run harness"\n'
                          "        run: |\n          set -euo pipefail\n          bash tools/tos_entry_harness.sh\n"))
add("c1-dup-jobs", UR, "[C-1·⑬n] 최상위 jobs: 중복", wf() + JOBS + JOBHDR + STEPSKW + _BENIGN)
add("c1-dup-permissions", UR, "[C-1·⑬n] 최상위 permissions: 중복",
    wf(top="name: tos-gate\non: [pull_request]\npermissions:\n  contents: write\npermissions:\n  contents: read\n"))
add("c1-dup-runs-on", UR, "[C-1·⑬n] 잡 runs-on: 중복",
    wf(jobhdr="  tos-gate:\n    name: tos-gate\n    runs-on: macos-latest\n    runs-on: ubuntu-latest\n"))

# ── [G4] 순환 alias — 계약이 «미종료»에 상태값을 배정하지 않은 자리 ─────────────────
add("g4-cycle-self", UR, "[G4] 자기참조 anchor — compose 가 «같은 노드 객체»를 돌려준다(순환 그래프)",
    "a: &x\n  b: *x\n")
add("g4-cycle-branch", UR, "[G4] **분기** 순환 — 방문집합 없이는 2^depth 폭발(수정 전 15초 미종료 실측) · yq 도 stack overflow",
    "a: &x\n  b: *x\n  c: *x\n")
add("g4-cycle-in-job", UR, "[G4] 게이트 잡 «안»의 순환 — jobs.tos-gate.steps 가 자기 잡을 가리킨다",
    "name: tos-gate\non: [pull_request]\npermissions:\n  contents: read\n"
    "jobs:\n  tos-gate: &x\n    name: tos-gate\n    runs-on: ubuntu-latest\n    steps: *x\n")

# ── [M-2/M-4] anchor · allowlist · merge key ─────────────────────────────────────
add("m2-anchor-dup-job", UR, "[⑬m] anchor/alias 로 게이트 잡 복제 → yq 확장 후 jobs 개수 2",
    "name: tos-gate\non: [pull_request]\npermissions:\n  contents: read\njobs:\n"
    "  tos-gate: &g\n    name: tos-gate\n    runs-on: ubuntu-latest\n" + STEPSKW + S_CO + S_B + S_A +
    "  tos-gate-2: *g\n")
add("m2-anchor-alias-only", UR, "[⑬m] anchor 로 «게이트 잡만» 정의 후 alias — jobs 1 이나 이름/키 분열 관측",
    "name: tos-gate\non: [pull_request]\npermissions:\n  contents: read\n"
    "x-base: &g\n  name: tos-gate\n  runs-on: ubuntu-latest\n" + "  steps:\n" +
    "    - uses: actions/checkout@" + CO_SHA + "\n      with:\n        fetch-depth: 0\n        persist-credentials: false\n"
    "jobs:\n  tos-gate: *g\n")
add("m2-merge-key", UR, "[M-4] `<<` merge key 존재 자체가 금지 리터럴",
    "name: tos-gate\non: [pull_request]\npermissions:\n  contents: read\n"
    "x-base: &b\n  runs-on: ubuntu-latest\njobs:\n  tos-gate:\n    <<: *b\n    name: tos-gate\n" +
    STEPSKW + S_CO + S_B + S_A)
add("m2-top-concurrency", UR, "[M-2] 최상위 allowlist 밖 — concurrency",
    wf(top=TOP + "concurrency:\n  group: g\n  cancel-in-progress: true\n"))
add("m2-top-env", UR, "[M-2] 최상위 allowlist 밖 — env (PATH 조작)",
    wf(top=TOP + "env:\n  PATH: /evil:/usr/bin\n"))
add("m2-top-defaults", UR, "[M-2·⑬h] 최상위 allowlist 밖 — defaults.run.shell: \"true {0}\"",
    wf(top=TOP + "defaults:\n  run:\n    shell: \"true {0}\"\n"))
add("m2-job-defaults", UR, "[⑬h] 잡 수준 defaults.run.shell — 게이트 잡 허용 키 밖",
    wf(jobhdr=JOBHDR + "    defaults:\n      run:\n        shell: \"true {0}\"\n"))

# ── [F#4] 값 전수 핀 ─────────────────────────────────────────────────────────────
add("f4-perms-absent", UR, "[F#4①] permissions 생략 (= 리포/조직 기본값·blob 밖)",
    wf(top="name: tos-gate\non: [pull_request]\n"))
add("f4-perms-write", UR, "[F#4①] permissions: {contents: write}",
    wf(top="name: tos-gate\non: [pull_request]\npermissions:\n  contents: write\n"))
add("f4-perms-extra", UR, "[F#4①] permissions 에 키 추가 — 정확히 {contents: read} 아님",
    wf(top="name: tos-gate\non: [pull_request]\npermissions:\n  contents: read\n  actions: read\n"))
add("f4-runson-2204", UR, "[F#4②] runs-on: ubuntu-22.04 (허용 2 밖)",
    wf(jobhdr="  tos-gate:\n    name: tos-gate\n    runs-on: ubuntu-22.04\n"))
add("f4-runson-macos", UR, "[F#4②] runs-on: macos-latest",
    wf(jobhdr="  tos-gate:\n    name: tos-gate\n    runs-on: macos-latest\n"))
add("f4-runson-selfhosted", UR, "[F#4②] runs-on: [self-hosted, linux] (배열)",
    wf(jobhdr="  tos-gate:\n    name: tos-gate\n    runs-on: [self-hosted, linux]\n"))
add("f4-runson-expr", UR, "[F#4②] runs-on: ${{ vars.RUNNER }} (표현식)",
    wf(jobhdr="  tos-gate:\n    name: tos-gate\n    runs-on: ${{ vars.RUNNER }}\n"))
add("f4-with-absent", UR, "[F#4③] 체크아웃 with 생략 (= 얕은 클론 + 토큰 잔류)",
    wf(steps=s_co(with_block="") + S_B + S_A))
add("f4-fetchdepth-absent", UR, "[F#4③] fetch-depth 생략 (기본 1 = 얕은 클론)",
    wf(steps=s_co(with_block="        with:\n          persist-credentials: false\n") + S_B + S_A))
add("f4-fetchdepth-1", UR, "[F#4③] fetch-depth: 1",
    wf(steps=s_co(with_block="        with:\n          fetch-depth: 1\n          persist-credentials: false\n") + S_B + S_A))
add("f4-fetchdepth-false", UR, "[F#4③·bool 배제] fetch-depth: false — `False == 0` 파이썬 등가를 배제한다",
    wf(steps=s_co(with_block="        with:\n          fetch-depth: false\n          persist-credentials: false\n") + S_B + S_A))
add("f4-persistcred-absent", UR, "[F#4③] persist-credentials 미지정 (기본 true = 토큰 잔류)",
    wf(steps=s_co(with_block="        with:\n          fetch-depth: 0\n") + S_B + S_A))
add("f4-persistcred-true", UR, "[F#4③] persist-credentials: true",
    wf(steps=s_co(with_block="        with:\n          fetch-depth: 0\n          persist-credentials: true\n") + S_B + S_A))
add("f4-persistcred-str", UR, "[F#4③·음극성 bool] persist-credentials: \"false\" (문자열) — `is False` 만 통과",
    wf(steps=s_co(with_block="        with:\n          fetch-depth: 0\n          persist-credentials: \"false\"\n") + S_B + S_A))
add("f4-with-extra", UR, "[F#4③] with 에 키 추가 (ref)",
    wf(steps=s_co(with_block="        with:\n          fetch-depth: 0\n          persist-credentials: false\n          ref: main\n") + S_B + S_A))
add("f4-checkout-tag", UR, "[⑬i] 체크아웃 uses 가 태그(@v4) — SHA 핀 아님",
    wf(steps=s_co(uses="actions/checkout@v4") + S_B + S_A))
add("f4-checkout-othersha", UR, "[⑬i] 체크아웃 uses 가 임의 40-hex SHA (포크 커밋)",
    wf(steps=s_co(uses="actions/checkout@" + "a" * 40) + S_B + S_A))

# ── [F#2] 두 층 객체 결속 ────────────────────────────────────────────────────────
add("f2-sibling-job", UR, "[F#2ii·item1] 형제 잡 존재 — jobs 개수 2",
    wf(jobhdr="  tos-gate:\n    name: gate (canonical)\n    runs-on: ubuntu-latest\n") +
    "  evil:\n    name: tos-gate\n    runs-on: ubuntu-latest\n" + STEPSKW + _BENIGN)
add("f2-sibling-namesok", UR, "[F#2ii 단독] 게이트 잡 name 은 정본인데 형제 잡이 있다 — jobs 개수만으로 red",
    wf() + "  other:\n    name: other\n    runs-on: ubuntu-latest\n" + STEPSKW + _BENIGN)
add("f2-jobid-mismatch", UR, "[F#2ii] 잡 id 가 gate — 계약 리터럴 tos-gate 아님",
    wf(jobhdr="  gate:\n    name: tos-gate\n    runs-on: ubuntu-latest\n"))
add("f2-name-free", UR, "[F#2i-b] 잡 name 이 자유 문자열 (v2.21 에라타 3차 R-3 가 허용하던 자리)",
    wf(jobhdr="  tos-gate:\n    name: TOS Gate\n    runs-on: ubuntu-latest\n"))
add("f2-name-absent", UR, "[F#2i-b] 잡 name 키 부재 (표시 이름 fallback 은 문서 미규정)",
    wf(jobhdr="  tos-gate:\n    runs-on: ubuntu-latest\n"))

# ── ⑬ 회귀 (v2.21 에서 이미 red — v2.22 에서도 red 여야 한다) ─────────────────────
add("13a-echo", UR, "⑬a — 하니스가 echo 인자",
    wf(steps=S_CO + S_B + s_a(run='set -euo pipefail\necho "bash tools/tos_entry_harness.sh"')))
add("13b-trailcomment", UR, "⑬b — trailing 주석(정규화가 제거하지 않는다)",
    wf(steps=S_CO + S_B + s_a(run="set -euo pipefail\nbash tools/tos_entry_harness.sh  # run it")))
add("13c-ortrue", UR, "⑬c — `|| true` 무효화",
    wf(steps=S_CO + s_b(run="set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' " + SHA +
                            " | shasum -a 256 -c - || true") + S_A))
add("13d-unreachable", UR, "⑬d — 도달 불가 호출 `false && …`",
    wf(steps=S_CO + S_B + s_a(run="set -euo pipefail\nfalse && bash tools/tos_entry_harness.sh || true")))
add("13f-set-plus-e", UR, "⑬f — set +e",
    wf(steps=S_CO + s_b(run="set -euo pipefail\nset +e\nprintf '%s  tools/tos_entry_harness.sh\\n' " + SHA +
                            " | shasum -a 256 -c -") + S_A))
add("13f-trap", UR, "⑬f — trap … ERR",
    wf(steps=S_CO + s_b(run="set -euo pipefail\ntrap 'exit 0' ERR\nprintf '%s  tools/tos_entry_harness.sh\\n' " +
                            SHA + " | shasum -a 256 -c -") + S_A))
add("13g-exit0", UR, "⑬g — 선행 종결자 `exit 0`",
    wf(steps=S_CO + S_B + s_a(run="set -euo pipefail\nexit 0\nbash tools/tos_entry_harness.sh")))
add("13g-exec-true", UR, "⑬g — 선행 종결자 `exec true`",
    wf(steps=S_CO + S_B + s_a(run="set -euo pipefail\nexec true\nbash tools/tos_entry_harness.sh")))
add("13g-guarded-exit", UR, "⑬g — 선행 종결자 `[ -n \"${SKIP:-}\" ] && exit 0`",
    wf(steps=S_CO + S_B + s_a(run='set -euo pipefail\n[ -n "${SKIP:-}" ] && exit 0\nbash tools/tos_entry_harness.sh')))
add("nbsp-trailing", UR, "NBSP trailing (ASCII 핀 — 유니코드 공백은 제거하지 않는다)",
    wf(steps=S_CO + S_B + s_a(run="set -euo pipefail\u00a0\nbash tools/tos_entry_harness.sh")))
add("inline-semicolon", UR, "inline `;` 한 줄",
    wf(steps=S_CO + S_B + s_a(run="set -euo pipefail; bash tools/tos_entry_harness.sh")))
add("env-bash", UR, "`env bash …` (정본 아님)",
    wf(steps=S_CO + S_B + s_a(run="set -euo pipefail\nenv bash tools/tos_entry_harness.sh")))
add("13i-extra-step", UR, "⑬i — 선행 run 스텝($GITHUB_PATH 조작) 추가 → steps ≠ 3",
    wf(steps=S_CO + '      - name: "prep"\n        run: |\n          echo /x >> $GITHUB_PATH\n' + S_B + S_A))
add("13i-steps-two", UR, "steps 2개 — 체크아웃 누락", wf(steps=S_B + S_A))
add("13j-job-container", UR, "⑬j — 잡 container: (가짜 bash 이미지) → 게이트 잡 허용 키 밖",
    wf(jobhdr=JOBHDR + "    container: evil/bash:latest\n"))
add("13j-job-env", UR, "⑬j — 잡 env: → 게이트 잡 허용 키 밖",
    wf(jobhdr=JOBHDR + "    env:\n      PATH: /evil\n"))
add("13j-job-if", UR, "잡 수준 if: → 게이트 잡 허용 키 밖(M-1 스킵 벡터)",
    wf(jobhdr=JOBHDR + "    if: github.event_name == 'push'\n"))
add("13j-job-needs", UR, "잡 수준 needs: → 게이트 잡 허용 키 밖(M-1 스킵 벡터)",
    wf(jobhdr=JOBHDR + "    needs: [other]\n"))
add("13e-step-env", UR, "⑬e — 스텝 env: (닫힌 메타 키 집합 위배)",
    wf(steps=S_CO + s_b(meta="env:\n  FOO: bar") + S_A))
add("13e-step-workdir", UR, "⑬e — 스텝 working-directory:",
    wf(steps=S_CO + s_b(meta="working-directory: /tmp") + S_A))
add("13e-step-id", UR, "⑬e — 스텝 id:", wf(steps=S_CO + s_b(meta="id: verify") + S_A))

# ── 정직 워크플로(C-1 대조군 · item 5) — 판정 대상이 아니라 «키 트리 발산 0» 관측용 ──
HONEST = [
    ("honest-on-list", "on: 을 리스트로 쓰는 정직한 워크플로",
     "name: test\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
     "    steps:\n      - uses: actions/checkout@v4\n      - run: pytest\n"),
    ("honest-on-map", "on: 을 맵으로 쓰고 branches 필터",
     "name: ci\non:\n  push:\n    branches: [main]\n  pull_request:\n    types: [opened, synchronize]\n"
     "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make\n"),
    ("honest-yesno", "YAML 1.1 이 bool 로 접는 키·값 다수 (yes/no/off/on/y/n)",
     "name: legacy\non: [push]\nenv:\n  yes: a\n  no: b\n  off: c\n  on: d\n  y: e\n  n: f\n"
     "jobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"),
    ("honest-truefalse", "true/false 키와 값",
     "name: tf\non: [push]\nenv:\n  true: 1\n  false: 0\n  TRUE: x\n  False: y\n"
     "jobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"),
    ("honest-null", "null 계열 키 (~, null, Null, NULL)",
     "name: nul\non: [push]\nenv:\n  \"~\": a\n  null: b\n  Null: c\n  NULL: d\n"
     "jobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"),
    ("honest-numeric", "숫자·8진수·sexagesimal 형태 키",
     "name: num\non: [push]\nenv:\n  1: a\n  0o17: b\n  1:2:3: c\n  1e3: d\n"
     "jobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"),
    ("honest-realgate", "본 계약 정본 워크플로 자신",
     wf()),
]


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    os.makedirs(os.path.join(out, "honest"), exist_ok=True)
    idx = []
    for cid, exp, desc, text in CASES:
        with open(os.path.join(out, cid + ".yml"), "wb") as f:
            f.write(text.encode("utf-8"))
        idx.append("%s|%s|%s" % (cid, exp, desc))
    open(os.path.join(out, "INDEX.txt"), "w", encoding="utf-8").write("\n".join(idx) + "\n")
    hidx = []
    for hid, desc, text in HONEST:
        with open(os.path.join(out, "honest", hid + ".yml"), "wb") as f:
            f.write(text.encode("utf-8"))
        hidx.append("%s|VALUE_OK|%s" % (hid, desc))
    open(os.path.join(out, "honest", "INDEX.txt"), "w", encoding="utf-8").write("\n".join(hidx) + "\n")
    print("fixtures=%d (blob 판정) + %d (정직 워크플로 키트리) → %s" % (len(idx), len(hidx), out))
```
### mut-v222.py  (sha256 `57a713c2599108d637d265e008d12fb7b740deebe289e11ac05b7c761047ee42` · 138행)

```python
#!/usr/bin/env python3
"""역방향 fail-open 사냥 — «신규 술어가 실제로 판정을 지고 있는가» 를 뮤테이션으로 확인한다.

각 뮤테이션은 v2.22 술어의 **한 검사만** 무력화한 사본을 만들고 그 검사가 «유일하게» 잡던
픽스처를 돌린다.  기대는 `BLOB_OK`(= 무력화하면 통과한다 = 그 검사가 판정을 지고 있었다).
**`UNVERIFIED_REVISION` 이 그대로면** 두 경우 중 하나다:
  (a) 다른 검사가 «벨트»로 같은 자리를 잡고 있다(중복 방어 — 기록하고 어느 검사인지 적는다)
  (b) 그 검사가 «죽은 코드»다(= 결함 — 그러면 그렇게 적는다)
자기신고가 아니라 **관측 가능한 판정 뒤집힘**으로 본다.
"""
import pathlib, subprocess, sys

SP = pathlib.Path(__file__).resolve().parent
SRC = (SP / "wfcanon-v222.py").read_text(encoding="utf-8")
PY = "/Users/harris/Development/private/kis_unified_sts/.venv/bin/python"
OUT = SP / "mut"
OUT.mkdir(exist_ok=True)

# (id, 무력화 대상, old, new, 픽스처, 모드)
MUT = [
 ("M1-C1-dup", "C-1 전 노드 중복 키 검출",
  '    if dups:\n        print("WF-D1 중복 키 검출', '    if False:\n        print("WF-D1 중복 키 검출',
  "c1-dupsteps-benign-first", "blob"),
 ("M2-merge-key", "`<<` merge key 금지",
  '    if merges:\n        print("WF-D2 `<<`', '    if False:\n        print("WF-D2 `<<`',
  "m2-merge-key", "blob"),
 ("M3-keytree-belt", "두 파서 `.value` 키 트리 벨트",
  '    if not same_tree:\n        print("WF-D3 compose', '    if False:\n        print("WF-D3 compose',
  "m2-merge-key", "blob"),
 ("M4-parser-pin", "yq 파서 버전 핀",
  '    if not vok:\n        print("WF-P1', '    if False:\n        print("WF-P1',
  "pos-canonical", "blob-fakeyq"),
 ("M5-top-allowlist", "최상위 allowlist",
  '    if outside:\n        why.append("최상위 allowlist 밖 키', '    if False:\n        why.append("최상위 allowlist 밖 키',
  "m2-top-concurrency", "blob"),
 ("M6-permissions", "permissions 존재+값 핀",
  '    if "permissions" not in doc:', '    if False and "permissions" not in doc:',
  "f4-perms-absent", "blob"),
 ("M6b-permissions-val", "permissions 값 핀(정확히 {contents: read})",
  '    elif doc["permissions"] != PERMS_EXACT:', '    elif False:',
  "f4-perms-write", "blob"),
 ("M7-on", "on ⊆ {pull_request, push}",
  '    if not onset or not (onset <= ON_ALLOW):', '    if False:',
  "m1-on-schedule", "blob"),
 ("M8-jobs-count", "jobs 정확히 1개",
  '    if len(jobs) != 1:', '    if False:',
  "f2-sibling-job", "blob"),
 ("M9-job-keys", "게이트 잡 허용 키 닫힌 집합",
  '    if jkeys != JOB_ALLOW:', '    if False:',
  "13j-job-container", "blob"),
 ("M10-name-pin", "잡 name 값-핀",
  '    elif job.get("name") != GATE_JOB:', '    elif False:',
  "f2-name-free", "blob"),
 ("M11-runs-on", "runs-on 허용 리터럴 2개",
  '    if not isinstance(ro, str) or ro not in RUNS_ON_OK:', '    if False:',
  "f4-runson-2204", "blob"),
 ("M12-steps-order", "steps 정확히 3개·순서 고정",
  '        canon_step(s1, STEP_VER, CANON_B, "②B/verify sha256", why)\n        canon_step(s2, STEP_RUN, CANON_A, "③A/run harness", why)',
  '        canon_step(s1, STEP_RUN, CANON_A, "②(뮤테이션: v2.21 순서)", why)\n        canon_step(s2, STEP_VER, CANON_B, "③(뮤테이션: v2.21 순서)", why)',
  "f1-v221-order", "blob"),
 ("M13-checkout-pin", "체크아웃 uses SHA 핀",
  '        if s0.get("uses") != CHECKOUT_USES:', '        if False:',
  "f4-checkout-tag", "blob"),
 ("M14-with-persist", "persist-credentials `is False`",
  '            if "persist-credentials" in w and w["persist-credentials"] is not False:',
  '            if False:',
  "f4-persistcred-true", "blob"),
 ("M14b-with-fetchdepth", "fetch-depth 정수 0 (bool 배제)",
  '            if "fetch-depth" in w and not is_exact_int(w["fetch-depth"], 0):', '            if False:',
  "f4-fetchdepth-false", "blob"),
 ("M15-coe-key", "continue-on-error 키 부재",
  '    if "continue-on-error" in st:', '    if False:',
  "f1-coe-false", "blob"),
 ("M16-shell", "SHELL_OK 3값",
  '    if "shell" in st and str(st["shell"]).strip() not in SHELL_OK:', '    if False:',
  "f1-shell-sh", "blob"),
 ("M17-run-step-keys", "run 스텝 허용 키 닫힌 집합",
  '    extra = sorted(keys - RUN_STEP_REQ - RUN_STEP_OPT)', '    extra = []',
  "13e-step-env", "blob"),
 ("M1b-C1+belt", "C-1 중복 검출 **+** 키 트리 벨트 (이중)",
  '    if dups:\n        print("WF-D1 중복 키 검출', '    if False:\n        print("WF-D1 중복 키 검출',
  "c1-dupsteps-benign-first", "blob", [('    if not same_tree:\n        print("WF-D3 compose', '    if False:\n        print("WF-D3 compose')]),
 ("M2b-merge+belt", "`<<` 금지 **+** 키 트리 벨트 (이중)",
  '    if merges:\n        print("WF-D2 `<<`', '    if False:\n        print("WF-D2 `<<`',
  "m2-merge-key", "blob", [('    if not same_tree:\n        print("WF-D3 compose', '    if False:\n        print("WF-D3 compose')]),
 ("M2c-merge+belt+allow", "`<<` 금지 **+** 키 트리 벨트 **+** 최상위 allowlist (삼중)",
  '    if merges:\n        print("WF-D2 `<<`', '    if False:\n        print("WF-D2 `<<`',
  "m2-merge-key", "blob", [('    if not same_tree:\n        print("WF-D3 compose', '    if False:\n        print("WF-D3 compose'),
                           ('    if outside:\n        why.append("최상위 allowlist 밖 키', '    if False:\n        why.append("최상위 allowlist 밖 키')]),
 ("M6c-permissions-both", "permissions 존재 **+** 값 두 분기 (이중)",
  '    if "permissions" not in doc:\n        why.append("permissions 키 부재(= 리포/조직 기본값 = blob 밖·정적 결정 불가)")\n    elif doc["permissions"] != PERMS_EXACT:\n        why.append("permissions = %r \u2260 정확히 %r" % (doc["permissions"], PERMS_EXACT))',
  '    if False:\n        pass\n    elif False:\n        pass',
  "f4-perms-absent", "blob", []),
 ("M8b-jobs-count-solo", "jobs 정확히 1개 (name 정본인 형제 잡 픽스처)",
  '    if len(jobs) != 1:', '    if False:',
  "f2-sibling-namesok", "blob", []),
 ("M15b-coe+stepkeys", "continue-on-error 키 **+** run 스텝 허용 키 (이중)",
  '    if "continue-on-error" in st:', '    if False:',
  "f1-coe-false", "blob", [('    extra = sorted(keys - RUN_STEP_REQ - RUN_STEP_OPT)', '    extra = []')]),
 ("M18-server-hit", "서버 이름 필터 hit 유일성",
  '    if len(hit) != 1:', '    if False:',
  "dupname", "server"),
]

fx = SP / "fx"
fake = SP / "fx84v222" / "fakeyq" / "yq"
print("  %-22s %-40s %-26s %-14s %s" % ("뮤테이션", "무력화 대상", "픽스처", "기대", "실측"))
flip = same = 0
for _m in MUT:
    mid, what, old, new, fixture, mode = _m[:6]
    extra_subs = _m[6] if len(_m) > 6 else []
    if SRC.count(old) != 1:
        print("  %-22s ** 앵커 출현 %d회 — 뮤테이션 불가 **" % (mid, SRC.count(old)))
        continue
    p = OUT / (mid + ".py")
    _src = SRC.replace(old, new)
    for _o, _n in extra_subs:
        assert _src.count(_o) == 1, (mid, _o[:40])
        _src = _src.replace(_o, _n)
    p.write_text(_src, encoding="utf-8")
    env = None
    if mode == "server":
        target = SP / "fx84v222" / "jobs" / "dupname.json"; m = "server"; exp = "SERVER_OK"
    elif mode == "blob-fakeyq":
        target = fx / (fixture + ".yml"); m = "blob"; exp = "BLOB_OK"
        env = {"WF_YQ": str(fake)}
    else:
        target = fx / (fixture + ".yml"); m = "blob"; exp = "BLOB_OK"
    import os
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run([PY, str(p), m, str(target)], capture_output=True, text=True, env=e)
    got = [l[len("RESULT="):] for l in r.stdout.split("\n") if l.startswith("RESULT=")]
    got = got[-1] if got else "<none>"
    mark = "판정 뒤집힘 = 이 검사가 지고 있었다" if got == exp else "**불변 — 벨트/죽은코드 판별 필요**"
    if got == exp: flip += 1
    else: same += 1
    print("  %-22s %-40s %-26s %-14s %-20s %s" % (mid, what, fixture, exp, got, mark))
print("  ⇒ 판정 뒤집힘 %d / 불변 %d  (불변 항은 아래 «벨트 판별» 참조)" % (flip, same))
```
### canon-recon-v222.py  (sha256 `26ae758fc05c023b123300c62543dc04dbe1b5837a0a6ecd5556a96db80c1d4d` · 102행)

```python
#!/usr/bin/env python3
"""[G1] 정본 «잡 템플릿» **재-파생(re-derivation)** — byte 대조가 아니다.

계약에는 잡 템플릿의 코드펜스가 «없다»(실측: `^[[:space:]]*jobs:` 0건 / 7,912행).
byte 로 핀된 것은 **정본 A(:5713-5716)·정본 B(:5724-5727) = run 본문 둘뿐**이다.
따라서 술어가 쓰는 «정본 잡» 은 산문 불릿에서 **재구성한 것**이며, 이 파일이 그 재구성을
**독립 아티팩트로 실체화**하고 각 줄의 계약 근거를 병기한다.

**이것은 «계약에 이런 펜스가 있다» 가 아니라 «산문을 이렇게 읽었다» 이다.**
다른 소비자가 다르게 읽을 수 있는 자리는 DERIVATION 표의 «판단» 열에 적었다.
"""
import hashlib, pathlib, subprocess, sys

SP = pathlib.Path(__file__).resolve().parent
SHA = "957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d"
CO = "3d3c42e5aac5ba805825da76410c181273ba90b1"

# 계약 산문 불릿 → YAML 줄 (독립 재타이핑 · mkwf-v222.py 를 import 하지 않는다)
RECON = (
    "name: tos-gate\n"
    "on: [pull_request]\n"
    "permissions:\n"
    "  contents: read\n"
    "jobs:\n"
    "  tos-gate:\n"
    "    name: tos-gate\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - uses: actions/checkout@" + CO + "\n"
    "        with:\n"
    "          fetch-depth: 0\n"
    "          persist-credentials: false\n"
    '      - name: "tos-gate: verify harness sha256"\n'
    "        run: |\n"
    "          set -euo pipefail\n"
    "          printf '%s  tools/tos_entry_harness.sh\\n' " + SHA + " | shasum -a 256 -c -\n"
    '      - name: "tos-gate: run harness"\n'
    "        run: |\n"
    "          set -euo pipefail\n"
    "          bash tools/tos_entry_harness.sh\n"
)

DERIVATION = [
    # (YAML 요소, 계약 근거, 성격, 판단이 개입한 자리)
    ("최상위 키 집합", ":5644", "닫힌 allowlist `{name, run-name, on, permissions, jobs}`",
     "`name`·`run-name` 은 **선택**이다(밖이 아니면 통과) — 재구성본은 `name` 만 둔다"),
    ("`on: [pull_request]`", ":5655", "`on` ⊆ `{pull_request, push}` · list·map 양형",
     "**⊆ 의 좌변이 «키 집합»인지 미규정** — 키 집합으로 읽었다(EC-4)"),
    ("`permissions: {contents: read}`", ":5651-5654", "존재 강제 + **정확히** 그 값", "없음"),
    ("`jobs` 1개 · 잡 id `tos-gate`", ":5659-5662", "«정확히 1개» ∧ 키 == 계약 리터럴", "없음"),
    ("잡 키 = `{name, runs-on, steps}`", ":5663-5664", "닫힌 집합", "없음"),
    ("`name: tos-gate`", ":5665-5671", "존재 강제 + 값-핀", "없음"),
    ("`runs-on: ubuntu-latest`", ":5672-5675", "허용 «정확히 2개» 중 하나 · 스칼라만",
     "재구성본은 첫째 값을 쓴다(`ubuntu-24.04` 도 정본 — `ctrl-runs-on-2404` 가 대조)"),
    ("`steps` 3개·순서 고정", ":5676-5689", "[① 체크아웃 · ② 정본 B · ③ 정본 A]",
     "**v2.22 가 반전한 축** — :5689·:5708 이 «② 정본 B → ③ 정본 A» 를 명시"),
    ("`uses: actions/checkout@3d3c…`", ":5677-5679", "허용 SHA = 이 1개 계약 리터럴 핀", "없음"),
    ("체크아웃 키 = `{uses, with}`", ":5680", "닫힌 키",
     "**체크아웃 스텝의 `name:` 부재가 문언에 명시돼 있지 않다** — 닫힌 키에서 «파생»했다(EC-3)"),
    ("`with: {fetch-depth: 0, persist-credentials: false}`", ":5680-5688", "존재 강제 + **정확히** 그 값",
     "`fetch-depth` 는 bool 배제 정수 0 · `persist-credentials` 는 음극성이라 `is False` 만(파이썬 등가 함정)"),
    ("스텝 ② `name` 리터럴", ":5721", "계약 리터럴 (byte 불변)", "없음"),
    ("스텝 ② `run` 본문", ":5724-5727", "**계약 코드펜스 = 정본 B (byte 핀)**",
     "**여기만 byte 대조다** — 나머지는 전부 재-파생"),
    ("스텝 ③ `name` 리터럴", ":5710", "계약 리터럴 (byte 불변)", "없음"),
    ("스텝 ③ `run` 본문", ":5713-5716", "**계약 코드펜스 = 정본 A (byte 핀)**",
     "**여기만 byte 대조다**"),
    ("run 스텝 메타", ":5752-5762", "`{name, run}` + 선택 `{shell, timeout-minutes}` · `continue-on-error` 키 부재",
     "**`if:` 는 :5759 가 «허용 값 집합»을 주지만 :5762 닫힌 집합엔 없다 — 좁은 쪽(부재)을 따랐다(EC-1)**"),
    ("`|` literal block scalar 표기", ":5750", "에라타 ⓐ/E1 — `>` folded 는 접혀 불일치", "없음"),
]

if __name__ == "__main__":
    out = SP / "canon-job-template.reconstructed.yml"
    out.write_bytes(RECON.encode("utf-8"))
    h = hashlib.sha256(RECON.encode()).hexdigest()
    print("[G1] 정본 잡 템플릿 **재-파생본** → %s" % out.name)
    print("     sha256 = %s · %d행 · %d바이트" % (h, RECON.count("\n"), len(RECON.encode())))
    print("     **성격 = re-derivation(산문→구조), NOT byte comparison.**"
          "  계약에 이 펜스는 «존재하지 않는다».")
    print()
    print("  %-44s %-16s %s" % ("YAML 요소", "계약 근거", "성격 / 판단이 개입한 자리"))
    for elem, ref, kind, judg in DERIVATION:
        print("  %-44s %-16s %s" % (elem, ref, kind))
        if judg != "없음":
            print("  %-44s %-16s   ↳ 판단: %s" % ("", "", judg))
    print()
    # 독립 재타이핑이 픽스처 생성기와 «수렴»하는가 (byte 대조)
    pos = SP / "fx" / "pos-canonical.yml"
    if pos.exists():
        same = pos.read_bytes() == RECON.encode()
        print("  독립 재타이핑 vs 픽스처 생성기 `mkwf-v222.py` 의 `pos-canonical.yml` → **byte 동일 = %s**" % same)
        if not same:
            import difflib
            for d in list(difflib.unified_diff(pos.read_text().split("\n"), RECON.split("\n"),
                                               "pos-canonical.yml", "reconstructed", lineterm=""))[:20]:
                print("    " + d)
    # 재-파생본이 술어를 통과하는가 (양성 앵커)
    r = subprocess.run([sys.executable, str(SP / "wfcanon-v222.py"), "blob", str(out)],
                       capture_output=True, text=True)
    res = [l for l in r.stdout.split("\n") if l.startswith("RESULT=")]
    print("  재-파생본에 대한 술어 판정 = %s   (양성 앵커 — 재구성이 자기 술어와 정합)" % (res[-1] if res else "?"))
```
### canon-job-template.reconstructed.yml  (sha256 `4a4e1f1f46ad7fde126a29fcfb8820ff65254e1f47fc10049caceff3f59befe3` · 21행)

```yaml
name: tos-gate
on: [pull_request]
permissions:
  contents: read
jobs:
  tos-gate:
    name: tos-gate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          fetch-depth: 0
          persist-credentials: false
      - name: "tos-gate: verify harness sha256"
        run: |
          set -euo pipefail
          printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
      - name: "tos-gate: run harness"
        run: |
          set -euo pipefail
          bash tools/tos_entry_harness.sh
```
### t84v222.sh  (sha256 `6bbfbfbb55ab831478e03630ce1210d97d6f34736cbdccd10ce7d6c519727092` · 568행)

```bash
#!/usr/bin/env bash
# t84v222.sh — v2.22(계약 8ec22754) T-84 드라이버.
#   t84v221.sh(sha256 962cc027…) 의 헬퍼 블록 원문을 재사용하고 seam 을 v2.22 엔드포인트로 확장한다.
#   GET-only · 서버 «쓰기» 0 · 픽스처는 scratchpad 독립 repo.
#   절 번호 = 브리프 §3 의 9항 번호 (보고서 절 번호와 1:1).
SP="$(cd "$(dirname "$0")" && pwd)"
EX="$SP/u17-verify-v222.sh"                       # 판정 실행기 (v2.22)
WFS="$SP/wfcanon-v222.py"                         # (b)③ 정본 «잡 템플릿» 술어 (v2.22)
EX221="$SP/u17-verify-v221.sh"                    # 직전 판 실행기 — 대조군
WFS221="$SP/wfcanon-v221.py"                      # 직전 판 술어 — 대조군
PY=/Users/harris/Development/private/kis_unified_sts/.venv/bin/python
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
WF=.github/workflows/tos-gate.yml
EVILWF=.github/workflows/evil.yml
OR=kakao-harris-lee/kis_unified_sts; PINURL=https://github.com/kakao-harris-lee/kis_unified_sts.git
WB=mission-critical-trading-operating-system; REPO=/Users/harris/Development/private/kis_unified_sts
CT="$REPO/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md"
DP="$REPO/docs/plans/2026-08-11-tos-completion-development-plan.md"
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
TLAND=2026-08-10T00:00:00Z
THEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1     # SIMULATED target 브랜치 HEAD sha
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
FX="$SP/fx84v222"; SEAM="$SP/seam222"; FXW="$SP/fx"
sec(){ printf '\n########## %s ##########\n' "$*"; }
sub(){ printf '\n---------- %s ----------\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; git -C "$1" remote add origin "${2:-$PINURL}"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; }
art(){ mkdir -p "$1/$(dirname $PC)"; { [ -n "${2:-}" ] && printf 'owner_repo: %s\n' "$2"; [ -n "${3:-}" ] && printf 'target_branch: %s\n' "$3"; printf 'operator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED test fixture\n'; } > "$1/$PC"
  git -C "$1" add -A; git -C "$1" commit -q -m "P: D0A-PREVENTION-CONTROL (SIMULATED)"; git -C "$1" rev-parse HEAD; }
wfc(){ mkdir -p "$1/.github/workflows"; cp "$FXW/${2:-pos-canonical}.yml" "$1/$WF"; git -C "$1" add -A; git -C "$1" commit -q -m "W: add $WF (SIMULATED)"; git -C "$1" rev-parse HEAD; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact\n' > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "D0-A: introduce config/tos_completion.yaml"; git -C "$1" rev-parse HEAD; }
run(){ # run <repo> [responder] [executor] [env-prefix]
  echo "-- remotes --"; git -C "$1" remote -v | sed 's/^/  | /'
  echo "-- artifact @HEAD --"; git -C "$1" show "HEAD:$PC" 2>/dev/null | sed 's/^/  | /'
  git -C "$1" log --oneline --format='%h %s' | sed 's/^/  /'
  echo "\$ ${4:-}U17_RESPONDER=${2:-gh} bash $(basename "${3:-$EX}") <fixture>"
  env ${4:-} U17_RESPONDER="${2:-gh}" U17_CAPTURE_DIR="$(mktemp -d)" bash "${3:-$EX}" "$1"; echo "u17_rc=$?"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; if [ -f "$4" ]; then cp "$4" "$1/$(k "$2").body"; else printf '%s\n' "$4" > "$1/$(k "$2").body"; fi; }
ACT='{"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}'
RULES_APPLIED(){ printf '[{"type":"required_status_checks","ruleset_id":%s,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":%s},{"type":"non_fast_forward","ruleset_id":%s},{"type":"deletion","ruleset_id":%s}]' "$1" "$1" "$1" "$1"; }
RSET_ONE(){ printf '{"id":%s,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"%s","updated_at":"%s","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}' "$1" "$2" "$3"; }
RSET_LIST(){ printf '[{"id":%s,"name":"protect_main","target":"branch","enforcement":"active","created_at":"%s","updated_at":"%s"}]' "$1" "$2" "$3"; }
base_common(){ inject "$1" "apps/github-actions" 200 '{"id":15368,"slug":"github-actions","name":"GitHub Actions"}'; inject "$1" "repos/$OR" 200 '{"full_name":"kakao-harris-lee/kis_unified_sts","default_branch":"main"}'; }
seam_ruleset(){ rm -rf "$1"; mkdir -p "$1"; base_common "$1"
  inject "$1" "repos/$OR/branches/main/protection" 404 '{"message":"Branch not protected","status":"404"}'
  inject "$1" "repos/$OR/rules/branches/main" 200 "$(RULES_APPLIED "$2")"
  inject "$1" "repos/$OR/rulesets" 200 "$(RSET_LIST "$2" "$3" "$4")"
  inject "$1" "repos/$OR/rulesets/$2" 200 "$(RSET_ONE "$2" "$3" "$4")"; }
contents_json(){ python3 - "$1" "$2" "$3" <<'PY'
import json,sys,base64
t=open(sys.argv[1],'rb').read()
print(json.dumps({"name":sys.argv[3].split("/")[-1],"path":sys.argv[3],"sha":sys.argv[2],"size":len(t),"type":"file","encoding":"base64","content":base64.b64encode(t).decode()+"\n"}))
PY
}
# ── [v2.22·M-7] (b-blob)@target seam — branches/<target> → .commit.sha → contents?ref=<sha>
seam_target(){ # seam_target <dir> <fixture-id|NONE> [target-head]
  local d="$1" fx="$2" th="${3:-$THEAD}"
  inject "$d" "repos/$OR/branches/main" 200 "{\"name\":\"main\",\"commit\":{\"sha\":\"$th\",\"url\":\"SIMULATED\"}}"
  if [ "$fx" = NONE ]; then inject "$d" "repos/$OR/contents/$WF?ref=$th" 404 '{"message":"Not Found","status":"404"}'
  else cp "$FXW/$fx.yml" "$d/twf.txt"; inject "$d" "repos/$OR/contents/$WF?ref=$th" 200 "$(contents_json "$d/twf.txt" "$(git hash-object "$d/twf.txt")" "$WF")"; fi; }
# ── check-run 원소 (details_url 로 run id 를 준다 — 정방향 매핑)
crun(){ # crun <name> <conclusion> <appid> <head> <suite> <runid>
  printf '{"name":"%s","conclusion":"%s","app":{"id":%s,"slug":"github-actions"},"head_sha":"%s","check_suite":{"id":%s},"details_url":"https://github.com/%s/actions/runs/%s/job/9%s"}' \
    "$1" "$2" "$3" "$4" "$5" "$OR" "$6" "$6"; }
wfrun(){ # wfrun <dir> <runid> <path> <head> <suite> [conclusion]
  inject "$1" "repos/$OR/actions/runs/$2" 200 "{\"id\":$2,\"name\":\"tos-gate\",\"path\":\"$3\",\"head_sha\":\"$4\",\"check_suite_id\":$5,\"conclusion\":\"${6:-success}\"}"; }
jobs_json(){ # jobs_json <variant> <head>
  local v="$1" h="$2" steps jc=success extra=""
  case "$v" in
    ok|dupname|skipped|neutral|cancelled|nullconc)
       steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":2},{"name":"tos-gate: run harness","conclusion":"success","number":3},{"name":"Complete job","conclusion":"success","number":4}]' ;;
    noverify) steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2}]' ;;
    verifyfail) steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: verify harness sha256","conclusion":"failure","number":2}]' ;;
    norun) steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":2}]' ;;
    jobfail) steps='[{"name":"tos-gate: verify harness sha256","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2}]'; jc=failure ;;
  esac
  case "$v" in skipped) jc=skipped ;; neutral) jc=neutral ;; cancelled) jc=cancelled ;; nullconc) jc=null ;; esac
  local q='"'; [ "$v" = nullconc ] && q=''
  [ "$v" = dupname ] && extra=",{\"id\":900002,\"run_id\":424242,\"name\":\"tos-gate\",\"status\":\"completed\",\"conclusion\":\"success\",\"head_sha\":\"$h\",\"steps\":$steps}"
  printf '{"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":%s%s%s,"head_sha":"%s","steps":%s}%s]}' "$q" "$jc" "$q" "$h" "$steps" "$extra"; }
# ── 리비전 seam — 단일 정본 check-run (기본 경로)
rev_seam(){ # rev_seam <dir> <d> <head> <suite> <merged_at|NOPR> [wf-fixture] [jobs-variant] [runid]
  local dir="$1" d="$2" h="$3" s="$4" m="$5" fx="${6:-pos-canonical}" jv="${7:-ok}" rid="${8:-424242}"
  if [ "$m" = NOPR ]; then inject "$dir" "repos/$OR/commits/$d/pulls" 200 '[]'; return; fi
  inject "$dir" "repos/$OR/commits/$d/pulls" 200 "[{\"number\":9999,\"state\":\"closed\",\"merged_at\":\"$m\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$h\"}}]"
  inject "$dir" "repos/$OR/commits/$h/check-runs" 200 "{\"total_count\":2,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s},\"details_url\":\"https://github.com/$OR/actions/runs/111/job/1\"},$(crun tos-gate success 15368 "$h" "$s" "$rid")]}"
  inject "$dir" "repos/$OR/check-suites/$s" 200 "{\"id\":$s,\"head_sha\":\"$h\",\"app\":{\"id\":15368},\"status\":\"completed\",\"conclusion\":\"success\"}"
  wfrun "$dir" "$rid" "$WF" "$h" "$s"
  inject "$dir" "repos/$OR/actions/runs/111" 200 "{\"id\":111,\"path\":\".github/workflows/test.yml\",\"head_sha\":\"$h\",\"check_suite_id\":$s}"
  inject "$dir" "repos/$OR/actions/runs?check_suite_id=$s" 200 "{\"total_count\":1,\"workflow_runs\":[{\"id\":$rid,\"name\":\"tos-gate\",\"path\":\"$WF\",\"head_sha\":\"$h\",\"check_suite_id\":$s,\"conclusion\":\"success\"}]}"
  cp "$FXW/$fx.yml" "$dir/wf.txt"; inject "$dir" "repos/$OR/contents/$WF?ref=$h" 200 "$(contents_json "$dir/wf.txt" "$(git hash-object "$dir/wf.txt")" "$WF")"
  inject "$dir" "repos/$OR/actions/runs/$rid/jobs" 200 "$(jobs_json "$jv" "$h")"; }
inj_wf_at(){ cp "$FXW/$2.yml" "$1/wf.txt"; inject "$1" "repos/$OR/contents/$WF?ref=$3" 200 "$(contents_json "$1/wf.txt" "$(git hash-object "$1/wf.txt")" "$WF")"; }

rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"
printf 't84v222_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'HEAD=%s  freeze=8ec227541d12ca290bbe4906ebe146aed5f06040\n' "$(git -C "$REPO" rev-parse HEAD)"
for f in "$EX" "$WFS" "$SP/mkwf-v222.py" "$SP/derive-v222.py" "$EX221" "$WFS221" "$SP/mkwf-v221.py" "$SP/t84v221.sh"; do
  printf 'sha256(%-22s)=%s\n' "$(basename "$f")" "$(shasum -a 256 "$f" | cut -d" " -f1)"; done
printf -- '-- 실행기 diff(v2.21 → v2.22) 행수 = %s (파생기 훅 12개) --\n' "$(diff "$EX221" "$EX" | grep -c '^[<>]')"
printf 'git=%s · gh=%s · yq=%s · python3=%s · venv=%s (PyYAML %s)\n' "$(git --version)" "$(gh --version|head -1)" "$(yq --version)" "$(python3 -V)" "$($PY -V)" "$($PY -c 'import yaml;print(yaml.__version__)')"

########################################################################
sec "3. 정본 리터럴 결속 — 계약 코드펜스·본문 리터럴 == 술어 상수 (byte 일치)"
$PY - "$SP" "$CT" <<'PYEOF'
import sys, pathlib, importlib.util
SP = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("w", SP / "wfcanon-v222.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
spec21 = importlib.util.spec_from_file_location("w21", SP / "wfcanon-v221.py")
m21 = importlib.util.module_from_spec(spec21); spec21.loader.exec_module(m21)
C = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8").split("\n")
def fence(anchor):
    i = next(k for k, l in enumerate(C) if anchor in l)
    f = [k for k in range(i, i + 14) if C[k].strip() == "```"]
    return "\n".join(C[f[0]+1:f[1]]), f[0]+2, f[1]
A, a1, a2 = fence("정본 A** 와 일치")
B, b1, b2 = fence("정본 B** 와 일치")
print("  계약 :%d-%d 정본 A = %r" % (a1, a2, A))
print("  술어 CANON_A            = %r   → byte 동일? %s" % (m.CANON_A, A == m.CANON_A))
print("  v2.21 술어 CANON_A      = %r   → **v2.22 와 byte 동일? %s**  (코드 델타 0 축)" % (m21.CANON_A, m21.CANON_A == m.CANON_A))
print("  계약 :%d-%d 정본 B = %r" % (b1, b2, B))
print("  술어 CANON_B            = %r   → byte 동일? %s" % (m.CANON_B, B == m.CANON_B))
print("  v2.21 술어 CANON_B      = %r   → **v2.22 와 byte 동일? %s**  (코드 델타 0 축)" % (m21.CANON_B, m21.CANON_B == m.CANON_B))
print()
doc = "\n".join(C)
def lit(name, value, needle=None):
    n = needle if needle is not None else value
    hits = [i+1 for i, l in enumerate(C) if n in l]
    print("  %-22s 술어=%-58r 계약 본문 출현=%s%s" % (name, value, len(hits), (" :%s" % hits[:4]) if hits else "  ← **부재**"))
    return len(hits) > 0
allok = True
allok &= lit("STEP_VER", m.STEP_VER, '`name: "tos-gate: verify harness sha256"`')
allok &= lit("STEP_RUN", m.STEP_RUN, '`name: "tos-gate: run harness"`')
allok &= lit("GATE_JOB", m.GATE_JOB, "게이트 체크 이름 = `tos-gate`")
allok &= lit("CHECKOUT_USES", m.CHECKOUT_USES, "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1")
allok &= lit("CHECKOUT_WITH", m.CHECKOUT_WITH_KEYS, "`{fetch-depth: 0, persist-credentials: false}`")
allok &= lit("PERMS_EXACT", m.PERMS_EXACT, "**`permissions` = 존재 강제 + 정확히 `{contents: read}`**")
allok &= lit("RUNS_ON_OK", sorted(m.RUNS_ON_OK), "`{ubuntu-latest, ubuntu-24.04}`")
allok &= lit("TOP_ALLOW", sorted(m.TOP_ALLOW), "`{name, run-name, on, permissions, jobs}`")
allok &= lit("JOB_ALLOW", sorted(m.JOB_ALLOW), "닫힌 집합 `{name, runs-on, steps}`")
allok &= lit("SHELL_OK", sorted(m.SHELL_OK), "`{ bash , bash -euo pipefail {0} , bash -eo pipefail {0} }`")
allok &= lit("ON_ALLOW", sorted(m.ON_ALLOW), "**`on` ⊆ `{pull_request, push}`**")
allok &= lit("IF_OK", sorted(m.IF_OK), "`{ success() , ${{ success() }} }`")
allok &= lit("YQ 파서 핀", m.YQ_FLAVOR + " " + m.YQ_MAJMIN + "x", "`yq (mikefarah) v4.48.x`")
print()
print("  SHELL_OK v2.21 == v2.22 ? %s   (계약 문언만 «생략부호 → 3값 명시»로 바뀌었고 술어 코드는 불변)"
      % (m21.SHELL_OK == m.SHELL_OK))
print("  normalize() v2.21 == v2.22 ? %s   (코드 델타 0)"
      % (m21.normalize.__code__.co_code == m.normalize.__code__.co_code))
print("  ⇒ 모든 리터럴 계약 본문 실재 = %s" % allok)
print()
print("  **정본 «순서»** — 계약 :5689 / :5708 원문:")
for i, l in enumerate(C):
    if "② **정본 B 스텝" in l or "워크플로 `steps` 의 실행 순서는" in l:
        print("    :%d %s" % (i+1, l.strip()))
PYEOF

########################################################################
sec "3-2. [G1] 정본 «잡 템플릿» 재-파생 — 계약에 이 펜스는 «존재하지 않는다»"
echo "-- 양방향 실측: 계약 7,912행에 «^[[:space:]]*jobs:» 는 몇 건인가 --"
printf '  grep -cE \x27^[[:space:]]*jobs:\x27  → %s   (부재)\n' "$(grep -cE '^[[:space:]]*jobs:' "$CT")"
printf '  grep -c  \x27jobs\x27               → %s   (대조군 — 문자열 자체는 실재하므로 «부재»가 팬텀이 아니다)\n' "$(grep -c 'jobs' "$CT")"
printf '  yaml 코드펜스 위치                    → %s   (:3865 무관 · :5968 countersign 형식)\n' "$(grep -n '^```yaml' "$CT" | cut -d: -f1 | tr '\n' ' ')"
printf '  «정본 잡 템플릿» 산문 출현            → %s\n' "$(grep -n '정본 잡 템플릿' "$CT" | cut -d: -f1 | tr '\n' ' ')"
echo "  ⇒ byte 로 핀된 것은 정본 A(:5713-5716)·정본 B(:5724-5727) = run «본문» 둘뿐이다"
echo
$PY "$SP/canon-recon-v222.py"

########################################################################
sec "2·13. 실행기 파생 표 + 술어 배터리 (기대는 픽스처 생성기가 «미리» 적었다) · 회귀"
$PY "$SP/mkwf-v222.py" "$FXW" | sed 's/^/  /'
sub "B-1  v2.22 술어 × $(grep -c . "$FXW/INDEX.txt") 픽스처 — 기대/실측 + v2.21 대조군"
printf '  %-28s %-22s %-22s %-22s %s\n' id "기대(사전 기입)" "실측 v2.22" "대조군 v2.21" "판정"
FAIL=0; N21OK=0; NCLOSE=0; NTOT=0
while IFS='|' read -r cid exp desc; do
  [ -n "$cid" ] || continue; NTOT=$((NTOT+1))
  got=$($PY "$WFS" blob "$FXW/$cid.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  g21=$($PY "$WFS221" blob "$FXW/$cid.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  mark=OK; [ "$got" = "$exp" ] || { mark="**MISMATCH**"; FAIL=$((FAIL+1)); }
  [ "$g21" = BLOB_OK ] && N21OK=$((N21OK+1))
  { [ "$g21" = BLOB_OK ] && [ "$got" != BLOB_OK ]; } && { NCLOSE=$((NCLOSE+1)); mark="$mark ← v2.22 신규 차단"; }
  printf '  %-28s %-22s %-22s %-22s %s\n' "$cid" "$exp" "$got" "$g21" "$mark"
done < "$FXW/INDEX.txt"
echo "  ⇒ 기대 ≠ 실측 = $FAIL 건 / $NTOT · v2.21 이 BLOB_OK 를 낸 픽스처 = $N21OK · **v2.22 가 새로 닫은 자리 = $NCLOSE**"

sub "B-2  대표 4종 전문 transcript (양성 · 정규화 대조군 · F#1 순서 · C-1 시퀀스 내부)"
for c in pos-canonical ctrl-comments f1-v221-order c1-dup-in-step-run; do
  echo "== $c =="; sed 's/^/  | /' "$FXW/$c.yml"; $PY "$WFS" blob "$FXW/$c.yml" 2>&1 | sed 's/^/  /'
done

########################################################################
sec "4. [항목 1] per-d 결속 반례 — 두 층이 서로 다른 객체를 집는다 (blob=잡 id · 서버=표시 이름)"
sub "1-A  형제 잡: jobs.tos-gate(표시 이름 «gate (canonical)») + jobs.evil(name: tos-gate)"
sed 's/^/  | /' "$FXW/f2-sibling-job.yml"
R1="$FX/split"; mk "$R1"; art "$R1" "$OR" main >/dev/null; W1=$(wfc "$R1" f2-sibling-job); D1=$(d0a "$R1")
S1="$SEAM/split"; seam_ruleset "$S1" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z
rev_seam "$S1" "$D1" "$W1" 777001 "$TLAND" f2-sibling-job ok
# 서버 잡 응답: 표시 이름 «gate (canonical)» 인 정본 잡 + 표시 이름 «tos-gate» 인 우회 잡
inject "$S1" "repos/$OR/actions/runs/424242/jobs" 200 "{\"total_count\":2,\"jobs\":[{\"id\":900001,\"run_id\":424242,\"name\":\"gate (canonical)\",\"status\":\"completed\",\"conclusion\":\"success\",\"head_sha\":\"$W1\",\"steps\":[{\"name\":\"Set up job\",\"conclusion\":\"success\"}]},{\"id\":900002,\"run_id\":424242,\"name\":\"tos-gate\",\"status\":\"completed\",\"conclusion\":\"success\",\"head_sha\":\"$W1\",\"steps\":[{\"name\":\"tos-gate: verify harness sha256\",\"conclusion\":\"success\"},{\"name\":\"tos-gate: run harness\",\"conclusion\":\"success\"}]}]}"
seam_target "$S1" f2-sibling-job
echo; echo ">>> 대조군: v2.21 실행기 (기대 = PREVENTION_ACTIVE — 두 층이 다른 객체를 집는다)"
run "$R1" "file:$S1" "$EX221"
echo; echo ">>> v2.22 실행기 (기대 = PREVENTION_UNVERIFIED_REVISION)"
run "$R1" "file:$S1" "$EX"

sub "1-B  서버 층 단독 — 표시 이름 «tos-gate» 인 잡이 2개 (⑭ㄱ hit 비-유일)"
JD="$FX/jobs"; mkdir -p "$JD"; jobs_json dupname deadbeef > "$JD/dupname.json"
echo "  기대 v2.22 = UNVERIFIED_REVISION · 대조군 v2.21 = SERVER_OK(hit[0] 을 말없이 집는다)"
printf '  v2.22: '; $PY "$WFS" server "$JD/dupname.json" 2>&1 | sed -n 's/^RESULT=/RESULT=/p'
printf '  v2.21: '; $PY "$WFS221" server "$JD/dupname.json" 2>&1 | sed -n 's/^RESULT=/RESULT=/p'
$PY "$WFS" server "$JD/dupname.json" 2>&1 | sed 's/^/    /'

sub "1-C  per-리비전 결속 (N-11) — PR head 는 «비정본» · target 은 «정본» ⇒ 여전히 차단"
R2="$FX/perd"; mk "$R2"; art "$R2" "$OR" main >/dev/null; W2=$(wfc "$R2" pos-canonical); D2=$(d0a "$R2")
S2="$SEAM/perd"; seam_ruleset "$S2" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z
rev_seam "$S2" "$D2" "$W2" 777001 "$TLAND" f1-v221-order ok      # @d = v2.21 순서(비정본)
seam_target "$S2" pos-canonical                                   # @target = 정본
echo "  ⇒ (b-blob)@target 이 (b-blob)@d 를 «대체»하면 이 구성이 통과한다 — «추가»임을 실증한다"
run "$R2" "file:$S2" "$EX"

########################################################################
sec "5. [항목 2] 진입 비-vacuity — D = ∅ 에서 blob limb 가 «실제로 평가»되는가"
R3="$FX/entry"; mk "$R3"; art "$R3" "$OR" main >/dev/null; W3=$(wfc "$R3" pos-canonical)
echo "  D0-A 산출물(config/tos_completion.yaml) 존재? $( [ -e "$R3/config/tos_completion.yaml" ] && echo YES || echo 'NO ← D0-A 미착수' ) · D = ∅"
sub "2-양성  target 정본 ⇒ PREVENTION_ACTIVE"
S3="$SEAM/entry-pos"; seam_ruleset "$S3" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; seam_target "$S3" pos-canonical
run "$R3" "file:$S3" "$EX"
sub "2-음성-a  target 에 정본 파일 «부재»(404) ⇒ UNVERIFIED_REVISION (ABSENT 로 접지 않는다)"
S4="$SEAM/entry-404"; seam_ruleset "$S4" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; seam_target "$S4" NONE
run "$R3" "file:$S4" "$EX"
sub "2-음성-b  target blob 이 «이탈»(v2.21 순서) ⇒ UNVERIFIED_REVISION"
S5="$SEAM/entry-dev"; seam_ruleset "$S5" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; seam_target "$S5" f1-v221-order
run "$R3" "file:$S5" "$EX"
sub "2-대조군  같은 두 음성 seam 을 v2.21 실행기로 — (b)(c) 가 vacuous 인 채 ACTIVE 면 그것이 심판 #3 이 지적한 자리"
echo ">>> v2.21 × entry-404"; run "$R3" "file:$S4" "$EX221"
echo ">>> v2.21 × entry-dev"; run "$R3" "file:$S5" "$EX221"

########################################################################
sec "6. [항목 3] C-1 두 순서 — 잡 «안» steps: 중복"
for c in c1-dupsteps-benign-first c1-dupsteps-canon-first; do
  sub "$c"; sed 's/^/  | /' "$FXW/$c.yml"
  printf '  v2.22 = '; $PY "$WFS" blob "$FXW/$c.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1
  printf '  v2.21 = '; $PY "$WFS221" blob "$FXW/$c.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1
  $PY "$WFS" blob "$FXW/$c.yml" 2>&1 | grep -E '^WF-D[123]' | sed 's/^/    /'
done
sub "3-e2e  «무해 먼저» 를 실행기로 (v2.21 = ACTIVE / v2.22 = 차단)"
R4="$FX/dupsteps"; mk "$R4"; art "$R4" "$OR" main >/dev/null; W4=$(wfc "$R4" c1-dupsteps-benign-first); D4=$(d0a "$R4")
S6="$SEAM/dup"; seam_ruleset "$S6" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z
rev_seam "$S6" "$D4" "$W4" 777001 "$TLAND" c1-dupsteps-benign-first ok; seam_target "$S6" c1-dupsteps-benign-first
echo ">>> v2.21"; run "$R4" "file:$S6" "$EX221"
echo ">>> v2.22"; run "$R4" "file:$S6" "$EX"

########################################################################
sec "7. [항목 4] C-1 시퀀스 내부 — steps[i] 매핑 안의 중복 키"
for c in c1-dup-in-step-run c1-dup-in-step-name c1-dup-jobs c1-dup-permissions c1-dup-runs-on; do
  printf '  %-24s v2.22=%-22s v2.21=%-22s\n' "$c" \
    "$($PY "$WFS" blob "$FXW/$c.yml" 2>&1 | sed -n 's/^RESULT=//p'|tail -1)" \
    "$($PY "$WFS221" blob "$FXW/$c.yml" 2>&1 | sed -n 's/^RESULT=//p'|tail -1)"
done
sub "4-전문  c1-dup-in-step-run (시퀀스 원소 안의 중복 run:)"
sed 's/^/  | /' "$FXW/c1-dup-in-step-run.yml"; $PY "$WFS" blob "$FXW/c1-dup-in-step-run.yml" 2>&1 | sed 's/^/  /'

########################################################################
sec "8. [항목 5] C-1 정직 워크플로 발산 0 + construct/safe_load 대조군"
printf '  %-22s %-14s %s\n' id "«.value» 트리 판정" 설명
NDIV=0
while IFS='|' read -r hid exp desc; do
  [ -n "$hid" ] || continue
  got=$($PY "$WFS" keytree "$FXW/honest/$hid.yml" 2>&1 | sed -n 's/^RESULT=//p'|tail -1)
  [ "$got" = VALUE_OK ] || NDIV=$((NDIV+1))
  printf '  %-22s %-14s %s\n' "$hid" "$got" "$desc"
  $PY "$WFS" keytree "$FXW/honest/$hid.yml" 2>&1 | grep '^KT ' | sed 's/^/      /'
done < "$FXW/honest/INDEX.txt"
echo "  ⇒ 정직 워크플로 «.value» 키 트리 발산 = $NDIV 건 (기대 0)"
sub "5-대조군 전문 — honest-yesno (yes/no/off/on 키)"
sed 's/^/  | /' "$FXW/honest/honest-yesno.yml"
$PY "$WFS" keytree "$FXW/honest/honest-yesno.yml" 2>&1 | sed 's/^/  /'

########################################################################
sec "9. [항목 6] F#1 3축 + «자기수복 하니스» 반사실 대조"
sub "6-A  3축 — 술어 단위 (기대는 사전 기입)"
for c in f1-if-always f1-if-success f1-coe-true f1-coe-false f1-shell-sh f1-shell-pwsh f1-v221-order f1-timeout-zero; do
  printf '  %-20s v2.22=%-22s v2.21=%-22s\n' "$c" \
    "$($PY "$WFS" blob "$FXW/$c.yml" 2>&1 | sed -n 's/^RESULT=//p'|tail -1)" \
    "$($PY "$WFS221" blob "$FXW/$c.yml" 2>&1 | sed -n 's/^RESULT=//p'|tail -1)"
done
sub "6-B  «자기수복 하니스» 런타임 실증 — 부작용(마커 파일)으로 관측한다"
RT="$FX/selfheal"; rm -rf "$RT"; mkdir -p "$RT/tools"
cat > "$RT/canon.sh" <<'CANONEOF'
#!/usr/bin/env bash
# APPROVED harness (SIMULATED) — 승인된 바이트
echo APPROVED_HARNESS_RAN
CANONEOF
CSHA=$(shasum -a 256 "$RT/canon.sh" | cut -d' ' -f1)
cat > "$RT/tools/tos_entry_harness.sh" <<CANONEOF2
#!/usr/bin/env bash
# UNAPPROVED harness (SIMULATED) — 실행되면 부작용을 남기고 «자기 파일을 정본 바이트로 덮은 뒤» exit 0
touch "\$(dirname "\$0")/../EVIL_EXECUTED"
echo "EVIL: unapproved harness executed; self-healing to canonical bytes"
cp "\$(dirname "\$0")/../canon.sh" "\$0"
exit 0
CANONEOF2
ESHA=$(shasum -a 256 "$RT/tools/tos_entry_harness.sh" | cut -d' ' -f1)
echo "  정본(승인) 바이트 sha256      = $CSHA"
echo "  비승인 하니스 초기 sha256     = $ESHA   (≠ 정본 — 검증이 먼저면 여기서 비-0)"
stepA(){ ( cd "$1" && set -euo pipefail; bash tools/tos_entry_harness.sh ); }
stepB(){ ( cd "$1" && set -euo pipefail; printf '%s  tools/tos_entry_harness.sh\n' "$2" | shasum -a 256 -c - ); }
runorder(){ # runorder <label> <order:v221|v222>
  local L="$1" O="$2" W="$FX/sh-$2" out rc
  rm -rf "$W"; cp -R "$RT" "$W"; rm -f "$W/EVIL_EXECUTED"
  echo "  --- $L ---"
  echo "  진입 시 하니스 sha256 = $(shasum -a 256 "$W/tools/tos_entry_harness.sh" | cut -d' ' -f1)"
  if [ "$O" = v221 ]; then
    out=$(stepA "$W" 2>&1); rc=$?
    printf '  step② run harness   : %s   [rc=%s]\n' "$(printf '%s' "$out" | tr '\n' ' ')" "$rc"
    if [ "$rc" -eq 0 ]; then out=$(stepB "$W" "$CSHA" 2>&1); rc=$?
      printf '  step③ verify sha256 : %s   [rc=%s]\n' "$(printf '%s' "$out" | tr '\n' ' ')" "$rc"
    else printf '  step③ 미도달 (암묵 success() 게이트)\n'; fi
  else
    out=$(stepB "$W" "$CSHA" 2>&1); rc=$?
    printf '  step② verify sha256 : %s   [rc=%s]\n' "$(printf '%s' "$out" | tr '\n' ' ')" "$rc"
    if [ "$rc" -eq 0 ]; then out=$(stepA "$W" 2>&1); rc=$?
      printf '  step③ run harness   : %s   [rc=%s]\n' "$(printf '%s' "$out" | tr '\n' ' ')" "$rc"
    else printf '  step③ 미도달 (② 가 비-0 · set -euo pipefail 하 암묵 success() 게이트)\n'; fi
  fi
  echo "  ⇒ 부작용 관측(자기신고 아님): EVIL_EXECUTED 마커 = $( [ -e "$W/EVIL_EXECUTED" ] && echo '**실재 — 비승인 바이트가 실행됐다**' || echo '**부재 — 비승인 바이트가 실행되지 않았다**' )"
  echo "  ⇒ 종료 시 하니스 sha256 = $(shasum -a 256 "$W/tools/tos_entry_harness.sh" | cut -d' ' -f1)"
}
runorder "v2.21 정본 순서 [② 실행 → ③ 검증]  (반사실)" v221
runorder "v2.22 정본 순서 [② 검증 → ③ 실행]" v222
echo "  ⇒ 두 순서의 정적 blob 은 **같은 스텝 byte·같은 이름**이며 다른 것은 «순서»뿐이다:"
printf '     v2.21 순서 blob 판정: v2.22 술어=%s / v2.21 술어=%s\n' \
  "$($PY "$WFS" blob "$FXW/f1-v221-order.yml" 2>&1|sed -n 's/^RESULT=//p'|tail -1)" \
  "$($PY "$WFS221" blob "$FXW/f1-v221-order.yml" 2>&1|sed -n 's/^RESULT=//p'|tail -1)"

########################################################################
sec "10. [항목 7] anchor · «<<» merge key · 파서 버전"
for c in m2-anchor-dup-job m2-anchor-alias-only m2-merge-key; do
  sub "$c"; sed 's/^/  | /' "$FXW/$c.yml"
  printf '  v2.22=%s  v2.21=%s\n' \
    "$($PY "$WFS" blob "$FXW/$c.yml" 2>&1|sed -n 's/^RESULT=//p'|tail -1)" \
    "$($PY "$WFS221" blob "$FXW/$c.yml" 2>&1|sed -n 's/^RESULT=//p'|tail -1)"
  $PY "$WFS" blob "$FXW/$c.yml" 2>&1 | grep -E '^WF-(D[123]|J1|T1)' | sed 's/^/    /'
done
sub "7-파서 버전 위조 — 가짜 yq 를 PATH 에 두고 --version 을 다른 메이저로 만든다"
FAKE="$FX/fakeyq"; mkdir -p "$FAKE"
printf '#!/bin/sh\nif [ "$1" = "--version" ]; then echo "yq (https://github.com/mikefarah/yq/) version v3.4.1"; exit 0; fi\nexec %s "$@"\n' "$(command -v yq)" > "$FAKE/yq"
chmod +x "$FAKE/yq"; command -v yq | sed 's/^/  실제 yq = /'
sed 's/^/  | /' "$FAKE/yq"
echo "  \$ WF_YQ=$FAKE/yq wfcanon-v222.py blob pos-canonical.yml   (기대 = UNVERIFIABLE)"
WF_YQ="$FAKE/yq" $PY "$WFS" blob "$FXW/pos-canonical.yml" 2>&1 | sed 's/^/    /'
echo "  \$ (핀 일치 yq) — 기대 = BLOB_OK"
$PY "$WFS" blob "$FXW/pos-canonical.yml" 2>&1 | grep -E '^WF-P0|^RESULT=' | sed 's/^/    /'
sub "7-e2e  파서 위조를 실행기 경로로 (기대 = PREVENTION_UNVERIFIABLE · 전순서 1)"
run "$R3" "file:$S3" "$EX" "WF_YQ=$FAKE/yq " | tail -30

########################################################################
sec "11. [항목 8] 값 핀 3종 — permissions · runs-on · checkout with"
printf '  %-24s %-22s %-22s %s\n' id "v2.22" "v2.21(대조군)" 설명
while IFS='|' read -r cid exp desc; do
  case "$cid" in f4-*|ctrl-runs-on-2404|pos-canonical)
    printf '  %-24s %-22s %-22s %s\n' "$cid" \
      "$($PY "$WFS" blob "$FXW/$cid.yml" 2>&1|sed -n 's/^RESULT=//p'|tail -1)" \
      "$($PY "$WFS221" blob "$FXW/$cid.yml" 2>&1|sed -n 's/^RESULT=//p'|tail -1)" "$desc" ;;
  esac
done < "$FXW/INDEX.txt"
sub "8-전문  f4-persistcred-true · f4-fetchdepth-false (음극성 bool·int 등가 배제)"
for c in f4-persistcred-true f4-fetchdepth-false; do
  echo "== $c =="; sed -n '5,9p' "$FXW/$c.yml" | sed 's/^/  | /'
  $PY "$WFS" blob "$FXW/$c.yml" 2>&1 | grep -E '^WF-S2|^WF-C5 위배|^RESULT=' | sed 's/^/    /'
done
sub "8-e2e  f4-perms-absent 를 실행기로 (v2.21 = ACTIVE / v2.22 = 차단)"
R5="$FX/perms"; mk "$R5"; art "$R5" "$OR" main >/dev/null; W5=$(wfc "$R5" f4-perms-absent); D5=$(d0a "$R5")
S7="$SEAM/perms"; seam_ruleset "$S7" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z
rev_seam "$S7" "$D5" "$W5" 777001 "$TLAND" f4-perms-absent ok; seam_target "$S7" f4-perms-absent
echo ">>> v2.21"; run "$R5" "file:$S7" "$EX221" | grep -aE '^  \| WF-C6|^U17-fire|^prevention_control_state=|^reason=|^u17_rc='
echo ">>> v2.22"; run "$R5" "file:$S7" "$EX"    | grep -aE '^  \| WF-T2|^  \| WF-C5 위배|^U17-BT \(b-blob\)|^U17-fire|^prevention_control_state=|^reason=|^u17_rc='

########################################################################
sec "12. [항목 9] 동명 decoy 3케이스 — **잔여**로 실증한다 (닫혔다고 적지 않는다)"
R6="$FX/decoy"; mk "$R6"; art "$R6" "$OR" main >/dev/null; W6=$(wfc "$R6" pos-canonical); D6=$(d0a "$R6")
decoy_seam(){ # decoy_seam <dir> <case:1|2|3>
  local d="$1" c="$2" cr=""
  seam_ruleset "$d" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z
  inject "$d" "repos/$OR/commits/$D6/pulls" 200 "[{\"number\":9999,\"state\":\"closed\",\"merged_at\":\"$TLAND\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$W6\"}}]"
  inject "$d" "repos/$OR/check-suites/777001" 200 "{\"id\":777001,\"head_sha\":\"$W6\",\"app\":{\"id\":15368}}"
  case "$c" in
    1) cr="$(crun tos-gate success 15368 "$W6" 777001 555555)" ;;                                     # evil 단독
    2) cr="$(crun tos-gate success 15368 "$W6" 777001 424242),$(crun tos-gate success 15368 "$W6" 777001 555555)" ;;
    3) cr="$(crun tos-gate failure 15368 "$W6" 777001 424242),$(crun tos-gate success 15368 "$W6" 777001 555555)" ;;
  esac
  inject "$d" "repos/$OR/commits/$W6/check-runs" 200 "{\"total_count\":9,\"check_runs\":[$cr]}"
  wfrun "$d" 555555 "$EVILWF" "$W6" 777001                                                            # decoy = 다른 path
  [ "$c" = 1 ] || wfrun "$d" 424242 "$WF" "$W6" 777001 "$( [ "$c" = 3 ] && echo failure || echo success )"
  # 같은 suite 에 두 run 이 산다 (실 GitHub: 한 커밋의 Actions run 들이 한 suite 를 공유)
  if [ "$c" = 1 ]; then
    inject "$d" "repos/$OR/actions/runs?check_suite_id=777001" 200 "{\"total_count\":1,\"workflow_runs\":[{\"id\":555555,\"path\":\"$EVILWF\",\"head_sha\":\"$W6\",\"check_suite_id\":777001,\"conclusion\":\"success\"}]}"
  else
    inject "$d" "repos/$OR/actions/runs?check_suite_id=777001" 200 "{\"total_count\":2,\"workflow_runs\":[{\"id\":424242,\"path\":\"$WF\",\"head_sha\":\"$W6\",\"check_suite_id\":777001,\"conclusion\":\"$( [ "$c" = 3 ] && echo failure || echo success )\"},{\"id\":555555,\"path\":\"$EVILWF\",\"head_sha\":\"$W6\",\"check_suite_id\":777001,\"conclusion\":\"success\"}]}"
  fi
  inj_wf_at "$d" pos-canonical "$W6"
  inject "$d" "repos/$OR/actions/runs/424242/jobs" 200 "$(jobs_json "$( [ "$c" = 3 ] && echo jobfail || echo ok )" "$W6")"
  inject "$d" "repos/$OR/actions/runs/555555/jobs" 200 "$(jobs_json ok "$W6")"
  seam_target "$d" pos-canonical; }
for c in 1 2 3; do
  case $c in
    1) T="① evil 단독 — 정본 path check-run 부재 ⇒ **red**" ;;
    2) T="② 정본 + decoy 둘 다 success ⇒ **red 가 아니다 = 잔여**" ;;
    3) T="③ 정본 fail + decoy success ⇒ **red**" ;;
  esac
  sub "9-$c  $T"
  SD="$SEAM/decoy$c"; rm -rf "$SD"; decoy_seam "$SD" "$c"
  echo ">>> v2.22"; run "$R6" "file:$SD" "$EX" | grep -aE '^U17-B2e|^  \| check-run #|^U17-BT \(b-blob\)|^U17-fire|^prevention_control_state=|^reason=|^u17_rc='
  echo ">>> v2.21 (대조군)"; run "$R6" "file:$SD" "$EX221" | grep -aE '^U17-fire|^prevention_control_state=|^reason=|^u17_rc='
done
echo
echo "  **잔여 등재(닫지 못한다)**: 케이스 ② 는 v2.22 에서도 통과다 — (a) 예방 층은 이름·app_id 만 보고"
echo "  blob 을 읽지 않으며, (b) path-aware 열거도 «정본 path 가 success» 면 통과시킨다.  «닫혔다»가 아니다."

########################################################################
sec "12-c. [G5] **과잉 차단** 실증 — 정직한 «on: [pull_request, push]» 이 (b)② «정확히 1» 과 충돌한다"
echo "  계약은 workflow run 의 «event» 를 어디에도 핀하지 않는다 — run 정체성은 «path»(:5554)·«head_sha»(:5556) 뿐이다."
echo "  그런데 «on: [pull_request, push]»(:5655 가 «허용»)이면 같은 head_sha 에 **같은 path 의 run 이 둘**"
echo "  (push 트리거 · pull_request 트리거) 생기고, 각각 «tos-gate» check-run 을 낸다."
echo "  ⇒ (b)② 의 «정본 path check-run 이 정확히 1개» 가 **정직한 구성**을 red 로 만든다."
R7g="$FX/onboth"; mk "$R7g"; art "$R7g" "$OR" main >/dev/null; W7g=$(wfc "$R7g" ctrl-on-push); D7g=$(d0a "$R7g")
S7g="$SEAM/onboth"; seam_ruleset "$S7g" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z
inject "$S7g" "repos/$OR/commits/$D7g/pulls" 200 "[{\"number\":9999,\"state\":\"closed\",\"merged_at\":\"$TLAND\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$W7g\"}}]"
# 같은 head_sha · 같은 path · 다른 event → 다른 run/suite (실 GitHub 거동)
inject "$S7g" "repos/$OR/commits/$W7g/check-runs" 200 "{\"total_count\":2,\"check_runs\":[$(crun tos-gate success 15368 "$W7g" 777001 424242),$(crun tos-gate success 15368 "$W7g" 777002 424243)]}"
inject "$S7g" "repos/$OR/check-suites/777001" 200 "{\"id\":777001,\"head_sha\":\"$W7g\",\"app\":{\"id\":15368}}"
inject "$S7g" "repos/$OR/check-suites/777002" 200 "{\"id\":777002,\"head_sha\":\"$W7g\",\"app\":{\"id\":15368}}"
inject "$S7g" "repos/$OR/actions/runs/424242" 200 "{\"id\":424242,\"path\":\"$WF\",\"head_sha\":\"$W7g\",\"event\":\"pull_request\",\"check_suite_id\":777001,\"conclusion\":\"success\"}"
inject "$S7g" "repos/$OR/actions/runs/424243" 200 "{\"id\":424243,\"path\":\"$WF\",\"head_sha\":\"$W7g\",\"event\":\"push\",\"check_suite_id\":777002,\"conclusion\":\"success\"}"
inject "$S7g" "repos/$OR/actions/runs/424242/jobs" 200 "$(jobs_json ok "$W7g")"
inject "$S7g" "repos/$OR/actions/runs/424243/jobs" 200 "$(jobs_json ok "$W7g")"
# [대조군 공정성] v2.21 실행기는 `actions/runs?check_suite_id=` 를 쓴다 — 그 엔드포인트도 주입해야
#   v2.21 이 «엔드포인트 부재(ERR)» 가 아니라 «자기 술어» 로 판정한다
inject "$S7g" "repos/$OR/actions/runs?check_suite_id=777001" 200 "{\"total_count\":1,\"workflow_runs\":[{\"id\":424242,\"path\":\"$WF\",\"head_sha\":\"$W7g\",\"event\":\"pull_request\",\"check_suite_id\":777001,\"conclusion\":\"success\"}]}"
inject "$S7g" "repos/$OR/actions/runs?check_suite_id=777002" 200 "{\"total_count\":1,\"workflow_runs\":[{\"id\":424243,\"path\":\"$WF\",\"head_sha\":\"$W7g\",\"event\":\"push\",\"check_suite_id\":777002,\"conclusion\":\"success\"}]}"
inj_wf_at "$S7g" ctrl-on-push "$W7g"; seam_target "$S7g" ctrl-on-push
echo "  blob 층 판정(정직한 워크플로여야 한다): $($PY "$WFS" blob "$FXW/ctrl-on-push.yml" 2>&1|sed -n 's/^RESULT=//p'|tail -1)"
echo ">>> v2.22 (실측 — 과잉 차단이면 UNVERIFIED_REVISION)"
run "$R7g" "file:$S7g" "$EX" | grep -aE '^U17-B2e|^  \| check-run #|^U17-fire|^prevention_control_state=|^reason=|^u17_rc='
echo ">>> v2.21 (대조군 — 첫 후보에서 break 하므로 통과 기대)"
run "$R7g" "file:$S7g" "$EX221" | grep -aE '^U17-fire|^prevention_control_state=|^u17_rc='
echo "  ⇒ **이것은 fail-open 이 아니라 fail-closed 방향의 과잉 차단**이지만, F#4 가 닫으려던"
echo "     «두 소비자가 같은 blob 에 다른 결론» 클래스가 v2.22 «신규» 술어 안에서 재발한 자리다(에라타 후보 EC-7)"

########################################################################
sec "12-d. [G4] 순환 alias — 계약이 «미종료» 에 상태값을 배정하지 않았다"
echo "-- (1) compose 가 순환 «노드 그래프» 를 만드는가 (객체 identity) --"
$PY - <<'PYX'
import yaml
for f in ("fx/g4-cycle-self.yml","fx/g4-cycle-branch.yml","fx/g4-cycle-in-job.yml"):
    n=yaml.compose(open(f).read()); found=[]
    def scan(x, anc, path, d=0):
        if d>40: return
        if id(x) in anc: found.append(path); return
        if isinstance(x, yaml.MappingNode):
            for k,v in x.value: scan(v, anc|{id(x)}, "%s.%s"%(path,k.value), d+1)
        elif isinstance(x, yaml.SequenceNode):
            for i,v in enumerate(x.value): scan(v, anc|{id(x)}, "%s[%d]"%(path,i), d+1)
    scan(n, frozenset(), "$")
    print("  %-26s 자기 조상을 다시 가리키는 노드 = %d건 %s" % (f.split('/')[-1], len(found), found[:3]))
PYX
echo "-- (2) 방문집합 «없는» 순회(깊이 상한 64 만) 가 종료하는가 — 워치독 12초 --"
$PY - <<'PYX'
import signal, time, yaml
class TO(Exception): pass
signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TO()))
def naive(n, d=0, cap=64):                      # ← 수정 «전» 의 walk (깊이 상한만)
    if d > cap: return "<cap>"
    if isinstance(n, yaml.MappingNode): return [[k.value, naive(v,d+1,cap)] for k,v in n.value]
    if isinstance(n, yaml.SequenceNode): return [naive(v,d+1,cap) for v in n.value]
    return None
for f in ("fx/g4-cycle-self.yml","fx/g4-cycle-branch.yml"):
    node=yaml.compose(open(f).read()); t=time.time(); signal.alarm(12)
    try:
        r=naive(node); signal.alarm(0)
        print("  %-26s 종료 %.3fs · 결과 크기=%d" % (f.split('/')[-1], time.time()-t, len(repr(r))))
    except TO: print("  %-26s **12초 미종료 — 판정 자체가 없다(fail-closed 도 아니다)**" % f.split('/')[-1])
    except MemoryError: signal.alarm(0); print("  %-26s **MemoryError**" % f.split('/')[-1])
PYX
echo "-- (3) 방문집합 «있는» 현행 술어 (기대: 전건 종료 + UNVERIFIED_REVISION) --"
for c in g4-cycle-self g4-cycle-branch g4-cycle-in-job; do
  printf '  %-26s → %s\n' "$c" "$($PY "$WFS" blob "$FXW/$c.yml" 2>&1|sed -n 's/^RESULT=//p'|tail -1)"
done
$PY "$WFS" blob "$FXW/g4-cycle-in-job.yml" 2>&1 | grep -E '^WF-D2c' | sed 's/^/      /'
echo "-- (4) 판정 파서 yq 자신은 순환에 무엇을 하는가 (워치독 10초) --"
for c in g4-cycle-self g4-cycle-branch g4-cycle-in-job; do
  ( yq -o=json . "$FXW/$c.yml" > "$FX/$c.yqout" 2>&1; echo $? > "$FX/$c.yqrc" ) & P=$!
  ( sleep 10; kill -9 $P 2>/dev/null ) 2>/dev/null & Wd=$!; wait $P 2>/dev/null; kill $Wd 2>/dev/null; wait $Wd 2>/dev/null
  printf '  %-26s rc=%-3s %s\n' "$c" "$(cat "$FX/$c.yqrc" 2>/dev/null||echo KILL)" "$(head -c 130 "$FX/$c.yqout"|tr '\n' ' ')"
done
echo "-- (5) v2.21 술어 대조군 (워치독 15초) --"
$PY - <<'PYX'
import subprocess, sys, time
for c in ("g4-cycle-self","g4-cycle-branch","g4-cycle-in-job"):
    t=time.time()
    try:
        r=subprocess.run([sys.executable,"wfcanon-v221.py","blob","fx/%s.yml"%c],capture_output=True,text=True,timeout=15)
        out=[l for l in r.stdout.split("\n") if l.startswith("RESULT=")]
        if out: print("  %-26s %.2fs → %s" % (c, time.time()-t, out[-1]))
        else:
            err=[l for l in r.stderr.strip().split("\n") if l][-1] if r.stderr.strip() else ""
            print("  %-26s %.2fs → **RESULT 라인 부재 · rc=%d** (%s)" % (c, time.time()-t, r.returncode, err))
    except subprocess.TimeoutExpired: print("  %-26s **15초 미종료**" % c)
PYX
echo "  ⇒ v2.21 은 «g4-cycle-in-job» 에서 **판정을 내지 못하고 죽는다**(yq 가 순환을 «조용히 절단»해"
echo "     «steps» 가 시퀀스가 아닌 매핑이 되고 v2.21 이 그것을 리스트로 순회한다)."
echo "     실행기의 «case *)» 가 빈 WFRES 를 red 로 접으므로 **결과적으로는 fail-closed 지만 설계가 아니라 우연**이다."

########################################################################
sec "12-b. 역방향 fail-open 사냥 — 신규 술어 뮤테이션 (자기신고 금지 · 판정 뒤집힘으로 본다)"
$PY "$SP/mut-v222.py"
sub "12-b 벨트 판별 — «불변» 항이 죽은 코드인가 벨트인가 (실측으로 귀속한다)"
echo "  M1  (C-1 중복)         → 불변.  벨트 = 두 파서 «.value» 키 트리(yq last-wins 붕괴 vs compose 보존).  M1b 이중 무력화에서 BLOB_OK 로 뒤집힘 ⇒ 죽은 코드 아님"
echo "  M2  («<<» 금지)        → 불변.  벨트 = 키 트리 + **최상위 allowlist**(anchor 소스 «x-base» 가 allowlist 밖).  실측 발화 지점:"
$PY "$SP/mut/M2b-merge+belt.py" blob "$FXW/m2-merge-key.yml" 2>&1 | grep -E '^WF-T1|^WF-C5 위배|^RESULT=' | sed 's/^/      /'
echo "       M2c 삼중 무력화에서 BLOB_OK ⇒ 죽은 코드 아님.  **단독 부담 픽스처는 만들지 못했다** —"
echo "       워크플로에서 «<<» 는 anchor 소스를 필요로 하고 그 관용 위치(최상위 x-* 키)가 allowlist 밖이기 때문이다(정직 기록)"
echo "  M3  (키 트리 벨트)      → 불변.  **구성상 벨트다** — 알려진 발산 원천이 중복 키와 «<<» 둘뿐이고 그 둘은 이미 차단된다."
echo "                          M1b(벨트 무력화 시 중복이 통과)가 이 검사가 살아 있음을 뒤집힘으로 보인다"
echo "  M6  (permissions 존재) → 실측 «<none>» = 뮤테이션 산출물의 KeyError 크래시(첫 분기만 끄면 둘째 분기가 doc[\"permissions\"] 를 읽는다)."
echo "                          **술어의 결함이 아니라 뮤테이션 설계 오류**다 — M6c 이중 무력화가 BLOB_OK 로 뒤집혀 검사가 살아 있음을 보인다"
echo "  M8  (jobs 개수)        → 불변.  벨트 = 잡 «name» 값-핀(그 픽스처의 게이트 잡 표시 이름이 비정본).  M8b 단독 픽스처에서 뒤집힘"
echo "  M15 (continue-on-error) → 불변.  벨트 = run 스텝 허용 키 닫힌 집합.  M15b 이중 무력화에서 뒤집힘"
echo "  ⇒ **죽은 검사 0 · 신규 fail-open 0**.  «불변» 7건은 전부 중복 방어(벨트) 또는 뮤테이션 산출물이며 그 귀속을 실행으로 보였다"

sec "13. 회귀 — v2.21 증거가 이미 세운 축이 v2.22 에서도 그대로인가"
sub "R-1 ⑭ 서버 변형 (부재·실패·잡실패 · skipped/neutral/cancelled/null)"
printf '  %-11s %-24s %-24s\n' variant v2.22 v2.21
for v in ok noverify verifyfail norun jobfail skipped neutral cancelled nullconc dupname; do
  jobs_json "$v" deadbeef > "$JD/$v.json"
  printf '  %-11s %-24s %-24s\n' "$v" \
    "$($PY "$WFS" server "$JD/$v.json" 2>&1|sed -n 's/^RESULT=//p'|tail -1)" \
    "$($PY "$WFS221" server "$JD/$v.json" 2>&1|sed -n 's/^RESULT=//p'|tail -1)"
done
sub "R-2 ⑪-(a) 연속성 정상 ⇒ ACTIVE / ⑪-(b) updated_at > t_land ⇒ CONTINUITY_UNVERIFIABLE"
RC="$FX/cont"; mk "$RC"; art "$RC" "$OR" main >/dev/null; WC=$(wfc "$RC" pos-canonical); DC=$(d0a "$RC")
SA="$SEAM/11a"; seam_ruleset "$SA" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$SA" "$DC" "$WC" 777001 "$TLAND"; seam_target "$SA" pos-canonical
run "$RC" "file:$SA" "$EX" | tail -8
SB="$SEAM/11b"; seam_ruleset "$SB" 42 2026-08-01T00:00:00Z 2026-08-11T09:00:00Z; rev_seam "$SB" "$DC" "$WC" 777001 "$TLAND"; seam_target "$SB" pos-canonical
run "$RC" "file:$SB" "$EX" | tail -6
sub "R-3 ⑨ 착수 «후» 아티팩트 편집 ⇒ ARTIFACT_MUTATED"
R9="$FX/mutated"; mk "$R9"; art "$R9" "$OR" main >/dev/null; W9=$(wfc "$R9" pos-canonical); D9=$(d0a "$R9")
printf 'owner_repo: %s\ntarget_branch: main\noperator_countersign: "operator 2026-08-20T00:00:00Z"   # SIMULATED (edited AFTER d)\n' "$OR" > "$R9/$PC"
git -C "$R9" add -A; git -C "$R9" commit -q -m "P_edit: artifact edited after D0-A start (SIMULATED)"
S8="$SEAM/mut"; seam_ruleset "$S8" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S8" "$D9" "$W9" 777001 "$TLAND"; seam_target "$S8" pos-canonical
run "$R9" "file:$S8" "$EX" | tail -6
sub "R-4 ⑤⑩⑫ live (GET-only) — 선언 target 불일치 · 타 원격 · GH_HOST override 불변"
RH="$FX/host"; mk "$RH"; art "$RH" "$OR" main >/dev/null
echo ">>> ⑫-a live 기본"; run "$RH" gh "$EX" | grep -aE '^U17-0 |^U17-H |^U17-BT |^prevention_control_state=|^reason='
echo ">>> ⑫-b live GH_HOST=example.invalid override (상태값 «불변» 기대)"
run "$RH" gh "$EX" "GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy " | grep -aE '^U17-0 |^U17-H |^U17-BT |^prevention_control_state=|^reason='
R5a="$FX/decl-wb"; mk "$R5a"; art "$R5a" "$OR" "$WB" >/dev/null
echo ">>> ⑤-a live 선언 target=작업 브랜치"; run "$R5a" gh "$EX" | grep -aE '^prevention_control_state=|^reason='
R7="$FX/rem-gitlab"; mk "$R7" https://gitlab.com/kakao-harris-lee/kis_unified_sts.git; art "$R7" "$OR" main >/dev/null
echo ">>> ⑩-a live 타 host 원격"; run "$R7" gh "$EX" | grep -aE '^prevention_control_state=|^reason='

########################################################################
sec "14. 본 저장소 live 실측 (GET · 실행기 1회) — 오늘의 main 은 무엇인가"
for p in "$PC" "$WF" tools/tos_entry_harness.sh config/tos_completion.yaml; do
  printf '  %-62s %s\n' "$p" "$( [ -e "$REPO/$p" ] && echo "실재(sha256 $(shasum -a 256 "$REPO/$p"|cut -c1-16)…)" || echo "부재" )"; done
U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO" 2>&1 | grep -aE '^U17-0 |^U17-A1 |^U17-BT|^U17-fire|^prevention_control_state=|^reason='
echo "  (실행기 rc 는 위 상태값이 결정한다 — ACTIVE 만 0)"
```
---

## 부기 — 이 증거가 «하지 않은» 것

- **계약 두 문서를 편집하지 않았다.**  발견한 문언 문제는 §14 에 모았을 뿐이다.
- **커밋하지 않았다.**
- **GitHub 에 write API 를 호출하지 않았다.**  `gh api` GET 만 썼고, live 로 불가능한 구성
  (보호 설정 변경·check-run 게시·타 host 응답)은 전부 `responder=file:` seam 이며 `SIMULATED` 다.
- **«해소» 를 주장하지 않는다.**  네 처분(#1/F#1 · #2/M-7 · F#2 · F#4)과 C-1·M-4·M-2·M-1·M-3 에 대해
  **요구된 술어를 구현해 돌린 결과**를 적었을 뿐이고, 판정은 레인 B 재심의 소관이다.
- **잔여를 «닫혔다»고 적지 않았다.**  §13-E 가 그 목록이며, 특히 동명 decoy 케이스 ② 는
  §12 에서 `PREVENTION_ACTIVE` 로 «잔여임을 실행으로» 남겼다.
