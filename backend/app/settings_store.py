"""Load/save the single settings row, creating defaults on first use."""

from sqlalchemy.orm import Session

from app.models import UserSettings
from app.schemas import SettingsIn

DEFAULT_SETTINGS = SettingsIn(
    locations=["Bengaluru", "Remote India"],
    job_types=["Internship"],
    categories=["Software Engineering", "AI/ML", "Backend", "Computer Vision"],
    keywords=[],
    max_age_days=30,
    browser_notifications=True,
)


def get_settings(session: Session) -> UserSettings:
    settings = session.get(UserSettings, 1)
    if settings is None:
        settings = UserSettings(id=1, **DEFAULT_SETTINGS.model_dump())
        session.add(settings)
        session.commit()
    return settings


def save_settings(session: Session, new_values: SettingsIn) -> UserSettings:
    settings = get_settings(session)
    for key, value in new_values.model_dump().items():
        setattr(settings, key, value)
    session.commit()
    return settings
