"""Environment-label consistency predicate (design #40 D4-b; ADR-002-013 :498).

Realizes design doc #40's D4.1 environment-isolation check
(``docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-decisions.md`` §D4.1
line 113): "런타임은 기동 인자로 받은 환경 라벨과 custody 디렉터리의 매니페스트
라벨이 **불일치하면 기동 거부**." ADR-002-013 §19 line 498 verbatim: "Test,
simulation, development, paper, restricted-live, and production SHALL use distinct
identities, credentials, routes, trust roots, endpoint policies, and account
allowlists sufficient to make cross-environment broker acceptance impossible."

This module authors only the pure comparison; **refusing to boot** on a mismatch is
a runtime (``tos_runtime``) action, out of kernel scope (D1 not yet ratified — this
predicate has no side effect, it only reports).

Pure module: stdlib only (no ``pydantic`` needed — a two-string comparison needs no
typed record); no ``shared.*``, no I/O.
"""

from __future__ import annotations

__all__ = ["environment_label_consistent"]


def environment_label_consistent(
    runtime_label: str | None, manifest_label: str | None
) -> bool:
    """Whether the boot-arg environment label matches the custody manifest's label.

    Fail-closed (playbook §2.A): either label being ``None`` or blank is treated
    as "not provably consistent", never as a vacuous match — an unlabeled boot
    argument or an unlabeled custody manifest is exactly the ambiguity
    ADR-002-013 :498's "distinct identities... sufficient to make cross-
    environment broker acceptance impossible" is designed to foreclose, so the
    absence of a label can never be read as "the labels happen to agree".
    Positive admission requires byte-exact equality — no case-folding, no
    prefix/substring match, no environment-family grouping (e.g.
    ``"restricted-live"`` and ``"production"`` are never treated as compatible).

    Args:
        runtime_label: The environment label supplied as a boot argument.
        manifest_label: The environment label recorded in the D4 custody
            directory's manifest.

    Returns:
        ``True`` iff both labels are present, non-blank, and byte-exact equal.
    """
    if runtime_label is None or manifest_label is None:
        return False
    if not runtime_label.strip() or not manifest_label.strip():
        return False
    return runtime_label == manifest_label
