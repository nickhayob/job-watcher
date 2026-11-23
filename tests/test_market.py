"""The Market page definitions, checked on a small history with known answers."""

from jobwatcher import market
from jobwatcher.build import build_history
from tests.conftest import FAKE, OTHER, gh

SOURCES = [FAKE, OTHER]


def history(data_dir, put):
    # day 1 is the baseline: fake:1, fake:2, other:9 are first-run postings
    put("2026-11-01", FAKE, gh((1, "Financial Analyst"), (2, "Chef")))
    put("2026-11-01", OTHER, gh((9, "Nurse")))
    # day 2: fake:3 is new (in role); fake:2 removed (first-run: no days-open)
    put("2026-11-02", FAKE, gh((1, "Financial Analyst"), (3, "Credit Analyst")))
    put("2026-11-02", OTHER, gh((9, "Nurse")))
    # day 4: fake:4 new; fake:3 removed after 2 days (seen day 2, removed day 4)
    put("2026-11-04", FAKE, gh((1, "Financial Analyst"), (4, "Cook")))
    put("2026-11-04", OTHER, gh((9, "Nurse"), (10, "Treasury Analyst")))
    # day 10: fake:4 removed after 6 days; other:10 still open
    put("2026-11-10", FAKE, gh((1, "Financial Analyst")))
    put("2026-11-10", OTHER, gh((9, "Nurse"), (10, "Treasury Analyst")))
    rows = build_history(data_dir, SOURCES)
    return [{**r} for r in rows]


def test_market_numbers(data_dir, put):
    rows = history(data_dir, put)
    m = market.compute(rows, "2026-11-10")

    assert m["dates"][0] == "2026-11-01" and m["dates"][-1] == "2026-11-10" and len(m["dates"]) == 10
    # new postings leave out first-run postings: fake:3 (day 2), fake:4 and other:10 (day 4)
    assert m["newAll"][1] == 1 and m["newAll"][3] == 2 and sum(m["newAll"]) == 3
    assert m["newRole"][1] == 1 and m["newRole"][3] == 1 and sum(m["newRole"]) == 2
    # removed: fake:2 on day 2, fake:3 on day 4, fake:4 on day 10
    assert m["removedPerDay"][1] == 1 and m["removedPerDay"][3] == 1 and m["removedPerDay"][9] == 1
    # open on day 10: fake:1, other:9, other:10
    assert m["openTotal"] == 3
    assert m["perEmployer"] == [["Other Co", 2], ["Fake Co", 1]]
    # days open: fake:3 -> 2 days, fake:4 -> 6 days (fake:2 is first-run, left out)
    assert sorted(m["daysOpen"]) == [2, 6] and m["daysOpenMedian"] == 4
    assert m["histogram"] == [0, 0, 1, 0, 1, 0, 0, 0]
    # share removed within seven days: postings first seen on or before day 3 (Nov 10 minus 7)
    # that are not first-run: only fake:3 (seen day 2, removed after 2 days)
    assert (m["shareNumerator"], m["shareDenominator"]) == (1, 1)
    assert m["shareRemovedWithin7"] == 1.0
    assert m["topLocations"] == [["Remote", 3]]


def test_no_history_yet(data_dir, put):
    put("2026-11-01", FAKE, gh((1, "A")))
    m = market.compute(build_history(data_dir, SOURCES), "2026-11-01")
    assert m["newAll"] == [0] and m["removedPerDay"] == [0]
    assert m["daysOpen"] == [] and m["daysOpenMedian"] is None
    assert m["shareRemovedWithin7"] is None
