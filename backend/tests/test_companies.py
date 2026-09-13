import json
from pathlib import Path

import httpx
import pytest

from app.sources.base import SourceError
from app.sources.companies import CompaniesSource, parse_ashby, parse_greenhouse, parse_lever
from app.sources.settings_file import Board

FIXTURES = Path(__file__).parent / "fixtures"
load = lambda name: json.loads((FIXTURES / name).read_text(encoding="utf-8"))

GROWW = Board(ats="greenhouse", slug="groww", name="Groww")
PAYTM = Board(ats="lever", slug="paytm", name="Paytm")
SARVAM = Board(ats="ashby", slug="sarvam", name="Sarvam AI")


def test_greenhouse_real_fixture():
    jobs = [parse_greenhouse(raw, GROWW, india_only=True) for raw in load("greenhouse_groww.json")["jobs"]]
    assert all(jobs)
    job = jobs[0]
    assert job.external_id == "greenhouse:groww:4880153101"
    assert job.company == "Groww"
    assert job.url.startswith("https://job-boards.eu.greenhouse.io/groww/jobs/")
    assert "India" in job.location
    assert job.posted_at.isoformat().startswith("2026-06-03")  # first_published, not updated_at
    assert job.job_type == "Full-time"
    assert job.description and "<" not in job.description and "&lt;" not in job.description


def test_lever_real_fixture_filters_to_india_and_maps_types():
    raws = load("lever_paytm.json")
    jobs = [parse_lever(raw, PAYTM, india_only=True) for raw in raws]
    kept = [j for j in jobs if j]
    assert len(kept) == 6  # Luxembourg-only role dropped; the Dubai role also lists Noida and Mumbai
    by_title = {j.title: j for j in kept}
    assert by_title["HR Payroll-Intern"].job_type == "Internship"
    assert by_title["Accounts Payable Specialist - Mumbai"].job_type == "Full-time"
    assert by_title["Affiliate Marketing (Social PR)"].job_type == "Full-time"  # "On-roll"
    assert all(j.external_id.startswith("lever:paytm:") for j in kept)
    assert len([parse_lever(raw, PAYTM, india_only=False) for raw in raws if parse_lever(raw, PAYTM, False)]) == 7


def test_ashby_real_fixture():
    jobs = [parse_ashby(raw, SARVAM, india_only=True) for raw in load("ashby_sarvam.json")["jobs"]]
    assert all(jobs)
    intern = jobs[0]
    assert intern.title == "Strategy and Operations Intern"
    assert intern.job_type == "Internship"  # title wins over employmentType "FullTime"
    assert {j.title: j.category for j in jobs}["Backend Engineer, Chanakya"] == "Backend"
    assert {j.title: j.category for j in jobs}["Data Scientist - Evaluations, Chanakya"] == "AI/ML"


def test_remote_india_roles():
    lever = parse_lever({"id": "x", "text": "Backend Intern", "hostedUrl": "https://jobs.lever.co/a/x", "country": "IN",
                         "workplaceType": "remote", "categories": {"location": "India", "commitment": "Intern"}},
                        PAYTM, True)
    assert lever.is_remote and lever.location == "India · Remote (India)"

    ashby = parse_ashby({"id": "y", "title": "ML Engineer", "jobUrl": "https://jobs.ashbyhq.com/a/y", "isRemote": True,
                         "location": "Remote", "address": {"postalAddress": {"addressCountry": "India"}},
                         "employmentType": "FullTime"}, SARVAM, True)
    assert ashby.is_remote and ashby.location == "Remote (India)"


def test_global_remote_dropped_when_india_only():
    raw = {"id": 1, "title": "SWE", "absolute_url": "https://boards.greenhouse.io/x/1", "location": {"name": "Remote - US"}}
    assert parse_greenhouse(raw, GROWW, india_only=True) is None
    assert parse_greenhouse(raw, GROWW, india_only=False).is_remote


@pytest.mark.parametrize("parser,board,raw", [
    (parse_greenhouse, GROWW, {"id": 1, "title": "X", "absolute_url": "javascript:alert(1)", "location": {"name": "India"}}),
    (parse_greenhouse, GROWW, {"title": "X", "absolute_url": "https://x", "location": {"name": "India"}}),
    (parse_lever, PAYTM, {"id": "1", "hostedUrl": "https://x", "country": "IN"}),
    (parse_ashby, SARVAM, {"id": "1", "title": "X", "jobUrl": "https://x", "location": "India", "isListed": False}),
    (parse_ashby, SARVAM, "garbage"),
    (parse_lever, PAYTM, {"id": "1", "text": "X", "hostedUrl": "https://x", "country": "IN", "createdAt": "soon",
                          "categories": "not-a-dict"}),
])
def test_malformed_or_unsafe_listings(parser, board, raw):
    job = parser(raw, board, True)
    if job is not None:  # the last case is usable, just with missing optional data
        assert job.posted_at is None and job.url == "https://x"


def make_source(handler, boards):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return CompaniesSource(boards, client=client, sleep=lambda s: None)


def test_one_bad_board_is_a_warning_not_a_failure():
    def handler(request):
        if "greenhouse" in request.url.host:
            return httpx.Response(200, json=load("greenhouse_groww.json"))
        return httpx.Response(404)

    result = make_source(handler, [GROWW, PAYTM]).fetch_jobs()
    assert len(result.jobs) == 5
    assert result.errors == ["lever/paytm: board not found (check the slug in config/sources.json)"]


def test_filtered_listings_are_not_counted_as_malformed():
    result = make_source(lambda r: httpx.Response(200, json=load("lever_paytm.json")), [PAYTM]).fetch_jobs()
    assert (len(result.jobs), result.skipped_records) == (6, 0)


def test_all_boards_failing_raises():
    with pytest.raises(SourceError):
        make_source(lambda r: httpx.Response(500), [GROWW, SARVAM]).fetch_jobs()


def test_wrong_shape_is_reported():
    result = make_source(lambda r: httpx.Response(200, json={"unexpected": True}) if "lever" in r.url.host
                         else httpx.Response(200, json=load("greenhouse_groww.json")), [GROWW, PAYTM]).fetch_jobs()
    assert "unexpected response shape" in result.errors[0]


def test_slug_validation_blocks_url_injection():
    with pytest.raises(ValueError):
        Board(ats="lever", slug="../../evil?x=1")
