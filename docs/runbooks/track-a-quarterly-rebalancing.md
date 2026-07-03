# Track A 분기 리밸런싱 런북

트랙 A(중장기 코어 포트폴리오)의 분기 정기 리밸런싱 절차.
근거: `docs/통합_투자_시스템_전략_설계서.md` §2.2(편입/편출 규칙)·§2.3(리밸런싱
주기)·§1.2(자금 이동 일방향 원칙)·§8.1(주기별 리뷰 체계),
`docs/plans/2026-07-02-unified-investment-system-roadmap.md` §5.3.

> **트랙 A는 수동 트랙이다.** 이 런북의 모든 매매는 operator가 증권사에서
> 직접 집행하고, 시스템에는 `sts portfolio` CLI로 **기록만** 한다. 어떤
> 자동 주문 경로도 존재하지 않는다.

## 실행 시점

| 구분 | 조건 |
|------|------|
| 정기 | 분기 1회 — **1/4/7/10월 첫 거래주** |
| 수시 | 섹터 비중이 목표 대비 **±10%p 이탈** 시 (`rebalancing.drift_threshold_pct`) |
| 수시 | 단일 종목이 코어의 **25% 초과** 시 (`rebalancing.single_holding_max`) |
| 금지 | 일간 가격 변동에 따른 임의 매매 — 트레이딩 충동은 Tier 2에서만 해소 |

## 사전 준비 (리밸런싱 주 첫 거래일 전)

- [ ] 보유 전 종목의 수동 평가 갱신:

  ```bash
  sts portfolio value <symbol> <직전 종가> --date <기준일>
  ```

  (평가가 45일 — `monitor.track_a.valuation_stale_days` — 을 넘기면
  `portfolio:equity:latest`의 `missing_components`에
  `track_a_valuation_stale`이 뜬다. 리밸런싱 전 반드시 해소.)
- [ ] 현재 상태 확인:

  ```bash
  sts portfolio list
  ```

  섹터 실측 vs 목표(방산 35% / 반도체 장비 35% / 로보틱스 15% / 현금 15%)와
  이탈 플래그를 확인한다.

## 체크리스트 1 — Kill Criteria 점검 (편출 기준, 설계서 §2.2)

보유·후보 전 종목에 대해 (`config/portfolio/core_holdings.yaml`):

- [ ] 각 종목의 `kill_criteria` 항목을 하나씩 사실 확인 — **하나라도 발동
      시 편출 검토** (예: 로보틱스 IPO 재추진 → HD현대 할인 논거 소멸)
- [ ] `thesis`(투자 논거 1문장)가 여전히 유효한지 확인 — 논거가 바뀌었으면
      YAML의 thesis를 갱신하고 기록에 남긴다
- [ ] 더 나은 논거의 종목 발견 시 교체 검토 — 단, **월 1회 이상 교체 금지**
      (회전율 억제)
- [ ] `kill_criteria`가 비어 있는 종목이 있으면 즉시 보완 (로더가 경고 로그를
      남긴다 — 편입 기준 위반 상태)

## 체크리스트 2 — 비중 조정

- [ ] `sts portfolio list`의 섹터 비중에서 목표 대비 ±10%p 초과 이탈 섹터
      확인
- [ ] 단일 종목 가치가 코어 총 평가액의 25%를 초과하는지 확인
- [ ] 조정 매매 계획 수립 — 신규 편입은 편입 기준(§2.2) 전부 충족 시에만:
  1. 투자 논거 1문장 기술 가능
  2. Kill Criteria 사전 명시
  3. 분할 매수 계획 (최소 3회 분할, 1회 매수는 목표 비중의 40% 이하)
- [ ] 증권사에서 수동 집행

## 체크리스트 3 — Tier 간 자금 이동 (설계서 §1.2, 일방향 원칙)

- [ ] **Tier 2 → Tier 1 (허용)**: 트레이딩 누적 수익이 초기 Tier 2 자본의
      **+30%를 초과**하면, **초과분의 50%**를 코어로 이전
      (`fund_movement.tier2_to_tier1`). 이전액만큼 `cash_krw` 또는 신규
      매수를 YAML에 반영
- [ ] **Tier 1 → Tier 2 (원칙 금지)**: 트레이딩 손실 보전용 코어 매도 금지.
      유일한 예외(6개월+ EV 양수 검증, 연 1회 리밸런싱 시점)는 문서화된
      수동 결정으로만
- [ ] **Tier 3**: `/market`의 Tier 3 게이지(`portfolio:tier3:watch`) 확인 —
      `triggered=true`(KOSPI 고점 대비 −15% 이상)이고 코어 논거가 훼손되지
      않았으면 기회 자본을 **3분할** 투입 검토. 발동 판단·집행 모두 수동

## 체크리스트 4 — 기록 (설계서 §8.1: 분기 산출물 = 리밸런싱 기록)

- [ ] 집행한 모든 매매를 원장에 기록 (**주문 아님 — 사후 기록**):

  ```bash
  sts portfolio record buy  <symbol> <shares> <체결가>
  sts portfolio record sell <symbol> <shares> <체결가>
  ```

- [ ] `config/portfolio/core_holdings.yaml`의 `shares`/`avg_price`/`cash_krw`
      를 체결 결과로 직접 갱신 (CLI는 이 파일을 재기록하지 않는다)
- [ ] 편입/편출 종목의 `holdings`/`candidates` 항목과 `thesis`/`kill_criteria`
      갱신
- [ ] 체결가 기준으로 평가 갱신: `sts portfolio value <symbol> <price>`
- [ ] `sts portfolio list`로 최종 비중이 목표 밴드 내인지 재확인
- [ ] 리밸런싱 요약(사유·매매 내역·전후 비중·Kill Criteria 판정)을 git 커밋
      메시지 또는 분기 리뷰 노트에 남긴다 — YAML 변경분이 그 자체로 감사
      기록이 된다

## 참조

- 원장/스키마: `config/portfolio/core_holdings.yaml` (주석에 스키마 문서)
- 평가 사이드카: `config/portfolio/core_holdings_valuations.yaml` (CLI 관리)
- 로더: `shared/portfolio/core_holdings.py`
- 모니터 발행: `services/portfolio_monitor/` — `portfolio:equity:latest`
  (`track_a_equity`), `portfolio:tier3:watch`
- 자금 이동/트리거 파라미터: `config/portfolio.yaml::fund_movement`
