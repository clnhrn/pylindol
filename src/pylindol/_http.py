"""HTTP session setup for talking to the PHIVOLCS website."""

import ssl
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import certifi
import requests
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pylindol.config.paths import CA_CERTIFICATE_PATH

try:
    _VERSION = version("pylindol")
except PackageNotFoundError:  # pragma: no cover - bare checkout
    _VERSION = "unknown"

# (connect, read) timeouts in seconds. Monthly pages are several MB and the
# site can be slow, so the read timeout is generous.
REQUEST_TIMEOUT = (10, 60)
USER_AGENT = f"pylindol/{_VERSION} (+https://github.com/clnhrn/pylindol)"


def create_ssl_context() -> ssl.SSLContext:
    """Build an SSL context that trusts certifi's CAs plus the bundled intermediate.

    Some PHIVOLCS servers send their certificate without the GlobalSign
    intermediate that issued it, so verification against certifi alone fails.
    Loading that intermediate into the context lets OpenSSL complete the chain.
    Everything stays in memory; no combined bundle is written to disk.

    Returns:
        The SSL context to use for PHIVOLCS requests.
    """
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        context.load_verify_locations(cafile=CA_CERTIFICATE_PATH)
    except (OSError, ssl.SSLError) as e:
        logger.warning(
            f"Could not load bundled CA certificate {CA_CERTIFICATE_PATH}, "
            f"using certifi only: {e}"
        )
    return context


class _SSLContextAdapter(HTTPAdapter):
    """HTTPAdapter that verifies connections with a given SSL context."""

    def __init__(self, ssl_context: ssl.SSLContext, **kwargs: Any) -> None:
        self._ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        kwargs["ssl_context"] = self._ssl_context
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any) -> Any:
        proxy_kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def build_session() -> requests.Session:
    """Create a session with retries, a descriptive User-Agent and PHIVOLCS TLS setup.

    Transient failures (connection errors, 429 and 5xx responses) are retried
    up to three times with exponential backoff.

    Returns:
        A configured `requests.Session`. Close it when done.
    """
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        # Return the last response instead of raising, so callers get a normal
        # HTTPError from raise_for_status().
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.mount(
        "https://", _SSLContextAdapter(create_ssl_context(), max_retries=retry)
    )
    return session
