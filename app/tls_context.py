"""Verified HTTPS using native defaults, plus roots for portable macOS builds."""
from pathlib import Path
import ssl
import sys

MACOS_CA_FILE = Path('/etc/ssl/cert.pem')


def https_context():
    """Keep Python's default trust and add Apple's shipped public CA bundle.

    Frozen Homebrew Python retains its build machine's OpenSSL CA path. That
    path need not exist on another Mac, leaving a valid but empty trust store.
    Load macOS roots in addition to defaults; malformed roots still fail closed.
    This does not change system trust, verification modes, or hostname checks.
    On Windows, create_default_context loads Python's default Windows trust
    stores; the macOS PEM is neither inspected nor loaded.
    """
    context = ssl.create_default_context()
    if sys.platform == 'darwin' and MACOS_CA_FILE.is_file():
        context.load_verify_locations(cafile=str(MACOS_CA_FILE))
    return context
