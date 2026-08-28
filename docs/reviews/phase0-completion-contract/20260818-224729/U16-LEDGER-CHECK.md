# U16-LEDGER-CHECK — v2.14 T-82 ⑮·⑰ⓐⓑⓒ·⑱ + (iii)(v)(H5-②) 손 실행 기록

> **비규범 손 실행 — 실제 소비자(`tools/tos_completion_status.py --check`)는 D0-A 이후이며, 이 파일은
> 계약(v2.14 `db19a0e8`)이 경로·형식을 규정하지 않은 부속이다.** U-16/§12.3.4-T/§8 T-82 행 어디에도
> 증거 아티팩트 경로가 없음을 grep 으로 확인(0건)한 뒤, 같은 스탬프 디렉터리에 sibling 으로 두었다.
> 픽스처는 전부 scratchpad 하위 **독립 git 저장소**(본 저장소와 무관·무접촉)다.
- **생성 시각**: 2026-08-18T15:05:27Z (UTC) · **생성 주체**: 오케스트레이터 지시 하의 실행 에이전트
- **관련 계약**: U-16-g (g6) 구조 정의 `C_R(c)` + 존재 양화 증인(:6173-6199, [H4]) · 원장 tombstone-graph
  (`row_ref`·`supersedes`·`LEDGER_EFF`·MALFORMED 4조건·[H5-①②], :6062-6111) · §8 T-82 행 ⑮⑰⑱ (18종)
- **결과 요약 — 실행기 stdout·rc 원문 그대로**:

| 변이 | 픽스처 (DAG 는 본문) | 방출값 | rc | 기대 | 대조 |
| --- | --- | --- | --- | --- | --- |
| ⑰ⓐ 기존-경로 `B∥A` | H0(경로 有·digest 無) → B(digest 삽입) ∥ A(approved_at_head=B) → M | `C_R={B}` · `g6_verdict=APPROVAL_ORDER_INVALID` | 1 | red | **일치** |
| ⑰ⓑ 머지 해소 도입 | B(무-digest 편집) ∥ A → M 에서 digest 도입 | `C_R={M}` · `APPROVAL_ORDER_INVALID` | 1 | red (초안 pickaxe 는 ∅ 공허참) | **일치** |
| ⑰ⓒ 양성 | B1·B2 독립 삽입, A ⊐ B1 | `C_R={B1,B2}` · `g6_verdict=OK` (증인 B1) | 0 | green | **일치** |
| ⑮ 회귀 (v2.13 `R∥A`) | 신규 아티팩트 R ∥ A → M | `C_R={R}` · `APPROVAL_ORDER_INVALID` | 1 | red | **일치** |
| ⑱ 병렬 seq=1 충돌 | X1(seq1) ∥ Y1(seq1) → M | `LEDGER_EFF={X1,Y1}` · `APPROVAL_MALFORMED`(키 중복) | 1 | MALFORMED | **일치** |
| ⑱ 복구 | Z1(seq1, supersedes row_ref(X1))·Z2(seq2, supersedes row_ref(Y1)) append | `LEDGER_EFF={Z1,Z2}` · `NO_ROWS_CLEAR` · 구 행 X1·Y1 잔존·g5 동일 | 0 | green·구 행 잔존 | **일치** |
| (v) 경쟁 재부여 | Za ∥ Zb (둘 다 supersedes X1, 별개 커밋) → M2 | `LEDGER_EFF={Z2,Za,Zb}` · `APPROVAL_MALFORMED`(키 중복) | 1 | MALFORMED | **일치** |
| (v) 재-supersede 복구 | Zc(seq1, supersedes [Za, Zb]) append | `LEDGER_EFF={Z2,Zc}` · `NO_ROWS_CLEAR` | 0 | green | **일치** |
| (iii) 순환 시도 (모델) | A 를 편집해 B 지목 → A 의 row_digest 변경 → B 의 지목 대상 부재 | `APPROVAL_MALFORMED`(부재 행 지목 [G5-(ii)]) | 1 | 순환 구성 불가 → 부재 지목 MALFORMED | **일치** |
| H5-② (모델, 보너스) | 같은 c_APP 안 동일 row_digest 행 둘 | `APPROVAL_MALFORMED`(row_ref 비단사) | 1 | MALFORMED | **일치** |

---

## 1. g6 실행기 `cr-exec.sh` — 원문 (sha256 `f44e57cca3eb16efeeccf5302d577eb9aa8ac1d9108be09346df33a7e3975cdc`)

구조 정의 `C_R(c)` 를 `git rev-list c` 전수 순회로 파생(플래그·pickaxe 미사용): x 에 digest 있고 모든 부모에
없음(부모에 경로 부재 = ∉ [H4]) → 원소. 요구 = ∃ x ∈ C_R : x ⊰ c_APP. `C_R=∅` 은 `PROVENANCE_UNVERIFIABLE`(면제 없음).
방출 `g6_verdict=` · OK 만 exit 0 · trap EXIT.

