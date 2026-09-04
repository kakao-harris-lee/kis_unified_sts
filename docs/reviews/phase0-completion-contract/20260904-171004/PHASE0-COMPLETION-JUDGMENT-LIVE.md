# Phase 0 완료 판정 — 완료 판단 시점 live 실측 기록 (2차)

> **Document class**: 비규범 **측정 전사**(측정 기록). Phase 0 완료 판정(계약 §11) 자체가
> 아니다 — verdict YAML·`operator_countersign`·판정 어휘를 포함하지 않는다. 완료의
> *결정*은 별도 기록(`PHASE0-COMPLETION-DECISION.md`, 같은 디렉터리)이 별도로 담당한다.
> 이 기록은 2026-09-03 실측 기록
> (`docs/reviews/phase0-completion-contract/20260903-073904/PHASE0-COMPLETION-JUDGMENT-LIVE.md`)
> 이후 변경분을 반영한 **재측정**이다. 계약
> `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`,
> 상위 계획 `docs/plans/2026-08-11-tos-completion-development-plan.md`, `tos-spec/`,
> `config/`, `tools/`, `.github/` 는 이 기록이 편집하지 않는다.

## §0 결속

| 항 | 값 | 출처 |
| --- | --- | --- |
| 성격 | Phase 0 완료 판정(§11)용 «완료 판단 시점 live» 실측 기록(2차) — 판정 자체가 아니다 | 이 기록 |
| 측정 대상 head | `d07646c2923784e90ace718d98511a80c2d2fef7`(local branch `mission-critical-trading-operating-system`) | `$S/judgment/versions.log` |
| 그 head 와 push/merge 위치 | 원격 추적 브랜치 HEAD = `c555022922f2ad9efb09e90f734bdfd18884efb0`(측정 head 는 push 대비 1커밋 앞 — `d07646c2` docs(reviews) 전용, `git diff --stat c5550229 d07646c2` = `docs/reviews/phase0-codex-records/**` 137개 파일 전량 신규 추가·+18,852/−0); `main`=`70b100e7`(09-03 기록과 동일, 그 뒤 main 착지 없음) | `$S/judgment/ci.log`(「Commits ahead of tracking branch」·「Tracking branch HEAD」), 직접 재실행 `git diff --stat c5550229 d07646c2` |
| 계약 blob(`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`) | `899689fccdf7bed1705e927e2745ad839dc63875`(09-03 기록의 `0f8f3568…`에서 변경 — 에라타 52~56차 5커밋 반영) | `$S/judgment/binding.log` §「Contract design file blob」 |
| 상위 계획 blob(`docs/plans/2026-08-11-tos-completion-development-plan.md`) | `ec3464c068dff2030e0764f3b05c985a821730f5`(09-03 기록과 동일 — 무편집) | `$S/judgment/binding.log` §「Development plan file blob」 |
| `bound_set_digest`(OQ-11-DISPOSITION.md 명령으로 재계산) | `4e6c975f794696066a25abe4ee827594afa18f8fac8bfb5e7bf31d43508b3c2f` == `tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md`의 값 == `docs/reviews/phase0-completion-contract/20260904-133500/verdict.md`의 `bound_set_digest`(09-03 기록의 `e0729ff3…`에서 O-6 재결속으로 변경) | `$S/judgment/binding.log` §「Computing digest」·§「OQ-11 DISPOSITION binding info」·§「Latest verdict binding info」; 직접 대조 확인(OQ-11-DISPOSITION.md·레인 B verdict 재열람) |
| U-15 R-7 currency (`git rev-list --full-history 48243cd2..HEAD -- <두 bound path>`) | `0` 커밋 | `$S/judgment/binding.log` §「Full history commit count (contract plan files)」; 직접 재실행 결과도 `0`(`wc -l`) |
| `tools/tos_entry_harness.sh` sha256 | `059e13f22397d53c53211895cc321fef81ab7925135b196e27315e813d723177` == `.github/workflows/tos-gate.yml:17` 핀(09-03 기록과 동일 — 무변경) | `$S/judgment/binding.log` §「Tool and harness shasum」·§「CI workflow references」 |
| `tools/u17-verify.sh` sha256 | `0b68ef856836380817dac179aee07e09276dbd9cb66feea9817c669bcdf9814e`(09-03 기록과 동일 — 무변경) | `$S/judgment/binding.log` §「Tool and harness shasum」 |
| `tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md` `operator_countersign` | `"chihun,lee 2026-08-28T05:23:48Z"`(그대로 인용 — 이 기록은 갱신하지 않는다) | `$S/judgment/binding.log` §「Operator countersign references」 |
| U-17 (b)② `scope:` (U17-B2-DEVIATION-ACCEPTANCE.md) | `d=28475ca1…`·`landing_pr=638`·`landing_head=21c47e42…`·`check_run_id=100181808552`·`repaired_by=d56785ab`·`independent_readjudication=docs/reviews/phase0-completion-contract/20260902-195656/verdict.md`(09-03 기록과 동일 삼중값) | `$S/judgment/binding.log` §「U17 scope」; `tos-spec/src/part-1-foundation/decisions/U17-B2-DEVIATION-ACCEPTANCE.md` 직접 재열람 |
| gh 인증 | `kakao-harris-lee`(keyring) · Active account: true · 전부 GET | `$S/judgment/u17-live.log:8-13`, 파일 말미 `=== gh auth status ===` 블록 |
| 실행 UTC | u17 live 스크립트 시작 `2026-09-04T08:10:16Z`(파일 1행), 첫 GitHub API 호출(U17-A00) `utc=2026-09-04T08:12:41Z`, 이 기록 저작 시각 `2026-09-04T08:18Z` 무렵 | `$S/judgment/u17-live.log:1`, `$S/judgment/u17-live.log:16`, 직접 실행 `date -u` |

