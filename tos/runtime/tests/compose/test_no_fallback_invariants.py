"""§2-4 of the TOS rescope plan, collected in one module: **no MOCK → REAL order
fallback, and a read-only principal never reaches an order endpoint.**

``docs/plans/2026-10-22-tos-rescope-plan.md`` §2 sentence 4 — the one thing that plan
refuses to shrink — requires that these two refusals be in a CI-required check. They
were, but scattered across five files, each pinning one clause of one of them:

* ``compose/test_kis_mock_e2e_honesty.py::test_a_real_scope_with_the_kis_mock_transport
  _refuses_to_boot`` — the end-to-end boot refusal for ``REAL_ORDER`` and ``REAL_READ``
  on the kis-mock transport. It accepts whichever of three checks fires first, so it
  pins THAT the boot refuses, not WHICH clause refuses, and it covers only that one
  transport kind.
* ``compose/test_transport_wiring.py::test_full_sweep_every_scope_x_both_kinds`` — the
  scope × transport-kind sweep, by scope NAME.
* ``transport/kis_mock/test_config.py`` — the order transport's host seal: a REAL
  ``rest_base``, however spelled, is refused (the MOCK → REAL direction at the wire).
* ``transport/kis_quote/test_config.py::test_non_conforming_tr_id_refuses`` — an ORDER
  TR id (``VTTC0012U`` / ``TTTC0011U``) typed into the read-only quote transport's
  config is refused: the quote intake cannot be pointed at an order TR at all.
* ``tos/tests/brokercap/test_brokercap_fallback.py`` — the kernel's own
  approved-fallback predicates.

**What nothing asserted, and this module does.** That no READ-class principal can hold
an order surface at all — not in any committed scope table, and not after the config
edits an operator reaching for a fallback would actually make. The clauses below are
each one concrete failing input against the REAL loader
(:func:`~tos_runtime.brokercap.scopes.load_broker_scopes`) and the REAL transport wiring
(:func:`~tos_runtime.compose._transport_wiring.refuse_transport_scope_mismatch`) —
nothing here stands in for the thing under test, and nothing here re-authors a clause
that already exists in one of the five files above.

Measured while writing this (2026-10-29, shipped ``broker_scopes.example.yaml`` plus the
four deployed trees): the read-only principal has NO path to an order endpoint. Five
independent rules close it, and each one has its own test below —

1. every committed READ scope declares ``endpoint_class: BROKER_GET``, GET-only methods
   and ``NON_AUTHORIZING_READ`` tuples (:func:`test_no_committed_read_scope_declares_an
   _order_surface`);
2. a READ scope is refused by BOTH transport kinds, so no boot composes an order
   transport while a read principal is the active scope
   (:func:`test_a_read_scope_can_never_be_the_active_scope_of_either_transport`);
3. a READ scope cannot ACQUIRE an admissible order capability: the only two admissible
   order tuples in this system (``BROKER_SIMULATION`` × ``STOCK`` × ``MOCK_ORDER``) are
   already held by ``MOCK_STOCK_ORDER``, so claiming one is a duplicate-tuple refusal,
   and every other order tuple is ``PROHIBITED``
   (:func:`test_a_read_scope_cannot_acquire_an_order_capability`);
4. the read credential can never be the order credential
   (:func:`test_the_read_principal_can_never_be_the_order_principal`);
5. and — the rule clause 3 turned out to be standing in for — the loader itself refuses
   a ``principal_class: READ`` scope whose endpoint, methods or tuples are not read-only,
   by allowlist, whether or not an order scope exists beside it
   (:func:`test_the_loader_refuses_a_read_scope_that_is_not_read_only`; #999, from
   review-998 r1's bypass input).

Clauses 1 and 2 sweep every committed scope table, and
:func:`test_the_sweep_sees_every_deployed_tree` is what keeps that sweep honest: the
shipped example is a constant in :data:`_SCOPE_TABLES` while the deployed trees come
from a glob, so a glob that matched nothing would leave both clauses green on the
example alone (review-998 r1 MEDIUM).

Hermetic (``tos/runtime/tests/conftest.py`` D1.4): the committed config files and the
broker-profile INSTANCE document are only ever READ; every write goes to ``tmp_path``.
"""

