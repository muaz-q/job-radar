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

similar opening -- "is this the same job, reworded by another site?"
    Big companies post on their own careers site AND on aggregators, with rewritten titles
    and location formats: "Summer 2027 Intern - Software Engineer / Bengaluru, India · 2 locations"
    vs "Software Engineer - Summer Internship 2027 / Hyderabad · Bangalore". Measured on live
    data (2026-09-14): 4 of 115 alerts were such duplicates, all at target companies.
    Match = same company (ignoring "Corporation", "Inc"...) + same job type + the same set of
    meaningful title words (seasons, years and filler removed; "internship" == "intern", but
    intern-ness is KEPT so "Software Engineer, Intern" never merges into "Software Engineer")
    + compatible locations (a shared city, or one side vague: remote / multiple locations)
    + the earlier job was first seen within SIMILAR_WINDOW_DAYS
    + it came from a DIFFERENT source. Within one site, distinct ids are deliberate: replaying the
      live history showed NVIDIA and Paytm post the same title as separate per-city jobs, and
      merging those could hide a Bengaluru posting behind an earlier Hyderabad one.

A job is new only if none of these match.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import utcnow
from app.models import Job
from app.normalize import canonical_url, identity_company, identity_location, identity_text
from app.sources.base import NormalizedJob

SIMILAR_WINDOW_DAYS = 120

_TITLE_FILLER = {
    "the", "a", "an", "and", "or", "of", "in", "for", "to", "at", "with", "on", "position", "role", "opening",
    "program", "programme", "hiring", "urgent", "summer", "winter", "fall", "autumn", "spring", "remote", "hybrid",
}
_INTERN_WORDS = {"intern", "interns", "internship", "internships"}
_COMPANY_FILLER = re.compile(r"\b(corporation|incorporated|company|co|group|holdings|india)\b")
_CITIES = {"bengaluru", "hyderabad", "pune", "mumbai", "gurgaon", "gurugram", "delhi", "noida", "chennai",
           "kolkata", "ahmedabad", "jaipur", "kochi", "coimbatore", "indore", "chandigarh"}
_VAGUE_LOCATION = re.compile(r"\b(remote|multiple|locations?)\b")


def opening_signature(company: str | None, title: str | None, job_type: str | None) -> tuple[str, str, str] | None:
    """(company, job type, title words) or None when the title is too generic to compare safely."""
    company_key = " ".join(_COMPANY_FILLER.sub(" ", identity_company(company)).split())
    words = set()
    for word in identity_text(title).split():
        if word in _INTERN_WORDS:
            words.add("intern")
        elif word not in _TITLE_FILLER and not re.fullmatch(r"(19|20)\d\d", word):
            words.add(word)
    if not company_key or len(words - {"intern"}) < 2:
        return None  # "Intern" or "Engineer" alone would merge unrelated openings
    return company_key, job_type or "", " ".join(sorted(words))


@dataclass(frozen=True)
class LocationProfile:
    cities: frozenset[str] = field(default_factory=frozenset)
    vague: bool = True

    @classmethod
    def of(cls, location: str | None) -> "LocationProfile":
        text = identity_location(location)  # also maps Bangalore -> bengaluru
        cities = frozenset(word for word in text.split() if word in _CITIES)
        return cls(cities=cities, vague=not cities or bool(_VAGUE_LOCATION.search(text)))

    def compatible(self, other: "LocationProfile") -> bool:
        return self.vague or other.vague or bool(self.cities & other.cities)


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
    similar: int = 0  # how many of the duplicates were reworded copies from another listing


Openings = dict[tuple[str, str, str], list[tuple[str, LocationProfile]]]  # signature -> [(source, location)]


def _recent_openings(session: Session, companies: set[str]) -> Openings:
    """Signatures of openings first seen recently, for the companies in this batch only."""
    since = utcnow() - timedelta(days=SIMILAR_WINDOW_DAYS)
    index: Openings = {}
    rows = session.execute(
        select(Job.source, Job.company, Job.title, Job.job_type, Job.location).where(Job.first_seen_at >= since)
    )
    for source, company, title, job_type, location in rows:
        if " ".join(_COMPANY_FILLER.sub(" ", identity_company(company)).split()) not in companies:
            continue  # cheap skip before computing title words
        signature = opening_signature(company, title, job_type)
        if signature:
            index.setdefault(signature, []).append((source, LocationProfile.of(location)))
    return index


def _seen_elsewhere(openings: Openings, signature, source: str, profile: LocationProfile) -> bool:
    return any(other != source and profile.compatible(seen) for other, seen in openings.get(signature, []))


def find_new_jobs(session: Session, jobs: list[NormalizedJob]) -> DedupResult:
    """Split fetched jobs into unseen ones and duplicates (of the DB or of each other)."""
    keyed = [(job, fingerprint(job), content_key(job)) for job in jobs]
    fingerprints = {fp for _, fp, _ in keyed}
    content_keys = {ck for _, _, ck in keyed}

    known_fingerprints = set(session.scalars(select(Job.fingerprint).where(Job.fingerprint.in_(fingerprints))))
    known_content = set(session.scalars(select(Job.content_key).where(Job.content_key.in_(content_keys))))
    signatures = [opening_signature(job.company, job.title, job.job_type) for job, _, _ in keyed]
    openings = _recent_openings(session, {s[0] for s in signatures if s}) if any(signatures) else {}

    new_jobs, duplicates, similar = [], 0, 0
    for (job, fp, ck), signature in zip(keyed, signatures):
        if fp in known_fingerprints or ck in known_content:
            duplicates += 1
            continue
        profile = LocationProfile.of(job.location)
        if signature and _seen_elsewhere(openings, signature, job.source, profile):
            duplicates += 1
            similar += 1
            continue
        known_fingerprints.add(fp)  # same job twice in one batch (e.g. listed on two search pages)
        known_content.add(ck)
        if signature:
            openings.setdefault(signature, []).append((job.source, profile))
        new_jobs.append((job, fp, ck))
    return DedupResult(new_jobs=new_jobs, duplicates=duplicates, similar=similar)