---

## §1 U-17 live 실측 원문

전체 로그는 저작 세션의 스크래치패드에만 보존되며(`u17-live.log` 369,964 bytes·`u17-live.raw` 368,226 bytes,
`gh` JSON 덤프 포함) 이 기록에는 커밋하지 않는다 — 아래 `utc=`·`x-github-request-id=` 값이
재조회·대조의 근거다(계약 U-17 「리뷰어가 재조회해 대조」).

```text
16:    15	U17-A00 apps/github-actions  utc=2026-09-04T08:12:41Z  http=200  x-github-request-id=2710:12BE1B:4DB829:664EDD:6A9A7D78
18:    17	U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-09-04T08:12:41Z  http=200  x-github-request-id=F1C6:12F955:4E3019:66C8AF:6A9A7D79  (.default_branch=main)
19:    18	U17-A0W repos/kakao-harris-lee/kis_unified_sts/actions/workflows/tos-gate.yml  utc=2026-09-04T08:12:42Z  http=200  x-github-request-id=BB8F:3BF92E:4FCD0D:68663E:6A9A7D79
21:    20	U17-0w 핀 workflow_id=343700405 (state=active · repos/kakao-harris-lee/kis_unified_sts/actions/workflows/tos-gate.yml 의 .id · 구조 파생 · ①-R 전 결속 · 폴백 없음)
62:    61	U17-α0 적용 룰셋(연속성 입력우주) = [21886181]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682 21886181])
63:    62	u17_live_state=PREVENTION_ACTIVE
140:   139	U17-C1R repos/kakao-harris-lee/kis_unified_sts/actions/workflows/343700405/runs?head_sha=21c47e42ff1487282ce2f9da0df11756ff146a3a&per_page=100  utc=2026-09-04T08:12:54Z  http=200  x-github-request-id=B441:3ED3A:4D6F54:660910:6A9A7D85
149:   148	U17-C1R ①-R 1,000-런 상한 관측: 수집 런 수=1 · total_count=1
161:   160	U17-C3 ③-C 합집합 |E₀|=1 (S_R 전체 소비 완료 · 1,000-suite 잘림의 대상 아님 — GitHub 처방 이행)
172:   171	U17-ALFA1 S_A(포함 조건: head_sha==21c47e42ff1487282ce2f9da0df11756ff146a3a ∧ app.id==15368) = ["91075486666", "91075486707", "91075486743"]
197:   196	U17-ALFA5 α 축 통과: (i) S_R⊆S_A ∧ (ii) S_A∖S_R 전 원소 «확인된 타 워크플로»
208:   207	U17-BETA1 β 축 통과: 좌=1 == 우=1
210:   209	U17-C1Rr ①-R run 결속 맵 구성(추가 HTTP 없음 — R 자체가 path/head_sha 를 담는다): 1개
223:   222	U17-fire PREVENTION_UNVERIFIED_REVISION: (b)② d=28475ca1ca82fe99054a2cc04cf1b58e4550097a head=21c47e42ff1487282ce2f9da0df11756ff146a3a 4단계 ∀-success 위배 — [(0, 100181808552, 'failure')] (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함)
224:   223	U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-09-02T08:57:41Z  (서버 부여 값만 · 커밋 author/committer date 불신)
225:   224	U17-α ruleset 21886181: ruleset 21886181 created_at=2026-08-30T23:51:12.269000+00:00 ≤ t_land ∧ updated_at=2026-09-02T08:57:40.403000+00:00 ≤ t_land
225: prevention_control_state=PREVENTION_UNVERIFIED_REVISION
226: reason=(b)② d=28475ca1ca82fe99054a2cc04cf1b58e4550097a head=21c47e42ff1487282ce2f9da0df11756ff146a3a 4단계 ∀-success 위배 — [(0, 100181808552, 'failure')] (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함) [수집 1건 중 전순서 최소]
rc=1
```

