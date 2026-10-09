import re
import sys
from pathlib import Path

import click
import pandas as pd
import requests
from loguru import logger

from pylindol.earthquake_info_scraper import (
    OUTPUT_FORMATS,
    DataNotAvailableError,
    PhivolcsEarthquakeInfoScraper,
    export_dataframe,
    format_dataframe,
    month_range,
    scrape_months,
)


def _configure_logging(verbose: bool, quiet: bool) -> None:
    """Route pylindol's logs to stderr at the requested verbosity.

    Args:
        verbose: Show debug-level detail (overrides `quiet`).
        quiet: Show only warnings and errors.
    """
    level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | {message}"
    )
    logger.enable("pylindol")
    logger.remove()
    logger.add(sys.stderr, level=level, format=log_format)


class YearMonth(click.ParamType):  # type: ignore[type-arg]
    """A month written as YYYY-MM, converted to a `(year, month)` tuple."""

    name = "YYYY-MM"

    def convert(self, value, param, ctx):
        if isinstance(value, tuple):
            return value
        match = re.fullmatch(r"(\d{4})-(\d{1,2})", value)
        if not match:
            self.fail(f"{value!r} is not in YYYY-MM format.", param, ctx)
        return int(match[1]), int(match[2])


@click.command()
@click.option(
    "--month",
    type=click.IntRange(1, 12),
    default=None,
    help="Month to scrape (1-12). Requires --year. Defaults to the current month.",
)
@click.option(
    "--year",
    type=int,
    default=None,
    help="Year to scrape (2017 or later). Requires --month.",
)
@click.option(
    "--start",
    type=YearMonth(),
    default=None,
    help="First month of a range to scrape, e.g. 2025-01. Requires --end.",
)
@click.option(
    "--end",
    type=YearMonth(),
    default=None,
    help="Last month of the range (inclusive), e.g. 2025-06. Requires --start.",
)
@click.option(
    "--output-path",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("data"),
    show_default=True,
    help="Directory to save the output file in.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="csv",
    show_default=True,
    help="Output file format. Parquet needs the pylindol[parquet] extra.",
)
@click.option(
    "--stdout",
    "to_stdout",
    is_flag=True,
    help="Print the data (CSV or JSON) instead of saving a file.",
)
@click.option(
    "--delay",
    type=click.FloatRange(min=0),
    default=1.0,
    show_default=True,
    help="Seconds to wait between requests when scraping a range.",
)
@click.option("-v", "--verbose", is_flag=True, help="Show debug-level logging.")
@click.option("-q", "--quiet", is_flag=True, help="Show only warnings and errors.")
@click.version_option(package_name="pylindol")
def main(
    month,
    year,
    start,
    end,
    output_path,
    output_format,
    to_stdout,
    delay,
    verbose,
    quiet,
):
    """
    Scrape earthquake information from the PHIVOLCS website.

    By default, scrapes the current month's data. Use --month/--year for a
    past month, or --start/--end for a range of months.
    """
    _configure_logging(verbose, quiet)

    if (start is None) != (end is None):
        raise click.UsageError("--start and --end must be used together.")
    if start is not None and (month is not None or year is not None):
        raise click.UsageError("Use either --month/--year or --start/--end, not both.")
    if to_stdout and output_format == "parquet":
        raise click.UsageError("--stdout supports csv and json, not parquet.")

    # Validate all input before touching the network.
    try:
        if start is not None:
            month_range(start, end)
            stem = (
                f"phivolcs_earthquake_data_{start[1]}_{start[0]}_to_{end[1]}_{end[0]}"
            )
        else:
            scraper = PhivolcsEarthquakeInfoScraper(
                month=month, year=year, export=False
            )
            stem = f"phivolcs_earthquake_data_{scraper.month}_{scraper.year}"
    except ValueError as e:
        raise click.UsageError(str(e)) from e

    try:
        df: pd.DataFrame = (
            scrape_months(start, end, delay=delay)
            if start is not None
            else scraper.fetch()
        )
    except DataNotAvailableError as e:
        raise click.ClickException(str(e)) from e
    except requests.RequestException as e:
        raise click.ClickException(f"Could not get data from PHIVOLCS: {e}") from e

    if to_stdout:
        click.echo(format_dataframe(df, output_format), nl=False)
        return
    try:
        export_dataframe(df, output_path / f"{stem}.{output_format}", output_format)
    except ImportError as e:
        raise click.ClickException(str(e)) from e
