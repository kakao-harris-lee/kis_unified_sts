# 새 스토어 파일의 WAL 전환 경합 — #818 수정 계획

- 작성: 2026-09-30 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `7d039339`
- 요청: 운영자 2026-09-30 「#818 수정 계획 써줘」.
- 성격: 계획. 운영자 처분(§6) 뒤 같은 브랜치에서 구현한다.
- ⚠ **순서 제약**: PR #817(#801 원자적 제네시스)이 같은 생성자 줄들(`PRAGMA journal_mode=WAL` 바로 뒤의
  `open_or_create_schema`)을 고친다. 구현은 **#817 머지 뒤** 그 main 위에서 시작한다.

## 0. 요약

- **결함**: 두 프로세스가 **완전히 새** 스토어 파일을 동시에 열면, `PRAGMA journal_mode=WAL` 이
  `OperationalError: database is locked` 로 실패한다.
  - 원인: 저널 모드를 롤백 저널 → WAL 로 바꾸려면 배타 잠금이 필요한데, 이 PRAGMA 는 sqlite 의 busy
    handler(연결의 timeout)를 **거치지 않는다**. 진 쪽은 기다리지 않고 바로 실패한다.
  - #817 은 그 뒤의 제네시스 경합(R-1 · R-2)을 닫았다. 그러나 「같은 빈 `data_dir` 동시 첫 부팅이 죽는다」는
    사용자 증상은 이 한 줄 앞에서 남는다.
- **수정 — 기다린 뒤 한 번 더**: PRAGMA 가 잠금으로 실패하면 `BEGIN IMMEDIATE; ROLLBACK` 으로 **sqlite 자신의
  busy handler 로 기다린 뒤** PRAGMA 를 다시 부른다.
  - 전환을 끝낸 쪽이 잠금을 놓으면, 기다린 쪽의 두 번째 PRAGMA 는 이미 WAL 인 파일에 대한 무동작이다.
  - 새 대기 상수가 없다. 대기 상한은 연결에 이미 설정된 timeout 이다(`PRAGMA busy_timeout`, 기본 5000 ms ·
    rcl 은 주입값).
  - 반환값이 `wal` 이 아니면 **부팅 거부** — 지금은 반환값을 확인하지 않는다.

## 1. 실측 (2026-09-30 · 스크래치 · 호스트 로컬)

`multiprocessing`(fork) N 개가 `Barrier` 로 동시에 **새 파일**에 `sqlite3.connect(…, isolation_level=None)`
(기본 timeout) → `PRAGMA journal_mode=WAL` 을 부른다.

| 방식 | N=2 | N=8 |
|---|---|---|
| 지금 코드(재시도 없음) | **17 / 80 실패**(21 %) | **22 / 320 실패** |
| 잠금 실패 시 `BEGIN IMMEDIATE; ROLLBACK` 로 기다린 뒤 한 번 더 | **0 / 120** | **0 / 480** |
| (참고) 5 ms 간격 재시도 · 상한 = `busy_timeout` | 0 / 80 | 0 / 320 |

- 실패는 전부 `database is locked` 다.
- 성공한 모든 연결의 반환값은 `wal` 이었다.
- PR #817 리뷰의 실측(실제 `SqliteEvidenceStore` · N=2 22/80 · N=4 57/160 · N=8 90/320)과 같은 결함이다.
  그쪽 비율이 더 높은 것은 PRAGMA 뒤의 부팅 단계가 창을 넓히기 때문이다.

## 2. 결정

### 2.1 공유 헬퍼

`tos_runtime/operations/schema_ledger.py`(네 스토어가 이미 여는 모듈)에 `enable_wal_journal(conn)` 을 둔다.

```text
try:    mode = PRAGMA journal_mode=WAL
except OperationalError("database is locked"):
        BEGIN IMMEDIATE ; ROLLBACK        ← sqlite busy handler 로 대기 (연결의 timeout 까지)
        mode = PRAGMA journal_mode=WAL    ← 두 번째도 실패하면 그대로 올린다 (부팅 거부)
if mode != "wal": raise (부팅 거부 — 조용히 롤백 저널로 돌지 않는다)
```

- **재시도는 딱 한 번**이다. 무한 루프도 새 횟수 상수도 없다. 두 번째 실패는 「연결의 timeout 동안 다른 쪽이
  잠금을 놓지 않았다」는 뜻이므로 fail-closed 가 맞다.
- `database is locked` 가 아닌 `OperationalError` 는 재시도하지 않고 그대로 올린다.
- `BEGIN IMMEDIATE` 는 롤백 저널 파일에서는 RESERVED 잠금이다. 곧바로 `ROLLBACK` 하므로 쓰기는 0 이다.
- 네 스토어(evidence · inbox · marketfeed · rcl)의 `self._conn.execute("PRAGMA journal_mode=WAL")` 한 줄을 이
  헬퍼 호출로 바꾼다(DRY).

