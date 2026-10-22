# CP-3 band 첫 켜기 세션 — LONG tenant 2026-10-22 (실측)

- 계획: `docs/plans/2026-10-15-tos-cp3-band-via-producer-plan.md` §4 「켜기와 첫 세션 수용」.
- 절차·명령: `docs/runbooks/tos-paper-boot.md` §7.2-d (band 수용 명령 · §3.6 대조 · 실전 주문 TR 검사).
- 선행 증거: `docs/broker-profiles/evidence/2026-10-08-cp3-venue-limits/README.md` (P-VL — band 가
  미니 틱 0.02 격자에만 떨어진다) · `docs/broker-profiles/evidence/2026-10-12-cp3-pr1-minute-probe/README.md`.
- 세션: `CP3-BAND-FS.json:session.date=2026-10-22` · 트리
  `CP3-BAND-FS.json:session.tenant_tree=cp3-setup-d-long` · 월물
  `CP3-BAND-FS.json:session.instrument=A05611` · 라벨
  `CP3-BAND-FS.json:session.environment_label=paper` · 코드
  `CP3-BAND-FS.json:session.repo_commit=b15069fd1737962d92766e73648b0c2128957d32`
  (런타임 `CP3-BAND-FS.json:session.runtime_code_digest=b06d01f9cee56d11eb9e310b82e32244695bd62e8211a9a3491a23fcd4cca1b6`).
- **주문 0 건** (`CP3-BAND-FS.json:real_order_tr_check.real_orders=0`). 실전 호출은 **조회 GET 뿐**이다.
- 방법: 세션 아티팩트에 대한 **오프라인 재계산**
  (`CP3-BAND-FS.json:generated_from.method=offline recomputation over the session's own artifacts; stores opened read-only (mode=ro)`).
  이 디렉터리에는 계좌 식별자·토큰·원본 저널을 싣지 않는다 — 파생 수치만 싣는다.

## 0. 답 — 한 문장

band **원천 쪽은 전부 정상**이고(줄 하나, 개장 뒤, 부팅 전에 보였고, 정책에 묶였다), **런타임이 그
줄을 읽는 자리에 한 번도 도달하지 않았다** — 그날 25 건의 제안이 전부 `CANDIDATE_COMMAND_CONSTRUCTION`
에서 거부돼 venue 스냅샷이 한 번도 발행되지 않았기 때문이다. 그래서 §4 수용 1·2·3 은 **실패가 아니라
«미집행»(NOT EXERCISED)** 으로 기록한다. band 결함의 증거는 하나도 없고, band 가 쓰였다는 증거도 없다.

## 1. 수용 표 (단일 표)