행 번호는 `$S/judgment/u17-live.log`의 `cat -n` 행 번호(왼쪽 숫자, 저작 세션이 이미 붙인 것)와
파일 내부 오프셋 라벨(오른쪽 숫자, `U17-*` 태그 옆)을 함께 적었다. `prevention_control_state=`·
`reason=`·`rc=1`은 파일 말미의 `sed -n '220,234p'` 재확인으로 다음 위치에 있다(브리핑 메모 (1)
그대로): 스크립트 자신의 종료 코드는 이 전사문 직후의 `rc=1` 줄이고, 그 뒤에 이어지는 `gh auth
status` 블록의 `rc=0`은 그 별개 명령의 종료 코드다 — 혼동해 U-17 자체를 `rc=0`으로 읽지 않는다.

`(b)②`의 이유는 09-03 기록과 **완전히 동일한 삼중값**(`d=28475ca1…`, `head=21c47e42…`,
check-run `100181808552` `failure`)을 지목한다. 이 삼중값은
`tos-spec/src/part-1-foundation/decisions/U17-B2-DEVIATION-ACCEPTANCE.md`의 `scope:`가
기록한 삼중값과 **일치한다**(§0 표에 인용):

```yaml
scope:
  d: 28475ca1ca82fe99054a2cc04cf1b58e4550097a          # D0A-FIRST (config/tos_completion.yaml 도입 커밋)
  landing_pr: 638
  landing_head: 21c47e42ff1487282ce2f9da0df11756ff146a3a
  check_run_id: 100181808552                             # tos-gate · conclusion=failure
  repaired_by: d56785ab                                  # PR #639 병합 커밋 (§12.3.4-R 재핀 · 하니스 sha 059e13f2…)
  independent_readjudication: docs/reviews/phase0-completion-contract/20260902-195656/verdict.md
```

두 기록이 같은 삼중값을 담고 있다는 사실만을 이 기록은 진술한다 — 그 편차를 받아들일지는
완료 판단(결정 기록)의 소관이다. 다른 편차는 발화하지 않았다: `u17_live_state=PREVENTION_ACTIVE`,
α(U17-ALFA5)와 β(U17-BETA1) 둘 다 통과, ①-R/②-S/③-C 상한 미도달(148/160행 관측 수=1·
total_count=1, 1,000 미만) — 09-03 기록과 값이 동일하다(같은 두 커밋 `d`/`landing_head`에 대한
재측정이므로 서버 판정이 바뀔 이유가 없다).

---

## §2 기계 표면 (§11)

