# 선물 패러다임 전환 — 마스터 인덱스 & 디컴포지션

**Status:** Draft (needs user review)
**Source plan:** `docs/plans/2026-04-20-futures-trading-change-paradagms.md`
**Owner:** chihunlee@gmail.com
**Target branch:** `feat/futures-paradigm-shift`

원본 지침서는 8주 로드맵이라 단일 spec으로 구현 불가능하다. 본 문서는 로드맵을 검증 가능한 하위 spec들로 분해하고, 원본 계획과 현재 코드베이스 사이의 **미해결 간극**을 명시한다.

---

## 1. 현재 상태 vs. 원본 계획

| 영역 | 원본 가정 | 현재 실제 |
|------|----------|----------|
| 뉴스 수집 | 6개 소스 워커 | MK + Naver Finance 2개만 (`shared/llm/collectors.py:798-`) |
| 뉴스 스코어링 | 카테고리/감성/impact/direction/confidence/keywords | `news_sentiment` 단일 enum (coarse) |
| LLM 파이프라인 | 실시간 consumer group | 모두 배치 cron (premarket/intraday/close) |
| Redis Streams | 신규 10개 스트림 | 추상화는 이미 존재 (`StreamPublisher`/`StreamConsumer` + consumer groups) |
| 외국인 수급 | **틱 단위** foreign/sell volume | **KIS `H0STCNT0`는 집계 틱만 노출 — 투자자별 분해 없음** (`shared/kis/stock_feed.py:54`) |
| 선물 주문 | Passive Maker 지정가 + OCO | **시장가 전용** (`executor.py:350`), OCO 없음 |
| 슬리피지 추적 | `order_fills` ClickHouse 테이블 | 모델은 있으나 (`slippage_model.py`) DB 스키마 없음 |
| 리스크 | 일/주간 MDD + 연속손실 + 스프레드 + 시간대 | 일일 MDD만 (`shared/risk/manager.py:289`) |
| 시그널 파이프라인 | `candidate → risk_filter → final` | 단일 단계 (`StrategyManager.check_entries()`) |
| 포지션 사이징 | Fixed-fractional (stop × multiplier) | `RiskBasedSizer` (loss per share) — multiplier 개념 없음 |
| 계약 승수 | YAML 로드 | **하드코딩 50,000** (`arbitrage/config.py`, `trend/config.py`) — 프로젝트 규칙 위반 |
| Kill switch | 6개 자동 정지 조건 | 일일 손실 블록 1개만 |
| 디렉터리 구조 | `kospi200-trading/` 신규 | 기존 `kis-unified-trading/` 진화 |

---

## 2. 원본 계획의 미해결 질문 (구현 전 결정 필요)

### Q1. 외국인 수급 실시간 데이터 소스 (BLOCKER)
원본은 `tick.foreign_buy_volume`을 가정하지만 KIS는 이를 노출하지 않는다. 선택지:
- **Q1-A.** KRX Open API의 투자자별 매매동향(장중 10분 지연) 사용 — 실시간 Setup B 트리거 불가
- **Q1-B.** 키움증권 OpenAPI+ 병행 (키움 계좌 별도 필요) — 개발/운영 부담 큼
- **Q1-C.** Setup B를 **지연 허용형** 으로 재설계 — 10분 지연 데이터 + 가격 모멘텀 재확인 조건
- **Q1-D.** 외국인 수급 없이 Setup A + C만 구축 (Setup B drop)

본 마스터 spec에서는 **Q1-C를 기본 가정**으로 제안. Phase 1에서 KRX API 수집기 구축하고, 지연 영향을 Phase 4 백테스트에서 측정한다.

### Q2. 매크로 야간 데이터 소스
원본 `stream:macro.overnight`은 스키마도 소스도 없음. 제안:
- S&P 500 / Nasdaq: Yahoo Finance (`yfinance` — 이미 RL 데이터용 사용 중) 또는 Investing.com
- Eurex KOSPI 야간: EUREX 웹 스크래핑 또는 한국거래소 야간 세션 데이터 (17:00-05:00)
- 환율: 한국은행 ECOS API 또는 Investing.com

Phase 1에서 최소 소스 확보, 스키마 확정.

### Q3. 뉴스 수집 소스 우선순위 & 법적 검토
원본 5개 외부 소스는 robots.txt / ToS 검토 필요. DART Open API는 안전하나 나머지는 크롤링 부담. Phase 1 범위를 **DART + Yonhap RSS + Reuters RSS + Investing.com API** 로 제한하고 한국경제/네이버는 Phase 2 이후로 연기 권장.

### Q4. 계약 승수 / 틱 가치 단일 소스화
미니선물(A05xxx): 계약 승수 250,000원 × 0.05pt = 12,500원/tick? 아니면 원본 지침서처럼 50,000원/pt?
**실거래 전 검증 필수.** KRX 공식 계약 명세로 확정 후 `config/execution.yaml`에 `futures_contract_spec` 섹션 신설.

### Q5. RL 전환 시점 & 호환성
원본 §11은 RL을 "보조 필터"로 재학습한다. **현재 `rl_mppo`는 운용 중**이고 매달 재학습된다. 전환 시나리오:
- **단계 1 (Phase 1-4):** RL은 운용 유지, 새 파이프라인은 별도 계좌/계약으로 paper only
- **단계 2 (Phase 5 검증 후):** 새 시스템이 3개월 EV+ 달성 시 RL 역할 축소
- **단계 3:** RL을 candidate signal의 P(진입 적합) 보조 필터로 재학습

**원본 §11의 "RL을 메인에서 버린다"는 표현은 오해 소지.** 운용 중단은 신 시스템 검증 후 단계적.

