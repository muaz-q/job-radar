"""Wellfound source adapter.

Access method (checked against https://wellfound.com/robots.txt on 2026-09-13):
public role/location search pages such as /role/l/software-engineer/bangalore are
allowed. Those server-rendered pages embed their listing data as JSON in the
`__NEXT_DATA__` script tag, which is what we read. We do NOT log in, call private
APIs, use disallowed paths (/_jobs/, /search, ?jobId=...), rotate user agents, or
try to get past challenges. One request per configured page per scan, with a pause
between requests. If Wellfound blocks us or changes the page, this adapter reports
a clear SourceError and the rest of the app keeps working.

All Wellfound-specific knowledge lives in this file.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone

import httpx

from app.normalize import classify_category, clean_description, clean_text, normalize_job_type
from app.sources.base import FetchResult, JobSource, NormalizedJob, SourceError

log = logging.getLogger(__name__)

BASE_URL = "https://wellfound.com"
USER_AGENT = "JobRadar/0.1 (personal job-alert tool; low-frequency polling)"
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_REMOTE_KINDS = {"REMOTE", "ONSITE_OR_REMOTE", "REMOTE_ONLY"}


def job_url(job_id: str, slug: str | None) -> str:
    return f"{BASE_URL}/jobs/{job_id}-{slug}" if slug else f"{BASE_URL}/jobs/{job_id}"


def _parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for text in (clean_text(v, 100) for v in value) if text]


def _location(raw: dict) -> tuple[str | None, bool]:
    onsite = _string_list(raw.get("locationNames"))
    regions = _string_list(raw.get("acceptedRemoteLocationNames"))
    remote_config = raw.get("remoteConfig")
    if isinstance(remote_config, dict):
        is_remote = raw.get("remote") is True or remote_config.get("kind") in _REMOTE_KINDS
    else:
        # Older listings have no remoteConfig and remote=false, yet name the countries remote
        # candidates are accepted from. That list is the only remote signal they carry.
        is_remote = raw.get("remote") is True or bool(regions)
    parts = list(onsite)
    if is_remote:
        parts.append(f"Remote ({', '.join(regions)})" if regions else "Remote")
    return (" · ".join(parts) or None), is_remote


def parse_listing(raw: object, company: str | None, logo_url: str | None = None) -> NormalizedJob | None:
    """Turn one JobListingSearchResult into a NormalizedJob, or None if it is unusable."""
    if not isinstance(raw, dict):
        return None
    job_id = raw.get("id")
    job_id = str(job_id).strip() if isinstance(job_id, (str, int)) and not isinstance(job_id, bool) else ""
    title = clean_text(raw.get("title"), 300)
    company = clean_text(company, 300)
    if not job_id or not title or not company:
        return None

    location, is_remote = _location(raw)
    slug = raw.get("slug") if isinstance(raw.get("slug"), str) and re.fullmatch(r"[\w-]+", raw["slug"]) else None
    role_title = clean_text(raw.get("primaryRoleTitle"), 200)
    return NormalizedJob(
        source="wellfound",
        external_id=job_id,
        company=company,
        title=title,
        url=job_url(job_id, slug),
        location=location,
        is_remote=is_remote,
        posted_at=_parse_timestamp(raw.get("liveStartAt")),
        description=clean_description(raw.get("description")),
        job_type=normalize_job_type(raw.get("jobType"), title),
        category=classify_category(title, role_title),
        compensation=clean_text(raw.get("compensation"), 200),
        logo_url=logo_url if isinstance(logo_url, str) and logo_url.startswith("https://") else None,
    )


def parse_search_page(html: str) -> tuple[list[NormalizedJob], int]:
    """Extract jobs from a search page. Returns (jobs, skipped_record_count).

    Raises SourceError if the page has no recognizable listing data at all.
    """
    match = _NEXT_DATA.search(html)
    if not match:
        raise SourceError("page has no __NEXT_DATA__ block (layout changed, or an access challenge was served)")
    try:
        data = json.loads(match.group(1))
        apollo = data["props"]["pageProps"]["apolloState"]["data"]
    except (ValueError, KeyError, TypeError) as exc:
        raise SourceError(f"listing data not in the expected shape: {exc!r}") from exc
    if not isinstance(apollo, dict):
        raise SourceError("listing data not in the expected shape: apolloState.data is not an object")

    # Listings reference their company only indirectly: StartupResult.highlightedJobListings -> listing keys.
    company_by_listing: dict[str, str] = {}
    logo_by_listing: dict[str, str] = {}
    for key, value in apollo.items():
        if key.startswith("StartupResult:") and isinstance(value, dict):
            for ref in value.get("highlightedJobListings") or []:
                if isinstance(ref, dict) and isinstance(ref.get("__ref"), str):
                    company_by_listing[ref["__ref"]] = value.get("name")
                    logo_by_listing[ref["__ref"]] = value.get("logoUrl")

    jobs, skipped = [], 0
    for key, value in apollo.items():
        if not key.startswith("JobListingSearchResult:"):
            continue
        job = parse_listing(value, company_by_listing.get(key), logo_by_listing.get(key))
        if job is None:
            skipped += 1
        else:
            jobs.append(job)
    return jobs, skipped


class WellfoundSource(JobSource):
    name = "wellfound"
    display_name = "Wellfound"

    def __init__(self, search_paths: list[str], request_delay_seconds: float = 3.0,
                 timeout_seconds: float = 20.0, client: httpx.Client | None = None,
                 sleep=time.sleep):
        if not search_paths:
            raise ValueError("Wellfound needs at least one search path")
        self.search_paths = search_paths
        self.request_delay_seconds = request_delay_seconds
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._sleep = sleep

    def _get_page(self, client: httpx.Client, path: str) -> str:
        url = f"{BASE_URL}/{path}"
        try:
            response = client.get(url)
        except httpx.HTTPError as exc:
            raise SourceError(f"{path}: request failed ({type(exc).__name__}: {exc})") from exc
        if response.is_redirect:
            raise SourceError(f"{path}: redirected to {response.headers.get('location')} (search page does not exist)")
        if response.status_code == 429:
            raise _RateLimited(f"{path}: HTTP 429 rate limited; stopping this scan")
        if response.status_code in (401, 403):
            raise SourceError(f"{path}: HTTP {response.status_code} access refused (not bypassing)")
        if response.status_code != 200:
            raise SourceError(f"{path}: HTTP {response.status_code}")
        return response.text

    def fetch_jobs(self) -> FetchResult:
        result = FetchResult()
        client = self._client or httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=self.timeout_seconds,
            follow_redirects=False,
        )
        try:
            for index, path in enumerate(self.search_paths):
                if index:
                    self._sleep(self.request_delay_seconds)
                try:
                    jobs, skipped = parse_search_page(self._get_page(client, path))
                except _RateLimited as exc:
                    result.errors.append(str(exc))
                    break
                except SourceError as exc:
                    result.errors.append(str(exc) if str(exc).startswith(path) else f"{path}: {exc}")
                    continue
                log.info("wellfound page=%s jobs=%d skipped=%d", path, len(jobs), skipped)
                result.jobs.extend(jobs)
                result.skipped_records += skipped
        finally:
            if self._client is None:
                client.close()

        if not result.jobs and result.errors:
            raise SourceError("; ".join(result.errors))
        return result


class _RateLimited(SourceError):
    pass
