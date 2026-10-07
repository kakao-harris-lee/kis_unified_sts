# TOS Control Plane and first tenant plan

작성: 2026-10-06. 기준 코드: `5c4f38e9`.
상태: **CP-0 문서 기반 정리 완료; CP-1 코드·출력 배선·조회 서비스 배포 완료, 실제 세션 출력과 재시작 identity 관측 완료(2026-10-07 — 남은 것은 재시작 뒤 장중 export 주기와 UI stale 렌더 화면); CP-3 착수 문서 작성(결정 대기); CP-2 이후 계획**. 실행·배포·live 승인 문서가 아니다.
기존 TOS Phase 번호와 구분하기 위해 이 계획만 CP-0~CP-4를 사용한다.

## 1. 목적과 선행 조사

이미 있는 Application Runtime을 기준으로 제품 조회 경계를 완성하고,
레거시 capability 하나를 paper tenant로 이관할 수 있는 검증 조건을 만든다.
현재 `compose`, driver, KIS mock/synthetic transport, 운영 CLI, projection/API를 재사용한다.
새 프레임워크·새 parser·새 앱 패키지는 이번 계획에 필요하지 않다.
현재 소스와 기존 설계를 조사한 문서 작업으로, 신규 라이브러리 선정은 수행하지 않았다.

- [계층과 의존성 정본](../architecture/tos-system-context.md)
- [공개/내부 인터페이스 목록](../architecture/tos-public-interfaces.md)
- [Legacy disposition](../migration/legacy-disposition.md)
- [기존 migration 정본](../../tos-spec/src/MIGRATION-CONFORMANCE-REGISTER.md)
- [기존 runtime 운영 배선 계획](2026-09-13-tos-runtime-operations-wiring-plan.md)
- [paper 부팅 런북](../runbooks/tos-paper-boot.md), [cold backup 런북](../runbooks/tos-evidence-cold-backup.md)

기각 대안: 새 `app/` 프레임워크는 runtime 중복, legacy executor 래핑은 방화벽 위반,
UI의 DB write는 권한·증거 경계 우회, 전면 삭제는 연구/운영 소비자 상실,
공유 Python DTO의 dashboard→runtime import는 역방향 방화벽 위반이다.

## 2. 선행 상태와 권한

2026-10-06 정적 검사: `tos_spec_status --check` PASS,
`tos_completion_status --check` GREEN(violations=0). 완료 관측에는
`planned_unassigned_pairs=749` 등이 남으며 restricted-live/production은 모두 NOT_AUTHORIZED다.
검사 GREEN을 전체 구현 완료로 읽지 않는다. 검사 정본은 각 도구와 규범 문서다.
고정된 Phase-0 completion contract 본문은 수정하지 않는다.

CP-1은 읽기 전용 제품 작업이다. CP-2는 우선 설계이며 위험 명령을 웹으로 노출하지 않는다.
CP-3/4는 paper 범위다. 실전 선물 주문/증거금 투입은 영구 정책 차단이며
live 승인이나 실전 fill을 이 계획의 완료 조건으로 요구하지 않는다.

## 3. 단계·담당 역할·산출물·완료 기준

### CP-0 — 현재 문서와 책임 정렬

담당: 문서/아키텍처 작성자. 이번 변경 범위.

- [x] `tos/CLAUDE.md` skeleton 문구를 구현 상태로 교체하고 firewall 방향을 명시.
- [x] 공식 계층 명칭·소유자·허용 의존 방향 확정.
- [x] 외부 계약과 내부 포트를 나눈 공개 인터페이스 카탈로그 작성.
- [x] PROJECT_STATUS에 현재 TOS 검사/구현/운영 미확인 상태 분리.
- [x] 기존 migration 정본에 연결한 처분표와 CP 단계 작성·색인 연결.

완료 기준: 코드 근거/상대 링크 실재, 문서간 명명 일치, frozen contract·runtime 코드 무변경.

### CP-1 — 조회 전용 TOS 운영 화면

담당 역할: Product UI + dashboard + Runtime projection + Ops.
구현 순서: 계약 fixture → API 소비 → UI → 배포 관측.

재사용: EXT-01/02, 기존 dashboard 인증과 프론트 API client, 기존 화면 컴포넌트.
최소 새 표면: TOS 상태 화면, schema v1 JSON fixture/계약 검사, freshness 설정.

