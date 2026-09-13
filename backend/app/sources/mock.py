"""A local fake source for development and end-to-end testing without the network."""

from datetime import timedelta

from app.database import utcnow
from app.sources.base import FetchResult, JobSource, NormalizedJob

_SAMPLE_JOBS = [
    ("m-1", "Nimbus AI", "AI Engineer Intern", "Bengaluru", False, "Internship", "AI/ML", 12),
    ("m-2", "Stackwise", "Backend Intern", "Remote (India)", True, "Internship", "Backend", 22),
    ("m-3", "Optiq Labs", "Computer Vision Intern", "Bengaluru", False, "Internship", "Computer Vision", 90),
    ("m-4", "Ledgerly", "Senior Backend Engineer", "Bengaluru", False, "Full-time", "Backend", 300),
    ("m-5", "Brightpath", "Marketing Intern", "Mumbai", False, "Internship", "Other", 45),
    ("m-6", "Orbital Data", "Data Engineer", "Remote", True, "Full-time", "Data", 600),
]


class MockSource(JobSource):
    name = "mock"
    display_name = "Mock (development)"

    def __init__(self, emit_new_job_each_scan: bool = False):
        self.emit_new_job_each_scan = emit_new_job_each_scan

    def fetch_jobs(self) -> FetchResult:
        now = utcnow()
        jobs = [
            NormalizedJob(
                source=self.name,
                external_id=external_id,
                company=company,
                title=title,
                url=f"https://example.com/jobs/{external_id}",
                location=location,
                is_remote=remote,
                posted_at=now - timedelta(minutes=minutes_ago),
                description=f"{title} at {company}. Python, APIs and teamwork.",
                job_type=job_type,
                category=category,
            )
            for external_id, company, title, location, remote, job_type, category, minutes_ago in _SAMPLE_JOBS
        ]
        if self.emit_new_job_each_scan:
            stamp = now.strftime("%Y%m%d%H%M%S")
            jobs.append(NormalizedJob(
                source=self.name,
                external_id=f"live-{stamp}",
                company="Fresh Startup",
                title=f"ML Engineer Intern ({now:%H:%M:%S})",
                url=f"https://example.com/jobs/live-{stamp}",
                location="Bengaluru",
                posted_at=now,
                description="Brand-new mock job emitted by this scan.",
                job_type="Internship",
                category="AI/ML",
            ))
        return FetchResult(jobs=jobs)
