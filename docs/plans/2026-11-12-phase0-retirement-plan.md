# Phase-0 판정 장치 퇴역 + git 이력 합치기 준비

- 날짜: 2026-11-12 · 운영자 지시: «Phase-0 도구 퇴역 계획도 같이 진행해, .git 로그도 불필요해 … 레거시 참조가 많으면 혼선이 생겨»
- 근거: Phase 0 는 2026-10-22 서명(#920)으로 닫혔고, 범위 축소 계획(`docs/plans/2026-10-22-tos-rescope-plan.md`) 이후
  완료 기준은 `TOS_PAPER_READY` 다. 계약서와 그 판정 장치는 역사 기록인데 CI 시간과 저장소 부피의 큰 몫을 차지하고,
  옛 커밋 sha 에 기대어 이력 합치기를 막는다.
- 앞선 정리: 참조 없는 문서 504개 삭제 PR(`docs/remove-unreferenced-docs`, 같은 날). 이 계획은 그 PR 머지 뒤의 main 을 기준으로 한다.

## 1. 지우는 것 (P1, PR 1개, 등급 B — CI 게이트를 바꾼다)

| 묶음 | 경로 |
|---|---|
| 도구 | `tools/tos_completion_status.py` · `tools/tos_contract_check.py` · `tools/.tos_contract_baseline.json` · `tools/tos_contract_index.py` · `tools/tos_entry_harness.sh` · `tools/u17-verify.sh` · `tools/wfcanon-v222.py` · `tools/ladder-v222e5.py` · `tools/pagelimb-v222e5.py` · `tools/spikes/phase0_contract/` |
| 설정 | `config/tos_completion.yaml` |
| 테스트 | `tests/tools/test_tos_completion_status.py` · `tests/tools/test_tos_contract_index.py` · `tests/tools/test_u17_verify.py` |
| 문서 | `docs/reviews/phase0-completion-contract/` · `docs/reviews/phase0-codex-records/`(앞 PR 에서 남은 것) · `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md` · `docs/plans/contracts/tos-phase0-completion-contract.manifest.yaml` · `docs/plans/2026-08-27-*` · `docs/plans/2026-08-28-c4-*` · `docs/plans/2026-08-06-tos-phase0-p03-dev-owner-assignment.md` · `docs/runbooks/u17-prevention-control.md` |
| 스펙 | `tos-spec/src/TOS-COMPLETION-STATUS.md`(+ `SUMMARY.md` 줄) · `tos-spec/src/verification/{EVIDENCE-REQUIRED-KINDS,EVIDENCE-SURFACE-MAP,PHASE0-UNCHECKABLE-REGISTER}.csv` · `tos-spec/src/part-1-foundation/decisions/` 의 Phase-0 전용 6개(OQ-11-DISPOSITION · OQ-11-RAISE-LEDGER · CLOSABLE-NO-APPROVAL-LEDGER · D0A-PREVENTION-CONTROL · U17-*) |

규모: 약 430 파일 · 16만 줄 · 17 MB. 남기는 것: `tos_firewall_check` · `tos_redigest` · `tos_size_budget` · `tos_spec_status` ·
`tos_profile_census` · `tos_recovery_drill` 과 tos-spec 의 RFC/GOV/ADR 본문 — 모두 살아 있는 게이트이거나 커널 테스트가 읽는다.
`docs/plans/2026-08-11-tos-completion-development-plan.md` 는 남긴다(`tos_spec_status` 경고와 그 테스트가 읽는다; 지우려면 별도 수정).

## 2. 같이 고치는 것

- `.github/workflows/tos-firewall.yml`: «phase0 completion contract checks» · «Layer 4 self-reference gate» · «Layer 4 self-test» · yq pin
  단계 삭제, 배터리에서 `test_u17_verify.py` 제거. `fetch-depth: 0` 은 남은 단계가 필요로 하지 않으면 기본값으로.
- `.github/workflows/tos-gate.yml`: **삭제하지 않는다.** 룰셋(id 21886181)이 `tos-gate` 체크를 필수로 요구하므로, 파일을 지우면
  모든 PR 이 오지 않는 체크를 기다린다. 대신 같은 잡 이름으로 하네스 실행을 `python tools/tos_redigest.py --check`(살아 있는 게이트,
  수 초) 로 바꾼다. 룰셋은 손대지 않는다.
- `.github/workflows/test.yml`: 경로 부정(57-62) · `--ignore=tests/tools/test_u17_verify.py`(262, 324) 정리.
- `pyproject.toml`: v222 동결 스크립트 ruff/black 제외 줄 삭제.
- `CLAUDE.md` «Read the index before the contract» 절과 `tos/CLAUDE.md` 의 계약/인덱스 안내: 계약서·인덱스 도구가 퇴역했다는 한 줄로 바꾼다.
  하네스 변경 이력 표에 한 행 추가.
- `docs/plans/INDEX.md` · `README.md`(u17 런북 링크) 의 죽은 항목 정리.
- 주석에만 남은 언급(`tos_profile_census.py` docstring, `tos/src/...` 주석)은 그대로 둔다 — 동작과 무관하고 커널 바이트를 건드리면
  `tos_redigest` 재도출이 필요해진다.

## 3. 확인 (측정으로만)

- CI 필수 체크(`tos-gate` · `ruff` · `tos-firewall`) 와 나머지 체크 green.
- 로컬: `python tools/tos_spec_status.py --check` · `tos_firewall_check.py` · `tos_redigest.py --check` · `tos_size_budget.py --check` rc 0,
  `pytest tests/tools/test_tos_*.py -n 4` green, `git grep -nE 'tos_completion_status|tos_contract_check|tos_contract_index|tos_entry_harness|u17-verify'`
  결과가 주석·역사 문서뿐.
- `config/tos_runtime/**` · `tos/src/**` 바이트 불변(`git diff --stat origin/main -- config/tos_runtime tos/src` 빈 결과) — 테넌트
  digest 와 세션에 영향 없음.
- 머지 시각: 세션과 무관(CI·문서만 바꿈)이므로 장중 가능.

## 4. 이력 합치기 준비 (P2 — 실행은 운영자)

P1 이 머지되면 옛 sha 를 실제로 따라가는 코드는 없다(조사 결과: 남는 것은 문자열 sha 와 `legacy-final` 태그 없으면 건너뛰는 검사 하나).
남은 막힘과 순서:

1. **열린 PR 정리.** 합치기 전에 열린 PR 은 모두 머지하거나 닫는다(새 루트 위로는 그대로 옮겨지지 않는다). 현재 5개 —
   #1067 · #1060 (11-12 15:40 뒤 머지), #1068 (TOS_PAPER_READY 뒤), #1053 · #1052 (11-16 머지 예정). 그래서 가장 이른 실행일은 #1068 이 정리된 뒤다.
2. **옛 이력 보관.** `git bundle create ~/.local/state/kis/history-archive-<날짜>.bundle --all` 로 전체 이력(태그 `legacy-final` 포함)을 파일로
   남기고 `git bundle verify` 통과를 확인한다. 문서가 «`legacy-final` (`6fc17c0f8d25`) 에 코드가 남아 있다» 고 적은 곳은
   «이력 보관 번들의 `legacy-final`» 로 바꾼다(합치기 직전 PR 1개).
3. **룰셋.** `tos-gate` 룰셋의 `non_fast_forward` · `deletion` 규칙을 잠시 끈다(운영자, GitHub 설정).
4. **합치기.** 새 루트 커밋 하나(`git checkout --orphan` → 전체 add → commit) 를 main 에 강제 push, 원격 브랜치·태그 정리. 스크립트는
   `~/.config/kis-probes/` 에 둔다: 실행 전 열린 PR 0 · 번들 verify ok · 작업 트리 깨끗 을 확인하고, 아니면 멈춘다.
5. **룰셋 복구**, 로컬 체크아웃·워크트리 재생성(`wt-paper` · `wt-cold` 는 다음 cron 이 새로 만든다), 다음 날 preflight 3방향 확인.

알려 둘 것: 저장소가 public 이라 GitHub 의 PR 참조(`refs/pull/*`)는 강제 push 로 지워지지 않는다 — 옛 커밋은 GitHub 쪽에 남고,
로컬과 새 클론이 작아지는 것이 실제 효과다. 원격까지 완전히 지우려면 새 저장소로 옮기거나 GitHub 지원 요청이 필요하다.

## 5. 되돌리기

- P1: PR `git revert`.
- P2: 번들에서 `git clone` 으로 옛 이력 복구, 필요하면 강제 push 로 되돌림.
