"""The pipeline end to end: new-job detection, filtering, notification selection, failures."""

from datetime import timedelta

from app.database import utcnow
from app.models import Job, Notification, SourceState
from app.notifications import BrowserChannel, NotificationService, build_message, relative_age
from app.schemas import SettingsIn
from app.settings_store import DEFAULT_SETTINGS, save_settings
from tests.conftest import FakeSource, SourceError, make_job


def counts(db):
    with db.session() as session:
        return session.query(Job).count(), session.query(Notification).count()


def test_first_second_third_scan(db, scanner, source, open_settings):
    source.jobs = [make_job(i) for i in range(50)]
    first = scanner.scan().sources[0]
    assert (first.fetched, first.new, first.notifications) == (50, 50, 50)

    source.jobs += [make_job(i) for i in range(50, 53)]
    second = scanner.scan().sources[0]
    assert (second.fetched, second.new, second.duplicates, second.notifications) == (53, 3, 50, 3)

    third = scanner.scan().sources[0]
    assert (third.fetched, third.new, third.notifications) == (53, 0, 0)
    assert counts(db) == (53, 53)


def test_only_matching_new_jobs_notify_but_all_are_remembered(db, scanner, source):
    with db.session() as session:
        save_settings(session, DEFAULT_SETTINGS)
    source.jobs = [
        make_job(1),                                    # Bengaluru internship, Backend -> match
        make_job(2, job_type="Full-time"),              # wrong type
        make_job(3, location="Remote (India)", is_remote=True, category="AI/ML"),  # match
        make_job(4, location="Mumbai"),                 # wrong location
        make_job(5, posted_at=utcnow() - timedelta(days=90)),  # too old
    ]
    summary = scanner.scan().sources[0]
    assert (summary.new, summary.matching, summary.notifications) == (5, 2, 2)

    with db.session() as session:
        notified = sorted(n.job.external_id for n in session.query(Notification))
        assert notified == ["ext-1", "ext-3"]
    assert counts(db) == (5, 2)


def test_widening_filters_never_renotifies_known_jobs(db, scanner, source):
    with db.session() as session:
        save_settings(session, DEFAULT_SETTINGS)
    source.jobs = [make_job(2, job_type="Full-time")]
    assert scanner.scan().sources[0].notifications == 0

    with db.session() as session:
        save_settings(session, DEFAULT_SETTINGS.model_copy(update={"job_types": ["Internship", "Full-time"]}))
    assert scanner.scan().sources[0].notifications == 0


def test_notifications_disabled_still_records_jobs(db, scanner, source):
    with db.session() as session:
        save_settings(session, SettingsIn(browser_notifications=False))
    source.jobs = [make_job(1)]
    summary = scanner.scan().sources[0]
    assert (summary.new, summary.matching, summary.notifications) == (1, 1, 0)


def test_source_failure_is_recorded_and_app_continues(db, open_settings):
    broken = FakeSource(error=SourceError("HTTP 403 access refused"))
    broken.name = "broken"
    healthy = FakeSource(jobs=[make_job(1)])
    from app.scanner import Scanner

    summary = Scanner(db, [broken, healthy]).scan()
    assert summary.sources[0].status == "error"
    assert summary.sources[1].new == 1

    with db.session() as session:
        state = session.get(SourceState, "broken")
        assert state.status == "error"
        assert state.consecutive_failures == 1
        assert "403" in state.last_error

    broken.error = None
    broken.jobs = [make_job(9, source="broken")]
    Scanner(db, [broken]).scan()
    with db.session() as session:
        state = session.get(SourceState, "broken")
        assert (state.status, state.consecutive_failures, state.last_error) == ("ok", 0, None)


def test_unexpected_adapter_exception_is_contained(db, open_settings):
    from app.scanner import Scanner

    summary = Scanner(db, [FakeSource(error=RuntimeError("boom"))]).scan()
    assert summary.sources[0].status == "error"
    assert "RuntimeError: boom" in summary.sources[0].errors[0]


def test_partial_errors_mark_warning(db, scanner, source, open_settings):
    source.jobs = [make_job(1)]
    source.errors = ["p2: redirected"]
    summary = scanner.scan().sources[0]
    assert summary.status == "warning" and summary.new == 1


def test_jobs_with_unsafe_urls_are_never_stored(db, scanner, source, open_settings):
    source.jobs = [make_job(1, url="javascript:alert(1)"), make_job(2, url="data:text/html,x"), make_job(3)]
    summary = scanner.scan().sources[0]
    assert (summary.new, summary.status) == (1, "warning")
    assert "2 job(s) with a non-http(s) URL skipped" in summary.errors


def test_broken_channel_does_not_block_other_channels(db, source, open_settings):
    class Exploding(BrowserChannel):
        name = "exploding"

        def send(self, session, job):
            raise RuntimeError("push service down")

    from app.scanner import Scanner

    source.jobs = [make_job(1)]
    summary = Scanner(db, [source], NotificationService([Exploding(), BrowserChannel()])).scan().sources[0]
    assert summary.notifications == 1


def test_message_is_minimal():
    now = utcnow()
    job = make_job(1, title="AI Engineer Intern", company="Nimbus", category="AI/ML",
                   posted_at=now - timedelta(minutes=12))
    heading, body = build_message(job, now)
    assert heading == "New AI/ML Internship"
    assert body == "AI Engineer Intern\nNimbus\nBengaluru\nPosted 12 min ago"

    heading, body = build_message(make_job(2, job_type="Full-time", category="Other", location=None,
                                           posted_at=None), now)
    assert heading == "New Job"
    assert body.endswith("Location not listed\nJust discovered")


def test_relative_age():
    now = utcnow()
    assert relative_age(now, now) == "just now"
    assert relative_age(now - timedelta(hours=1), now) == "1 hour ago"
    assert relative_age(now - timedelta(days=3), now) == "3 days ago"
    assert relative_age(None, now) is None
