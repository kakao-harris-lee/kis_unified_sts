"""The ``_runtime.band_source`` / ``_runtime.price_scale`` loader rules — CP-3 band 원천 웨이브"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos_runtime.venue import VenuePolicyConfigError, load_venue_constraint_policy
from tos_runtime.venue.band_journal import ProducerJournalBandSource

from ._documents import (
    SCHEME,
    band_source_runtime_extra,
    producer_journal_band_source_runtime_extra,
    venue_policy_yaml,
)

_INSTRUMENT = "K200F"


def _write(
    tmp_path: Path,
    *,
    runtime_extra: str,
    price_min: str = "null",
    price_max: str = "null",
) -> Path:
    """A fixture venue policy with ``runtime_extra`` in its ``_runtime`` block."""
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
    """The loader takes a THUNK, not a value (independent review L1) — wrapped here so the"""
    return load_venue_constraint_policy(
        path,
        scheme=SCHEME,
        band_transport_instrument_reader=lambda: transport_instrument,
    )


class TestEveryRuleIsReachedAlone:
    """The baseline: the unmutated declaration LOADS, and loads with the values it declared."""

    def test_a_fully_declared_band_source_loads(self, tmp_path: Path) -> None:
        loaded = _load(_write(tmp_path, runtime_extra=band_source_runtime_extra()))

        assert loaded.band_source is not None
        assert loaded.band_source.instrument == _INSTRUMENT
        assert loaded.band_source.tr_id == "FHMIF10000000"
        assert loaded.band_source.price_scale == 100
        assert loaded.band_source.timeout_ms == 5000
        assert loaded.band_source.read_on == ("boot", "phase_change")
        assert loaded.price_scale == 100
        assert loaded.band_source_digest is not None
        assert (
            _load(_write(tmp_path, runtime_extra=band_source_runtime_extra()))
        ).band_source_digest == loaded.band_source_digest

    def test_no_declaration_at_all_loads_with_none_and_demands_no_price_scale(
        self, tmp_path: Path
    ) -> None:
        """Plan §4.1's 재리뷰 MEDIUM: an ABSENT key is ``null``, and a tree that declares none"""
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

    def test_a_price_scale_without_a_band_source_is_returned(
        self, tmp_path: Path
    ) -> None:
        """PR #927 review M1: a kis-mock boot cross-checks its codec's ``price_scale`` against"""
        loaded = _load(_write(tmp_path, runtime_extra="price_scale: 100\n"))

        assert loaded.band_source is None
        assert loaded.price_scale == 100

    @pytest.mark.parametrize("value", ["0", "-100", '"100"', "1.5", "true"])
    def test_a_malformed_price_scale_without_a_band_source_refuses(
        self, tmp_path: Path, value: str
    ) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(_write(tmp_path, runtime_extra=f"price_scale: {value}\n"))
        assert "_runtime.price_scale must be a positive int" in str(excinfo.value)


class TestLazyTransportRead:
    """Independent review L1 — the ``kis_quote`` thunk is called ONLY for a policy that"""

    def test_no_declaration_never_calls_the_reader(self, tmp_path: Path) -> None:
        calls: list[int] = []

        def _explode() -> str | None:
            calls.append(1)
            raise AssertionError("the transport document must not be read at all")

        path = tmp_path / "venue_constraint_policy.yaml"
        path.write_text(venue_policy_yaml(), encoding="utf-8")

        loaded = load_venue_constraint_policy(
            path, scheme=SCHEME, band_transport_instrument_reader=_explode
        )

        assert loaded.band_source is None
        assert calls == []

    def test_a_declaration_does_call_the_reader(self, tmp_path: Path) -> None:
        """The baseline: without it the test above would also pass against a loader that"""
        calls: list[int] = []

        def _counted() -> str | None:
            calls.append(1)
            return _INSTRUMENT

        loaded = load_venue_constraint_policy(
            _write(tmp_path, runtime_extra=band_source_runtime_extra()),
            scheme=SCHEME,
            band_transport_instrument_reader=_counted,
        )

        assert loaded.band_source is not None
        assert calls == [1]


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
    """Plan §4.4b — the band must be read for the contract the policy scopes."""

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
    """Plan §4.4b's config-consistency rule (NOT a guard — it has no fail-open input today;"""

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
    """Plan §4.1's ``timeout_ms`` paragraph — a named-TBD (``null``) template value the"""

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
    """Plan §4.1 — ``kind``/``tr_id``/``bound``/``failure``/``read_on``."""

    def test_an_unreadable_kind_refuses(self, tmp_path: Path) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=band_source_runtime_extra(kind='"regulation_calc"'),
                )
            )

        assert "is not one of ['kis_quote_get', 'producer_journal']" in str(
            excinfo.value
        )

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
        """The rule is SUBSET, not equality — ``["boot"]`` is a legitimate declaration, and"""
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


