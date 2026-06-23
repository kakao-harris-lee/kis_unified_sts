# GDELT GKG-File Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Rewrite `GDELTNewsSource` from the IP-blocked DOC 2.0 API to the GKG CSV feed on `data.gdeltproject.org`, using direct aiohttp + stdlib (no new deps).

**Architecture:** Each poll: fetch `lastupdate.txt` → newest `*.gkg.csv.zip` URL+slice-ts → (skip if unchanged) → download the zip → parse the GKG 2.1 TSV in a thread executor → filter rows by keyword (PAGE_TITLE/V2Themes) → map to `NewsItem`. Pure parse/map helpers are unit-tested without network; `fetch()` orchestrates I/O.

**Tech Stack:** Python 3.12, asyncio, aiohttp, stdlib (`zipfile`, `io`, `csv`, `re`, `hashlib`), pytest. Spec: `docs/superpowers/specs/2026-06-23-gdelt-gkg-source-design.md`. Branch: `feat/gdelt-gkg-source`.

## Global Constraints
- No new dependencies — stdlib only (no gdeltPyR/pandas).
- Preserve contract: `GDELTNewsSource(name="gdelt").fetch() -> AsyncIterator[NewsItem]`; `news_id = "gdelt_" + sha256(url)[:16]`; skip records lacking url OR title.
- Best-effort: any I/O/parse failure → `logger.warning(...)` + yield nothing; never raise out of `fetch()`.
- Bounded: only the newest 15-min slice per poll; `max_records` cap; aiohttp timeout; max-download-bytes guard; skip if slice-ts unchanged since last poll.
- KST/UTC: GKG DATE is UTC → epoch-ms (tz-agnostic). Config-driven. Parse runs in `asyncio.to_thread`. `.venv/bin/pytest`. Feature branch only.

## File Structure
- `shared/news/sources/gdelt.py` (REWRITE fetch + add pure helpers; keep `_parse_gdelt_date`).
- `shared/news/config.py` `GDELTSourceConfig` (drop query/timespan/sort; add gkg_base_url + match_keywords).
- `config/news_sources.yaml` gdelt block.
- `services/news_collector/main.py` GDELTNewsSource instantiation.
- Tests: `tests/unit/news/sources/test_gdelt.py` (rewrite to GKG fixtures), `tests/unit/news/test_collector_main.py` (instantiation, if it asserts gdelt args).

---

### Task 1: `GDELTSourceConfig` + yaml (DOC params → GKG params)

**Files:**
- Modify: `shared/news/config.py` (`GDELTSourceConfig`)
- Modify: `config/news_sources.yaml` (gdelt block)
- Test: `tests/unit/news/test_config.py` (or the closest existing config test — locate it; else add a focused test)

**Interfaces:**
- Produces: `GDELTSourceConfig` with fields `enabled: bool=False`, `poll_interval_seconds: int=600`, `gkg_base_url: str="http://data.gdeltproject.org/gdeltv2"`, `match_keywords: list[str]=["federal reserve","bond yields","equity market","semiconductor"]`, `max_records: int=20` (gt0, le100), `timeout_seconds: float=20.0`. (Removed: `query`, `timespan`, `sort`.)

- [ ] **Step 1: failing test** — load config, assert gdelt has `gkg_base_url`, `match_keywords` (non-empty list), `max_records`, and NO `query`/`timespan`/`sort` attribute. If a config test file exists for news, extend it; else create `tests/unit/news/test_gdelt_config.py`:
```python
from shared.news.config import GDELTSourceConfig
def test_gdelt_config_gkg_fields():
    c = GDELTSourceConfig()
    assert c.gkg_base_url.endswith("/gdeltv2")
    assert "federal reserve" in [k.lower() for k in c.match_keywords]
    assert c.max_records == 20
    assert not hasattr(c, "query") and not hasattr(c, "timespan") and not hasattr(c, "sort")
```
- [ ] **Step 2: run → FAIL** (`.venv/bin/pytest tests/unit/news/test_gdelt_config.py -v`) — fields/removals not yet present.
- [ ] **Step 3: implement** — edit `GDELTSourceConfig` (read `shared/news/config.py` first):
```python
class GDELTSourceConfig(SourceCommon):
    enabled: bool = False
    poll_interval_seconds: int = Field(default=600, gt=0)
    gkg_base_url: str = "http://data.gdeltproject.org/gdeltv2"
    match_keywords: list[str] = Field(
        default_factory=lambda: [
            "federal reserve", "bond yields", "equity market", "semiconductor",
        ]
    )
    max_records: int = Field(default=20, gt=0, le=100)
    timeout_seconds: float = Field(default=20.0, gt=0)
```
   Update `config/news_sources.yaml` gdelt block: remove `query`/`timespan`/`sort`; add:
