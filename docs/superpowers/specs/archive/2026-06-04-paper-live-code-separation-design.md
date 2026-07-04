# Paper/Live Source-Code Separation — Design

- Date: 2026-06-04
- Status: Design (pending implementation plan)
- Scope: Separate the **source-code version** that paper and live trading run, so
  live executes only validated code while paper continues to run dev/latest.

## 1. Goal

오늘까지 paper/live는 **런타임/배포만** 분리돼 있다 (compose env-file, project name,
host port, runtime ledger, Redis 인스턴스). 그러나 **소스 코드는 동일 체크아웃**에서
빌드/실행된다 — paper와 live가 같은 코드를 돈다.

이 설계는 분리를 **코드 버전까지** 확장한다:

- **paper = 개발·검증 환경** — `main`(dev 최신)을 계속 추적한다.
- **live = 검증된 코드만** — 명시적으로 검증·tag된 릴리스 시점에 고정된다.

검증 단위는 **전체 코드베이스(코드 버전)** 다. 전략 config·모델뿐 아니라
`shared/`·`services/`·`cli/` 엔진 코드 전체가 tag로 고정된다.

## 2. Current state (검증된 사실)

- 트레이딩 실행(canonical) = **호스트 venv + cron**: crontab이 `$KIS_PYTHON -m cli.main
  trade start ...`를 단일 디렉토리 `/home/deploy/project/kis_unified_sts`에서 실행한다.
- compose `trader`(`--profile trading`)는 신규 경로로 존재하나, live의 canonical 실행
  경로는 **호스트 venv+cron으로 유지**한다(운영자 결정 2026-06-04).
- 기존 live 게이트: `config/futures_live.yaml::enabled`(기본 false), Redis
  `futures:live:suspended`, `TRADING_LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING`, 전략
  `enabled` 플래그, Phase 5 Gate. — 이들은 *무엇을/언제* 거래할지 게이트하지, *어느 코드
  버전*인지는 게이트하지 않는다. 본 설계가 그 위에 **코드 버전 게이트**를 추가한다.
- compose env 템플릿: paper `REDIS_HOST_PORT=6381` / live `6382`,
  `data/runtime/{paper,live}/runtime.db`, `COMPOSE_PROJECT_NAME=kis_{paper,live}`.

## 3. Locked decisions (브레인스토밍 2026-06-04)

| 결정 | 선택 |
|---|---|
| 검증 단위 | **전체 코드베이스(코드 버전)** |
| live 실행 경로 | **호스트 venv + cron** (현행 유지) |
| 분리 방식 | **독립 clone 2개** (paper repo / live repo) |
| live 디렉토리 | `/home/deploy/project/kis_unified_sts_live` (sibling) |
| Redis 격리 | **compose redis 재사용** — paper `127.0.0.1:6381` / live `127.0.0.1:6382` (둘 다 DB 1) |

DRY 원칙 준수: 소스는 **하나의 origin**이 단일 진실원이며, 디스크에 두 벌
materialize될 뿐 코드 포크가 아니다.

## 4. Directory layout

```
/home/deploy/project/kis_unified_sts        # PAPER/DEV (기존, 변경 없음)
    ├─ .git                                  # main 추적
    ├─ .venv                                 # dev deps
    ├─ .env                                  # = .env.paper 내용
    ├─ data/runtime/paper/runtime.db
    └─ logs/, pids/

/home/deploy/project/kis_unified_sts_live   # LIVE (신규 독립 clone)
    ├─ .git                                  # 검증 tag vX.Y.Z 에 고정(detached)
    ├─ .venv                                 # 검증 tag의 pinned deps
    ├─ .env                                  # = .env.live 내용 (실 KIS live 자격증명)
    ├─ data/runtime/live/runtime.db
    └─ logs/, pids/
```

- 기존 디렉토리는 **rename하지 않는다** — crontab/cron 스크립트가 절대경로
  `/home/deploy/project/kis_unified_sts`를 하드코딩하고 있어 rename은 파괴적이다.
  기존을 dev/paper로 두고, live는 sibling 신규 clone으로 추가한다.
- live clone 생성: `git clone <origin> /home/deploy/project/kis_unified_sts_live`
  → `git -C … checkout <validated-tag>`.

## 5. Per-clone isolation

