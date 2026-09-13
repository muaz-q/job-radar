from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.routes.deps import get_session
from app.schemas import SettingsIn, SettingsOptions, SettingsOut
from app.settings_store import get_settings, save_settings

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsOut)
def read_settings(session: Annotated[Session, Depends(get_session)]):
    return get_settings(session)


@router.put("/settings", response_model=SettingsOut)
def update_settings(new_values: SettingsIn, session: Annotated[Session, Depends(get_session)]):
    return save_settings(session, new_values)


@router.get("/settings/options", response_model=SettingsOptions)
def settings_options():
    """The allowed values for each filter, so the UI never hard-codes them."""
    return SettingsOptions()
