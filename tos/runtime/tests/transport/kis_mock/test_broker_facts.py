"""``KisMockBrokerFacts`` — item 12's GET-only mock account / tradability source (PR-3a)."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import pytest
import yaml
from tos_runtime.transport.kis_mock.broker_facts import (
    BROKER_FACTS_OBSERVED_KIND,
    BrokerFactsConfigError,
    KisMockBrokerFacts,
    load_broker_facts_config,
)
from tos_runtime.transport.kis_mock.client import KisMockClientError, RawResponse
from tos_runtime.transport.kis_mock.token import TokenStale

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SHIPPED = _REPO_ROOT / "config/tos_runtime/cp3-setup-d-stock-005930/broker_facts.yaml"
_ACCOUNT = "12345678-01"
_OK_BALANCE = {"rt_cd": "0", "msg1": "ok", "output1": [], "output2": [{}]}


def _quote(flag: object) -> dict[str, Any]:
    return {"rt_cd": "0", "output": {"temp_stop_yn": flag, "stck_prpr": "271500"}}


class _Client:
    """Answers by TR id from a scripted queue; records every GET."""

    def __init__(self, **by_tr: list[object]) -> None:
        self._by_tr = {k: list(v) for k, v in by_tr.items()}
        self.calls: list[dict[str, Any]] = []

    def get_quote(
        self,
        tr_id: str,
        query: str,
        *,
        access_token: str,  # noqa: ARG002
        app_key: bytes,  # noqa: ARG002
        app_secret: bytes,  # noqa: ARG002
        path: str,
    ) -> RawResponse:
        self.calls.append({"tr_id": tr_id, "query": parse_qs(query), "path": path})
        nxt = self._by_tr[tr_id].pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        assert isinstance(nxt, dict)
        return RawResponse(status=200, json=nxt, text=json.dumps(nxt))


class _Credentials:
    def app_key(self) -> bytes:
        return b"key"

    def app_secret(self) -> bytes:
        return b"secret"


class _Session:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    def ensure_token_string(self) -> str:
        if self._error is not None:
            raise self._error
        return "token"

    @contextmanager
    def app_credentials(self) -> Iterator[_Credentials]:
        yield _Credentials()


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000

    def now_ms(self) -> int:
        return self.now


class _Sink:
    def __init__(self) -> None:
        self.rows: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        self.rows.append((kind, dict(fields)))


def _facts(
    client: _Client,
    *,
    session: _Session | None = None,
    account: str = _ACCOUNT,
) -> tuple[KisMockBrokerFacts, _Clock, _Sink]:
    clock, sink = _Clock(), _Sink()
    facts = KisMockBrokerFacts(
        config=load_broker_facts_config(_SHIPPED),
        client=client,
        credential_session=session or _Session(),  # type: ignore[arg-type]
        monotonic=clock,
        evidence_sink=sink,
        account=account,
        instrument="005930",
    )
    return facts, clock, sink


def test_two_good_answers_make_all_three_facts_current() -> None:
    client = _Client(VTTC8434R=[_OK_BALANCE], FHKST01010100=[_quote("N")])
    facts, _, sink = _facts(client)
    assert facts.account_facts_current() is True
    assert facts.tradability_facts_current() is True
    assert facts.generation_current() is True
    # one refresh for the three reads — two GETs, one evidence row
    assert [c["tr_id"] for c in client.calls] == ["VTTC8434R", "FHKST01010100"]
    assert [kind for kind, _ in sink.rows] == [BROKER_FACTS_OBSERVED_KIND]
    balance, quote = client.calls
    assert balance["query"]["CANO"] == ["12345678"]
    assert balance["query"]["ACNT_PRDT_CD"] == ["01"]
    assert balance["path"] == "/uapi/domestic-stock/v1/trading/inquire-balance"
    assert quote["query"] == {
        "FID_COND_MRKT_DIV_CODE": ["J"],
        "FID_INPUT_ISCD": ["005930"],
    }


def test_the_evidence_row_carries_no_account_number_or_secret() -> None:
    client = _Client(VTTC8434R=[_OK_BALANCE], FHKST01010100=[_quote("N")])
    facts, _, sink = _facts(client)
    facts.refresh()
    text = json.dumps(sink.rows)
    for secret in ("12345678", "token", "key", "secret"):
        assert secret not in text.replace("tradable", "").replace("quote_tr_id", "")


def test_a_halted_instrument_is_not_tradable() -> None:
    client = _Client(VTTC8434R=[_OK_BALANCE], FHKST01010100=[_quote("Y")])
    facts, _, _ = _facts(client)
    assert facts.tradability_facts_current() is False
    assert facts.account_facts_current() is True


@pytest.mark.parametrize(
    ("balance", "quote", "account", "tradable", "generation"),
    [
        ({"rt_cd": "1", "msg1": "no"}, _quote("N"), False, True, False),
        (_OK_BALANCE, _quote(None), True, None, False),
        (_OK_BALANCE, _quote(""), True, None, False),
        (_OK_BALANCE, {"rt_cd": "1"}, True, None, False),
        (KisMockClientError("down"), _quote("N"), False, None, False),
    ],
)
def test_a_failed_or_unparseable_answer_is_never_current(
    balance: object,
    quote: object,
    account: bool,
    tradable: bool | None,
    generation: bool,
) -> None:
    client = _Client(VTTC8434R=[balance], FHKST01010100=[quote])
    facts, _, _ = _facts(client)
    assert facts.account_facts_current() is account
    assert facts.tradability_facts_current() is tradable
    assert facts.generation_current() is generation


def test_a_stale_token_is_no_facts_at_all() -> None:
    facts, _, sink = _facts(_Client(), session=_Session(TokenStale("cooldown")))
    assert facts.account_facts_current() is False
    assert facts.tradability_facts_current() is None
    assert facts.generation_current() is False
    assert sink.rows[0][1]["reason"] == "TokenStale"


def test_an_account_that_is_not_ten_digits_is_refused_without_a_balance_get() -> None:
    client = _Client(FHKST01010100=[_quote("N")])
    facts, _, _ = _facts(client, account="1234")
    assert facts.account_facts_current() is False
    assert [c["tr_id"] for c in client.calls] == ["FHKST01010100"]


def test_an_observation_past_max_age_is_refreshed_before_use() -> None:
    client = _Client(
        VTTC8434R=[_OK_BALANCE, {"rt_cd": "1"}],
        FHKST01010100=[_quote("N"), _quote("N")],
    )
    facts, clock, _ = _facts(client)
    assert facts.account_facts_current() is True
    clock.now += 30_000  # exactly max_age: still current, no GET
    assert facts.account_facts_current() is True
    assert len(client.calls) == 2
    clock.now += 1  # past max_age: refresh, and the new answer wins
    assert facts.account_facts_current() is False
    assert len(client.calls) == 4


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


def test_the_shipped_config_names_the_official_trs() -> None:
    config = load_broker_facts_config(_SHIPPED)
    assert (config.balance_tr_id, config.quote_tr_id) == ("VTTC8434R", "FHKST01010100")
    assert config.quote_market_div_code == "J"


@pytest.mark.parametrize(
    ("update", "why"),
    [
        ({"balance_tr_id": "TTTC8434R"}, "not a 모의"),
        ({"balance_path": "uapi/x"}, "must start with"),
        ({"max_age_ms": 0}, "positive int"),
        ({"max_age_ms": True}, "positive int"),
        ({"balance_params": {"CANO": "1"}}, "CANO/ACNT_PRDT_CD"),
        ({"balance_params": {"X": 1}}, "strings to strings"),
        ({"extra": 1}, "exactly the keys"),
        # named-TBD placeholders are refused, not sent to the broker as a TR id / path / param
        ({"quote_tr_id": "TBD"}, "placeholder"),
        ({"balance_path": "TBD"}, "placeholder"),
        ({"balance_params": {"INQR_DVSN": "TBD"}}, "placeholder"),
    ],
)
def test_each_malformed_config_is_refused(
    tmp_path: Path, update: dict[str, Any], why: str
) -> None:
    raw = yaml.safe_load(_SHIPPED.read_text(encoding="utf-8"))
    raw.update(update)
    path = tmp_path / "broker_facts.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(BrokerFactsConfigError, match=why):
        load_broker_facts_config(path)


def test_an_absent_config_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BrokerFactsConfigError, match="cannot be read"):
        load_broker_facts_config(tmp_path / "broker_facts.yaml")
