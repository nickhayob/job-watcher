"""Fetching: paging, empty boards and incomplete paging."""

import pytest

from jobwatcher import fetch
from jobwatcher.fetch import SourceError, fetch_source
from jobwatcher.sources import Source

SMART = Source("s", "S", "smartrecruiters", {"company": "Co", "search": "analyst"})


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


def smart_pages(total, available=None):
    """A SmartRecruiters-style board that serves 100 postings per page."""
    available = total if available is None else available

    def handler(method, url, kwargs):
        offset = int(url.split("offset=")[1].split("&")[0])
        items = [{"id": str(i), "name": "n"} for i in range(offset, min(offset + 100, available))]
        return FakeResponse({"totalFound": total, "content": items})

    return handler


def test_smartrecruiters_pages_and_search_term():
    session = FakeSession(smart_pages(230))
    raw = fetch_source(SMART, session)
    assert len(raw["content"]) == 230 and raw["totalFound"] == 230
    assert [c[1].split("offset=")[1].split("&")[0] for c in session.calls] == ["0", "100", "200"]
    assert all(c[1].endswith("&q=analyst") for c in session.calls)


def test_board_over_5000_needs_a_search_term():
    with pytest.raises(SourceError, match="needs a search term"):
        fetch_source(SMART, FakeSession(smart_pages(5001)))


def test_incomplete_paging_fails_instead_of_returning_a_partial_board():
    with pytest.raises(SourceError, match="stopped early"):
        fetch_source(SMART, FakeSession(smart_pages(500, available=100)))


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
    assert [j["id"] for j in fetch_source(lever, session)] == ["1"]
    assert len(session.calls) == 2


def test_429_waits_for_retry_after_then_succeeds(monkeypatch):
    waits = []
    monkeypatch.setattr(fetch.time, "sleep", waits.append)

    class Throttled(FakeResponse):
        headers = {"Retry-After": "7"}

    answers = [Throttled({}, 429), FakeResponse({}, 429), FakeResponse([{"id": "1", "text": "x"}])]
    lever = Source("l", "L", "lever", {"company": "l"})
    assert [j["id"] for j in fetch_source(lever, FakeSession(lambda m, u, k: answers.pop(0)))] == ["1"]
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
