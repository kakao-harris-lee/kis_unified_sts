# TOS public interface catalog

기준: 2026-10-06, `5c4f38e9`. [공식 계층](tos-system-context.md)의 인터페이스 목록.
여기서 public은 지정된 소비자에게 노출된 경계라는 뜻이며, 모든 Python 심볼을
제품 SDK 또는 안정된 원격 API로 승인한다는 뜻이 아니다. 정확한 타입·필드는
아래 코드 정본을 따른다. `_` 모듈은 설명을 위한 구현 근거이며 외부 import 계약이 아니다.

## 1. 제품·운영 외부 표면

| ID | 표면 / 소유자 → 소비자 | 입력·출력 및 실패 의미 | 상태 / 근거 |
|---|---|---|---|
| EXT-01 | Operator projection / runtime → dashboard | schema v1 JSON; generation·monotonic export time·non_authorizing·운영 사실. 원천 없음은 null. 임시 파일 후 atomic replace. | 구현. [producer](../../tos/runtime/src/tos_runtime/operator/projection.py), [exporter](../../tos/runtime/src/tos_runtime/operator/export.py) |
| EXT-02 | `GET /api/tos/projection` / dashboard → 제품 UI | `available`, `reason`, `age_seconds`, `projection`. 파일 경로는 응답에 없다(서버 로그만). unavailable 사유는 다섯 접두 중 하나다 — `projection file absent` · `cannot read projection: <예외>`(권한·경로) · `invalid json: <예외>`(최상위가 객체가 아니면 예외 이름 없는 상수 `invalid json: top-level value is not an object`) · `unsupported schema_version (expected N, got <타입>)` · `schema mismatch at <위치>: <예외>`(위치를 못 읽으면 ` at …` 없이 `schema mismatch: <예외>`). 사유는 파일에서 읽은 값을 담지 않는다(위치의 매핑 키는 `<key>`). 신규 extra 필드는 무시; 미지원 version은 거부. | API 및 `/tos` UI 구현, 2026-10-06 배포됨(missing·auth 상태 검증 완료; 첫 정상 paper 세션 export 는 미관측 — `docs/PROJECT_STATUS.md` 제품 통합 행). [route/DTO](../../services/dashboard/routes/tos_projection.py), [tests](../../tests/unit/dashboard/test_tos_projection.py), [사유 접두 fixture](../../tests/fixtures/tos/projection-reasons.json), [UI 매처](../../strategy-builder-ui/src/lib/dashboard/tos.ts) |
| EXT-03 | `python -m tos_runtime.compose` / 운영자 → runtime | `run`이 설정을 검증·조립·구동. 설정/권한 거부는 부팅 성공이 아니다. 자세한 플래그는 CLI parser와 런북 정본. | 구현. [CLI](../../tos/runtime/src/tos_runtime/compose/cli.py), [run dispatch](../../tos/runtime/src/tos_runtime/compose/_run_dispatch.py), [boot runbook](../runbooks/tos-paper-boot.md) |
| EXT-04 | 운영 CLI / 운영자 → durable state | `backup-set`, `cold-backup`, `restore-drill`, `migrate`, `rotate-key`, `rearm`, `ack-alert`; `nontrade-eval`은 저장소를 쓰지 않는 dry run, `print-digests`, `print-policy-digests`는 조회. 명령별 precondition·증거 계약은 구현에 귀속. | 구현. [CLI](../../tos/runtime/src/tos_runtime/compose/cli.py), [CLI tests](../../tos/runtime/tests/compose/test_cli.py), [cold-backup tests](../../tos/runtime/tests/compose/test_cold_backup_cli.py) |
| EXT-05 | 향후 operator command ingress / Control Plane → runtime | 명령 식별자·actor·scope·generation·승인 참조·durable 결과의 설계 필요. | **미구현/제안**. 현재 HTTP command API가 있다는 뜻이 아님. |

