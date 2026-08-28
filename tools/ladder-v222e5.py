#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ladder-v222e5.py — U-17 (b)② «4단 사다리» 술어  [gen-2 = v2.22 에라타 5차 ⓦ]

계약 근거(`fd13ca26` docs/plans/2026-08-12-tos-phase0-completion-contract-design.md):
  :5724-5793  «4단 사다리» — 1단계 열거 집합 `E` · 2단계 완결성(두 축을 «각각» 직접) ·
              3단계 «현행» 집합 `C` = **2단 접기**: (3-1) attempt 접기[(check_suite.id, name, path)] →
              (3-2) **run 접기**[(name, path)] · 둘 다 `completed_at` 최대(동값 `id` 최대) ·
              탈락 라벨을 **구분**한다(:5763-5766) · 4단계 ∀-success
  :5638-5639  ①② 를 «동명 check-run 전수»에 path-aware 로 적용(M-3) — 원소별 «결속» 조건
  :5679-5682  `E` 는 사다리 전 구간에서 «불변» — 원소를 «배제»해 정의역을 좁히지 않는다.
              `|E| ≥ 1` ⇒ `|C| ≥ 1` 은 «요구»가 아니라 «귀결»이다(∅ 위 공허참을 구조로 차단).

  이 판(gen-2)은 **(3-2) run 접기**를 갖는다 — «재실행»(attempt)과 «재트리거»(run)를 두 라벨로
  구분해 기록한다(합치면 기록에서 구별되지 않는다·:5765-5766).  **`C` 는 단일 원소**이고,
  구조 관찰상 (3-1) 을 지워도 `C` 는 불변이다 — (3-1) 이 남는 이유는 라벨 구분뿐이다(:5767-5771).

사용:
  ladder-v222e4.py <check-runs-body.json> <runs.json|NONE> <check-name> <wf-path> <head-sha> <app-id>
    check-runs-body.json : «수집(평탄화) 결과» — `{"check_runs":[...]}` 또는 bare array 둘 다 받는다
    runs.json            : {"<run id>": {"path": ..., "head_sha": ...}} — 호출자(실행기)가 조회해 넘긴다
방출:
  LAD-*  관측 라인(전수 열거 표 · 탈락분 라벨 · |E| · |C| · 접기 단수)
  LAD-R <run id>                       — `C` 에 대응하는 run = 층 (2) 의 `R`
  RESULT=<상태값>|<사유>  또는  RESULT=LADDER_OK|<사유>   (rc 0 = LADDER_OK 만)

정직 경계 — «기록된 판단» 2건:
  (D1) 원소별 결속(①②)을 2단계 «앞»에 둔다.  계약은 이 둘의 전순서를 «규정하지 않는다»
       (결속 위배 = 8 · 미완결 = 1 이므로 순서가 상태값을 바꾼다).  결속은 «원소의 정체»에
       대한 조건이고 잘못 결속된 원소에 «완결됐는가»를 묻는 것이 무의미하므로 앞에 둔다.
       **미정 쌍으로 등재한다** — 두 위배가 동시 발생하면 이 구현은 8 을 내고 전순서 규율
       («최소 순위»)은 1 을 낼 것이다.  어느 쪽이든 «차단»이며 승인 경로는 열리지 않는다.
  (D2) `completed_at` 파싱 실패는 `PREVENTION_UNVERIFIABLE` 이다 — «비교를 수행할 수 없다»는
       조회-불가 축이고, 그 값으로 리비전을 조사할 것이 없다.