```yaml
      gkg_base_url: "http://data.gdeltproject.org/gdeltv2"
      match_keywords:
        - "federal reserve"
        - "bond yields"
        - "equity market"
        - "semiconductor"
```
   (keep `enabled`, `poll_interval_seconds`, `max_records`, `timeout_seconds`.)
- [ ] **Step 4: run → PASS.** Also `.venv/bin/python -c "from shared.news.config import NewsCollectorConfig; NewsCollectorConfig.from_yaml()"` loads without error (verify yaml ↔ model agree; if ServiceConfigBase forbids extras, the removed keys must be gone from yaml).
- [ ] **Step 5: commit** `feat(news-gdelt): GDELTSourceConfig DOC params → gkg_base_url + match_keywords`.

---

### Task 2: Pure GKG helpers (parse + map), TDD with fixtures

**Files:**
- Modify: `shared/news/sources/gdelt.py` (add module-level pure helpers; keep `_parse_gdelt_date`)
- Test: `tests/unit/news/sources/test_gdelt.py` (rewrite)

**Interfaces:**
- Produces (module-level functions in gdelt.py):
  - `_parse_lastupdate(text: str) -> tuple[str | None, str | None]` → `(gkg_zip_url, slice_ts)` from the `.gkg.csv.zip` line; `(None, None)` if absent/malformed.
  - `_extract_page_title(extras: str) -> str | None` → text inside `<PAGE_TITLE>…</PAGE_TITLE>`, else None.
  - `_gkg_rows_to_items(csv_text: str, *, match_keywords: list[str], max_records: int, version: str, now_ms: int) -> list[NewsItem]` → parsed + filtered + mapped NewsItems (≤ max_records).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/news/sources/test_gdelt.py
from shared.news.sources.gdelt import (
    _parse_lastupdate, _extract_page_title, _gkg_rows_to_items,
)

_LASTUPDATE = (
    "201892 abc http://data.gdeltproject.org/gdeltv2/20260623091500.export.CSV.zip\n"
    "88123 def http://data.gdeltproject.org/gdeltv2/20260623091500.mentions.CSV.zip\n"
    "305551 ghi http://data.gdeltproject.org/gdeltv2/20260623091500.gkg.csv.zip\n"
)

def test_parse_lastupdate_picks_gkg():
    url, ts = _parse_lastupdate(_LASTUPDATE)
    assert url == "http://data.gdeltproject.org/gdeltv2/20260623091500.gkg.csv.zip"
    assert ts == "20260623091500"

def test_parse_lastupdate_malformed():
    assert _parse_lastupdate("") == (None, None)
    assert _parse_lastupdate("garbage no zip here") == (None, None)

def test_extract_page_title():
    assert _extract_page_title('<PAGE_TITLE>Fed holds rates</PAGE_TITLE>') == "Fed holds rates"
    assert _extract_page_title("<PAGE_LINKS>x</PAGE_LINKS>") is None
    assert _extract_page_title("") is None

