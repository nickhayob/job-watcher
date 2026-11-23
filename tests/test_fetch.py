"""Fetching: paging, empty boards and incomplete paging."""

import pytest

from jobwatcher import fetch
from jobwatcher.fetch import SourceError, fetch_source
from jobwatcher.sources import Source

WORKDAY = Source(
    "wd",
    "WD",
    "workday",
    {"host": "wd.wd5.myworkdayjobs.com", "tenant": "wd", "site": "Careers", "search": "analyst"},
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.handler(method, url, kwargs)


def workday_pages(total, available=None, total_on_first_page_only=False):
    available = total if available is None else available

    def handler(method, url, kwargs):
        body = kwargs["json"]
        start = body["offset"]
        n = max(0, min(body["limit"], available - start))
        jobs = [{"title": f"t{i}", "externalPath": f"/job/x/t{i}_R{i}", "bulletFields": [f"R{i}"]}
                for i in range(start, start + n)]
        shown = 0 if (total_on_first_page_only and start > 0) else total
        return FakeResponse({"total": shown, "jobPostings": jobs, "facets": [{"big": "x" * 10}]})

    return handler


def test_workday_pages_and_search_term():
    session = FakeSession(workday_pages(45))
    raw = fetch_source(WORKDAY, session)
    assert len(raw["jobPostings"]) == 45 and raw["total"] == 45
    assert "facets" not in raw
    assert [c[2]["json"]["offset"] for c in session.calls] == [0, 20, 40]
    assert all(c[2]["json"]["searchText"] == "analyst" for c in session.calls)
    assert session.calls[0][0] == "POST"


def test_workday_total_reported_on_the_first_page_only():
    # several real Workday boards return total=0 on every page after the first
    raw = fetch_source(WORKDAY, FakeSession(workday_pages(45, total_on_first_page_only=True)))
    assert len(raw["jobPostings"]) == 45 and raw["total"] == 45


def test_board_over_5000_needs_a_search_term():
    with pytest.raises(SourceError, match="needs a search term"):
        fetch_source(WORKDAY, FakeSession(workday_pages(5001)))


def test_incomplete_paging_fails_instead_of_returning_a_partial_board():
    with pytest.raises(SourceError, match="stopped early"):
        fetch_source(WORKDAY, FakeSession(workday_pages(100, available=20)))


def test_empty_board_is_a_failure():
    greenhouse = Source("g", "G", "greenhouse", {"token": "g"})
    with pytest.raises(SourceError, match="no postings"):
        fetch_source(greenhouse, FakeSession(lambda m, u, k: FakeResponse({"jobs": []})))


def test_http_error_is_a_failure(monkeypatch):
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    lever = Source("l", "L", "lever", {"company": "l"})
    with pytest.raises(SourceError, match="HTTP 404"):
        fetch_source(lever, FakeSession(lambda m, u, k: FakeResponse({}, status=404)))


def test_server_error_is_retried(monkeypatch):
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    answers = [FakeResponse({}, 503), FakeResponse([{"id": "1", "text": "x"}])]
    lever = Source("l", "L", "lever", {"company": "l"})
    session = FakeSession(lambda m, u, k: answers.pop(0))
    assert fetch_source(lever, session) == [{"id": "1", "text": "x"}]
    assert len(session.calls) == 2


def test_smartrecruiters_pages():
    source = Source("s", "S", "smartrecruiters", {"company": "Co"})

    def handler(method, url, kwargs):
        offset = int(url.split("offset=")[1])
        items = [{"id": str(i), "name": "n"} for i in range(offset, min(offset + 100, 130))]
        return FakeResponse({"totalFound": 130, "content": items})

    raw = fetch_source(source, FakeSession(handler))
    assert len(raw["content"]) == 130


def test_429_waits_for_retry_after_then_succeeds(monkeypatch):
    waits = []
    monkeypatch.setattr(fetch.time, "sleep", waits.append)

    class Throttled(FakeResponse):
        headers = {"Retry-After": "7"}

    answers = [Throttled({}, 429), FakeResponse({}, 429), FakeResponse([{"id": "1", "text": "x"}])]
    lever = Source("l", "L", "lever", {"company": "l"})
    assert fetch_source(lever, FakeSession(lambda m, u, k: answers.pop(0))) == [{"id": "1", "text": "x"}]
    assert waits == [7, 15]  # Retry-After first, then the growing backoff


def test_gives_up_after_the_last_retry(monkeypatch):
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    lever = Source("l", "L", "lever", {"company": "l"})
    session = FakeSession(lambda m, u, k: FakeResponse({}, 429))
    with pytest.raises(SourceError, match="HTTP 429"):
        fetch_source(lever, session)
    assert len(session.calls) == len(fetch.BACKOFF) + 1


def test_no_request_starts_after_the_deadline(monkeypatch):
    monkeypatch.setattr(fetch, "DEADLINE", 0)  # long past
    lever = Source("l", "L", "lever", {"company": "l"})
    session = FakeSession(lambda m, u, k: FakeResponse([{"id": "1", "text": "x"}]))
    with pytest.raises(SourceError, match="run time limit"):
        fetch_source(lever, session)
    assert session.calls == []
