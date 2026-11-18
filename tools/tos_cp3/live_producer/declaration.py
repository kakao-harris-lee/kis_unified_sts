"""The tenant's DECLARATION: what computes this session's published fields."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.indicators.fields import (  # noqa: E402
    FieldError,
    FieldsDocument,
    parse_fields_document,
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


def load_declaration(
    tenant_tree: Path, *, strategy: StrategyInputs, anchor: OpenAnchor
) -> tuple[FieldsDocument, dict[str, Any]]:
    """Load and bind the tenant's ``fields.yaml``, or refuse to start."""
    fields_yaml = fields_yaml_of(tenant_tree)
    try:
        # ONE read (#1101 re-review LOW 1): the lineage digest below is of the
        # SAME bytes this parse validated, so the two cannot describe different
        # files. `load_fields_file` is the path-taking twin of these two lines
        # and the validation itself — `parse_fields_document` — is shared with
        # it, so no refusal is restated here; only the YAML error it would have
        # dressed up is folded into the one refusal this function raises.
        raw_bytes = fields_yaml.read_bytes()
        document = parse_fields_document(yaml.safe_load(raw_bytes.decode("utf-8")))
        assert_dsl_refs_are_published(
            document, strategies_dir=tenant_tree / "strategies"
        )
        assert_publish_matches_critical_inputs(
            document, policy_path=tenant_tree / "critical_input_policy.yaml"
        )
        assert_declaration_binds_to_the_run(document, strategy=strategy, anchor=anchor)
    except (FieldError, ProduceFieldsError, OSError, yaml.YAMLError) as exc:
        raise LiveProducerRefused(
            f"{fields_yaml}: the tenant declaration is not usable for this "
            f"session — {exc}"
        ) from exc
    except (KeyError, TypeError, ValueError) as exc:
        # #1068 review LOW 1. The checks above read values by key and coerce
        # them (`params["open_hour"]`, `int(config.vol_window_bars)`,
        # `float(config.vol_percentile)`), so a missing key or a value that is
        # not the expected type ends them with a raw lookup/coercion error.
        # Fail-closed either way, but a traceback is not the one exception the
        # runner reads as "the producer did not start" — so it refuses here
        # like every other declaration fault. It names BOTH files on purpose
        # (#1101 re-review LOW 2): the compared values come from the
        # declaration AND from the strategy YAML it is sized against, and this
        # clause cannot tell which side was unreadable.
        raise LiveProducerRefused(
            f"{fields_yaml}: the tenant declaration is not usable for this "
            f"session — binding it ended in a raw lookup/coercion error "
            f"({type(exc).__name__}: {exc}). The bind compares this file's "
            f"declared params with the strategy YAML it is sized against "
            f"({strategy.path}), so either side can be the one at fault"
        ) from exc
    record = {
        "stage": "declaration",
        "fields_yaml": str(fields_yaml),
        "fields_yaml_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "schema": document.schema,
        "catalog": document.catalog,
        "published": [entry.name for entry in document.publish],
    }
    return document, record
