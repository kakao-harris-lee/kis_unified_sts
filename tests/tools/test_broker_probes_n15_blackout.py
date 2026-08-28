"""N-15 token blackout — why four runs produced four empty artifacts.

``N-15-20260729T063312Z``, ``063609Z``, ``064035Z`` and ``064922Z`` all have
``duration_s: 0.0``, ``credentials: {}``, ``observations: []`` and
``measurements: {}``. Three of them carry one line::

    ValueError: Token issue failed: {'error_code': 'EGW00133',
      'error_description': '접근토큰 발급 잠시 후 다시 시도하세요(1분당 1회)'}

That is the probe's own first statement — ``auth.get_token()``, "ensure we start
holding a valid token" — raising. ``run.py`` catches it, builds a *fresh* ProbeRun
to record the failure, and the populated one is discarded along with everything the
probe had already observed. So a refusal to issue a token, which is precisely the
phenomenon N-15 exists to measure, destroyed the measurement instead of being it.

The session timeline the four artifacts and ``P-15-20260729T063207Z`` fix between
them, all UTC:

===========  ==========================================================
06:32:07     P-15 issues a token — 200, ``expires_in`` 86400
06:32:12     P-15 reissues 5 s later — 403 EGW00133, limit binds
06:33:12     N-15 #1 — EGW00133
06:36:09     N-15 #2 — RemoteDisconnected
06:40:35     N-15 #3 — EGW00133, 265 s after the previous attempt
06:49:22     N-15 #4 — EGW00133, 527 s after the previous attempt
===========  ==========================================================

The last two rows do the real work. Both refusals came after gaps far longer than
the documented minute, so the literal "1분당 1회" reading does not explain them —
and neither does "each rejected attempt restarts the cooldown", the obvious
alternative, because 527 s of quiet did not clear it either. Whatever binds here,
it is not what the error string says, and a 180 s timeout could never have found
it.

These tests pin the three harness changes that follow: the probe survives a refusal
at t=0, a censored run still carries its lower bound, and the reissue window is
kept distinct from the question that actually feeds ``B_egress_hard_fence`` —
whether the credential the process ALREADY holds still works.

No socket is opened.
"""

from __future__ import annotations

import argparse
import time
from typing import Any

import pytest

from tools.broker_probes import probes_auth
from tools.broker_probes.probes_auth import (
    _HELD_OK,
    _HELD_REJECTED,
    _HELD_UNKNOWN,
    _backoff_schedule,
    probe_n15,
)

_SYMBOL = "A05608"

