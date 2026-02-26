"""RL 모델 학습 스크립트

KOSPI200 선물 강화학습 모델 학습/평가 파이프라인.
ClickHouse에서 1분봉 데이터를 로드하고, RL 모델을 학습.

Usage:
    # M-PPO 학습
    python scripts/training/train_rl.py --algo mppo

    # 전체 비교 학습
    python scripts/training/train_rl.py --algo all

    # 슬리피지 분석
    python scripts/training/train_rl.py --algo mppo --slippage-analysis

    # 또는 CLI 사용
    sts rl train --algo mppo
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.config import ConfigLoader
from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS

logger = logging.getLogger(__name__)


def _validate_ohlcv_quality(
    df: pd.DataFrame,
    *,
    symbol: str,
    table: str,
    max_zero_volume_ratio: float = 0.95,
    max_zero_volume_price_move_ratio: float = 0.20,
    reject_duplicate_datetime: bool = True,
    require_monotonic_datetime: bool = True,
) -> None:
    """Validate OHLCV integrity for RL training/evaluation inputs."""
    if df.empty:
        raise ValueError(f"Empty dataset: {table} ({symbol})")

    if "datetime" not in df.columns:
        raise ValueError("Missing required column: datetime")

    if reject_duplicate_datetime:
        duplicate_count = int(df["datetime"].duplicated().sum())
        if duplicate_count > 0:
            raise ValueError(
                f"Data quality check failed ({table}/{symbol}): "
                f"duplicated datetime rows={duplicate_count}"
            )

    if require_monotonic_datetime and not df["datetime"].is_monotonic_increasing:
        raise ValueError(
            f"Data quality check failed ({table}/{symbol}): "
            "datetime is not monotonic increasing"
        )

    if "volume" in df.columns:
        zero_volume_ratio = float((df["volume"] == 0).mean())
        if zero_volume_ratio > max_zero_volume_ratio:
            raise ValueError(
                f"Data quality check failed ({table}/{symbol}): "
                f"zero-volume ratio={zero_volume_ratio:.4f} > {max_zero_volume_ratio:.4f}"
            )

        if "close" in df.columns:
            close_diff = df["close"].diff().abs().fillna(0)
            phantom_ratio = float(((df["volume"] == 0) & (close_diff > 0)).mean())
            if phantom_ratio > max_zero_volume_price_move_ratio:
                raise ValueError(
                    f"Data quality check failed ({table}/{symbol}): "
                    "zero-volume moving-price ratio="
                    f"{phantom_ratio:.4f} > {max_zero_volume_price_move_ratio:.4f}"
                )


def load_data_from_clickhouse(
    config_path: str = "ml/rl_mppo.yaml",
    persist_scaler: bool = False,
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    """ClickHouse에서 1분봉 데이터 로드 및 일별 분할

    Returns:
        (train_days, train_prices, test_days, test_prices)
        각각 일별 배열 리스트
    """
    config = ConfigLoader.load(config_path)
    data_cfg = config.get("data", {})

    symbol = data_cfg.get("symbol", "101S6000")
    database = data_cfg.get("database", "kospi")
    table = data_cfg.get("table", "kospi200f_1m")
    train_ratio = float(data_cfg.get("train_ratio", 0.8))
    min_bars = data_cfg.get("min_bars_per_day", 300)
    quality_cfg = data_cfg.get("quality", {}) or {}
    quality_enabled = bool(quality_cfg.get("enabled", True))
    max_zero_volume_ratio = float(quality_cfg.get("max_zero_volume_ratio", 0.95))
    max_zero_volume_price_move_ratio = float(
        quality_cfg.get("max_zero_volume_price_move_ratio", 0.20)
    )
    reject_duplicate_datetime = bool(
        quality_cfg.get("reject_duplicate_datetime", True)
    )
    require_monotonic_datetime = bool(
        quality_cfg.get("require_monotonic_datetime", True)
    )

    logger.info(
        f"Loading data: {database}.{table}, symbol={symbol}, "
        f"train_ratio={train_ratio}"
    )

    try:
        import os

        from clickhouse_driver import Client as CHSyncClient

        client = CHSyncClient(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
            user=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        )

        query = f"""
            SELECT datetime, open, high, low, close, volume
            FROM {database}.{table}
            WHERE code = %(symbol)s
            ORDER BY datetime
        """
        rows = client.execute(query, {"symbol": symbol})
        df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])

    except Exception as e:
        logger.warning(f"ClickHouse not available: {e}. Using sample data.")
        df = _generate_sample_data()

    if df.empty:
        logger.warning("No data loaded. Using sample data.")
        df = _generate_sample_data()
    elif quality_enabled:
        _validate_ohlcv_quality(
            df,
            symbol=symbol,
            table=f"{database}.{table}",
            max_zero_volume_ratio=max_zero_volume_ratio,
            max_zero_volume_price_move_ratio=max_zero_volume_price_move_ratio,
            reject_duplicate_datetime=reject_duplicate_datetime,
            require_monotonic_datetime=require_monotonic_datetime,
        )

    # 가격 미러링 증강 설정
    mirror_aug = data_cfg.get("mirror_augmentation", True)

    # 미러 데이터 생성 (OHLC를 평균가 기준으로 반전)
    df_mirror = None
    if mirror_aug:
        ref_price = df["close"].mean()
        df_mirror = df.copy()
        for col in ["open", "high", "low", "close"]:
            df_mirror[col] = 2 * ref_price - df[col]
        # 반전 시 high/low 스왑
        df_mirror["high"], df_mirror["low"] = (
            df_mirror["low"].copy(),
            df_mirror["high"].copy(),
        )
        logger.info(
            f"Mirror augmentation: ref_price={ref_price:.2f}, "
            f"original close range [{df['close'].min():.2f}, {df['close'].max():.2f}] → "
            f"mirror close range [{df_mirror['close'].min():.2f}, {df_mirror['close'].max():.2f}]"
        )

    # 피처 계산 (원본)
    calc = RLFeatureCalculator()
    df = calc.calculate(df)

    # 피처 계산 (미러)
    if mirror_aug and df_mirror is not None:
        df_mirror = calc.calculate(df_mirror)

    # NaN 제거
    df = df.dropna(subset=RL_FEATURE_COLUMNS)
    if mirror_aug and df_mirror is not None:
        df_mirror = df_mirror.dropna(subset=RL_FEATURE_COLUMNS)

    # 일별 분할
    df["date"] = pd.to_datetime(df["datetime"]).dt.date
    dates = sorted(df["date"].unique())

    if mirror_aug and df_mirror is not None:
        df_mirror["date"] = pd.to_datetime(df_mirror["datetime"]).dt.date

    # 최소 바 수 필터
    valid_dates = []
    for d in dates:
        day_df = df[df["date"] == d]
        if len(day_df) >= min_bars:
            valid_dates.append(d)

    logger.info(f"Valid dates: {len(valid_dates)} / {len(dates)}")

    # train/test 분할
    split_idx = int(len(valid_dates) * train_ratio)
    train_dates = valid_dates[:split_idx]
    test_dates = valid_dates[split_idx:]

    # 정규화 (MinMaxScaler - 학습셋 fit)
    from sklearn.preprocessing import MinMaxScaler

    scaler = MinMaxScaler()

    # 학습 데이터로 scaler fit
    train_all = pd.concat([df[df["date"] == d][RL_FEATURE_COLUMNS] for d in train_dates])
    scaler.fit(train_all.values)

    # scaler 저장 (학습 시에만; 평가/분석 실행에서 덮어쓰기 방지)
    if persist_scaler:
        save_dir = Path(ConfigLoader.load(config_path).get("training", {}).get(
            "save_dir", "./models/futures/rl/"
        ))
        save_dir.mkdir(parents=True, exist_ok=True)
        scaler_path = save_dir / "scaler.joblib"
        joblib.dump(scaler, scaler_path)
        logger.info(f"Scaler saved to {scaler_path}")

    def split_days(date_list, source_df):
        days = []
        prices = []
        for d in date_list:
            day_df = source_df[source_df["date"] == d]
            if len(day_df) == 0:
                continue
            features = scaler.transform(day_df[RL_FEATURE_COLUMNS].values)
            ohlc = day_df[["open", "high", "low", "close"]].values
            days.append(features.astype(np.float32))
            prices.append(ohlc.astype(np.float32))
        return days, prices

    train_days, train_prices = split_days(train_dates, df)
    test_days, test_prices = split_days(test_dates, df)

    # 미러 데이터를 훈련 세트에만 추가 (테스트 제외)
    if mirror_aug and df_mirror is not None:
        mirror_train_days, mirror_train_prices = split_days(train_dates, df_mirror)
        n_original = len(train_days)
        train_days.extend(mirror_train_days)
        train_prices.extend(mirror_train_prices)
        logger.info(
            f"Mirror augmentation: train {n_original} → {len(train_days)} days "
            f"(+{len(mirror_train_days)} mirrored)"
        )

    logger.info(
        f"Data split: train={len(train_days)} days, test={len(test_days)} days"
    )

    return train_days, train_prices, test_days, test_prices


def precompute_tft_aux(
    config_path: str = "ml/rl_mppo.yaml",
) -> tuple[list[np.ndarray] | None, list[np.ndarray] | None]:
    """TFT 방향 확률을 RL 학습 보조 피처로 사전 계산

    ClickHouse에서 동일 데이터를 로드하고, TFT scaler + 모델로
    각 일/스텝별 [p_up_1m, p_up_5m, p_up_15m] 확률을 계산한다.

    Returns:
        (train_aux, test_aux): 각각 일별 (n_bars, 3) 배열 리스트.
        tft_aux.enabled가 False면 (None, None).
    """
    config = ConfigLoader.load(config_path)
    tft_aux_cfg = config.get("tft_aux", {})

    if not tft_aux_cfg.get("enabled", False):
        return None, None

    import torch
    from shared.ml.tft.dataset import compute_time_features
    from shared.ml.tft.model import TFTModel

    model_path = tft_aux_cfg["model_path"]
    lookback = tft_aux_cfg.get("lookback", 60)

    # TFT 모델 로드
    logger.info(f"Loading TFT model from {model_path}")
    tft_model = TFTModel.load(model_path)
    tft_model.eval()

    # TFT scaler 로드 (RL scaler와 별개)
    tft_scaler_path = Path(model_path).parent / "scaler.joblib"
    tft_scaler = joblib.load(tft_scaler_path)
    logger.info(f"TFT scaler loaded from {tft_scaler_path}")

    # ClickHouse에서 동일 데이터 로드
    data_cfg = config.get("data", {})
    symbol = data_cfg.get("symbol", "101S6000")
    database = data_cfg.get("database", "kospi")
    table = data_cfg.get("table", "kospi200f_1m")
    train_ratio = float(data_cfg.get("train_ratio", 0.8))
    min_bars = data_cfg.get("min_bars_per_day", 300)
    mirror_aug = data_cfg.get("mirror_augmentation", True)

    import os
    from clickhouse_driver import Client as CHSyncClient

    client = CHSyncClient(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )

    query = f"""
        SELECT datetime, open, high, low, close, volume
        FROM {database}.{table}
        WHERE code = %(symbol)s
        ORDER BY datetime
    """
    rows = client.execute(query, {"symbol": symbol})
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])

    # 피처 계산
    calc = RLFeatureCalculator()
    df = calc.calculate(df)
    df = df.dropna(subset=RL_FEATURE_COLUMNS)
    df["date"] = pd.to_datetime(df["datetime"]).dt.date
    dates = sorted(df["date"].unique())

    # 동일 날짜 필터 + 분할
    valid_dates = [d for d in dates if len(df[df["date"] == d]) >= min_bars]
    split_idx = int(len(valid_dates) * train_ratio)
    train_dates = valid_dates[:split_idx]
    test_dates = valid_dates[split_idx:]

    def compute_aux_for_dates(date_list: list) -> list[np.ndarray]:
        """일별 TFT 방향 확률 계산"""
        aux_list = []
        for d in date_list:
            day_df = df[df["date"] == d]
            if len(day_df) == 0:
                continue
            n_bars = len(day_df)
            raw_features = day_df[RL_FEATURE_COLUMNS].values
            scaled = tft_scaler.transform(raw_features).astype(np.float32)
            time_feat = compute_time_features(n_bars)
            combined = np.concatenate([scaled, time_feat], axis=1)  # (n_bars, 28)

            # 결과: (n_bars, 3) — 각 스텝의 [p_up_1m, p_up_5m, p_up_15m]
            day_probs = np.full((n_bars, 3), 0.5, dtype=np.float32)

            # lookback 이후부터 배치로 TFT 추론
            if n_bars > lookback:
                # 배치 구성: 한번에 추론
                batch = np.stack([
                    combined[t - lookback:t]
                    for t in range(lookback, n_bars)
                ])  # (n_bars - lookback, lookback, 28)
                probs = tft_model.predict_direction_probs(batch)  # (n_bars - lookback, 3)
                day_probs[lookback:] = probs

            aux_list.append(day_probs)
        return aux_list

    train_aux = compute_aux_for_dates(train_dates)
    test_aux = compute_aux_for_dates(test_dates)

    # 미러 증강 데이터에 대해서는 중립 확률(0.5) 사용
    if mirror_aug:
        n_original = len(train_aux)
        mirror_aux = [
            np.full_like(a, 0.5) for a in train_aux
        ]
        train_aux.extend(mirror_aux)
        logger.info(
            f"TFT aux: {n_original} original + {len(mirror_aux)} mirror (0.5) "
            f"= {len(train_aux)} train, {len(test_aux)} test days"
        )
    else:
        logger.info(
            f"TFT aux computed: {len(train_aux)} train, {len(test_aux)} test days"
        )

    return train_aux, test_aux


def _generate_sample_data(n_days: int = 60, bars_per_day: int = 405) -> pd.DataFrame:
    """샘플 데이터 생성 (ClickHouse 미연결 시)"""
    np.random.seed(42)
    rows = []
    base_price = 350.0

    for day in range(n_days):
        price = base_price
        for bar in range(bars_per_day):
            dt = pd.Timestamp(f"2025-{1 + day // 22:02d}-{1 + day % 22:02d} "
                              f"{9 + bar // 60:02d}:{bar % 60:02d}:00")
            change = np.random.normal(0, 0.1)
            price += change
            high = price + abs(np.random.normal(0, 0.05))
            low = price - abs(np.random.normal(0, 0.05))
            volume = int(np.random.exponential(100))
            rows.append({
                "datetime": dt,
                "open": price - change * 0.5,
                "high": high,
                "low": low,
                "close": price,
                "volume": volume,
            })

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="RL 모델 학습")
    parser.add_argument(
        "--algo",
        type=str,
        default="mppo",
        choices=["mppo", "dqn", "a2c", "ppo", "all"],
        help="학습 알고리즘",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="ml/rl_mppo.yaml",
        help="설정 파일 경로",
    )
    parser.add_argument(
        "--slippage-analysis",
        action="store_true",
        help="슬리피지 분석 실행",
    )
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="슬리피지별 재학습 (표3)",
    )
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="평가만 실행 (학습 건너뛰기)",
    )
    parser.add_argument(
        "--save-scaler-only",
        action="store_true",
        help="Scaler만 저장 (학습/평가 건너뛰기)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 데이터 로드 (학습 시에만 scaler 저장)
    persist_scaler = bool(args.save_scaler_only or not args.evaluate_only)
    train_days, train_prices, test_days, test_prices = load_data_from_clickhouse(
        args.config,
        persist_scaler=persist_scaler,
    )

    if args.save_scaler_only:
        logger.info("Scaler saved. Exiting (--save-scaler-only).")
        return

    # TFT 보조 피처 사전 계산 (tft_aux.enabled=true인 경우)
    train_aux, test_aux = precompute_tft_aux(args.config)

    if not args.evaluate_only:
        from shared.ml.rl.trainer import RLTrainer

        trainer = RLTrainer(config_path=args.config)

        if args.algo == "all":
            models = trainer.train_all(
                train_days=train_days,
                train_prices=train_prices,
                eval_days=test_days,
                eval_prices=test_prices,
            )
        else:
            model = trainer.train(
                algo=args.algo,
                train_days=train_days,
                train_prices=train_prices,
                eval_days=test_days,
                eval_prices=test_prices,
                train_aux=train_aux,
                eval_aux=test_aux,
            )
            models = {args.algo: model}

        # 모델 비교 평가 (표1)
        from shared.ml.rl.evaluator import RLEvaluator
        from shared.ml.rl.baselines import MACrossBaseline

        evaluator = RLEvaluator(config_path=args.config)

        # MA-CROSS 베이스라인 추가
        baseline = MACrossBaseline(config_path=args.config)
        baseline_result = baseline.evaluate(test_days, test_prices)
        logger.info(f"MA-CROSS baseline: {baseline_result}")

        # 모델 비교
        if len(models) > 1:
            evaluator.compare_models(models, test_days, test_prices)

        # 슬리피지 분석
        if args.slippage_analysis and args.algo != "all":
            model = models.get(args.algo)
            if model:
                evaluator.slippage_analysis(
                    model, test_days, test_prices, retrain=False
                )
                if args.retrain:
                    evaluator.slippage_analysis(
                        model,
                        test_days,
                        test_prices,
                        retrain=True,
                        trainer=trainer,
                        train_days=train_days,
                        train_prices=train_prices,
                    )

    logger.info("Done.")


if __name__ == "__main__":
    main()