class TestPerKindRequiredKeys:
    """2026-10-15 plan §3.3 — "로더는 kind 마다 필수 키를 따로 요구한다"."""

    def test_the_producer_journal_baseline_loads(self, tmp_path: Path) -> None:
        """The baseline every mutation below departs from in ONE leaf. Without it a refusal"""
        loaded = _load(
            _write(
                tmp_path,
                runtime_extra=producer_journal_band_source_runtime_extra(
                    instrument=_INSTRUMENT
                ),
            ),
            transport_instrument=None,
        )

        assert isinstance(loaded.band_source, ProducerJournalBandSource)
        assert loaded.band_source.band_journal_path == "/nonexistent/band.jsonl"
        assert loaded.band_source.approved_source_prefixes == ("tos-cp3-live",)
        assert loaded.price_scale == 100
        assert loaded.band_source_digest is not None

    def test_a_producer_journal_source_needs_no_kis_quote_document(
        self, tmp_path: Path
    ) -> None:
        """Plan §3.3. The ``kis_quote_get`` kind refuses without one (that rule has its own"""
        loaded = _load(
            _write(
                tmp_path,
                runtime_extra=producer_journal_band_source_runtime_extra(
                    instrument=_INSTRUMENT
                ),
            ),
            transport_instrument=None,
        )

        assert loaded.band_source is not None

    @pytest.mark.parametrize("leaf", ["band_journal_path", "approved_source_prefixes"])
    def test_a_missing_producer_journal_leaf_refuses(
        self, tmp_path: Path, leaf: str
    ) -> None:
        """Each of the two keys this kind actually READS, removed one at a time."""
        block = producer_journal_band_source_runtime_extra(instrument=_INSTRUMENT)
        mutated = "\n".join(
            line
            for line in block.splitlines()
            if not line.strip().startswith(f"{leaf}:")
        )

        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(_write(tmp_path, runtime_extra=mutated + "\n"), None)

        assert leaf in str(excinfo.value)

    @pytest.mark.parametrize(
        "leaf_yaml",
        [
            "  timeout_ms: 5000\n",
            '  tr_id: "FHMIF10000000"\n',
            '  upper_field: "futs_mxpr"\n',
            '  lower_field: "futs_llam"\n',
            '  basis_field: "futs_sdpr"\n',
        ],
    )
    def test_a_kis_quote_get_leaf_under_producer_journal_refuses(
        self, tmp_path: Path, leaf_yaml: str
    ) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=producer_journal_band_source_runtime_extra(
                        instrument=_INSTRUMENT, extra_leaves=leaf_yaml
                    ),
                ),
                None,
            )

        assert "belong(s) to another kind" in str(excinfo.value)

    def test_a_producer_journal_leaf_under_kis_quote_get_refuses(
        self, tmp_path: Path
    ) -> None:
        """The mirror direction — otherwise the rule would be "producer_journal is strict and"""
        block = band_source_runtime_extra(instrument=_INSTRUMENT)
        mutated = block.replace(
            '  bound: "trading_date_kst"',
            '  band_journal_path: "/x/band.jsonl"\n  bound: "trading_date_kst"',
        )

        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(_write(tmp_path, runtime_extra=mutated))

        assert "band_journal_path" in str(excinfo.value)

    @pytest.mark.parametrize("value", ["[]", '[""]'])
    def test_an_empty_approved_prefix_list_or_entry_refuses(
        self, tmp_path: Path, value: str
    ) -> None:
        """``[]`` approves no writer, so the band would be permanently absent for a reason no"""
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=producer_journal_band_source_runtime_extra(
                        instrument=_INSTRUMENT, approved_source_prefixes=value
                    ),
                ),
                None,
            )

        assert "approved_source_prefixes" in str(excinfo.value)

    def test_the_contract_bond_still_holds_for_this_kind(self, tmp_path: Path) -> None:
        """Band plan 2026-10-08 §4.4b is kind-independent: the source's instrument must be"""
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=producer_journal_band_source_runtime_extra(
                        instrument="A05611"
                    ),
                ),
                None,
            )

        assert "scope.instruments" in str(excinfo.value)

    def test_the_price_scale_bond_still_holds_for_this_kind(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=producer_journal_band_source_runtime_extra(
                        instrument=_INSTRUMENT, band_price_scale="1"
                    ),
                ),
                None,
            )

        assert "price_scale" in str(excinfo.value)

    def test_the_two_literal_bounds_rule_still_holds_for_this_kind(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _load(
                _write(
                    tmp_path,
                    runtime_extra=producer_journal_band_source_runtime_extra(
                        instrument=_INSTRUMENT
                    ),
                    price_min="100",
                    price_max="500",
                ),
                None,
            )

        assert "two sources for one bound" in str(excinfo.value)
