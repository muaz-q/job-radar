"""Notification service.

Detection code calls `NotificationService.notify(jobs)` and knows nothing about how
alerts reach the user. Every channel first records a "pending" notification; delivery
then depends on the channel:

BrowserChannel -- the open dashboard polls for pending notifications, shows them as
    browser notifications, and marks them delivered.

TelegramChannel -- `NotificationService.deliver_pending()` sends them through the
    Telegram Bot API and marks them delivered. Recording first and delivering second
    means scan results can be saved before anything is sent: a crash mid-run causes at
    worst a retry of unsent alerts, never a job forgotten or announced twice.

A WhatsApp or mobile-push channel would be one more class with the same two methods.
"""

import html
import logging
from abc import ABC, abstractmethod
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import utcnow
from app.models import Job, Notification

log = logging.getLogger(__name__)


def relative_age(moment: datetime | None, now: datetime | None = None) -> str | None:
    if moment is None:
        return None
    seconds = max(0, int(((now or utcnow()) - moment).total_seconds()))
    for unit_seconds, unit in ((86400, "day"), (3600, "hour"), (60, "min")):
        if seconds >= unit_seconds:
            count = seconds // unit_seconds
            return f"{count} {unit}{'s' if count != 1 and unit != 'min' else ''} ago"
    return "just now"


def build_message(job: Job, now: datetime | None = None) -> tuple[str, str]:
    """Minimal alert text: heading plus title / company / location / age. Nothing else."""
    kind = "Internship" if job.job_type == "Internship" else "Job"
    category = "" if job.category == "Other" else f"{job.category} "
    heading = f"New {category}{kind}"
    posted = relative_age(job.posted_at, now)
    lines = [job.title, job.company, job.location or "Location not listed"]
    lines.append(f"Posted {posted}" if posted else "Just discovered")
    return heading, "\n".join(lines)


class DeliveryError(Exception):
    pass


class NotificationChannel(ABC):
    name: str

    @abstractmethod
    def is_enabled(self, settings) -> bool: ...

    def send(self, session: Session, job: Job) -> Notification:
        """Record a pending notification for this channel."""
        heading, body = build_message(job)
        notification = Notification(job=job, channel=self.name, heading=heading, body=body, url=job.url)
        session.add(notification)
        return notification


class BrowserChannel(NotificationChannel):
    name = "browser"

    def is_enabled(self, settings) -> bool:
        return bool(settings.browser_notifications)


