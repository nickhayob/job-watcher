"""A Python version of the Market page's six calculations.

The Market page computes these numbers in the browser (market-calc.js). This
module follows the same definitions so the tests, and a check against the
real page, can confirm the page agrees with data/history.csv.
"""

from collections import Counter
from datetime import date, timedelta
from statistics import median

BUCKETS = [("0", 0, 0), ("1", 1, 1), ("2", 2, 2), ("3-4", 3, 4), ("5-7", 5, 7),
           ("8-14", 8, 14), ("15-30", 15, 30), ("31+", 31, 10**9)]


def _day(text):
    return date.fromisoformat(text)


def compute(rows, last_run):
    """rows: history rows as read by csv.DictReader. last_run: YYYY-MM-DD."""
    open_rows = [r for r in rows if r["status"] == "open"]
    not_first = [r for r in rows if r["first_run"] != "true"]

    start = min([r["first_seen"] for r in rows] + [last_run])
    dates = []
    d = _day(start)
    while d <= _day(last_run):
        dates.append(d.isoformat())
        d += timedelta(days=1)
    new_all = Counter(r["first_seen"] for r in not_first)
    new_role = Counter(r["first_seen"] for r in not_first if r["in_role"] == "true")
    removed = Counter(r["removed_date"] for r in rows if r["removed_date"])

    per_employer = sorted(Counter(r["employer"] for r in open_rows).items(), key=lambda kv: (-kv[1], kv[0]))

    closed = [r for r in not_first if r["removed_date"]]
    days_open = [(_day(r["removed_date"]) - _day(r["first_seen"])).days for r in closed]
    histogram = [sum(1 for v in days_open if lo <= v <= hi) for _, lo, hi in BUCKETS]

    cutoff = (_day(last_run) - timedelta(days=7)).isoformat()
    eligible = [r for r in not_first if r["first_seen"] <= cutoff]
    quick = [
        r for r in eligible
        if r["removed_date"] and (_day(r["removed_date"]) - _day(r["first_seen"])).days <= 7
    ]

    locations = sorted(
        Counter(r["location"] for r in open_rows if r["location"]).items(), key=lambda kv: (-kv[1], kv[0])
    )
    return {
        "dates": dates,
        "newAll": [new_all.get(x, 0) for x in dates],
        "newRole": [new_role.get(x, 0) for x in dates],
        "removedPerDay": [removed.get(x, 0) for x in dates],
        "perEmployer": [list(kv) for kv in per_employer],
        "openTotal": len(open_rows),
        "daysOpen": days_open,
        "daysOpenMedian": median(days_open) if days_open else None,
        "histogram": histogram,
        "shareDenominator": len(eligible),
        "shareNumerator": len(quick),
        "shareRemovedWithin7": len(quick) / len(eligible) if eligible else None,
        "topLocations": [list(kv) for kv in locations[:15]],
    }
