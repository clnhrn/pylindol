"""Scrape earthquake information from the PHIVOLCS website."""

import re
import time
import warnings
from collections.abc import Iterator
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Literal, get_args
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from loguru import logger

from pylindol._http import REQUEST_TIMEOUT, build_session

BASE_URL = "https://earthquake.phivolcs.dost.gov.ph"
PHILIPPINE_TZ = ZoneInfo("Asia/Manila")

# PHIVOLCS's monthly archive starts in January 2017; earlier months return 404.
EARLIEST_YEAR = 2017

OutputFormat = Literal["csv", "json", "parquet"]
OUTPUT_FORMATS: tuple[str, ...] = get_args(OutputFormat)

# Every page layout since 2017 lists these columns in this order, but header
# rows are inconsistent (missing, inside the first data row, or in a separate
# table), so columns are assigned by position.
_SOURCE_COLUMNS = [
    "datetime",
    "latitude",
    "longitude",
    "depth_km",
    "magnitude",
    "location",
]
OUTPUT_COLUMNS = [
    "datetime",
    "date",
    "time",
    "latitude",
    "longitude",
    "depth_km",
    "magnitude",
    "location",
]

# e.g. "09 October 2026 - 07:24 PM" or "31 Jan 2017 - 11:55 PM". Spacing is
# optional because older pages are hand-edited and inconsistent.
_DATETIME_PATTERN = re.compile(
    r"^(?P<day>\d{1,2})\s*(?P<month>[A-Za-z]+)\.?\s*(?P<year>\d{4})\s*-\s*"
    r"(?P<clock>\d{1,2}:\d{2})\s*(?P<meridiem>[AaPp][Mm])$"
)


class DataNotAvailableError(Exception):
    """Raised when PHIVOLCS has no earthquake data for the requested month."""


def _today() -> date:
    """Today's date in Philippine time, which is what PHIVOLCS's pages follow."""
    return datetime.now(PHILIPPINE_TZ).date()


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _month_name(year: int, month: int) -> str:
    return date(year, month, 1).strftime("%B")


