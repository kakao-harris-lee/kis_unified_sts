# Superpowers Plans Index

> **2026-11-12 — 미참조 과거 문서 정리.** 저장소 어디에서도 참조하지 않는 과거
> 문서를 삭제했다. 내용은 git 이력에 그대로 남아 있다:
> `git log --diff-filter=D -- docs/`.

Last updated: 2026-11-12.

`docs/superpowers/plans/` holds generated implementation plans that still need
active attention. **None remain today**: the 2026-06/07 plans and the whole
`archive/` tree described the legacy stock/futures runtime removed in L1–L7 and
were unreferenced, so they were deleted on 2026-11-12.

Use the surviving design specs in `docs/superpowers/specs/` for design
rationale, and `docs/runbooks/` for current operational procedures.

## Status

Active plans: none.

Active design specs:

| Date | Spec | Purpose |
|---|---|---|
| 2026-07-08 | [Re-entry guard fix (RC4)](../specs/2026-07-08-reentry-guard-fix.md) | Re-entry guard key-mismatch design. |
| 2026-07-07 | [Setup D trend filter design](../specs/2026-07-07-setup-d-trend-filter-design.md) | Mitigation for Setup D entering repeatedly against steady one-way trend days; implemented but **ships OFF by default** (enable acceptance criteria not met on available data). |

Retained archived spec:

| Date | Spec | Purpose |
|---|---|---|
| 2026-06-25 | [mr-highvol Setup D spec](../specs/archive/2026-06-25-futures-mr-highvol-setup-d.md) | Research/design/validation for the Setup D VWAP reversion strategy — the CP-3 B3 witness's setup (`shared/decision/setups/vwap_reversion.py`, `config/strategies/futures/setup_d_vwap_reversion.yaml`). |

## Adding A New Superpowers Plan

1. Add new implementation plans at this level only while work is actively
   underway.
2. Link the design spec in `docs/superpowers/specs/`.
3. After implementation lands and runbooks/docs point at the current operating
   procedure, drop the plan from this index — the record stays in the history.
