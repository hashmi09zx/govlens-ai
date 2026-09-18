import logging
from typing import List, Dict, Any
from app.graph.state import ResearchState
from app.models.domain import Fact, Conflict, classify_source_authority

logger = logging.getLogger(__name__)

# Authority ranking for conflict resolution (1 is highest priority, 7 is lowest)
AUTHORITY_RANK = {
    "official_corrigendum": 1,
    "official_notification": 2,
    "official_website": 3,
    "official_department": 4,
    "reputed_secondary": 5,
    "secondary_job_site": 6,
    "blog_forum": 7,
    "secondary": 6,
    "corrigendum": 1,
}


def get_fact_authority_level(fact: Dict[str, Any]) -> int:
    auth_lvl = fact.get("authority_level")
    if auth_lvl is not None and isinstance(auth_lvl, int):
        return auth_lvl
    st = fact.get("source_type", "secondary")
    return AUTHORITY_RANK.get(st, 6)


def resolve_fact_conflict(field: str, facts: List[Dict[str, Any]]) -> Conflict:
    """
    Applies deterministic progressive authority + agreement resolution rules:
    Priority 1 (Corrigendum) > Priority 2 (Official Notification) > Priority 3 (Official Website) >
    Priority 4 (Official Dept) > Priority 5 (Reputed Secondary) > Priority 6 (Job Site) > Priority 7 (Blog/Forum).

    If official sources are absent and multiple secondary sources agree on the same value,
    corroborates them into a single non-official fact with collected corroborating sources.
    """
    # Count frequency of values for secondary source agreement
    value_frequency: Dict[str, int] = {}
    value_sources: Dict[str, List[str]] = {}
    for f in facts:
        val_norm = str(f.get("value", "")).strip().lower()
        if val_norm:
            value_frequency[val_norm] = value_frequency.get(val_norm, 0) + 1
            src_url = f.get("source_url") or f.get("source") or ""
            if src_url:
                value_sources.setdefault(val_norm, []).append(src_url)

    # Sort facts: Primary sort by authority_level (ascending: 1 is best),
    # secondary sort by frequency of value (descending), tertiary sort by confidence (descending)
    sorted_facts = sorted(
        facts,
        key=lambda f: (
            get_fact_authority_level(f),
            -value_frequency.get(str(f.get("value", "")).strip().lower(), 1),
            -float(f.get("confidence", 0.5)),
        ),
    )

    winning_fact = dict(sorted_facts[0])
    winning_val_norm = str(winning_fact.get("value", "")).strip().lower()
    auth_lvl = get_fact_authority_level(winning_fact)
    is_official = winning_fact.get("official", auth_lvl <= 4)

    # If multiple secondary sources agree, record corroborating sources & boost confidence
    agreed_sources = list(set(value_sources.get(winning_val_norm, [])))
    if len(agreed_sources) > 1:
        winning_fact["corroborating_sources"] = agreed_sources
        if not is_official:
            winning_fact["confidence"] = min(0.90, float(winning_fact.get("confidence", 0.70)) + 0.15)

    winning_val = winning_fact["value"]
    winning_source_type = winning_fact.get("source_type", "secondary")

    if is_official:
        reason = f"Resolved using official authority hierarchy: '{winning_source_type}' (Level {auth_lvl}) preferred over secondary sources."
    elif len(agreed_sources) > 1:
        reason = f"Resolved via multi-source agreement across {len(agreed_sources)} independent secondary sources: {winning_val}."
    else:
        reason = f"Resolved using highest available secondary source level ({winning_source_type}, Level {auth_lvl})."

    # Ensure model compatibility
    pydantic_facts = []
    for f in facts:
        f_copy = dict(f)
        f_copy["authority_level"] = get_fact_authority_level(f_copy)
        f_copy["official"] = f_copy.get("official", f_copy["authority_level"] <= 4)
        pydantic_facts.append(Fact.model_validate(f_copy))

    return Conflict(
        field=field,
        conflicting_facts=pydantic_facts,
        resolved_value=winning_val,
        resolution_reason=reason,
        resolved=True,
    )


def conflict_agent_node(state: ResearchState) -> ResearchState:
    """
    Node 5: Detects conflicting facts by field and resolves using deterministic source authority hierarchy.
    """
    facts = state.get("extracted_facts") or []
    logger.info(f"ConflictAgent analyzing {len(facts)} extracted facts for conflicts...")

    # Group facts by field
    field_facts: Dict[str, List[Dict[str, Any]]] = {}
    for f in facts:
        field = f.get("field")
        if field:
            field_facts.setdefault(field, []).append(f)

    conflicts: List[Dict[str, Any]] = []

    for field, fact_list in field_facts.items():
        # Check if there are distinct conflicting values
        distinct_vals = set(f.get("value", "").strip().lower() for f in fact_list)
        if len(distinct_vals) > 1:
            logger.info(f"Conflict detected for field '{field}' across {len(fact_list)} facts.")
            conflict_obj = resolve_fact_conflict(field, fact_list)
            conflicts.append(conflict_obj.model_dump())

    status = dict(state.get("research_status", {}))
    status["conflict_agent"] = "completed"

    return {
        **state,
        "conflicts": conflicts,
        "research_status": status,
    }

