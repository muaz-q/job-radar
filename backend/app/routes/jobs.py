from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.filters import FilterSettings, matches_filters, matches_location
from app.models import Job
from app.routes.deps import get_session
from app.schemas import CategoryOption, JobDetail, JobList, JobSummary, JobTypeOption, LocationOption
from app.settings_store import get_settings
from app.status import job_sort_key

router = APIRouter(tags=["jobs"])


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/jobs", response_model=JobList)
def list_jobs(
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    source: Annotated[str | None, Query(max_length=50, pattern=r"^[a-z0-9_-]+$")] = None,
    location: LocationOption | None = None,
    category: CategoryOption | None = None,
    job_type: JobTypeOption | None = None,
    matching: bool = Query(False, description="Only jobs matching the saved settings filters"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(Job)
    if source:
        query = query.where(Job.source == source)
    if category:
        query = query.where(Job.category == category)
    if job_type:
        query = query.where(Job.job_type == job_type)
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        query = query.where(or_(Job.title.ilike(pattern, escape="\\"), Job.company.ilike(pattern, escape="\\")))

    jobs = list(session.scalars(query))
    # Location and saved-filter matching use the same Python rules as the scanner, so the
    # dashboard and the notifications can never disagree. Fine at personal-tool volumes.
    if location:
        jobs = [job for job in jobs if matches_location(job, location)]
    filters = FilterSettings.from_model(get_settings(session))
    flagged = [(job, matches_filters(job, filters)) for job in jobs]
    if matching:
        flagged = [(job, ok) for job, ok in flagged if ok]

    flagged.sort(key=lambda pair: job_sort_key(pair[0]), reverse=True)
    page = flagged[offset: offset + limit]
    items = [JobSummary.model_validate(job).model_copy(update={"matches_filters": ok}) for job, ok in page]
    return JobList(total=len(flagged), items=items)


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: int, session: Annotated[Session, Depends(get_session)]):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    ok = matches_filters(job, FilterSettings.from_model(get_settings(session)))
    return JobDetail.model_validate(job).model_copy(update={"matches_filters": ok})