EXT-01/02의 `age_seconds`는 파일 mtime 기반이다. `available=true`는 parse 가능을
뜻하며 fresh·healthy·거래 허용을 뜻하지 않는다. monotonic timestamp를 다른
프로세스/호스트의 벽시계와 빼서 freshness로 쓰지 않는다. threshold는 후속 설정 계약에서 정한다.
읽기 경로는 `TOS_OPERATOR_PROJECTION_PATH`로 지정되며 생산 경로와 실제 mount의
일치 여부는 배포 검증 항목이다. producer/API/UI가 `tests/fixtures/tos/operator-projection-v1*.json` 계약 fixture를 공유한다.
`protective.last_verdict`는 6키 객체(`derestriction_admissible`·`capacity_exhausted`·
`classification`·`unevaluated`·`reasons`·`protective_classification_digest`)이며
producer 키 집합은 DTO 테스트가 producer 소스에서 직접 대조한다(역방향 import 없음).
EXT-02의 사유 접두는 `tests/fixtures/tos/projection-reasons.json`이 정본이고
Python 방출기와 TS 매처 양쪽이 그 파일을 단언한다. 다만 CI 게이트는 Python 쪽뿐이다 — `.github/workflows/` 에 node 잡(`setup-node`·vitest·tsc)이 없어 TS 단언은 로컬·리뷰에서만 돈다.
전체 schema 생성 산출물은 없으며 fixture가 schema 전체를 대체하지 않는다.
그룹 전체와 미해결 알림 목록의 null도 원천 없음으로 보존한다.

EXT-04의 CLI `restore-drill`은 non-live 복원과 digest 검증까지다.
full replay/readiness 판정은 아래 INT-06의 전략별 호출자가 필요하다.
CLI exit 0만으로 전체 복구 훈련 성공을 보고하지 않는다.

## 2. 런타임 내부 통합 표면 — 제품에서 직접 호출 금지

| ID | 인터페이스 | 소유자 / 허용 소비자 | 계약과 근거 |
|---|---|---|---|
| INT-01 | `compose_paper_runtime(...) → ComposedRuntime` | runtime compose / runtime entrypoint·hermetic tests | config/data/custody 경로, environment, 필수 `ConstructionConfig`; release 거부는 예외. [exported surface](../../tos/runtime/src/tos_runtime/compose/__init__.py), [signature](../../tos/runtime/src/tos_runtime/compose/root.py) |
| INT-02 | `EngineDriver.enqueue_and_run`, `run_once`, `run_until_idle` | runtime engine / runtime producers | durable inbox·ordering·evidence를 거치는 event 처리. 일반 웹 요청용 enqueue API가 아니다. [driver](../../tos/runtime/src/tos_runtime/engine/driver.py) |
| INT-03 | `ObservationIntake.poll`, `DurableSnapshotStore` | runtime marketfeed / scheduler·adapter | 관측 입력과 durable snapshot 저장·조회; 검증된 시간/출처를 가진 커널 입력으로 연결. [ports](../../tos/runtime/src/tos_runtime/marketfeed/ports.py) |
| INT-04 | `Transport.send_once` | kernel brokeradapter / runtime transport | 전송 결과 계약; gateway 검사를 우회한 직접 호출은 앱 통합 방법이 아니다. [protocol](../../tos/src/tos/brokeradapter/protocol.py), [transport selection](../../tos/runtime/src/tos_runtime/compose/_transport_wiring.py) |
| INT-05 | `EvidenceAppendPort`, `CredentialCustody`, `KeyProvider`, `BrokerWitness`, `EvidenceReceiptReader` | 각 runtime owner / compose로 결선한 내부 소비자 | 증거 append, credential lifetime, 키 세대, 브로커 증언·receipt 조회. [evidence](../../tos/runtime/src/tos_runtime/evidence/ports.py), [custody](../../tos/runtime/src/tos_runtime/custody/ports.py), [recon](../../tos/runtime/src/tos_runtime/recon/ports.py) |
| INT-06 | `backup_set`, `restore_set`, `restore_drill` | runtime operations / 운영 CLI·전략별 drill caller | durable-set manifest·검증 복원·재생 판정을 구분. [implementation](../../tos/runtime/src/tos_runtime/operations/backup_set.py), [tests](../../tos/runtime/tests/operations/test_backup_set.py) |

## 3. 변경 규율과 후속 계약

- 현재 Python 표면의 안정된 버전 정책은 별도 확정되지 않았다. 새 소비자를 추가할 때 소유자·호환성·실패 계약을 함께 갱신한다.
- projection schema 변경은 producer/DTO/fixture를 같은 변경 범위에서 대조한다. JSON fixture 공유가 Python 역방향 import를 허용하지 않는다.
- 신규 command는 기존 CLI의 권한·세대·승인·증거 검사를 재사용할 수 있는지 먼저 분석한다. 모든 CLI가 이미 공통 command envelope를 지원한다고 가정하지 않는다.
- `_wiring`, DB 테이블, private helpers는 공개 확장점이 아니다. UI/BFF의 직접 SQLite write는 금지한다.
- 이 카탈로그는 호스트 경로·계좌·시크릿·실행 승인을 배포하지 않는다. 운영 명령은 해당 런북을 따른다.
