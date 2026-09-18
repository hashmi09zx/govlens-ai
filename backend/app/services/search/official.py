import os
from typing import List
from app.services.search.base import SearchProvider
from app.services.search.duckduckgo_provider import DuckDuckGoSearchProvider
from app.models.domain import SourceItem


from app.models.domain import SourceItem, classify_source_authority


class OfficialSourceSearch:
    def __init__(self, provider: SearchProvider = None):
        self.provider = provider or DuckDuckGoSearchProvider()

    def search(self, query: str, num_results: int = 5) -> List[SourceItem]:
        # Clean query without breaking DuckDuckGo search parser
        clean_query = f"{query} official notice"
        results = self.provider.search(clean_query, num_results=num_results)

        # Tag and prioritize results using official classification
        for item in results:
            classification = classify_source_authority(url=item.url, title=item.title, snippet=item.snippet)
            item.source_type = classification["source_type"]
            item.authority_level = classification["authority_level"]
            item.official = classification["official"]

        return results

