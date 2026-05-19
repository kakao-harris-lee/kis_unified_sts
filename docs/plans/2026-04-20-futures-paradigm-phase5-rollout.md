# Phase 5 — Paper → Live Rollout (Week 7+)

**Status:** Draft
**Parent:** `docs/plans/2026-04-20-futures-paradigm-master.md`
**Target branch:** `feat/futures-paradigm-phase5`
**Depends on:**
1. Phase 4 완료 게이트 통과 (2주 paper uptime + 20 fills + slippage ≤ 0.4 tick + kill-switch drill green)
2. **Phase 3 final sign-off** — `scripts/walk_forward_paper_foldin.py` reports all four rules pass (bootstrap rule 1+2, paper rule 3+4) after 60-90 days of Phase 4 paper accumulation. The original "Phase 3 12개월 clean data 게이트" was replaced 2026-04-29 by this conditional/final two-step path; see `docs/runbooks/phase3-verification.md` § "Phase 3 status determination".

Gate 3 ladder progression (1→2→5 contracts) is gated on **final** sign-off, not the conditional provisional that allows Gate 1 paper extension.
**Blocks:** (최종)

---

## 1. 목표

Phase 4의 페이퍼 검증을 바탕으로 **1계약 소액 실전** 으로 전환하고, 주간 Edge Review + 롤백 런북 + 기존 `rl_mppo`와의 병행 운영 체제를 확립한다.

**완료 정의:**
- 1계약 실계좌 2주 운영 완료
- 일일 MDD -3% 초과 사건 0건
- 누적 순수익 > 슬리피지 + 수수료
- 실거래 평균 슬리피지 ≤ 0.4 tick
- `rl_mppo` 운용과 독립 계좌로 3개월 병행 확인
- 주간 Edge Review 리포트 8주 연속 발행

---

## 2. 검증 게이트 (원본 §12의 Phase 3~5)

### 2.1 Gate 1 — Paper Trading 2주 (Phase 4 종료 시점 연장)

조건 (모두 충족):
- [ ] 최소 100회 시그널 누적 관찰
- [ ] 백테스트 대비 실시간 시그널 발생 일치도 > 95% (±5%p 이내)
- [ ] 기록 승률 및 EV가 백테스트의 ±20% 이내 유지
- [ ] Kill switch 오탐 0회

미달 시: Phase 3 파라미터 재튜닝 (`scripts/optimize_decision_engine.py`) → 재-bootstrap (`scripts/walk_forward_bootstrap.py`) → 통과하면 Phase 4 페이퍼 재시작. (2026-04-29 update: Phase 3 sign-off는 더 이상 12개월 calendar gate가 아니라 conditional + final two-step path. Gate 1 fallback 시점에는 보통 "재튜닝" 만으로는 부족하고, 추가 paper 데이터 누적이 필요하다는 점을 인지할 것.)

### 2.2 Gate 2 — 소액 실전 준비

- [ ] **법적 검토:** 자동매매 브로커 약관 확인 (`docs/runbooks/futures-legal-review.md`)
- [ ] **세무:** 파생상품 양도세 계산 로직 확인
- [ ] 실계좌 증거금 입금 확인 (1계약 × 미니 증거금 ≈ 200만원 + 버퍼)
- [ ] 계약 명세 재확인 (§Q4): multiplier 50k / tick 0.02pt / tick value 1k
- [ ] 수수료 실측 (KIS 계좌 개별 협의 수수료 확인)
- [ ] KIS 선물 실전 환경 API 연결 테스트 (Paper TR IDs → Real TR IDs 전환)
- [ ] 재시작 시 오픈 포지션 인식 드릴 (`scripts/trading/recover_positions.py`)

### 2.3 Gate 3 — 소액 실전 2주 운영

조건 (모두 충족):
- [ ] 1계약 고정, 일일 최대 2회 거래
- [ ] 일일 MDD -3% 초과 사건 0건
- [ ] 누적 수익 > 슬리피지 + 수수료 (순수익 양수)
- [ ] 실거래 슬리피지 ≤ 0.4 tick 평균
- [ ] Kill switch 작동 0회 (정상 운영)
- [ ] API 에러율 < 2% (5분 rolling)

미달 시: 즉시 중단 → 원인 분석 → Paper로 회귀.

### 2.4 Gate 4 — 증량 결정

Gate 3 통과 후:
- 1→2 계약 증량 제안 (사용자 승인 필요)
- 증량 전 `config/risk.yaml`의 `max_position_size_contracts`, 포지션 사이저 상한 조정
- 2계약 2주 검증 재실행
- **무한 증량 금지.** 메모리상 계획 상한은 5계약 (≈2,500만원 risk).

---

## 3. 주간 Edge Review 자동화

### 3.1 Cron

```bash
# scripts/cron/weekly_edge_review.sh
0 6 * * 1    scripts/cron/weekly_edge_review.sh
```

### 3.2 리포트 구성 (`scripts/analysis/weekly_edge_review.py`)

