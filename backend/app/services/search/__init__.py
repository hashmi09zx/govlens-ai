import os
from app.services.search.base import SearchProvider
from app.services.search.duckduckgo_provider import DuckDuckGoSearchProvider
from app.services.search.official import OfficialSourceSearch
from app.services.search.general import GeneralWebSearch


def get_search_provider() -> SearchProvider:
    provider_type = os.getenv("SEARCH_PROVIDER", "duckduckgo").lower()
    if provider_type == "duckduckgo":
        return DuckDuckGoSearchProvider()
    # Default fallback
    return DuckDuckGoSearchProvider()