class TelegramChannel(NotificationChannel):
    """Pushes alerts to a Telegram chat. Works with every browser and device closed."""

    name = "telegram"
    API = "https://api.telegram.org/bot{token}/sendMessage"
    MAX_INDIVIDUAL = 5          # more than this in one run -> one summary message
    MAX_MESSAGE_CHARS = 3800    # Telegram's hard limit is 4096

    def __init__(self, bot_token: str, chat_id: str, dashboard_url: str = "", client: httpx.Client | None = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.dashboard_url = dashboard_url
        self._client = client

    def is_enabled(self, settings) -> bool:
        # Always record: if credentials are missing, alerts wait as "pending" until they are configured.
        return True

    def _post(self, text: str, button: tuple[str, str] | None = None) -> None:
        if not self.bot_token or not self.chat_id:
            raise DeliveryError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set")
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
                   "link_preview_options": {"is_disabled": True}}
        if button and button[1].startswith("https://"):
            payload["reply_markup"] = {"inline_keyboard": [[{"text": button[0], "url": button[1]}]]}
        client = self._client or httpx.Client(timeout=20)
        try:
            response = client.post(self.API.format(token=self.bot_token), json=payload)
        except httpx.HTTPError as exc:
            # Never include the exception text: httpx messages contain the URL, which contains the token.
            raise DeliveryError(f"Telegram request failed ({type(exc).__name__})") from None
        finally:
            if self._client is None:
                client.close()
        if response.status_code != 200:
            try:
                description = response.json().get("description", "")
            except ValueError:
                description = ""
            raise DeliveryError(f"Telegram HTTP {response.status_code}: {description}"[:300])

    @staticmethod
    def format_single(n: Notification) -> str:
        title, *rest = n.body.split("\n")
        return f"<b>{html.escape(n.heading)}</b>\n\n<b>{html.escape(title)}</b>\n" + html.escape("\n".join(rest))

    def format_summary(self, notifications: list[Notification]) -> str:
        header = f"<b>{len(notifications)} new jobs</b>\n"
        lines, shown = [], 0
        for n in notifications:
            title, company, location, *_ = (n.body.split("\n") + ["", "", ""])[:3]
            line = (f'• <a href="{html.escape(n.url, quote=True)}">{html.escape(title)}</a>'
                    f" — {html.escape(company)} · {html.escape(location)}")
            if len(header) + sum(len(l) + 1 for l in lines) + len(line) > self.MAX_MESSAGE_CHARS - 80:
                break
            lines.append(line)
            shown += 1
        more = len(notifications) - shown
        footer = f"\n…and {more} more on the dashboard." if more else ""
        return header + "\n".join(lines) + footer

    def deliver(self, notifications: list[Notification]) -> list[int]:
        """Send; return the ids delivered. On failure raises DeliveryError carrying `.delivered` (partial progress)."""
        delivered: list[int] = []
        try:
            if len(notifications) <= self.MAX_INDIVIDUAL:
                for n in notifications:
                    self._post(self.format_single(n), ("View Job →", n.url))
                    delivered.append(n.id)
            else:
                self._post(self.format_summary(notifications), ("Open dashboard", self.dashboard_url))
                delivered.extend(n.id for n in notifications)
        except DeliveryError as exc:
            exc.delivered = delivered
            raise
        return delivered

    def send_text(self, text: str) -> None:
        """Operational alerts (e.g. a source failing repeatedly)."""
        self._post(html.escape(text))


def build_channels(config) -> list[NotificationChannel]:
    channels: list[NotificationChannel] = []
    for name in config.notify_channel_names:
        if name == "browser":
            channels.append(BrowserChannel())
        elif name == "telegram":
            channels.append(TelegramChannel(config.telegram_bot_token, config.telegram_chat_id, config.dashboard_url))
        else:
            raise ValueError(f"unknown notification channel in NOTIFY_CHANNELS: {name!r} (known: browser, telegram)")
    return channels


class NotificationService:
    def __init__(self, channels: list[NotificationChannel] | None = None):
        self.channels = channels if channels is not None else [BrowserChannel()]

    def notify(self, session: Session, jobs: list[Job], settings) -> int:
        """Record one notification per job per enabled channel. Returns the number created."""
        channels = [c for c in self.channels if c.is_enabled(settings)]
        if jobs and not channels:
            log.info("notifications disabled; %d matching new jobs not announced", len(jobs))
            return 0
        sent = 0
        for job in jobs:
            for channel in channels:
                try:
                    channel.send(session, job)
                    sent += 1
                except Exception:  # one broken channel must not stop the others
                    log.exception("channel %s failed for job %s", channel.name, job.id)
        return sent

    def deliver_pending(self, session: Session) -> dict[str, dict]:
        """Push pending notifications for channels that can push. Returns per-channel results."""
        results = {}
        for channel in self.channels:
            if not hasattr(channel, "deliver"):
                continue
            pending = list(session.scalars(
                select(Notification).where(Notification.channel == channel.name, Notification.status == "pending")
                .order_by(Notification.id)
            ))
            if not pending:
                results[channel.name] = {"pending": 0, "delivered": 0, "error": None}
                continue
            error = None
            try:
                delivered = channel.deliver(pending)
            except DeliveryError as exc:
                delivered, error = getattr(exc, "delivered", []), str(exc)
                log.error("delivery via %s failed: %s (%d left pending for the next run)",
                          channel.name, error, len(pending) - len(delivered))
            now = utcnow()
            for n in pending:
                if n.id in delivered:
                    n.status, n.delivered_at = "delivered", now
            session.commit()
            results[channel.name] = {"pending": len(pending), "delivered": len(delivered), "error": error}
        return results
