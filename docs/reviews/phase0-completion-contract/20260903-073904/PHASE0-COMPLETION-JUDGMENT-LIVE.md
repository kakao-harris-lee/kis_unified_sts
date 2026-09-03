# Phase 0 완료 판정 — 완료 판단 시점 live 실측 기록

> **Document class**: 비규범 **측정 전사**(측정 기록). Phase 0 완료 판정(계약 §11) 자체가
> 아니다 — verdict YAML·`operator_countersign`·판정 어휘를 포함하지 않는다. 완료의
> *결정*은 별도 기록이 별도로 담당한다. 계약
> `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`,
> 상위 계획 `docs/plans/2026-08-11-tos-completion-development-plan.md`, `tos-spec/`,
> `config/`, `tools/`, `.github/` 는 이 기록이 편집하지 않는다.

## §0 결속

| 항 | 값 |
| --- | --- |
| 성격 | Phase 0 완료 판정(§11)용 «완료 판정 시점 live» 실측 기록 — 판정 자체가 아니다 |
| 판정 대상 head | `faea9720f61a9a598e0dabae427ff2d7ed73199d`(branch가 origin에 push됨; `main`=`70b100e7`; 그 사이 두 커밋은 tools 전용 — `cdd3c561` mypy 잔존 1건 해소, `faea9720` `tos_spec_status` 스캐너 git 우주 정정) |
| 계약 blob(`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`) | `0f8f35682f724c76d58d4b334fec3ecf47518e6f` — addendum-7(`20260902-215717`)의 값과 동일(재계산 확인) |
| 상위 계획 blob(`docs/plans/2026-08-11-tos-completion-development-plan.md`) | `ec3464c068dff2030e0764f3b05c985a821730f5`(재계산 확인) |
| `bound_set_digest` 재계산(OQ-11-DISPOSITION.md 의 명령 그대로) | `e0729ff3ccbbab41b007464742290e4e875c07846b5a87d228727abc2ae4480f` == `docs/reviews/phase0-completion-contract/20260902-195656/verdict.md` 의 `bound_set_digest`(재계산 확인) |
| U-15 R-7 currency | `git rev-list --full-history cdecb692..HEAD -- <두 bound path>` = 0 커밋(재실행 확인) |
| `tools/tos_entry_harness.sh` sha256 | `059e13f22397d53c53211895cc321fef81ab7925135b196e27315e813d723177` == `.github/workflows/tos-gate.yml:17` 핀(재계산·재대조 확인) |
| `tools/u17-verify.sh` sha256 | `0b68ef856836380817dac179aee07e09276dbd9cb66feea9817c669bcdf9814e` == addendum-7(재계산 확인) |
| `tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md` `operator_countersign` | `"chihun,lee 2026-08-28T05:23:48Z"`(그대로 인용 — 이 기록은 갱신하지 않는다; 재대조 확인) |
| gh 인증 | `kakao-harris-lee`(keyring) · 전부 GET |
| 실행 UTC | u17 live 시작 `2026-09-03T07:39:04Z`(U17-A00), 이 기록 시각 `2026-09-03T07:42:54Z` |

---

## §1 U-17 live 실측 원문

전체 로그는 저작 세션의 스크래치패드에만 보존되며(368 KB, `gh` JSON 덤프 포함) 이
기록에는 커밋하지 않는다 — 아래 `utc=` · `x-github-request-id=` 값이 재조회·대조의
근거다(계약 U-17 「리뷰어가 재조회해 대조」).

