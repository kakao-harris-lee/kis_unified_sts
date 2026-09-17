"""``intake_kind`` wiring-level tests (TOS tick-source wave, W2 lane review finding — HIGH).

**Why this file exists, separate from ``test_marketfeed_wiring.py``.** That suite's own
config-writer, ``_write_marketfeed_config``, ALWAYS writes a valid, non-empty ``intake_kind:
journal`` — every test there exercises the journal-backed happy path, never the SELECTOR itself.
An independent review confirmed this gap by mutation: patching ``_require_intake_kind`` to
silently return ``"journal"`` on a missing/empty value left **zero tests red** — the headline
claim ("어느 쪽도 자동 대체 없음", neither intake kind is a silent fallback for the other) had no
test defending it, and the entire ``intake_kind: kis_quote`` branch (``_build_intake``,
``_resolve_kis_instance_rest_bases``) was never reached through ``build_tick_scheduler`` at all —
``grep -rln "_resolve_kis_instance_rest_bases|_build_intake" tests/`` returned nothing before this
file. This module closes both gaps: every selector-refusal case, and a REAL ``kis_quote`` branch
execution through the full compose stack.

Hermetic (D1.4): no network — the ``kis_quote``-branch tests below never call ``tick_once()``
(module docstring's own "WIRING, not admission" scope discipline, mirroring
``test_transport_wiring.py``'s ``test_e2e_boot_wires_a_kis_mock_transport_and_codec_digest_source``)
so ``endpoint_rest_base`` stays the real MOCK_VTS host string end to end — the host-seal check is
a pure string comparison, never an actual request.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.compose._marketfeed_wiring import (
    MarketFeedConfigError,
    load_marketfeed_config,
)
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.transport.kis_quote.adapter import KisQuoteObservationIntake
from tos_runtime.transport.kis_quote.config import KisQuoteTransportConfigError

from . import _fixtures as fx
from .test_compose_root import _compose
from .test_marketfeed_wiring import (
    _write_critical_input_policy,
    _write_journal,
)
from .test_transport_wiring import _activate_mock_stock_order, _build_custody

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _write_marketfeed_config_raw(config_dir: Path, raw: dict[str, Any]) -> None:
    """Write ``marketfeed.yaml`` from a caller-supplied raw mapping, bypassing
    ``_write_marketfeed_config``'s own always-valid ``intake_kind``/``journal_path`` — the
    selector-refusal tests below need to control (or omit) exactly those two fields."""
    (config_dir / "marketfeed.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )


def _valid_marketfeed_raw(*, journal_path: Path) -> dict[str, Any]:
    """The same fields ``test_marketfeed_wiring.py``'s own ``_write_marketfeed_config`` writes,
    as a plain dict a test can selectively mutate/omit before writing."""
    return {
        "instruments": [fx.INSTRUMENT],
        "instrument_class": fx.INSTRUMENT_CLASS,
        "account": fx.ACCOUNT,
        "direction": "LONG",
        "quantity_basis": "FIXED",
        "unit": "CONTRACT",
        "intake_kind": "journal",
        "journal_path": str(journal_path),
        "poll_interval_ms": 100,
        "snapshot_age_bound": 60_000,
        "interval_width": 1_000,
    }


def _write_kis_quote_transport_config(config_dir: Path, **overrides: Any) -> Path:
    """Write a fully-valued ``kis_quote.yaml`` — mirrors
    ``_fixtures.write_kis_mock_transport_config``'s own "every named-TBD field of the shipped
    example filled with a concrete, schema-valid value" discipline. Defaults to the REAL MOCK_VTS
    host string (:data:`_fixtures.KIS_MOCK_REST_BASE`) — no network is ever exercised by the
    tests in this module (module docstring)."""
    raw: dict[str, Any] = {
        "endpoint_rest_base": fx.KIS_MOCK_REST_BASE,
        "allow_plaintext_for_tests": False,
        "quote_path": "/uapi/domestic-futureoption/v1/quotations/inquire-price",
        "tr_id": "FHMIF10000000",
        "market_div_code": "F",
        "instrument": fx.INSTRUMENT,
        "token_path": "/oauth2/tokenP",
        "token_reissue_min_interval_s": 60,
        "field_mapping": {"futs_prpr": "close"},
        "source_id": "kis_quote_wiring_test",
        "request_timeout_s": 2.0,
    }
    raw.update(overrides)
    path = config_dir / "kis_quote.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# selector refusals — cheap, SYNTHETIC transport, no broker instance needed
# (none of these reach _build_intake's kis_quote branch at all)
# ---------------------------------------------------------------------------


def test_missing_intake_kind_refuses(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    del raw["intake_kind"]
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="intake_kind"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_null_intake_kind_refuses(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    raw["intake_kind"] = None
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="intake_kind"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_unknown_intake_kind_refuses(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``journal_path`` is deliberately OMITTED from ``raw`` (not merely left at its valid
    default) — with ``journal_path`` present, ``_resolve_journal_path``'s own XOR cross-check
    ("journal_path is set but intake_kind is not journal") fires first and its message also
    contains the substring ``intake_kind=``, which would satisfy a loose ``match="intake_kind"``
    even if ``_require_intake_kind``'s own membership check were deleted entirely (verified by
    mutation — see the W2 lane review finding this docstring closes). Omitting ``journal_path``
    means that XOR check cannot fire at all, so only ``_require_intake_kind`` itself can raise
    here, and ``match`` is narrowed to ``"is not one of"`` — the fragment unique to its
    membership-check branch, not shared with its missing/null branch or with
    ``_resolve_journal_path``'s messages."""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    del raw["journal_path"]
    raw["intake_kind"] = "websocket"  # not one of ("journal", "kis_quote")
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="is not one of"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_journal_path_present_with_kis_quote_intake_refuses(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``journal_path`` set while ``intake_kind: kis_quote`` — refused BEFORE ever reaching
    ``_build_intake``/``_resolve_kis_instance_rest_bases`` (no ``kis_quote.yaml``/broker
    instance is written here at all — if this refused for the WRONG reason, that absence would
    make it fail loud, not pass by accident)."""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    raw["intake_kind"] = "kis_quote"
    # journal_path deliberately LEFT IN raw — this is the field under test.
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="journal_path"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_journal_path_absent_with_journal_intake_refuses(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``match`` is narrowed to ``"required when intake_kind"`` — the fragment unique to
    ``_resolve_journal_path``'s own dedicated "missing for the journal branch" check. A generic
    ``match="journal_path"`` would ALSO be satisfied if that dedicated check were deleted and
    ``_resolve_journal_path`` fell through to ``_require_str(raw, "journal_path", path)``, whose
    own generic-field message ("'journal_path' is missing, still null (named-TBD), or not a
    non-empty string") also contains the substring ``journal_path`` — verified by mutation (W2
    lane review finding this docstring closes)."""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    del raw["journal_path"]
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="required when intake_kind"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


# ---------------------------------------------------------------------------
# kis_quote branch — actually reached through build_tick_scheduler
# ---------------------------------------------------------------------------
#
# MOCK_STOCK_ORDER is the only scope in broker_scopes.example.yaml bound to the MOCK_VTS
# INSTANCE document (REAL_READ/REAL_ORDER bind to REAL_PROD instead, which would make
# _resolve_kis_instance_rest_bases's own mock/real documents identical and refuse on THAT
# ground — not the one under test here). Activating it forces transport_kind=KIS_MOCK
# (refuse_transport_scope_mismatch — module docstring), which is a TEST FIXTURE constraint, not
# a claim that the kis_quote intake depends on the order transport kind in production:
# _resolve_kis_instance_rest_bases takes broker_scopes as a plain argument, independent of
# transport_kind, exactly like _marketfeed_wiring.py's own module docstring says.


def test_kis_quote_intake_builds_through_the_full_compose_stack(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root)
    _write_critical_input_policy(config_dir)
    _write_kis_quote_transport_config(config_dir)
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "unused.jsonl")
    raw["intake_kind"] = "kis_quote"
    del raw["journal_path"]
    _write_marketfeed_config_raw(config_dir, raw)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    try:
        assert runtime.marketfeed is not None
        assert isinstance(runtime.marketfeed._intake, KisQuoteObservationIntake)
    finally:
        runtime.rcl_log.close()
        runtime.evidence_store.close()


