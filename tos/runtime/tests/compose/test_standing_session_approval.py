"""Standing session approval (operator decision 2026-10-24) — step 4 passes in the running loop
for a KIS MOCK stock session from ONE operator artifact written before the open.

Against the fake KIS server, no verify item patched (the only production patch is PR-3a's
INSTANCE ``rest_base`` -> fake server, infrastructure). Pinned:

* artifact present -> ONE pass (no approval file, no re-drive) -> step 4 ADMIT -> SEND -> ACK
  -> fill -> release, with ``APPROVAL_STANDING_BOUND`` at boot and one
  ``APPROVAL_STANDING_CONSUMED`` row naming the proposal digest and the RCL command;
* every bound: wrong instrument / direction / quantity / date / tree -> step 4 UNKNOWN, 0 POSTs;
* uses: the (max_uses+1)-th proposal is not approved; a use whose RCL append did not commit is
  not counted; a crash after the use committed and before the send, then restart -> the use is
  still counted, no second order;
* MOCK only: a SYNTHETIC tree, a REAL / POSITION_OR_CASH scope, a REAL-host / relabelled /
  unbound / absent profile never approve, artifact present or not;
* no artifact, or a refused artifact (mode, unknown field, digest changed after bind) -> today's
  behaviour (step 4 UNKNOWN).
"""

from __future__ import annotations