### 2.2 커널 `CompositeStateStore` — 범위 밖

- `tos/src/tos/staterestore/store.py:124` 에도 같은 줄이 있다. 하지만 이것은 **커널**이라 런타임 헬퍼를
  import 할 수 없다(방화벽).
- 부팅 때가 아니라 복구 기록자가 **필요할 때** 연다(`recovery/composite_state_writer.py:110`). 한 프로세스
  안에서만 열린다.
- 커널 쪽 사본을 만들면 DRY 위반 + 커널 변경이다. 노출이 다르므로 별도 결정으로 남긴다(§5).

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| 짧은 간격 sleep 재시도(상한 = `busy_timeout`) | 동작은 같지만(§1) 새 간격 상수가 생긴다. sqlite 의 busy handler 를 쓰면 대기 정책이 연결 하나에 모인다 |
| compose 가 모든 스토어 파일을 먼저 만들고 WAL 로 전환 | 스토어를 여는 경로가 compose 하나가 아니다 — 운영자 CLI(`migrate`·`backup-set`·`rearm` 등), 테스트, 프로브. 결함을 스토어 생성자에서 닫아야 모든 경로가 덮인다 |
| `data_dir` 잠금 | #817 계획 §3 과 같은 이유 — D2.1 이 flock 을 정확성에 기대지 않는다 |
| 반환값 확인 없이 재시도만 | 전환이 조용히 실패해 롤백 저널로 돌면 `synchronous=FULL`·WAL 을 전제한 내구성 논증이 깨진다 |

## 4. 작업

| # | 내용 | 종료 조건 |
|---|---|---|
| T-1 | `enable_wal_journal(conn)` + 단위 테스트 | 잠금 실패 → 대기 → 성공 · 두 번째 실패는 그대로 올림 · `database is locked` 가 아닌 오류는 재시도 없음 · 반환값 `wal` 아님 → 거부 |
| T-2 | 네 스토어 생성자를 헬퍼로 | 기존 스위트 무변경 통과 · 새 파일 모양·`user_version`·CREATED 행 바이트 동일(#817 의 `_PRE_CHANGE_SHAPES` 핀 재사용) |
| T-3 | **#817 의 동시성 테스트에서 `_precreate_wal_file` 을 뺀 변종**(스토어별 · N=8 · 시작 장벽) | 수정 전 코드에서 `database is locked` 가 **재현되어 먼저 red** · 수정 후 N 개 모두 성공 · CREATED 행 1 |
| T-4 | 타임아웃 초과 시 명시적 거부(한쪽이 배타 잠금을 timeout 넘게 쥔다 · 테스트에서 짧은 timeout 주입) | `OperationalError` 로 부팅 거부 · 파일 무손상 |
| T-5 | digest 재도출(마지막 커밋) · 계획 §7 착지 · INDEX · #818 링크 · #817 의 「#818 로 추적」 문구 정리 | 통상 게이트 + mypy(저장소 루트 · `PYTHONPATH=tos/src:tos/runtime/src` · 마지막 줄 `Success`) |

**뮤테이션**(red 확인):
- 재시도 제거 → T-3 red
- 반환값 확인 제거 → T-1 red
- `database is locked` 가 아닌 오류도 재시도 → T-1 red

## 5. 위험·범위 밖

- **#817 머지 뒤 시작**(같은 줄). #817 의 `_precreate_wal_file` 은 T-3 에서 뺀 변종과 함께, 원래 목적(제네시스
  트랜잭션만 격리해 보기)을 그대로 두고 문구만 갱신한다.
- **커널 `CompositeStateStore`**(§2.2)는 이번 범위 밖이다. 두 런타임이 같은 `data_dir` 에서 복구 기록을 동시에
  처음 쓰는 경우에만 드러난다. 필요하면 별도 이슈로 연다.
- 대기 상한은 연결의 timeout 이다. evidence·inbox·marketfeed 는 파이썬 기본 5 s, rcl 은 주입값이다. 새 설정 키는
  만들지 않는다.
- 런타임 소스 변경 → digest 재도출.

## 6. 운영자 확인

1. **「기다린 뒤 한 번 더」(§2.1)** — sleep 재시도나 compose 선생성이 아니라 sqlite busy handler 로 대기. 동의 여부.
2. **반환값이 `wal` 이 아니면 부팅 거부** — 동의 여부.
3. **커널 `CompositeStateStore` 는 범위 밖**(§2.2) — 동의 여부.
4. 구현은 **#817 머지 뒤** 이 브랜치에서 — 동의 여부.