| 자원 | paper (기존) | live (신규 clone) | 격리 메커니즘 |
|---|---|---|---|
| git ref | `main` | 검증 tag `vX.Y.Z` (detached) | 별도 `.git` |
| Python venv | 자체 `.venv` | 자체 `.venv` (tag의 deps) | 별도 디렉토리 |
| env | `.env`(=paper) | `.env`(=live) | 별도 파일 |
| runtime ledger | `data/runtime/paper/runtime.db` | `data/runtime/live/runtime.db` | 별도 경로(env) |
| logs/pids/.cache | 자체 | 자체 | 별도 디렉토리 |
| Redis | `127.0.0.1:6381` DB1 | `127.0.0.1:6382` DB1 | **별도 인스턴스(포트)** |

gitignore된 런타임 산출물(.venv/.env/data/logs/pids/.cache)은 clone마다 독립이므로
자동 격리된다.

## 6. Redis isolation (핵심 안전장치)

호스트 cron paper+live가 **같은 Redis 인스턴스+DB1**을 공유하면
`trading:{asset}:positions`, status, kill-switch 키가 충돌 → paper/live 포지션이
섞인다(치명적).

해결: 각 clone의 `.env`가 **다른 Redis 포트**를 가리킨다. compose가 띄우는 per-project
redis를 재사용한다.

- paper `.env`: `REDIS_HOST=127.0.0.1`, `REDIS_PORT=6381`, `REDIS_DB=1`
  (→ `kis_paper-redis`)
- live `.env`: `REDIS_HOST=127.0.0.1`, `REDIS_PORT=6382`, `REDIS_DB=1`
  (→ `kis_live-redis`)

DB는 둘 다 1 유지(프로젝트 "DB1 only" 컨벤션 준수); 격리는 인스턴스(포트)로 한다.

**전제(운영 의존성)**: 각 환경의 compose redis가 떠 있어야 한다 —
`docker compose --env-file .env.paper up -d redis` / `… .env.live up -d redis`.
이 의존성은 runbook과 live preflight 가드레일이 검사한다.

## 7. Promotion & rollback

### 승격 (paper → live)
1. paper(dev)에서 코드 변경을 개발·검증한다.
2. 검증 통과 — 기존 게이트 재사용: 백테스트/Optuna, paper 트레이딩 성과,
   Phase 5 Gate, regime-gate counterfactual, model-evaluator/deployer.
3. 운영자가 검증 시점을 **annotated tag**로 찍는다:
   `git tag -a vYYYY.MM.DD -m "validated: <근거>" && git push origin vYYYY.MM.DD`.
   → tag를 찍는 행위 = 명시적 서면 승인.
4. live clone에 반영:
   `git -C …_live fetch --tags && git -C …_live checkout vYYYY.MM.DD`
   → deps 변경 시 `…_live/.venv/bin/pip install -e .`.
5. live preflight 통과 후 cron이 새 코드로 거래 시작.

### 롤백
- `git -C …_live checkout <이전 검증 tag>` → 즉시 이전 검증본으로. (deps 롤백 필요 시
  `pip install -e .` 재실행.)
- 코드와 무관한 즉시 중단은 기존 kill-switch(`futures:live:suspended`) 사용.

### Tag 컨벤션
- `vYYYY.MM.DD`(필요 시 `-N` suffix). Annotated tag만 "검증"으로 인정한다.
  lightweight tag/브랜치는 live가 거부한다(§8).

## 8. Live guardrail — 검증 코드 강제

live cron 시작 래퍼(신규 `scripts/ops/live_preflight.sh`)가 거래 기동 **전에** 검사하고,
하나라도 실패하면 **거부(비기동)** 한다:

1. `git -C $KIS_LIVE_PROJECT describe --exact-match --tags HEAD` 성공
   — HEAD가 **annotated tag에 고정**돼야 한다(브랜치/임의 커밋 거부).
2. `git -C $KIS_LIVE_PROJECT status --porcelain`가 비어 있음 — 워킹트리 clean
   (검증 후 무단 수정 금지).
3. `.env`의 `REDIS_PORT=6382` 및 live Redis(`127.0.0.1:6382`) ping 성공.
4. (기존) `futures_live.enabled` / `TRADING_LIVE_CONFIRM` / suspend 플래그 확인은
   기존 `LiveModeGuard` 경로가 계속 담당.

→ "검정된 파일만 live" 가 **물리적으로 강제**된다: tag가 아니거나 dirty면 live는 안 뜬다.