| 기준 | 명령 | 결과 수 | 판정 | 로그 경로 |
|---|---|---|---|---|
| **수용 1a** — `band.jsonl` 첫 줄이 **개장 뒤** | `cat $SESSION/producer/band.jsonl` | 줄 `CP3-BAND-FS.json:acceptance_1_band_line.band_jsonl_lines=1` · `as_of_ms` `CP3-BAND-FS.json:acceptance_1_band_line.band_as_of_ms=1792626370996` ≥ 개장 `CP3-BAND-FS.json:acceptance_1_band_line.session_open_ms=1792626300000` (`CP3-BAND-FS.json:acceptance_1_band_line.line_is_after_open=true`) | **PASS** | `$SESSION/producer/band.jsonl` |
| **수용 1b** — 러너가 **부팅 전에** 그 줄을 봤다 | `grep -c 'BAND ABSENT' $SESSION/session.log` | `CP3-BAND-FS.json:acceptance_1_band_line.band_absent_log_lines=0` · `CP3-BAND-FS.json:acceptance_1_band_line.line_seen_before_boot=true` (band line ok 08:46:15 → BOOT `CP3-BAND-FS.json:session.boot_kst=2026-10-22 08:46:18`) | **PASS** | `$SESSION/session.log` · `$SESSION/producer/band-line-wait.log` |
| **수용 1c** — 런타임 `VENUE_BAND_OBSERVED` 의 `raw_payload_digest` 가 그 줄과 같다 | 런북 §7.2-d 「digest 가 그 줄의 것과 같은가」 | `VENUE_BAND_OBSERVED` 행 `CP3-BAND-FS.json:acceptance_1_band_line.venue_band_observed_rows_store_total=0` (OBSERVED 도 REFUSED 도 0) | **NOT EXERCISED** (§2) | `$LEAF/evidence.sqlite3` |
| **수용 2** — 그날 소비된 모든 가격이 band 안 | 런북 §7.2-d 의 `consumed-ids × fields.jsonl × band 행` 조인 | `CP3-BAND-FS.json:acceptance_2_prices_inside_band.runbook_join_result=SKIPPED (no band)` | **NOT EXERCISED** (§2) | `$LEAF/evidence.sqlite3` |
| **수용 2 (파생)** — 같은 조인을 **band 행 대신 `band.jsonl` 줄**로 | 같은 조인, `price_min`/`price_max` 를 줄의 `lower`·`upper` ×100 으로 | joined `CP3-BAND-FS.json:acceptance_2_prices_inside_band.joined=409` of `CP3-BAND-FS.json:acceptance_2_prices_inside_band.consumed_ids_this_session=409` · outside `CP3-BAND-FS.json:acceptance_2_prices_inside_band.outside=0` (종가 `CP3-BAND-FS.json:acceptance_2_prices_inside_band.consumed_close_x100_min=85124`~`CP3-BAND-FS.json:acceptance_2_prices_inside_band.consumed_close_x100_max=89374`, band `CP3-BAND-FS.json:acceptance_2_prices_inside_band.derived_band_lower_x100=82022`~`CP3-BAND-FS.json:acceptance_2_prices_inside_band.derived_band_upper_x100=96286`) | **파생 OK** (수용 아님) | `$SESSION/producer/band.jsonl` |
| **수용 3** — `VENUE_SNAPSHOT_ISSUED` 에 `band_digest`, `absent_fields` 에서 세 필드가 빠짐 | 런북 §7.2-d 의 `VENUE_SNAPSHOT_ISSUED` 질의 | 이 세션의 행 `CP3-BAND-FS.json:acceptance_3_snapshot_carries_band.venue_snapshot_issued_rows_this_session=0` (스토어 전체 `CP3-BAND-FS.json:acceptance_3_snapshot_carries_band.venue_snapshot_issued_rows_store_total=1`, 그 한 행은 `CP3-BAND-FS.json:acceptance_3_snapshot_carries_band.store_row_belongs_to_boot=2026-10-15` 부팅의 것이고 `band_digest` 는 `CP3-BAND-FS.json:acceptance_3_snapshot_carries_band.store_row_band_digest=null`) | **NOT EXERCISED** (§2) | `$LEAF/evidence.sqlite3` |
| **M5 ①** — 「값을 쥐고도 UNKNOWN 으로 거절된 **부팅 후** 소비 id」 = 0 | `session_inputs.py consumed-ids` | 이 세션 `CP3-BAND-FS.json:m5.this_session_value=1` (`CP3-BAND-FS.json:m5.this_session_raw_event_ids[0]=A05611:1m:20261022T151200+0900`) · 스토어 전체 수는 `CP3-BAND-FS.json:m5.store_wide_value=2` (§4) | **FAIL (1 봉)** | `$SESSION/producer/boot-journal-snapshot.json` |
| **M5 ②** — 「소비되지 않은 줄」 = 0 | 같은 명령 | `CP3-BAND-FS.json:m5.published_not_consumed=0` (짝 없는 12 봉은 전부 생산자 사유: `no_raw_row_for_minute` `CP3-BAND-FS.json:m5.unpaired_reason_counts.no_raw_row_for_minute=10` · `late_completed` `CP3-BAND-FS.json:m5.unpaired_reason_counts.late_completed=1` · `published_after_session_close` `CP3-BAND-FS.json:m5.unpaired_reason_counts.published_after_session_close=1`) | **PASS** | `$SESSION/producer/producer-log.jsonl` |
| **M6** — `max_stamp_to_replace_s` < 0.300 | `producer-summary.json` | `CP3-BAND-FS.json:m6.max_stamp_to_replace_s=0.003937260014936328` | **PASS** | `$SESSION/producer/producer-summary.json` |
| **B3** — `unresolved.count` = 0 | `diff_decisions.py` (B1a·B2·B1b 이어서) | `CP3-BAND-FS.json:b3.unresolved_count=0` · 비교 `CP3-BAND-FS.json:b3.compared_bars=409` 봉 | **PASS** | `$SESSION/producer/market/stitch.json` · `$SESSION/config/` |
| **B3 live 대조** (보고, 거부 아님) | 같은 명령의 `live_comparison` | identical `CP3-BAND-FS.json:b3.identical=382` · divergent `CP3-BAND-FS.json:b3.divergent=27` · kind_only `CP3-BAND-FS.json:b3.kind_only_matches=0` (§3) | **보고** | 같음 |
| **실전 주문 TR** — 조회 TR 부분집합 · GET 뿐 · 실주문 0 | 런북 §7.2-d 의 두 로그 TR 분포 | 파일 `CP3-BAND-FS.json:real_order_tr_check.log_files=2` · 행 `CP3-BAND-FS.json:real_order_tr_check.rows=977` · TR `CP3-BAND-FS.json:real_order_tr_check.tr_ids[0]=FHKIF03020200`·`CP3-BAND-FS.json:real_order_tr_check.tr_ids[1]=FHMIF10000000` · method `CP3-BAND-FS.json:real_order_tr_check.methods[0]=GET` | **PASS** | `$SESSION/producer/producer-log.jsonl` · `$SESSION/producer/band-log.jsonl` |
| **기준가 대 전일 종가** (계획 §4.4a 잔여 위험의 **측정**) | 줄의 `basis` ×100 대 동결 프레임의 전일 종가 | `CP3-BAND-FS.json:basis_vs_previous_close.band_basis_x100=89154` vs `CP3-BAND-FS.json:basis_vs_previous_close.previous_session_close_x100=89154` → 차 `CP3-BAND-FS.json:basis_vs_previous_close.difference_x100=0` · `symmetric_about_basis` `CP3-BAND-FS.json:basis_vs_previous_close.symmetric_about_basis=true` | **측정 (뒤집힘 없음)** | `$SESSION/producer/market/` (동결 프레임) |

