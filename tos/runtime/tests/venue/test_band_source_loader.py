"""The ``_runtime.band_source`` / ``_runtime.price_scale`` loader rules — CP-3 band 원천 웨이브
plan §8 items 4b, 4d and 6 (``docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md``).

**One test per CLAUSE, never one test per file.** #838's lesson is that a guard proved only in
aggregate hides whichever clause contributes nothing: if deleting one clause leaves every test
green, that clause was never judging anything. So each refusal below is reached by a document
that differs from a LOADABLE one in exactly one leaf, and
:class:`TestEveryRuleIsReachedAlone`'s baseline pins that the unmutated document really does
load — without it, every refusal here could be firing for an unrelated reason.

**Nothing in this file touches the network**, and no band is read: a loader refusal happens
before any reader exists.

Hermetic (``tos/runtime/tests/conftest.py`` D1.4): every write lands under ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos_runtime.venue import VenuePolicyConfigError, load_venue_constraint_policy

from ._documents import SCHEME, band_source_runtime_extra, venue_policy_yaml

#: The band source's own instrument, equal to the fixture policy's ``scope.instruments`` sole
#: element — a LOADABLE declaration, which every mutation below departs from in one leaf.
_INSTRUMENT = "K200F"


def _write(
    tmp_path: Path,
    *,
    runtime_extra: str,
    price_min: str = "null",
    price_max: str = "null",
) -> Path:
    """A fixture venue policy with ``runtime_extra`` in its ``_runtime`` block.

    ``price_min``/``price_max`` default to ``null`` here — the opposite of
    :func:`venue_policy_yaml`'s own defaults — because a DECLARED band source is the source of
    those two bounds (plan §4.1 "원천 둘"). A test that wants the literals back passes them.

    Spelled out rather than forwarded through ``**kwargs: str``: :func:`venue_policy_yaml` also
    takes ``int`` parameters, so a ``str``-valued kwargs unpack is a type error waiting for the
    first test that mistypes a name (mypy says so — ``arg-type`` on the unpack). These two are
    the only overrides this suite has ever needed.
    """
    path = tmp_path / "venue_constraint_policy.yaml"
    path.write_text(
        venue_policy_yaml(
            price_min=price_min,
            price_max=price_max,
            runtime_extra=runtime_extra,
        ),
        encoding="utf-8",
    )
    return path


def _load(path: Path, transport_instrument: str | None = _INSTRUMENT):
    return load_venue_constraint_policy(
        path, scheme=SCHEME, band_transport_instrument=transport_instrument
    )


class TestEveryRuleIsReachedAlone:
    """The baseline: the unmutated declaration LOADS, and loads with the values it declared.

    Without this, a refusal test proves only "this document does not load", which a typo in the
    fixture would also satisfy.
    """

    def test_a_fully_declared_band_source_loads(self, tmp_path: Path) -> None:
        loaded = _load(_write(tmp_path, runtime_extra=band_source_runtime_extra()))

        assert loaded.band_source is not None
        assert loaded.band_source.instrument == _INSTRUMENT
        assert loaded.band_source.tr_id == "FHMIF10000000"
        assert loaded.band_source.price_scale == 100
        assert loaded.band_source.timeout_ms == 5000
        assert loaded.band_source.read_on == ("boot", "phase_change")
        assert loaded.price_scale == 100
        # The digest is over the declaration, so it is stable across loads of the same bytes
        # and is what VENUE_POLICY_BOUND records (plan §4.5 / §6 (B)).
        assert loaded.band_source_digest is not None
        assert (
            _load(_write(tmp_path, runtime_extra=band_source_runtime_extra()))
        ).band_source_digest == loaded.band_source_digest

    def test_no_declaration_at_all_loads_with_none_and_demands_no_price_scale(
        self, tmp_path: Path
    ) -> None:
        """Plan §4.1's 재리뷰 MEDIUM: an ABSENT key is ``null``, and a tree that declares none
        is NOT required to carry ``_runtime.price_scale``. Requiring it unconditionally would
        ABORT the resident paper session at the first 08:45 after this merge — this assertion
        is the unit-level half of that, ``tests/compose/test_venue_band_source_wiring.py``
        asserts it against the REAL resident file."""
        path = tmp_path / "venue_constraint_policy.yaml"
        path.write_text(venue_policy_yaml(), encoding="utf-8")

        loaded = load_venue_constraint_policy(path, scheme=SCHEME)

        assert loaded.band_source is None
        assert loaded.band_source_digest is None
        assert loaded.price_scale is None

    def test_an_explicit_null_declaration_is_the_same_as_absence(
        self, tmp_path: Path
    ) -> None:
        loaded = _load(
            _write(
                tmp_path,
                runtime_extra="band_source: null\n",
                price_min="100",
                price_max="500",
            )
        )

        assert loaded.band_source is None


class TestTwoSourcesForOneBound:
    """Plan §4.1 — ``shape_constraints.price_min``/``price_max`` literals AND a band source."""

    @pytest.mark.parametrize(
        ("price_min", "price_max"), [("100", "null"), ("null", "500"), ("100", "500")]
    )
    def test_a_literal_bound_beside_a_band_source_refuses(
        self, tmp_path: Path, price_min: str, price_max: str
    ) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=band_source_runtime_extra(),
                    price_min=price_min,
                    price_max=price_max,
                )
            )

        assert "price_min/price_max carry literals" in str(excinfo.value)


class TestContractBond:
    """Plan §4.4b — the band must be read for the contract the policy scopes.

    The input is the 2026-10-08 P-VL measurement's own neighbouring contract: ``A05611``'s band
    passes every §4.2 validation clause, so nothing downstream of the loader can tell it apart
    from ``A05610``'s. ``tests/venue/test_service_band.py`` carries the ADMISSIBLE-with-the-
    wrong-band half of this red proof.
    """

    def test_an_instrument_outside_scope_refuses(self, tmp_path: Path) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=band_source_runtime_extra(instrument="A05611"),
                ),
                transport_instrument="A05611",
            )

        assert "scope.instruments' sole element" in str(excinfo.value)


class TestTransportConsistency:
    """Plan §4.4b's config-consistency rule (NOT a guard — it has no fail-open input today;
    it becomes one when the same transport is also the order price's source)."""

    def test_an_absent_transport_document_refuses(self, tmp_path: Path) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(tmp_path, runtime_extra=band_source_runtime_extra()),
                transport_instrument=None,
            )

        assert "no kis_quote transport document" in str(excinfo.value)

    def test_a_disagreeing_transport_instrument_refuses(self, tmp_path: Path) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(tmp_path, runtime_extra=band_source_runtime_extra()),
                transport_instrument="A05611",
            )

        assert "kis_quote transport instrument" in str(excinfo.value)


