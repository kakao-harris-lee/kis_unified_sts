# 통합 투자 시스템 구현 로드맵 (Unified Investment System Roadmap)

> **상위 문서**: [docs/통합_투자_시스템_전략_설계서.md](../통합_투자_시스템_전략_설계서.md) (v1.0, 2026-07-02)
> **본 문서 목적**: 설계서의 전략 체계(트랙 A/B/C, 자본 3-계층, 시장 국면 엔진, 통합
> 리스크 예산)를 **현재 코드베이스에 실제로 매핑한 구현 로드맵**. 추가로 하락장
> 대응을 위한 **선물 시장구조 기반 Market Risk Score(0~100) 시스템**과 그 대시보드
> 투명성 설계를 포함한다.
> **작성일**: 2026-07-02 · **상태**: Active
>
> 기존 [ROADMAP.md](../ROADMAP.md)(Stock/Futures 자산별 로드맵)를 대체하지 않는다.
> 이 문서는 그 위에 얹히는 **크로스에셋 통합 트랙**이며, 충돌 시 리스크 규칙은
> 설계서 > 본 로드맵 > 자산별 로드맵 순으로 우선한다. 단, 저장소 불변 규칙
> (CLAUDE.md)은 설계서보다 우선한다 — §1 조정 사항 참조.

---

## 1. 설계서 ↔ 현재 시스템 조정 사항 (Reconciliation)

설계서는 시스템 외부에서 작성된 마스터 전략 문서다. 코드베이스 현실과 충돌하는
항목은 아래와 같이 **명시적으로 조정**하고, 이 조정이 본 로드맵 전체에 적용된다.

| # | 설계서 내용 | 현재 시스템 현실 | 조정 결정 |
|---|---|---|---|
| R1 | Layer 6: ClickHouse 통합 스키마 | ClickHouse는 2026-06-03 런타임에서 완전 제거. Redis DB 1 + SQLite `RuntimeLedger` + Parquet/DuckDB가 현행 | 설계서의 "ClickHouse 적재"는 전부 **RuntimeLedger(신호/주문/체결) + Parquet/DuckDB(일별 시계열)**로 읽는다. ClickHouse 재도입 금지 |
| R2 | Layer 4: "RL 모델을 진입 확률 필터로 보조 사용" | RL/TFT 경로는 2026-06-03 완전 제거, 재도입 금지 (CLAUDE.md 불변 규칙) | **RL은 필터로도 재도입하지 않는다.** 해당 역할은 LLM 컨텍스트(veto/risk_mode/size_factor) + RegimeGate + 신규 Market Risk Score가 대신한다 |
| R3 | Layer 3: 트랙 B = VR 시스템 (VR 1차 트리거) | `vr_composite`는 성과 문제로 disabled. 현재 활성: `momentum_breakout`, `pattern_pullback`, `williams_r` | 트랙 B = **decoupled stock pipeline 전체**로 정의. 설계서 3.1/3.2의 규칙(국면 필터, ATR 손절/익절 규격, 1% 리스크 사이징)은 특정 전략이 아니라 **파이프라인 공통 정책**으로 구현. VR 재활성화는 별도 evidence 게이트 |
| R4 | Layer 5: `stream:regime.daily` 단일 스트림 | 국면 판단이 3곳에 분산: HAR-RV `RegimeGate`(선물), median-MFI `stock:daemon:market_regime`(주식 bear-exit), LLM `risk_mode`(양쪽 소프트 게이트) | 신규 **통합 국면 엔진**이 셋을 대체하지 않고 **상위에서 합성**한다(§4). 기존 게이트는 유지, 신규 엔진은 shadow → 검증 → enforcement 순서로 진입 |
| R5 | Layer 6.3: 개인 Claude 환경 분리 | 운영 관행 사항 | 코드 변경 없음. 운영 체크리스트에만 반영 |
| R6 | 트랙 C 당일청산 전제 | 야간 세션 비활성(18:00–06:00 미거래), 08:45 정규장, full vs Mini 상품 정책 미확정 (ROADMAP 미결) | Risk Score의 야간 입력(미 선물/환율)은 **익일 장전 산출**로 반영. 상품/세션 정책 미결은 헤지 계약수 계산의 선행 조건(§5.4) |
| R7 | 설계서 §9 Phase 1~5 | 저장소는 paper-first + evidence 게이트 문화, F-9/Phase 5 게이트 진행 중 | 설계서 Phase를 본 문서 §7의 Phase 0~6으로 재구성. 기존 자산별 게이트(F-9, Phase 5 live)는 그대로 병행 |

---

## 2. 현재 상태 진단 (2026-07-02 조사 기준)

### 이미 있는 것

- **국면/게이트 (자산별 분산, 미통합)**:
  - 선물 `RegimeGate`(`shared/strategy/gates/regime_gate.py`) — HAR-RV 변동성
    percentile(`forecast:vol:current`) 단일 스칼라 기반 진입 필터, 입력 결측 시
    PERMISSIVE fail-open. Setup A/C/D 어댑터·백테스트 엔진에 연결.
  - 주식 국면 — median-MFI 기반 `MarketClassifier`가
    `stock:daemon:market_regime`(TTL 900s)에 발행, M4-X bear-exit이 소비.
    매크로·수급 입력 없음.
  - LLM `MarketContext`(regime/risk_mode/risk_score) — 자산군별 Redis 발행 +
    SQLite `market_context_history`. 단 이 `risk_score`는 RiskMode의 **정적
    매핑(RISK_OFF=75/NEUTRAL=50/RISK_ON=25)**일 뿐 합성 위험지표가 아니다.
- **시장구조 데이터 조각 (수집은 있으나 의사결정 미연결)**:
  - OI — KIS WebSocket 틱 필드로 수신되어 Redis 틱 스트림에 흐르고 KRX 일별
    API 코드도 존재하나, 저장·신호·표시 없음.
  - 베이시스 — `shared/arbitrage/basis_calculator.py`(이론가+z-score)가
    라이브러리로만 존재, 어떤 데몬에도 미연결. KRX 기반 실측 베이시스는 LLM
    야간 스크립트 경로에만 있음.
  - 외국인/기관/프로그램 — KRX 스크레이퍼가 LLM 야간/장전 스크립트 경로에만
    연결(프로그램 매매는 raw JSON 수집만 되고 **파싱조차 안 됨**). 선물 라이브
    경로(`FuturesFlowCollector`)는 investor flow를 **명시적으로 제외** 중.
- **매크로 (수집됨, 소비처 거의 없음)**: `services/macro_overnight_collector`가
  USD/KRW(ECOS)·S&P500/NASDAQ 현물·VIX·DXY·US10Y를 15분 주기로
  `stream:macro.overnight`에 발행. 전략 소비는 Setup A의 `sp500_change_pct`
  단 하나. NQ/ES **선물**·SOX·EUREX 야간 종가는 부재/보류
  (`config/macro_sources.yaml`).
- **리스크 집행**: kill_switch(일 3%/주 7%/연속 6패/API 오류율/뉴스 지연,
  `config/kill_switch.yaml`), `shared/risk/` 필터 계층(daily/weekly MDD,
  consecutive loss 등), live_mode_guard, `/api/trading/risk-exposure`.
