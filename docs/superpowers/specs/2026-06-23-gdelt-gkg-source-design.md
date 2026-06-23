# GDELT News Source → GKG File Fetch — Design Spec

**Status:** Draft for review
**Date:** 2026-06-23
**Branch:** `feat/gdelt-gkg-source`

## Goal

Restore GDELT global event/headline coverage in the news collector by rewriting
`GDELTNewsSource` from the DOC 2.0 API (now permanently HTTP-429 blocked from
this host's IP) to the GDELT GKG file feed on `data.gdeltproject.org` (reachable,
HTTP 200) — using direct CSV fetch with no new dependencies.

## Problem

`shared/news/sources/gdelt.py` calls `https://api.gdeltproject.org/api/v2/doc/doc`.
Diagnosis (2026-06-23): that endpoint returns **HTTP 429 on every request from
this IP** — confirmed with isolated single calls after a 10s wait, simpler/smaller
queries, and varied User-Agents (all 429, body "Please limit requests to one
every 5 seconds…"). It is an IP-level block, not a cadence/query/UA issue, so it
cannot be fixed by config. The collector logs `gdelt rate limited` every poll and
ingests zero GDELT articles. The GKG file server `data.gdeltproject.org` IS
reachable from this IP (lastupdate.txt → HTTP 200). Host IP 222.236.x is a Korean
ISP (not a cloud range).

## Design — direct GKG CSV fetch (no gdeltPyR/pandas)

All `aiohttp` + Python stdlib (`zipfile`, `io`, `csv`, `re`). No new deps.

```
GDELTNewsSource.fetch()  (each poll):
 1. aiohttp GET  {gkg_base_url}/lastupdate.txt        (small text, 200)
 2. parse → newest line ending in ".gkg.csv.zip" → URL + 15-min slice timestamp
 3. if slice timestamp == last processed → return (skip; no re-ingest)
 4. aiohttp GET the .gkg.csv.zip (bounded; timeout + max-bytes guard)
 5. in a thread executor: zipfile → read the single .csv → parse TSV rows
 6. filter rows whose PAGE_TITLE or V2Themes contains any match_keyword (ci)
 7. map up to max_records matching rows → NewsItem, yield
 8. record this slice timestamp as last processed
```

### GKG 2.1 column → NewsItem mapping
GKG 2.1 is tab-delimited (~27 cols). Used columns (0-indexed; implementer MUST
verify the GKG 2.1 column order against a live file header during implementation):
- DATE (col 1, `YYYYMMDDHHMMSS`, UTC) → `published_at_ms` (epoch ms)
- SourceCommonName (col 3) → `domain` (→ keywords + body)
- DocumentIdentifier (col 4) → `url`
- V2EnhancedThemes (col 8) → keyword matching + (optionally) keywords
- V1.5Tone (col 15, first comma value) → optional body summary
- V2EXTRASXML (col 26) → `<PAGE_TITLE>…</PAGE_TITLE>` (regex) → `title`

Mapping rules (preserve the current source's contract):
- `title` from PAGE_TITLE; **if absent → skip the record** (current source skips
  items lacking title/url — keep that invariant).
- `url` required; skip if empty.
- `news_id` = `gdelt_<sha256(url)[:16]>` (UNCHANGED → downstream dedup compatible).
- `source` = `"gdelt"`, `source_version` = `"gdelt-gkg-v1"` (bumped).
- `body` = title + `domain=<d>` + optional `tone=<t>` (mirrors current join style).
- `lang` = from GKG TranslationInfo (col 25) if present, else `"unknown"`.
- `keywords` = `["gdelt", domain]` + the matched keyword(s).
- `published_at_ms` = DATE→epoch-ms; if unparseable → received time.

### Filtering (replicates the old DOC `query`)
The DOC API queried server-side; GKG files are the unfiltered global firehose, so
filter locally. Match a row if any `match_keyword` (case-insensitive substring)
appears in the PAGE_TITLE or V2Themes. Default `match_keywords`:
`["federal reserve", "bond yields", "equity market", "semiconductor"]`
(derived from the old OR query). Cap output at `max_records`.

## Components / file changes
- **Rewrite** `shared/news/sources/gdelt.py`: replace the DOC-API `fetch()` body
  with the GKG pipeline. Keep the class name `GDELTNewsSource`, `name="gdelt"`,
  `fetch() -> AsyncIterator[NewsItem]`, and constructor `session=`-injected. Add
  small helpers: `_parse_lastupdate(text) -> (url, slice_ts)`,
  `_extract_page_title(extras) -> str|None`, `_parse_gkg_rows(csv_text) ->
  iterable[NewsItem-fields]`. Keep `_parse_gdelt_date`-style UTC→epoch helper.
- **Modify** `shared/news/config.py` `GDELTSourceConfig`: drop `query`/`timespan`/
  `sort` (DOC-only); add `gkg_base_url: str = "http://data.gdeltproject.org/gdeltv2"`
  and `match_keywords: list[str] = [<defaults>]`. Keep `enabled`,
  `poll_interval_seconds`, `max_records`, `timeout_seconds`.
- **Modify** `config/news_sources.yaml` gdelt block: replace query/timespan/sort
  with `gkg_base_url` + `match_keywords`; keep enabled/poll/max_records/timeout.
- **Modify** `services/news_collector/main.py` GDELTNewsSource instantiation to
  pass the new config fields (drop query/timespan/sort, add gkg_base_url/
  match_keywords).

## Error handling / safety
- Best-effort (mirrors current): lastupdate fetch / download / unzip / parse
  failure → `logger.warning(...)` + yield nothing (return). No raise.
- Bounded: only the newest 15-min slice per poll; `max_records` cap; aiohttp
  `timeout`; a max-download-bytes guard on the zip (reject absurd sizes); skip if
  the slice timestamp is unchanged since the last poll (avoid re-parsing).
- Parse runs in a thread executor (`asyncio.to_thread`) so the CSV decode never
  blocks the event loop.
- DOC API 429 is gone (data server returns 200). KST/UTC: GKG DATE is UTC →
  epoch-ms (tz-agnostic). No new deps (stdlib only).

## Testing
- `_parse_lastupdate`: real-format text → correct newest .gkg.csv.zip URL + ts;
  malformed → None/empty (no crash).
- `_extract_page_title`: Extras with/without `<PAGE_TITLE>` → title/None.
- GKG row parse+filter+map: a small TSV fixture with (a) a row with PAGE_TITLE +
  matching keyword → NewsItem with correct url/title/domain/published_at_ms/
  news_id, (b) a row without PAGE_TITLE → skipped, (c) a row not matching any
  keyword → skipped, (d) max_records cap honored.
- Error path: aiohttp download raises → `fetch()` yields nothing, no exception.
- HTTP mocked (aiohttp); zip from an in-memory `zipfile` fixture. No network.

## Scope / out of scope
- **In:** rewrite the gdelt source backend + its config + tests. No new deps.
- **Out:** other news sources; the news→forecast pipeline (unchanged — gdelt just
  resumes feeding `news:raw`); switching to gdeltPyR library (rejected — direct
  CSV is lighter and dependency-free).
- **Rollout:** config bind-mounted `:ro` → after merge, `news-collector` restart
  picks up the new source (no rebuild needed for config; code change needs the
  image rebuilt). Set `gdelt.enabled: true`. Observe `news:raw`/`stream:news.raw`
  for gdelt-sourced entries + absence of the `gdelt rate limited` warning.