def validate_year_month(year: int, month: int) -> None:
    """Check that a month exists in the PHIVOLCS archive and is not in the future.

    Args:
        year: The year, from 2017 up to the current year.
        month: The month, 1-12.

    Raises:
        TypeError: If `year` or `month` is not an integer.
        ValueError: If the month is outside 1-12, before January 2017, or in
            the future (in Philippine time).
    """
    for name, value in (("year", year), ("month", month)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an int, not {type(value).__name__}.")
    if not 1 <= month <= 12:
        raise ValueError(f"Month must be between 1 and 12. You provided {month}.")
    if year < EARLIEST_YEAR:
        raise ValueError(
            f"PHIVOLCS archives start in January {EARLIEST_YEAR}. You provided {year}."
        )
    today = _today()
    if (year, month) > (today.year, today.month):
        raise ValueError(
            f"{_month_name(year, month)} {year} is in the future. "
            "Please provide a month that is current or in the past."
        )


def month_range(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """List every (year, month) from `start` to `end`, inclusive.

    Args:
        start: The first month as `(year, month)`.
        end: The last month as `(year, month)`.

    Returns:
        The months in chronological order.

    Raises:
        ValueError: If `start` is after `end`, or either fails
            `validate_year_month`.
    """
    validate_year_month(*start)
    validate_year_month(*end)
    if start > end:
        raise ValueError("The start month must not be after the end month.")

    def _iter() -> Iterator[tuple[int, int]]:
        year, month = start
        while (year, month) <= end:
            yield year, month
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)

    return list(_iter())


def _json_ready(df: pd.DataFrame) -> pd.DataFrame:
    """Format datetimes as ISO 8601 strings that keep the +08:00 offset."""
    return df.assign(datetime=df["datetime"].map(lambda ts: ts.isoformat()))


def export_dataframe(
    df: pd.DataFrame, path: str | Path, output_format: OutputFormat = "csv"
) -> Path:
    """Write earthquake data to a file, creating parent directories as needed.

    Args:
        df: Data returned by `PhivolcsEarthquakeInfoScraper.run()` or
            `scrape_months()`.
        path: The file to write.
        output_format: One of "csv", "json" or "parquet". Parquet needs the
            `parquet` extra (`pip install "pylindol[parquet]"`).

    Returns:
        The path written to.

    Raises:
        ValueError: If `output_format` is not supported.
        ImportError: If Parquet is requested but pyarrow is not installed.
    """
    path = Path(path)
    if output_format not in OUTPUT_FORMATS:
        raise ValueError(
            f"output_format must be one of {', '.join(OUTPUT_FORMATS)}, "
            f"not {output_format!r}."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "csv":
        df.to_csv(path, index=False)
    elif output_format == "json":
        _json_ready(df).to_json(path, orient="records", indent=2, force_ascii=False)
    else:
        try:
            df.to_parquet(path, index=False)
        except ImportError as e:
            raise ImportError(
                'Parquet output needs pyarrow: pip install "pylindol[parquet]"'
            ) from e
    logger.info(f"Exported data to {path}")
    return path


def format_dataframe(df: pd.DataFrame, output_format: Literal["csv", "json"]) -> str:
    """Render earthquake data as CSV or JSON text, e.g. for printing to stdout.

    Args:
        df: The earthquake data.
        output_format: "csv" or "json".

    Returns:
        The rendered text.
    """
    if output_format == "csv":
        return df.to_csv(index=False, lineterminator="\n")
    if output_format == "json":
        text = _json_ready(df).to_json(orient="records", indent=2, force_ascii=False)
        return f"{text}\n"
    raise ValueError(f"Cannot format data as {output_format!r} text.")


class PhivolcsEarthquakeInfoScraper:
    """Scrape earthquake information for one month from the PHIVOLCS website.

    By default it scrapes the current month (in Philippine time) from the main
    page. Past months are read from PHIVOLCS's monthly archive.
    """

    def __init__(
        self,
        month: int | None = None,
        year: int | None = None,
        output_path: str | Path = "data",
        export: bool = True,
        *,
        output_format: OutputFormat = "csv",
        session: requests.Session | None = None,
        export_to_csv: bool | None = None,
    ) -> None:
        """Initialize the scraper.

        Args:
            month: The month to scrape (1-12). Requires `year`.
            year: The year to scrape (2017 or later). Requires `month`.
            output_path: Directory that `run()` exports to.
            export: Whether `run()` writes the data to a file.
            output_format: File format for the export: "csv", "json" or
                "parquet".
            session: Optional `requests.Session` to reuse across scrapers. By
                default each request uses a new, preconfigured session.
            export_to_csv: Deprecated alias for `export`.

        Raises:
            TypeError: If `month` or `year` is not an integer.
            ValueError: If only one of `month`/`year` is provided, the month
                is invalid, before 2017 or in the future, or `output_format`
                is not supported.
        """
        if export_to_csv is not None:
            warnings.warn(
                "export_to_csv is deprecated; use export instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            export = export_to_csv

        if month is not None and year is None:
            raise ValueError("If month is provided, year must also be provided.")
        if month is None and year is not None:
            raise ValueError("If year is provided, month must also be provided.")
        if output_format not in OUTPUT_FORMATS:
            raise ValueError(
                f"output_format must be one of {', '.join(OUTPUT_FORMATS)}, "
                f"not {output_format!r}."
            )

        if month is None or year is None:
            today = _today()
            year, month = today.year, today.month
        validate_year_month(year, month)

        self.month = month
        self.year = year
        self.output_path = output_path
        self.export = export
        self.output_format = output_format
        self.session = session

    @property
    def month_url(self) -> str:
        """URL of this month's page in the PHIVOLCS archive."""
        return (
            f"{BASE_URL}/EQLatest-Monthly/{self.year}/"
            f"{self.year}_{_month_name(self.year, self.month)}.html"
        )

    @property
    def file_name(self) -> str:
        """Name of the file `run()` exports to."""
        return f"phivolcs_earthquake_data_{self.month}_{self.year}.{self.output_format}"

    def _fetch_page(self, url: str) -> bytes:
        """Fetch a page from the PHIVOLCS website.

        Args:
            url: The page URL to request.

        Returns:
            The raw page content.

        Raises:
            requests.HTTPError: If the response status is 4xx or 5xx.
            requests.RequestException: On connection errors or timeouts.
        """
        logger.debug(f"Fetching {url}")
        if self.session is not None:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        else:
            with build_session() as session:
                response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.content

    def _fetch_month_page(self) -> bytes:
        """Fetch the page that lists this month's earthquakes.

        The main page holds the current month and, until PHIVOLCS archives it,
        the previous month too. So a missing archive page for last month falls
        back to the main page.
        """
        today = _today()
        current = (today.year, today.month)
        target = (self.year, self.month)
        if target == current:
            logger.info(f"Scraping current month: {self.month} of {self.year}")
            return self._fetch_page(BASE_URL)

        logger.info(f"Scraping month {self.month} of year {self.year}")
        try:
            return self._fetch_page(self.month_url)
        except requests.HTTPError as e:
            if e.response is None or e.response.status_code != 404:
                raise
            if target == _previous_month(*current):
                logger.info("Archive page not published yet, reading the main page")
                return self._fetch_page(BASE_URL)
            raise self._not_available() from e

    def _not_available(self) -> DataNotAvailableError:
        return DataNotAvailableError(
            f"Earthquake data for {_month_name(self.year, self.month)} {self.year} "
            "is not available on the PHIVOLCS website."
        )

    def extract_target_table(self, page: bytes) -> pd.DataFrame:
        """Find the earthquake table on a PHIVOLCS page.

        The page has several layout tables, so the earthquake table is the one
        with the most rows whose first cell is a PHIVOLCS date-time.

        Args:
            page: The content of the page in bytes.

        Returns:
            The raw earthquake table, as parsed by pandas.

        Raises:
            DataNotAvailableError: If the page has no earthquake table.
        """
        try:
            # Pass bytes, not text: pages mix UTF-8 and windows-1252, and lxml
            # picks the right one from each page's charset declaration. The
            # stubs only allow text buffers, though pandas accepts bytes.
            # flavor="lxml" stops pandas falling back to bs4/html5lib, which
            # aren't dependencies, when a page has no tables.
            tables = pd.read_html(BytesIO(page), flavor="lxml")  # type: ignore[arg-type]
        except ValueError:  # pandas raises ValueError when there are no tables
            tables = []

        best, best_count = None, 0
        for table in tables:
            if table.shape[1] < len(_SOURCE_COLUMNS):
                continue
            count = int(
                _clean_text(table.iloc[:, 0]).str.fullmatch(_DATETIME_PATTERN).sum()
            )
            if count > best_count:
                best, best_count = table, count
        if best is None:
            raise self._not_available()
        return best

    def _normalize(self, table: pd.DataFrame) -> pd.DataFrame:
        """Turn a raw PHIVOLCS table into typed columns for this month only.

        Drops header, month-name and footer rows, parses the date-time as
        Philippine time, converts numeric columns, and tidies whitespace in
        the location.
        """
        df = table.iloc[:, : len(_SOURCE_COLUMNS)].copy()
        df.columns = _SOURCE_COLUMNS
        parts = _clean_text(df["datetime"]).str.extract(_DATETIME_PATTERN)
        is_data_row = parts.notna().all(axis=1)
        df, parts = df[is_data_row], parts[is_data_row]

        # Rebuild each value with standard spacing, since older pages have
        # typos like "11Jun 2017" or "16 Jun 2017 -12:50 AM".
        canonical = parts["day"] + " " + parts["month"] + " " + parts["year"]
        canonical += " " + parts["clock"] + " " + parts["meridiem"]
        parsed = pd.to_datetime(
            canonical, format="mixed", errors="coerce"
        ).dt.tz_localize(PHILIPPINE_TZ)
        in_month = (parsed.dt.year == self.year) & (parsed.dt.month == self.month)
        df, parsed = df[in_month], parsed[in_month]

        out = pd.DataFrame(
            {
                "datetime": parsed,
                "date": parsed.dt.strftime("%Y-%m-%d"),
                "time": parsed.dt.strftime("%H:%M:%S"),
                **{
                    col: pd.to_numeric(_clean_text(df[col]), errors="coerce").astype(
                        "float64"
                    )
                    for col in ("latitude", "longitude", "depth_km", "magnitude")
                },
                "location": _clean_text(df["location"]).str.replace(
                    r"\s+", " ", regex=True
                ),
            },
            columns=OUTPUT_COLUMNS,
        )
        return out.reset_index(drop=True)

    def fetch(self) -> pd.DataFrame:
        """Download and parse this month's earthquakes without exporting them.

        Returns:
            One row per earthquake, newest first, with the columns in
            `OUTPUT_COLUMNS`. `datetime` is timezone-aware (Asia/Manila).

        Raises:
            DataNotAvailableError: If PHIVOLCS has no data for the month.
            requests.RequestException: On network errors.
        """
        df = self._normalize(self.extract_target_table(self._fetch_month_page()))
        today = _today()
        if df.empty and (self.year, self.month) != (today.year, today.month):
            raise self._not_available()
        return df

    def run(self) -> pd.DataFrame:
        """Fetch this month's earthquakes and export them if `export` is set.

        Returns:
            The earthquake data (see `fetch()`).

        Raises:
            DataNotAvailableError: If PHIVOLCS has no data for the month.
            requests.RequestException: On network errors.
        """
        df = self.fetch()
        if self.export:
            export_dataframe(
                df, Path(self.output_path) / self.file_name, self.output_format
            )
        return df


def _clean_text(column: pd.Series) -> pd.Series:
    """Cells as stripped strings, with byte-order marks some pages contain removed."""
    return column.astype(str).str.replace("﻿", "", regex=False).str.strip()


def scrape_months(
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    delay: float = 1.0,
    skip_missing: bool = True,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Scrape a range of months into one DataFrame.

    Args:
        start: The first month as `(year, month)`, e.g. `(2025, 1)`.
        end: The last month (inclusive) as `(year, month)`.
        delay: Seconds to wait between requests, to go easy on PHIVOLCS.
        skip_missing: Log and skip months PHIVOLCS has no data for, instead of
            raising.
        session: Optional `requests.Session` to use. One is created and
            closed automatically if omitted.

    Returns:
        The earthquakes for every month, in the order the months were
        scraped (oldest month first, newest earthquake first within a month).

    Raises:
        ValueError: If the range is invalid.
        DataNotAvailableError: If a month is missing and `skip_missing` is
            False, or no month in the range has data.
        requests.RequestException: On network errors.
    """
    months = month_range(start, end)
    own_session = session is None
    active_session = session if session is not None else build_session()
    frames = []
    try:
        for i, (year, month) in enumerate(months):
            if i and delay:
                time.sleep(delay)
            scraper = PhivolcsEarthquakeInfoScraper(
                month=month, year=year, export=False, session=active_session
            )
            try:
                frames.append(scraper.fetch())
            except DataNotAvailableError as e:
                if not skip_missing:
                    raise
                logger.warning(f"Skipping: {e}")
    finally:
        if own_session:
            active_session.close()

    if not frames:
        raise DataNotAvailableError(
            f"No earthquake data is available from {start[1]}/{start[0]} "
            f"to {end[1]}/{end[0]}."
        )
    return pd.concat(frames, ignore_index=True)
