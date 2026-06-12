# pylindol

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![PyPI version](https://img.shields.io/pypi/v/pylindol)

pylindol is a lightweight library for scraping the latest earthquake data from the [Philippine Institute of Volcanology and Seismology (PHIVOLCS)](https://earthquake.phivolcs.dost.gov.ph) website. It provides a simple API and command line tool to pull up-to-date earthquake information for your applications, scripts, or research.

## Requirements

- Python >= 3.11

## Installation

Install from PyPI:

```bash
pip install pylindol
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add pylindol
```

## Command line usage

Installing the package adds the `pylindol` command.

Scrape the current month:

```bash
pylindol
```

Scrape a specific month and year:

```bash
pylindol --month 8 --year 2025
```

Save to a custom output directory (default is `data`):

```bash
pylindol --month 8 --year 2025 --output-path archive
```

Control log verbosity. The CLI logs at INFO by default; use `-v`/`--verbose`
for debug detail or `-q`/`--quiet` to show only warnings and errors:

```bash
pylindol --month 8 --year 2025 -v   # debug
pylindol --month 8 --year 2025 -q   # warnings and errors only
```

See all options:

```bash
pylindol --help
```

The CLI always writes a CSV file.

## Library usage

```python
from pylindol import PhivolcsEarthquakeInfoScraper

# Scrape the current month (returns a pandas DataFrame).
scraper = PhivolcsEarthquakeInfoScraper()
df = scraper.run()
print(df.head())
```

Scrape a specific month and year:

```python
scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025)
df = scraper.run()
```

By default `run()` also writes a CSV file. Set `export_to_csv=False` to skip
the file and only return the DataFrame:

```python
scraper = PhivolcsEarthquakeInfoScraper(
    month=8,
    year=2025,
    output_path="archive",   # CSV output directory
    export_to_csv=False,     # return the DataFrame only
)
df = scraper.run()
```

### Constructor options

| Argument        | Default  | Description                               |
| --------------- | -------- | ----------------------------------------- |
| `month`         | `None`   | Month to scrape (1-12). Requires `year`.  |
| `year`          | `None`   | Year to scrape. Requires `month`.         |
| `output_path`   | `"data"` | Directory for the CSV output.             |
| `export_to_csv` | `True`   | Whether to write a CSV file.              |

If neither `month` nor `year` is given, the scraper uses the current month.
Both must be provided together.

### Logging

pylindol uses [loguru](https://loguru.readthedocs.io) and stays silent when
imported as a library. Enable its logs in your application with:

```python
from loguru import logger

logger.enable("pylindol")
```

### Errors

- `ValueError` if only one of `month`/`year` is provided, an input fails
  validation (month outside 1-12, year before 1900 or in the future), or the
  requested month is in the future.
- `DataNotAvailableError` if PHIVOLCS has no data for the requested month.

## Output

CSV files are named:

```
phivolcs_earthquake_data_{month}_{year}.csv
```

They are written to the output directory (default `data/`, created
automatically). For example: `data/phivolcs_earthquake_data_10_2025.csv`.

Each file contains earthquake details including date, time, magnitude,
location, and depth.

## Development

Run from source:

```bash
git clone git@github.com:clnhrn/pylindol.git
cd pylindol
uv sync

# Run the tests
uv run pytest
```

## License

Released under the [MIT License](LICENSE).
