"""Database tables."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow


class Job(Base):
    """Every job the system has ever seen, matching or not.

    Non-matching jobs are kept too: they are the "already known" registry. If they
    were discarded, widening the filters later would re-announce old jobs as new.
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(300))
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str] = mapped_column(String(1000))
    posted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    job_type: Mapped[str] = mapped_column(String(30))
    category: Mapped[str] = mapped_column(String(50))
    compensation: Mapped[str | None] = mapped_column(String(200))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    # Identity of this exact posting (source + id / canonical URL).
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    # Identity of the opening regardless of URL/source (company + title + location).
    content_key: Mapped[str] = mapped_column(String(64), index=True)
    # Whether the job matched the filters at the moment it was discovered.
    matched_on_discovery: Mapped[bool] = mapped_column(Boolean, default=False)

    notifications: Mapped[list["Notification"]] = relationship(back_populates="job")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    heading: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000))
    # pending -> delivered (the browser displayed it)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    job: Mapped[Job] = relationship(back_populates="notifications")


class SourceState(Base):
    __tablename__ = "source_states"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    # idle | running | ok | warning | error
    status: Mapped[str] = mapped_column(String(20), default="idle")
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    last_new_count: Mapped[int] = mapped_column(Integer, default=0)


class UserSettings(Base):
    """Single-row table (id=1). No accounts in V1."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    locations: Mapped[list] = mapped_column(JSON)
    job_types: Mapped[list] = mapped_column(JSON)
    categories: Mapped[list] = mapped_column(JSON)
    keywords: Mapped[list] = mapped_column(JSON)
    max_age_days: Mapped[int | None] = mapped_column(Integer)
    browser_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
