"""Unit tests for ODNO identity matching (``tools/broker_probes``).

The two broker surfaces do not encode an order number the same way. Verbatim,
from one 모의투자 order — artifact ``P-5-20260731T002112Z.json``:

* ``output.ODNO`` of the futures order accept response: ``"0000000762"``
* ``odno`` of the inquire-ccnl row for that same order: ``"        762"``

Every probe compared them with ``str(...).strip()`` on each side, i.e. asked
whether ``"762" == "0000000762"``. That is False for every order that has ever
existed, so P-5 polled for 30 s, never matched, and recorded a CENSORED trial with
``n=0`` and ``NOT_MEASURED`` — while its own cleanup cancel of that ODNO returned
``rt_cd=0``. The query surface had been returning the order the whole time. The
measurement was lost to the comparison, not to the broker.

Three properties are tested here, because each one fails silently:

1. **Canonicalization.** Space-padded, zero-padded and bare forms of one order
   number collapse to one key; a genuinely different order number does not; and an
   absent ODNO never matches a real one. A non-numeric ODNO is refused loudly,
   because the failure being removed here is precisely a silent non-match.
2. **Every matching site.** One test per probe that matches a submitted order
   against a query row, each serving the row in the broker's own space-padded form.
   These are the regressions that matter: a site that missed the fix reproduces the
   censoring with no visible symptom. The negative direction is asserted too — a
   row belonging to a different order must still not match, or the fix would be
   "match everything".
3. **The wire form survives.** Canonicalization is for comparison only. A cancel
   still sends the verbatim zero-padded ``ORGN_ODNO``, which is the form the broker
   demonstrably accepted a cancel for.

No test here opens a socket: ``probes_order.http_json`` is replaced by a recorder.
"""

from __future__ import annotations

import argparse
import itertools
from collections.abc import Callable
from typing import Any

import pytest

from tools.broker_probes import probes_order
from tools.broker_probes.common import ProbeError, ProbeRun
from tools.broker_probes.probes_order import (
    _ODNO_ABSENT,
    _ODNO_FORMAT_KEY,
    Placed,
    odno_key,
    probe_nmpr_ab,
    probe_p2,
    probe_p5,
    probe_p8,
    probe_pfqp,
    record_odno_wire_format,
)

_ACCOUNT = "1234567890"
_SYMBOL = "A01609"

#: The verbatim pair from artifact ``P-5-20260731T002112Z`` — one order, two
#: encodings. Every canonicalization test is anchored to the real observation
#: rather than to an invented example.
_SUBMIT_FORM = "0000000762"
_QUERY_ROW_FORM = "        762"

#: The touch the recorder quotes, so a resting price is derivable.
_LAST_PRICE = "905.20"


def _space_pad(zero_padded: str) -> str:
    """Re-encode an accept-response ODNO the way the query row returns it.

    Leading zeros dropped, then space-padded to 11 characters — the shape of
    ``"        762"``.
    """
    return zero_padded.lstrip("0").rjust(11)


def _foreign_row_odno(_zero_padded: str) -> str:
    """A row belonging to a different order, in the same broker encoding."""
    return _space_pad("0000000999")


