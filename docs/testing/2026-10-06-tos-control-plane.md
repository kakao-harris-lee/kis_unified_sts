# CP-1 조회 전용 TOS 운영 화면 — 구현 및 검증

2026-10-06. 브랜치 `feat/tos-control-plane-readonly`, 별도 worktree.
문서 정리 PR #860 이후 후속 구현. 실제 거래·paper 프로세스·cron·credential을 변경하지 않는다.

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
- 두 중립 JSON fixture를 producer·API·UI가 대조. Python 역방향 import 없음.
- Next proxy는 정확히 `GET /api/tos/projection`만 추가. 다른 TOS 경로와 쓰기 요청은 거부.
- Compose는 기존 경로를 기본으로 유지하며 projection 디렉터리와 읽기 경로를 env로 선택 가능.

## 운영 연결 조건

현재 호스트 read-only 확인:

- `kis_paper-dashboard`의 `/app/data/tos_runtime` mount는 writable=false.
- 인증된 내부 GET 결과 `available=false`, `reason=projection file absent`, `age_seconds=null`.
- 현재 호스트 paper session wrapper/driver에서 `projection` 경로 연결이 검색되지 않았다.

따라서 이번 구현을 **운영 중 TOS의 실시간 화면 배포 완료**로 보고하지 않는다.
다음 운영 변경은 paper 코드 핀/래퍼의 소유 작업과 함께 진행해야 한다.

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
