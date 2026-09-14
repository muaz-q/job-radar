"""Big-company careers sites: Workday-hosted sites, Amazon Jobs and Microsoft Careers.

Access checked 2026-09-14:
- Workday sites (e.g. salesforce.wd12.myworkdayjobs.com): robots.txt explicitly allows each
  career site and publishes job sitemaps. We call the JSON endpoint the public site itself uses.
- amazon.jobs: robots.txt only disallows /internal; /en/search.json is the public search.
- apply.careers.microsoft.com: robots.txt disallows everything EXCEPT a list that explicitly
  includes /api/pcsx (the job search API). It rate-limits quickly, so we make very few requests
  and stop for the hour on HTTP 429.
- Google careers is NOT supported: robots.txt disallows /about/careers/applications/jobs/results.

Each fetcher returns (jobs, skipped_count) or raises SourceError.
"""

import re
from datetime import datetime, timedelta, timezone

import httpx

from app.normalize import classify_category, clean_description, clean_text, join_locations, mentions_india, normalize_job_type
from app.sources.base import NormalizedJob, SourceError

_BENGALURU = re.compile(r"\b(bangalore|bengaluru)\b", re.I)
_INDIA = re.compile(r"\bindia\b", re.I)
_REMOTE = re.compile(r"\bremote\b", re.I)


def _request(client: httpx.Client, label: str, method: str, url: str, **kwargs) -> httpx.Response:
    try:
        response = client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise SourceError(f"{label}: request failed ({type(exc).__name__})") from exc
    if response.status_code == 429:
        raise SourceError(f"{label}: HTTP 429 rate limited; skipped until the next scan")
    if response.status_code != 200:
        raise SourceError(f"{label}: HTTP {response.status_code}")
    try:
        response.json()
    except ValueError as exc:
        raise SourceError(f"{label}: response is not JSON") from exc
    return response


# ------------------------------------------------------------------ Workday

WORKDAY_PAGE = 20


def parse_workday_posted(text: object, now: datetime | None = None) -> datetime | None:
    """Workday lists only relative dates: "Posted Today", "Posted Yesterday", "Posted 3 Days Ago", "Posted 30+ Days Ago"."""
    if not isinstance(text, str):
        return None
    now = now or datetime.now(timezone.utc)
    lowered = text.lower()
    if "today" in lowered:
        return now
    if "yesterday" in lowered:
        return now - timedelta(days=1)
    match = re.search(r"(\d+)(\+)?\s+days?\s+ago", lowered)
    if match and not match.group(2):
        return now - timedelta(days=int(match.group(1)))
    # "30+ Days Ago" hides the real date. Unknown dates never hide a job (see filters.is_recent_enough):
    # long-open internships at target companies otherwise vanish behind a guessed age.
    return None


def _facet_values(facets: object, parameter: str | None = None):
    """Yield (facetParameter, id, descriptor) for every selectable value.

    Workday nests groups: {"facetParameter": "locationMainGroup", "values": [{"facetParameter":
    "locations", "descriptor": "City", "values": [...cities...]}]}. A nested value must be sent under
    its own group's parameter ("locations"); the outer name is rejected with HTTP 400.
    """
    for item in facets if isinstance(facets, list) else []:
        if not isinstance(item, dict):
            continue
        own = item.get("facetParameter") or parameter
        if isinstance(item.get("values"), list):
            yield from _facet_values(item["values"], own)
        elif item.get("id") and isinstance(item.get("descriptor"), str) and parameter:
            yield parameter, item["id"], item["descriptor"]


def workday_location_groups(facets: object) -> list[tuple[str, dict, str | None]]:
    """Queries to run, most specific first: one per Bengaluru location value, then all of India.

    Returns (label, appliedFacets, location_label). location_label None means "use the posting's own text".
    Querying Bengaluru explicitly matters: most multi-city postings only say "3 Locations".
    """
    groups = []
    for param, value_id, descriptor in _facet_values(facets):
        if _BENGALURU.search(descriptor):
            remote = " · Remote (India)" if _REMOTE.search(descriptor) else ""
            groups.append((descriptor, {param: [value_id]}, f"Bengaluru, India{remote}"))
    india = {}
    for param, value_id, descriptor in _facet_values(facets):
        if descriptor.strip().lower() == "india":  # a country facet
            india = {param: [value_id]}
            break
    if not india:  # no country facet: select every location value in India
        for param, value_id, descriptor in _facet_values(facets):
            if _INDIA.search(descriptor):
                india.setdefault(param, []).append(value_id)
    if india:
        groups.append(("India", india, None))
    return groups


