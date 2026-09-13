"""Company careers boards via the official public job-board APIs of Greenhouse, Lever and Ashby.

These endpoints exist so that anyone can list a company's open jobs:
  https://boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=true
  https://api.lever.co/v0/postings/<slug>?mode=json
  https://api.ashbyhq.com/posting-api/job-board/<slug>
Aggregators such as HireHire are largely built on the same data. One request per
company per scan; one failing company is a warning, not a failed source.
"""

import logging
import time
from datetime import datetime, timezone

import httpx

from app.normalize import (
    classify_category, clean_description, clean_text, join_locations, mentions_india, normalize_job_type, strip_html,
)
from app.sources.base import FetchResult, JobSource, NormalizedJob, SourceError
from app.sources.settings_file import Board

log = logging.getLogger(__name__)

USER_AGENT = "JobRadar/0.1 (personal job-alert tool; hourly polling)"
ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}


def _iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _epoch_ms(value: object) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _names(items: object, key: str = "name") -> list[str]:
    if not isinstance(items, list):
        return []
    return [n for n in (clean_text(i.get(key)) if isinstance(i, dict) else None for i in items) if n]


def _web_url(value: object) -> str | None:
    return value if isinstance(value, str) and value.startswith("https://") else None


def _job_id(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    return str(value).strip() or None


def parse_greenhouse(raw: object, board: Board, india_only: bool) -> NormalizedJob | None:
    if not isinstance(raw, dict):
        return None
    job_id, title, url = _job_id(raw.get("id")), clean_text(raw.get("title"), 300), _web_url(raw.get("absolute_url"))
    if not (job_id and title and url):
        return None
    location = clean_text((raw.get("location") or {}).get("name") if isinstance(raw.get("location"), dict) else None, 300)
    is_remote = bool(location and "remote" in location.lower())
    if india_only and not mentions_india(location):
        return None
    job_type_values = [clean_text(m.get("value")) for m in raw.get("metadata") or []
                       if isinstance(m, dict) and isinstance(m.get("name"), str)
                       and m["name"].lower() in ("employment type", "job type") and isinstance(m.get("value"), str)]
    return NormalizedJob(
        source="companies",
        external_id=f"greenhouse:{board.slug}:{job_id}",
        company=board.name or clean_text(raw.get("company_name"), 300) or board.slug,
        title=title,
        url=url,
        location=location,
        is_remote=is_remote,
        posted_at=_iso(raw.get("first_published")) or _iso(raw.get("updated_at")),
        description=strip_html(raw.get("content")),
        job_type=normalize_job_type(job_type_values[0] if job_type_values else None, title, default="Full-time"),
        category=classify_category(title, *_names(raw.get("departments"))),
    )


def parse_lever(raw: object, board: Board, india_only: bool) -> NormalizedJob | None:
    if not isinstance(raw, dict):
        return None
    job_id, title, url = _job_id(raw.get("id")), clean_text(raw.get("text"), 300), _web_url(raw.get("hostedUrl"))
    if not (job_id and title and url):
        return None
    categories = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
    all_locations = categories.get("allLocations") if isinstance(categories.get("allLocations"), list) else []
    places = [clean_text(p, 100) for p in [categories.get("location"), *all_locations]]
    in_india = raw.get("country") == "IN" or mentions_india(*places)
    if india_only and not in_india:
        return None
    is_remote = raw.get("workplaceType") == "remote"
    remote_label = ("Remote (India)" if in_india else "Remote") if is_remote else None
    return NormalizedJob(
        source="companies",
        external_id=f"lever:{board.slug}:{job_id}",
        company=board.name or board.slug,
        title=title,
        url=url,
        location=join_locations(*places, remote_label),
        is_remote=is_remote,
        posted_at=_epoch_ms(raw.get("createdAt")),
        description=clean_description(raw.get("descriptionPlain")),
        job_type=normalize_job_type(categories.get("commitment"), title, default="Full-time"),
        category=classify_category(title, clean_text(categories.get("team")), clean_text(categories.get("department"))),
    )


def parse_ashby(raw: object, board: Board, india_only: bool) -> NormalizedJob | None:
    if not isinstance(raw, dict) or raw.get("isListed") is False:
        return None
    job_id, title, url = _job_id(raw.get("id")), clean_text(raw.get("title"), 300), _web_url(raw.get("jobUrl"))
    if not (job_id and title and url):
        return None
    address = raw.get("address") if isinstance(raw.get("address"), dict) else {}
    postal = address.get("postalAddress") if isinstance(address.get("postalAddress"), dict) else {}
    places = [clean_text(raw.get("location"), 100), *_names(raw.get("secondaryLocations"), key="location")]
    in_india = mentions_india(*places, clean_text(postal.get("addressCountry")))
    if india_only and not in_india:
        return None
    is_remote = raw.get("isRemote") is True or raw.get("workplaceType") == "Remote"
    remote_label = ("Remote (India)" if in_india else "Remote") if is_remote else None
    return NormalizedJob(
        source="companies",
        external_id=f"ashby:{board.slug}:{job_id}",
        company=board.name or board.slug,
        title=title,
        url=url,
        location=join_locations(*[p for p in places if not (is_remote and p and p.lower() == "remote")], remote_label),
        is_remote=is_remote,
        posted_at=_iso(raw.get("publishedAt")),
        description=clean_description(raw.get("descriptionPlain")),
        job_type=normalize_job_type(raw.get("employmentType"), title, default="Full-time"),
        category=classify_category(title, clean_text(raw.get("team")), clean_text(raw.get("department"))),
    )


PARSERS = {"greenhouse": parse_greenhouse, "lever": parse_lever, "ashby": parse_ashby}


def extract_listings(ats: str, payload: object) -> list:
    """Greenhouse and Ashby wrap listings in {"jobs": [...]}; Lever returns a bare list."""
    listings = payload.get("jobs") if ats in ("greenhouse", "ashby") and isinstance(payload, dict) else payload
    if not isinstance(listings, list):
        raise SourceError(f"unexpected response shape from {ats}")
    return listings


class CompaniesSource(JobSource):
    name = "companies"
    display_name = "Company careers pages"

    def __init__(self, boards: list[Board], india_only: bool = True, request_delay_seconds: float = 1.0,
                 timeout_seconds: float = 20.0, client: httpx.Client | None = None, sleep=time.sleep):
        self.boards = boards
        self.india_only = india_only
        self.request_delay_seconds = request_delay_seconds
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._sleep = sleep

    def _fetch_board(self, client: httpx.Client, board: Board) -> tuple[list[NormalizedJob], int]:
        label = f"{board.ats}/{board.slug}"
        try:
            response = client.get(ENDPOINTS[board.ats].format(slug=board.slug))
        except httpx.HTTPError as exc:
            raise SourceError(f"{label}: request failed ({type(exc).__name__})") from exc
        if response.status_code == 404:
            raise SourceError(f"{label}: board not found (check the slug in config/sources.json)")
        if response.status_code != 200:
            raise SourceError(f"{label}: HTTP {response.status_code}")
        try:
            listings = extract_listings(board.ats, response.json())
        except ValueError as exc:
            raise SourceError(f"{label}: response is not JSON") from exc
        except SourceError as exc:
            raise SourceError(f"{label}: {exc}") from exc

        parser, jobs, skipped = PARSERS[board.ats], [], 0
        for raw in listings:
            job = parser(raw, board, self.india_only)
            if job is not None:
                jobs.append(job)
            elif not _looks_valid(raw):  # filtered-out (non-India) listings are not "malformed"
                skipped += 1
        return jobs, skipped

    def fetch_jobs(self) -> FetchResult:
        result = FetchResult()
        client = self._client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=self.timeout_seconds)
        try:
            for index, board in enumerate(self.boards):
                if index:
                    self._sleep(self.request_delay_seconds)
                try:
                    jobs, skipped = self._fetch_board(client, board)
                except SourceError as exc:
                    result.errors.append(str(exc))
                    continue
                log.info("companies board=%s/%s jobs=%d skipped=%d", board.ats, board.slug, len(jobs), skipped)
                result.jobs.extend(jobs)
                result.skipped_records += skipped
        finally:
            if self._client is None:
                client.close()
        if result.errors and len(result.errors) == len(self.boards):
            raise SourceError("; ".join(result.errors))
        return result


def _looks_valid(raw: object) -> bool:
    return isinstance(raw, dict) and bool(_job_id(raw.get("id"))) and bool(raw.get("title") or raw.get("text"))
