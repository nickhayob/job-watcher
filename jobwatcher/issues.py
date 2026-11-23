"""Open one GitHub Issue per day that lists new and removed postings.

The issue is titled with the date. A second run on the same day updates that
day's issue, and opening a new day's issue closes the older ones.
"""

import re

import requests

API = "https://api.github.com"
DATE_TITLE = re.compile(r"\d{4}-\d{2}-\d{2}")
MAX_BODY = 60000  # GitHub allows 65,536 characters


def _link(row):
    title = re.sub(r"([\[\]\\|`*_<>])", r"\\\1", row["title"] or "(untitled)")
    detail = ", ".join(p for p in (row["employer"], row["location"]) if p)
    return f"- [{title}]({row['url']}) — {detail}" + (" ⭐ in role" if row["in_role"] == "true" else "")


def _section(heading, rows, budget):
    """Render a list of postings, in-role first, within a character budget."""
    ordered = sorted(rows, key=lambda r: (r["in_role"] != "true", r["employer"], r["title"]))
    lines = [f"## {heading} ({len(rows)})", ""]
    if not rows:
        lines.append("None.")
        return "\n".join(lines), 0
    used, shown = len("\n".join(lines)), 0
    for row in ordered:
        line = _link(row)
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
        shown += 1
    if shown < len(rows):
        lines.append("")
        lines.append(f"…and {len(rows) - shown} more (see `data/history.csv`).")
    return "\n".join(lines), shown


def render_body(date, new_rows, removed_rows, results, first_run):
    """Markdown body for the day's issue."""
    failed = [r["name"] for r in results if not r["ok"]]
    head = [f"Job Watcher run for **{date}** (UTC)."]
    if first_run:
        head.append(
            "This is the first run for these sources, so every posting found is the starting "
            "baseline. New and removed postings begin with the next run."
        )
    if failed:
        head.append("Sources that failed today: " + ", ".join(sorted(failed)) + ".")
    head_text = "\n\n".join(head)
    budget = (MAX_BODY - len(head_text)) // 2
    new_text, _ = _section("New postings", new_rows, budget)
    removed_text, _ = _section("Removed postings", removed_rows, budget)
    return f"{head_text}\n\n{new_text}\n\n{removed_text}\n"


class GitHub:
    def __init__(self, repo, token, session=None):
        self.repo = repo
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _call(self, method, path, **kwargs):
        response = self.session.request(method, f"{API}/repos/{self.repo}{path}", timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def issues(self, state):
        found, page = [], 1
        while True:
            batch = self._call(
                "GET", "/issues", params={"state": state, "per_page": 100, "page": page}
            )
            found.extend(i for i in batch if "pull_request" not in i)
            if len(batch) < 100:
                return found
            page += 1

    def sync_daily_issue(self, date, body):
        """Create or update the issue titled with the date; close the older ones."""
        existing = [i for i in self.issues("all") if i["title"] == date]
        if existing:
            number = existing[0]["number"]
            self._call("PATCH", f"/issues/{number}", json={"body": body, "state": "open"})
        else:
            number = self._call("POST", "/issues", json={"title": date, "body": body})["number"]
        for issue in self.issues("open"):
            if DATE_TITLE.fullmatch(issue["title"]) and issue["title"] != date:
                self._call("PATCH", f"/issues/{issue['number']}", json={"state": "closed"})
        return number
