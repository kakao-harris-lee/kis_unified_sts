"""The 2026-11-24 P-SC cancel rows, verbatim off the 모의 account (issue #1169)."""

from __future__ import annotations

__all__ = [
    "MEASURED_CANCEL_ROW",
    "MEASURED_DATE",
    "MEASURED_INSTRUMENT",
    "MEASURED_ORIGINAL_ODNO",
    "MEASURED_ORIGINAL_ROW",
    "measured_rows",
]

MEASURED_DATE = "20261124"
MEASURED_INSTRUMENT = "035420"
MEASURED_ORIGINAL_ODNO = "0000011558"
MEASURED_CANCEL_ODNO = "0000011561"

# P-SC-20261124T005122Z, 시행 A, snapshot t+2290 ms — and the 12 polls after it, all equal.
# A cancel of an unfilled 1-share order leaves the ORIGINAL row at `cncl_yn=N` for ever and
# states the cancel only as `cncl_cfrm_qty`; `cncl_yn=Y` arrives on a SEPARATE row with its
# own ODNO whose `orgn_odno` is the original (10-digit zero-padded). Note `sll_buy_dvsn_cd`
# is "02" on BOTH rows — only the NAME differs (매수 / 매수취소).
MEASURED_ORIGINAL_ROW: dict[str, str] = {
    "ord_dt": MEASURED_DATE,
    "ord_gno_brno": "00950",
    "odno": MEASURED_ORIGINAL_ODNO,
    "orgn_odno": "0000000000",
    "ord_dvsn_name": "보통가",
    "sll_buy_dvsn_cd": "02",
    "sll_buy_dvsn_cd_name": "매수",
    "pdno": MEASURED_INSTRUMENT,
    "prdt_name": "NAVER",
    "ord_qty": "1",
    "ord_unpr": "118100",
    "ord_tmd": "095130",
    "tot_ccld_qty": "0",
    "avg_prvs": "0",
    "cncl_yn": "N",
    "tot_ccld_amt": "0",
    "ord_dvsn_cd": "00",
    "cncl_cfrm_qty": "1",
    "rmn_qty": "0",
    "rjct_qty": "0",
    "excg_id_dvsn_cd": "KRX",
}

MEASURED_CANCEL_ROW: dict[str, str] = {
    "ord_dt": MEASURED_DATE,
    "ord_gno_brno": "00950",
    "odno": MEASURED_CANCEL_ODNO,
    "orgn_odno": MEASURED_ORIGINAL_ODNO,
    "ord_dvsn_name": "보통가",
    "sll_buy_dvsn_cd": "02",
    "sll_buy_dvsn_cd_name": "매수취소",
    "pdno": MEASURED_INSTRUMENT,
    "prdt_name": "NAVER",
    "ord_qty": "1",
    "ord_unpr": "0",
    "ord_tmd": "095134",
    "tot_ccld_qty": "0",
    "avg_prvs": "0",
    "cncl_yn": "Y",
    "tot_ccld_amt": "0",
    "ord_dvsn_cd": "00",
    "cncl_cfrm_qty": "0",
    "rmn_qty": "0",
    "rjct_qty": "0",
    "excg_id_dvsn_cd": "KRX",
}


def measured_rows(**overrides: str) -> tuple[dict[str, str], dict[str, str]]:
    """``(cancel row, original row)`` in the order the broker returned them, plus overrides."""
    return (
        {**MEASURED_CANCEL_ROW, **overrides},
        {**MEASURED_ORIGINAL_ROW, **overrides},
    )
