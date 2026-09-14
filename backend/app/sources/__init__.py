"""Source registry: builds adapter instances from config/sources.json."""

from app.config import Config
from app.sources.base import FetchResult, JobSource, NormalizedJob, SourceError
from app.sources.companies import CompaniesSource
from app.sources.mock import MockSource
from app.sources.settings_file import SourcesFile, UnstopOptions, load_sources_file
from app.sources.unstop import UnstopSource
from app.sources.wellfound import WellfoundSource

KNOWN_SOURCES = {
    "wellfound": "Wellfound",
    "companies": "Company careers pages",
    "unstop": "Unstop",
    "mock": "Mock (development)",
}


def build_sources(config: Config, sources_file: SourcesFile | None = None) -> list[JobSource]:
    """Enabled sources from the sources file. ENABLED_SOURCES, when set, overrides the enabled flags."""
    file = sources_file or load_sources_file(config.sources_file)
    override = config.enabled_source_names
    unknown = set(override) - set(KNOWN_SOURCES)
    if unknown:
        raise ValueError(f"unknown source(s) in ENABLED_SOURCES: {', '.join(sorted(unknown))}")

    def wanted(name: str, options) -> bool:
        if override:
            return name in override
        return options is not None and options.enabled

    # Order matters: when two sources list the same opening in one scan, the earlier source is kept.
    # Company careers pages first, so alerts link to the official posting rather than an aggregator.
    sources: list[JobSource] = []
    if wanted("companies", file.companies):
        if file.companies is None:
            raise ValueError("companies is enabled but has no boards in the sources file")
        sources.append(CompaniesSource(file.companies.boards, file.companies.india_only,
                                       file.companies.request_delay_seconds, file.companies.timeout_seconds))
    if wanted("unstop", file.unstop):
        options = file.unstop or UnstopOptions()
        sources.append(UnstopSource(options.max_pages, options.request_delay_seconds, options.timeout_seconds))
    if wanted("wellfound", file.wellfound):
        if file.wellfound is None:
            raise ValueError("wellfound is enabled but has no settings in the sources file")
        sources.append(WellfoundSource(file.wellfound.searches, file.wellfound.request_delay_seconds,
                                       file.wellfound.timeout_seconds))
    if wanted("mock", file.mock):
        sources.append(MockSource(emit_new_job_each_scan=file.mock.emit_new_job_each_scan
                                  or config.mock_emit_new_job_each_scan))
    return sources


__all__ = ["FetchResult", "JobSource", "NormalizedJob", "SourceError", "build_sources", "KNOWN_SOURCES"]
