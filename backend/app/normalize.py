"""Source-independent normalization: turns raw strings into consistent job fields.

Every rule here is deterministic keyword matching. No ML/LLM classification in V1.
"""

import html
import re
from urllib.parse import urlsplit, urlunsplit

_WHITESPACE = re.compile(r"\s+")


def clean_text(value: object, max_length: int | None = None) -> str | None:
    """Unescape HTML entities, collapse whitespace, return None for empty/non-string."""
    if not isinstance(value, str):
        return None
    text = _WHITESPACE.sub(" ", html.unescape(value)).strip()
    if not text:
        return None
    return text[:max_length] if max_length else text


def clean_description(value: object, max_length: int = 20000) -> str | None:
    """Like clean_text but keeps line breaks, which matter for readability."""
    if not isinstance(value, str):
        return None
    lines = [" ".join(line.split()) for line in html.unescape(value).splitlines()]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text[:max_length] or None


# ---------------------------------------------------------------- job type

_JOB_TYPE_PATTERNS = [
    ("Internship", re.compile(r"\bintern(ship)?s?\b|\btrainee\b|\bapprentice", re.I)),
    ("Part-time", re.compile(r"\bpart[\s_-]?time\b", re.I)),
    ("Contract", re.compile(r"\bcontract(or)?\b|\bfreelance\b|\bcontract[\s_-]?to[\s_-]?hire\b", re.I)),
    # "On-roll" is Indian HR usage for a permanent employee (seen on Paytm's Lever board).
    ("Full-time", re.compile(r"\bfull[\s_-]?time\b|\bpermanent\b|\bon[\s-]?roll\b", re.I)),
]


def normalize_job_type(raw_type: object, title: str | None = None, default: str = "Other") -> str:
    """Map a source's job-type value to one of our options.

    An "intern" title wins over the source's type: sources often label internships
    "full-time" (a full-time internship), and for this product the internship-ness matters.
    `default` is for sources that never state a type (most company job boards are full-time).
    """
    if title and _JOB_TYPE_PATTERNS[0][1].search(title):
        return "Internship"
    if isinstance(raw_type, str):
        for label, pattern in _JOB_TYPE_PATTERNS:
            if pattern.search(raw_type):
                return label
        return "Other" if raw_type.strip() else default
    return default


# ---------------------------------------------------------------- category

# Non-engineering roles often carry tech words in the title ("Technical Support Engineer",
# "AI Content Creator", "AI Business Operations"). Checked against the title only.
_NON_ENGINEERING_TITLE = re.compile(
    r"\b(support|sales|pre[\s-]?sales|customer success|account (manager|executive)|marketing|recruit(er|ing)"
    r"|talent acquisition|business (development|operations)|operations|content|creator|copywrit\w*|social media"
    r"|campus ambassador|ambassador|human resources|hr|finance|accounting|legal|lawyer|graphic|designer"
    r"|video|editor|teacher|tutor|teaching)\b", re.I)

SOFTWARE_ENGINEERING = "Software Engineering"

# Most specific first. Software Engineering is the generic fallback and is only tried after
# every specific category failed on both the title and the hints.
_CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    ("Computer Vision", re.compile(
        r"\bcomputer vision\b|\bcv engineer\b|\bvision\b|\bperception\b|\bimage processing\b|\bslam\b", re.I)),
    ("AI/ML", re.compile(
        r"\bmachine learning\b|\bml\b|\bai\b|\ba\.i\.|\bdeep learning\b|\bllms?\b|\bnlp\b|\bgen ?ai\b"
        r"|\bartificial intelligence\b|\bdata scientist\b|\bmlops\b|\bprompt engineer", re.I)),
    ("Data", re.compile(
        r"\bdata (engineer|analyst|analytics|platform)\b|\banalytics\b|\bbusiness intelligence\b|\betl\b", re.I)),
    ("DevOps", re.compile(
        r"\bdevops\b|\bsre\b|\bsite reliability\b|\binfrastructure\b|\bplatform engineer\b|\bcloud engineer\b", re.I)),
    ("Backend", re.compile(r"\bback[\s-]?end\b|\bapi engineer\b|\bserver[\s-]side\b", re.I)),
    ("Software Engineering", re.compile(
        r"\bsoftware\b|\bdeveloper\b|\bengineer(ing)?\b|\bfull[\s-]?stack\b|\bfront[\s-]?end\b|\bsde\b"
        r"|\bprogrammer\b|\bmobile\b|\bandroid\b|\bios\b|\bweb\b", re.I)),
]


