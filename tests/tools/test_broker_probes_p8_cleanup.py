"""P-8 cleanup disposition — the defect that voided five correct measurements.

Five P-8 trials ran on 2026-07-31 (``P-8-20260731T015220Z``, ``015259Z``,
``015340Z``, ``015415Z``, ``020121Z``). All five agreed, verbatim:

* the amend was accepted — ``rt_cd=0``, ``모의투자 정정주문이 완료 되었습니다``,
* a NEW ODNO was issued — 3143→3144, 3164→3166, 3180→3181, 3194→3196, 3331→3332,
* the poll loop saw zero coexistence,
* and the cleanup cancel of the ORIGINAL was rejected with
  ``모의투자 정정/취소할 수량이 없습니다``.

The fourth bullet is not a failure. It is the same finding as the second and third
said a different way: the amend took the original's remaining quantity, so there
was nothing left to cancel. The harness recorded it through ``run.error``, and
``ProbeRun.to_dict`` classes any run with a non-empty ``errors`` list as
``NOT_MEASURED`` — so P-8's success condition was wired to void P-8. Five runs, a
funded 모의 account, an open session, and no usable artifact.

Downgrading that rejection is the fix, and the downgrade is where the danger is.
A cancel that really failed leaves an order resting on the book and the operator
has to hear about it, so the downgrade is licensed by exactly one thing: the
open-order surface positively answering, for the whole book, that the order is not
live. Three ways of *not* answering used to pass as an answer, and each has a
negative test below:

**A — a rejection carrying an empty list.** This broker signals an empty result set
with ``rt_cd='7'`` + ``msg_cd='KIOK0560'`` (``P-BAL-20260731T114344Z``), not with
``rt_cd=0`` and no rows. A liveness check that ignored ``rt_cd`` read that shape as
"nothing is live".

**B — one page of a paged surface.** ``P-5b-20260731T014917Z`` measured THIS
surface at ``page_size_observed: 15``, ``continuation_supported: true``, and its own
walk hit the ten-page budget still holding a continuation key. Order 16 is not on
page 1, and "not on page 1" is not "not live".

**C — a throttled cancel.** ``초당 거래건수를 초과하였습니다`` means the request never
reached the matching engine, so the order is still there *by construction* and its
liveness is not the question. Consulting the surface at all invites it to answer
the wrong question.

No socket is opened: ``probes_order.http_json`` is replaced by a recorder that
replays the broker behaviour above.
"""

from __future__ import annotations

import argparse
import itertools
from typing import Any

import pytest

from tools.broker_probes import probes_order
from tools.broker_probes.probes_order import (
    _CLEANUP_ATTEMPTS,
    _CLEANUP_CANCELLED,
    _CLEANUP_LIVENESS_UNKNOWN,
    _CLEANUP_NOTHING_TO_CANCEL,
    _CLEANUP_STILL_LIVE,
    _CLEANUP_THROTTLED,
    probe_p8,
)

_ACCOUNT = "1234567890"
_SYMBOL = "A05608"
_LAST_PRICE = "905.20"

#: The rejection the broker returned for every superseded original, verbatim from
#: the five artifacts.
_NO_QTY = "모의투자 정정/취소할 수량이 없습니다."

#: The rejection that ended trial 1's cleanup with order 0000003144 left resting.
_THROTTLED = "초당 거래건수를 초과하였습니다."


class _StubAuth:
    def get_auth_headers(self) -> dict[str, str]:
        return {"authorization": "Bearer stub"}


@pytest.fixture
def futures_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", _ACCOUNT)
    monkeypatch.delenv("KIS_TOKEN_CACHE_DIR", raising=False)