`$SESSION` = `CP3-BAND-FS.json:session.session_dir=~/.local/state/tos/cp3-sessions/long-20261022` ·
`$LEAF` = `CP3-BAND-FS.json:session.durable_leaf=~/.local/state/tos/cp3-setup-d-long-data/A05611`.

## 2. 왜 「미집행」인가 — 런타임이 band 를 읽는 자리에 도달하지 않았다

band 읽기는 **지연**이다: `tos/runtime/src/tos_runtime/venue/service.py` 의
`VenueConstraintService.snapshot()` 이 **첫 스냅샷**에서 `_read_band("boot")` 를 부르고,
`snapshot()` 은 venue 스테이지와 non-trade 수용 공급자 **둘에서만** 불린다 — 둘 다 후보 명령
구성(`CANDIDATE_COMMAND_CONSTRUCTION`)의 **하류**다
(`CP3-BAND-FS.json:why_not_exercised.band_read_site=tos/runtime/src/tos_runtime/venue/service.py — VenueConstraintService.snapshot() calls _read_band('boot') on the FIRST snapshot; snapshot() is reached only from the venue stage and the non-trade admissibility provider, both downstream of candidate command construction`).

그날의 수는 이렇다.

- 제안 `CP3-BAND-FS.json:why_not_exercised.proposals_this_session=25` 건 전부가
  `FLOW_HALTED` `STAGE_DENIED` — `CP3-BAND-FS.json:why_not_exercised.flow_halted_all_stage_denied_at_candidate_command_construction=25`,
  사유는 `quantity_basis` `CP3-BAND-FS.json:why_not_exercised.flow_halted_quantity_basis=ZERO_POSITION`
  이 봉투의 허용 집합 밖이라는 것.
