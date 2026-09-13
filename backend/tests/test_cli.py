"""The GitHub Actions scanner path: config files -> scan -> export -> deliver."""

import json
from pathlib import Path

import pytest

from app import cli
from app.config import REPO_ROOT, Config
from app.sources import build_sources
from app.sources.settings_file import load_sources_file
from tests.conftest import FakeSource, make_job


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"locations": ["Bengaluru"], "job_types": ["Internship"], "categories": [],
                                    "keywords": [], "max_age_days": None, "browser_notifications": True}))
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"mock": {"enabled": True}}))
    fake = FakeSource(jobs=[make_job(1), make_job(2, job_type="Full-time")])
    monkeypatch.setattr(cli, "build_sources", lambda config, file: [fake])
    monkeypatch.setattr(cli, "get_config", lambda: Config(_env_file=None, notify_channels="telegram"))
    return {"state": tmp_path / "state", "settings": settings, "sources": sources, "fake": fake}


def run(workspace, command):
    return cli.main([command, "--state-dir", str(workspace["state"]),
                     "--settings", str(workspace["settings"]), "--sources", str(workspace["sources"])])


def read(workspace, name):
    return json.loads((workspace["state"] / "public" / name).read_text(encoding="utf-8"))


def test_scan_exports_dashboard_files(workspace):
    assert run(workspace, "scan") == 0
    jobs = {j["title"]: j for j in read(workspace, "jobs.json")["jobs"]}
    matching, other = jobs["Backend Engineer Intern 1"], jobs["Backend Engineer Intern 2"]
    assert matching["matches_filters"] and not other["matches_filters"]
    assert matching["location_tags"] == ["Bengaluru"]
    assert matching["description"] == "Python APIs" and other["description"] is None

    meta = read(workspace, "meta.json")
    assert meta["settings"]["locations"] == ["Bengaluru"] and meta["scan_interval_minutes"] == 60
    assert "Computer Vision" in meta["options"]["categories"]
    assert read(workspace, "sources.json")[0]["status"] == "ok"
    notifications = read(workspace, "notifications.json")
    assert [(n["channel"], n["status"]) for n in notifications] == [("telegram", "pending")]


def test_state_persists_between_runs(workspace):
    run(workspace, "scan")
    workspace["fake"].jobs.append(make_job(3))
    run(workspace, "scan")
    assert len(read(workspace, "notifications.json")) == 2  # job 1 not re-announced
    assert len(read(workspace, "jobs.json")["jobs"]) == 3


def test_deliver_without_credentials_keeps_pending_and_succeeds(workspace, capsys):
    run(workspace, "scan")
    assert run(workspace, "deliver") == 0
    assert "telegram delivery failed" in capsys.readouterr().out
    assert read(workspace, "notifications.json")[0]["status"] == "pending"


def test_invalid_settings_file_fails_loudly(workspace):
    workspace["settings"].write_text('{"locations": ["Mars"]}')
    assert run(workspace, "scan") == 2
    assert not (workspace["state"] / "public").exists()


def test_repo_config_files_are_valid():
    """The committed config/ files must always load (the Actions scan depends on them)."""
    cli.load_settings_file(REPO_ROOT / "config" / "settings.json")
    sources = build_sources(Config(_env_file=None), load_sources_file(REPO_ROOT / "config" / "sources.json"))
    assert {s.name for s in sources} == {"wellfound", "companies", "unstop"}


def test_enabled_sources_override(tmp_path):
    file = load_sources_file(REPO_ROOT / "config" / "sources.json")
    assert [s.name for s in build_sources(Config(_env_file=None, enabled_sources="mock"), file)] == ["mock"]
    with pytest.raises(ValueError):
        build_sources(Config(_env_file=None, enabled_sources="linkedin"), file)


def test_frontend_options_match_backend():
    """The Vercel settings function validates with its own copy of the options."""
    js = (REPO_ROOT / "frontend" / "api" / "_options.js").read_text(encoding="utf-8")
    options = json.loads(js.split("OPTIONS =", 1)[1].strip().rstrip(";"))
    from app.schemas import CATEGORY_OPTIONS, JOB_TYPE_OPTIONS, LOCATION_OPTIONS
    assert options == {"locations": list(LOCATION_OPTIONS), "job_types": list(JOB_TYPE_OPTIONS),
                       "categories": list(CATEGORY_OPTIONS)}
