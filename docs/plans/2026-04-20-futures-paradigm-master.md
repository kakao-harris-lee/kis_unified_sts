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
| 외국인 수급 | **틱 단위** foreign/sell volume | **Q1-D 결정으로 Setup B 전면 drop** |
| 선물 주문 | Passive Maker 지정가 + OCO | **시장가 전용** (`executor.py:350`), OCO 없음 |
| 슬리피지 추적 | `order_fills` ClickHouse 테이블 | 모델은 있으나 (`slippage_model.py`) DB 스키마 없음 |
| 리스크 | 일/주간 MDD + 연속손실 + 스프레드 + 시간대 | 일일 MDD만 (`shared/risk/manager.py:289`) |
| 계약 명세 | 원본 지침서 `0.05` tick 가정 (F200용) | **확정: 미니 multiplier 50k, tick 0.02pt, tick value 1k** (§Q4) |
| 시그널 파이프라인 | `candidate → risk_filter → final` | 단일 단계 (`StrategyManager.check_entries()`) |
| 포지션 사이징 | Fixed-fractional (stop × multiplier) | `RiskBasedSizer` (loss per share) — multiplier 개념 없음 |
| 계약 승수 | YAML 로드 | **하드코딩 50,000** (`arbitrage/config.py`, `trend/config.py`) — 프로젝트 규칙 위반 |
| Kill switch | 6개 자동 정지 조건 | 일일 손실 블록 1개만 |
| 디렉터리 구조 | `kospi200-trading/` 신규 | 기존 `kis-unified-trading/` 진화 |

---

## 2. 결정된 사항 (2026-04-20 사용자 확정)

### Q1. 외국인 수급 실시간 데이터 — **DROP Setup B (Q1-D 채택)**
KIS `H0STCNT0`는 투자자별 틱 데이터 미노출, KRX는 장중 10분 지연, 키움 병행은 운영 부담 과다.
**결정:** Setup B 전면 제거. Setup A(gap reversion) + Setup C(event reaction) 2개만 구축.
**파급:** Phase 1에서 `foreign_flow_collector`, `stream:foreign.flow.raw`, `investor_flow_raw` 테이블, `shared/flow/` 모듈 모두 삭제. `config/flow_sources.yaml` 미작성.

### Q2. 매크로 야간 데이터 소스 — Yahoo Finance + ECOS로 확정
- S&P 500 / Nasdaq / VIX / DXY / US10Y: **`yfinance`** (기존 RL 데이터용 이미 사용 중)
- USDKRW: **한국은행 ECOS API**
- Eurex KOSPI 야간: Phase 1 우선 제외 (스크래핑 부담), Phase 3 이전 KRX 야간 세션 데이터 재검토

### Q3. Investing.com API — **DROP (사용자 확정: 계약 없음)**
**파급:** Phase 1 `config/news_sources.yaml`에서 `investing` 섹션 삭제. 뉴스 소스 축소: DART + Yonhap + Reuters + MK 어댑트.

### Q4. 미니 KOSPI200 선물 계약 명세 — **확정**

| 항목 | 값 |
|------|-----|
| 거래승수 (Multiplier) | **50,000원 / 1포인트** |
| 호가가격단위 (Tick size) | **0.02포인트** |
| 1틱 가치 (Tick value) | **1,000원** (= 50,000 × 0.02) |

**파급 — 기존 코드 정정 필요:**
- `shared/execution/executor.py:803`의 슬리피지 계산 `/ 0.05`는 **풀사이즈 선물**(F200) 가정. 미니는 `0.02`로 분기 필요 → Phase 4에서 계약별 tick_size 파라미터화.
- `shared/arbitrage/config.py`, `shared/trend/config.py`의 `multiplier: int = 50000`은 값은 맞지만 하드코딩은 여전히 규칙 위반 → Phase 3에서 `config/execution.yaml`의 `futures_contract_spec` 섹션으로 이관.
- 원본 지침서 §9.1 `/ 0.05`, §8.3 `50,000원` 하드코딩은 본 spec에서 대체.

**확정 설정 (Phase 3에서 적용):**