- recovery/release/safety/currentness/RCL/inbox/evidence/backup/alert 상태를 읽기 전용으로 표시.
- missing/invalid/unsupported/unknown/stale를 구분. null을 정상값으로 변환하지 않음.
- freshness 기준·polling 간격은 설정으로 관리; API `available`과 건강 상태를 분리.
- producer와 DTO의 필드·null·version 호환성을 독립적으로 대조한다. fixture는 중립 JSON 경로를
  사용하고 Python import 공유를 추가하지 않는다. 파일 위치는 구현 시 기존 test fixture 관례를 따른다.
- producer 경로/consumer env/읽기 전용 volume/권한을 대조하고 export 정지 시 UI stale 전환을 확인.
- backend 응답의 내부 path를 UI에 그대로 노출할 필요는 없다. 인증 실패·응답 오류도 처리한다.

완료 증거: schema fixture 테스트, missing/malformed/version/unknown/stale UI 테스트,
배포에서 producer→API→화면 연결 확인과 exporter 정지 관측. 조회 성공은 거래 승인 근거가 아니다.
롤백: 화면·조회 연결을 비활성화하며 runtime 거래/증거 데이터는 변경하지 않는다.

### CP-2 — 운영 명령 계약 설계

담당 역할: Runtime authority/recovery + API/auth + Ops.
선행: CP-1의 identity·freshness·읽기 계약.

산출물은 명령별 설계 표다: 대상 CLI, actor/role, scope, command ID,
expected generation, 승인 reference, 입력 digest, 중복 처리, TTL/만료,
권한 취소·재시작·결과 receipt/evidence, 실패 시 운영 절차.
각 항목은 기존 명령이 이미 만족하는지/새 seam이 필요한지 명시한다.

최초 범위는 `ack-alert`의 의미 분석과 조회 결과 확인이다. ack를 rearm/resume으로
해석하지 않는다. `rearm`, key rotation, migrate, 주문 명령은 위험도가 다른 별도 결정이다.
전달 방식을 파일/IPC/HTTP 중 미리 구현하지 않고 인증·재전송·durability 비교 후 정한다.

완료 기준: stale generation, 만료·취소 승인, 중복 command, runtime crash, scope 불일치,
읽기 사용자 권한 상승의 거부/복구 시나리오가 명령별로 정의됨.
설계 완료는 API 구현 승인이 아니다. 운영자의 범위 결정 후 별도 구현 작업으로 전환한다.

### CP-3 — 첫 paper tenant 콘텐츠 이관

담당 역할: Strategy + Risk + Runtime + Data.
CP-2의 원격 명령 구현은 선행 조건이 아니다. 기존 CLI로 paper 검증할 수 있다.

선행 선택표: 전략 하나·상품 하나·paper 환경·시세 데이터·정책 digest·검증 기간·담당자.
전략 선택은 **미정**. 현재 `bootproof_band`는 부팅 증명 콘텐츠이며 경제적 전략 이관 완료가 아니다.
후보는 레거시 의존도, DSL 표현 가능성, 데이터 가용성, long/short 검증 가능성으로 비교한다.

- 규칙·청산·수량·위험 정책과 Critical Inputs를 추출하고 DSL/config로 재저작한다.
- 동일 입력의 legacy/TOS 산출물을 별도 실행하여 비교. 직접 import·이중 broker 전송 없음.
- 동일성 대신 의도된 정책 차이를 허용하려면 차이별 승인 근거를 남긴다.
- restart/replay/reconciliation/backup restore, partial/duplicate/unknown receipt를 포함한다.
- 주식 swing EOD 일괄청산 금지, 선물 long/short 대칭을 보존한다.
- full restore drill은 전략별 `restore_drill` caller로 readiness까지 검증한다.

완료 증거: 이관 artifact+digest, 입력 dataset lineage, 판단/거부/risk 차이 보고서,
양방향·재시작·복구 증거. 해결되지 않은 차이는 미해결로 남긴다.
롤백: 후보 paper 실행을 차단하고 비교 산출물/증거를 보존한다.

### CP-4 — paper scope 전환과 레거시 축소