def parse_workday_posting(raw: object, board, location_label: str | None, now: datetime | None = None) -> NormalizedJob | None:
    if not isinstance(raw, dict):
        return None
    title = clean_text(raw.get("title"), 300)
    path = raw.get("externalPath")
    if not (title and isinstance(path, str) and re.fullmatch(r"/job/[\w\-./%()+,]+", path)):
        return None
    bullets = raw.get("bulletFields") if isinstance(raw.get("bulletFields"), list) else []
    req_id = next((b for b in bullets if isinstance(b, str) and re.fullmatch(r"[\w-]{3,40}", b)), None) or path.rsplit("_", 1)[-1]
    text = clean_text(raw.get("locationsText"), 200)
    many = text and re.fullmatch(r"\d+ Locations?", text)
    if location_label:
        location = location_label + (f" · {text.lower()}" if many else "")
    else:
        location = f"India · {text.lower()}" if many else text
    return NormalizedJob(
        source="companies",
        external_id=f"workday:{board.slug}:{req_id}",
        company=board.name or board.slug,
        title=title,
        url=f"https://{board.host}.myworkdayjobs.com/{board.site}{path}",
        location=location,
        is_remote=bool(location and _REMOTE.search(location)),
        posted_at=parse_workday_posted(raw.get("postedOn"), now),
        job_type=normalize_job_type(None, title, default="Full-time"),
        category=classify_category(title),
    )


def fetch_workday(client: httpx.Client, board, india_only: bool, sleep, delay: float, max_jobs: int = 400):
    label = f"workday/{board.slug}"
    api = f"https://{board.host}.myworkdayjobs.com/wday/cxs/{board.slug}/{board.site}/jobs"

    def page(applied: dict, offset: int) -> dict:
        body = {"appliedFacets": applied, "limit": WORKDAY_PAGE, "offset": offset, "searchText": ""}
        return _request(client, label, "POST", api, json=body).json()

    first = page({}, 0)
    if india_only:
        groups = workday_location_groups(first.get("facets"))
        if not groups:
            return [], 0  # this site has no India locations at all
    else:
        groups = [("all", {}, None)]

    jobs, skipped = [], 0
    for _, applied, location_label in groups:
        offset, total = 0, None
        while offset < max_jobs and (total is None or offset < total):
            sleep(delay)
            data = page(applied, offset)
            postings = data.get("jobPostings") if isinstance(data.get("jobPostings"), list) else []
            if total is None:  # Workday reports the real total only on the first page; later pages say 0
                total = data.get("total") if isinstance(data.get("total"), int) else len(postings)
            for raw in postings:
                job = parse_workday_posting(raw, board, location_label)
                if job is None:
                    skipped += 1
                else:
                    jobs.append(job)
            if not postings:
                break
            offset += WORKDAY_PAGE
    return jobs, skipped


# ------------------------------------------------------------------ Amazon

AMAZON_SEARCH = "https://www.amazon.jobs/en/search.json"
AMAZON_PAGE = 100