- **대시보드**: Cockpit, `/risk`, `/signals`(decision trace), `/event-context`,
  `/coverage`, `/experiments`, `/universe`, `/evidence` 등 Quant Ops Workbench
  P0~P2.

> ⚠️ 주의: `shared/llm/market_analyzers.py`의 `FuturesAnalyzer`/`OptionsAnalyzer`/
> `BondAnalyzer` 등은 현재 **`np.random` 합성 샘플 데이터**를 반환한다. 신규
> Market Risk Score는 이 경로를 입력으로 삼지 않고 Phase 0의 실데이터
> 수집기만 사용한다.

### 없는 것 (본 로드맵이 만드는 것)

| 갭 | 내용 |
|---|---|
| G1 | **통합 크로스에셋 국면 엔진** — RISK_ON/NEUTRAL/RISK_OFF 단일 판정과 트랙별 반응 매트릭스 |
| G2 | **Market Risk Score(0~100) 합성 모델** — 존재하지 않음 |
| G3 | **프로그램 매매 파싱·저장·신호화** — raw JSON 수집 코드만 있고 파싱/저장/신호 없음 |
| G4 | **미결제약정(OI) 활용** — 틱 필드로 흐르기만 하고 저장·신호·표시 전무 |
| G5 | **베이시스 상태 관리** — BasisCalculator 라이브러리만 있고 데몬 연결·이력 보존·콘탱고/백워데이션 상태 분류 없음 |
| G6 | **매크로의 게이트 입력화** — USD/KRW 등이 수집되지만 소비처가 사실상 없음(Setup A의 sp500 하나). NQ/ES 선물·SOX는 수집 자체가 없음 |
| G7 | **일별 시장구조 시계열 저장소** — 외국인 선물 누적조차 Redis TTL 넘게 보존 안 됨 |
| G8 | **시장 위험/국면 대시보드 페이지** — 어디에도 없음 |
| G9 | **헤지 어드바이저** — 현물 보유 vs 선물 노출 넷팅·헤지 권고 로직 없음 |
| G10 | **통합 MDD 감시(전체 자산 기준)·트랙 자본 한도** — 자산별 한도만 존재 |
| G11 | **트랙 A(중장기 코어) 기록 체계** — 시스템에 트랙 A 개념 자체가 없음 |

(G1~G7은 2026-06-28 갭 리서치에서도 동일하게 지적됨:
[investigations/2026-06-28-quant-system-gap-research.md](../investigations/2026-06-28-quant-system-gap-research.md))

---

## 3. 목표 아키텍처

```text
                    ┌──────────────────────────────────────────────┐
                    │  Market Structure Collectors (Phase 0)       │
                    │  외국인 선물수급(일별 누적) · OI · 프로그램     │
                    │  베이시스 · USD/KRW · 미선물(ES/NQ/SOX) · VIX  │
                    └──────────────┬───────────────────────────────┘
                                   │ Redis DB1 스냅샷(TTL) + Parquet 일별 시계열
                                   ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Market Risk Score Engine (Phase 1)                     │
        │  구성요소별 sub-score(0~100) → 가중합 → EMA 평활          │
        │  + Unified Regime: RISK_ON / NEUTRAL / RISK_OFF          │
        │  발행: stream:market.risk, market:risk:latest,           │
        │        regime:unified:daily                              │
        └───────┬─────────────────┬─────────────────┬─────────────┘
                │ (Phase 2 연동)   │                 │
                ▼                 ▼                 ▼
      트랙 B (stock pipeline)  트랙 C (futures)   트랙 A (수동 코어)
      score≥70 → 신규 롱 금지   사이즈/방향 편향    주간 리포트·Tier 3 감시
      국면별 신뢰도 필터        조절 (반응 매트릭스) (자동매매 아님)
                │                 │
                └────────┬────────┘
                         ▼
        ┌─────────────────────────────────────────────┐
        │  통합 리스크 예산 (Phase 3)                   │
        │  전체 자산 MDD -5%/-8%/-12% 서킷 브레이커      │
        │  트랙 자본 한도 (Tier 2 내부 70/30 등)         │
        ├─────────────────────────────────────────────┤
        │  헤지 어드바이저 (Phase 4, paper·권고 전용)    │
        │  현물 β-노출 vs 선물 넷 노출 → 헤지 계약수 권고 │
        └─────────────────────────────────────────────┘
                         │
                         ▼
        대시보드 /market 페이지 + Cockpit 배지 + Telegram 알림 (Phase 1~)
```

원칙 (저장소 불변 규칙 준수):

- 모든 가중치·임계값·밴드·스케줄은 `config/market_risk.yaml`(신규) 등 YAML로만
  정의. 하드코딩 금지.
- Redis DB 1, 신규 키 전부 TTL(운영 24h, 누적 스냅샷 48h). 일별 이력은
  Parquet/DuckDB(`shared/storage/market_data_store.py` 확장).
- KST 기준 산출(장 마감 후 일별 확정 + 장전 갱신 + 장중 인트라데이 갱신).
- 신규 게이트는 전부 **shadow(log-only) → counterfactual 검증 → enforcement**
  3단계. RegimeGate P2-③의 fail-open(PERMISSIVE on miss) 선례를 따른다.
- 주식 스윙 청산은 시그널 기반 유지(EOD 일괄 청산 금지), 선물 롱/숏 대칭 유지.

---

## 4. Market Risk Score 상세 설계

### 4.1 구성 요소와 초기 가중치

각 요소는 롤링 윈도(기본 240거래일) 대비 percentile 또는 클리핑 z-score로
**0~100 sub-score(높을수록 위험)**로 정규화한 뒤 가중합한다. 가중치·윈도·매핑은
전부 `config/market_risk.yaml`.

| 구성 요소 | 원천 데이터 | 위험 방향 | 초기 가중치 |
|---|---|---|---|
| 외국인 선물 순매수 | 당일 순매수 + 20일 누적 (KIS 투자자 매매동향) | 누적 순매도 심화 = 위험↑ | 25 |
| 베이시스 | 현선물 괴리(이론 베이시스 대비), 5일 평균 + 당일 | 백워데이션 심화 = 위험↑ | 15 |
| USD/KRW | 레벨 percentile + 5일 변화율 | 급등 = 위험↑ | 15 |
| 프로그램 매매 | 차익+비차익 순매수 (일별) | 대규모 순매도 = 위험↑ | 10 |
| 미결제약정 | OI 변화 × 가격 방향 조합 (가격 하락 + OI 증가 = 신규 숏 축적) | 숏 축적 = 위험↑ | 10 |
| 해외 지수 선물 | ES/NQ 선물 야간 등락 + ^SOX (Yahoo 직접 조회 확인, 2026-07-02) | 급락 = 위험↑ | 10 |
| 변동성 | HAR-RV 예측 RV (기존 모델 재사용; V-KOSPI는 후순위 추가) | 고변동 = 위험↑ | 10 |
| 지수 추세 | KOSPI MA 배열(5/20/60) + 20일 수익률 (`shared/regime` detector 재사용 또는 신규 산출) | 역배열/하락추세 = 위험↑ | 5 |

