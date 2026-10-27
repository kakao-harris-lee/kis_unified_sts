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
key/secret. It takes a :class:`KisWitnessCredentialSession` (see that Protocol's own
docstring for the shape, and why — C-2 decision (C)) as a constructor dependency and opens one
``request_credentials()`` block per page of every walk — "ask again every request, let the
session decide freshness", never this class's own cooldown/expiry math.

**Never claims more than it verified.** Every :class:`~tos_runtime.recon.ports.WitnessSnapshot`
this class returns carries ``provenance="kis-mock-stock"`` and
``independent_of_evidence_store=True`` — the latter is honest here (unlike
``witness_synthetic.py``) because this class's only I/O is the two HTTP GETs described
above; it holds no reference to any evidence store at all.

Firewall (RUNTIME scope R1): stdlib (``dataclasses``, ``datetime``, ``decimal``, ``re``,
``typing``, ``zoneinfo``) + this package's own sibling modules
(:mod:`~tos_runtime.recon.ports`, :mod:`~tos_runtime.recon.witness_kis_config`,
:mod:`~tos_runtime.recon.witness_kis_client`) plus the stdlib-only KIS account parser
:mod:`tos_runtime.transport.kis_mock.account` (PR-3b — one 8-2 parser for order and fill reads) —
no ``os.environ``, no ``shared.*``, no
evidence-store import, no direct ``tos.*`` import at all (this module only ever sees
``InstrumentKey``/``WitnessScope`` etc. through :mod:`tos_runtime.recon.ports`'s own
re-exports, so it opens no new commons edge beyond the one that module already has).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
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
from tos_runtime.transport.kis_mock.account import KisAccountError, split_kis_account

__all__ = [
    "KisOrderRow",
    "KisStockBrokerWitness",
    "KisWitnessCredentialSession",
    "KisWitnessRequestCredentials",
    "KstDateSource",
    "SystemKstDateSource",
    "TrustedKstDateSource",
]

#: KIS's own "more follows" tr_cont response codes (measured:
#: ``tools/broker_probes/probes_balance.py:174-186``, itself measured against
#: ``shared/kis/client.py:354`` and KIS's official ``inquire_balance`` example). Any
#: NON-EMPTY value outside this pair is the broker's end-of-set signal.
_TR_CONT_MORE_CODES = ("M", "F")

#: ``YYYYMMDD`` as KIS writes ``ord_dt`` — ASCII digits only.
_YYYYMMDD = re.compile(r"[0-9]{8}")

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


def _header_value(secret: bytes) -> str:
    """ASCII-decode one credential for its header. A non-ASCII credential is refused WITHOUT
    chaining the decode error: ``UnicodeDecodeError.object`` holds the whole plaintext, which
    would outlive the zeroed handle on the chained ``WitnessUnavailable`` (review finding, PR #806).
    """
    try:
        return secret.decode("ascii")
    except UnicodeDecodeError:
        pass
    # Raised OUTSIDE the except block so neither __cause__ nor __context__ carries the bytes.
    raise ValueError("KIS credential is not ASCII — refusing to send it")


@runtime_checkable
class KisWitnessRequestCredentials(Protocol):
    """What one request needs, valid only inside the ``with`` block that produced it."""

    access_token: str

    def app_key(self) -> bytes:
        """The KIS app key bytes for the ``appkey`` header (raises once the block exits)."""
        ...

    def app_secret(self) -> bytes:
        """The KIS app secret bytes for the ``appsecret`` header (raises once the block
        exits)."""
        ...


