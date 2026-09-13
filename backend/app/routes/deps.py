"""Shared FastAPI dependencies. Everything hangs off app.state so tests can swap it."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import Config
from app.scanner import Scanner


def get_session(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session_dependency()


def get_scanner(request: Request) -> Scanner:
    return request.app.state.scanner


def get_app_config(request: Request) -> Config:
    return request.app.state.config
