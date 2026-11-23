"""The daily pipeline.

Run it with:  uv run python -m jobwatcher.run [--commit]

Steps:
 1. Call every source and save what it returns in data/raw/<date>/<source>.json.gz.
    A source that fails writes no raw file; every result goes in run.json.
 2. Build data/history.csv from the raw files.
 3. Write data/status.json.
 4. Open the day's GitHub Issue (when a token is available).
 5. Commit and push the data (with --commit).
"""

import argparse
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import store
from .build import build_history, write_history
from .fetch import count_postings, fetch_source, new_session
from .issues import GitHub, render_body
from .sources import SOURCES
from .status import build_status, write_status

WORKERS = 8


def fetch_all(data_dir, date, sources, fetcher=fetch_source):
    """Fetch every source in parallel and save the raw files. Returns the results."""
    store.reset_day(data_dir, date)

    def one(source):
        started = time.time()
        try:
            raw = fetcher(source, new_session())
            count = count_postings(source, raw)
            store.write_raw(data_dir, date, source.name, raw)
            result = {"name": source.name, "ok": True, "count": count, "error": ""}
        except Exception as exc:  # one source failing must not stop the run
            result = {"name": source.name, "ok": False, "count": 0, "error": str(exc)[:300]}
        result["seconds"] = round(time.time() - started, 1)
        status = "ok" if result["ok"] else f"FAILED ({result['error']})"
        print(f"  {source.name:14} {result['count']:6} postings  {status}", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(one, sources))
    store.write_run_log(data_dir, date, results)
    return results


def run_pipeline(data_dir=store.DATA_DIR, now=None, sources=None, fetcher=fetch_source, github=None):
    """Steps 1 to 4. Returns (date, status, rows)."""
    sources = SOURCES if sources is None else sources
    now = now or datetime.now(timezone.utc)
    date = now.strftime("%Y-%m-%d")
    print(f"Run {now.isoformat(timespec='seconds')}: {len(sources)} sources")
    results = fetch_all(data_dir, date, sources, fetcher)
    rows = build_history(data_dir, sources)
    write_history(rows, Path(data_dir) / "history.csv")
    status = build_status(
        rows, now.strftime("%Y-%m-%dT%H:%M:%SZ"), date, results, data_dir, sources
    )
    write_status(status, Path(data_dir) / "status.json")
    print(
        f"{status['open']} open, {status['new_today']} new, {status['removed_today']} removed, "
        f"{sum(r['ok'] for r in results)}/{len(results)} sources ok"
    )
    if github is not None:
        new_rows = [r for r in rows if r["first_seen"] == date and r["first_run"] == "false"]
        removed_rows = [r for r in rows if r["status"] == "removed" and r["removed_date"] == date]
        body = render_body(date, new_rows, removed_rows, results, status["days_with_success"] <= 1)
        number = github.sync_daily_issue(date, body)
        print(f"issue #{number} updated for {date}")
    return date, status, rows


def commit_and_push(date, data_dir=store.DATA_DIR):
    """Commit the raw files, history and status, then push."""
    root = Path(data_dir).resolve().parent

    def git(*args, check=True):
        return subprocess.run(["git", *args], cwd=root, check=check, capture_output=True, text=True)

    if os.environ.get("GITHUB_ACTIONS"):
        git("config", "user.name", "github-actions[bot]")
        git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "data")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("nothing changed; no commit")
        return
    git("commit", "-m", f"Daily data {date}")
    git("pull", "--rebase", "--autostash")
    git("push")
    print(f"committed and pushed Daily data {date}")


def main():
    parser = argparse.ArgumentParser(description="Run the daily job watcher pipeline.")
    parser.add_argument("--commit", action="store_true", help="commit and push the data")
    args = parser.parse_args()
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    github = GitHub(repo, token) if repo and token else None
    if github is None:
        print("no GITHUB_REPOSITORY/GITHUB_TOKEN: skipping the issue")
    date, _, _ = run_pipeline(github=github)
    if args.commit:
        commit_and_push(date)


if __name__ == "__main__":
    main()
