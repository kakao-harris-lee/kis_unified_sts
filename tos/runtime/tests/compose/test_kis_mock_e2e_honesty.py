"""KIS MOCK transport e2e honesty + counterfactual (TOS KIS MOCK transport plan T3,
``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md`` §4 row T3, §0 "핵심 귀결", §9 T2
landing note 잔여 ①).

**What this file proves, and what it does not.** With ``MOCK_STOCK_ORDER`` active
(``profile_evidence_ok: true``) and ``kis-mock`` wired, the Coordinator's own non-live
admission (T2 lane B) genuinely ADMITS the send — no ``LIVE_SCOPE_NOT_AUTHORIZED`` halt is ever
recorded. The kernel gateway's own 17-item verify list still denies it honestly, today, at THREE
independent gates, not the two the plan's §0 headline names:

1. item 5 (``VALID_LIVE_SCOPE`` / ``live_scope_valid``) of the six DEFERRED_ITEMS — the ONE
   still genuinely UNKNOWN after Phase 5 W3-b landed real owners for the other five
   (items 4/7/8/9/10 — the Safety Authority epoch service + the four safety-mesh services,
   SAFETY_ENVELOPE_PROFILE/DEVIATION/INCIDENT/MONITORING);
2. item 6 (``ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY``) — brokercap
   ``capability_admissible`` is structurally ``PROHIBITED`` for a Broker Capability Profile
   INSTANCE with no approved ``minimum_live_gate_satisfied``/``VERIFIED`` dimension (P0-2);
3. item 12 (``VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION``) — empirically confirmed
   here as an ADDITIONAL, independent P0-2 blocker the plan's §0/§9 prose does not name: its own
   recorded reason is the SAME "the versioned Profile is P0-2-blocked" fact item 6 cites
   (``tos_runtime.brokercap.derive.derive_item6_item12``'s ``broker_constraint_generation_current``
   — gated on the SAME INSTANCE document's ``degraded_since_authorization`` being non-``None``,
   which the shipped example config leaves honestly ``null``). This is not a second, unrelated
   gate: it is the SAME P0-2 "approved Broker Capability Profile INSTANCE" fact items 6 and 12
   both read, so the counterfactual below lifts both through the ONE seam that derives them,
   :func:`~tos_runtime.brokercap.derive_item6_item12` — never a fourth, invented shortcut.

The counterfactual tests below therefore apply exactly two *conceptual* lifts (deferred Phase 5
mesh; P0-2 broker-capability-profile facts) even though the P0-2 lift touches three verify
items (6, 12) plus the ``capability_admissible`` call — see :func:`_lift_p02_capability_profile`'s
own docstring. Team-lead brief §0 note "잔여 ①" (forcing ``deferred_item_verdict`` alone does not
reach the transport because item 6 blocks independently) is confirmed and extended here: item 12
blocks independently too.

Hermetic (D1.4): the fake KIS server binds ``127.0.0.1`` only; ``scheme: http`` is admitted only
via ``allow_plaintext_for_tests: true`` (test-only escape hatch, config.py's own docstring); no
``os.environ``, ``subprocess``, or ``importlib.import_module`` anywhere in this module (the
firewall scans tests too).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.brokercap import Admissibility
from tos.egressgw import gateway as gateway_module
from tos.egressgw.vocabulary import DEFERRED_ITEMS, VerifyOutcome, verify_item_number
from tos.rcl import CapacityState
from tos_runtime.brokercap.instance import load_instance_documents
from tos_runtime.calendar.owner import SessionFactsOwner
from tos_runtime.compose import context as context_module
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.transport.kis_mock.adapter import KisMockTransport
from tos_runtime.transport.kis_mock.client import KisMockHttpClient

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from ..transport.kis_mock.test_adapter import (
    _retry_primitive_offenders_excluding_pacing,
)
from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted
from .test_transport_wiring import _activate_mock_stock_order

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_ENVIRONMENT_LABEL = "non-live-test"

#: The 6 deferred verify-item numbers this suite pins (plan §4 T3: "list the 6 item numbers").
_EXPECTED_DEFERRED_ITEM_NUMBERS = frozenset(
    verify_item_number(item) for item in DEFERRED_ITEMS
)

#: Phase 5 W3 landed real safety-mesh services (SAFETY_ENVELOPE_PROFILE/DEVIATION/
#: INCIDENT/MONITORING) + the Safety Authority epoch supply — 5 of the 6 DEFERRED_ITEMS are
#: genuinely SATISFIED in production now, not merely simulated (``_lift_phase5_deferred_mesh``
#: below still exists for tests that need ALL SIX lifted, e.g. counterfactual A/B). Only item 5
#: (``VALID_LIVE_SCOPE`` / ``live_scope_valid``) stays UNKNOWN — plan §2 decision 4's own
#: operator confirmation ③ (a): committed until a live-authorization runtime exists (Phase 6+).
_EXPECTED_UNSUPPLIED_DEFERRED_ITEM_NUMBERS = frozenset({5})

#: A distinctive token that must NEVER appear in any recorded evidence payload — stands in for
#: every credential/token secret this suite's custody/fake-server fixtures mint.
_ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
_TOKEN_PATH = "/oauth2/tokenP"
_APP_KEY_SECRET_BYTES = b"test-secret-kis_mock.app_key"
_APP_SECRET_SECRET_BYTES = b"test-secret-kis_mock.app_secret"
_FAKE_BEARER_TOKEN = "t3-fake-bearer-token-never-in-evidence"


# ===========================================================================
# Shared setup helpers
# ===========================================================================


def _activate_and_admit(config_dir: Path, custody_root: Path) -> None:
    """The T2-proven shape every scenario in this file starts from: MOCK_STOCK_ORDER active
    (``profile_evidence_ok: true``, via :func:`~.test_transport_wiring._activate_mock_stock_order`
    — reused, never duplicated) + the Coordinator's own non-live admission posture granted.
    """
    _activate_mock_stock_order(config_dir)
    fx.provision_kis_mock_custody(custody_root)
    (config_dir / "coordinator_preconditions.yaml").write_text(
        yaml.safe_dump(
            {
                "live_authorization_state": "NOT_AUTHORIZED",
                "nonlive_broker_consuming": {"admitted": True},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _drive_crossing_tick(runtime, custody_root: Path):
    """Drive :func:`~._fixtures.crossing_event` through the SAME two-``run_once`` shape every
    landed compose e2e test in this suite uses (proposal -> write approval -> re-drive to the
    gateway) — returns the second call's ``EventResult`` (the one that reaches the gateway).
    """
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label=_ENVIRONMENT_LABEL,
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    results2 = runtime.run_once((event,))
    return results2[0]


def _lift_phase5_deferred_mesh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force every :data:`~tos.egressgw.vocabulary.DEFERRED_ITEMS` verdict to ``SATISFIED`` —
    the narrowest seam naming "Phase 5 W3 closed": :func:`tos.egressgw.gateway
    .deferred_item_verdict` is the ONE function :func:`~tos.egressgw.gateway.verify_send_boundary`
    dispatches every deferred item through (module-global lookup at call time, so patching the
    module attribute takes effect), reusing the gateway's own ``_verdict`` builder rather than
    hand-constructing a :class:`~tos.egressgw.records.VerifyItemVerdict`.

    Kernel round #2 §2 decisions 1/2 moved this function to :mod:`tos.egressgw.mesh`, dropped
    its leading underscore, and added a third ``context`` parameter (the six injected mesh
    flags) — ``gateway.py`` still imports it by name into its own module namespace
    (``from tos.egressgw.mesh import deferred_item_verdict``), so patching
    ``gateway_module.deferred_item_verdict`` still takes effect at
    ``verify_send_boundary``'s call site, unchanged.
    """

    def _satisfied(item: Any, applicability: Any, context: Any) -> Any:
        del applicability, context
        return gateway_module._verdict(
            item,
            VerifyOutcome.SATISFIED,
            reason="T3 counterfactual: Phase 5 W3 safety-governance mesh simulated closed",
        )

    monkeypatch.setattr(gateway_module, "deferred_item_verdict", _satisfied)


