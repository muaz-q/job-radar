"""The scan pipeline: fetch -> dedup -> filter -> store -> notify, per source.

A failing source is recorded (status=error, error message kept) and never stops
other sources or crashes the app. The next scheduled scan is the retry.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.database import Database, utcnow
from app.dedup import find_new_jobs
from app.filters import FilterSettings, matches_filters
from app.models import Job, SourceState
from app.notifications import NotificationService
from app.schemas import ScanSummary, SourceScanSummary
from app.settings_store import get_settings
from app.sources.base import FetchResult, JobSource, NormalizedJob, SourceError

log = logging.getLogger(__name__)


class ScanInProgress(Exception):
    pass


def get_source_state(session: Session, name: str) -> SourceState:
    state = session.get(SourceState, name)
    if state is None:
        state = SourceState(name=name, status="idle", consecutive_failures=0,
                            last_fetched_count=0, last_new_count=0)
        session.add(state)
    return state


def _is_web_url(url: str | None) -> bool:
    parts = urlsplit(url or "")
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def _to_model(job: NormalizedJob, fingerprint: str, content_key: str, matched: bool, now: datetime) -> Job:
    return Job(
        source=job.source, external_id=job.external_id, company=job.company, title=job.title,
        location=job.location, is_remote=job.is_remote, url=job.url, posted_at=job.posted_at,
        first_seen_at=now, description=job.description, job_type=job.job_type, category=job.category,
        compensation=job.compensation, fingerprint=fingerprint, content_key=content_key,
        matched_on_discovery=matched,
    )


class Scanner:
    def __init__(self, db: Database, sources: list[JobSource], notifier: NotificationService | None = None,
                 deliver_after_scan: bool = True):
        self.db = db
        self.sources = sources
        self.notifier = notifier or NotificationService()
        # The local app pushes alerts (e.g. Telegram) right away. The GitHub scanner turns this off
        # so it can save scan results before sending anything.
        self.deliver_after_scan = deliver_after_scan
        self._lock = threading.Lock()
        self.next_scan_at: datetime | None = None
        self.last_manual_scan_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        return self._lock.locked()

    def scan(self) -> ScanSummary:
        if not self._lock.acquire(blocking=False):
            raise ScanInProgress()
        try:
            started = utcnow()
            outcomes = self._fetch_all()
            # Processing stays sequential and in configured order: database writes are single-threaded,
            # and when two sources list the same opening, the earlier source's link is the one kept.
            results = [self._finish(source, outcome) for source, outcome in outcomes]
            if self.deliver_after_scan:
                try:
                    with self.db.session() as session:
                        self.notifier.deliver_pending(session)
                except Exception:
                    log.exception("delivering notifications failed; they stay pending for the next scan")
            return ScanSummary(started_at=started, finished_at=utcnow(), sources=results)
        finally:
            self._lock.release()

    def _fetch_all(self) -> list[tuple[JobSource, FetchResult | Exception]]:
        """Fetch every source at the same time. Sources are different websites, so running them in
        parallel costs no politeness: each adapter still spaces out requests to its own site."""
        with self.db.session() as session:
            for source in self.sources:
                get_source_state(session, source.name).status = "running"
            session.commit()

        def fetch(source: JobSource) -> FetchResult | Exception:
            started = time.monotonic()
            log.info("scan started source=%s", source.name)
            try:
                return source.fetch_jobs()
            except Exception as exc:  # SourceError or anything unexpected inside an adapter
                return exc
            finally:
                log.info("fetch finished source=%s seconds=%.1f", source.name, time.monotonic() - started)

        if not self.sources:
            return []
        with ThreadPoolExecutor(max_workers=len(self.sources), thread_name_prefix="fetch") as pool:
            outcomes = list(pool.map(fetch, self.sources))  # map keeps the configured order
        return list(zip(self.sources, outcomes))

    def _finish(self, source: JobSource, outcome: FetchResult | Exception) -> SourceScanSummary:
        if isinstance(outcome, Exception):
            return self._record_failure(source, outcome)
        try:
            return self._process(source, outcome)
        except Exception as exc:
            log.exception("processing failed source=%s", source.name)
            return self._record_failure(source, exc)

    def _process(self, source: JobSource, fetched: FetchResult) -> SourceScanSummary:
        now = utcnow()
        # The UI opens job.url directly, so only ever store plain web links.
        usable = [job for job in fetched.jobs if _is_web_url(job.url)]
        unsafe_urls = len(fetched.jobs) - len(usable)
        with self.db.session() as session:
            settings = get_settings(session)
            filters = FilterSettings.from_model(settings)
            dedup = find_new_jobs(session, usable)

            new_models, matching = [], []
            for job, fp, ck in dedup.new_jobs:
                matched = matches_filters(job, filters, now)
                model = _to_model(job, fp, ck, matched, now)
                new_models.append(model)
                if matched:
                    matching.append(model)
            session.add_all(new_models)
            session.flush()  # assign ids before notifications reference the jobs

            sent = self.notifier.notify(session, matching, settings)

            state = get_source_state(session, source.name)
            state.last_checked_at = now
            state.last_fetched_count = len(fetched.jobs)
            state.last_new_count = len(new_models)
            errors = list(fetched.errors)
            if fetched.skipped_records:
                errors.append(f"{fetched.skipped_records} malformed record(s) skipped")
            if unsafe_urls:
                errors.append(f"{unsafe_urls} job(s) with a non-http(s) URL skipped")
            if errors:
                state.status, state.last_error = "warning", "; ".join(errors)[:2000]
            else:
                state.status, state.last_error = "ok", None
            state.last_success_at = now
            state.consecutive_failures = 0
            session.commit()

        log.info(
            "scan finished source=%s fetched=%d new=%d duplicates=%d (reworded=%d) matching=%d notifications=%d errors=%d",
            source.name, len(fetched.jobs), len(new_models), dedup.duplicates, dedup.similar, len(matching), sent,
            len(errors),
        )
        return SourceScanSummary(
            source=source.name, status=state.status, fetched=len(fetched.jobs), new=len(new_models),
            duplicates=dedup.duplicates, matching=len(matching), notifications=sent, errors=errors,
        )

    def _record_failure(self, source: JobSource, exc: Exception) -> SourceScanSummary:
        message = str(exc) if isinstance(exc, SourceError) else f"{type(exc).__name__}: {exc}"
        log.error("scan failed source=%s error=%s", source.name, message)
        with self.db.session() as session:
            state = get_source_state(session, source.name)
            state.status = "error"
            state.last_checked_at = utcnow()
            state.last_error = message[:2000]
            state.consecutive_failures += 1
            session.commit()
        return SourceScanSummary(source=source.name, status="error", fetched=0, new=0, duplicates=0,
                                 matching=0, notifications=0, errors=[message])
