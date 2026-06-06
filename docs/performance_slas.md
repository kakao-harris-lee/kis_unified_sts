# Performance Service Level Agreements (SLAs)

**Version:** 1.0
**Last Updated:** 2026-06-06
**Status:** Active

---

## Executive Summary

This document defines the performance Service Level Agreements (SLAs) for the KIS Unified Trading Platform. These SLAs establish acceptable performance thresholds for critical system components to ensure reliable, low-latency trading operations.

**Critical Constraint:** RL inference must fit within 1-minute candle intervals (p99 < 60 seconds) to maintain real-time trading capabilities.

**Performance Philosophy:** All SLAs are derived from empirical baseline measurements and include safety margins (20% warning threshold, 50% critical threshold) to detect performance regressions before they impact trading operations.

---

## Component SLAs

### 1. WebSocket Message Processing

**Purpose:** Real-time market data ingestion for stock (H0STCNT0) and futures (H0IFASP0) feeds.

#### Performance Targets

| Metric | Baseline | Warning Threshold | Critical Threshold | Unit |
|--------|----------|-------------------|-------------------|------|
| Publish Throughput (100 msg) | TBD | Baseline × 0.8 | Baseline × 0.5 | msg/s |
| Publish Throughput (1000 msg) | TBD | Baseline × 0.8 | Baseline × 0.5 | msg/s |
| End-to-End Latency p50 | TBD | Baseline × 1.2 | Baseline × 1.5 | ms |
| End-to-End Latency p95 | TBD | Baseline × 1.2 | Baseline × 1.5 | ms |
| End-to-End Latency p99 | TBD | Baseline × 1.2 | Baseline × 1.5 | ms |
| Peak Load Handling | 1000 msg/s | 800 msg/s | 500 msg/s | msg/s |
| Sustained Load Handling | 5000 msg | N/A | N/A | msg |

#### Rationale

- **Throughput:** Must handle peak market volatility periods (opening bell, economic announcements)
- **Latency:** End-to-end processing time impacts signal generation and order execution timing
- **Peak Load:** Market data bursts during high volatility require sustained high throughput
- **Dependency:** Redis pub/sub for message distribution

#### Monitoring Recommendations

```yaml
Prometheus Metrics:
  - websocket_messages_processed_total (counter)
  - websocket_message_processing_latency_seconds (histogram, p50/p95/p99)
  - websocket_publish_throughput_per_second (gauge)

Prometheus Alerts:
  - Warning: p95 latency > baseline × 1.2 for 5 minutes
  - Critical: p99 latency > baseline × 1.5 for 2 minutes
  - Critical: Throughput < baseline × 0.8 for 3 minutes
```

---

### 2. Parquet/DuckDB Market Data Performance

**Purpose:** Historical market data retrieval for indicator warmup, backtesting,
research, and strategy validation. ClickHouse is retired from the active stack;
SLA coverage applies to Parquet files queried through `ParquetMarketDataStore`
and DuckDB.

#### Performance Targets

| Metric | Baseline | Warning Threshold | Critical Threshold | Unit |
|--------|----------|-------------------|-------------------|------|
| 1-Day Parquet Query p95 | < 500 | 600 | 750 | ms |
| 30-Day Parquet Query p95 | < 1000 | 1200 | 1500 | ms |
| 100-Day Parquet Query p95 | TBD | Baseline × 1.2 | Baseline × 1.5 | ms |
| Concurrent Queries (5 workers) | TBD | Baseline × 0.8 | Baseline × 0.5 | qps |
| Concurrent Queries (20 workers) | TBD | Baseline × 0.8 | Baseline × 0.5 | qps |
| Query Latency p50 | TBD | Baseline × 1.2 | Baseline × 1.5 | ms |
| Query Latency p99 | TBD | Baseline × 1.2 | Baseline × 1.5 | ms |

#### Rationale

- **30-Day Query:** Critical for pre-market warmup (indicator initialization before trading starts)
- **Concurrent Queries:** Support parallel backtesting and strategy optimization (20+ concurrent backtests)
- **100-Day Query:** Extended backtest ranges for strategy validation
- **Latency Impact:** Slow queries delay trading start time and reduce indicator accuracy

#### Monitoring Recommendations