- 통과 `CP3-BAND-FS.json:why_not_exercised.flow_step_admitted_this_session=0` ·
  수용 결정 `CP3-BAND-FS.json:why_not_exercised.order_admissibility_decisions_this_session=0`.
- **대조군 — 2026-10-15 genesis 세션**(같은 스토어 · 전략 버전 동일
  `CP3-BAND-FS.json:why_not_exercised.same_strategy_version_both_sessions=true` · 주문구성정책
  digest 동일 `CP3-BAND-FS.json:why_not_exercised.same_order_construction_policy_digest=true`): 제안
  `CP3-BAND-FS.json:why_not_exercised.genesis_20261015_proposals=25` 중
  `CP3-BAND-FS.json:why_not_exercised.genesis_20261015_flow_step_admitted=6` 이 구성을 통과해
  스냅샷 `CP3-BAND-FS.json:why_not_exercised.genesis_20261015_venue_snapshot_issued=1` 건과
  수용 결정 `CP3-BAND-FS.json:why_not_exercised.genesis_20261015_order_admissibility_decisions=6`
  건을 남겼다. 즉 이 경로는 막힌 것이 아니라 **그날 열리지 않았다**.

해석(측정 아님): 그날 Setup D 의 진입 발화는 **숏**이었고(B3 `LEGACY_ONLY_ENTRY`
`CP3-BAND-FS.json:b3.buckets.LEGACY_ONLY_ENTRY=3`, 귀속
`CP3-BAND-FS.json:why_not_exercised.b3_legacy_only_entries_attribution=legacy_short_entry`), LONG
tenant 는 그것을 취할 수 없으므로 실시간 제안 25 건은 **전부 청산(FLAT)** 이었다. 청산의
`quantity_basis` 가 `ZERO_POSITION` 이고, 그 토큰은 이 봉투의 허용 집합에 없다.

- band 쪽은 묶였다: 부팅 시 `VENUE_POLICY_BOUND` 가 `band_source_digest`
  `CP3-BAND-FS.json:acceptance_1_band_line.band_source_digest=ad65b40bdf5b74fdb5955e0492193357a12b6f52aff5aadd0cbd2632c312ccd6`
  를 실었다(`CP3-BAND-FS.json:acceptance_1_band_line.band_source_bound_at_boot=true`).
- 줄 자체도 읽혔다면 통과했을 모양이다: 두 값 모두 `tick_size`
  `CP3-BAND-FS.json:basis_vs_previous_close.tick_size=2` 격자 위에 있다
  (`CP3-BAND-FS.json:basis_vs_previous_close.lower_on_tick_grid=true` ·
  `CP3-BAND-FS.json:basis_vs_previous_close.upper_on_tick_grid=true`) — P-VL 이 미니 틱 0.02 로
  실측한 것과 같은 격자다. **읽혔다는 뜻은 아니다.**

⛔ 그래서 이 세션은 band 의 **런타임 측 증명이 아니다**. 계획 §4 가 요구한 세 가지는 다음 세션
중 후보 하나가 후보 명령 구성을 통과하는 날에 처음 집행된다.

## 3. B3 — 통과, 그리고 소견 하나

`unresolved` `CP3-BAND-FS.json:b3.unresolved_count=0`. 버킷은
`AGREE_NO_ACTION` `CP3-BAND-FS.json:b3.buckets.AGREE_NO_ACTION=381` ·
`TOS_EXIT_ON_LEGACY_AFTER_CUTOFF` `CP3-BAND-FS.json:b3.buckets.TOS_EXIT_ON_LEGACY_AFTER_CUTOFF=19` ·
`TOS_EXIT_ON_LEGACY_NOT_EXTREME` `CP3-BAND-FS.json:b3.buckets.TOS_EXIT_ON_LEGACY_NOT_EXTREME=4` ·
`TOS_EXIT_ON_LEGACY_BEFORE_WINDOW` `CP3-BAND-FS.json:b3.buckets.TOS_EXIT_ON_LEGACY_BEFORE_WINDOW=1` ·
`TOS_EXIT_ON_LEGACY_VOL_BELOW_GATE` `CP3-BAND-FS.json:b3.buckets.TOS_EXIT_ON_LEGACY_VOL_BELOW_GATE=1` ·
`LEGACY_ONLY_ENTRY` 3.

