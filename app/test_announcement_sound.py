"""Platform sound routing only: every audio backend is mocked, never played."""
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import announcement_sound as sound


class AnnouncementSoundTests(unittest.TestCase):
    def windows_backend(self):
        return SimpleNamespace(PlaySound=Mock(), SND_ALIAS=0x10000,
                               SND_ASYNC=1, SND_NODEFAULT=2)

    def test_windows_uses_one_async_system_alias_without_mac_or_qt(self):
        backend = self.windows_backend()
        with patch.object(sound.sys, 'platform', 'win32'), \
                patch.dict(sys.modules, {'winsound': backend, 'PySide6.QtWidgets': None}), \
                patch.object(sound, 'Path', side_effect=AssertionError('no macOS file access')), \
                patch.object(sound.subprocess, 'Popen') as process:
            self.assertTrue(sound.play_reset_sound())
        backend.PlaySound.assert_called_once_with('SystemAsterisk', 0x10003)
        process.assert_not_called()

    def test_windows_unavailable_sound_is_silent_and_does_not_retry(self):
        for error in (RuntimeError('sound unavailable'), OSError('device unavailable')):
            backend = self.windows_backend()
            backend.PlaySound.side_effect = error
            with self.subTest(error=error), patch.object(sound.sys, 'platform', 'win32'), \
                    patch.dict(sys.modules, {'winsound': backend, 'PySide6.QtWidgets': None}), \
                    patch.object(sound.subprocess, 'Popen') as process:
                self.assertFalse(sound.play_reset_sound())
            backend.PlaySound.assert_called_once()
            process.assert_not_called()

    def test_missing_windows_backend_does_not_try_qt_or_a_subprocess(self):
        with patch.object(sound.sys, 'platform', 'win32'), \
                patch.dict(sys.modules, {'winsound': None, 'PySide6.QtWidgets': None}), \
                patch.object(sound.subprocess, 'Popen') as process:
            self.assertFalse(sound.play_reset_sound())
        process.assert_not_called()

    def test_macos_keeps_its_existing_local_sound_command(self):
        with patch.object(sound.sys, 'platform', 'darwin'), \
                patch.object(sound.Path, 'is_file', return_value=True), \
                patch.object(sound.subprocess, 'Popen') as process, \
                patch.dict(sys.modules, {'winsound': None}):
            self.assertTrue(sound.play_reset_sound())
        process.assert_called_once_with(['/usr/bin/afplay', '/System/Library/Sounds/Glass.aiff'],
            stdin=sound.subprocess.DEVNULL, stdout=sound.subprocess.DEVNULL,
            stderr=sound.subprocess.DEVNULL, close_fds=True)

    def test_macos_missing_sound_or_failed_process_does_not_fallback(self):
        with patch.object(sound.sys, 'platform', 'darwin'), \
                patch.object(sound.Path, 'is_file', return_value=False), \
                patch.object(sound.subprocess, 'Popen') as process:
            self.assertFalse(sound.play_reset_sound())
            process.assert_not_called()
        with patch.object(sound.sys, 'platform', 'darwin'), \
                patch.object(sound.Path, 'is_file', return_value=True), \
                patch.object(sound.subprocess, 'Popen', side_effect=OSError('unavailable')) as process:
            self.assertFalse(sound.play_reset_sound())
        process.assert_called_once()

    def test_other_platforms_require_a_qt_app_and_contain_backend_errors(self):
        app = Mock()
        with patch.object(sound.sys, 'platform', 'linux'), \
                patch.dict(sys.modules, {'PySide6.QtWidgets': SimpleNamespace(QApplication=app)}):
            app.instance.return_value = None
            self.assertFalse(sound.play_reset_sound())
            app.beep.assert_not_called()
            app.instance.return_value = object()
            self.assertTrue(sound.play_reset_sound())
            app.beep.assert_called_once()
            app.beep.side_effect = RuntimeError('Qt closing')
            self.assertFalse(sound.play_reset_sound())


if __name__ == '__main__':
    unittest.main()
