from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field


SourceTypeLiteral = Literal[
    "official_corrigendum",
    "official_notification",
    "official_website",
    "official_department",
    "reputed_secondary",
    "secondary_job_site",
    "blog_forum",
    "secondary",
    "corrigendum",
]


def classify_source_authority(url: str, title: str = "", snippet: str = "") -> Dict[str, Any]:
    """
    Deterministically classifies a URL and title into the 7-level source priority hierarchy:
    Priority 1: Corrigendum / Official Amendment (official=True)
    Priority 2: Official Recruitment Notification (official=True)
    Priority 3: Official Government / Recruitment Website (official=True)
    Priority 4: Official Department / Ministry Website (official=True)
    Priority 5: Reputed Secondary Source (official=False)
    Priority 6: Other Reliable Educational / Job Information Website (official=False)
    Priority 7: Blog / Forum / User-generated Source (official=False)
    """
    low_url = (url or "").lower()
    low_title = (title or "").lower()
    low_snippet = (snippet or "").lower()
    combined_text = f"{low_url} {low_title} {low_snippet}"

    # Official domain check
    official_domains = [
        ".gov.in", ".nic.in", "bpsc.bihar.gov.in", "bpsc", "ssc.gov.in", "upsc.gov.in",
        "rrb", "ibps.in", "nta.ac.in", "cbse.gov.in", "sbi.co.in", "rbi.org.in"
    ]
    is_official_domain = any(domain in low_url for domain in official_domains)

    # Priority 1: Corrigendum / Official Amendment
    if any(term in combined_text for term in ["corrigendum", "amendment", "addendum", "erratum", "errata"]):
        if is_official_domain or ".pdf" in low_url:
            return {"source_type": "official_corrigendum", "authority_level": 1, "official": True}
        return {"source_type": "reputed_secondary", "authority_level": 5, "official": False}

    # Priority 2: Official Recruitment Notification
    if is_official_domain and any(term in combined_text for term in ["notification", "advt", "advertisement", "pdf", "notice"]):
        return {"source_type": "official_notification", "authority_level": 2, "official": True}

    # Priority 3: Official Government / Recruitment Website
    if is_official_domain:
        if any(term in low_url for term in ["bpsc", "ssc", "upsc", "rrb", "ibps"]):
            return {"source_type": "official_website", "authority_level": 3, "official": True}
        return {"source_type": "official_department", "authority_level": 4, "official": True}

    # General .gov domain
    if ".gov" in low_url or ".nic" in low_url:
        return {"source_type": "official_department", "authority_level": 4, "official": True}

    # Priority 7: Blog / Forum / User-generated
    if any(term in low_url for term in ["forum", "reddit", "quora", "medium.com", "wordpress.com", "blogspot.com", "telegram", "facebook.com", "twitter.com"]):
        return {"source_type": "blog_forum", "authority_level": 7, "official": False}

    # Priority 5: Reputed Secondary Source
    reputed_domains = [
        "adda247.com", "testbook.com", "careerpower.in", "sarkariresult.com",
        "jagranjosh.com", "byjusexamprep.com", "pw.live", "unacademy.com",
        "timesofindia", "indianexpress", "hindustantimes", "livemint", "thehindu",
        "careers360.com", "collegedunia.com", "shiksha.com", "sarkariresult"
    ]
    if any(domain in low_url for domain in reputed_domains):
        return {"source_type": "reputed_secondary", "authority_level": 5, "official": False}

    # Priority 6: Other Reliable Educational / Job Information Website
    return {"source_type": "secondary_job_site", "authority_level": 6, "official": False}


class Fact(BaseModel):
    field: str
    value: str
    source: str
    source_url: Optional[str] = None
    source_type: SourceTypeLiteral = "secondary"
    authority_level: int = Field(default=7, ge=1, le=7)
    official: bool = False
    source_date: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    corroborating_sources: List[str] = Field(default_factory=list)


class Conflict(BaseModel):
    field: str
    conflicting_facts: List[Fact]
    resolved_value: Optional[str] = None
    resolution_reason: Optional[str] = None
    resolved: bool = False


class SourceItem(BaseModel):
    url: str
    title: str
    snippet: str = ""
    source_type: SourceTypeLiteral = "secondary"
    authority_level: int = 7
    official: bool = False
    content_hash: Optional[str] = None


class UserProfile(BaseModel):
    education: Optional[str] = None
    age: Optional[int] = None
    category: Optional[str] = None
    gender: Optional[str] = None
    state: Optional[str] = None


class RecruitmentCandidate(BaseModel):
    id: str
    name: str
    org: str
    year: str
    advt_number: str
    post: Optional[str] = None

