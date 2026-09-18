import pytest
from app.agents.verification_agent import verification_agent_node
from app.graph.state import ResearchState


def test_verification_agent_bounded_retries():
    # Low confidence extracted fact for high-risk field
    initial_state: ResearchState = {
        "user_query": "UPSC CDS 2026",
        "user_profile": None,
        "recruitment": {"name": "UPSC CDS 2026", "org": "UPSC", "year": "2026"},
        "candidates": None,
        "official_sources": [],
        "secondary_sources": [],
        "extracted_facts": [
            {
                "field": "application_deadline",
                "value": "Tentative 2026",
                "source": "https://randomblog.com/cds",
                "source_type": "secondary",
                "confidence": 0.40,
            }
        ],
        "conflicts": [],
        "verified_facts": [],
        "report": {},
        "user_requests": [],
        "affected_sections": [],
        "research_status": {},
        "confidence": {},
        "selected_candidate_id": None,
        "field_retry_counts": {
            "application_deadline": 3,
            "eligibility_education": 3,
            "eligibility_age_limit": 3,
            "vacancies_total": 3,
            "application_fee_general": 3,
            "exam_date": 3,
            "application_portal_url": 3,
        },  # Reached max retries across all fields
    }

    res_state = verification_agent_node(initial_state)

    # Must find fallback value "Information could not be reliably determined from the available sources."
    deadline_facts = [f for f in res_state["verified_facts"] if f.get("field") == "application_deadline"]
    assert len(deadline_facts) > 0
    fallback_fact = deadline_facts[-1]
    assert fallback_fact["value"] == "Information could not be reliably determined from the available sources."

