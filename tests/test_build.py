"""First-seen, last-seen and removed logic, and rebuilding from raw files."""

from jobwatcher import roles
from jobwatcher.build import COLUMNS, build_history, read_history, write_history
from tests.conftest import FAKE, OTHER, gh

SOURCES = [FAKE, OTHER]


def by_id(rows):
    return {r["source_id"]: r for r in rows if r["source"] == "fake"}


def test_first_run_postings(data_dir, put):
    put("2026-11-01", FAKE, gh((1, "Financial Analyst"), (2, "Chef")))
    rows = by_id(build_history(data_dir, SOURCES))
    assert rows["1"]["posting_id"] == "fake:1"
    assert rows["1"]["first_run"] == "true"
    assert rows["1"]["first_seen"] == rows["1"]["last_seen"] == "2026-11-01"
    assert rows["1"]["status"] == "open" and rows["1"]["removed_date"] == ""
    assert rows["1"]["in_role"] == "true" and rows["2"]["in_role"] == "false"
    assert rows["1"]["employer"] == "Fake Co"


def test_new_posting_and_last_seen(data_dir, put):
    put("2026-11-01", FAKE, gh((1, "A")))
    put("2026-11-02", FAKE, gh((1, "A"), (2, "B")))
    put("2026-11-03", FAKE, gh((1, "A"), (2, "B")))
    rows = by_id(build_history(data_dir, SOURCES))
    assert rows["1"]["first_run"] == "true" and rows["1"]["last_seen"] == "2026-11-03"
    assert rows["2"]["first_run"] == "false"
    assert rows["2"]["first_seen"] == "2026-11-02" and rows["2"]["last_seen"] == "2026-11-03"


def test_removed(data_dir, put):
    put("2026-11-01", FAKE, gh((1, "A"), (2, "B")))
    put("2026-11-02", FAKE, gh((1, "A")))
    put("2026-11-03", FAKE, gh((1, "A")))
    rows = by_id(build_history(data_dir, SOURCES))
    assert rows["2"]["status"] == "removed"
    assert rows["2"]["removed_date"] == "2026-11-02"  # the first day it was missing
    assert rows["2"]["last_seen"] == "2026-11-01"
    assert rows["1"]["status"] == "open"


def test_reopened_keeps_first_seen(data_dir, put):
    put("2026-11-01", FAKE, gh((1, "A")))
    put("2026-11-02", FAKE, gh((2, "B")))
    put("2026-11-03", FAKE, gh((1, "A"), (2, "B")))
    row = by_id(build_history(data_dir, SOURCES))["1"]
    assert row["status"] == "open" and row["removed_date"] == ""
    assert row["first_seen"] == "2026-11-01" and row["last_seen"] == "2026-11-03"
    assert row["first_run"] == "true"


def test_failed_source_day_removes_nothing(data_dir, put):
    # no raw file for FAKE on 11-02 (the source failed), but OTHER has one
    put("2026-11-01", FAKE, gh((1, "A")))
    put("2026-11-02", OTHER, gh((9, "Z")))
    put("2026-11-03", FAKE, gh((1, "A")))
    rows = build_history(data_dir, SOURCES)
    row = by_id(rows)["1"]
    assert row["status"] == "open" and row["last_seen"] == "2026-11-03"
    # OTHER's first raw file is 11-02, so its posting is a first-run posting
    assert next(r for r in rows if r["source"] == "other")["first_run"] == "true"


def test_first_run_is_per_source(data_dir, put):
    put("2026-11-01", FAKE, gh((1, "A")))
    put("2026-11-02", FAKE, gh((1, "A")))
    put("2026-11-02", OTHER, gh((5, "E")))
    put("2026-11-03", OTHER, gh((5, "E"), (6, "F")))
    rows = {r["posting_id"]: r for r in build_history(data_dir, SOURCES)}
    assert rows["other:5"]["first_run"] == "true"
    assert rows["other:6"]["first_run"] == "false"


def test_duplicate_listing_counts_once(data_dir, put):
    put("2026-11-01", FAKE, gh((1, "A"), (1, "A")))
    assert len(build_history(data_dir, SOURCES)) == 1


def test_sorted_by_posting_id(data_dir, put):
    put("2026-11-01", OTHER, gh((3, "x")))
    put("2026-11-01", FAKE, gh((2, "x"), (10, "x"), (1, "x")))
    ids = [r["posting_id"] for r in build_history(data_dir, SOURCES)]
    assert ids == sorted(ids)


def test_title_and_fields_update(data_dir, put):
    put("2026-11-01", FAKE, gh((1, "Analyst")))
    put("2026-11-02", FAKE, gh((1, "Financial Analyst")))
    row = by_id(build_history(data_dir, SOURCES))["1"]
    assert row["title"] == "Financial Analyst" and row["in_role"] == "true"


def test_rebuild_is_identical_and_rule_change_applies_to_all_days(data_dir, put, tmp_path, monkeypatch):
    put("2026-11-01", FAKE, gh((1, "Marketing Analyst")))
    put("2026-11-02", FAKE, gh((1, "Marketing Analyst"), (2, "Other Analyst")))
    first = tmp_path / "a.csv"
    write_history(build_history(data_dir, SOURCES), first)
    write_history(build_history(data_dir, SOURCES), tmp_path / "b.csv")
    assert first.read_bytes() == (tmp_path / "b.csv").read_bytes()
    assert {r["in_role"] for r in read_history(first)} == {"false"}

    # change the title rule: every day of history follows it
    monkeypatch.setattr("jobwatcher.build.in_role", lambda title: "Analyst" in title)
    write_history(build_history(data_dir, SOURCES), tmp_path / "c.csv")
    assert {r["in_role"] for r in read_history(tmp_path / "c.csv")} == {"true"}
    assert roles.in_role("Marketing Analyst") is False  # the real rule is untouched


def test_csv_columns_and_empty_values(data_dir, put, tmp_path):
    put("2026-11-01", FAKE, gh((1, "Analyst, Finance")))
    path = tmp_path / "history.csv"
    write_history(build_history(data_dir, SOURCES), path)
    header = path.read_text().splitlines()[0].split(",")
    assert header == COLUMNS
    row = read_history(path)[0]
    assert row["department"] == "" and row["posted_date"] == "" and row["removed_date"] == ""