명령 `.venv/bin/python tools/tos_completion_status.py --check`, rc 0, 출력 전문
(`$S/judgment/completion-check.log`):

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
  D0-5[backtest__init__]=UNBOUND (dsl_evaluation_budget_steps)
  D0-5[resolver]=VALUED+UNBOUND (MAX_future_timestamp_tolerance_ms:VALUED; MAX_critical_input_consumer_receipt_age_ms:VALUED; MAX_time_transport_and_queue_uncertainty_ms:VALUED; MAX_clock_domain_conversion_uncertainty_ms:VALUED; MAX_time_source_precision_ms:VALUED; MAX_time_source_sequence_gap_ms:VALUED; max_age_bound:UNBOUND)
  D0-5[results]=UNBOUND (dsl_evaluation_budget_steps)
  D0-5[construction]=UNBOUND (risk_budget:UNBOUND; per_unit_risk:UNBOUND; lot_size:UNBOUND; min_quantity:UNBOUND; max_quantity:UNBOUND; max_notional:UNBOUND)
  D0-5[records]=UNBOUND (risk_budget:UNBOUND; per_unit_risk:UNBOUND; lot_size:UNBOUND; lot_rounding:UNBOUND; min_quantity:UNBOUND; max_quantity:UNBOUND; max_notional:UNBOUND)
  D0-5[engine]=UNBOUND (dsl_evaluation_budget_steps; CONTRAST: MAX_dsl_evaluation_ms)
  D0-5[marketfeed]=VALUED+UNBOUND (MAX_future_timestamp_tolerance_ms:VALUED; MAX_critical_input_consumer_receipt_age_ms:VALUED; MAX_time_transport_and_queue_uncertainty_ms:VALUED; MAX_clock_domain_conversion_uncertainty_ms:VALUED; MAX_time_source_precision_ms:VALUED; MAX_time_source_sequence_gap_ms:VALUED; max_age_bound:UNBOUND)

RESULT: GREEN (violations=0)
RESULT: rc=0

=== git status check (should be empty) ===
end git status check
```

09-03 기록 대비 변화: `D0-5[resolver]`가 `UNBOUND (docstring 에 UNBOUND 선언 문언 존재)`에서
**`VALUED+UNBOUND`(6개 필드 VALUED·`max_age_bound`만 UNBOUND)로**, `D0-5[marketfeed]`도
동일하게 **`UNBOUND`에서 `VALUED+UNBOUND`로** 재분류됐다. 09-03 기록의 marketfeed `NONE`
주장은 독립 심사로 거짓 판정됐다(§5 참조) — `UNCHK-026`은 제거됐다.

`tos-spec/src/TOS-COMPLETION-STATUS.md`(HEAD 시점) 발췌, `$S/judgment/status-doc.log`에서
그대로 인용:

State machine values(`status-doc.log:40-43`):

```text
- `oq11_raise_state=NOT_REQUIRED`
- `d0a_entry_state=ENTRY_OK`
- `d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR`
- `closable_no_provenance_state=NO_ROWS_CLEAR`
```

U-10 metrics / completion observations(`status-doc.log:49-72`) — 위 `--check` 출력과
완전 일치(D0-5 7행 포함, `VALUED+UNBOUND` 2행 포함).

Phase 0 termination-condition overview §11(`status-doc.log:115-145`, 그대로 인용):

```text
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

`U-17` 행이 명시하는 「live evaluation at completion-judgment time」이 §1의 실측이다 — 이
생성물 자신은 그 평가를 수행하지 않는다고 스스로 적고 있다. 09-03 기록과 이 표 자체는 동일
(D0-5는 이미 그때도 `MET` 표기였다 — 변화는 D0-5 판정을 구성하는 하위 셀의 값역/근거이지
상태값 자체가 아니다).

---

## §3 §11 «추가» 표 실측