def test_kis_quote_intake_missing_config_file_refuses_at_wiring_level(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Same setup as the happy path, MINUS ``kis_quote.yaml`` itself — proves
    ``_build_intake``'s kis_quote branch is genuinely reached (not short-circuited) even in a
    failure case, and that the failure is the SPECIFIC ``kis_quote.yaml``-shaped one, not a
    coincidental earlier refusal."""
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root)
    _write_critical_input_policy(config_dir)
    # Deliberately NOT calling _write_kis_quote_transport_config(config_dir).
    assert not (config_dir / "kis_quote.yaml").exists()
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "unused.jsonl")
    raw["intake_kind"] = "kis_quote"
    del raw["journal_path"]
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(KisQuoteTransportConfigError, match="not found"):
        _compose(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            transport_kind=TransportKind.KIS_MOCK,
        )


def test_kis_quote_intake_no_instance_binding_refuses_at_wiring_level(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """The DEFAULT ``config_dir`` fixture's ``broker_scopes.yaml`` (``SYNTHETIC_FUTURES_ORDER``,
    no ``instance`` block) — proves ``_resolve_kis_instance_rest_bases`` itself refuses, not
    merely a config-file-shape check, when the active scope carries no broker instance binding at
    all. Left at the SYNTHETIC default transport_kind deliberately: this is the "kis_quote intake
    with a purely synthetic order transport" shape the module docstring claims is possible — it
    fails here ONLY because this particular default scope has no instance binding, not because
    synthetic and kis_quote are inherently incompatible."""
    _write_critical_input_policy(config_dir)
    _write_kis_quote_transport_config(config_dir)
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "unused.jsonl")
    raw["intake_kind"] = "kis_quote"
    del raw["journal_path"]
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="instance"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


# ---------------------------------------------------------------------------
# shipped example (W2 lane review finding — LOW: no test ever loaded this file)
# ---------------------------------------------------------------------------


def test_shipped_example_file_is_all_null_and_therefore_refuses() -> None:
    """``marketfeed.example.yaml`` is a template, not an approved config — every leaf is ``null``
    (named-TBD), so loading it as-shipped must refuse (``_marketfeed_wiring`` module docstring's
    own "still-null or missing required leaf here IS a fail-closed refusal at load" note). Mirrors
    ``test_construction_config.py``'s
    ``test_shipped_example_file_is_all_null_and_therefore_refuses``.

    Every other test in this module and in ``test_marketfeed_wiring.py`` writes its own synthetic
    ``marketfeed.yaml`` via ``_write_marketfeed_config``/``_write_marketfeed_config_raw`` — nothing
    ever loaded the shipped example file itself before this test existed, which is exactly why a
    missing required key in it (``poll_interval_ms``, W2 lane) went unnoticed by hand: "every
    fixture is green" and "the shipped example is valid" were unconnected statements."""
    example_path = (
        Path(__file__).resolve().parents[2] / "config" / "marketfeed.example.yaml"
    )
    assert (
        example_path.is_file()
    ), "fixture assumption: the example file ships at this path"
    with pytest.raises(MarketFeedConfigError):
        load_marketfeed_config(example_path)
