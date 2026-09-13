"""Static JSON snapshot for the hosted dashboard.

GitHub Actions runs a scan, then writes these files; the Vercel dashboard reads them
straight from the repository. Everything the dashboard needs is precomputed here
(filter match flags, location tags), so filter rules exist only in Python.

  meta.json           when generated, scan interval, filter options, the settings used
  jobs.json           recent jobs, newest first
  notifications.json  alert history
  sources.json        source health
"""

import json
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import utcnow
from app.filters import FilterSettings, matches_filters, matches_location
from app.models import Job, Notification
from app.schemas import (
    CATEGORY_OPTIONS, JOB_TYPE_OPTIONS, LOCATION_OPTIONS, JobSummary, NotificationOut, SettingsOut,
)
from app.settings_store import get_settings
from app.status import job_sort_key, source_statuses

MAX_JOBS = 3000
JOB_WINDOW_DAYS = 60
MAX_NOTIFICATIONS = 500
DESCRIPTION_CHARS = 1500


def _write(path: Path, payload) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")
    tmp.replace(path)  # never leave a half-written file behind


def export_snapshot(session: Session, out_dir: Path, enabled_sources: list[str], scan_interval_minutes: int) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    now = utcnow()
    settings = get_settings(session)
    filters = FilterSettings.from_model(settings)

    recent = session.scalars(select(Job).where(Job.first_seen_at >= now - timedelta(days=JOB_WINDOW_DAYS)))
    jobs = sorted(recent, key=job_sort_key, reverse=True)[:MAX_JOBS]
    job_rows = []
    for job in jobs:
        matched = matches_filters(job, filters, now)
        row = JobSummary.model_validate(job).model_copy(update={"matches_filters": matched}).model_dump(mode="json")
        row["location_tags"] = [option for option in LOCATION_OPTIONS if matches_location(job, option)]
        # Descriptions only for matching jobs keeps the file small; the "View Job" link has the full text.
        row["description"] = (job.description or "")[:DESCRIPTION_CHARS] if matched and job.description else None
        job_rows.append(row)

    notifications = session.scalars(
        select(Notification).order_by(Notification.created_at.desc(), Notification.id.desc()).limit(MAX_NOTIFICATIONS)
    )
    next_scan_at = now + timedelta(minutes=scan_interval_minutes)
    meta = {
        "generated_at": now.isoformat(),
        "scan_interval_minutes": scan_interval_minutes,
        "options": {"locations": LOCATION_OPTIONS, "job_types": JOB_TYPE_OPTIONS, "categories": CATEGORY_OPTIONS},
        "settings": SettingsOut.model_validate(settings).model_dump(mode="json"),
    }
    _write(out_dir / "meta.json", meta)
    _write(out_dir / "jobs.json", {"generated_at": meta["generated_at"], "jobs": job_rows})
    _write(out_dir / "notifications.json", [NotificationOut.model_validate(n).model_dump(mode="json") for n in notifications])
    _write(out_dir / "sources.json", [s.model_dump(mode="json") for s in
                                      source_statuses(session, enabled_sources, next_scan_at=next_scan_at)])
    return {"jobs": len(job_rows), "matching": sum(r["matches_filters"] for r in job_rows)}
