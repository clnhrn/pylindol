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


class PhivolcsEarthquakeInfoScraper:
    """
    This class is used to scrape the latest earthquake information from the
    PHIVOLCS website.

    You can either scrape the latest earthquake information or a specific month
    and year. By default, it will scrape the latest earthquake information.
    """

    def __init__(
        self,
        month: Optional[int] = None,
        year: Optional[int] = None,
        output_path: Optional[str] = "data",
        export_to_csv: Optional[bool] = True,
    ):
        """
        Initialize the scraper.

        Args:
            month: The month to scrape.
            year: The year to scrape.
            output_path: The path to export the dataframe.
            export_to_csv: Whether to export the dataframe to a CSV file.
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
        """
        Setup certificate handler and append CA certificates to certifi bundle.
        """
        try:
            self.certificate_handler = CertificateHandler()

            # Check if the CA certificate file exists and add it
            if CA_CERTIFICATE_PATH.exists():
                logger.info(f"Adding CA certificate: {CA_CERTIFICATE_PATH}")
                self.certificate_handler.add_certificate(CA_CERTIFICATE_PATH)
                logger.info("CA certificate successfully added to certifi bundle")
            else:
                logger.warning(f"CA certificate file not found: {CA_CERTIFICATE_PATH}")
                logger.info(
                    "Using default certifi bundle without custom CA certificates"
                )

        except Exception as e:
            logger.error(f"Error setting up certificates: {e}")
            logger.warning("Continuing with default certifi bundle")

    def _validate_month_input(self, month: int) -> int:
        """
        Validate the month input.
        """
        if month is not None and month < 1 or month > 12:
            raise ValueError((f"Month must be between 1 and 12. You provided {month}."))
        return month

    def _validate_year_input(self, year: int) -> int:
        """
        Validate the year input.
        """
        if year is not None and (year < 1900 or year > datetime.now().year):
            raise ValueError(
                (
                    "Year must be greater than 1900 and less than the current year "
                    f"({datetime.now().year}). You provided {year}."
                )
            )
        return year

    def extract_main_page(self) -> bytes:
        """
        Scrape the main earthquake data page of the PHIVOLCS website.

        Returns:
            bytes: The content of the main page.
        """
        try:
            with requests.Session() as session:
                # Use certificate handler if available
                if (
                    self.certificate_handler
                    and self.certificate_handler.custom_certificates
                ):
                    bundle_path = self.certificate_handler.get_bundle_path()
                    logger.info(f"Using combined certificate bundle: {bundle_path}")
                    response = session.get(self.base_url, verify=str(bundle_path))
                else:
                    logger.info("Using default certifi bundle")
                    response = session.get(self.base_url)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Error extracting main page: {e}")
            raise

    def extract_month_page(self) -> bytes:
        """
        Scrape the monthly earthquake data page of the PHIVOLCS website.

        Returns:
            bytes: The content of the monthly page.
        """
        try:
            with requests.Session() as session:
                # Use certificate handler if available
                if (
                    self.certificate_handler
                    and self.certificate_handler.custom_certificates
                ):
                    bundle_path = self.certificate_handler.get_bundle_path()
                    logger.info(f"Using combined certificate bundle: {bundle_path}")
                    response = session.get(self.month_url, verify=str(bundle_path))
                else:
                    logger.info("Using default certifi bundle")
                    response = session.get(self.month_url)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Error extracting month page: {e}")
            raise

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

    def _export_to_csv(self, df: pd.DataFrame):
        """
        Export the dataframe to a CSV file.

        Args:
            df: The dataframe to export.
            output_path: The path to export the dataframe.
        """
        Path(self.output_path).mkdir(exist_ok=True, parents=True)
        file_name = (
            Path(self.output_path)
            / f"phivolcs_earthquake_data_{self.month}_{self.year}.csv"
        )
        df.to_csv(file_name, index=False)
        logger.info(f"Exported data to {file_name}")

    def _run_main_scrape(self) -> pd.DataFrame:
        """
        Run the scraper for the main page.

        Returns:
            pd.DataFrame: The dataframe containing the earthquake data
            from the main page.
        """
        page = self.extract_main_page()
        table = self.extract_target_table(page)
        if self.export_to_csv:
            self._export_to_csv(table)
        return table

    def _run_month_scrape(self) -> pd.DataFrame:
        """
        Run the scraper for the month page.

        Returns:
            pd.DataFrame: The dataframe containing the earthquake data
            from the month page.
        """
        page = self.extract_month_page()
        table = self.extract_target_table(page)
        if self.export_to_csv:
            self._export_to_csv(table)
        return table

    def run(self) -> pd.DataFrame:
        """
        Run the scraper.

        Returns:
            pd.DataFrame: The dataframe containing the earthquake data
            from the main page or the month page.
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
        elif self.month == datetime.now().month and self.year == datetime.now().year:
            logger.info(
                f"Scraping main (current month) page: {self.month} of {self.year}"
            )
            return self._run_main_scrape()
        else:
            logger.info(f"Scraping month {self.month} of year {self.year}")
            return self._run_month_scrape()
