import logging
from typing import List, Dict, Any
from app.graph.state import ResearchState
from app.services.search.official import OfficialSourceSearch
from app.services.search.general import GeneralWebSearch

logger = logging.getLogger(__name__)


def source_agent_node(state: ResearchState) -> ResearchState:
    """
    Node 3: Generates adapted multi-query search set and discovers official + secondary sources.
    """
    rec = state.get("recruitment") or {}
    exam_name = rec.get("name") or state.get("user_query", "Government Recruitment")
    logger.info(f"SourceAgent running multi-query adaptive discovery for '{exam_name}'")

    # Clean queries without broken boolean query syntax
    queries = [
        f"{exam_name} official notification",
        f"{exam_name} eligibility criteria qualification age limit",
        f"{exam_name} vacancies details category wise",
        f"{exam_name} application fee important dates",
        f"{exam_name} selection process exam pattern syllabus",
    ]

    official_searcher = OfficialSourceSearch()
    general_searcher = GeneralWebSearch()

    official_sources: List[Dict[str, Any]] = list(state.get("official_sources") or [])
    secondary_sources: List[Dict[str, Any]] = list(state.get("secondary_sources") or [])
    seen_urls = set(s.get("url") for s in official_sources + secondary_sources)

    for query in queries:
        # Run official search
        off_res = official_searcher.search(query, num_results=3)
        for item in off_res:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                if item.source_type in ["official_notification", "official_website", "corrigendum"]:
                    official_sources.append(item.model_dump())
                else:
                    secondary_sources.append(item.model_dump())

        # Run general web search
        gen_res = general_searcher.search(query, num_results=3)
        for item in gen_res:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                secondary_sources.append(item.model_dump())

    status = dict(state.get("research_status", {}))
    status["source_agent"] = "completed"

    logger.info(f"SourceAgent discovered {len(official_sources)} official and {len(secondary_sources)} secondary sources.")

    return {
        **state,
        "official_sources": official_sources,
        "secondary_sources": secondary_sources,
        "research_status": status,
    }