```bash
#!/usr/bin/env bash
# g6 «손 실행기» — v2.14 U-16-g (g6) 구조 정의 C_R(c) + 존재 양화 증인 (계약 db19a0e8 :6173-6199)
#   C_R(c) = { x ⊑ c : digest ∈ blob(x:ref) ∧ ∀p∈parents(x): digest ∉ blob(p:ref) }   (부모에 경로 부재 = ∉ 로 읽음 [H4])
#   요구: ∃ x ∈ C_R(c) : x 가 c_APP 의 진 조상.  위반 → APPROVAL_ORDER_INVALID · C_R=∅ → PROVENANCE_UNVERIFIABLE(면제 없음)
# 산출: stdout 에 g6_verdict=<값> 한 줄 (프로그램 산출).  exit 0 = OK, 그 외 비-0.  플래그·pickaxe 미사용.
# 사용: bash cr-exec.sh <repo> <digest> <reviewer_ref> <c(전이 커밋)> <c_APP>
set -u -o pipefail
EMITTED=0
emit() { EMITTED=1; printf 'g6_verdict=%s\nreason=%s\n' "$1" "$2"; [ "$1" = OK ] && exit 0; exit 1; }
trap '[ "$EMITTED" -eq 1 ] || { printf "g6_verdict=%s\nreason=%s\n" PROVENANCE_UNVERIFIABLE "판정 미산출 상태로 종료"; exit 1; }' EXIT
cd "${1:?repo}" || emit PROVENANCE_UNVERIFIABLE "repo 진입 실패"
DIG="${2:?digest}"; REF="${3:?reviewer_ref}"; C="${4:?c}"; CAPP="${5:?c_APP}"
has() { git cat-file -e "$1:$REF" 2>/dev/null && git show "$1:$REF" 2>/dev/null | grep -qF -- "$DIG"; }
CR=""
for x in $(git rev-list "$C" 2>/dev/null); do
  has "$x" || continue
  intro=1
  for p in $(git log --format=%P -1 "$x"); do has "$p" && { intro=0; break; }; done
  [ "$intro" = 1 ] && CR="$CR $x"
done
printf 'C_R(c=%s) = {%s }\n' "$(git rev-parse --short "$C")" "$(for x in $CR; do printf ' %s' "$(git rev-parse --short "$x")"; done)"
[ -n "$CR" ] || emit PROVENANCE_UNVERIFIABLE "C_R = ∅ (면제하지 않는다)"
for x in $CR; do
  if git merge-base --is-ancestor "$x" "$CAPP" && [ "$x" != "$(git rev-parse "$CAPP")" ]; then
    emit OK "증인 $(git rev-parse --short "$x") ⊰ c_APP=$(git rev-parse --short "$CAPP")"
  fi
done
emit APPROVAL_ORDER_INVALID "C_R 원소 중 c_APP=$(git rev-parse --short "$CAPP") 의 진 조상 없음"
```

## 2. 원장 실행기 `ledger-exec.py` — 원문 (sha256 `be1901eb0434eabd5fc9f11d682bb62782d2ee6e72ed5feb64ff2e7ada63b475`)

`row_ref=(c_APP, row_digest)`(digest 는 U-16-f 방식 정규형·`supersedes` 포함 [H5-①]) · c_APP 는 git 모드에서
행 라인의 **도입 지점**을 구조 정의로 파생(pickaxe 아님) · `LEDGER_EFF` = 지목되지 않은 행 · MALFORMED 4조건
+ [H5-②] · 결번 → `APPROVAL_MISSING` · 방출 `closable_no_provenance_state=` · `NO_ROWS_CLEAR` 만 exit 0.