@runtime_checkable
class KisWitnessCredentialSession(Protocol):
    """The injected credential owner this witness asks for one request's credentials
    (C-2 decision (C): ``docs/plans/2026-09-23-tos-kis-credential-ownership-decision-c2.md`` §4).

    Satisfied structurally by
    :class:`~tos_runtime.transport.kis_mock.credential_session.KisCredentialSession` — this
    module does not import it (the firewall lets a ``recon`` module import only its siblings);
    only the compose root connects the two. The session keeps owning everything about the
    token (issuance, expiry, the reissue cooldown) and the custody loads; this witness never
    holds a ``CredentialCustody`` reference.

    **Why a context, not three getters.** The earlier shape (``access_token()`` /
    ``app_key_header()`` / ``app_secret_header()``) returned the plaintext key and secret as
    ``str`` return values whose lifetime nothing bounded. Here the key and secret are readable
    only inside the ``with`` block wrapped around one GET, and the session zeroes the
    underlying handles when the block exits — the same lifetime the order transport and the
    quote intake give them. The HTTP header values themselves are still ``str`` for the length
    of the request (C-2 §1.1 L4 — unavoidable in every option).

    Any exception :meth:`request_credentials` raises (a stale token inside the reissue
    cooldown, a custody refusal) becomes this witness's own
    :class:`~tos_runtime.recon.ports.WitnessUnavailable` at the :meth:`KisStockBrokerWitness
    .observe` boundary.
    """

    def request_credentials(
        self,
    ) -> AbstractContextManager[KisWitnessRequestCredentials]:
        """Token + app key/secret for one request, inside the ``with`` block only."""
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
    """Reads the real wall clock UNGATED by trusted time — kept for standalone measurement only.
    A composition root wires :class:`TrustedKstDateSource` instead (plan 2026-09-26 egress
    trading date §2 decision 4). Test suites inject a fixed :class:`KstDateSource` double.
    """

    _KST = ZoneInfo("Asia/Seoul")

    def today(self) -> str:
        return datetime.now(self._KST).strftime("%Y%m%d")


class _UnixMsReading(Protocol):
    @property
    def unix_ms(self) -> int: ...


class _WallClockLike(Protocol):
    """Structural stand-in for :class:`tos_runtime.calendar.ports.WallClockReference` — kept
    local so this module opens no import edge beyond its siblings (module docstring firewall).
    """

    def read(self) -> _UnixMsReading | None: ...


class TrustedKstDateSource:
    """``today()`` from a :class:`~tos_runtime.calendar.ports.WallClockReference` — in production
    a :class:`~tos_runtime.calendar.ports.FreshTrustedWallClockReference` (trusted AND fresh; the
    plain trusted reference serves the last evaluated snapshot, which can be days old — review
    finding 1) — so the witness never queries a date the runtime does not trust.
    An absent reading raises :class:`~tos_runtime.recon.ports.WitnessUnavailable`, the port's own
    "could not answer" outcome, rather than guessing a date."""

    _KST = ZoneInfo("Asia/Seoul")

    def __init__(self, wall_clock: _WallClockLike) -> None:
        self._wall_clock = wall_clock

    def today(self) -> str:
        reading = self._wall_clock.read()
        if reading is None:
            raise WitnessUnavailable(
                "TrustedKstDateSource: no trusted wall-clock reading — refusing to guess the "
                "inquiry date"
            )
        return datetime.fromtimestamp(reading.unix_ms / 1000, tz=self._KST).strftime(
            "%Y%m%d"
        )


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

    #: One entry per page: that page's ``output1`` list, or ``None`` when the page did not
    #: carry a list at all — ``output1`` missing, ``null``, or a non-list such as a dict
    #: (review-973 round 2 HIGH). The distinction matters because a malformed container used
    #: to be flattened to ``[]``, making it indistinguishable from a page that genuinely
    #: listed no rows: the balance read then saw an empty, "complete" holdings account and
    #: called it flat. An empty LIST is well-formed — a flat KIS account really does answer
    #: ``output1: []``. Both consumers iterate a ``None`` page as no rows, so the order walk
    #: behaves exactly as before; only :meth:`KisStockBrokerWitness._read_balance` reads the
    #: ``None`` itself, as evidence that its holdings picture is incomplete.
    pages: tuple[list[dict[str, Any]] | None, ...]
    output2_first: dict[str, Any] | None

    @property
    def containers_wellformed(self) -> bool:
        """Whether every page carried a genuine ``output1`` list."""
        return all(rows is not None for rows in self.pages)


