"""CP-3 B1b — the committed Setup D **SHORT** strategy content, and the drift
guard that ties BOTH B1b renders to their deployed tenant trees.

The LONG mirror of the first four claims is
``test_cp3_strategy_content.py``; this module adds the SHORT half plus two
things neither file had before 2026-10-09:

* **the deployed-tree drift guard.** ``config/tos_runtime/cp3-setup-d-long/``
  and ``…-short/`` each carry a copy of a B1b strategy file with its account /
  instrument replaced by the named-TBD token. Nothing checked that the copies
  were still copies — ``test_tenant_tree_copies.py`` compares each tenant tree
  against the RESIDENT tree and ``test_tenant_tree_short.py`` compares the two
  tenant trees against each other, so the B1b ↔ deployed edge was unguarded in
  both directions. A B1b run therefore measured parity for a rule the
  deployment might no longer carry. This module closes that edge for both
  directions at once;
* **the two renders are different strategies, not one with a sign flip** — the
  SHORT entry fires at ``z_x1000 >= +1800`` and must NOT fire on a LONG-extreme
  bar, measured through the real driver rather than asserted about the YAML.

Hermetic: repo files read with ``yaml`` and plain paths (no ``shared.*`` — the
firewall forbids it for runtime scope outright), synthetic JSONL under
``tmp_path``, no network, no clock.
"""

from __future__ import annotations

import copy
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.dsl import DecisionKind
from tos.engine.admission import policy_work_steps, strategy_admissible
from tos.engine.vocabulary import AdmissionVerdict

from .. import runner
from ..lineage import entry_comparison
from . import _cp3_fixtures as fx

#: ``config/strategies/futures/setup_d_vwap_reversion.yaml`` 74행
#: ``extreme_atr_mult: 1.8`` — the citation, as a ``Decimal`` so the ×1000 is
#: exact (``1.8 * 1000`` in binary float is ``1800.0000000000002``).
CITED_EXTREME_ATR_MULT = Decimal("1.8")

#: The expected SHORT binding: ``+trunc(1.8 × 1000)``. The LONG file's mirror
#: constant is ``-1800``; the sign is the whole difference.
EXPECTED_Z_ENTRY_MIN_X1000 = 1800

#: ``B1b config_dir -> deployed tenant tree``, for the drift guard. Both edges
#: are checked, so the guard cannot be satisfied by the direction that happens
#: to be under edit.
B1B_TO_DEPLOYED = {
    "LONG": (
        ("strategies", "setup_d_long.strategy.yaml"),
        ("cp3-setup-d-long", "setup_d_long.strategy.yaml"),
    ),
    "SHORT": (
        ("short", "strategies", "setup_d_short.strategy.yaml"),
        ("cp3-setup-d-short", "setup_d_short.strategy.yaml"),
    ),
}

#: The leaves a deployed copy replaces with the named-TBD token, because the
#: account number and the contract month are never committed. Normalising THESE
#: and nothing else is what makes the comparison meaningful: a drift guard that
#: normalised the comparison operator, or the direction, would admit the two
#: files being different strategies.
COORDINATE_KEYS = ("account", "instrument")
NAMED_TBD = "TBD"


def _repo_root() -> Path | None:
    """The repo root, found by walking up for the two directories that mark it.

    ``None`` when this package was extracted away from the repo. Every caller
    FAILS on ``None`` rather than skipping: a drift guard that quietly does not
    run is the guard this module exists because of.
    """
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tos").is_dir() and (candidate / "config").is_dir():
            return candidate
    return None


def _require_repo_root() -> Path:
    repo_root = _repo_root()
    if repo_root is None:  # pragma: no cover - only outside the repo checkout
        pytest.fail(
            "cannot locate the repo root from this test file — the deployed-tree "
            "cross-checks cannot be skipped silently"
        )
    return repo_root


def _short_content() -> runner.LoadedStrategyContent:
    """The committed SHORT strategy content, through the production loader."""
    return runner.load_strategy_content(
        strategy_path=fx.SHORT_STRATEGY_PATH, bindings_path=fx.SHORT_BINDINGS_PATH
    )


def normalise_coordinates(document: Any) -> Any:
    """A strategy document with every target's account/instrument set to TBD.

    Applied to BOTH sides, so the deployed copy (which already carries
    ``"TBD"``) is unchanged by it and the B1b copy's harness literals are
    erased. Nothing else is touched — in particular not ``op``, ``direction``,
    ``position_effect`` or any ``rationale``.
    """
    out = copy.deepcopy(document)
    for rule in out["policy"]["rules"]:
        target = rule["decision"].get("target")
        if not target:
            continue
        for key in COORDINATE_KEYS:
            if key in target:
                target[key] = NAMED_TBD
    return out


