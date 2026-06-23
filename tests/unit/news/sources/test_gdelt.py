import re

import aiohttp
import pytest
from aioresponses import aioresponses

from shared.news.sources.gdelt import (
    GDELTNewsSource,
    _extract_page_title,
    _gkg_rows_to_items,
    _parse_gdelt_date,
    _parse_lastupdate,
)

# ---------------------------------------------------------------------------
# Existing DOC-API tests (kept verbatim)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gdelt_parses_limited_doc_api_response():
    payload = {
        "articles": [
            {
                "url": "https://example.com/markets/1",
                "title": "Global yields move equity markets",
                "seendate": "20260515T010203Z",
                "domain": "example.com",
                "sourcecountry": "US",
                "language": "English",
            }
        ]
    }
    with aioresponses() as m:
        m.get(
            re.compile(r"^https://api\.gdeltproject\.org/api/v2/doc/doc.*"),
            payload=payload,
        )
        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(
                session=session,
                query='"stock market"',
                max_records=20,
                timespan="6h",
                poll_interval_seconds=300,
            )
            items = [it async for it in src.fetch()]

    assert len(items) == 1
    assert items[0].source == "gdelt"
    assert items[0].news_id.startswith("gdelt_")
    assert items[0].published_at_ms == 1_778_806_923_000
    assert "domain=example.com" in items[0].body
    assert items[0].keywords == ["gdelt", "example.com"]
    assert src.poll_interval_seconds == 300


@pytest.mark.asyncio
async def test_gdelt_parses_compact_seendate_response():
    payload = {
        "articles": [
            {
                "url": "https://example.com/markets/compact",
                "title": "Compact GDELT timestamp",
                "seendate": "20260515010203",
                "domain": "example.com",
                "sourcecountry": "US",
                "language": "English",
            }
        ]
    }
    with aioresponses() as m:
        m.get(
            re.compile(r"^https://api\.gdeltproject\.org/api/v2/doc/doc.*"),
            payload=payload,
        )
        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(session=session, query='"stock market"')
            items = [it async for it in src.fetch()]

    assert len(items) == 1
    assert items[0].published_at_ms == 1_778_806_923_000


@pytest.mark.asyncio
async def test_gdelt_rate_limit_returns_empty():
    with aioresponses() as m:
        m.get(
            re.compile(r"^https://api\.gdeltproject\.org/api/v2/doc/doc.*"),
            status=429,
        )
        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(session=session, query='"stock market"')
            items = [it async for it in src.fetch()]

    assert items == []


# ---------------------------------------------------------------------------
# New pure-helper tests (Task 2)
# ---------------------------------------------------------------------------

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
    assert (
        _extract_page_title("<PAGE_TITLE>Fed holds rates</PAGE_TITLE>")
        == "Fed holds rates"
    )
    assert _extract_page_title("<PAGE_LINKS>x</PAGE_LINKS>") is None
    assert _extract_page_title("") is None


def test_extract_page_title_dotall_with_whitespace():
    """Test DOTALL + whitespace stripping for multiline PAGE_TITLE."""
    result = _extract_page_title("<PAGE_TITLE>\n  Multi\nline  \n</PAGE_TITLE>")
    assert result == "Multi\nline"


def test_parse_lastupdate_malformed_ts():
    """Test malformed filename (non-digit prefix) returns (url, None)."""
    url, ts = _parse_lastupdate(
        "305551 ghi http://data.gdeltproject.org/gdeltv2/BADNAME.gkg.csv.zip"
    )
    assert url == "http://data.gdeltproject.org/gdeltv2/BADNAME.gkg.csv.zip"
    assert ts is None


def _row(
    date="20260623091500",
    domain="reuters.com",
    url="https://reuters.com/a",
    themes="ECON_INTEREST_RATE",
    tone="-2.5,1,3,4",
    title="Federal Reserve holds rates",
):
    # GKG 2.1: 27 tab-separated columns; fill only the ones we read.
    cols = [""] * 27
    cols[1] = date
    cols[3] = domain
    cols[4] = url
    cols[8] = themes
    cols[15] = tone
    cols[26] = f"<PAGE_TITLE>{title}</PAGE_TITLE>" if title else ""
    return "\t".join(cols)


# Expected published_at_ms for GKG DATE 20260623091500 UTC.
# Computed: datetime(2026,6,23,9,15,0,tzinfo=UTC).timestamp() * 1000 = 1782206100000
_EXPECTED_PUBLISHED_AT_MS = int(_parse_gdelt_date("20260623091500") * 1000)


def test_gkg_rows_map_and_filter():
    rows = "\n".join(
        [
            _row(
                url="https://r.com/fed", title="Federal Reserve signals cut"
            ),  # matches title
            _row(
                url="https://r.com/chip",
                themes="WB_SEMICONDUCTOR",
                title="Chip demand",
            ),  # matches theme 'semiconductor'
            _row(
                url="https://r.com/none",
                themes="SPORTS",
                title="Local football result",
            ),  # no match → skip
            _row(url="https://r.com/notitle", title=""),  # no PAGE_TITLE → skip
            _row(url="", title="No url"),  # no url → skip
        ]
    )
    items = _gkg_rows_to_items(
        rows,
        match_keywords=["federal reserve", "semiconductor"],
        max_records=20,
        version="gdelt-gkg-v1",
        now_ms=1782000000000,
    )
    urls = {it.url for it in items}
    assert "https://r.com/fed" in urls
    assert "https://r.com/none" not in urls
    assert "https://r.com/notitle" not in urls

    fed = next(it for it in items if it.url == "https://r.com/fed")
    assert fed.news_id.startswith("gdelt_")
    assert len(fed.news_id) == len("gdelt_") + 16
    assert fed.source == "gdelt"
    assert fed.source_version == "gdelt-gkg-v1"
    assert fed.title == "Federal Reserve signals cut"
    assert "gdelt" in fed.keywords
    assert "reuters.com" in fed.keywords
    assert fed.published_at_ms == _EXPECTED_PUBLISHED_AT_MS


def test_gkg_rows_respects_max_records():
    rows = "\n".join(
        _row(url=f"https://r.com/{i}", title=f"Federal Reserve item {i}")
        for i in range(10)
    )
    items = _gkg_rows_to_items(
        rows,
        match_keywords=["federal reserve"],
        max_records=3,
        version="v",
        now_ms=1,
    )
    assert len(items) == 3
