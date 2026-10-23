"""The ONE KIS account parser — order encoding and the balance read both use it (#932 Codex r1 HIGH).

A KIS account number is ``8-2``: an 8-digit 종합계좌번호 (``CANO``) and a 2-digit 계좌상품코드
(``ACNT_PRDT_CD``). The KIS official examples send them as two body/query fields —
``examples_llm/domestic_stock/order_cash/order_cash.py`` ("POST API ... (EX. "CANO" :
"12345678", "ACNT_PRDT_CD": "01",...)") and ``inquire_balance`` ("계좌번호 체계(8-2)의 앞 8자리" /
"뒤 2자리").

The sealed account coordinate stays the whole number (``"88888888-01"`` or ``"8888888801"``) —
:class:`~tos.egressgw.SendSeal` binds it as given. Before this module the order codec sent that
whole string as ``CANO`` while the balance reader split it, so one of the two was always wrong
for any one account string; now both split it here, the same way.

Accepted: exactly 10 ASCII digits, optionally with ONE hyphen after the eighth. Anything else is
refused — never guessed, never padded.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["KisAccount", "KisAccountError", "split_kis_account"]


class KisAccountError(ValueError):
    """The account coordinate is not a KIS ``8-2`` account number."""


@dataclass(frozen=True)
class KisAccount:
    """The two KIS wire fields one account number becomes."""

    #: 종합계좌번호 — 8 digits.
    cano: str
    #: 계좌상품코드 — 2 digits.
    acnt_prdt_cd: str


def split_kis_account(account: str) -> KisAccount:
    """``"88888888-01"`` / ``"8888888801"`` -> ``KisAccount("88888888", "01")``, or refuse.

    The error message never repeats the account itself (it is a sealed coordinate, and a
    refusal reason can reach an evidence row).

    Raises:
        KisAccountError: not 10 ASCII digits with at most one hyphen, after the eighth digit.
    """
    if not isinstance(account, str):
        raise KisAccountError("KIS account must be a string")
    if account.count("-") > 1 or ("-" in account and account.index("-") != 8):
        raise KisAccountError(
            "KIS account must be 8-2 digits (one hyphen after the 8th)"
        )
    digits = account.replace("-", "")
    if len(digits) != 10 or not (digits.isascii() and digits.isdigit()):
        raise KisAccountError("KIS account must be exactly 10 ASCII digits (8-2)")
    return KisAccount(cano=digits[:8], acnt_prdt_cd=digits[8:])
