# Plans Index

> **2026-11-14 — 역사 계획 은퇴.** 끝난 2026-07~09 커널·런타임 착지 기록과
> 상위 제안·측정 계획 35건을 지웠다. 남긴 것은 지금 도는 것(CP-3 테넌트 트리 ·
> 합성 venue 원장 · P2 선언형 필드)의 결정 기록, `TOS_PAPER_READY` 기준,
> 방화벽 설계 계약뿐이다. 내용은 git 이력에 그대로 있다:
> `git log --diff-filter=D -- docs/plans/`.

> **2026-11-12 — 미참조 과거 문서 정리.** 저장소 어디에서도 참조하지 않는 과거
> 문서를 삭제했다. 내용은 git 이력에 그대로 남아 있다:
> `git log --diff-filter=D -- docs/`.

## Current TOS integration entry — 2026-10-06

- [Control Plane and first tenant plan](2026-10-06-tos-control-plane-and-first-tenant-plan.md): CP-0 documentation complete; CP-1 implemented, deployed and observed (2026-10-07); CP-2 onward planned, paper-only migration scope.
- [CP-3 kickoff — first tenant candidate comparison and operator decisions](2026-10-07-tos-cp3-first-tenant-kickoff.md): operator-approved 2026-10-07 (all nine decisions as recommended; decision 9 re-decided 2026-10-08 as (a) rulebook-primary — see the next entry); first tenant = Setup D; DSL can only compare published scalars, so indicator math moves upstream; same-input parity needs new builds on both sides of the import firewall (JSONL indicator producer, in-tree Bar loader/driver runner, legacy reject emitter, decision-level diff, one-order-per-scope disposition); paper venue `max_quantity` is null today so paper can only observe decisions until sourced; §5 steps 1-2 implemented (B1a shared indicator producer, B2 legacy per-bar candidate/reject emitter and B3 decision-level diff, all `tools/tos_cp3/`), B1b in #877; B3's first real run over 101S6000 2025-12-01~2026-04-30 (35,612 bars) reports rule-level entry agreement 374/374 and 0 UNRESOLVED bars, with the 18 extra TOS actions attributed to B1a-D1/B2-L9 (min_confidence unpublished) and 176 legacy short fires to B1b-D5 (LONG-only render); the SHORT half closed 2026-10-09 (B1b SHORT render under `tos/runtime/cp3/short/`, B3 attribution made direction-aware from B1b's lineage rather than a caller flag): rule-level entry agreement 176/176, position-model 56/56, 0 UNRESOLVED, 12 extra TOS actions to B1a-D1/B2-L9 and 374 legacy long fires to B1b-D5; the LONG artifacts reproduce byte-for-byte under the new tool; `short_blocked_regimes` (decision 5) is declared but absorbs zero bars because the guard lives in `setup_d_adapter` after `check()` returns and B2 drives `check()` directly; B4 disposed as 체결 비교 포기 and stated in B3's summary.json scope block.
- [CP-3 decision 9 — venue quantity-limit source and mock GET probe design](2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md): operator chose (a) 2026-10-08, superseding the 10-07 probe-as-source recommendation; primary source = KRX 시행세칙 별표 17의2 **미니코스피200선물거래** row (the deployed/tenant product is mini `A056xx`): 정규거래 10,000 contracts (full `101xxxx` row 2,000 applies only to the parity dataset), 제164차 in force 2026-07-06; evidence `docs/broker-profiles/evidence/2026-10-08-krx-venue-limits/`; `VTTO5105R` is deposit/parameter-derived so the probe only corroborates (≥1 orderable, band matches 제56조 arithmetic); `price_min/max` are per-day dynamic, so decision 9 alone leaves `order_shape_admissible` UNKNOWN — the band-source wave is a separate operator decision (§6), with a prerequisite finding that the deployed `tick_size: 5` is the full contract's 0.05 while mini's regulation tick is 0.02. Design only; probe `P-VL`, evidence and tenant-tree values land in later PRs.
- [CP-3 band-source wave — tick 5→2 + band (i) broker read](2026-10-08-tos-cp3-band-source-wave-plan.md): operator decisions 2026-10-08 (max_quantity 10000 tenant-only · tick 5→2 · band (i) broker GET first). Runtime `VenueConstraintService` fills effective `price_min/max` from a policy-declared `_runtime.band_source` read at boot/phase change, bound to the snapshot's existing provenance fields; no kernel change. Intraday band only widens (제56조의2) so one boot read is conservative; three fail-open guards (validation set · trading-date · contract binding — v2 after review #883). Resident paper stays off (synthetic prices). §6 (A) first runtime network egress/token and (B) `_runtime` outside activation digest — both approved as recommended 2026-10-08.
- [CP-3 ③ live field producer](2026-10-10-tos-cp3-live-field-producer-plan.md): operator decisions 2026-10-10 — ③ accepted, data source = REAL-key GET-only `FHKIF03020200` minute chart for both seed (prior 3 sessions) and intraday. Re-runs B1a `produce_bars` over seed+today each minute (no second field implementation); `as_of_ms` = append time (800 ms budget), `source_id` `tos-cp3-live/<ver>`, atomic whole-file replace. PR-1 market-hours probe (M1–M4, 10-12) → PR-2 producer → PR-3 runner wiring → first genesis (approved) → band source on.
- [CP-3 band via producer (i-b′)](2026-10-15-tos-cp3-band-via-producer-plan.md): operator decision 2026-10-15 — band switch-on path (c). The band plan's §9 3 was not executable (host seal and token bound to the active ORDER scope, SYNTHETIC in every tree; runtime holds no KIS credentials by design). The ③ producer GETs `FHMIF10000000` REAL GET-only and appends `band.jsonl`; the runtime reads it via a new `band_source.kind: producer_journal` (zero sockets, zero credentials kept). Contract binding becomes a real read-side guard; new source-allowlist guard. PR-A producer → PR-B runtime + LONG switch-on (`expected_code_digest` re-derive).
- [CP-3 ④ tenant render and boot-path redesign](2026-10-09-tos-cp3-tenant-render-and-boot-path-plan.md): operator directive 2026-10-09 「다시 설계」. Renderer rule table → per-tree committed `RENDER.yaml` manifest (closed value-source set; members still always derived); exact-once anchor rule kept by collapsing repeated tenant coordinates with YAML anchors/aliases (missed alias → existing loader TBD refusal); tenant direction declared+verified, not substituted; journal split synthetic (resident) vs external (③, required `--journal-path`); pre-③ boot-proof only in a scratch data dir. Resident render must stay byte-identical. No kernel/runtime change.
- [Legacy removal (2026-11-07, #1040)](2026-11-07-legacy-removal-plan.md): **operator-approved 2026-11-07.** Removes legacy code outside the import closure of the TOS-side roots (`tools/tos_cp3`, `tools/broker_probes`, `sts tos`, the dashboard `/tos` route) in seven PRs L1–L7. Measured: `tos/` reaches 0 legacy modules, `tools/tos_cp3` 240/739. The session code digest covers only `tos`/`tos_runtime`. The legacy Setup D code that B3 compares against stays byte-for-byte until `TOS_PAPER_READY`. Merges after the close only; none on 11-11–11-13 (roll) or 11-19.
- [TOS FLAT exit held quantity (2026-11-04, #1025)](2026-11-04-tos-flat-exit-held-quantity-plan.md): **operator-approved 2026-11-03 (option A).** Exit (FLAT/`ZERO_POSITION`) proposals were refused at step 2 in every CP-3 tree. The cause is twofold: the admitted set holds only `RISK`, and step 2 reads the held position from the in-memory engine ledger, which the entry fill releases (#966). The runtime step-2 wrapper now feeds FLAT proposals the same durable entry remainder step 6 uses (no kernel change), and the three trees admit `ZERO_POSITION`.
- [TOS unsent reservation release (2026-11-01, #974)](2026-11-01-tos-unsent-reservation-release-plan.md): **operator-approved 2026-11-01** (replaces the 10-29 hold; kernel change approved; no Codex). A CLOSE halted after step 9 but before send leaves a `NOT_SENT` reservation, and every later close is denied. Synthetic trees have no manual fallback, and the venue ledger (on after 11-13) makes this reachable. Option A: release only reservations proven unsent by a five-condition evidence predicate (kernel `discard_unsent` + RCL `FINAL_QUANTITY_PROOF` qty 0). Re-measured 11-01: 0 occurrences.
- [TOS synthetic venue ledger (2026-10-31, #1011)](2026-10-31-tos-synthetic-venue-ledger-plan.md): **operator-approved 2026-10-31 (option A; switch on after 11-13).** Synthetic trees seal their scope after the first entry because the only witness re-reads the evidence store (`WITNESS_NOT_INDEPENDENT`), so the fill never reaches `POSITION_CONSUMED`. Recommended option A: the runtime records synthetic fills at the transport boundary into a separate `venue_ledger.sqlite3`, and a new witness reads only that file. The W2-R rule stays, the kernel is untouched, and #1015's close bound goes live. Also splits the `WITNESS_NOT_INDEPENDENT` hold reason from the POST_TRADE "conflict" reading.
- [TOS_PAPER_READY relaxation (2026-11-11)](2026-11-11-tos-paper-ready-relaxation.md): operator directive — sentence 1 becomes 5 cumulative clean LONG trading days in a 40-day window (no streak reset, B3 must only run), sentence 2 accepts one MOCK entry through the full boundary from any signal (R4 probe rule), M4's 10-day window with the 12-10 roll is dropped. Sentences 3–5 unchanged.
- [TOS platform roadmap (2026-11-11, adopted)](2026-11-11-tos-platform-roadmap.md): after `TOS_PAPER_READY` — P1 observation (`sts tos inspect`, per-rule pass/fail), P2 declarative indicator fields (`fields.yaml` + versioned catalog, second strategy YAML-only), P3 replay + CI golden decisions, P4 execution in MOCK/SYNTHETIC (position fields in capsule, stop/size as YAML), P5 performance. Principle: strategies are tenant YAML, never per-strategy code.
- [TOS P2 declarative fields (2026-11-11)](2026-11-11-tos-p2-declarative-fields.md): `fields.yaml` + catalog `tos-field-catalog/1` in `shared/indicators/fields/`; P2-a catalog/evaluator, P2-b byte-identical equivalence vs the legacy-driven producer on 20 days × 3 trees, P2-c producer switch after `TOS_PAPER_READY`, P2-d second strategy config-only. The early-return chain is reproduced first, untangled into DSL only after P3 goldens.
- [Phase-0 판정 장치 퇴역 (2026-11-12)](2026-11-12-phase0-retirement-plan.md): Phase 0 는 2026-10-22 서명(#920)으로 닫혔고 완료 기준은 `TOS_PAPER_READY` 다. P1 — 완료 계약서·인덱스 도구·완료/계약 검사기·U-17 예방 통제와 그 CI 단계를 지운다(`tos-gate` 체크 이름은 유지하고 내용만 `tos_redigest --check` 로 교체). P2(이력 합치기)는 운영자 실행.
- [TOS 효용성·활용성과 활용 방안 (2026-11-13)](2026-11-13-tos-utility-and-usage.md): 평가 문서(일정 변경 없음) — 안전 집행·관측 기반으로는 쓸 만하나 체결 확인 0건·전략 1개라 전략 플랫폼 증거는 아직 없다. 11-13 주식 MOCK 진입은 ACK 까지 갔으나 `FILL_OBSERVER_ACK_UNTRACKABLE`(no_trading_date)로 문장 2 미달. 쓰임 셋(선물 신호 관측기 · 12월 주식 전략 실험대 · 2027-Q1 성과 증명), 전략 추가 표준 절차, 매일 운영 루틴, 중단 기준 넷.
- [TOS 코드 절반 이하 (2026-11-13)](2026-11-13-tos-code-halving-plan.md): 운영자 지시 — S1 안 쓰는 커널 패키지·B3·시간 스냅샷 부피, S2 안 터진 판정 장치(안전망 wdr/sir/spg/protective/liveauth/hag/stm, verify 17→8, currentness 21→12) 합치기·제거, S3 tos-spec·tos-evidence·역사 문서 은퇴, S4 docstring 첫 줄·주석 제거. 지킬 것: 중복 주문 방지·#998·리스크 한도·GET 전용.
- Current implementation/check snapshot: [PROJECT_STATUS](../PROJECT_STATUS.md).
- The dated update paragraphs below are historical observations, not current entry-gate verdicts. Consult the current checkers and normative sources for authorization.

## Historical index updates

- **2026-11-14 — 역사 계획 은퇴** (`2026-11-13-tos-code-halving-plan.md` §S3/§4).
  끝난 착지 기록 35건(2026-07~09 커널·런타임, 상위 제안표, 측정 계획)과 끝난
  측정 캠페인 증거 5건을 지웠다. 런북은 **하나도 지우지 않았다** —
  `tos-paper-boot-history.md` 는 콜드 백업 런북의 거부 대응표가 그 §4-A
  `migrate` 절차로 운영자를 보내므로 이력이 아니라 현행 절차의 부록이다. 내용은
  git 이력에 있다: `git log --diff-filter=D -- docs/`.
- **2026-11-13 — 역사 문서 은퇴** (`2026-11-13-tos-code-halving-plan.md` §S3).
  2026-04 · 2026-07 · 2026-08 의 RFC 설계 코퍼스(약 48k 줄)와 끝난 Phase 1~5
  구현 기록, 레거시 런북·루트 문서를 지웠다. 남긴 것은 코드·CI·설정이 인용하는
  문서와 현재 런북뿐이다. 내용은 git 이력에 있다:
  `git log --diff-filter=D -- docs/`.
- **2026-11-12 — Phase-0 판정 장치 퇴역** (`2026-11-12-phase0-retirement-plan.md`).
  완료 계약 에라타·재심 기록과 그 설계 문서를 지웠다 — Phase 0 는 2026-10-22
  서명(#920)으로 닫혔고 완료 기준은 `TOS_PAPER_READY` 다.

현재 런타임 스냅샷은 [../PROJECT_STATUS.md](../PROJECT_STATUS.md), TOS 로드맵은
[2026-11-11-tos-platform-roadmap.md](2026-11-11-tos-platform-roadmap.md) 다.

## Active

| Plan | Status |
|---|---|
| [2026-07-20-tos-boundary-and-import-firewall-design.md](2026-07-20-tos-boundary-and-import-firewall-design.md) | **설계 문서 #1 — tos/ 경계 & import-firewall 계약 (v2, 비준 대상)** — IMPLEMENTATION-PLAN-002 §2 그린필드 경계의 프로젝트 측 확정 입력물. §1 관계 모델(격리 동거→콘텐츠 이주→역전; 운영↔tos 양방향 import 금지, dual-use는 커먼즈 승격), §2 경계 3분류, §3 import 정의(직접=default-deny/내부 금지=전이 포함) + 허용목록 v2 + 3층 강제(커스텀 AST 게이트·import-linter 전이 검출·required CI check) + §3.4 `shared/determinism` 추출 선행 작업, §4 SAFE-045 계층 방어(자격증명·라우트 부재 1차, 잔여 리스크 정직 기록), §5 독립 배포 단위+VER §2.3/§3/§9 정렬 run manifest 7항목, §6 개정 로그+repo 분리 트리거, §7 비준 체크리스트 8항목. v1은 독립 비평 리뷰 REJECT(CRITICAL 2 실증: backtest 허용 모듈의 `shared.execution`·MLflow 전이 import) → v2 전 findings 반영. **2026-07-20 운영자 비준(v2) — 효력 발생.** Phase 1(EV-L1 비전송) 코드/테스트 착수 승인. §6.3 선행 작업 2건 완료(2026-07-20): `shared/determinism` 신설(+`ContractSpec`→`shared/instruments`), 3층 게이트(`tools/tos_firewall_check.py`·`.importlinter`·CI `tos-firewall`)+최소 `tos/` 스켈레톤. **다음(설계 #2)도 2026-07-20 비준 완료.** |
| [2026-10-24-tos-stock-mock-activation-record.md](2026-10-24-tos-stock-mock-activation-record.md) | **운영자 승인 기록 (2026-10-24).** KIS 모의 주식 테넌트 활성화 — `tests/unit/scripts/test_render_stock_tenant_mock_boot.py` 가 이 승인을 인용한다. |


## Adding A Plan

1. Add new plans at `docs/plans/2026-MM-DD-<slug>.md`, at most 300 lines
   (CLAUDE.md R4 — 넘으면 범위를 쪼갠다).
2. Put the new plan in **Active** while work is underway or operator decisions
   remain open.
3. 끝났고 코드·설정·CI 가 그 경로를 인용하지 않게 된 기록은 **지운다** —
   git 이력이 보존한다. `archive/` 는 2026-11-13 에 없어졌다.
