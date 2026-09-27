"""The ``intake_kind: journal`` pacing guard — ``poll_interval_ms +
journal_pass_allowance_ms`` must fit inside the conservative freshness budget
(plan ``docs/plans/2026-09-27-tos-poll-interval-freshness-budget-plan.md`` §2.3,
operator disposition §6.1 2026-09-27; issue #807).

**Why this file exists.** The two halves of the budget live in DIFFERENT config files —
``marketfeed.yaml::poll_interval_ms`` and ``time.yaml``'s VER-002 bounds — and nothing
held them together, so the paper deployment shipped ``poll_interval_ms: 1000`` against a
1000 ms freshness bound with 200 ms of delay bounds and read 7 of 18 rehearsal observations
STALE. Every number this module parametrizes is a concrete input the plan's §2.3 names, so
the guard cannot be "a check that admits what it says it blocks" (the repeated defect shape
recorded in the host memory file ``guards-that-admit-what-they-name.md``).

The arithmetic cases call :func:`~tos_runtime.compose._marketfeed_wiring
._load_config_within_freshness_budget` directly — it is the exact function
``build_tick_scheduler`` calls, and a hermetic loader-level call keeps the parametrized
matrix cheap. :func:`test_boot_refuses_a_journal_pacing_outside_the_budget` and its admitted
twin are the ones that prove the guard is actually ON the boot path (delete the call from
``build_tick_scheduler`` and only those two go red).

Hermetic (D1.4): every file lives under ``tmp_path``; no network, no ambient env.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.compose._marketfeed_wiring import (
    MarketFeedConfigError,
    _load_config_within_freshness_budget,
)
from tos_runtime.marketfeed.time_projection import _DELAY_BOUND_FIELDS
from tos_runtime.time.config import _BOUND_FIELD_BY_KEY, load_time_config

from . import _fixtures as fx
from .test_compose_root import _compose
from .test_marketfeed_intake_kind_wiring import (
    _valid_marketfeed_raw,
    _write_kis_quote_transport_config,
    _write_marketfeed_config_raw,
)
from .test_marketfeed_wiring import _write_critical_input_policy, _write_journal

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: The APPROVED paper values this plan reasons in (``config/tos_runtime/paper/time.yaml``:
#: ``MAX_time_conservative_freshness_age_ms`` 1000, VER-002 L1078 APPROVED 2026-09-04; each
#: of the four delay bounds 50, APPROVED 2026-07-29). Written into the test's own
#: ``time.yaml`` rather than read from the deploy directory so this suite stays hermetic —
#: ``test_deploy_approved_values.py`` is what pins the committed file to these same numbers.
_PAPER_MAX_AGE_MS = 1000
_PAPER_DELAY_BOUND_MS = 50

#: Budget = 1000 - 4*50 = 800 ms. The plan's §2.3 numbers are all stated against this.
_PAPER_BUDGET_MS = _PAPER_MAX_AGE_MS - _PAPER_DELAY_BOUND_MS * len(_DELAY_BOUND_FIELDS)

#: ``TrustworthyTimeConfig`` field name -> the ``time.yaml`` key that fills it. Inverted
#: from the loader's OWN table so the four delay-bound keys below can never drift from the
#: four fields :data:`_DELAY_BOUND_FIELDS` names (the guard reads the fields; the fixture
#: writes the keys; one table maps them).
_DELAY_KEY_BY_FIELD = {field: key for key, field in _BOUND_FIELD_BY_KEY.items()}

#: Sentinel for "the key is absent from the mapping entirely" (distinct from ``None``,
#: which is the still-``null`` named-TBD case).
_MISSING = object()


def _write_paper_shaped_time_yaml(config_dir: Path, **overrides: int) -> None:
    """Re-shape the ``config_dir`` fixture's own ``time.yaml`` to the APPROVED paper bounds.

    Only the freshness bound and the four delay bounds are touched — every other key keeps
    the fixture's value, so a refusal here can only come from the pacing budget.
    """
    path = config_dir / "time.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["MAX_time_conservative_freshness_age_ms"] = _PAPER_MAX_AGE_MS
    for field in _DELAY_BOUND_FIELDS:
        raw[_DELAY_KEY_BY_FIELD[field]] = _PAPER_DELAY_BOUND_MS
    raw.update(overrides)
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _write_journal_marketfeed(
    config_dir: Path, tmp_path: Path, **overrides: Any
) -> Path:
    """Write a valid ``intake_kind: journal`` ``marketfeed.yaml``, with ``overrides``
    applied last (a value of :data:`_MISSING` deletes the key)."""
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "journal.jsonl")
    for key, value in overrides.items():
        if value is _MISSING:
            del raw[key]
        else:
            raw[key] = value
    _write_marketfeed_config_raw(config_dir, raw)
    return config_dir / "marketfeed.yaml"


# ---------------------------------------------------------------------------
# the budget arithmetic — plan §2.3's concrete inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("poll_ms", "allowance_ms", "admitted"),
    [
        # The shipped paper defect (plan §1): 1100 > 800.
        (1000, 100, False),
        # Boundary. The kernel's freshness verdict is `source_age + sum(delay_bounds) >
        # max_age_bound -> STALE` (tos/src/tos/time/predicates.py `freshness_verdict`), so
        # EQUALITY is still FRESH and the guard must admit exactly-the-budget.
        (700, 100, True),
        (701, 100, False),
        # Operator disposition §6.1 (가): the value this plan lands, 300 ms of collector
        # headroom left over.
        (400, 100, True),
    ],
)
def test_journal_pacing_against_the_paper_shaped_budget(
    tmp_path: Path, config_dir: Path, poll_ms: int, allowance_ms: int, admitted: bool
) -> None:
    _write_paper_shaped_time_yaml(config_dir)
    time_config = load_time_config(config_dir / "time.yaml")
    assert (
        time_config.max_time_conservative_freshness_age_ms
        - sum(getattr(time_config, field) for field in _DELAY_BOUND_FIELDS)
        == _PAPER_BUDGET_MS
    ), "fixture assumption: the paper-shaped budget is 800 ms"
    path = _write_journal_marketfeed(
        config_dir,
        tmp_path,
        poll_interval_ms=poll_ms,
        journal_pass_allowance_ms=allowance_ms,
    )

    if admitted:
        config = _load_config_within_freshness_budget(path, time_config)
        assert config.poll_interval_ms == poll_ms
        assert config.journal_pass_allowance_ms == allowance_ms
        return
    with pytest.raises(MarketFeedConfigError, match="paces outside the conservative"):
        _load_config_within_freshness_budget(path, time_config)


@pytest.mark.parametrize("raised_field", _DELAY_BOUND_FIELDS)
@pytest.mark.parametrize(("poll_ms", "admitted"), [(400, True), (650, False)])
def test_raising_any_one_delay_bound_narrows_the_budget(
    tmp_path: Path, config_dir: Path, raised_field: str, poll_ms: int, admitted: bool
) -> None:
    """Plan §2.3's Σ pin, widened to all four terms. With ONE delay bound at 150 instead of
    50 the sum is 300 and the budget 700, so 400 + 100 is still admitted while 650 + 100 =
    750 is refused — and 750 WOULD be admitted against the unraised 800 ms budget. Dropping
    any single term from the guard's sum therefore turns the refused row red for that term's
    parametrization, which is what stops the sum from silently shrinking (the same direction
    ``RuntimeTimeProjection``'s own completeness check refuses to move in).
    """
    _write_paper_shaped_time_yaml(
        config_dir, **{_DELAY_KEY_BY_FIELD[raised_field]: 150}
    )
    time_config = load_time_config(config_dir / "time.yaml")
    path = _write_journal_marketfeed(
        config_dir, tmp_path, poll_interval_ms=poll_ms, journal_pass_allowance_ms=100
    )

    if admitted:
        assert (
            _load_config_within_freshness_budget(path, time_config).poll_interval_ms
            == poll_ms
        )
        return
    with pytest.raises(MarketFeedConfigError, match="paces outside the conservative"):
        _load_config_within_freshness_budget(path, time_config)


def test_the_refusal_message_names_the_three_terms_and_the_collector_headroom(
    tmp_path: Path, config_dir: Path
) -> None:
    """An operator reading only the message must be able to pick a value. Plan §2.3: the
    message names ``poll_interval_ms``, ``journal_pass_allowance_ms``, the budget it is
    measured against, and what would be left for the upstream collector (here: -300 ms).
    """
    _write_paper_shaped_time_yaml(config_dir)
    time_config = load_time_config(config_dir / "time.yaml")
    path = _write_journal_marketfeed(
        config_dir, tmp_path, poll_interval_ms=1000, journal_pass_allowance_ms=100
    )

    with pytest.raises(MarketFeedConfigError) as excinfo:
        _load_config_within_freshness_budget(path, time_config)
    message = str(excinfo.value)
    assert "poll_interval_ms=1000" in message
    assert "journal_pass_allowance_ms=100" in message
    assert "MAX_time_conservative_freshness_age_ms=1000" in message
    assert "sum(delay_bounds)=200" in message
    assert "800 ms" in message
    assert "-300 ms of headroom" in message


# ---------------------------------------------------------------------------
# the new key itself — required XOR forbidden, and positive
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [_MISSING, None, "TBD", "", 0, -1, True])
def test_journal_pass_allowance_is_required_and_positive_for_journal(
    tmp_path: Path, config_dir: Path, value: Any
) -> None:
    """Plan §2.3's last refusal row. ``"TBD"``/``""``/``True`` are refused by
    ``_require_int``'s own type check (a placeholder string is not an int, and ``bool`` is
    excluded explicitly), missing/``null`` by the required-for-journal check, and ``0``/
    negatives by the positivity check — an allowance of zero claims a pass that costs no
    time, which would hand the whole budget back to ``poll_interval_ms``."""
    _write_paper_shaped_time_yaml(config_dir)
    time_config = load_time_config(config_dir / "time.yaml")
    path = _write_journal_marketfeed(
        config_dir, tmp_path, journal_pass_allowance_ms=value
    )

    with pytest.raises(MarketFeedConfigError, match="journal_pass_allowance_ms"):
        _load_config_within_freshness_budget(path, time_config)


def test_kis_quote_is_not_subject_to_the_pacing_guard(
    tmp_path: Path, config_dir: Path
) -> None:
    """Plan §0-3 / §2.3's last row: ``kis_quote`` + ``poll_interval_ms: 1000`` is ADMITTED
    against the very budget that refuses the same number for ``journal``. That adapter
    stamps ``as_of_ms`` from the SAME cached pre-pass time reading the scheduler's own
    ``now_ms`` comes from (``TrustworthyTimeService.wall_clock_now()`` returns the snapshot
    cached by the last ``evaluate()``, not a fresh reading), so its ``source_age`` is always
    0 and the phase term does not apply — a property of the shared cache, not a measured
    short path; the adapter's real HTTP round trip is never measured (issue #810). And the
    same key is its HTTP request spacing, which the 모의 quote rate limit (1–2 rps, probe
    P-13) forbids shrinking below 800 ms."""
    _write_paper_shaped_time_yaml(config_dir)
    time_config = load_time_config(config_dir / "time.yaml")
    path = _write_journal_marketfeed(
        config_dir,
        tmp_path,
        intake_kind="kis_quote",
        journal_path=_MISSING,
        journal_pass_allowance_ms=_MISSING,
        poll_interval_ms=1000,
    )

    config = _load_config_within_freshness_budget(path, time_config)
    assert config.intake_kind == "kis_quote"
    assert config.poll_interval_ms == 1000
    assert config.journal_pass_allowance_ms is None


def test_journal_pass_allowance_present_with_kis_quote_refuses(
    tmp_path: Path, config_dir: Path
) -> None:
    """The required-XOR-forbidden half, mirroring ``journal_path``'s own cross-check: a
    ``kis_quote`` deployment that inherited the journal allowance is refused rather than
    silently ignoring a key that looks load-bearing (``_resolve_journal_path``'s own
    reasoning, applied to the second ``journal``-only key)."""
    _write_paper_shaped_time_yaml(config_dir)
    time_config = load_time_config(config_dir / "time.yaml")
    path = _write_journal_marketfeed(
        config_dir,
        tmp_path,
        intake_kind="kis_quote",
        journal_path=_MISSING,
        journal_pass_allowance_ms=100,
    )

    with pytest.raises(MarketFeedConfigError, match="journal_pass_allowance_ms"):
        _load_config_within_freshness_budget(path, time_config)


# ---------------------------------------------------------------------------
# the guard is ON the boot path (not merely a function that exists)
# ---------------------------------------------------------------------------


def test_boot_refuses_a_journal_pacing_outside_the_budget(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Through the REAL composition root: the 2026-09-27 paper combination (1000 + 100
    against the approved 800 ms budget) does not boot. Removing the guard's call from
    ``build_tick_scheduler`` leaves every loader-level test above green and turns this
    one red."""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    _write_paper_shaped_time_yaml(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    raw["poll_interval_ms"] = 1000
    raw["journal_pass_allowance_ms"] = 100
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="paces outside the conservative"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_boot_admits_the_disposition_pacing_against_the_same_budget(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """The twin of the test above with ONLY ``poll_interval_ms`` changed to the operator's
    400 — so the refusal there is the pacing budget and nothing else about the paper-shaped
    ``time.yaml``."""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    _write_paper_shaped_time_yaml(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    raw["poll_interval_ms"] = 400
    raw["journal_pass_allowance_ms"] = 100
    _write_marketfeed_config_raw(config_dir, raw)

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    try:
        assert runtime.marketfeed is not None
    finally:
        runtime.rcl_log.close()
        runtime.evidence_store.close()


def test_kis_quote_boot_is_not_budgeted(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``kis_quote`` + 1000 reaches a REAL ``build_tick_scheduler`` call under the same
    paper-shaped budget. It stops at ``_resolve_kis_instance_rest_bases`` (the default
    fixture scope carries no INSTANCE binding — ``test_marketfeed_intake_kind_wiring.py``'s
    own ``test_kis_quote_intake_no_instance_binding_refuses_at_wiring_level``), which is
    strictly LATER than the pacing guard: applying the guard to ``kis_quote`` would change
    this failure to the pacing message and turn this test red."""
    _write_critical_input_policy(config_dir)
    _write_kis_quote_transport_config(config_dir)
    _write_paper_shaped_time_yaml(config_dir)
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "unused.jsonl")
    raw["intake_kind"] = "kis_quote"
    raw["poll_interval_ms"] = 1000
    del raw["journal_path"]
    del raw["journal_pass_allowance_ms"]
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="instance") as excinfo:
        _compose(tmp_path, config_dir, data_dir, custody_root)
    assert "paces outside" not in str(excinfo.value)


def test_fixture_instrument_is_the_one_the_journal_tests_share() -> None:
    """Guards the import above: ``_valid_marketfeed_raw`` is the sibling module's helper,
    so a change to its shape (a new required key, say) lands here too rather than leaving
    this suite quietly testing a stale config shape."""
    raw = _valid_marketfeed_raw(journal_path=Path("/tmp/unused.jsonl"))
    assert raw["instruments"] == [fx.INSTRUMENT]
    assert raw["intake_kind"] == "journal"
    assert raw["journal_pass_allowance_ms"] == 100
