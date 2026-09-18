import time
import logging
from typing import List
from ddgs import DDGS
from app.services.search.base import SearchProvider
from app.models.domain import SourceItem, classify_source_authority

logger = logging.getLogger(__name__)


class DuckDuckGoSearchProvider(SearchProvider):
    def search(self, query: str, num_results: int = 5) -> List[SourceItem]:
        results: List[SourceItem] = []
        queries_to_try = [query]

        # Add simplified fallback queries if original query was long
        words = query.split()
        if len(words) > 3:
            stop_words = {"detailed", "examination", "advertisement", "criteria", "for", "the", "in", "of", "and", "a", "an", "to"}
            meaningful_words = [w for w in words if w.lower() not in stop_words]
            if len(meaningful_words) >= 2:
                queries_to_try.append(" ".join(meaningful_words[:4]))
            queries_to_try.append(" ".join(words[-4:]))

        for q in queries_to_try:
            try:
                with DDGS() as ddgs:
                    ddg_results = list(ddgs.text(q, max_results=num_results))
                    for item in ddg_results:
                        url = item.get("href", "")
                        title = item.get("title", "")
                        snippet = item.get("body", "")

                        classification = classify_source_authority(url=url, title=title, snippet=snippet)

                        results.append(
                            SourceItem(
                                url=url,
                                title=title,
                                snippet=snippet,
                                source_type=classification["source_type"],
                                authority_level=classification["authority_level"],
                                official=classification["official"],
                            )
                        )
                if results:
                    break
            except Exception as e:
                logger.warning(f"DuckDuckGo search attempt failed for '{q}': {e}. Retrying fallback...")
                time.sleep(1.0)

        return results
