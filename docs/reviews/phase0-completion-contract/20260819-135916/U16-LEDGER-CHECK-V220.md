# U16-LEDGER-CHECK-V220 — T-82 실행 증거 (계약 v2.20 동결 `3d17ea66` · 격리 스냅샷 기층)

- **비규범 부속**(non-normative). 계약·개발계획을 바꾸지 않는다. 판정 권한 없음 — 실행 «기록»이다.
- 생성 UTC: `2026-08-19T07:50:58Z` (드라이버 첫 줄 원문)
- **S-24 결속**(§1 원문): HEAD == `3d17ea66` · 계약 워킹트리 blob == `git show 3d17ea66:` blob · 개발계획 blob == 동결 blob · `3d17ea66..HEAD` 두 문서 커밋 **0** · 하니스 `sed -n '4654,4754p'` sha256 == `957bf49d…` **byte-동일**
- 실행기: `u16-full-exec-v220.py` sha256 `b90920bdc6d2120954e95273c063fbf8c959e943f0c816c2bd82f8df42045e56` (589행) — v2.19 에라타 6차 실행기(`9db15709…`)에서 **파생**(델타 §2)
- **서버 조회 0**(순수 in-repo) · 서버 쓰기·설정 변경 **0** · 픽스처는 scratchpad **독립 git 저장소**(본 저장소 무접촉·worktree 미사용)
- **판정 소비자는 이 파일의 응답을 신뢰하지 않고 스스로 실행한다** — 실행기·드라이버 원문(§8)과 sha256 을 그대로 재실행하면 같은 값이 나온다(결정적).

## 1. S-24 결속 원문

```text
s24_v220_utc=2026-08-19T07:51:32Z
① HEAD          = 3d17ea66896062140679faa895463b13a65cd510   (동결 3d17ea66 과 동일? YES)
② 계약 워킹트리 blob = 5d6044e904e9c2e74bf4abb661b3b4b47f044689
   계약 동결 blob      = 5d6044e904e9c2e74bf4abb661b3b4b47f044689   → 동일
③ 개발계획 워킹트리 blob = d00aa15ef84a9f76058403a0dd91549c9f614533
   개발계획 동결 blob      = d00aa15ef84a9f76058403a0dd91549c9f614533   → 동일
④ 3d17ea66..HEAD 두 문서 커밋 = 0건
   3d17ea66..HEAD 전체 커밋   = 0건
⑤ 계약 행수 = 7494 · 개발계획 행수 = 579
⑥ 하니스 §12.3.4-R 블록 (계약 :4654-4754 · 101행) sha256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
   계약 리터럴                                   = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d   → 일치
   블록 경계 원문: #!/usr/bin/env bash
                   emit ENTRY_OK "R-0~R-7 전부 기대와 일치"
⑦ 동결 blob 에서 같은 범위 추출 → sha256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d (byte-동일? YES)
⑧ 워킹트리 상태 (두 문서 한정): 0건 변경
⑨ 본 저장소 [PARENTS-UNTRUSTED] 관측: git replace -l=[] · info/grafts=ABSENT · is_shallow=false
⑩ 픽스처 격리: 본 저장소 밖 독립 저장소 = 9개 · worktree = 3 (본 저장소 worktree 목록)
```

주: ⑩ 의 `worktree = 3` 은 **본 저장소에 이미 존재하던 타 세션 worktree**(`.worktrees/futures-risk-hardening-design` · `orca/workspaces/...`)이며 **이 증거는 worktree 를 만들지 않았다** — 이 회차 픽스처 9개는 전부 scratchpad 독립 저장소다.

## 2. 실행기 파생 — v2.19 에라타 6차 → v2.20 (델타 1건)

v2.20 심판 처분 중 U-16 축에 코드 델타가 있는 것은 **#3 격리 스냅샷 기층** 하나다. #2(U-16-a2 «g6 전 항» 전칭)는 이 실행기가 **이미 g6 을 실행**하므로 코드 델타 0이고, 대조군(`u16-g6omit-v220.py`)이 «g6 생략 소비자»의 실패를 실증한다(§3 ⑮).

```diff
2c2,13
< """U-16 «전 규칙» 손 실행기 — v2.19 에라타 6차 (계약 359f5bc5 §13.6.5
---
> """U-16 «전 규칙» 손 실행기 — v2.20 동결 3d17ea66 (계약 §13.6.5)
> 
> v2.19 에라타 6차 실행기(359f5bc5·sha256 9db15709...) 에서 파생 — 델타는 **v2.20 심판 처분 #3 1건**뿐이다:
>   [#3 격리 스냅샷 기층 — 계약 :7098-7124] 조상성·부모·원장 blob 을 소비하는 «모든» 판정을
>   진입 시점 HEAD 의 «격리 스냅샷»(`git clone --no-local --no-hardlinks` + `GIT_NO_REPLACE_OBJECTS=1`)
>   «안에서만» 수행한다.  스냅샷 생성 실패는 **fail-closed**(정직 경계 (a)), 스냅샷 «안»의 청정성
>   (`replace -l` 공집합 ∧ grafts 부재 ∧ ㉠ 재파생==%P)은 **canary** 로 방출한다(정직 경계 (b)).
>   #2(U-16-a2 g6 «전 항» 전칭)는 이 실행기가 **이미 g6 을 실행**하므로 코드 델타 0 —
>   대조군 파일(`u16-g6omit-v220.py`)이 «g6 생략 소비자»를 실증한다.
> 
> (구 헤더 — v2.19 계보 보존)
> U-16 «전 규칙» 손 실행기 — v2.19 에라타 6차 (계약 359f5bc5 §13.6.5
75a87,88
> CANARY_SHALLOW_LOCAL = True            # [E12 관할] 스냅샷 canary 의 ㉠ 불일치 중 얕은 «경계» 귀속분은 국소 (대조군 E: False = 계약 :7124 «항상 성립» 문언의 «문자» 구현)
> SNAPSHOT_BASE = True                   # [v2.20 #3] 격리 스냅샷 기층 (대조군 파일: False — 원 저장소 직접 소비)
288a302,373
> 
> 
> 
> # ── [v2.20 — 심판 #3] 격리 스냅샷 기층 (계약 3d17ea66 :7098-7124) ────────────────────────────
> def snapshot(origin):
>     """진입 시점 HEAD 를 «격리 스냅샷»으로 고정한다 — 단일 방법: git clone --no-local --no-hardlinks.
> 
>     극성(계약): grafts 는 직렬화되지 않아 전송으로 따라오지 않고, replace ref 는 기본 refspec 이
>     가져오지 않는다.  커밋 객체는 내용주소라 스냅샷의 부모 줄은 원본과 바이트 동일 = «참 그래프».
>     정직 경계 (a) 원본 graft 가 참 부모를 도달 불가로 만들면 clone «생성»이 실패한다(fail-closed).
>              (b) 스냅샷 «안»의 ㉡·㉠ 을 canary 로 재확인한다(--local 폴백·번들 오용 적발).
>     """
>     import os as _os, subprocess as _sp, tempfile as _tf
> 
>     def og(*a):
>         return _sp.run(["git", "-C", origin, *a], capture_output=True, text=True).stdout.strip()
> 
>     repl0 = [x.split()[0] for x in og("replace", "-l").splitlines() if x.strip()]
>     gp0 = og("rev-parse", "--git-path", "info/grafts")
>     if gp0 and not _os.path.isabs(gp0):
>         gp0 = _os.path.join(og("rev-parse", "--show-toplevel") or origin, gp0)
>     print("[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=%s · %s=%s"
>           % ([x[:7] for x in repl0], gp0, "present" if _os.path.isfile(gp0) else "ABSENT"))
>     head = og("rev-parse", "HEAD")
>     snap = _os.path.join(_tf.mkdtemp(), "snap")
>     env = dict(_os.environ); env["GIT_NO_REPLACE_OBJECTS"] = "1"
>     print("[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks %s %s" % (origin, snap))
>     r = _sp.run(["git", "clone", "--quiet", "--no-local", "--no-hardlinks", origin, snap],
>                 capture_output=True, text=True, env=env)
>     print("[격리 스냅샷] clone rc=%d %s" % (r.returncode, (r.stderr or "").strip()[:300]))
>     if r.returncode != 0:
>         emit("PROVENANCE_UNVERIFIABLE",
>              "[격리 스냅샷] clone 실패(rc=%d) — 정직 경계 (a): 원본 graft 가 참 부모를 도달 불가로 만들면 "
>              "스냅샷 «생성»이 실패한다(거짓 통과 없음·fail-closed): %s" % (r.returncode, (r.stderr or "").strip()[:200]), [])
>     def sg(*a):
>         return _sp.run(["git", "-C", snap, *a], capture_output=True, text=True)
>     if sg("cat-file", "-e", head + "^{commit}").returncode != 0:
>         emit("PROVENANCE_UNVERIFIABLE", "[격리 스냅샷] 진입 HEAD(%s) 가 스냅샷에 부재 — 핀 실패 fail-closed" % head[:7], [])
>     sg("checkout", "--quiet", "--detach", head)
>     replc = [x.split()[0] for x in sg("replace", "-l").stdout.splitlines() if x.strip()]
>     gpc = sg("rev-parse", "--git-path", "info/grafts").stdout.strip()
>     if gpc and not _os.path.isabs(gpc):
>         gpc = _os.path.join(sg("rev-parse", "--show-toplevel").stdout.strip() or snap, gpc)
>     commits = sg("rev-list", "--all").stdout.split()
>     # [E12 관할] ㉢ 먼저 — 얕은 «경계» 커밋은 그 자체로 ㉠ 불일치(cat-file 부모 有 vs %P ∅)를 만든다(계약 :7148-7152).
>     # 경계로 «특정»되는 불일치는 국소 귀속하고, «남는» 것만 기층 오염(전역)으로 올린다.
>     shp = sg("rev-parse", "--git-path", "shallow").stdout.strip()
>     if shp and not _os.path.isabs(shp):
>         shp = _os.path.join(sg("rev-parse", "--show-toplevel").stdout.strip() or snap, shp)
>     try:
>         shallow_set = set(open(shp).read().split())
>     except Exception:
>         shallow_set = set()
>     mism = 0; local = 0
>     for x in commits:
>         tp = sorted(l.split()[1] for l in sg("--no-replace-objects", "cat-file", "commit", x).stdout.split("\n\n")[0].splitlines() if l.startswith("parent "))
>         ap = sorted(_sp.run(["git", "-C", snap, "log", "--format=%P", "-1", x], capture_output=True, text=True).stdout.split())
>         if tp != ap:
>             if CANARY_SHALLOW_LOCAL and x in shallow_set:
>                 local += 1
>             else:
>                 mism += 1
>     print("[격리 스냅샷] canary(스냅샷 «안»): HEAD=%s · replace -l=%s · %s=%s · is_shallow=%s · ㉠ 불일치 전역 %d건 (㉢ 얕은 경계 국소 귀속 %d건 · E12 관할) / 커밋 %d개"
>           % (sg("rev-parse", "HEAD").stdout.strip()[:7], [x[:7] for x in replc], gpc,
>              "present" if _os.path.isfile(gpc) else "ABSENT",
>              sg("rev-parse", "--is-shallow-repository").stdout.strip(), mism, local, len(commits)))
>     if replc or _os.path.isfile(gpc) or mism:
>         emit("PROVENANCE_UNVERIFIABLE",
>              "[격리 스냅샷 canary] 기층 오염 — replace=%s grafts=%s ㉠불일치=%d (정직 경계 (b): --local 폴백·번들 오용 적발)"
>              % (replc, _os.path.isfile(gpc), mism), [])
>     _os.environ["GIT_NO_REPLACE_OBJECTS"] = "1"
>     return snap
293c378,379
<     R = sys.argv[1]
---
>     ORIGIN = sys.argv[1]
>     R = snapshot(ORIGIN) if SNAPSHOT_BASE else ORIGIN   # [v2.20 #3] 격리 스냅샷 기층 (대조군 파일은 이 한 줄이 다르다)
```

### 2-1. 대조군 — 판정 실행기 대비 «한 축»만 다르다

| 파일 | sha256 | diff 행수 | 바꾼 축 |
| --- | --- | --- | --- |
| `u16-nosnap-v220.py` | `9b64168c343824685979bca9cc2e97fc7ff566df0f8a1197f67eb8128d85078b` | — | `SNAPSHOT_BASE=False` — 격리 스냅샷 «없이» 원 저장소 직접 소비 (v2.19 거동) · ⑳ⓒ |
| `u16-g6omit-v220.py` | `6e9662e2ad10f4bbda75d5a77f3bd4d11d950ae95e5ab7387531d362a2531a7b` | — | `g6` 생략 — U-16-a2 전칭을 «(g1~g5)» 닫힌 열거로 읽은 소비자 · ⑮ |
| `u16-edgeseq-v220.py` | `c42d910d654f97b774bd565580b8e901e07f3465856cfdb5e301c0018d418903` | — | 폐지된 `edge_seq` «기재값 ≠ 파생값 = MALFORMED» 소비 (v2.13 거동) · ⑯⑱ |
| `u16-order-ctrl-g1first-v220.py` | `8077b7c2d1cf13b20be689b803c6fc2e8d2f14187cf7e77b5258c57d41ed911e` | — | `EVAL_ORDER="g1-first"` — U-16-d 를 «g1·g4 먼저»로 문자 구현 · ⑳ⓑ |
| `u16-canary-literal-v220.py` | `5b5f7bc9ee949f0393175fa3a73e27da2854562fb62ee4d5912307d3fa6b3f46` | — | `CANARY_SHALLOW_LOCAL=False` — 계약 :7124 «㉠==%P 는 항상 성립하는 canary» 문언의 «문자» 구현 · ⑳ⓑ 관측 |

```diff
=== nosnap
88c88
< SNAPSHOT_BASE = True                   # [v2.20 #3] 격리 스냅샷 기층 (대조군 파일: False — 원 저장소 직접 소비)
---
> SNAPSHOT_BASE = False                  # [대조군 A — 판정용 아님] 격리 스냅샷 «없이» 원 저장소에서 직접 소비 (v2.19 거동)
=== g6omit
93c93
<                   "g6(C_R blob·∃witness)", "h", "MALFORMED(orphan/double-cover)",
---
>                   "h", "MALFORMED(orphan/double-cover)",
519,521c519
<         elif capp1 and not CR:
<             pre.append(("PROVENANCE_UNVERIFIABLE",
<                         "g6 C_R=∅" + (" [SHALLOW] 경계 커밋 %s 로 확정 불가" % [x[:7] for x in CRB] if CRB else "")))
---
>         # [대조군 B] g6 파생 선-검사(C_R=∅)도 함께 사라진다 — g6 을 «전 항»에서 뺀 소비자는 C_R 을 계산하지 않는다
545,547c543,544
<         if not any(strict_anc(x, capp1) for x in CR):
<             return ("APPROVAL_ORDER_INVALID",
<                     "g6 C_R={%s} 에 c_APP 진 조상 증인 없음" % ",".join(x[:7] for x in CR))
---
>         # [대조군 B — 판정용 아님] g6 «생략»: U-16-a2 전칭을 «(g1~g5)» 닫힌 열거로 읽은 소비자.
>         # (v2.20 심판 #2 가 지목한 그 독해 — «리뷰를 보고 승인했다»의 소비가 사라진다)
=== edgeseq
229c229,230
<                             reviewer_ref=f[4], rationale_ref=f[5], raw=l.strip()))
---
>                             reviewer_ref=f[4], rationale_ref=f[5], raw=l.strip(),
>                             seq=(f[6] if len(f) >= 7 else None)))   # [대조군 C] 폐지된 edge_seq «기재» 열
552a554,558
>             # [대조군 C — 판정용 아님] 폐지된 `edge_seq` «기재값 ≠ 파생값 = MALFORMED» 소비 (v2.13 거동·U-16-b #2 마감 «전»)
>             for _a in cands:
>                 if _a.get("seq") != str(i):
>                     add(f"edge#{i}[{rid}]", "APPROVAL_MALFORMED",
>                         f"edge_seq 기재값({_a.get('seq')}) ≠ 파생 순번({i}) — 폐지 필드 소비")
=== order-ctrl-g1first
89c89
< EVAL_ORDER = "precheck-first"          # 대조군 파일: "g1-first"  (계약 U-16-d ① 선-검사 → ② g-단락 · [E6] 국소)
---
> EVAL_ORDER = "g1-first"        # [대조군 D — 판정용 아님] 계약 U-16-d 를 «g1·g4 먼저»로 문자 구현 (⑳ⓑ 판별력)          # 대조군 파일: "g1-first"  (계약 U-16-d ① 선-검사 → ② g-단락 · [E6] 국소)
=== canary-literal
87c87
< CANARY_SHALLOW_LOCAL = True            # [E12 관할] 스냅샷 canary 의 ㉠ 불일치 중 얕은 «경계» 귀속분은 국소 (대조군 E: False = 계약 :7124 «항상 성립» 문언의 «문자» 구현)
---
> CANARY_SHALLOW_LOCAL = False            # [E12 관할] 스냅샷 canary 의 ㉠ 불일치 중 얕은 «경계» 귀속분은 국소 (대조군 E: False = 계약 :7124 «항상 성립» 문언의 «문자» 구현)
```

## 3. 기대 / 실측 표 (전건)