# ---------------------------------------------------------------------------
# The SHORT render loads, is admitted, and carries the mirrored threshold
# ---------------------------------------------------------------------------


def test_short_strategy_loads_through_the_real_loader_and_admission_gate() -> None:
    """The committed SHORT file is admitted by the shipped loader.

    Its own ``config_dir`` is load-bearing: ``load_strategy_content`` refuses a
    ``strategies/`` directory holding more than the one requested file, so a
    SHORT file beside the LONG one would refuse the LONG run too. Passing here
    means a boot would accept this file, with the same null-leaf / ``"TBD"`` /
    stray-file / unknown-key / orphan-binding discipline.
    """
    content = _short_content()
    assert strategy_admissible(content.strategy).verdict is AdmissionVerdict.ADMISSIBLE
    assert content.instrument_key.instrument == fx.INSTRUMENT
    assert content.instrument_key.account == "cp3-b1b-short"
    assert content.direction == "SHORT"
    assert content.strategy.dsl_version == "cp3-b1b-dsl-1"
    assert content.strategy.config_binding_version == "cp3-b1b-bind-1"
    assert content.bindings == {"z_entry_min_x1000": EXPECTED_Z_ENTRY_MIN_X1000}


def test_short_policy_shape_mirrors_the_long_one() -> None:
    """Entry first, then the two FLAT exits, then the mandatory default.

    The FLAT targets' ``direction`` is ``LONG``: the DSL's FLAT direction is
    the direction of the CLOSING action (``tos.dsl.proposal.build_flat``), and
    a short is closed by buying. Asserted here because the token reads
    backwards at a glance and a "fix" would invert the deployment.
    """
    content = _short_content()
    policy = content.strategy.policy
    assert policy is not None
    kinds = [rule.decision.kind for rule in policy.rules]
    assert kinds == [DecisionKind.ACTION, DecisionKind.FLAT, DecisionKind.FLAT]
    assert policy.default.kind is DecisionKind.NO_ACTION
    assert [len(rule.all_of) for rule in policy.rules] == [5, 1, 1]
    entry = policy.rules[0].decision.target
    assert entry is not None
    assert entry.quantity_basis == "RISK"
    assert entry.direction == "SHORT"
    assert entry.position_effect == "OPEN"
    for rule in policy.rules[1:]:
        target = rule.decision.target
        assert target is not None
        assert target.position_effect == "CLOSE"
        assert target.direction == "LONG"


def test_short_work_steps_fit_the_injected_budget() -> None:
    """Same ``3 + 7 + 14 = 24`` as the LONG render — the counts do not move."""
    content = _short_content()
    policy = content.strategy.policy
    assert policy is not None
    steps = policy_work_steps(policy)
    assert steps == content.work_steps == 3 + 7 + 14 == 24
    assert steps <= runner.DEFAULT_BUDGET_STEPS == 64
    compares = sum(len(rule.all_of) for rule in policy.rules)
    assert compares == 7 <= 20


def test_short_z_entry_binding_is_plus_trunc_extreme_atr_mult_times_1000() -> None:
    """The authored binding equals ``+trunc(extreme_atr_mult × 1000)``.

    The LONG mirror of this test lives in ``test_cp3_strategy_content.py``; the
    sign is the only difference, and the ``extreme_atr_mult`` is read from the
    legacy YAML below rather than restated, for the reason that file's 2026-10-08
    review recorded: a test-local literal stays green while the shipped
    derivation becomes false.
    """
    content = _short_content()
    derived = int(CITED_EXTREME_ATR_MULT * 1000)
    assert derived == EXPECTED_Z_ENTRY_MIN_X1000
    assert content.bindings["z_entry_min_x1000"] == derived


def test_cited_extreme_atr_mult_still_matches_the_legacy_setup_d_yaml() -> None:
    """The citation is checked against the file it cites — not trusted."""
    path = (
        _require_repo_root()
        / "config"
        / "strategies"
        / "futures"
        / "setup_d_vwap_reversion.yaml"
    )
    assert path.is_file(), f"{path} is missing — the cited source must exist"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    params = document["strategy"]["entry"]["params"]
    actual = Decimal(str(params["extreme_atr_mult"]))
    assert actual == CITED_EXTREME_ATR_MULT, (
        f"{path} now declares extreme_atr_mult={actual}; the SHORT render's "
        f"z_entry_min_x1000 ({EXPECTED_Z_ENTRY_MIN_X1000}) is derived from "
        f"{CITED_EXTREME_ATR_MULT} and is stale"
    )


