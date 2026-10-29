"""Platform trust regressions; no network, credentials or real app data."""
import io
import ssl
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch

import app_updates
import tls_context
import public_announcements


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
        context = ssl.create_default_context()
        roots = Mock()
        roots.is_file.side_effect = AssertionError('Windows must not inspect macOS roots')
        with patch.object(tls_context.sys, 'platform', 'win32'), \
                patch.object(tls_context, 'MACOS_CA_FILE', roots), \
                patch.object(tls_context.ssl, 'create_default_context', return_value=context):
            self.assertIs(tls_context.https_context(), context)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        roots.is_file.assert_not_called()

    def test_default_trust_initialization_failure_never_uses_unverified_context(self):
        with patch.object(tls_context.sys, 'platform', 'win32'), \
                patch.object(tls_context.ssl, 'create_default_context', side_effect=ssl.SSLError('trust error')), \
                patch.object(tls_context.ssl, '_create_unverified_context') as unverified:
            with self.assertRaises(ssl.SSLError):
                tls_context.https_context()
        unverified.assert_not_called()

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


class PublicFeedTrustTests(unittest.TestCase):
    def test_both_public_hosts_use_verified_tls_without_auth_handlers(self):
        context = ssl.create_default_context()
        for url, host in ((public_announcements.STATUS_URL, 'codex-resets.com'),
                          (public_announcements.OfficialProductProvider.url, 'learn.chatgpt.com')):
            response = io.BytesIO(b'{}')
            response.geturl = lambda: url
            response.headers = {}
            opener = Mock()
            opener.open.return_value = response
            with self.subTest(host=host), patch.object(tls_context.sys, 'platform', 'win32'), \
                    patch.object(tls_context, 'https_context', return_value=context), \
                    patch.object(public_announcements.urllib.request, 'build_opener', return_value=opener) as build:
                self.assertEqual(public_announcements.fetch_bytes(url, host=host), (b'{}', None))
            handlers = build.call_args.args
            self.assertEqual(len(handlers), 2)
            self.assertIsInstance(handlers[0], public_announcements._SameHostRedirect)
            self.assertEqual(handlers[0].host, host)
            self.assertIsInstance(handlers[1], urllib.request.HTTPSHandler)
            self.assertIs(handlers[1]._context, context)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            request = opener.open.call_args.args[0]
            self.assertFalse(request.has_header('Cookie'))
            self.assertFalse(request.has_header('Authorization'))

    def test_public_certificate_failure_is_not_retried_or_downgraded(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.URLError(ssl.SSLCertVerificationError(1, 'rejected'))
        with patch.object(public_announcements.urllib.request, 'build_opener', return_value=opener), \
                patch.object(tls_context.ssl, '_create_unverified_context') as unverified:
            with self.assertRaises(public_announcements.ProviderError) as caught:
                public_announcements.fetch_bytes(public_announcements.STATUS_URL, host='codex-resets.com')
        self.assertEqual(caught.exception.code, 'network')
        opener.open.assert_called_once()
        unverified.assert_not_called()


if __name__ == '__main__':
    unittest.main()
