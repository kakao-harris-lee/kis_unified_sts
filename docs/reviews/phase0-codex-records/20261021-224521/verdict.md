adjudicator: codex
reviewed_at_head: b15069fd1737962d92766e73648b0c2128957d32
reviewed_scope_digest: 86be0b03f72f275b1e8d8d244f5615871f9ec63cd163e1379b3208cc7dc86bac
lane: A (TOS Phase-0 kernel surface, incremental from c5550229)
scope: git diff --shortstat c5550229 HEAD -- <kernel paths>: 361 files changed, 29743 insertions(+), 2288 deletions(-) (repo-wide branch diff; focus restricted to kernel paths)

# Codex Adversarial Review

Target: branch diff against c555022922f2ad9efb09e90f734bdfd18884efb0
Verdict: needs-attention

Do not ship: the new kernel position classifier drops outstanding exposure after nonterminal results. Firewall and spec-status checks pass; completion verification stopped with rc=2 because temporary storage was unavailable.

Findings:
- [high] Preserve outstanding exposure after consumed nonterminal results (tos/src/tos/position/predicates.py:131-140)
  Membership in consumed_by_attempt counts only the filled quantity and skips all outstanding-exposure buckets. However, engine/core.py emits EGRESS_RESULT_CONSUMED for applied ACK, TIMEOUT, UNKNOWN and PARTIAL_FILL results too. Reproduced with a sealed 10-unit BUY: worst-credible usage becomes zero after a consumed zero-fill result, or 7 after a partial fill with 3 remaining. This understates the risk observation and contradicts DR-0003 §2.2's requirement to retain unresolved exposure. The Decimal-only mapping cannot distinguish terminal results from outstanding orders.
  Recommendation: Carry result state and remaining quantity into classification. Retain unresolved quantities in the appropriate unknown or in-flight buckets until terminality is established. Add regressions for ACK, TIMEOUT, UNKNOWN and partial fills in both directions.

Next steps:
- Fix the classifier and verify that nonterminal results cannot erase outstanding exposure.
- Rerun the completion checker with usable temporary storage.
EXIT=0
