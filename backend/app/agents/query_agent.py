import logging
from typing import Optional
from pydantic import BaseModel
from app.graph.state import ResearchState
from app.services.llm import get_llm_service

logger = logging.getLogger(__name__)


class QueryParseResult(BaseModel):
    org_hint: str
    exam_name_hint: str
    year_hint: str
    post_hint: Optional[str] = None
    extracted_education: Optional[str] = None
    extracted_age: Optional[int] = None
    extracted_category: Optional[str] = None


def query_agent_node(state: ResearchState) -> ResearchState:
    """
    Node 1: Uses fast Groq model to parse user_query into exam hints
    and user profile attributes if present in the text.
    """
    user_query = state.get("user_query", "")
    logger.info(f"QueryAgent parsing: '{user_query}'")

    llm = get_llm_service()

    prompt = f"""Parse the following Indian Government Exam research query into structured hints.
User Query: "{user_query}"

Extract:
- org_hint: Organization or recruiting body name (e.g., BPSC, SSC, UPSC, RRB, IBPS).
- exam_name_hint: Exam name (e.g., TRE 4.0 Computer Science, CGL, CDS, Constable).
- year_hint: Recruitment year or cycle (e.g., 2026, 2025, 2024). Default to current year if unspecified.
- post_hint: Target post name if mentioned (e.g., PGT Computer Science, Assistant Audit Officer, Inspector).
- extracted_education, extracted_age, extracted_category: Optional profile hints if user mentioned them in the prompt.
"""

    parsed: QueryParseResult = llm.invoke(
        prompt=prompt,
        model_tier="fast",
        response_schema=QueryParseResult,
    )

    # Merge user profile if extracted
    profile = state.get("user_profile") or {}
    if parsed.extracted_education and not profile.get("education"):
        profile["education"] = parsed.extracted_education
    if parsed.extracted_age and not profile.get("age"):
        profile["age"] = parsed.extracted_age
    if parsed.extracted_category and not profile.get("category"):
        profile["category"] = parsed.extracted_category

    status = dict(state.get("research_status", {}))
    status["query_agent"] = "completed"

    return {
        **state,
        "user_profile": profile,
        "recruitment": {
            "name": f"{parsed.org_hint} {parsed.exam_name_hint} {parsed.year_hint}".strip(),
            "org": parsed.org_hint,
            "year": parsed.year_hint,
            "post": parsed.post_hint,
        },
        "research_status": status,
    }