```python
#!/usr/bin/env python3
"""U-16 원장 «손 실행기» — v2.14 tombstone-graph (계약 db19a0e8 :6062-6111).
row_ref = (c_APP, row_digest) · supersedes 는 행(row_ref)을 지목 · LEDGER_EFF = 어떤 supersedes 에도 지목되지 않은 행
MALFORMED: EFF 내 (row_id,edge_seq) 중복 · 부재 행 지목 [G5-(ii)] · 순환 [G5-(iii)] · 신 행이 구 행보다 먼저 도입
결번 → APPROVAL_MISSING · 그 외 → NO_ROWS_CLEAR.  stdout: closable_no_provenance_state=<값> (프로그램 산출) · rc 0 = NO_ROWS_CLEAR 만.
모드:  git  <repo> <ledger-path> <edges>          — 원장 파일 행의 c_APP 를 구조 정의(도입 지점: 행 ∈ blob(x) ∧ ∀p ∉ blob(p))로 파생
       refs <repo> <ledger-path>                  — 각 행의 row_ref 출력 (픽스처 저작용)
       model <json-file> <edges>                  — 행·c_APP·순서를 명시한 모델 (git 없이)
행 형식(원장 파일): name|row_id|edge_seq|transition|digest|supersedes   supersedes = 'capp:rowdigest;capp:rowdigest' 또는 빈칸
"""
import hashlib, json, subprocess, sys

FIELDS = ("row_id", "edge_seq", "transition", "digest", "supersedes")   # 정규형 대상 (name 은 표시용 — 계약 열 아님)

def canon_digest(row):   # U-16-f 방식: LC_ALL=C 열이름 정렬 · <열>=<값> NUL 결합 · sha256
    return hashlib.sha256(b"\0".join(f"{k}={row[k]}".encode() for k in sorted(FIELDS))).hexdigest()

def parse_line(line):
    name, row_id, seq, tr, dg, sup = (line.rstrip("\n").split("|") + [""] * 6)[:6]
    sups = [tuple(s.split(":", 1)) for s in sup.split(";") if s]
    return {"name": name, "row_id": row_id, "edge_seq": int(seq), "transition": tr, "digest": dg,
            "supersedes": sup, "_sups": sups, "_line": line.rstrip("\n")}

def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True).stdout

def blob_has(repo, commit, path, line):
    r = subprocess.run(["git", "-C", repo, "show", f"{commit}:{path}"], capture_output=True, text=True)
    return r.returncode == 0 and line in r.stdout.splitlines()

def c_app_structural(repo, path, line):   # 도입 지점(들) — 최초 도입 커밋. 복수면 사전순 최소(픽스처는 단일)
    out = []
    for x in git(repo, "rev-list", "HEAD").split():
        if not blob_has(repo, x, path, line): continue
        parents = git(repo, "log", "--format=%P", "-1", x).split()
        if all(not blob_has(repo, p, path, line) for p in parents): out.append(x)
    return sorted(out)[0] if out else None

def is_strict_ancestor(repo, a, b):
    if a == b: return False
    return subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", a, b]).returncode == 0

def evaluate(rows, edges, ancestor):   # rows: dicts with c_APP · ancestor(a,b) → a ⊰ b
    for r in rows: r["_ref"] = (r["c_APP"], canon_digest(r))
    # [H5-②] 같은 c_APP 안에 row_digest 가 같은 행이 둘 = MALFORMED (row_ref 비단사 → 지목 대상 미결정)
    seen = {}
    for r in rows: seen.setdefault(r["_ref"], []).append(r["name"])
    noninj = {k: v for k, v in seen.items() if len(v) > 1}
    if noninj:
        print(f"closable_no_provenance_state=APPROVAL_MALFORMED\nreason=같은 c_APP 안 동일 row_digest 행 둘 이상 [H5-②] row_ref 비단사: {noninj}"); sys.exit(1)
    refs = {r["_ref"]: r for r in rows}
    targeted, absent, order_bad = set(), [], []
    for r in rows:
        for t in r["_sups"]:
            full = next((k for k in refs if k[0].startswith(t[0]) and k[1].startswith(t[1])), None)
            if full is None: absent.append((r["name"], t)); continue
            targeted.add(full)
            if not ancestor(refs[full]["c_APP"], r["c_APP"]): order_bad.append((r["name"], refs[full]["name"]))
    # 순환: supersede 그래프 DFS
    graph = {}
    for r in rows:
        for t in r["_sups"]:
            full = next((k for k in refs if k[0].startswith(t[0]) and k[1].startswith(t[1])), None)
            if full: graph.setdefault(r["_ref"], []).append(full)
    def cyclic():
        seen, stack = set(), set()
        def dfs(n):
            if n in stack: return True
            if n in seen: return False
            seen.add(n); stack.add(n)
            if any(dfs(m) for m in graph.get(n, [])): return True
            stack.discard(n); return False
        return any(dfs(n) for n in list(graph))
    eff = [r for r in rows if r["_ref"] not in targeted]
    tomb = [r["name"] for r in rows if r["_ref"] in targeted]
    keys = {}
    for r in eff: keys.setdefault((r["row_id"], r["edge_seq"]), []).append(r["name"])
    dup = {k: v for k, v in keys.items() if len(v) > 1}
    gaps = [n for n in range(1, edges + 1) if n not in {r["edge_seq"] for r in eff}]
    print(f"LEDGER_EFF={{{','.join(sorted(r['name'] for r in eff))}}} tombstoned={{{','.join(sorted(tomb)) or '-'}}} rows_present={len(rows)}")
    def emit(state, reason):
        print(f"closable_no_provenance_state={state}\nreason={reason}"); sys.exit(0 if state == "NO_ROWS_CLEAR" else 1)
    if absent:    emit("APPROVAL_MALFORMED", f"supersedes 가 부재 행 지목 [G5-(ii)]: {absent}")
    if cyclic():  emit("APPROVAL_MALFORMED", "supersede 관계 순환 [G5-(iii)]")
    if order_bad: emit("APPROVAL_MALFORMED", f"신 행이 구 행보다 먼저 도입(c_APP 순서 위반): {order_bad}")
    if dup:       emit("APPROVAL_MALFORMED", f"LEDGER_EFF 내 (row_id,edge_seq) 중복: {dup}")
    if gaps:      emit("APPROVAL_MISSING", f"edge_seq 결번 {gaps} (그 간선의 승인 부재)")
    emit("NO_ROWS_CLEAR", f"키 중복 0 · 결번 0 · 구 행 잔존={tomb or 'n/a'}")

def main():
    try:
        mode = sys.argv[1]
        if mode in ("git", "refs"):
            repo, path = sys.argv[2], sys.argv[3]
            rows = [parse_line(l) for l in git(repo, "show", f"HEAD:{path}").splitlines() if l.strip()]
            for r in rows: r["c_APP"] = c_app_structural(repo, path, r["_line"]) or "MISSING"
            if mode == "refs":
                for r in rows: print(f"{r['name']} row_ref=({r['c_APP'][:12]},{canon_digest(r)[:16]})")
                return
            evaluate(rows, int(sys.argv[4]), lambda a, b: is_strict_ancestor(repo, a, b))
        elif mode == "model":
            m = json.load(open(sys.argv[2])); order = m["order"]
            rows = []
            for r in m["rows"]:
                rows.append({**r, "supersedes": ";".join(f"{a}:{b}" for a, b in r.get("sups", [])),
                             "_sups": [tuple(x) for x in r.get("sups", [])]})
            evaluate(rows, int(sys.argv[3]), lambda a, b: order.index(a) < order.index(b))
        else: raise SystemExit("bad mode")
    except SystemExit: raise
    except Exception as e:
        print(f"closable_no_provenance_state=PROVENANCE_UNVERIFIABLE\nreason=판정 미산출: {e!r}"); sys.exit(1)

if __name__ == "__main__": main()
```

