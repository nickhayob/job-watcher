"""Shared helpers: a tiny fake source and raw-file writers."""

import pytest

from jobwatcher import store
from jobwatcher.sources import Source

FAKE = Source("fake", "Fake Co", "greenhouse", {"token": "fake"})
OTHER = Source("other", "Other Co", "greenhouse", {"token": "other"})


def gh(*items):
    """A Greenhouse-style raw response from (id, title) pairs."""
    return {
        "jobs": [
            {
                "id": job_id,
                "title": title,
                "location": {"name": "Remote"},
                "absolute_url": f"https://example.com/{job_id}",
            }
            for job_id, title in items
        ]
    }


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def put(data_dir):
    def _put(date, source, raw):
        store.write_raw(data_dir, date, source.name, raw)

    return _put
