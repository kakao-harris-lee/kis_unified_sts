"""tos.marketfeed — market data → admitted Critical Input value surface (design #32, D-E2)."""

from __future__ import annotations

from tos.marketfeed._base import (
    FETCH_SURFACE_TOKENS,
    CanonicalizationScheme,
    FrozenModel,
    MarketFeedIntegrityError,
    fetch_surface_offenders,
    get_scheme,
    seal_fetch_surface,
)
from tos.marketfeed.records import (
    AdmittedValue,
    PreimageEntry,
    RawPayloadPreimage,
    RejectedValue,
    ValueResolution,
)
from tos.marketfeed.resolver import (
    MarketFeedContextResolver,
    ResolvedTick,
    SnapshotStore,
    TimeCoordinateProjection,
    ValueCandidateSource,
)
from tos.marketfeed.value import (
    capsule_top_level_keys,
    context_value_view_digest,
    index_observations,
    lineage_state_for_output,
    project_scalar,
    publish_context_value_view,
    snapshot_binds_capsule_reference,
    value_field_state,
    value_namespace_is_disjoint,
    view_digest_matches,
)
from tos.marketfeed.vocabulary import (
    ADMITTING_DISPOSITIONS,
    ValueRejectionReason,
    ValueViewDisposition,
)

__all__ = [
    "FETCH_SURFACE_TOKENS",
    "CanonicalizationScheme",
    "FrozenModel",
    "MarketFeedIntegrityError",
    "fetch_surface_offenders",
    "get_scheme",
    "seal_fetch_surface",
    "ADMITTING_DISPOSITIONS",
    "ValueRejectionReason",
    "ValueViewDisposition",
    "AdmittedValue",
    "PreimageEntry",
    "RawPayloadPreimage",
    "RejectedValue",
    "ValueResolution",
    "capsule_top_level_keys",
    "context_value_view_digest",
    "index_observations",
    "lineage_state_for_output",
    "project_scalar",
    "publish_context_value_view",
    "snapshot_binds_capsule_reference",
    "value_field_state",
    "value_namespace_is_disjoint",
    "view_digest_matches",
    "MarketFeedContextResolver",
    "ResolvedTick",
    "SnapshotStore",
    "TimeCoordinateProjection",
    "ValueCandidateSource",
]
