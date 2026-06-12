"""Tests for the CLI interface."""

import responses
from click.testing import CliRunner

from pylindol.cli import main


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
