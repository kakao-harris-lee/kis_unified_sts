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

### A1-b. 측정 가드를 in-tree 로 (**구현 — PR #826**)

- A1 재실행 전에 프리플라이트·워치독 드라이버를 **저장소에 커밋하고 기본-on** 으로 둔다 —
  co-tenant 빌드 · `MemAvailable` · **스왑 여유**(전역 `CLAUDE.md`: Swap free 2 GB 미만이면
  착수 금지) · 상위 RSS 를 착수 전과 진행 중에 확인. 2026-09-30 실행의 가드는 커밋되지 않아
  소실됐고 스왑 문턱은 애초에 빠져 있었다(§7.1.7 편차 11 · 11-b).
- 착지: `tools/tos_evidence_scan_measure.py` + `tests/tools/test_tos_evidence_scan_measure.py`
  (§7.1.9). 벤치는 무변경 — 드라이버가 벤치를 자식 프로세스로 몬다.

### A2. `kind` 인덱스 (A1 이 필요를 보이면)

- `CREATE INDEX entries_kind_seq ON entries(kind, seq)` — 21 개 질의의 형태(`WHERE kind = ? [AND seq > ?] ORDER BY seq`)에 맞는다.
- **이것은 DB 마이그레이션이다**(CLAUDE.md 의 되돌리기 어려운 경로). `schema_ledger` 로 버전을 올리고,
  기존 DB 에는 부팅 시 멱등 생성 · 행·체인·digest 는 **바이트 불변**(인덱스는 저장 표현이 아니라 보조 구조).
- 기대 효과: 부팅 질의가 `TIME_HEALTH_SNAPSHOT` 75 % 를 건너뛴다 → 이력에 비례하던 비용이 해당 kind 행 수에 비례.
- 대가: 쓰기마다 인덱스 갱신 · 파일 크기 소폭 증가(A1 에서 함께 잰다).
- **365 일치 실측으로 강화됨(2026-10-01 · 28.7 M 행 · 53.226 GB).** **수치는 §7.1.12 「읽어야 할
  것」 2 한 곳에만 둔다** — 여기서 되풀이하면 한쪽을 고칠 때 다른 쪽이 조용히 어긋난다. 요지:
  인덱스 뒤 선택도 높은 부팅 형태의 비용이 30·90·365 일치에서 **같고**, 인덱스의 최악(hot kind
  전량 읽기)은 365 일치에서도 **측정 가능한 열화가 없다**.
- ⚠ **인덱스가 닿지 않는 `kind` 필터 없는 전체 스캔(90 일 8.7 s → 365 일 129.7 s)은 부팅 비용이
  아니다.** 벤치의 형태별 플래그가 `boot_path=False` 이고, §7.1.2 가 §7.1.1 의 **행 단위** ✅ 를
  형태 단위로 읽은 것이 과잉 독해였다(§7.1.12 「읽어야 할 것」 2 의 정정 표와 소비자 표).
- ⚠ 비용 쪽(+1.8 % 파일 증가)은 365 일치에서 **재확인되지 않았다**(드라이버가 인덱스 뒤 크기를
  적지 않는다 — §7.1.12 「아티팩트가 답하지 못한 것」 2).

### A2-b. `FlowObservationReader` 의 제안별 전체 스캔 (후속 — 이 계획에서 구현하지 않음)

- 위 전체 스캔의 소비자 넷 중 셋(복원 시 체인 재검증 · 보존 판정 · 운영자 프로젝션)은 오프라인
  이지만 넷째는 **런타임이고 제안마다 돈다**: `riskstate/flow_observation.py` 의
  `FlowObservationReader._resolve_handling_started_monotonic` 이 `(seq, kind)` **한 행**을 찾으려고
  `iter_entry_meta()` 로 테이블 전체를 훑는다. 호출 경로는
  `riskstate/service.py::_observe_flow` → `FlowObservationReader.observe` 이고, `_observe_flow` 는
  `aggregate_inputs_for` · `action_flow_inputs_for` 에서 **리스크 단계 시도마다** 불린다.
- 365 일치 실측으로 그 전체 스캔은 **≥130 s** 다(§7.1.12 「읽어야 할 것」 2). A2 인덱스는 이것을
  돕지 못한다 — `kind` 로 좁히는 질의가 아니기 때문이다.
- **고칠 자리는 인덱스가 아니라 그 행이다.** `seq` 는 `entries` 의 PK 이므로 PK 조회 한 번으로
  행을 집고 `kind` 를 확인하면 된다. 별도 PR 로 다루고, 회귀 테스트는 「전체 스캔을 하지 않는다」를
  들어야 한다.

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

#### 7.1.2 A1 측정 — 이력이 늘 때 부팅 질의가 얼마나 비싸지는가 (2026-09-30 실측)

도구는 `tools/tos_evidence_scan_bench.py`(+ `tests/tools/test_tos_evidence_scan_bench.py`),
main `7d039339` 판 — 리뷰 처분(§7.1.6)이 반영된 본이다. 합성 DB 는 저장소 밖
(`~/.local/state/tos/measure/`)에만 만들고 크기별 전·후 쌍이 끝나면 즉시 지운다(피크 디스크 =
한 파일).

**⚠ 합성 이력의 체인은 유효하지 않다.** 행을 참조 파일에서 그대로 복사하므로 `chain_digest`
가 반복된다. 재는 것은 **스캔 비용**이고 체인 검증은 애초에 부팅 경로에 없다(복원 때만 —
계획 §1). 합성본은 절대 복원 소스가 아니다.

**⚠ 측정 조건 — 절대 ms 는 잡음이 있다. 읽어야 할 것은 비율과 질의계획이다.**
다른 프로젝트의 빌드가 **같이 돌 수 있는 상태로** 쟀다(운영자 처분 2026-09-30 「점검 완화
허용」 — **이 측정에 한해** co-tenant 빌드 중단 조건을 빼고 메모리 문턱만 남겼다: 시작
≥ 6 GB · 진행 중 < 4 GB 면 워치독이 해당 단계를 중단. ⚠ **그 가드를 들고 있던 드라이버는
보존되지 않았다** — 아래 「가드의 행방」. ⚠ 스왑 문턱은 빠져 있었다 — §7.1.7 편차 11).
⚠ **이웃 빌드가 실제로 돌았다는 아티팩트는 없다.** `a1.log` 의 크기별 프리플라이트는 30·90·365
셋 다 `no competing build, 14 GB available` 이고, 패스 **진행 중**의 경합을 기록한 것은 아무
데도 없다(프리플라이트는 착수 시점 1 회 표본이라 진행 중 경합을 배제하지도 못한다). 그러므로
「빌드가 간헐적으로 돌았다」는 세션 기록이지 측정이 아니고, 아래에서 저속의 원인으로 쓰지
않는다. OS 페이지 캐시도 비우지 않으므로(root 없이 불가) 비인덱스 비용은 차가운 호스트보다
**과소평가**된다 — 인덱스 이득을 부풀리는 방향이 아니다.

**⚠ 가드의 행방 — 「다음 실행은 다시 보호된다」는 주장을 철회한다.** 위 문턱 둘을 들고
있던 것은 벤치가 아니라 이 실행을 몰았던 **드라이버 스크립트**인데, 그 스크립트는 저장소에
커밋되지 않았고(이 PR 은 docs-only) 호스트에도 남아 있지 않다. 확인 방법과 결과: 드라이버가
`a1.log` 에 찍은 고유 문자열(`co-tenant build check RELAXED` · `preflight ok (days=`)로
`/home/deploy` 전체를 `grep -rl` 한 결과 맞은 것은 **로그와 세션 트랜스크립트뿐**이고
실행 가능한 `.py`/`.sh` 는 하나도 없다. `~/.local/state/tos/measure/` 에도 없다.
따라서 재실행 시 보호를 받으려면 **그 가드를 다시 만들어야 한다** — 지금 in-tree 에 있는
것은 `tools/tos_evidence_scan_bench.py` 뿐이고, 이 도구 자체에는 co-tenant·메모리 프리플라이트가
없다. §7.1.5 가 낳았다고 적은 가드는 현재 **실행 가능한 형태로 존재하지 않는다.**

참조 분포: 2026-09-28 장중 15 분 실 `run`(poll 400) · 2824 행 · `TIME_HEALTH_SNAPSHOT` 77 %
(payload 바이트로는 89 %). 일치 환산 = 장중 7 h → recurring kind ×28, 부팅 1 회 kind ×1.

**⚠ 이 계획에는 `TIME_HEALTH_SNAPSHOT` 비중이 세 번, 서로 다른 분모로 나온다.** 충돌이
아니라 분모가 다른 것이므로 여기서 한 번에 맞춰 둔다(참조 파일 `evidence.sqlite3` 5,332,992 B
를 읽어 재확인):

| 값 | 분모 | 나오는 곳 |
|---:|---|---|
| **77 %** | **행 수** — 2,180 / 2,824 | 위 참조 분포 · 아래 「읽어야 할 네 가지」 3 |
| **89 %** | **`payload_json` 바이트** — 3,715,802 / 4,186,410 B | 위 참조 분포 |
| **75 %** | **payload + 식별자 + digest 바이트 ÷ 파일 5.33 MB** | §0-3 · §1 표 · §2 A2 기대 효과 |

저선택도 인덱스 논증(아래 3)이 쓰는 것은 **행 비중 77 %** 이고, §2 A2 의 「75 % 를 건너뛴다」는
**바이트 비중**이다. 같은 kind 를 서로 다른 축으로 잰 값이다.

| 일수 | 행 | 파일(전) | 파일(후) | 증가 | 인덱스 생성 | build 벽시계 | build 최대 RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 | 2,359,200 | 4.374 GB | 4.452 GB | +1.8 % | 2.3 s | 31 s | 49.8 MB |
| 90 | 7,077,600 | 13.123 GB | 13.357 GB | +1.8 % | 7.4 s | 88 s | 49.7 MB |
| 365 | 28,703,600 | 53.226 GB | (미측정) | — | (미측정) | 366 s | 48.8 MB |

**최대 RSS — 이 실행 구간(30–365 일)에서는 평평하다:**

| 단계 | 30 일 | 90 일 | 365 일 |
|---|---:|---:|---:|
| `build` | 49.8 MB | 49.7 MB | 48.8 MB |
| `measure` (전) | 22.3 MB | 22.3 MB | (중단 — 아래) |
| `measure` (후) | 21.9 MB | 22.5 MB | — |

행이 12 배(2.36 M → 28.7 M)가 되어도 `build` RSS 가 49.8 → 48.8 MB 로 움직이지 않는다.
어디에도 결과셋을 적재하지 않기 때문이고(`fetchall` 호출 0, 커서 프록시 테스트로 구조 고정),
그것이 §7.1.5 사고의 직접 교정이다.

**⚠ 다만 「`--days` 와 무관한 상수」라고는 말할 수 없다 — 이전 실측과 값이 다르다.**
아래는 이 라운드 이전에 같은 벤치로 잰 1·10 일치다(리뷰 전 본문에 있던 표를 지우지 않고
여기로 옮긴다):

| 단계 (이전 실측, 도구 `117fcb32`) | 1 일치 | 10 일치 |
|---|---:|---:|
| `build` 최대 RSS | 28.0 MB | 28.0 MB |
| `measure` 최대 RSS | 19.3 MB | 19.3 MB |
| 파일 크기 | 145.8 MB | 1.458 GB |
| `build` 벽시계 | 0.51 s | 3.82 s |

`build` RSS 가 28.0 MB → 48.8–49.8 MB 로 **1.8 배** 벌어져 있다. 벤치 코드는 같다 —
`git diff 117fcb32 HEAD -- tools/tos_evidence_scan_bench.py` 가 비어 있고 `117fcb32` 는
`7d039339` 의 조상이다. `--batch-rows` 도 양쪽 기본값 10000 이고, 메모리를 묶는 것은 그
값뿐이다(`build_synthetic` 독스트링). **원인 미확인.** 배제된 것만 적는다 — 코드 차이가
아니고, `--days` 에 대한 단조 증가도 아니다(30 → 365 에서 오히려 49.8 → 48.8 MB 로
줄어든다). 1·10 일치 수치 자체가 `~/.local/state/tos/measure/a1/` 에 아티팩트가 없는
**세션 기록**이라 계측 방식(`/usr/bin/time` 인지 내부 측정인지)도 지금 확인할 수 없다.
이 데이터가 뒷받침하는 것은 「30–365 일 구간에서 평평하다」까지다.

**전·후 (ms, 각 3 회 중 최소):**

| 질의 형태 | 행 (30d/90d) | 30일 전 | 30일 후 | 90일 전 | 90일 후 | 이득(90일) |
|---|---:|---:|---:|---:|---:|---:|
| `kind = ?` — 없는 kind (0 행 반환) | 0/0 | 1,362 | 0.104 | 6,658 | 0.105 | 63,568 × |
| `kind = ? LIMIT 1` — 존재 확인 | 0/0 | 1,277 | 0.104 | 5,070 | 0.057 | 88,722 × |
| `COUNT(*) WHERE kind = ?` — 없는 kind | 1/1 | 1,429 | 0.089 | 3,899 | 0.060 | 64,650 × |
| `kind IN (?, ?) ORDER BY seq ASC` | 0/0 | 1,239 | 0.116 | 4,635 | 0.068 | 68,217 × |
| `kind IN (...) AND seq > ? LIMIT 1` | 0/0 | 1,431 | 0.116 | 4,040 | 0.133 | 30,404 × |
| `kind = ? ORDER BY seq ASC` — warm kind 전량 | 151,200/453,600 | 1,465 | 154 | 4,074 | 306 | 13 × |
| `kind = ? ORDER BY seq DESC` — warm kind 전량 | 151,200/453,600 | 1,426 | 224 | 5,317 | 391 | 14 × |
| `COUNT(*) WHERE kind = ?` — hot kind | 1/1 | 1,415 | 106 | 3,973 | 188 | 21 × |
| ⚠ `kind = ? ORDER BY seq ASC` — **hot kind 전량** | 1,831,200/5,493,600 | 2,517 | 2,491 | 6,928 | 7,703 | **0.90 ×** |
| `ORDER BY seq DESC LIMIT 1` — 꼬리 (PK) | 1/1 | 0.053 | 0.061 | 0.058 | 0.075 | **0.77 ×** |
| **대조군**: `kind` 필터 없는 전체 스캔 | 2,359,200/7,077,600 | 2,560 | 3,571 | 7,959 | 8,742 | **0.91 ×** |