| 항목 | 계약 기준 | 실측 | 명령/출처 |
| --- | --- | --- | --- |
| `tos/tests` 전량 green | 8,742(계약 §2 표) | dots(진행 문자 수)=8756 · nondot=0 · rc=0 | `$S/judgment/tos-tests.log`(`dots=    8756` / `nondot=       0` / `rc=0`) |
| `tos/tests` collect-only 총량(교차검증) | - | `grep -c "::"` 결과 = **0**(pytest 9.0.2 `--collect-only -q`가 `<path>: <count>` 파일-집계 형식을 출력해 `::` 토큰이 없다 — 브리핑이 지목한 대로 원 `collect=` 라인은 사용 불가) · 파일별 집계값을 직접 합산하면 **8756**(=`dots`와 일치) | 직접 실행: `PYTHONPATH=tos/src .venv/bin/python -m pytest tos/tests --collect-only -q -p no:cacheprovider 2>/dev/null \| grep -c "::"` → `0`; 대체 합산: 같은 명령에 `2>&1 \| awk -F': ' '/^tests\// {sum+=$2} END {print sum}'` → `8756` |
| completion-status 테스트 스위트 | - | 242 tests · rc 0(실행 로그는 진행 점만 표시하며 요약 카운트 라인은 캡처되지 않았다 — 진행 문자 수를 세면 72+72+72+26=242) | `$S/pytest-c6.log`(4개 진행 라인 `[ 29%]/[ 59%]/[ 89%]/[100%]`; 브리핑이 명시한 「242 tests, rc」) |
| `ruff check tos/src tos/tests tests/tos_l3 tools` | - | `All checks passed!` rc 0 | `$S/judgment/ruff.log` |
| `black --check tos/src tos/tests tests/tos_l3 tools` | 70 | `69 files would be reformatted, 751 files would be left unchanged.`(black 26.5.1) — 무증가(−1) | `$S/judgment/black.log`; 이 명령의 `rc=0`은 파이프의 종료 코드이지 black 자신의 것이 아니다(브리핑 메모 (2) — black은 `--check`에서 재포맷 대상이 있으면 통상 비0을 반환하므로, 이 로그의 `rc=0`을 black 통과로 읽지 않는다) |
| `mypy tos/src/tos --ignore-missing-imports --no-error-summary` | 8 | `error:` 8건(mypy 2.3.1) · `error_count=8` · `rc=1` — 무증가(0) | `$S/judgment/mypy.log` |
| `tools/tos_spec_status.py --check` | - | rc 0 · `TOS spec status PASS: documents=13, ADRs=45, ... restricted_live=NOT_AUTHORIZED, production=NOT_AUTHORIZED` | `$S/judgment/spec-check.log` |
| `tools/tos_contract_check.py`(Layer 4) | - | rc 0 · `tos-contract: PASS — 자기참조 stale 위반 없음` | `$S/judgment/contract-check.log`(RUN 1) |
| `tools/tos_contract_check.py --self-test`(Layer 4) | - | rc 0 · `self-test: PASS — 뮤테이션 145종 전부 판별 · 죽은 검사 0 · 앵커 불일치 0 · 역방향 과잉 차단 0 · 대조군 무효 0 · 분류기 대조군 2종 전건 통과` | `$S/judgment/contract-check.log`(RUN 2, 말미) |

`Phase 0 완료 주장은 D0-A 이후에만`(계약 `:4541`): D0A-FIRST `28475ca1`은 PR #638로 main에
착지했다(`merged_at=2026-09-02T08:57:41Z` — §1 223행, 09-03/09-04 두 실측이 동일 값).

---

## §4 CI 실측 (gh · GET)

측정 head `d07646c2`, 그 직전 push된 head `c5550229`에는 **CI run 이 없다** — `tos-gate`는
`on: [pull_request]` 전용 워크플로이고 현재 이 브랜치에 열린 PR이 없기 때문이다(브리핑 메모 (4)).
이 head 의 CI 판정은 **미측정 — PR 미개설**로 기록한다.

브랜치 `mission-critical-trading-operating-system`의 가장 최근 CI run 12건(모두 PR head 였던
과거 리비전에 대한 결과이며 `d07646c2`/`c5550229`에 대한 것이 아니다):

