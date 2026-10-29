"""Windows source-startup regressions; only temporary files and mocked processes.

These run on macOS/Linux too. No real Startup entry, mutex, process scan,
process termination, Codex profile, Qt application, or network is used.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import codex_startup as cs
import desktop_services as services
import platform_paths as paths


class WindowsStartupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / '用户 Home'
        self.source = self.root / '源码 & checkout'
        self.source.mkdir()
        self.start_patch(patch.dict(os.environ, {
            'LOCALAPPDATA': str(self.root / 'Local Data'),
            'APPDATA': str(self.root / 'Roaming Data'),
        }, clear=True))
        self.start_patch(patch.object(paths, 'WINDOWS', True))
        self.start_patch(patch.object(paths, 'MACOS', False))
        self.start_patch(patch.object(cs, 'MACOS', False))
        self.start_patch(patch.object(Path, 'home', return_value=self.home))
        self.start_patch(patch.object(paths, 'app_root', return_value=self.source))
        self.start_patch(patch.object(sys, 'frozen', False, create=True))

    def start_patch(self, item):
        result = item.start()
        self.addCleanup(item.stop)
        return result

    def interpreter(self, windowless=False):
        python = self.root / 'Python 环境' / 'python.exe'
        python.parent.mkdir(exist_ok=True)
        python.write_text('not executable test data', encoding='utf-8')
        if windowless:
            python.with_name('pythonw.exe').write_text('test data', encoding='utf-8')
        self.start_patch(patch.object(sys, 'executable', str(python)))
        return python

    def fake_kernel(self, already_running=False):
        kernel = Mock()
        kernel.CreateMutexW.return_value = 123
        self.start_patch(patch.object(cs.ctypes, 'WinDLL', return_value=kernel, create=True))
        self.start_patch(patch.object(cs.ctypes, 'get_last_error',
                                     return_value=183 if already_running else 0, create=True))
        return kernel

    def test_missing_pythonw_uses_the_existing_interpreter_for_source_and_login_commands(self):
        python = self.interpreter()
        self.assertFalse(python.with_name('pythonw.exe').exists())
        self.assertEqual(paths.background_python(), python)
        self.assertEqual(cs.app_command()[0], str(python))
        self.assertEqual(services.command(), subprocess.list2cmdline(
            [str(python), str(Path(services.__file__).with_name('enhanced.py'))]))

    def test_pythonw_is_preferred_when_it_is_a_real_file(self):
        python = self.interpreter(windowless=True)
        self.assertEqual(paths.background_python(), python.with_name('pythonw.exe'))
        self.assertEqual(cs.app_command()[0], str(python.with_name('pythonw.exe')))

    def test_a_directory_named_pythonw_is_not_an_interpreter(self):
        python = self.interpreter()
        python.with_name('pythonw.exe').mkdir()
        self.assertEqual(paths.background_python(), python)

    def test_frozen_gui_command_does_not_use_a_python_interpreter(self):
        self.interpreter(windowless=True)
        executable = str(self.source / 'BailongEnhanced.exe')
        with patch.object(sys, 'frozen', True), patch.object(sys, 'executable', executable):
            self.assertEqual(cs.app_command(), [executable])
            self.assertEqual(services.command(), subprocess.list2cmdline([executable]))

    def test_existing_always_quoted_login_entry_remains_detectable(self):
        self.interpreter(windowless=True)
        entry=services.startup_paths()[0]
        entry.parent.mkdir(parents=True)
        # Quote-less paths expose the compatibility difference from list2cmdline.
        args=['C:\\Python\\pythonw.exe','C:\\checkout\\app\\enhanced.py']
        legacy=' '.join('"'+arg+'"' for arg in args).replace('"','""')
        entry.write_text('shell.Run "'+legacy+'", 0, False\n',encoding='utf-16')
        with patch.object(services,'_command_args',return_value=args),patch.object(sys,'platform','win32'):
            self.assertTrue(services.autostart_enabled())

    def test_appdata_environment_and_conventional_fallbacks_are_consistent(self):
        self.assertEqual(paths.local_appdata(), self.root / 'Local Data')
        self.assertTrue(cs.startup_path().is_relative_to(self.root / 'Roaming Data'))
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(paths.local_appdata(), self.home / 'AppData/Local')
            startup = self.home / 'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup'
            self.assertEqual(paths.startup_folder(), startup)
            self.assertEqual(cs.startup_path(), startup / 'BailongCodexSync.vbs')
            self.assertEqual(services.startup_paths()[0], startup / 'BailongEnhanced.vbs')
        self.assertFalse(self.home.exists())  # Resolving paths alone never registers anything.

    def test_new_source_config_stays_disabled_without_creating_a_login_entry(self):
        with patch.object(cs, 'spawn') as spawn, patch.object(cs, 'register') as register:
            self.assertFalse(cs.enabled())
            self.assertIsNone(cs.ensure_watcher())
        spawn.assert_not_called()
        register.assert_not_called()
        self.assertFalse(paths.startup_folder().exists())

    def test_enabling_registers_only_a_watcher_with_quoted_source_paths(self):
        python = self.interpreter()
        command = [str(python), str(self.source / 'app/enhanced.py')]
        with patch.object(cs, 'app_command', return_value=command), patch.object(cs, 'spawn') as spawn:
            cs.configure(True)
        script = cs.startup_path().read_text(encoding='utf-16')
        line = next(line for line in script.splitlines() if line.startswith('s.Run '))
        literal = re.fullmatch(r's.Run "((?:""|[^"])*)",0,False', line).group(1)
        self.assertEqual(literal.replace('""', '"'), subprocess.list2cmdline(command + ['--watch-codex']))
        self.assertIn('s.CurrentDirectory = "' + str(self.source) + '"', script)
        self.assertEqual([p.name for p in paths.startup_folder().iterdir()], ['BailongCodexSync.vbs'])
        spawn.assert_called_once_with(command + ['--watch-codex'])
        self.assertNotIn('--from-codex', script)
        self.assertFalse(services.startup_paths()[0].exists())  # No unconditional GUI login entry.

    def test_source_login_entry_refreshes_to_the_current_checkout(self):
        self.interpreter()
        cs.atomic(cs.preference_path(), {'enabled': True})
        cs.startup_path().parent.mkdir(parents=True)
        cs.startup_path().write_text('old checkout', encoding='utf-16')
        command = ['new python.exe', str(self.source / 'app/enhanced.py')]
        with patch.object(cs, 'app_command', return_value=command), patch.object(cs, 'spawn'):
            cs.ensure_watcher()
        self.assertIn('new python.exe', cs.startup_path().read_text(encoding='utf-16'))

    def test_failed_spawn_restores_the_previous_preference_and_startup_entry(self):
        self.interpreter()
        cs.atomic(cs.preference_path(), {'enabled': False, 'retained': 'test'})
        cs.startup_path().parent.mkdir(parents=True)
        cs.startup_path().write_bytes(b'old test entry')
        before = (cs.preference_path().read_bytes(), cs.startup_path().read_bytes())
        with patch.object(cs, 'spawn', side_effect=OSError('test denial')):
            with self.assertRaises(OSError):
                cs.configure(True)
        self.assertEqual((cs.preference_path().read_bytes(), cs.startup_path().read_bytes()), before)

    def test_control_characters_cannot_inject_a_vbs_line(self):
        cs.atomic(cs.preference_path(), {'enabled': True})
        with patch.object(cs, 'app_command', return_value=['python.exe', 'bad\nsource.py']):
            with self.assertRaises(OSError):
                cs.register()
        self.assertFalse(cs.startup_path().exists())

    def test_python_console_fallback_is_hidden_and_disconnected_from_parent_stdio(self):
        with patch.object(cs.subprocess, 'Popen') as popen:
            cs.spawn(['python.exe', 'source.py', '--watch-codex'])
        self.assertEqual(popen.call_args.kwargs['creationflags'], 0x08000000)
        for name in ('stdin', 'stdout', 'stderr'):
            self.assertEqual(popen.call_args.kwargs[name], subprocess.DEVNULL)
        self.assertNotIn('shell', popen.call_args.kwargs)

    def test_existing_watcher_mutex_closes_its_handle_and_never_launches(self):
        kernel = self.fake_kernel(already_running=True)
        with patch.object(cs, 'spawn') as spawn, patch.object(cs, 'desktop_sessions') as sessions:
            self.assertEqual(cs.main(), 0)
        kernel.CreateMutexW.assert_called_once_with(None, False, 'Local\\BailongCodexSyncV1')
        kernel.CloseHandle.assert_called_once_with(123)
        spawn.assert_not_called()
        sessions.assert_not_called()

    def test_watcher_waits_for_codex_and_launches_one_gui_for_the_same_session(self):
        kernel = self.fake_kernel()
        command = ['python.exe', 'enhanced.py']
        with patch.object(cs, 'enabled', side_effect=[True, True, True, True, False]), \
                patch.object(cs, 'desktop_sessions', side_effect=[set(), None, {(20, 1.)}, {(20, 1.)}]), \
                patch.object(cs, 'current_command', return_value=command), \
                patch.object(cs.time, 'sleep'), patch.object(cs, 'spawn') as spawn:
            self.assertEqual(cs.main(), 0)
        spawn.assert_called_once_with(command + ['--from-codex'])
        kernel.CloseHandle.assert_called_once_with(123)

    def test_unknown_presence_interrupts_consecutive_absence_and_never_reopens_a_closed_pet(self):
        gate = cs.LaunchGate()
        session = {(20, 1.)}
        self.assertTrue(gate.observe(session))
        for value in (set(), None, set(), session):
            self.assertFalse(gate.observe(value))
        self.assertFalse(gate.observe(set()))
        self.assertFalse(gate.observe(set()))
        self.assertTrue(gate.observe({(21, 2.)}))

    def test_exit_requires_observed_codex_and_three_consecutive_confirmed_absences(self):
        gate = cs.ExitGate()
        for _ in range(4):
            self.assertFalse(gate.observe(set()))
        self.assertFalse(gate.observe({(20, 1.)}))
        for value in (set(), set(), None, set(), set()):
            self.assertFalse(gate.observe(value))
        self.assertTrue(gate.observe(set()))

    def test_macos_still_uses_its_current_interpreter_and_library_support_directory(self):
        python = self.interpreter(windowless=True)
        with patch.object(paths, 'WINDOWS', False), patch.object(paths, 'MACOS', True), \
                patch.dict(os.environ, {}, clear=True):
            self.assertEqual(paths.background_python(), python)
            self.assertEqual(paths.local_appdata(), self.home / 'Library/Application Support')


if __name__ == '__main__':
    unittest.main()
