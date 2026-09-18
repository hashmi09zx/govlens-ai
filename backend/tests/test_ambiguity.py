import pytest
from app.graph.state import ResearchState
from app.graph.research_graph import check_recruitment_ambiguity


def test_recruitment_ambiguity_routing():
    ambiguous_state: ResearchState = {
        "user_query": "BPSC TRE",
        "user_profile": None,
        "recruitment": None,
        "candidates": [
            {"id": "cand_1", "name": "BPSC TRE 3.0", "org": "BPSC", "year": "2024", "advt_number": "22/2024"},
            {"id": "cand_2", "name": "BPSC TRE 4.0", "org": "BPSC", "year": "2025", "advt_number": "27/2025"},
        ],
        "official_sources": [],
        "secondary_sources": [],
        "extracted_facts": [],
        "conflicts": [],
        "verified_facts": [],
        "report": {},
        "user_requests": [],
        "affected_sections": [],
        "research_status": {"recruitment_id": "ambiguous"},
        "confidence": {},
        "selected_candidate_id": None,
        "field_retry_counts": {},
    }

    route = check_recruitment_ambiguity(ambiguous_state)
    assert route == "ambiguous"

    resolved_state = {**ambiguous_state, "research_status": {"recruitment_id": "resolved"}}
    route_resolved = check_recruitment_ambiguity(resolved_state)
    assert route_resolved == "resolved"
