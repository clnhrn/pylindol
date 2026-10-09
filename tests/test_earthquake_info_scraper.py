"""Tests for the PhivolcsEarthquakeInfoScraper class and helpers."""

import json
from unittest.mock import MagicMock

import pandas as pd
import pytest
import requests
import responses
from conftest import BASE_URL, archive_url, load_page

from pylindol._http import build_session
from pylindol.earthquake_info_scraper import (
    OUTPUT_COLUMNS,
    DataNotAvailableError,
    PhivolcsEarthquakeInfoScraper,
    export_dataframe,
    format_dataframe,
    month_range,
    scrape_months,
)


class TestInit:
    """Construction and input validation."""

    def test_defaults_to_current_philippine_month(self, frozen_today):
        scraper = PhivolcsEarthquakeInfoScraper()
        assert (scraper.year, scraper.month) == (frozen_today.year, frozen_today.month)
        assert scraper.output_path == "data"
        assert scraper.export is True
        assert scraper.output_format == "csv"

    def test_month_url_and_file_name(self):
        scraper = PhivolcsEarthquakeInfoScraper(
            month=8, year=2025, output_format="json"
        )
        assert scraper.month_url == archive_url(2025, "August")
        assert scraper.file_name == "phivolcs_earthquake_data_8_2025.json"

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({"month": 8}, "year must also be provided"),
            ({"year": 2025}, "month must also be provided"),
            ({"month": 0, "year": 2025}, "between 1 and 12"),
            ({"month": 13, "year": 2025}, "between 1 and 12"),
            ({"month": 12, "year": 2016}, "archives start in January 2017"),
            ({"month": 11, "year": 2026}, "November 2026 is in the future"),
            ({"month": 1, "year": 2027}, "is in the future"),
            ({"month": 8, "year": 2025, "output_format": "xml"}, "output_format"),
        ],
    )
    def test_invalid_input_raises_value_error(self, kwargs, message):
        with pytest.raises(ValueError, match=message):
            PhivolcsEarthquakeInfoScraper(**kwargs)

    @pytest.mark.parametrize("month, year", [("8", 2025), (8, 2025.0), (True, 2025)])
    def test_non_int_input_raises_type_error(self, month, year):
        with pytest.raises(TypeError, match="must be an int"):
            PhivolcsEarthquakeInfoScraper(month=month, year=year)

    def test_earliest_archive_month_is_accepted(self):
        scraper = PhivolcsEarthquakeInfoScraper(month=1, year=2017)
        assert scraper.month_url == archive_url(2017, "January")

    def test_export_to_csv_is_a_deprecated_alias(self):
        with pytest.warns(DeprecationWarning, match="export_to_csv"):
            scraper = PhivolcsEarthquakeInfoScraper(
                month=8, year=2025, export_to_csv=False
            )
        assert scraper.export is False


class TestExtractAndNormalize:
    """Parsing real PHIVOLCS page layouts into the normalized columns."""

    @pytest.mark.parametrize(
        "page, year, month, rows",
        [
            ("main_page_2026_10", 2026, 10, 5),
            ("archive_2025_August", 2025, 8, 7),
            ("archive_2019_June", 2019, 6, 8),
            ("archive_2018_January", 2018, 1, 6),
            ("archive_2017_January", 2017, 1, 7),
        ],
    )
    def test_every_layout_parses_to_the_same_columns(self, page, year, month, rows):
        scraper = PhivolcsEarthquakeInfoScraper(month=month, year=year)
        df = scraper._normalize(scraper.extract_target_table(load_page(page)))

        assert list(df.columns) == OUTPUT_COLUMNS
        assert len(df) == rows
        assert str(df["datetime"].dt.tz) == "Asia/Manila"
        assert (df["datetime"].dt.month == month).all()
        for col in ("latitude", "longitude", "depth_km", "magnitude"):
            assert df[col].dtype == "float64"
            assert df[col].notna().all()
        assert df["latitude"].between(0, 25).all()
        assert df["longitude"].between(110, 135).all()
        assert not df["location"].str.contains("  ").any()
        assert df["location"].str.contains("°").all()

    def test_values_match_the_page(self):
        scraper = PhivolcsEarthquakeInfoScraper(month=1, year=2018)
        df = scraper._normalize(
            scraper.extract_target_table(load_page("archive_2018_January"))
        )
        first = df.iloc[0]
        assert first["datetime"].isoformat() == "2018-01-31T23:07:00+08:00"
        assert (first["date"], first["time"]) == ("2018-01-31", "23:07:00")
        assert (first["latitude"], first["longitude"]) == (13.20, 125.48)
        assert (first["depth_km"], first["magnitude"]) == (25.0, 2.8)
        assert first["location"] == "082m N 29° E of Palapag (Northern Samar)"

    def test_tolerates_spacing_typos_in_old_pages(self):
        # Real values from the June 2017 archive.
        table = pd.DataFrame(
            [
                ["16 Jun 2017 -12:50 AM", "12.29", "125.91", "043", "3.0", "a"],
                ["11Jun 2017 - 01:49 AM", "13.10", "125.73", "025", "3.2", "b"],
                ["June", None, None, None, None, None],
            ]
        )
        scraper = PhivolcsEarthquakeInfoScraper(month=6, year=2017)
        df = scraper._normalize(table)
        assert list(df["datetime"].map(lambda ts: ts.isoformat())) == [
            "2017-06-16T00:50:00+08:00",
            "2017-06-11T01:49:00+08:00",
        ]

    def test_main_page_is_filtered_to_the_requested_month(self):
        page = load_page("main_page_2026_10")
        october = PhivolcsEarthquakeInfoScraper(month=10, year=2026)
        september = PhivolcsEarthquakeInfoScraper(month=9, year=2026)

        oct_df = october._normalize(october.extract_target_table(page))
        sep_df = september._normalize(september.extract_target_table(page))

        assert set(oct_df["date"].str[:7]) == {"2026-10"}
        assert set(sep_df["date"].str[:7]) == {"2026-09"}

    def test_page_without_earthquake_table_raises(self):
        scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025)
        page = b"<html><table><tr><td>Hello</td></tr></table></html>"
        with pytest.raises(DataNotAvailableError, match="August 2025"):
            scraper.extract_target_table(page)

    def test_page_with_no_tables_raises(self):
        scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025)
        with pytest.raises(DataNotAvailableError):
            scraper.extract_target_table(b"<html><body>Maintenance</body></html>")


