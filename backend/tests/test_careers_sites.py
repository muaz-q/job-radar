"""Workday, Amazon and Microsoft careers sites, tested against saved real responses."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app.filters import matches_location
from app.sources.careers_sites import (
    microsoft_location, parse_amazon, parse_microsoft, parse_workday_posted, parse_workday_posting,
    workday_location_groups,
)
from app.sources.companies import CompaniesSource
from app.sources.settings_file import Board

FIXTURES = Path(__file__).parent / "fixtures"
load = lambda name: json.loads((FIXTURES / name).read_text(encoding="utf-8"))

SALESFORCE = Board(ats="workday", slug="salesforce", name="Salesforce", host="salesforce.wd12", site="External_Career_Site")
AMAZON = Board(ats="amazon", slug="amazon", name="Amazon")
MICROSOFT = Board(ats="microsoft", slug="microsoft", name="Microsoft", queries=["intern"])
NOW = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------- Workday

@pytest.mark.parametrize("text,days", [
    ("Posted Today", 0), ("Posted Yesterday", 1), ("Posted 3 Days Ago", 3),
])
def test_workday_relative_dates(text, days):
    assert parse_workday_posted(text, NOW) == NOW - timedelta(days=days)


def test_workday_unknown_date_text():
    # "30+" hides the real date; found live hiding Salesforce's open Summer 2027 SWE intern role.
    assert parse_workday_posted("Posted 30+ Days Ago", NOW) is None
    assert parse_workday_posted("Posted recently", NOW) is None
    assert parse_workday_posted(None, NOW) is None


def test_workday_queries_bengaluru_first_then_india():
    facets = [
        {"facetParameter": "locationMainGroup", "values": [
            {"descriptor": "India - Bangalore", "id": "blr", "count": 93},
            {"descriptor": "India - Bangalore - Remote", "id": "blr-remote", "count": 1},
            {"descriptor": "USA - California", "id": "ca", "count": 400},
        ]},
        {"facetParameter": "country", "values": [{"descriptor": "India", "id": "in", "count": 128}]},
    ]
    groups = workday_location_groups(facets)
    assert [(label, applied) for label, applied, _ in groups] == [
        ("India - Bangalore", {"locationMainGroup": ["blr"]}),
        ("India - Bangalore - Remote", {"locationMainGroup": ["blr-remote"]}),
        ("India", {"country": ["in"]}),
    ]
    assert groups[1][2] == "Bengaluru, India · Remote (India)"


def test_workday_nested_groups_use_their_own_parameter():
    """Real Autodesk structure: sending the outer name 'locationMainGroup' returned HTTP 400 live."""
    facets = [{"facetParameter": "locationMainGroup", "values": [
        {"facetParameter": "locationCountry", "descriptor": "Country", "values": [
            {"descriptor": "India", "id": "in"}, {"descriptor": "Taiwan", "id": "tw"}]},
        {"facetParameter": "locations", "descriptor": "City", "values": [
            {"descriptor": "AMER - United States - Indiana - Offsite/Home", "id": "indiana"},
            {"descriptor": "APAC - India - Bengaluru - Sunriver", "id": "blr"}]},
    ]}]
    groups = workday_location_groups(facets)
    assert [(applied, loc) for _, applied, loc in groups] == [
        ({"locations": ["blr"]}, "Bengaluru, India"),
        ({"locationCountry": ["in"]}, None),  # "Indiana" is not India
    ]


def test_workday_without_country_facet_selects_india_locations():
    facets = [{"facetParameter": "locationMainGroup", "values": [
        {"descriptor": "India, Bengaluru", "id": "b"}, {"descriptor": "India, Pune", "id": "p"},
        {"descriptor": "Taiwan, Taipei", "id": "t"}]}]
    groups = workday_location_groups(facets)
    assert groups[-1][1] == {"locationMainGroup": ["b", "p"]}


def test_workday_real_postings_from_bengaluru_query():
    raw = load("workday_jobs.json")["jobPostings"]
    jobs = [parse_workday_posting(r, SALESFORCE, "Bengaluru, India", NOW) for r in raw]
    assert all(jobs)
    job = jobs[0]
    assert job.external_id == "workday:salesforce:JR353962"
    assert job.url.startswith("https://salesforce.wd12.myworkdayjobs.com/External_Career_Site/job/")
    assert job.location == "Bengaluru, India · 5 locations"
    assert matches_location(job, "Bengaluru")
    assert job.posted_at == NOW - timedelta(days=2)


def test_workday_multi_city_posting_outside_bengaluru_query_does_not_claim_bengaluru():
    job = parse_workday_posting({"title": "Engineer", "externalPath": "/job/India---Pune/Engineer_JR1",
                                 "locationsText": "3 Locations", "bulletFields": ["JR1"]}, SALESFORCE, None, NOW)
    assert job.location == "India · 3 locations"
    assert not matches_location(job, "Bengaluru")


@pytest.mark.parametrize("raw", [
    None, {"title": "X"}, {"title": "X", "externalPath": "https://evil.example/job"},
    {"title": "", "externalPath": "/job/a/b_1"},
])
def test_workday_malformed_postings(raw):
    assert parse_workday_posting(raw, SALESFORCE, None, NOW) is None


def test_workday_board_needs_host_and_site():
    with pytest.raises(ValueError):
        Board(ats="workday", slug="salesforce")
    with pytest.raises(ValueError):
        Board(ats="workday", slug="x", host="evil.com/../", site="Ext")


# ---------------------------------------------------------------- Amazon

def test_amazon_real_fixture():
    jobs = [parse_amazon(r, AMAZON) for r in load("amazon_search.json")["jobs"]]
    assert all(jobs)
    job = jobs[0]
    assert job.external_id.startswith("amazon:")
    assert job.url.startswith("https://www.amazon.jobs/en/jobs/")
    assert job.location.endswith("India") and "IND" not in job.location
    assert job.posted_at.year == 2026
    assert all(matches_location(j, "Bengaluru") for j in jobs if "Bengaluru" in j.location)


def test_amazon_intern_and_double_space_date():
    job = parse_amazon({"id_icims": "1", "title": "SDE Intern", "job_path": "/en/jobs/1/sde-intern",
                        "normalized_location": "Bengaluru, Karnataka, IND", "posted_date": "September  2, 2026",
                        "job_schedule_type": "full-time", "job_category": "Software Development"}, AMAZON)
    assert job.job_type == "Internship"
    assert job.posted_at == datetime(2026, 9, 2, tzinfo=timezone.utc)
    assert job.category == "Software Engineering"


@pytest.mark.parametrize("raw", [None, {"title": "X", "job_path": "/en/jobs/1"}, {"id": 1, "title": "X", "job_path": "javascript:x"}])
def test_amazon_malformed(raw):
    assert parse_amazon(raw, AMAZON) is None


# ---------------------------------------------------------------- Microsoft

def test_microsoft_real_fixture_includes_multi_location_india_internships():
    jobs = [parse_microsoft(r, MICROSOFT) for r in load("microsoft_search.json")["data"]["positions"]]
    assert all(jobs)
    swe = next(j for j in jobs if j.title == "Software Engineering INTERN")
    assert swe.job_type == "Internship"
    assert swe.location == "India · Multiple locations"
    assert matches_location(swe, "Bengaluru")  # unspecified Indian cities are not silently dropped
    assert swe.url.startswith("https://apply.careers.microsoft.com/careers/job/")


@pytest.mark.parametrize("raw,expected", [
    (["India, Karnataka, Bangalore"], "Bangalore, Karnataka, India"),
    (["India, Multiple Locations, Multiple Locations"], "India · Multiple locations"),
    (["India, Telangana, Hyderabad", "India, Karnataka, Bangalore"], "Hyderabad, Telangana, India · Bangalore, Karnataka, India"),
    ([], None),
    ("not-a-list", None),
])
def test_microsoft_location(raw, expected):
    assert microsoft_location(raw) == expected


def test_microsoft_malformed():
    assert parse_microsoft({"name": "X", "positionUrl": "https://evil.example"}, MICROSOFT) is None


def test_query_validation():
    with pytest.raises(ValueError):
        Board(ats="microsoft", slug="microsoft", queries=["intern&location=US"])


# ---------------------------------------------------------------- through the companies source

def make_source(handler, boards):
    return CompaniesSource(boards, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)


def test_workday_fetch_pages_bengaluru_then_india():
    calls = []
    posting = load("workday_jobs.json")["jobPostings"][0]

    def handler(request):
        body = json.loads(request.content)
        calls.append((body["appliedFacets"], body["offset"]))
        if body["appliedFacets"] == {} and body["limit"] == 20 and body["offset"] == 0 and len(calls) == 1:
            return httpx.Response(200, json={"total": 1, "jobPostings": [], "facets": [
                {"facetParameter": "locationMainGroup", "values": [{"descriptor": "India - Bangalore", "id": "blr"}]},
                {"facetParameter": "country", "values": [{"descriptor": "India", "id": "in"}]}]})
        if body["appliedFacets"] == {"locationMainGroup": ["blr"]}:
            return httpx.Response(200, json={"total": 1, "jobPostings": [posting]})
        return httpx.Response(200, json={"total": 1, "jobPostings": [posting]})

    result = make_source(handler, [SALESFORCE]).fetch_jobs()
    assert [applied for applied, _ in calls] == [{}, {"locationMainGroup": ["blr"]}, {"country": ["in"]}]
    assert [j.location for j in result.jobs] == ["Bengaluru, India · 5 locations", "India · 5 locations"]


def test_workday_keeps_paging_when_later_pages_report_total_zero():
    """Real Workday behaviour: page 1 says total=45, pages 2+ say total=0."""
    posting = load("workday_jobs.json")["jobPostings"][0]
    offsets = []

    def handler(request):
        body = json.loads(request.content)
        if body["appliedFacets"] == {} and not offsets:
            offsets.append("facets")
            return httpx.Response(200, json={"total": 45, "jobPostings": [], "facets": [
                {"facetParameter": "country", "values": [{"descriptor": "India", "id": "in"}]}]})
        offsets.append(body["offset"])
        count = 20 if body["offset"] < 40 else 5
        return httpx.Response(200, json={"total": 45 if body["offset"] == 0 else 0,
                                         "jobPostings": [dict(posting, bulletFields=[f"JR{body['offset']}-{i}"]) for i in range(count)]})

    result = make_source(handler, [SALESFORCE]).fetch_jobs()
    assert offsets == ["facets", 0, 20, 40]
    assert len(result.jobs) == 45


def test_microsoft_rate_limit_is_a_warning_and_other_companies_still_work():
    def handler(request):
        if "microsoft" in request.url.host:
            return httpx.Response(429, text="Please try again later")
        return httpx.Response(200, json=load("amazon_search.json"))

    result = make_source(handler, [MICROSOFT, AMAZON]).fetch_jobs()
    assert len(result.jobs) == len(load("amazon_search.json")["jobs"])
    assert result.errors == ["microsoft: HTTP 429 rate limited; skipped until the next scan"]


def test_parser_bug_in_one_company_is_contained(monkeypatch):
    from app.sources import careers_sites

    def broken(*args, **kwargs):
        raise KeyError("surprise")

    monkeypatch.setitem(careers_sites.FETCHERS, "amazon", broken)
    result = make_source(lambda r: httpx.Response(200, json=load("greenhouse_groww.json")),
                         [AMAZON, Board(ats="greenhouse", slug="groww")]).fetch_jobs()
    assert result.errors == ["amazon/amazon: unexpected KeyError"]
    assert len(result.jobs) == 5
