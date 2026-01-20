# Futures ML Models Directory

이 디렉토리에는 선물 거래용 CNN-LSTM 모델이 저장됩니다.

## 파일 구조

```
models/futures/
├── trading_lstm.pth      # 단일 모델 가중치
├── trading_lstm.json     # 모델 메타데이터
├── scaler.json           # StandardScaler 파라미터
└── ensemble/             # Multi-horizon 앙상블 모델
    ├── model_h1.pth / model_h1.json
    ├── model_h3.pth / model_h3.json
    ├── model_h5.pth / model_h5.json
    └── model_h10.pth / model_h10.json
```

## 모델 학습

```bash
# 단일 모델 학습
python scripts/training/train_futures_lstm.py --days 30 --epochs 100

# 앙상블 모델 학습
python scripts/training/train_futures_lstm.py --ensemble --horizons 1,3,5,10
```

## 모델 메타데이터 예시 (trading_lstm.json)

```json
{
  "model_type": "cnn-lstm",
  "input_dim": 10,
  "hidden_dim": 64,
  "num_layers": 2,
  "num_classes": 3,
  "dropout": 0.2,
  "cnn_channels": [32, 64],
  "kernel_size": 3,
  "seq_len": 60,
  "version": "1.0.0",
  "feature_columns": [
    "returns", "ma_ratio_5", "ma_ratio_10", "ma_ratio_20",
    "rsi", "bb_position", "volume_ratio", "volatility",
    "hl_range", "candle_body"
  ]
}
```

## Cron 설정 (주간 재학습)

```bash
# 매주 일요일 새벽 2시
0 2 * * 0 cd /path/to/kis_unified_sts && python scripts/training/train_futures_lstm.py --days 30 --epochs 100 >> /var/log/lstm_train.log 2>&1
```
