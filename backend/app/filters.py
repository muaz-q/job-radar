"""Deterministic filter matching.

Semantics:
- Dimensions combine with AND: location AND job type AND category AND keywords AND age.
- Options within a dimension combine with OR.
- An empty dimension means "don't filter on this".
- Keywords match whole words/phrases, case-insensitively, in title, company or description.
  They are escaped before use; user input is never interpreted as a regex.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol


class JobLike(Protocol):
    title: str
    company: str
    location: str | None
    is_remote: bool
    description: str | None
    job_type: str
    category: str
    posted_at: datetime | None


@dataclass(frozen=True)
class FilterSettings:
    locations: list[str] = field(default_factory=list)
    job_types: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    max_age_days: int | None = None

    @classmethod
    def from_model(cls, settings) -> "FilterSettings":
        return cls(
            locations=list(settings.locations or []),
            job_types=list(settings.job_types or []),
            categories=list(settings.categories or []),
            keywords=list(settings.keywords or []),
            max_age_days=settings.max_age_days,
        )


_BENGALURU = re.compile(r"\b(bengaluru|bangalore|bangaluru)\b", re.I)
_INDIA = re.compile(r"\bindia\b", re.I)


def matches_location(job: JobLike, option: str) -> bool:
    location = job.location or ""
    if option == "Bengaluru":
        return bool(_BENGALURU.search(location))
    if option == "Remote India":
        return job.is_remote and bool(_INDIA.search(location))
    if option == "Remote (Anywhere)":
        return job.is_remote
    return False


def _keyword_pattern(keyword: str) -> re.Pattern:
    # \b fails next to symbols like "c++", so use explicit non-word lookarounds.
    return re.compile(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", re.I)


def matches_keywords(job: JobLike, keywords: list[str]) -> bool:
    haystack = " ".join(filter(None, [job.title, job.company, job.description]))
    return any(_keyword_pattern(k).search(haystack) for k in keywords)


def is_recent_enough(job: JobLike, max_age_days: int | None, now: datetime | None = None) -> bool:
    if max_age_days is None or job.posted_at is None:  # unknown posting date: don't hide it
        return True
    now = now or datetime.now(timezone.utc)
    return job.posted_at >= now - timedelta(days=max_age_days)


def matches_filters(job: JobLike, settings: FilterSettings, now: datetime | None = None) -> bool:
    if settings.locations and not any(matches_location(job, o) for o in settings.locations):
        return False
    if settings.job_types and job.job_type not in settings.job_types:
        return False
    if settings.categories and job.category not in settings.categories:
        return False
    if settings.keywords and not matches_keywords(job, settings.keywords):
        return False
    return is_recent_enough(job, settings.max_age_days, now)