`live_comparison.divergent` `CP3-BAND-FS.json:b3.divergent=27` 은 **두 모양뿐**이다.

- `CP3-BAND-FS.json:b3.divergence_shape_flat_vs_proposal=25` 봉 — 오프라인은 `FLAT`·
  `capacity_denied=true`, 실시간은 `PROPOSAL`·`capacity_denied=false`. 같은 25 봉이 위 §2 의
  `ZERO_POSITION` 거부들이다.
- `CP3-BAND-FS.json:b3.divergence_shape_no_action_vs_no_outcome=2` 봉 — 오프라인 `NO_ACTION`,
  실시간 `NO_OUTCOME`. 둘 다 `DECISION_WITHHELD`
  `CP3-BAND-FS.json:m5.live_withhold_reason_for_the_two_no_outcome_bars=TIME_NOT_ADMITTED` 이고,
  하나는 부팅 전 줄(`CP3-BAND-FS.json:m5.this_session_pre_boot_raw_event_ids[0]=A05611:1m:20261022T084500+0900`),
  다른 하나가 **M5 ① 이 센 그 봉**(15:12)이다.

귀속은 `ticks_without_a_decision` `CP3-BAND-FS.json:b3.ticks_without_a_decision=0` ·
캡슐 키 `CP3-BAND-FS.json:b3.attributed_by_capsule_id=709` · 증거 구간
`CP3-BAND-FS.json:b3.attributed_by_evidence_seq_range=3`.

## 4. 런북이 답하지 못한 것 둘 — **지정 durable set 은 세션을 누적한다**

§7.2-d 의 §3.6 명령들은 `$SESSION/data/$INSTRUMENT`(세션마다 새 data dir)를 전제로 쓰였다. 실제
tenant 세션은 **지정 durable 잎**을 쓰고, 그 잎은 지워지지 않는다. 그래서:

1. **「부팅 행이 2 건」은 하루에 두 번 부팅한 것이 아니다.** `TIME_SERVICE_STARTUP`
   `CP3-BAND-FS.json:store_accumulation.time_service_startup_rows_total=2` 의 벽시계는
   `CP3-BAND-FS.json:store_accumulation.boot_wall_clock_kst[0]=2026-10-15T10:02:52.127000+09:00`
   와 `CP3-BAND-FS.json:store_accumulation.boot_wall_clock_kst[1]=2026-10-22T08:46:20.445000+09:00`
   — **genesis 세션과 이 세션**이다. 같은 이유로 세션 로그 끝의 kind 분포
   (`EVENT_CONSUMED` `CP3-BAND-FS.json:store_accumulation.event_consumed_store_total=712`)는
   스토어 전체이고 이 세션 몫은
   `CP3-BAND-FS.json:store_accumulation.event_consumed_this_session=409` 다.
2. **그대로는 B3 가 돌지 않는다.** `diff_decisions.py` 는 스토어 전체 입력을 **거부한다**(exit 2:
   「The runtime consumed bars this offline trio does not cover」) — 동결 프레임은 2026-10-16~22
   만 덮는데 소비 id 에는 10-15 세션의 `CP3-BAND-FS.json:b3.scoping_dropped_ids=303` 건이 섞여
   있기 때문이다. 이 측정은 `consumed-ids.json` 과 `live.jsonl` 을 **그날 `raw_event_id` 로 걸러**
   돌렸다(`CP3-BAND-FS.json:b3.session_day=20261022`). 같은 이유로 M5 의 추출기 수도 스토어 전체
   (`CP3-BAND-FS.json:m5.store_wide_value=2`)이므로 그날 수
   (`CP3-BAND-FS.json:m5.this_session_value=1`)와 나눠 적는다 — 스토어 전체 수의 나머지 한 건은
   10-15 세션의 **부팅 전** 줄이고, 추출기는 **오늘의** boot snapshot 만 알기 때문에 그것을
   부팅 후로 센다. 런북 §7.2-d 에 이 두 가지를 반영하는 것은 별도 변경이다.

