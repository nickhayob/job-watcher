"""Convert each applicant tracking system's raw JSON to one set of columns.

Every converter returns a list of dicts. Each dict has the history columns
    source_id, title, location, department, posted_date, url
(the build adds employer and the other history columns) and the detail columns
    place, city, region, country, salary_min, salary_max, salary_currency,
    salary_source, min_years, skills
that go to data/details.csv. A column the source does not provide is left empty.
"""

import re
from datetime import datetime, timezone

COMMON = ["source_id", "title", "location", "department", "posted_date", "url"]
EXTRA = [
    "place", "city", "region", "country",
    "salary_min", "salary_max", "salary_currency", "salary_source", "min_years", "skills",
]

# how many of each unit make a year, for pay quoted by the hour, week or month
PER_YEAR = {"year": 1, "annual": 1, "month": 12, "week": 52, "day": 260, "hour": 2080}


def clean(value):
    """Collapse whitespace; None becomes an empty string."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _date(value):
    """YYYY-MM-DD from an ISO timestamp string (empty if missing)."""
    text = clean(value)
    return text[:10] if re.match(r"\d{4}-\d{2}-\d{2}", text) else ""


def annual(amount, interval):
    """A pay amount as a yearly amount, given words like '1 HOUR' or 'per-year-salary'."""
    if amount in (None, ""):
        return ""
    text = (interval or "").lower()
    factor = next((f for word, f in PER_YEAR.items() if word in text), 1)
    return int(round(float(amount) * factor))


def sane_max(low, high):
    """A pay range's maximum, or the minimum when the maximum is implausible.

    One real board listed a $152,405 minimum with a $179,300,152 maximum, so a
    maximum more than four times the minimum is treated as a typo.
    """
    if low in ("", None) or high in ("", None):
        return high
    return high if low <= high <= 4 * low else low


def skills_text(found):
    """{'excel': 2, 'sql': 1} as 'excel:2;sql:1', most-mentioned first."""
    ordered = sorted((found or {}).items(), key=lambda kv: (-kv[1], kv[0]))
    return ";".join(f"{k}:{v}" for k, v in ordered)


def split_place(place):
    """(city, region, country) from a place written 'City, Region, Country'."""
    parts = [p.strip() for p in (place or "").split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[0], parts[1], parts[-1]
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return (parts[0] if parts else ""), "", ""


def _row(source_id, title, location="", department="", posted_date="", url="", **extra):
    row = {
        "source_id": clean(source_id),
        "title": clean(title),
        "location": clean(location),
        "department": clean(department),
        "posted_date": posted_date,
        "url": clean(url),
    }
    row.update({key: "" for key in EXTRA})
    for key, value in extra.items():
        row[key] = clean(value) if key not in ("skills",) else value
    if not row["place"]:
        row["place"] = row["location"]
    if row["place"] and not row["city"]:
        city, region, country = split_place(row["place"])
        row["city"] = city
        row["region"] = row["region"] or region
        row["country"] = row["country"] or country
    return row


def _described(jw):
    """The columns that come from a description summary ('_jw')."""
    jw = jw or {}
    out = {"skills": skills_text(jw.get("skills")), "min_years": jw.get("min_years", "")}
    return out


def _text_pay(jw):
    """Pay found in the description text (a yearly dollar range)."""
    pay = (jw or {}).get("pay")
    if not pay:
        return {}
    return {"salary_min": pay[0], "salary_max": sane_max(pay[0], pay[1]), "salary_currency": "USD", "salary_source": "text"}


def convert_greenhouse(source, raw):
    rows = []
    for job in raw.get("jobs", []):
        departments = job.get("departments") or []
        extra = _described(job.get("_jw"))
        ranges = job.get("pay_input_ranges") or []
        if ranges and ranges[0].get("min_cents") is not None:
            r = ranges[0]
            extra.update(
                salary_min=int(r["min_cents"] / 100),
                salary_max=sane_max(int(r["min_cents"] / 100), int((r.get("max_cents") or r["min_cents"]) / 100)),
                salary_currency=r.get("currency_type") or "",
                salary_source="listing",
            )
        else:
            extra.update(_text_pay(job.get("_jw")))
        rows.append(
            _row(
                job["id"],
                job.get("title"),
                (job.get("location") or {}).get("name"),
                departments[0].get("name") if departments else "",
                _date(job.get("first_published")),
                job.get("absolute_url"),
                **extra,
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
        extra = _described(job.get("_jw"))
        salary = job.get("salaryRange") or {}
        if salary.get("min") is not None:
            extra.update(
                salary_min=annual(salary.get("min"), salary.get("interval")),
                salary_max=sane_max(annual(salary.get("min"), salary.get("interval")),
                                    annual(salary.get("max", salary.get("min")), salary.get("interval"))),
                salary_currency=salary.get("currency") or "",
                salary_source="listing",
            )
        else:
            extra.update(_text_pay(job.get("_jw")))
        rows.append(
            _row(
                job["id"],
                job.get("text"),
                location,
                cats.get("department") or cats.get("team"),
                posted,
                job.get("hostedUrl"),
                country=job.get("country") or "",
                **extra,
            )
        )
    return rows


def convert_ashby(source, raw):
    rows = []
    for job in raw.get("jobs", []):
        extra = _described(job.get("_jw"))
        salary = None
        for tier in (job.get("compensation") or {}).get("compensationTiers") or []:
            for part in tier.get("components") or []:
                if part.get("compensationType") == "Salary" and part.get("minValue") is not None:
                    salary = part
                    break
            if salary:
                break
        if salary:
            extra.update(
                salary_min=annual(salary["minValue"], salary.get("interval")),
                salary_max=sane_max(annual(salary["minValue"], salary.get("interval")),
                                    annual(salary.get("maxValue", salary["minValue"]), salary.get("interval"))),
                salary_currency=salary.get("currencyCode") or "",
                salary_source="listing",
            )
        else:
            extra.update(_text_pay(job.get("_jw")))
        address = (job.get("address") or {}).get("postalAddress") or {}
        city, region, country = (clean(address.get(k)) for k in ("addressLocality", "addressRegion", "addressCountry"))
        place = ", ".join(p for p in (city, region, country) if p) if city else ""
        rows.append(
            _row(
                job["id"],
                job.get("title"),
                job.get("location"),
                job.get("department") or job.get("team"),
                _date(job.get("publishedAt")),
                job.get("jobUrl"),
                place=place,
                city=city,
                region=region,
                country=country,
                **extra,
            )
        )
    return rows


def convert_smartrecruiters(source, raw):
    company = source.params["company"]
    rows = []
    for job in raw.get("content", []):
        loc = job.get("location") or {}
        country = (loc.get("country") or "").upper()
        location = loc.get("fullLocation") or ", ".join(
            p for p in (loc.get("city"), loc.get("region"), country) if p
        )
        city = clean(loc.get("city"))
        place = ", ".join(p for p in (city, clean(loc.get("region")), country) if p) if city else ""
        rows.append(
            _row(
                job["id"],
                job.get("name"),
                location,
                (job.get("department") or {}).get("label"),
                _date(job.get("releasedDate")),
                f"https://jobs.smartrecruiters.com/{company}/{job['id']}",
                place=place,
                city=city,
                region=loc.get("region") or "",
                country=country,
            )
        )
    return rows


def convert_oracle(source, raw):
    host, site = source.params["host"], source.params["site"]
    rows = []
    for job in raw.get("requisitions", []):
        place = job.get("PrimaryLocation") or ""
        rows.append(
            _row(
                job["Id"],
                job.get("Title"),
                place,
                job.get("JobFunction") or job.get("JobFamily"),
                _date(job.get("PostedDate")),
                f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{job['Id']}",
                place=place,
                **_described(job.get("_jw")),
            )
        )
    return rows


CONVERTERS = {
    "greenhouse": convert_greenhouse,
    "lever": convert_lever,
    "ashby": convert_ashby,
    "smartrecruiters": convert_smartrecruiters,
    "oracle": convert_oracle,
}


def convert(source, raw):
    """Convert one source's raw JSON to a list of common-column dicts."""
    return CONVERTERS[source.ats](source, raw)
