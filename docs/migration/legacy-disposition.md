# Legacy disposition — 기능별 처리와 전환 작업표

기준: 2026-10-06, repository `5c4f38e9`. **처분 계획이며 전환/삭제 완료 증거가 아니다.**
실행 경로·규범 이관 상태의 정본은 기존
[MIGRATION-CONFORMANCE-REGISTER.csv](../../tos-spec/src/MIGRATION-CONFORMANCE-REGISTER.csv)와
[설명 문서](../../tos-spec/src/MIGRATION-CONFORMANCE-REGISTER.md)다.
이 문서는 그 ID를 유지하고 제품·연구·운영 기능의 작업 순서를 보완한다.
정본 레지스터를 복사하거나 완료 상태를 독립적으로 승격하지 않는다.

## 1. 공통 처분 기준

| 처분 | 의미 | 삭제 조건 |
|---|---|---|
| 유지 | TOS 밖 연구·데이터·제품 기능으로 존속 | 현재 삭제 대상 아님; 주문 권한 연결 여부는 별도 조사 |
| 동결 후 대체 | 기존 동작의 추가 확장을 멈추고 TOS 구현으로 전환 | 아래 G1~G5 모두 충족한 scope에 한함 |
| 콘텐츠 이관 | 전략 의미·상품/계좌 지식·위험 정책을 DSL/profile/config로 재저작 | 동등성/의도된 차이 승인과 대체 소비자 검증 후 이전 콘텐츠 종료 |
| 임시 브리지 | 직렬화 조회 경계로 점진 연결 | 모든 소비자 이동, 장애/복구 관측 후 브리지 축소 |
| 이식 금지 | legacy execution/KIS/service 구현을 TOS에 복사하거나 import하지 않음 | 코드 이전 대신 규범과 관측 증거를 입력으로 새 구현 |

## 2. 기능 inventory

caller는 소스상 경로이며 실제 호스트의 활성 프로세스라는 뜻이 아니다.
각 행의 담당자는 역할 기준이며 특정 개인에게 배정 완료됐다는 뜻이 아니다.

| 기능 / 기존 ID | 현재 owner·caller / 데이터 소유자 | 처분·목표 | 검증 / 책임 역할 |
|---|---|---|---|
| 주식·선물 monolith / LEGACY-001·002 | `services/trading/orchestrator.py` → `shared/execution/executor.py`; legacy ledger/state | 동결 후 scope별 대체; runtime driver+kernel authority+gateway | 주문·거부·위험 소비·복구 비교; Runtime 담당 |
| 선물 decoupled router / LEGACY-003 | `services/order_router/main.py`; stream/legacy 실행 상태 | 동결 후 대체; TOS 단일 send authority | 오래된 queue·재시도·프로세스 재시작이 이중 전송을 못 만드는 증거; Execution 담당 |
| 주식 paper router / LEGACY-004 | `services/stock_order_router/main.py`; VirtualBroker/legacy ledger | paper 비교용 임시 유지; 첫 tenant 선택과 별개 | 동일 입력 판단 비교, live authority로 오인 금지; Strategy 담당 |
| 공통 executor / LEGACY-005 | `shared/execution/executor.py`; 위 caller들과 수동 도구 | 이식 금지, 소비자 0 증명 후 폐기 | 정본 census와 broker symbol 역검색, G1~G5; Execution 담당 |
| 수동 flatten / LEGACY-006 | `scripts/trading/flatten_all.py`; 직접 broker 경로 | 실행 금지 경로 inventory에 유지; 앱 API로 포장하지 않음 | 정본의 실전 기본값/직접 sender 위험 보존; Ops 담당. 실전 선물 주문은 정책 차단 |
| 수동 복구 / LEGACY-007 | `scripts/trading/recover_positions.py`; broker GET와 sentinel | 읽기 조사 도구로 분리; resume 판정은 runtime recovery/recon | 정본의 sentinel 소비자 부재를 해결 완료로 표시하지 않음; Recovery 담당 |
| 전략·위험 콘텐츠 | `shared/strategy/`, `config/strategies/`, `shared/risk/`; monolith/전략 서비스 | DSL·governed policy로 콘텐츠 이관; 중복 risk authority는 전환 뒤 제거 | 진입/청산/수량/거부 사유·long/short·재시작 비교; Strategy/Risk 담당 |
| KIS 시세·수집·상품 지식 | `shared/kis/`, `services/market_ingest/`, `services/screener.py`; Redis/Parquet | 수집·연구 유지, TOS intake/profile는 별도 구현 | source/time/상품 식별·읽기와 주문 경로 분리; Market Data 담당 |
| 백테스트·최적화 | `shared/backtest/backend.py`, `cli/main.py`; 연구 산출물 | 외부 연구 도구 유지; TOS 판단 비교는 독립 산출물로 | vectorbt 기본값과 legacy fallback 보존, fallback 사용 0 이전 엔진 삭제 금지; Research 담당 |
| 저장소·원장 | `shared/storage/`; legacy services/연구 | legacy 데이터 보존; TOS SQLite durable set과 소유권 분리 | 단순 파일 복사로 상태 이전 금지, 대사·retention·복원 증거; Data/Ops 담당 |
| dashboard·UI | `services/dashboard/`, `strategy-builder-ui/`; 기존 API/화면 | 유지 + TOS 조회 브리지; TOS write는 별도 명령 계약 이후 | schema/version/unknown/freshness·배포 mount·인증 확인; Product 담당 |
| 알림·스케줄러 | `services/`, 기존 운영 설정; legacy alert/cron 소비자 | 전달 기능 유지, TOS projection 소비는 별도 연결 | dedup·장애 알림·ack 의미·재시작 검증; Ops 담당 |

