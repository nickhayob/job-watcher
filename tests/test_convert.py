"""Each source's raw JSON becomes the common columns."""

from jobwatcher.convert import COMMON, convert
from jobwatcher.sources import Source

GREENHOUSE = Source("acme", "Acme", "greenhouse", {"token": "acme"})
LEVER = Source("lev", "Lev", "lever", {"company": "lev"})
ASHBY = Source("ash", "Ash", "ashby", {"board": "ash"})
SMART = Source("smart", "Smart", "smartrecruiters", {"company": "SmartCo"})


def test_greenhouse():
    raw = {
        "jobs": [
            {
                "id": 8379685,
                "title": "  Senior  Financial Analyst ",
                "location": {"name": "Menlo Park, CA"},
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/8379685",
                "first_published": "2026-11-12T11:42:52-05:00",
            },
            {"id": 2, "title": "Engineer", "location": None, "absolute_url": "u2"},
        ]
    }
    rows = convert(GREENHOUSE, raw)
    assert list(rows[0]) == COMMON
    assert rows[0] == {
        "source_id": "8379685",
        "title": "Senior Financial Analyst",
        "location": "Menlo Park, CA",
        "department": "",
        "posted_date": "2026-11-12",
        "url": "https://boards.greenhouse.io/acme/jobs/8379685",
    }
    assert rows[1]["location"] == "" and rows[1]["posted_date"] == ""


def test_lever():
    raw = [
        {
            "id": "abc-123",
            "text": "FP&A Analyst",
            "categories": {"location": "New York, NY", "department": "Finance", "team": "FP&A"},
            "createdAt": 1792767640768,
            "hostedUrl": "https://jobs.lever.co/lev/abc-123",
        },
        {
            "id": "def",
            "text": "Analyst",
            "categories": {"allLocations": ["A", "B"], "team": "Ops"},
            "hostedUrl": "https://jobs.lever.co/lev/def",
        },
    ]
    rows = convert(LEVER, raw)
    assert rows[0]["source_id"] == "abc-123"
    assert rows[0]["location"] == "New York, NY"
    assert rows[0]["department"] == "Finance"
    assert rows[0]["posted_date"] == "2026-10-23"
    assert rows[0]["url"] == "https://jobs.lever.co/lev/abc-123"
    assert rows[1]["location"] == "A, B" and rows[1]["department"] == "Ops"
    assert rows[1]["posted_date"] == ""


def test_ashby():
    raw = {
        "jobs": [
            {
                "id": "34413f8d",
                "title": " Credit Analyst",
                "department": "Finance",
                "team": "Risk",
                "location": "New York, NY (HQ)",
                "publishedAt": "2026-04-07T17:12:35.753+00:00",
                "jobUrl": "https://jobs.ashbyhq.com/ash/34413f8d",
            }
        ]
    }
    (row,) = convert(ASHBY, raw)
    assert row == {
        "source_id": "34413f8d",
        "title": "Credit Analyst",
        "location": "New York, NY (HQ)",
        "department": "Finance",
        "posted_date": "2026-04-07",
        "url": "https://jobs.ashbyhq.com/ash/34413f8d",
    }


def test_smartrecruiters():
    raw = {
        "content": [
            {
                "id": "744000163289359",
                "name": "Treasury Analyst",
                "location": {"fullLocation": "Blumenau, SC, Brazil"},
                "department": {"label": "Finance"},
                "releasedDate": "2026-11-23T17:44:03.484Z",
            },
            {"id": "2", "name": "X", "location": {"city": "Dublin", "country": "ie"}},
        ]
    }
    rows = convert(SMART, raw)
    assert rows[0]["location"] == "Blumenau, SC, Brazil"
    assert rows[0]["department"] == "Finance"
    assert rows[0]["posted_date"] == "2026-11-23"
    assert rows[0]["url"] == "https://jobs.smartrecruiters.com/SmartCo/744000163289359"
    assert rows[1]["location"] == "Dublin, IE"
    assert rows[1]["department"] == ""
