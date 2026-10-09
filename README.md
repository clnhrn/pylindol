# pylindol

[![CI](https://github.com/clnhrn/pylindol/actions/workflows/ci.yml/badge.svg)](https://github.com/clnhrn/pylindol/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/pylindol)](https://pypi.org/project/pylindol/)
[![Python versions](https://img.shields.io/pypi/pyversions/pylindol)](https://pypi.org/project/pylindol/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/clnhrn/pylindol/blob/main/LICENSE)

pylindol scrapes earthquake data from the
[Philippine Institute of Volcanology and Seismology (PHIVOLCS)](https://earthquake.phivolcs.dost.gov.ph)
website into clean, typed pandas DataFrames. It works as a Python library and
as a command line tool, and covers every month PHIVOLCS has published since
January 2017.

![PHIVOLCS earthquakes in August 2025, plotted by location, depth and magnitude](https://raw.githubusercontent.com/clnhrn/pylindol/main/docs/map.png)

<sub>Made with [`examples/plot_map.py`](https://github.com/clnhrn/pylindol/blob/main/examples/plot_map.py).</sub>

## Installation

```bash
pip install pylindol
# or
uv add pylindol
```

For Parquet output, install the extra: `pip install "pylindol[parquet]"`.

Requires Python 3.11 or later.

## Command line usage

```bash
pylindol                                 # current month, saved to data/
pylindol --month 8 --year 2025           # a past month
pylindol --start 2025-01 --end 2025-06   # a range of months, in one file
pylindol --month 8 --year 2025 --format json --output-path archive
pylindol --month 8 --year 2025 --stdout | head   # print instead of saving
```

| Option | Description |
| --- | --- |
| `--month`, `--year` | Month to scrape. Defaults to the current month (Philippine time). |
| `--start`, `--end` | Range of months to scrape, as `YYYY-MM`. |
| `--format` | `csv` (default), `json` or `parquet`. |
| `--output-path` | Directory to save to. Default: `data`. |
| `--stdout` | Print CSV or JSON instead of saving a file. |
| `--delay` | Seconds between requests when scraping a range. Default: 1. |
| `-v` / `-q` | Debug logging / warnings and errors only. |

Run `pylindol --help` for details.

## Library usage

```python
from pylindol import PhivolcsEarthquakeInfoScraper, scrape_months

# One month. Returns a DataFrame and, by default, also writes a CSV.
df = PhivolcsEarthquakeInfoScraper(month=8, year=2025).run()

# Just the DataFrame, no file.
df = PhivolcsEarthquakeInfoScraper(month=8, year=2025, export=False).run()

# Write JSON to a custom directory instead.
PhivolcsEarthquakeInfoScraper(
    month=8, year=2025, output_path="archive", output_format="json"
).run()

# Several months in one DataFrame (requests are spaced out by `delay`).
df = scrape_months((2025, 1), (2025, 6))

strong = df[df["magnitude"] >= 5]
```

### Output

Every layout PHIVOLCS has used is normalized to the same columns:

| Column | Type | Example |
| --- | --- | --- |
| `datetime` | datetime, Asia/Manila timezone | `2025-08-31 23:56:00+08:00` |
| `date` | string | `2025-08-31` |
| `time` | string | `23:56:00` |
| `latitude` | float, °N | `13.35` |
| `longitude` | float, °E | `120.66` |
| `depth_km` | float | `8.0` |
| `magnitude` | float | `1.9` |
| `location` | string | `012 km S 35° W of Abra De Ilog (Occidental Mindoro)` |

Files are named `phivolcs_earthquake_data_{month}_{year}.{format}`, or
`phivolcs_earthquake_data_{m1}_{y1}_to_{m2}_{y2}.{format}` for a range. JSON
keeps the `+08:00` offset in `datetime`.

### Errors

- `ValueError`: invalid input, such as a month outside 1-12, a month before
  January 2017, or a future month, or only one of `month`/`year` given.
- `TypeError`: `month` or `year` is not an integer.
- `DataNotAvailableError`: PHIVOLCS has no data for the month.
- `requests.RequestException`: network errors, after automatic retries.

### Logging

pylindol uses [loguru](https://loguru.readthedocs.io) and is silent when
imported as a library. To see its logs:

```python
from loguru import logger

logger.enable("pylindol")
```

## How it works

- **Finding the data.** PHIVOLCS pages are hand-edited HTML with several
  layout tables, and the earthquake table's structure has changed over the
  years: headers in the first row or in a separate table, extra empty
  columns, mixed encodings and typos such as `11Jun 2017`. pylindol picks the
  table whose rows look like PHIVOLCS timestamps and maps its columns by
  position, so all of these parse the same way.
- **The current month.** The main page lists the current month and, until
  PHIVOLCS archives it, the previous one. pylindol filters the page to the
  month you asked for, and reads last month from the main page while its
  archive page doesn't exist yet.
- **TLS.** Some PHIVOLCS servers don't send the intermediate certificate
  their certificate chain needs, so a standard `requests` call fails
  verification. pylindol ships that intermediate (GlobalSign RSA OV SSL CA
  2018) and loads it, along with certifi's CAs, into an in-memory SSL
  context. Nothing is written to disk, and verification is never turned off.
- **Being polite.** Requests send a `pylindol` User-Agent, time out, retry
  transient errors with backoff, and range scrapes wait between months.
  Please don't lower `--delay` for large ranges; PHIVOLCS is a public
  service.

## Development

```bash
git clone git@github.com:clnhrn/pylindol.git
cd pylindol
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

uv run pytest            # unit tests, using saved PHIVOLCS pages
uv run pytest -m live    # tests against the real website
uv run ruff check . && uv run mypy
```

Commits follow [Conventional Commits](https://www.conventionalcommits.org).
Merging to `main` opens a version bump PR, and merging that PR tags the
release and publishes it to PyPI.

## License

Released under the [MIT License](https://github.com/clnhrn/pylindol/blob/main/LICENSE).