def _row(date="20260623091500", domain="reuters.com",
         url="https://reuters.com/a", themes="ECON_INTEREST_RATE",
         tone="-2.5,1,3,4", title="Federal Reserve holds rates"):
    # GKG 2.1: 27 tab-separated columns; fill only the ones we read.
    cols = [""] * 27
    cols[1] = date; cols[3] = domain; cols[4] = url; cols[8] = themes
    cols[15] = tone; cols[26] = f"<PAGE_TITLE>{title}</PAGE_TITLE>" if title else ""
    return "\t".join(cols)

def test_gkg_rows_map_and_filter():
    rows = "\n".join([
        _row(url="https://r.com/fed", title="Federal Reserve signals cut"),      # matches title
        _row(url="https://r.com/chip", themes="WB_SEMICONDUCTOR", title="Chip demand"),  # matches theme 'semiconductor'? theme has SEMICONDUCTOR
        _row(url="https://r.com/none", themes="SPORTS", title="Local football result"),  # no match → skip
        _row(url="https://r.com/notitle", title=""),                              # no PAGE_TITLE → skip
        _row(url="", title="No url"),                                             # no url → skip
    ])
    items = _gkg_rows_to_items(rows, match_keywords=["federal reserve","semiconductor"],
                               max_records=20, version="gdelt-gkg-v1", now_ms=1782000000000)
    urls = {it.url for it in items}
    assert "https://r.com/fed" in urls
    assert "https://r.com/none" not in urls and "https://r.com/notitle" not in urls
    fed = next(it for it in items if it.url == "https://r.com/fed")
    assert fed.news_id.startswith("gdelt_") and len(fed.news_id) == len("gdelt_") + 16
    assert fed.source == "gdelt" and fed.source_version == "gdelt-gkg-v1"
    assert fed.title == "Federal Reserve signals cut" and fed.domain_in_keywords if False else True
    assert "gdelt" in fed.keywords and "reuters.com" in fed.keywords
    assert fed.published_at_ms == 1782... if False else fed.published_at_ms > 0  # DATE parsed

def test_gkg_rows_respects_max_records():
    rows = "\n".join(_row(url=f"https://r.com/{i}", title=f"Federal Reserve item {i}") for i in range(10))
    items = _gkg_rows_to_items(rows, match_keywords=["federal reserve"], max_records=3,
                              version="v", now_ms=1)
    assert len(items) == 3
```
(Note for implementer: the `if False else True`/`if False else …` placeholders above are to keep the example compilable — replace with the real assertion: `fed.published_at_ms` equals the epoch-ms of `20260623091500` UTC. Compute it via the same `_parse_gdelt_date`.)

- [ ] **Step 2: run → FAIL** (`ImportError` — helpers not defined).
- [ ] **Step 3: implement** the helpers in `shared/news/sources/gdelt.py`:
```python
import csv as _csv
import io as _io
import re as _re

_PAGE_TITLE_RE = _re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", _re.DOTALL)

def _parse_lastupdate(text: str) -> tuple[str | None, str | None]:
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[-1].endswith(".gkg.csv.zip"):
            url = parts[-1]
            fname = url.rsplit("/", 1)[-1]            # 20260623091500.gkg.csv.zip
            ts = fname.split(".", 1)[0]               # 20260623091500
            return url, (ts if ts.isdigit() else None)
    return None, None

def _extract_page_title(extras: str) -> str | None:
    if not extras:
        return None
    m = _PAGE_TITLE_RE.search(extras)
    if not m:
        return None
    title = m.group(1).strip()
    return title or None

# GKG 2.1 column indices (verify against a live file during implementation).
_C_DATE, _C_DOMAIN, _C_URL, _C_THEMES, _C_TONE, _C_EXTRAS = 1, 3, 4, 8, 15, 26

