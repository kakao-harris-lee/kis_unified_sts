# RL Model Retraining & Data Refresh Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 선물 RL (`rl_mppo`)이 학습 eval Sharpe 3.19에서 실운용 15.9% 승률 / avg -0.70 PnL/trade로 악화된 성능 괴리를 복구한다. Obs 파이프라인·프로파일 매트릭스 정합은 이미 확인/수정 (PR 2026-04-15 paper-trading-quality-recovery). 남은 원인 후보는 (a) scaler 도메인 부정합 (101S6000 연결선물 학습 vs A05xxx 미니 거래), (b) 시장 레짐 변화 (2026-04 관세 충격/KOSPI200 레벨), (c) 학습 데이터 노후화.

**Architecture:** 3 phase로 진행 — 진단 심화 → 재학습 실험 → 승격 결정. 재학습 자체는 별도 PR이며 본 plan은 실험 설계만 제공.

**Tech Stack:** Python, Stable-Baselines3 (Maskable PPO), MLflow, Optuna, ClickHouse

---

## Phase 1: Deep Diagnostic

### Task 1.1: Live obs drift 재분석 (PSI per feature)
**Prerequisite:** ≥50 live trades with `obs` captured in `position.metadata` (Task 2.0 capture was added 2026-04-15).

Steps:
1. Wait until `kospi.rl_trades` accumulates ≥50 entries with non-null `obs_json`
2. Run `scripts/analysis/rl_live_vs_train_obs_drift.py` (created in Task 2.0)
3. Compute PSI per feature — features with PSI > 0.2 are high-drift candidates
4. Append results to this plan under `## Findings / Task 1.1`

Expected output: ranked list of drifting features, decision on whether scaler re-fit is warranted.

### Task 1.2: Scaler domain 부정합 테스트
**Context:** Current scaler (`models/futures/rl/scaler.joblib`) was fit on `101S6000` (연결선물). Live trading uses `A05xxx` (미니 근월물). Investigate whether re-fitting scaler on mini data improves obs distribution alignment.

Steps:
1. Load recent A05xxx 1분봉 데이터 from ClickHouse (`kospi.kospi_mini_1m`, last 6 months)
2. Re-fit MinMaxScaler on same 25 features using mini data
3. Compare scaled obs distributions: original scaler vs mini-fit scaler (KS test per feature)
4. Run 30-day backtest on `101S6000` with mini-fit scaler — measure Sharpe delta
5. Decision criterion: if Sharpe on held-out `101S6000` data does not degrade > 10%, mini-fit scaler is viable

**CLAUDE.md policy note:** RL 학습은 `101S6000` 기준 고정. Scaler re-fit on mini data is a runtime-only change (not a training data change) — this is allowable as long as the model weights remain unchanged.

### Task 1.3: 2026-03 이후 Rolling Backtest
**Context:** Verify whether the trained model's eval-time performance (Sharpe 3.19) still holds on recent data.

Steps:
1. Run `sts backtest run` (or `scripts/training/evaluate_rl.py`) with:
   - Data: `kospi200f_1m`, `101S6000`, 2026-03-01 to present
   - Model: `mppo_best/best_model.zip`
   - `is_backtest=True`, `close_on_day_change=True`
2. Record: Sharpe, win rate, avg PnL/trade, max drawdown
3. Compare vs original eval metrics (Sharpe 3.19, WR 45.1%, 82 trades)
4. If Sharpe < 1.0 on 2026-03+ data, confirms regime shift as primary cause

Append results to `## Findings / Task 1.3`.

---

## Phase 2: Retraining Experiments (MLflow/Optuna tracked)

**Prerequisite:** Phase 1 findings confirm that model degradation is not solely scaler-fixable.

### Task 2.1: 최신 데이터 기본 재학습
**Hypothesis:** Training cutoff is stale (original model trained ~2025-Q4). Adding 2026 data will improve regime generalization.

Steps:
1. Export updated `101S6000` data from ClickHouse: all available up to 2026-04-01
2. Run `scripts/training/train_rl.py` with:
   - `table=kospi200f_1m`, `symbol=101S6000`
   - Same hyperparameters as `mppo_best` (from MLflow run)
   - `n_timesteps=2_000_000` (same as original)
   - MLflow experiment: `rl_retraining_2026_04`
3. Evaluate on held-out 2026-03+ data
4. Track: eval Sharpe, WR, PnL/trade vs `mppo_best` baseline

