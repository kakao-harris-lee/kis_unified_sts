"""GET-only KIS 모의투자 (VTS) account / tradability facts for item 12 (PR-3a, option (a))."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

import yaml

from tos_runtime._named_tbd import reject_named_tbd
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.account import KisAccountError, split_kis_account
from tos_runtime.transport.kis_mock.client import RawResponse
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSession
from tos_runtime.transport.kis_mock.token import (
    EvidenceRecorder,
)

__all__ = [
    "BROKER_FACTS_CONFIG_NAME",
    "BROKER_FACTS_OBSERVED_KIND",
    "BrokerFactsConfig",
    "BrokerFactsConfigError",
    "BrokerFactsObservation",
    "KisMockBrokerFacts",
    "load_broker_facts_config",
]

BROKER_FACTS_CONFIG_NAME = "broker_facts.yaml"
BROKER_FACTS_OBSERVED_KIND = "BROKER_FACTS_OBSERVED"

_KEYS = (
    "balance_tr_id",
    "balance_path",
    "balance_params",
    "quote_tr_id",
    "quote_path",
    "quote_market_div_code",
    "max_age_ms",
)


class BrokerFactsConfigError(Exception):
    """``broker_facts.yaml`` is missing or malformed — a boot refusal."""


@dataclass(frozen=True)
class BrokerFactsConfig:
    """``broker_facts.yaml``, validated (module docstring)."""

    balance_tr_id: str
    balance_path: str
    balance_params: tuple[tuple[str, str], ...]
    quote_tr_id: str
    quote_path: str
    quote_market_div_code: str
    max_age_ms: int


def load_broker_facts_config(path: Path) -> BrokerFactsConfig:
    """Read and validate ``broker_facts.yaml``."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise BrokerFactsConfigError(f"{path}: cannot be read ({exc})") from exc
    if not isinstance(raw, dict) or set(raw) != set(_KEYS):
        raise BrokerFactsConfigError(
            f"{path}: expected exactly the keys {sorted(_KEYS)}, got "
            f"{sorted(raw) if isinstance(raw, dict) else type(raw).__name__}"
        )
    strings = {k: raw[k] for k in _KEYS if k not in ("balance_params", "max_age_ms")}
    for key, value in strings.items():
        if not isinstance(value, str) or not value:
            raise BrokerFactsConfigError(f"{path}: {key} must be a non-empty string")
        reject_named_tbd(
            value, field=key, context=str(path), error_cls=BrokerFactsConfigError
        )
    if not strings["balance_tr_id"].startswith("V"):
        raise BrokerFactsConfigError(
            f"{path}: balance_tr_id {strings['balance_tr_id']!r} is not a 모의 (V-prefixed) "
            "TR — this source reads the mock account only"
        )
    for key in ("balance_path", "quote_path"):
        if not strings[key].startswith("/"):
            raise BrokerFactsConfigError(f"{path}: {key} must start with '/'")
    params = raw["balance_params"]
    if not isinstance(params, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in params.items()
    ):
        raise BrokerFactsConfigError(
            f"{path}: balance_params must map strings to strings"
        )
    for key, value in params.items():
        reject_named_tbd(
            value,
            field=f"balance_params.{key}",
            context=str(path),
            error_cls=BrokerFactsConfigError,
        )
    if {"CANO", "ACNT_PRDT_CD"} & set(params):
        raise BrokerFactsConfigError(
            f"{path}: balance_params may not carry CANO/ACNT_PRDT_CD — the account comes "
            "from the sealed instrument key, never from config"
        )
    max_age = raw["max_age_ms"]
    if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age < 1:
        raise BrokerFactsConfigError(f"{path}: max_age_ms must be a positive int")
    return BrokerFactsConfig(
        balance_tr_id=strings["balance_tr_id"],
        balance_path=strings["balance_path"],
        balance_params=tuple(sorted(params.items())),
        quote_tr_id=strings["quote_tr_id"],
        quote_path=strings["quote_path"],
        quote_market_div_code=strings["quote_market_div_code"],
        max_age_ms=max_age,
    )


class _GetClient(Protocol):
    def get_quote(
        self,
        tr_id: str,
        query: str,
        *,
        access_token: str,
        app_key: bytes,
        app_secret: bytes,
        path: str,
    ) -> RawResponse: ...