- 합성: `score = Σ(wᵢ·subᵢ)/Σwᵢ`, EMA(3) 평활.
- **결측 처리**: 결측 요소는 가중치에서 제외하고 재정규화하되, 결측 요소 목록과
  커버리지 비율을 항상 함께 발행(대시보드 투명성). 커버리지 < 60%면 score는
  `DEGRADED` 플래그와 함께 발행하고 enforcement에는 사용하지 않는다(fail-open).
- **산출 주기**: ① 장 마감 후 일별 확정치(전 요소), ② 장전 08:00 갱신(야간 미선물·
  환율 반영), ③ 장중 30분 주기 인트라데이 갱신(외국인 선물·베이시스·프로그램 등
  장중 가용 요소만).
- **장전 산출의 환율 시의성 (2026-07-02 스파이크 확정)**: ECOS 매매기준율은 당일치
  고시가 08:30 이후라 08:00 산출에는 전일치만 존재한다. 따라서 평일 07:45 KST
  장전 수집 세션(Yahoo `KRW=X` 준실시간 역외환율 + ES/NQ)을 신설해 보강하고,
  ECOS는 일별 확정 정본으로 유지한다(출처 필드로 구분).

### 4.2 밴드와 대응 규칙 (설계서 5.2 매트릭스의 수치화)

히스테리시스: 밴드 전환은 ±5점 버퍼를 넘거나 2회 연속 산출에서 유지될 때만 확정
(플래핑 방지).

| Score | 밴드 | Unified Regime | 트랙 B (주식) | 트랙 C (선물) | 트랙 A (코어) |
|---|---|---|---|---|---|
| 0–29 | LOW | RISK_ON | 매수 신호 정상 실행 | 롱/숏 양방향, 정상 사이즈 | 정상 보유 |
| 30–54 | NEUTRAL | RISK_ON~NEUTRAL | 정상 실행 | 양방향, 정상 사이즈 | 정상 보유 |
| 55–69 | ELEVATED | NEUTRAL | 신뢰도 HIGH 신호만 실행 | 양방향, 사이즈 70% | 정상 보유 |
| **70–84** | **HIGH** | **RISK_OFF** | **신규 롱 전면 금지**, 보유분 손절/청산 규칙만 가동 | 신규 롱 금지, 숏 편향 허용, 사이즈 50%, **보유 현물 헤지 검토(어드바이저 발동)** | 신규 매수 중단 |
| 85–100 | CRITICAL | RISK_OFF | 신규 진입 전면 금지 | 신규 진입 금지(청산·헤지 목적 숏만), 헤지 실행 검토 | 신규 매수 중단, **Tier 3 발동 감시**(KOSPI 고점 대비 −15% 워치) |

- Unified Regime 3-상태는 score 밴드 + 지수 추세 방향으로 결정(순수 score 단독이
  아님 — 고점 부근 과열/저점 공포를 구분하기 위해 추세 부호를 함께 본다). 매핑
  규칙도 YAML.
- 기존 게이트와의 관계: LLM veto·HAR-RV RegimeGate·bear-exit은 그대로 두고,
  Unified Regime/score 게이트는 **추가 필터**로 얹는다(가장 보수적인 판정 우선).

### 4.3 발행 체계

| 대상 | 형태 | TTL/보존 |
|---|---|---|
| `market:risk:latest` | Redis hash — score, 밴드, regime, 요소별 sub-score/원값/신선도, 커버리지, DEGRADED 여부 | 24h |
| `stream:market.risk` | Redis stream — 산출 이벤트(장전/장중/일별 확정) | maxlen 캡 |
| `regime:unified:daily` | Redis key — 일별 확정 국면(설계서 `stream:regime.daily` 대응) | 48h |
| Parquet `market_structure_daily` | 일별 전 요소 원값 + sub-score + score + regime (백테스트/검증용 정본) | 영구 |
| RuntimeLedger | 밴드 전환·enforcement 발동 이벤트 감사 기록 | 영구 |

장중 잠정치는 Redis 전용으로 두고, Parquet에는 `premarket`(08:00 시점 지식)과
`close`(마감 확정, replace-day 멱등 덮어쓰기) 2개 스냅샷 행만 기록한다 —
백테스트에서 장중 시점은 `premarket` 행만 참조해 look-ahead를 차단한다
(`LookaheadGuard` 정합). 상세 DDL·키 계약은 2026-07-02 KRX/저장 설계 스파이크
보고 기준.

### 4.4 검증 계획 (enforcement 전 필수 게이트)

1. **백필**: KRX/KIS 일별 데이터로 최소 2년(가용 범위) 백필 → 히스토리컬 score
   재산출.
2. **사후 검증**: score ≥ 70 일자의 이후 5/20일 KOSPI 수익률 분포 vs 전체 분포
   비교(위험 신호의 판별력), 주요 급락 에피소드(예: 2026-07-02 하락장) 재현 확인.
3. **Counterfactual**: 기존 paper 체결에 score 게이트를 소급 적용했을 때의
   차단/허용 손익 비교(RegimeGate counterfactual 스크립트 패턴 재사용).
4. **Shadow 운영**: 최소 10거래일 log-only — 밴드 전환 빈도, 플래핑, 데이터 결측률
   관찰 후 enforcement 전환은 operator 승인.

---

## 5. 세부 트랙별 계획

### 5.1 트랙 B (주식 파이프라인) 연동

- `stock_strategy`(M4-P) 진입 게이트에 score/regime 필터 추가: HIGH 이상 신규 롱
  차단, ELEVATED에서 신뢰도 필터. (shadow → enforcement)
- 설계서 3.2 리스크 규격 정렬 감사: 현행 three-stage exit·리스크 필터 설정을
  "2×ATR 손절(−7% 캡) / 2×ATR 1차 익절 50% / 10일 최저가 트레일링 / 1회 리스크
  = 트랙 B 자본의 1.0%" 규격과 대조하고, 차이는 YAML로 수렴하거나 명시적 편차
  기록으로 남긴다. 일괄 EOD 청산은 계속 금지.
- 상관관계 규칙(설계서 7.2): 트랙 A 보유 종목과 동일 종목 중복 진입 금지 +
  반도체 섹터 비중 상한 40% → `stock_risk_filter`(M4-R)에 설정 기반으로 추가
  (트랙 A 보유 목록은 §5.5의 트랙 A 원장에서 읽음).

### 5.2 트랙 C (선물) 연동

- `decision_engine`에 score 입력 추가: 밴드별 사이즈 계수(70%/50%)와 롱 차단·숏
  편향 허용을 반응 매트릭스 YAML로 반영. 롱/숏 대칭 원칙 유지 — 방향 자체는
  `signal_direction`이 결정하고 score는 허용/사이즈만 조절.
