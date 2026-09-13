"""config/sources.json: which sources run and their options.

One file for both the local app and the GitHub Actions scanner, edited by hand.
Everything is validated; board slugs end up in URLs, so they are restricted to safe characters.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WellfoundOptions(_Strict):
    enabled: bool = True
    searches: list[str] = Field(min_length=1)
    request_delay_seconds: float = Field(default=3.0, ge=1.0)
    timeout_seconds: float = Field(default=20.0, gt=0)


class Board(_Strict):
    ats: Literal["greenhouse", "lever", "ashby"]
    slug: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    name: str | None = Field(default=None, max_length=100)


class CompaniesOptions(_Strict):
    enabled: bool = True
    # Global companies list hundreds of US/EU roles; keep only India-based and India-remote ones.
    india_only: bool = True
    request_delay_seconds: float = Field(default=1.0, ge=0.5)
    timeout_seconds: float = Field(default=20.0, gt=0)
    boards: list[Board] = Field(min_length=1)


class UnstopOptions(_Strict):
    enabled: bool = True
    # Results are not sorted by date, so reading only page 1 would miss new postings.
    max_pages: int = Field(default=30, ge=1, le=60)
    request_delay_seconds: float = Field(default=2.0, ge=1.0)
    timeout_seconds: float = Field(default=20.0, gt=0)


class MockOptions(_Strict):
    enabled: bool = False
    emit_new_job_each_scan: bool = False


class SourcesFile(_Strict):
    wellfound: WellfoundOptions | None = None
    companies: CompaniesOptions | None = None
    unstop: UnstopOptions | None = None
    mock: MockOptions = MockOptions()


def load_sources_file(path: str | Path) -> SourcesFile:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"sources file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"sources file is not valid JSON: {path}: {exc}") from exc
    return SourcesFile.model_validate(raw)
