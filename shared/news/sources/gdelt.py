"""GDELT news source: GKG file pipeline."""

from __future__ import annotations

import asyncio
import csv as _csv
import hashlib
import io as _io
import logging
import re as _re
import time
import zipfile as _zip
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import aiohttp

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)

_USER_AGENT = "kis-unified-sts-news-collector/1.0"


class GDELTNewsSource(NewsSource):
    name = "gdelt"
    version = "gdelt-gkg-v1"
    poll_interval_seconds = 600
    _MAX_ZIP_BYTES = 50 * 1024 * 1024

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        gkg_base_url: str,
        match_keywords: list[str],
        max_records: int = 20,
        poll_interval_seconds: int | None = None,
        timeout: float = 20.0,
    ):
        self._session = session
        self._base = gkg_base_url.rstrip("/")
        self._match_keywords = list(match_keywords)
        self._max_records = max(1, min(max_records, 100))
        self._timeout = timeout
        self._last_slice_ts: str | None = None
        self.poll_interval_seconds = poll_interval_seconds or self.poll_interval_seconds

    async def fetch(self) -> AsyncIterator[NewsItem]:
        try:
            async with self._session.get(
                f"{self._base}/lastupdate.txt",
                headers={"User-Agent": _USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status != 200:
                    logger.warning("gdelt lastupdate http %s", resp.status)
                    return
                lastupdate = await resp.text()
        except Exception:
            logger.warning("gdelt lastupdate fetch failed", exc_info=True)
            return

        url, slice_ts = _parse_lastupdate(lastupdate)
        if not url:
            logger.warning("gdelt: no gkg url in lastupdate")
            return
        if slice_ts and slice_ts == self._last_slice_ts:
            return  # already processed this slice

        try:
            async with self._session.get(
                url,
                headers={"User-Agent": _USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status != 200:
                    logger.warning("gdelt gkg http %s", resp.status)
                    return
                raw = await resp.read()
        except Exception:
            logger.warning("gdelt gkg download failed", exc_info=True)
            return

        if len(raw) > self._MAX_ZIP_BYTES:
            logger.warning("gdelt gkg zip too large: %d", len(raw))
            return

        now_ms = int(time.time() * 1000)
        try:
            items = await asyncio.to_thread(
                _decode_and_map,
                raw,
                self._match_keywords,
                self._max_records,
                self.version,
                now_ms,
            )
        except Exception:
            logger.warning("gdelt gkg parse failed", exc_info=True)
            return

        self._last_slice_ts = slice_ts or self._last_slice_ts
        for it in items:
            yield it


def _decode_and_map(
    raw: bytes,
    match_keywords: list[str],
    max_records: int,
    version: str,
    now_ms: int,
) -> list[NewsItem]:
    """Unzip GKG CSV and map rows to NewsItems (runs in executor thread)."""
    with _zip.ZipFile(_io.BytesIO(raw)) as z:
        names = z.namelist()
        if not names:
            return []
        csv_text = z.read(names[0]).decode("utf-8", errors="replace")
    return _gkg_rows_to_items(
        csv_text,
        match_keywords=match_keywords,
        max_records=max_records,
        version=version,
        now_ms=now_ms,
    )


def _parse_gdelt_date(raw: str) -> float:
    if not raw:
        return 0.0
    for fmt in ("%Y%m%d%H%M%S", "%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC).timestamp()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# GKG 2.1 pure helpers (no network/IO — used by Task-3 fetch())
# ---------------------------------------------------------------------------

_PAGE_TITLE_RE = _re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", _re.DOTALL)

# GKG 2.1 column indices.
_C_DATE = 1
_C_DOMAIN = 3
_C_URL = 4
_C_THEMES = 8
_C_TONE = 15
_C_EXTRAS = 26


def _parse_lastupdate(text: str) -> tuple[str | None, str | None]:
    """Return (gkg_zip_url, slice_ts) from a GDELT lastupdate manifest text.

    Scans lines for the one ending in `.gkg.csv.zip` and extracts the
    timestamp prefix from the filename.  Returns (None, None) if absent or
    malformed.
    """
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[-1].endswith(".gkg.csv.zip"):
            url = parts[-1]
            fname = url.rsplit("/", 1)[-1]  # e.g. 20260623091500.gkg.csv.zip
            ts = fname.split(".", 1)[0]  # e.g. 20260623091500
            return url, (ts if ts.isdigit() else None)
    return None, None


def _extract_page_title(extras: str) -> str | None:
    """Return text inside the first <PAGE_TITLE>…</PAGE_TITLE> tag, or None."""
    if not extras:
        return None
    m = _PAGE_TITLE_RE.search(extras)
    if not m:
        return None
    title = m.group(1).strip()
    return title or None


def _gkg_rows_to_items(
    csv_text: str,
    *,
    match_keywords: list[str],
    max_records: int,
    version: str,
    now_ms: int,
) -> list[NewsItem]:
    """Parse GKG 2.1 TSV rows into NewsItems, filtered by keyword match.

    Args:
        csv_text: Raw tab-separated GKG CSV content (no header row expected).
        match_keywords: Case-insensitive substrings to match against title+themes.
        max_records: Hard cap on the number of items returned.
        version: Value for ``NewsItem.source_version``.
        now_ms: Current epoch-ms used as ``received_at_ms`` and as fallback
            ``published_at_ms`` when the DATE column cannot be parsed.

    Returns:
        List of at most *max_records* matching NewsItems.
    """
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
        items.append(
            NewsItem(
                news_id=f"gdelt_{digest}",
                source="gdelt",
                published_at_ms=int(published_s * 1000) if published_s else now_ms,
                received_at_ms=now_ms,
                title=title,
                body=body,
                url=url,
                source_version=version,
                lang="unknown",
                keywords=[k for k in ("gdelt", domain) if k],
            )
        )
        if len(items) >= max_records:
            break
    return items
