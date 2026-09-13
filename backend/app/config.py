"""Application configuration, loaded from environment variables / a .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Config(BaseSettings):
    # Reads job-radar/.env, then backend/.env (later wins), then real environment variables (win over both).
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./job_radar.db"

    # Which sources run and their options (company list, search pages, ...).
    sources_file: Path = REPO_ROOT / "config" / "sources.json"
    # Filter settings used by the GitHub Actions scanner (the local app keeps settings in its database).
    settings_file: Path = REPO_ROOT / "config" / "settings.json"
    # Optional comma-separated override of the enabled flags in the sources file, e.g. "mock".
    enabled_sources: str = ""

    # Automatic scanning (local app). Minimum of 5 minutes so we never hammer a source.
    scheduler_enabled: bool = True
    scan_interval_minutes: int = Field(default=15, ge=5)
    # Minimum gap between two manual POST /scan calls (0 disables the guard).
    min_manual_scan_gap_seconds: int = Field(default=60, ge=0)

    # Mock source: when true, each scan also emits one brand-new job (for testing alerts).
    mock_emit_new_job_each_scan: bool = False

    # Comma-separated notification channels: browser (dashboard tab), telegram.
    notify_channels: str = "browser"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Linked from Telegram summary messages.
    dashboard_url: str = ""

    # Where the frontend runs; used for CORS when not going through the Vite proxy.
    frontend_origin: str = "http://localhost:5173"

    log_level: str = "INFO"

    @property
    def enabled_source_names(self) -> list[str]:
        return [s.strip().lower() for s in self.enabled_sources.split(",") if s.strip()]

    @property
    def notify_channel_names(self) -> list[str]:
        return [s.strip().lower() for s in self.notify_channels.split(",") if s.strip()]


@lru_cache
def get_config() -> Config:
    return Config()
