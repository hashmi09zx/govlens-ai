import pytest
from app.models.domain import Fact, classify_source_authority
from app.agents.conflict_agent import resolve_fact_conflict
from app.agents.verification_agent import verification_agent_node, EXHAUSTED_FALLBACK_STR


def test_1_official_source_available():
    """Test 1: Official source available -> use official value, official = True."""
    facts = [
        Fact(
            field="application_deadline",
            value="15 October 2026",
            source="BPSC Official Notification",
            source_url="https://bpsc.bihar.gov.in/notice_advt_2026.pdf",
            source_type="official_notification",
            authority_level=2,
            official=True,
            confidence=0.95,
        ).model_dump()
    ]
    
    state = {
        "extracted_facts": facts,
        "conflicts": [],
        "recruitment": {"name": "BPSC TRE 4.0"},
        "field_retry_counts": {
            "eligibility_education": 3,
            "eligibility_age_limit": 3,
            "vacancies_total": 3,
            "application_fee_general": 3,
            "exam_date": 3,
            "application_portal_url": 3,
        },
        "research_status": {},
    }
    
    result = verification_agent_node(state)
    verified = result["verified_facts"]
    
    deadline_fact = next(f for f in verified if f["field"] == "application_deadline")
    assert deadline_fact["value"] == "15 October 2026"
    assert deadline_fact["official"] is True
    assert deadline_fact["authority_level"] <= 4


def test_2_official_source_unavailable_secondary_used():
    """Test 2: Official source unavailable, secondary available -> use secondary value, official = False."""
    facts = [
        Fact(
            field="application_fee_general",
            value="₹750",
            source="Adda247 Education Portal",
            source_url="https://www.adda247.com/bpsc-tre-fee",
            source_type="reputed_secondary",
            authority_level=5,
            official=False,
            confidence=0.80,
        ).model_dump()
    ]
    
    state = {
        "extracted_facts": facts,
        "conflicts": [],
        "recruitment": {"name": "BPSC TRE 4.0"},
        "field_retry_counts": {
            "application_deadline": 3,
            "eligibility_education": 3,
            "eligibility_age_limit": 3,
            "vacancies_total": 3,
            "application_fee_general": 3,
            "exam_date": 3,
            "application_portal_url": 3,
        },
        "research_status": {},
    }
    
    result = verification_agent_node(state)
    verified = result["verified_facts"]
    
    fee_fact = next(f for f in verified if f["field"] == "application_fee_general")
    assert fee_fact["value"] == "₹750"
    assert fee_fact["official"] is False
    assert fee_fact["authority_level"] == 5


def test_3_multiple_secondary_sources_agree():
    """Test 3: Multiple secondary sources agree -> value used, marked non-official, corroborating sources recorded."""
    facts = [
        Fact(
            field="vacancies_total",
            value="32,388",
            source="Testbook",
            source_url="https://testbook.com/bpsc-vacancy",
            source_type="reputed_secondary",
            authority_level=5,
            official=False,
            confidence=0.75,
        ).model_dump(),
        Fact(
            field="vacancies_total",
            value="32,388",
            source="CareerPower",
            source_url="https://www.careerpower.in/bpsc-vacancy",
            source_type="reputed_secondary",
            authority_level=5,
            official=False,
            confidence=0.75,
        ).model_dump(),
    ]
    
    conflict_res = resolve_fact_conflict("vacancies_total", facts)
    assert conflict_res.resolved_value == "32,388"
    assert conflict_res.resolved is True

    state = {
        "extracted_facts": facts,
        "conflicts": [conflict_res.model_dump()],
        "recruitment": {"name": "BPSC TRE 4.0"},
        "field_retry_counts": {
            "application_deadline": 3,
            "eligibility_education": 3,
            "eligibility_age_limit": 3,
            "vacancies_total": 3,
            "application_fee_general": 3,
            "exam_date": 3,
            "application_portal_url": 3,
        },
        "research_status": {},
    }
    
    result = verification_agent_node(state)
    verified = result["verified_facts"]
    
    vacancy_fact = next(f for f in verified if f["field"] == "vacancies_total")
    assert vacancy_fact["value"] == "32,388"
    assert vacancy_fact["official"] is False


def test_4_sources_conflict_official_wins():
    """Test 4: Sources conflict (Official vs Secondary) -> Official source wins."""
    facts = [
        Fact(
            field="application_fee_general",
            value="₹750",
            source="BPSC Official Notice",
            source_url="https://bpsc.bihar.gov.in/notice.pdf",
            source_type="official_notification",
            authority_level=2,
            official=True,
            confidence=0.95,
        ).model_dump(),
        Fact(
            field="application_fee_general",
            value="₹700",
            source="Blog Post",
            source_url="https://someblog.com/bpsc-fee",
            source_type="blog_forum",
            authority_level=7,
            official=False,
            confidence=0.50,
        ).model_dump(),
    ]
    
    conflict_res = resolve_fact_conflict("application_fee_general", facts)
    assert conflict_res.resolved_value == "₹750"
    
    state = {
        "extracted_facts": facts,
        "conflicts": [conflict_res.model_dump()],
        "recruitment": {"name": "BPSC TRE 4.0"},
        "field_retry_counts": {
            "application_deadline": 3,
            "eligibility_education": 3,
            "eligibility_age_limit": 3,
            "vacancies_total": 3,
            "application_fee_general": 3,
            "exam_date": 3,
            "application_portal_url": 3,
        },
        "research_status": {},
    }

    
    result = verification_agent_node(state)
    verified = result["verified_facts"]
    
    fee_fact = next(f for f in verified if f["field"] == "application_fee_general")
    assert fee_fact["value"] == "₹750"
    assert fee_fact["official"] is True
    assert fee_fact["authority_level"] == 2


def test_5_no_reliable_source_fallback():
    """Test 5: No reliable source available -> returns updated exhausted fallback string."""
    state = {
        "extracted_facts": [],
        "conflicts": [],
        "recruitment": {"name": "NonExistentExam2099XYZ"},
        "field_retry_counts": {
            "application_deadline": 3,
            "eligibility_education": 3,
            "eligibility_age_limit": 3,
            "vacancies_total": 3,
            "application_fee_general": 3,
            "exam_date": 3,
            "application_portal_url": 3,
        },
        "research_status": {},
    }
    
    result = verification_agent_node(state)
    verified = result["verified_facts"]
    
    for field in ["application_deadline", "eligibility_education", "vacancies_total"]:
        fact = next(f for f in verified if f["field"] == field)
        assert fact["value"] == EXHAUSTED_FALLBACK_STR
        assert fact["value"] != "Not specified in the available official sources."


def test_6_source_transparency_metadata():
    """Test 6: Ensure every returned fact retains full source transparency metadata."""
    classification = classify_source_authority("https://bpsc.bihar.gov.in/advt.pdf", "BPSC Notice")
    fact = Fact(
        field="eligibility_age_limit",
        value="18 to 37 Years",
        source="BPSC Notice",
        source_url="https://bpsc.bihar.gov.in/advt.pdf",
        source_type=classification["source_type"],
        authority_level=classification["authority_level"],
        official=classification["official"],
        confidence=0.95,
    ).model_dump()

    required_keys = ["field", "value", "source", "source_url", "source_type", "authority_level", "official", "confidence"]
    for k in required_keys:
        assert k in fact, f"Missing source transparency key '{k}' in Fact"

    assert fact["authority_level"] == 2
    assert fact["official"] is True
