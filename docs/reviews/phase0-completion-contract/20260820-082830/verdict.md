# verdict — 레인 B (계획 심판) · v2.21 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: 93522c098751cd8cdc216393beeaf50f03604943
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 298869e057e71914cd239b6bffee9f00de38fbd7b47820fa1027278ab8921a8e
reviewed_version: v2.21 (계약 7,554행 에라타 3차 재동결 c4d97118 · 개발계획 580행 0528a919) — 동결 0528a919 · 증거 3e0f2429 · 에라타 65cf2635/7adc1246/c4d97118 · addendum 83f12afd/5954b22d/b5afa6f6 · INDEX 85070bb3 · 재결속 93522c09
findings: 4                        # high 2 / medium 2 — 직전 #1 회피(2연속) · #2(#5/#6) 부분해소(3연속) · 신규 2 · 아크 누적 해소 11 불변
prior_verdict: .omc/review/20260819-193235/verdict.md   # v2.20 재심
mode: A (adversarial-review, --scope working-tree, --background), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-mt0r7xm7-tk5k3w / codex thread 01a01c77-f69d-7c30-952e-2b055ed60748 (turn 01a01c77-f7f1-7e10-bdc7-cbb6ee663a09)
     # 채택 잡은 7m 39s 정상 완주 · parseError null · codex.status 0 · stderr "" · write false
     # 선행 3회는 환경 결함(아래 «디스패치 경위») — 심사 내용과 무관
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **불변**(HEAD·`plan_scope_digest`·
내용-only digest `0752d016…` == 아티팩트 보유값 `OQ-11-DISPOSITION.md:9`). Codex 도
결속 HEAD·두 digest·커밋 순서·**두 동결 blob 과 후속 대상-계획 편집 0**을 독립 확인
("all match"). 재결속은 **두 문서 모두 개정된** 내용(계약 에라타 3차 `c4d97118`·
개발계획 `0528a919`)에 대해 1회(`93522c09`).

## 디스패치 경위 (환경 결함 — 판정 무관하나 기록)

채택 잡 이전 3회 시도가 실패했다. **그중 2회차가 이 게이트의 fail-closed 규칙이
정확히 겨냥하는 형태를 만들었다**:

| # | job | 결말 |
|---|-----|------|
| 1 | `review-mt0q87vu-u3iy7q` | companion 의 `--background` 가 클라이언트에 붙어 스트리밍·블록 → Bash 3분 타임아웃 SIGTERM 이 프로세스 그룹째 종료. **레지스트리는 `running` 잔존 — `status` 의 `running` 은 프로세스 생존의 증거가 아니다** |
| 2 | `review-mt0r1dos-8j1smi` | 같은 클래스 예상되어 선제 `cancel`. **중단 직전 산출 = `Verdict: needs-attention / No material findings.` (`Turn interrupted`·EXIT=1)** |
| 3 | `setsid` 런치 | macOS 에 `setsid` 부재 — 잡 생성 0 |
| 4 | `review-mt0r7xm7-tk5k3w` | `perl POSIX::setsid()` 완전 분리(PID 40657·PPID 1) → 정상 완주. **채택** |

**2회차 산출물은 판정이 아니다.** `Turn interrupted` 의 부분 산출이 스키마 모양을
갖췄고 «findings 0» 을 말했다 — 그것을 판정으로 읽었으면 이번 판은 **findings 4 대신
0** 으로 기록됐다. 「판정 불능 = 실패이지 통과가 아니다」가 산문 규칙이 아니라 실제
회피 경로임을 이번 실행이 실증한다. `codex.status`·`parseError`·완주 여부를 값으로
확인하고 채택했다.

## 처분

**직전 2건: #1 회피(2연속) · #2(#5/#6) 부분해소(3연속)** — **신규 해소 0 · 아크 누적
해소 11 불변**. `CLAUDE.md` 비협상 직접 충돌 **없음**(14판 연속). **S-20 종수 14 일관
확인**(심판 실측 — 오케스트레이터 독립 실측도 일치). **S-22: 문언 전파는 일어났으나
의미 소비자 전파가 미완**(심판 표현) — 오케스트레이터 실측으로 §8 T-84 행(`:2891`)에는
⑬a~⑬j 전건 전파 확인, 그러나 `:5752` U-17-d 대조군 줄은 여전히 ⑬ 를 «비활성 리터럴»
(v2.20 어휘)로 적어 v2.21 «정본 불일치 클래스» 재편이 미전파(아래 관측).

