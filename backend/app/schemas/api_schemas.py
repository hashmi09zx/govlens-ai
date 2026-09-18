from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.models.domain import UserProfile, RecruitmentCandidate


class ResearchRequest(BaseModel):
    user_query: str
    user_profile: Optional[UserProfile] = None


class ResearchResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ResolveRecruitmentRequest(BaseModel):
    selected_candidate_id: str


class RequestChangeInput(BaseModel):
    request_text: str
    target_sections: Optional[List[str]] = None


class JobStatusResponse(BaseModel):
    job_id: str
    recruitment_id: Optional[str] = None
    status: str
    current_step: str
    research_status: Dict[str, str] = {}
    candidates: Optional[List[RecruitmentCandidate]] = None
    error: Optional[str] = None


class ReportResponse(BaseModel):
    id: str
    recruitment_id: str
    version: str
    sections: Dict[str, Any]
    changed_sections: List[str] = []
    created_at: str


class ReportVersionItem(BaseModel):
    id: str
    version: str
    changed_sections: List[str] = []
    source_request_id: Optional[str] = None
    created_at: str