반환 행 수는 전·후가 같다 — 인덱스는 비용을 바꾸고 결과를 바꾸지 않는다.

**읽어야 할 네 가지:**

1. **비인덱스 비용은 「찾는 kind」가 아니라 「전체 이력」에 비례한다.** 없는 kind 를 찾는
   질의가 30 일 1.36 s → 90 일 6.66 s 다. **0 행을 돌려주는 질의**가 그렇다 — 표 전체를 읽고
   아무것도 못 찾기 때문이다. 계획 §0-3 의 「이력에 비례해 느려진다」가 이것이다.
2. **인덱스가 걸리면 그 비용이 상수가 된다.** 같은 질의가 30 일 0.104 ms · 90 일 0.105 ms —
   데이터가 3 배가 되어도 **변하지 않는다**. 질의계획은 `SEARCH … USING [COVERING] INDEX
   entries_kind_seq`. 이득이 이력과 함께 커진다(30 일 ~13,000 × → 90 일 ~64,000 ×) —
   그것이 A2 가 사려는 성질이다. warm kind 전량 읽기도 13 × / 14 × 로 같은 방향이다.
3. **⚠ hot kind 전량 읽기는 이득이 없다 — 「손해」라고는 이 데이터로 말할 수 없다.**
   30 일 2517 → 2491 ms(−1 %), 90 일 6928 → 7703 ms(+11 %). ⚠ **초판은 이 +11 % 를
   「느려짐」으로 적었는데, 그 크기는 잡음 바닥 안이다.** 질의계획이 전·후 모두 `SCAN entries`
   로 **바뀌지 않는** 대조군이 같은 패스에서 30 일 +39 % · 90 일 +10 % 움직였다
   (2,560 → 3,571 · 7,959 → 8,742). 파일은 +1.8 % 밖에 안 커졌으므로 그 드리프트는 인덱스
   때문이 아니라 패스 간 변동이다. hot kind 의 +11 % 는 그 안에 들어간다 — 읽을 수 있는 것은
   **「측정 가능한 변화 없음」**까지다(표의 값은 3 회 중 **최소**다. ⚠ 초판은 여기에 「벤치가
   분산을 남기지 않는다」고 적었는데 사실이 아니다 — 기록된 분산으로 다시 읽어도 결론은
   같다는 것까지 **§7.1.12 「잡음 바닥」** 이 든다). 방향 자체는 저선택도 인덱스의 교과서적 예상과 같다 — 행의 77 % 를
   비커버링 인덱스로 끌면 순차 스캔 한 번 대신 히트마다 임의 행 조회가 된다 — 다만 이 실행은
   그 예상을 **확인하지도 반증하지도 못했다.**
   **어느 쪽이든 A2 에 대한 반증은 아니다: `TIME_HEALTH_SNAPSHOT` 을 읽는 런타임 모듈은
   하나도 없다**(계획 §1 의 관측을 이 라운드에서 `git grep` 으로 재확인 — 리더 0). 그 형태는
   인덱스 최악을 **측정해 상한을 박는 프로브**이지 어떤 모듈도 내지 않는 질의다. §7.1.1 의
   부팅 리더 14 개가 실제로 내는 형태는 전부 선택도가 높은 쪽이다. 도구가 이 사실을 상수
   주석으로 들고 있고, 런타임에 「absent 는 정말 없는가 · hot 은 정말 최빈인가」를 단정해
   분포가 바뀌면 거부한다(리뷰 MEDIUM-6).
4. 대조군(`kind` 필터 없는 전체 스캔 — `replay`/`iter_entry_meta`)은 개선되지 않는다.
   개선될 수 **없고**(질의계획이 전·후 모두 `SCAN entries`), 그래서 위 개선이 캐시가 아니라
   인덱스 때문임을 뒷받침한다. ⚠ 다만 대조군의 +39 %(30 일)·+10 %(90 일)는 파일이 +1.8 %
   커진 것으로 **설명되지 않는다** — 이것이 이 실행의 **잡음 바닥**이고, 3 에서 hot kind 를
   「측정 가능한 변화 없음」으로 읽는 근거다. PK 꼬리 질의도 같다(0.058 → 0.075 ms).

**365 일치 질의 타이밍은 측정하지 않았고, 중단 시점의 수치도 남기지 않았다.**

365 일치 파일(53.23 GB)은 빌드까지 끝냈으나(위 표, 28.7 M 행 · 366 s · RSS 48.8 MB) 비인덱스
패스를 **중단했다**. ⚠ **그 패스는 아티팩트를 하나도 남기지 못했다** — `a1.log` 는
`########## days=365 BEFORE index` 줄에서 끝나고, `before-365d.json` 은 존재하지 않으며
`before-365d.time` 은 0 바이트다. 이 절의 초판이 실측으로 적었던 「캐시 초과 구간
24 MB/s(2,888 MB / 120 s)」와 「612 GB 진행」은 **세션 기록뿐이고 아티팩트가 없다.** 감사도
재현도 불가능하므로 실측에서 내린다. 그 위에 세워져 있던 「76 × 붕괴」·「1 회 스캔 ≈ 35 분」·
「전·후 패스 ≈ 19.4 h」·「페이지 캐시를 넘는 순간 처리량이 무너진다」는 전부 **가설**이다.

아티팩트가 실제로 말하는 것은 이것뿐이다:

| 값 | 출처 | 지위 |
|---|---|---|
| 90 일치 비인덱스 패스 벽시계 **238.6 s** | `before-90d.time` | 실측 |
| 그 패스가 디스크에서 실제로 읽은 양 **19.0 GB** → **79.6 MB/s** | `before-90d.time` 의 `File system inputs: 37,112,704`(512 B 블록) | 실측 |
| 그 패스의 논리 처리량 **≈ 1,815 MB/s** | 433 GB ÷ 238.6 s | **모델값** — 분모만 실측 |
| 365 일치 비인덱스 패스가 돈 시간 **≤ 6,970 s** | `a1.log` mtime 07:43:54 → `synth/` mtime 09:40:04 | 실측(상한) |
| 365 일치 구간 속도 · 진행량 | 세션 기록 | **아티팩트 없음** |

**1,815 MB/s 는 실측이 아니라 모델값이다.** 분자 433 GB 는 「전체 스캔 형태 11 개 × 3 회 ×
13.123 GB」로 **센 것**이지 잰 것이 아니다(벤치 15 형태 중 sub-ms 로 끝나는 4 개 —
`by_kind_and_seq` · `exists_seq_and_kind` · `tip_excluding_kinds` · `tip_unfiltered` — 는
한 페이지만 읽는다. 여기에 `validate_shape_kinds` 의 `GROUP BY kind` 전체 스캔 1 회를
더하면 446 GB · 1,870 MB/s 다). 그리고 이 값은 **저장장치 속도가 아니다** — 같은 패스가
디스크에서 실제로 읽은 것은 19.0 GB(79.6 MB/s)뿐이고 나머지는 페이지 캐시에서 나왔다.
30 일치 패스는 `File system inputs: 0` — 디스크를 **한 블록도** 읽지 않았는데 같은 방식으로
계산하면 2,483 MB/s 가 나온다. 이 숫자는 메모리 대역폭과 CPU 를 재고 있지 디스크를 재고
있지 않다.

**타임스탬프가 묶는 것은 창(window)뿐이다.** 365 일치 비인덱스 패스는 `a1.log` 의 마지막
쓰기(07:43:54.626)와 합성 파일이 지워진 시각(`synth/` mtime 09:40:04.298) 사이,
**6,970 s 이내**에 돌았다. 세션 기록의 612 GB 가 **논리 바이트**라면 그 창의 평균은
**≥ 88 MB/s** 다.

⚠ 그렇다고 두 세션 값이 **서로 모순인 것은 아니다** — 24 MB/s 의 회계(논리인지 물리
디스크인지)가 어디에도 기록돼 있지 않기 때문이다. 바로 위에서 같은 벤치의 90 일치 패스가
논리 433 GB 대 물리 19.0 GB 로 **23 배** 벌어지는 것을 보았다. 그러니 「612 GB 논리 ·
24 MB/s 물리」는 서로 어긋나지 않고 **동시에 참일 수 있다.** 두 값은 틀린 것이 아니라
**단위가 불명이라 비교 불가**이고, 그래서 여기서 결론으로 쓰지 않는다.

느려진 원인도 지목하지 않는다. 페이지 캐시 초과는 아래 「반대 증거」 때문에 단정할 수 없고,
이웃 빌드의 I/O 경합은 **관측된 바가 없다**(위 「측정 조건」 — 프리플라이트 셋 다
`no competing build`). 둘 다 가능한 이야기일 뿐 아티팩트가 가리키는 쪽은 없다.

**산술 정정 (세션 값을 그대로 끌고 가도 초판 숫자는 틀렸다).**

- 53,226 MB ÷ 24 MB/s = **2,218 s(≈ 37 분)** 이지 2,115 s 가 아니다. 2,115 s 는 파일을
  MiB(50,760 MiB)로, 속도를 MB/s 로 읽어 **단위를 섞었을 때** 정확히 나오는 값이다.
- **1,756 GB(= 33 × 53.226 GB)는 「전 패스」 하나뿐**이다. 인덱스 후 패스도 hot kind 전량
  읽기와 대조군 전체 스캔이 남아(90 일치에서 7,703 ms · 8,742 ms) 최소 6 회 × 53.226 GB =
  **319 GB** 를 더 읽는다. 전·후 합계는 **≈ 2,076 GB** 이고, warm kind 의 인덱스 경유 임의
  행 조회는 여기에 포함조차 하지 않았다.
- 따라서 초판의 「612 GB / 1,756 GB (35 %)」는 분자에 아티팩트가 없고 분모도 틀렸다.

이 셋은 24 MB/s 가 사실일 때만 성립하는 **가설**이며, 결론으로 쓰지 않는다.

**⚠ 반대 증거 — 90 일치에서 이미 캐시를 넘겼는데 절벽은 없었다.** 초판의 「≈14 GB」는
페이지 캐시를 잰 값이 아니라 프리플라이트가 찍은 **`MemAvailable`** 이다(`a1.log`:
`14 GB available`). 그리고 90 일치 패스는 그 문턱을 이미 건드렸다 — 파일이 13.123 GB 인데
디스크에서 읽은 것은 **19.0 GB** 로 파일의 1.45 배다. 전부 캐시에 남아 있었다면 나올 수 없는
값이고, 즉 **축출이 이미 일어났다.** 그런데도 패스는 238.6 s 에 끝났고 붕괴는 없었다.
따라서 「캐시를 넘는 **순간** 처리량이 무너진다」는 형태의 주장은 이 데이터와 맞지 않는다.
53.23 GB(= `MemAvailable` 의 약 4 배)에서 무슨 일이 벌어지는지는 여전히 열려 있지만,
그것은 **절벽이 있다는 근거가 아니라 미측정이라는 뜻**이다.

**남는 사실.** 365 일치에서 비인덱스 by-kind 질의가 얼마나 걸리는지는 **미측정이다.**
30 → 90 일에서 비인덱스 비용이 이력과 함께 자란다는 것(없는 kind 1.36 s → 6.66 s, 행 3 배)은
실측이다. 53 GB 에서 무슨 일이 벌어지는지는 **다시 재야 한다**(§7.1.7 편차 10 · 후속 A1-b).

**종료 조건 판정 (계획 §2 A1 「며칠치 이력에서 부팅이 N 초를 넘는가」).**
부팅 리더가 실제로 내는 형태에서, 인덱스 없이 질의 하나가 **90 일치에 4–7 s** 다
(365 일치는 미측정 — 위). §7.1.1 의 부팅 경로 리더는 14 개이고 여러 개가 여러 kind 를
읽으므로 부팅 리플레이·복구 조립은 그 값들의 합으로 쌓인다. 인덱스 뒤에는 **선택도가 높은
형태**가 90 일치에서 **0.057–0.133 ms** 로 떨어진다(위 표의 0.105 · 0.057 · 0.060 · 0.068 ·
0.133). ⚠ **「전부 0.1 ms 미만」은 아니다** — warm kind 전량 읽기는 인덱스 뒤에도 154 ms
(30 일) · 306 / 391 ms(90 일)이고, hot kind 전량 읽기는 2,491 / 7,703 ms 로 사실상 변하지
않는다. **A2 는 필요하고 효과가 있다** — 다만 그 효과는 「0 행 · 존재 확인 · COUNT」 계열에서
4–7 s → 0.1 ms 대이고, 전량 읽기 계열에서는 13–14 × 이거나 없다.

⚠ **인덱스가 닿지 않는 전체 스캔이 남는다.** 대조군인 `kind` 필터 없는 전체 스캔은
`evidence/store.py` 의 질의 형태이고 90 일치에서 인덱스로 **나아지지 않는다**(7.96 → 8.74 s).
이력에 비례하는 그 전체 스캔은 계속 나고, 경계 있는/스트리밍 리플레이는 A2 와 **별개의
변경**이다(여기서 설계하지 않는다).
⚠⚠ **이 절의 초판은 그것을 「§7.1.1 에서 부팅 경로(✅)」라며 부팅 비용으로 적었는데 틀렸다** —
그 ✅ 는 호출부 6 개·형태 4 종을 묶은 **행 단위** 표시이고, 이 형태의 리더는 복원 시 체인
재검증과 보존 판정·운영자 프로젝션이다. 근거 표는 **§7.1.12 「읽어야 할 것」 2** 에 있다.

단, 이 판정은 「paper 합성 경로 기준」이다(계획 §5 의 유보 그대로) — 주문이 실제로 나가는
단계의 분포는 다를 수 있다.

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

