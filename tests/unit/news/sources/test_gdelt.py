import io
import zipfile

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
# Helpers shared by async-fetch tests
# ---------------------------------------------------------------------------

_BASE = "http://data.gdeltproject.org/gdeltv2"
_LASTUPDATE_TEXT = (
    "201892 abc http://data.gdeltproject.org/gdeltv2/20260623091500.export.CSV.zip\n"
    "88123 def http://data.gdeltproject.org/gdeltv2/20260623091500.mentions.CSV.zip\n"
    "305551 ghi http://data.gdeltproject.org/gdeltv2/20260623091500.gkg.csv.zip\n"
)
_GKG_ZIP_URL = "http://data.gdeltproject.org/gdeltv2/20260623091500.gkg.csv.zip"
_SLICE_TS = "20260623091500"


def _row(
    date="20260623091500",
    domain="reuters.com",
    url="https://reuters.com/a",
    themes="ECON_INTEREST_RATE",
    tone="-2.5,1,3,4",
    title="Federal Reserve holds rates",
):
    """Build a single GKG 2.1 TSV row (27 columns)."""
    cols = [""] * 27
    cols[1] = date
    cols[3] = domain
    cols[4] = url
    cols[8] = themes
    cols[15] = tone
    cols[26] = f"<PAGE_TITLE>{title}</PAGE_TITLE>" if title else ""
    return "\t".join(cols)


def _zip_bytes(csv_text: str) -> bytes:
    """Build an in-memory ZIP containing one GKG CSV file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("20260623091500.gkg.csv", csv_text)
    return buf.getvalue()


_CSV_TEXT = _row(
    url="https://reuters.com/fed",
    title="Federal Reserve signals cut",
    themes="ECON_INTEREST_RATE",
)
_ZIP_PAYLOAD = _zip_bytes(_CSV_TEXT)


# ---------------------------------------------------------------------------
# Async fetch() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_yields_mapped_news_items():
    """Happy-path: lastupdate → zip → parsed NewsItem yielded."""
    with aioresponses() as m:
        m.get(f"{_BASE}/lastupdate.txt", status=200, body=_LASTUPDATE_TEXT)
        m.get(_GKG_ZIP_URL, status=200, body=_ZIP_PAYLOAD)

        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(
                session=session,
                gkg_base_url=_BASE,
                match_keywords=["federal reserve"],
                max_records=20,
                poll_interval_seconds=300,
            )
            items = [it async for it in src.fetch()]

    assert len(items) == 1
    item = items[0]
    assert item.source == "gdelt"
    assert item.source_version == "gdelt-gkg-v1"
    assert item.news_id.startswith("gdelt_")
    assert item.url == "https://reuters.com/fed"
    assert item.title == "Federal Reserve signals cut"
    assert src.poll_interval_seconds == 300
    # slice-ts recorded
    assert src._last_slice_ts == _SLICE_TS


@pytest.mark.asyncio
async def test_fetch_skip_unchanged_slice():
    """Second fetch with same slice_ts should yield nothing (already processed)."""
    with aioresponses() as m:
        # Register both first-fetch mocks and a second lastupdate-only mock.
        m.get(f"{_BASE}/lastupdate.txt", status=200, body=_LASTUPDATE_TEXT)
        m.get(_GKG_ZIP_URL, status=200, body=_ZIP_PAYLOAD)
        # Second call sees the same lastupdate → same slice_ts → early return.
        m.get(f"{_BASE}/lastupdate.txt", status=200, body=_LASTUPDATE_TEXT)

        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(
                session=session,
                gkg_base_url=_BASE,
                match_keywords=["federal reserve"],
            )
            # First fetch → consumes items
            first = [it async for it in src.fetch()]
            assert len(first) == 1
            assert src._last_slice_ts == _SLICE_TS

            # Second fetch with same slice_ts → skip (no zip download)
            second = [it async for it in src.fetch()]

    assert second == []


@pytest.mark.asyncio
async def test_fetch_lastupdate_non_200_yields_nothing():
    """HTTP error on lastupdate.txt → yields nothing, no raise."""
    with aioresponses() as m:
        m.get(f"{_BASE}/lastupdate.txt", status=503)

        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(
                session=session,
                gkg_base_url=_BASE,
                match_keywords=["federal reserve"],
            )
            items = [it async for it in src.fetch()]

    assert items == []


@pytest.mark.asyncio
async def test_fetch_zip_download_error_yields_nothing():
    """HTTP error on zip download → yields nothing, no raise."""
    with aioresponses() as m:
        m.get(f"{_BASE}/lastupdate.txt", status=200, body=_LASTUPDATE_TEXT)
        m.get(_GKG_ZIP_URL, status=500)

        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(
                session=session,
                gkg_base_url=_BASE,
                match_keywords=["federal reserve"],
            )
            items = [it async for it in src.fetch()]

    assert items == []


@pytest.mark.asyncio
async def test_fetch_network_exception_yields_nothing():
    """Connection error on lastupdate fetch → yields nothing, no raise."""
    with aioresponses() as m:
        m.get(
            f"{_BASE}/lastupdate.txt",
            exception=aiohttp.ClientConnectionError("simulated"),
        )

        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(
                session=session,
                gkg_base_url=_BASE,
                match_keywords=["federal reserve"],
            )
            items = [it async for it in src.fetch()]

    assert items == []


@pytest.mark.asyncio
async def test_fetch_zip_download_network_exception_yields_nothing():
    """Connection error on zip download → yields nothing, no raise."""
    with aioresponses() as m:
        m.get(f"{_BASE}/lastupdate.txt", status=200, body=_LASTUPDATE_TEXT)
        m.get(
            _GKG_ZIP_URL,
            exception=aiohttp.ClientConnectionError("simulated"),
        )

        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(
                session=session,
                gkg_base_url=_BASE,
                match_keywords=["federal reserve"],
            )
            items = [it async for it in src.fetch()]

    assert items == []


# ---------------------------------------------------------------------------
# Pure-helper tests (Task 2 — unchanged)
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