## 3. 픽스처 스크립트 원문 — `t82-cr.sh` (sha256 `f2e86d548435a859b31fe1a685aa26ae72d3068f01f3f25ecaf71a0dc0149a3f`) · `t82-ledger.sh` (sha256 `37a7c5b3e1e844751ea2d4859a50f69625f579de597df6cfe557f9a36181731a`)

```bash
#!/usr/bin/env bash
# t82-cr.sh — T-82 ⑮·⑰ⓐⓑⓒ 픽스처(독립 git repo, scratchpad 하위) + g6 실행기. 본 저장소 무접촉.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
CR="$SP/cr-exec.sh"; FX="$SP/fx"; DIG=deadbeefcafe0001; REF=reviews/review.md
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec() { printf '\n########## %s ##########\n' "$*"; }
newrepo() { rm -rf "$1"; git init -q -b main "$1"; }
c()  { git -C "$1" add -A && git -C "$1" commit -q --allow-empty -m "$2" && git -C "$1" rev-parse --short HEAD; }
dag(){ git -C "$1" log --graph --oneline --all; }

# ⑰ⓐ  H0(기존 reviewer 경로, digest 없음) → B(digest 삽입) ∥ A(approved_at_head=B 승인 행) → M(NO 전이) merge
sec "T-82 (17)a existing-path B∥A"
R="$FX/17a"; newrepo "$R"; mkdir -p "$R/reviews"
echo "unrelated review text" > "$R/$REF"; echo "id,closable" > "$R/register.csv"; echo "r1,YES" >> "$R/register.csv"; : > "$R/ledger.csv"; H0=$(c "$R" "H0: base (reviewer path exists, no digest)")
git -C "$R" checkout -q -b b "$H0"; echo "review body $DIG" >> "$R/$REF"; B=$(c "$R" "B: insert digest into existing reviewer path")
git -C "$R" checkout -q -b a "$H0"; echo "r1,1,YES->NO,$DIG,approved_at_head=$B,ref=$REF" >> "$R/ledger.csv"; A=$(c "$R" "A: approval row (approved_at_head=B)")
git -C "$R" merge -q --no-edit b; sed -i '' 's/^r1,YES$/r1,NO/' "$R/register.csv"; M=$(c "$R" "M: merge + NO transition")
dag "$R"; echo "H0=$H0 B=$B A=$A M=$M"
bash "$CR" "$R" "$DIG" "$REF" "$M" "$A"; echo "cr_rc=$?"

# ⑰ⓑ  머지 해소에서 digest 도입 — C_R={M}
sec "T-82 (17)b digest introduced at merge resolution"
R="$FX/17b"; newrepo "$R"; mkdir -p "$R/reviews"
echo "unrelated review text" > "$R/$REF"; echo "id,closable" > "$R/register.csv"; echo "r1,YES" >> "$R/register.csv"; : > "$R/ledger.csv"; H0=$(c "$R" "H0: base")
git -C "$R" checkout -q -b b "$H0"; echo "B-side edit (no digest)" >> "$R/$REF"; B=$(c "$R" "B: reviewer edit without digest")
git -C "$R" checkout -q -b a "$H0"; echo "r1,1,YES->NO,$DIG,approved_at_head=$B,ref=$REF" >> "$R/ledger.csv"; A=$(c "$R" "A: approval row (approved_at_head=B)")
git -C "$R" merge -q --no-commit --no-edit b >/dev/null 2>&1 || true
echo "review body $DIG (introduced in merge resolution)" >> "$R/$REF"; sed -i '' 's/^r1,YES$/r1,NO/' "$R/register.csv"; M=$(c "$R" "M: merge — digest introduced in resolution + NO transition")
dag "$R"; echo "H0=$H0 B=$B A=$A M=$M"
bash "$CR" "$R" "$DIG" "$REF" "$M" "$A"; echo "cr_rc=$?"

# ⑰ⓒ  양성 — B1·B2 가 같은 digest 를 독립 삽입, A ⊐ B1 (증인 존재 → OK)
sec "T-82 (17)c positive — independent B1/B2, A descends from B1"
R="$FX/17c"; newrepo "$R"; mkdir -p "$R/reviews"
echo "unrelated review text" > "$R/$REF"; echo "id,closable" > "$R/register.csv"; echo "r1,YES" >> "$R/register.csv"; : > "$R/ledger.csv"; H0=$(c "$R" "H0: base")
git -C "$R" checkout -q -b b1 "$H0"; echo "review body $DIG" >> "$R/$REF"; B1=$(c "$R" "B1: insert digest")
echo "r1,1,YES->NO,$DIG,approved_at_head=$B1,ref=$REF" >> "$R/ledger.csv"; A=$(c "$R" "A: approval row (descends from B1)")
git -C "$R" checkout -q -b b2 "$H0"; echo "review body $DIG" >> "$R/$REF"; B2=$(c "$R" "B2: independent insert of same digest")
git -C "$R" checkout -q b1; git -C "$R" merge -q --no-edit b2 >/dev/null 2>&1 || { git -C "$R" checkout --theirs "$REF" 2>/dev/null; git -C "$R" add -A; git -C "$R" commit -q -m "merge b2"; }
sed -i '' 's/^r1,YES$/r1,NO/' "$R/register.csv"; M=$(c "$R" "M: NO transition")
dag "$R"; echo "H0=$H0 B1=$B1 B2=$B2 A=$A M=$M"
bash "$CR" "$R" "$DIG" "$REF" "$M" "$A"; echo "cr_rc=$?"

# ⑮ (v2.13 회귀)  신규 아티팩트 R ∥ A merge — R ⋠ A
sec "T-82 (15) regression — new artifact R ∥ A"
R="$FX/15"; newrepo "$R"
echo "id,closable" > "$R/register.csv"; echo "r1,YES" >> "$R/register.csv"; : > "$R/ledger.csv"; H0=$(c "$R" "H0: base (no reviewer path)")
git -C "$R" checkout -q -b r "$H0"; mkdir -p "$R/reviews"; echo "review body $DIG" > "$R/$REF"; RR=$(c "$R" "R: new reviewer artifact with digest")
git -C "$R" checkout -q -b a "$H0"; echo "r1,1,YES->NO,$DIG,approved_at_head=$RR,ref=$REF" >> "$R/ledger.csv"; A=$(c "$R" "A: approval row (approved_at_head=R)")
git -C "$R" merge -q --no-edit r; sed -i '' 's/^r1,YES$/r1,NO/' "$R/register.csv"; M=$(c "$R" "M: merge + NO transition")
dag "$R"; echo "H0=$H0 R=$RR A=$A M=$M"
bash "$CR" "$R" "$DIG" "$REF" "$M" "$A"; echo "cr_rc=$?"
```