| 케이스 | 계약 기대 | 실측 상태값 | rc | 일치 |
| --- | --- | --- | --- | --- |
| **⑮** R∥A merge (신규 아티팩트) | `APPROVAL_ORDER_INVALID`(11) + rc≠0 | `APPROVAL_ORDER_INVALID` | 1 | ✅ |
| ⑮ 대조군 — **g6 생략** 소비자 | green 이면 **실패 실증** | **`NO_ROWS_CLEAR`** | **0** | ✅ 실패 실증 |
| **⑯** 선형 반복(현행 스키마·`edge_seq` 미기재) | `NO_ROWS_CLEAR` + rc=0 | `NO_ROWS_CLEAR` | 0 | ✅ |
| ⑯ 대조군 — 폐지 `edge_seq` 기재값 소비 | MALFORMED(영구 차단) = **롤백 결함** | **`APPROVAL_MALFORMED`** | 1 | ✅ 판별력 |
| **⑱** 병렬 반복(서로 다른 승인 행) | `NO_ROWS_CLEAR` + rc=0 | `NO_ROWS_CLEAR` | 0 | ✅ |
| ⑱ 대조군 — 폐지 `edge_seq` 기재값 소비 | MALFORMED | **`APPROVAL_MALFORMED`** | 1 | ✅ 판별력 |
| ⑱-2 «별개 `row_id`» 문언 리터럴 (관측) | (계약 E4: 다른 row_id 는 구조상 덮지 못함) | `APPROVAL_MALFORMED`(고아) | 1 | 관측 일치 |
| **⑳ⓐ** 동일 승인 행 형제 독립 도입 | `APPROVAL_MALFORMED`(3) + rc≠0 (`|c_APP|=2`) | `APPROVAL_MALFORMED` | 1 | ✅ |
| ⑳ⓐ 대조군 — «복수면 사전순 최소»(v2.15 부속) | 통과하면 F5 «회피» 실증 | **`NO_ROWS_CLEAR`** | **0** | ✅ 실패 실증 |
| **⑳ⓑ** 얕은 클론 선-검사 corner | `PROVENANCE_UNVERIFIABLE`(2) + rc≠0 | `PROVENANCE_UNVERIFIABLE` (`|c_APP|=0`) | 1 | ✅ |
| ⑳ⓑ 대조군 — «g1·g4 먼저» 문자 구현 | `APPROVAL_MALFORMED`(3) 이면 실패 | **`APPROVAL_MALFORMED`** | 1 | ✅ 판별력 |
| ⑳ⓑ 관측 대조 — canary 문언 «문자» 구현 | (계약 :7124 vs :7148 E12 충돌 관측) | `PROVENANCE_UNVERIFIABLE` — 사유가 «기층 오염»으로 바뀜 | 1 | 극성 동일·사유 상이 → **문언 결함 후보 N-1** |
| **⑳ⓒ** 부모신뢰 TOCTOU · 스냅샷 «없는» 소비자 | 뒤집히면 실패 | **`NO_ROWS_CLEAR`** | **0** | ✅ fail-open 재현 |
| ⑳ⓒ 스냅샷 «기층» 판정 실행기 (같은 훅) | 구조대로 유지 | `PROVENANCE_UNVERIFIABLE` | 1 | ✅ 불변 |
| ⑳ⓒ 정직 이력(훅 없음) 기준선 | — | `PROVENANCE_UNVERIFIABLE` | 1 | ✅ (b)==(c) 동일 |
| ⑳ⓒ(d) 정직 경계 (a) — 원본 grafts 가 참 부모 고아화 | 스냅샷 «생성» 실패 = fail-closed | `PROVENANCE_UNVERIFIABLE` (`clone rc=128`) | 1 | ✅ |
| 회귀 ⑰ⓐ 기존-경로 B∥A | `APPROVAL_ORDER_INVALID`(11) | `APPROVAL_ORDER_INVALID` | 1 | ✅ |
| 회귀 ⑰ⓑ 머지 해소 digest 도입 | `APPROVAL_UNBOUND`(10) [E2] | `APPROVAL_UNBOUND` | 1 | ✅ |
| 회귀 ⑰ⓒ 양성 (B1·B2 독립·A ⊐ B1) | `NO_ROWS_CLEAR` | `NO_ROWS_CLEAR` | 0 | ✅ |
| 회귀 ⑲ digest 선배치 | `APPROVAL_ORDER_INVALID`(11) | `APPROVAL_ORDER_INVALID` | 1 | ✅ |
| 회귀 ⑪ transition 명세 불일치 | `APPROVAL_MALFORMED`(3) | `APPROVAL_MALFORMED` | 1 | ✅ |
| 자인 잔여 — 단일 행이 두 간선을 덮음 | 계약이 «닫지 못한다»고 적은 자리 | `NO_ROWS_CLEAR` | 0 | 계약 표기대로 |

**S-23**: 판정 실행기의 모든 실행에서 `rules_missing=∅` 이다(전 규칙 실행). 예외는 **선-검사에서 조기 방출된 두 경우**(⑳ⓑ 얕은 클론의 대조군 E · ⑳ⓒ(d) clone 실패) — 둘 다 **green 이 아니라 차단**이므로 S-23 의 «차집합이 비지 않으면 green 대신 PARTIAL» 요건과 충돌하지 않는다(원문 §7).

## 4. 격리 스냅샷 기층 — canary 와 정직 경계

모든 판정 실행이 진입 시점 HEAD 에서 `git clone --no-local --no-hardlinks`(+`GIT_NO_REPLACE_OBJECTS=1`) 스냅샷을 만들고 **그 안에서만** 조상성·부모·원장 blob 을 소비한다. 각 실행의 canary 원문(발췌):

```text
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6e29849 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpduesot9m/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 7개
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=96b76a7 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpg8674ann/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 7개
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6318c95 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp9d4cuvzg/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 5개
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6318c95 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp9lw_co4c/snap/.git/info/grafts=ABSENT · is_shallow=true · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 1건 · E12 관할) / 커밋 1개
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6318c95 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp4gxti7zy/snap/.git/info/grafts=ABSENT · is_shallow=true · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 1건 · E12 관할) / 커밋 1개
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6318c95 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp7y4bw0ik/snap/.git/info/grafts=ABSENT · is_shallow=true · ㉠ 불일치 전역 1건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 1개
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=664b47a · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp5o1l_coq/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
```

- **정직 경계 (a)** — 원본 grafts 가 참 부모를 도달 불가로 만들면 `clone rc=128`(`fetch-pack` 실패)로 **스냅샷 생성이 실패**하고 실행기는 `PROVENANCE_UNVERIFIABLE` 로 **fail-closed** 한다(§3 ⑳ⓒ(d) · 원문 §7). 「거짓 조상성」이 아니라 「생성 실패」다.
- **정직 경계 (b)** — 스냅샷 «안»의 `replace -l` 공집합 ∧ grafts 부재 ∧ ㉠(`cat-file` 부모 == `%P`)를 **canary** 로 재확인한다. **[E12 관할]** ㉠ 불일치 중 «얕은 경계»로 특정되는 것은 국소 귀속하고 «남는» 것만 기층 오염으로 올린다 — 이 국소화가 없으면 얕은 원본에서 canary 가 오발화한다(§9 N-1).
- **정직 경계 (c)** — 판정 소비자 «자신의 환경 위조»는 계약 밖. 이 증거도 그 층은 닫지 않는다.

## 5. ⑳ⓒ — 부모신뢰 TOCTOU (SIMULATED 훅 interleaving)

훅은 **조상성 «소비»(`rev-list` · `merge-base --is-ancestor`) 호출 중에만** 후보 «밖» 커밋(`H0`)의 부모를 `grafts` 로 재작성하고 **호출 직후 제거**한다. ㉠ 의 교차검사(`log --format=%P` · `cat-file`)는 **건드리지 않는다** — 관측이 참을 보게 두고 소비만 재작성하는 것이 계약이 지목한 TOCTOU 창이다.

```text

########## [v2.20 #3] T-82 ⑳ⓒ 부모신뢰 TOCTOU — SIMULATED 훅 interleaving (조상성 조회 «중»에만 graft 설치·조회 후 제거) ##########
  S0=2f7dbe2 H0=249202a(재작성 대상·후보 밖) R=51703e2 A=b3bbfeb CN=57c8e7e M=HEAD=412fe75
  graft 줄(설치될 내용) = 249202a9470794be24d957ece32d04fd34fc974e 2f7dbe2602bf88e804928fd6e36bea94179739c3 51703e27bad9b7cf11a91524c5d2578fc165edab
  *   412fe75 M: merge reviewer branch
  |\  
  | * 51703e2 R: reviewer artifact (digest)
  * | 57c8e7e CN: NO transition
  * | b3bbfeb A: approval row (aah=R)
  * | 249202a H0: unrelated only (리뷰어 blob 없음·원장 행 없음) ⇒ 후보 우주 «밖»
  |/  
  * 2f7dbe2 S0: register/ledger-header/rationale (리뷰어 경로 없음)
  shim sha256 = aae8890c36e6d58a3cc76adf0e34c934e2e63871956e9dc9abd5f79d8bbab25a · 실 git = /usr/local/bin/git
  훅 «밖» 관측: grafts 파일 = ABSENT (㉡ 은 관측 시점에 항상 부재를 본다)
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
  훅 «안» 효과: is-ancestor(R,CN) = rc 0  (0 = 조상성 뒤집힘) · 훅 밖 = rc 1
  훅 실행 «후» grafts = ABSENT
```

| 실행 | 격리 스냅샷 | 상태값 | rc | 판독 |
| --- | --- | --- | --- | --- |
| (a) 대조군 A + 훅 | **없음** | **`NO_ROWS_CLEAR`** | **0** | ㉡ 은 관측 시점에 grafts 부재를 보고 ㉠ 도 침묵 — 그런데 조상성이 뒤집혀 **green = fail-open** |
| (b) 판정 실행기 + 같은 훅 | 있음 | `PROVENANCE_UNVERIFIABLE` | 1 | 스냅샷 조상성 불변 — 창이 «구조»로 닫힘 |
| (c) 판정 실행기 · 훅 없음 | 있음 | `PROVENANCE_UNVERIFIABLE` | 1 | (b)==(c) — 훅이 판정을 움직이지 못한다 |

## 6. U-17 축 스냅샷 적용 — `D`·`P` 조상성 (1픽스처)

```text

########## [v2.20 #3] U-17 축 스냅샷 적용 — D·P 조상성도 스냅샷 «안»에서 소비한다 (같은 interleaving 훅) ##########
  seed=778db30 W=dcbe0e6(후보 밖·재작성 대상) d=fb4b5a9 P=8ddcd02 HEAD=de6f2cc
  graft 줄 = dcbe0e6b88c93af8deb184cf5337d0527ce69179 778db309f9f3099d0f2ef448f4d0c5ec58612c78 8ddcd027d748bb71222009b995632b47ddec770f
  정직 이력: is-ancestor(P,d) rc=1  (1 = P ⋠ d = LATE 진실)
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
  graft 설치 후(원 저장소): is-ancestor(P,d) rc=0 · --no-replace-objects 하 rc=0  (K-4: grafts 는 무력화로 안 꺼진다)
$ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks <origin> <snap>
  | 힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
  | 힌트: 버전에서 제거될 예정입니다.
  | 힌트: 
  | 힌트: 그래프트를 레퍼런스로 전환하려면
  | 힌트: "git replace --convert-graft-file" 명령을
  | 힌트: 사용하십시오.
  | 힌트: 
  | 힌트: 이 메시지를 보지 않으려면
  | 힌트: "git config advice.graftFileDeprecated false"
  | 힌트: 명령을 사용하십시오
  | remote: 힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃        
  | remote: 힌트: 버전에서 제거될 예정입니다.        
  | remote: 힌트:         
  | remote: 힌트: 그래프트를 레퍼런스로 전환하려면        
  | remote: 힌트: "git replace --convert-graft-file" 명령을        
  | remote: 힌트: 사용하십시오.        
  | remote: 힌트:         
  | remote: 힌트: 이 메시지를 보지 않으려면        
  | remote: 힌트: "git config advice.graftFileDeprecated false"        
  | remote: 힌트: 명령을 사용하십시오        
  clone rc=0
  스냅샷 canary: replace -l=[] · grafts=ABSENT · is_shallow=false
  스냅샷 조상성: is-ancestor(P,d) rc=1  (1 = 참 조상성 = LATE 유지 · 원본 graft 미전파)
  ㉠ 대조(스냅샷): 불일치 0건
```

→ 원 저장소에서는 graft 가 `P ⋠ d` 를 뒤집고(`rc 1 → 0`) **`--no-replace-objects` 로도 꺼지지 않는다**(K-4). 스냅샷에서는 `rc=1`(참 조상성)이 유지되고 canary 는 깨끗하다.

## 7. 실행 기록 (stdout 전문 · rc 포함)

### 7-1. `bash t82v220.sh` (821행)

