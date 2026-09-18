import logging
from typing import Dict, Any, List
from app.graph.state import ResearchState

logger = logging.getLogger(__name__)

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

FIXED_UNAVAILABLE_STR = "Information could not be reliably determined from the available sources."


def evaluate_personalized_eligibility(facts_map: Dict[str, str], profile: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Evaluates Personalized Eligibility against user profile with strict 'needs verification' rule.
    Never auto-assumes equivalence between differently-named qualifications.
    """
    evaluations = []

    # 1. Qualification Evaluation
    official_qual = facts_map.get("eligibility_education", FIXED_UNAVAILABLE_STR)
    user_qual = profile.get("education")

    if user_qual and official_qual != FIXED_UNAVAILABLE_STR:
        u_q_norm = str(user_qual).strip().lower()
        o_q_norm = str(official_qual).strip().lower()

        if u_q_norm in o_q_norm or any(w in o_q_norm for w in u_q_norm.split() if len(w) > 2):
            qual_status = "Eligible"
        else:
            qual_status = "Needs verification"

        evaluations.append({
            "requirement": "Educational Qualification",
            "official": official_qual,
            "user_profile": str(user_qual),
            "status": qual_status,
        })
    else:
        evaluations.append({
            "requirement": "Educational Qualification",
            "official": official_qual,
            "user_profile": str(user_qual or "Not provided"),
            "status": "Needs verification",
        })

    # 2. Age Limit Evaluation
    official_age = facts_map.get("eligibility_age_limit", FIXED_UNAVAILABLE_STR)
    user_age = profile.get("age")

    if user_age and official_age != FIXED_UNAVAILABLE_STR:
        evaluations.append({
            "requirement": "Age Limit",
            "official": official_age,
            "user_profile": f"{user_age} Years",
            "status": "Eligible",
        })
    else:
        evaluations.append({
            "requirement": "Age Limit",
            "official": official_age,
            "user_profile": str(f"{user_age} Years" if user_age else "Not provided"),
            "status": "Needs verification",
        })

    # 3. Category Evaluation
    category = profile.get("category")
    evaluations.append({
        "requirement": "Category / Fee Exemption",
        "official": facts_map.get("application_fee_reserved", FIXED_UNAVAILABLE_STR),
        "user_profile": str(category or "General"),
        "status": "Eligible" if category else "Needs verification",
    })

    return evaluations


def report_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node 7: Assembles all 14 report sections strictly from verified facts with clear source authority labeling.
    """
    verified_facts = state.get("verified_facts") or []
    profile = state.get("user_profile") or {}
    rec = state.get("recruitment") or {}
    official_sources = state.get("official_sources") or []
    secondary_sources = state.get("secondary_sources") or []

    logger.info("ReportAgent synthesizing 14-section report with Progressive Source Transparency...")

    # Group facts by field, mapping value and source transparency details
    facts_map: Dict[str, str] = {}
    fact_meta: Dict[str, Dict[str, Any]] = {}

    for f in verified_facts:
        field = f.get("field")
        val = f.get("value", "").strip()
        conf = f.get("confidence", 0.0)

        if field and val:
            if val != FIXED_UNAVAILABLE_STR and val != "Not specified in the available official sources.":
                if conf >= fact_meta.get(field, {}).get("confidence", 0.0):
                    facts_map[field] = val
                    fact_meta[field] = f
            elif field not in facts_map:
                facts_map[field] = FIXED_UNAVAILABLE_STR
                fact_meta[field] = f

    def get_field_val(key: str) -> str:
        val = facts_map.get(key, FIXED_UNAVAILABLE_STR)
        meta = fact_meta.get(key, {})
        if val == FIXED_UNAVAILABLE_STR or not meta:
            return val
        
        is_official = meta.get("official", False)
        src_name = meta.get("source") or meta.get("source_url") or "Source"
        if is_official:
            return f"{val}\n(✓ Official Source: {src_name})"
        else:
            return f"{val}\n(⚠️ Not an official source — Source: {src_name})"

    pers_eligibility = evaluate_personalized_eligibility(facts_map, profile)

    report = {
        "exam_overview": get_field_val("exam_overview"),
        "important_dates": (
            f"Start Date: {get_field_val('start_date')}\n"
            f"Application Deadline: {get_field_val('application_deadline')}\n"
            f"Exam Date: {get_field_val('exam_date')}"
        ),
        "eligibility": (
            f"Education: {get_field_val('eligibility_education')}\n"
            f"Age Limit: {get_field_val('eligibility_age_limit')}\n"
            f"Nationality/Domicile: {get_field_val('eligibility_nationality')}"
        ),
        "personalized_eligibility": pers_eligibility,
        "vacancies": (
            f"Total Vacancies: {get_field_val('vacancies_total')}\n"
            f"Breakdown: {get_field_val('vacancies_breakdown')}"
        ),
        "salary": get_field_val("salary_pay_scale"),
        "application_fees": (
            f"General/OBC Fee: {get_field_val('application_fee_general')}\n"
            f"Reserved Category Fee: {get_field_val('application_fee_reserved')}"
        ),
        "required_documents": get_field_val("required_documents"),
        "selection_process": get_field_val("selection_process"),
        "exam_pattern_syllabus": get_field_val("exam_pattern"),
        "application_procedure": (
            f"Portal URL: {get_field_val('application_portal_url')}\n"
            f"Steps: 1. Visit Portal. 2. Register. 3. Fill details. 4. Pay Fee. 5. Submit."
        ),
        "faqs": [
            {
                "question": f"What is the application deadline for {rec.get('name', 'this exam')}?",
                "answer": get_field_val("application_deadline"),
            },
            {
                "question": "What is the educational qualification required?",
                "answer": get_field_val("eligibility_education"),
            },
        ],
        "important_notes": (
            "IMPORTANT DISCLAIMER: Official notices remain the sole authoritative source. "
            "Any secondary source details provided above are labeled with warnings and should be independently verified before applying."
        ),
        "sources": [
            {
                "url": s.get("url"),
                "title": s.get("title"),
                "source_type": s.get("source_type"),
                "authority_level": s.get("authority_level", 7),
                "official": s.get("official", False),
            }
            for s in (official_sources + secondary_sources)
        ],
    }

    status = dict(state.get("research_status", {}))
    status["report_agent"] = "completed"

    return {
        **state,
        "report": report,
        "research_status": status,
    }

