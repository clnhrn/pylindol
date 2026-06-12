"""
Unit tests for the CertificateHandler class.
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pylindol.utils.certificate_handler import CertificateHandler


def _make_cert(path: Path) -> Path:
    """Write a minimal PEM certificate to `path` and return it."""
    path.write_text(
        "-----BEGIN CERTIFICATE-----\n"
        "MIIDXTCCAkWgAwIBAgIJAKoK/OvM8K5AMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV\n"
        "-----END CERTIFICATE-----\n"
    )
    return path


class TestCertificateHandler:
    """Test cases for CertificateHandler class."""

    def test_init(self):
        """Test CertificateHandler initialization."""
        handler = CertificateHandler()
        assert handler.custom_certificates == []
        assert handler.certifi_bundle_path is not None

    def test_add_certificate_file_not_found(self):
        """Test add_certificate with non-existent file."""
        handler = CertificateHandler()
        with pytest.raises(FileNotFoundError):
            handler.add_certificate("/non/existent/path.pem")

    def test_add_certificate_not_a_file(self, tmp_path):
        """Test add_certificate with directory instead of file."""
        handler = CertificateHandler()
        with pytest.raises(ValueError, match="Path is not a file"):
            handler.add_certificate(tmp_path)

    def test_add_certificate_invalid_format(self, tmp_path):
        """Test add_certificate with invalid certificate format."""
        handler = CertificateHandler()
        cert_file = tmp_path / "invalid.pem"
        cert_file.write_text("not a certificate")

        with pytest.raises(ValueError, match="Invalid certificate format"):
            handler.add_certificate(cert_file)

    @patch("ssl.create_default_context")
    def test_add_certificate_valid(self, mock_ssl_context, tmp_path):
        """Test add_certificate with valid certificate."""
        handler = CertificateHandler()
        cert_file = tmp_path / "valid.pem"

        # Create a mock valid certificate
        cert_content = """-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAKoK/OvM8K5AMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV
BAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX
aWRnaXRzIFB0eSBMdGQwHhcNMTcwOTEyMjE1MjAyWhcNMTgwOTEyMjE1MjAyWjBF
-----END CERTIFICATE-----"""

        cert_file.write_text(cert_content)

        # Mock SSL context to not actually validate
        mock_context = MagicMock()
        mock_ssl_context.return_value = mock_context

        result = handler.add_certificate(cert_file)

        assert result is True
        assert len(handler.custom_certificates) == 1
        assert handler.custom_certificates[0] == cert_file

    def test_create_combined_bundle_no_custom_certs(self):
        """Test create_combined_bundle with no custom certificates."""
        handler = CertificateHandler()
        result = handler.create_combined_bundle()
        assert result == Path(handler.certifi_bundle_path)

    def test_create_combined_bundle_with_custom_certs(self, tmp_path):
        """Test create_combined_bundle with custom certificates."""
        cache_path = tmp_path / "bundle.pem"
        handler = CertificateHandler(bundle_cache_path=cache_path)

        cert1 = _make_cert(tmp_path / "cert1.pem")
        cert2 = _make_cert(tmp_path / "cert2.pem")

        with patch("ssl.create_default_context"):
            handler.add_certificate(cert1)
            handler.add_certificate(cert2)

        result = handler.create_combined_bundle()

        # Writes to the configured cache path, not a per-process temp file.
        assert result == cache_path
        assert result.exists()
        content = result.read_text()
        assert "certificate" in content.lower()

    def test_get_bundle_path_no_custom_certs(self):
        """Test get_bundle_path with no custom certificates."""
        handler = CertificateHandler()
        result = handler.get_bundle_path()
        assert result == Path(handler.certifi_bundle_path)

    def test_get_bundle_path_caches_combined_bundle(self, tmp_path):
        """Repeated calls reuse the same combined bundle instead of rebuilding it."""
        cache_path = tmp_path / "bundle.pem"
        handler = CertificateHandler(bundle_cache_path=cache_path)
        with patch("ssl.create_default_context"):
            handler.add_certificate(_make_cert(tmp_path / "test.pem"))

        first = handler.get_bundle_path()
        second = handler.get_bundle_path()
        assert first == second == cache_path

    def test_get_bundle_path_reuses_fresh_bundle_without_rebuilding(self, tmp_path):
        """A fresh cached bundle is reused by a new handler without a rebuild."""
        cache_path = tmp_path / "bundle.pem"
        cert = _make_cert(tmp_path / "test.pem")

        with patch("ssl.create_default_context"):
            builder = CertificateHandler(bundle_cache_path=cache_path)
            builder.add_certificate(cert)
            builder.get_bundle_path()  # builds the cache file

            reuser = CertificateHandler(bundle_cache_path=cache_path)
            reuser.add_certificate(cert)

        with patch.object(
            reuser, "create_combined_bundle", wraps=reuser.create_combined_bundle
        ) as spy:
            result = reuser.get_bundle_path()
        assert result == cache_path
        spy.assert_not_called()

    def test_get_bundle_path_rebuilds_stale_bundle(self, tmp_path):
        """A bundle older than its certificate is rebuilt rather than reused."""
        cache_path = tmp_path / "bundle.pem"
        cert = _make_cert(tmp_path / "test.pem")

        with patch("ssl.create_default_context"):
            builder = CertificateHandler(bundle_cache_path=cache_path)
            builder.add_certificate(cert)
            builder.get_bundle_path()

            # Make the certificate newer than the cached bundle.
            future = cache_path.stat().st_mtime + 100
            os.utime(cert, (future, future))

            handler = CertificateHandler(bundle_cache_path=cache_path)
            handler.add_certificate(cert)
        assert handler._bundle_is_fresh(cache_path) is False
        with patch.object(
            handler, "create_combined_bundle", wraps=handler.create_combined_bundle
        ) as spy:
            handler.get_bundle_path()
        spy.assert_called_once()

    def test_add_certificate_invalidates_cached_bundle(self, tmp_path):
        """Adding a certificate clears the in-memory cached bundle path."""
        cache_path = tmp_path / "bundle.pem"
        handler = CertificateHandler(bundle_cache_path=cache_path)

        with patch("ssl.create_default_context"):
            handler.add_certificate(_make_cert(tmp_path / "cert1.pem"))
            handler.get_bundle_path()
            assert handler._combined_bundle_path is not None

            handler.add_certificate(_make_cert(tmp_path / "cert2.pem"))

        assert handler._combined_bundle_path is None
