"""Run isolated source tests and a short offscreen GUI startup; no packaging."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    'test_enhanced_core', 'test_public_announcements',
    'test_public_announcements_panel', 'test_announcement_integration',
    'test_tls_context', 'test_announcement_sound', 'test_windows_startup',
    'test_profile_isolation', 'test_video_fullscreen', 'test_material_store',
    'test_reset_watch', 'test_x_announcements', 'test_source_updates',
    'test_windows_ipc', 'test_live_compaction', 'test_connection_and_sessions',
    'test_conversation_navigation', 'test_read_completion', 'test_wsl_codex',
    'test_refresh_flow', 'test_quota',
)

def run():
    # macOS Unix-domain socket paths have a short limit; its default per-user
    # temp path plus the isolated instance name can exceed that limit.
    with tempfile.TemporaryDirectory(prefix='bl-ci-', dir='/tmp' if sys.platform == 'darwin' else None) as directory:
        base = Path(directory)
        env = os.environ.copy()
        env.update(LOCALAPPDATA=str(base/'local'), APPDATA=str(base/'roaming'),
                   CODEX_HOME=str(base/'codex'), BAILONG_CODEX_HOME=str(base/'codex'),
                   BAILONG_CODEX=str(base/'missing-codex.exe'),
                   PYTHONPATH=str(ROOT/'app'), QT_QPA_PLATFORM='offscreen',
                   PYTHONUTF8='1')
        (base/'codex').mkdir()
        if sys.platform == 'darwin':
            (base/'tmp').mkdir()
            env['TMPDIR'] = str(base/'tmp')
        subprocess.run([sys.executable, '-m', 'unittest', '-v', *TESTS],
                       cwd=ROOT/'app', env=env, check=True, timeout=180)
        # Separate fresh state proves the actual entry point initializes and
        # exits through its built-in, monitor-free smoke mode.
        env['LOCALAPPDATA'] = str(base/'smoke-local')
        env['APPDATA'] = str(base/'smoke-roaming')
        completed = subprocess.run([sys.executable, str(ROOT/'app/enhanced.py'), '--smoke-test'],
                                   cwd=ROOT, env=env, check=True, timeout=45)
        state = Path(env['LOCALAPPDATA'])/'BailongEnhanced'
        runtime = json.loads((state/'runtime.json').read_text(encoding='utf-8'))
        assert runtime.get('decode_error') in (None, ''), 'Animation decoder failed'
        assert runtime.get('local_build') == '1.0.1-community.2-preview.1'
        assert not list((Path(env['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup').glob('*'))
        assert not list((Path(env['LOCALAPPDATA'])/'LaunchAgents').glob('*'))
        print(json.dumps({'platform': sys.platform, 'python': sys.version.split()[0],
                          'tests': 'passed', 'offscreen_smoke_exit': completed.returncode,
                          'version': runtime['local_build'], 'startup_entries_created': False}))

if __name__ == '__main__':
    run()
