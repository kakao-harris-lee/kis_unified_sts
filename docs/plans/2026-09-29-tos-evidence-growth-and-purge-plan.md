# 증거 증가 대응 — 퍼지 전 단계와 퍼지의 전제 (계획)

- 작성: 2026-09-29 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `341a4430`
- 요청: 운영자 2026-09-29 「증거 퍼지 계획 써줘」(#806 계획 §6.1-3 「증거 퍼지는 별도 계획」).
- 성격: **결정 메모 + 단계 계획.** 되돌리기 어려운 경로(데이터 파기)이므로 운영자 처분 전에는 코드 0.
  Codex 계획 심사는 운영자 요청이 있을 때만 한다(CLAUDE.md 2026-09-11 — 데이터 파기 경로는 심사 대상이 될 수 있다).

## 0. 요약 — 조사가 질문을 바꿨다

1. **파괴적 퍼지는 지금 할 수 없다. 규범 두 개가 막는다.**
   - 비준된 설계 #40 D3.1(`docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-decisions.md:92`):
     「**삭제 잡은 Phase 2 범위 밖**(툼스톤 스키마만)」 · 컴팩션도 「구현하지 않는다(항목 삭제 0)」(`:66`).
   - ADR-002-016 §17(`tos-spec/.../ADR-002-016-...md:443`): 「Destructive deletion requires approved policy,
     **effective-human dual control**, scope proof, expired holds, integrity-preserving tombstone, and evidence that
     economic lifetime and acceptance obligations ended.」 운영자 1인 체제에서 이중 통제는 현재 충족 수단이 없다.
2. **디스크는 급하지 않다.**
   - 장중 실측(2026-09-28, poll 400 · 5 s 관측) 기준 data dir 은 약 **200 MB/일**이다.
   - 호스트 여유 344 GB → 약 **4.7 년**치다.
3. **실제로 커지는 위험은 부팅·복구 시간이다.**
   - 증거 테이블에는 **인덱스가 하나도 없다**(`seq` PK 뿐).
   - 런타임 **21 개 모듈**이 `SELECT … FROM entries WHERE kind = ?` 로 이력을 읽는다. 부팅 리플레이·복구·포지션
     재구성·안전 재무장이 포함된다. 이 질의는 전부 **전체 스캔**이다 → 이력에 비례해 느려진다.
   - 그 스캔 대상의 **75 %** 가 `TIME_HEALTH_SNAPSHOT` 이고, 런타임에서 **그것을 읽는 코드는 0** 이다(쓰기만 한다).
4. **그래서 이 계획은 두 트랙이다.**
   - **트랙 A (지금 · 무손실)**: 측정 → `kind` 인덱스 → 압축 콜드 백업. 아무것도 지우지 않는다.
   - **트랙 B (나중 · 파괴적)**: 진짜 퍼지. 전제 다섯 개(§4)가 채워질 때까지 착수하지 않는다.

## 1. 실측 (2026-09-28 11:00 KST 실 `run` 15 분 · main `ac2efb0f` 상당 · poll 400)

| 파일 | 크기 / 15 분 | 장중 7 h 환산 | xz -6 압축비 |
|---|---|---|---|
| `evidence.sqlite3` | 5.33 MB | ≈ 150 MB/일 | **14 ×** |
| `inbox.sqlite3` | 0.89 MB | ≈ 25 MB/일 | 21 × |
| `marketfeed.sqlite3` | 0.84 MB | ≈ 24 MB/일 | 39 × |
| 합계 | ≈ 7.1 MB | **≈ 200 MB/일** | 압축 뒤 ≈ 13 MB/일 |

증거 종류별(같은 실행 · payload + 식별자 + digest 바이트):

| kind | 행 | 바이트 | 비중 |
|---|---|---|---|
| `TIME_HEALTH_SNAPSHOT` | 2180 | 3.99 MB | **75 %** |
| `DECISION_OUTCOME_EMITTED` | 179 | 0.31 MB | 6 % |
| `FLOW_HALTED` | 89 | 0.13 MB | 2 % |
| `EVENT_CONSUMED` | 180 | 0.11 MB | 2 % |
| 그 밖 | — | 나머지 | — |

코드 사실(main `341a4430`):

| 무엇 | 위치 |
|---|---|
| `entries` 스키마 — 인덱스 없음 · `segment_id` 열은 있으나 경계 정책 미구현 | `tos/runtime/src/tos_runtime/evidence/store.py:165-177 · :564-567` |
| `UPDATE`/`DELETE` 트리거 거부(D3.1 「표현 불가능화」) | `store.py:180-195` |
| 체인 검증은 `entry_digest`·`key_generation`·`chain_digest` 만 읽는다(payload 불필요) | `store.py:736-757` |
| 전체 체인 재검증은 **복원 때만**(부팅 때는 하지 않는다) | `evidence/backup.py:179` · `operations/backup_set.py:578` |
| 보존 판정: 커널 `retention_deletable`(5 입력 순수 술어) + 런타임 `RetentionPolicy`(판정만 · 삭제 잡 없음) · 나이는 **프로세스 단조시계**라 재시작을 넘지 못한다 | `tos/src/tos/evidence/retention.py` · `tos/runtime/src/tos_runtime/evidence/retention.py:1-30` |
| 보존 값은 named-TBD(`evidence_retention.example.yaml` 만, paper 설정 없음) | `tos/runtime/config/evidence_retention.example.yaml` |
| `entries` 를 읽는 모듈 21 개 | `git grep -l "FROM entries" -- tos/runtime/src`(§2 T-A1 이 목록을 표로 만든다) |
| `TIME_HEALTH_SNAPSHOT` 을 읽는 런타임 코드 | **없음**(`time/service.py:75-76` 의 쓰기 상수뿐) |

## 2. 트랙 A — 무손실 (착수 제안)

### A1. 측정 (코드 변경 0)

- **합성 이력으로 부팅·복구 시간을 잰다.** 오늘의 행 분포를 복제해 30 · 90 · 365 일치 `evidence.sqlite3` 를 만든다.
  각각에서 `compose_paper_runtime` 부팅(리플레이 포함), `recovery` 입력 조립, `safety.rearm` 경로의 벽시계 시간을 잰다.
- **읽기 목록 표**: 21 개 모듈 × 읽는 `kind` × 부팅 경로 여부 × 질의 형태(전 이력 / 꼬리 / 존재 여부).
- **종료 조건**: 「며칠치 이력에서 부팅이 N 초를 넘는가」의 곡선. A2 의 필요성과 효과를 이 숫자로 판단한다.

### A2. `kind` 인덱스 (A1 이 필요를 보이면)

- `CREATE INDEX entries_kind_seq ON entries(kind, seq)` — 21 개 질의의 형태(`WHERE kind = ? [AND seq > ?] ORDER BY seq`)에 맞는다.
- **이것은 DB 마이그레이션이다**(CLAUDE.md 의 되돌리기 어려운 경로). `schema_ledger` 로 버전을 올리고,
  기존 DB 에는 부팅 시 멱등 생성 · 행·체인·digest 는 **바이트 불변**(인덱스는 저장 표현이 아니라 보조 구조).
- 기대 효과: 부팅 질의가 `TIME_HEALTH_SNAPSHOT` 75 % 를 건너뛴다 → 이력에 비례하던 비용이 해당 kind 행 수에 비례.
- 대가: 쓰기마다 인덱스 갱신 · 파일 크기 소폭 증가(A1 에서 함께 잰다).

### A3. 압축 콜드 백업 (기존 `backup()` 재사용)

- 이미 있는 세대 스탬프 백업(`evidence/backup.py` — `sqlite3.backup()` + 매니페스트 + 복원 시 독립 재검증)을
  **장 마감 뒤** 돌리고, 결과를 xz 로 압축해 저장소 밖 보관 디렉터리에 둔다(경로는 설정).
- 매 백업마다: 압축 해제 → digest 일치 → `verify_or_raise` 까지 확인하고 그 결과를 증거로 남긴다.
- **라이브 파일은 건드리지 않는다.** 디스크는 줄지 않는다. 트랙 B 가 언젠가 지울 때 쓸 **검증된 원본 사본**을
  미리 쌓아 두는 것이다(ADR §17 「independently verified snapshot … raw material」의 준비).

### 트랙 A 에서 하지 않는 것

- **라이브 파일 분할(세그먼트 회전)**: 21 개 읽기 모듈이 전 이력을 가정한다. 세그먼트 인식 읽기로 바꾸는 것은
  사실상 컴팩션 설계이고, D3.1 의 「컴팩션 구현하지 않음」 을 건드린다 → 트랙 B 쪽 결정.
- **payload 떼어내기**(`TIME_HEALTH_SNAPSHOT` 의 payload 를 보관소로 옮기고 digest 뼈대만 남기기): 체인 검증은
  유지되지만 `UPDATE` 트리거(D3.1)와 정면으로 부딪힌다 → 트랙 B 후보.

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| `TIME_HEALTH_SNAPSHOT` 을 상태 전이 때만 기록 | 「영수증 없으면 일어나지 않았다」 계약(`time/service.py:658`) — #806 계획 §3 에서 이미 기각 |
| 오래된 행 `DELETE` | 트리거가 막는다(설계상 표현 불가능) · D3.1 · ADR §17 전제 미충족 |
| 트리거를 잠시 끄고 지우기 | 「권한 있는 내부자 변조」를 스스로 수행하는 것 — ADR-002-016 의 탐지 대상 그 자체 |
| 폴링을 다시 늦춰 쓰기량 감소 | #807 결함 재발(STALE 37–42 %) |
| 증거를 다른 저장소(ClickHouse 등)로 이관 | CLAUDE.md — ClickHouse 신규 사용 금지 · D3.1 은 stdlib sqlite 로 닫혀 있다 |

## 4. 트랙 B — 파괴적 퍼지의 전제 (지금은 착수하지 않는다)

전부 채워져야 한다. 하나라도 비면 트랙 B 는 열리지 않는다.

| # | 전제 | 근거 | 현재 |
|---|---|---|---|
| B-1 | **D3.1 개정 비준** — 삭제 잡(또는 컴팩션)을 범위 안으로 | 설계 #40 D3.1 `:66 · :92` | 범위 밖 |
| B-2 | **Evidence Integrity Policy 보존 값** — 레코드 클래스별 `minimum_days_by_class`. ADR §17 의 여섯 지평(정정·늦은 체결 · 멱등·리플레이 · 경제 효과 · 검토 · 사고·규제·법적 보류 · 검증 수명) 중 가장 긴 것 | ADR-002-016 §17 `:432-439` | named-TBD |
| B-3 | **이중 통제의 충족 수단** — 두 번째 사람, 또는 운영자 1인 체제를 ⚠ 편차로 등재하는 결정 | ADR §17 `:443` · `Tombstone.dual_control_ref` 필수 | 없음 |
| B-4 | **벽시계 나이** — 보존 나이가 재시작을 넘어야 한다(지금은 단조시계) · 신뢰 시각(Trustworthy Time)으로 | `evidence/retention.py:19-26` | 미배선 |
| B-5 | **열림/live 판정의 레코드별 도출** — 열린 주문·UNKNOWN·미해제 용량·사고 등이 없음을 증명(`RetentionSubject` → `open_or_live=False`) | ADR §17 `:441` · 커널 `tombstone_admissible` | 미배선 |

B 가 열리면 첫 후보는 **`TIME_HEALTH_SNAPSHOT` 의 payload 떼어내기**다.
- 이유: 런타임 읽기 0 이고, 체인 검증은 digest 만 쓰며, A3 의 검증된 원본이 보관소에 있다.
- 행 삭제가 아니라 표현 교체(ADR §17 「compaction may replace storage representation only when …」)이므로 가장
  좁은 파괴다.
- 그래도 `UPDATE` 트리거 개정이 필요하다 → B-1 안에서 결정한다.

## 5. 위험

- **A2 는 DB 마이그레이션이다.** 실패 시 부팅 거부 → 롤백 절차(인덱스 `DROP` 은 데이터 불변)를 A2 PR 에 포함한다.
- **A3 는 디스크를 오히려 쓴다**(압축본 ≈ 13 MB/일). 여유 대비 무시할 수준이지만 보관 경로의 용량 경보를 둔다.
- 측정(A1)의 합성 이력은 오늘 하루의 분포를 복제한 것이다. 실제 운영 분포(주문이 실제로 나가는 단계)와 다를 수
  있다 — 결과를 「paper 합성 경로 기준」으로 명시한다.
- inbox·marketfeed(합계 25 %)는 증거가 아니라 규범이 다르다. 이 계획은 증거만 다루고, 둘은 A1 측정에만 포함한다.

## 6. 운영자 확인

1. **트랙 A 착수**(A1 측정 → 결과를 보고 A2·A3 결정) — 동의 여부.
2. **트랙 B** 는 전제 B-1…B-5 가 채워질 때까지 보류 — 동의 여부. 특히 **B-3 이중 통제**를 어떻게 풀지(두 번째 사람 / 편차 등재) 방향.
3. 이 계획에 **Codex 계획 심사**(`codex-gate`)를 붙일지 — 데이터 파기 경로라 대상이 될 수 있다. 요청할 때만.

### 6.1 운영자 처분 (2026-09-29)

1. **트랙 A = A1 · A2 · A3 모두 착수.**
   - A1 측정 결과는 A2 의 효과 확인(전·후 비교)으로도 쓴다.
   - A2 는 **기존 `migrate` 경로**(`compose/cli.py` 의 `migrate` 하위 명령 · `operations/schema_ledger` ·
     `EVIDENCE_SCHEMA_VERSION` 1 → 2)로 간다. 새 마이그레이션 수단을 만들지 않는다.
   - A3 는 **기존 `backup` 경로**(`operations/backup_set.py` — 다섯 파일 durable set)에 압축·압축 해제 검증을 얹는다.
2. **트랙 B 는 보류**하되, **B-3 이중 통제 방향 = 운영자 1인 체제를 ⚠ 편차로 등재**한다. 트랙 B 가 열릴 때
   그 편차 문서를 함께 비준한다. B-1 · B-2 · B-4 · B-5 는 그대로 전제로 남는다.
3. Codex 계획 심사는 요청하지 않았다. **A2 는 DB 마이그레이션**(되돌리기 어려운 경로)이다. 따라서 구현 PR 의
   Codex 코드 심사는 운영자가 범위·비용을 승인할 때만 붙인다.

## 7. 착지 기록

PR 마다 번호·main SHA·실측 전후를 덧붙인다. 원 계획 문언은 지우지 않는다.

### 7.1 트랙 A 착지 — PR #816 (2026-09-30, 분기점 main `341a4430`)

운영자 처분 §6.1 대로 A1·A2·A3 을 한 PR 에 담았다. **트랙 B(파괴적 삭제)는 손대지 않았고,
증거 행을 지우거나 고치거나 다시 쓰는 코드는 이 PR 에 한 줄도 없다.** append-only 트리거는
그대로다.

| 커밋 | 내용 |
|---|---|
| `4e0717ab` | A1 벤치 도구 + 헤르메틱 테스트 |
| `c29ed889` | A2 증거 스키마 v2 — `entries_kind_seq`, 기존 `migrate` 경로 |
| `f12e7721` | A3 옵트인 압축 콜드 백업 + 되읽기 검증 |
| `2ad72daa` | digest 재도출 (1차) |
| `05ae64b5` | 리뷰 HIGH-1 — 문서화된 롤백이 편도였다 |
| `df77fc78` | 리뷰 MEDIUM-4·5 · L1 · L2 · L7 |
| `117fcb32` | 리뷰 HIGH-2 · MEDIUM-HIGH-3 · MEDIUM-6 · L4 · L6 |

#### 7.1.1 읽기 목록 표 (A1 산출물 ①)

⚠ **계획 §1 의 「`entries` 를 읽는 모듈 21 개」는 과다 계상이다.**
`git grep -l "FROM entries" -- tos/runtime/src` 는 21 파일을 맞히지만, 그중 **둘**
(`rcl/gates.py` · `rcl/log.py`)은 **RCL 커밋로그 자신의 별도 `entries` 테이블**을 읽는다 —
증거 저장소가 아니다. 증거 저장소를 읽는 것은 **19**, 그중 부팅·복구 경로는 **14** 다.
A2 인덱스가 실제로 돕는 대상은 그 14 다.

| 모듈 (`tos/runtime/src/tos_runtime/`) | 읽는 kind | 부팅 경로 | 질의 형태 |
|---|---|---|---|
| `engine/replay.py:194` | `EVENT_CONSUMED` | ✅ (`compose/_boot_integrity.py:136`) | `kind = ?` · `ORDER BY seq ASC` |
| `engine/replay_stage.py:124` | `FLOW_STEP_ADMITTED` · `FLOW_HALTED` | ✅ (`compose/_engine_wiring.py:81`) | `kind IN (?, ?)` · `ORDER BY seq ASC` |
| `engine/replay_transmit.py:94,114` | `SEND_HANDED_OFF` | ✅ (`compose/_engine_wiring.py:82`) | `kind = ?` · `kind = ? LIMIT 1` |
| `engine/driver.py:447,477` | `EVENT_CONSUMED` · `SEND_STARTED`/`SEND_HANDED_OFF` | ✅ (크래시 복구) | `kind = ? ORDER BY seq ASC` · `kind IN (...) AND seq > ? LIMIT 1` |
| `recovery/inputs.py:98,104` | `REPLAY_VERDICT_IDENTICAL` · `REPLAY_DIVERGED` | ✅ (`compose/_recovery_wiring.py:130`) | `COUNT(*) WHERE kind = ?` |
| `recovery/legacy_receipts.py:134` | `EVENT_CONSUMED` | ✅ (inputs 경유) | `kind = ?` · `ORDER BY seq ASC` |
| `recovery/reconciliation.py:226` | `SEND_HANDED_OFF` | ✅ (inputs 경유) | `kind = ?` · `ORDER BY seq ASC` |
| `recon/evidence_reader.py:150` | `EGRESS_RESULT_CONSUMED` · `RESULT_UNMATCHED` · `POSTTRADE_FINALITY_PROOF` | ✅ (reconciliation 경유) | `kind IN (...)` · `ORDER BY seq ASC` |
| `recon/witness_synthetic.py:162` | `EGRESS_RESULT_CONSUMED` · `RESULT_UNMATCHED` | ✅ (reconciliation 경유) | `kind IN (...)` · `ORDER BY seq ASC` |
| `riskstate/flow_observation.py:216,369` | `SEND_SEALED` · `EVENT_HANDLING_STARTED` · 복구 마커 2종 | ✅ (`compose/_riskstate_wiring.py:54`) | `kind = ? ORDER BY seq ASC` · `kind = ? AND seq = ?` |
| `riskstate/position.py:146` | `SEND_SEALED` | ✅ (riskstate 배선) | `kind = ?` · `ORDER BY seq ASC` |
| `venue/service.py:126` | `VENUE_POLICY_BOUND` 외 3종 | ✅ | `COUNT(*) WHERE kind = ?` |
| `compose/_operations_wiring.py:363` | `STM_ALERT` 외 3종 | ✅ | `kind = ?` |
| `evidence/store.py:337,525,777,835,869,883` | `KEY_ROTATION` · 전체 | ✅ | `kind = ?` · PK 꼬리 · 전체 스캔 · `kind NOT IN (...) ORDER BY seq DESC LIMIT 1` |
| `posttrade/release_consumer.py:369,576,689,703,747` | `CAPACITY_RELEASE_INTENT`/`HELD` · `ECONOMIC_OBLIGATION` · `POSTTRADE_FINALITY_PROOF` · `RELEASE_PROOF_OVERDUE` | ⚠ 배선은 부팅, 질의는 체결 후 | `kind IN (?, ?) DESC` · `kind = ? ASC/DESC` · `kind = ?` |
| `safety/ack.py:195,208` | `STM_ALERT` · `STM_ALERT_ACKNOWLEDGED` | ❌ 운영자 CLI | `seq = ? AND kind = ?` · `kind = ?` |
| `safety/rearm.py:682` | `REARM_APPROVED` | ❌ 운영자 CLI | `kind = ?` |
| `operations/backup_set.py:318,325,340` | `EVENT_CONSUMED` | ❌ 운영자 | `COUNT(*) WHERE kind = '...'` |
| `backtest/calibration_report.py:168` | `EGRESS_RESULT_CONSUMED` | ❌ 오프라인 | `kind = ?` · `ORDER BY seq ASC` |
| ~~`rcl/gates.py:159,299`~~ | — | — | **RCL 커밋로그의 `entries`** — 증거 저장소 아님 |
| ~~`rcl/log.py:353,368,514`~~ | — | — | **RCL 커밋로그의 `entries`** — 증거 저장소 아님 |

#### 7.1.2 A1 측정 — 무엇이 측정됐고 무엇이 아직 아닌가

도구는 `tools/tos_evidence_scan_bench.py`(+ `tests/tools/test_tos_evidence_scan_bench.py`).
합성 DB 는 저장소 밖(`~/.local/state/tos/measure/`)에만 만들고 쌍 측정이 끝나면 즉시 지운다.

**⚠ 합성 이력의 체인은 유효하지 않다.** 행을 참조 파일에서 그대로 복사하므로 `chain_digest`
가 반복된다. 재는 것은 **스캔 비용**이고 체인 검증은 애초에 부팅 경로에 없다(복원 때만 —
계획 §1). 합성본은 절대 복원 소스가 아니다.

**실측된 것 (도구 최종판, `117fcb32`):**

| 단계 | 1 일치 | 10 일치 |
|---|---:|---:|
| `build` 최대 RSS | 28.0 MB | 28.0 MB |
| `measure` 최대 RSS | 19.3 MB | 19.3 MB |
| 파일 크기 | 145.8 MB | 1.458 GB |
| `build` 벽시계 | 0.51 s | 3.82 s |

RSS 가 `--days` 에 대해 **상수**다(계획 §1 의 ≈150 MB/일과도 일치: 1 일치 145.8 MB).

**30 일치 전·후 쌍 (도구 초판 — 절대값은 최종판과 비교 불가, 비율과 질의계획만 유효):**

2.36 M 행 · 4.374 GB. 인덱스 생성 3.0 s · 파일 4.374 → 4.452 GB (+1.8 %).

| 질의 형태 | 전 | 후 | 후 질의계획 |
|---|---:|---:|---|
| `by_kind_payload_asc__hot` (1.83 M 행) | 2951 ms | **4013 ms** | SEARCH … INDEX |
| `by_kind_payload_asc__warm` (151 k 행) | 1514 ms | 274 ms | SEARCH … INDEX |
| `by_kind_payload_unordered__absent` (0 행) | 1392 ms | 0.068 ms | SEARCH … INDEX |
| `exists_by_kind` (0 행) | 1231 ms | 0.059 ms | COVERING INDEX |
| `count_by_kind__hot` | 1269 ms | 82.7 ms | COVERING INDEX |
| `count_by_kind__absent` | 1263 ms | 0.063 ms | COVERING INDEX |
| `full_scan_chain_control` (kind 필터 없음) | 3360 ms | 4320 ms | SCAN — **대조군, 불변** |

**⚠ hot kind 전량 읽기는 인덱스로 느려진다** (2951 → 4013 ms). 저선택도 인덱스의 교과서적
사례다 — 표의 77 % 를 비커버링 인덱스로 끌면 순차 스캔 한 번 대신 히트마다 임의 행 조회가
된다. **그러나 이것은 A2 에 대한 반증이 아니다: `TIME_HEALTH_SNAPSHOT` 을 읽는 런타임
모듈은 하나도 없다**(계획 §1 의 관측을 이 라운드에서 재확인). 그 형태는 인덱스 최악을
**측정해 상한을 박는 프로브**이지 어떤 모듈도 내지 않는 질의가 아니다. 부팅 리더가 실제로
내는 형태는 전부 선택도가 높은 쪽이고, 거기서 5×–20,000× 다. 도구가 그 사실을 상수
주석으로 들고 있고, 런타임에 「absent 는 정말 없는가 · hot 은 정말 최빈인가」를 단정한다.

**아직 측정되지 않은 것: 30/90/365 일치 전·후 표(최종 도구판).**
사유 — 이 실행은 호스트 동시성 가드에 막혀 있다. 드라이버는 다른 프로젝트 빌드가 도는 동안
크기별로 착수를 보류하는데(§7.1.5 의 사고 이후 넣은 가드), 해당 co-tenant 빌드가 2026-09-30
01:30~03:0x 동안 거의 연속으로 돌았다. 가드를 **제거**해 겹쳐 돌리는 변경은 권한 계층이
거부했다(Security Weaken). 가드를 유지한 채 「중단」 대신 「대기」로 바꾸고 메모리 워치독
(가용 4 GB 미만이면 진행 중인 단계를 중단)을 **추가**하는 데까지는 갔으나, 창이 열리지
않았다. 운영자 판단이 필요한 지점이며, 측정 자체는 준비된 상태다(드라이버 1 일치 스모크
통과).

#### 7.1.3 A2 — 실 데이터 마이그레이션

실 paper 산출물(`~/.local/state/tos/realclock-20260928T110001-LONG/data`)의 **사본**에 대해
(원본은 건드리지 않음):

| 항목 | 값 |
|---|---|
| `migrate --store evidence` | v1 → v2 · `entries_kind_seq` 생성 |
| 행 수 | 2824 (불변) |
| 전 열 · 전 행 sha256 (seq 순) | `327e4c86…` → `327e4c86…` **동일** |
| `user_version` | 1 → 2 |

즉 `payload_json` · `entry_digest` · `chain_digest` 를 포함해 **한 바이트도 움직이지 않았다**.
인덱스는 저장 표현이 아니라 보조 구조라는 주장이 실 데이터에서 확인됐다.

#### 7.1.4 A3 — 압축 콜드 백업 왕복

같은 사본에 대해, 실 커스터디 키로:

```
backup-set: wrote gen1 manifest under .../backups
backup-set: archived gen1 to .../cold/gen1.set.tar.xz (7194422 -> 427912 bytes),
            read back and verified: 4 file digest(s) + evidence chain
```

**16.8 ×**, 종료코드 0. 멤버가 4 개인 것은 이 data dir 에 `composite_state` 가 없기 때문이다
(그 런타임은 composite 를 한 번도 쓰지 않았다) — 없는 것을 지어내지 않고 정직하게 비운다.
아카이브 뒤 `inbox`/`marketfeed`/`rcl` 의 sha256 은 원본과 동일했다(라이브 파일 불변).

#### 7.1.5 ⚠ 사고 — A1 초판이 호스트를 메모리 고갈시켰다 (2026-09-30 00:24 KST)

earlyoom 이 이 세션의 python 을 **VmRSS 16.4 GB** 에서 SIGTERM 했고, 19 초 앞서 **무관한
다른 세션의 Gradle(java, 1.5 GB)까지** 죽였다. 스왑은 0 이었다.

- 원인: 도구 초판 `measure()` 가 `fetchall()` 이었다. 90 일치에서 hot kind 는 5.49 M 행 ×
  ≈1.7 KB payload ≈ 9 GB 의 파이썬 문자열이 된다. **빌드가 아니라 측정이 원인이다**(로그상
  `days=90 build` 는 완료됐고 `days=90 BEFORE index` 에서 죽었다).
- 조치: 커서를 스트리밍한다. 이제 이 모듈은 `fetchall` 을 **어디에서도** 부르지 않으며,
  커서 프록시 테스트가 그것을 구조적으로 고정한다(되돌리면 red — 확인함).
  빌드도 배치마다 commit 하고 참조 kind 를 repeat 마다 재질의해 스트리밍한다(리뷰 HIGH-2 —
  초판 빌드는 독스트링이 주장하던 한계를 코드가 지키지 않고 있었다).
- 재발 방지: 드라이버가 크기마다 착수 전 co-tenant 빌드·가용 메모리를 확인하고, 진행 중에도
  5 초마다 가용 메모리를 재 4 GB 미만이면 그 단계를 스스로 중단한다(earlyoom 이 희생자를
  고르게 두지 않는다). 각 크기의 합성 DB 는 쌍 측정 직후 삭제해 피크 디스크를 한 파일로 묶는다.
- **교훈**: 「참조 창이 분 단위라 작다」는 한계가 아니라 입력에 대한 가정이다. 계획이 「메모리
  상수」를 주장하면 그 주장을 **테스트가 들고 있어야 한다**.

이 사고가 §7.1.2 의 동시성 가드를 낳았고, 그 가드가 지금 A1 재실행을 막고 있다.

#### 7.1.6 리뷰 처분 (2026-09-30)

리뷰 레인은 **저자와 다른 패스**였으나 **같은 계열(Sonnet)** 이다 — Opus 소진 상태였고,
운영자는 A2(DB 마이그레이션 = 되돌리기 어려운 경로)에 대해 **Codex 심사를 붙이지 않기로**
했다(CLAUDE.md 2026-09-11 은 그 경로를 대상으로 «할 수 있다»로 열어 두었을 뿐, 범위·비용
승인이 있을 때만이다). 따라서 이 라운드의 교차모델 독립성은 **없다** — 그 사실을 판정의
일부로 기록한다.

판정 **needs-attention**. 리뷰어가 각 지적을 실행으로 재현했다.

| # | 지적 | 조치 |
|---|---|---|
| HIGH-1 | **문서화한 롤백이 편도였다.** 롤백 뒤 재-`migrate` 가 `IntegrityError` 로 죽고 파일이 v1·무인덱스에 갇힌다(v2 코드는 부팅 거부, `migrate` 로는 탈출 불가). 두 번째 형태(인덱스만 삭제)는 조용히 무인덱스로 부팅되고 아무것도 탐지 못 한다 | 대장 스탬프 멱등화 + `repair_statements` 복구 패스 + 런북·독스트링을 지원 절차 하나로 재작성. 테스트 4건 **수정 전 red 확인** |
| HIGH-2 | **벤치의 메모리 한계가 미시행.** `build_synthetic` 이 참조 kind 를 `fetchall()` | 스트리밍 + 「이 모듈은 `fetchall` 을 어디서도 부르지 않는다」를 커서 프록시로 구조 고정(되돌리면 red) |
| MEDIUM-HIGH-3 | 드리프트 검사가 **열 이름만** 비교. 독스트링의 `sqlite_master` 재확인은 **존재하지 않았다** | `PRAGMA table_info` 전체(name·type·notnull·pk) 비교 + `store.py` 를 텍스트로 읽어 DDL 리터럴 일치를 단정하는 테스트(import 는 방화벽 위반, read 는 아님). 거짓 문장 교체 |
| MEDIUM-4 | 검증 실패가 **검증 안 된 아카이브**를 남기고, 「같은 세대 덮어쓰기 거부」 때문에 **재시도까지 막았다** | `.partial` 에 쓰고 검증 통과 뒤에만 rename · 실패 시 unlink |
| MEDIUM-5 | `verify_dir` 미정리 | 성공 시 삭제 · 실패 시 보존(거부 메시지가 경로를 말한다) |
| MEDIUM-6 | hot/warm/absent kind 가 하드코딩·미검증이고 `STALL_ALERT` 는 `tos/` 에 **존재하지 않는다** | 측정 대상 파일에 대해 런타임 단정 · 실제 호출부 파라미터(`{"STM_ALERT"}`)로 교체 · 낡은 인용 5건 갱신 |
| L1 | `filter="data"` 탈출 테스트 없음 | `../` · 절대경로 멤버 테스트. `fully_trusted` 에서 red 확인 |
| L2 | `filter=` 미지원 인터프리터의 TypeError | 「손상된 아카이브」로 접지 않고 환경 결함으로 보고(< 3.11.4 명시) |
| L3 | `migrate` 가 「is current」만 출력 | `MigrationOutcome` — 적용·복구·무변경을 구분해 출력 |
| L4 | 「19 vs 21」 불일치 | 21 파일 중 둘은 RCL 의 별도 `entries` → 증거 리더 19 · 부팅 경로 14 로 통일(§7.1.1) |
| L6 | `--json-out` 덮어쓰기 | 기존 측정 결과를 덮지 않는다 |
| L7 | 매니페스트가 설명하지 않는 멤버 통과 | 거부 |

**범위 밖으로 남긴 것 (의도적):**

- `compute_schema_shape_digest` 에 인덱스를 포함시키지 않았다. 포함시키면 **모든 스토어의
  CREATED digest 가 바뀐다** — 이 PR 범위를 훨씬 넘는 파급이다. 그래서 「인덱스 삭제는
  형상 digest 로 탐지되지 않는다」는 성질은 남아 있고, 대신 `migrate` 의 복구 패스가 그것을
  고칠 수 있게 했다.
- 계획 §5 의 **보관 경로 용량 경보**는 이 PR 에서 구현하지 않았다. A3 는 압축·검증까지이고
  스케줄링(cron)도 범위 밖이다 — 둘 다 이월.

#### 7.1.7 계획 대비 편차

| # | 편차 | 이유 |
|---|---|---|
| 1 | A3 를 `backup_set.py` 안이 아니라 **`operations/backup_archive.py`** 로 분리 | 접어 넣으면 992/1000 줄(`config/tos_size_budget.yaml`, `tos/runtime/src` 는 등재 예외 0). 평범한 수정 한 번이면 게이트가 빨개진다. 운영자 진입점은 여전히 `backup-set` 하나 |
| 2 | A2 인덱스 생성을 **genesis 에서만** — 계획 §2 문언의 「기존 DB 에는 부팅 시 멱등 생성」과 다르다 | `CREATE INDEX IF NOT EXISTS` 는 주변 `CREATE TABLE`/`TRIGGER` 와 달리 기존 파일에서 no-op 이 아니다. 무조건 실행하면 (a) 두 문장 뒤 `ensure_schema_current` 가 거부할 v1 파일에 수 GB 인덱스를 먼저 써넣고 — 「부팅 시 자동 적용 0」(`operations/schema_ledger`)과 정면 충돌 — (b) 운영자가 롤백하려고 방금 지운 인덱스를 되살린다. 생성은 `migrate` 에만 둔다 |
| 3 | 공개 `verify_archive()` 추가 | 콜드 보관본을 새 압축 없이 몇 달 뒤 재검사하는 방향이 실재하고, 그래야 「손상 아카이브 거부」를 공개 경로로 테스트할 수 있다 |
| 4 | 기존 테스트 `test_apply_migrations_brings_a_pre_ledger_file_to_baseline` 수정 | 증거 저장소가 v2 가 되어 pre-ledger 파일이 0 → 1 → 2 사다리를 오른다 |
| 5 | 합성 체인 무효 | 스캔 비용만 재고, 체인 검증은 부팅 경로에 없다(§7.1.2) |
| 6 | 벤치가 `entries` DDL 을 복제 | `tools/` 는 방화벽 역방향 규칙(TOS-FW-R)상 `tos`/`tos_runtime` 을 import 할 수 없다. 드리프트는 런타임 형상 비교 + 소스 텍스트 대조로 막았다 |
| 7 | digest 커밋이 §7 기록보다 먼저 | §7 은 문서이고 digest 는 `tos/src/**.py` + `tos/runtime/src/**.py` 만 접는다 — 문서 커밋이 digest 를 무효화할 수 없다. 반대로 미갱신 digest 를 브랜치에 남기는 쪽이 `release.yaml` 14차 주석이 #814 에 대해 지적한 바로 그 결함이다 |
| 8 | 합성 data dir 에 대한 실 `compose_paper_runtime` 부팅 미시도 | 운영자 지시(질의 형태 수치로 충분) |
| 9 | 자체 테스트가 잡은 결함 2건 | `lzma.LZMAError` 가 `Exception` 직계라 `OSError`/`TarError` catch 를 빠져나갔다(가장 먼저 시험하게 되는 손상 형태) · `tarfile.open(mode="w:xz")` 는 `preset: Literal[0..9]` 를 요구 → `--xz-preset` 0–9 범위 가드를 **실제로** 넣었다(mypy 를 `cast` 로 잠재우지 않았다) |

#### 7.1.8 게이트

`tos-firewall` · `lint-imports`(3 kept, 0 broken) · completion GREEN · spec PASS ·
contract PASS + self-test PASS(뮤테이션 145종) · citation PASS · named-TBD PASS ·
size budget PASS(0 violations) · black/ruff 전부 통과.

CI 와 같은 형태의 mypy 세 줄 전부 `Success`:
`tos/runtime/tests`(236 files) · `tos/runtime/src`(189 files) · `cd tos && mypy src`(265 files).

`expected_code_digest`: `39a8d87d…` → `5e0472ca…`(15차) → **`25f0300a…`**(16차, 리뷰 처분
반영). `expected_dependency_set_digest` 불변
(`20559763…`, 같은 배포 호스트 루트 `.venv`).