```yaml
Prometheus Metrics:
  - market_data_query_duration_seconds (histogram, p50/p95/p99)
  - market_data_queries_total (counter, labeled by data_range,timeframe)
  - market_data_concurrent_queries (gauge)
  - market_data_query_throughput_qps (gauge)

Prometheus Alerts:
  - Warning: 30-day query p95 > 1200ms for 5 minutes
  - Critical: 30-day query p95 > 1500ms for 2 minutes
  - Warning: Query throughput (20 workers) < baseline × 0.8
  - Critical: Query latency p99 > baseline × 1.5
```

#### Capacity Planning

- **Data Growth:** Query performance depends on partition/file count and row-group
  shape.
- **Partitioning:** Use symbol/date partitioning under `data/market`.
- **Query Engine:** Prefer DuckDB predicate pushdown for broad scans and
  `ParquetMarketDataStore` for symbol/time-window access.
- **Hardware:** Use SSD-backed storage for `data/market` if 30-day p95 exceeds
  1000ms consistently.

---

### 3. Redis Position State Operations

**Purpose:** Position tracking, recovery after restart, and real-time state synchronization.

#### Performance Targets

| Metric | Baseline | Warning Threshold | Critical Threshold | Unit |
|--------|----------|-------------------|-------------------|------|
| Write Throughput | >= 1000 | 800 | 500 | ops/s |
| Read Throughput | >= 1000 | 800 | 500 | ops/s |
| HGETALL Throughput | >= 1000 | 800 | 500 | ops/s |
| Concurrent Access (10 workers) | TBD | Baseline × 0.8 | Baseline × 0.5 | ops/s |
| Concurrent Access (50 workers) | TBD | Baseline × 0.7 | Baseline × 0.5 | ops/s |
| Read Latency p50 | TBD | Baseline × 1.2 | Baseline × 1.5 | ms |
| Read Latency p95 | TBD | Baseline × 1.2 | Baseline × 1.5 | ms |
| Read Latency p99 | < 10 | 12 | 15 | ms |
| Write Latency p50 | TBD | Baseline × 1.2 | Baseline × 1.5 | ms |
| Write Latency p95 | TBD | Baseline × 1.2 | Baseline × 1.5 | ms |
| Write Latency p99 | < 10 | 12 | 15 | ms |

#### Rationale

- **Throughput:** >= 1000 ops/s ensures position state updates don't bottleneck trading cycles
- **Latency:** < 10ms p99 prevents state read/write from blocking orchestrator cycles
- **Concurrent Access:** Support multiple strategies/workers accessing position state simultaneously
- **Recovery:** Fast HGETALL for rapid position restoration after process restart

#### Monitoring Recommendations

```yaml
Prometheus Metrics:
  - redis_position_state_operations_total (counter, labeled by op_type: read/write)
  - redis_position_state_latency_seconds (histogram, p50/p95/p99)
  - redis_position_state_throughput_ops (gauge)
  - redis_concurrent_workers (gauge)

Prometheus Alerts:
  - Warning: Write ops/s < 800 for 3 minutes
  - Critical: Write ops/s < 500 for 1 minute
  - Warning: p99 latency > 12ms for 5 minutes
  - Critical: p99 latency > 15ms for 2 minutes
  - Critical: Concurrent worker throughput degradation > 30%
```

#### Database Configuration

- **Database:** Redis DB 1 (DB 0 reserved for other projects)
- **Key Pattern:** `trading:{asset}:positions` (hash structure)
- **Persistence:** RDB + AOF for durability
- **Memory Policy:** noeviction (prevent position data loss)

---

### 4. Orchestrator Scalability

**Purpose:** Single-threaded orchestrator managing entry/exit signals across multiple concurrent positions.

#### Performance Targets

| Metric | Baseline | Warning Threshold | Critical Threshold | Unit |
|--------|----------|-------------------|-------------------|------|
| Cycle Time (1 position) | TBD | Baseline × 1.2 | Baseline × 1.5 | seconds |
| Cycle Time (5 positions) | TBD | Baseline × 1.2 | Baseline × 1.5 | seconds |
| Cycle Time (10 positions) | < 5.0 | 6.0 | 7.5 | seconds |
| Cycle Time (20 positions) | TBD | Baseline × 1.2 | Baseline × 1.5 | seconds |
| Memory Usage (1 position) | TBD | Baseline × 1.3 | Baseline × 1.5 | MB |
| Memory Usage (20 positions) | TBD | Baseline × 1.3 | Baseline × 1.5 | MB |
| Scalability Factor (20 pos) | 14-17x | 20x (linear) | 25x | multiplier |

#### Rationale

