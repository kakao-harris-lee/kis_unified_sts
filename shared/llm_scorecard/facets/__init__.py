# Import all facet modules so their register_facet() calls populate FACET_REGISTRY
# when this package is imported.  Add new facets here.
from shared.llm_scorecard.facets import direction  # noqa: F401
from shared.llm_scorecard.facets import movers  # noqa: F401
from shared.llm_scorecard.facets import themes  # noqa: F401