```text
15: U17-A00 apps/github-actions  utc=2026-09-03T07:39:04Z  http=200  x-github-request-id=E188:184067:2F2481:3A6549:6A992417
17: U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-09-03T07:39:04Z  http=200  x-github-request-id=E189:3CED70:2F0EF4:3A4EC4:6A992417  (.default_branch=main)
18: U17-A0W repos/kakao-harris-lee/kis_unified_sts/actions/workflows/tos-gate.yml  utc=2026-09-03T07:39:04Z  http=200  x-github-request-id=E1AE:D9D9C:2FEB0D:3B2E07:6A992418
20: U17-0w 핀 workflow_id=343700405 (state=active · repos/kakao-harris-lee/kis_unified_sts/actions/workflows/tos-gate.yml 의 .id · 구조 파생 · ①-R 전 결속 · 폴백 없음)
61: U17-α0 적용 룰셋(연속성 입력우주) = [21886181]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682 21886181])
62: u17_live_state=PREVENTION_ACTIVE
139: U17-C1R repos/kakao-harris-lee/kis_unified_sts/actions/workflows/343700405/runs?head_sha=21c47e42ff1487282ce2f9da0df11756ff146a3a&per_page=100  utc=2026-09-03T07:39:18Z  http=200  x-github-request-id=E263:3C0EFF:2F3EA1:3A7E79:6A992425
148: U17-C1R ①-R 1,000-런 상한 관측: 수집 런 수=1 · total_count=1
160: U17-C3 ③-C 합집합 |E₀|=1 (S_R 전체 소비 완료 · 1,000-suite 잘림의 대상 아님 — GitHub 처방 이행)
171: U17-ALFA1 S_A(포함 조건: head_sha==21c47e42ff1487282ce2f9da0df11756ff146a3a ∧ app.id==15368) = ["91075486666", "91075486707", "91075486743"]
196: U17-ALFA5 α 축 통과: (i) S_R⊆S_A ∧ (ii) S_A∖S_R 전 원소 «확인된 타 워크플로»
207: U17-BETA1 β 축 통과: 좌=1 == 우=1
209: U17-C1Rr ①-R run 결속 맵 구성(추가 HTTP 없음 — R 자체가 path/head_sha 를 담는다): 1개
222: U17-fire PREVENTION_UNVERIFIED_REVISION: (b)② d=28475ca1ca82fe99054a2cc04cf1b58e4550097a head=21c47e42ff1487282ce2f9da0df11756ff146a3a 4단계 ∀-success 위배 — [(0, 100181808552, 'failure')] (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함)
223: U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-09-02T08:57:41Z  (서버 부여 값만 · 커밋 author/committer date 불신)
224: U17-α ruleset 21886181: ruleset 21886181 created_at=2026-08-30T23:51:12.269000+00:00 ≤ t_land ∧ updated_at=2026-09-02T08:57:40.403000+00:00 ≤ t_land
225: prevention_control_state=PREVENTION_UNVERIFIED_REVISION
226: reason=(b)② d=28475ca1ca82fe99054a2cc04cf1b58e4550097a head=21c47e42ff1487282ce2f9da0df11756ff146a3a 4단계 ∀-success 위배 — [(0, 100181808552, 'failure')] (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함) [수집 1건 중 전순서 최소]
227: rc=1
```

`(b)②` 의 이유는 `d=28475ca1…`, `head=21c47e42…`, check-run `100181808552` `failure` 를
지목한다. 이 삼중값은 `tos-spec/src/part-1-foundation/decisions/U17-B2-DEVIATION-ACCEPTANCE.md`
의 `scope:` 가 기록한 삼중값과 **일치한다**(그 파일에서 그대로 인용):

```yaml
scope:
  d: 28475ca1ca82fe99054a2cc04cf1b58e4550097a          # D0A-FIRST (config/tos_completion.yaml 도입 커밋)
  landing_pr: 638
  landing_head: 21c47e42ff1487282ce2f9da0df11756ff146a3a
  check_run_id: 100181808552                             # tos-gate · conclusion=failure
  repaired_by: d56785ab                                  # PR #639 병합 커밋 (§12.3.4-R 재핀 · 하니스 sha 059e13f2…)
  independent_readjudication: docs/reviews/phase0-completion-contract/20260902-195656/verdict.md
```

두 기록이 같은 삼중값을 담고 있다는 사실만을 이 기록은 진술한다 — 그 편차를
받아들일지는 완료 판단(결정 기록)의 소관이다.