def _lift_p02_capability_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lift the P0-2 "approved Broker Capability Profile INSTANCE" facts items 6 and 12 both
    read (module docstring) — the narrowest two seams:

    * :func:`tos.brokercap.capability_admissible`, as bound into
      :mod:`tos.egressgw.gateway`'s own namespace (``_check_allowance`` calls it as a bare
      global, so patching the module attribute takes effect) — forced ``ADMISSIBLE``.
    * :func:`tos_runtime.brokercap.derive_item6_item12`, as bound into
      :mod:`tos_runtime.compose.context`'s own namespace (``_item6_item12_fields`` calls it the
      same way) — wrapped so the REAL derivation still runs (nothing else about the scope is
      faked), but ``account_instrument_action_allowed`` (item 6's own positivity gate, checked
      AFTER ``capability_admissible`` returns admissible — patching ``capability_admissible``
      alone is not sufficient, confirmed empirically) and ``broker_constraint_generation_current``
      (item 12) are both forced ``True``.
    """

    def _always_admissible(*_args: Any, **_kwargs: Any) -> Admissibility:
        return Admissibility.ADMISSIBLE

    monkeypatch.setattr(gateway_module, "capability_admissible", _always_admissible)
    real_derive = context_module.derive_item6_item12

    def _lifted_derive(scope: Any, config: Any, instance: Any) -> Any:
        fields = real_derive(scope, config, instance)
        return dataclasses.replace(
            fields,
            account_instrument_action_allowed=True,
            broker_constraint_generation_current=True,
        )

    monkeypatch.setattr(context_module, "derive_item6_item12", _lifted_derive)


def _lift_venue_session_account_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force item 12's OTHER half — the kernel composite over
    :meth:`~tos_runtime.calendar.owner.SessionFactsOwner.session_facts_current` /
    ``tradability_facts_current`` / ``account_facts_current`` (kernel round #3 §2
    decision 4, superseding TOS Phase 5 W5 plan §2 decision 3's single
    pre-composed method) — to ``True`` by forcing all three sub-facts ``True``.
    This scope (MOCK_STOCK_ORDER) is broker-reaching, so the real owner
    honestly returns ``None`` for tradability/account (no tradability/
    account-halt source exists yet for a broker scope) — a SEPARATE,
    independent reason item 12 stays UNKNOWN from P0-2's
    ``broker_constraint_generation_current`` gate (module docstring; see
    :func:`test_honest_deny_full_evidence_level`'s pin distinguishing the two).
    The counterfactual/mutation-b tests below need BOTH halves lifted to reach
    a genuine SATISFIED send.
    """

    def _always_true_session(  # noqa: ARG001 - fixed monkeypatch signature
        self, instrument_class: str
    ) -> bool:
        return True

    def _always_true_flag(  # noqa: ARG001 - fixed monkeypatch signature
        self, *, broker_reaching: bool
    ) -> bool:
        return True

    monkeypatch.setattr(
        SessionFactsOwner, "session_facts_current", _always_true_session
    )
    monkeypatch.setattr(
        SessionFactsOwner, "tradability_facts_current", _always_true_flag
    )
    monkeypatch.setattr(SessionFactsOwner, "account_facts_current", _always_true_flag)