@pytest.fixture(autouse=True)
def no_sleeping(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cleanup retry gap is seconds of real time and buys these tests nothing."""
    monkeypatch.setattr(probes_order.time, "sleep", lambda _s: None)


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "probe_id": "P-8",
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
        "visibility_timeout_s": 0.05,
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


class _Broker:
    """Replays the 2026-07-31 모의 futures behaviour, with the knobs the tests need.

    Default behaviour is exactly what the five artifacts recorded: an amend issues
    a new ODNO, the original stops appearing live, and cancelling the original is
    rejected for want of quantity.

    Args:
        original_stays_live: Keep the amended-away original on the open-order
            surface with ``qty>0``. The case the fix must NOT downgrade — the order
            really would still be resting.
        listing_mode: How the open-order surface answers. ``"ok"`` answers
            normally; ``"rt_cd_reject_empty_rows"`` is scenario A;
            ``"no_output1"`` omits the list entirely; ``"keys_stall"`` hands back a
            continuation key that never advances; ``"empty_page_with_keys"`` hands
            back an empty page that still carries a continuation key.
        page_size: Rows per page. Anything smaller than the live set makes the
            surface paged, which is scenario B.
        extra_live: Synthetic live orders the probe did not create, so a paged
            walk has something to page THROUGH.
        throttle_cancels: 1-based indices of cancel calls to reject with the
            per-second throttle. Trial 1 of the campaign was ``{2}`` — the cancel of
            the still-live NEW order, which is what left 0000003144 on the book.
        throttle_is_coded: Pair the throttle with ``msg_cd='EGW00201'``, the code
            ``is_rate_limited`` recognises. ``False`` serves the Korean sentence
            alone, which is all the campaign artifact recorded.
        amend_keeps_odno: The amend rests under the SAME order number, so the probe
            records one ODNO twice.
    """

    def __init__(
        self,
        *,
        original_stays_live: bool = False,
        listing_mode: str = "ok",
        page_size: int = 100,
        extra_live: int = 0,
        throttle_cancels: frozenset[int] = frozenset(),
        throttle_is_coded: bool = True,
        amend_keeps_odno: bool = False,
    ) -> None:
        self.original_stays_live = original_stays_live
        self.listing_mode = listing_mode
        self.page_size = page_size
        self.throttle_cancels = throttle_cancels
        self.throttle_is_coded = throttle_is_coded
        self.amend_keeps_odno = amend_keeps_odno
        self.cancels_seen = 0
        self.calls: list[dict[str, Any]] = []
        self._numbers = itertools.count(3143)
        self._live: set[str] = {str(9000 + i).rjust(10, "0") for i in range(extra_live)}
        self._superseded: set[str] = set()

    def _next_odno(self) -> str:
        return str(next(self._numbers)).rjust(10, "0")

    def _all_rows(self) -> list[dict[str, str]]:
        live = set(self._live)
        if self.original_stays_live:
            live |= self._superseded
        # Descending, the broker's own SORT_SQN='DS' order — so the order placed
        # first lands on the LAST page, which is what makes scenario B bite.
        return [
            {
                "odno": odno.lstrip("0").rjust(11),  # space-padded, as observed
                "pdno": _SYMBOL,
                "ord_qty": "1",
                "tot_ccld_qty": "0",
                "qty": "1",
            }
            for odno in sorted(live, reverse=True)
        ]

    def __call__(
        self,
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
        self.calls.append(
            {"url": url, "method": method, "body": body, "params": params or {}}
        )
        if "quotations/inquire-price" in url:
            return 200, {"rt_cd": "0", "output1": {"futs_prpr": _LAST_PRICE}}, 1.0, "{}"
        if "trading/inquire-ccnl" in url:
            return self._inquire(params or {})
        if "trading/order-rvsecncl" in url:
            return self._rvsecncl(body)
        if url.endswith("trading/order"):
            odno = self._next_odno()
            self._live.add(odno)
            return 200, {"rt_cd": "0", "output": {"ODNO": odno}}, 1.0, "{}"
        raise AssertionError(f"unexpected probe URL: {url}")

    def _inquire(
        self, params: dict[str, Any]
    ) -> tuple[int, dict[str, Any], float, str]:
        if self.listing_mode == "no_output1":
            return 200, {"rt_cd": "1", "msg1": "조회 실패"}, 1.0, "{}"
        if self.listing_mode == "rt_cd_reject_empty_rows":
            # Scenario A, in this broker's own empty-set notation.
            payload = {
                "rt_cd": "7",
                "msg_cd": "KIOK0560",
                "msg1": "조회할 내용이 없습니다",
                "output1": [],
            }
            return 200, payload, 1.0, str(payload)
        if self.listing_mode == "keys_stall":
            return (
                200,
                {"rt_cd": "0", "output1": self._all_rows(), "ctx_area_nk200": "1"},
                1.0,
                "{}",
            )
        if self.listing_mode == "empty_page_with_keys":
            # The broker says "more follows" while handing back an empty page —
            # a shape never observed on this surface (P-5b walked ten full
            # pages). The walk must refuse rather than call the book complete.
            return (
                200,
                {"rt_cd": "0", "output1": [], "ctx_area_nk200": "1"},
                1.0,
                "{}",
            )
        rows = self._all_rows()
        cursor = int(params.get("CTX_AREA_NK200") or 0)
        page = rows[cursor : cursor + self.page_size]
        payload: dict[str, Any] = {"rt_cd": "0", "output1": page}
        if cursor + self.page_size < len(rows):
            payload["ctx_area_nk200"] = str(cursor + self.page_size)
        return 200, payload, 1.0, "{}"

    def _rvsecncl(self, body: dict[str, Any]) -> tuple[int, dict[str, Any], float, str]:
        origin = str(body.get("ORGN_ODNO", ""))
        if body.get("RVSE_CNCL_DVSN_CD") == "01":
            # The amend consumes the original and rests under a new number, unless
            # this broker amends in place.
            if self.amend_keeps_odno:
                new_odno = origin
            else:
                self._live.discard(origin)
                self._superseded.add(origin)
                new_odno = self._next_odno()
                self._live.add(new_odno)
            return (
                200,
                {
                    "rt_cd": "0",
                    "msg1": "모의투자 정정주문이 완료 되었습니다.",
                    "output": {"ODNO": new_odno},
                },
                1.0,
                "{}",
            )
        self.cancels_seen += 1
        if self.cancels_seen in self.throttle_cancels:
            payload = {"rt_cd": "1", "msg1": _THROTTLED}
            if self.throttle_is_coded:
                payload["msg_cd"] = "EGW00201"
            return 200, payload, 1.0, str(payload)
        if origin not in self._live:
            return 200, {"rt_cd": "1", "msg1": _NO_QTY}, 1.0, "{}"
        self._live.discard(origin)
        return (
            200,
            {"rt_cd": "0", "msg1": "모의투자 취소주문이 완료 되었습니다."},
            1.0,
            "{}",
        )


def _install(monkeypatch: pytest.MonkeyPatch, broker: _Broker) -> _Broker:
    monkeypatch.setattr(probes_order, "http_json", broker)
    monkeypatch.setattr(
        "shared.kis.auth.KISAuthManager", lambda *a, **k: _StubAuth(), raising=True
    )
    return broker


def _cancel_bodies(broker: _Broker) -> list[dict[str, Any]]:
    return [
        c["body"]
        for c in broker.calls
        if "trading/order-rvsecncl" in c["url"]
        and c["body"].get("RVSE_CNCL_DVSN_CD") == "02"
    ]


def _inquiries_after_first_cancel(broker: _Broker) -> int:
    """Open-order reads issued once cleanup had begun."""
    seen_cancel = False
    count = 0
    for call in broker.calls:
        if (
            "trading/order-rvsecncl" in call["url"]
            and call["body"].get("RVSE_CNCL_DVSN_CD") == "02"
        ):
            seen_cancel = True
        elif seen_cancel and "trading/inquire-ccnl" in call["url"]:
            count += 1
    return count


# ---------------------------------------------------------------------------
# The defect: a correct measurement demoted to NOT_MEASURED
# ---------------------------------------------------------------------------


def test_the_campaign_run_now_produces_a_measured_artifact(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Replay of the five 2026-07-31 trials, end to end.

    Every one of them produced this exact sequence and every one of them was
    demoted. The assertion that matters is ``provenance_class``: the campaign
    README could only cite those artifacts "with the reason attached", which is
    what a NOT_MEASURED artifact costs.
    """
    _install(monkeypatch, _Broker())

    run = probe_p8(_args())

    assert run.measurements["replace_issues_new_odno"] is True
    assert run.measurements["replace_rejected"] is False
    assert run.errors == []
    assert run.to_dict()["provenance_class"] == "MEASURED"


def test_the_superseded_original_is_recorded_as_evidence_not_as_a_failure(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The rejection answers the question the poll loop could not resolve.

    ``coexistence_ms`` is bounded below by the poll granularity — 1100 ms in the
    campaign. A broker that refuses to cancel the original *while a verified walk
    of the whole book reports no live row for it* has stated the quantity is gone,
    which is a stronger statement than any 1100 ms-resolution poll can make.
    """
    _install(monkeypatch, _Broker())

    run = probe_p8(_args())

    assert run.measurements["original_not_cancellable_after_amend"] is True
    dispositions = list(run.measurements["cleanup_dispositions"].values())
    assert dispositions[0] == _CLEANUP_NOTHING_TO_CANCEL
    assert dispositions[1] == _CLEANUP_CANCELLED
    downgraded = [
        o
        for o in run.observations
        if o.get("disposition") == _CLEANUP_NOTHING_TO_CANCEL
    ]
    assert downgraded and downgraded[0]["msg"] == _NO_QTY
    assert downgraded[0]["liveness_evidence"]["outcome"] == "COMPLETE_WALK"


def test_the_measurement_names_no_cause_and_declares_the_fill_confound(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """A fill produces the identical observation, and P-8 never asks.

    The field states the structural fact — the original was not cancellable — and
    the note carries the alternative explanation rather than the field name
    asserting a mechanism the probe did not establish.
    """
    _install(monkeypatch, _Broker())

    run = probe_p8(_args())

    assert "original_quantity_consumed_by_amend" not in run.measurements
    note = run.measurements["amend_consumption_note"]
    assert "A fill produces the SAME observation" in note
    assert "names no cause" in note or "names no cause" in note.replace("  ", " ")


def test_the_verdict_requires_the_amend_to_have_been_accepted(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Without an accepted amend and a new ODNO there is nothing to attribute to.

    An original that is simply gone — filled, or cancelled out of band — must not
    read as replace evidence, so the conjunction is checked rather than inferred
    from the cleanup disposition alone.
    """
    from tools.broker_probes.probes_order import _original_not_cancellable

    dispositions = {"0000003143": _CLEANUP_NOTHING_TO_CANCEL}
    odnos = ["0000003143", "0000003144"]

    assert (
        _original_not_cancellable(
            odnos, dispositions, amend_accepted=True, new_odno="0000003144"
        )
        is True
    )
    assert (
        _original_not_cancellable(
            odnos, dispositions, amend_accepted=False, new_odno="0000003144"
        )
        is None
    )
    assert (
        _original_not_cancellable(odnos, dispositions, amend_accepted=True, new_odno="")
        is None
    )


def test_the_two_liveness_consumers_get_separate_polarity_notes(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The 2026-08-01 fail-closed argument is scoped to ``coexistence_ms``.

    Cleanup reads the same ``qty>0`` predicate with the polarity reversed — there a
    missing live row silences an error — so one shared note would have carried a
    safety argument into a consumer it does not hold for.
    """
    _install(monkeypatch, _Broker())

    run = probe_p8(_args())

    coexistence = run.measurements["liveness_predicate_note"]
    cleanup = run.measurements["cleanup_liveness_note"]
    assert "SCOPED TO coexistence_ms" in coexistence
    assert "OPPOSITE polarity" in cleanup
    assert "fail-OPEN" in cleanup


# ---------------------------------------------------------------------------
# A / B / C — the ways of not answering that used to pass as an answer
# ---------------------------------------------------------------------------


def test_scenario_a_a_rejection_carrying_an_empty_list_is_not_an_answer(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """``rt_cd='7'`` + ``KIOK0560`` + ``output1: []`` must not read as "nothing live".

    That is this broker's empty-result-set notation (``P-BAL-20260731T114344Z``),
    and a check that looked only at ``output1`` would have taken a rejection as a
    clean bill of health for a resting order.
    """
    _install(
        monkeypatch,
        _Broker(original_stays_live=True, listing_mode="rt_cd_reject_empty_rows"),
    )

    run = probe_p8(_args())

    assert run.errors, "a rejection response must never clear a live order"
    dispositions = run.measurements["cleanup_dispositions"]
    assert _CLEANUP_NOTHING_TO_CANCEL not in dispositions.values()
    assert _CLEANUP_LIVENESS_UNKNOWN in dispositions.values()
    evidence = [o for o in run.observations if "liveness_evidence" in o]
    assert evidence[0]["liveness_evidence"]["outcome"] == "NOT_A_POSITIVE_ANSWER"
    assert evidence[0]["liveness_evidence"]["rt_cd"] == "7"


def test_scenario_b_an_order_on_page_two_is_not_missing(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """A single-page read of a paged surface is a fail-open liveness check.

    ``P-5b-20260731T014917Z`` measured this surface at 15 rows per page with
    continuation support. Here the still-live original sits on page 2 and the page
    budget is one, so the walk cannot see the whole book — and refuses to answer
    rather than reporting the order absent.
    """
    _install(monkeypatch, _Broker(original_stays_live=True, page_size=1))

    run = probe_p8(_args(max_pages=1))

    assert run.errors, "a truncated walk must not clear a live order"
    dispositions = run.measurements["cleanup_dispositions"]
    assert _CLEANUP_NOTHING_TO_CANCEL not in dispositions.values()
    evidence = [o for o in run.observations if "liveness_evidence" in o]
    assert (
        evidence[0]["liveness_evidence"]["outcome"]
        == "PAGE_BUDGET_EXHAUSTED_BOOK_INCOMPLETE"
    )


def test_scenario_b_control_the_walk_does_cross_pages_when_it_may(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The guard must not degrade into "never answer".

    Same paged surface, same page size, budget raised: the superseded original is
    genuinely absent, the walk crosses the pages holding the other live orders and
    reaches the end of the book, and the downgrade happens on real evidence.
    """
    broker = _install(monkeypatch, _Broker(page_size=1, extra_live=2))

    run = probe_p8(_args(max_pages=10))

    downgraded = [
        o
        for o in run.observations
        if o.get("disposition") == _CLEANUP_NOTHING_TO_CANCEL
    ]
    assert downgraded, "an honest absence must still downgrade"
    evidence = downgraded[0]["liveness_evidence"]
    assert evidence["outcome"] == "COMPLETE_WALK"
    assert evidence["pages_walked"] > 1
    assert broker.page_size == 1


def test_an_empty_page_with_a_continuation_key_is_not_a_complete_walk(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The broker's "more follows" signal outranks a row-count heuristic.

    An empty page carrying a continuation key has never been observed on this
    surface (P-5b walked ten full pages). Treating it as the end of the book
    would clear an order resting on a later page — the walk refuses instead.
    """
    _install(
        monkeypatch,
        _Broker(original_stays_live=True, listing_mode="empty_page_with_keys"),
    )

    run = probe_p8(_args())

    assert (
        run.errors
    ), "an empty page with continuation keys must not clear a live order"
    dispositions = run.measurements["cleanup_dispositions"]
    assert _CLEANUP_NOTHING_TO_CANCEL not in dispositions.values()
    assert _CLEANUP_LIVENESS_UNKNOWN in dispositions.values()
    evidence = [o for o in run.observations if "liveness_evidence" in o]
    assert (
        evidence[0]["liveness_evidence"]["outcome"]
        == "EMPTY_PAGE_WITH_CONTINUATION_KEY"
    )


def test_a_continuation_key_that_stalls_is_not_an_answer(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Keys that stop advancing mean the walk is not progressing through the book."""
    _install(monkeypatch, _Broker(original_stays_live=True, listing_mode="keys_stall"))

    run = probe_p8(_args())

    assert run.errors
    evidence = [o for o in run.observations if "liveness_evidence" in o]
    assert (
        evidence[0]["liveness_evidence"]["outcome"]
        == "CONTINUATION_KEYS_DID_NOT_ADVANCE"
    )


def test_scenario_c_a_throttled_cancel_never_consults_liveness(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The order is still resting by construction, so liveness is the wrong question.

    Asking anyway lets the surface answer it — possibly wrongly — and a
    ``NOTHING_TO_CANCEL`` reached that way would clear an order the broker never
    even looked at.
    """
    broker = _install(
        monkeypatch,
        _Broker(throttle_cancels=frozenset(range(1, _CLEANUP_ATTEMPTS * 4))),
    )

    run = probe_p8(_args())

    assert _inquiries_after_first_cancel(broker) == 0
    dispositions = run.measurements["cleanup_dispositions"]
    assert _CLEANUP_NOTHING_TO_CANCEL not in dispositions.values()
    assert set(dispositions.values()) == {_CLEANUP_THROTTLED}
    assert run.errors and all("may still be resting" in e for e in run.errors)


def test_an_uncoded_throttle_still_fails_closed(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """``is_rate_limited`` keys on 429/EGW00201, and the campaign saw only the 문언.

    So a throttle carrying the Korean sentence alone is NOT recognised as one. That
    is deliberate — the recognition rule is the repo's single measured definition
    and widening it here would be invention — and the fallback has to be safe: the
    liveness walk finds the order live, the cancel is retried, and the operator is
    told. What must never happen is a silent downgrade.
    """
    _install(
        monkeypatch,
        _Broker(
            original_stays_live=True,
            throttle_cancels=frozenset(range(1, _CLEANUP_ATTEMPTS * 4)),
            throttle_is_coded=False,
        ),
    )

    run = probe_p8(_args())

    dispositions = run.measurements["cleanup_dispositions"]
    assert _CLEANUP_NOTHING_TO_CANCEL not in dispositions.values()
    assert _CLEANUP_STILL_LIVE in dispositions.values()
    assert run.errors


# ---------------------------------------------------------------------------
# The other direction: the fix must not swallow a real cleanup failure
# ---------------------------------------------------------------------------


def test_the_same_rejection_stays_an_error_when_the_order_is_still_live(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Identical broker sentence, opposite disposition.

    This is why the downgrade is keyed to the open-order surface and not to the
    message. A harness that pattern-matched ``정정/취소할 수량이 없습니다`` would
    accept it from an order that really is resting, and the operator would never be
    told. The order here stays visible with ``qty>0`` throughout.
    """
    _install(monkeypatch, _Broker(original_stays_live=True))

    run = probe_p8(_args())

    assert run.errors, "a live order that would not cancel must be reported"
    assert "may still be resting" in run.errors[0]
    assert run.to_dict()["provenance_class"] == "NOT_MEASURED"
    assert _CLEANUP_STILL_LIVE in run.measurements["cleanup_dispositions"].values()
    assert run.measurements["original_not_cancellable_after_amend"] is None


def test_an_unreadable_open_order_surface_counts_as_live(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Unknown liveness is treated as live — fail-closed.

    The listing is the only evidence for the downgrade, so when it does not answer
    there is no evidence, and "no evidence" must not read as "nothing to cancel".
    """
    _install(monkeypatch, _Broker(listing_mode="no_output1"))

    run = probe_p8(_args())

    assert run.errors
    assert (
        _CLEANUP_LIVENESS_UNKNOWN in run.measurements["cleanup_dispositions"].values()
    )
    assert run.measurements["original_not_cancellable_after_amend"] is None


def test_a_throttled_cancel_is_retried_instead_of_abandoned(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Trial 1 of the campaign left order 0000003144 resting on the book.

    The throttled call in that trial was the cancel of the NEW order, which was
    genuinely live, so the retry is the only thing that can clear it.
    """
    broker = _install(monkeypatch, _Broker(throttle_cancels=frozenset({2})))

    run = probe_p8(_args())

    assert run.errors == []
    dispositions = run.measurements["cleanup_dispositions"]
    new_odno = list(dispositions)[1]
    assert dispositions[new_odno] == _CLEANUP_CANCELLED
    attempts = [b["ORGN_ODNO"] for b in _cancel_bodies(broker)]
    assert attempts.count(new_odno) == 2, "the throttled cancel must be retried"
    final = [o for o in run.observations if o.get("cleanup_cancel") == new_odno]
    assert len(final) == 1 and final[0]["attempt"] == 2


# ---------------------------------------------------------------------------
# Guarantees the fix must not disturb
# ---------------------------------------------------------------------------


def test_the_cancel_still_sends_the_verbatim_zero_padded_odno(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Canonicalization is for comparison only and must not reach a request body.

    The retry loop and the liveness walk both canonicalize; ``ORGN_ODNO`` still
    carries the accept response's own form, which is the form the broker
    demonstrably accepts (``P-5-20260731T002112Z`` cleanup, ``rt_cd=0``).
    """
    broker = _install(monkeypatch, _Broker())

    probe_p8(_args())

    sent = [b["ORGN_ODNO"] for b in _cancel_bodies(broker)]
    assert sent, "the probe must clean up after itself"
    assert all(len(o) == 10 and o.startswith("0") for o in sent)


def test_an_amend_that_keeps_the_number_is_cancelled_once(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """One order, recorded twice, must not become two cancels or one lost outcome.

    Keying the disposition map by ODNO means a repeat would overwrite the first
    outcome, and sending the second cancel would be a request for work already
    done.
    """
    broker = _install(monkeypatch, _Broker(amend_keeps_odno=True))

    run = probe_p8(_args())

    assert len(_cancel_bodies(broker)) == 1
    assert len(run.measurements["cleanup_dispositions"]) == 1
    collapsed = [
        o for o in run.observations if "cleanup_duplicate_odnos_collapsed" in o
    ]
    assert collapsed and collapsed[0]["cleanup_duplicate_odnos_collapsed"] == 1
