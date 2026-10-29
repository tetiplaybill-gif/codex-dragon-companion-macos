"""macOS login-start LaunchAgents and Keychain secrets (skipped elsewhere)."""
import os,plistlib,sys,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import codex_startup as cs
import desktop_services as ds
from platform_paths import launch_agent

@unittest.skipUnless(sys.platform=='darwin','macOS LaunchAgent')
class MacStartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,HOME=str(self.root/'home'),LOCALAPPDATA=str(self.root/'local'));self.env.start()
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def args(self,path):
        with open(path,'rb') as f:return plistlib.load(f)
    def test_pet_agent_roundtrip_and_foreign_or_corrupt_entries(self):
        path,label=launch_agent();self.assertEqual(path.parent,self.root/'local/LaunchAgents')
        self.assertFalse(ds.autostart_enabled())
        ds.set_autostart(True);data=self.args(path)
        self.assertEqual(data['Label'],label);self.assertEqual(data['ProgramArguments'],cs.app_command())
        self.assertIs(data['RunAtLoad'],True);self.assertIs(data['KeepAlive'],False);self.assertIs(data['AbandonProcessGroup'],True)
        self.assertEqual(path.stat().st_mode&0o022,0);self.assertTrue(ds.autostart_enabled())
        data['ProgramArguments']=['/elsewhere/BailongEnhanced'];path.write_bytes(plistlib.dumps(data));self.assertFalse(ds.autostart_enabled())
        path.write_text('<plist><dict><key>x');self.assertFalse(ds.autostart_enabled())
        ds.set_autostart(False);self.assertFalse(path.exists());ds.set_autostart(False)
    def test_translocated_bundle_is_refused(self):
        with patch.object(cs,'app_command',return_value=['/private/var/folders/x/AppTranslocation/1/d/BailongEnhanced.app/Contents/MacOS/BailongEnhanced']):
            with self.assertRaises(OSError):ds.set_autostart(True)
        self.assertFalse(launch_agent()[0].exists())
    def test_codex_agent_enable_disable_and_rollback(self):
        with patch.object(cs,'spawn') as launch:
            cs.configure(True);self.assertTrue(cs.enabled())
            self.assertEqual(self.args(cs.startup_path())['ProgramArguments'],cs.app_command()+['--watch-codex'])
            launch.assert_called_once_with(cs.app_command()+['--watch-codex'])
            cs.configure(False);self.assertFalse(cs.startup_path().exists())
        before=cs.preference_path().read_bytes()
        with patch.object(cs,'spawn',side_effect=OSError('denied')),self.assertRaises(OSError):cs.configure(True)
        self.assertEqual(cs.preference_path().read_bytes(),before);self.assertFalse(cs.startup_path().exists())
    def test_spawn_detaches_without_windows_flags(self):
        with patch.object(cs.subprocess,'Popen') as launch:cs.spawn(['pet','--from-codex'])
        self.assertNotIn('creationflags',launch.call_args.kwargs);self.assertTrue(launch.call_args.kwargs['start_new_session'])

@unittest.skipUnless(sys.platform=='darwin' and os.environ.get('BAILONG_KEYCHAIN_TEST')=='1','touches the login Keychain')
class KeychainTests(unittest.TestCase):
    def test_roundtrip_without_file_and_delete(self):
        from mac_keychain import KeychainStore
        with tempfile.TemporaryDirectory() as folder:
            store=KeychainStore(Path(folder)/'credentials.dpapi.json',service='BailongEnhanced-test-'+uuid.uuid4().hex[:8])
            try:
                self.assertEqual(store.get('a'),'');store.put('a','example-local-test-secret');self.assertEqual(store.get('a'),'example-local-test-secret')
                store.put('a','第二个 key "x"');self.assertEqual(store.get('a'),'第二个 key "x"');self.assertFalse(store.path.exists())
            finally:store.put('a','')
            self.assertEqual(store.get('a',),'')
    def test_read_lists_names_and_remove_deletes_items(self):
        from mac_keychain import KeychainStore
        store=KeychainStore(service='BailongEnhanced-test-'+uuid.uuid4().hex[:8])
        try:
            self.assertEqual(store.read(),{})
            store.put('a','example-local-test-secret');store.put('chat:a:1','second-test-secret')
            names=store.read();self.assertEqual(set(names),{'a','chat:a:1'})
            self.assertNotIn('example-local-test-secret',names.values())
            store.remove(['a']);self.assertEqual(set(store.read()),{'chat:a:1'})
        finally:store.remove(['a','chat:a:1'])
        self.assertEqual(store.read(),{})
    def test_desktop_services_exports_keychain_store(self):
        self.assertEqual(ds.SecretStore.__name__,'KeychainStore')

@unittest.skipUnless(sys.platform=='darwin','macOS update policy')
class MacUpdateTests(unittest.TestCase):
    def test_controller_never_checks_downloads_or_installs(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from update_controller import UpdateController,MAC_MESSAGE
        with tempfile.TemporaryDirectory() as folder,patch('update_controller.UpdateJob') as job:
            c=UpdateController('0.8.8',Path(folder));c.configure(True)
            self.assertFalse(c.enabled);self.assertFalse(c.check());self.assertFalse(c.download_install())
            job.assert_not_called();self.assertEqual(c.state['message'],MAC_MESSAGE);c.shutdown()

if __name__=='__main__':unittest.main()