이 사고가 위 「재발 방지」의 동시성·메모리 가드를 낳았고, 그 가드를 단 드라이버로 A1 을
**2026-09-30 에 실제로 돌렸다** — 30·90 일치는 전·후를 모두 측정했고, 365 일치는 빌드까지만
하고 비인덱스 패스를 중단했다(§7.1.2). ⚠ 다만 **그 드라이버는 보존되지 않았다** — 커밋되지
않았고 호스트에도 남아 있지 않다(§7.1.2 「가드의 행방」). 따라서 위 「재발 방지」 항목은 이
실행에서 무엇이 돌았는지에 대한 기록이지, 지금 재실행하면 받을 보호에 대한 서술이 아니다.

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
| 10 | **365 일치 질의 타이밍 중단** — 빌드 사실(28.7 M 행 · 53.23 GB · 366 s · RSS 48.8 MB)만 실측하고 전·후 표는 30·90 일치로 낸다 | 파일(53.23 GB)이 프리플라이트가 찍은 `MemAvailable`(`14 GB available`)의 약 4 배라 패스가 너무 느려 보인다는 **실행 중 판단**으로 중단했다. 계획 §2 A1 에는 이 대비책 문언이 **없다** — 사전 승인된 fallback 이 아니라 그 자리에서 내린 결정이다. ⚠ 중단 시점의 속도·진행량을 아티팩트로 남기지 못했고(`before-365d.time` 0 바이트 · `before-365d.json` 없음 · `a1.log` 는 `days=365 BEFORE index` 에서 끝남), 따라서 초판이 근거로 적었던 「1,815 → 24 MB/s · 76 × 붕괴 · 19.4 h · 35 % 진행」은 **가설로 격하**했다(§7.1.2). 남은 편차 사실은 「365 일치 전·후 표 미측정」 하나다. **2026-10-01 — 표는 ✅ 해소, 가설은 ⚠ 부분 해소 (§7.1.12).** A1-b 드라이버로 완주했다(전 패스 3 h 54 m · 후 패스 15 m · 전 패스 물리 읽기 1,729.74 GB). 편차 **사실**(전·후 표 미측정)은 닫혔다. 격하했던 가설 넷 중 셋은 전 패스의 **역방향 스캔 국면에서 재현**됐고(물리 **26.6 MB/s** · 1 회 23.8–34.5 분 · 붕괴 60–68 ×) 틀렸던 것은 **그 속도를 패스 전체로 외삽한 것**이다 — 같은 패스의 정방향 국면은 418.3 MB/s 로 역방향의 **16 배**이고, 그래서 전·후 합계는 19.4 h 가 아니라 **4.157 h** 다. ⚠ 90 일치의 물리 79.6 MB/s 와는 비교하지 않는다 — 그 값은 캐시 적중 ≈95 % 에 묶여 있어 장치 속도가 아니다. 두 실행에서 같은 뜻을 갖는 축은 논리 처리량이고, 거기서는 1,815(모델) → 정방향 430.5 · 역방향 30.1 MB/s 다. 넷째(「캐시 초과 **순간** 붕괴」)는 **여전히 판정 불가** — 적중률 95.6 %(13 GB) → 4.5 %(53 GB) 두 점뿐이라 절벽과 소진을 구분하지 못한다. 후속: 180 일치(≈26 GB) 또는 270 일치(≈39 GB) 한 점 (**이 PR 에서 돌리지 않았다**) |
| 11 | A1 실행에 한해 co-tenant 빌드 중단 조건 해제 | 운영자 명시 승인(2026-09-30 「점검 완화 허용」). 실행 중에는 메모리 문턱 둘(시작 ≥ 6 GB · 진행 중 < 4 GB 중단)을 유지했고 `a1.log` 의 크기별 `preflight ok` 줄이 그것을 보여 준다. ⚠ 그러나 **「다음 실행은 다시 보호된다」는 철회한다** — 그 문턱을 들고 있던 드라이버는 커밋되지 않았고 호스트에도 남아 있지 않다(§7.1.2 「가드의 행방」). 재실행 전에 가드를 다시 만들어야 한다. 그 대가로 절대 ms 에 잡음이 있다(§7.1.2 측정 조건) |
| 11-b | ⚠ **미등재 편차 — 스왑 문턱이 프리플라이트에 없었다** | 전역 `~/.claude/CLAUDE.md` 는 「available 6 GB 미만 **또는 Swap free 2 GB 미만**이면 빌드를 시작하지 않는다」 + 상위 RSS 확인(`ps --sort=-rss`)을 요구한다. `a1.log` 의 프리플라이트가 찍은 것은 `no competing build, N GB available, N disk free` 뿐이고 **스왑도 상위 RSS 도 없다**. 운영자 면제는 co-tenant 조건에만 걸려 있었으므로(「메모리 문턱만 남겼다」) 스왑 게이트는 **승인 없이 빠진 것**이고 편차로 적히지도 않았다. 이것이 사소하지 않은 이유는 §7.1.5 의 그 사고에서 먼저 무너진 것이 available 이 아니라 **스왑 0** 이었기 때문이다(§7.1.5 「스왑은 0 이었다」). 후속 A1-b 가 닫는다 |

**후속 등재 — A1-b (이 PR 범위 밖, 구현하지 않음).**
A1 재실행 전에 프리플라이트·워치독을 **in-tree 로** 올린다: co-tenant 빌드 · `MemAvailable` ·
**스왑 여유** · 상위 RSS 를 착수 전과 진행 중에 확인하는 드라이버를 저장소에 커밋하고
**기본-on** 으로 둔다(계획 §2 A1-b). 근거는 편차 11(가드 소실) · 11-b(스왑 문턱 누락)이고,
§7.1.5 의 교훈 「계획이 주장하면 그 주장을 테스트가 들고 있어야 한다」가 가드에도 그대로
적용되기 때문이다 — 지금 가드는 `a1.log` 의 문자열로만 존재한다.

#### 7.1.8 게이트

`tos-firewall` · `lint-imports`(3 kept, 0 broken) · completion GREEN · spec PASS ·
contract PASS + self-test PASS(뮤테이션 145종) · citation PASS · named-TBD PASS ·
size budget PASS(0 violations) · black/ruff 전부 통과.

CI 와 같은 형태의 mypy 세 줄 전부 `Success`:
`tos/runtime/tests`(236 files) · `tos/runtime/src`(189 files) · `cd tos && mypy src`(265 files).

`expected_code_digest`: `39a8d87d…` → `5e0472ca…`(15차) → **`25f0300a…`**(16차, 리뷰 처분
반영). `expected_dependency_set_digest` 불변
(`20559763…`, 같은 배포 호스트 루트 `.venv`).

#### 7.1.9 A1-b 착지 — PR #826 (2026-09-30, 분기점 main `2b018a27`) — §7.1 과 별개 PR

§7.1.7 편차 11(가드 소실)·11-b(스왑 문턱 누락)를 닫는다. **측정 자체는 다시 돌리지 않았다** —
이 PR 은 다음 실행이 받을 보호를 in-tree 로 올릴 뿐이고, §7.1.2 의 수치는 하나도 바뀌지 않는다.

| 커밋 | 내용 |
|---|---|
| `fb083dde` | 프리플라이트·워치독 드라이버 + 헤르메틱 테스트 |
| `f12ca02a` · `2e68d4ff` · `202ac95d` | 이 절(§7.1.9) 자체 — 착지 기록 · 헤딩 깊이 · 커밋 SHA |
| `5310e90a` | 자체 리뷰 1 — 중단이 방금 만든 합성 파일을 지우고 있었다 |
| `12988f4a` | 자체 리뷰 2 — 부분 빌드를 「재개 가능」이라고 안내하던 메시지 |
| `1b2293e1` | 자체 리뷰 3 — 중단된 단계가 자원 수치를 하나도 안 남겼다 |
| `77af085b` | 독립 리뷰 #826 지적 F1~F9 |
| `b3650672` · `e13203ed` | 리뷰 1회차 처분 §7.1.10 · 이 표 (F10) |
| `a5c5bfec` | 리뷰 2회차 지적 F1~F10 |
| `fcc934f8` | 리뷰 2회차 처분 §7.1.11 · 이 표 |

⚠ 이 표는 초판에서 `fb083dde` 와 `5310e90a` 만 들고 있었다. 그 뒤 두 커밋이 더 들어왔는데
같은 절의 산문은 그 동작을 「착지했다」고 서술하고 있었다 — 감사자가 git 과 대조하면 주인 없는
동작이 나온다(리뷰 F10). 이 절의 규율이 「세션 기록이 아니라 파일을 인용한다」인 이상, 표가
브랜치와 어긋나는 것은 사소한 누락이 아니다.

**무엇이 들어왔나.** `tools/tos_evidence_scan_measure.py`(순수 stdlib) 가 한 번의 측정을 몰고,
호스트가 감당 못 할 때 **착수를 거부하거나 진행 중 중단**한다. 기존 벤치
`tools/tos_evidence_scan_bench.py` 는 **한 줄도 바뀌지 않았다** — 드라이버가 벤치를 자식 프로세스로
부른다. `tos/src` · `tos/runtime/src` 무변경이므로 **digest 재도출 없음**.

단계는 `build` → `before` → `after` 셋이다. **별도의 「인덱스 생성」 단계는 없다** — 벤치에 그런
하위명령이 없고 인덱스 생성은 `measure --create-index` 안에 있어서, `after` 단계가 그것을 부르고
인덱스 생성 시간은 자식의 stdout(`after-Nd.out`)에 남는다.

**문턱과 그 출처.** 코드에 맨 상수로 박힌 문턱은 없다 — 전부 인자이고, 기본값마다 출처를 적었다.

| 인자 | 기본값 | 출처 |
|---|---:|---|
| `--min-available-gb` | 6 | 전역 `~/.claude/CLAUDE.md` 「로컬 빌드 동시 실행 제한」(2026-09-25) |
| `--min-swap-free-gb` | 2 | **같은 규칙의 스왑 절** — 편차 11-b 가 빠져 있었다고 적은 그 조항 |
| `--abort-available-gb` | 4 | 2026-09-30 실행이 실제로 쓴 값(§7.1.2 「진행 중 < 4 GB」) — 재실행 비교 가능성 |
| `--abort-swap-free-gb` | 1 | **규칙 없음.** 전역 규칙은 착수만 말한다. 이 드라이버 자신의 값(착수 문턱의 절반, 메모리 쌍의 4/6 과 같은 관계)이라고 코드에 적었다 |
| `--watch-interval-s` | 5 | §7.1.5 「재발 방지」의 「5 초마다」 |
| `--term-grace-s` | 10 | 이 드라이버 자신의 값 |
| `--disk-headroom-ratio` | 1.25 | 예측은 합성 파일만 덮는다. `after` 가 인덱스를 제자리에 만들고(+1.8 %, §7.1.2 30·90 일 공통) sqlite 가 만드는 동안 임시 공간을 쓴다. 1.25 는 그 실측 위에 얹은 이 드라이버의 여유 |

**디스크 추정은 유도값이지 상수가 아니다.** 벤치 자신의 `profile_kinds`(따라서 `entries` 형상
드리프트 가드가 그대로 적용된다)로 참조 분포를 읽고, 벤치의 복제 규칙(부팅 1회 kind 는 `days` 배,
나머지는 `round(days×session_hours×60÷reference_minutes)` 배)을 다시 적용한 뒤, payload 를 **참조
파일 자신의** `file_bytes / payload_bytes` 비로 환산한다. 2026-09-30 아티팩트와 대조:

| 값 | 예측 | `a1/build-30d.json` 실측 | 차 |
|---|---:|---:|---:|
| 행 | 2,359,200 | 2,359,200 | **정확 일치** |
| 바이트 | 4,471,389,391 | 4,373,725,184 | +2.2 % |

행이 정확히 맞는 것은 우연이 아니라 **테스트가 들고 있는 성질**이다(`test_the_size_estimate_
predicts_the_real_row_count_exactly` 가 실제 합성 파일을 만들어 벤치의 보고 행수와 대조한다).
복제 규칙은 드라이버가 **다시 적은** 것이므로 — 벤치가 그 규칙을 함수로 노출하지 않는다 — 그
사본이 조용히 벌어지는 것을 그 테스트가 막는다. 바이트는 추정이고, 틀리는 방향은 **거부 쪽**이다.

**§7.1.2 가 「없다」고 적은 두 가지를 부수적으로 닫는다.**

0. **중단도 수치를 남긴다.** `ABORTED-…json` 의 `partial_resource` 가 죽인 자식의 rusage
   (최대 RSS · user/system · `File system inputs`/`outputs`)와 마지막 `/proc/<pid>/io` 를 든다.
   §7.1.2 가 365 일치 중단에 대해 「중단 시점의 수치도 남기지 않았다」고 적고 초판의 수치를 전부
   **가설로 격하**해야 했던 바로 그 구멍이다 — `before-365d.time` 은 0 바이트였고
   `before-365d.json` 은 없었다. `os.wait4` 가 죽인 자식의 rusage 를 돌려주므로 버리지 않고 적는다.
1. **아티팩트가 남는다.** `preflight.json`(최신) · `preflight.jsonl`(누적) · `watchdog.jsonl`(표본
   시계열) · `<step>-Nd.resource.json` · `<step>-Nd.time`. 「프리플라이트 셋 다 `no competing
   build`」 같은 문장을 다음부터는 **파일로** 인용한다. 프리플라이트는 **거부할 때도** 쓴다 —
   아무것도 안 남기는 거부는 애초에 검사하지 않은 것과 구별되지 않는다.
2. **물리 대 논리 읽기.** 자식의 `/proc/<pid>/io` 에서 `rchar`(프로세스가 요청한 바이트, 페이지
   캐시 포함) 옆에 `read_bytes`(블록 계층이 실제로 옮긴 바이트)를 남긴다. §7.1.2 가 90 일치에서
   논리 433 GB 대 물리 19.0 GB 로 **23 배** 벌어지는 것을 `File system inputs` 하나로 겨우 짚어낸
   그 구분이, 다음부터는 단계마다 직접 기록된다. 표본은 종료 직전 것이라 각 레코드가 자신의
   `proc_io_sample_age_seconds` 를 들고 있다 — `--watch-interval-s` 로 묶인 잔차를 숨기지 않고 적는다.

**자원 계측은 `os.wait4` 다** — A1-b 가 지정받은 `getrusage(RUSAGE_CHILDREN)` 차분이 아니다.
`RUSAGE_CHILDREN.ru_maxrss` 는 지금까지 거둔 **모든** 자식에 대한 진행 최대값이라, 최대값을 올리지
않은 단계에서는 전·후 차가 0 이고 아무것도 말하지 않는다(실제로 §7.1.2 의 `measure` 단계들이
`build` 의 49.8 MB 아래다). `os.wait4(pid, …)` 는 **그 자식 하나의** rusage 를 돌려주고, GNU
`time -v` 가 읽는 것과 같은 커널 카운터다. 의도적 개선이라 코드와 커밋에 이유를 적었다.

