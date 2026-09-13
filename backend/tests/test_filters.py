from datetime import timedelta

import pytest

from app.database import utcnow
from app.filters import FilterSettings, matches_filters, matches_location
from tests.conftest import make_job

TARGET = FilterSettings(
    locations=["Bengaluru", "Remote India"],
    job_types=["Internship"],
    categories=["AI/ML", "Backend", "Computer Vision", "Software Engineering"],
)


@pytest.mark.parametrize("location,remote,option,expected", [
    ("Bengaluru", False, "Bengaluru", True),
    ("Bangalore", False, "Bengaluru", True),
    ("Seattle · Bengaluru · Lisbon", False, "Bengaluru", True),
    ("Mumbai", False, "Bengaluru", False),
    ("Remote (India)", True, "Remote India", True),
    ("Bengaluru · Remote (India)", True, "Remote India", True),
    ("Remote (United States)", True, "Remote India", False),
    ("Remote", True, "Remote India", False),
    ("India", False, "Remote India", False),  # onsite somewhere in India is not remote
    ("Remote", True, "Remote (Anywhere)", True),
    (None, False, "Bengaluru", False),
    (None, True, "Remote (Anywhere)", True),
])
def test_location_matching(location, remote, option, expected):
    assert matches_location(make_job(location=location, is_remote=remote), option) is expected


def test_target_profile_matches_and_rejects():
    assert matches_filters(make_job(), TARGET)
    assert not matches_filters(make_job(job_type="Full-time"), TARGET)
    assert not matches_filters(make_job(category="Other"), TARGET)
    assert not matches_filters(make_job(location="Pune"), TARGET)


def test_empty_settings_match_everything():
    assert matches_filters(make_job(location=None, job_type="Other", category="Other"), FilterSettings())


def test_keywords_whole_word_case_insensitive_any_of():
    settings = FilterSettings(keywords=["python", "machine learning"])
    assert matches_filters(make_job(description="We use PYTHON daily"), settings)
    assert matches_filters(make_job(title="Machine Learning Intern", description=None), settings)
    assert not matches_filters(make_job(title="Intern", description="Pythonic mindset"), settings)


def test_keywords_with_symbols_and_regex_characters_are_literal():
    assert matches_filters(make_job(description="Modern C++ and C#"), FilterSettings(keywords=["c++"]))
    assert not matches_filters(make_job(description="anything"), FilterSettings(keywords=[".*"]))
    assert not matches_filters(make_job(title="AI", description="x"), FilterSettings(keywords=["ai/ml"]))


def test_ai_keyword_does_not_match_inside_words():
    assert not matches_filters(make_job(title="Maintainer", description="Email support"),
                               FilterSettings(keywords=["ai"]))


def test_max_age():
    now = utcnow()
    settings = FilterSettings(max_age_days=30)
    assert matches_filters(make_job(posted_at=now - timedelta(days=29)), settings, now)
    assert not matches_filters(make_job(posted_at=now - timedelta(days=31)), settings, now)
    assert matches_filters(make_job(posted_at=None), settings, now)  # unknown date is not hidden
