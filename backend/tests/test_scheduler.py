import asyncio

import pytest

from app import scheduler
from app.scanner import ScanInProgress


class CountingScanner:
    def __init__(self, error=None):
        self.calls = 0
        self.error = error
        self.next_scan_at = None

    def scan(self):
        self.calls += 1
        if self.error:
            raise self.error


def run_two_cycles(monkeypatch, fake):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.run_scheduler(fake, interval_minutes=15))
    return sleeps


def test_scans_immediately_then_every_interval(monkeypatch):
    fake = CountingScanner()
    assert run_two_cycles(monkeypatch, fake) == [900, 900]
    assert fake.calls == 2
    assert fake.next_scan_at is not None


@pytest.mark.parametrize("error", [RuntimeError("database locked"), ScanInProgress()])
def test_a_crashing_scan_does_not_stop_the_loop(monkeypatch, error):
    fake = CountingScanner(error=error)
    run_two_cycles(monkeypatch, fake)
    assert fake.calls == 2
