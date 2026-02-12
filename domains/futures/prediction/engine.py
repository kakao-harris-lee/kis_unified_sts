"""Prediction Engine

선물 전용 딥러닝 추론 엔진.
FEATURE_STREAM → PREDICTION_STREAM

Usage:
    engine = PredictionEngine()
    engine.start()
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from domains.futures.prediction.features import FeatureCalculator
from shared.ml import ModelLoader
from shared.streaming import StreamConsumer, StreamMessage, StreamPublisher
from shared.streaming.client import RedisClient

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """예측 결과"""

    symbol: str
    timestamp: float
    up_prob: float
    down_prob: float
    hold_prob: float
    model_version: str
    inference_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "up_prob": self.up_prob,
            "down_prob": self.down_prob,
            "hold_prob": self.hold_prob,
            "model_version": self.model_version,
            "inference_time_ms": self.inference_time_ms,
        }


class PredictionEngine(StreamConsumer):
    """Prediction Engine

    FEATURE_STREAM에서 피처를 읽어 CNN-LSTM 모델로 추론 후
    PREDICTION_STREAM에 결과 발행.

    Usage:
        engine = PredictionEngine()
        engine.start()
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        feature_stream: str | None = None,
        prediction_stream: str | None = None,
        lookback_window: int = 60,
        device: str = "auto",
    ):
        """
        Args:
            model_path: 모델 경로 (기본: models/futures/trading_lstm.pth)
            feature_stream: 피처 스트림 이름 (기본: FEATURE_STREAM)
            prediction_stream: 예측 스트림 이름 (기본: PREDICTION_STREAM)
            lookback_window: 시퀀스 길이 (기본: 60)
            device: 추론 디바이스
        """
        # 환경 변수에서 설정 로드
        feature_stream = feature_stream or os.environ.get(
            "REDIS_FEATURE_STREAM", "FEATURE_STREAM"
        )
        prediction_stream = prediction_stream or os.environ.get(
            "REDIS_PREDICTION_STREAM", "PREDICTION_STREAM"
        )
        group_name = os.environ.get("PREDICTION_GROUP", "prediction_group")

        super().__init__(
            stream_name=feature_stream,
            group_name=group_name,
            consumer_name="prediction_1",
            component_name="prediction_engine",
        )

        # 모델 로더
        model_path = model_path or Path("models/futures/trading_lstm.pth")
        self.model_loader = ModelLoader(model_path, device=device)
        self.model_version = os.environ.get("MODEL_VERSION", "1.0.0")

        # Publisher
        self.publisher = StreamPublisher(prediction_stream)

        # Redis 클라이언트 (피처 윈도우 조회용)
        self.redis = RedisClient.get_client()

        # 설정
        self.lookback = lookback_window
        self.feature_calculator = FeatureCalculator()

        # 통계
        self._inference_count = 0
        self._total_inference_time = 0.0

    def start(self) -> None:
        """Prediction Engine 시작"""
        # 모델 로드
        self.model_loader.load()
        logger.info(
            f"PredictionEngine started with model: {self.model_loader.model_path}"
        )

        # Consumer 루프 시작
        self.run()

    def _get_feature_window(self, symbol: str) -> Optional[list[dict]]:
        """Redis에서 Feature Rolling Window 조회"""
        key = f"feature_window:{symbol}"
        try:
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to get feature window: {e}")
        return None

    def _prepare_sequence(self, features: list[dict]) -> Optional[np.ndarray]:
        """피처 리스트를 모델 입력용 시퀀스로 변환"""
        return self.feature_calculator.prepare_sequence(features, self.lookback)

    def process_message(self, message: StreamMessage) -> bool:
        """피처 메시지 처리 및 예측 실행"""
        try:
            data = message.data
            symbol = data.get("symbol")

            if not symbol:
                return True

            # 1. Feature Window 조회
            features = self._get_feature_window(symbol)
            if not features:
                return True  # 데이터 부족, 스킵

            # 2. 시퀀스 준비
            sequence = self._prepare_sequence(features)
            if sequence is None:
                return True  # 데이터 부족, 스킵

            # 3. 추론 실행
            start_time = time.time()
            probs = self.model_loader.predict(sequence)
            inference_time_ms = (time.time() - start_time) * 1000

            if probs is None:
                return True

            # 4. 결과 구성
            result = PredictionResult(
                symbol=symbol,
                timestamp=time.time(),
                hold_prob=float(probs[0]),
                up_prob=float(probs[1]),
                down_prob=float(probs[2]),
                model_version=self.model_version,
                inference_time_ms=inference_time_ms,
            )

            # 5. PREDICTION_STREAM에 발행
            self.publisher.publish(result.to_dict(), parent_message=message)

            logger.debug(
                f"Prediction: {symbol} Up={result.up_prob:.2f} "
                f"Down={result.down_prob:.2f} ({inference_time_ms:.1f}ms)"
            )

            # 통계 업데이트
            self._inference_count += 1
            self._total_inference_time += inference_time_ms

            if self._inference_count % 100 == 0:
                avg_time = self._total_inference_time / self._inference_count
                logger.info(
                    f"Predictions: {self._inference_count}, "
                    f"Avg inference: {avg_time:.2f}ms"
                )

            return True

        except Exception as e:
            logger.error(f"Error in prediction: {e}", exc_info=True)
            return False

    def get_stats(self) -> dict[str, Any]:
        """통계 조회"""
        avg_time = (
            self._total_inference_time / self._inference_count
            if self._inference_count > 0
            else 0.0
        )
        return {
            "inference_count": self._inference_count,
            "avg_inference_time_ms": avg_time,
            "model_version": self.model_version,
            "lookback_window": self.lookback,
        }


def main():
    """Prediction Engine 실행"""
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting Prediction Engine...")
    engine = PredictionEngine()

    try:
        engine.start()
    except KeyboardInterrupt:
        engine.stop()


if __name__ == "__main__":
    main()
