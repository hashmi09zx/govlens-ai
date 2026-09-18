import logging
from typing import List, Optional
from pydantic import BaseModel
from app.graph.state import ResearchState
from app.services.llm import get_llm_service

logger = logging.getLogger(__name__)


class RequestParseResult(BaseModel):
    affected_sections: List[str]
    requires_new_research: bool
    research_query: str


def request_agent_node(state: ResearchState) -> ResearchState:
    """
    Node 8: Parses HITL user change request into targeted affected sections and research query.
    """
    user_requests = state.get("user_requests") or []
    if not user_requests:
        logger.warning("RequestAgent called without user_requests in state.")
        return state

    latest_request = user_requests[-1]
    request_text = latest_request.get("request_text", "")

    logger.info(f"RequestAgent parsing HITL request: '{request_text}'")

    llm = get_llm_service()
    prompt = f"""You are a Human-In-The-Loop (HITL) request agent.
Parse the user's follow-up question/change request for a government exam report.

User Request: "{request_text}"

Available Report Sections:
1. exam_overview
2. important_dates
3. eligibility
4. personalized_eligibility
5. vacancies
6. salary
7. application_fees
8. required_documents
9. selection_process
10. exam_pattern_syllabus
11. application_procedure
12. faqs

Instructions:
1. Identify WHICH specific report section(s) are affected by this request (list section names).
2. Determine if targeted web re-research is required (requires_new_research = true/false).
3. Formulate a targeted search query for re-research.
"""

    try:
        parsed: RequestParseResult = llm.invoke(
            prompt=prompt,
            model_tier="fast",
            response_schema=RequestParseResult,
        )
        affected = parsed.affected_sections if parsed.affected_sections else ["eligibility"]
    except Exception as e:
        logger.warning(f"RequestAgent parsing failed: {e}. Defaulting to eligibility section.")
        affected = ["eligibility"]

    status = dict(state.get("research_status", {}))
    status["request_agent"] = "completed"

    return {
        **state,
        "affected_sections": affected,
        "research_status": status,
    }
