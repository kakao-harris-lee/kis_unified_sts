# Setup C Event-Score Observation

Use this read-only check to decide whether Setup C has enough fresh scored-event
history for activation review. It observes the same payload shape published by
`ForecastPublisher` to `forecast:event:latest` and the bounded Redis list
`forecast:event:history`.

## Offline Check

Use an offline JSON fixture when Redis is unavailable or when reviewing captured
evidence. The file must contain a list of `EventScore` JSON objects.

```bash
python scripts/ops/setup_c_event_score_observe.py \
  --history-json /path/to/event-score-history.json \
  --min-history 20 \
  --max-age-minutes 60 \
  --min-impact-score 60 \
  --output-json reports/setup-c-event-score-readiness.json
```

## Redis Check

Runtime observation is read-only. Use Redis DB 1 unless an operator env file
intentionally overrides the URL.

```bash
REDIS_URL=redis://localhost:6379/1 \
python scripts/ops/setup_c_event_score_observe.py \
  --min-history 20 \
  --max-age-minutes 60 \
  --min-impact-score 60 \
  --output-json reports/setup-c-event-score-readiness.json
```

## Report Fields

- `ready`: true only when history length, freshness, and impact-score thresholds
  all pass.
- `count`: valid event-score rows parsed from history.
- `fresh_count`: rows within `--max-age-minutes` of `--asof` or current time.
- `max_age_minutes`: oldest parsed row age.
- `impact_score`: minimum and average observed impact score.
- `tier_distribution`: count by `impact_tier`.
- `missing_evidence`: activation blockers such as
  `event_score_history_empty`, `event_score_stale`, and
  `impact_score_below_minimum`. Placeholder values such as `TODO`, `TBD`,
  `placeholder`, or `replace me` are rejected as
  `placeholder_event_score_evidence`.

Passing this check is observation evidence only. Setup C still needs real
scored-event production running during market-relevant windows before activation.