import dataclasses
import json
import os
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from tos.brokercap import (
    AuthorizationClass,
    BrokerEnvironment,
    EconomicEffect,
)
from tos.dsl.serialization import parse_strategy
from tos.engine.admission import strategy_admissible
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.rcl import AppendRefusal, AppendRefusalReason, CapacityState, CommandType
from tos_runtime.authority.standing import (
    STANDING_APPROVAL_RELPATH,
    STANDING_APPROVAL_SCHEMA,
    StandingApprovalSource,
    load_standing_approval,
)
from tos_runtime.brokercap import (
    is_mock_order_class,
    load_active_instance_document,
    load_broker_scopes,
)
from tos_runtime.calendar.config import load_calendar_config
from tos_runtime.calendar.phase import trading_date_at
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.operations.dependency_admission import observe_runtime_artifact
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.risk.ledger_stages import AggregateRiskDecisionStage
from tos_runtime.strategy.loader import load_strategies

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from .test_compose_root import _compose, _reach_trusted
from .test_kis_mock_e2e_honesty import _boot
from .test_kis_mock_fill_finality_e2e import (
    _ORDER_PATH,
    _ack,
    _close,
    _deploy,
    _rcl_releases,
    _rcl_state,
    _row,
    _rows,
    _script_broker,
    _sealed_quantity,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_ENV = "non-live-test"
#: The fixture tree's sealed quantity (``1E+1`` on the command's QUANTITY axis).
_FIXTURE_QTY = 10


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


# ===========================================================================
# helpers
# ===========================================================================


def _strategy_id(config_dir: Path) -> str:
    fx.write_band_strategy_file(config_dir)
    loaded = load_strategies(
        config_dir / "strategies", parse=parse_strategy, admit=strategy_admissible
    )
    (entry,) = loaded.strategies
    assert entry.strategy.strategy_id is not None
    return entry.strategy.strategy_id


def _fixture_trading_date(config_dir: Path) -> str:
    calendar = load_calendar_config(config_dir / "calendar.yaml")
    date = trading_date_at(fx.DEFAULT_WALL_CLOCK_UNIX_MS, fx.INSTRUMENT_CLASS, calendar)
    assert date is not None
    return date


def _document(config_dir: Path, **overrides: Any) -> dict[str, Any]:
    """The artifact a correct operator would write for the fixture MOCK tree."""
    document: dict[str, Any] = {
        "schema": STANDING_APPROVAL_SCHEMA,
        "environment_label": _ENV,
        "code_digest": observe_runtime_artifact().source_tree_digest,
        "trading_date": _fixture_trading_date(config_dir),
        "strategy_id": _strategy_id(config_dir),
        "instrument": fx.INSTRUMENT,
        "max_quantity": _FIXTURE_QTY,
        "actions": [
            {
                "position_effect": "OPEN",
                "direction": "LONG",
                "side": fx.SIDE,
                "max_uses": 1,
            }
        ],
        "trading_approval_policy_id": "standing-session-approval",
        "trading_approval_policy_generation": 1,
        "trading_approval_policy_digest": None,
    }
    document.update(overrides)
    return document


def _write(custody_root: Path, document: dict[str, Any], *, mode: int = 0o600) -> Path:
    path = custody_root / STANDING_APPROVAL_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    os.chmod(path, mode)
    return path


def _step4(result) -> Any:
    assert result.flow is not None
    (verdict,) = [
        v for v in result.flow.verdicts if v.step is CommitmentStep.INDEPENDENT_APPROVAL
    ]
    return verdict


def _standing_uses(runtime) -> list[str]:
    """Committed standing-approval consumption command ids, from the RCL itself."""
    return [
        entry.command_id
        for entry in runtime.rcl_log.replay()
        if entry.kind == CommandType.CONSUME_APPROVAL_DECISION.value
        and entry.command_id.startswith("iap-consumption:standing-approval:")
    ]


def _no_per_proposal_files(custody_root: Path) -> None:
    approvals = custody_root / "approvals"
    assert [p.name for p in approvals.iterdir()] == ["standing-session.yaml"]


def _one_pass(runtime):
    (result,) = runtime.run_once((fx.crossing_event(),))
    return result


def _deployed(config_dir, custody_root, server, monkeypatch, **overrides):
    _deploy(config_dir, custody_root, server, monkeypatch)
    _write(custody_root, _document(config_dir, **overrides))


# ===========================================================================
# 1. the running loop: one pass, no approval file, no re-drive -> ACK -> fill -> release
# ===========================================================================


def test_one_pass_with_the_standing_artifact_sends_acks_fills_and_releases(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    _deployed(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    (bound,) = _rows(runtime, "APPROVAL_STANDING_BOUND")

    result = _one_pass(runtime)
    assert _step4(result).outcome is StageOutcome.ADMIT
    assert result.flow.handed_off is True
    _no_per_proposal_files(custody_root)
    assert len(server.requests_for(_ORDER_PATH)) == 1

    proposal_digest = result.pipeline.proposal.canonical_digest
    (consumed,) = _rows(runtime, "APPROVAL_STANDING_CONSUMED")
    assert consumed["artifact_digest"] == bound["artifact_digest"]
    assert consumed["proposal_digest"] == proposal_digest
    assert consumed["slot"] == 1 and consumed["consumption_outcome"] == "CONSUMED_NEW"
    assert _standing_uses(runtime) == [consumed["rcl_command_id"]]

    ack = _ack(runtime)
    date, qty = ack["trading_date"], _sealed_quantity(runtime)
    _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )
    observer = runtime.fill_observer
    assert observer is not None
    observer.poll_once()
    assert _rcl_state(runtime) is CapacityState.POSITION_CONSUMED
    assert _rcl_releases(runtime) == 1
    assert len(server.requests_for(_ORDER_PATH)) == 1
    _close(runtime)


# ===========================================================================
# 2. bounds — each one alone keeps step 4 UNKNOWN and sends nothing
# ===========================================================================


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"instrument": "005930"}, "instrument_mismatch"),
        (
            {
                "actions": [
                    {
                        "position_effect": "OPEN",
                        "direction": "SHORT",
                        "side": fx.SIDE,
                        "max_uses": 1,
                    }
                ]
            },
            "action_not_declared",
        ),
        ({"max_quantity": _FIXTURE_QTY - 1}, "quantity_exceeds_max"),
        ({"trading_date": "20200102"}, "trading_date_mismatch_or_session_closed"),
        ({"code_digest": "0" * 64}, "code_digest_mismatch"),
        ({"strategy_id": "astrat-" + "0" * 64}, "strategy_mismatch"),
    ],
    ids=[
        "instrument",
        "direction",
        "quantity",
        "date",
        "tree-release",
        "tree-strategy",
    ],
)
def test_a_proposal_outside_any_bound_is_not_approved(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server, overrides, reason
) -> None:
    _deployed(config_dir, custody_root, server, monkeypatch, **overrides)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    result = _one_pass(runtime)
    assert _step4(result).outcome is StageOutcome.UNKNOWN
    assert server.requests_for(_ORDER_PATH) == []
    assert _standing_uses(runtime) == []
    assert [r["reason"] for r in _rows(runtime, "APPROVAL_STANDING_NOT_COVERED")] == [
        reason
    ]
    _close(runtime)