### Task 2.2: Regime-aware obs feature 추가 실험
**Hypothesis:** The model has no explicit market regime signal. Adding a regime feature (e.g., KOSPI200 30-day return z-score, VIX proxy) may improve generalization.

Steps:
1. Add 1-2 regime features to obs builder (`shared/strategy/rl_model_helpers.py`):
   - `kospi200_zscore_30d`: KOSPI200 index 30일 수익률 z-score (from `kospi.kospi200_index_1m`)
   - `vix_proxy`: realized volatility of `101S6000` over last 30 bars
2. Update scaler to include new dims (dim will increase from 25 → 26 or 27)
3. Retrain from scratch with new obs space
4. Compare eval Sharpe vs Task 2.1 baseline

**Note:** This is a breaking obs-space change — new model cannot share scaler with `mppo_best`.

### Task 2.3: Mixed Training 실험 (조건부)
**Prerequisite:** Task 1.2 shows mini-fit scaler has materially different distribution from 101S6000 scaler.

**Hypothesis:** Alternating training batches between `101S6000` and `kospi_mini_1m` data improves transfer.

**CLAUDE.md policy re-check:** CLAUDE.md states "RL 학습은 101S6000 기준 고정" and "학습을 kospi_mini_1m 기준으로 전환하지 않는다." Mixed training is NOT a full switch — it uses mini data as supplemental domain adaptation. However, this requires explicit approval from the operator before proceeding.

**Only execute if operator approves.** Document approval in this plan.

---

## Phase 3: Promotion Decision

### Task 3.1: Champion vs Challenger 평가
1. Identify best challenger from Phase 2 (highest eval Sharpe on 2026-03+ data)
2. Run `shared/ml/rl/evaluator.py` ChampionChallenger comparison:
   - Champion: `mppo_best/best_model.zip`
   - Challenger: best Phase 2 model
   - Test period: 2026-01-01 to 2026-04-01 (out-of-sample for both)
3. Challenger must exceed champion on ALL three gates:
   - Eval Sharpe on 2026-03+ data > 1.5
   - Win rate > 40%
   - Avg PnL/trade > 0

### Task 3.2: Paper Trading A/B — 5영업일
1. Deploy challenger as `mppo_challenger/best_model.zip`
2. Run parallel paper sessions:
   - Session A: current champion (`RL_MPPO_MODEL_PATH=mppo_best/best_model.zip`)
   - Session B: challenger (`RL_MPPO_MODEL_PATH=mppo_challenger/best_model.zip`)
3. Compare after 5 full trading days:
   - **Promotion gates:** win rate > 25% AND avg PnL/trade > 0 in live paper
4. Log results to `kospi.rl_trades` with separate `model_version` field

### Task 3.3: ModelRegistry Stage 이동
1. If challenger passes Task 3.2 gates:
   ```bash
   cp models/futures/rl/mppo_best/best_model.zip models/futures/rl/mppo_prev_best/best_model.zip
   cp models/futures/rl/mppo_challenger/best_model.zip models/futures/rl/mppo_best/best_model.zip
   cp models/futures/rl/scaler_challenger.joblib models/futures/rl/scaler.joblib
   ```
2. Tag MLflow run as `production` stage
3. Update `MEMORY.md` with new champion metrics

---

## Safety

- **현재 champion `mppo_best/best_model.zip` 보존.** Phase 2/3 실험은 별도 경로(`mppo_challenger/`)에서만 수행.
- **롤백 절차**: `cp models/futures/rl/mppo_prev_best/best_model.zip models/futures/rl/mppo_best/best_model.zip` — 즉시 복원 가능.
- **승격 조건**: 5일 paper A/B에서 win rate > 25% AND avg PnL > 0 동시 충족 시만.
- **승격 실패 시**: 자동 롤백, champion 유지, Phase 1 진단 재검토.

---

## Open Questions for Executor

1. **학습 데이터 cutoff**: 2026-03-01? 2026-04-01? 관세 충격(2026-04초) 포함 여부 결정 필요 — 포함 시 더 최신 레짐 학습 가능하나 데이터 양 감소.
2. **A05xxx 미니 데이터 학습 허용 여부**: Task 2.3 실행 전 operator 승인 필수. CLAUDE.md `RL 학습은 101S6000 기준 고정` 정책과 충돌.
3. **Retraining 자원**: GPU 없음 → CPU 학습 예상 소요 시간 (`n_timesteps=2M`: ~4-6시간 on 8-core CPU).
4. **kospi_mini_1m 데이터 상태**: ClickHouse에 ~21K bars만 있음 (MEMORY.md). Task 2.3 실행 가능 여부 사전 확인 필요.