def _refuse_instrument_conflict(row: KisOrderRow, *, queried: str) -> None:
    """A row must name the instrument it was asked for (PR-3b review HIGH 2). The witness
    carries no instrument on :class:`~tos_runtime.recon.ports.WitnessOrder`, so a row for another
    symbol — or one naming none — would otherwise be joined by ODNO alone and corroborate a fill
    it says nothing about. Never filtered out: the whole read is unavailable, so the conflict
    surfaces as "not corroborated" instead of disappearing.

    Raises:
        WitnessUnavailable: ``row.pdno`` is absent, or differs from ``queried`` (when one was).
    """
    if row.pdno is None or (queried and row.pdno != queried):
        raise WitnessUnavailable(
            f"KisStockBrokerWitness: order row {row.odno!r} names instrument {row.pdno!r}, "
            f"queried {queried or '(any)'!r} — a row that does not name the queried instrument "
            "cannot corroborate anything"
        )


@dataclass(frozen=True)
class KisOrderRow:
    """One 주식일별주문체결조회 (``VTTC0081R``) ``output1`` row, typed — the ONE parse of that row
    this runtime has. :meth:`KisStockBrokerWitness.observe` folds it into a
    :class:`~tos_runtime.recon.ports.WitnessOrder`; the post-ACK fill observer
    (:mod:`tos_runtime.posttrade.fill_observer`) reads the extra fields it needs to fail closed
    (``ord_qty``, ``rjct_qty``, ``orgn_odno``). Field names are KIS's own (official
    ``COLUMN_MAPPING``, open-trading-api ``inquire_daily_ccld``); a magnitude that does not parse
    is ``None``, never a fabricated zero.
    """

    odno: str | None
    orgn_odno: str | None
    ord_dt: str | None
    pdno: str | None
    ord_qty: Decimal | None
    tot_ccld_qty: Decimal | None
    rmn_qty: Decimal | None
    rjct_qty: Decimal | None
    cancelled: bool

    @classmethod
    def from_wire(cls, row: Mapping[str, Any]) -> KisOrderRow:
        def _text(name: str) -> str | None:
            value = str(row.get(name) or "").strip()
            return value or None

        ord_dt = str(row.get("ord_dt") or "").strip()
        return cls(
            odno=_text("odno"),
            orgn_odno=_text("orgn_odno"),
            # KIS 주문일자 — anything but YYYYMMDD digits is no date at all.
            ord_dt=ord_dt if _YYYYMMDD.fullmatch(ord_dt) is not None else None,
            pdno=_text("pdno"),
            ord_qty=_decimal_or_none(row.get("ord_qty")),
            tot_ccld_qty=_decimal_or_none(row.get("tot_ccld_qty")),
            rmn_qty=_decimal_or_none(row.get("rmn_qty")),
            rjct_qty=_decimal_or_none(row.get("rjct_qty")),
            cancelled=str(row.get("cncl_yn") or "").strip() == _CANCELLED,
        )