```bash
#!/usr/bin/env bash
# t82-ledger.sh — T-82 ⑱(병렬 seq=1 충돌 → MALFORMED → Z1/Z2 supersedes append → NO_ROWS_CLEAR·구 행 잔존)
#                 + (v) 재부여 충돌 → 재-supersede 복구 (git 픽스처) + (iii) 순환 시도 → 부재 행 지목 MALFORMED (모델)
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
LX="$SP/ledger-exec.py"; FX="$SP/fx"; L=ledger.csv
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec() { printf '\n########## %s ##########\n' "$*"; }
c()  { git -C "$1" add -A && git -C "$1" commit -q --allow-empty -m "$2" && git -C "$1" rev-parse --short HEAD; }
run(){ python3 "$LX" git "$1" "$L" 2; echo "ledger_rc=$?"; }
refof(){ python3 "$LX" refs "$1" "$L" | awk -v n="$2" '$1==n{gsub(/[()]/,"",$2); sub(/^row_ref=/,"",$2); print $2}' | tr ',' ':'; }

sec "T-82 (18) parallel edge_seq=1 conflict -> recovery by supersedes (git fixture, edges=2)"
R="$FX/18"; rm -rf "$R"; git init -q -b main "$R"
: > "$R/$L"; H=$(c "$R" "H: base (empty ledger; register r1 has two ->NO edges e_a, e_b)")
git -C "$R" checkout -q -b x "$H"; echo "X1|r1|1|YES->NO|D|" >> "$R/$L"; X=$(c "$R" "X1: approval seq=1 for e_a (branch x)")
git -C "$R" checkout -q -b y "$H"; echo "Y1|r1|1|YES->NO|D|" >> "$R/$L"; Y=$(c "$R" "Y1: approval seq=1 for e_b (branch y)")
git -C "$R" checkout -q x; git -C "$R" merge -q --no-edit y 2>/dev/null || { cat "$R/$L" | grep -v '^[<=>]' | sort -u > "$R/$L.m"; mv "$R/$L.m" "$R/$L"; git -C "$R" add -A; git -C "$R" commit -q -m "M: merge x+y (both seq=1)"; }
M=$(git -C "$R" rev-parse --short HEAD)
git -C "$R" log --graph --oneline --all; echo "H=$H X=$X Y=$Y M=$M"
echo "-- ledger @M --"; cat "$R/$L"
echo "-- before recovery --"; run "$R"
RX=$(refof "$R" X1); RY=$(refof "$R" Y1); echo "row_ref(X1)=$RX  row_ref(Y1)=$RY"
echo "Z1|r1|1|YES->NO|D|$RX" >> "$R/$L"; echo "Z2|r1|2|YES->NO|D|$RY" >> "$R/$L"; Z=$(c "$R" "Z: reassignment rows Z1(seq=1 supersedes X1) Z2(seq=2 supersedes Y1) — append only")
echo "-- ledger @Z (구 행 X1·Y1 잔존 확인) --"; cat "$R/$L"
echo "-- after recovery --"; run "$R"
echo "-- g5 불변: 구 행이 도입 시점 내용과 동일한가 --"
for n in X1 Y1; do a=$(git -C "$R" show "$M:$L" | grep "^$n|"); b=$(grep "^$n|" "$R/$L"); [ "$a" = "$b" ] && echo "$n: 동일" || echo "$n: 변조!"; done

sec "T-82 (v) rival reassignment rows (both supersede X1, in PARALLEL commits) -> MALFORMED -> re-supersede both -> NO_ROWS_CLEAR"
git -C "$R" checkout -q "$M" 2>/dev/null; git -C "$R" checkout -q -b rival_a
echo "Za|r1|1|YES->NO|D|$RX" >> "$R/$L"; echo "Z2|r1|2|YES->NO|D|$RY" >> "$R/$L"; ZA=$(c "$R" "Za: rival reassignment (supersedes X1) + Z2  [branch rival_a]")
git -C "$R" checkout -q -b rival_b "$M"
echo "Zb|r1|1|YES->NO|D|$RX" >> "$R/$L"; ZB=$(c "$R" "Zb: rival reassignment (supersedes X1)  [branch rival_b]")
git -C "$R" checkout -q rival_a; git -C "$R" merge -q --no-edit rival_b 2>/dev/null || { grep -v '^[<=>]' "$R/$L" | awk '!seen[$0]++' > "$R/$L.m"; mv "$R/$L.m" "$R/$L"; git -C "$R" add -A; git -C "$R" commit -q -m "M2: merge rival_a+rival_b"; }
echo "-- ledger @M2 --"; cat "$R/$L"
echo "-- rival state --"; run "$R"
RA=$(refof "$R" Za); RB=$(refof "$R" Zb); echo "row_ref(Za)=$RA row_ref(Zb)=$RB"
echo "Zc|r1|1|YES->NO|D|$RA;$RB" >> "$R/$L"; ZC=$(c "$R" "Zc: supersedes both rivals")
echo "-- after re-supersede --"; run "$R"
git -C "$R" log --graph --oneline --all

sec "T-82 (iii) cycle attempt -> folds into absent-row targeting -> MALFORMED (model; H5-① makes true cycles unconstructible)"
cat > "$FX/iii.json" <<'EOF'
{"order":["cA","cB","cA2"],
 "rows":[{"name":"A2","row_id":"r1","edge_seq":1,"transition":"YES->NO","digest":"D","c_APP":"cA","sups":[["cB","*"]]},
         {"name":"B","row_id":"r1","edge_seq":1,"transition":"YES->NO","digest":"D","c_APP":"cB","sups":[["cA","*"]]}]}
EOF
echo "(모델: A 가 B 를 지목하도록 «편집»되면 A 의 row_digest 가 바뀌어 B 가 지목한 원래 A 행은 부재가 된다 — 순환은 구성 불가, 부재 지목으로 접힌다)"
python3 - "$FX/iii.json" <<'PY'
import json,sys,hashlib
m=json.load(open(sys.argv[1])); F=("row_id","edge_seq","transition","digest","supersedes")
def dg(r,s): return hashlib.sha256(b"\0".join(f"{k}={v}".encode() for k,v in sorted({**{k:r[k] for k in F if k!='supersedes'},'supersedes':s}.items()))).hexdigest()[:16]
A0={"row_id":"r1","edge_seq":1,"transition":"YES->NO","digest":"D"}
dA0=dg(A0,""); B=m["rows"][1]; dB=dg(B,f"cA:{dA0}")            # B 는 «원래 A»(supersedes 없음)를 지목
A2=m["rows"][0]; dA2=dg(A2,f"cB:{dB}")                          # A 를 편집해 B 를 지목 → A 의 digest 가 dA0 → dA2 로 변함
m["rows"][0]["sups"]=[["cB",dB]]; m["rows"][1]["sups"]=[["cA",dA0]]
print(f"digest(A original)={dA0}  digest(A2 edited)={dA2}  digest(B)={dB}")
json.dump(m,open(sys.argv[1],"w"))
PY
python3 "$LX" model "$FX/iii.json" 1; echo "ledger_rc=$?"
```

