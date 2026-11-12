"""The tenant's DECLARATION: what computes this session's published fields.

Since P2-c (plan ``docs/plans/2026-11-11-tos-p2-declarative-fields.md`` §3) the
live producer does not drive the legacy Setup D; it evaluates the tenant tree's
``fields.yaml``. Loading that document, refusing the ones this session must not
publish from, and the digest the lineage records are one concern, and they are
answered ONCE at boot — so they live here rather than in the loop
(:mod:`~tools.tos_cp3.live_producer.producer`), the same file split plan §3.5
made for :mod:`~tools.tos_cp3.live_producer.line` and
:mod:`~tools.tos_cp3.live_producer.halt_policy`.

Everything here is pure: a path in, a document and a log record out. The three
refusals it raises are the producer's own
(:mod:`~tools.tos_cp3.produce_fields`); this module only makes sure each of
them reaches the runner as the one exception it reads as "the producer did not
start".
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.indicators.fields import (  # noqa: E402
    FieldError,
    FieldsDocument,
    load_fields_file,
)
from tools.tos_cp3.live_producer.config import LiveProducerRefused  # noqa: E402
from tools.tos_cp3.produce_fields import (  # noqa: E402
    OpenAnchor,
    ProduceFieldsError,
    StrategyInputs,
    assert_declaration_binds_to_the_run,
    assert_dsl_refs_are_published,
    assert_publish_matches_critical_inputs,
)


def fields_yaml_of(tenant_tree: Path) -> Path:
    """The declaration a tenant tree publishes from."""
    return tenant_tree / "fields.yaml"


def fields_yaml_digest(fields_yaml: Path) -> str:
    """Digest of the declaration's BYTES, as the lineage records it."""
    return hashlib.sha256(fields_yaml.read_bytes()).hexdigest()


def load_declaration(
    tenant_tree: Path, *, strategy: StrategyInputs, anchor: OpenAnchor
) -> tuple[FieldsDocument, dict[str, Any]]:
    """Load and bind the tenant's ``fields.yaml``, or refuse to start.

    Three refusals, all asked here because at boot each is free and later each
    is three layers away:

    * the document does not load (:func:`load_fields_file`);
    * the strategy DSL reads a resolved value the declaration does not publish,
      or the publish set is not the one the tenant's
      ``critical_input_policy.yaml`` declares — either way the kernel refuses
      the WHOLE poll on a journal key, every minute from the open;
    * the declaration is bound to another session's open or to a vol window the
      seed was not built for (:func:`assert_declaration_binds_to_the_run`).

    Every one of them becomes a :class:`LiveProducerRefused`, because that is
    the one exception ``producer.main`` turns into "the producer did not
    start". A ``FieldSpecError`` or a ``ProduceFieldsError`` escaping here
    would leave the runner reading a traceback instead of a reason.

    Args:
        tenant_tree: the rendered tenant tree this session serves.
        strategy: the strategy YAML the seed is sized from.
        anchor: the open anchor the runtime resolved for this session.

    Returns:
        The parsed document, and the ``declaration`` log record naming what
        this session publishes from.

    Raises:
        LiveProducerRefused: on any of the three.
    """
    fields_yaml = fields_yaml_of(tenant_tree)
    try:
        document = load_fields_file(fields_yaml)
        assert_dsl_refs_are_published(
            document, strategies_dir=tenant_tree / "strategies"
        )
        assert_publish_matches_critical_inputs(
            document, policy_path=tenant_tree / "critical_input_policy.yaml"
        )
        assert_declaration_binds_to_the_run(document, strategy=strategy, anchor=anchor)
    except (FieldError, ProduceFieldsError, OSError) as exc:
        raise LiveProducerRefused(
            f"{fields_yaml}: the tenant declaration is not usable for this "
            f"session — {exc}"
        ) from exc
    record = {
        "stage": "declaration",
        "fields_yaml": str(fields_yaml),
        "fields_yaml_sha256": fields_yaml_digest(fields_yaml),
        "schema": document.schema,
        "catalog": document.catalog,
        "published": [entry.name for entry in document.publish],
    }
    return document, record