```text
t82v220_utc=2026-08-19T07:50:58Z
sha256(u16-full-exec-v220.py)=b90920bdc6d2120954e95273c063fbf8c959e943f0c816c2bd82f8df42045e56
sha256(u16-order-ctrl-g1first-v220.py)=8077b7c2d1cf13b20be689b803c6fc2e8d2f14187cf7e77b5258c57d41ed911e
sha256(u16-g6omit-v220.py)=6e9662e2ad10f4bbda75d5a77f3bd4d11d950ae95e5ab7387531d362a2531a7b
sha256(u16-edgeseq-v220.py)=c42d910d654f97b774bd565580b8e901e07f3465856cfdb5e301c0018d418903
sha256(u16-nosnap-v220.py)=9b64168c343824685979bca9cc2e97fc7ff566df0f8a1197f67eb8128d85078b
sha256(u16-canary-literal-v220.py)=5b5f7bc9ee949f0393175fa3a73e27da2854562fb62ee4d5912307d3fa6b3f46
sha256(u16-full-exec-v215.py)=a0201149b794de7ae438d05e035246d35598a1173ecd5481e1217e647f38e5d0
-- 대조군 파일 diff (판정 실행기 대비 «한 축»만 다름) --
  u16-order-ctrl-g1first-v220.py: 2 행
  u16-g6omit-v220.py: 11 행
  u16-edgeseq-v220.py: 8 행
  u16-nosnap-v220.py: 2 행
  u16-canary-literal-v220.py: 2 행
git version = git version 2.38.0
D_NO(row_content_digest of proposed r1 NO row) = 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9
계약 U-16-d 전순서: 1 CONSUMER_ABSENT · 2 PROVENANCE_UNVERIFIABLE · 3 APPROVAL_MALFORMED · 4 APPROVAL_MISSING · 5 SAME_COMMIT · 6 AFTER · 7 CONTENT_DRIFT · 8 HEAD_INVALID · 9 ROW_MUTATED · 10 UNBOUND · 11 ORDER_INVALID · 12 NO_ROWS_CLEAR

########## T-82 ⑱-1 [현행 스키마] 병렬 반복 이력(양성) — ABSENT->NO->YES->NO 두 간선을 «서로 다른 승인 행»이 각각 덮고, 두 도입이 형제 브랜치 → merge · edge_seq 기재 없음 ⇒ NO_ROWS_CLEAR ##########
자동 병합: LEDGER.md
충돌 (내용): LEDGER.md에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
H0=bcec7a2 A1=c2b31ec A2=3bb7f4f MA=1a7ed00 e1=059bb15 e2=6e29849
-- LEDGER@HEAD --
  | ## ledger
  | r1 | ABSENT->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | bcec7a2 | reviews/review.md | rationale/r1-a.md
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | bcec7a2 | reviews/review.md | rationale/r1-b.md
-- g5 구 승인 행 불변 확인: A1·A2 도입 시점 행 (HEAD 행과 byte 동일이어야 한다) --
  A1| r1 | ABSENT->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | bcec7a2 | reviews/review.md | rationale/r1-a.md
  A2| r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | bcec7a2 | reviews/review.md | rationale/r1-b.md
  * 6e29849 e2: YES->NO
  * 014cae8 back to YES
  * 059bb15 e1: ABSENT->NO
  *   1a7ed00 MA: merge sibling approval introductions (union)
  |\  
  | * 3bb7f4f A2: approval row (YES->NO, rationale b) [branch b]
  * | c2b31ec A1: approval row (ABSENT->NO, rationale a) [branch a]
  |/  
  * bcec7a2 H0: r1 absent (reviewer artifact with digest)
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/18-1/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/18-1 /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpduesot9m/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6e29849 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpduesot9m/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 7개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpduesot9m/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpduesot9m/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=6e29849 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('1a7ed00', '059bb15', 'ABSENT->NO'), ('014cae8', '6e29849', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'ABSENT->NO', '|c_APP|=1', ['c2b31ec']), ('r1', 'YES->NO', '|c_APP|=1', ['3bb7f4f'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/ABSENT->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
  row r1/YES->NO raw#1: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 1a7ed00->059bb15 ABSENT->NO]: COVERED by c_APP=c2b31ec C_R={bcec7a2}
  · edge#2[r1 014cae8->6e29849 YES->NO]: COVERED by c_APP=3bb7f4f C_R={bcec7a2}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## T-82 ⑱-2 [문언 리터럴 «별개 row_id»] 같은 반복 이력을 «서로 다른 row_id» 승인 행으로 덮으면? (관측 보고 대상) ##########
자동 병합: LEDGER.md
충돌 (내용): LEDGER.md에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
  | ## ledger
  | r1 | ABSENT->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 45e1b21 | reviews/review.md | rationale/r1.md
  | r1b | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 45e1b21 | reviews/review.md | rationale/r1.md
  * 96b76a7 e2: YES->NO
  * 7a36720 back to YES
  * 79b3c78 e1: ABSENT->NO
  *   c570d23 MB: merge sibling approvals
  |\  
  | * cb75f42 B2: approval row_id=r1b (문언 «별개 row_id»)
  * | 3bb858c B1: approval row_id=r1
  |/  
  * 45e1b21 H0: r1 absent
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/18-2/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/18-2 /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpg8674ann/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=96b76a7 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpg8674ann/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 7개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpg8674ann/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpg8674ann/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=96b76a7 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('c570d23', '79b3c78', 'ABSENT->NO'), ('7a36720', '96b76a7', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'ABSENT->NO', '|c_APP|=1', ['3bb858c']), ('r1b', 'YES->NO', '|c_APP|=1', ['cb75f42'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/ABSENT->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
  row r1b/YES->NO raw#1: |c_APP|=1 g4_bad=False g2_bad=True 대응간선=0 row_id간선=0
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1b/YES->NO]: APPROVAL_MALFORMED(3) — 고아 — 대응 간선 0 (row_id 간선 0 · g1 transition 전건 불일치)
  · edge#1[r1 c570d23->79b3c78 ABSENT->NO]: COVERED by c_APP=3bb858c C_R={45e1b21}
  · edge#2[r1 7a36720->96b76a7 YES->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1b/YES->NO] — 고아 — 대응 간선 0 (row_id 간선 0 · g1 transition 전건 불일치) · 발화 전체=['APPROVAL_MALFORMED', 'APPROVAL_MISSING']
u16_rc=1

########## T-82 ⑳ⓐ 동일 승인 행 형제 독립 도입 → |c_APP(a)|=2 ⇒ APPROVAL_MALFORMED(3) + rc≠0 ##########
H0=58d2844 X=9218768(=9218768ded5a8e60b4782819e511fe2ce2694118) CN=b8732f6 Y=c4d5651(=c4d56517c74eeeda50a77675b5ec99d493eb4fdc)  [사전순: X < Y — 사전순 최소 = 조상 도입]
-- LEDGER@HEAD (형제 두 도입이 «같은 한 줄» 로 합쳐진다) --
  | ## ledger
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 58d2844 | reviews/review.md | rationale/r1.md
  *   6318c95 M: merge sibling identical approval introduction
  |\  
  | * c4d5651 Y: approval row A (byte-identical) [branch y nonce=3]
  * | b8732f6 CN: NO transition (child of X)
  * | 9218768 X: approval row A [branch x nonce=3]
  |/  
  * 58d2844 H0: base (r1=YES; reviewer=full)
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20a/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20a /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp9d4cuvzg/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6318c95 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp9d4cuvzg/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 5개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp9d4cuvzg/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp9d4cuvzg/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=6318c95 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('c4d5651', '6318c95', 'YES->NO'), ('9218768', 'b8732f6', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=2', ['c4d5651', '9218768'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=2 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['c4d5651', '9218768']
  · edge#1[r1 c4d5651->6318c95 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
  · edge#2[r1 9218768->b8732f6 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['c4d5651', '9218768'] · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1

########## T-82 ⑳ⓐ 판별력 대조 — 같은 픽스처를 «복수면 사전순 최소» 구현(직전 판 부속 u16-full-exec-v215.py)으로 실행 → 조상 도입을 골라 통과하면 그것이 F5 «회피»의 실증 ##########
  *   6318c95 M: merge sibling identical approval introduction
  |\  
  | * c4d5651 Y: approval row A (byte-identical) [branch y nonce=3]
  * | b8732f6 CN: NO transition (child of X)
  * | 9218768 X: approval row A [branch x nonce=3]
  |/  
  * 58d2844 H0: base (r1=YES; reviewer=full)
$ python3 u16-full-exec-v215.py <fixture>
NO_rows=['r1']
EDGES(r1)=[('c4d5651', '6318c95', 'YES->NO'), ('9218768', 'b8732f6', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2])
ledger_rows=[('r1', 'YES->NO', '9218768')]
edge#1 r1 c4d5651->6318c95 YES->NO: COVERED by c_APP=9218768 C_R={58d2844}
edge#2 r1 9218768->b8732f6 YES->NO: COVERED by c_APP=9218768 C_R={58d2844}
rules_executed=U-16-a(EDGES);g1;U-16-c(c_APP⊰c);g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover)
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 고아 0
u16_rc=0

########## T-82 ⑳ⓑ 선-검사 순서 corner — 형제 동일 행 도입을 «얕은 클론»에서 실행: |c_APP|=0 ∧ g1 위배 동시 성립 ⇒ PROVENANCE_UNVERIFIABLE(2) + rc≠0 ##########
-- 얕은 클론 확인 --
  is-shallow-repository = true
  rev-list HEAD 개수    = 1
  parents(HEAD)         =   (객체 실재? )
-- 원장·레지스터 @HEAD --
  | ## ledger
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 58d2844 | reviews/review.md | rationale/r1.md
  | id,closable,owner_track
  | other,YES,x
  | r1,NO,tos
  * 6318c95 M: merge sibling identical approval introduction
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20b-shallow/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20b-shallow /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp9lw_co4c/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6318c95 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp9lw_co4c/snap/.git/info/grafts=ABSENT · is_shallow=true · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 1건 · E12 관할) / 커밋 1개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp9lw_co4c/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=True · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp9lw_co4c/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=6318c95 is_shallow=True .git/shallow=['6318c95'] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('b8732f6', '6318c95', 'ABSENT->NO'), ('c4d5651', '6318c95', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=0(+경계 1)', [])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=0 경계커밋=['6318c95'] g4_bad=False g2_bad=False 대응간선=0 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 1건: [('6318c95', ['b8732f6', 'c4d5651'], [])]
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: PROVENANCE_UNVERIFIABLE(2) — |c_APP|=0 (도입 지점 파생 불가)
  · edge#1[r1 b8732f6->6318c95 ABSENT->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
  · edge#2[r1 c4d5651->6318c95 ABSENT->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ row[r1/YES->NO] — |c_APP|=0 (도입 지점 파생 불가) · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_MISSING']
u16_rc=1

########## T-82 ⑳ⓑ 판별력 대조 — 같은 얕은 클론을 «g1·g4 먼저» 문자 구현(u16-order-ctrl-g1first.py)으로 실행 → APPROVAL_MALFORMED(3) 이면 «실패»(전순서 최소 = 2) ##########
  * 6318c95 M: merge sibling identical approval introduction
$ python3 u16-order-ctrl-g1first-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20b-shallow/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20b-shallow /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp4gxti7zy/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6318c95 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp4gxti7zy/snap/.git/info/grafts=ABSENT · is_shallow=true · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 1건 · E12 관할) / 커밋 1개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp4gxti7zy/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=True · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp4gxti7zy/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=6318c95 is_shallow=True .git/shallow=['6318c95'] EVAL_ORDER=g1-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('b8732f6', '6318c95', 'ABSENT->NO'), ('c4d5651', '6318c95', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=0(+경계 1)', [])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=0 경계커밋=['6318c95'] g4_bad=False g2_bad=False 대응간선=0 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 1건: [('6318c95', ['b8732f6', 'c4d5651'], [])]
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — 고아 — 대응 간선 0 (row_id 간선 2 · g1 transition 전건 불일치)
  · edge#1[r1 b8732f6->6318c95 ABSENT->NO]: APPROVAL_MALFORMED(3) — g1 YES->NO≠ABSENT->NO (후보 1 · 대응 1)
  · edge#2[r1 c4d5651->6318c95 ABSENT->NO]: APPROVAL_MALFORMED(3) — g1 YES->NO≠ABSENT->NO (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — 고아 — 대응 간선 0 (row_id 간선 2 · g1 transition 전건 불일치) · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1

########## T-82 ⑳ⓑ 관측 대조 — 같은 얕은 클론을 «canary ㉠ = 항상 성립» 문언(계약 :7124)의 «문자» 구현(대조군 E)으로 실행 → 스냅샷이 얕음을 «상속»하므로 canary 가 발화해 사유가 «기층 오염»으로 바뀐다(E12 관할과 충돌 — 관측 보고) ##########
  * 6318c95 M: merge sibling identical approval introduction
$ python3 u16-canary-literal-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20b-shallow/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20b-shallow /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp7y4bw0ik/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6318c95 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp7y4bw0ik/snap/.git/info/grafts=ABSENT · is_shallow=true · ㉠ 불일치 전역 1건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 1개
rules_executed=
rules_missing=U-16-a(EDGES);U-16-a2(∀edge∃row);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;g6(C_R blob·∃witness);h;MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=[격리 스냅샷 canary] 기층 오염 — replace=[] grafts=False ㉠불일치=1 (정직 경계 (b): --local 폴백·번들 오용 적발)
u16_rc=1

########## 회귀 ⑯ — ABSENT->NO->YES->NO, 간선별 별도 승인 (선형) ⇒ NO_ROWS_CLEAR ##########
  | ## ledger
  | r1 | ABSENT->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | e13a94f7582da7d689637233d00407b844b4710f | reviews/review.md | rationale/r1.md
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 84073a29f64a28557df8cd71bdfcd284e5c347d8 | reviews/review.md | rationale/r1.md
  * 664b47a e2: YES->NO
  * 47b8d18 A2: approval (YES->NO)
  * 84073a2 back to YES
  * 499bb23 e1: ABSENT->NO
  * 977ad60 A1: approval (ABSENT->NO)
  * e13a94f H0: r1 absent
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/16/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/16 /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp5o1l_coq/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=664b47a · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp5o1l_coq/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp5o1l_coq/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp5o1l_coq/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=664b47a is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('977ad60', '499bb23', 'ABSENT->NO'), ('47b8d18', '664b47a', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'ABSENT->NO', '|c_APP|=1', ['977ad60']), ('r1', 'YES->NO', '|c_APP|=1', ['47b8d18'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/ABSENT->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
  row r1/YES->NO raw#1: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 977ad60->499bb23 ABSENT->NO]: COVERED by c_APP=977ad60 C_R={e13a94f}
  · edge#2[r1 47b8d18->664b47a YES->NO]: COVERED by c_APP=47b8d18 C_R={e13a94f}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## 회귀 ⑰ⓐ 기존-경로 B∥A (blob C_R) ⇒ APPROVAL_ORDER_INVALID(11) ##########
H0=cbca92b B=52051e9 A=da59e5e M=5c26bd5
  * 5c26bd5 M: NO transition
  *   2e12067 M0: merge B
  |\  
  | * 52051e9 B: real review content (digest) into existing path
  * | da59e5e A: approval row (aah=B) [parallel to B]
  |/  
  * cbca92b H0: base (r1=YES; reviewer=unrelated)
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/17a/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/17a /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp63apfdm0/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=5c26bd5 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp63apfdm0/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 5개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp63apfdm0/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp63apfdm0/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=5c26bd5 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('2e12067', '5c26bd5', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['da59e5e'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 2e12067->5c26bd5 YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={52051e9} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={52051e9}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=전순서 최소 = APPROVAL_ORDER_INVALID(11) @ edge#1[r1 2e12067->5c26bd5 YES->NO] — g6 C_R={52051e9} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={52051e9} · 발화 전체=['APPROVAL_ORDER_INVALID']
u16_rc=1

########## 회귀 ⑰ⓑ 머지 해소에서 digest blob 도입 ⇒ APPROVAL_UNBOUND(10) [v2.15 E2 에라타 기대값] ##########
H0=21b3e2c B=8ce4f86 A=eb63650 M=f2a60f2
  *   f2a60f2 M: merge — digest blob introduced in resolution + NO transition
  |\  
  | * 8ce4f86 B: reviewer edit without digest
  * | eb63650 A: approval row (aah=B — B lacks digest)
  |/  
  * 21b3e2c H0: base (r1=YES; reviewer=unrelated)
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/17b/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/17b /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpr41scfih/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=f2a60f2 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpr41scfih/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 4개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpr41scfih/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpr41scfih/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=f2a60f2 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('eb63650', 'f2a60f2', 'YES->NO'), ('8ce4f86', 'f2a60f2', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['eb63650'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 eb63650->f2a60f2 YES->NO]: APPROVAL_UNBOUND(10) — h digest ∉ blob(approved_at_head:reviewer_ref) (후보 1 · 대응 1) C_R={8ce4f86}
  · edge#2[r1 8ce4f86->f2a60f2 YES->NO]: APPROVAL_UNBOUND(10) — h digest ∉ blob(approved_at_head:reviewer_ref) (후보 1 · 대응 1) C_R={8ce4f86}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_UNBOUND
reason=전순서 최소 = APPROVAL_UNBOUND(10) @ edge#1[r1 eb63650->f2a60f2 YES->NO] — h digest ∉ blob(approved_at_head:reviewer_ref) (후보 1 · 대응 1) C_R={8ce4f86} · 발화 전체=['APPROVAL_UNBOUND']
u16_rc=1
-- ⑰ⓑ g6 단독 뷰 (target=blob(M:ref), c=M, c_APP=A) --
  C_R(target=blob(M))={f2a60f2}
  g6_verdict=APPROVAL_ORDER_INVALID

########## 회귀 ⑰ⓒ 양성 — B1·B2 독립 동일 blob, A ⊐ B1 ⇒ NO_ROWS_CLEAR ##########
H0=cca6b08 B1=e7e0314 A=99de0e7 B2=f622d50 M=5a4523b
  * 5a4523b M: NO transition
  *   164f068 M0: merge B2
  |\  
  | * f622d50 B2: independent identical blob
  * | 99de0e7 A: approval (aah=B1)
  * | e7e0314 B1: review content (digest)
  |/  
  * cca6b08 H0: base (r1=YES; reviewer=unrelated)
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/17c/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/17c /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp8b1ln99z/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=5a4523b · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp8b1ln99z/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp8b1ln99z/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp8b1ln99z/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=5a4523b is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('164f068', '5a4523b', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['99de0e7'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 164f068->5a4523b YES->NO]: COVERED by c_APP=99de0e7 C_R={f622d50,e7e0314}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## 회귀 ⑲ digest 선배치 ⇒ APPROVAL_ORDER_INVALID(11) ##########
H0=a353678 B=83f9269 A=56e40bf M=61edcc9
  * 61edcc9 M: NO transition
  *   69072c6 M0: merge B
  |\  
  | * 83f9269 B: real review content (digest kept)
  * | 56e40bf A: approval row (aah=B) [parallel]
  |/  
  * a353678 H0: base (r1=YES; reviewer=carrier)
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/19/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/19 /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp2y1skta4/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=61edcc9 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp2y1skta4/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 5개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp2y1skta4/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp2y1skta4/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=61edcc9 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('69072c6', '61edcc9', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['56e40bf'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 69072c6->61edcc9 YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={83f9269} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={83f9269}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=전순서 최소 = APPROVAL_ORDER_INVALID(11) @ edge#1[r1 69072c6->61edcc9 YES->NO] — g6 C_R={83f9269} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={83f9269} · 발화 전체=['APPROVAL_ORDER_INVALID']
u16_rc=1
-- ⑲ v2.14 토큰 기반 C_R 대조 --
  token C_R={a353678}  witness=YES(green — 선배치 우회 통과)

########## 회귀 ⑮ 신규 아티팩트 R ∥ A ⇒ APPROVAL_ORDER_INVALID(11) ##########
H0=be9215b R=845b7c4 A=09dbd55 M=3072489
  * 3072489 M: NO transition
  *   f4e989e M0: merge R
  |\  
  | * 845b7c4 R: new reviewer artifact
  * | 09dbd55 A: approval (aah=R) [parallel]
  |/  
  * be9215b H0: base (r1=YES; reviewer=none)
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/15/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/15 /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp4ti1seoj/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=3072489 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp4ti1seoj/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 5개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp4ti1seoj/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp4ti1seoj/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=3072489 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('f4e989e', '3072489', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['09dbd55'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 f4e989e->3072489 YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={845b7c4} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={845b7c4}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=전순서 최소 = APPROVAL_ORDER_INVALID(11) @ edge#1[r1 f4e989e->3072489 YES->NO] — g6 C_R={845b7c4} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={845b7c4} · 발화 전체=['APPROVAL_ORDER_INVALID']
u16_rc=1

########## 회귀 ⑪ transition 명세 불일치 (원장 YES->NO · 실제 파생 간선 ABSENT->NO) ⇒ APPROVAL_MALFORMED(3) ##########
  | ## ledger
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 80e9000880e8f6b956342c09ef0861b5d6c9ff5f | reviews/review.md | rationale/r1.md
  * 1a5121c e: actual edge is ABSENT->NO
  * f9d30ff A: approval claims YES->NO
  * 80e9000 H0: r1 absent
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/11/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/11 /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmphnuwnohq/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=1a5121c · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmphnuwnohq/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 3개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmphnuwnohq/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmphnuwnohq/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=1a5121c is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('f9d30ff', '1a5121c', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['f9d30ff'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=0 row_id간선=1
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — 고아 — 대응 간선 0 (row_id 간선 1 · g1 transition 전건 불일치)
  · edge#1[r1 f9d30ff->1a5121c ABSENT->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — 고아 — 대응 간선 0 (row_id 간선 1 · g1 transition 전건 불일치) · 발화 전체=['APPROVAL_MALFORMED', 'APPROVAL_MISSING']
u16_rc=1

########## 자인 잔여 — 단일 행이 두 간선을 덮는다 (계약 «닫지 못하는 것» 정직 표기 그대로) ##########
  | ## ledger
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 3cd3493c936401e1f05dce34f92a0ead363bb75b | reviews/review.md | rationale/r1.md
  * 7f27aee e2: YES->NO (no new approval)
  * 7d55a77 back to YES
  * d826a77 e1: YES->NO
  * e72763e A: SINGLE approval row
  * 3cd3493 H0: base (r1=YES; reviewer=full)
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/one/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/one /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpr6sdm9fd/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=7f27aee · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpr6sdm9fd/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 5개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpr6sdm9fd/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpr6sdm9fd/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=7f27aee is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('7d55a77', '7f27aee', 'YES->NO'), ('e72763e', 'd826a77', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['e72763e'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 7d55a77->7f27aee YES->NO]: COVERED by c_APP=e72763e C_R={3cd3493}
  · edge#2[r1 e72763e->d826a77 YES->NO]: COVERED by c_APP=e72763e C_R={3cd3493}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## [v2.20 #2] T-82 ⑮ 판별력 대조 — 같은 R∥A 픽스처를 «g6 생략» 소비자(U-16-a2 전칭을 «(g1~g5)» 닫힌 열거로 읽은 구현)로 실행 → green 이면 그것이 심판 #2 가 지목한 실패다 ##########
  * 3072489 M: NO transition
  *   f4e989e M0: merge R
  |\  
  | * 845b7c4 R: new reviewer artifact
  * | 09dbd55 A: approval (aah=R) [parallel]
  |/  
  * be9215b H0: base (r1=YES; reviewer=none)
$ python3 u16-g6omit-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/15/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/15 /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpfinocikv/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=3072489 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpfinocikv/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 5개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpfinocikv/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpfinocikv/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=3072489 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('f4e989e', '3072489', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['09dbd55'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 f4e989e->3072489 YES->NO]: COVERED by c_APP=09dbd55 C_R={845b7c4}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## [v2.20 #4] T-82 ⑯ 판별력 대조 — 선형 반복 이력을 «폐지 edge_seq 기재값» 소비 구현으로 실행 → MALFORMED(영구 차단) 이면 그것이 v2.13 롤백 결함이다 ##########
  * 664b47a e2: YES->NO
  * 47b8d18 A2: approval (YES->NO)
  * 84073a2 back to YES
  * 499bb23 e1: ABSENT->NO
  * 977ad60 A1: approval (ABSENT->NO)
  * e13a94f H0: r1 absent
$ python3 u16-edgeseq-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/16/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/16 /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpt9_vreyt/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=664b47a · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpt9_vreyt/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpt9_vreyt/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpt9_vreyt/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=664b47a is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('977ad60', '499bb23', 'ABSENT->NO'), ('47b8d18', '664b47a', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'ABSENT->NO', '|c_APP|=1', ['977ad60']), ('r1', 'YES->NO', '|c_APP|=1', ['47b8d18'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/ABSENT->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
  row r1/YES->NO raw#1: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1]: APPROVAL_MALFORMED(3) — edge_seq 기재값(None) ≠ 파생 순번(1) — 폐지 필드 소비
  · edge#1[r1]: APPROVAL_MALFORMED(3) — edge_seq 기재값(None) ≠ 파생 순번(1) — 폐지 필드 소비
  · edge#1[r1 977ad60->499bb23 ABSENT->NO]: COVERED by c_APP=977ad60 C_R={e13a94f}
  · edge#2[r1]: APPROVAL_MALFORMED(3) — edge_seq 기재값(None) ≠ 파생 순번(2) — 폐지 필드 소비
  · edge#2[r1]: APPROVAL_MALFORMED(3) — edge_seq 기재값(None) ≠ 파생 순번(2) — 폐지 필드 소비
  · edge#2[r1 47b8d18->664b47a YES->NO]: COVERED by c_APP=47b8d18 C_R={e13a94f}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ edge#1[r1] — edge_seq 기재값(None) ≠ 파생 순번(1) — 폐지 필드 소비 · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1

########## [v2.20 #4] T-82 ⑱ 판별력 대조 — 병렬 반복 이력을 «폐지 edge_seq 기재값» 소비 구현으로 실행 ##########
  * 6e29849 e2: YES->NO
  * 014cae8 back to YES
  * 059bb15 e1: ABSENT->NO
  *   1a7ed00 MA: merge sibling approval introductions (union)
  |\  
  | * 3bb7f4f A2: approval row (YES->NO, rationale b) [branch b]
  * | c2b31ec A1: approval row (ABSENT->NO, rationale a) [branch a]
  |/  
  * bcec7a2 H0: r1 absent (reviewer artifact with digest)
$ python3 u16-edgeseq-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/18-1/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/18-1 /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpzsh98dv6/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=6e29849 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpzsh98dv6/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 7개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpzsh98dv6/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpzsh98dv6/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=6e29849 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('1a7ed00', '059bb15', 'ABSENT->NO'), ('014cae8', '6e29849', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'ABSENT->NO', '|c_APP|=1', ['c2b31ec']), ('r1', 'YES->NO', '|c_APP|=1', ['3bb7f4f'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/ABSENT->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
  row r1/YES->NO raw#1: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1]: APPROVAL_MALFORMED(3) — edge_seq 기재값(None) ≠ 파생 순번(1) — 폐지 필드 소비
  · edge#1[r1]: APPROVAL_MALFORMED(3) — edge_seq 기재값(None) ≠ 파생 순번(1) — 폐지 필드 소비
  · edge#1[r1 1a7ed00->059bb15 ABSENT->NO]: COVERED by c_APP=c2b31ec C_R={bcec7a2}
  · edge#2[r1]: APPROVAL_MALFORMED(3) — edge_seq 기재값(None) ≠ 파생 순번(2) — 폐지 필드 소비
  · edge#2[r1]: APPROVAL_MALFORMED(3) — edge_seq 기재값(None) ≠ 파생 순번(2) — 폐지 필드 소비
  · edge#2[r1 014cae8->6e29849 YES->NO]: COVERED by c_APP=3bb7f4f C_R={bcec7a2}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ edge#1[r1] — edge_seq 기재값(None) ≠ 파생 순번(1) — 폐지 필드 소비 · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1

########## [v2.20 #3] T-82 ⑳ⓒ 부모신뢰 TOCTOU — SIMULATED 훅 interleaving (조상성 조회 «중»에만 graft 설치·조회 후 제거) ##########
  S0=2f7dbe2 H0=249202a(재작성 대상·후보 밖) R=51703e2 A=b3bbfeb CN=57c8e7e M=HEAD=412fe75
  graft 줄(설치될 내용) = 249202a9470794be24d957ece32d04fd34fc974e 2f7dbe2602bf88e804928fd6e36bea94179739c3 51703e27bad9b7cf11a91524c5d2578fc165edab
  *   412fe75 M: merge reviewer branch
  |\  
  | * 51703e2 R: reviewer artifact (digest)
  * | 57c8e7e CN: NO transition
  * | b3bbfeb A: approval row (aah=R)
  * | 249202a H0: unrelated only (리뷰어 blob 없음·원장 행 없음) ⇒ 후보 우주 «밖»
  |/  
  * 2f7dbe2 S0: register/ledger-header/rationale (리뷰어 경로 없음)
  shim sha256 = aae8890c36e6d58a3cc76adf0e34c934e2e63871956e9dc9abd5f79d8bbab25a · 실 git = /usr/local/bin/git
  훅 «밖» 관측: grafts 파일 = ABSENT (㉡ 은 관측 시점에 항상 부재를 본다)
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
  훅 «안» 효과: is-ancestor(R,CN) = rc 0  (0 = 조상성 뒤집힘) · 훅 밖 = rc 1
  훅 실행 «후» grafts = ABSENT

########## ⑳ⓒ (a) 격리 스냅샷 «없는» 소비자(대조군 A) + interleaving 훅 ⇒ 뒤집히면 실패 ##########
  *   412fe75 M: merge reviewer branch
  |\  
  | * 51703e2 R: reviewer artifact (digest)
  * | 57c8e7e CN: NO transition
  * | b3bbfeb A: approval row (aah=R)
  * | 249202a H0: unrelated only (리뷰어 blob 없음·원장 행 없음) ⇒ 후보 우주 «밖»
  |/  
  * 2f7dbe2 S0: register/ledger-header/rationale (리뷰어 경로 없음)
$ PATH=<shim>:$PATH python3 u16-nosnap-v220.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20c/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20c/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=412fe75 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('51703e2', '412fe75', 'YES->NO'), ('b3bbfeb', '57c8e7e', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['b3bbfeb'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 51703e2->412fe75 YES->NO]: COVERED by c_APP=b3bbfeb C_R={51703e2}
  · edge#2[r1 b3bbfeb->57c8e7e YES->NO]: COVERED by c_APP=b3bbfeb C_R={51703e2}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## ⑳ⓒ (b) 격리 스냅샷 «기층» 판정 실행기 + 같은 훅 ⇒ 스냅샷 조상성 불변 ##########
$ PATH=<shim>:$PATH python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20c/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20c /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp76zsipwg/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=412fe75 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp76zsipwg/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp76zsipwg/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp76zsipwg/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=412fe75 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('51703e2', '412fe75', 'YES->NO'), ('b3bbfeb', '57c8e7e', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['b3bbfeb'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 51703e2->412fe75 YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={51703e2} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={51703e2}
  · edge#2[r1 b3bbfeb->57c8e7e YES->NO]: PROVENANCE_UNVERIFIABLE(2) — g6 C_R=∅ (후보 1 · 대응 1) C_R={}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ edge#2[r1 b3bbfeb->57c8e7e YES->NO] — g6 C_R=∅ (후보 1 · 대응 1) C_R={} · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_ORDER_INVALID']
u16_rc=1

########## ⑳ⓒ (c) 정직 이력(훅 없음) — 판정 실행기 기준선 ##########
  *   412fe75 M: merge reviewer branch
  |\  
  | * 51703e2 R: reviewer artifact (digest)
  * | 57c8e7e CN: NO transition
  * | b3bbfeb A: approval row (aah=R)
  * | 249202a H0: unrelated only (리뷰어 blob 없음·원장 행 없음) ⇒ 후보 우주 «밖»
  |/  
  * 2f7dbe2 S0: register/ledger-header/rationale (리뷰어 경로 없음)
$ python3 u16-full-exec-v220.py <fixture>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20c/.git/info/grafts=ABSENT
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20c /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp6i3se64t/snap
[격리 스냅샷] clone rc=0 
[격리 스냅샷] canary(스냅샷 «안»): HEAD=412fe75 · replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp6i3se64t/snap/.git/info/grafts=ABSENT · is_shallow=false · ㉠ 불일치 전역 0건 (㉢ 얕은 경계 국소 귀속 0건 · E12 관할) / 커밋 6개
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp6i3se64t/snap/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp6i3se64t/snap/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=412fe75 is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('51703e2', '412fe75', 'YES->NO'), ('b3bbfeb', '57c8e7e', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['b3bbfeb'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 51703e2->412fe75 YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={51703e2} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={51703e2}
  · edge#2[r1 b3bbfeb->57c8e7e YES->NO]: PROVENANCE_UNVERIFIABLE(2) — g6 C_R=∅ (후보 1 · 대응 1) C_R={}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ edge#2[r1 b3bbfeb->57c8e7e YES->NO] — g6 C_R=∅ (후보 1 · 대응 1) C_R={} · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_ORDER_INVALID']
u16_rc=1

########## ⑳ⓒ (d) 정직 경계 (a) 실증 — 원본 grafts 가 «참 부모»를 고아화하면 스냅샷 «생성»이 실패한다(fail-closed·거짓 통과 없음) ##########
  grafts(고아화) = 412fe753cfe85e9c3958f1625c1e8bb669f6a8a4 2f7dbe2602bf88e804928fd6e36bea94179739c3   (HEAD 의 부모를 S0 로 재작성 → 참 부모들이 도달 불가)
$ python3 u16-full-exec-v220.py <fixture-with-orphaning-grafts>
[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20c-orphan/.git/info/grafts=present
[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx82v220/20c-orphan /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmpnsb794pl/snap
[격리 스냅샷] clone rc=128 힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
remote: 힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃        
remote: 힌트: 버전에
rules_executed=
rules_missing=U-16-a(EDGES);U-16-a2(∀edge∃row);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;g6(C_R blob·∃witness);h;MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=[격리 스냅샷] clone 실패(rc=128) — 정직 경계 (a): 원본 graft 가 참 부모를 도달 불가로 만들면 스냅샷 «생성»이 실패한다(거짓 통과 없음·fail-closed): 힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDep
u16_rc=1

########## [v2.20 #3] U-17 축 스냅샷 적용 — D·P 조상성도 스냅샷 «안»에서 소비한다 (같은 interleaving 훅) ##########
  seed=778db30 W=dcbe0e6(후보 밖·재작성 대상) d=fb4b5a9 P=8ddcd02 HEAD=de6f2cc
  graft 줄 = dcbe0e6b88c93af8deb184cf5337d0527ce69179 778db309f9f3099d0f2ef448f4d0c5ec58612c78 8ddcd027d748bb71222009b995632b47ddec770f
  정직 이력: is-ancestor(P,d) rc=1  (1 = P ⋠ d = LATE 진실)
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
  graft 설치 후(원 저장소): is-ancestor(P,d) rc=0 · --no-replace-objects 하 rc=0  (K-4: grafts 는 무력화로 안 꺼진다)
$ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks <origin> <snap>
  | 힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
  | 힌트: 버전에서 제거될 예정입니다.
  | 힌트: 
  | 힌트: 그래프트를 레퍼런스로 전환하려면
  | 힌트: "git replace --convert-graft-file" 명령을
  | 힌트: 사용하십시오.
  | 힌트: 
  | 힌트: 이 메시지를 보지 않으려면
  | 힌트: "git config advice.graftFileDeprecated false"
  | 힌트: 명령을 사용하십시오
  | remote: 힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃        
  | remote: 힌트: 버전에서 제거될 예정입니다.        
  | remote: 힌트:         
  | remote: 힌트: 그래프트를 레퍼런스로 전환하려면        
  | remote: 힌트: "git replace --convert-graft-file" 명령을        
  | remote: 힌트: 사용하십시오.        
  | remote: 힌트:         
  | remote: 힌트: 이 메시지를 보지 않으려면        
  | remote: 힌트: "git config advice.graftFileDeprecated false"        
  | remote: 힌트: 명령을 사용하십시오        
  clone rc=0
  스냅샷 canary: replace -l=[] · grafts=ABSENT · is_shallow=false
  스냅샷 조상성: is-ancestor(P,d) rc=1  (1 = 참 조상성 = LATE 유지 · 원본 graft 미전파)
  ㉠ 대조(스냅샷): 불일치 0건
```

