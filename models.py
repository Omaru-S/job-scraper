from dataclasses import dataclass
from typing import Optional


@dataclass
class JobOffer:
    title: str
    location: str
    url: str
    source: str
    company: Optional[str] = None
    posted_at: Optional[str] = None
    description: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    remote_type: Optional[str] = None  # "remote", "hybrid", "on-site", or None if unknown
    experience: Optional[str] = None
    score: Optional[float] = None
    grade: Optional[str] = None