"""
import datetime
import json
import re
import sys

UV = "PREVENTION_UNVERIFIABLE"
UR = "PREVENTION_UNVERIFIED_REVISION"
OK = "LADDER_OK"
RUN_RE = re.compile(r"/actions/runs/(\d+)")


def obs(s):
    print(s)


def die(state, why):
    print("RESULT=%s|%s" % (state, why))
    sys.exit(0 if state == OK else 1)


def rid_of(cr):
    for u in (cr.get("details_url") or "", cr.get("html_url") or ""):
        m = RUN_RE.search(u)
        if m:
            return m.group(1)
    return ""


def main():
    if len(sys.argv) != 7:                                                             # [STEP0]
        die(UV, "argv %d개 (요구 7) — 술어 호출 규격 위반" % (len(sys.argv) - 1))      # [STEP0]
    body_p, runs_p, CHECK, WFPATH, HEADSHA, APPID = sys.argv[1:7]                      # [STEP0]

    try:                                                                               # [STEP0]
        raw = json.load(open(body_p, encoding="utf-8"))                                 # [STEP0]
    except Exception as e:                                                              # [STEP0]
        die(UV, "check-runs 수집 본문 파싱 실패 %r" % (e,))                             # [STEP0]
    if isinstance(raw, dict):                                                           # [STEP0]
        elems, tot = raw.get("check_runs") or [], raw.get("total_count")                # [STEP0]
    elif isinstance(raw, list):                                                         # [STEP0]
        elems, tot = raw, None                                                          # [STEP0]
    else:                                                                               # [STEP0]
        die(UV, "check-runs 본문이 객체도 배열도 아니다: %s" % type(raw).__name__)      # [STEP0]

    runs = {}                                                                           # [STEP0]
    if runs_p != "NONE":                                                                # [STEP0]
        try:                                                                            # [STEP0]
            runs = json.load(open(runs_p, encoding="utf-8"))                             # [STEP0]
        except Exception as e:                                                           # [STEP0]
            die(UV, "runs.json 파싱 실패 %r" % (e,))                                     # [STEP0]
        if not isinstance(runs, dict):                                                   # [STEP0]
            die(UV, "runs.json 이 «run id → {path, head_sha}» 객체가 아니다")            # [STEP0]

    # ── 동명 전수 (conclusion 으로 «먼저 거르지 않는다» — M-3)
    named = []                                                                          # [STEP0]
    for i, cr in enumerate(elems):                                                      # [STEP0]
        if not isinstance(cr, dict) or cr.get("name") != CHECK:                          # [STEP0]
            continue                                                                     # [STEP0]
        rid = rid_of(cr)                                                                 # [STEP0]
        rec = runs.get(rid) if rid else None                                             # [STEP0]
        named.append({                                                                   # [STEP0]
            "idx": i, "id": cr.get("id"),                                                # [STEP0]
            "suite": (cr.get("check_suite") or {}).get("id"),                            # [STEP0]
            "rid": rid, "run": rec,                                                      # [STEP0]
            "path": (rec or {}).get("path"),                                             # [STEP0]
            "run_head": (rec or {}).get("head_sha"),                                     # [STEP0]
            "name": cr.get("name"), "status": cr.get("status"),                          # [STEP0]
            "completed_at": cr.get("completed_at"),                                      # [STEP0]
            "conclusion": cr.get("conclusion"), "head_sha": cr.get("head_sha"),          # [STEP0]
            "app_id": (cr.get("app") or {}).get("id"),                                   # [STEP0]
        })                                                                               # [STEP0]

    obs("LAD-0 수집 원소 %d개 · total_count=%s · 이름 == %r 인 원소 %d개 (conclusion 으로 «먼저 거르지 않는다»·M-3)"
        % (len(elems), tot, CHECK, len(named)))
    obs("LAD-1t 동명 check-run «전수» 열거표:")
    for x in named:
        obs("  | #%-3d id=%-11s suite=%-13s run=%-11s path=%-34s status=%-12s completed_at=%-22s conclusion=%s"
            % (x["idx"], x["id"], x["suite"], x["rid"] or "∅",
               x["path"] if x["path"] is not None else "∅(미해석)",
               x["status"], x["completed_at"], x["conclusion"]))

    unres = [x for x in named if (not x["rid"]) or x["run"] is None or x["path"] is None]
    if unres:
        die(UR, "동명 check-run %d개(#%s)의 workflow run 결속 불가 — run id 부재 또는 runs.json 미해석이라 "
                "`path` 미결정 = E 구성 불가(fail-closed)"
            % (len(unres), ",".join(str(x["idx"]) for x in unres)))

    # ── 1단계 — 열거 집합 E (계약 :5643-5645)
    E = tuple(x for x in named if x["path"] == WFPATH)                                   # [STEP1]
    E_FROZEN = tuple(id(x) for x in E)                                                   # [E-IMMUT]
    obs("LAD-1 1단계 — E = «name == %r ∧ path == %r» 전수 → |E| = %d  (동명·타 path %d개 = 열거 기록만·decoy 잔여)"
        % (CHECK, WFPATH, len(E), len(named) - len(E)))                                  # [STEP1]
    if len(E) == 0:                                                                      # [STEP1]
        die(UR, "1단계 |E|=0 — 정본 path(%s) 의 동명 check-run 부재 (= evil 단독 · 케이스 ①)" % WFPATH)  # [STEP1]

    # ── 원소별 결속 ①② (M-3 path-aware) — 판단 (D1): 2단계 «앞»
    bad = []
    for x in E:
        if str(x["app_id"]) != str(APPID):
            bad.append("#%d app.id=%s≠Actions %s (위조 표면)" % (x["idx"], x["app_id"], APPID))
        if x["head_sha"] != HEADSHA:
            bad.append("#%d check-run head_sha=%s≠PR head" % (x["idx"], x["head_sha"]))
        if x["run_head"] != HEADSHA:
            bad.append("#%d run %s head_sha=%s≠PR head" % (x["idx"], x["rid"], x["run_head"]))
        try:
            x["_id"] = int(x["id"])
        except Exception:
            bad.append("#%d check-run `id`=%r 이 정수가 아니다 — 동값 tie-break 피연산자 부재" % (x["idx"], x["id"]))
    obs("LAD-1b 원소별 결속(①② · app.id/head_sha/run.head_sha/`id`) — 위배 %d건%s"
        % (len(bad), ("  " + " ; ".join(bad)) if bad else ""))
    if bad:
        die(UR, "원소별 결속 위배 — " + " ; ".join(bad))

    # ── 2단계 — 완결성.  두 축을 «각각 직접» 본다 (4차 ⓥ) · 미완결 원소를 «제외»하지 않는다
    ax_status = [x for x in E if x["status"] != "completed"]                              # [STEP2]
    ax_cat = [x for x in E if x["completed_at"] is None]                                 # [STEP2]
    obs("LAD-2 2단계 — 완결성 두 축 «각각»: 축A(status != \"completed\") %d건 · 축B(completed_at == null) %d건"
        % (len(ax_status), len(ax_cat)))                                                 # [STEP2]
    if ax_status or ax_cat:                                                              # [STEP2]
        die(UV, "2단계 완결성 불충족(전이적 차단 — «런이 끝난 뒤 재조회하라») — "         # [STEP2]
                "축A status!=completed: %s · 축B completed_at==null: %s"                 # [STEP2]
            % ([(x["idx"], x["status"]) for x in ax_status],                              # [STEP2]
               [x["idx"] for x in ax_cat]))                                              # [STEP2]

    E_RE = tuple(x for x in named if x["path"] == WFPATH)                                # [E-IMMUT]
    if tuple(id(x) for x in E_RE) != E_FROZEN:                                           # [E-IMMUT]
        die(UV, "[E-IMMUT] 2단계 후 E 가 변했다 — 정의역 분열(4차 비평 MAJOR-1)")        # [E-IMMUT]

    for x in E:
        s = x["completed_at"]
        try:
            x["_t"] = datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(datetime.timezone.utc)
        except Exception:
            die(UV, "completed_at=%r (#%d) 파싱 불가 — (completed_at, id) 전순서 결정 불가(판단 D2·fail-closed)"
                % (s, x["idx"]))

    def ordkey(x):
        return (x["_t"], x["_id"])

    # ── 3단계 — «현행» 집합 C (계약 :5666-5673 · 1단 접기)
    # [E-IMMUT] 접기 «직전»에 «지역 이름 E 자신»의 결속을 확인한다.  아래 두 canary(E_RE/E_RE2)는
    #   `named` 로부터 «재파생»하므로 `E = tuple(... )` 로 **재결속**해 정의역을 좁히는 구현을 잡지
    #   «못한다»(뮤테이션 MP-i-a-canary 로 실측 확인 — 최초 저작은 잡는다고 적었고 틀렸다).
    #   계약 «`E` 는 사다리 전 구간에서 불변 — 원소를 «배제»해 정의역을 좁히지 않는다»(:5679)의 이행.
    if tuple(id(x) for x in E) != E_FROZEN:                                              # [E-IMMUT]
        die(UV, "[E-IMMUT] 접기 «전» 지역 이름 E 가 재결속됐다 — 정의역 축소(4차 비평 MAJOR-1)")   # [E-IMMUT]
    groups = {}
    for e in E:                                       # E 를 «읽기»만 한다 — 원소를 지우지 않는다
        groups.setdefault((e["suite"], e["name"], e["path"]), []).append(e)
    surv31, drop31 = [], []
    for k in sorted(groups, key=repr):
        g = groups[k]
        w = max(g, key=ordkey)
        surv31.append(w)
        drop31 += [e for e in g if e is not w]
    for e in drop31:
        obs("LAD-3drop «대체된 attempt» #%d id=%s suite=%s run=%s completed_at=%s conclusion=%s"
            " [라벨 구분: 같은 suite 안의 «재실행» — run 층 대체는 (3-2) 소관]"
            % (e["idx"], e["id"], e["suite"], e["rid"], e["completed_at"], e["conclusion"]))
    obs("LAD-3 3단계 — (3-1) attempt 접기[(check_suite.id, name, path) · (completed_at, id) 최대]: "
        "그룹 %d개 · 생존 %d · 탈락(«대체된 attempt») %d"
        % (len(groups), len(surv31), len(drop31)))
    # ── (3-2) run 접기 — [v2.22 에라타 5차 ⓦ] 신설.  (3-1) 생존자 «전체»를 (name, path) 로 접는다.
    groups32 = {}
    for e in surv31:
        groups32.setdefault((e["name"], e["path"]), []).append(e)
    surv32, drop32 = [], []
    for k in sorted(groups32, key=repr):
        g = groups32[k]
        w = max(g, key=ordkey)
        surv32.append(w)
        drop32 += [e for e in g if e is not w]
    for e in drop32:
        obs("LAD-3drop «대체된 run» #%d id=%s suite=%s run=%s completed_at=%s conclusion=%s"
            % (e["idx"], e["id"], e["suite"], e["rid"], e["completed_at"], e["conclusion"]))
    C = surv32
    FOLD = 2
    obs("LAD-3 3단계 — (3-2) run 접기[(name, path) · (completed_at, id) 최대]: "
        "그룹 %d개 · 생존 %d · 탈락(«대체된 run») %d · **접기 단수 = %d**"
        % (len(groups32), len(surv32), len(drop32), FOLD))
    obs("LAD-3c |C| = %d  (구조: |E| ≥ 1 ⇒ |C| ≥ 1 — «요구»가 아니라 «귀결»이라 ∅ 위 공허참이 도달 불가)" % len(C))
    for x in C:
        obs("LAD-C 현행 #%d id=%s suite=%s run=%s completed_at=%s conclusion=%s"
            % (x["idx"], x["id"], x["suite"], x["rid"], x["completed_at"], x["conclusion"]))

    # ── 4단계 — ∀-success (계약 :5674-5675)
    nonok = [x for x in C if x["conclusion"] != "success"]                                # [STEP4]
    obs("LAD-4 4단계 — ∀ c ∈ C: conclusion == \"success\" · 위배 %d건" % len(nonok))      # [STEP4]
    if nonok:                                                                             # [STEP4]
        die(UR, "4단계 ∀-success 위배 — %s (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함)"  # [STEP4]
            % [(x["idx"], x["id"], x["conclusion"]) for x in nonok])                       # [STEP4]

    E_RE2 = tuple(x for x in named if x["path"] == WFPATH)                                # [E-IMMUT]
    if tuple(id(x) for x in E_RE2) != E_FROZEN:                                           # [E-IMMUT]
        die(UV, "[E-IMMUT] 4단계 후 E 가 변했다 — 정의역 분열(4차 비평 MAJOR-1)")         # [E-IMMUT]

    R, seen = [], set()
    for x in C:
        if x["rid"] not in seen:
            seen.add(x["rid"])
            R.append(x["rid"])
    for r in R:
        obs("LAD-R %s" % r)
    obs("LAD-Rn |R| = %d  (층 (2) 는 «같은 R» 위에서 평가된다 — 2차 ⓝ)" % len(R))
    die(OK, "|E|=%d ∧ 결속 위배 0 ∧ 완결성 두 축 0 ∧ 접기 단수 %d → |C|=%d ∧ ∀-success ∧ |R|=%d"
        % (len(E), FOLD, len(C), len(R)))


if __name__ == "__main__":
    main()
