"""Read skills, years of experience and pay out of a job description.

Job descriptions are long, so the pipeline does not keep them. At fetch time each
description is read once for the skills it names (using skills.json, the same
list the Resume page uses in the browser), the lowest "N years of experience"
it asks for, and any pay range written in the text. Those small results are
stored in the raw file under "_jw", and the long description text is dropped.
"""

import html
import json
import re
from pathlib import Path

SKILLS_PATH = Path(__file__).resolve().parent.parent / "skills.json"

_compiled = None


def dictionary():
    """The skills list as [(id, label, compiled pattern)]."""
    global _compiled
    if _compiled is None:
        entries = json.loads(SKILLS_PATH.read_text(encoding="utf-8"))
        _compiled = [(e["id"], e["label"], re.compile(e["pattern"], re.IGNORECASE)) for e in entries]
    return _compiled


def plain_text(markup):
    """Job-description HTML (possibly HTML-escaped, as Greenhouse sends it) as plain text."""
    text = html.unescape(markup or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def skills_in(text):
    """{skill id: number of mentions} for every skill the text names."""
    found = {}
    for skill_id, _, pattern in dictionary():
        n = len(pattern.findall(text))
        if n:
            found[skill_id] = n
    return found


_YEARS = [
    re.compile(r"(\d{1,2})\s*(?:\+|or more|plus)?\s*(?:years?|yrs?)[^.\n]{0,50}?experience", re.IGNORECASE),
    re.compile(r"experience[^.\n]{0,40}?(\d{1,2})\s*(?:\+|or more|plus)?\s*(?:years?|yrs?)", re.IGNORECASE),
]


def min_years(text):
    """The smallest 'N years of experience' the text asks for, or None."""
    values = [int(m) for pattern in _YEARS for m in pattern.findall(text) if 0 < int(m) < 30]
    return min(values) if values else None


_AMOUNT = r"\$\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK])"
_PAY = re.compile(_AMOUNT + r"\s*(?:-|–|—|to|and)\s*\$?\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK])")


def _amount(text):
    text = text.replace(",", "").replace(" ", "")
    return round(float(text[:-1]) * 1000) if text[-1] in "kK" else float(text)


def pay_range(text):
    """The first dollar range in the text that looks like a yearly salary: (low, high) or None."""
    for match in _PAY.finditer(text):
        low, high = _amount(match.group(1)), _amount(match.group(2))
        if 30000 <= low <= high <= 1_000_000:
            return (int(low), int(high))
    return None


def describe(markup):
    """What the pipeline keeps from one description: {'skills', 'min_years', 'pay'}."""
    text = plain_text(markup)
    out = {"skills": skills_in(text)}
    years = min_years(text)
    if years is not None:
        out["min_years"] = years
    pay = pay_range(text)
    if pay:
        out["pay"] = list(pay)
    return out


# --- slimming the raw responses ---------------------------------------------

_LEVER_DESCRIPTIONS = (
    "description", "descriptionPlain", "descriptionBody", "descriptionBodyPlain",
    "lists", "additional", "additionalPlain", "opening", "openingPlain",
)


def _strip_tree(items):
    """Greenhouse departments and offices carry long id lists; keep only what is useful."""
    return [{k: v for k, v in item.items() if k not in ("child_ids", "parent_id")} for item in items or []]


def slim(source, raw):
    """Replace each posting's long description with its small summary under '_jw'.

    Every other field the board returned is kept.
    """
    if source.ats == "greenhouse":
        for job in raw.get("jobs", []):
            job["_jw"] = describe(job.pop("content", ""))
            job.pop("data_compliance", None)
            for key in ("departments", "offices"):
                if key in job:
                    job[key] = _strip_tree(job[key])
    elif source.ats == "lever":
        for job in raw:
            text = job.get("descriptionPlain") or plain_text(job.get("description"))
            extra = " ".join(str(job.get(k) or "") for k in ("additionalPlain", "openingPlain"))
            lists = " ".join(f"{item.get('text', '')} {plain_text(item.get('content'))}" for item in job.get("lists") or [])
            job["_jw"] = describe(f"{text} {lists} {extra}")
            for key in _LEVER_DESCRIPTIONS:
                job.pop(key, None)
    elif source.ats == "ashby":
        for job in raw.get("jobs", []):
            job["_jw"] = describe(job.get("descriptionPlain") or job.get("descriptionHtml"))
            job.pop("descriptionHtml", None)
            job.pop("descriptionPlain", None)
    elif source.ats == "oracle":
        for item in raw.get("requisitions", []):
            item["_jw"] = describe(item.get("ShortDescriptionStr"))
    return raw
