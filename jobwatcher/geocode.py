"""Find map coordinates for the locations in the history.

The map page needs a latitude and longitude for each location string. They are
kept in data/geo.json ({"New York, NY": [40.71, -74.01], "Remote": null}), which
is separate from the history so the history still depends on the raw files alone.
Lookups use Open-Meteo's free geocoding API, which only ever sees a city name.
A location that cannot be placed is saved as null so it is not tried again.
"""

import argparse
import csv
import json
import re
import time
from collections import Counter
from pathlib import Path

import requests

SEARCH_URL = "https://geocoding-api.open-meteo.com/v1/search"
USER_AGENT = "job-watcher/1.0 (class project; looks up city names for a map)"

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def search_terms(location):
    """(city name, hint) from a location string, or None if it cannot be placed."""
    text = re.sub(r"\s+", " ", location or "").strip()
    if not text or re.search(r"remote|hybrid|anywhere|multiple|various|nationwide", text, re.I):
        return None
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts or len(parts[0]) > 40:
        return None
    return parts[0], (parts[1] if len(parts) > 1 else "")


def choose(results, hint):
    """Pick the search result that matches the hint (a state or a country)."""
    if not results:
        return None
    if not hint:
        return results[0]
    h = hint.strip().lower()
    state = STATES.get(hint.strip().upper())
    for r in results:
        if state and r.get("country_code") == "US" and (r.get("admin1") or "").lower() == state.lower():
            return r
        if not state and h in ((r.get("country") or "").lower(), (r.get("country_code") or "").lower(),
                               (r.get("admin1") or "").lower()):
            return r
    return None


def lookup_location(location, session=None):
    """Return [lat, lon] for a location string, None if it cannot be placed.

    Raises requests.RequestException when the service itself fails.
    """
    terms = search_terms(location)
    if terms is None:
        return None
    name, hint = terms
    session = session or requests
    response = session.get(
        SEARCH_URL,
        params={"name": name, "count": 10, "language": "en", "format": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    best = choose(response.json().get("results") or [], hint)
    return [round(best["latitude"], 3), round(best["longitude"], 3)] if best else None


def update_geo(rows, path, lookup=lookup_location, limit=100, pause=0.15):
    """Add up to `limit` new locations (most common first) to the geo file. Returns the dict."""
    path = Path(path)
    geo = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    counts = Counter(r["location"] for r in rows if r["status"] == "open" and r["location"])
    todo = [loc for loc, _ in counts.most_common() if loc not in geo][:limit]
    errors = 0
    for loc in todo:
        try:
            geo[loc] = lookup(loc)
            errors = 0
        except (requests.RequestException, ValueError, KeyError):
            errors += 1  # leave it for the next run
            if errors >= 3:
                break
        time.sleep(pause)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(geo.items())), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    return geo


def main():
    parser = argparse.ArgumentParser(description="Add map coordinates for the locations in a history file.")
    parser.add_argument("--history", default="data/history.csv")
    parser.add_argument("--geo", default="data/geo.json")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    with open(args.history, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    geo = update_geo(rows, args.geo, limit=args.limit)
    placed = sum(1 for v in geo.values() if v)
    print(f"{placed} of {len(geo)} locations placed in {args.geo}")


if __name__ == "__main__":
    main()