`.time` 파일은 GNU `time -v` 의 **필드명 그대로** 쓴다 — §7.1.2 가 `before-90d.time` 의
`File system inputs: 37,112,704` 을 인용하고 있어서, 같은 grep 이 계속 같은 이름을 찾아야 한다.
`wait4` 가 주지 않는 필드는 **0 으로 채우지 않고 뺀다**(「측정 안 함」을 뜻하는 0 은 이 계획이 이미
한 번 철회해야 했던 종류의 숫자다).

**「자기가 막는다고 말한 것을 허용하는 가드」 방지.** 중단 문턱이 착수 문턱보다 **높게** 설정되면
드라이버가 거부한다. 그 조합은 프리플라이트가 방금 통과시킨 런을 워치독이 첫 표본에서 죽이는
것이거나, 뒤집어 읽으면 착수 문턱이 진짜 진행 중 문턱이고 중단 문턱이 장식이라는 뜻이다.

**실호스트 실측 2건(합성 실행 아님).**

1. **프리플라이트가 실제로 거부했다.** 이 PR 작업 중 호스트에서 다른 프로젝트의 Gradle 빌드가
   돌고 있었고, `preflight` 하위명령이 그 PID 들을 대며 rc=1 로 멈췄다. 같은 실행에서 **오탐
   1건**이 드러났다 — 다른 에이전트 세션의 `bash -c "… pgrep -f 'GradleWrapperMain|…'"` 가
   **패턴을 찾고 있다는 이유로** 매치됐다. 전역 규칙 자신의 `| grep -v pgrep` 이 겨냥한 바로 그
   경우라 검색 명령 필터를 넣고 **양방향**으로 테스트했다(검색 줄은 통과, 진짜
   `java … GradleWorkerMain` 줄은 거부). 무엇을 가릴 수 있는지도 코드에 적었다.
2. **추정이 2026-09-30 아티팩트와 맞는다** — 위 표.

**테스트 증거.**
`.venv/bin/pytest tests/tools/test_tos_evidence_scan_measure.py tests/tools/test_tos_evidence_scan_bench.py -q -p no:cacheprovider`
→ **48 passed**(신규 30 + 기존 벤치 18).

**가드 레드 증명 — 16/16, 초록으로 남은 가드 0.** 각 가드를 하나씩 무력화하고 그 테스트만 다시
돌려 red 를 확인한 뒤 복원했다. §7.1.5 의 교훈(「계획이 주장하면 테스트가 그 주장을 들고 있어야
한다」)을 가드 자신에게 적용한 것이고, `MEMORY.md` 의 반복 결함 형태
(「새 가드에 **이것이 실패하는 구체적 입력**을 못 쓰면 아무것도 막지 않는 것」)가 요구하는 절차다.

| 무력화한 가드 | red 가 된 테스트 |
|---|---|
| 프리플라이트 `MemAvailable` 문턱 | `test_preflight_refuses_when_mem_available_is_below_the_start_floor` |
| 프리플라이트 `SwapFree` 문턱 (편차 11-b) | `test_preflight_refuses_when_swap_free_is_below_the_start_floor` |
| 프리플라이트 경합 빌드/측정 | `..._when_a_gradle_build_is_running` · `..._when_another_measurement_driver_is_running` |
| 검색 명령 필터(오탐 쪽) | `test_a_process_merely_searching_for_the_marker_is_not_a_competing_build` |
| 프리플라이트 디스크 여유 | `..._when_the_disk_cannot_hold_the_synthetic_file` · `test_the_cli_reports_a_refusal_as_exit_one_and_starts_nothing` |
| 프리플라이트 기존 아티팩트 | `..._when_a_step_artifact_already_exists` |
| meminfo 필드 결손 fail-closed | `test_meminfo_without_the_fields_the_guards_need_is_refused` |
| 중단 문턱 < 착수 문턱 검증 | `test_an_abort_floor_above_the_start_floor_is_refused` |
| 워치독 `MemAvailable` 중단 | `test_the_watchdog_kills_the_child_when_memory_falls_and_writes_the_abort_artifact` |
| 워치독 `SwapFree` 중단 | `test_the_watchdog_aborts_on_low_swap_alone` |
| 워치독 co-tenant 중단 | `test_the_watchdog_aborts_when_a_competing_build_appears_mid_run` |
| 유예 뒤 SIGKILL 승격 | `test_a_child_that_ignores_sigterm_is_escalated_to_sigkill` |
| 크기 추정 스케일 규칙 | `test_the_size_estimate_predicts_the_real_row_count_exactly` |
| 중단 시 합성 파일 보존 | `test_an_aborted_run_keeps_the_synthetic_file_it_built` |
| 보존 판정 세 갈래 | `test_the_synthetic_disposition_says_the_right_thing_for_each_outcome` |
| 중단 레코드의 부분 자원 수치 | `test_the_watchdog_kills_the_child_when_memory_falls_and_writes_the_abort_artifact` |

SIGKILL 승격 테스트는 자식이 **핸들러를 설치했다고 알린 뒤에만** 중단을 일으킨다. 그러지 않으면
인터프리터 기동 중에 SIGTERM 이 닿아 기본 처리로 죽고, 테스트는 **초록인데 승격은 증명하지 못한다.**

**자체 리뷰가 잡은 결함 1건.** 초판은 실행이 끝나면 합성 파일을 지웠는데, 그 `finally` 가
**중단에도 걸렸다** — 워치독이 메모리 부족으로 단계를 멈추면 방금 만든 합성 파일까지 사라진다.
지우는 것은 메모리에 아무 도움이 안 되고(부족한 것은 RAM 이지 디스크가 아니다) 365 일치면 366 s
· 53 GB 를 버리는 것이다. 이제 **전 단계가 실제로 돈 뒤에만** 지우고, 중단 시에는 파일 경로와
크기, 재개용 `--steps` 를 로그에 적고 남긴다. 테스트가 이것을 들고 있다(위 표 — 되돌리면
「the aborted run deleted the build it had just paid for」로 red).

같은 검토에서 **초판의 재개 안내가 틀렸다**는 것도 나왔다. 「첫 단계를 뺀 나머지」를 재개 대상으로
적었는데, **`build` 중에 멈춘 경우 그 파일은 부분 기록**이라 측정 입력이 아니고 벤치는 기존
`--out` 을 덮어쓰기를 거부한다 — 있지도 않은 재개를 권하는 안내였다. 판정을
`decide_synthetic_disposition()` 으로 빼내 세 갈래(`delete` / `keep-partial` / `keep-resumable`)를
각각 테스트한다. 부분 파일 메시지에는 `--steps` 가 **없어야** 한다는 것까지 단언한다.

**계획 §2 A1-b 대비 편차.**

| # | 편차 | 이유 |
|---|---|---|
| a | 자원 계측을 `getrusage(RUSAGE_CHILDREN)` 차분이 아니라 `os.wait4` 로 | 위 「자원 계측은 `os.wait4` 다」 — 차분은 최대값을 올리지 않은 단계에 대해 0 을 준다 |
| b | 중단 아티팩트 이름이 `ABORTED-<step>.json` 이 아니라 `ABORTED-<step>-<days>d.json` | 출력 디렉터리 하나를 크기별로 공유한다(기존 `a1/` 가 그렇다). 다른 아티팩트가 전부 `-Nd` 를 달고 있는 이유와 같다 |
| c | `.time` 텍스트와 `.resource.json` 을 **둘 다** 쓴다 | 지시는 「JSON 으로」였다. `.time` 을 JSON 으로 바꾸면 §7.1.2 의 `File system inputs` 인용과 같은 grep 이 죽는다 — 비교 가능성을 지키려고 둘을 쓴다 |
| d | 호스트 판독기(`HostReader`)가 `main()` 의 **키워드 인자**이지 CLI 플래그가 아니다 | 테스트는 주입해야 하고, 운영자는 셸에서 더 관대한 `/proc` 을 가리킬 수 없어야 한다 |
| e | 검색 명령 필터를 추가했다 | 위 실측 1 — 첫 실호스트 실행이 오탐을 냈다. 전역 규칙의 `grep -v pgrep` 을 일반화한 것이고 양방향으로 테스트했다 |

**게이트.** `tos_firewall_check.py` PASS · size budget PASS(0 violations, `tools/` 는 애초에 범위 밖) ·
contract PASS · completion GREEN · spec PASS · `ruff check` 통과 · `black --check` 통과 ·
`mypy tools/tos_evidence_scan_measure.py --ignore-missing-imports` 클린 ·
`mypy tests/… --disable-error-code=no-untyped-def`(CI 의 테스트 트리 형태) 클린.
⚠ `lint-imports` 는 **로컬에서 돌지 않았다** — 배포 호스트 루트 `.venv` 에 `tos_runtime` 이 editable
설치돼 있지 않고(`Could not find package 'tos_runtime'`), 공유 루트 venv 에 설치하지 않는 규율이
있다. CI 의 `tos-firewall` 잡이 설치 후 돌린다. 이 PR 은 import 를 하나도 추가하지 않는다.

**365 일치 재실행 명령 (이 PR 에서 돌리지 않았다).** 호스트에 다른 프로젝트의 Gradle 빌드가 도는
동안에는 이 드라이버가 **스스로 거부한다** — 그것이 의도된 동작이다. 빌드가 끝난 뒤:

```bash
cd <repo>
.venv/bin/python tools/tos_evidence_scan_measure.py run \
  --reference ~/.local/state/tos/realclock-20260928T110001-LONG/data/evidence.sqlite3 \
  --synthetic ~/.local/state/tos/measure/synth/synth-365d.sqlite3 \
  --out-dir   ~/.local/state/tos/measure/a1b \
  --days 365 --repeats 3
```

문턱은 전부 기본값(착수 6 GB / 2 GB · 진행 중 4 GB / 1 GB · 5 초 표본)이라 평시에는 아무 플래그도
필요 없다. 착수 전에 먼저 보고 싶으면 같은 인자로 `run` 대신 `preflight` 를 쓰면 자식을 하나도
띄우지 않고 판정만 낸다. 30·90 일치는 `--days` 만 바꾼다. 합성 파일은 쌍 측정이 끝나면 기본으로
지워진다(피크 디스크 = 한 파일) — 남기려면 `--keep-synthetic`.

⚠ 운영자 면제(§7.1.7 편차 11 의 「co-tenant 조건 해제」)를 **다시** 쓰려면 이 드라이버에는 그런
플래그가 없다. 그때는 면제를 편차로 등재하고 `--min-available-gb`/`--min-swap-free-gb` 를 명시적으로
낮춰야 하며, 그 값은 `preflight.json` 의 `thresholds` 에 그대로 남는다 — 지난번처럼 기록 없이
빠지지 않는다.

#### 7.1.10 독립 리뷰 #826 처분 (2026-10-01)

리뷰 레인은 **저자와 다른 패스**였다. 교차모델 독립성은 **없다**(§7.1.6 과 같은 상태 — Codex
심사는 붙이지 않았다). 그 사실을 판정의 일부로 적는다. 판정 **needs-attention**, 지적 10 건,
**전건 수정**(기각 0).

| # | 지적 | 조치 |
|---|---|---|
| F1 | **실패한 자식이 「완료된 단계」였다.** `main()` 이 `StepResult.returncode` 를 안 봐서, `build` 가 1 로 죽어도 `before`/`after` 가 없는 DB 에 대고 돌고, 셋 다 완료로 집계돼 합성 파일이 지워지고 **종료코드 0** 이 나왔다 | `MeasureStepFailed` — 즉시 중단 · 파일 보존 · rc≠0. 테스트 2건(기존 `--synthetic` 으로 `build` 실패 · `--repeats 0` 으로 `before` 실패) |
| F2 | **실행 중 예외가 아티팩트 없이 자식을 죽였다.** 일시적 `pgrep` 2/3 이나 읽을 수 없는 `/proc` → `MeasureRefused` → `BaseException` 경로가 자식을 죽이고 「Nothing was started」 뜻의 예외로 종료 | (a) 호스트 읽기 실패는 `--host-read-retries`(기본 1) 재시도 후 `check="host_read"` 정식 중단 (b) 예상 못 한 예외는 `check="driver_error"` 로 **아티팩트를 쓴 뒤** 재-raise |
| F3 | **이 파일을 열기만 해도 「경쟁 측정」.** 패턴이 파일명 부분문자열이라 `pytest …test_tos_evidence_scan_measure.py` · `mypy` · `vim` · `git show` 가 전부 매치 — 장시간 측정 중 이 도구를 고치면 측정이 죽는다 | 패턴을 **호출 형태**로 좁히고(`…\.py +(run\|preflight\|build\|measure\|profile)\b`), 출력 디렉터리에 **락 파일**을 추가. 주인이 사라진 락은 stale 로 무시(SIGKILL 당한 런이 다음을 영영 막지 않게) |
| F4 | **문서화한 재개가 실제로는 막혔다.** 중단 로그가 `--steps before,after` 를 권하는데 `artifacts_absent` 가 그 중단이 만든 `.out`/`.err` 때문에 거부 | 중단 시 그 둘을 `<step>-Nd.<run_id>.aborted.{out,err}` 로 **옮긴다**(삭제 아님). 테스트가 중단 뒤 **권고된 명령 그대로** 돌려 rc=0 확인 |
| F5 | **재개가 자기 빌드가 쓴 공간을 또 요구.** 60 GB 디스크에 53 GB 를 쓴 뒤 재개가 66 GB 를 요구받아 거부 | `build` 가 계획에 없고 파일이 있으면 새 바이트는 인덱스뿐 — `--index-growth-ratio`(§7.1.2 실측 +1.8 %). 덤으로 `build` 없이 파일도 없으면 **선행 거부** |
| F6 | **벽시계가 표본 주기만큼 부풀었다.** `wait4` 를 5 s 주기로만 폴링해 8.0 s 단계가 10.0 s · CPU 80 % 로 찍힘 — §7.1.2 가 인용하는 GNU `time -v` 수치와 비교 불가 | 두 주기로 분리: `--poll-interval-s`(0.1 s)로 거두고 호스트는 `--watch-interval-s` 로 표본 |
| F7 | **이미 끝난 자식에 대한 중단.** 표본과 종료가 겹치면 완결된 `<step>-Nd.json` 옆에 `ABORTED` 가 생겨 다음 재개가 막힌다 · `AbortRecord.returncode` 가 raw wait status(256)를 적었다 | 위반 발견 시 **자식을 먼저 재확인** — 이미 끝났으면 성공으로 마무리. 종료코드 변환을 `_returncode()` 하나로 통일 |
| F8 | **스왑 없는 호스트에서 안내가 틀렸다.** 도움말은 `--min-swap-free-gb 0` 으로 빠지라는데 기본 중단 문턱 1.0 이 거부 — 타본 적 없는 플래그를 대며 | 지정 안 한 중단 문턱은 `min(기본, 착수 문턱)` 으로 **유도**하고 `preflight.json` warnings 에 기록. **명시한** 값이 착수 문턱보다 높은 것은 여전히 모순이므로 거부 |
| F9 | **셸 문법에 붙은 검색 명령을 못 알아봤다** — `$(pgrep`, `;pgrep`, `\|grep` | 셸 구두점으로도 분리. 양방향 테스트(`/opt/grepbuild/gradlew` 는 여전히 빌드) |
| F10 | §7.1.9 커밋 표가 브랜치와 어긋났다 | 위 표 전면 갱신 + 왜 사소하지 않은지 한 줄 |

