## 0.6.1 (2026-10-09)

### Fix

- **deps**: require urllib3 2.8.0 for security fixes

## 0.6.0 (2026-10-09)

### BREAKING CHANGE

- output columns are now datetime, date, time, latitude,
longitude, depth_km, magnitude and location, with numeric types and a
timezone-aware datetime. pylindol.utils.CertificateHandler is removed.
export_to_csv is deprecated in favor of export. Years before 2017 are
rejected, and non-integer month/year raise TypeError.

### Feat

- normalized columns, date ranges, JSON/Parquet output, safer HTTP

## 0.5.2 (2026-06-12)

### Refactor

- restore timestamp in CLI log format
- make logging silent-by-default with CLI verbosity control
- consolidate scraper, trim cert handler, cache CA bundle

## 0.5.1 (2026-06-09)

### Fix

- show friendly error when earthquake data is unavailable

## 0.5.0 (2026-06-09)

### Feat

- create a GitHub Release on publish

## 0.4.1 (2026-06-09)

### Fix

- open a PR for version bumps instead of pushing to protected main
- create annotated tags so they push to remote
- remove unreliable if condition from bump workflow
- fetch tags explicitly before commitizen bump

## 0.4.0 (2026-06-09)

### Feat

- add separate Date and Time columns to CSV output

### Fix

- update CLI test mock HTML to use correct datetime column header

## 0.3.0 (2025-10-15)

### Feat

- make csv export optional

## 0.2.0 (2025-10-15)

### Feat

- add commitizen
- add workflow to run tests
- add license information to pyproject.toml

### Fix

- implement improved certificate handling
- update script entry point in pyproject.toml

### Refactor

- rename project from phivolcs-eq-data to pylindol
- move log messages to the run method
- reorganize imports
