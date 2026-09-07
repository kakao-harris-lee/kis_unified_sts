# 설계 문서 #40 — Phase 2 선행 결정 4건: runtime shell 경계 · RCL 저장/합의/장애 모델 · Evidence Store 내구/보존/백업 · 워크로드 정체성/키 회전/자격증명 보관 (2026-09-07, v1)

- **상위 계획**: `docs/plans/2026-08-11-tos-completion-development-plan.md` §4.2 (운영 shell) · §6 Phase 2 «선행 결정 1~4»
- **운영자 지시 (2026-09-07)**: 「모의투자 실측 제외하고 Phase 1 부터 진행」 · 「병렬로 Phase 진행 가능하면 바로 착수」
- **저작**: 세션 모델 단독 (운영자 지시 2026-09-04 — 기획 파이프라인·자동 심판 없음). 운영자 검토 대상.
- **상태**: **PROPOSED — 운영자 비준 대기.** 상위 계획 §4.2 「경계 ADR이 승인되기 전에는 네트워크 코드를 `tos/` 커널 안에 임시로 넣지 않는다」에 따라 D1 비준 전에는 어떤 런타임 I/O 코드도 착지하지 않는다.
- **권한**: 이 문서는 어떤 게이트·축·계좌에도 권한을 부여하지 않는다. restricted-live/production 은 `AUTHORITY-STATUS.csv` 만이 바꾼다.

## 0. 이 문서가 확정하는 것 / 하지 않는 것

**확정(4건)** — D1 composition 경계 · D2 RCL 저장/합의/장애 모델 · D3 Evidence Store 내구/보존/백업 · D4 워크로드 정체성·키 회전·자격증명 보관. 각 결정은 «Phase 2 비-live 범위에서의 구현 선택»이며, tos-spec 의 ADR-002-0xx 규범을 **해석**하지 **완화**하지 않는다. 규범을 지금 만족시키지 못하는 자리는 ⚠ 편차로 등재한다(숨기지 않는다).

**하지 않는 것** — tos-spec 본문 편집(브로커-무관 규범은 불변) · Phase 0 완료 계약 편집 · 실 브로커 transport(Phase 4) · 복구 코디네이터/조정(Phase 5) · 어떤 EV 행의 상태 변경 · restricted-live 판단.

**전제 실측(2026-09-07 서베이, `feat/tos-phase2-authority-runtime` @ `e7bf37a0`)**

- 커널 13패키지 중 11개는 순수 술어/레코드이며 «runtime 이연» 마커를 자기 문서에 명시한다. 실 I/O 는 `tos/src/tos/staterestore/store.py` 의 sqlite3 WAL(`synchronous=FULL`, 차원별 1트랜잭션) 하나뿐이다(`store.py:96-140`).
- `SendAttemptLedger`(`egressgw/gateway.py:278-291`)·`ProvisionalReservationLedger`(`engine/state.py`)·`ProvisionalStandIn`(`engine/standins.py`) 는 전부 «NON-AUTHORITATIVE PROVISIONAL» 자기선언.
- 방화벽 정방향 스캔은 `tos/` 전체를 걷는다(`tools/tos_firewall_check.py` `run_checks`: `repo_root/"tos"` · `_iter_py_files` 는 `.venv` 만 제외). 따라서 `tos/runtime/` 은 그대로 두면 커널과 같은 allowlist(socket/ssl 금지 등)에 걸린다.
- `tos/pyproject.toml` 허용 서드파티 = pydantic·numpy·pandas·pyyaml(+pytest·hypothesis). 합의·암호·DB 드라이버 라이브러리는 0.
- EV-L3 파일럿의 sqlite3/WAL 은 «pilot-scope» 로만 비준됐다(OQ-1 (A) 채택 2026-08-06 · RESIDUAL-RISK-REGISTER-002.yaml:279-283). ADR-002-005 §4 의 프로젝트 영속 기술 결정은 **열려 있었고, 이 문서 D2/D3 가 그 결정이다.**
- 배포 현실 = 단일 운영자·단일 호스트(`tos-spec/src/decision-records/DR-0001-Single-Operator-Live-Governance.md`, Accepted). 다중 노드 quorum 배포는 존재하지 않는다.