from __future__ import annotations

import copy
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.brokercap.routing import AuthorizationClass, OperationClass
from tos_runtime.brokercap.scopes import (
    BrokerScopeConfigError,
    BrokerScopesConfig,
    EndpointClass,
    PrincipalClass,
    load_broker_scopes,
)
from tos_runtime.compose._transport_wiring import (
    TransportKind,
    TransportWiringError,
    refuse_transport_scope_mismatch,
)

from .test_transport_wiring import _BROKER_SCOPES_EXAMPLE_PATH, _ENVIRONMENT_LABEL

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]

#: The deployed config trees' root. Its SUBDIRECTORIES are the independent source for
#: "how many deployed scope tables there should be" — see
#: :func:`test_the_sweep_sees_every_deployed_tree`.
_DEPLOY_ROOT = _REPO_ROOT / "config" / "tos_runtime"

#: The deployed scope tables (resident + the CP-3 tenants). A GLOB, not a list — a tree
#: added later joins this sweep the day it lands, which is the hole a hand-written list
#: leaves.
_DEPLOYED_SCOPE_TABLES: tuple[Path, ...] = tuple(
    sorted(_DEPLOY_ROOT.glob("*/broker_scopes.yaml"))
)

#: Every committed scope table: the shipped example plus the deployed ones.
#:
#: ⚠ The example is a CONSTANT and the rest is a glob, so a glob that matched nothing
#: would leave this tuple non-empty and every parametrized clause below would still be
#: GREEN — on the example alone, with the deployed trees silently out of the sweep
#: (review-998 r1 MEDIUM). :func:`test_the_sweep_sees_every_deployed_tree` is what makes
#: that state red; it is deliberately NOT a bare "the glob is non-empty" assertion, which
#: a single surviving table would satisfy.
_SCOPE_TABLES: tuple[Path, ...] = (
    _BROKER_SCOPES_EXAMPLE_PATH,
    *_DEPLOYED_SCOPE_TABLES,
)

#: The operation classes a read scope's own capability tuples may carry. The complement
#: — ``ORDER_SEND`` / ``CANCEL_REPLACE`` — is what
#: :data:`tos.brokercap.routing._ORDER_MUTATING_OPERATIONS` names as broker-order-state
#: mutating.
_READ_OPERATIONS = frozenset(
    {
        OperationClass.MARKET_DATA_READ,
        OperationClass.ACCOUNT_READ,
        OperationClass.CAPABILITY_PROBE,
    }
)

#: What each transport kind's refusal SAYS, so clause 2 pins the REASON and not merely
#: the exception type (review-998 r1 LOW). A kind whose message stopped naming its own
#: condition — or a refusal that moved to a different clause — is worth looking at rather
#: than silently still green.
_REFUSAL_BY_KIND: Mapping[TransportKind, str] = {
    TransportKind.KIS_MOCK: "MOCK-shaped under BROKER_SIMULATION",
    TransportKind.SYNTHETIC: "non-broker-reaching (reaches_broker is False)",
}

#: The two admissible order tuples in this system, both held by ``MOCK_STOCK_ORDER``
#: (``broker_scopes.example.yaml``). Named here because clause 3's first input is
#: "a READ scope claims one of them".
_MOCK_STOCK_ORDER_SEND: Mapping[str, str] = {
    "environment": "BROKER_SIMULATION",
    "operation_class": "ORDER_SEND",
    "economic_effect": "BROKER_RESOURCE_ONLY",
    "asset_scope": "STOCK",
    "authorization_class": "MOCK_ORDER",
}


def _table_id(path: Path) -> str:
    return path.parent.name if path.name == "broker_scopes.yaml" else path.stem


def _raw(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), path
    return raw


