# Phase 0 완료 판정 — 완료 판단 시점 live 실측 기록 (3차 · main 착지 head)

> **Document class**: 비규범 **측정 전사**(측정 기록). Phase 0 완료 판정(계약 §11) 자체가
> 아니다 — verdict YAML·`operator_countersign`·판정 어휘를 포함하지 않는다. 완료의
> *결정*은 같은 디렉터리의 `PHASE0-COMPLETION-DECISION.md`(현재 `PENDING_OPERATOR_COUNTERSIGN`
> 초안)가 담당한다. 이 기록은 2026-09-04 실측 기록
> (`docs/reviews/phase0-completion-contract/20260904-171004/PHASE0-COMPLETION-JUDGMENT-LIVE.md`)과
> **같은 항목**을 main 착지 head 에서 다시 잰 것이다. 계약
> `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`, 상위 계획
> `docs/plans/2026-08-11-tos-completion-development-plan.md`, `tos-spec/`, `config/`, `tools/`,
> `.github/` 는 이 기록이 편집하지 않는다.
>
> `$S` = 측정 세션 스크래치 `p0rejudge/logs/`. 로그는 09-04 기록과 같이 커밋하지 않는다 —
> 아래 `utc=`·`x-github-request-id=`·행 번호가 재조회·대조의 근거다.

## §0 결속

