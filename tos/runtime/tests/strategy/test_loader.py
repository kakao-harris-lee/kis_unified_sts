"""``tos_runtime.strategy.loader`` tests (TOS Phase 3 슬라이스 D-R ``[D-R-1]``,
docs/plans/2026-09-09-tos-phase3-event-core-plan.md §1.2).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml
from tos.engine.vocabulary import AdmissionVerdict
from tos_runtime.strategy.loader import (
    LoadedStrategies,
    StrategyLoadError,
    load_strategies,
)

from .conftest import (
    admissible_strategy_mapping,
    in_process_typed_strategy,
    inadmissible_strategy_mapping,
    write_strategy_yaml,
)


def test_happy_path_loads_one_admissible_strategy(strategies_dir, parse, admit):
    path = write_strategy_yaml(
        strategies_dir, "band.strategy.yaml", admissible_strategy_mapping()
    )
    loaded = load_strategies(strategies_dir, parse=parse, admit=admit)
    assert isinstance(loaded, LoadedStrategies)
    assert len(loaded.strategies) == 1
    entry = loaded.strategies[0]
    assert entry.path == path
    assert entry.strategy.status.value == "ISSUED"
    assert entry.sha256_digest == hashlib.sha256(path.read_bytes()).hexdigest()


def test_loads_multiple_files_in_sorted_path_order(strategies_dir, parse, admit):
    write_strategy_yaml(
        strategies_dir, "b.strategy.yaml", admissible_strategy_mapping()
    )
    write_strategy_yaml(
        strategies_dir, "a.strategy.yaml", admissible_strategy_mapping()
    )
    loaded = load_strategies(strategies_dir, parse=parse, admit=admit)
    assert [entry.path.name for entry in loaded.strategies] == [
        "a.strategy.yaml",
        "b.strategy.yaml",
    ]


def test_unknown_key_refuses_naming_the_path(strategies_dir, parse, admit):
    mapping = admissible_strategy_mapping()
    mapping["policy"]["rules"][0]["decision"]["target"]["not_a_real_field"] = "x"
    path = write_strategy_yaml(strategies_dir, "bad.strategy.yaml", mapping)
    with pytest.raises(StrategyLoadError) as excinfo:
        load_strategies(strategies_dir, parse=parse, admit=admit)
    assert str(path) in str(excinfo.value)


def test_inadmissible_strategy_refuses_naming_the_path(strategies_dir, parse, admit):
    """This test exercises the typed D1<->D4 admission refusal
    (``compare_has_capsule_operand``) — one of the several checks
    ``strategy_admissible`` runs (the D-K lane's escape-checker gate is
    another, exercised by ``tos/tests`` directly). ``load_strategies``
    refuses on ANY ``AdmissionVerdict`` that is not ``ADMISSIBLE`` — it is
    agnostic to which admission rule fired, so it needs no change
    regardless of which gate inside ``strategy_admissible`` rejects."""
    mapping = inadmissible_strategy_mapping()

    # sanity: confirm the fixture is genuinely inadmissible via the real gate
    parsed = parse(mapping)
    assert admit(parsed).verdict is AdmissionVerdict.INADMISSIBLE

    path = write_strategy_yaml(strategies_dir, "inadmissible.strategy.yaml", mapping)
    with pytest.raises(StrategyLoadError) as excinfo:
        load_strategies(strategies_dir, parse=parse, admit=admit)
    assert str(path) in str(excinfo.value)


def test_yaml_and_in_process_typed_paths_admit_identically(
    strategies_dir, parse, admit
):
    """Design #31 §1.2 "두 경로 동형" ("the two paths are isomorphic"): a
    strategy authored as serialized YAML and the SAME strategy built
    in-process via typed construction must converge on the identical
    artifact (same digest/id) and admit identically. This is the concrete
    proof that ``tos_runtime.strategy.loader``'s injected ``parse`` (wired
    to the real kernel ``tos.dsl.serialization.parse_strategy`` in
    production) does not create a second, divergent authoring surface."""
    mapping = admissible_strategy_mapping()
    path = write_strategy_yaml(strategies_dir, "band.strategy.yaml", mapping)

    loaded = load_strategies(strategies_dir, parse=parse, admit=admit)
    yaml_strategy = loaded.strategies[0].strategy
    assert loaded.strategies[0].path == path

    typed_strategy = in_process_typed_strategy()

    assert yaml_strategy.canonical_digest == typed_strategy.canonical_digest
    assert yaml_strategy.strategy_id == typed_strategy.strategy_id

    yaml_admission = admit(yaml_strategy)
    typed_admission = admit(typed_strategy)
    assert (
        yaml_admission.verdict is typed_admission.verdict is AdmissionVerdict.ADMISSIBLE
    )
    assert yaml_admission.instrument_key == typed_admission.instrument_key


def test_null_leaf_anywhere_refuses_naming_the_field(strategies_dir, parse, admit):
    mapping = admissible_strategy_mapping()
    mapping["policy"]["rules"][0]["decision"]["rationale"] = None
    path = write_strategy_yaml(strategies_dir, "null-leaf.strategy.yaml", mapping)
    with pytest.raises(StrategyLoadError) as excinfo:
        load_strategies(strategies_dir, parse=parse, admit=admit)
    message = str(excinfo.value)
    assert str(path) in message
    assert "rationale" in message


def test_top_level_null_leaf_refuses(strategies_dir, parse, admit):
    mapping = admissible_strategy_mapping(dsl_version=None)
    write_strategy_yaml(strategies_dir, "null-top.strategy.yaml", mapping)
    with pytest.raises(StrategyLoadError, match="dsl_version"):
        load_strategies(strategies_dir, parse=parse, admit=admit)


def test_not_a_mapping_refuses(strategies_dir, parse, admit):
    path = strategies_dir / "list.strategy.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(StrategyLoadError, match="top-level mapping"):
        load_strategies(strategies_dir, parse=parse, admit=admit)


def test_malformed_yaml_refuses(strategies_dir, parse, admit):
    path = strategies_dir / "malformed.strategy.yaml"
    path.write_text("not: valid: yaml: [[[", encoding="utf-8")
    with pytest.raises(StrategyLoadError, match="not valid YAML"):
        load_strategies(strategies_dir, parse=parse, admit=admit)


def test_empty_directory_refuses(strategies_dir, parse, admit):
    with pytest.raises(StrategyLoadError, match="no strategy files"):
        load_strategies(strategies_dir, parse=parse, admit=admit)


def test_missing_directory_refuses(tmp_path: Path, parse, admit):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(StrategyLoadError, match="does not exist"):
        load_strategies(missing, parse=parse, admit=admit)


def test_digest_is_deterministic_across_loads(strategies_dir, parse, admit):
    path = write_strategy_yaml(
        strategies_dir, "band.strategy.yaml", admissible_strategy_mapping()
    )
    first = load_strategies(strategies_dir, parse=parse, admit=admit)
    second = load_strategies(strategies_dir, parse=parse, admit=admit)
    assert first.strategies[0].sha256_digest == second.strategies[0].sha256_digest
    assert (
        first.strategies[0].sha256_digest
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )


def test_one_bad_file_refuses_the_whole_directory_not_a_partial_admit(
    strategies_dir, parse, admit
):
    """A directory with one good file and one bad file must refuse
    entirely — never silently admit the good one and skip the bad one
    (plan §1.2: "이유를 evidence STRATEGY_REFUSED" — the whole load is
    refused, not filtered)."""
    write_strategy_yaml(
        strategies_dir, "a-good.strategy.yaml", admissible_strategy_mapping()
    )
    write_strategy_yaml(
        strategies_dir, "b-bad.strategy.yaml", inadmissible_strategy_mapping()
    )
    with pytest.raises(StrategyLoadError):
        load_strategies(strategies_dir, parse=parse, admit=admit)


def test_example_strategy_yaml_is_refused_as_shipped(parse, admit, tmp_path: Path):
    """``tos/runtime/config/strategies/example.strategy.yaml`` documents the
    shape with every value left as a named-TBD ``null`` — it must be refused
    exactly like any other still-null strategy file, never silently
    admitted."""
    example_path = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "strategies"
        / "example.strategy.yaml"
    )
    assert example_path.is_file()
    directory = tmp_path / "strategies"
    directory.mkdir()
    (directory / "example.strategy.yaml").write_bytes(example_path.read_bytes())
    with pytest.raises(StrategyLoadError, match="null"):
        load_strategies(directory, parse=parse, admit=admit)


def test_null_leaf_on_optional_only_field_refuses(strategies_dir, parse, admit):
    """A null on a field that pydantic types as Optional (e.g.
    ``quantity_basis``) is never caught by type validation or by the
    admission gate's wildcard-scope check — ONLY the loader's own explicit
    null-leaf walk catches it. This is the case that makes the null-leaf
    check load-bearing rather than redundant with downstream validation."""
    mapping = admissible_strategy_mapping()
    mapping["policy"]["rules"][0]["decision"]["target"]["quantity_basis"] = None
    path = write_strategy_yaml(strategies_dir, "optional-null.strategy.yaml", mapping)
    with pytest.raises(StrategyLoadError) as excinfo:
        load_strategies(strategies_dir, parse=parse, admit=admit)
    message = str(excinfo.value)
    assert str(path) in message
    assert "quantity_basis" in message


def test_yml_suffix_is_loaded_like_yaml(strategies_dir, parse, admit):
    """2026-09-09 independent-review finding #12: ``*.yml`` (not just
    ``*.yaml``) is a genuine strategy file, not silently skipped."""
    path = strategies_dir / "band.strategy.yml"
    path.write_text(
        yaml.safe_dump(admissible_strategy_mapping(), sort_keys=False),
        encoding="utf-8",
    )
    loaded = load_strategies(strategies_dir, parse=parse, admit=admit)
    assert [entry.path for entry in loaded.strategies] == [path]


def test_stray_non_strategy_file_refuses_naming_it(strategies_dir, parse, admit):
    """2026-09-09 independent-review finding #12: a stray file that is
    neither ``*.yaml`` nor ``*.yml`` (e.g. a renamed-away bad strategy, an
    editor backup) refuses the WHOLE directory rather than being silently
    ignored by the glob."""
    write_strategy_yaml(
        strategies_dir, "a-good.strategy.yaml", admissible_strategy_mapping()
    )
    stray = strategies_dir / "band.strategy.yaml.bak"
    stray.write_text("not a strategy file", encoding="utf-8")
    with pytest.raises(StrategyLoadError) as excinfo:
        load_strategies(strategies_dir, parse=parse, admit=admit)
    assert str(stray) in str(excinfo.value)


def test_unknown_top_level_key_refuses_naming_the_path(strategies_dir, parse, admit):
    """Runtime-level coverage for 2026-09-09 independent-review finding #17
    mutation M7: ``_StrategyAuthoringContent`` (the kernel's top-level
    parsing model, ``tos.dsl.serialization``) is ``extra='forbid'`` — this
    was kernel-red but runtime-green (the only existing nested-unknown-key
    test exercises a DIFFERENT, nested pydantic model, ``TargetSpec``, not
    the top-level authoring content). An unknown key directly alongside
    ``dsl_version``/``config_binding_version``/``policy`` must refuse here
    too, through the REAL injected ``parse`` (``tos.dsl.serialization.
    parse_strategy``), not just in the kernel's own unit test."""
    mapping = admissible_strategy_mapping()
    mapping["not_a_real_top_level_field"] = "x"
    path = write_strategy_yaml(strategies_dir, "bad-top-level.strategy.yaml", mapping)
    with pytest.raises(StrategyLoadError) as excinfo:
        load_strategies(strategies_dir, parse=parse, admit=admit)
    assert str(path) in str(excinfo.value)


