"""The tenant's DECLARATION: what computes this session's published fields."""

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
    """Load and bind the tenant's ``fields.yaml``, or refuse to start."""
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
    except (KeyError, TypeError, ValueError) as exc:
        # #1068 review LOW 1. The bind reads declared params by key and coerces
        # them (`params["open_hour"]`, `int(...)`, the vol_ref window/warmup/q),
        # so a declaration that omits one or spells it as a non-number ends the
        # bind with a raw lookup/coercion error. Fail-closed either way, but a
        # traceback is not the one exception the runner reads as "the producer
        # did not start" — so it refuses here like every other declaration
        # fault, naming the file and the key.
        raise LiveProducerRefused(
            f"{fields_yaml}: the tenant declaration is not usable for this "
            f"session — a declared field's params are missing or not the "
            f"expected type ({type(exc).__name__}: {exc})"
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
