from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import utcnow
from app.models import Notification
from app.routes.deps import get_session
from app.schemas import NotificationOut

router = APIRouter(tags=["notifications"])


class MarkDelivered(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    session: Annotated[Session, Depends(get_session)],
    status: Literal["pending", "delivered"] | None = None,
    limit: int = Query(200, ge=1, le=1000),
):
    query = select(Notification).order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    if status:
        query = query.where(Notification.status == status)
    return list(session.scalars(query))


@router.post("/notifications/mark-delivered")
def mark_delivered(payload: MarkDelivered, session: Annotated[Session, Depends(get_session)]):
    """Called by the dashboard after it has shown the browser notifications."""
    result = session.execute(
        update(Notification)
        .where(Notification.id.in_(payload.ids), Notification.status == "pending")
        .values(status="delivered", delivered_at=utcnow())
    )
    session.commit()
    return {"updated": result.rowcount}
