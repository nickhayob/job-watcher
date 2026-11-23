"""Call each employer's job board and return the JSON it sends.

Every board is read with a plain request and no login. A board that fails
raises an error; the caller records the failure and carries on with the rest.
"""

import time
from urllib.parse import quote

import requests

USER_AGENT = "job-watcher/1.0 (class project; reads public job boards once a day)"
TIMEOUT = (10, 60)  # connect, read
RETRIES = 3
MAX_POSTINGS = 5000  # a board larger than this must be read with a search term
WORKDAY_PAGE = 20  # Workday returns at most 20 postings per request
SMARTRECRUITERS_PAGE = 100


class SourceError(Exception):
    """A source could not be read."""


def new_session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session


def _request_json(session, method, url, **kwargs):
    """Request JSON, retrying on network errors, 429 and 5xx."""
    last = None
    for attempt in range(RETRIES):
        try:
            response = session.request(method, url, timeout=TIMEOUT, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                last = f"HTTP {response.status_code}"
            elif response.status_code != 200:
                raise SourceError(f"HTTP {response.status_code} from {url}")
            else:
                return response.json()
        except SourceError:
            raise
        except (requests.RequestException, ValueError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(2 * (attempt + 1))
    raise SourceError(f"{last} from {url}")


def fetch_greenhouse(source, session):
    token = source.params["token"]
    data = _request_json(session, "GET", f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    if not isinstance(data, dict) or "jobs" not in data:
        raise SourceError("unexpected Greenhouse response")
    return data


def fetch_lever(source, session):
    company = source.params["company"]
    data = _request_json(session, "GET", f"https://api.lever.co/v0/postings/{company}?mode=json")
    if not isinstance(data, list):
        raise SourceError("unexpected Lever response")
    return data


def fetch_ashby(source, session):
    board = source.params["board"]
    data = _request_json(session, "GET", f"https://api.ashbyhq.com/posting-api/job-board/{board}")
    if not isinstance(data, dict) or "jobs" not in data:
        raise SourceError("unexpected Ashby response")
    return data


def _check_complete(label, got, total):
    """A board that stops paging early would look like mass removals."""
    if got < 0.9 * total:
        raise SourceError(f"{label} paging stopped early: {got} of {total} postings")


def fetch_smartrecruiters(source, session):
    company = source.params["company"]
    base = f"https://api.smartrecruiters.com/v1/companies/{company}/postings"
    content, offset, total = [], 0, None
    while total is None or offset < total:
        page = _request_json(
            session, "GET", f"{base}?limit={SMARTRECRUITERS_PAGE}&offset={offset}"
        )
        total = page.get("totalFound", 0)
        if total > MAX_POSTINGS:
            raise SourceError(f"{total} postings: more than {MAX_POSTINGS}, needs a search term")
        batch = page.get("content", [])
        if not batch:
            break
        content.extend(batch)
        offset += SMARTRECRUITERS_PAGE
    _check_complete("SmartRecruiters", len(content), total or 0)
    return {"totalFound": total or 0, "content": content}


def fetch_workday(source, session):
    p = source.params
    url = f"https://{p['host']}/wday/cxs/{p['tenant']}/{quote(p['site'])}/jobs"
    postings, offset, total = [], 0, None
    while total is None or offset < total:
        body = {
            "appliedFacets": {},
            "limit": WORKDAY_PAGE,
            "offset": offset,
            "searchText": p.get("search", ""),
        }
        page = _request_json(session, "POST", url, json=body)
        # some Workday boards report the total on the first page only
        if total is None or page.get("total"):
            total = page.get("total", 0)
        if total > MAX_POSTINGS:
            raise SourceError(f"{total} postings: more than {MAX_POSTINGS}, needs a search term")
        batch = page.get("jobPostings", [])
        if not batch:
            break
        postings.extend(batch)
        offset += WORKDAY_PAGE
    _check_complete("Workday", len(postings), total or 0)
    # the facet counts in each response are not postings, so they are not kept
    return {"total": total or 0, "jobPostings": postings}


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "workday": fetch_workday,
}


def count_postings(source, raw):
    """How many postings a raw response holds."""
    if source.ats == "lever":
        return len(raw)
    if source.ats == "greenhouse" or source.ats == "ashby":
        return len(raw.get("jobs", []))
    if source.ats == "smartrecruiters":
        return len(raw.get("content", []))
    return len(raw.get("jobPostings", []))


def fetch_source(source, session=None):
    """Return a source's raw JSON. An empty board counts as a failure.

    A board that suddenly lists nothing is far more likely to be an outage
    than an employer with no jobs, and treating it as empty would mark every
    posting removed.
    """
    session = session or new_session()
    raw = FETCHERS[source.ats](source, session)
    if count_postings(source, raw) == 0:
        raise SourceError("board returned no postings")
    return raw