| 항 | 값 | 09-04 대비 | 출처 |
| --- | --- | --- | --- |
| 측정 대상 head | `b15069fd1737962d92766e73648b0c2128957d32` = `origin/main` (PR #907 머지 커밋, `mergedAt=2026-10-20T14:41:35Z`) | 09-04 는 브랜치 head `d07646c2`(PR 미개설) | `$S/binding.log`, `$S/ci.log` |
| 측정 방식 | origin/main 분리 워크트리 · 추적 파일 변경 0 · 측정 뒤 워크트리 제거 | 동일 | — |
| 계약 blob | `6f94dfbbafd48fa3d1b4c73266fdfda19da9bce5` | **변경** (`899689fc…` → 에라타 57차 `5dfcb236` · 58차 `1db8f9b8`, 2026-09-05) | `$S/binding.log` |
| 상위 계획 blob | `ec3464c068dff2030e0764f3b05c985a821730f5` | 동일 | `$S/binding.log` |
| `bound_set_digest` 재계산 | `045f3ae7565860df6e0c38d3c7ee49c76f3a4d3784d646279cd1be2727dbb429` == `OQ-11-DISPOSITION.md` 값 == `20260905-214532/verdict.md:11` | **변경** (`4e6c975f…`) | `$S/binding.log` |
| U-15 R-7 currency `git rev-list --full-history 97596460..HEAD -- <두 bound path>` | `0` (`97596460` 은 HEAD 의 조상) | 동일 결과(0) | `$S/binding.log` |
| 참고: `1db8f9b8..HEAD --full-history` | `2` — `97596460`·`b3f1d2d5` 둘 다 머지 커밋, 두 bound path blob 은 양 부모에서 불변 | — | `$S/binding.log` |
| `tools/tos_entry_harness.sh` sha256 | `059e13f22397d53c53211895cc321fef81ab7925135b196e27315e813d723177` == `.github/workflows/tos-gate.yml:17` 핀 | 동일 | `$S/binding.log` |
| `tools/u17-verify.sh` sha256 | `0b68ef856836380817dac179aee07e09276dbd9cb66feea9817c669bcdf9814e` | 동일 | `$S/binding.log` |
| `D0A-PREVENTION-CONTROL.md` `operator_countersign` | `"chihun,lee 2026-08-28T05:23:48Z"` | 동일 (이 기록은 갱신하지 않는다) | `$S/binding.log` |
| U-17 (b)② `scope:` | `d=28475ca1…` · `landing_pr=638` · `landing_head=21c47e42…` · `check_run_id=100181808552` | 동일 | `U17-B2-DEVIATION-ACCEPTANCE.md:15-22` |
| gh 인증 | `kakao-harris-lee` · Active account: true · 전부 GET | 동일 | `$S/u17-live2.log:234-240` |
| 실행 UTC | u17 스크립트 `2026-10-21T13:38:38Z` ~ `13:40:05Z` | — | `$S/u17-live2.log:1,232` |

### 환경 전제 (이 호스트에서 U-17 을 재현하려면)

- 호스트 `gh 2.45.0` 은 `gh api --slurp` 를 모른다. 시스템 gh 로 돌린 1차 실행은 (b)① 조회가 전부
  `status=ERR` 가 되어 `prevention_control_state=PREVENTION_UNVERIFIABLE` 로 fail-closed 됐다
  (`$S/u17-live.log:147` `unknown flag: --slurp` · `:169-171`). **아래 §1 은 2차 실행**
  (스크래치 전용 standalone `gh 2.63.2`, sha256 `f687dc93…8618`)의 값이다.
- 호스트에 `yq` 가 없다. `tools/wfcanon-v222.py:114-116` 이 핀한 mikefarah `yq v4.48.x` 를
  스크래치 전용 standalone 바이너리(`v4.48.1`, sha256 `99df6047…fd9f`)로 썼다. 공유 venv 무접촉.

## §1 U-17 live 실측

명령: `PATH=<scratch bin>:$PATH U17_PYBIN=.venv/bin/python bash tools/u17-verify.sh .` · API 22건 전부
http=200 · 열거 완전성 전 엔드포인트 `RESULT=PAGES_OK`.

- 첫 호출 `U17-A00 apps/github-actions utc=2026-10-21T13:39:48Z http=200 x-github-request-id=C2AC:9B3FA:2114D0:372AEC:6AD8C0A1` (`:18`)
- 마지막 호출 `U17-BETA …/commits/21c47e42…/check-runs utc=2026-10-21T13:40:04Z http=200 x-github-request-id=C2A1:268CD3:2170E4:379559:6AD8C0B2` (`:200`)

```text
226: U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-09-02T08:57:41Z  (서버 부여 값만 · 커밋 author/committer date 불신)
227: U17-α ruleset 21886181: ruleset 21886181 updated_at=2026-09-06T15:21:13.608000+00:00 > t_land=2026-09-02T08:57:41+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가
228: U17-fire PREVENTION_CONTINUITY_UNVERIFIABLE: (α) ruleset 21886181 updated_at=2026-09-06T15:21:13.608000+00:00 > t_land=2026-09-02T08:57:41+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가 — 운영자 재심사 경로(영구 차단 아님)
229: prevention_control_state=PREVENTION_UNVERIFIED_REVISION
230: reason=(b)② d=28475ca1ca82fe99054a2cc04cf1b58e4550097a head=21c47e42ff1487282ce2f9da0df11756ff146a3a 4단계 ∀-success 위배 — [(0, 100181808552, 'failure')] (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함) [수집 2건 중 전순서 최소]
231: rc=1
```

09-04 와 같은 값: `u17_live_state=PREVENTION_ACTIVE`(`:65`) · workflow_id `343700405`(`:23`) · 적용 룰셋
`[21886181]`(`:64`) · α(`:199`)·β(`:210`) 축 통과 · `t_land` · (b)② 삼중값. (b)② 삼중값은
`U17-B2-DEVIATION-ACCEPTANCE.md` 의 `scope:` 와 **일치한다**.

**09-04 와 다른 것 — 발화 1건 → 2건.** 룰셋 `21886181` 의 `updated_at` 이
`2026-09-06T15:21:13.608Z` 로 `t_land` 뒤다(09-04 는 `2026-09-02T08:57:40.403Z ≤ t_land` 로 통과).
그래서 α 연속성 축이 `PREVENTION_CONTINUITY_UNVERIFIABLE` 을 새로 발화했다. 방출 상태는 전순서상
최소인 `PREVENTION_UNVERIFIED_REVISION` 그대로지만, 이 두 번째 발화는
`U17-B2-DEVIATION-ACCEPTANCE.md` 의 `scope:`(b)② 삼중값) **밖**이다. 이 기록은 그 사실만 적는다 —
수용 여부는 결정 기록의 소관이다.