class TestFetch:
    """Choosing the right page and handling HTTP outcomes."""

    @responses.activate
    def test_current_month_reads_the_main_page(self):
        responses.add(responses.GET, BASE_URL, body=load_page("main_page_2026_10"))
        df = PhivolcsEarthquakeInfoScraper(export=False).run()
        assert len(df) == 5
        assert responses.calls[0].request.url.rstrip("/") == BASE_URL

    @responses.activate
    def test_past_month_reads_the_archive(self):
        url = archive_url(2025, "August")
        responses.add(responses.GET, url, body=load_page("archive_2025_August"))
        df = PhivolcsEarthquakeInfoScraper(month=8, year=2025, export=False).run()
        assert len(df) == 7
        assert responses.calls[0].request.url == url

    @responses.activate
    def test_previous_month_falls_back_to_main_page_until_archived(self):
        responses.add(responses.GET, archive_url(2026, "September"), status=404)
        responses.add(responses.GET, BASE_URL, body=load_page("main_page_2026_10"))
        df = PhivolcsEarthquakeInfoScraper(month=9, year=2026, export=False).run()
        assert set(df["date"].str[:7]) == {"2026-09"}
        assert len(responses.calls) == 2

    @responses.activate
    def test_missing_older_archive_raises_data_not_available(self):
        responses.add(responses.GET, archive_url(2026, "August"), status=404)
        scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2026, export=False)
        with pytest.raises(DataNotAvailableError, match="August 2026"):
            scraper.run()
        assert len(responses.calls) == 1

    @responses.activate
    def test_archive_with_no_rows_for_month_raises(self):
        # An archive page that only has rows for a different month.
        responses.add(
            responses.GET,
            archive_url(2025, "July"),
            body=load_page("archive_2025_August"),
        )
        scraper = PhivolcsEarthquakeInfoScraper(month=7, year=2025, export=False)
        with pytest.raises(DataNotAvailableError):
            scraper.run()

    @responses.activate
    def test_server_error_raises_http_error(self):
        responses.add(responses.GET, archive_url(2025, "August"), status=500)
        scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025, export=False)
        with pytest.raises(requests.HTTPError):
            scraper.run()

    def test_requests_use_a_timeout(self):
        session = MagicMock()
        session.get.return_value.content = load_page("archive_2025_August")
        scraper = PhivolcsEarthquakeInfoScraper(
            month=8, year=2025, export=False, session=session
        )
        scraper.run()
        _, kwargs = session.get.call_args
        assert kwargs["timeout"] is not None


