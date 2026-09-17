"""``KisStockBrokerWitness`` — the real KIS 모의투자 ``BrokerWitness`` (W3 lane,
``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`` §0.4/§2 decision 5/§4
W3/§6.1 처분③).

**Why this class exists.** :class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness`
reads the SAME sqlite evidence store the evidence-receipt path reads, so it hardcodes
``independent_of_evidence_store=False`` (that module's own docstring, independent-review
finding F2) — a ``CORROBORATED`` verdict built from it is a structural label, not
substantive corroboration. This class reads an actual broker (KIS 모의투자) over the
network, so it can honestly set ``independent_of_evidence_store=True`` (never touches the
evidence store — verified structurally by this module's own test suite, a negative-grep
mirroring ``test_witness_synthetic.py::test_module_never_writes_to_the_evidence_store``).

**Scope — both axes of ``WitnessSnapshot`` (operator disposition ③, 2026-09-17).**

* ``positions``/``cash`` — 주식 잔고조회 (stock balance inquiry), mock TR ``VTTC8434R``,
  ``/uapi/domestic-stock/v1/trading/inquire-balance``. Measured:
  ``docs/broker-profiles/evidence/2026-09-11-p02-t3-campaign/P-BAL-20260911T002427Z.json``
  (``measurements.target``, ``measurements.truncation_risk``) — a 25-row account observed
  across 2 pages (20 + 5) under a page size of 20, ``verdict:
  TRUNCATION_RISK_DEMONSTRATED``. **This is exactly why :meth:`observe` walks the
  continuation keys to completion (or raises) rather than reading one page** — the legacy
  runtime (``shared/kis/client.py:931-932``, reference only, not imported here — firewall-
  denied) reads page 1 only, and ``services/trading/broker_verification.py:187-190``
  (reference only) then DESTROYS a position absent from that possibly-truncated read. A
  witness that reproduced the same truncation would be worse than useless for
  reconciliation: it would corroborate the very defect it exists to catch.
* ``orders`` — 주식일별주문체결조회 (stock daily execution inquiry), mock TR
  ``VTTC0081R``, ``/uapi/domestic-stock/v1/trading/inquire-daily-ccld``. Sourced from
  ``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:1548-1575`` (§ "체결조회로
  독립 확인") and, with the exact wire parameter set this module mirrors,
  ``tools/broker_probes/probes_order.py:1079-1150`` (``MockTradingClient.stock_daily_ccld``,
  reference only — a probes-harness module, not imported here). Both TR ids are 모의
  (``V``-prefixed) — this witness is 모의투자-only, structurally
  (:mod:`tos_runtime.recon.witness_kis_config`'s host seal + TR-id shape check).

**Futures — refused outright, at construction, not at ``observe()`` time.**
:class:`~tos_runtime.recon.ports.WitnessScope` carries no asset-class field (only
``account``/``instrument_keys``/``attempt_ids``), so there is no way to route a "futures"
scope through :meth:`observe` even if one arrived — this class simply never queries a
futures endpoint. :func:`~tos_runtime.recon.witness_kis_config.refuse_futures_asset` is
still called at construction (with the constant ``"stock"``) so the refusal is one
structurally testable code path rather than an implicit absence — see that function's own
docstring for the two independent reasons (mock server support, root ``CLAUDE.md``
Non-Negotiable Rules).

**Token/credentials — injected, no lifecycle owned here (task instruction).** This class
does not issue, cache, or reissue a bearer token, and does not itself hold the KIS app
key/secret. It takes a :class:`KisWitnessTokenSession` (see that Protocol's own docstring
for the exact shape assumed, and why) as a constructor dependency, calling it fresh for
every page of every walk — mirroring
:meth:`tos_runtime.transport.kis_mock.adapter.KisMockTransport._ensure_token_string`'s own
"ask again every send, let the session decide freshness" discipline, never this class's own
cooldown/expiry math.

**Never claims more than it verified.** Every :class:`~tos_runtime.recon.ports.WitnessSnapshot`
this class returns carries ``provenance="kis-mock-stock"`` and
``independent_of_evidence_store=True`` — the latter is honest here (unlike
``witness_synthetic.py``) because this class's only I/O is the two HTTP GETs described
above; it holds no reference to any evidence store at all.

Firewall (RUNTIME scope R1): stdlib (``dataclasses``, ``datetime``, ``decimal``,
``typing``, ``zoneinfo``) + this package's own sibling modules
(:mod:`~tos_runtime.recon.ports`, :mod:`~tos_runtime.recon.witness_kis_config`,
:mod:`~tos_runtime.recon.witness_kis_client`) — no ``os.environ``, no ``shared.*``, no
evidence-store import, no direct ``tos.*`` import at all (this module only ever sees
``InstrumentKey``/``WitnessScope`` etc. through :mod:`tos_runtime.recon.ports`'s own
re-exports, so it opens no new commons edge beyond the one that module already has).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from tos_runtime.recon.ports import (
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
    WitnessUnavailable,
)
from tos_runtime.recon.witness_kis_client import (
    KisWitnessClientError,
    KisWitnessHttpClient,
    RawGetResponse,
)
from tos_runtime.recon.witness_kis_config import KisWitnessConfig, refuse_futures_asset

__all__ = [
    "KisStockBrokerWitness",
    "KisWitnessTokenSession",
    "KstDateSource",
    "SystemKstDateSource",
]

#: KIS's own "more follows" tr_cont response codes (measured:
#: ``tools/broker_probes/probes_balance.py:174-186``, itself measured against
#: ``shared/kis/client.py:354`` and KIS's official ``inquire_balance`` example). Any
#: NON-EMPTY value outside this pair is the broker's end-of-set signal.
_TR_CONT_MORE_CODES = ("M", "F")

#: Request-side continuation header for a follow-up page (``probes_balance.py:189``).
_TR_CONT_REQUEST_NEXT = "N"

#: ``EgressResultKind``-shaped mapping is not applicable here — this is the
#: 체결조회(execution-inquiry) row -> :class:`WitnessOrderState` mapping instead, derived
#: from the same three row fields P-11 measured (``cncl_yn``, ``tot_ccld_qty``,
#: ``rmn_qty`` — ``docs/broker-profiles/evidence/2026-07-29-p02-t2-campaign/
#: P-11-20260805T000653Z.json`` ``measurements.fill_case.execution_inquiry.row``).
_CANCELLED = "Y"


def _decimal_or_none(value: Any) -> Decimal | None:
    """Best-effort ``Decimal`` coercion for a JSON-decoded numeric/string field.

    Fail-closed: ``None`` and any unparseable value pass through as ``None`` rather than
    a fabricated zero standing in for an absent magnitude (mirrors
    ``witness_synthetic.py``'s own ``_to_decimal``).
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (str, int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    return None


@runtime_checkable
class KisWitnessTokenSession(Protocol):
    """The injected token-lifecycle dependency this witness assumes.

    **Assumed shape (task instruction: study ``adapter.py``'s existing token handling
    so this Protocol matches it, and report the assumption).** Read from
    :meth:`tos_runtime.transport.kis_mock.adapter.KisMockTransport._ensure_token_string`
    / ``_issue_token`` (``adapter.py:394-465``): that method (a) reissues only when the
    held token is absent or has outlived its own ``expires_in`` seconds, read off the
    token response itself — never a fixed TTL; (b) refuses to reissue inside a
    cooldown window since the last issuance ATTEMPT (not the last success) if the held
    token is already stale, raising rather than blocking; (c) loads the KIS app
    key/secret from custody in the narrowest possible ``with`` block, wrapped directly
    around the one ``issue_token`` network call.

    This Protocol reduces that to the two facts a READ-ONLY caller needs and asks the
    session to keep owning everything else:

    * :meth:`access_token` — a currently-valid bearer string, reissuing internally per
      (a)/(b)/(c) above. This witness calls it before every page of every walk (never
      caching it itself) and treats ANY exception it raises as this witness's own
      :class:`~tos_runtime.recon.ports.WitnessUnavailable` (wrapped at the
      :meth:`KisStockBrokerWitness.observe` boundary — see that method).
    * :meth:`app_key_header` / :meth:`app_secret_header` — the plaintext app
      key/secret for the ``appkey``/``appsecret`` request headers KIS's own wire
      convention requires on EVERY call, not only token issuance
      (``shared/kis/auth.py:494-506`` reference; ``kis_mock/client.py``'s own
      ``post_order`` sends both alongside the bearer token). A read-only witness still
      needs these per-GET, so this Protocol asks for them directly rather than
      re-deriving them from a loaded :class:`~tos_runtime.custody.ports.CredentialHandle`
      itself — this witness holds no ``CredentialCustody`` reference at all, by design
      (task instruction: no token/credential lifecycle owned here).

    The concurrent W2 lane (2026-09-17) is extracting a reusable token session out of
    ``adapter.py`` — whatever it lands must satisfy this Protocol, or a thin adapter
    wraps it to do so; this witness does not import ``tos_runtime.transport.kis_mock``
    at all (a GET-only reconciliation seam has no reason to depend on the order-transport
    package), so the actual wiring is a compose-root concern, not this module's.
    """

    def access_token(self) -> str:
        """Return a currently-valid bearer token string (module docstring)."""
        ...

    def app_key_header(self) -> str:
        """Return the KIS app key (plaintext) for the ``appkey`` request header."""
        ...

    def app_secret_header(self) -> str:
        """Return the KIS app secret (plaintext) for the ``appsecret`` request header."""
        ...


@runtime_checkable
class KstDateSource(Protocol):
    """Supplies "today" in KST as ``YYYYMMDD`` — the one ambient-time fact 주식일별
    주문체결조회 needs (``INQR_STRT_DT``/``INQR_END_DT``). Injected, per this package's
    "everything ambient is a seam" discipline (mirrors
    :mod:`tos_runtime.time.sources`'s own ``MonotonicSource`` — a Protocol wrapping the
    one real-clock read, rather than this module calling ``datetime.now()`` inline)."""

    def today(self) -> str:
        """Return today's KST calendar date as ``YYYYMMDD``."""
        ...


class SystemKstDateSource:
    """Reads the real wall clock — the one ambient-time read in this module's own
    production wiring, isolated to this one small class exactly the way
    :class:`tos_runtime.time.sources.ProcessMonotonicSource` isolates
    ``time.monotonic_ns()``. Test suites inject a fixed :class:`KstDateSource` double
    instead of this class."""

    _KST = ZoneInfo("Asia/Seoul")

    def today(self) -> str:
        return datetime.now(self._KST).strftime("%Y%m%d")


#: The KIS wire field-name spelling a continuation key arrives under — lowercase, exactly.
#: ``probes_balance.py``'s own ``_read_ctx_key`` defensively also checks an uppercase
#: spelling, but every P-BAL artifact this repo has ever recorded — 2026-07-29 campaign
#: (``P-BAL-20260731T081805Z.json``, ``:083102Z``, ``:084147Z``, ``:084238Z``,
#: ``P-BAL-20260805T000827Z.json``) through the 2026-09-11 campaign
#: (``P-BAL-20260911T002427Z.json``) — reports ``found_at: "body:ctx_area_fk100"`` /
#: ``"body:ctx_area_nk100"`` and NEVER once an uppercase ``found_at``. Review MEDIUM-2
#: (2026-09-17): an untested defensive branch resting on no evidence is exactly the
#: phantom this repo's own lesson warns about ("필드를 제거하라, 무시하지 말고" —
#: [[injected-literals-hide-dead-paths]]) — removed rather than kept-and-unexercised. If a
#: future measurement ever observes an uppercase key, add it back WITH the artifact that
#: demonstrates it and a test that exercises that exact branch.
def _read_ctx_key(body: Mapping[str, Any], suffix: str, kind: str) -> str:
    name = f"ctx_area_{kind}{suffix}"
    return str(body.get(name) or "").strip()


@dataclass(frozen=True)
class _WalkOutcome:
    """The rows and (for the balance walk only) the ``output2`` block accumulated across
    a completed continuation walk."""

    pages: tuple[list[dict[str, Any]], ...]
    output2_first: dict[str, Any] | None


class KisStockBrokerWitness:
    """A :class:`~tos_runtime.recon.ports.BrokerWitness` over the real KIS 모의투자 stock
    balance + execution-inquiry TRs (module docstring)."""

    def __init__(
        self,
        *,
        config: KisWitnessConfig,
        client: KisWitnessHttpClient,
        token_session: KisWitnessTokenSession,
        date_source: KstDateSource,
        asset: str = "stock",
    ) -> None:
        """Wire this witness's dependencies (all injected — no ambient state beyond the
        one isolated wall-clock read in :class:`SystemKstDateSource`).

        Args:
            config: The fail-closed-loaded :class:`KisWitnessConfig`.
            client: The GET-only stdlib HTTP shim.
            token_session: See :class:`KisWitnessTokenSession`'s own docstring.
            date_source: Supplies "today" in KST for the execution-inquiry TR's date
                window.
            asset: MUST be ``"stock"`` — any other value is refused immediately
                (module docstring "Futures — refused outright").

        Raises:
            ~tos_runtime.recon.witness_kis_config.FuturesAssetRefused: ``asset`` is not
                ``"stock"``.
        """
        refuse_futures_asset(asset)
        self._config = config
        self._client = client
        self._token_session = token_session
        self._date_source = date_source

    # -- BrokerWitness port -------------------------------------------------------------

    def observe(self, scope: WitnessScope) -> WitnessSnapshot:
        """Observe this account's stock positions/cash and today's stock order fills.

        Raises:
            WitnessUnavailable: ``scope.account`` is not a 10-digit KIS account number,
                the token session raised, a request failed/was rejected, or a
                continuation walk could not be completed (module docstring — never a
                silently truncated snapshot).
        """
        try:
            cano, acnt_prdt_cd = self._split_account(scope.account)
            positions, cash = self._read_balance(cano, acnt_prdt_cd, scope)
            orders = self._read_orders(cano, acnt_prdt_cd, scope)
        except WitnessUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - the port's own two-outcome contract
            # ports.py's contract is exactly two outcomes: a genuine WitnessSnapshot, or
            # WitnessUnavailable. Any other exception (a token-session failure, an HTTP
            # client fault, an unexpected KeyError on a malformed body) is wrapped here
            # rather than left to propagate as a THIRD, undocumented outcome. The
            # wrapped message never repeats `exc`'s own text if that text could carry a
            # secret (it cannot: this witness's own exceptions below are already
            # secret-free by construction, and `KisWitnessClientError`'s own messages
            # never format a header value).
            raise WitnessUnavailable(
                f"KisStockBrokerWitness.observe: could not complete — {type(exc).__name__}"
            ) from exc

        return WitnessSnapshot(
            observed_at_generation=scope.as_of_generation,
            orders=orders,
            positions=positions,
            cash=cash,
            provenance="kis-mock-stock",
            # Honest True: this class holds no evidence-store reference at all (module
            # docstring) — unlike witness_synthetic.py, there is nothing here to be
            # non-independent OF.
            independent_of_evidence_store=True,
        )

    # -- account -----------------------------------------------------------------------

    @staticmethod
    def _split_account(account: str) -> tuple[str, str]:
        """Split ``scope.account`` into KIS's ``(CANO, ACNT_PRDT_CD)`` pair.

        **Assumption, stated plainly (report this if wrong):** this witness assumes
        ``WitnessScope.account`` IS the 10-digit KIS account number (CANO + product code
        concatenated) — the same convention
        ``tools/broker_probes/common.py:266-270``'s ``ProbeCredentials.cano``/
        ``.acnt_prdt_cd`` properties use. The kernel's own ``WitnessScope.account`` is an
        opaque ``str`` (``ports.py``) with no KIS-specific shape mandated — if a real
        compose-root wiring uses a different (runtime-internal) account identifier, the
        translation to a KIS account number belongs at that wiring layer, not invented
        here as a guess.
        """
        digits = "".join(ch for ch in account if ch.isdigit())
        if len(digits) != 10:
            raise WitnessUnavailable(
                "KisStockBrokerWitness: scope.account must be a 10-digit KIS account "
                f"number (CANO + product code) — got {len(digits)} digit(s). This "
                "witness cannot answer for a non-KIS-shaped account identifier."
            )
        return digits[:8], digits[8:10]

    # -- HTTP --------------------------------------------------------------------------

    def _headers(self, *, tr_id: str, tr_cont: str) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self._token_session.access_token()}",
            "appkey": self._token_session.app_key_header(),
            "appsecret": self._token_session.app_secret_header(),
            "tr_id": tr_id,
            "custtype": "P",
        }
        if tr_cont:
            headers["tr_cont"] = tr_cont
        return headers

    def _get_page(
        self, *, path: str, tr_id: str, params: Mapping[str, str], tr_cont: str
    ) -> RawGetResponse:
        try:
            return self._client.get(
                path,
                headers=self._headers(tr_id=tr_id, tr_cont=tr_cont),
                params=params,
            )
        except KisWitnessClientError as exc:
            raise WitnessUnavailable(
                f"KisStockBrokerWitness: transport failure on {path} — "
                f"{type(exc).__name__}"
            ) from exc

    # -- generic continuation walk (module docstring's central discipline) -------------

    def _walk_continuation(
        self,
        *,
        path: str,
        tr_id: str,
        build_params: Any,
    ) -> _WalkOutcome:
        """Walk ``CTX_AREA_FK100``/``NK100`` to completion, or raise.

        ``build_params(fk, nk)`` returns this page's full query-parameter mapping — the
        caller supplies every field except the two continuation keys, which this method
        owns exclusively.

        Never returns a partial result: any of a broker rejection, a "more follows"
        signal with no usable cursor, a non-advancing cursor, or exhausting
        ``config.max_pages`` while the broker still signals more, raises
        :class:`~tos_runtime.recon.ports.WitnessUnavailable` instead of returning what
        was read so far (module docstring's central reason this class exists).
        """
        pages: list[list[dict[str, Any]]] = []
        output2_first: dict[str, Any] | None = None
        fk = nk = ""
        for index in range(self._config.max_pages):
            tr_cont = "" if index == 0 else _TR_CONT_REQUEST_NEXT
            response = self._get_page(
                path=path, tr_id=tr_id, params=build_params(fk, nk), tr_cont=tr_cont
            )
            # Review MEDIUM-1 (2026-09-17): the HTTP status is checked BEFORE the body is
            # trusted at all — a non-200 response that happens to carry a JSON body shaped
            # like a successful KIS answer (rt_cd="0") — a proxy, a WAF, an intermediary's
            # own error page — must never be read as a genuine broker success just because
            # its body parses.
            if response.status != 200:
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: page {index} of {tr_id} returned HTTP "
                    f"{response.status} (expected 200) — refusing to trust its body"
                )
            if response.json is None:
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: page {index} of {tr_id} did not parse as "
                    "JSON"
                )
            body = response.json
            rt_cd = str(body.get("rt_cd") or "").strip()
            if rt_cd != "0":
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: page {index} of {tr_id} rejected "
                    f"(rt_cd={rt_cd!r}, msg_cd={body.get('msg_cd')!r})"
                )
            rows = body.get("output1")
            pages.append(rows if isinstance(rows, list) else [])
            if output2_first is None:
                out2 = body.get("output2")
                if isinstance(out2, list) and out2 and isinstance(out2[0], dict):
                    output2_first = out2[0]

            next_fk = _read_ctx_key(body, "100", "fk")
            next_nk = _read_ctx_key(body, "100", "nk")
            tr_cont_out = str(response.headers.get("tr_cont") or "").strip()
            more = tr_cont_out in _TR_CONT_MORE_CODES

            if not more:
                return _WalkOutcome(pages=tuple(pages), output2_first=output2_first)

            if not next_fk and not next_nk:
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: page {index} of {tr_id} answered "
                    f"tr_cont={tr_cont_out!r} (more follows) but returned no "
                    "continuation key — cannot walk further, refusing to return a "
                    "partial result"
                )
            if (next_fk, next_nk) == (fk, nk):
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: continuation keys did not advance on page "
                    f"{index} of {tr_id} while tr_cont={tr_cont_out!r} still signalled "
                    "more — a further request would repeat this page; refusing to loop "
                    "or return a partial result"
                )
            fk, nk = next_fk, next_nk
        raise WitnessUnavailable(
            f"KisStockBrokerWitness: {tr_id} walk stopped at max_pages="
            f"{self._config.max_pages} while the broker was still signalling more — "
            "this is OUR cap, not the broker's end-of-set; refusing to return a "
            "partial holdings/order list (contrast tools/broker_probes/probes_balance.py, "
            "which is allowed to report a lower bound — a WitnessSnapshot may not)"
        )

    # -- balance -------------------------------------------------------------------------

    def _read_balance(
        self, cano: str, acnt_prdt_cd: str, scope: WitnessScope
    ) -> tuple[tuple[tuple[str, Decimal], ...], Decimal | None]:
        """주식 잔고조회 — mirrors ``tools/broker_probes/probes_balance.py``'s own
        ``_balance_params`` for the stock target (module docstring)."""

        def build_params(fk: str, nk: str) -> dict[str, str]:
            return {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": fk,
                "CTX_AREA_NK100": nk,
            }

        outcome = self._walk_continuation(
            path=self._config.balance_path,
            tr_id=self._config.balance_tr_id,
            build_params=build_params,
        )

        instruments = {key.instrument for key in scope.instrument_keys}
        positions: list[tuple[str, Decimal]] = []
        for rows in outcome.pages:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("pdno") or "").strip()
                qty = _decimal_or_none(row.get("hldg_qty"))
                # Positive-quantity filter mirrors the runtime consumer's own convention
                # (shared/kis/client.py:1002, reference only) — a flattened (qty<=0) row
                # is not a held position.
                if qty is None or qty <= 0:
                    continue
                if instruments and symbol not in instruments:
                    continue
                positions.append((symbol, qty))

        cash = (
            _decimal_or_none(outcome.output2_first.get("dnca_tot_amt"))
            if outcome.output2_first is not None
            else None
        )
        return tuple(positions), cash

    # -- orders --------------------------------------------------------------------------

    def _read_orders(
        self, cano: str, acnt_prdt_cd: str, scope: WitnessScope
    ) -> tuple[WitnessOrder, ...]:
        """주식일별주문체결조회 — mirrors ``tools/broker_probes/probes_order.py``'s own
        ``stock_daily_ccld`` params exactly (module docstring).

        Never filters by ``scope.attempt_ids`` (ports.py's own orphan-detection
        requirement) — and in fact CANNOT: the broker's own row shape carries no
        attempt-id field at all, so :attr:`~tos_runtime.recon.ports.WitnessOrder
        .attempt_id` is always ``None`` for every order this witness returns. Every
        order this witness reports is, from this witness's own perspective alone,
        indistinguishable from an "orphan" — that is an honest limitation, not a filter
        this class applies (see :class:`KisWitnessTokenSession`'s own docstring's
        sibling note on not overclaiming).
        """
        today = self._date_source.today()
        symbols = [key.instrument for key in scope.instrument_keys] or [""]

        orders: list[WitnessOrder] = []
        for symbol in symbols:

            def build_params(
                fk: str, nk: str, *, symbol: str = symbol
            ) -> dict[str, str]:
                return {
                    "CANO": cano,
                    "ACNT_PRDT_CD": acnt_prdt_cd,
                    "INQR_STRT_DT": today,
                    "INQR_END_DT": today,
                    "SLL_BUY_DVSN_CD": "00",
                    "PDNO": symbol,
                    "CCLD_DVSN": "00",
                    "INQR_DVSN": "00",
                    "INQR_DVSN_3": "00",
                    "ORD_GNO_BRNO": "",
                    "ODNO": "",
                    "INQR_DVSN_1": "",
                    "CTX_AREA_FK100": fk,
                    "CTX_AREA_NK100": nk,
                    "EXCG_ID_DVSN_CD": "KRX",
                }

            outcome = self._walk_continuation(
                path=self._config.order_inquiry_path,
                tr_id=self._config.order_inquiry_tr_id,
                build_params=build_params,
            )
            for rows in outcome.pages:
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    orders.append(self._order_from_row(row))
        return tuple(orders)

    @staticmethod
    def _order_from_row(row: Mapping[str, Any]) -> WitnessOrder:
        cancelled = str(row.get("cncl_yn") or "").strip() == _CANCELLED
        filled_qty = _decimal_or_none(row.get("tot_ccld_qty"))
        remaining_qty = _decimal_or_none(row.get("rmn_qty"))
        odno = row.get("odno")

        if cancelled:
            state = WitnessOrderState.CANCELLED
        elif filled_qty is not None and filled_qty > 0:
            state = (
                WitnessOrderState.FILLED
                if remaining_qty is not None and remaining_qty <= 0
                else WitnessOrderState.PARTIAL
            )
        elif filled_qty is not None and filled_qty == 0:
            state = WitnessOrderState.ACKED
        else:
            state = WitnessOrderState.UNKNOWN

        return WitnessOrder(
            # The broker's own row carries no attempt-id concept at all (method
            # docstring) — always None, never guessed from ODNO.
            attempt_id=None,
            broker_execution_id=str(odno).strip() if odno else None,
            quantity=filled_qty,
            remaining=remaining_qty,
            state=state,
        )