def _verify_item_payloads(runtime) -> list[dict[str, Any]]:
    rows = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'VERIFY_ITEM' ORDER BY rowid"
    ).fetchall()
    return [json.loads(row[0])["payload"] for row in rows]


def _evidence_kind_count(runtime, kind: str) -> int:
    return runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()[0]


def _evidence_kind_like_count(runtime, pattern: str) -> int:
    return runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind LIKE ?", (pattern,)
    ).fetchone()[0]


def _evidence_row_order(runtime, kind: str) -> int | None:
    """The (0-based) position of the FIRST ``entries`` row with this ``kind`` in rowid order, or
    ``None`` if no such row exists — used to prove one evidence kind precedes another.
    """
    rows = runtime.evidence_store.connection.execute(
        "SELECT rowid, kind FROM entries ORDER BY rowid"
    ).fetchall()
    for index, (_rowid, row_kind) in enumerate(rows):
        if row_kind == kind:
            return index
    return None


def _all_evidence_text(runtime) -> str:
    rows = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries"
    ).fetchall()
    return " ".join(row[0] for row in rows)


def _independent_wire_digest(
    *, account: str, instrument: str, quantity: str, price: str
) -> str:
    """A GENUINELY independent oracle for the KIS ``order_cash`` wire-body digest — hand-built
    from the codec's own FROZEN recipe (``codec.py``'s module docstring), calling NEITHER
    :meth:`~tos_runtime.transport.kis_mock.codec.KisOrderWireCodec.encode_fields` NOR its
    private ``_decimal_to_kis_string`` helper. Reviewer disposition MEDIUM-2: the prior version
    of this check called ``encode_fields`` directly, so it was "three consumers agreeing on one
    encoder", not "the encoding is actually correct" — corrupting ``_decimal_to_kis_string`` left
    every assertion in this file green. This version's own ``format(Decimal(...), "f")`` call is
    a DIFFERENT call site from the codec's private helper, so a corrupted
    ``_decimal_to_kis_string`` still poisons the seal's own ``request_bytes_digest`` (computed by
    the compose resolver's ``KisWireCodecDigest``, which DOES call it) while this oracle keeps
    computing the correct value — the two then disagree, and the assertion goes red.

    The five static literals are ``fx.write_kis_mock_transport_config``'s own
    ``static_body_fields`` values, reproduced here as plain config literals (reviewer's own
    suggested fix) rather than read back off the loaded ``KisMockTransportConfig`` object — this
    suite's one config fixture is the sole source of truth for them.
    """
    fields = {
        "CANO": account,
        "PDNO": instrument,
        "ORD_QTY": format(Decimal(quantity), "f"),
        "ORD_UNPR": format(Decimal(price), "f"),
        "ACNT_PRDT_CD": "01",
        "ORD_DVSN": "00",
        "EXCG_ID_DVSN_CD": "KRX",
        "SLL_TYPE": "",
        "CNDT_PRIC": "",
    }
    body = json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _assert_byte_seal_identity_and_result_ordering(
    runtime, order_request: Any, seal_payload: dict[str, Any]
) -> None:
    """Counterfactual B's own byte-seal-identity block, extracted (review LOW: keep
    ``test_counterfactual_b_live_against_hermetic_fake_kis_server`` at or under the 100-line
    function budget) — the wire bytes the fake server actually received equal BOTH the seal's
    own ``request_bytes_digest`` and a hand-built, genuinely independent oracle
    (:func:`_independent_wire_digest`, reviewer disposition MEDIUM-2 — never calls
    ``KisOrderWireCodec``), and ``EGRESS_RESULT_RECORDED`` is recorded exactly once, after
    ``NETWORK_CALL_ENTERED``.
    """
    # The wire bytes ARE the sealed bytes — the sha256 of what the fake server actually
    # received equals the seal's own request_bytes_digest, not a value this test invents.
    received_digest = hashlib.sha256(order_request.body).hexdigest()
    assert received_digest == seal_payload["request_bytes_digest"]
    # ...and it equals a hand-built, genuinely independent oracle too — proving not just "the
    # wire bytes are what was sealed" but "what was sealed was correctly encoded" (a corrupted
    # decimal formatter would surface here).
    independent_digest = _independent_wire_digest(
        account=seal_payload["account"],
        instrument=seal_payload["instrument_key"]["instrument"],
        quantity=seal_payload["outbound_quantity"],
        price=seal_payload["outbound_price"],
    )
    assert received_digest == independent_digest

    assert _evidence_kind_count(runtime, "EGRESS_RESULT_RECORDED") == 1
    network_call_entered_order = _evidence_row_order(runtime, "NETWORK_CALL_ENTERED")
    egress_result_recorded_order = _evidence_row_order(
        runtime, "EGRESS_RESULT_RECORDED"
    )
    assert network_call_entered_order is not None
    assert egress_result_recorded_order is not None
    assert network_call_entered_order < egress_result_recorded_order