def test_the_entry_comparison_the_lineage_publishes_is_the_authored_one() -> None:
    """``parents.strategy_file.entry_comparison`` is rendered, never a literal.

    B1b-D5's note quotes this phrase. Rendered from the authored compare and
    the resolved binding, it cannot disagree with the file it describes; a
    literal could.
    """
    assert entry_comparison(_short_content()) == "z_x1000 >= 1800"
    long_content = runner.load_strategy_content(
        strategy_path=fx.STRATEGY_PATH, bindings_path=fx.BINDINGS_PATH
    )
    assert entry_comparison(long_content) == "z_x1000 <= -1800"


# ---------------------------------------------------------------------------
# The drift guard: each B1b render still equals its deployed tenant copy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("direction", sorted(B1B_TO_DEPLOYED))
def test_b1b_copy_equals_the_deployed_tenant_strategy_after_normalising_coordinates(
    direction: str,
) -> None:
    """The deployed tenant strategy IS the B1b one, modulo account/instrument.

    Concrete failing input: an operator retunes the SHORT entry in
    ``config/tos_runtime/cp3-setup-d-short/strategies/setup_d_short.strategy.yaml``
    — flips ``GE`` to ``LE``, renames a gate, edits a ``rationale`` — and the
    B1b render that the parity report was measured with keeps the old rule. The
    report would then describe a deployment that no longer exists. Nothing
    checked this edge before 2026-10-09: ``test_tenant_tree_copies.py`` checks
    tenant-vs-resident and ``test_tenant_tree_short.py`` checks LONG-vs-SHORT,
    and neither reaches ``tos/runtime/cp3/``.

    Compared as PARSED YAML, not bytes: the two files carry different header
    comments on purpose (each explains its own role), and a byte comparison
    would either fail forever or force the comments to be identical and
    therefore wrong in one of the two places.
    """
    repo_root = _require_repo_root()
    b1b_parts, (tree, filename) = B1B_TO_DEPLOYED[direction]
    b1b_path = Path(__file__).resolve().parent.parent.joinpath(*b1b_parts)
    deployed_path = (
        repo_root / "config" / "tos_runtime" / tree / "strategies" / filename
    )
    assert b1b_path.is_file(), b1b_path
    assert deployed_path.is_file(), deployed_path

    b1b_doc = yaml.safe_load(b1b_path.read_text(encoding="utf-8"))
    deployed_doc = yaml.safe_load(deployed_path.read_text(encoding="utf-8"))
    assert normalise_coordinates(b1b_doc) == normalise_coordinates(deployed_doc), (
        f"{b1b_path} and {deployed_path} have diverged beyond the coordinate "
        f"leaves {COORDINATE_KEYS}. Whichever was edited, the other must follow "
        "in the SAME PR — a parity run measured against the B1b copy says "
        "nothing about a deployment that carries different rules."
    )
    # The normalisation only erases coordinates: the deployed copy's targets
    # really are the named-TBD token (the operator-fill gate), and the B1b
    # copy's really are concrete. Without this, a normaliser that blanked the
    # whole target would satisfy the equality above.
    for rule in deployed_doc["policy"]["rules"]:
        target = rule["decision"].get("target")
        if target:
            assert [target[k] for k in COORDINATE_KEYS] == [NAMED_TBD, NAMED_TBD]
    for rule in b1b_doc["policy"]["rules"]:
        target = rule["decision"].get("target")
        if target:
            assert NAMED_TBD not in [target[k] for k in COORDINATE_KEYS]


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda doc: doc["policy"]["rules"][0]["all_of"][-1].__setitem__("op", "LE"),
            id="entry-operator-flipped",
        ),
        pytest.param(
            lambda doc: doc["policy"]["rules"][0]["decision"]["target"].__setitem__(
                "direction", "LONG"
            ),
            id="entry-direction-flipped",
        ),
        pytest.param(
            lambda doc: doc["policy"]["rules"][0]["all_of"][0]["left"][
                "ref"
            ].__setitem__(2, "entry_window_v2"),
            id="gate-renamed",
        ),
        pytest.param(
            lambda doc: doc["policy"]["rules"][1]["decision"].__setitem__(
                "rationale", "R2-EXIT-VWAP-REVERTED: something else entirely."
            ),
            id="rationale-rewritten",
        ),
        pytest.param(
            lambda doc: doc["policy"]["rules"][0]["all_of"][-1]["right"][
                "ref"
            ].__setitem__(1, "z_entry_max_x1000"),
            id="binding-key-swapped",
        ),
    ],
)
def test_the_drift_guard_rejects_a_divergent_deployed_copy(mutate: Any) -> None:
    """The red half: each mutation the guard must catch, applied in memory.

    Without these, ``normalise_coordinates`` could be weakened to blank
    whatever differs and the equality above would stay green forever. Each
    case is a change an operator could plausibly make to the deployed tree
    alone — the operator, the direction, a gate name, a rationale, the bound
    key — and each must break the equality.
    """
    b1b_doc = yaml.safe_load(fx.SHORT_STRATEGY_PATH.read_text(encoding="utf-8"))
    deployed = normalise_coordinates(b1b_doc)
    mutate(deployed)
    assert normalise_coordinates(b1b_doc) != deployed


