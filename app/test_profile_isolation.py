import os
import unittest
from unittest.mock import patch
import platform_paths


class ProfileIsolationTests(unittest.TestCase):
    def test_default_macos_keeps_existing_instance(self):
        with patch.object(platform_paths, 'MACOS', True), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(platform_paths.instance_server_name(), 'bailong-enhanced-local-v1')

    def test_custom_macos_profiles_cannot_contact_normal_or_each_other(self):
        names = []
        for directory in ('/tmp/bailong-profile-a', '/tmp/bailong-profile-b'):
            with patch.object(platform_paths, 'MACOS', True), patch.dict(os.environ, {'LOCALAPPDATA': directory}, clear=True):
                name = platform_paths.instance_server_name()
                self.assertEqual(name, platform_paths.instance_server_name())
                self.assertNotEqual(name, 'bailong-enhanced-local-v1')
                names.append(name)
        self.assertNotEqual(*names)

    def test_equivalent_profile_paths_share_one_instance(self):
        names = []
        for directory in ('/tmp/bailong-profile-a', '/tmp/bailong-profile-a/../bailong-profile-a'):
            with patch.object(platform_paths, 'MACOS', True), patch.dict(os.environ, {'LOCALAPPDATA': directory}, clear=True):
                names.append(platform_paths.instance_server_name())
        self.assertEqual(*names)

    def test_windows_localappdata_keeps_existing_instance(self):
        with patch.object(platform_paths, 'MACOS', False), patch.dict(os.environ, {'LOCALAPPDATA': '/tmp/windows'}, clear=True):
            self.assertEqual(platform_paths.instance_server_name(), 'bailong-enhanced-local-v1')


if __name__ == '__main__':
    unittest.main()