## §2 기계 표면 (§11)

`.venv/bin/python tools/tos_completion_status.py --check` → `RESULT: GREEN (violations=0)` · rc 0
(`$S/completion-check.log:39-40`). `--write` 뒤 `git status --short` 빈 출력(`:50-51`) — 커밋된
`tos-spec/src/TOS-COMPLETION-STATUS.md` 가 현행이다.

상태 라인 4종: `oq11_raise_state=NOT_REQUIRED` · `d0a_entry_state=ENTRY_OK` ·
`d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR` · `closable_no_provenance_state=NO_ROWS_CLEAR`
(`:8-11`) — 09-04 와 동일.

완료 관측 중 09-04 대비 바뀐 것:

| 항 | 09-04 | 현재 |
| --- | --- | --- |
| `planned_unassigned_pairs` | 799 | 749 |
| `blank_normative_ref_rows` | 21 | 22 |
| `D0-5[resolver]` | `VALUED+UNBOUND` (`max_age_bound:UNBOUND`) | `VALUED` (7필드 전부, `MAX_time_conservative_freshness_age_ms:VALUED`) |
| `D0-5[marketfeed]` | `VALUED+UNBOUND` | `VALUED` (같은 형태) |
| `ref_reuse_top` 4·5위 | `sbr`(5)·`evidence`(4) | `are`(5)·`iap`(5) |

그 밖의 관측은 09-04 와 같다: `unmapped_pairs=0` · `superset_declared_pairs=0` ·
`FWD-a 미충족 1행 (표본=['STATE-EV-004'])` → 제외 후 0행 · `U-13 fwd_a_excluded_rows=['STATE-EV-004']` ·
`closable_no_rows=1` · `imprecise_owner_track=9` · `unassigned_owner_rows=0` · 나머지 D0-5 사이트 5개.

§11 개관(`tos-spec/src/TOS-COMPLETION-STATUS.md`, `$S/status-doc.log:116-146`)은 09-04 표와 **행·값 완전
동일**하다: `K-1`~`K-14`·`U-14`·`U-12`·`U-13`·`U-15`·`U-16`·`U-1a`·`U-4`·`U-5`·`U-8`·`U-9`·`D0-1`·`A-1`·
`A-2`·`A-3`·`D-1`·`D0-5` 전부 `MET`, `U-17` 은 「requires a live evaluation at completion-judgment time …
Unevaluated counts as unmet (fail-closed).」(§1 이 그 평가), `RES-1` `MET`(U-13-e 제외).

## §3 §11 «추가» 표 실측

| 항목 | 기준 | 실측 | 출처 |
| --- | --- | --- | --- |
| `tos/tests` 전량 green | 계약 8,742 · 09-04 8,756 | dots=9,616 · nondot=0 · rc 0 | `$S/tos-tests.raw`, `$S/tos-tests.log` |
| collect-only 교차검증 | — | 파일별 집계 합 9,616 (= dots) | `$S/collect.log:2-3` |
| `ruff check tos/src tos/tests tests/tos_l3 tools` | 0 | `All checks passed!` rc 0 (ruff 0.15.4) | `$S/ruff.log` |
| `black --check` 같은 경로 | 70 무증가 | would-reformat **0** · `918 files would be left unchanged.` rc 0 (black **26.1.0** — 09-04 는 26.5.1) | `$S/black.log` |
| `mypy tos/src/tos --ignore-missing-imports --no-error-summary` | 8 무증가 | error **0** · rc 0 (mypy 2.3.1) | `$S/mypy.log` |
| `tools/tos_spec_status.py --check` | PASS | rc 0 · `TOS spec status PASS: … profile_keys=164, profile_null_keys=16, restricted_live=NOT_AUTHORIZED, production=NOT_AUTHORIZED` + 비차단 WARNING(개발계획 §1 기준표 163/16 ↔ 파생 164/16) | `$S/spec-check.log` |
| `tools/tos_contract_check.py` | PASS | rc 0 · `tos-contract: PASS — 자기참조 stale 위반 없음` | `$S/contract-check.log:2-3` |
| `tools/tos_contract_check.py --self-test` | PASS | rc 0 · 뮤테이션 145종 전부 판별 · 죽은 검사 0 | `$S/contract-check.log:156-157` |