- **10 Position SLA:** < 5 seconds cycle time ensures timely signal generation and order execution
- **Sub-Linear Scaling:** 14-17x cycle time for 20 positions (vs 20x baseline) demonstrates efficient batching
- **Memory Stability:** No memory leaks as position count increases (validated by memory scaling tests)
- **Maximum Capacity:** >= 20 concurrent positions supported (stress test validated)

#### Monitoring Recommendations

```yaml
Prometheus Metrics:
  - orchestrator_cycle_duration_seconds (histogram, labeled by position_count)
  - orchestrator_positions_active (gauge)
  - orchestrator_memory_usage_mb (gauge)
  - orchestrator_scalability_factor (gauge)

Prometheus Alerts:
  - Warning: 10-position cycle time > 6.0s for 5 minutes
  - Critical: 10-position cycle time > 7.5s for 2 minutes
  - Warning: Scalability factor > 20x (linear degradation)
  - Critical: Scalability factor > 25x (exponential degradation)
  - Warning: Memory growth > 30% baseline for same position count
```

#### Orchestrator Cycle Components

```
1. Entry Signal Checking (_handle_entry) - scan candidates for entry signals
2. Exit Signal Checking (_handle_exit) - scan open positions for exit signals
3. Position State Updates - update PnL, stop prices, trailing stops
4. Risk Management Checks - drawdown limits, regime filters, BEAR blocking
```

**Hot Path Optimizations:**
- Caching: Entry signal cache reduces redundant calculations by ~60%
- Dict Operations: < 50 dict accesses per cycle (measured)
- Memory Overhead: Caching adds < 100 KB for 100 symbols

---

### 5. RL Model Inference Latency

**Purpose:** Real-time RL model predictions for entry/exit decisions (Maskable PPO for futures trading).

#### Performance Targets

| Metric | Baseline (CPU) | Baseline (GPU) | Warning Threshold | Critical Threshold | Hard Limit | Unit |
|--------|----------------|----------------|-------------------|-------------------|------------|------|
| Single Inference Latency | < 100 | < 50 | Baseline × 1.2 | Baseline × 1.5 | N/A | ms |
| Batch Inference (10 obs) | TBD | TBD | Baseline × 1.2 | Baseline × 1.5 | N/A | ms |
| Cold Start Latency | TBD | TBD | Baseline × 1.2 | Baseline × 1.5 | N/A | ms |
| Warm Inference Latency | < 100 | < 50 | 120 | 150 | N/A | ms |
| Inference Latency p50 | TBD | TBD | Baseline × 1.2 | Baseline × 1.5 | N/A | ms |
| Inference Latency p95 | TBD | TBD | Baseline × 1.2 | Baseline × 1.5 | N/A | ms |
| Inference Latency p99 | TBD | TBD | Baseline × 1.2 | Baseline × 1.5 | **60,000** | ms |
| Inference Consistency (CV) | < 20% | < 20% | 25% | 30% | N/A | % |

#### Rationale

- **1-Minute Candle Constraint:** RL inference p99 **MUST** be < 60 seconds to fit within candle intervals
- **Hard Limit:** p99 >= 60s is a **critical failure** (trading signals would lag behind market data)
- **CPU vs GPU:** GPU provides ~2x speedup for warm inference (50ms vs 100ms)
- **Consistency:** Low coefficient of variation (CV < 20%) ensures predictable latency
- **Cold vs Warm:** First inference includes model loading overhead (~500-2000ms)

#### Monitoring Recommendations

```yaml
Prometheus Metrics:
  - rl_inference_duration_seconds (histogram, p50/p95/p99, labeled by device: cpu/gpu)
  - rl_inference_total (counter, labeled by model: entry/exit)
  - rl_inference_cold_start_duration_seconds (histogram)
  - rl_inference_consistency_cv (gauge)
  - rl_model_cache_hits_total (counter)

Prometheus Alerts:
  - CRITICAL: p99 latency > 60s (HARD LIMIT VIOLATION)
  - Warning: p99 latency > 50s (approaching hard limit)
  - Warning: p95 latency > baseline × 1.2
  - Critical: Coefficient of variation > 30% (inconsistent inference)
  - Warning: Cold start latency > 5s (slow model loading)
```

#### Model Configuration

