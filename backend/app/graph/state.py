from typing import TypedDict, Optional, List, Dict, Any


class ResearchState(TypedDict):
    user_query: str
    user_profile: Optional[Dict[str, Any]]
    recruitment: Optional[Dict[str, Any]]
    candidates: Optional[List[Dict[str, Any]]]
    official_sources: List[Dict[str, Any]]
    secondary_sources: List[Dict[str, Any]]
    extracted_facts: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    verified_facts: List[Dict[str, Any]]
    report: Dict[str, Any]
    user_requests: List[Dict[str, Any]]
    affected_sections: List[str]
    research_status: Dict[str, str]
    confidence: Dict[str, float]
    selected_candidate_id: Optional[str]
    field_retry_counts: Dict[str, int]
