from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Config
from app.database import utcnow
from app.routes.deps import get_app_config, get_scanner, get_session
from app.scanner import ScanInProgress, Scanner
from app.schemas import ScanSummary, SourceOut
from app.status import source_statuses

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=list[SourceOut])
def list_sources(
    session: Annotated[Session, Depends(get_session)],
    scanner: Annotated[Scanner, Depends(get_scanner)],
    config: Annotated[Config, Depends(get_app_config)],
):
    return source_statuses(
        session,
        enabled=[source.name for source in scanner.sources],
        running=scanner.is_running,
        next_scan_at=scanner.next_scan_at if config.scheduler_enabled else None,
    )


@router.post("/scan", response_model=ScanSummary)
def trigger_scan(
    scanner: Annotated[Scanner, Depends(get_scanner)],
    config: Annotated[Config, Depends(get_app_config)],
):
    """Run a scan now (synchronously) and return what it found."""
    gap = timedelta(seconds=config.min_manual_scan_gap_seconds)
    last = scanner.last_manual_scan_at
    if last is not None and utcnow() - last < gap:
        wait = int((gap - (utcnow() - last)).total_seconds()) + 1
        raise HTTPException(status_code=429, detail=f"Scanned moments ago. Try again in {wait}s.",
                            headers={"Retry-After": str(wait)})
    try:
        scanner.last_manual_scan_at = utcnow()
        return scanner.scan()
    except ScanInProgress:
        raise HTTPException(status_code=409, detail="A scan is already running.")