| 워크플로 | head | 결과 | 시각 |
| --- | --- | --- | --- |
| tos-gate | `1964de73` | success | `2026-09-02T13:29:00Z` |
| tos-firewall | `1964de73` | success | `2026-09-02T13:29:00Z` |
| Tests | `1964de73` | success | `2026-09-02T13:29:00Z` |
| tos-gate | `44ffce5e` | success | `2026-09-02T13:05:40Z` |
| tos-firewall | `44ffce5e` | success | `2026-09-02T13:05:40Z` |
| Tests | `44ffce5e` | success | `2026-09-02T13:05:40Z` |
| Tests | `a9da27b0` | success | `2026-09-02T11:12:40Z` |
| tos-gate | `a9da27b0` | success | `2026-09-02T11:12:40Z` |
| tos-firewall | `a9da27b0` | success | `2026-09-02T11:12:40Z` |
| Tests | `21c47e42` | **failure** | `2026-09-02T08:37:52Z` |
| tos-gate | `21c47e42` | **failure** | `2026-09-02T08:37:52Z` |
| tos-firewall | `21c47e42` | **failure** | `2026-09-02T08:37:52Z` |

`main`의 최근 CI(6건, main push 트리거이므로 `tos-gate` 없음):

| 워크플로 | head | 결과 | 시각 |
| --- | --- | --- | --- |
| tos-firewall | `70b100e7` | success | `2026-09-02T13:36:15Z` |
| Tests | `70b100e7` | success | `2026-09-02T13:36:15Z` |
| tos-firewall | `4a0d122b` | success | `2026-09-02T13:13:44Z` |
| Tests | `4a0d122b` | success | `2026-09-02T13:13:44Z` |
| tos-firewall | `d56785ab` | success | `2026-09-02T11:20:05Z` |
| Tests | `d56785ab` | success | `2026-09-02T11:20:05Z` |

09-03 기록 대비 CI 표는 변화가 없다(같은 리비전 집합) — 유일한 차이는 측정 head 가
`faea9720`(09-03)에서 `d07646c2`(09-04)로 이동했고, 두 head 모두 PR 미개설로 CI 미측정
상태라는 점이다.

출처: `$S/judgment/ci.log`.

---

## §5 §12.3 절차표 9행(codex-reviewer 적대적 코드 리뷰) 실측

09-03 기록은 이 행을 「미실행으로 관측됨」으로 남겼다. 그 사이 레인 A가 **실행되어
approve로 종결**됐다:

- 정본: `docs/reviews/phase0-codex-records/20260904-155704/verdict.md`
  (`job_id: review-mtmnmhm1-pc6tnu` · `reviewed_at_head: c555022922f2ad9efb09e90f734bdfd18884efb0`
  · `verdict: approve` · `findings: []`(0건) · `subcommand: adversarial-review (--wait ·
  setsid · base 28475ca1^ · scope branch · 재심 #6)`).
- 판정문 그대로: 「§12.3 절차표 9행 레인 A 게이트 개방(HEAD c5550229). §11 `D0-5` = MET(7/7
  판정됨 · 5 UNBOUND · resolver/marketfeed VALUED+UNBOUND). 이 approve 는 작업 트리 전체에
  결속된다 — 코드 한 줄이라도 바뀌면 무효·재심.」
- 재심 이력(레인 A, `docs/reviews/phase0-codex-records/README.md` 색인표): 1차
  `20260903-165133`(needs-attention 3) → #1 `20260904-001114`(needs-attention 3) → #2
  `20260904-100015`(needs-attention 1) → 레인 B 측면 `20260904-101247`(approve) → #3
  `20260904-101638`(approve · 이후 C4로 무효) → #4 `20260904-150103`(needs-attention 1) →
  #5 `20260904-154559`(needs-attention 1) → #6 `20260904-155704`(**approve · findings 0**).
- 레인 B(계약) 최신 approve: `docs/reviews/phase0-completion-contract/20260904-133500/verdict.md`
  (`job_id: review-mtmgna46-osp4fm` · `reviewed_at_head: 48243cd2e07c1357a389e670cf2f23af479d1595`
  · `verdict: approve` · 에라타 52~56차 + O-6 재결속).