## 8. 실행기·드라이버 원문

### 8-1. 판정 실행기 `u16-full-exec-v220.py` (sha256 `b90920bdc6d2120954e95273c063fbf8c959e943f0c816c2bd82f8df42045e56` · 589행)

```python
#!/usr/bin/env python3
"""U-16 «전 규칙» 손 실행기 — v2.20 동결 3d17ea66 (계약 §13.6.5)

v2.19 에라타 6차 실행기(359f5bc5·sha256 9db15709...) 에서 파생 — 델타는 **v2.20 심판 처분 #3 1건**뿐이다:
  [#3 격리 스냅샷 기층 — 계약 :7098-7124] 조상성·부모·원장 blob 을 소비하는 «모든» 판정을
  진입 시점 HEAD 의 «격리 스냅샷»(`git clone --no-local --no-hardlinks` + `GIT_NO_REPLACE_OBJECTS=1`)
  «안에서만» 수행한다.  스냅샷 생성 실패는 **fail-closed**(정직 경계 (a)), 스냅샷 «안»의 청정성
  (`replace -l` 공집합 ∧ grafts 부재 ∧ ㉠ 재파생==%P)은 **canary** 로 방출한다(정직 경계 (b)).
  #2(U-16-a2 g6 «전 항» 전칭)는 이 실행기가 **이미 g6 을 실행**하므로 코드 델타 0 —
  대조군 파일(`u16-g6omit-v220.py`)이 «g6 생략 소비자»를 실증한다.

(구 헤더 — v2.19 계보 보존)
U-16 «전 규칙» 손 실행기 — v2.19 에라타 6차 (계약 359f5bc5 §13.6.5

v2.19 에라타 5차 실행기(eddbd241·sha256 26f0583a…) 에서 파생 — 델타는 **에라타 6차 [E15] 1건**(주석·헤더만·거동 불변):
  [E15 — stop-time BLOCK] 결합 base 는 **«저장소 루트(`--show-toplevel`)»만**.  `--absolute-git-dir` 결합은 **철회** —
  `<root>/.git` + `.git/info/grafts` = 이중 `.git` → «거짓 ABSENT» → ㉡ 통과 = **fail-open**(addendum-5 가 «fail-closed»로 오분류).
  [E15 극성] «거짓 부재가 검사를 통과시키면 fail-open» — 부재의 극성은 «검사 방향»이 정한다.  절대 출력은 그대로(결합 금지).


v2.19 에라타 4차 실행기(db6ce918·sha256 2a9d254f…) 에서 파생 — 델타는 **에라타 5차 [E14] 1건**뿐이다:
  파생 경로의 «결합 기준» 고정 — `--git-path` 가 «상대»면 **저장소 루트(`git rev-parse --show-toplevel`)와 결합**하고 절대면 그대로 쓴다.
  **cwd 기준 상대 검사 금지**(저장소 밖 cwd 에서 «거짓 ABSENT» → ㉡ 통과하는 fail-open L-1 을 닫는다).
  (E10~E13 은 db6ce918 실행기 거동 그대로 — 코드 델타 0.)


v2.19 에라타 3차 실행기(f6493d23·sha256 d0c62ee7…) 에서 파생 — 델타는 **에라타 4차 2건**뿐이다:
  [E12] ㉠/㉢ «관할» — 절차 순서를 «㉢ 먼저»로 명시: 얕은 경계로 «특정»되는 ㉠ 불일치는 국소 귀속(PU_LOCAL)하고 «남는» 것만 전역(PU_MISMATCH).
  [E13] 저장소 내부 경로는 리터럴 `.git/…` 금지 — `git rev-parse --git-path <x>` 파생만.  (`--git-path` 는 일반 배치에서 «상대» 경로를
        주므로 저장소 루트 기준으로 결합한다 — §5 L-1.)
  (E10·E11 은 f6493d23 실행기 거동 그대로 — 코드 델타 0.)


v2.19 에라타 2차 실행기(ad5be1a3·sha256 cca1d6d7…) 에서 파생 — 델타는 **에라타 3차 [E10] 1건**뿐이다:
  `[PARENTS-UNTRUSTED]` 판별을 «재구조화» — ㉠ 주 판별 = 부모 집합 «구조 재파생»(`git --no-replace-objects cat-file commit <x>` 의
  `parent` 줄 직접 파싱).  판정의 «모든» ∀p∈parents(x) 항이 이 재파생 집합을 쓰고, 이 집합이 «이력 뷰»(`git log --format=%P`, 무력화 «없이»)와
  불일치하면 이력 뷰가 재작성된 것 → 전역 `PROVENANCE_UNVERIFIABLE`.  열거가 아니라 재파생이라 열린-세계(M-3)를 닫는다.
  ㉡ 전역 관측(`git replace -l` 공집합 ∧ `<git-dir>/info/grafts` 부재)은 «보조»로 격하 · ㉢ 국소 축(얕은 경계)은 그대로.
  [독해 — 계약 미규정] ㉠ 불일치가 «얕은 경계»에서 비롯되면 ㉢ 이 담당한다(전역 승격 안 함) — E6 국소화·T-82 ⑳ⓑ 판별력 보존(§5 K-1).
  E11(P_first)은 U-17 소관이라 이 실행기의 델타가 아니다.
 U-16-a/a2/b/c/d/f/g(g1~g6)/h).

v2.19 에라타 실행기(e3ed4e78·sha256 729867ca…) 에서 파생 — 델타는 **에라타 2차 [E8] 1건**뿐이다:
  `[SHALLOW]` → **`[PARENTS-UNTRUSTED]`** 일반화(U-16-c 유일 소스).  «부모 집합을 신뢰할 수 없는 상태»는 둘이다 —
  (1) 얕은 클론 «경계»(부모 미상): `.git/shallow` ∪ 부모 커밋 «객체» 조회 실패 → **국소**(E6 — 해당 행/간선의 후보 우주에 있을 때만)
  (2) 부모 «재작성»: `git replace --graft`/replace ref · `.git/info/grafts` → **전역 관측**(어느 커밋이 재작성됐는지 per-commit 판별 수단이 없다)
  판별 = 이중: ① 관측 `git replace -l` 공집합 ∧ `.git/info/grafts` 부재 — 위반 → `PROVENANCE_UNVERIFIABLE`(전순서 2)
              ② 무력화 `GIT_NO_REPLACE_OBJECTS=1` 전역(모든 조상·부모 파생 git 호출).  **grafts 는 ② 로 꺼지지 않는다(실측)** — ① 이 그 축을 담당.
  E9(P_first/P_last)는 U-17 소관이라 이 실행기의 델타가 아니다.


v2.19 실행기(d5a8302a·sha256 5692e75d…) 에서 파생 — 델타는 **에라타 [SHALLOW]/E5 1건**뿐이다:
  `C_R(c)`(g6) 의 «∀-부모» 항에도 얕은 클론 경계 단서를 적용한다(계약 U-16-c [SHALLOW] 동형 — `c_APP` 는 v2.19 에
  이미 적용돼 있었고 에라타가 그 독해를 계약 문언으로 승격했다).  경계 커밋은 «진짜 루트»가 아니므로 도입 지점으로
  «확정하지 않는다» → 그 결과 `C_R` 크기 0 → 선-검사 2 `PROVENANCE_UNVERIFIABLE`.
  **[E6] 전역 단축이 아니라 «해당 행/간선의 후보 우주» 국소 판정**이다(얕아도 후보 우주 밖이면 접지 않는다).
  **[E7]** 고아 구조 정의·«한 간선 다수 후보 → 전순서 최소» 는 v2.19 실행기가 이미 그 거동이었다 — 에라타가
  그 독해를 계약 문언으로 승격했으므로 코드 델타 0(이제 «자체 선언»이 아니라 «계약 인용»이다).


v2.15 부속(`U16-LEDGER-CHECK.md` §1 · sha256 a0201149…) 에서 파생하며 델타는 **심판 F4·F5 처분 두 가지**뿐이다:
  [F5] `c_APP(a)` 를 «구조 집합»으로 파생한다 — v2.15 부속의 «복수면 사전순 최소»(계약 밖 자체 보충)를 폐기하고
       `U-16-c` 카디널리티 처분을 그대로 소비: |c_APP|=0 → PROVENANCE_UNVERIFIABLE · |c_APP|>1 → APPROVAL_MALFORMED ·
       |c_APP|=1 → 그 «유일 원소»를 세 소비처(U-16-c 조상성 · g5 · g6)가 쓴다.
  [F4] 상태 우선순위를 «실행기 자체 선언»에서 **계약 `U-16-d` 전순서 12단**으로 교체하고, 평가 절차를
       **① 선-검사(1~4) → ② g-단락(5~11)** 으로 둔다(계약 U-16-d 정정 블록의 문자 구현).
       `edge_seq` 는 «표시용 파생»으로만 방출하고 판정 입력에 쓰지 않는다(U-16-b #2 마감 스키마).

S-23: 실행한 규칙 목록을 방출하고, 계약 소비 규칙 집합과 차집합이 비지 않으면 green(NO_ROWS_CLEAR) 대신
      PARTIAL_EXECUTION 을 방출한다.

픽스처 형식: register.csv = 'id,closable,owner_track' (헤더 있음) ·
             LEDGER.md 행 = 'row_id | transition | row_content_digest | approved_at_head | reviewer_ref | rationale_ref'
row_content_digest = U-16-f: 레지스터 행 전 열을 LC_ALL=C 열이름 정렬 '<열>=<값>' NUL 결합 sha256.

방출: closable_no_provenance_state=<값> · rules_executed=<목록> · rc 0 = NO_ROWS_CLEAR 만.
"""
import hashlib, subprocess, sys

# ── 계약 U-16-d 전순서 (유일 소스 — 실행기가 순서를 «선언»하지 않는다)
TOTAL_ORDER = ["CONSUMER_ABSENT", "PROVENANCE_UNVERIFIABLE", "APPROVAL_MALFORMED", "APPROVAL_MISSING",
               "APPROVAL_SAME_COMMIT", "APPROVAL_AFTER", "APPROVAL_CONTENT_DRIFT", "APPROVAL_HEAD_INVALID",
               "APPROVAL_ROW_MUTATED", "APPROVAL_UNBOUND", "APPROVAL_ORDER_INVALID", "NO_ROWS_CLEAR"]
TO = {s: i + 1 for i, s in enumerate(TOTAL_ORDER)}

# ── [v2.19 U-16-d 정정] ① 선-검사(1~4) 를 g-규칙 «앞»에 둔다.  대조군(«g1·g4 먼저» 문자 구현)은 이 한 줄만 다르다.
CANARY_SHALLOW_LOCAL = True            # [E12 관할] 스냅샷 canary 의 ㉠ 불일치 중 얕은 «경계» 귀속분은 국소 (대조군 E: False = 계약 :7124 «항상 성립» 문언의 «문자» 구현)
SNAPSHOT_BASE = True                   # [v2.20 #3] 격리 스냅샷 기층 (대조군 파일: False — 원 저장소 직접 소비)
EVAL_ORDER = "precheck-first"          # 대조군 파일: "g1-first"  (계약 U-16-d ① 선-검사 → ② g-단락 · [E6] 국소)

RULES_CONTRACT = ["U-16-a(EDGES)", "U-16-a2(∀edge∃row)", "U-16-b(edge_seq 표시용 파생·판정 미소비)",
                  "U-16-c(c_APP 구조 집합·카디널리티·진 조상)", "g1", "g2", "g3", "g4", "g5",
                  "g6(C_R blob·∃witness)", "h", "MALFORMED(orphan/double-cover)",
                  "U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)"]
REG, LED = "register.csv", "LEDGER.md"
R = None


# [E8 ②] 무력화 — 모든 git 호출이 replace 뷰를 따르지 않는다 (grafts 는 이 플래그로 꺼지지 않는다: ① 관측이 담당)
GITBASE = ["git", "--no-replace-objects", "-C"]


def g(*a):
    return subprocess.run([*GITBASE, R, *a], capture_output=True, text=True).stdout.strip()


def ok(*a):
    return subprocess.run([*GITBASE, R, *a], capture_output=True).returncode == 0


def have(commit):
    """커밋 «객체»가 실재하는가 (얕은 클론 경계 판별 — 경로 부재와 구별한다)."""
    return ok("cat-file", "-e", commit + "^{commit}")


def gitpath(rel):
    """[E13 파생 + E14/E15 결합] `--git-path` 출력이 «상대»면 **저장소 루트(`--show-toplevel`)** 와 결합하고 절대면 그대로.
    **`--absolute-git-dir` 결합 금지**(이중 `.git` → 거짓 ABSENT → fail-open · E15).
    cwd 기준 상대 검사는 «금지» — 저장소 밖 cwd 에서 «거짓 ABSENT» 가 되어 ㉡ 이 통과하는 fail-open(L-1)을 닫는다."""
    import os as _os
    v = g("rev-parse", "--git-path", rel)
    if not v:
        return ""
    if _os.path.isabs(v):
        return v
    top = g("rev-parse", "--show-toplevel") or R
    return _os.path.join(top, v)


def shallow_boundary():
    """얕은 클론 «경계» 커밋 집합(.git/shallow).  이들의 부모 집합은 «부재»가 아니라 «미상»이다 —
    git 은 경계 커밋을 부모 없는 커밋처럼 보고하므로(`%P` 공백), 구조 정의의 ∀-부모 항이
    «공허참»이 되어 임의 커밋이 도입 지점으로 확정된다(fail-open).  그래서 경계를 분리 관측한다."""
    import os
    try:
        return set(open(gitpath("shallow")).read().split())
    except Exception:
        return set()


def show(c, p):
    r = subprocess.run([*GITBASE, R, "show", f"{c}:{p}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def blob(c, p):
    return g("rev-parse", "--quiet", "--verify", f"{c}:{p}") or "ABSENT"


def parents(c):
    """[E10 ㉠] 부모 집합 «구조 재파생» — 커밋 «객체»의 parent 줄을 직접 파싱한다.
    replace ref·grafts·«미지의 재작성 기제»를 따르지 않는다(열거가 아니라 재파생)."""
    out = subprocess.run([*GITBASE, R, "cat-file", "commit", c], capture_output=True, text=True).stdout
    ps = []
    for line in out.split("\n"):
        if line == "":
            break
        if line.startswith("parent "):
            ps.append(line.split()[1])
    return ps


def parents_ambient(c):
    """[E10 ㉠ 대조] «이력 뷰»가 주는 부모 — 무력화를 걷어내고 관측(재작성 여부를 보려면 뷰를 그대로 봐야 한다)."""
    import os as _os
    env = dict(_os.environ); env.pop("GIT_NO_REPLACE_OBJECTS", None)
    return subprocess.run(["git", "-C", R, "log", "--format=%P", "-1", c],
                          capture_output=True, text=True, env=env).stdout.split()


PU_MISMATCH = []
PU_LOCAL = []


def check_parents(x):
    """[E12] ㉠ 불일치 수집 — «㉢ 먼저»: 얕은 경계로 «특정»되면 국소 귀속(PU_LOCAL)하고 전역으로 승격하지 않는다."""
    tp, ap = sorted(parents(x)), sorted(parents_ambient(x))
    if tp == ap:
        return True
    if x in shallow_boundary():
        PU_LOCAL.append((x, tp, ap))
        return True
    PU_MISMATCH.append((x, tp, ap))
    return False


def strict_anc(a, b):
    return a != b and ok("merge-base", "--is-ancestor", a, b)


def reg_rows(c):
    t = show(c, REG)
    out = {}
    if t is None:
        return out
    lines = [l for l in t.splitlines() if l.strip()]
    if not lines:
        return out
    hdr = lines[0].split(",")
    for l in lines[1:]:
        f = l.split(",")
        out[f[0]] = dict(zip(hdr, f))
    return out


def canon_digest(row):
    return hashlib.sha256(b"\0".join(f"{k}={row[k]}".encode() for k in sorted(row))).hexdigest()


def led_raw(c):
    """커밋 c 시점 원장 blob 의 «정규형» 행 집합 (U-16-c rows(y:LEDGER)) — 경로 부재 = 공집합([H4] 동형)."""
    t = show(c, LED)
    if t is None:
        return set()
    return set(l.strip() for l in t.splitlines() if l.strip() and not l.startswith("#"))


def led_rows(c):
    t = show(c, LED)
    out = []
    if t is None:
        return out
    for l in t.splitlines():
        if not l.strip() or l.startswith("#"):
            continue
        f = [x.strip() for x in l.split("|")]
        if len(f) >= 6:
            out.append(dict(row_id=f[0], transition=f[1], digest=f[2], aah=f[3],
                            reviewer_ref=f[4], rationale_ref=f[5], raw=l.strip()))
    return out


def c_app_set(raw):
    """U-16-c 구조 집합:  c_APP(a) = { x ⊑ HEAD : a ∈ rows(x:LEDGER) ∧ ∀p∈parents(x): a ∉ rows(p:LEDGER) }
    부모 «커밋 객체»가 없으면(얕은 클론 경계) 둘째 항을 평가할 수 없으므로 그 x 를 도입 지점으로 «확정하지 않는다»
    — 부재를 «참»으로 접으면 얕은 클론이 임의 커밋을 도입 지점으로 만들어낸다(fail-open)."""
    cands, boundary = [], []
    for x in g("rev-list", "HEAD").splitlines():
        if raw not in led_raw(x):
            continue
        check_parents(x)                  # [E12] ㉢ 먼저 — 얕은 경계면 국소 귀속, 남는 것만 전역
        if is_boundary(x):                # ㉢ 국소 — 부모 «객체» 미상 ⇒ 도입 지점으로 확정하지 않는다
            boundary.append(x)
            continue
        if all(raw not in led_raw(p) for p in parents(x)):
            cands.append(x)
    return cands, boundary


def replace_refs():
    """[E8 ①] `git replace -l` — 부모 «재작성» 관측 (grafts 는 여기에 «나타나지 않는다» — 실측)."""
    return [x for x in g("replace", "-l").split() if x]


def grafts_present():
    """[E8 ①] `.git/info/grafts` 실재 여부 (deprecated 이나 동작하며 `--no-replace-objects` 로 꺼지지 않는다 — 실측)."""
    import os
    return os.path.exists(gitpath("info/grafts"))


def is_boundary(x):
    """[PARENTS-UNTRUSTED (1)] 얕은 클론 «경계» — 그 커밋의 부모 집합이 «미상» (진짜 루트와 구별한다).
    (2) «재작성» 축은 per-commit 판별 수단이 없어 main() 의 «전역 관측»이 담당한다."""
    if x in shallow_boundary():
        return True
    return any(not have(p) for p in parents(x))


def c_r_set(c, ref, aah):
    """g6 구조 정의:  C_R(c) = { x ⊑ c : blob(x:ref) == blob(aah:ref) ∧ ∀p∈parents(x): blob(p:ref) ≠ 그 blob }
    부모 경로 «부재»는 ≠ 로 읽는다([H4]).  **[SHALLOW/E5] 부모 «커밋 객체» 미상(얕은 경계)은 다르다** —
    ∀-부모 항을 평가할 수 없으므로 그 x 를 도입 지점으로 확정하지 않는다(반환 2번째 값에 경계를 모은다)."""
    tgt = blob(aah, ref)
    if tgt == "ABSENT":
        return [], []
    cands, bnd = [], []
    for x in g("rev-list", c).splitlines():
        if blob(x, ref) != tgt:
            continue
        check_parents(x)                  # [E12] ㉢ 먼저 — 얕은 경계면 국소 귀속, 남는 것만 전역
        if is_boundary(x):
            bnd.append(x)
            continue
        if all(blob(p, ref) != tgt for p in parents(x)):
            cands.append(x)
    return cands, bnd


def emit(state, reason, executed, extra=()):
    for line in extra:
        print(line)
    print("rules_executed=" + ";".join(executed))
    missing = [r for r in RULES_CONTRACT if r not in executed]
    print("rules_missing=" + (";".join(missing) if missing else "∅"))
    if missing and state == "NO_ROWS_CLEAR":
        print("closable_no_provenance_state=PARTIAL_EXECUTION")
        print(f"reason=S-23: 미실행 규칙 {missing} — green 방출 금지")
        sys.exit(1)
    print(f"closable_no_provenance_state={state}")
    print(f"reason={reason}")
    sys.exit(0 if state == "NO_ROWS_CLEAR" else 1)



# ── [v2.20 — 심판 #3] 격리 스냅샷 기층 (계약 3d17ea66 :7098-7124) ────────────────────────────
def snapshot(origin):
    """진입 시점 HEAD 를 «격리 스냅샷»으로 고정한다 — 단일 방법: git clone --no-local --no-hardlinks.

    극성(계약): grafts 는 직렬화되지 않아 전송으로 따라오지 않고, replace ref 는 기본 refspec 이
    가져오지 않는다.  커밋 객체는 내용주소라 스냅샷의 부모 줄은 원본과 바이트 동일 = «참 그래프».
    정직 경계 (a) 원본 graft 가 참 부모를 도달 불가로 만들면 clone «생성»이 실패한다(fail-closed).
             (b) 스냅샷 «안»의 ㉡·㉠ 을 canary 로 재확인한다(--local 폴백·번들 오용 적발).
    """
    import os as _os, subprocess as _sp, tempfile as _tf

    def og(*a):
        return _sp.run(["git", "-C", origin, *a], capture_output=True, text=True).stdout.strip()

    repl0 = [x.split()[0] for x in og("replace", "-l").splitlines() if x.strip()]
    gp0 = og("rev-parse", "--git-path", "info/grafts")
    if gp0 and not _os.path.isabs(gp0):
        gp0 = _os.path.join(og("rev-parse", "--show-toplevel") or origin, gp0)
    print("[격리 스냅샷] 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=%s · %s=%s"
          % ([x[:7] for x in repl0], gp0, "present" if _os.path.isfile(gp0) else "ABSENT"))
    head = og("rev-parse", "HEAD")
    snap = _os.path.join(_tf.mkdtemp(), "snap")
    env = dict(_os.environ); env["GIT_NO_REPLACE_OBJECTS"] = "1"
    print("[격리 스냅샷] $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks %s %s" % (origin, snap))
    r = _sp.run(["git", "clone", "--quiet", "--no-local", "--no-hardlinks", origin, snap],
                capture_output=True, text=True, env=env)
    print("[격리 스냅샷] clone rc=%d %s" % (r.returncode, (r.stderr or "").strip()[:300]))
    if r.returncode != 0:
        emit("PROVENANCE_UNVERIFIABLE",
             "[격리 스냅샷] clone 실패(rc=%d) — 정직 경계 (a): 원본 graft 가 참 부모를 도달 불가로 만들면 "
             "스냅샷 «생성»이 실패한다(거짓 통과 없음·fail-closed): %s" % (r.returncode, (r.stderr or "").strip()[:200]), [])
    def sg(*a):
        return _sp.run(["git", "-C", snap, *a], capture_output=True, text=True)
    if sg("cat-file", "-e", head + "^{commit}").returncode != 0:
        emit("PROVENANCE_UNVERIFIABLE", "[격리 스냅샷] 진입 HEAD(%s) 가 스냅샷에 부재 — 핀 실패 fail-closed" % head[:7], [])
    sg("checkout", "--quiet", "--detach", head)
    replc = [x.split()[0] for x in sg("replace", "-l").stdout.splitlines() if x.strip()]
    gpc = sg("rev-parse", "--git-path", "info/grafts").stdout.strip()
    if gpc and not _os.path.isabs(gpc):
        gpc = _os.path.join(sg("rev-parse", "--show-toplevel").stdout.strip() or snap, gpc)
    commits = sg("rev-list", "--all").stdout.split()
    # [E12 관할] ㉢ 먼저 — 얕은 «경계» 커밋은 그 자체로 ㉠ 불일치(cat-file 부모 有 vs %P ∅)를 만든다(계약 :7148-7152).
    # 경계로 «특정»되는 불일치는 국소 귀속하고, «남는» 것만 기층 오염(전역)으로 올린다.
    shp = sg("rev-parse", "--git-path", "shallow").stdout.strip()
    if shp and not _os.path.isabs(shp):
        shp = _os.path.join(sg("rev-parse", "--show-toplevel").stdout.strip() or snap, shp)
    try:
        shallow_set = set(open(shp).read().split())
    except Exception:
        shallow_set = set()
    mism = 0; local = 0
    for x in commits:
        tp = sorted(l.split()[1] for l in sg("--no-replace-objects", "cat-file", "commit", x).stdout.split("\n\n")[0].splitlines() if l.startswith("parent "))
        ap = sorted(_sp.run(["git", "-C", snap, "log", "--format=%P", "-1", x], capture_output=True, text=True).stdout.split())
        if tp != ap:
            if CANARY_SHALLOW_LOCAL and x in shallow_set:
                local += 1
            else:
                mism += 1
    print("[격리 스냅샷] canary(스냅샷 «안»): HEAD=%s · replace -l=%s · %s=%s · is_shallow=%s · ㉠ 불일치 전역 %d건 (㉢ 얕은 경계 국소 귀속 %d건 · E12 관할) / 커밋 %d개"
          % (sg("rev-parse", "HEAD").stdout.strip()[:7], [x[:7] for x in replc], gpc,
             "present" if _os.path.isfile(gpc) else "ABSENT",
             sg("rev-parse", "--is-shallow-repository").stdout.strip(), mism, local, len(commits)))
    if replc or _os.path.isfile(gpc) or mism:
        emit("PROVENANCE_UNVERIFIABLE",
             "[격리 스냅샷 canary] 기층 오염 — replace=%s grafts=%s ㉠불일치=%d (정직 경계 (b): --local 폴백·번들 오용 적발)"
             % (replc, _os.path.isfile(gpc), mism), [])
    _os.environ["GIT_NO_REPLACE_OBJECTS"] = "1"
    return snap


def main():
    global R
    ORIGIN = sys.argv[1]
    R = snapshot(ORIGIN) if SNAPSHOT_BASE else ORIGIN   # [v2.20 #3] 격리 스냅샷 기층 (대조군 파일은 이 한 줄이 다르다)
    executed = []
    contributions = []          # (scope, state, why)

    def add(scope, state, why):
        contributions.append((scope, state, why))
        print(f"  · {scope}: {state}({TO[state]}) — {why}")

    if not ok("rev-parse", "--is-inside-work-tree"):
        emit("PROVENANCE_UNVERIFIABLE", "git 작업트리 아님", executed)
    HEAD = g("rev-parse", "HEAD")
    SHALLOW = (g("rev-parse", "--is-shallow-repository") == "true")
    REPL, GRAFTS = replace_refs(), grafts_present()
    print(f"[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l={[x[:7] for x in REPL]} · {gitpath('info/grafts')}(--git-path 파생)={'present' if GRAFTS else 'ABSENT'}"
          f" · ㉢ is_shallow={SHALLOW} · shallow 파생 경로={gitpath('shallow')} · 무력화 = git --no-replace-objects (전 호출)"
          f" · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱")
    print(f"HEAD={HEAD[:7]} is_shallow={SHALLOW} .git/shallow={[x[:7] for x in sorted(shallow_boundary())]} EVAL_ORDER={EVAL_ORDER}"
          f"  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)")

    # ── 소비자 부재 (전순서 1)
    consumer_absent = (show(HEAD, REG) is None) or (show(HEAD, LED) is None)

    cur = reg_rows(HEAD)
    no_rows = [rid for rid, r in cur.items() if r.get("closable") == "NO"]

    # ── U-16-a: EDGES(r)  (→NO 간선 전부 · 루트/부모 부재는 ABSENT->NO)
    executed.append("U-16-a(EDGES)")
    edges = {}
    for rid in no_rows:
        E = []
        for c in g("rev-list", "HEAD").splitlines():
            if reg_rows(c).get(rid, {}).get("closable") != "NO":
                continue
            ps = parents(c) or [None]
            for p in ps:
                pv = "ABSENT" if p is None or rid not in reg_rows(p) else reg_rows(p)[rid]["closable"]
                if pv != "NO":
                    E.append((p, c, "ABSENT->NO" if pv == "ABSENT" else "YES->NO"))
        E.sort(key=lambda e: (g("log", "--format=%ad", "--date=iso-strict", "-1", e[1]), e[1]))
        edges[rid] = E
    # ── U-16-b: edge_seq 는 «표시용 파생»만 — 판정 입력 아님
    executed.append("U-16-b(edge_seq 표시용 파생·판정 미소비)")
    print(f"NO_rows={no_rows}")
    for rid, E in edges.items():
        print(f"EDGES({rid})={[((p or 'ROOT')[:7], c[:7], t) for p, c, t in E]}  "
              f"(edge_seq 표시용 파생={list(range(1, len(E) + 1))} · 판정 미소비)")

    L = led_rows(HEAD)
    executed.append("U-16-c(c_APP 구조 집합·카디널리티·진 조상)")
    for a in L:
        a["capp"], a["capp_boundary"] = c_app_set(a["raw"])
    print("ledger_rows=" + str([(a["row_id"], a["transition"],
                                 "|c_APP|=%d%s" % (len(a["capp"]),
                                                   "" if not a["capp_boundary"] else "(+경계 %d)" % len(a["capp_boundary"])),
                                 [x[:7] for x in a["capp"]]) for a in L]))

    executed += ["g1", "g2", "g3", "g4", "g5", "h", "g6(C_R blob·∃witness)",
                 "U-16-a2(∀edge∃row)", "MALFORMED(orphan/double-cover)",
                 "U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)"]

    # ── 규칙 사실 수집 (short-circuit 없이 전부 측정한 뒤 순서를 적용한다)
    def g4_bad(a):
        return show(HEAD, a["rationale_ref"]) is None

    def g2_bad(a):
        return a["row_id"] not in cur or canon_digest(cur[a["row_id"]]) != a["digest"]

    def g3_bad(a, c):
        return (not have(a["aah"])) or (not ok("merge-base", "--is-ancestor", a["aah"], c)) \
            or show(a["aah"], a["reviewer_ref"]) is None

    def g5_bad(a, capp):
        return a["raw"] not in led_raw(capp)

    def h_bad(a):
        t = show(a["aah"], a["reviewer_ref"])
        return t is None or a["digest"] not in t

    print("\n[사실 수집] 규칙별 측정값 (순서 적용 «전»)")
    for a in L:
        a["_g4"] = g4_bad(a)
        a["_g2"] = g2_bad(a)
        a["_matching_edges"] = [(rid, e) for rid, E in edges.items() for e in E
                                if rid == a["row_id"] and e[2] == a["transition"]]
        a["_rowid_edges"] = [(rid, e) for rid, E in edges.items() for e in E if rid == a["row_id"]]
        print(f"  row {a['row_id']}/{a['transition']} raw#{L.index(a)}: |c_APP|={len(a['capp'])}"
              f"{'' if not a['capp_boundary'] else ' 경계커밋=' + str([x[:7] for x in a['capp_boundary']])}"
              f" g4_bad={a['_g4']} g2_bad={a['_g2']} 대응간선={len(a['_matching_edges'])} row_id간선={len(a['_rowid_edges'])}")

    print(f"[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 {len(PU_LOCAL)}건: "
          f"{[(x[:7], [q[:7] for q in tp], [q[:7] for q in ap]) for x, tp, ap in PU_LOCAL]}")
    print(f"[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 {len(PU_MISMATCH)}건: "
          f"{[(x[:7], [q[:7] for q in tp], [q[:7] for q in ap]) for x, tp, ap in PU_MISMATCH]}")
    print("\n[상태 귀속] 계약 U-16-d 순서 적용")
    if consumer_absent:
        add("global", "CONSUMER_ABSENT", "레지스터·원장 부재")
    if PU_MISMATCH:
        add("global", "PROVENANCE_UNVERIFIABLE",
            "[PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: %s"
            % [(x[:7], [q[:7] for q in tp], [q[:7] for q in ap]) for x, tp, ap in PU_MISMATCH])
    if REPL:
        add("global", "PROVENANCE_UNVERIFIABLE",
            "[PARENTS-UNTRUSTED] git replace -l 비공집합(%s) — 부모 집합 재작성 = 신뢰 불가" % [x[:7] for x in REPL])
    if GRAFTS:
        add("global", "PROVENANCE_UNVERIFIABLE",
            "[PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)")
    # 얕은 클론은 «전역 단축»으로 처리하지 않는다 — 경계 커밋을 도입 지점으로 «확정하지 않음»으로써
    # `|c_APP|=0` 이라는 구조 사실로 드러나고, 그 값이 선-검사 2 에서 소비된다(계약 U-16-d ①).
    # 그래야 «순서» 대조군(g1-first)이 전역 단축에 가려지지 않고 순서만으로 갈린다.

    # ── 행 단위 구조 상태
    def row_state(a):
        pre = []
        if len(a["capp"]) == 0:
            pre.append(("PROVENANCE_UNVERIFIABLE", "|c_APP|=0 (도입 지점 파생 불가)"))
        if len(a["capp"]) > 1:
            pre.append(("APPROVAL_MALFORMED", "|c_APP|=%d>1 (동일 승인 행 병렬 독립 도입) %s"
                        % (len(a["capp"]), [x[:7] for x in a["capp"]])))
        g14 = []
        if a["_g4"]:
            g14.append(("APPROVAL_MALFORMED", "g4 rationale_ref 미해석"))
        if not a["_matching_edges"]:
            g14.append(("APPROVAL_MALFORMED",
                        "고아 — 대응 간선 0 (row_id 간선 %d · g1 transition 전건 불일치)" % len(a["_rowid_edges"])))
        seq = (pre + g14) if EVAL_ORDER == "precheck-first" else (g14 + pre)
        return seq[0] if seq else None

    for a in L:
        st = row_state(a)
        if st:
            add(f"row[{a['row_id']}/{a['transition']}]", st[0], st[1])

    # ── 간선 단위
    def cand_state(a, p, c, kind):
        """한 후보 행 a 가 간선 (p→c) 에 대해 도달하는 상태 (없으면 None = 덮음)."""
        capp1 = a["capp"][0] if len(a["capp"]) == 1 else None
        CR, CRB = (c_r_set(c, a["reviewer_ref"], a["aah"]) if capp1 else ([], []))
        pre = []
        if len(a["capp"]) == 0:
            pre.append(("PROVENANCE_UNVERIFIABLE", "|c_APP|=0"))
        elif capp1 and not CR:
            pre.append(("PROVENANCE_UNVERIFIABLE",
                        "g6 C_R=∅" + (" [SHALLOW] 경계 커밋 %s 로 확정 불가" % [x[:7] for x in CRB] if CRB else "")))
        if len(a["capp"]) > 1:
            pre.append(("APPROVAL_MALFORMED", "|c_APP|>1"))
        if a["_g4"]:
            pre.append(("APPROVAL_MALFORMED", "g4"))
        g1v = [("APPROVAL_MALFORMED", f"g1 {a['transition']}≠{kind}")] if a["transition"] != kind else []
        head = (pre + g1v) if EVAL_ORDER == "precheck-first" else (g1v + pre)
        if head:
            return head[0]
        if capp1 is None:
            return ("PROVENANCE_UNVERIFIABLE", "|c_APP|≠1 — g-단락 진입 불가")
        # ② g-단락 (5~11) — |c_APP|=1 의 «유일 원소»만 쓴다
        if capp1 == c:
            return ("APPROVAL_SAME_COMMIT", f"U-16-c c_APP={capp1[:7]} == 간선 커밋")
        if not strict_anc(capp1, c):
            return ("APPROVAL_AFTER", f"U-16-c c_APP={capp1[:7]} 가 {c[:7]} 의 진 조상 아님")
        if a["_g2"]:
            return ("APPROVAL_CONTENT_DRIFT", "g2 재계산 digest ≠ 원장 보유값")
        if g3_bad(a, c):
            return ("APPROVAL_HEAD_INVALID", "g3 approved_at_head 비조상·그 시점 blob 소비 불가")
        if g5_bad(a, capp1):
            return ("APPROVAL_ROW_MUTATED", "g5 c_APP 시점 행 ≠ 현행 행")
        if h_bad(a):
            return ("APPROVAL_UNBOUND", "h digest ∉ blob(approved_at_head:reviewer_ref)")
        if not any(strict_anc(x, capp1) for x in CR):
            return ("APPROVAL_ORDER_INVALID",
                    "g6 C_R={%s} 에 c_APP 진 조상 증인 없음" % ",".join(x[:7] for x in CR))
        return None

    for rid, E in edges.items():
        for i, (p, c, kind) in enumerate(E, 1):
            cands = [a for a in L if a["row_id"] == rid]
            corr = [a for a in cands if a["transition"] == kind] if EVAL_ORDER == "precheck-first" else cands
            covers, fails = [], []
            for a in corr:
                st = cand_state(a, p, c, kind)
                (covers if st is None else fails).append((a, st))
            tag = f"edge#{i}[{rid} {(p or 'ROOT')[:7]}->{c[:7]} {kind}]"
            crs = {tuple(c_r_set(c, a["reviewer_ref"], a["aah"])[0]) for a in corr if len(a["capp"]) == 1}
            crtxt = " C_R=" + "|".join("{" + ",".join(x[:7] for x in cr) + "}" for cr in crs) if crs else ""
            if len(covers) == 1:
                print(f"  · {tag}: COVERED by c_APP={covers[0][0]['capp'][0][:7]}{crtxt}")
            elif len(covers) > 1:
                add(tag, "APPROVAL_MALFORMED",
                    "이중 덮음 %s" % [x[0]["capp"][0][:7] for x in covers])
            elif not fails:
                add(tag, "APPROVAL_MISSING", f"덮는 행 부재 (후보 {len(cands)} · 대응 {len(corr)}){crtxt}")
            else:
                st = min((f[1] for f in fails), key=lambda s: TO[s[0]])
                add(tag, st[0], f"{st[1]} (후보 {len(cands)} · 대응 {len(corr)}){crtxt}")

    if not no_rows:
        emit("NO_ROWS_CLEAR", "closable=NO 행 없음(판정 우주 ∅ — 공허 통과가 아니라 대상 없음)", executed)
    if contributions:
        best = min(contributions, key=lambda t: TO[t[1]])
        allst = sorted({c[1] for c in contributions}, key=lambda s: TO[s])
        emit(best[1], f"전순서 최소 = {best[1]}({TO[best[1]]}) @ {best[0]} — {best[2]} · 발화 전체={allst}", executed)
    emit("NO_ROWS_CLEAR", "모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0", executed)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print("rules_executed=\nrules_missing=(예외)\nclosable_no_provenance_state=PROVENANCE_UNVERIFIABLE")
        print(f"reason=판정 미산출: {e!r}")
        sys.exit(1)
```