## 9. Cron split

- crontab은 paper/live 변수를 분리한다:
  ```cron
  KIS_PROJECT=/home/deploy/project/kis_unified_sts          # paper/dev (기존)
  KIS_PYTHON=/home/deploy/project/kis_unified_sts/.venv/bin/python
  KIS_LIVE_PROJECT=/home/deploy/project/kis_unified_sts_live # live (신규)
  KIS_LIVE_PYTHON=/home/deploy/project/kis_unified_sts_live/.venv/bin/python
  ```
- 기존 paper 엔트리는 그대로(`$KIS_PROJECT`/`$KIS_PYTHON`).
- live 엔트리는 `$KIS_LIVE_PROJECT`에서 `live_preflight.sh` → 통과 시 trade start
  (`--live --yes-live` + `TRADING_LIVE_CONFIRM`)로 추가한다. KST native 유지.
- live cron은 운영자가 실제 전환 시점(Phase 5 Gate 통과 + 서면 승인)에만 설치한다.

## 10. 변경되지 않는 것 (out of scope here)

- compose paper/live 분리(env-file, project, ports, runtime ledger) — 그대로.
- 기존 live 게이트(`futures_live.enabled`, suspend, `TRADING_LIVE_CONFIRM`) — 그대로,
  코드 버전 게이트는 그 위 추가 층.
- compose 기반 live(검증 이미지 tag, "Approach C")는 **향후 옵션** — live를 compose로
  옮길 때 재검토. 지금은 호스트 venv+cron.

## 11. 구현 분담: repo 산출물 vs 운영자 호스트 단계

본 설계의 **소스 관리 대상**(이 repo의 PR로 들어가는 것):

- `scripts/ops/live_preflight.sh` — §8 가드레일.
- `scripts/ops/promote_live.sh` — §7 승격 헬퍼(fetch tag + checkout + deps + preflight).
- `docs/runbooks/paper-live-code-separation.md` — clone 생성·승격·롤백·cron 설치 runbook.
- crontab **템플릿/문서** 갱신(실 crontab은 호스트별이라 운영자가 설치).

**운영자 호스트 단계**(repo 밖, 실 자격증명 포함 — 자동화/커밋하지 않음):

- `git clone … kis_unified_sts_live` + `checkout <tag>` + `.venv` 생성.
- `.env.live`(실 KIS live 키) 작성 — **시크릿은 코드/AI가 다루지 않는다**.
- live compose redis 기동, live cron 설치.

## 12. Risks & mitigations

| 리스크 | 완화 |
|---|---|
| paper/live Redis 키 충돌 | 별도 인스턴스(6381/6382), preflight ping 검사 |
| 검증 안 된 코드가 live 진입 | preflight: HEAD=annotated tag + clean 강제 |
| deps drift(tag deps ≠ live venv) | 승격 시 `pip install -e .`, preflight에 venv 일치(선택) 검사 |
| 두 venv·cron 관리 부담 | promote_live.sh 단일 진입점 + runbook |
| 디스크/혼동 | live는 read-only 운영(직접 편집 금지), 워킹트리 dirty면 거부 |
| live compose redis 미기동 | preflight ping 실패 → 비기동 |

## 13. Acceptance criteria

- [ ] `kis_unified_sts_live` 독립 clone이 검증 tag에 detached로 고정.
- [ ] paper/live가 서로 다른 Redis 인스턴스(6381/6382)에 접속, 키 충돌 없음.
- [ ] `live_preflight.sh`: tag 아님/ dirty / redis down 중 하나라도면 비기동(거부) — 테스트로 검증.
- [ ] `promote_live.sh`로 tag 한 줄 승격 + 롤백 동작.
- [ ] runbook이 clone 생성→승격→롤백→cron 설치를 처음부터 끝까지 안내.
- [ ] 기존 paper cron/디렉토리 무변경, 기존 live 게이트 유지.
- [ ] DRY: 소스 중복 없음(단일 origin), 시크릿은 repo 밖.

## 14. Open questions (구현 계획에서 확정)

- promote/preflight 스크립트 위치 컨벤션(`scripts/ops/` vs `scripts/cron/`).
- preflight의 venv-deps 일치 검사 포함 여부(엄격도).
- tag 네이밍 최종(`vYYYY.MM.DD` vs semver `vX.Y.Z`).
