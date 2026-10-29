"""Test support: keep chat credential tests off the real macOS login Keychain.

On macOS the app stores keys in the Keychain, which is shared by every
process of the user. Tests instead use the Windows file store with a
reversible stand-in for DPAPI, so they exercise the same code paths and
never read, write or delete real Keychain items. Elsewhere this is a no-op
and Windows keeps testing real DPAPI.
"""
import base64
import sys
from unittest.mock import patch

import desktop_services

FileSecretStore=desktop_services.FileSecretStore


def _fake_protect(value,decrypt=False):
    return base64.b64decode(value,validate=True).decode('utf-8') if decrypt else base64.b64encode(value.encode('utf-8')).decode('ascii')


def isolate_secrets(case):
    if sys.platform!='darwin':return
    for target,value in (('desktop_services.SecretStore',FileSecretStore),('chat_config.SecretStore',FileSecretStore),
                         ('desktop_services.protect',_fake_protect)):
        patcher=patch(target,value);patcher.start();case.addCleanup(patcher.stop)