def _spy_send_once(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Spy on every :class:`KisMockTransport` instance's ``send_once`` (class-level patch, the
    same technique ``test_transport_wiring.py``'s own
    ``test_synthetic_compose_never_wires_the_seal_registry_observer`` uses for ``SealRegistry
    .capture``) — records the RETURNED ``EgressResultPayload`` for each call, never altering
    behaviour."""
    calls: list[Any] = []
    original = KisMockTransport.send_once

    def _spying(self: KisMockTransport, attempt: Any, **kwargs: Any) -> Any:
        result = original(self, attempt, **kwargs)
        calls.append(result)
        return result

    monkeypatch.setattr(KisMockTransport, "send_once", _spying)
    return calls


def _spy_do_request(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Spy on ``KisMockHttpClient._do_request`` — the ONE call site that ever opens a socket
    (client.py's own module docstring) — proving dry_run opens zero."""
    calls: list[Any] = []
    original = KisMockHttpClient._do_request

    def _spying(self: KisMockHttpClient, method: str, path: str, **kwargs: Any) -> Any:
        calls.append((method, path))
        return original(self, method, path, **kwargs)

    monkeypatch.setattr(KisMockHttpClient, "_do_request", _spying)
    return calls


def _patch_instance_documents_to_host(
    monkeypatch: pytest.MonkeyPatch, *, mock_rest_base: str
) -> None:
    """Substitute the MOCK_VTS INSTANCE document's own ``rest_base`` for ``mock_rest_base``
    (the fake server's own dynamically-assigned ``http://127.0.0.1:<port>``), leaving every
    other document (in particular REAL_PROD's own real, different, ``rest_base``) untouched —
    the SAME monkeypatch seam and "never invented, only doctored from the real loaded documents"
    discipline ``test_transport_wiring.py``'s own
    ``test_load_transport_config_kis_mock_refuses_when_mock_document_rest_base_is_none`` already
    uses for ``tos_runtime.compose._transport_wiring.load_instance_documents``. This is the ONLY
    way a hermetic ``127.0.0.1`` fake server can stand in for the real MOCK_VTS host through the
    REAL compose root's own host-seal check (config.py's decision-5 exact-match refusal) without
    weakening that check itself."""

    def _patched(path: Path) -> tuple[Any, ...]:
        documents = load_instance_documents(path)
        return tuple(
            (
                dataclasses.replace(document, rest_base=mock_rest_base)
                if document.environment == "MOCK_VTS"
                else document
            )
            for document in documents
        )

    monkeypatch.setattr(
        "tos_runtime.compose._transport_wiring.load_instance_documents", _patched
    )


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


# ===========================================================================
# 1. Honest deny (full, evidence-level) — no counterfactual lift
# ===========================================================================


