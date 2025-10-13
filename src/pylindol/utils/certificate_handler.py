"""
Certificate handler for managing custom CA certificates with certifi.

This module provides functionality to append custom CA certificates to the
certifi certificate bundle, which is useful for handling SSL connections
to servers with custom or additional certificates.
"""

import certifi
import ssl
import tempfile
from pathlib import Path
from typing import List, Optional, Union
from loguru import logger


class CertificateHandler:
    """
    A class to handle custom CA certificates by appending them to certifi's bundle.

    This class provides methods to:
    - Append custom CA certificates to the certifi bundle
    - Verify certificate paths and contents
    - Get the combined certificate bundle path
    - Validate SSL contexts
    """

    def __init__(self):
        """Initialize the CertificateHandler."""
        self.certifi_bundle_path = certifi.where()
        self.custom_certificates: List[Path] = []

    def add_certificate(self, certificate_path: Union[str, Path]) -> bool:
        """
        Add a custom CA certificate to the handler.

        Args:
            certificate_path: Path to the CA certificate file

        Returns:
            bool: True if certificate was successfully added, False otherwise

        Raises:
            FileNotFoundError: If the certificate file doesn't exist
            ValueError: If the certificate file is invalid
        """
        cert_path = Path(certificate_path)

        if not cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")

        if not cert_path.is_file():
            raise ValueError(f"Path is not a file: {cert_path}")

        # Validate the certificate content
        if not self._validate_certificate_content(cert_path):
            raise ValueError(f"Invalid certificate format: {cert_path}")

        self.custom_certificates.append(cert_path)
        logger.info(f"Added certificate: {cert_path}")
        return True

    def _validate_certificate_content(self, cert_path: Path) -> bool:
        """
        Validate that the certificate file contains valid PEM format.

        Args:
            cert_path: Path to the certificate file

        Returns:
            bool: True if certificate is valid, False otherwise
        """
        try:
            with open(cert_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Basic PEM format validation
            if "-----BEGIN CERTIFICATE-----" not in content:
                return False

            if "-----END CERTIFICATE-----" not in content:
                return False

            # Try to parse the certificate
            ssl.create_default_context().load_verify_locations(str(cert_path))
            return True

        except (ssl.SSLError, UnicodeDecodeError, OSError) as e:
            logger.warning(f"Certificate validation failed for {cert_path}: {e}")
            return False

    def create_combined_bundle(
        self, output_path: Optional[Union[str, Path]] = None
    ) -> Path:
        """
        Create a combined certificate bundle by appending custom certificates.

        Args:
            output_path: Optional path to save the combined bundle.
                        If None, creates a temporary file.

        Returns:
            Path: Path to the combined certificate bundle

        Raises:
            OSError: If there's an error reading or writing certificate files
        """
        if not self.custom_certificates:
            logger.info("No custom certificates to append, returning certifi bundle")
            return Path(self.certifi_bundle_path)

        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".pem", delete=False
            )
            output_path = Path(temp_file.name)
            temp_file.close()
        else:
            output_path = Path(output_path)

        try:
            # Read the original certifi bundle
            with open(self.certifi_bundle_path, "r", encoding="utf-8") as f:
                combined_content = f.read()

            # Ensure there's a newline at the end
            if not combined_content.endswith("\n"):
                combined_content += "\n"

            # Append custom certificates
            for cert_path in self.custom_certificates:
                logger.info(f"Appending certificate: {cert_path}")
                with open(cert_path, "r", encoding="utf-8") as f:
                    cert_content = f.read()

                # Ensure proper formatting
                if not cert_content.startswith("\n"):
                    combined_content += "\n"
                combined_content += cert_content
                if not cert_content.endswith("\n"):
                    combined_content += "\n"

            # Write the combined bundle
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(combined_content)

            logger.info(f"Created combined certificate bundle: {output_path}")
            return output_path

        except (OSError, UnicodeDecodeError) as e:
            logger.error(f"Error creating combined certificate bundle: {e}")
            raise

    def get_bundle_path(self, use_combined: bool = True) -> Path:
        """
        Get the certificate bundle path.

        Args:
            use_combined: If True and custom certificates exist, return combined bundle.
                         If False, return only certifi bundle.

        Returns:
            Path: Path to the certificate bundle
        """
        if use_combined and self.custom_certificates:
            return self.create_combined_bundle()
        return Path(self.certifi_bundle_path)

    def create_ssl_context(self, use_combined: bool = True) -> ssl.SSLContext:
        """
        Create an SSL context using the certificate bundle.

        Args:
            use_combined: If True and custom certificates exist, use combined bundle.
                         If False, use only certifi bundle.

        Returns:
            ssl.SSLContext: Configured SSL context
        """
        bundle_path = self.get_bundle_path(use_combined)

        context = ssl.create_default_context()
        context.load_verify_locations(str(bundle_path))

        logger.info(f"Created SSL context with bundle: {bundle_path}")
        return context

    def verify_connection(
        self, hostname: str, port: int = 443, use_combined: bool = True
    ) -> bool:
        """
        Verify SSL connection to a hostname using the certificate bundle.

        Args:
            hostname: Target hostname
            port: Target port (default: 443)
            use_combined: If True and custom certificates exist, use combined bundle.
                         If False, use only certifi bundle.

        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            context = self.create_ssl_context(use_combined)

            with ssl.create_connection((hostname, port)) as sock:
                with context.wrap_socket(sock, server_hostname=hostname):
                    logger.info(f"SSL connection verified to {hostname}:{port}")
                    return True

        except (ssl.SSLError, OSError) as e:
            logger.error(f"SSL connection failed to {hostname}:{port}: {e}")
            return False

    def clear_custom_certificates(self) -> None:
        """Clear all custom certificates from the handler."""
        self.custom_certificates.clear()
        logger.info("Cleared all custom certificates")

    def list_certificates(self) -> List[Path]:
        """
        Get a list of currently added custom certificates.

        Returns:
            List[Path]: List of custom certificate paths
        """
        return self.custom_certificates.copy()

    def __len__(self) -> int:
        """Return the number of custom certificates."""
        return len(self.custom_certificates)

    def __repr__(self) -> str:
        """Return a string representation of the CertificateHandler."""
        return f"CertificateHandler(certificates={len(self.custom_certificates)})"


# Convenience function for common usage
def create_certificate_handler_with_ca(
    ca_certificate_path: Union[str, Path],
) -> CertificateHandler:
    """
    Create a CertificateHandler instance with a specific CA certificate.

    Args:
        ca_certificate_path: Path to the CA certificate file

    Returns:
        CertificateHandler: Configured handler with the CA certificate

    Raises:
        FileNotFoundError: If the certificate file doesn't exist
        ValueError: If the certificate file is invalid
    """
    handler = CertificateHandler()
    handler.add_certificate(ca_certificate_path)
    return handler


if __name__ == "__main__":
    from pylindol.config.paths import CA_CERTIFICATE_PATH

    handler = create_certificate_handler_with_ca(CA_CERTIFICATE_PATH)
    print(handler.get_bundle_path())