### 8-2. 드라이버 `t82v220.sh` (sha256 `0aa32961c912b5f30cdbb08259e82eda84609abe99149bb861c98d833ebf1867` · 277행)

```bash
#!/usr/bin/env bash
# t82v220.sh — T-82 (계약 v2.20 동결 3d17ea66) — 격리 스냅샷 기층 위에서 «전 규칙» 실행기로 실행한다.
#   ⑮(R∥A + g6 «생략» 대조군) · ⑯(선형 반복·현행 스키마) · ⑱(병렬 반복·현행 스키마) + edge_seq 소비 변형 대조군
#   · ⑳ⓐ(형제 동일 행) · ⑳ⓑ(얕은 클론 선-검사) · ⑳ⓒ(부모신뢰 TOCTOU — SIMULATED 훅 interleaving)
#   · 회귀 ⑰ⓐⓑⓒ·⑲·⑪·자인 잔여 · U-17 축 스냅샷 적용(D·P 조상성) 1픽스처.
#   t82v219.sh 에서 파생 — 실행기 교체(v220) + 대조군 3종 추가 + ⑮/⑯/⑳ⓒ/U-17축 절 추가.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence
SP19=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u16-full-exec-v220.py"                 # 판정 실행기 — 격리 스냅샷 기층
CTRL="$SP/u16-order-ctrl-g1first-v220.py"      # 대조군 D — EVAL_ORDER 한 줄 (⑳ⓑ)
EXG6="$SP/u16-g6omit-v220.py"                  # 대조군 B — g6 «생략» (⑮)
EXSEQ="$SP/u16-edgeseq-v220.py"                # 대조군 C — 폐지 edge_seq 기재값 소비 (⑯·⑱)
EXNS="$SP/u16-nosnap-v220.py"                  # 대조군 A — 격리 스냅샷 «없음» (⑳ⓒ)
EX215="$SP19/u16-full-exec-v215.py"            # 직전 판 부속 — «복수면 사전순 최소» (⑳ⓐ)
EXCAN="$SP/u16-canary-literal-v220.py"         # 대조군 E — canary 의 ㉠ 를 계약 :7124 «항상 성립» 문언대로 «문자» 구현 (얕음 국소화 없음)
FX="$SP/fx82v220"; REF=reviews/review.md; RAT=rationale/r1.md
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
dig(){ python3 -c "import hashlib,sys; r=dict(id=sys.argv[1],closable=sys.argv[2],owner_track=sys.argv[3]); print(hashlib.sha256(b'\0'.join(f'{k}={r[k]}'.encode() for k in sorted(r))).hexdigest())" "$@"; }
DNO=$(dig r1 NO tos)     # 승인 대상 = 제안된 NO 행 (id=r1, closable=NO, owner_track=tos)
reg(){ printf 'id,closable,owner_track\n'; for kv in "$@"; do printf '%s\n' "$kv"; done; }
c(){ git -C "$1" add -A && git -C "$1" commit -q --allow-empty -m "$2" && git -C "$1" rev-parse --short HEAD; }
base(){ rm -rf "$1"; git init -q -b main "$1"; mkdir -p "$1/reviews" "$1/rationale"
  reg 'other,YES,x' 'r1,YES,tos' > "$1/register.csv"; echo "## ledger" > "$1/LEDGER.md"; echo "rationale for r1 NO" > "$1/$RAT"
  echo "rationale (approver a)" > "$1/rationale/r1-a.md"; echo "rationale (approver b)" > "$1/rationale/r1-b.md"
  case "${2:-full}" in full) printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$1/$REF";; carrier) printf '%s\n' "$DNO" > "$1/$REF";; unrelated) printf 'unrelated review text\n' > "$1/$REF";; none) ;; esac
  c "$1" "H0: base (r1=YES; reviewer=${2:-full})"; }
row(){ printf 'r1 | %s | %s | %s | %s | %s\n' "$1" "$DNO" "$2" "$REF" "${3:-$RAT}"; }
setNO(){ reg 'other,YES,x' 'r1,NO,tos' > "$1/register.csv"; }
setYES(){ reg 'other,YES,x' 'r1,YES,tos' > "$1/register.csv"; }
run(){ git -C "$1" log --graph --oneline --all | sed 's/^/  /'; echo "\$ python3 $(basename "${2:-$EX}") <fixture>"; python3 "${2:-$EX}" "$1"; echo "u16_rc=$?"; }
mergeled(){ git -C "$1" merge -q --no-ff -m "$3" "$2" 2>/dev/null || { { echo "## ledger"; git -C "$1" show HEAD:LEDGER.md | tail -n +2; git -C "$1" show "$2":LEDGER.md | tail -n +2; } | awk '!seen[$0]++' > "$1/LEDGER.md"; git -C "$1" add -A; git -C "$1" commit -q -m "$3"; }; }

rm -rf "$FX"; mkdir -p "$FX"
printf 't82v220_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for f in "$EX" "$CTRL" "$EXG6" "$EXSEQ" "$EXNS" "$EXCAN" "$EX215"; do printf 'sha256(%s)=%s\n' "$(basename "$f")" "$(shasum -a 256 "$f" | cut -d" " -f1)"; done
printf -- '-- 대조군 파일 diff (판정 실행기 대비 «한 축»만 다름) --\n'
for f in "$CTRL" "$EXG6" "$EXSEQ" "$EXNS" "$EXCAN"; do printf '  %s: %s 행\n' "$(basename "$f")" "$(diff "$EX" "$f" | grep -c '^[<>]')"; done
printf 'git version = %s\n' "$(git --version)"
echo "D_NO(row_content_digest of proposed r1 NO row) = $DNO"
echo "계약 U-16-d 전순서: 1 CONSUMER_ABSENT · 2 PROVENANCE_UNVERIFIABLE · 3 APPROVAL_MALFORMED · 4 APPROVAL_MISSING · 5 SAME_COMMIT · 6 AFTER · 7 CONTENT_DRIFT · 8 HEAD_INVALID · 9 ROW_MUTATED · 10 UNBOUND · 11 ORDER_INVALID · 12 NO_ROWS_CLEAR"

########################################################################
sec "T-82 ⑱-1 [현행 스키마] 병렬 반복 이력(양성) — ABSENT->NO->YES->NO 두 간선을 «서로 다른 승인 행»이 각각 덮고, 두 도입이 형제 브랜치 → merge · edge_seq 기재 없음 ⇒ NO_ROWS_CLEAR"
R="$FX/18-1"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"
echo "rationale (approver a)" > "$R/rationale/r1-a.md"; echo "rationale (approver b)" > "$R/rationale/r1-b.md"
printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; H0=$(c "$R" "H0: r1 absent (reviewer artifact with digest)")
# 두 승인 행의 «도입»을 형제 브랜치에 두고 merge (원장만 건드린다 — 레지스터 무변경 · edge_seq 기재 없음)
git -C "$R" checkout -q --detach "$H0"; row ABSENT-\>NO "$H0" rationale/r1-a.md >> "$R/LEDGER.md"; A1=$(c "$R" "A1: approval row (ABSENT->NO, rationale a) [branch a]")
git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$H0" rationale/r1-b.md >> "$R/LEDGER.md"; A2=$(c "$R" "A2: approval row (YES->NO, rationale b) [branch b]")
git -C "$R" checkout -q --detach "$A1"; mergeled "$R" "$A2" "MA: merge sibling approval introductions (union)"
MA=$(git -C "$R" rev-parse --short HEAD)
# 반복 이력: ABSENT->NO (e1) → back to YES → YES->NO (e2)  — 두 간선 모두 MA 의 자손이다
setNO "$R"; E1=$(c "$R" "e1: ABSENT->NO"); setYES "$R"; HY=$(c "$R" "back to YES"); setNO "$R"; E2=$(c "$R" "e2: YES->NO")
git -C "$R" branch -f main HEAD
echo "H0=$H0 A1=$A1 A2=$A2 MA=$MA e1=$E1 e2=$E2"; echo "-- LEDGER@HEAD --"; git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'
echo "-- g5 구 승인 행 불변 확인: A1·A2 도입 시점 행 (HEAD 행과 byte 동일이어야 한다) --"
git -C "$R" show "$A1:LEDGER.md" | tail -n +2 | sed 's/^/  A1| /'; git -C "$R" show "$A2:LEDGER.md" | tail -n +2 | sed 's/^/  A2| /'; run "$R"

sec "T-82 ⑱-2 [문언 리터럴 «별개 row_id»] 같은 반복 이력을 «서로 다른 row_id» 승인 행으로 덮으면? (관측 보고 대상)"
R="$FX/18-2"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"
printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; H0=$(c "$R" "H0: r1 absent")
git -C "$R" checkout -q --detach "$H0"; printf 'r1 | ABSENT->NO | %s | %s | %s | %s\n' "$DNO" "$H0" "$REF" "$RAT" >> "$R/LEDGER.md"; B1=$(c "$R" "B1: approval row_id=r1")
git -C "$R" checkout -q --detach "$H0"; printf 'r1b | YES->NO | %s | %s | %s | %s\n' "$DNO" "$H0" "$REF" "$RAT" >> "$R/LEDGER.md"; B2=$(c "$R" "B2: approval row_id=r1b (문언 «별개 row_id»)")
git -C "$R" checkout -q --detach "$B1"; mergeled "$R" "$B2" "MB: merge sibling approvals"; MB=$(git -C "$R" rev-parse --short HEAD)
setNO "$R"; c "$R" "e1: ABSENT->NO" >/dev/null; setYES "$R"; c "$R" "back to YES" >/dev/null; setNO "$R"; E2=$(c "$R" "e2: YES->NO")
git -C "$R" branch -f main HEAD
git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'; run "$R"

########################################################################
sec "T-82 ⑳ⓐ 동일 승인 행 형제 독립 도입 → |c_APP(a)|=2 ⇒ APPROVAL_MALFORMED(3) + rc≠0"
# X(조상 도입) 가 Y(형제 도입) 보다 «사전순으로 앞서도록» 구성한다 — «복수면 사전순 최소» 구현이 조상을 골라 통과하는 최악 케이스를 실측하기 위함
n=0
while :; do
  R="$FX/20a"; H0=$(base "$R")
  git -C "$R" checkout -q --detach; row YES-\>NO "$H0" >> "$R/LEDGER.md"; X=$(c "$R" "X: approval row A [branch x nonce=$n]")
  setNO "$R"; CN=$(c "$R" "CN: NO transition (child of X)")
  git -C "$R" checkout -q --detach main; row YES-\>NO "$H0" >> "$R/LEDGER.md"; Y=$(c "$R" "Y: approval row A (byte-identical) [branch y nonce=$n]")
  XF=$(git -C "$R" rev-parse "$X"); YF=$(git -C "$R" rev-parse "$Y")
  [ "$XF" \< "$YF" ] && break
  n=$((n+1)); [ "$n" -lt 60 ] || { echo "  (nonce 60회 내 X<Y 구성 실패 — 그대로 진행)"; break; }
done
git -C "$R" checkout -q --detach "$CN"; mergeled "$R" "$Y" "M: merge sibling identical approval introduction"; git -C "$R" branch -f main HEAD
echo "H0=$H0 X=$X(=$XF) CN=$CN Y=$Y(=$YF)  [사전순: $( [ "$XF" \< "$YF" ] && echo 'X < Y — 사전순 최소 = 조상 도입' || echo 'Y < X')]"
echo "-- LEDGER@HEAD (형제 두 도입이 «같은 한 줄» 로 합쳐진다) --"; git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'; run "$R"

sec "T-82 ⑳ⓐ 판별력 대조 — 같은 픽스처를 «복수면 사전순 최소» 구현(직전 판 부속 u16-full-exec-v215.py)으로 실행 → 조상 도입을 골라 통과하면 그것이 F5 «회피»의 실증"
run "$R" "$EX215"

########################################################################
sec "T-82 ⑳ⓑ 선-검사 순서 corner — 형제 동일 행 도입을 «얕은 클론»에서 실행: |c_APP|=0 ∧ g1 위배 동시 성립 ⇒ PROVENANCE_UNVERIFIABLE(2) + rc≠0"
SH="$FX/20b-shallow"; rm -rf "$SH"
git clone -q --depth 1 "file://$FX/20a" "$SH" 2>/dev/null
echo "-- 얕은 클론 확인 --"
echo "  is-shallow-repository = $(git -C "$SH" rev-parse --is-shallow-repository)"
echo "  rev-list HEAD 개수    = $(git -C "$SH" rev-list HEAD | wc -l | tr -d ' ')"
echo "  parents(HEAD)         = $(git -C "$SH" log --format=%P -1 HEAD)  (객체 실재? $(for p in $(git -C "$SH" log --format=%P -1 HEAD); do git -C "$SH" cat-file -e "$p^{commit}" 2>/dev/null && echo -n "$p=present " || echo -n "$p=ABSENT "; done))"
echo "-- 원장·레지스터 @HEAD --"; git -C "$SH" show HEAD:LEDGER.md | sed 's/^/  | /'; git -C "$SH" show HEAD:register.csv | sed 's/^/  | /'
run "$SH"

sec "T-82 ⑳ⓑ 판별력 대조 — 같은 얕은 클론을 «g1·g4 먼저» 문자 구현(u16-order-ctrl-g1first.py)으로 실행 → APPROVAL_MALFORMED(3) 이면 «실패»(전순서 최소 = 2)"
run "$SH" "$CTRL"

sec "T-82 ⑳ⓑ 관측 대조 — 같은 얕은 클론을 «canary ㉠ = 항상 성립» 문언(계약 :7124)의 «문자» 구현(대조군 E)으로 실행 → 스냅샷이 얕음을 «상속»하므로 canary 가 발화해 사유가 «기층 오염»으로 바뀐다(E12 관할과 충돌 — 관측 보고)"
run "$SH" "$EXCAN"

########################################################################
sec "회귀 ⑯ — ABSENT->NO->YES->NO, 간선별 별도 승인 (선형) ⇒ NO_ROWS_CLEAR"
R="$FX/16"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; H0=$(c "$R" "H0: r1 absent")
row ABSENT-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A1=$(c "$R" "A1: approval (ABSENT->NO)"); setNO "$R"; E1=$(c "$R" "e1: ABSENT->NO")
setYES "$R"; H2=$(c "$R" "back to YES")
row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A2=$(c "$R" "A2: approval (YES->NO)"); setNO "$R"; E2=$(c "$R" "e2: YES->NO")
git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'; run "$R"

sec "회귀 ⑰ⓐ 기존-경로 B∥A (blob C_R) ⇒ APPROVAL_ORDER_INVALID(11)"
R="$FX/17a"; H0=$(base "$R" unrelated)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B=$(c "$R" "B: real review content (digest) into existing path")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$B")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=B) [parallel to B]")
git -C "$R" merge -q --no-ff -m "M0: merge B" "$B"; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B=$B A=$A M=$M"; run "$R"

sec "회귀 ⑰ⓑ 머지 해소에서 digest blob 도입 ⇒ APPROVAL_UNBOUND(10) [v2.15 E2 에라타 기대값]"
R="$FX/17b"; H0=$(base "$R" unrelated)
git -C "$R" checkout -q --detach; printf 'unrelated review text\nB-side edit (no digest)\n' > "$R/$REF"; B=$(c "$R" "B: reviewer edit without digest")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$B")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=B — B lacks digest)")
git -C "$R" merge -q --no-commit --no-ff "$B" >/dev/null 2>&1 || true; printf 'independent review of r1 -> NO (introduced in merge resolution)\n%s\n' "$DNO" > "$R/$REF"; setNO "$R"; M=$(c "$R" "M: merge — digest blob introduced in resolution + NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B=$B A=$A M=$M"; run "$R"
echo "-- ⑰ⓑ g6 단독 뷰 (target=blob(M:ref), c=M, c_APP=A) --"
python3 - "$R" "$REF" "$M" "$A" <<'PY'
import subprocess,sys
R,REF,C,CAPP=sys.argv[1:5]
def g(*a): return subprocess.run(["git","-C",R,*a],capture_output=True,text=True).stdout.strip()
def ok(*a): return subprocess.run(["git","-C",R,*a],capture_output=True).returncode==0
def blob(c): return g("rev-parse","--quiet","--verify",f"{c}:{REF}") or "ABSENT"
tgt=blob(C); CR=[x for x in g("rev-list",C).splitlines() if blob(x)==tgt and all(blob(p)!=tgt for p in g("log","--format=%P","-1",x).split())]
print(f"  C_R(target=blob(M))={{{','.join(x[:7] for x in CR)}}}"); w=[x for x in CR if x!=g("rev-parse",CAPP) and ok("merge-base","--is-ancestor",x,CAPP)]
print("  g6_verdict=" + ("OK" if w else "APPROVAL_ORDER_INVALID"))
PY

sec "회귀 ⑰ⓒ 양성 — B1·B2 독립 동일 blob, A ⊐ B1 ⇒ NO_ROWS_CLEAR"
R="$FX/17c"; H0=$(base "$R" unrelated)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B1=$(c "$R" "B1: review content (digest)"); row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval (aah=B1)")
git -C "$R" checkout -q --detach main; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B2=$(c "$R" "B2: independent identical blob")
git -C "$R" checkout -q --detach "$A"; git -C "$R" merge -q --no-ff -m "M0: merge B2" "$B2" 2>/dev/null || { git -C "$R" checkout --theirs "$REF"; git -C "$R" add -A; git -C "$R" commit -q -m "M0: merge B2"; }; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B1=$B1 A=$A B2=$B2 M=$M"; run "$R"

sec "회귀 ⑲ digest 선배치 ⇒ APPROVAL_ORDER_INVALID(11)"
R="$FX/19"; H0=$(base "$R" carrier)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B=$(c "$R" "B: real review content (digest kept)")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$B")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=B) [parallel]")
git -C "$R" merge -q --no-ff -m "M0: merge B" "$B"; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B=$B A=$A M=$M"; run "$R"
echo "-- ⑲ v2.14 토큰 기반 C_R 대조 --"
python3 - "$R" "$REF" "$M" "$A" "$DNO" <<'PY'
import subprocess,sys
R,REF,C,CAPP,DIG=sys.argv[1:6]
def g(*a): return subprocess.run(["git","-C",R,*a],capture_output=True,text=True).stdout.strip()
def ok(*a): return subprocess.run(["git","-C",R,*a],capture_output=True).returncode==0
def has(c):
    r=subprocess.run(["git","-C",R,"show",f"{c}:{REF}"],capture_output=True,text=True); return r.returncode==0 and DIG in r.stdout
CR=[x for x in g("rev-list",C).splitlines() if has(x) and all(not has(p) for p in g("log","--format=%P","-1",x).split())]
print(f"  token C_R={{{','.join(x[:7] for x in CR)}}}  witness={'YES(green — 선배치 우회 통과)' if any(x!=g('rev-parse',CAPP) and ok('merge-base','--is-ancestor',x,CAPP) for x in CR) else 'NO'}")
PY

sec "회귀 ⑮ 신규 아티팩트 R ∥ A ⇒ APPROVAL_ORDER_INVALID(11)"
R="$FX/15"; H0=$(base "$R" none)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; RR=$(c "$R" "R: new reviewer artifact")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$RR")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval (aah=R) [parallel]")
git -C "$R" merge -q --no-ff -m "M0: merge R" "$RR"; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 R=$RR A=$A M=$M"; run "$R"

sec "회귀 ⑪ transition 명세 불일치 (원장 YES->NO · 실제 파생 간선 ABSENT->NO) ⇒ APPROVAL_MALFORMED(3)"
R="$FX/11"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; H0=$(c "$R" "H0: r1 absent")
row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval claims YES->NO"); setNO "$R"; E=$(c "$R" "e: actual edge is ABSENT->NO")
git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'; run "$R"

sec "자인 잔여 — 단일 행이 두 간선을 덮는다 (계약 «닫지 못하는 것» 정직 표기 그대로)"
R="$FX/one"; H0=$(base "$R")
row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A=$(c "$R" "A: SINGLE approval row"); setNO "$R"; E1=$(c "$R" "e1: YES->NO"); setYES "$R"; c "$R" "back to YES" >/dev/null; setNO "$R"; E2=$(c "$R" "e2: YES->NO (no new approval)")
git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'; run "$R"

########################################################################
sec "[v2.20 #2] T-82 ⑮ 판별력 대조 — 같은 R∥A 픽스처를 «g6 생략» 소비자(U-16-a2 전칭을 «(g1~g5)» 닫힌 열거로 읽은 구현)로 실행 → green 이면 그것이 심판 #2 가 지목한 실패다"
run "$FX/15" "$EXG6"

sec "[v2.20 #4] T-82 ⑯ 판별력 대조 — 선형 반복 이력을 «폐지 edge_seq 기재값» 소비 구현으로 실행 → MALFORMED(영구 차단) 이면 그것이 v2.13 롤백 결함이다"
run "$FX/16" "$EXSEQ"

sec "[v2.20 #4] T-82 ⑱ 판별력 대조 — 병렬 반복 이력을 «폐지 edge_seq 기재값» 소비 구현으로 실행"
run "$FX/18-1" "$EXSEQ"

########################################################################
sec "[v2.20 #3] T-82 ⑳ⓒ 부모신뢰 TOCTOU — SIMULATED 훅 interleaving (조상성 조회 «중»에만 graft 설치·조회 후 제거)"
# 픽스처: ⑮ 와 같은 R∥A 구성이되 «후보 우주 밖» 커밋 H0 의 부모를 재작성해 R ⊰ CN 조상성만 뒤집는다.
R="$FX/20c"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' 'r1,YES,tos' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"
S0=$(c "$R" "S0: register/ledger-header/rationale (리뷰어 경로 없음)")
printf 'unrelated\n' > "$R/note.md"; H0=$(c "$R" "H0: unrelated only (리뷰어 blob 없음·원장 행 없음) ⇒ 후보 우주 «밖»")
git -C "$R" checkout -q --detach "$S0"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; RR=$(c "$R" "R: reviewer artifact (digest)")
git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$(git -C "$R" rev-parse "$RR")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=R)")
setNO "$R"; CN=$(c "$R" "CN: NO transition")
git -C "$R" merge -q --no-ff -m "M: merge reviewer branch" "$RR" 2>/dev/null || { git -C "$R" add -A; git -C "$R" commit -q -m "M: merge reviewer branch"; }
git -C "$R" branch -f main HEAD; M=$(git -C "$R" rev-parse --short HEAD)
GRAFT_LINE="$(git -C "$R" rev-parse "$H0") $(git -C "$R" rev-parse "$S0") $(git -C "$R" rev-parse "$RR")"
echo "  S0=$S0 H0=$H0(재작성 대상·후보 밖) R=$RR A=$A CN=$CN M=HEAD=$M"
echo "  graft 줄(설치될 내용) = $GRAFT_LINE"
git -C "$R" log --oneline --graph --all | sed 's/^/  /'
# SIMULATED 훅: `merge-base --is-ancestor` «호출 중에만» grafts 를 설치하고 즉시 제거한다 (관측 직전·직후엔 부재)
SHIM="$FX/shim20c"; rm -rf "$SHIM"; mkdir -p "$SHIM"; REALGIT=$(command -v git)
cat > "$SHIM/git" <<SHIMEOF
#!/bin/sh
# [T-82 ⑳ⓒ SIMULATED 훅] 조상성 조회 «중»에만 후보 «밖» 커밋의 부모를 재작성한다 (조회 후 즉시 제거).
case " \$* " in
  # ㉠ 의 교차검사(log --format=%P · cat-file)는 «건드리지 않는다» — 관측이 참을 보게 두고
  # 조상성 «소비»(rev-list · merge-base)만 재작성한다.  이것이 계약이 말한 TOCTOU 창이다.
  *" log "*|*" cat-file "*) exec $REALGIT "\$@" ;;
  *" rev-list "*|*" merge-base --is-ancestor "*)
      mkdir -p "$R/.git/info"; printf '%s\n' "$GRAFT_LINE" > "$R/.git/info/grafts"
      $REALGIT "\$@"; rc=\$?
      rm -f "$R/.git/info/grafts"
      exit \$rc ;;
esac
exec $REALGIT "\$@"
SHIMEOF
chmod +x "$SHIM/git"
echo "  shim sha256 = $(shasum -a 256 "$SHIM/git" | cut -d' ' -f1) · 실 git = $REALGIT"
echo "  훅 «밖» 관측: grafts 파일 = $( [ -f "$R/.git/info/grafts" ] && echo present || echo ABSENT ) (㉡ 은 관측 시점에 항상 부재를 본다)"
echo "  훅 «안» 효과: is-ancestor(R,CN) = rc $(PATH="$SHIM:$PATH" git -C "$R" merge-base --is-ancestor "$RR" "$CN"; echo $?)  (0 = 조상성 뒤집힘) · 훅 밖 = rc $(git -C "$R" merge-base --is-ancestor "$RR" "$CN"; echo $?)"
echo "  훅 실행 «후» grafts = $( [ -f "$R/.git/info/grafts" ] && echo present || echo ABSENT )"

sec "⑳ⓒ (a) 격리 스냅샷 «없는» 소비자(대조군 A) + interleaving 훅 ⇒ 뒤집히면 실패"
git -C "$R" log --graph --oneline --all | sed 's/^/  /'; echo "\$ PATH=<shim>:\$PATH python3 $(basename "$EXNS") <fixture>"
PATH="$SHIM:$PATH" python3 "$EXNS" "$R"; echo "u16_rc=$?"

sec "⑳ⓒ (b) 격리 스냅샷 «기층» 판정 실행기 + 같은 훅 ⇒ 스냅샷 조상성 불변"
echo "\$ PATH=<shim>:\$PATH python3 $(basename "$EX") <fixture>"
PATH="$SHIM:$PATH" python3 "$EX" "$R"; echo "u16_rc=$?"

sec "⑳ⓒ (c) 정직 이력(훅 없음) — 판정 실행기 기준선"
run "$R"

sec "⑳ⓒ (d) 정직 경계 (a) 실증 — 원본 grafts 가 «참 부모»를 고아화하면 스냅샷 «생성»이 실패한다(fail-closed·거짓 통과 없음)"
R2="$FX/20c-orphan"; rm -rf "$R2"; cp -R "$R" "$R2"
ORPHAN="$(git -C "$R2" rev-parse "$M") $(git -C "$R2" rev-parse "$S0")"
mkdir -p "$R2/.git/info"; printf '%s\n' "$ORPHAN" > "$R2/.git/info/grafts"
echo "  grafts(고아화) = $ORPHAN   (HEAD 의 부모를 S0 로 재작성 → 참 부모들이 도달 불가)"
echo "\$ python3 $(basename "$EX") <fixture-with-orphaning-grafts>"; python3 "$EX" "$R2"; echo "u16_rc=$?"

########################################################################
sec "[v2.20 #3] U-17 축 스냅샷 적용 — D·P 조상성도 스냅샷 «안»에서 소비한다 (같은 interleaving 훅)"
R3="$FX/u17snap"; rm -rf "$R3"; git init -q -b main "$R3"; mkdir -p "$R3/.github/workflows" "$R3/config" "$R3/tos-spec/src/part-1-foundation/decisions"
echo seed > "$R3/seed.md"; SEED=$(c "$R3" "seed")
printf 'name: tos-gate\non: [pull_request]\n' > "$R3/.github/workflows/tos-gate.yml"; W=$(c "$R3" "W: workflow (후보 우주 «밖» — 아티팩트·config 경로 없음)")
printf 'x: 1\n' > "$R3/config/tos_completion.yaml"; D1=$(c "$R3" "d: introduce config/tos_completion.yaml (D 후보)")
git -C "$R3" checkout -q --detach "$SEED"; printf 'owner_repo: x\n' > "$R3/tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md"; P1=$(c "$R3" "P: artifact (P_first/P_last 후보)")
git -C "$R3" checkout -q --detach "$D1"; git -C "$R3" merge -q --no-ff -m "M: merge artifact branch" "$P1" 2>/dev/null || { git -C "$R3" add -A; git -C "$R3" commit -q -m "M: merge artifact branch"; }
git -C "$R3" branch -f main HEAD
GL3="$(git -C "$R3" rev-parse "$W") $(git -C "$R3" rev-parse "$SEED") $(git -C "$R3" rev-parse "$P1")"
echo "  seed=$SEED W=$W(후보 밖·재작성 대상) d=$D1 P=$P1 HEAD=$(git -C "$R3" rev-parse --short HEAD)"
echo "  graft 줄 = $GL3"
echo "  정직 이력: is-ancestor(P,d) rc=$(git -C "$R3" merge-base --is-ancestor "$P1" "$D1"; echo $?)  (1 = P ⋠ d = LATE 진실)"
mkdir -p "$R3/.git/info"; printf '%s\n' "$GL3" > "$R3/.git/info/grafts"
echo "  graft 설치 후(원 저장소): is-ancestor(P,d) rc=$(git -C "$R3" merge-base --is-ancestor "$P1" "$D1"; echo $?) · --no-replace-objects 하 rc=$(git -C "$R3" --no-replace-objects merge-base --is-ancestor "$P1" "$D1"; echo $?)  (K-4: grafts 는 무력화로 안 꺼진다)"
SNAP3="$FX/u17snap-clone"; rm -rf "$SNAP3"
echo "\$ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks <origin> <snap>"
GIT_NO_REPLACE_OBJECTS=1 git clone --quiet --no-local --no-hardlinks "$R3" "$SNAP3" 2>&1 | sed 's/^/  | /'; echo "  clone rc=${PIPESTATUS[0]}"
if [ -d "$SNAP3/.git" ]; then
  echo "  스냅샷 canary: replace -l=[$(git -C "$SNAP3" replace -l | tr '\n' ' ')] · grafts=$( [ -f "$SNAP3/.git/info/grafts" ] && echo present || echo ABSENT ) · is_shallow=$(git -C "$SNAP3" rev-parse --is-shallow-repository)"
  echo "  스냅샷 조상성: is-ancestor(P,d) rc=$(git -C "$SNAP3" merge-base --is-ancestor "$P1" "$D1"; echo $?)  (1 = 참 조상성 = LATE 유지 · 원본 graft 미전파)"
  echo "  ㉠ 대조(스냅샷): $(for x in $(git -C "$SNAP3" rev-list --all); do tp=$(git -C "$SNAP3" --no-replace-objects cat-file commit "$x" | awk '/^$/{exit} /^parent /{printf "%s ", $2}'); ap=$(git -C "$SNAP3" log --format=%P -1 "$x"); [ "$(echo $tp)" = "$(echo $ap)" ] || printf 'MISMATCH:%s ' "$x"; done; echo '불일치 0건')"
fi
rm -f "$R3/.git/info/grafts"
```

