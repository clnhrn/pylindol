"""Tests for the PhivolcsEarthquakeInfoScraper class."""

from datetime import datetime

import pandas as pd
import pytest
import responses

from pylindol.earthquake_info_scraper import PhivolcsEarthquakeInfoScraper


class TestPhivolcsEarthquakeInfoScraperInit:
    """Test initialization of the scraper."""

    def test_init_with_no_params(self):
        """Test initialization with no parameters defaults to current month."""
        scraper = PhivolcsEarthquakeInfoScraper()
        assert scraper.month == datetime.now().month
        assert scraper.year == datetime.now().year
        assert scraper.output_path == "data"
        assert scraper.export_to_csv is True

    def test_init_with_valid_month_and_year(self):
        """Test initialization with valid month and year."""
        scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025)
        assert scraper.month == 8
        assert scraper.year == 2025
        assert "2025_August.html" in scraper.month_url

    def test_init_with_custom_output_path(self):
        """Test initialization with custom output path."""
        scraper = PhivolcsEarthquakeInfoScraper(
            month=8, year=2025, output_path="custom/path"
        )
        assert scraper.output_path == "custom/path"
        assert scraper.export_to_csv is True

    def test_init_with_only_month_raises_error(self):
        """Test that providing only month raises ValueError."""
        with pytest.raises(ValueError, match="year must also be provided"):
            PhivolcsEarthquakeInfoScraper(month=8)

    def test_init_with_only_year_raises_error(self):
        """Test that providing only year raises ValueError."""
        with pytest.raises(ValueError, match="month must also be provided"):
            PhivolcsEarthquakeInfoScraper(year=2025)

    def test_init_with_export_to_csv_false(self):
        """Test initialization with export_to_csv set to False."""
        scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025, export_to_csv=False)
        assert scraper.export_to_csv is False


class TestPhivolcsEarthquakeInfoScraperValidation:
    """Test validation methods of the scraper."""

    def test_month_validation_rejects_less_than_one(self):
        """Test that month < 1 raises ValueError."""
        with pytest.raises(ValueError, match="Month must be between 1 and 12"):
            PhivolcsEarthquakeInfoScraper(month=0, year=2025)

    def test_month_validation_rejects_greater_than_twelve(self):
        """Test that month > 12 raises ValueError."""
        with pytest.raises(ValueError, match="Month must be between 1 and 12"):
            PhivolcsEarthquakeInfoScraper(month=13, year=2025)

    def test_year_validation_rejects_too_old(self):
        """Test that year < 1900 raises ValueError."""
        with pytest.raises(ValueError, match="Year must be greater than 1900"):
            PhivolcsEarthquakeInfoScraper(month=1, year=1899)

    def test_year_validation_rejects_future(self):
        """Test that year > current year raises ValueError."""
        future_year = datetime.now().year + 1
        with pytest.raises(ValueError, match="less than the current year"):
            PhivolcsEarthquakeInfoScraper(month=1, year=future_year)

    def test_future_date_validation_in_run(self, tmp_path):
        """Test that run() rejects future dates."""
        now = datetime.now()
        if now.month < 12:
            future_month = now.month + 1
            future_year = now.year
        else:
            future_month = 1
            future_year = now.year + 1

        scraper = PhivolcsEarthquakeInfoScraper(
            month=future_month, year=future_year, output_path=str(tmp_path)
        )

        with pytest.raises(ValueError, match="is in the future"):
            scraper.run()