**F3 에 대해 한 가지 더.** 패턴과 락은 **다른 질문에 답하므로 둘 다** 둔다 — 패턴은 같은
호스트에서 다른 디렉터리에 쓰는 드라이버를 보고, 락은 이 출력 디렉터리를 정말 누가 잡았는지를
오탐 0 으로 말한다. 락만 두면 다른 out-dir 의 동시 실행을 놓치고, 패턴만 두면 F3 의 오탐 계열이
영원히 남는다.

**부수 개선.** `PreflightCheck` 가 `measured_bytes`/`floor_bytes` 를 들어, `preflight.json` 을
「12.00 GB」 문자열 재파싱이 아니라 숫자로 인용할 수 있다.

**테스트.** 두 파일 **66 passed**(measure 48 + bench 18). 이 라운드의 **레드 증명 13 건 추가,
초록으로 남은 가드 0** — 누적 **29/29**. F7 의 경쟁 테스트는 마커 파일 대신 커널의 좀비 상태
(`/proc/<pid>/stat` 의 `Z`)를 기다린다: 「다 했다」를 파일에 쓰는 것과 실제로 종료하는 것은 서로
다른 순간이라, 마커로는 「이미 끝났다」를 표현할 수 없고 초판 테스트가 실제로 깜빡였다.

| 무력화한 가드 | red 가 된 테스트 |
|---|---|
| F1 실패 단계 중단 | `test_f1_a_failed_step_stops_the_run_keeps_the_file_and_exits_non_zero` · `test_f1_a_failed_step_keeps_a_synthetic_this_run_did_create` |
| F2 호스트 읽기 재시도 후 중단 | `test_f2_a_host_read_failure_is_retried_once_then_aborts_with_an_artifact` |
| F2 드라이버 오류도 아티팩트 | `test_f2_an_unexpected_driver_error_still_writes_an_abort_artifact` |
| F3 호출 형태 패턴 | `test_f3_editing_or_testing_this_tool_is_not_a_competing_measurement` · `test_f3_the_pattern_matches_a_real_invocation_through_the_real_pgrep` |
| F9 셸 구두점 토큰화 | `test_f9_a_search_command_glued_to_shell_syntax_is_still_a_search` |
| F4 중단 산출물 이동 | `test_f4_the_documented_resume_command_actually_gets_past_preflight` |
| F5 계획된 단계 기준 디스크 | `test_f5_a_resume_is_not_asked_for_the_space_its_build_already_spent` |
| F5 합성 파일 없는 measure-only 거부 | `test_f5_measure_only_without_a_synthetic_file_is_refused_up_front` |
| F6 두 주기 | `test_f6_wall_clock_is_not_rounded_up_to_the_host_sample_interval` |
| F7 종료 재확인 | `test_f7_a_breach_that_coincides_with_the_child_exiting_is_not_an_abort` |
| F7 종료코드 변환 | `test_f7_an_abort_records_the_exit_code_the_way_a_step_result_does` |
| F8 중단 문턱 유도 | `test_f8_lowering_the_start_floor_lowers_the_in_run_floor_with_it` · `test_f8_a_swapless_host_runs_end_to_end_with_one_flag` |
| 출력 디렉터리 락 | `test_the_output_directory_lock_refuses_a_second_run_and_survives_a_kill` |

**365 일치 재실행 명령은 §7.1.9 의 것 그대로다** — 새 플래그는 전부 기본값이 있고, 기본값은
이 라운드에서 바뀌지 않았다. 달라진 것은 그 명령이 **중간에 멈췄을 때**다: 실패한 단계가 rc≠0
로 보고되고, 중단이 산출물을 남기며, 로그가 권하는 재개가 실제로 돈다.

#### 7.1.11 독립 리뷰 #826 2회차 처분 (2026-10-01)

1회차와 같은 조건 — 저자와 **다른 패스**, 교차모델 독립성 **없음**. 판정
**needs-attention**, 지적 10 건, **전건 수정**(기각 0). 둘(F2 · F7)은 리뷰어가 브랜치
코드로 **실행해서** 확인한 것이라 가설이 아니다.

| # | 지적 | 조치 |
|---|---|---|
| F1 | **SIGTERM 이 자식을 고아로 남겼다.** 핸들러가 없어 드라이버에 SIGTERM/SIGHUP 이 닿으면 인터프리터가 즉시 끝나고 중단 경로가 아예 안 돈다 — tmux 창을 닫거나 `timeout`·`kill`·earlyoom 이 **드라이버를** 고르면 53 GB 를 쓰던 자식이 **워치독 없이 계속 돌고** 락은 stale, 아티팩트는 0 | 두 신호를 `MeasureSignalled` 로 올려 같은 중단 경로를 타게 하고 `check="driver_signalled"` 로 기록. 테스트가 실제 하위 프로세스에 SIGTERM 을 보내 **자식이 죽었는지**와 아티팩트·락 해제를 확인 |
| F2 | **테스트 스위트가 실행 중인 측정을 죽일 수 있었다**(실행 확인). 1회차에서 좁힌 패턴이 스위트가 실제로 띄우는 `bench build\|measure` 자식과 읽기 전용 `profile` 까지 맞혔다 | 패턴에서 `profile`·`preflight` 제거(둘 다 경합하지 않는다) · **자기 자손 제외** · **pytest 자손 제외** |
| F3 | 기존 `--synthetic` 위의 build 를 프리플라이트가 통과시켰다 — 벤치가 반드시 거부하므로 **1단계 실패가 확정**인데, 네 아티팩트를 남겨 재시도까지 막았다 | `synthetic_absent` 검사. 여기서 거부하면 비용 0 |
| F4 | `--no-watchdog` 인데 in-run kill 이 하나 남아 있었다 — 호스트 읽기 2연속 실패가 「가드가 눈이 멀었다」며 자식을 죽였다, **끈 가드를 근거로** | 기록만 하고 `fatal: false` 를 함께 남긴다 |
| F5 | **실패한 단계의 수치가 조용히 덮였다.** `artifacts_absent` 는 `.out/.err/.json` 만 보는데 실패 단계는 이미 `.time`·`.resource.json` 을 썼다 | 다섯 파일을 `step_artifact_paths()` 한 곳에 모으고, 실패 시에도 중단과 똑같이 전부 옆으로 옮긴다 |
| F6 | 리더 실패(`meminfo` 필드 결손 · `pgrep` 비정상 종료)가 **`preflight.json` 을 쓰기 전에** 터져, 「아티팩트 없는 거부」가 그대로 재현됐다 — 그 기록이 막으려던 바로 그것 | 실패한 **검사**로 적고 기록을 쓴다 |
| F7 | **경로 끝이 `rg`/`grep` 인 빌드가 숨었다**(실행 확인). 모든 토큰에 basename 을 적용해 `-Dorg.gradle.appname=/home/u/rg` 가 명령 `rg` 로 읽혔다 | **명령 자리**의 토큰만 분류 — 첫 토큰 · 셸 구분자 뒤 · 셸의 `-c` 뒤. `VAR=value` 와 `eval`/`if`/`!`/`sudo` 접두어는 건너뛴다(그래야 F9 사례를 여전히 잡는다) |
| F8 | 재개가 중단된 런의 로그를 통째로 덮었다 — ABORT 줄과 처분 메시지가 사라진다 | run_id 헤더를 달고 **append** |
| F9 | 매 표본마다 pgrep 2회 + 조상 체인 2회 재구성(6시간이면 ~4,300 표본) | 자기 체인 1회 캐시 · 두 패턴을 **하나의 pgrep** 으로 |
| F10 | 추정(참조 전체 `GROUP BY`)이 메모리 검사보다 **먼저**, 쓰지도 않는 measure-only 에서도 돌았다 | 지연 호출로 바꿔 **build 가 계획에 있고 앞선 검사가 통과했을 때만**. `--reference` 는 measure-only 에서 선택 |

**건너뛴 검사는 통과가 아니다.** F10 때문에 디스크 검사가 「평가 안 함」이 될 수 있어
`PreflightCheck.evaluated` 를 추가했다. 그 값은 **이미 다른 이유로 거부된 런에서만**
False 가 되고, 거부 사유 목록에서는 빠지되 기록에는 남는다. 건강한 호스트에서 전 검사가
evaluated 임을 테스트가 고정한다 — 그러지 않으면 「건너뜀」이 조용한 통과가 된다.

**⚠ 레드 증명 초안에서 3건이 초록이었다.** 이 라운드의 교훈이라 그대로 적는다.

- **자손 제외와 pytest 제외가 서로를 덮고 있었다.** pytest 아래에서는 자기 자손이 곧
  pytest 자손이라, 둘 중 **어느 쪽을 꺼도 스위트가 초록**이었다 — 둘 다 「무엇의 이유도
  아닌 가드」. 가짜 `/proc` 트리를 만들어 규칙을 분리했다(pid 200 이 드라이버, 201 이 그
  자식, 300 이 무관한 두 번째 런).
- **실행 확인된 F7 사례의 음성 테스트가 아예 없었다.** 기존 F9 테스트는 옛 토크나이저로도
  통과하므로 F7 수정을 전혀 지키지 않았다. 두 사례를 음성으로 추가했다.

이것이 `MEMORY.md` 의 반복 결함 형태(「가드가 자기가 막는다고 말한 것을 허용한다」)가
**가드가 아니라 가드의 증명**에서 나타난 경우다. 레드 증명을 돌리지 않았다면 「지적 10건
수정」이라고 적고 셋은 사실이 아니었을 것이다.

**테스트.** 두 파일 **81 passed**(measure 63 + bench 18) · `tests/tools/test_tos_*.py`
전체 배터리 green. **레드 증명 이 라운드 14 건, 초록으로 남은 가드 0 — 누적 43/43.**

| 무력화한 가드 | red 가 된 테스트 |
|---|---|
| F1 SIGTERM/SIGHUP 핸들러 | `test_r2_f1_sigterm_to_the_driver_kills_the_child_and_leaves_an_artifact` |
| F2 pytest 자손 제외 | `test_f2_a_process_descended_from_another_pytest_is_excluded` |
| F2 자기 자손 제외(`scan` 호출부) | `test_f2_the_descendant_rule_is_live_in_scan_not_just_available` |
| F2 패턴에서 `profile`/`preflight` 제거 | `test_f3_a_real_second_driver_invocation_is_still_caught` · `test_f3_the_pattern_matches_a_real_invocation_through_the_real_pgrep` |
| F3 `synthetic_absent` | `test_r2_f3_a_build_onto_an_existing_synthetic_is_refused_before_anything_runs` |
| F4 no-watchdog 비치명 | `test_r2_f4_with_the_watchdog_off_a_host_read_failure_is_recorded_not_fatal` |
| F5 다섯 파일 한 목록 | `test_r2_f5_a_failed_step_cannot_have_its_resource_numbers_overwritten` |
| F6 리더 실패도 기록 | `test_r2_f6_a_reader_failure_still_writes_the_preflight_record` |
| F7 명령 자리 토크나이저 | `test_a_process_merely_searching_for_the_marker_is_not_a_competing_build` |
| F7 명령 자리만 분류 | `test_r2_f7_a_build_whose_paths_end_in_a_search_command_name_is_not_hidden` |
| F8 로그 append | `test_r2_f8_the_run_log_is_appended_not_replaced` |
| F10 추정 지연·조건부 | `test_r2_f10_the_reference_is_not_scanned_when_the_host_already_failed` |
| F10 measure-only 에 `--reference` 불필요 | `test_r2_f10_a_measure_only_resume_needs_no_reference_at_all` |
| `evaluated=False` 는 통과가 아니다 | `test_r2_f10_the_reference_is_not_scanned_when_the_host_already_failed` |

**365 일치 재실행 명령은 §7.1.9 의 것 그대로다.** 새 인자(`--poll-interval-s` ·
`--host-read-retries` · `--index-growth-ratio`)는 전부 기본값이 있다. 이 라운드가 바꾼 것은
**그 명령이 잘못될 때**다: 창을 닫아도 자식이 남지 않고, 동료가 테스트를 돌려도 측정이
죽지 않으며, 재개가 앞선 런의 로그와 수치를 덮지 않고, 측정 전용 재개에는 `--reference`
조차 필요 없다.

#### 7.1.12 A1 365일 재측정 (2026-10-01, 드라이버 PR #826)

§7.1.7 편차 10(「365 일치 전·후 표 미측정」)을 닫는다. §7.1.9 가 적어 둔 재실행 명령을
**글자 그대로** 돌렸고, 이번에는 드라이버가 모든 단계의 자원 수치와 호스트 시계열을
아티팩트로 남겼다. 아티팩트 디렉터리는 `~/.local/state/tos/measure/a1b/` 이고, 아래 모든
수치는 그 안의 파일·필드로 환원된다(인용 형식: `(아티팩트: <파일> · <필드>)`).
합성 파일은 설계대로 측정이 끝난 직후 드라이버가 지웠다(`measure-365d.log` 마지막 줄
`removed synthetic …`) — 저장소에는 아무것도 복사하지 않는다.

**⚠ §7.1.2 의 유보는 그대로다.** 합성 이력의 체인은 유효하지 않고(행을 참조 파일에서
복사하므로 `chain_digest` 반복), 재는 것은 스캔 비용뿐이다. OS 페이지 캐시도 비우지
않았다(root 없이 불가). 판정은 「paper 합성 경로 기준」이다.

**측정 조건**

