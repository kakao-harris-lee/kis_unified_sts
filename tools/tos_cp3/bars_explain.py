#!/usr/bin/env python3
"""규칙이 무엇을 말하는 규칙인지를 바 문서에 함께 싣는다 — 식별자 대신 문장으로.

계획 ``docs/plans/2026-11-25-tos-operator-page-legibility-plan.md`` §4 ③: 지금
화면은 규칙을 ``R1-ENTRY-LONG`` 같은 식별자로, 조건을 ``z_x1000 LE
config.z_entry_max_x1000`` 같은 식으로 보여 준다. 두 문장 모두 이미 설정에 있다 —
전략 YAML 의 ``rationale`` 과 ``fields.yaml`` 의 필드 정의다. 내보내기가 그 둘을
바 문서에 옮겨 적으면 화면이 쉬운 말로 그릴 수 있다.

**세션이 실제로 쓴 트리를 읽는다.** 저장소의 현재 tenant 설정이 아니라 그 세션
디렉터리 안에 렌더된 사본(``inspect_session.resolve_session`` 이 고르는 그것)을
읽는다. 규칙이 바뀐 뒤 지난 세션을 열면 그날 돌지 않은 설명이 붙는다.

**프로브 표시는 tenant 콘텐츠를 건드리지 않는다.** ``config/tos_bars_explain.yaml``
이 그 표를 들고 있고, 왜 거기인지는 그 파일의 머리말이 적는다 — 요약하면 전략 DSL
모델이 ``extra="forbid"`` 이고 전략의 canonical digest 가 증거에 적히는 재연 입력
이라, 전략 YAML 에 키를 하나 더하는 것은 적재 거부 아니면 영구 재연 어긋남이다.

**경로는 싣지 않는다.** 이 블록은 ``export_bars`` 가 쓰는 문서에 들어가고, 그
문서는 대시보드가 그대로 브라우저에 보낸다. 읽은 파일의 경로는 어느 키에도 없다.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import inspect_session, status_board  # noqa: E402

__all__ = [
    "EXPLAIN_SCHEMA",
    "FIELDS_FILE_NAME",
    "PROBE_CONFIG_PATH",
    "ExplainRefusal",
    "TenantContent",
    "build_explain",
    "load_probe_rule_ids",
    "read_tenant_content",
    "rule_id_of",
]

#: 이 블록의 판 이름. 바 문서 자신의 ``schema_version`` 과 별개로, 블록 하나가
#: 바뀐 것을 읽는 쪽이 알 수 있게 블록 안에 적는다.
EXPLAIN_SCHEMA = "tos-bars-explain/1"

FIELDS_FILE_NAME = "fields.yaml"
RENDER_MANIFEST_NAME = "RENDER.yaml"

#: 프로브 표를 담은 설정. tenant 콘텐츠가 아니라 운영자 측 파일이다.
PROBE_CONFIG_PATH = REPO_ROOT / "config" / "tos_bars_explain.yaml"

#: 규칙이 필드를 가리키는 모양 — ``[capsule, resolved_values, <발행 이름>]``.
#: 커널의 DSL 어휘이고, 이 모듈은 그것을 import 하지 못하므로(방화벽 TOS-FW-R)
#: 여기 다시 적는다. ``export_bars`` 가 ``tos_bars`` route 와 만나는 방식과 같다.
_CAPSULE_REF_HEAD = ("capsule", "resolved_values")

#: 설정 바인딩을 가리키는 모양 — ``[config, <키>]``. 그 값은 바 문서의
#: ``bindings.values`` 에 이미 있으므로 여기서는 이름만 모은다.
_CONFIG_REF_HEAD = "config"

#: 필드 하나가 다른 필드를 가리키는 자리. ``inputs`` 말고 ``params.sample_when``
#: 도 필드 이름이다(게이트된 통계가 어느 봉을 표본으로 삼는지) — 빠뜨리면 설명
#: 사슬이 거기서 끊긴다.
_PARAM_FIELD_KEYS = ("sample_when",)


class ExplainRefusal(Exception):
    """설명을 붙이지 못한 사유 — 바 문서 자체는 그래도 나간다."""


def rule_id_of(rationale: str | None) -> str | None:
    """규칙 id = ``rationale`` 의 콜론 앞 토큰.

    ``tos/runtime/cp3/strategy.py::_rule_id`` 와 **같은** 도출이다. 그 모듈을
    import 할 수 없으므로(이쪽은 레거시 측이고 커널은 별 프로세스다) 다시 적고,
    두 쪽이 어긋나면 설명이 엉뚱한 규칙에 붙는다 — 테스트가 실제 바 문서의
    ``rules[].rule_id`` 와 대조해 그것을 잡는다.
    """
    if rationale is None:
        return None
    head, _, _ = rationale.partition(":")
    head = head.strip()
    return head or None


def _load_yaml(path: Path, *, what: str) -> Any:
    import yaml

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ExplainRefusal(f"{what}: {type(exc).__name__}") from exc


def load_probe_rule_ids(path: Path = PROBE_CONFIG_PATH) -> frozenset[str]:
    """«이 규칙은 주문 경로 시험이다» 로 선언된 규칙 id 들."""
    raw = _load_yaml(path, what="프로브 표를 읽지 못했다")
    if not isinstance(raw, dict):
        raise ExplainRefusal("프로브 표의 최상위가 매핑이 아니다")
    declared = raw.get("probe_rule_ids") or []
    if not isinstance(declared, list):
        raise ExplainRefusal("'probe_rule_ids' 가 목록이 아니다")
    return frozenset(str(item) for item in declared if isinstance(item, str) and item)


def _catalog(fields_doc: Any) -> dict[str, dict[str, Any]]:
    """``fields.yaml`` 의 카탈로그 — 내부 이름 → 정의."""
    entries = (fields_doc or {}).get("fields") or []
    catalog: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            catalog[entry["name"]] = entry
    return catalog


def _published(fields_doc: Any) -> dict[str, dict[str, Any]]:
    """``publish:`` 블록 — 발행 이름 → ``{field, scale}``.

    규칙이 가리키는 것도, 바마다 값이 실리는 것도 **발행 이름**이다. 내부 이름과
    같은 필드가 많지만(``entry_window``) 다른 것도 있어서(``z`` → ``z_x1000``)
    이 표가 없으면 ``z_x1000`` 의 정의를 찾지 못한다.
    """
    entries = (fields_doc or {}).get("publish") or []
    published: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        field, alias = entry.get("field"), entry.get("as")
        if isinstance(field, str) and isinstance(alias, str):
            published[alias] = {"field": field, "scale": entry.get("scale")}
    return published


def _refs(operand: Any) -> tuple[list[str], list[str]]:
    """한 피연산자가 가리키는 ``(필드 발행 이름, 설정 키)``."""
    ref = operand.get("ref") if isinstance(operand, dict) else None
    if not isinstance(ref, list) or not ref:
        return [], []
    parts = [str(part) for part in ref]
    if tuple(parts[:2]) == _CAPSULE_REF_HEAD and len(parts) > 2:
        return [parts[2]], []
    if parts[0] == _CONFIG_REF_HEAD and len(parts) > 1:
        return [], [parts[1]]
    return [], []


def _closure(
    seeds: Iterable[str],
    *,
    catalog: Mapping[str, dict[str, Any]],
    published: Mapping[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """``seeds`` 가 가리키는 필드와 **그것이 딛고 선 필드 전부**의 정의.

    사슬을 끝까지 따라가는 이유: ``reversal_ok`` 만 내면 화면은 «반전 확인» 이
    참이었다는 것밖에 말하지 못한다. 무엇을 보고 그렇게 판정했는지는 그 입력들
    (``improve_ok`` → ``z_improvement`` → ``abs_prev_z``…)에 있다.
    """
    alias_of = {spec["field"]: name for name, spec in published.items()}
    out: dict[str, dict[str, Any]] = {}
    pending = list(seeds)
    while pending:
        name = pending.pop()
        if name in out:
            continue
        spec = published.get(name)
        internal = spec["field"] if spec is not None else name
        entry = catalog.get(internal)
        if entry is None:
            # 카탈로그가 모르는 이름 — 지어내지 않고 그 사실만 적는다.
            out[name] = {"field": internal, "op": None, "known": False}
            continue
        params = entry.get("params")
        inputs = [str(item) for item in entry.get("inputs") or []]
        out[name] = {
            "field": internal,
            "op": entry.get("op"),
            "inputs": inputs,
            "params": params if isinstance(params, dict) else None,
            "scale": None if spec is None else spec.get("scale"),
            "published_as": alias_of.get(internal),
            "known": True,
        }
        pending.extend(inputs)
        if isinstance(params, dict):
            pending.extend(
                str(params[key]) for key in _PARAM_FIELD_KEYS if key in params
            )
    return out


def _rule_block(
    rule: Any, *, position: int, probe_rule_ids: frozenset[str]
) -> dict[str, Any]:
    """한 규칙의 설명 — 식별자 · 문장 · 가리키는 필드 · 프로브 여부."""
    decision = rule.get("decision") if isinstance(rule, dict) else None
    decision = decision if isinstance(decision, dict) else {}
    rationale = decision.get("rationale")
    rule_id = rule_id_of(rationale if isinstance(rationale, str) else None)
    fields: list[str] = []
    bindings: list[str] = []
    for compare in rule.get("all_of") or []:
        if not isinstance(compare, dict):
            continue
        for side in ("left", "right"):
            found, keys = _refs(compare.get(side))
            fields.extend(found)
            bindings.extend(keys)
    target = decision.get("target")
    target_rationale = target.get("rationale") if isinstance(target, dict) else None
    return {
        # 화면이 쓰는 두 이름. `label` 은 점검 보고서의 `R<n>` 과 같은 순번이다.
        "label": f"R{position}",
        "rule_id": rule_id,
        "decision_kind": decision.get("kind"),
        "rationale": rationale if isinstance(rationale, str) else None,
        "target_rationale": (
            target_rationale if isinstance(target_rationale, str) else None
        ),
        # SAFETY: 프로브를 신호와 섞어 그리면 전략 성적이 거짓이 된다 — R4 는 주문 경로 시험이지 Setup D 진입이 아니다
        "probe": rule_id is not None and rule_id in probe_rule_ids,
        "fields": list(dict.fromkeys(fields)),
        "bindings": list(dict.fromkeys(bindings)),
    }


@dataclass(frozen=True)
class TenantContent:
    """한 세션이 **실제로 쓴** tenant 콘텐츠와, 그것이 어느 시장·방향이었나.

    ``render_dir`` 은 호스트 경로다. 이 안에 머물고 내보내는 문서에는 어느 키로도
    실리지 않는다 — 같은 디렉터리의 다른 설정(가격 필드 키)을 더 읽어야 해서
    들고 있을 뿐이다.
    """

    strategy: dict[str, Any]
    fields_doc: dict[str, Any]
    market: str | None
    direction: str | None
    render_dir: Path


def read_tenant_content(
    session: str,
    *,
    config_path: Path = status_board.DEFAULT_CONFIG_PATH,
    state_dir: str | None = None,
) -> TenantContent:
    """그 세션이 **실제로 쓴** 렌더 사본에서 전략 · 필드 · 시장 · 방향을.

    ``with_evidence=False``: 설명은 증거를 읽지 않는다. 잎을 열지 않으므로 잎이
    옮겨지거나 지워진 날에도 지난 세션의 규칙 설명은 그대로 나온다.
    """
    config = status_board.load_config(config_path)
    root = (
        status_board.expand_path(state_dir)
        if state_dir is not None
        else config.state_dir
    )
    try:
        paths = inspect_session.resolve_session(
            session,
            state_dir=root,
            sessions_subdir=config.tenant_sessions_subdir,
            with_evidence=False,
        )
    except (inspect_session.InspectRefusal, ValueError, OSError) as exc:
        raise ExplainRefusal(f"세션을 찾지 못했다: {type(exc).__name__}") from exc

    render_dir = paths.strategy_path.parent.parent
    strategy = _load_yaml(paths.strategy_path, what="전략 YAML 을 읽지 못했다")
    fields_doc = _load_yaml(
        render_dir / FIELDS_FILE_NAME, what="fields.yaml 을 읽지 못했다"
    )
    manifest = _load_yaml(
        render_dir / RENDER_MANIFEST_NAME, what="렌더 매니페스트를 읽지 못했다"
    )
    if not isinstance(strategy, dict) or not isinstance(fields_doc, dict):
        raise ExplainRefusal("전략 또는 필드 문서의 최상위가 매핑이 아니다")
    manifest = manifest if isinstance(manifest, dict) else {}
    market = manifest.get("market")
    declared = manifest.get("direction")
    value = declared.get("value") if isinstance(declared, dict) else None
    return TenantContent(
        strategy=strategy,
        fields_doc=fields_doc,
        market=market if isinstance(market, str) and market else None,
        direction=(str(value).upper() if isinstance(value, str) and value else None),
        render_dir=render_dir,
    )


def build_explain(
    strategy: Mapping[str, Any],
    fields_doc: Mapping[str, Any],
    *,
    probe_rule_ids: frozenset[str],
) -> dict[str, Any]:
    """규칙 설명 블록. 순수 함수 — 디스크를 보지 않는다."""
    policy = strategy.get("policy")
    policy = policy if isinstance(policy, dict) else {}
    rules: Sequence[Any] = policy.get("rules") or []
    blocks = [
        _rule_block(rule, position=position, probe_rule_ids=probe_rule_ids)
        for position, rule in enumerate(rules, start=1)
    ]
    default = policy.get("default")
    default = default if isinstance(default, dict) else {}
    default_rationale = default.get("rationale")
    seeds = [name for block in blocks for name in block["fields"]]
    return {
        "schema": EXPLAIN_SCHEMA,
        "rules": blocks,
        "default": {
            "rule_id": rule_id_of(
                default_rationale if isinstance(default_rationale, str) else None
            ),
            "decision_kind": default.get("kind"),
            "rationale": (
                default_rationale if isinstance(default_rationale, str) else None
            ),
        },
        "fields": _closure(
            seeds, catalog=_catalog(fields_doc), published=_published(fields_doc)
        ),
        # 프로브 표시가 어디서 왔는지 — tenant 콘텐츠가 아니라는 사실 자체가
        # 화면이 아니라 리뷰어를 향한 정보라, 경로가 아니라 토큰으로 적는다.
        "probe_basis": "OPERATOR_RULE_MAP",
    }