### Q6. 디렉터리 구조
원본 §15는 `kospi200-trading/` 신규 루트를 제안. **거부.** 기존 `kis_unified_sts/` 컨벤션을 따른다:
- 새 서비스: `services/news_collector/`, `services/news_scorer/`, `services/foreign_flow/`, `services/macro_overnight/`, `services/decision_engine/`
- 엔진 로직: `shared/decision/setups/` (Setup A/B/C)
- 리스크 필터 확장: `shared/risk/filters/`
- ClickHouse 마이그레이션: `infra/clickhouse/migrations/` (신규)

---

## 3. 디컴포지션 — Phase별 Spec 파일

| Phase | Spec 파일 | 기간 | 핵심 산출물 | 검증 게이트 |
|-------|-----------|------|------------|------------|
| **1** | `2026-04-20-futures-paradigm-phase1-data-infra.md` | Week 1-2 | 뉴스/수급/매크로 수집 + ClickHouse 스키마 + Redis stream 정의 | 24h 연속 수집 성공, 누적 데이터 확인 |
| **2** | `2026-04-20-futures-paradigm-phase2-scoring.md` | Week 3-4 | 뉴스 감성 분류기 (LLM per-news scoring), 수급 trend 집계 | 1,000건 스코어링, 사람 라벨과 agreement ≥ 70% |
| **3** | `2026-04-20-futures-paradigm-phase3-decision-engine.md` | Week 5 | Setup A/B/C + RiskFilterLayer + 포지션 사이저 + `signal.candidate→final` 파이프라인 | 단위 테스트 + 과거 6개월 백테스트 EV > 0.5 tick/setup |
| **4** | `2026-04-20-futures-paradigm-phase4-execution.md` | Week 5-6 | Passive Maker 라우터 + OCO + force-close + 슬리피지 로깅 + Kill switch | Paper 100회 체결, 슬리피지 ≤ 0.4 tick 평균 |
| **5** | `2026-04-20-futures-paradigm-phase5-rollout.md` | Week 7+ | Paper→Live 게이트, Grafana 대시보드, 주간 Edge Review, 롤백 런북 | 2주 소액 실전 일일 MDD ≤ 3%, 누적 PnL > 슬리피지+수수료 |
| **RL** | `2026-04-20-futures-paradigm-rl-repurposing.md` | Phase 5 이후 | RL을 진입 적합성 보조 필터로 재학습 | 로깅 전용 3개월 → A/B 비교 → 편입 |

각 Phase spec은 **이전 Phase의 검증 게이트가 통과되어야** 착수한다.

---

## 4. 공통 횡단 원칙

1. **기존 컨벤션 준수.** `shared/config/base.py`의 `ServiceConfigBase` 상속, ConfigLoader, EntryRegistry, `docs/plans/` 컨벤션. 신규 디렉터리 금지(§Q6).
2. **하드코딩 금지.** 계약 승수, 임계값, 시간대는 모두 YAML. 코드 리터럴 감지되면 PR 반려.
3. **feature branch 필수.** `feat/futures-paradigm-phase1-*` 등. main 직접 커밋 금지.
4. **Redis DB 1 사용.** 기존 프로젝트 규칙.
5. **테스트 필수.** `pytest tests/` 통과 + 각 Setup/Filter에 단위 테스트.
6. **Telegram 알림.** 기존 `shared/notification/telegram.py` 재사용 — 신규 채널 만들지 않고 `TELEGRAM_FUTURES_*` 또는 `TELEGRAM_BRIEFING_*`에 tag prefix.
7. **ClickHouse TTL.** 뉴스 2년, 수급 1년, 시그널/체결 5년, 일일 성과 영구 (스키마 §3 참조).
8. **RL 운용 단절 금지.** 원본 §11은 "메인에서 버림"이라 표현하나, 신 시스템이 검증될 때까지 `rl_mppo` 운용은 유지한다. 두 시스템은 다른 계약/계좌로 병행 paper.

---

## 5. 성공 기준 (전체)

원본 지침서의 Phase 4/5 조건을 그대로 계승:
- 2주 소액 실전 중 일일 MDD -3% 초과 없음
- 누적 수익 > 슬리피지 + 수수료
- 실거래 슬리피지 ≤ 0.4 tick 평균
- 백테스트 대비 실시간 시그널 발생 일치도 > 95%

---

## 6. 리스크 레지스터

| 리스크 | 심각도 | 완화책 |
|--------|--------|--------|
| KIS 투자자별 틱 데이터 부재 (Q1) | HIGH | Setup B 지연 허용 재설계, 또는 drop |
| 계약 승수/틱 가치 오계산 (Q4) | CRITICAL | 실거래 전 KRX 공식 명세 재확인, 샌드박스 1계약 테스트 |
| LLM API 비용 폭증 | MEDIUM | 일일 예산 상한, 중복 제거 LRU 10k, Phase 2에서 FinBERT 대체 준비 |
| 뉴스 크롤링 ToS 위반 | MEDIUM | Phase 1은 공식 API/RSS만 사용 |
| 기존 RL 운용 중단 리스크 | HIGH | 병행 paper 필수, 검증 전 switch 금지 |
| 백테스트-실거래 괴리 | HIGH | 슬리피지 모델 주간 재보정, Phase 3에서 ATS 미지원 명시 |

---

## 7. 다음 단계

1. **이 마스터 spec 사용자 검토** (미해결 질문 Q1~Q5 답변 필요)
2. Phase 1 spec 상세 작성 (`2026-04-20-futures-paradigm-phase1-data-infra.md`) — 이번 세션에서 진행
3. Phase 2-5 + RL spec은 Phase 1 검토 승인 후 별도 세션에서 작성
4. 각 Phase spec 확정 후 `writing-plans` skill로 implementation plan 작성 → 구현
