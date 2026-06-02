---
name: ops-harness
description: "운영/모니터링 오케스트레이터. 시스템 모니터링, 장애 대응, 알림 관리. 헬스체크, 성능 분석, 인시던트 대응, Telegram 알림."
---

# Ops Harness — 운영/모니터링 오케스트레이터

트레이딩 시스템의 운영 안정성을 보장하기 위한 모니터링, 장애 대응, 알림 관리를 조율한다.

## 전문가 풀

| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `ops-monitor` | 시스템 모니터링/성능 분석 | 헬스체크, 상태 점검, 성능, 모니터링, 리소스 |
| `incident-responder` | 장애 대응/진단/복구 | 장애, 에러, 크래시, 끊김, 복구, 롤백 |
| `alert-manager` | 알림 설정/관리 | Telegram, 알림, Cron, 브리핑, 알림 규칙 |

## 운용 흐름

```
                              ┌→ [ops-monitor]        상시 모니터링
[ops-harness] → 상황 판단 →   ├→ [incident-responder] 장애 감지 시
                              └→ [alert-manager]      알림/Cron 관리
```

### 상시 모니터링 사이클
```
ops-monitor: 헬스체크 (인프라 + 트레이딩)
    ↓ [이상 감지]
    ├→ WARNING: alert-manager → Telegram 경고 발송
    └→ CRITICAL: incident-responder → 긴급 대응
                    ↓ [복구 완료]
                 alert-manager → 복구 알림 발송
                    ↓
                 ops-monitor → 복구 후 상태 재검증
```

## 시나리오별 워크플로우

### 1. 정기 헬스체크
```
ops-monitor 단독:
- Docker 컨테이너 상태
- ClickHouse 연결/디스크
- Redis DB 1 메모리/키
- WebSocket 연결 상태
- KIS API 응답 상태
→ 결과: OK / WARNING / CRITICAL 리포트
```

### 2. 장애 대응 (파이프라인)
```
ops-monitor: 이상 감지 (CRITICAL)
    ↓
incident-responder: 원인 진단 + 복구 실행
    ↓
alert-manager: 장애 알림 → 복구 알림
    ↓
ops-monitor: 복구 후 안정성 재검증
```

### 3. 알림 체계 설정/변경
```
alert-manager 단독:
- Telegram 채널 설정
- Cron 스케줄 관리
- 알림 규칙 추가/수정
- 노이즈 분석 및 필터링
```

### 4. 성능 분석 (팬아웃)
```
ops-monitor + alert-manager (병렬):
- ops-monitor: 일별/주별 트레이딩 성과 분석
- alert-manager: 알림 히스토리 분석 (노이즈/중요도)
→ 통합: 성능 보고서 + 알림 최적화 권장
```

### 5. 배포 후 모니터링
```
model-deployer (strategy-lab)에서 인계:
    ↓
ops-monitor: 새 전략 성능 추적 (Sharpe, DD, latency)
    ↓ [이상 시]
incident-responder: 전략/설정 롤백 판단
    ↓
alert-manager: 이상/롤백 알림
```

## 라우팅 규칙

```
"시스템 상태 확인해줘" → ops-monitor
"ClickHouse 안 돼" → incident-responder
"Telegram 알림 설정해줘" → alert-manager
"오늘 PnL 분석해줘" → ops-monitor
"WebSocket 끊겼어" → incident-responder
"Cron 스크립트 상태 확인" → alert-manager
"전체 헬스체크" → ops-monitor → (이상 시) incident-responder
```

## 교차 도메인 협업

| 상황 | ops-harness 에이전트 | 협력 대상 (다른 하네스) |
|------|---------------------|----------------------|
| 전략 배포 후 성능 이상 | ops-monitor | model-deployer (trading-harness) |
| 장애로 포지션 정합성 불일치 | incident-responder | - (직접 Redis 확인) |
| 전략 성과 급락 | ops-monitor | backtest-engineer (trading-harness) |
| 새 전략 배포 후 알림 추가 | alert-manager | strategy-architect (trading-harness) |
| WebSocket/ClickHouse 복구 후 데이터 gap | incident-responder | data-engineer (trading-harness) |
| EGW00201/주문 거부/토큰 만료 | incident-responder | execution-specialist (trading-harness) |
| rate-limit 상태·체결 지표 이상 | ops-monitor | execution-specialist (trading-harness) |
| 브리핑 cron 실행/지연, 콘텐츠 품질 | alert-manager | llm-analyst (trading-harness, 콘텐츠) |
