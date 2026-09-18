import time
import logging
from typing import List, Dict, Any
from pydantic import BaseModel
from app.graph.state import ResearchState
from app.models.domain import Fact
from app.services.llm import get_llm_service
from app.services.fetcher import FetcherService

logger = logging.getLogger(__name__)


class FactExtractionResponse(BaseModel):
    facts: List[Fact]


def extraction_agent_node(state: ResearchState) -> ResearchState:
    """
    Node 4: Fetches source pages and extracts structured Fact objects using the Groq LLM.
    """
    official_sources = state.get("official_sources") or []
    secondary_sources = state.get("secondary_sources") or []
    all_sources = official_sources + secondary_sources

    logger.info(f"ExtractionAgent processing {len(all_sources)} sources...")

    fetcher = FetcherService()
    llm = get_llm_service()
    extracted_facts: List[Dict[str, Any]] = list(state.get("extracted_facts") or [])

    # Process top 8 sources for deep coverage
    target_sources = all_sources[:8]

    for src in target_sources:
        url = src.get("url", "")
        source_type = src.get("source_type", "secondary")
        snippet = src.get("snippet", "")

        # Fetch page text
        text, content_hash = fetcher.fetch_url(url)
        if content_hash:
            src["content_hash"] = content_hash

        # Combine snippet and fetched page text (up to 12,000 chars)
        combined_text = f"Title/Snippet: {snippet}\n\nPage Text:\n{text[:12000] if text else snippet}"

        prompt = f"""You are an autonomous evidence extraction agent for Indian Government Recruitment Exams.
Extract comprehensive, detailed recruitment facts from the source text below for the exam "{state.get('user_query')}".

Source URL: {url}
Source Type: {source_type}

Source Text:
{combined_text}

Instructions:
Extract facts for any of the following fields if present:
- exam_overview: Summary of recruitment, conducting body, posts, purpose.
- application_deadline: Closing date for online application.
- start_date: Opening date for online application.
- exam_date: Date or tentative month of examination.
- eligibility_education: Degree, diploma, subject specialization requirements (e.g. B.Tech CS, MCA, B.Sc).
- eligibility_age_limit: Minimum and maximum age cutoff, age relaxations for reserved categories.
- eligibility_nationality: Citizenship/Domicile requirements.
- vacancies_total: Total number of posts advertised.
- vacancies_breakdown: Post-wise, subject-wise, or category-wise vacancy distribution.
- salary_pay_scale: Pay level, grade pay, basic pay scale.
- application_fee_general: Fee for General / OBC / EWS candidates.
- application_fee_reserved: Fee for SC / ST / PwD / Female candidates.
- required_documents: Certificates, photos, ID proofs needed at application and document verification time.
- selection_process: Stages of recruitment (Prelims, Mains, Interview, Document Verification, Skill Test, Cutoffs, Negative marking).
- exam_pattern: Exam duration, subjects, marks per section, negative marking scheme, mode of exam.
- application_portal_url: Official website link to apply.

Rules:
1. Extract rich, clear, complete details for each field.
2. Set confidence between 0.85 and 1.0 for official sources; between 0.65 and 0.85 for reputable secondary sources.
3. NEVER invent fake dates or fees if completely absent from the text.
"""

        try:
            res: FactExtractionResponse = llm.invoke(
                prompt=prompt,
                model_tier="large",
                response_schema=FactExtractionResponse,
            )
            for fact in res.facts:
                fact_dict = fact.model_dump()
                fact_dict["source"] = url
                fact_dict["source_type"] = source_type
                extracted_facts.append(fact_dict)

        except Exception as e:
            logger.warning(f"Fact extraction failed for {url}: {e}")

        # Pace calls to stay under Groq free-tier rate limits (TPM)
        time.sleep(1.2)

    status = dict(state.get("research_status", {}))
    status["extraction_agent"] = "completed"

    logger.info(f"ExtractionAgent extracted total {len(extracted_facts)} facts.")

    return {
        **state,
        "extracted_facts": extracted_facts,
        "research_status": status,
    }
