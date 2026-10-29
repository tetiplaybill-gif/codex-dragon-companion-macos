"""macOS Codex discovery, presence, links and the watcher lock (skipped elsewhere)."""
import json,os,plistlib,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import codex_mac
import codex_startup as cs
from desktop_services import open_codex

SID='11111111-1111-4111-8111-111111111111'

def bundle(root,name,ident,exe):
    path=Path(root)/name;(path/'Contents/MacOS').mkdir(parents=True)
    (path/'Contents/Info.plist').write_bytes(plistlib.dumps(dict(CFBundleIdentifier=ident,CFBundleExecutable=exe)))
    (path/'Contents/MacOS'/exe).write_text('');return path

def package(root,entry='bin/codex'):
    root=Path(root);(root/'bin').mkdir(parents=True);(root/'codex-package.json').write_text(json.dumps(dict(entrypoint=entry)))
    cli=root/'bin/codex';cli.write_text('#!/bin/sh\n');cli.chmod(0o755);return cli

def process(pid,name,exe,args=()):
    p=Mock(pid=pid,info=dict(name=name,exe=exe));p.exe.return_value=exe;p.cmdline.return_value=[exe,*args];p.create_time.return_value=100.
    return p

@unittest.skipUnless(sys.platform=='darwin','macOS Codex layout')
class MacCodexTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_only_the_main_app_executable_is_the_desktop(self):
        app=bundle(self.root,'ChatGPT.app','com.openai.codex','ChatGPT')
        helper=bundle(app/'Contents/Frameworks','Codex (Renderer).app','com.openai.codex.helper.renderer','Codex (Renderer)')
        cli=bundle(app/'Contents/Resources/codex-cli','CodexCLI.app','com.openai.codex.cli','codex')
        self.assertTrue(codex_mac.desktop_executable(app/'Contents/MacOS/ChatGPT'))
        for exe in (helper/'Contents/MacOS/Codex (Renderer)',cli/'Contents/MacOS/codex',app/'Contents/MacOS/Other',self.root/'codex'):
            self.assertFalse(codex_mac.desktop_executable(exe),exe)
    def test_package_entry_is_confined_and_executable(self):
        self.assertEqual(codex_mac.package_entry(self.root/'a'),None)
        cli=package(self.root/'a');self.assertEqual(codex_mac.package_entry(self.root/'a'),cli)
        cli.chmod(0o644);self.assertEqual(codex_mac.package_entry(self.root/'a'),None)
        package(self.root/'b','../a/bin/codex');self.assertEqual(codex_mac.package_entry(self.root/'b'),None)
    def test_bundled_cli_comes_before_the_daemon_copy(self):
        app=bundle(self.root,'ChatGPT.app','com.openai.codex','ChatGPT')
        bundled=package(app/'Contents/Resources/codex-cli');daemon=package(self.root/'home/packages/app-server-daemon/current')
        with patch.object(codex_mac,'installed_bundles',return_value=[app]),patch.object(codex_mac.shutil,'which',return_value=None):
            found=list(codex_mac.cli_candidates(self.root/'home'))
        self.assertEqual(found[:2],[bundled,daemon])
    def test_desktop_sessions_skip_helpers_and_report_uncertain_scans(self):
        app=bundle(self.root,'ChatGPT.app','com.openai.codex','ChatGPT')
        cli=bundle(self.root,'CodexCLI.app','com.openai.codex.cli','codex')
        values=[process(1,'ChatGPT',str(app/'Contents/MacOS/ChatGPT')),process(2,'codex',str(cli/'Contents/MacOS/codex')),
                process(3,'ChatGPT',str(app/'Contents/MacOS/ChatGPT'),('--type=renderer',)),process(4,'Finder','/System/Finder')]
        with patch.object(cs.psutil,'process_iter',return_value=values):self.assertEqual(cs.desktop_sessions(),{(1,100.)})
        denied=process(5,'ChatGPT','x');denied.exe.side_effect=cs.psutil.AccessDenied(5)
        with patch.object(cs.psutil,'process_iter',return_value=[denied]):self.assertIsNone(cs.desktop_sessions())
    def test_links_and_app_launch_use_open_without_a_shell(self):
        with patch.object(codex_mac.subprocess,'run',return_value=Mock(returncode=0)) as run:
            open_codex(SID);open_codex()
        self.assertEqual(run.call_args_list[0].args[0],['/usr/bin/open','codex://threads/'+SID])
        self.assertEqual(run.call_args_list[1].args[0],['/usr/bin/open','-b','com.openai.codex'])
        with patch.object(codex_mac.subprocess,'run',return_value=Mock(returncode=1)):
            with self.assertRaisesRegex(OSError,'对应会话'):open_codex(SID)
    def test_watcher_lock_is_single_instance(self):
        with patch.dict(os.environ,LOCALAPPDATA=str(self.root)):
            first=cs.instance_lock();self.assertIsNotNone(first)
            self.assertIsNone(cs.instance_lock())
            first.close();second=cs.instance_lock();self.assertIsNotNone(second);second.close()
    def test_watcher_hands_off_to_the_copy_named_by_the_login_agent(self):
        moved=self.root/'Applications/BailongEnhanced.app/Contents/MacOS/BailongEnhanced';moved.parent.mkdir(parents=True);moved.write_text('')
        with patch.dict(os.environ,LOCALAPPDATA=str(self.root)),patch.object(cs,'spawn') as launch,patch.object(cs,'desktop_sessions',return_value=set()),\
                patch.object(cs,'current_command',return_value=['/old/BailongEnhanced']):
            cs.atomic(cs.preference_path(),{'enabled':True})
            from platform_paths import launch_agent,write_launch_agent
            path,label=launch_agent('codex-sync');write_launch_agent(path,label,[moved,'--watch-codex'])
            self.assertEqual(cs.main(),0)
        launch.assert_called_once_with([str(moved),'--watch-codex'])

