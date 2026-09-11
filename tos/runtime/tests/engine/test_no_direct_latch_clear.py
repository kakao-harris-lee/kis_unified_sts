"""Grep-pin canary: nothing under ``tos_runtime/src`` outside
:mod:`tos_runtime.compose._types` calls ``SqliteEventInbox.clear_new_risk_halt`` directly
(re-review finding RR2, 2026-09-09) — mirrors ``test_no_direct_core_calls.py``'s own idiom for
``EngineCore.handle``/``run``.

**Why this exists.** ``ComposedRuntime.clear_new_risk_halt`` (:mod:`tos_runtime.compose._types`)
is the ONLY sanctioned door onto the independent-review finding #3 new-risk halt latch's clear
path: it durably appends ``NEW_RISK_HALT_CLEARED_BY_OPERATOR`` / ``NEW_RISK_HALT_CLEAR_REFUSED``
evidence BEFORE calling the storage-layer guard
(:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.clear_new_risk_halt`). The storage layer
performs the exact same seq/attestation checks but writes NO evidence of its own — the re-review
measured directly that a bare ``inbox.clear_new_risk_halt(...)`` call clears the latch with zero
evidence rows. This pin makes "only the wrapper calls it" mechanical rather than conventional.

A pattern match, not an AST walk — deliberately simple, mirroring
``test_no_direct_core_calls.py``'s own stated rationale. Scoped to ``tos_runtime/src`` ONLY (not
``tos_runtime/tests``): re-review finding RR1's own direct unit tests on
``SqliteEventInbox.clear_new_risk_halt`` (``tests/engine/test_inbox.py``) are exactly the
storage-layer guard exercised on its own terms, independent of the compose fixture the wrapper
needs — those are legitimate, in-scope test callers, not a bypass of the operator door.
"""

from __future__ import annotations

import re
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]  # tos/runtime
_SRC = _RUNTIME_ROOT / "src"

#: The only MODULE allowed to call ``inbox.clear_new_risk_halt(`` directly — this IS the
#: sanctioned wrapper, by design (module docstring). No per-line marker escape hatch: there is no
#: legitimate reason for a second production caller to exist under ``src``.
_ALLOWED_FILES = {
    _SRC / "tos_runtime" / "compose" / "_types.py",
}

#: Matches a call to ``clear_new_risk_halt(`` on something ending in ``inbox`` (``self.inbox.``,
#: ``self._inbox.``, a bare ``_inbox.``, ``runtime.inbox.``, ...) — the storage-layer method's own
#: receiver shape in every real call site. Does NOT match a bare string mention of the method name
#: (e.g. ``driver.py``'s own operator-facing detail text, which names
#: ``ComposedRuntime.clear_new_risk_halt`` — no ``inbox.`` immediately before the dot).
#:
#: **MEDIUM-7 (independent review, disposed).** The prior pattern, ``\binbox\.clear_new_risk_halt\(``,
#: relied on a ``\b`` word boundary immediately before ``inbox`` — but ``\b`` fires only at a
#: transition between a word char and a non-word char, and ``_`` IS a word character. So
#: ``self._inbox.clear_new_risk_halt(`` (:mod:`tos_runtime.safety.rearm`'s own
#: :class:`~tos_runtime.safety.rearm.ReArmWorkflow`, which stores its read-only inbox reference as
#: ``self._inbox``) never matched at all — this pin was blind to exactly the module whose own
#: module docstring promises it never calls the storage-layer clear. ``[\w.]*`` (any run of word
#: characters or dots, including none) in place of the ``\b`` anchor matches every real receiver
#: shape (``self.inbox.``, ``self._inbox.``, a bare ``_inbox.``, ``runtime.inbox.``) while still
#: requiring the literal ``inbox.clear_new_risk_halt(`` substring, so ``driver.py``'s prose mention
#: of ``ComposedRuntime.clear_new_risk_halt`` (no ``inbox.`` immediately before the dot) and the
#: method's own ``def clear_new_risk_halt(`` line still do not match.
_DIRECT_CALL = re.compile(r"[\w.]*inbox\.clear_new_risk_halt\(")


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def test_no_direct_inbox_latch_clear_calls_outside_the_compose_wrapper() -> None:
    offenders: list[str] = []
    for path in _python_files(_SRC):
        if path in _ALLOWED_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _DIRECT_CALL.search(line):
                offenders.append(
                    f"{path.relative_to(_RUNTIME_ROOT)}:{lineno}: {line.strip()}"
                )
    assert offenders == [], (
        "direct SqliteEventInbox.clear_new_risk_halt( call(s) found outside "
        "tos_runtime/compose/_types.py — this bypasses the evidence-writing operator door "
        "(re-review finding RR2):\n" + "\n".join(offenders)
    )


def test_the_pattern_itself_catches_every_real_receiver_shape() -> None:
    r"""MEDIUM-7 mutation pin: prove the regex, not just the file scan, actually catches
    ``self._inbox.clear_new_risk_halt(`` — the exact shape :mod:`tos_runtime.safety.rearm` uses
    for its (read-only, never-called-this-way) inbox reference. The prior ``\binbox\.`` pattern
    silently let this receiver shape through (word-boundary blind spot between ``_`` and ``i``);
    this test would have caught that regression directly, without needing a real offending file.
    """
    caught = (
        "self._inbox.clear_new_risk_halt(",
        "self.inbox.clear_new_risk_halt(",
        "_inbox.clear_new_risk_halt(",
        "runtime.inbox.clear_new_risk_halt(",
    )
    for scratch in caught:
        assert _DIRECT_CALL.search(
            scratch
        ), f"_DIRECT_CALL must match the real receiver shape {scratch!r}"

    not_caught = (
        "ComposedRuntime.clear_new_risk_halt(latched_evidence_seq=1, approvals_dir=path)",
        "    def clear_new_risk_halt(",
    )
    for scratch in not_caught:
        assert not _DIRECT_CALL.search(
            scratch
        ), f"_DIRECT_CALL must NOT match the non-offending text {scratch!r}"