black 수치는 버전이 내려간 상태(26.5.1 → 26.1.0)의 값이라 09-04 수치와 바로 비교하지 않는다.

## §4 CI 실측 (gh · GET)

09-04 의 「PR 미개설 → 미측정」은 해소됐다. HEAD 는 PR #907 머지 커밋이다.

- `gh pr checks 907` → 8/8 pass: `backtest-extra` · `lint` · `performance` · `ruff` · `test` · `tos-firewall` ·
  **`tos-gate`**(run `39438812589`, PR head `97453314`, `2026-10-20T14:23:41Z` success) · `type-check` (`$S/ci.log:2-15`)
- HEAD `b15069fd` main push run: `ruff` · `tos-firewall` · `Tests` 전부 success (`$S/ci.log:17-20`)
- HEAD 밖 관측: 직전 main sha `65cb38c2` 의 **스케줄 run 2건 failure** — `Dev/Test Containers`
  `2026-10-19T22:39:59Z`, `Tests` `2026-10-19T04:05:50Z` (`$S/ci.log:25-29`). 같은 sha 의 push run 은 success.

## §5 §12.3 절차표 9행(레인 A) 실측

- 직전 레인 A approve: `docs/reviews/phase0-codex-records/20260904-155704/verdict.md`
  (`reviewed_at_head: c5550229…` · findings 0). 그 판정문 자신이 「이 approve 는 작업 트리 전체에
  결속된다 — 코드 한 줄이라도 바뀌면 무효·재심」이라 적는다. 그 뒤 `c5550229..HEAD` 는 커밋 1,846개,
  `tos/` 만 843파일 +189,567/−2,053 이다 (`$S/laneA.log`).
