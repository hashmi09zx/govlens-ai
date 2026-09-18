import logging
import uuid
from typing import List, Optional
from pydantic import BaseModel
from app.graph.state import ResearchState
from app.services.llm import get_llm_service
from app.services.search.official import OfficialSourceSearch
from app.models.domain import RecruitmentCandidate

logger = logging.getLogger(__name__)


class DisambiguationAnalysis(BaseModel):
    is_ambiguous: bool
    reason: str
    candidates: List[RecruitmentCandidate]


def recruitment_id_agent_node(state: ResearchState) -> ResearchState:
    """
    Node 2: Disambiguates recruitment or locks in selected candidate.
    """
    logger.info("RecruitmentIDAgent analyzing query...")
    status = dict(state.get("research_status", {}))
    rec = state.get("recruitment") or {}
    selected_id = state.get("selected_candidate_id")

    # If user selected a candidate via resolve-recruitment endpoint: LOCK IN & RETURN
    if selected_id:
        cands = state.get("candidates") or []
        selected_cand = None
        for idx, cand in enumerate(cands):
            c_id = str(cand.get("id", ""))
            c_advt = str(cand.get("advt_number", ""))
            c_name = str(cand.get("name", ""))
            if str(selected_id) in [c_id, c_advt, c_name, str(idx), str(idx + 1)]:
                selected_cand = cand
                break

        if not selected_cand and cands:
            selected_cand = cands[0]

        if not selected_cand:
            selected_cand = {
                "id": str(uuid.uuid4()),
                "name": str(selected_id),
                "org": rec.get("org", "Government Board"),
                "year": rec.get("year", "2026"),
                "advt_number": "Official Notice",
            }

        logger.info(f"Recruitment locked by user selection: {selected_cand.get('name')}")
        status["recruitment_id"] = "resolved"
        return {
            **state,
            "recruitment": selected_cand,
            "research_status": status,
        }

    # Run official search to inspect notifications
    query_str = f"{rec.get('org', '')} {rec.get('name', '')} {rec.get('year', '')}"
    searcher = OfficialSourceSearch()
    search_results = searcher.search(query_str, num_results=5)

    snippets_text = "\n".join([f"- Title: {r.title} | Snippet: {r.snippet} | URL: {r.url}" for r in search_results])

    llm = get_llm_service()
    prompt = f"""Analyze the search results for the user query "{state.get('user_query')}".
Determine if there are multiple distinct recruitment notifications or advertisement cycles (e.g. TRE 3.0 vs TRE 4.0, or different post categories/advertisement numbers) that make the request ambiguous.

Search Results:
{snippets_text}

Instructions:
1. If the query clearly matches ONE single recruitment notification, set is_ambiguous = false and return 1 candidate item.
2. If there are 2 or more distinct plausible recruitment cycles/advt numbers, set is_ambiguous = true and list all plausible candidate options with distinct id, advt_number, org, year.
"""

    try:
        analysis: DisambiguationAnalysis = llm.invoke(
            prompt=prompt,
            model_tier="fast",
            response_schema=DisambiguationAnalysis,
        )

        if analysis.is_ambiguous and len(analysis.candidates) > 1:
            logger.info(f"Recruitment query is ambiguous. Surfacing {len(analysis.candidates)} candidates.")
            status["recruitment_id"] = "ambiguous"
            cands_dict = []
            for idx, c in enumerate(analysis.candidates):
                c_dict = c.model_dump()
                c_dict["id"] = f"cand_{idx+1}"
                cands_dict.append(c_dict)
            return {
                **state,
                "candidates": cands_dict,
                "research_status": status,
            }

        if analysis.candidates:
            locked_rec = analysis.candidates[0].model_dump()
            if not locked_rec.get("id"):
                locked_rec["id"] = str(uuid.uuid4())
        else:
            locked_rec = {
                "id": str(uuid.uuid4()),
                "name": rec.get("name", state.get("user_query")),
                "org": rec.get("org", "Government Recruitment Board"),
                "year": rec.get("year", "2026"),
                "advt_number": "Official Notification 2026",
                "post": rec.get("post"),
            }

        status["recruitment_id"] = "resolved"
        return {
            **state,
            "recruitment": locked_rec,
            "research_status": status,
        }

    except Exception as e:
        logger.warning(f"RecruitmentIDAgent error: {e}. Falling back to single recruitment object.")
        status["recruitment_id"] = "resolved"
        fallback_rec = {
            "id": str(uuid.uuid4()),
            "name": rec.get("name", state.get("user_query")),
            "org": rec.get("org", "Official Board"),
            "year": rec.get("year", "2026"),
            "advt_number": "01/2026",
            "post": rec.get("post"),
        }
        return {
            **state,
            "recruitment": fallback_rec,
            "research_status": status,
        }
