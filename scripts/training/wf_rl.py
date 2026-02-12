"""RL Walk-Forward 검증 스크립트

5M best_model의 성과가 상승장 편향인지 진정한 알파인지 검증.
6개월 Train / 2개월 Test / 2개월 Slide → 4 folds.

Usage:
    python scripts/training/wf_rl.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.config import ConfigLoader
from shared.ml.rl.env import FuturesTradingEnv, RLEnvConfig, mask_fn
from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS

logger = logging.getLogger(__name__)

# Walk-Forward fold 정의: (train_start, train_end, test_start, test_end)
WF_FOLDS = [
    ("2024-12", "2025-05", "2025-06", "2025-07"),
    ("2025-02", "2025-07", "2025-08", "2025-09"),
    ("2025-04", "2025-09", "2025-10", "2025-11"),
    ("2025-06", "2025-11", "2025-12", "2026-01"),
]

TIMESTEPS_PER_FOLD = 2_000_000


def load_all_data() -> pd.DataFrame:
    """ClickHouse에서 전체 데이터 로드 + 피처 계산"""
    from clickhouse_driver import Client as CHSyncClient

    client = CHSyncClient(
        host="localhost", port=9000,
        user="default", password="@1tidh6ls6ls",
    )
    rows = client.execute("""
        SELECT datetime, open, high, low, close, volume
        FROM kospi.kospi200f_1m
        WHERE code = '101S6000'
        ORDER BY datetime
    """)
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])

    calc = RLFeatureCalculator()
    df = calc.calculate(df)
    df = df.dropna(subset=RL_FEATURE_COLUMNS)
    df["date"] = pd.to_datetime(df["datetime"]).dt.date
    df["month"] = pd.to_datetime(df["datetime"]).dt.strftime("%Y-%m")

    return df


def create_mirror(df: pd.DataFrame) -> pd.DataFrame:
    """가격 미러링 데이터 생성"""
    ref_price = df["close"].mean()
    df_mirror = df.copy()
    for col in ["open", "high", "low", "close"]:
        df_mirror[col] = 2 * ref_price - df[col]
    df_mirror["high"], df_mirror["low"] = (
        df_mirror["low"].copy(),
        df_mirror["high"].copy(),
    )
    calc = RLFeatureCalculator()
    df_mirror = calc.calculate(df_mirror)
    df_mirror = df_mirror.dropna(subset=RL_FEATURE_COLUMNS)
    df_mirror["date"] = pd.to_datetime(df_mirror["datetime"]).dt.date
    df_mirror["month"] = pd.to_datetime(df_mirror["datetime"]).dt.strftime("%Y-%m")
    return df_mirror


def split_by_months(
    df: pd.DataFrame,
    start_month: str,
    end_month: str,
    min_bars: int = 300,
) -> list:
    """월 범위로 데이터 필터링 후 일별 분할"""
    mask = (df["month"] >= start_month) & (df["month"] <= end_month)
    subset = df[mask]
    dates = sorted(subset["date"].unique())

    valid_dates = [d for d in dates if len(subset[subset["date"] == d]) >= min_bars]
    return valid_dates


def prepare_fold_data(
    df: pd.DataFrame,
    df_mirror: pd.DataFrame,
    train_dates: list,
    test_dates: list,
) -> tuple:
    """fold별 학습/평가 데이터 준비 (정규화 + 일별 분할)"""
    from sklearn.preprocessing import MinMaxScaler

    scaler = MinMaxScaler()
    train_features = pd.concat(
        [df[df["date"] == d][RL_FEATURE_COLUMNS] for d in train_dates]
    )
    scaler.fit(train_features.values)

    def to_day_arrays(date_list, source_df):
        days, prices = [], []
        for d in date_list:
            day_df = source_df[source_df["date"] == d]
            if len(day_df) == 0:
                continue
            feat = scaler.transform(day_df[RL_FEATURE_COLUMNS].values).astype(np.float32)
            ohlc = day_df[["open", "high", "low", "close"]].values.astype(np.float32)
            days.append(feat)
            prices.append(ohlc)
        return days, prices

    train_days, train_prices = to_day_arrays(train_dates, df)
    test_days, test_prices = to_day_arrays(test_dates, df)

    # Mirror augmentation (train only)
    mirror_days, mirror_prices = to_day_arrays(train_dates, df_mirror)
    train_days.extend(mirror_days)
    train_prices.extend(mirror_prices)

    return train_days, train_prices, test_days, test_prices


def train_fold(
    fold_idx: int,
    train_days: list[np.ndarray],
    train_prices: list[np.ndarray],
    test_days: list[np.ndarray],
    test_prices: list[np.ndarray],
    env_config: RLEnvConfig,
    algo_config: dict,
) -> Path:
    """단일 fold 학습 → best_model 경로 반환"""
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
    from sb3_contrib.common.wrappers import ActionMasker
    from stable_baselines3.common.vec_env import DummyVecEnv

    from shared.ml.base import get_device

    save_dir = Path(f"./models/futures/rl/wf_fold{fold_idx}")
    save_dir.mkdir(parents=True, exist_ok=True)

    # Training env
    class _DayRotatingEnv(FuturesTradingEnv):
        def __init__(self, all_days, all_prices, cfg):
            self._all_days = all_days
            self._all_prices = all_prices
            self._day_idx = 0
            super().__init__(day_data=all_days[0], config=cfg, prices=all_prices[0])

        def reset(self, **kwargs):
            self._day_idx = (self._day_idx + 1) % len(self._all_days)
            self.day_data = self._all_days[self._day_idx]
            self.prices = self._all_prices[self._day_idx]
            return super().reset(**kwargs)

    def make_train():
        env = _DayRotatingEnv(train_days, train_prices, env_config)
        return ActionMasker(env, mask_fn)

    def make_eval():
        env = _DayRotatingEnv(test_days, test_prices, env_config)
        return ActionMasker(env, mask_fn)

    train_env = DummyVecEnv([make_train])
    eval_env = DummyVecEnv([make_eval])

    device = get_device("auto")
    policy_kwargs = algo_config.get("policy_kwargs", {})

    model = MaskablePPO(
        "MlpPolicy",
        train_env,
        learning_rate=algo_config.get("learning_rate", 0.0001),
        gamma=algo_config.get("gamma", 0.999),
        gae_lambda=algo_config.get("gae_lambda", 0.95),
        clip_range=algo_config.get("clip_range", 0.2),
        ent_coef=algo_config.get("ent_coef", 0.05),
        vf_coef=algo_config.get("vf_coef", 0.5),
        max_grad_norm=algo_config.get("max_grad_norm", 0.5),
        n_steps=algo_config.get("n_steps", 2048),
        batch_size=algo_config.get("batch_size", 64),
        n_epochs=algo_config.get("n_epochs", 10),
        policy_kwargs=policy_kwargs if policy_kwargs else None,
        device=device,
        verbose=0,
    )

    callbacks = [
        MaskableEvalCallback(
            eval_env,
            best_model_save_path=str(save_dir),
            log_path=str(save_dir),
            eval_freq=10_000,
            deterministic=True,
            verbose=0,
        ),
    ]

    model.learn(
        total_timesteps=TIMESTEPS_PER_FOLD,
        callback=callbacks,
        progress_bar=True,
    )

    return save_dir / "best_model.zip"


def evaluate_model(
    model_path: str,
    test_days: list[np.ndarray],
    test_prices: list[np.ndarray],
    env_config: RLEnvConfig,
) -> dict:
    """모델 평가 → 성과 지표 반환"""
    from sb3_contrib import MaskablePPO

    model = MaskablePPO.load(model_path)

    total_pnl = 0
    total_trades = 0
    total_wins = 0
    total_losses = 0
    long_t = 0
    short_t = 0
    daily_pnls = []
    all_wins = []
    all_losses = []

    for day_features, day_prices in zip(test_days, test_prices):
        env = FuturesTradingEnv(
            day_data=day_features, config=env_config, prices=day_prices
        )
        obs, _ = env.reset()
        terminated = False
        while not terminated:
            masks = env.action_masks()
            action, _ = model.predict(obs, deterministic=True, action_masks=masks)
            obs, _, terminated, _, info = env.step(int(action))

        daily_pnls.append(info["total_pnl"])
        total_pnl += info["total_pnl"]
        total_trades += info["n_trades"]
        total_wins += info["wins"]
        total_losses += info["losses"]
        for t in env.trade_history:
            if t.get("side") == "LONG":
                long_t += 1
            else:
                short_t += 1
            if t["pnl"] > 0:
                all_wins.append(t["pnl"])
            elif t["pnl"] < 0:
                all_losses.append(t["pnl"])

    daily_pnls = np.array(daily_pnls)
    n_days = len(daily_pnls)
    wr = total_wins / max(total_trades, 1) * 100
    long_pct = long_t / max(total_trades, 1) * 100
    wl_ratio = (
        np.mean(all_wins) / abs(np.mean(all_losses))
        if all_wins and all_losses
        else 0
    )
    sharpe = (
        daily_pnls.mean() / daily_pnls.std() * np.sqrt(252)
        if daily_pnls.std() > 0
        else 0
    )
    pos_days = int(np.sum(daily_pnls > 0))

    # Market direction
    first_price = test_prices[0][0, 3]
    last_price = test_prices[-1][-1, 3]
    market_return = (last_price - first_price) / first_price * 100

    return {
        "pnl": total_pnl,
        "trades": total_trades,
        "wr": wr,
        "long_pct": long_pct,
        "wl_ratio": wl_ratio,
        "sharpe": sharpe,
        "pos_days": pos_days,
        "n_days": n_days,
        "market_return": market_return,
        "avg_daily_pnl": daily_pnls.mean(),
    }


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = ConfigLoader.load("ml/rl_mppo.yaml")
    env_cfg = config["env"]
    reward_cfg = config.get("reward", {})
    algo_config = config.get("mppo", {})

    env_config = RLEnvConfig(
        initial_balance=env_cfg["initial_balance"],
        commission_rate=env_cfg["commission_rate"],
        tick_size=env_cfg["tick_size"],
        tick_value=env_cfg["tick_value"],
        contract_multiplier=env_cfg["contract_multiplier"],
        max_contracts=env_cfg["max_contracts"],
        slippage=0.0,
        margin_rate=env_cfg.get("margin_rate", 0.15),
        n_market_features=env_cfg["n_market_features"],
        n_position_features=env_cfg["n_position_features"],
        w_profit=reward_cfg.get("w_profit", 10.0),
        w_cost=reward_cfg.get("w_cost", 0.3),
        w_risk=reward_cfg.get("w_risk", 0.0),
        max_loss=reward_cfg.get("max_loss", -5_000_000),
        loss_penalty_coeff=reward_cfg.get("loss_penalty_coeff", 2.0),
    )

    logger.info("Loading all data...")
    df = load_all_data()
    logger.info(f"Data loaded: {len(df)} rows, dates: {df['date'].min()} ~ {df['date'].max()}")

    logger.info("Creating mirror data...")
    df_mirror = create_mirror(df)

    results = []
    for fold_idx, (tr_start, tr_end, te_start, te_end) in enumerate(WF_FOLDS):
        fold_name = f"Fold {fold_idx + 1}"
        logger.info(f"\n{'='*60}")
        logger.info(f"{fold_name}: Train {tr_start}~{tr_end}, Test {te_start}~{te_end}")
        logger.info(f"{'='*60}")

        train_dates = split_by_months(df, tr_start, tr_end)
        test_dates = split_by_months(df, te_start, te_end)

        logger.info(f"  Train days: {len(train_dates)}, Test days: {len(test_dates)}")

        if len(train_dates) < 10 or len(test_dates) < 5:
            logger.warning(f"  Skipping {fold_name}: insufficient data")
            continue

        train_days, train_prices, test_days, test_prices = prepare_fold_data(
            df, df_mirror, train_dates, test_dates
        )

        logger.info(
            f"  Train arrays: {len(train_days)} (incl. mirror), "
            f"Test arrays: {len(test_days)}"
        )

        # Train
        logger.info(f"  Training {TIMESTEPS_PER_FOLD:,} steps...")
        best_model_path = train_fold(
            fold_idx, train_days, train_prices,
            test_days, test_prices, env_config, algo_config,
        )

        # Evaluate
        logger.info(f"  Evaluating best_model...")
        result = evaluate_model(
            str(best_model_path), test_days, test_prices, env_config,
        )
        result["fold"] = fold_name
        result["train_period"] = f"{tr_start}~{tr_end}"
        result["test_period"] = f"{te_start}~{te_end}"
        results.append(result)

        logger.info(
            f"  Result: PnL {result['pnl']/1e6:+.1f}M, "
            f"{result['trades']}t, WR {result['wr']:.1f}%, "
            f"Sharpe {result['sharpe']:+.2f}, "
            f"Market {result['market_return']:+.1f}%"
        )

    # Summary
    print("\n" + "=" * 90)
    print("WALK-FORWARD RESULTS")
    print("=" * 90)
    print(
        f"{'Fold':>8} | {'Test Period':>14} | {'PnL (M)':>10} | {'Trades':>7} | "
        f"{'WR%':>6} | {'W/L':>5} | {'Sharpe':>7} | {'Mkt%':>6} | {'Pos Days':>10}"
    )
    print("-" * 90)

    total_pnl = 0
    total_trades = 0
    total_days = 0
    total_pos_days = 0
    all_sharpes = []

    for r in results:
        print(
            f"{r['fold']:>8} | {r['test_period']:>14} | {r['pnl']/1e6:>+9.1f}M | "
            f"{r['trades']:>7d} | {r['wr']:>5.1f}% | {r['wl_ratio']:>4.2f} | "
            f"{r['sharpe']:>+6.2f} | {r['market_return']:>+5.1f}% | "
            f"{r['pos_days']:>4d}/{r['n_days']:<4d}"
        )
        total_pnl += r["pnl"]
        total_trades += r["trades"]
        total_days += r["n_days"]
        total_pos_days += r["pos_days"]
        all_sharpes.append(r["sharpe"])

    print("-" * 90)
    avg_sharpe = np.mean(all_sharpes) if all_sharpes else 0
    print(
        f"{'TOTAL':>8} | {'':>14} | {total_pnl/1e6:>+9.1f}M | "
        f"{total_trades:>7d} | {'':>6} | {'':>5} | "
        f"{avg_sharpe:>+6.2f} | {'':>6} | "
        f"{total_pos_days:>4d}/{total_days:<4d}"
    )

    # Verdict
    print("\n" + "=" * 90)
    profitable_folds = sum(1 for r in results if r["pnl"] > 0)
    print(f"Profitable folds: {profitable_folds}/{len(results)}")
    print(f"Avg Sharpe across folds: {avg_sharpe:+.2f}")
    if avg_sharpe > 0.5:
        print("VERDICT: Walk-Forward PASSED — strategy shows consistent alpha")
    elif avg_sharpe > 0:
        print("VERDICT: Walk-Forward MARGINAL — some alpha but inconsistent")
    else:
        print("VERDICT: Walk-Forward FAILED — no consistent alpha detected")


if __name__ == "__main__":
    main()