다른 편차는 발화하지 않았다: `u17_live_state=PREVENTION_ACTIVE`, α(U17-ALFA5)와
β(U17-BETA1) 둘 다 통과, ①-R/②-S/③-C 상한 미도달(148/160행 관측 수=1·total_count=1,
1,000 미만).

---

## §2 기계 표면 (§11)

명령 `.venv/bin/python tools/tos_completion_status.py --check`, rc 0, 출력 38행 전문:

```text
미구현(C2c 이후) — 강제 지점 미등록:

--check 밖 강제 지점:
  - U-17 → tools/u17-verify.sh (가드 체인·live)

상태 라인 (rc 비결합 — 상태별 rc 결합은 해당 check_id 의 Finding 이 담당):
  oq11_raise_state=NOT_REQUIRED
  d0a_entry_state=ENTRY_OK
  d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR
  closable_no_provenance_state=NO_ROWS_CLEAR

완료 관측 (§11 소관 · rc 비결합):
  unmapped_pairs=0
  planned_unassigned_pairs=799
  superset_declared_pairs=0
  FWD-a-0 불충족 evidence_id=['STATE-EV-004']
  FWD-a 미충족 1행 (표본=['STATE-EV-004'])
  FWD-a-0 불충족(제외 후) evidence_id=[]
  FWD-a 미충족(제외 후) 0행
  ref_reuse_max=8
  ref_reuse_top=[('tos/src/tos/hag/predicates.py', 8), ('tos/src/tos/capsule/predicates.py', 7), ('tos/src/tos/spg/predicates.py', 6), ('tos/src/tos/sbr/predicates.py', 5), ('tos/src/tos/evidence/predicates.py', 4)]
  profile_dependent_blocked=['BC-EV-003', 'ECO-EV-012', 'IOM-EV-008']
  closable_no_rows=1
  blank_normative_ref_rows=21
  imprecise_owner_track=9
  unassigned_owner_rows=0
  U-13 fwd_a_excluded_rows=['STATE-EV-004']
  U-13 remainder_rows=[]
  A-2: ARCHITECTURE-GATE-STATUS.md 에 기계 파싱 가능한 권한 축-표기 없음(실측 확인 — §6.4 대조 대상에서 제외)
  D0-5[backtest__init__]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)
  D0-5[resolver]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)
  D0-5[results]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)
  D0-5[construction]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)
  D0-5[records]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)
  D0-5[engine]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)
  D0-5[marketfeed]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)

RESULT: GREEN (violations=0)
```

`FWD-a 미충족 1행 (표본=['STATE-EV-004'])` 과 `FWD-a 미충족(제외 후) 0행` 이 위 출력에
함께 나타난다 — 제외 전/후 두 계수가 동시에 노출된다.

`tos-spec/src/TOS-COMPLETION-STATUS.md:38-43`(state machine values, 그대로 인용):

```text
## State machine values

- `oq11_raise_state=NOT_REQUIRED`
- `d0a_entry_state=ENTRY_OK`
- `d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR`
- `closable_no_provenance_state=NO_ROWS_CLEAR`
```

같은 문서 `:45-73`(U-10 metrics and completion observations, FWD-a 두 계수 포함):

```text
- `unmapped_pairs=0`
- `planned_unassigned_pairs=799`
- `superset_declared_pairs=0`
- `FWD-a-0 불충족 evidence_id=['STATE-EV-004']`
- `FWD-a 미충족 1행 (표본=['STATE-EV-004'])`
- `FWD-a-0 불충족(제외 후) evidence_id=[]`
- `FWD-a 미충족(제외 후) 0행`
- `ref_reuse_max=8`
- `ref_reuse_top=[('tos/src/tos/hag/predicates.py', 8), ('tos/src/tos/capsule/predicates.py', 7), ('tos/src/tos/spg/predicates.py', 6), ('tos/src/tos/sbr/predicates.py', 5), ('tos/src/tos/evidence/predicates.py', 4)]`
- `profile_dependent_blocked=['BC-EV-003', 'ECO-EV-012', 'IOM-EV-008']`
- `closable_no_rows=1`
- `blank_normative_ref_rows=21`
- `imprecise_owner_track=9`
- `unassigned_owner_rows=0`
- `U-13 fwd_a_excluded_rows=['STATE-EV-004']`
- `U-13 remainder_rows=[]`
- `A-2: ARCHITECTURE-GATE-STATUS.md 에 기계 파싱 가능한 권한 축-표기 없음(실측 확인 — §6.4 대조 대상에서 제외)`
- `D0-5[backtest__init__]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)`
- `D0-5[resolver]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)`
- `D0-5[results]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)`
- `D0-5[construction]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)`
- `D0-5[records]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)`
- `D0-5[engine]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)`
- `D0-5[marketfeed]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)`
```

