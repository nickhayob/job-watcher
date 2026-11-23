"""Build data/history.csv from the raw files alone.

Run it with:  uv run python -m jobwatcher.build

The history depends only on the files in data/raw and on the rules in this
package (the converters and the title rule), so building it again gives the
same file, and a change to a rule applies to every day of the history.
"""

import argparse
import csv
from pathlib import Path

from . import store
from .convert import convert
from .roles import in_role
from .sources import BY_NAME

COLUMNS = [
    "posting_id",
    "source",
    "source_id",
    "employer",
    "title",
    "location",
    "department",
    "posted_date",
    "url",
    "in_role",
    "first_run",
    "first_seen",
    "last_seen",
    "status",
    "removed_date",
]


def _flag(value):
    return "true" if value else "false"


def apply_day(history, by_source, source, date, converted, is_first_file):
    """Apply one source's listing for one day to the history (in place)."""
    listed = set()
    ids = by_source.setdefault(source.name, set())
    for item in converted:
        posting_id = f"{source.name}:{item['source_id']}"
        if posting_id in listed:
            continue  # the board listed the same posting twice
        listed.add(posting_id)
        row = history.get(posting_id)
        if row is None:
            row = {
                "posting_id": posting_id,
                "source": source.name,
                "source_id": item["source_id"],
                "first_run": _flag(is_first_file),
                "first_seen": date,
                "removed_date": "",
            }
            history[posting_id] = row
            ids.add(posting_id)
        row["employer"] = source.employer
        for key in ("title", "location", "department", "posted_date", "url"):
            row[key] = item[key]
        row["in_role"] = _flag(in_role(item["title"]))
        row["last_seen"] = date
        row["status"] = "open"  # a removed posting listed again opens again
        row["removed_date"] = ""
    for posting_id in ids - listed:
        row = history[posting_id]
        if row["status"] == "open":
            row["status"] = "removed"
            row["removed_date"] = date


def build_history(data_dir=store.DATA_DIR, sources=None):
    """Return the history rows (sorted by posting_id) built from the raw files."""
    sources = BY_NAME if sources is None else {s.name: s for s in sources}
    history, by_source, first_file_seen = {}, {}, set()
    for date in store.raw_dates(data_dir):
        for name in store.raw_names(data_dir, date):
            source = sources.get(name)
            if source is None:
                continue  # a raw file for a source that is no longer watched
            converted = convert(source, store.read_raw(data_dir, date, name))
            apply_day(history, by_source, source, date, converted, name not in first_file_seen)
            first_file_seen.add(name)
    return [history[key] for key in sorted(history)]


def write_history(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_history(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser(description="Build data/history.csv from data/raw.")
    parser.add_argument("--data", default=str(store.DATA_DIR), help="data folder")
    args = parser.parse_args()
    rows = build_history(args.data)
    write_history(rows, Path(args.data) / "history.csv")
    print(f"wrote {len(rows)} postings to {Path(args.data) / 'history.csv'}")


if __name__ == "__main__":
    main()