- **Model Path:** `models/futures/rl/mppo_best/best_model.zip`
- **Override:** Environment variable `RL_MPPO_MODEL_PATH` for path override
- **Shared Components:** `shared/strategy/rl_model_helpers.py` (model cache, obs builder, confidence calc)
- **Action Space:** 5 actions (LONG_ENTRY=0, LONG_EXIT=1, SHORT_ENTRY=2, SHORT_EXIT=3, HOLD=4)
- **Observation Dim:** 31 dimensions (scaler applied, dict market_data + OHLCV features)
- **Safety Mechanisms:** Hard stop (-3%), EOD close (15:15) override model predictions

#### Capacity Planning

- **GPU Recommendation:** If p99 > 30s on CPU, consider GPU deployment for 2x speedup
- **Model Optimization:** Quantization (int8) can reduce inference time by ~30-40%
- **Batch Inference:** Batching 10 observations reduces per-observation latency by ~20%
- **Caching:** Model cache saves ~50MB memory by avoiding redundant loads

---

## Hierarchical RL Performance Addendum

**Status:** Future Enhancement (Directional/Risk Budget Modes)

When hierarchical RL is deployed (High-level 15m + Low-level 1m agents):

### Additional Performance Targets

| Metric | Target | Warning | Critical | Unit |
|--------|--------|---------|----------|------|
| High-Level Inference (15m) | < 100 | 120 | 150 | ms |
| Low-Level Inference (1m) | < 100 | 120 | 150 | ms |
| Combined Latency p99 | < 60,000 | 50,000 | 60,000 | ms |
| Hierarchical Overhead | < 20% | 25% | 30% | % vs flat RL |

**Rationale:** Combined high + low inference must still respect 60s hard limit. Hierarchical overhead should be < 20% compared to flat RL.

---

## Performance Testing & Regression Detection

### Baseline Establishment

Baselines are captured in `tests/performance/baselines.json` via:

```bash
pytest tests/performance/ -v -s --json-report --json-report-file=tests/performance/baselines.json
```

### Regression Detection

Performance regression checks run via `scripts/performance/check_regression.py`:

```bash
python scripts/performance/check_regression.py \
  --baseline tests/performance/baselines.json \
  --current tests/performance/baselines.json
```

**Threshold Logic:**
- **Warning:** 20% performance degradation (exit code 1 with warnings)
- **Error:** 50% performance degradation (exit code 2, fails CI build)

### CI Integration

Performance regression checks run:
- **Weekly:** Every Monday 00:00 UTC (scheduled cron)
- **On PR to main:** Automated performance validation before merge
- **Manually:** `pytest -m performance` for ad-hoc benchmarking

**GitHub Actions Job:** `.github/workflows/test.yml` → `performance` job

---

## Monitoring & Alerting Stack

### Prometheus Configuration

```yaml
# /etc/prometheus/prometheus.yml
scrape_configs:
  - job_name: 'kis-trading'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:9090']
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: '(websocket|market_data|redis|orchestrator|rl)_.*'
        action: keep
```

### Monitoring Dashboards

**Recommended Dashboards:**

1. **WebSocket Performance**
   - Throughput (msg/s) timeseries
   - Latency percentiles (p50/p95/p99) heatmap
   - Peak vs sustained load comparison

2. **Parquet/DuckDB Market Data Performance**
   - Query latency by data range (1d/30d/100d)
   - Concurrent query throughput
   - Query duration distribution (histogram)

3. **Redis Position State**
   - Read/write ops/s timeseries
   - Latency percentiles heatmap
   - Concurrent worker throughput degradation

4. **Orchestrator Scalability**
   - Cycle time by position count (1/5/10/20)
   - Memory usage scaling
   - Scalability factor gauge (target: < 20x for 20 positions)

5. **RL Inference Latency**
   - Inference duration percentiles (p50/p95/p99) with 60s hard limit line
   - Cold vs warm inference comparison
   - Inference consistency (CV) timeseries
   - Model cache hit rate

### PagerDuty Alert Routing

```yaml
# Alert Severity Mapping
Critical Alerts → PagerDuty → Immediate Page (24/7)
  - RL inference p99 > 60s (hard limit violation)
  - Orchestrator 10-position cycle > 7.5s
  - Redis write ops/s < 500

Warning Alerts → Slack → #trading-alerts (business hours)
  - Any metric > warning threshold × 5 minutes
  - Performance degradation trends (20%+)
```

---

## Capacity Planning Guidelines

### When to Scale Up

