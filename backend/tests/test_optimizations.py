"""Parallel fetching and reworded cross-site duplicates (2026-09-14 optimization pass)."""

import threading
import time
from datetime import timedelta

import httpx
import pytest

from app.database import utcnow
from app.dedup import LocationProfile, find_new_jobs, opening_signature
from app.models import Job
from app.scanner import Scanner
from app.sources.base import FetchResult, JobSource
from app.sources.companies import CompaniesSource, website
from app.sources.settings_file import Board
from tests.conftest import FakeSource, make_job


# ---------------------------------------------------------------- reworded duplicates, from real alerts

REAL_PAIRS = [
    # (official careers site, Unstop) - each pair produced two Telegram alerts before this change
    (("Salesforce", "Summer 2027 Intern - Software Engineer", "Bengaluru, India · 2 locations"),
     ("Salesforce", "Software Engineer - Summer Internship 2027", "Hyderabad · Bangalore")),
    (("Microsoft", "Software Engineering INTERN", "India · Multiple locations"),
     ("Microsoft", "Software Engineering Internship", "Remote (India)")),
    (("NVIDIA", "PhD Intern, AI ML in Wireless L1/L2 - Fall 2026", "Bengaluru, India"),
     ("NVIDIA Corporation", "AI ML in Wireless L1/L2 PhD Internship", "Bangalore")),
    (("Rubrik", "Software Engineer - Winter Intern", "Bangalore"),
     ("Rubrik Inc", "Software Engineer Internship", "Bangalore")),
]


def store(db, *jobs, days_ago=0):
    from app.dedup import content_key, fingerprint
    from app.scanner import _to_model
    with db.session() as session:
        session.add_all(_to_model(j, fingerprint(j), content_key(j), True, utcnow() - timedelta(days=days_ago)) for j in jobs)
        session.commit()


@pytest.mark.parametrize("official,aggregator", REAL_PAIRS)
def test_real_reworded_pairs_are_one_opening(db, official, aggregator):
    store(db, make_job("a", source="companies", company=official[0], title=official[1], location=official[2]))
    with db.session() as session:
        result = find_new_jobs(session, [make_job("b", source="unstop", company=aggregator[0], title=aggregator[1],
                                                  location=aggregator[2])])
    assert result.new_jobs == [] and result.similar == 1


def test_internship_never_merges_into_full_time_role(db):
    store(db, make_job("ft", source="companies", company="Stripe", title="Software Engineer", job_type="Full-time"))
    with db.session() as session:
        result = find_new_jobs(session, [make_job("in", source="unstop", company="Stripe", title="Software Engineer, Intern",
                                                  job_type="Internship")])
    assert len(result.new_jobs) == 1


def test_different_specific_cities_stay_separate(db):
    store(db, make_job("a", source="companies", company="Acme", title="Backend Engineer Intern", location="Hyderabad"))
    with db.session() as session:
        result = find_new_jobs(session, [make_job("b", source="unstop", company="Acme", title="Backend Engineer Internship",
                                                  location="Pune")])
    assert len(result.new_jobs) == 1


def test_different_title_words_stay_separate(db):
    store(db, make_job("a", source="companies", company="Rubrik", title="Software Engineer - Winter Intern"))
    with db.session() as session:
        result = find_new_jobs(session, [make_job("b", source="unstop", company="Rubrik", title="Software Engineer (CPD) - Winter Intern")])
    assert len(result.new_jobs) == 1


def test_different_companies_stay_separate(db):
    store(db, make_job("a", source="companies", company="Acme", title="ML Engineer Intern"))
    with db.session() as session:
        result = find_new_jobs(session, [make_job("b", source="unstop", company="Globex", title="ML Engineer Intern")])
    assert len(result.new_jobs) == 1


def test_openings_older_than_the_window_can_be_announced_again(db):
    store(db, make_job("a", source="companies", company="Acme", title="ML Engineer Intern"), days_ago=200)
    with db.session() as session:
        result = find_new_jobs(session, [make_job("b", source="unstop", company="Acme", title="ML Engineering Internship 2027")])
    assert len(result.new_jobs) == 1


def test_same_site_postings_with_distinct_ids_are_never_merged(db):
    """Replaying live history: NVIDIA/Paytm post one title as separate per-city jobs on the same site."""
    store(db, make_job("hyd", source="companies", company="NVIDIA", title="Senior Verification Engineer - Hardware",
                       location="India · 2 locations"))
    with db.session() as session:
        result = find_new_jobs(session, [make_job("blr", source="companies", company="NVIDIA",
                                                  title="Senior Verification Engineer - Hardware",
                                                  location="Bengaluru, India · 2 locations")])
    assert len(result.new_jobs) == 1 and result.similar == 0


def test_reworded_copy_from_another_site_inside_one_batch(db):
    with db.session() as session:
        result = find_new_jobs(session, [make_job("a", source="wellfound", company="Abstrabit Technologies", title="AI Engineer Intern"),
                                         make_job("b", source="unstop", company="Abstrabit Technologies", title="AI Engineer Internship")])
    assert len(result.new_jobs) == 1 and result.similar == 1


