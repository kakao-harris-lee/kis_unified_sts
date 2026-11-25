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

#: An absolute (or ``~``-rooted) path token. The lookbehind keeps Korean text
#: and ratios — «확인/막힘», ``0/143`` — from reading as paths.
_ABSOLUTE_PATH = re.compile(r"(?<![\w.])~?/[\w./@%+-]+")

#: Account-number shapes. The 10-digit floor is why session names
#: (``…-20261125``) and symbols (``000660``) survive.
_HYPHENATED_ACCOUNT = re.compile(r"(?<!\d)\d{8}-\d{2}(?!\d)")
_BARE_ACCOUNT = re.compile(r"(?<!\d)\d{10,12}(?!\d)")

#: Keys whose value is a structured identifier, exempt from the account
#: *pattern* rule only.
#:
#: SAFETY: broker_execution_id is a broker order number (odno), not an account — it is ten digits, and masking it would leave the operator unable to find that order at the broker
_IDENTIFIER_KEYS = frozenset({"broker_execution_id"})


def _redact_text(text: str, *, mask_account_pattern: bool = True) -> str:
    out = _ABSOLUTE_PATH.sub(PATH_PLACEHOLDER, text)
    if mask_account_pattern:
        out = _HYPHENATED_ACCOUNT.sub(ACCOUNT_PLACEHOLDER, out)
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
