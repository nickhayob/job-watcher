"""Build data/status.json, which describes the latest run."""

import json
from pathlib import Path

from . import store


def build_status(rows, run_time, run_date, results, data_dir=store.DATA_DIR, sources=None):
    """Return the status dict.

    rows: the history rows. run_time: ISO UTC time string. run_date: YYYY-MM-DD.
    results: the per-source results of the run, a list of dicts with
    name, ok and count.
    """
    dates = store.raw_dates(data_dir)
    by_name = {r["name"]: r for r in results}
    names = [s.name for s in sources] if sources is not None else [r["name"] for r in results]
    return {
        "run_time": run_time,
        "first_run_date": dates[0] if dates else run_date,
        "days_with_success": len(dates),
        "open": sum(1 for r in rows if r["status"] == "open"),
        "new_today": sum(
            1 for r in rows if r["first_seen"] == run_date and r["first_run"] == "false"
        ),
        "removed_today": sum(
            1 for r in rows if r["status"] == "removed" and r["removed_date"] == run_date
        ),
        "sources": [
            {
                "name": name,
                "ok": bool(by_name.get(name, {}).get("ok", False)),
                "count": int(by_name.get(name, {}).get("count", 0)),
            }
            for name in names
        ],
    }


def write_status(status, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