@dataclass(frozen=True)
class BrokerFactsObservation:
    """One refresh: when, and what each GET established."""

    as_of_ms: int
    account_ok: bool
    tradable: bool | None
    reason: str


class KisMockBrokerFacts:
    """Item 12's three broker-side facts from two mock GETs (module docstring)."""

    def __init__(
        self,
        *,
        config: BrokerFactsConfig,
        client: _GetClient,
        credential_session: KisCredentialSession,
        monotonic: MonotonicSource,
        evidence_sink: EvidenceRecorder,
        account: str,
        instrument: str,
    ) -> None:
        self._config = config
        self._client = client
        self._session = credential_session
        self._monotonic = monotonic
        self._evidence = evidence_sink
        self._account = account
        self._instrument = instrument
        self._observation: BrokerFactsObservation | None = None

    def account_facts_current(self) -> bool | None:
        observation = self._current()
        return None if observation is None else observation.account_ok

    def tradability_facts_current(self) -> bool | None:
        observation = self._current()
        if observation is None or observation.tradable is None:
            return None
        return observation.tradable

    def generation_current(self) -> bool | None:
        observation = self._current()
        if observation is None:
            return None
        return observation.account_ok and observation.tradable is not None

    def _current(self) -> BrokerFactsObservation | None:
        observation = self._observation
        if observation is None or self._expired(observation):
            observation = self.refresh()
            if self._expired(observation):
                return None
        return observation

    def _expired(self, observation: BrokerFactsObservation) -> bool:
        return self._monotonic.now_ms() - observation.as_of_ms > self._config.max_age_ms

    def refresh(self) -> BrokerFactsObservation:
        """Two GETs now; replaces the held observation and writes one evidence row."""
        as_of_ms = self._monotonic.now_ms()
        account_ok, tradable, reason = False, None, "ok"
        try:
            token = self._session.ensure_token_string()
            account_ok, reason = self._read_account(token)
            tradable, quote_reason = self._read_tradability(token)
            if reason == "ok":
                reason = quote_reason
        except Exception as exc:  # noqa: BLE001 - fail closed, never crash the resolver
            account_ok, tradable = False, None
            reason = type(exc).__name__
        observation = BrokerFactsObservation(
            as_of_ms=as_of_ms, account_ok=account_ok, tradable=tradable, reason=reason
        )
        self._observation = observation
        self._evidence(
            BROKER_FACTS_OBSERVED_KIND,
            {
                "instrument": self._instrument,
                "account_ok": account_ok,
                "tradable": tradable,
                "reason": reason,
                "balance_tr_id": self._config.balance_tr_id,
                "quote_tr_id": self._config.quote_tr_id,
                "as_of_ms": as_of_ms,
            },
        )
        return observation

    def _get(self, token: str, tr_id: str, path: str, params: dict[str, str]) -> Any:
        with self._session.app_credentials() as credentials:
            response = self._client.get_quote(
                tr_id,
                urlencode(params),
                access_token=token,
                app_key=credentials.app_key(),
                app_secret=credentials.app_secret(),
                path=path,
            )
        return response.json

    def _read_account(self, token: str) -> tuple[bool, str]:
        try:
            account = split_kis_account(self._account)
        except KisAccountError:
            return False, "account_not_kis_8_2"
        body = self._get(
            token,
            self._config.balance_tr_id,
            self._config.balance_path,
            {
                "CANO": account.cano,
                "ACNT_PRDT_CD": account.acnt_prdt_cd,
                **dict(self._config.balance_params),
            },
        )
        if not isinstance(body, dict):
            return False, "balance_malformed"
        if body.get("rt_cd") != "0":
            return False, "balance_rt_cd_not_ok"
        return True, "ok"

    def _read_tradability(self, token: str) -> tuple[bool | None, str]:
        body = self._get(
            token,
            self._config.quote_tr_id,
            self._config.quote_path,
            {
                "FID_COND_MRKT_DIV_CODE": self._config.quote_market_div_code,
                "FID_INPUT_ISCD": self._instrument,
            },
        )
        if not isinstance(body, dict) or body.get("rt_cd") != "0":
            return None, "quote_not_ok"
        output = body.get("output")
        flag = output.get("temp_stop_yn") if isinstance(output, dict) else None
        if flag == "N":
            return True, "ok"
        if flag == "Y":
            return False, "temp_stop_yn=Y"
        return None, "temp_stop_yn_unrecognized"