def test_honest_deny_full_evidence_level(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MOCK_STOCK_ORDER active + kis-mock (dry_run) + Coordinator non-live admission granted:
    the Coordinator admits (no ``LIVE_SCOPE_NOT_AUTHORIZED``), the gateway denies honestly at
    the SEND_BOUNDARY_VERIFICATION step, and the transport is never called."""
    _activate_and_admit(config_dir, custody_root)
    fx.write_kis_mock_transport_config(config_dir)
    send_once_calls = _spy_send_once(monkeypatch)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None
    assert result.flow.handed_off is True  # steps 1-14 admitted
    assert result.flow.handoff is not None
    assert (
        result.flow.handoff.accepted_for_transmission is not True
    )  # gateway itself denied

    # No LIVE_SCOPE_NOT_AUTHORIZED halt — the Coordinator's own gate ADMITTED this send
    # (T2 lane B's own non-live admission), never the thing that is being tested here.
    live_scope_halts = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE payload_json LIKE '%LIVE_SCOPE_NOT_AUTHORIZED%'"
    ).fetchone()[0]
    assert live_scope_halts == 0

    verdicts = _verify_item_payloads(runtime)
    assert len(verdicts) == 17
    assert verdicts[0]["applicability"] == "BROKER_RESOURCE_CONSUMING"

    unknown_items = {v["item"] for v in verdicts if v["outcome"] == "UNKNOWN"}
    deferred_names = {item.value for item in DEFERRED_ITEMS}
    # Phase 5 W3-b landed real owners for 5 of the 6 DEFERRED_ITEMS (module docstring's
    # own updated count) — only VALID_LIVE_SCOPE (item 5) is still genuinely UNKNOWN
    # (this composition supplies no live-authorization runtime yet). item 12
    # (VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION) is the ONE additional,
    # non-deferred item that is ALSO UNKNOWN today (module docstring's "three gates, not
    # two") — pinned as an exact set so a genuinely NEW, unrelated UNKNOWN item, or an
    # accidentally-fabricated positive on item 5, would both be caught.
    assert unknown_items == {
        "VALID_LIVE_SCOPE",
        "VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION",
    }
    # TOS Phase 5 W5 (plan §2 decision 3): item 12's kernel gate (gateway.py's
    # _check_venue_generations) checks venue_session_account_facts_current BEFORE
    # broker_constraint_generation_current -- whichever is non-positive FIRST decides the
    # reason text. This scope (MOCK_STOCK_ORDER) is broker-reaching, so the real
    # SessionFactsOwner honestly returns None for venue_session_account_facts_current (no
    # tradability/account-halt source exists for a broker scope yet) -- a DIFFERENT,
    # independent reason from item 12's OTHER half (broker_constraint_generation_current,
    # blocked by the P0-2 unapproved-INSTANCE gap). Pinning the reason text distinguishes
    # the two: mutation M2 (forcing venue_session_account_facts_current to True for a
    # broker-reaching scope) would flip this reason to the SECOND branch's text instead,
    # making this assertion go red.
    (item12_verdict,) = (
        v
        for v in verdicts
        if v["item"] == "VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION"
    )
    assert "venue / session" in item12_verdict["detail"]
    assert "broker-constraint generation" not in item12_verdict["detail"]

    observed_unsupplied_deferred_numbers = {
        verify_item_number(item)
        for item in DEFERRED_ITEMS
        if item.value in unknown_items
    }
    assert (
        observed_unsupplied_deferred_numbers
        == _EXPECTED_UNSUPPLIED_DEFERRED_ITEM_NUMBERS
    )
    assert sorted(_EXPECTED_DEFERRED_ITEM_NUMBERS) == [4, 5, 7, 8, 9, 10]

    # The 5 now-supplied deferred items are SATISFIED, never merely absent-from-unknown by
    # accident — each traced to its own real Phase 5 W3 owner (module docstring).
    satisfied_deferred = {
        v["item"]
        for v in verdicts
        if v["item"] in deferred_names and v["item"] not in unknown_items
    }
    assert satisfied_deferred == {
        "CURRENT_SAFETY_AUTHORITY_EPOCH",
        "HARD_SAFETY_ENVELOPE_VERSIONS",
        "SAFETY_DEVIATION",
        "SAFETY_INCIDENT",
        "SAFETY_MONITORING",
    }
    for v in verdicts:
        if v["item"] in satisfied_deferred:
            assert v["outcome"] == "SATISFIED"

    # item 6's own verdict: DENIED (not UNKNOWN — capability_admissible is PROHIBITED, not
    # REDUCED), reason names PROHIBITED explicitly (gateway.py _check_allowance).
    (item6_verdict,) = (
        v
        for v in verdicts
        if v["item"] == "ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY"
    )
    assert item6_verdict["outcome"] == "DENIED"
    assert "PROHIBITED" in item6_verdict["detail"]

    # The gateway itself refused (SEND_REFUSED) — never the transport, never SEND_SEALED at
    # all (the halt is BEFORE seal construction, gateway.py's own __call__ order).
    assert _evidence_kind_count(runtime, "SEND_REFUSED") == 1
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 0
    assert _evidence_kind_like_count(runtime, "TRANSPORT_%") == 0
    assert send_once_calls == []

    # Zero seals left in the SealRegistry — trivially true here (nothing was ever captured,
    # since SEND_SEALED is never recorded), asserted directly against the live instance T2's
    # own compose wiring constructs.
    assert runtime.transport._seal_lookup._seals == {}  # noqa: SLF001

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ===========================================================================
# 2. Counterfactual A — "Phase 5 + P0-2 closed" (dry_run)
# ===========================================================================


def test_counterfactual_a_phase5_and_p02_closed_dry_run(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lift BOTH blockers (deferred mesh + P0-2 capability-profile facts) and re-drive the SAME
    crossing tick: the gateway now reaches step 18, ``SEND_SEALED`` is recorded before
    ``NETWORK_CALL_ENTERED``, the adapter runs in dry_run (``TRANSPORT_DRY_RUN`` — byte-seal
    identity holds), the result is ``UNKNOWN`` re-injected as ``EGRESS_RESULT`` with the
    reservation quarantined, and zero sockets are opened."""
    _activate_and_admit(config_dir, custody_root)
    fx.write_kis_mock_transport_config(config_dir)  # mode: dry_run (default)
    _lift_phase5_deferred_mesh(monkeypatch)
    _lift_p02_capability_profile(monkeypatch)
    _lift_venue_session_account_facts(monkeypatch)
    do_request_calls = _spy_do_request(monkeypatch)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is True

    assert _evidence_row_order(runtime, "SEND_SEALED") is not None
    assert _evidence_row_order(runtime, "NETWORK_CALL_ENTERED") is not None
    assert _evidence_row_order(runtime, "SEND_SEALED") < _evidence_row_order(
        runtime, "NETWORK_CALL_ENTERED"
    )

    (dry_run_row,) = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'TRANSPORT_DRY_RUN'"
    ).fetchall()
    dry_run_payload = json.loads(dry_run_row[0])["payload"]

    (seal_row,) = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'SEND_SEALED'"
    ).fetchall()
    seal_payload = json.loads(seal_row[0])["payload"]["send_seal"]

    independent_digest = _independent_wire_digest(
        account=seal_payload["account"],
        instrument=seal_payload["instrument_key"]["instrument"],
        quantity=seal_payload["outbound_quantity"],
        price=seal_payload["outbound_price"],
    )

    # Byte-seal identity (plan §5): the dry-run evidence's own digest, the seal's own
    # request_bytes_digest, and a hand-built, genuinely independent oracle (reviewer
    # disposition MEDIUM-2 — never calls KisOrderWireCodec) all agree.
    assert (
        dry_run_payload["request_bytes_digest"] == seal_payload["request_bytes_digest"]
    )
    assert dry_run_payload["request_bytes_digest"] == independent_digest

    reservation = runtime.core.ledger.outstanding(fx.instrument_key())
    assert reservation is not None
    assert reservation.capacity_state is CapacityState.QUARANTINED_UNKNOWN

    assert (
        do_request_calls == []
    )  # zero sockets opened — dry_run never reaches the client

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ===========================================================================
# 3. Counterfactual B — live against the hermetic fake KIS server
# ===========================================================================


