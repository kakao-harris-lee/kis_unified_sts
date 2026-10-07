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
- 두 중립 JSON fixture(`tos/runtime/tests/fixtures/operator-projection-v1*.json`)를
  dashboard 테스트·UI 테스트·runtime 테스트가 모두 읽는다. 다만 runtime 쪽
  `test_shared_product_contract_fixture`는 fixture의 그룹을 projection의 reader로
  갈아끼워 **assembler pass-through만** 증명한다 — 실제 `_operations_wiring`
  reader는 거치지 않으므로 producer의 키 집합을 검증하지 않는다. 더 정확히는
  `OperatorProjection.build` 가 reader 반환값을 검증하지 않으므로 그 테스트에서
  **그룹 내용은 순수 에코**다. 실측: fixture 에서
  `protective_classification_digest` 를 지우면 runtime 테스트는 green 이고
  dashboard 의 `test_shared_projection_contract_fixtures` 만 red 다.
  따라서 fixture 내용을 DTO 와 대조하는 레인은 dashboard 쪽 하나뿐이다.
  producer 키 집합은 별도로 `tests/unit/dashboard/test_tos_projection.py::
  test_protective_last_verdict_matches_the_producer_key_set`가 producer **소스**를
  `ast`로 읽어 DTO 필드와 대조한다(import 없음). Python 역방향 import 없음.
- fixture 가 `tos/` 아래 있어도 그 dashboard 레인은 fixture 변경에 **돈다**.
  `.github/workflows/test.yml` 이 `paths-ignore` 대신 `paths` + 부정 패턴을 쓰고
  마지막 줄에서 `tos/runtime/tests/fixtures/**` 를 재포함하기 때문이다(패턴은
  순차 평가되고 뒤가 이긴다). 그 줄을 지우거나 `!tos/**` 위로 올리면 미러 단언과
  `SHARED_PROJECTION_FIXTURES` 핀이 동시에 fixture-only PR 의 사정권에서 빠진다.
- Next proxy는 정확히 `GET /api/tos/projection`만 추가. 다른 TOS 경로와 쓰기 요청은 거부.
- Compose는 기존 경로를 기본으로 유지하며 projection 디렉터리와 읽기 경로를 env로 선택 가능.
  두 변수(`TOS_OPERATOR_PROJECTION_DIR` 호스트 디렉터리 · `TOS_OPERATOR_PROJECTION_PATH`
  컨테이너 파일)는 한 쌍이며 `.env*.example` 넷과 compose 주석에 기록했다.
- 응답 본문은 projection 파일 경로를 싣지 않는다. 대신 unavailable 분기가
  원인별 레벨로 남긴다 — 세션 밖의 **정상** 상태인 `projection file absent` 는
  **INFO**, 실제 결함 셋(읽기 실패·invalid json·schema/version mismatch)은
  **WARNING**. 실측 근거: 이 앱은 로깅을 설정하지 않고 uvicorn 의
  `LOGGING_CONFIG` 는 `uvicorn`·`uvicorn.error`·`uvicorn.access` 셋만 선언하므로
  루트 로거에 핸들러가 없고 레벨은 WARNING 이다. 따라서 WARNING 은
  `logging.lastResort`(stderr)로 컨테이너에 보이고 INFO 는 아무 출력도 내지
  않는다. 탭 하나가 15 초마다 조회하므로 정상 상태를 WARNING 으로 두면
  시간당 240 줄이 보인다.
- 어떤 `reason` 도 projection 파일에서 읽은 **값**을 담지 않는다. 버전 불일치는
  값이 아니라 타입을, schema mismatch 는 DTO 로 해석한 위치를 보고한다
  (매핑 키는 `<key>` 로 가린다 — 키도 파일에서 온다).