def test_b1b_bindings_equal_the_deployed_tenant_bindings() -> None:
    """The bindings files carry no coordinates, so they compare unnormalised.

    Concrete failing input: the deployed SHORT bindings are retuned to
    ``z_entry_min_x1000: 1900`` and the B1b copy keeps ``1800`` — every
    agreement number in the parity report would then be about a threshold the
    deployment does not use.
    """
    repo_root = _require_repo_root()
    pairs = {
        "LONG": (fx.BINDINGS_PATH, "cp3-setup-d-long"),
        "SHORT": (fx.SHORT_BINDINGS_PATH, "cp3-setup-d-short"),
    }
    for direction, (b1b_path, tree) in pairs.items():
        deployed_path = (
            repo_root / "config" / "tos_runtime" / tree / "strategy_bindings.yaml"
        )
        assert yaml.safe_load(b1b_path.read_text(encoding="utf-8")) == yaml.safe_load(
            deployed_path.read_text(encoding="utf-8")
        ), f"{direction}: {b1b_path} and {deployed_path} have diverged"


# ---------------------------------------------------------------------------
# The two renders are different strategies, measured through the driver
# ---------------------------------------------------------------------------


def test_the_short_entry_fires_on_the_positive_extreme_and_not_the_negative(
    tmp_path: Path,
) -> None:
    """Driven through the real core: ``+1800`` fires, ``+1799`` and ``-1800`` do not.

    This is what makes "the SHORT render is a different strategy, not a sign
    flip" a measurement. A file that kept the LONG comparison would fire on the
    LONG-extreme bar and stay silent on the SHORT one; both halves are asserted
    so neither direction of that mistake passes.
    """
    lines = fx.synthetic_stream(
        bar_count=4,
        special={
            1: fx.short_entry_fields,
            2: fx.short_near_miss_entry_fields,
            3: fx.entry_fields,  # the LONG extreme: z_x1000 = -1800
        },
    )
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=_short_content()
    )
    fired = artifacts.rule_fire_counts
    assert fired.get("R1-ENTRY-SHORT") == 1, fired
    assert fired.get("R0-DEFAULT-NO-ACTION") == 3, fired
    assert artifacts.outcome_counts == {
        DecisionKind.ACTION.value: 1,
        DecisionKind.NO_ACTION.value: 3,
    }


def test_the_long_render_does_not_fire_on_the_short_extreme(tmp_path: Path) -> None:
    """The mirror: the committed LONG file must ignore ``z_x1000 = +1800``."""
    lines = fx.synthetic_stream(
        bar_count=3, special={1: fx.short_entry_fields, 2: fx.entry_fields}
    )
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    content = runner.load_strategy_content(
        strategy_path=fx.STRATEGY_PATH, bindings_path=fx.BINDINGS_PATH
    )
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=content
    )
    assert artifacts.rule_fire_counts.get("R1-ENTRY-LONG") == 1
    assert artifacts.rule_fire_counts.get("R0-DEFAULT-NO-ACTION") == 2


