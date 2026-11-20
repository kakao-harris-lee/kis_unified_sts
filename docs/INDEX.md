# Documentation Index

기준: 2026-11-20. `docs/` 는 **지금 도는 것**만 담는다. 끝난 일의 서사는 git 이력에 있다:
`git log --diff-filter=D -- docs/`.

> **2026-11-20 — 역사 문서 정리.** 레거시 런타임 처분표(`migration/legacy-disposition.md`) ·
> CP-0~CP-4 통합 계획 · superpowers 계획 색인 · `reports/` 의 폐기된 전략 연구 4건을
> 지우고, 큰 런북 넷(paper boot 이력 · 콜드 백업 · RCL 마이그레이션 · CI 병렬 노트)에서
> 날짜가 박힌 기록을 걷어 냈다. 남긴 것은 코드·테스트·CI·설정이 **읽거나 절 번호로
> 가리키는** 문서, 현재 런북, 지금 도는 것의 결정 기록뿐이다.
>
> 이전 라운드: 2026-11-14(역사 계획·증거) · 2026-11-13(RFC 코퍼스·레거시 런북) ·
> 2026-11-12(Phase-0 판정 장치). 전부 `2026-11-13-tos-code-halving-plan.md` §S3/§4.

「지금 무엇이 도는가」 → [PROJECT_STATUS.md](PROJECT_STATUS.md).
「어디로 가는가」 → [플랫폼 로드맵](plans/2026-11-11-tos-platform-roadmap.md) ·
[활용 계획](plans/2026-11-19-tos-usage-plan.md).

---

## 📊 상태

| Doc | 쓰임 |
|-----|------|
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 60초 스냅숏 — 도는 tenant, 완료 기준, 알려진 위험. |

## 📐 아키텍처

| Doc | 쓰임 |
|-----|------|
| [architecture/tos-system-context.md](architecture/tos-system-context.md) | TOS 공식 계층·책임·허용 의존 방향 정본. |
| [architecture/tos-public-interfaces.md](architecture/tos-public-interfaces.md) | 외부 조회/CLI 계약과 런타임 내부 포트. |
| [ports.md](ports.md) | 호스트 포트 소유 — Caddy 5081 하나. 내부 서비스 포트는 비공개. |

## ⚙️ 운영

| Doc | 쓰임 |
|-----|------|
| 운영 런북 전체 | → [README.md § Runbooks](../README.md#runbooks) — 런북 색인은 README 하나가 정본이다 |
| [CI_PARALLEL_NOTES.md](CI_PARALLEL_NOTES.md) | `pytest-xdist` 두 패스 분할(병렬 + `serial` 직렬)과 hermetic 규칙. |

## 📁 하위 디렉터리

| Path | 내용 |
|------|------|
| [plans/](plans/) | 지금 도는 것의 결정 기록과 코드·설정이 인용하는 설계 문서 → [plans/INDEX.md](plans/INDEX.md) |
| [broker-profiles/](broker-profiles/) | KIS capability profile(런타임·검사기가 읽는다) + 측정 캠페인 증거 |
| [runbooks/](runbooks/) | 운영 런북 → [README.md § Runbooks](../README.md#runbooks) |
| [superpowers/specs/](superpowers/specs/) | 살아 있는 설계 스펙 둘 — Setup D VWAP 되돌림(B3 증인의 설계)과 그 추세 필터. 둘 다 `config/strategies/futures/setup_d_vwap_reversion.yaml` 이 인용한다 |

## 새 문서를 더할 때

1. 새 doc 은 top-level `docs/` 또는 맞는 하위 디렉터리에.
2. 카테고리가 분명하면 위 표에 한 줄 추가.
3. **시간이 지나 아무도 인용하지 않는 기록은 지운다** — git 이력이 보존한다.
4. PROJECT_STATUS.md 는 살아 있는 스냅숏으로 계속 갱신한다.
