---
name: ops-harness
description: "운영/장애 오케스트레이터. TOS paper 상주 세션·CP-3 tenant 세션 상태 확인, 부팅 거부·장중 중단 진단, KIS 모의 전송 실패, docker 스택·Redis DB 1·호스트 자원. 헬스체크, 상태 확인, 장애, 크래시, 복구 요청 시."
---

# Ops Harness — 운영/장애 오케스트레이터

지금 운영되는 것은 **TOS paper 상주 세션**, **CP-3 tenant 세션**(선물 synthetic,
주식은 KIS **모의** 계좌), 그리고 읽기 전용 운영자 표면(dashboard + `/tos` UI)이다.
레거시 트레이딩 런타임·Telegram 알림·브리핑 cron 은 존재하지 않는다.

## 전문가 2명

| 에이전트 | 영역 | 트리거 |
|---------|------|-------|
| `ops-monitor` | 상태 확인 (읽기 전용) | 헬스체크, 상태, 성능, 모니터링, 리소스, 오늘 뭐 돌았나 |
| `incident-responder` | 장애 진단·복구 | 장애, 에러, 크래시, 부팅 거부, 끊김, 복구, 왜 안 떴나 |

> 알림 전달 레인은 없다. 알림이 필요하면 운영자에게 직접 보고한다.

## 라우팅

```
"지금 상태 어때" / "오늘 뭐 돌았어" / "스택 살아있나"   → ops-monitor
"세션이 안 떴어" / "부팅 거부됐어" / "전송이 실패해"      → incident-responder
"상태 보고 문제 있으면 고쳐줘"                          → ops-monitor → (이상 시) incident-responder
```

## 표준 헬스체크 순서 (ops-monitor)

```bash
sts tos status                 # 한 장 상태판 — 오늘 무엇이 돌았고 무엇이 막혔나
docker compose ps              # dashboard · strategy-builder-ui · caddy · redis · prometheus
curl -fsS http://localhost:${DASHBOARD_HOST_PORT:-5081}/health
redis-cli -n 1 INFO memory     # DB 1 전용
free -m; df -h /mnt/c          # 호스트 여유 (available·Swap free·vhdx)
```

세션 로그: `~/.local/state/tos/paper-logs/`,
`~/.local/state/tos/cp3-*-tenant-daily.cron.log`. cron 래퍼는
`~/.config/kis-probes/`, 설치 도구는 `tools/tos_cp3/runners/install_tenant_cron.sh`.

## 장애 진단 1차 분기 (incident-responder)

| 증상 | 먼저 볼 것 |
|------|-----------|
| 세션이 시각에 안 떴다 | cron 로그 → `@reboot` catch-up 이 돌았는지 → 호스트가 재부팅했는지 |
| 부팅 거부 (`EngineReplayDiverged` / digest BEHIND) | `config/tos_runtime/<tenant>/release.yaml::expected_code_digest` vs 현재 트리 |
| 모의 전송이 ACK 를 못 따라간다 | 토큰·앱키 공유 대기열 → 페이싱 슬롯 → 패스 안 사전 GET 대기 시간 |
| 프로세스가 이유 없이 죽는다 | `journalctl -u earlyoom` → `free -m` → `df -h /mnt/c` |
| 대시보드가 "projection file absent" | `TOS_OPERATOR_PROJECTION_DIR`(호스트) ↔ `TOS_OPERATOR_PROJECTION_PATH`(컨테이너) 짝 |

## 작업 원칙

- **모니터링은 비파괴적이다.** 상태를 바꾸는 조치는 incident-responder 로 넘긴다.
- **안전 인터록은 어떤 복구로도 끄지 않는다** — 실주문 차단, 미입금 ABORT,
  fail-closed 분기. 실전 선물 계좌는 절대 입금하지 않는다 (CLAUDE.md 비협상).
- **모의 tenant 의 장중 수정·재시작은 상시 승인**, **커널 변경은 15:40 뒤**.
- **호스트 사전확인은 별도 턴으로.** `free`/`pgrep`/`ps` 를 빌드·테스트 명령과
  한 배치로 보내면 결과를 보기 전에 빌드가 이미 돈다.
- **새 가드에는 실제 사고 1건을** (CLAUDE.md R5). 가설만으로 검사기를 늘리지 않는다.
- **기록은 가볍게** (R7): 한 표 — 명령, 결과 숫자, 로그 경로.

## 다른 하네스와의 경계

- **`devx-harness`**: 빌드·테스트·CI 인프라(Docker 이미지·compose 프로파일·
  GitHub Actions·flaky/hermetic). «CI 가 빨갛다» 는 그쪽, «운영 세션이 안 돈다» 는 여기.
- **`code-audit`**: 코드 품질 감사. 장애의 근본 원인이 코드면 수정은 그쪽 경로로.