같은 문서 `:115-145`(Phase 0 termination-condition overview §11, 그대로 인용):

```text
## Phase 0 termination-condition overview (section 11)

- `K-1`: `MET`
- `K-2`: `MET`
- `K-3`: `MET`
- `K-4`: `MET`
- `K-5/FWD-METRICS`: `MET`
- `K-6`: `MET`
- `K-9`: `MET`
- `K-11`: `MET`
- `K-12`: `MET`
- `K-13`: `MET`
- `K-14`: `MET`
- `U-14`: `MET`
- `U-12`: `MET`
- `U-13`: `MET`
- `U-15`: `MET`
- `U-16`: `MET`
- `U-1a`: `MET`
- `U-4`: `MET`
- `U-5`: `MET`
- `U-8`: `MET`
- `U-9`: `MET`
- `D0-1`: `MET`
- `A-1`: `MET`
- `A-2`: `MET`
- `A-3`: `MET`
- `D-1`: `MET`
- `D0-5`: `MET`
- `U-17`: requires a live evaluation at completion-judgment time; this generated document does not perform that evaluation. Unevaluated counts as unmet (fail-closed).
- `RES-1`: `MET` — `STATE-EV-004` is excluded from the `FWD-a` termination condition by the checker-derived exclusion list (`U-13 fwd_a_excluded_rows` above; contract U-13-e).
```

`U-17` 행이 명시하는 「live evaluation at completion-judgment time」이 §1 의 실측이다 —
이 문서(생성물) 자신은 그 평가를 수행하지 않는다고 스스로 적고 있다.

---

## §3 §11 «추가» 표 실측

