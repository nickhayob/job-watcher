"""Convert each applicant tracking system's raw JSON to one set of columns.

Every converter returns a list of dicts with these keys:
source_id, title, location, department, posted_date, url
(employer and the other history columns are added by the build).
A column the source does not provide is left as an empty string.
"""

import re
from datetime import datetime, timezone

COMMON = ["source_id", "title", "location", "department", "posted_date", "url"]


def clean(value):
    """Collapse whitespace; None becomes an empty string."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _date(value):
    """YYYY-MM-DD from an ISO timestamp string (empty if missing)."""
    text = clean(value)
    return text[:10] if re.match(r"\d{4}-\d{2}-\d{2}", text) else ""


def _row(source_id, title, location="", department="", posted_date="", url=""):
    return {
        "source_id": clean(source_id),
        "title": clean(title),
        "location": clean(location),
        "department": clean(department),
        "posted_date": posted_date,
        "url": clean(url),
    }


def convert_greenhouse(source, raw):
    rows = []
    for job in raw.get("jobs", []):
        rows.append(
            _row(
                job["id"],
                job.get("title"),
                (job.get("location") or {}).get("name"),
                "",  # the list endpoint has no department
                _date(job.get("first_published")),
                job.get("absolute_url"),
            )
        )
    return rows


def convert_lever(source, raw):
    rows = []
    for job in raw:
        cats = job.get("categories") or {}
        location = cats.get("location") or ", ".join(cats.get("allLocations") or [])
        created = job.get("createdAt")
        posted = ""
        if isinstance(created, (int, float)):
            posted = datetime.fromtimestamp(created / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        rows.append(
            _row(
                job["id"],
                job.get("text"),
                location,
                cats.get("department") or cats.get("team"),
                posted,
                job.get("hostedUrl"),
            )
        )
    return rows


def convert_ashby(source, raw):
    rows = []
    for job in raw.get("jobs", []):
        rows.append(
            _row(
                job["id"],
                job.get("title"),
                job.get("location"),
                job.get("department") or job.get("team"),
                _date(job.get("publishedAt")),
                job.get("jobUrl"),
            )
        )
    return rows


def convert_smartrecruiters(source, raw):
    company = source.params["company"]
    rows = []
    for job in raw.get("content", []):
        loc = job.get("location") or {}
        location = loc.get("fullLocation") or ", ".join(
            p for p in (loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()) if p
        )
        rows.append(
            _row(
                job["id"],
                job.get("name"),
                location,
                (job.get("department") or {}).get("label"),
                _date(job.get("releasedDate")),
                f"https://jobs.smartrecruiters.com/{company}/{job['id']}",
            )
        )
    return rows


_MULTI_LOCATION = re.compile(r"\d+ Locations?", re.IGNORECASE)


def workday_location(locations_text, external_path):
    """Workday shows '2 Locations' for multi-location postings.

    In that case use the first location, which is the second segment of the
    posting's URL path (for example /job/McLean-VA/Title_R1 gives 'McLean, VA').
    """
    text = clean(locations_text)
    if text and not _MULTI_LOCATION.fullmatch(text):
        return text
    parts = (external_path or "").split("/")
    if len(parts) > 2 and parts[2]:
        slug = parts[2]
        if "---" in slug:  # for example Remote---US
            return clean(slug.replace("---", "\0").replace("-", " ").replace("\0", " - "))
        return re.sub(r" ([A-Z]{2})$", r", \1", clean(slug.replace("-", " ")))
    return text


def convert_workday(source, raw):
    host = source.params["host"]
    site = source.params["site"]
    rows = []
    for job in raw.get("jobPostings", []):
        path = job.get("externalPath") or ""
        bullets = job.get("bulletFields") or []
        source_id = bullets[0] if bullets else path
        rows.append(
            _row(
                source_id,
                job.get("title"),
                workday_location(job.get("locationsText"), path),
                "",  # the list endpoint has no department
                "",  # it only says 'Posted Today' / '30+ Days Ago'
                f"https://{host}/en-US/{site}{path}",
            )
        )
    return rows


CONVERTERS = {
    "greenhouse": convert_greenhouse,
    "lever": convert_lever,
    "ashby": convert_ashby,
    "smartrecruiters": convert_smartrecruiters,
    "workday": convert_workday,
}


def convert(source, raw):
    """Convert one source's raw JSON to a list of common-column dicts."""
    return CONVERTERS[source.ats](source, raw)
