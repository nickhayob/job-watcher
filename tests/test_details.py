"""Descriptions, pay, exact places and details.csv."""

import csv
import json

import pytest

from jobwatcher import skills
from jobwatcher.build import DETAIL_COLUMNS, build_all, write_details, write_history
from jobwatcher.convert import annual, convert, skills_text, split_place
from jobwatcher.fetch import SourceError, fetch_source
from jobwatcher.sources import Source
from tests.conftest import FAKE

LEVER = Source("lev", "Lev", "lever", {"company": "lev"})
ASHBY = Source("ash", "Ash", "ashby", {"board": "ash"})
GREEN = Source("gh", "GH", "greenhouse", {"token": "gh"})
ORACLE = Source("jpm", "JPM", "oracle", {"host": "x.fa.oraclecloud.com", "site": "CX_1", "search": "analyst"})


# ---------- reading a description ----------
def test_skills_years_and_pay_from_a_description():
    html_text = (
        "&lt;p&gt;You have 3+ years of experience with Excel and SQL, plus financial modeling. "
        "Python is a plus. The annual salary range is $120,000 - $150,000.&lt;/p&gt;"
    )
    out = skills.describe(html_text)
    assert out["skills"] == {"excel": 1, "sql": 1, "python": 1, "modeling": 1}
    assert out["min_years"] == 3
    assert out["pay"] == [120000, 150000]


def test_pay_forms_and_rejects():
    assert skills.pay_range("Pay is $95K - $120K per year") == (95000, 120000)
    assert skills.pay_range("between $150,000 and $200,000") == (150000, 200000)
    assert skills.pay_range("a $5,000 - $8,000 signing bonus") is None  # too small to be a salary
    assert skills.pay_range("no pay listed") is None


def test_min_years_takes_the_smallest():
    text = "5+ years of experience in finance; at least 2 years experience with Excel"
    assert skills.min_years(text) == 2
    assert skills.min_years("our firm has 20 years of history") is None


def test_the_skills_list_is_valid_for_python_and_for_the_browser():
    entries = json.loads(skills.SKILLS_PATH.read_text())
    assert len(entries) >= 40
    assert len({e["id"] for e in entries}) == len(entries)
    for e in entries:  # lookbehind, named groups and inline flags do not work the same in JavaScript
        assert "(?<" not in e["pattern"] and "(?P" not in e["pattern"] and "(?i" not in e["pattern"]


# ---------- slimming raw responses ----------
def test_slim_replaces_long_descriptions_with_a_summary():
    gh = {"jobs": [{"id": 1, "title": "t", "content": "&lt;p&gt;Excel needed&lt;/p&gt;", "data_compliance": [{}],
                    "departments": [{"id": 1, "name": "Finance", "child_ids": [2], "parent_id": None}]}]}
    out = skills.slim(GREEN, gh)["jobs"][0]
    assert "content" not in out and "data_compliance" not in out
    assert out["_jw"]["skills"] == {"excel": 1}
    assert out["departments"] == [{"id": 1, "name": "Finance"}]

    lever = [{"id": "a", "text": "t", "description": "<p>SQL</p>", "descriptionPlain": "SQL and Python",
              "lists": [{"text": "x", "content": "<li>Tableau</li>"}], "additional": "<p>z</p>"}]
    out = skills.slim(LEVER, lever)[0]
    assert set(out) == {"id", "text", "_jw"} and set(out["_jw"]["skills"]) == {"sql", "python", "tableau"}

    ashby = {"jobs": [{"id": "a", "title": "t", "descriptionHtml": "<p>x</p>", "descriptionPlain": "Bloomberg terminal"}]}
    out = skills.slim(ASHBY, ashby)["jobs"][0]
    assert "descriptionHtml" not in out and out["_jw"]["skills"] == {"bloomberg": 1}


