# Opening Volume Surge — prev_day_volume 데이터 파이프라인

## Problem

`opening_volume_surge` 전략은 `prev_day_volume`(전일 거래량)이 필수 트리거인데,
멀티전략 오케스트레이터 경로에서는 이 데이터가 주입되지 않아 진입 시그널이 100% 스킵됨.

KIS API에는 전일 거래량 필드가 없으며, 유일한 소스는 pykrx.

## Solution

Screener startup 시 pykrx로 전일 거래량을 1회 조회하여 캐시 → Redis metadata에 포함
→ Fusion Ranker가 merge → 오케스트레이터의 기존 파이프라인으로 전달.

## Changes

### 1. `shared/collector/prev_day_volume.py` (신규)
- pykrx `get_market_ohlcv_by_ticker()` 래퍼
- `fetch_prev_day_volumes(codes, date)` → `{code: volume}` dict
- Lazy 조회 지원 (캐시 miss 시 개별 종목 조회)

### 2. `services/screener.py`
- Startup 시 `_prev_day_volumes` 캐시 초기화 (pykrx 1회 호출)
- 매 스캔 주기: 신규 종목은 lazy 조회
- Redis publish payload에 `metadata` dict 추가: `{code: {"prev_day_volume": N}}`

### 3. `services/fusion_ranker.py`
- Screener payload의 `metadata`를 읽어서 자체 metadata에 merge
- `prev_day_volume` 등 screener-origin 필드가 fusion output에 포함

### 4. 오케스트레이터
- **변경 없음** — 기존 `_load_ranked_targets()` → `symbol_metadata_cache` → `enriched.update(meta)` 파이프라인 그대로 사용

### 5. 테스트
- `shared/collector/prev_day_volume.py` 유닛 테스트
- Screener metadata 포함 확인
- Fusion Ranker merge 확인