| 항목 | 계약 기준 | 실측 | 명령 |
| --- | --- | --- | --- |
| `tos/tests` 전량 green | 8,742(계약 §2 표) | collected 8756 · passed 8756 · rc 0 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tos/src .venv/bin/python -m pytest tos/tests -q -p no:cacheprovider`(실행 전 `tos/**/__pycache__` 퍼지). 계수 방법: addopts `-ra -q` 라 요약행이 없어 진행 문자(`.`) 계수=8756=`--collect-only -q` 파일별 합·비-`.` 상태 문자 0 |
| `ruff check tos/src tos/tests tests/tos_l3 tools` | - | `All checks passed!` rc 0 | 상동 |
| `black --check tos/src tos/tests tests/tos_l3 tools` | 70 | `69 files would be reformatted, 751 files would be left unchanged.` — pyenv black 26.1.0 · `.venv` black 26.5.1 동일 결과(무증가: −1) | 상동 |
| `mypy tos/src/tos --ignore-missing-imports --no-error-summary` | 8 | `error:` 8건 — pyenv mypy 2.3.0 · `.venv` mypy 2.3.1 동일(무증가: 0) | 상동 |
| `tools/tos_spec_status.py --check` | - | rc 0 | 상동 |
| `tools/tos_contract_check.py`(Layer 4) | - | rc 0 · `tos-contract: PASS — 자기참조 stale 위반 없음` | 상동 |
| `tools/tos_contract_check.py --self-test`(Layer 4) | - | rc 0 · `self-test: PASS — 뮤테이션 145종 전부 판별 · 죽은 검사 0 · 앵커 불일치 0 · 역방향 과잉 차단 0 · 대조군 무효 0 · 분류기 대조군 2종 전건 통과` | 상동 |

`Phase 0 완료 주장은 D0-A 이후에만`(계약 `:4541`): D0A-FIRST `28475ca1` 은 PR #638 로
main 에 착지했다(`merged_at=2026-09-02T08:57:41Z` — §1 223행).

---

## §4 CI 실측 (gh · GET)

| 워크플로 | 대상 | 결과 | 시각 |
| --- | --- | --- | --- |
| tos-firewall(main push) | `70b100e7` | success | `2026-09-02T13:36:15Z` |
| tos-firewall(main push) | `4a0d122b` | success | - |
| tos-firewall(main push) | `d56785ab` | success | - |
| test.yml(main) | `70b100e7` | success | - |
| test.yml(main) | `4a0d122b` | success | - |
| tos-gate(`on: [pull_request]` 전용) | PR head `1964de73` | success | `2026-09-02T13:29:00Z` |
| tos-gate(PR 전용) | PR head `44ffce5e` | success | - |
| tos-gate(PR 전용) | PR head `a9da27b0` | success | - |

`faea9720` 에는 아직 CI run 이 없다(PR 미개설·main 미착지) — 이 head 의 CI 판정은
**미측정**이다.

---

## §5 §12.3 절차표 9행(codex-reviewer 적대적 코드 리뷰) 실측

D0 구현 범위에 대한 lane-A(코드) verdict 는 존재하지 않는다. 근거: 2026-09-01 이후
추적된 스탬프는 `20260901-223154`(UNCHK-014 NO-row 제안 + Codex 독립 검토 — 제안
문서이지 코드가 아니다), `20260902-174919` · `20260902-195656`(lane-B 계획 재심 —
`job_class: review`, `reviewed_plan_paths` = 두 계획 문서)뿐이다. `.omc/review/` 스탬프도
2026-09-01 이후로는 같은 두 건이다. 범위 규모(`git diff --stat 28475ca1^ 70b100e7 -- .
':!docs/plans' ':!docs/reviews'`): 34개 파일, +14,343/−99. code-ish(`*.py *.sh *.yml
*.yaml`) 24개 파일 +11,428/−92. first-parent 커밋 7개.

미실행으로 관측됨 — 처분은 운영자 결정.

---

## §6 S-26(계약 자신의 종결 자격) 실측 — 종결 주장이 아니다

계약 §11.1 은 §11 표(Phase 0 종료 조건)와 S-26(계약 «종결» 자격)을 별개 축으로
분리한다. 이 절은 측정값만 기록한다: ① 계약 blob 은 마지막 편집(`cdecb692`) 이후
무변경(bound-path 커밋 0건, §0). ② 그 편집 이후 material 0 인 독립 재심 = 1건
(`20260902-195656`, approve, findings 0). S-26 ②는 연속 2회를 요구한다. ⑤ 와 ⑧ 은 계약
본문에 열린 상태로 기록돼 있다. 따라서 S-26 의 AND 는 충족되지 않으며, 이 기록은
부분·전체를 불문하고 종결을 주장하지 않는다(S-26 머리말이 「부분 종결」 표기를
금지한다). 2026-08-30 운영자 지시(재심 #21 종결)는 유효하며, 이 기록은 그 재심을
재개하지 않는다. S-26 ⓒ: 종결 판정 기록은 문서 «밖»에서만 이뤄진다 — 이 파일은
계약 문서 밖이다.

---

## §7 이 기록이 하지 않는 것

- 계약·상위 계획 무편집(bound paths).
- 기계 상태 불변 — `prevention_control_state`·`d0a_entry_state` 등 어떤 상태값도
  이 기록으로 바뀌지 않는다.
- G1~G3 미부여(§10).
- `restricted_live`/`production` `NOT_AUTHORIZED` 불변.
- verdict·countersign 이 아니다 — 완료 판단은 별도 기록의 소관이다.