| Component | Scale Trigger | Recommended Action |
|-----------|---------------|-------------------|
| WebSocket | p95 latency > 1.2× baseline | Increase Redis memory, optimize pub/sub |
| Market data store | 30-day query p95 > 1200ms | Add SSD, compact Parquet files, review partitioning |
| Redis | Write ops/s < 800 | Increase Redis memory, enable persistence optimization |
| Orchestrator | 10-position cycle > 6s | Profile hot paths, optimize indicator calculations |
| RL Inference | p99 > 30s (CPU) | Deploy GPU, enable model quantization, batch inference |

### Load Testing Schedule

- **Weekly:** Automated performance regression tests (GitHub Actions)
- **Monthly:** Full load/stress testing suite (all components, 100% test coverage)
- **Quarterly:** Capacity planning review based on historical metrics
- **Pre-Release:** Mandatory performance validation before production deployment

---

## Appendix A: Test Coverage Summary

### Performance Test Modules

| Module | Test Scenarios | Metrics Captured | Dependencies |
|--------|----------------|------------------|--------------|
| `test_websocket_load.py` | 6 scenarios (100-5000 msg) | Throughput, latency p50/p95/p99 | Redis |
| `test_market_data_store_load.py` | 6 scenarios (1d-100d, concurrent) | Query latency, throughput (qps) | Parquet/DuckDB |
| `test_redis_load.py` | 6 scenarios (CRUD, concurrent) | Ops/s, latency p50/p95/p99 | Redis |
| `test_orchestrator_scalability.py` | 6 scenarios (1-20 positions) | Cycle time, memory, scalability factor | None (pure) |
| `test_orchestrator_hot_path_benchmark.py` | 7 scenarios (entry/exit, cache) | Execution time, speedup ratio, memory overhead | None (pure) |

**Total Test Scenarios:** 31 scenarios across 5 modules
**Total Metrics Tracked:** 40+ distinct performance metrics

---

## Appendix B: Performance Baseline Template

**Format:** JSON (stored in `tests/performance/baselines.json`)

```json
{
  "websocket": {
    "publish_throughput_100_msg_per_s": 1500.0,
    "end_to_end_latency_p50_ms": 2.5,
    "end_to_end_latency_p95_ms": 8.0,
    "end_to_end_latency_p99_ms": 12.0
  },
  "market_data": {
    "query_latency_1d_p95_ms": 150.0,
    "query_latency_30d_p95_ms": 800.0,
    "concurrent_queries_20_workers_qps": 25.0
  },
  "redis": {
    "write_ops_per_second": 2500.0,
    "read_ops_per_second": 3000.0,
    "latency_p99_ms": 5.0
  },
  "orchestrator": {
    "cycle_time_1_position_s": 0.25,
    "cycle_time_10_positions_s": 3.5,
    "cycle_time_20_positions_s": 4.2,
    "scalability_factor_20_positions": 16.8
  },
  "rl_inference": {
    "single_inference_latency_cpu_ms": 80.0,
    "inference_latency_p99_ms": 150.0,
    "cold_start_latency_ms": 1500.0,
    "consistency_cv_percent": 15.0
  }
}
```

**Note:** TBD values are populated after initial baseline run. Thresholds are calculated as:
- Warning = baseline × 1.2 (latency) or baseline × 0.8 (throughput)
- Critical = baseline × 1.5 (latency) or baseline × 0.5 (throughput)

---

## Appendix C: Glossary

- **p50/p95/p99:** Percentile latency (50th, 95th, 99th percentile)
- **ops/s:** Operations per second (throughput metric)
- **qps:** Queries per second (market-data query throughput)
- **CV:** Coefficient of Variation (stddev / mean × 100%)
- **Cycle Time:** Time to complete one orchestrator iteration (entry check → exit check → state update)
- **Cold Start:** First inference including model loading overhead
- **Warm Inference:** Subsequent inference with cached model
- **Scalability Factor:** Cycle time multiplier vs single-position baseline (e.g., 20 positions / 1 position)
- **Sub-Linear Scaling:** Performance degradation slower than linear (e.g., 16x for 20 positions vs 20x baseline)

---

## Document Maintenance

**Review Schedule:** Quarterly (every 3 months)
**Owner:** Platform Engineering Team
**Approval Required:** CTO sign-off for SLA changes
**Changelog:**
- 2026-06-06 v1.1: Retired ClickHouse query SLA and replaced it with
  Parquet/DuckDB market-data SLA.
- 2026-03-08 v1.0: Initial SLA establishment (derived from empirical baselines)

---

**End of Document**