class TestPhivolcsEarthquakeInfoScraperScraping:
    """Test scraping functionality with mocked requests."""

    @responses.activate
    def test_extract_main_page_success(self):
        """Test successful extraction of main page."""
        mock_html = "<html><body>Test content</body></html>"
        responses.add(
            responses.GET,
            "https://earthquake.phivolcs.dost.gov.ph",
            body=mock_html,
            status=200,
        )

        scraper = PhivolcsEarthquakeInfoScraper()
        content = scraper.extract_main_page()
        assert content == mock_html.encode()

    @responses.activate
    def test_extract_month_page_success(self):
        """Test successful extraction of monthly page."""
        mock_html = "<html><body>Monthly data</body></html>"
        url = (
            "https://earthquake.phivolcs.dost.gov.ph/"
            "EQLatest-Monthly/2025/2025_August.html"
        )
        responses.add(
            responses.GET,
            url,
            body=mock_html,
            status=200,
        )

        scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025)
        content = scraper.extract_month_page()
        assert content == mock_html.encode()

    def test_extract_target_table(self):
        """Test extraction of target table from HTML."""
        # Create mock HTML with 3 tables (we extract the 3rd one)
        mock_html = """
        <html>
            <body>
                <table><tr><td>Table 1</td></tr></table>
                <table><tr><td>Table 2</td></tr></table>
                <table>
                    <tr><th>Date</th><th>Magnitude</th></tr>
                    <tr><td>2025-08-01</td><td>5.0</td></tr>
                </table>
            </body>
        </html>
        """

        scraper = PhivolcsEarthquakeInfoScraper()
        df = scraper.extract_target_table(mock_html.encode())

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    @responses.activate
    def test_run_with_current_month(self, tmp_path):
        """Test run method for current month with mocked response."""
        # Create mock HTML with proper table structure
        mock_html = """
        <html>
            <body>
                <table><tr><td>Table 1</td></tr></table>
                <table><tr><td>Table 2</td></tr></table>
                <table>
                    <tr><th>Date</th><th>Magnitude</th></tr>
                    <tr><td>2025-10-01</td><td>5.0</td></tr>
                    <tr><td>2025-10-02</td><td>4.5</td></tr>
                </table>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            "https://earthquake.phivolcs.dost.gov.ph",
            body=mock_html,
            status=200,
        )

        scraper = PhivolcsEarthquakeInfoScraper(output_path=str(tmp_path))
        result_df = scraper.run()

        # Check that run() returns a DataFrame
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) > 0

        # Check that CSV was created
        now = datetime.now()
        expected_file = (
            tmp_path / f"phivolcs_earthquake_data_{now.month}_{now.year}.csv"
        )
        assert expected_file.exists()

    @responses.activate
    def test_run_with_specific_month(self, tmp_path):
        """Test run method for specific month with mocked response."""
        mock_html = """
        <html>
            <body>
                <table><tr><td>Table 1</td></tr></table>
                <table><tr><td>Table 2</td></tr></table>
                <table>
                    <tr><th>Date</th><th>Magnitude</th></tr>
                    <tr><td>2025-08-01</td><td>5.0</td></tr>
                </table>
            </body>
        </html>
        """

        url = (
            "https://earthquake.phivolcs.dost.gov.ph/"
            "EQLatest-Monthly/2025/2025_August.html"
        )
        responses.add(
            responses.GET,
            url,
            body=mock_html,
            status=200,
        )

        scraper = PhivolcsEarthquakeInfoScraper(
            month=8, year=2025, output_path=str(tmp_path)
        )
        result_df = scraper.run()

        # Check that run() returns a DataFrame
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) > 0

        # Check that CSV was created
        expected_file = tmp_path / "phivolcs_earthquake_data_8_2025.csv"
        assert expected_file.exists()


class TestPhivolcsEarthquakeInfoScraperExportToCSV:
    """Test export_to_csv functionality."""

    @responses.activate
    def test_run_with_export_to_csv_false_current_month(self, tmp_path):
        """Test run method with export_to_csv=False for current month."""
        mock_html = """
        <html>
            <body>
                <table><tr><td>Table 1</td></tr></table>
                <table><tr><td>Table 2</td></tr></table>
                <table>
                    <tr><th>Date</th><th>Magnitude</th></tr>
                    <tr><td>2025-10-01</td><td>5.0</td></tr>
                    <tr><td>2025-10-02</td><td>4.5</td></tr>
                </table>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            "https://earthquake.phivolcs.dost.gov.ph",
            body=mock_html,
            status=200,
        )

        scraper = PhivolcsEarthquakeInfoScraper(
            output_path=str(tmp_path), export_to_csv=False
        )
        result_df = scraper.run()

        # Check that run() returns a DataFrame
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) > 0

        # Check that NO CSV was created
        now = datetime.now()
        expected_file = (
            tmp_path / f"phivolcs_earthquake_data_{now.month}_{now.year}.csv"
        )
        assert not expected_file.exists()

    @responses.activate
    def test_run_with_export_to_csv_false_specific_month(self, tmp_path):
        """Test run method with export_to_csv=False for specific month."""
        mock_html = """
        <html>
            <body>
                <table><tr><td>Table 1</td></tr></table>
                <table><tr><td>Table 2</td></tr></table>
                <table>
                    <tr><th>Date</th><th>Magnitude</th></tr>
                    <tr><td>2025-08-01</td><td>5.0</td></tr>
                </table>
            </body>
        </html>
        """

        url = (
            "https://earthquake.phivolcs.dost.gov.ph/"
            "EQLatest-Monthly/2025/2025_August.html"
        )
        responses.add(
            responses.GET,
            url,
            body=mock_html,
            status=200,
        )

        scraper = PhivolcsEarthquakeInfoScraper(
            month=8, year=2025, output_path=str(tmp_path), export_to_csv=False
        )
        result_df = scraper.run()

        # Check that run() returns a DataFrame
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) > 0

        # Check that NO CSV was created
        expected_file = tmp_path / "phivolcs_earthquake_data_8_2025.csv"
        assert not expected_file.exists()