## 4. 실행 기록 — g6 (⑰ⓐⓑⓒ·⑮) 픽스처 DAG + 방출값 원문

```text
t82_cr_utc=2026-08-18T14:58:55Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t82-cr.sh

########## T-82 (17)a existing-path B∥A ##########
* cc714d5 M: merge + NO transition
*   2da8d24 Merge branch 'b' into a
|\  
| * ea83458 B: insert digest into existing reviewer path
* | a56272f A: approval row (approved_at_head=B)
|/  
* 58f3486 H0: base (reviewer path exists, no digest)
H0=58f3486 B=ea83458 A=a56272f M=cc714d5
C_R(c=cc714d5) = { ea83458 }
g6_verdict=APPROVAL_ORDER_INVALID
reason=C_R 원소 중 c_APP=a56272f 의 진 조상 없음
cr_rc=1

########## T-82 (17)b digest introduced at merge resolution ##########
*   49a00b4 M: merge — digest introduced in resolution + NO transition
|\  
| * 5d44208 B: reviewer edit without digest
* | be82e7c A: approval row (approved_at_head=B)
|/  
* 0a5dc72 H0: base
H0=0a5dc72 B=5d44208 A=be82e7c M=49a00b4
C_R(c=49a00b4) = { 49a00b4 }
g6_verdict=APPROVAL_ORDER_INVALID
reason=C_R 원소 중 c_APP=be82e7c 의 진 조상 없음
cr_rc=1

########## T-82 (17)c positive — independent B1/B2, A descends from B1 ##########
* 10193d8 M: NO transition
*   94a3de2 Merge branch 'b2' into b1
|\  
| * c235cd3 B2: independent insert of same digest
* | 40187a0 A: approval row (descends from B1)
* | 4306ac0 B1: insert digest
|/  
* 6ac2601 H0: base
H0=6ac2601 B1=4306ac0 B2=c235cd3 A=40187a0 M=10193d8
C_R(c=10193d8) = { c235cd3 4306ac0 }
g6_verdict=OK
reason=증인 4306ac0 ⊰ c_APP=40187a0
cr_rc=0

########## T-82 (15) regression — new artifact R ∥ A ##########
* 790ea3f M: merge + NO transition
*   10ade57 Merge branch 'r' into a
|\  
| * ac5f2ef R: new reviewer artifact with digest
* | 00873c0 A: approval row (approved_at_head=R)
|/  
* 18d7e1e H0: base (no reviewer path)
H0=18d7e1e R=ac5f2ef A=00873c0 M=790ea3f
C_R(c=790ea3f) = { ac5f2ef }
g6_verdict=APPROVAL_ORDER_INVALID
reason=C_R 원소 중 c_APP=00873c0 의 진 조상 없음
cr_rc=1
(t82-cr.sh exit=0)
```

