# Phase 0 완료 판정 — 완료 판단 시점 live 실측 기록 (4차 · PR #910 머지 head)

> **Document class**: 비규범 **측정 전사**(측정 기록). Phase 0 완료 판정(계약 §11) 자체가 아니다.
> 완료의 *결정*은 `docs/reviews/phase0-completion-contract/20261021-223338/PHASE0-COMPLETION-DECISION.md`
> (현재 `PENDING_OPERATOR_COUNTERSIGN` 초안)가 담당하며, 그 초안의 `measurement_record` 가 이 기록을 가리킨다.
> 이 기록은 3차 기록(`docs/reviews/phase0-completion-contract/20261021-223338/PHASE0-COMPLETION-JUDGMENT-LIVE.md`,
> head `b15069fd`)과 **같은 항목**을 레인 A 지적 수정(PR #910)이 착지한 head 에서 다시 잰 것이다. 3차 기록은
> 레인 A 재심 #7 의 증거로 그대로 남는다. 계약·상위 계획·`tos-spec/`·`config/`·`tools/`·`.github/` 무편집.
>
> `$S` = 측정 세션 스크래치 `p0rejudge2/logs/`. 로그는 커밋하지 않는다. 측정은 371051f4 분리 워크트리에서 했고
> 추적 파일 변경 0, 측정 뒤 워크트리를 제거했다.

## §0 결속 — 3차 대비 값 변경 0

| 항 | 값 | 출처 |
| --- | --- | --- |
| 측정 대상 head | `371051f478583f5bab0d5bed2f02df2facdde22f` = `origin/main` (PR #910 머지, `mergedAt=2026-10-21T14:47:07Z`) | `$S/binding.log:2-3`, `$S/ci.log:13` |
| 계약 blob | `6f94dfbbafd48fa3d1b4c73266fdfda19da9bce5` (3차와 동일) | `$S/binding.log:5` |
| 상위 계획 blob | `ec3464c068dff2030e0764f3b05c985a821730f5` (동일) | `:6` |
| `bound_set_digest` 재계산 | `045f3ae7565860df6e0c38d3c7ee49c76f3a4d3784d646279cd1be2727dbb429` == `OQ-11-DISPOSITION.md:15` == `20260905-214532/verdict.md:11` (동일) | `:8,13,14` |
| U-15 R-7 `git rev-list --full-history 97596460..HEAD -- <두 bound path>` | `0` · `97596460` 은 HEAD 의 조상 | `:16,18` |
| `1db8f9b8..HEAD --full-history` | `2` — 두 머지(`b3f1d2d5`·`97596460`) 모두 main 쪽 부모 `dc900970` 만 계약 blob `899689fc…`, 브랜치 쪽 부모와 머지 결과는 `6f94dfbb…`, 개발계획 blob 은 양 부모 `ec3464c0…` | `:20,22-31` |
| `tools/tos_entry_harness.sh` sha256 | `059e13f2…3d723177` == `.github/workflows/tos-gate.yml:17` 핀 | `:33,36` |
| `tools/u17-verify.sh` sha256 | `0b68ef85…bdf9814e` | `:41` |
| `D0A-PREVENTION-CONTROL.md:7` `operator_countersign` | `"chihun,lee 2026-08-28T05:23:48Z"` | `:53` |
| U-17 (b)② `scope:` | `U17-B2-DEVIATION-ACCEPTANCE.md:15-22` 와 동일 | `:60-67` |
| 스크래치 standalone 바이너리 | gh `2.63.2` sha256 `f687dc93…8618` · yq `v4.48.1` sha256 `99df6047…fd9f` (3차와 동일 바이너리) | `:47-51` |
| gh 인증 | `kakao-harris-lee` · Active account: true · 전부 GET | `$S/u17-live.log:26-30` |

## §1 U-17 live 실측 — 상태·사유·발화 2건 3차와 동일

명령: `PATH=<scratch bin>:$PATH U17_PYBIN=.venv/bin/python bash tools/u17-verify.sh .` (처음부터 standalone gh 사용 —
시스템 gh 로 돌린 fail-closed 1차 실행은 이번에는 없다). 로그는 단일본 245행이며 3차 로그(`u17-live2.log`)와 행 번호가
대응하지 않는다.

- `http=` 줄 23건 = `http=200` 22건 + `http=404` 1건(`:39` `U17-A1 …/branches/main/protection`, classic 보호 부재 —
  `:80` `classic=False ruleset=True`) · `--slurp` 호출 9건 전부 `status=200`(`:47, 61, 143, 158, 169, 180, 193, 204, 216`) ·
  열거 완전성 `RESULT=PAGES_OK` 9건
- 첫 호출 `U17-A00 apps/github-actions utc=2026-10-21T14:54:25Z http=200 x-github-request-id=C2BC:3DBEDF:292D7B:451C6A:6AD8D21F` (`:32`)
- 마지막 `x-github-request-id` 를 남긴 호출 `U17-BETA …/commits/21c47e42…/check-runs utc=2026-10-21T14:54:44Z http=200` (`:214`)
- 마지막 호출 `U17-B2s --slurp …/commits/21c47e42…/check-runs utc=2026-10-21T14:54:45Z status=200` (`:216`)

```text
239: U17-fire PREVENTION_UNVERIFIED_REVISION: (b)② d=28475ca1ca82fe99054a2cc04cf1b58e4550097a head=21c47e42ff1487282ce2f9da0df11756ff146a3a 4단계 ∀-success 위배 — [(0, 100181808552, 'failure')] (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함)
240: U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-09-02T08:57:41Z  (서버 부여 값만 · 커밋 author/committer date 불신)
241: U17-α ruleset 21886181: ruleset 21886181 updated_at=2026-09-06T15:21:13.608000+00:00 > t_land=2026-09-02T08:57:41+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가
242: U17-fire PREVENTION_CONTINUITY_UNVERIFIABLE: (α) ruleset 21886181 updated_at=2026-09-06T15:21:13.608000+00:00 > t_land=2026-09-02T08:57:41+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가 — 운영자 재심사 경로(영구 차단 아님)
243: prevention_control_state=PREVENTION_UNVERIFIED_REVISION
244: reason=(b)② d=28475ca1ca82fe99054a2cc04cf1b58e4550097a head=21c47e42ff1487282ce2f9da0df11756ff146a3a 4단계 ∀-success 위배 — [(0, 100181808552, 'failure')] (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함) [수집 2건 중 전순서 최소]
245: rc=1
```

3차와 같은 값: `u17_live_state=PREVENTION_ACTIVE`(`:79`) · workflow_id `343700405`(`:37`) · 적용 룰셋 `[21886181]`(`:78`) ·
`U17-ALFA5` α 포함 축(`:213`)·`U17-BETA1` β 축(`:224`) 통과 · (b)② 삼중값 == `U17-B2-DEVIATION-ACCEPTANCE.md` `scope:`.
**α 연속성 발화(`:241-242`)는 3차와 문자 단위로 같고, 여전히 그 `scope:` 밖이다.**

## §2 기계 표면 (§11) — 3차와 byte 동일

- `tools/tos_completion_status.py --check` → `RESULT: GREEN (violations=0)` · rc 0 (`$S/completion-check.log:39-40`)
- `--write` 뒤 `git status --short` 빈 출력 (`:53-54`) — 커밋된 `tos-spec/src/TOS-COMPLETION-STATUS.md` 가 현행
- 상태 라인 4종 `NOT_REQUIRED` · `ENTRY_OK` · `ENTRY_PROVENANCE_CLEAR` · `NO_ROWS_CLEAR` (`:8-11`), 완료 관측 전 항목(`:14-37`)
  3차와 문자 단위 동일
- `tos-spec/src/TOS-COMPLETION-STATUS.md` 는 파일 전체가 3차와 byte 동일(파일 전체 sha256
  `36e1bba68d9cbb501033741711d5b2dd91e3294a8ff651c8c6796c5c43f38b01`). §11 개관(`:116-146`):
  K-*·U-*·D0-1·A-1~3·D-1·D0-5 전부 `MET`, `U-17` 은 live 평가 필요(§1), `RES-1` `MET`

## §3 §11 «추가» 표 실측

| 항목 | 기준 | 실측 | 3차 대비 | 출처 |
| --- | --- | --- | --- | --- |
| `tos/tests` 전량 green | 계약 8,742 | dots=9,657 · nondot=0 · rc 0 · collect 합 9,657 | **+41** — `tos/tests/position/test_position_predicates.py` 9 → 50 (b15069fd..371051f4 의 `tos/tests` 변경은 이 파일 하나) | `$S/tos-tests.raw`(진행 줄 135개 · dots 9,657 · non-dot 0) · `$S/tos-tests.log:2`(`rc=0`) · `$S/collect.log:2-4` |
| `ruff check tos/src tos/tests tests/tos_l3 tools` | 0 | `All checks passed!` rc 0 (ruff 0.15.4) | 동일 | `$S/ruff.log:2-4` |
| `black --check` 같은 경로 | 70 무증가 | 0 · `918 files would be left unchanged.` (black 26.1.0) | 동일 | `$S/black.log:2-6` |
| `mypy tos/src/tos` | 8 무증가 | error 0 · rc 0 (mypy 2.3.1) | 동일 | `$S/mypy.log:2-4` |
| `tools/tos_spec_status.py --check` | PASS | rc 0 · 같은 PASS 줄 + 비차단 WARNING(163/16 ↔ 164/16) | 동일 | `$S/spec-check.log:2-4` |
| `tools/tos_contract_check.py` · `--self-test` | PASS | rc 0 · 뮤테이션 145종 전부 판별 | 동일 | `$S/contract-check.log:2-3,156-157` |
| `print-digests` vs 세 `release.yaml` | 일치 | `expected_code_digest: ba1de6b28ef1d961b3e77de1c65eef490efaac284041d8ee6c0f42261fd41b6e` · `expected_dependency_set_digest: 20559763…` == `config/tos_runtime/{paper,cp3-setup-d-long,cp3-setup-d-short}/release.yaml:849-850` | 신규 항목 · code digest 는 PR #910 이 `b06d01f9…` 에서 재도출 | `$S/digests.log:2-6,69-70,123-124,177-178` |

## §4 CI 실측 (gh · GET)

- `gh pr checks 910` → 8/8 pass (`$S/ci.log:3-11`) — `tos-gate` run `39616276272`
- 네 run(`39616276560` Tests · `39616276172` ruff · `39616276220` tos-firewall · `39616276272` tos-gate) 전부
  `headSha=9c6e15e66bd5b8233a08f53188c557ba5fdc3f88` · `conclusion=success` · `event=pull_request` (`$S/ci.log:15-18`).
  §5 가 보이듯 `9c6e15e6` 와 HEAD 의 트리는 동일하다.
- HEAD `371051f4` main push run 3/3 success — ruff·tos-firewall, Tests(`39619902863`, 측정 중 완료 `2026-10-21T15:06:12Z`) (`$S/ci.log:20-34`)
- HEAD 밖 관측: 3차와 같은 두 건(`65cb38c2` 스케줄 run `Dev/Test Containers`·`Tests` failure, 10-19). 새 실패 0 (`$S/ci.log:24-26`)

## §5 §12.3 절차표 9행(레인 A)

- **레인 A 재심 #8** `docs/reviews/phase0-codex-records/20261021-232321/verdict.md` — `reviewed_at_head: 9c6e15e66bd5b8233a08f53188c557ba5fdc3f88` ·
  `reviewed_scope_digest: 0d17df2e7cd374b7bfe933abd6aa26cf08752888d07d633747cc3c7de2b53bc5` · 잡 `review-mvi7d3uc-0lohyi` ·
  `--base c5550229 --scope branch`. 판정 원문: 「Verdict: approve」 · 「No material findings.」 · 「Resolved. PR #910 preserves nonterminal exposure symmetrically without understating the ARE decision sum.」
- 범위: 운영자 승인(2026-10-21) 커널 경로 + `tos/runtime/src/tos_runtime/riskstate/position.py` · `tos/runtime/tests/riskstate/` ·
  digest 파일(focus text 지시). 판정문은 Codex 샌드박스가 read-only 라 파일 기반 런타임 테스트를 돌리지 못했다고 적는다 —
  그 테스트는 §4 의 PR CI(`tos-firewall`)가 같은 트리에서 통과했다.
- **결속 간극 0**: 재심 범위 경로 한정 `git diff --stat 9c6e15e6 371051f4 -- <범위>` 출력 없음(`$S/laneA.log:21`) ·
  전체 `git diff --numstat 9c6e15e6 371051f4 | wc -l` = 0(`:23-24`) · `git log --oneline 9c6e15e6..371051f4` = 머지 커밋
  1개뿐(`:25-27`). 리뷰 레인이 따로 확인: 두 커밋의 트리 id 가 같고(`aa2c0b53…`) `9c6e15e6` 는 `371051f4` 의 두 번째 부모다.
  재심 #8 의 approve 는 이 head 의 트리에 결속된다.
- 3차 기록 §5 의 재심 #7 high finding(`tos/src/tos/position/predicates.py:131-140`)은 PR #910 이 고쳤고 재심 #8 이 「Resolved.」로 판정했다.
- 보존: `verdict.md` · `focus.txt` · `revision.txt` · `codex-result.json` · `job.txt` · `codex-wait.out` · `codex-wait.err`
  7개를 byte 동일 사본으로 보존(`cmp`). 원본의 `codex-result.err`(0바이트)와 빈 `evidence/` 는 복사하지 않았다.
  `reviewed_scope_digest` 의 계산 방식은 보존 아티팩트로 재확인되지 않는다.

## §6 S-26 — 3차와 동일, 종결 주장 아님

계약 편집 0(마지막 `1db8f9b8`, 2026-09-05) · 신규 계약 재심 0(최신 `20260905-214532`) · ⑥ 카운터 리셋 미발동 ·
⑤·⑧ 열린 상태 그대로 (`$S/s26-count.log`). 해석은 3차 기록 §6 과 같다 — S-26 의 AND 는 충족되지 않는다.

## §7 이 기록이 하지 않는 것

- 계약·상위 계획·`tos-spec/**`·`tools/**`·`config/**`·`.github/**` 무편집 · 기계 상태 불변
- G1~G3 미부여 · `restricted_live`/`production` `NOT_AUTHORIZED` 불변
- verdict·countersign 이 아니다 · U-17 α 연속성 발화의 수용(운영자 소관) · S-26 종결 판정
