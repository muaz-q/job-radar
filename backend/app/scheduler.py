"""Periodic scanning with a plain asyncio task. No extra scheduler dependency needed.

Scans run in a worker thread so the (blocking) HTTP fetches never stall the API.
A failed scan is logged and the loop simply waits for the next interval: that is the retry.
"""

import asyncio
import logging
from datetime import timedelta

from app.database import utcnow
from app.scanner import ScanInProgress, Scanner

log = logging.getLogger(__name__)


async def run_scheduler(scanner: Scanner, interval_minutes: int) -> None:
    interval = timedelta(minutes=interval_minutes)
    log.info("scheduler started interval_minutes=%d", interval_minutes)
    while True:
        try:
            await asyncio.to_thread(scanner.scan)
        except ScanInProgress:
            log.info("scheduled scan skipped: a scan is already running")
        except Exception:
            log.exception("scheduled scan crashed; will retry next interval")
        scanner.next_scan_at = utcnow() + interval
        await asyncio.sleep(interval.total_seconds())