주요 소스 근거: [monolith](../../services/trading/orchestrator.py),
[executor](../../shared/execution/executor.py), [futures router](../../services/order_router/main.py),
[stock router](../../services/stock_order_router/main.py),
[backtest dispatch](../../shared/backtest/backend.py),
[TOS interfaces](../architecture/tos-public-interfaces.md).
연구·제품 기능의 '유지'는 레거시 거래 런타임 개발 재개를 의미하지 않는다.

## 3. scope별 cutover·rollback·삭제 게이트

scope = 환경·계좌·상품·전략·세션 및 authority generation을 식별하는 전환 단위다.
실계좌 식별자와 키는 문서 대신 비밀 설정을 참조한다. 현재 모든 행은 **전환 미인증**이다.

1. **G1 inventory:** 정본 ID, active caller/수동 진입점/queue/credential/network 경로,
   데이터 owner·보존 기간·담당 역할을 전수 확인한다. 모르는 caller는 미해결로 남긴다.
2. **G2 parity:** 고정된 동일 입력과 config digest로 판단·수량·가격·거부·risk consumption을
   비교한다. 차이는 결함/승인된 정책 차이/자료 부족으로 분류하고 마지막 두 범주를 숨기지 않는다.
3. **G3 single authority:** 이전 sender를 비활성화하고 credential/network fence,
   queued-work 무효화·세대 전환·미결 attempt 대사를 증명한 뒤 새 sender를 허용한다.
   env flag 하나만 변경한 것은 증거가 아니다. 비교 실행은 두 broker sender를 켜지 않는다.
4. **G4 observation and rollback:** 관측 기간과 통과 기준은 선택 scope 계획의 config/정책으로 확정한다.
   실패 시 신규 authority를 먼저 차단하고 미결 주문·receipt·RCL·broker 상태를 대사한다.
   구세대 재활성화는 새 generation/권한 검증 뒤에만 한다. reconciliation 불확실 상태는 중단 유지.
   DB를 과거 파일로 덮어쓰는 rollback은 금지한다. paper drill로 이 순서를 입증한다.
5. **G5 deletion:** 모든 caller·cron·이미지·runbook·credential/network 우회 경로 제거,
   데이터 보존/복구 확인 및 rollback 의존 종료를 증명한다. 정본 상태와 이 표를 함께 갱신한다.

행별 실행 티켓은 `ID / scope / active callers / data owner / replacement / parity artifact /
cutover evidence / rollback drill / deletion condition / owner / status`를 채운다.
아직 정해지지 않은 scope·관측 기간·담당자는 숫자나 이름을 발명하지 않고 `UNASSIGNED`로 둔다.

## 4. 다음 작업

먼저 read-only Control Plane을 구현한 뒤 첫 tenant 하나를 선정한다.
[단계별 계획](../plans/2026-10-06-tos-control-plane-and-first-tenant-plan.md)의 CP-0~CP-4를 따른다.
기존 레거시 paper 재배포나 실전 선물 프로브를 이 문서의 자동 후속 작업으로 실행하지 않는다.