@pytest.fixture
def futures_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Export exactly the env vars ``resolve_credentials`` reads for futures."""
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", _ACCOUNT)
    monkeypatch.delenv("KIS_TOKEN_CACHE_DIR", raising=False)


class _StubAuth:
    def get_auth_headers(self) -> dict[str, str]:
        return {"authorization": "Bearer stub"}


def _args(**overrides: object) -> argparse.Namespace:
    """Order-probe arguments with the clocks wound down and pacing disabled.

    Every assertion below is on a recorded identity or a recorded case, never on a
    wall-clock value, so no test here is timing-fragile.
    """
    base: dict[str, object] = {
        "probe_id": "P-5",
        "symbol": _SYMBOL,
        "asset": "futures",
        "confirm": True,
        "quantity": 1,
        "price_offset_pct": 10.0,
        "samples": 1,
        "margin_pct": 50.0,
        "poll_ms": 1.0,
        "gap_ms": 0.0,
        "inter_trial_s": 0.0,
        "settle_seconds": 0.0,
        "visibility_timeout_s": 2.0,
        "balance_timeout_s": 2.0,
        "late_window_s": 0.05,
        "max_pages": 10,
        "allow_fill": False,
        "stock_order_type": "market",
        "pace_s": 0.0,
        "token_cache_dir": None,
        "out_dir": None,
        "note": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _install_futures_recorder(
    monkeypatch: pytest.MonkeyPatch,
    *,
    row_odno: Callable[[str], str] = _space_pad,
) -> list[dict[str, Any]]:
    """Serve a futures quote, order accepts, cancels/amends and inquire-ccnl rows.

    The accept response zero-pads its ODNO and the inquire row re-encodes it
    through ``row_odno`` — by default the broker's observed space-padded form. That
    asymmetry is the whole point: a recorder that echoed one format back would let
    the defect pass.

    Args:
        row_odno: Re-encodes an accepted ODNO into the row's ``odno`` field. Pass
            :func:`_foreign_row_odno` to serve rows for a different order.
    """
    calls: list[dict[str, Any]] = []
    accepted: list[str] = []
    cancelled: set[str] = set()
    numbers = itertools.count(762)

    def _next_odno() -> str:
        return str(next(numbers)).rjust(10, "0")

    def _rows() -> list[dict[str, str]]:
        return [
            {
                "odno": row_odno(odno),
                "pdno": _SYMBOL,
                "ord_qty": "1",
                "tot_ccld_qty": "0",
                # A cancelled order reports nothing remaining, which is what lets
                # P-FQP reach a stable (filled, remaining=0) reading.
                "qty": "0" if odno in cancelled else "1",
                "nmpr_type_cd": "01",
            }
            for odno in accepted
        ]

    def _recorder(
        _session: Any,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> tuple[int, dict[str, Any], float, str]:
        body = json_body or {}
        calls.append(
            {"url": url, "method": method, "body": body, "params": params or {}}
        )
        if "quotations/inquire-price" in url:
            payload: dict[str, Any] = {
                "rt_cd": "0",
                "output1": {"futs_prpr": _LAST_PRICE},
            }
        elif "trading/inquire-ccnl" in url:
            payload = {"rt_cd": "0", "output1": _rows()}
        elif "trading/order-rvsecncl" in url:
            # An amend issues its own new resting order; a cancel takes the
            # original's remaining quantity to zero. Both acks carry their OWN
            # zero-padded ODNO, which is the Q-CXL-1 quirk P-FQP records.
            ack_odno = _next_odno()
            if body.get("RVSE_CNCL_DVSN_CD") == "01":
                # The amended order rests under the SAME ODNO the ack reports —
                # drawing a second number here would serve a row the probe was
                # never told about, and P-8 would see zero coexistence for a
                # reason that has nothing to do with the broker.
                accepted.append(ack_odno)
            else:
                cancelled.add(str(body.get("ORGN_ODNO", "")))
            payload = {"rt_cd": "0", "output": {"ODNO": ack_odno}}
        elif url.endswith("trading/order"):
            odno = _next_odno()
            accepted.append(odno)
            payload = {"rt_cd": "0", "output": {"ODNO": odno}}
        else:  # pragma: no cover - an unexpected path is a test bug, not a pass
            raise AssertionError(f"unexpected probe URL: {url}")
        return 200, payload, 1.0, "{}"

    monkeypatch.setattr(probes_order, "http_json", _recorder)
    monkeypatch.setattr(
        "shared.kis.auth.KISAuthManager", lambda *a, **k: _StubAuth(), raising=True
    )
    return calls


def _cancels(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in calls if "trading/order-rvsecncl" in c["url"]]


# ---------------------------------------------------------------------------
# odno_key — the canonicalization rule
# ---------------------------------------------------------------------------


def test_the_two_observed_encodings_share_one_key() -> None:
    """The exact pair from ``P-5-20260731T002112Z``, and the bug it caused."""
    assert odno_key(_SUBMIT_FORM) == odno_key(_QUERY_ROW_FORM) == "762"
    # What the old comparison actually evaluated.
    assert _QUERY_ROW_FORM.strip() != _SUBMIT_FORM


@pytest.mark.parametrize(
    "raw",
    [
        "0000000762",
        "        762",
        "762",
        "  0000000762  ",
        "\t762\n",
        "00762",
    ],
)
def test_every_representation_collapses_to_the_same_key(raw: str) -> None:
    """Whitespace and leading zeros are the only differences, in any combination."""
    assert odno_key(raw) == "762"


def test_a_different_order_number_still_does_not_match() -> None:
    """The fix must canonicalize, not equate."""
    assert odno_key("        763") != odno_key("0000000762")
    assert odno_key("0000007620") != odno_key("0000000762")


def test_an_all_zero_odno_keeps_a_single_zero() -> None:
    """``lstrip('0')`` on ``"0000000000"`` is empty; the key must not be."""
    assert odno_key("0000000000") == "0"
    assert odno_key("0") == "0"
    assert odno_key("0000000000") != _ODNO_ABSENT


@pytest.mark.parametrize("absent", ["", "   ", None])
def test_an_absent_odno_never_matches_a_real_one(absent: object) -> None:
    """Empty and ``None`` collapse to a sentinel that is not a digit string.

    Two absent values do share the sentinel — that is what set arithmetic over
    query rows needs. The guarantee is only that an absent ODNO never matches a
    REAL order number, including the all-zero one.
    """
    assert odno_key(absent) == _ODNO_ABSENT
    assert odno_key(absent) != odno_key(_SUBMIT_FORM)
    assert odno_key(absent) != odno_key("0000000000")


@pytest.mark.parametrize("raw", ["A0000762", "76-2", "762x", "７６２"])
def test_a_non_numeric_odno_is_refused_loudly(raw: str) -> None:
    """Loud, not a silent non-match — a silent non-match is the original defect.

    A quietly unmatchable identifier censors every trial of a run instead of
    failing one call, which is exactly how the P-5 measurement was lost.
    """
    with pytest.raises(ProbeError, match="not numeric"):
        odno_key(raw)


def test_placed_keeps_the_verbatim_odno_and_derives_the_key() -> None:
    """The wire form and the comparison form are different values, both available."""
    placed = Placed(_SUBMIT_FORM, 0.0, {})

    assert placed.odno == _SUBMIT_FORM
    assert placed.key == "762"


# ---------------------------------------------------------------------------
# the per-probe regressions — a space-padded row IS the submitted order
# ---------------------------------------------------------------------------


def test_p5_recognises_the_space_padded_row_as_its_own_order(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The regression that matters: the sample P-5 exists to take is taken.

    Before the fix this run produced ``censored_trials=1``, ``n=0`` and
    ``NOT_MEASURED`` against a query that was returning the order all along.
    """
    _install_futures_recorder(monkeypatch)

    run = probe_p5(_args())

    candidate = run.measurements["B_broker_query_consistency_candidate"]
    assert candidate["n"] == 1
    assert run.measurements["censored_trials"] == 0
    assert run.errors == []
    assert run.to_dict()["provenance_class"] == "MEASURED"


