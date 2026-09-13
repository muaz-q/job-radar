"""Command-line entry points, used by the GitHub Actions scanner.

  python -m app.cli scan    --state-dir ../state   # scan, save to state/job_radar.db, export state/public/*.json
  python -m app.cli deliver --state-dir ../state   # send pending alerts (Telegram), re-export

Two separate steps so the workflow can save the scan results *before* sending anything.
Exit code is non-zero only for problems a human must fix (bad config files); a failing
job source is recorded in the data and reported, not treated as a crash.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select

from app.config import Config, get_config
from app.database import Database
from app.export import export_snapshot
from app.models import SourceState
from app.notifications import NotificationService, TelegramChannel, build_channels, DeliveryError
from app.scanner import Scanner
from app.schemas import SettingsIn
from app.settings_store import save_settings
from app.sources import build_sources
from app.sources.settings_file import load_sources_file

log = logging.getLogger("job_radar.cli")

# Alert once when a source reaches this many failures in a row (not again until it recovers).
FAILURE_ALERT_THRESHOLD = 3
GITHUB_SCAN_INTERVAL_MINUTES = 60


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    # httpx logs full request URLs at INFO; the Telegram URL contains the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def load_settings_file(path: Path) -> SettingsIn:
    try:
        return SettingsIn.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        raise ValueError(f"settings file not found: {path}") from None
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"settings file {path} is invalid: {exc}") from exc


def open_state(state_dir: Path) -> Database:
    state_dir.mkdir(parents=True, exist_ok=True)
    db = Database(f"sqlite:///{(state_dir / 'job_radar.db').as_posix()}")
    db.create_all()
    return db


def github_annotation(level: str, message: str) -> None:
    """Shows up on the workflow run page in GitHub (harmless noise when run locally)."""
    print(f"::{level}::{message}", flush=True)


def cmd_scan(args, config: Config) -> int:
    settings = load_settings_file(args.settings)
    sources_file = load_sources_file(args.sources)
    db = open_state(args.state_dir)
    with db.session() as session:
        save_settings(session, settings)

    sources = build_sources(config, sources_file)
    scanner = Scanner(db, sources, NotificationService(build_channels(config)), deliver_after_scan=False)
    summary = scanner.scan()
    for s in summary.sources:
        line = (f"{s.source}: status={s.status} fetched={s.fetched} new={s.new} duplicates={s.duplicates} "
                f"matching={s.matching} alerts={s.notifications}")
        print(line, flush=True)
        for error in s.errors:
            github_annotation("error" if s.status == "error" else "warning", f"{s.source}: {error}")

    with db.session() as session:
        exported = export_snapshot(session, args.state_dir / "public", [s.name for s in sources],
                                   GITHUB_SCAN_INTERVAL_MINUTES)
    print(f"exported jobs={exported['jobs']} matching={exported['matching']}", flush=True)
    return 0


def cmd_deliver(args, config: Config) -> int:
    db = open_state(args.state_dir)
    channels = build_channels(config)
    service = NotificationService(channels)
    with db.session() as session:
        results = service.deliver_pending(session)
        for channel, result in results.items():
            print(f"{channel}: pending={result['pending']} delivered={result['delivered']}", flush=True)
            if result["error"]:
                github_annotation("warning", f"{channel} delivery failed, will retry next run: {result['error']}")

        telegram = next((c for c in channels if isinstance(c, TelegramChannel)), None)
        failing = session.scalars(
            select(SourceState).where(SourceState.consecutive_failures == FAILURE_ALERT_THRESHOLD)
        ).all()
        for state in failing if telegram else []:
            try:
                telegram.send_text(f"⚠ Job Radar: {state.name} has failed {state.consecutive_failures} scans in a row.\n"
                                   f"{(state.last_error or '')[:500]}")
            except DeliveryError as exc:
                github_annotation("warning", f"could not send source-failure alert: {exc}")

        sources_file = load_sources_file(args.sources)
        enabled = [s.name for s in build_sources(config, sources_file)]
        export_snapshot(session, args.state_dir / "public", enabled, GITHUB_SCAN_INTERVAL_MINUTES)
    return 0


def main(argv: list[str] | None = None) -> int:
    config = get_config()
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Job Radar scanner")
    parser.add_argument("command", choices=["scan", "deliver"])
    parser.add_argument("--state-dir", type=Path, required=True, help="holds job_radar.db and public/*.json")
    parser.add_argument("--settings", type=Path, default=config.settings_file)
    parser.add_argument("--sources", type=Path, default=config.sources_file)
    args = parser.parse_args(argv)
    configure_logging(config.log_level)
    try:
        return {"scan": cmd_scan, "deliver": cmd_deliver}[args.command](args, config)
    except (ValueError, ValidationError) as exc:
        github_annotation("error", str(exc))
        log.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
