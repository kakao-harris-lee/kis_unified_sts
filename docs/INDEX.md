# Documentation Index

Last updated: 2026-11-14 (역사 계획·증거 은퇴, `docs/plans/2026-11-13-tos-code-halving-plan.md` §S3/§4).

> **2026-11-14 — 역사 계획·증거 은퇴.** 끝난 2026-07~09 커널·런타임 착지 기록
> 35건과 끝난 측정 캠페인 증거 5건(P0-2 T2 · CP-3 PR-1 분봉 프로브 · PR-2b 둘 ·
> 주식 MOCK 빈 결과)을 지웠다. 남긴 것은 코드·테스트·CI·설정이 **읽는** 문서,
> 지금 도는 것의 결정 기록, 현재 런북, 그리고 배포된 venue 값의 1차 출처(KRX
> 규정 원문)뿐이다. 내용은 git 이력에 그대로 있다:
> `git log --diff-filter=D -- docs/`.

> **2026-11-13 — 역사 문서 은퇴.** 레거시 런타임 시절의 로드맵·가이드·검증
> 기록과 2026-07~08 RFC 설계 코퍼스를 지웠다. 코드·CI 가 읽는 문서와 현재
> 런북만 남는다. 내용은 git 이력에 그대로 있다:
> `git log --diff-filter=D -- docs/`.

> **The legacy trading runtime no longer exists.** Removal plan:
> [plans/2026-11-07-legacy-removal-plan.md](plans/2026-11-07-legacy-removal-plan.md);
> the code last existed at tag `legacy-final` (`6fc17c0f8d25`). Current state:
> [PROJECT_STATUS.md](PROJECT_STATUS.md).

Top-level `docs/` index. For plans see [plans/INDEX.md](plans/INDEX.md);
for runbooks see [README.md § Runbooks](../README.md#runbooks).

For "what's the project doing right now?" → [PROJECT_STATUS.md](PROJECT_STATUS.md).
For "where is TOS headed?" → [plans/2026-11-11-tos-platform-roadmap.md](plans/2026-11-11-tos-platform-roadmap.md)
and the [TOS integration plan](plans/2026-10-06-tos-control-plane-and-first-tenant-plan.md).

---

## 📊 Project status

| Doc | Use |
|-----|-----|
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 60-second dashboard — current phase, active sessions, blocking risks. |

## 📐 Architecture & API

| Doc | Use |
|-----|-----|
| [architecture/tos-system-context.md](architecture/tos-system-context.md) | TOS 공식 계층·책임·허용 의존 방향 정본. |
| [architecture/tos-public-interfaces.md](architecture/tos-public-interfaces.md) | 외부 조회/CLI 계약과 런타임 내부 포트, 현재 구현과 후속 명령 경계. |
| [migration/legacy-disposition.md](migration/legacy-disposition.md) | 기능별 유지·이관·폐기 및 전환/롤백 조건. |
| [ports.md](ports.md) | Host port ownership: Caddy host 5081, internal service ports stay private. |

## ⚙️ Operations

| Doc | Use |
|-----|-----|
| 운영 런북 전체 | → [README.md § Runbooks](../README.md#runbooks) — 런북 색인은 README 하나가 정본이다 |
| [CI_PARALLEL_NOTES.md](CI_PARALLEL_NOTES.md) | `pytest-xdist` 병렬 실행 (병렬 패스 + `serial` 마커 직렬 패스) + parallel-unsafe 테스트 목록. |

## 📁 Sub-directories

| Path | 내용 |
|------|------|
| [plans/](plans/) | 현재 계획과 코드·설정이 인용하는 설계 문서 → [plans/INDEX.md](plans/INDEX.md) |
| [broker-profiles/](broker-profiles/) | KIS capability profile (런타임이 읽는다) + 측정 캠페인 증거 |
| [runbooks/](runbooks/) | 운영 런북 → [README.md § Runbooks](../README.md#runbooks) |
| [superpowers/plans/](superpowers/plans/) | Active generated implementation plans only → [superpowers/plans/INDEX.md](superpowers/plans/INDEX.md) |

## How to add a new doc

1. 새 doc은 top-level `docs/` 또는 적절한 sub-directory에 배치.
2. **카테고리 의도가 분명**한 경우 (operations / architecture 등): 본 INDEX 표에 한 줄 추가.
3. 시간이 지나 아무도 인용하지 않는 기록은 지운다 — git 이력이 보존한다.
4. PROJECT_STATUS.md는 살아있는 dashboard로 계속 갱신한다.
