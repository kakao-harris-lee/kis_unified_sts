# CP-1 조회 전용 TOS 운영 화면 — 구현 및 검증

2026-10-06. 브랜치 `feat/tos-control-plane-readonly`, 별도 worktree.
문서 정리 PR #860 이후 후속 구현. #861을 main `af43fd8a`에 병합하고 조회 서비스를 배포했다.
후속 출력 배선은 host wrapper/driver 인자만 변경했다. 실제 거래·cron·credential은 변경하지 않았다.

## 중복 확인

확인 시 main `5c4f38e9`, 문서 PR 생성 전 열린 PR 0.
Claude의 저장된 마지막 완료 작업은 #859 월물별 durable-set·콜드 백업 정리다.
`wt-paper`, `wt-cold`, P8 및 P02 evidence worktree는 clean이었다.
미병합 원격 `feat/setup-d-decoupled-port`는 2026-09-09 Setup D/decision-engine 작업이며
projection 또는 `/tos` 화면을 구현하지 않는다. Claude 프로세스는 실행 중이므로
진행 의도를 단정하지 않고, CP-1을 별도 branch/worktree로 격리했다.

## 구현

- `/tos`: recovery/release/safety/currentness/RCL/inbox/evidence/backup/alert 조회. 명령 버튼 없음.
- `available=true`와 정상·거래 권한을 분리. null/false/0 보존.
- missing, malformed, unsupported, unknown, stale, auth/network failure 별도 표시.
- UI 경고용 설정은 `strategy-builder-ui/src/config/tos-control-plane.json`.
  15초 poll, 60초 stale, 1초 경과 갱신. runtime monotonic time과 브라우저 시계는 비교하지 않음.
  API 파일 age에 브라우저 monotonic 경과를 더해 요청이 멈춰도 캐시가 늙는다.
- dashboard DTO는 producer의 whole-group null 및 unknown alert 목록을 보존한다.
- 두 중립 JSON fixture(`tests/fixtures/tos/operator-projection-v1*.json`)를
  dashboard 테스트·UI 테스트·runtime 테스트가 모두 읽는다. 다만 runtime 쪽
  `test_shared_product_contract_fixture`는 fixture의 그룹을 projection의 reader로
  갈아끼워 **assembler pass-through만** 증명한다 — 실제 `_operations_wiring`
  reader는 거치지 않으므로 producer의 키 집합을 검증하지 않는다.
  producer 키 집합은 별도로 `tests/unit/dashboard/test_tos_projection.py::
  test_protective_last_verdict_matches_the_producer_key_set`가 producer **소스**를
  `ast`로 읽어 DTO 필드와 대조한다(import 없음). Python 역방향 import 없음.
- Next proxy는 정확히 `GET /api/tos/projection`만 추가. 다른 TOS 경로와 쓰기 요청은 거부.
- Compose는 기존 경로를 기본으로 유지하며 projection 디렉터리와 읽기 경로를 env로 선택 가능.
  두 변수(`TOS_OPERATOR_PROJECTION_DIR` 호스트 디렉터리 · `TOS_OPERATOR_PROJECTION_PATH`
  컨테이너 파일)는 한 쌍이며 `.env*.example` 넷과 compose 주석에 기록했다.
- 응답 본문은 projection 파일 경로를 싣지 않는다. 대신 unavailable 분기가
  **WARNING**으로 남긴다 — 이 앱은 자체 로깅 설정이 없고 uvicorn 기본 INFO 라
  DEBUG 는 아무에게도 닿지 않는다. 라우트는 `/tos` 를 연 동안만 돌므로
  15 초 폴링이 배경에서 로그를 쌓지 않는다.
- 어떤 `reason` 도 projection 파일에서 읽은 **값**을 담지 않는다. 버전 불일치는
  값이 아니라 타입을, schema mismatch 는 DTO 로 해석한 위치를 보고한다
  (매핑 키는 `<key>` 로 가린다 — 키도 파일에서 온다).
- 사유 접두 다섯은 `tests/fixtures/tos/projection-reasons.json` 하나에 있고,
  Python 방출기(라우트 소스 AST)와 TS 매처가 같은 파일을 단언한다.
- 파일을 **열지 못한 경우**(권한·uid·디렉터리)는 `cannot read projection: <예외>`로
  형식 오류와 구분해 보고하고 화면도 별도 상태로 표시한다.

## 운영 연결 조건

배포 전 호스트 read-only 확인:

- `kis_paper-dashboard`의 `/app/data/tos_runtime` mount는 writable=false.
- 인증된 내부 GET 결과 `available=false`, `reason=projection file absent`, `age_seconds=null`.
- 현재 호스트 paper session wrapper/driver에서 `projection` 경로 연결이 검색되지 않았다.

아래는 배포 전 확인한 연결 조건이다. 적용 결과는 마지막 배포 기록을 따른다.
**운영 중인 TOS의 실제 출력 갱신까지 확인한 것으로 보고하지 않는다.**