def test_counterfactual_b_live_against_hermetic_fake_kis_server(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """Same two lifts + ``mode: live`` (loader reached with ``codec_bound=True`` through the
    real compose root) + ``allow_plaintext_for_tests: true`` + the hermetic fake KIS server
    answering token + order with ``rt_cd == "0"`` and an ``ODNO``: exactly one order POST, its
    body bytes' sha256 equals the seal's ``request_bytes_digest``, ``ACK`` with
    ``broker_execution_id == ODNO`` observed exactly once, and no secret bytes anywhere in
    evidence."""
    server.set_response(
        _TOKEN_PATH,
        status=200,
        body={"access_token": _FAKE_BEARER_TOKEN, "expires_in": 86400},
    )
    server.set_response(
        _ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "msg_cd": "APBK0013",
            "msg1": "정상처리",
            "output": {"ODNO": "T3-ODNO-1"},
        },
    )
    _patch_instance_documents_to_host(monkeypatch, mock_rest_base=server.rest_base)
    _activate_and_admit(config_dir, custody_root)
    fx.write_kis_mock_transport_config(
        config_dir,
        mode="live",
        endpoint_rest_base=server.rest_base,
        allow_plaintext_for_tests=True,
    )
    _lift_phase5_deferred_mesh(monkeypatch)
    _lift_p02_capability_profile(monkeypatch)
    _lift_venue_session_account_facts(monkeypatch)
    send_once_calls = _spy_send_once(monkeypatch)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is True

    order_requests = server.requests_for(_ORDER_PATH)
    assert len(order_requests) == 1
    (order_request,) = order_requests

    (seal_row,) = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'SEND_SEALED'"
    ).fetchall()
    seal_payload = json.loads(seal_row[0])["payload"]["send_seal"]

    _assert_byte_seal_identity_and_result_ordering(runtime, order_request, seal_payload)

    assert len(send_once_calls) == 1
    (result_payload,) = send_once_calls
    assert result_payload.kind.value == "ACK"
    assert result_payload.broker_execution_id == "T3-ODNO-1"

    evidence_text = _all_evidence_text(runtime)
    assert _APP_KEY_SECRET_BYTES.decode() not in evidence_text
    assert _APP_SECRET_SECRET_BYTES.decode() not in evidence_text
    assert _FAKE_BEARER_TOKEN not in evidence_text

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ===========================================================================
# 4. Mutations pinned as tests (plan §4 T3 row)
# ===========================================================================