- 사유 접두 다섯은 `tests/fixtures/tos/projection-reasons.json` 하나에 있고,
  Python 방출기(라우트 소스 AST)와 TS 매처가 같은 파일을 단언한다.
  TS 쪽은 #867 이 추가한 `.github/workflows/ui.yml`(체크 이름
  「UI suite (lint + build + tsc + vitest)」)이 돌린다. 그 잡은 필수 체크가 아니고
  경로 게이팅이므로 UI 경로를 건드리지 않는 PR 에서는 돌지 않는다.
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
Dashboard 회귀 테스트는 #864 커밋 `1836695b` 기준 33개로 증가했다
(#864 최종 head `f7d15736` 에서는 42개다 — 같은 아크의 서로 다른 head 수치다). 잘못된 UTF-8, atomic replace 중
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
  (이 두 항목은 2026-10-07 첫 실제 세션에서 관측했다 — 아래 절. 이 배포 기록 자체는
  2026-10-06 시점 그대로 둔다.)

## 첫 실제 세션 관측 2026-10-07

2026-10-07 첫 실제 paper 세션(08:45~15:45 KST, 세션 `2026-10-07-084508-LONG`,
data dir `/home/deploy/.local/state/tos/paper-data/A05610`)에서
[인계 기록](../runbooks/2026-10-06-tos-cp1-claude-handoff.md) §6 의 넷 중 셋을 관측했다.
아래 수치는 호스트에서 직접 뜬 세 지점의 원시 관측 그대로다.

| 지점 | 프로브 KST | 파일 mtime | 파일 gen | API gen | age 초 | `/tos` |
|---|---|---|---|---|---|---|
| T1 | 09:07:12 | 09:07:10 | 264 | 264 | 1.5 | 200 |
| T2 | 09:37:15 | 09:37:11 | 624 | 624 | 4.3 | 200 |
| T3 | 15:52:17 | 15:45:00 | 5033 | 5033 | 437.3 | 200 |
| T3' | 15:52:47 | 15:45:00 | 5033 | 5033 | 467.3 | — |

T3 와 T3' 는 같은 정지 상태를 30 초 간격으로 두 번 찍은 것이다. `/tos` 는 방문마다 한 번만
확인했으므로 표본은 넷이 아니라 셋이고 **세 방문 전부 200** 이다 — T3' 칸이 빈 것은 그
재프로브 시점에 따로 찍지 않았다는 뜻이다.

- **생성과 재작성.** 운영 projection 파일
  `/home/deploy/.local/state/tos/paper-projection/operator_projection.json` 하나가
  mode `0600` 으로 생겼다. 세 관측 시점 모두 그 디렉터리에는 이 파일 하나뿐이었다. T1→T2 는
  1803 초에 generation +360 이므로 약 5.0 초마다 재작성이다.
- **producer → 인증 API → `/tos` 값 일치.** Caddy 경유 인증 GET 이 세 지점 전부
  `available=true`·`reason=None` 이고 generation 이 같은 시점 파일과 같다(264·624·5033).
  `/tos` 도 세 지점 전부 200. producer 세대 변화가 조회 표면까지 같은 값으로 도달한다.
- **runtime identity 는 하루 종일 불변.** `cell_id` `paper`, `process_nonce` 접두
  `997451dd`, `code_digest`
  `ec20680a444cc9798ad601fbcda61edc05cee30d1c00f524c60b717c5f3a5044`,
  `runtime_generation` `0` — 세 지점 동일. 세션 worktree 는 `4010bc175d5f` 이고 digest 는
  `release.yaml` 과 일치했다.
- **stale 전환 — 관측한 것과 안 한 것.** 15:45:06 `stop: driver exited` 로 멈추고 그 뒤
  세션 프로세스 0, 마지막 쓰기는 15:45:00 이다. 정지 약 7 분 뒤 두 프로브의 age 가
  437.3 → 467.3 초로 경과하고 generation 은 5033 에 고정이다.
  [UI 설정](../../strategy-builder-ui/src/config/tos-control-plane.json)의
  `staleAfterSeconds` 가 60 이므로, UI 의 stale 판정을 구동하는 **API 입력**은 stale
  조건을 만족한다. **UI 가 실제로 stale 로 렌더한 화면은 확인하지 않았다** — 관측한 것은
  그 렌더를 구동하는 API age 뿐이고 브라우저 캡처는 없다.
- **미관측.** 인계 기록 §6 체크 4(재시작 뒤 runtime identity·generation 갱신).
  2026-10-07 은 하루 한 세션이라 같은 날 재시작이 없었고, 위 identity 네 값은 **불변**만
  보였다 — **변화** 쪽 증거는 아직 없다. UI stale 렌더 화면도 같다. 둘 다 다음 정상
  세션일의 관측 대상이다.

세션 보고서는
`/home/deploy/.local/state/tos/paper-sessions/2026-10-07-084508-LONG/report.json` 이다.
인증 GET 에 쓴 API 키는 이 기록에 담지 않는다.

## 재시작 관측 2026-10-07 17:32 — 인계 §6 체크 4

운영자 지시(「재시작이 필요하면 진행해」, 2026-10-07 오후)로 **같은 날** 같은 잎
`paper-data/A05610` 에 두 번째 세션을 손으로 띄웠다 — 세션 `2026-10-07-173223-LONG`.
래퍼는 cron 과 같은 `2c3284a4…` 이고 바뀐 것은 환경변수 `TOS_PAPER_MINUTES=7` 하나다:
15:45 이 지난 뒤의 `start` 는 이 값 없이는 「stop time already passed」로 ABORT 이고, 이
변수는 projection 을 session-local 로 격리하는 조건(`--selftest`·data-dir·instrument·
fake-date·worktree·calendar 우회)에 **들지 않으므로** 운영 파일에 그대로 쓴다. 정지는 cron 과
같은 `stop`(드라이버 SIGTERM)이고, 18:00 콜드 백업의 열린 핸들 검사 전에 스토어를 닫았다
(17:34:10 `driver exited`, `fuser` 0 건). 텔레그램 기동·종료 줄은 평소대로 나갔다(17:32:42 ·
17:34:11 `telegram notified`) — 기동 줄의 「정지 15:45 KST」는 래퍼 템플릿이고 실제 정지는
손 `stop` 이다.

| 지점 | 프로브 KST | 파일 mtime | 파일 gen | API gen | `process_nonce` 접두 | `runtime_generation` | age 초 | `/tos` |
|---|---|---|---|---|---|---|---|---|
| R0 | 17:31:58 | 15:45:00 | 5033 | 5033 | `997451dd` | 0 | 6433.1 | 200 |
| — | 17:32:23 `start` · 17:32:37 boot proof OK(14.33 s · genesis=no · baseline_seq 147922) | | | | | | | |
| R1 | 17:32:49 | 15:45:00 | 5033 | 5033 | `997451dd` | 0 | 6469.5 | 200 |
| R2 | 17:33:34 | 17:32:50 | 1 | 1 | `e431c2d8` | 0 | 44.3 | 200 |
| — | 17:34:06 `stop` → 17:34:10 `driver exited` rc=0 · `stop_reason=signal` | | | | | | | |
| R3 | 17:34:14 | 17:32:50 | 1 | 1 | `e431c2d8` | 0 | 84.1 | 200 |
| R3' | 17:34:36 | 17:32:50 | 1 | 1 | `e431c2d8` | 0 | 106.2 | 200 |

다섯 지점 전부 인증 GET 은 `available=true`·`reason=None`, 비인증 GET 은 401 이다.
`cell_id` 는 `paper`, `code_digest` 는
`ec20680a444cc9798ad601fbcda61edc05cee30d1c00f524c60b717c5f3a5044` 으로 다섯 지점 동일 —
워크트리 커밋은 아침 `4010bc17` 에서 `45ebdab9` 로 바뀌었지만 tos 바이트는 같아 digest
가드가 통과했다.

- **관측됨 — identity 갱신.** 재작성된 첫 파일(17:32:50)부터 `process_nonce` 가
  `997451dd…` → `e431c2d8…` 로 바뀌고 `projection_generation` 은 5033 → **1** 로 되돌아간다
  (프로세스별 export 순번이라 부팅 export 가 1 이다). 인증 API 는 같은 시점 파일과 같은 값을
  돌려준다(R2·R3·R3' 전부 gen 1·새 nonce).
- **관측됨 — 교체 전 창.** 부팅 증명(17:32:37) 뒤 약 12 초 동안은 **이전 프로세스의 파일**
  (gen 5033·옛 nonce·age 6469 초)이 그대로 서빙된다(R1). 그 창에서 API 는 옛 identity 를
  `available=true` 로 돌려주고 stale 판정은 age 가 맡는다 — 첫 export 는 operations wiring 의
  `exporter.export()` 한 번이고(`compose/_operations_wiring.py`), 그 전에는 아무도 파일을
  건드리지 않는다.
- **`runtime_generation` 은 재시작 카운터가 아니다 — 세 부팅 전부 0.** compose root 가
  identity 를 `runtime_generation=0` 으로 만들고(`compose/_wiring.py::_build_identity`),
  `acquire_epoch(identity, runtime_generation=0)` 으로 넘기며, `seed_from(rcl_log)` 의 반환값은
  쓰지 않는다(같은 파일, 「not separately consumed by this compose root」 주석). 재시작마다
  실제로 올라가는 durable 값은 RCL `epochs.epoch` 다 — 정지 뒤 `rcl.sqlite3` 를 읽기 전용
  (`mode=ro&immutable=1`)으로 연 결과 세 행이 epoch 1·2·3 이고 nonce 는 각각 `13b564cd…`
  (10-06 08:45) · `997451dd…`(10-07 08:45) · `e431c2d8…`(10-07 17:32), `runtime_generation`
  열은 셋 다 0 이다. 그러므로 인계 §6 체크 4 의 「generation 갱신」은 **epoch 로 관측됐고
  `runtime_generation` 으로는 관측될 수 없는 값**이다. 설계 #40 D1.1 의 문장(「epoch 와 같은
  트랜잭션에서 증가」)과 compose root 의 0 고정이 다른 것을 말하는지, projection 이 epoch 를
  실어야 하는지는 운영자 결정이고 이 기록은 코드를 바꾸지 않았다.
- **미관측 — 재시작 뒤 장중 export 주기.** `projection_generation` 은 17:32:50 의 1 에서 정지까지
  움직이지 않았다. 재export 는 드라이버 턴 뒤 콜백에 묶여 있는데
  (`driver.bind_after_turn(exporter.as_after_turn_callback())`), 장 밖 틱은 턴 전에
  `SKIPPED_SESSION_CLOSED` 로 끝난다(`marketfeed/scheduler.py::decide_tick`). 보고서도 같다 —
  관측 덧붙임 17 · 소비 0 · 스냅샷 +0 · 결정 none. 아침 세션의 5 초 주기가 새 nonce 아래에서도
  이어지는지는 **08:45–15:45 안의 재시작**에서만 볼 수 있고, 이 실행은 그것을 재지 않았다.
- **리플레이.** `REPLAY_VERDICT_IDENTICAL` 1 · `REPLAY_DIVERGED` 0 · 증거행 +20 ·
  data dir +24,576 B. `boot_seconds` 는 genesis 2.0 → 08:45 9.21(75,839 행 위) → 17:32
  **14.33**(147,922 행 위)으로, 런북 §7.8 2 의 리플레이 시간 곡선에 세 번째 점이 생겼다.
- **정지 뒤 stale 입력 재현.** R3→R3' 에서 generation 1 고정·age 84.1 → 106.2 초로 체크 3 과
  같은 모양이다. UI 가 stale 로 렌더한 화면은 이번에도 캡처하지 않았다.

원시 관측은 `~/.local/state/tos/measure/cp1-restart-20261007/`(700/600 · `R0-file`·`R0-api`·
`R1`·`R2`·`R3`·`R3b`·`report-summary`), 세션 디렉터리
`~/.local/state/tos/paper-sessions/2026-10-07-173223-LONG/`(`report.json`), 날짜 로그
`~/.local/state/tos/paper-logs/2026-10-07.log` 의 17:32:17 블록이다. 인증 GET 에 쓴 API 키는
이 기록에 담지 않는다.
