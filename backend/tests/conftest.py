from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.database import Database, utcnow
from app.main import create_app
from app.scanner import Scanner
from app.schemas import SettingsIn
from app.settings_store import save_settings
from app.sources.base import FetchResult, JobSource, NormalizedJob, SourceError


def make_job(n: int | str = 1, **overrides) -> NormalizedJob:
    values = dict(
        source="fake",
        external_id=f"ext-{n}",
        company=f"Company {n}",
        title=f"Backend Engineer Intern {n}",
        url=f"https://jobs.example.com/{n}",
        location="Bengaluru",
        is_remote=False,
        posted_at=utcnow() - timedelta(hours=1),
        description="Python APIs",
        job_type="Internship",
        category="Backend",
    )
    values.update(overrides)
    return NormalizedJob(**values)


class FakeSource(JobSource):
    """A source whose output each test controls."""

    name = "fake"
    display_name = "Fake"

    def __init__(self, jobs=None, error: Exception | None = None):
        self.jobs = list(jobs or [])
        self.error = error
        self.errors: list[str] = []

    def fetch_jobs(self) -> FetchResult:
        if self.error:
            raise self.error
        return FetchResult(jobs=list(self.jobs), errors=list(self.errors))


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(f"sqlite:///{tmp_path / 'test.db'}")
    database.create_all()
    return database


@pytest.fixture
def open_settings(db):
    """Settings that match everything, so tests of dedup aren't entangled with filters."""
    with db.session() as session:
        save_settings(session, SettingsIn(locations=[], job_types=[], categories=[], keywords=[],
                                          max_age_days=None, browser_notifications=True))


@pytest.fixture
def source() -> FakeSource:
    return FakeSource()


@pytest.fixture
def scanner(db, source) -> Scanner:
    return Scanner(db, [source])


@pytest.fixture
def client(scanner) -> TestClient:
    config = Config(scheduler_enabled=False, min_manual_scan_gap_seconds=0, enabled_sources="mock",
                    _env_file=None)
    with TestClient(create_app(config, scanner)) as test_client:
        yield test_client


__all__ = ["FakeSource", "SourceError", "make_job"]
