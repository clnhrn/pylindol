"""
Unit tests for the CertificateHandler class.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

import pytest
import ssl

from pylindol.utils.certificate_handler import (
    CertificateHandler,
    create_certificate_handler_with_ca,
)


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
        handler = CertificateHandler()

        # Create mock certificate files with proper PEM format
        cert1 = tmp_path / "cert1.pem"
        cert1.write_text(
            "-----BEGIN CERTIFICATE-----\n"
            "MIIDXTCCAkWgAwIBAgIJAKoK/OvM8K5AMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV\n"
            "BAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX\n"
            "aWRnaXRzIFB0eSBMdGQwHhcNMTcwOTEyMjE1MjAyWhcNMTgwOTEyMjE1MjAyWjBF\n"
            "-----END CERTIFICATE-----"
        )

        cert2 = tmp_path / "cert2.pem"
        cert2.write_text(
            "-----BEGIN CERTIFICATE-----\n"
            "MIIDXTCCAkWgAwIBAgIJAKoK/OvM8K5AMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV\n"
            "BAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX\n"
            "aWRnaXRzIFB0eSBMdGQwHhcNMTcwOTEyMjE1MjAyWhcNMTgwOTEyMjE1MjAyWjBF\n"
            "-----END CERTIFICATE-----"
        )

        # Mock SSL context for validation to avoid actual certificate parsing
        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = MagicMock()
            mock_ssl.return_value = mock_context

            handler.add_certificate(cert1)
            handler.add_certificate(cert2)

        result = handler.create_combined_bundle()

        # Should create a temporary file
        assert isinstance(result, Path)
        assert result.suffix == ".pem"

        # Verify the file exists and contains content
        assert result.exists()
        content = result.read_text()
        assert "certifi" in content.lower() or "certificate" in content.lower()

    def test_get_bundle_path_no_custom_certs(self):
        """Test get_bundle_path with no custom certificates."""
        handler = CertificateHandler()
        result = handler.get_bundle_path()
        assert result == Path(handler.certifi_bundle_path)

    def test_get_bundle_path_use_certifi_only(self, tmp_path):
        """Test get_bundle_path with use_combined=False."""
        handler = CertificateHandler()

        # Add a certificate but request certifi only
        cert_file = tmp_path / "test.pem"
        cert_file.write_text(
            "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----"
        )

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = MagicMock()
            mock_ssl.return_value = mock_context
            handler.add_certificate(cert_file)

        result = handler.get_bundle_path(use_combined=False)
        assert result == Path(handler.certifi_bundle_path)

    def test_clear_custom_certificates(self, tmp_path):
        """Test clear_custom_certificates method."""
        handler = CertificateHandler()

        # Add certificates
        cert1 = tmp_path / "cert1.pem"
        cert1.write_text(
            "-----BEGIN CERTIFICATE-----\ncert1\n-----END CERTIFICATE-----"
        )

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = MagicMock()
            mock_ssl.return_value = mock_context
            handler.add_certificate(cert1)

        assert len(handler.custom_certificates) == 1

        handler.clear_custom_certificates()
        assert len(handler.custom_certificates) == 0

    def test_list_certificates(self, tmp_path):
        """Test list_certificates method."""
        handler = CertificateHandler()

        cert1 = tmp_path / "cert1.pem"
        cert1.write_text(
            "-----BEGIN CERTIFICATE-----\ncert1\n-----END CERTIFICATE-----"
        )

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = MagicMock()
            mock_ssl.return_value = mock_context
            handler.add_certificate(cert1)

        certs = handler.list_certificates()
        assert len(certs) == 1
        assert certs[0] == cert1
        # Should return a copy, not the original list
        assert certs is not handler.custom_certificates

    def test_len(self, tmp_path):
        """Test __len__ method."""
        handler = CertificateHandler()
        assert len(handler) == 0

        cert1 = tmp_path / "cert1.pem"
        cert1.write_text(
            "-----BEGIN CERTIFICATE-----\ncert1\n-----END CERTIFICATE-----"
        )

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = MagicMock()
            mock_ssl.return_value = mock_context
            handler.add_certificate(cert1)

        assert len(handler) == 1

    def test_repr(self, tmp_path):
        """Test __repr__ method."""
        handler = CertificateHandler()
        assert "CertificateHandler(certificates=0)" in repr(handler)

        cert1 = tmp_path / "cert1.pem"
        cert1.write_text(
            "-----BEGIN CERTIFICATE-----\ncert1\n-----END CERTIFICATE-----"
        )

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = MagicMock()
            mock_ssl.return_value = mock_context
            handler.add_certificate(cert1)

        assert "CertificateHandler(certificates=1)" in repr(handler)


class TestCreateCertificateHandlerWithCA:
    """Test cases for create_certificate_handler_with_ca function."""

    def test_create_handler_with_ca(self, tmp_path):
        """Test create_certificate_handler_with_ca function."""
        cert_file = tmp_path / "test.pem"
        cert_file.write_text(
            "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----"
        )

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = MagicMock()
            mock_ssl.return_value = mock_context

            handler = create_certificate_handler_with_ca(cert_file)

        assert isinstance(handler, CertificateHandler)
        assert len(handler.custom_certificates) == 1
        assert handler.custom_certificates[0] == cert_file

    def test_create_handler_with_ca_file_not_found(self):
        """Test create_certificate_handler_with_ca with non-existent file."""
        with pytest.raises(FileNotFoundError):
            create_certificate_handler_with_ca("/non/existent/path.pem")
