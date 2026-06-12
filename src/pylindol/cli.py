import sys

import click
from loguru import logger

from pylindol.earthquake_info_scraper import (
    DataNotAvailableError,
    PhivolcsEarthquakeInfoScraper,
)


def _configure_logging(verbose: bool, quiet: bool) -> None:
    """Route pylindol's logs to stderr at the requested verbosity.

    Args:
        verbose: Show debug-level detail (overrides `quiet`).
        quiet: Show only warnings and errors.
    """
    level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    logger.enable("pylindol")
    logger.remove()
    logger.add(sys.stderr, level=level, format="<level>{level: <8}</level> {message}")


@click.command()
@click.option(
    "--month",
    type=int,
    default=None,
    help="Month to scrape (1-12). If not provided, scrapes current month.",
)
@click.option(
    "--year",
    type=int,
    default=None,
    help="Year to scrape. If not provided, scrapes current year.",
)
@click.option(
    "--output-path",
    type=str,
    default="data",
    help="Path to save the output CSV file. Default is 'data'.",
)
@click.option(
    "-v", "--verbose", is_flag=True, help="Show debug-level logging."
)
@click.option(
    "-q", "--quiet", is_flag=True, help="Show only warnings and errors."
)
def main(month, year, output_path, verbose, quiet):
    """
    Scrape earthquake information from PHIVOLCS website.

    By default, scrapes the current month's data. You can specify a different
    month and year to scrape historical data.
    """
    _configure_logging(verbose, quiet)
    scraper = PhivolcsEarthquakeInfoScraper(
        month=month, year=year, output_path=output_path
    )
    try:
        scraper.run()
    except DataNotAvailableError as e:
        raise click.ClickException(str(e))
