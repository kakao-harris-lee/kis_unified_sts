"""The ONE KIS account parser — order encoding and the balance read both use it (#932 Codex r1 HIGH)."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["KisAccount", "KisAccountError", "split_kis_account"]


class KisAccountError(ValueError):
    """The account coordinate is not a KIS ``8-2`` account number."""


@dataclass(frozen=True)
class KisAccount:
    """The two KIS wire fields one account number becomes."""

    cano: str
    acnt_prdt_cd: str


def split_kis_account(account: str) -> KisAccount:
    """``"88888888-01"`` / ``"8888888801"`` -> ``KisAccount("88888888", "01")``, or refuse."""
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
