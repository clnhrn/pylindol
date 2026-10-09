"""Shared test fixtures.

The HTML files in tests/fixtures/ are real PHIVOLCS pages trimmed to a few
rows each. They cover every table layout the site has used since 2017:

- main_page_2026_10: the main page, which holds both October and September.
- archive_2025_August: the current archive layout.
- archive_2019_June: 12 columns with footer rows of month links.
- archive_2018_January: header inside the first row, plus a "January" row.
- archive_2017_January: windows-1252, header in a separate table.
"""

from datetime import date
from pathlib import Path

import pytest

import pylindol.earthquake_info_scraper as scraper_module

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = scraper_module.BASE_URL

# The main page fixture was saved on this date (Philippine time).
FROZEN_TODAY = date(2026, 10, 9)


def load_page(name: str) -> bytes:
    """Return the bytes of a saved PHIVOLCS page from tests/fixtures/."""
    return (FIXTURES / f"{name}.html").read_bytes()


def archive_url(year: int, month_name: str) -> str:
    return f"{BASE_URL}/EQLatest-Monthly/{year}/{year}_{month_name}.html"


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    """Pin "today" so tests don't depend on when they run."""
    monkeypatch.setattr(scraper_module, "_today", lambda: FROZEN_TODAY)
    return FROZEN_TODAY


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Skip the politeness delay between requests in range scrapes."""
    monkeypatch.setattr(scraper_module.time, "sleep", lambda _seconds: None)