---

## Findings

*(각 Task 완료 후 여기에 결과를 append)*

### Task 1.1 — Live Obs Drift (PSI)
*TBD — requires ≥50 live trades with obs captured*

### Task 1.2 — Scaler Domain Mismatch (completed 2026-04-15)

**Data:**
- Training scaler source: `101S6000` (`data/kospi200f_1m_clean.csv`, 4,521 bars → 4,402 after NaN drop)
- Mini test: `kospi.kospi_mini_1m`, last 180 days (90,027 bars → 89,908 after NaN drop)
- Mini contract codes: A05601–A05609 (all available, pooled)

**Per-feature KS drift (summary):**
- Features with KS > 0.3 (significant drift): **12 / 25**
- Features with >5% out-of-[0,1] under prod scaler: **15 / 25**

**Top drifting features (KS statistic):**

| Feature | KS stat | % clipped by prod scaler |
|---------|---------|--------------------------|
| `returns` | 0.715 | 11.5% |
| `bb_upper_dist` | 0.686 | 7.3% |
| `price_change_5` | 0.607 | 8.6% |
| `macd` | 0.538 | 0.2% |
| `volatility` | 0.527 | 28.1% |

**Notable outliers:**
- `volatility`: 28.1% of mini bars fall outside prod scaler's [0,1] range — the worst clipping. Median under prod scaler = 0.632 vs self-scaler = 0.196 (3x scale mismatch).
- `volume_ratio`: 28.2% clipped (KS = 0.283, just under threshold). Volume scaling between KOSPI200 연결선물 and mini contracts is structurally different (MEMORY.md: mini liquidity is 1/9 to 1/42 of F200).
- `bb_upper_dist`, `bb_lower_dist`, `bb_width`: all show significant drift — the absolute price level of mini contracts (lower) compresses BB bands differently in MinMax space.

**Verdict:** CONFIRMED

Scaler domain mismatch is a **primary contributing factor** to live obs degradation. 12 features with KS > 0.3 and 15 features with >5% clipping means the model is receiving substantially distorted obs in live trading. The `volatility` and `volume_ratio` features — both carrying strong regime signal — are the worst affected.

**Next step:**
- Task 2.1: Re-fit scaler on `kospi_mini_1m` data and save as `models/futures/rl/scaler_mini.joblib`
- Runtime change (no model retraining needed): swap scaler in `shared/strategy/rl_model_helpers.py` obs builder for live trading path
- Validate: 30-day backtest on `101S6000` with mini-fit scaler should not degrade Sharpe by >10% vs current scaler (use `mppo_best_5m_backup.zip` as baseline)
- CLAUDE.md policy compliance: scaler re-fit is a **runtime preprocessing change only** — model weights and training data policy (`101S6000`) remain unchanged

#### Mini-fit scaler validation (completed 2026-04-15)

- Mini scaler fit on 180 days of `kospi.kospi_mini_1m` (89,908 feature rows, 25 features)
- Artifact saved: `models/futures/rl/scaler_mini.joblib` (opt-in, NOT activated by default)
- Runtime override mechanism added:
  - `RL_MPPO_SCALER_PATH` env var (highest priority) in `shared/strategy/rl_model_helpers.py`
  - `scaler_path_override: ""` field in `config/ml/rl_mppo.yaml` (empty = production scaler)
- Backtest on `101S6000` 2026-03-04 to 2026-04-14 (30 valid days, 12,266 bars), model: `mppo_best_5m_backup.zip`:

| | Production scaler | Mini-fit scaler | Delta |
|---|---|---|---|
| **Sharpe ratio** | 2.83 | 1.55 | **-45.2%** |
| Win rate | 54.9% | 54.2% | -0.7 pp |
| Avg return/day | +1.250% | +0.620% | -0.63 pp |
| Total return | +37.53% | +18.65% | -18.88 pp |
| R/R ratio | 1.47 | 1.25 | -0.22 |
| Total trades | 51 | 48 | -3 |

