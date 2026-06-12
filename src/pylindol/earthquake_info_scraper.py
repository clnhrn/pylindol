from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger

from pylindol.config.paths import CA_CERTIFICATE_PATH
from pylindol.utils.certificate_handler import CertificateHandler


class DataNotAvailableError(Exception):
    """Raised when PHIVOLCS has no earthquake data for the requested month."""


class PhivolcsEarthquakeInfoScraper:
    """Scrape earthquake information from the PHIVOLCS website.

    You can either scrape the latest earthquake information or a specific month
    and year. By default, it scrapes the current month from the main page.
    """

    def __init__(
        self,
        month: Optional[int] = None,
        year: Optional[int] = None,
        output_path: str = "data",
        export_to_csv: bool = True,
    ):
        """Initialize the scraper.

        Args:
            month: The month to scrape. Requires `year` to also be provided.
            year: The year to scrape. Requires `month` to also be provided.
            output_path: Directory to export the CSV to.
            export_to_csv: Whether to export the dataframe to a CSV file.

        Raises:
            ValueError: If only one of `month`/`year` is provided, or if either
                fails validation.
        """

        self.base_url = "https://earthquake.phivolcs.dost.gov.ph"
        self.output_path = output_path
        self.export_to_csv = export_to_csv
        self.certificate_handler = None

        if month is not None and year is None:
            raise ValueError("If month is provided, year must also be provided.")
        elif month is None and year is not None:
            raise ValueError("If year is provided, month must also be provided.")

        if month is not None and year is not None:
            self.month = self._validate_month_input(month)
            self.year = self._validate_year_input(year)
            month_name = datetime(self.year, self.month, 1).strftime("%B")
            self.month_url = (
                f"{self.base_url}/EQLatest-Monthly/{self.year}/"
                f"{self.year}_{month_name}.html"
            )
        else:
            self.month = datetime.now().month
            self.year = datetime.now().year

        # Setup certificates before running any requests
        self._setup_certificates()

    def _setup_certificates(self):
        """Set up the certificate handler and append the CA cert to the certifi bundle.

        Falls back to the default certifi bundle if the bundled CA certificate
        is missing or cannot be loaded; failures are logged, not raised.
        """
        try:
            self.certificate_handler = CertificateHandler()

            # Check if the CA certificate file exists and add it
            if CA_CERTIFICATE_PATH.exists():
                logger.debug(f"Adding CA certificate: {CA_CERTIFICATE_PATH}")
                self.certificate_handler.add_certificate(CA_CERTIFICATE_PATH)
                logger.debug("CA certificate successfully added to certifi bundle")
            else:
                logger.warning(
                    f"CA certificate file not found: {CA_CERTIFICATE_PATH}. "
                    "Using the default certifi bundle."
                )

        except Exception as e:
            logger.warning(
                f"Error setting up certificates, using the default certifi bundle: {e}"
            )

    def _validate_month_input(self, month: int) -> int:
        """Validate the month input.

        Args:
            month: The month to validate.

        Returns:
            The validated month.

        Raises:
            ValueError: If the month is outside 1-12.
        """
        if month < 1 or month > 12:
            raise ValueError((f"Month must be between 1 and 12. You provided {month}."))
        return month

    def _validate_year_input(self, year: int) -> int:
        """Validate the year input.

        Args:
            year: The year to validate.

        Returns:
            The validated year.

        Raises:
            ValueError: If the year is before 1900 or after the current year.
        """
        if year < 1900 or year > datetime.now().year:
            raise ValueError(
                (
                    "Year must be greater than 1900 and less than the current year "
                    f"({datetime.now().year}). You provided {year}."
                )
            )
        return year

    def _fetch_page(self, url: str) -> bytes:
        """Fetch a page from the PHIVOLCS website.

        Uses the combined certificate bundle when custom CA certificates are
        available, otherwise falls back to the default certifi bundle.

        Args:
            url: The page URL to request.

        Returns:
            The raw page content.

        Raises:
            requests.HTTPError: If the response status is 4xx or 5xx.
        """
        with requests.Session() as session:
            if (
                self.certificate_handler
                and self.certificate_handler.custom_certificates
            ):
                bundle_path = self.certificate_handler.get_bundle_path()
                logger.debug(f"Using combined certificate bundle: {bundle_path}")
                response = session.get(url, verify=str(bundle_path))
            else:
                logger.debug("Using default certifi bundle")
                response = session.get(url)
            response.raise_for_status()
            return response.content

    def extract_target_table(self, page: bytes) -> pd.DataFrame:
        """
        Extract the target table from the page.

        Args:
            page: The content of the page in bytes.

        Returns:
            pd.DataFrame: Dataframe of the target table.
        """
        soup = BeautifulSoup(page, "html.parser")
        tables = pd.read_html(StringIO(soup.prettify()))
        return tables[2]

    def _add_datetime_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add separate Date and Time columns derived from the combined datetime column.

        Args:
            df: DataFrame with a `Date - Time  (Philippine Time)` column.

        Returns:
            A copy of the DataFrame with `Date` and `Time` columns inserted
            immediately after the combined datetime column.
        """
        datetime_col = next(
            (c for c in df.columns if isinstance(c, str) and c.startswith("Date - Time")),
            None,
        )
        if datetime_col is None:
            # Old/unavailable months return a placeholder table with no parsed
            # header, so the datetime column never appears.
            month_name = datetime(self.year, self.month, 1).strftime("%B")
            raise DataNotAvailableError(
                f"Earthquake data for {month_name} {self.year} is not available "
                "on the PHIVOLCS website."
            )
        parsed = pd.to_datetime(df[datetime_col], format="mixed")
        idx = df.columns.get_loc(datetime_col)
        df = df.copy()
        df.insert(idx + 1, "Date", parsed.dt.strftime("%Y-%m-%d"))
        df.insert(idx + 2, "Time", parsed.dt.strftime("%H:%M:%S"))
        return df

    def _export_to_csv(self, df: pd.DataFrame):
        """Export the dataframe to a CSV file under `output_path`.

        Args:
            df: The dataframe to export.
        """
        Path(self.output_path).mkdir(exist_ok=True, parents=True)
        file_name = (
            Path(self.output_path)
            / f"phivolcs_earthquake_data_{self.month}_{self.year}.csv"
        )
        df.to_csv(file_name, index=False)
        logger.info(f"Exported data to {file_name}")

    def run(self) -> pd.DataFrame:
        """Run the scraper.

        The current month is read from the site's main page; any past month is
        read from its monthly archive page.

        Returns:
            The dataframe containing the earthquake data.

        Raises:
            ValueError: If the requested month-year is in the future.
            DataNotAvailableError: If PHIVOLCS has no data for the month.
        """
        target_date = date(self.year, self.month, 1)
        current_date = date.today().replace(day=1)
        if target_date > current_date:
            raise ValueError(
                (
                    f"Month {self.month} of year {self.year} is in the future. "
                    "Please provide a month-year combination that is current "
                    "or in the past."
                )
            )

        if target_date == current_date:
            logger.info(f"Scraping current month page: {self.month} of {self.year}")
            url = self.base_url
        else:
            logger.info(f"Scraping month {self.month} of year {self.year}")
            url = self.month_url

        table = self._add_datetime_columns(
            self.extract_target_table(self._fetch_page(url))
        )
        if self.export_to_csv:
            self._export_to_csv(table)
        return table
