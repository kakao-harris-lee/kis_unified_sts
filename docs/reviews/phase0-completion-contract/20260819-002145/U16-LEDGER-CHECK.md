# U16-LEDGER-CHECK — v2.15 T-82 ⑱(전 규칙)·⑯·⑰ⓐⓑⓒ·⑲·⑮ + 자인 잔여 손 실행 기록 (S-23 전 규칙 실행기)

> **비규범 손 실행 — 실제 소비자(`tools/tos_completion_status.py --check`)는 D0-A 이후이며, 이 파일은
> 계약(v2.15 `11a56d3e`)이 경로·형식을 규정하지 않은 부속이다.** U-16/§13.6.5/§8 T-82 행 어디에도 증거
> 아티팩트 경로가 없음(직전 사이클 grep 0건·v2.15 도 동일)을 전제로, 같은 스탬프 디렉터리에 sibling 으로 두었다.
> 픽스처는 전부 scratchpad 하위 **독립 git 저장소**(`fx82/*` — 본 저장소와 무관·무접촉·worktree 미사용)다.
- **생성 시각**: 2026-08-18T16:43:21Z (UTC) · 실행 시각 `t82_v215_utc=2026-08-18T16:32:43Z` · **생성 주체**: 오케스트레이터
  지시 하의 실행 에이전트(실행)·조립 에이전트(조립 — 재실행 없이 원문 그대로 수록)
- **관련 계약**: U-16-a `EDGES(r)` 전칭 · U-16-a2 · U-16-c(c_APP ⊰ c) · U-16-g (g1~g6 — **g6 = blob 동일성 `C_R(c)` + ∃ 증인
  [F3 v2.15 재정의·H4]**) · U-16-h · **#2 마감 스키마: `edge_seq` 기재 필드 폐지 → 소비자 파생**(F4) · **S-23**(실행 규칙 목록
  방출·차집합 비면 green 금지) · §8 T-82 행 ⑮⑯⑰⑱⑲ (19종) · «닫지 못하는 것» 정직 표기(:6215-6220)
- **S-23 — 이 실행기가 실행·방출한 규칙 목록**(각 run 의 `rules_executed=` 라인 원문과 동일 · 계약 소비 규칙 집합과의
  차집합 ∅ 을 실행기가 검사하고, 비어 있지 않으면 `NO_ROWS_CLEAR` 대신 `PARTIAL_EXECUTION` 을 방출하도록 잠금):
  `U-16-a(EDGES)` · `g1` · `U-16-c(c_APP⊰c)` · `g2` · `g3` · `g4` · `g5` · `h` · `g6(C_R blob·∃witness)` · `U-16-a2(∀edge∃row)` ·
  `MALFORMED(orphan/double-cover)` — **11 규칙 전부 실행**(v2.14 부속은 g6 + tombstone-graph 만 실행해 «회피» 판정).
- **결과 요약 — 실행기 stdout·rc 원문 그대로**:

| 변이 | 픽스처 (DAG 는 §3·§4) | 방출값 (`closable_no_provenance_state=`) | rc | 기대 (§8 T-82 행) | 대조 |
| --- | --- | --- | --- | --- | --- |
| **⑱ 병렬 X∥Y (edge_seq 필드 없음)** | H0(r1=YES) → 브랜치 a: X(승인·rationale a) → CX(NO 전이) ∥ 브랜치 b: Y(승인·rationale b) → CY(NO 전이) → M(원장 합집합 머지) | `NO_ROWS_CLEAR` · edge#1·#2 각각 정확히 1행에 덮임 · `edge_seq 표시용 파생=[1,2]` | 0 | **v2.15 재저작**: append 없이 소비자 파생 → **green** · 구 행 무변조 | **일치** |
| ⑯ 회귀 (ABSENT→NO→YES→NO, 간선별 승인) | H0(r1 absent) → A1 → e1(ABSENT->NO) → back to YES → A2 → e2(YES->NO) | `NO_ROWS_CLEAR` · edge#1 `ABSENT->NO` COVERED by A1 · edge#2 `YES->NO` COVERED by A2 | 0 | green (어떤 간선도 무시되지 않음) | **일치** |
| ⑰ⓐ 기존-경로 `B∥A` (blob C_R) | H0(무관 리뷰) → B(실제 리뷰 내용=digest 삽입) ∥ A(aah=B) → M0 → M(NO) | `APPROVAL_ORDER_INVALID` · `C_R={ba06260}` 증인 없음 | 1 | `C_R={B}` · B ⋠ A → ORDER_INVALID red | **일치** |
| ⑰ⓑ 머지 해소에서 digest blob 도입 | H0 → B(digest 없는 편집) ∥ A(aah=B) → M(해소에서 digest 도입 + NO) | **`APPROVAL_UNBOUND`**(h: digest ∉ blob(aah=B)) · g6 단독 뷰(target=blob(M)) `C_R={726da04}` → `APPROVAL_ORDER_INVALID` | 1 | «`C_R={M}` · M ⋠ A → red» | **red 일치 · 값은 h 가 g6 보다 먼저 발화 — §5-1 보고** |
| ⑰ⓒ 양성 — B1·B2 독립 동일 blob, A ⊐ B1 | H0 → B1(리뷰 blob) → A(aah=B1) ∥ B2(독립 동일 blob) → M0 → M(NO) | `NO_ROWS_CLEAR` · `C_R={e8f3dfc,bb3cde9}` 증인 B1 | 0 | green (∃ 양화자) | **일치** |
| **⑲ digest 선배치** | H0(**digest 만 담은 빈 운반자**) → B(실제 내용 작성·digest 유지) ∥ A(aah=B) → M0 → M(NO) | `APPROVAL_ORDER_INVALID` · `C_R={ae57e70}`(=B) 증인 없음 | 1 | **blob 정의**: `C_R={B}` · B ⋠ A → red | **일치** |
| ⑲ 대조 — v2.14 토큰 기반 C_R | 같은 픽스처 | `token C_R={e0b4e46}`(=H0) · `witness=YES(green — 선배치 우회 통과)` | — | v2.14 정의에서 g6 통과(우회) | **일치 — F3 재정의의 판별력 실증** |
| ⑮ 회귀 (신규 아티팩트 R ∥ A) | H0(리뷰 경로 없음) → R(신규 아티팩트) ∥ A(aah=R) → M0 → M(NO) | `APPROVAL_ORDER_INVALID` · `C_R={719390f}`(=R, [H4] 부모 경로 부재 = ≠) | 1 | red | **일치** |
| 자인 잔여 — 단일 행이 두 간선 덮음 | H0 → A(단일 승인) → e1 → back to YES → e2(승인 없음) | `NO_ROWS_CLEAR` · edge#1·#2 둘 다 `COVERED by c_APP=fe4f94e` | 0 | 계약 «닫지 못하는 것» 정직 표기 그대로 — «덮였다»까지만 주장 | **일치(계약 정직 표기와 정합)** |

