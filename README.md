# Job Watcher

[![Tests](https://github.com/nickhayob/job-watcher/actions/workflows/tests.yml/badge.svg)](https://github.com/nickhayob/job-watcher/actions/workflows/tests.yml)
[![Daily data](https://github.com/nickhayob/job-watcher/actions/workflows/daily.yml/badge.svg)](https://github.com/nickhayob/job-watcher/actions/workflows/daily.yml)

A tool that watches the job market for me. Every day, on its own, it pulls the open positions at 40 employers, compares them with what it saw the day before, records what is new and what is gone, and publishes the result to a website.

- **My role:** finance analyst (financial analyst, FP&A, credit, treasury, investment and similar analyst titles).
- **Site:** <https://nickhayob.github.io/job-watcher/>
- **Repository:** <https://github.com/nickhayob/job-watcher>

The pipeline is a Python program run once a day by GitHub Actions. The site is three static pages on GitHub Pages that read the two data files in the browser and do all calculations there. The site can be installed as an app and still opens offline.

## How it works

1. **Fetch.** Every source is called and what it returns is saved in `data/raw/<date>/<source>.json.gz`. A source that fails writes no raw file that day; one failing never stops the run. Failed sources are tried again after a pause. The result of every source (success or failure, with the error) is written to `data/raw/<date>/run.json`.
2. **Build.** `data/history.csv` is built from the raw files alone, so building it again gives the same file and a change to a rule applies to every day of the history.
3. **Status.** `data/status.json` describes the latest run.
4. **Issue.** A GitHub Issue titled with the date lists the new and removed postings, each with a link. The previous day's issue is closed. An issue is opened every day, even with no changes.
5. **Commit.** The raw files, history and status are committed and pushed (`Daily data <date>`).

A second run on the same day replaces that day's raw files, rebuilds the history, and updates that day's issue, so each day counts once.

### Rules for the history

For each source, day by day, in date order:

- A posting seen for the first time gets that day as `first_seen`.
- Every posting the source lists that day gets that day as `last_seen`.
- An open posting is marked `removed`, with that day as `removed_date`, when the source has a raw file for that day and no longer lists it. A day with no raw file for a source (the source failed) changes nothing for that source.
- A removed posting that is listed again becomes `open` again, with `removed_date` cleared and `first_seen` unchanged.
- `first_run` is `true` for postings listed in the first raw file of their source. Their start date is unknown, so the Market page leaves them out where a start date is needed.
- Rows are sorted by `posting_id` (`<source>:<the source's own id>`).

### Build the history from the raw files

```bash
uv run python -m jobwatcher.build
```

This rewrites `data/history.csv` from everything in `data/raw/`. Running it again produces an identical file.

## Sources

Every board returns JSON to a request with no login. The tool never reads a web page's HTML. No board comes close to 5,000 postings (the largest, ServiceNow, has about 1,000), so no search term is needed. The tool refuses a board over 5,000 postings unless a search term is set in `jobwatcher/sources.py` (a `search` value on a SmartRecruiters source).

Sixteen banks on Workday (Capital One, Wells Fargo, Mastercard and others) were tried first. Workday answered GitHub's servers with HTTP 429 and made one daily run take half an hour, so, as the project allows, those employers were replaced with the boards below, which answer in seconds.

| Source (`name`) | Employer | Applicant tracking system |
|---|---|---|
| `stripe` | Stripe | Greenhouse |
| `robinhood` | Robinhood | Greenhouse |
| `coinbase` | Coinbase | Greenhouse |
| `affirm` | Affirm | Greenhouse |
| `sofi` | SoFi | Greenhouse |
| `block` | Block | Greenhouse |
| `brex` | Brex | Greenhouse |
| `chime` | Chime | Greenhouse |
| `carta` | Carta | Greenhouse |
| `adyen` | Adyen | Greenhouse |
| `gusto` | Gusto | Greenhouse |
| `toast` | Toast | Greenhouse |
| `airbnb` | Airbnb | Greenhouse |
| `lyft` | Lyft | Greenhouse |
| `databricks` | Databricks | Greenhouse |
| `datadog` | Datadog | Greenhouse |
| `cloudflare` | Cloudflare | Greenhouse |
| `okta` | Okta | Greenhouse |
| `mongodb` | MongoDB | Greenhouse |
| `anthropic` | Anthropic | Greenhouse |
| `point72` | Point72 | Greenhouse |
| `ripple` | Ripple | Greenhouse |
| `payoneer` | Payoneer | Greenhouse |
| `monzo` | Monzo | Greenhouse |
| `betterment` | Betterment | Greenhouse |
| `billcom` | Bill | Greenhouse |
| `lendingtree` | LendingTree | Greenhouse |
| `palantir` | Palantir | Lever |
| `spotify` | Spotify | Lever |
| `nium` | Nium | Lever |
| `wealthfront` | Wealthfront | Lever |
| `crypto` | Crypto.com | Lever |
| `ramp` | Ramp | Ashby |
| `plaid` | Plaid | Ashby |
| `notion` | Notion | Ashby |
| `wealthsimple` | Wealthsimple | Ashby |
| `airwallex` | Airwallex | Ashby |
| `experian` | Experian | SmartRecruiters |
| `servicenow` | ServiceNow | SmartRecruiters |
| `equinox` | Equinox | SmartRecruiters |

Notes on the data:

- A board that suddenly returns no postings, or whose paging stops early, is treated as a failure, not as "every posting was removed".
- A run stops starting new requests after 25 minutes, so a throttled run still finishes and commits. (A normal run takes about 30 seconds.)
- Greenhouse's list has no department, so `department` is empty for those sources (and for any other field a board does not provide). Greenhouse's `first_published` is used for `posted_date` when it is present.
- Each raw file is exactly what the board returned, so files that include full job descriptions (Lever, Ashby) are the largest part of the repository.

## The title rule

A posting is **in my role** when its title:

1. contains the word **analyst**, and
2. contains a finance topic: *financial, finance, FP&A, investment(s), credit, treasury, valuation, equity research, corporate development, budget, forecasting*, and
3. contains none of these words: *fraud, crime(s), AML, KYC, compliance, sanction(s), cyber, security, software, systems analyst, clinical, nurse, intelligence*.

It looks only at the title and ignores case. So `Senior Financial Analyst`, `FP&A Analyst`, `Credit Analyst - Commercial Banking` and `Treasury Analyst` match; `Data Analyst`, `Financial Advisor`, `FP&A Manager` and `Fraud Analyst` do not. The rule is in `jobwatcher/roles.py` and is re-applied to every row each time the history is built.

## Files

| Path | What it does |
|---|---|
| `jobwatcher/sources.py` | The watch list: every employer, its applicant tracking system and board settings. |
| `jobwatcher/fetch.py` | Calls each ATS's JSON API with retries, back-off on HTTP 429, paging, completeness checks and the run time limit. |
| `jobwatcher/convert.py` | One converter per ATS that turns raw JSON into the common columns. |
| `jobwatcher/roles.py` | The title rule (`in_role`). |
| `jobwatcher/store.py` | Reads and writes the compressed raw files and each day's `run.json`. |
| `jobwatcher/build.py` | Builds `data/history.csv` from the raw files (`uv run python -m jobwatcher.build`). |
| `jobwatcher/status.py` | Builds `data/status.json`. |
| `jobwatcher/issues.py` | Opens the day's GitHub Issue and closes the previous one. |
| `jobwatcher/run.py` | The daily pipeline: fetch, build, status, issue, commit (`uv run python -m jobwatcher.run --commit`). |
| `jobwatcher/geocode.py` | Looks up map coordinates for locations (Open-Meteo geocoding; only city names are sent) and keeps them in `data/geo.json`. |
| `jobwatcher/market.py` | A Python version of the Market page's six calculations, used by the tests to check the page's definitions. |
| `tests/` | The pytest suite: converters for every source, the title rule, first-seen/last-seen/removed logic, fetching, the pipeline and the Market numbers. |
| `.github/workflows/daily.yml` | Runs the pipeline every day at 12:23 UTC (and on demand). |
| `.github/workflows/tests.yml` | Runs the tests on every push. |
| `data/raw/<date>/<source>.json.gz` | What each source returned that day, compressed. |
| `data/raw/<date>/run.json` | The result of every source that day, success or failure. |
| `data/history.csv` | One row per posting (see columns below). |
| `data/status.json` | The latest run: time, counts and the status of every source. |
| `data/geo.json` | Map coordinates for each location string (extra; not part of the history). `null` means the place could not be placed. |
| `index.html` | Today page: last run, source status, the four counts, new and removed postings. |
| `browse.html` | Browse page: filters, search, sort, apply links and a starred shortlist. |
| `map.html` | Map page: an interactive map (Leaflet and OpenStreetMap) of where the open postings are, with the same role and employer filters. |
| `market.html` | Market page: six findings, each with a chart, computed in the browser from the history. |
| `app.js` | Shared code: the navigation bar, data loading, CSV parsing, the shortlist. |
| `charts.js` | Small SVG bar charts (no library, so charts work offline). |
| `market-calc.js` | The six Market calculations. |
| `style.css` | The one set of fonts and colors for all pages (light and dark). |
| `manifest.webmanifest`, `sw.js`, `icons/` | Make the site installable and usable offline. |
| `tools/make_icons.py` | Draws the app icons. |
| `pyproject.toml`, `uv.lock` | Python dependencies (managed with uv). |

### `data/history.csv` columns

`posting_id`, `source`, `source_id`, `employer`, `title`, `location`, `department`, `posted_date`, `url`, `in_role`, `first_run`, `first_seen`, `last_seen`, `status`, `removed_date`. Dates are UTC dates (`YYYY-MM-DD`). A column a source does not provide is left empty.

### `data/status.json` keys

`run_time` (UTC), `first_run_date`, `days_with_success`, `open`, `new_today` (first-run postings left out), `removed_today`, and `sources`, a list of `{name, ok, count}`.

## The site

- **Today** shows the last run time, the status of every source, the four counts (days with a successful run, open, new today, removed today) and the lists of new and removed postings.
- **Browse** shows open postings with a switch between my role (the default) and all postings, filters for employer, location and days open, a title search, a sort by first-seen date, an apply link for every posting, and a star that saves a posting to a shortlist kept in the browser (it is still there after a reload).
- **Map** shows the open postings as circles on an interactive map, sized by count, with the same my-role/all and employer filters. Clicking a circle lists employers and posting links and links to Browse filtered to that place.
- **Market** has six sections, each with a heading that states the finding, a paragraph that explains it and a chart: new postings per day, removed postings per day, open postings per employer, days open (median), share removed within seven days, and top locations. Every number is computed in the browser from `data/history.csv`.
- The site is **installable** (web app manifest and service worker). When online, pages load the data files from the network; when offline, the site opens and shows the last data it loaded.

## Run it yourself

```bash
uv sync                                    # install dependencies
uv run pytest                              # run the tests
uv run python -m jobwatcher.run            # fetch, build, write status (no commit)
uv run python -m jobwatcher.build          # rebuild data/history.csv from data/raw
uv run python -m http.server 8000          # then open http://localhost:8000
```

Opening the issue and committing only happen in GitHub Actions (or with `--commit` and a `GITHUB_TOKEN`).