---

## D1. Composition 경계 — **A안 채택**: `tos/runtime/` 별도 distribution `tos-runtime`

### D1.1 결정

| 항목 | 값 |
|---|---|
| 파일시스템 | `tos/runtime/` (src-layout: `tos/runtime/src/tos_runtime/`, 테스트 `tos/runtime/tests/`, 자체 `tos/runtime/pyproject.toml`) |
| distribution / import 이름 | `tos-runtime` / `tos_runtime` |
| 허용 import 방향 | `tos_runtime → tos`(커널) ✔ · `tos_runtime → 승인 어댑터`(D1.3 allowlist) ✔ · `tos → tos_runtime` ✘ · 저장소 밖(`shared/services/cli/…`) → `tos` **또는** `tos_runtime` ✘ (R-역방향을 두 패키지로 확장) · `tos_runtime → shared.*` ✘ (커널은 6 커먼즈 중 0 사용 실측 — 런타임에 새 커먼즈 의존을 열지 않는다) · `tos_runtime → §2.3 운영 집합` ✘ (전이 포함) |
| composition root | `tos_runtime.compose` 단 하나 — 커널 Protocol 심(§0 전제의 `SendTransport`·`GatewayEvidenceSink`·`EvidenceSink`·`Transport`·`SnapshotStore`·`Stage`·`Transmit`·`DecisionContextResolver`)을 구현체와 **한 자리**에서 결선한다. 커널 어디에도 «기본 구현» 을 두지 않는다. |
| 설정 | 파일 경로는 CLI 인자로만 주입(`os.environ`/`os.getenv` 는 런타임에서도 **직접 금지** 유지 — 상위 계획 §5.3 「ambient env 로 라우팅하지 않는다」). YAML 파싱은 pyyaml(이미 허용). |

### D1.2 B안(프로세스/IPC 완전 분리) 기각 사유

failure-domain·자격증명 격리는 최강이나, (i) IPC 스키마·durability·마이그레이션 소유권이 Phase 2 에 새 표면을 셋 더 만들고 (ii) 단일 호스트 배포(DR-0001)에서 프로세스 분리가 주는 격리 이득이 A안의 «자격증명은 런타임 안에서도 별 principal·별 custody 스코프»(D4)로 대부분 회수되며 (iii) A안은 B안으로의 승격을 막지 않는다(커널 Protocol 심이 그대로 IPC 경계가 된다). 상위 계획 §4.2 권고와 일치.

### D1.3 방화벽 설계 개정(#1 §3.2/§3.3/§6.1) — 이 문서 비준 시 **같은 PR** 에서 적용

