import click

from pylindol.earthquake_info_scraper import PhivolcsEarthquakeInfoScraper


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
def main(month, year, output_path):
    """
    Scrape earthquake information from PHIVOLCS website.

    By default, scrapes the current month's data. You can specify a different
    month and year to scrape historical data.
    """
    scraper = PhivolcsEarthquakeInfoScraper(
        month=month, year=year, output_path=output_path
    )
    scraper.run()