WSL_PROFILE=dict(source='wsl',home='',cli='',wsl_distro='Ubuntu',wsl_user='alice',wsl_home='/home/alice/.codex',wsl_cli='/usr/bin/codex',wsl_path='/usr/bin:/bin')

class WslSourceGuardTests(unittest.TestCase):
    """Runs everywhere: a WSL profile copied from Windows never reaches wsl.exe on macOS, and Windows keeps WSL."""
    def test_macos_ignores_a_saved_wsl_source(self):
        import codex_connection as connection,wsl_codex as wsl
        with tempfile.TemporaryDirectory() as home,patch('codex_connection.sys.platform','darwin'),patch('codex_connection.saved_paths',return_value=WSL_PROFILE),\
             patch.dict(os.environ,{'BAILONG_CODEX_HOME':home}),\
             patch('wsl_codex.running',side_effect=AssertionError('wsl.exe probed')),patch('wsl_codex.command',side_effect=AssertionError('wsl.exe command')):
            self.assertFalse(connection.is_wsl_source())
            self.assertFalse(connection.is_wsl_source(wsl.unc('Ubuntu','/home/alice/.codex')))
            self.assertEqual(connection.data_home(),Path(home).resolve())
            self.assertEqual(connection.cli_command('codex','--version'),['codex','--version'])
            self.assertEqual(connection.child_environment()['CODEX_HOME'],str(Path(home).resolve()))
    def test_macos_rejects_saving_a_wsl_source(self):
        import codex_connection as connection
        with patch('codex_connection.sys.platform','darwin'),patch('wsl_codex.validate',side_effect=AssertionError('WSL validation')):
            with self.assertRaisesRegex(ValueError,'WSL'):connection.validate_paths(WSL_PROFILE)
    def test_windows_keeps_the_wsl_source(self):
        import codex_connection as connection,wsl_codex as wsl
        with patch('codex_connection.sys.platform','win32'),patch('codex_connection.saved_paths',return_value=WSL_PROFILE):
            self.assertTrue(connection.is_wsl_source())
            self.assertEqual(str(connection.data_home()),wsl.unc('Ubuntu','/home/alice/.codex'))
            self.assertTrue(connection.is_wsl_source(connection.data_home()))

if __name__=='__main__':unittest.main()