def test_p5_still_censors_an_order_the_query_never_returns(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The negative direction: canonicalizing must not make matching unconditional.

    The row here is a well-formed order in the broker's own encoding — just a
    different order. It must not be mistaken for the submitted one.
    """
    _install_futures_recorder(monkeypatch, row_odno=_foreign_row_odno)

    run = probe_p5(_args(visibility_timeout_s=0.05))

    assert run.measurements["B_broker_query_consistency_candidate"]["n"] == 0
    assert run.measurements["censored_trials"] == 1
    assert "never appeared" in run.errors[0]


def test_p2_confirms_its_odnos_against_space_padded_rows(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """P-2's set intersection was empty for every run; it now identifies both sends."""
    _install_futures_recorder(monkeypatch)

    run = probe_p2(_args(probe_id="P-2"))

    assert run.measurements["distinct_odno_count"] == 2
    assert run.measurements["odno_confirmed_in_query"] == ["762", "763"]
    assert run.measurements["verdict"].startswith("NO_DEDUP")


def test_p8_sees_both_legs_live_across_the_two_encodings(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """A raw compare finds neither leg and reports zero coexistence.

    That is the fail-open direction for ``B_protective_request_complete``: it would
    claim an atomic replace the probe never observed.
    """
    _install_futures_recorder(monkeypatch)

    run = probe_p8(_args(probe_id="P-8", visibility_timeout_s=0.05))

    assert run.measurements["replace_issues_new_odno"] is True
    assert run.measurements["replace_rejected"] is False
    assert run.measurements["coexistence_ms"] > 0.0


def test_pfqp_finds_its_own_row_after_the_cancel(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """A permanently unmatched row reads as "no late events" — an honest-negative trap."""
    _install_futures_recorder(monkeypatch)

    run = probe_pfqp(_args(probe_id="P-FQP"))

    assert run.measurements["B_final_quantity_proof_candidate"]["n"] == 1
    readings = [o for o in run.observations if "reading_remaining" in o]
    assert readings and readings[0]["reading_remaining"] == 0


def test_nmpr_matches_both_arm_rows_and_reads_the_echo(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Unmatched rows silently downgrade every echo verdict to UNKNOWN.

    With both rows found the probe can answer from the broker's echoed fields
    instead of from its own comparison bug.
    """
    _install_futures_recorder(monkeypatch)

    run = probe_nmpr_ab(_args(probe_id="P-NMPR"))

    assert run.measurements["arm_a_row"] is not None
    assert run.measurements["arm_b_row"] is not None
    assert run.measurements["query_echoes_quote_fields"] == ["nmpr_type_cd"]
    assert run.measurements["verdict"].startswith("BOTH_ACCEPTED, ECHO_PRESENT")


# ---------------------------------------------------------------------------
# the artifact record — the asymmetry is evidence, not just a bug
# ---------------------------------------------------------------------------


def test_a_run_records_both_wire_encodings_verbatim(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The artifact carries the disagreement, with the padding intact."""
    _install_futures_recorder(monkeypatch)

    record = probe_p5(_args()).measurements[_ODNO_FORMAT_KEY]

    assert record["paired"] is True
    submit = record["submit_response_samples"][0]
    row = record["query_row_samples"][0]
    assert submit["verbatim"] == _SUBMIT_FORM
    assert submit["leading_pad"] == "zero"
    assert row["verbatim"] == _QUERY_ROW_FORM
    assert row["leading_pad"] == "space"
    assert submit["canonical_key"] == row["canonical_key"] == "762"
    assert "P-5-20260731T002112Z" in record["identity_matching"]
    assert "모의투자" in record["scope"]


def test_a_one_sided_observation_is_recorded_rather_than_omitted() -> None:
    """An unpaired record states what is missing; it never disappears."""
    run = ProbeRun(probe_id="P-5", title="t", mode="live", environment="MOCK_VTS")

    record_odno_wire_format(run, [_SUBMIT_FORM], [])

    record = run.measurements[_ODNO_FORMAT_KEY]
    assert record["paired"] is False
    assert "not observed side by side" in record["incomplete"]


def test_a_paired_record_is_not_overwritten_by_a_later_one_sided_call() -> None:
    """Probes call the recorder from inside poll loops; the paired sample must hold."""
    run = ProbeRun(probe_id="P-5", title="t", mode="live", environment="MOCK_VTS")

    record_odno_wire_format(run, [_SUBMIT_FORM], [{"odno": _QUERY_ROW_FORM}])
    record_odno_wire_format(run, [], [])

    assert run.measurements[_ODNO_FORMAT_KEY]["paired"] is True


def test_an_unparseable_sample_does_not_destroy_the_record() -> None:
    """A format record is evidence; it must survive the thing it is evidence of."""
    run = ProbeRun(probe_id="P-5", title="t", mode="live", environment="MOCK_VTS")

    record_odno_wire_format(run, ["not-a-number"], [{"odno": _QUERY_ROW_FORM}])

    sample = run.measurements[_ODNO_FORMAT_KEY]["submit_response_samples"][0]
    assert sample["verbatim"] == "not-a-number"
    assert "not numeric" in sample["canonical_key_error"]


# ---------------------------------------------------------------------------
# the wire form is untouched
# ---------------------------------------------------------------------------


def test_cleanup_cancels_with_the_verbatim_zero_padded_odno(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Canonicalization is for comparison only.

    ``ORGN_ODNO`` must carry the accept response's form — the one the broker
    demonstrably accepted a cancel for (``P-5-20260731T002112Z``, ``rt_cd=0``). A
    canonical key on the wire would be an untested request shape.
    """
    calls = _install_futures_recorder(monkeypatch)

    probe_p2(_args(probe_id="P-2"))

    sent = [c["body"]["ORGN_ODNO"] for c in _cancels(calls)]
    assert sent == ["0000000762", "0000000763"]
    assert all(o != odno_key(o) for o in sent)