- 설계서 4.2 생존 규칙 정렬 감사: 현행 kill_switch는 일 3%/주 7%/연속 6패를
  커버하고, 연속 4패 → ×0.5 소프트 축소도 `ConsecutiveLossFilter`+사이저에
  이미 존재한다(2026-07-03 감사로 확인 — 갭은 "2주 지속성"과 1계약 base의
  floor-at-1 실효성). 남은 갭: 월간 15% 당월 완전 중단(월간 PnL 추적 부재),
  weekly PnL 리셋 semantics. 상세는 정렬 감사 리포트 참조.
- 분기 수익 인출·증거금 리셋(설계서 4.3)은 수동 운영 절차로 런북화.

### 5.3 트랙 A (중장기 코어) 체계화

- **트랙 A 원장**: RuntimeLedger에 `track_id` 컬럼 도입(B/C 기존 흐름은 각
  파이프라인이 태깅, A는 수동 입력). 수동 매매 기록용 CLI
  (`sts portfolio add|list`) 또는 대시보드 폼(읽기 전용 대시보드 원칙 예외이므로
  CLI 우선).
- **Kill Criteria 문서화**: 보유/후보 종목별 투자 논거 1문장 + 무효화 조건을
  YAML(`config/portfolio/core_holdings.yaml`)로 관리 → 대시보드 표시 + 분기
  리뷰 체크리스트.
- **Tier 3 트리거 감시**: KOSPI 고점 대비 드로다운 워치(−15%)를 /market 페이지와
  Telegram 알림에 연결. 발동 판단·집행은 수동(자동 매수 없음).

### 5.4 헤지 어드바이저 (권고 전용 → 이후 게이트)

- 입력: 트랙 B 보유 현물 롱 명목가(+ 이후 트랙 A 포함 옵션) × 추정 β,
  선물 넷 서명 노출(기존 `/api/trading/risk-exposure` 확장).
- 출력: `순 β-노출 ÷ (선물가 × 승수)` 기반 헤지 계약수 권고 + 근거. **자동 주문
  없음** — 대시보드 카드 + Telegram 권고까지가 Phase 4 범위.
- 선행 조건: full vs Mini KOSPI200 상품/승수/틱 정책 확정(기존 ROADMAP 미결 항목).
  자동 헤지 집행은 별도 plan + operator 게이트로만.

### 5.5 통합 리스크 예산 (설계서 Layer 1·7)

- `config/portfolio.yaml`(신규): Tier 1/2/3 비율, Tier 2 내부 B/C 배분(70/30),
  트랙 C 월간 한도, 자금 이동 규칙 파라미터.
- **통합 MDD 모니터**: 일별 배치가 전체 자산 스냅샷(계좌 잔고 수집 + 트랙 A 원장
  평가액)을 합산해 월간 MDD 산출 → −5% (B/C 신규 사이즈 50%), −8% (B/C 신규
  전면 중단), −12% (전 시스템 정지 + 리뷰 문서 게이트) 서킷 브레이커.
  트랙 A는 MDD 트리거로 매도하지 않는다.
- 발동 경로는 기존 kill_switch/suspended 플래그 체계를 재사용(신규 병렬 메커니즘
  금지).

---

## 6. 대시보드 투명성 설계

### 6.1 신규 `/market` 페이지 (Market Risk & Structure)

| 영역 | 내용 |
|---|---|
| 헤더 | Risk Score 게이지(0~100) + 밴드 배지 + 전일 대비 Δ + Unified Regime 배지 + DEGRADED/커버리지 경고 |
| 구성 요소 분해 | 요소별 sub-score·가중치·기여도·원값·데이터 신선도 테이블 — "왜 74점인가"가 한눈에 보이도록 |
| 트랙 반응 패널 | 현재 발동 중인 지시("트랙 B: 신규 롱 금지 — score 74 ≥ 70"), 어떤 규칙이 발동했는지 명시. shadow 단계에서는 "(shadow — 미집행)" 라벨 |
| 차트 | ① score 90일 이력 + KOSPI 오버레이 ② 외국인 선물 20일 누적 순매수 ③ 베이시스 이력(콘탱고/백워데이션 음영) ④ OI vs 가격 ⑤ 프로그램 일별 순매수 ⑥ USD/KRW ⑦ 해외선물 야간 등락 타일 |
| 헤지 카드 (Phase 4) | 현물 β-노출, 선물 넷 노출, 권고 헤지 계약수, 권고 근거, 권고 이력 |
| Tier 3 워치 | KOSPI 고점 대비 드로다운 게이지(−15% 트리거 라인) |

### 6.2 기존 화면 연동

- **Cockpit**: ops summary 헤더에 score 칩 + regime 배지 추가. LLM 브리핑
  프롬프트에 score/구성요소를 주입해 브리핑이 위험도 근거를 서술하게 함.
- **`/signals` decision trace**: score/regime 게이트의 통과·차단 사유를 기존
  reject-reason 체계에 추가(shadow 단계에서도 "would-have-blocked" 표기).
- **`/risk`**: 크로스에셋 넷 β-노출 행 추가(헤지 어드바이저와 동일 산식).
- **API**: `GET /api/market-risk`(현재값+분해), `GET /api/market-risk/history`,
  `/api/health/summary`에 수집기 신선도 편입. 신규 라우트는 전부
  `services/dashboard` 아래(구 `services/api` 부활 금지).
- **알림**: 밴드 전환(70/85 교차), DEGRADED 진입, 통합 MDD 단계 발동 시 Telegram.

---

## 7. 구현 Phase (게이트 포함)

기존 자산별 트랙(F-9 컷오버, Phase 5 live 게이트, HAR-RV log-RV, Setup C/D 검증)은
**본 로드맵과 병행**하며 서로 블로킹하지 않는다.

### Phase 0 — 시장구조 데이터 기반 (약 1~2주) 🔄 (2026-07-02 착수)

행동 변화 없음(수집·저장만). **모든 후속 Phase의 선행 조건.**

- [x] KIS TR 가용성 검증 스파이크 (2026-07-02 완료): 아래 "데이터 소스 확정" 표에
      반영. 신규 수급 TR은 전부 실전(REAL) appkey 전용(모의 미지원). 잔여 프로브
      3건(`FHPPG04600001` 행 상한, SOX 심볼 표기, `FHMIF10000000` 야간코드 응답)은
      실전 토큰 환경에서 각 1콜 — operator/deploy 호스트
- [x] 매크로 소스 스파이크 (2026-07-02 완료): ES=F/NQ=F/^SOX/KRW=X Yahoo 가용
      확인, V-KOSPI 판정(O6), EUREX 종료 확인(O9), 장전 환율 시의성 갭 확인(§4.1)
- [x] KRX 폴백 평가 + 저장/백필 설계 (2026-07-02 완료): 프로그램·선물 투자자
      동향은 KRX 로그인 장벽으로 스크레이핑 폴백 부적합 → KIS TR 1차(O1 갱신).
      주식 투자자별은 익명 `MDCSTAT02203_OUT` 가용(2년+ 백필 실측). OI·K200
      선물/지수 종가는 KRX Open API(`drv/fut_bydd_trd`, `idx/kospi_dd_trd`) 가용.
      `market_structure_daily` DDL·Redis 키 계약·백필 계획 확정. 기존
      `KRXDataCollector` bld 결함 2건 발견(O10)
