import json
from pathlib import Path

import httpx
import pytest

from app.filters import matches_location
from app.sources.base import SourceError
from app.sources.unstop import UnstopSource, parse_opportunity

PAGE = json.loads((Path(__file__).parent / "fixtures" / "unstop_page.json").read_text(encoding="utf-8"))


def test_real_page_fixture():
    jobs = [parse_opportunity(raw) for raw in PAGE["data"]["data"]]
    assert all(jobs)
    assert all(j.job_type == "Internship" and j.url.startswith("https://unstop.com/internships/") for j in jobs)
    assert all(j.posted_at is not None and j.posted_at.tzinfo is not None for j in jobs)

    by_title = {j.title: j for j in jobs}
    bangalore = by_title["Lawyer Internship"]
    assert matches_location(bangalore, "Bengaluru")
    wfh = by_title["Campus Ambassador Internship"]
    assert wfh.is_remote and wfh.location == "Remote (India)"
    assert matches_location(wfh, "Remote India")
    hr = by_title["HR Internship"]
    assert hr.location == "Mohali · Remote (India)"


def test_posted_date_parsing():
    job = parse_opportunity({"id": 1, "title": "SDE Intern", "organisation": {"name": "Acme"},
                             "seo_url": "https://unstop.com/internships/sde-1", "approved_date": "2026-09-13 19:35:50 GMT+0530"})
    assert job.posted_at.isoformat() == "2026-09-13T19:35:50+05:30"
    assert job.category == "Software Engineering"


def test_compensation():
    base = {"id": 1, "title": "Intern", "organisation": {"name": "A"}, "seo_url": "https://unstop.com/internships/x"}
    job = parse_opportunity({**base, "jobDetail": {"show_salary": 1, "paid_unpaid": "paid", "min_salary": 2000, "max_salary": 19500}})
    assert job.compensation == "₹2,000 – ₹19,500"
    assert parse_opportunity({**base, "jobDetail": {"show_salary": 0, "min_salary": 5}}).compensation is None


@pytest.mark.parametrize("raw", [
    None, {}, {"id": "1", "title": "x", "organisation": {"name": "A"}, "seo_url": "https://unstop.com/x"},  # id must be int
    {"id": 1, "title": "x", "organisation": {}, "seo_url": "https://unstop.com/x"},
    {"id": 1, "title": "x", "organisation": {"name": "A"}, "seo_url": "https://evil.example/x", "public_url": "../../x?y"},
])
def test_malformed(raw):
    assert parse_opportunity(raw) is None


def page(n, last, items):
    return {"data": {"current_page": n, "last_page": last, "data": items}}


def test_reads_every_page_up_to_the_limit():
    requested = []

    def handler(request):
        n = int(request.url.params["page"])
        requested.append(n)
        return httpx.Response(200, json=page(n, 5, [dict(PAGE["data"]["data"][0], id=n)]))

    source = UnstopSource(max_pages=3, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)
    result = source.fetch_jobs()
    assert requested == [1, 2, 3] and len(result.jobs) == 3


def test_failure_mid_way_keeps_earlier_pages():
    def handler(request):
        n = int(request.url.params["page"])
        return httpx.Response(200, json=page(n, 3, [dict(PAGE["data"]["data"][0], id=n)])) if n == 1 else httpx.Response(503)

    result = UnstopSource(client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None).fetch_jobs()
    assert len(result.jobs) == 1 and "HTTP 503" in result.errors[0]


def test_nothing_fetched_raises():
    with pytest.raises(SourceError, match="unexpected response shape"):
        UnstopSource(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"x": 1}))),
                     sleep=lambda s: None).fetch_jobs()