class KisStockBrokerWitness:
    """A :class:`~tos_runtime.recon.ports.BrokerWitness` over the real KIS 모의투자 stock
    balance + execution-inquiry TRs (module docstring)."""

    def __init__(
        self,
        *,
        config: KisWitnessConfig,
        client: KisWitnessHttpClient,
        credential_session: KisWitnessCredentialSession,
        date_source: KstDateSource,
        asset: str = "stock",
    ) -> None:
        """Wire this witness's dependencies (all injected — no ambient state beyond the
        one isolated wall-clock read in :class:`SystemKstDateSource`).

        Args:
            config: The fail-closed-loaded :class:`KisWitnessConfig`.
            client: The GET-only stdlib HTTP shim.
            credential_session: See :class:`KisWitnessCredentialSession`'s own docstring.
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
        self._credential_session = credential_session
        self._date_source = date_source

    # -- BrokerWitness port -------------------------------------------------------------

    def observe(
        self,
        scope: WitnessScope,
        *,
        today: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> WitnessSnapshot:
        """Observe this account's stock positions/cash and today's stock order fills.

        Args:
            scope: Account, instrument and extra order dates to observe.
            today: The trading date to read as "today"; ``None`` asks the date source. The
                fill observer's FETCH thread passes the date its plan was built under (issue
                #950), so the date source is only ever read on the loop thread.
            deadline_expired: Asked before every page of every walk, like
                :meth:`order_rows`'s. The fill observer's FETCH passes only its SHUTDOWN flag
                here — never a time deadline, for the release-semantics reason
                :meth:`order_rows`'s own note gives. ``None``: unbounded as before.

        Raises:
            WitnessUnavailable: ``scope.account`` is not a 10-digit KIS account number,
                the credential session raised, a request failed/was rejected, or a
                continuation walk could not be completed (module docstring — never a
                silently truncated snapshot).
        """
        try:
            cano, acnt_prdt_cd = self._split_account(scope.account)
            positions, cash, positions_complete = self._read_balance(
                cano, acnt_prdt_cd, scope, deadline_expired=deadline_expired
            )
            today = today or self._date_source.today()
            # Today, plus any older date the caller names (PR-3b: an ACK from a previous trading
            # day is still reconcilable — its order lives under its own 주문일자).
            dates = (today, *sorted(set(scope.order_dates) - {today}))
            rows: tuple[KisOrderRow, ...] = ()
            for date in dates:
                rows += self._read_order_rows(
                    cano, acnt_prdt_cd, scope, date, deadline_expired=deadline_expired
                )
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
            orders=tuple(self._order_from_row(row) for row in rows),
            positions=positions,
            # #966 review round 1: only a holdings read with every row attributed proves
            # flatness; a dropped row must not read as "no position".
            positions_complete=positions_complete,
            cash=cash,
            provenance="kis-mock-stock",
            # Honest True: this class holds no evidence-store reference at all (module
            # docstring) — unlike witness_synthetic.py, there is nothing here to be
            # non-independent OF.
            independent_of_evidence_store=True,
            # One inquiry per date (INQR_STRT_DT == INQR_END_DT); a single-date snapshot records
            # it, a multi-date one records None (the field's own contract).
            order_inquiry_date=today if len(dates) == 1 else None,
        )

    def order_rows(
        self,
        scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str, tuple[KisOrderRow, ...]]:
        """One date's 주식일별주문체결조회 rows — no balance read (the post-ACK fill observer's
        GET: one TR, ``VTTC0081R``, not two).

        Args:
            scope: Account and instrument to inquire.
            inquiry_date: ``YYYYMMDD`` to inquire; ``None`` is today (trusted date source). An
                ACK from an earlier trading day is read under its own date — VTTC0081R serves the
                last three months (open-trading-api ``inquire_daily_ccld``, ``pd_dv=inner``).
            deadline_expired: Asked before every page (:meth:`_walk_continuation`) — the
                caller's own bound on how long this read may take in total. A walk it stops is
                ``WitnessUnavailable`` with no rows, never a partial list. ``None`` = unbounded
                by anything but ``max_pages`` and the per-GET timeout.

                :meth:`observe` gets no TIME deadline on the release path: a deadline there
                would make a slow-but-working broker HOLD capacity rather than release it, a
                release-semantics change. Issue #950 moved that read off the loop thread
                instead: the fill observer's FETCH prefetches the release reconciliation's
                snapshot (:mod:`tos_runtime.posttrade.fill_fetch`) and the loop serves it. A
                reconciliation the prefetch did not anticipate still reads live, bounded by
                ``request_timeout_s`` x ``max_pages`` as before.

        Returns:
            ``(date, rows)`` — the KST date the inquiry covered (``INQR_STRT_DT ==
            INQR_END_DT``) and every row the completed continuation walk returned, never filtered
            by attempt or order number (the caller attributes; an unattributable row is its
            finding, not something to drop here).

        Raises:
            WitnessUnavailable: Exactly as :meth:`observe` — a malformed account, a credential
                failure, a rejected or incomplete walk.
        """
        try:
            cano, acnt_prdt_cd = self._split_account(scope.account)
            date = inquiry_date or self._date_source.today()
            return date, self._read_order_rows(
                cano, acnt_prdt_cd, scope, date, deadline_expired=deadline_expired
            )
        except WitnessUnavailable:
            raise
        except (
            Exception
        ) as exc:  # noqa: BLE001 - same two-outcome contract as observe()
            raise WitnessUnavailable(
                f"KisStockBrokerWitness.order_rows: could not complete — {type(exc).__name__}"
            ) from exc

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
        # PR-3b (#932 dde3fbce): the SAME parser the order codec and the balance facts use, so a
        # fill read targets exactly the account the order went to — never a looser reading.
        try:
            parsed = split_kis_account(account)
        except KisAccountError as exc:
            raise WitnessUnavailable(
                f"KisStockBrokerWitness: scope.account is not a KIS 8-2 account ({exc}) — this "
                "witness cannot answer for a non-KIS-shaped account identifier."
            ) from None
        return parsed.cano, parsed.acnt_prdt_cd

    # -- HTTP --------------------------------------------------------------------------

    @staticmethod
    def _headers(
        credentials: KisWitnessRequestCredentials, *, tr_id: str, tr_cont: str
    ) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {credentials.access_token}",
            "appkey": _header_value(credentials.app_key()),
            "appsecret": _header_value(credentials.app_secret()),
            "tr_id": tr_id,
            "custtype": "P",
        }
        if tr_cont:
            headers["tr_cont"] = tr_cont
        return headers

    def _get_page(
        self, *, path: str, tr_id: str, params: Mapping[str, str], tr_cont: str
    ) -> RawGetResponse:
        # One credential block per GET (KisWitnessCredentialSession docstring): the session
        # decides token freshness every page, and the key/secret handles are zeroed the moment
        # this one request returns.
        with self._credential_session.request_credentials() as credentials:
            try:
                return self._client.get(
                    path,
                    headers=self._headers(credentials, tr_id=tr_id, tr_cont=tr_cont),
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
        deadline_expired: Callable[[], bool] | None = None,
    ) -> _WalkOutcome:
        """Walk ``CTX_AREA_FK100``/``NK100`` to completion, or raise.

        ``build_params(fk, nk)`` returns this page's full query-parameter mapping — the
        caller supplies every field except the two continuation keys, which this method
        owns exclusively.

        ``deadline_expired`` (optional) is asked BEFORE every page, including the first: a
        caller that is waited on — the fill observer's poll, inside the session loop's
        tick-to-tick window (#949 review HIGH) — bounds the whole walk that way. It owns the
        clock; this class has none. ``True`` stops the walk and raises, exactly like our own
        ``max_pages`` cap: what was read so far is NEVER returned (see below), so a deadline
        can only produce "unavailable", never "these are all the rows".

        Never returns a partial result: any of a broker rejection, a "more follows"
        signal with no usable cursor, a non-advancing cursor, exhausting
        ``config.max_pages`` while the broker still signals more, or the caller's deadline,
        raises :class:`~tos_runtime.recon.ports.WitnessUnavailable` instead of returning what
        was read so far (module docstring's central reason this class exists).
        """
        pages: list[list[dict[str, Any]] | None] = []
        output2_first: dict[str, Any] | None = None
        fk = nk = ""
        for index in range(self._config.max_pages):
            if deadline_expired is not None and deadline_expired():
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: {tr_id} walk stopped by the caller's deadline "
                    f"before page {index} — refusing to return a partial order/holdings "
                    "list (the same answer our own max_pages cap gives)"
                )
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
            pages.append(rows if isinstance(rows, list) else None)
            if output2_first is None:
                out2 = body.get("output2")
                if isinstance(out2, list) and out2 and isinstance(out2[0], dict):
                    output2_first = out2[0]

            next_fk = _read_ctx_key(body, "100", "fk")
            next_nk = _read_ctx_key(body, "100", "nk")
            tr_cont_out = str(response.headers.get("tr_cont") or "").strip()
            more = tr_cont_out in _TR_CONT_MORE_CODES

            if not more:
                return _WalkOutcome(tuple(pages), output2_first)

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
        self,
        cano: str,
        acnt_prdt_cd: str,
        scope: WitnessScope,
        *,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[tuple[tuple[str, Decimal], ...], Decimal | None, bool]:
        """주식 잔고조회 — mirrors ``tools/broker_probes/probes_balance.py``'s own
        ``_balance_params`` for the stock target (module docstring).

        Returns ``(positions, cash, positions_complete)``. The third element is ``False`` as
        soon as anything in this read could not be fully taken in:

        * a holdings ROW that could not be read — a non-dict row, a blank ``pdno``, or an
          ``hldg_qty`` that does not parse (#966 review round 1, Codex HIGH), since such a row
          is silently dropped from ``positions`` below;
        * a holdings PAGE whose ``output1`` was not a list at all — missing, ``null``, or a
          dict (review-973 round 2 HIGH), since that page contributes zero rows.

        Either way the result would otherwise be indistinguishable from a flat account (see
        :attr:`~tos_runtime.recon.ports.WitnessSnapshot.positions_complete`). An empty list is
        well-formed: a genuinely flat account answers ``output1: []``.

        Page-level truncation needs no flag: the continuation walk raises
        :class:`~tos_runtime.recon.ports.WitnessUnavailable` rather than return a partial page
        set (:meth:`_walk_continuation`).
        """

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
            deadline_expired=deadline_expired,
        )

        instruments = {key.instrument for key in scope.instrument_keys}
        positions: list[tuple[str, Decimal]] = []
        # review-973 round 2 HIGH: a page whose `output1` was not a list contributed zero rows
        # and would otherwise read as "this account holds nothing".
        complete = outcome.containers_wellformed
        for rows in outcome.pages:
            for row in rows if rows is not None else ():
                if not isinstance(row, dict):
                    complete = False
                    continue
                symbol = str(row.get("pdno") or "").strip()
                qty = _decimal_or_none(row.get("hldg_qty"))
                if not symbol or qty is None:
                    # Unreadable: the row is dropped, so record that this holdings account
                    # is NOT complete rather than let the drop read as "no position".
                    complete = False
                    continue
                # Positive-quantity filter mirrors the runtime consumer's own convention
                # (shared/kis/client.py:1002, reference only) — a flattened (qty<=0) row
                # is not a held position, and IS a fully-read row.
                if qty <= 0:
                    continue
                if instruments and symbol not in instruments:
                    continue
                positions.append((symbol, qty))

        cash = (
            _decimal_or_none(outcome.output2_first.get("dnca_tot_amt"))
            if outcome.output2_first is not None
            else None
        )
        return tuple(positions), cash, complete

    # -- orders --------------------------------------------------------------------------

    def _read_order_rows(
        self,
        cano: str,
        acnt_prdt_cd: str,
        scope: WitnessScope,
        today: str,
        *,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[KisOrderRow, ...]:
        """주식일별주문체결조회 — mirrors ``tools/broker_probes/probes_order.py``'s own
        ``stock_daily_ccld`` params exactly (module docstring).

        Never filters by ``scope.attempt_ids`` (ports.py's own orphan-detection
        requirement) — and in fact CANNOT: the broker's own row shape carries no
        attempt-id field at all, so :attr:`~tos_runtime.recon.ports.WitnessOrder
        .attempt_id` is always ``None`` for every order this witness returns. Every
        order this witness reports is, from this witness's own perspective alone,
        indistinguishable from an "orphan" — that is an honest limitation, not a filter
        this class applies (the module docstring's "never claims more than it verified"
        note).
        """
        symbols = [key.instrument for key in scope.instrument_keys] or [""]

        orders: list[KisOrderRow] = []
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
                deadline_expired=deadline_expired,
            )
            for rows in outcome.pages:
                for row in rows if rows is not None else ():
                    if not isinstance(row, dict):
                        continue
                    parsed = KisOrderRow.from_wire(row)
                    _refuse_instrument_conflict(parsed, queried=symbol)
                    orders.append(parsed)
        return tuple(orders)

    @staticmethod
    def _order_from_row(row: KisOrderRow) -> WitnessOrder:
        filled_qty = row.tot_ccld_qty
        remaining_qty = row.rmn_qty

        if row.cancelled:
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
            broker_execution_id=row.odno,
            quantity=filled_qty,
            remaining=remaining_qty,
            state=state,
            # KIS 주문일자 — the broker's own date for this ODNO (plan 2026-09-26 egress trading
            # date §2 decision 4).
            order_date=row.ord_dt,
        )