| 항목 | 값 | 출처 |
|---|---|---|
| 호스트 | 이 WSL 배포 호스트(`SwapTotal` 8.00 GiB) | `preflight.json` · `checks[swap_free].detail` |
| run id | `8960731fcc6b` | `preflight.json` · `run_id` |
| 착수 | 2026-10-01T10:49:51.221+09:00 | `preflight.json` · `at_kst` |
| 종료 | 2026-10-01T15:06:09.112+09:00 (`after` 자식 종료) | `after-365d.resource.json` · `finished_at_kst` |
| 전체 벽시계 | 15,377.8 s = **4 h 16 m 17.8 s** (build 412.06 + before 14,064.80 + after 900.89) | 세 `*.resource.json` · `wall_seconds` 합 |
| 도구 | `tools/tos_evidence_scan_measure.py` 가 `tools/tos_evidence_scan_bench.py` 를 자식으로 | `preflight.json` · `tool` · 각 `*.resource.json` · `argv` |

명령은 `preflight.json` 의 `argv` 그대로다 — §7.1.9 가 등재한 재실행 명령과 플래그가 같고,
문턱은 전부 기본값이다(`preflight.json` · `thresholds`: 착수 6/2 GiB · 중단 4/1 GiB ·
표본 5 s · `disk_headroom_ratio` 1.25 · `index_growth_ratio` 0.018).

```
run --reference /home/deploy/.local/state/tos/realclock-20260928T110001-LONG/data/evidence.sqlite3
    --synthetic /home/deploy/.local/state/tos/measure/synth/synth-365d.sqlite3
    --out-dir   /home/deploy/.local/state/tos/measure/a1b
    --days 365 --repeats 3
```