## 5. 실행 기록 — 원장 (⑱·(v)·(iii)) 픽스처 DAG + 방출값 원문 (+ H5-② 모델)

```text
t82_ledger_utc=2026-08-18T15:01:15Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t82-ledger.sh

########## T-82 (18) parallel edge_seq=1 conflict -> recovery by supersedes (git fixture, edges=2) ##########
자동 병합: ledger.csv
충돌 (내용): ledger.csv에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
*   d727ebd M: merge x+y (both seq=1)
|\  
| * cbb9cd3 Y1: approval seq=1 for e_b (branch y)
* | 0fb79da X1: approval seq=1 for e_a (branch x)
|/  
* 8cae81a H: base (empty ledger; register r1 has two ->NO edges e_a, e_b)
H=8cae81a X=0fb79da Y=cbb9cd3 M=d727ebd
-- ledger @M --
X1|r1|1|YES->NO|D|
Y1|r1|1|YES->NO|D|
-- before recovery --
LEDGER_EFF={X1,Y1} tombstoned={-} rows_present=2
closable_no_provenance_state=APPROVAL_MALFORMED
reason=LEDGER_EFF 내 (row_id,edge_seq) 중복: {('r1', 1): ['X1', 'Y1']}
ledger_rc=1
row_ref(X1)=0fb79da9e623:131eb9610d010b5c  row_ref(Y1)=cbb9cd33ef33:131eb9610d010b5c
-- ledger @Z (구 행 X1·Y1 잔존 확인) --
X1|r1|1|YES->NO|D|
Y1|r1|1|YES->NO|D|
Z1|r1|1|YES->NO|D|0fb79da9e623:131eb9610d010b5c
Z2|r1|2|YES->NO|D|cbb9cd33ef33:131eb9610d010b5c
-- after recovery --
LEDGER_EFF={Z1,Z2} tombstoned={X1,Y1} rows_present=4
closable_no_provenance_state=NO_ROWS_CLEAR
reason=키 중복 0 · 결번 0 · 구 행 잔존=['X1', 'Y1']
ledger_rc=0
-- g5 불변: 구 행이 도입 시점 내용과 동일한가 --
X1: 동일
Y1: 동일

########## T-82 (v) rival reassignment rows (both supersede X1, in PARALLEL commits) -> MALFORMED -> re-supersede both -> NO_ROWS_CLEAR ##########
자동 병합: ledger.csv
충돌 (내용): ledger.csv에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
-- ledger @M2 --
X1|r1|1|YES->NO|D|
Y1|r1|1|YES->NO|D|
Za|r1|1|YES->NO|D|0fb79da9e623:131eb9610d010b5c
Z2|r1|2|YES->NO|D|cbb9cd33ef33:131eb9610d010b5c
Zb|r1|1|YES->NO|D|0fb79da9e623:131eb9610d010b5c
-- rival state --
LEDGER_EFF={Z2,Za,Zb} tombstoned={X1,Y1} rows_present=5
closable_no_provenance_state=APPROVAL_MALFORMED
reason=LEDGER_EFF 내 (row_id,edge_seq) 중복: {('r1', 1): ['Za', 'Zb']}
ledger_rc=1
row_ref(Za)=8bc5d4a4ff26:89d59bd5efc78fe5 row_ref(Zb)=feef777bb38b:89d59bd5efc78fe5
-- after re-supersede --
LEDGER_EFF={Z2,Zc} tombstoned={X1,Y1,Za,Zb} rows_present=6
closable_no_provenance_state=NO_ROWS_CLEAR
reason=키 중복 0 · 결번 0 · 구 행 잔존=['X1', 'Y1', 'Za', 'Zb']
ledger_rc=0
* 6d13837 Zc: supersedes both rivals
*   5cee4e2 M2: merge rival_a+rival_b
|\  
| * feef777 Zb: rival reassignment (supersedes X1)  [branch rival_b]
* | 8bc5d4a Za: rival reassignment (supersedes X1) + Z2  [branch rival_a]
|/  
| * 5918481 Z: reassignment rows Z1(seq=1 supersedes X1) Z2(seq=2 supersedes Y1) — append only
|/  
*   d727ebd M: merge x+y (both seq=1)
|\  
| * cbb9cd3 Y1: approval seq=1 for e_b (branch y)
* | 0fb79da X1: approval seq=1 for e_a (branch x)
|/  
* 8cae81a H: base (empty ledger; register r1 has two ->NO edges e_a, e_b)

########## T-82 (iii) cycle attempt -> folds into absent-row targeting -> MALFORMED (model; H5-① makes true cycles unconstructible) ##########
(모델: A 가 B 를 지목하도록 «편집»되면 A 의 row_digest 가 바뀌어 B 가 지목한 원래 A 행은 부재가 된다 — 순환은 구성 불가, 부재 지목으로 접힌다)
digest(A original)=131eb9610d010b5c  digest(A2 edited)=b8b11bc9eb86f7e4  digest(B)=c7f616aa6d5a25b6
LEDGER_EFF={A2} tombstoned={B} rows_present=2
closable_no_provenance_state=APPROVAL_MALFORMED
reason=supersedes 가 부재 행 지목 [G5-(ii)]: [('B', ('cA', '131eb9610d010b5c'))]
ledger_rc=1
(t82-ledger.sh exit=0)

-- [H5-②] 같은 c_APP 안 동일 row_digest 행 둘 (모델) --
$ python3 ledger-exec.py model fx/h52.json 1
closable_no_provenance_state=APPROVAL_MALFORMED
reason=같은 c_APP 안 동일 row_digest 행 둘 이상 [H5-②] row_ref 비단사: {('cS', '131eb9610d010b5cfa1c472cf82e973ab2bee400a9dc5ce461e1e5c58c0d0d09'): ['P', 'Q']}
ledger_rc=1
```

