"""Read and write the raw files under data/raw/<date>/<source>.json.gz.

A day's folder also holds run.json, the result of every source that day
(success or failure). The history build reads only the .json.gz files.
"""

import gzip
import json
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def raw_root(data_dir):
    return Path(data_dir) / "raw"


def day_dir(data_dir, date):
    return raw_root(data_dir) / date


def reset_day(data_dir, date):
    """Remove a day's raw files so a second run on the same day replaces them."""
    folder = day_dir(data_dir, date)
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)


def write_raw(data_dir, date, name, obj):
    folder = day_dir(data_dir, date)
    folder.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # mtime=0 keeps the compressed bytes identical for identical input
    (folder / f"{name}.json.gz").write_bytes(gzip.compress(payload, mtime=0))


def read_raw(data_dir, date, name):
    path = day_dir(data_dir, date) / f"{name}.json.gz"
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def raw_dates(data_dir):
    """Sorted dates that have at least one raw file."""
    root = raw_root(data_dir)
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir() and any(d.glob("*.json.gz")))


def raw_names(data_dir, date):
    """Sorted source names that have a raw file on a date."""
    return sorted(p.name[: -len(".json.gz")] for p in day_dir(data_dir, date).glob("*.json.gz"))


def write_run_log(data_dir, date, results):
    folder = day_dir(data_dir, date)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "run.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


def read_run_log(data_dir, date):
    path = day_dir(data_dir, date) / "run.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