def _load(
    path: Path,
    tmp_path: Path,
    *,
    active_scope: str | None = None,
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> BrokerScopesConfig:
    """Load ``path`` through the REAL loader, optionally with ``active_scope`` forced and
    ``mutate`` applied to the raw mapping first.

    The copy lands in ``tmp_path`` (D1.4) and its ``instance_path`` is re-expressed
    relative to that directory from whatever the original resolved to — never a literal
    path to the INSTANCE document, so a table that binds a different one still loads the
    one it names.
    """
    raw = copy.deepcopy(_raw(path))
    if active_scope is not None:
        raw["active_scope"] = active_scope
    if mutate is not None:
        mutate(raw)
    instance = (path.parent / str(raw["instance_path"])).resolve()
    raw["instance_path"] = os.path.relpath(instance, tmp_path)
    copied = tmp_path / f"broker_scopes_{_table_id(path)}.yaml"
    copied.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(copied, environment_label=_ENVIRONMENT_LABEL)


def _scope(raw: dict[str, Any], name: str) -> dict[str, Any]:
    return next(scope for scope in raw["scopes"] if scope["name"] == name)


def _read_scope_names(path: Path) -> tuple[str, ...]:
    """The READ-class scope names in ``path``, read from the file itself (the loader is
    not available before an ``active_scope`` is chosen, which is what this answers)."""
    return tuple(
        str(scope["name"])
        for scope in _raw(path)["scopes"]
        if scope.get("principal_class") == PrincipalClass.READ.value
    )


# ===========================================================================
# The sweep's own coverage (review-998 r1 MEDIUM)
# ===========================================================================


def test_the_sweep_sees_every_deployed_tree() -> None:
    """**Every deployed tree contributes exactly one scope table to the clauses below.**

    The expected set comes from the DIRECTORY LISTING, not from the glob that builds the
    sweep: comparing the glob against itself would be a tautology, and the state this
    exists to catch is the glob matching FEWER files than there are trees.

    Two concrete inputs it turns red, both of which leave :data:`_SCOPE_TABLES`
    non-empty — the example is a constant — so every clause below would otherwise stay
    green on the example alone while saying nothing about what production boots:

    * the glob matches nothing at all (``config/tos_runtime/`` moved, the file renamed);
    * one tree loses its own ``broker_scopes.yaml`` while the others keep theirs.

    A directory that is deliberately not a deployment tree would also turn this red,
    which is the intended direction: it is then a one-line decision here rather than a
    silent gap, the same discipline ``test_tenant_tree_copies.py``'s own exhaustiveness
    test applies to the files inside each tree.
    """
    trees = sorted(path.name for path in _DEPLOY_ROOT.iterdir() if path.is_dir())
    assert trees, f"{_DEPLOY_ROOT} holds no deployed tree — has it moved?"
    swept = sorted(path.parent.name for path in _DEPLOYED_SCOPE_TABLES)
    assert swept == trees, (
        f"the sweep covers {swept} but {_DEPLOY_ROOT} holds {trees} — "
        f"{sorted(set(trees) - set(swept))} contribute no broker_scopes.yaml, so the "
        "clauses below say nothing about them"
    )


# ===========================================================================
# Clause 1 — no committed READ scope declares an order surface
# ===========================================================================


@pytest.mark.parametrize("table", _SCOPE_TABLES, ids=_table_id)
def test_no_committed_read_scope_declares_an_order_surface(
    table: Path, tmp_path: Path
) -> None:
    """**Every committed scope table, through the real loader.**

    A read principal with ``endpoint_class: BROKER_ORDER``, a non-GET method, or an
    order-mutating capability tuple would be a read credential with an order route
    declared on the config surface the operator reads — §2-4's own failing shape. The
    deployed trees are swept as well as the example, because the example is not what
    production boots.

    The ``assert read_scopes`` is not decoration: without it a table that dropped its
    READ scope (or renamed the class) would make every assertion below vacuous and this
    test would still be green.
    """
    config = _load(table, tmp_path, active_scope=_read_scope_names(table)[0])
    read_scopes = [
        scope for scope in config.scopes if scope.principal_class is PrincipalClass.READ
    ]
    assert read_scopes, f"{table}: no READ-class scope — the sweep below is vacuous"
    order_principals = {
        scope.principal
        for scope in config.scopes
        if scope.principal_class is PrincipalClass.ORDER
    }
    assert order_principals, f"{table}: no ORDER-class scope to be separate FROM"
    for scope in read_scopes:
        where = f"{table}::{scope.name}"
        assert scope.endpoint_class is EndpointClass.BROKER_GET, where
        assert scope.allowed_methods == ("GET",), f"{where}: {scope.allowed_methods}"
        assert scope.principal not in order_principals, where
        for capability in scope.capability_tuples:
            assert capability.operation_class in _READ_OPERATIONS, (
                where,
                capability.operation_class,
            )
            assert (
                capability.authorization_class
                is AuthorizationClass.NON_AUTHORIZING_READ
            ), (where, capability.authorization_class)


# ===========================================================================
# Clause 2 — a READ scope composes NEITHER transport
# ===========================================================================


@pytest.mark.parametrize("kind", list(TransportKind), ids=lambda k: k.value)
@pytest.mark.parametrize("table", _SCOPE_TABLES, ids=_table_id)
def test_a_read_scope_can_never_be_the_active_scope_of_either_transport(
    table: Path, kind: TransportKind, tmp_path: Path
) -> None:
    """**The order path is not composable while a read principal is active.**

    ``tos_runtime`` has exactly two transport kinds, and the order egress is built for
    one of them. Activating a READ scope and asking the real wiring for EITHER kind must
    refuse: ``kis-mock`` because the scope's tuples are not MOCK-shaped under
    ``BROKER_SIMULATION`` (a READ scope binds ``BROKER_PRODUCTION``, which is also the
    MOCK → REAL direction the host seal refuses at the wire), ``synthetic`` because a
    ``BROKER_GET`` scope IS broker-reaching and a synthetic boot requires that it not be.

    So there is no (read scope, transport kind) pair that composes an order sender at
    all — which is the "can never reach" half of §2-4, stated over every committed
    table rather than over one hand-picked scope name.

    The refusal's own REASON is pinned per kind (:data:`_REFUSAL_BY_KIND`), not just the
    exception type: both kinds raise the same ``TransportWiringError``, so without that
    a refusal arriving for an unrelated reason — a malformed copy, a renamed scope —
    would read as this invariant holding.
    """
    expected = _REFUSAL_BY_KIND.get(kind)
    assert expected is not None, f"no refusal reason pinned for transport kind {kind}"
    for name in _read_scope_names(table):
        config = _load(table, tmp_path, active_scope=name)
        with pytest.raises(TransportWiringError) as refusal:
            refuse_transport_scope_mismatch(kind, config)
        message = str(refusal.value)
        assert name in message, message
        assert expected in message, message


# ===========================================================================
# Clause 3 — a READ scope cannot ACQUIRE an order capability
# ===========================================================================


@pytest.mark.parametrize(
    ("capability", "refusal_says"),
    [
        pytest.param(
            # The tuple MOCK_STOCK_ORDER already holds — there is no second admissible
            # order tuple to claim instead.
            _MOCK_STOCK_ORDER_SEND,
            "appears in both",
            id="mock-stock-order-send",
        ),
        pytest.param(
            # A MOCK futures order: PROHIBITED (the futures account is never funded).
            {**_MOCK_STOCK_ORDER_SEND, "asset_scope": "FUTURES"},
            "is PROHIBITED",
            id="mock-futures-order-send",
        ),
        pytest.param(
            # A REAL order: PROHIBITED — no sanctioned real-order path exists for any
            # asset in this repo.
            {
                **_MOCK_STOCK_ORDER_SEND,
                "environment": "BROKER_PRODUCTION",
                "authorization_class": "REAL_ORDER",
            },
            "is PROHIBITED",
            id="real-order-send",
        ),
    ],
)
def test_a_read_scope_cannot_acquire_an_order_capability(
    capability: Mapping[str, str], refusal_says: str, tmp_path: Path
) -> None:
    """**The config edit an operator reaching for a fallback would actually make.**

    Give the read scope the whole order surface — ``endpoint_class: BROKER_ORDER``, a
    ``SUBMIT`` method, the MOCK_VTS instance binding, ``profile_evidence_ok: true`` — and
    one order capability tuple. All three inputs are refused AT LOAD, each by a rule that
    names no forbidden endpoint or method, only this table's own contents:

    * the two admissible order tuples (``BROKER_SIMULATION`` × ``STOCK`` × ``MOCK_ORDER``)
      are already held by ``MOCK_STOCK_ORDER``, and no two scopes may carry the same
      tuple (finding F3), so there is no admissible order tuple left to claim;
    * every other order tuple is ``PROHIBITED`` by
      :func:`~tos.brokercap.routing.routing_admissibility` — futures mock orders and ALL
      production orders — and the loader refuses a PROHIBITED ``active_scope``.

    Clause 2 above is what a reader might expect to carry this on its own; it does not.
    It asks about the scope as COMMITTED, so without this test a table that handed the
    read principal an order capability would simply make clause 2's refusal disappear.

    Both rules here read the rest of the table, so both stop holding if
    ``MOCK_STOCK_ORDER`` is deleted in the same edit (review-998 r1 measured exactly
    that). Clause 5 is the rule that does not: it reads nothing but the read scope
    itself, and it runs after these two so each input above still refuses for the reason
    this test pins.
    """

    def mutate(raw: dict[str, Any]) -> None:
        scope = _scope(raw, "REAL_READ")
        scope["endpoint_class"] = "BROKER_ORDER"
        scope["allowed_methods"] = ["SUBMIT"]
        scope["profile_evidence_ok"] = True
        scope["instance"] = {
            "environment": "MOCK_VTS",
            "degraded_since_authorization": False,
        }
        scope["profile_key"]["environment"] = "MOCK_VTS"
        scope["capability_tuples"] = [dict(capability)]

    with pytest.raises(BrokerScopeConfigError) as refusal:
        _load(
            _BROKER_SCOPES_EXAMPLE_PATH,
            tmp_path,
            active_scope="REAL_READ",
            mutate=mutate,
        )
    # WHICH rule refuses, not merely that something did: a refusal that moved to another
    # clause would be worth looking at rather than silently still green.
    assert refusal_says in str(refusal.value), str(refusal.value)


# ===========================================================================
# Clause 4 — the read credential is never the order credential
# ===========================================================================


def test_the_read_principal_can_never_be_the_order_principal(tmp_path: Path) -> None:
    """**The second shape of "the read-only principal reaches an order endpoint": keep
    the scopes apart and give the ORDER scope the READ principal's credential.**

    Nothing about the order path's own checks would notice — the custody manifest's
    principal would equal the active scope's principal, which is all
    :func:`~tos_runtime.compose._transport_wiring.refuse_custody_principal_mismatch`
    asks. The refusal is the loader's, through the kernel predicate
    :func:`~tos.brokercap.routing.credential_principal_separation_ok`, and it names both
    scopes.
    """

    def mutate(raw: dict[str, Any]) -> None:
        read_principal = _scope(raw, "REAL_READ")["principal"]
        _scope(raw, "MOCK_STOCK_ORDER")["principal"] = read_principal
        _scope(raw, "MOCK_STOCK_ORDER")["profile_evidence_ok"] = True

    with pytest.raises(BrokerScopeConfigError) as refusal:
        _load(
            _BROKER_SCOPES_EXAMPLE_PATH,
            tmp_path,
            active_scope="MOCK_STOCK_ORDER",
            mutate=mutate,
        )
    message = str(refusal.value)
    assert "share principal" in message, message
    assert "REAL_READ" in message and "MOCK_STOCK_ORDER" in message, message


# ===========================================================================
# Clause 5 — the loader itself refuses a READ scope that is not read-only
# ===========================================================================

#: review-998 r1's bypass input (issue #999): the order surface it moved onto
#: ``REAL_READ`` — endpoint class, methods, MOCK_VTS instance binding, positive profile
#: evidence and one order tuple — while leaving ``principal_class: READ`` in place.
_ORDER_SURFACE: Mapping[str, Any] = {
    "endpoint_class": "BROKER_ORDER",
    "allowed_methods": ["SUBMIT", "CANCEL_REPLACE"],
    "capability_tuples": [dict(_MOCK_STOCK_ORDER_SEND)],
}


def _order_shaped_read_scope(raw: dict[str, Any], **fields: Any) -> None:
    """Apply ``fields`` to ``REAL_READ`` and DELETE ``MOCK_STOCK_ORDER``.

    The deletion is review-998 r1's own input and the reason this clause exists: with
    the order scope gone, the duplicate-tuple refusal clause 3 relies on has nothing
    left to collide with, so every input below loads unless the loader itself checks
    ``principal_class`` against the scope's own surface.
    """
    raw["scopes"] = [
        scope for scope in raw["scopes"] if scope["name"] != "MOCK_STOCK_ORDER"
    ]
    scope = _scope(raw, "REAL_READ")
    scope["profile_evidence_ok"] = True
    scope["instance"] = {
        "environment": "MOCK_VTS",
        "degraded_since_authorization": False,
    }
    scope["profile_key"]["environment"] = "MOCK_VTS"
    scope.update(fields)


@pytest.mark.parametrize(
    ("fields", "offending_field"),
    [
        pytest.param(
            dict(_ORDER_SURFACE), "endpoint_class", id="review-998-order-surface"
        ),
        pytest.param(
            {"allowed_methods": ["GET", "SUBMIT"]},
            "allowed_methods",
            id="a-non-GET-method-beside-GET",
        ),
        pytest.param(
            {"capability_tuples": [dict(_MOCK_STOCK_ORDER_SEND)]},
            "capability_tuples[0].operation_class",
            id="an-order-tuple-under-a-GET-endpoint",
        ),
    ],
)
def test_the_loader_refuses_a_read_scope_that_is_not_read_only(
    fields: Mapping[str, Any], offending_field: str, tmp_path: Path
) -> None:
    """**``principal_class: READ`` means BROKER_GET, GET and read-only tuples — checked
    by the loader, not inferred from the presence of a neighbouring order scope.**

    Clause 3's refusals all depend on ``MOCK_STOCK_ORDER`` existing: it is what owns the
    only two admissible order tuples, so claiming one is a duplicate. Delete that scope
    first — one line of YAML — and the read scope can take the whole order surface
    (review-998 r1 finding 2, measured against this loader before issue #999: the table
    loaded and the kis-mock wiring accepted it). No real order resulted, because the MOCK
    host seal and the custody principal stop it, but §2-4's own shape — a READ principal
    holding an order endpoint — was reachable by config edit alone.

    The three inputs are the three surfaces a READ scope has: its endpoint class, its
    methods, and its capability tuples. Each is refused AT LOAD naming the scope and the
    field, and what the loader checks is an ALLOWLIST of what READ may carry
    (``BROKER_GET`` / ``GET`` / ``NON_AUTHORIZING_READ`` read operations with no economic
    effect), not a list of order-shaped names to forbid — so an axis member added to the
    kernel later stays out of a read scope until someone lists it on purpose.
    """
    with pytest.raises(BrokerScopeConfigError) as refusal:
        _load(
            _BROKER_SCOPES_EXAMPLE_PATH,
            tmp_path,
            active_scope="REAL_READ",
            mutate=lambda raw: _order_shaped_read_scope(raw, **fields),
        )
    message = str(refusal.value)
    assert "REAL_READ" in message, message
    assert offending_field in message, message
    assert "principal_class READ" in message, message