# ---------- pay and places per source ----------
def test_pay_normalising():
    assert annual(50, "1 HOUR") == 104000
    assert annual(10000, "1 MONTH") == 120000
    assert annual(120000, "per-year-salary") == 120000
    assert annual(None, "1 YEAR") == ""


def test_ashby_pay_and_exact_place():
    raw = {"jobs": [{
        "id": "1", "title": "Analyst", "location": "New York, NY (HQ)", "jobUrl": "u",
        "compensation": {"compensationTiers": [{"components": [
            {"compensationType": "EquityPercentage", "minValue": None},
            {"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD", "minValue": 211400, "maxValue": 290600},
        ]}]},
        "address": {"postalAddress": {"addressLocality": "New York City", "addressRegion": "NY", "addressCountry": "USA"}},
        "_jw": {"skills": {"sql": 2, "excel": 2, "python": 1}, "min_years": 4},
    }]}
    (row,) = convert(ASHBY, raw)
    assert (row["salary_min"], row["salary_max"], row["salary_currency"], row["salary_source"]) == ("211400", "290600", "USD", "listing")
    assert (row["place"], row["city"], row["region"], row["country"]) == ("New York City, NY, USA", "New York City", "NY", "USA")
    assert row["skills"] == "excel:2;sql:2;python:1" and row["min_years"] == "4"


def test_greenhouse_pay_listing_text_and_department():
    listed = {"jobs": [{"id": 1, "title": "t", "location": {"name": "Remote"}, "absolute_url": "u",
                        "departments": [{"name": "Finance"}],
                        "pay_input_ranges": [{"min_cents": 9000000, "max_cents": 12000000, "currency_type": "USD"}]}]}
    (row,) = convert(GREEN, listed)
    assert (row["salary_min"], row["salary_max"], row["salary_source"]) == ("90000", "120000", "listing")
    assert row["department"] == "Finance"

    from_text = {"jobs": [{"id": 2, "title": "t", "location": {"name": "NYC"}, "absolute_url": "u",
                           "pay_input_ranges": [], "_jw": {"pay": [100000, 130000]}}]}
    (row,) = convert(GREEN, from_text)
    assert (row["salary_min"], row["salary_currency"], row["salary_source"]) == ("100000", "USD", "text")

    (row,) = convert(GREEN, {"jobs": [{"id": 3, "title": "t", "absolute_url": "u"}]})
    assert row["salary_min"] == "" and row["salary_source"] == ""


def test_lever_salary_range_and_country():
    raw = [{"id": "a", "text": "t", "hostedUrl": "u", "country": "US",
            "categories": {"location": "Austin, TX"},
            "salaryRange": {"currency": "USD", "interval": "per-hour-wage", "min": 50, "max": 60}}]
    (row,) = convert(LEVER, raw)
    assert (row["salary_min"], row["salary_max"]) == ("104000", "124800")
    assert row["country"] == "US" and row["city"] == "Austin" and row["region"] == "TX"


def test_an_implausible_maximum_is_dropped():
    # a real Coinbase listing: minimum $152,405, maximum $179,300,152
    raw = {"jobs": [{"id": 1, "title": "t", "location": {"name": "Remote"}, "absolute_url": "u",
                     "pay_input_ranges": [{"min_cents": 15240500, "max_cents": 17930015200, "currency_type": "USD"}]}]}
    (row,) = convert(GREEN, raw)
    assert (row["salary_min"], row["salary_max"]) == ("152405", "152405")
    from jobwatcher.convert import sane_max
    assert sane_max(100000, 150000) == 150000 and sane_max(100000, 90000) == 100000 and sane_max("", 5) == 5


def test_split_place():
    assert split_place("Columbus, OH, United States") == ("Columbus", "OH", "United States")
    assert split_place("Singapore, Singapore") == ("Singapore", "Singapore", "")
    assert split_place("Remote") == ("Remote", "", "")
    assert skills_text({"sql": 1, "excel": 3}) == "excel:3;sql:1"


