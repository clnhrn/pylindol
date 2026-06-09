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