대조군 5종은 §2-1 의 `diff` 원문으로 전량 재구성 가능하다(판정 실행기 + 표기된 한 축).

## 9. 관측 보고 · 결함 후보 (등급 명시)

### N-1 **[문언 — 계약이 실행과 어긋난 자리]** 계약 :7124 «㉠==%P 는 항상 성립하는 canary» vs :7148-7152 E12 «㉢ 먼저·국소 귀속»

- 계약 `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:7124-7125` 은 «깨끗한 기층에서 ㉠(재파생)==`%P`·㉡(부재)는 **항상 성립하는 canary**»라고 적는다.
- 그러나 **원본이 얕은 클론이면 스냅샷도 얕음을 상속**하고(실측: `is_shallow=true`), 얕은 «경계» 커밋은 `cat-file` 부모 有 vs `%P` ∅ 라 **㉠ 불일치를 정상적으로 만든다**(계약 :7148-7152 E12 가 명시한 그 사실).
- 실측: 문언을 «문자» 구현한 대조군 E 는 ⑳ⓑ 픽스처에서 `기층 오염` 을 사유로 방출해 **`|c_APP|=0` 이라는 참 사유를 덮었다**. 판정 실행기(E12 국소화 적용)는 계약 기대 사유(`|c_APP|=0`)를 낸다.
- **등급: 문언**(극성은 양쪽 다 fail-closed 이므로 fail-open 아님). 제안: :7124 의 canary 문장에 «단, ㉢ 얕은 경계 귀속분은 E12 관할» 을 명시.