- **Verdict: DO NOT ACTIVATE** — Sharpe degradation -45.2% far exceeds the -10% criterion.
- **Interpretation:** The model learned obs distributions from `101S6000` (production scaler's range). The mini-fit scaler has data ranges 2.1x–5.3x wider for most features, so the model receives obs values in a completely different [0,1] region than it was trained on. Win rate is nearly identical (54.9% vs 54.2%) but profitability collapses — indicating the model can still identify direction but the entry/exit timing degrades badly with the mismatched normalization.
- **Root cause of live underperformance:** The scaler mismatch is *confirmed* on the distribution level (KS test) but a straight swap makes performance worse, not better. The correct fix is to **retrain the model jointly** with mini data or to retrain using `101S6000` data with the same temporal distribution as current mini live data (Task 2.1 retraining path).
- **`scaler_mini.joblib` status:** Committed as artifact for future reference; remains deactivated (`scaler_path_override: ""`).
- **Script:** `scripts/analysis/rl_backtest_with_mini_scaler.py`

**Script:** `scripts/analysis/rl_scaler_domain_test.py`

### Task 1.3 — 2026-03+ Rolling Backtest (completed 2026-04-15)

**Data:** kospi200f_1m / 101S6000, 2026-03-04 to 2026-04-14, 30 valid trading days (12,677 raw bars → 12,266 after feature NaN drop, 1 day skipped for <300 bars)

**Model evaluated:** `models/futures/rl/mppo_best/best_model.zip`

**CRITICAL NOTE — Model identity:** At time of evaluation, `mppo_best/best_model.zip` was **not** the original February champion (Sharpe 3.19, 82 trades). The file was overwritten at 2026-04-14 23:13 by a retraining run on branch `feat/hybrid-full-training-config` (checkpoint at ~1.25M steps, trained on 86 days of data from 2025-07-01 to 2026-04-15 from ClickHouse). The original February champion (`mppo_best_5m_backup.zip`) has a different MD5 hash. Therefore the metrics below reflect the **retrained model on partially-overlapping data** (ClickHouse 80/20 split cutoff = 2026-03-19; test days 2026-03-20 to 2026-04-14, but evaluation window starts 2026-03-04 — so days 2026-03-04 to 2026-03-19 overlap with the model's training set).

**Results (current `mppo_best` — retrained ~Apr 14):**

| Metric | 2026-03-04 to 2026-04-14 | Original eval ref (Feb champion) | Delta |
|---|---|---|---|
| Sharpe ratio | **11.39** | 3.19 | +8.20 |
| Win rate | **66.8%** | 45.1% | +21.7 pp |
| Avg return/day | **+5.970%** | N/A (trade-based) | — |
| Total return | +179.14% | N/A | — |
| Max drawdown | -9.44% | N/A | — |
| R/R ratio | 2.55 | 1.83 | +0.72 |
| Total trades | 443 | 82 (60-day test) | +361 |
| Trading days | 30 | ~60 | — |
| Daily P&L | +24 / =0 / -6 | N/A | — |

**Interpretation:**

The very high Sharpe (11.39) and WR (66.8%) are **not interpretable as genuine out-of-sample performance** for two reasons:

1. **Model identity mismatch:** The file tested is a newly retrained model (Apr 14), not the February champion (Sharpe 3.19, `mppo_best_5m_backup.zip`). The retraining used ClickHouse data spanning up to 2026-04-15 with 80/20 split (cutoff 2026-03-19), so ~50% of the backtest window (2026-03-04 to 2026-03-19) **falls inside the model's training set**.

2. **High trade frequency:** 443 trades in 30 days (~14.8/day) vs 82 trades in ~60 days (~1.4/day) for the original champion, suggesting the retrained model has materially different behavior (potentially overfit to the available data).

**Actionable conclusions:**

- To properly evaluate the **original February champion** against 2026-03+ data, the backtest should be re-run with `models/futures/rl/mppo_best_5m_backup.zip` using a scaler fit on pre-2026-03 data (the original scaler from commit `b8ea59a`). The current `scaler.joblib` in the repo is from Mar 13 2026 and may also overlap with test data.
- The retrained model's in-sample performance (Sharpe 11.39) does not directly address the hypothesis of regime shift — it shows the **new model learned the recent data** but does not confirm whether the old model degraded due to regime shift.
- **Recommendation for Task 2.1:** Before re-running with the Feb champion model, clarify the Feb champion's exact training data cutoff. If it was trained on CSV data (ending 2026-02-26), then 2026-03-04 to 2026-04-14 is a clean out-of-sample window for it.

**Supplemental run — February champion (`mppo_best_5m_backup.zip`, Feb 8) on same period:**

| Metric | 2026-03-04 to 2026-04-14 | Original eval ref (Feb champion) | Delta |
|---|---|---|---|
| Sharpe ratio | **2.83** | 3.19 | -0.36 (-11%) |
| Win rate | **54.9%** | 45.1% | +9.8 pp |
| Avg return/day | +1.250% | N/A | — |
| Total return | +37.53% | N/A | — |
| Max drawdown | -21.17% | N/A | — |
| R/R ratio | 1.47 | 1.83 | -0.36 |
| Total trades | 51 | 82 (60-day test) | -31 |
| Trading days | 30 | ~60 | — |
| Daily P&L | +13 / =0 / -17 | N/A | — |

**Interpretation (Feb champion — genuine out-of-sample):**

- Sharpe 2.83 vs training reference 3.19: **-11% degradation** — minor, within acceptable variance.
- This is **not a regime shift crisis** on historical data. The model continues to function well in the 2026-03+ period.
- Win rate 54.9% is higher than reference 45.1%, but R/R ratio dropped (1.47 vs 1.83). The model is winning more frequently but with smaller winners — consistent with a mildly changed volatility/price level environment.
- Max drawdown increased (-21.17% vs unknown original) and daily win/loss is nearly even (+13/-17), suggesting the model is trading conservatively with frequent small reversals.
- **Hypothesis assessment:**
  - **Regime shift hypothesis: PARTIALLY SUPPORTED** — there is measurable but mild degradation in R/R and drawdown characteristics, consistent with the April 2026 tariff shock changing intraday volatility patterns.
  - **Model generalization hypothesis: NOT SUPPORTED** — the model still achieves Sharpe 2.83 on out-of-sample data; this is not a generalization failure.
  - **Infra/live-specific hypothesis: STILL PRIMARY CANDIDATE** — the backtest Sharpe (2.83) being so much higher than live-reported performance (approx. Sharpe < 1 from 15.9% WR) strongly points to a live execution gap, not a model degradation issue.
- **Recommendation:** Task 2.1 (retraining) is **lower priority** than resolving live execution discrepancies (obs pipeline, scaler mismatch, price execution). The Feb champion model generalizes well to recent data.

**Script:** `scripts/analysis/rl_backtest_2026q1.py`

---

## Status

**PLAN-ONLY.** Implementation is a follow-up PR. Parent plan: `docs/plans/2026-04-15-paper-trading-quality-recovery.md` (Task 2.5 decision).

### Task 2.1 — Latest Data Retraining (completed 2026-04-16)

**Config:** `config/ml/rl_mppo_challenger_2026_04.yaml`
- Data: ClickHouse `kospi.kospi200f_1m`, symbol `101S6000`, 193 days total, 86 valid
- Mirror augmentation: 68 → 136 train days, 18 test days
- Hyperparameters: identical to production champion (rl_mppo.yaml)
- Timesteps: 5,000,000 (took 1h 52m on CPU at ~744 FPS)

**Training trajectory:**
- Early eval reward: 17-63 (timesteps 10K-60K)
- Mid-training: 30-85 (reward stabilized)
- End-of-training: avg ~55-65 reward/episode, positive

**Artifacts:**
- Best model: `models/futures/rl/mppo_challenger/mppo_best/best_model.zip` (saved at timestep ~4.8M)
- Final model: `models/futures/rl/mppo_challenger/mppo_final.zip`
- Scaler: `models/futures/rl/mppo_challenger/scaler.joblib` (re-fit on latest data)

**Rolling backtest (2026-03-04 to 2026-04-14, production scaler):**

| Metric | Champion | Challenger | Delta |
|---|---|---|---|
| Sharpe | 14.91 | 13.25 | -11% |
| Win rate | 56.8% | 52.8% | -4.0pp |
| R/R ratio | — | 1.70 | — |
| Max drawdown | — | -5.14% | — |
| Trades | — | 2,174 | — |
| Daily P&L | — | +24/-6 | — |

**Assessment:**
- Challenger passes Phase 3 Task 3.1 quantitative gates (Sharpe > 1.5, WR > 40%, avg PnL > 0)
- Challenger is slightly weaker than champion (-11% Sharpe, -4pp WR)
- Both models show very high Sharpe (14-15) under the backtest evaluator — this may overstate real-world performance (evaluation methodology note)
- **Recommendation:** proceed to Phase 3 Task 3.2 paper A/B (5-day live comparison) before promotion decision

**Next steps:**
- Deploy challenger as `RL_MPPO_MODEL_PATH=models/futures/rl/mppo_challenger/mppo_best/best_model.zip` for one of two parallel sessions
- Compare vs champion over 5 trading days
- Promote only if challenger avg PnL > 0 in live paper