- [x] 매크로 수집기 확장 구현 (2026-07-02 완료): Yahoo 티커맵 config화
      (`yahoo_symbols` 섹션), `MacroSnapshot`에 es/nq/sox/usdkrw_realtime 8필드
      additive 추가, 07:45 장전 세션 등록(`deploy/scheduler.crontab` — Compose
      scheduler가 정본으로 판정, 레거시 install_phase1_crontab.sh 미접촉).
      테스트 29건 + 하류 회귀 102건 통과. **scheduler 이미지 리빌드 후 활성화**
- [x] `market_structure` 수집기 (Wave 2b, 2026-07-02 완료):
      `services/market_structure_collector` close(18:40)/premarket(08:00) 모드
      — 외국인 선물(`K2I`/`F001` 장마감 캡처), 프로그램(KIS 일별, tr_cont
      연속조회), OI 스냅샷 파싱(`shared/kis/client.py`), 베이시스, 파생값
      (20일 누적·oi_price_signal 4분면·basis_dev·ma_alignment), Redis 발행
      (§4.3 계약 일치 검증), premarket look-ahead 차단(전일 close + 야간
      신호만). `scripts/backfill_market_structure.py`(`--from-csv` 수동 경로
      포함) + `/api/health/summary`·`/api/health/market-structure` 신선도.
      신규 테스트 79건 + 회귀 655건 통과
- [x] 야간선물 WS 캡처 수집기 (O9, 2026-07-02 완료):
      `services/night_futures_collector` one-shot + `config/night_futures.yaml`
      + `H0MFCNT0` 파싱(`shared/kis/websocket.py`, 공식 예제 2건 교차 검증 —
      mrkt_basis[13]/dprt[14]/OI[18] 확정). 05:50~06:00 KST 마지막 체결 →
      `market:structure:night_close`(TTL 24h), 체결 0건 시 미발행. crontab
      `48 5 * * 2-6`. 테스트 38건 + kis/services 회귀 414건 통과.
      **가동 전 운영 확인**: 활성 근월물 야간 tr_key를 `fo_cme_code.mst`로 확정
      (YAML 주석에 절차 기록, 현재 값은 예시 형식)
- [x] 저장 구현 (2026-07-02 완료): `shared/storage/market_structure_store.py`
      — hive 파티션, premarket/close 2-스냅샷, replace-day 멱등 쓰기 +
      `config/market_structure.yaml`. 단위 테스트 18건 통과
- [x] `KRXDataCollector` bld 결함 수정(O10, 2026-07-02 완료): 투자자별 경로를
      `MDCSTAT02203_OUT`(익명 outerLoader 부트스트랩 + LOGOUT 재시도)으로 교정,
      프로그램 경로는 KIS TR 이관까지 명시적 결측 처리. 테스트 13건 + llm 회귀
      79건 통과
- [x] Redis DB1 스냅샷 발행 (Wave 2b에 포함 완료): `market:structure:latest`
      (24h), `stream:market.structure`(maxlen 5000+24h), cum20(48h),
      `market:structure:night_close`(24h)
- [x] `/api/health/summary` + `/api/health/market-structure` 수집 신선도 노출
      (Wave 2b에 포함 완료)
- **게이트**: 10거래일 무결 수집 + 백필 완료 + 데이터 품질 리포트

#### 데이터 소스 확정 (2026-07-02 스파이크 종합)

| 요소 | forward 수집 | 과거 백필 (≥2년) |
|---|---|---|
| 외국인 선물 순매수 | KIS `FHPTJ04030000`(시장 `K2I`/상품 `F001`) 장중 폴링 + 장마감(15:45+) 확정 스냅샷 캡처 — 일별 확정 TR은 선물 시장 미지원 | KRX 로그인 CSV 수동 1회 익스포트 런북 (익명/`_OUT` 불가) |
| 프로그램 매매 | KIS `FHPPG04600001`(일별) + `FHPPG04600101`(장중, 직전 30분 창 폴링) | KIS `FHPPG04600001` 날짜범위 (행 상한 프로브 후 확정) |
| 미결제약정(OI) | WS 필드[18] 축적 + `FHMIF10000000` 스냅샷 정기 저장(`hts_otst_stpl_qty` 파싱 추가) — OI 이력 REST 미제공 | KRX Open API `drv/fut_bydd_trd`(`OPN_INTRST_QTY`) |
| 베이시스 | KIS K200 현재지수 `FHPUP02100000` + 기존 선물 시세, `shared/arbitrage/basis_calculator.py` 재사용 | KIS `FHKUP03500100`(K200 일봉, `U`/`2001`) + KRX Open API 선물 종가 |
| USD/KRW | ECOS(일별 확정 정본) + Yahoo `KRW=X`(07:45 장전, Wave 2a 구현) | KIS `FHKST03030100`(`X`/`FX@KRW`) 또는 ECOS |
| ES/NQ/SOX | Yahoo (Wave 2a 구현 완료) — KIS 해외 TR은 교차검증 대안 | Yahoo chart API (KIS `HHDFC55020100` 대안, 40건 페이징) |
| KRX 야간 K200 선물 | KIS WS `H0MFCNT0` 05:50~06:00 캡처 — 체결가+`mrkt_basis`+`dprt`+OI 필드 직접 제공, REST 부재 (Wave 2e) | 불가 — forward 축적만 |
| 주식 투자자별(보조) | KRX 익명 `MDCSTAT02203_OUT` (Wave 2c 교정) | 동일 경로 (2년+ 실측) |

레이트리밋/토큰: 실전 REST 초당 20건·WS 세션당 등록 41건·토큰 재발급 1분 1회 —
수집기는 기존 토큰 캐시(`shared/kis/auth.py`)와 `_RateLimiter`
(`shared/execution/rate_limiter.py`)를 재사용하고, 시그널 hot path보다 낮은
우선순위로 분리한다. 수집기별 독립 토큰 발급 금지.

### Phase 1 — Market Risk Score + 통합 국면 엔진 (약 2주) 🔄 (2026-07-02 착수)

- [x] 엔진 (2026-07-03 완료): `shared/risk/market_risk_score.py` +
      `config/market_risk.yaml`(§4 스펙 — 8요소 정규화·가중합·EMA3·히스테리시스
      ±5/2연속·regime 매핑·coverage<0.6 degraded) +
      `services/market_risk_engine` one-shot(premarket 08:05/intraday 30분/
      close 18:45, crontab 등록) + hindcast CLI(look-ahead-free) + HAR-RV
      주입(`forecast:vol:current`, close 시 원값 Parquet 영속) +
      `RuntimeLedger.record_risk_event` 감사 + 기존 Telegram 채널 재사용 알림.
      shadow 전용 — 전략/게이트 미연결. 테스트 67건 통과
- [x] 검증 도구(§4.4, 2026-07-02 완료): 백필 FX 정렬 수정(O11-① 해소 —
      `d < day` 직전 확정 봉, ECOS forward와 정렬),
      `scripts/validation/validate_market_risk_score.py`(판별력 순열 검정 +
      밴드 플래핑 + 에피소드 재현), `market_risk_counterfactual.py`(롱 신규만
      소급 차단, look-ahead 안전, insufficient-data 우아 종료). 테스트 39건
      통과. **실데이터 리포트는 operator 백필 + 1a hindcast `--write` 후 실행**