def test_mutation_a_retry_loop_would_be_caught_by_the_existing_negative_grep() -> None:
    """(a) Add a retry loop to a scratch COPY of the real adapter.py source (never written to
    disk) and confirm the SAME detector
    ``tos.runtime.tests.transport.kis_mock.test_adapter
    ._retry_primitive_offenders_excluding_pacing`` (imported, not re-implemented) that backs the
    landed, production negative-grep test
    ``tos/runtime/tests/transport/kis_mock/test_adapter.py
    ::test_no_retry_primitive_anywhere_in_the_package_except_the_pacing_helper`` flags it — a
    real retry loop landing in ``adapter.py`` outside ``_enforce_pacing`` would turn THAT test
    red, since it scans the real package files with this exact helper.
    """
    adapter_path = Path(
        Path(__file__).resolve().parents[2]
        / "src"
        / "tos_runtime"
        / "transport"
        / "kis_mock"
        / "adapter.py"
    )
    real_source = adapter_path.read_text(encoding="utf-8")
    mutated_source = real_source + (
        "\n\n"
        "def _t3_planted_retry(client):\n"
        "    for _attempt in range(3):\n"
        "        client.post_order()\n"
    )
    offenders = _retry_primitive_offenders_excluding_pacing(
        mutated_source, adapter_path
    )
    assert offenders != []
    assert any("for ... in range(...)" in offender for offender in offenders)

    # Control: the UN-mutated real source is clean (today) — proves the mutation, not some
    # pre-existing offender, is what the assertion above is catching.
    assert _retry_primitive_offenders_excluding_pacing(real_source, adapter_path) == []