## 5. 생산자 — 하루를 온전히 돌았다

발행 `CP3-BAND-FS.json:producer.published=410` · 동결 봉
`CP3-BAND-FS.json:producer.frozen_bars_today=411` · `fetch_error`
`CP3-BAND-FS.json:producer.fetch_error=0` · `produce_error`
`CP3-BAND-FS.json:producer.produce_error=0` · 부팅 시 STALE 줄
`CP3-BAND-FS.json:producer.consumed_stale_at_boot=1`. 러너가 읽는 종료코드는
`CP3-BAND-FS.json:session.producer_rc=0` · `CP3-BAND-FS.json:session.run_rc=0`.

런북 §7.2-d 의 「살아 있지만 멈춘 생산자 / 낡은 피드」 손 확인: 저널 마지막 줄은
`CP3-BAND-FS.json:session.last_journal_raw_event_id=A05611:1m:20261022T154500+0900` 이고 발행
시각은 `CP3-BAND-FS.json:session.last_journal_published_kst=2026-10-22T15:46:02.434000+09:00`
— 마감(15:45) 직후다. 멈춘 생산자도 낡은 피드도 아니다.

## 6. 기준가 — 브로커가 준 `futs_sdpr` 는 **그 전 세션의 종가 그 자체**였다

계획 §4.4a 의 잔여 위험은 「브로커가 전일 band 를 내줄 수 있다」였다. 이제 REAL 원천이므로 동결
프레임과 대조할 수 있다.

- 줄의 `basis` ×100 = `CP3-BAND-FS.json:basis_vs_previous_close.band_basis_x100=89154`.
- 동결 프레임의 전 세션
  (`CP3-BAND-FS.json:basis_vs_previous_close.previous_session_day=2026-10-21`) 마지막 봉
  `CP3-BAND-FS.json:basis_vs_previous_close.previous_session_last_bar=A05611:1m:20261021T154500+0900`
  종가 `CP3-BAND-FS.json:basis_vs_previous_close.previous_session_close_x100=89154`.
- 차 `CP3-BAND-FS.json:basis_vs_previous_close.difference_x100=0`.

대칭은 `CP3-BAND-FS.json:basis_vs_previous_close.symmetric_about_basis=true`
(위폭 `CP3-BAND-FS.json:basis_vs_previous_close.upper_minus_basis_x100=7132` = 아래폭
`CP3-BAND-FS.json:basis_vs_previous_close.basis_minus_lower_x100=7132`, 기준가의
`CP3-BAND-FS.json:basis_vs_previous_close.half_width_over_basis_pct=7.9996` %).

⚠ `symmetric_about_basis` 는 1 단계의 **필요조건**이지 1 단계 판별이 아니다(2·3 단계도 기준가
대칭이다). 그리고 이 대조는 **그날 하루치**다 — 뒤집힘이 없었다는 것이지 「브로커가 늘 당일
기준가를 준다」가 아니다.

## 7. 남은 것

- 수용 1·2·3 은 **후보 하나가 후보 명령 구성을 통과하는 첫 세션**에 처음 집행된다. 그때까지
  band 는 묶여 있으나 읽히지 않는다. 지금 상태의 보수성은 유지된다(런타임에서 band 가 없으면
  `UNKNOWN` → 송신 0).
- M5 ① 의 1 봉(15:12, `TIME_NOT_ADMITTED`)은 그 자체로 소견이다. 상한 계수이므로
  「stale 이거나 평가 시각을 세울 수 없었거나」 둘 중 하나이고, 가르는 계수는 아직 없다.
- 런북 §7.2-d 의 §3.6 절차는 **누적 durable 잎**을 전제로 다시 써야 한다(§4).
