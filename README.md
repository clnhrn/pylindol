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

uv automatically creates a virtual environment with Python 3.13 and installs all dependencies:

```bash
# This creates a .venv with Python 3.13 and installs dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows
```

### Using pip

This approach requires Python 3.13 to be installed.

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows

# Install the dependencies in editable mode
pip install -e .
```

## Usage

### Command Line Interface (CLI)

The package provides the `phivolcs-eq-data` command after installation.

#### Basic usage (scrape current month)

```bash
phivolcs-eq-data
```

#### Scrape a specific month and year

```bash
phivolcs-eq-data --month 8 --year 2025
```

#### Specify custom output directory

```bash
phivolcs-eq-data --output-path my_data
```

#### Combine options

```bash
phivolcs-eq-data --month 9 --year 2025 --output-path archive
```

#### Get help

```bash
phivolcs-eq-data --help
```

### Python Library

You can also use the scraper as a Python library in your code.

#### Import the class

```python
from phivolcs_eq_data import PhivolcsEarthquakeInfoScraper
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
- ✅ Input validation (month range, year validation, and future date prevention)
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
