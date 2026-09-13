import json
from pathlib import Path

import httpx
import pytest

from app.sources.base import SourceError
from app.sources.wellfound import WellfoundSource, parse_listing, parse_search_page

FIXTURE = (Path(__file__).parent / "fixtures" / "wellfound_search_page.html").read_text(encoding="utf-8")


def page_with(apollo: dict) -> str:
    payload = {"props": {"pageProps": {"apolloState": {"data": apollo}}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'


def test_parses_real_page_fixture():
    jobs, skipped = parse_search_page(FIXTURE)
    assert skipped == 0
    assert len(jobs) == 9
    first = next(j for j in jobs if j.external_id == "3315160")
    assert first.company == "Acuver Consulting"
    assert first.title == "Software Engineer"
    assert first.url == "https://wellfound.com/jobs/3315160-software-engineer"
    assert first.location == "Bengaluru"
    assert first.is_remote is False
    assert first.job_type == "Full-time"
    assert first.category == "Software Engineering"
    assert first.posted_at is not None and first.posted_at.tzinfo is not None
    assert "&amp;" not in (first.description or "")


def test_remote_region_is_kept_in_location():
    jobs, _ = parse_search_page(FIXTURE)
    india = next(j for j in jobs if j.external_id == "4587537")
    assert india.location.endswith("Remote (India)")
    assert india.is_remote


def test_explicit_onsite_config_wins_over_remote_region_list():
    job = parse_listing({"id": "1", "title": "Engineer", "remote": False, "locationNames": ["Pune"],
                         "remoteConfig": {"kind": "ONSITE"}, "acceptedRemoteLocationNames": ["India"]}, "Acme")
    assert job.is_remote is False and job.location == "Pune"


def test_computer_vision_title_classified():
    jobs, _ = parse_search_page(FIXTURE)
    assert next(j for j in jobs if j.external_id == "255384").category == "Computer Vision"


@pytest.mark.parametrize("raw", [
    None, "string", [], {},
    {"id": "1"},                                  # no title
    {"id": None, "title": "Engineer"},            # no id
    {"id": True, "title": "Engineer"},            # bool is not an id
    {"id": "1", "title": "   "},                  # blank title
])
def test_malformed_listing_is_rejected(raw):
    assert parse_listing(raw, "Company") is None


def test_listing_without_company_is_rejected():
    assert parse_listing({"id": "1", "title": "Engineer"}, None) is None


def test_missing_optional_fields_are_tolerated():
    job = parse_listing({"id": 77, "title": "Backend Intern", "remoteConfig": None, "liveStartAt": "yesterday",
                         "locationNames": "not-a-list", "slug": "../../evil"}, "Acme")
    assert job is not None
    assert job.external_id == "77"
    assert job.posted_at is None
    assert job.location is None
    assert job.url == "https://wellfound.com/jobs/77"  # unsafe slug dropped
    assert job.job_type == "Internship"


def test_page_mixing_good_and_malformed_records_counts_skips():
    apollo = {
        "StartupResult:1": {"name": "Acme", "highlightedJobListings": [{"__ref": "JobListingSearchResult:a"},
                                                                       {"__ref": "JobListingSearchResult:b"}]},
        "JobListingSearchResult:a": {"id": "a", "title": "ML Engineer"},
        "JobListingSearchResult:b": {"id": "b"},
        "JobListingSearchResult:orphan": {"id": "c", "title": "No company"},
    }
    jobs, skipped = parse_search_page(page_with(apollo))
    assert [j.external_id for j in jobs] == ["a"]
    assert skipped == 2


@pytest.mark.parametrize("html", [
    "<html>Just a moment...</html>",
    '<script id="__NEXT_DATA__">{not json</script>',
    '<script id="__NEXT_DATA__">{"props": {}}</script>',
    '<script id="__NEXT_DATA__">{"props": {"pageProps": {"apolloState": {"data": []}}}}</script>',
])
def test_unrecognizable_page_raises_source_error(html):
    with pytest.raises(SourceError):
        parse_search_page(html)


def make_source(handler, paths=("p1", "p2")):
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    sleeps = []
    return WellfoundSource(list(paths), request_delay_seconds=3, client=client, sleep=sleeps.append), sleeps


def test_fetch_pauses_between_pages_and_combines_results():
    source, sleeps = make_source(lambda request: httpx.Response(200, text=FIXTURE))
    result = source.fetch_jobs()
    assert len(result.jobs) == 18  # same page twice; dedup is the pipeline's job, not the adapter's
    assert sleeps == [3]
    assert result.errors == []


def test_partial_failure_returns_jobs_and_errors():
    def handler(request):
        if request.url.path == "/p1":
            return httpx.Response(303, headers={"location": "https://wellfound.com/location/bangalore"})
        return httpx.Response(200, text=FIXTURE)

    result = make_source(handler)[0].fetch_jobs()
    assert len(result.jobs) == 9
    assert len(result.errors) == 1 and "redirected" in result.errors[0]


def test_total_failure_raises():
    source, _ = make_source(lambda request: httpx.Response(403))
    with pytest.raises(SourceError, match="403"):
        source.fetch_jobs()


def test_network_error_raises():
    def handler(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(SourceError, match="request failed"):
        make_source(handler)[0].fetch_jobs()


def test_rate_limit_stops_remaining_pages():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(429)

    with pytest.raises(SourceError, match="429"):
        make_source(handler, paths=("p1", "p2", "p3"))[0].fetch_jobs()
    assert calls == ["/p1"]
