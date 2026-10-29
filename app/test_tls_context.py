"""Portable macOS trust store regressions; no network or real app data."""
import ssl
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch

import app_updates
import tls_context


class VerifiedContextTests(unittest.TestCase):
    @unittest.skipUnless(tls_context.MACOS_CA_FILE.is_file(), 'macOS system CA bundle not present')
    def test_macos_adds_roots_without_replacing_default_trust(self):
        context = ssl.create_default_context()
        original_roots = set(context.get_ca_certs(binary_form=True))
        with patch.object(tls_context.sys, 'platform', 'darwin'), \
                patch.object(tls_context.ssl, 'create_default_context', return_value=context):
            result = tls_context.https_context()
        self.assertIs(result, context)
        self.assertEqual(result.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(result.check_hostname)
        self.assertGreater(result.cert_store_stats()['x509_ca'], 0)
        self.assertTrue(original_roots.issubset(set(result.get_ca_certs(binary_form=True))))

    def test_other_platforms_keep_the_default_context(self):
        context = Mock()
        with patch.object(tls_context.sys, 'platform', 'win32'), \
                patch.object(tls_context.ssl, 'create_default_context', return_value=context):
            self.assertIs(tls_context.https_context(), context)
        context.load_verify_locations.assert_not_called()

    def test_missing_system_bundle_preserves_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            context = Mock()
            with patch.object(tls_context.sys, 'platform', 'darwin'), \
                    patch.object(tls_context, 'MACOS_CA_FILE', Path(folder) / 'missing.pem'), \
                    patch.object(tls_context.ssl, 'create_default_context', return_value=context):
                self.assertIs(tls_context.https_context(), context)
            context.load_verify_locations.assert_not_called()

    def test_invalid_system_bundle_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            invalid = Path(folder) / 'invalid.pem'
            invalid.write_text('not a certificate')
            with patch.object(tls_context.sys, 'platform', 'darwin'), \
                    patch.object(tls_context, 'MACOS_CA_FILE', invalid):
                with self.assertRaises(ssl.SSLError):
                    tls_context.https_context()


class DownloadTrustTests(unittest.TestCase):
    def test_github_opener_keeps_verified_https_and_redirect_restrictions(self):
        context = tls_context.https_context()
        opener = Mock()
        with patch.object(app_updates, 'https_context', return_value=context), \
                patch.object(app_updates.urllib.request, 'build_opener', return_value=opener) as build:
            result = app_updates.open_url('https://github.com/Wunsch2048/codex-bailong-desktop-pet')
        self.assertIs(result, opener.open.return_value)
        handlers = build.call_args.args
        self.assertTrue(any(isinstance(h, app_updates.GitHubRedirect) for h in handlers))
        https = next(h for h in handlers if isinstance(h, urllib.request.HTTPSHandler))
        self.assertIs(https._context, context)
        self.assertEqual(https._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(https._context.check_hostname)

    def test_certificate_failure_is_not_retried_with_weaker_verification(self):
        error = urllib.error.URLError(ssl.SSLCertVerificationError(1, 'certificate rejected'))
        opener = Mock()
        opener.open.side_effect = error
        with patch.object(app_updates.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaises(urllib.error.URLError) as caught:
                app_updates.open_url('https://github.com/Wunsch2048/codex-bailong-desktop-pet')
        self.assertIs(caught.exception, error)
        opener.open.assert_called_once()

    def test_disallowed_url_is_rejected_before_building_a_connection(self):
        with patch.object(app_updates.urllib.request, 'build_opener') as build:
            with self.assertRaises(app_updates.UpdateError):
                app_updates.open_url('http://github.com/Wunsch2048/codex-bailong-desktop-pet')
        build.assert_not_called()


if __name__ == '__main__':
    unittest.main()