def classify_category(title: str | None, *hints: str | None) -> str:
    """Classify from the job title, using hints (role title, team, job areas) to refine it.

    Never uses the description, which mentions everything. Order of evaluation:
    non-engineering title -> Other; specific category in title; specific category in hints;
    generic Software Engineering in title, then hints; else Other.
    """
    title = title or ""
    hint_text = " ".join(h for h in hints if h)
    if _NON_ENGINEERING_TITLE.search(title):
        return "Other"
    specific = [(c, p) for c, p in _CATEGORY_RULES if c != SOFTWARE_ENGINEERING]
    generic = [(c, p) for c, p in _CATEGORY_RULES if c == SOFTWARE_ENGINEERING]
    for rules in (specific, generic):
        for text in (title, hint_text):
            for category, pattern in rules:
                if text and pattern.search(text):
                    return category
    return "Other"


# ---------------------------------------------------------------- location

_CITY_ALIASES = {"bangalore": "bengaluru", "bengaluru": "bengaluru", "bangaluru": "bengaluru"}

_INDIA = re.compile(
    r"\b(india|bengaluru|bangalore|hyderabad|pune|mumbai|gurgaon|gurugram|new delhi|delhi|noida|chennai"
    r"|kolkata|ahmedabad|jaipur|kochi|coimbatore|indore|chandigarh|trivandrum|thiruvananthapuram|mysore|mysuru)\b",
    re.I,
)


def normalize_city(name: str) -> str:
    key = name.strip().lower()
    return _CITY_ALIASES.get(key, key)


def mentions_india(*texts: str | None) -> bool:
    return any(t and _INDIA.search(t) for t in texts)


def join_locations(*parts: str | None) -> str | None:
    """Join location fragments with " · ", dropping blanks and repeats."""
    seen = []
    for part in parts:
        text = clean_text(part, 200)
        if text and text.lower() not in (s.lower() for s in seen):
            seen.append(text)
    return " · ".join(seen) or None


def strip_html(value: object) -> str | None:
    """HTML (possibly entity-escaped, as Greenhouse sends it) to readable plain text."""
    if not isinstance(value, str):
        return None
    text = html.unescape(value)
    text = re.sub(r"(?i)<\s*(br|/p|/div|/li|/h\d)\s*/?>", "\n", text)
    text = re.sub(r"(?i)<\s*li[^>]*>", "• ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return clean_description(text)


# ---------------------------------------------------------------- URLs

_TRACKING_PARAMS = re.compile(r"^(utm_|ref$|source$|gclid$|fbclid$)", re.I)


def canonical_url(url: str | None) -> str | None:
    """Normalize URL variations: scheme, www, case of host, trailing slash, fragment, tracking params."""
    if not url or not isinstance(url, str):
        return None
    parts = urlsplit(url.strip())
    if not parts.netloc:
        return None
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    query = "&".join(
        pair for pair in sorted(parts.query.split("&"))
        if pair and not _TRACKING_PARAMS.match(pair.split("=", 1)[0])
    )
    return urlunsplit(("https", host, path, query, ""))


# ---------------------------------------------------------------- identity helpers

_COMPANY_SUFFIXES = re.compile(
    r"\b(private limited|pvt\.? ltd\.?|pvt|ltd\.?|limited|inc\.?|llc|llp|corp\.?|technologies|labs)\s*$", re.I
)
_NON_WORD = re.compile(r"[^\w]+")


def identity_text(value: str | None) -> str:
    """Aggressive normalization used only for comparing identities, never for display."""
    if not value:
        return ""
    text = html.unescape(value).lower()
    return _NON_WORD.sub(" ", text).strip()


def identity_company(value: str | None) -> str:
    text = identity_text(value)
    previous = None
    while previous != text:  # strip stacked suffixes such as "technologies pvt ltd"
        previous = text
        text = _COMPANY_SUFFIXES.sub("", text).strip()
    return text


def identity_location(value: str | None) -> str:
    text = identity_text(value)
    return " ".join(normalize_city(word) for word in text.split())
