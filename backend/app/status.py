"""Read-side helpers shared by the REST API and the static JSON export."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Job, SourceState
from app.schemas import SourceOut
from app.sources import KNOWN_SOURCES

_OLDEST = datetime.min.replace(tzinfo=timezone.utc)


def job_sort_key(job: Job):
    """Newest discoveries first; within one scan, most recently posted first."""
    return job.first_seen_at, job.posted_at or _OLDEST, job.id


def source_statuses(session: Session, enabled: list[str], running: bool = False,
                    next_scan_at: datetime | None = None) -> list[SourceOut]:
    counts = dict(session.execute(select(Job.source, func.count()).group_by(Job.source)).all())
    states = {state.name: state for state in session.scalars(select(SourceState))}
    names = enabled + sorted((set(counts) | set(states)) - set(enabled))

    result = []
    for name in names:
        state = states.get(name)
        is_enabled = name in enabled
        result.append(SourceOut(
            name=name,
            display_name=KNOWN_SOURCES.get(name, name),
            enabled=is_enabled,
            status=("running" if running and is_enabled else state.status) if state else "idle",
            last_checked_at=state.last_checked_at if state else None,
            last_success_at=state.last_success_at if state else None,
            last_error=state.last_error if state else None,
            consecutive_failures=state.consecutive_failures if state else 0,
            last_fetched_count=state.last_fetched_count if state else 0,
            last_new_count=state.last_new_count if state else 0,
            total_jobs=counts.get(name, 0),
            next_scan_at=next_scan_at if is_enabled else None,
        ))
    return result