- [x] 대시보드 `/market` v1 (2026-07-02 완료): `GET /api/market-risk`(+
      `/history`, 컬럼 폴백으로 Phase 0 데이터에서도 동작) + `/market` 페이지
      (밴드 게이지·8요소 분해·트랙 반응 패널 "shadow — 미집행" 상시·score×
      KOSPI 90일/외국인 수급/베이시스 차트·야간 신호 타일) + 내비 링크 +
      Cockpit 칩(미발행 시 자동 숨김). 백엔드 9건+dashboard 회귀 220건,
      프론트 Vitest 82건+lint+build 통과. §6.1 차트 7종 중 OI/프로그램/환율
      차트는 후속(데이터는 history 응답에 포함)
- **게이트**: 사후 검증 리포트에서 score≥70의 판별력 확인 + shadow 10거래일 +
  operator 리뷰 → Phase 2 진행 승인

### Phase 2 — 트랙 연동 (enforcement) (약 2주) 🔄 (2026-07-03 착수)

전 구현이 `config/market_risk_gate.yaml::mode: shadow` 기본값으로 들어간다 —
실차단이 켜지는 enforce 전환은 Phase 1 판별력 리포트 + shadow 10거래일 +
operator 승인 후 YAML 변경으로만 한다.

- [x] 공유 게이트 평가기 (2026-07-03 완료): `shared/risk/market_risk_gate.py`
      + `config/market_risk_gate.yaml` — off/shadow/enforce(기본 shadow),
      fail-open 11경로, 진입 전용, `gate_trace_payload` 고정 계약.
      테스트 71건
- [x] 설계서 3.2/4.2 리스크 규격 정렬 감사 (2026-07-03 완료):
      [investigations/2026-07-03-design-spec-risk-alignment-audit.md](../investigations/2026-07-03-design-spec-risk-alignment-audit.md)
      — 트랙 B 일치 0/부분 2/부재 3, 트랙 C 일치 1/부분 3/부재 2. 후속 티켓
      후보: 월간 15% 래치, 연속 4패 축소의 2주 지속성, 주식 ATR exit 규격,
      weekly PnL 리셋, 분기 리셋 런북. 현행이 더 보수적인 지점(−1.5% 손절,
      1계약 캡, 6패 중단)은 편차 유지 권고