def parse_amazon(raw: object, board) -> NormalizedJob | None:
    if not isinstance(raw, dict):
        return None
    job_id = raw.get("id_icims") or raw.get("id")
    title = clean_text(raw.get("title"), 300)
    path = raw.get("job_path")
    if not (isinstance(job_id, (str, int)) and not isinstance(job_id, bool) and title
            and isinstance(path, str) and re.fullmatch(r"/[\w\-./]+", path)):
        return None
    location = clean_text(raw.get("normalized_location") or raw.get("location"), 200)
    if location:
        location = re.sub(r",\s*IND\b", ", India", location)
    posted = None
    if isinstance(raw.get("posted_date"), str):
        try:
            posted = datetime.strptime(" ".join(raw["posted_date"].split()), "%B %d, %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    is_remote = bool(location and re.search(r"\bvirtual\b|\bremote\b", location, re.I))
    return NormalizedJob(
        source="companies",
        external_id=f"amazon:{job_id}",
        company=board.name or "Amazon",
        title=title,
        url=f"https://www.amazon.jobs{path}",
        location=join_locations(location, "Remote (India)" if is_remote and mentions_india(location) else None),
        is_remote=is_remote,
        posted_at=posted,
        description=clean_description(raw.get("description_short") or raw.get("description")),
        job_type=normalize_job_type(raw.get("job_schedule_type"), title, default="Full-time"),
        category=classify_category(title, clean_text(raw.get("job_category")), clean_text(raw.get("job_family"))),
    )


def fetch_amazon(client: httpx.Client, board, india_only: bool, sleep, delay: float):
    """Newest first, so the first pages always contain anything posted since the last scan."""
    label = "amazon"
    jobs, skipped = [], 0
    for page_index in range(board.max_pages):
        if page_index:
            sleep(delay)
        params = {"result_limit": AMAZON_PAGE, "offset": page_index * AMAZON_PAGE, "sort": "recent"}
        if india_only:
            params["country"] = "IND"
        data = _request(client, label, "GET", AMAZON_SEARCH, params=params).json()
        listings = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(listings, list):
            raise SourceError(f"{label}: unexpected response shape")
        for raw in listings:
            job = parse_amazon(raw, board)
            if job is None:
                skipped += 1
            else:
                jobs.append(job)
        if len(listings) < AMAZON_PAGE:
            break
    return jobs, skipped


# ------------------------------------------------------------------ Microsoft

MICROSOFT_SEARCH = "https://apply.careers.microsoft.com/api/pcsx/search"


def microsoft_location(locations: object) -> str | None:
    """"India, Karnataka, Bangalore" -> "Bangalore, Karnataka, India"; unspecified cities -> "India · Multiple locations"."""
    names = []
    for entry in locations if isinstance(locations, list) else []:
        parts = [p.strip() for p in entry.split(",")] if isinstance(entry, str) else []
        parts = [p for p in parts if p]
        if not parts:
            continue
        if any(p.lower() == "multiple locations" for p in parts):
            names.append(f"{parts[0]} · Multiple locations")
        else:
            names.append(", ".join(reversed(parts)))
    return join_locations(*names)


def parse_microsoft(raw: object, board) -> NormalizedJob | None:
    if not isinstance(raw, dict):
        return None
    job_id = raw.get("displayJobId") or raw.get("id")
    title = clean_text(raw.get("name"), 300)
    path = raw.get("positionUrl")
    if not (isinstance(job_id, (str, int)) and not isinstance(job_id, bool) and title
            and isinstance(path, str) and re.fullmatch(r"/careers/job/\d+", path)):
        return None
    location = microsoft_location(raw.get("locations"))
    is_remote = str(raw.get("workLocationOption", "")).lower() == "remote"
    posted = raw.get("postedTs")
    return NormalizedJob(
        source="companies",
        external_id=f"microsoft:{job_id}",
        company=board.name or "Microsoft",
        title=title,
        url=f"https://apply.careers.microsoft.com{path}",
        location=join_locations(location, "Remote (India)" if is_remote and mentions_india(location) else None),
        is_remote=is_remote,
        posted_at=datetime.fromtimestamp(posted, tz=timezone.utc)
        if isinstance(posted, (int, float)) and not isinstance(posted, bool) and posted > 0 else None,
        job_type=normalize_job_type(None, title, default="Full-time"),
        category=classify_category(title, clean_text(raw.get("department"))),
    )


def fetch_microsoft(client: httpx.Client, board, india_only: bool, sleep, delay: float):
    label = "microsoft"
    jobs, skipped = [], 0
    for index, query in enumerate(board.queries):
        if index:
            sleep(max(delay, 5.0))  # Microsoft rate-limits bursts
        params = {"domain": "microsoft.com", "query": query, "location": "India" if india_only else "",
                  "start": 0, "num": 20, "sort_by": "timestamp"}
        data = _request(client, label, "GET", MICROSOFT_SEARCH, params=params).json()
        positions = (data.get("data") or {}).get("positions") if isinstance(data, dict) else None
        if not isinstance(positions, list):
            raise SourceError(f"{label}: unexpected response shape")
        for raw in positions:
            job = parse_microsoft(raw, board)
            if job is None:
                skipped += 1
            else:
                jobs.append(job)
    return jobs, skipped


FETCHERS = {"workday": fetch_workday, "amazon": fetch_amazon, "microsoft": fetch_microsoft}
