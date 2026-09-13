from datetime import timedelta

from app.database import utcnow
from tests.conftest import SourceError, make_job


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_default_settings_and_options(client):
    settings = client.get("/settings").json()
    assert settings["locations"] == ["Bengaluru", "Remote India"]
    assert settings["job_types"] == ["Internship"]
    assert "Computer Vision" in client.get("/settings/options").json()["categories"]


def test_update_settings_sanitizes_and_persists(client):
    body = {"locations": ["Bengaluru", "Bengaluru"], "job_types": ["Full-time"], "categories": ["Data"],
            "keywords": ["  Python ", "PYTHON", "machine   learning", ""], "max_age_days": 7,
            "browser_notifications": False}
    saved = client.put("/settings", json=body).json()
    assert saved["locations"] == ["Bengaluru"]
    assert saved["keywords"] == ["python", "machine learning"]
    assert client.get("/settings").json() == saved


def test_update_settings_rejects_bad_input(client):
    for body in [
        {"locations": ["Mars"]},
        {"job_types": ["Volunteer"]},
        {"keywords": ["<script>"]},
        {"keywords": ["x" * 51]},
        {"keywords": ["k"] * 51},
        {"max_age_days": 0},
        {"unknown_field": 1},
    ]:
        assert client.put("/settings", json=body).status_code == 422, body


def test_scan_then_jobs_newest_first(client, source):
    now = utcnow()
    source.jobs = [make_job(1, posted_at=now - timedelta(hours=5)),
                   make_job(2, posted_at=now - timedelta(minutes=5)),
                   make_job(3, posted_at=None)]
    summary = client.post("/scan").json()["sources"][0]
    assert summary["new"] == 3

    items = client.get("/jobs").json()["items"]
    assert [j["external_id"] if "external_id" in j else j["title"] for j in items] == [
        "Backend Engineer Intern 2", "Backend Engineer Intern 1", "Backend Engineer Intern 3"]

    source.jobs.append(make_job(4))
    client.post("/scan")
    assert client.get("/jobs").json()["items"][0]["title"] == "Backend Engineer Intern 4"


def test_jobs_query_filters(client, source):
    source.jobs = [
        make_job(1, category="AI/ML", title="ML Intern"),
        make_job(2, location="Remote (India)", is_remote=True),
        make_job(3, source="fake", job_type="Full-time", company="Zeta 100%"),
    ]
    client.post("/scan")

    def titles(**params):
        return sorted(j["title"] for j in client.get("/jobs", params=params).json()["items"])

    assert titles(category="AI/ML") == ["ML Intern"]
    assert titles(location="Remote India") == ["Backend Engineer Intern 2"]
    assert titles(job_type="Full-time") == ["Backend Engineer Intern 3"]
    assert titles(q="ml intern") == ["ML Intern"]
    assert titles(q="100%") == ["Backend Engineer Intern 3"]     # % is literal, not a wildcard
    assert titles(q="%") == ["Backend Engineer Intern 3"]
    assert titles(source="nope") == []
    assert titles(matching="true") == ["Backend Engineer Intern 2", "ML Intern"]  # defaults: internships
    assert client.get("/jobs", params={"location": "Mars"}).status_code == 422
    assert client.get("/jobs", params={"limit": 1000}).status_code == 422


def test_pagination(client, source):
    source.jobs = [make_job(i) for i in range(5)]
    client.post("/scan")
    page = client.get("/jobs", params={"limit": 2, "offset": 4}).json()
    assert page["total"] == 5 and len(page["items"]) == 1


def test_job_detail_and_404(client, source):
    source.jobs = [make_job(1)]
    client.post("/scan")
    job_id = client.get("/jobs").json()["items"][0]["id"]
    detail = client.get(f"/jobs/{job_id}").json()
    assert detail["description"] == "Python APIs"
    assert detail["posted_at"] and detail["first_seen_at"]
    assert client.get("/jobs/99999").status_code == 404
    assert client.get("/jobs/abc").status_code == 422


def test_notifications_flow(client, source):
    source.jobs = [make_job(1), make_job(2)]
    client.post("/scan")
    pending = client.get("/notifications", params={"status": "pending"}).json()
    assert len(pending) == 2
    assert pending[0]["url"].startswith("https://")

    assert client.post("/notifications/mark-delivered", json={"ids": [pending[0]["id"]]}).json() == {"updated": 1}
    assert len(client.get("/notifications", params={"status": "pending"}).json()) == 1
    delivered = client.get("/notifications", params={"status": "delivered"}).json()
    assert delivered[0]["delivered_at"] is not None

    client.post("/scan")  # nothing new -> no new notifications
    assert len(client.get("/notifications").json()) == 2
    assert client.post("/notifications/mark-delivered", json={"ids": []}).status_code == 422


def test_sources_reports_health(client, source):
    assert client.get("/sources").json()[0]["status"] == "idle"
    source.jobs = [make_job(1)]
    client.post("/scan")
    status = client.get("/sources").json()[0]
    assert (status["name"], status["status"], status["total_jobs"], status["last_fetched_count"]) == ("fake", "ok", 1, 1)

    source.error = SourceError("HTTP 403 access refused")
    assert client.post("/scan").status_code == 200  # a failing source is not an API failure
    status = client.get("/sources").json()[0]
    assert status["status"] == "error" and "403" in status["last_error"]
    assert status["total_jobs"] == 1  # previously found jobs are kept


def test_manual_scan_rate_guard(client, scanner):
    client.app.state.config.min_manual_scan_gap_seconds = 60
    assert client.post("/scan").status_code == 200
    response = client.post("/scan")
    assert response.status_code == 429 and "Retry-After" in response.headers


def test_concurrent_scan_rejected(client, scanner):
    scanner._lock.acquire()
    try:
        assert client.post("/scan").status_code == 409
    finally:
        scanner._lock.release()
