"""
Certificate handler for managing custom CA certificates with certifi.

This module provides functionality to append custom CA certificates to the
certifi certificate bundle, which is useful for handling SSL connections
to servers with custom or additional certificates.
"""

import os
import certifi
import ssl
import tempfile
from pathlib import Path
from typing import List, Optional, Union
from loguru import logger

# Combined bundles are written here and reused across runs, so repeated
# invocations do not litter the temp directory with one bundle per process.
DEFAULT_BUNDLE_CACHE_PATH = Path(tempfile.gettempdir()) / "pylindol_ca_bundle.pem"


class CertificateHandler:
    """Handle custom CA certificates by appending them to certifi's bundle.

    This class provides methods to:
    - Append custom CA certificates to the certifi bundle
    - Verify certificate paths and contents
    - Get the combined certificate bundle path (built once and cached)
    """

    def __init__(self, bundle_cache_path: Optional[Union[str, Path]] = None):
        """Initialize the CertificateHandler.

        Args:
            bundle_cache_path: Where to cache the combined bundle. Defaults to a
                fixed path in the system temp directory so the bundle is reused
                across runs. Mainly an injection point for tests.
        """
        self.certifi_bundle_path = certifi.where()
        self.custom_certificates: List[Path] = []
        self.bundle_cache_path = Path(bundle_cache_path or DEFAULT_BUNDLE_CACHE_PATH)
        self._combined_bundle_path: Optional[Path] = None

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
        self._combined_bundle_path = None  # invalidate the cached bundle
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

        The bundle is written atomically (temp file plus rename) so a concurrent
        reader never sees a half-written file at the shared cache path.

        Args:
            output_path: Optional path to save the combined bundle. Defaults to
                `bundle_cache_path`.

        Returns:
            Path: Path to the combined certificate bundle

        Raises:
            OSError: If there's an error reading or writing certificate files
        """
        if not self.custom_certificates:
            logger.info("No custom certificates to append, returning certifi bundle")
            return Path(self.certifi_bundle_path)

        output_path = (
            Path(output_path) if output_path is not None else self.bundle_cache_path
        )

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

            self._write_atomic(output_path, combined_content)
            logger.info(f"Created combined certificate bundle: {output_path}")
            return output_path

        except (OSError, UnicodeDecodeError) as e:
            logger.error(f"Error creating combined certificate bundle: {e}")
            raise

    @staticmethod
    def _write_atomic(output_path: Path, content: str) -> None:
        """Write `content` to `output_path` atomically via a temp file and rename."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(suffix=".pem", dir=output_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_name, output_path)
        except OSError:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def _bundle_is_fresh(self, bundle_path: Path) -> bool:
        """Whether a cached bundle exists and is newer than all of its sources.

        Args:
            bundle_path: Path to the cached combined bundle.

        Returns:
            True if the bundle is at least as new as the certifi bundle and every
            custom certificate, meaning it can be reused without rebuilding.
        """
        if not bundle_path.exists():
            return False
        bundle_mtime = bundle_path.stat().st_mtime
        sources = [Path(self.certifi_bundle_path), *self.custom_certificates]
        return all(bundle_mtime >= source.stat().st_mtime for source in sources)

    def get_bundle_path(self) -> Path:
        """Get the certificate bundle path.

        Reuses the cached combined bundle when it is still fresh, rebuilding it
        only when certifi or a custom certificate has changed. Returns the plain
        certifi bundle when no custom certificates have been added.

        Returns:
            Path: Path to the certificate bundle.
        """
        if not self.custom_certificates:
            return Path(self.certifi_bundle_path)
        if self._combined_bundle_path is None:
            self._combined_bundle_path = (
                self.bundle_cache_path
                if self._bundle_is_fresh(self.bundle_cache_path)
                else self.create_combined_bundle()
            )
        return self._combined_bundle_path
