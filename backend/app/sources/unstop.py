"""Unstop internships via its public API.

https://unstop.com/robots.txt explicitly allows /api/public/*. We read the open
internship search results page by page (they are not sorted by date, so all pages
are read), with a pause between requests.
"""

import logging
import re
import time
from datetime import datetime

import httpx

from app.normalize import classify_category, clean_text, join_locations, strip_html
from app.sources.base import FetchResult, JobSource, NormalizedJob, SourceError

log = logging.getLogger(__name__)

USER_AGENT = "JobRadar/0.1 (personal job-alert tool; hourly polling)"
SEARCH_URL = "https://unstop.com/api/public/opportunity/search-result"
# 100 per page: the same ~850 internships in 9 requests instead of 29 (checked 2026-09-14).
PER_PAGE = 100


def _parse_posted(raw: dict) -> datetime | None:
    # approved_date looks like "2026-09-13 19:35:50 GMT+0530"
    value = raw.get("approved_date")
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S GMT%z")
        except ValueError:
            pass
    value = raw.get("updated_at")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _cities(raw: dict, detail: dict) -> list[str]:
    cities = []
    for container in (raw.get("locations"), detail.get("locations")):
        for item in container if isinstance(container, list) else []:
            city = clean_text(item.get("city"), 100) if isinstance(item, dict) else clean_text(item, 100)
            if city:
                cities.append(city)
    return cities


def _compensation(detail: dict) -> str | None:
    low, high = detail.get("min_salary"), detail.get("max_salary")
    if not detail.get("show_salary") or detail.get("paid_unpaid") == "unpaid":
        return None
    numbers = [n for n in (low, high) if isinstance(n, (int, float)) and not isinstance(n, bool) and n > 0]
    if not numbers:
        return None
    return " – ".join(f"₹{n:,.0f}" for n in dict.fromkeys(numbers))


def parse_opportunity(raw: object) -> NormalizedJob | None:
    if not isinstance(raw, dict):
        return None
    job_id = raw.get("id")
    job_id = str(job_id) if isinstance(job_id, int) and not isinstance(job_id, bool) else None
    title = clean_text(raw.get("title"), 300)
    organisation = raw.get("organisation") if isinstance(raw.get("organisation"), dict) else {}
    company = clean_text(organisation.get("name"), 300)
    url = raw.get("seo_url")
    if not (isinstance(url, str) and url.startswith("https://unstop.com/")):
        path = raw.get("public_url")
        url = f"https://unstop.com/{path}" if isinstance(path, str) and re.fullmatch(r"[\w/-]+", path) else None
    if not (job_id and title and company and url):
        return None

    detail = raw.get("jobDetail") if isinstance(raw.get("jobDetail"), dict) else {}
    is_remote = detail.get("type") == "wfh" or (raw.get("region") == "online" and not _cities(raw, detail))
    work_functions = [clean_text(w.get("name")) for w in raw.get("workfunction") or [] if isinstance(w, dict)]
    return NormalizedJob(
        source="unstop",
        external_id=job_id,
        company=company,
        title=title,
        url=url,
        # Unstop is an India-only platform, so remote roles are remote within India.
        location=join_locations(*_cities(raw, detail), "Remote (India)" if is_remote else None),
        is_remote=is_remote,
        posted_at=_parse_posted(raw),
        description=strip_html(raw.get("details")),
        job_type="Internship",
        category=classify_category(title, *filter(None, work_functions)),
        compensation=_compensation(detail),
        # organisation.logoUrl is the company logo. The listing's own image (logoUrl2) is sometimes
        # a recruiter's personal photo, so it is deliberately not used.
        logo_url=organisation.get("logoUrl") if str(organisation.get("logoUrl", "")).startswith("https://") else None,
    )


class UnstopSource(JobSource):
    name = "unstop"
    display_name = "Unstop"

    def __init__(self, max_pages: int = 30, request_delay_seconds: float = 2.0, timeout_seconds: float = 20.0,
                 client: httpx.Client | None = None, sleep=time.sleep):
        self.max_pages = max_pages
        self.request_delay_seconds = request_delay_seconds
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._sleep = sleep

    def _get_page(self, client: httpx.Client, page: int) -> dict:
        params = {"opportunity": "internships", "oppstatus": "open", "per_page": PER_PAGE, "page": page}
        try:
            response = client.get(SEARCH_URL, params=params)
        except httpx.HTTPError as exc:
            raise SourceError(f"page {page}: request failed ({type(exc).__name__})") from exc
        if response.status_code == 429:
            raise SourceError(f"page {page}: HTTP 429 rate limited; stopping this scan")
        if response.status_code != 200:
            raise SourceError(f"page {page}: HTTP {response.status_code}")
        try:
            data = response.json()["data"]
            if not isinstance(data.get("data"), list):
                raise TypeError("data.data is not a list")
            return data
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise SourceError(f"page {page}: unexpected response shape ({exc})") from exc

    def fetch_jobs(self) -> FetchResult:
        result = FetchResult()
        client = self._client or httpx.Client(headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                                              timeout=self.timeout_seconds)
        try:
            page, last_page = 1, 1
            while page <= min(last_page, self.max_pages):
                if page > 1:
                    self._sleep(self.request_delay_seconds)
                try:
                    data = self._get_page(client, page)
                except SourceError as exc:
                    result.errors.append(str(exc))
                    break  # later pages depend on knowing last_page; retry next scan
                last_page = data.get("last_page") if isinstance(data.get("last_page"), int) else page
                for raw in data["data"]:
                    job = parse_opportunity(raw)
                    if job is None:
                        result.skipped_records += 1
                    else:
                        result.jobs.append(job)
                page += 1
            log.info("unstop pages=%d jobs=%d skipped=%d", page - 1, len(result.jobs), result.skipped_records)
        finally:
            if self._client is None:
                client.close()
        if not result.jobs and result.errors:
            raise SourceError("; ".join(result.errors))
        return result
