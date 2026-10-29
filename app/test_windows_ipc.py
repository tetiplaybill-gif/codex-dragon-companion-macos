"""Offline Windows IPC profile boundaries; no native API, pipe or user data."""
import builtins
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import codex_connection
import codex_live_status as live


class WindowsPipeProfileTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.gettempdir()) / 'bailong-ipc-test-home'
        self.default = (self.home / '.codex').resolve()
        self.custom = (self.home / 'other-profile').resolve()

    def test_custom_env_and_saved_homes_never_use_default_pipe(self):
        variants = [
            ({'BAILONG_CODEX_HOME': str(self.custom), 'CODEX_HOME': ''}, {}),
            ({'BAILONG_CODEX_HOME': '', 'CODEX_HOME': str(self.custom)}, {}),
            ({'BAILONG_CODEX_HOME': '', 'CODEX_HOME': ''}, {'home': str(self.custom)}),
        ]
        # Test real profile selection while replacing all possible user sources.
        for env, saved in variants:
            with self.subTest(env=env, saved=saved), patch.dict(os.environ, env), \
                    patch.object(Path, 'home', return_value=self.home), \
                    patch.object(codex_connection, 'saved_paths', return_value=saved), \
                    patch.object(codex_connection, 'user_environment', return_value=''):
                self.assertFalse(live.windows_default_pipe_allowed())

    def test_default_and_equivalent_explicit_default_homes_are_allowed(self):
        for key in (None, 'BAILONG_CODEX_HOME', 'CODEX_HOME'):
            env = {'BAILONG_CODEX_HOME': '', 'CODEX_HOME': ''}
            if key: env[key] = str(self.default / '..' / '.codex')
            with self.subTest(key=key), patch.dict(os.environ, env), \
                    patch.object(Path, 'home', return_value=self.home), \
                    patch.object(codex_connection, 'saved_paths', return_value={}), \
                    patch.object(codex_connection, 'user_environment', return_value=''):
                self.assertTrue(live.windows_default_pipe_allowed())

    def test_bailong_override_priority_does_not_attach_the_other_profile(self):
        for bailong, codex, allowed in ((self.custom, self.default, False),
                                        (self.default, self.custom, True)):
            with self.subTest(allowed=allowed), patch.dict(os.environ,
                    {'BAILONG_CODEX_HOME': str(bailong), 'CODEX_HOME': str(codex)}), \
                    patch.object(Path, 'home', return_value=self.home), \
                    patch.object(codex_connection, 'saved_paths', return_value={}):
                self.assertEqual(live.windows_default_pipe_allowed(), allowed)

    def test_unreadable_or_invalid_home_fails_closed(self):
        for error in (OSError('unavailable'), RuntimeError('resolve failure'), ValueError('invalid')):
            with self.subTest(error=error), \
                    patch.object(codex_connection, 'data_home', side_effect=error):
                self.assertFalse(live.windows_default_pipe_allowed())

    def test_custom_profile_returns_before_native_import_and_keeps_log_stop_unset(self):
        stop = threading.Event()
        reader = live.LiveStatusReader(stop, Mock())
        original_import = builtins.__import__
        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'msvcrt' or (name == 'ctypes' and 'wintypes' in fromlist):
                raise AssertionError('native Windows API imported before isolation guard')
            return original_import(name, globals, locals, fromlist, level)
        with patch.object(live, 'MACOS', False), patch.object(live.os, 'name', 'nt'), \
                patch.object(codex_connection, 'data_home', return_value=self.custom), \
                patch.object(Path, 'home', return_value=self.home), \
                patch('builtins.__import__', side_effect=guarded_import), \
                patch('builtins.open', side_effect=AssertionError('no pipe or credential reads')) as opened:
            reader.run()
        opened.assert_not_called()
        self.assertEqual(reader.health_snapshot(), {'state': 'degraded', 'code': 'ipc_disconnected'})
        self.assertFalse(reader.connected)
        self.assertFalse(stop.is_set())

    def test_macos_dispatch_is_unchanged_and_does_not_consult_windows_guard(self):
        reader = live.LiveStatusReader(threading.Event(), Mock())
        with patch.object(live, 'MACOS', True), patch.object(reader, '_run_unix') as unix, \
                patch.object(live, 'windows_default_pipe_allowed', side_effect=AssertionError('Windows guard on Mac')):
            reader.run()
        unix.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
