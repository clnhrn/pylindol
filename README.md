# pylindol

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![PyPI version](https://badge.fury.io/py/pylindol.svg)

pylindol is a lightweight and easy-to-use library designed to scrape or pull the latest earthquake data from the [Philippine Institute of Volcanology and Seismology (PHIVOLCS)](https://earthquake.phivolcs.dost.gov.ph) website. It provides a simple API to get up-to-date information for your applications, scripts, or research projects.

## Requirements

- Python >= 3.11

## Installation

Install pylindol directly from PyPI:

```bash
pip install pylindol
```

### Using a virtual environment (recommended)

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows

# Install pylindol
pip install pylindol
```

### Using uv

If you prefer using `uv` for faster package management:

```bash
uv add pylindol
```

## Usage

### Command Line Interface (CLI)

The package provides the `pylindol` command after installation.

#### Basic usage (scrape current month)

```bash
pylindol
```

#### Scrape a specific month and year

```bash
pylindol --month 8 --year 2025
```

#### Specify custom output directory

```bash
pylindol --output-path my_data
```

#### Combine options

```bash
pylindol --month 9 --year 2025 --output-path archive
```

#### Get help

```bash
pylindol --help
```

### Python Library

You can also use the scraper as a Python library in your code.

#### Import the class

```python
from pylindol import PhivolcsEarthquakeInfoScraper
```

#### Scrape current month

```python
scraper = PhivolcsEarthquakeInfoScraper()
df = scraper.run()  # Returns a pandas DataFrame
print(df.head())  # Display first few rows
```

#### Scrape specific month and year

```python
scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025)
df = scraper.run()  # Returns a pandas DataFrame
```

#### Specify custom output path

```python
scraper = PhivolcsEarthquakeInfoScraper(
    month=9, 
    year=2025, 
    output_path="custom/directory"
)
df = scraper.run()  # Returns a pandas DataFrame
```

#### Control CSV export

```python
# Export to CSV (default behavior)
scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025)
df = scraper.run()  # Also saves to CSV file

# Skip CSV export and only return DataFrame
scraper = PhivolcsEarthquakeInfoScraper(
    month=8, 
    year=2025, 
    export_to_csv=False
)
df = scraper.run()  # Only returns DataFrame, no CSV file
```

## Features

- ✅ Scrape current month's earthquake data
- ✅ Scrape historical data by month and year
- ✅ Returns pandas DataFrame for easy data manipulation
- ✅ Optional CSV export (can be disabled)
- ✅ Automatic CA certificate handling for SSL connections
- ✅ Input validation (month range, year validation, and future date prevention)
- ✅ Structured logging with loguru

## Output

The scraper saves earthquake data as CSV files with the naming convention:

```
phivolcs_earthquake_data_{month}_{year}.csv
```

**Default location:** `data/` directory (created automatically if it doesn't exist)

**Example:** `data/phivolcs_earthquake_data_10_2025.csv`

**Note:** You can disable CSV export by setting `export_to_csv=False` in the constructor. Note that the CLI will always export data to a CSV file.

The CSV files contain earthquake information including date, time, magnitude, location, and depth.

## Development

If you want to contribute to pylindol or run it from source:

```bash
# Clone the repository
git clone git@github.com:clnhrn/pylindol.git
cd pylindol

# Install in development mode
pip install -e .

# Or using uv
uv sync
```
