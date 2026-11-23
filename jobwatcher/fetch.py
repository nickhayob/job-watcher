"""Call each employer's job board and return the JSON it sends.

Every board is read with a plain request and no login. A board that fails
raises an error; the caller records the failure and carries on with the rest.
"""

import time
from urllib.parse import quote

import requests

from .skills import slim

USER_AGENT = "job-watcher/1.0 (class project; reads public job boards once a day)"
TIMEOUT = (10, 60)  # connect, read
BACKOFF = [5, 15, 30, 60]  # seconds to wait before each retry
DEADLINE = None  # time.time() after which no new request starts (set by the run)
MAX_POSTINGS = 5000  # a board larger than this must be read with a search term
SMARTRECRUITERS_PAGE = 100
ORACLE_PAGE = 100


class SourceError(Exception):
    """A source could not be read."""


def new_session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session


def _wait_time(response, attempt):
    """Seconds to wait before a retry; honour Retry-After when the server sends it."""
    retry_after = getattr(response, "headers", {}).get("Retry-After") if response is not None else None
    try:
        if retry_after:
            return min(float(retry_after), 120)
    except ValueError:
        pass
    return BACKOFF[min(attempt, len(BACKOFF) - 1)]


def _request_json(session, method, url, **kwargs):
    """Request JSON, retrying on network errors, 429 and 5xx with a growing wait."""
    last = None
    for attempt in range(len(BACKOFF) + 1):
        if DEADLINE is not None and time.time() > DEADLINE:
            raise SourceError("run time limit reached before this source finished")
        response = None
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
        if attempt < len(BACKOFF):
            time.sleep(_wait_time(response, attempt))
    raise SourceError(f"{last} from {url}")


def fetch_greenhouse(source, session):
    token = source.params["token"]
    data = _request_json(session, "GET", f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true&pay_transparency=true")
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
    data = _request_json(session, "GET", f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true")
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
    search = source.params.get("search")  # a board over 5,000 postings is read with a search term
    extra = f"&q={quote(search)}" if search else ""
    content, offset, total = [], 0, None
    while total is None or offset < total:
        page = _request_json(
            session, "GET", f"{base}?limit={SMARTRECRUITERS_PAGE}&offset={offset}{extra}"
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


def fetch_oracle(source, session):
    """Oracle Recruiting Cloud boards (for example JPMorgan Chase).

    These boards can hold thousands of postings, so they are read with a search
    term (params['search']) and refused if even that returns more than 5,000.
    """
    p = source.params
    base = f"https://{p['host']}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    search = quote(p.get("search", ""))
    items, offset, total = [], 0, None
    while total is None or offset < total:
        finder = f"findReqs;siteNumber={p['site']},limit={ORACLE_PAGE},offset={offset},keyword={search},sortBy=POSTING_DATES_DESC"
        page = _request_json(session, "GET", f"{base}?onlyData=true&expand=requisitionList.secondaryLocations&finder={finder}")
        head = (page.get("items") or [{}])[0]
        total = head.get("TotalJobsCount", 0)
        if total > MAX_POSTINGS:
            raise SourceError(f"{total} postings: more than {MAX_POSTINGS}, needs a search term")
        batch = head.get("requisitionList", [])
        if not batch:
            break
        items.extend(batch)
        offset += ORACLE_PAGE
    _check_complete("Oracle", len(items), total or 0)
    return {"total": total or 0, "requisitions": items}


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "oracle": fetch_oracle,
}


def count_postings(source, raw):
    """How many postings a raw response holds."""
    if source.ats == "lever":
        return len(raw)
    if source.ats == "greenhouse" or source.ats == "ashby":
        return len(raw.get("jobs", []))
    if source.ats == "oracle":
        return len(raw.get("requisitions", []))
    return len(raw.get("content", []))


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
    return slim(source, raw)
