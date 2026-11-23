"""The daily run: a failed source, a second run on the same day, status and issues."""

import json
from datetime import datetime, timezone

from jobwatcher import store
from jobwatcher.build import read_history
from jobwatcher.issues import GitHub, render_body
from jobwatcher.run import run_pipeline
from tests.conftest import FAKE, OTHER, gh

SOURCES = [FAKE, OTHER]


def at(day, hour=12):
    return datetime(2026, 11, day, hour, 5, tzinfo=timezone.utc)


def fetcher_for(responses):
    """responses: source name -> raw JSON or an Exception to raise."""

    def fetcher(source, session):
        result = responses[source.name]
        if isinstance(result, Exception):
            raise result
        return result

    return fetcher


def test_failed_source_does_not_stop_the_run(data_dir):
    fetcher = fetcher_for({"fake": gh((1, "Financial Analyst")), "other": RuntimeError("boom")})
    date, status, rows = run_pipeline(data_dir, at(1), SOURCES, fetcher, retry_wait=0)
    assert date == "2026-11-01"
    assert not (data_dir / "raw" / date / "other.json.gz").exists()  # failure writes no raw file
    assert (data_dir / "raw" / date / "fake.json.gz").exists()
    log = {r["name"]: r for r in store.read_run_log(data_dir, date)}
    assert log["fake"]["ok"] and not log["other"]["ok"] and "boom" in log["other"]["error"]
    assert status["sources"] == [
        {"name": "fake", "ok": True, "count": 1},
        {"name": "other", "ok": False, "count": 0},
    ]
    assert (data_dir / "history.csv").exists() and (data_dir / "status.json").exists()


def test_status_counts_over_days(data_dir):
    run_pipeline(data_dir, at(1), SOURCES, fetcher_for({"fake": gh((1, "A"), (2, "B")), "other": gh((7, "G"))}))
    _, status, _ = run_pipeline(
        data_dir, at(2), SOURCES, fetcher_for({"fake": gh((1, "A"), (3, "C")), "other": gh((7, "G"))})
    )
    assert status["first_run_date"] == "2026-11-01"
    assert status["days_with_success"] == 2
    assert status["open"] == 3  # fake:1, fake:3, other:7
    assert status["new_today"] == 1  # fake:3 (first-run postings are left out)
    assert status["removed_today"] == 1  # fake:2
    assert status["run_time"] == "2026-11-02T12:05:00Z"
    saved = json.loads((data_dir / "status.json").read_text())
    assert saved == status
    assert list(saved) == [
        "run_time", "first_run_date", "days_with_success", "open",
        "new_today", "removed_today", "sources",
    ]


def test_second_run_same_day_replaces_the_day(data_dir):
    run_pipeline(data_dir, at(1, 8), SOURCES, fetcher_for({"fake": gh((1, "A"), (2, "B")), "other": gh((7, "G"))}))
    _, status, rows = run_pipeline(
        data_dir, at(1, 20), SOURCES, fetcher_for({"fake": gh((1, "A")), "other": gh((7, "G"))})
    )
    assert status["days_with_success"] == 1  # the day counts once
    assert [r["source_id"] for r in rows if r["source"] == "fake"] == ["1"]  # the earlier raw file is replaced


def test_failure_day_then_recovery(data_dir):
    run_pipeline(data_dir, at(1), SOURCES, fetcher_for({"fake": gh((1, "A")), "other": gh((7, "G"))}))
    run_pipeline(data_dir, at(2), SOURCES, fetcher_for({"fake": gh((1, "A")), "other": RuntimeError("down")}))
    _, status, rows = run_pipeline(
        data_dir, at(3), SOURCES, fetcher_for({"fake": gh((1, "A")), "other": gh((7, "G"))})
    )
    other = next(r for r in rows if r["posting_id"] == "other:7")
    assert other["status"] == "open" and other["removed_date"] == ""
    assert status["removed_today"] == 0
    assert status["days_with_success"] == 3


class FakeGitHub(GitHub):
    def __init__(self):
        self.issues_made = {}

    def sync_daily_issue(self, date, body):
        self.issues_made[date] = body
        return len(self.issues_made)