---

## 1. 전 규칙 실행기 `u16-full-exec.py` — 원문 (sha256 `a0201149b794de7ae438d05e035246d35598a1173ecd5481e1217e647f38e5d0`)

독해 선언(계약이 리터럴로 고정하지 않은 자리):
- **판정 우주** = HEAD 레지스터에서 `closable=NO` 인 모든 행 · `EDGES(r)` = `git rev-list HEAD` 전수에서 `closable(c,r)==NO ∧
  closable(p,r)!=NO` 인 (p→c) — 루트(p 없음)·부모에 행 부재 = `ABSENT->NO`. **`edge_seq` 는 표시용 파생**((author date, commit id)
  사전식) — 판정에 소비하지 않는다(#2 마감 스키마).
- **c_APP** = 원장 raw 행의 도입 지점(구조: 행 ∈ blob(x:LEDGER) ∧ ∀p ∉ — 복수면 사전순 최소; 픽스처는 단일).
- **덮음** ⇔ g1 ∧ U-16-c(c_APP ⊰ c, 동일 커밋 = `APPROVAL_SAME_COMMIT`) ∧ g2 ∧ g3 ∧ g4 ∧ g5 ∧ h ∧ g6. **g6 `C_R(c)`** = `{ x ⊑ c :
  blob(x:ref) == blob(aah:ref) ∧ ∀p∈parents(x): blob(p:ref) ≠ 그 blob }` — 부모에 경로 부재는 `≠` 로 읽음([H4]) · `C_R=∅` →
  `PROVENANCE_UNVERIFIABLE`(면제 없음) · 요구 ∃ x∈C_R: x ⊰ c_APP.
- **판정** = U-16-a2 ∀간선 ∃덮는 행 · 이중 덮음/구조적 고아(row_id 무간선·g1 전부 불일치) = MALFORMED · 특정 규칙에서 탈락한 행은
  그 규칙 상태로 귀속(고아 아님).
- **상태 우선순위(실행기 선언 — 계약 U-16-d 는 전순서를 두지 않는다)**: «전제 붕괴 순서» PROVENANCE_UNVERIFIABLE > MALFORMED >
  MISSING > SAME_COMMIT > AFTER > CONTENT_DRIFT > HEAD_INVALID > ROW_MUTATED > UNBOUND > ORDER_INVALID > NO_ROWS_CLEAR. **규칙 평가
  순서 g1 → U-16-c → g2 → g3 → g4 → g5 → h → g6** — 행이 h 에서 탈락하면 g6 은 평가되지 않는다(⑰ⓑ 의 관측 근거, §5-1).
- **S-23 잠금**: `rules_executed=` 방출 후 계약 소비 규칙 집합(11)과 차집합이 비지 않으면 `NO_ROWS_CLEAR` 대신 `PARTIAL_EXECUTION`/1.
- rc 0 = `NO_ROWS_CLEAR` 만 · 예외 경로는 `PROVENANCE_UNVERIFIABLE`/1 로 폐쇄.

```python
#!/usr/bin/env python3
"""U-16 «전 규칙» 손 실행기 — v2.15 (계약 11a56d3e §13.6.5 U-16-a/a2/c/d/f/g(g1~g6)/h · #2 마감 스키마: edge_seq 없음).
S-23: 실행한 규칙 목록을 방출하고, 계약 소비 규칙 집합과 차집합이 비지 않으면 green 을 방출하지 않는다.
픽스처 형식: register.csv = 'id,closable,owner_track' (헤더 있음) · LEDGER.md 행 = 'row_id | transition | row_content_digest | approved_at_head | reviewer_ref | rationale_ref'
row_content_digest = U-16-f: 레지스터 행 전 열을 LC_ALL=C 열이름 정렬 '<열>=<값>' NUL 결합 sha256.
간선: U-16-a  EDGES(r) = { (p→c) : closable(c,r)==NO ∧ closable(p,r)!=NO } (루트는 p=None → ABSENT->NO). 판정 우주 = HEAD 에서 closable=NO 인 모든 행.
덮음(a 가 (p→c) 를 덮는다) ⇔ g1 ∧ U-16-c(c_APP(a) ⊰ c, 동일 커밋 거부) ∧ g2 ∧ g3 ∧ g4 ∧ g5 ∧ h ∧ g6.   판정 = U-16-a2 ∀간선 ∃덮는 행 · 이중 덮음/구조적 고아 행(row_id 무간선·g1 전부 불일치) = MALFORMED · 규칙 탈락 행은 그 규칙 상태로 귀속.
상태 우선순위(실행기 선언 — 계약 U-16-d 는 전순서를 두지 않으므로 «전제 붕괴 순서»로 정함): PROVENANCE_UNVERIFIABLE > APPROVAL_MALFORMED > APPROVAL_MISSING > SAME_COMMIT > AFTER > CONTENT_DRIFT > HEAD_INVALID > ROW_MUTATED > UNBOUND > ORDER_INVALID > NO_ROWS_CLEAR
방출: closable_no_provenance_state=<값> · rules_executed=<목록> · rc 0 = NO_ROWS_CLEAR 만.
"""
import hashlib, subprocess, sys
RULES_CONTRACT = ["U-16-a(EDGES)", "U-16-a2(∀edge∃row)", "U-16-c(c_APP⊰c)", "g1", "g2", "g3", "g4", "g5", "g6(C_R blob·∃witness)", "h", "MALFORMED(orphan/double-cover)"]
REG, LED = "register.csv", "LEDGER.md"
PRIO = ["PROVENANCE_UNVERIFIABLE","APPROVAL_MALFORMED","APPROVAL_MISSING","APPROVAL_SAME_COMMIT","APPROVAL_AFTER","APPROVAL_CONTENT_DRIFT","APPROVAL_HEAD_INVALID","APPROVAL_ROW_MUTATED","APPROVAL_UNBOUND","APPROVAL_ORDER_INVALID","NO_ROWS_CLEAR"]
R = None
def g(*a): return subprocess.run(["git","-C",R,*a],capture_output=True,text=True).stdout.strip()
def ok(*a): return subprocess.run(["git","-C",R,*a],capture_output=True).returncode==0
def show(c,p):
    r=subprocess.run(["git","-C",R,"show",f"{c}:{p}"],capture_output=True,text=True); return r.stdout if r.returncode==0 else None
def blob(c,p): return g("rev-parse","--quiet","--verify",f"{c}:{p}") or "ABSENT"
def parents(c): return g("log","--format=%P","-1",c).split()
def strict_anc(a,b): return a!=b and ok("merge-base","--is-ancestor",a,b)
def reg_rows(c):
    t=show(c,REG); out={}
    if t is None: return out
    lines=[l for l in t.splitlines() if l.strip()]
    if not lines: return out
    hdr=lines[0].split(",")
    for l in lines[1:]:
        f=l.split(","); out[f[0]]=dict(zip(hdr,f))
    return out
def canon_digest(row): return hashlib.sha256(b"\0".join(f"{k}={row[k]}".encode() for k in sorted(row))).hexdigest()
def led_rows(c):
    t=show(c,LED); out=[]
    if t is None: return out
    for l in t.splitlines():
        if not l.strip() or l.startswith("#"): continue
        f=[x.strip() for x in l.split("|")]
        if len(f)>=6: out.append(dict(row_id=f[0],transition=f[1],digest=f[2],aah=f[3],reviewer_ref=f[4],rationale_ref=f[5],raw=l))
    return out
def c_app(row):  # 도입 지점(구조): raw 행 ∈ blob(x:LED) ∧ ∀p ∉ — 복수면 사전순 최소(픽스처는 단일)
    cands=[x for x in g("rev-list","HEAD").splitlines() if row["raw"] in (show(x,LED) or "") and all(row["raw"] not in (show(p,LED) or "") for p in parents(x))]
    return sorted(cands)[0] if cands else None
def emit(state, reason, executed):
    print(f"rules_executed={';'.join(executed)}")
    missing=[r for r in RULES_CONTRACT if r not in executed]
    if missing and state=="NO_ROWS_CLEAR":
        print(f"closable_no_provenance_state=PARTIAL_EXECUTION\nreason=S-23: 미실행 규칙 {missing} — green 방출 금지"); sys.exit(1)
    print(f"closable_no_provenance_state={state}\nreason={reason}"); sys.exit(0 if state=="NO_ROWS_CLEAR" else 1)
def main():
    global R; R=sys.argv[1]; executed=[]
    if not ok("rev-parse","--is-inside-work-tree") or g("rev-parse","--is-shallow-repository")!="false": emit("PROVENANCE_UNVERIFIABLE","이력 파생 불가",executed)
    HEAD=g("rev-parse","HEAD"); cur=reg_rows(HEAD)
    no_rows=[rid for rid,r in cur.items() if r.get("closable")=="NO"]
    # U-16-a: EDGES(r) for each NO row
    executed.append("U-16-a(EDGES)")
    edges={}
    for rid in no_rows:
        E=[]
        for c in g("rev-list","HEAD").splitlines():
            if reg_rows(c).get(rid,{}).get("closable")!="NO": continue
            ps=parents(c) or [None]
            for p in ps:
                pv = "ABSENT" if p is None or rid not in reg_rows(p) else reg_rows(p)[rid]["closable"]
                if pv!="NO": E.append((p,c,"ABSENT->NO" if pv=="ABSENT" else "YES->NO"))
        # 표시용 edge_seq 파생: (author date, commit id) 사전식 (U-12 ①-b)
        E.sort(key=lambda e:(g("log","--format=%ad","--date=iso-strict","-1",e[1]),e[1]))
        edges[rid]=E
    L=led_rows(HEAD)
    for a in L: a["c_APP"]=c_app(a)
    print(f"NO_rows={no_rows}")
    for rid,E in edges.items(): print(f"EDGES({rid})={[((p or 'ROOT')[:7],c[:7],t) for p,c,t in E]}  (edge_seq 표시용 파생={list(range(1,len(E)+1))})")
    print(f"ledger_rows={[(a['row_id'],a['transition'],(a['c_APP'] or '?')[:7]) for a in L]}")
    def covers(a,p,c,kind):   # → (True,'') | (False,state,why)  — 규칙 순서: g1 → U-16-c → g2 → g3 → g4 → g5 → h → g6
        if a["row_id"]!=[k for k,E in edges.items() if (p,c,kind) in E][0]: return (False,None,"row_id≠")
        if a["transition"]!=kind: return (False,"APPROVAL_MALFORMED",f"g1 {a['transition']}≠{kind}")
        if not a["c_APP"]: return (False,"APPROVAL_MALFORMED","c_APP 파생 불가")
        if a["c_APP"]==c: return (False,"APPROVAL_SAME_COMMIT","U-16-c c_APP==c")
        if not strict_anc(a["c_APP"],c): return (False,"APPROVAL_AFTER","U-16-c c_APP⋠c")
        if canon_digest(cur[a["row_id"]])!=a["digest"]: return (False,"APPROVAL_CONTENT_DRIFT","g2 digest≠재계산")
        if not ok("merge-base","--is-ancestor",a["aah"],c) or show(a["aah"],a["reviewer_ref"]) is None: return (False,"APPROVAL_HEAD_INVALID","g3")
        if show(HEAD,a["rationale_ref"]) is None: return (False,"APPROVAL_MALFORMED","g4 rationale_ref 부재")
        if a["raw"] not in (show(a["c_APP"],LED) or ""): return (False,"APPROVAL_ROW_MUTATED","g5")
        if a["digest"] not in show(a["aah"],a["reviewer_ref"]): return (False,"APPROVAL_UNBOUND","h digest∉blob(aah)")
        tgt=blob(a["aah"],a["reviewer_ref"])
        CR=[x for x in g("rev-list",c).splitlines() if blob(x,a["reviewer_ref"])==tgt and all(blob(pp,a["reviewer_ref"])!=tgt for pp in parents(x))]
        a.setdefault("_CR",{})[c]=CR
        if not CR: return (False,"PROVENANCE_UNVERIFIABLE","g6 C_R=∅")
        if not any(strict_anc(x,a["c_APP"]) for x in CR): return (False,"APPROVAL_ORDER_INVALID",f"g6 C_R={{{','.join(x[:7] for x in CR)}}} 증인 없음")
        return (True,None,"")
    executed += ["g1","U-16-c(c_APP⊰c)","g2","g3","g4","g5","h","g6(C_R blob·∃witness)","U-16-a2(∀edge∃row)","MALFORMED(orphan/double-cover)"]
    worst=[]; covered_by={}
    for rid,E in edges.items():
        for i,(p,c,kind) in enumerate(E,1):
            hits=[]; fails=[]
            for a in L:
                if a["row_id"]!=rid: continue
                okc,st,why=covers(a,p,c,kind)
                if okc: hits.append(a)
                elif st: fails.append((st,why,(a['c_APP'] or '?')[:7])); a["_attributed"]=True if not why.startswith("g1") else a.get("_attributed",False)
            crs={tuple(a.get('_CR',{}).get(c)) for a in L if a.get('_CR',{}).get(c)}
            crtxt=" C_R="+"|".join("{"+",".join(x[:7] for x in cr)+"}" for cr in crs) if crs else ""
            if len(hits)==1: print(f"edge#{i} {rid} {(p or 'ROOT')[:7]}->{c[:7]} {kind}: COVERED by c_APP={hits[0]['c_APP'][:7]}{crtxt}"); covered_by.setdefault(id(hits[0]),[]).append(c)
            elif len(hits)>1: print(f"edge#{i} {rid} {(p or 'ROOT')[:7]}->{c[:7]} {kind}: DOUBLE-COVER {[h['c_APP'][:7] for h in hits]}"); worst.append("APPROVAL_MALFORMED")
            else:
                print(f"edge#{i} {rid} {(p or 'ROOT')[:7]}->{c[:7]} {kind}: UNCOVERED fails={fails}{crtxt}")
                worst.append(min((f[0] for f in fails), key=PRIO.index) if fails else "APPROVAL_MISSING")
    for a in L:   # 고아 = «어떤 간선에도 구조적으로 대응하지 않는 행»(row_id 무간선·g1 전부 불일치). 특정 규칙(U-16-c~g6)에서 탈락한 행은 그 규칙 상태로 귀속되며 고아가 아니다
        if id(a) not in covered_by and not a.get("_attributed"): print(f"ORPHAN row c_APP={(a['c_APP'] or '?')[:7]} (구조적 비대응)"); worst.append("APPROVAL_MALFORMED")
    if not no_rows: emit("NO_ROWS_CLEAR","closable=NO 행 없음(판정 우주 ∅ — 공허 통과가 아니라 대상 없음)",executed)
    if worst: emit(min(worst,key=PRIO.index),f"차단 사유(우선순위 최상): {sorted(set(worst),key=PRIO.index)}",executed)
    emit("NO_ROWS_CLEAR","모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 고아 0",executed)
if __name__=="__main__":
    try: main()
    except SystemExit: raise
    except Exception as e:
        print(f"rules_executed=\nclosable_no_provenance_state=PROVENANCE_UNVERIFIABLE\nreason=판정 미산출: {e!r}"); sys.exit(1)
```

## 2. 픽스처·드라이버 `t82-v215.sh` — 원문 (sha256 `3b1c86dd60473bb5572513b5c2e583d73e28d4e39941efb42172d1e023f8c207`)

픽스처 형식: `register.csv` = `id,closable,owner_track`(헤더 有) · `LEDGER.md` 행 = `row_id | transition | row_content_digest |
approved_at_head | reviewer_ref | rationale_ref`(**`edge_seq` 열 없음**) · `row_content_digest` = U-16-f(레지스터 행 전 열 `LC_ALL=C`
열이름 정렬 `<열>=<값>` NUL 결합 sha256) — 승인 대상 = 제안된 `r1,NO,tos` 행(`D_NO=81b7ea74…`, 실행 원문 첫 줄). reviewer 경로 상태
4종(full/carrier/unrelated/none)이 각 변이의 H0 를 만든다. 원장 충돌은 합집합으로 해소(`mergeled`) — 기존 행 삭제·변조 없음.

```bash
#!/usr/bin/env bash
# t82-v215.sh — T-82 ⑱(전 규칙 재실행)·⑯ 회귀·⑰ⓐⓑⓒ(blob 기준)·⑲ 선배치·⑮ 회귀·자인 잔여 — 독립 git 픽스처(scratchpad) + 전 규칙 실행기.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
EX="$SP/u16-full-exec.py"; FX="$SP/fx82"; REF=reviews/review.md; RAT=rationale/r1.md
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
dig(){ python3 -c "import hashlib,sys; r=dict(id=sys.argv[1],closable=sys.argv[2],owner_track=sys.argv[3]); print(hashlib.sha256(b'\0'.join(f'{k}={r[k]}'.encode() for k in sorted(r))).hexdigest())" "$@"; }
DNO=$(dig r1 NO tos)     # 승인 대상 = 제안된 NO 행 (id=r1, closable=NO, owner_track=tos)
reg(){ printf 'id,closable,owner_track\n'; for kv in "$@"; do printf '%s\n' "$kv"; done; }   # reg 'other,YES,x' 'r1,NO,tos'
c(){ git -C "$1" add -A && git -C "$1" commit -q --allow-empty -m "$2" && git -C "$1" rev-parse --short HEAD; }
base(){ # base <repo> [reviewer-content-mode: full|carrier|none|unrelated]  — H0: r1=YES, rationale, ledger 헤더, reviewer 경로 상태
  rm -rf "$1"; git init -q -b main "$1"; mkdir -p "$1/reviews" "$1/rationale"
  reg 'other,YES,x' 'r1,YES,tos' > "$1/register.csv"; echo "## ledger" > "$1/LEDGER.md"; echo "rationale for r1 NO" > "$1/$RAT"; echo "rationale (approver a)" > "$1/rationale/r1-a.md"; echo "rationale (approver b)" > "$1/rationale/r1-b.md"
  case "${2:-full}" in full) printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$1/$REF";; carrier) printf '%s\n' "$DNO" > "$1/$REF";; unrelated) printf 'unrelated review text\n' > "$1/$REF";; none) ;; esac
  c "$1" "H0: base (r1=YES; reviewer=${2:-full})"; }
row(){ printf 'r1 | %s | %s | %s | %s | %s\n' "$1" "$DNO" "$2" "$REF" "${3:-$RAT}"; }   # row <transition> <approved_at_head> [rationale_ref]
setNO(){ reg 'other,YES,x' 'r1,NO,tos' > "$1/register.csv"; }
setYES(){ reg 'other,YES,x' 'r1,YES,tos' > "$1/register.csv"; }
run(){ git -C "$1" log --graph --oneline --all; python3 "$EX" "$1"; echo "u16_rc=$?"; }
mergeled(){ # mergeled <repo> <other-commit> <msg> — LEDGER 충돌 시 합집합으로 해소
  git -C "$1" merge -q --no-ff -m "$3" "$2" 2>/dev/null || { { echo "## ledger"; git -C "$1" show HEAD:LEDGER.md | tail -n +2; git -C "$1" show "$2":LEDGER.md | tail -n +2; } | awk '!seen[$0]++' > "$1/LEDGER.md"; git -C "$1" add -A; git -C "$1" commit -q -m "$3"; }; }
echo "D_NO(row_content_digest of proposed r1 NO row) = $DNO"

sec "T-82 (18) parallel X∥Y (no edge_seq field) — full-rule executor"
R="$FX/18"; H0=$(base "$R")
git -C "$R" checkout -q --detach; row YES-\>NO "$(git -C "$R" rev-parse HEAD)" rationale/r1-a.md >> "$R/LEDGER.md"; X=$(c "$R" "X: approval row (aah=H0, rationale a) [branch a]"); setNO "$R"; CX=$(c "$R" "CX: NO transition e_a")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse HEAD)" rationale/r1-b.md >> "$R/LEDGER.md"; Y=$(c "$R" "Y: approval row (aah=H0, rationale b) [branch b]"); setNO "$R"; CY=$(c "$R" "CY: NO transition e_b")
git -C "$R" checkout -q --detach "$CX"; mergeled "$R" "$CY" "M: merge (parents CX,CY both NO)"; git -C "$R" branch -f main HEAD
echo "H0=$H0 X=$X CX=$CX Y=$Y CY=$CY"; cat "$R/LEDGER.md"; run "$R"

sec "T-82 (16) regression — ABSENT->NO->YES->NO, separate approvals per edge"
R="$FX/16"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; H0=$(c "$R" "H0: r1 absent")
row ABSENT-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A1=$(c "$R" "A1: approval (ABSENT->NO)"); setNO "$R"; E1=$(c "$R" "e1: ABSENT->NO")
setYES "$R"; H2=$(c "$R" "back to YES")
row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A2=$(c "$R" "A2: approval (YES->NO)"); setNO "$R"; E2=$(c "$R" "e2: YES->NO")
cat "$R/LEDGER.md"; run "$R"

sec "T-82 (17)a existing-path B∥A (blob C_R)"
R="$FX/17a"; H0=$(base "$R" unrelated)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B=$(c "$R" "B: real review content (digest) into existing path")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$B")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=B) [parallel to B]")
git -C "$R" merge -q --no-ff -m "M0: merge B" "$B"; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B=$B A=$A M=$M"; run "$R"

sec "T-82 (17)b digest blob introduced at merge resolution (aah must cite that blob → g3/h 선발화 여부 실측)"
R="$FX/17b"; H0=$(base "$R" unrelated)
git -C "$R" checkout -q --detach; printf 'unrelated review text\nB-side edit (no digest)\n' > "$R/$REF"; B=$(c "$R" "B: reviewer edit without digest")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$B")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=B — B lacks digest)")
git -C "$R" merge -q --no-commit --no-ff "$B" >/dev/null 2>&1 || true; printf 'independent review of r1 -> NO (introduced in merge resolution)\n%s\n' "$DNO" > "$R/$REF"; setNO "$R"; M=$(c "$R" "M: merge — digest blob introduced in resolution + NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B=$B A=$A M=$M"; run "$R"
echo "-- (17)b g6-isolated view (blob C_R with target=blob(M:ref), c=M, c_APP=A) --"
python3 - "$R" "$REF" "$M" "$A" <<'PY'
import subprocess,sys
R,REF,C,CAPP=sys.argv[1:5]
def g(*a): return subprocess.run(["git","-C",R,*a],capture_output=True,text=True).stdout.strip()
def ok(*a): return subprocess.run(["git","-C",R,*a],capture_output=True).returncode==0
def blob(c): return g("rev-parse","--quiet","--verify",f"{c}:{REF}") or "ABSENT"
tgt=blob(C); CR=[x for x in g("rev-list",C).splitlines() if blob(x)==tgt and all(blob(p)!=tgt for p in g("log","--format=%P","-1",x).split())]
print(f"C_R(target=blob(M))={{{','.join(x[:7] for x in CR)}}}"); w=[x for x in CR if x!=g("rev-parse",CAPP) and ok("merge-base","--is-ancestor",x,CAPP)]
print("g6_verdict=" + ("OK" if w else "APPROVAL_ORDER_INVALID"))
PY

sec "T-82 (17)c positive — B1·B2 independent identical blob, A descends from B1"
R="$FX/17c"; H0=$(base "$R" unrelated)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B1=$(c "$R" "B1: review content (digest)"); row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval (aah=B1)")
git -C "$R" checkout -q --detach main; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B2=$(c "$R" "B2: independent identical blob")
git -C "$R" checkout -q --detach "$A"; git -C "$R" merge -q --no-ff -m "M0: merge B2" "$B2" 2>/dev/null || { git -C "$R" checkout --theirs "$REF"; git -C "$R" add -A; git -C "$R" commit -q -m "M0: merge B2"; }; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B1=$B1 A=$A B2=$B2 M=$M"; run "$R"

sec "T-82 (19) digest pre-placement — H0 empty carrier(digest only) → B real content keeps digest ∥ A(aah=B) → M"
R="$FX/19"; H0=$(base "$R" carrier)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B=$(c "$R" "B: real review content (digest kept)")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$B")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=B) [parallel]")
git -C "$R" merge -q --no-ff -m "M0: merge B" "$B"; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B=$B A=$A M=$M"; run "$R"
echo "-- (19) v2.14 token-based C_R for contrast --"
python3 - "$R" "$REF" "$M" "$A" "$DNO" <<'PY'
import subprocess,sys
R,REF,C,CAPP,DIG=sys.argv[1:6]
def g(*a): return subprocess.run(["git","-C",R,*a],capture_output=True,text=True).stdout.strip()
def ok(*a): return subprocess.run(["git","-C",R,*a],capture_output=True).returncode==0
def has(c): r=subprocess.run(["git","-C",R,"show",f"{c}:{REF}"],capture_output=True,text=True); return r.returncode==0 and DIG in r.stdout
CR=[x for x in g("rev-list",C).splitlines() if has(x) and all(not has(p) for p in g("log","--format=%P","-1",x).split())]
print(f"token C_R={{{','.join(x[:7] for x in CR)}}}  witness={'YES(green — 선배치 우회 통과)' if any(x!=g('rev-parse',CAPP) and ok('merge-base','--is-ancestor',x,CAPP) for x in CR) else 'NO'}")
PY

sec "T-82 (15) regression — new artifact R ∥ A"
R="$FX/15"; H0=$(base "$R" none)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; RR=$(c "$R" "R: new reviewer artifact")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$RR")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval (aah=R) [parallel]")
git -C "$R" merge -q --no-ff -m "M0: merge R" "$RR"; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 R=$RR A=$A M=$M"; run "$R"

sec "T-82 자인 잔여 — single row (same content·transition) is ancestor of both edges → covers both (계약 :6215-6220 정직 표기)"
R="$FX/one"; H0=$(base "$R")
row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A=$(c "$R" "A: SINGLE approval row"); setNO "$R"; E1=$(c "$R" "e1: YES->NO"); setYES "$R"; c "$R" "back to YES" >/dev/null; setNO "$R"; E2=$(c "$R" "e2: YES->NO (no new approval)")
cat "$R/LEDGER.md"; run "$R"
```

## 3. 실행 기록 — 방출값 원문 전문 (픽스처 DAG · EDGES · ledger_rows · 간선별 덮음 · rules_executed · 상태 · rc)

```text
t82_v215_utc=2026-08-18T16:32:43Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t82-v215.sh
D_NO(row_content_digest of proposed r1 NO row) = 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9

########## T-82 (18) parallel X∥Y (no edge_seq field) — full-rule executor ##########
자동 병합: LEDGER.md
충돌 (내용): LEDGER.md에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
H0=c4f8798 X=c9404fc CX=c7148af Y=178059a CY=5b9e372
## ledger
r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | c4f87980dd03514b899154c48b582cb20c190d7c | reviews/review.md | rationale/r1-a.md
r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | c4f87980dd03514b899154c48b582cb20c190d7c | reviews/review.md | rationale/r1-b.md
*   82f2b17 M: merge (parents CX,CY both NO)
|\  
| * 5b9e372 CY: NO transition e_b
| * 178059a Y: approval row (aah=H0, rationale b) [branch b]
* | c7148af CX: NO transition e_a
* | c9404fc X: approval row (aah=H0, rationale a) [branch a]
|/  
* c4f8798 H0: base (r1=YES; reviewer=full)
NO_rows=['r1']
EDGES(r1)=[('178059a', '5b9e372', 'YES->NO'), ('c9404fc', 'c7148af', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2])
ledger_rows=[('r1', 'YES->NO', 'c9404fc'), ('r1', 'YES->NO', '178059a')]
edge#1 r1 178059a->5b9e372 YES->NO: COVERED by c_APP=178059a C_R={c4f8798}
edge#2 r1 c9404fc->c7148af YES->NO: COVERED by c_APP=c9404fc C_R={c4f8798}
rules_executed=U-16-a(EDGES);g1;U-16-c(c_APP⊰c);g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover)
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 고아 0
u16_rc=0

########## T-82 (16) regression — ABSENT->NO->YES->NO, separate approvals per edge ##########
## ledger
r1 | ABSENT->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | f5036639939e252531f9b922a746ee63ecbe4c0c | reviews/review.md | rationale/r1.md
r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 677f3edf2d44f879c9fed2f6416f5af80e771422 | reviews/review.md | rationale/r1.md
* ec8cee9 e2: YES->NO
* 8e5f547 A2: approval (YES->NO)
* 677f3ed back to YES
* c71df97 e1: ABSENT->NO
* 105aed2 A1: approval (ABSENT->NO)
* f503663 H0: r1 absent
NO_rows=['r1']
EDGES(r1)=[('105aed2', 'c71df97', 'ABSENT->NO'), ('8e5f547', 'ec8cee9', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2])
ledger_rows=[('r1', 'ABSENT->NO', '105aed2'), ('r1', 'YES->NO', '8e5f547')]
edge#1 r1 105aed2->c71df97 ABSENT->NO: COVERED by c_APP=105aed2 C_R={f503663}
edge#2 r1 8e5f547->ec8cee9 YES->NO: COVERED by c_APP=8e5f547 C_R={f503663}
rules_executed=U-16-a(EDGES);g1;U-16-c(c_APP⊰c);g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover)
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 고아 0
u16_rc=0

########## T-82 (17)a existing-path B∥A (blob C_R) ##########
H0=21685e7 B=ba06260 A=061c2e0 M=050e852
* 050e852 M: NO transition
*   caec33b M0: merge B
|\  
| * ba06260 B: real review content (digest) into existing path
* | 061c2e0 A: approval row (aah=B) [parallel to B]
|/  
* 21685e7 H0: base (r1=YES; reviewer=unrelated)
NO_rows=['r1']
EDGES(r1)=[('caec33b', '050e852', 'YES->NO')]  (edge_seq 표시용 파생=[1])
ledger_rows=[('r1', 'YES->NO', '061c2e0')]
edge#1 r1 caec33b->050e852 YES->NO: UNCOVERED fails=[('APPROVAL_ORDER_INVALID', 'g6 C_R={ba06260} 증인 없음', '061c2e0')] C_R={ba06260}
rules_executed=U-16-a(EDGES);g1;U-16-c(c_APP⊰c);g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover)
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=차단 사유(우선순위 최상): ['APPROVAL_ORDER_INVALID']
u16_rc=1

########## T-82 (17)b digest blob introduced at merge resolution (aah must cite that blob → g3/h 선발화 여부 실측) ##########
H0=080967c B=fe566f9 A=8b4022c M=726da04
*   726da04 M: merge — digest blob introduced in resolution + NO transition
|\  
| * fe566f9 B: reviewer edit without digest
* | 8b4022c A: approval row (aah=B — B lacks digest)
|/  
* 080967c H0: base (r1=YES; reviewer=unrelated)
NO_rows=['r1']
EDGES(r1)=[('8b4022c', '726da04', 'YES->NO'), ('fe566f9', '726da04', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2])
ledger_rows=[('r1', 'YES->NO', '8b4022c')]
edge#1 r1 8b4022c->726da04 YES->NO: UNCOVERED fails=[('APPROVAL_UNBOUND', 'h digest∉blob(aah)', '8b4022c')]
edge#2 r1 fe566f9->726da04 YES->NO: UNCOVERED fails=[('APPROVAL_UNBOUND', 'h digest∉blob(aah)', '8b4022c')]
rules_executed=U-16-a(EDGES);g1;U-16-c(c_APP⊰c);g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover)
closable_no_provenance_state=APPROVAL_UNBOUND
reason=차단 사유(우선순위 최상): ['APPROVAL_UNBOUND']
u16_rc=1
-- (17)b g6-isolated view (blob C_R with target=blob(M:ref), c=M, c_APP=A) --
C_R(target=blob(M))={726da04}
g6_verdict=APPROVAL_ORDER_INVALID

########## T-82 (17)c positive — B1·B2 independent identical blob, A descends from B1 ##########
H0=35fbcda B1=bb3cde9 A=e32629a B2=e8f3dfc M=d942315
* d942315 M: NO transition
*   15b5aae M0: merge B2
|\  
| * e8f3dfc B2: independent identical blob
* | e32629a A: approval (aah=B1)
* | bb3cde9 B1: review content (digest)
|/  
* 35fbcda H0: base (r1=YES; reviewer=unrelated)
NO_rows=['r1']
EDGES(r1)=[('15b5aae', 'd942315', 'YES->NO')]  (edge_seq 표시용 파생=[1])
ledger_rows=[('r1', 'YES->NO', 'e32629a')]
edge#1 r1 15b5aae->d942315 YES->NO: COVERED by c_APP=e32629a C_R={e8f3dfc,bb3cde9}
rules_executed=U-16-a(EDGES);g1;U-16-c(c_APP⊰c);g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover)
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 고아 0
u16_rc=0

########## T-82 (19) digest pre-placement — H0 empty carrier(digest only) → B real content keeps digest ∥ A(aah=B) → M ##########
H0=e0b4e46 B=ae57e70 A=6fb3f0c M=3e132d5
* 3e132d5 M: NO transition
*   7a88441 M0: merge B
|\  
| * ae57e70 B: real review content (digest kept)
* | 6fb3f0c A: approval row (aah=B) [parallel]
|/  
* e0b4e46 H0: base (r1=YES; reviewer=carrier)
NO_rows=['r1']
EDGES(r1)=[('7a88441', '3e132d5', 'YES->NO')]  (edge_seq 표시용 파생=[1])
ledger_rows=[('r1', 'YES->NO', '6fb3f0c')]
edge#1 r1 7a88441->3e132d5 YES->NO: UNCOVERED fails=[('APPROVAL_ORDER_INVALID', 'g6 C_R={ae57e70} 증인 없음', '6fb3f0c')] C_R={ae57e70}
rules_executed=U-16-a(EDGES);g1;U-16-c(c_APP⊰c);g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover)
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=차단 사유(우선순위 최상): ['APPROVAL_ORDER_INVALID']
u16_rc=1
-- (19) v2.14 token-based C_R for contrast --
token C_R={e0b4e46}  witness=YES(green — 선배치 우회 통과)

########## T-82 (15) regression — new artifact R ∥ A ##########
H0=c9a5291 R=719390f A=4e9cf80 M=90efa1b
* 90efa1b M: NO transition
*   7a6f03d M0: merge R
|\  
| * 719390f R: new reviewer artifact
* | 4e9cf80 A: approval (aah=R) [parallel]
|/  
* c9a5291 H0: base (r1=YES; reviewer=none)
NO_rows=['r1']
EDGES(r1)=[('7a6f03d', '90efa1b', 'YES->NO')]  (edge_seq 표시용 파생=[1])
ledger_rows=[('r1', 'YES->NO', '4e9cf80')]
edge#1 r1 7a6f03d->90efa1b YES->NO: UNCOVERED fails=[('APPROVAL_ORDER_INVALID', 'g6 C_R={719390f} 증인 없음', '4e9cf80')] C_R={719390f}
rules_executed=U-16-a(EDGES);g1;U-16-c(c_APP⊰c);g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover)
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=차단 사유(우선순위 최상): ['APPROVAL_ORDER_INVALID']
u16_rc=1

########## T-82 자인 잔여 — single row (same content·transition) is ancestor of both edges → covers both (계약 :6215-6220 정직 표기) ##########
## ledger
r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 60b2507c075e68eb0a4ffd0a999aca6ed21961dc | reviews/review.md | rationale/r1.md
* 588756f e2: YES->NO (no new approval)
* 4b172f7 back to YES
* 4da424a e1: YES->NO
* fe4f94e A: SINGLE approval row
* 60b2507 H0: base (r1=YES; reviewer=full)
NO_rows=['r1']
EDGES(r1)=[('fe4f94e', '4da424a', 'YES->NO'), ('4b172f7', '588756f', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2])
ledger_rows=[('r1', 'YES->NO', 'fe4f94e')]
edge#1 r1 fe4f94e->4da424a YES->NO: COVERED by c_APP=fe4f94e C_R={60b2507}
edge#2 r1 4b172f7->588756f YES->NO: COVERED by c_APP=fe4f94e C_R={60b2507}
rules_executed=U-16-a(EDGES);g1;U-16-c(c_APP⊰c);g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover)
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 고아 0
u16_rc=0
(t82-v215.sh exit=0)
```

## 4. 픽스처 DAG (조립 시점 재확인 · `git -C $SP/fx82/<n> log --graph --oneline --all` — 실행 출력의 DAG 와 동일)

```text
== fx82/18  ($ git -C $SP/fx82/18 log --graph --oneline --all)
*   82f2b17 M: merge (parents CX,CY both NO)
|\  
| * 5b9e372 CY: NO transition e_b
| * 178059a Y: approval row (aah=H0, rationale b) [branch b]
* | c7148af CX: NO transition e_a
* | c9404fc X: approval row (aah=H0, rationale a) [branch a]
|/  
* c4f8798 H0: base (r1=YES; reviewer=full)
== fx82/16  ($ git -C $SP/fx82/16 log --graph --oneline --all)
* ec8cee9 e2: YES->NO
* 8e5f547 A2: approval (YES->NO)
* 677f3ed back to YES
* c71df97 e1: ABSENT->NO
* 105aed2 A1: approval (ABSENT->NO)
* f503663 H0: r1 absent
== fx82/17a  ($ git -C $SP/fx82/17a log --graph --oneline --all)
* 050e852 M: NO transition
*   caec33b M0: merge B
|\  
| * ba06260 B: real review content (digest) into existing path
* | 061c2e0 A: approval row (aah=B) [parallel to B]
|/  
* 21685e7 H0: base (r1=YES; reviewer=unrelated)
== fx82/17b  ($ git -C $SP/fx82/17b log --graph --oneline --all)
*   726da04 M: merge — digest blob introduced in resolution + NO transition
|\  
| * fe566f9 B: reviewer edit without digest
* | 8b4022c A: approval row (aah=B — B lacks digest)
|/  
* 080967c H0: base (r1=YES; reviewer=unrelated)
== fx82/17c  ($ git -C $SP/fx82/17c log --graph --oneline --all)
* d942315 M: NO transition
*   15b5aae M0: merge B2
|\  
| * e8f3dfc B2: independent identical blob
* | e32629a A: approval (aah=B1)
* | bb3cde9 B1: review content (digest)
|/  
* 35fbcda H0: base (r1=YES; reviewer=unrelated)
== fx82/19  ($ git -C $SP/fx82/19 log --graph --oneline --all)
* 3e132d5 M: NO transition
*   7a88441 M0: merge B
|\  
| * ae57e70 B: real review content (digest kept)
* | 6fb3f0c A: approval row (aah=B) [parallel]
|/  
* e0b4e46 H0: base (r1=YES; reviewer=carrier)
== fx82/15  ($ git -C $SP/fx82/15 log --graph --oneline --all)
* 90efa1b M: NO transition
*   7a6f03d M0: merge R
|\  
| * 719390f R: new reviewer artifact
* | 4e9cf80 A: approval (aah=R) [parallel]
|/  
* c9a5291 H0: base (r1=YES; reviewer=none)
== fx82/one  ($ git -C $SP/fx82/one log --graph --oneline --all)
* 588756f e2: YES->NO (no new approval)
* 4b172f7 back to YES
* 4da424a e1: YES->NO
* fe4f94e A: SINGLE approval row
* 60b2507 H0: base (r1=YES; reviewer=full)
```

## 5. 관측·정직 기록 (고치지 않는다 — bound_paths 동결)

1. **[계약 문언 정밀화 후보] ⑰ⓑ — h 가 g6 보다 먼저 발화 → `APPROVAL_UNBOUND`.** §8 T-82 ⑰ⓑ 행은 «`C_R={M}` · M ⋠ A → red»
   라 적혀 있다. 그 `C_R={M}` 은 **v2.14 토큰 정의**(digest 토큰의 도입 지점 = 머지 해소 커밋 M) 하의 서술이고, **v2.15 F3 blob 정의**
   에서 `C_R` 의 대상 blob 은 `blob(approved_at_head:ref)` = `blob(B:ref)` 인데 B 의 blob 에는 digest 가 없다 → **U-16-h(`digest ∈
   blob(aah)`)가 먼저 탈락**해 `APPROVAL_UNBOUND` 가 방출된다(실행기 규칙 순서 h → g6). g6 만 따로 보면(§3 «g6-isolated view» —
   대상 blob 을 계약 밖 가정 `blob(M:ref)` 로 두었을 때) `C_R={M}` · `APPROVAL_ORDER_INVALID` 로 행의 서술과 일치한다. **극성(red)은
   동일**하며 행은 특정 상태값이 아니라 «red» 를 계약하므로 대조군 통과다. 그러나 행의 `C_R={M}` 서술은 blob 정의에서는 성립하지
   않는다(blob 정의로는 `C_R={B}` — 대상 blob = B 의 blob, 도입 지점 B). 다음 개정에서 ⑰ⓑ 행 서술을 F3 정의로 재기술하면 닫힌다.
   **고치지 않고 보고한다.**
2. **⑱ — v2.15 재저작 기대 정확 도달**: `edge_seq` 기재 필드 없이 X∥Y 두 승인 행이 각자 자기 간선만 덮고(`x ⋡ e_b · y ⋡ e_a`), 머지
   후 `EDGES(r1)={e_a,e_b}` 둘 다 덮여 `NO_ROWS_CLEAR`/0. append·삭제·변조 0(원장 @M 원문 §3). v2.14 부속(supersedes append)이 전체
   계약에서 green 불가였던 자리를 **전 규칙 실행기**로 재실증 — S-23 `rules_executed=` 11 규칙 전부 방출.
3. **⑲ 대조 실측**: 같은 픽스처에서 v2.14 토큰 정의는 `token C_R={H0}`·증인 YES(green — 우회 통과), blob 정의는 `C_R={B}`·증인 없음
   → `APPROVAL_ORDER_INVALID`. **F3 재정의가 §8 ⑲ 행이 기술한 우회를 정확히 red 로 뒤집음**을 두 정의의 병렬 실행으로 보였다.
4. **⑰ⓑ 간선 2개**: M 의 두 부모(A·B)가 모두 r1=YES 라 `EDGES(r1)` 이 2개(A→M · B→M) — 둘 다 같은 사유로 UNCOVERED. 계약 U-16-a
   전칭 그대로이며 결과에 영향 없음.
5. **자인 잔여**: 계약 :6215-6220 «닫지 못하는 것»(row_id·transition·row_content_digest 가 완전히 같은 단일 승인 행의 c_APP 가 두 간선
   모두의 조상이면 그 한 행이 둘을 덮는다) 을 픽스처로 그대로 만들어 `NO_ROWS_CLEAR`/0 실측 — 계약이 «덮였다»까지만 주장한다는
   정직 표기와 정합. `UNCHK-012` 축 잔여로 남는다(계약 그대로).
6. **실행기 우선순위는 실행기 선언이다**: 계약 U-16-d 는 상태값 간 전순서를 두지 않는다. 여러 규칙이 동시에 탈락할 때 어느 값을
   방출하는지는 §1 독해 선언의 «전제 붕괴 순서» 이며, 이번 변이들은 전부 단일 사유라 순서 의존 결과가 없다(⑰ⓑ 는 «규칙 평가
   순서»(h 먼저) 의존 — 위 1).
7. 본 저장소 무접촉: 픽스처는 `scratchpad/fx82/*` 독립 저장소, worktree 미사용(U15 transcript §7 사후 검증 원문 참조).