담당 역할: Runtime/Execution + Ops + Data. 선행: CP-3와 해당 scope의 승인된 처분표.
[Legacy G1~G5](../migration/legacy-disposition.md#3-scope별-cutoverrollback삭제-게이트)를 적용한다.

순서: old sender fence → queue/attempt 대사·세대 전환 → new sender 허용 → 관측 →
rollback drill → rollback 의존 종료 → caller 없는 legacy 코드 삭제.
각 단계의 artifact와 정본 레지스터 상태를 함께 갱신한다.
관측 기간·중단 기준은 scope 계획에서 정하며 이 문서는 숫자를 발명하지 않는다.

완료 조건: 동일 scope에 단일 send authority, old queue/retry 재실행 거부,
데이터 보존·복구, 수동/cron 우회 경로 제거, deletion census.
실전 범위 전환은 이 단계에 포함하지 않는다.

## 4. 미결 결정과 다음 착수점

| 결정 | 필요 시점 | 정직한 현재 상태 |
|---|---|---|
| UI `/tos` 독립 화면 또는 Cockpit 섹션 | CP-1 구현 시작 | 미정; 기존 UI 탐색 후 최소 변경 선택 |
| freshness/polling 수치·배포 projection 경로 | CP-1 배포 검증 전 | 미정; 설정으로 기록하고 실제 export 주기 검증 |
| command 범위·전달 방식·승인 책임 | CP-2 설계 완료 | 미정; 기존 CLI 우선 |
| 첫 tenant 전략/상품/기간/담당자 | CP-3 시작 | 결정됨 2026-10-07 — Setup D (CP-3 착수 문서 §4) |
| scope별 rollback 종료·삭제 시점 | CP-4 삭제 전 | 미정; 관측 증거 필요 |

CP-1 구현 상태는 §6과 [검증 기록](../testing/2026-10-06-tos-control-plane.md)을 따른다.
명령/거래 런타임 변경이나 운영 배포는 수행하지 않았다. 기존 paper 운영·장기 증거 측정은 해당 런북을 따른다.

## 5. 이번 문서 검증

문서 변경 후 링크·소스 경로·diff whitespace·방화벽·spec/completion 정적 검사로 확인한다.
코드 변경이 없으므로 전체 pytest/Gradle/프론트 빌드는 실행하지 않는다.
독립 계획 심판/PR/배포는 이번 문서 작성의 완료 상태에 포함하지 않는다.

## 6. CP-1 구현 범위 확정 — 2026-10-06

중복 조사: 원격 최신 main `5c4f38e9`, 열린 PR 0(문서 #860 생성 전),
Claude 최신 기록은 #859 월물별 data-dir/backup 종료. `wt-paper`, `wt-cold`,
P8/evidence 워크트리는 clean. 미병합 원격 `feat/setup-d-decoupled-port`는
Setup D/decision engine 경로이며 TOS UI와 겹치지 않는다. 실행 중인 Claude
프로세스 자체를 작업 없음의 증거로 보지 않고 CP-1은 별도 worktree로 격리한다.

선택: `/tos` 전용 조회 화면 + 기존 Navigation 한 항목. dashboard axios client와
TanStack Query의 기존 polling을 재사용한다([공식 polling 문서](https://tanstack.com/query/latest/docs/framework/react/guides/polling)).
별도 state/store/framework는 추가하지 않는다. UI 표시용 poll/freshness/timer는
`strategy-builder-ui/src/config/tos-control-plane.json` 한 곳에 둔다.
15초 조회·60초 stale는 UI 경고 기본값이며 거래/위험 게이트 임계값이 아니다.

추가 발견: producer는 그룹 전체 또는 unresolved alert 목록을 null로 내보낼 수 있지만
기존 dashboard DTO가 이를 거부한다. 원천 없음 보존을 위해 nullable DTO로 정렬한다.
중립 JSON fixture를 runtime producer·dashboard consumer·UI 테스트가 함께 사용하며
runtime source 변경과 Python 역방향 import는 없다.

배포: #861은 main `af43fd8a`에 병합했고 dashboard·UI만 갱신했다. host wrapper/driver에
기존 `--projection-path`를 연결했다. 전용 디렉터리는 deploy 소유 0700이며 dashboard는
읽기 전용으로 마운트한다. scratch/override 세션은 session-local 파일로 격리한다.
cron·코드 핀 정책·커널·durable set은 변경하지 않았다.

실제 마운트와 인증, `/tos`의 missing 표시를 확인했다. 현재 paper 세션이 정지해 있어
실제 export generation 증가·종료 후 stale 관측은 다음 정상 세션에서 확인해야 한다.
Claude 독립 리뷰는 token 한도로 미실행이며 자체 점검·CI 통과와 구분한다.
[출력 연결 런북](../runbooks/tos-paper-projection-connection.md)과
[배포 검증 기록](../testing/2026-10-06-tos-control-plane.md)을 참조한다.