def test_the_short_lineage_declares_its_direction_and_the_short_difference(
    tmp_path: Path,
) -> None:
    """``parents.strategy_file.direction`` is SHORT and B1b-D5 says SHORT side.

    B3 reads that key to decide which legacy fires its AGREE_ENTRY half is, so
    a lineage that omitted it (or kept LONG) would make the SHORT measurement
    report the LONG denominator.
    """
    path = fx.write_jsonl(
        tmp_path / "fields.jsonl",
        fx.synthetic_stream(bar_count=3, special={1: fx.short_entry_fields}),
    )
    content = _short_content()
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=content
    )
    lineage = runner.build_lineage(
        artifacts=artifacts,
        content=content,
        fields_path=path,
        fields_lineage_path=None,
        budget_steps=runner.DEFAULT_BUDGET_STEPS,
        max_unresolved_send_per_scope=runner.DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE,
    )
    strategy_block = lineage["parents"]["strategy_file"]
    assert strategy_block["direction"] == "SHORT"
    assert strategy_block["entry_comparison"] == "z_x1000 >= 1800"
    d5 = next(
        item for item in lineage["declared_differences"] if item["id"] == "B1b-D5"
    )
    assert d5["item"] == "SHORT side only"
    assert "z_x1000 >= 1800" in d5["note"]
    assert "the LONG half is a separate render" in d5["note"]


def test_the_regime_guard_difference_says_why_it_cannot_show_up(
    tmp_path: Path,
) -> None:
    """B1b-D8 points at B2-L1 and does NOT claim its zero count as evidence.

    ``short_blocked_regimes`` is the operator's 결정 5 deletion and it bites
    the SHORT side asymmetrically in a DEPLOYMENT — but it cannot produce a
    decision-level difference in a B1a/B2/B1b comparison, because the legacy
    side of that comparison never applies it either: the block lives in
    ``shared/strategy/entry/setup_d_adapter.py``, AFTER ``check()`` returns,
    and B2 drives ``check()``. B2 already declares exactly that as **B2-L1**,
    so B1b-D8 cites it rather than re-deriving it.

    The second half is the 2026-10-09 review's L1: the note must NOT offer
    ``attribution_ids['B1b-D8'] == 0`` as evidence. No attribution rule cites
    B1b-D8, so that zero holds by construction and would hold even if the
    guard did bite. What backs "no hidden regime difference in this window" is
    the UNRESOLVED count.
    """
    content = _short_content()
    path = fx.write_jsonl(tmp_path / "fields.jsonl", fx.synthetic_stream(bar_count=2))
    lineage = runner.build_lineage(
        artifacts=runner.run_replay(
            records=runner.read_field_records(path), content=content
        ),
        content=content,
        fields_path=path,
        fields_lineage_path=None,
        budget_steps=runner.DEFAULT_BUDGET_STEPS,
        max_unresolved_send_per_scope=runner.DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE,
    )
    note = next(
        item for item in lineage["declared_differences"] if item["id"] == "B1b-D8"
    )["note"]
    assert "setup_d_adapter.py:174" in note
    assert "B2-L1" in note
    assert "emit_legacy_decisions.py:946" in note
    assert "UNRESOLVED" in note
    # The overclaim the review found, asserted as an ABSENCE: the earlier note
    # said "the item absorbs zero bars" as if that measured something.
    assert "absorbs zero bars" not in note
    assert "BY CONSTRUCTION" in note

    # The claims are checked against the files they are about. (1) the block is
    # still downstream of check() in the adapter.
    repo_root = _require_repo_root()
    adapter = (
        repo_root / "shared" / "strategy" / "entry" / "setup_d_adapter.py"
    ).read_text(encoding="utf-8")
    check_at = adapter.index("self._setup.check(")
    block_at = adapter.index("short_blocked_regimes")
    assert check_at < block_at, (
        "the regime block moved ahead of check(); B1b-D8's note now claims "
        "something false about what B2 measures"
    )
    # (2) the NEGATIVE half, which the previous revision never checked: the
    # setup `check()` B2 drives must itself contain no regime block. Reading
    # only the adapter leaves "B2 never applies it" resting on the absence
    # being somewhere else — if a regime gate were added to the setup, the
    # adapter assertion above would still pass and the note would be false.
    setup_src = (
        repo_root / "shared" / "decision" / "setups" / "vwap_reversion.py"
    ).read_text(encoding="utf-8")
    for token in (
        "short_blocked_regimes",
        "long_blocked_regimes",
        "resolve_regime_label",
    ):
        offenders = [
            line
            for line in setup_src.splitlines()
            if token in line and not line.lstrip().startswith("#")
        ]
        assert not offenders, (
            f"{token} now appears in SetupDVWAPReversion's own module outside a "
            f"comment ({offenders[:2]}); B2 drives check() directly, so B1b-D8's "
            "claim that the legacy side of this comparison never applies the "
            "regime block would no longer hold"
        )