## 6. 관측·정직 기록

1. **(v) 픽스처 1차 구성 오류와 실행기 보강**: 첫 실행에서 Za·Zb 를 **같은 커밋**에 넣어 두 행의
   `row_ref` 가 동일해졌고, 실행기가 이를 «키 중복 MALFORMED» 로 잡아 극성은 맞았으나 계약 [H5-②](같은
   c_APP 안 동일 row_digest 행 둘 = MALFORMED — 지목 대상 비결정)의 사유가 아니었고, 이어진 Zc 가 «양쪽
   동시 묘비화»(계약이 택하지 않은 대안)로 복구되는 형태였다. **실행기에 [H5-②] 검사를 추가**하고 픽스처를
   «경쟁 재부여 = 별개 브랜치 커밋»으로 정정해 재실행했다(§5 는 정정 후 원문). 보너스 모델로 [H5-②] 가
   그 자체로 MALFORMED 를 내는 것을 확인.
2. **(iii) 순환은 구성 불가**: [H5-①] 대로 supersedes 가 digest 정규형에 포함되므로 A 가 B 를 지목하도록
   편집되는 순간 A 의 row_ref 가 바뀌어 B 의 지목이 «부재 행» 으로 접힌다 — 실행기의 순환 검사는 방어적
   잔존이며 실측 발화 경로는 [G5-(ii)] 였다.
3. **c_APP 파생**: 픽스처 원장 행은 각 커밋에 유일하게 도입되므로 구조 정의(도입 지점)가 단일 원소를 낸다.
   실제 소비자는 U-16-g g5 의 «도입 커밋 시점 내용 대조» 와 결합해야 하며 이 손 실행은 그 부분(g1~g5·h)을
   실행하지 않았다 — 검사 범위는 g6 와 tombstone-graph 판정뿐이다.
4. 본 저장소 무접촉: 픽스처는 `scratchpad/fx/*` 독립 저장소, worktree 미사용.
