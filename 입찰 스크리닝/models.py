from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass
class UniqueEvent:
    quote_id: int
    quote_name: str
    latest_date: str
    rebid_count: int

@dataclass
class EventGroup:
    group_name: str
    quote_ids: List[int]
    brands: List[str]
    search_keywords: List[str]

@dataclass
class SearchResults:
    group_name: str
    urls: List[str]
    url_snippets: Dict[str, str]

@dataclass
class ScreeningResult:
    group_name: str
    quote_ids: List[int]
    event_count: int
    supplier: Optional[str]
    coupon_type: Optional[str]
    face_value: Optional[str]
    validity_days: Optional[str]
    evidence_url: Optional[str]
    confidence: str
    confidence_reason: str
    search_date: str