- **레인 A 재심 #7 실행 (2026-10-21)**: `docs/reviews/phase0-codex-records/20261021-224521/verdict.md`
  - 잡 `review-mvi5zwoy-rq2g4h` · `adversarial-review --wait --base c5550229 --scope branch`
  - `reviewed_at_head: b15069fd…` · `reviewed_scope_digest: 86be0b03f72f275b1e8d8d244f5615871f9ec63cd163e1379b3208cc7dc86bac`
  - 범위: 운영자 결정(2026-10-21 「Phase 0 표면만」)으로 커널 경로 — `tos/src` · `tos/tests` · `tos-spec` ·
    `.github` · `config/tos_completion.yaml` · Phase 0 검사 도구 9개 · `tos/pyproject.toml` · `tos/uv.lock` ·
    `.importlinter`. 한정은 focus text 지시이며 diff 도구 필터가 아니다. CP-3 런타임(`tos/runtime`)·
    `tests/`·`tools/tos_cp3`·레거시 코드는 범위 밖.
  - **판정: `needs-attention`, finding 1건 [high]** — 원문 그대로:

    > Preserve outstanding exposure after consumed nonterminal results (tos/src/tos/position/predicates.py:131-140)
    > Membership in consumed_by_attempt counts only the filled quantity and skips all outstanding-exposure buckets. However, engine/core.py emits EGRESS_RESULT_CONSUMED for applied ACK, TIMEOUT, UNKNOWN and PARTIAL_FILL results too. Reproduced with a sealed 10-unit BUY: worst-credible usage becomes zero after a consumed zero-fill result, or 7 after a partial fill with 3 remaining. This understates the risk observation and contradicts DR-0003 §2.2's requirement to retain unresolved exposure. The Decimal-only mapping cannot distinguish terminal results from outstanding orders.

  - 오케스트레이터 수용검사(file:line 실재): `tos/src/tos/position/predicates.py:131-140` 은
    `consumed_by_attempt` 에 있는 시도를 `filled` 만으로 `confirmed_net` 에 넣고 `continue` 한다.
    `tos/src/tos/engine/core.py` 는 `application.applied` 인 결과마다 `EGRESS_RESULT_CONSUMED` 를
    `filled_quantity`·`remaining_quantity` 와 함께 기록한다(`:738-756`). 그 맵을 만드는
    `tos/runtime/src/tos_runtime/riskstate/position.py:283-288` 은 `filled_quantity` 만 읽고
    `remaining_quantity`·결과 종류는 버린다. 지적의 구조는 코드와 맞는다 — **finding 은 기각되지 않는다.**
    이 술어는 `1e84ac14`(커널 라운드 #4)에서 런타임으로부터 「verbatim」 이식됐고 이식 시점은 `c5550229`
    뒤라 레인 A 증분 범위 안이다. Codex 재현(10단위 BUY → 0 / 7)은 이 기록이 독립 재현하지 않았다.
  - Codex 부기: 「completion verification stopped with rc=2 because temporary storage was unavailable」 —
    Codex 샌드박스 사정이다. 같은 head 의 `--check` 는 §2 가 rc 0 으로 잰다.
  - `codex-result.json` 은 보존되지 않았다 — companion 잡 상태가 제거된 리뷰 워크트리에 있어
    `result` 회수가 「No job found」 였다. 보존본은 `verdict.md`(Codex stdout 축자)·`job.txt` 다.

## §6 S-26(계약 자신의 종결 자격) 실측 — 종결 주장이 아니다

정본 위치는 계약 `:3923` 이후(`tools/tos_contract_index.py --locate S-26` → 후보 2개, 정본 `:3923`).
요약하지 않고 포인터만 적는다: 머리말 `:3923-3925` · ① `:3926` · ② `:4149` · ③ `:4150` · ④ `:4151` ·
⑤ `:4152` · ⑥ `:4153-4204` · ⑧ `:4205` (⑦ 은 없다).

- ① 마지막 계약 편집 `1db8f9b8` 이후 bound path 내용 변경 0 (§0).
- ② 그 편집 이후 material 0 독립 재심 = `20260905-144700`(#9, `review-mtnyojac-nhulgc`) ·
  `20260905-214532`(#10, `review-mtodn6sx-1fg1eh`) 두 건, 서로 다른 잡, 같은 contract blob `6f94dfbb`.
  #10 은 자기 문언으로 「**계약 내용 재심 아님 — 결속 head 갱신.**」(`20260905-214532/verdict.md:23`)이다.
  ② 를 2/2 로 읽을지 1/2 로 읽을지는 판정 사항이며 이 기록은 정하지 않는다.
- ⑤ `docs/reviews/phase0-codex-records/README.md` §S-26 재개 아크: 「3회차부터는 ⑤ 도 불성립」.
  그 뒤 ⑤ 를 닫는 처분은 관측되지 않았다.
- ⑧ 계약 `:4205` 가 「이 절은 «현재» 충족 불가」로 적은 상태 그대로다.
- 따라서 S-26 의 AND 는 충족되지 않으며, 이 기록은 종결을 주장하지 않는다.

## §7 이 기록이 하지 않는 것

- 계약·상위 계획·`tos-spec/**`·`tools/**`·`config/**`·`.github/**` 무편집.
- 기계 상태 불변 — 어떤 상태값도 이 기록으로 바뀌지 않는다.
- G1~G3 미부여. `restricted_live`/`production` `NOT_AUTHORIZED` 불변.
- verdict·countersign 이 아니다 — 완료 판단은 같은 디렉터리의 결정 기록(초안) 소관이다.
- 레인 A finding 의 수정 — 커널 코드 변경이며 별도 PR 소관이다.
- U-17 α 연속성 발화의 수용 — 운영자 소관이다.
- S-26 종결 판정.