@pytest.mark.parametrize("title", ["Intern", "Internship 2027", "Engineer", ""])
def test_too_generic_titles_are_not_compared(title):
    assert opening_signature("Acme", title, "Internship") is None


def test_location_profiles():
    assert LocationProfile.of("Bangalore").cities == {"bengaluru"}
    assert not LocationProfile.of("Hyderabad").compatible(LocationProfile.of("Pune"))
    assert LocationProfile.of("Hyderabad · Bangalore").compatible(LocationProfile.of("Bengaluru, India"))
    assert LocationProfile.of("India · Multiple locations").compatible(LocationProfile.of("Pune"))
    assert LocationProfile.of(None).vague


def test_scanner_prefers_the_official_listing_when_both_arrive_in_one_scan(db, open_settings):
    official = FakeSource(jobs=[make_job("sf", source="companies", company="Salesforce",
                                         title="Summer 2027 Intern - Software Engineer", location="Bengaluru, India",
                                         url="https://salesforce.example/job")])
    official.name = "companies"
    aggregator = FakeSource(jobs=[make_job("un", source="unstop", company="Salesforce",
                                           title="Software Engineer - Summer Internship 2027", location="Bangalore",
                                           url="https://unstop.example/job")])
    aggregator.name = "unstop"
    summary = Scanner(db, [official, aggregator]).scan()
    assert [(s.source, s.new, s.notifications) for s in summary.sources] == [("companies", 1, 1), ("unstop", 0, 0)]
    with db.session() as session:
        assert [j.url for j in session.query(Job)] == ["https://salesforce.example/job"]


# ---------------------------------------------------------------- parallel fetching

class BlockingSource(JobSource):
    """Finishes only after every other BlockingSource has started: deadlocks if fetched one by one."""

    display_name = "Blocking"

    def __init__(self, name, barrier, jobs):
        self.name = name
        self.barrier = barrier
        self.jobs = jobs

    def fetch_jobs(self):
        self.barrier.wait(timeout=5)  # raises BrokenBarrierError on timeout -> recorded as a failure
        return FetchResult(jobs=self.jobs)


def test_sources_are_fetched_at_the_same_time(db, open_settings):
    barrier = threading.Barrier(3)
    sources = [BlockingSource(f"s{i}", barrier, [make_job(i, source=f"s{i}")]) for i in range(3)]
    started = time.monotonic()
    summary = Scanner(db, sources).scan()
    assert time.monotonic() - started < 4
    assert [(s.source, s.status, s.new) for s in summary.sources] == [("s0", "ok", 1), ("s1", "ok", 1), ("s2", "ok", 1)]


def test_one_slow_or_failing_source_does_not_change_the_others(db, open_settings):
    from tests.conftest import SourceError
    broken = FakeSource(error=SourceError("down"))
    broken.name = "broken"
    healthy = FakeSource(jobs=[make_job(1)])
    summary = Scanner(db, [broken, healthy]).scan()
    assert [(s.source, s.status) for s in summary.sources] == [("broken", "error"), ("fake", "ok")]


def test_boards_on_different_websites_run_in_parallel_but_same_website_is_sequential():
    active, peak, per_host_active, lock = 0, 0, {}, threading.Lock()
    overlap_on_same_host = []

    def handler(request):
        nonlocal active, peak
        host = request.url.host
        with lock:
            active += 1
            peak = max(peak, active)
            per_host_active[host] = per_host_active.get(host, 0) + 1
            if per_host_active[host] > 1:
                overlap_on_same_host.append(host)
        time.sleep(0.2)
        with lock:
            active -= 1
            per_host_active[host] -= 1
        return httpx.Response(200, json={"jobs": []} if "greenhouse" in host or "ashby" in host else [])

    boards = [Board(ats="greenhouse", slug="a"), Board(ats="greenhouse", slug="b"),
              Board(ats="lever", slug="c"), Board(ats="ashby", slug="d")]
    source = CompaniesSource(boards, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)
    source.fetch_jobs()
    assert peak >= 2                   # different websites overlapped
    assert overlap_on_same_host == []  # never two requests at once to the same website


def test_results_keep_configured_order_and_errors_whatever_finishes_first():
    def handler(request):
        if "lever" in request.url.host:
            return httpx.Response(404)
        time.sleep(0.1 if "greenhouse" in request.url.host else 0)
        return httpx.Response(200, json={"jobs": []})

    boards = [Board(ats="greenhouse", slug="first"), Board(ats="lever", slug="second"), Board(ats="ashby", slug="third")]
    result = CompaniesSource(boards, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None).fetch_jobs()
    assert result.errors == ["lever/second: board not found (check the slug in config/sources.json)"]


def test_website_grouping():
    assert website(Board(ats="workday", slug="nvidia", host="nvidia.wd5", site="X")) == "nvidia.wd5.myworkdayjobs.com"
    assert website(Board(ats="greenhouse", slug="a")) == website(Board(ats="greenhouse", slug="b"))


def test_unstop_asks_for_100_per_page():
    from app.sources.unstop import UnstopSource
    seen = []

    def handler(request):
        seen.append(request.url.params["per_page"])
        return httpx.Response(200, json={"data": {"last_page": 1, "data": []}})

    UnstopSource(client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None).fetch_jobs()
    assert seen == ["100"]
