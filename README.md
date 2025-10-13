# PHIVOLCS Earthquake Data Scraper

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

A tool to scrape earthquake information from the [Philippine Institute of Volcanology and Seismology (PHIVOLCS)](https://earthquake.phivolcs.dost.gov.ph) website.

This allows you to download earthquake data for the current month or historical data from specific months and years, saving the results as CSV files.

## Requirements

- Python >= 3.13
- Dependencies: beautifulsoup4, certifi, click, loguru, lxml, pandas, requests

## Setup

### Clone the repository
```bash
git clone git@github.com:clnhrn/phivolcs-eq-data.git
```

## Installation

If you don't have `uv` installed yet, follow the installation steps here: https://docs.astral.sh/uv/getting-started/installation/

### Using uv (recommended)

```bash
uv sync
```

### Using pip

```bash
pip install -e .
```

## Usage

### Command Line Interface (CLI)

The package provides a `phivolcs-scraper` command after installation.

#### Basic usage (scrape current month)

```bash
phivolcs-scraper
```

#### Scrape a specific month and year

```bash
phivolcs-scraper --month 8 --year 2025
```

#### Specify custom output directory

```bash
phivolcs-scraper --output-path my_data
```

#### Combine options

```bash
phivolcs-scraper --month 9 --year 2025 --output-path archive
```

#### Get help

```bash
phivolcs-scraper --help
```

### Python Library

You can also use the scraper programmatically in your Python code.

#### Import the class

```python
from phivolcs_scraper import PhivolcsEarthquakeInfoScraper
```

#### Scrape current month

```python
scraper = PhivolcsEarthquakeInfoScraper()
scraper.run()
```

#### Scrape specific month and year

```python
scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025)
scraper.run()
```

#### Specify custom output path

```python
scraper = PhivolcsEarthquakeInfoScraper(
    month=9, 
    year=2025, 
    output_path="custom/directory"
)
scraper.run()
```

## Features

- ✅ Scrape current month's earthquake data
- ✅ Scrape historical data by month and year
- ✅ Automatic CA certificate handling for SSL connections
- ✅ Input validation (month range, year validation, future date prevention)
- ✅ Export data to CSV format
- ✅ Structured logging with loguru

## Output

The scraper saves earthquake data as CSV files with the naming convention:

```
phivolcs_earthquake_data_{month}_{year}.csv
```

**Default location:** `data/` directory (created automatically if it doesn't exist)

**Example:** `data/phivolcs_earthquake_data_10_2025.csv`

The CSV files contain earthquake information including date, time, magnitude, location, and depth.

## Development

This project uses `uv` for dependency management and packaging.

```bash
# Install development dependencies
uv sync

# Run the scraper
uv run phivolcs-scraper
```

## License

This project is licensed under the terms specified in the package metadata.

## Author

clnhrn (herniacln@gmail.com)

