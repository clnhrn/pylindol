"""Tests for the CLI interface."""

from unittest.mock import patch

import pytest
import responses
from click.testing import CliRunner
from loguru import logger

from pylindol.cli import _configure_logging, main
from pylindol.earthquake_info_scraper import PhivolcsEarthquakeInfoScraper


class TestCLI:
    """Test CLI functionality."""

    def test_cli_help(self):
        """Test that CLI help command works."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        expected = "Scrape earthquake information from PHIVOLCS website"
        assert expected in result.output
        assert "--month" in result.output
        assert "--year" in result.output
        assert "--output-path" in result.output

    @responses.activate
    def test_cli_with_valid_options(self, tmp_path, monkeypatch):
        """Test CLI with valid month and year options."""
        # Mock the HTTP response
        mock_html = """
        <html>
            <body>
                <table><tr><td>Table 1</td></tr></table>
                <table><tr><td>Table 2</td></tr></table>
                <table>
                    <tr><th>Date - Time  (Philippine Time)</th><th>Magnitude</th></tr>
                    <tr><td>2025-08-01 09:15:00</td><td>5.0</td></tr>
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

        runner = CliRunner()
        result = runner.invoke(
            main, ["--month", "8", "--year", "2025", "--output-path", str(tmp_path)]
        )

        # Should succeed
        assert result.exit_code == 0

        # Check that CSV file was created
        import os

        csv_files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        assert len(csv_files) == 1
        assert "phivolcs_earthquake_data_8_2025.csv" in csv_files[0]

    def test_cli_with_invalid_month(self):
        """Test CLI rejects invalid month."""
        runner = CliRunner()
        result = runner.invoke(main, ["--month", "13", "--year", "2025"])

        # Should fail with error
        assert result.exit_code != 0

    def test_cli_with_only_month(self):
        """Test CLI rejects month without year."""
        runner = CliRunner()
        result = runner.invoke(main, ["--month", "8"])

        # Should fail with error
        assert result.exit_code != 0
        # Check that exception was raised (it won't be in output with Click)
        assert isinstance(result.exception, ValueError)

    @responses.activate
    def test_cli_shows_friendly_error_when_data_unavailable(self, tmp_path):
        """Unavailable months show a clean message instead of a traceback."""
        # No <th>, so pandas assigns integer columns: the unavailable-month case.
        mock_html = """
        <html>
            <body>
                <table><tr><td>Table 1</td></tr></table>
                <table><tr><td>Table 2</td></tr></table>
                <table>
                    <tr><td>Date - Time  (Philippine Time)</td><td>Magnitude</td></tr>
                </table>
            </body>
        </html>
        """

        url = (
            "https://earthquake.phivolcs.dost.gov.ph/"
            "EQLatest-Monthly/2017/2017_January.html"
        )
        responses.add(responses.GET, url, body=mock_html, status=200)

        runner = CliRunner()
        result = runner.invoke(
            main, ["--month", "1", "--year", "2017", "--output-path", str(tmp_path)]
        )

        assert result.exit_code != 0
        assert "not available" in result.output
        # A friendly Click error, not an unhandled traceback.
        assert result.exc_info is None or result.exception.__class__.__name__ != "AttributeError"


class TestLoggingBehavior:
    """Test logging configuration and the library's silent-by-default behavior."""

    @pytest.mark.parametrize(
        "verbose, quiet, expected_level",
        [
            (False, False, "INFO"),
            (True, False, "DEBUG"),
            (False, True, "WARNING"),
            (True, True, "DEBUG"),  # verbose wins over quiet
        ],
    )
    def test_configure_logging_sets_expected_level(self, verbose, quiet, expected_level):
        """The verbosity flags map to the right loguru level and enable pylindol."""
        with patch("pylindol.cli.logger") as mock_logger:
            _configure_logging(verbose=verbose, quiet=quiet)

        mock_logger.enable.assert_called_once_with("pylindol")
        mock_logger.remove.assert_called_once()
        _, kwargs = mock_logger.add.call_args
        assert kwargs["level"] == expected_level

    def test_library_logs_suppressed_when_disabled(self):
        """With pylindol disabled (the default), its logs reach no caller sink."""
        logger.disable("pylindol")
        messages = []
        sink_id = logger.add(messages.append, level="DEBUG")
        try:
            # Construction logs at DEBUG inside the pylindol package.
            PhivolcsEarthquakeInfoScraper(month=8, year=2025, export_to_csv=False)
        finally:
            logger.remove(sink_id)

        assert messages == []
