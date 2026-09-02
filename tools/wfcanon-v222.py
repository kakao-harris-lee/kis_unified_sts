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
SHA      = "059e13f22397d53c53211895cc321fef81ab7925135b196e27315e813d723177"
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