### N-2 **[관측]** ⑳ⓒ 의 fail-open 은 «조상성 소비만» 재작성하는 훅에서만 재현된다

훅이 `log --format=%P`·`cat-file` 까지 재작성하면 ㉠ 가 즉시 발화해 차단된다(첫 실행에서 실측). 즉 **v2.19 의 ㉠+㉡ 조합은 «어설픈» 재작성을 이미 막고 있었고, v2.20 이 닫은 것은 «㉠ 교차검사를 피해가는» 창이다**. 계약 :7098-7104 의 서술과 정합하며, 이 구분을 증거에 남긴다. **등급: 관측.**

### N-3 **[관측]** ⑱-2(별개 `row_id`)는 `APPROVAL_MALFORMED`(고아)로 접힌다

v2.19 에라타 E4 가 «별개 `row_id` 가 아니라 같은 `row_id`·다른 내용» 이라고 마감한 그 자리의 재확인이다. 계약과 실행이 일치한다. **등급: 관측.**

### N-4 **[관측]** `edge_seq` 대조군은 «기재값 부재»를 불일치로 읽는다

현행 스키마 픽스처에는 `edge_seq` 열이 없으므로 폐지 필드 소비 구현은 `기재값(None) ≠ 파생 순번(1)` 로 MALFORMED 를 낸다 — 계약 ⑯/⑱ 이 예고한 «정상 이력 영구 차단»의 형태 그대로다. **등급: 관측(판별력 확인).**

### N-5 **[fail-open/차단 등급 신규 결함 후보 0]**

이 회차 U-16 축에서 **계약 문언을 그대로 구현했을 때 green 을 내는 자리는 발견되지 않았다.** N-1 은 «과잉 차단(사유 오귀속)» 방향이고 나머지는 관측이다.
