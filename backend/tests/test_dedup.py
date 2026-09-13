from app.dedup import content_key, find_new_jobs, fingerprint
from app.models import Job
from app.scanner import _to_model
from app.database import utcnow
from tests.conftest import make_job


def store(db, jobs):
    with db.session() as session:
        session.add_all(_to_model(j, fingerprint(j), content_key(j), True, utcnow()) for j in jobs)
        session.commit()


def test_fingerprint_is_stable_and_prefers_external_id():
    job = make_job(1)
    assert fingerprint(job) == fingerprint(make_job(1))
    # Title edits and URL slug changes keep the same posting identity.
    assert fingerprint(job) == fingerprint(make_job(1, title="Renamed", url="https://other/1"))


def test_fingerprint_differs_across_sources_and_ids():
    assert fingerprint(make_job(1)) != fingerprint(make_job(2))
    assert fingerprint(make_job(1)) != fingerprint(make_job(1, source="other"))


def test_fingerprint_without_external_id_uses_canonical_url():
    a = make_job(1, external_id=None, url="https://www.jobs.example.com/1/?utm_source=mail")
    b = make_job(1, external_id=None, url="http://jobs.example.com/1", title="Different title")
    assert fingerprint(a) == fingerprint(b)


def test_fingerprint_without_id_or_url_uses_content():
    a = make_job(1, external_id=None, url="", location="Bangalore")
    b = make_job(1, external_id=None, url="", location="Bengaluru")
    assert fingerprint(a) == fingerprint(b)


def test_content_key_ignores_source_and_formatting():
    a = make_job(1, company="Acme Pvt Ltd", title="Backend  Intern", location="Bangalore")
    b = make_job(99, source="other", company="ACME", title="backend intern", location="Bengaluru")
    assert content_key(a) == content_key(b)


def test_missing_location_is_handled():
    assert content_key(make_job(1, location=None)) != content_key(make_job(1))


def test_ten_fetched_seven_known_three_new(db):
    fetched = [make_job(i) for i in range(10)]
    store(db, fetched[:7])
    with db.session() as session:
        result = find_new_jobs(session, fetched)
    assert [j.external_id for j, _, _ in result.new_jobs] == ["ext-7", "ext-8", "ext-9"]
    assert result.duplicates == 7


def test_same_url_different_formatting_is_duplicate(db):
    store(db, [make_job(1, external_id=None, url="https://jobs.example.com/a")])
    with db.session() as session:
        result = find_new_jobs(session, [make_job(1, external_id=None, url="HTTP://WWW.jobs.example.com/a/#top",
                                                  company="New Co", title="Changed")])
    assert result.new_jobs == [] and result.duplicates == 1


def test_repost_with_new_id_but_same_company_title_location_is_duplicate(db):
    store(db, [make_job(1)])
    with db.session() as session:
        result = find_new_jobs(session, [make_job(1, external_id="brand-new-id", url="https://x/new")])
    assert result.new_jobs == []


def test_same_title_at_different_companies_are_distinct(db):
    jobs = [make_job(i, title="Software Engineer") for i in range(3)]
    with db.session() as session:
        assert len(find_new_jobs(session, jobs).new_jobs) == 3


def test_duplicates_within_one_batch(db):
    with db.session() as session:
        result = find_new_jobs(session, [make_job(1), make_job(1), make_job(2)])
    assert len(result.new_jobs) == 2 and result.duplicates == 1


def test_empty_batch(db):
    with db.session() as session:
        result = find_new_jobs(session, [])
    assert result.new_jobs == [] and result.duplicates == 0
    assert session.query(Job).count() == 0
