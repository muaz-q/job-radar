"""config/sources.json: which sources run and their options.

One file for both the local app and the GitHub Actions scanner, edited by hand.
Everything is validated; board slugs end up in URLs, so they are restricted to safe characters.
"""

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WellfoundOptions(_Strict):
    enabled: bool = True
    searches: list[str] = Field(min_length=1)
    request_delay_seconds: float = Field(default=3.0, ge=1.0)
    timeout_seconds: float = Field(default=20.0, gt=0)


class Board(_Strict):
    """One company careers source.

    greenhouse / lever / ashby: slug = the company's board name.
    workday: slug = tenant, plus host ("salesforce.wd12") and site ("External_Career_Site"),
             all visible in the careers URL https://<host>.myworkdayjobs.com/<site>.
    amazon / microsoft: the company's own careers search; slug is just a label.
    """

    ats: Literal["greenhouse", "lever", "ashby", "workday", "amazon", "microsoft"]
    slug: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    name: str | None = Field(default=None, max_length=100)
    host: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,60}\.wd\d{1,3}$")
    site: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,100}$")
    # amazon: pages of 100 newest jobs to read per scan
    max_pages: int = Field(default=2, ge=1, le=10)
    # microsoft: search terms, one request each (keep this short: Microsoft rate-limits)
    queries: list[str] = Field(default_factory=lambda: ["intern", "software engineer"], min_length=1, max_length=4)

    @field_validator("queries")
    @classmethod
    def safe_queries(cls, values: list[str]) -> list[str]:
        for query in values:
            if not re.fullmatch(r"[\w +#.-]{1,40}", query):
                raise ValueError(f"unsupported characters in query: {query!r}")
        return values

    @model_validator(mode="after")
    def workday_needs_host_and_site(self) -> "Board":
        if self.ats == "workday" and not (self.host and self.site):
            raise ValueError(f"workday board {self.slug!r} needs both host and site")
        return self


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