**⚠ 분기점 SHA 는 아티팩트가 아니다 — 외부에서 확인했다.** 드라이버는 argv·문턱·호스트는
적지만 **저장소 커밋을 적지 않는다**. 공용 체크아웃(`/home/deploy/project/kis_unified_sts`)의
reflog 로 확인한 결과: 10:49:13 KST 에 main `32539e07`(PR #826 머지)로 fast-forward 했고,
**측정 도중인 13:07:39 KST 에 `f23bb4c3` 로 또 fast-forward 했다.** 즉 `before` 자식은
`32539e07` 의 소스로, `after` 자식(14:51:08 기동)은 `f23bb4c3` 의 소스로 떴다. 두 도구가
그 구간에서 **한 바이트도 바뀌지 않았음**을 확인했으므로 측정에는 영향이 없다:

```
git diff --stat 32539e07 f23bb4c3 -- tools/tos_evidence_scan_bench.py \
                                      tools/tos_evidence_scan_measure.py   # 출력 없음
```

`MEMORY.md` 의 「프로브는 분리 워크트리에서만」(#793 HIGH)이 겨냥한 상황이 그대로 재현됐다 —
공용 체크아웃에서 돌리면 옆 레인이 측정 **도중에** 트리를 바꾼다. 이번에는 무해했지만
그것은 사후 확인의 결과이지 설계된 보호가 아니다.

**프리플라이트 — 7 검사 전부 ok**(`preflight.json` · `verdict: "ok"` · `warnings: []`).
⚠ 드라이버의 사람용 문자열은 `_GB = 1024**3`(GiB)인데 라벨이 `GB` 다. 이 계획 본문은
십진 GB 를 쓰므로(53.226 GB = 53,225,779,200 B) 아래는 **바이트**를 같이 적는다.

| 검사 | 로그 문자열 | 바이트 | 문턱 |
|---|---|---:|---|
| `mem_available` | `14.31 GB` | 15,361,388,544 | 6.00 GiB |
| `swap_free` | `4.33 GB` | 4,647,964,672 | 2.00 GiB |
| `competing_build` | `none` | — | 없을 것 |
| `competing_measurement` | `none` | — | 없을 것 |
| `disk_free` | `341.20 GB free` / `63.33 GB needed` | 366,358,962,176 / 68,002,380,330 | 예측×1.25 |
| `artifacts_absent` | `none present` | — | 기존 산출물 없을 것 |
| `output_dir_unlocked` | `no live lock` | — | 다른 런이 안 잡고 있을 것 |

**워치독 — 표본 3,054 건, 위반 0.**

| 값 | 결과 | 출처 |
|---|---|---|
| 표본 수 | 3,054 (build 82 · before 2,793 · after 179) | `watchdog.jsonl` 행 수 |
| 최소 `MemAvailable` | **13.668 GiB** (14:05:03.786, `before`) | `watchdog.jsonl` · `mem_available_gb` 최소 |
| 최소 `SwapFree` | **3.002 GiB** (14:45:12.180, `before`) | 같은 파일 · `swap_free_gb` 최소 |
| 착수 문턱(6/2 GiB) 위반 | **0 건** | 위 두 값이 전 구간 문턱 위 |
| 중단 문턱(4/1 GiB) 위반 | **0 건** | 같음 |
| `competing` 비어 있지 않은 표본 | **0 건** | `watchdog.jsonl` · `competing` |

**⚠ co-tenant 에 대해 아티팩트가 말할 수 있는 것과 없는 것.** 워치독이 기록한 경합은
**0 건**이지만, 그 패턴은 Gradle 과 **다른 측정 드라이버**만 본다 — 2회차 리뷰 F2 가
pytest 자손과 벤치의 `profile`/`preflight` 를 **의도적으로 제외**했기 때문이다(§7.1.11).
그러므로 「다른 레인이 이 호스트에서 pytest 를 돌렸다」는 운영자·세션 보고는
**이 아티팩트로 확인되지도 반증되지도 않는다** — §7.1.2 가 「이웃 빌드가 돌았다」를
세션 기록으로 강등한 것과 같은 지위다. 아티팩트가 실제로 말하는 것은 메모리 여유뿐이고,
그것은 전 구간 13.67 GiB 아래로 내려간 적이 없다.

**build — 2026-09-30 과 바이트 단위로 같은 파일**

| 값 | 2026-10-01 | 2026-09-30(§7.1.2) | 출처 |
|---|---:|---:|---|
| 행 | 28,703,600 | 28,703,600 | `build-365d.json` · `rows` |
| 파일 | 53,225,779,200 B = **53.226 GB** | 53,225,779,200 B | `build-365d.json` · `file_bytes` |
| 벽시계 | **412.06 s** | 366 s | `build-365d.resource.json` · `wall_seconds` |
| 최대 RSS | **48.4 MiB** (50,778,112 B) | 48.8 MB | `build-365d.resource.json` · `max_rss_bytes` |
| 물리 쓰기 | 53,229,731,840 B | (미기록) | `build-365d.resource.json` · `proc_io.write_bytes` |
| 물리 읽기 | **0 B** (`fs_inputs_blocks` 0) | 0 blocks | 같은 파일 · `proc_io.read_bytes` |

행과 파일 바이트가 **정확히 일치**한다 — 빌드는 재현된다. 벽시계만 366 → 412 s (+12.6 %)
느려졌고 RSS 는 평평하다. 참조 파일은 캐시에 있어 디스크를 한 블록도 읽지 않았다.

**프리플라이트 예측 대비.** 예측 54,401,904,264 B(로그 문자열 `50.67 GB`, 즉 GiB) 대
실측 53,225,779,200 B → **+2.21 % 과대**(`preflight.json` · `estimate.predicted_file_bytes`).
행 예측 28,703,600 은 **정확 일치**. §7.1.9 가 30 일치에서 보고한 +2.2 % 와 같은 크기이고,
틀리는 방향도 그대로 **거부 쪽**(여유를 더 요구하는 쪽)이다.

**전 패스(인덱스 없음) — 3 h 54 m, 디스크에서 1.73 TB**

| 값 | 결과 | 출처 |
|---|---:|---|
| 벽시계 | **14,064.80 s** = 3 h 54 m 24.8 s | `before-365d.resource.json` · `wall_seconds` |
| 물리 읽기 | **1,729,740,062,720 B = 1,729.74 GB** | 같은 파일 · `proc_io.read_bytes` |
| 물리 읽기(교차 확인) | 3,380,758,680 × 512 B = 1,730.95 GB (0.07 % 차 — `/proc` 표본이 종료 3.4 s 전) | 같은 파일 · `fs_inputs_blocks` · `proc_io_sample_age_seconds` |
| 논리 읽기(`rchar`) | **1,810,388,987,303 B = 1,810.39 GB** | 같은 파일 · `proc_io.rchar` |
| 페이지 캐시가 덮은 양 | 1,810.39 − 1,729.74 = **80.65 GB (4.5 %)** | 위 두 값 |
| 최대 RSS | **25.1 MiB** (26,345,472 B) | 같은 파일 · `max_rss_bytes` |

**⚠ 패스 평균 처리량(논리 128.72 · 물리 122.98 MB/s)은 혼합값이다 — 이 패스는 두 모드로
갈라진다.** 아래는 추정이 아니라 **형태별 실측**이다.

**조인 방법(재현 가능).** `watchdog.jsonl` 은 5 s 마다 자식의 **누적** `child_io.read_bytes` ·
`rchar` 를 `elapsed_seconds` 와 함께 적는다(드라이버 PR #826 가 넣은 것 — §7.1.9 「물리 대 논리
읽기」). `before-365d.json` 각 레코드의 `seconds` 합을 순서대로 누적하면 형태 경계의 경과시각이
나오고, 그 시각에서 누적 `read_bytes` 를 선형보간해 차분하면 **형태별 물리 바이트**가 된다.
경계의 원점은 `wall_seconds` − Σ`seconds` = **126.3 s** 로, 벤치가 형태를 돌기 전에 하는
`validate_shape_kinds` 의 `GROUP BY` 전체 스캔 1 회(워치독상 ≈121 s · 53.4 GB)와 기동 시간이다.
형태별 물리 바이트의 합은 1,729.8 GB 로 `proc_io.read_bytes` 1,729.74 GB 와 **0.004 %** 차다 —
조인이 닫힌다는 뜻이다. 경계를 ±5 s 움직여도 100 s 이상 걸리는 형태에서는 0.5 % 미만으로 변한다.

| 구간(실행 순서) | 벽시계 | 물리 GB | 논리 GB | 캐시가 덮은 GB | **물리 MB/s** |
|---|---:|---:|---:|---:|---:|
| `validate_shape_kinds` `GROUP BY` + 기동 | 126.3 | 53.85 | 55.37 | 1.52 | 426.4 |
| `by_kind_payload_asc__hot` ×3 | 434.7 | 159.74 | 159.74 | 0.00 | 367.5 |
| `by_kind_payload_asc__warm` ×3 | 389.7 | 159.67 | 159.67 | 0.00 | 409.8 |
| `by_kind_payload_unordered__absent` ×3 | 359.1 | 159.35 | 160.35 | 1.00 | 443.8 |
| **`by_kind_payload_desc__warm` ×3** | **5,374.6** | 142.58 | 161.47 | **18.89** | **26.5** |
| `by_kinds_in_payload_asc` ×3 | 351.4 | 142.55 | 158.99 | 16.44 | 405.6 |
| **`by_kinds_in_payload_desc` ×3** | **5,228.5** | 139.00 | 159.98 | **20.98** | **26.6** |
| `exists_by_kind` ×3 | 330.4 | 145.57 | 157.56 | 11.99 | 440.6 |
| `exists_by_kinds_after_seq` ×3 | 357.5 | 154.74 | 159.69 | 4.95 | 432.8 |
| `count_by_kind__hot` ×3 | 360.1 | 156.84 | 159.68 | 2.84 | 435.5 |
| `count_by_kind__absent` ×3 | 356.3 | 158.25 | 159.57 | 1.32 | 444.2 |
| sub-ms 형태 4 개 ×3 | ≈0 | ≈0 | ≈0 | — | — |
| `full_scan_chain_control` ×3 | 396.1 | 157.60 | 158.32 | 0.72 | 397.9 |

| 국면 | 스캔 | 벽시계 | 물리 GB | 캐시 GB | **물리 MB/s** | **논리 MB/s** |
|---|---:|---:|---:|---:|---:|---:|
| **정방향**(ASC · 무정렬 · `GROUP BY`) | 28 | 3,461.6 s (24.6 %) | 1,448.2 | 40.8 | **418.3** | **430.5** |
| **역방향**(`ORDER BY seq DESC` 두 형태 ×3) | 6 | **10,603.2 s (75.4 %)** | 281.6 | 39.9 | **26.6** | **30.1** |

바이트로는 역방향이 전체의 17.6 % 인데 **벽시계로는 75.4 %** 다. 형태별 물리 처리량은
정방향 **367.5–444.2 MB/s**, 역방향 **26.5 / 26.6 MB/s** — 같은 파일·같은 호스트에서
**16 배** 갈린다. 캐시가 덮은 80.65 GB 중 **가장 큰 두 몫(18.89 · 20.98 GB)이 역방향 두 형태**
이고, 그 직후 형태(`by_kinds_in_payload_asc` 16.44 · `exists_by_kind` 11.99)가 그다음이다.
그럴듯한 설명은 있지만 **아티팩트가 원인을 가리지는 않는다** — 분포만 적는다.

**모델 확인 — 전 패스는 맞았고, 후 패스는 애초에 예측이 아니라 하한이었다.**
§7.1.2 는 90 일치 논리량을 「전체 스캔 형태 11 개 × 3 회 + `GROUP BY` 1 회」로 **세어** 내고
그것을 **모델값**으로 라벨했다. 같은 셈을 365 일치 전 패스에 적용하면
(11 × 3 + 1) × 53,225,779,200 = **1,809,676,492,800 B** 이고 실측 `rchar` 는
1,810,388,987,303 B 다 — **차 0.04 %. 전 패스 모델은 확인됐다.**
후 패스는 다르다. §7.1.2 가 적은 것은 「**최소** 6 회 × 53.226 GB = 319 GB」라는 **하한**이고,
실측은 364.83 GB = **6.85 파일분**이다. 하한은 지켜졌지만(6.85 ≥ 6) 예측이 아니었으므로
**확인됐다고 말할 수 없다.** 두 항을 더하면(1,809.68 + 319.35 = **2,129.03 GB** 대 실측
2,175.22 GB, **2.1 %** 차) **0.04 % 로 맞은 항과 하한인 항이 섞여** 후 패스까지 확인된 것처럼
읽힌다 — 그래서 결론으로 쓰지 않는다. 남는 0.85 파일분은 인덱스 생성이 테이블을 한 번 읽는
몫과 인덱스 경유 임의 행 조회가 섞인 것이지만, 성분별 분해는 아티팩트에 없다.

**인덱스 생성과 후 패스**

**인덱스 생성 146.840 s**(`after-365d.out` 1행 — 벤치가 `measure --create-index` 안에서
만들고 그 시간을 stdout 에 적는다. 별도 단계가 없는 이유는 §7.1.9 에 있다).

| 일수 | 행 | 인덱스 생성 | 행당 | 출처 |
|---:|---:|---:|---:|---|
| 30 | 2,359,200 | 2.3 s | 0.98 µs | §7.1.2 표(⚠ `a1/` 에 `.out` 이 없어 이 둘은 아티팩트 미확인) |
| 90 | 7,077,600 | 7.4 s | 1.05 µs | 같음 |
| **365** | **28,703,600** | **146.840 s** | **5.12 µs** | `after-365d.out` 1행 |

행이 4.06 배일 때 생성 시간은 **19.8 배**다. 행당 비용이 1.05 → 5.12 µs 로 **4.9 배**.

| 값 | 결과 | 출처 |
|---|---:|---|
| 벽시계 | **900.89 s** = 15 m 0.9 s | `after-365d.resource.json` · `wall_seconds` |
| 물리 읽기 | 351,010,689,024 B = 351.01 GB | 같은 파일 · `proc_io.read_bytes` |
| 논리 읽기 | 364,831,515,585 B = 364.83 GB (= **6.85 파일분**) | 같은 파일 · `proc_io.rchar` |
| 물리 처리량 **(인덱스 생성 포함 분모)** | 351.01 GB ÷ 900.89 s = **389.63 MB/s** | 위 두 값 |
| 물리 처리량 **(인덱스 생성 146.84 s 제외 분모)** | 351.01 GB ÷ 754.05 s = **465.50 MB/s** | 위 · `after-365d.out` |
| 물리 쓰기 | 1,964,519,424 B = 1.96 GB | 같은 파일 · `proc_io.write_bytes` |
| 최대 RSS | **25.1 MiB** | 같은 파일 · `max_rss_bytes` |

두 분모를 모두 적는 이유는 389.63 이 「패스 처리량」, 465.50 이 「스캔 처리량」으로 서로 다른
질문의 답이기 때문이다(인덱스 생성이 읽은 바이트를 분자에서 뺄 수는 없어 465.50 도 상한이다).
전 패스의 정방향 국면 418.3 MB/s 와 같은 자릿수다 — 후 패스에는 역방향 전체 스캔이 없다.

RSS 는 §7.1.2 의 RSS 표에서 365 일치 `measure` 칸이 `(중단 — 아래)` 로 비어 있던 자리다.
전·후 모두 **25.1 MiB** 이고, 30·90 일치의 21.9–22.5 MB 와 같은 자릿수다 — 커서 스트리밍
구조(§7.1.5)가 28.7 M 행에서도 유지된다.

**전·후 (ms, 각 3 회 중 최소)**

`90일 전` 칸은 비교용으로 §7.1.2 와 같은 아티팩트(`a1/before-90d.json`)에서 가져왔다.
§7.1.2 의 표가 15 형태 중 11 개만 실었으므로 여기서는 **15 개 전부** 싣는다.
「부팅」 칸은 **벤치의 형태별 `boot_path` 플래그**다(§7.1.1 의 모듈 행 ✅ 와 다른 경우는
아래 「읽어야 할 것」 2 에서 따로 처분한다).

| 질의 형태 (`QUERY_SHAPES` 이름) | 부팅 | 행 | 90일 전 | 365일 전 | 365일 후 | 이득 | 질의계획(후) |
|---|:--:|---:|---:|---:|---:|---:|---|
| `by_kind_payload_asc__hot` | ✅ | 22,279,600 | 6,928.203 | 119,809.073 | 112,768.126 | **1.06 ×** | `SEARCH … USING INDEX entries_kind_seq` |
| `by_kind_payload_asc__warm` | ✅ | 1,839,600 | 4,073.999 | 119,629.744 | 1,349.983 | 88.6 × | `SEARCH … USING INDEX` |
| `by_kind_payload_unordered__absent` | ✅ | 0 | 6,658.108 | 114,295.348 | 0.060 | 1,904,478 × | `SEARCH … USING INDEX` |
| `by_kind_payload_desc__warm` | ❌ | 1,839,600 | 5,317.247 | **1,427,532.071** | 1,604.287 | 890 × | `SEARCH … USING INDEX` |
| `by_kinds_in_payload_asc` | ✅ | 0 | 4,635.281 | 110,712.368 | 0.115 | 965,083 × | `SEARCH … USING INDEX` + `TEMP B-TREE FOR ORDER BY` |
| `by_kinds_in_payload_desc` | ❌ | 0 | 5,649.409 | **1,519,459.622** | 0.069 | 21,896,755 × | `SEARCH … USING INDEX` + `TEMP B-TREE FOR ORDER BY` |
| `exists_by_kind` | ✅ | 0 | 5,070.354 | 105,877.789 | 0.065 | 1,625,538 × | `SEARCH … USING COVERING INDEX` |
| `exists_by_kinds_after_seq` | ✅ | 0 | 4,039.629 | 116,720.987 | 0.114 | 1,024,524 × | `SEARCH … USING COVERING INDEX (kind=? AND seq>?)` |
| `count_by_kind__hot` | ✅ | 1 | 3,972.906 | 117,047.280 | 827.475 | 141 × | `SEARCH … USING COVERING INDEX` |
| `count_by_kind__absent` | ✅ | 1 | 3,899.384 | 117,469.771 | 0.062 | 1,889,858 × | `SEARCH … USING COVERING INDEX` |
| `by_kind_and_seq` | ✅ | 0 | 0.055 | 0.065 | 0.059 | 1.09 × | `SEARCH … USING INTEGER PRIMARY KEY (rowid=?)` |
| `exists_seq_and_kind` | ✅ | 0 | 0.052 | 0.065 | 0.057 | 1.15 × | `SEARCH … USING INTEGER PRIMARY KEY (rowid=?)` |
| `tip_excluding_kinds` | ✅ | 1 | 0.105 | 0.106 | 0.069 | 1.53 × | `SCAN entries` |
| `tip_unfiltered` | ✅ | 1 | 0.058 | 0.110 | 0.059 | 1.86 × | `SCAN entries` |
| **대조군** `full_scan_chain_control` | ❌ | 28,703,600 | 7,958.561 | 131,099.217 | 129,725.740 | **1.01 ×** | `SCAN entries` (전·후 동일) |

(아티팩트: `before-365d.json` · `after-365d.json` · `a1/before-90d.json` — 각 레코드의
`best_seconds` × 1000 · `rows_returned` · `boot_path` · `plan`.) 반환 행 수는 전·후가 같다.

**잡음 바닥 — 대조군만으로는 모자라고, 이번에는 분산이 있다**

**대조군 드리프트 −1.05 %**(131,099.217 → 129,725.740 ms). 질의계획이 전·후 모두
`SCAN entries` 로 **바뀌지 않는** 형태가 1 % 안에서 움직였다 — 30·90 일치의 +39 % · +10 %
(§7.1.2)보다 훨씬 좁다.

**⚠ 그러나 대조군 하나로는 모자란다 — 형태마다 반복 폭이 다르다.** 전 패스 전체 스캔
11 형태의 `seconds` 배열을 전부 보면 **단조 증가 5 · 단조 감소 1 · 혼합 5** 로,
「패스가 진행되며 일관되게 느려졌다」는 일반화는 **성립하지 않는다**. 폭만이 사실이다:

| 형태 | 전 패스 3 회 (s) | 추세 | 폭 |
|---|---|---|---:|
| `full_scan_chain_control` | 132.242 · 132.766 · 131.099 | 혼합 | 1.3 % |
| `by_kind_payload_unordered__absent` | 126.369 · 118.430 · 114.295 | **감소** | −9.6 % |
| `by_kind_payload_asc__warm` | 146.827 · 119.630 · 123.211 | 혼합 | 22.7 % |
| `by_kind_payload_asc__hot` | 119.809 · 141.449 · **173.414** | 증가 | **+44.7 %** |
| `by_kind_payload_desc__warm` | 1,427.5 · 1,878.6 · **2,068.5** | 증가 | **+44.9 %** |
| `by_kinds_in_payload_desc` | 1,519.5 · 1,790.9 · **1,918.2** | 증가 | +26.2 % |

후 패스는 같은 형태가 좁다(`by_kind_payload_asc__hot` 115.496 · 113.148 · 112.768 = 2.4 %).
벤치가 **최소**를 남기므로 표의 「전」 칸은 전 패스의 가장 좋은 회차다.

따라서 **hot kind 전량 읽기의 −5.9 %(119,809 → 112,768 ms)는 그 폭 안에 들어간다** —
읽을 수 있는 것은 §7.1.2 와 같은 **「측정 가능한 변화 없음」**까지다. 저선택도 비커버링
인덱스의 교과서적 열화를 이 실행도 **확인하지 못했고 반증하지도 못했다.** 어느 쪽이든 A2 에
대한 반증이 아닌 이유도 그대로다 — `TIME_HEALTH_SNAPSHOT` 을 읽는 런타임 모듈은 0 이고,
이 형태는 상한을 박는 프로브이지 어떤 모듈도 내지 않는 질의다.

**⚠ §7.1.2 의 한 문장을 정정했다.** §7.1.2 는 「벤치는 3 회 중 최소만 남기고 분산을 남기지
않으므로 더 좁힐 근거가 없다」고 적었는데 **사실이 아니다** — 모든 `*-Nd.json` 이
`best_seconds` 옆에 3 회 전부를 `seconds` 배열로 들고 있고 `a1/` 도 그렇다. 그 분산으로 다시
읽어도 §7.1.2 의 결론(hot kind 「측정 가능한 변화 없음」)은 **그대로 선다**: 90 일치 hot 은
전 `[14.893, 8.162, 6.928]` s · 후 `[8.980, 10.805, 7.703]` s 로 두 구간이 **겹친다**.
§7.1.2 본문에는 한 줄 포인터만 남기고 논증은 여기에만 둔다(같은 숫자를 두 곳에 두면 한쪽을
고칠 때 다른 쪽이 조용히 어긋난다 — 이 PR 이 고치고 있는 바로 그 결함 형태다).

**⚠ 새 관측 — 53 GB 에서 역방향 전체 스캔이 정방향의 12–14 배다**

위 국면 분해가 그것이다. 같은 일을 하는 정방향·역방향 쌍으로 보면:

| 쌍 | 90일 전 | 365일 전 |
|---|---:|---:|
| `by_kind_payload_desc__warm` ÷ `by_kind_payload_asc__warm` | 1.31 × | **11.93 ×** |
| `by_kinds_in_payload_desc` ÷ `by_kinds_in_payload_asc` | 1.22 × | **13.72 ×** |

`by_kinds_in_payload_desc` 는 **0 행을 돌려주면서** 1,519 s 가 걸렸다 — 정렬할 것이 없으므로
정렬 비용이 아니고, 전체를 역순으로 훑는 비용이다. 90 일치에서 1.2–1.3 배였던 것이 365 일치에서
12–14 배가 됐다. 그럴듯한 설명(순차 readahead 가 역방향 접근에 듣지 않는다)은 있지만
**이 아티팩트는 원인을 가리지 못한다** — 관측만 적는다. 실무적 함의는 작다: 두 형태의 리더는
`posttrade/release_consumer.py`(§7.1.1 「배선은 부팅, 질의는 체결 후」)이고 벤치도 `boot_path=False`
로 표시한다. 그리고 인덱스 뒤에는 1.6 s / 0.069 ms 로 사라진다.

**읽어야 할 것**

**1. 「파일이 RAM 을 넘으면 처리량이 무너지는가」 — 질의 형태에 따라 다르고, 두 점으로는 못 정한다.**

이 실행이 그 구간이다: 파일 53.226 GB 대 착수 시 `MemAvailable` 15.36 GB(=14.31 GiB), 약 3.5 배.
그러나 「무너졌다/아니다」를 패스 하나의 평균으로 말할 수 없다는 것이 이 측정의 첫 결과다.

**비교는 논리 축에서 한다.** §7.1.2 의 90 일치 물리 79.6 MB/s 는 **장치 대역폭이 아니라
디스크에서 **얼마나 적게** 읽었는지에 묶인 값**이다(패스 238.6 s 동안 물리 19.0 GB · 캐시 적중
≈95 %). 적중률이 95 % 인 패스와 4.5 % 인 패스의 **물리** 수치를 나란히 놓고 「장치가 빨라졌다/
느려졌다」로 읽으면 안 된다. 두 실행에서 같은 뜻을 갖는 축은 **논리 처리량**이다:

| 축 | 90일치 | 365일치 정방향 | 365일치 역방향 |
|---|---:|---:|---:|
| **논리 처리량** | 1,815 MB/s (**모델값**) | **430.5 MB/s** (실측) | **30.1 MB/s** (실측) |
| 1,815 대비 | — | **4.2 ×** 느려짐 | **60 ×** 느려짐 |
| (참고) 물리 처리량 | 79.6 MB/s — 캐시 95 % 에 묶인 값 | 418.3 MB/s | 26.6 MB/s |
| 페이지 캐시 적중률 | ≈95 %(분모가 모델값) | — | — |

패스 전체로는 적중률이 **95.6 %(90 일) → 4.5 %(365 일)** 로 소진됐고, 그래서 정방향조차
1,815 → 430.5 MB/s(4.2 배)로 내려간다. 역방향은 거기에 더해 접근 패턴 비용이 얹혀 30.1 MB/s 다.

**⚠ 「절벽이냐 소진이냐」는 이 데이터로 정해지지 않는다.** 가진 점은 셋뿐이고
(30 일 4.37 GB · 90 일 13.12 GB 적중률 ≈95 % · 365 일 53.23 GB 적중률 4.5 %), 13–53 GB
**사이에 점이 없다.** 적중률이 95 % → 4.5 % 로 가는 과정이 완만한 소진인지 그 구간 어딘가의
계단인지, 두 점은 구분하지 못한다. 초판은 여기서 「절벽이 아니라 소진」이라고 **단정했는데
철회한다** — 그것은 §7.1.2 가 「넘는 **순간** 무너진다」를 단정했던 것과 **같은 종류의
과잉 독해**다. 이 데이터가 지지하는 것은 「90 일에서 365 일 사이에 캐시가 소진되고 실효
처리량이 떨어진다」까지이고, **그 사이 모양은 미측정**이다. 그것을 정하려면 180 일치(≈26 GB)
또는 270 일치(≈39 GB)가 필요하다 — §7.1.7 편차 10 의 후속으로 등재하고 **여기서 돌리지 않는다**.

질의 하나로 봐도 비용은 초선형으로 자란다(없는 kind 를 찾는 정방향 질의, 행당):

| 일수 | 행 | 없는 kind 질의 | 행당 |
|---:|---:|---:|---:|
| 30 | 2,359,200 | 1.362 s | 0.577 µs |
| 90 | 7,077,600 | 6.658 s | 0.941 µs |
| **365** | **28,703,600** | **114.295 s** | **3.982 µs** |

행이 4.06 배일 때 시간은 17.2 배 — 행당 비용 자체가 **4.2 배** 나빠진다.

**2. 365 일치 부팅 질의 비용 — 인덱스 전 105.9–117.5 s, 인덱스 후 0.057–0.115 ms.**

**이 절이 A2 의 효과 수치를 드는 유일한 자리다** — §2 A2 · §7.1.7 편차 10 · 아래
「계획에 바꾸는 것」은 여기를 가리키기만 한다.

벤치의 형태별 `boot_path` 로 부팅 경로는 **12 형태**다. 인덱스 뒤에 sub-ms 로 떨어지는 것은
그중 **9 개**이고, 그 아홉의 인덱스 **전** 값은 **105.9–117.5 s 가 다섯**,
**이미 sub-ms 가 넷**(`by_kind_and_seq` · `exists_seq_and_kind` · `tip_excluding_kinds` ·
`tip_unfiltered` — PK·꼬리 형태)이다. 인덱스 **후** 아홉 개는 **0.057–0.115 ms** 이고,
같은 아홉 형태가 30 일치 **0.061–0.118 ms**(`a1/after-30d.json`) · 90 일치
**0.057–0.133 ms**(`a1/after-90d.json`) 였다 — 이력이 **12.2 배**(30 → 365 일)가 되어도 **같다**.

⚠ **119.8 s 를 이 범위에 넣으면 안 된다.** 그것은 `by_kind_payload_asc__hot`(행의 77 % 를
읽는 **저**선택도 프로브)의 값이고, 인덱스 뒤에도 112.8 s 로 sub-ms 군에 들어오지 않는다.
초판 §7.1.12 와 §2 A2 는 「105.9–119.8 s → 0.057–0.115 ms」로 **서로 다른 형태 집합의 양끝을
짝지었다** — 인덱스가 돕지 않는 바로 그 형태로 before 쪽을 부풀린 것이다.

| 묶음 | 1 회 합(전) | 1 회 합(후) |
|---|---:|---:|
| 부팅 경로 12 형태 | **921.6 s** | 114.9 s |
| 위에서 hot kind 프로브 둘(런타임 리더 0)을 뺀 10 형태 | **684.7 s** | **1.351 s** |

(합은 **각 형태를 한 번씩 돈 산술**이지 부팅 시뮬레이션이 아니다 — 합성 data dir 에 대한
실 `compose_paper_runtime` 부팅은 §7.1.7 편차 8 대로 시도하지 않았다. 후 1.351 s 의 거의
전부가 `by_kind_payload_asc__warm` 1.350 s 다.)

**⚠ 정정 — 「kind 필터 없는 전체 스캔은 부팅 경로」는 틀렸다(§7.1.2 에서 물려받은 것).**
§7.1.2 는 PR #819 지적 7 을 처분하면서 대조군을 「§7.1.1 에서 부팅 경로(✅)」라고 적었고
초판 §7.1.12 가 그대로 따랐다. 확인해 보면 그렇지 않다(심볼로 인용한다 — §7.1.1 과 벤치의
`readers=` 튜플이 들고 있는 줄번호는 작성 시점의 것이라 지금 트리와 어긋난다):

| 근거 | 내용 |
|---|---|
| 벤치의 **형태별** 플래그 | `full_scan_chain_control` 은 `boot_path=False`(`tools/tos_evidence_scan_bench.py` — 「index cannot help those … kept as the control group」) |
| 그 형태의 리더 둘 | `SqliteEvidenceStore.replay`(독스트링: 「for `verify_chain`」) · `SqliteEvidenceStore.iter_entry_meta`(독스트링: 「`evidence.retention` 의 read shape」). 측정 커밋 `32539e07` 과 현재 브랜치 양쪽에서 `evidence/store.py:789` · `:893` 이다 — 벤치의 `readers=` 가 든 `:777`/`:883` 은 `7d039339` 시점의 **낡은 줄번호** |
| 계획 §1 의 코드 사실 | 「전체 체인 재검증은 **복원 때만**(부팅 때는 하지 않는다)」 — `evidence/backup.py` · `operations/backup_set.py` |
| §7.1.1 의 ✅ 가 가리키는 것 | `evidence/store.py` **행 하나**에 호출부 6 개와 형태 4 종(`kind = ?` · PK 꼬리 · 전체 스캔 · `kind NOT IN (...)`)이 묶여 있고 ✅ 는 **행 단위**다(그 행의 줄번호도 작성 시점의 것이다) |

따라서 **형태별 플래그(벤치)를 따른다.** §7.1.1 의 행 단위 ✅ 를 형태 단위로 읽은 것이
원래의 과잉 독해다. 위 표·합은 이미 그 기준이라 수정이 필요 없고, **초판 산문의
「부팅은 인덱스가 있어도 최소 ~130 s 의 전체 스캔을 계속 낸다」는 철회한다.**

**⚠⚠ 그 ~130 s 의 주인은 넷이고, 그중 하나는 오프라인이 아니다.** 인덱스 전 131.1 s →
후 129.7 s 는 실측이고(인덱스는 닿을 수 없다 — 질의계획이 전·후 모두 `SCAN entries`),
90 일치 8.7 s 에서 **15 배**가 됐다. `iter_entry_meta` 호출부를 전부 세면:

| 소비자 | 성격 | 빈도 |
|---|---|---|
| `SqliteEvidenceStore.replay` → `verify_chain` | 복원 시 체인 재검증 | 복원마다 |
| `evidence/retention.py` 보존 판정 | 오프라인 | 판정마다 |
| `compose/_operations_wiring.py` `_read_unresolved_candidates` | 운영자 프로젝션 — **`lambda` 지연 호출**이라 배선 시점엔 돌지 않는다 | 프로젝션 조회마다 |
| **`riskstate/flow_observation.py` `FlowObservationReader._resolve_handling_started_monotonic`** | **런타임 · 제안마다** — `riskstate/service.py::_observe_flow` → `FlowObservationReader.observe` 가 호출하고, `_observe_flow` 자신은 `aggregate_inputs_for` · `action_flow_inputs_for` 에서 **리스크 단계 시도마다** 불린다 | **제안마다** |

넷째가 운영상 중요한 쪽이다. 그 코드는 `(seq, kind)` **한 행**을 찾으려고 테이블 전체를
`iter_entry_meta()` 로 훑는다 — 365 일치에서 **제안 하나에 ≥130 s** 다. 고칠 자리는 인덱스가
아니라 그 행이다(`seq` 는 PK 이므로 PK 조회 뒤 `kind` 확인). **후속으로 등재한다**(§2 A2-b) —
이 PR 은 문서 전용이라 구현하지 않는다. 앞의 셋은 오프라인·복원 경로라 ~130 s 가 같은 무게를
갖지 않는다. ⚠ 대조군은 3 열만 읽고 `iter_entry_meta` 는 8 열을 읽으므로 실제 호출은 이보다
**비쌀 수 있다** — 그 형태는 재지 않았다.

**3. 철회됐던 세션 수치 — 「국면」을 넣으면 대부분 재현된다.**

§7.1.2 가 「세션 기록·아티팩트 없음」으로 내린 값들을 이번 실측과 대조한다.
⚠ **초판 §7.1.12 는 이 표를 패스 평균과 대조해 「반증」이라고 적었는데, 그것이 틀렸다** —
그 값들은 전 패스의 **역방향 국면**과 맞는다. 2026-09-30 의 중단된 패스는 바로 그 국면에서
멈췄다(아래 타임라인). 세션 값이 틀렸던 것은 **속도가 아니라 그것을 패스 전체로 외삽한 것**이다.

| 철회된 값 | 이번 실측 | 판정 |
|---|---|---|
| 지속 **24 MB/s** (2,888 MB / 120 s) | 역방향 국면 물리 **26.6 MB/s**(형태별 26.5 · 26.6) / 정방향 418.3 / 패스 평균 123 | **역방향 국면에서 재현**(10 % 차) — 패스 평균으로는 재현 안 됨 |
| **「1 회 스캔 ≈ 35 분」** | 역방향 1 회 **23.8–34.5 분** / 정방향 1 회 1.8–2.9 분 | **역방향 국면에서 재현**(상단 34.5 분) |
| **「76 × 붕괴」** (1,815 → 24 MB/s) | 역방향 물리 기준 1,815 ÷ 26.6 = **68 ×** · 논리 기준 **60 ×** / 정방향 4.2 × / 패스 평균 14.1 × | **역방향 국면에서 재현**(12 % 차) |
| **612 GB 진행** | 역방향 첫 블록은 cum 1,183 → 6,558 s 이고 612 GB(= 11.5 파일분)는 cum **≈5,524 s** 다. 2026-09-30 중단 창은 **≤ 6,970 s**(§7.1.2) | **창 안에 들어간다** — 재현은 아니다(그 실행의 아티팩트는 여전히 0) |
| **「전·후 패스 ≈ 19.4 h」** | 24 MB/s 를 전 패스 전부(1,756–1,810 GB)에 적용하면 **20.3–20.9 h** — 외삽 산술은 맞는다. 실측은 **4.157 h** | **외삽이 틀렸다** — 34 회 중 28 회가 16 배 빠른 국면이었다 |
| **「캐시를 넘는 순간 처리량이 무너진다」** | 적중률 95.6 % → 4.5 %(두 점). 그 사이 모양은 **미측정** | **판정 불가**(위 1 — 180/270 일치 필요) |

**읽어야 할 교훈은 「세션 값이 과장이었다」가 아니다.** 그 값들은 자기가 보던 국면을 정확히
서술하고 있었고, 틀린 것은 **그 국면이 패스 전체를 대표한다는 가정**이다. 이 측정도 같은
함정을 두 번 밟았다 — 초판은 패스 평균을 국면의 반증으로 썼고, 그 다음 판은 국면별 물리
바이트를 「아티팩트에 없다」고 적었다. 둘 다 리뷰가 되돌렸다.

**아티팩트가 답하지 못한 것**

1. **13–53 GB 사이의 캐시 적중률 곡선.** 점이 없어 「절벽 대 소진」이 정해지지 않는다.
   180 일치(≈26 GB)나 270 일치(≈39 GB)가 그것을 정한다 — §7.1.7 편차 10 의 후속으로 등재.
2. **인덱스 뒤 파일 크기.** 드라이버는 `after` 뒤 크기를 적지 않고 합성 파일을 지웠다.
   §7.1.2 의 **+1.8 %** 증가(`--index-growth-ratio` 기본값의 근거)는 365 일치에서
   **재확인되지 않았다.** `after` 의 물리 쓰기 1.96 GB(53.226 GB 의 3.7 %)는 인덱스 페이지와
   sqlite 정렬용 임시 공간이 섞인 **상한**일 뿐이다.
3. **후 패스 논리 바이트의 성분 분해.** 6.85 파일분 중 인덱스 생성 몫과 인덱스 경유 임의 행
   조회 몫을 가를 수 없다(후 패스는 형태 경계마다 전 패스처럼 긴 구간이 없어 워치독 조인의
   분해능이 떨어진다 — 5 s 표본에 15 형태가 754 s 안에 들어간다).
4. **저장소 커밋.** 드라이버가 `preflight.json` 에 적지 않는다(위 「분기점 SHA」 — reflog 로
   밖에서 확인했다). `git rev-parse HEAD` 를 적게 하는 것이 가장 싼 보완이다.
5. **co-tenant pytest.** 워치독 패턴이 설계상 보지 않는다(위 「co-tenant」).
6. **역방향 스캔 12–14 배의 원인.** 관측만 있고 원인은 가리지 못했다.
7. **실 부팅 시간.** 질의 형태의 산술 합일 뿐 `compose_paper_runtime` 부팅은 재지 않았다
   (§7.1.7 편차 8 — 운영자 지시).

**이 측정이 계획에 바꾸는 것**

1. **§7.1.7 편차 10 — 표는 ✅ 해소, 가설은 ⚠ 부분 해소.** 「365 일치 전·후 표 미측정」이라는
   편차 **사실 자체는 닫혔다.** 그 위에 얹혀 있던 가설 넷 중 셋(24 MB/s · 35 분 · 76 ×)은
   **역방향 국면에서 재현**됐고 외삽만 틀렸으며, 넷째(「캐시 초과 순간 붕괴」)는
   **여전히 판정 불가**다 — 13–53 GB 사이에 점이 없다.
2. **A2 의 근거는 강화된다.** 수치는 위 「읽어야 할 것」 2 에 있고 여기서 되풀이하지 않는다.
   요지: 인덱스 뒤 선택도 높은 부팅 형태의 비용이 30·90·365 일치에서 **같고**, 인덱스의
   최악(hot kind 전량)은 365 일치에서도 **측정 가능한 열화가 없다**. 비용 쪽(파일 증가)만
   재확인되지 않았다(위 「답하지 못한 것」 2).
3. **새 후속 — A2-b: `FlowObservationReader` 의 제안별 전체 스캔.** ~130 s 의 인덱스 면역
   전체 스캔 소비자 넷 중 셋은 복원·보존·운영자 프로젝션(오프라인)이지만, 넷째는
   **리스크 단계 시도마다 도는 런타임 경로**다(위 「읽어야 할 것」 2 의 소비자 표). A2 인덱스는
   그것을 돕지 못하고 **고칠 자리는 그 행**이다 — `§2 A2-b` 로 등재했고 이 PR 에서
   구현하지 않는다.
4. **트랙 B 의 급함은 바뀌지 않는다.** 디스크는 여전히 여유 ≈4.7 년이고(§0-2), 이 측정은
   파괴적 퍼지의 전제 B-1…B-5 중 어느 것도 건드리지 않는다.
