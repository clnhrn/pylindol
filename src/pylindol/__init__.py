from importlib.metadata import PackageNotFoundError, version

from loguru import logger

from pylindol.earthquake_info_scraper import (
    OUTPUT_COLUMNS,
    DataNotAvailableError,
    PhivolcsEarthquakeInfoScraper,
    export_dataframe,
    scrape_months,
)

try:
    __version__ = version("pylindol")
except PackageNotFoundError:  # pragma: no cover - bare checkout
    __version__ = "unknown"

# Stay silent when imported as a library; applications opt in with
# logger.enable("pylindol"). See https://loguru.readthedocs.io for details.
logger.disable("pylindol")

__all__ = [
    "OUTPUT_COLUMNS",
    "DataNotAvailableError",
    "PhivolcsEarthquakeInfoScraper",
    "__version__",
    "export_dataframe",
    "scrape_months",
]
