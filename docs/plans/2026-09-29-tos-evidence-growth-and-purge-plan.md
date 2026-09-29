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