def test_oracle_conversion():
    raw = {"total": 1, "requisitions": [{
        "Id": "210804703", "Title": "Finance & Business Management - Analyst", "PostedDate": "2026-11-23",
        "PrimaryLocation": "Columbus, OH, United States", "JobFunction": "Finance",
        "_jw": {"skills": {"excel": 1}},
    }]}
    (row,) = convert(ORACLE, raw)
    assert row["source_id"] == "210804703" and row["posted_date"] == "2026-11-23"
    assert row["department"] == "Finance" and row["location"] == "Columbus, OH, United States"
    assert row["url"] == "https://x.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/210804703"
    assert (row["city"], row["region"], row["country"]) == ("Columbus", "OH", "United States")
    assert row["skills"] == "excel:1"


# ---------- fetching an Oracle board ----------
class FakeResponse:
    def __init__(self, payload):
        self.payload, self.status_code = payload, 200

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, total, available=None):
        self.total, self.available, self.calls = total, total if available is None else available, []

    def request(self, method, url, **kwargs):
        self.calls.append(url)
        offset = int(url.split("offset=")[1].split(",")[0])
        n = max(0, min(100, self.available - offset))
        reqs = [{"Id": str(i), "Title": "Analyst", "ShortDescriptionStr": "Excel"} for i in range(offset, offset + n)]
        return FakeResponse({"items": [{"TotalJobsCount": self.total, "requisitionList": reqs}]})


def test_oracle_pages_use_the_search_term_and_are_summarised():
    session = FakeSession(230)
    raw = fetch_source(ORACLE, session)
    assert len(raw["requisitions"]) == 230
    assert all("keyword=analyst" in c for c in session.calls) and len(session.calls) == 3
    assert raw["requisitions"][0]["_jw"]["skills"] == {"excel": 1}


def test_oracle_board_over_5000_needs_a_search_term_and_partial_paging_fails():
    with pytest.raises(SourceError, match="needs a search term"):
        fetch_source(ORACLE, FakeSession(6000))
    with pytest.raises(SourceError, match="stopped early"):
        fetch_source(ORACLE, FakeSession(500, available=100))


# ---------- details.csv ----------
def test_details_are_built_from_raw_files_and_follow_history(data_dir, tmp_path):
    from jobwatcher import store

    day1 = {"jobs": [{"id": 1, "title": "Financial Analyst", "location": {"name": "NYC"}, "absolute_url": "u1",
                      "_jw": {"skills": {"excel": 2}, "pay": [90000, 100000]}}]}
    day2 = {"jobs": [{"id": 1, "title": "Financial Analyst", "location": {"name": "NYC"}, "absolute_url": "u1",
                      "_jw": {"skills": {"excel": 2, "sql": 1}, "pay": [95000, 105000]}}]}
    store.write_raw(data_dir, "2026-11-01", "fake", day1)
    store.write_raw(data_dir, "2026-11-02", "fake", day2)
    history, details = build_all(data_dir, [FAKE])
    assert [d["posting_id"] for d in details] == [h["posting_id"] for h in history]
    assert details[0]["skills"] == "excel:2;sql:1" and details[0]["salary_min"] == "95000"  # the latest day wins

    write_details(details, tmp_path / "details.csv")
    write_history(history, tmp_path / "history.csv")
    again = build_all(data_dir, [FAKE])
    write_details(again[1], tmp_path / "again.csv")
    assert (tmp_path / "details.csv").read_bytes() == (tmp_path / "again.csv").read_bytes()  # rebuilds identically
    with open(tmp_path / "details.csv", newline="") as handle:
        assert next(csv.reader(handle)) == DETAIL_COLUMNS
    # history.csv keeps exactly its required columns
    with open(tmp_path / "history.csv", newline="") as handle:
        header = next(csv.reader(handle))
    assert "salary_min" not in header and header[0] == "posting_id" and len(header) == 15
