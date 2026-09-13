import json

import httpx

from app.models import Notification
from app.notifications import NotificationService, TelegramChannel
from app.scanner import Scanner
from tests.conftest import make_job


class FakeTelegram:
    def __init__(self, fail_after: int | None = None, status: int = 500):
        self.messages = []
        self.fail_after = fail_after
        self.status = status

    def handler(self, request):
        if self.fail_after is not None and len(self.messages) >= self.fail_after:
            return httpx.Response(self.status, json={"ok": False, "description": "Too Many Requests"})
        self.messages.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    def channel(self, token="123:secret", chat="42", dashboard="https://radar.example.com"):
        return TelegramChannel(token, chat, dashboard, client=httpx.Client(transport=httpx.MockTransport(self.handler)))


def scan_with(db, source, telegram, jobs, deliver=True):
    source.jobs = jobs
    Scanner(db, [source], NotificationService([telegram]), deliver_after_scan=deliver).scan()


def statuses(db):
    with db.session() as session:
        return [n.status for n in session.query(Notification).order_by(Notification.id)]


def test_few_jobs_send_one_message_each_with_view_button(db, source, open_settings):
    fake = FakeTelegram()
    scan_with(db, source, fake.channel(), [make_job(1, title="AI <Engineer> Intern & co"), make_job(2)])
    assert len(fake.messages) == 2
    first = fake.messages[0]
    assert first["chat_id"] == "42" and first["parse_mode"] == "HTML"
    assert "AI &lt;Engineer&gt; Intern &amp; co" in first["text"]  # user-visible text is escaped
    assert first["reply_markup"]["inline_keyboard"][0][0] == {"text": "View Job →", "url": "https://jobs.example.com/1"}
    assert statuses(db) == ["delivered", "delivered"]


def test_many_jobs_become_one_summary(db, source, open_settings):
    fake = FakeTelegram()
    scan_with(db, source, fake.channel(), [make_job(i) for i in range(12)])
    assert len(fake.messages) == 1
    text = fake.messages[0]["text"]
    assert text.startswith("<b>12 new jobs</b>")
    assert text.count("<a href=") == 12
    assert fake.messages[0]["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://radar.example.com"
    assert set(statuses(db)) == {"delivered"}


def test_huge_summary_stays_under_telegram_limit(db, source, open_settings):
    fake = FakeTelegram()
    scan_with(db, source, fake.channel(), [make_job(i, title="Very long title " * 8) for i in range(200)])
    text = fake.messages[0]["text"]
    assert len(text) < 4096 and "more on the dashboard" in text


def test_already_sent_jobs_are_never_resent(db, source, open_settings):
    fake = FakeTelegram()
    channel = fake.channel()
    scan_with(db, source, channel, [make_job(1)])
    scan_with(db, source, channel, [make_job(1), make_job(2)])
    scan_with(db, source, channel, [make_job(1), make_job(2)])
    assert len(fake.messages) == 2


def test_failure_keeps_unsent_pending_and_retries_next_run(db, source, open_settings):
    fake = FakeTelegram(fail_after=1, status=429)
    channel = fake.channel()
    scan_with(db, source, channel, [make_job(1), make_job(2), make_job(3)])
    assert statuses(db) == ["delivered", "pending", "pending"]

    fake.fail_after = None
    with db.session() as session:
        result = NotificationService([channel]).deliver_pending(session)
    assert result["telegram"]["delivered"] == 2
    assert statuses(db) == ["delivered"] * 3
    assert len(fake.messages) == 3


def test_missing_credentials_keep_alerts_pending(db, source, open_settings):
    fake = FakeTelegram()
    scan_with(db, source, fake.channel(token=""), [make_job(1)])
    assert fake.messages == [] and statuses(db) == ["pending"]


def test_network_error_message_never_contains_the_token(db, open_settings):
    def boom(request):
        raise httpx.ConnectError(f"failed to connect to {request.url}")

    channel = TelegramChannel("123:SUPERSECRET", "42", client=httpx.Client(transport=httpx.MockTransport(boom)))
    try:
        channel.send_text("hi")
    except Exception as exc:
        assert "SUPERSECRET" not in str(exc)
    else:
        raise AssertionError("expected DeliveryError")
