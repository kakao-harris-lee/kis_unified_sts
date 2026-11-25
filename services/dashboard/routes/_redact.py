"""Reader-side redaction: the web tier does not trust the exporter to be right.

``/tos`` is reachable from the internet behind Cloudflare Access and the app has
no auth of its own, so a host path or an account number in a response body is a
disclosure. The exporters already redact (``tools/tos_cp3/redact.py``) — but
"already redacted upstream" is an assumption, and the one time it was wrong
(#1179 review: runner ``ABORT`` lines carrying ``$TENANT_CUSTODY_ROOT`` reached
``board.json`` and the route served them) nothing downstream noticed.

So this module redacts again, on the way out. It is **not** a second copy of a
shared library: ``services/`` cannot import ``tools/`` (the dashboard image does
not carry it and the firewall forbids reaching the kernel side), so the two
sides meet through the file and each states the rule itself — the same reason
every TOS read model restates its exporter's constants. The two implementations
are deliberately kept simple enough to read side by side, and the shared
fixture ``tests/fixtures/tos/redaction-cases.json`` pins the cases both must
agree on.

A document needing redaction here is a **fault**, not a normal state: it means
the exporter regressed. The caller logs it at ``WARNING`` and reports
``redacted=true`` on the response, so the page can say the document was altered
rather than quietly serving a scrubbed version of a broken export.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["ACCOUNT_PLACEHOLDER", "PATH_PLACEHOLDER", "redact_payload"]

#: Mirrors ``tools/tos_cp3/redact.py``'s own constants. Restated, not imported.
PATH_PLACEHOLDER = "<경로>"
ACCOUNT_PLACEHOLDER = "<계좌>"

#: A web URL, matched only so it can be handed back **unchanged**: without it
#: the path rule eats ``//host/path`` and serves half an address.
#:
#: SAFETY: http(s) only — ``file:///home/…`` and ``sqlite:////home/…`` are host paths wearing a scheme, and a generic ``\w+://`` carve-out would hand them through untouched
_URL = r"(?P<url>https?://[^\s'\"<>]*)"

#: A dashboard route path. Kept as-is: ``/api/tos/status`` is this service's
#: own public surface, and masking it turns an instruction into «<경로>».
_ROUTE = r"(?P<route>/api/[A-Za-z0-9_./\-]*)"

#: An absolute path glued straight onto an ASCII word (``data_leaf/home/…``),
#: which the POSIX rule's lookbehind refuses. Only well-known roots, so a word
#: followed by an ordinary two-segment path is not swept up with it.
_GLUED_ROOT = r"(?P<glued>/(?:home|tmp|var|mnt|root|etc|usr|opt)/[A-Za-z0-9_./@%+\-]*)"

#: Windows shapes — ``C:\…``, ``C:/…`` and ``\\wsl$\…`` UNC.
_WINDOWS = (
    r"(?P<win>(?<![A-Za-z0-9_])"
    r"(?:[A-Za-z]:[\\/]|\\\\[A-Za-z0-9_.$-]+\\)[^\s'\"<>]*)"
)

#: ``$HOME/…`` / ``${TENANT_CUSTODY_ROOT}/…``, as the runners interpolate them.
_SHELL = r"(?P<shell>\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/[A-Za-z0-9_./@%+\-]*)"

#: An absolute (or ``~``-rooted) path token: ``~/…``, or two or more segments.
#: The lookbehind is ASCII-only on purpose — Hangul must NOT shield a path, or
#: ``잎/home/deploy/x`` ships whole (#1179 review LOW) — and the two-segment
#: floor is what keeps «확인/막힘» and «손익/pnl» from reading as paths.
_POSIX = (
    r"(?P<posix>(?<![A-Za-z0-9_.])"
    r"(?:~/[A-Za-z0-9_./@%+\-]*|/[A-Za-z0-9_.@%+\-]+(?:/[A-Za-z0-9_.@%+\-]*)+))"
)

#: A relative state path: ``.local/state/tos/…``. The first segment must carry
#: a letter, or ``.5/2`` reads as one and a decimal pair is masked.
_RELATIVE = (
    r"(?P<rel>(?<![A-Za-z0-9_./~])"
    r"\.[A-Za-z0-9_\-]*[A-Za-z][A-Za-z0-9_\-]*(?:/[A-Za-z0-9_.@%+\-]+)+)"
)

_PATH_TOKEN = re.compile(
    "|".join((_URL, _WINDOWS, _SHELL, _ROUTE, _GLUED_ROOT, _POSIX, _RELATIVE))
)

#: A quoted path is redacted to its closing quote, so the tail of a path with a
#: space in it (``'/home/deploy/my data/x.yaml'``) does not survive the token
#: rule, which stops at the space.
_QUOTED_PATH = re.compile(
    r"""(['"])((?:~?/|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/|[A-Za-z]:[\\/]|\\\\)[^'"]*)\1"""
)

_ASCII_LETTER = re.compile(r"[A-Za-z]")

#: Account-number shapes. The 10-digit floor is why session names
#: (``…-20261125``) and symbols (``000660``) survive.
_HYPHENATED_ACCOUNT = re.compile(r"(?<!\d)\d{8}-\d{2}(?!\d)")
_BARE_ACCOUNT = re.compile(r"(?<!\d)\d{10,12}(?!\d)")

#: Eight digits that an account-ish label introduces (``CANO=…``, ``계좌 …``).
#:
#: SAFETY: a bare eight-digit run is never masked — that is the trading date (20261125), and masking it blanks every session name on the page
_LABELLED_ACCOUNT = re.compile(
    r"((?:CANO|ACNO|ACCT|ACCOUNT|계좌)[A-Za-z0-9_가-힣]*"  # label, Korean tail included
    r"(?:\s*(?:no|num|number)\.?)?"  # «acct no», «Account No.»
    r"\s*[:=]?\s*)(\d{8})(?![\d-])",
    re.IGNORECASE,
)

#: Keys whose value is a structured identifier, exempt from the account
#: *pattern* rule only.
#:
#: SAFETY: broker_execution_id is a broker order number (odno), not an account — it is ten digits, and masking it would leave the operator unable to find that order at the broker
_IDENTIFIER_KEYS = frozenset({"broker_execution_id"})


def _replace_path_token(match: re.Match[str]) -> str:
    """One token, masked — except a URL, a route and a digits-only run."""
    token = match.group(0)
    if match.lastgroup in {"url", "route"}:
        return token
    # SAFETY: «3 /378» is a ratio, not a path — masking it deletes the measurement the sentence exists to report
    if match.lastgroup == "posix" and not _ASCII_LETTER.search(token):
        return token
    return PATH_PLACEHOLDER


def _redact_text(text: str, *, mask_account_pattern: bool = True) -> str:
    # Quotes first: the token rule stops at a space, which would close the
    # quote around the tail of a path instead of around the placeholder.
    out = _QUOTED_PATH.sub(
        lambda m: f"{m.group(1)}{PATH_PLACEHOLDER}{m.group(1)}", text
    )
    out = _PATH_TOKEN.sub(_replace_path_token, out)
    if mask_account_pattern:
        out = _HYPHENATED_ACCOUNT.sub(ACCOUNT_PLACEHOLDER, out)
        out = _LABELLED_ACCOUNT.sub(rf"\1{ACCOUNT_PLACEHOLDER}", out)
        out = _BARE_ACCOUNT.sub(ACCOUNT_PLACEHOLDER, out)
    return out


def redact_payload(value: Any, _key: str | None = None) -> tuple[Any, bool]:
    """``(redacted value, whether anything changed)``, walking every string leaf.

    Walks keys as well as values: the point is that no field — including one
    added to the exporter tomorrow — can bypass this by not being on a list.
    """
    if isinstance(value, str):
        out = _redact_text(value, mask_account_pattern=_key not in _IDENTIFIER_KEYS)
        return out, out != value
    if isinstance(value, Mapping):
        changed = False
        result: dict[Any, Any] = {}
        for key, item in value.items():
            new_key: Any = key
            if isinstance(key, str):
                new_key = _redact_text(key)
                changed = changed or new_key != key
            new_item, item_changed = redact_payload(item, key)
            changed = changed or item_changed
            result[new_key] = new_item
        return result, changed
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        changed = False
        items = []
        for item in value:
            new_item, item_changed = redact_payload(item, _key)
            changed = changed or item_changed
            items.append(new_item)
        return items, changed
    return value, False
