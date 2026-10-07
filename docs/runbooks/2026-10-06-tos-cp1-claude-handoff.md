# 2026-10-06 TOS 계층 정리 및 CP-1 작업 인계 — Codex → Claude

- 작성: 2026-10-06 · 대상 독자: CP-1 조회 화면과 paper projection 배선을 이어받는 사람/에이전트
- 기준 main: **`00bd5456`**(PR #869 병합)
- 충돌 시 정본: **코드와 CI 워크플로 > 계획·testing 문서 > 이 문서.** CP-1 구현·검증
  상세는 [`docs/testing/2026-10-06-tos-control-plane.md`](../testing/2026-10-06-tos-control-plane.md),
  출력 연결 절차는 [`tos-paper-projection-connection.md`](tos-paper-projection-connection.md) 가 정본이다.

## 0. 한 줄 요약

TOS·레거시 계층 명명을 확정하고 **조회 전용 `/tos` 화면과 호스트 projection 출력 배선**을
main 에 올려 dashboard·UI 두 서비스로 배포했다(#860~#864). 리뷰에서 분리한 후속 넷
(#866~#869)도 머지됐다(main `00bd5456`). 작성 시점에 관측하지
못했던 **실제 paper 세션의 projection 갱신**은 2026-10-07 첫 실제 세션에서 §6 의 넷 중
셋까지 관측했다 — 파일 생성·generation 증가, producer↔API 값 일치, 정지 뒤 stale 입력.
넷째 **재시작 뒤 runtime identity 갱신**은 같은 날 17:32 운영자 지시의 손 재시작에서 관측했다
(`process_nonce` 교체 · export 순번 1 로 복귀 · RCL epoch 3). 남은 것은 재시작 뒤 **장중**
export 주기와 UI stale 렌더 화면이다. 후속 넷의 처분은 §6 끝에 적었다.

이 문서는 2026-10-06 작업 종료 시점의 인계 기록이다. 이후 작업을 재개할 때는
현재 Git 상태와 실제 프로세스를 다시 확인한다. 이 인계 파일 자체는 별도 생성했으며,
아래의 main 병합 완료 기록은 #860~#864 작업과 그 후속 #866~#869 를 가리킨다.

## 1. 커밋·병합 상태

관련 구현과 배포 기록은 모두 main에 병합했다. 인계 기준 main은 `00bd5456`다.
앞의 다섯은 CP-1 아크이고, 뒤의 넷은 그 리뷰에서 분리한 후속이다(§6).

| PR | 내용 | main 병합 커밋 | 리뷰 |
|---|---|---|---|
| [#860](https://github.com/kakao-harris-lee/kis_unified_sts/pull/860) | TOS·레거시 계층 문서 및 후속 로드맵 | `455db342` | **없음** — CI 만으로 머지(코멘트 0) |
| [#861](https://github.com/kakao-harris-lee/kis_unified_sts/pull/861) | CP-1 조회 화면·출력 배선·API 수정 | `af43fd8a` | [사후 리뷰](https://github.com/kakao-harris-lee/kis_unified_sts/pull/861#issuecomment-6016550580)(머지 뒤, 지적 11·노트 8) → #864 가 처분 |
| [#862](https://github.com/kakao-harris-lee/kis_unified_sts/pull/862) | 실제 배포 결과 및 남은 확인 사항 문서화 | `373450ba` | **없음** — CI 만으로 머지(코멘트 0) |
| [#863](https://github.com/kakao-harris-lee/kis_unified_sts/pull/863) | 콜드 백업 후속 — 산출물 모드(umask 077 판)·cron 로그 문장 정정·첫 실전 실행 등재 | `7b69d11b` | [정식 리뷰 1회](https://github.com/kakao-harris-lee/kis_unified_sts/pull/863#issuecomment-6016436632)(지적 11·노트 10) → [처분](https://github.com/kakao-harris-lee/kis_unified_sts/pull/863#issuecomment-6016449338) |
| [#864](https://github.com/kakao-harris-lee/kis_unified_sts/pull/864) | projection DTO를 producer 계약에 맞춤 — #861 사후 리뷰 처분 | `9198d44c` | [1회차](https://github.com/kakao-harris-lee/kis_unified_sts/pull/864#issuecomment-6017198723)·[2회차](https://github.com/kakao-harris-lee/kis_unified_sts/pull/864#issuecomment-6017847627) + [독립 검증자](https://github.com/kakao-harris-lee/kis_unified_sts/pull/864#issuecomment-6018491899) |
| [#866](https://github.com/kakao-harris-lee/kis_unified_sts/pull/866) | UI 프록시가 대시보드 키를 빌려주기 전에 호출자를 인증(#861 노트 f) | `7f643ba6` | [리뷰 1회](https://github.com/kakao-harris-lee/kis_unified_sts/pull/866#issuecomment-6019365372)(지적 3·노트 a) → [처분](https://github.com/kakao-harris-lee/kis_unified_sts/pull/866#issuecomment-6019549882) |
| [#867](https://github.com/kakao-harris-lee/kis_unified_sts/pull/867) | 프런트엔드 스위트를 CI 잡으로 추가(#864 2회차 지적 5) | `87ff87b1` | [리뷰 1회](https://github.com/kakao-harris-lee/kis_unified_sts/pull/867#issuecomment-6019962905) → [처분](https://github.com/kakao-harris-lee/kis_unified_sts/pull/867#issuecomment-6020377431) |
| [#868](https://github.com/kakao-harris-lee/kis_unified_sts/pull/868) | `tos`를 라우팅 표 안으로 넣고 HEAD 정책을 명시(#861 노트 c·d) | `47bbce70` | [리뷰 1회](https://github.com/kakao-harris-lee/kis_unified_sts/pull/868#issuecomment-6019343586)(지적 3·노트 a) → [처분](https://github.com/kakao-harris-lee/kis_unified_sts/pull/868#issuecomment-6019449902) |
| [#869](https://github.com/kakao-harris-lee/kis_unified_sts/pull/869) | projection 계약 fixture를 생산자 배포로 이동(#861 노트 e) | `00bd5456` | [리뷰 1회](https://github.com/kakao-harris-lee/kis_unified_sts/pull/869#issuecomment-6019606413)(지적 2) → [처분](https://github.com/kakao-harris-lee/kis_unified_sts/pull/869#issuecomment-6019949958) |

#861 최종 구현 코드 `bb394cb1`의 전체 CI가 통과했다.
#862와 #863은 문서 범위라 ruff·tos-firewall·tos-gate 3개만 돌고 모두 통과했다
(`test`는 docs-only 변경에서 경로 게이팅으로 돌지 않는다).
#864는 최종 head `f7d15736`에서 `test`·`lint`·`type-check`·`performance`·
`backtest-extra`·`ruff`·`tos-gate`·`tos-firewall`·Docker·Dev Container가 모두 통과했다.

## 2. TOS·레거시 계층 문서 정리

- `tos/CLAUDE.md` 드리프트 수정.
- 공식 계층 명명 확정:
  - `tos`: **TOS Kernel**
  - `tos_runtime`: **Application Runtime + Infrastructure Adapters**
  - dashboard의 TOS 표면: **Control Plane API (BFF)**
  - `strategy-builder-ui`: **Product / Operator UI**
  - 전략 DSL·프로파일·governed 설정: **Tenant Content**
- 시스템 경계, 공개 인터페이스 카탈로그, 레거시 정리 기준 작성.
- 프로젝트 상태·문서 인덱스 갱신 및 CP-0~CP-4 로드맵 구체화.

주요 문서:

- [시스템 경계](../architecture/tos-system-context.md)
- [공개 인터페이스 카탈로그](../architecture/tos-public-interfaces.md)
- [레거시 정리 기준](../migration/legacy-disposition.md)
- [Control Plane 및 첫 tenant 계획](../plans/2026-10-06-tos-control-plane-and-first-tenant-plan.md)
- [프로젝트 상태](../PROJECT_STATUS.md)

레거시 정리 상태는 기존 `tos-spec/src/MIGRATION-CONFORMANCE-REGISTER.csv`가
기준이다. 별도 중복 상태표를 만들지 않았다. 계층 명명은 import firewall을 변경하지 않는다.

## 3. CP-1 조회 전용 운영 화면 구현·배포

- `/tos` 화면과 Navigation 항목 추가.
- 복구·실행·릴리스·안전 서비스·입력 유효성·원장·증거·백업·알림 조회.
- unknown/null/false/0을 구분하고 missing·invalid·unsupported·stale·인증/통신 오류 표시.
- 15초 조회, 60초부터 stale. UI 설정은
  `strategy-builder-ui/src/config/tos-control-plane.json`에 둔다.
- 캐시된 조회 값도 브라우저 monotonic 경과에 따라 오래된 상태로 전환한다.
- 공통 JSON fixture(#869 이후 `tos/runtime/tests/fixtures/operator-projection-v1*.json`)를 dashboard·UI·runtime
  테스트가 함께 읽는다. 다만 #861 시점의 nullable 정합은 불완전했다 —
  `protective.last_verdict`가 producer의 6-키 중첩이 아니라 `str | None`이어서 첫 실제
  verdict에 필드 하나가 아니라 문서 전체가 거부될 상태였고, runtime fixture 테스트는
  reader를 갈아끼워 assembler pass-through만 증명해 그것을 못 봤다. #864가 producer
  소스를 `ast`로 읽어 DTO 필드와 대조하는 방식으로 닫았다.
- Next proxy에는 정확한 projection GET만 허용.
- 자체 점검에서 잘못된 UTF-8의 500 응답, atomic replace 중 파일 내용·mtime 세대 불일치,
  미래 mtime의 잘못된 recent 표시를 수정하고 회귀 테스트를 추가했다.

main 병합 후 dashboard·UI 두 서비스만 배포했다. 커널·주문 경로·durable set·cron·코드 핀
정책은 변경하지 않았다. 배포 전후 container ID 비교에서도 두 조회 서비스 외 거래
컨테이너는 유지됐다. 조회 결과는 거래 실행 권한을 부여하지 않는다.

#864 병합 뒤 2026-10-06 23:39 KST(두 컨테이너 기동 시각)에 같은 두 서비스를 다시 배포했다. dashboard와 UI
컨테이너만 재생성되어 둘 다 healthy이고, Caddy와 거래 컨테이너는 그대로다. Caddy 경유
`/tos` 200, 비인증 projection GET 401, 인증 GET 200을 재확인했다. 세션 밖의 projection
부재는 이제 WARNING이 아니라 INFO로 기록된다 — 탭 하나가 15초마다 조회하므로 정상
상태를 WARNING으로 두면 시간당 240줄이 쌓인다.

위 `23:39` 은 이제 **dashboard 컨테이너에만** 참이다. UI 컨테이너는 그 뒤 교체됐다 — §6 끝.

## 4. 실제 호스트 출력 배선

다음 비버전 호스트 파일을 원본 SHA와 정지 상태 확인 후 수정했다.

- `/home/deploy/.config/kis-probes/tos-paper-session.sh`
- `/home/deploy/.config/kis-probes/tos_paper_session.py`

기존 runtime `--projection-path`를 연결했다.

| 구간 | 경로·설정 |
|---|---|
| host 출력 파일 | `/home/deploy/.local/state/tos/paper-projection/operator_projection.json` |
| dashboard 파일 | `/app/data/tos_runtime/operator_projection.json` |
| wrapper 설정 | `TOS_PAPER_PROJECTION_PATH` |
| Compose host 디렉터리 설정 | `TOS_OPERATOR_PROJECTION_DIR` |
| Compose container 파일 설정 | `TOS_OPERATOR_PROJECTION_PATH` |

전용 디렉터리는 deploy 소유 0700이며 producer는 기존 umask 077을 상속한다.
Dashboard에는 읽기 전용 **디렉터리**로 마운트한다. 파일 단독 bind는 atomic replace 이후
갱신을 놓칠 수 있으므로 사용하지 않는다. 기존 `data/tos_runtime`은 root 소유여서
producer 출력 위치로 사용하지 않았다.

`.env.paper`에는 projection 좌표 두 설정만 추가했다. 이 두 설정은 #864가 `.env*.example`
넷과 compose 마운트 주석에도 적었다(마운트 의미는 그대로). selftest 또는
data-dir/instrument/fake-date/worktree/calendar 우회 세션은 session-local 출력으로
격리해 운영 파일을 덮어쓰지 않는다. 직접 driver를 호출할 때 projection 인자를 생략하면 이전 동작을 유지한다.

원본 백업:

`/home/deploy/.local/state/tos/paper-ops/projection-connection-20261006/`

원본 script와 비밀 설정 백업이 들어 있다. 비밀 설정 내용을 출력·커밋하지 않는다.

재현 가능한 변경과 검증 도구:

- [host script 패치](patches/tos-paper-projection.patch)
- `scripts/tos/check_paper_projection_wiring.py`
- [출력 연결·복구 런북](tos-paper-projection-connection.md)

커밋된 패치를 별도 원본 사본에 적용해 설치 파일과 byte-identical임을 확인했다.
설치 후 SHA-256:

```text
tos-paper-session.sh  2c3284a4ec3a1312018c0d6c730b7f2dbfb891c53fb4a2ea86aecb8980aaccef
tos_paper_session.py  3ce14fb685a009b993ba9fcaa1b4693c38efd4279e60fa4e0622140336b8624e
```

## 5. 검증 및 리뷰 상태

- 테스트(#864 최종 head `f7d15736` 기준): `tests/unit/dashboard` 413 passed·2 skipped
  (그중 `test_tos_projection.py` 42개), `tos/runtime/tests/operator` 36개, UI 세 파일 74개.
- 위 수치를 #861 시점 수치와 나란히 읽을 때는 **범위를 맞춰야 한다**. #864가 실제로 늘린
  것은 dashboard projection **13 → 42** 하나뿐이다.
  - runtime: `tos/runtime/tests/operator/`는 `bb394cb1`과 `9198d44c` 사이에 무변경이다.
    25는 `test_projection.py` 단독 수집, 36은 같은 디렉터리 셋(projection 25 +
    `test_export.py` 7 + `test_no_write_port.py` 4)이라 증가가 아니라 범위 차이다.
  - frontend: 257은 39파일 전체 스위트, 74는 이 작업이 건드린 3파일이라 비교 대상이 아니다.
  - 이 절 끝에 링크한 상세 문서의 #861 아크 절은 dashboard를 33개로 적는데, 그것은 #864 커밋
    `1836695b` 시점 수치다 — 같은 아크의 서로 다른 head를 적은 것이고 둘 다 맞다.
- Frontend 타입 검사·빌드·변경 파일 lint, spec/firewall 및 #861 전체 CI 통과.
- 실행 없이 7개 경로 선택과 driver 인자 유무 검증 통과. 이 검증은 runtime을 실행하지 않는다.
  #864가 이 게이트의 fail-open 둘을 닫고 래퍼의 기본 published 경로까지 보게 했으며,
  레드 증명 14건이 각각 exit 1임을(그리고 `python -O`에서도 같음을) 확인했다.
- TS 쪽 단언에도 이제 CI 잡이 있다 — #867이 `.github/workflows/ui.yml`
  (체크 이름 「UI suite (lint + build + tsc + vitest)」)을 추가했다. 다만 **필수 체크가
  아니고 경로 게이팅**이라 UI 경로를 건드리지 않는 PR에서는 돌지 않는다.
- 컨테이너 uid 1000의 읽기 성공·쓰기 거부·같은 컨테이너에서 atomic replace 후 갱신 확인.
- 실제 Caddy 경유 `/tos` 200, 인증 projection GET 200, 비인증 GET 401.
- API `Cache-Control: no-store` 확인.
- dashboard·UI 모두 healthy·restart 0, 브라우저 오류 0·390px 모바일 가로 넘침 없음.

#861은 머지 뒤 Claude 독립 리뷰를 받았다 — 지적 11건과 노트 8건이
[#861 사후 리뷰](https://github.com/kakao-harris-lee/kis_unified_sts/pull/861#issuecomment-6016550580)로 올라왔고, 그 처분이 #864다.
#864 자체도 머지 전에 리뷰 2회차와 독립 검증 레인을 거쳤다:
[1회차](https://github.com/kakao-harris-lee/kis_unified_sts/pull/864#issuecomment-6017198723) → [처분](https://github.com/kakao-harris-lee/kis_unified_sts/pull/864#issuecomment-6017458370),
[2회차](https://github.com/kakao-harris-lee/kis_unified_sts/pull/864#issuecomment-6017847627) → [처분](https://github.com/kakao-harris-lee/kis_unified_sts/pull/864#issuecomment-6018130898),
그리고 독립 검증이 head에서 찾은 BLOCK 넷을 [마지막 처분](https://github.com/kakao-harris-lee/kis_unified_sts/pull/864#issuecomment-6018491899)으로
닫았다. 2회차 처분 보고는 적용 스크립트가 중간에 죽어 디스크에 닿지 않은 수정 둘을
적용했다고 적었고, 그것을 잡은 것이 그 독립 검증 레인이다.

**작성자 자체 점검과 CI 통과를 독립 리뷰 승인으로 취급하면 안 된다** — 위 사례가 그
이유다. 이 규칙은 리뷰가 실제로 돌았는지와 무관하게 유지한다.

상세 결과: [CP-1 구현·검증·배포 기록](../testing/2026-10-06-tos-control-plane.md).

## 6. 이어서 확인할 사항

배포 확인 시 paper 프로세스는 정지해 있었고 운영 projection 파일도 없었다.
실제 화면은 missing 상태를 정확히 표시했다. 검증용 fixture를 운영 파일에 쓰거나
장 마감 후 검증을 위해 거래 세션을 임의로 시작하지 않았다.

다음 정상 paper 세션에서 아래를 확인해야 한다. 그 세션은 2026-10-07(08:45~15:45 KST)에
돌았고 **넷 중 셋을 관측했다**. 수치의 정본은
[CP-1 구현·검증·배포 기록](../testing/2026-10-06-tos-control-plane.md)의
「첫 실제 세션 관측 2026-10-07」절이다.

1. projection 파일 생성 및 generation 증가 — **관측됨(2026-10-07)**. T1 09:07:12 KST 에
   mode `0600` 파일 하나, generation 264. T2 09:37:15 에 624, T3 15:52:17 에 5033(마지막
   쓰기 15:45:00). T1→T2 1803 초에 +360 세대로 약 5.0 초마다 재작성.
2. producer → 인증 API → `/tos` 값 일치 — **관측됨(2026-10-07)**. T1·T2·T3 전부 Caddy
   경유 인증 GET 이 `available=true`·`reason=None` 이고 generation 이 같은 시점 파일과
   같다(264·624·5033). `/tos` 도 세 지점 전부 200.
3. 세션 종료 후 stale 전환 — **관측됨(2026-10-07, 단서 있음)**. 15:45:06
   `stop: driver exited` 뒤 세션 프로세스 0. T3 와 30 초 뒤 재프로브의 age 가 437.3 초·
   467.3 초로 `staleAfterSeconds` 60 을 넘고 generation 은 5033 고정이다. 관측한 것은 UI
   의 stale 판정을 구동하는 **API 입력**이고, UI 가 실제로 stale 로 렌더한 화면은
   스크린샷으로 확인하지 않았다.
4. 재시작 후 runtime identity·generation 갱신 — **관측됨(2026-10-07 17:32, 손 재시작)**.
   운영자 지시로 같은 잎에 두 번째 세션(`2026-10-07-173223-LONG`, `TOS_PAPER_MINUTES=7`,
   정지는 cron 과 같은 `stop`)을 띄웠다. 재작성된 첫 파일(17:32:50)부터 `process_nonce`
   `997451dd…` → `e431c2d8…`, `projection_generation` 5033 → 1 이고 인증 API 가 같은 값을
   돌려준다. `runtime_generation` 은 세 부팅 전부 **0** — compose root 가 0 으로 고정해 넘기는
   값이라 재시작 카운터가 아니고, 실제로 오르는 durable 값은 RCL `epochs.epoch`(1·2·3)다.
   ⚠ 장 밖이라 틱이 전부 `SKIPPED_SESSION_CLOSED` 로 끝나 **재시작 뒤 장중 export 주기**(새
   nonce 아래 generation 증가)는 이 실행이 재지 않았다 — 08:45–15:45 안의 재시작이 필요하다.
   부팅 증명 뒤 약 12 초는 옛 프로세스의 파일이 그대로 서빙된다(age 로만 stale).

완료 범위는 코드·호스트 배선·조회 서비스 배포와 missing/auth 상태 검증에 더해 위 1~4 의
실제 세션 관측이다. 재시작 뒤 장중 export 주기와 UI stale 렌더 화면은 관측한 것으로 보고하지
않는다.

#861·#864 리뷰에서 분리한 후속은 넷이고 **넷 다 main에 머지됐다**. 네 건 모두
#864가 만든 것이 아니라 그 전부터 있던 상태였다.

- **UI 프록시의 미인증 root 다섯** — 프록시가 모든 상류 요청에 서버 키를 붙이면서 자기
  인증은 없어, Caddy `@to_dashboard`에 없는 root 다섯(coverage·event-context·
  market-risk·portfolio·reports)이 키 없이 200이다. 기존 보안 결함이고 projection
  경로와 독립이다(#861 노트 f). **[#866](https://github.com/kakao-harris-lee/kis_unified_sts/pull/866) 머지됨** — `7f643ba6`.
- **프록시의 `tos` 전용 분기와 HEAD 정책** — `tos`가 `compatRoots`/`directRoots` 밖의
  early-return이라 `isDirectPath`와 어긋나고, `HEAD /api/tos/projection`은 405다. 라우팅
  테이블 통합은 TOS 외 root의 거동까지 바꾸므로 범위를 따로 잡는다(#861 노트 c
  뒷부분·d). **[#868](https://github.com/kakao-harris-lee/kis_unified_sts/pull/868) 머지됨** — `47bbce70`.
- **UI 스위트 CI 잡**(`setup-node`+vitest+tsc) — 이것이 없는 동안 TS 단언은 로컬·리뷰에서만
  돌았다. 1회차의 `as const` TS2322이 `next build`에서만 터질 결함이었던 것과 같은
  구멍이다(#864 2회차 지적 5). **[#867](https://github.com/kakao-harris-lee/kis_unified_sts/pull/867) 머지됨** — `87ff87b1`.
- **tos runtime 테스트의 fixture 소유 위치** — `tos/runtime/tests/operator/test_projection.py`가
  `parents[4]/tests/fixtures/tos`로 레거시 트리에 손을 뻗는다. `tos/CLAUDE.md` 작업 집합
  밖이라 #864는 건드리지 않았다(#861 노트 e). **[#869](https://github.com/kakao-harris-lee/kis_unified_sts/pull/869) 머지됨** — `00bd5456`.
  fixture 를 `tos/runtime/tests/fixtures/` 로 옮기고 `projection-reasons.json` 은 레거시
  트리에 남겼다.

#866·#868 의 UI 프록시 변경은 **배포됐다**. 호스트에 떠 있는 UI 컨테이너는
2026-10-07 13:17:15 KST 생성판이다(`docker inspect kis_paper-strategy-builder-ui
--format '{{.Created}}'` → `2026-10-07T04:17:15Z`). #871 은 13:16:00 KST 에 머지됐으므로
(`gh pr view 871 --json mergedAt` → `2026-10-07T04:16:00Z`) 지금 컨테이너는 그 75 초 뒤
판이고, #866·#868 머지보다 뒤다. 같은 명령으로 dashboard 컨테이너는 2026-10-06
23:39:37 KST 그대로여서 이 재생성은 UI 단독이다. 그 사이의 다른 재배포는 컨테이너가
교체되면 흔적이 남지 않으므로, 여기에는 **지금 떠 있는 컨테이너가 증명하는 것만** 적는다.

## 7. Claude 작업 중복 확인 기록

작업 착수 시 저장된 Claude의 마지막 완료 작업은 #859 월물별 durable-set·콜드 백업이었다.
`wt-paper`, `wt-cold`, P8 및 P02 evidence worktree는 clean이었다. 미병합 Setup D 브랜치는
CP-1 projection/UI와 겹치지 않았다. 실행 중인 Claude 프로세스 자체를 작업 없음의 증거로
삼지 않고 별도 worktree에서 구현했다. 이 기록은 착수 시점의 조사이며 재개 시 재확인한다.
