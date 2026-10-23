"""One normalized REAL-host comparison for every MOCK-only seal and the profile binding
(#932 final review MEDIUM): a REAL host spelled differently is still the REAL host."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos_runtime.recon import witness_kis_config
from tos_runtime.transport.endpoint import (
    EndpointOrigin,
    EndpointOriginError,
    endpoint_origin,
    real_host_problem,
)
from tos_runtime.transport.kis_mock import config as kis_mock_config
from tos_runtime.transport.kis_quote import config as kis_quote_config

_REAL = "https://openapi.koreainvestment.com:9443"
_MOCK = "https://openapivts.koreainvestment.com:29443"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DRAFT = _REPO_ROOT / "docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"

#: The review's four REAL-host spellings that byte-exact comparison let through.
REAL_VARIANTS = [
    "https://openapi.koreainvestment.com:9443/",
    "https://OpenAPI.koreainvestment.com:9443",
    "https://openapi.koreainvestment.com",  # implicit 443 — still the REAL hostname
    "https://openapi.koreainvestment.com.:9443",
]


def test_normalized_origin() -> None:
    real = EndpointOrigin("https", "openapi.koreainvestment.com", 9443)
    assert endpoint_origin(_REAL) == real
    for spelling in (
        "https://openapi.koreainvestment.com:9443/",
        "HTTPS://OpenAPI.KoreaInvestment.com:9443",
        "https://openapi.koreainvestment.com.:9443",
    ):
        assert endpoint_origin(spelling) == real
    assert endpoint_origin("https://openapi.koreainvestment.com") == EndpointOrigin(
        "https", "openapi.koreainvestment.com", 443
    )
    assert endpoint_origin(
        "https://openapi.koreainvestment.com:443"
    ) == endpoint_origin("https://openapi.koreainvestment.com")
    assert endpoint_origin("http://127.0.0.1:8080").port == 8080


@pytest.mark.parametrize(
    "bad",
    [
        "https://user:pw@openapi.koreainvestment.com:9443",
        "https://openapi.koreainvestment.com:9443?x=1",
        "https://openapi.koreainvestment.com:9443#f",
        "https://openapi.koreainvestment.com:9443/uapi",
        "https://openapi.koreainvestment.com:9443//",
        "https://öpenapi.koreainvestment.com:9443",
        "https://xn--penapi-zxa.koreainvestment.com:9443 ",
        " https://openapi.koreainvestment.com:9443",
        "https://openapi.koreainvestment.com:99999",
        "https://openapi..koreainvestment.com:9443",
        "https://openapi.koreainvestment.com..:9443",
        "https://%6Fpenapi.koreainvestment.com:9443",
        "ftp://openapi.koreainvestment.com:9443",
        "https://:9443",
        "",
    ],
)
def test_spellings_that_cannot_be_normalized_honestly_are_refused(bad: str) -> None:
    with pytest.raises(EndpointOriginError):
        endpoint_origin(bad)


def _seals():
    return [
        (
            kis_mock_config._validate_endpoint,
            kis_mock_config.KisMockTransportConfigError,
        ),
        (
            kis_quote_config._validate_endpoint,
            kis_quote_config.KisQuoteTransportConfigError,
        ),
        (
            witness_kis_config._validate_endpoint,
            witness_kis_config.KisWitnessConfigError,
        ),
    ]


@pytest.mark.parametrize("variant", REAL_VARIANTS)
@pytest.mark.parametrize("seal", range(3))
def test_red_a_real_host_variant_as_the_mock_fact_is_refused_at_every_seal(
    variant: str, seal: int
) -> None:
    """The MOCK_VTS document's rest_base set to a REAL-host spelling, the config echoing it
    byte-exact: before, every seal booted against the REAL host."""
    validate, error = _seals()[seal]
    with pytest.raises(error, match="must differ"):
        validate(
            variant,
            instance_mock_rest_base=variant,
            instance_real_rest_base=_REAL,
            allow_plaintext_for_tests=False,
            path=Path("cfg.yaml"),
        )


@pytest.mark.parametrize("variant", REAL_VARIANTS)
def test_an_endpoint_spelling_the_real_host_is_refused(variant: str) -> None:
    assert "equals the INSTANCE REAL_PROD" in (
        real_host_problem(
            variant, instance_mock_rest_base=_MOCK, instance_real_rest_base=_REAL
        )
        or ""
    )


def test_the_genuine_mock_host_passes_every_seal() -> None:
    assert (
        real_host_problem(
            _MOCK, instance_mock_rest_base=_MOCK, instance_real_rest_base=_REAL
        )
        is None
    )
    for validate, _error in _seals():
        validate(
            _MOCK,
            instance_mock_rest_base=_MOCK,
            instance_real_rest_base=_REAL,
            allow_plaintext_for_tests=False,
            path=Path("cfg.yaml"),
        )


@pytest.mark.parametrize("variant", REAL_VARIANTS)
@pytest.mark.parametrize("seal", range(3))
def test_a_config_endpoint_spelling_the_real_host_is_refused_at_every_seal(
    variant: str, seal: int
) -> None:
    validate, error = _seals()[seal]
    with pytest.raises(error, match="equals the INSTANCE REAL_PROD"):
        validate(
            variant,
            instance_mock_rest_base=_MOCK,
            instance_real_rest_base=_REAL,
            allow_plaintext_for_tests=False,
            path=Path("cfg.yaml"),
        )


@pytest.mark.parametrize("variant", REAL_VARIANTS)
def test_red_a_real_host_variant_on_the_mock_document_refuses_to_load(
    tmp_path: Path, variant: str
) -> None:
    """MOCK_VTS's rest_base set to a REAL-host spelling: before, it loaded as a bound
    BROKER_SIMULATION profile."""
    from tos_runtime.brokercap.instance import (
        BrokerInstanceConfigError,
        load_instance_document,
        load_instance_documents,
    )

    text = _DRAFT.read_text(encoding="utf-8")
    old = f'rest_base: "{_MOCK}"'
    assert text.count(old) == 1
    path = tmp_path / "profile.yaml"
    path.write_text(text.replace(old, f'rest_base: "{variant}"'), encoding="utf-8")
    with pytest.raises(BrokerInstanceConfigError, match="REAL host"):
        load_instance_documents(path)
    with pytest.raises(BrokerInstanceConfigError, match="REAL host"):
        load_instance_document(path, environment="MOCK_VTS")


def _rewrite(node: object, old: str, new: str) -> object:
    if isinstance(node, dict):
        return {k: _rewrite(v, old, new) for k, v in node.items()}
    if isinstance(node, list):
        return [_rewrite(v, old, new) for v in node]
    return node.replace(old, new) if isinstance(node, str) else node


@pytest.mark.parametrize("variant", REAL_VARIANTS)
def test_red_a_third_simulation_document_on_a_real_host_variant_does_not_bind(
    tmp_path: Path, variant: str
) -> None:
    """A third document (a copy of MOCK_VTS under another environment name) declaring
    BROKER_SIMULATION on a REAL-host spelling. The REAL host comes only from the REAL_PROD
    document in the same file — no hostname list. Before, it loaded bound."""
    import yaml
    from tos_runtime.brokercap.instance import (
        BrokerInstanceConfigError,
        load_instance_document,
        load_instance_documents,
    )

    docs = list(yaml.safe_load_all(_DRAFT.read_text(encoding="utf-8")))
    (mock,) = [d for d in docs if d["profile_identity"]["environment"] == "MOCK_VTS"]
    third = _rewrite(_rewrite(mock, "MOCK_VTS", "MOCK_VTS_THIRD"), _MOCK, variant)
    assert isinstance(third, dict)
    assert third["profile_identity"]["environment"] == "MOCK_VTS_THIRD"
    path = tmp_path / "profile.yaml"
    path.write_text(
        yaml.safe_dump_all([*docs, third], sort_keys=False), encoding="utf-8"
    )
    # the whole-file load refuses at whichever side it meets first (REAL_PROD now shares a
    # host with a simulation document); the third document alone refuses as REAL-hosted
    with pytest.raises(
        BrokerInstanceConfigError, match="REAL host|a simulation document uses"
    ):
        load_instance_documents(path)
    with pytest.raises(BrokerInstanceConfigError, match="REAL host"):
        load_instance_document(path, environment="MOCK_VTS_THIRD")
    # the genuine MOCK_VTS document in the same file still binds
    assert load_instance_document(
        path, environment="MOCK_VTS"
    ).environment_class_host_bound