#: The refusal body, verbatim from the three artifacts.
_EGW00133 = {
    "error_code": "EGW00133",
    "error_description": "접근토큰 발급 잠시 후 다시 시도하세요(1분당 1회)",
}


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "probe_id": "N-15",
        "asset": "futures",
        "symbol": _SYMBOL,
        "confirm": True,
        "margin_pct": 50.0,
        "token_cache_dir": None,
        "out_dir": None,
        "note": None,
        "trials": 1,
        "inter_trial_s": 0.0,
        "reissue_gap_s": 5.0,
        "reissue_poll_s": 10.0,
        "blackout_backoff_factor": 2.0,
        "blackout_backoff_max_s": 120.0,
        "blackout_max_attempts": 4,
        "blackout_observe_only": False,
        "blackout_timeout_s": 900.0,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", "1234567890")
    monkeypatch.delenv("KIS_TOKEN_CACHE_DIR", raising=False)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``sleep`` advance a simulated offset instead of costing wall time.

    The schedule under test spans minutes on purpose. Real monotonic time still
    runs underneath, so nothing goes backwards; the offset only jumps it forward by
    exactly what the probe asked to sleep, which is what makes
    ``gap_since_prev_attempt_s`` assertable at all.
    """
    offset = [0.0]
    real = time.monotonic

    def _sleep(seconds: float) -> None:
        offset[0] += seconds

    monkeypatch.setattr(time, "sleep", _sleep)
    monkeypatch.setattr(time, "monotonic", lambda: real() + offset[0])


class _StubAuth:
    """Stands in for ``KISAuthManager`` — records what the probe asked of it.

    Args:
        token: One token for every trial.
        tokens: Per-trial sequence; ``None`` in a slot makes that trial's initial
            acquisition fail, which is how a PRE_EXISTING_REFUSAL trial is staged
            alongside a clean one.
    """

    def __init__(
        self,
        *,
        token: str | None = "held-token",
        tokens: list[str | None] | None = None,
    ) -> None:
        self._tokens = list(tokens) if tokens is not None else None
        self._token = token
        self.invalidated = 0

    def get_token(self) -> str:
        if self._tokens is not None:
            value = self._tokens.pop(0) if self._tokens else None
        else:
            value = self._token
        if value is None:
            raise ValueError(f"Token issue failed: {_EGW00133}")
        return value

    def invalidate(self) -> None:
        self.invalidated += 1


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    auth: _StubAuth | None = None,
    issue_results: list[bool] | None = None,
    held: tuple[int, dict[str, Any]] = (200, {"rt_cd": "0"}),
) -> dict[str, Any]:
    """Wire the token endpoint, the held-token read and the auth manager.

    Args:
        issue_results: One entry per reissue attempt — ``True`` grants a token.
            Runs past the end of the list keep refusing, which is the censored
            case.
        held: ``(http_status, body)`` the authenticated read returns.
    """
    auth = auth or _StubAuth()
    grants = list(issue_results or [])
    state: dict[str, Any] = {"auth": auth, "issue_calls": 0, "held_calls": 0}

    def _issue(_session: Any, _creds: Any) -> tuple[int, dict[str, Any], float, str]:
        idx = state["issue_calls"]
        state["issue_calls"] += 1
        if idx < len(grants) and grants[idx]:
            return 200, {"access_token": "fresh", "expires_in": 86400}, 1.0, "{}"
        return 403, dict(_EGW00133), 1.0, str(_EGW00133)

    def _http(
        _session: Any,
        _method: str,
        _url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> tuple[int, dict[str, Any], float, str]:
        state["held_calls"] += 1
        state["last_held_headers"] = headers
        status, body = held
        return status, dict(body), 1.0, str(body)

    monkeypatch.setattr(probes_auth, "_issue_token_raw", _issue)
    monkeypatch.setattr(probes_auth, "http_json", _http)
    monkeypatch.setattr(
        "shared.kis.auth.KISAuthManager", lambda *a, **k: auth, raising=True
    )
    return state


def _rejections(run: Any) -> list[dict[str, Any]]:
    for obs in run.observations:
        if "rejections" in obs:
            return obs["rejections"]
    return []


# ---------------------------------------------------------------------------
# The backoff schedule
# ---------------------------------------------------------------------------


def test_the_schedule_widens_and_then_caps() -> None:
    """15 s → 30 → 60 → 120 → 120…, twelve calls reaching ~17 min.

    The old fixed 5 s poll spent 36 calls on a shared app key inside 180 s, against
    a refusal since observed to outlast 8.8 min. Reach mattered more than
    resolution and the budget had to come down, not up.
    """
    schedule = _backoff_schedule(
        _args(
            reissue_poll_s=15.0, blackout_max_attempts=12, blackout_backoff_max_s=120.0
        )
    )

    assert schedule[:4] == [15.0, 30.0, 60.0, 120.0]
    assert set(schedule[4:]) == {120.0}
    assert sum(schedule) > 8.8 * 60


def test_factor_one_reproduces_the_old_fixed_interval_poll() -> None:
    """An escape hatch back to the previous behaviour, for comparison runs."""
    schedule = _backoff_schedule(
        _args(reissue_poll_s=5.0, blackout_backoff_factor=1.0, blackout_max_attempts=4)
    )

    assert schedule == [5.0, 5.0, 5.0]


def test_a_single_attempt_sleeps_not_at_all() -> None:
    """There is no gap after the last attempt — the schedule is gaps, not attempts."""
    assert _backoff_schedule(_args(blackout_max_attempts=1)) == []


# ---------------------------------------------------------------------------
# The probe survives the refusal that used to kill it
# ---------------------------------------------------------------------------


def test_a_refusal_at_t0_is_recorded_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """The exact failure of three of the four 2026-07-29 artifacts.

    ``get_token()`` raises, and the old probe let it escape to ``run.py``, which
    rebuilt a blank ProbeRun. A blackout already in progress is the phenomenon, not
    an obstacle to observing it.
    """
    _install(monkeypatch, auth=_StubAuth(token=None), issue_results=[False, True])

    run = probe_n15(_args())

    refusals = [o for o in run.observations if o.get("initial_token") == "REFUSED"]
    assert refusals, "the refusal must survive into the artifact"
    assert "EGW00133" in refusals[0]["detail"]
    assert "LOWER bound" in refusals[0]["reading"]
    trial = [o for o in run.observations if "origin" in o][0]
    assert trial["origin"] == "PRE_EXISTING_REFUSAL"


def test_a_pre_existing_refusal_does_not_invalidate_a_token_it_never_got(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """Nothing to invalidate, and unlinking a cache file would only add noise."""
    auth = _StubAuth(token=None)
    _install(monkeypatch, auth=auth, issue_results=[True])

    probe_n15(_args())

    assert auth.invalidated == 0


def test_observe_only_never_invalidates(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """For watching a window that is already open without disturbing the cache."""
    auth = _StubAuth()
    _install(monkeypatch, auth=auth, issue_results=[True])

    probe_n15(_args(blackout_observe_only=True))

    assert auth.invalidated == 0


def test_the_normal_path_still_invalidates(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """The designed measurement is unchanged when a token can be held."""
    auth = _StubAuth()
    _install(monkeypatch, auth=auth, issue_results=[True])

    run = probe_n15(_args())

    assert auth.invalidated == 1
    assert run.errors == []
    assert run.to_dict()["provenance_class"] == "MEASURED"


# ---------------------------------------------------------------------------
# Censoring carries evidence instead of destroying it
# ---------------------------------------------------------------------------


def test_a_censored_run_reports_a_lower_bound_and_stays_not_measured(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """Both halves matter, and they pull in opposite directions.

    The bound has to be there — an empty ``measurements`` object is what the four
    artifacts shipped, and it taught nobody anything. The provenance has to stay
    ``NOT_MEASURED`` — a run that never saw the window close has not measured it,
    and promoting it would be exactly the fail-open move the campaign's approval
    chain exists to prevent.
    """
    _install(monkeypatch, issue_results=[False, False, False, False])

    run = probe_n15(_args())

    bound = run.measurements["reissue_refusal_lower_bound"]
    assert bound is not None
    assert bound["censored_trials"] == 1
    assert bound["completed_trials"] == 0
    assert bound["provenance"].startswith("CENSORED_LOWER_BOUND")
    assert any("CENSORED" in e for e in run.errors)
    assert run.to_dict()["provenance_class"] == "NOT_MEASURED"


def test_an_uncensored_run_reports_no_lower_bound(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """``None``, not a zero — there is no censoring to describe."""
    _install(monkeypatch, issue_results=[True])

    run = probe_n15(_args())

    assert run.measurements["reissue_refusal_lower_bound"] is None


def test_the_gap_that_a_refusal_survived_is_reported(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """The measurement that discriminates the two cooldown models.

    If every rejected attempt restarted the cooldown, a refusal could never outlive
    a gap longer than the cooldown. The 06:49:22Z artifact refused after 527 s of
    quiet, so the model was already in trouble; this field is how a future run says
    so from its own data instead of from an archaeology of timestamps.
    """
    _install(monkeypatch, issue_results=[False, False, False, False])

    run = probe_n15(_args(reissue_poll_s=100.0, blackout_backoff_factor=1.0))

    assert run.measurements["reissue_refusal_survived_gap_s"] >= 100.0
    gaps = [r["gap_since_prev_attempt_s"] for r in _rejections(run)]
    assert gaps[0] == pytest.approx(0.0, abs=1.0)
    assert gaps[1] >= 100.0


def test_the_token_call_budget_is_bounded_and_reported(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """P-13 and the paper fleet share this quota, so the spend is stated."""
    state = _install(monkeypatch, issue_results=[False] * 20)

    run = probe_n15(_args(trials=2, blackout_max_attempts=3))

    assert state["issue_calls"] == 6
    assert run.measurements["token_endpoint_calls_made"] == 6


# ---------------------------------------------------------------------------
# The quantity that actually feeds B_egress_hard_fence
# ---------------------------------------------------------------------------


def test_a_still_accepted_held_token_is_not_an_egress_blackout(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """``invalidate()`` unlinks a local file; it does not revoke anything.

    So a reissue refusal with the previously issued token still authorizing is a
    cooldown, not a window in which the fleet has no credential. The old probe
    could not tell the two apart and would have written the cooldown into
    ``B_egress_hard_fence``.
    """
    _install(monkeypatch, issue_results=[False, True], held=(200, {"rt_cd": "0"}))

    run = probe_n15(_args())

    tally = run.measurements["held_token_usability_samples"]
    assert tally[_HELD_OK] == 1
    assert tally[_HELD_REJECTED] == 0
    assert "not an egress blackout" in run.measurements["interaction_verdict"]


def test_a_rejected_held_token_is_the_hazard(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """No usable credential and no way to get one — the plan §2:68 interaction."""
    _install(
        monkeypatch,
        issue_results=[False, True],
        held=(403, {"msg_cd": "EGW00121", "msg1": "유효하지 않은 토큰입니다"}),
    )

    run = probe_n15(_args())

    assert run.measurements["held_token_usability_samples"][_HELD_REJECTED] == 1


def test_a_throttled_usability_check_is_undetermined_not_rejected(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """A throttled call never reached the authorization check.

    Reading it as a rejection would manufacture an egress blackout out of a rate
    limit — and this probe runs alongside P-13, which exists to cause rate limits.
    """
    _install(
        monkeypatch,
        issue_results=[False, True],
        held=(429, {"msg_cd": "EGW00201", "msg1": "초당 거래건수를 초과하였습니다."}),
    )

    run = probe_n15(_args())

    tally = run.measurements["held_token_usability_samples"]
    assert tally[_HELD_UNKNOWN] == 1
    assert tally[_HELD_REJECTED] == 0


def test_the_held_token_read_carries_the_held_token(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """Asking with a freshly minted token would answer a different question."""
    state = _install(monkeypatch, issue_results=[False, True])

    probe_n15(_args())

    assert state["last_held_headers"]["authorization"] == "Bearer held-token"


def test_a_200_with_a_nonzero_rt_cd_is_undetermined_not_rejected(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """KIS signals plenty of failures as HTTP 200 with ``rt_cd != "0"``.

    An authorization rejection may well arrive in that shape — but so does every
    ordinary business rejection, and no artifact in this campaign has recorded the
    token-rejection code on this surface. Guessing the mapping would let a bad
    symbol read as a dead credential and manufacture an egress blackout, so the
    probe records UNDETERMINED and says so out loud.
    """
    _install(
        monkeypatch,
        issue_results=[False, True],
        held=(200, {"rt_cd": "1", "msg_cd": "APBK0919", "msg1": "종목코드 오류"}),
    )

    run = probe_n15(_args())

    tally = run.measurements["held_token_usability_samples"]
    assert tally[_HELD_UNKNOWN] == 1
    assert tally[_HELD_REJECTED] == 0


def test_the_unreachability_of_rejected_is_declared_in_the_artifact(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """An all-UNDETERMINED tally is not evidence the held token kept working.

    Since REJECTED is asserted only on 401/403, it may be structurally unreachable
    here. A reader who saw ``REJECTED: 0`` without this caveat would draw exactly
    the wrong conclusion, so the caveat travels with the numbers.
    """
    _install(monkeypatch, issue_results=[False, True])

    run = probe_n15(_args())

    note = run.measurements["held_token_rejection_reachability"]
    assert "may be unreachable" in note
    assert "does NOT mean the held token kept working" in note


# ---------------------------------------------------------------------------
# Origin separation — a lower bound must not be summarised as a measurement
# ---------------------------------------------------------------------------


def test_a_pre_existing_trial_is_kept_out_of_the_measured_candidate(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """Its clock starts when the probe noticed, not when the blackout began.

    So its elapsed time UNDER-states the window. Pooling it with a clean
    invalidate→reissue sample drags the candidate down, and the candidate feeds
    ``B_egress_hard_fence`` — a hard maximum, where understating is the fail-open
    direction. Trial 0 here is pre-existing, trial 1 is clean.
    """
    auth = _StubAuth(tokens=[None, "held-token"])
    _install(monkeypatch, auth=auth, issue_results=[True, True])

    run = probe_n15(_args(trials=2))

    assert run.measurements["token_blackout_window_candidate"]["n"] == 1
    bound = run.measurements["pre_existing_refusal_lower_bound_ms"]
    assert bound is not None
    assert len(bound["samples"]) == 1
    assert bound["provenance"].startswith("CENSORED_LOWER_BOUND")
    assert (
        "POST_INVALIDATE trials only"
        in run.measurements["token_blackout_window_candidate_origin"]
    )


def test_no_pre_existing_trial_leaves_the_bound_absent(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """``None``, not an empty summary — there is no censored sample to describe."""
    _install(monkeypatch, issue_results=[True])

    run = probe_n15(_args())

    assert run.measurements["pre_existing_refusal_lower_bound_ms"] is None
    assert run.measurements["token_blackout_window_candidate"]["n"] == 1


def test_the_censored_count_is_not_recovered_by_grepping_error_text(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """An operator note containing the word must not inflate the count.

    The count is taken at the censoring site. Scanning ``run.errors`` for the
    substring was wrong in both directions — an unrelated error mentioning
    CENSORED would have raised it, and rewording the censoring message would have
    silently zeroed it.
    """
    from tools.broker_probes.probes_auth import _refusal_lower_bound

    assert _refusal_lower_bound(0, [1.0], []) is None
    bound = _refusal_lower_bound(2, [1.0], [2.0])
    assert bound is not None
    assert bound["censored_trials"] == 2
    assert bound["completed_trials"] == 1
    assert bound["pre_existing_origin_trials"] == 1


# ---------------------------------------------------------------------------
# The salvage window
# ---------------------------------------------------------------------------


def test_only_a_run_built_inside_the_window_can_be_salvaged() -> None:
    """Otherwise ``_last`` is "the most recent run anywhere in the process".

    A run left behind by an earlier probe — or, in this suite, by an earlier test —
    could then be written out as some later probe's evidence. Resetting at the
    probe call boundary makes a salvaged run provably one that invocation created.
    """
    from tools.broker_probes.common import ProbeRun

    stale = ProbeRun(probe_id="N-15", title="t", mode="live", environment="MOCK_VTS")
    assert ProbeRun.salvage("N-15") is stale

    ProbeRun.reset_salvage()
    assert ProbeRun.salvage("N-15") is None

    fresh = ProbeRun(probe_id="N-15", title="t", mode="live", environment="MOCK_VTS")
    assert ProbeRun.salvage("N-15") is fresh
    assert ProbeRun.salvage("P-8") is None


def test_the_default_timeout_outlasts_the_default_schedule() -> None:
    """The budget and the ceiling have to agree, or one silently truncates the other.

    At the previous 900 s ceiling the 12-call schedule stopped after attempt 10 at
    t=825 s, so the runbook's "12 calls / ~18 min" was arithmetic the code did not
    honour.
    """
    parser = argparse.ArgumentParser()
    probes_auth.add_auth_args(parser)
    defaults = parser.parse_args([])

    schedule = _backoff_schedule(defaults)
    last_attempt_at = sum(schedule)

    assert len(schedule) == defaults.blackout_max_attempts - 1
    assert last_attempt_at == pytest.approx(1065.0)
    assert last_attempt_at < defaults.blackout_timeout_s


def test_without_a_symbol_the_missing_check_is_declared(
    monkeypatch: pytest.MonkeyPatch, auth_env: None, clock: None
) -> None:
    """An explicit skip, never a silent omission.

    Without the authenticated read there is no usable-credential evidence at all,
    and the reissue window must not be read as one. The four 2026-07-29 runs passed
    no ``--symbol`` and said nothing about it.
    """
    state = _install(monkeypatch, issue_results=[False, True])

    run = probe_n15(_args(symbol=""))

    assert any(s["what"] == "held-token usability" for s in run.skips)
    assert state["held_calls"] == 0
    tally = run.measurements["held_token_usability_samples"]
    assert tally[_HELD_UNKNOWN] == 1
    assert tally[_HELD_OK] == 0
