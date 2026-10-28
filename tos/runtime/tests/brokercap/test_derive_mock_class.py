"""``derive_item6_item12`` under option (a) "K" (operator decision 2026-10-23).

The MOCK_STOCK_ORDER scope (REDUCED, real MOCK_VTS INSTANCE draft) passes item 6 and takes
item 12 from the injected mock-account freshness. Every mutation of its tuples toward real money
— production environment, position/cash effect, real-order authorization, an unknown axis —
falls back to the ordinary rule: REDUCED fails item 6, and item 12 reads the profile approval
the draft does not have, whatever the mock source says.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import pytest
import yaml
from tos.brokercap import (
    AuthorizationClass,
    BrokerEnvironment,
    CapabilityTuple,
    EconomicEffect,
)
from tos_runtime.brokercap import (
    BrokerScopesConfig,
    derive_item6_item12,
    load_active_instance_document,
    load_broker_scopes,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DRAFT = _REPO_ROOT / "docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
_EXAMPLE = Path(__file__).resolve().parents[2] / "config/broker_scopes.example.yaml"


def _mock_scopes(tmp_path: Path) -> BrokerScopesConfig:
    raw = yaml.safe_load(_EXAMPLE.read_text(encoding="utf-8"))
    raw["active_scope"] = "MOCK_STOCK_ORDER"
    raw["instance_path"] = os.path.relpath(
        _DRAFT, tmp_path
    )  # relative, as committed trees (#958)
    for scope in raw["scopes"]:
        if scope["name"] == "MOCK_STOCK_ORDER":
            scope["profile_evidence_ok"] = True
    path = tmp_path / "broker_scopes.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(path, environment_label="non-live-test")


def _with_tuples(
    config: BrokerScopesConfig, tuples: tuple[CapabilityTuple, ...]
) -> BrokerScopesConfig:
    scope = dataclasses.replace(config.active_scope, capability_tuples=tuples)
    return dataclasses.replace(
        config,
        active_scope=scope,
        scopes=tuple(scope if s.name == scope.name else s for s in config.scopes),
    )


def _derive(config: BrokerScopesConfig, generation: bool | None):
    return derive_item6_item12(
        config.active_scope,
        config,
        load_active_instance_document(config),
        mock_generation_current=generation,
    )


def test_the_mock_scope_passes_item_6_and_takes_item_12_from_the_mock_source(
    tmp_path: Path,
) -> None:
    config = _mock_scopes(tmp_path)
    fields = _derive(config, True)
    assert fields.account_instrument_action_allowed is True
    assert fields.broker_constraint_generation_current is True
    assert "mock-account GET freshness" in fields.reason


@pytest.mark.parametrize("generation", [None, False])
def test_a_stale_or_absent_mock_source_fails_item_12(
    tmp_path: Path, generation: bool | None
) -> None:
    fields = _derive(_mock_scopes(tmp_path), generation)
    assert fields.broker_constraint_generation_current is False
    # item 6 is about the scope, not the account read
    assert fields.account_instrument_action_allowed is True


def _mutations(base: CapabilityTuple) -> list[CapabilityTuple]:
    return [
        base.model_copy(update={"environment": BrokerEnvironment.BROKER_PRODUCTION}),
        base.model_copy(update={"economic_effect": EconomicEffect.POSITION_OR_CASH}),
        base.model_copy(update={"authorization_class": AuthorizationClass.REAL_ORDER}),
        CapabilityTuple.model_construct(**{**base.model_dump(), "environment": None}),
        CapabilityTuple.model_construct(
            **{**base.model_dump(), "economic_effect": None}
        ),
    ]


@pytest.mark.parametrize("index", range(5))
def test_each_mutation_toward_real_money_is_refused_on_both_items(
    tmp_path: Path, index: int
) -> None:
    config = _mock_scopes(tmp_path)
    original = config.active_scope.capability_tuples
    mutated = _mutations(original[0])[index]
    fields = _derive(_with_tuples(config, (mutated, *original[1:])), True)
    # REDUCED without the mock class: item 6 refused, as before option (a)
    assert fields.account_instrument_action_allowed is False
    # item 12 ignores the mock source and reads the profile (no approvers -> False)
    assert fields.broker_constraint_generation_current is False


# ---------------------------------------------------------------------------
# The profile's own environment class (#932 Codex r2)
# ---------------------------------------------------------------------------


def test_the_draft_instance_documents_declare_their_environment_class() -> None:
    from tos_runtime.brokercap.instance import load_instance_documents

    classes = {
        d.environment: d.profile.environment_class
        for d in load_instance_documents(_DRAFT)
    }
    assert classes == {
        "MOCK_VTS": BrokerEnvironment.BROKER_SIMULATION,
        "REAL_PROD": BrokerEnvironment.BROKER_PRODUCTION,
    }


@pytest.mark.parametrize(
    "environment_class",
    [BrokerEnvironment.BROKER_PRODUCTION, BrokerEnvironment.SYNTHETIC, None],
)
def test_a_mock_scope_bound_to_a_non_simulation_profile_is_refused_on_both_items(
    tmp_path: Path, environment_class: BrokerEnvironment | None
) -> None:
    """The mock tuples alone no longer make the class: the bound profile must say simulation."""
    config = _mock_scopes(tmp_path)
    instance = load_active_instance_document(config)
    assert instance is not None
    relabelled = dataclasses.replace(
        instance,
        profile=instance.profile.model_copy(
            update={"environment_class": environment_class}
        ),
    )
    fields = derive_item6_item12(
        config.active_scope, config, relabelled, mock_generation_current=True
    )
    assert fields.account_instrument_action_allowed is False
    assert fields.broker_constraint_generation_current is False


def test_an_unknown_environment_class_refuses_to_load(tmp_path: Path) -> None:
    from tos_runtime.brokercap.instance import (
        BrokerInstanceConfigError,
        load_instance_documents,
    )

    text = _DRAFT.read_text(encoding="utf-8").replace(
        "environment_class: BROKER_SIMULATION", "environment_class: SIMULATION_ISH", 1
    )
    path = tmp_path / "profile.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(BrokerInstanceConfigError, match="environment_class"):
        load_instance_documents(path)


# ---------------------------------------------------------------------------
# The class is tied to the document's own host (#932 Codex r3)
# ---------------------------------------------------------------------------

_REAL_HOST = "https://openapi.koreainvestment.com:9443"
_MOCK_HOST = "https://openapivts.koreainvestment.com:29443"


def _edited_draft(tmp_path: Path, *edits: tuple[str, str]) -> Path:
    """The real draft with exact-text edits, each required to hit exactly once."""
    text = _DRAFT.read_text(encoding="utf-8")
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    path = tmp_path / "profile.yaml"
    path.write_text(text, encoding="utf-8")
    return path


_REAL_CLASS = "    environment_class: BROKER_PRODUCTION\n"
_MOCK_CLASS = "    environment_class: BROKER_SIMULATION\n"


def test_the_shipped_documents_are_host_bound() -> None:
    from tos_runtime.brokercap.instance import load_instance_documents

    documents = load_instance_documents(_DRAFT)
    assert all(d.environment_class_host_bound for d in documents)
    hosts = {d.environment: d.rest_base for d in documents}
    assert hosts == {"MOCK_VTS": _MOCK_HOST, "REAL_PROD": _REAL_HOST}


@pytest.mark.parametrize("loader", ["all", "real_only"])
def test_red_codex_r3_real_prod_relabelled_simulation_refuses_to_load(
    tmp_path: Path, loader: str
) -> None:
    """Codex r3's exact input: ONLY REAL_PROD's class flipped. It used to load (REAL_PROD is
    also NON_LIVE with no action classes) and relax item 6 for a production profile."""
    from tos_runtime.brokercap.instance import (
        BrokerInstanceConfigError,
        load_instance_document,
        load_instance_documents,
    )

    path = _edited_draft(
        tmp_path, (_REAL_CLASS, "    environment_class: BROKER_SIMULATION\n")
    )
    with pytest.raises(BrokerInstanceConfigError, match="REAL host"):
        if loader == "all":
            load_instance_documents(path)
        else:
            load_instance_document(path, environment="REAL_PROD")


@pytest.mark.parametrize(
    ("edits", "why"),
    [
        # the MOCK document moved onto the REAL host while still claiming simulation
        (((f'rest_base: "{_MOCK_HOST}"', f'rest_base: "{_REAL_HOST}"'),), "REAL host"),
        # a class nobody can tie to a broker host
        (
            ((_MOCK_CLASS, "    environment_class: SYNTHETIC\n"),),
            "not a broker environment",
        ),
    ],
)
def test_a_class_its_host_does_not_support_refuses_to_load(
    tmp_path: Path, edits: tuple[tuple[str, str], ...], why: str
) -> None:
    from tos_runtime.brokercap.instance import (
        BrokerInstanceConfigError,
        load_instance_documents,
    )

    with pytest.raises(BrokerInstanceConfigError, match=why):
        load_instance_documents(_edited_draft(tmp_path, *edits))


def test_red_codex_r3_a_simulation_profile_on_the_real_host_built_outside_the_loader(
    tmp_path: Path,
) -> None:
    """A REAL-host document carrying a SIMULATION profile, assembled in code (not by the
    loader, so not host-bound): items 6 and 12 refused, and the kernel is handed no profile —
    the gateway takes the normal capability check and DENIES."""
    from tos.egressgw import SendBoundaryContext
    from tos.egressgw.gateway import _check_allowance
    from tos.egressgw.vocabulary import BrokerApplicability, VerifyOutcome

    config = _mock_scopes(tmp_path)
    instance = load_active_instance_document(config)
    assert instance is not None
    # a plain copy of the loaded MOCK document moved onto the REAL host — whatever the loader
    # bound, it bound a different host
    forged = dataclasses.replace(
        instance, environment="REAL_PROD", rest_base=_REAL_HOST
    )
    assert forged.profile.environment_class is BrokerEnvironment.BROKER_SIMULATION
    fields = derive_item6_item12(
        config.active_scope, config, forged, mock_generation_current=True
    )
    assert fields.account_instrument_action_allowed is False
    assert fields.broker_constraint_generation_current is False
    # an un-host-bound class claim never reaches the kernel: no profile at all
    assert fields.broker_capability_profile is None
    verdict = _check_allowance(
        None,  # type: ignore[arg-type]
        SendBoundaryContext(
            capability_tuples=config.active_scope.capability_tuples,
            broker_capability_profile=fields.broker_capability_profile,
            account_instrument_action_allowed=True,
            max_quantity_within_allowance=True,
        ),
        BrokerApplicability.BROKER_RESOURCE_CONSUMING,
    )
    assert verdict.outcome is VerifyOutcome.DENIED


def test_production_declared_on_the_simulation_host_refuses_to_load(
    tmp_path: Path,
) -> None:
    """The REAL document moved onto the MOCK host. Loaded alone so the PRODUCTION branch is
    the one that answers (the all-documents load fails earlier on the MOCK document)."""
    from tos_runtime.brokercap.instance import (
        BrokerInstanceConfigError,
        load_instance_document,
    )

    path = _edited_draft(
        tmp_path, (f'rest_base: "{_REAL_HOST}"', f'rest_base: "{_MOCK_HOST}"')
    )
    with pytest.raises(BrokerInstanceConfigError, match="a simulation document uses"):
        load_instance_document(path, environment="REAL_PROD")


def test_a_file_without_a_real_host_loads_the_simulation_claim_unbound(
    tmp_path: Path,
) -> None:
    """No REAL host to exclude: the claim cannot be proven, so it loads unbound (never read
    as simulation). The transport seal refuses such a file outright."""
    from tos_runtime.brokercap.instance import load_instance_documents

    docs = list(yaml.safe_load_all(_DRAFT.read_text(encoding="utf-8")))
    mock_only = [d for d in docs if d["profile_identity"]["environment"] == "MOCK_VTS"]
    assert len(mock_only) == 1
    path = tmp_path / "mock-only.yaml"
    path.write_text(yaml.safe_dump(mock_only[0], sort_keys=False), encoding="utf-8")
    (document,) = load_instance_documents(path)
    assert document.profile.environment_class is BrokerEnvironment.BROKER_SIMULATION
    assert document.environment_class_host_bound is False
