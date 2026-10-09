"""Tests for the HTTP session setup."""

import ssl
from datetime import date, datetime, timedelta

import certifi
import pytest

from pylindol._http import (
    USER_AGENT,
    _SSLContextAdapter,
    build_session,
    create_ssl_context,
)
from pylindol.config.paths import CA_CERTIFICATE_PATH
from pylindol.earthquake_info_scraper import BASE_URL, PhivolcsEarthquakeInfoScraper


def _certifi_ca_count() -> int:
    return ssl.create_default_context(cafile=certifi.where()).cert_store_stats()[
        "x509_ca"
    ]


class TestSSLContext:
    def test_adds_bundled_intermediate_to_certifi(self):
        context = create_ssl_context()
        assert context.cert_store_stats()["x509_ca"] == _certifi_ca_count() + 1
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True

    def test_falls_back_to_certifi_when_cert_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "pylindol._http.CA_CERTIFICATE_PATH", tmp_path / "missing.pem"
        )
        context = create_ssl_context()
        assert context.cert_store_stats()["x509_ca"] == _certifi_ca_count()

    def test_bundled_certificate_is_not_about_to_expire(self):
        """Fails 90 days before expiry, as a reminder to check the certificate.

        Uses a private but long-stable CPython helper to read the PEM.
        """
        info = ssl._ssl._test_decode_cert(str(CA_CERTIFICATE_PATH))  # type: ignore[attr-defined]
        expires = datetime.strptime(info["notAfter"], "%b %d %H:%M:%S %Y %Z").date()
        assert expires - date.today() > timedelta(days=90), (
            f"{CA_CERTIFICATE_PATH.name} expires on {expires}. Check whether "
            "PHIVOLCS still needs it, and replace or remove it."
        )


class TestSession:
    def test_session_setup(self):
        with build_session() as session:
            assert session.headers["User-Agent"] == USER_AGENT
            adapter = session.get_adapter(BASE_URL)
            assert isinstance(adapter, _SSLContextAdapter)
            assert adapter.max_retries.total == 3
            assert 503 in adapter.max_retries.status_forcelist
            pool_kwargs = adapter.poolmanager.connection_pool_kw
            assert isinstance(pool_kwargs["ssl_context"], ssl.SSLContext)

    def test_proxy_manager_uses_the_ssl_context(self):
        with build_session() as session:
            adapter = session.get_adapter(BASE_URL)
            manager = adapter.proxy_manager_for("http://proxy.invalid:3128")
            assert manager.connection_pool_kw["ssl_context"] is adapter._ssl_context


@pytest.mark.live
class TestLive:
    """Hits the real PHIVOLCS website. Run with: pytest -m live"""

    def test_tls_verifies_against_phivolcs(self):
        with build_session() as session:
            response = session.get(BASE_URL, timeout=(10, 60))
        assert response.status_code == 200

    def test_archive_month_parses(self, monkeypatch):
        monkeypatch.setattr(
            "pylindol.earthquake_info_scraper._today", lambda: date.today()
        )
        df = PhivolcsEarthquakeInfoScraper(month=1, year=2024, export=False).run()
        assert len(df) > 100
        assert df["magnitude"].notna().all()
