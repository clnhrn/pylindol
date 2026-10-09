"""Tests for the CLI interface."""

import json
from unittest.mock import patch

import pandas as pd
import pytest
import requests
import responses
from click.testing import CliRunner
from conftest import BASE_URL, archive_url, load_page
from loguru import logger

from pylindol import __version__
from pylindol.cli import _configure_logging, main
from pylindol.earthquake_info_scraper import (
    OUTPUT_COLUMNS,
    PhivolcsEarthquakeInfoScraper,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def august_2025():
    responses.add(
        responses.GET,
        archive_url(2025, "August"),
        body=load_page("archive_2025_August"),
    )


class TestCLI:
    """Command line behavior."""

    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert (
            "Scrape earthquake information from the PHIVOLCS website" in result.output
        )
        for option in ("--month", "--year", "--start", "--end", "--format", "--stdout"):
            assert option in result.output

    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    @responses.activate
    def test_writes_csv_for_month(self, runner, tmp_path, august_2025):
        result = runner.invoke(
            main, ["--month", "8", "--year", "2025", "--output-path", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        df = pd.read_csv(tmp_path / "phivolcs_earthquake_data_8_2025.csv")
        assert list(df.columns) == OUTPUT_COLUMNS
        assert len(df) == 7

    @responses.activate
    def test_current_month_by_default(self, runner, tmp_path):
        responses.add(responses.GET, BASE_URL, body=load_page("main_page_2026_10"))
        result = runner.invoke(main, ["--output-path", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "phivolcs_earthquake_data_10_2026.csv").exists()

    @responses.activate
    @pytest.mark.parametrize("fmt", ["json", "parquet"])
    def test_other_formats(self, runner, tmp_path, august_2025, fmt):
        result = runner.invoke(
            main,
            ["--month", "8", "--year", "2025", "--format", fmt]
            + ["--output-path", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / f"phivolcs_earthquake_data_8_2025.{fmt}").exists()

    @responses.activate
    def test_stdout_json(self, runner, tmp_path, monkeypatch, august_2025):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            main,
            ["--month", "8", "--year", "2025", "--stdout", "--format", "json", "-q"],
        )
        assert result.exit_code == 0, result.output
        assert len(json.loads(result.stdout)) == 7
        assert list(tmp_path.iterdir()) == []

    @responses.activate
    def test_stdout_csv(self, runner, august_2025):
        result = runner.invoke(
            main, ["--month", "8", "--year", "2025", "--stdout", "-q"]
        )
        assert result.exit_code == 0, result.output
        assert result.stdout.splitlines()[0] == ",".join(OUTPUT_COLUMNS)

    @responses.activate
    def test_range(self, runner, tmp_path, august_2025):
        responses.add(responses.GET, archive_url(2025, "September"), status=404)
        result = runner.invoke(
            main,
            ["--start", "2025-08", "--end", "2025-09", "--output-path", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        df = pd.read_csv(tmp_path / "phivolcs_earthquake_data_8_2025_to_9_2025.csv")
        assert len(df) == 7
        assert "Skipping" in result.stderr

    @pytest.mark.parametrize(
        "args, message",
        [
            (["--month", "13", "--year", "2025"], "1<=x<=12"),
            (["--month", "8"], "year must also be provided"),
            (["--month", "12", "--year", "2016"], "archives start in January 2017"),
            (["--month", "12", "--year", "2026"], "in the future"),
            (["--start", "2025-01"], "--start and --end must be used together"),
            (["--start", "2025-01", "--end", "2025/02"], "YYYY-MM"),
            (["--start", "2025-03", "--end", "2025-01"], "must not be after"),
            (
                ["--start", "2025-01", "--end", "2025-02", "--month", "1"],
                "not both",
            ),
            (["--stdout", "--format", "parquet"], "not parquet"),
        ],
    )
    def test_invalid_input_is_a_usage_error(self, runner, args, message):
        result = runner.invoke(main, args)
        assert result.exit_code == 2
        assert message in result.output
        assert "Traceback" not in result.output

    @responses.activate
    def test_data_unavailable_is_a_friendly_error(self, runner, tmp_path):
        responses.add(responses.GET, archive_url(2025, "August"), status=404)
        result = runner.invoke(
            main, ["--month", "8", "--year", "2025", "--output-path", str(tmp_path)]
        )
        assert result.exit_code == 1
        assert "not available" in result.output
        assert "Traceback" not in result.output

    @responses.activate
    def test_network_error_is_a_friendly_error(self, runner):
        responses.add(
            responses.GET,
            archive_url(2025, "August"),
            body=requests.ConnectionError("connection refused"),
        )
        result = runner.invoke(main, ["--month", "8", "--year", "2025"])
        assert result.exit_code == 1
        assert "Could not get data from PHIVOLCS" in result.output

    @responses.activate
    def test_missing_pyarrow_is_a_friendly_error(self, runner, tmp_path, mocker):
        responses.add(
            responses.GET,
            archive_url(2025, "August"),
            body=load_page("archive_2025_August"),
        )
        mocker.patch.object(pd.DataFrame, "to_parquet", side_effect=ImportError)
        result = runner.invoke(
            main,
            ["--month", "8", "--year", "2025", "--format", "parquet"]
            + ["--output-path", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "pylindol[parquet]" in result.output


class TestLoggingBehavior:
    """Logging configuration and the library's silent-by-default behavior."""

    @pytest.mark.parametrize(
        "verbose, quiet, expected_level",
        [
            (False, False, "INFO"),
            (True, False, "DEBUG"),
            (False, True, "WARNING"),
            (True, True, "DEBUG"),  # verbose wins over quiet
        ],
    )
    def test_configure_logging_sets_level(self, verbose, quiet, expected_level):
        with patch("pylindol.cli.logger") as mock_logger:
            _configure_logging(verbose=verbose, quiet=quiet)

        mock_logger.enable.assert_called_once_with("pylindol")
        mock_logger.remove.assert_called_once()
        _, kwargs = mock_logger.add.call_args
        assert kwargs["level"] == expected_level

    @responses.activate
    def test_library_logs_suppressed_when_disabled(self, august_2025):
        """With pylindol disabled (the default), its logs reach no caller sink."""
        logger.disable("pylindol")
        messages = []
        sink_id = logger.add(messages.append, level="DEBUG")
        try:
            PhivolcsEarthquakeInfoScraper(month=8, year=2025, export=False).run()
        finally:
            logger.remove(sink_id)

        assert messages == []