class TestExport:
    """Writing files in each format."""

    @pytest.fixture
    def df(self):
        scraper = PhivolcsEarthquakeInfoScraper(month=8, year=2025)
        return scraper._normalize(
            scraper.extract_target_table(load_page("archive_2025_August"))
        )

    @responses.activate
    def test_run_exports_csv_by_default(self, tmp_path):
        responses.add(
            responses.GET,
            archive_url(2025, "August"),
            body=load_page("archive_2025_August"),
        )
        output = tmp_path / "nested" / "dir"
        PhivolcsEarthquakeInfoScraper(month=8, year=2025, output_path=output).run()

        written = pd.read_csv(output / "phivolcs_earthquake_data_8_2025.csv")
        assert list(written.columns) == OUTPUT_COLUMNS
        assert written.loc[0, "datetime"] == "2025-08-31 23:56:00+08:00"

    @responses.activate
    def test_run_without_export_writes_nothing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        responses.add(
            responses.GET,
            archive_url(2025, "August"),
            body=load_page("archive_2025_August"),
        )
        PhivolcsEarthquakeInfoScraper(month=8, year=2025, export=False).run()
        assert list(tmp_path.iterdir()) == []

    def test_json_keeps_the_philippine_offset(self, df, tmp_path):
        path = export_dataframe(df, tmp_path / "out.json", "json")
        records = json.loads(path.read_text(encoding="utf-8"))
        assert records[0]["datetime"] == "2025-08-31T23:56:00+08:00"
        assert "°" in records[0]["location"]

    def test_parquet_round_trips(self, df, tmp_path):
        path = export_dataframe(df, tmp_path / "out.parquet", "parquet")
        result = pd.read_parquet(path)
        # pyarrow restores Asia/Manila as a different tz object, so compare
        # the zone by name and the values exactly.
        assert str(result["datetime"].dt.tz) == "Asia/Manila"
        pd.testing.assert_frame_equal(result, df, check_dtype=False)

    def test_parquet_without_pyarrow_gives_install_hint(self, df, tmp_path, mocker):
        mocker.patch.object(pd.DataFrame, "to_parquet", side_effect=ImportError)
        with pytest.raises(ImportError, match=r"pylindol\[parquet\]"):
            export_dataframe(df, tmp_path / "out.parquet", "parquet")

    def test_unknown_format_raises(self, df, tmp_path):
        with pytest.raises(ValueError, match="output_format"):
            export_dataframe(df, tmp_path / "out.xml", "xml")  # type: ignore[arg-type]

    def test_format_dataframe(self, df):
        csv_text = format_dataframe(df, "csv")
        assert csv_text.splitlines()[0] == ",".join(OUTPUT_COLUMNS)
        assert "\r" not in csv_text
        assert json.loads(format_dataframe(df, "json"))[0]["magnitude"] == 1.9
        with pytest.raises(ValueError):
            format_dataframe(df, "parquet")  # type: ignore[arg-type]


class TestScrapeMonths:
    """Scraping a range of months."""

    def test_month_range_crosses_years(self):
        assert month_range((2024, 11), (2025, 2)) == [
            (2024, 11),
            (2024, 12),
            (2025, 1),
            (2025, 2),
        ]

    def test_month_range_rejects_reversed_range(self):
        with pytest.raises(ValueError, match="must not be after"):
            month_range((2025, 3), (2025, 1))

    def test_month_range_validates_both_ends(self):
        with pytest.raises(ValueError, match="2017"):
            month_range((2016, 12), (2017, 2))

    @responses.activate
    def test_concatenates_months_and_skips_missing(self):
        responses.add(
            responses.GET,
            archive_url(2025, "August"),
            body=load_page("archive_2025_August"),
        )
        responses.add(responses.GET, archive_url(2025, "September"), status=404)
        df = scrape_months((2025, 8), (2025, 9))
        assert len(df) == 7
        assert list(df.columns) == OUTPUT_COLUMNS

    @responses.activate
    def test_raises_on_missing_month_when_not_skipping(self):
        responses.add(responses.GET, archive_url(2025, "August"), status=404)
        with pytest.raises(DataNotAvailableError):
            scrape_months((2025, 8), (2025, 8), skip_missing=False)

    @responses.activate
    def test_raises_when_no_month_has_data(self):
        responses.add(responses.GET, archive_url(2025, "August"), status=404)
        with pytest.raises(DataNotAvailableError, match="No earthquake data"):
            scrape_months((2025, 8), (2025, 8))

    @responses.activate
    def test_reuses_one_session(self, mocker):
        for name in ("June", "July"):
            responses.add(
                responses.GET,
                archive_url(2025, name),
                body=load_page("archive_2025_August"),
            )
        build = mocker.patch(
            "pylindol.earthquake_info_scraper.build_session", wraps=build_session
        )
        with pytest.raises(DataNotAvailableError):
            # The fixture only has August rows, so both months are empty.
            scrape_months((2025, 6), (2025, 7))
        assert build.call_count == 1