신규 2건의 성격:

- **F#2 (high) = 신규 결함 클래스** — «검증의 두 층이 서로 다른 객체를 식별한다».
  blob 층은 YAML **잡 id** 로, 서버 층은 **표시 이름**으로 고르는데 **에라타 3차가
  R-3 과잉 차단 완화로 잡 `name` 을 자유 문자열로 허용**하면서 두 키가 분리 가능해졌다.
  **직전 에라타의 완화가 연 자리**다.
- **F#4 (medium) = R-1 재발 클래스** — 계약이 «닫힌 집합»·«핀»이라 말하고 **값을 두지
  않아** 술어가 형식만 검사하는 자리. 에라타 3차가 checkout SHA 한 자리를 닫았으나
  같은 클래스가 `permissions`·`runs-on`·`with[fetch-depth]`·YAML 파서 4자리에 잔존.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

NO-SHIP. HEAD `93522c09`, plan_scope_digest `298869e0…`, bound_set_digest `0752d016…`, commit order, both frozen blobs, and zero later target-plan edits all match. Prior findings: #1 회피—direct ⑬c/⑬g strings are rejected, but the canonical order still permits an unapproved harness to execute and restore itself before hashing; #2 부분해소—ownership wording moved pre-D0-A, but no authoritative pre-D0-A U-17 consumer is produced and the claimed proof uses the wrong harness bytes. Criteria: (1) order/dependencies BLOCK, (2) hidden assumptions BLOCK, (3) verifiability BLOCK, (4) failure handling BLOCK; separate rollback defect not found, (5) scope/overdesign not applicable, (6) no direct CLAUDE.md non-negotiable conflict, (7) omissions BLOCK. S-20 remains consistently 14 cases; S-22 textual propagation occurred, but semantic consumer propagation is incomplete.

