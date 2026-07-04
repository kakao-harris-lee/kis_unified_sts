# Theme Leader Universe Design

## Goal

Improve the paper stock pipeline's entry timeliness by adding a theme-leader
screening layer that promotes fast-moving, catalyst-backed Korean equity themes
into the existing `system:trade_targets:latest` path without enabling live stock
orders.

## Scope

This design is paper-only. It does not add a live KIS stock order adapter and it
does not change the stock order router's broker mode. The deliverable is a
data-flow improvement:

```text
KIS ranking/news/LLM/disclosure-derived signals
  -> theme leader candidates
  -> fusion_ranker
  -> system:trade_targets:latest
  -> market-ingest WebSocket subscriptions
  -> stock_strategy candidate signals
  -> stock_risk_filter
  -> stock_order_router paper fills
  -> stock_monitor/dashboard
```

## Current Fit

The repository already has most of the required skeleton:

- `services/screener.py` publishes `system:universe:latest`.
- `services/fusion_ranker.py` publishes `system:trade_targets:latest`.
- `services/market_ingest/main.py` subscribes stocks from trade targets and
  daily watchlist, then publishes ticks to `market:ticks`.
- `services/stock_strategy/main.py` and `services/stock_strategy/universe.py`
  merge daily watchlist and trade targets for strategy evaluation.
- `services/stock_monitor/daemon.py` republishes final signals/fills into
  dashboard-native `trading:stock:*` keys.
- `services/dashboard/routes/coverage.py` already exposes coverage diagnostics
  for universe, trade targets, and daily indicators.

The main weakness is not missing infrastructure. The weakness is ranking and
admission: fast theme/news candidates are not first-class inputs, LLM-only
admission is disabled by default, and the 40-symbol WebSocket cap can retain a
different set in ingest than in strategy.

## Theme Candidate Model

Add a small shared contract for theme candidates. It should be plain Python data
and JSON-friendly. A candidate has:

- `code`, `name`, `theme_id`, `theme_label`
- `rank_in_theme`, `theme_score`, `leader_score`
- evidence fields: `keywords`, `source_hits`, `reason`
- signal fields: `relative_strength`, `trading_value_score`,
  `volume_surge_score`, `intraday_persistence`, `catalyst_score`,
  `freshness_score`
- risk fields: `risk_flags`, `state` (`watch`, `active`, `quarantine`)
- TTL metadata: `generated_at`, `ttl_seconds`

The shared scorer should be deterministic and conservative:

```text
leader_score =
  0.25 * relative_strength
+ 0.20 * trading_value_score
+ 0.15 * volume_surge_score
+ 0.15 * catalyst_score
+ 0.10 * theme_breadth_score
+ 0.10 * intraday_persistence
+ 0.05 * freshness_score
- risk_penalty
```

Promotion rule for `active`:

- `leader_score >= 0.70`
- no hard risk flag
- at least one market signal and one catalyst/theme signal

`watch` candidates are published for observability but do not need to enter the
top `trade_targets` set unless fusion score is high enough. `quarantine`
candidates are visible but must not be admitted to trade targets.

## Theme Discovery Service

Add `services/theme_discovery.py` as a read-only producer. It should:

1. Load `system:universe:latest` from screener.
2. Optionally load scored news / LLM metadata if present.
3. Assign theme labels from config keyword maps and existing screener metadata.
4. Score candidates through the shared scorer.
5. Publish:
   - `system:themes:latest`
   - `system:theme_targets:latest`
   - stream `system:theme_targets`

This service should fail open: malformed optional inputs produce fewer theme
signals, not daemon failure. Redis writes must use DB1 via existing client
helpers and TTLs must be configured.

## Fusion Integration

Extend `FusionRanker` so theme targets become an explicit input beside realtime
screener and LLM quality.

New config:

```yaml
redis_keys:
  theme_targets: "${THEME_TARGETS_LATEST_KEY:system:theme_targets:latest}"

weights:
  theme: 0.20

theme:
  enabled: true
  active_state_bonus: 0.08
  quarantine_penalty: 1.0
```

The payload published to `system:trade_targets:latest` must preserve theme
metadata under each symbol so downstream strategy, monitor, and dashboard can
show the entry reason.

## Universe Cap Alignment

Create one shared helper for choosing the stock subscription/evaluation
universe. Both market ingest and stock strategy must use the same priority
order:

1. active theme/fusion trade targets
2. remaining trade targets
3. daily watchlist symbols
4. stable existing symbols, if caller provides them

This prevents a crowded theme burst from putting one top-40 set on WebSocket and
a different top-40 set in strategy evaluation.

## Dashboard / Observability

Extend coverage diagnostics to include theme targets:

- source name: `theme_targets`
- Redis key: `system:theme_targets:latest`
- symbol count, freshness, missing daily indicator symbols
- metadata keys including `themes`, `state_counts`, and source key names

The first implementation can be API-only. Existing Workbench `/coverage` can
show the new source if it renders sources generically; a dedicated visual panel
is a follow-up if the current UI hides relevant metadata.

## Testing

Use narrow unit tests first:

- scorer promotion/quarantine behavior
- theme discovery payload shape and TTL behavior
- fusion ranker theme score contribution and metadata preservation
- shared stock universe cap order
- dashboard coverage extraction for theme targets

Then run targeted integration tests:

- stock universe parsing tests
- fusion ranker tests
- market ingest tests
- stock strategy daemon tests
- dashboard coverage tests

Finally run the broader paper-flow gate already used in this repo when touching
stream contracts.

## Non-Goals

- No live stock order adapter.
- No external paid data provider integration in phase 1.
- No broad UI redesign.
- No replacement of current screener/fusion pipeline.
