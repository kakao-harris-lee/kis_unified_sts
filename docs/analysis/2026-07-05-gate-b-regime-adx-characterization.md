# Gate B — AdaptiveRegimeDetector ADX 임계값 characterization

- 작성일: 2026-07-05
- 목적: #562(detector ADX를 canonical Wilder로 위임 → 값 ~2배)가 요구한 **연기된 검증**.
  stale 임계값(`adx_strong_trend=25`, `adx_weak_trend=20`)이 doubled ADX에서 regime을
  과분류하는지 실 데이터로 characterize.
- 선행: [[indicator-audit-2026-07-05]], [indicator-m2-handoff](../plans/2026-07-04-indicator-m2-handoff.md)(Gate B 정의).
- 재현: `scripts/analysis/gate_b_regime_char.py` (일봉 parquet + `AdaptiveRegimeDetector`).

## 표본
- 소스: `data/market/stock/daily` 250 심볼, 55바 trailing window마다 `detect()`, forward 5바 수익률.
- **31,127 관측**. 기간 2026-02~06 (~3.5개월).
- ⚠️ **표본 한계**: 단일 강세장(전체 fwd 5바 평균 **+1.10%**), 3.5개월. 하락장 미포함.

## 결과

### [1] Canonical ADX 분포 (25/20이 무엇을 나누는가)
| 지표 | 값 |
|---|---|
| mean / median | 27.01 / 24.53 |
| P(ADX>25, strong) | **48.2%** |
| P(20≤ADX≤25) | 20.5% |
| P(ADX<20, weak) | 31.2% |
| P(ADX>40) / P(ADX>50) | 13.8% / 4.9% |

→ canonical ADX 중앙값이 24.5로 임계값 25 바로 근처. **바의 절반(48%)이 "strong trend"** 로 분류됨.

### [2] Regime 분포 — 현행 25/20
| 상태 | 비율 |
|---|---|
| TRENDING_BULL | 43.7% |
| TRENDING_BEAR | 22.3% |
| CALM_SIDEWAYS | 16.1% |
| VOLATILE_SIDEWAYS | 16.1% |
| MEAN_REVERTING | 1.7% |

→ **TRENDING 합계 66.1%**. 시장이 2/3 시간을 추세로 보내지 않으므로 **추세 과분류**.

### [3] Head-to-head — 50/40 ("old 반-스케일 등가" 보정)
| 상태 | 25/20 | 50/40 |
|---|---|---|
| TRENDING 합계 | **66.1%** | **47.1%** (−19.0pp) |
| CALM_SIDEWAYS | 16.1% | 36.0% |
| MEAN_REVERTING | 1.7% | 0.0% |

→ 임계값을 canonical 스케일에 맞춰 올리면(50/40) 분포가 훨씬 균형적. #562 이전에는 ADX가 ~반-스케일이라 25/20이 사실상 50/40처럼 작동했음(= [3]에 가까움). #562가 ADX를 고치며 [2]로 이동시켰고, 그 이동은 **검증되지 않았음**.

### [4] Counterfactual — regime 라벨별 forward 5바 수익률
| 상태 | n | mean | median |
|---|---|---|---|
| TRENDING_BULL | 13,616 | **+1.449%** | +0.000% |
| VOLATILE_SIDEWAYS | 5,002 | +1.070% | +0.000% |
| MEAN_REVERTING | 537 | +0.833% | +0.170% |
| TRENDING_BEAR | 6,950 | +0.783% | +0.267% |
| CALM_SIDEWAYS | 5,022 | +0.633% | +0.118% |
| (ALL) | 31,127 | +1.097% | — |

- 방향성: BULL(+1.449%) > BEAR(+0.783%), 스프레드 **+0.67pp** — 약한 양(+) 판별력.
- ⚠️ **BEAR 검증 실패**: TRENDING_BEAR의 forward 수익률이 **여전히 양(+0.78%)** — 표본에 하락장이 없어 "bear" 라벨이 실제 하락을 잡지 못함.
- ⚠️ **BULL 중앙값 0.0%**: +1.449% 평균은 우측 꼬리(소수 급등)에 의한 것. 중앙값 기준 BULL은 flat → 판별력 과대평가 주의.

## 판정 & 권고

1. **25/20은 canonical ADX에서 추세 과분류(66% TRENDING)** 이 맞다. #562가 ADX 스케일을 고쳤으나 임계값이 그대로라 regime 분포가 검증 없이 추세 쪽으로 이동했다.
2. **그러나 임계값을 지금 확정 재튜닝할 수 없다**: 표본이 단일 강세장 3.5개월이라 (a) BEAR 라벨을 검증할 하락장이 없고, (b) counterfactual 판별력이 약하며(BULL 중앙값 flat), (c) regime→PnL 인과를 신뢰할 근거가 부족하다.
3. **권고**:
   - **`regime_detection_mode: adaptive`를 계속 OFF(dormant) 유지.** 실 stock=MarketClassifier(MFI-only), RegimeGate=HAR-RV라 이 detector는 현재 라이브 미사용 → 조치 시급성 없음.
   - 활성화 전제조건: **≥3년, 강세/약세/횡보 포함 다중-regime 일봉**으로 재실행 → BEAR arm 검증 + counterfactual 유의성 확보 + 임계값 확정. (KRX 일별정산 적재 필요, [[futures-daily-data-gap-cta-blocked]] 참조.)
   - 활성화 시 잠정값: canonical ADX 스케일엔 **strong~40 / weak~25** 가 교과서 의도("strong trend는 canonical ADX ~40")와 균형 분포에 부합. 단 위 검증 통과 후 확정.
   - 부수: dead config `very_strong_trend: 40`(미배선) 배선 또는 제거.

**결론: #562의 ADX 수정은 정확하나, regime 임계값은 미검증 상태. 데이터 부족으로 재튜닝 보류, adaptive OFF 유지가 정당한 선택.** Gate B는 "통과/실패"가 아니라 **"데이터-블록: 활성화 금지, 다중-regime 데이터 확보 후 재실행"** 으로 판정한다.
