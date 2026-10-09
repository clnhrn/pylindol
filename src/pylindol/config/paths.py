from pathlib import Path

# Intermediate certificate that some PHIVOLCS servers omit from their TLS chain.
# It expires on 2028-11-21; tests/test_http.py starts failing ahead of that date
# as a reminder to check whether it is still needed or has a successor.
CA_CERTIFICATE_PATH = (
    Path(__file__).parent.parent
    / "ca_certificates"
    / "GlobalSign RSA OV SSL CA 2018.pem"
)