class TestPriceScale:
    """Plan §8 4d — the price-scale rules apply ONLY to a tree that declares a band source."""

    def test_an_absent_price_scale_refuses(self, tmp_path: Path) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path, runtime_extra=band_source_runtime_extra(price_scale=None)
                )
            )

        assert "_runtime.price_scale must be a positive int" in str(excinfo.value)

    def test_a_disagreeing_price_scale_refuses(self, tmp_path: Path) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=band_source_runtime_extra(
                        price_scale="100", band_price_scale="1"
                    ),
                )
            )

        assert "!= _runtime.band_source.price_scale" in str(excinfo.value)


class TestTimeoutMs:
    """Plan §4.1's ``timeout_ms`` paragraph — a named-TBD (``null``) template value the
    ENABLING deployment's operator adopts. A tree that turns the source on without adopting one
    must not boot; §8 4d's other half (a GET that exceeds it) lives in
    ``test_band_source.py``."""

    @pytest.mark.parametrize("value", ["null", "0", "-1", '"5000"', "true", "5000.0"])
    def test_a_non_positive_int_timeout_refuses(
        self, tmp_path: Path, value: str
    ) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path, runtime_extra=band_source_runtime_extra(timeout_ms=value)
                )
            )

        assert "band_source.timeout_ms must be a positive int" in str(excinfo.value)


class TestDeclaredVocabulary:
    """Plan §4.1 — ``kind``/``tr_id``/``bound``/``failure``/``read_on``.

    Each of these refuses a declaration the runtime cannot honour. Without them a document
    could declare, say, ``failure: "last_known"`` and still get the ``unknown`` behaviour —
    the policy would say one thing and the runtime do another, which is exactly the
    "guard that admits what it names" shape this repo keeps rediscovering.
    """

    def test_an_unreadable_kind_refuses(self, tmp_path: Path) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=band_source_runtime_extra(kind='"regulation_calc"'),
                )
            )

        assert "is not 'kis_quote_get'" in str(excinfo.value)

    @pytest.mark.parametrize(
        "value", ['"VTTO1001U"', '"FHMIF1000000"', '"fhmif10000000"']
    )
    def test_a_tr_id_outside_the_measured_quote_shape_refuses(
        self, tmp_path: Path, value: str
    ) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(tmp_path, runtime_extra=band_source_runtime_extra(tr_id=value))
            )

        assert "measured KIS quotations TR id shape" in str(excinfo.value)

    def test_an_unimplemented_bound_refuses(self, tmp_path: Path) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path, runtime_extra=band_source_runtime_extra(bound='"session"')
                )
            )

        assert "is not 'trading_date_kst'" in str(excinfo.value)

    def test_a_failure_response_other_than_unknown_refuses(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=band_source_runtime_extra(failure='"last_known"'),
                )
            )

        assert "is not 'unknown'" in str(excinfo.value)

    @pytest.mark.parametrize("value", ['["boot", "every_tick"]', '["intraday"]', "[]"])
    def test_a_read_on_outside_the_two_tokens_refuses(
        self, tmp_path: Path, value: str
    ) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(tmp_path, runtime_extra=band_source_runtime_extra(read_on=value))
            )

        assert "must be a non-empty subset of" in str(excinfo.value)

    def test_a_read_on_subset_of_one_token_loads(self, tmp_path: Path) -> None:
        """The rule is SUBSET, not equality — ``["boot"]`` is a legitimate declaration (read
        once, never again). Without this the ``read_on`` test above would also pass against a
        wrongly-written equality check."""
        loaded = _load(
            _write(
                tmp_path, runtime_extra=band_source_runtime_extra(read_on='["boot"]')
            )
        )

        assert loaded.band_source is not None
        assert loaded.band_source.read_on == ("boot",)

    def test_a_non_mapping_band_source_refuses(self, tmp_path: Path) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(_write(tmp_path, runtime_extra='band_source: "FHMIF10000000"\n'))

        assert "_runtime.band_source must be a mapping or null" in str(excinfo.value)
