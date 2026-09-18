from typing import List
from app.services.search.base import SearchProvider
from app.services.search.duckduckgo_provider import DuckDuckGoSearchProvider
from app.models.domain import SourceItem


class GeneralWebSearch:
    def __init__(self, provider: SearchProvider = None):
        self.provider = provider or DuckDuckGoSearchProvider()

    def search(self, query: str, num_results: int = 5) -> List[SourceItem]:
        results = self.provider.search(query, num_results=num_results)
        return results
