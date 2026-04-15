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

### Task 1.2 — Scaler Domain Mismatch
*TBD*

### Task 1.3 — 2026-03+ Rolling Backtest
*TBD*

---

## Status

**PLAN-ONLY.** Implementation is a follow-up PR. Parent plan: `docs/plans/2026-04-15-paper-trading-quality-recovery.md` (Task 2.5 decision).