```yaml
# config/execution.yaml (신규 섹션)
futures_contract_spec:
  kospi200_mini:
    multiplier_krw_per_point: 50000
    tick_size_points: 0.02
    tick_value_krw: 1000
    commission_rate: 0.00003        # TBD (실계좌 수수료 확인 후)
    symbol_prefix: "A05"
  kospi200_full:
    multiplier_krw_per_point: 250000
    tick_size_points: 0.05
    tick_value_krw: 12500
    commission_rate: 0.00003
    symbol_prefix: "101"
```

### Q5. RL 전환 — 3개월 병행 paper 후 단계적 (확정)
- **Phase 1-5 전체 기간:** `rl_mppo` 운용 유지, 신 시스템은 별도 paper 계정
- **Phase 5 완료 + 3개월 EV+ 유지** 시 RL 재학습 검토 (RL spec 참조)
- 신 시스템과 RL을 **동일 계약에서 동시 운용하지 않는다** (시그널 충돌 방지)

### Q6. 디렉터리 구조 — 기존 `kis_unified_sts/` 진화 (확정)
원본 §15의 `kospi200-trading/` 신규 루트 제안 거부. 신규 모듈:
- `services/news_collector/`, `services/news_scorer/`, `services/macro_overnight_collector/`
- `services/decision_engine/` (Phase 3)
- `shared/news/`, `shared/macro/`, `shared/decision/setups/`
- `shared/risk/filters/` (기존 `shared/risk/manager.py` 확장)
- `infra/clickhouse/migrations/` (신규 마이그레이션 인프라)

~~`services/foreign_flow/`~~ 및 ~~`shared/flow/`~~ — **Q1-D 결정으로 삭제.**

---

## 3. 디컴포지션 — Phase별 Spec 파일

| Phase | Spec 파일 | 기간 | 핵심 산출물 | 검증 게이트 |
|-------|-----------|------|------------|------------|
| **1** | `2026-04-20-futures-paradigm-phase1-data-infra.md` | Week 1-2 | 뉴스/매크로 수집 + ClickHouse 스키마 + Redis stream 정의 | 48h 연속 수집 성공, 누적 데이터 확인 |
| **2** | `2026-04-20-futures-paradigm-phase2-scoring.md` | Week 3-4 | 뉴스 감성 분류기 (LLM per-news scoring) | 1,000건 스코어링, 사람 라벨과 agreement ≥ 70% |
| **3** | `2026-04-20-futures-paradigm-phase3-decision-engine.md` | Week 5 | Setup A/C + RiskFilterLayer + 포지션 사이저 + `signal.candidate→final` 파이프라인 | 단위 테스트 + 과거 6개월 백테스트 EV > 0.5 tick/setup |
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
| ~~KIS 투자자별 틱 데이터 부재~~ | ~~HIGH~~ | **해소: Setup B drop (Q1-D)** |
| 계약 승수/틱 가치 오계산 | CRITICAL→LOW | **해소: §Q4에서 확정값 (50k / 0.02pt / 1k). Phase 4에서 executor `/ 0.05` 분기 처리** |
| Setup 다양성 부족 (A+C만) | MEDIUM | Phase 5에서 EV 관찰 후 Setup D 후보 발굴 고려 (볼륨/옵션 기반 등) |
| LLM API 비용 폭증 | MEDIUM | 일일 예산 상한, 중복 제거 LRU 20k, Phase 2에서 FinBERT 대체 준비 |
| 뉴스 크롤링 ToS 위반 | LOW | DART Open API + RSS만 사용 |
| 기존 RL 운용 중단 리스크 | HIGH | 병행 paper 필수 (§Q5), 검증 전 switch 금지 |
| 백테스트-실거래 괴리 | HIGH | 슬리피지 모델 주간 재보정, Phase 4에서 mini 틱 값 확인 |

---

## 7. 다음 단계

1. ~~마스터 spec 검토 (Q1~Q6)~~ — **완료 (2026-04-20)**
2. ~~Phase 1 spec 작성~~ — **완료 (dropped scope 반영됨)**
3. Phase 2 / 3 / 4 / 5 / RL 재활용 spec 작성 (이번 세션)
4. 사용자 최종 검토
5. 각 Phase spec 확정 후 `writing-plans` skill로 implementation plan 작성 → 구현