def test_dropping_a_rule_changes_the_loaded_strategy_digest(
    strategies_dir, parse, admit
):
    """Runtime-level coverage for 2026-09-09 independent-review finding #17
    mutation M5 (``lower_strategy`` silently drops the first authored rule —
    kernel-red, runtime-green): the runtime suite had no assertion that a
    strategy's own identity (``canonical_digest``) is sensitive to its rule
    count at all. Two strategy files differing ONLY by one extra rule must
    load to two DIFFERENT digests — if a rule were silently dropped
    somewhere on this path, the two artifacts could otherwise collide."""
    one_rule = admissible_strategy_mapping()
    two_rules = admissible_strategy_mapping()
    two_rules["policy"]["rules"] = list(two_rules["policy"]["rules"]) + [
        {
            "all_of": [
                {
                    "left": {"ref": ["capsule", "resolved_values", "close"]},
                    "op": "GT",
                    "right": {"ref": ["capsule", "resolved_values", "upper_band"]},
                }
            ],
            "decision": {
                "kind": "NO_ACTION",
                "rationale": "second rule — exists only to change the digest",
            },
        }
    ]
    write_strategy_yaml(strategies_dir, "one-rule.strategy.yaml", one_rule)
    loaded_one = load_strategies(strategies_dir, parse=parse, admit=admit)

    two_rules_dir = strategies_dir.parent / "strategies-two-rules"
    two_rules_dir.mkdir()
    write_strategy_yaml(two_rules_dir, "two-rule.strategy.yaml", two_rules)
    loaded_two = load_strategies(two_rules_dir, parse=parse, admit=admit)

    assert (
        loaded_one.strategies[0].strategy.canonical_digest
        != loaded_two.strategies[0].strategy.canonical_digest
    )
