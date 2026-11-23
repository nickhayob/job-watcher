"""Map coordinates for locations."""

import json

import requests

from jobwatcher.geocode import choose, lookup_location, search_terms, update_geo

RESULTS = [
    {"name": "McLean", "admin1": "Texas", "country": "United States", "country_code": "US", "latitude": 35.2, "longitude": -100.6},
    {"name": "McLean", "admin1": "Virginia", "country": "United States", "country_code": "US", "latitude": 38.934, "longitude": -77.177},
]


def test_search_terms():
    assert search_terms("McLean, VA") == ("McLean", "VA")
    assert search_terms("Hyderabad, India") == ("Hyderabad", "India")
    assert search_terms("Chicago") == ("Chicago", "")
    assert search_terms("Remote - USA") is None
    assert search_terms("US Remote") is None
    assert search_terms("") is None
    assert search_terms("BU3-Budapest-GTC White House Vaci ut 47 District XIII Budapest, Hungary") is None


def test_choose_matches_the_state_or_country_hint():
    assert choose(RESULTS, "VA")["admin1"] == "Virginia"
    assert choose(RESULTS, "TX")["admin1"] == "Texas"
    assert choose(RESULTS, "United States")["admin1"] == "Texas"  # first match for the country
    assert choose(RESULTS, "ZZ") is None  # a hint that matches nothing is not guessed
    assert choose(RESULTS, "")["admin1"] == "Texas"  # no hint: the top result
    assert choose([], "VA") is None


class FakeSession:
    def __init__(self, results):
        self.results, self.calls = results, []

    def get(self, url, params=None, **kwargs):
        self.calls.append(params)

        class Resp:
            def raise_for_status(self_inner):
                pass

            def json(self_inner):
                return {"results": self.results}

        return Resp()


def test_lookup_location():
    session = FakeSession(RESULTS)
    assert lookup_location("McLean, VA", session) == [38.934, -77.177]
    assert session.calls[0]["name"] == "McLean"
    assert lookup_location("Remote", session) is None
    assert len(session.calls) == 1  # remote never calls the service


def row(location, status="open"):
    return {"location": location, "status": status}


def test_update_geo_adds_new_places_most_common_first_and_keeps_old_ones(tmp_path):
    path = tmp_path / "geo.json"
    path.write_text(json.dumps({"Old, NY": [1, 2]}))
    seen = []

    def lookup(loc):
        seen.append(loc)
        return None if loc == "Remote" else [9.0, 8.0]

    rows = [row("A, VA"), row("B, VA"), row("B, VA"), row("Remote"), row("Old, NY"), row("Gone, VA", "removed")]
    geo = update_geo(rows, path, lookup, limit=2, pause=0)
    assert seen == ["B, VA", "A, VA"]  # most common first, capped at the limit, closed postings ignored
    assert geo["Old, NY"] == [1, 2] and geo["B, VA"] == [9.0, 8.0]
    assert "Remote" not in geo  # beyond the limit: left for the next run
    update_geo(rows, path, lookup, limit=5, pause=0)
    assert json.loads(path.read_text())["Remote"] is None  # saved as null so it is not tried again
    assert seen.count("B, VA") == 1


def test_update_geo_stops_after_repeated_service_errors_and_records_nothing_for_them(tmp_path):
    path = tmp_path / "geo.json"

    def broken(loc):
        raise requests.ConnectionError("down")

    geo = update_geo([row(f"C{i}, VA") for i in range(10)], path, broken, limit=10, pause=0)
    assert geo == {}