**이 approve가 결속하는 head 는 `c5550229`다.** 그 뒤 1커밋(`d07646c2`)이 붙었는데,
`git diff --stat c5550229 d07646c2`는 `docs/reviews/phase0-codex-records/**` 137개 파일
전량 신규 추가(+18,852/−0)뿐이며, 레인 A 심사 범위 지정(`git diff 28475ca1^ HEAD -- .
':!docs/plans' ':!docs/reviews'`)이 `docs/reviews`를 이미 제외한다 — 따라서 그 커밋은
승인 범위 밖의 docs 전용 변경이다. 다만 `docs/reviews/phase0-codex-records/README.md`
자신이 명시하듯 「`reviewed_scope_digest`는 HEAD `c5550229`의 작업 트리 전체에 결속되며,
그 이후 트리 digest가 바뀌면 codex-gate 규율상 재심 대상」이다 — **레인 A를 `d07646c2`에
대해 재실행할지는 운영자 결정**이며, 이 기록은 그 결정을 대신하지 않는다.

또한 09-03 기록이 `NONE`으로 남겨두었던 marketfeed 완료 주장은 독립 확인 심사
(`docs/reviews/phase0-codex-records/20260904-131909-marketfeed/verdict.md`,
`verdict: needs-attention`, `claim: marketfeed — tos/src/tos/marketfeed 패키지는
VERIFICATION-PROFILE-002 의 결속 값을 소비하지 않는다`)로 **거짓으로 판정**되어
`UNCHK-026`이 제거되고 D0-5 marketfeed 셀이 `VALUED+UNBOUND`로 재분류됐다(§2 참조).

---

## §6 S-26(계약 자신의 종결 자격) 실측 — 종결 주장이 아니다

계약 §11.1 은 §11 표(Phase 0 종료 조건)와 S-26(계약 «종결» 자격)을 별개 축으로 분리한다
(`§11.1: R-F4 수렴하지 않는다 → S-26 이 유일 정본, §11.1 은 포인터일 뿐`). 이 절은 측정값만
기록한다.

- ① 계약 blob 은 마지막 편집(C1⁗ `8923aab2`, 에라타 56차) 이후 무변경(bound-path 커밋 0건 —
  §0 U-15 R-7 currency).
- ② 그 편집 이후 material 0 인 독립 재심 = **1건**(`docs/reviews/phase0-completion-contract/
  20260904-133500/verdict.md`, approve, findings 0). S-26 ②는 **연속 2회**를 요구하므로
  이 1건만으로는 미충족.
- ⑤·⑧: 계약 본문에 열린 상태로 기록돼 있다(09-03 기록 이후 이 두 축을 닫는 처분은
  관측되지 않았다).
- 따라서 S-26의 AND는 **충족되지 않으며**, 이 기록은 부분·전체를 불문하고 종결을 주장하지
  않는다(S-26 머리말이 「부분 종결」 표기를 금지한다).
- 2026-08-30 운영자 지시(재심 #21 종결)는 유효하며, 이 기록은 그 재심을 재개하지 않는다.
  다만 2026-09-04 운영자 지시로 그 정지는 **에라타 52~56차 범위에 한해서만** 해제되어
  레인 B 재심이 위 5커밋에 대해 진행됐다 — 그 범위 밖에서는 정지가 여전히 유효하다.
- S-26 ⓒ: 종결 판정 기록은 문서 «밖»에서만 이뤄진다 — 이 파일은 계약 문서 밖이다.

---

## §7 이 기록이 하지 않는 것

- 계약·상위 계획 무편집(bound paths), `tos-spec/**`·`tools/**`·`config/**`·`.github/**` 무편집.
- 기계 상태 불변 — `prevention_control_state`·`d0a_entry_state` 등 어떤 상태값도 이
  기록으로 바뀌지 않는다.
- G1~G3 미부여(§10).
- `restricted_live`/`production` `NOT_AUTHORIZED` 불변.
- verdict·countersign 이 아니다 — 완료 판단은 별도 기록(`PHASE0-COMPLETION-DECISION.md`,
  현재 `decision: PENDING_OPERATOR_COUNTERSIGN` 초안)의 소관이다.
- 레인 A(`c5550229` 결속)를 측정 head(`d07646c2`)로 재실행하는 결정 — 운영자 소관(§5).
- S-26 종결 판정 — §6은 측정값만 기록하며 AND 미충족을 스스로 진술한다.