def test_the_session_closing_expires_the_approval(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """Outside every calendar window the trusted trading date is ``None`` — no approval."""
    _deployed(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    monkeypatch.setattr(runtime.session_facts, "trading_date_now", lambda _cls: None)
    assert _step4(_one_pass(runtime)).outcome is StageOutcome.UNKNOWN
    assert server.requests_for(_ORDER_PATH) == []
    reasons = [r["reason"] for r in _rows(runtime, "APPROVAL_STANDING_NOT_COVERED")]
    assert reasons == ["trading_date_mismatch_or_session_closed"]
    _close(runtime)


def test_the_stock_calendar_has_no_trading_date_after_the_last_window() -> None:
    """The stock tree's own calendar: 15:59 KST still dated, 16:00 KST (AFTER_HOURS end) not."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    repo = Path(__file__).resolve().parents[4]
    calendar = load_calendar_config(
        repo / "config" / "tos_runtime" / "cp3-setup-d-stock-005930" / "calendar.yaml"
    )

    def _at(hh: int, mm: int) -> str | None:
        instant = datetime(2026, 10, 26, hh, mm, tzinfo=ZoneInfo("Asia/Seoul"))
        return trading_date_at(int(instant.timestamp() * 1000), "krx-stock", calendar)

    assert _at(9, 0) == "20261026"
    assert _at(15, 59) == "20261026"
    assert _at(16, 0) is None


# ===========================================================================
# 3. uses — counted from the committed RCL log, never reused
# ===========================================================================


def test_the_proposal_after_max_uses_is_not_approved(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    _deployed(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _step4(_one_pass(runtime)).outcome is StageOutcome.ADMIT
    second = _one_pass(runtime)
    assert _step4(second).outcome is StageOutcome.UNKNOWN
    assert len(server.requests_for(_ORDER_PATH)) == 1
    assert len(_standing_uses(runtime)) == 1
    reasons = [r["reason"] for r in _rows(runtime, "APPROVAL_STANDING_NOT_COVERED")]
    assert reasons == ["uses_exhausted:OPEN-LONG-" + fx.SIDE]
    _close(runtime)


def test_a_use_whose_append_did_not_commit_is_not_counted(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    _deployed(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    original = SqliteCommitLog.append_cas

    def _refusing(self, entry, **kwargs):
        if entry.kind is CommandType.CONSUME_APPROVAL_DECISION:
            return AppendRefusal(
                reason=AppendRefusalReason.STORE_UNAVAILABLE, detail="rolled back"
            )
        return original(self, entry, **kwargs)

    monkeypatch.setattr(SqliteCommitLog, "append_cas", _refusing)
    assert _step4(_one_pass(runtime)).outcome is StageOutcome.UNKNOWN
    assert server.requests_for(_ORDER_PATH) == []
    assert _standing_uses(runtime) == []
    assert _rows(runtime, "APPROVAL_STANDING_CONSUMED") == []

    monkeypatch.setattr(SqliteCommitLog, "append_cas", original)
    assert _step4(_one_pass(runtime)).outcome is StageOutcome.ADMIT
    (consumed,) = _rows(runtime, "APPROVAL_STANDING_CONSUMED")
    assert consumed["slot"] == 1
    assert len(server.requests_for(_ORDER_PATH)) == 1
    _close(runtime)


class _Crash(BaseException):
    """Process death right after step 4 committed its use (kill -9 stand-in)."""


@pytest.mark.parametrize("max_uses", [1, 2])
def test_a_crash_after_the_use_committed_still_counts_it_after_restart(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server, max_uses
) -> None:
    actions = [
        {
            "position_effect": "OPEN",
            "direction": "LONG",
            "side": fx.SIDE,
            "max_uses": max_uses,
        }
    ]
    _deployed(config_dir, custody_root, server, monkeypatch, actions=actions)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)

    def _die(self, request):
        raise _Crash

    with monkeypatch.context() as patch:
        patch.setattr(AggregateRiskDecisionStage, "__call__", _die)
        with pytest.raises(_Crash):
            _one_pass(runtime)
    assert len(_standing_uses(runtime)) == 1
    assert server.requests_for(_ORDER_PATH) == []
    _close(runtime)

    # The reboot is held by the recovery barrier (an unreconciled possibly-live attempt): it
    # drives nothing at all. The committed use is still on the log and still counted.
    runtime2 = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    assert runtime2.driver is None
    assert len(_standing_uses(runtime2)) == 1
    source = StandingApprovalSource(
        custody_root,
        environment_label=_ENV,
        code_digest=observe_runtime_artifact().source_tree_digest,
        uid=os.getuid(),
        mock_class=lambda: True,
        trading_date_reader=lambda: None,
        construction_reader=lambda: None,
        rcl_log=runtime2.rcl_log,
        writer_epoch=runtime2.writer_epoch,
        evidence=runtime2.evidence_store,
    )
    approval = load_standing_approval(
        custody_root / STANDING_APPROVAL_RELPATH, expected_owner_uid=os.getuid()
    )
    (action,) = approval.actions
    assert source.free_slot(approval.trading_date, action) == (
        None if max_uses == 1 else 2
    )
    assert server.requests_for(_ORDER_PATH) == []
    _close(runtime2)


# ===========================================================================
# 4. MOCK only, by construction
# ===========================================================================


def test_a_synthetic_tree_never_uses_the_artifact(
    config_dir, data_dir, custody_root, tmp_path
) -> None:
    """The futures trees are SYNTHETIC: the artifact is not even read there (pinned: stock MOCK
    only)."""
    _write(custody_root, _document(config_dir))
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    result = _one_pass(runtime)
    assert _step4(result).outcome is StageOutcome.UNKNOWN
    assert _standing_uses(runtime) == []
    for kind in ("APPROVAL_STANDING_BOUND", "APPROVAL_STANDING_NOT_COVERED"):
        assert _rows(runtime, kind) == []
    _close(runtime)


def test_the_mock_gate_is_load_bearing_in_the_running_loop(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """Mutation: if the MOCK predicate said no, the same deployment sends nothing."""
    import tos_runtime.compose._standing_wiring as wiring

    _deployed(config_dir, custody_root, server, monkeypatch)
    monkeypatch.setattr(wiring, "is_mock_order_class", lambda _scope, _instance: False)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _step4(_one_pass(runtime)).outcome is StageOutcome.UNKNOWN
    assert server.requests_for(_ORDER_PATH) == []
    assert _rows(runtime, "APPROVAL_STANDING_BOUND") == []
    _close(runtime)


def _mock_scope_and_instance(config_dir, custody_root, server, monkeypatch):
    _deploy(config_dir, custody_root, server, monkeypatch)
    scopes = load_broker_scopes(
        config_dir / "broker_scopes.yaml", environment_label=_ENV
    )
    instance = load_active_instance_document(scopes)
    assert is_mock_order_class(scopes.active_scope, instance) is True
    return scopes.active_scope, instance


def _retuple(scope, **update):
    return dataclasses.replace(
        scope,
        capability_tuples=tuple(
            t.model_copy(update=update) for t in scope.capability_tuples
        ),
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "real-environment",
        "real-order",
        "position-or-cash",
        "real-host-profile",
        "relabelled-profile",
        "unbound-profile",
        "no-profile",
    ],
)
def test_no_non_mock_scope_or_profile_is_ever_approved(
    config_dir, data_dir, custody_root, server, monkeypatch, mutation
) -> None:
    scope, instance = _mock_scope_and_instance(
        config_dir, custody_root, server, monkeypatch
    )
    if mutation == "real-environment":
        scope = _retuple(scope, environment=BrokerEnvironment.BROKER_PRODUCTION)
    elif mutation == "real-order":
        scope = _retuple(scope, authorization_class=AuthorizationClass.REAL_ORDER)
    elif mutation == "position-or-cash":
        scope = _retuple(scope, economic_effect=EconomicEffect.POSITION_OR_CASH)
    elif mutation == "real-host-profile":
        instance = dataclasses.replace(
            instance, rest_base="https://openapi.example:9443"
        )
    elif mutation == "relabelled-profile":
        instance = dataclasses.replace(
            instance,
            profile=instance.profile.model_copy(
                update={"environment_class": BrokerEnvironment.BROKER_PRODUCTION}
            ),
        )
    elif mutation == "unbound-profile":
        instance = dataclasses.replace(instance, environment_class_binding=None)
    else:
        instance = None
    assert is_mock_order_class(scope, instance) is False

    _write(custody_root, _document(config_dir))
    reads: list[str] = []

    def _date() -> str | None:
        reads.append("date")
        return None

    def _construction() -> None:
        reads.append("construction")

    source = StandingApprovalSource(
        custody_root,
        environment_label=_ENV,
        code_digest=observe_runtime_artifact().source_tree_digest,
        uid=os.getuid(),
        mock_class=lambda: is_mock_order_class(scope, instance),
        trading_date_reader=_date,
        construction_reader=_construction,
        # never reached: the MOCK gate closes before the log is read
        rcl_log=cast(SqliteCommitLog, object()),
        writer_epoch=0,
        evidence=None,
    )
    source.bind_at_boot()
    assert source.provide(object()) is None  # type: ignore[arg-type]
    assert reads == []


# ===========================================================================
# 5. no artifact / refused artifact -> today's behaviour
# ===========================================================================


def test_no_artifact_keeps_step4_unknown(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    _deploy(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _step4(_one_pass(runtime)).outcome is StageOutcome.UNKNOWN
    assert server.requests_for(_ORDER_PATH) == []
    text = json.dumps([_rows(runtime, k) for k in ("APPROVAL_STANDING_BOUND",)])
    assert text == "[[]]"
    _close(runtime)


@pytest.mark.parametrize(
    "defect", ["mode-0644", "unknown-field", "missing-field", "bad-schema"]
)
def test_a_refused_artifact_is_no_approval(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server, defect
) -> None:
    _deploy(config_dir, custody_root, server, monkeypatch)
    document = _document(config_dir)
    mode = 0o600
    if defect == "mode-0644":
        mode = 0o644
    elif defect == "unknown-field":
        document["environment_class"] = "BROKER_SIMULATION"
    elif defect == "missing-field":
        del document["max_quantity"]
    else:
        document["schema"] = "tos-standing-session-approval/0"
    _write(custody_root, document, mode=mode)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _rows(runtime, "APPROVAL_STANDING_BOUND") == []
    assert [r["reason"] for r in _rows(runtime, "APPROVAL_STANDING_REFUSED")] == [
        "unloadable"
    ]
    assert _step4(_one_pass(runtime)).outcome is StageOutcome.UNKNOWN
    assert server.requests_for(_ORDER_PATH) == []
    _close(runtime)


def test_an_artifact_rewritten_after_bind_is_refused_until_restart(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    _deployed(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    actions = [
        {"position_effect": "OPEN", "direction": "LONG", "side": fx.SIDE, "max_uses": 5}
    ]
    _write(custody_root, _document(config_dir, actions=actions))
    assert _step4(_one_pass(runtime)).outcome is StageOutcome.UNKNOWN
    (refused,) = _rows(runtime, "APPROVAL_STANDING_REFUSED")
    assert refused["reason"] == "digest_changed_since_bound"
    assert server.requests_for(_ORDER_PATH) == []
    _close(runtime)