def _gkg_rows_to_items(
    csv_text: str, *, match_keywords: list[str], max_records: int,
    version: str, now_ms: int,
) -> list[NewsItem]:
    kws = [k.lower() for k in match_keywords if k]
    items: list[NewsItem] = []
    reader = _csv.reader(_io.StringIO(csv_text), delimiter="\t")
    for cols in reader:
        if len(cols) <= _C_EXTRAS:
            continue
        url = cols[_C_URL].strip()
        title = _extract_page_title(cols[_C_EXTRAS])
        if not url or not title:
            continue
        themes = cols[_C_THEMES]
        hay = f"{title}\n{themes}".lower()
        if not any(k in hay for k in kws):
            continue
        domain = cols[_C_DOMAIN].strip()
        published_s = _parse_gdelt_date(cols[_C_DATE].strip())
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        body = " ".join(p for p in (title, f"domain={domain}" if domain else "") if p)
        items.append(NewsItem(
            news_id=f"gdelt_{digest}", source="gdelt",
            published_at_ms=int(published_s * 1000) if published_s else now_ms,
            received_at_ms=now_ms, title=title, body=body, url=url,
            source_version=version, lang="unknown",
            keywords=[k for k in ("gdelt", domain) if k],
        ))
        if len(items) >= max_records:
            break
    return items
```
- [ ] **Step 4: run → PASS** (replace the `if False` placeholders with the real published_at_ms assertion first).
- [ ] **Step 5: commit** `feat(news-gdelt): pure GKG parse/title/map helpers`.

---

### Task 3: Rewrite `fetch()` (async GKG pipeline) + constructor + main wiring

**Files:**
- Modify: `shared/news/sources/gdelt.py` (`__init__`, `fetch`, class `version`)
- Modify: `services/news_collector/main.py` (instantiation)
- Test: `tests/unit/news/sources/test_gdelt.py` (async fetch with mocked aiohttp + zip fixture)

**Interfaces:**
- Consumes: helpers from Task 2; `GDELTSourceConfig` fields (Task 1).
- Produces: `GDELTNewsSource(*, session, gkg_base_url, match_keywords, max_records=20, poll_interval_seconds=None, timeout=20.0)`; `version="gdelt-gkg-v1"`; `fetch()` yields NewsItems from the latest GKG slice.

- [ ] **Step 1: Write the failing async test** — mock `session.get` to return (a) lastupdate.txt then (b) a zip bytes containing one `.csv` with matching GKG rows; assert `fetch()` yields the mapped NewsItem; a second `fetch()` with the SAME slice-ts yields nothing (skip). Also: download error → yields nothing (no raise). Build the zip fixture in-memory:
```python
import io, zipfile, pytest
def _zip_bytes(csv_text):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z: z.writestr("20260623091500.gkg.csv", csv_text)
    return buf.getvalue()
