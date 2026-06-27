# Import all facet modules so their register_facet() calls populate FACET_REGISTRY
# when this package is imported.  Add new facets here.
from shared.llm_scorecard.facets import (
    direction,  # noqa: F401
    movers,  # noqa: F401
    themes,  # noqa: F401
    volume_surge,  # noqa: F401
)