def test_issue_opened_every_day_even_with_no_changes(data_dir):
    github = FakeGitHub()
    same = {"fake": gh((1, "A")), "other": gh((7, "G"))}
    run_pipeline(data_dir, at(1), SOURCES, fetcher_for(same), github)
    run_pipeline(data_dir, at(2), SOURCES, fetcher_for(same), github)
    assert set(github.issues_made) == {"2026-11-01", "2026-11-02"}
    assert "None." in github.issues_made["2026-11-02"]
    assert "starting baseline" in github.issues_made["2026-11-01"]


def test_issue_body_lists_postings_with_links():
    new = [{"title": "Financial Analyst [II]", "url": "https://x/1", "employer": "Fake Co",
            "location": "NYC", "in_role": "true"}]
    removed = [{"title": "Chef", "url": "https://x/2", "employer": "Other Co",
                "location": "", "in_role": "false"}]
    body = render_body("2026-11-02", new, removed, [{"name": "fake", "ok": False}], False)
    assert "## New postings (1)" in body and "## Removed postings (1)" in body
    assert "[Financial Analyst \\[II\\]](https://x/1)" in body
    assert "(https://x/2)" in body
    assert "Sources that failed today: fake." in body


def test_issue_body_is_cut_to_fit():
    many = [{"title": f"Job {i}", "url": f"https://x/{i}", "employer": "E" * 50,
             "location": "L" * 50, "in_role": "false"} for i in range(3000)]
    body = render_body("2026-11-02", many, [], [], False)
    assert len(body) < 65000 and "more (see `data/history.csv`)" in body


class FakeSession:
    """Records the calls GitHub.sync_daily_issue makes."""

    def __init__(self, open_issues, all_issues):
        self.headers, self.calls = {}, []
        self.open_issues, self.all_issues = open_issues, all_issues

    def request(self, method, url, params=None, json=None, **kwargs):
        self.calls.append((method, url.split("/repos/r/r")[1], params, json))

        class Resp:
            def raise_for_status(self_inner):
                pass

            def json(self_inner):
                if method == "GET":
                    return self.open_issues if params["state"] == "open" else self.all_issues
                return {"number": 99}

        return Resp()


def test_sync_creates_issue_and_closes_previous_day():
    old = {"number": 5, "title": "2026-11-01"}
    session = FakeSession(open_issues=[old, {"number": 6, "title": "Bug report"}], all_issues=[old])
    number = GitHub("r/r", "token", session).sync_daily_issue("2026-11-02", "body")
    assert number == 99
    methods = [(c[0], c[1]) for c in session.calls]
    assert ("POST", "/issues") in methods
    assert ("PATCH", "/issues/5") in methods  # yesterday closed
    assert ("PATCH", "/issues/6") not in methods  # a non-date issue is left alone
    assert [c for c in session.calls if c[1] == "/issues/5"][0][3] == {"state": "closed"}


def test_sync_updates_todays_issue_on_a_second_run():
    today = {"number": 7, "title": "2026-11-02"}
    session = FakeSession(open_issues=[today], all_issues=[today])
    assert GitHub("r/r", "token", session).sync_daily_issue("2026-11-02", "new body") == 7
    assert not [c for c in session.calls if c[0] == "POST"]
    patch = [c for c in session.calls if c[1] == "/issues/7"]
    assert patch and patch[0][3] == {"body": "new body", "state": "open"}


def test_failed_source_is_retried_and_can_recover(data_dir):
    calls = {"other": 0}

    def fetcher(source, session):
        if source.name == "other":
            calls["other"] += 1
            if calls["other"] == 1:
                raise RuntimeError("HTTP 429")
            return gh((7, "G"))
        return gh((1, "A"))

    _, status, _ = run_pipeline(data_dir, at(1), SOURCES, fetcher, retry_wait=0)
    assert calls["other"] == 2
    assert [s["ok"] for s in status["sources"]] == [True, True]
    assert (data_dir / "raw" / "2026-11-01" / "other.json.gz").exists()
