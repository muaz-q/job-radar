import pytest

from app.normalize import (
    canonical_url, classify_category, clean_description, clean_text, identity_company, identity_location,
    normalize_job_type,
)


@pytest.mark.parametrize("raw,title,expected", [
    ("full-time", "Software Engineer", "Full-time"),
    ("internship", "Software Engineer", "Internship"),
    ("full-time", "AI Engineer Intern", "Internship"),  # intern title beats source label
    ("Part Time", "Designer", "Part-time"),
    ("contract", "Developer", "Contract"),
    ("cofounder", "CTO", "Other"),
    (None, "Developer", "Other"),
    (None, "International Sales Lead", "Other"),  # "international" is not "intern"
])
def test_job_type(raw, title, expected):
    assert normalize_job_type(raw, title) == expected


@pytest.mark.parametrize("texts,expected", [
    (("Computer Vision Engineer",), "Computer Vision"),
    (("ML Engineer", "Software Engineer"), "AI/ML"),
    (("AI - Software Engineer and Architect",), "AI/ML"),
    (("Senior Backend Engineer",), "Backend"),
    (("Software Engineer", "Backend Engineer"), "Backend"),
    (("Data Engineer",), "Data"),
    (("Site Reliability Engineer",), "DevOps"),
    (("Full Stack Developer",), "Software Engineering"),
    (("Maintenance Manager",), "Other"),  # "ai" inside "maintenance" must not match
    (("Marketing Intern",), "Other"),
    (("Lead Technical Support Engineer", "Software Engineer"), "Other"),  # seen live on Wellfound
    (("Sales Engineer",), "Other"),
    # Seen live on Unstop, where broad "job area" hints pushed these into AI/ML:
    (("AI Content Creator Internship", "Artificial Intelligence"), "Other"),
    (("Growth & Operations Internship", "AI"), "Other"),
    (("AI Business Operations Internship",), "Other"),
    (("Engineering Internship", "Machine Learning"), "AI/ML"),        # generic title, specific hint
    (("Python Developer Internship", "Backend Development"), "Backend"),
    (("Business Intelligence Analyst",), "Data"),
    (("DevOps Engineer",), "DevOps"),
    ((None,), "Other"),
])
def test_category(texts, expected):
    assert classify_category(*texts) == expected


@pytest.mark.parametrize("url", [
    "https://wellfound.com/jobs/123-backend",
    "http://wellfound.com/jobs/123-backend",
    "https://www.WellFound.com/jobs/123-backend/",
    "https://wellfound.com/jobs/123-backend?utm_source=x&ref=abc",
    "https://wellfound.com/jobs/123-backend#apply",
    "  https://wellfound.com/jobs/123-backend  ",
])
def test_canonical_url_collapses_variations(url):
    assert canonical_url(url) == "https://wellfound.com/jobs/123-backend"


def test_canonical_url_keeps_meaningful_query_and_rejects_garbage():
    assert canonical_url("https://x.com/job?id=5&utm_medium=y") == "https://x.com/job?id=5"
    assert canonical_url("not a url") is None
    assert canonical_url(None) is None


def test_clean_text_and_description():
    assert clean_text("  Design &amp;\n  build  ") == "Design & build"
    assert clean_text("   ") is None
    assert clean_text(42) is None
    assert clean_description("Line one\n\n\n\nLine   two") == "Line one\n\nLine two"


def test_identity_helpers():
    assert identity_company("Tonbo Imaging Pvt. Ltd.") == identity_company("tonbo imaging")
    assert identity_company("Acme Technologies Private Limited") == "acme"
    assert identity_location("Bangalore") == identity_location("Bengaluru")