def test_mutation_b_a_digest_mismatch_is_refused_before_any_network_call(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(b) Corrupt the seal the adapter reads (the narrowest seam that stands in for "the
    adapter's digest comparison was removed": a mismatched ``request_bytes_digest`` sails
    through ``send_once`` unchallenged) and confirm the REAL, unmutated
    :meth:`~tos_runtime.transport.kis_mock.adapter.KisMockTransport._prepare_send` catches it —
    ``TRANSPORT_BINDING_MISMATCH`` evidence, ``SendRefused`` (the gateway's own
    ``TRANSPORT_RAISED``), and zero POSTs. If that digest-comparison ``if`` in ``adapter.py``
    were ever deleted, THIS test's ``do_request_calls == []`` / ``accepted_for_transmission is
    not True`` assertions would go red — the corrupted seal would instead sail through to a
    live POST carrying a body that does not match what was sealed.
    """
    _activate_and_admit(config_dir, custody_root)
    fx.write_kis_mock_transport_config(config_dir)
    _lift_phase5_deferred_mesh(monkeypatch)
    _lift_p02_capability_profile(monkeypatch)
    _lift_venue_session_account_facts(monkeypatch)
    do_request_calls = _spy_do_request(monkeypatch)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)

    # Wrap the SealRegistry AFTER compose so the gateway still captures+wires normally, but the
    # adapter's own SealLookup port resolves a digest-corrupted copy — a mismatched
    # request_bytes_digest is exactly "the sealed request bytes were not what was actually
    # built", the one fact decision 3's digest check exists to catch.
    real_seal_lookup = runtime.transport._seal_lookup  # noqa: SLF001

    def _corrupting_lookup(attempt_id: str) -> Any:
        seal = real_seal_lookup(attempt_id)
        if seal is None:
            return None
        return seal.model_copy(
            update={"request_bytes_digest": "t3-mutation-pin-deliberately-mismatched"}
        )

    monkeypatch.setattr(runtime.transport, "_seal_lookup", _corrupting_lookup)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is not True

    (mismatch_row,) = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'TRANSPORT_BINDING_MISMATCH'"
    ).fetchall()
    mismatch_payload = json.loads(mismatch_row[0])["payload"]
    assert mismatch_payload["sealed_request_bytes_digest"] == (
        "t3-mutation-pin-deliberately-mismatched"
    )

    (send_refused_row,) = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'SEND_REFUSED' "
        "AND payload_json LIKE '%TRANSPORT_RAISED%'"
    ).fetchall()
    assert send_refused_row is not None
    assert do_request_calls == []

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_mutation_c_lifting_only_the_deferred_gate_still_denies(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(c) Lift ONLY the deferred Phase 5 mesh (item 6/12's own P0-2 facts untouched) — pins T2
    §9 잔여 ①: still denied, transport still 0."""
    _activate_and_admit(config_dir, custody_root)
    fx.write_kis_mock_transport_config(config_dir)
    _lift_phase5_deferred_mesh(monkeypatch)
    send_once_calls = _spy_send_once(monkeypatch)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is not True
    assert send_once_calls == []
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 0

    verdicts = _verify_item_payloads(runtime)
    (item6_verdict,) = (
        v
        for v in verdicts
        if v["item"] == "ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY"
    )
    assert item6_verdict["outcome"] == "DENIED"

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_mutation_d_lifting_only_p02_capability_profile_still_denies(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(d) Lift ONLY item 6/12's P0-2 capability-profile facts (the deferred mesh untouched) —
    the mirror of (c): still denied, transport still 0."""
    _activate_and_admit(config_dir, custody_root)
    fx.write_kis_mock_transport_config(config_dir)
    _lift_p02_capability_profile(monkeypatch)
    send_once_calls = _spy_send_once(monkeypatch)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is not True
    assert send_once_calls == []
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 0

    verdicts = _verify_item_payloads(runtime)
    unknown_items = {v["item"] for v in verdicts if v["outcome"] == "UNKNOWN"}
    # This lift never touched the deferred mesh — 5 of 6 DEFERRED_ITEMS are genuinely
    # SATISFIED by their real Phase 5 W3 owners regardless (module docstring); only item 5
    # (VALID_LIVE_SCOPE) is still honestly UNKNOWN, which alone still denies the send.
    assert "VALID_LIVE_SCOPE" in unknown_items

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_mutation_e_lifting_only_venue_session_account_facts_switches_the_item12_reason(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(e) TOS Phase 5 W5 — the mirror of mutation (d): lift ONLY the venue-half
    sub-facts (the P0-2 capability-profile facts untouched). Item 12's outcome
    SWITCHES from UNKNOWN to the OTHER branch's own outcome — DENIED, not
    UNKNOWN (kernel round #3 §11 결정 5: ``broker_constraint_generation_current``
    is a strict ``bool`` here, and the DRAFT/unapproved-INSTANCE P0-2 gap makes
    it honestly ``False``, which now denies explicitly rather than folding into
    ``UNKNOWN``) — and the reason text names the broker-constraint half,
    proving the two reasons are genuinely independent and distinguishable, not
    one fact silently masking the other."""
    _activate_and_admit(config_dir, custody_root)
    fx.write_kis_mock_transport_config(config_dir)
    _lift_venue_session_account_facts(monkeypatch)
    send_once_calls = _spy_send_once(monkeypatch)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is not True
    assert send_once_calls == []

    verdicts = _verify_item_payloads(runtime)
    (item12_verdict,) = (
        v
        for v in verdicts
        if v["item"] == "VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION"
    )
    assert item12_verdict["outcome"] == "DENIED"
    assert "broker-constraint generation" in item12_verdict["detail"]
    assert "venue / session" not in item12_verdict["detail"]

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ===========================================================================
# 5. Honesty guard — no monkeypatch, live mode, a REACHABLE server: still 0 POSTs
# ===========================================================================


def test_honesty_guard_no_monkeypatch_live_mode_against_reachable_server_still_zero_posts(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """With NO monkeypatch at all — the real gates hold even when ``mode: live`` is configured
    and a server IS listening and ready to answer: the deferred mesh + P0-2 facts deny before
    the transport is ever constructed a network call for, so the reachable server receives
    nothing."""
    server.set_response(
        _TOKEN_PATH,
        status=200,
        body={"access_token": _FAKE_BEARER_TOKEN, "expires_in": 86400},
    )
    server.set_response(
        _ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "msg_cd": "APBK0013",
            "msg1": "정상처리",
            "output": {"ODNO": "X"},
        },
    )
    _patch_instance_documents_to_host(monkeypatch, mock_rest_base=server.rest_base)
    _activate_and_admit(config_dir, custody_root)
    fx.write_kis_mock_transport_config(
        config_dir,
        mode="live",
        endpoint_rest_base=server.rest_base,
        allow_plaintext_for_tests=True,
    )
    send_once_calls = _spy_send_once(monkeypatch)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is not True

    assert server.all_requests == []
    assert send_once_calls == []
    assert _evidence_kind_like_count(runtime, "TRANSPORT_%") == 0

    runtime.rcl_log.close()
    runtime.evidence_store.close()
