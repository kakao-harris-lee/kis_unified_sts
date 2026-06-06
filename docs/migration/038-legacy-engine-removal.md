# Legacy RL Paper Trading Engine 제거 (2026-03-08)

## 📋 요약

선물 RL paper trading의 레거시 엔진(`shared/ml/rl/paper_trader.py`)과 `--engine legacy` CLI 플래그를 제거하였습니다. 모든 RL paper trading은 이제 `TradingOrchestrator` 경로를 통해 실행됩니다.

---

## ❌ 제거된 항목

| 항목 | 경로 | 설명 |
|------|------|------|
| 레거시 엔진 파일 | `shared/ml/rl/paper_trader.py` | 949줄의 독립 실행형 RL paper trading 엔진 |
| CLI 플래그 | `--engine legacy/orchestrator` | `sts rl paper` 명령의 엔진 선택 옵션 |
| 모듈 export | `shared/ml/rl/__init__.py` | `RLPaperTrader`, `run_paper_trader` export |

**제거 이유:**
- 중복 유지보수 부담 (790+ 파일 코드베이스)
- `TradingOrchestrator`가 이미 표준 경로로 문서화됨
- 개발자 혼란 방지 (단일 실행 경로로 통일)

---

## ✅ 마이그레이션 가이드

### 명령어 변경사항

#### Before (2026-03-08 이전)

```bash
# 레거시 엔진 (제거됨)
sts rl paper --engine legacy

# Orchestrator 엔진 (기본값이었음)
sts rl paper --engine orchestrator

# --engine 생략 시 orchestrator 사용
sts rl paper
```

#### After (2026-03-08 이후)

```bash
# 단일 실행 경로 (항상 TradingOrchestrator 사용)
sts rl paper

# 기존 옵션들은 모두 그대로 사용 가능
sts rl paper --model mppo_best
sts rl paper --strategy rl_mppo
sts rl paper --no-daemon
sts rl paper --symbol A05603
```

**변경 필요 사항:**
- `--engine` 플래그를 사용한 명령어 → 해당 플래그 제거
- 코드에서 `paper_trader.py` import → 제거 또는 `TradingOrchestrator` 사용

---

## 🔄 마이그레이션 매핑

| 레거시 경로 | 새 경로 | 변경 사항 |
|-------------|---------|-----------|
| `from shared.ml.rl import RLPaperTrader` | `from services.trading import TradingOrchestrator` | 모듈 변경 |
| `from shared.ml.rl import run_paper_trader` | CLI 명령어 사용 | 함수 대신 CLI 사용 권장 |
| `sts rl paper --engine legacy` | `sts rl paper` | `--engine` 플래그 제거 |
| `sts rl paper --engine orchestrator` | `sts rl paper` | `--engine` 플래그 제거 |

---

## 📊 동작 차이점

### 기대되는 차이점: **없음**

`TradingOrchestrator`는 이미 기본 경로였으며, 레거시 엔진과 동일한 기능을 제공합니다:

| 기능 | 레거시 엔진 | TradingOrchestrator | 비고 |
|------|-------------|---------------------|------|
| RL 모델 추론 | ✅ | ✅ | 동일 |
| WebSocket 실시간 데이터 | ✅ | ✅ | 동일 |
| Redis 포지션 추적 | ✅ | ✅ | 동일 |
| Parquet 지표 워밍업 | ❌ | ✅ | 개선됨 |
| IndicatorEngine 통합 | 부분적 | ✅ | 개선됨 |
| 재시작 시 복구 | ✅ | ✅ | 동일 |
| Telegram 알림 | ✅ | ✅ | 동일 |
| Hard stop / EOD 안전장치 | ✅ | ✅ | 동일 |

**개선된 점:**
- **Pre-market Parquet warmup**: 장 시작 전 Parquet market data에서 지표 사전 로드로 초기 레이턴시 감소
- **IndicatorEngine 완전 통합**: VWAP, RVOL, volume 가속도 등 추가 지표 지원
- **단일 코드베이스**: 유지보수 부담 감소, 버그 수정 시 일관성 보장

---

## 🧪 검증 체크리스트

마이그레이션 후 다음을 확인하세요:

- [ ] `sts rl paper` 명령 실행 성공 (--engine 플래그 없이)
- [ ] `sts rl paper --help`에 `--engine` 옵션이 표시되지 않음
- [ ] 기존 모델 파일 경로 정상 작동 (`RL_MPPO_MODEL_PATH` 환경변수)
- [ ] Redis 포지션 복구 정상 작동 (프로세스 재시작 테스트)
- [ ] Telegram 알림 정상 수신
- [ ] Parquet 지표 데이터 조회 정상

---

## ⚠️ 주의사항

### 1. 환경변수 및 설정 파일

기존 환경변수 및 설정은 **모두 그대로 사용 가능**합니다:

```bash
# 그대로 사용 가능
export RL_MPPO_MODEL_PATH=/path/to/model
export KIS_FUTURES_APP_KEY=...
export KIS_FUTURES_APP_SECRET=...
export REDIS_HOST=localhost
```

### 2. 코드 Import 변경

레거시 엔진을 직접 import한 코드가 있다면 수정 필요:

```python
# ❌ 제거됨 - ImportError 발생
from shared.ml.rl import RLPaperTrader, run_paper_trader

# ✅ 권장 - CLI 명령어 사용
import subprocess
subprocess.run(["sts", "rl", "paper"])

# ✅ 또는 TradingOrchestrator 직접 사용
from services.trading import TradingOrchestrator
orchestrator = TradingOrchestrator(asset_class="futures", strategy_name="rl_mppo")
orchestrator.start()
```

### 3. Cron 작업 업데이트

Cron에서 `--engine` 플래그를 사용했다면 제거 필요:

```bash
# Before
0 9 * * 1-5 cd /path/to/project && sts rl paper --engine orchestrator

# After
0 9 * * 1-5 cd /path/to/project && sts rl paper
```

---

## 🔗 관련 문서

- [CLAUDE.md - RL 선물 운용 규칙](../../CLAUDE.md#rl-선물-운용-규칙)
- [TradingOrchestrator 구현](../../services/trading/orchestrator.py)
- [RL MPPO 전략 설정](../../config/strategies/futures/rl_mppo.yaml)

---

## 📝 롤백 안내

만약 문제가 발생하여 레거시 엔진으로 롤백이 필요한 경우:

```bash
# 이 커밋 이전으로 되돌리기
git revert <commit-hash-of-038>

# 또는 특정 커밋 체크아웃
git checkout <commit-before-038> -- shared/ml/rl/paper_trader.py
git checkout <commit-before-038> -- shared/ml/rl/__init__.py
git checkout <commit-before-038> -- cli/main.py
```

**롤백이 필요한 경우 즉시 이슈를 등록해주세요.**

---

## 🎯 기대 효과

1. **코드베이스 단순화**: 949줄 제거 + 중복 로직 제거
2. **유지보수 부담 감소**: 단일 실행 경로로 버그 수정 및 기능 추가 용이
3. **개발자 경험 개선**: 명확한 단일 경로로 혼란 방지
4. **테스트 부담 감소**: 하나의 경로만 테스트하면 됨

---

**마이그레이션 완료일**: 2026-03-08
**영향받는 컴포넌트**: RL Paper Trading (Futures)
**하위 호환성**: 기존 명령어 `sts rl paper` 그대로 작동 (--engine 플래그만 제거됨)
