"""Pydantic schemas: API input validation and response shapes."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LocationOption = Literal["Bengaluru", "Remote India", "Remote (Anywhere)"]
JobTypeOption = Literal["Internship", "Full-time", "Part-time", "Contract", "Other"]
CategoryOption = Literal[
    "Software Engineering", "AI/ML", "Backend", "Computer Vision", "Data", "DevOps", "Other"
]

LOCATION_OPTIONS: tuple[str, ...] = LocationOption.__args__
JOB_TYPE_OPTIONS: tuple[str, ...] = JobTypeOption.__args__
CATEGORY_OPTIONS: tuple[str, ...] = CategoryOption.__args__

MAX_KEYWORDS = 50
MAX_KEYWORD_LENGTH = 50
# Letters, digits, spaces and a few symbols that appear in tech terms (c++, c#, node.js, ai/ml).
_KEYWORD_ALLOWED = re.compile(r"^[\w\s+#./-]+$")


def _unique(values: list) -> list:
    return list(dict.fromkeys(values))


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locations: list[LocationOption] = Field(default_factory=list, max_length=len(LOCATION_OPTIONS))
    job_types: list[JobTypeOption] = Field(default_factory=list, max_length=len(JOB_TYPE_OPTIONS))
    categories: list[CategoryOption] = Field(default_factory=list, max_length=len(CATEGORY_OPTIONS))
    keywords: list[str] = Field(default_factory=list, max_length=MAX_KEYWORDS)
    max_age_days: int | None = Field(default=None, ge=1, le=365)
    browser_notifications: bool = True

    @field_validator("locations", "job_types", "categories")
    @classmethod
    def dedupe_options(cls, values: list[str]) -> list[str]:
        return _unique(values)

    @field_validator("keywords")
    @classmethod
    def sanitize_keywords(cls, values: list[str]) -> list[str]:
        cleaned = []
        for raw in values:
            keyword = " ".join(raw.split()).lower()
            if not keyword:
                continue
            if len(keyword) > MAX_KEYWORD_LENGTH:
                raise ValueError(f"keyword longer than {MAX_KEYWORD_LENGTH} characters: {keyword[:20]}...")
            if not _KEYWORD_ALLOWED.match(keyword):
                raise ValueError(f"keyword contains unsupported characters: {keyword!r}")
            cleaned.append(keyword)
        return _unique(cleaned)


class SettingsOut(SettingsIn):
    model_config = ConfigDict(from_attributes=True)


class SettingsOptions(BaseModel):
    locations: tuple[str, ...] = LOCATION_OPTIONS
    job_types: tuple[str, ...] = JOB_TYPE_OPTIONS
    categories: tuple[str, ...] = CATEGORY_OPTIONS


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    company: str
    title: str
    location: str | None
    is_remote: bool
    url: str
    posted_at: datetime | None
    first_seen_at: datetime
    job_type: str
    category: str
    compensation: str | None
    logo_url: str | None = None
    matches_filters: bool = False


class JobDetail(JobSummary):
    external_id: str | None
    description: str | None
    fingerprint: str
    matched_on_discovery: bool


class JobList(BaseModel):
    total: int
    items: list[JobSummary]


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    channel: str
    heading: str
    body: str
    url: str
    status: str
    created_at: datetime
    delivered_at: datetime | None


class SourceOut(BaseModel):
    name: str
    display_name: str
    enabled: bool
    status: str
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    last_fetched_count: int
    last_new_count: int
    total_jobs: int
    next_scan_at: datetime | None


class SourceScanSummary(BaseModel):
    source: str
    status: str
    fetched: int
    new: int
    duplicates: int
    matching: int
    notifications: int
    errors: list[str]


class ScanSummary(BaseModel):
    started_at: datetime
    finished_at: datetime
    sources: list[SourceScanSummary]