1. **Setup별 성과:** trades, win_rate, avg_R:R, EV, 슬리피지, 누적 PnL
2. **백테스트 vs 실거래 괴리:** 일치도, 예상-실제 PnL 차이
3. **리스크 이벤트:** kill switch 트리거, 연속 손실 기록, spread widening 차단 횟수
4. **데이터 품질:** 뉴스 수집량, macro 스냅샷 결측 건수, scoring fallback 비율
5. **권장 액션:** EV 음수 Setup 일시정지, 파라미터 재튜닝 대상

### 3.3 발송

- Telegram `TELEGRAM_BRIEFING_*` 채널에 요약
- 상세 HTML 리포트는 `reports/weekly/YYYY-WW.html` 저장
- Slack 없으면 Telegram 대체

---

## 4. 운영 대시보드 (최종 세트)

| 화면/지표 | 출처 | 비고 |
|----------|------|------|
| Cockpit overview | 신규 | 당일 PnL, 포지션, 시그널 발생 |
| Data quality indicators | Phase 1 확장 | 수집/스코어링 건강성 |
| Decision-engine indicators | Phase 3 | Setup별 시그널, 필터 거부율 |
| Execution indicators | Phase 4 | 슬리피지, 체결률, 레이턴시 |
| Risk indicators | Phase 4 + 신규 | MDD, 연속손실, VaR, kill switch 상태 |
| Existing paper-trading views | 변경 없음 | `rl_mppo` + 주식 페이퍼 |

**시각 일관성:** 모든 신규 대시보드에 `system=futures_paradigm` 태그 label로 `rl_mppo` 지표와 구분.

---

## 5. RL `rl_mppo` 병행 운영 방침

### 5.1 원칙

- **Phase 5 전 기간 동안** `rl_mppo` 운용 유지
- 신 시스템과 **동일 계약/계정에서 동시 진입 금지**
- 두 시스템은 **독립 계좌** 사용 권장 (충돌 완전 배제)
- 독립 계좌 불가 시: `risk_filter`에서 "symbol lock" (동일 심볼 기존 포지션 검출 시 거부)

### 5.2 성과 비교 지표

주간 Edge Review에 `rl_mppo` vs Setup A+C 비교 섹션 추가:
- Sharpe, Win rate, Avg PnL, Max DD
- 3개월 누적 기준 신 시스템이 RL 성능의 50% 이상 달성 시 RL spec 검토 개시

### 5.3 전환 조건 (RL spec과 연계)

다음 모두 충족 시 RL 보조 필터 재학습 검토 (RL spec 참조):
- 신 시스템 3개월 EV+ 유지
- 신 시스템 Sharpe ≥ 1.5
- 평균 슬리피지 ≤ 0.4 tick

---

## 6. 롤백 & 긴급 대응 (원본 부록 B 확장)

### 6.1 자동 롤백 트리거

- Kill switch 작동 → 즉시 정지 (Phase 4 §6)
- 주간 Edge Review에서 연속 2주 EV 음수 → Paper 회귀 제안 (사용자 승인)

### 6.2 수동 롤백 런북 (`docs/runbooks/futures-paradigm-rollback.md`)

```
1. 모든 오픈 포지션 시장가 청산 확인
   > sts futures flatten-all --confirm
2. 신 시스템 systemd units 정지
   > systemctl stop kis-news-collector kis-news-scorer ...
3. Decision Engine 비활성화 (config/decision_engine.yaml enabled=false)
4. rl_mppo 운용만 유지 확인
5. 로그 수집 (ClickHouse + Redis + 앱)
6. 24시간 내 근본 원인 분석 완료 전 재개 금지
7. 재개 전 Paper Trading 최소 3일 재검증
```

### 6.3 드릴 연 2회

- 모의 롤백 훈련 (실거래 없는 주말) — 전체 단계 수행 시간 측정

---

## 7. 문서화

### 7.1 신규 런북

- `docs/runbooks/futures-paradigm-operations.md` — 일일 운영 체크리스트
- `docs/runbooks/futures-paradigm-rollback.md` — §6.2
- `docs/runbooks/futures-paradigm-failure-modes.md` — Phase 4에서 작성
- `docs/runbooks/futures-legal-review.md` — Gate 2 산출물

### 7.2 CLAUDE.md 업데이트

Phase 5 완료 시 CLAUDE.md `선물 (Futures)` 섹션 갱신:
- 현재 운용 전략 목록에 Setup A/C 추가
- `rl_mppo` 위치 (메인 → 병행) 업데이트
- 계약 명세 `futures_contract_spec` 섹션 링크

---

## 8. Phase 5 완료 게이트

- [ ] Gate 1-3 모두 통과
- [ ] 3개 신규 운영 대시보드 구축
- [ ] 주간 Edge Review 8주 연속 발행 (Phase 4 말 포함)
- [ ] 롤백 드릴 1회 수행 및 런북 검증
- [ ] CLAUDE.md 업데이트
- [ ] 사용자 서면 승인 (증량 결정은 별도)

---

## 9. 명시적 비범위

- 다계약 증량 (2→5 등 상위 단계는 Gate 4 이후 별도 판단)
- RL 보조 필터 활성화 (RL spec)
- 주식 전략 연동 (주식은 기존 체계 유지)
- 옵션/ELW 등 신규 상품 (본 프로젝트 범위 외)
- `kospi200_full` (F200) 운용 — 본 spec은 mini 전용
