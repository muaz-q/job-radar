"""Fingerprinting and new-job detection.

Two identities are computed for every job:

fingerprint  -- "is this the same posting?"
    source + external_id when the source gives one, else source + canonical URL,
    else source + company/title/location. External ids survive title edits and URL
    slug changes, so they are preferred.

content_key  -- "is this the same opening?"
    company + title + location, normalized, WITHOUT the source. Catches the same
    job reposted under a new id, or listed on two sources. Trade-off: two genuinely
    separate openings with identical company, title and location collapse into one
    alert. For an alerting tool that is the right side to err on.

A job is new only if neither identity has been seen before.
"""

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job
from app.normalize import canonical_url, identity_company, identity_location, identity_text
from app.sources.base import NormalizedJob


def _sha256(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def content_key(job: NormalizedJob) -> str:
    return _sha256(identity_company(job.company), identity_text(job.title), identity_location(job.location))


def fingerprint(job: NormalizedJob) -> str:
    source = job.source.lower()
    if job.external_id and job.external_id.strip():
        return _sha256(source, "id", job.external_id.strip().lower())
    url = canonical_url(job.url)
    if url:
        return _sha256(source, "url", url)
    return _sha256(source, "content", content_key(job))


@dataclass
class DedupResult:
    new_jobs: list[tuple[NormalizedJob, str, str]]  # (job, fingerprint, content_key)
    duplicates: int


def find_new_jobs(session: Session, jobs: list[NormalizedJob]) -> DedupResult:
    """Split fetched jobs into unseen ones and duplicates (of the DB or of each other)."""
    keyed = [(job, fingerprint(job), content_key(job)) for job in jobs]
    fingerprints = {fp for _, fp, _ in keyed}
    content_keys = {ck for _, _, ck in keyed}

    known_fingerprints = set(session.scalars(select(Job.fingerprint).where(Job.fingerprint.in_(fingerprints))))
    known_content = set(session.scalars(select(Job.content_key).where(Job.content_key.in_(content_keys))))

    new_jobs, duplicates = [], 0
    for job, fp, ck in keyed:
        if fp in known_fingerprints or ck in known_content:
            duplicates += 1
            continue
        known_fingerprints.add(fp)  # same job twice in one batch (e.g. listed on two search pages)
        known_content.add(ck)
        new_jobs.append((job, fp, ck))
    return DedupResult(new_jobs=new_jobs, duplicates=duplicates)
