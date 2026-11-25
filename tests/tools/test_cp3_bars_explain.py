"""``tools/tos_cp3/bars_explain.py`` — 규칙 문장과 필드 정의를 바 문서에 싣는다.

두 가지를 본다. 하나는 **저장소의 진짜 tenant 콘텐츠**로 — 규칙 id 도출이 커널의
것과 같은지, 프로브 표가 실제 tenant 의 프로브 규칙을 빠짐없이 담는지. 다른 하나는
손으로 쓴 작은 전략·필드 문서로 — 사슬 추적과 거부 경계.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.tos_cp3 import bars_explain as be

REPO_ROOT = Path(__file__).resolve().parents[2]
TENANT_ROOT = REPO_ROOT / "config" / "tos_runtime"

#: 저장소가 실제로 들고 있는 tenant 전략 파일 전부.
TENANT_STRATEGIES = sorted(TENANT_ROOT.glob("cp3-setup-d-*/strategies/*.yaml"))


def _rule_ids(strategy: dict[str, Any]) -> list[str]:
    ids = []
    for rule in (strategy.get("policy") or {}).get("rules") or []:
        rationale = (rule.get("decision") or {}).get("rationale")
        rule_id = be.rule_id_of(rationale)
        if rule_id:
            ids.append(rule_id)
    return ids


def test_the_repo_actually_has_tenant_strategies_to_check() -> None:
    """아래 두 검사가 빈 목록 위에서 공허하게 통과하지 않게."""
    assert len(TENANT_STRATEGIES) >= 5, [p.name for p in TENANT_STRATEGIES]


def test_the_rule_id_is_the_token_before_the_colon() -> None:
    """커널의 ``cp3/strategy.py::_rule_id`` 와 **같은** 도출이어야 한다.

    두 쪽이 어긋나면 설명이 엉뚱한 규칙에 붙는다. 저쪽을 import 할 수 없으므로
    (레거시 측이고 커널은 별 프로세스다) 규약을 여기서 못 박는다.
    """
    assert be.rule_id_of("R1-ENTRY-LONG: entry window open, …") == "R1-ENTRY-LONG"
    assert be.rule_id_of("  R3-EXIT-EOD : trailing space  ") == "R3-EXIT-EOD"
    assert be.rule_id_of("no colon here") == "no colon here"
    assert be.rule_id_of(": empty head") is None
    assert be.rule_id_of(None) is None


def test_every_probe_rule_in_the_repo_is_declared_in_the_map() -> None:
    """tenant 에 프로브 규칙을 넣고 표에 적지 않으면 화면이 그것을 신호로 그린다.

    프로브 규칙은 자기 id 에 ``PROBE`` 를 달고 있다(``R4-M2-PROBE-ENTRY-LONG``).
    새 프로브를 넣고 ``config/tos_bars_explain.yaml`` 을 잊으면 여기서 빨개진다 —
    런타임 가드가 아니라 테스트다(CLAUDE.md R5: 새 검사기는 실제 사고가 있어야
    한다. 이것은 검사기가 아니라 저장소 사실의 대조다).
    """
    declared = be.load_probe_rule_ids()
    found: set[str] = set()
    for path in TENANT_STRATEGIES:
        strategy = yaml.safe_load(path.read_text(encoding="utf-8"))
        found |= {rid for rid in _rule_ids(strategy) if "PROBE" in rid.upper()}
    assert found, "저장소에 프로브 규칙이 하나도 없다 — 이 검사는 공허하다"
    assert found <= declared, sorted(found - declared)


def test_the_map_declares_nothing_that_no_tenant_has() -> None:
    """죽은 등록은 다음 읽는 사람을 속인다 — 표는 지금 있는 규칙만 담는다."""
    declared = be.load_probe_rule_ids()
    everything: set[str] = set()
    for path in TENANT_STRATEGIES:
        strategy = yaml.safe_load(path.read_text(encoding="utf-8"))
        everything |= set(_rule_ids(strategy))
    assert declared <= everything, sorted(declared - everything)


# --------------------------------------------------------------------------- #
# 손으로 쓴 전략·필드 — 사슬 추적과 거부 경계
# --------------------------------------------------------------------------- #

STRATEGY: dict[str, Any] = {
    "policy": {
        "rules": [
            {
                "all_of": [
                    {
                        "left": {"ref": ["capsule", "resolved_values", "entry_window"]},
                        "op": "EQ",
                        "right": {"const": True},
                    },
                    {
                        "left": {"ref": ["capsule", "resolved_values", "z_x1000"]},
                        "op": "LE",
                        "right": {"ref": ["config", "z_entry_max_x1000"]},
                    },
                ],
                "decision": {
                    "kind": "ACTION",
                    "rationale": "R1-ENTRY-LONG: 진입 조건이 모두 섰다.",
                    "target": {"rationale": "R1-ENTRY-LONG: 롱 하나를 연다."},
                },
            },
            {
                "all_of": [
                    {
                        "left": {"ref": ["capsule", "resolved_values", "entry_window"]},
                        "op": "EQ",
                        "right": {"const": True},
                    }
                ],
                "decision": {
                    "kind": "ACTION",
                    "rationale": "R4-M2-PROBE-ENTRY-LONG: 경계 프로브다.",
                },
            },
        ],
        "default": {
            "kind": "NO_ACTION",
            "rationale": "R0-DEFAULT-NO-ACTION: 아무 규칙도 서지 않았다.",
        },
    }
}

FIELDS: dict[str, Any] = {
    "fields": [
        {"name": "close", "op": "bar.close"},
        {"name": "vwap", "op": "session.vwap_typical"},
        {"name": "atr", "op": "atr", "params": {"period": 14}},
        {"name": "mso", "op": "session.minutes_since_open"},
        {
            "name": "entry_window",
            "op": "between",
            "inputs": ["mso"],
            "params": {"lo": 15, "hi": 345},
        },
        {"name": "usable", "op": "all", "inputs": ["entry_window"]},
        {
            "name": "vol_ref",
            "op": "gated_percentile",
            "inputs": ["atr"],
            "params": {"q": 90.0, "sample_when": "usable"},
        },
        {"name": "z", "op": "ratio_z", "inputs": ["close", "vwap", "atr"]},
    ],
    "publish": [
        {"field": "close", "as": "close_x100", "scale": {"mult": 100}},
        {"field": "z", "as": "z_x1000", "scale": {"mult": 1000}},
        {"field": "entry_window", "as": "entry_window"},
    ],
}

PROBES = frozenset({"R4-M2-PROBE-ENTRY-LONG"})


def test_each_rule_carries_its_own_sentence_and_what_it_reads() -> None:
    explain = be.build_explain(STRATEGY, FIELDS, probe_rule_ids=PROBES)
    first, second = explain["rules"]
    assert first["label"] == "R1"
    assert first["rule_id"] == "R1-ENTRY-LONG"
    assert first["decision_kind"] == "ACTION"
    assert first["rationale"].startswith("R1-ENTRY-LONG:")
    assert first["target_rationale"].endswith("롱 하나를 연다.")
    assert first["fields"] == ["entry_window", "z_x1000"]
    assert first["bindings"] == ["z_entry_max_x1000"]
    assert second["label"] == "R2"
    assert explain["default"]["rule_id"] == "R0-DEFAULT-NO-ACTION"
    assert explain["schema"] == be.EXPLAIN_SCHEMA


def test_only_the_declared_rule_is_marked_a_probe() -> None:
    """프로브를 신호와 섞어 그리면 전략 성적이 거짓이 된다."""
    explain = be.build_explain(STRATEGY, FIELDS, probe_rule_ids=PROBES)
    assert [rule["probe"] for rule in explain["rules"]] == [False, True]
    assert explain["probe_basis"] == "OPERATOR_RULE_MAP"


def test_a_published_name_resolves_to_its_catalog_definition_and_scale() -> None:
    """규칙은 ``z_x1000`` 을 가리키는데 카탈로그는 ``z`` 로 안다 — publish 가 잇는다."""
    fields = be.build_explain(STRATEGY, FIELDS, probe_rule_ids=PROBES)["fields"]
    assert fields["z_x1000"]["field"] == "z"
    assert fields["z_x1000"]["op"] == "ratio_z"
    assert fields["z_x1000"]["scale"] == {"mult": 1000}
    assert fields["z_x1000"]["inputs"] == ["close", "vwap", "atr"]


def test_the_chain_is_followed_all_the_way_down() -> None:
    """«반전 확인이 참» 만으로는 왜 그런지 말할 수 없다 — 딛고 선 필드까지 싣는다."""
    fields = be.build_explain(STRATEGY, FIELDS, probe_rule_ids=PROBES)["fields"]
    # z_x1000 → z → close·vwap·atr, entry_window → mso.
    for name in ("z_x1000", "close", "vwap", "atr", "entry_window", "mso"):
        assert name in fields, name
    assert fields["atr"]["params"] == {"period": 14}


def test_a_sample_when_parameter_is_a_field_reference_too() -> None:
    """게이트된 통계가 어느 봉을 표본으로 삼는지 — 빠뜨리면 사슬이 거기서 끊긴다."""
    fields = be.build_explain(
        {
            "policy": {
                "rules": [
                    {
                        "all_of": [
                            {
                                "left": {
                                    "ref": ["capsule", "resolved_values", "vol_ref"]
                                },
                                "op": "GT",
                                "right": {"const": 0},
                            }
                        ],
                        "decision": {"kind": "ACTION", "rationale": "RX: x"},
                    }
                ],
                "default": {"kind": "NO_ACTION", "rationale": "R0: y"},
            }
        },
        FIELDS,
        probe_rule_ids=frozenset(),
    )["fields"]
    assert "usable" in fields
    assert "entry_window" in fields


def test_a_name_the_catalog_does_not_define_says_so_instead_of_inventing() -> None:
    fields = be.build_explain(
        {
            "policy": {
                "rules": [
                    {
                        "all_of": [
                            {
                                "left": {
                                    "ref": ["capsule", "resolved_values", "ghost"]
                                },
                                "op": "EQ",
                                "right": {"const": True},
                            }
                        ],
                        "decision": {"kind": "ACTION", "rationale": "RX: x"},
                    }
                ],
                "default": {"kind": "NO_ACTION", "rationale": "R0: y"},
            }
        },
        FIELDS,
        probe_rule_ids=frozenset(),
    )["fields"]
    assert fields["ghost"] == {"field": "ghost", "op": None, "known": False}


def test_the_explain_block_carries_no_path(tmp_path: Path) -> None:
    """이 블록은 브라우저로 간다 — 읽은 파일의 경로가 어느 키에도 없어야 한다."""
    import json

    rendered = json.dumps(
        be.build_explain(STRATEGY, FIELDS, probe_rule_ids=PROBES), ensure_ascii=False
    )
    assert "/" not in rendered.replace("tos-bars-explain/1", "")


def test_an_unreadable_probe_map_is_a_refusal_not_an_empty_set(
    tmp_path: Path,
) -> None:
    """표를 못 읽은 것과 «프로브가 하나도 없다» 는 다른 사실이다.

    빈 집합으로 떨어지면 프로브 규칙이 조용히 신호로 그려진다.
    """
    broken = tmp_path / "probe.yaml"
    broken.write_text("probe_rule_ids: not-a-list\n", encoding="utf-8")
    with pytest.raises(be.ExplainRefusal):
        be.load_probe_rule_ids(broken)

    with pytest.raises(be.ExplainRefusal):
        be.load_probe_rule_ids(tmp_path / "missing.yaml")


def test_the_shipped_probe_map_loads() -> None:
    """내보내기가 매일 아침 읽는 그 파일이 실제로 읽히는지."""
    assert be.load_probe_rule_ids() == {"R4-M2-PROBE-ENTRY-LONG"}
