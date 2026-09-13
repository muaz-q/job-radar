"""The contract every job source implements.

The rest of the app only ever sees `NormalizedJob` objects and `FetchResult`s, so a
new source (Cutshort, a company careers page, ...) is one new file in this package.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class NormalizedJob:
    source: str
    external_id: str | None
    company: str
    title: str
    url: str
    location: str | None = None
    is_remote: bool = False
    posted_at: datetime | None = None
    description: str | None = None
    job_type: str = "Full-time"
    category: str = "Other"
    compensation: str | None = None


@dataclass
class FetchResult:
    """What a source returns. Partial success is allowed: some jobs plus some errors."""

    jobs: list[NormalizedJob] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    # Raw records the source could not turn into a job (malformed data). Counted, not fatal.
    skipped_records: int = 0


class SourceError(Exception):
    """The source could not be fetched at all (network failure, blocked, page changed)."""


class JobSource(ABC):
    name: str
    display_name: str

    @abstractmethod
    def fetch_jobs(self) -> FetchResult:
        """Fetch current listings. Raise SourceError if nothing could be fetched."""
