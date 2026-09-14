"""Company logos: extraction per source, safe storage, backfill, and upgrading an existing database."""

import json
import sqlite3
from pathlib import Path

import httpx
from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect
from sqlalchemy.schema import CreateTable

from app.database import Database
from app.models import Job
from app.scanner import Scanner
from app.schemas import JobSummary
from app.sources.companies import CompaniesSource, company_logo_url
from app.sources.settings_file import Board
from app.sources.unstop import parse_opportunity
from app.sources.wellfound import parse_search_page
from tests.conftest import FakeSource, make_job

FIXTURES = Path(__file__).parent / "fixtures"


def test_unstop_uses_company_logo_never_the_listing_image():
    raws = json.loads((FIXTURES / "unstop_page.json").read_text(encoding="utf-8"))["data"]["data"]
    jobs = {raw["id"]: parse_opportunity(raw) for raw in raws}
    with_logo = next(r for r in raws if r["organisation"].get("logoUrl"))
    without = next(r for r in raws if not r["organisation"].get("logoUrl") and r.get("logoUrl2"))
    assert jobs[with_logo["id"]].logo_url == with_logo["organisation"]["logoUrl"]
    assert jobs[without["id"]].logo_url is None  # logoUrl2 can be a recruiter's photo


def test_wellfound_logo_comes_from_the_startup():
    jobs, _ = parse_search_page((FIXTURES / "wellfound_search_page.html").read_text(encoding="utf-8"))
    assert all(j.logo_url and j.logo_url.startswith("https://photos.wellfound.com/") for j in jobs)


def test_company_boards_use_the_configured_domain():
    board = Board(ats="greenhouse", slug="groww", name="Groww", domain="groww.in")
    assert company_logo_url(board) == "https://www.google.com/s2/favicons?domain=groww.in&sz=128"
    assert company_logo_url(Board(ats="lever", slug="x")) is None
    listing = json.loads((FIXTURES / "greenhouse_groww.json").read_text(encoding="utf-8"))
    source = CompaniesSource([board], client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=listing))),
                             sleep=lambda s: None)
    assert {j.logo_url for j in source.fetch_jobs().jobs} == {company_logo_url(board)}


def test_domain_is_validated():
    import pytest
    for bad in ("groww.in/../../x", "javascript:alert(1)", "evil.com?x=1", "localhost"):
        with pytest.raises(ValueError):
            Board(ats="lever", slug="x", domain=bad)


def logos(db):
    with db.session() as session:
        return {j.external_id: j.logo_url for j in session.query(Job)}


def test_only_https_logos_are_stored(db, open_settings):
    source = FakeSource(jobs=[make_job(1, logo_url="https://cdn.example/logo.png"),
                              make_job(2, logo_url="http://cdn.example/logo.png"),
                              make_job(3, logo_url="javascript:alert(1)"), make_job(4)])
    Scanner(db, [source]).scan()
    assert logos(db) == {"ext-1": "https://cdn.example/logo.png", "ext-2": None, "ext-3": None, "ext-4": None}


def test_jobs_stored_before_logos_existed_get_one_on_the_next_scan(db, open_settings):
    source = FakeSource(jobs=[make_job(1), make_job(2, logo_url="https://cdn.example/original.png")])
    Scanner(db, [source]).scan()
    source.jobs = [make_job(1, logo_url="https://cdn.example/new.png"), make_job(2, logo_url="https://cdn.example/other.png")]
    summary = Scanner(db, [source]).scan().sources[0]
    assert summary.new == 0 and summary.notifications == 0  # backfilling is not a new job
    assert logos(db) == {"ext-1": "https://cdn.example/new.png", "ext-2": "https://cdn.example/original.png"}


def test_logo_is_part_of_the_api_and_export_shape():
    assert "logo_url" in JobSummary.model_fields


def test_existing_database_without_the_column_is_upgraded_in_place(tmp_path):
    """The hosted database on the data branch was created before logos existed."""
    path = tmp_path / "old.db"
    old_ddl = str(CreateTable(Job.__table__).compile(dialect=sqlite_dialect()))
    old_ddl = "\n".join(line for line in old_ddl.splitlines() if "logo_url" not in line)
    connection = sqlite3.connect(path)
    connection.execute(old_ddl)
    connection.execute("INSERT INTO jobs (source, company, title, url, first_seen_at, job_type, category, fingerprint, "
                       "content_key, is_remote, matched_on_discovery) VALUES ('s', 'Acme', 'Intern', 'https://x', "
                       "'2026-09-01 00:00:00', 'Internship', 'Other', 'fp', 'ck', 0, 1)")
    connection.commit()
    connection.close()

    db = Database(f"sqlite:///{path.as_posix()}")
    db.create_all()
    db.create_all()  # running twice must be harmless
    with db.session() as session:
        job = session.query(Job).one()
        assert (job.company, job.logo_url) == ("Acme", None)