1. producer가 쓸 전용 projection 디렉터리와 파일을 확정한다. custody/durable-set 디렉터리 전체를 마운트하지 않는다.
2. runtime의 기존 `--projection-path`와 아래 consumer 좌표를 맞춘다.
3. host 설정에서 `TOS_OPERATOR_PROJECTION_DIR`은 projection 파일의 부모 디렉터리,
   `TOS_OPERATOR_PROJECTION_PATH`는 `/app/data/tos_runtime/<파일명>`으로 지정한다.
   기본값은 `./data/tos_runtime` / `/app/data/tos_runtime/operator_projection.json`이다.
4. 읽기 전용 **디렉터리** mount를 사용한다. 파일 단독 bind는 atomic replace 뒤 오래된 inode를 볼 수 있다.
5. 배포는 기존 `scripts/deploy_paper.sh`·운영 런북 절차를 따른다. 이 문서만으로 실행하지 않는다.
6. producer 세대 변화→API→UI를 확인하고 exporter 중단 후 stale 전환을 관측한다.
   인증 거부·mount 권한·missing·재시작·exporter 복귀를 확인한다.

rollback은 UI/조회 연결을 이전 버전으로 되돌리는 범위다. runtime DB나 authority를 되돌리지 않는다.

## 검증 기록

- Dashboard projection 테스트: 10개 통과(인증, 계약 fixture, null, GET-only 포함).
- Runtime projection 테스트: 25개 통과(공통 fixture 포함).
- Frontend: 전체 39파일/257테스트 통과; 변경 파일 ESLint·TypeScript 통과.
- Compose config 및 `git diff --check` 통과.
- Production build 통과(`/tos` 정적 route 포함).
- Chromium production-build 브라우저 검증: desktop, 390px mobile overflow 없음,
  null/stale/missing/invalid/unsupported/auth 상태 및 page error 0 확인.
  중립 fixture를 HTTP에서 대체한 화면 검증이며 실제 paper 운영 연결 증거가 아니다.
  로컬 캡처: `/tmp/kis-cp1-artifacts/desktop.png`, `mobile-unknown.png` (비커밋).
- `tos_firewall_check.py` PASS. Runtime 테스트 mypy는 CI와 같은
  `--disable-error-code=no-untyped-def` 옵션을 사용한다(기존 fixture helper 규칙).

## 출력 연결 후속 변경

[운영 연결 런북](../runbooks/tos-paper-projection-connection.md)에 host 패치,
producer/consumer 좌표, scratch 격리, 배포 및 복구 절차를 구체화했다.
Dashboard 회귀 테스트는 33개로 증가했다. 잘못된 UTF-8, atomic replace 중
age/content 일관성, 미래 mtime unknown 처리를 포함한다. host wiring 검증은
실행 없이 7개 경로 선택, 상대 경로 abort 1건(래퍼 자신의 `abort()` 를 추출해
실행하므로 래퍼에서 `abort` 가 사라지면 게이트가 FAIL 한다), 래퍼 자신의
기본 published 경로(절대·`operator_projection.json`·세션 로컬 아님·
`TOS_PAPER_PROJECTION_PATH` 로 덮어쓰기 가능), driver 인자 유무를 확인한다.
Claude 독립 리뷰는 token 한도로 실행되지 않았으며 자체 점검과 구분한다.

## 배포 기록 — 2026-10-06 20:14 KST

- #861 최종 코드 `bb394cb1`의 모든 CI 통과(스케줄 실패 보고 작업만 해당 없음으로 skip).
  main 병합 `af43fd8a`. Claude 독립 리뷰 미실행은 그대로 유지한다.
- host preimage SHA와 정지 상태를 확인하고 wrapper/driver 설치. 커밋된 패치를
  별도 사본에 재적용해 설치 파일과 byte-identical임을 확인했다.
- private backup: `~/.local/state/tos/paper-ops/projection-connection-20261006/`.
  원본 script와 비밀 설정 백업은 Git에 포함하지 않는다.
- `.env.paper`의 projection 좌표 두 개 설정, 전용 디렉터리 uid/gid 1000·0700.
  실제 dashboard mount는 `paper-projection` → `/app/data/tos_runtime`, `rw=false`.
- 새 이미지의 uid 1000에서 읽기 성공·쓰기 거부·같은 container에서 atomic replace
  후 새 내용 읽기를 검증했다. 별도 probe 파일은 삭제했고 운영 projection은 만들지 않았다.
- `scripts/deploy_paper.sh --services "dashboard strategy-builder-ui" --no-build --no-cleanup -y`
  통과. 앞서 해당 코드의 두 이미지를 빌드했다. 두 서비스 healthy, restart 0.
  배포 전후 container ID 비교에서 이 두 개 외 변화 없음.
- 실제 Caddy 경유 `/tos` 200, 브라우저의 인증 projection GET 200·available=false·missing.
  인증 없는 projection GET 401. API `Cache-Control: no-store` 확인.
  Chromium page errors 0, 390px 모바일 overflow 없음.
- 실제 paper 세션은 기동하지 않았다. 다음 정상 세션의 generation 증가와 종료 뒤 stale
  전환은 미확인이다. fixture 검증을 실제 세션 증거로 대체하지 않는다.
