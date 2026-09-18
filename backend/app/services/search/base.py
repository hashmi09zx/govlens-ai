from abc import ABC, abstractmethod
from typing import List
from app.models.domain import SourceItem


class SearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, num_results: int = 5) -> List[SourceItem]:
        """Perform search and return list of SourceItems."""
        pass