```
Follow the existing async-test + aiohttp-mock conventions in the repo's news source tests (read the current test_gdelt.py / test_marketaux.py for the session-mock pattern: a fake context-manager response with `.status`, `.text()`, `.read()`).
- [ ] **Step 2: run → FAIL** (constructor signature / new fetch not present).
- [ ] **Step 3: implement** — rewrite `__init__` + `fetch()` (keep best-effort try/except, executor parse):
```python
class GDELTNewsSource(NewsSource):
    name = "gdelt"
    version = "gdelt-gkg-v1"
    poll_interval_seconds = 600
    _MAX_ZIP_BYTES = 50 * 1024 * 1024

    def __init__(self, *, session, gkg_base_url, match_keywords,
                 max_records=20, poll_interval_seconds=None, timeout=20.0):
        self._session = session
        self._base = gkg_base_url.rstrip("/")
        self._match_keywords = list(match_keywords)
        self._max_records = max(1, min(max_records, 100))
        self._timeout = timeout
        self._last_slice_ts: str | None = None
        self.poll_interval_seconds = poll_interval_seconds or self.poll_interval_seconds

    async def fetch(self):
        import asyncio
        try:
            async with self._session.get(
                f"{self._base}/lastupdate.txt",
                headers={"User-Agent": _USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status != 200:
                    logger.warning("gdelt lastupdate http %s", resp.status); return
                lastupdate = await resp.text()
        except Exception:
            logger.warning("gdelt lastupdate fetch failed", exc_info=True); return

        url, slice_ts = _parse_lastupdate(lastupdate)
        if not url:
            logger.warning("gdelt: no gkg url in lastupdate"); return
        if slice_ts and slice_ts == self._last_slice_ts:
            return  # already processed this slice

        try:
            async with self._session.get(
                url, headers={"User-Agent": _USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status != 200:
                    logger.warning("gdelt gkg http %s", resp.status); return
                raw = await resp.read()
        except Exception:
            logger.warning("gdelt gkg download failed", exc_info=True); return

        if len(raw) > self._MAX_ZIP_BYTES:
            logger.warning("gdelt gkg zip too large: %d", len(raw)); return

        now_ms = int(time.time() * 1000)
        try:
            items = await asyncio.to_thread(
                _decode_and_map, raw, self._match_keywords, self._max_records,
                self.version, now_ms,
            )
        except Exception:
            logger.warning("gdelt gkg parse failed", exc_info=True); return

        self._last_slice_ts = slice_ts or self._last_slice_ts
        for it in items:
            yield it

def _decode_and_map(raw: bytes, match_keywords, max_records, version, now_ms):
    import io as _io2, zipfile as _zip
    with _zip.ZipFile(_io2.BytesIO(raw)) as z:
        name = z.namelist()[0]
        csv_text = z.read(name).decode("utf-8", errors="replace")
    return _gkg_rows_to_items(csv_text, match_keywords=match_keywords,
                              max_records=max_records, version=version, now_ms=now_ms)
```
   Remove the old DOC `_normalize_query` (now unused) and the DOC `fetch` body. In `services/news_collector/main.py`, change the GDELTNewsSource(...) call to pass `gkg_base_url=cfg.sources.gdelt.gkg_base_url, match_keywords=cfg.sources.gdelt.match_keywords, max_records=..., poll_interval_seconds=..., timeout=cfg.sources.gdelt.timeout_seconds` (drop query/timespan/sort).
- [ ] **Step 4: run → PASS** — `.venv/bin/pytest tests/unit/news/sources/test_gdelt.py tests/unit/news/test_collector_main.py -v`.
- [ ] **Step 5: commit** `feat(news-gdelt): rewrite fetch() to GKG file pipeline (DOC API → data.gdeltproject.org)`.

---

### Task 4: Full regression + deploy note + final review

- [ ] **Step 1:** `.venv/bin/pytest -n auto -m "not serial" -q` + `.venv/bin/pytest -m "serial" -q` — both exit 0.
- [ ] **Step 2:** `.venv/bin/ruff check` + `.venv/bin/black --check` on changed files (gdelt.py, config.py, main.py).
- [ ] **Step 3:** Deploy note (PR body): config bind-mounted → after merge rebuild `news-collector` (code change is baked) + `up -d --no-deps`; set `gdelt.enabled: true`. Verify `news:raw`/`stream:news.raw` gets gdelt entries + no `gdelt rate limited` warning.
- [ ] **Step 4:** Controller runs the final whole-branch review.

---

## Self-Review
**Spec coverage:** config (Task 1), pure parse/title/map helpers (Task 2), async fetch pipeline + constructor + main wiring (Task 3), regression+deploy (Task 4). Mapping rules, keyword filter, skip-no-title, news_id, best-effort, bounded, executor — all covered.
**Placeholder scan:** Tasks 1-3 carry complete code. The test example's `if False else …` markers are explicitly flagged for the implementer to replace with the real published_at_ms assertion (kept only so the example parses). "Locate the existing config/news test" pointers require finding the real test path at execution — concrete, not vague.
**Type consistency:** `_parse_lastupdate -> (url, slice_ts)`, `_extract_page_title -> str|None`, `_gkg_rows_to_items(... now_ms)` / `_decode_and_map` consistent across Tasks 2-3. `version="gdelt-gkg-v1"` consistent. Config fields (gkg_base_url, match_keywords) consistent across Tasks 1/3.
**Note for executor:** verify GKG 2.1 column indices (1/3/4/8/15/26) against a live `.gkg.csv` header before trusting the mapping; the column order is the one external dependency the tests fixture-mock around.