1. **스캔 범위 이원화**: `tools/tos_firewall_check.py` 정방향 스캔을 «커널 범위»(`tos/src`·`tos/tests` — 현행 allowlist v2 그대로)와 «런타임 범위»(`tos/runtime/**` — 아래 allowlist R1)로 나눈다. 범위 판별은 경로 접두 하나이며, `tos/` 아래 그 밖의 경로(예: 새 형제 디렉터리)는 **커널 범위로 fail-closed**(모르는 곳은 엄격한 쪽).
2. **allowlist R1(런타임 직접 import)** = (커널 allowlist v2 **에서 커먼즈 6종 `shared.*` 를 뺀 것**) ∪ `tos.*` ∪ `tos_runtime.*` ∪ stdlib `socket`·`ssl`·`http`·`urllib.request`·`sqlite3`(이미 허용)·`hmac`·`hashlib`·`secrets`. `shared.*` 는 런타임 범위에서 **직접 import 전면 거부**(D1.1 표 «tos_runtime → shared.* ✘» 의 기계 강제 — 커널이 커먼즈 0 사용인데 런타임이 레거시 의존을 새로 여는 것을 막는다). **계속 금지**: `subprocess`·`ctypes`·`ftplib`·`smtplib`·`poplib`·`imaplib`·`telnetlib`·`os.environ`/`os.getenv`·동적 import. 서드파티 추가는 0(Phase 2 는 stdlib 로 닫는다 — D2/D3). *(v1.2 정정: v1 문언은 커먼즈를 포함해 D1.1 과 모순이었다 — 준비 레인이 적발.)*
3. **신규 규칙 (g)**: 커널 범위의 어떤 파일도 `tos_runtime` 을 import 하지 못한다(AST) + `.importlinter` 에 `source tos → forbidden tos_runtime` 계약 추가. **규칙 (e) 확장**: `tos/` 밖 파일의 `import tos_runtime` 도 위반.
4. `.importlinter` 의 `tos-operational-firewall` 계약 `source_modules` 에 `tos_runtime` 추가(전이 방어를 런타임에도).
5. CI `tos-firewall` 잡: 런타임 범위 스캔은 같은 검사기 한 번의 호출에 포함(스텝 추가 없음) · `pytest tos/runtime/tests` 스텝 추가 · 크기 budget `scope` 에 `tos/runtime/src` 추가 · `tos-gate.yml`·하니스는 불변.
6. §6.1 개정 로그 1줄: 「2026-09-xx: D1 — `tos/runtime/` 런타임 범위 신설·allowlist R1·규칙 (g)·(e) 확장 (설계 #40 D1.3)」.

### D1.4 런타임 테스트의 hermetic 정의

커널 테스트 규율(«no .env, no network, no Redis»)을 런타임에는 **«외부 네트워크 0·ambient env 0·임시 디렉터리 밖 쓰기 0»** 으로 재정의한다. `127.0.0.1` 소켓과 `tmp_path` 의 sqlite 파일은 허용(그것이 런타임의 존재 이유). 위반 시 실패하는 픽스처(외부 주소 `socket.connect` 몽키패치 거부)를 `tos/runtime/tests/conftest.py` 에 둔다.

---

## D2. RCL 저장/합의/장애 모델 — **단일 노드 선형화 로그(sqlite3 WAL) + 교체 가능한 `CommitLog` 포트 · quorum 복제는 등재된 편차**

### D2.1 결정

- **Safety Commit Log 구현체 = `tos_runtime.rcl.SqliteCommitLog`**: 파일 1개 · `journal_mode=WAL` · `synchronous=FULL` · 모든 변이는 `BEGIN IMMEDIATE` 트랜잭션 안의 **compare-and-set**(기대 `seq`/기대 상태 → 새 상태) · 단조 `seq` · 각 항목에 `writer_epoch` 결속.
- **Writer fencing**: 프로세스는 기동 시 `epochs` 테이블에서 **새 epoch 를 원자적으로 발급**(이전 epoch 는 즉시 무효). 모든 쓰기는 «내 epoch == 현재 epoch» 를 같은 트랜잭션에서 검사한다 → stale epoch writer 의 쓰기는 **구조적으로 거부**(ADR-002-003 :171/:175 «enforcement points reject epoch below current», ADR-002-012 :131 «Writer Epoch ≠ consensus term without proof» — 여기서는 단일 노드라 epoch = 로그 순서 그 자체이고 그 사실을 문서화한다). OS 파일 잠금은 **보조**이지 정체성이 아니다(`flock` 은 NFS·크래시 시 신뢰 불가).
- **선형화 읽기**: 모든 판정 읽기는 «현재 epoch 확인 + `seq` 스냅샷» 을 같은 트랜잭션에서(ADR-002-012 :243 read-index 상당). 캐시 없음(`staterestore/store.py:109-110` 규율 상속).
- **예약 생명주기**: `CapacityReservation{RESERVED → POTENTIALLY_LIVE → (CONFIRMED|RELEASED|QUARANTINED)}` 를 로그 항목으로 — `mark_potentially_live` 의 권위 전이가 처음으로 RCL 소유가 된다(현행 engine 투영은 이 로그의 **읽기 투영**으로 강등). 해제(release)는 **broker truth 또는 evidence 가 확정한 종결만**이 트리거이며 자동 re-arm 없음(ADR-002-012 :37).
- **포트**: 커널에 `tos.rcl.CommitLog` **Protocol** 을 신설(순수 시그니처: `append_cas`·`read_linearizable`·`current_epoch`·`replay`). 런타임 sqlite 구현과 미래의 복제 구현이 같은 포트를 만족한다. 커널은 포트만 알고 구현을 모른다(D1 방향).
- **컴팩션/보존**: Phase 2 는 컴팩션을 **구현하지 않는다**(항목 삭제 0). 툼스톤·재시도 지평 규칙(ADR-002-012 :437)은 D3 보존 정책과 같은 표에서 정의만 한다.
- **장애 계약(각 서비스가 정상 API 보다 먼저 구현·테스트 — 상위 계획 Phase 2)**: ① stale epoch writer → 거부+evidence ② 중복 command / 같은 ID 다른 바이트 → 두 번째는 거부, 바이트 불일치는 `INTEGRITY_VIOLATION` 기록 ③ 파티션/quorum 상실 → 단일 노드에서는 «로그 파일 접근 불가» 로 사상 = 모든 신규 위험 거부 ④ durable commit 전/후 크래시 → EV-L3 파일럿 주입 하네스(`tests/tos_l3`) 재사용 ⑤ 재기동 후 replay → 로그 전량 재생이 같은 상태를 재현하지 못하면 `CORRUPTION` 표면화·비-live 고정(ADR-002-012 :491) ⑥ 클록 역행/왜곡 → 로그는 클록을 **쓰지 않는다**(순서 = seq) · 시간은 D2 밖(Trustworthy Time 서비스가 따로 evidence) ⑦ 저장소 불가/부분 커밋 → fail-closed(쓰기 실패 = 거부, 성공 보고 없음).

### D2.2 ⚠ 등재 편차

- **ADR-002-012 :17/:19 «quorum-replicated, 2f+1»** — Phase 2 는 f=0. 이는 규범 완화가 아니라 «비-live 범위의 선택» 이며, ADR-002-009 :276-282 항목 6(로컬 저장소는 별도 승인 기제+파티션/페일오버 evidence 없이는 RCL 기판이 아니다)과 :283 에 따라 **restricted-live/production 게이트는 이 편차만으로도 NO 로 남는다**. 등재 위치: Phase 2 착수 PR 에서 `RESIDUAL-RISK-REGISTER-002.yaml` 에 신규 행(«RCL 복제 부재 · 단일 노드 · 해소 = 복제 구현체 + 페일오버 evidence»)을 추가(레지스터 편집은 결속 집합 편집이 아니다 — 실측: `tools/tos_completion_status.py:96` `U12_BOUND_PATHS` 는 완료 계약 `docs/plans/2026-08-12-*` 와 개발계획 `docs/plans/2026-08-11-*` **둘**이며 tos-spec 레지스터는 포함되지 않는다. 같은 이유로 이 문서는 개발계획 본문을 편집하지 않는다 — §1 기준선 163/16 경고 정정도 재결속 사이클에서만).
- **ADR-002-012 :369-376 membership/joint consensus** — 단일 노드에서 표현 불가 → 같은 행에 병기.

### D2.3 기각 대안

- raft 라이브러리 내장: 허용 서드파티 0·다중 노드 배포 부재·«합의는 동기화된 클록에 의존하면 안 된다»(:249)를 단일 호스트에서 검증 불가. 포트를 남겨 승격 경로만 확보.
- Redis: 운영 집합(§2.3) 이자 내구성 모델이 선형화 로그가 아님. 방화벽이 이미 금지.
- 외부 RDBMS: 배포 부재·의존 추가. 루트 CLAUDE.md 「Runtime ledger: SQLite WAL」과도 정합.
- `staterestore.CompositeStateStore` 를 그대로 RCL 로 승격: 그 모듈은 EV-L3 파일럿의 **주입 지점 보존**이 목적(차원별 1트랜잭션이 «불완전 저장소» 셀을 만든다)이라 CAS·epoch 가 없다. 재사용 대상은 «sqlite 연결/트랜잭션 규율» 이지 스키마가 아니다 — 런타임 `SqliteCommitLog` 는 그 규율(`WAL`·`FULL`·연결 컨텍스트)을 **함수 수준으로 추출해 공유**하고 스키마는 별도.

---

## D3. Evidence Store 내구/보존/백업 — **append-only sqlite3 + 프로덕션 해시체인 + 분리된 비상 HALT 경로 + 세대 스탬프 백업**

### D3.1 결정

- **저장소**: `tos_runtime.evidence.SqliteEvidenceStore` — RCL 과 **다른 파일**(장애 도메인 분리 · ADR-002-016 :21/:23 «asymmetric emergency path, separately durable» 의 전제). append-only 테이블(`UPDATE`/`DELETE` 를 트리거로 거부 — 표현 불가능화) · `WAL`·`FULL`.
- **체인**: `evidence/ledger.py` 의 `ProvisionalHashChainScheme`(«explicitly non-production») 을 **런타임 구현체** `Sha256HmacChainScheme` 로 대체 — 항목 digest = SHA-256(정본 바이트) · 체인 = HMAC-SHA256(key_generation, prev_chain ‖ digest)(stdlib `hashlib`/`hmac`). 키는 D4 custody 에서 온다. 커널의 `SegmentCommitmentScheme` Protocol 을 그대로 만족.
- **커밋 영수증**: `append()` 는 durable 커밋 **후에만** `(segment_id, seq, chain_digest, key_generation)` 을 돌려주며, 이 영수증이 없는 «기록됨» 주장은 존재하지 않는다(egressgw 의 `SEND_STARTED` 는 이 영수증을 받은 뒤에야 transport 를 부른다 — ADR-002-016 :19 «no in-memory buffering substitute»).
- **비상 HALT 경로**: `tos_runtime.evidence.EmergencyAppendLog` — 별 파일·JSON Lines·`os.fsync` per line·의존 0(sqlite 가 죽어도 쓴다). HALT/보호 조치 기록은 **두 경로에 모두** 쓰고 하나라도 실패하면 실패로 보고(성공 과대 보고 금지).
- **outbox**: 외부 싱크(운영자 알림·텔레메트리)로의 전달은 같은 트랜잭션의 outbox 행으로만 예약, 전달자는 별 루프(at-least-once · 수신측 멱등 키 = `(segment_id, seq)`). Phase 2 는 outbox 테이블과 소비자 포트만, 실제 외부 싱크는 0.
- **보존**: `config/tos_runtime/evidence_retention.yaml` 에 레코드 클래스별 최소 보존 기간(값은 운영자 승인 대상 · 이 문서는 값을 발명하지 않는다 — `named-TBD`) · «열린/live 레코드는 재구성 가능성 아래로 삭제 불가»(ADR-002-016 :432-441)는 술어 `deletable(record, holds, now)` 로만 존재하고 **삭제 잡은 Phase 2 범위 밖**(툼스톤 스키마만).
- **백업/복원**: sqlite `backup()` API 로 세대 스탬프 파일 `evidence.<generation>.sqlite3` + 매니페스트(파일 digest·마지막 `seq`·chain_digest·key_generation) 생성. **복원은 항상 새 세대를 발급하고 비-live 로 고정**하며 살아남은 브랜치 전부와 대조한 결과를 evidence 로 남긴다(ADR-002-016 :449-459 표 «Backup older than current history restored»).
- **리플레이**: `replay(store) -> Iterator[Record]` 는 체인 재검증을 겸하며 불일치 시 `CORRUPTION` 을 표면화. 리플레이 환경은 live 자격증명을 갖지 않는다(:380-382) — D4 custody 스코프 `replay` 는 evidence 검증 키만.
- **비밀 미기록**: 레코드 직렬화 전 `scrub()` 이 D4 의 «비밀 필드 목록» 을 결정론적으로 마스킹하고 그 사실 자체를 항목 메타에 남긴다(:426).

### D3.2 기각 대안

- 로그 파일(JSONL) 단일 저장소: 트랜잭션 outbox·리플레이 인덱스·«UPDATE 거부» 표현이 어렵다. JSONL 은 비상 경로에만.
- RCL 과 같은 파일: 장애 도메인 결합 · HALT 경로의 «분리 내구» 위반.
- 외부 서명(HSM/KMS): 배포 부재 · 비밀 반출 규칙(ADR-002-013 :255-257) 은 D4 파일 custody 로 우선 만족.

---

## D4. 워크로드 정체성 · 키 회전 · 자격증명 보관 — **런타임 인스턴스 정체성 + 파일 custody(0600) + 스코프 분리 + deny-first 회전**

### D4.1 결정

- **정체성**: `RuntimeIdentity{cell_id, runtime_generation, process_nonce, code_digest}` — 기동 시 발급, 모든 evidence·RCL 항목에 결속. `runtime_generation` 은 D2 epoch 와 **같은 트랜잭션**에서 증가(ADR-002-017 :15 Recovery Generation 의 전신 · Phase 5 가 소비).
- **custody 포트**: 커널에 `tos.liveauth`… 가 아니라 **런타임에** `tos_runtime.custody.CredentialCustody` Protocol(커널은 자격증명 개념을 모른다 — 커널은 principal 문자열과 route inventory 만 본다, `egressgw/records.py` `TransportNature`). Phase 2 구현체 = `FileCustody`: CLI 로 받은 디렉터리 안의 스코프별 파일(`read.principal`, `evidence.key`, …) · 권한 `0600`·소유자 일치 검사(아니면 거부) · 로드 시 evidence 에 **principal id 와 파일 digest 만**(비밀 0) 기록 · 메모리 핸들은 사용 후 즉시 폐기.
- **스코프 분리**: `read`(시세/계좌 조회) · `order`(주문) · `evidence`(체인 HMAC) · `replay`(검증 전용 공개 파라미터) — 서로 다른 파일·서로 다른 principal 문자열, `credential_principal_separation_ok` 로 기동 시 검증(ADR-002-013 :267-269). **Phase 2 는 `order` 스코프 파일을 로드하는 코드 경로를 두지 않는다**(Phase 4 KIS MOCK 주식 주문 때 · 선물 REAL 은 영구 부재 — 루트 CLAUDE.md 비협상).
- **키 회전(evidence HMAC)**: 새 `key_generation` 은 RCL/evidence 양쪽에 «회전 커밋» 항목을 남기고 그 seq 부터만 유효 · 이전 키는 **회전 커밋과 동시에** 서명 무효(검증에는 유효 — 과거 체인 검증용) · 겹침 0(ADR-002-013 :401-418 deny-first). 브로커 자격증명 회전은 Phase 4.
- **환경 격리**: `non-live-test`/`paper`/`restricted-live`/`production` 은 서로 다른 custody 디렉터리·다른 `cell_id` 접두·다른 trust root 파일(ADR-002-013 :498). 런타임은 기동 인자로 받은 환경 라벨과 custody 디렉터리의 매니페스트 라벨이 **불일치하면 기동 거부**.

### D4.2 기각 대안

- 환경변수: ADR-002-013 :257 명시 금지 · 방화벽 (c) 규칙과 충돌.
- OS 키체인: 배포는 Linux 컨테이너(단일 호스트)라 이식성·헤드리스 문제.
- Vault/KMS: 배포 부재 · 네트워크 의존 추가. 포트가 있으므로 후속 승격 가능.

---

## 5. Phase 2 구현 순서 → 레인 (D1 비준 후)

| 순서 | 상위 계획 항목 | 산출물 | 의존 |
|---|---|---|---|
| 0 | D1.3 방화벽 개정 + `tos/runtime/` 스켈레톤 + CI | 검사기 범위 이원화·규칙 (g)·importlinter·`tos/runtime/pyproject.toml`·hermetic 픽스처 | 운영자 비준 |
| 1 | Trustworthy Time + generation/epoch | `tos_runtime.time`(단조 소스 + health generation 레코드 → 커널 `tos.time` 술어 소비) · `RuntimeIdentity` | 0 |
| 2 | durable Evidence Store | D3 전부(+ `Sha256HmacChainScheme`·비상 경로·outbox·백업/복원·리플레이) | 0, D4 custody `evidence` 스코프 |
| 3 | linearizable RCL + fencing + 예약 생명주기 | D2 전부 · 커널 `tos.rcl.CommitLog` 포트 · engine 투영 강등 | 2 (전이는 evidence 를 남긴다) |
| 4 | Safety Authority + IAP | epoch 소유 authority 서비스(커널 `authority`/`iap` 술어 소비) · 승인 nonce 소비 fencing | 3 |
| 5 | ARA + AFG | `are`/`afg` 술어를 RCL 원자 커밋에 결선 | 3 |
| 6 | currentness/quorum + release-admission | `cur`·`sci` 술어의 런타임 소비 · 단일 노드 «quorum» = 자기 자신+epoch(편차 병기) | 1, 3 |

각 순서는 장애 계약 테스트 → 정상 API 순으로(상위 계획). 순서 1·2 는 병렬 가능(레인 2개), 3 이후는 직렬. 종료 조건은 상위 계획 Phase 2 그대로 + 이 문서 편차 2건의 레지스터 등재.

## 5-A. D1 비준 «전» 에 착지 가능한 선행 작업 (운영자 지시 «병렬 착수» 이행 · 전부 되돌리기 쉬움)

| 레인 | 내용 | 왜 비준 전에 가능한가 |
|---|---|---|
| D1.3 준비 | 방화벽 검사기 범위 이원화·규칙 (g)·(e) 확장·`.importlinter` 계약·설계 #1 §6.1 개정 로그·`tos/runtime/` 스켈레톤(pyproject·빈 패키지·hermetic conftest)·CI 스텝·budget scope | §6.1 절차가 «본 문서를 수정하는 PR» 이므로 비준은 곧 그 PR 의 머지다. 스켈레톤에는 네트워크·sqlite 코드가 없다(상위 계획 §4.2 준수). |
| D3 커널 측 | `EvidenceCommitReceipt` 레코드 · `Sha256HmacChainScheme`(stdlib hashlib/hmac · 키 바이트는 주입 · 기존 `SegmentCommitmentScheme` Protocol 구현) · `retention_deletable(...)` 순수 술어(기간 값은 주입 · 열린/live 레코드는 항상 False) | 순수 · I/O 0 · 커널 allowlist 안 |
| D4 커널 측 | `RuntimeIdentity` 레코드(cell_id·runtime_generation·process_nonce·code_digest — 전부 주입 스칼라) · `environment_label_consistent(runtime_label, manifest_label)` 술어(None/불일치 = False) | 순수 · custody 는 여전히 런타임 소관(커널은 비밀을 모른다) |

D2 커널 측(포트·술어)은 `8ea42a8d` 로 착지 완료.

## 6. 운영자 확인 사항 (비준 체크리스트)

1. D1 A안 · `tos/runtime/` 배치 · allowlist R1 · 규칙 (g)/(e) 확장 — **방화벽 설계 #1 개정을 승인하는가**.
2. D2 «단일 노드 f=0» 편차를 RESIDUAL-RISK-REGISTER-002 에 등재하는 방식으로 진행하는가(restricted-live NO 유지에 동의).
3. D3 보존 기간 값은 named-TBD 로 두고 후속 승인하는가.
4. D4 custody 디렉터리·환경 라벨 규약(파일 custody, 키체인/Vault 기각)에 동의하는가.

## 7. 개정 로그

- 2026-09-07: v1 최초 저작(세션 모델 단독 · 서베이 2건 실측 반영).
- 2026-09-07: v1.1 — D2 커널 측 포트 착지(`8ea42a8d`, `tos.rcl.commitlog` · I/O 0 · D1 비준과 무관한 순수 술어) 에서 드러난 정정 둘. ① D2.1 의 예약 생명주기 약칭 `RESERVED → POTENTIALLY_LIVE → CONFIRMED|RELEASED|QUARANTINED` 는 새 enum 이 아니라 기존 `tos.rcl.CapacityState` 9종(ADR-002-002 §10.1 · `engine/state.py` 가 이미 예약 생명주기로 소비)에 사상한다 — RESERVED≈COMMITTED_UNBOUND/ATTEMPT_BOUND · CONFIRMED≈POSITION_CONSUMED · QUARANTINED=QUARANTINED_UNKNOWN · POTENTIALLY_LIVE/RELEASED 는 동명. 해제 admit 의 finality 목적지는 {RELEASED, POSITION_CONSUMED}. ② `WriterEpoch` 는 RCL 로컬 `int` 이며 `tos.authority` 의 Safety Authority epoch 와 **동일시하지 않는다**(ADR-002-012 §5.5 :129-131) — D2.1 「epoch = 로그 순서 그 자체」 문장은 «RCL writer epoch» 에 한정된 진술로 읽는다. 런타임 `SqliteCommitLog` 는 두 epoch 의 사상을 **증명 없이 결합하지 않는다**(같은 트랜잭션에서 둘 다 기록하되 별 컬럼).
