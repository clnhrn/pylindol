from loguru import logger

from pylindol.earthquake_info_scraper import PhivolcsEarthquakeInfoScraper

# Stay silent when imported as a library; applications opt in with
# logger.enable("pylindol"). See https://loguru.readthedocs.io for details.
logger.disable("pylindol")

__all__ = ["PhivolcsEarthquakeInfoScraper"]