Findings:
- [high] [#1 회피] The harness runs before its digest is verified (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5482-5514)
  The canonical order is checkout → run harness → verify sha256. Because the checkout is writable, a non-approved `tools/tos_entry_harness.sh` can execute, replace its own path with the published canonical bytes, and exit 0. The following checksum then sees `957bf49d…`; both server steps report success and the static workflow remains canonical, so U-17 can return `PREVENTION_ACTIVE` although the approved bytes never executed. This is a deterministic in-job counterexample, not a GitHub-internal residual boundary. Detecting literal `|| true`/`set +e` variants therefore does not satisfy the prior recommendation.
  Recommendation: Keep #1 and shipment blocked until the authoritative U-17 path rejects a self-repairing, initially mismatched harness with non-zero/non-ACTIVE and proves the executed bytes are the bytes whose digest was verified.
- [high] Blob validation and server validation can select different jobs (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5479-5544)
  The blob side validates `jobs.&lt;gate-job&gt;` while allowing an arbitrary job `name`; the server side later selects a job by display name. A workflow can therefore keep a canonical `jobs.tos-gate` under another display name and add a second job named `tos-gate` whose two named steps merely succeed. Workflow path/head checks still match, but the required check and server steps come from the bypass job. The recorded executor confirms the split: ADDENDUM-3:939-945 validates `jobs[GATE_JOB]`, whereas :975-1003 filters server jobs only by `name`, without uniqueness or job-id correlation.
  Recommendation: Block until a same-workflow duplicate-name mutation is non-ACTIVE and the blob object, check-run, and server job are proven to identify one unique job.
- [medium] [#2 부분해소] The pre-D0-A sequence still lacks its authoritative verifier (docs/plans/2026-08-11-tos-completion-development-plan.md:270-275)
  The development prerequisite materializes the ruleset, workflow, and `957bf49d…` harness, but not the separate `u17-verify` executable required by the guard chain. The contract identifies its consumer as a reviewer or post-D0-A checker (:5366-5372, :5748-5767). Worse, the cited ordering proof uses a synthetic `echo ENTRY_OK` harness whose recomputed hash is `fbc0d9b5…`, then reports ACTIVE (V221 evidence :1924-1977); with `D=∅`, the contract explicitly skips revision checks (:5567-5570). Thus the phase labels align, but the required pre-D0-A artifacts are not authoritatively verified before consumption.
  Recommendation: Keep #2 partially resolved until the same pre-D0-A producer owns the verifier as an explicit prerequisite and the authoritative path reaches ACTIVE using the canonical harness without any D0-A or Phase 1 artifact.
- [medium] The purported closed template still contains open contract values (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5477-5493)
  The contract calls `permissions` minimal but supplies only an example, calls `runs-on` a closed literal set but appends “etc.”, describes checkout `with` as minimal, and names only an unspecified existing YAML parser. The hand executor chooses exact permission/runner sets, yet ADDENDUM-3:917-920 merely limits checkout keys and never requires `fetch-depth: 0` or checks its value. Consequently two consumers can make different conforming decisions for the same blob—the same form-only gap that produced the arbitrary-checkout-SHA erratum.
  Recommendation: Do not accept the closed-world claim until every accepted value and parser contract is fixed and the authoritative consumer rejects omitted/altered checkout depth, undeclared runners or permissions, and parser-ambiguity fixtures.

Next steps:
- Keep Lane B, D0-A implementation, and shipment blocked while any finding remains.
- Any target-plan edit invalidates the verified digests and requires a fresh freeze, binding, and adjudication.
```

### 구조화 JSON 원문 (`result review-mt0r7xm7-tk5k3w --json` · `confidence` 포함 · verbatim)

```json
{
  "verdict": "needs-attention",
  "summary": "NO-SHIP. HEAD `93522c09`, plan_scope_digest `298869e0…`, bound_set_digest `0752d016…`, commit order, both frozen blobs, and zero later target-plan edits all match. Prior findings: #1 회피—direct ⑬c/⑬g strings are rejected, but the canonical order still permits an unapproved harness to execute and restore itself before hashing; #2 부분해소—ownership wording moved pre-D0-A, but no authoritative pre-D0-A U-17 consumer is produced and the claimed proof uses the wrong harness bytes. Criteria: (1) order/dependencies BLOCK, (2) hidden assumptions BLOCK, (3) verifiability BLOCK, (4) failure handling BLOCK; separate rollback defect not found, (5) scope/overdesign not applicable, (6) no direct CLAUDE.md non-negotiable conflict, (7) omissions BLOCK. S-20 remains consistently 14 cases; S-22 textual propagation occurred, but semantic consumer propagation is incomplete.",
  "findings": [
    {"severity": "high", "title": "[#1 회피] The harness runs before its digest is verified", "body": "The canonical order is checkout → run harness → verify sha256. Because the checkout is writable, a non-approved `tools/tos_entry_harness.sh` can execute, replace its own path with the published canonical bytes, and exit 0. The following checksum then sees `957bf49d…`; both server steps report success and the static workflow remains canonical, so U-17 can return `PREVENTION_ACTIVE` although the approved bytes never executed. This is a deterministic in-job counterexample, not a GitHub-internal residual boundary. Detecting literal `|| true`/`set +e` variants therefore does not satisfy the prior recommendation.", "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md", "line_start": 5482, "line_end": 5514, "confidence": 0.99, "recommendation": "Keep #1 and shipment blocked until the authoritative U-17 path rejects a self-repairing, initially mismatched harness with non-zero/non-ACTIVE and proves the executed bytes are the bytes whose digest was verified."},
    {"severity": "high", "title": "Blob validation and server validation can select different jobs", "body": "The blob side validates `jobs.&lt;gate-job&gt;` while allowing an arbitrary job `name`; the server side later selects a job by display name. A workflow can therefore keep a canonical `jobs.tos-gate` under another display name and add a second job named `tos-gate` whose two named steps merely succeed. Workflow path/head checks still match, but the required check and server steps come from the bypass job. The recorded executor confirms the split: ADDENDUM-3:939-945 validates `jobs[GATE_JOB]`, whereas :975-1003 filters server jobs only by `name`, without uniqueness or job-id correlation.", "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md", "line_start": 5479, "line_end": 5544, "confidence": 0.99, "recommendation": "Block until a same-workflow duplicate-name mutation is non-ACTIVE and the blob object, check-run, and server job are proven to identify one unique job."},
    {"severity": "medium", "title": "[#2 부분해소] The pre-D0-A sequence still lacks its authoritative verifier", "body": "The development prerequisite materializes the ruleset, workflow, and `957bf49d…` harness, but not the separate `u17-verify` executable required by the guard chain. The contract identifies its consumer as a reviewer or post-D0-A checker (:5366-5372, :5748-5767). Worse, the cited ordering proof uses a synthetic `echo ENTRY_OK` harness whose recomputed hash is `fbc0d9b5…`, then reports ACTIVE (V221 evidence :1924-1977); with `D=∅`, the contract explicitly skips revision checks (:5567-5570). Thus the phase labels align, but the required pre-D0-A artifacts are not authoritatively verified before consumption.", "file": "docs/plans/2026-08-11-tos-completion-development-plan.md", "line_start": 270, "line_end": 275, "confidence": 0.98, "recommendation": "Keep #2 partially resolved until the same pre-D0-A producer owns the verifier as an explicit prerequisite and the authoritative path reaches ACTIVE using the canonical harness without any D0-A or Phase 1 artifact."},
    {"severity": "medium", "title": "The purported closed template still contains open contract values", "body": "The contract calls `permissions` minimal but supplies only an example, calls `runs-on` a closed literal set but appends “etc.”, describes checkout `with` as minimal, and names only an unspecified existing YAML parser. The hand executor chooses exact permission/runner sets, yet ADDENDUM-3:917-920 merely limits checkout keys and never requires `fetch-depth: 0` or checks its value. Consequently two consumers can make different conforming decisions for the same blob—the same form-only gap that produced the arbitrary-checkout-SHA erratum.", "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md", "line_start": 5477, "line_end": 5493, "confidence": 0.96, "recommendation": "Do not accept the closed-world claim until every accepted value and parser contract is fixed and the authoritative consumer rejects omitted/altered checkout depth, undeclared runners or permissions, and parser-ambiguity fixtures."}
  ],
  "next_steps": [
    "Keep Lane B, D0-A implementation, and shipment blocked while any finding remains.",
    "Any target-plan edit invalidates the verified digests and requires a fresh freeze, binding, and adjudication.",
    ""
  ]
}
```

> 포워더 전달: parseError null·codex.status 0·stderr ""·target working-tree explicit·write false·
> 채택 잡 재시도 0(선행 3회는 환경 결함). `next_steps[2]` 빈 문자열은 산출 잔여물(내용 손실 없음).
> Codex 가 두 계획 문서·직전 verdict·증거 4편(V221 + addendum ×3)·`CLAUDE.md` 를 직접 통독.

---

# 수용검사 (오케스트레이터) — **채택 4 / 기각 0**

기각 가능 사유 3가지(팬텀 `file:line` / 의도적 silenced / 비협상 배치) 중 **해당 없음**.
전건 실측.

| # | sev | 실측 | 처분 |
|---|-----|------|------|
| 1 | high (#1 회피·2연속) | `:5482-5487` **«`steps` = 정확히 3개·순서 고정: [① 체크아웃 · ② 정본 A 스텝 · ③ 정본 B 스텝]»** 리터럴 확인 — 정본 A = `bash tools/tos_entry_harness.sh`(**실행**), 정본 B = `printf '%s  …' 957bf49d… \| shasum -a 256 -c -`(**검증**). **실행이 검증보다 앞선다**. 계약 `:5512-5514` 는 «정본 B 는 파일 sha 불일치 시 … digest 불일치의 «실패 전파»를 정본이 «구조로» 보장한다» 고 적는데, 자기수복 하니스는 **스텝 ② 에서 실행된 뒤 자기 파일을 정본 바이트로 덮고 exit 0** → 스텝 ③ 이 보는 것은 이미 정본이라 `OK`/0. 두 스텝 success·정적 blob 정본 유지 → `PREVENTION_ACTIVE`. **정직 경계(`:5528-5540`)는 잔여를 «잡 «밖»»(다른 잡의 아티팩트/캐시 오염·runner 이미지·GitHub 내부·스텝 «이름» 위조·checkout 자체 신뢰)로 열거**하는데 이 반례는 **잡 «안»·체크아웃 워크스페이스**다 — 선언된 경계에 포섭되지 않음 확인. 의도적 silenced 아님 | **채택** |
| 2 | high (신규 클래스) | 계약 `:5476-5481` 의 닫힌 세계는 `jobs.<게이트 잡>` **하나**와 워크플로 수준 4항(`defaults`/`env`/`permissions`/`on`)에만 걸린다 — **`jobs` 개수·형제 잡을 제약하는 문언 부재**(`:5460-5560` 전수 grep: «다른 잡» 은 정직 경계 문단 1회뿐, 그것도 «아티팩트/캐시 오염» 맥락). 실행기 실측으로 분열 확인: **ADDENDUM-3 `:940` `if GATE_JOB not in jobs:` = YAML 잡 id 로 선택** vs **`:983` `hit = [x for x in jobs if x.get("name") == GATE_JOB]` · `:987` `job = hit[0]` = 서버 표시 이름으로 선택·유일성 검사 없음·잡 id 상관 없음**. 그리고 **에라타 3차(`:5479`)가 R-3 완화로 잡 허용 키에 `name` 을 넣어** 두 키의 분리를 가능케 함 — 직전 에라타의 완화가 연 자리. 팬텀 아님·silenced 아님 | **채택** |
| 3 | medium (#2 부분·3연속) | 개발계획 `:270-275` 선행조건 = 룰셋·`tos-gate.yml`·**하니스 파일** 3종뿐 — `u17-verify` 부재 확인. 계약 `:5757-5762` **가드 체인 3단 «`bash <§12.3.4-R 하니스>` && `bash <u17-verify>` && `<D0A-FIRST>`»** 리터럴 확인 + `:5764-5767` «왜 하니스에 넣지 않는가 … **별도 실행기** + 가드 체인 3단» — `u17-verify` 가 하니스와 **구별되는 필수 산출물**임이 계약 자신의 문언. 계약 `:5368-5370` «판정 소비자 = … (**리뷰어 / D0-A 이후의 검사기**)» 확인 → pre-D0-A 소유자 없음. `:5567-5570` «**`D = ∅` 이면 (b)·(c) 는 «검증 대상 없음»**» 확인, 그리고 V221 G-2 순서 실증(`:1924-1980`)이 실제로 `U17-B D=∅ — (b)(c) 검증 대상 없음` 을 출력하고 `prevention_control_state=PREVENTION_ACTIVE`/`u17_rc=0` 도달 — **정본 대조가 있는 (b) 층이 통째로 vacuous 인 채 ACTIVE** 확인. 즉 «순서 실증»은 하니스 바이트에 대해 아무것도 증명하지 않는다(픽스처 자신도 «순서만 실증» 정직 표기). **단서**: 심판 본문의 `fbc0d9b5…` 리터럴은 **V221 전문 grep 0건 = 팬텀 하위 인용**(픽스처는 실체화된 하니스 파일의 sha 를 애초에 출력하지 않는다). 그러나 **finding 자신의 `file:line`(개발계획 `:270-275`)은 실재**하고 핵심 주장(u17-verify 누락·(b) vacuous)은 계약·증거에서 독립 확증 → 기각 사유 불성립. 팬텀 하위 인용은 다음 재심에 함께 제시 | **채택** (하위 인용 1건 팬텀 기록) |
| 4 | medium (R-1 재발 클래스) | `:5477` **«`permissions` 최소(예 `contents: read`)»** — «예» = 예시·값 미고정 · `:5480-5481` **«`runs-on` ∈ 닫힌 리터럴 집합(`ubuntu-latest`·`ubuntu-24.04` 등 GitHub-hosted)»** — «등» = 열린 열거 · `:5486-5487` 체크아웃 «최소 `with`[`fetch-depth: 0`]» 이나 ADDENDUM-3 `:917-920` 은 `set(w) - CHECKOUT_WITH_OK` 로 **허용 키 밖만 거부** — `fetch-depth` **존재·값 미검사** 확인 · YAML 파서는 «기존 도구»로만 지칭·구현 미고정. **에라타 3차가 닫은 R-1(«핀»이라 적고 값 부재 → 형식만 검사)과 동일 클래스가 4자리 잔존**. 오케스트레이터가 심판과 **독립으로 먼저 실측**한 자리(디스패치 전 기록)와 일치. 비협상 배치 아님(계약 리터럴 고정은 «하드코딩 금지» 조항과 무관 — 그 조항은 임계값·심볼·포트·Redis DB·스케줄의 **런타임 설정** 축이다) | **채택** |

비협상 대조(8항 전수): 선물 long/short 대칭 · 실계좌 증거금/실물 선물 주문 경로 ·
주식 EOD 일괄청산 · ClickHouse 신규 · RL/TFT 부활 · 하드코딩 · Redis DB 1 이탈/TTL 없는 키 ·
비KST 세션 로직 — **4건 어느 것도 배치 권고 아님**(14판 연속 충돌 0).

## 관측 (finding 아님)

- **S-20 종수 14 일관** — 심판 판정과 오케스트레이터 독립 실측 일치. §8 T-84 행
  (`:2891`)에 **⑬a~⑬j 전건 전파 확인**(에라타 #2/#3 의 S-22 형제 소비처는 이 표면에선
  닫혔다). ⑬ 하위 케이스는 종수를 늘리지 않는다는 «종수 불변» 주장도 정합.
- **잔여 S-22 1자리 (오케스트레이터 실측 — 심판 미지적)**: `:5752` U-17-d 대조군 줄이
  여전히 «**14종** [v2.19: ⑪ 연속성 · ⑫ GH_HOST · **v2.20: ⑬ 비활성 리터럴** · ⑭ 서버
  스텝]» — v2.21 이 ⑬ 를 «정본 불일치 클래스»로 **재편**했는데 이 소비처는 v2.20 어휘
  «비활성 리터럴» 유지. 종수(14)는 맞으나 **명명이 stale**. 다음 개정에서 함께 닫을 것.
- **#1 저작 경로 (심판 Recommendation 이행 방향)**: 정본 스텝 순서를 **검증 → 실행**으로
  뒤집는 것이 최소 교정이다 — [① 체크아웃 · ② **정본 B(sha 검증)** · ③ **정본 A(하니스
  실행)**]. `set -euo pipefail` 하에서 ② 가 비-0 이면 ③ 이 도달하지 않으므로 «검증된
  바이트가 실행된 바이트»가 **순서로** 성립한다(자기수복 반례 소멸 — 수복할 시점 자체가
  없다). T-84 에 «자기수복 하니스» 대조군 신설(초기 불일치 → 실행 중 정본 복원 → 여전히
  비-0/non-ACTIVE 여야 red). 정본 A/B 코드펜스·⑬ 하위 케이스·§8 행·(B) 주 전부 lockstep.
- **F#2 저작 경로**: 두 층의 **동일 객체 결속**이 필요하다 — (i) 잡 허용 키에서 `name`
  재-배제하거나 `name` 을 **계약 리터럴**로 고정(R-3 완화는 자유 문자열이 아니라 «정본
  이름»으로 되돌린다) (ii) 워크플로에 **게이트 잡 유일성**(그 `name` 을 갖는 잡이 정확히
  1개) 명문화 (iii) 서버 층을 이름 필터가 아니라 **check-run → job id 상관**으로 전환하고
  실행기 `hit[0]` 을 «유일하지 않으면 UNVERIFIED_REVISION» 으로 교정. T-84 ⑬k(동일
  워크플로 중복 이름) 신설.
- **F#4 저작 경로**: 4자리 전부 리터럴 고정 — `permissions` 정확 집합 · `runs-on` 정확
  리터럴 1~2개(«등» 제거) · 체크아웃 `with` = 정확히 `{fetch-depth: 0}`(존재·값 검사) ·
  **YAML 파서 구현·버전 계약 고정**(파서 모호성 픽스처 대조군 동반). R-1 이 남긴 클래스를
  **전수**로 닫는 것이 요점 — 한 자리씩 닫으면 다음 에라타가 또 나온다.
- **디스패치 2회차의 «findings 0» 미완 산출물** (위 «디스패치 경위») — 이 게이트의
  fail-closed 규칙이 겨냥하는 형태가 **이번 실행에서 실제로 발생**했다. 기록으로 남긴다.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
