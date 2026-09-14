"""SQLAlchemy engine, session factory and a UTC-safe datetime column type."""

from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Stores datetimes as naive UTC, always returns timezone-aware UTC.

    SQLite drops timezone info. Without this, values read back are naive while
    freshly created values are aware, and comparing them raises TypeError.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime passed to UTCDateTime; use timezone-aware values")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return None if value is None else value.replace(tzinfo=timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


class Database:
    """Holds the engine + session factory so tests can swap in a temporary database."""

    def __init__(self, database_url: str):
        self.engine = make_engine(database_url)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        from app import models  # noqa: F401  (registers tables)

        Base.metadata.create_all(self.engine)
        self._add_missing_columns()

    # Columns added after the first release. create_all() never alters existing tables, and the
    # hosted scanner's database on the data branch predates these, so they are added in place.
    _ADDED_COLUMNS = {"jobs": {"logo_url": "VARCHAR(500)"}}

    def _add_missing_columns(self) -> None:
        inspector = inspect(self.engine)
        with self.engine.begin() as connection:
            for table, columns in self._ADDED_COLUMNS.items():
                existing = {column["name"] for column in inspector.get_columns(table)}
                for name, ddl in columns.items():
                    if name not in existing:
                        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

    def session(self) -> Session:
        return self.session_factory()

    def session_dependency(self) -> Iterator[Session]:
        with self.session() as session:
            yield session