- [x] 트랙 B: M4-P 진입 게이트 배선 (2026-07-03 완료): 사이클당 1회 평가
      (bear gate 패턴), 기술 신호+LLM discovery 후보 모두 trace 첨부
      (`market_risk_gate` 키) + enforce 시 blanket reject(#483 레인)/
      min_confidence 기각, shadow는 throttled 로그만. `_publish_regime` 이후
      평가로 M4-X bear-exit 피드 불가침. `config/stock_market_risk_gate.yaml`
      (신뢰도 라벨→float 매핑). 테스트 187+청산 회귀 111 통과
- [x] 트랙 C: decision_engine 게이트 배선 (2026-07-03 완료): publish 직전
      평가(signal_direction→side, 대칭 유지), enforce 차단 audit 로그 + 곱셈
      사이즈 합성(RiskFilterLayer factor × entry_size_factor, risk_filter
      최소 확장으로 전달 경로 확보), shadow throttled 로그. 테스트 236건 통과.
      **주의**: 현행 futures paper는 모놀리식 경로라 이 게이트는 디커플드 체인
      기동 시에만 작동(O13·F-9와 동일 맥락)
- [x] 리뷰 패스 (2026-07-03, 판정: 커밋 가능): 블로킹 2건 직접 수정 —
      stock_monitor·futures_monitor serializer가 게이트 필드를 드롭해 양 자산
      모두 `/signals` trace 미도달이던 브리지 갭(passthrough+테스트 9건 추가).
      안전 점검(진입 전용/shadow 기본/fail-open/regime publish 순서) 전 항목
      통과. 백엔드 1042건+프론트 93건. 비차단 잔여는 O14
- [x] `/signals` trace 게이트 표시 + `/market` 패널 라이브 (2026-07-03 완료):
      trace 응답에 `market_risk_gate` 블록(다중 소스 폴백, 부재 시 null),
      `/api/market-risk`에 `gate` 섹션(mode+매트릭스), DecisionTracePanel
      "차단됨/shadow — 차단됐을 것" 구분 칩, TrackResponsePanel 라이브
      매트릭스(현재 밴드 강조, gate 부재 시 정적 폴백). 백엔드 228건+프론트
      93건+lint/build 통과
- **게이트**: shadow 대비 enforcement 전환은 operator 승인. 전환 후 2주간
  차단/허용 내역 주간 리뷰

### Phase 3 — 통합 리스크 예산 + 서킷 브레이커 (약 2주) 🔄 (2026-07-03 착수)

서킷 브레이커도 Phase 2와 동일하게 `config/portfolio.yaml::circuit_breaker.mode:
shadow` 기본 — enforce 전환은 드릴 통과 + operator 승인 후 YAML로만.

- [x] `config/portfolio.yaml` + RuntimeLedger `track_id` 태깅 (2026-07-03
      완료): Tier 65/25/10·B/C 70/30·MDD 단계(shadow 기본)·자금 이동 파라미터
      + `shared/portfolio/config.py`(track 매핑 A/B/C). ledger SCHEMA_VERSION
      2 — orders/fills/trades/signal_decisions에 track_id(idempotent ALTER,
      기존 행 NULL, COALESCE upsert), fills/trades 전 기록 경로 태깅(디커플드
      B/C + 모놀리식), track 필터 조회 헬퍼. 테스트 100건+광역 회귀 1255건
- [x] 트랙 C 생존 규칙 정렬 (2026-07-03 완료): 신규 `risk:state:*:period`
      해시(TTL이 월말+grace를 커버, 24h idle 의존 제거) — C1 kill_switch
      `monthly_loss` 0.15 조건+당월 말 래치, C2 4패 ×0.5 축소 14일 지속
      (승리·재기동 생존, `reduce_blocks_at_floor` 기본 false·operator 결정),
      C5 weekly KST 월요일 경계 리셋. 6패 하드 중단 등 기존 보수 값 불변.
      신규 44건+회귀 1029건 통과. 신규 조건도 decoupled killswitch 프로파일
      에서만 평가(O13 커버리지 동일)
- [x] 전체 자산 스냅샷 + 통합 MDD 모니터 + 서킷 브레이커 (2026-07-03 완료):
      `shared/portfolio/equity.py`(capital_base 앵커 + track별 realized/
      unrealized, 실패 시 직전 equity 유지+degraded) +
      `services/portfolio_monitor`(08:50/19:00 크론, idempotent) +
      `portfolio:equity:latest`(fraction 단위) + ledger
      `portfolio_equity_daily` + `shared/risk/filters/portfolio_mdd.py`
      (REDUCE ×0.5/HALT 차단, enforce 전용·fail-open) + FULL_STOP은 기존
      sentinel/suspend 재사용 + `scripts/ops/portfolio_mdd_drill.py`
      (dry-run 11/11 PASS). 월내 단계 래치, shadow 기본
- [x] `/risk` 통합 자산 표시 (2026-07-03 완료): `GET /api/portfolio/equity`
      (+history — ledger는 read-only SQLite URI로 접근, 스키마 생성 원천 차단)
      + 통합 자산 카드 행(트랙 분해·MDD·단계/mode 배지) + 자산 곡선(단계
      전환 마커)·MDD 서브차트(임계선). 배치 미가동 시 empty state.
      백엔드 241건+프론트 113건+lint/build 통과
- [x] 리뷰 패스 (2026-07-03, 판정: 커밋 가능): 블로킹 1건 수정 — 3B는 MDD를
      fraction(−0.0494)으로 발행하는데 3D 프론트가 percent로 가정한 단위
      불일치 → 프론트를 fraction 해석으로 정렬(필드 계약 명문화). risk
      계층 동시 수정(3B/3C)은 충돌 없음 확인. 주말 enforce 공백은 08:50
      프리마켓 크론으로 해소. 백엔드 1494건+프론트 113건+드릴 11/11
- **게이트**: 서킷 브레이커 드라이런(모의 트리거) + kill-switch 연동 드릴 —
      오프라인 드릴은 통과(11/11). 남은 것: 모의투자 서버에서 `--execute`
      드릴(실 sentinel 트립+원복) + enforce 전환은 operator 승인

### Phase 4 — 헤지 어드바이저 (paper·권고 전용) ✅ (2026-07-03 완료)

- [x] 상품 확정: **미니 KOSPI200** (O4 — 정밀도 5배/증거금 1/5, operator 승인)
- [x] 엔진: `shared/portfolio/hedge.py`(β 회귀 120일·클리핑, product-aware
      승수 — 보유 full ×250k/mini ×50k 구분, floor 권고·net≤0→0·stale 생략)
      + `config/hedge_advisor.yaml`(승수는 execution.yaml과 런타임 교차 검증,
      불일치 시 발행 전 loud fail) + portfolio_monitor 통합(_cli fail-safe
      배선 — 어드바이저 실패가 equity 배치를 못 죽임)
- [x] 발행/이력/알림: `portfolio:hedge:latest`(18필드, TTL 24h) +
      `stream:portfolio.hedge` + ledger v4 `hedge_advice`(전환/변경 시에만
      기록) + Telegram rising edge("권고일 뿐 자동 주문 아님" 문구)
- [x] UI: `GET /api/portfolio/hedge`(+history, read-only URI) + `/market`
      헤지 카드("권고 전용 — 자동 주문 없음" 상시 라벨) + `/risk` 순 β-노출 셀
- [x] 리뷰 패스 (2026-07-03, 판정: 커밋 가능): 권고 전용 보증 PASS —
      집행 코드 0건, execution import 가드 테스트(AST+서브프로세스) 실효성
      확인, UI 집행 컨트롤 0건. 계약 18필드 3-way 일치. 중단 복구 감사에서
      프로덕션 미배선(데드 코드)·테스트 전무 블로킹 2건을 해소(테스트 111건
      추가). 백엔드 247건+프론트 125건 통과. 비차단 잔여는 O15
- **게이트 (유지)**: HIGH 밴드 실발생 구간에서 권고 품질 리뷰 후, 자동 헤지
  여부는 별도 plan + operator 게이트로만 논의

### Phase 5 — 트랙 A 운영 체계화 (분기 운영) ⏳

- [ ] 트랙 A 수동 원장 CLI(`sts portfolio`) + `core_holdings.yaml`(Kill Criteria)
- [ ] 상관관계 규칙(동일 종목 중복 금지·섹터 상한)을 M4-R에 연결
- [ ] Tier 3 워치(/market + 알림), 분기 리밸런싱 체크리스트 런북
- [ ] 첫 분기 리밸런싱 실행 기록

### Phase 6 — 통합 성과 피드백 루프 (지속) ⏳

- [ ] 주간: 트랙 B/C 슬리피지·승률·Edge 자동 리포트(RuntimeLedger 배치;
      설계서의 "ClickHouse 주간 배치" 대응)
- [ ] 월간: 통합 자산 곡선·트랙별 기여도·MDD 요약 1페이지 자동 생성
- [ ] 분기: 설계서 8.2 판정 기준(트랙 B 백테스트 대비 60%, 트랙 C EV 검증)
      자동 산출 → 승격/강등/폐지 판단 자료
- [ ] 6개월 후: 첫 통합 평가(설계서 Phase 5 대응)

---

## 8. 열린 결정 / 리스크

| # | 항목 | 내용 |
|---|---|---|
| O1 | ~~KIS TR 가용성~~ **확정 (2026-07-02 스파이크)** | Phase 0의 "데이터 소스 확정" 표 참조. 요지: 프로그램매매는 KIS 일별 TR이 날짜범위 백필까지 지원(KRX 폴백 불필요), 외국인 선물 순매수는 KIS 장중 스냅샷(`K2I`/`F001`)만 가용 → 장마감 캡처로 forward 축적 + 백필은 KRX 로그인 CSV 수동 런북, OI 이력은 REST 미제공 → WS+스냅샷 forward / KRX Open API 백필. 신규 수급 TR 전부 실전 appkey 전용. 잔여 프로브 3건은 실전 토큰 환경에서 각 1콜 |
| O2 | ~~SOX 데이터 소스~~ **해소 (2026-07-02 스파이크)** | `^SOX` Yahoo 직접 조회 확인 — SOXX 프록시 불필요. ES=F/NQ=F/KRW=X도 가용. 단 `macro_sources.yaml`의 `sessions:` 블록은 코드가 소비하지 않는 장식이므로, 확장 시 티커맵 config화 포함 (Wave 2a 구현) |
| O3 | 가중치 초기값 | §4.1은 출발점일 뿐. 백필 사후 검증에서 판별력 낮은 요소는 가중치 조정(전부 YAML이므로 코드 변경 없음). 과최적화 경계 — 요소 추가/제거는 분기 리뷰에서만 |
| O4 | ~~full vs Mini 상품 정책~~ **헤지 상품 확정 (2026-07-03, operator 승인)** | **헤지 어드바이저는 미니 KOSPI200 선물 사용.** 근거: 승수 1/5(5만원/pt)로 헤지 계약수 정밀도 5배 — 현재 Tier 2 자본 규모에서 full 1계약(~9,500만원 명목)은 반올림 오차 자체가 방향성 베팅이 됨. 증거금 1/5, 저장소 실행 가드의 Mini semantics 기본값과 정합. 소액 헤지에서 유동성 차이는 무시 가능. **트레이딩 전략의 상품 governance(기존 ROADMAP 항목)는 별도 결정으로 유지** — 이 확정은 헤지 인스트루먼트에 한정 |
| O5 | 전체 자산 스냅샷 범위 | 트랙 A가 별도 증권사 계좌면 수동 입력 의존 — 정확도 한계를 월간 리뷰에서 보정 |
| O6 | ~~V-KOSPI~~ **판정 확정 (2026-07-02 스파이크)** | Yahoo에 V-KOSPI 없음(404 확인). KRX OpenAPI 파생상품지수는 AUTH_KEY 서비스별 승인 필요 + 일별 종가라 정보 우위 낮음 → **HAR-RV 유지 확정**. 후속: deploy 호스트 KRX_API_KEY로 `idx/drvprod_dd_trd` 1회 검증만 백로그로 유지 |
| O7 | 밴드 전환 빈도 | 히스테리시스에도 횡보장에서 ELEVATED↔HIGH 플래핑 가능성 — shadow 기간 관찰 지표로 지정 |
| O8 | 합성 데이터 오염 방지 | `market_analyzers.py`의 `np.random` 샘플 경로는 Risk Score 입력 금지(실데이터 수집기 전용). 기존 `MarketContext.risk_score`(정적 매핑)와 명칭 혼동 방지를 위해 신규 지표는 `market_risk_score`로 구분하고, 장기적으로 합성 분석기 경로는 실데이터로 교체 또는 제거 |
| O9 | ~~KRX 야간파생시장 종가 신호~~ **확정 (2026-07-02 스파이크)** | 야간 REST 시세는 부재, **WS `H0MFCNT0`(실시간-064)만 가용** — 체결가와 함께 `mrkt_basis`(시장 베이시스)/`dprt`(괴리율)/OI 필드를 직접 제공해 신호 품질이 ES/NQ 프록시보다 우월. 05:50~06:00 KST 캡처 윈도우 수집기로 마지막 체결을 Redis 스냅샷(TTL 24h)에 저장(Wave 2e). 과거 백필 불가(forward 축적만). `eurex_kospi_close` 레거시 필드는 `krx_night_kospi200_close`로 대체 예정 |
| O10 | ~~`KRXDataCollector` 프로덕션 결함~~ **수정 완료 (Wave 2c)** | 투자자매매·프로그램매매 bld가 잘못된 화면 조회 + KRX 로그인 정책 변경으로 수급 수치가 조용히 빈 값이던 결함. 투자자별 경로는 `MDCSTAT02203_OUT`(public `get_investor_trading`)으로 교정, 프로그램 경로는 KIS TR 이관까지 명시적 결측 처리 |
| O14 | Phase 2 리뷰 비차단 지적 (2026-07-03) | ① enforce에서 차단된 선물 후보는 audit 로그에만 남음(스트림/ledger 미기록) — enforce 전환 리뷰 전에 RuntimeLedger 기록 배선 고려(주식은 #483 eval 레인에 기록됨). ② trace의 ledger 폴백(`signal_decisions`)은 현재 기록자 없는 dead path(무해, 감사 기록 배선 시 활성화). ③ 선물 shadow 로그 스로틀 간격 하드코딩(주식은 YAML), throttle 헬퍼 2종 수렴 후보. ④ min_confidence 경계값(=0.7) 고정 테스트 없음 |
| O15 | Phase 4 리뷰 비차단 지적 (2026-07-03) | ① hedge stale 임계(14h) 여유가 10분뿐(19:00 발행→익일 08:50 갭 13h50m) — 크론 지연 시 아침 false stale 가능, `PORTFOLIO_HEDGE_STALE_SECONDS` env로 조정. ② execution import 서브프로세스 가드가 lazy 의존 4종의 전이 그래프 미커버(수동 검증 결과 현재 유입 없음) — 가드 스니펫 확장 권장. ③ `query_hedge_advice` limit이 ASC 선두 N 반환(현 호출자는 정확) |
| O13 | **kill_switch 조건 미평가 가능성 (2026-07-03 감사 발견, 운영 중요)** | 현행 모놀리식 futures paper 운용에서 kill_switch 모니터는 `futures-killswitch` 프로파일 뒤에 있고, 조건 데이터원 `risk:state:futures`는 decoupled `order_router`만 기록 → **일 3%/주 7%/연속 6패 kill 조건이 실제로 평가되지 않고 있을 가능성**. 운용 중 일일 가드는 `risk_management.yaml`의 5%(더 느슨)만. F-9 컷오버 전에 커버리지 정책 결정 필요(모놀리식에도 risk-state 기록 추가 vs 컷오버로 해소). `risk_stock.max_position_risk_pct: 0.02`는 어떤 필터도 소비하지 않는 선언값 |
| O12 | Phase 1 리뷰 비차단 지적 (2026-07-03 검수 패스) | 블로킹 1건(수집 coverage_ratio vs 스코어 risk_coverage_ratio 컬럼 혼용)은 수정 완료. 잔여: ① **premarket score 미영속** — 엔진 premarket 모드는 Redis-only라 premarket Parquet 행에 score 컬럼이 없음 → counterfactual의 premarket 경로는 항상 전일 close 폴백(보수적·안전), 에피소드 표의 premarket 셀은 결측. premarket score 영속화 여부는 §4.4 게이트 운영 후 결정. ② close 행 부재 시 `market:structure:latest` 폴백으로 계산한 값이 `regime:unified:daily`에 확정 기록될 수 있음 — 폴백 시 regime 기록 스킵 검토. ③ 프론트 밴드 경계/트랙 매트릭스는 YAML 정본의 정적 사본 — Phase 2 전 API 노출 검토 |
| O11 | 리뷰 비차단 지적 (2026-07-02 검수 패스) | ① 백필 `usdkrw`가 `KRW=X` 당일 봉을 close 행에 기록 — 봉 확정(~익일 07:00 KST)이 컷오프(18:40)를 넘고 forward 경로(ECOS≈전일 평균)와 ~1일 어긋남. 백테스트 프로토콜상 악용 불가하나 **Phase 1 사후검증 전에** overseas식 직전 봉(`d < day`) 또는 ECOS로 정렬 필요. ② `futs_prdy_ctrt` 부재 시 client가 `change=0.0` 반환 → 결측이 "보합"으로 위장(`oi_price_signal=neutral`) — 수집기에서 raw 필드 부재 구분 권장. ③ 야간 종가 TTL 24h로 월요일 premarket이 금요일 야간 신호를 못 봄 + `night`가 coverage 미포함이라 부재가 안 드러남 — 주말 케이스 정책(누적형 TTL 48h+ 또는 결측 명시) 결정 필요. ④ float 파서 4종·KST now 헬퍼 중복 — shared 유틸 수렴 후보 |

---

## 9. 문서 연동

- [ROADMAP.md](../ROADMAP.md)에 "Cross-Asset" 섹션으로 본 트랙 요약 추가
- [plans/INDEX.md](INDEX.md) Active에 등재
- Phase 완료 시마다 PROJECT_STATUS.md의 Recent Decisions 갱신
- 설계서와 본 문서가 충돌하면: 저장소 불변 규칙(CLAUDE.md) > 설계서 리스크 규칙 >
  본 로드맵 > 자산별 로드맵

---

*⚠️ 본 문서는 개인 시스템 설계 자료이며 투자 자문이 아니다. 모든 enforcement
전환·live 게이트·헤지 집행은 operator 승인 없이 진행하지 않는다.*
